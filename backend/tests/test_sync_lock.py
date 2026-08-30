"""Блокировка синхронизации.

`sync:state` идёт каждые 10–15 минут и рано или поздно застанет ночной
`sync:documents`. Два прогона разом — двойной расход общего с ботом лимита.
"""

import pytest

from moysklad.sync.lock import advisory_lock

pytestmark = pytest.mark.django_db(transaction=True)


def test_lock_is_acquired_and_released():
    with advisory_lock("test:sync") as acquired:
        assert acquired

    # После выхода блокировка свободна — иначе следующий прогон не запустится.
    with advisory_lock("test:sync") as acquired:
        assert acquired


def _holder_connection(settings):
    """Отдельное соединение: из своей сессии блокировка берётся повторно,
    и проверка бы ничего не значила."""
    import psycopg

    db = settings.DATABASES["default"]
    return psycopg.connect(
        dbname=db["NAME"], user=db["USER"], password=db["PASSWORD"],
        host=db["HOST"], port=db["PORT"],
    )


def test_second_run_is_skipped_not_queued(settings):
    """Второй прогон уходит, а не встаёт в очередь.

    Очередь синхронизаций хуже пропущенного запуска: следующий случится
    через 15 минут, а накопленная очередь ударит по лимиту разом.
    """
    from moysklad.sync.lock import _lock_key

    holder = _holder_connection(settings)
    try:
        with holder.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(%s)", [_lock_key("test:busy")])
        holder.commit()

        with advisory_lock("test:busy") as acquired:
            assert not acquired, "чужая блокировка обязана останавливать запуск"

        # Снимаем явно, а не закрытием соединения: Postgres освобождает
        # блокировки закрытой сессии не мгновенно, и проверка «теперь свободно»
        # стала бы плавающей — такой тест хуже отсутствующего.
        with holder.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [_lock_key("test:busy")])
        holder.commit()
    finally:
        holder.close()

    with advisory_lock("test:busy") as acquired:
        assert acquired, "после освобождения блокировка обязана быть доступной"


def test_lock_dies_with_its_connection(settings):
    """Блокировка снимается сама при обрыве соединения.

    Ради этого свойства advisory-блокировка и выбрана вместо строки-флага
    в таблице: после падения процесса флаг остаётся стоять, и синхронизация
    молча не запускается, пока человек не заметит.

    Postgres освобождает блокировки закрытой сессии не мгновенно, поэтому
    здесь короткое ожидание, а не единичная проверка.
    """
    import time

    from moysklad.sync.lock import _lock_key

    holder = _holder_connection(settings)
    with holder.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_lock(%s)", [_lock_key("test:orphan")])
    holder.commit()
    holder.close()  # соединение оборвалось, снять блокировку некому

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with advisory_lock("test:orphan") as acquired:
            if acquired:
                return
        time.sleep(0.1)

    pytest.fail("блокировка не освободилась после закрытия соединения")


def test_lock_is_released_after_error():
    """Блокировка снимается и при падении — иначе синхронизация встанет молча.

    Ровно этим плоха строка-флаг в таблице: после аварии процесса она
    остаётся стоять, и никто не запускается, пока человек не заметит.
    """
    with pytest.raises(RuntimeError):
        with advisory_lock("test:failing") as acquired:
            assert acquired
            raise RuntimeError("прогон упал")

    with advisory_lock("test:failing") as acquired:
        assert acquired, "после падения блокировка обязана быть свободной"
