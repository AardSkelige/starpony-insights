"""Остатки по складам — знаменатель для «сколько склада пересчитано».

Проверяется то, что ломается тихо: пустая таблица после сбоя (склад
покажется пересчитанным на сто процентов), позиция, увезённая на другой
склад и оставшаяся на первом, и нулевые остатки, попавшие в знаменатель.
"""

from decimal import Decimal

import pytest

from core.models import Product, StoreStock, SyncKind, SyncRun
from moysklad.sync.store_stock import sync_store_stock

pytestmark = pytest.mark.django_db

BASE = "https://api.moysklad.ru/api/remap/1.2"
PRODUCT_ID = "22222222-2222-2222-2222-222222222222"


class FakeClient:
    request_count = 0

    def __init__(self, rows):
        self._rows = rows
        self.calls = []

    def iterate(self, path, params=None):
        self.calls.append((path, params))
        yield from self._rows.get(path, [])


def report_row(*, product_id=PRODUCT_ID, stores=(("Производство", 5.0),)):
    return {
        "meta": {"href": f"{BASE}/entity/product/{product_id}", "type": "product"},
        "stockByStore": [
            {"name": name, "stock": stock, "reserve": 0.0, "inTransit": 0.0}
            for name, stock in stores
        ],
    }


@pytest.fixture
def run():
    return SyncRun.objects.create(kind=SyncKind.DOCUMENTS)


@pytest.fixture
def product(run):
    return Product.objects.create(ms_id=PRODUCT_ID, name="Отдушка", last_seen_run=run)


def test_stock_is_saved_per_store(run, product):
    client = FakeClient(
        {"/report/stock/bystore": [report_row(stores=(("Производство", 5.0), ("Хоз товары", 2.0)))]}
    )

    outcome = sync_store_stock(client, run)

    assert outcome.created == 2
    assert set(StoreStock.objects.values_list("store_name", flat=True)) == {
        "Производство", "Хоз товары"
    }


def test_zero_stock_is_not_a_place_where_it_lies(run, product):
    """Ноль на складе — не «лежит здесь».

    Попади он в знаменатель, склад требовал бы пересчёта того, чего на нём
    нет, и доля пересчитанного была бы занижена навсегда.
    """
    client = FakeClient(
        {"/report/stock/bystore": [report_row(stores=(("Производство", 0.0), ("Хоз товары", 2.0)))]}
    )

    sync_store_stock(client, run)

    assert list(StoreStock.objects.values_list("store_name", flat=True)) == ["Хоз товары"]


def test_moved_product_leaves_the_old_store(run, product):
    """Позиция, увезённая на другой склад, обязана исчезнуть с первого."""
    StoreStock.objects.create(
        product=product, store_name="Производство", quantity=Decimal("5.000")
    )
    client = FakeClient({"/report/stock/bystore": [report_row(stores=(("Хоз товары", 5.0),))]})

    sync_store_stock(client, SyncRun.objects.create(kind=SyncKind.DOCUMENTS))

    assert list(StoreStock.objects.values_list("store_name", flat=True)) == ["Хоз товары"]


def test_unknown_product_is_skipped_and_counted(run, product):
    """Отчёт отдаёт и модификации с комплектами. Потерянная строка занижает
    знаменатель, и склад покажется чище, чем он есть."""
    client = FakeClient(
        {"/report/stock/bystore": [report_row(product_id="99999999-9999-9999-9999-999999999999")]}
    )

    outcome = sync_store_stock(client, run)

    assert outcome.extra["skipped"] == 1
    assert StoreStock.objects.count() == 0


def test_failed_report_keeps_previous_rows(run, product):
    """Сбой не опустошает таблицу.

    Пустая таблица означает «на складах ничего не лежит», то есть склад
    пересчитан на сто процентов, — ошибка, выглядящая хорошей новостью.
    """
    StoreStock.objects.create(
        product=product, store_name="Производство", quantity=Decimal("5.000")
    )

    class Broken(FakeClient):
        def iterate(self, path, params=None):
            raise RuntimeError("сеть отвалилась")
            yield

    outcome = sync_store_stock(Broken({}), run)

    assert not outcome.ok
    assert StoreStock.objects.count() == 1


def test_store_stock_runs_after_products():
    """Строки ссылаются на товары — до них вешать их не на что."""
    from moysklad.sync.full import ENTITIES

    names = [name for name, _ in ENTITIES]

    assert names.index("product") < names.index("storestock")


def test_short_report_does_not_replace_the_table(run, product):
    """Короткий, но успешный отчёт таблицу не трогает.

    МойСклад отдаёт только товары с уже пересчитанными остатками. Прогон,
    поймавший середину пересчёта, вернёт треть строк без единой ошибки —
    и заменив таблицу этой третью, страница показала бы склады пересчитанными
    почти полностью, а «не проверено» — почти нулём. Ошибка, выглядящая
    хорошей новостью.
    """
    others = [
        Product.objects.create(ms_id=f"33333333-3333-3333-3333-{i:012d}", name=f"Товар {i}", last_seen_run=run)
        for i in range(9)
    ]
    for item in [product, *others]:
        StoreStock.objects.create(
            product=item, store_name="Производство", quantity=Decimal("1.000")
        )

    client = FakeClient({"/report/stock/bystore": [report_row(stores=(("Производство", 5.0),))]})

    outcome = sync_store_stock(client, SyncRun.objects.create(kind=SyncKind.DOCUMENTS))

    assert outcome.extra["partial"] is True
    assert StoreStock.objects.count() == 10
    assert StoreStock.objects.get(product=product).quantity == Decimal("1.000")


def test_full_report_replaces_the_table(run, product):
    """Полный отчёт заменяет таблицу — иначе увезённое никогда не исчезнет."""
    StoreStock.objects.create(
        product=product, store_name="Производство", quantity=Decimal("1.000")
    )
    client = FakeClient({"/report/stock/bystore": [report_row(stores=(("Хоз товары", 5.0),))]})

    outcome = sync_store_stock(client, SyncRun.objects.create(kind=SyncKind.DOCUMENTS))

    assert outcome.extra["partial"] is False
    assert list(StoreStock.objects.values_list("store_name", flat=True)) == ["Хоз товары"]
