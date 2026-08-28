"""Панель материала: то самое место, где число объясняет себя.

Строка таблицы говорит «1 500 г воды». Панель обязана разложить это число
на слагаемые так, чтобы они сошлись обратно, — иначе объяснение не проверяемо,
а по этим числам закупают.
"""

from decimal import Decimal

import pytest

from api.shipments.services import material_detail, materials
from tests.shipments.conftest import moscow, position

pytestmark = pytest.mark.django_db


@pytest.fixture
def shampoo(make_product, make_plan):
    bottled = make_product("Шампунь 500 мл", article="100.001", code="2-001")
    base = make_product("Основа шампуня", article="", code="")
    water = make_product("Вода дистиллированная", article="W-1", code="9-001")
    make_plan("Замес основы", base, output=1, materials=[(water, 100)])
    make_plan("Розлив", bottled, output=1, materials=[(base, 1), (water, 50)])
    return {"bottled": bottled, "base": base, "water": water}


class TestExplanation:
    def test_both_paths_are_shown(self, shampoo, make_demand):
        """Вода из замеса и вода из розлива — два слагаемых, а не одно число.

        Это главное обещание страницы: посчитанное показывает, как получено.
        """
        position(make_demand(), shampoo["bottled"], "10", 500_00)

        detail = material_detail.detail(materials.Filters(), shampoo["water"].pk)
        paths = detail["sources"][0]["paths"]

        assert len(paths) == 2, f"объяснён один путь из двух: {paths}"
        by_chain = {tuple(path["chain"]): path["quantity"] for path in paths}
        assert by_chain == {
            ("Розлив", "Замес основы"): Decimal("1000"),
            ("Розлив",): Decimal("500"),
        }

    def test_paths_add_up_to_the_source(self, shampoo, make_demand):
        """Слагаемые складываются в число изделия."""
        position(make_demand(), shampoo["bottled"], "7", 350_00)

        source = material_detail.detail(materials.Filters(), shampoo["water"].pk)["sources"][0]
        assert sum(path["quantity"] for path in source["paths"]) == source["quantity"]

    def test_sources_add_up_to_the_row(self, shampoo, make_demand, make_product, make_plan):
        """Сумма по изделиям равна числу в строке таблицы.

        Разойдись они — человек увидит в панели одно, а в таблице другое,
        и перестанет верить обоим.
        """
        conditioner = make_product("Кондиционер 500 мл", article="100.002", code="2-002")
        make_plan("Розлив кондиционера", conditioner, output=1, materials=[(shampoo["water"], 30)])

        document = make_demand()
        position(document, shampoo["bottled"], "10", 500_00)
        position(document, conditioner, "4", 200_00)

        row = next(
            item
            for item in materials.page(materials.Filters())["results"]
            if item["material_id"] == shampoo["water"].pk
        )
        detail = material_detail.detail(materials.Filters(), shampoo["water"].pk)

        assert sum(source["quantity"] for source in detail["sources"]) == row["quantity"]
        assert detail["quantity"] == row["quantity"]

    def test_sources_are_sorted_by_weight(self, shampoo, make_demand, make_product, make_plan):
        """Крупнейший источник сверху: порядок сам отвечает «откуда столько»."""
        conditioner = make_product("Кондиционер 500 мл", article="100.002", code="2-002")
        make_plan("Розлив кондиционера", conditioner, output=1, materials=[(shampoo["water"], 30)])

        document = make_demand()
        position(document, shampoo["bottled"], "1", 50_00)
        position(document, conditioner, "100", 5000_00)

        names = [
            source["name"]
            for source in material_detail.detail(materials.Filters(), shampoo["water"].pk)["sources"]
        ]
        assert names == ["Кондиционер 500 мл", "Шампунь 500 мл"]


class TestPrice:
    def test_price_names_its_document(self, shampoo, make_demand, make_supply, make_counterparty):
        """Цена приходит с документом, датой и поставщиком.

        Число, посчитанное по цене, обязано назвать её источник: иначе
        колонка «Стоимость» — сумма, за которую никто не отвечает.
        """
        supplier = make_counterparty("ООО Химснаб")
        position(make_demand(), shampoo["bottled"], "10", 500_00)
        make_supply(shampoo["water"], "2.50", moment=moscow(2026, 6, 15), supplier=supplier)

        price = material_detail.detail(materials.Filters(), shampoo["water"].pk)["price"]
        assert price["price_kopecks"] == Decimal("2.50")
        assert price["supplier"] == "ООО Химснаб"
        assert price["moment"].date() == moscow(2026, 6, 15).date()

    def test_no_purchases_means_no_price_block(self, shampoo, make_demand):
        position(make_demand(), shampoo["bottled"], "10", 500_00)
        detail = material_detail.detail(materials.Filters(), shampoo["water"].pk)
        assert detail["price"] is None
        assert detail["cost_kopecks"] is None


class TestSelection:
    def test_material_outside_selection_is_404(self, shampoo, make_demand):
        """Материала в этой выборке нет — пустые блоки соврали бы «не расходовался»."""
        position(make_demand(moment=moscow(2026, 3, 1)), shampoo["bottled"], "10", 500_00)

        with pytest.raises(material_detail.MaterialNotUsed):
            material_detail.detail(
                materials.Filters(date_from=moscow(2026, 6, 1).date()),
                shampoo["water"].pk,
            )

    def test_filters_apply_to_detail(self, shampoo, make_demand, make_channel):
        """Панель объясняет ту строку, которую видно, — с теми же фильтрами."""
        ozon = make_channel("Озон")
        position(make_demand(channel=ozon), shampoo["bottled"], "10", 500_00)
        position(make_demand(), shampoo["bottled"], "90", 4500_00)

        detail = material_detail.detail(
            materials.Filters(channel_id=ozon.pk), shampoo["water"].pk
        )
        assert detail["quantity"] == Decimal("1500")


class TestRest:
    """Длинный список источников сворачивается, а не обрезается.

    У воды в боевых данных пятьдесят девять изделий-источников. Показать
    двадцать и промолчать про остальные значит показать объяснение, которое
    не сходится с объясняемым числом.
    """

    @pytest.fixture
    def many_sources(self, shampoo, make_product, make_plan, make_demand):
        document = make_demand()
        position(document, shampoo["bottled"], "1", 50_00)
        for index in range(material_detail.SOURCE_LIMIT + 5):
            item = make_product(f"Изделие {index}", article=f"P-{index}", code=f"1-{index:03d}")
            make_plan(f"Розлив {index}", item, output=1, materials=[(shampoo["water"], 10)])
            position(document, item, "1", 10_00)

    def test_hidden_sources_are_summed_not_dropped(self, shampoo, many_sources):
        detail = material_detail.detail(materials.Filters(), shampoo["water"].pk)

        assert len(detail["sources"]) == material_detail.SOURCE_LIMIT
        assert detail["sources_count"] == material_detail.SOURCE_LIMIT + 6
        assert detail["rest"]["products_count"] == 6

        shown = sum(source["quantity"] for source in detail["sources"])
        assert shown + detail["rest"]["quantity"] == detail["quantity"]

    def test_short_list_has_no_rest(self, shampoo, make_demand):
        """Пустой хвост и свёрнутый хвост — разные вещи."""
        position(make_demand(), shampoo["bottled"], "10", 500_00)
        assert material_detail.detail(materials.Filters(), shampoo["water"].pk)["rest"] is None
