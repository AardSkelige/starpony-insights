"""Страница «Материалы в приёмках»: что и почём закупали.

Строка — наименование, слагаемые строки — закупки по документам
(`purchases.py`). Здесь сборка страницы: количества, суммы, средняя цена,
динамика, поиск, сортировка, итоги.

**Расчётные числа отдаются составляющими, а не готовым текстом.** Средняя
приходит вместе с оплаченным количеством, из которого получена; динамика —
вместе с обеими ценами, которые сравнивались. Что за приёмки за этим стоят,
видно в раскрытии строки.

**Три числа про цену, и они разные.** Средняя за период отвечает «во сколько
обошлось в среднем», последняя — «почём сейчас», динамика — «в какую сторону
идёт». Ни одно не заменяет другое: у изопропилового спирта шесть закупок
и разброс от 0,2210 до 0,2600 за грамм.
"""

from dataclasses import dataclass
from decimal import Decimal

from api.common.selection import page_bounds
from api.supplies.services import purchases, selection, summary
from api.supplies.services.purchases import Purchase
from core.money import share

# Сортировки, разрешённые снаружи. Список закрытый — как у соседних страниц.
ORDERING = (
    "amount", "-amount",
    "quantity", "-quantity",
    "name", "-name",
    "avg_price", "-avg_price",
    "last_price", "-last_price",
    "change", "-change",
    "supplies", "-supplies",
    "suppliers", "-suppliers",
)
DEFAULT_ORDERING = "-amount"


@dataclass(frozen=True)
class Filters(selection.Filters):
    """Фильтры страницы. Общее — выше по цепочке, своё — порядок строк.

    Период и поставщик отбирают приёмки, поиск — материалы. Разные вещи:
    выбрав «Лемун», человек сужает документы; набрав «отдушка», сужает строки
    таблицы уже внутри выбранного.
    """

    ordering: str = DEFAULT_ORDERING


def row_of(product, items: list[Purchase]) -> dict:
    """Строка таблицы вместе с составляющими своих расчётных чисел."""
    paid = purchases.priced(items)

    quantity = sum((item.quantity for item in items), Decimal(0))
    paid_quantity = sum((item.quantity for item in paid), Decimal(0))
    amount = sum(item.amount_kopecks for item in items)

    last = paid[-1] if paid else None
    previous = paid[-2] if len(paid) > 1 else None

    return {
        "material_id": product.pk,
        "name": product.name,
        "article": product.article,
        "code": product.code,
        "uom": _uom_of(product, items),
        # Материал, пришедший в разных единицах, складывать нельзя: килограмм
        # против грамма ошибается ровно в тысячу раз и на глаз незаметен.
        # Сегодня таких нет ни одного, и потому признак нужен сейчас: когда
        # появится первый, расхождение иначе никто не заметит.
        "mixed_uom": len(_uoms_of(items)) > 1,

        "quantity": quantity,
        # Сколько из пришедшего досталось даром. Отдельно от количества,
        # а не вычтено из него: на склад оно поступило и в расчёт
        # производства войдёт — не входит только в цену.
        "free_quantity": quantity - paid_quantity,
        "amount_kopecks": amount,

        # Средняя — по оплаченному количеству, а не по всему пришедшему.
        # У этикетки Табак-Ваниль 280 штук из 496 пришли даром, и деление
        # на всё количество занизило бы цену вдвое.
        "avg_price_kopecks": unit_price(amount, paid_quantity),
        "paid_quantity": paid_quantity,

        "last_price_kopecks": last.price_kopecks if last else None,
        "last_moment": last.moment if last else None,
        "last_document_number": last.number if last else None,
        "last_supplier": last.supplier if last else None,

        # Динамика — к предыдущей закупке, а не к первой за период. Отвечает
        # на «подорожало ли в этот раз»: у флакона 25,05 → 28,00 → 31,05
        # первая-к-последней дала бы +24%, скрыв, что последний шаг +10,9%.
        # Весь ряд виден в раскрытии строки, так что тренд не теряется.
        "previous_price_kopecks": previous.price_kopecks if previous else None,
        # Количества обеих сравниваемых закупок. Без них процент врёт
        # умолчанием: лауроилглутамат «подорожал на 278 %», но 19.07 пришло
        # 5000 г по 45 копеек, а 05.08 — 1000 г по 170. Это в том числе
        # про размер партии, и человек обязан видеть это рядом с числом,
        # а не искать в раскрытии строки.
        "previous_quantity": previous.quantity if previous else None,
        "last_quantity": last.quantity if last else None,
        "price_change": price_change(previous, last),

        # Ряд цен для линии в колонке и для графика в разборе. Только те
        # закупки, у которых цена есть: бесплатная приёмка нарисовала бы
        # падение до нуля и обратно — движение, которого не было.
        #
        # Даты приходят вместе с ценами, потому что линия обязана строиться
        # по времени, а не по номеру закупки. Между 28.02 и 14.05 два с половиной
        # месяца, между 01.07 и 30.07 — один; равные промежутки на экране
        # соврали бы о том, как быстро дорожает материал.
        "prices": [
            {"moment": item.moment, "price_kopecks": item.price_kopecks}
            for item in paid
        ],
        "supplies_count": len(items),
        "suppliers_count": len({item.supplier_id for item in items}),
        # Идентификаторы — для итога по показанным строкам: сложить
        # `supplies_count` нельзя, одна приёмка приносит несколько материалов
        # и была бы посчитана столько раз, сколько в ней наименований.
        # В ответ не уходят — они нужны только счёту.
        "document_ids": {item.document_id for item in items},
        "supplier_ids": {item.supplier_id for item in items},
    }


def _uoms_of(items: list[Purchase]) -> set[str]:
    return {name for item in items for name in item.uoms}


def _uom_of(product, items: list[Purchase]) -> str:
    """Единица измерения строки: из приёмок, а при их молчании — из карточки.

    Приёмка — факт, карточка — намерение. Но единица в позиции заполнена
    не всегда (три позиции из 402 пришли без неё), и тогда карточка лучше,
    чем пустая ячейка.
    """
    names = _uoms_of(items)
    if len(names) == 1:
        return next(iter(names))
    if names:
        return ""
    return product.uom.name if product.uom else ""


def unit_price(amount_kopecks: int, quantity: Decimal) -> Decimal | None:
    """Цена за единицу. `None` — делить не на что: всё пришло даром."""
    if quantity <= 0 or amount_kopecks <= 0:
        return None
    return Decimal(amount_kopecks) / quantity


def price_change(previous: Purchase | None, last: Purchase | None) -> Decimal | None:
    """Насколько последняя цена отличается от предыдущей, долей единицы.

    `None`, когда сравнивать не с чем: закупка была одна или единственная
    с ценой. Ноль здесь читался бы как «цена не менялась», а это другое
    утверждение — таких материалов десять, и они честно показывают ноль.
    """
    if previous is None or last is None:
        return None
    before, after = previous.price_kopecks, last.price_kopecks
    if before is None or after is None or before <= 0:
        return None
    return (after - before) / before


def _matches(row: dict, term: str) -> bool:
    """Поиск по материалу: название, артикул, код — как у соседних страниц."""
    needle = term.strip().casefold()
    return any(
        needle in (row[key] or "").casefold() for key in ("name", "article", "code")
    )


# По чему сравнивают строки для каждого разрешённого ключа сортировки.
_SORT_KEYS = {
    "amount": lambda row: row["amount_kopecks"],
    "quantity": lambda row: row["quantity"],
    "avg_price": lambda row: row["avg_price_kopecks"],
    "last_price": lambda row: row["last_price_kopecks"],
    "change": lambda row: row["price_change"],
    "supplies": lambda row: row["supplies_count"],
    "suppliers": lambda row: row["suppliers_count"],
    "name": lambda row: row["name"].casefold(),
}


def _sorted(rows: list[dict], ordering: str) -> list[dict]:
    """Порядок показа. Строки, которым сортировать нечем, всегда внизу.

    По цене материала, доставшегося даром, сказать нечего — ни «дорогой»,
    ни «дешёвый»; по динамике материала, купленного однажды, тоже. Такие
    строки идут отдельным списком, а не хитрым ключом: переворот направления
    иначе поднял бы их наверх, и список «где сильнее всего подорожало»
    начинался бы с тех, у кого цена не менялась ни разу.

    Ничьи разрешает `material_id`: без него строки с равной суммой шли бы
    в порядке, который не обязан повторяться между запросами, и один материал
    попал бы на две страницы подряд, а другой — ни на одну.
    """
    if ordering not in ORDERING:
        ordering = DEFAULT_ORDERING
    desc = ordering.startswith("-")
    key = _SORT_KEYS[ordering.lstrip("-")]

    known = [row for row in rows if key(row) is not None]
    unknown = [row for row in rows if key(row) is None]

    known.sort(key=lambda row: (key(row), row["material_id"]), reverse=desc)
    unknown.sort(key=lambda row: row["material_id"])
    return known + unknown


def prepared(filters: Filters) -> dict:
    """Все строки выборки и оба набора итогов — без нарезки на страницы.

    Отдельно от `page`, потому что выгрузке нужны **все** строки, а не первая
    сотня: приёмки читаются одним запросом, и делать его дважды — ради
    страницы и ради файла — незачем.
    """
    positions = list(
        selection.supply_positions(
            date_from=filters.date_from,
            date_to=filters.date_to,
            supplier_id=filters.supplier_id,
        ).select_related("product", "product__uom", "uom", "document", "document__agent")
    )
    grouped = purchases.by_material(positions)
    products = {position.product_id: position.product for position in positions}

    everything = [
        row_of(products[material_id], items) for material_id, items in grouped.items()
    ]
    # Доля материала считается от суммы **всей** выборки, а не найденного:
    # иначе после поиска «отдушка» её доля показала бы 100%, хотя отдушек
    # в закупках восьмая часть.
    selection_amount = sum(row["amount_kopecks"] for row in everything)
    for row in everything:
        row["amount_share"] = share(row["amount_kopecks"], selection_amount)

    rows = everything
    if filters.search:
        rows = [row for row in everything if _matches(row, filters.search)]

    return {
        "rows": _sorted(rows, filters.ordering),
        # Итог под таблицей — про то, что в ней видно: он обязан сходиться
        # со сложением колонки, иначе человек проверит на калькуляторе
        # и получит другое число.
        "totals": summary.table_totals(rows, selection_amount),
        # Сводка — про выборку приёмок целиком. Поиск её не трогает:
        # он сужает список материалов, а не то, что закупили.
        "coverage": summary.coverage(everything, positions, selection_amount),
    }


def page(filters: Filters) -> dict:
    """Всё, что нужно странице, за один проход по позициям приёмок."""
    whole = prepared(filters)
    rows = whole["rows"]

    start, end = page_bounds(filters.page, filters.page_size)

    return {
        "count": len(rows),
        "totals": whole["totals"],
        "coverage": whole["coverage"],
        "results": rows[start:end],
    }
