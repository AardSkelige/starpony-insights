"""Себестоимость из FIFO → тип цены «Себестоимость» в карточке товара.

МойСклад считает FIFO-себестоимость сам, но в карточку товара её не кладёт:
тип цены «Себестоимость» остаётся пустым, пока туда кто-нибудь не запишет.
Этим и занят этот модуль — ради самого учёта, не ради наших страниц.

**Число берётся из Postgres, а не из API.** Тот же `/report/stock/all` синк
остатков обходит каждые 15 минут, и в зеркале оно свежее, чем у прежнего
демона с его пятичасовым шагом. Ходить за ним второй раз — платить пять
единиц общего с ботом лимита за то, что уже лежит рядом (`CLAUDE.md` §1).

**В PUT уходит одна цена, а не весь набор.** Документация прямо обещает:
цены продажи обновляются как элементы вложенной коллекции, и тип цены,
не переданный в теле, не изменяется. Прежний демон вычитывал все цены товара
и слал обратно целиком — лишняя работа и лишний риск затереть цену, которую
человек поправил между чтением и записью.
"""

import logging
from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone

from core.models import ProductKind, Stock, WritebackKind
from moysklad.client import MoySkladClient
from moysklad.limits import ApiDisabledRisk
from moysklad.writeback.journal import (
    ChangeLimitReached,
    WritebackRun,
    WritebackSession,
)

logger = logging.getLogger(__name__)

COST_PRICE_TYPE = "Себестоимость"
DATE_FIELD = "Дата обновления себестоимости"


class ReferenceMissing(RuntimeError):
    """В учёте нет того, во что писать. Заводится руками, кодом не создаётся."""


def _round_kopecks(value: Decimal) -> int:
    """Дробные копейки — в целые: тип цены хранит целое число копеек.

    Округление вверх с половины, а не усечение: `int(Decimal("11841.9"))`
    дал бы 11841, и карточка расходилась бы с отчётом на копейку у каждого
    второго товара — дробная себестоимость у 150 позиций из 255.
    """
    return int(value.to_integral_value(rounding=ROUND_HALF_UP))


def _fetch_price_type(client: MoySkladClient) -> dict:
    """Мета типа цены «Себестоимость»."""
    # Возвращает голый массив, а не объект с `rows`, — поэтому не `iterate`.
    for row in client.get("/context/companysettings/pricetype") or []:
        if row.get("name") == COST_PRICE_TYPE:
            return row["meta"]
    raise ReferenceMissing(
        f"В учёте нет типа цены «{COST_PRICE_TYPE}». Заведите его в МойСкладе: "
        f"настройки компании → типы цен."
    )


def _fetch_currency(client: MoySkladClient) -> dict:
    """Мета валюты по умолчанию. Все 386 документов аккаунта — в рублях."""
    for row in client.iterate("/entity/currency"):
        if row.get("default"):
            return row["meta"]
    raise ReferenceMissing("В учёте нет валюты по умолчанию")


def _fetch_date_field(client: MoySkladClient) -> dict | None:
    """Мета доп. поля с датой обновления. Нет поля — просто не пишем дату."""
    for row in client.iterate("/entity/product/metadata/attributes"):
        if row.get("name") == DATE_FIELD:
            return row["meta"]
    logger.warning(
        "Доп. поле «%s» в учёте не заведено — дата обновления записываться "
        "не будет, сама себестоимость запишется", DATE_FIELD,
    )
    return None


def _current_cost(product: dict, price_type_href: str) -> int | None:
    """Что сейчас стоит в «Себестоимости» карточки. `None` — не заполнено.

    Округление то же, что у записи, а не `int()`. Иначе стороны сравнения
    считают по-разному: цену `11841.6`, проставленную человеком, чтение даст
    как 11841, а расчёт — 11842, и товар будет переписываться **каждый прогон**,
    вечно и незаметно, выедая общую с ботом корзину лимита.
    """
    for price in product.get("salePrices") or []:
        href = price.get("priceType", {}).get("meta", {}).get("href")
        if href == price_type_href:
            value = price.get("value")
            return _round_kopecks(Decimal(str(value))) if value is not None else None
    return None


def _fifo_by_product() -> dict[str, Decimal]:
    """FIFO из зеркала: {ms_id товара: себестоимость в копейках}.

    Только ненулевая: ноль в `Stock` означает «остатка нет, FIFO неизвестен»,
    а не «товар бесплатный». Записать такой ноль в карточку значило бы
    заменить незнание уверенной ложью.
    """
    rows = (
        Stock.objects.filter(cost_kopecks__gt=0, product__kind=ProductKind.PRODUCT)
        .exclude(product__deleted_at__isnull=False)
        .values_list("product__ms_id", "cost_kopecks")
    )
    return {str(ms_id): cost for ms_id, cost in rows}


def run_cost_prices_writeback(
    client: MoySkladClient,
    *,
    dry_run: bool = False,
    manual: bool = False,
) -> WritebackRun:
    """Проставить себестоимость в карточки товаров. Возвращает запись журнала."""
    session = WritebackSession(
        WritebackKind.COST_PRICES, dry_run=dry_run, manual=manual
    )
    session.ensure_enabled()

    error, stopped = "", False
    try:
        try:
            price_type = _fetch_price_type(client)
            currency = _fetch_currency(client)
            date_field = _fetch_date_field(client)
            fifo = _fifo_by_product()
            # Локальное время: МойСклад показывает дату как есть, без пояса,
            # и записанное в UTC читалось бы в карточке на три часа назад.
            now = timezone.localtime().strftime("%Y-%m-%d %H:%M:%S.000")

            _walk_products(
                session, client, fifo, price_type, currency, date_field, now
            )

        except (ApiDisabledRisk, ChangeLimitReached) as risk:
            error, stopped = str(risk), True
            logger.error("Запись себестоимости остановлена: %s", error)
        except ReferenceMissing:
            # Наружу: в учёте нет типа цены или валюты, и человеку надо сказать
            # что именно завести. Спрятать это в статус прогона значит выдать
            # «Итог: не удалось» вместо готового указания, что делать.
            error = "нет обязательного справочника в учёте"
            raise
        except Exception as failure:  # noqa: BLE001 — журнал важнее типа ошибки
            error = f"{type(failure).__name__}: {failure}"
            logger.exception("Запись себестоимости не удалась")
    finally:
        # `finally`, а не просто следом за `except`: журнал закрывается, даже
        # если процесс убивают. Крон запускает команду под `timeout 900`,
        # и на SIGTERM записи, уже ушедшие в МойСклад, остались бы вовсе
        # без журнальной строки, а прогон навсегда — в состоянии «идёт».
        # Ровно то, ради предотвращения чего §6 и написан.
        run = session.finish(
            request_count=client.request_count, error=error, stopped=stopped
        )

    return run


def _walk_products(
    session: WritebackSession,
    client: MoySkladClient,
    fifo: dict[str, Decimal],
    price_type: dict,
    currency: dict,
    date_field: dict | None,
    now: str,
) -> None:
    """Обойти действующие товары и записать разошедшиеся.

    Архивные исключены явным фильтром: их не продают и не закупают, а PUT
    в архивный товар — запись в общую с ботом корзину ради числа, которого
    никто не увидит. В зеркале они нужны (иначе рвётся история документов),
    здесь — нет.

    Фильтр стоит, хотя API и так отдаёт по умолчанию только действующие
    (проверено 27.08: 314 из 380). Умолчание чужого сервиса — не то, на чём
    держат намерение: сменится оно молча, а заметить это будет нечем.
    """
    for row in client.iterate("/entity/product", {"filter": "archived=false"}):
        ms_id = row.get("id")
        session.note_considered()

        target = fifo.get(ms_id)
        if target is None:
            # Остатка нет — FIFO неизвестен. Не ошибка: у 103 позиций из 315
            # так и есть постоянно.
            session.note_skipped()
            continue

        new_kopecks = _round_kopecks(target)
        old_kopecks = _current_cost(row, price_type["href"])
        if old_kopecks == new_kopecks:
            session.note_skipped()
            continue

        name = row.get("name", "—")
        if session.dry_run:
            session.record(
                ms_id=ms_id, name=name, field=COST_PRICE_TYPE,
                old_value=old_kopecks, new_value=new_kopecks,
            )
            continue

        payload = {
            "salePrices": [{
                "value": new_kopecks,
                "currency": {"meta": currency},
                "priceType": {"meta": price_type},
            }]
        }
        if date_field:
            payload["attributes"] = [{"meta": date_field, "value": now}]

        try:
            client.put(f"/entity/product/{ms_id}", payload)
        except ApiDisabledRisk:
            raise
        except Exception as failure:  # noqa: BLE001
            session.record(
                ms_id=ms_id, name=name, field=COST_PRICE_TYPE,
                old_value=old_kopecks, new_value=new_kopecks,
                error=f"{type(failure).__name__}: {failure}",
            )
            continue

        session.record(
            ms_id=ms_id, name=name, field=COST_PRICE_TYPE,
            old_value=old_kopecks, new_value=new_kopecks,
        )
