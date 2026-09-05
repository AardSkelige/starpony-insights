"""Свёрнутые блоки под таблицей: что не считали, где не сходится, чем считали.

Все три отвечают формой, а не текстом (`CLAUDE.md` §8.0): доля пересчитанного
читается длиной полосы, а «Производство/Тара — 0 из 27» списком строк
не читается вовсе.

**Блоки и таблица говорят об одном множестве.** Деньги здесь — по последнему
пересчёту каждой позиции, ровно как в таблице. Сложи блок всю историю
пересчётов, и два числа на одном экране означали бы разное, оставаясь оба
верными, — тот самый дефект, который на «Каналах» стоил 281 126 ₽ непонимания.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone

from api.inventory.services.selection import Filters
from core.dates import local_date
from core.models import Inventory, StoreStock
from core.money import share
from core.services.catalogue import stocked

# Сколько строк показывать в полосах. Больше десятка полос перестают
# сравниваться взглядом, а вопрос к списку один — «кто из них главный».
BAR_LIMIT = 10

# Подпись для документов, у которых склад не приехал. Не пустая строка:
# безымянная карточка читается как поломка вёрстки, а не как след сбоя.
NO_STORE = "Склад не указан"


def coverage(rows: list[dict]) -> dict:
    """Что не считали — по папкам номенклатуры.

    Знаменатель — вся выборка, а не пересчитанное: доля «сколько из скольких»
    только так и отвечает на вопрос. Папки без единого пересчёта остаются
    в списке — они и есть ответ.
    """
    folders: dict[str, dict] = {}
    for row in rows:
        entry = folders.setdefault(
            row["folder"] or "Без папки", {"folder": row["folder"] or "Без папки",
                                           "products_count": 0, "counted_count": 0,
                                           "days_ago": [], "moments": []}
        )
        entry["products_count"] += 1
        if row["counted_times"]:
            entry["counted_count"] += 1
            entry["days_ago"].append(row["days_ago"])
            entry["moments"].append(row["last_moment"])

    items = []
    for entry in folders.values():
        ages = sorted(entry.pop("days_ago"))
        moments = entry.pop("moments")
        items.append({
            **entry,
            "share": share(entry["counted_count"], entry["products_count"]),
            # Медиана, а не среднее: одна давняя позиция в папке из сорока
            # сдвинула бы среднее на месяц и назвала бы папку забытой.
            "days_ago": ages[len(ages) // 2] if ages else None,
            # Когда группу трогали в последний раз. Отдельно от медианы,
            # и это разные ответы: медиана говорит «типично по позициям
            # папки», дата — «когда до этой папки вообще доходили руки».
            # Спрашивают чаще второе: «когда считали сырьё».
            "last_moment": max(moments) if moments else None,
            "last_days_ago": min(ages) if ages else None,
        })
    items.sort(key=lambda item: (-item["products_count"], item["folder"]))

    counted = sum(item["counted_count"] for item in items)
    products = sum(item["products_count"] for item in items)
    oldest = [item for item in items if item["days_ago"] is not None]

    return {
        "products_count": products,
        "counted_count": counted,
        "never_counted_count": products - counted,
        # Папка, которую не открывали дольше всех, — с неё и начинают.
        "oldest_folder": max(oldest, key=lambda item: item["days_ago"])["folder"]
        if oldest else "",
        "oldest_days_ago": max((item["days_ago"] for item in oldest), default=None),
        "items": items,
    }


def worst(rows: list[dict]) -> dict:
    """Где не сходится — дороже всего, по последнему пересчёту позиции."""
    priced = [row for row in rows if row["correction_money_kopecks"] is not None]
    priced.sort(key=lambda row: abs(row["correction_money_kopecks"]), reverse=True)

    return {
        "money_kopecks": sum(row["correction_money_kopecks"] for row in priced),
        "diverged_count": sum(1 for row in rows if row["correction"]),
        "counted_count": sum(1 for row in rows if row["counted_times"]),
        # Позиции, где расхождение есть, а оценить его нечем: себестоимости
        # у них нет. Итог без этого числа выглядел бы полным.
        "unpriced_count": sum(
            1 for row in rows
            if row["correction"] and row["correction_money_kopecks"] is None
        ),
        "items": [
            {
                "product_id": row["product_id"],
                "name": row["name"],
                "correction": row["correction"],
                "uom": row["uom"],
                "money_kopecks": row["correction_money_kopecks"],
            }
            for row in priced[:BAR_LIMIT] if row["correction"]
        ],
    }


def repeats(rows: list[dict]) -> dict:
    """Расходится из раза в раз — про историю, а не про последний пересчёт.

    Единственный блок страницы, который смотрит на все пересчёты сразу,
    и смотрит намеренно: позиция, разошедшаяся дважды из двух, — это не
    случайность счёта, а место, где учёт систематически расходится с полкой.
    """
    items = [
        {
            "product_id": row["product_id"],
            "name": row["name"],
            "folder": row["folder"],
            "counted_times": row["counted_times"],
            "diverged_times": row["diverged_times"],
        }
        for row in rows if row["diverged_times"] > 1
    ]
    items.sort(key=lambda item: (-item["diverged_times"], item["name"].casefold()))

    return {"count": len(items), "items": items[:BAR_LIMIT]}


def documents(filters: Filters) -> dict:
    """Чем считали: сами инвентаризации, по одной строке.

    Список короткий — шесть документов, — и он здесь не ради самого списка,
    а ради ответа «где считали»: складов три, и каждый пересчёт трогает один.
    """
    queryset = Inventory.objects.alive().order_by("-moment")
    if filters.store:
        queryset = queryset.filter(store_name=filters.store)

    items = []
    for inventory in queryset.prefetch_related("positions"):
        positions = list(inventory.positions.all())
        items.append({
            "inventory_id": inventory.id,
            "number": inventory.number,
            "moment": inventory.moment,
            # Та же подпись, что в сводке складов: страница группирует бумаги
            # по имени склада, и пустое имя против «Склад не указан» развело
            # бы их по разным карточкам — документ снова стал бы невидим.
            "store_name": inventory.store_name or NO_STORE,
            "positions_count": len(positions),
            "diverged_count": sum(1 for p in positions if p.correction_amount),
            "description": inventory.description,
        })

    return {"count": len(items), "items": items}


def store_recounts(filters: Filters) -> list[dict]:
    """По каждому складу: когда считали, сколько пересчитано и на сколько денег.

    Пересчёт — операция **склада**, а не папки: документ всегда про один склад
    целиком. «Когда считали сырьё» и «когда считали Производство» — разные
    вопросы, и второй берётся прямо из документов.

    Знаменатель — позиции, которые на складе **лежат** сейчас (ненулевой
    остаток из `/report/stock/bystore`). Считать от всей номенклатуры нельзя:
    на «Готовой продукции» сырья нет и не должно быть, а доля пересчёта
    от 312 позиций объявила бы склад заброшенным.

    Числитель — те из них, что попадали в инвентаризацию **этого** склада.
    Пересчёт на соседнем складе про этот ничего не говорит.
    """
    today = local_date(timezone.now())

    stocked_ids = set(stocked().values_list("id", flat=True))
    on_store: dict[str, dict[int, Decimal]] = {}
    cost: dict[int, Decimal] = {}
    for row in StoreStock.objects.select_related("product__stock"):
        if row.product_id not in stocked_ids:
            continue
        on_store.setdefault(row.store_name, {})[row.product_id] = row.quantity
        stock = getattr(row.product, "stock", None)
        cost[row.product_id] = stock.cost_kopecks if stock else Decimal(0)

    counted_on_store: dict[str, set[int]] = {}
    latest: dict[str, dict] = {}
    # Документы без склада тоже попадают в сводку — под своей подписью.
    # Прежде они выпадали из неё и не показывались нигде, продолжая считаться
    # в заголовке блока: «6 инвентаризаций», из которых видно пять. Пустое
    # имя означает, что `expand=store` не доехал, и синк об этом
    # предупреждает — молчать здесь значило бы прятать след сбоя.
    queryset = Inventory.objects.alive()
    if filters.store:
        queryset = queryset.filter(store_name=filters.store)
    for inventory in queryset.order_by("moment").prefetch_related("positions"):
        counted = counted_on_store.setdefault(inventory.store_name, set())
        counted.update(p.product_id for p in inventory.positions.all())
        latest[inventory.store_name] = {
            "number": inventory.number,
            "moment": inventory.moment,
        }

    items = []
    for store_name in sorted(set(on_store) | set(latest)):
        if filters.store and store_name != filters.store:
            continue
        here = on_store.get(store_name, {})
        counted = counted_on_store.get(store_name, set())
        last = latest.get(store_name)

        unchecked = sum(
            (quantity * cost.get(product_id, Decimal(0))
             for product_id, quantity in here.items()
             if product_id not in counted),
            Decimal(0),
        )
        items.append({
            "store_name": store_name or NO_STORE,
            "number": last["number"] if last else "",
            "moment": last["moment"] if last else None,
            "days_ago": (today - local_date(last["moment"])).days if last else None,
            "products_count": len(here),
            # Только те пересчитанные, что на складе и сейчас лежат: позиция,
            # посчитанная в мае и с тех пор увезённая, знаменателя не имеет,
            # и доля вышла бы больше единицы.
            "counted_count": len(counted & set(here)),
            "share": share(len(counted & set(here)), len(here)),
            # Во сколько обходится непроверенное. Ровно это число превращает
            # «пересчитано 18 %» из отметки в задачу.
            # Округление, а не усечение: правило копеек одно на весь проект
            # (`core/money.py`, `parse_kopecks`, `money_of`).
            "unchecked_kopecks": int(
                unchecked.to_integral_value(rounding=ROUND_HALF_UP)
            ),
        })

    items.sort(key=lambda item: -item["unchecked_kopecks"])
    return items
