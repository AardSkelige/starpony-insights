"""Лимит запросов и предохранитель.

Тесты здесь обязательны: ошибка в лимитере не падает, а тихо выедает корзину,
общую с ботом Agent - StarPony, — и учёт компании встаёт круглосуточно.
"""

import pytest

from moysklad.limits import (
    FALLBACK_INTERVAL_SECONDS,
    ApiDisabledRisk,
    CircuitBreaker,
    LimitHeaders,
    RateLimiter,
)


def headers(limit=45, remaining=45, interval_ms=3000, retry_after_ms=None):
    result = {
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": str(remaining),
        "X-Lognex-Retry-TimeInterval": str(interval_ms),
    }
    if retry_after_ms is not None:
        result["X-Lognex-Retry-After"] = str(retry_after_ms)
    return result


class TestLimitHeaders:
    def test_parses_all_headers(self):
        parsed = LimitHeaders.parse(headers(retry_after_ms=1500))
        assert (parsed.limit, parsed.remaining) == (45, 45)
        assert (parsed.interval_ms, parsed.retry_after_ms) == (3000, 1500)

    def test_missing_headers_are_none(self):
        assert LimitHeaders.parse({}) == LimitHeaders()

    def test_garbage_is_treated_as_missing(self):
        """Невнятное значение безопаснее считать отсутствующим, чем угадывать."""
        parsed = LimitHeaders.parse({"X-RateLimit-Remaining": "не число"})
        assert parsed.remaining is None


class TestRateLimiter:
    def test_falls_back_to_slowest_schedule(self):
        """Без заголовков держим темп под нижнюю границу расписания — 11 за 3с."""
        assert RateLimiter().delay_before_next() == pytest.approx(FALLBACK_INTERVAL_SECONDS)
        assert FALLBACK_INTERVAL_SECONDS == pytest.approx(3 / 11)

    def test_pause_grows_as_basket_empties(self):
        """Ключевое свойство: чем меньше осталось, тем реже ходим.

        Первая версия формулы этого не обеспечивала — при остатке 14 пауза
        была меньше, чем при 22, то есть у дна корзины клиент разгонялся.
        """
        limiter = RateLimiter()
        delays = []
        for remaining in (45, 30, 22, 18, 15, 14):
            limiter.observe(headers(remaining=remaining))
            delays.append(limiter.delay_before_next())

        assert delays == sorted(delays), f"пауза не растёт монотонно: {delays}"

    def test_stops_at_bot_reserve(self):
        """Запас бота не трогаем: ждём сброса окна целиком.

        30% корзины оставлены боту, который проверяет учёт круглосуточно
        и ждать не может.
        """
        limiter = RateLimiter()
        limiter.observe(headers(limit=45, remaining=13, interval_ms=3000))
        assert limiter.delay_before_next() == pytest.approx(3.0)

    def test_never_waits_longer_than_the_window(self):
        """Ждать дольше окна бессмысленно — лимит к тому моменту сброшен."""
        limiter = RateLimiter()
        limiter.observe(headers(limit=45, remaining=32, interval_ms=3000))
        assert limiter.delay_before_next() <= 3.0

    def test_retry_delay_comes_from_server(self):
        assert RateLimiter().retry_delay(headers(retry_after_ms=2500)) == pytest.approx(2.5)

    def test_retry_delay_is_capped(self):
        """Одному ответу нельзя останавливать синхронизацию на час."""
        assert RateLimiter().retry_delay(headers(retry_after_ms=3_600_000)) == 30.0


class TestCircuitBreaker:
    def test_stops_after_consecutive_429(self):
        """Серия 429 — прямая дорога к отключению доступа. Останавливаемся."""
        breaker = CircuitBreaker(max_consecutive_429=3)
        breaker.record_error(429)
        breaker.record_error(429)
        with pytest.raises(ApiDisabledRisk, match="429"):
            breaker.record_error(429)

    def test_stops_after_consecutive_errors(self):
        breaker = CircuitBreaker(max_consecutive_errors=3)
        breaker.record_error(500)
        breaker.record_error(500)
        with pytest.raises(ApiDisabledRisk):
            breaker.record_error(500)

    def test_success_resets_the_counter(self):
        """Одиночные сбои — не повод останавливаться."""
        breaker = CircuitBreaker(max_consecutive_errors=3)
        for _ in range(10):
            breaker.record_error(500)
            breaker.record_error(500)
            breaker.record_success()

    def test_error_message_explains_the_stakes(self):
        """Сообщение читает человек ночью: оно должно объяснять, почему встали."""
        breaker = CircuitBreaker(max_consecutive_429=1)
        with pytest.raises(ApiDisabledRisk) as info:
            breaker.record_error(429)
        assert "поддержк" in str(info.value).lower()
