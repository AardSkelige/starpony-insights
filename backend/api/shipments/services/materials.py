"""Страница «Материалы в отгрузках»: сколько сырья ушло с проданной продукцией.

Разворачивание по техкартам живёт в `consumption.py`. Здесь — сборка страницы:
цены, поиск, сортировка, итоги.

**Расчётные числа отдаются составляющими, а не готовым текстом.** Стоимость
приходит вместе с ценой и количеством, из которых получена, а откуда взялась
сама цена — видно в раскрытии строки: номер приёмки, дата, поставщик.

**Цена — из последней приёмки, а не из карточки товара.** Почему именно так —
в `core/services/purchase_prices.py`: карточка заполнена у 42 материалов
из 161 и у большинства разошлась с тем, что заплатили.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from api.shipments.services import consumption, selection
from api.shipments.services.consumption import Consumed
from core.money import share
from core.services.purchase_prices import PurchasePrice, last_purchase_prices

# Сортировки, разрешённые снаружи. Список закрытый — как у соседней страницы.
# Минус означает убывание, как принято от DRF до SQL.
ORDERING = (
    "cost", "-cost",
    "quantity", "-quantity",
    "name", "-name",
    "share", "-share",
    "products", "-products",
)
DEFAULT_ORDERING = "-cost"

_KOPECK = Decimal("1")


@dataclass(frozen=True)
class Filters(selection.Filters):
    """Фильтры страницы. Общее — в `selection.Filters`, своё — порядок строк.

    Период и канал отбирают отгрузки, поиск — материалы. Это разные вещи,
    и поиск поэтому применяется после разворачивания: строка таблицы здесь —
    сырьё, а не проданный товар. Искать «воду» среди проданного бессмысленно,
    её не продают.
    """

    ordering: str = DEFAULT_ORDERING


def rows_of(materials: list[Consumed], prices: dict[int, PurchasePrice]) -> list[dict]:
    """Строки таблицы вместе с составляющими своих расчётных чисел."""
    return [
        {
            "material_id": item.product.pk,
            "name": item.product.name,
            "article": item.product.article,
            "code": item.product.code,
            "uom": item.product.uom.name if item.product.uom else "",
            "quantity": item.quantity,
            "products_count": len(item.sources),
            # Цена приходит рядом со стоимостью: формулу фронт собирает
            # из полученного, а не пересчитывает сам.
            "price_kopecks": _price_of(prices.get(item.product.pk)),
            "price_moment": _moment_of(prices.get(item.product.pk)),
            "cost_kopecks": cost_of(item.quantity, prices.get(item.product.pk)),
        }
        for item in materials
    ]


def _price_of(price: PurchasePrice | None) -> Decimal | None:
    return price.price_kopecks if price else None


def _moment_of(price: PurchasePrice | None):
    return price.moment if price else None


def cost_of(quantity: Decimal, price: PurchasePrice | None) -> int | None:
    """Стоимость израсходованного, целыми копейками. None — цены нет вовсе.

    Округляется здесь, а не в подвале: итог собирается сложением того, что
    показано в колонке, и без этого расходился бы с ней на копейки — ровно
    там, где человек проверяет сложением на калькуляторе.

    Ноль вместо None не годится: он читался бы как «материал достался даром»,
    а на деле его просто ни разу не покупали. Таких три из ста шестидесяти
    одного, и все — доли грамма.
    """
    if price is None:
        return None
    return int((quantity * price.price_kopecks).quantize(_KOPECK, rounding=ROUND_HALF_UP))


def _matches(row: dict, term: str) -> bool:
    """Поиск по материалу: название, артикул, код — как у соседней страницы."""
    needle = term.strip().casefold()
    return any(
        needle in (row[key] or "").casefold() for key in ("name", "article", "code")
    )


# По чему сравнивают строки для каждого разрешённого ключа сортировки.
_SORT_KEYS = {
    "cost": lambda row: row["cost_kopecks"],
    "quantity": lambda row: row["quantity"],
    # Доля пропорциональна стоимости в пределах одной выборки: делить каждую
    # строку на одно и то же число порядок не меняет.
    "share": lambda row: row["cost_kopecks"],
    "products": lambda row: row["products_count"],
    "name": lambda row: row["name"].casefold(),
}


def _sorted(rows: list[dict], ordering: str) -> list[dict]:
    """Порядок показа. Строки без цены всегда внизу.

    Без цены нельзя сказать ни «дорогой», ни «дешёвый», и в списке «самое
    дорогое сырьё» такая строка не имеет права стоять первой. Они сортируются
    отдельным списком, а не хитрым ключом: переворот направления иначе
    поднял бы их наверх.

    Ничьи разрешает `material_id`: без него строки с равной стоимостью шли бы
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
    сотня: разворот техкарт стоит одного прохода, и делать его дважды —
    ради страницы и ради файла — незачем.
    """
    result = consumption.of_shipments(
        date_from=filters.date_from,
        date_to=filters.date_to,
        channel_id=filters.channel_id,
    )
    prices = last_purchase_prices(item.product.pk for item in result.materials)

    everything = rows_of(result.materials, prices)
    # Доля материала считается от стоимости **всей** выборки, а не найденного:
    # иначе после поиска «вода» её доля показала бы 100%, хотя воды в сырье
    # восемь процентов.
    selection_cost = _sum_cost(everything)
    for row in everything:
        row["cost_share"] = share(row["cost_kopecks"], selection_cost)

    rows = everything
    if filters.search:
        rows = [row for row in everything if _matches(row, filters.search)]

    return {
        "rows": _sorted(rows, filters.ordering),
        # Итог под таблицей — про то, что в ней видно: он обязан сходиться
        # со сложением колонки, иначе человек проверит на калькуляторе
        # и получит другое число.
        "totals": _table_totals(rows, selection_cost),
        # Сводка — про выборку отгрузок целиком. Поиск её не трогает:
        # он сужает список материалов, а не то, что отгрузили.
        "coverage": _coverage(everything, selection_cost, result),
        # Поиск не применяется и здесь: блок объясняет, чего в расчёте нет
        # вовсе. Исчезни он от запроса «вода», человек читал бы таблицу
        # как полную, хотя пять наименований в неё не вошли.
        "without_plan": result.without_plan,
    }


def page(filters: Filters) -> dict:
    """Всё, что нужно странице, за один разворот техкарт."""
    whole = prepared(filters)
    rows = whole["rows"]

    start, end = selection.page_bounds(filters.page, filters.page_size)

    return {
        "count": len(rows),
        "totals": whole["totals"],
        "coverage": whole["coverage"],
        "results": rows[start:end],
        "without_plan": whole["without_plan"],
    }


def _sum_cost(rows: list[dict]) -> int:
    return sum(row["cost_kopecks"] for row in rows if row["cost_kopecks"] is not None)


def _table_totals(rows: list[dict], selection_cost: int) -> dict:
    """Итог по строкам таблицы — с учётом поиска.

    Доля считается от стоимости всей выборки, как и у отдельных строк.
    Без поиска это ровно сто процентов, с поиском — сколько найденное
    занимает в общем сырье. Написать «100 %» жёстко значило бы поставить
    над колонкой, где доли складываются в восемь процентов, итог «сто».
    """
    priced = [row for row in rows if row["cost_kopecks"] is not None]
    cost = _sum_cost(rows)
    return {
        "materials_count": len(rows),
        "cost_kopecks": cost,
        "cost_share": share(cost, selection_cost),
        "priced_count": len(priced),
        "unpriced_count": len(rows) - len(priced),
    }


def _coverage(
    everything: list[dict], selection_cost: int, result: consumption.Consumption
) -> dict:
    """Насколько полное число видит человек — по выборке, а не по поиску.

    Числитель и знаменатель здесь обязаны быть об одном и том же множестве.
    Возьми стоимость с учётом поиска, а выручку без — получится дробь,
    которая выглядит обычным процентом и врёт, не подавая вида.
    """
    priced = [row for row in everything if row["cost_kopecks"] is not None]
    return {
        "materials_count": len(everything),
        "cost_kopecks": selection_cost,
        "priced_count": len(priced),
        "unpriced_count": len(everything) - len(priced),
        "sold_products_count": result.exploded_count + len(result.without_plan),
        "exploded_products_count": result.exploded_count,
        "without_plan_count": len(result.without_plan),
        "revenue_kopecks": result.revenue_kopecks,
        "documents_count": result.documents_count,
        # Может быть больше единицы, и это не ошибка: 6 июля 2026 выручка
        # 7,13 ₽ против сырья на 290,91 ₽ — товар отгружали за 0 ₽, а сырьё
        # на него потрачено. Поле обязано вместить такое число, а не упасть.
        "cost_share_of_revenue": share(selection_cost, result.revenue_kopecks),
    }
