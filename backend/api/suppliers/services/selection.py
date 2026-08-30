"""Выборка раздела «Поставщики»: приёмки периода, а не их строки.

Отличие от соседнего раздела в единице счёта. «Материалы в приёмках» считают
по строкам — там вопрос «что и почём закупали». Здесь вопрос «кто, на сколько
и как часто», и единица — сам документ: приёмка это одна поставка.

Что считается существующей приёмкой, знает `core.services.documents.alive` —
общее с соседями утверждение о домене. Период — общий слой API.

**Справочника для сужения здесь нет.** У отгрузок это канал продаж,
у «Материалов в приёмках» — поставщик. Здесь поставщик и есть строка таблицы:
выбери его фильтром — и в списке останется он один, а переключиться будет
нечем, кроме сброса. Сужают период и поиск по названию.
"""

from dataclasses import dataclass
from datetime import date

from django.db.models import QuerySet

from api.common import selection
from core.models import Document, DocumentKind
from core.services.documents import alive


@dataclass(frozen=True)
class Filters(selection.Filters):
    """Фильтры страницы. Своё у неё — только порядок строк.

    Поиск сужает поставщиков по названию, период — приёмки. Разные вещи:
    период меняет то, что посчитано, а поиск — только то, что показано.
    """

    ordering: str = "-amount"


def supplies(
    *, date_from: date | None = None, date_to: date | None = None
) -> QuerySet[Document]:
    """Приёмки периода вместе с поставщиком и вызвавшим их заказом.

    Связи подтягиваются здесь, а не по месту: без заказа срок поставки стоил
    бы запроса на строку, а без контрагента — ещё одного. На 93 приёмках это
    незаметно и станет заметно ровно тогда, когда история дорастёт до тысяч.
    """
    queryset = alive(DocumentKind.SUPPLY).select_related("agent", "purchase_order")
    return selection.within(queryset, date_from, date_to, field="moment")
