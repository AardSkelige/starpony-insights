"""Товары в отгрузках: фильтры, границы периода, порядок и страницы."""

from datetime import date
from decimal import Decimal

import pytest

from api.shipments.services import products
from tests.shipments.conftest import moscow, position

pytestmark = pytest.mark.django_db


# --- Границы периода ---------------------------------------------------------


def test_period_includes_the_last_second_of_the_final_day(make_product, make_demand):
    """Документ, проведённый в 23:59:59, входит в свой день.

    Сравнение с концом дня по секундам молча теряет такие документы:
    ошибки нет, просто выручка меньше.
    """
    product = make_product()
    position(
        make_demand(moment=moscow(2026, 6, 30, 23, 59, 59, 999999)), product, "1.000", 10000
    )

    _, count, revenue = products.rows(
        products.Filters(date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    )

    assert count == 1
    assert revenue == 10000


def test_period_includes_the_first_second_of_the_first_day(make_product, make_demand):
    product = make_product()
    position(make_demand(moment=moscow(2026, 6, 1, 0, 0, 0)), product, "1.000", 10000)

    _, count, _ = products.rows(
        products.Filters(date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    )

    assert count == 1


def test_period_excludes_the_day_after(make_product, make_demand):
    product = make_product()
    position(make_demand(moment=moscow(2026, 7, 1, 0, 0, 0)), product, "1.000", 10000)

    _, count, _ = products.rows(
        products.Filters(date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    )

    assert count == 0


# --- Фильтры -----------------------------------------------------------------


def test_channel_filter(make_product, make_demand, channel):
    product = make_product()
    position(make_demand(channel=channel), product, "1.000", 10000)
    position(make_demand(), product, "7.000", 70000)

    (row,), _, _ = products.rows(products.Filters(channel_id=channel.id))

    assert row["quantity"] == Decimal("1.000")


@pytest.mark.parametrize("term", ["шампунь", "ШАМПУНЬ", "100.001", "2-001"])
def test_search_covers_name_article_and_code(make_product, make_demand, term):
    """Ищут по-разному: по названию, по артикулу с сайта и по коду из учёта."""
    product = make_product(name="Шампунь", article="100.001", code="2-001")
    position(make_demand(), product, "1.000", 10000)
    position(make_demand(), make_product(name="Воск", article="400.004", code="2-064"),
             "1.000", 20000)

    _, count, _ = products.rows(products.Filters(search=term))

    assert count == 1


# --- Наполнение фильтра каналов ----------------------------------------------


def test_channel_list_does_not_shrink_when_a_channel_is_chosen(
    make_product, make_demand, channel, make_channel
):
    """Выбор канала не должен опустошать список каналов.

    Считай мы его по отфильтрованной выборке — после выбора «Озон» в списке
    остался бы один «Озон», и переключиться на соседний канал стало бы нечем.
    """
    other = make_channel("ВКонтакте")
    product = make_product()
    position(make_demand(channel=channel), product, "1.000", 10000)
    position(make_demand(channel=other), product, "1.000", 10000)

    names = [row["name"] for row in products.channels(products.Filters(channel_id=channel.id))]

    assert names == ["ВКонтакте", "Озон"]


def test_channel_list_respects_the_period(make_product, make_demand, channel, make_channel):
    """Канал, по которому в периоде ничего не было, в фильтре не нужен."""
    other = make_channel("Яндекс")
    product = make_product()
    position(make_demand(moment=moscow(2026, 6, 15), channel=channel), product, "1.000", 10000)
    position(make_demand(moment=moscow(2026, 1, 15), channel=other), product, "1.000", 10000)

    names = [
        row["name"]
        for row in products.channels(
            products.Filters(date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
        )
    ]

    assert names == ["Озон"]


# --- Страницы и порядок ------------------------------------------------------


def test_ordering_is_fully_determined(make_product, make_demand):
    """Порядок строк определён полностью — до последнего ключа.

    Без разрешения ничьих товары с равной выручкой идут так, как Postgres
    сочтёт удобным, и между запросами порядок может смениться: один товар
    попадёт на две страницы подряд, другой — ни на одну.

    Проверяется сам запрос, а не выданный порядок: недетерминизм нельзя
    воспроизвести по заказу, и тест «строки не повторились» проходит вхолостую —
    на маленькой выборке они не повторятся и без ключа.
    """
    for index in range(3):
        position(make_demand(), make_product(code=f"2-{index:03d}"), "1.000", 10000)

    ordering = products.grouped(products.Filters()).query.order_by

    assert ordering[-1] == products.TIE_BREAKER, (
        "Последний ключ сортировки должен быть уникальным полем, "
        f"а сортировка выглядит так: {ordering}"
    )


def test_paging_returns_each_row_once(make_product, make_demand):
    """Страницы вместе дают всю выборку и ничего не дублируют."""
    for index in range(6):
        position(make_demand(), make_product(code=f"2-{index:03d}"), "1.000", 10000)

    first, _, _ = products.rows(products.Filters(page=1, page_size=3))
    second, _, _ = products.rows(products.Filters(page=2, page_size=3))

    seen = [row["product_id"] for row in first + second]
    assert len(seen) == len(set(seen)) == 6


def test_unknown_ordering_falls_back_to_default(make_product, make_demand):
    """Мусор в «ordering» не должен ни падать, ни сортировать по чужому полю."""
    small, big = make_product(code="2-001"), make_product(code="2-002")
    position(make_demand(), small, "1.000", 10000)
    position(make_demand(), big, "1.000", 90000)

    rows, _, _ = products.rows(products.Filters(ordering="product__uom__name"))

    assert [row["product_id"] for row in rows] == [big.id, small.id]


def test_ordering_uses_minus_for_descending(make_product, make_demand):
    """Минус означает убывание — как в DRF и в SQL.

    Обратное соглашение читается наоборот у текстовых полей: «name»
    пришлось бы понимать как «от Я к А», и стрелка в заголовке колонки
    показывала бы не туда.
    """
    small, big = make_product(code="2-001"), make_product(code="2-002")
    position(make_demand(), small, "1.000", 10000)
    position(make_demand(), big, "1.000", 90000)

    ascending, _, _ = products.rows(products.Filters(ordering="revenue"))
    descending, _, _ = products.rows(products.Filters(ordering="-revenue"))

    assert [row["product_id"] for row in ascending] == [small.id, big.id]
    assert [row["product_id"] for row in descending] == [big.id, small.id]


def test_default_ordering_puts_the_biggest_first(make_product, make_demand):
    """Без явной сортировки сверху самое крупное: страницу открывают ради него."""
    small, big = make_product(code="2-001"), make_product(code="2-002")
    position(make_demand(), small, "1.000", 10000)
    position(make_demand(), big, "1.000", 90000)

    rows, _, _ = products.rows(products.Filters())

    assert [row["product_id"] for row in rows] == [big.id, small.id]


def test_name_ordering_is_alphabetical(make_product, make_demand):
    """«name» — от А к Я, как ожидает человек от текстовой колонки."""
    later = make_product(name="Яблочный шампунь", code="2-001")
    earlier = make_product(name="Апельсиновый шампунь", code="2-002")
    position(make_demand(), later, "1.000", 90000)
    position(make_demand(), earlier, "1.000", 10000)

    rows, _, _ = products.rows(products.Filters(ordering="name"))

    assert [row["name"] for row in rows] == [
        "Апельсиновый шампунь",
        "Яблочный шампунь",
    ]


def test_sorting_by_average_price(make_product, make_demand):
    """Сортировка по средней цене — «что у нас самое дорогое»."""
    cheap, pricey = make_product(code="2-001"), make_product(code="2-002")
    position(make_demand(), cheap, "10.000", 10000)   # 10 ₽ за штуку
    position(make_demand(), pricey, "1.000", 9000)    # 90 ₽ за штуку

    rows, _, _ = products.rows(products.Filters(ordering="-avg_price"))

    assert [row["product_id"] for row in rows] == [pricey.id, cheap.id]


def test_sorting_by_average_price_survives_zero_quantity(make_product, make_demand):
    """Нулевое количество не должно ронять весь запрос.

    Деление на ноль в Postgres прерывает выборку целиком, а не одну строку:
    страница отдала бы ошибку вместо таблицы.
    """
    normal, empty = make_product(code="2-001"), make_product(code="2-002")
    position(make_demand(), normal, "2.000", 20000)
    position(make_demand(), empty, "0.000", 0)

    rows, _, _ = products.rows(products.Filters(ordering="-avg_price"))

    assert len(rows) == 2
    # Строка без цены уходит в конец: сравнивать её не с чем.
    assert rows[0]["product_id"] == normal.id


def test_sorting_by_free_quantity(make_product, make_demand):
    """Сортировка по бесплатным — «что раздаём больше всего»."""
    few, many = make_product(code="2-001"), make_product(code="2-002")
    position(make_demand(), few, "1.000", 0)
    position(make_demand(), many, "9.000", 0)

    rows, _, _ = products.rows(products.Filters(ordering="-free"))

    assert [row["product_id"] for row in rows] == [many.id, few.id]


def test_sorting_by_share_matches_revenue(make_product, make_demand):
    """Доля пропорциональна выручке, поэтому и порядок у них один.

    Отдельного выражения не нужно: деление каждой строки на одно и то же
    число порядок не меняет.
    """
    small, big = make_product(code="2-001"), make_product(code="2-002")
    position(make_demand(), small, "1.000", 10000)
    position(make_demand(), big, "5.000", 90000)

    by_share, _, _ = products.rows(products.Filters(ordering="-share"))
    by_revenue, _, _ = products.rows(products.Filters(ordering="-revenue"))

    assert [row["product_id"] for row in by_share] == [row["product_id"] for row in by_revenue]


def test_channel_list_ignores_the_search_term(
    make_product, make_demand, channel, make_channel
):
    """Поиск не должен выбрасывать каналы из фильтра.

    Иначе набранное слово убирает выбранный канал из списка, поле показывает
    «Канал» — будто ничего не выбрано, — а выборка всё ещё отфильтрована
    по нему. Выйти можно только «Сбросить», теряя заодно и поиск.
    """
    other = make_channel("ВКонтакте")
    position(make_demand(channel=channel), make_product(name="Шампунь"), "1.000", 10000)
    position(make_demand(channel=other), make_product(name="Воск", code="2-009"), "1.000", 10000)

    names = [
        row["name"]
        for row in products.channels(
            products.Filters(channel_id=channel.id, search="шампунь")
        )
    ]

    assert names == ["ВКонтакте", "Озон"]
