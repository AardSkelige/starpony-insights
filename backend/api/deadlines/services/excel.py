"""Выгрузка «Сроки оплаты» в XLSX.

Два листа. На первом — контрагенты со сводными числами, как на экране.
На втором — каждый неоплаченный документ отдельной строкой: дата, номер,
сумма, возраст, срок оплаты и комментарий из учёта.

Второй лист не украшение. Сводное число на первом отвечает «сколько
и как давно», а вопросы этого раздела — «за что именно» и «с чего начать
разговор» — требуют самих документов: у Каприоля 98 125 ₽ сложились
из недоплаченного отчёта и неоплаченного целиком, и на первом листе
этой разницы не увидеть.

**Расчёты через площадку идут отдельной колонкой, а не отдельным файлом.**
Долгом они не являются, но и терять их нельзя: товар ушёл, деньги
не пришли. Колонка отвечает на «почему эта строка не в общем итоге».
"""

from io import BytesIO

from api.common import workbook
from api.common.workbook import MONEY, SHARE
from api.deadlines.services import deadlines as service
from core.dates import local_date, today as local_today
from core.money import rubles
from core.models import DocumentKind
from core.services.payment_deadline import consigned, debts
from core.text import with_plural

# Порядок и подписи совпадают с экраном: файл, где колонки идут иначе,
# заставляет сверять их глазами.
COLUMNS: tuple[tuple[str, int, str], ...] = (
    ("Контрагент", 40, "name"),
    ("Расчёты", 18, "settlement"),
    ("Долг, ₽", 16, "debt"),
    ("Доля в долге", 14, "share"),
    ("Документов", 12, "documents"),
    ("Старейший долг, дней", 20, "oldest"),
    ("Свежайший долг, дней", 20, "newest"),
    ("Отсрочка, дней", 14, "deferral"),
    ("Каналы", 30, "channels"),
)

DOCUMENT_COLUMNS: tuple[tuple[str, int, str], ...] = (
    ("Дата", 12, "date"),
    ("Документ", 12, "number"),
    ("Вид", 22, "kind"),
    ("Контрагент", 40, "agent"),
    ("Сумма, ₽", 16, "total"),
    ("Оплачено, ₽", 16, "paid"),
    ("Долг, ₽", 16, "debt"),
    ("Возраст, дней", 14, "age"),
    ("Срок оплаты", 14, "due"),
    ("Канал", 18, "channel"),
    ("Комментарий", 50, "description"),
)

FORMATS = {
    "debt": MONEY,
    "share": SHARE,
    "total": MONEY,
    "paid": MONEY,
}

DIRECT = "напрямую"
VIA_MARKETPLACE = "через площадку"


def build(filters: service.Filters) -> BytesIO:
    """Собрать книгу по всей выборке фильтров.

    Берёт `prepared`, а не `page`: та режет выборку на страницы, и файл
    молча терял бы всё после десятой строки — при том, что строка итога
    считается по всем.

    Площадки идут следом за дебиторкой, а не в отдельном файле: в строку
    итога они не входят, и колонка «Расчёты» говорит, почему.
    """
    whole = service.prepared(filters)
    rows = whole["rows"] + whole["marketplaces"]
    shown = {row["agent_id"] for row in rows}

    return workbook.build(
        workbook.Sheet(
            "Контрагенты",
            COLUMNS,
            [_cells(row) for row in rows],
            FORMATS,
            _totals_row(whole["totals"]),
        ),
        workbook.Sheet(
            "Документы",
            DOCUMENT_COLUMNS,
            _document_rows(shown),
            FORMATS,
        ),
    )


def _cells(row: dict) -> dict:
    return {
        "name": row["name"],
        "settlement": VIA_MARKETPLACE if row["is_marketplace"] else DIRECT,
        "debt": rubles(row["debt_kopecks"]),
        # У площадок доля не выводится вовсе. На экране две группы стоят
        # порознь и каждая считает долю внутри себя; в файле они попадают
        # в одну колонку — и доли сложились бы в двести процентов, причём
        # ровно в том месте, где это невозможно заметить. Пустая ячейка
        # честнее: доля площадки в дебиторке не определена, потому что
        # площадка в дебиторку не входит.
        "share": _share_of(row),
        "documents": row["documents_count"],
        "oldest": row["oldest_age_days"],
        "newest": row["newest_age_days"],
        # Прочерк, а не пустая ячейка: пустая читается как «забыли выгрузить»,
        # а отсутствие отсрочки — это факт учёта и причина, по которой
        # в колонке срока напротив тоже прочерк.
        "deferral": row["deferral_days"] if row["deferral_days"] is not None else "—",
        "channels": ", ".join(row["channels"]),
    }


def _share_of(row: dict) -> float | None:
    """Доля строки в дебиторке. У площадки её нет — она вне этого множества."""
    if row["is_marketplace"] or row["debt_share"] is None:
        return None
    return float(row["debt_share"])


def _document_rows(shown: set[int]) -> list[dict]:
    """Неоплаченные документы тех контрагентов, что попали на первый лист.

    Поиск учитывается и здесь: два листа одного файла обязаны быть про одно
    и то же. Оставь мы на втором все документы, сумма по нему не сошлась бы
    с суммой по первому — и какой из двух верен, по файлу не понять.

    Товар по договорам комиссии попадает сюда же, отдельным видом документа.
    В долг он не входит и в строку итога тоже, но вопрос «а где остальные
    отгрузки Каприоля» задаётся первым, и файл обязан на него отвечать.
    """
    today = local_today()
    rows = [
        _document_cells(debt)
        for debt in debts(today=today) + consigned(today=today)
        if debt.document.agent_id in shown
    ]
    # Хронологически, от свежего к старому: лист читают как ленту, а список
    # контрагентов уже есть на первом.
    rows.sort(key=lambda row: row["sort_key"], reverse=True)
    for row in rows:
        del row["sort_key"]
    return rows


def _document_cells(debt) -> dict:
    document = debt.document
    return {
        "sort_key": document.moment,
        "date": local_date(document.moment).strftime("%d.%m.%Y"),
        "number": document.number,
        "kind": DocumentKind(document.kind).label,
        "agent": document.agent.name,
        "total": rubles(document.total_kopecks),
        "paid": rubles(document.paid_kopecks),
        "debt": rubles(debt.debt_kopecks),
        "age": debt.age_days,
        # Срок оплаты появляется только у документа с отсрочкой. Прочерк —
        # это ответ «посчитать не из чего», и он честнее пустой ячейки.
        "due": debt.due_date.strftime("%d.%m.%Y") if debt.due_date else "—",
        "channel": (
            document.sales_channel.name if document.sales_channel is not None else ""
        ),
        "description": document.description,
    }


def _totals_row(totals: dict) -> dict:
    """Итог по дебиторке, а не по всем строкам файла.

    Площадки в него не входят намеренно — как и на экране: их выплата
    приходит реестром и в учёт не заводится, и сложение дало бы число,
    которое никому не должны.
    """
    return {
        "name": "Итого · "
        + with_plural(
            totals["counterparties_count"], "контрагент", "контрагента", "контрагентов"
        ),
        "settlement": DIRECT,
        "debt": rubles(totals["debt_kopecks"]),
        "share": float(totals["debt_share"])
        if totals["debt_share"] is not None
        else None,
        "documents": totals["documents_count"],
        "oldest": totals["oldest_age_days"],
    }
