"""Выгрузка «Инвентаризация» в XLSX.

Два листа. На первом — то же, что на экране: позиции номенклатуры с датой
последнего пересчёта и его итогом. На втором — сами инвентаризации: когда,
на каком складе и сколько позиций разошлось.

Второй лист не украшение: первый отвечает «что не сходится у этой позиции»,
а вопрос «чем вообще считали» — про документы, и в списке позиций его
не видно. Складов три, и пересчёт всегда трогает один.

**«Никогда» уходит словом, а не пустой ячейкой.** Пустая читается как
«данные не доехали», а «никогда» — это ответ, и он же главный на странице:
таких позиций 239 из 312.
"""

from io import BytesIO

from api.common import workbook
from api.common.workbook import MONEY, QUANTITY, SHARE, UNIT_PRICE
from api.inventory.services import blocks, selection
from api.inventory.services import inventory as service
from core.money import rubles

# Порядок и подписи совпадают с экраном: файл, где колонки идут иначе,
# заставляет сверять их глазами.
COLUMNS: tuple[tuple[str, int, str], ...] = (
    ("Позиция", 44, "name"),
    ("Артикул", 14, "article"),
    ("Папка", 30, "folder"),
    ("Единица", 10, "uom"),
    ("Считали", 14, "last_date"),
    ("Склад", 20, "store"),
    ("Дней назад", 12, "days_ago"),
    ("Пересчётов", 12, "counted_times"),
    ("Из них с расхождением", 22, "diverged_times"),
    ("Сейчас на складе", 18, "stock"),
    ("Числилось", 14, "calculated"),
    ("Нашли", 14, "counted"),
    ("Расхождение", 14, "correction"),
    ("Себестоимость, ₽", 18, "cost"),
    ("В деньгах, ₽", 16, "money"),
)

DOCUMENT_COLUMNS: tuple[tuple[str, int, str], ...] = (
    ("Дата", 12, "date"),
    ("Номер", 12, "number"),
    ("Склад", 20, "store"),
    ("Позиций", 10, "positions"),
    ("Разошлось", 12, "diverged"),
    ("Доля разошедшихся", 18, "share"),
    ("Комментарий", 46, "description"),
)

FORMATS = {
    "stock": QUANTITY,
    "calculated": QUANTITY,
    "counted": QUANTITY,
    "correction": QUANTITY,
    "cost": UNIT_PRICE,
    "money": MONEY,
    "share": SHARE,
}

NEVER = "никогда"


def build(filters: selection.Filters) -> BytesIO:
    """Собрать книгу по всей выборке фильтров.

    Берёт `prepared`, а не `page`: та режет выборку на страницы, и файл
    молча терял бы всё после двухсотой строки.
    """
    whole = service.prepared(filters)

    return workbook.build(
        workbook.Sheet(
            "Позиции",
            COLUMNS,
            [_cells(row) for row in whole["rows"]],
            FORMATS,
            _totals_row(whole["totals"]),
        ),
        workbook.Sheet(
            "Инвентаризации",
            DOCUMENT_COLUMNS,
            _document_rows(filters),
            FORMATS,
        ),
    )


def _cells(row: dict) -> dict:
    counted = bool(row["counted_times"])
    return {
        "name": row["name"],
        "article": row["article"],
        "folder": row["folder"],
        "uom": row["uom"],
        # Дата строкой: в ячейке она читается одинаково в любой локали.
        "last_date": row["last_moment"].strftime("%d.%m.%Y") if counted else NEVER,
        "store": row["last_store"],
        "days_ago": row["days_ago"],
        "counted_times": row["counted_times"],
        "diverged_times": row["diverged_times"],
        "stock": row["stock_quantity"],
        "calculated": row["calculated"],
        "counted": row["counted"],
        "correction": row["correction"],
        "cost": rubles(row["cost_kopecks"]),
        "money": rubles(row["correction_money_kopecks"]),
    }


def _document_rows(filters: selection.Filters) -> list[dict]:
    rows = []
    for item in blocks.documents(filters)["items"]:
        rows.append(
            {
                "date": item["moment"].strftime("%d.%m.%Y"),
                "number": item["number"],
                "store": item["store_name"],
                "positions": item["positions_count"],
                "diverged": item["diverged_count"],
                "share": item["diverged_count"] / item["positions_count"]
                if item["positions_count"] else None,
                "description": item["description"],
            }
        )
    return rows


def _totals_row(totals: dict) -> dict:
    """Итог по строкам файла, а не по всей выборке: с поиском они разные."""
    return {
        "name": f"Итого · позиций {totals['products_count']}",
        "counted_times": f"не считали {totals['never_counted_count']}",
        "diverged_times": totals["diverged_count"],
        "money": rubles(totals["money_kopecks"]),
    }
