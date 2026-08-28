"""Цена последней закупки — общая для «Материалов», «Приёмок» и «Поставщиков».

По этой цене считают стоимость израсходованного сырья. Ошибка здесь не падает,
а выражается в неверной сумме — и заметят её при сверке с поставщиком,
а не на экране.
"""

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
)
from core.services.purchase_prices import last_purchase_prices

pytestmark = pytest.mark.django_db


@pytest.fixture
def run():
    return SyncRun.objects.create(kind=SyncKind.DOCUMENTS)


@pytest.fixture
def supplier(run):
    return Counterparty.objects.create(
        ms_id="70000000-0000-0000-0000-000000000001",
        name="ООО Химснаб",
        last_seen_run=run,
    )


@pytest.fixture
def water(run):
    return Product.objects.create(
        ms_id="70000000-0000-0000-0000-000000000002",
        name="Вода дистиллированная",
        last_seen_run=run,
    )


@pytest.fixture
def buy(run, supplier):
    counter = {"n": 0}

    def _make(product, price, day, kind=DocumentKind.SUPPLY, deleted=False,
              applicable=True, agent=None, quantity="1"):
        counter["n"] += 1
        document = Document.objects.create(
            ms_id=f"70000000-0000-0000-0000-1{counter['n']:011d}",
            kind=kind,
            number=f"{counter['n']:05d}",
            moment=timezone.make_aware(timezone.datetime(2026, 1, day)),
            agent=agent or supplier,
            applicable=applicable,
            deleted_at=timezone.now() if deleted else None,
            last_seen_run=run,
        )
        DocumentPosition.objects.create(
            document=document,
            product=product,
            quantity=Decimal(quantity),
            price_kopecks=Decimal(price),
            total_kopecks=0,
        )
        return document

    return _make


def test_latest_wins(water, buy):
    """Цены сырья меняются — берётся та, по которой заплатили в последний раз."""
    buy(water, "200", day=5)
    buy(water, "300", day=20)
    buy(water, "250", day=12)

    assert last_purchase_prices([water.pk])[water.pk].price_kopecks == Decimal("300")


def test_zero_price_is_not_a_price(water, buy):
    """Нулевая позиция — образец или бонус, а не новая цена.

    В боевых данных таких 97 из 402. Взять нуль за последнюю цену значит
    обнулить стоимость материала целиком, и число исчезнет с экрана
    без единого признака, что оно потеряно.
    """
    buy(water, "300", day=5)
    buy(water, "0", day=20)

    assert last_purchase_prices([water.pk])[water.pk].price_kopecks == Decimal("300")


def test_deleted_document_is_ignored(water, buy):
    buy(water, "300", day=5)
    buy(water, "999", day=20, deleted=True)

    assert last_purchase_prices([water.pk])[water.pk].price_kopecks == Decimal("300")


def test_draft_document_is_ignored(water, buy):
    """Черновик приёмки лежит в той же таблице, но товар по нему не пришёл."""
    buy(water, "300", day=5)
    buy(water, "999", day=20, applicable=False)

    assert last_purchase_prices([water.pk])[water.pk].price_kopecks == Decimal("300")


def test_shipment_is_not_a_purchase(water, buy):
    """Отгрузка — это продажа, её цена к закупке отношения не имеет."""
    buy(water, "300", day=5)
    buy(water, "999", day=20, kind=DocumentKind.DEMAND)

    assert last_purchase_prices([water.pk])[water.pk].price_kopecks == Decimal("300")


def test_never_purchased_is_absent(water):
    """Отсутствие в ответе, а не нулевая цена: их нельзя путать."""
    assert last_purchase_prices([water.pk]) == {}


def test_carries_document_and_supplier(water, buy, run):
    """Цена называет свой источник: документ, дату и поставщика."""
    other = Counterparty.objects.create(
        ms_id="70000000-0000-0000-0000-000000000003", name="ИП Петров", last_seen_run=run
    )
    buy(water, "200", day=5)
    document = buy(water, "300", day=20, agent=other)

    price = last_purchase_prices([water.pk])[water.pk]
    assert price.document_number == document.number
    assert price.supplier == "ИП Петров"
    # Через localtime: учёт ведётся в Москве, а в UTC 20 января превращается
    # в 19-е — ровно та ошибка на три часа, о которой предупреждает разбор
    # ответов МойСклада.
    assert timezone.localtime(price.moment).day == 20


def test_same_moment_resolves_deterministically(water, buy):
    """Две приёмки одним моментом не оставляют выбор на усмотрение базы."""
    first = buy(water, "200", day=10)
    second = buy(water, "300", day=10)
    assert first.moment == second.moment

    chosen = {last_purchase_prices([water.pk])[water.pk].price_kopecks for _ in range(5)}
    assert len(chosen) == 1, "выбор цены неустойчив между запросами"


def test_one_query_for_many_products(water, buy, run, django_assert_num_queries):
    """Цены на все материалы берутся одним запросом, а не по одному на строку."""
    others = [
        Product.objects.create(
            ms_id=f"70000000-0000-0000-0000-2{index:011d}",
            name=f"Сырьё {index}",
            last_seen_run=run,
        )
        for index in range(10)
    ]
    for index, product in enumerate([water, *others]):
        buy(product, str(100 + index), day=5)

    with django_assert_num_queries(1):
        prices = last_purchase_prices([product.pk for product in [water, *others]])

    assert len(prices) == 11
