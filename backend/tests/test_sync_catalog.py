"""Синхронизация номенклатуры.

Единицы измерения проверяются отдельно: ошибка в них не падает, а даёт
расхождение ровно в 1000 раз — граммы против килограммов.
"""

from decimal import Decimal

import pytest

from core.models import Product, SyncKind, SyncRun, Uom
from moysklad.sync.catalog import folder_path, uom_from_ref

pytestmark = pytest.mark.django_db


UOM_ID = "8e2eb543-99e9-4077-bc31-93b1359de9c4"


@pytest.fixture
def run():
    return SyncRun.objects.create(kind=SyncKind.DOCUMENTS)


@pytest.fixture
def grams(run):
    return Uom.objects.create(ms_id=UOM_ID, name="г", description="Грамм", last_seen_run=run)


class TestUomResolution:
    def test_resolves_by_reference(self, grams):
        """В товаре единица приходит ссылкой без названия — берём из справочника.

        Так и было пропущено в первой версии: код читал `uom.name`, которого
        в ответе нет, и все 314 товаров сохранились без единицы измерения.
        """
        ref = {"meta": {"href": f"https://api.moysklad.ru/api/remap/1.2/entity/uom/{UOM_ID}"}}
        assert uom_from_ref(ref, {UOM_ID: grams}) == grams

    @pytest.mark.parametrize("ref", [None, {}, {"meta": {}}, {"meta": {"href": ""}}])
    def test_missing_reference_gives_none(self, ref):
        assert uom_from_ref(ref, {}) is None

    def test_unknown_uom_gives_none(self):
        """Единицы нет в справочнике — лучше пусто, чем чужая единица."""
        ref = {"meta": {"href": "https://api.moysklad.ru/api/remap/1.2/entity/uom/unknown"}}
        assert uom_from_ref(ref, {}) is None


class TestProductFields:
    def test_fractional_buy_price_is_kept(self, run):
        """Закупочная цена хранится в копейках, с шестью знаками дробной части.

        Именно в копейках, а не в рублях: деление на 100 при записи сдвигает
        дробную часть на два знака и вытесняет значащие. На боевых данных
        это дало 8 копеек расхождения между суммой позиций и суммой документа.
        """
        product = Product.objects.create(
            ms_id="11111111-1111-1111-1111-111111111111",
            name="Основа кондиционера",
            buy_price_kopecks=Decimal("7284.090909"),
            last_seen_run=run,
        )
        product.refresh_from_db()
        assert product.buy_price_kopecks == Decimal("7284.090909")

    def test_quantity_precision_is_three_decimals(self, run):
        """Количества — три знака: техкарты считают в долях грамма."""
        product = Product.objects.create(
            ms_id="22222222-2222-2222-2222-222222222222",
            name="Трилон Б",
            min_balance=Decimal("0.300"),
            last_seen_run=run,
        )
        product.refresh_from_db()
        assert product.min_balance == Decimal("0.300")


class TestFolderPath:
    """Путь группы товара — по нему выводится линейка продукции.

    Ошибка здесь была тихой и стоила целой страницы: `pathName` — это путь
    **до** группы, без её собственного имени. Код брал его вместо полного
    пути, и все 90 товаров готовой продукции складывались в одну «Готовую
    продукцию». Семь линеек учёта — шампуни, кондиционеры, репеллент,
    амуниция, бытовая химия и две собачьих — исчезали целиком, а поле
    при этом выглядело заполненным.
    """

    def test_keeps_the_group_name_itself(self):
        """«Готовая продукция» + «Репеллент» = «Готовая продукция/Репеллент»."""
        row = {"productFolder": {"pathName": "Готовая продукция", "name": "Репеллент"}}
        assert folder_path(row) == "Готовая продукция/Репеллент"

    def test_top_level_group_has_no_prefix(self):
        """Группа в корне: пути до неё нет, и лишнего разделителя быть не должно."""
        row = {"productFolder": {"pathName": "", "name": "Хоз. товары"}}
        assert folder_path(row) == "Хоз. товары"

    def test_nested_group_keeps_the_whole_path(self):
        row = {"productFolder": {"pathName": "Хоз. товары/Упаковка", "name": "Короба"}}
        assert folder_path(row) == "Хоз. товары/Упаковка/Короба"

    @pytest.mark.parametrize("row", [{}, {"productFolder": None}, {"productFolder": {}}])
    def test_product_without_a_group_gives_empty(self, row):
        """Товар вне групп — обычное состояние: услуги лежат в корне."""
        assert folder_path(row) == ""
