"""Страница «Сроки оплаты»: кому звонить и где застряли деньги.

Строка — контрагент, слагаемые строки — его неоплаченные документы. Так,
а не документом на строку: у «Интернет Решений» 150 отгрузок, и список
из них отвечает на вопрос «какие бумаги висят», которого никто не задаёт.
Спрашивают «кто должен и давно ли», и это ровно одна строка на контрагента.

**Три суммы, а не одна.** Долг покупателя, расчёты через площадку и товар
на реализации приходят из одного места учёта — «отгружено, не оплачено», —
но означают разное:

| | На 02.09.2026 | Что это |
|---|---|---|
| Дебиторка | 123 044 ₽ | нам должны, можно звонить |
| Площадки | 314 470 ₽ | выплата придёт реестром, в учёт не заводится |
| Реализация | 452 696 ₽ | товар у комиссионера, долг придёт отчётом |

Сложи их — получится 890 210 ₽ «долга», из которого настоящего меньше
седьмой части. Ровно поэтому раздел не может быть списком неоплаченных
отгрузок: число было бы честно посчитано и полностью бесполезно.

**Признак площадки берётся из учёта** — группа контрагента «маркетплейсы»,
которую человек уже ведёт руками. Не флаг в нашей админке и не догадка
по имени: второй список тех же контрагентов разошёлся бы с первым.
"""

from collections import defaultdict

from api.common.selection import page_bounds
from api.deadlines.services import aging, selection, summary
from core.dates import today as local_today
from core.models import Counterparty
from core.money import share
from core.services.payment_deadline import GROUP_LABELS, DebtGroup, consigned, debts

Filters = selection.Filters
ORDERING = selection.ORDERING
DEFAULT_ORDERING = selection.DEFAULT_ORDERING


def row_of(debts_of_agent: list) -> dict:
    """Строка таблицы вместе с составляющими своих чисел."""
    agent = debts_of_agent[0].document.agent
    ages = [debt.age_days for debt in debts_of_agent]

    return {
        "agent_id": agent.id,
        "name": agent.name,
        # Расчёты идут через площадку: выплата приходит реестром раз в цикл
        # и в учёт не заводится. Строка остаётся, но живёт отдельно от долга.
        "is_marketplace": agent.is_marketplace,
        # Отсрочка контрагента. `null` у всех 107 на 02.09 — и это состояние
        # учёта, а не пробел расчёта: колонка объясняет отсутствие срока.
        "deferral_days": agent.deferral_days,

        "debt_kopecks": sum(debt.debt_kopecks for debt in debts_of_agent),
        "documents_count": len(debts_of_agent),

        # Возраст старейшего непогашенного документа — то, по чему решают,
        # звонить сегодня или подождать. Медиана здесь не годится: платить
        # заставляет самый застарелый долг, а не типичный.
        "oldest_age_days": max(ages),
        "newest_age_days": min(ages),
        # Распределение долга самого контрагента по полкам возраста:
        # 150 отгрузок Озона одного месяца и 22 отгрузки Яндекса,
        # растянутые на три, — это разные новости при одинаковой сумме.
        "aging": aging.distribution(debts_of_agent),

        # Чем именно возник долг. Объясняет Каприоль: у него две строки —
        # отчёты комиссионера, а не отгрузки, и без этого «2 документа
        # на 98 125 ₽» рядом с 16 отгрузками в разборе выглядит ошибкой.
        "kinds": _kinds(debts_of_agent),
        # Каналы, по которым ушёл неоплаченный товар. Из них видно,
        # что долг Яндекс.Маркета пришёл не только с его канала.
        "channels": _channels(debts_of_agent),
        # Группы срока. Сегодня все до одной в «без оформленной отсрочки»;
        # включатся сами, как только в учёте появятся дни отсрочки.
        "groups": _groups(debts_of_agent),
    }


def _kinds(debts_of_agent: list) -> dict:
    counts: dict[str, int] = defaultdict(int)
    for debt in debts_of_agent:
        counts[debt.document.kind] += 1
    return dict(counts)


def _channels(debts_of_agent: list) -> list[str]:
    return sorted(
        {
            debt.document.sales_channel.name
            for debt in debts_of_agent
            if debt.document.sales_channel is not None
        }
    )


def _groups(debts_of_agent: list) -> list[dict]:
    """Сколько документов и денег в каждой группе срока.

    Пустые группы остаются: «просрочено — ноль» это ответ, а исчезнувшая
    строка читается как «мы это не считали».
    """
    counts = {group: {"count": 0, "debt_kopecks": 0} for group in DebtGroup}
    for debt in debts_of_agent:
        entry = counts[debt.group]
        entry["count"] += 1
        entry["debt_kopecks"] += debt.debt_kopecks
    return [
        {
            "key": group,
            "label": GROUP_LABELS[group],
            "count": counts[group]["count"],
            "debt_kopecks": counts[group]["debt_kopecks"],
        }
        for group in DebtGroup
    ]


def _matches(row: dict, term: str) -> bool:
    """Поиск по названию контрагента. Больше искать здесь не по чему."""
    return term.strip().casefold() in row["name"].casefold()


# По чему сравнивают строки для каждого разрешённого ключа сортировки.
_SORT_KEYS = {
    "debt": lambda row: row["debt_kopecks"],
    "name": lambda row: row["name"].casefold(),
    "documents": lambda row: row["documents_count"],
    "oldest": lambda row: row["oldest_age_days"],
}


def _sorted(rows: list[dict], ordering: str) -> list[dict]:
    """Порядок показа. Ничьи разрешает идентификатор контрагента.

    Без него два контрагента с равным долгом шли бы в порядке, который
    не обязан повторяться между запросами, — и строка прыгала бы
    при перелистывании.
    """
    if ordering not in ORDERING:
        ordering = DEFAULT_ORDERING
    key = _SORT_KEYS[ordering.lstrip("-")]
    return sorted(
        rows,
        key=lambda row: (key(row), row["agent_id"]),
        reverse=ordering.startswith("-"),
    )


def prepared(filters: Filters) -> dict:
    """Всё, что знает страница, без нарезки на страницы.

    Отдельно от `page`, потому что выгрузке нужны все строки: долги читаются
    двумя запросами, и делать их дважды — ради экрана и ради файла — незачем.
    """
    today = local_today()

    by_agent: dict[int, list] = defaultdict(list)
    for debt in debts(today=today):
        by_agent[debt.document.agent_id].append(debt)

    everything = [row_of(items) for items in by_agent.values()]

    # Две картины, а не одна: долг покупателя и расчёты через площадку.
    # Разделение здесь, а не на фронте: итог и доли обязаны считаться
    # от того же множества, что показано, — иначе доля дебиторки посчиталась
    # бы от суммы, в которую входят площадки, и молча стала бы вчетверо меньше.
    receivable = [row for row in everything if not row["is_marketplace"]]
    marketplace = [row for row in everything if row["is_marketplace"]]

    receivable_kopecks = sum(row["debt_kopecks"] for row in receivable)
    for row in receivable:
        row["debt_share"] = share(row["debt_kopecks"], receivable_kopecks)
    # Доля площадки — внутри площадок: положи её рядом с дебиторкой,
    # и сумма долей перевалила бы за сто процентов. Знаменатель считается
    # один раз, а не на каждой строке: у соседней ветки он вынесен, и две
    # соседние строки, написанные по-разному, читаются как разные по смыслу.
    marketplace_kopecks = sum(row["debt_kopecks"] for row in marketplace)
    for row in marketplace:
        row["debt_share"] = share(row["debt_kopecks"], marketplace_kopecks)

    rows = receivable
    found_marketplace = marketplace
    if filters.search:
        rows = [row for row in receivable if _matches(row, filters.search)]
        found_marketplace = [
            row for row in marketplace if _matches(row, filters.search)
        ]

    # График старения — про то же, что таблица под ним. Соседние числа
    # обязаны быть об одном множестве: покажи он всю дебиторку при поиске
    # «пмт», столбики описывали бы не найденное, ничем этого не выдав.
    shown_debts = [
        debt
        for agent_id, items in by_agent.items()
        for debt in items
        if agent_id in {row["agent_id"] for row in rows}
    ]

    return {
        "rows": _sorted(rows, filters.ordering),
        "marketplaces": _sorted(found_marketplace, DEFAULT_ORDERING),
        "aging": aging.distribution(shown_debts),
        "totals": summary.table_totals(rows, receivable_kopecks),
        "coverage": summary.coverage(
            receivable,
            marketplace,
            _consignment(today),
            deferral_filled=Counterparty.objects.alive()
            .exclude(deferral_days=None)
            .count(),
            counterparties_total=Counterparty.objects.alive().count(),
        ),
    }


def _consignment(today) -> dict:
    """Товар, отгруженный по договорам комиссии. Не долг — не считаем долгом.

    Считается по всем комиссионерам, а не по строкам таблицы, и число
    контрагентов идёт рядом именно поэтому. Комиссионер, у которого все
    отчёты оплачены, строки не имеет вовсе — а товар у него лежит:
    у «ИП Полковниковой» это 4 отгрузки при пустом долге. Без счётчика
    сумма в сводке была бы больше суммы, которую можно найти в разборе
    строк, и объяснить разницу было бы нечем.
    """
    rows = consigned(today=today)
    return {
        "count": len(rows),
        # Сумма документов, а не остаток к оплате: подпись «Товар
        # на реализации» — про отгруженное, и это то же число, которое
        # «Каналы продаж» вычитают в своей сводке.
        "debt_kopecks": sum(debt.document.total_kopecks for debt in rows),
        "counterparties_count": len({debt.document.agent_id for debt in rows}),
    }


def page(filters: Filters) -> dict:
    """Всё, что нужно странице."""
    whole = prepared(filters)
    rows = whole["rows"]
    start, end = page_bounds(filters.page, filters.page_size)

    return {
        "count": len(rows),
        "aging": whole["aging"],
        "totals": whole["totals"],
        "coverage": whole["coverage"],
        # Площадок две, и разбивать их на страницы нечего: блок под таблицей
        # показывает их целиком.
        "marketplaces": whole["marketplaces"],
        "results": rows[start:end],
    }
