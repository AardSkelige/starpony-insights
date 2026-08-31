"""Выручка по каналам во времени — стопка столбиков.

Отвечает на «растёт или падает и за счёт кого». Ни таблица, ни полосы этого
не показывают: они описывают период целиком, и канал, появившийся в августе,
выглядит в них так же, как канал, который весь период держался ровно.
На боевых данных это ровно случай Озона — 135 отгрузок, все за один месяц.

**Корзины общие с «Товарами в отгрузках»** (`api/common/timeline.py`): шаг
подбирается под длину периода и подписывается на экране. Разойдись он между
страницами, август у одной начинался бы первого числа, у другой —
с понедельника.

**В стопке пять каналов и «Другое».** Не ограничение вкуса: девять заливок
подряд перестают различаться, и палитра прямо запрещает выдавать девятый
оттенок. Хвост не выбрасывается, а сворачивается — иначе слагаемые
перестанут складываться в высоту столбика.

**Считается в Python, а не запросом.** Отгрузки уже прочитаны страницей
ради строк таблицы; второй запрос за той же сотней документов дал бы
ту же группировку и лишнее обращение к базе.
"""

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from api.common import timeline
from core.dates import local_date
from core.models import Document

# Сколько каналов показать поимённо. Остальные — «Другое».
NAMED = 5

OTHER = "Другое"


@dataclass(frozen=True)
class Dynamics:
    """Ряд столбиков вместе с тем, чем он измерен."""

    step: str
    step_label: str
    # Границы корзин: одни на все серии, иначе столбики не сложатся.
    points: list[dict]
    # Серии в порядке показа: сначала названные каналы по убыванию выручки,
    # последним — «Другое».
    series: list[dict]


@dataclass(frozen=True)
class Scale:
    """Одни корзины на весь экран.

    Стопка вверху страницы и ряд отдельного канала в разборе строки обязаны
    стоять на одних границах: два ряда с разным шагом рядом читаются как
    разные периоды, и «канал вырос» превращается в «график шире».
    """

    step: str
    step_label: str
    bounds: list[tuple[date, date]]


def scale(
    shipments: list[Document], *, date_from: date | None, date_to: date | None
) -> Scale:
    """Шаг и границы корзин для выборки.

    Границы берутся из фильтров, а при открытом периоде — из самих отгрузок:
    пустой хвост до сегодняшнего дня показал бы спад, которого нет, —
    там просто нет данных.
    """
    if not shipments:
        return Scale(step="day", step_label=timeline.STEPS["day"][1], bounds=[])

    days = [local_date(shipment.moment) for shipment in shipments]
    start = date_from or min(days)
    end = date_to or max(days)
    if end < start:
        start, end = end, start

    step = timeline.step_for((end - start).days + 1)
    return Scale(
        step=step,
        step_label=timeline.STEPS[step][1],
        bounds=timeline.buckets(start, end, step),
    )


def line(shipments: Iterable[Document], scale: Scale) -> list[int]:
    """Выручка одного канала по корзинам — ряд для разбора строки.

    Возвращает столько же чисел, сколько корзин: пустая корзина это ноль,
    а не пропуск. Месяц без продаж — факт, и выброси его, провал в спросе
    превратится в непрерывный ряд, где ничего не случилось.
    """
    found: dict[date, int] = {}
    for shipment in shipments:
        bucket = timeline.bucket_of(local_date(shipment.moment), scale.step)
        found[bucket] = found.get(bucket, 0) + shipment.total_kopecks
    return [found.get(opens, 0) for opens, _ in scale.bounds]


def of(
    shipments: Iterable[Document],
    scale: Scale,
    *,
    date_from: date | None,
    date_to: date | None,
    slots: dict[int, int],
) -> Dynamics:
    """Стопка по каналам на готовых корзинах."""
    shipments = list(shipments)
    if not shipments or not scale.bounds:
        return Dynamics(
            step=scale.step, step_label=scale.step_label, points=[], series=[]
        )

    step, bounds = scale.step, scale.bounds

    revenue: dict[int | None, int] = {}
    names: dict[int | None, str] = {}
    for shipment in shipments:
        key = shipment.sales_channel_id
        revenue[key] = revenue.get(key, 0) + shipment.total_kopecks
        names[key] = shipment.sales_channel.name if shipment.sales_channel else OTHER

    # Канал без имени — отгрузка без канала в учёте. В стопке она уходит
    # в «Другое»: отдельной серией она обещала бы канал, которого нет.
    named = [key for key in revenue if key is not None]
    named.sort(key=lambda key: (-revenue[key], names[key]))
    shown = named[:NAMED]
    folded = set(revenue) - set(shown)

    by_bucket: dict[date, dict[int | None, int]] = {
        opens: {} for opens, _ in bounds
    }
    for shipment in shipments:
        bucket = timeline.bucket_of(local_date(shipment.moment), step)
        # Корзина лежит вне периода только если отгрузка вышла за границы
        # фильтра, а выборка уже обрезана по ним. Проверка оставлена, чтобы
        # расхождение календарей не роняло страницу целиком.
        basket = by_bucket.get(bucket)
        if basket is None:
            continue
        key = shipment.sales_channel_id if shipment.sales_channel_id in shown else None
        basket[key] = basket.get(key, 0) + shipment.total_kopecks

    series = [
        {
            "channel_id": key,
            "name": names[key],
            "slot": slots.get(key),
            "revenue_kopecks": revenue[key],
        }
        for key in shown
    ]
    if folded:
        series.append(
            {
                "channel_id": None,
                "name": OTHER,
                "slot": None,
                "revenue_kopecks": sum(revenue[key] for key in folded),
            }
        )

    points = [
        {
            # Крайние корзины подрезаются границами фильтра: выборка уже
            # обрезана по ним, и полный интервал в подписи описывал бы дни,
            # которых в столбике нет.
            "start": max(opens, date_from) if date_from else opens,
            "end": min(closes, date_to) if date_to else closes,
            "values": [
                by_bucket[opens].get(item["channel_id"], 0) for item in series
            ],
        }
        for opens, closes in bounds
    ]

    return Dynamics(
        step=step, step_label=scale.step_label, points=points, series=series
    )
