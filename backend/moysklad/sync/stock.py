"""Синхронизация остатков — то, что идёт каждые 10–15 минут."""

import logging

from core.models import Product, Stock
from moysklad.client import MoySkladClient
from moysklad.limits import ApiDisabledRisk
from moysklad.parsing import parse_decimal
from moysklad.sync.references import ms_id_from
from moysklad.sync.runner import EntityOutcome, SyncRun

logger = logging.getLogger(__name__)

# Какую долю известных позиций отчёт должен вернуть, чтобы считаться полным.
# Ниже — не обнуляем пропавшее: скорее всего, МойСклад пересчитывает остатки,
# и через 15 минут они вернутся сами.
MIN_REPORT_COMPLETENESS = 0.8


def sync_stock(client: MoySkladClient, run: SyncRun) -> EntityOutcome:
    """Остатки, резервы, себестоимость и время лежания.

    Один запрос на весь склад: `/report/stock/all` отдаёт сразу всё нужное,
    включая `stockDays`. Он весит 5 единиц лимита вместо одной — но это
    несравнимо дешевле, чем спрашивать по каждому из 380 товаров.
    """
    outcome = EntityOutcome()
    products = {str(p.ms_id): p for p in Product.objects.all()}
    skipped = 0
    seen: set[int] = set()

    try:
        # stockMode передаётся внутри filter, а не отдельным параметром.
        # Отдельным он молча игнорируется: сейчас это незаметно, потому что
        # `all` и есть значение по умолчанию, но при смене на positiveOnly
        # отчёт продолжил бы отдавать всё.
        for row in client.iterate("/report/stock/all", {"filter": "stockMode=all"}):
            outcome.fetched += 1

            product = products.get(ms_id_from(row))
            if product is None:
                # Отчёт отдаёт и то, чего нет в зеркале: модификации,
                # комплекты. Пропускаем, но считаем — молчаливая потеря
                # остатка означает неверный расчёт закупки.
                skipped += 1
                continue

            _, created = Stock.objects.update_or_create(
                product=product,
                defaults={
                    "quantity": parse_decimal(row.get("stock")) or 0,
                    "reserved": parse_decimal(row.get("reserve")) or 0,
                    "in_transit": parse_decimal(row.get("inTransit")) or 0,
                    "cost_kopecks": parse_decimal(row.get("price")) or 0,
                    "stock_days": row.get("stockDays"),
                },
            )
            outcome.created += created
            outcome.updated += not created
            seen.add(product.pk)

    except ApiDisabledRisk:
        raise
    except Exception as error:
        outcome.error = f"{type(error).__name__}: {error}"
        return outcome

    # Товар, пропавший из отчёта, обнуляется — но только если отчёт похож
    # на полный.
    #
    # Документация прямо предупреждает: «в отчёт попадают только товары
    # с уже пересчитанными остатками на момент запроса». Пересчёт не мгновенный,
    # поэтому товар может выпасть из одного прогона и вернуться в следующий.
    # Безусловное обнуление стирало бы его остаток каждые 15 минут, и расчёт
    # закупки видел бы ноль там, где товар есть на складе.
    zeroed = 0
    known = Stock.objects.count()
    complete_enough = outcome.fetched > 0 and (
        known == 0 or outcome.fetched >= known * MIN_REPORT_COMPLETENESS
    )

    if complete_enough:
        zeroed = Stock.objects.exclude(product_id__in=seen).update(
            quantity=0, reserved=0, in_transit=0, stock_days=None
        )
    elif known:
        logger.warning(
            "Остатки: отчёт вернул %s позиций против %s известных — похоже "
            "на пересчёт в МойСкладе. Обнуление пропущено, старые остатки "
            "сохранены до следующего прогона.",
            outcome.fetched, known,
        )

    outcome.extra = {"skipped": skipped, "zeroed": zeroed, "partial": not complete_enough}
    if skipped:
        logger.warning(
            "Остатки: %s позиций отчёта не найдены в зеркале — расчёт закупки "
            "по ним будет неполным", skipped,
        )

    return outcome
