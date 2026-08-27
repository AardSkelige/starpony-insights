"""Расчёт сырья по техкартам.

Здесь считаются числа, по которым закупают. Ошибка не падает, а выражается
в лишней или недостающей закупке, поэтому проверок много и они подробные.
"""

from decimal import Decimal

import pytest

from core.models import ProcessingPlan, ProcessingPlanMaterial, Product, SyncKind, SyncRun
from core.services.materials import (
    CircularBillOfMaterials,
    direct_materials,
    explode,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def run():
    return SyncRun.objects.create(kind=SyncKind.DOCUMENTS)


@pytest.fixture
def make_product(run):
    counter = {"n": 0}

    def _make(name):
        counter["n"] += 1
        return Product.objects.create(
            ms_id=f"{counter['n']:08d}-0000-0000-0000-000000000000",
            name=name,
            last_seen_run=run,
        )

    return _make


@pytest.fixture
def make_plan(run):
    counter = {"n": 100}

    def _make(name, product, output=1, materials=()):
        counter["n"] += 1
        plan = ProcessingPlan.objects.create(
            ms_id=f"{counter['n']:08d}-0000-0000-0000-000000000000",
            name=name,
            product=product,
            output_quantity=Decimal(str(output)),
            last_seen_run=run,
        )
        for material, quantity in materials:
            ProcessingPlanMaterial.objects.create(
                plan=plan, product=material, quantity=Decimal(str(quantity))
            )
        return plan

    return _make


class TestExplode:
    def test_product_without_plan_is_the_material(self, make_product):
        """Товар, который ничем не производится, — это и есть закупаемое."""
        water = make_product("Вода")
        needs = explode(water, Decimal("5"))
        assert len(needs) == 1
        assert needs[0].product == water
        assert needs[0].quantity == Decimal("5")

    def test_single_level(self, make_product, make_plan):
        soap = make_product("Мыло")
        oil = make_product("Масло")
        make_plan("Замес мыла", soap, output=1, materials=[(oil, 10)])

        needs = explode(soap, Decimal("3"))
        assert needs[0].product == oil
        assert needs[0].quantity == Decimal("30")

    def test_semi_finished_is_unrolled_to_raw(self, make_product, make_plan):
        """Полуфабрикат раскрывается до сырья.

        Так устроено производство StarPony: сначала замес основы, потом
        розлив по флаконам. Прямой состав розлива покажет основу — а закупают
        не её, а воду и отдушку.
        """
        bottled = make_product("Шампунь во флаконе")
        base = make_product("Основа шампуня")
        water = make_product("Вода")
        bottle = make_product("Флакон")

        make_plan("Замес основы", base, output=1, materials=[(water, 200)])
        make_plan("Розлив", bottled, output=1, materials=[(base, 1), (bottle, 1)])

        needs = {n.product.name: n.quantity for n in explode(bottled, Decimal("10"))}
        assert "Основа шампуня" not in needs, "полуфабрикат обязан быть раскрыт"
        assert needs["Вода"] == Decimal("2000")
        assert needs["Флакон"] == Decimal("10")

    def test_output_quantity_is_divided(self, make_product, make_plan):
        """Расход считается на единицу, а не на прогон.

        Техкарта на 4 единицы из 100 г материала — это 25 г на единицу.
        Пропустить деление значит завысить закупку вчетверо.
        """
        item = make_product("Изделие")
        stuff = make_product("Материал")
        make_plan("Замес", item, output=4, materials=[(stuff, 100)])

        needs = explode(item, Decimal("1"))
        assert needs[0].quantity == Decimal("25")

    def test_same_material_from_different_branches_is_summed(self, make_product, make_plan):
        """Один материал из разных веток складывается, а не затирается.

        Вода входит и в основу, и в розлив — в закупке это одна строка.
        """
        final = make_product("Готовое")
        base = make_product("Основа")
        water = make_product("Вода")

        make_plan("Замес", base, output=1, materials=[(water, 100)])
        make_plan("Розлив", final, output=1, materials=[(base, 1), (water, 50)])

        needs = explode(final, Decimal("1"))
        assert len(needs) == 1
        assert needs[0].quantity == Decimal("150")

    def test_fractional_quantities_are_exact(self, make_product, make_plan):
        """Доли грамма не теряются.

        Трилон Б идёт по 0.3 г на замес: округление до целых обнулило бы
        половину состава.
        """
        item = make_product("Изделие")
        trilon = make_product("Трилон Б")
        make_plan("Замес", item, output=1, materials=[(trilon, "0.300")])

        needs = explode(item, Decimal("7"))
        assert needs[0].quantity == Decimal("2.100")

    def test_explains_itself(self, make_product, make_plan):
        """Расчётное число приходит вместе с цепочкой, по которой получено."""
        final = make_product("Готовое")
        base = make_product("Основа")
        water = make_product("Вода")
        make_plan("Замес основы", base, output=1, materials=[(water, 10)])
        make_plan("Розлив", final, output=1, materials=[(base, 1)])

        needs = explode(final, Decimal("1"))
        assert needs[0].via == [["Розлив", "Замес основы"]]

    def test_all_paths_are_explained(self, make_product, make_plan):
        """Материал из двух веток объясняет обе.

        Вода входит и в замес основы, и в розлив. Показать один путь значит
        объяснить половину числа — а по этим числам закупают.
        """
        final = make_product("Готовое")
        base = make_product("Основа")
        water = make_product("Вода")
        make_plan("Замес", base, output=1, materials=[(water, 100)])
        make_plan("Розлив", final, output=1, materials=[(base, 1), (water, 50)])

        need = explode(final, Decimal("1"))[0]
        assert need.quantity == Decimal("150")
        assert len(need.via) == 2, f"объяснён только один путь из двух: {need.via}"
        assert ["Розлив", "Замес"] in need.via
        assert ["Розлив"] in need.via

    def test_circular_plans_raise_instead_of_hanging(self, make_product, make_plan):
        """Круговая ссылка — понятная ошибка, а не зависание.

        Техкарты правят люди, и «А из Б, Б из А» рано или поздно случится.
        Без предела это повисшая страница без объяснения причины.
        """
        a = make_product("А")
        b = make_product("Б")
        make_plan("Из Б делаем А", a, output=1, materials=[(b, 1)])
        make_plan("Из А делаем Б", b, output=1, materials=[(a, 1)])

        with pytest.raises(CircularBillOfMaterials, match="по кругу"):
            explode(a, Decimal("1"))

    def test_archived_plan_is_ignored(self, make_product, make_plan):
        """Техкарта в архиве описывает то, как делали раньше.

        Считать по ней закупку — заказывать по устаревшему составу.
        """
        item = make_product("Изделие")
        stuff = make_product("Материал")
        plan = make_plan("Старый замес", item, output=1, materials=[(stuff, 10)])
        ProcessingPlan.objects.filter(pk=plan.pk).update(archived=True)

        needs = explode(item, Decimal("1"))
        assert needs[0].product == item, "архивная карта не должна участвовать"

    def test_newest_plan_wins_when_several_exist(self, make_product, make_plan):
        """Если на товар несколько карт, выбор не должен зависеть от порядка
        строк в базе: побеждает самая свежая, и так каждый раз."""
        from django.utils import timezone

        item = make_product("Изделие")
        old_stuff = make_product("Старый материал")
        new_stuff = make_product("Новый материал")

        old_plan = make_plan("Было", item, output=1, materials=[(old_stuff, 10)])
        new_plan = make_plan("Стало", item, output=1, materials=[(new_stuff, 10)])
        ProcessingPlan.objects.filter(pk=old_plan.pk).update(
            ms_updated=timezone.now() - timezone.timedelta(days=30)
        )
        ProcessingPlan.objects.filter(pk=new_plan.pk).update(ms_updated=timezone.now())

        for _ in range(3):
            needs = explode(item, Decimal("1"))
            assert needs[0].product == new_stuff, "выбор техкарты неустойчив"

    def test_deleted_plan_is_ignored(self, make_product, make_plan, run):
        """Техкарта, исчезнувшая из учёта, в расчёт не идёт."""
        item = make_product("Изделие")
        stuff = make_product("Материал")
        plan = make_plan("Замес", item, output=1, materials=[(stuff, 10)])

        from django.utils import timezone

        ProcessingPlan.objects.filter(pk=plan.pk).update(deleted_at=timezone.now())

        needs = explode(item, Decimal("1"))
        assert needs[0].product == item, "без техкарты изделие — само себе материал"


class TestDirectMaterials:
    def test_shows_semi_finished_as_is(self, make_product, make_plan):
        """Прямой состав показывает техкарту как есть, без разворачивания."""
        final = make_product("Готовое")
        base = make_product("Основа")
        water = make_product("Вода")
        make_plan("Замес", base, output=1, materials=[(water, 100)])
        make_plan("Розлив", final, output=1, materials=[(base, 2)])

        names = {m.product.name: m.quantity for m in direct_materials(final)}
        assert names == {"Основа": Decimal("2")}

    def test_no_plan_gives_empty(self, make_product):
        assert direct_materials(make_product("Вода")) == []
