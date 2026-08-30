"""Синхронизация заказов поставщикам и связи «приёмка → заказ».

Связь существует ради одного числа — срока поставки, — и ломается она тихо:
приёмка без заказа не падает и не выглядит неправильной, она просто выпадает
из знаменателя медианы. Поэтому проверяется и сама связь, и счётчик потерь.

Отдельным файлом от `test_sync_documents.py`: тот про то, как документ
превращается в строку таблицы, этот — про то, как два документа находят
друг друга.
"""

import pytest
from django.utils import timezone

from core.models import (
    Counterparty,
    Document,
    DocumentKind,
    Product,
    SyncKind,
    SyncRun,
    Uom,
)
from moysklad.sync import full
from moysklad.sync.documents import sync_purchase_orders, sync_supplies

pytestmark = pytest.mark.django_db

BASE = "https://api.moysklad.ru/api/remap/1.2"

ORDER_ID = "11111111-1111-1111-1111-111111111111"
SUPPLY_ID = "22222222-2222-2222-2222-222222222222"


def ref(entity: str, ms_id: str) -> dict:
    return {"meta": {"href": f"{BASE}/entity/{entity}/{ms_id}", "type": entity}}


class FakeClient:
    """Отдаёт заранее заданные строки и запоминает, о чём его спрашивали.

    Параметры запроса здесь не украшение: `expand=positions` у заказов —
    это лишние данные на каждый документ, и проверить, что его не просят,
    можно только так.
    """

    request_count = 0

    def __init__(self, rows_by_path: dict[str, list[dict]]):
        self._rows = rows_by_path
        self.calls: list[tuple[str, dict]] = []

    def iterate(self, path, params=None):
        self.calls.append((path, dict(params or {})))
        yield from self._rows.get(path, [])


@pytest.fixture
def run():
    return SyncRun.objects.create(kind=SyncKind.DOCUMENTS)


@pytest.fixture
def supplier(run):
    return Counterparty.objects.create(
        ms_id="aaaaaaaa-0000-0000-0000-000000000001",
        name="ООО «Лемун»",
        last_seen_run=run,
    )


@pytest.fixture
def material(run):
    uom = Uom.objects.create(
        ms_id="ffffffff-0000-0000-0000-000000000001", name="г", last_seen_run=run
    )
    return Product.objects.create(
        ms_id="bbbbbbbb-0000-0000-0000-000000000001",
        name="Отдушка",
        uom=uom,
        last_seen_run=run,
    )


def order_row(ms_id=ORDER_ID, *, agent, moment="2026-04-01 10:00:00.000"):
    return {
        "id": ms_id,
        "name": "З-00001",
        "moment": moment,
        "agent": ref("counterparty", str(agent.ms_id)),
        "sum": 500000.0,
        "applicable": True,
    }


def supply_row(ms_id=SUPPLY_ID, *, agent, order_ms_id=ORDER_ID, material=None,
               moment="2026-04-09 15:00:00.000"):
    row = {
        "id": ms_id,
        "name": "00001",
        "moment": moment,
        "agent": ref("counterparty", str(agent.ms_id)),
        "sum": 500000.0,
        "applicable": True,
    }
    if order_ms_id:
        row["purchaseOrder"] = ref("purchaseorder", order_ms_id)
    if material is not None:
        row["positions"] = {
            "rows": [
                {
                    "assortment": ref("product", str(material.ms_id)),
                    "quantity": 1000.0,
                    "price": 500.0,
                    "discount": 0.0,
                }
            ]
        }
    return row


class TestOrdersAreStored:
    def test_order_becomes_a_document_of_its_own_kind(self, run, supplier):
        client = FakeClient({"/entity/purchaseorder": [order_row(agent=supplier)]})

        outcome = sync_purchase_orders(client, run)

        assert outcome.ok and outcome.created == 1
        order = Document.objects.get(ms_id=ORDER_ID)
        assert order.kind == DocumentKind.PURCHASE_ORDER
        assert order.total_kopecks == 500000

    def test_positions_are_not_requested(self, run, supplier):
        """У заказа нас интересует только дата. Что заказывали — известно
        из приёмки, и вторая копия тех же строк разошлась бы с первой
        там, где пришло не всё заказанное."""
        client = FakeClient({"/entity/purchaseorder": [order_row(agent=supplier)]})

        sync_purchase_orders(client, run)

        path, params = client.calls[0]
        assert path == "/entity/purchaseorder"
        assert "expand" not in params

    def test_marking_deleted_does_not_touch_supplies(self, run, supplier):
        """Заказы и приёмки лежат в одной таблице. Пометка исчезнувших идёт
        по своему виду, иначе прогон заказов похоронил бы все приёмки."""
        Document.objects.create(
            ms_id=SUPPLY_ID,
            kind=DocumentKind.SUPPLY,
            number="00001",
            moment=timezone.now(),
            agent=supplier,
            last_seen_run=SyncRun.objects.create(kind=SyncKind.DOCUMENTS),
        )
        client = FakeClient({"/entity/purchaseorder": [order_row(agent=supplier)]})

        sync_purchase_orders(client, run)

        assert Document.objects.get(ms_id=SUPPLY_ID).deleted_at is None


class TestLink:
    def test_supply_finds_its_order(self, run, supplier, material):
        """Ради этой связи заказы и синхронизируются: без неё срок поставки
        не посчитать ничем."""
        sync_purchase_orders(
            FakeClient({"/entity/purchaseorder": [order_row(agent=supplier)]}), run
        )
        outcome = sync_supplies(
            FakeClient(
                {"/entity/supply": [supply_row(agent=supplier, material=material)]}
            ),
            run,
        )

        assert outcome.ok
        supply = Document.objects.get(ms_id=SUPPLY_ID)
        assert supply.purchase_order is not None
        assert str(supply.purchase_order.ms_id) == ORDER_ID

    def test_missing_order_is_counted_not_swallowed(self, run, supplier, material):
        """Приёмка ссылается на заказ, которого в зеркале нет. Она обязана
        сохраниться — товар пришёл, — но потеря обязана посчитаться: иначе
        медиана незаметно съедет на оставшихся парах."""
        outcome = sync_supplies(
            FakeClient(
                {"/entity/supply": [supply_row(agent=supplier, material=material)]}
            ),
            run,
        )

        assert outcome.ok
        assert Document.objects.get(ms_id=SUPPLY_ID).purchase_order is None
        assert outcome.extra["unlinked_supplies"] == 1

    def test_supply_without_a_reference_is_not_a_loss(self, run, supplier, material):
        """Приёмка, у которой заказа нет вовсе, — не потеря синхронизации,
        а факт учёта. Считать её пропавшей значило бы поднять тревогу
        на пустом месте."""
        outcome = sync_supplies(
            FakeClient(
                {
                    "/entity/supply": [
                        supply_row(agent=supplier, order_ms_id=None, material=material)
                    ]
                }
            ),
            run,
        )

        assert outcome.extra["unlinked_supplies"] == 0

    def test_order_of_a_wrong_kind_is_not_linked(self, run, supplier, material):
        """Ссылка на документ, который заказом не является, связи не даёт.
        Иначе битая ссылка привязала бы приёмку к отгрузке, и срок поставки
        посчитался бы от чужой даты."""
        Document.objects.create(
            ms_id=ORDER_ID,
            kind=DocumentKind.DEMAND,
            number="О-00001",
            moment=timezone.now(),
            agent=supplier,
            last_seen_run=run,
        )

        outcome = sync_supplies(
            FakeClient(
                {"/entity/supply": [supply_row(agent=supplier, material=material)]}
            ),
            run,
        )

        assert Document.objects.get(ms_id=SUPPLY_ID).purchase_order is None
        assert outcome.extra["unlinked_supplies"] == 1


class TestOrderOfEntities:
    def test_orders_are_synced_before_supplies(self):
        """Приёмка ссылается на заказ. В обратном порядке связь не установилась
        бы ни у одной из них — и молча, ровно один прогон, срок поставки
        показывался бы прочерком."""
        names = [name for name, _ in full.ENTITIES]

        assert names.index("purchaseorder") < names.index("supply")

    def test_orders_are_synced_after_counterparties(self):
        """Заказ висит на контрагенте: без справочника он был бы пропущен целиком."""
        names = [name for name, _ in full.ENTITIES]

        assert names.index("counterparty") < names.index("purchaseorder")
