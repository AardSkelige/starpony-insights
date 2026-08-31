"""Каналы продаж: доступ к разделу, разбор запроса, контракт ответа.

Контракт проверяется через API, а не через сервис. Причина — дефект
соседней страницы: доля больше единицы не влезала в `DecimalField(9, 8)`,
и весь ответ уходил пятисотой. Падала сериализация, которой тест
на сервисе не видит вовсе.
"""

import pytest

from tests.channels.conftest import moscow, position

pytestmark = pytest.mark.django_db

PAGE_KEY = "channels"
URL = "/api/channels/"


@pytest.fixture
def sold(make_channel, make_demand, make_buyer, make_product):
    goods = make_product("Репеллент 500 мл")
    market = make_channel("Маркет")

    first = make_demand(moment=moscow(2026, 5, 4), total_kopecks=500_000)
    position(first, goods, 1, 500_000)
    second = make_demand(
        sales_channel=market, moment=moscow(2026, 5, 6), total_kopecks=50_000
    )
    position(second, goods, 1, 50_000)
    # Отгрузка без канала: в таблицу не попадает, в сводке остаётся.
    make_demand(sales_channel=None, moment=moscow(2026, 5, 7), total_kopecks=0)
    return first


class TestAccess:
    def test_requires_login(self, client):
        assert client.get(URL).status_code == 401

    def test_requires_this_page(self, client, make_user):
        """Права соседнего раздела не открывают этот. Проверяется именно
        отгрузками: «Товары в отгрузках» считают по тем же документам,
        и перепутать ключ в реестре легко."""
        client.force_login(make_user(pages=["shipments-products"]))
        assert client.get(URL).status_code == 403

    def test_allows_granted_user(self, client, make_user):
        client.force_login(make_user(pages=[PAGE_KEY]))
        assert client.get(URL).status_code == 200

    def test_export_requires_this_page(self, client, make_user):
        client.force_login(make_user(pages=["shipments-products"]))
        assert client.get(f"{URL}xlsx/").status_code == 403


class TestQuery:
    @pytest.fixture(autouse=True)
    def logged_in(self, client, make_user):
        client.force_login(make_user(pages=[PAGE_KEY]))

    def test_rejects_reversed_period(self, client):
        """Начало периода позже конца — ошибка ввода, а не пустой список."""
        response = client.get(URL, {"date_from": "2026-07-01", "date_to": "2026-06-01"})
        assert response.status_code == 400

    def test_rejects_unknown_ordering(self, client):
        """Список сортировок закрытый: неизвестный ключ — четырёхсотая,
        а не молчаливая сортировка по умолчанию."""
        response = client.get(URL, {"ordering": "revenue; drop"})
        assert response.status_code == 400

    def test_rejects_oversized_page(self, client):
        """Ответ на `?page_size=1000` обязан сказать, что столько не отдаём:
        обрежь мы молча, человек решит, что строк действительно двести."""
        assert client.get(URL, {"page_size": 1000}).status_code == 400


class TestPayload:
    @pytest.fixture(autouse=True)
    def logged_in(self, client, make_user):
        client.force_login(make_user(pages=[PAGE_KEY]))

    def test_row_carries_the_cheque_with_its_parts(self, client, sold):
        """Расчётное число уходит составляющими: страница обязана показать
        формулу по наведению и собрать её из полученного, а не пересчитать."""
        body = client.get(URL).json()
        row = body["results"][0]

        assert row["name"] == "Озон"
        assert row["revenue_kopecks"] == 500_000
        assert row["receipt"]["kopecks"] == 500_000
        assert row["receipt"]["shipments"] == 1
        assert row["receipt"]["min_kopecks"] == 500_000
        assert row["receipt"]["average_kopecks"] == 500_000

    def test_totals_and_coverage_are_about_different_sets(self, client, sold):
        """Итог таблицы — про показанное, сводка — про выборку целиком
        вместе с отгрузкой без канала."""
        body = client.get(URL).json()

        assert body["totals"]["shipments_count"] == 2
        assert body["coverage"]["shipments_count"] == 3
        assert body["coverage"]["unassigned_shipments_count"] == 1

    def test_dynamics_series_and_points_line_up(self, client, sold):
        """Столбик обязан нести столько же чисел, сколько серий, и в том же
        порядке: иначе слагаемые лягут не под свои цвета."""
        body = client.get(URL).json()
        line = body["dynamics"]

        assert line["step_label"]
        assert all(
            len(point["values"]) == len(line["series"]) for point in line["points"]
        )
        assert sum(sum(point["values"]) for point in line["points"]) == 550_000

    def test_search_keeps_the_denominator(self, client, sold):
        """Поиск сужает строки, но не то, от чего считается доля."""
        body = client.get(URL, {"search": "маркет"}).json()

        assert body["count"] == 1
        assert body["results"][0]["revenue_share"] == "0.09090909"

    def test_export_returns_a_workbook(self, client, sold):
        response = client.get(f"{URL}xlsx/")

        from urllib.parse import unquote

        assert response.status_code == 200
        assert response["Content-Type"].endswith("spreadsheetml.sheet")
        # Имя уезжает в заголовок процентным кодированием — русские буквы
        # в HTTP-заголовке иначе не живут.
        assert "Каналы продаж" in unquote(response["Content-Disposition"])
