"""Строка «Прибыльности»: один товар за период, со всеми составляющими.

Числа собираются из двух источников, и это осознанно. Себестоимость **на
момент продажи** знает только МойСклад — она в зеркале отчёта. Что ушло
даром и что лежит у комиссионера — знаем только мы, потому что в отчёте
обеих величин нет вовсе.

Расчёт в Python, а не в базе: товаров на странице шестьдесят два, а слить
три источника в один запрос значило бы написать подзапрос, который никто
не прочитает. Порог для переезда в SQL — когда номенклатура перевалит
за несколько тысяч; сегодня это оптимизация вслепую.
"""

from decimal import Decimal

from django.db.models import Q, Sum

from api.profitability.services.selection import Basis, Filters
from api.profitability.services import selection
from core.models import ContractType, Counterparty

ZERO = Decimal(0)

# Имена аннотаций намеренно не совпадают с именами полей. `annotate(quantity=…)`
# перекрывает поле `quantity`, и следующая же агрегация по нему падает
# с «'quantity' is an aggregate»: Django видит уже не колонку, а сумму.
# Те же грабли описаны в `api/shipments/services/products.py` — здесь на них
# наступили второй раз.
QTY = "qty"
REV = "rev"
CST = "cst"
FREE_QTY = "free_qty"
MK_QTY = "mk_qty"
MK_REV = "mk_rev"
MK_CST = "mk_cst"
CONSIGNED_QTY = "consigned_qty"
CONSIGNED_REV = "consigned_rev"


def _marketplace() -> Q:
    """Расчёты идут через площадку. Признак — группа контрагента из учёта.

    **Отбор по идентификаторам, а не сравнением массива в запросе.**
    `tags__contains=["маркетплейсы"]` — точное совпадение, с учётом регистра
    и пробелов, а группу набирает человек: `Counterparty.is_marketplace`
    именно поэтому сравнивает через `casefold()` и `strip()`. Две копии
    правила разошлись бы молча — площадка исчезала бы отсюда, оставаясь
    площадкой на «Сроках оплаты».

    Цена — один запрос на 107 контрагентов за расчёт страницы. Правило
    же остаётся ровно одно, и живёт оно в модели.
    """
    return Q(document__agent_id__in=marketplace_ids())


def marketplace_ids() -> list[int]:
    """Кто из контрагентов — площадка. Читается моделью, а не запросом.

    Список собирается один раз на расчёт страницы: `_marketplace()` зовут
    дважды — на количество и на выручку, — и без общего списка это два
    одинаковых запроса подряд.
    """
    return [
        agent.pk
        for agent in Counterparty.objects.only("id", "tags")
        if agent.is_marketplace
    ]


def _commission() -> Q:
    """Товар ушёл на реализацию, а не продан."""
    return Q(document__contract__contract_type=ContractType.COMMISSION)


def _fields(prefix: str = "product__") -> tuple[str, ...]:
    return (
        f"{prefix}id", f"{prefix}name", f"{prefix}article",
        f"{prefix}code", f"{prefix}folder", f"{prefix}uom__name",
    )


def _head(row: dict, prefix: str = "product__") -> dict:
    """Шапка строки: чем товар является. Одинакова у обеих баз расчёта."""
    return {
        "product_id": row[f"{prefix}id"],
        "name": row[f"{prefix}name"],
        "article": row[f"{prefix}article"],
        "code": row[f"{prefix}code"],
        "folder": row[f"{prefix}folder"] or "",
        "uom": row[f"{prefix}uom__name"] or "",
    }


def _sold(filters: Filters) -> dict[int, dict]:
    """Что продано за период по данным отчёта: деньги за товар."""
    rows = (
        selection.profit_days(date_from=filters.date_from, date_to=filters.date_to)
        .values(*_fields())
        .annotate(**{
            QTY: Sum("quantity"),
            REV: Sum("revenue_kopecks"),
            CST: Sum("cost_kopecks"),
            MK_QTY: Sum("marketplace_quantity"),
            MK_REV: Sum("marketplace_revenue_kopecks"),
            MK_CST: Sum("marketplace_cost_kopecks"),
        })
    )
    return {row["product__id"]: row for row in rows}


def _shipped(filters: Filters) -> dict[int, dict]:
    """Что уехало со склада за период — вместе с подарками и площадками.

    Считается всегда, при любой базе: подарки нужны обеим, а «отгружено,
    ещё не продано» — это ответ на вопрос, почему выручка здесь меньше,
    чем на «Товарах в отгрузках».
    """
    marketplaces = _marketplace()
    rows = (
        selection.shipment_positions(
            date_from=filters.date_from, date_to=filters.date_to
        )
        .values(*_fields())
        .annotate(**{
            QTY: Sum("quantity"),
            REV: Sum("total_kopecks"),
            # Даром — позиции с нулевой суммой: призы, подарки, замены брака,
            # пробники. Себестоимость у них настоящая, выручки нет вовсе.
            FREE_QTY: Sum("quantity", filter=Q(total_kopecks=0)),
            # Площадка — признак контрагента, а не канала продаж: «Точка
            # продаж» смешанная, 5 документов площадки против 30 обычных.
            MK_QTY: Sum("quantity", filter=marketplaces),
            MK_REV: Sum("total_kopecks", filter=marketplaces),
            # Ушло по договору комиссии — то есть на реализацию, а не продано.
            CONSIGNED_QTY: Sum("quantity", filter=_commission()),
            CONSIGNED_REV: Sum("total_kopecks", filter=_commission()),
        })
    )
    return {row["product__id"]: row for row in rows}


def _realised(filters: Filters) -> dict[int, dict]:
    """Что комиссионер уже продал — по позициям отчётов комиссионера."""
    rows = (
        selection.commission_report_positions(
            date_from=filters.date_from, date_to=filters.date_to
        )
        .values("product__id")
        .annotate(**{QTY: Sum("quantity"), REV: Sum("total_kopecks")})
    )
    return {row["product__id"]: row for row in rows}


def _share(part, whole):
    """Доля одного числа в другом. `None` — делить не на что.

    Ноль вместо `None` не годится: он читается как «доля нулевая», а на деле
    величина неизвестна — например, товар отдали даром и выручки нет.
    """
    if whole is None or whole == 0:
        return None
    return Decimal(part) / Decimal(whole)


def build(filters: Filters) -> list[dict]:
    """Строки страницы: по одной на товар, со всеми составляющими маржи.

    Порядок и разбиение на страницы — не здесь: строк шестьдесят с небольшим,
    и сортировать их обязан тот, кто знает выбранный порядок.
    """
    sold = _sold(filters)
    shipped = _shipped(filters)
    realised = _realised(filters)

    rows = []
    for product_id in sold.keys() | shipped.keys():
        s = sold.get(product_id)
        sh = shipped.get(product_id)
        head = _head(s) if s else _head(sh)

        sold_quantity = (s or {}).get(QTY) or ZERO
        sold_revenue = (s or {}).get(REV) or 0
        sold_cost = (s or {}).get(CST) or 0

        # Средняя себестоимость единицы за период — из отчёта, а не из
        # остатков: она нужна там, где количество известно нам, а цена
        # только МойСкладу — у подарков и у товара на реализации.
        unit_cost = _share(sold_cost, sold_quantity)

        free_quantity = (sh or {}).get(FREE_QTY) or ZERO
        # Себестоимость подарков — расчётная, и это обязано быть сказано
        # на экране: количество наше, цена единицы из отчёта за период.
        # По дням её считать нельзя: на 76 днях из 663 отчёт и отгрузки
        # расходятся, потому что комиссия переносит продажу на свой день.
        free_cost = int(free_quantity * unit_cost) if unit_cost is not None else 0

        shipped_quantity = (sh or {}).get(QTY) or ZERO
        shipped_revenue = (sh or {}).get(REV) or 0

        # Лежит у комиссионера: отгружено по комиссии минус то, что он продал.
        # Ниже нуля не опускается: отчёт может закрывать отгрузку прошлого
        # периода, и минус здесь означал бы «продал больше, чем взял».
        consigned = (sh or {}).get(CONSIGNED_QTY) or ZERO
        unsold_quantity = max(consigned - ((realised.get(product_id) or {}).get(QTY) or ZERO), ZERO)
        unsold_revenue = max(
            ((sh or {}).get(CONSIGNED_REV) or 0)
            - ((realised.get(product_id) or {}).get(REV) or 0),
            0,
        )

        if filters.basis == Basis.SHIPPED:
            quantity, revenue = shipped_quantity, shipped_revenue
            # Себестоимость отгруженного — расчётная по той же причине:
            # МойСклад считает её только для проданного.
            cost = int(quantity * unit_cost) if unit_cost is not None else None
            mk_quantity = (sh or {}).get(MK_QTY) or ZERO
            mk_revenue = (sh or {}).get(MK_REV) or 0
            mk_cost = int(mk_quantity * unit_cost) if unit_cost is not None else None
        else:
            quantity, revenue, cost = sold_quantity, sold_revenue, sold_cost
            mk_quantity = (s or {}).get(MK_QTY) or ZERO
            mk_revenue = (s or {}).get(MK_REV) or 0
            mk_cost = (s or {}).get(MK_CST) or 0

        if not filters.with_free:
            # Выручку править не надо — у подарка её нет вовсе. Убирается
            # только их себестоимость и их штуки.
            quantity = max(quantity - free_quantity, ZERO)
            if cost is not None:
                cost = max(cost - free_cost, 0)

        profit = None if cost is None else revenue - cost

        rows.append({
            **head,
            "quantity": quantity,
            "revenue_kopecks": revenue,
            "cost_kopecks": cost,
            "profit_kopecks": profit,
            "margin": _share(profit, revenue) if profit is not None else None,
            "unit_cost_kopecks": unit_cost,
            "cost_is_estimated": filters.basis == Basis.SHIPPED,

            "free_quantity": free_quantity,
            "free_cost_kopecks": free_cost,

            "marketplace_quantity": mk_quantity,
            "marketplace_revenue_kopecks": mk_revenue,
            "marketplace_cost_kopecks": mk_cost,

            "unsold_quantity": unsold_quantity,
            "unsold_kopecks": unsold_revenue,

            "shipped_quantity": shipped_quantity,
            "shipped_revenue_kopecks": shipped_revenue,
            "sold_quantity": sold_quantity,
            "sold_revenue_kopecks": sold_revenue,
        })

    return rows
