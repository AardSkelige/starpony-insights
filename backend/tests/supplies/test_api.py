"""Материалы в приёмках: доступ к разделу, разбор запроса, контракт ответа."""

import pytest

from tests.supplies.conftest import moscow, position

pytestmark = pytest.mark.django_db

PAGE_KEY = "supplies-materials"
URL = "/api/supplies/materials/"


@pytest.fixture
def bottle(make_supply, make_product):
    material = make_product("Флакон 500 мл", article="2.001", code="2-001")
    position(make_supply(moment=moscow(2026, 4, 19)), material, 1000, "2505")
    return material


class TestAccess:
    def test_requires_login(self, client):
        assert client.get(URL).status_code == 401

    def test_requires_this_page(self, client, make_user):
        """Права соседнего раздела не открывают этот.

        Проверяется именно приёмками: «Материалы в отгрузках» называются
        почти так же, и перепутать ключ в реестре легко.
        """
        client.force_login(make_user(pages=["shipments-materials"]))
        assert client.get(URL).status_code == 403

    def test_allows_granted_user(self, client, make_user):
        client.force_login(make_user(pages=[PAGE_KEY]))
        assert client.get(URL).status_code == 200

    def test_detail_requires_this_page(self, client, make_user, bottle):
        client.force_login(make_user(pages=["shipments-materials"]))
        assert client.get(f"{URL}{bottle.pk}/").status_code == 403

    def test_export_requires_this_page(self, client, make_user):
        client.force_login(make_user(pages=["shipments-materials"]))
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
        assert client.get(URL, {"page_size": 10_000}).status_code == 400

    def test_rejects_unknown_ordering(self, client):
        """Сортировка попадает в код напрямую — список закрытый."""
        assert client.get(URL, {"ordering": "revenue"}).status_code == 400

    def test_rejects_channel_of_the_neighbouring_page(self, client):
        """У приёмки нет канала продаж, и вид, что он принят, — обман.

        Ссылка «приёмки по Озону» открывалась бы полным списком, выглядя
        отфильтрованной.
        """
        response = client.get(URL, {"channel_id": 1})
        assert response.status_code == 200
        assert "channels" not in response.json()

    def test_accepts_the_whole_ordering_list(self, client, bottle):
        from api.supplies.services.materials import ORDERING

        for ordering in ORDERING:
            assert client.get(URL, {"ordering": ordering}).status_code == 200


class TestPayload:
    @pytest.fixture(autouse=True)
    def logged_in(self, client, make_user):
        client.force_login(make_user(pages=[PAGE_KEY]))

    def test_carries_suppliers_for_the_filter(self, client, bottle):
        """Список поставщиков приезжает со страницей, а не отдельной ручкой.

        Двадцать два значения не стоят своей строки в реестре прав.
        """
        payload = client.get(URL).json()
        assert [item["name"] for item in payload["suppliers"]] == ["ООО «Лемун»"]

    def test_row_carries_the_parts_of_its_numbers(self, client, bottle):
        """Формула собирается из полученного, а не пересчитывается фронтом."""
        row = client.get(URL).json()["results"][0]
        for key in (
            "quantity",
            "free_quantity",
            "paid_quantity",
            "amount_kopecks",
            "avg_price_kopecks",
            "last_price_kopecks",
            "last_moment",
            "last_document_number",
            "last_supplier",
            "previous_price_kopecks",
            "price_change",
        ):
            assert key in row

    def test_detail_answers_404_outside_the_selection(self, client, bottle):
        response = client.get(f"{URL}{bottle.pk}/", {"date_from": "2026-07-01"})
        assert response.status_code == 404

    def test_export_is_an_xlsx_attachment(self, client, bottle):
        """Имя файла говорит, что внутри, и уезжает в percent-кодировке.

        Тип задаётся явно: поток в памяти имени не имеет, и без этого книга
        уходит как `application/octet-stream`, который Excel не открывает.
        """
        from urllib.parse import unquote

        response = client.get(f"{URL}xlsx/")
        assert response.status_code == 200
        assert "Материалы в приёмках" in unquote(response["Content-Disposition"])
        assert response["Content-Type"].endswith("spreadsheetml.sheet")


class TestWideNumbers:
    """Поля обязаны вмещать то, что бывает в учёте, а не то, что ожидалось.

    На соседней странице `DecimalField(9, 8)` уронил весь ответ пятисотой
    на дне, где доля вышла 4080%: поле в девять знаков вмещает только числа
    меньше десяти. Здесь такие числа тоже бывают — лауроилглутамат подорожал
    на 278% за две закупки, а этикетка у другой типографии стоила в 4,5 раза
    дороже.
    """

    @pytest.fixture(autouse=True)
    def logged_in(self, client, make_user):
        client.force_login(make_user(pages=[PAGE_KEY]))

    def test_fiftyfold_price_growth_survives(self, client, make_supply, make_product):
        material = make_product("Соль пищевая")
        position(make_supply(moment=moscow(2026, 3, 17)), material, 1000, "4")
        position(make_supply(moment=moscow(2026, 8, 2)), material, 1000, "200")

        row = client.get(URL).json()["results"][0]
        assert float(row["price_change"]) == pytest.approx(49.0)

    def test_wide_spread_between_suppliers_survives(
        self, client, make_supply, make_product, make_supplier
    ):
        material = make_product("Этикетка")
        position(
            make_supply(agent=make_supplier("Принтец")), material, 100, "1428.57"
        )
        position(
            make_supply(agent=make_supplier("ООО «Типография»")), material, 100, "641250"
        )

        payload = client.get(f"{URL}{material.pk}/").json()
        assert float(payload["suppliers"][1]["above_best"]) == pytest.approx(447.9, abs=0.1)
