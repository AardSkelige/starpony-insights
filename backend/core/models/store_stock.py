"""Остаток по складам — знаменатель для «сколько склада пересчитано».

Отдельно от `Stock`, хотя оба про остаток. Причина не в полях, а в вопросе:
`Stock` отвечает «сколько всего есть» и обновляется каждые пятнадцать минут,
потому что от него зависят закупка и производство. Здесь — «что лежит
на каждом из трёх складов», и это нужно ровно затем, чтобы разделить
пересчитанное и непересчитанное. Свежесть в четверть часа такому вопросу
не нужна, а лишний запрос в общей с ботом корзине — нужен ещё меньше.

**Склад хранится именем, а не ссылкой на справочник.** Имя приходит прямо
в строке отчёта (`stockByStore[].name`), как и в инвентаризации, — заводить
таблицу складов значило бы синхронизировать сущность ради одного поля,
которое и так приезжает.
"""

from django.db import models

from core.models.base import BackupGroup, DomainModel
from core.models.catalog import Product


class StoreStock(DomainModel):
    """Сколько позиции лежит на конкретном складе.

    Восстанавливается синхронизацией, поэтому в ежедневный бэкап не идёт.
    """

    backup_group = BackupGroup.MIRROR

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="store_stocks",
        verbose_name="Товар",
    )
    store_name = models.CharField("Склад", max_length=255, db_index=True)

    # Количества — три знака: API отдаёт их типом Float.
    quantity = models.DecimalField("Остаток", max_digits=18, decimal_places=3, default=0)
    reserved = models.DecimalField("В резерве", max_digits=18, decimal_places=3, default=0)

    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Остаток по складу"
        verbose_name_plural = "Остатки по складам"
        constraints = [
            models.UniqueConstraint(
                fields=["product", "store_name"], name="unique_product_store"
            )
        ]
        indexes = [models.Index(fields=["store_name"])]

    def __str__(self) -> str:
        return f"{self.product} на складе «{self.store_name}»: {self.quantity}"
