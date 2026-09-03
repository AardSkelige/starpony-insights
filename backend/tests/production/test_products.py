"""Первое звено: что кончается и сколько этого произвести.

Стережёт то, что ломается молча: округление предложенного количества,
разницу между «ноль» и «не знаем», отбор товаров и порядок строк.
Ошибка здесь не падает — она показывает правдоподобное число.
"""

from decimal import Decimal

import pytest

from api.production.services import products
from api.production.services.selection import Filters
from tests.production.conftest import moscow

pytestmark = pytest.mark.django_db


def rows_by_article(filters=None):
    return {
        row.product.article: row
        for row in products.rows(filters or Filters(horizon=60))
    }


class TestSuggested:
    """Сколько варить: темп продаж × горизонт − остаток."""

    def test_считает_по_формуле(self):
        # 2 шт в день × 60 дней = 120, минус 20 на складе = 100.
        assert products.suggested_for(Decimal("2"), Decimal("20"), 60) == 100

    def test_округляет_вверх(self):
        # 1,033 шт в день × 60 = 61,98, минус 1 = 60,98. Половину флакона
        # не варят, и недоварить значит вернуться к строке через неделю.
        assert products.suggested_for(Decimal("1.033"), Decimal("1"), 60) == 61

    def test_остатка_больше_чем_нужно_ноль_а_не_минус(self):
        assert products.suggested_for(Decimal("1"), Decimal("500"), 60) == 0

    def test_не_продавался_нечего_восполнять(self):
        # None, а не ноль: ноль значил бы «производить не надо», а мы просто
        # не знаем, сколько его берут.
        assert products.suggested_for(Decimal(0), Decimal("10"), 60) is None

    def test_остаток_неизвестен_нечего_вычитать(self):
        assert products.suggested_for(Decimal("2"), None, 60) is None

    def test_горизонт_меняет_ответ(self):
        per_day, available = Decimal("2"), Decimal("20")
        assert products.suggested_for(per_day, available, 30) == 40
        assert products.suggested_for(per_day, available, 90) == 160


class TestCatalogue:
    """Кого показываем: товар — это то, у чего есть артикул."""

    def test_материал_без_артикула_не_товар(self, shampoo, make_product):
        make_product("Кокамид ДЭА", code="1-009")
        assert set(rows_by_article()) == {"100.011.05"}

    def test_архивный_не_предлагаем_варить(self, shampoo, make_product):
        make_product("Старый шампунь", article="100.004.05", archived=True)
        assert set(rows_by_article()) == {"100.011.05"}

    def test_услуга_не_товар(self, shampoo, make_product):
        from core.models import ProductKind

        make_product("Доставка", article="900.001.01", kind=ProductKind.SERVICE)
        assert set(rows_by_article()) == {"100.011.05"}

    def test_товар_без_техкарты_показан_но_помечен(self, shampoo, make_product):
        make_product("Таблетка-мыло", article="100.022.03")
        rows = rows_by_article()
        # Показан: его тоже кончает продаваться, и прятать строку значит
        # выдать пробел в учёте за отсутствие товара.
        assert rows["100.022.03"].has_plan is False
        assert rows["100.011.05"].has_plan is True

    def test_поиск_ищет_по_артикулу_и_названию(self, shampoo):
        assert set(rows_by_article(Filters(search="100.011"))) == {"100.011.05"}
        assert set(rows_by_article(Filters(search="шампунь"))) == {"100.011.05"}
        assert rows_by_article(Filters(search="кондиционер")) == {}


class TestCoverage:
    """Надолго ли хватит: остаток против темпа продаж."""

    def test_хватит_на_столько_дней_сколько_есть(self, shampoo, sell):
        # 30 штук за 30 дней = 1 в день; на складе 3 → хватит на 3 дня.
        sell(shampoo, 30, day=1)
        rows = rows_by_article(
            Filters(date_from=moscow(2026, 5, 1).date(),
                    date_to=moscow(2026, 5, 30).date(), horizon=60)
        )
        assert rows["100.011.05"].left.days_left == 3

    def test_резерв_не_свой(self, shampoo, sell, make_stock):
        """Зарезервированное обещано покупателю и запасом не считается."""
        from core.models import Stock

        Stock.objects.filter(product=shampoo).update(reserved=Decimal("2"))
        sell(shampoo, 30, day=1)
        rows = rows_by_article(
            Filters(date_from=moscow(2026, 5, 1).date(),
                    date_to=moscow(2026, 5, 30).date(), horizon=60)
        )
        # Свободен один флакон из трёх, значит хватит на день, а не на три.
        assert rows["100.011.05"].available == Decimal(1)
        assert rows["100.011.05"].left.days_left == 1

    def test_не_продавался_запас_неизвестен_а_не_бесконечен(self, shampoo):
        row = rows_by_article()["100.011.05"]
        # Прочерк, а не «хватит навсегда»: расхода не было, делить не на что.
        assert row.left.days_left is None
        assert row.suggested is None

    def test_остатка_в_отчёте_нет_это_не_ноль(
        self, shampoo, make_product, make_plan, sell, gram
    ):
        water = make_product("Вода", code="1-003")
        other = make_product("Кондиционер", article="200.040.05", code="2-002")
        make_plan(other, [(water, 100)])
        sell(other, 30, day=1)

        row = rows_by_article(
            Filters(date_from=moscow(2026, 5, 1).date(),
                    date_to=moscow(2026, 5, 30).date(), horizon=60)
        )["200.040.05"]
        assert row.available is None
        assert row.left.days_left is None
        # И варить не предлагаем: неясно, от чего отталкиваться.
        assert row.suggested is None

    def test_черновик_отгрузки_не_продажа(self, shampoo, sell):
        sell(shampoo, 30, day=1, applicable=False)
        assert rows_by_article()["100.011.05"].left.quantity == 0

    def test_удалённая_отгрузка_не_продажа(self, shampoo, sell):
        sell(shampoo, 30, day=1, deleted=True)
        assert rows_by_article()["100.011.05"].left.quantity == 0

    def test_подарок_считается_расходом(self, shampoo, sell):
        """Отданное даром произведено так же, как проданное."""
        sell(shampoo, 30, day=1)  # цена ноль — как подарок в учёте
        assert rows_by_article()["100.011.05"].left.quantity == 30


class TestOrder:
    """Порядок строк: сверху то, что кончается раньше."""

    def test_неизвестный_запас_уходит_в_конец(
        self, shampoo, make_product, make_plan, make_stock, sell
    ):
        water = make_product("Вода", code="1-003")
        quiet = make_product("Кондиционер", article="200.040.05", code="2-002")
        make_plan(quiet, [(water, 100)])
        make_stock(quiet, 500)

        sell(shampoo, 30, day=1)
        sell(quiet, 30, day=1)

        order = [
            row.product.article
            for row in products.rows(
                Filters(date_from=moscow(2026, 5, 1).date(),
                        date_to=moscow(2026, 5, 30).date(), horizon=60)
            )
        ]
        # Шампуня хватит на 3 дня, кондиционера на 500 — первый выше.
        assert order == ["100.011.05", "200.040.05"]


    def test_при_равном_запасе_выше_тот_что_уходит_быстрее(
        self, shampoo, make_product, make_plan, make_stock, sell
    ):
        """Ноль дней у обоих — но дыра разная, и первым варят большую.

        На боевых данных восемнадцать позиций разом показывают «хватит
        на 0 дней»; алфавит внутри нуля ставил товар с расходом 0,129 шт/день
        выше товара с 0,535 — то есть срочность подменял порядок букв.
        """
        water = make_product("Вода", code="1-003")
        slow = make_product("Аква-кондиционер", article="200.001.05", code="2-002")
        make_plan(slow, [(water, 100)])
        make_stock(slow, 0)
        from core.models import Stock

        Stock.objects.filter(product=shampoo).update(quantity=0, reserved=0)

        sell(slow, 3, day=1)      # медленный, но первый по алфавиту
        sell(shampoo, 60, day=1)  # быстрый

        order = [
            row.product.article
            for row in products.rows(
                Filters(date_from=moscow(2026, 5, 1).date(),
                        date_to=moscow(2026, 5, 30).date(), horizon=60)
            )
        ]
        assert order == ["100.011.05", "200.001.05"]


class TestSummary:
    """Итог обязан быть про то же множество, что и строки."""

    def test_знаменатель_сужается_поиском(
        self, shampoo, make_product, make_plan, make_stock
    ):
        water = make_product("Вода", code="1-003")
        other = make_product("Кондиционер", article="200.040.05", code="2-002")
        make_plan(other, [(water, 100)])
        make_stock(other, 5)

        assert products.page(Filters())["summary"]["products_count"] == 2
        # Найдя один товар, человек обязан увидеть итог по одному:
        # иначе доля считается от множества, которого на экране нет.
        found = products.page(Filters(search="шампунь"))["summary"]
        assert found["products_count"] == 1

    def test_неизвестные_считаются_отдельно_от_кончающихся(
        self, shampoo, make_product, make_plan, sell
    ):
        water = make_product("Вода", code="1-003")
        other = make_product("Кондиционер", article="200.040.05", code="2-002")
        make_plan(other, [(water, 100)])
        sell(shampoo, 300, day=1)

        summary = products.page(
            Filters(date_from=moscow(2026, 5, 1).date(),
                    date_to=moscow(2026, 5, 30).date())
        )["summary"]
        # «Кончается 1 из 2» без второго числа читалось бы как «второй
        # в порядке», а про него мы просто ничего не знаем.
        assert summary["critical_count"] == 1
        assert summary["unknown_count"] == 1
        assert summary["without_plan_count"] == 0
