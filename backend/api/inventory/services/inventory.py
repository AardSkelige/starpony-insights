"""Страница «Инвентаризация»: когда позицию считали и на сколько она не сошлась.

Строка — позиция номенклатуры, а не документ. Список из шести инвентаризаций
человек и так видит в учёте, и переносить его сюда — работа без результата
(`CLAUDE.md` §8.0). Вопрос, на который учёт не отвечает, звучит иначе:
**что не пересчитывали вовсе**. На боевых данных таких позиций 241 из 314,
и 110 из них — сырьё.

**Деньги считаются нами, а не берутся из учёта.** В документах инвентаризации
цена заполнена у 10 позиций из 55 разошедшихся, поэтому `correctionSum`
там нулевой при живой недостаче. Здесь расхождение умножается на
себестоимость из остатков — число расчётное, поэтому уходит вместе со своими
составляющими и сопровождается оговоркой на экране (`CLAUDE.md` §4).
"""

from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone

from api.common.selection import matching, page_bounds
from api.inventory.services.selection import Filters
from core.dates import local_date
from core.models import InventoryPosition
from core.services.catalogue import stocked

# Сортировки, разрешённые снаружи. Список закрытый, как у соседних страниц.
ORDERING = (
    "money", "-money",
    "correction", "-correction",
    "last", "-last",
    "name", "-name",
    "times", "-times",
)
DEFAULT_ORDERING = "-money"


def money_of(correction: Decimal | None, cost_kopecks: Decimal | None) -> int | None:
    """Во что расхождение обходится: штуки × себестоимость, целыми копейками.

    `None` — себестоимости нет (у 14 позиций из 55), и ноль вместо неё
    читался бы как «сошлось», хотя товар пропал. Различать обязательно:
    именно на этом месте учёт и молчит.
    """
    if correction is None or not cost_kopecks:
        return None
    return int((correction * cost_kopecks).to_integral_value(rounding=ROUND_HALF_UP))


def _row(product, positions: list[InventoryPosition], today) -> dict:
    """Строка таблицы: последний пересчёт позиции и его итог.

    Последний, а не суммарный: «числилось 42, нашли 5» — это факт одного дня,
    и складывать такие пары по разным пересчётам значило бы получить число,
    которого не было ни в одном документе.
    """
    stock = getattr(product, "stock", None)
    cost = stock.cost_kopecks if stock else None

    row = {
        "product_id": product.id,
        "name": product.name,
        "article": product.article,
        "folder": product.folder,
        # Единица обязательна рядом с количеством: «числилось 5 730» у спирта
        # это граммы, а у короба — штуки. Ошибка здесь ровно в 1000 раз
        # и на глаз незаметна (`CLAUDE.md` §3).
        "uom": product.uom.name if product.uom else "",
        "counted_times": len(positions),
        "diverged_times": sum(1 for p in positions if p.correction_amount),
        "cost_kopecks": cost or None,
        # Сколько числится сейчас. Нужно ровно для решения «идти считать
        # или нет»: расхождение трёхмесячной давности по позиции, которой
        # на складе нет вовсе, пересчитывать незачем.
        "stock_quantity": stock.quantity if stock else None,
        "last_moment": None,
        "last_store": "",
        "days_ago": None,
        "calculated": None,
        "counted": None,
        "correction": None,
        "correction_money_kopecks": None,
    }
    if not positions:
        return row

    last = max(positions, key=lambda p: p.inventory.moment)
    row.update(
        last_moment=last.inventory.moment,
        last_store=last.inventory.store_name,
        # По местному календарю, а не вычитанием UTC: пересчёт, проведённый
        # до трёх ночи по Москве, иначе оказался бы «вчерашним».
        days_ago=(today - local_date(last.inventory.moment)).days,
        calculated=last.calculated,
        counted=last.counted,
        correction=last.correction_amount,
        correction_money_kopecks=money_of(last.correction_amount, cost),
    )
    return row


# По чему сравнивают строки для каждого разрешённого ключа сортировки.
#
# `money` и `correction` — по модулю: вопрос «где сильнее всего не сошлось»
# не различает недостачу и излишек, а знак несёт само число в колонке.
_SORT_KEYS = {
    "money": lambda row: abs(row["correction_money_kopecks"])
    if row["correction_money_kopecks"] is not None else None,
    "correction": lambda row: abs(row["correction"])
    if row["correction"] is not None else None,
    "last": lambda row: row["days_ago"],
    "name": lambda row: row["name"].casefold(),
    "times": lambda row: row["counted_times"],
}

# «Никогда не считали» при сортировке по давности — не пропуск, а край шкалы.
# Позиция, до которой не дошли ни разу, ждёт дольше любой посчитанной,
# и уехав вниз вместе с прочерками, она пропала бы ровно из того порядка,
# ради которого его и включают.
_NEVER = 10**6


def _sorted(rows: list[dict], ordering: str) -> list[dict]:
    """Порядок показа. Строки, которым сравнивать нечем, всегда внизу.

    Отдельным списком, а не хитрым ключом: переворот направления иначе
    поднял бы наверх позиции без единого расхождения, и «где не сходится»
    начиналось бы с тех, где сходится всё.
    """
    if ordering not in ORDERING:
        ordering = DEFAULT_ORDERING
    desc = ordering.startswith("-")
    name = ordering.lstrip("-")
    key = _SORT_KEYS[name]

    if name == "last":
        known = rows
        unknown: list[dict] = []
    else:
        known = [row for row in rows if key(row) is not None]
        unknown = [row for row in rows if key(row) is None]

    def sort_key(row):
        value = key(row)
        if value is None:
            value = _NEVER  # только для «last»: никогда — это дольше всех
        return (value, row["product_id"])

    known.sort(key=sort_key, reverse=desc)
    unknown.sort(key=lambda row: row["product_id"])
    return known + unknown


def prepared(filters: Filters) -> dict:
    """Все строки выборки и итог по ним. Два запроса на всю страницу."""
    products = stocked().select_related("stock", "uom")
    if filters.folder:
        products = products.filter(folder=filters.folder)
    if filters.search:
        products = products.filter(matching(filters.search, prefix=""))

    positions = (
        InventoryPosition.objects.filter(inventory__deleted_at__isnull=True)
        .select_related("inventory")
    )
    if filters.store:
        positions = positions.filter(inventory__store_name=filters.store)

    by_product: dict[int, list[InventoryPosition]] = {}
    for position in positions:
        by_product.setdefault(position.product_id, []).append(position)

    today = local_date(timezone.now())
    rows = [_row(p, by_product.get(p.id, []), today) for p in products]

    return {"rows": _sorted(rows, filters.ordering), "totals": totals(rows)}


def totals(rows: list[dict]) -> dict:
    """Итог под таблицей — про то, что в ней видно, с учётом поиска."""
    money = [row["correction_money_kopecks"] for row in rows]
    return {
        "products_count": len(rows),
        "never_counted_count": sum(1 for row in rows if not row["counted_times"]),
        # По последнему пересчёту, а не по всей истории: колонка
        # «Расхождение» показывает именно его, и позиция, разошедшаяся
        # в июне и сошедшаяся в августе, попадала бы в итог, но не в блок
        # «Где не сходится». Два числа на одном экране обязаны означать одно.
        # Сколько раз позиция расходилась за историю — вопрос блока
        # «Расходится из раза в раз».
        "diverged_count": sum(1 for row in rows if row["correction"]),
        "money_kopecks": sum(value for value in money if value is not None),
        # Сколько расхождений осталось без денежной оценки. Без этого числа
        # итог выглядел бы полным, хотя себестоимости нет у части позиций.
        #
        # Считаются только те, где расхождение **есть**: у позиции, которая
        # сошлась, оценивать нечего, и попав сюда, она раздувала бы «не
        # оценено» втрое — 35 вместо 12 на боевых данных. Ровно то же условие
        # стоит в блоке «Где не сходится»: два числа на одном экране обязаны
        # означать одно.
        "unpriced_count": sum(
            1
            for row in rows
            if row["correction"] and row["correction_money_kopecks"] is None
        ),
    }


def page(whole: dict, filters: Filters) -> dict:
    """Срез страницы из уже посчитанной выборки.

    Принимает `prepared`, а не зовёт его сам: блоки под таблицей считаются
    по тем же строкам, и второй проход стоил бы полного перебора
    номенклатуры со всеми позициями инвентаризаций — на каждый запрос.
    """
    rows = whole["rows"]
    start, end = page_bounds(filters.page, filters.page_size)

    return {
        "count": len(rows),
        "totals": whole["totals"],
        "results": rows[start:end],
    }
