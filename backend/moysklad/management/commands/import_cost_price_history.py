"""Перенести историю прогонов себестоимости из Horse Bio в журнал.

Одноразовая операция, но команда остаётся в репозитории: без неё через месяц
не ответить, откуда в журнале записи старше самой системы.

История лежала в `.sync_state.json` внутри боевого тома `sp_cost_prices_data`
и обрезалась демоном до 90 записей — то есть примерно до трёх недель при
четырёх прогонах в сутки. Всё, что старше, потеряно безвозвратно ещё до
переезда; забрали то, что было.

    python manage.py import_cost_price_history /путь/к/.sync_state.json
"""

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand, CommandError

from core.models import (
    WritebackChange,
    WritebackKind,
    WritebackRun,
    WritebackStatus,
)

# Демон писал время без пояса, а работал по московскому — как и весь учёт.
MOSCOW = ZoneInfo("Europe/Moscow")
FIELD = "Себестоимость"


class Command(BaseCommand):
    help = "Импортировать историю прогонов себестоимости из .sync_state.json"

    def add_arguments(self, parser):
        parser.add_argument("path", type=str, help="Путь к .sync_state.json")
        parser.add_argument(
            "--dry-run", action="store_true", help="Только показать, что импортируется"
        )

    def handle(self, *args, **options):
        path = Path(options["path"])
        if not path.exists():
            raise CommandError(f"Файл не найден: {path}")

        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as broken:
            raise CommandError(f"Файл не разбирается как JSON: {broken}") from broken

        history = state.get("history") or []
        if not history:
            raise CommandError("В файле нет истории прогонов")

        imported, skipped, changes_total = 0, 0, 0

        for record in history:
            started = self._parse_moment(record.get("date"))
            if started is None:
                self.stderr.write(f"Пропущен прогон с датой {record.get('date')!r}")
                skipped += 1
                continue

            # Повторный запуск не должен задваивать: дата прогона уникальна,
            # демон запускался раз в пять часов.
            if WritebackRun.objects.filter(
                kind=WritebackKind.COST_PRICES, started_at=started
            ).exists():
                skipped += 1
                continue

            changes = record.get("changes") or []
            errors = record.get("errors") or []
            changes_total += len(changes)

            if options["dry_run"]:
                imported += 1
                continue

            run = self._create_run(record, started, changes, errors)
            self._create_changes(run, changes, errors)
            imported += 1

        verb = "будет импортировано" if options["dry_run"] else "импортировано"
        self.stdout.write(
            f"Прогонов {verb}: {imported}, пропущено: {skipped}, "
            f"изменений цен: {changes_total}"
        )
        self.stdout.write(self.style.SUCCESS("Готово"))

    @staticmethod
    def _parse_moment(raw: str | None) -> datetime | None:
        if not raw:
            return None
        try:
            return datetime.strptime(raw, "%Y-%m-%d %H:%M").replace(tzinfo=MOSCOW)
        except ValueError:
            return None

    @staticmethod
    def _create_run(record, started, changes, errors) -> WritebackRun:
        stats = record.get("stats") or {}
        skipped_same = stats.get("skipped_same", 0)
        skipped_zero = stats.get("skipped_zero", 0)

        if errors and changes:
            status = WritebackStatus.PARTIAL
        elif errors:
            status = WritebackStatus.FAILED
        else:
            status = WritebackStatus.SUCCESS

        return WritebackRun.objects.create(
            kind=WritebackKind.COST_PRICES,
            status=status,
            started_at=started,
            # Длительности прежний демон не хранил. Ставим то же время,
            # а не выдуманное: нулевая длительность честнее правдоподобной.
            finished_at=started,
            considered=stats.get("updated", 0) + skipped_same + skipped_zero,
            changed=stats.get("updated", 0),
            skipped=skipped_same + skipped_zero,
            failed=len(errors),
            # Запросы демон не считал вовсе.
            request_count=0,
        )

    @staticmethod
    def _create_changes(run, changes, errors) -> None:
        rows = []
        for change in changes:
            rows.append(
                WritebackChange(
                    run=run,
                    target_ms_id=change["id"],
                    target_name=change.get("name", "—")[:255],
                    field=FIELD,
                    # Демон хранил рубли, у нас копейки — как в самом учёте.
                    old_value=Decimal(str(change.get("old_rub", 0))) * 100,
                    new_value=Decimal(str(change.get("new_rub", 0))) * 100,
                )
            )
        for failure in errors:
            rows.append(
                WritebackChange(
                    run=run,
                    target_ms_id=failure["id"],
                    target_name=failure.get("name", "—")[:255],
                    field=FIELD,
                    error=str(failure.get("error", ""))[:2000],
                )
            )
        WritebackChange.objects.bulk_create(rows)
