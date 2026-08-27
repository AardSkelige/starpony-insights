"""Свежесть данных: «данные на 14:32» в шапке каждой страницы.

Отдельным модулем, а не полем в каждом разделе: отметку показывают все десять
страниц, и вопрос «на какой момент эти числа» один и тот же для всех.

Берётся время последнего **успешного** прогона, а не последнего вообще.
Прогон, оборвавшийся на середине, оставляет данные наполовину вчерашними —
показать его время значило бы соврать ровно в том месте, которое существует,
чтобы не врать.
"""

from datetime import datetime

from core.models import SyncKind, SyncRun, SyncStatus


def last_success(kind: str) -> datetime | None:
    """Когда данные этого вида обновились в последний раз без потерь."""
    run = (
        SyncRun.objects.filter(kind=kind, status=SyncStatus.SUCCESS)
        .exclude(finished_at=None)
        .order_by("-finished_at")
        .first()
    )
    return run.finished_at if run else None


def documents_synced_at() -> datetime | None:
    """Отметка для разделов, считающих по документам: отгрузки, приёмки, маржа."""
    return last_success(SyncKind.DOCUMENTS)
