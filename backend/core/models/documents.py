"""Документы учёта: отгрузки, приёмки и заказы поставщикам.

Одна модель на все виды — структура у них совпадает до поля `kind`. Разводить
их по таблицам значило бы дублировать и модель, и синхронизацию, и все запросы
поверх: «что продали» и «что закупили» почти всегда считаются одинаково.

**Заказ поставщику приходит без позиций** — и это проверено, а не принято
из удобства. Позиции у него есть (415 строк в 96 заказах), и `expand` их
не стоил бы ни одного лишнего запроса. Взять их имело бы смысл ради двух
вещей, и обе оказались пустыми:

- **Недопоставка.** 92 заказа из 94 закрыты ровно тем, что заказали. Из двух
  расхождений одно — пересорт (+108 одного наименования, −108 другого).
  Колонка «выполняет заказ полностью» показывала бы 98 % у всех.
- **Товар в пути.** Открытых заказов два, и один из них от 10 марта
  на 184 820 ₽ — за полгода это не поставка в пути, а забытый документ.

Значит от заказа нужен ровно один факт — дата, от которой до приёмки
считается срок поставки. Хранить строки, которые никто не читает, — долг:
через месяц их примут за источник правды и посчитают по ним.
"""

from django.db import models

from core.models.base import BackupGroup
from core.models.catalog import Product, Uom
from core.models.counterparty import Counterparty, SalesChannel
from core.models.mirror import MirrorModel


class DocumentKind(models.TextChoices):
    DEMAND = "demand", "Отгрузка"
    SUPPLY = "supply", "Приёмка"
    PURCHASE_ORDER = "purchase_order", "Заказ поставщику"


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

    # Заказ, которым приёмка была вызвана. Заполнен только у приёмок, и от него
    # считается срок поставки: сколько прошло от заказа до прихода товара.
    #
    # Ссылка на себя, а не отдельная таблица связи: у приёмки заказ ровно один
    # (`purchaseOrder` в API — одиночное поле), а обратное направление —
    # массив `supplies` у заказа — восстанавливается из неё же.
    #
    # SET_NULL, а не CASCADE: исчезнувший в учёте заказ не должен уносить
    # за собой приёмку. Товар пришёл и деньги потрачены независимо от того,
    # что случилось с бумагой, которая его вызвала.
    purchase_order = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplies",
        verbose_name="Заказ поставщику",
    )

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
