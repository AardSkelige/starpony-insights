"""Полки возраста: границы, пустые корзины и доли.

Ошибка на границе тихая вдвойне. Сдвинься она на день — долг возрастом
ровно 30 суток уедет в «31–60», и человек прочитает на экране, что площадка
нарушила обещанный цикл выплаты, хотя она его выдержала.
"""

import pytest

from api.deadlines.services import aging
from api.deadlines.services.aging import AgeBucket

pytestmark = pytest.mark.django_db


class Debt:
    """Долг, каким его видит старение: возраст и сумма, больше ничего.

    Настоящий `Debt` тянет за собой документ, контрагента и договор —
    для проверки границ это шум, а не условие.
    """

    def __init__(self, age_days: int, debt_kopecks: int = 100_00):
        self.age_days = age_days
        self.debt_kopecks = debt_kopecks


class TestBoundaries:
    @pytest.mark.parametrize(
        ("age_days", "expected"),
        [
            (0, AgeBucket.FRESH),
            (14, AgeBucket.FRESH),
            (15, AgeBucket.RECENT),
            (30, AgeBucket.RECENT),
            (31, AgeBucket.STALE),
            (60, AgeBucket.STALE),
            (61, AgeBucket.OLD),
            (365, AgeBucket.OLD),
        ],
    )
    def test_shelf_of_age(self, age_days, expected):
        assert aging.bucket_of(age_days) == expected

    def test_upper_bound_is_inclusive(self):
        """Названная на экране граница означает то, что написано.

        «15–30 дней» обязано включать тридцатый день: он и есть обещанный
        срок выплаты площадки, и попади он в соседнюю корзину, страница
        сообщала бы о нарушении там, где его нет.
        """
        assert aging.bucket_of(30) == AgeBucket.RECENT
        assert aging.bucket_of(31) == AgeBucket.STALE


class TestDistribution:
    def test_empty_shelves_stay(self):
        """Пустая полка остаётся в ответе.

        Пропусти её — и шкала превращается в произвольный набор столбиков,
        а «между 15 и 60 днями ничего нет» перестаёт читаться. Это
        утверждение о данных, и оно должно быть видно.
        """
        rows = aging.distribution([Debt(1), Debt(100)])

        assert [row["key"] for row in rows] == [
            AgeBucket.FRESH,
            AgeBucket.RECENT,
            AgeBucket.STALE,
            AgeBucket.OLD,
        ]
        assert [row["count"] for row in rows] == [1, 0, 0, 1]

    def test_money_lands_on_its_shelf(self):
        rows = {row["key"]: row for row in aging.distribution(
            [Debt(3, 10_000), Debt(20, 30_000), Debt(20, 20_000), Debt(90, 40_000)]
        )}

        assert rows[AgeBucket.FRESH]["debt_kopecks"] == 10_000
        assert rows[AgeBucket.RECENT]["debt_kopecks"] == 50_000
        assert rows[AgeBucket.STALE]["debt_kopecks"] == 0
        assert rows[AgeBucket.OLD]["debt_kopecks"] == 40_000

    def test_shares_add_up_to_one(self):
        rows = aging.distribution([Debt(3, 25_000), Debt(40, 75_000)])
        assert sum(row["share"] for row in rows) == 1

    def test_shelf_says_whether_it_is_within_the_promised_cycle(self):
        """Граница «свежести» приходит с сервера, а не повторяется на экране.

        Заголовок блока говорит «старше 30 дней». Держи фронтенд свой список
        полок — сдвинь границу здесь, и фраза осталась бы прежней, а складывать
        стала бы другие корзины. Молча.
        """
        rows = {row["key"]: row for row in aging.distribution([])}

        assert rows[AgeBucket.FRESH]["fresh"] is True
        assert rows[AgeBucket.RECENT]["fresh"] is True
        assert rows[AgeBucket.STALE]["fresh"] is False
        assert rows[AgeBucket.OLD]["fresh"] is False

        # Последняя полка без потолка: у неё его нет, и `null` честнее числа.
        assert rows[AgeBucket.RECENT]["up_to_days"] == aging.PROMISED_CYCLE_DAYS
        assert rows[AgeBucket.OLD]["up_to_days"] is None

    def test_share_is_none_when_there_is_nothing(self):
        """Ноль долей и «долей нет» — разные утверждения.

        Ноль читается как «эта полка пуста при непустых соседях»,
        а делить не на что — совсем другое дело.
        """
        rows = aging.distribution([])
        assert all(row["share"] is None for row in rows)
        assert all(row["count"] == 0 for row in rows)
