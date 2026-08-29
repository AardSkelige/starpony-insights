"""Фикстуры приёмок — общие для всех проверок раздела.

Лежат в своей папке, а не в общем `conftest.py`: имена `run`, `make_product`,
`supply` уже заняты локальными фикстурами соседних тестов, и вынос наверх
сделал бы неочевидным, чья версия сработала.
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
    SyncKind,
    SyncRun,
    Uom,
)


def moscow(year, month, day, hour=12, minute=0, second=0, microsecond=0):
    """Момент в московском поясе — том, в котором живёт учёт и человек."""
    return timezone.make_aware(
        datetime(year, month, day, hour, minute, second, microsecond)
    )


@pytest.fixture
def run():
    return SyncRun.objects.create(kind=SyncKind.DOCUMENTS)


@pytest.fixture
def gram(run):
    return Uom.objects.create(
        ms_id="00000000-0000-0000-0000-0000000000f1", name="г", last_seen_run=run
    )


@pytest.fixture
def piece(run):
    return Uom.objects.create(
        ms_id="00000000-0000-0000-0000-0000000000f2", name="шт", last_seen_run=run
    )


@pytest.fixture
def make_supplier(run):
    counter = {"n": 0}

    def _make(name="ООО «Лемун»"):
        counter["n"] += 1
        return Counterparty.objects.create(
            ms_id=f"50000000-0000-0000-0000-{counter['n']:012d}",
            name=name,
            last_seen_run=run,
        )

    return _make


@pytest.fixture
def supplier(make_supplier):
    return make_supplier()


@pytest.fixture
def make_product(run, gram):
    counter = {"n": 0}

    def _make(name="Отдушка", article="1.001", code="1-001", uom=None):
        counter["n"] += 1
        return Product.objects.create(
            ms_id=f"00000000-0000-0000-0000-{counter['n']:012d}",
            name=name,
            article=article,
            code=code,
            uom=uom or gram,
            last_seen_run=run,
        )

    return _make


@pytest.fixture
def make_supply(run, supplier):
    """Приёмка без позиций: их добавляет `position`.

    Отдельно от позиций намеренно — половина проверок раздела про то,
    что происходит, когда один материал приходит одним документом дважды.
    """
    counter = {"n": 0}

    def _make(moment=None, agent=None, deleted=False, kind=DocumentKind.SUPPLY,
              applicable=True):
        counter["n"] += 1
        return Document.objects.create(
            ms_id=f"40000000-0000-0000-0000-{counter['n']:012d}",
            kind=kind,
            number=f"{counter['n']:05d}",
            moment=moment or moscow(2026, 5, 1),
            agent=agent or supplier,
            applicable=applicable,
            deleted_at=timezone.now() if deleted else None,
            last_seen_run=run,
        )

    return _make


def position(document, product, quantity, price_kopecks, uom=None):
    """Строка приёмки. Сумма считается из цены и количества, как в учёте."""
    quantity = Decimal(str(quantity))
    price = Decimal(str(price_kopecks))
    return DocumentPosition.objects.create(
        document=document,
        product=product,
        uom=uom or product.uom,
        quantity=quantity,
        price_kopecks=price,
        total_kopecks=int(price * quantity),
    )


@pytest.fixture
def bought(make_supply, make_product):
    """Материал с историей: три закупки по растущей цене у одного поставщика.

    Числа взяты с боевых: флакон 28/410 подорожал с 25,05 до 31,05 ₽
    за три приёмки — на нём ловится и средняя, и динамика к предыдущей.
    """
    bottle = make_product("Флакон 500 мл", article="2.001", code="2-001")
    for day, price in ((19, "2505"), (20, "2675.9"), (21, "3105")):
        position(make_supply(moment=moscow(2026, 4, day)), bottle, 1000, price)
    return bottle
