"""Фикстуры отгрузок — общие для всех проверок раздела.

Лежат в своей папке, а не в общем `conftest.py`: имена `run`, `agent`,
`make_product` уже заняты локальными фикстурами соседних тестов, и вынос
наверх сделал бы неочевидным, чья версия сработала.
"""

from datetime import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from core.models import (
    Counterparty,
    Document,
    DocumentKind,
    DocumentPosition,
    Product,
    SalesChannel,
    SyncKind,
    SyncRun,
    Uom,
)


def moscow(year, month, day, hour=12, minute=0, second=0, microsecond=0):
    """Момент в московском поясе — том, в котором живёт учёт и человек."""
    return timezone.make_aware(
        datetime(year, month, day, hour, minute, second, microsecond)
    )


def position(document, product, quantity, total_kopecks, price_kopecks=0):
    return DocumentPosition.objects.create(
        document=document,
        product=product,
        quantity=Decimal(quantity),
        total_kopecks=total_kopecks,
        price_kopecks=Decimal(price_kopecks),
    )


@pytest.fixture
def run():
    return SyncRun.objects.create(kind=SyncKind.DOCUMENTS)


@pytest.fixture
def uom(run):
    return Uom.objects.create(
        ms_id="00000000-0000-0000-0000-0000000000ff", name="шт", last_seen_run=run
    )


@pytest.fixture
def agent(run):
    return Counterparty.objects.create(
        ms_id="00000000-0000-0000-0000-0000000000aa", name="Покупатель", last_seen_run=run
    )


@pytest.fixture
def make_agent(run):
    """Разные покупатели — нужны там, где важно «кому», а не «сколько»."""
    counter = {"n": 0}

    def _make(name):
        counter["n"] += 1
        return Counterparty.objects.create(
            ms_id=f"30000000-0000-0000-0000-{counter['n']:012d}",
            name=name,
            last_seen_run=run,
        )

    return _make


@pytest.fixture
def channel(run):
    return SalesChannel.objects.create(
        ms_id="00000000-0000-0000-0000-0000000000cc", name="Озон", last_seen_run=run
    )


@pytest.fixture
def make_channel(run):
    counter = {"n": 0}

    def _make(name):
        counter["n"] += 1
        return SalesChannel.objects.create(
            ms_id=f"20000000-0000-0000-0000-{counter['n']:012d}",
            name=name,
            last_seen_run=run,
        )

    return _make


@pytest.fixture
def make_product(run, uom):
    counter = {"n": 0}

    def _make(name="Шампунь", article="100.001", code="2-001"):
        counter["n"] += 1
        return Product.objects.create(
            ms_id=f"00000000-0000-0000-0000-{counter['n']:012d}",
            name=name,
            article=article,
            code=code,
            uom=uom,
            last_seen_run=run,
        )

    return _make


@pytest.fixture
def make_demand(run, agent):
    counter = {"n": 0}

    def _make(moment=None, channel=None, deleted=False, kind=DocumentKind.DEMAND,
              applicable=True, buyer=None):
        counter["n"] += 1
        return Document.objects.create(
            ms_id=f"10000000-0000-0000-0000-{counter['n']:012d}",
            kind=kind,
            number=f"{counter['n']:05d}",
            moment=moment or moscow(2026, 6, 15),
            agent=buyer or agent,
            sales_channel=channel,
            applicable=applicable,
            deleted_at=timezone.now() if deleted else None,
            last_seen_run=run,
        )

    return _make


@pytest.fixture
def make_plan(run):
    """Техкарта с составом. Объём выпуска по умолчанию единица."""
    from core.models import ProcessingPlan, ProcessingPlanMaterial

    counter = {"n": 0}

    def _make(name, product, output=1, materials=()):
        counter["n"] += 1
        plan = ProcessingPlan.objects.create(
            ms_id=f"30000000-0000-0000-0000-{counter['n']:012d}",
            name=name,
            product=product,
            output_quantity=Decimal(str(output)),
            last_seen_run=run,
        )
        for material, quantity in materials:
            ProcessingPlanMaterial.objects.create(
                plan=plan, product=material, quantity=Decimal(str(quantity))
            )
        return plan

    return _make


@pytest.fixture
def make_supply(run, agent):
    """Приёмка с одной позицией — источник цены закупки."""
    counter = {"n": 500}

    def _make(product, price_kopecks, quantity=1, moment=None, supplier=None):
        counter["n"] += 1
        document = Document.objects.create(
            ms_id=f"40000000-0000-0000-0000-{counter['n']:012d}",
            kind=DocumentKind.SUPPLY,
            number=f"{counter['n']:05d}",
            moment=moment or moscow(2026, 5, 1),
            agent=supplier or agent,
            last_seen_run=run,
        )
        DocumentPosition.objects.create(
            document=document,
            product=product,
            quantity=Decimal(str(quantity)),
            price_kopecks=Decimal(str(price_kopecks)),
            total_kopecks=int(Decimal(str(price_kopecks)) * Decimal(str(quantity))),
        )
        return document

    return _make


@pytest.fixture
def make_stock():
    """Остаток на складе. Свободный считается моделью: количество минус резерв."""
    from core.models import Stock

    def _make(product, quantity, reserved="0"):
        return Stock.objects.create(
            product=product,
            quantity=Decimal(str(quantity)),
            reserved=Decimal(str(reserved)),
        )

    return _make


@pytest.fixture
def make_counterparty(run):
    counter = {"n": 0}

    def _make(name):
        counter["n"] += 1
        return Counterparty.objects.create(
            ms_id=f"50000000-0000-0000-0000-{counter['n']:012d}",
            name=name,
            last_seen_run=run,
        )

    return _make
