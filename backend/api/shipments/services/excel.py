"""Выгрузка «Товары в отгрузках» в XLSX.

Отдельным модулем от расчёта: сводка по товарам нужна и экрану, и файлу,
а знание про ширину колонки и формат ячейки — только файлу. Как устроена
сама книга — в `workbook.py`, общем для выгрузок раздела.
"""

from io import BytesIO

from api.shipments.services import products, workbook
from api.shipments.services.workbook import MONEY, QUANTITY, SHARE
from core.money import rubles
from core.text import with_plural

# Порядок и подписи совпадают с экраном: файл, где колонки идут иначе,
# заставляет сверять их глазами.
COLUMNS: tuple[tuple[str, int, str], ...] = (
    ("Код", 12, "code"),
    ("Артикул", 14, "article"),
    ("Наименование", 52, "name"),
    ("Ед.", 6, "uom"),
    ("Продано", 12, "quantity"),
    ("в т.ч. даром", 13, "free_quantity"),
    ("Выручка, ₽", 15, "revenue"),
    ("Средняя цена продажи, ₽", 22, "avg_price"),
    ("Без учёта бесплатных, ₽", 22, "avg_price_paid"),
    ("Доля в выручке", 15, "share"),
    ("Отгрузок", 10, "documents_count"),
)

# Сколько строк тянуть из базы за раз. Своя мера, а не высота страницы:
# совпадение чисел здесь ничего не значит, а связь заставила бы менять
# запрос к базе всякий раз, когда меняют вид таблицы на экране.
CHUNK = 200

# Excel считает в числах с плавающей точкой, и точность Decimal ему не
# передать. Поэтому в файл уходят рубли числом: он для чтения и сводных
# таблиц, а сверка до копейки идёт по экрану и по самому учёту.
FORMATS = {
    "quantity": QUANTITY,
    "free_quantity": QUANTITY,
    "revenue": MONEY,
    "avg_price": MONEY,
    "avg_price_paid": MONEY,
    "share": SHARE,
}


def build(filters: products.Filters) -> BytesIO:
    """Собрать книгу по всей выборке фильтров."""
    totals = products.summary(filters)
    return workbook.build(
        workbook.Sheet(
            "Товары в отгрузках",
            COLUMNS,
            (_cells(row) for row in _every_row(filters, totals["revenue_kopecks"])),
            FORMATS,
            _totals_row(totals),
        )
    )


def _cells(row: dict) -> dict:
    return {
        "code": row["code"],
        "article": row["article"],
        "name": row["name"],
        "uom": row["uom"],
        "quantity": float(row["quantity"]),
        "free_quantity": float(row["free_quantity"]),
        "revenue": rubles(row["revenue_kopecks"]),
        "avg_price": rubles(row["avg_price_kopecks"]),
        "avg_price_paid": rubles(row["avg_price_paid_kopecks"]),
        "share": float(row["revenue_share"]) if row["revenue_share"] is not None else None,
        "documents_count": row["documents_count"],
    }


def _every_row(filters: products.Filters, total_revenue: int):
    """Все строки выборки, пачками.

    Идёт по срезам запроса напрямую, а не через `products.page`: та на каждый
    вызов пересчитывает итоги и общее число строк, и на выгрузке из тысячи
    позиций это пять лишних проходов по всем документам.
    """
    chosen = products.grouped(filters)
    start = 0
    while True:
        chunk = list(chosen[start : start + CHUNK])
        if not chunk:
            return
        for item in chunk:
            yield products.row_of(item, total_revenue)
        if len(chunk) < CHUNK:
            return
        start += CHUNK


def _totals_row(totals: dict) -> dict:
    return {
        "name": "Итого · "
        + with_plural(
            totals["products_count"], "наименование", "наименования", "наименований"
        ),
        "quantity": float(totals["quantity"]),
        "free_quantity": float(totals["free_quantity"]),
        "revenue": rubles(totals["revenue_kopecks"]),
        "documents_count": totals["documents_count"],
    }
