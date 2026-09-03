"""Срок оплаты: когда должны заплатить и сколько уже просрочено.

Даты оплаты в учёте нет и быть не может — она не хранится, а считается:
**дата документа плюс дни отсрочки**. Отсрочка берётся из двух мест,
и порядок между ними важен: индивидуальный срок на отгрузке точнее общего
срока контрагента, поэтому он побеждает.

**Два вида документов, а не один.** По договору комиссии товар уходит
на реализацию: `payedSum` у такой отгрузки не заполняется никогда, и долг
возникает по отчёту комиссионера. Считать такие отгрузки неоплаченными —
значит показать самый крупный долг в системе там, где долга нет вовсе.

**Отсрочка не проставлена ни у кого.** Разведка 30.08 показала: поле пусто
у всех 104 контрагентов и у всех отгрузок. Поэтому пустая отсрочка — рабочее
состояние, а не сбой: долг без оформленной отсрочки существует и обязан быть
виден, просто про него нельзя сказать «просрочен».
"""

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from django.db.models import F, QuerySet

from core.dates import local_date, today as local_today
from core.models import Document, DocumentKind
from core.services import consignment

# За сколько дней до срока считать оплату «скоро истекает». Три дня —
# как было в прежнем демоне: столько занимает банковский перевод,
# если платёж отправят сегодня.
WARN_DAYS = 3

# Виды документов, по которым возникает долг покупателя. Приёмки и заказы
# сюда не входят: это наш долг поставщику, другой раздел и другой знак.
DEBT_KINDS = (DocumentKind.DEMAND, DocumentKind.COMMISSION_REPORT)


class DebtGroup(StrEnum):
    """Во что складывается долг. Порядок — от срочного к спокойному."""

    OVERDUE = "overdue"
    SOON = "soon"
    ON_TIME = "on_time"
    UNDATED = "undated"


GROUP_LABELS = {
    DebtGroup.OVERDUE: "Просрочено",
    DebtGroup.SOON: "Скоро истекает",
    DebtGroup.ON_TIME: "В норме",
    DebtGroup.UNDATED: "Без оформленной отсрочки",
}


@dataclass(frozen=True)
class Debt:
    """Один неоплаченный документ и всё, что о его сроке известно."""

    document: Document
    deferral_days: int | None
    deferral_source: str
    due_date: date | None
    days_left: int | None
    group: DebtGroup
    # Сколько дней документ висит неоплаченным. Не срок и не просрочка:
    # факт учёта, который существует **всегда** — в отличие от срока оплаты,
    # которого без отсрочки нет вовсе. Отсрочка не проставлена ни у одного
    # из 107 контрагентов, и без возраста страница не смогла бы отделить
    # вчерашнюю отгрузку от той, что висит с апреля.
    age_days: int

    @property
    def debt_kopecks(self) -> int:
        return self.document.unpaid_kopecks

    @property
    def days_overdue(self) -> int | None:
        """Насколько просрочено. `None` — срок не наступил или неизвестен."""
        if self.days_left is None or self.days_left >= 0:
            return None
        return -self.days_left

    @property
    def explanation(self) -> str:
        """Откуда взялось число. Расчётное значение обязано объяснять себя."""
        if self.deferral_days is None:
            return (
                "Отсрочка не указана ни у контрагента, ни в документе — "
                "срок оплаты посчитать не из чего"
            )
        moment = local_date(self.document.moment).strftime("%d.%m.%Y")
        return (
            f"{moment} (дата документа) + {self.deferral_days} дн. "
            f"({self.deferral_source}) = {self.due_date.strftime('%d.%m.%Y')}"
        )


def deferral_for(document: Document) -> tuple[int | None, str]:
    """Сколько дней отсрочки у документа и откуда взялось число.

    Индивидуальный срок побеждает общий: договорённость по конкретной
    отгрузке точнее той, что записана у контрагента вообще.

    Ноль — это ответ («платят в день отгрузки»), а не отсутствие: проверка
    идёт на `is not None`, иначе нулевая отсрочка молча превратилась бы
    в «срок неизвестен».
    """
    if document.deferral_days is not None:
        return document.deferral_days, "индивидуальный срок документа"
    if document.agent.deferral_days is not None:
        return document.agent.deferral_days, "срок контрагента"
    return None, ""


def classify(days_left: int | None) -> DebtGroup:
    if days_left is None:
        return DebtGroup.UNDATED
    if days_left < 0:
        return DebtGroup.OVERDUE
    if days_left <= WARN_DAYS:
        return DebtGroup.SOON
    return DebtGroup.ON_TIME


def debt_from(document: Document, *, today: date) -> Debt:
    days, source = deferral_for(document)

    due_date = None
    days_left = None
    if days is not None:
        # Местный календарь, а не UTC: документ, проведённый между полуночью
        # и тремя ночи по Москве, иначе числится предыдущим днём, и срок
        # оплаты уезжает на сутки — тихо и ровно на один день.
        due_date = local_date(document.moment) + timedelta(days=days)
        days_left = (due_date - today).days

    return Debt(
        document=document,
        deferral_days=days,
        deferral_source=source,
        due_date=due_date,
        days_left=days_left,
        group=classify(days_left),
        # Тот же местный календарь, что и у срока: разойдись они, документ,
        # проведённый ночью, был бы на день моложе своего же срока оплаты.
        #
        # Не ниже нуля: МойСклад разрешает провести документ будущей датой,
        # и без ограничения возраст уходил бы в минус. «−3 дня» в колонке
        # читается как сбой, а полка возраста принимала такой долг за самый
        # свежий — то есть будущая отгрузка выглядела бы благополучнее
        # вчерашней.
        age_days=max((today - local_date(document.moment)).days, 0),
    )


def unpaid_documents() -> QuerySet[Document]:
    """Проведённые документы с долгом покупателя.

    Отгрузки по договору комиссии здесь остаются: отсеиваются они позже,
    в `debts`, где видно, почему именно. Фильтровать их запросом значило бы
    спрятать причину в SQL, а на вопрос «где мои 12 отгрузок комиссионеру»
    отвечать нечем.
    """
    return (
        Document.objects.alive()
        .filter(kind__in=DEBT_KINDS, applicable=True)
        # Строго меньше суммы: переплату долгом не считаем, а равенство —
        # это полностью оплаченный документ.
        .filter(paid_kopecks__lt=F("total_kopecks"))
        # Канал продаж — здесь, а не по месту: без него разбор строки
        # стоил бы запроса на каждый из 189 документов.
        .select_related("agent", "contract", "sales_channel")
        .order_by("moment")
    )


def debts(*, today: date | None = None) -> list[Debt]:
    """Все неоплаченные документы со сроками, от срочного к спокойному.

    Отгрузки по договору комиссии исключаются здесь: долг по ним живёт
    в отчёте комиссионера, и учитывать оба значило бы посчитать один
    и тот же товар дважды.
    """
    today = today or local_today()
    rows = [
        debt_from(document, today=today)
        for document in unpaid_documents()
        if not consignment.is_consignment(document)
    ]

    order = list(DebtGroup)
    # Внутри группы — по сроку: сначала то, что просрочено сильнее всего.
    return sorted(
        rows,
        key=lambda debt: (
            order.index(debt.group),
            debt.days_left if debt.days_left is not None else 0,
        ),
    )


def consigned(*, today: date | None = None) -> list[Debt]:
    """Отгрузки по договору комиссии: товар ушёл на реализацию.

    Обратная сторона `debts` — то, что она отсеивает, и по той же причине.
    Долгом это не является: `payedSum` у такой отгрузки не заполняется
    никогда, деньги приходят отчётом комиссионера, и он в долг уже включён.
    Посчитать оба значило бы посчитать один и тот же товар дважды.

    Отдельной функцией, а не флагом у `debts`: вызывающему нужно то или
    другое, и признак в сигнатуре означал бы, что где-то он выставлен
    наугад. На вопрос «где мои 452 696 ₽» отвечает эта функция.

    **Оплата эту сторону не сужает.** `unpaid_documents` здесь не годится:
    реализация — про товар, который лежит у комиссионера, а не про долг.
    Появись у комиссионной отгрузки `payedSum` — МойСклад его не заполняет,
    но и не запрещает, — она выпала бы отсюда целиком, а из вычитания
    на «Каналах» нет, и одна подпись показала бы два числа. Поэтому
    множество берётся общим запросом `consignment.shipments`.
    """
    today = today or local_today()
    return [
        debt_from(document, today=today)
        for document in consignment.shipments()
        .select_related("agent", "contract", "sales_channel")
        .order_by("moment")
    ]


def totals(rows: list[Debt]) -> dict[DebtGroup, dict]:
    """Сколько и на какую сумму в каждой группе.

    Считается по переданным строкам, а не отдельным запросом: иначе итог
    описывал бы одно множество, а таблица — другое, и дробь из них выглядела
    бы обычным процентом, тихо соврав.
    """
    result = {
        group: {"count": 0, "debt_kopecks": 0, "label": GROUP_LABELS[group]}
        for group in DebtGroup
    }
    for row in rows:
        bucket = result[row.group]
        bucket["count"] += 1
        bucket["debt_kopecks"] += row.debt_kopecks
    return result
