"""Механика синхронизации: журнал, штамп прогона, пометка исчезнувших.

Здесь проверяется то, что в жизни случается редко и молча: частичный отказ
и исчезновение документа из учёта.
"""

import pytest

from core.models import Product, SyncEntityResult, SyncKind, SyncRun, SyncStatus
from moysklad.sync.runner import (
    EntityOutcome,
    SyncSession,
    mark_missing_as_deleted,
    restore_returned,
    upsert,
)

pytestmark = pytest.mark.django_db


def make_product(ms_id, run, name="Товар"):
    upsert(Product, ms_id, run, {"name": name})
    return Product.objects.get(ms_id=ms_id)


class TestSyncSession:
    def test_all_succeeded_is_success(self):
        session = SyncSession(SyncKind.DOCUMENTS)
        session.record("product", EntityOutcome(fetched=10, created=10))
        assert session.finish().status == SyncStatus.SUCCESS

    def test_partial_failure_is_not_success(self):
        """Главное свойство журнала.

        Если приёмки обновились, а отгрузки упали, маржа считается на смеси
        свежего и вчерашнего. Такой прогон обязан отличаться от удавшегося,
        иначе «данные на 14:32» врут.
        """
        session = SyncSession(SyncKind.DOCUMENTS)
        session.record("supply", EntityOutcome(fetched=5, created=5))
        session.record("demand", EntityOutcome(error="429 Too Many Requests"))

        assert session.finish().status == SyncStatus.PARTIAL

    def test_total_failure(self):
        session = SyncSession(SyncKind.DOCUMENTS)
        session.record("demand", EntityOutcome(error="нет связи"))
        assert session.finish().status == SyncStatus.FAILED

    def test_result_is_stored_per_entity(self):
        session = SyncSession(SyncKind.STATE)
        session.record("stock", EntityOutcome(fetched=255, updated=255))
        session.record("demand", EntityOutcome(error="таймаут"))
        session.finish()

        results = {r.entity: r for r in SyncEntityResult.objects.all()}
        assert results["stock"].status == SyncStatus.SUCCESS
        assert results["demand"].status == SyncStatus.FAILED
        assert results["demand"].error == "таймаут"

    def test_breaker_error_marks_run_failed(self):
        """Остановка предохранителем — отказ, даже если часть данных дошла."""
        session = SyncSession(SyncKind.DOCUMENTS)
        session.record("product", EntityOutcome(fetched=314, created=314))
        run = session.finish(error="5 ответов 429 подряд")
        assert run.status == SyncStatus.FAILED


class TestDeletionTracking:
    def test_missing_rows_are_marked_deleted(self):
        """Документ, исчезнувший из выгрузки, — удалённый.

        Другого способа узнать нет: корзины у документов не существует,
        `/entity/demand/trash` отвечает 404 (проверено на боевом аккаунте).
        """
        first = SyncRun.objects.create(kind=SyncKind.DOCUMENTS)
        make_product("11111111-1111-1111-1111-111111111111", first)
        make_product("22222222-2222-2222-2222-222222222222", first)

        # Во втором прогоне пришёл только один товар.
        second = SyncRun.objects.create(kind=SyncKind.DOCUMENTS)
        make_product("11111111-1111-1111-1111-111111111111", second)

        assert mark_missing_as_deleted(Product, second) == 1
        assert Product.objects.alive().count() == 1
        assert Product.objects.count() == 2, "строка не должна удаляться физически"

    def test_returned_rows_are_restored(self):
        """Вернувшийся документ снимает пометку сам, без человека с SQL.

        Снимает именно `restore_returned` после успешного обхода, а не сам
        `upsert`: раньше пометку сбрасывал upsert, и восстановление молча
        не работало — до него не доходила ни одна строка.
        """
        first = SyncRun.objects.create(kind=SyncKind.DOCUMENTS)
        make_product("11111111-1111-1111-1111-111111111111", first)

        second = SyncRun.objects.create(kind=SyncKind.DOCUMENTS)
        mark_missing_as_deleted(Product, second)
        assert Product.objects.alive().count() == 0

        # Документ вернулся в учёт — и обход завершился успешно.
        third = SyncRun.objects.create(kind=SyncKind.DOCUMENTS)
        make_product("11111111-1111-1111-1111-111111111111", third)
        assert restore_returned(Product, third) == 1
        assert Product.objects.alive().count() == 1

    def test_restore_only_touches_rows_seen_in_this_run(self):
        """Восстанавливается только то, что действительно вернулось."""
        first = SyncRun.objects.create(kind=SyncKind.DOCUMENTS)
        make_product("11111111-1111-1111-1111-111111111111", first)
        make_product("22222222-2222-2222-2222-222222222222", first)

        second = SyncRun.objects.create(kind=SyncKind.DOCUMENTS)
        mark_missing_as_deleted(Product, second)

        # В третьем прогоне вернулся только один.
        third = SyncRun.objects.create(kind=SyncKind.DOCUMENTS)
        make_product("11111111-1111-1111-1111-111111111111", third)

        assert restore_returned(Product, third) == 1
        assert Product.objects.alive().count() == 1

    def test_upsert_does_not_duplicate(self):
        """Повторный прогон обновляет, а не создаёт заново.

        Никакого truncate/insert: на строки зеркала ссылаются данные,
        введённые людьми.
        """
        run = SyncRun.objects.create(kind=SyncKind.DOCUMENTS)
        _, created = upsert(Product, "11111111-1111-1111-1111-111111111111", run, {"name": "Было"})
        assert created

        obj, created = upsert(Product, "11111111-1111-1111-1111-111111111111", run, {"name": "Стало"})
        assert not created

        assert Product.objects.count() == 1
        assert Product.objects.get().name == "Стало"
        # Объект возвращается сразу: второй SELECT на каждую строку —
        # лишние сотни запросов за прогон.
        assert obj.name == "Стало"
