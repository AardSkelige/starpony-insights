"""Выгрузка «Прибыльность» в XLSX.

Два листа, и второй не украшение. На первом — то же, что на экране: товар,
выручка, себестоимость, прибыль, маржа. На втором — линейки продукции:
вопрос «на какой линейке зарабатываем» решается не по товарам, а по группам,
и складывать 53 строки в уме ради него не должен никто.

**Оговорка про площадки едет в файл вместе с числами.** Отдельной колонкой
«в т.ч. через площадки» — иначе выгруженная маржа Озона в 90,5 % отправится
в чужую переписку без единого признака, что комиссия из неё не вычтена.
"""

from io import BytesIO

from api.common import workbook
from api.common.workbook import MONEY, QUANTITY, SHARE
from api.profitability.services import profitability as service
from api.profitability.services.selection import Basis, Filters
from core.money import rubles

# Порядок и подписи совпадают с экраном: файл, где колонки идут иначе,
# заставляет сверять их глазами.
COLUMNS: tuple[tuple[str, int, str], ...] = (
    ("Артикул", 14, "article"),
    ("Товар", 46, "name"),
    ("Линейка", 26, "family"),
    ("Продано", 11, "quantity"),
    ("Выручка, ₽", 15, "revenue"),
    ("Себестоимость, ₽", 18, "cost"),
    ("Прибыль, ₽", 15, "profit"),
    ("Маржа", 10, "margin"),
    ("Доля в прибыли", 15, "share"),
    ("Через площадки, ₽", 18, "marketplace"),
    ("Отдано даром, шт", 17, "free"),
    ("На реализации, шт", 18, "unsold"),
)

FAMILY_COLUMNS: tuple[tuple[str, int, str], ...] = (
    ("Линейка", 32, "name"),
    ("Товаров", 10, "products"),
    ("Выручка, ₽", 16, "revenue"),
    ("Себестоимость, ₽", 18, "cost"),
    ("Прибыль, ₽", 16, "profit"),
    ("Маржа", 10, "margin"),
)

FORMATS = {
    "quantity": QUANTITY,
    "revenue": MONEY,
    "cost": MONEY,
    "profit": MONEY,
    "margin": SHARE,
    "share": SHARE,
    "marketplace": MONEY,
    "free": QUANTITY,
    "unsold": QUANTITY,
}


def _family(folder: str) -> str:
    """Линейка — последнее звено пути группы, как и на экране."""
    return (folder or "").split("/")[-1] or "Без группы"


def _row(row: dict) -> dict:
    return {
        "article": row["article"],
        "name": row["name"],
        "family": _family(row["folder"]),
        "quantity": row["quantity"],
        "revenue": rubles(row["revenue_kopecks"]),
        "cost": rubles(row["cost_kopecks"]),
        "profit": rubles(row["profit_kopecks"]),
        "margin": row["margin"],
        "share": row["profit_share"],
        "marketplace": rubles(row["marketplace_revenue_kopecks"]),
        "free": row["free_quantity"],
        "unsold": row["unsold_quantity"],
    }


def build(filters: Filters) -> BytesIO:
    """Книга по всей выборке, а не по видимой странице.

    Строки берутся из `select`, а не из `page`: высота страницы подрезается
    потолком в 200, и хвост выборки исчез бы из файла молча.
    """
    selection = service.select(filters)
    rows = service.with_share(selection.ordered, selection.denominator)
    totals = selection.totals

    return workbook.build(
        workbook.Sheet(
            title=_title(filters),
            columns=COLUMNS,
            rows=[_row(row) for row in rows],
            formats=FORMATS,
            totals={
                "article": "Итого",
                "name": f"{totals['products_count']} товаров",
                "quantity": totals["quantity"],
                "revenue": rubles(totals["revenue_kopecks"]),
                "cost": rubles(totals["cost_kopecks"]),
                "profit": rubles(totals["profit_kopecks"]),
                "margin": totals["margin"],
            },
        ),
        workbook.Sheet(
            title="По линейкам",
            columns=FAMILY_COLUMNS,
            rows=[
                {
                    "name": family["name"],
                    "products": family["products_count"],
                    "revenue": rubles(family["revenue_kopecks"]),
                    "cost": rubles(family["cost_kopecks"]),
                    "profit": rubles(family["profit_kopecks"]),
                    "margin": family["margin"],
                }
                for family in selection.families
            ],
            formats=FORMATS,
        ),
    )


def _title(filters: Filters) -> str:
    """Имя листа называет базу расчёта.

    Без этого два файла за один период выглядят одинаково и расходятся
    на 281 126 ₽ — а объяснения в них нет ни строчки.
    """
    return "Продано" if filters.basis == Basis.SOLD else "Отгружено"
