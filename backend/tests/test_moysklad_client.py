"""Поведение клиента на ответах, которые в жизни встречаются редко,
но именно они решают, останемся ли мы с работающим API.

Ответы подменены: вызвать 429 или серию пятисоток на боевом аккаунте нельзя —
за это отключают доступ, а восстанавливают только через поддержку.
"""

import pytest
import requests
import responses

from moysklad.client import BASE_URL, MoySkladClient, MoySkladError
from moysklad.limits import ApiDisabledRisk


@pytest.fixture
def client():
    """Клиент без настоящих пауз: тесты проверяют логику, а не терпение."""
    return MoySkladClient(token="test-token", sleep=lambda _: None, max_attempts=3)


def limit_headers(remaining=45, retry_after=None):
    headers = {
        "X-RateLimit-Limit": "45",
        "X-RateLimit-Remaining": str(remaining),
        "X-Lognex-Retry-TimeInterval": "3000",
    }
    if retry_after is not None:
        headers["X-Lognex-Retry-After"] = str(retry_after)
    return headers


class TestRequests:
    @responses.activate
    def test_sends_required_headers(self, client):
        """gzip обязателен: без него API отвечает 415, а не отдаёт данные."""
        responses.get(f"{BASE_URL}/entity/product", json={"rows": []}, headers=limit_headers())

        client.get("/entity/product")

        sent = responses.calls[0].request.headers
        assert sent["Authorization"] == "Bearer test-token"
        assert "gzip" in sent["Accept-Encoding"]

    @responses.activate
    def test_repeated_filters_go_as_separate_params(self, client):
        """Два условия отбора — два параметра `filter`, а не один со склейкой."""
        responses.get(f"{BASE_URL}/entity/demand", json={"rows": []}, headers=limit_headers())

        client.get("/entity/demand", [("filter", "updated>=2026-01-01"), ("filter", "applicable=true")])

        assert responses.calls[0].request.url.count("filter=") == 2


class TestRetries:
    @responses.activate
    def test_retries_after_429(self, client):
        responses.get(f"{BASE_URL}/entity/product", status=429, headers=limit_headers(0, 500))
        responses.get(f"{BASE_URL}/entity/product", json={"rows": [{"id": "1"}]}, headers=limit_headers())

        assert client.get("/entity/product")["rows"] == [{"id": "1"}]
        assert len(responses.calls) == 2

    @responses.activate
    def test_gives_up_on_4xx(self, client):
        """Неверный запрос повторять бессмысленно: ответ не изменится,
        а счётчик ошибок на стороне МойСклада растёт."""
        responses.get(f"{BASE_URL}/entity/product", status=404, json={}, headers=limit_headers())

        with pytest.raises(MoySkladError) as error:
            client.get("/entity/product")

        assert error.value.status == 404
        assert len(responses.calls) == 1

    @responses.activate
    def test_network_failure_is_retried(self, client):
        """Обрыв связи сервер не видит — его счётчик ошибок не растёт."""
        responses.get(f"{BASE_URL}/entity/product", body=requests.ConnectionError("обрыв"))
        responses.get(f"{BASE_URL}/entity/product", json={"rows": []}, headers=limit_headers())

        assert client.get("/entity/product") == {"rows": []}


class TestCircuitBreaker:
    @responses.activate
    def test_stops_before_api_gets_disabled(self, client):
        """Серия 429 останавливает работу целиком.

        Иначе следующий шаг — автоматическое отключение доступа, и вместе
        с нами учёт теряет бот, то есть вся компания.
        """
        for _ in range(10):
            responses.get(f"{BASE_URL}/entity/product", status=429, headers=limit_headers(0, 100))

        with pytest.raises(ApiDisabledRisk, match="поддержк"):
            for _ in range(5):
                try:
                    client.get("/entity/product")
                except MoySkladError:
                    continue


class TestPagination:
    @responses.activate
    def test_walks_all_pages(self, client):
        responses.get(
            f"{BASE_URL}/entity/product",
            json={"rows": [{"id": str(i)} for i in range(100)], "meta": {"size": 150}},
            headers=limit_headers(),
        )
        responses.get(
            f"{BASE_URL}/entity/product",
            json={"rows": [{"id": str(i)} for i in range(100, 150)], "meta": {"size": 150}},
            headers=limit_headers(),
        )

        assert len(list(client.iterate("/entity/product"))) == 150

    @responses.activate
    def test_stops_on_empty_page_even_if_size_lies(self, client):
        """Защита от бесконечного цикла.

        Если `size` окажется больше, чем строк на самом деле, обход по одному
        лишь этому признаку никогда не кончится — а непрерывный поток запросов
        и есть то, за что отключают доступ.
        """
        responses.get(
            f"{BASE_URL}/entity/product",
            json={"rows": [{"id": "1"}], "meta": {"size": 99999}},
            headers=limit_headers(),
        )
        responses.get(
            f"{BASE_URL}/entity/product",
            json={"rows": [], "meta": {"size": 99999}},
            headers=limit_headers(),
        )

        assert len(list(client.iterate("/entity/product"))) == 1
