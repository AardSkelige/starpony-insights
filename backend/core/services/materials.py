"""Расчёт сырья по технологическим картам.

Общая доменная логика: на ней стоят и «Материалы в отгрузках», и «Расчёт
производства». Держать её в одном из разделов API значило бы, что второй
раздел импортирует чужой код или заводит свою копию — и копии разъедутся.

Главное здесь — разворачивание цепочки. Производство идёт в два шага:
сырьё → полуфабрикат («замес») → готовый товар («розлив»). Прямой состав
техкарты розлива покажет полуфабрикат, а закупают не его. Поэтому состав
раскрывается рекурсивно до того, что действительно покупают.
"""

import logging
from dataclasses import dataclass, field
from decimal import Decimal

from core.models import ProcessingPlan, Product

# Предел вложенности. В боевых данных максимум два уровня, но техкарты правят
# люди, и «А делается из Б, Б делается из А» рано или поздно случится.
# Без предела это зависание синхронизации или страницы, а не сообщение об ошибке.
MAX_DEPTH = 10

logger = logging.getLogger(__name__)


class CircularBillOfMaterials(RuntimeError):
    """Техкарты ссылаются друг на друга по кругу."""


@dataclass
class MaterialNeed:
    """Сколько одного материала нужно и откуда это следует."""

    product: Product
    quantity: Decimal
    # Пути, по которым пришли к материалу, — список цепочек техкарт.
    # Именно список: один материал попадает в изделие несколькими путями
    # (вода входит и в замес, и в розлив), и показать только первый значит
    # объяснить лишь часть числа.
    via: list[list[str]] = field(default_factory=list)


def plans_by_product() -> dict[int, ProcessingPlan]:
    """Что чем производится. Один запрос вместо обращения на каждом шаге.

    Архивные техкарты исключены: убранная в архив карта описывает то, как
    делали раньше. Оставить её — считать закупку по устаревшему составу.

    Порядок задан явно, потому что на один товар может быть несколько карт:
    побеждает самая свежая. Без сортировки выбор зависел бы от порядка строк
    в базе и менялся между прогонами без всякого признака.
    """
    plans = (
        ProcessingPlan.objects.alive()
        .filter(archived=False)
        .select_related("product")
        .prefetch_related("materials__product", "materials__uom")
        .order_by("product_id", "-ms_updated")
    )

    chosen: dict[int, ProcessingPlan] = {}
    for plan in plans:
        if plan.product_id in chosen:
            logger.warning(
                "У товара «%s» несколько действующих техкарт. Считаем по «%s», "
                "игнорируем «%s».",
                plan.product.name, chosen[plan.product_id].name, plan.name,
            )
            continue
        chosen[plan.product_id] = plan
    return chosen


def explode(
    product: Product,
    quantity: Decimal,
    *,
    plans: dict[int, ProcessingPlan] | None = None,
) -> list[MaterialNeed]:
    """Развернуть изделие до сырья.

    Возвращает список того, что нужно закупить или взять со склада, —
    без полуфабрикатов: они раскрыты до своего состава.
    """
    plans = plans_by_product() if plans is None else plans
    collected: dict[int, MaterialNeed] = {}

    def walk(current: Product, needed: Decimal, depth: int, trail: list[str]) -> None:
        if depth > MAX_DEPTH:
            raise CircularBillOfMaterials(
                f"Техкарты ссылаются по кругу: {' → '.join(trail)}. "
                f"Проверьте состав в МойСкладе."
            )

        plan = plans.get(current.pk)
        if plan is None:
            # Товар ничем не производится — это и есть то, что закупают.
            entry = collected.get(current.pk)
            if entry is None:
                collected[current.pk] = MaterialNeed(current, needed, [list(trail)])
            else:
                entry.quantity += needed
                if trail and list(trail) not in entry.via:
                    entry.via.append(list(trail))
            return

        # Расход на единицу продукции: техкарта описывает объём выпуска,
        # который не обязан быть единицей.
        for material in plan.materials.all():
            per_unit = material.quantity / plan.output_quantity
            walk(
                material.product,
                needed * per_unit,
                depth + 1,
                trail + [plan.name],
            )

    walk(product, quantity, 0, [])
    return sorted(collected.values(), key=lambda need: need.product.name)


def direct_materials(
    product: Product, *, plans: dict[int, ProcessingPlan] | None = None
) -> list[MaterialNeed]:
    """Прямой состав на единицу — без разворачивания полуфабрикатов.

    Нужен там, где показывают саму техкарту, а не потребность в сырье.
    """
    plans = plans_by_product() if plans is None else plans
    plan = plans.get(product.pk)
    if plan is None:
        return []

    return [
        MaterialNeed(
            material.product,
            material.quantity / plan.output_quantity,
            [[plan.name]],
        )
        for material in plan.materials.all()
    ]
