"""Регулярность поставок: как часто поставщик привозит.

Ошибка здесь тихая ровно так же, как в сроке поставки: число остаётся
правдоподобным. «Возит раз в 22 дня» вместо «раз в 6» никто не оспорит,
а закупку по нему спланируют.

Проверяется то, из-за чего расчёт врал бы, не подавая вида: подмена медианы
средним, документы вместо дней и ноль, выданный за отсутствие промежутка.
"""

from decimal import Decimal

import pytest

from api.suppliers.services import regularity, selection
from core.models import Document, DocumentKind
from tests.suppliers.conftest import moscow

pytestmark = pytest.mark.django_db


def measured():
    """Приёмки так, как их берёт страница."""
    return list(selection.supplies())


class TestMedianNotAverage:
    def test_one_long_gap_does_not_move_the_median(self, make_supply):
        """«Полицвет» с боевых: возит раз в неделю, но однажды пропал
        на 73 дня. Среднее 22,5 дня против медианы 6,5 — вчетверо."""
        for day in (1, 5, 11, 15, 19):
            make_supply(moment=moscow(2026, 4, day))
        make_supply(moment=moscow(2026, 7, 1))

        result = regularity.of(measured())

        # Промежутки 4, 6, 4, 4 и 73 дня: медиана 4, среднее 18,2 — вчетверо.
        assert result.days == Decimal("4")
        assert result.average_days == Decimal("18.2")

    def test_spread_comes_along_for_the_explanation(self, make_supply):
        """Медиана без разброса рядом описывает поставку, которой не было:
        у «Ревады-Невы» 21 день сложился из 2 и 40."""
        for day in (1, 3, 30):
            make_supply(moment=moscow(2026, 4, day))

        result = regularity.of(measured())

        assert (result.min_days, result.max_days) == (2, 27)
        assert result.gaps == 2


class TestDaysNotDocuments:
    def test_same_day_supplies_are_one_delivery(self, make_supply):
        """У «Интернет Решений» 31 марта три приёмки. Считай мы документами,
        появились бы интервалы в ноль дней — цикл поставки, которого нет.

        Дедупликация меняет числа заметно: у них же среднее 13,7 → 17,8."""
        for _ in range(3):
            make_supply(moment=moscow(2026, 4, 1))
        make_supply(moment=moscow(2026, 4, 11))

        result = regularity.of(measured())

        assert result.delivery_days == 2
        assert result.gaps == 1
        assert result.days == Decimal("10")

    def test_hours_within_a_day_do_not_split_it(self, make_supply):
        """Две приёмки одного дня в 9 утра и в 6 вечера — одна поставка."""
        make_supply(moment=moscow(2026, 4, 1, hour=9))
        make_supply(moment=moscow(2026, 4, 1, hour=18))

        assert regularity.of(measured()).delivery_days == 1


class TestNothingToMeasure:
    def test_single_delivery_has_no_interval(self, make_supply):
        """Семь поставщиков из двадцати трёх привозили однажды. Промежутка
        между поставками не существует, и ноль читался бы как «возит
        каждый день»."""
        make_supply(moment=moscow(2026, 4, 1))

        result = regularity.of(measured())

        assert result.days is None
        assert result.gaps == 0
        assert result.delivery_days == 1

    def test_empty_selection_says_nothing(self):
        assert regularity.of([]) == regularity.NOTHING


class TestSelection:
    def test_drafts_and_deleted_stay_out(self, make_supply):
        """По черновику приёмки товар на склад ещё не пришёл, а исчезнувший
        из учёта документ не должен попадать ни в одну сумму. Попади они
        в выборку — регулярность считалась бы по поставкам, которых не было.
        """
        make_supply(moment=moscow(2026, 4, 1))
        make_supply(moment=moscow(2026, 4, 5), applicable=False)
        make_supply(moment=moscow(2026, 4, 9), deleted=True)

        assert regularity.of(measured()).delivery_days == 1

    def test_other_document_kinds_stay_out(self, make_supply, supplier, run):
        """Отгрузка в выборку приёмок попасть не должна: у неё и контрагент
        тот же бывает, и период тот же, а поставкой она не является.

        Проверяется здесь, а не в помощнике теста: отбор решает `selection`,
        и именно на него опирается страница.
        """
        make_supply(moment=moscow(2026, 4, 1))
        Document.objects.create(
            ms_id="90000000-0000-0000-0000-000000000001",
            kind=DocumentKind.DEMAND,
            number="О-00001",
            moment=moscow(2026, 4, 5),
            agent=supplier,
            last_seen_run=run,
        )

        assert len(measured()) == 1

    def test_period_narrows_the_selection(self, make_supply):
        for day in (1, 10, 20):
            make_supply(moment=moscow(2026, 4, day))

        inside = list(
            selection.supplies(
                date_from=moscow(2026, 4, 5).date(), date_to=moscow(2026, 4, 20).date()
            )
        )

        assert regularity.of(inside).delivery_days == 2

    def test_last_day_of_period_is_included(self, make_supply):
        """Документ, проведённый в 23:59, обязан войти в свой день:
        сравнение с концом дня теряет его без единого признака."""
        make_supply(moment=moscow(2026, 4, 20, hour=23))

        inside = list(
            selection.supplies(
                date_from=moscow(2026, 4, 1).date(), date_to=moscow(2026, 4, 20).date()
            )
        )

        assert len(inside) == 1
