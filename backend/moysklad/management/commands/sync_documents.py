"""Полная синхронизация справочников и документов. Запускается ночью.

Инкремента нет намеренно: при тысяче документов полный проход занимает секунды,
а у него нет класса ошибок «пропустили правку задним числом». Порог перехода
на инкремент по `updated` — когда полный проход перевалит за 10 минут
или документов станет больше 20 000. Раньше — преждевременная оптимизация.

Сам проход живёт в `moysklad/sync/full.py`: его же запускает кнопка
«Обновить» на странице, и двух копий порядка сущностей быть не должно.
"""

from django.core.management.base import BaseCommand, CommandError

from moysklad.sync.full import AlreadyRunning, TokenMissing, run_documents_sync


class Command(BaseCommand):
    help = "Синхронизировать справочники и документы из МойСклада"

    def add_arguments(self, parser):
        parser.add_argument(
            "--manual",
            action="store_true",
            help="Отметить прогон как запущенный кнопкой, а не расписанием",
        )

    def handle(self, *args, **options):
        try:
            run = run_documents_sync(manual=options["manual"])
        except TokenMissing:
            raise CommandError("MOYSKLAD_TOKEN не задан. Добавьте его в backend/.env")
        except AlreadyRunning:
            self.stdout.write("Синхронизация уже идёт — пропускаем запуск.")
            return

        self.stdout.write(
            f"{run.get_status_display()}. "
            f"Запросов к API: {run.request_count}, "
            f"время: {run.duration_seconds:.1f}с"
        )
