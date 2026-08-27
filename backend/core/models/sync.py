"""Журнал синхронизаций.

Отвечает на два вопроса, без которых зеркало нельзя считать надёжным:
«актуальны ли данные на экране» и «что исчезло из учёта».

Частичный отказ — главная опасность. Если приёмки обновились, а отгрузки
упали на 429, маржа считается на смеси свежего и вчерашнего, и никто об этом
не знает. Поэтому статус хранится по каждой сущности отдельно, а «данные на …»
берётся из последнего **успешного** прогона.
"""

from django.db import models
from django.utils import timezone

from core.models.base import BackupGroup, DomainModel


class SyncKind(models.TextChoices):
    DOCUMENTS = "documents", "Документы — ночью"
    STATE = "state", "Состояние — каждые 10–15 минут"


class SyncStatus(models.TextChoices):
    RUNNING = "running", "Идёт"
    SUCCESS = "success", "Успешно"
    PARTIAL = "partial", "Частично — часть сущностей не обновилась"
    FAILED = "failed", "Не удалось"


class SyncRun(DomainModel):
    """Один прогон синхронизации."""

    backup_group = BackupGroup.SNAPSHOT

    kind = models.CharField("Что синхронизируем", max_length=16, choices=SyncKind)
    status = models.CharField(
        "Итог", max_length=16, choices=SyncStatus, default=SyncStatus.RUNNING
    )
    started_at = models.DateTimeField("Начат", default=timezone.now)
    finished_at = models.DateTimeField("Закончен", null=True, blank=True)

    # Сколько запросов ушло в МойСклад. Лимит общий с ботом, и рост этого
    # числа — первый признак, что синхронизация начала мешать чужой работе.
    request_count = models.PositiveIntegerField("Запросов к API", default=0)
    triggered_manually = models.BooleanField("Запущен кнопкой", default=False)
    error = models.TextField("Ошибка", blank=True)

    class Meta:
        verbose_name = "Прогон синхронизации"
        verbose_name_plural = "Прогоны синхронизации"
        indexes = [models.Index(fields=["kind", "-started_at"])]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} — {self.get_status_display()}"

    @property
    def duration_seconds(self) -> float | None:
        if not self.finished_at:
            return None
        return (self.finished_at - self.started_at).total_seconds()


class SyncEntityResult(DomainModel):
    """Итог по одной сущности внутри прогона.

    Без этой таблицы «синхронизация прошла» — слишком грубая правда:
    прогон, где отгрузки не доехали, выглядел бы так же, как удавшийся.
    """

    backup_group = BackupGroup.SNAPSHOT

    run = models.ForeignKey(SyncRun, on_delete=models.CASCADE, related_name="entities")
    entity = models.CharField("Сущность", max_length=64)
    status = models.CharField("Итог", max_length=16, choices=SyncStatus)
    fetched = models.PositiveIntegerField("Получено из API", default=0)
    created = models.PositiveIntegerField("Создано", default=0)
    updated = models.PositiveIntegerField("Обновлено", default=0)
    marked_deleted = models.PositiveIntegerField("Помечено удалёнными", default=0)
    error = models.TextField("Ошибка", blank=True)

    class Meta:
        verbose_name = "Результат по сущности"
        verbose_name_plural = "Результаты по сущностям"
        constraints = [
            models.UniqueConstraint(fields=["run", "entity"], name="unique_run_entity"),
        ]

    def __str__(self) -> str:
        return f"{self.entity}: {self.get_status_display()}"
