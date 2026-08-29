"""Общий слой выборки: границы страницы и границы дня.

Проверяется здесь, а не через страницу. Страничная проверка «выборка
не длиннее потолка» проходила вхолостую: в фикстуре был один материал,
и `1 <= 200` выполнялось при любом коде. Три таких теста в этом проекте
уже находили — зелёный тест ничего не значит, пока не доказано,
что он умеет краснеть.
"""

from datetime import date

import pytest
from django.utils import timezone

from api.common.selection import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    Filters,
    day_after,
    day_start,
    matching,
    page_bounds,
)


class TestPageBounds:
    def test_caps_the_height(self):
        """Ссылка с `size=100000` не должна уводить базу в долгий скан."""
        assert page_bounds(1, 100_000) == (0, MAX_PAGE_SIZE)

    def test_caps_the_height_on_a_later_page(self):
        """Потолок действует и на смещение, а не только на длину среза."""
        start, end = page_bounds(3, 100_000)
        assert end - start == MAX_PAGE_SIZE
        assert start == 2 * MAX_PAGE_SIZE

    def test_zero_height_falls_back_to_one(self):
        """Нулевая высота дала бы пустой срез на непустой выборке."""
        assert page_bounds(1, 0) == (0, 1)

    def test_page_below_one_starts_at_zero(self):
        """`?page=0` и `?page=-3` — не повод резать с отрицательного смещения."""
        assert page_bounds(0, 10) == (0, 10)
        assert page_bounds(-3, 10) == (0, 10)

    def test_offsets_follow_the_height(self):
        assert page_bounds(2, 25) == (25, 50)
        assert page_bounds(4, 10) == (30, 40)


class TestDayBounds:
    def test_day_starts_at_midnight_local(self):
        """Граница периода — про календарь, а не про UTC."""
        start = day_start(date(2026, 6, 30))
        assert (start.hour, start.minute, start.second) == (0, 0, 0)
        assert start.tzinfo is not None

    def test_upper_bound_is_the_next_day(self):
        """Сравнивать с концом дня нельзя: `moment` хранит доли секунды,
        и документ, проведённый в 23:59:59.5, выпал бы из периода."""
        assert day_after(date(2026, 6, 30)) == day_start(date(2026, 7, 1))

    def test_bounds_are_aware_of_the_current_zone(self):
        """Учёт ведётся в Москве, и «за 30 июня» значит московские сутки."""
        assert timezone.is_aware(day_start(date(2026, 6, 30)))


class TestSearchCondition:
    @pytest.mark.parametrize(
        "field", ["product__name__icontains", "product__article__icontains",
                  "product__code__icontains"]
    )
    def test_looks_at_name_article_and_code(self, field):
        """Поиск идёт по трём полям: по названию, артикулу и коду.

        Условие, а не готовый фильтр: у деталей строки путь к товару другой,
        и переносится именно условие.
        """
        assert field in str(matching("вода"))


class TestFilters:
    def test_default_height_matches_the_screen(self):
        """Два разных умолчания значили бы, что `/api/docs` расходится
        с тем, что человек видит на странице."""
        assert Filters().page_size == DEFAULT_PAGE_SIZE

    def test_has_no_ordering(self):
        """Общего умолчания порядка нет: у «Товаров» это `-revenue`,
        у «Материалов» такого ключа нет вовсе. Его задаёт наследник."""
        assert not hasattr(Filters(), "ordering")
