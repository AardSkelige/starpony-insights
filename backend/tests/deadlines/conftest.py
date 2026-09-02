"""Фикстуры раздела «Сроки оплаты».

Лежат в своей папке по той же причине, что у соседей: имена `run`,
`make_agent`, `make_document` заняты локальными фикстурами других тестов,
и вынос наверх сделал бы неочевидным, чья версия сработала.

**Даты здесь считаются от «сегодня», а не задаются числами.** Возраст долга —
величина, которая меняется каждый день, и фикстура с 1 июня протухла бы
через неделю: тест сначала краснеет по календарю, потом его правят «чтобы
проходил», и он перестаёт проверять что-либо.
"""

from datetime import datetime, timedelta

import pytest
from django.utils import timezone

from core.dates import today as local_today
from core.models import (
    Contract,
    ContractType,
    Counterparty,
    Document,
    DocumentKind,
    SalesChannel,
    SyncKind,
    SyncRun,
)


def moscow(year, month, day, hour=12):
    """Момент в московском поясе — том, в котором живёт учёт и человек."""
    return timezone.make_aware(datetime(year, month, day, hour))


def days_ago(days: int, hour: int = 12):
    """Момент ровно столько-то календарных дней назад.

    Полдень намеренно: он одинаково далёк от обеих границ суток, и тест
    не начинает зависеть от часа своего запуска. Ночные моменты проверяются
    отдельно и явно — там как раз и живёт ошибка на один день.
    """
    day = local_today() - timedelta(days=days)
    return timezone.make_aware(datetime(day.year, day.month, day.day, hour))


@pytest.fixture
def run():
    return SyncRun.objects.create(kind=SyncKind.DOCUMENTS)


@pytest.fixture
def make_agent(run):
    counter = {"n": 0}

    def _make(name="Покупатель", *, deferral_days=None, tags=()):
        counter["n"] += 1
        return Counterparty.objects.create(
            ms_id=f"aaaaaaaa-0000-0000-0000-{counter['n']:012d}",
            name=name,
            deferral_days=deferral_days,
            tags=list(tags),
            last_seen_run=run,
        )

    return _make


@pytest.fixture
def make_contract(run):
    counter = {"n": 0}

    def _make(agent, contract_type=ContractType.COMMISSION):
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
def make_channel(run):
    counter = {"n": 0}

    def _make(name="Озон"):
        counter["n"] += 1
        return SalesChannel.objects.create(
            ms_id=f"eeeeeeee-0000-0000-0000-{counter['n']:012d}",
            name=name,
            last_seen_run=run,
        )

    return _make


@pytest.fixture
def make_document(run, make_agent):
    """Неоплаченный документ по умолчанию: сумма есть, оплаты нет."""
    counter = {"n": 0}
    default = {"agent": None}

    def _make(
        *,
        agent=None,
        age_days=10,
        moment=None,
        kind=DocumentKind.DEMAND,
        total_kopecks=100_000,
        paid_kopecks=0,
        contract=None,
        sales_channel=None,
        deferral_days=None,
        applicable=True,
        deleted=False,
        description="",
    ):
        counter["n"] += 1
        if agent is None:
            if default["agent"] is None:
                default["agent"] = make_agent()
            agent = default["agent"]

        return Document.objects.create(
            ms_id=f"dddddddd-0000-0000-0000-{counter['n']:012d}",
            kind=kind,
            number=f"{counter['n']:05d}",
            moment=moment if moment is not None else days_ago(age_days),
            agent=agent,
            contract=contract,
            sales_channel=sales_channel,
            total_kopecks=total_kopecks,
            paid_kopecks=paid_kopecks,
            deferral_days=deferral_days,
            applicable=applicable,
            description=description,
            deleted_at=timezone.now() if deleted else None,
            last_seen_run=run,
        )

    return _make
