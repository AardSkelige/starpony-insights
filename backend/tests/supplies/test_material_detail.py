"""Разбор строки: слагаемые обязаны сходиться с объясняемым числом.

Объяснение, которое не складывается обратно, объяснением не является —
урок соседней страницы, где панель показывала 20 источников из 59 и молча
теряла 452 килограмма.
"""

from decimal import Decimal

import pytest

from api.supplies.services import material_detail, materials
from tests.supplies.conftest import moscow, position

pytestmark = pytest.mark.django_db


def detail(material, filters=None):
    return material_detail.detail(filters or materials.Filters(), material.pk)


class TestHistoryAddsUp:
    def test_amounts_sum_to_the_row(self, bought):
        """Сложите суммы приёмок — получите сумму строки."""
        payload = detail(bought)
        assert sum(item["amount_kopecks"] for item in payload["history"]) == payload[
            "amount_kopecks"
        ]

    def test_quantities_sum_to_the_row(self, bought):
        payload = detail(bought)
        assert sum(
            (item["quantity"] for item in payload["history"]), Decimal(0)
        ) == payload["quantity"]

    def test_history_is_chronological(self, bought):
        """История цен читается слева направо: старое сначала."""
        payload = detail(bought)
        assert [item["moment"].day for item in payload["history"]] == [19, 20, 21]

    def test_free_purchase_has_no_price_and_no_change(self, make_supply, make_product):
        label = make_product("Этикетка")
        position(make_supply(moment=moscow(2026, 5, 1)), label, 100, "1400")
        position(make_supply(moment=moscow(2026, 6, 1)), label, 30, "0")

        free = detail(label)["history"][1]
        assert free["is_free"] is True
        assert free["price_kopecks"] is None
        assert free["price_change"] is None

    def test_change_skips_the_free_purchase(self, make_supply, make_product):
        """База сравнения — предыдущая цена, а не предыдущая приёмка.

        Иначе после бесплатной допечатки цена «выросла с нуля».
        """
        label = make_product("Этикетка")
        position(make_supply(moment=moscow(2026, 5, 1)), label, 100, "2000")
        position(make_supply(moment=moscow(2026, 6, 1)), label, 30, "0")
        position(make_supply(moment=moscow(2026, 7, 1)), label, 100, "2400")

        assert detail(label)["history"][2]["price_change"] == Decimal("0.2")


class TestSuppliers:
    @pytest.fixture
    def spirit(self, make_supply, make_product, make_supplier):
        """Изопропиловый спирт с боевых: три поставщика, шесть закупок."""
        material = make_product("Изопропиловый спирт")
        rows = (
            ("ООО «Интернет Решения»", 5, 14, "2491"),
            ("ООО «Интернет Решения»", 5, 15, "2400"),
            ("Алещенко Иван", 6, 10, "3000"),
            ("ООО «Всеинструменты»", 7, 30, "2202"),
        )
        agents = {}
        for name, month, day, price in rows:
            agent = agents.setdefault(name, make_supplier(name))
            position(
                make_supply(agent=agent, moment=moscow(2026, month, day)),
                material,
                1000,
                price,
            )
        return material

    def test_cheapest_last_price_first(self, spirit):
        """Список читают как «у кого брать» — дешёвый сверху."""
        names = [item["name"] for item in detail(spirit)["suppliers"]]
        assert names == [
            "ООО «Всеинструменты»",
            "ООО «Интернет Решения»",
            "Алещенко Иван",
        ]

    def test_above_best_is_zero_for_the_cheapest(self, spirit):
        """Ноль здесь верен и означает «он и есть лучший»."""
        assert detail(spirit)["suppliers"][0]["above_best"] == 0

    def test_above_best_compares_last_prices(self, spirit):
        """2400 против 2202 — плюс девять процентов."""
        second = detail(spirit)["suppliers"][1]
        assert round(second["above_best"], 4) == Decimal("0.0899")

    def test_last_price_is_the_latest_of_that_supplier(self, spirit):
        """У «Интернет Решений» две закупки: 24,91 и 24,00. Берётся вторая."""
        second = detail(spirit)["suppliers"][1]
        assert second["supplies_count"] == 2
        assert second["last_price_kopecks"] == 2400

    def test_spread_is_between_suppliers_not_across_time(
        self, make_supply, make_product, make_supplier
    ):
        """«Крышка флип-топ»: 5,19 → 9,00 у одного «Лемуна».

        Считай мы крайние цены вообще, разброс вышел бы 73% — и это
        предложение уйти от «Лемуна» к «Лемуну».
        """
        material = make_product("Крышка флип-топ")
        lemun = make_supplier("ООО «Лемун»")
        position(make_supply(agent=lemun, moment=moscow(2026, 3, 1)), material, 100, "519")
        position(make_supply(agent=lemun, moment=moscow(2026, 8, 1)), material, 100, "900")

        rows = detail(material)["suppliers"]
        assert len(rows) == 1
        assert rows[0]["above_best"] == 0

    def test_free_only_supplier_has_no_price(self, make_supply, make_product, make_supplier):
        """Подарок — не предложение, и в сравнении цен он не участвует."""
        label = make_product("Этикетка")
        printer = make_supplier("Принтец")
        typography = make_supplier("ООО «Типография»")
        position(make_supply(agent=printer), label, 280, "0")
        position(make_supply(agent=typography), label, 100, "1400")

        rows = detail(label)["suppliers"]
        assert rows[0]["name"] == "ООО «Типография»"
        # Безценовые вниз: сказать про них «дороже» или «дешевле» нечего.
        assert rows[1]["name"] == "Принтец"
        assert rows[1]["last_price_kopecks"] is None
        assert rows[1]["above_best"] is None


class TestSelection:
    def test_detail_follows_the_page_filters(self, bought):
        """Разбор за апрель не должен объяснять строку за весь период.

        Иначе слагаемые не сойдутся с числом, которое они объясняют.
        """
        filters = materials.Filters(
            date_from=moscow(2026, 4, 20).date(), date_to=moscow(2026, 4, 21).date()
        )
        payload = detail(bought, filters)
        assert len(payload["history"]) == 2
        assert payload["quantity"] == Decimal("2000.000")

    def test_material_outside_the_selection_is_refused(self, bought):
        """Пустые блоки читались бы как «не закупался никогда»."""
        filters = materials.Filters(date_from=moscow(2026, 7, 1).date())
        with pytest.raises(material_detail.MaterialNotPurchased):
            detail(bought, filters)


class TestQueries:
    def test_detail_costs_a_fixed_number_of_queries(
        self, bought, django_assert_num_queries
    ):
        """Шесть запросов на раскрытие строки, и ни одного на её содержимое.

        Было два — позиции и остаток. Четыре добавил запас в днях: расход
        берётся из отгрузок через техкарты, а это отгрузки, техкарты, их
        материалы и границы периода. Цена осознанная: «пора ли закупать» —
        главный вопрос страницы, и остаток без скорости расхода на него
        не отвечает.

        Число закреплено не ради самого числа, а чтобы **рост был заметен**:
        N+1 внутри разворота техкарт добавил бы запрос на каждое изделие,
        и на боевых данных это шестьдесят шесть запросов вместо четырёх.
        """
        with django_assert_num_queries(6):
            detail(bought)
