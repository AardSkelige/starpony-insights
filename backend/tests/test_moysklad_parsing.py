"""Разбор значений из API.

Обе проверяемые здесь ошибки не падают, а тихо врут: сдвиг времени на три часа
и потеря знаков в себестоимости выглядят как правдоподобные числа.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from moysklad.parsing import MOYSKLAD_TZ, parse_datetime, parse_decimal


class TestParseDatetime:
    def test_moscow_time_not_utc(self):
        """МойСклад отдаёт московское время без указания пояса.

        Принять его за UTC — сдвинуть всё на три часа: вечерняя отгрузка
        уедет во вчера, и отчёт за день не сойдётся с учётом.
        """
        parsed = parse_datetime("2026-08-27 10:55:00.000")
        assert parsed.tzinfo is not None, "время обязано быть с поясом"
        assert parsed.astimezone(timezone.utc).hour == 7

    def test_handles_both_formats(self):
        """API отдаёт время и с миллисекундами, и без."""
        assert parse_datetime("2026-08-27 10:55:00.000") == datetime(
            2026, 8, 27, 10, 55, tzinfo=MOYSKLAD_TZ
        )
        assert parse_datetime("2026-08-27 10:55:00") == datetime(
            2026, 8, 27, 10, 55, tzinfo=MOYSKLAD_TZ
        )

    @pytest.mark.parametrize("value", [None, "", "не время", "27.08.2026"])
    def test_bad_values_give_none(self, value):
        """Неразобранное время — None, а не сегодняшняя дата: подставленное
        «сейчас» выглядит достоверно и потому опаснее пустоты."""
        assert parse_datetime(value) is None


class TestParseDecimal:
    def test_no_float_error_leaks_in(self):
        """Разбор идёт через str: Decimal(0.1) уносит погрешность в расчёты."""
        assert parse_decimal(0.1) == Decimal("0.1")
        assert parse_decimal(0.1) != Decimal(0.1)

    def test_keeps_fractional_kopecks(self):
        """У 150 из 255 позиций себестоимость в дробных копейках.

        Округление до целой копейки даёт 65 копеек расхождения на тысячу
        единиц — на 89 техкартах это уже видно в марже.
        """
        parsed = parse_decimal(11841.934782608696, kopecks_to_units=True)
        assert parsed == Decimal("118.41934782608696")
        assert parsed != Decimal("118.42")

    def test_kopecks_to_roubles(self):
        assert parse_decimal(422000.0, kopecks_to_units=True) == Decimal("4220")

    @pytest.mark.parametrize("value", [None, "", "не число", {}])
    def test_bad_values_give_none(self, value):
        assert parse_decimal(value) is None
