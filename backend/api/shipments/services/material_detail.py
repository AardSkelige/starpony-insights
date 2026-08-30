"""Детали одного материала: хватит ли, почём, сколько на изделие и где сидит.

Отдельным запросом, а не полем в списке: у воды пятьдесят девять изделий-
источников, и на сто шестьдесят одну строку это девять тысяч лишних строк
в ответе, из которых человек посмотрит одну.

**Порядок ответов задан тем, как часто их спрашивают.** Первым — запас:
на сколько хватит остатка при нынешнем расходе. Это единственное число
на странице, требующее действия сегодня: у диметикона его хватает на ноль
дней, у воды на три. Дальше цена, норма расхода и распределение.

**Разбор по техкартам остался последним и свёрнутым.** Он объясняет число
до последнего слагаемого и незаменим ровно там, где расход не сводится
к простому умножению: отдушка входит в шампунь и через замес основы,
и прямым добавлением при розливе, и 1,02 г на изделие — не описка.
Но таких материалов один из 161, и встречать этим блоком остальные сто
шестьдесят значило показывать название трижды подряд вместо ответа.
"""

from decimal import Decimal


from api.shipments.services import material_rates, selection
from core.services import consumption
from api.shipments.services.materials import Filters, cost_of
from core.models import Product
from core.services import coverage
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
        selection.shipment_positions(
            date_from=filters.date_from,
            date_to=filters.date_to,
            channel_id=filters.channel_id,
        )
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

    stock = stock_of(material_id)
    # `_days_of_data` считается только при открытом периоде: при заданных
    # границах `days_in` возвращает их разницу, а лишний обход всех позиций
    # выборки ради отброшенного числа стоит запроса на каждое раскрытие
    # строки.
    span = (
        coverage.days_in(filters.date_from, filters.date_to, 0)
        if filters.date_from and filters.date_to
        else coverage.days_in(None, None, _days_of_data(filters))
    )
    left = coverage.of(
        total,
        span,
        # Свободный остаток, а не общий: зарезервированное под заказы уже
        # обещано, и считать его своим значит обнаружить нехватку
        # в день отгрузки.
        Decimal(stock["available"]) if stock else None,
    )

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
        "stock": stock,
        # Запас в днях — первая половина порога закупки (`PRD.md` §5.9).
        # Считается из того, что уже на экране: расход за период против
        # свободного остатка.
        "coverage": {
            "quantity": left.quantity,
            "per_day": left.per_day,
            "days_of_period": left.days_of_period,
            "days_left": left.days_left,
            "level": coverage.level(left.days_left),
        },
        # Сколько материала уходит на одно изделие. Одна строка там, где
        # норма одна на все изделия (121 материал из 161), несколько — там,
        # где она различается: у диметикона 200 г против 20 г.
        "rates": material_rates.rates_of(sources),
        # Где сидит расход: пять крупнейших изделий и свёрнутый хвост.
        "distribution": material_rates.distribution(sources, total),
        "sources_count": len(sources),
        # Сколько изделий получают материал несколькими путями — по **всем**
        # источникам, а не по двадцати показанным. Заголовок свёрнутого
        # разбора считался по видимым и у воды утверждал «в каждое одним
        # путём», хотя многопутёвое изделие могло стоять двадцать первым:
        # блок обещал, что раскрывать нечего, ровно там, где ради этого
        # он и существует.
        "multi_path_count": sum(
            1 for source in sources if len(source["paths"]) > 1
        ),
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


def _days_of_data(filters: Filters) -> int:
    """Длина выборки в днях, когда период не задан руками."""
    return coverage.days_of(
        selection.shipment_positions(
            date_from=filters.date_from,
            date_to=filters.date_to,
            channel_id=filters.channel_id,
        )
    )
