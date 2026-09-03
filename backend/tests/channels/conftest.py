"""Фикстуры раздела каналов продаж.

Лежат в своей папке по той же причине, что у поставщиков: имена `make_demand`
и `make_product` заняты локальными фикстурами соседних тестов, и вынос наверх
сделал бы неочевидным, чья версия сработала.

**Отгрузка здесь создаётся с каналом, но канал можно снять.** В боевых данных
канал заполнен у 305 отгрузок из 306, и обе стороны обязаны проверяться:
отгрузка без канала не становится строкой таблицы, но обязана попасть
в сводку — иначе итог страницы молча разойдётся с учётом.
"""

from datetime import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from core.models import (
    Contract,
    ContractType,
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


def moscow(year, month, day, hour=12):
    """Момент в московском поясе — том, в котором живёт учёт и человек."""
    return timezone.make_aware(datetime(year, month, day, hour))


@pytest.fixture
def run():
    return SyncRun.objects.create(kind=SyncKind.DOCUMENTS)


@pytest.fixture
def piece(run):
    return Uom.objects.create(
        ms_id="00000000-0000-0000-0000-0000000000f2", name="шт", last_seen_run=run
    )


@pytest.fixture
def make_channel(run):
    counter = {"n": 0}

    def _make(name="Озон"):
        counter["n"] += 1
        return SalesChannel.objects.create(
            ms_id=f"90000000-0000-0000-0000-{counter['n']:012d}",
            name=name,
            last_seen_run=run,
        )

    return _make


@pytest.fixture
def channel(make_channel):
    return make_channel()


@pytest.fixture
def make_buyer(run):
    counter = {"n": 0}

    def _make(name="Ложис Софья"):
        counter["n"] += 1
        return Counterparty.objects.create(
            ms_id=f"51000000-0000-0000-0000-{counter['n']:012d}",
            name=name,
            last_seen_run=run,
        )

    return _make


@pytest.fixture
def buyer(make_buyer):
    return make_buyer()


@pytest.fixture
def make_contract(run, buyer):
    """Договор с контрагентом. По умолчанию комиссия — ради неё он и заведён."""
    counter = {"n": 0}

    def _make(agent=None, contract_type=ContractType.COMMISSION):
        counter["n"] += 1
        return Contract.objects.create(
            ms_id=f"61000000-0000-0000-0000-{counter['n']:012d}",
            name=f"{counter['n']:05d}",
            contract_type=contract_type,
            agent=agent or buyer,
            last_seen_run=run,
        )

    return _make


@pytest.fixture
def make_product(run, piece):
    counter = {"n": 0}

    def _make(name="Репеллент 500 мл", article="2.001", code="2-001"):
        counter["n"] += 1
        return Product.objects.create(
            ms_id=f"10000000-0000-0000-0000-{counter['n']:012d}",
            name=name,
            article=article,
            code=code,
            uom=piece,
            last_seen_run=run,
        )

    return _make


@pytest.fixture
def make_demand(run, channel, buyer):
    """Отгрузка. `sales_channel=None` — отгрузка без канала, такая в учёте есть."""
    counter = {"n": 0}

    def _make(
        moment=None,
        *,
        sales_channel=-1,
        agent=None,
        total_kopecks=100_000,
        contract=None,
        deleted=False,
        applicable=True,
    ):
        counter["n"] += 1
        return Document.objects.create(
            ms_id=f"41000000-0000-0000-0000-{counter['n']:012d}",
            kind=DocumentKind.DEMAND,
            number=f"{counter['n']:05d}",
            moment=moment or moscow(2026, 5, 1),
            agent=agent or buyer,
            sales_channel=channel if sales_channel == -1 else sales_channel,
            contract=contract,
            total_kopecks=total_kopecks,
            applicable=applicable,
            deleted_at=timezone.now() if deleted else None,
            last_seen_run=run,
        )

    return _make


def position(document, product, quantity, price_kopecks):
    """Строка отгрузки. Сумма считается из цены и количества, как в учёте."""
    quantity = Decimal(str(quantity))
    price = Decimal(str(price_kopecks))
    return DocumentPosition.objects.create(
        document=document,
        product=product,
        uom=product.uom,
        quantity=quantity,
        price_kopecks=price,
        total_kopecks=int(price * quantity),
    )
