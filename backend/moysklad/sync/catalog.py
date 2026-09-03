"""Синхронизация номенклатуры."""

import logging

from core.models import Product, ProductKind, Uom
from moysklad.client import MoySkladClient
from moysklad.limits import ApiDisabledRisk
from moysklad.parsing import parse_datetime, parse_decimal
from moysklad.sync.runner import (
    EntityOutcome,
    SyncRun,
    mark_missing_as_deleted,
    restore_returned,
    upsert,
)

logger = logging.getLogger(__name__)


def folder_path(row: dict) -> str:
    """Путь группы товара — по нему выводится линейка продукции.

    Собирается из двух полей, а не берётся из одного. `pathName` — это путь
    **до** группы, без её собственного имени: у товара в «Готовая продукция /
    Репеллент» там лежит «Готовая продукция». Взять его одно значило бы
    свалить все 90 товаров готовой продукции в одну группу и потерять семь
    линеек учёта — а поле при этом выглядит заполненным, и потеря молчит.
    """
    folder = row.get("productFolder") or {}
    parts = [folder.get("pathName") or "", folder.get("name") or ""]
    return "/".join(part for part in parts if part)


def sync_uoms(client: MoySkladClient, run: SyncRun) -> EntityOutcome:
    """Справочник единиц измерения — 59 строк одним запросом.

    Идёт до товаров: в товаре единица приходит только ссылкой, и без этого
    справочника её негде взять.
    """
    outcome = EntityOutcome()

    try:
        for row in client.iterate("/entity/uom"):
            outcome.fetched += 1
            _, created = upsert(
                Uom,
                row["id"],
                run,
                {
                    "name": row.get("name", ""),
                    "description": row.get("description", "") or "",
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


def uom_from_ref(ref: dict | None, cache: dict[str, Uom]) -> Uom | None:
    """Единица измерения по ссылке из товара.

    Ссылка выглядит как `.../entity/uom/8e2eb543-...`, названия в ней нет —
    берём из справочника, загруженного заранее.
    """
    href = (ref or {}).get("meta", {}).get("href", "")
    if not href:
        return None
    return cache.get(href.rsplit("/", 1)[-1])


def sync_products(client: MoySkladClient, run: SyncRun) -> EntityOutcome:
    """Товары, материалы и услуги.

    Услуги — отдельная сущность API, но в документах они такие же позиции.
    Их всего две («Доставка» и «Доставка для закупок»), зато встречаются
    в 31 позиции, и без них стоимость закупки занижена.
    """
    outcome = EntityOutcome()
    # Справочник целиком в память: 59 строк, зато ни одного лишнего запроса
    # и ни одного обращения к базе внутри цикла.
    uoms = {str(u.ms_id): u for u in Uom.objects.all()}

    # `archived=true;archived=false` — и архивные тоже. По умолчанию API
    # отдаёт только действующие, а документы ссылаются на архивные: 66 товаров
    # из 380 лежат в архиве, и на них приходится 67 позиций приёмок. Без них
    # позиции молча теряются, и стоимость закупки оказывается занижена.
    #
    # В интерфейсе архивные скрываются по полю `archived`, но в зеркале они
    # обязаны быть — иначе история документов рвётся.
    ARCHIVED_TOO = "archived=true;archived=false"

    sources = (
        (
            "/entity/product",
            ProductKind.PRODUCT,
            {"expand": "productFolder", "filter": ARCHIVED_TOO},
        ),
        ("/entity/service", ProductKind.SERVICE, {"filter": ARCHIVED_TOO}),
    )

    try:
        for path, kind, params in sources:
            for row in client.iterate(path, params):
                outcome.fetched += 1

                # buyPrice приходит как {"value": 123.0, "currency": {...}}
                # в копейках. Валюта всегда рубль — проверено на всех 386
                # документах боевого аккаунта.
                buy_price = (row.get("buyPrice") or {}).get("value")

                _, created = upsert(
                    Product,
                    row["id"],
                    run,
                    {
                        "kind": kind,
                        "name": row.get("name", ""),
                        "article": row.get("article", "") or "",
                        "code": row.get("code", "") or "",
                        "folder": folder_path(row),
                        "uom": uom_from_ref(row.get("uom"), uoms),
                        "archived": bool(row.get("archived")),
                        "buy_price_kopecks": parse_decimal(buy_price),
                        "min_balance": parse_decimal(row.get("minimumBalance")),
                        "ms_updated": parse_datetime(row.get("updated")),
                    },
                )
                if created:
                    outcome.created += 1
                else:
                    outcome.updated += 1

    except ApiDisabledRisk:
        # Сквозь общий обработчик: предохранитель останавливает весь прогон,
        # а не только эту сущность. Продолжить — значит добить лимит,
        # общий с ботом, и потерять доступ к API до звонка в поддержку.
        raise
    except Exception as error:
        # Прогон продолжится по другим сущностям, а эта будет помечена
        # неудачной — и «данные на …» не станет врать про свежесть.
        outcome.error = f"{type(error).__name__}: {error}"
        return outcome

    # Пометка исчезнувших — только после полного успешного обхода.
    outcome.marked_deleted = mark_missing_as_deleted(Product, run)
    restored = restore_returned(Product, run)
    if restored:
        logger.info("Вернулись в учёт: %s товаров", restored)

    return outcome
