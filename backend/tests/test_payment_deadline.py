"""Срок оплаты: дата документа плюс дни отсрочки.

Ошибки здесь тихие все до одной. Ноль, принятый за пустоту, отодвигает срок
в бесконечность. Отгрузка по договору комиссии, посчитанная обычной, создаёт
самый крупный долг в системе из воздуха. День, взятый по UTC вместо местного
календаря, сдвигает просрочку ровно на сутки — и ни один тест на фикстурах
с полуднем этого не заметит.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from core.models import (
    Contract,
    ContractType,
    Counterparty,
    Document,
    DocumentKind,
    SyncKind,
    SyncRun,
)
from core.services import consignment
from core.services.payment_deadline import (
    DebtGroup,
    consigned,
    debt_from,
    debts,
    deferral_for,
    totals,
)

pytestmark = pytest.mark.django_db

MOSCOW = ZoneInfo("Europe/Moscow")
TODAY = date(2026, 9, 2)


@pytest.fixture
def run():
    return SyncRun.objects.create(kind=SyncKind.DOCUMENTS)


@pytest.fixture
def make_agent(run):
    counter = {"n": 0}

    def _make(name="Покупатель", deferral_days=None):
        counter["n"] += 1
        return Counterparty.objects.create(
            ms_id=f"aaaaaaaa-0000-0000-0000-{counter['n']:012d}",
            name=name,
            deferral_days=deferral_days,
            last_seen_run=run,
        )

    return _make


@pytest.fixture
def make_contract(run):
    counter = {"n": 0}

    def _make(agent, contract_type=ContractType.SALES):
        counter["n"] += 1
        return Contract.objects.create(
            ms_id=f"cccccccc-0000-0000-0000-{counter['n']:012d}",
            name=f"Д-{counter['n']}",
            contract_type=contract_type,
            agent=agent,
            last_seen_run=run,
        )

    return _make


@pytest.fixture
def make_document(run):
    counter = {"n": 0}

    def _make(
        agent,
        *,
        kind=DocumentKind.DEMAND,
        moment=datetime(2026, 8, 20, 12, 0, tzinfo=MOSCOW),
        total=100_000,
        paid=0,
        deferral_days=None,
        contract=None,
        applicable=True,
    ):
        counter["n"] += 1
        return Document.objects.create(
            ms_id=f"dddddddd-0000-0000-0000-{counter['n']:012d}",
            kind=kind,
            number=f"{counter['n']:05d}",
            moment=moment,
            agent=agent,
            total_kopecks=total,
            paid_kopecks=paid,
            deferral_days=deferral_days,
            contract=contract,
            applicable=applicable,
            last_seen_run=run,
        )

    return _make


class TestWhichDeferralWins:
    def test_document_beats_counterparty(self, make_agent, make_document):
        """Индивидуальный срок точнее общего и обязан побеждать."""
        agent = make_agent(deferral_days=30)
        document = make_document(agent, deferral_days=5)

        days, source = deferral_for(document)

        assert days == 5
        assert source == "индивидуальный срок документа"

    def test_counterparty_used_when_document_is_silent(
        self, make_agent, make_document
    ):
        agent = make_agent(deferral_days=30)
        assert deferral_for(make_document(agent)) == (30, "срок контрагента")

    def test_zero_deferral_is_an_answer_not_a_gap(self, make_agent, make_document):
        """Ноль означает «платят в день отгрузки», а не «срок неизвестен».

        Проверка на истинность вместо `is not None` отправила бы такой
        документ в группу «без оформленной отсрочки», то есть спрятала
        бы просрочку у того, кто обязан платить сразу.
        """
        agent = make_agent(deferral_days=0)
        document = make_document(agent)

        assert deferral_for(document) == (0, "срок контрагента")

        debt = debt_from(document, today=TODAY)
        assert debt.due_date == date(2026, 8, 20)
        assert debt.group == DebtGroup.OVERDUE

    def test_no_deferral_anywhere_is_undated(self, make_agent, make_document):
        """Отсрочки нет ни у кого — это рабочее состояние аккаунта.

        Поле пусто у всех 104 контрагентов. Долг существует и обязан быть
        виден, но сказать «просрочен» про него нельзя.
        """
        debt = debt_from(make_document(make_agent()), today=TODAY)

        assert debt.deferral_days is None
        assert debt.due_date is None
        assert debt.days_left is None
        assert debt.group == DebtGroup.UNDATED
        assert debt.days_overdue is None


class TestGrouping:
    @pytest.mark.parametrize(
        "deferral, expected",
        [
            (5, DebtGroup.OVERDUE),   # срок 25.08, сегодня 02.09 — восемь дней долой
            (12, DebtGroup.OVERDUE),  # срок 01.09 — вчера
            (13, DebtGroup.SOON),     # срок 02.09 — ровно сегодня
            (15, DebtGroup.SOON),     # срок 04.09 — два дня
            (16, DebtGroup.SOON),     # срок 05.09 — три дня, граница включительно
            (17, DebtGroup.ON_TIME),  # срок 06.09 — четыре дня, уже спокойно
            (60, DebtGroup.ON_TIME),
        ],
    )
    def test_groups_by_days_left(
        self, make_agent, make_document, deferral, expected
    ):
        agent = make_agent(deferral_days=deferral)
        debt = debt_from(make_document(agent), today=TODAY)
        assert debt.group == expected

    def test_days_overdue_counts_from_the_due_date(self, make_agent, make_document):
        agent = make_agent(deferral_days=5)
        debt = debt_from(make_document(agent), today=TODAY)

        assert debt.due_date == date(2026, 8, 25)
        assert debt.days_overdue == 8


class TestLocalCalendar:
    def test_night_document_keeps_its_moscow_day(self, make_agent, make_document):
        """Документ, проведённый в 01:00 по Москве, — это сегодняшний документ.

        `moment.date()` у значения **из базы** даёт UTC-дату и отнёс бы его
        к предыдущим суткам. Просрочка вышла бы на день больше, чем есть, —
        тихо и всегда в одну сторону.

        Документ обязательно перечитывается из базы. Объект, только что
        созданный в памяти, помнит переданный пояс, и `.date()` у него
        отвечает по-московски сам собой — на таком тест проходит и при
        сломанном коде. Этот тест ровно так и был написан сначала: подмена
        `local_date` на `.date()` его не роняла.
        """
        agent = make_agent(deferral_days=10)
        created = make_document(
            agent, moment=datetime(2026, 8, 20, 1, 0, tzinfo=MOSCOW)
        )
        night = Document.objects.get(pk=created.pk)

        debt = debt_from(night, today=TODAY)

        assert debt.due_date == date(2026, 8, 30), (
            "день документа взят по UTC, а не по местному календарю"
        )


class TestCommission:
    def test_commission_shipment_is_not_a_debt(
        self, make_agent, make_contract, make_document
    ):
        """Товар по комиссии ушёл на реализацию — долга по отгрузке нет.

        `payedSum` у таких отгрузок не заполняется никогда, и посчитать
        их неоплаченными значит создать самый крупный долг в системе
        из воздуха, притом растущий с каждой новой отгрузкой.
        """
        agent = make_agent(deferral_days=10)
        commission = make_contract(agent, ContractType.COMMISSION)
        make_document(agent, contract=commission, total=500_000, paid=0)

        assert debts(today=TODAY) == []

    def test_commission_report_is_a_debt(
        self, make_agent, make_contract, make_document
    ):
        """А вот отчёт комиссионера — долг, и именно он.

        Он тоже идёт по договору комиссии, и отсеивать его по договору
        значило бы потерять единственный документ, где долг настоящий.
        """
        agent = make_agent(deferral_days=10)
        commission = make_contract(agent, ContractType.COMMISSION)
        make_document(
            agent,
            kind=DocumentKind.COMMISSION_REPORT,
            contract=commission,
            total=300_000,
            paid=100_000,
        )

        rows = debts(today=TODAY)

        assert len(rows) == 1
        assert rows[0].debt_kopecks == 200_000

    def test_sales_contract_shipment_stays_a_debt(
        self, make_agent, make_contract, make_document
    ):
        agent = make_agent(deferral_days=10)
        sales = make_contract(agent, ContractType.SALES)
        make_document(agent, contract=sales, total=100_000, paid=0)

        assert len(debts(today=TODAY)) == 1


class TestWhatIsExcluded:
    def test_paid_documents_are_out(self, make_agent, make_document):
        agent = make_agent(deferral_days=10)
        make_document(agent, total=100_000, paid=100_000)
        assert debts(today=TODAY) == []

    def test_partially_paid_document_shows_the_remainder(
        self, make_agent, make_document
    ):
        agent = make_agent(deferral_days=10)
        make_document(agent, total=100_000, paid=30_000)

        assert debts(today=TODAY)[0].debt_kopecks == 70_000

    def test_unapplicable_document_is_out(self, make_agent, make_document):
        """Непроведённый документ обязательством не стал."""
        agent = make_agent(deferral_days=10)
        make_document(agent, applicable=False)
        assert debts(today=TODAY) == []

    def test_supplies_are_out(self, make_agent, make_document):
        """Приёмка — наш долг поставщику, другой раздел и другой знак."""
        agent = make_agent(deferral_days=10)
        make_document(agent, kind=DocumentKind.SUPPLY, total=100_000, paid=0)
        assert debts(today=TODAY) == []

    def test_deleted_document_is_out(self, make_agent, make_document):
        from django.utils import timezone

        agent = make_agent(deferral_days=10)
        document = make_document(agent)
        document.deleted_at = timezone.now()
        document.save(update_fields=["deleted_at"])

        assert debts(today=TODAY) == []


class TestOrderAndTotals:
    def test_most_urgent_comes_first(self, make_agent, make_document):
        calm = make_agent("Спокойный", deferral_days=60)
        late = make_agent("Просрочивший", deferral_days=1)
        unknown = make_agent("Без отсрочки")

        make_document(calm)
        make_document(late)
        make_document(unknown)

        groups = [row.group for row in debts(today=TODAY)]

        assert groups == [DebtGroup.OVERDUE, DebtGroup.ON_TIME, DebtGroup.UNDATED]

    def test_totals_match_the_rows(self, make_agent, make_document):
        """Итог обязан сходиться со сложением строк — того же множества.

        Отдельный запрос для итога описывал бы другое множество, и дробь
        из них выглядела бы обычным процентом, тихо соврав.
        """
        late = make_agent("Просрочивший", deferral_days=1)
        make_document(late, total=100_000, paid=0)
        make_document(late, total=50_000, paid=20_000)

        rows = debts(today=TODAY)
        summary = totals(rows)

        assert summary[DebtGroup.OVERDUE]["count"] == 2
        assert summary[DebtGroup.OVERDUE]["debt_kopecks"] == 130_000
        assert sum(g["debt_kopecks"] for g in summary.values()) == sum(
            row.debt_kopecks for row in rows
        )


class TestExplanation:
    def test_explains_where_the_date_came_from(self, make_agent, make_document):
        """Расчётное число обязано объяснять себя (`CLAUDE.md` §4)."""
        agent = make_agent(deferral_days=14)
        debt = debt_from(make_document(agent), today=TODAY)

        assert debt.explanation == (
            "20.08.2026 (дата документа) + 14 дн. (срок контрагента) = 03.09.2026"
        )

    def test_explains_the_gap_when_there_is_no_deferral(
        self, make_agent, make_document
    ):
        debt = debt_from(make_document(make_agent()), today=TODAY)
        assert "не указана" in debt.explanation


class TestAge:
    """Возраст долга: сколько дней документ висит неоплаченным.

    Не срок и не просрочка. Срок без отсрочки посчитать не из чего,
    а возраст есть всегда — на нём и держится страница, пока поля в учёте
    не заполнены.
    """

    def test_age_counts_calendar_days(self, make_agent, make_document):
        debt = debt_from(make_document(make_agent()), today=TODAY)
        assert debt.age_days == 13

    def test_age_is_local_not_utc(self, make_agent, make_document):
        """Документ, проведённый ночью по Москве, не на день старше себя.

        `moment.date()` у значения **из базы** даёт UTC-дату: отгрузка
        в 01:00 по Москве числилась бы предыдущим днём, и возраст вырос бы
        ровно на сутки — тихо.

        Считается через `debts`, а не через созданный объект: у только что
        созданной модели в памяти лежит момент с московским поясом, и `.date()`
        у него отвечает правильно **случайно**. Проверка на покраснение это
        и вскрыла — тест проходил, не проверяя ничего.
        """
        make_document(
            make_agent(), moment=datetime(2026, 8, 20, 1, 0, tzinfo=MOSCOW)
        )

        assert [row.age_days for row in debts(today=TODAY)] == [13]

    def test_future_document_is_not_younger_than_today(
        self, make_agent, make_document
    ):
        """Документ будущей датой не бывает моложе нуля дней.

        МойСклад разрешает провести отгрузку завтрашним числом. Без нижней
        границы возраст ушёл бы в минус: «−3 дня» в колонке читается как сбой,
        а полка возраста приняла бы такой долг за самый свежий — то есть
        будущая отгрузка выглядела бы благополучнее вчерашней.
        """
        future = make_document(
            make_agent(), moment=datetime(2026, 9, 5, 12, 0, tzinfo=MOSCOW)
        )

        assert debt_from(future, today=TODAY).age_days == 0

    def test_age_exists_without_a_deferral(self, make_agent, make_document):
        """Срока нет, возраст есть — в этом весь смысл."""
        debt = debt_from(make_document(make_agent()), today=TODAY)

        assert debt.due_date is None
        assert debt.group == DebtGroup.UNDATED
        assert debt.age_days == 13


class TestConsigned:
    """Товар, отгруженный по договору комиссии, — обратная сторона `debts`."""

    def test_returns_what_debts_leaves_out(
        self, make_agent, make_contract, make_document
    ):
        """Одна отгрузка не может быть и долгом, и товаром на реализации.

        Посчитать оба значило бы посчитать один и тот же товар дважды:
        деньги по нему придут отчётом комиссионера, а он уже в долге.
        """
        agent = make_agent("КРМОО «Каприоль»")
        contract = make_contract(agent, contract_type=ContractType.COMMISSION)
        make_document(agent, contract=contract, total=400_000)
        make_document(
            agent,
            kind=DocumentKind.COMMISSION_REPORT,
            contract=contract,
            total=80_000,
        )

        assert [row.debt_kopecks for row in debts(today=TODAY)] == [80_000]
        assert [row.debt_kopecks for row in consigned(today=TODAY)] == [400_000]

    def test_commission_report_is_never_consignment(
        self, make_agent, make_contract, make_document
    ):
        """Отчёт идёт по тому же договору комиссии, но он и есть долг."""
        agent = make_agent()
        contract = make_contract(agent, contract_type=ContractType.COMMISSION)
        make_document(
            agent, kind=DocumentKind.COMMISSION_REPORT, contract=contract
        )

        assert consigned(today=TODAY) == []
        assert len(debts(today=TODAY)) == 1

    def test_sales_contract_is_not_consignment(
        self, make_agent, make_contract, make_document
    ):
        agent = make_agent()
        make_document(
            agent, contract=make_contract(agent, contract_type=ContractType.SALES)
        )

        assert consigned(today=TODAY) == []

    def test_оплаченная_отгрузка_с_реализации_не_пропадает(
        self, make_agent, make_contract, make_document
    ):
        """«Отгружено на реализацию» — про товар, а не про оплату.

        Здесь и на «Каналах» одна подпись и обязано быть одно число.
        Сузь эту сторону оплатой — и страницы разойдутся молча в тот день,
        когда у комиссионной отгрузки впервые появится `payedSum`:
        МойСклад его не заполняет, но запретить это ничто не мешает.
        """
        agent = make_agent()
        contract = make_contract(agent, contract_type=ContractType.COMMISSION)
        make_document(agent, contract=contract, total=400_000, paid=400_000)
        make_document(agent, contract=contract, total=52_696, paid=20_000)

        shipped = sum(row.document.total_kopecks for row in consigned(today=TODAY))
        assert shipped == 452_696
        assert shipped == consignment.outstanding().shipped_kopecks
