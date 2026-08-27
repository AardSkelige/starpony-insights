"""Номенклатура: товары, материалы, техкарты.

Поля взяты из фактических ответов API, а не из документации по памяти:
`price`, `quantity`, `stock` приходят типом Float, поэтому разбираются
через `Decimal(str(x))`: иначе погрешность двоичного представления
float переезжает в расчёты себестоимости.
"""

from django.db import models

from core.models.base import BackupGroup
from core.models.mirror import MirrorModel


class Uom(MirrorModel):
    """Единица измерения.

    Отдельной таблицей, потому что в товаре она приходит только ссылкой,
    без названия. Догружать её по каждому товару — сотни запросов из общей
    с ботом корзины ради 59 строк справочника.

    Ошибка здесь стоит дорого: техкарта в граммах против приёмки в килограммах
    расходится ровно в 1000 раз и на глаз незаметна.
    """

    backup_group = BackupGroup.MIRROR

    name = models.CharField("Обозначение", max_length=32)
    description = models.CharField("Название", max_length=255, blank=True)

    class Meta:
        verbose_name = "Единица измерения"
        verbose_name_plural = "Единицы измерения"

    def __str__(self) -> str:
        return self.name


class ProductKind(models.TextChoices):
    PRODUCT = "product", "Товар или материал"
    SERVICE = "service", "Услуга"


class Product(MirrorModel):
    """Позиция номенклатуры: товар, материал или услуга.

    Товары и материалы в МойСкладе — одна сущность. Услуги — другая, но в
    документах ведут себя одинаково, а терять их нельзя: доставка в приёмке
    входит в стоимость закупки и дальше в маржу. Поэтому одна таблица
    с признаком вида, а не две почти одинаковые.
    """

    backup_group = BackupGroup.MIRROR

    kind = models.CharField(
        "Вид", max_length=16, choices=ProductKind, default=ProductKind.PRODUCT
    )
    name = models.CharField("Название", max_length=255)
    article = models.CharField("Артикул", max_length=100, blank=True)
    code = models.CharField("Код", max_length=100, blank=True)
    # Путь папки: по нему выводится линейка продукции (PRD §5.10).
    folder = models.CharField("Группа", max_length=255, blank=True)
    uom = models.ForeignKey(
        Uom,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
        verbose_name="Единица измерения",
    )
    archived = models.BooleanField("В архиве", default=False)

    # Закупочная цена — удельная величина, поэтому DECIMAL, а не копейки:
    # округление до копейки на грамме сырья даёт ошибку в проценты.
    # В копейках, как приходит из учёта: деление на 100 при записи вытесняет
    # значащие знаки из дробной части — см. DocumentPosition.price_kopecks.
    buy_price_kopecks = models.DecimalField(
        "Закупочная цена, копейки",
        max_digits=18,
        decimal_places=6,
        null=True,
        blank=True,
    )
    min_balance = models.DecimalField(
        "Неснижаемый остаток", max_digits=18, decimal_places=3, null=True, blank=True
    )

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        indexes = [models.Index(fields=["name"]), models.Index(fields=["article"])]

    def __str__(self) -> str:
        return self.name
