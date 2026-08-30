"""Поставщики: доступ к разделу, разбор запроса, контракт ответа.

Контракт проверяется через API, а не через сервис. Причина в дефекте
соседней страницы: доля больше единицы не влезала в `DecimalField(9, 8)`,
и весь ответ уходил пятисотой — падала сериализация, которой тест
на сервисе не видит вовсе.
"""

import pytest

from api.suppliers.serializers import SuppliersQuerySerializer
from tests.suppliers.conftest import moscow, position

pytestmark = pytest.mark.django_db

PAGE_KEY = "suppliers"
URL = "/api/suppliers/"


@pytest.fixture
def stocked(make_supply, make_product, make_supplier):
    other = make_supplier("Принтец")
    first = make_supply(moment=moscow(2026, 4, 1), total_kopecks=600_000, lead_days=8)
    position(first, make_product("Отдушка"), 1000, "600")
    second = make_supply(moment=moscow(2026, 4, 20), total_kopecks=400_000, lead_days=2)
    position(second, make_product("Диметикон"), 2000, "200")
    third = make_supply(moment=moscow(2026, 4, 10), agent=other, total_kopecks=100_000)
    position(third, make_product("Этикетка"), 100, "1000")
    return first


class TestAccess:
    def test_requires_login(self, client):
        assert client.get(URL).status_code == 401

    def test_requires_this_page(self, client, make_user):
        """Права соседнего раздела не открывают этот. Проверяется именно
        приёмками: «Материалы в приёмках» считают по тем же документам,
        и перепутать ключ в реестре легко."""
        client.force_login(make_user(pages=["supplies-materials"]))
        assert client.get(URL).status_code == 403

    def test_allows_granted_user(self, client, make_user):
        client.force_login(make_user(pages=[PAGE_KEY]))
        assert client.get(URL).status_code == 200

    def test_export_requires_this_page(self, client, make_user):
        client.force_login(make_user(pages=["supplies-materials"]))
        assert client.get(f"{URL}xlsx/").status_code == 403


class TestQuery:
    @pytest.fixture(autouse=True)
    def logged_in(self, client, make_user):
        client.force_login(make_user(pages=[PAGE_KEY]))

    def test_rejects_reversed_period(self, client):
        """Начало периода позже конца — ошибка ввода, а не пустой список."""
        response = client.get(URL, {"date_from": "2026-07-01", "date_to": "2026-06-01"})
        assert response.status_code == 400

    def test_caps_page_size(self, client):
        """Ответ на `?page_size=10000` должен сказать, что столько не отдаём,
        а не обрезать молча: иначе человек решит, что строк действительно
        двести."""
        assert client.get(URL, {"page_size": 10_000}).status_code == 400

    def test_rejects_unknown_ordering(self, client):
        """Сортировка попадает в код напрямую — список закрытый."""
        assert client.get(URL, {"ordering": "; drop"}).status_code == 400

    def test_has_no_picker_in_the_contract(self, client, stocked):
        """Справочника для сужения здесь нет: поставщик и есть строка таблицы,
        и фильтр по нему оставил бы в ней ровно одну.

        Проверяется контракт, а не отказ на лишний параметр: лишние параметры
        игнорируют все страницы проекта, и одна строгая посреди девяти
        нестрогих — непоследовательность, которая хуже самой проблемы.
        Важно другое: чтобы `supplier_id` не оказался приделан незаметно.
        """
        fields = SuppliersQuerySerializer().fields

        assert "supplier_id" not in fields
        assert "channel_id" not in fields

        whole = client.get(URL).json()
        assert client.get(URL, {"supplier_id": 1}).json() == whole


class TestContract:
    @pytest.fixture(autouse=True)
    def logged_in(self, client, make_user):
        client.force_login(make_user(pages=[PAGE_KEY]))

    def test_row_carries_what_the_explanation_needs(self, client, stocked):
        """Формула собирается фронтом из полученного, а не пересчитывается.
        Значит медиана обязана приходить вместе с разбросом и знаменателем."""
        row = client.get(URL).json()["results"][0]

        assert row["regularity"]["days"] == "19.0"
        assert row["regularity"]["measurements"] == 1
        assert (row["regularity"]["min_days"], row["regularity"]["max_days"]) == (19, 19)
        assert row["lead_time"]["days"] == "5.0"
        assert row["lead_time"]["measurements"] == 2
        assert row["lead_time"]["unlinked"] == 0

    def test_zero_lead_time_is_not_null(self, client, stocked):
        """У «Принтеца» заказ и приёмка одним днём — у него забирают.
        Ноль здесь ответ, а `null` был бы ложью про половину закупок."""
        rows = {row["name"]: row for row in client.get(URL).json()["results"]}

        assert rows["Принтец"]["lead_time"]["days"] == "0.0"

    def test_single_delivery_has_no_regularity(self, client, stocked):
        """А вот промежутка между поставками у него нет вовсе — там `null`."""
        rows = {row["name"]: row for row in client.get(URL).json()["results"]}

        assert rows["Принтец"]["regularity"]["days"] is None
        assert rows["Принтец"]["regularity"]["measurements"] == 0

    def test_both_totals_are_served(self, client, stocked):
        """Два набора, а не один: итог про таблицу, сводка про выборку."""
        payload = client.get(URL).json()

        assert payload["totals"]["suppliers_count"] == 2
        assert payload["coverage"]["supplies_count"] == 3
        assert payload["coverage"]["free_positions_count"] == 0

    def test_freshness_is_served(self, client, stocked):
        """«Данные на 14:32» показывают все десять страниц."""
        assert "synced_at" in client.get(URL).json()

    def test_large_share_does_not_break_serialization(
        self, client, make_supply, make_supplier
    ):
        """Разрядность доли с запасом: на соседней странице `DecimalField(9, 8)`
        не вместил 4080 %, и весь ответ уходил пятисотой. Здесь доля больше
        единицы невозможна — но проверяется через API, а не через сервис:
        падает сериализация, и тест на сервисе этого не видит.
        """
        make_supply(agent=make_supplier("Один"), total_kopecks=1)
        make_supply(agent=make_supplier("Другой"), total_kopecks=999_999_999)

        assert client.get(URL).status_code == 200


class TestExport:
    @pytest.fixture(autouse=True)
    def logged_in(self, client, make_user):
        client.force_login(make_user(pages=[PAGE_KEY]))

    def test_serves_a_workbook(self, client, stocked):
        response = client.get(f"{URL}xlsx/")

        assert response.status_code == 200
        assert response["Content-Type"].endswith("spreadsheetml.sheet")

    def test_file_name_carries_the_period(self, client, stocked):
        """Две выборки за разные периоды, скачанные в один день, иначе
        получили бы одинаковое имя."""
        response = client.get(
            f"{URL}xlsx/", {"date_from": "2026-04-01", "date_to": "2026-04-30"}
        )

        assert "01.04.2026" in response["Content-Disposition"]
