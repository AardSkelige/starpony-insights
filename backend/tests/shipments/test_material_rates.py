"""Норма расхода и распределение — то, что заменило «откуда взялись».

Замер на боевых данных: из 161 материала у 100 расход равен проданному
один к одному, у 109 источник ровно один, несколько путей — у одного.
Прежний блок сообщал название трижды подряд; эти два — норму и то,
в чём сидит основное.
"""

from decimal import Decimal


from api.shipments.services.material_rates import (
    TOP_SOURCES,
    distribution,
    rates_of,
)


def source(name, sold, used, product_id=None):
    return {
        "product_id": product_id or abs(hash(name)) % 10_000,
        "name": name,
        "sold_quantity": Decimal(str(sold)),
        "quantity": Decimal(str(used)),
    }


class TestRates:
    def test_single_rate_collapses_to_one_row(self):
        """Триггер с боевых: 16 изделий, на каждое ровно один.

        Шестнадцать одинаковых строк не сообщают ничего сверх одной —
        ровно это и делал прежний блок.
        """
        rows = rates_of([source(f"Изделие {i}", 10, 10) for i in range(16)])

        assert len(rows) == 1
        assert rows[0]["rate"] == 1
        assert rows[0]["products_count"] == 16

    def test_different_rates_stay_apart(self):
        """Диметикон: 8 изделий по 200 г, 12 по 20 г. Разница в десять раз."""
        rows = rates_of(
            [source(f"Дорогое {i}", 1, 200) for i in range(8)]
            + [source(f"Дешёвое {i}", 1, 20) for i in range(12)]
        )

        assert [(row["rate"], row["products_count"]) for row in rows] == [
            (200, 8),
            (20, 12),
        ]

    def test_bigger_rate_first(self):
        """Расхождение в техкартах заметно сверху списка, а не в середине."""
        rows = rates_of([source("Мало", 1, 1), source("Много", 1, 500)])
        assert rows[0]["rate"] > rows[1]["rate"]

    def test_visually_equal_rates_are_one_row(self):
        """Группировка идёт по ключу, а на экран уходят шесть знаков.

        Техкарта одного изделия задаёт 0,142857, техкарта другого — 1/7.
        Ключи разные, но обе строки читаются как «0,142857», и человек
        видит две одинаковые нормы вместо одной. Группировать надо по тому,
        что видно.
        """
        rows = rates_of(
            [
                source("Первое", 1, Decimal("0.142857")),
                source("Второе", 7, 1),
            ]
        )

        assert len(rows) == 1, "две строки с одинаковым числом на экране"
        assert rows[0]["products_count"] == 2

    def test_examples_are_the_biggest_consumers(self):
        """В примере стоит то, что человек уже видел в распределении рядом."""
        rows = rates_of(
            [
                source("Мелкое", 1, 10),
                source("Крупное", 10, 100),
                source("Среднее", 5, 50),
            ]
        )
        assert rows[0]["examples"][0] == "Крупное"

    def test_examples_are_capped(self):
        """Строка обязана оставаться строкой, а не превращаться в список."""
        rows = rates_of([source(f"Изделие {i}", 1, 5) for i in range(20)])
        assert len(rows[0]["examples"]) == 3

    def test_unsold_product_gives_no_rate(self):
        """Делить не на что, а «ноль на ноль» — не факт учёта."""
        assert rates_of([source("Непроданное", 0, 0)]) == []


class TestDistribution:
    def test_parts_add_up_to_the_whole(self):
        """Слагаемые обязаны складываться в объясняемое число.

        Иначе расхождение спишут на расчёт — так уже было, когда панель
        показывала 20 источников из 59 и молча теряла 452 килограмма.
        """
        sources = [source(f"Изделие {i}", 1, (i + 1) * 10) for i in range(12)]
        total = sum((item["quantity"] for item in sources), Decimal(0))

        result = distribution(sources, total)
        shown = sum(item["quantity"] for item in result["top"])

        assert shown + result["rest"]["quantity"] == total

    def test_shares_add_up_to_one(self):
        sources = [source(f"Изделие {i}", 1, (i + 1) * 10) for i in range(12)]
        total = sum((item["quantity"] for item in sources), Decimal(0))

        result = distribution(sources, total)
        shares = [item["share"] for item in result["top"]]

        assert sum(shares) + result["rest"]["share"] == 1

    def test_biggest_first(self):
        result = distribution(
            [source("Мало", 1, 1), source("Много", 1, 100)], Decimal(101)
        )
        assert result["top"][0]["name"] == "Много"

    def test_short_list_has_no_tail(self):
        """Пустой хвост и свёрнутый хвост — разные вещи, и выглядят по-разному."""
        sources = [source(f"Изделие {i}", 1, 10) for i in range(TOP_SOURCES)]
        result = distribution(sources, Decimal(TOP_SOURCES * 10))

        assert result["rest"] is None
        assert len(result["top"]) == TOP_SOURCES

    def test_tail_counts_everyone_left(self):
        sources = [source(f"Изделие {i}", 1, 10) for i in range(TOP_SOURCES + 7)]
        result = distribution(sources, Decimal((TOP_SOURCES + 7) * 10))

        assert result["rest"]["products_count"] == 7

    def test_zero_total_gives_no_shares(self):
        """Делить не на что — прочерк, а не ноль процентов."""
        result = distribution([source("Изделие", 1, 0)], Decimal(0))
        assert result["top"][0]["share"] is None
