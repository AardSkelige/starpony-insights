"""Общее для всего, что зеркалится из МойСклада.

Удаление документа в учёте до нас никак не доходит: у отгрузок нет корзины
(проверено на боевом аккаунте — `/entity/demand/trash` отвечает 404), а вебхуки
мы не используем. Единственный признак — документ перестал приходить в выгрузке.

Отсюда механизм: каждая строка помнит прогон, в котором её видели последний раз.
После **успешного** прохода всё, что осталось со старым штампом, помечается
удалённым. Только после успешного: если выгрузка оборвалась на середине,
недошедшее — это не удалённое.
"""

from django.db import models

from core.models.base import DomainModel
from core.models.sync import SyncRun


class MirrorQuerySet(models.QuerySet):
    def alive(self):
        """Всё, что есть в учёте сейчас. Обычный вид для расчётов."""
        return self.filter(deleted_at__isnull=True)


class MirrorModel(DomainModel):
    """Зеркало сущности МойСклада.

    Наследует DomainModel, а не models.Model: иначе модель не попадает
    в разбивку по группам бэкапа, и скрипт молча пропускает целую группу
    таблиц. Проверка это не ловила — она перебирала наследников DomainModel
    и потому просто не видела зеркало.

    Данные восстанавливаются синхронизацией, поэтому в ежедневный бэкап
    не идут — группа задаётся наследником через `backup_group`.
    """

    ms_id = models.UUIDField("Идентификатор в МойСкладе", unique=True, db_index=True)
    ms_updated = models.DateTimeField("Изменён в учёте", null=True, blank=True)

    last_seen_run = models.ForeignKey(
        SyncRun,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Последний раз видели в прогоне",
    )
    deleted_at = models.DateTimeField(
        "Исчез из учёта",
        null=True,
        blank=True,
        db_index=True,
        help_text="Строка не удаляется физически: на неё могут ссылаться "
                  "данные, введённые людьми.",
    )

    synced_at = models.DateTimeField("Обновлено у нас", auto_now=True)

    objects = MirrorQuerySet.as_manager()

    class Meta:
        abstract = True
