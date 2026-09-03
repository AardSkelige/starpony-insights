"""Сборка ответа «Расчёта производства» — из посчитанного в то, что уходит.

Отдельно от `batch.py` по причине изменения: там правила домена — как
разворачивать техкарты и что считать нехваткой, — а здесь форма ответа,
которая меняется вместе с контрактом и сериализаторами. Один файл на двоих
перевалил за четыреста строк, и правка любой из двух причин заставляла
читать обе.

Готовые объекты — `PurchasePrice`, `LeadTime` — уходят как есть, а не
пересобираются в словари: поля перечислены в общих сериализаторах, и второй
их список здесь разошёлся бы с ними на первом же добавленном поле.
"""

from dataclasses import replace

from api.production.services import products
from api.production.services.batch import Batch, BatchLine, Need, of
from api.production.services.selection import Filters
from core.models import Product


def resolve(
    batch: dict[str, int | None], filters: Filters
) -> dict[str, int | None]:
    """Заменить «посчитай сам» на предложенное количество.

    **Считается на сервере, а не на фронте.** Фронт разрешал их по списку
    товаров, а тот приходит **суженным поиском** — и партия, собранная
    до поиска, молча теряла всё, чего в найденном не оказалось: «Взять всё»
    на тридцать позиций, потом запрос «шампунь», и закупка пересчитывалась
    по трём. Ни одного признака, что считали не то.

    **Поиск сюда не входит по той же причине.** Партия собрана раньше и от
    того, что человек сейчас ищет, зависеть не должна: `search=""` — не
    небрежность, а условие правильности.

    **Позиция без предложения остаётся `None`, а не выбрасывается.**
    Предлагать нечего — товар не продавался за период либо остаток
    неизвестен, — но галочку человек поставил, и `_lines` вернёт строку
    названной (`LineProblem.NO_QUANTITY`). Выбрасывали её раньше: галочка
    стояла, поле «произвести» было пустым, а в партии позиции не было —
    ровно то, против чего заведён `LineProblem`.
    """
    unresolved = [article for article, q in batch.items() if q is None]
    if not unresolved:
        return dict(batch)

    # Считается только по отмеченному, а не по всему каталогу: полное
    # верхнее звено на каждое нажатие «плюс» — трата, которой правка
    # количества стоить не должна.
    suggested = {
        row.product.article: row.suggested
        for row in products.rows(
            replace(filters, search=""), articles=unresolved
        )
    }

    resolved: dict[str, int | None] = {}
    for article, quantity in batch.items():
        value = quantity if quantity is not None else suggested.get(article)
        resolved[article] = value if value and value > 0 else None
        if quantity is not None:
            resolved[article] = quantity
    return resolved


def page(batch_query: dict[str, int | None], filters: Filters) -> dict:
    """Нижнее звено целиком — то, что уходит на экран."""
    result = of(resolve(batch_query, filters))
    products = {
        line.product.pk: line.product for line in result.lines if line.product
    }
    return {
        "lines": [_line_cells(line) for line in result.lines],
        "materials": [_need_cells(need, products) for need in result.needs],
        "summary": _summary(result),
    }


def _line_cells(line: BatchLine) -> dict:
    return {
        "article": line.article,
        "quantity": line.quantity,
        "product_id": line.product.pk if line.product else None,
        "name": line.product.name if line.product else "",
        "problem": line.problem,
    }


def _need_cells(need: Need, products: dict[int, Product]) -> dict:
    return {
        "product_id": need.product.pk,
        "name": need.product.name,
        "article": need.product.article,
        "code": need.product.code,
        "uom": need.product.uom.name if need.product.uom else "",

        "quantity": need.quantity,
        "available": need.available,
        "shortage": need.shortage,
        "after": need.after,

        "min_balance": need.min_balance,
        "archived": need.archived,
        "below_min_now": need.below_min_now,
        "below_min_after": need.below_min_after,

        # Готовые объекты, а не собранные заново словари: поля перечислены
        # в общем сериализаторе, и второй список здесь разошёлся бы с ним
        # на первом же добавленном поле. Так же устроены «Поставщики».
        "price": need.price,
        "cost_kopecks": need.cost_kopecks,
        "lead_time": need.waiting,
        "supplier": need.price.supplier if need.price else "",

        "via": [
            {"chain": list(path.chain), "quantity": path.quantity}
            for path in need.via
        ],
        # Из какого товара партии сколько пришло — по убыванию вклада:
        # вопрос к строке обычно один, «из-за чего его столько».
        "sources": [
            {
                "product_id": product_id,
                "name": products[product_id].name,
                "quantity": quantity,
            }
            for product_id, quantity in sorted(
                need.sources.items(), key=lambda item: -item[1]
            )
            if product_id in products
        ],
    }


def _summary(result: Batch) -> dict:
    counted = [line for line in result.lines if line.counts]
    shortages = result.shortages
    waits = [
        need.waiting.days for need in shortages if need.waiting.days is not None
    ]
    return {
        "products_count": len(counted),
        "units_count": sum(line.quantity for line in counted),
        "materials_count": len(result.needs),

        "shortages_count": len(shortages),
        "purchase_kopecks": result.purchase_kopecks,
        # Рядом с суммой обязательно: она итог по тем, у кого известна цена,
        # а не по всем недостающим (`DESIGN.md` §8).
        "priced_shortages_count": result.priced_shortages_count,
        # Партия начнётся не раньше, чем приедет последнее из недостающего.
        # Максимум, а не среднее: ждать придётся самого долгого.
        "max_lead_time_days": max(waits) if waits else None,
        # Знаменатель срока — рядом, как у суммы закупки. Срок известен
        # только там, где известен поставщик, а он берётся из последней
        # приёмки: без цены нет и поставщика. «Ждать 3 дня» по двум
        # позициям из пяти без этого числа читается как срок по всем
        # (`DESIGN.md` §8).
        "timed_shortages_count": len(waits),

        "unknown_stock_count": sum(
            1 for need in result.needs if need.available is None
        ),
        # Архивное сырьё в действующих техкартах. Ноль на боевых данных
        # с 03.09 — но забывчивость повторится, и тогда число скажет,
        # что чинить надо техкарту, а не закупку.
        "archived_count": sum(1 for need in result.needs if need.archived),
        "below_min_now_count": sum(1 for need in result.needs if need.below_min_now),
        "below_min_after_count": sum(
            1 for need in result.needs if need.below_min_after
        ),
    }
