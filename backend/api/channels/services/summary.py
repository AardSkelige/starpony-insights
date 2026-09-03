"""Итоги страницы «Каналы продаж»: что в таблице и что в выборке.

Два набора чисел, а не один, — правило, купленное на трёх соседних
страницах. Итог под таблицей считается по показанным строкам и обязан
сходиться со сложением колонки; сводка описывает выборку отгрузок целиком,
и поиск её не трогает.

Смешай их — получится дробь, где числитель от найденного, а знаменатель
от всего: «выручка 219 027 ₽ из 305 отгрузок» после поиска «озон» выглядит
обычным числом и врёт молча.
"""

from core.money import share
from core.services import consignment


def table_totals(rows: list[dict], selection_revenue: int) -> dict:
    """Итог по строкам таблицы — с учётом поиска.

    Доля считается от выручки всей выборки, как и у отдельных строк. Без
    поиска это ровно сто процентов, с поиском — сколько найденное занимает
    во всех продажах.
    """
    revenue = sum(row["revenue_kopecks"] for row in rows)
    return {
        "channels_count": len(rows),
        "shipments_count": sum(row["shipments_count"] for row in rows),
        "revenue_kopecks": revenue,
        "revenue_share": share(revenue, selection_revenue),
        # Реализация в итоге считается по показанным строкам, как и выручка
        # рядом: соседние числа обязаны быть об одном множестве. Оговорка
        # над таблицей берётся отсюда — при поиске она сужается вместе
        # со строками, а не остаётся про всю базу (`DESIGN.md` §8).
        "consignment": consignment.share_of(
            total_kopecks=revenue,
            consignment_kopecks=sum(
                row["consignment"].consignment_kopecks for row in rows
            ),
        ),
        # Покупатели и товары — через объединение, а не сложением колонки:
        # один покупатель приходит через несколько каналов, и сложение
        # посчитало бы его дважды. Итог обязан сходиться с числом строк
        # в таблице, а не с суммой ячеек, которые считают разное.
        "buyers_count": len(set().union(*(row["agent_ids"] for row in rows)))
        if rows
        else 0,
        "products_count": len(set().union(*(row["product_ids"] for row in rows)))
        if rows
        else 0,
    }


def coverage(everything: list[dict], selection: dict) -> dict:
    """Насколько полное число видит человек — по выборке, а не по поиску.

    Числитель и знаменатель здесь обязаны быть об одном множестве. Возьми
    число найденных каналов, а число отгрузок — по всей выборке, получится
    дробь, которая выглядит обычной и врёт, не подавая вида.
    """
    return {
        "channels_count": len(everything),
        # Отгрузки выборки целиком — вместе с теми, у кого канала нет.
        # Именно это число сходится с учётом, и именно оно объясняет,
        # почему итог таблицы меньше.
        "shipments_count": selection["shipments_count"],
        "revenue_kopecks": selection["revenue_kopecks"],
        # Отгрузки без канала. На боевых данных одна из 306, и молчать о ней
        # нельзя: без этого числа итог таблицы просто не сходится с учётом,
        # и расхождение выглядит ошибкой расчёта.
        "unassigned_shipments_count": selection["unassigned_shipments_count"],
        "unassigned_revenue_kopecks": selection["unassigned_revenue_kopecks"],
        # Отгрузки, ушедшие даром: 46 из 306 на боевых данных. Без этого
        # числа нулевая медиана чека у двух каналов выглядит сбоем расчёта.
        "free_shipments_count": sum(
            row["receipt"].free_shipments for row in everything
        ),
        "buyers_count": selection["buyers_count"],
        "products_count": selection["products_count"],
    }
