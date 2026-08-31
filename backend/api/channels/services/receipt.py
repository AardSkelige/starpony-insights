"""Средний чек канала: сколько обычно приносит одна отгрузка.

**Медиана, а не среднее** — по той же причине, что срок поставки
и регулярность на соседней странице. У «Точки продаж» на боевых данных
среднее 13 766 ₽ против медианы 2 772 ₽: одна отгрузка на 99 495 ₽ утащила
среднее впятеро. Спрашивают «сколько обычно», и отвечает на это медиана.

**Ноль — это ответ, а не пробел.** У Instagram и Telegram медиана ровно
ноль: 9 отгрузок из 15 и 11 из 14 ушли даром. Подменить это прочерком
значило бы соврать — канал работает, просто не продаёт. Прочерк остаётся
каналу, у которого отгрузок нет вовсе.

**Разброс идёт рядом с медианой всегда.** Одно число описывает середину
и молчит о том, существует ли она: у «Эл.почты» шесть отгрузок от нуля
до 26 190 ₽, и «обычно 15 745 ₽» без границ рядом — утверждение о канале,
которого в учёте не было.
"""

import statistics
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from core.models import Document


@dataclass(frozen=True)
class Receipt:
    """Чек вместе с тем, из чего он получен.

    Составляющие уходят на страницу, а не остаются на сервере: объяснение
    по наведению обязано собираться из полученного, а не пересчитываться
    на фронте — вторая арифметика разойдётся с первой.
    """

    # Медиана суммы отгрузки, копейки. `None` — отгрузок не было вовсе.
    kopecks: int | None
    # Знаменатель медианы: по скольким отгрузкам она посчитана.
    shipments: int
    min_kopecks: int | None
    max_kopecks: int | None
    # Среднее — только в объяснении, рядом с медианой. Расхождение между
    # ними само говорит, держится канал на потоке или на редких крупных
    # отгрузках.
    average_kopecks: int | None
    # Сколько отгрузок ушло даром. Объясняет нулевую медиану: без этого
    # числа «чек 0 ₽» выглядит сбоем расчёта, а не фактом учёта.
    free_shipments: int


NOTHING = Receipt(
    kopecks=None,
    shipments=0,
    min_kopecks=None,
    max_kopecks=None,
    average_kopecks=None,
    free_shipments=0,
)


def of(shipments: Iterable[Document]) -> Receipt:
    """Чек по набору отгрузок одного канала."""
    amounts = sorted(shipment.total_kopecks for shipment in shipments)
    if not amounts:
        return NOTHING

    return Receipt(
        # Медиана чётного числа отгрузок — среднее двух средних, и половина
        # копейки здесь настоящая. Округляется до копейки: суммы учёта целые,
        # и дробная копейка на экране была бы величиной, которой нет.
        kopecks=int(Decimal(str(statistics.median(amounts))).to_integral_value()),
        shipments=len(amounts),
        min_kopecks=amounts[0],
        max_kopecks=amounts[-1],
        average_kopecks=int(Decimal(str(statistics.mean(amounts))).to_integral_value()),
        free_shipments=sum(1 for amount in amounts if amount <= 0),
    )
