"""Синхронизация справочников, на которые ссылаются документы.

Отдельно от самих документов: это разные сущности с разной частотой изменений,
и держать их вместе значило бы читать двести строк ради одной функции.
"""

import logging

from core.models import Contract, ContractType, Counterparty, SalesChannel
from moysklad.client import MoySkladClient
from moysklad.limits import ApiDisabledRisk
from moysklad.parsing import attribute_int, parse_datetime
from moysklad.sync.runner import (
    EntityOutcome,
    SyncRun,
    mark_missing_as_deleted,
    restore_returned,
    upsert,
)

logger = logging.getLogger(__name__)


def ms_id_from(ref: dict | None) -> str | None:
    """Идентификатор из ссылки вида `.../entity/counterparty/<uuid>`.

    Параметры запроса отрезаются: в отчёте об остатках ссылка приходит
    как `.../entity/product/<uuid>?expand=supplier`, и без этого в идентификатор
    попадал хвост `?expand=supplier`. Ошибка тихая — товар «не находится»,
    и все 253 позиции остатков молча пропадали.
    """
    href = (ref or {}).get("meta", {}).get("href", "")
    if not href:
        return None
    return href.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]


# Названия доп. полей в учёте. По названию, а не по идентификатору:
# идентификатор свой в каждом аккаунте.
DEFERRAL_FIELD = "Срок отсрочки (дней)"

# И архивные тоже. По умолчанию API отдаёт только действующие, а документы
# ссылаются на архивных: проверено 02.09 — в учёте 107 контрагентов, из них
# 2 в архиве, и в зеркало они не попадали вовсе.
#
# Без них документ на архивного контрагента пропускается целиком: он выпадает
# из выручки, маржи и каналов продаж — молча, потому что пропуск виден только
# счётчиком в логе. Ровно та же ошибка, что была с 66 архивными товарами,
# и лечится она так же (`sync/catalog.py`).
ARCHIVED_TOO = "archived=true;archived=false"


def sync_counterparties(client: MoySkladClient, run: SyncRun) -> EntityOutcome:
    outcome = EntityOutcome()

    try:
        # Доп. поля приходят прямо в объекте — `expand` для них не нужен
        # и был бы вреден: при limit больше 100 он молча игнорируется,
        # и отсрочка не доехала бы вовсе.
        for row in client.iterate(
            "/entity/counterparty", {"filter": ARCHIVED_TOO}
        ):
            outcome.fetched += 1
            _, created = upsert(
                Counterparty,
                row["id"],
                run,
                {
                    "name": row.get("name", ""),
                    "inn": row.get("inn", "") or "",
                    "archived": bool(row.get("archived")),
                    "deferral_days": attribute_int(
                        row.get("attributes"), DEFERRAL_FIELD
                    ),
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


def sync_contracts(client: MoySkladClient, run: SyncRun) -> EntityOutcome:
    """Договоры. Идут после контрагентов и до документов.

    Порядок обязателен: договор ссылается на контрагента, а отгрузка и отчёт
    комиссионера — на договор. В обратном порядке связь не установилась бы
    ни у одного документа, и весь товар, ушедший на реализацию, попал бы
    в раздел «Сроки оплаты» как безнадёжный долг.
    """
    outcome = EntityOutcome()
    agents = {str(c.ms_id): c for c in Counterparty.objects.all()}
    skipped = 0
    # Пропущенные — не исчезнувшие. Без этого списка они попали бы под пометку
    # удаления и были бы посчитаны второй раз, уже как «исчезли из учёта».
    skipped_ids: list[str] = []

    try:
        for row in client.iterate("/entity/contract", {"filter": ARCHIVED_TOO}):
            outcome.fetched += 1

            agent = agents.get(ms_id_from(row.get("agent")))
            if agent is None:
                # Контрагента нет в зеркале — договор повесить не на что.
                # Пропускаем строку, но считаем: молча потерянный договор
                # комиссии превращает реализацию в мнимый долг.
                logger.warning(
                    "Договор %s пропущен: контрагент не найден в зеркале",
                    row.get("name"),
                )
                skipped += 1
                skipped_ids.append(row["id"])
                continue

            # Тип приходит как Commission / Sales; в учёте купли-продажа —
            # значение по умолчанию и может не прийти вовсе.
            raw_type = (row.get("contractType") or "").lower()
            contract_type = (
                ContractType.COMMISSION
                if raw_type == "commission"
                else ContractType.SALES
            )

            _, created = upsert(
                Contract,
                row["id"],
                run,
                {
                    "name": row.get("name", ""),
                    "contract_type": contract_type,
                    "agent": agent,
                    "archived": bool(row.get("archived")),
                    "ms_updated": parse_datetime(row.get("updated")),
                },
            )
            outcome.created += created
            outcome.updated += not created
    except ApiDisabledRisk:
        raise
    except Exception as error:
        outcome.error = f"{type(error).__name__}: {error}"
        return outcome

    outcome.marked_deleted = mark_missing_as_deleted(
        Contract, run, keep_ms_ids=skipped_ids
    )
    restore_returned(Contract, run)
    outcome.extra = {"skipped": skipped}
    if skipped:
        logger.warning(
            "Договоров без контрагента в зеркале: %s — отгрузки по ним "
            "будут считаться обычными продажами", skipped,
        )
    return outcome


def sync_sales_channels(client: MoySkladClient, run: SyncRun) -> EntityOutcome:
    outcome = EntityOutcome()

    try:
        # Архивных каналов на 02.09 нет ни одного, фильтр стоит на будущее:
        # заархивированный канал перестал бы приходить, и отгрузки на него
        # молча теряли бы канал — `sales_channel` обнуляется через SET_NULL,
        # документ при этом сохраняется. Раздел «Каналы продаж» показал бы
        # часть выручки в «без канала», и списать это было бы не на что.
        for row in client.iterate("/entity/saleschannel", {"filter": ARCHIVED_TOO}):
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
