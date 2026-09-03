"""Площадки: признак, множества и неизвестная себестоимость.

Три ошибки в одном блоке, и все три тихие. Признак, набранный с заглавной,
теряет площадку целиком — при том что «Сроки оплаты» её видят. Прямые
продажи, посчитанные вычитанием из другого множества, уходят в минус.
Неизвестная себестоимость, принятая за ноль, даёт маржу ровно 100 % —
самое опасное число на этой странице.
"""

from decimal import Decimal

import pytest

from api.profitability.services.profitability import page
from api.profitability.services.selection import Basis, Filters

from .conftest import moscow, position

pytestmark = pytest.mark.django_db


class TestTagIsNormalised:
    """Группу набирает человек, и регистр у неё какой угодно."""

    @pytest.mark.parametrize("tag", ["маркетплейсы", "Маркетплейсы", " Маркетплейсы "])
    def test_marketplace_is_recognised_whatever_the_case(
        self, tag, product, make_agent, make_profit_day, make_demand
    ):
        """Тот же признак, что у `Counterparty.is_marketplace`.

        Тот сравнивает через `casefold()` и `strip()` намеренно: группу
        заводит человек. Точное сравнение массива в запросе расходится
        с ним молча — площадка исчезает со страницы, оставаясь площадкой
        на «Сроках оплаты».
        """
        ozon = make_agent("ООО «Интернет Решения»", tags=[tag])
        assert ozon.is_marketplace, "фикстура обязана давать площадку"

        make_profit_day(quantity="10", revenue_kopecks=100_000, cost_kopecks=30_000)
        shipment = make_demand(moment=moscow(2026, 7, 15), agent=ozon)
        position(shipment, product, 10, 10_000)

        row = page(Filters(basis=Basis.SHIPPED))["results"][0]

        assert row["marketplace_quantity"] == Decimal("10.000")
        assert row["marketplace_revenue_kopecks"] == 100_000


class TestUnknownCostDoesNotLeak:
    """Товар без известной себестоимости не должен ломать соседние числа."""

    @pytest.fixture
    def mixed(self, make_product, make_agent, make_profit_day, make_demand):
        """Один товар с себестоимостью, второй — площадочный и без неё."""
        ozon = make_agent("ООО «Интернет Решения»", tags=["маркетплейсы"])

        known = make_product(name="Репеллент", article="300.001.05")
        make_profit_day(product=known, quantity="10", revenue_kopecks=100_000,
                        cost_kopecks=30_000)
        direct = make_demand(moment=moscow(2026, 7, 15))
        position(direct, known, 10, 10_000)

        # Отгружался только через площадку и ни разу не продан: в отчёте
        # прибыльности его нет, средней цены единицы взять неоткуда.
        # Сумма нарочно больше известной выручки — так разность двух разных
        # множеств уходит в минус, а не прячется за случайным перевесом.
        unknown = make_product(name="Воск", article="400.003.15")
        through = make_demand(moment=moscow(2026, 7, 16), agent=ozon)
        position(through, unknown, 5, 30_000)
        return known, unknown

    def test_direct_revenue_never_goes_negative(self, mixed):
        """Прямые продажи считаются вычитанием — значит из того же множества.

        Выручка итога складывается по строкам с известной себестоимостью,
        а выручка площадок — по всем. Разность двух разных множеств дала
        «напрямую −900 ₽»: отрицательная выручка на экране.
        """
        marketplaces = page(Filters(basis=Basis.SHIPPED, page_size=200))["marketplaces"]

        assert marketplaces["direct_revenue_kopecks"] >= 0
        assert marketplaces["direct_cost_kopecks"] >= 0

    def test_marketplace_margin_is_not_a_hundred_percent(self, mixed):
        """Неизвестная себестоимость — не ноль.

        Принятая за ноль, она даёт маржу ровно 100 %, и это число выглядит
        достовернее любого другого на странице.
        """
        marketplaces = page(Filters(basis=Basis.SHIPPED, page_size=200))["marketplaces"]

        assert marketplaces["marketplace_margin"] != Decimal(1)

    def test_both_parts_are_of_one_set(self, mixed):
        """Каждая часть считается по строкам с известной себестоимостью.

        Проверяется не сложение — оно сходится всегда, потому что «напрямую»
        и есть разность, — а **каждое слагаемое по отдельности**: площадки
        обязаны браться из того же множества, что и итог.

        Правило «соседние числа обязаны быть об одном множестве» — шесть
        дефектов этого класса за четыре сессии.
        """
        payload = page(Filters(basis=Basis.SHIPPED, page_size=200))
        marketplaces = payload["marketplaces"]
        known = [row for row in payload["results"] if row["cost_kopecks"] is not None]

        assert marketplaces["marketplace_revenue_kopecks"] == sum(
            row["marketplace_revenue_kopecks"] for row in known
        )
        assert marketplaces["direct_revenue_kopecks"] == sum(
            row["revenue_kopecks"] - row["marketplace_revenue_kopecks"]
            for row in known
        )
