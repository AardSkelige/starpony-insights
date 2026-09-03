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
from decimal import ROUND_HALF_UP, Decimal

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

from api.common.selection import matching, page_bounds
from api.shipments.services import selection
from core.models import DocumentPosition
from core.money import share
from core.services import consignment

# Имена аннотаций намеренно не совпадают с именами полей. `annotate(quantity=…)`
# перекрывает поле `quantity`, и следующая же агрегация по нему падает
# с «'quantity' is an aggregate»: Django видит уже не колонку, а сумму.
QTY = "qty"
QTY_FREE = "qty_free"
REVENUE = "revenue"
# Из выручки — товар на реализации: отгружен по договору комиссии, но продажей
# станет с приходом отчёта комиссионера. Без этого числа «Прибыльность»
# и эта страница расходятся на 281 126 ₽ (03.09), и обе цифры верны.
CONSIGNMENT = "consignment"
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

_QUANTITY = DecimalField(max_digits=18, decimal_places=3)


@dataclass(frozen=True)
class Filters(selection.Filters):
    """Фильтры страницы. Общее — в `selection.Filters`, своё — порядок строк."""

    ordering: str = DEFAULT_ORDERING


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
        # Тем же агрегатом, что и выручка: разойдись они, доля реализации
        # считалась бы от одного множества, а сама выручка от другого.
        CONSIGNMENT: Coalesce(
            Sum("total_kopecks", filter=consignment.where("document__")),
            Value(0),
        ),
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
        queryset = queryset.filter(matching(filters.search))

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
        # Итог по выборке: оговорка над таблицей считается отсюда, а не
        # складыванием строк — при разбиении на страницы строк видно десять.
        "consignment": consignment.share_of(totals[REVENUE], totals[CONSIGNMENT]),
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

    **Доля берётся от выручки выборки, но без учёта поиска.** Период и канал
    в знаменатель входят: при фильтре по Озону доли обязаны складываться
    в сто процентов Озона. Поиск — нет: набрав «шампунь», человек сужает
    список строк, а не то, что продали, и доля 14,4 % должна значить долю
    в выручке, а не в найденном. Иначе, найдя один товар, увидишь «100 %».

    То же правило действует на обеих страницах материалов — там оно было
    выведено раньше, и три страницы обязаны считать долю одинаково.
    """
    # Не `selection`: так называется модуль общего отбора, который этот файл
    # импортирует, — и локальное имя перекрыло бы его внутри функции.
    chosen = grouped(filters)
    totals = summary(filters)
    whole = coverage(filters)
    # Знаменатель доли — выручка выборки без поиска, и это ровно то, что
    # уже посчитала сводка: тот же отбор, тот же агрегат. Отдельный проход
    # `summary(replace(filters, search=""))` был вторым обходом всех позиций
    # за тем же числом.
    denominator = whole["revenue_kopecks"] if filters.search else totals["revenue_kopecks"]

    start, end = page_bounds(filters.page, filters.page_size)
    visible = list(chosen[start:end])

    return {
        "count": chosen.count(),
        "totals": {**totals, "revenue_share": share(totals["revenue_kopecks"], denominator)},
        "coverage": whole,
        "results": [row_of(item, denominator) for item in visible],
    }


def coverage(filters: Filters) -> dict:
    """Сводка и охват расчёта — про выборку целиком, **без поиска**.

    Соседняя с итогом величина, и путать их нельзя. Итог под таблицей считает
    показанное и обязан сходиться со сложением колонки; сводка описывает
    период и канал целиком. Смешай их — получится дробь, где числитель
    от найденного, а знаменатель от всего: она выглядит обычным числом
    и врёт молча (`DESIGN.md` §8).

    Три вопроса, и все три страница иначе оставляет без ответа:

    - **сколько всего продано** — выручка выборки, а не найденного;
    - **всё ли доехало** — сумма позиций против суммы самих документов:
      расходятся они ровно тогда, когда синхронизация потеряла строку,
      и это единственное место, где потеря видна (`CLAUDE.md` §9);
    - **сколько из этого ещё не продано** — вычитание по товару
      на реализации, то же самое, что на «Каналах продаж».
    """
    chosen = selection.shipment_positions(
        date_from=filters.date_from,
        date_to=filters.date_to,
        channel_id=filters.channel_id,
    )
    totals = chosen.aggregate(
        revenue_kopecks=Coalesce(Sum("total_kopecks"), Value(0)),
        positions_count=Count("id"),
        # Позиции с нулевой суммой: подарки, образцы, призы. Товар со склада
        # ушёл, в выручку не попал — без этого числа выручка выглядит
        # заниженной, и объяснить это нечем.
        free_positions_count=Count("id", filter=Q(total_kopecks=0)),
        products_count=Count("product", distinct=True),
        documents_count=Count("document", distinct=True),
    )
    free_value_kopecks, unpriced = _free_value(chosen)
    documents_revenue = selection.demands(
        date_from=filters.date_from,
        date_to=filters.date_to,
        channel_id=filters.channel_id,
    ).aggregate(total=Coalesce(Sum("total_kopecks"), Value(0)))["total"]

    return {
        **totals,
        "free_value_kopecks": free_value_kopecks,
        "free_unpriced_products_count": unpriced,
        "documents_revenue_kopecks": documents_revenue,
        # Состояние на сегодня, а не итог периода: отчёт комиссионера приходит
        # позже отгрузки, часто в следующем месяце, и «отгружено за август»
        # против «отчётов за август» сравнивало бы два разных множества.
        # Считается здесь, а не в `summary`: выгрузке этот блок не нужен,
        # и платить за два полнотабличных запроса ради файла незачем.
        "consignment_outstanding": consignment.outstanding(),
    }


def _free_value(positions: QuerySet[DocumentPosition]) -> tuple[int, int]:
    """Во сколько обошлась раздача — и сколько товаров оценить не удалось.

    «266 позиций даром» — честное число, которое ничего не говорит: раздача
    на сорок тысяч и на четыреста — разные разговоры (`CLAUDE.md` §8.0).
    Здесь она переводится в деньги.

    **Цена — своя у каждого товара, средняя по платным продажам этой же
    выборки.** Не общая средняя по чеку: раздают дешёвое и дорогое в разной
    пропорции, и одна цена на всех дала бы число, которое ни на что
    не опирается.

    **Товар, который только раздавали, оценить нечем**, и придумывать ему
    цену нельзя. Такие считаются отдельно, и их число идёт рядом с суммой:
    «оценить нечем ещё три» — это ответ, а молчание — занижение.

    Считается в `Decimal` и округляется **один раз, в конце**: цена штуки
    бывает долями копейки, и округление на каждом товаре накопило бы ошибку
    (`CLAUDE.md` §3).
    """
    value = Decimal(0)
    unpriced = 0

    for item in positions.values("product_id").annotate(**_sums()):
        free: Decimal = item[QTY_FREE]
        if free <= 0:
            continue

        paid_quantity: Decimal = item[QTY] - free
        if paid_quantity <= 0:
            # Товар уходил только даром: платной продажи, из которой взялась
            # бы цена, в этой выборке нет вовсе.
            unpriced += 1
            continue

        value += free * Decimal(item[REVENUE]) / paid_quantity

    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP)), unpriced


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
        # Сколько из выручки товара — реализация. По комиссии уходили 45
        # товаров из 66: у части это почти вся их выручка.
        "consignment": consignment.share_of(revenue, item[CONSIGNMENT]),
        "documents_count": item[DOCS],
        # Расчётные. None вместо нуля там, где делить не на что: ноль читался бы
        # как «товар отдавали бесплатно», а на деле цены просто нет.
        "avg_price_kopecks": _divide(revenue, quantity),
        "avg_price_paid_kopecks": _divide(revenue, quantity - free),
        # Доля от выручки выборки без учёта поиска: при фильтре по каналу доли
        # строк обязаны складываться в сто процентов, иначе число рядом
        # с ними перестаёт значить то, что написано.
        "revenue_share": share(revenue, total_revenue),
    }


def _divide(revenue: int, quantity: Decimal) -> Decimal | None:
    """Цена за единицу. Делит в Decimal: во float цена сырья теряет знаки."""
    if quantity <= 0:
        return None
    return Decimal(revenue) / quantity
