"""Страница «Каналы продаж»: где продаём и сколько это приносит.

Строка — канал, слагаемые строки — его отгрузки. Числа отвечают на разные
вопросы, и ни одно не заменяет другое: выручка — «сколько приносит»,
отгрузки — «сколько раз продали», чек — «сколько обычно за раз»,
покупатели — «канал это площадка или люди».

**Главный вопрос страницы — расхождение первых двух.** Озон даёт 135 отгрузок
из 305 и 17 % выручки, «Точка продаж» — 34 отгрузки и 37 %. Одно и то же
слово «канал» описывает вал мелких заказов и редкие крупные, и таблица,
где эти колонки стоят рядом, отвечает на это без единого расчёта.

**Расчётное число отдаётся составляющими, а не готовым текстом.** Медиана
чека приходит вместе с разбросом и средним, из которых получена: у «Точки
продаж» среднее 13 766 ₽ против медианы 2 772 ₽, и само это расхождение —
ответ на вопрос, чем канал держится.
"""

from api.channels.services import (
    breakdown,
    dynamics,
    palette,
    receipt,
    selection,
    summary,
)
from api.common.selection import page_bounds
from core.money import share
from core.services import consignment
from core.services.documents import positions_in

# Сортировки, разрешённые снаружи. Список закрытый — как у соседних страниц.
ORDERING = (
    "revenue", "-revenue",
    "name", "-name",
    "shipments", "-shipments",
    "receipt", "-receipt",
    "buyers", "-buyers",
    "products", "-products",
    "last", "-last",
)
DEFAULT_ORDERING = "-revenue"

Filters = selection.Filters


def row_of(
    channel_id: int,
    name: str,
    slot: int | None,
    shipments: list,
    positions: list,
    scale: dynamics.Scale,
) -> dict:
    """Строка таблицы вместе с составляющими своих расчётных чисел."""
    moments = sorted(shipment.moment for shipment in shipments)
    cheque = receipt.of(shipments)

    return {
        "channel_id": channel_id,
        "name": name,
        # Номер цвета в палитре. Закреплён за каналом, а не за его местом
        # в списке: сортировка не должна перекрашивать графики.
        "slot": slot,

        "shipments_count": len(shipments),
        "revenue_kopecks": sum(shipment.total_kopecks for shipment in shipments),

        # Сколько из выручки канала — товар на реализации, а не продажа.
        # У «Точки продаж» это 87 %, у Telegram 97 %: вывод «канал приносит
        # больше всех» без этого числа держится на складе комиссионера.
        "consignment": _consignment_of(shipments),

        "first_moment": moments[0],
        "last_moment": moments[-1],

        "receipt": cheque,

        "buyers_count": len({shipment.agent_id for shipment in shipments}),
        "products_count": len({position.product_id for position in positions}),

        # Кто и что именно. До сих пор на «кому продали через этот канал»
        # ответить было нечем: приходилось идти на страницу отгрузок
        # и фильтровать её по каналу.
        "buyers": breakdown.buyers(shipments),
        "products": breakdown.products(positions),

        # Выручка канала по тем же корзинам, что и стопка наверху страницы:
        # разбор строки показывает ряд одного канала, и границы столбиков
        # у них обязаны совпадать.
        "dynamics": dynamics.line(shipments, scale),

        # Для итога по показанным строкам: сложить `buyers_count` нельзя,
        # один покупатель приходит через несколько каналов и был бы посчитан
        # дважды. В ответ не уходит.
        "agent_ids": {shipment.agent_id for shipment in shipments},
        "product_ids": {position.product_id for position in positions},
    }



def _matches(row: dict, term: str) -> bool:
    """Поиск по названию канала. Больше искать здесь не по чему: у канала
    в учёте есть только имя и тип."""
    return term.strip().casefold() in row["name"].casefold()


# По чему сравнивают строки для каждого разрешённого ключа сортировки.
_SORT_KEYS = {
    "revenue": lambda row: row["revenue_kopecks"],
    "shipments": lambda row: row["shipments_count"],
    "receipt": lambda row: row["receipt"].kopecks,
    "buyers": lambda row: row["buyers_count"],
    "products": lambda row: row["products_count"],
    "last": lambda row: row["last_moment"],
    "name": lambda row: row["name"].casefold(),
}


def _sorted(rows: list[dict], ordering: str) -> list[dict]:
    """Порядок показа. Строки, которым сортировать нечем, всегда внизу.

    Прочерк у чека значит «отгрузок не было вовсе», и такие строки идут
    отдельным списком, а не хитрым ключом: переворот направления иначе
    поднял бы их наверх, и список «где чек крупнее» начинался бы с каналов,
    где не продавали.

    Ничьи разрешает `channel_id`: без него каналы с равной выручкой шли бы
    в порядке, который не обязан повторяться между запросами.
    """
    if ordering not in ORDERING:
        ordering = DEFAULT_ORDERING
    desc = ordering.startswith("-")
    key = _SORT_KEYS[ordering.lstrip("-")]

    known = [row for row in rows if key(row) is not None]
    unknown = [row for row in rows if key(row) is None]

    known.sort(key=lambda row: (key(row), row["channel_id"]), reverse=desc)
    unknown.sort(key=lambda row: row["channel_id"])
    return known + unknown


def prepared(filters: Filters) -> dict:
    """Все строки выборки, оба набора итогов и ряд по времени.

    Отдельно от `page`, потому что выгрузке нужны **все** строки: отгрузки
    читаются одним запросом, и делать его дважды — ради страницы и ради
    файла — незачем.
    """
    shipments = list(
        selection.demands(date_from=filters.date_from, date_to=filters.date_to)
    )
    positions = list(
        positions_in(
            selection.demands(date_from=filters.date_from, date_to=filters.date_to)
        ).select_related("document", "product")
    )
    slots = palette.slots()

    by_channel: dict[int, list] = {}
    names: dict[int, str] = {}
    for shipment in shipments:
        # Отгрузка без канала строкой не становится: канала, к которому её
        # отнести, в учёте нет. Она остаётся в сводке — там видно, сколько
        # учёт недосчитал таблице.
        if shipment.sales_channel_id is None:
            continue
        by_channel.setdefault(shipment.sales_channel_id, []).append(shipment)
        names[shipment.sales_channel_id] = shipment.sales_channel.name

    positions_by_channel: dict[int, list] = {}
    for position in positions:
        channel_id = position.document.sales_channel_id
        if channel_id is None:
            continue
        positions_by_channel.setdefault(channel_id, []).append(position)

    scale = dynamics.scale(
        shipments, date_from=filters.date_from, date_to=filters.date_to
    )

    everything = [
        row_of(
            channel_id,
            names[channel_id],
            slots.get(channel_id),
            items,
            positions_by_channel.get(channel_id, []),
            scale,
        )
        for channel_id, items in by_channel.items()
    ]

    # Доля канала считается от выручки **всей** выборки, а не найденного:
    # иначе после поиска «озон» его доля показала бы 100 %, хотя на Озон
    # приходится шестая часть продаж.
    selection_revenue = sum(row["revenue_kopecks"] for row in everything)
    for row in everything:
        row["revenue_share"] = share(row["revenue_kopecks"], selection_revenue)

    unassigned = [
        shipment for shipment in shipments if shipment.sales_channel_id is None
    ]
    whole = {
        "shipments_count": len(shipments),
        "revenue_kopecks": sum(shipment.total_kopecks for shipment in shipments),
        "unassigned_shipments_count": len(unassigned),
        "unassigned_revenue_kopecks": sum(
            shipment.total_kopecks for shipment in unassigned
        ),
        "buyers_count": len({shipment.agent_id for shipment in shipments}),
        "products_count": len({position.product_id for position in positions}),
    }

    rows = everything
    if filters.search:
        rows = [row for row in everything if _matches(row, filters.search)]

    return {
        # Расстановка каналов — для полос над таблицей. Считается по всей
        # выборке и **до** поиска, как сводка и стопка: полосы отвечают
        # на «кому уходят деньги у нас», а не «среди найденного». И до
        # нарезки на страницы: восьмой канал не перестаёт существовать
        # оттого, что не поместился на первый экран.
        "standings": _standings(everything),
        # Итог под таблицей — про то, что в ней видно: он обязан сходиться
        # со сложением колонки при любом поиске.
        "totals": summary.table_totals(rows, selection_revenue),
        # Сводка — про выборку отгрузок целиком, вместе с теми, у кого канала
        # нет. Поиск её не трогает.
        "coverage": summary.coverage(everything, whole),
        # Стопка строится по всей выборке, а не по найденному: она отвечает
        # на «как менялось у нас», и поиск по названию канала не обязан
        # переписывать историю продаж.
        "dynamics": dynamics.of(
            shipments,
            scale,
            date_from=filters.date_from,
            date_to=filters.date_to,
            slots=slots,
        ),
        "rows": _sorted(rows, filters.ordering),
    }


def _standings(rows: list[dict]) -> list[dict]:
    """Доля в деньгах против доли в отгрузках — по каналу на строку.

    Две доли рядом и есть главный вопрос страницы: у Озона 44 % отгрузок
    и 17 % денег, у «Точки продаж» 11 % и 37 %. Считаются от одного
    и того же множества — иначе сравнение бессмысленно, а выглядит обычным.
    """
    shipments = sum(row["shipments_count"] for row in rows)
    revenue = sum(row["revenue_kopecks"] for row in rows)
    return [
        {
            "channel_id": row["channel_id"],
            "name": row["name"],
            "slot": row["slot"],
            "revenue_kopecks": row["revenue_kopecks"],
            "revenue_share": share(row["revenue_kopecks"], revenue),
            # Та же оговорка, что в строке таблицы: полосы отвечают на «кто
            # приносит больше», и у «Точки продаж» 87 % её денег — товар,
            # который ещё не продан. Без пометки длина полосы врёт сильнее
            # всего именно здесь, потому что на неё и смотрят первой.
            "consignment": row["consignment"],
            "shipments_count": row["shipments_count"],
            "shipments_share": share(row["shipments_count"], shipments),
        }
        for row in sorted(rows, key=lambda item: -item["revenue_kopecks"])
    ]


def page(filters: Filters) -> dict:
    """Всё, что нужно странице, за три запроса: отгрузки, их строки, слоты."""
    whole = prepared(filters)
    rows = whole["rows"]

    start, end = page_bounds(filters.page, filters.page_size)

    return {
        "count": len(rows),
        "standings": whole["standings"],
        "totals": whole["totals"],
        # Сверка с «Прибыльностью» — **состояние на сегодня, а не итог
        # периода**: отчёт комиссионера приходит позже отгрузки, часто
        # в следующем месяце, и «отгружено за август» против «отчётов
        # за август» сравнивало бы два разных множества (`DESIGN.md` §8).
        #
        # Считается здесь, а не в `prepared`: это карточка экрана, и двух
        # полнотабличных запросов ради выгрузки, где её нет, платить незачем.
        "coverage": {
            **whole["coverage"],
            "consignment_outstanding": consignment.outstanding(),
        },
        "dynamics": whole["dynamics"],
        "results": rows[start:end],
    }


def _consignment_of(shipments: list) -> consignment.Share:
    """Доля реализации в выручке канала.

    Считается в Python, как и вся строка: документы уже загружены,
    и второй запрос ради того же множества был бы тратой. Условие при этом
    общее с «Товарами в отгрузках» (`core.services.consignment`), где
    группировка идёт запросом.
    """
    return consignment.share_of(
        total_kopecks=sum(shipment.total_kopecks for shipment in shipments),
        consignment_kopecks=sum(
            shipment.total_kopecks
            for shipment in shipments
            if consignment.is_consignment(shipment)
        ),
    )
