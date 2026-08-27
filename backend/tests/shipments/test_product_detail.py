"""Детали строки: разбивка по каналам, последние отгрузки, остаток."""

from datetime import date
from decimal import Decimal

import pytest

from api.shipments.services import product_detail, products
from core.models import Stock
from tests.shipments.conftest import moscow, position

pytestmark = pytest.mark.django_db

PAGE_KEY = "shipments-products"


def test_channels_are_sorted_by_quantity(make_product, make_demand, channel, make_channel):
    """Полосы читаются сверху вниз, и порядок сам отвечает, какой канал главный.

    Канал с бо́льшим количеством заведён вторым намеренно: иначе порядок
    по количеству совпал бы с порядком заведения, и тест прошёл бы
    при любой сортировке.
    """
    bigger = make_channel("Telegram")
    product = make_product()
    position(make_demand(channel=channel), product, "2.000", 20000)
    position(make_demand(channel=bigger), product, "10.000", 100000)

    rows = product_detail.channels(products.Filters(), product.id)

    assert [row["name"] for row in rows] == ["Telegram", "Озон"]
    assert rows[0]["quantity"] == Decimal("10.000")


def test_channels_sum_up_to_the_row(make_product, make_demand, channel, make_channel):
    """Разбивка обязана сходиться с числом в строке таблицы.

    Разойдись они — человек увидит «продано 43», сложит полосы и получит 39,
    и дальше не поверит ни одному числу на странице.
    """
    product = make_product()
    position(make_demand(channel=channel), product, "7.000", 70000)
    position(make_demand(channel=make_channel("ВКонтакте")), product, "3.000", 30000)

    rows = product_detail.channels(products.Filters(), product.id)
    (line,), _, _ = products.rows(products.Filters())

    assert sum(row["quantity"] for row in rows) == line["quantity"]
    assert sum(row["revenue_kopecks"] for row in rows) == line["revenue_kopecks"]


def test_shipment_without_a_channel_is_not_dropped(make_product, make_demand, channel):
    """Отгрузка без канала остаётся видимой отдельной строкой.

    Выбросить её значит потерять штуки, которые в итоге строки посчитаны, —
    и разбивка перестанет сходиться.
    """
    product = make_product()
    position(make_demand(channel=channel), product, "5.000", 50000)
    position(make_demand(), product, "2.000", 20000)

    rows = product_detail.channels(products.Filters(), product.id)

    assert [row["name"] for row in rows] == ["Озон", "Без канала"]
    assert sum(row["quantity"] for row in rows) == Decimal("7.000")


def test_channels_respect_the_period(make_product, make_demand, channel, make_channel):
    """Детали объясняют ту строку, которую видно, — с теми же фильтрами."""
    product = make_product()
    position(make_demand(moment=moscow(2026, 6, 15), channel=channel), product, "5.000", 50000)
    position(
        make_demand(moment=moscow(2026, 1, 15), channel=make_channel("Яндекс")),
        product, "9.000", 90000,
    )

    rows = product_detail.channels(
        products.Filters(date_from=date(2026, 6, 1), date_to=date(2026, 6, 30)), product.id
    )

    assert [row["name"] for row in rows] == ["Озон"]


def test_documents_are_newest_first(make_product, make_demand):
    """Сначала последние: вопрос к списку — «кому продали недавно»."""
    product = make_product()
    position(make_demand(moment=moscow(2026, 6, 1)), product, "1.000", 10000)
    position(make_demand(moment=moscow(2026, 6, 20)), product, "1.000", 10000)

    rows = product_detail.documents(products.Filters(), product.id)

    assert [row["moment"].date() for row in rows] == [date(2026, 6, 20), date(2026, 6, 1)]


def test_documents_are_capped(make_product, make_demand):
    """Тысяча строк в выдвижной панели не отвечает ни на один вопрос."""
    product = make_product()
    for day in range(1, product_detail.DOCUMENT_LIMIT + 5):
        position(make_demand(moment=moscow(2026, 6, day)), product, "1.000", 10000)

    rows = product_detail.documents(products.Filters(), product.id)

    assert len(rows) == product_detail.DOCUMENT_LIMIT


def test_stock_ignores_the_period(make_product, make_demand):
    """Остаток — это «сегодня», а не «за апрель»."""
    product = make_product()
    position(make_demand(moment=moscow(2026, 6, 15)), product, "1.000", 10000)
    Stock.objects.create(
        product=product, quantity=Decimal("12.000"), reserved=Decimal("2.000"), stock_days=7
    )

    row = product_detail.stock(product.id)

    assert row["quantity"] == Decimal("12.000")
    assert row["available"] == Decimal("10.000")
    assert row["stock_days"] == 7


def test_stock_is_none_when_unknown(make_product, make_demand):
    """Ноль читался бы как «кончился». Остатка просто нет в отчёте."""
    product = make_product()
    position(make_demand(), product, "1.000", 10000)

    assert product_detail.stock(product.id) is None


def test_detail_refuses_a_product_outside_the_selection(make_product, make_demand, channel):
    """Товар не в выборке — 404, а не пустые блоки.

    Пустая разбивка читалась бы как «продаж не было», хотя на деле запрос
    просто не про эту выборку.
    """
    product = make_product()
    position(make_demand(channel=channel), product, "1.000", 10000)

    with pytest.raises(product_detail.ProductNotSold):
        product_detail.detail(
            products.Filters(date_from=date(2020, 1, 1), date_to=date(2020, 12, 31)),
            product.id,
        )


def test_detail_endpoint_requires_the_page(client, make_user, make_product, make_demand):
    product = make_product()
    position(make_demand(), product, "1.000", 10000)
    client.force_login(make_user(pages=["deadlines"]))

    assert client.get(f"/api/shipments/products/{product.id}/").status_code == 403


def test_detail_endpoint_returns_the_breakdown(
    client, make_user, make_product, make_demand, channel
):
    product = make_product()
    position(make_demand(channel=channel), product, "3.000", 30000)
    client.force_login(make_user(pages=[PAGE_KEY]))

    body = client.get(f"/api/shipments/products/{product.id}/").json()

    assert [row["name"] for row in body["channels"]] == ["Озон"]
    assert body["documents"][0]["agent"] == "Покупатель"
    assert body["stock"] is None


def test_detail_endpoint_answers_404_outside_the_selection(
    client, make_user, make_product, make_demand
):
    product = make_product()
    position(make_demand(moment=moscow(2026, 6, 15)), product, "1.000", 10000)
    client.force_login(make_user(pages=[PAGE_KEY]))

    response = client.get(
        f"/api/shipments/products/{product.id}/",
        {"date_from": "2020-01-01", "date_to": "2020-12-31"},
    )

    assert response.status_code == 404
