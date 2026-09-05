"""Таблица «Инвентаризации»: последний пересчёт позиции и его цена.

Проверяется то, что ломается тихо: деньги, посчитанные не по той цене;
«никогда» на дне списка ровно там, где оно и есть ответ; сложение пар
«числилось — нашли» по разным пересчётам.
"""

from decimal import Decimal

import pytest

from api.inventory.services import selection
from api.inventory.services import inventory as service
from core.models import ProductKind
from tests.inventory.conftest import moscow

pytestmark = pytest.mark.django_db


def rows_of(**filters):
    return service.prepared(selection.Filters(**filters))["rows"]


def row_named(rows, name):
    return next(row for row in rows if row["name"] == name)


class TestMoney:
    """Деньги считает страница, а не учёт: в документах цена почти не стоит.

    На боевых данных цена заполнена у 10 позиций из 55 разошедшихся, и
    `correctionSum` там нулевой при живой недостаче.
    """

    def test_correction_is_multiplied_by_cost(self, make_product, make_inventory, count_position):
        product = make_product("Шампунь", cost="9415.000000")
        count_position(make_inventory(moscow(2026, 8, 6)), product,
                       calculated="9.000", counted="8.000")

        row = row_named(rows_of(), "Шампунь")

        assert row["correction"] == Decimal("-1.000")
        assert row["correction_money_kopecks"] == -9415

    def test_money_is_whole_kopecks(self, make_product, make_inventory, count_position):
        """Округление, а не усечение: дробная себестоимость — норма.

        У 150 позиций из 255 она дробная, и `int()` вместо округления
        занижал бы каждую строку.
        """
        product = make_product("Короб", cost="1789.400000")
        count_position(make_inventory(moscow(2026, 8, 6)), product,
                       calculated="10.000", counted="7.000")

        assert row_named(rows_of(), "Короб")["correction_money_kopecks"] == -5368

    def test_missing_cost_gives_none_not_zero(self, make_product, make_inventory, count_position):
        """Себестоимости нет — величина неизвестна, а не равна нулю.

        Ноль читался бы как «сошлось» ровно там, где товар пропал:
        на боевых данных таких позиций 12 из 43 разошедшихся.
        """
        product = make_product("Тубус", cost=None)
        count_position(make_inventory(moscow(2026, 8, 6)), product,
                       calculated="10.000", counted="7.000")

        row = row_named(rows_of(), "Тубус")

        assert row["correction"] == Decimal("-3.000")
        assert row["correction_money_kopecks"] is None

    def test_unpriced_rows_are_counted_in_totals(self, make_product, make_inventory, count_position):
        """Итог без числа «не оценено» выглядел бы полным."""
        inventory = make_inventory(moscow(2026, 8, 6))
        count_position(inventory, make_product("С ценой", cost="10000.000000"))
        count_position(inventory, make_product("Без цены", cost=None))

        totals = service.prepared(selection.Filters())["totals"]

        assert totals["unpriced_count"] == 1
        assert totals["money_kopecks"] == -20000

    def test_cost_travels_with_the_number(self, make_product, make_inventory, count_position):
        """Расчётное число уходит вместе с тем, чем его считали (`CLAUDE.md` §4)."""
        product = make_product("Плёнка", cost="57626.500000")
        count_position(make_inventory(moscow(2026, 8, 6)), product,
                       calculated="4.000", counted="2.000")

        assert row_named(rows_of(), "Плёнка")["cost_kopecks"] == Decimal("57626.500000")


class TestLastCount:
    def test_row_shows_the_last_count_not_the_sum(self, make_product, make_inventory, count_position):
        """«Числилось 42, нашли 5» — факт одного дня.

        Сложение таких пар по разным пересчётам дало бы число, которого
        не было ни в одном документе.
        """
        product = make_product("Короб")
        count_position(make_inventory(moscow(2026, 5, 27)), product,
                       calculated="20.000", counted="18.000")
        count_position(make_inventory(moscow(2026, 8, 6)), product,
                       calculated="42.000", counted="5.000")

        row = row_named(rows_of(), "Короб")

        assert row["calculated"] == Decimal("42.000")
        assert row["counted"] == Decimal("5.000")
        assert row["counted_times"] == 2
        assert row["diverged_times"] == 2

    def test_never_counted_row_has_no_numbers(self, make_product):
        make_product("Пигмент чёрный")

        row = row_named(rows_of(), "Пигмент чёрный")

        assert row["counted_times"] == 0
        assert row["days_ago"] is None
        assert row["last_moment"] is None
        assert row["correction"] is None


class TestOrdering:
    def test_never_counted_comes_first_by_age(self, make_product, make_inventory, count_position):
        """«Никогда» — край шкалы, а не пропуск.

        Позиция, до которой не дошли ни разу, ждёт дольше любой посчитанной.
        Уехав вниз к прочеркам, она пропала бы ровно из того порядка,
        ради которого его и включают.
        """
        count_position(make_inventory(moscow(2026, 8, 6)), make_product("Считали"))
        make_product("Не считали")

        rows = rows_of(ordering="-last")

        assert rows[0]["name"] == "Не считали"

    def test_freshest_comes_first_by_reversed_age(self, make_product, make_inventory, count_position):
        count_position(make_inventory(moscow(2026, 8, 6)), make_product("Считали"))
        make_product("Не считали")

        rows = rows_of(ordering="last")

        assert rows[0]["name"] == "Считали"

    def test_money_sorts_by_size_not_by_sign(self, make_product, make_inventory, count_position):
        """Вопрос «где сильнее не сошлось» не различает недостачу и излишек.

        Сортируй мы по знаку, крупный излишек оказался бы в самом низу —
        а это ровно такая же ошибка счёта, как недостача.
        """
        inventory = make_inventory(moscow(2026, 8, 6))
        count_position(inventory, make_product("Излишек", cost="10000.000000"),
                       calculated="0.000", counted="10.000")
        count_position(inventory, make_product("Недостача", cost="10000.000000"),
                       calculated="3.000", counted="0.000")

        rows = rows_of(ordering="-money")

        assert [row["name"] for row in rows[:2]] == ["Излишек", "Недостача"]

    def test_rows_without_money_sink(self, make_product, make_inventory, count_position):
        count_position(make_inventory(moscow(2026, 8, 6)),
                       make_product("Разошлось", cost="10000.000000"))
        make_product("Не считали")

        rows = rows_of(ordering="-money")

        assert rows[-1]["name"] == "Не считали"


class TestSelection:
    def test_services_and_archived_are_out(self, make_product):
        """Отбор общим определением: услугу не пересчитывают, архив не выпускают."""
        make_product("Товар")
        make_product("Доставка", kind=ProductKind.SERVICE)
        make_product("Снят с производства", archived=True)

        assert [row["name"] for row in rows_of()] == ["Товар"]

    def test_raw_materials_are_in(self, make_product):
        """Сырьё — то, что не считают чаще всего: 110 из 239 непересчитанных."""
        make_product("Масло макадамии", folder="Производство/Сырьё")

        assert [row["name"] for row in rows_of()] == ["Масло макадамии"]

    def test_store_narrows_counts_not_products(self, make_product, make_inventory, count_position):
        """Склад сужает пересчёты, а не номенклатуру.

        Складов три, номенклатура общая: позиция, посчитанная на «Хоз
        товарах», на «Производстве» не считалась — и обязана быть видна там
        как непересчитанная, иначе «что не считали на этом складе» не спросить.
        """
        product = make_product("Короб")
        count_position(make_inventory(moscow(2026, 8, 6), store="Хоз товары"), product)

        rows = rows_of(store="Производство")

        assert [row["name"] for row in rows] == ["Короб"]
        assert rows[0]["counted_times"] == 0

    def test_folder_narrows_products(self, make_product):
        make_product("Короб", folder="Хоз. товары/Упаковка")
        make_product("Масло", folder="Производство/Сырьё")

        assert [row["name"] for row in rows_of(folder="Производство/Сырьё")] == ["Масло"]

    def test_search_narrows_totals_too(self, make_product, make_inventory, count_position):
        """Итог под таблицей обязан сходиться со сложением колонки."""
        inventory = make_inventory(moscow(2026, 8, 6))
        count_position(inventory, make_product("Короб", cost="10000.000000"))
        count_position(inventory, make_product("Плёнка", cost="20000.000000"))

        totals = service.prepared(selection.Filters(search="Короб"))["totals"]

        assert totals["products_count"] == 1
        assert totals["money_kopecks"] == -20000

    def test_deleted_inventory_is_ignored(self, make_product, make_inventory, count_position):
        """Документ, исчезнувший из учёта, не считается пересчётом."""
        from django.utils import timezone

        product = make_product("Короб")
        inventory = make_inventory(moscow(2026, 8, 6))
        count_position(inventory, product)
        inventory.deleted_at = timezone.now()
        inventory.save(update_fields=["deleted_at"])

        assert row_named(rows_of(), "Короб")["counted_times"] == 0


class TestUnits:
    """Единица измерения едет вместе с количеством.

    «Числилось 5 730» у изопропилового спирта — это граммы, а у короба —
    штуки. Ошибка здесь ровно в 1000 раз и на глаз незаметна.
    """

    def test_unit_travels_with_the_row(self, make_product, make_inventory, count_position, run):
        from core.models import Uom

        gram = Uom.objects.create(
            ms_id="00000000-0000-0000-0000-0000000000f1", name="г", last_seen_run=run
        )
        product = make_product("Изопропиловый спирт")
        product.uom = gram
        product.save(update_fields=["uom"])
        count_position(make_inventory(moscow(2026, 6, 3)), product,
                       calculated="5730.000", counted="3500.000")

        assert row_named(rows_of(), "Изопропиловый спирт")["uom"] == "г"

    def test_missing_unit_is_empty_not_broken(self, make_product):
        make_product("Без единицы")

        assert row_named(rows_of(), "Без единицы")["uom"] == ""


class TestUnpricedMeaning:
    """«Не оценено» в итоге и в блоке — одно и то же число.

    Считаются только расхождения без себестоимости. Позиция, которая
    сошлась, оценивать нечего: попав в счётчик, она раздувала бы его втрое —
    35 вместо 12 на боевых данных, — и подвал таблицы спорил бы с блоком
    под ней, оставаясь формально верным.
    """

    def test_matched_row_without_cost_is_not_unpriced(
        self, make_product, make_inventory, count_position
    ):
        count_position(make_inventory(moscow(2026, 8, 6)),
                       make_product("Сошлось без цены", cost=None),
                       calculated="5.000", counted="5.000")

        assert service.prepared(selection.Filters())["totals"]["unpriced_count"] == 0

    def test_totals_and_block_agree(self, make_product, make_inventory, count_position):
        from api.inventory.services import blocks

        inventory = make_inventory(moscow(2026, 8, 6))
        count_position(inventory, make_product("Разошлось без цены", cost=None))
        count_position(inventory, make_product("Сошлось без цены", cost=None),
                       calculated="5.000", counted="5.000")

        rows = service.prepared(selection.Filters())["rows"]

        assert service.totals(rows)["unpriced_count"] == blocks.worst(rows)["unpriced_count"] == 1
