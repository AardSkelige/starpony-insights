"""Документы учёта: отгрузки и приёмки.

Одна модель на оба вида — структура у них совпадает до поля `kind`. Разводить
их по таблицам значило бы дублировать и модель, и синхронизацию, и все запросы
поверх: «что продали» и «что закупили» почти всегда считаются одинаково.
"""

from django.db import models

from core.models.base import BackupGroup
from core.models.catalog import Product, Uom
from core.models.counterparty import Counterparty, SalesChannel
from core.models.mirror import MirrorModel


class DocumentKind(models.TextChoices):
    DEMAND = "demand", "Отгрузка"
    SUPPLY = "supply", "Приёмка"


class Document(MirrorModel):
    backup_group = BackupGroup.MIRROR

    kind = models.CharField("Вид", max_length=16, choices=DocumentKind, db_index=True)
    number = models.CharField("Номер", max_length=64)
    moment = models.DateTimeField("Дата документа", db_index=True)

    agent = models.ForeignKey(
        Counterparty,
        on_delete=models.PROTECT,
        related_name="documents",
        verbose_name="Контрагент",
    )
    sales_channel = models.ForeignKey(
        SalesChannel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents",
        verbose_name="Канал продаж",
    )

    # Суммы документа — целые копейки: так сходится с учётом до копейки
    # Дробные копейки бывают только у удельных величин — см. позиции ниже.
    total_kopecks = models.BigIntegerField("Сумма, копейки", default=0)
    paid_kopecks = models.BigIntegerField("Оплачено, копейки", default=0)
    vat_kopecks = models.BigIntegerField("НДС, копейки", default=0)

    applicable = models.BooleanField("Проведён", default=True)

    class Meta:
        verbose_name = "Документ"
        verbose_name_plural = "Документы"
        indexes = [
            models.Index(fields=["kind", "-moment"]),
            models.Index(fields=["kind", "agent"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} {self.number}"

    @property
    def unpaid_kopecks(self) -> int:
        """Сколько ещё не оплачено. Основа раздела «Сроки оплаты»."""
        return max(self.total_kopecks - self.paid_kopecks, 0)


class DocumentPosition(models.Model):
    """Строка документа.

    Не зеркало: у позиций свои идентификаторы, но отдельно они не живут —
    приходят и исчезают вместе с документом.
    """

    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name="positions"
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="positions", verbose_name="Товар"
    )
    uom = models.ForeignKey(
        Uom, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        verbose_name="Единица измерения",
    )

    # Количество — три знака: МойСклад отдаёт его типом Float, и без Decimal
    # на экране появляется «0.30000000000000004 шт».
    quantity = models.DecimalField(
        "Количество", max_digits=18, decimal_places=3, default=0
    )

    # Цена — в копейках, как приходит из учёта, и не делится на 100 при записи.
    # Деление добавило бы два знака к дробной части и вытеснило значащие:
    # цена 82.55374 копейки превращалась в 0.825537 рубля, теряя 4e-7 —
    # при количестве 200 000 это ровно 8 копеек расхождения с документом.
    price_kopecks = models.DecimalField(
        "Цена за единицу, копейки", max_digits=18, decimal_places=6, default=0
    )
    discount = models.DecimalField(
        "Скидка, %", max_digits=6, decimal_places=3, default=0
    )

    # Сумма строки целыми копейками, посчитанная из неокруглённых значений.
    # Хранится отдельно, а не считается на лету: только так сумма позиций
    # сходится с суммой документа, что бы ни случилось с точностью цены.
    total_kopecks = models.BigIntegerField("Сумма строки, копейки", default=0)

    class Meta:
        verbose_name = "Позиция документа"
        verbose_name_plural = "Позиции документов"
        indexes = [models.Index(fields=["document", "product"])]

    def __str__(self) -> str:
        return f"{self.product} × {self.quantity}"
