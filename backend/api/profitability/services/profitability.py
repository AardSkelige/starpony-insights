"""Страница «Прибыльность»: что попадает в выборку и в каком порядке.

Здесь всё, что меняется вместе с **фильтрами**. Сборка самой строки —
в `rows.py`, она меняется вместе с вопросом «из чего складывается маржа».
Блоки под таблицей — в `blocks.py`, они меняются вместе с вопросами,
которые задают к выборке.
"""

from dataclasses import dataclass
from decimal import Decimal

from api.common.selection import page_bounds
from api.profitability.services import blocks, rows as row_builder
from api.profitability.services.selection import Filters

ZERO = Decimal(0)

# Сортировки, разрешённые снаружи. Список закрытый: строки сортируются
# в Python, но открытый перечень всё равно пустил бы в ключ что угодно.
# Минус означает убывание — как принято везде, от DRF до SQL.
ORDERING = {
    "profit": ("profit_kopecks", False),
    "-profit": ("profit_kopecks", True),
    "margin": ("margin", False),
    "-margin": ("margin", True),
    "revenue": ("revenue_kopecks", False),
    "-revenue": ("revenue_kopecks", True),
    "quantity": ("quantity", False),
    "-quantity": ("quantity", True),
    "cost": ("cost_kopecks", False),
    "-cost": ("cost_kopecks", True),
    "name": ("name", False),
    "-name": ("name", True),
}
DEFAULT_ORDERING = "-profit"


def _sort_key(row: dict, field: str):
    """Ключ сортировки, кладущий неизвестное в конец при любом направлении.

    `None` в марже — это «посчитать не из чего», а не «маржа нулевая».
    Без этой пары строка без себестоимости оказалась бы первой в списке
    самых прибыльных — там, где на неё точно посмотрят.
    """
    value = row.get(field)
    if field == "name":
        return (0, str(value or "").casefold())
    return (0, value) if value is not None else (1, ZERO)


def _ordered(items: list[dict], ordering: str) -> list[dict]:
    field, reverse = ORDERING.get(ordering, ORDERING[DEFAULT_ORDERING])
    unknown_last = [row for row in items if row.get(field) is not None]
    unknown = [row for row in items if row.get(field) is None]
    # Артикул последним ключом: без него строки с равными числами идут
    # в порядке, который база не обязана сохранять между запросами, —
    # товар попал бы на две страницы подряд либо ни на одну.
    unknown_last.sort(key=lambda row: (_sort_key(row, field), row["article"]), reverse=reverse)
    unknown.sort(key=lambda row: row["article"])
    return unknown_last + unknown


def _meaningful(row: dict) -> bool:
    """Есть ли о чём говорить в этой строке.

    Товар, у которого в выбранной базе не осталось ни штук, ни выручки,
    строкой быть не должен: четыре позиции «Амуниция» уходили только даром,
    и при выключенных подарках от них остаются одни нули. Они не исчезают
    из ответа — их считает блок полноты расчёта, и число там сходится
    с числом скрытых строк.
    """
    return bool(row["quantity"]) or bool(row["revenue_kopecks"])


@dataclass(frozen=True)
class Selection:
    """Посчитанная выборка целиком, до нарезки на страницы.

    Отдельно от `page`, потому что выгрузка берёт **все** строки, а не сто:
    высота страницы подрезается потолком в 200, и позови выгрузка `page`
    с большим числом, хвост выборки исчез бы из файла молча.

    Итоги и линейки лежат здесь же, а не считаются вызывающим: экран
    и файл обязаны показать одни и те же числа, а два места расчёта
    однажды разойдутся.
    """

    ordered: list[dict]
    totals: dict
    coverage: dict
    marketplaces: dict
    families: list[dict]
    losses: list[dict]
    denominator: int


def select(filters: Filters) -> Selection:
    """Строки выборки в порядке показа, вместе со знаменателем доли.

    **Знаменатель доли считается без поиска.** Период и база в него входят,
    поиск — нет: набрав «шампунь», человек сужает список строк, а не то,
    что продали. Иначе, найдя один товар, он увидел бы «100 %» — дефект,
    найденный на трёх страницах подряд.
    """
    everything = row_builder.build(filters)
    visible = [row for row in everything if _meaningful(row)]
    hidden = [row for row in everything if not _meaningful(row)]

    denominator = sum(
        row["profit_kopecks"] for row in visible if row["profit_kopecks"]
    )

    found = visible
    if filters.search:
        term = filters.search.strip().casefold()
        found = [
            row for row in visible
            if term in row["name"].casefold()
            or term in (row["article"] or "").casefold()
            or term in (row["code"] or "").casefold()
        ]

    return Selection(
        ordered=_ordered(found, filters.ordering),
        totals=blocks.totals_of(found),
        coverage=blocks.coverage_of(visible, hidden, filters),
        marketplaces=blocks.marketplaces_of(visible),
        families=blocks.families_of(visible),
        losses=blocks.losses_of(visible),
        denominator=denominator,
    )


def with_share(rows: list[dict], denominator: int) -> list[dict]:
    """Доля строки в прибыли всей выборки. `None` — делить не на что."""
    return [
        {
            **row,
            "profit_share": (
                Decimal(row["profit_kopecks"]) / Decimal(denominator)
                if row["profit_kopecks"] and denominator > 0
                else None
            ),
        }
        for row in rows
    ]


def page(filters: Filters) -> dict:
    """Всё, что нужно странице, за один расчёт строк."""
    selection = select(filters)
    start, end = page_bounds(filters.page, filters.page_size)

    return {
        "count": len(selection.ordered),
        "results": with_share(selection.ordered[start:end], selection.denominator),
        "totals": selection.totals,
        "coverage": selection.coverage,
        "marketplaces": selection.marketplaces,
        "families": selection.families,
        "losses": selection.losses,
    }
