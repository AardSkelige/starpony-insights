"""Выгрузка «Материалы в отгрузках» в XLSX.

Два листа, а не один. На первом сырьё; на втором — те наименования, которые
техкарты не имеют. Свести их в одну таблицу нельзя: доставка не сырьё,
и в сумму материалов она не входит — а в общем списке кто-нибудь её
обязательно сложит вместе с остальным.
"""

from io import BytesIO

from api.common import workbook
from api.common.workbook import MONEY, QUANTITY, SHARE, UNIT_PRICE
from api.shipments.services import materials
from core.money import rubles
from core.text import with_plural

# Порядок и подписи совпадают с экраном: файл, где колонки идут иначе,
# заставляет сверять их глазами.
COLUMNS: tuple[tuple[str, int, str], ...] = (
    ("Код", 12, "code"),
    ("Артикул", 14, "article"),
    ("Материал", 46, "name"),
    ("Ед.", 6, "uom"),
    ("Израсходовано", 16, "quantity"),
    ("Цена последней закупки, ₽", 24, "price"),
    ("Дата закупки", 14, "price_date"),
    ("Стоимость, ₽", 16, "cost"),
    ("Доля в стоимости", 16, "share"),
    ("Изделий", 10, "products_count"),
)

WITHOUT_PLAN_COLUMNS: tuple[tuple[str, int, str], ...] = (
    ("Код", 12, "code"),
    ("Артикул", 14, "article"),
    ("Наименование", 46, "name"),
    ("Вид", 12, "kind"),
    ("Ед.", 6, "uom"),
    ("Продано", 14, "quantity"),
    ("Выручка, ₽", 16, "revenue"),
)

# Excel считает в числах с плавающей точкой, и точность Decimal ему не
# передать. Поэтому в файл уходят рубли числом: он для чтения и сводных
# таблиц, а сверка до копейки идёт по экрану и по самому учёту.
FORMATS = {
    "quantity": QUANTITY,
    "price": UNIT_PRICE,
    "cost": MONEY,
    "share": SHARE,
    "revenue": MONEY,
}


def build(filters: materials.Filters) -> BytesIO:
    """Собрать книгу по всей выборке фильтров.

    Берёт `prepared`, а не `page`: та режет выборку на страницы, и файл
    молча терял бы всё после двухсотой строки — при том, что строка итога
    считается по всем. Сегодня материалов 161, и обрезка была бы не видна
    до первого расширения периода.
    """
    whole = materials.prepared(filters)

    return workbook.build(
        workbook.Sheet(
            "Материалы в отгрузках",
            COLUMNS,
            [_cells(row) for row in whole["rows"]],
            FORMATS,
            _totals_row(whole["totals"]),
        ),
        # Лист создаётся всегда, даже пустым: его отсутствие человек прочтёт
        # как «всё развернулось», а это разные вещи — и проверить их нечем.
        workbook.Sheet(
            "Без техкарты",
            WITHOUT_PLAN_COLUMNS,
            [_without_plan_cells(row) for row in whole["without_plan"]],
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
        "price": rubles(row["price_kopecks"]),
        # Дата строкой, а не датой Excel: в ячейке она читается одинаково
        # в любой локали, а сортировать файл по ней никто не станет.
        "price_date": row["price_moment"].strftime("%d.%m.%Y") if row["price_moment"] else "",
        "cost": rubles(row["cost_kopecks"]),
        "share": float(row["cost_share"]) if row["cost_share"] is not None else None,
        "products_count": row["products_count"],
    }


def _without_plan_cells(row: dict) -> dict:
    return {
        "code": row["code"],
        "article": row["article"],
        "name": row["name"],
        "kind": "Услуга" if row["is_service"] else "Товар",
        "uom": row["uom"],
        "quantity": float(row["quantity"]),
        "revenue": rubles(row["revenue_kopecks"]),
    }


def _totals_row(totals: dict) -> dict:
    """Итог по строкам файла, а не по всей выборке.

    Иначе при выгрузке с поиском сумма в подвале не сойдётся со сложением
    колонки — а файл открывают именно для того, чтобы складывать.

    **У колонки «Изделий» итога нет намеренно.** Сложить её нельзя: одно
    изделие даёт несколько материалов и было бы посчитано столько раз,
    сколько в нём сырья. А число развёрнутых изделий из охвата описывает
    всю выборку — при выгрузке с поиском оно оказалось бы подписью
    к восьми показанным строкам.
    """
    return {
        "name": "Итого · "
        + with_plural(
            totals["materials_count"], "материал", "материала", "материалов"
        ),
        "cost": rubles(totals["cost_kopecks"]),
    }
