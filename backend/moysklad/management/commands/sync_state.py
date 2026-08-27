"""Синхронизация изменчивого: остатки, резервы, себестоимость.

Идёт каждые 10–15 минут, в отличие от ночного `sync_documents`. Разделение
по линии «факты против состояния»: проведённый документ не меняется, а остаток
меняется после каждой отгрузки.

Своя блокировка, отдельная от документов: эти прогоны не должны ждать друг
друга, но и наезжать друг на друга тоже не должны — лимит общий.
"""

import os

from django.core.management.base import BaseCommand, CommandError

from core.models import SyncKind
from moysklad.client import MoySkladClient
from moysklad.limits import ApiDisabledRisk
from moysklad.sync import advisory_lock
from moysklad.sync.runner import SyncSession
from moysklad.sync.stock import sync_stock

ENTITIES = (("stock", sync_stock),)


class Command(BaseCommand):
    help = "Обновить остатки и себестоимость из МойСклада"

    def add_arguments(self, parser):
        parser.add_argument(
            "--manual",
            action="store_true",
            help="Отметить прогон как запущенный кнопкой, а не расписанием",
        )

    def handle(self, *args, **options):
        token = os.getenv("MOYSKLAD_TOKEN")
        if not token:
            raise CommandError("MOYSKLAD_TOKEN не задан. Добавьте его в backend/.env")

        with advisory_lock("sync:state") as acquired:
            if not acquired:
                self.stdout.write("Обновление остатков уже идёт — пропускаем запуск.")
                return

            client = MoySkladClient(token=token)
            session = SyncSession(SyncKind.STATE, manual=options["manual"])
            stopped = ""

            for name, sync in ENTITIES:
                try:
                    session.record(name, sync(client, session.run))
                except ApiDisabledRisk as risk:
                    stopped = str(risk)
                    self.stderr.write(self.style.ERROR(stopped))
                    break

            run = session.finish(request_count=client.request_count, error=stopped)
            self.stdout.write(
                f"{run.get_status_display()}. Запросов к API: {run.request_count}, "
                f"время: {run.duration_seconds:.1f}с"
            )
