"""Предохранитель обязан останавливать весь прогон, а не одну сущность.

Самый дорогой сценарий в проекте: серия 429 срабатывает внутри первой
сущности, её обработчик ошибок глотает остановку, и прогон идёт дальше —
каждая следующая сущность добивает уже исчерпанный лимит. МойСклад
отключает доступ пользователю, и вместе с нами учёт теряет бот,
то есть вся компания. Включают обратно только через поддержку.

Тест перебирает все функции синхронизации автоматически: забыть защиту
в новой — обычное дело, и цена ошибки слишком велика.
"""

import inspect

import pytest

from core.models import SyncKind, SyncRun
from moysklad.limits import ApiDisabledRisk
from moysklad.sync import catalog, documents, references

pytestmark = pytest.mark.django_db


class ExplodingClient:
    """Клиент, у которого предохранитель срабатывает на первом же запросе."""

    request_count = 0

    def iterate(self, *args, **kwargs):
        raise ApiDisabledRisk("3 ответа 429 подряд, обращайтесь в поддержку")
        yield  # pragma: no cover — генератор, до сюда не доходит

    def get(self, *args, **kwargs):
        raise ApiDisabledRisk("3 ответа 429 подряд, обращайтесь в поддержку")


def sync_functions():
    """Все функции синхронизации сущностей — найденные, а не перечисленные."""
    found = []
    for module in (catalog, documents, references):
        for name, fn in vars(module).items():
            if not name.startswith("sync_") or not inspect.isfunction(fn):
                continue
            # Общая реализация принимает вид документа отдельным аргументом,
            # её проверяют обёртки sync_demands и sync_supplies.
            if name == "sync_documents":
                continue
            found.append(pytest.param(fn, id=name))
    return found


@pytest.mark.parametrize("sync", sync_functions())
def test_breaker_stops_the_whole_run(sync):
    """Остановка предохранителя проходит сквозь обработчик ошибок сущности.

    Если функция вернёт EntityOutcome с ошибкой вместо исключения, прогон
    продолжится и добьёт лимит.
    """
    run = SyncRun.objects.create(kind=SyncKind.DOCUMENTS)

    with pytest.raises(ApiDisabledRisk):
        sync(ExplodingClient(), run)


def test_at_least_one_function_is_checked():
    """Страховка от «тест зелёный, потому что проверять нечего»."""
    assert len(sync_functions()) >= 5
