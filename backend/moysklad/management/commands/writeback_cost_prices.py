"""Проставить себестоимость в карточки товаров МойСклада.

Запускается по расписанию (`deploy/cron/starpony.cron`) и руками.
Пробный прогон обязателен после любой правки расчёта:

    python manage.py writeback_cost_prices --dry-run
"""

import os

from django.core.management.base import BaseCommand, CommandError

from core.models import WritebackStatus
from moysklad.client import MoySkladClient
from moysklad.writeback.cost_prices import ReferenceMissing, run_cost_prices_writeback
from moysklad.writeback.journal import WritebackDisabled


class Command(BaseCommand):
    help = "Записать FIFO-себестоимость в тип цены «Себестоимость» карточек товаров"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только показать, что изменилось бы. В учёт ничего не пишется.",
        )
        parser.add_argument(
            "--cron",
            action="store_true",
            help="Запуск по расписанию. Прогон не помечается как запущенный человеком.",
        )

    def handle(self, *args, **options):
        token = os.getenv("MOYSKLAD_TOKEN")
        if not token:
            raise CommandError("MOYSKLAD_TOKEN не задан")

        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("Пробный прогон — учёт не меняется"))

        client = MoySkladClient(token=token)
        try:
            run = run_cost_prices_writeback(
                client,
                dry_run=dry_run,
                # Расписание запускает ту же команду, что и человек. Без флага
                # все четыре суточных прогона писались бы в журнал как ручные,
                # и поле перестало бы отвечать на вопрос, ради которого заведено.
                manual=not options["cron"],
            )
        except WritebackDisabled as disabled:
            raise CommandError(str(disabled)) from disabled
        except ReferenceMissing as missing:
            raise CommandError(str(missing)) from missing

        self._report(run)

    def _report(self, run):
        verb = "изменилось бы" if run.dry_run else "изменено"
        # Пропуск с разбивкой по причине. Склеенное «пропущено 315» читалось
        # одинаково и как «всё уже сходится», и как «запись не работает»,
        # а отличить одно от другого было нечем.
        self.stdout.write(
            f"Рассмотрено {run.considered}, {verb} {run.changed}, "
            f"пропущено {run.skipped} "
            f"(без себестоимости {run.skipped_unknown}, "
            f"уже совпадает {run.skipped_equal}), "
            f"запросов {run.request_count}"
        )

        for change in run.changes.all()[:50]:
            if change.error:
                self.stdout.write(self.style.ERROR(
                    f"  {change.target_name}: {change.error}"
                ))
                continue
            was = "—" if change.old_value is None else f"{change.old_value / 100:.2f}"
            self.stdout.write(
                f"  {change.target_name}: {was} → {change.new_value / 100:.2f} ₽"
            )

        if run.failed:
            self.stdout.write(self.style.ERROR(f"Не удалось записать: {run.failed}"))
        if run.error:
            self.stdout.write(self.style.ERROR(run.error))

        if run.status == WritebackStatus.SUCCESS:
            self.stdout.write(self.style.SUCCESS("Готово"))
        else:
            raise CommandError(f"Итог прогона: {run.get_status_display()}")
