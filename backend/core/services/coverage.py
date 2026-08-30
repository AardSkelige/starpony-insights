"""Запас в днях: на сколько хватит остатка при нынешнем расходе.

**Первая половина порога закупки** (`PRD.md` §5.9). Там записано, почему
сигнал нельзя строить на `minimumBalance`: поле пусто у всех 314 позиций,
и признак «всё хорошо» на пустом поле — худший вид молчаливой поломки.
Расход за период против свободного остатка такой проблемы не имеет:
оба числа берутся из фактов учёта.

Живёт в `core/`, а не у страницы: тот же расчёт нужен «Расчёту производства»
(хватит ли сырья на партию) и «Поставщикам» (кого торопить). Ошибка здесь
тихая — число остаётся правдоподобным, — и второй копии у неё быть не должно.

**Это не прогноз.** Средний расход выбранного периода, а не тренд: пяти
месяцев истории мало, чтобы говорить о сезонности, и Prophet в проекте
отсутствует намеренно. Меняешь период — меняется и число, и подсказка
на экране обязана это сказать.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db.models import Max, Min, QuerySet

from core.dates import days_between
from core.models import DocumentPosition


@dataclass(frozen=True)
class Coverage:
    """На сколько хватит остатка и из чего это посчитано."""

    # Расход за период — числитель формулы. Хранится рядом с ответом,
    # а не берётся из строки таблицы: у «Материалов в приёмках» в строке
    # лежит **закупленное**, а не израсходованное, и подставить её значило бы
    # показать формулу, в которой числа не сходятся.
    quantity: Decimal
    # Средний расход за сутки. Приходит рядом с ответом, чтобы формула
    # собиралась из полученного, а не пересчитывалась на фронте.
    per_day: Decimal
    days_of_period: int
    # `None` — остатка в отчёте нет вовсе (36 материалов из 161) либо расхода
    # за период не было. Ноль здесь означал бы «кончился», а это другое
    # утверждение об учёте: мы просто не знаем.
    days_left: int | None
    available: Decimal | None


def days_in(date_from: date | None, date_to: date | None, fallback: int) -> int:
    """Длина периода в днях. Обе границы включаются: 1–2 августа — два дня.

    Пустая граница означает «весь период данных», и её длину знает только
    вызывающий — он и передаёт `fallback` из фактических дат выборки.
    Придумывать её здесь значило бы делить на срок, которого не было.
    """
    if date_from and date_to:
        return max((date_to - date_from).days + 1, 1)
    return max(fallback, 1)


def days_of(positions: QuerySet[DocumentPosition]) -> int:
    """Длина выборки в днях — от первого документа до последнего.

    Нужна, когда период не задан руками: делить расход на срок, которого
    в данных не было («сегодня минус год»), значит занизить дневной расход
    во столько раз, во сколько ошиблись со сроком.

    Живёт здесь, а не у раздела: тот же вопрос задают «Материалы в отгрузках»
    и «Материалы в приёмках», а две копии разошлись бы на первом же
    уточнении — например, считать ли последний день целиком.
    """
    bounds = positions.aggregate(
        first=Min("document__moment"), last=Max("document__moment")
    )
    if not bounds["first"] or not bounds["last"]:
        return 1
    return days_between(bounds["first"], bounds["last"]) + 1


def of(
    quantity: Decimal,
    days: int,
    available: Decimal | None,
) -> Coverage:
    """Запас по расходу за период и свободному остатку.

    Свободный остаток, а не общий: зарезервированное под заказы уже обещано,
    и считать его своим значит обнаружить нехватку в день отгрузки.
    """
    days = max(days, 1)
    per_day = quantity / days if quantity > 0 else Decimal(0)

    if available is None or per_day <= 0:
        return Coverage(
            quantity=quantity,
            per_day=per_day,
            days_of_period=days,
            days_left=None,
            available=available,
        )

    # Округление вниз: «хватит на 2,9 дня» — это два дня, а не три.
    # Вверх — значит пообещать день, которого нет.
    return Coverage(
        quantity=quantity,
        per_day=per_day,
        days_of_period=days,
        days_left=int(max(available, Decimal(0)) / per_day),
        available=available,
    )


# Пороги тревоги. Две недели — примерный срок поставки у большинства
# поставщиков StarPony; месяц — запас на то, чтобы успеть заказать спокойно.
# Числа здесь, а не в компоненте: раскраска строки и текст предупреждения
# обязаны меняться вместе.
CRITICAL_DAYS = 14
LOW_DAYS = 30


def level(days_left: int | None) -> str:
    """Насколько всё плохо: `none` — не знаем, `ok` / `low` / `critical`."""
    if days_left is None:
        return "none"
    if days_left <= CRITICAL_DAYS:
        return "critical"
    if days_left <= LOW_DAYS:
        return "low"
    return "ok"
