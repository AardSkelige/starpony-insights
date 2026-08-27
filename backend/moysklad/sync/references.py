"""Синхронизация справочников, на которые ссылаются документы.

Отдельно от самих документов: это разные сущности с разной частотой изменений,
и держать их вместе значило бы читать двести строк ради одной функции.
"""

import logging

from core.models import Counterparty, SalesChannel
from moysklad.client import MoySkladClient
from moysklad.limits import ApiDisabledRisk
from moysklad.parsing import parse_datetime
from moysklad.sync.runner import (
    EntityOutcome,
    SyncRun,
    mark_missing_as_deleted,
    restore_returned,
    upsert,
)

logger = logging.getLogger(__name__)


def ms_id_from(ref: dict | None) -> str | None:
    """Идентификатор из ссылки вида `.../entity/counterparty/<uuid>`."""
    href = (ref or {}).get("meta", {}).get("href", "")
    return href.rsplit("/", 1)[-1] if href else None


def sync_counterparties(client: MoySkladClient, run: SyncRun) -> EntityOutcome:
    outcome = EntityOutcome()

    try:
        for row in client.iterate("/entity/counterparty"):
            outcome.fetched += 1
            _, created = upsert(
                Counterparty,
                row["id"],
                run,
                {
                    "name": row.get("name", ""),
                    "inn": row.get("inn", "") or "",
                    "archived": bool(row.get("archived")),
                    "ms_updated": parse_datetime(row.get("updated")),
                },
            )
            outcome.created += created
            outcome.updated += not created
    except ApiDisabledRisk:
        # Сквозь общий обработчик: предохранитель останавливает весь прогон,
        # а не только эту сущность. Продолжить — значит добить лимит,
        # общий с ботом, и потерять доступ к API до звонка в поддержку.
        raise
    except Exception as error:
        outcome.error = f"{type(error).__name__}: {error}"
        return outcome

    outcome.marked_deleted = mark_missing_as_deleted(Counterparty, run)
    restore_returned(Counterparty, run)
    return outcome


def sync_sales_channels(client: MoySkladClient, run: SyncRun) -> EntityOutcome:
    outcome = EntityOutcome()

    try:
        for row in client.iterate("/entity/saleschannel"):
            outcome.fetched += 1
            _, created = upsert(
                SalesChannel,
                row["id"],
                run,
                {
                    "name": row.get("name", ""),
                    "type": row.get("type", "") or "",
                    "ms_updated": parse_datetime(row.get("updated")),
                },
            )
            outcome.created += created
            outcome.updated += not created
    except ApiDisabledRisk:
        # Сквозь общий обработчик: предохранитель останавливает весь прогон,
        # а не только эту сущность. Продолжить — значит добить лимит,
        # общий с ботом, и потерять доступ к API до звонка в поддержку.
        raise
    except Exception as error:
        outcome.error = f"{type(error).__name__}: {error}"
        return outcome

    outcome.marked_deleted = mark_missing_as_deleted(SalesChannel, run)
    restore_returned(SalesChannel, run)
    return outcome
