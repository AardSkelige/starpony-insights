"""Фикстуры главной.

Свой набор, а не общий: имена `run`, `make_product`, `make_document` заняты
локальными фикстурами четырёх других папок, и вынос наверх сделал бы
неочевидным, чья версия сработала.

**Даты считаются от последнего полного месяца, а не задаются числами.**
Окно главной само едет по календарю: тест с зашитым августом краснеет
первого сентября, его правят «чтобы проходил» — и он перестаёт проверять
что-либо. Здесь месяц берётся у того же `period.window`, который считает
страницу, поэтому тест верен в любой день года.
"""

from datetime import datetime, time
from decimal import Decimal

import pytest
from django.utils import timezone

from api.home.services import period
from core.models import (
    Counterparty,
    Document,
    DocumentKind,
    DocumentPosition,
    ProcessingPlan,
    ProcessingPlanMaterial,
    Product,
    ProductKind,
    ProfitDay,
    SalesChannel,
    Stock,
    SyncKind,
    SyncRun,
    SyncStatus,
    Uom,
)


@pytest.fixture
def window():
    """Окно страницы на сегодня: последний полный месяц и предыдущий."""
    return period.window()


def at(day, hour=12):
    """Полдень указанного дня в московском поясе.

    Полдень намеренно: он одинаково далёк от обеих границ суток, и тест
    не начинает зависеть от часа своего запуска. Ровно та ошибка, которую
    ловит `core/dates.py`, — граничные моменты проверяются отдельно.
    """
    return timezone.make_aware(datetime.combine(day, time(hour=hour)))


@pytest.fixture
def run():
    return SyncRun.objects.create(kind=SyncKind.DOCUMENTS)


@pytest.fixture
def synced(run):
    """Успешные прогоны обоих видов: без них главная отвечает «данных нет»."""
    now = timezone.now()
    for kind in (SyncKind.STATE, SyncKind.DOCUMENTS):
        SyncRun.objects.create(
            kind=kind, status=SyncStatus.SUCCESS, started_at=now, finished_at=now
        )


@pytest.fixture
def piece(run):
    return Uom.objects.create(
        ms_id="00000000-0000-0000-0000-0000000000f2", name="шт", last_seen_run=run
    )


@pytest.fixture
def make_product(run, piece):
    counter = {"n": 0}

    def _make(name="Товар", article="", kind=ProductKind.PRODUCT, archived=False):
        counter["n"] += 1
        return Product.objects.create(
            ms_id=f"00000000-0000-0000-0000-{counter['n']:012d}",
            kind=kind,
            name=name,
            article=article,
            uom=piece,
            archived=archived,
            last_seen_run=run,
        )

    return _make


@pytest.fixture
def make_stock():
    def _make(product, quantity=0, reserved=0, sale_price=0, cost=0):
        return Stock.objects.create(
            product=product,
            quantity=Decimal(str(quantity)),
            reserved=Decimal(str(reserved)),
            sale_price_kopecks=Decimal(str(sale_price)),
            cost_kopecks=Decimal(str(cost)),
        )

    return _make


@pytest.fixture
def buyer(run):
    return Counterparty.objects.create(
        ms_id="50000000-0000-0000-0000-000000000001",
        name="ООО «Конный клуб»",
        last_seen_run=run,
    )


@pytest.fixture
def make_channel(run):
    counter = {"n": 0}

    def _make(name):
        counter["n"] += 1
        return SalesChannel.objects.create(
            ms_id=f"60000000-0000-0000-0000-{counter['n']:012d}",
            name=name,
            last_seen_run=run,
        )

    return _make


@pytest.fixture
def make_shipment(run, buyer):
    """Отгрузка с позициями. Сумма документа складывается из строк."""
    counter = {"n": 0}

    def _make(day, items, channel=None):
        counter["n"] += 1
        document = Document.objects.create(
            ms_id=f"40000000-0000-0000-0000-{counter['n']:012d}",
            kind=DocumentKind.DEMAND,
            number=f"{counter['n']:05d}",
            moment=at(day),
            agent=buyer,
            sales_channel=channel,
            last_seen_run=run,
        )
        total = 0
        for product, quantity, price in items:
            quantity = Decimal(str(quantity))
            line = int(quantity * Decimal(str(price)))
            total += line
            DocumentPosition.objects.create(
                document=document,
                product=product,
                uom=product.uom,
                quantity=quantity,
                price_kopecks=Decimal(str(price)),
                total_kopecks=line,
            )
        document.total_kopecks = total
        document.save(update_fields=["total_kopecks"])
        return document

    return _make


@pytest.fixture
def make_sale():
    """Строка отчёта прибыльности: продано, выручка, себестоимость."""

    def _make(product, day, quantity=1, revenue=0, cost=0):
        return ProfitDay.objects.create(
            product=product,
            date=day,
            quantity=Decimal(str(quantity)),
            revenue_kopecks=revenue,
            cost_kopecks=cost,
        )

    return _make


@pytest.fixture
def make_plan(run):
    """Техкарта: из чего и сколько получается за прогон."""
    counter = {"n": 0}

    def _make(product, materials, output=1):
        counter["n"] += 1
        plan = ProcessingPlan.objects.create(
            ms_id=f"70000000-0000-0000-0000-{counter['n']:012d}",
            name=f"Техкарта {counter['n']}",
            product=product,
            output_quantity=Decimal(str(output)),
            last_seen_run=run,
        )
        for material, quantity in materials:
            ProcessingPlanMaterial.objects.create(
                plan=plan, product=material, uom=material.uom,
                quantity=Decimal(str(quantity)),
            )
        return plan

    return _make
