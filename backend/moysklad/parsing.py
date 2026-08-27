"""Разбор значений из ответов API. Одно место на весь проект.

Здесь живут два правила, каждое из которых легко нарушить незаметно:
время без пояса и числа типа Float.
"""

import logging
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# МойСклад отдаёт время строкой «2026-08-27 10:55:00.000» — без пояса.
# Проверено на боевом аккаунте: это московское время (документ, созданный
# в 11:30 МСК, приходит с moment 10:55 при UTC 08:30).
#
# Принять его за UTC — значит сдвинуть все даты на три часа: вечерняя отгрузка
# уедет во вчера, а отчёт за день не сойдётся с учётом.
MOYSKLAD_TZ = ZoneInfo("Europe/Moscow")

DATETIME_FORMATS = ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S")


def parse_datetime(value: str | None) -> datetime | None:
    """Время из API — в осознанный datetime с московским поясом."""
    if not value:
        return None

    for fmt in DATETIME_FORMATS:
        try:
            naive = datetime.strptime(value, fmt)
        except ValueError:
            continue
        return naive.replace(tzinfo=MOYSKLAD_TZ)

    logger.warning("Не удалось разобрать время из API: %r", value)
    return None


def parse_decimal(value, *, kopecks_to_units: bool = False) -> Decimal | None:
    """Число из API в Decimal.

    Через `str`, а не напрямую из float: `Decimal(0.1)` уносит в число
    погрешность двоичного представления, и она переезжает в расчёты.

    `kopecks_to_units=True` — для денег. Дробные копейки не редкость:
    из 255 позиций с остатком у 150 себестоимость дробная, вплоть до
    `11841.934782608696` копеек. Округлять их нельзя: ошибка ложится
    в себестоимость и дальше в маржу.
    """
    if value is None:
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        logger.warning("Не удалось разобрать число из API: %r", value)
        return None
    return result / 100 if kopecks_to_units else result


def parse_kopecks(value) -> int:
    """Сумма документа в целые копейки.

    Округление, а не усечение: суммы приходят типом Float, и `int(1234.9999999)`
    дал бы 1234 — расхождение с учётом там, где оно обязано сходиться в ноль.
    """
    amount = parse_decimal(value)
    return int(amount.to_integral_value(rounding=ROUND_HALF_UP)) if amount is not None else 0
