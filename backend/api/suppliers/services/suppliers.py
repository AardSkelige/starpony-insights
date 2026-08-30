"""Страница «Поставщики»: кто, на сколько, как часто и как долго везёт.

Строка — поставщик, слагаемые строки — его приёмки. Четыре числа отвечают
на разные вопросы, и ни одно не заменяет другое: сумма — «сколько денег туда
уходит», регулярность — «как часто привозит», срок поставки — «сколько ждать
после заказа», наименования — «насколько он нам незаменим».

**Сумма берётся из документа, а не складывается из строк.** Позиции сходятся
с суммой документа на всех 387 документах, но сойтись перестанут ровно тогда,
когда синхронизация пропустит позицию, — а она об этом честно предупреждает
счётчиком. Сумма документа при этом остаётся фактом учёта, и брать надо её.

**Расчётные числа отдаются составляющими, а не готовым текстом.** Медиана
приходит вместе с разбросом и средним, из которых получена: у «Ревады-Невы»
две поставки, 2 и 40 дней, и медиана 21 без разброса рядом описывает срок,
которого не было ни разу.
"""

from decimal import Decimal

from api.common.selection import page_bounds
from api.suppliers.services import regularity, selection, summary
from core.money import share
from core.services import lead_time
from core.services.documents import positions_in

# Сколько наименований показать поимённо в разборе строки. Остальные —
# строкой «ещё N», как у распределения расхода на соседней странице: хвост
# сворачивается, но не выбрасывается, иначе слагаемые не складываются
# в сумму поставщика.
MATERIAL_LIMIT = 5

# Сортировки, разрешённые снаружи. Список закрытый — как у соседних страниц.
ORDERING = (
    "amount", "-amount",
    "name", "-name",
    "supplies", "-supplies",
    "materials", "-materials",
    "last", "-last",
    "regularity", "-regularity",
    "lead_time", "-lead_time",
)
DEFAULT_ORDERING = "-amount"

Filters = selection.Filters


def row_of(agent_id: int, name: str, supplies: list, positions: list) -> dict:
    """Строка таблицы вместе с составляющими своих расчётных чисел."""
    pace = regularity.of(supplies)
    waiting = lead_time.of(supplies)
    moments = sorted(supply.moment for supply in supplies)

    return {
        "supplier_id": agent_id,
        "name": name,

        "supplies_count": len(supplies),
        # Дней поставок, а не документов: три приёмки одним днём — это одна
        # поставка, разбитая на бумаги. Их шесть на боевых данных, и без
        # различия регулярность считалась бы по интервалам в ноль дней.
        "delivery_days": pace.delivery_days,
        "amount_kopecks": sum(supply.total_kopecks for supply in supplies),

        "first_moment": moments[0],
        "last_moment": moments[-1],

        "materials_count": len({position.product_id for position in positions}),
        "positions_count": len(positions),
        # Позиции, пришедшие даром: у «Принтеца» 97 из 129 — образцы, бонусы
        # и допечатка этикеток. Без этого числа «46 наименований на 55 100 ₽»
        # выглядит странно и нечем объяснить.
        "free_positions_count": sum(
            1 for position in positions if position.total_kopecks <= 0
        ),

        "regularity": pace,
        "lead_time": waiting,

        # Что именно у него берём. До сих пор страница отвечала только числом
        # «39 наименований», а на вопрос «каких» — ничем: чтобы узнать,
        # приходилось идти на соседнюю страницу и фильтровать по поставщику.
        "materials": _materials(positions),

        # Наименования — для итога по показанным строкам: сложить
        # `materials_count` нельзя, 21 материал приходит больше чем от одного
        # поставщика и был бы посчитан дважды. В ответ не уходит.
        "material_ids": {position.product_id for position in positions},
    }


def _materials(positions: list) -> dict:
    """Крупнейшие наименования поставщика по сумме, хвост — строкой.

    По сумме, а не по количеству: количества у материалов в разных единицах
    (граммы против штук), и сложить их нельзя, а сравнить длиной полосы —
    тем более. Деньги — единственное, что у них общее.
    """
    by_product: dict[int, dict] = {}
    for position in positions:
        entry = by_product.setdefault(
            position.product_id,
            {"name": position.product.name, "amount_kopecks": 0},
        )
        entry["amount_kopecks"] += position.total_kopecks

    rows = sorted(
        by_product.values(), key=lambda item: item["amount_kopecks"], reverse=True
    )
    total = sum(item["amount_kopecks"] for item in rows)
    shown, rest = rows[:MATERIAL_LIMIT], rows[MATERIAL_LIMIT:]

    return {
        "items": [
            {**item, "share": share(item["amount_kopecks"], total)} for item in shown
        ],
        "rest_count": len(rest),
        "rest_amount_kopecks": sum(item["amount_kopecks"] for item in rest),
    }


def _matches(row: dict, term: str) -> bool:
    """Поиск по названию поставщика. Больше искать здесь не по чему:
    артикула и кода у контрагента нет."""
    return term.strip().casefold() in row["name"].casefold()


# По чему сравнивают строки для каждого разрешённого ключа сортировки.
_SORT_KEYS = {
    "amount": lambda row: row["amount_kopecks"],
    "supplies": lambda row: row["supplies_count"],
    "materials": lambda row: row["materials_count"],
    "last": lambda row: row["last_moment"],
    "name": lambda row: row["name"].casefold(),
    "regularity": lambda row: row["regularity"].days,
    "lead_time": lambda row: row["lead_time"].days,
}


def _sorted(rows: list[dict], ordering: str) -> list[dict]:
    """Порядок показа. Строки, которым сортировать нечем, всегда внизу.

    О регулярности поставщика с единственной приёмкой сказать нечего —
    семь из двадцати трёх именно таковы. Такие строки идут отдельным списком,
    а не хитрым ключом: переворот направления иначе поднял бы их наверх,
    и список «кто возит реже всех» начинался бы с тех, кто не возил дважды.

    Ничьи разрешает `supplier_id`: без него поставщики с равной суммой шли бы
    в порядке, который не обязан повторяться между запросами.
    """
    if ordering not in ORDERING:
        ordering = DEFAULT_ORDERING
    desc = ordering.startswith("-")
    key = _SORT_KEYS[ordering.lstrip("-")]

    known = [row for row in rows if key(row) is not None]
    unknown = [row for row in rows if key(row) is None]

    known.sort(key=lambda row: (key(row), row["supplier_id"]), reverse=desc)
    unknown.sort(key=lambda row: row["supplier_id"])
    return known + unknown


def prepared(filters: Filters) -> dict:
    """Все строки выборки и оба набора итогов — без нарезки на страницы.

    Отдельно от `page`, потому что выгрузке нужны **все** строки: приёмки
    читаются одним запросом, и делать его дважды — ради страницы и ради
    файла — незачем.
    """
    supplies = list(
        selection.supplies(date_from=filters.date_from, date_to=filters.date_to)
    )
    positions = list(
        positions_in(
            selection.supplies(
                date_from=filters.date_from, date_to=filters.date_to
            )
        ).select_related("document", "product")
    )

    by_agent: dict[int, list] = {}
    names: dict[int, str] = {}
    for supply in supplies:
        by_agent.setdefault(supply.agent_id, []).append(supply)
        names[supply.agent_id] = supply.agent.name

    positions_by_agent: dict[int, list] = {}
    for position in positions:
        positions_by_agent.setdefault(position.document.agent_id, []).append(position)

    everything = [
        row_of(agent_id, names[agent_id], items, positions_by_agent.get(agent_id, []))
        for agent_id, items in by_agent.items()
    ]

    # Доля поставщика считается от суммы **всей** выборки, а не найденного:
    # иначе после поиска «принт» его доля показала бы 100 %, хотя на «Принтец»
    # приходится шестнадцатая часть закупок.
    selection_amount = sum(row["amount_kopecks"] for row in everything)
    for row in everything:
        row["amount_share"] = share(row["amount_kopecks"], selection_amount)

    rows = everything
    if filters.search:
        rows = [row for row in everything if _matches(row, filters.search)]

    return {
        # Итог под таблицей — про то, что в ней видно: он обязан сходиться
        # со сложением колонки при любом поиске.
        "totals": summary.table_totals(rows, selection_amount),
        # Сводка — про выборку приёмок целиком. Поиск её не трогает: он сужает
        # список поставщиков, а не то, что закупили.
        "coverage": summary.coverage(everything, positions, selection_amount),
        "rows": _sorted(rows, filters.ordering),
    }


def page(filters: Filters) -> dict:
    """Всё, что нужно странице, за два запроса: приёмки и их строки."""
    whole = prepared(filters)
    rows = whole["rows"]

    start, end = page_bounds(filters.page, filters.page_size)

    return {
        "count": len(rows),
        "totals": whole["totals"],
        "coverage": whole["coverage"],
        "results": rows[start:end],
    }


def days_of(value: Decimal | None) -> str:
    """Дни для выгрузки: целое остаётся целым, половина сохраняется.

    В XLSX уходит текстом, а не числом: «0» в колонке срока читается как
    пустая ячейка, а «в тот же день» — как ответ.
    """
    if value is None:
        return "—"
    if value == 0:
        return "в тот же день"
    whole = value.to_integral_value()
    return f"{whole if value == whole else value}".replace(".", ",")
