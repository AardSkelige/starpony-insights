"""Итоги страницы «Материалы в приёмках»: что в таблице и что в выборке.

Два набора чисел, а не один, — урок соседней страницы. Итог под таблицей
считается по показанным строкам и обязан сходиться со сложением колонки;
сводка описывает выборку приёмок целиком, и поиск её не трогает.

Смешай их — получится дробь, где числитель от найденного, а знаменатель
от всего: «закуплено на 33 103 ₽ из 93 приёмок» после поиска «отдушка»
выглядит обычным числом и врёт молча.
"""


from core.money import share


def table_totals(rows: list[dict], selection_amount: int) -> dict:
    """Итог по строкам таблицы — с учётом поиска.

    Доля считается от суммы всей выборки, как и у отдельных строк. Без поиска
    это ровно сто процентов, с поиском — сколько найденное занимает во всех
    закупках. Написать «100 %» жёстко значило бы поставить над колонкой,
    где доли складываются в восемь процентов, итог «сто».
    """
    priced = [row for row in rows if row["avg_price_kopecks"] is not None]
    amount = sum(row["amount_kopecks"] for row in rows)
    return {
        "materials_count": len(rows),
        "amount_kopecks": amount,
        "amount_share": share(amount, selection_amount),
        "priced_count": len(priced),
        "unpriced_count": len(rows) - len(priced),
        # Приёмки и поставщики — тоже про показанные строки, а не про выборку.
        # Иначе подвал при поиске «отдушка» читается как «8 материалов
        # из 93 приёмок», где 93 описывают все 212: числитель от найденного,
        # знаменатель от всего — дробь, которая выглядит обычной и врёт.
        "documents_count": len(
            {document for row in rows for document in row["document_ids"]}
        ),
        "suppliers_count": len(
            {supplier for row in rows for supplier in row["supplier_ids"]}
        ),
    }


def coverage(everything: list[dict], positions: list, selection_amount: int) -> dict:
    """Насколько полное число видит человек — по выборке, а не по поиску.

    Числитель и знаменатель здесь обязаны быть об одном множестве. Возьми
    число найденных материалов, а число приёмок — по всей выборке, получится
    дробь, которая выглядит обычной и врёт, не подавая вида.
    """
    priced = [row for row in everything if row["avg_price_kopecks"] is not None]
    free_positions = [item for item in positions if item.total_kopecks <= 0]

    return {
        "materials_count": len(everything),
        "amount_kopecks": selection_amount,
        "documents_count": len({item.document_id for item in positions}),
        "suppliers_count": len({item.document.agent_id for item in positions}),
        "positions_count": len(positions),
        # Позиции, пришедшие даром: 97 из 402 на боевых данных. Без этого
        # числа средняя цена выглядит посчитанной по всему, что закупили.
        "free_positions_count": len(free_positions),
        "priced_count": len(priced),
        # Наименования, у которых цены нет вовсе: приходили только даром.
        # Их 24, все — этикетки от «Принтеца».
        "unpriced_count": len(everything) - len(priced),
        # Сколько наименований умеют показать динамику и разброс. Эти два
        # числа объясняют прочерки в колонках: у 130 материалов из 212
        # закупка была одна, и сравнивать их последнюю цену не с чем.
        "with_history_count": sum(
            1 for row in everything if row["price_change"] is not None
        ),
        "multi_supplier_count": sum(
            1 for row in everything if row["suppliers_count"] > 1
        ),
    }
