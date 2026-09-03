"""Сборка ответа: итог обязан сходиться с показанным.

Отдельно от `test_batch.py`, как и сам код: там проверяется расчёт,
здесь — форма ответа. Правило `DESIGN.md` §8: сумма в подвале собирается
сложением того, что видно в колонке, а знаменатель доли не сужается
поиском.
"""

from decimal import Decimal

import pytest

from api.production.services import payload
from api.production.services.selection import Filters
from tests.production.conftest import moscow, position

pytestmark = pytest.mark.django_db

# Период и горизонт для разрешения «посчитай сам». В этих проверках
# количества заданы числами, и на итог фильтры не влияют.
FILTERS = Filters()


class TestSummary:
    """Итог обязан сходиться с показанным."""

    def test_сумма_закупки_складывается_из_показанного(
        self, shampoo, make_document, supplier
    ):
        from core.models import DocumentKind, Product

        water = Product.objects.get(name="Вода дистиллированная")
        position(
            make_document(kind=DocumentKind.SUPPLY, agent=supplier),
            water, 1000, price_kopecks="2.5",
        )

        answer = payload.page({"100.011.05": 100}, FILTERS)
        shown = sum(row["cost_kopecks"] or 0 for row in answer["materials"])
        assert answer["summary"]["purchase_kopecks"] == shown

    def test_рядом_с_суммой_сколько_позиций_её_составили(self, shampoo):
        """Сумма — итог по тем, у кого есть цена, а не по всем недостающим."""
        summary = payload.page({"100.011.05": 100}, FILTERS)["summary"]
        assert summary["shortages_count"] == 2
        # Цены нет ни у одной, и сумма это обязана признать: «0 ₽» рядом
        # с «не хватает двух позиций» без второго числа читалось бы
        # как «докупка бесплатна».
        assert summary["priced_shortages_count"] == 0
        assert summary["purchase_kopecks"] == 0

    def test_срок_партии_по_самому_долгому(
        self, shampoo, make_document, supplier, run
    ):
        from core.models import Counterparty, DocumentKind, Product

        water = Product.objects.get(name="Вода дистиллированная")
        scent = Product.objects.get(name="Отдушка «Лесные ягоды»")
        slow = Counterparty.objects.create(
            ms_id="50000000-0000-0000-0000-000000000008",
            name="ООО «Долгий»", last_seen_run=run,
        )

        for product, agent, days in ((water, supplier, 3), (scent, slow, 20)):
            order = make_document(
                kind=DocumentKind.PURCHASE_ORDER, moment=moscow(2026, 6, 1),
                agent=agent,
            )
            position(
                make_document(
                    kind=DocumentKind.SUPPLY,
                    moment=moscow(2026, 6, 1 + days),
                    agent=agent,
                    purchase_order=order,
                ),
                product, 1000, price_kopecks="2.0",
            )

        # Обоих не хватает; партия начнётся не раньше, чем приедет последнее.
        summary = payload.page({"100.011.05": 100}, FILTERS)["summary"]
        assert summary["shortages_count"] == 2
        assert summary["max_lead_time_days"] == Decimal("20")

    def test_негодные_строки_не_считаются_товарами_партии(
        self, shampoo, make_product
    ):
        make_product("Таблетка-мыло", article="100.022.03")
        summary = payload.page({"100.011.05": 5, "100.022.03": 100}, FILTERS)["summary"]
        assert summary["products_count"] == 1
        assert summary["units_count"] == 5


class TestArchivedCount:
    def test_архивное_сырьё_считается_в_итоге(self, shampoo):
        from core.models import Product

        assert payload.page({"100.011.05": 1}, FILTERS)["summary"][
            "archived_count"
        ] == 0
        Product.objects.filter(name="Отдушка «Лесные ягоды»").update(archived=True)
        assert payload.page({"100.011.05": 1}, FILTERS)["summary"][
            "archived_count"
        ] == 1


class TestResolve:
    """Разрешение количеств: что заменяется, что остаётся неизвестным."""

    def test_считает_только_по_отмеченному(self, shampoo, make_product, make_plan):
        """Полный каталог на каждое нажатие «плюс» — трата, а не расчёт."""
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        water = shampoo.produced_by.first().materials.first().product
        for n in range(5):
            other = make_product(
                f"Кондиционер {n}", article=f"200.04{n}.05", code=f"2-10{n}"
            )
            make_plan(other, [(water, 100)])

        with CaptureQueriesContext(connection) as narrow:
            payload.resolve({"100.011.05": None}, FILTERS)
        with CaptureQueriesContext(connection) as wide:
            payload.resolve(
                {f"200.04{n}.05": None for n in range(5)} | {"100.011.05": None},
                FILTERS,
            )
        # Число запросов то же — сужение идёт условием, а не циклом.
        assert len(narrow) == len(wide)

    def test_ничего_не_разрешать_значит_не_ходить_в_базу(self, shampoo):
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        with CaptureQueriesContext(connection) as queries:
            assert payload.resolve({"100.011.05": 5}, FILTERS) == {"100.011.05": 5}
        # Все количества заданы — верхнее звено считать незачем.
        assert len(queries) == 0

    def test_нечего_предложить_остаётся_неизвестным(self, shampoo):
        # Продаж за период не было — предложение не считается.
        assert payload.resolve({"100.011.05": None}, FILTERS) == {
            "100.011.05": None
        }
