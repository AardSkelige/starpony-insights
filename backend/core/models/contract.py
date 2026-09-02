"""Договоры с контрагентами.

Нужны ради одного различия, без которого раздел «Сроки оплаты» врёт:
**товар по договору комиссии уходит на реализацию, а не в продажу.**
У таких отгрузок `payedSum` не заполняется никогда — деньги приходят
не за отгрузку, а по отчёту комиссионера. Считать их неоплаченными значит
показать долг там, где долга нет, и притом самый крупный: он копится
с каждой новой отгрузкой комиссионеру.

Отдельной таблицей, а не признаком в документе: отчёт комиссионера тоже
ссылается на договор, и объяснение «долг контролируется по отчёту, договор
такой-то» без номера договора не собрать (`CLAUDE.md` §4).
"""

from django.db import models

from core.models.base import BackupGroup
from core.models.counterparty import Counterparty
from core.models.mirror import MirrorModel


class ContractType(models.TextChoices):
    SALES = "sales", "Купли-продажи"
    COMMISSION = "commission", "Комиссии"


class Contract(MirrorModel):
    backup_group = BackupGroup.MIRROR

    name = models.CharField("Номер договора", max_length=255)
    contract_type = models.CharField(
        "Тип", max_length=16, choices=ContractType, default=ContractType.SALES
    )
    agent = models.ForeignKey(
        Counterparty,
        on_delete=models.PROTECT,
        related_name="contracts",
        verbose_name="Контрагент",
    )
    archived = models.BooleanField("В архиве", default=False)

    class Meta:
        verbose_name = "Договор"
        verbose_name_plural = "Договоры"
        indexes = [models.Index(fields=["contract_type"])]

    def __str__(self) -> str:
        return f"{self.get_contract_type_display()} № {self.name}"

    @property
    def is_commission(self) -> bool:
        return self.contract_type == ContractType.COMMISSION
