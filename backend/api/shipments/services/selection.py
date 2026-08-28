"""Выборка позиций отгрузок: период, канал, поиск по номенклатуре.

Общее основание двух страниц раздела. «Товары в отгрузках» сворачивает эти
позиции по товару, «Материалы в отгрузках» разворачивает их же по техкартам —
но отбирают обе одинаково, и разойдись отбор, две страницы за один период
показали бы разное число отгрузок.

Границы периода живут здесь же: день — понятие календаря, а не UTC, и
сравнение с концом дня теряет документ, проведённый в 23:59:59.5.
"""

from datetime import date, datetime, time, timedelta

from django.db.models import Q, QuerySet
from django.utils import timezone

from core.models import DocumentKind, DocumentPosition


def day_start(day: date) -> datetime:
    """Начало дня в текущем поясе: граница периода — про календарь, не про UTC."""
    return timezone.make_aware(datetime.combine(day, time.min))


def day_after(day: date) -> datetime:
    """Начало следующего дня: верхняя граница строгая, чтобы день вошёл целиком.

    Сравнивать с концом дня нельзя: `moment` хранит секунды, и документ,
    проведённый в 23:59:59.5, выпал бы из периода без единого признака.
    """
    return day_start(day) + timedelta(days=1)


def shipment_positions(
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    channel_id: int | None = None,
) -> QuerySet[DocumentPosition]:
    """Позиции отгрузок, попавшие в период и канал.

    Удалённые документы исключаются: строка не удаляется физически, но
    исчезнувший из учёта документ не должен попадать ни в одну сумму.
    """
    queryset = DocumentPosition.objects.filter(
        document__kind=DocumentKind.DEMAND,
        document__deleted_at__isnull=True,
        # Только проведённые: черновик отгрузки лежит в той же таблице,
        # но товар по нему со склада не ушёл и денег не принёс. Сейчас таких
        # нет ни одного, и именно поэтому фильтр нужен сегодня — когда
        # появится первый, расхождение с учётом никто не заметит.
        document__applicable=True,
    )

    if date_from:
        queryset = queryset.filter(document__moment__gte=day_start(date_from))
    if date_to:
        queryset = queryset.filter(document__moment__lt=day_after(date_to))
    if channel_id:
        queryset = queryset.filter(document__sales_channel_id=channel_id)

    return queryset


def matching(term: str) -> Q:
    """Условие поиска по номенклатуре: название, артикул, код.

    Возвращает условие, а не отфильтрованный запрос: у «Материалов» искать
    надо по полю `product`, а у деталей строки — по другому пути к тому же
    товару. Условие переносится, готовый фильтр — нет.
    """
    return (
        Q(product__name__icontains=term)
        | Q(product__article__icontains=term)
        | Q(product__code__icontains=term)
    )


def channels(
    *, date_from: date | None = None, date_to: date | None = None
) -> list[dict]:
    """Каналы, встречающиеся в отгрузках периода, — для выпадающего списка.

    Фильтр по каналу и поиск сняты намеренно. Оставь мы канал — после выбора
    «Озон» в списке остался бы один «Озон», и переключиться было бы нечем,
    кроме сброса всех фильтров. Оставь поиск — набранное слово могло бы
    выкинуть выбранный канал из списка, и поле показало бы «Канал», хотя
    фильтр по нему всё ещё действует.

    Отдаётся вместе со страницей, а не отдельным справочником: девять значений
    не стоят своей строки в реестре прав, а соседние разделы возьмут их так же —
    из своего ответа.
    """
    rows = (
        shipment_positions(date_from=date_from, date_to=date_to)
        .exclude(document__sales_channel=None)
        .values("document__sales_channel_id", "document__sales_channel__name")
        .distinct()
        .order_by("document__sales_channel__name")
    )
    return [
        {
            "id": row["document__sales_channel_id"],
            "name": row["document__sales_channel__name"],
        }
        for row in rows
    ]
