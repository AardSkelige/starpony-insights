"""Запас в днях — первая половина порога закупки.

Ошибка здесь тихая: число остаётся правдоподобным. «Хватит на 90 дней»
вместо «на 9» никто не заметит, пока сырьё не кончится посреди партии.
"""

from datetime import date
from decimal import Decimal

import pytest

from core.services.coverage import (
    CRITICAL_DAYS,
    LOW_DAYS,
    days_in,
    level,
    of,
)


class TestPeriodLength:
    def test_both_bounds_are_inclusive(self):
        """1–2 августа — два дня, а не один: обе границы входят в период."""
        assert days_in(date(2026, 8, 1), date(2026, 8, 2), 999) == 2

    def test_one_day_period_is_one_day(self):
        """Деление на ноль дней дало бы бесконечный расход."""
        assert days_in(date(2026, 8, 1), date(2026, 8, 1), 999) == 1

    def test_open_period_falls_back_to_the_data(self):
        """«Весь период» — это фактические даты выборки, а не догадка."""
        assert days_in(None, None, 148) == 148
        assert days_in(date(2026, 8, 1), None, 148) == 148

    def test_never_zero(self):
        """Пустая выборка не должна ронять расчёт делением на ноль."""
        assert days_in(None, None, 0) == 1


class TestCoverage:
    def test_days_left_is_stock_over_daily_rate(self):
        """Диметикон с боевых: 36 168 г за 148 дней против остатка 132,58 г."""
        result = of(Decimal("36168"), 148, Decimal("132.58"))

        assert round(result.per_day, 1) == Decimal("244.4")
        assert result.days_left == 0

    def test_rounds_down(self):
        """«Хватит на 2,9 дня» — это два дня. Вверх значит пообещать
        день, которого нет."""
        assert of(Decimal("100"), 10, Decimal("29")).days_left == 2

    def test_no_stock_is_unknown_not_zero(self):
        """У 36 материалов из 161 остатка в отчёте нет вовсе.

        Ноль читался бы как «кончился» — утверждение об учёте, которого
        учёт не делает.
        """
        result = of(Decimal("824.5"), 148, None)

        assert result.days_left is None
        assert result.per_day > 0

    def test_no_consumption_gives_no_answer(self):
        """Материал не расходовался — делить не на что.

        Ноль здесь означал бы «кончится сегодня», хотя не кончится никогда
        при таком расходе.
        """
        assert of(Decimal(0), 148, Decimal("500")).days_left is None

    def test_negative_stock_is_treated_as_empty(self):
        """Отрицательный остаток в учёте бывает — это пересорт, не запас."""
        assert of(Decimal("100"), 10, Decimal("-50")).days_left == 0

    def test_carries_its_own_arithmetic(self):
        """Формула собирается из полученного, а не пересчитывается фронтом."""
        result = of(Decimal("1480"), 148, Decimal("300"))

        assert result.per_day == 10
        assert result.days_of_period == 148
        assert result.available == 300
        assert result.days_left == 30


class TestLevel:
    def test_unknown_stock_has_its_own_level(self):
        """«Не знаем» — не то же самое, что «всё хорошо»."""
        assert level(None) == "none"

    @pytest.mark.parametrize("days", [0, 3, CRITICAL_DAYS])
    def test_two_weeks_or_less_is_critical(self, days):
        """Две недели — примерный срок поставки: заказывать уже поздно."""
        assert level(days) == "critical"

    @pytest.mark.parametrize("days", [CRITICAL_DAYS + 1, LOW_DAYS])
    def test_up_to_a_month_is_low(self, days):
        assert level(days) == "low"

    def test_more_than_a_month_is_fine(self):
        assert level(LOW_DAYS + 1) == "ok"
