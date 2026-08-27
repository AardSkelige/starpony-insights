"""Ход синхронизации: журнал, штамп прогона, пометка исчезнувших.

Одна сущность, упавшая на 429, не должна выглядеть как удавшийся прогон —
иначе расчёты пойдут на смеси свежих и вчерашних данных, и никто не заметит.
Поэтому итог пишется по каждой сущности отдельно, а общий статус становится
`partial`, если упало хоть что-то.
"""

import logging
from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone

from core.models import SyncEntityResult, SyncKind, SyncRun, SyncStatus

logger = logging.getLogger(__name__)


@dataclass
class EntityOutcome:
    """Что случилось с одной сущностью."""

    fetched: int = 0
    created: int = 0
    updated: int = 0
    marked_deleted: int = 0
    error: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.error


class SyncSession:
    """Прогон целиком: открывает журнал, копит итоги, закрывает статусом."""

    def __init__(self, kind: SyncKind, *, manual: bool = False):
        self.run = SyncRun.objects.create(kind=kind, triggered_manually=manual)
        self._outcomes: dict[str, EntityOutcome] = {}

    def record(self, entity: str, outcome: EntityOutcome) -> None:
        self._outcomes[entity] = outcome
        SyncEntityResult.objects.update_or_create(
            run=self.run,
            entity=entity,
            defaults={
                "status": SyncStatus.SUCCESS if outcome.ok else SyncStatus.FAILED,
                "fetched": outcome.fetched,
                "created": outcome.created,
                "updated": outcome.updated,
                "marked_deleted": outcome.marked_deleted,
                "error": outcome.error[:2000],
            },
        )
        if outcome.ok:
            logger.info(
                "%s: получено %s, создано %s, обновлено %s, помечено удалёнными %s",
                entity, outcome.fetched, outcome.created, outcome.updated,
                outcome.marked_deleted,
            )
        else:
            logger.error("%s: %s", entity, outcome.error)

    def finish(self, *, request_count: int = 0, error: str = "") -> SyncRun:
        succeeded = [o for o in self._outcomes.values() if o.ok]
        failed = [o for o in self._outcomes.values() if not o.ok]

        if error or (failed and not succeeded):
            status = SyncStatus.FAILED
        elif failed:
            # Частичный отказ — отдельный статус, а не «успех с оговоркой».
            # Именно он скрывает расхождения, если его не различать.
            status = SyncStatus.PARTIAL
        else:
            status = SyncStatus.SUCCESS

        self.run.status = status
        self.run.finished_at = timezone.now()
        self.run.request_count = request_count
        self.run.error = error[:2000]
        self.run.save(update_fields=["status", "finished_at", "request_count", "error"])
        return self.run

    @property
    def all_succeeded(self) -> bool:
        return bool(self._outcomes) and all(o.ok for o in self._outcomes.values())


def mark_missing_as_deleted(model, run: SyncRun) -> int:
    """Пометить удалённым всё, чего не было в этом прогоне.

    Вызывается **только после успешного** обхода сущности. Оборвавшаяся
    выгрузка не означает, что документы удалили, — а пометка снимет их
    из всех расчётов разом.

    Строки не удаляются физически: на них могут ссылаться данные,
    введённые людьми.
    """
    missing = model.objects.filter(deleted_at__isnull=True).exclude(last_seen_run=run)
    return missing.update(deleted_at=timezone.now())


def restore_returned(model, run: SyncRun) -> int:
    """Снять пометку удаления с того, что снова появилось в учёте.

    Документ могли пометить удалённым по ошибке — например, из-за фильтра
    в выгрузке. Если он вернулся, отметка должна сняться сама, а не ждать
    человека с SQL-консолью.
    """
    return model.objects.filter(
        deleted_at__isnull=False, last_seen_run=run
    ).update(deleted_at=None)


@transaction.atomic
def upsert(model, ms_id, run: SyncRun, defaults: dict):
    """Создать или обновить строку зеркала. Возвращает (объект, создан ли).

    Только upsert по `ms_id`, никакого truncate/insert: на строки зеркала
    ссылаются введённые людьми данные, и пересоздание оборвало бы связи.

    Пометку удаления здесь не снимаем — это делает `restore_returned` после
    успешного обхода. Иначе получалось бы два места, отвечающих за одно и то
    же, и восстановление молча не работало: строка выходила из удалённых
    ещё до того, как до неё доходила проверка.
    """
    return model.objects.update_or_create(
        ms_id=ms_id,
        defaults={**defaults, "last_seen_run": run},
    )
