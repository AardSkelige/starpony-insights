"""Материалы в отгрузках: доступ к разделу, разбор запроса, контракт ответа."""

import pytest

from tests.shipments.conftest import position

pytestmark = pytest.mark.django_db

PAGE_KEY = "shipments-materials"
URL = "/api/shipments/materials/"


@pytest.fixture
def shampoo(make_product, make_plan, make_demand):
    bottled = make_product("Шампунь 500 мл", article="100.001", code="2-001")
    water = make_product("Вода дистиллированная", article="W-1", code="9-001")
    make_plan("Розлив", bottled, output=1, materials=[(water, 50)])
    position(make_demand(), bottled, "10", 500_00)
    return {"bottled": bottled, "water": water}


class TestAccess:
    def test_requires_login(self, client):
        assert client.get(URL).status_code == 401

    def test_requires_this_page(self, client, make_user):
        """Доступ к соседнему разделу не открывает этот.

        Префикс `/api/shipments/products/` длиннее `/api/shipments/`,
        и права одной страницы не должны протекать на другую.
        """
        client.force_login(make_user(pages=["shipments-products"]))
        assert client.get(URL).status_code == 403

    def test_allows_granted_user(self, client, make_user):
        client.force_login(make_user(pages=[PAGE_KEY]))
        assert client.get(URL).status_code == 200

    def test_detail_requires_this_page(self, client, make_user, shampoo):
        client.force_login(make_user(pages=["shipments-products"]))
        assert client.get(f"{URL}{shampoo['water'].pk}/").status_code == 403

    def test_export_requires_this_page(self, client, make_user):
        client.force_login(make_user(pages=["shipments-products"]))
        assert client.get(f"{URL}xlsx/").status_code == 403


class TestQuery:
    def test_rejects_reversed_period(self, client, make_user):
        """Начало периода позже конца — ошибка ввода, а не пустой список."""
        client.force_login(make_user(pages=[PAGE_KEY]))
        response = client.get(URL, {"date_from": "2026-07-01", "date_to": "2026-06-01"})
        assert response.status_code == 400

    def test_caps_page_size(self, client, make_user):
        client.force_login(make_user(pages=[PAGE_KEY]))
        assert client.get(URL, {"page_size": 10_000}).status_code == 400

    def test_rejects_unknown_ordering(self, client, make_user):
        """Сортировка попадает в код напрямую — список закрытый."""
        client.force_login(make_user(pages=[PAGE_KEY]))
        assert client.get(URL, {"ordering": "cost; drop table"}).status_code == 400


class TestPayload:
    def test_answer_carries_everything_the_page_needs(self, client, make_user, shampoo):
        """Одним запросом: строки, итоги, каналы, свежесть и блок без техкарт."""
        client.force_login(make_user(pages=[PAGE_KEY]))
        payload = client.get(URL).json()

        assert set(payload) == {
            "synced_at",
            "count",
            # Два набора чисел, а не один: подвал таблицы про найденное,
            # сводка — про выборку отгрузок. Слить их значит показать дробь
            # с числителем от одного множества и знаменателем от другого.
            "totals",
            "coverage",
            "results",
            "without_plan",
            "channels",
        }
        assert payload["results"][0]["name"] == "Вода дистиллированная"

    def test_numbers_come_with_their_parts(self, client, make_user, shampoo, make_supply):
        """Стоимость приходит вместе с ценой и датой, из которых получена."""
        make_supply(shampoo["water"], "2.50")
        client.force_login(make_user(pages=[PAGE_KEY]))

        row = client.get(URL).json()["results"][0]
        assert row["price_kopecks"] == "2.500000"
        assert row["price_moment"] is not None
        assert row["cost_kopecks"] == 1250

    def test_detail_explains_with_paths(self, client, make_user, shampoo):
        client.force_login(make_user(pages=[PAGE_KEY]))
        payload = client.get(f"{URL}{shampoo['water'].pk}/").json()

        assert payload["material"]["name"] == "Вода дистиллированная"
        assert payload["sources"][0]["paths"][0]["chain"] == ["Розлив"]

    def test_detail_of_absent_material_is_404(self, client, make_user, shampoo, make_product):
        client.force_login(make_user(pages=[PAGE_KEY]))
        stranger = make_product("Не при делах", article="", code="")
        assert client.get(f"{URL}{stranger.pk}/").status_code == 404


class TestExtremeShare:
    """Сырья может уйти больше, чем принесла выручка, — и это не ошибка.

    На боевых данных так вышло 6 июля 2026: выручка 7,13 ₽ против сырья
    на 290,91 ₽, потому что товар отгрузили почти даром. Доля 4080%.
    """

    def test_share_above_ten_does_not_break_the_answer(
        self, client, make_user, make_product, make_plan, make_demand, make_supply
    ):
        """Проверяется через API, а не через сервис: падал сериализатор.

        `DecimalField(max_digits=9, decimal_places=8)` вмещает только числа
        меньше десяти, и на 40.8 весь ответ уходил пятисотой — вся страница,
        а не одна ячейка.
        """
        bottled = make_product("Шампунь 500 мл", article="100.001", code="2-001")
        water = make_product("Вода", article="W-1", code="9-001")
        make_plan("Розлив", bottled, output=1, materials=[(water, 50)])
        make_supply(water, "100")

        # Отгрузка за копейку: выручка мизерная, сырьё потрачено полностью —
        # ровно то, что даёт день с образцами и заменами брака.
        position(make_demand(), bottled, "10", 1)

        client.force_login(make_user(pages=[PAGE_KEY]))
        response = client.get(URL)

        assert response.status_code == 200, "ответ упал на большой доле"
        share = float(response.json()["coverage"]["cost_share_of_revenue"])
        assert share > 10, f"сценарий не воспроизвёлся: доля {share}"
