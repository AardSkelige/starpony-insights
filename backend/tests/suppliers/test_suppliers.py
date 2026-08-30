"""Сборка страницы «Поставщики»: строки, доли, сортировка, два набора итогов.

Проверяется то, что уже ломалось на соседних страницах и ломается тихо:
знаменатель доли, сузившийся поиском; итог, смешавший два множества;
и наименование, посчитанное дважды, потому что приходит от двух поставщиков.
"""

from decimal import Decimal

import pytest

from api.suppliers.services import suppliers as service
from tests.suppliers.conftest import moscow, position

pytestmark = pytest.mark.django_db


@pytest.fixture
def three_suppliers(make_supply, make_supplier, make_product):
    """Трое: крупный, средний и разовый — плюс общий для двоих материал.

    Общий материал здесь не для красоты: 21 наименование из 212 на боевых
    данных приходит больше чем от одного поставщика, и именно на них
    сложение колонки расходится с числом наименований в выборке.
    """
    big = make_supplier("ООО «Химпитерторг Групп»")
    small = make_supplier("Принтец")
    once = make_supplier("ООО «Азимут»")

    shared = make_product("Отдушка", article="1.001", code="1-001")
    only_big = make_product("Диметикон", article="1.002", code="1-002")
    only_small = make_product("Этикетка", article="3.001", code="3-001")

    first = make_supply(moment=moscow(2026, 4, 1), agent=big, total_kopecks=600_000)
    position(first, shared, 1000, "400")
    position(first, only_big, 1000, "200")

    second = make_supply(
        moment=moscow(2026, 4, 15), agent=big, total_kopecks=400_000, lead_days=8
    )
    position(second, only_big, 2000, "200")

    third = make_supply(moment=moscow(2026, 4, 10), agent=small, total_kopecks=300_000)
    position(third, shared, 500, "400")
    position(third, only_small, 100, "1000")

    fourth = make_supply(moment=moscow(2026, 4, 20), agent=once, total_kopecks=100_000)
    position(fourth, only_small, 50, "2000")

    return {"big": big, "small": small, "once": once}


class TestRows:
    def test_amount_comes_from_the_document(self, three_suppliers):
        """Сумма документа — факт учёта. Складывать позиции значило бы
        разойтись с ним ровно тогда, когда синхронизация пропустит строку."""
        rows = {row["name"]: row for row in service.prepared(service.Filters())["rows"]}

        assert rows["ООО «Химпитерторг Групп»"]["amount_kopecks"] == 1_000_000
        assert rows["ООО «Химпитерторг Групп»"]["supplies_count"] == 2

    def test_materials_are_counted_per_supplier(self, three_suppliers):
        rows = {row["name"]: row for row in service.prepared(service.Filters())["rows"]}

        assert rows["ООО «Химпитерторг Групп»"]["materials_count"] == 2
        assert rows["Принтец"]["materials_count"] == 2
        assert rows["ООО «Азимут»"]["materials_count"] == 1

    def test_period_bounds_come_from_the_supplies(self, three_suppliers):
        rows = {row["name"]: row for row in service.prepared(service.Filters())["rows"]}
        big = rows["ООО «Химпитерторг Групп»"]

        assert big["first_moment"] == moscow(2026, 4, 1)
        assert big["last_moment"] == moscow(2026, 4, 15)

    def test_free_positions_are_counted(self, make_supply, make_product):
        """У «Принтеца» 97 позиций из 129 пришли даром. Без этого числа
        «46 наименований на 55 100 ₽» объяснить нечем."""
        supply = make_supply(total_kopecks=0)
        position(supply, make_product("Этикетка"), 280, "0")
        position(supply, make_product("Крышка"), 100, "500")

        row = service.prepared(service.Filters())["rows"][0]

        assert row["positions_count"] == 2
        assert row["free_positions_count"] == 1


class TestShares:
    def test_shares_add_up_to_one(self, three_suppliers):
        rows = service.prepared(service.Filters())["rows"]

        assert sum(row["amount_share"] for row in rows) == Decimal(1)

    def test_search_does_not_narrow_the_denominator(self, three_suppliers):
        """Набрав «принт», человек сужает список строк, а не то, что закупили.

        Иначе, найдя одного поставщика, увидишь «100 %» и прочтёшь это как
        «весь закуп у него».
        """
        found = service.prepared(service.Filters(search="принт"))

        assert len(found["rows"]) == 1
        assert found["rows"][0]["amount_share"] < Decimal("0.5")
        assert found["totals"]["amount_share"] == found["rows"][0]["amount_share"]

    def test_period_does_narrow_the_denominator(self, three_suppliers):
        """А период — входит: при выборе апреля доли обязаны складываться
        в сто процентов апреля, а не всей истории."""
        rows = service.prepared(
            service.Filters(date_from=moscow(2026, 4, 12).date())
        )["rows"]

        assert sum(row["amount_share"] for row in rows) == Decimal(1)


class TestTotals:
    def test_column_adds_up_to_the_footer(self, three_suppliers):
        """Экран открывают, чтобы складывать, и расхождение находят
        калькулятором."""
        whole = service.prepared(service.Filters())

        assert whole["totals"]["amount_kopecks"] == sum(
            row["amount_kopecks"] for row in whole["rows"]
        )
        assert whole["totals"]["supplies_count"] == sum(
            row["supplies_count"] for row in whole["rows"]
        )

    def test_shared_material_is_not_counted_twice(self, three_suppliers):
        """Отдушка приходит от двоих. Сложение колонки дало бы четыре
        наименования там, где их три."""
        whole = service.prepared(service.Filters())

        assert whole["totals"]["materials_count"] == 3
        assert sum(row["materials_count"] for row in whole["rows"]) == 5

    def test_totals_follow_the_search(self, three_suppliers):
        found = service.prepared(service.Filters(search="принт"))

        assert found["totals"]["suppliers_count"] == 1
        assert found["totals"]["supplies_count"] == 1
        assert found["totals"]["materials_count"] == 2


class TestCoverageIsAboutTheSelection:
    def test_search_does_not_touch_it(self, three_suppliers):
        """Сводка описывает выборку приёмок целиком. Слей её с итогом —
        получится дробь, где числитель от найденного, а знаменатель от всего:
        «1 поставщик из 4 приёмок» выглядит обычным числом и врёт молча.
        """
        whole = service.prepared(service.Filters())
        found = service.prepared(service.Filters(search="принт"))

        assert found["coverage"] == whole["coverage"]
        assert found["coverage"]["suppliers_count"] == 3
        assert found["coverage"]["supplies_count"] == 4

    def test_counts_what_explains_the_dashes(self, three_suppliers):
        """У «Принтеца» и «Азимута» по одной поставке, и промежутка между
        поставками не существует. Сводка обязана сказать, у скольких строк
        прочерк, — иначе он читается как сбой.

        Срок при этом есть у всех троих: он считается и по одной поставке,
        лишь бы у неё был заказ.
        """
        coverage = service.prepared(service.Filters())["coverage"]

        assert coverage["with_regularity_count"] == 1
        assert coverage["with_lead_time_count"] == 3
        assert coverage["unlinked_supplies_count"] == 0

    def test_unlinked_supplies_are_visible(self, make_supply):
        """Приёмка без заказа в зеркале обязана считаться: иначе срок
        посчитается не по всей истории и не скажет об этом."""
        make_supply(moment=moscow(2026, 4, 1), lead_days=3)
        make_supply(moment=moscow(2026, 4, 10), ordered=False)

        coverage = service.prepared(service.Filters())["coverage"]

        assert coverage["unlinked_supplies_count"] == 1


class TestOrdering:
    def test_default_is_by_amount(self, three_suppliers):
        rows = service.prepared(service.Filters())["rows"]

        assert [row["name"] for row in rows] == [
            "ООО «Химпитерторг Групп»",
            "Принтец",
            "ООО «Азимут»",
        ]

    def test_unknown_ordering_falls_back(self, three_suppliers):
        """Сортировка приходит из адресной строки: ссылка с чужой страницы
        не должна ронять эту."""
        rows = service.prepared(service.Filters(ordering="-revenue"))["rows"]

        assert rows[0]["name"] == "ООО «Химпитерторг Групп»"

    def test_rows_without_a_value_stay_at_the_bottom(self, three_suppliers):
        """Переворот направления не должен поднимать наверх тех, кому
        сортировать нечем: список «кто возит реже всех» начинался бы
        с поставщиков, не возивших дважды."""
        for ordering in ("regularity", "-regularity"):
            rows = service.prepared(service.Filters(ordering=ordering))["rows"]
            assert rows[-1]["name"] == "ООО «Азимут»"

    def test_ties_are_resolved_stably(self, make_supply, make_supplier):
        """Без разрешения ничьих один поставщик попал бы на две страницы
        подряд, а другой — ни на одну."""
        for name in ("Первый", "Второй", "Третий"):
            make_supply(agent=make_supplier(name), total_kopecks=100_000)

        first = service.prepared(service.Filters())["rows"]
        second = service.prepared(service.Filters())["rows"]

        assert [row["name"] for row in first] == [row["name"] for row in second]


class TestPerSupplier:
    """Медианы считаются каждому свои — через тот же путь, что и страница."""

    def test_suppliers_do_not_borrow_each_others_numbers(
        self, make_supply, make_supplier
    ):
        """Главное различие боевых данных: «Химпитерторг» возит за 7,5 дня
        раз в две недели, у «Принтеца» забирают в тот же день раз в неделю.
        Смешай их — оба получат несуществующую середину.
        """
        carrier = make_supplier("ООО «Химпитерторг Групп»")
        counter = make_supplier("Принтец")
        for day, lead in ((1, 7), (15, 8), (29, 9)):
            make_supply(moment=moscow(2026, 4, day), agent=carrier, lead_days=lead)
        for day in (1, 8, 15):
            make_supply(moment=moscow(2026, 4, day), agent=counter, lead_days=0)

        rows = {row["name"]: row for row in service.prepared(service.Filters())["rows"]}

        assert rows["ООО «Химпитерторг Групп»"]["lead_time"].days == Decimal("8")
        assert rows["ООО «Химпитерторг Групп»"]["regularity"].days == Decimal("14")
        assert rows["Принтец"]["lead_time"].days == Decimal("0")
        assert rows["Принтец"]["regularity"].days == Decimal("7")

    def test_page_does_not_query_per_row(
        self, three_suppliers, django_assert_num_queries
    ):
        """Ни срок, ни поставщик не стоят запроса на строку.

        Два запроса на всю страницу: приёмки и их позиции. N+1 здесь
        незаметен на 95 приёмках и станет заметен ровно тогда, когда
        история дорастёт до тысяч.
        """
        with django_assert_num_queries(2):
            service.prepared(service.Filters())


class TestPage:
    def test_page_slices_but_totals_do_not(self, three_suppliers):
        """Итог считается по всей выборке, а не по видимой странице."""
        page = service.page(service.Filters(page_size=1))

        assert page["count"] == 3
        assert len(page["results"]) == 1
        assert page["totals"]["suppliers_count"] == 3


class TestDaysForExport:
    def test_zero_is_spelled_out(self):
        """Ноль в колонке срока читается как пустая ячейка. У троих
        поставщиков из двадцати трёх медиана ровно ноль, и это ответ."""
        assert service.days_of(Decimal("0")) == "в тот же день"

    def test_whole_days_stay_whole(self):
        assert service.days_of(Decimal("7.0")) == "7"

    def test_half_a_day_survives(self):
        assert service.days_of(Decimal("7.5")) == "7,5"

    def test_nothing_measured_is_a_dash(self):
        assert service.days_of(None) == "—"


class TestMaterialsOfSupplier:
    """Что именно у поставщика берём.

    Число «39 наименований» страница показывала и раньше, но на «каких»
    не отвечала: чтобы узнать, приходилось идти на соседнюю страницу
    и фильтровать по поставщику.
    """

    def test_sorted_by_amount_not_quantity(
        self, make_supply, make_supplier, make_product
    ):
        """По деньгам, а не по количеству: граммы и штуки не сравнить
        ни сложением, ни длиной полосы. Деньги — единственное общее."""
        supplier = make_supplier("ООО «Лемун»")
        cheap_but_many = make_product("Вода", article="1.007", code="1-007")
        dear_but_few = make_product("Отдушка", article="1.001", code="1-001")

        supply = make_supply(agent=supplier, total_kopecks=300_000)
        position(supply, cheap_but_many, 100_000, "1")
        position(supply, dear_but_few, 100, "2000")

        row = service.prepared(service.Filters())["rows"][0]

        assert [item["name"] for item in row["materials"]["items"]] == [
            "Отдушка",
            "Вода",
        ]

    def test_tail_is_folded_not_dropped(
        self, make_supply, make_supplier, make_product
    ):
        """Хвост свёрнут, но не отброшен: иначе показанное не складывается
        в сумму поставщика, и расхождение спишут на расчёт."""
        supply = make_supply(total_kopecks=0)
        for i in range(service.MATERIAL_LIMIT + 3):
            position(supply, make_product(f"Материал {i}"), 1, str((i + 1) * 100))

        materials = service.prepared(service.Filters())["rows"][0]["materials"]
        shown = sum(item["amount_kopecks"] for item in materials["items"])

        assert len(materials["items"]) == service.MATERIAL_LIMIT
        assert materials["rest_count"] == 3
        # 100 + 200 + … + 800 = 3600 копеек.
        assert shown + materials["rest_amount_kopecks"] == 3600

    def test_shares_add_up_to_one(self, three_suppliers):
        """Доли внутри блока — от суммы этого поставщика, а не всей выборки:
        иначе у мелкого поставщика все доли были бы по проценту."""
        rows = service.prepared(service.Filters())["rows"]
        big = next(row for row in rows if row["name"].startswith("ООО «Химпитерторг"))

        assert sum(item["share"] for item in big["materials"]["items"]) == Decimal(1)
