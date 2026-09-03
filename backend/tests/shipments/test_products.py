"""Товары в отгрузках: агрегация и расчётные числа.

Проверяется то, что ломается тихо: деньги, доли и то, что в выборку
попадать не должно. Внешний вид не проверяется — он ломается заметно.
"""

from decimal import Decimal

import pytest

from api.shipments.services import products
from core.models import DocumentKind
from tests.shipments.conftest import position

pytestmark = pytest.mark.django_db


def test_revenue_and_quantity_sum_up(make_product, make_demand):
    """Выручка и количество складываются по всем отгрузкам товара."""
    product = make_product()
    position(make_demand(), product, "3.000", 30000)
    position(make_demand(), product, "2.000", 20000)

    rows, count, total_revenue = products.rows(products.Filters())

    assert count == 1
    assert total_revenue == 50000
    assert rows[0]["quantity"] == Decimal("5.000")
    assert rows[0]["revenue_kopecks"] == 50000


def test_free_quantity_counts_only_zero_sum_positions(make_product, make_demand):
    """«Даром» — это позиции с нулевой суммой, а не с нулевой ценой.

    Смешать их с продажами значит занизить среднюю цену, ничем этого не показав:
    на боевых данных так теряется от 20 до 30 процентов.
    """
    product = make_product()
    position(make_demand(), product, "4.000", 40000)
    position(make_demand(), product, "1.000", 0)

    (row,), _, _ = products.rows(products.Filters())

    assert row["quantity"] == Decimal("5.000")
    assert row["free_quantity"] == Decimal("1.000")
    # 40000 копеек ÷ 5 штук против 40000 ÷ 4 платных
    assert row["avg_price_kopecks"] == Decimal(8000)
    assert row["avg_price_paid_kopecks"] == Decimal(10000)


def test_average_price_keeps_fractional_kopecks(make_product, make_demand):
    """Средняя цена не округляется до копейки.

    ДЭТА стоит 480 ₽/кг, в техкарте её 0.1 г. Округление такой удельной
    величины даёт ошибку в проценты, а не в копейки.
    """
    product = make_product()
    position(make_demand(), product, "3.000", 10000)

    (row,), _, _ = products.rows(products.Filters())

    assert row["avg_price_kopecks"] == Decimal(10000) / Decimal("3.000")
    assert row["avg_price_kopecks"] != Decimal(3333)


def test_average_price_is_none_without_quantity(make_product, make_demand):
    """Ноль вместо цены читался бы как «отдавали бесплатно». Цены просто нет."""
    product = make_product()
    position(make_demand(), product, "0.000", 0)

    (row,), _, _ = products.rows(products.Filters())

    assert row["avg_price_kopecks"] is None
    assert row["avg_price_paid_kopecks"] is None


def test_shares_add_up_to_one(make_product, make_demand):
    """Доли строк складываются в единицу — иначе число значит не то, что написано."""
    first, second = make_product(code="2-001"), make_product(code="2-002")
    position(make_demand(), first, "1.000", 30000)
    position(make_demand(), second, "1.000", 10000)

    rows, _, _ = products.rows(products.Filters())

    assert sum(row["revenue_share"] for row in rows) == Decimal(1)


def test_share_is_none_when_nothing_was_sold_for_money(make_product, make_demand):
    """Вся выборка бесплатна — доли нет. Ноль здесь означал бы «ничего не дал»."""
    product = make_product()
    position(make_demand(), product, "2.000", 0)

    (row,), _, _ = products.rows(products.Filters())

    assert row["revenue_share"] is None


def test_share_is_taken_from_the_same_selection(make_product, make_demand, channel):
    """При фильтре по каналу доля считается от выручки этого канала.

    Считай мы от всех продаж — доли на экране не сложились бы в сто процентов.
    """
    product = make_product()
    position(make_demand(channel=channel), product, "1.000", 25000)
    position(make_demand(), make_product(code="2-009"), "1.000", 75000)

    (row,), _, _ = products.rows(products.Filters(channel_id=channel.id))

    assert row["revenue_share"] == Decimal(1)


# --- Что в выборку не попадает -----------------------------------------------


def test_supplies_are_not_counted(make_product, make_demand):
    """Приёмки лежат в той же таблице и не должны попасть в продажи."""
    product = make_product()
    position(make_demand(), product, "1.000", 10000)
    position(make_demand(kind=DocumentKind.SUPPLY), product, "5.000", 50000)

    (row,), _, _ = products.rows(products.Filters())

    assert row["quantity"] == Decimal("1.000")


def test_unposted_documents_are_not_counted(make_product, make_demand):
    """Черновик отгрузки лежит в той же таблице, но продажей не является.

    Товар по нему со склада не ушёл и денег не принёс. Сейчас непроведённых
    отгрузок нет ни одной — и именно поэтому важно отсечь их сегодня:
    когда появится первая, расхождение с учётом никто не заметит.
    """
    product = make_product()
    position(make_demand(), product, "1.000", 10000)
    position(make_demand(applicable=False), product, "9.000", 90000)

    (row,), _, _ = products.rows(products.Filters())

    assert row["quantity"] == Decimal("1.000")
    assert row["revenue_kopecks"] == 10000


def test_deleted_documents_are_not_counted(make_product, make_demand):
    """Исчезнувший из учёта документ не входит ни в одну сумму.

    Строка не удаляется физически — на неё могут ссылаться данные людей,
    но в расчёте её быть не должно.
    """
    product = make_product()
    position(make_demand(), product, "1.000", 10000)
    position(make_demand(deleted=True), product, "9.000", 90000)

    (row,), _, _ = products.rows(products.Filters())

    assert row["quantity"] == Decimal("1.000")
    assert row["revenue_kopecks"] == 10000


class TestShareIgnoresSearch:
    """Доля — от выручки выборки, но без учёта поиска.

    Период и канал в знаменатель входят: при фильтре по Озону доли обязаны
    складываться в сто процентов Озона. Поиск — нет: он сужает список строк,
    а не то, что продали. Иначе, найдя один товар, человек увидит «100 %»
    и прочтёт это как «весь оборот в нём».

    То же правило на обеих страницах материалов — три страницы обязаны
    считать долю одинаково.
    """

    @pytest.fixture
    def two_products(self, make_product, make_demand):
        shampoo = make_product("Шампунь 500 мл", article="100.001", code="2-001")
        brush = make_product("Щётка", article="200.001", code="3-001")
        position(make_demand(), shampoo, "1", 250_00)
        position(make_demand(), brush, "1", 750_00)
        return {"shampoo": shampoo, "brush": brush}

    def test_search_does_not_inflate_the_share(self, two_products):
        """Шампунь — четверть выручки, и поиск этого не меняет."""
        page = products.page(products.Filters(search="шампунь"))

        assert page["count"] == 1
        assert page["results"][0]["revenue_share"] == Decimal("0.25")

    def test_channel_does_narrow_the_share(self, make_product, make_demand, channel):
        """Канал в знаменатель входит: доли Озона складываются в сто процентов."""
        shampoo = make_product("Шампунь 500 мл", article="100.001", code="2-001")
        brush = make_product("Щётка", article="200.001", code="3-001")
        position(make_demand(channel=channel), shampoo, "1", 250_00)
        position(make_demand(), brush, "1", 750_00)

        page = products.page(products.Filters(channel_id=channel.pk))
        assert page["results"][0]["revenue_share"] == 1

    def test_footer_share_matches_the_column(self, two_products):
        """Итог обязан сходиться со сложением колонки, а не показывать «100 %»."""
        page = products.page(products.Filters(search="шампунь"))
        shown = sum(row["revenue_share"] for row in page["results"])

        assert page["totals"]["revenue_share"] == shown

    def test_no_search_is_a_hundred_percent(self, two_products):
        page = products.page(products.Filters())
        assert page["totals"]["revenue_share"] == 1

    def test_extra_aggregate_only_when_searching(
        self, two_products, django_assert_num_queries
    ):
        """Знаменатель без поиска — второй проход, и он платится только там,
        где поиск задан.

        Числа абсолютные, а не разница: она одна поймала бы лишний проход,
        но не поймала бы запрос на строку. Восемь — это строки, их счёт,
        итог, два агрегата сводки, свёртка по товарам для стоимости раздачи
        и два вычитания по реализации.

        **С поиском их столько же.** Знаменатель доли — это выручка выборки
        без поиска, и её уже посчитала сводка: отдельный проход за тем же
        числом был вторым обходом всех позиций.
        """
        with django_assert_num_queries(8):
            products.page(products.Filters())
        with django_assert_num_queries(8):
            products.page(products.Filters(search="шампунь"))
