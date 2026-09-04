"""Время столбиками: по дням, неделям или месяцам.

Общее основание двух разделов. «Товары в отгрузках» рисуют этим ряд продаж
одного товара, «Каналы продаж» — выручку по каналам стопкой; вопрос у обоих
один — **растёт или падает**, и корзины у них обязаны совпадать. Разойдись
шаг между страницами, август у одной начинался бы первого числа,
а у другой — с понедельника.

Здесь только корзины: как выбрать шаг, куда падает дата, где границы
столбика. Что в корзине суммируется, знает раздел — у отгрузок это штуки
и деньги позиций, у каналов деньги документов.

Отвечает на вопрос, на который до сих пор не отвечало ничто на странице, —
**растёт или падает**. Журнал последних десяти отгрузок его не заменял:
по строке «00278 · 24.08 · Ложис Софья · 1 шт · 0 ₽» решение не принимают,
а сто девять таких строк в панель не помещаются.

**Шаг подбирается под период, а не задан навсегда.** Пять месяцев по дням —
это полторы сотни столбиков шириной в пиксель; неделя по месяцам —
один столбик. Правило простое и подписывается на экране: человек обязан
видеть, в чём мерят, иначе смена шага читается как смена данных.

**Границы и корзины считаются в одном календаре.** `Trunc*` режет по
`TIME_ZONE`, а `moment.date()` вернул бы UTC-дату — ряд обрывался бы раньше
последней корзины, и отгрузка после полуночи по Москве пропадала бы целиком.
Перевод — `core/dates.py`.

**Пустые промежутки заполняются нулями.** Неделя без продаж — это факт,
а не отсутствие данных: выбрось её, и провал в спросе превратится
в непрерывный ряд, где ничего не случилось.

**У столбика две границы, а не одна.** Одна дата рядом с подписью «по неделям»
читается как день — так и вышло при первом показе: «29.06.26: 6 шт» выглядело
продажей двадцать девятого июня, хотя это неделя с 29 июня по 5 июля. Конец
промежутка считает сервер: он же выбрал шаг, и вторая арифметика дат
на фронте разошлась бы с ним на феврале.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db.models import DecimalField, Max, Min, Sum, Value
from django.db.models.functions import Coalesce, TruncDay, TruncMonth, TruncWeek

from core.dates import local_date

_QUANTITY = DecimalField(max_digits=18, decimal_places=3)

# Границы выбора шага, в днях. Числа подобраны по ширине панели: столбик
# у́же четырёх точек перестаёт читаться, а меньше пяти столбиков не образуют
# ряда, по которому видно направление.
WEEK_FROM_DAYS = 32
MONTH_FROM_DAYS = 190

# Подпись говорит, **чем измерен один столбик**, а не «по неделям».
# Разница не в словах: «по неделям» рядом с одной датой в подсказке читается
# как день, и вопрос «это дни видимо?» возник на первом же показе.
STEPS = {
    "day": (TruncDay, "столбик — день"),
    "week": (TruncWeek, "столбик — неделя"),
    "month": (TruncMonth, "столбик — месяц"),
}


@dataclass(frozen=True)
class Timeline:
    """Ряд столбиков вместе с тем, чем он измерен."""

    step: str
    # Подпись для экрана: «по неделям». Приходит с сервера, потому что шаг
    # выбирает сервер, и два места, решающие это по-своему, разъедутся.
    step_label: str
    points: list[dict]


def step_for(days: int) -> str:
    """Каким шагом мерить период такой длины."""
    if days < WEEK_FROM_DAYS:
        return "day"
    if days < MONTH_FROM_DAYS:
        return "week"
    return "month"


def _next(start: date, step: str) -> date:
    if step == "day":
        return start + timedelta(days=1)
    if step == "week":
        return start + timedelta(days=7)
    # Первое число следующего месяца — без арифметики по числу дней,
    # которая ошибается на феврале и на декабре.
    return (start.replace(day=1) + timedelta(days=32)).replace(day=1)


def _floor(day: date, step: str) -> date:
    if step == "day":
        return day
    if step == "week":
        # Понедельник — так же, как считает `TruncWeek` в Postgres.
        return day - timedelta(days=day.weekday())
    return day.replace(day=1)


def bucket_of(day: date, step: str) -> date:
    """В какую корзину падает день. Начало корзины и есть её имя."""
    return _floor(day, step)


def buckets(start: date, end: date, step: str) -> list[tuple[date, date]]:
    """Границы всех корзин периода — включая пустые.

    Пустые промежутки нужны так же, как заполненные: месяц без продаж —
    это факт, а не отсутствие данных. Выбрось его, и провал превратится
    в непрерывный ряд, где ничего не случилось.

    Конец корзины — последний её день, а не первый день следующей:
    «29.06 – 05.07» читается как неделя, «29.06 – 06.07» — как восемь дней.
    """
    out: list[tuple[date, date]] = []
    cursor = _floor(start, step)
    while cursor <= end:
        out.append((cursor, _next(cursor, step) - timedelta(days=1)))
        cursor = _next(cursor, step)
    return out


def of(
    positions, *, date_from: date | None, date_to: date | None, step: str | None = None
) -> Timeline:
    """Продажи по столбикам за период выборки.

    Границы берутся из фильтров, а при открытом периоде — из самих отгрузок:
    рисовать пустой хвост до сегодняшнего дня значило бы показать спад,
    которого нет, — там просто нет данных.

    `step` задаётся снаружи там, где шаг диктует **вопрос**, а не длина
    периода. Главная спрашивает «растём ли мы от месяца к месяцу», и ответ
    обязан быть в месяцах: вся история проекта — 157 дней, автоматический
    выбор дал бы недели, и рядом с месячным пульсом на той же карточке
    столбики мерили бы другое. Разрешить переопределение дешевле, чем завести
    вторую арифметику корзин: она разойдётся с этой на феврале.
    """
    # Границы одним запросом: два `order_by().first()` стоили бы двух.
    bounds = positions.aggregate(first=Min("document__moment"), last=Max("document__moment"))
    first_seen, last_seen = bounds["first"], bounds["last"]

    if first_seen is None or last_seen is None:
        return Timeline(step="day", step_label=STEPS["day"][1], points=[])

    # Границы — по местному календарю, тому же, в котором `Trunc*` считает
    # корзины. Считай их по UTC, и ряд обрывался бы раньше последней корзины:
    # отгрузка в час ночи попадает в корзину следующего дня, до которой цикл
    # уже не доходит, и её штуки исчезали из графика целиком.
    start = date_from or local_date(first_seen)
    end = date_to or local_date(last_seen)
    if end < start:
        start, end = end, start

    step = step or step_for((end - start).days + 1)
    trunc, label = STEPS[step]

    rows = (
        positions.annotate(bucket=trunc("document__moment"))
        .values("bucket")
        .annotate(
            quantity=Coalesce(Sum("quantity"), Value(Decimal(0)), output_field=_QUANTITY),
            revenue_kopecks=Coalesce(Sum("total_kopecks"), Value(0)),
        )
        .order_by("bucket")
    )
    found = {
        (row["bucket"].date() if isinstance(row["bucket"], datetime) else row["bucket"]): row
        for row in rows
    }

    points: list[dict] = []
    for cursor, closes in buckets(start, end, step):
        row = found.get(cursor)
        points.append(
            {
                # Крайние корзины подрезаются границами **фильтра**: выборка
                # уже обрезана по ним, и полный интервал в подписи описывал бы
                # дни, которых в столбике нет. Период с середины недели давал
                # «29.06 – 05.07» там, где посчитана только среда–воскресенье.
                #
                # Подрезка только по заданному фильтру, а не по датам данных:
                # без фильтра корзина честно охватывает всю неделю, просто
                # в первых её днях продаж не было — и сказать «неделя»
                # там правильно.
                "start": max(cursor, date_from) if date_from else cursor,
                "end": min(closes, date_to) if date_to else closes,
                "quantity": row["quantity"] if row else Decimal(0),
                "revenue_kopecks": row["revenue_kopecks"] if row else 0,
            }
        )

    return Timeline(step=step, step_label=label, points=points)
