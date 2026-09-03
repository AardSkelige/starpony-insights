"""Выборка страницы «Прибыльность»: что считается товаром и по какой базе.

Своё у раздела — ровно две вещи, и обе про домен, а не про адресную строку.

**Первая: товар — это то, у чего есть артикул.** Решение владельца 02.09.
Без него в марже оказываются четыре услуги «Доставка»: себестоимости
у услуги нет и быть не может, а выручка есть — 12 970 ₽ с маржой 100 %.
Такая строка возглавила бы список «на чём зарабатываем», и это была бы
неправда о продукте.

**Вторая: выручка бывает двух видов, и они не равны.** «Продано» — деньги
за товар: так считает МойСклад, и товар по договору комиссии становится
проданным только с приходом отчёта комиссионера. «Отгружено» — всё, что
уехало со склада. На 02.09 разница 281 126 ₽, и это не ошибка ни одной
из сторон: 521 штука лежит у комиссионеров непроданной.
"""

from dataclasses import dataclass
from datetime import date

from django.db.models import Q, QuerySet

from api.common import selection
from core.models import DocumentKind, DocumentPosition, ProfitDay


class Basis:
    """По какому событию считается выручка."""

    SOLD = "sold"        # деньги за товар: отчёт прибыльности МойСклада
    SHIPPED = "shipped"  # всё, что уехало со склада, включая реализацию

    CHOICES = (SOLD, SHIPPED)


@dataclass(frozen=True)
class Filters(selection.Filters):
    """Общее — в `selection.Filters`, своё — база расчёта, подарки и порядок.

    `with_free` по умолчанию выключен: товар, отданный даром, имеет
    себестоимость и не имеет выручки, и включённым он тянет маржу вниз
    у каждого четвёртого товара — у Репеллента даром ушла четверть объёма.
    Это вложение в продвижение, а не убыток от цены, и вопрос страницы
    («правильно ли мы назначили цену») он не проясняет, а запутывает.
    """

    basis: str = Basis.SOLD
    with_free: bool = False
    ordering: str = "-profit"


def _articled() -> Q:
    """Условие «это товар, а не услуга».

    Возвращает условие, а не готовый фильтр: одно и то же утверждение
    прикладывается и к строкам отчёта (`product__article`), и к позициям
    документов. Две копии разошлись бы, и два числа на одной странице
    оказались бы о разных множествах.
    """
    return ~Q(product__article="")


def profit_days(
    *, date_from: date | None = None, date_to: date | None = None
) -> QuerySet[ProfitDay]:
    """Строки отчёта прибыльности, попавшие в период.

    Период режется по полю `date`, а не по моменту документа: в зеркале
    отчёта день уже посчитан МойСкладом по местному календарю, и второй
    раз его границы вычислять не надо.
    """
    queryset = ProfitDay.objects.filter(_articled())
    if date_from:
        queryset = queryset.filter(date__gte=date_from)
    if date_to:
        queryset = queryset.filter(date__lte=date_to)
    return queryset


def shipment_positions(
    *, date_from: date | None = None, date_to: date | None = None
) -> QuerySet[DocumentPosition]:
    """Позиции отгрузок за период — база «Отгружено» и источник подарков.

    Отбор тот же, что у «Товаров в отгрузках»: удалённые и непроведённые
    исключены. Разойдись он, две страницы за один период показали бы
    разное число отгруженного.
    """
    queryset = DocumentPosition.objects.filter(
        _articled(),
        document__kind=DocumentKind.DEMAND,
        document__deleted_at__isnull=True,
        document__applicable=True,
    )
    return selection.within(queryset, date_from, date_to)


def commission_report_positions(
    *, date_from: date | None = None, date_to: date | None = None
) -> QuerySet[DocumentPosition]:
    """Позиции отчётов комиссионера — то, что комиссионер уже продал.

    Нужны ради одного вычитания: отгружено по комиссии минус продано
    комиссионером — и есть товар, лежащий у него на реализации.
    """
    queryset = DocumentPosition.objects.filter(
        _articled(),
        document__kind=DocumentKind.COMMISSION_REPORT,
        document__deleted_at__isnull=True,
        document__applicable=True,
    )
    return selection.within(queryset, date_from, date_to)


def matching(term: str) -> Q:
    """Условие поиска по номенклатуре — общее с остальными разделами."""
    return selection.matching(term)
