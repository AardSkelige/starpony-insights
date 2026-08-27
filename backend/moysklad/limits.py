"""Лимит запросов к МойСкладу и предохранитель.

Лимит общий с ботом Agent - StarPony: в аккаунте один пользователь, и корзина
у нас одна на двоих. Бот проверяет учёт круглосуточно, поэтому наша задача —
не выбрать корзину до дна, а не «успеть побольше».

Расчёт идёт по заголовкам ответа, а не по собственному счётчику окна. Вес
запроса растёт по расписанию (3 единицы с 1 сентября, 4 с 1 декабря 2026),
и клиент, считающий сам, придётся править к каждой дате.
"""

from dataclasses import dataclass

# Нижняя граница расписания: 11 запросов за 3 секунды. Пока заголовков нет —
# держим темп под неё, а не под текущий, более щедрый лимит.
FALLBACK_INTERVAL_SECONDS = 3.0 / 11

# Доля корзины, которую фоновая синхронизация может занимать. Остальное —
# запас боту, который работает круглосуточно и ждать не может.
BACKGROUND_SHARE = 0.7


@dataclass(frozen=True)
class LimitHeaders:
    """Что сказал сервер об остатке лимита. Любое поле может отсутствовать."""

    limit: int | None = None
    remaining: int | None = None
    interval_ms: int | None = None
    retry_after_ms: int | None = None

    @classmethod
    def parse(cls, headers) -> "LimitHeaders":
        def number(name: str) -> int | None:
            raw = headers.get(name)
            if raw is None:
                return None
            try:
                return int(float(raw))
            except (TypeError, ValueError):
                # Заголовок есть, но невнятный: считаем, что его нет, — это
                # безопаснее, чем гадать и выбрать корзину до дна.
                return None

        return cls(
            limit=number("X-RateLimit-Limit"),
            remaining=number("X-RateLimit-Remaining"),
            interval_ms=number("X-Lognex-Retry-TimeInterval"),
            retry_after_ms=number("X-Lognex-Retry-After"),
        )


class RateLimiter:
    """Сколько ждать перед следующим запросом."""

    def __init__(self, background_share: float = BACKGROUND_SHARE):
        self._share = background_share
        self._state = LimitHeaders()

    def observe(self, headers) -> None:
        self._state = LimitHeaders.parse(headers)

    def delay_before_next(self) -> float:
        """Пауза в секундах перед следующим запросом."""
        state = self._state

        if state.limit is None or state.remaining is None or not state.interval_ms:
            return FALLBACK_INTERVAL_SECONDS

        interval = state.interval_ms / 1000

        # Запас бота — доля корзины, которую мы не трогаем вовсе.
        reserved_for_others = state.limit * (1 - self._share)
        ours_left = state.remaining - reserved_for_others

        if ours_left <= 0:
            # Осталось только чужое. Ждём сброса окна целиком.
            return interval

        # Свою долю растягиваем на весь интервал: чем меньше осталось, тем
        # реже ходим. Пауза не превышает длину окна — ждать дольше бессмысленно,
        # к этому моменту лимит уже сбросится.
        return min(interval, interval / ours_left)

    def retry_delay(self, headers) -> float:
        """Сколько ждать после 429. Сервер говорит это сам."""
        state = LimitHeaders.parse(headers)
        # `is not None`, а не проверка на истинность: сервер может ответить 0 —
        # «ограничение снято, можно сразу». Считать это отсутствием заголовка
        # значит ждать на ровном месте.
        if state.retry_after_ms is not None:
            # Ограничиваем сверху: доверять чужому числу без потолка —
            # значит позволить одному ответу остановить синхронизацию надолго.
            return min(state.retry_after_ms / 1000, 30.0)
        return FALLBACK_INTERVAL_SECONDS * 3


class ApiDisabledRisk(RuntimeError):
    """Дальнейшие запросы опасны: следующий шаг — отключение доступа."""


class CircuitBreaker:
    """Предохранитель против автоматического отключения доступа.

    МойСклад выключает доступ пользователю, если тот сделал более 200 ошибочных
    запросов в минуту в течение часа. Включают обратно только через поддержку,
    и вместе с нами доступ потеряет бот — то есть учёт компании.

    Поэтому серия ошибок подряд останавливает работу целиком. Лучше не досинхронизировать
    сегодня, чем на сутки лишить компанию учёта.
    """

    def __init__(self, max_consecutive_errors: int = 5, max_consecutive_429: int = 3):
        self._max_errors = max_consecutive_errors
        self._max_429 = max_consecutive_429
        self._errors = 0
        self._rate_limited = 0

    def record_success(self) -> None:
        self._errors = 0
        self._rate_limited = 0

    def record_error(self, status: int | None) -> None:
        self._errors += 1
        if status == 429:
            self._rate_limited += 1
        else:
            self._rate_limited = 0

        if self._rate_limited >= self._max_429:
            raise ApiDisabledRisk(
                f"{self._rate_limited} ответов 429 подряд. Останавливаемся: "
                f"дальнейшие попытки ведут к отключению доступа к API, "
                f"а восстановить его можно только через поддержку МойСклада."
            )

        if self._errors >= self._max_errors:
            raise ApiDisabledRisk(
                f"{self._errors} ошибок подряд (последняя — {status}). "
                f"Останавливаемся, чтобы не попасть под автоматическое "
                f"отключение доступа."
            )
