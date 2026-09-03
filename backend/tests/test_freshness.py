"""Свежесть данных: отметка «данные на 14:32» в шапке каждой страницы."""

from datetime import timedelta

import pytest
from django.utils import timezone

from core.models import SyncKind, SyncRun, SyncStatus
from core.services.freshness import (
    documents_synced_at,
    oldest_of,
    stock_synced_at,
)

pytestmark = pytest.mark.django_db


# --- Свежесть данных ---------------------------------------------------------


def test_synced_at_uses_last_successful_run():
    """Отметка берётся с последнего успешного прогона, а не с последнего вообще.

    Прогон, оборвавшийся на середине, оставляет данные наполовину вчерашними.
    Показать его время — соврать ровно там, где отметка и существует,
    чтобы не врать.
    """
    good = timezone.now() - timedelta(hours=2)
    SyncRun.objects.create(
        kind=SyncKind.DOCUMENTS, status=SyncStatus.SUCCESS, finished_at=good
    )
    SyncRun.objects.create(
        kind=SyncKind.DOCUMENTS,
        status=SyncStatus.PARTIAL,
        finished_at=timezone.now(),
    )

    assert documents_synced_at() == good


def test_synced_at_ignores_other_kinds():
    """Прогон остатков не говорит ничего о свежести документов."""
    SyncRun.objects.create(
        kind=SyncKind.STATE, status=SyncStatus.SUCCESS, finished_at=timezone.now()
    )

    assert documents_synced_at() is None


# --- Страница, считающая по двум источникам ----------------------------------


def test_oldest_of_takes_the_laggard():
    """Страница свежа настолько, насколько свеж её самый отставший источник.

    «Расчёт производства» берёт продажи из документов (ночной прогон),
    а остатки из отчёта (каждые 10–15 минут). Возьми он младшую отметку —
    и обещал бы свежесть продажам, которых у нас нет.
    """
    old = timezone.now() - timedelta(days=1)
    fresh = timezone.now()
    assert oldest_of(old, fresh) == old
    assert oldest_of(fresh, old) == old


def test_oldest_of_is_silent_when_one_source_is_unknown():
    """Неизвестная отметка обнуляет обещание, а не игнорируется.

    «Данные на 12:37» рядом с остатками, которые не синхронизировались ни
    разу, — обещание, ничем не обеспеченное. Прочерк здесь честнее времени.
    """
    assert oldest_of(timezone.now(), None) is None
    assert oldest_of(None, None) is None


def test_stock_and_documents_are_different_marks():
    """Прогоны разных видов не подменяют друг друга.

    Ровно эта подмена и случилась 03.09: остатки в зеркале отставали
    на неделю, а страница показала бы время документов и выглядела свежей.
    """
    stock_moment = timezone.now()
    SyncRun.objects.create(
        kind=SyncKind.STATE, status=SyncStatus.SUCCESS, finished_at=stock_moment
    )
    assert stock_synced_at() == stock_moment
    assert documents_synced_at() is None
    assert oldest_of(documents_synced_at(), stock_synced_at()) is None
