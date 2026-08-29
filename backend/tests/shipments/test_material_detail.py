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


@pytest.fixture
def sold_ten(shampoo, make_demand):
    """Десять шампуней одной отгрузкой: 500 г воды напрямую, 1000 через основу."""
    return position(make_demand(), shampoo["bottled"], "10", 500_00)


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


class TestCoverageInDetail:
    """Запас в днях — единственное число страницы, требующее действия сегодня.

    Считается из того, что уже загружено: расход за период против свободного
    остатка. На боевых данных диметикона хватает на 0 дней, воды на 3.
    """

    def test_days_left_uses_free_stock_not_total(
        self, shampoo, make_demand, make_stock
    ):
        """Зарезервированное уже обещано под заказы.

        Считать его своим значит обнаружить нехватку в день отгрузки —
        и сказать «хватит на 10 дней» там, где хватит на один.
        """
        # Десять дней по 150 г воды в день: 1500 г расхода за 10 дней.
        position(make_demand(moment=moscow(2026, 6, 1)), shampoo["bottled"], "5", 250_00)
        position(make_demand(moment=moscow(2026, 6, 10)), shampoo["bottled"], "5", 250_00)
        make_stock(shampoo["water"], quantity="1500", reserved="1350")

        payload = material_detail.detail(materials.Filters(), shampoo["water"].pk)

        # Расход 150 г/день. Свободно 150 → ровно на день.
        # По всему остатку вышло бы десять — вдесятеро больше правды.
        assert payload["coverage"]["per_day"] == Decimal("150")
        assert payload["coverage"]["days_left"] == 1

    def test_no_stock_means_unknown_not_zero(self, shampoo, sold_ten):
        """У 36 материалов из 161 остатка в отчёте нет вовсе.

        Ноль читался бы как «кончился» — утверждение об учёте, которого
        учёт не делает.
        """
        payload = material_detail.detail(materials.Filters(), shampoo["water"].pk)

        assert payload["stock"] is None
        assert payload["coverage"]["days_left"] is None
        assert payload["coverage"]["level"] == "none"
        # Расход при этом известен: нет остатка, а не нет расхода.
        assert payload["coverage"]["per_day"] > 0

    def test_period_length_comes_from_the_filters(self, shampoo, make_demand):
        """Период задан руками — делим на него, а не на разброс дат.

        Иначе выборка за один день, в который отгрузок было две, дала бы
        дневной расход вдвое ниже настоящего.
        """
        position(make_demand(moment=moscow(2026, 6, 10)), shampoo["bottled"], "10", 500_00)

        payload = material_detail.detail(
            materials.Filters(
                date_from=moscow(2026, 6, 1).date(), date_to=moscow(2026, 6, 30).date()
            ),
            shampoo["water"].pk,
        )
        assert payload["coverage"]["days_of_period"] == 30

    def test_open_period_measures_the_data(self, shampoo, make_demand):
        """Период не задан — длина берётся из фактических дат отгрузок.

        «Сегодня минус год» занизил бы дневной расход во столько раз,
        во сколько ошиблись со сроком.
        """
        position(make_demand(moment=moscow(2026, 6, 1)), shampoo["bottled"], "10", 500_00)
        position(make_demand(moment=moscow(2026, 6, 10)), shampoo["bottled"], "10", 500_00)

        payload = material_detail.detail(materials.Filters(), shampoo["water"].pk)
        assert payload["coverage"]["days_of_period"] == 10


class TestRatesInDetail:
    def test_uniform_rate_is_one_row(self, shampoo, sold_ten):
        """121 материал из 161 имеет одну норму на все изделия."""
        payload = material_detail.detail(materials.Filters(), shampoo["water"].pk)

        assert len(payload["rates"]) == 1
        assert payload["rates"][0]["products_count"] == 1

    def test_rate_counts_every_path(self, shampoo, sold_ten):
        """Норма — весь расход на изделие, а не расход одним путём.

        В шампунь вода приходит дважды: 100 г через замес основы и 50 г
        прямым добавлением при розливе. Норма — 150 г, и показать 50
        значило бы занизить её втрое.
        """
        payload = material_detail.detail(materials.Filters(), shampoo["water"].pk)
        assert payload["rates"][0]["rate"] == 150

    def test_distribution_adds_up_to_the_row(self, shampoo, sold_ten):
        """Показанное обязано складываться в число, которое объясняет."""
        payload = material_detail.detail(materials.Filters(), shampoo["water"].pk)
        dist = payload["distribution"]

        shown = sum(item["quantity"] for item in dist["top"])
        if dist["rest"]:
            shown += dist["rest"]["quantity"]
        assert shown == payload["quantity"]

    def test_breakdown_by_plans_is_still_there(self, shampoo, sold_ten):
        """Разбор по техкартам не удалён — он уехал вниз и свернулся.

        Это единственное место, где видно, что отдушка приходит в шампунь
        двумя путями и 1,02 г на изделие — не описка.
        """
        payload = material_detail.detail(materials.Filters(), shampoo["water"].pk)

        assert payload["sources_count"] >= 1
        assert payload["sources"][0]["paths"]


class TestMultiPathCount:
    """Заголовок свёрнутого разбора говорит, стоит ли его открывать.

    Считался по двадцати показанным источникам, а сравнивался с общим их
    числом: у воды (59 источников) заголовок утверждал «в каждое одним
    путём», хотя многопутёвое изделие могло стоять двадцать первым. Блок
    обещал, что раскрывать нечего, ровно там, где ради этого и существует.
    """

    def test_counts_paths_beyond_the_shown_sources(
        self, shampoo, make_demand, make_product, make_plan
    ):
        # Двадцать один источник: двадцать простых и один двухпутёвый,
        # который по величине расхода окажется за пределом показанных.
        for index in range(20):
            simple = make_product(f"Мыло {index}", article=f"9.{index}", code=f"9-{index}")
            make_plan(f"Розлив мыла {index}", simple, output=1,
                      materials=[(shampoo["water"], 1000)])
            position(make_demand(), simple, "10", 100_00)

        # Шампунь берёт воду двумя путями, но расходует мало — уйдёт в хвост.
        position(make_demand(), shampoo["bottled"], "1", 500_00)

        payload = material_detail.detail(materials.Filters(), shampoo["water"].pk)

        assert payload["sources_count"] == 21
        assert len(payload["sources"]) == 20
        assert payload["multi_path_count"] == 1, (
            "многопутёвое изделие за пределом показанных не сосчитано"
        )

    def test_no_multi_paths_is_zero(self, shampoo, make_demand, make_product, make_plan):
        simple = make_product("Мыло", article="9.1", code="9-1")
        make_plan("Розлив мыла", simple, output=1, materials=[(shampoo["water"], 10)])
        position(make_demand(), simple, "10", 100_00)

        payload = material_detail.detail(materials.Filters(), shampoo["water"].pk)
        assert payload["multi_path_count"] == 0


class TestDetailQueries:
    def test_fixed_period_costs_no_extra_query(
        self, shampoo, sold_ten, django_assert_num_queries
    ):
        """Границы заданы — длину периода считать неоткуда не надо.

        `days_in` при обеих границах возвращает их разницу, и обход всех
        позиций выборки ради отброшенного числа стоил запроса на каждое
        раскрытие строки.
        """
        filters = materials.Filters(
            date_from=moscow(2026, 6, 1).date(), date_to=moscow(2026, 6, 30).date()
        )
        with django_assert_num_queries(9):
            material_detail.detail(filters, shampoo["water"].pk)

    def test_open_period_pays_for_measuring_the_data(
        self, shampoo, sold_ten, django_assert_num_queries
    ):
        """Период не задан — длина берётся из дат выборки, это один запрос.

        Ровно на один больше, чем при заданных границах: столько и стоит
        измерение выборки, и столько мы перестали платить впустую.
        """
        with django_assert_num_queries(10):
            material_detail.detail(materials.Filters(), shampoo["water"].pk)
