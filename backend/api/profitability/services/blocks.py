"""Блоки под таблицей «Прибыльности»: что показать, кроме строк.

Отдельно от `profitability.py` по причине изменения, а не по счётчику строк.
Тот файл меняется вместе с **фильтрами**: порядок строк, разбиение
на страницы, что попадает в выборку. Этот — вместе с **вопросами**, которые
задают к выборке: чего стоят подарки, где маржа завышена, на какой линейке
держится заработок. Так же поделены «Каналы продаж» — `channels.py`
и `breakdown.py`.

Все числа здесь считаются **по выборке целиком**, а не по показанной
странице: это ответы на «полное ли то, что показано», и меняться от того,
какая страница открыта, они не имеют права.
"""

from decimal import Decimal

from api.profitability.services.selection import Filters

ZERO = Decimal(0)


# Сколько товаров показывать в списках «где даром» и «в минусе».
# Больше — это уже таблица, а не ответ на вопрос «кто из них главный».
TOP = 5


def most_given_away_of(rows: list[dict]) -> list[dict]:
    """Товары, на которых подарки стоят дороже всего, — по всей выборке.

    Считается на сервере, а не на фронте, ровно по одной причине: фронт
    видит только показанную страницу. Список, собранный по десяти строкам
    из пятидесяти трёх, не содержал бы лидера вовсе.

    **Порядок — по себестоимости отданного, а не по доле.** Доля выводит
    наверх мелочь: четыре позиции «Амуниции» роздано целиком, и каждая
    даёт ровно 100 % при трёх штуках. Четыре одинаковые полосы не отвечают
    на вопрос «кто из них главный» — а вопрос блока денежный: во сколько
    обходится щедрость. Доля остаётся рядом, вторым числом.
    """
    ranked = []
    for row in rows:
        shipped = row["shipped_quantity"]
        free = row["free_quantity"]
        if not free or not shipped:
            continue
        ranked.append({
            "product_id": row["product_id"],
            "name": row["name"],
            "article": row["article"],
            "free_quantity": free,
            "shipped_quantity": shipped,
            "free_cost_kopecks": row["free_cost_kopecks"],
            "share": Decimal(free) / Decimal(shipped),
        })
    ranked.sort(key=lambda item: -item["free_cost_kopecks"])
    return ranked[:TOP]


def coverage_of(items: list[dict], hidden: list[dict], filters: Filters) -> dict:
    """Полнота расчёта: что осталось за пределами маржи и почему.

    Считается по всей выборке, поиск её не сужает: это ответ на вопрос
    «полное ли то, что показано», и он не должен меняться от набранного
    в поле поиска слова.
    """
    everything = items + hidden
    unsold = [row for row in everything if row["unsold_quantity"]]
    free = [row for row in everything if row["free_quantity"]]
    return {
        "basis": filters.basis,
        "with_free": filters.with_free,

        # Отдано даром: настоящая себестоимость без выручки.
        "free_products_count": len(free),
        "free_quantity": sum((row["free_quantity"] for row in free), ZERO),
        "free_cost_kopecks": sum(row["free_cost_kopecks"] for row in free),

        # Отгружено, но ещё не продано: лежит у комиссионера на реализации.
        "unsold_products_count": len(unsold),
        "unsold_quantity": sum((row["unsold_quantity"] for row in unsold), ZERO),
        "unsold_kopecks": sum(row["unsold_kopecks"] for row in unsold),

        # Строки, скрытые как пустые в выбранной базе. Число здесь обязано
        # сходиться с разницей между товарами в выборке и строками таблицы.
        "hidden_products_count": len(hidden),

        # Обе базы рядом — чтобы разница между ними была числом, а не
        # догадкой: «почему здесь меньше, чем в отгрузках».
        "sold_revenue_kopecks": sum(row["sold_revenue_kopecks"] for row in everything),
        "shipped_revenue_kopecks": sum(
            row["shipped_revenue_kopecks"] for row in everything
        ),

        # Кому достаётся даром — по всей выборке, а не по показанной странице.
        "most_given_away": most_given_away_of(everything),
    }


def marketplaces_of(items: list[dict]) -> dict:
    """Через площадки и напрямую — две маржи, из которых верна одна.

    Озон и ПМТ удерживают комиссию при выплате, и в учёт она не попадает
    вовсе: отдельного документа с ней нет. Значит маржа по площадкам
    завышена ровно на их процент, а по прямым продажам — настоящая.
    Показать одно число на всех значило бы смешать факт с завышенным.
    """
    # **Всё считается по строкам с известной себестоимостью.** Площадочная
    # часть, взятая по всем строкам, а прямая — вычитанием из известных,
    # это два разных множества: на боевой форме «напрямую» уходило в минус,
    # а маржа площадок становилась ровно 100 % — то самое число, которое
    # выглядит достовернее любого другого на странице.
    #
    # Строки без себестоимости при этом не пропадают молча: их выручку
    # называет `revenue_without_cost_kopecks` в итоге.
    known = [row for row in items if row["cost_kopecks"] is not None]
    mk_revenue = sum(row["marketplace_revenue_kopecks"] for row in known)
    mk_cost = sum(row["marketplace_cost_kopecks"] or 0 for row in known)
    revenue = sum(row["revenue_kopecks"] for row in known)
    cost = sum(row["cost_kopecks"] for row in known)

    direct_revenue = revenue - mk_revenue
    direct_cost = cost - mk_cost
    return {
        "marketplace_products_count": len([r for r in known if r["marketplace_quantity"]]),
        "marketplace_quantity": sum((row["marketplace_quantity"] for row in known), ZERO),
        "marketplace_revenue_kopecks": mk_revenue,
        "marketplace_cost_kopecks": mk_cost,
        "marketplace_profit_kopecks": mk_revenue - mk_cost,
        "marketplace_margin": (
            Decimal(mk_revenue - mk_cost) / Decimal(mk_revenue) if mk_revenue else None
        ),
        "direct_revenue_kopecks": direct_revenue,
        "direct_cost_kopecks": direct_cost,
        "direct_profit_kopecks": direct_revenue - direct_cost,
        "direct_margin": (
            Decimal(direct_revenue - direct_cost) / Decimal(direct_revenue)
            if direct_revenue > 0
            else None
        ),
    }


def families_of(items: list[dict]) -> list[dict]:
    """Линейки продукции — из пути группы в номенклатуре.

    Берётся последнее звено пути: «Готовая продукция/Репеллент» это
    «Репеллент». Полный путь превратил бы полосы в семь одинаковых
    подписей, различающихся концом, — тот самый дефект, ради которого
    в `BarList` заведён `multilineLabels`.
    """
    buckets: dict[str, dict] = {}
    for row in items:
        if row["cost_kopecks"] is None:
            continue
        name = (row["folder"] or "").split("/")[-1] or "Без группы"
        bucket = buckets.setdefault(
            name, {"name": name, "revenue_kopecks": 0, "cost_kopecks": 0,
                   "products_count": 0}
        )
        bucket["revenue_kopecks"] += row["revenue_kopecks"]
        bucket["cost_kopecks"] += row["cost_kopecks"]
        bucket["products_count"] += 1

    families = []
    for bucket in buckets.values():
        profit = bucket["revenue_kopecks"] - bucket["cost_kopecks"]
        families.append({
            **bucket,
            "profit_kopecks": profit,
            "margin": (
                Decimal(profit) / Decimal(bucket["revenue_kopecks"])
                if bucket["revenue_kopecks"]
                else None
            ),
        })
    return sorted(families, key=lambda f: -f["profit_kopecks"])


def losses_of(items: list[dict]) -> list[dict]:
    """Проданное в минус — сверху и отдельно, как требует `PRD.md` §5.10.

    Отдельным блоком, а не сортировкой: страница открывается лидерами,
    и убыточная позиция, стоящая шестидесятой, осталась бы незамеченной.
    """
    losing = [row for row in items if row["profit_kopecks"] is not None
              and row["profit_kopecks"] < 0]
    return sorted(losing, key=lambda row: row["profit_kopecks"])


def totals_of(items: list[dict]) -> dict:
    """Итог по показанному множеству — с учётом поиска, как в подвале."""
    revenue = sum(row["revenue_kopecks"] for row in items)
    # Себестоимость складывается только по строкам, где она известна.
    # Иначе прибыль в подвале посчиталась бы по одному множеству,
    # а выручка — по другому.
    known = [row for row in items if row["cost_kopecks"] is not None]
    cost = sum(row["cost_kopecks"] for row in known)
    known_revenue = sum(row["revenue_kopecks"] for row in known)
    profit = known_revenue - cost
    return {
        "products_count": len(items),
        "quantity": sum((row["quantity"] for row in items), ZERO),
        "revenue_kopecks": revenue,
        "cost_kopecks": cost,
        "profit_kopecks": profit,
        "margin": Decimal(profit) / Decimal(known_revenue) if known_revenue else None,
        # Сколько выручки осталось без себестоимости. Ноль — нормальное
        # состояние; ненулевое обязано быть видно, иначе маржа считается
        # по части выборки, а выглядит как по всей.
        "revenue_without_cost_kopecks": revenue - known_revenue,
    }
