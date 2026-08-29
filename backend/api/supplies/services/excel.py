"""Выгрузка «Материалы в приёмках» в XLSX.

Два листа. На первом — то же, что на экране: наименования со сводными
числами. На втором — каждая закупка отдельной строкой: дата, приёмка,
поставщик, количество, цена.

Второй лист не украшение. Сводное число на первом отвечает «сколько всего»,
а вопросы этого раздела — «когда подорожало» и «у кого дешевле» — требуют
самих закупок. Без них файл открывают, чтобы тут же вернуться на экран.
"""

from io import BytesIO

from api.common import workbook
from api.common.workbook import MONEY, QUANTITY, SHARE, UNIT_PRICE
from api.supplies.services import materials, purchases, selection
from core.money import rubles
from core.text import with_plural

# Порядок и подписи совпадают с экраном: файл, где колонки идут иначе,
# заставляет сверять их глазами.
COLUMNS: tuple[tuple[str, int, str], ...] = (
    ("Код", 12, "code"),
    ("Артикул", 14, "article"),
    ("Материал", 46, "name"),
    ("Ед.", 6, "uom"),
    ("Закуплено", 14, "quantity"),
    ("в т.ч. даром", 14, "free_quantity"),
    ("Сумма, ₽", 16, "amount"),
    ("Доля в закупках", 16, "share"),
    ("Средняя цена, ₽", 18, "avg_price"),
    ("Последняя цена, ₽", 18, "last_price"),
    ("Дата последней", 15, "last_date"),
    ("Поставщик последней", 30, "last_supplier"),
    ("Изменение к предыдущей", 22, "change"),
    ("Закупок", 10, "supplies_count"),
    ("Поставщиков", 12, "suppliers_count"),
)

PURCHASE_COLUMNS: tuple[tuple[str, int, str], ...] = (
    ("Дата", 12, "date"),
    ("Приёмка", 12, "number"),
    ("Поставщик", 32, "supplier"),
    ("Код", 12, "code"),
    ("Артикул", 14, "article"),
    ("Материал", 46, "name"),
    ("Ед.", 6, "uom"),
    ("Количество", 14, "quantity"),
    ("Цена, ₽", 14, "price"),
    ("Сумма, ₽", 16, "amount"),
)

# Excel считает в числах с плавающей точкой, и точность Decimal ему не
# передать. Поэтому в файл уходят рубли числом: он для чтения и сводных
# таблиц, а сверка до копейки идёт по экрану и по самому учёту.
FORMATS = {
    "quantity": QUANTITY,
    "free_quantity": QUANTITY,
    "amount": MONEY,
    "share": SHARE,
    "avg_price": UNIT_PRICE,
    "last_price": UNIT_PRICE,
    "price": UNIT_PRICE,
    "change": SHARE,
}


def build(filters: materials.Filters) -> BytesIO:
    """Собрать книгу по всей выборке фильтров.

    Берёт `prepared`, а не `page`: та режет выборку на страницы, и файл
    молча терял бы всё после двухсотой строки — при том, что строка итога
    считается по всем.
    """
    whole = materials.prepared(filters)

    return workbook.build(
        workbook.Sheet(
            "Материалы в приёмках",
            COLUMNS,
            [_cells(row) for row in whole["rows"]],
            FORMATS,
            _totals_row(whole["totals"]),
        ),
        workbook.Sheet(
            "Закупки",
            PURCHASE_COLUMNS,
            _purchase_rows(filters, {row["material_id"] for row in whole["rows"]}),
            FORMATS,
        ),
    )


def _cells(row: dict) -> dict:
    return {
        "code": row["code"],
        "article": row["article"],
        "name": row["name"],
        "uom": row["uom"],
        "quantity": float(row["quantity"]),
        # Пусто, а не ноль: даром не приходило ничего — это не «пришло ноль».
        "free_quantity": float(row["free_quantity"]) or None,
        "amount": rubles(row["amount_kopecks"]),
        "share": float(row["amount_share"]) if row["amount_share"] is not None else None,
        "avg_price": rubles(row["avg_price_kopecks"]),
        "last_price": rubles(row["last_price_kopecks"]),
        # Дата строкой, а не датой Excel: в ячейке она читается одинаково
        # в любой локали, а сортировать файл по ней никто не станет.
        "last_date": row["last_moment"].strftime("%d.%m.%Y") if row["last_moment"] else "",
        "last_supplier": row["last_supplier"] or "",
        "change": float(row["price_change"]) if row["price_change"] is not None else None,
        "supplies_count": row["supplies_count"],
        "suppliers_count": row["suppliers_count"],
    }


def _purchase_rows(filters: materials.Filters, material_ids: set[int]) -> list[dict]:
    """Закупки тех материалов, что попали на первый лист.

    Поиск учитывается и здесь: два листа одного файла обязаны быть про одно
    и то же. Оставь мы на втором все закупки, сумма по нему не сошлась бы
    с суммой по первому — и какой из двух верен, по файлу не понять.
    """
    positions = selection.supply_positions(
        date_from=filters.date_from,
        date_to=filters.date_to,
        supplier_id=filters.supplier_id,
    ).select_related("product", "product__uom", "uom", "document", "document__agent")

    products = {}
    for position in positions:
        products[position.product_id] = position.product

    rows = []
    for material_id, items in purchases.by_material(positions).items():
        if material_id not in material_ids:
            continue
        product = products[material_id]
        for item in items:
            rows.append(
                {
                    "date": item.moment.strftime("%d.%m.%Y"),
                    "number": item.number,
                    "supplier": item.supplier,
                    "code": product.code,
                    "article": product.article,
                    "name": product.name,
                    "uom": next(iter(item.uoms), ""),
                    "quantity": float(item.quantity),
                    "price": rubles(item.price_kopecks),
                    "amount": rubles(item.amount_kopecks),
                }
            )

    # Хронологически: лист читают как ленту закупок, а не как список товаров.
    rows.sort(key=lambda row: (row["date"][6:], row["date"][3:5], row["date"][:2]))
    return rows


def _totals_row(totals: dict) -> dict:
    """Итог по строкам файла, а не по всей выборке.

    **Все четыре числа — про одно множество.** Сумма и доля брались из итога,
    а приёмки с поставщиками — из охвата, и подвал при выгрузке с поиском
    читался как «Итого · 8 материалов … Закупок 93 · Поставщиков 22», где
    93 и 22 описывают все 212 наименований. Дробь, где числитель от найденного,
    а знаменатель от всего, выглядит обычной и врёт, не подавая вида.
    """
    return {
        "name": "Итого · "
        + with_plural(
            totals["materials_count"], "материал", "материала", "материалов"
        ),
        "amount": rubles(totals["amount_kopecks"]),
        "share": float(totals["amount_share"])
        if totals["amount_share"] is not None
        else None,
        "supplies_count": totals["documents_count"],
        "suppliers_count": totals["suppliers_count"],
    }
