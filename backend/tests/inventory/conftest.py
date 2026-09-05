"""Фикстуры раздела «Инвентаризация».

Лежат в своей папке по той же причине, что у соседей: имена `run`, `product`
заняты локальными фикстурами других проверок, и вынос наверх сделал бы
неочевидным, чья версия сработала.

**У товара здесь всегда есть остаток.** Деньги страницы считаются по
себестоимости из остатков, и фикстура без него описывала бы учёт, которого
нет: расхождение не оценивалось бы ни в одной проверке.
"""

from datetime import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from core.models import (
    Inventory,
    InventoryPosition,
    Product,
    ProductKind,
    Stock,
    SyncKind,
    SyncRun,
)


def moscow(year, month, day, hour=12):
    """Момент в московском поясе — том, в котором живёт учёт и человек."""
    return timezone.make_aware(datetime(year, month, day, hour))


@pytest.fixture
def run():
    return SyncRun.objects.create(kind=SyncKind.DOCUMENTS)


@pytest.fixture
def make_product(run):
    counter = {"n": 0}

    def _make(name="Товар", *, folder="Готовая продукция", cost="100.00",
              article="", kind=ProductKind.PRODUCT, archived=False):
        counter["n"] += 1
        product = Product.objects.create(
            ms_id=f"00000000-0000-0000-0000-{counter['n']:012d}",
            name=name,
            article=article,
            folder=folder,
            kind=kind,
            archived=archived,
            last_seen_run=run,
        )
        if cost is not None:
            Stock.objects.create(
                product=product,
                quantity=Decimal("10.000"),
                cost_kopecks=Decimal(cost),
            )
        return product

    return _make


@pytest.fixture
def make_inventory(run):
    counter = {"n": 0}

    def _make(moment, *, store="Хоз товары", number=""):
        counter["n"] += 1
        return Inventory.objects.create(
            ms_id=f"11111111-0000-0000-0000-{counter['n']:012d}",
            number=number or f"0000{counter['n']}",
            moment=moment,
            store_name=store,
            last_seen_run=run,
        )

    return _make


@pytest.fixture
def count_position():
    def _make(inventory, product, *, calculated="10.000", counted="8.000",
              correction=None):
        calculated = Decimal(calculated)
        counted = Decimal(counted)
        return InventoryPosition.objects.create(
            inventory=inventory,
            product=product,
            calculated=calculated,
            counted=counted,
            correction_amount=Decimal(correction) if correction is not None
            else counted - calculated,
        )

    return _make
