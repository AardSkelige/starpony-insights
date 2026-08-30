"""Итоги страницы «Поставщики»: что в таблице и что в выборке.

Два набора чисел, а не один, — правило, купленное на соседних страницах.
Итог под таблицей считается по показанным строкам и обязан сходиться
со сложением колонки; сводка описывает выборку приёмок целиком,
и поиск её не трогает.

Смешай их — получится дробь, где числитель от найденного, а знаменатель
от всего: «закуплено на 55 100 ₽ из 95 приёмок» после поиска «принт»
выглядит обычным числом и врёт молча.
"""

from core.money import share


def table_totals(rows: list[dict], selection_amount: int) -> dict:
    """Итог по строкам таблицы — с учётом поиска.

    Доля считается от суммы всей выборки, как и у отдельных строк. Без поиска
    это ровно сто процентов, с поиском — сколько найденное занимает во всех
    закупках. Написать «100 %» жёстко значило бы поставить над колонкой,
    где доли складываются в шесть процентов, итог «сто».
    """
    amount = sum(row["amount_kopecks"] for row in rows)
    return {
        "suppliers_count": len(rows),
        "supplies_count": sum(row["supplies_count"] for row in rows),
        "amount_kopecks": amount,
        "amount_share": share(amount, selection_amount),
        # Наименования — через объединение, а не сложением колонки:
        # 21 материал приходит больше чем от одного поставщика, и сложение
        # посчитало бы его дважды. Итог обязан сходиться с числом строк
        # в таблице, а не с суммой ячеек, которые считают разное.
        "materials_count": len(set().union(*(row["material_ids"] for row in rows)))
        if rows
        else 0,
    }


def coverage(everything: list[dict], positions: list, selection_amount: int) -> dict:
    """Насколько полное число видит человек — по выборке, а не по поиску.

    Числитель и знаменатель здесь обязаны быть об одном множестве. Возьми
    число найденных поставщиков, а число приёмок — по всей выборке, получится
    дробь, которая выглядит обычной и врёт, не подавая вида.
    """
    return {
        "suppliers_count": len(everything),
        "supplies_count": sum(row["supplies_count"] for row in everything),
        "amount_kopecks": selection_amount,
        "positions_count": len(positions),
        "materials_count": len(
            {position.product_id for position in positions}
        ),
        # Позиции, пришедшие даром: 97 из 402 на боевых данных, все от одного
        # поставщика. Без этого числа суммы у «Принтеца» выглядят заниженными
        # и объяснить их нечем.
        "free_positions_count": sum(
            1 for position in positions if position.total_kopecks <= 0
        ),
        # Сколько поставщиков умеют показать регулярность и срок. Эти два
        # числа объясняют прочерки в колонках: у семи из двадцати трёх
        # поставка была одна, и промежутка между поставками не существует.
        "with_regularity_count": sum(
            1 for row in everything if row["regularity"].days is not None
        ),
        "with_lead_time_count": sum(
            1 for row in everything if row["lead_time"].days is not None
        ),
        # Приёмки, у которых заказа в зеркале нет. На боевых данных таких
        # ноль — связь заполнена на все 95, — и молчать о появлении первой
        # нельзя: срок посчитается не по всей истории и не скажет об этом.
        "unlinked_supplies_count": sum(
            row["lead_time"].unlinked for row in everything
        ),
    }
