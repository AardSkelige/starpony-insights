"""«Где зарабатываем» и «Что выросло и упало» — обе из отчёта прибыльности.

Один источник и один вопрос: **на чём мы зарабатываем и куда это движется.**
Поэтому они и лежат вместе — меняться будут по одной причине.

**Маржа полосами, а не столбиком чисел.** Шесть процентов рядом с восьмьюдесятью
семью читаются длиной мгновенно, а списком — чтением; это правило продукта,
а не оформления (`CLAUDE.md` §8.0). Сортировка по марже, а не по выручке:
вопрос карточки — «где зарабатываем», и первым обязан стоять край, а не объём.

**Услуги исключены везде.** Доставку не производят и не продают: её падение
означало бы «меньше возили», а не «хуже продаём», и в списке товаров такая
строка отвечает на чужой вопрос. Исключение идёт по виду номенклатуры,
а не по имени: услуг в зеркале четыре, и пятая появится.

**Порог выручки у списка худших.** Товар, проданный один раз на 200 ₽, всегда
даст крайнюю маржу в любую сторону, и без порога карточка каждый месяц
показывала бы случайную мелочь вместо того, на чём стоит бизнес.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Sum

from api.home.services.period import Window
from core.models import ProductKind, ProfitDay

TOP_ROWS = 5

# Ниже этой выручки за месяц товар в разбор маржи не попадает. Порог низкий
# намеренно: он отсекает случайную единичную продажу, а не мелкие позиции.
MIN_REVENUE_KOPECKS = 300_000


@dataclass(frozen=True)
class MarginRow:
    name: str
    revenue_kopecks: int
    # Маржа в сотых долях процента: 6900 — это 69,00 %.
    margin: int
    quantity: str


@dataclass(frozen=True)
class ChangeRow:
    name: str
    delta_kopecks: int
    now_kopecks: int
    earlier_kopecks: int


def _by_product(window_first, window_last) -> dict[str, dict]:
    return {
        row["product__name"]: row
        for row in ProfitDay.objects.filter(date__gte=window_first, date__lte=window_last)
        .exclude(product__kind=ProductKind.SERVICE)
        .values("product__name")
        .annotate(
            revenue=Sum("revenue_kopecks"),
            cost=Sum("cost_kopecks"),
            quantity=Sum("quantity"),
        )
    }


def _margin(revenue: int, cost: int) -> int:
    """Маржа в сотых долях процента. Всё в `Decimal` — правило §3.

    Деление float поверх копеечных целых давало погрешность там, где оба
    числа точные. А `int()` у отрицательной маржи усекает **к нулю**,
    то есть показывает убыток мягче, чем он есть: −37,49 % превращались
    в −37,00 %. Округление к ближайшему верно в обе стороны.
    """
    return int(
        (Decimal(revenue - cost) / Decimal(revenue) * 10000).to_integral_value(
            rounding=ROUND_HALF_UP
        )
    )


def margins(window: Window) -> list[MarginRow]:
    """Товары месяца: лучшие по марже и худшие, между ними — разрыв.

    Показываются оба края, а не верх списка: карточка отвечает на «где
    зарабатываем», и ответ «на кондиционерах по 85 %» неполон без «а шампунь
    всех мастей идёт по шесть».
    """
    rows = [
        MarginRow(
            name=name,
            revenue_kopecks=row["revenue"],
            margin=_margin(row["revenue"], row["cost"]),
            quantity=str(row["quantity"]),
        )
        for name, row in _by_product(window.current.first, window.current.last).items()
        if row["revenue"] and row["revenue"] >= MIN_REVENUE_KOPECKS
    ]
    rows.sort(key=lambda row: (-row.margin, row.name))

    if len(rows) <= TOP_ROWS + 2:
        return rows
    # Верх и низ, без середины: середина не отвечает ни на один вопрос,
    # а место занимает.
    return rows[:TOP_ROWS] + rows[-2:]


def changes(window: Window) -> list[ChangeRow]:
    """Что выросло и что упало против прошлого месяца.

    Появление и исчезновение считаются наравне с изменением: товар, который
    в июле продавали, а в августе нет, — это падение на всю его выручку,
    и пропустить его значило бы показать рост там, где половина ассортимента
    остановилась.
    """
    now = _by_product(window.current.first, window.current.last)
    was = _by_product(window.earlier.first, window.earlier.last)

    rows = [
        ChangeRow(
            name=name,
            delta_kopecks=(now.get(name, {}).get("revenue") or 0)
            - (was.get(name, {}).get("revenue") or 0),
            now_kopecks=now.get(name, {}).get("revenue") or 0,
            earlier_kopecks=was.get(name, {}).get("revenue") or 0,
        )
        for name in set(now) | set(was)
    ]
    rows = [row for row in rows if row.delta_kopecks]
    # Имя разрешает ничьи. Без него строки с равной дельтой шли в порядке
    # обхода множества — то есть в порядке хеша, который рандомизирован
    # между запусками: срез «верх и низ» показывал бы разные товары
    # от запроса к запросу. Тот же приём, что у `_sorted` в приёмках.
    rows.sort(key=lambda row: (-row.delta_kopecks, row.name))

    # Верх и низ одного ряда, а не два списка: у полос общая ось, и разделить
    # их значило бы дать каждой половине свой масштаб — падение на 3 000 ₽
    # выглядело бы так же весомо, как рост на 52 000 ₽.
    if len(rows) <= TOP_ROWS + 3:
        return rows
    return rows[:TOP_ROWS] + rows[-3:]
