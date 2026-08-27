"""Контрагенты: покупатели и поставщики."""

from django.db import models

from core.models.base import BackupGroup
from core.models.mirror import MirrorModel


class Counterparty(MirrorModel):
    backup_group = BackupGroup.MIRROR

    name = models.CharField("Название", max_length=255)
    inn = models.CharField("ИНН", max_length=12, blank=True)
    archived = models.BooleanField("В архиве", default=False)

    class Meta:
        verbose_name = "Контрагент"
        verbose_name_plural = "Контрагенты"
        indexes = [models.Index(fields=["name"])]

    def __str__(self) -> str:
        return self.name


class SalesChannel(MirrorModel):
    """Канал продаж.

    Лежит прямо в отгрузке, отдельного запроса не требует. Заполнен
    у 99.7% отгрузок, поэтому работает и фильтром, и отдельным разделом
    и отдельным разделом со статистикой по каналам.
    """

    backup_group = BackupGroup.MIRROR

    name = models.CharField("Название", max_length=255)
    type = models.CharField("Тип", max_length=64, blank=True)

    class Meta:
        verbose_name = "Канал продаж"
        verbose_name_plural = "Каналы продаж"

    def __str__(self) -> str:
        return self.name
