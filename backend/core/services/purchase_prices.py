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
from decimal import ROUND_HALF_UP, Decimal
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
    # Кто продал — идентификатором, а не только именем. По нему считается срок
    # поставки: «не хватает 3867 г, везут восемь дней» — это ответ, а «не хватает
    # 3867 г» отправляет человека искать поставщика на соседнюю страницу.
    supplier_id: int


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
            supplier_id=row.document.agent_id,
        )
        for row in rows
    }


# Копейка — предел точности денег в учёте. Цена за единицу дробная (ДЭТА
# стоит 4,8 копейки за грамм), но заплаченная сумма целая.
_KOPECK = Decimal("1")


def cost_of(quantity: Decimal, price: PurchasePrice | None) -> int | None:
    """Стоимость количества по этой цене, целыми копейками. `None` — цены нет.

    Живёт рядом с ценой, а не у страницы: «Материалы в отгрузках» считают
    так стоимость израсходованного, «Расчёт производства» — стоимость
    докупки недостающего. Вопрос разный, арифметика одна, и вторая копия
    разошлась бы на округлении — то есть на копейках в итоге, ровно там,
    где человек проверяет сложением.

    Округляется здесь, а не в подвале: итог собирается сложением того, что
    показано в колонке, и без этого расходился бы с ней.

    Ноль вместо `None` не годится: он читался бы как «материал достался
    даром», а на деле его просто ни разу не покупали. Таких три из ста
    шестидесяти одного, и все — доли грамма.
    """
    if price is None:
        return None
    return int(
        (quantity * price.price_kopecks).quantize(_KOPECK, rounding=ROUND_HALF_UP)
    )
