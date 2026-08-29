"""Выборка позиций отгрузок: период, канал, поиск по номенклатуре.

Общее основание двух страниц раздела. «Товары в отгрузках» сворачивает эти
позиции по товару, «Материалы в отгрузках» разворачивает их же по техкартам —
но отбирают обе одинаково, и разойдись отбор, две страницы за один период
показали бы разное число отгрузок.

Здесь только то, что про отгрузки: вид документа и канал продаж. Период,
поиск, страница и границы дня — в `api/common/selection.py`, потому что
у приёмок они точно такие же.
"""

from dataclasses import dataclass
from datetime import date

from django.db.models import QuerySet

from api.common import selection
from core.models import DocumentKind, DocumentPosition


@dataclass(frozen=True)
class Filters(selection.Filters):
    """Общее — в `selection.Filters`, своё у отгрузок — канал продаж.

    У приёмок канала нет вовсе: товар приходит от поставщика, а не через
    Озон. Держи мы это поле в общем классе, страница приёмок принимала бы
    `channel_id` и молча его игнорировала.
    """

    channel_id: int | None = None


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
    queryset = selection.within(queryset, date_from, date_to)

    if channel_id:
        queryset = queryset.filter(document__sales_channel_id=channel_id)

    return queryset


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
