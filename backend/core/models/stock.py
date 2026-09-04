"""Остатки на складе — то, что меняется постоянно.

Отдельно от номенклатуры намеренно: товар правят редко, а остаток меняется
после каждой отгрузки. Синхронизации у них разные — ночная и каждые 10–15 минут,
и держать их в одной таблице значило бы переписывать справочник ради чисел.
"""

from django.db import models

from core.models.base import BackupGroup, DomainModel
from core.models.catalog import Product


class Stock(DomainModel):
    """Остаток и себестоимость по товару.

    Восстанавливается синхронизацией, поэтому в ежедневный бэкап не идёт.
    """

    backup_group = BackupGroup.MIRROR

    product = models.OneToOneField(
        Product, on_delete=models.CASCADE, related_name="stock", verbose_name="Товар"
    )

    # Количества — три знака: API отдаёт их типом Float, и без Decimal
    # на экране появляется «0.30000000000000004 шт».
    quantity = models.DecimalField("Всего", max_digits=18, decimal_places=3, default=0)
    reserved = models.DecimalField("В резерве", max_digits=18, decimal_places=3, default=0)
    in_transit = models.DecimalField("Ожидается", max_digits=18, decimal_places=3, default=0)

    # Себестоимость в копейках, как приходит из учёта: деление на 100 при записи
    # вытесняет значащие знаки — у 150 позиций из 255 она дробная.
    cost_kopecks = models.DecimalField(
        "Себестоимость единицы, копейки", max_digits=18, decimal_places=6, default=0
    )

    # Возраст сегодняшнего остатка: сколько дней он лежит на складе.
    # Считает МойСклад, мы забираем готовым (`stockDays` в `/report/stock/all`,
    # в документации — «количество дней на складе»).
    #
    # **Это не «дни без движения»**, хотя так поле называлось до 04.09.
    # Проверено на боевых: у всех 57 товаров с нулевым остатком здесь ноль,
    # и ни у одного не больше. Лежать нечему — значит и дней нет; читать
    # это как «движение было сегодня» было прямой ошибкой.
    stock_days = models.IntegerField("Дней на складе", null=True, blank=True)

    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Остаток"
        verbose_name_plural = "Остатки"
        indexes = [models.Index(fields=["-stock_days"])]

    def __str__(self) -> str:
        return f"{self.product}: {self.quantity}"

    @property
    def available(self):
        """Свободный остаток: что можно продать или пустить в производство."""
        return self.quantity - self.reserved
