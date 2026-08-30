"""Фикстуры раздела поставщиков — общие для всех проверок.

Лежат в своей папке по той же причине, что у приёмок: имена `run`,
`make_supply`, `supplier` заняты локальными фикстурами соседних тестов,
и вынос наверх сделал бы неочевидным, чья версия сработала.

**Приёмка здесь создаётся вместе с вызвавшим её заказом.** В боевых данных
связь заполнена у всех 95 приёмок, и фикстура без заказа описывала бы учёт,
которого нет: срок поставки не считался бы ни в одной проверке.
"""

from datetime import datetime, timedelta
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


def moscow(year, month, day, hour=12):
    """Момент в московском поясе — том, в котором живёт учёт и человек."""
    return timezone.make_aware(datetime(year, month, day, hour))


@pytest.fixture
def run():
    return SyncRun.objects.create(kind=SyncKind.DOCUMENTS)


@pytest.fixture
def gram(run):
    return Uom.objects.create(
        ms_id="00000000-0000-0000-0000-0000000000f1", name="г", last_seen_run=run
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

    def _make(name="Отдушка", article="1.001", code="1-001"):
        counter["n"] += 1
        return Product.objects.create(
            ms_id=f"00000000-0000-0000-0000-{counter['n']:012d}",
            name=name,
            article=article,
            code=code,
            uom=gram,
            last_seen_run=run,
        )

    return _make


@pytest.fixture
def make_supply(run, supplier):
    """Приёмка вместе с заказом, который её вызвал.

    `lead_days` — сколько прошло от заказа до прихода; `ordered=False` снимает
    заказ вовсе, чтобы проверить приёмку, у которой срок не считается.
    """
    counter = {"n": 0}

    def _make(
        moment=None,
        agent=None,
        *,
        total_kopecks=100_000,
        lead_days=0,
        ordered=True,
        deleted=False,
        applicable=True,
    ):
        counter["n"] += 1
        agent = agent or supplier
        moment = moment or moscow(2026, 5, 1)

        order = None
        if ordered:
            order = Document.objects.create(
                ms_id=f"70000000-0000-0000-0000-{counter['n']:012d}",
                kind=DocumentKind.PURCHASE_ORDER,
                number=f"З-{counter['n']:05d}",
                moment=moment - timedelta(days=lead_days),
                agent=agent,
                last_seen_run=run,
            )

        return Document.objects.create(
            ms_id=f"40000000-0000-0000-0000-{counter['n']:012d}",
            kind=DocumentKind.SUPPLY,
            number=f"{counter['n']:05d}",
            moment=moment,
            agent=agent,
            purchase_order=order,
            total_kopecks=total_kopecks,
            applicable=applicable,
            deleted_at=timezone.now() if deleted else None,
            last_seen_run=run,
        )

    return _make


def position(document, product, quantity, price_kopecks):
    """Строка приёмки. Сумма считается из цены и количества, как в учёте."""
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
