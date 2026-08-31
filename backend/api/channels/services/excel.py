"""Выгрузка «Каналы продаж» в XLSX.

Два листа. На первом — то же, что на экране: каналы со сводными числами.
На втором — каждая отгрузка отдельной строкой: дата, номер, канал,
покупатель и сумма.

Второй лист не украшение. Сводное число на первом отвечает «сколько
обычно», а вопросы этого раздела — «откуда взялся такой разброс»
и «кто именно покупает» — требуют самих отгрузок: у «Точки продаж» медиана
чека 2 772 ₽ при отгрузке на 99 495 ₽ в том же канале, и на первом листе
этого не увидеть.

**Разброс уходит текстом, а не двумя числами.** «0,00 — 99 495,50 ₽»
читается как ответ, а две соседние колонки с границами читаются как две
разные величины, которые надо сопоставить самому.
"""

from io import BytesIO

from api.channels.services import channels as service, selection
from api.common import workbook
from api.common.workbook import MONEY, SHARE
from core.dates import local_date
from core.money import rubles

# Порядок и подписи совпадают с экраном: файл, где колонки идут иначе,
# заставляет сверять их глазами.
COLUMNS: tuple[tuple[str, int, str], ...] = (
    ("Канал", 22, "name"),
    ("Отгрузок", 10, "shipments"),
    ("В том числе даром", 18, "free"),
    ("Выручка, ₽", 16, "revenue"),
    ("Доля в выручке", 16, "share"),
    ("Средний чек, ₽", 16, "receipt"),
    ("Разброс чека, ₽", 24, "receipt_span"),
    ("Покупателей", 13, "buyers"),
    ("Товаров", 10, "products"),
    ("Первая отгрузка", 16, "first_date"),
    ("Последняя отгрузка", 18, "last_date"),
)

SHIPMENT_COLUMNS: tuple[tuple[str, int, str], ...] = (
    ("Дата", 12, "date"),
    ("Отгрузка", 12, "number"),
    ("Канал", 22, "channel"),
    ("Покупатель", 38, "buyer"),
    ("Сумма, ₽", 16, "amount"),
)

FORMATS = {
    "revenue": MONEY,
    "receipt": MONEY,
    "share": SHARE,
    "amount": MONEY,
}


def span(receipt) -> str:
    """Границы чека одной ячейкой. Прочерк — отгрузок не было вовсе."""
    if receipt.min_kopecks is None:
        return "—"
    return f"{rubles(receipt.min_kopecks):,.2f} — {rubles(receipt.max_kopecks):,.2f}".replace(
        ",", " "
    ).replace(".", ",")


def build(filters: service.Filters) -> BytesIO:
    """Книга по той же выборке, что на экране, — целиком, а не страницей."""
    whole = service.prepared(filters)
    rows = whole["rows"]

    sheet = workbook.Sheet(
        title="Каналы",
        columns=COLUMNS,
        rows=[
            {
                "name": row["name"],
                "shipments": row["shipments_count"],
                "free": row["receipt"].free_shipments,
                "revenue": rubles(row["revenue_kopecks"]),
                "share": float(row["revenue_share"]) if row["revenue_share"] else None,
                "receipt": rubles(row["receipt"].kopecks),
                "receipt_span": span(row["receipt"]),
                "buyers": row["buyers_count"],
                "products": row["products_count"],
                "first_date": local_date(row["first_moment"]),
                "last_date": local_date(row["last_moment"]),
            }
            for row in rows
        ],
        formats=FORMATS,
        totals={
            "name": "Итого",
            "shipments": whole["totals"]["shipments_count"],
            "revenue": rubles(whole["totals"]["revenue_kopecks"]),
            "share": float(whole["totals"]["revenue_share"])
            if whole["totals"]["revenue_share"]
            else None,
            # Чек в итоге не стоит: медианы не складываются, и число
            # в этой ячейке было бы величиной, которой нет ни у одного канала.
            "buyers": whole["totals"]["buyers_count"],
            "products": whole["totals"]["products_count"],
        },
    )

    shipments = selection.demands(
        date_from=filters.date_from, date_to=filters.date_to
    ).order_by("-moment")
    detail = workbook.Sheet(
        title="Отгрузки",
        columns=SHIPMENT_COLUMNS,
        rows=[
            {
                "date": local_date(shipment.moment),
                "number": shipment.number,
                # Отгрузка без канала на втором листе остаётся: он про учёт,
                # а не про таблицу, и молчаливая потеря строки здесь дала бы
                # файл, который не сходится с самим собой.
                "channel": shipment.sales_channel.name
                if shipment.sales_channel
                else "— без канала —",
                "buyer": shipment.agent.name,
                "amount": rubles(shipment.total_kopecks),
            }
            for shipment in shipments
        ],
        formats=FORMATS,
    )

    return workbook.build(sheet, detail)
