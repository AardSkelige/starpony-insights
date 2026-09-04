"""Проставить неснижаемый остаток в карточки товаров МойСклада.

Запускается кроном раз в сутки, после ночного синка документов: порог
считается от темпа продаж, а темп меняется вместе с отгрузками.
"""

import os

from django.core.management.base import BaseCommand, CommandError

from moysklad.client import MoySkladClient
from moysklad.writeback.journal import WritebackDisabled
from moysklad.writeback.min_balance import run_min_balance_writeback


class Command(BaseCommand):
    help = "Записать неснижаемый остаток в карточки товаров"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать, что изменилось бы, ничего не записывая",
        )
        # `--cron`, а не `--manual`: контракт общий с записью себестоимости,
        # и умолчание там обратное — без флага прогон считается ручным.
        # Два разных флага на одну механику разъехались бы, и однажды кто-то
        # передал бы не тот: журнал перестал бы отличать расписание
        # от человека ровно тогда, когда это важнее всего.
        parser.add_argument(
            "--cron",
            action="store_true",
            help="Запуск по расписанию. Прогон не помечается как запущенный человеком.",
        )

    def handle(self, *args, **options):
        token = os.getenv("MOYSKLAD_TOKEN")
        if not token:
            raise CommandError("MOYSKLAD_TOKEN не задан. Добавьте его в backend/.env")

        client = MoySkladClient(token=token)

        try:
            run = run_min_balance_writeback(
                client, dry_run=options["dry_run"], manual=not options["cron"]
            )
        except WritebackDisabled as stop:
            # Не ошибка, а решение человека: выключатель выключен. Команда
            # обязана сказать это словами, а не упасть с трассировкой —
            # иначе крон каждую ночь шлёт письмо о «сбое».
            self.stdout.write(self.style.WARNING(str(stop)))
            return

        self.stdout.write(
            f"Рассмотрено {run.considered}, изменено {run.changed}, "
            f"пропущено {run.skipped} "
            f"(значение неизвестно {run.skipped_unknown}, "
            f"уже совпадает {run.skipped_equal}), "
            f"ошибок {run.failed}. Запросов к API: {run.request_count}."
        )
        if run.error:
            self.stderr.write(self.style.ERROR(run.error))
