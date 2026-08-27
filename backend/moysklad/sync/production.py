"""Синхронизация технологических карт."""

import logging

from django.db import transaction

from core.models import ProcessingPlan, ProcessingPlanMaterial, Product
from moysklad.client import MoySkladClient
from moysklad.limits import ApiDisabledRisk
from moysklad.parsing import parse_datetime, parse_decimal
from moysklad.sync.references import ms_id_from
from moysklad.sync.runner import (
    EntityOutcome,
    SyncRun,
    mark_missing_as_deleted,
    restore_returned,
    upsert,
)

logger = logging.getLogger(__name__)


@transaction.atomic
def _save_materials(plan: ProcessingPlan, rows: list[dict], products: dict) -> int:
    """Переписать состав техкарты целиком. Возвращает число пропущенных.

    Одной транзакцией: без неё сбой между удалением и вставкой оставит
    техкарту без состава, а сама техкарта будет считаться свежей.
    """
    materials = []
    skipped = 0

    for row in rows:
        product = products.get(ms_id_from(row.get("assortment")))
        if product is None:
            logger.warning(
                "Техкарта %s: материал не найден в зеркале", plan.name
            )
            skipped += 1
            continue

        materials.append(
            ProcessingPlanMaterial(
                plan=plan,
                product=product,
                # Единица берётся у товара: в строке техкарты своей нет,
                # количество указано в базовой единице номенклатуры.
                uom=product.uom,
                quantity=parse_decimal(row.get("quantity")) or 0,
            )
        )

    plan.materials.all().delete()
    ProcessingPlanMaterial.objects.bulk_create(materials)
    return skipped


def sync_processing_plans(client: MoySkladClient, run: SyncRun) -> EntityOutcome:
    """Техкарты вместе с составом.

    Состав тянется через `expand`: иначе на каждую из 89 техкарт уходил бы
    отдельный запрос, а корзина лимита общая с ботом.
    """
    outcome = EntityOutcome()
    skipped_plans = 0
    skipped_materials = 0

    products = {str(p.ms_id): p for p in Product.objects.all()}

    try:
        for row in client.iterate(
            "/entity/processingplan",
            {
                "expand": "materials,products,parametricMaterials",
                "filter": "archived=true;archived=false",
            },
        ):
            outcome.fetched += 1

            # Параметрическая техкарта держит состав в другом поле, и наш
            # разбор увидел бы её пустой: карта записалась бы, а материалы
            # молча исчезли. Таких сейчас нет, поддержки не пишем — но и терять
            # состав без следа нельзя.
            parametric = (row.get("parametricMaterials") or {}).get("rows")
            if parametric:
                logger.warning(
                    "Техкарта %s пропущена: параметрический состав пока "
                    "не поддерживается (%s строк)", row.get("name"), len(parametric),
                )
                skipped_plans += 1
                continue

            product_rows = (row.get("products") or {}).get("rows", [])
            if len(product_rows) > 1:
                # Одна карта выпускает несколько разных продуктов. Записать
                # состав первому значит приписать ему весь расход, а второй
                # выглядел бы как покупной. Таких карт нет — но появятся,
                # и это должно быть видно.
                logger.warning(
                    "Техкарта %s пропущена: выпускает %s продуктов, "
                    "распределение расхода между ними не реализовано",
                    row.get("name"), len(product_rows),
                )
                skipped_plans += 1
                continue

            if not product_rows:
                # Техкарта без продукта ничего не производит — считать по ней
                # нечего, а ссылка на несуществующий товар уронила бы запись.
                logger.warning("Техкарта %s пропущена: не указан продукт", row.get("name"))
                skipped_plans += 1
                continue

            # Именно assortment, а не сама строка: у строки продукта своя meta,
            # и её href ведёт на строку техкарты, а не на товар. Ошибка тихая —
            # товар «не находится», и техкарта молча выпадает из расчётов.
            product = products.get(ms_id_from(product_rows[0].get("assortment")))
            if product is None:
                logger.warning(
                    "Техкарта %s пропущена: продукт не найден в зеркале", row.get("name")
                )
                skipped_plans += 1
                continue

            output = parse_decimal(product_rows[0].get("quantity")) or 0
            if output <= 0:
                # На это число делят, считая расход на единицу продукции.
                logger.warning(
                    "Техкарта %s пропущена: объём выпуска %s", row.get("name"), output
                )
                skipped_plans += 1
                continue

            plan, created = upsert(
                ProcessingPlan,
                row["id"],
                run,
                {
                    "name": row.get("name", ""),
                    "folder": row.get("pathName", "") or "",
                    "product": product,
                    "output_quantity": output,
                    "archived": bool(row.get("archived")),
                    "ms_updated": parse_datetime(row.get("updated")),
                },
            )
            outcome.created += created
            outcome.updated += not created

            skipped_materials += _save_materials(
                plan, (row.get("materials") or {}).get("rows", []), products
            )

    except ApiDisabledRisk:
        raise
    except Exception as error:
        outcome.error = f"{type(error).__name__}: {error}"
        return outcome

    outcome.marked_deleted = mark_missing_as_deleted(ProcessingPlan, run)
    restore_returned(ProcessingPlan, run)
    outcome.extra = {
        "skipped_plans": skipped_plans,
        "skipped_materials": skipped_materials,
    }
    if skipped_plans or skipped_materials:
        logger.warning(
            "Техкарты: пропущено карт %s, материалов %s — расчёт производства "
            "по ним будет неполным",
            skipped_plans, skipped_materials,
        )

    return outcome
