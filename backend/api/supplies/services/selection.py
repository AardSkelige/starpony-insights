"""Выборка позиций приёмок: период, поставщик, поиск по номенклатуре.

Основание раздела. Общее с отгрузками — период, поиск, страница, границы
дня — живёт в `api/common/selection.py`; здесь только то, что про приёмки.

**Своё у приёмок — поставщик вместо канала продаж.** Канала у приёмки нет:
товар приходит от контрагента, а не через Озон. Поэтому фильтр раздела
свой, и общим классом фильтров он быть не может — приняв `channel_id`,
страница молча проигнорировала бы его.
"""

from dataclasses import dataclass
from datetime import date

from django.db.models import QuerySet

from api.common import selection
from core.models import DocumentKind, DocumentPosition
from core.services.documents import alive, positions_in


@dataclass(frozen=True)
class Filters(selection.Filters):
    """Общее — в `selection.Filters`, своё у приёмок — поставщик."""

    supplier_id: int | None = None


def supply_positions(
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    supplier_id: int | None = None,
) -> QuerySet[DocumentPosition]:
    """Позиции приёмок, попавшие в период и к поставщику.

    Что считается существующей приёмкой, знает `core.services.documents.alive`:
    то же утверждение нужно «Поставщикам», которые считают по документам,
    а не по строкам. Разойдись эти два места — страницы за один период
    показали бы разные приёмки, и разошлись бы молча.
    """
    queryset = positions_in(alive(DocumentKind.SUPPLY))
    queryset = selection.within(queryset, date_from, date_to)

    if supplier_id:
        queryset = queryset.filter(document__agent_id=supplier_id)

    return queryset


def suppliers(
    *, date_from: date | None = None, date_to: date | None = None
) -> list[dict]:
    """Поставщики, встречающиеся в приёмках периода, — для списка фильтра.

    Фильтр по поставщику и поиск сняты намеренно, ровно как у каналов
    в отгрузках: оставь мы поставщика — после выбора «Лемун» в списке
    остался бы один «Лемун», и переключиться было бы нечем, кроме сброса
    всех фильтров.

    Их двадцать два — обычный выпадающий список справляется. Понадобится
    поиск внутри списка (сотня и больше) — это правка одного компонента
    фильтров, а не контракта.
    """
    rows = (
        supply_positions(date_from=date_from, date_to=date_to)
        .values("document__agent_id", "document__agent__name")
        .distinct()
        .order_by("document__agent__name")
    )
    return [
        {"id": row["document__agent_id"], "name": row["document__agent__name"]}
        for row in rows
    ]
