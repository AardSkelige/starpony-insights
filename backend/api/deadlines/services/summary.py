"""Итоги страницы «Сроки оплаты»: что в таблице и что во всей картине.

Два набора чисел, а не один, — правило, купленное на соседних страницах.
Итог под таблицей считается по показанным строкам и обязан сходиться
со сложением колонки; сводка описывает весь незакрытый долг, и поиск
её не трогает.

Здесь у этого правила есть третья доля. Кроме дебиторки и найденного
существует то, что долгом не является вовсе, но из того же учёта:
расчёты через площадку и товар, отгруженный по договору комиссии.
Сложи их в одно число — и «нам должны 890 210 ₽» будет неправдой
в семи случаях из десяти.
"""

from core.money import share
from core.services.payment_deadline import DebtGroup


def table_totals(rows: list[dict], receivable_kopecks: int) -> dict:
    """Итог по строкам таблицы — с учётом поиска.

    Доля считается от всей дебиторки, как и у отдельных строк: без поиска
    это ровно сто процентов, с поиском — сколько найденное занимает в долге.
    Написать «100 %» жёстко значило бы поставить над колонкой с шестью
    процентами итог «сто».
    """
    debt = sum(row["debt_kopecks"] for row in rows)
    return {
        "counterparties_count": len(rows),
        "documents_count": sum(row["documents_count"] for row in rows),
        "debt_kopecks": debt,
        "debt_share": share(debt, receivable_kopecks),
        # Старейший долг среди показанных строк, а не среди всех: подвал
        # обязан описывать таблицу. Ноль строк — величины не существует.
        "oldest_age_days": max((row["oldest_age_days"] for row in rows), default=None),
    }


def coverage(
    receivable: list[dict],
    marketplace: list[dict],
    consignment: dict,
    deferral_filled: int,
    counterparties_total: int,
) -> dict:
    """Вся картина расчётов с покупателями — поиск её не трогает.

    Три суммы рядом отвечают на вопрос, который иначе задают вслух каждый
    раз: почему «не оплачено» в учёте и «нам должны» — разные числа.
    """
    receivable_kopecks = sum(row["debt_kopecks"] for row in receivable)
    marketplace_kopecks = sum(row["debt_kopecks"] for row in marketplace)

    return {
        "counterparties_count": len(receivable),
        "documents_count": sum(row["documents_count"] for row in receivable),
        "debt_kopecks": receivable_kopecks,

        # Площадки: отгружено и не закрыто, но выплата приходит реестром
        # и в учёт не заводится вовсе. Долгом это назвать нельзя, спрятать —
        # тем более: товар ушёл, деньги не пришли.
        "marketplaces_count": len(marketplace),
        "marketplace_documents_count": sum(
            row["documents_count"] for row in marketplace
        ),
        "marketplace_kopecks": marketplace_kopecks,

        # Товар по договорам комиссии: ушёл на реализацию, `payedSum`
        # у таких отгрузок не заполняется никогда, и долг по ним возникает
        # отчётом комиссионера — он и попадает в дебиторку.
        "consignment_count": consignment["count"],
        "consignment_kopecks": consignment["debt_kopecks"],
        # По скольким комиссионерам. Не всегда совпадает с числом строк
        # в таблице: у комиссионера с оплаченными отчётами долга нет,
        # а товар на реализации есть.
        "consignment_counterparties_count": consignment["counterparties_count"],

        # Сколько контрагентов умеют показать срок оплаты. Объясняет, почему
        # на экране нет ни «просрочено», ни «в норме»: без отсрочки срока
        # не существует, и это состояние учёта, а не пустой расчёт.
        "with_deferral_count": deferral_filled,
        "counterparties_total": counterparties_total,

        # Просроченное и подходящее к сроку — по всей дебиторке. Сегодня оба
        # нули, потому что отсрочки нет ни у кого; появится она — появятся
        # и числа, без единой правки кода. Отдаются отдельно от возраста
        # намеренно: возраст говорит «висит давно», просрочка — «нарушен
        # договор», и это разные утверждения.
        **_by_group(receivable),
    }


def _by_group(rows: list[dict]) -> dict:
    """Сколько денег и документов в срочных группах, по всей дебиторке.

    Складывается из тех же `groups`, что показывает строка: второй запрос
    описывал бы другое множество, и итог разошёлся бы со сложением колонки.
    """
    totals = {group: {"count": 0, "debt_kopecks": 0} for group in DebtGroup}
    for row in rows:
        for entry in row["groups"]:
            bucket = totals[DebtGroup(entry["key"])]
            bucket["count"] += entry["count"]
            bucket["debt_kopecks"] += entry["debt_kopecks"]

    return {
        "overdue_count": totals[DebtGroup.OVERDUE]["count"],
        "overdue_kopecks": totals[DebtGroup.OVERDUE]["debt_kopecks"],
        "soon_count": totals[DebtGroup.SOON]["count"],
        "soon_kopecks": totals[DebtGroup.SOON]["debt_kopecks"],
    }
