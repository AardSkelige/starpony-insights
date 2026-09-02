"""Разбор строки «Сроков оплаты»: из чего сложился долг контрагента.

Отдельным запросом, а не вместе со строкой. У «Интернет Решений»
150 неоплаченных отгрузок, и они уехали бы в каждый ответ страницы —
включая те случаи, когда строку никто не раскрывал. У «Поставщиков»
решение обратное, и по той же причине: там слагаемые это десяток чисел,
а не полторы сотни документов.

**Товар на реализации показывается здесь же.** Долгом он не считается,
но именно он объясняет, почему у Каприоля 98 125 ₽ при 452 696 ₽
отгруженного: деньги придут отчётом комиссионера, когда товар продадут,
и два непогашенных отчёта — это и есть строка таблицы.
"""

from core.dates import local_date, today as local_today
from core.models import Counterparty, DocumentKind
from core.services.payment_deadline import consigned, debts

# Сколько документов показать поимённо. Остальные — строкой «ещё N»:
# у Озона их 150, и список на полтораста строк отвечает на вопрос,
# которого никто не задавал. Хвост сворачивается, но не выбрасывается,
# иначе слагаемые перестают сходиться с суммой строки.
DOCUMENT_LIMIT = 20


def _document(debt) -> dict:
    document = debt.document
    return {
        "number": document.number,
        "kind": document.kind,
        "kind_label": DocumentKind(document.kind).label,
        "moment": document.moment,
        "age_days": debt.age_days,

        "total_kopecks": document.total_kopecks,
        "paid_kopecks": document.paid_kopecks,
        "debt_kopecks": debt.debt_kopecks,

        "due_date": debt.due_date,
        "days_left": debt.days_left,
        "group": debt.group,
        # Формула у расчётного числа. Без отсрочки она говорит именно это —
        # «посчитать не из чего», а не молчит.
        "explanation": debt.explanation,

        "channel": (
            document.sales_channel.name
            if document.sales_channel is not None
            else ""
        ),
        # Комментарий из учёта: причина здесь и живёт. У отгрузки в нём пишут
        # про накладные расходы, у отчёта комиссионера — про период.
        "description": document.description,
    }


def of(agent_id: int) -> dict | None:
    """Долг одного контрагента по документам. `None` — долга за ним нет.

    Ни одного долга и несуществующий контрагент — разные вещи, но ответ
    на них один: показывать нечего. Различать их на экране незачем,
    а вот отдать пустой разбор вместо 404 значило бы нарисовать панель
    с нулями там, где строки не было вовсе.
    """
    agent = Counterparty.objects.filter(id=agent_id).first()
    if agent is None:
        return None

    today = local_today()
    rows = [debt for debt in debts(today=today) if debt.document.agent_id == agent_id]
    if not rows:
        return None

    # От свежих к старым: разбор читают сверху, а первым вопросом идёт
    # «что последнее ушло без оплаты».
    rows.sort(key=lambda debt: debt.document.moment, reverse=True)
    shown, rest = rows[:DOCUMENT_LIMIT], rows[DOCUMENT_LIMIT:]

    consignment = [
        debt for debt in consigned(today=today) if debt.document.agent_id == agent_id
    ]

    return {
        "agent_id": agent.id,
        "name": agent.name,
        "is_marketplace": agent.is_marketplace,
        "deferral_days": agent.deferral_days,

        "debt_kopecks": sum(debt.debt_kopecks for debt in rows),
        "documents_count": len(rows),
        "oldest_age_days": max(debt.age_days for debt in rows),

        "documents": [_document(debt) for debt in shown],
        "rest_count": len(rest),
        "rest_debt_kopecks": sum(debt.debt_kopecks for debt in rest),

        # Товар по договорам комиссии. Ноль — обычный случай: договор комиссии
        # есть у двоих из 107.
        "consignment": {
            "count": len(consignment),
            "kopecks": sum(debt.debt_kopecks for debt in consignment),
            "contracts": sorted(
                {
                    debt.document.contract.name
                    for debt in consignment
                    if debt.document.contract is not None
                }
            ),
            "first_moment": (
                min(local_date(debt.document.moment) for debt in consignment)
                if consignment
                else None
            ),
        },
    }
