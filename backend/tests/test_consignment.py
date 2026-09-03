"""Товар на реализации: отгружен, но ещё не продан.

Ошибка здесь тихая в обе стороны. Не пометим реализацию — выручка канала
читается как заработанная, хотя товар лежит у комиссионера и может
вернуться: у «Точки продаж» так 87 % её денег. Пометим лишнее — цвет
перестанет что-либо значить, и вместе с ним перестанут замечать настоящие
пометки.
"""

from datetime import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

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

pytestmark = pytest.mark.django_db


def moscow(day=1):
    return timezone.make_aware(datetime(2026, 5, day, 12))


@pytest.fixture
def run():
    return SyncRun.objects.create(kind=SyncKind.DOCUMENTS)


@pytest.fixture
def agent(run):
    return Counterparty.objects.create(
        ms_id="50000000-0000-0000-0000-000000000001",
        name="ИП Комиссионер",
        last_seen_run=run,
    )


@pytest.fixture
def make_contract(run, agent):
    counter = {"n": 0}

    def _make(kind=ContractType.COMMISSION):
        counter["n"] += 1
        return Contract.objects.create(
            ms_id=f"60000000-0000-0000-0000-{counter['n']:012d}",
            name=f"{counter['n']:05d}",
            contract_type=kind,
            agent=agent,
            last_seen_run=run,
        )

    return _make


@pytest.fixture
def make_document(run, agent):
    counter = {"n": 0}

    def _make(
        kopecks,
        kind=DocumentKind.DEMAND,
        contract=None,
        applicable=True,
        deleted=False,
    ):
        counter["n"] += 1
        return Document.objects.create(
            ms_id=f"40000000-0000-0000-0000-{counter['n']:012d}",
            kind=kind,
            number=f"{counter['n']:05d}",
            moment=moscow(counter["n"]),
            agent=agent,
            contract=contract,
            total_kopecks=kopecks,
            applicable=applicable,
            deleted_at=timezone.now() if deleted else None,
            last_seen_run=run,
        )

    return _make


class TestIsConsignment:
    """Что считается реализацией, а что продажей."""

    def test_договор_комиссии(self, make_document, make_contract):
        document = make_document(1000, contract=make_contract())
        assert consignment.is_consignment(document) is True

    def test_договор_купли_продажи(self, make_document, make_contract):
        document = make_document(1000, contract=make_contract(ContractType.SALES))
        assert consignment.is_consignment(document) is False

    def test_без_договора_это_продажа(self, make_document):
        """Умолчание — продажа, и обратное было бы опасным.

        Договора комиссии в учёте нет, значит и реализации нет. Пометь мы
        реализацией всё, у чего договор не заполнен, — а он не заполнен
        у большинства отгрузок, — цвет накрыл бы всю страницу.
        """
        assert consignment.is_consignment(make_document(1000)) is False

    def test_документа_нет_вовсе(self):
        assert consignment.is_consignment(None) is False

    def test_отчёт_комиссионера_не_реализация(self, make_document, make_contract):
        """Отчёт идёт по тому же договору, но он и есть продажа.

        Предикат один на проект: «Сроки оплаты» отсеивают им отгрузки
        из долга, «Каналы» — красят им полосу. Считай он отчёт реализацией,
        первый же вызывающий со смешанным списком посчитал бы товар дважды:
        сначала отгрузкой комиссионеру, потом его же отчётом.
        """
        document = make_document(
            1000, kind=DocumentKind.COMMISSION_REPORT, contract=make_contract()
        )
        assert consignment.is_consignment(document) is False


class TestShare:
    """Доля реализации в показанном и когда полоса перекрашивается."""

    def test_доля_считается_от_показанного(self):
        assert consignment.share_of(1000, 250).fraction == Decimal("0.25")

    def test_больше_половины_перекрашивает(self):
        """Порог — половина: это уже другой вывод, а не оговорка к прежнему.

        У «Точки продаж» 87 %, у Telegram 97 % — вывод «канал приносит
        больше всех» держится на складе комиссионера.
        """
        assert consignment.share_of(1000, 500).tone == "warning"
        assert consignment.share_of(1000, 870).tone == "warning"

    def test_меньше_половины_не_перекрашивает(self):
        """У МАХ 31 % — оговорка нужна, пересмотр вывода нет.

        Подпись доли при этом остаётся: цветом в одиночку статус
        не передаётся (`DESIGN.md` §1).
        """
        assert consignment.share_of(1000, 310).tone == "default"

    def test_реализации_нет_пометки_нет(self):
        """Пометка без повода перестаёт замечаться, а с ней и настоящие."""
        assert consignment.share_of(1000, 0).tone == "default"
        assert consignment.share_of(1000, 0).fraction == Decimal(0)

    def test_выручки_нет_доля_прочерк(self):
        """Ноль в знаменателе — не ноль процентов, а «сказать нечего»."""
        assert consignment.share_of(0, 0).fraction is None


class TestOutstanding:
    """Вся картина: отгружено → продано отчётами → осталось на реализации."""

    def test_вычитание_сходится(self, make_document, make_contract):
        contract = make_contract()
        make_document(452_696_00, contract=contract)
        make_document(171_570_00, kind=DocumentKind.COMMISSION_REPORT,
                      contract=contract)

        result = consignment.outstanding()
        assert result.shipped_kopecks == 452_696_00
        assert result.reported_kopecks == 171_570_00
        # Ровно то расхождение, что было записано долгом в `STATUS`.
        assert result.pending_kopecks == 281_126_00

    def test_отгрузка_по_купле_продаже_в_реализацию_не_идёт(
        self, make_document, make_contract
    ):
        make_document(100_000, contract=make_contract(ContractType.SALES))
        make_document(50_000, contract=make_contract())

        assert consignment.outstanding().shipped_kopecks == 50_000

    def test_черновик_и_удалённое_не_считаются(
        self, make_document, make_contract
    ):
        """Те же три условия, что у любого документа в расчёте."""
        contract = make_contract()
        make_document(10_000, contract=contract)
        make_document(99_000, contract=contract, applicable=False)
        make_document(99_000, contract=contract, deleted=True)

        assert consignment.outstanding().shipped_kopecks == 10_000

    def test_отчётов_больше_чем_отгрузок_не_даёт_минуса(
        self, make_document, make_contract
    ):
        """Отчёт может прийти за отгрузку, которой в зеркале ещё нет.

        «Минус сорок тысяч на реализации» — число, которое ничего не значит.
        """
        contract = make_contract()
        make_document(10_000, contract=contract)
        make_document(50_000, kind=DocumentKind.COMMISSION_REPORT,
                      contract=contract)

        assert consignment.outstanding().pending_kopecks == 0
