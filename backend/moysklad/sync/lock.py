"""Блокировка, чтобы два прогона не наехали друг на друга.

`sync:state` идёт каждые 10–15 минут и рано или поздно застанет ночной
`sync:documents`.Два прогона разом — это двойной расход общего с ботом лимита
и гонка при записи одних и тех же строк.

Взята advisory-блокировка Postgres, а не строка в таблице: она снимается сама
при обрыве соединения. Флаг в таблице после падения процесса остаётся стоять,
и синхронизация молча не запускается, пока кто-нибудь не заметит.
"""

import contextlib
import logging
from zlib import crc32

from django.db import connection

logger = logging.getLogger(__name__)


def _lock_key(name: str) -> int:
    """Имя блокировки в число, которого ждёт Postgres."""
    # crc32 даёт 32 бита, приводим к знаковому — иначе большие значения
    # не влезают в bigint при передаче.
    return crc32(name.encode()) - 2**31


@contextlib.contextmanager
def advisory_lock(name: str):
    """Захватить блокировку или выйти, если её держит другой прогон.

    Отдаёт True, если блокировка получена. Ждать не пытается намеренно:
    очередь из синхронизаций хуже, чем пропущенный запуск — следующий
    всё равно случится через 15 минут.
    """
    key = _lock_key(name)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [key])
        acquired = cursor.fetchone()[0]

    if not acquired:
        logger.info("Синхронизация «%s» уже идёт, пропускаем запуск", name)
        yield False
        return

    try:
        yield True
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [key])
