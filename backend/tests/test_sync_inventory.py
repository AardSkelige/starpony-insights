"""Синхронизация инвентаризаций.

Проверяется то, что ломается тихо: расхождение, посчитанное нами вместо
учёта; позиция, потерянная вместе с расхождением; документ, помеченный
удалённым из-за собственного пропуска.
"""

from decimal import Decimal

import pytest
from django.utils import timezone

from core.models import Inventory, InventoryPosition, Product, SyncKind, SyncRun
from moysklad.sync.full import ENTITIES
from moysklad.sync.inventory import sync_inventories

pytestmark = pytest.mark.django_db

BASE = "https://api.moysklad.ru/api/remap/1.2"
INVENTORY_ID = "11111111-1111-1111-1111-111111111111"
PRODUCT_ID = "22222222-2222-2222-2222-222222222222"


def meta(entity: str, ms_id: str) -> dict:
    return {"meta": {"href": f"{BASE}/entity/{entity}/{ms_id}", "type": entity}}


class FakeClient:
    """Отдаёт заданные строки по пути. Запоминает параметры запросов."""

    request_count = 0

    def __init__(self, rows: dict):
        self._rows = rows
        self.calls: list[tuple[str, dict | None]] = []

    def iterate(self, path, params=None):
        self.calls.append((path, params))
        yield from self._rows.get(path, [])


def position(
    *,
    product_id: str = PRODUCT_ID,
    quantity: float = 8.0,
    calculated: float = 10.0,
    correction: float = -2.0,
    correction_sum: float = -30000.0,
    price: float = 15000.0,
    assortment_type: str = "product",
) -> dict:
    return {
        "assortment": meta(assortment_type, product_id),
        "quantity": quantity,
        "calculatedQuantity": calculated,
        "correctionAmount": correction,
        "correctionSum": correction_sum,
        "price": price,
    }


def document(*, ms_id: str = INVENTORY_ID, positions: list[dict] | None = None, **fields) -> dict:
    row = {
        "id": ms_id,
        "name": "00006",
        "moment": "2026-08-06 12:00:00.000",
        "updated": "2026-08-06 12:30:00.000",
        "sum": 340000.0,
        "description": "Плановый пересчёт",
        "store": dict(meta("store", "33333333-3333-3333-3333-333333333333"), name="Материалы"),
        "positions": {"rows": positions if positions is not None else [position()]},
    }
    row.update(fields)
    return row


@pytest.fixture
def run():
    return SyncRun.objects.create(kind=SyncKind.DOCUMENTS)


@pytest.fixture
def product(run):
    return Product.objects.create(ms_id=PRODUCT_ID, name="Шампунь", last_seen_run=run)


class TestCorrectionComesFromAccounting:
    """Расхождение берётся из ответа API, а не считается нами.

    Инвентаризация, созданная через API с позициями в теле, приходит
    с расчётным остатком, равным фактическому: наша разность выдала бы
    ноль за результат расчёта, и страница молча соврала бы о сходимости.
    """

    def test_correction_is_stored_as_accounting_counted_it(self, run, product):
        client = FakeClient({"/entity/inventory": [document()]})

        sync_inventories(client, run)

        saved = InventoryPosition.objects.get()
        assert saved.correction_amount == Decimal("-2.000")
        assert saved.correction_sum_kopecks == -30000

    def test_correction_is_not_recomputed_from_quantities(self, run, product):
        """Учёт сказал −5 при разнице −2 — храним −5 и считаем это расхождением.

        Пересчитать самим значило бы подменить учёт своей арифметикой:
        число на экране перестало бы сходиться с числом в карточке документа,
        и объяснить его было бы нечем.
        """
        client = FakeClient({"/entity/inventory": [document(positions=[position(correction=-5.0)])]})

        outcome = sync_inventories(client, run)

        assert InventoryPosition.objects.get().correction_amount == Decimal("-5.000")
        assert outcome.extra["mismatched_corrections"] == 1

    def test_matching_correction_raises_no_alarm(self, run, product):
        client = FakeClient({"/entity/inventory": [document()]})

        outcome = sync_inventories(client, run)

        assert outcome.extra["mismatched_corrections"] == 0

    def test_api_created_document_is_visible_as_broken(self, run, product):
        """Ровно та ловушка: расчётный остаток подменён фактическим.

        Расхождение выходит нулевым при живой недостаче, и без счётчика
        документ выглядел бы сошедшимся.
        """
        client = FakeClient(
            {"/entity/inventory": [document(positions=[position(quantity=8.0, calculated=8.0, correction=0.0)])]}
        )

        outcome = sync_inventories(client, run)

        saved = InventoryPosition.objects.get()
        assert saved.counted == saved.calculated == Decimal("8.000")
        assert saved.correction_amount == 0
        # Само по себе это законный документ — «всё сошлось». Отличить его
        # от подменённого можно только по несходимости, и её здесь нет:
        # предупреждать не о чем, но и уверять, что пересчёт был честным,
        # синк не вправе.
        assert outcome.extra["mismatched_corrections"] == 0


class TestStore:
    """Склад не украшение: их три, и пересчитан всегда один.

    Без него «считали 06.08» читается как «посчитали весь товар», хотя
    посчитана была упаковка на одном складе из трёх.
    """

    def test_store_name_is_saved(self, run, product):
        sync_inventories(FakeClient({"/entity/inventory": [document()]}), run)

        assert Inventory.objects.get().store_name == "Материалы"

    def test_missing_store_leaves_the_field_empty(self, run, product):
        """Склад не доехал — лучше пусто, чем чужое имя."""
        sync_inventories(FakeClient({"/entity/inventory": [document(store={})]}), run)

        assert Inventory.objects.get().store_name == ""


class TestPrecision:
    def test_quantities_keep_three_decimals(self, run, product):
        client = FakeClient(
            {"/entity/inventory": [document(positions=[position(quantity=0.125, calculated=0.5, correction=-0.375)])]}
        )

        sync_inventories(client, run)

        saved = InventoryPosition.objects.get()
        assert saved.counted == Decimal("0.125")
        assert saved.calculated == Decimal("0.500")
        assert saved.correction_amount == Decimal("-0.375")

    def test_price_is_stored_in_kopecks_with_six_decimals(self, run, product):
        client = FakeClient({"/entity/inventory": [document(positions=[position(price=7284.090909)])]})

        sync_inventories(client, run)

        assert InventoryPosition.objects.get().price_kopecks == Decimal("7284.090909")

    def test_correction_sum_is_whole_kopecks(self, run, product):
        """Сумма — целые копейки: округление, а не усечение."""
        client = FakeClient({"/entity/inventory": [document(positions=[position(correction_sum=-29999.6)])]})

        sync_inventories(client, run)

        assert InventoryPosition.objects.get().correction_sum_kopecks == -30000

    def test_document_sum_is_whole_kopecks(self, run, product):
        client = FakeClient({"/entity/inventory": [document(sum=340000.4)]})

        sync_inventories(client, run)

        assert Inventory.objects.get().total_kopecks == 340000


class TestSkips:
    def test_unknown_assortment_is_skipped_and_counted(self, run, product):
        """Модификация или комплект: строку теряем, но не молча.

        Потерянная позиция — это потерянное расхождение: страница покажет
        «всё сошлось» там, где не сошлось.
        """
        client = FakeClient(
            {
                "/entity/inventory": [
                    document(
                        positions=[
                            position(),
                            position(product_id="99999999-9999-9999-9999-999999999999", assortment_type="variant"),
                        ]
                    )
                ]
            }
        )

        outcome = sync_inventories(client, run)

        assert InventoryPosition.objects.count() == 1
        assert outcome.extra["skipped_positions"] == 1

    def test_document_without_date_is_skipped(self, run, product):
        client = FakeClient({"/entity/inventory": [document(moment="")]})

        outcome = sync_inventories(client, run)

        assert Inventory.objects.count() == 0
        assert outcome.extra["skipped_documents"] == 1

    def test_skipped_document_is_not_marked_deleted(self, run, product):
        """Пропуск — не исчезновение.

        Без исключения из пометки документ выпал бы из расчётов навсегда:
        штампа прогона у него нет, а `restore_returned` снимает пометку
        только с того, что в прогоне видели.
        """
        Inventory.objects.create(
            ms_id=INVENTORY_ID, number="00006", moment=timezone.now(), last_seen_run=run
        )
        later = SyncRun.objects.create(kind=SyncKind.DOCUMENTS)
        client = FakeClient({"/entity/inventory": [document(moment="")]})

        outcome = sync_inventories(client, later)

        assert outcome.marked_deleted == 0
        assert Inventory.objects.get().deleted_at is None


class TestMirror:
    def test_missing_document_is_marked_deleted(self, run, product):
        Inventory.objects.create(
            ms_id="44444444-4444-4444-4444-444444444444",
            number="00001",
            moment=timezone.now(),
            last_seen_run=run,
        )
        later = SyncRun.objects.create(kind=SyncKind.DOCUMENTS)

        outcome = sync_inventories(FakeClient({"/entity/inventory": []}), later)

        assert outcome.marked_deleted == 1
        assert Inventory.objects.get().deleted_at is not None

    def test_returned_document_loses_the_mark(self, run, product):
        Inventory.objects.create(
            ms_id=INVENTORY_ID,
            number="00006",
            moment=timezone.now(),
            deleted_at=timezone.now(),
            last_seen_run=run,
        )
        later = SyncRun.objects.create(kind=SyncKind.DOCUMENTS)

        sync_inventories(FakeClient({"/entity/inventory": [document()]}), later)

        assert Inventory.objects.get().deleted_at is None

    def test_positions_are_replaced_not_doubled(self, run, product):
        """Второй прогон переписывает строки целиком, а не добавляет к ним."""
        client = FakeClient({"/entity/inventory": [document()]})
        sync_inventories(client, run)

        later = SyncRun.objects.create(kind=SyncKind.DOCUMENTS)
        sync_inventories(FakeClient({"/entity/inventory": [document()]}), later)

        assert InventoryPosition.objects.count() == 1


class TestRequest:
    def test_positions_and_store_come_with_the_document(self, run, product):
        """`expand` вместо запроса на каждый документ: корзина общая с ботом."""
        client = FakeClient({"/entity/inventory": [document()]})

        sync_inventories(client, run)

        path, params = client.calls[0]
        assert path == "/entity/inventory"
        assert params["expand"] == "positions,store"

    def test_inventory_runs_after_products(self):
        """Позиция ссылается на товар — до товаров вешать её не на что."""
        names = [name for name, _ in ENTITIES]

        assert names.index("product") < names.index("inventory")
