"""Защита входа от перебора паролей.

Форма открыта наружу. На SSH этого сервера шло 7590 попыток подбора в сутки,
и ждать, что веб-форму обойдут стороной, оснований нет.
"""

import pytest
from django.core.cache import cache

from api.auth import throttling

pytestmark = pytest.mark.django_db

URL = "/api/auth/login/"


@pytest.fixture(autouse=True)
def clean_cache():
    """Счётчики живут в кеше и переживают тест, если их не убрать."""
    cache.clear()
    yield
    cache.clear()


def wrong(client, username="sergey", password="не-тот-пароль"):
    return client.post(
        URL, {"username": username, "password": password}, content_type="application/json"
    )


def test_wrong_password_is_still_just_unauthorized(client, make_user):
    make_user(username="sergey")

    assert wrong(client).status_code == 401


def test_blocks_after_too_many_failures(client, make_user):
    """Перебор упирается в стену, а не идёт бесконечно."""
    make_user(username="sergey")

    for _ in range(throttling.MAX_ATTEMPTS):
        assert wrong(client).status_code == 401

    response = wrong(client)
    assert response.status_code == 429
    assert response["Retry-After"] == str(throttling.WINDOW_SECONDS)


def test_block_holds_even_for_the_right_password(client, make_user):
    """После блокировки не пускают даже с правильным паролем.

    Иначе перебор просто заканчивается успехом на попытке, где пароль угадан:
    стена, которую можно пройти верным ответом, — это не стена.
    """
    make_user(username="sergey")

    for _ in range(throttling.MAX_ATTEMPTS):
        wrong(client)

    response = client.post(
        URL,
        {"username": "sergey", "password": "secret-pass-123"},
        content_type="application/json",
    )

    assert response.status_code == 429


def test_successful_login_clears_the_counter(client, make_user):
    """Успешный вход обнуляет счёт: иначе он копится между рабочими днями."""
    make_user(username="sergey")

    for _ in range(throttling.MAX_ATTEMPTS - 1):
        wrong(client)

    ok = client.post(
        URL,
        {"username": "sergey", "password": "secret-pass-123"},
        content_type="application/json",
    )
    assert ok.status_code == 200

    # Счёт обнулён — снова доступны все попытки.
    for _ in range(throttling.MAX_ATTEMPTS):
        assert wrong(client).status_code == 401


def test_counts_by_username_not_only_by_address(client, make_user, rf):
    """Ботнет с тысячи адресов не должен перебирать пароль одного человека."""
    make_user(username="sergey")

    for index in range(throttling.MAX_ATTEMPTS):
        client.post(
            URL,
            {"username": "sergey", "password": "нет"},
            content_type="application/json",
            HTTP_X_FORWARDED_FOR=f"10.0.0.{index}",
        )

    # Адрес новый, а логин тот же — блокировка держит.
    response = client.post(
        URL,
        {"username": "sergey", "password": "нет"},
        content_type="application/json",
        HTTP_X_FORWARDED_FOR="10.0.0.200",
    )
    assert response.status_code == 429


def test_counts_by_address_not_only_by_username(client, make_user):
    """Один источник не переберёт много логинов подряд."""
    make_user(username="sergey")

    for index in range(throttling.MAX_ATTEMPTS):
        wrong(client, username=f"кто-то-{index}")

    # Логин новый, адрес тот же — блокировка держит.
    assert wrong(client, username="ещё-кто-то").status_code == 429


def test_case_does_not_bypass_the_limit(client, make_user):
    """Смена регистра логина не должна открывать новый счёт попыток.

    Адреса намеренно все разные: с одного блокировка сработала бы по нему,
    и проверка регистра осталась бы не у дел.
    """
    make_user(username="sergey")

    for index in range(throttling.MAX_ATTEMPTS):
        client.post(
            URL,
            {"username": "sergey", "password": "нет"},
            content_type="application/json",
            HTTP_X_FORWARDED_FOR=f"10.0.0.{index}",
        )

    response = client.post(
        URL,
        {"username": "SERGEY", "password": "нет"},
        content_type="application/json",
        HTTP_X_FORWARDED_FOR="10.0.0.99",
    )
    assert response.status_code == 429


def test_real_address_is_read_from_behind_the_proxy(client, make_user):
    """За Caddy все запросы приходят с одного адреса — важен `X-Forwarded-For`.

    Читай мы только `REMOTE_ADDR`, все посетители считались бы одним
    источником, и первые же пять чужих ошибок закрыли бы вход всей компании.
    """
    make_user(username="sergey")

    # Пять неудач с одного внешнего адреса, разные логины.
    for index in range(throttling.MAX_ATTEMPTS):
        client.post(
            URL,
            {"username": f"кто-то-{index}", "password": "нет"},
            content_type="application/json",
            HTTP_X_FORWARDED_FOR="198.51.100.10",
        )

    # Другой внешний адрес, тот же прокси: человека пускают к форме.
    response = client.post(
        URL,
        {"username": "sergey", "password": "secret-pass-123"},
        content_type="application/json",
        HTTP_X_FORWARDED_FOR="198.51.100.11",
    )
    assert response.status_code == 200


def test_another_user_from_another_address_is_unaffected(client, make_user):
    """Чужая блокировка не должна мешать соседу работать."""
    make_user(username="sergey")
    make_user(username="anna")

    for _ in range(throttling.MAX_ATTEMPTS):
        wrong(client, username="sergey")

    response = client.post(
        URL,
        {"username": "anna", "password": "secret-pass-123"},
        content_type="application/json",
        HTTP_X_FORWARDED_FOR="203.0.113.7",
    )
    assert response.status_code == 200
