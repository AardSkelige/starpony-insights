"""Контрагенты: покупатели и поставщики."""

from django.db import models

from core.models.base import BackupGroup
from core.models.mirror import MirrorModel

# Группа контрагента, которой в учёте помечены маркетплейсы. Признак берётся
# из учёта, а не заводится у нас: человек уже ведёт эти группы руками,
# и второй список тех же контрагентов разошёлся бы с первым.
#
# Почему это важно именно здесь: площадка платит реестром раз в несколько
# недель, и выплата в учёт не заводится вовсе — у «Интернет Решений» ни одного
# платежа на 236 235 ₽ отгрузок. Считать это долгом наравне с покупателем,
# который просто не заплатил, значит утопить настоящую дебиторку: на 02.09
# это 314 470 ₽ площадок против 123 044 ₽ живого долга.
MARKETPLACE_TAG = "маркетплейсы"


class Counterparty(MirrorModel):
    backup_group = BackupGroup.MIRROR

    name = models.CharField("Название", max_length=255)
    inn = models.CharField("ИНН", max_length=12, blank=True)
    archived = models.BooleanField("В архиве", default=False)

    # Отсрочка платежа из доп. поля «Срок отсрочки (дней)». Срока оплаты
    # в учёте нет и быть не может: он не хранится, а считается — «дата отгрузки
    # плюс дни отсрочки».
    #
    # `null`, а не ноль: разница между ними — это разница между «платят
    # по факту, сразу» и «мы не знаем, договаривались ли об отсрочке».
    # Разведка 30.08 показала, что поле не заполнено ни у одного из 104
    # контрагентов, поэтому пустота здесь — нормальное состояние, а не сбой.
    deferral_days = models.PositiveIntegerField(
        "Отсрочка, дней", null=True, blank=True
    )

    # Группы контрагента из учёта — как есть, списком строк. Зеркало, а не
    # разбор: сегодня из них читается один признак (маркетплейс), но группы
    # заводит человек, и следующая понадобившаяся не потребует ни миграции,
    # ни повторного синка.
    tags = models.JSONField("Группы", default=list, blank=True)

    class Meta:
        verbose_name = "Контрагент"
        verbose_name_plural = "Контрагенты"
        indexes = [models.Index(fields=["name"])]

    def __str__(self) -> str:
        return self.name

    @property
    def is_marketplace(self) -> bool:
        """Расчёты идут через площадку, а не напрямую.

        Сравнение без учёта регистра и пробелов: группу набирает человек,
        и «Маркетплейсы» с заглавной — та же группа, а не другая.
        """
        return any(
            str(tag).strip().casefold() == MARKETPLACE_TAG
            for tag in (self.tags or [])
        )


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
