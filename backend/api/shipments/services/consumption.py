"""Расход сырья на проданное: разворачивание выборки отгрузок по техкартам.

Отдельно от сборки страницы: здесь ответ на вопрос «сколько чего
израсходовано», там — как это показать, сложить в деньги и отсортировать.
Разворачивание понадобится и раскрытию строки, и, позже, расчёту производства.

Считается в два шага. Сначала позиции отгрузок сворачиваются по товару —
это Postgres. Потом каждое проданное наименование разворачивается по
техкартам до сырья — это Python: рекурсия по составу в SQL не выражается,
а наименований за полгода шестьдесят шесть, и весь расчёт занимает 22 мс.

**Пять наименований из шестидесяти шести техкарты не имеют** — четыре вида
доставки и картонный короб, проданный отдельной строкой. Развернуть их не во
что, и `explode` вернул бы их самих: доставка встала бы в список материалов
наравне с водой. Поэтому они отобраны заранее и уходят отдельным списком —
не спрятаны, но и не смешаны с сырьём.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.db.models import Count, DecimalField, Sum, Value
from django.db.models.functions import Coalesce

from api.shipments.services import selection
from core.models import Product, ProductKind
from core.services.materials import explode, plans_by_product

_QUANTITY = DecimalField(max_digits=18, decimal_places=3)


@dataclass
class Consumed:
    """Сколько одного материала ушло и из каких изделий пришло."""

    product: Product
    quantity: Decimal = Decimal(0)
    # Изделие → сколько материала пришло от него. Это и объяснение числа,
    # и «из скольких наименований» в строке таблицы.
    sources: dict[int, Decimal] = field(default_factory=dict)


@dataclass
class Consumption:
    """Результат разворачивания всей выборки."""

    materials: list[Consumed]
    # Проданное, что развернуть не во что: услуги и покупные товары без техкарт.
    without_plan: list[dict]
    exploded_count: int
    revenue_kopecks: int
    documents_count: int


def sold(
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    channel_id: int | None = None,
) -> list[dict]:
    """Проданные наименования, свёрнутые по товару."""
    return list(
        selection.shipment_positions(
            date_from=date_from, date_to=date_to, channel_id=channel_id
        )
        .values("product_id")
        .annotate(
            quantity=Coalesce(Sum("quantity"), Value(Decimal(0)), output_field=_QUANTITY),
            revenue_kopecks=Coalesce(Sum("total_kopecks"), Value(0)),
        )
        .order_by("product_id")
    )


def of_shipments(
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    channel_id: int | None = None,
) -> Consumption:
    """Развернуть всё проданное за период до сырья."""
    rows = sold(date_from=date_from, date_to=date_to, channel_id=channel_id)
    plans = plans_by_product()
    products = {
        product.pk: product
        for product in Product.objects.select_related("uom").filter(
            pk__in=[row["product_id"] for row in rows]
        )
    }

    collected: dict[int, Consumed] = {}
    without_plan: list[dict] = []
    exploded = 0

    for row in rows:
        product = products[row["product_id"]]

        if product.pk not in plans:
            without_plan.append(
                {
                    "product_id": product.pk,
                    "name": product.name,
                    "article": product.article,
                    "code": product.code,
                    "uom": product.uom.name if product.uom else "",
                    "is_service": product.kind == ProductKind.SERVICE,
                    "quantity": row["quantity"],
                    "revenue_kopecks": row["revenue_kopecks"],
                }
            )
            continue

        exploded += 1
        for need in explode(product, row["quantity"], plans=plans):
            entry = collected.setdefault(need.product.pk, Consumed(need.product))
            entry.quantity += need.quantity
            entry.sources[product.pk] = (
                entry.sources.get(product.pk, Decimal(0)) + need.quantity
            )

    return Consumption(
        materials=list(collected.values()),
        without_plan=without_plan,
        exploded_count=exploded,
        revenue_kopecks=sum(row["revenue_kopecks"] for row in rows),
        documents_count=_documents_count(date_from, date_to, channel_id),
    )


def _documents_count(
    date_from: date | None, date_to: date | None, channel_id: int | None
) -> int:
    """Сколько отгрузок попало в выборку. Считает база, а не сумма по строкам.

    Одна отгрузка содержит несколько позиций, и сложить их по товарам значило бы
    посчитать её столько раз, сколько в ней наименований.
    """
    return (
        selection.shipment_positions(
            date_from=date_from, date_to=date_to, channel_id=channel_id
        )
        .values("document_id")
        .distinct()
        .count()
    )
