"""Выгрузка «Поставщики» в XLSX.

Два листа. На первом — то же, что на экране: поставщики со сводными числами.
На втором — каждая поставка отдельной строкой: дата, приёмка, сумма, заказ
и срок по ней.

Второй лист не украшение. Сводное число на первом отвечает «сколько обычно»,
а вопросы этого раздела — «когда сорвался срок» и «почему такой разброс» —
требуют самих поставок: у «Ревады-Невы» медиана 21 день сложилась
из двух поставок, 2 и 40 дней, и на первом листе этого не увидеть.

**Дни уходят текстом, а не числом.** Ноль в колонке срока читается как пустая
ячейка, а «в тот же день» — как ответ. Различие важное: у трёх поставщиков
из двадцати трёх медиана ровно ноль, и это факт учёта, а не пробел.
"""

from io import BytesIO

from api.common import workbook
from api.common.workbook import MONEY, SHARE
from api.suppliers.services import selection, suppliers as service
from core.money import rubles
from core.services import lead_time
from core.services.documents import exists
from core.text import with_plural

# Порядок и подписи совпадают с экраном: файл, где колонки идут иначе,
# заставляет сверять их глазами.
COLUMNS: tuple[tuple[str, int, str], ...] = (
    ("Поставщик", 38, "name"),
    ("Поставок", 10, "supplies"),
    ("Дней поставок", 14, "delivery_days"),
    ("Сумма, ₽", 16, "amount"),
    ("Доля в закупках", 16, "share"),
    ("Наименований", 14, "materials"),
    ("Возит раз в", 14, "regularity"),
    ("Разброс интервала", 18, "regularity_span"),
    ("Срок поставки", 14, "lead_time"),
    ("Разброс срока", 16, "lead_time_span"),
    ("Первая поставка", 16, "first_date"),
    ("Последняя поставка", 18, "last_date"),
)

SUPPLY_COLUMNS: tuple[tuple[str, int, str], ...] = (
    ("Дата", 12, "date"),
    ("Приёмка", 12, "number"),
    ("Поставщик", 38, "supplier"),
    ("Сумма, ₽", 16, "amount"),
    ("Заказ", 12, "order"),
    ("Дата заказа", 14, "order_date"),
    ("Срок поставки", 14, "lead_time"),
)

FORMATS = {
    "amount": MONEY,
    "share": SHARE,
}


def build(filters: service.Filters) -> BytesIO:
    """Собрать книгу по всей выборке фильтров.

    Берёт `prepared`, а не `page`: та режет выборку на страницы, и файл
    молча терял бы всё после двухсотой строки — при том, что строка итога
    считается по всем.
    """
    whole = service.prepared(filters)
    shown = {row["supplier_id"] for row in whole["rows"]}

    return workbook.build(
        workbook.Sheet(
            "Поставщики",
            COLUMNS,
            [_cells(row) for row in whole["rows"]],
            FORMATS,
            _totals_row(whole["totals"]),
        ),
        workbook.Sheet(
            "Поставки",
            SUPPLY_COLUMNS,
            _supply_rows(filters, shown),
            FORMATS,
        ),
    )


def _span(value) -> str:
    """Разброс словами: «0–20 дней». Пусто, когда мерить было нечего.

    Рядом с медианой обязательно: у «Ревады-Невы» срок 21 день сложился
    из 2 и 40, и одно число без разброса описывает поставку, которой не было.
    """
    if value.min_days is None:
        return ""
    if value.min_days == value.max_days:
        return f"{value.min_days}"
    return f"{value.min_days}–{value.max_days}"


def _cells(row: dict) -> dict:
    return {
        "name": row["name"],
        "supplies": row["supplies_count"],
        "delivery_days": row["delivery_days"],
        "amount": rubles(row["amount_kopecks"]),
        "share": float(row["amount_share"]) if row["amount_share"] is not None else None,
        "materials": row["materials_count"],
        "regularity": service.days_of(row["regularity"].days),
        "regularity_span": _span(row["regularity"]),
        "lead_time": service.days_of(row["lead_time"].days),
        "lead_time_span": _span(row["lead_time"]),
        # Дата строкой, а не датой Excel: в ячейке она читается одинаково
        # в любой локали, а сортировать файл по ней никто не станет.
        "first_date": row["first_moment"].strftime("%d.%m.%Y"),
        "last_date": row["last_moment"].strftime("%d.%m.%Y"),
    }


def _supply_rows(filters: service.Filters, shown: set[int]) -> list[dict]:
    """Поставки тех поставщиков, что попали на первый лист.

    Поиск учитывается и здесь: два листа одного файла обязаны быть про одно
    и то же. Оставь мы на втором все приёмки, сумма по нему не сошлась бы
    с суммой по первому — и какой из двух верен, по файлу не понять.
    """
    rows = []
    for supply in selection.supplies(
        date_from=filters.date_from, date_to=filters.date_to
    ):
        if supply.agent_id not in shown:
            continue
        order = supply.purchase_order
        # Те же три условия, что у расчёта срока: иначе файл показывал бы
        # номер и дату черновика рядом с прочерком в колонке срока.
        linked = exists(order)
        rows.append(
            {
                "date": supply.moment.strftime("%d.%m.%Y"),
                "number": supply.number,
                "supplier": supply.agent.name,
                "amount": rubles(supply.total_kopecks),
                "order": order.number if linked else "",
                "order_date": order.moment.strftime("%d.%m.%Y") if linked else "",
                "lead_time": service.days_of(lead_time.of([supply]).days),
            }
        )

    # Хронологически: лист читают как ленту поставок, а не как список
    # поставщиков — тот уже есть на первом.
    rows.sort(key=lambda row: (row["date"][6:], row["date"][3:5], row["date"][:2]))
    return rows


def _totals_row(totals: dict) -> dict:
    """Итог по строкам файла, а не по всей выборке.

    Все четыре числа — про одно множество. Возьми мы наименования из охвата,
    а сумму из итога, подвал при выгрузке с поиском читался бы как
    «2 поставщика … 212 наименований», где 212 описывают все двадцать три.
    """
    return {
        "name": "Итого · "
        + with_plural(
            totals["suppliers_count"], "поставщик", "поставщика", "поставщиков"
        ),
        "supplies": totals["supplies_count"],
        "amount": rubles(totals["amount_kopecks"]),
        "share": float(totals["amount_share"])
        if totals["amount_share"] is not None
        else None,
        "materials": totals["materials_count"],
    }
