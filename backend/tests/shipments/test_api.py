"""Товары в отгрузках: доступ к разделу и разбор запроса."""

from decimal import Decimal

import pytest

from api.shipments.services import products
from tests.shipments.conftest import position

pytestmark = pytest.mark.django_db

PAGE_KEY = "shipments-products"
URL = "/api/shipments/products/"


# --- Итоги -------------------------------------------------------------------


def test_totals_cover_the_whole_selection_not_the_page(make_product, make_demand):
    """Итог в подвале считается по выборке целиком, а не по видимой странице."""
    for index in range(5):
        position(make_demand(), make_product(code=f"2-{index:03d}"), "2.000", 10000)

    totals = products.summary(products.Filters(page=1, page_size=2))

    assert totals["products_count"] == 5
    assert totals["quantity"] == Decimal("10.000")
    assert totals["revenue_kopecks"] == 50000


def test_documents_are_counted_once_per_document(make_product, make_demand):
    """Две позиции одного документа — это одна отгрузка, а не две."""
    document = make_demand()
    product = make_product()
    position(document, product, "1.000", 10000)
    position(document, make_product(code="2-002"), "1.000", 10000)

    totals = products.summary(products.Filters())

    assert totals["documents_count"] == 1

# --- Доступ ------------------------------------------------------------------


def test_endpoint_requires_login(client):
    assert client.get(URL).status_code == 401


def test_endpoint_requires_the_page(client, make_user):
    """Доступ к соседнему разделу не открывает этот."""
    client.force_login(make_user(pages=["deadlines"]))

    assert client.get(URL).status_code == 403


def test_endpoint_allows_granted_user(client, make_user):
    client.force_login(make_user(pages=[PAGE_KEY]))

    assert client.get(URL).status_code == 200


def test_endpoint_rejects_reversed_period(client, make_user):
    """Начало периода позже конца — ошибка ввода, а не пустой список."""
    client.force_login(make_user(pages=[PAGE_KEY]))

    response = client.get(URL, {"date_from": "2026-07-01", "date_to": "2026-06-01"})

    assert response.status_code == 400


def test_endpoint_caps_page_size(client, make_user):
    """Запрос на десять тысяч строк не должен уводить базу в долгий скан."""
    client.force_login(make_user(pages=[PAGE_KEY]))

    response = client.get(URL, {"page_size": 10_000})

    assert response.status_code == 400
