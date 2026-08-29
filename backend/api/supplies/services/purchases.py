"""Закупка — это документ, а не строка в нём.

Единица счёта всего раздела. «Закупок 5» должно значить пять приёмок,
а цена закупки — то, что заплатили за единицу по этому документу.

**Почему не позиция.** Один и тот же материал приходит в одной приёмке
двумя строками: диметилфталат 10.03.2026 пришёл двумя партиями — 2000 г
по 40 копеек и 3000 г по 45. Считай мы позициями, у него оказалось бы шесть
«закупок» вместо пяти, а в динамике цен появился бы скачок 40 → 45 внутри
одного дня у одного поставщика — движение, которого не было.

**Нулевая цена — не цена, а признак.** 97 позиций из 402 пришли по нулю:
образцы, бонусы и допечатка этикеток от «Принтеца». Материал при этом
на склад поступил, и в количество он входит; в цену — нет. Взять ноль
за цену значит обнулить и среднюю, и динамику: у этикетки Табак-Ваниль
280 штук из 496 пришли даром, и средняя цена «сумма ÷ всё количество»
занизилась бы вдвое.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Iterable

from core.models import DocumentPosition


@dataclass
class Purchase:
    """Один материал в одной приёмке: сколько пришло и во сколько обошлось."""

    document_id: int
    number: str
    moment: datetime
    supplier_id: int
    supplier: str

    quantity: Decimal = Decimal(0)
    amount_kopecks: int = 0
    # Единицы, в которых материал пришёл этим документом. Множество, а не
    # строка: приди он килограммами там, где техкарта в граммах, ошибка
    # составит ровно тысячу раз и на глаз останется незаметной.
    uoms: set[str] = field(default_factory=set)

    @property
    def price_kopecks(self) -> Decimal | None:
        """Цена за единицу по этому документу. `None` — пришло даром.

        Средневзвешенная, если строк было несколько: 2000 г по 40 и 3000 г
        по 45 дают 43 копейки за грамм — ровно то, что заплатили за партию.
        """
        if self.amount_kopecks <= 0 or self.quantity <= 0:
            return None
        return Decimal(self.amount_kopecks) / self.quantity

    @property
    def is_free(self) -> bool:
        return self.amount_kopecks <= 0


def by_material(positions: Iterable[DocumentPosition]) -> dict[int, list[Purchase]]:
    """Закупки каждого материала, от старой к новой.

    Порядок задан до конца: у двух приёмок бывает один момент, и без
    `document_id` соседство в истории менялось бы между запросами —
    а «предыдущая цена» считается именно по соседству.

    Позиции приходят уже отобранными и с подтянутыми связями: раздел делает
    один запрос на всю страницу, а группировка стоит одного прохода по нему.
    """
    grouped: dict[int, dict[int, Purchase]] = defaultdict(dict)

    for position in positions:
        document = position.document
        purchases = grouped[position.product_id]

        purchase = purchases.get(document.pk)
        if purchase is None:
            purchase = Purchase(
                document_id=document.pk,
                number=document.number,
                moment=document.moment,
                supplier_id=document.agent_id,
                supplier=document.agent.name,
            )
            purchases[document.pk] = purchase

        purchase.quantity += position.quantity
        purchase.amount_kopecks += position.total_kopecks
        if position.uom_id:
            purchase.uoms.add(position.uom.name)

    return {
        product_id: sorted(
            purchases.values(), key=lambda item: (item.moment, item.document_id)
        )
        for product_id, purchases in grouped.items()
    }


def priced(purchases: Iterable[Purchase]) -> list[Purchase]:
    """Только те закупки, у которых есть цена. Порядок сохраняется."""
    return [item for item in purchases if not item.is_free]
