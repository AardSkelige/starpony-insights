"""Фикстуры «Расчёта производства».

Свой набор, а не общий с приёмками: там строка — позиция документа, здесь
строка — сам товар, и нужны техкарты, остатки и неснижаемые остатки, которых
у соседей нет вовсе.

**Числа взяты с боевых, а не круглые.** Экстракт зелёного чая с минимумом
500 при остатке 1048 — та самая пара, на которой ловится «хватает, но станет
ниже минимума»: с круглыми числами этот случай не отличить от «не хватает».
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
    ProcessingPlan,
    ProcessingPlanMaterial,
    Product,
    ProductKind,
    Stock,
    SyncKind,
    SyncRun,
    Uom,
)


def moscow(year, month, day, hour=12, minute=0):
    """Момент в московском поясе — том, в котором живёт учёт и человек."""
    return timezone.make_aware(datetime(year, month, day, hour, minute))


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
def make_product(run, gram):
    counter = {"n": 0}

    def _make(
        name="Материал",
        article="",
        code="",
        uom=None,
        archived=False,
        min_balance=None,
        folder="",
        kind=ProductKind.PRODUCT,
    ):
        counter["n"] += 1
        return Product.objects.create(
            ms_id=f"00000000-0000-0000-0000-{counter['n']:012d}",
            kind=kind,
            name=name,
            article=article,
            code=code,
            folder=folder,
            uom=uom or gram,
            archived=archived,
            min_balance=(
                Decimal(str(min_balance)) if min_balance is not None else None
            ),
            last_seen_run=run,
        )

    return _make


@pytest.fixture
def make_plan(run):
    """Техкарта с составом. `output` — сколько получается за прогон.

    Объём выпуска не единица по умолчанию намеренно: расход на единицу
    считается делением на него, и техкарта «100 штук из 5 кг» — обычный
    вид боевой карты. Забудь мы про деление, расход вышел бы в сто раз
    больше, и на объёме 1 это осталось бы незамеченным.
    """
    counter = {"n": 0}

    def _make(product, materials, output=1, archived=False, name=None):
        counter["n"] += 1
        plan = ProcessingPlan.objects.create(
            ms_id=f"70000000-0000-0000-0000-{counter['n']:012d}",
            name=name or f"Техкарта {counter['n']}",
            product=product,
            output_quantity=Decimal(str(output)),
            archived=archived,
            last_seen_run=run,
        )
        for material, quantity in materials:
            ProcessingPlanMaterial.objects.create(
                plan=plan,
                product=material,
                uom=material.uom,
                quantity=Decimal(str(quantity)),
            )
        return plan

    return _make


@pytest.fixture
def make_stock():
    def _make(product, quantity, reserved=0):
        return Stock.objects.create(
            product=product,
            quantity=Decimal(str(quantity)),
            reserved=Decimal(str(reserved)),
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
def supplier(run):
    return Counterparty.objects.create(
        ms_id="50000000-0000-0000-0000-000000000002",
        name="ООО «Химпитерторг»",
        last_seen_run=run,
    )


@pytest.fixture
def make_document(run, buyer):
    counter = {"n": 0}

    def _make(
        kind=DocumentKind.DEMAND,
        moment=None,
        agent=None,
        applicable=True,
        deleted=False,
        purchase_order=None,
    ):
        counter["n"] += 1
        return Document.objects.create(
            ms_id=f"40000000-0000-0000-0000-{counter['n']:012d}",
            kind=kind,
            number=f"{counter['n']:05d}",
            moment=moment or moscow(2026, 5, 1),
            agent=agent or buyer,
            applicable=applicable,
            deleted_at=timezone.now() if deleted else None,
            purchase_order=purchase_order,
            last_seen_run=run,
        )

    return _make


def position(document, product, quantity, price_kopecks=0):
    """Строка документа. Сумма считается из цены и количества, как в учёте."""
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


@pytest.fixture
def sell(make_document):
    """Продать товар в указанный день — отгрузкой, как в учёте."""

    def _sell(product, quantity, day=1, month=5, **kwargs):
        return position(
            make_document(moment=moscow(2026, month, day), **kwargs),
            product,
            quantity,
        )

    return _sell


@pytest.fixture
def shampoo(make_product, make_plan, make_stock, piece, gram):
    """Товар с техкартой, остатком и сырьём — основа большинства проверок.

    Один шампунь из воды и отдушки, объём выпуска 10 штук: так проверяется,
    что расход делится на объём, а не берётся из карты как есть.
    """
    water = make_product("Вода дистиллированная", code="1-001")
    scent = make_product("Отдушка «Лесные ягоды»", code="1-002", min_balance=70)
    bottle = make_product(
        "Шампунь для лошадей 500 мл",
        article="100.011.05",
        code="2-001",
        uom=piece,
        folder="Готовая продукция/Шампунь для лошадей",
    )
    make_plan(bottle, [(water, 4000), (scent, 40)], output=10)

    make_stock(water, 30000)
    make_stock(scent, 2.4)
    make_stock(bottle, 3)
    return bottle
