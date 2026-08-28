"""Доли и перевод копеек в рубли."""

from decimal import Decimal

from core.money import rubles, share


class TestShare:
    def test_divides_within_the_selection(self):
        assert share(25, 100) == Decimal("0.25")

    def test_unknown_part_stays_unknown(self):
        """Нет числителя — нет доли. Ноль читался бы как «доля нулевая»."""
        assert share(None, 100) is None

    def test_nothing_to_divide_by(self):
        """Нулевая выручка выборки: доли нет, а не «сто процентов»."""
        assert share(10, 0) is None
        assert share(10, -5) is None

    def test_can_exceed_one(self):
        """Больше единицы — не ошибка: сырья бывает дороже выручки.

        6 июля 2026 выручка 7,13 ₽ против сырья на 290,91 ₽ — товар
        отгружали за 0 ₽. Обрезать такую долю значило бы спрятать факт.
        """
        assert share(29091, 713) > 1

    def test_keeps_precision(self):
        """Делит в Decimal: во float доля теряет знаки, а по ней сортируют."""
        assert isinstance(share(1, 3), Decimal)


class TestRubles:
    def test_converts_kopecks(self):
        assert rubles(23153038) == 231530.38

    def test_keeps_unknown_unknown(self):
        """Цены нет — в ячейке пусто, а не ноль: ноль читается как «даром»."""
        assert rubles(None) is None

    def test_accepts_fractional_kopecks(self):
        """Удельные величины приходят дробными копейками — 2,5 копейки за грамм."""
        assert rubles(Decimal("2.50")) == 0.025
