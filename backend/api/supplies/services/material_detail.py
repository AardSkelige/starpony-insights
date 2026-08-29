"""Разбор строки «Материалы в приёмках»: откуда взялись её числа.

Три ответа на три вопроса строки. **История** объясняет среднюю и динамику:
каждая приёмка с датой, номером, поставщиком, количеством и ценой — сложите
суммы, получите сумму строки. **По поставщикам** объясняет разброс: у одного
и того же материала цены разных поставщиков различаются вдвое и втрое.
**Склад** отвечает на «а надо ли докупать» — он про сегодня, а не про период.

**Разброс считается по последним ценам поставщиков, а не по крайним ценам
вообще.** Иначе «Крышка флип-топ» показывает разброс 73% между «Лемуном»
и «Лемуном»: это движение цены во времени, а не разница между поставщиками,
и решение «уйти к другому» на нём построить нельзя.
"""

from decimal import Decimal

from api.supplies.services import materials, purchases, selection
from api.supplies.services.purchases import Purchase
from core.services.stock import stock_of


class MaterialNotPurchased(Exception):
    """Материал не закупался в этой выборке — отвечать нечем."""


def detail(filters: materials.Filters, material_id: int) -> dict:
    """Разбор одного материала по той же выборке, что у таблицы.

    Фильтры те же намеренно: слагаемые обязаны сходиться с числом своей
    строки. Возьми разбор весь период, а строка — апрель, и человек увидел бы
    объяснение, которое не складывается в объясняемое.
    """
    positions = list(
        selection.supply_positions(
            date_from=filters.date_from,
            date_to=filters.date_to,
            supplier_id=filters.supplier_id,
        )
        .filter(product_id=material_id)
        .select_related("product", "product__uom", "uom", "document", "document__agent")
    )
    if not positions:
        raise MaterialNotPurchased

    product = positions[0].product
    items = purchases.by_material(positions)[material_id]
    row = materials.row_of(product, items)

    return {
        "material": {
            "id": product.pk,
            "name": product.name,
            "article": product.article,
            "code": product.code,
            "uom": row["uom"],
        },
        "quantity": row["quantity"],
        "free_quantity": row["free_quantity"],
        "amount_kopecks": row["amount_kopecks"],
        "avg_price_kopecks": row["avg_price_kopecks"],
        "paid_quantity": row["paid_quantity"],
        "price_change": row["price_change"],
        # Порядок хронологический: история цен читается слева направо,
        # и разворачивать её ради «свежее сверху» значит ломать то самое,
        # ради чего её открыли.
        "history": [_purchase_cells(item, before) for item, before in _paired(items)],
        "suppliers": _by_supplier(items),
        # Остаток — про сегодня, а не про период: он отвечает на «хватит ли
        # до следующей закупки», и фильтры к этому вопросу отношения не имеют.
        "stock": stock_of(material_id),
    }


def _paired(items: list[Purchase]) -> list[tuple[Purchase, Purchase | None]]:
    """Каждая закупка вместе с предыдущей **ценой** — не просто предыдущей.

    Между двумя платными приёмками стоит бесплатная допечатка этикеток,
    и сравнение с ней дало бы «цена выросла с нуля» — бесконечность,
    выведенную из подарка.
    """
    pairs: list[tuple[Purchase, Purchase | None]] = []
    previous: Purchase | None = None
    for item in items:
        pairs.append((item, previous))
        if not item.is_free:
            previous = item
    return pairs


def _purchase_cells(item: Purchase, before: Purchase | None) -> dict:
    return {
        "document_id": item.document_id,
        "number": item.number,
        "moment": item.moment,
        "supplier": item.supplier,
        "quantity": item.quantity,
        "amount_kopecks": item.amount_kopecks,
        # `null` у бесплатной приёмки, а не ноль: ноль читался бы как цена,
        # и средняя по колонке, посчитанная глазом, разошлась бы с итогом.
        "price_kopecks": item.price_kopecks,
        "is_free": item.is_free,
        "price_change": materials.price_change(before, item) if not item.is_free else None,
    }


def _by_supplier(items: list[Purchase]) -> list[dict]:
    """Сводка по поставщикам: почём брали у каждого и насколько это дороже.

    Сравнение идёт с самой низкой **последней** ценой среди поставщиков —
    это и есть ответ на «где дешевле сейчас». Поставщики, у которых материал
    приходил только даром, цены не получают и в сравнении не участвуют:
    подарок не предложение.
    """
    grouped: dict[int, list[Purchase]] = {}
    for item in items:
        grouped.setdefault(item.supplier_id, []).append(item)

    rows = [_supplier_cells(group) for group in grouped.values()]

    known = [row["last_price_kopecks"] for row in rows if row["last_price_kopecks"]]
    best = min(known) if known else None

    for row in rows:
        price = row["last_price_kopecks"]
        # `null`, а не ноль, и у самого дешёвого тоже — ноль здесь верен
        # и означает «он и есть лучший».
        row["above_best"] = (
            (price - best) / best if price is not None and best else None
        )

    # Дешёвый сверху, безценовые вниз: список читают как «у кого брать».
    rows.sort(
        key=lambda row: (
            row["last_price_kopecks"] is None,
            row["last_price_kopecks"] or Decimal(0),
        )
    )
    return rows


def _supplier_cells(group: list[Purchase]) -> dict:
    paid = purchases.priced(group)
    quantity = sum((item.quantity for item in group), Decimal(0))
    paid_quantity = sum((item.quantity for item in paid), Decimal(0))
    amount = sum(item.amount_kopecks for item in group)

    return {
        "supplier_id": group[0].supplier_id,
        "name": group[0].supplier,
        "supplies_count": len(group),
        "quantity": quantity,
        "amount_kopecks": amount,
        "avg_price_kopecks": materials.unit_price(amount, paid_quantity),
        "last_price_kopecks": paid[-1].price_kopecks if paid else None,
        "last_moment": paid[-1].moment if paid else None,
    }
