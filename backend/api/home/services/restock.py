"""Что заказать у поставщика — доведённое до решения, а не до тревоги.

**«8 позиций сырья кончится за 30 дней» — это ещё не ответ.** Чтобы заказать,
нужны три вещи: сколько, у кого и почём. Продуктовый проход показал, что
ни одной из них на главной нет: человек видит тревогу и идёт собирать
недостающее руками по трём страницам.

Здесь всё три считаются рядом с самим сигналом:

- **сколько** — расход в день × горизонт минус свободный остаток;
- **у кого и почём** — последняя закупка (`core/services/purchase_prices.py`);
- **успеет ли** — медиана срока поставки у этого поставщика
  (`core/services/lead_time.py`).

**Срок нужен не для красоты.** «Хватит на 4 дня» при поставке в 8 дней —
это уже опоздание, и на экране это должно читаться иначе, чем «хватит
на 4 дня» у поставщика, который возит за сутки.
"""

import math
from dataclasses import dataclass
from decimal import Decimal

from core.models import Document, DocumentKind
from core.services import lead_time
from core.services.documents import alive
from core.services.purchase_prices import last_purchase_prices

# На сколько дней вперёд заказывать. Месяц — тот же горизонт, на котором
# стоит сигнал: смешивать два разных было бы странно, «кончится за 30 дней»
# и «заказать на 45» противоречат друг другу в одной строке.
HORIZON_DAYS = 30


@dataclass(frozen=True)
class Restock:
    """Что и у кого заказать по одной позиции."""

    quantity: Decimal
    uom: str
    cost_kopecks: int | None
    supplier: str
    # Медиана срока поставки у этого поставщика. `None` — связать приёмки
    # с заказами не удалось, и обещать срок нечем.
    lead_days: int | None
    # Успеваем ли: запас больше срока поставки. `False` — заказывать надо
    # было вчера, и это меняет тон строки, а не только её текст.
    in_time: bool | None


def _lead_by_supplier(supplier_ids: set[int]) -> dict[int, int | None]:
    """Медиана срока поставки по каждому поставщику. Один проход по приёмкам.

    По поставщику, а не общая: у «Интернет Решений» забирают сами (медиана
    ноль), а у «Ревады-Невы» ждут три недели. Общая медиана в 1 день
    обещала бы срок, которого у половины закупок не было.
    """
    if not supplier_ids:
        return {}

    supplies = list(
        alive(DocumentKind.SUPPLY)
        .filter(agent_id__in=supplier_ids)
        .select_related("purchase_order")
    )
    by_supplier: dict[int, list[Document]] = {}
    for supply in supplies:
        by_supplier.setdefault(supply.agent_id, []).append(supply)

    result: dict[int, int | None] = {}
    for supplier_id, documents in by_supplier.items():
        span = lead_time.of(documents)
        result[supplier_id] = int(span.days) if span.days is not None else None
    return result


def of(
    rows: list[tuple[int, str, Decimal, Decimal, int | None]],
) -> dict[int, Restock]:
    """Заказ по позициям. На вход — `(id, единица, расход в день, остаток, дней запаса)`.

    Считается пачкой, а не по одной: цены берутся одним запросом на всех,
    сроки — одним проходом по приёмкам. По позиции это было бы два запроса
    на каждую из восьми.
    """
    prices = last_purchase_prices([row[0] for row in rows])
    leads = _lead_by_supplier({price.supplier_id for price in prices.values()})

    result: dict[int, Restock] = {}
    for product_id, uom, per_day, available, days_left in rows:
        # Сколько не хватает до горизонта. Округление вверх и до целого:
        # заказывают штуками и граммами, а не долями, и недозаказать значит
        # вернуться к той же строке через неделю. То же правило,
        # что у `suggested_for` в «Расчёте производства».
        #
        # Целое считается здесь, а не при показе: «заказать ~0 шт» на экране
        # получалось именно из округления готовой дроби 0,4 — строка звала
        # к действию и тут же сообщала, что действия не нужно.
        need = Decimal(
            math.ceil(per_day * HORIZON_DAYS - max(available, Decimal(0)))
        )
        if need <= 0:
            continue

        price = prices.get(product_id)
        lead_days = leads.get(price.supplier_id) if price else None

        result[product_id] = Restock(
            quantity=need,
            uom=uom,
            cost_kopecks=(
                int((need * price.price_kopecks).to_integral_value()) if price else None
            ),
            supplier=price.supplier if price else "",
            lead_days=lead_days,
            # Сравнивается запас со сроком: «хватит на 4 дня» при поставке
            # в 8 — это уже опоздание. `None`, когда одно из двух неизвестно:
            # выдать незнание за «успеваем» здесь дороже всего.
            in_time=(
                None
                if lead_days is None or days_left is None
                else days_left >= lead_days
            ),
        )
    return result


def describe(restock: Restock) -> str:
    """Строка для человека: сколько, у кого, почём и успеваем ли."""
    parts = [f"заказать ~{restock.quantity:,.0f} {restock.uom}".replace(",", " ")]
    if restock.cost_kopecks is not None:
        parts.append(f"≈{restock.cost_kopecks / 100:,.0f} ₽".replace(",", " "))
    if restock.supplier:
        parts.append(restock.supplier)
    if restock.lead_days is not None:
        # Срок называется всегда, а не только когда не успеваем: «везут
        # 8 дней» — это то, из чего человек решает, звонить сегодня или
        # можно на неделе.
        parts.append(f"везут ~{restock.lead_days} дн")
    return " · ".join(parts)


__all__ = ["HORIZON_DAYS", "Restock", "describe", "of"]
