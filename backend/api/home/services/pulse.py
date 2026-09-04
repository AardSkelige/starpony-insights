"""Пульс: месяц против предыдущего, и ряд месяцев столбиками.

**Два множества, а не одно, и они названы по отдельности.** «Отгружено» —
это документы: сколько увезли со склада. «Продано» — отчёт прибыльности:
сколько из увезённого стало выручкой. По договору комиссии товар уходит
на реализацию и становится проданным только с отчётом комиссионера,
поэтому второе число меньше первого — на 179 852 ₽ в августе.

Это ровно тот дефект, который на трёх страницах ловили как «соседние числа
о разных множествах»: поставь мы выручку отгрузок рядом с маржой отчёта,
человек разделил бы одно на другое и получил бы маржу, которой нет.
Здесь они разведены заголовками, а разница названа прямо.

**Маржа живёт только во второй группе.** Себестоимость на момент продажи
есть исключительно в отчёте прибыльности (`PRD.md` §5.10): у отгрузок её
взять негде, и считать маржу «выручка отгрузок минус себестоимость продаж»
значило бы поделить одно множество на другое.

**Столбики — по месяцам, а не по автоматически подобранному шагу.** Вопрос
карточки — «растём ли мы от месяца к месяцу», и ответ обязан быть в месяцах.
Вся история проекта короче полугода, и автоматический выбор дал бы недели —
рядом с месячным сравнением на той же карточке столбики мерили бы другое.
"""

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Count, Sum

from api.common import timeline
from api.home.services.period import Month, Window
from core.models import DocumentKind, ProductKind, ProfitDay
from core.services.documents import alive, positions_in


@dataclass(frozen=True)
class Figure:
    """Число вместе с тем, во что оно превратилось из прошлого месяца."""

    key: str
    label: str
    value: int
    # Прошлое значение — рядом, а не вместо: «+148 %» без основания
    # не проверяется, а проверять такие числа приходят в первую очередь.
    earlier: int
    # Доля изменения в сотых. `None` — прошлый месяц был нулевым, и роста
    # «с нуля» в процентах не существует: делить не на что.
    change: Decimal | None
    # `money` — копейки, `count` — штуки, `percent` — сотые доли процента.
    unit: str


@dataclass(frozen=True)
class Pulse:
    shipped: list[Figure]
    sold: list[Figure]
    # Разница между множествами: товар, увезённый, но ещё не проданный.
    consignment_kopecks: int
    months: list[dict]


def _change(now: int, earlier: int) -> Decimal | None:
    if not earlier:
        return None
    return (Decimal(now - earlier) / Decimal(earlier) * 100).quantize(Decimal("0.1"))


def _shipments(month: Month) -> dict:
    return alive(DocumentKind.DEMAND).filter(
        moment__date__gte=month.first, moment__date__lte=month.last
    ).aggregate(total=Sum("total_kopecks"), documents=Count("id"))


def _sales(month: Month) -> dict:
    return (
        ProfitDay.objects.filter(date__gte=month.first, date__lte=month.last)
        .exclude(product__kind=ProductKind.SERVICE)
        .aggregate(revenue=Sum("revenue_kopecks"), cost=Sum("cost_kopecks"))
    )


def _median_receipt(month: Month) -> int:
    """Серединный чек месяца: половина отгрузок дороже, половина дешевле.

    Считается в Python по списку сумм, а не в SQL: отгрузок за месяц
    две сотни, и тянуть их дешевле, чем городить оконную функцию ради
    одного числа.
    """
    sums = sorted(
        alive(DocumentKind.DEMAND)
        .filter(moment__date__gte=month.first, moment__date__lte=month.last)
        .values_list("total_kopecks", flat=True)
    )
    if not sums:
        return 0
    middle = len(sums) // 2
    # Чётное число документов — среднее двух серединных, как принято
    # у медианы. Иначе результат зависел бы от того, чётный месяц или нет.
    if len(sums) % 2:
        return sums[middle]
    return (sums[middle - 1] + sums[middle]) // 2


def _margin(revenue: int, cost: int) -> int:
    """Маржа в сотых долях процента. Ноль выручки — ноль маржи, а не деление."""
    if not revenue:
        return 0
    return int(Decimal(revenue - cost) / Decimal(revenue) * 10000)


def of(window: Window) -> Pulse:
    now, was = _shipments(window.current), _shipments(window.earlier)
    sold_now, sold_was = _sales(window.current), _sales(window.earlier)

    shipped_total = now["total"] or 0
    shipped_was = was["total"] or 0
    documents = now["documents"] or 0
    documents_was = was["documents"] or 0

    # **Медиана, а не среднее.** На боевых средний чек августа — 3 251 ₽
    # при медианном 1 363 ₽: среднее втрое выше, потому что его тянет одна
    # отгрузка Озону на 99 496 ₽. «Средний чек упал на 41 %» читалось как
    # обеднение покупателя, а означало, что в июле была разовая крупная
    # поставка. Правило проекта «медиана без разброса врёт» здесь работало
    # наоборот: показывалось среднее вообще без медианы.
    #
    # Чек — по отгрузкам: «чек» это документ, а документов в отчёте
    # прибыльности нет вовсе.
    receipt = _median_receipt(window.current)
    receipt_was = _median_receipt(window.earlier)

    revenue = sold_now["revenue"] or 0
    revenue_was = sold_was["revenue"] or 0
    margin = _margin(revenue, sold_now["cost"] or 0)
    margin_was = _margin(revenue_was, sold_was["cost"] or 0)

    return Pulse(
        shipped=[
            Figure("shipped", "отгружено", shipped_total, shipped_was,
                   _change(shipped_total, shipped_was), "money"),
            Figure("documents", "отгрузок", documents, documents_was,
                   _change(documents, documents_was), "count"),
            Figure("receipt", "чек по середине", receipt, receipt_was,
                   _change(receipt, receipt_was), "money"),
        ],
        sold=[
            Figure("revenue", "продано", revenue, revenue_was,
                   _change(revenue, revenue_was), "money"),
            # Маржа сравнивается пунктами, а не процентами: «выросла на 47 %»
            # от 47,6 % до 69,9 % — арифметически верно и читается как ложь.
            Figure("margin", "маржа", margin, margin_was,
                   Decimal(margin - margin_was) / 100, "percent"),
        ],
        consignment_kopecks=shipped_total - revenue,
        months=_months(window),
    )


def _months(window: Window) -> list[dict]:
    """Ряд столбиков: полные месяцы плюс идущий, помеченный отдельно.

    Идущий месяц входит в ряд, но не в сравнения: выкинуть его значило бы
    показать, что сентября не было вовсе, а поставить наравне — объявить
    падение на девяносто процентов четвёртого числа.
    """
    end = (window.running or window.current).last
    row = timeline.of(
        positions_in(alive(DocumentKind.DEMAND)),
        date_from=None,
        date_to=end,
        step="month",
    )
    running_first = window.running.first if window.running else None
    return [
        {
            "start": point["start"],
            "end": point["end"],
            "revenue_kopecks": point["revenue_kopecks"],
            "partial": point["start"] == running_first,
        }
        for point in row.points
    ]
