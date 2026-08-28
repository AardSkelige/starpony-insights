"""Детали одного материала: из каких изделий пришёл, какими путями, что осталось.

Отдельным запросом, а не полем в списке: у воды пятьдесят девять изделий-
источников, и на сто шестьдесят одну строку это девять тысяч лишних строк
в ответе, из которых человек посмотрит одну.

**Здесь живёт объяснение числа.** Строка таблицы говорит «1 324 150 г воды»;
панель раскладывает это по изделиям, а внутри изделия — по путям, которыми
материал в него попал. Отдушка входит в шампунь и напрямую при розливе,
и через замес основы — два слагаемых, а не одно число с примечанием.
"""

from decimal import Decimal

from api.shipments.services import consumption
from api.shipments.services.materials import Filters, cost_of
from core.models import Product
from core.services.materials import explode, plans_by_product
from core.services.stock import stock_of
from core.services.purchase_prices import last_purchase_prices

# Сколько изделий показать. У воды их пятьдесят девять, и панель с таким
# списком не отвечает ни на один вопрос. Двадцать крупнейших отвечают на тот,
# ради которого её открыли, — «откуда столько».
#
# Остаток при этом не выбрасывается, а сворачивается в строку «ещё 39
# наименований». Иначе слагаемые в панели не складываются в число, которое
# она объясняет, — а объяснение, не сходящееся с объясняемым, хуже, чем его
# отсутствие: расхождение спишут на расчёт.
SOURCE_LIMIT = 20


class MaterialNotUsed(Exception):
    """Материал не участвует в выборке — деталям неоткуда взяться."""


def detail(filters: Filters, material_id: int) -> dict:
    """Всё про материал в контексте выбранных фильтров."""
    rows = consumption.sold(
        date_from=filters.date_from,
        date_to=filters.date_to,
        channel_id=filters.channel_id,
    )
    plans = plans_by_product()
    products = {
        product.pk: product
        for product in Product.objects.select_related("uom").filter(
            pk__in=[row["product_id"] for row in rows]
        )
    }

    sources: list[dict] = []
    total = Decimal(0)

    for row in rows:
        product = products[row["product_id"]]
        if product.pk not in plans:
            continue

        for need in explode(product, row["quantity"], plans=plans):
            if need.product.pk != material_id:
                continue
            total += need.quantity
            sources.append(
                {
                    "product_id": product.pk,
                    "name": product.name,
                    "sold_quantity": row["quantity"],
                    "sold_uom": product.uom.name if product.uom else "",
                    "quantity": need.quantity,
                    "paths": [
                        {"chain": list(path.chain), "quantity": path.quantity}
                        for path in sorted(need.via, key=lambda p: -p.quantity)
                    ],
                }
            )

    if not sources:
        raise MaterialNotUsed()

    sources.sort(key=lambda item: -item["quantity"])
    material = Product.objects.select_related("uom").get(pk=material_id)
    price = last_purchase_prices([material_id]).get(material_id)

    shown = sources[:SOURCE_LIMIT]
    hidden = sources[SOURCE_LIMIT:]

    return {
        "material": {
            "id": material.pk,
            "name": material.name,
            "article": material.article,
            "code": material.code,
            "uom": material.uom.name if material.uom else "",
        },
        "quantity": total,
        "cost_kopecks": cost_of(total, price),
        # Откуда взялась цена — с документом, датой и поставщиком. Без этого
        # колонка «Стоимость» остаётся числом, за которое никто не отвечает.
        "price": (
            {
                "price_kopecks": price.price_kopecks,
                "moment": price.moment,
                "document_number": price.document_number,
                "supplier": price.supplier,
            }
            if price
            else None
        ),
        "stock": stock_of(material_id),
        "sources_count": len(sources),
        "sources": shown,
        "rest": (
            {
                "products_count": len(hidden),
                "quantity": sum(item["quantity"] for item in hidden),
            }
            if hidden
            else None
        ),
    }
