"""Свежесть данных: отметка «данные на 14:32» в шапке каждой страницы."""

from datetime import timedelta

import pytest
from django.utils import timezone

from core.models import SyncKind, SyncRun, SyncStatus
from core.services.freshness import documents_synced_at

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
