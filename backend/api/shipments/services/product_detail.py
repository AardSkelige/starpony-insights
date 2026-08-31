"""Детали одного товара: по каким каналам ушёл, в каких документах, что на складе.

Отдельным запросом, а не полем в списке: разбивка по девяти каналам и десять
последних документов на каждую из шестидесяти шести строк — это шестьсот
лишних строк в ответе, из которых человек посмотрит одну.

Фильтры применяются те же, что к таблице: детали объясняют **ту строку,
которую видно**, и обязаны сходиться с её числами.
"""

from decimal import Decimal

from django.db.models import Count, DecimalField, Sum, Value
from django.db.models.functions import Coalesce

from api.common import timeline
from api.shipments.services.products import Filters, positions
from core.services.stock import stock_of

# Сколько контрагентов показать поимённо. Остальные — строкой «ещё N»,
# как у распределения расхода на соседней странице: хвост сворачивается,
# но не выбрасывается, иначе слагаемые не складываются в заголовок блока.
AGENT_LIMIT = 5

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


def free_recipients(filters: Filters, product_id: int) -> dict | None:
    """Кому товар уходил бесплатно. `None` — таких отгрузок не было.

    На боевых данных даром ушло 532 штуки из 2369 — почти четверть всего
    выпуска. Колонка это число показывала, но не отвечала «кому», а ответ
    оказался осмысленным: конные клубы, фонд, центры реабилитации лошадей
    и внутренние операции. Это спонсорство, а не потеря, и его надо видеть.
    """
    return _recipients(
        positions(filters).filter(product_id=product_id, total_kopecks=0)
    )


def buyers(filters: Filters, product_id: int) -> dict | None:
    """Кому товар продавали — крупнейшие покупатели. `None` — продаж не было.

    Заменило журнал последних отгрузок. Тот отвечал на «кому и когда» списком
    из десяти строк — при том что у ходового товара отгрузок 109, и по строке
    «00278 · Ложис Софья · 1 шт» решение не принимают. «Кто берёт больше
    всех» — вопрос, на который отвечают, и полоса отвечает на него длиной.

    Бесплатные отгрузки сюда не входят: у них свой блок, а смешай их
    с покупателями — «КСК Отрада» встал бы в список крупных клиентов
    с выручкой ноль.
    """
    return _recipients(
        positions(filters).filter(product_id=product_id).exclude(total_kopecks=0)
    )


def _recipients(queryset) -> dict | None:
    """Контрагенты выборки с количествами: крупнейшие поимённо, хвост строкой.

    Один расчёт на покупателей и на получателей бесплатного — отличается
    только выборка, которую передаёт вызывающий. Две копии разошлись бы
    на первом же уточнении: например, считать ли отгрузку, где товар
    и продали, и доложили бесплатно.

    **Группируется по идентификатору, а не по названию.** `Counterparty.name`
    не уникален — ни в модели, ни в самом МойСкладе: два «ИП Иванов» там
    заводятся спокойно. Сгруппируй мы по имени, их отгрузки слиплись бы
    в одну строку, и количество, выручка, число документов и сам состав
    первой пятёрки оказались бы неверны. В аккаунте дублей сейчас нет —
    все 104 имени уникальны, — и потому ошибка была бы тихой.
    """
    rows = list(
        queryset.values("document__agent_id", "document__agent__name")
        .annotate(
            quantity=Coalesce(Sum("quantity"), Value(Decimal(0)), output_field=_QUANTITY),
            revenue_kopecks=Coalesce(Sum("total_kopecks"), Value(0)),
            documents_count=Count("document", distinct=True),
        )
        .order_by("-quantity")
    )
    if not rows:
        return None

    shown = rows[:AGENT_LIMIT]
    rest = rows[AGENT_LIMIT:]
    notes = _notes_by_agent(queryset, [row["document__agent_id"] for row in shown])
    return {
        "agents": [
            {
                # Идентификатор уходит на фронт как ключ списка: по имени
                # React считал бы двух разных контрагентов одной строкой.
                "agent_id": row["document__agent_id"],
                "name": row["document__agent__name"],
                # Комментарии заказов — то самое «зачем». Пишутся людьми
                # живым языком, и потому не раскладываются по категориям:
                # «на призы на ЧР-2026 по конкуру» человек прочтёт быстрее,
                # чем поймёт код справочника.
                "notes": notes.get(row["document__agent_id"], []),
                "quantity": row["quantity"],
                "revenue_kopecks": row["revenue_kopecks"],
                "documents_count": row["documents_count"],
            }
            for row in shown
        ],
        "rest_agents_count": len(rest),
        "rest_quantity": sum((row["quantity"] for row in rest), Decimal(0)),
        "quantity": sum((row["quantity"] for row in rows), Decimal(0)),
    }


def _notes_by_agent(queryset, agent_ids: list[int]) -> dict[int, list[str]]:
    """Комментарии заказов, по одному набору на контрагента.

    **Комментарий берётся из заказа, а не из отгрузки.** В отгрузке пишут про
    накладные расходы («самовывоз», «доставку оплачивал получатель»), а зачем
    товар ушёл — пишут в заказе, из которого она выросла. Проверено на боевых:
    у всех 53 отгрузок с нулевой ценой заказ есть, и комментарий тоже.

    Повторы схлопываются: три отгрузки одного заказа несут один текст.
    """
    if not agent_ids:
        return {}

    rows = (
        queryset.filter(document__agent_id__in=agent_ids)
        .exclude(document__customer_order__description="")
        .values("document__agent_id", "document__customer_order__description")
        .distinct()
    )

    collected: dict[int, list[str]] = {}
    for row in rows:
        note = (row["document__customer_order__description"] or "").strip()
        if not note:
            continue
        bucket = collected.setdefault(row["document__agent_id"], [])
        if note not in bucket:
            bucket.append(note)
    return collected


def detail(filters: Filters, product_id: int) -> dict:
    """Всё про товар в контексте выбранных фильтров."""
    if not positions(filters).filter(product_id=product_id).exists():
        raise ProductNotSold()

    return {
        "channels": channels(filters, product_id),
        # Журнал последних отгрузок заменён двумя ответами: **когда** продавали
        # и **кому**. Список из десяти строк не отвечал ни на один вопрос,
        # а сто девять строк в панель не помещаются.
        "timeline": timeline.of(
            positions(filters).filter(product_id=product_id),
            date_from=filters.date_from,
            date_to=filters.date_to,
        ),
        "buyers": buyers(filters, product_id),
        "free": free_recipients(filters, product_id),
        "stock": stock_of(product_id),
    }
