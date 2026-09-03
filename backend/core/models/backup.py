"""Журнал резервных копий базы.

**Признак готовности бэкапа — не «скрипт написан», а «из архива поднялась
база».** Три раза подряд в этом проекте файл лежал в репозитории и не был
установлен на сервере — расписание синхронизации, ротация журнала и сам
бэкап. Поэтому здесь пишется не «запустились», а «сняли, проверили
восстановлением, сколько старого убрали».

Состояние живёт в базе, а не в файле рядом со скриптом (`CLAUDE.md` §2).
Да, журнал бэкапов лежит в той базе, которую бэкапят: восстановившись,
мы увидим историю на момент снимка — и это ровно то, что нужно, чтобы
понять, из чего восстановились.
"""

from django.db import models
from django.utils import timezone

from core.models.base import BackupGroup, DomainModel


class BackupStatus(models.TextChoices):
    RUNNING = "running", "Идёт"
    SUCCESS = "success", "Готово"
    FAILED = "failed", "Не удалось"


class BackupRun(DomainModel):
    """Одно снятие копии: когда, что вышло, проверено ли восстановлением."""

    backup_group = BackupGroup.SNAPSHOT

    started_at = models.DateTimeField("Начат", default=timezone.now)
    finished_at = models.DateTimeField("Закончен", null=True, blank=True)
    status = models.CharField(
        "Итог", max_length=16, choices=BackupStatus, default=BackupStatus.RUNNING
    )

    name = models.CharField("Файл архива", max_length=255, blank=True)
    size_bytes = models.BigIntegerField("Размер, байт", default=0)

    # Не «файл создался», а «из него читается опись». Пустой или обрезанный
    # архив создаётся точно так же успешно, как настоящий, и отличить их
    # по наличию файла нельзя.
    verified = models.BooleanField("Проверен восстановлением", default=False)

    # Что удалили этим прогоном. Именами, а не числом: на вопрос «куда делся
    # архив за прошлый вторник» число не отвечает.
    pruned = models.JSONField("Удалённые архивы", default=list, blank=True)
    kept = models.PositiveIntegerField("Осталось архивов", default=0)

    dry_run = models.BooleanField("Пробный прогон", default=False)
    error = models.TextField("Ошибка", blank=True)

    class Meta:
        verbose_name = "Запуск бэкапа"
        verbose_name_plural = "Бэкапы базы"
        indexes = [models.Index(fields=["-started_at"])]

    def __str__(self) -> str:
        mark = " (пробный)" if self.dry_run else ""
        return f"{self.name or 'без файла'} — {self.get_status_display()}{mark}"
