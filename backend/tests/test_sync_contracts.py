"""Договоры и доп. поля отсрочки — данные, без которых «Сроки оплаты» врут.

Все три ошибки здесь тихие: договор, не доехавший до зеркала, превращает
реализацию в мнимый долг; `expand` при большом лимите молча игнорируется,
и отсрочка не приезжает вовсе; ноль в доп. поле, принятый за пустоту,
отодвигает срок оплаты в бесконечность.
"""

from datetime import datetime
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
from moysklad.parsing import attribute_int
from moysklad.sync.documents import sync_commission_reports, sync_demands
from moysklad.sync.full import ENTITIES
from moysklad.sync.references import (
    sync_contracts,
    sync_counterparties,
    sync_sales_channels,
)

pytestmark = pytest.mark.django_db

BASE = "https://api.moysklad.ru/api/remap/1.2"
MOSCOW = ZoneInfo("Europe/Moscow")
AGENT_ID = "aaaaaaaa-1111-1111-1111-111111111111"
CONTRACT_ID = "cccccccc-1111-1111-1111-111111111111"


def meta(entity: str, ms_id: str) -> dict:
    return {"meta": {"href": f"{BASE}/entity/{entity}/{ms_id}", "type": entity}}


class FakeClient:
    """Отдаёт заданные строки по пути. Запоминает параметры запросов."""

    request_count = 0

    def __init__(self, rows: dict):
        self._rows = rows
        self.calls: list[tuple[str, dict | None]] = []

    def iterate(self, path, params=None):
        self.calls.append((path, params))
        yield from self._rows.get(path, [])


@pytest.fixture
def run():
    return SyncRun.objects.create(kind=SyncKind.DOCUMENTS)


@pytest.fixture
def agent(run):
    return Counterparty.objects.create(
        ms_id=AGENT_ID, name="Комиссионер", last_seen_run=run
    )


class TestAttributeParsing:
    def test_reads_value_by_name(self):
        attributes = [
            {"name": "Что-то ещё", "value": "нет"},
            {"name": "Срок отсрочки (дней)", "value": 14},
        ]
        assert attribute_int(attributes, "Срок отсрочки (дней)") == 14

    def test_zero_is_kept(self):
        """Ноль — это ответ «платят сразу», а не отсутствие значения."""
        assert attribute_int([{"name": "Срок", "value": 0}], "Срок") == 0

    @pytest.mark.parametrize(
        "attributes",
        [None, [], [{"name": "Другое", "value": 5}], [{"name": "Срок", "value": None}],
         [{"name": "Срок", "value": ""}]],
    )
    def test_missing_gives_none(self, attributes):
        assert attribute_int(attributes, "Срок") is None

    def test_garbage_does_not_crash_the_sync(self):
        """Человек вписал текст в числовое поле — пропускаем, а не роняем прогон."""
        assert attribute_int([{"name": "Срок", "value": "две недели"}], "Срок") is None

    def test_string_number_is_accepted(self):
        assert attribute_int([{"name": "Срок", "value": "30"}], "Срок") == 30


class TestCounterpartyDeferral:
    def test_deferral_is_synced(self, run):
        client = FakeClient({"/entity/counterparty": [{
            "id": AGENT_ID,
            "name": "Покупатель",
            "attributes": [{"name": "Срок отсрочки (дней)", "value": 21}],
        }]})

        sync_counterparties(client, run)

        assert Counterparty.objects.get(ms_id=AGENT_ID).deferral_days == 21

    def test_empty_deferral_is_normal(self, run):
        """Поле не заполнено ни у одного из 104 контрагентов — это не сбой."""
        client = FakeClient({"/entity/counterparty": [
            {"id": AGENT_ID, "name": "Покупатель"}
        ]})

        outcome = sync_counterparties(client, run)

        assert outcome.error == ""
        assert Counterparty.objects.get(ms_id=AGENT_ID).deferral_days is None

    def test_expand_is_not_requested(self, run):
        """`expand` для доп. полей не нужен и был бы вреден.

        При лимите больше 100 МойСклад его молча игнорирует — отсрочка
        не приехала бы вовсе, а прогон отчитался бы «получено 104».
        """
        client = FakeClient({"/entity/counterparty": []})

        sync_counterparties(client, run)

        _, params = client.calls[0]
        assert "expand" not in (params or {})


class TestContracts:
    def test_commission_type_is_recognised(self, run, agent):
        client = FakeClient({"/entity/contract": [{
            "id": CONTRACT_ID,
            "name": "К-1",
            "contractType": "Commission",
            **meta("counterparty", AGENT_ID),
            "agent": meta("counterparty", AGENT_ID),
        }]})

        sync_contracts(client, run)

        contract = Contract.objects.get(ms_id=CONTRACT_ID)
        assert contract.contract_type == ContractType.COMMISSION
        assert contract.is_commission

    def test_missing_type_means_sales(self, run, agent):
        """Купля-продажа — значение по умолчанию и может не прийти вовсе."""
        client = FakeClient({"/entity/contract": [{
            "id": CONTRACT_ID, "name": "К-1", "agent": meta("counterparty", AGENT_ID),
        }]})

        sync_contracts(client, run)

        assert Contract.objects.get(ms_id=CONTRACT_ID).contract_type == (
            ContractType.SALES
        )

    def test_contract_without_agent_is_counted_not_swallowed(self, run):
        """Договор без контрагента в зеркале — потеря, и она обязана считаться.

        Молча потерянный договор комиссии превращает реализацию
        в мнимый долг, притом самый крупный в системе.
        """
        client = FakeClient({"/entity/contract": [{
            "id": CONTRACT_ID,
            "name": "К-1",
            "contractType": "Commission",
            "agent": meta("counterparty", "unknown-agent-id"),
        }]})

        outcome = sync_contracts(client, run)

        assert Contract.objects.count() == 0
        assert outcome.extra["skipped"] == 1

    def test_contracts_are_synced_before_documents(self):
        """Порядок обязателен: документ ссылается на договор.

        В обратном порядке связь не установилась бы ни у одного документа —
        молча, ровно один прогон, и весь товар на реализации попал бы
        в долги.
        """
        names = [name for name, _ in ENTITIES]

        assert names.index("counterparty") < names.index("contract")
        assert names.index("contract") < names.index("demand")
        assert names.index("contract") < names.index("commissionreportin")


class TestDocumentFields:
    def test_demand_links_its_contract(self, run, agent):
        contract = Contract.objects.create(
            ms_id=CONTRACT_ID, name="К-1", contract_type=ContractType.COMMISSION,
            agent=agent, last_seen_run=run,
        )
        client = FakeClient({"/entity/demand": [{
            "id": "dddddddd-1111-1111-1111-111111111111",
            "name": "00001",
            "moment": "2026-08-20 12:00:00.000",
            "agent": meta("counterparty", AGENT_ID),
            "contract": meta("contract", CONTRACT_ID),
            "sum": 100000.0,
            "applicable": True,
        }]})

        sync_demands(client, run)

        assert Document.objects.get().contract == contract

    def test_individual_deferral_is_synced(self, run, agent):
        client = FakeClient({"/entity/demand": [{
            "id": "dddddddd-1111-1111-1111-111111111111",
            "name": "00001",
            "moment": "2026-08-20 12:00:00.000",
            "agent": meta("counterparty", AGENT_ID),
            "attributes": [{"name": "Индивидуальный срок (дней)", "value": 7}],
            "sum": 100000.0,
            "applicable": True,
        }]})

        sync_demands(client, run)

        assert Document.objects.get().deferral_days == 7

    def test_commission_report_is_stored_as_its_own_kind(self, run, agent):
        """Отчёт комиссионера — отдельный вид: по нему и возникает долг."""
        client = FakeClient({"/entity/commissionreportin": [{
            "id": "eeeeeeee-1111-1111-1111-111111111111",
            "name": "00001",
            "moment": "2026-08-20 12:00:00.000",
            "agent": meta("counterparty", AGENT_ID),
            "sum": 300000.0,
            "payedSum": 100000.0,
            "applicable": True,
        }]})

        sync_commission_reports(client, run)

        report = Document.objects.get()
        assert report.kind == DocumentKind.COMMISSION_REPORT
        assert report.unpaid_kopecks == 200000

    def test_commission_reports_go_without_positions(self, run, agent):
        """Позиции не нужны: вопрос раздела — «сколько должны», а не «за что»."""
        client = FakeClient({"/entity/commissionreportin": []})

        sync_commission_reports(client, run)

        _, params = client.calls[0]
        assert "expand" not in (params or {})

    def test_marking_deleted_does_not_touch_neighbours(self, run, agent):
        """Пометка исчезнувших идёт по своему виду документов.

        Отгрузки и отчёты живут в одной таблице, и общая пометка снесла бы
        соседей — то есть обнулила бы половину раздела за один прогон.
        """
        demand = Document.objects.create(
            ms_id="dddddddd-2222-2222-2222-222222222222",
            kind=DocumentKind.DEMAND, number="00009",
            moment=datetime(2026, 8, 1, 12, 0, tzinfo=MOSCOW),
            agent=agent, last_seen_run=run,
        )

        later = SyncRun.objects.create(kind=SyncKind.DOCUMENTS)
        sync_commission_reports(FakeClient({"/entity/commissionreportin": []}), later)

        demand.refresh_from_db()
        assert demand.deleted_at is None


class TestReviewFindings:
    """Дефекты, найденные обзором 02.09."""

    def test_negative_deferral_does_not_break_the_whole_entity(self, run):
        """Отрицательная отсрочка не должна ронять синхронизацию всех контрагентов.

        Поле — `PositiveIntegerField`, и Postgres ответил бы `IntegrityError`.
        Тот ловится широким `except` в синке, который выставляет ошибку
        **всей сущности**: одна опечатка у одного контрагента остановила бы
        синхронизацию всех 104.
        """
        client = FakeClient({"/entity/counterparty": [
            {
                "id": AGENT_ID,
                "name": "С опечаткой",
                "attributes": [{"name": "Срок отсрочки (дней)", "value": -5}],
            },
            {
                "id": "aaaaaaaa-2222-2222-2222-222222222222",
                "name": "Нормальный",
                "attributes": [{"name": "Срок отсрочки (дней)", "value": 14}],
            },
        ]})

        outcome = sync_counterparties(client, run)

        assert outcome.error == "", "опечатка уронила всю сущность"
        assert Counterparty.objects.count() == 2
        assert Counterparty.objects.get(ms_id=AGENT_ID).deferral_days is None
        assert Counterparty.objects.get(
            ms_id="aaaaaaaa-2222-2222-2222-222222222222"
        ).deferral_days == 14

    def test_skipped_contract_is_not_reported_as_vanished(self, run, agent):
        """Пропущенный договор — не исчезнувший из учёта.

        Он не получает штамп прогона, и без защиты попал бы под пометку
        удаления: отчёт заявлял бы, что договор исчез из МойСклада, хотя
        он там есть, — и та же потеря считалась бы дважды, ведь у пропусков
        свой счётчик.
        """
        # Договор уже в зеркале с прошлого прогона.
        earlier = SyncRun.objects.create(kind=SyncKind.DOCUMENTS)
        contract = Contract.objects.create(
            ms_id=CONTRACT_ID, name="К-1", contract_type=ContractType.COMMISSION,
            agent=agent, last_seen_run=earlier,
        )

        # В новом прогоне контрагента в зеркале нет — договор пропускается.
        client = FakeClient({"/entity/contract": [{
            "id": CONTRACT_ID,
            "name": "К-1",
            "contractType": "Commission",
            "agent": meta("counterparty", "unknown-agent-id"),
        }]})

        outcome = sync_contracts(client, run)

        contract.refresh_from_db()
        assert contract.deleted_at is None, "пропущенный договор помечен исчезнувшим"
        assert outcome.marked_deleted == 0
        assert outcome.extra["skipped"] == 1

    def test_genuinely_missing_contract_is_still_marked(self, run, agent):
        """А договор, которого в выгрузке нет вовсе, помечается как раньше.

        Защита пропущенных не должна выключить саму пометку — иначе
        исчезнувшие из учёта договоры остались бы в расчётах навсегда.
        """
        earlier = SyncRun.objects.create(kind=SyncKind.DOCUMENTS)
        gone = Contract.objects.create(
            ms_id="cccccccc-9999-9999-9999-999999999999", name="Старый",
            agent=agent, last_seen_run=earlier,
        )

        outcome = sync_contracts(FakeClient({"/entity/contract": []}), run)

        gone.refresh_from_db()
        assert gone.deleted_at is not None
        assert outcome.marked_deleted == 1


class TestArchivedAreMirrored:
    """Архивные справочники обязаны попадать в зеркало.

    По умолчанию API отдаёт только действующие. Проверено 02.09 на боевом
    аккаунте: контрагентов 107, из них 2 в архиве, и в зеркале их не было
    вовсе. Ровно та же ошибка, что стоила 66 архивных товаров.
    """

    @pytest.mark.parametrize(
        "sync, path",
        [
            (sync_counterparties, "/entity/counterparty"),
            (sync_contracts, "/entity/contract"),
            (sync_sales_channels, "/entity/saleschannel"),
        ],
        ids=["контрагенты", "договоры", "каналы продаж"],
    )
    def test_archived_are_requested(self, run, sync, path):
        client = FakeClient({path: []})

        sync(client, run)

        requested = dict(client.calls[0][1] or {})
        assert requested.get("filter") == "archived=true;archived=false", (
            f"{path} запрашивается без архивных — они не попадут в зеркало"
        )

    def test_archived_counterparty_is_stored_with_its_flag(self, run):
        """Признак архивности сохраняется, а не теряется по дороге.

        Без него архивный контрагент неотличим от действующего, и «почему
        он в списке» выяснять будет негде.
        """
        client = FakeClient({"/entity/counterparty": [
            {"id": AGENT_ID, "name": 'ООО "ЛАДОГА ПЛЮС"', "archived": True},
        ]})

        sync_counterparties(client, run)

        assert Counterparty.objects.get(ms_id=AGENT_ID).archived is True


class TestSkippedDocumentsAreNotVanished:
    """Пропущенный документ — не исчезнувший."""

    def test_document_without_agent_is_not_marked_deleted(self, run, agent):
        """Документ, чей контрагент не доехал, остаётся живым.

        Пометка убрала бы его из выручки, маржи и каналов продаж молча.
        Хуже того, вернуться он бы уже не смог: `restore_returned` снимает
        пометку только с того, что видели в прогоне, а пропущенный штампа
        не получает — и остался бы удалённым навсегда.
        """
        earlier = SyncRun.objects.create(kind=SyncKind.DOCUMENTS)
        doc = Document.objects.create(
            ms_id="dddddddd-7777-7777-7777-777777777777",
            kind=DocumentKind.DEMAND, number="00276",
            moment=datetime(2026, 8, 24, 12, 0, tzinfo=MOSCOW),
            agent=agent, total_kopecks=100000, last_seen_run=earlier,
        )

        # В этом прогоне контрагента в зеркале нет — документ пропускается.
        client = FakeClient({"/entity/demand": [{
            "id": "dddddddd-7777-7777-7777-777777777777",
            "name": "00276",
            "moment": "2026-08-24 12:00:00.000",
            "agent": meta("counterparty", "unknown-agent-id"),
            "sum": 100000.0,
            "applicable": True,
        }]})

        outcome = sync_demands(client, run)

        doc.refresh_from_db()
        assert doc.deleted_at is None, "пропущенный документ помечен исчезнувшим"
        assert outcome.marked_deleted == 0
        assert outcome.extra["skipped_documents"] == 1

    def test_genuinely_missing_document_is_still_marked(self, run, agent):
        """А документ, которого в выгрузке нет вовсе, помечается как раньше."""
        earlier = SyncRun.objects.create(kind=SyncKind.DOCUMENTS)
        gone = Document.objects.create(
            ms_id="dddddddd-8888-8888-8888-888888888888",
            kind=DocumentKind.DEMAND, number="00100",
            moment=datetime(2026, 8, 1, 12, 0, tzinfo=MOSCOW),
            agent=agent, last_seen_run=earlier,
        )

        outcome = sync_demands(FakeClient({"/entity/demand": []}), run)

        gone.refresh_from_db()
        assert gone.deleted_at is not None
        assert outcome.marked_deleted == 1
