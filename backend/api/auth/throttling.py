"""Защита входа от перебора паролей.

Форма входа открыта наружу и вызывает `authenticate()` без ограничений —
это приглашение перебирать. На SSH этого сервера шло 7590 попыток в сутки,
и ждать, что веб-форму обойдут стороной, оснований нет.

Считаются **неудачные** попытки, а не все запросы: человек, который верно
ввёл пароль десять раз за день, ничего не нарушил.

Ключей два, и каждый закрывает свой способ обойти второй:

* по адресу — один источник не переберёт много паролей;
* по логину — ботнет с тысячи адресов не переберёт пароль одного человека.

Счётчик живёт в кеше Django. В проде это таблица в Postgres: у gunicorn
два воркера, и счётчик в памяти процесса дал бы каждому свой лимит,
то есть удвоил бы допустимое число попыток.
"""

from dataclasses import dataclass

from django.core.cache import cache

# Пять попыток на пятнадцать минут. Человек, забывший пароль, укладывается;
# перебор при такой скорости занимает годы.
MAX_ATTEMPTS = 5
WINDOW_SECONDS = 15 * 60


@dataclass(frozen=True)
class Attempt:
    """Сколько попыток осталось и через сколько снимется запрет."""

    blocked: bool
    retry_after_seconds: int = 0


def _client_ip(request) -> str:
    """Адрес клиента.

    За Caddy настоящий адрес приходит в `X-Forwarded-For`; первый элемент —
    исходный клиент, дальше идут прокси. Без прокси остаётся `REMOTE_ADDR`.
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _keys(request, username: str) -> tuple[str, ...]:
    # Логин приводится к нижнему регистру: иначе «Sergey» и «sergey»
    # считаются раздельно, и лимит обходится сменой регистра.
    return (
        f"login-attempts:ip:{_client_ip(request)}",
        f"login-attempts:user:{username.strip().lower()}",
    )


def check(request, username: str) -> Attempt:
    """Не пора ли отказать, не проверяя пароль вовсе."""
    for key in _keys(request, username):
        if (cache.get(key) or 0) >= MAX_ATTEMPTS:
            return Attempt(blocked=True, retry_after_seconds=WINDOW_SECONDS)
    return Attempt(blocked=False)


def record_failure(request, username: str) -> None:
    """Запомнить неудачу по обоим ключам."""
    for key in _keys(request, username):
        # `add` ставит значение только если ключа нет — так создаётся окно
        # с нужным сроком жизни. Дальше `incr` не продлевает его, и окно
        # действительно скользит, а не растёт с каждой попыткой.
        cache.add(key, 0, WINDOW_SECONDS)
        try:
            cache.incr(key)
        except ValueError:
            # Ключ истёк между `add` и `incr` — редкая гонка. Начинаем заново.
            cache.set(key, 1, WINDOW_SECONDS)


def reset(request, username: str) -> None:
    """Вход удался — счётчики обнуляются, чтобы не копились между сессиями."""
    for key in _keys(request, username):
        cache.delete(key)
