"""«Кто дал деньги»: выручка отгрузок по каналам за месяц.

Отдельно от пульса, потому что источник другой: здесь документы, а не отчёт
прибыльности. Смешивать их в одной карточке нельзя — суммы каналов сложатся
в отгруженное, а не в проданное, и рядом с маржой это читалось бы как одно
множество.

**Полосами, а не таблицей.** Вопрос к списку каналов один — «на ком мы
держимся», и отвечает на него длина. Список из девяти строк с суммами
отвечает тем же, но чтением.

**Канал не заведён — это тоже строка.** Отгрузки без канала существуют,
и спрятать их значило бы не досчитать выручку: доли перестали бы давать
сто процентов, а причина осталась бы невидимой.
"""

from dataclasses import dataclass

from django.db.models import Count, Sum

from api.home.services.period import Window
from core.models import DocumentKind
from core.services.documents import alive

# Девятая строка складывается в «Другое», а не получает девятый цвет:
# повтор оттенка — это утверждение «та же сущность» (`DESIGN.md` §1).
# Здесь ряд один и рисуется `primary`, но предел тот же — список,
# который не читается с одного взгляда, перестаёт быть ответом.
TOP_ROWS = 7

OTHER = "Другие каналы"
WITHOUT = "Канал не указан"


@dataclass(frozen=True)
class ChannelRow:
    name: str
    revenue_kopecks: int
    documents: int


def of(window: Window) -> list[ChannelRow]:
    rows = [
        ChannelRow(
            name=row["sales_channel__name"] or WITHOUT,
            revenue_kopecks=row["total"] or 0,
            documents=row["documents"],
        )
        for row in alive(DocumentKind.DEMAND)
        .filter(moment__date__gte=window.current.first, moment__date__lte=window.current.last)
        .values("sales_channel__name")
        .annotate(total=Sum("total_kopecks"), documents=Count("id"))
    ]
    rows = [row for row in rows if row.revenue_kopecks]
    rows.sort(key=lambda row: (-row.revenue_kopecks, row.name))

    if len(rows) <= TOP_ROWS + 1:
        return rows

    tail = rows[TOP_ROWS:]
    return rows[:TOP_ROWS] + [
        ChannelRow(
            name=OTHER,
            revenue_kopecks=sum(row.revenue_kopecks for row in tail),
            documents=sum(row.documents for row in tail),
        )
    ]
