"""Расход сырья на проданное: разворачивание выборки отгрузок по техкартам.

Отдельно от сборки страницы: здесь ответ на вопрос «сколько чего
израсходовано», там — как это показать, сложить в деньги и отсортировать.

**Живёт в `core/`, потому что понадобилось второму разделу.** «Материалы
в приёмках» отвечают на «что закупали», а спрашивают с них «что пора
закупить» — и для этого нужен тот же расход, что считают «Материалы
в отгрузках». Расчёт понадобится и «Расчёту производства».

**Выборку задаёт раздел, а не этот модуль.** Он принимает готовый запрос
позиций отгрузок: у отгрузок есть фильтр по каналу продаж, у приёмок его
нет вовсе, и знать про каналы расчёту незачем. Так же устроены соседи —
`coverage.of` и `lead_time.of`.

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
from decimal import Decimal

from django.db.models import DecimalField, QuerySet, Sum, Value
from django.db.models.functions import Coalesce

from core.models import DocumentPosition, Product, ProductKind
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


def sold(positions: QuerySet[DocumentPosition]) -> list[dict]:
    """Проданные наименования, свёрнутые по товару."""
    return list(
        positions.values("product_id")
        .annotate(
            quantity=Coalesce(Sum("quantity"), Value(Decimal(0)), output_field=_QUANTITY),
            revenue_kopecks=Coalesce(Sum("total_kopecks"), Value(0)),
        )
        .order_by("product_id")
    )


def of_shipments(positions: QuerySet[DocumentPosition]) -> Consumption:
    """Развернуть всё проданное из этой выборки до сырья."""
    rows = sold(positions)
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
        documents_count=_documents_count(positions),
    )


def _documents_count(positions: QuerySet[DocumentPosition]) -> int:
    """Сколько отгрузок попало в выборку. Считает база, а не сумма по строкам.

    Одна отгрузка содержит несколько позиций, и сложить их по товарам значило бы
    посчитать её столько раз, сколько в ней наименований.
    """
    return positions.values("document_id").distinct().count()
