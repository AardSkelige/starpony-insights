"""Синхронизация документов: отгрузки, приёмки и заказы поставщикам.

Позиции тянутся вместе с документом через `expand` — иначе на каждый документ
уходил бы отдельный запрос, а корзина лимита общая с ботом.

**Заказы поставщикам идут без позиций и раньше приёмок.** Без позиций —
потому что нужны только шапка и дата: что заказывали, известно из приёмки.
Раньше — потому что приёмка ссылается на заказ, и синхронизируй мы их
в обратном порядке, связывать было бы не с чем ровно один прогон,
а срок поставки всё это время показывался бы прочерком.
"""

import logging
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from core.models import (
    Counterparty,
    Document,
    DocumentKind,
    DocumentPosition,
    Product,
    SalesChannel,
    Uom,
)
from moysklad.client import MoySkladClient
from moysklad.limits import ApiDisabledRisk
from moysklad.parsing import parse_datetime, parse_decimal, parse_kopecks
from moysklad.sync.references import ms_id_from
from moysklad.sync.runner import (
    EntityOutcome,
    SyncRun,
    upsert,
)

logger = logging.getLogger(__name__)

# Сколько позиций подтягивать вместе с документом. У МойСклада есть потолок
# на глубину expand, и 100 позиций в документе — величина с большим запасом:
# в боевых данных максимум около двух десятков.
POSITIONS_LIMIT = 100


@transaction.atomic
def _save_positions(
    document: Document, rows: list[dict], products: dict, uoms: dict
) -> int:
    """Переписать позиции документа целиком. Возвращает число пропущенных.

    Позиции отдельно от документа не живут, поэтому здесь замена, а не upsert:
    сверять их построчно дороже, чем перезаписать десяток строк.

    Одной транзакцией: без неё сбой между удалением и вставкой оставляет
    документ вовсе без позиций, а сам документ при этом считается свежим.
    """
    positions = []
    skipped = 0
    for row in rows:
        product = products.get(ms_id_from(row.get("assortment")))
        if product is None:
            # Позиция ссылается на то, чего нет в зеркале: модификацию,
            # комплект или товар, не дошедший из-за сбоя. Пропускаем строку,
            # но не роняем документ — иначе одна позиция остановит всю
            # синхронизацию. Пропуски считаются: молча потерянная позиция
            # означает, что сумма позиций перестала сходиться с документом.
            kind = (row.get("assortment") or {}).get("meta", {}).get("type", "?")
            logger.warning(
                "Документ %s: позиция типа «%s» не найдена в зеркале",
                document.number, kind,
            )
            skipped += 1
            continue

        quantity = parse_decimal(row.get("quantity")) or Decimal(0)
        price = parse_decimal(row.get("price")) or Decimal(0)
        discount = parse_decimal(row.get("discount")) or Decimal(0)

        positions.append(
            DocumentPosition(
                document=document,
                product=product,
                uom=uoms.get(ms_id_from(row.get("uom"))) or product.uom,
                quantity=quantity,
                price_kopecks=price,
                discount=discount,
                # Считается из неокруглённых значений и сразу приводится
                # к целым копейкам: сумма строки обязана сходиться с суммой
                # документа, а хранимая цена для этого недостаточно точна —
                # у неё шесть знаков, а в учёте встречаются бесконечные дроби.
                total_kopecks=int(
                    (quantity * price * (Decimal(1) - discount / 100)).to_integral_value(
                        rounding=ROUND_HALF_UP
                    )
                ),
            )
        )

    document.positions.all().delete()
    DocumentPosition.objects.bulk_create(positions)
    return skipped


def sync_documents(
    client: MoySkladClient,
    run: SyncRun,
    *,
    kind: DocumentKind,
    path: str,
    with_positions: bool = True,
) -> EntityOutcome:
    """Один вид документов — код общий, различается только источник.

    `with_positions` выключается для заказов поставщикам: у них нас интересует
    только дата, а `expand=positions` тянул бы строки, которые никто не читает.
    """
    outcome = EntityOutcome()

    # Справочники в память: сотни документов, и обращение к базе на каждую
    # позицию превратило бы синхронизацию в тысячи мелких запросов.
    skipped_documents = 0
    skipped_positions = 0
    unlinked_supplies = 0

    products = {str(p.ms_id): p for p in Product.objects.all()}
    uoms = {str(u.ms_id): u for u in Uom.objects.all()}
    agents = {str(c.ms_id): c for c in Counterparty.objects.all()}
    channels = {str(c.ms_id): c for c in SalesChannel.objects.all()}
    # Заказы — только для приёмок, и только они: чужие виды документов
    # в этот словарь не попадают, чтобы ошибочная ссылка не связала приёмку
    # с отгрузкой.
    orders = {
        str(d.ms_id): d
        for d in Document.objects.filter(kind=DocumentKind.PURCHASE_ORDER)
    }

    params = {"limit": POSITIONS_LIMIT}
    if with_positions:
        params["expand"] = "positions"

    try:
        for row in client.iterate(path, params):
            outcome.fetched += 1

            agent = agents.get(ms_id_from(row.get("agent")))
            if agent is None:
                # Контрагента могли удалить в учёте — в выгрузке его уже нет,
                # а старые документы на него ссылаются. Пропускаем документ,
                # а не роняем сущность: иначе один давний документ навсегда
                # остановит синхронизацию отгрузок, и все данные протухнут.
                logger.warning(
                    "Документ %s пропущен: контрагент не найден в зеркале",
                    row.get("name"),
                )
                skipped_documents += 1
                continue

            moment = parse_datetime(row.get("moment"))
            if moment is None:
                # Дата — обязательное поле: без неё документ не попадёт
                # ни в один отчёт за период, а запись упала бы на ограничении
                # базы и увела бы за собой всю сущность.
                logger.warning(
                    "Документ %s пропущен: не разобрана дата %r",
                    row.get("name"), row.get("moment"),
                )
                skipped_documents += 1
                continue

            order_ms_id = ms_id_from(row.get("purchaseOrder"))
            order = orders.get(order_ms_id)
            if order_ms_id and order is None:
                # Приёмка ссылается на заказ, которого в зеркале нет: заказ
                # удалили в учёте либо он не дошёл в этом прогоне. Срок
                # поставки по такой приёмке не посчитается, и молчать об этом
                # нельзя — иначе медиана незаметно съедет на оставшихся парах.
                logger.warning(
                    "Приёмка %s: заказ %s не найден в зеркале — срок поставки "
                    "по ней не посчитается",
                    row.get("name"), order_ms_id,
                )
                unlinked_supplies += 1

            document, created = upsert(
                Document,
                row["id"],
                run,
                {
                    "kind": kind,
                    "number": row.get("name", ""),
                    "moment": moment,
                    "agent": agent,
                    "purchase_order": order,
                    "sales_channel": channels.get(ms_id_from(row.get("salesChannel"))),
                    # round, а не int: суммы приходят типом Float, и усечение
                    # превратило бы 1234.9999999 в 1234 — расхождение с учётом
                    # на копейку там, где оно обязано сходиться в ноль.
                    "total_kopecks": parse_kopecks(row.get("sum")),
                    "paid_kopecks": parse_kopecks(row.get("payedSum")),
                    "vat_kopecks": parse_kopecks(row.get("vatSum")),
                    "applicable": bool(row.get("applicable")),
                    "ms_updated": parse_datetime(row.get("updated")),
                },
            )
            outcome.created += created
            outcome.updated += not created

            if with_positions:
                skipped_positions += _save_positions(
                    document,
                    (row.get("positions") or {}).get("rows", []),
                    products,
                    uoms,
                )

    except ApiDisabledRisk:
        # Сквозь общий обработчик: предохранитель останавливает весь прогон,
        # а не только эту сущность. Продолжить — значит добить лимит,
        # общий с ботом, и потерять доступ к API до звонка в поддержку.
        raise
    except Exception as error:
        outcome.error = f"{type(error).__name__}: {error}"
        return outcome

    # Пометка исчезнувших — только по своему виду документов: отгрузки
    # и приёмки живут в одной таблице, и общая пометка снесла бы соседей.
    missing = Document.objects.filter(
        kind=kind, deleted_at__isnull=True
    ).exclude(last_seen_run=run)
    outcome.marked_deleted = missing.update(deleted_at=timezone.now())
    outcome.extra = {
        "skipped_documents": skipped_documents,
        "skipped_positions": skipped_positions,
        "unlinked_supplies": unlinked_supplies,
    }
    if skipped_documents or skipped_positions:
        logger.warning(
            "%s: пропущено документов %s, позиций %s — сумма позиций "
            "перестанет сходиться с суммой документа",
            kind, skipped_documents, skipped_positions,
        )
    if unlinked_supplies:
        logger.warning(
            "%s: приёмок без заказа в зеркале %s — срок поставки посчитается "
            "не по всей истории",
            kind, unlinked_supplies,
        )
    Document.objects.filter(kind=kind, deleted_at__isnull=False, last_seen_run=run).update(
        deleted_at=None
    )

    return outcome


def sync_demands(client: MoySkladClient, run: SyncRun) -> EntityOutcome:
    return sync_documents(client, run, kind=DocumentKind.DEMAND, path="/entity/demand")


def sync_purchase_orders(client: MoySkladClient, run: SyncRun) -> EntityOutcome:
    """Заказы поставщикам — только шапки, и обязательно до приёмок."""
    return sync_documents(
        client,
        run,
        kind=DocumentKind.PURCHASE_ORDER,
        path="/entity/purchaseorder",
        with_positions=False,
    )


def sync_supplies(client: MoySkladClient, run: SyncRun) -> EntityOutcome:
    return sync_documents(client, run, kind=DocumentKind.SUPPLY, path="/entity/supply")
