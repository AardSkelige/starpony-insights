"""Технологические карты: из чего и в каком количестве делается продукция.

Производство идёт в два шага, и это видно прямо в данных: 17 техкарт делают
из сырья полуфабрикат («замес»), остальные 72 — из полуфабриката готовый
товар («розлив»). Материал одной техкарты может быть продуктом другой.

Отсюда главное следствие: чтобы узнать, сколько сырья нужно на готовый товар,
цепочку приходится разворачивать. Прямой список материалов покажет не сырьё,
а полуфабрикат — то есть не то, что закупают.
"""

from django.db import models

from core.models.base import BackupGroup
from core.models.catalog import Product, Uom
from core.models.mirror import MirrorModel


class ProcessingPlan(MirrorModel):
    """Техкарта: что получается и в каком объёме за один прогон."""

    backup_group = BackupGroup.MIRROR

    name = models.CharField("Название", max_length=255)
    # Путь папки — по нему выводится линейка продукции. TextField, а не
    # CharField: длина пути в API не ограничена, а превышение уронило бы
    # не одну строку, а всю синхронизацию техкарт разом.
    folder = models.TextField('Группа', blank=True)

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="produced_by",
        verbose_name="Что выпускается",
    )
    # Сколько получается за один прогон. Расход материала на единицу продукции
    # считается делением на это число, поэтому ноль здесь недопустим.
    output_quantity = models.DecimalField(
        "Объём выпуска", max_digits=18, decimal_places=3, default=1
    )
    archived = models.BooleanField("В архиве", default=False)

    class Meta:
        verbose_name = "Техкарта"
        verbose_name_plural = "Техкарты"
        indexes = [models.Index(fields=["product"])]

    def __str__(self) -> str:
        return self.name


class ProcessingPlanMaterial(models.Model):
    """Строка техкарты: сколько материала уходит на объём выпуска.

    Не зеркало: отдельно от техкарты не живёт, приходит и исчезает вместе с ней.
    """

    plan = models.ForeignKey(
        ProcessingPlan, on_delete=models.CASCADE, related_name="materials"
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="used_in", verbose_name="Материал"
    )
    uom = models.ForeignKey(
        Uom, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        verbose_name="Единица измерения",
    )
    # Три знака: в техкартах встречаются доли грамма (0.3 г Трилона Б),
    # и округление до целых обнулило бы половину состава.
    quantity = models.DecimalField("Количество", max_digits=18, decimal_places=3)

    class Meta:
        verbose_name = "Материал техкарты"
        verbose_name_plural = "Материалы техкарт"
        indexes = [models.Index(fields=["plan", "product"])]

    def __str__(self) -> str:
        return f"{self.product} × {self.quantity}"
