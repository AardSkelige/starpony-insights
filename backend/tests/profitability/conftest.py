"""Фикстуры раздела «Прибыльность».

Лежат в своей папке по той же причине, что у соседей: имена `run`,
`make_product`, `make_demand` заняты локальными фикстурами других тестов,
и вынос наверх сделал бы неочевидным, чья версия сработала.

**Числа здесь нарочно некруглые.** Себестоимость приходит из отчёта дробной
у 150 позиций из 255, и фикстура с ценой «100 ₽» пропустила бы ровно тот
класс ошибок, ради которого деньги хранятся копейками.
"""

from datetime import date, datetime
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
    ProfitDay,
    SalesChannel,
    SyncKind,
    SyncRun,
    Uom,
)

DAY = date(2026, 7, 15)


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
def make_product(run, piece):
    """Товар. Артикул есть — это и отличает товар от услуги в этом разделе."""
    counter = {"n": 0}

    def _make(name="Репеллент 500 мл", article=None, folder="Готовая продукция/Репеллент",
              kind="product"):
        counter["n"] += 1
        return Product.objects.create(
            ms_id=f"10000000-0000-0000-0000-{counter['n']:012d}",
            name=name,
            article=f"300.{counter['n']:03d}.05" if article is None else article,
            code=f"3-{counter['n']:03d}",
            folder=folder,
            kind=kind,
            uom=piece,
            last_seen_run=run,
        )

    return _make


@pytest.fixture
def product(make_product):
    return make_product()


@pytest.fixture
def make_agent(run):
    counter = {"n": 0}

    def _make(name="Покупатель", *, tags=()):
        counter["n"] += 1
        return Counterparty.objects.create(
            ms_id=f"51000000-0000-0000-0000-{counter['n']:012d}",
            name=name,
            tags=list(tags),
            last_seen_run=run,
        )

    return _make


@pytest.fixture
def buyer(make_agent):
    return make_agent()


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
def make_contract(run, buyer):
    counter = {"n": 0}

    def _make(agent=None, contract_type=ContractType.COMMISSION):
        counter["n"] += 1
        return Contract.objects.create(
            ms_id=f"cccccccc-0000-0000-0000-{counter['n']:012d}",
            name=f"Д-{counter['n']}",
            contract_type=contract_type,
            agent=agent or buyer,
            last_seen_run=run,
        )

    return _make


@pytest.fixture
def make_profit_day(product):
    """Строка зеркала отчёта прибыльности."""
    def _make(
        *,
        day=DAY,
        product=product,
        quantity="10",
        revenue_kopecks=54_936,
        cost_kopecks=30_716,
        marketplace_quantity="0",
        marketplace_revenue_kopecks=0,
        marketplace_cost_kopecks=0,
    ):
        return ProfitDay.objects.create(
            date=day,
            product=product,
            quantity=Decimal(quantity),
            revenue_kopecks=revenue_kopecks,
            cost_kopecks=cost_kopecks,
            marketplace_quantity=Decimal(marketplace_quantity),
            marketplace_revenue_kopecks=marketplace_revenue_kopecks,
            marketplace_cost_kopecks=marketplace_cost_kopecks,
        )

    return _make


@pytest.fixture
def make_demand(run, buyer):
    """Отгрузка с позициями — источник «сколько ушло» и «сколько даром»."""
    counter = {"n": 0}

    def _make(*, moment=None, agent=None, contract=None, sales_channel=None,
              kind=DocumentKind.DEMAND, applicable=True, deleted=False):
        counter["n"] += 1
        return Document.objects.create(
            ms_id=f"41000000-0000-0000-0000-{counter['n']:012d}",
            kind=kind,
            number=f"{counter['n']:05d}",
            moment=moment or moscow(2026, 7, 15),
            agent=agent or buyer,
            contract=contract,
            sales_channel=sales_channel,
            total_kopecks=0,
            applicable=applicable,
            deleted_at=timezone.now() if deleted else None,
            last_seen_run=run,
        )

    return _make


def position(document, product, quantity, price_kopecks):
    """Строка документа. Сумма считается из цены и количества, как в учёте."""
    quantity = Decimal(str(quantity))
    price = Decimal(str(price_kopecks))
    row = DocumentPosition.objects.create(
        document=document,
        product=product,
        uom=product.uom,
        quantity=quantity,
        price_kopecks=price,
        total_kopecks=int(price * quantity),
    )
    document.total_kopecks = sum(p.total_kopecks for p in document.positions.all())
    document.save(update_fields=["total_kopecks"])
    return row
