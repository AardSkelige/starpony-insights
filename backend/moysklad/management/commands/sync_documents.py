"""Полная синхронизация справочников и документов. Запускается ночью.

Инкремента нет намеренно: при тысяче документов полный проход занимает секунды,
а у него нет класса ошибок «пропустили правку задним числом». Порог перехода
на инкремент по `updated` — когда полный проход перевалит за 10 минут
или документов станет больше 20 000. Раньше — преждевременная оптимизация.
"""

import os

from django.core.management.base import BaseCommand, CommandError

from core.models import SyncKind
from moysklad.client import MoySkladClient
from moysklad.limits import ApiDisabledRisk
from moysklad.sync import advisory_lock
from moysklad.sync.catalog import sync_products, sync_uoms
from moysklad.sync.documents import sync_demands, sync_supplies
from moysklad.sync.references import sync_counterparties, sync_sales_channels
from moysklad.sync.runner import SyncSession

# Порядок обязателен, а не для красоты: документы ссылаются на товары,
# контрагентов и каналы, а товары — на единицы измерения. Справочники
# идут первыми, иначе документ не на что будет повесить.
ENTITIES = (
    ("uom", sync_uoms),
    ("product", sync_products),
    ("counterparty", sync_counterparties),
    ("saleschannel", sync_sales_channels),
    ("demand", sync_demands),
    ("supply", sync_supplies),
)


class Command(BaseCommand):
    help = "Синхронизировать справочники и документы из МойСклада"

    def add_arguments(self, parser):
        parser.add_argument(
            "--manual",
            action="store_true",
            help="Отметить прогон как запущенный кнопкой, а не расписанием",
        )

    def handle(self, *args, **options):
        token = os.getenv("MOYSKLAD_TOKEN")
        if not token:
            raise CommandError(
                "MOYSKLAD_TOKEN не задан. Добавьте его в backend/.env"
            )

        with advisory_lock("sync:documents") as acquired:
            if not acquired:
                self.stdout.write("Синхронизация уже идёт — пропускаем запуск.")
                return

            client = MoySkladClient(token=token)
            session = SyncSession(SyncKind.DOCUMENTS, manual=options["manual"])
            stopped = ""

            for name, sync in ENTITIES:
                try:
                    session.record(name, sync(client, session.run))
                except ApiDisabledRisk as risk:
                    # Предохранитель сработал: продолжать нельзя, иначе
                    # МойСклад отключит доступ всей компании.
                    stopped = str(risk)
                    self.stderr.write(self.style.ERROR(stopped))
                    break

            run = session.finish(request_count=client.request_count, error=stopped)

            self.stdout.write(
                f"{run.get_status_display()}. "
                f"Запросов к API: {run.request_count}, "
                f"время: {run.duration_seconds:.1f}с"
            )
