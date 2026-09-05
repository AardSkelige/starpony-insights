"""Инвентаризация: пересчёт склада и расхождения по нему.

Отдельно от `Document`, хотя это тоже документ учёта. Причина не в шапке —
она как раз совпадает, — а в позиции: у строки инвентаризации **два
количества**, расчётное и фактическое, и вся страница живёт на разнице между
ними. Впихни это в `DocumentPosition`, и у отгрузок с приёмками появятся три
поля, которые у них всегда пусты, а у «что и на сколько не сошлось» —
проверка вида документа в каждом запросе.

**Расхождение берётся из ответа API, а не считается нами.** У МойСклада есть
известный баг: инвентаризация, созданная с `positions` в теле запроса,
копирует `quantity` в `calculatedQuantity` — расчётный остаток становится
равен фактическому, и разница выходит нулевой (`moysklad/CLAUDE.md`). Наша
арифметика поверх двух одинаковых чисел дала бы тот же ноль, но выглядела бы
собственным расчётом. Поэтому `correction_amount` и `correction_sum_kopecks`
хранятся такими, какими их посчитал учёт: расходится страница с учётом или
нет — видно сразу, а не после сверки формул.
"""

from django.db import models

from core.models.base import BackupGroup
from core.models.catalog import Product
from core.models.mirror import MirrorModel


class Inventory(MirrorModel):
    backup_group = BackupGroup.MIRROR

    number = models.CharField("Номер", max_length=64)
    moment = models.DateTimeField("Дата документа", db_index=True)

    # Название склада, а не ссылка на справочник: складов три, они приходят
    # вместе с документом через `expand`, и больше их никто не спрашивает.
    # Заведём таблицу, когда склад понадобится второму разделу.
    #
    # Хранить его обязательно: пересчитали **где**. «Считали 06.08» без склада
    # означало бы, что посчитан весь товар, — а посчитана была упаковка
    # на одном складе из трёх.
    store_name = models.CharField("Склад", max_length=255, blank=True)

    # Сумма документа целыми копейками — стоимость пересчитанного объёма.
    # Нужна как знаменатель: «недостача 12 000 ₽» без масштаба не говорит
    # ничего, а «12 000 из 340 000» — говорит.
    total_kopecks = models.BigIntegerField("Сумма, копейки", default=0)

    # Комментарий из учёта: здесь пишут, почему считали и что нашли.
    description = models.TextField("Комментарий", blank=True)

    class Meta:
        verbose_name = "Инвентаризация"
        verbose_name_plural = "Инвентаризации"
        indexes = [models.Index(fields=["-moment"])]

    def __str__(self) -> str:
        return f"Инвентаризация {self.number}"


class InventoryPosition(models.Model):
    """Строка инвентаризации: сколько числилось, сколько нашли.

    Не зеркало: отдельно от документа не живёт, приходит и исчезает вместе
    с ним — как `DocumentPosition`.
    """

    inventory = models.ForeignKey(
        Inventory, on_delete=models.CASCADE, related_name="positions"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="inventory_positions",
        verbose_name="Товар",
    )

    # Оба количества — три знака, как везде: API отдаёт их типом Float.
    counted = models.DecimalField(
        "Фактически", max_digits=18, decimal_places=3, default=0
    )
    calculated = models.DecimalField(
        "Числилось", max_digits=18, decimal_places=3, default=0
    )

    # Разница и её стоимость — как их посчитал учёт (`correctionAmount`
    # и `correctionSum`), а не нами из двух полей выше. Почему — в шапке файла.
    correction_amount = models.DecimalField(
        "Расхождение", max_digits=18, decimal_places=3, default=0
    )
    correction_sum_kopecks = models.BigIntegerField(
        "Расхождение, копейки", default=0
    )

    # Цена — удельная величина в копейках, как у позиции документа: деление
    # на 100 при записи вытеснило бы значащие знаки из дробной части.
    price_kopecks = models.DecimalField(
        "Цена за единицу, копейки", max_digits=18, decimal_places=6, default=0
    )

    class Meta:
        verbose_name = "Позиция инвентаризации"
        verbose_name_plural = "Позиции инвентаризаций"
        indexes = [
            models.Index(fields=["inventory", "product"]),
            models.Index(fields=["product"]),
        ]

    def __str__(self) -> str:
        return f"{self.product}: {self.calculated} → {self.counted}"
