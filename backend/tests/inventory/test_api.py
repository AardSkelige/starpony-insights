"""Инвентаризация: доступ к разделу, разбор запроса, контракт ответа.

Контракт проверяется через API, а не через сервис: падение сериализации
тест на сервисе не видит вовсе, а ответ при этом уходит пятисотой.
"""

import pytest

from tests.inventory.conftest import moscow

pytestmark = pytest.mark.django_db

PAGE_KEY = "inventory"
URL = "/api/inventory/"


@pytest.fixture
def counted(make_product, make_inventory, count_position):
    inventory = make_inventory(moscow(2026, 8, 6), store="Хоз товары")
    count_position(inventory, make_product("Короб", folder="Хоз. товары/Упаковка",
                                           cost="1789.400000"),
                   calculated="10.000", counted="7.000")
    make_product("Масло макадамии", folder="Производство/Сырьё")
    return inventory


class TestAccess:
    def test_requires_login(self, client):
        assert client.get(URL).status_code == 401

    def test_requires_this_page(self, client, make_user):
        client.force_login(make_user(pages=["suppliers"]))
        assert client.get(URL).status_code == 403

    def test_allows_granted_user(self, client, make_user):
        client.force_login(make_user(pages=[PAGE_KEY]))
        assert client.get(URL).status_code == 200


class TestContract:
    def test_answers_both_questions_at_once(self, client, make_user, counted):
        """Оба вопроса страницы приходят одним ответом: блоки под таблицей
        не должны стоить второго запроса — их четыре."""
        client.force_login(make_user(pages=[PAGE_KEY]))

        body = client.get(URL).json()

        assert body["count"] == 2
        assert body["coverage"]["never_counted_count"] == 1
        assert body["worst"]["money_kopecks"] == -5368
        assert body["documents"]["count"] == 1
        assert body["stores"] == [{"id": 1, "name": "Хоз товары"}]
        # Папки — по всей номенклатуре, включая ту, где не считали ни разу:
        # иначе «Производство/Сырьё» нельзя было бы выбрать в фильтре.
        assert body["folders"] == ["Производство/Сырьё", "Хоз. товары/Упаковка"]

    def test_row_carries_its_formula(self, client, make_user, counted):
        """Расчётное число уходит с составляющими — иначе на экране нечем
        показать формулу (`CLAUDE.md` §4)."""
        client.force_login(make_user(pages=[PAGE_KEY]))

        row = client.get(f"{URL}?ordering=-money").json()["results"][0]

        assert row["correction"] == "-3.000"
        assert row["cost_kopecks"] == "1789.400000"
        assert row["correction_money_kopecks"] == -5368

    def test_rejects_unknown_ordering(self, client, make_user):
        client.force_login(make_user(pages=[PAGE_KEY]))

        assert client.get(f"{URL}?ordering=whatever").status_code == 400

    def test_rejects_too_big_page(self, client, make_user):
        client.force_login(make_user(pages=[PAGE_KEY]))

        assert client.get(f"{URL}?page_size=1000").status_code == 400

    def test_xlsx_is_a_file(self, client, make_user, counted):
        client.force_login(make_user(pages=[PAGE_KEY]))

        response = client.get(f"{URL}xlsx/")

        assert response.status_code == 200
        assert response["Content-Type"].startswith("application/vnd.openxmlformats")
