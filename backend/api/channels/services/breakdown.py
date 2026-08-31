"""Из чего складывается строка канала: кто покупает и что покупают.

Два списка, отвечающие на вопросы, которых в таблице нет вовсе. «Кто
покупает» вскрывает зависимость: у «Точки продаж» 87 % выручки даёт один
конноспортивный центр за 14 отгрузок из 34, и в строке этот канал выглядит
крупнейшим и здоровым. «Что покупают» отвечает линейками (`families.py`),
а не наименованиями: пять строк с разными вкусами кондиционера отвечают
на вопрос, которого не задавали.

Живут отдельно от `channels.py`: там выборка, сортировка и итоги страницы —
всё, что меняется вместе с фильтрами. Здесь то, что меняется вместе
с вопросом «на ком держится канал», и это другая причина.

**Хвост списка сворачивается, но не выбрасывается.** Слагаемые обязаны
складываться в выручку канала: потеряйся здесь товар, разница выглядела бы
потерянными деньгами, и найти её было бы нечем.
"""

from api.channels.services import families
from core.money import share
from core.text import with_plural

# Сколько покупателей и линеек показать поимённо. Остальные — строкой «ещё N».
LIMIT = 5


def top(rows: list[dict], total: int) -> dict:
    """Крупнейшие по выручке, хвост — строкой.

    По деньгам, а не по числу отгрузок: вопрос разбора — «на ком держится
    канал», и держится он на суммах. У «Точки продаж» 87 % выручки даёт один
    клуб за 14 отгрузок из 34 — по числу отгрузок этого не видно.
    """
    rows = sorted(rows, key=lambda item: -item["revenue_kopecks"])
    shown, rest = rows[:LIMIT], rows[LIMIT:]
    return {
        "items": [
            {**item, "share": share(item["revenue_kopecks"], total)} for item in shown
        ],
        "rest_count": len(rest),
        "rest_revenue_kopecks": sum(item["revenue_kopecks"] for item in rest),
    }


def buyers(shipments: list) -> dict:
    """Кто покупает. Подпись под строкой — сколько отгрузок он взял."""
    by_agent: dict[int, dict] = {}
    for shipment in shipments:
        entry = by_agent.setdefault(
            shipment.agent_id,
            {"name": shipment.agent.name, "revenue_kopecks": 0, "count": 0},
        )
        entry["revenue_kopecks"] += shipment.total_kopecks
        entry["count"] += 1

    rows = [
        {
            **entry,
            "note": with_plural(entry["count"], "отгрузка", "отгрузки", "отгрузок"),
        }
        for entry in by_agent.values()
    ]
    return top(rows, sum(entry["revenue_kopecks"] for entry in by_agent.values()))


def products(positions: list) -> dict:
    """Что покупают — линейками, а не наименованиями.

    Пять строк «Кондиционер для гривы и хвоста …Табак-Ваниль / …Кокосовое
    молоко / …Персик-Банан» отвечают на «какой вкус берут». Спрашивают
    другое — кондиционеры это или репелленты, — и на это отвечает линейка
    из артикула (`families.py`).
    """
    by_product: dict[int, dict] = {}
    for position in positions:
        entry = by_product.setdefault(
            position.product_id,
            {
                "name": position.product.name,
                "line": families.line_of(position.product),
                "revenue_kopecks": 0,
            },
        )
        entry["revenue_kopecks"] += position.total_kopecks

    rows = [
        {
            "name": row["name"],
            "revenue_kopecks": row["revenue_kopecks"],
            "note": variants(row),
        }
        for row in families.grouped(by_product)
    ]
    return top(rows, sum(entry["revenue_kopecks"] for entry in by_product.values()))


def variants(row: dict) -> str:
    """Что внутри свёрнутой линейки — для подсказки по наведению.

    Строка «Кондиционер 500 мл» отвечает на «что покупают», но прячет,
    какой именно: вкусов у него двадцать шесть. Названия вариантов уходят
    в подсказку — по убыванию выручки, потому что вопрос к ним «какой
    берут», а не «какие бывают».

    У отдельного товара подписи нет вовсе: «1 наименование» — шум,
    а не сведения.
    """
    # У одиночного товара в подсказке его полное название: подпись строки
    # сокращена до первого слова, и восстановить его больше негде.
    if row["items_count"] < 2:
        return row["full_name"] if row["full_name"] != row["name"] else ""

    shown = row["variants"][: families.VARIANTS]
    rest = row["items_count"] - len(shown)
    listed = ", ".join(shown) + (f" и ещё {rest}" if rest > 0 else "")
    count = with_plural(
        row["items_count"], "наименование", "наименования", "наименований"
    )
    return f"{count}: {listed}"


