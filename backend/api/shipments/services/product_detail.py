"""Детали одного товара: по каким каналам ушёл, в каких документах, что на складе.

Отдельным запросом, а не полем в списке: разбивка по девяти каналам и десять
последних документов на каждую из шестидесяти шести строк — это шестьсот
лишних строк в ответе, из которых человек посмотрит одну.

Фильтры применяются те же, что к таблице: детали объясняют **ту строку,
которую видно**, и обязаны сходиться с её числами.
"""

from decimal import Decimal

from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce

from api.shipments.services.products import Filters, positions
from core.services.stock import stock_of

# Сколько документов показать. Полный список — отдельная задача со своей
# страницей: десять последних отвечают на вопрос «кому и когда», а тысяча
# строк в выдвижной панели не отвечает ни на один.
DOCUMENT_LIMIT = 10

_QUANTITY = DecimalField(max_digits=18, decimal_places=3)


class ProductNotSold(Exception):
    """Товар не встречается в выборке — деталям неоткуда взяться."""


def channels(filters: Filters, product_id: int) -> list[dict]:
    """Сколько этого товара ушло по каждому каналу.

    Отсортировано по количеству: полосы читаются сверху вниз, и порядок
    сам отвечает на вопрос «какой канал главный».
    """
    rows = (
        positions(filters)
        .filter(product_id=product_id)
        .values("document__sales_channel_id", "document__sales_channel__name")
        .annotate(
            quantity=Coalesce(Sum("quantity"), Value(Decimal(0)), output_field=_QUANTITY),
            revenue_kopecks=Coalesce(Sum("total_kopecks"), Value(0)),
        )
        .order_by("-quantity")
    )
    return [
        {
            # Канал может быть не проставлен — на боевых данных это одна
            # отгрузка из 294. Молча выбросить её значит потерять штуки,
            # которые в итоге строки посчитаны.
            "id": row["document__sales_channel_id"],
            "name": row["document__sales_channel__name"] or "Без канала",
            "quantity": row["quantity"],
            "revenue_kopecks": row["revenue_kopecks"],
        }
        for row in rows
    ]


def documents(filters: Filters, product_id: int) -> list[dict]:
    """Последние отгрузки с этим товаром — кому, когда, сколько."""
    rows = (
        positions(filters)
        .filter(product_id=product_id)
        .select_related("document", "document__agent")
        .order_by("-document__moment", "-id")[:DOCUMENT_LIMIT]
    )
    return [
        {
            "number": row.document.number,
            "moment": row.document.moment,
            "agent": row.document.agent.name,
            "quantity": row.quantity,
            "total_kopecks": row.total_kopecks,
        }
        for row in rows
    ]


def detail(filters: Filters, product_id: int) -> dict:
    """Всё про товар в контексте выбранных фильтров."""
    if not positions(filters).filter(product_id=product_id).exists():
        raise ProductNotSold()

    return {
        "channels": channels(filters, product_id),
        "documents": documents(filters, product_id),
        "stock": stock_of(product_id),
    }
