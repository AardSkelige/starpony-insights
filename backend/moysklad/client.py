"""HTTP-клиент к API МойСклад.

Единственное место в проекте, которое ходит в чужой API. Ни один view сюда
не обращается: данные для страниц берутся из Postgres, а этот клиент работает
только в синхронизациях и обратной записи, по расписанию или по кнопке.

Лимит запросов общий с ботом Agent - StarPony — см. `limits.py`.
"""

import logging
import time
from typing import Any, Iterator
from urllib.parse import urlencode

import requests

from moysklad.limits import ApiDisabledRisk, CircuitBreaker, RateLimiter

logger = logging.getLogger(__name__)

BASE_URL = "https://api.moysklad.ru/api/remap/1.2"

# Сколько объектов просить за раз. Максимум API — 1000, но большие страницы
# дают заметно более долгий ответ и чаще рвутся на медленной сети.
PAGE_SIZE = 100

# Повторяем только то, что имеет шанс пройти со второй попытки.
RETRIABLE_STATUSES = frozenset({429, 500, 502, 503, 504})


class MoySkladError(RuntimeError):
    """Запрос к МойСкладу не удался."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class MoySkladClient:
    """Вежливый клиент: читает остаток лимита и останавливается при серии ошибок."""

    def __init__(
        self,
        token: str,
        *,
        base_url: str = BASE_URL,
        timeout: float = 60.0,
        max_attempts: int = 3,
        session: requests.Session | None = None,
        sleep=time.sleep,
    ):
        if not token:
            raise ValueError("Токен МойСклада обязателен")

        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_attempts = max_attempts
        self._sleep = sleep
        self._limiter = RateLimiter()
        self._breaker = CircuitBreaker()
        self.request_count = 0

        self._session = session or requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/json;charset=utf-8",
            "Content-Type": "application/json",
            # Без gzip API отвечает 415 — сжатие обязательно, а не желательно.
            "Accept-Encoding": "gzip",
        })

    def get(self, path: str, params: dict | list | None = None) -> dict:
        return self._request("GET", path, params=params)

    def put(self, path: str, payload: dict) -> dict:
        return self._request("PUT", path, json=payload)

    def iterate(self, path: str, params: dict | None = None) -> Iterator[dict]:
        """Все строки коллекции, страница за страницей.

        Генератор, а не список: полная выгрузка документов не должна лежать
        в памяти целиком, а вызывающий код всё равно обрабатывает построчно.
        """
        offset = 0
        # `limit` вызывающего — размер страницы обхода, а не потолок вложенных
        # коллекций: перетирать его молча значит однажды получить обрезанные
        # позиции документов и не понять почему.
        page_size = int((params or {}).get("limit") or PAGE_SIZE)

        while True:
            page_params = dict(params or {})
            page_params.update({"limit": page_size, "offset": offset})

            payload = self.get(path, page_params)
            rows = payload.get("rows", [])
            yield from rows

            meta = payload.get("meta", {})
            size = meta.get("size")
            offset += len(rows)

            # Останавливаемся и по признаку сервера, и по пустой странице:
            # без второго условия сбой в `size` даёт бесконечный цикл,
            # то есть ровно ту серию запросов, за которую отключают доступ.
            if not rows or (size is not None and offset >= size):
                return

    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = path if path.startswith("http") else f"{self._base_url}{path}"
        params = kwargs.pop("params", None)
        if params:
            # Список кортежей — для повторяющихся ключей: у МойСклада два
            # условия отбора передаются двумя параметрами `filter`, а не через
            # разделитель внутри одного.
            url = f"{url}?{urlencode(params, doseq=True)}"

        last_error: Exception | None = None

        for attempt in range(1, self._max_attempts + 1):
            self._sleep(self._limiter.delay_before_next())

            try:
                response = self._session.request(
                    method, url, timeout=self._timeout, **kwargs
                )
            except requests.RequestException as error:
                # Сеть оборвалась — сервер об этом не знает, для его счётчика
                # ошибок такого запроса не было. Предохранитель не трогаем.
                last_error = error
                logger.warning("Обрыв связи с МойСкладом (%s), попытка %s", error, attempt)
                if attempt == self._max_attempts:
                    raise MoySkladError(f"Нет связи с МойСкладом: {error}") from error
                self._sleep(2 ** attempt)
                continue

            self.request_count += 1
            self._limiter.observe(response.headers)

            if response.ok:
                self._breaker.record_success()
                return response.json() if response.content else {}

            self._breaker.record_error(response.status_code)

            if response.status_code in RETRIABLE_STATUSES and attempt < self._max_attempts:
                pause = (
                    self._limiter.retry_delay(response.headers)
                    if response.status_code == 429
                    else 2 ** attempt
                )
                logger.warning(
                    "МойСклад ответил %s на %s, повтор через %.1fс",
                    response.status_code, path, pause,
                )
                self._sleep(pause)
                continue

            raise MoySkladError(
                f"{method} {path} → {response.status_code}: {response.text[:200]}",
                status=response.status_code,
            )

        raise MoySkladError(f"{method} {path}: попытки исчерпаны ({last_error})")


__all__ = ["MoySkladClient", "MoySkladError", "ApiDisabledRisk", "BASE_URL"]
