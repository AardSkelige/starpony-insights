"""Срок поставки — вторая половина порога закупки.

Ошибка здесь тихая ровно так же, как в запасе: число остаётся правдоподобным.
«Везут за день» вместо «за восемь» никто не оспорит, пока сырьё не кончится
между заказом и приходом.

Проверяется то, из-за чего расчёт врал бы, не подавая вида: подмена медианы
средним, ноль, выданный за отсутствие данных, и приёмка без заказа,
молча выпавшая из знаменателя.
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from core.models import Counterparty, Document, DocumentKind, SyncKind, SyncRun
from core.services import lead_time

pytestmark = pytest.mark.django_db


def moscow(year, month, day, hour=12):
    """Момент в московском поясе — том, в котором живёт учёт и человек."""
    return timezone.make_aware(datetime(year, month, day, hour))


@pytest.fixture
def run():
    return SyncRun.objects.create(kind=SyncKind.DOCUMENTS)


@pytest.fixture
def make_supplier(run):
    counter = {"n": 0}

    def _make(name="ООО «Лемун»"):
        counter["n"] += 1
        return Counterparty.objects.create(
            ms_id=f"60000000-0000-0000-0000-{counter['n']:012d}",
            name=name,
            last_seen_run=run,
        )

    return _make


@pytest.fixture
def supplier(make_supplier):
    return make_supplier()


@pytest.fixture
def make_pair(run, supplier):
    """Заказ и вызванная им приёмка, разнесённые на заданное число дней."""
    counter = {"n": 0}

    def _make(
        days,
        *,
        agent=None,
        order_deleted=False,
        order_applicable=True,
        linked=True,
    ):
        counter["n"] += 1
        agent = agent or supplier
        ordered_at = moscow(2026, 4, 1)
        order = Document.objects.create(
            ms_id=f"70000000-0000-0000-0000-{counter['n']:012d}",
            kind=DocumentKind.PURCHASE_ORDER,
            number=f"З-{counter['n']:05d}",
            moment=ordered_at,
            agent=agent,
            applicable=order_applicable,
            deleted_at=timezone.now() if order_deleted else None,
            last_seen_run=run,
        )
        return Document.objects.create(
            ms_id=f"80000000-0000-0000-0000-{counter['n']:012d}",
            kind=DocumentKind.SUPPLY,
            number=f"{counter['n']:05d}",
            # Сдвиг днями, а не подстановкой числа месяца: 1 апреля плюс
            # тридцать дней — это 1 мая, а не «31 апреля».
            moment=ordered_at + timedelta(days=days),
            agent=agent,
            purchase_order=order if linked else None,
            last_seen_run=run,
        )

    return _make


def supplies():
    """Приёмки вместе с заказами — так их отдаёт `selection.supplies`.

    Отбор здесь простой намеренно: что считается существующей приёмкой,
    проверяется там, где это решает production, — в `tests/suppliers/
    test_regularity.py::TestSelection`. Дублировать отбор в помощнике значит
    проверять сам помощник.
    """
    return list(
        Document.objects.filter(kind=DocumentKind.SUPPLY).select_related(
            "purchase_order"
        )
    )


class TestMedianNotAverage:
    def test_median_ignores_the_long_tail(self, make_pair):
        """Боевое распределение: почти всё одним днём, редкое — сорока.

        Среднее по всем 95 парам 4,77 дня против медианы 1,00 — впятеро.
        Возьми мы среднее, «везут за пять дней» описывало бы поставщика,
        который либо отдаёт сразу, либо тянет месяц.
        """
        for days in (0, 0, 0, 1, 40):
            make_pair(days)

        result = lead_time.of(supplies())

        assert result.days == Decimal("0")
        assert result.average_days == Decimal("8.2")

    def test_even_count_keeps_the_half_day(self, make_pair):
        """Четыре поставки по 0, 0, 7 и 8 дней — срок честно «то сразу,
        то через неделю», и половина дня здесь настоящая."""
        for days in (0, 0, 7, 8):
            make_pair(days)

        assert lead_time.of(supplies()).days == Decimal("3.5")

    def test_average_comes_along_for_the_explanation(self, make_pair):
        """Расхождение медианы со средним само говорит о непредсказуемости —
        значит показывается рядом, а не остаётся на сервере."""
        for days in (1, 1, 1, 30):
            make_pair(days)

        result = lead_time.of(supplies())

        assert result.days == Decimal("1")
        assert result.average_days == Decimal("8.2")
        assert (result.min_days, result.max_days) == (1, 30)


class TestZeroIsAnAnswer:
    def test_same_day_is_zero_not_missing(self, make_pair):
        """У 46 пар из 95 заказ и приёмка одним днём: у поставщика забирают,
        а не ждут доставку. Это факт учёта, и прочерк здесь был бы ложью."""
        for _ in range(3):
            make_pair(0)

        result = lead_time.of(supplies())

        assert result.days == Decimal("0")
        assert result.pairs == 3

    def test_no_pairs_gives_none(self, make_pair):
        """А вот когда связать нечего — именно прочерк. Ноль читался бы
        как «привозят в тот же день»."""
        make_pair(5, linked=False)

        result = lead_time.of(supplies())

        assert result.days is None
        assert result.pairs == 0
        assert result.unlinked == 1

    def test_empty_selection_says_nothing(self):
        assert lead_time.of([]) == lead_time.NOTHING


class TestUnlinkedAreCounted:
    def test_supply_without_order_does_not_vanish(self, make_pair):
        """Молчаливая потеря опаснее падения: приёмка без заказа обязана
        считаться, иначе «срок по 12 приёмкам» выдаётся за «по 14»."""
        make_pair(3)
        make_pair(5)
        make_pair(7, linked=False)

        result = lead_time.of(supplies())

        assert result.pairs == 2
        assert result.unlinked == 1

    def test_draft_order_is_unlinked(self, make_pair):
        """Черновик заказа ничего не заказывал: дата у него есть с момента
        создания, а обязательством он не стал. Считай мы от неё, срок вышел бы
        от намерения, которого не было, — при том что у приёмок черновики
        отсеиваются. В аккаунте такой заказ уже есть, один из 96."""
        make_pair(3)
        make_pair(20, order_applicable=False)

        result = lead_time.of(supplies())

        assert result.days == Decimal("3")
        assert result.pairs == 1
        assert result.unlinked == 1

    def test_deleted_order_is_unlinked(self, make_pair):
        """Заказ, исчезнувший из учёта, перестаёт быть датой, от которой
        считают. Приёмка при этом остаётся — товар пришёл."""
        make_pair(3)
        make_pair(9, order_deleted=True)

        result = lead_time.of(supplies())

        assert result.days == Decimal("3")
        assert result.pairs == 1
        assert result.unlinked == 1


class TestCalendarDays:
    def test_night_delivery_is_one_day(self, run, supplier):
        """Заказ в 23:00, приёмка в 09:00 следующего утра — «на следующий
        день», а не «десять часов». Закупку планируют днями."""
        order = Document.objects.create(
            ms_id="70000000-0000-0000-0000-0000000000ff",
            kind=DocumentKind.PURCHASE_ORDER,
            number="З-00099",
            moment=moscow(2026, 4, 1, hour=23),
            agent=supplier,
            last_seen_run=run,
        )
        Document.objects.create(
            ms_id="80000000-0000-0000-0000-0000000000ff",
            kind=DocumentKind.SUPPLY,
            number="00099",
            moment=moscow(2026, 4, 2, hour=9),
            agent=supplier,
            purchase_order=order,
            last_seen_run=run,
        )

        assert lead_time.of(supplies()).days == Decimal("1")
