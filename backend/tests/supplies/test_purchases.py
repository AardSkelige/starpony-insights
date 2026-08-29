"""Закупка — документ, а не строка в нём.

Единица счёта всего раздела: от неё зависят «закупок 5», средняя цена
и динамика. Ошибка здесь тихая — числа остаются правдоподобными.
"""

from decimal import Decimal

import pytest

from api.supplies.services import purchases, selection
from tests.supplies.conftest import moscow, position

pytestmark = pytest.mark.django_db


def grouped():
    return purchases.by_material(
        selection.supply_positions().select_related(
            "product", "uom", "document", "document__agent"
        )
    )


class TestOneDocumentIsOnePurchase:
    def test_two_lines_of_one_document_merge(self, make_supply, make_product):
        """Диметилфталат 10.03.2026: 2000 г по 40 копеек и 3000 г по 45.

        Считай мы позициями — шесть «закупок» вместо пяти и скачок цены
        40 → 45 внутри одного дня у одного поставщика, движение,
        которого не было.
        """
        material = make_product("Диметилфталат")
        supply = make_supply()
        position(supply, material, 2000, "40")
        position(supply, material, 3000, "45")

        items = grouped()[material.pk]

        assert len(items) == 1
        assert items[0].quantity == 5000
        assert items[0].amount_kopecks == 215_000

    def test_merged_price_is_weighted(self, make_supply, make_product):
        """215 000 ÷ 5000 = 43 копейки — ровно то, что заплатили за партию.

        Среднее двух цен дало бы 42,5: цифра, которой в документе нет.
        """
        material = make_product("Диметилфталат")
        supply = make_supply()
        position(supply, material, 2000, "40")
        position(supply, material, 3000, "45")

        assert grouped()[material.pk][0].price_kopecks == 43

    def test_plain_average_of_lines_is_not_the_price(self, make_supply, make_product):
        """Среднее двух цен даёт 42,5 — цифру, которой в документе нет.

        Вес — количество: 3000 г по 45 значат больше, чем 2000 г по 40.
        """
        material = make_product("Диметилфталат")
        supply = make_supply()
        position(supply, material, 2000, "40")
        position(supply, material, 3000, "45")

        price = grouped()[material.pk][0].price_kopecks
        assert price != Decimal("42.5")
        assert price * grouped()[material.pk][0].quantity == 215_000


class TestOrder:
    def test_oldest_first(self, bought):
        items = grouped()[bought.pk]
        assert [item.moment.day for item in items] == [19, 20, 21]

    def test_same_moment_is_resolved_by_document(self, make_supply, make_product):
        """У двух приёмок бывает один момент.

        Без запасного признака порядок не обязан повторяться между
        запросами — а «предыдущая цена» считается именно по соседству,
        и динамика меняла бы знак от запроса к запросу.
        """
        material = make_product("Отдушка")
        moment = moscow(2026, 6, 1)
        first = make_supply(moment=moment)
        second = make_supply(moment=moment)
        position(second, material, 10, "200")
        position(first, material, 10, "100")

        items = grouped()[material.pk]
        assert [item.document_id for item in items] == [first.pk, second.pk]


class TestFree:
    def test_zero_amount_has_no_price(self, make_supply, make_product):
        """97 позиций из 402 приходят по нулю — образцы и бонусы.

        Ноль вместо `None` обнулил бы среднюю: у этикетки Табак-Ваниль
        280 штук из 496 пришли даром.
        """
        material = make_product("Этикетка")
        position(make_supply(), material, 280, "0")

        item = grouped()[material.pk][0]
        assert item.is_free
        assert item.price_kopecks is None

    def test_priced_keeps_order_and_drops_free(self, make_supply, make_product):
        material = make_product("Этикетка")
        for day, price in ((1, "0"), (2, "1400"), (3, "0"), (4, "1500")):
            position(make_supply(moment=moscow(2026, 6, day)), material, 10, price)

        prices = [item.price_kopecks for item in purchases.priced(grouped()[material.pk])]
        assert prices == [1400, 1500]


class TestUnits:
    def test_units_of_positions_are_collected(
        self, make_supply, make_product, gram, piece
    ):
        """Материал, пришедший в разных единицах, складывать нельзя.

        Килограмм против грамма ошибается ровно в тысячу раз и на глаз
        незаметен. Сегодня таких нет ни одного — признак нужен к первому.
        """
        material = make_product("Соль")
        supply = make_supply()
        position(supply, material, 10, "100", uom=gram)
        position(supply, material, 1, "100000", uom=piece)

        assert grouped()[material.pk][0].uoms == {"г", "шт"}
