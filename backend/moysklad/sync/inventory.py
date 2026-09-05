"""Синхронизация инвентаризаций — пересчётов склада.

Позиции тянутся вместе с документом через `expand`: инвентаризаций в учёте
единицы, а отдельный запрос за строками каждой стоил бы из корзины лимита,
общей с ботом.

**Расхождение сохраняется таким, каким его отдал учёт.** Считать его самим
из `quantity` и `calculatedQuantity` нельзя: инвентаризация, созданная
через API с `positions` в теле, приходит с расчётным остатком, равным
фактическому (`moysklad/CLAUDE.md`), — и наша разность выдала бы честный ноль
за результат расчёта. Здесь такой документ, наоборот, обязан быть заметен,
поэтому строки, где `correctionAmount` не сходится с разностью количеств,
считаются и попадают в предупреждение.
"""

import logging

from django.db import transaction

from core.models import Inventory, InventoryPosition, Product
from moysklad.client import MoySkladClient
from moysklad.limits import ApiDisabledRisk
from moysklad.parsing import parse_datetime, parse_decimal, parse_kopecks
from moysklad.sync.references import ms_id_from
from moysklad.sync.runner import (
    EntityOutcome,
    SyncRun,
    mark_missing_as_deleted,
    restore_returned,
    upsert,
)

logger = logging.getLogger(__name__)

# Столько позиций подтягивается вместе с документом. В боевых данных
# самая крупная инвентаризация — 15 строк, запас здесь с избытком.
POSITIONS_LIMIT = 100


@transaction.atomic
def _save_positions(
    inventory: Inventory, rows: list[dict], products: dict
) -> tuple[int, int]:
    """Переписать позиции целиком. Возвращает (пропущено, расхождений не сошлось).

    Замена, а не построчный upsert: позиции без документа не живут, и сверять
    их дороже, чем перезаписать десяток строк. Одной транзакцией — иначе сбой
    между удалением и вставкой оставит документ без позиций, а сам документ
    будет выглядеть свежим.
    """
    positions = []
    skipped = 0
    mismatched = 0

    for row in rows:
        product = products.get(ms_id_from(row.get("assortment")))
        if product is None:
            # Строка ссылается на то, чего нет в зеркале: модификацию,
            # комплект или товар, не дошедший из-за сбоя. Пропускаем строку,
            # не роняя документ, но считаем: молча потерянная позиция —
            # это расхождение, о котором никто не узнает.
            kind = (row.get("assortment") or {}).get("meta", {}).get("type", "?")
            logger.warning(
                "Инвентаризация %s: позиция типа «%s» не найдена в зеркале",
                inventory.number, kind,
            )
            skipped += 1
            continue

        counted = parse_decimal(row.get("quantity")) or 0
        calculated = parse_decimal(row.get("calculatedQuantity")) or 0
        correction = parse_decimal(row.get("correctionAmount")) or 0

        if correction != counted - calculated:
            # Либо документ заведён через API с позициями в теле и расчётный
            # остаток в нём подменён, либо учёт считает разницу иначе, чем
            # мы предполагаем. И то и другое означает, что странице нельзя
            # доверять числу, — и узнать об этом надо здесь, а не по жалобе.
            mismatched += 1

        positions.append(
            InventoryPosition(
                inventory=inventory,
                product=product,
                counted=counted,
                calculated=calculated,
                correction_amount=correction,
                correction_sum_kopecks=parse_kopecks(row.get("correctionSum")),
                price_kopecks=parse_decimal(row.get("price")) or 0,
            )
        )

    inventory.positions.all().delete()
    InventoryPosition.objects.bulk_create(positions)
    return skipped, mismatched


def sync_inventories(client: MoySkladClient, run: SyncRun) -> EntityOutcome:
    """Инвентаризации вместе с позициями."""
    outcome = EntityOutcome()

    products = {str(p.ms_id): p for p in Product.objects.all()}

    skipped_documents = 0
    skipped_positions = 0
    mismatched_corrections = 0
    stores: set[str] = set()
    # Пришедшее из учёта, но осознанно пропущенное. Без этого списка такая
    # строка не получит штамп прогона и будет помечена удалённой — то есть
    # исчезнет из расчётов, хотя документ в учёте есть.
    skipped_ids: list[str] = []

    try:
        for row in client.iterate(
            "/entity/inventory",
            {"limit": POSITIONS_LIMIT, "expand": "positions,store"},
        ):
            outcome.fetched += 1

            moment = parse_datetime(row.get("moment"))
            if moment is None:
                # Дата — то, ради чего страница существует: «когда считали
                # последний раз». Документ без неё не ответит ни на один
                # вопрос, а запись упала бы на ограничении базы и увела
                # за собой всю сущность.
                logger.warning(
                    "Инвентаризация %s пропущена: не разобрана дата %r",
                    row.get("name"), row.get("moment"),
                )
                skipped_documents += 1
                skipped_ids.append(row["id"])
                continue

            store = row.get("store") or {}
            store_id = ms_id_from(store)
            if store_id:
                stores.add(store_id)

            inventory, created = upsert(
                Inventory,
                row["id"],
                run,
                {
                    "number": row.get("name", ""),
                    "store_name": store.get("name", ""),
                    "moment": moment,
                    "description": row.get("description") or "",
                    "total_kopecks": parse_kopecks(row.get("sum")),
                    "ms_updated": parse_datetime(row.get("updated")),
                },
            )
            outcome.created += created
            outcome.updated += not created

            skipped, mismatched = _save_positions(
                inventory, (row.get("positions") or {}).get("rows", []), products
            )
            skipped_positions += skipped
            mismatched_corrections += mismatched

    except ApiDisabledRisk:
        # Сквозь общий обработчик: предохранитель останавливает весь прогон,
        # а не одну сущность.
        raise
    except Exception as error:
        outcome.error = f"{type(error).__name__}: {error}"
        return outcome

    outcome.marked_deleted = mark_missing_as_deleted(
        Inventory, run, keep_ms_ids=skipped_ids
    )
    restore_returned(Inventory, run)

    outcome.extra = {
        "skipped_documents": skipped_documents,
        "skipped_positions": skipped_positions,
        "mismatched_corrections": mismatched_corrections,
        "stores": len(stores),
    }

    if skipped_documents or skipped_positions:
        logger.warning(
            "Инвентаризации: пропущено документов %s, позиций %s — расхождения "
            "по ним не увидит никто",
            skipped_documents, skipped_positions,
        )
    if mismatched_corrections:
        logger.warning(
            "Инвентаризации: у %s позиций расхождение из учёта не равно разнице "
            "количеств. Либо документ заведён через API с позициями в теле "
            "(расчётный остаток в нём подменён), либо разница считается иначе.",
            mismatched_corrections,
        )
    missing_stores = Inventory.objects.filter(
        last_seen_run=run, store_name=""
    ).count()
    if missing_stores:
        # Без склада «пересчитали 06.08» перестаёт быть ответом: пересчитали
        # **где**, и на двух других складах товар в этот день не считали.
        # Пустое имя означает, что `expand` не доехал, — молчать об этом
        # нельзя, страница показала бы пересчёт всего склада вместо одного.
        logger.warning(
            "Инвентаризации: у %s документов не приехало название склада — "
            "проверьте expand=store",
            missing_stores,
        )

    return outcome
