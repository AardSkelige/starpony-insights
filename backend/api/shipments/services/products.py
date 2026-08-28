"""Товары в отгрузках: что и сколько продано за период.

Позиции отгрузок сворачиваются по товару. Всё считается в базе одним запросом —
перебирать 1042 позиции в Python значило бы тащить их в память ради сумм,
которые Postgres сложит сам.

**Расчётные числа отдаются составляющими, а не готовым текстом.** Средняя цена
приходит вместе с выручкой и количеством, из которых получена, — фронт рисует
формулу из них и ничего не досчитывает. Собирать текст здесь нельзя: рубли
существуют только на слое отображения, а формула с «231 530,38 ₽» — это уже
отображение.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db.models import (
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    Q,
    QuerySet,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce, NullIf

from api.shipments.services import selection
from core.models import DocumentPosition

# Имена аннотаций намеренно не совпадают с именами полей. `annotate(quantity=…)`
# перекрывает поле `quantity`, и следующая же агрегация по нему падает
# с «'quantity' is an aggregate»: Django видит уже не колонку, а сумму.
QTY = "qty"
QTY_FREE = "qty_free"
REVENUE = "revenue"
DOCS = "docs"
AVG = "avg_price"

# Сортировки, разрешённые снаружи. Список закрытый: «ordering» из запроса
# попадает прямо в ORM, и открытый перечень позволил бы сортировать по
# чему угодно, включая поля соседних таблиц.
# Минус означает убывание — как принято везде, от DRF до SQL. Обратное
# соглашение («revenue» = по убыванию) читается наоборот у текстовых полей:
# «name» пришлось бы понимать как Я→А.
ORDERING = {
    "revenue": REVENUE,
    "-revenue": f"-{REVENUE}",
    "quantity": QTY,
    "-quantity": f"-{QTY}",
    "free": QTY_FREE,
    "-free": f"-{QTY_FREE}",
    # Выражением, а не строкой: у средней цены бывает NULL — когда делить
    # не на что, — и Postgres по умолчанию кладёт NULL наверх при убывании.
    # Строка без цены оказалась бы первой в списке «самых дорогих».
    "avg_price": F(AVG).asc(nulls_last=True),
    "-avg_price": F(AVG).desc(nulls_last=True),
    "name": "product__name",
    "-name": "-product__name",
    # Доля пропорциональна выручке в пределах одной выборки, поэтому
    # сортируется по ней же. Отдельного выражения не нужно: делить каждую
    # строку на одно и то же число порядок не меняет.
    "share": REVENUE,
    "-share": f"-{REVENUE}",
}
DEFAULT_ORDERING = "-revenue"

# Последний ключ сортировки, разрешающий ничьи. Без него строки с равной
# выручкой идут в порядке, который Postgres не обязан сохранять между
# запросами: один товар попадёт на две страницы подряд, другой — ни на одну.
# Проверяется тестом по самому запросу: воспроизвести недетерминизм по заказу
# нельзя, а инвариант «порядок определён полностью» — можно.
TIE_BREAKER = "product_id"

MAX_PAGE_SIZE = 200
DEFAULT_PAGE_SIZE = 50

_QUANTITY = DecimalField(max_digits=18, decimal_places=3)


@dataclass(frozen=True)
class Filters:
    """Что человек выбрал в панели фильтров."""

    date_from: date | None = None
    date_to: date | None = None
    channel_id: int | None = None
    search: str = ""
    ordering: str = DEFAULT_ORDERING
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE


def _sums() -> dict:
    """Одни и те же агрегаты для итогов и для строк — считаются в одном месте.

    Разойдись они, итог в подвале перестал бы сходиться с суммой колонки,
    и разница была бы видна человеку раньше, чем нам.
    """
    return {
        QTY: Coalesce(Sum("quantity"), Value(Decimal(0)), output_field=_QUANTITY),
        # «Даром» — позиции с нулевой суммой: образцы, замены, подарки.
        # Природа этих отгрузок у владельца пока не уточнена, поэтому число
        # показывается отдельной величиной, а не растворяется в общем количестве.
        QTY_FREE: Coalesce(
            Sum("quantity", filter=Q(total_kopecks=0)),
            Value(Decimal(0)),
            output_field=_QUANTITY,
        ),
        REVENUE: Coalesce(Sum("total_kopecks"), Value(0)),
        DOCS: Count("document", distinct=True),
    }


def _average_price():
    """Средняя цена как выражение — чтобы по ней можно было сортировать.

    `NullIf` спасает от деления на ноль: количество бывает нулевым, и без
    него Postgres прерывает весь запрос, а не одну строку. Строки без цены
    уходят в конец списка — там им и место.
    """
    return ExpressionWrapper(
        F(REVENUE) / NullIf(F(QTY), Value(Decimal(0))),
        output_field=DecimalField(max_digits=18, decimal_places=6),
    )


def positions(filters: Filters) -> QuerySet[DocumentPosition]:
    """Позиции отгрузок, попавшие под фильтры страницы.

    Отбор по периоду и каналу — общий с «Материалами в отгрузках», поиск
    свой: здесь строка таблицы это проданный товар, и искать надо его.
    """
    queryset = selection.shipment_positions(
        date_from=filters.date_from,
        date_to=filters.date_to,
        channel_id=filters.channel_id,
    )

    if filters.search:
        queryset = queryset.filter(selection.matching(filters.search.strip()))

    return queryset


def summary(filters: Filters) -> dict:
    """Итоги по всей выборке — не по странице, которую видно на экране."""
    totals = positions(filters).aggregate(
        **_sums(),
        products_count=Count("product", distinct=True),
    )
    return {
        "quantity": totals[QTY],
        "free_quantity": totals[QTY_FREE],
        "revenue_kopecks": totals[REVENUE],
        "documents_count": totals[DOCS],
        "products_count": totals["products_count"],
    }


def channels(filters: Filters) -> list[dict]:
    """Каналы для выпадающего списка. Общий для раздела код — в `selection`."""
    return selection.channels(date_from=filters.date_from, date_to=filters.date_to)


def grouped(filters: Filters) -> QuerySet:
    """Позиции, свёрнутые по товару, в порядке показа."""
    return (
        positions(filters)
        .values(
            "product_id",
            "product__name",
            "product__article",
            "product__code",
            "product__uom__name",
        )
        .annotate(**_sums())
        .annotate(**{AVG: _average_price()})
        .order_by(ORDERING.get(filters.ordering, ORDERING[DEFAULT_ORDERING]), TIE_BREAKER)
    )


def page(filters: Filters) -> dict:
    """Всё, что нужно странице, за один расчёт итогов.

    Итоги нужны и подвалу, и доле в каждой строке. Считать их дважды —
    это второй проход по всем позициям на каждый запрос.

    Доля берётся от выручки **той же выборки**, а не от всех продаж вообще:
    иначе при фильтре по каналу доли строк не сложились бы в сто процентов,
    и число, показанное рядом с ними, перестало бы значить то, что написано.
    """
    # Не `selection`: так называется модуль общего отбора, который этот файл
    # импортирует, — и локальное имя перекрыло бы его внутри функции.
    chosen = grouped(filters)
    totals = summary(filters)

    page_size = max(1, min(filters.page_size, MAX_PAGE_SIZE))
    start = max(0, (filters.page - 1) * page_size)
    visible = list(chosen[start : start + page_size])

    return {
        "count": chosen.count(),
        "totals": totals,
        "results": [row_of(item, totals["revenue_kopecks"]) for item in visible],
    }


def rows(filters: Filters) -> tuple[list[dict], int, int]:
    """Строки, их число и выручка выборки. Обёртка для тестов и выгрузки."""
    result = page(filters)
    return result["results"], result["count"], result["totals"]["revenue_kopecks"]


def row_of(item: dict, total_revenue: int) -> dict:
    """Одна строка таблицы вместе с составляющими своих расчётных чисел."""
    quantity: Decimal = item[QTY]
    free: Decimal = item[QTY_FREE]
    revenue: int = item[REVENUE]

    return {
        "product_id": item["product_id"],
        "name": item["product__name"],
        "article": item["product__article"],
        "code": item["product__code"],
        "uom": item["product__uom__name"] or "",
        "quantity": quantity,
        "free_quantity": free,
        "revenue_kopecks": revenue,
        "documents_count": item[DOCS],
        # Расчётные. None вместо нуля там, где делить не на что: ноль читался бы
        # как «товар отдавали бесплатно», а на деле цены просто нет.
        "avg_price_kopecks": _divide(revenue, quantity),
        "avg_price_paid_kopecks": _divide(revenue, quantity - free),
        "revenue_share": _share(revenue, total_revenue),
    }


def _share(revenue: int, total_revenue: int) -> Decimal | None:
    """Доля позиции в выручке выборки, долей единицы. None — делить не на что."""
    if total_revenue <= 0:
        return None
    return Decimal(revenue) / Decimal(total_revenue)


def _divide(revenue: int, quantity: Decimal) -> Decimal | None:
    """Цена за единицу. Делит в Decimal: во float цена сырья теряет знаки."""
    if quantity <= 0:
        return None
    return Decimal(revenue) / quantity
