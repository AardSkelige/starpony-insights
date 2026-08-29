"""Расчёт страницы «Материалы в приёмках».

Здесь ошибка тихая: числа остаются правдоподобными. Средняя цена, занижённая
вдвое бесплатными поступлениями, выглядит обычной ценой, и заметить её можно
только сверкой с документом.
"""

from decimal import Decimal

import pytest

from api.common import selection as common
from api.supplies.services import materials
from core.models import DocumentKind
from tests.supplies.conftest import moscow, position

pytestmark = pytest.mark.django_db


def row(name, filters=None):
    """Строка выборки по названию материала."""
    rows = materials.prepared(filters or materials.Filters())["rows"]
    return next(item for item in rows if item["name"] == name)


class TestAveragePrice:
    def test_divides_by_paid_quantity_only(self, make_supply, make_product):
        """Этикетка Табак-Ваниль: 280 штук даром, 216 по 14,2857 ₽.

        Деление на всё количество дало бы 6,22 ₽ — цену, которой нет
        ни в одном документе, и заниженную вдвое.
        """
        label = make_product("Этикетка Табак-Ваниль")
        position(make_supply(moment=moscow(2026, 4, 22)), label, 280, "0")
        position(make_supply(moment=moscow(2026, 8, 21)), label, 216, "1428.5")

        item = row("Этикетка Табак-Ваниль")
        assert item["quantity"] == Decimal("496.000")
        assert item["free_quantity"] == Decimal("280.000")
        assert item["paid_quantity"] == Decimal("216.000")
        assert item["avg_price_kopecks"] == Decimal("1428.5")
        # Деление на всё количество дало бы вот это — вдвое меньше:
        assert item["amount_kopecks"] / item["quantity"] < 700

    def test_free_quantity_stays_inside_quantity(self, make_supply, make_product):
        """Даром пришедшее со склада не исчезает — оно там лежит.

        Вычти его из количества, и «Расчёт производства» недосчитается
        280 этикеток, которые есть в наличии.
        """
        label = make_product("Этикетка")
        position(make_supply(), label, 100, "0")
        position(make_supply(), label, 50, "1000")

        item = row("Этикетка")
        assert item["quantity"] == Decimal("150.000")
        assert item["free_quantity"] == Decimal("100.000")

    def test_only_free_has_no_price(self, make_supply, make_product):
        """24 наименования приходили только даром — все этикетки «Принтеца».

        Ноль читался бы как «достался даром» в смысле «бесплатный
        материал», а это утверждение о цене, которого учёт не делает.
        """
        label = make_product("Этикетка контроля")
        position(make_supply(), label, 10_000, "0")

        item = row("Этикетка контроля")
        assert item["avg_price_kopecks"] is None
        assert item["last_price_kopecks"] is None
        assert item["price_change"] is None


class TestPriceChange:
    def test_compares_with_the_previous_purchase(self, bought):
        """Флакон: 25,05 → 26,759 → 31,05. Последний шаг +16,0%.

        К первой закупке вышло бы +24,0% — число про весь период, а колонка
        отвечает на «подорожало ли в этот раз».
        """
        item = row("Флакон 500 мл")
        assert item["previous_price_kopecks"] == Decimal("2675.9")
        assert round(item["price_change"], 4) == Decimal("0.1604")

    def test_single_purchase_has_no_change(self, make_supply, make_product):
        """У 130 наименований из 212 закупка была одна.

        Ноль означал бы «цена не менялась» — а таких десять, и они
        показывают настоящий ноль.
        """
        material = make_product("ДЭТА")
        position(make_supply(), material, 200_000, "82.55374")

        assert row("ДЭТА")["price_change"] is None

    def test_unchanged_price_shows_zero(self, make_supply, make_product):
        material = make_product("Диметикон")
        position(make_supply(moment=moscow(2026, 5, 1)), material, 100, "45")
        position(make_supply(moment=moscow(2026, 6, 1)), material, 100, "45")

        assert row("Диметикон")["price_change"] == 0

    def test_free_purchase_is_not_a_base(self, make_supply, make_product):
        """Между двумя платными приёмками стоит бесплатная допечатка.

        Сравнение с ней дало бы «выросло с нуля» — бесконечность,
        выведенную из подарка. База берётся предыдущая **с ценой**.
        """
        label = make_product("Этикетка задняя")
        position(make_supply(moment=moscow(2026, 5, 1)), label, 100, "2410.67")
        position(make_supply(moment=moscow(2026, 6, 1)), label, 30, "0")
        position(make_supply(moment=moscow(2026, 7, 1)), label, 100, "2838.33")

        item = row("Этикетка задняя")
        assert item["previous_price_kopecks"] == Decimal("2410.67")
        assert round(item["price_change"], 3) == Decimal("0.177")


class TestWhatCounts:
    def test_shipment_is_not_a_supply(self, make_supply, make_product):
        """Отгрузки и приёмки лежат в одной таблице, различаясь полем `kind`."""
        material = make_product("Отдушка")
        position(make_supply(kind=DocumentKind.DEMAND), material, 10, "500")

        assert materials.prepared(materials.Filters())["rows"] == []

    def test_draft_supply_is_skipped(self, make_supply, make_product):
        """По черновику приёмки товар на склад не пришёл и деньги не ушли.

        Сейчас таких нет ни одного, и именно поэтому фильтр нужен сегодня:
        когда появится первый, расхождение с учётом никто не заметит.
        """
        material = make_product("Отдушка")
        position(make_supply(applicable=False), material, 10, "500")

        assert materials.prepared(materials.Filters())["rows"] == []

    def test_deleted_supply_is_skipped(self, make_supply, make_product):
        material = make_product("Отдушка")
        position(make_supply(deleted=True), material, 10, "500")

        assert materials.prepared(materials.Filters())["rows"] == []

    def test_period_includes_the_whole_last_day(self, make_supply, make_product):
        """Приёмка, проведённая в 23:59:59.5, обязана войти в свой день.

        Сравнение с концом дня теряло бы её без единого признака.
        """
        material = make_product("Отдушка")
        position(
            make_supply(moment=moscow(2026, 6, 30, 23, 59, 59, 500_000)),
            material,
            10,
            "500",
        )
        filters = materials.Filters(date_from=None, date_to=moscow(2026, 6, 30).date())

        assert len(materials.prepared(filters)["rows"]) == 1

    def test_supplier_filter_narrows_documents(
        self, make_supply, make_product, make_supplier
    ):
        material = make_product("Изопропиловый спирт")
        cheap = make_supplier("ООО «Всеинструменты»")
        dear = make_supplier("Алещенко Иван")
        position(make_supply(agent=cheap, moment=moscow(2026, 7, 30)), material, 24_000, "22.02")
        position(make_supply(agent=dear, moment=moscow(2026, 6, 10)), material, 20_000, "30")

        item = row("Изопропиловый спирт", materials.Filters(supplier_id=cheap.pk))
        assert item["quantity"] == Decimal("24000.000")
        assert item["suppliers_count"] == 1


class TestSearch:
    @pytest.mark.parametrize("term", ["хлопок", "1.001", "1-001"])
    def test_search_looks_at_name_article_and_code(
        self, term, make_supply, make_product
    ):
        """Ищут и по коду, и по артикулу — не только по названию.

        В учёте у материалов заполнены оба поля, и вводят обычно то,
        что видно на упаковке.
        """
        position(
            make_supply(),
            make_product("Отдушка Хлопок", article="1.001", code="1-001"),
            10,
            "754",
        )
        position(
            make_supply(),
            make_product("Флакон 500 мл", article="2.001", code="2-001"),
            10,
            "2505",
        )

        rows = materials.prepared(materials.Filters(search=term))["rows"]
        assert [item["name"] for item in rows] == ["Отдушка Хлопок"]

    def test_search_narrows_rows_but_not_coverage(self, make_supply, make_product):
        """Поиск сужает список материалов, а не то, что закупили.

        Возьми охват с учётом поиска — «закуплено на 33 103 ₽ из 93 приёмок»
        стало бы дробью, где числитель от найденного, а знаменатель от всего.
        """
        position(make_supply(), make_product("Отдушка Хлопок", code="1-001"), 10, "754")
        position(make_supply(), make_product("Флакон 500 мл", code="2-001"), 10, "2505")

        whole = materials.prepared(materials.Filters(search="отдушка"))

        assert whole["totals"]["materials_count"] == 1
        assert whole["coverage"]["materials_count"] == 2
        assert whole["coverage"]["documents_count"] == 2

    def test_share_is_taken_from_the_whole_selection(self, make_supply, make_product):
        """Доля строки — от суммы всей выборки, а не найденного.

        Иначе после поиска единственная найденная строка показала бы 100%.
        """
        position(make_supply(), make_product("Отдушка Хлопок", code="1-001"), 10, "1000")
        position(make_supply(), make_product("Флакон 500 мл", code="2-001"), 10, "3000")

        item = row("Отдушка Хлопок", materials.Filters(search="отдушка"))
        assert item["amount_share"] == Decimal("0.25")

    def test_table_total_matches_the_column(self, make_supply, make_product):
        """Итог под таблицей обязан сходиться со сложением колонки."""
        position(make_supply(), make_product("Отдушка Хлопок", code="1-001"), 10, "1000")
        position(make_supply(), make_product("Флакон 500 мл", code="2-001"), 10, "3000")

        whole = materials.prepared(materials.Filters(search="отдушка"))
        shown = sum(item["amount_kopecks"] for item in whole["rows"])

        assert whole["totals"]["amount_kopecks"] == shown
        assert whole["totals"]["amount_share"] == Decimal("0.25")


class TestOrdering:
    def test_default_is_the_largest_amount(self, make_supply, make_product):
        position(make_supply(), make_product("Отдушка", code="1-001"), 10, "1000")
        position(make_supply(), make_product("ДЭТА", code="1-002"), 10, "9000")

        rows = materials.prepared(materials.Filters())["rows"]
        assert [item["name"] for item in rows] == ["ДЭТА", "Отдушка"]

    def test_unknown_key_falls_back(self, bought):
        """Неизвестный ключ откатывается к своему, а не роняет страницу."""
        rows = materials.prepared(materials.Filters(ordering="revenue"))["rows"]
        assert len(rows) == 1

    @pytest.mark.parametrize("ordering", ["change", "-change", "avg_price", "-avg_price"])
    def test_rows_without_the_number_stay_at_the_bottom(
        self, ordering, make_supply, make_product
    ):
        """Список «где сильнее подорожало» не должен начинаться с прочерков.

        Отдельным списком, а не хитрым ключом: переворот направления иначе
        поднял бы их наверх.
        """
        once = make_product("ДЭТА", code="1-001")
        position(make_supply(), once, 10, "0")

        twice = make_product("Флакон", code="2-001")
        position(make_supply(moment=moscow(2026, 5, 1)), twice, 10, "2505")
        position(make_supply(moment=moscow(2026, 6, 1)), twice, 10, "3105")

        rows = materials.prepared(materials.Filters(ordering=ordering))["rows"]
        assert rows[-1]["name"] == "ДЭТА"


class TestPagination:
    def test_count_is_of_selection_not_page(self, make_supply, make_product):
        for index in range(5):
            position(make_supply(), make_product(f"Материал {index}", code=f"{index}"), 1, "100")

        page = materials.page(materials.Filters(page_size=2))
        assert page["count"] == 5
        assert len(page["results"]) == 2

    def test_huge_page_size_does_not_break_the_page(self, bought):
        """Ссылка с огромной высотой отвечает таблицей, а не ошибкой.

        Сам потолок проверяется в `tests/test_selection.py`: здесь строка
        одна, и сравнение с потолком выполнялось бы при любом коде.
        """
        page = materials.page(materials.Filters(page_size=100_000))
        assert len(page["results"]) == 1
        assert common.MAX_PAGE_SIZE == 200


class TestUnits:
    def test_mixed_units_are_flagged(self, make_supply, make_product, gram, piece):
        """Смешение единиц ошибается в тысячу раз и на глаз незаметно."""
        material = make_product("Соль")
        supply = make_supply()
        position(supply, material, 10, "100", uom=gram)
        position(supply, material, 1, "100000", uom=piece)

        item = row("Соль")
        assert item["mixed_uom"] is True
        assert item["uom"] == ""

    def test_single_unit_is_taken_from_positions(self, make_supply, make_product, piece):
        material = make_product("Флакон", uom=None)
        position(make_supply(), material, 10, "2505", uom=piece)

        item = row("Флакон")
        assert item["mixed_uom"] is False
        assert item["uom"] == "шт"


class TestCoverage:
    def test_counts_explain_the_dashes(self, make_supply, make_product):
        """Сводка объясняет, почему в колонках прочерки.

        Без этих чисел итог выглядит полным, хотя у 24 наименований цены
        нет вовсе, а у 130 сравнивать последнюю цену не с чем.
        """
        label = make_product("Этикетка", code="1-001")
        position(make_supply(), label, 100, "0")

        bottle = make_product("Флакон", code="2-001")
        position(make_supply(moment=moscow(2026, 5, 1)), bottle, 10, "2505")
        position(make_supply(moment=moscow(2026, 6, 1)), bottle, 10, "3105")

        coverage = materials.prepared(materials.Filters())["coverage"]

        assert coverage["materials_count"] == 2
        assert coverage["priced_count"] == 1
        assert coverage["unpriced_count"] == 1
        assert coverage["with_history_count"] == 1
        assert coverage["positions_count"] == 3
        assert coverage["free_positions_count"] == 1
        assert coverage["documents_count"] == 3
        assert coverage["suppliers_count"] == 1

    def test_multi_supplier_count(self, make_supply, make_product, make_supplier):
        material = make_product("Изопропиловый спирт")
        position(make_supply(agent=make_supplier("Первый")), material, 10, "2400")
        position(make_supply(agent=make_supplier("Второй")), material, 10, "3000")

        coverage = materials.prepared(materials.Filters())["coverage"]
        assert coverage["multi_supplier_count"] == 1
        assert coverage["suppliers_count"] == 2


class TestQueries:
    def test_page_costs_one_query(self, bought, django_assert_num_queries):
        """Расчёт страницы — один запрос, независимо от числа материалов.

        Тот же дефект уже был в общем сервисе техкарт: единица измерения
        догружалась по каждому материалу, 162 запроса на 161 строку.
        Не падало и не логировалось, только тратило.
        """
        with django_assert_num_queries(1):
            materials.page(materials.Filters())


class TestPriceSeries:
    """Ряд цен для линии: он должен складываться в то, что рисует.

    Линия — такое же расчётное число, как процент, и врёт она так же тихо:
    лишняя точка на нуле превращает ровную цену в обвал и отскок.
    """

    def test_series_is_chronological(self, bought):
        prices = [point["price_kopecks"] for point in row("Флакон 500 мл")["prices"]]
        assert prices == [Decimal("2505"), Decimal("2675.9"), Decimal("3105")]

    def test_series_carries_dates(self, bought):
        """Без дат линия строится по номеру закупки и врёт о скорости роста."""
        moments = [point["moment"].day for point in row("Флакон 500 мл")["prices"]]
        assert moments == [19, 20, 21]

    def test_free_purchases_are_not_points(self, make_supply, make_product):
        """Бесплатная приёмка нарисовала бы падение до нуля и обратно."""
        label = make_product("Этикетка")
        position(make_supply(moment=moscow(2026, 5, 1)), label, 100, "2000")
        position(make_supply(moment=moscow(2026, 6, 1)), label, 30, "0")
        position(make_supply(moment=moscow(2026, 7, 1)), label, 100, "2400")

        prices = [point["price_kopecks"] for point in row("Этикетка")["prices"]]
        assert prices == [Decimal("2000"), Decimal("2400")]

    def test_series_ends_with_the_last_price(self, bought):
        """Последняя точка линии и колонка «Последняя цена» — одно число."""
        item = row("Флакон 500 мл")
        assert item["prices"][-1]["price_kopecks"] == item["last_price_kopecks"]

    def test_unpriced_material_has_an_empty_series(self, make_supply, make_product):
        """Пустой список, а не точка на нуле: цены нет, а не «цена ноль»."""
        label = make_product("Этикетка контроля")
        position(make_supply(), label, 10_000, "0")

        assert row("Этикетка контроля")["prices"] == []


class TestChangeCarriesQuantities:
    """Процент обязан назвать не только цены, но и размеры партий.

    Лауроилглутамат «подорожал на 278 %»: 19.07 пришло 5000 г по 45 копеек,
    05.08 — 1000 г по 170. Партия впятеро меньше, и это часть ответа.
    Без количеств процент читается как чистое подорожание.
    """

    def test_both_quantities_come_with_the_percent(self, make_supply, make_product):
        material = make_product("Лауроилглутамат натрия, 95%")
        position(make_supply(moment=moscow(2026, 7, 19)), material, 5000, "45")
        position(make_supply(moment=moscow(2026, 8, 5)), material, 1000, "170")

        item = row("Лауроилглутамат натрия, 95%")
        assert item["previous_quantity"] == Decimal("5000.000")
        assert item["last_quantity"] == Decimal("1000.000")
        assert round(item["price_change"], 4) == Decimal("2.7778")

    def test_single_purchase_has_no_quantities_to_compare(
        self, make_supply, make_product
    ):
        """`None`, а не количество единственной закупки: сравнивать не с чем."""
        material = make_product("ДЭТА")
        position(make_supply(), material, 200_000, "82.55374")

        item = row("ДЭТА")
        assert item["previous_quantity"] is None
        assert item["last_quantity"] == Decimal("200000.000")


class TestTotalsCountDocuments:
    """Приёмки и поставщики в итоге — про показанные строки, а не про выборку."""

    def test_search_narrows_documents_in_totals(self, make_supply, make_product):
        position(make_supply(), make_product("Отдушка Хлопок", code="1-001"), 10, "754")
        position(make_supply(), make_product("Флакон 500 мл", code="2-001"), 10, "2505")

        whole = materials.prepared(materials.Filters(search="отдушка"))

        assert whole["totals"]["documents_count"] == 1
        # Охват при этом не сужается: он про выборку приёмок целиком.
        assert whole["coverage"]["documents_count"] == 2

    def test_one_supply_of_several_materials_counts_once(
        self, make_supply, make_product
    ):
        """Одна приёмка с тремя материалами — одна закупка, а не три."""
        supply = make_supply()
        for index in range(3):
            position(supply, make_product(f"Материал {index}", code=f"{index}"), 10, "100")

        totals = materials.prepared(materials.Filters())["totals"]
        assert totals["documents_count"] == 1
        assert totals["materials_count"] == 3

    def test_ids_do_not_leak_into_the_response(self, bought):
        """Идентификаторы нужны только счёту и в контракт не уходят."""
        from api.supplies.serializers import SupplyMaterialsSerializer

        page = materials.page(materials.Filters())
        data = SupplyMaterialsSerializer(
            {**page, "synced_at": None, "suppliers": []}
        ).data

        assert "document_ids" not in data["results"][0]
        assert "supplier_ids" not in data["results"][0]
