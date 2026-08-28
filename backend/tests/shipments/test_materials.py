"""Сборка страницы «Материалы в отгрузках».

Разворачивание техкарт проверено в `tests/test_materials.py`. Здесь — то,
что поверх: цены, стоимость, поиск, порядок, охват расчёта. Ошибка тут
не падает, а выражается в неверной сумме закупки.
"""

from decimal import Decimal

import pytest

from api.shipments.services import materials, selection
from core.models import ProductKind
from tests.shipments.conftest import moscow, position

pytestmark = pytest.mark.django_db


@pytest.fixture
def shampoo(make_product, make_plan):
    """Изделие в два уровня — как настоящее производство StarPony.

    Вода входит и в замес основы, и в розлив: 100 г через основу и 50 г
    напрямую. Именно на этом проверяется, что объяснение показывает
    оба слагаемых, а не одно.
    """
    bottled = make_product("Шампунь 500 мл", article="100.001", code="2-001")
    base = make_product("Основа шампуня", article="", code="")
    water = make_product("Вода дистиллированная", article="W-1", code="9-001")
    bottle = make_product("Флакон 500 мл", article="F-1", code="9-002")

    make_plan("Замес основы", base, output=1, materials=[(water, 100)])
    make_plan("Розлив", bottled, output=1, materials=[(base, 1), (water, 50), (bottle, 1)])
    return {"bottled": bottled, "base": base, "water": water, "bottle": bottle}


@pytest.fixture
def sold_ten(shampoo, make_demand):
    """Продано десять флаконов: 1500 г воды и 10 флаконов."""
    document = make_demand()
    position(document, shampoo["bottled"], "10", 500_00)
    return document


class TestPage:
    def test_semi_finished_never_reaches_the_table(self, shampoo, sold_ten):
        """Полуфабрикат раскрыт: в таблице сырьё, а не «Основа шампуня».

        Основу не закупают, и строка с ней означала бы, что человек
        закажет то, чего не существует у поставщика.
        """
        page = materials.page(materials.Filters())
        names = {row["name"] for row in page["results"]}
        assert "Основа шампуня" not in names
        assert names == {"Вода дистиллированная", "Флакон 500 мл"}

    def test_quantity_sums_both_branches(self, shampoo, sold_ten):
        """Вода из замеса и из розлива складывается в одну строку."""
        page = materials.page(materials.Filters())
        water = _row(page, "Вода дистиллированная")
        assert water["quantity"] == Decimal("1500")

    def test_cost_uses_last_purchase_price(self, shampoo, sold_ten, make_supply):
        """Стоимость считается по последней закупке, а не по первой.

        Цены сырья меняются: у отдушки «Лесные ягоды» в боевых данных
        разница между карточкой и последней приёмкой в полтора раза.
        """
        make_supply(shampoo["water"], "2.00", moment=moscow(2026, 1, 10))
        make_supply(shampoo["water"], "3.00", moment=moscow(2026, 3, 10))

        page = materials.page(materials.Filters())
        water = _row(page, "Вода дистиллированная")
        assert water["price_kopecks"] == Decimal("3.00")
        assert water["cost_kopecks"] == 4500, "взята не последняя цена"

    def test_zero_priced_supply_is_not_a_price(self, shampoo, sold_ten, make_supply):
        """Приёмка по нулю не отменяет настоящую цену.

        В боевых данных 97 позиций приёмок из 402 пришли по нулю — образцы
        и бонусы поставщика. Взять такую за последнюю цену значит обнулить
        стоимость материала: число просто исчезнет с экрана.
        """
        make_supply(shampoo["water"], "3.00", moment=moscow(2026, 1, 10))
        make_supply(shampoo["water"], "0", moment=moscow(2026, 6, 10))

        water = _row(materials.page(materials.Filters()), "Вода дистиллированная")
        assert water["price_kopecks"] == Decimal("3.00")
        assert water["cost_kopecks"] == 4500

    def test_price_from_deleted_supply_is_ignored(self, shampoo, sold_ten, make_supply):
        """Приёмка, исчезнувшая из учёта, цену не задаёт."""
        from django.utils import timezone

        make_supply(shampoo["water"], "2.00", moment=moscow(2026, 1, 10))
        newer = make_supply(shampoo["water"], "9.00", moment=moscow(2026, 6, 10))
        newer.deleted_at = timezone.now()
        newer.save(update_fields=["deleted_at"])

        water = _row(materials.page(materials.Filters()), "Вода дистиллированная")
        assert water["price_kopecks"] == Decimal("2.00")

    def test_material_without_purchases_has_no_cost(self, shampoo, sold_ten):
        """Материал, который ни разу не покупали, — прочерк, а не ноль.

        Ноль читался бы как «достался даром». Таких в боевых данных три
        из ста шестидесяти одного.
        """
        water = _row(materials.page(materials.Filters()), "Вода дистиллированная")
        assert water["cost_kopecks"] is None
        assert water["price_kopecks"] is None
        assert water["cost_share"] is None

    def test_totals_add_up_to_the_column(self, shampoo, sold_ten, make_supply):
        """Итог равен сумме показанного в колонке, до копейки.

        Округли строку и итог порознь — и человек, сложивший колонку
        на калькуляторе, получит другое число, чем подвал.
        """
        make_supply(shampoo["water"], "2.503", moment=moscow(2026, 1, 10))
        make_supply(shampoo["bottle"], "3105.7", moment=moscow(2026, 1, 10))

        page = materials.page(materials.Filters())
        column = sum(row["cost_kopecks"] for row in page["results"])
        assert page["totals"]["cost_kopecks"] == column

    def test_shares_add_up_to_one(self, shampoo, sold_ten, make_supply):
        """Доли строк складываются в единицу — иначе слово «доля» врёт."""
        make_supply(shampoo["water"], "2.00", moment=moscow(2026, 1, 10))
        make_supply(shampoo["bottle"], "3000", moment=moscow(2026, 1, 10))

        page = materials.page(materials.Filters())
        total = sum(row["cost_share"] for row in page["results"])
        assert abs(total - Decimal(1)) < Decimal("0.0000001")


class TestWithoutPlan:
    def test_service_is_not_a_material(self, shampoo, make_demand, make_product):
        """Доставка не попадает в список сырья.

        Без техкарты `explode` вернул бы её саму, и услуга встала бы
        в закупочный список наравне с водой.
        """
        delivery = make_product("Доставка", article="", code="")
        delivery.kind = ProductKind.SERVICE
        delivery.save(update_fields=["kind"])

        document = make_demand()
        position(document, shampoo["bottled"], "10", 500_00)
        position(document, delivery, "1", 300_00)

        page = materials.page(materials.Filters())
        assert "Доставка" not in {row["name"] for row in page["results"]}

        without = page["without_plan"]
        assert [row["name"] for row in without] == ["Доставка"]
        assert without[0]["is_service"] is True
        assert without[0]["revenue_kopecks"] == 300_00

    def test_goods_without_plan_are_shown_too(self, shampoo, make_demand, make_product):
        """Покупной товар без техкарты тоже виден.

        В боевых данных это картонный короб, проданный отдельной строкой:
        не услуга, но и не сырьё — разворачивать его не во что.
        """
        box = make_product("Картонный короб", article="K-1", code="8-001")
        document = make_demand()
        position(document, shampoo["bottled"], "1", 500_00)
        position(document, box, "6", 0)

        page = materials.page(materials.Filters())
        without = {row["name"]: row for row in page["without_plan"]}
        assert without["Картонный короб"]["is_service"] is False

    def test_search_does_not_hide_the_block(self, shampoo, sold_ten, make_demand, make_product):
        """Поиск не прячет блок «без техкарты».

        Исчезни он от запроса «вода» — человек прочтёт таблицу как полную,
        хотя часть проданного в неё не вошла вовсе.
        """
        delivery = make_product("Доставка", article="", code="")
        document = make_demand()
        position(document, delivery, "1", 300_00)

        page = materials.page(materials.Filters(search="вода"))
        assert [row["name"] for row in page["results"]] == ["Вода дистиллированная"]
        assert [row["name"] for row in page["without_plan"]] == ["Доставка"]

    def test_counts_describe_the_selection_not_the_search(
        self, shampoo, sold_ten, make_demand, make_product
    ):
        """Числа охвата не сужаются поиском: они про выборку отгрузок.

        «61 из 66 наименований развёрнуто» — свойство периода, а не запроса
        в поле поиска.
        """
        delivery = make_product("Доставка", article="", code="")
        document = make_demand()
        position(document, delivery, "1", 300_00)

        coverage = materials.page(materials.Filters(search="вода"))["coverage"]
        assert coverage["sold_products_count"] == 2
        assert coverage["exploded_products_count"] == 1
        assert coverage["without_plan_count"] == 1


class TestOrdering:
    def test_unpriced_rows_go_last_both_ways(self, shampoo, sold_ten, make_supply):
        """Строка без цены не может быть первой в списке «самое дорогое».

        И не может быть первой в списке «самое дешёвое»: цены нет вовсе,
        сказать про неё нечего ни в ту, ни в другую сторону.
        """
        make_supply(shampoo["bottle"], "3000", moment=moscow(2026, 1, 10))

        for ordering in ("-cost", "cost"):
            rows = materials.page(materials.Filters(ordering=ordering))["results"]
            assert rows[-1]["name"] == "Вода дистиллированная", ordering
            assert rows[-1]["cost_kopecks"] is None

    def test_unknown_ordering_falls_back(self, shampoo, sold_ten):
        """Значение из адресной строки может быть любым — берём известное."""
        rows = materials.page(materials.Filters(ordering="; drop table"))["results"]
        assert len(rows) == 2

    def test_order_is_fully_determined(self, shampoo, sold_ten, make_supply):
        """Одинаковая стоимость не оставляет порядок на усмотрение Postgres.

        Иначе один материал попадёт на две страницы подряд, а другой —
        ни на одну.
        """
        make_supply(shampoo["water"], "1", moment=moscow(2026, 1, 10))
        make_supply(shampoo["bottle"], "150", moment=moscow(2026, 1, 10))

        first = [row["material_id"] for row in materials.page(materials.Filters())["results"]]
        assert first[0] != first[1]
        for _ in range(3):
            again = [
                row["material_id"] for row in materials.page(materials.Filters())["results"]
            ]
            assert again == first, "порядок строк неустойчив"

    def test_by_name_reverses(self, shampoo, sold_ten):
        forward = [row["name"] for row in materials.page(materials.Filters(ordering="name"))["results"]]
        backward = [row["name"] for row in materials.page(materials.Filters(ordering="-name"))["results"]]
        assert backward == list(reversed(forward))


class TestFilters:
    def test_period_narrows_consumption(self, shampoo, make_demand):
        """Расход считается по отгрузкам периода, а не по всем вообще."""
        position(make_demand(moment=moscow(2026, 3, 1)), shampoo["bottled"], "10", 500_00)
        position(make_demand(moment=moscow(2026, 7, 1)), shampoo["bottled"], "1", 50_00)

        page = materials.page(
            materials.Filters(date_from=moscow(2026, 6, 1).date(), date_to=moscow(2026, 8, 1).date())
        )
        assert _row(page, "Флакон 500 мл")["quantity"] == Decimal("1")

    def test_channel_narrows_consumption(self, shampoo, make_demand, make_channel):
        ozon = make_channel("Озон")
        position(make_demand(channel=ozon), shampoo["bottled"], "10", 500_00)
        position(make_demand(), shampoo["bottled"], "3", 150_00)

        page = materials.page(materials.Filters(channel_id=ozon.pk))
        assert _row(page, "Флакон 500 мл")["quantity"] == Decimal("10")

    def test_draft_shipment_is_excluded(self, shampoo, make_demand):
        """Черновик лежит в той же таблице, но товар по нему не ушёл."""
        position(make_demand(applicable=False), shampoo["bottled"], "10", 500_00)
        assert materials.page(materials.Filters())["results"] == []

    def test_deleted_shipment_is_excluded(self, shampoo, make_demand):
        position(make_demand(deleted=True), shampoo["bottled"], "10", 500_00)
        assert materials.page(materials.Filters())["results"] == []

    def test_documents_counted_once(self, shampoo, make_demand, make_product):
        """Отгрузка с двумя позициями — одна отгрузка, а не две.

        Сложить `documents_count` по строкам значило бы посчитать документ
        столько раз, сколько в нём наименований.
        """
        other = make_product("Кондиционер 500 мл", article="100.002", code="2-002")
        document = make_demand()
        position(document, shampoo["bottled"], "1", 500_00)
        position(document, other, "1", 400_00)

        assert materials.page(materials.Filters())["coverage"]["documents_count"] == 1

    def test_search_matches_code_and_article(self, shampoo, sold_ten):
        by_code = materials.page(materials.Filters(search="9-001"))["results"]
        by_article = materials.page(materials.Filters(search="w-1"))["results"]
        assert [row["name"] for row in by_code] == ["Вода дистиллированная"]
        assert [row["name"] for row in by_article] == ["Вода дистиллированная"]


class TestPagination:
    def test_page_size_is_capped(self, shampoo, sold_ten):
        """Ссылка с огромной высотой страницы не должна уводить в долгий обход."""
        page = materials.page(materials.Filters(page_size=100_000))
        assert len(page["results"]) <= selection.MAX_PAGE_SIZE

    def test_count_is_of_selection_not_page(self, shampoo, sold_ten):
        page = materials.page(materials.Filters(page_size=1))
        assert page["count"] == 2
        assert len(page["results"]) == 1


def _row(page: dict, name: str) -> dict:
    return next(row for row in page["results"] if row["name"] == name)


class TestCost:
    """Расчёт не должен дорожать с числом строк.

    Проверяется числом запросов, а не временем: время плавает от машины,
    а «на каждую строку по запросу» — свойство кода, и оно либо есть,
    либо нет.
    """

    def test_query_count_does_not_grow_with_rows(
        self, make_product, make_plan, make_demand, django_assert_max_num_queries
    ):
        def sell(count: int):
            item = make_product(f"Изделие {count}", article=f"P-{count}", code=f"1-{count:03d}")
            stuff = [
                make_product(f"Сырьё {count}-{index}", article=f"S{count}-{index}",
                             code=f"9-{count:02d}{index:02d}")
                for index in range(count)
            ]
            make_plan(f"Розлив {count}", item, output=1,
                      materials=[(one, 1) for one in stuff])
            position(make_demand(), item, "1", 100_00)

        sell(3)
        with django_assert_max_num_queries(12) as small:
            materials.page(materials.Filters(page_size=100))

        sell(30)
        with django_assert_max_num_queries(12):
            page = materials.page(materials.Filters(page_size=100))

        # Высота страницы задана явно: проверяется рост числа запросов
        # со строками, и все строки должны попасть в ответ независимо
        # от того, сколько их показывает страница по умолчанию.
        assert len(page["results"]) == 33
        assert len(small.captured_queries) <= 12


class TestCoverageIsAboutTheSelection:
    """Сводка описывает выборку отгрузок, поиск её не сужает.

    Смешать одно с другим — значит показать дробь, у которой числитель
    от одного множества, а знаменатель от другого. Число при этом выглядит
    обычным процентом, и заметить подмену нечем.
    """

    def test_search_does_not_move_the_numerator_only(
        self, shampoo, sold_ten, make_supply, make_product, make_plan, make_demand
    ):
        make_supply(shampoo["water"], "2.00", moment=moscow(2026, 1, 10))
        make_supply(shampoo["bottle"], "3000", moment=moscow(2026, 1, 10))

        whole = materials.page(materials.Filters())["coverage"]
        searched = materials.page(materials.Filters(search="вода"))["coverage"]

        assert searched == whole, "поиск изменил сводку, хотя она про выборку"

    def test_footer_totals_follow_the_search(self, shampoo, sold_ten, make_supply):
        """А вот итог под таблицей обязан сходиться с тем, что в ней видно."""
        make_supply(shampoo["water"], "2.00", moment=moscow(2026, 1, 10))
        make_supply(shampoo["bottle"], "3000", moment=moscow(2026, 1, 10))

        page = materials.page(materials.Filters(search="вода"))
        column = sum(
            row["cost_kopecks"] for row in page["results"] if row["cost_kopecks"] is not None
        )
        assert page["totals"]["cost_kopecks"] == column
        assert page["totals"]["materials_count"] == 1

    def test_cost_may_exceed_revenue(self, shampoo, make_demand, make_supply):
        """Сырья может уйти больше, чем принесла выручка.

        На боевых данных это 6 июля 2026: выручка 7,13 ₽, сырья на 290,91 ₽ —
        доля 4080%. Товар отгружали за 0 ₽, а сырьё на него потрачено.
        Число честное, и поле обязано его вместить.
        """
        make_supply(shampoo["water"], "100", moment=moscow(2026, 1, 10))
        position(make_demand(), shampoo["bottled"], "10", 1)

        coverage = materials.page(materials.Filters())["coverage"]
        assert coverage["cost_share_of_revenue"] > 1000

    def test_footer_share_matches_the_column(self, shampoo, sold_ten, make_supply):
        """Итог доли сходится со сложением колонки — и при поиске тоже.

        Строки показывают долю от всей выборки, поэтому жёсткое «100 %»
        в подвале при поиске стояло бы над колонкой, где доли складываются
        в восемь процентов.
        """
        make_supply(shampoo["water"], "2.00", moment=moscow(2026, 1, 10))
        make_supply(shampoo["bottle"], "3000", moment=moscow(2026, 1, 10))

        page = materials.page(materials.Filters(search="вода"))
        column = sum(row["cost_share"] for row in page["results"])
        assert page["totals"]["cost_share"] == column
        assert page["totals"]["cost_share"] < 1, "поиск сузил выборку, а доля — нет"

        whole = materials.page(materials.Filters())
        assert whole["totals"]["cost_share"] == Decimal(1)
