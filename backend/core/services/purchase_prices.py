"""Цена последней закупки — по документам приёмок, а не по карточке товара.

Общая доменная логика: на ней стоят и «Материалы в отгрузках», и будущие
«Материалы в приёмках» с «Поставщиками». Держать её в одном из разделов API
значило бы, что второй импортирует чужой код или заводит свою копию.

**Почему не карточка товара.** У `Product.buy_price_kopecks` цена заполнена
у 42 наименований из 161 участвующих в расчёте, и у 152 товаров она разошлась
с тем, что заплатили: отдушка «Лесные ягоды» — 790 копеек в карточке против
493,75 в последней приёмке. Документ приёмки — факт с датой и номером,
карточка — намерение, которое правят не всегда.

**Почему не себестоимость остатка.** `Stock.cost_kopecks` известна по 96
наименованиям из 161. По тем, где известны обе, суммы сходятся в пределах
0,3% — так что выбор решается покрытием и тем, что цена из документа умеет
себя объяснить: «приёмка №00047 от 15.06.2026».
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Iterable

from core.models import DocumentKind, DocumentPosition


@dataclass(frozen=True)
class PurchasePrice:
    """Сколько за единицу заплатили в последний раз — и по какому документу."""

    # В копейках, как приходит из учёта, и дробная: делить на 100 при записи
    # значит вытеснить значащие знаки — см. DocumentPosition.price_kopecks.
    price_kopecks: Decimal
    moment: datetime
    document_number: str
    supplier: str


def last_purchase_prices(
    product_ids: Iterable[int] | None = None,
) -> dict[int, PurchasePrice]:
    """Последняя цена закупки по каждому товару. Один запрос на всех.

    Нулевые цены пропускаются: в боевых данных 97 позиций приёмок из 402
    пришли по нулю — образцы, бонусы поставщика и корректировки. Взять такую
    за последнюю цену значит обнулить стоимость материала целиком, и число
    просто исчезнет с экрана без единого признака, что оно потеряно.
    """
    queryset = DocumentPosition.objects.filter(
        document__kind=DocumentKind.SUPPLY,
        document__deleted_at__isnull=True,
        document__applicable=True,
        price_kopecks__gt=0,
    )
    if product_ids is not None:
        queryset = queryset.filter(product_id__in=list(product_ids))

    # DISTINCT ON — по одной строке на товар, ту, что сверху в сортировке.
    # Порядок задан до конца: у двух приёмок бывает один момент, и без `-id`
    # выбор между ними менялся бы между запросами без всякого признака.
    rows = (
        queryset.select_related("document", "document__agent")
        .order_by("product_id", "-document__moment", "-id")
        .distinct("product_id")
    )

    return {
        row.product_id: PurchasePrice(
            price_kopecks=row.price_kopecks,
            moment=row.document.moment,
            document_number=row.document.number,
            supplier=row.document.agent.name,
        )
        for row in rows
    }
