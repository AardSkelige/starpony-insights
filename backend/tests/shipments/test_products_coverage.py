"""Сводка и охват расчёта на «Товарах в отгрузках».

Три числа, и каждое отвечает на вопрос, который страница иначе оставляет
без ответа: сколько всего продано, всё ли доехало из учёта и сколько
из показанного ещё не продано.

Ошибки здесь тихие все три. Сводка, сузившаяся поиском, выглядит обычным
числом. Потерянная синхронизацией позиция не видна нигде, кроме сверки
с суммой документа. Реализация, посчитанная за период, даёт вычитание,
в котором уменьшаемое и вычитаемое про разные множества.
"""

import pytest

from api.shipments.services import products
from core.models import ContractType, DocumentKind
from tests.shipments.conftest import position

pytestmark = pytest.mark.django_db


class TestSelectionNotSearch:
    """Сводка описывает выборку, итог — показанное. Это разные множества."""

    @pytest.fixture
    def two_products(self, make_product, make_demand):
        shampoo = make_product("Шампунь 500 мл", article="100.001", code="2-001")
        brush = make_product("Щётка", article="200.001", code="3-001")
        position(make_demand(total_kopecks=250_00), shampoo, "1", 250_00)
        position(make_demand(total_kopecks=750_00), brush, "1", 750_00)

    def test_поиск_сводку_не_сужает(self, two_products):
        """Итог считает найденное, сводка — всю выборку.

        Возьми сводка поиск в расчёт — «продано на 250 ₽» стояло бы там,
        где продали на тысячу, и отличить это от настоящего падения продаж
        было бы нечем.
        """
        page = products.page(products.Filters(search="шампунь"))

        assert page["totals"]["revenue_kopecks"] == 250_00
        assert page["coverage"]["revenue_kopecks"] == 1000_00
        assert page["coverage"]["products_count"] == 2

    def test_канал_сводку_сужает(self, make_product, make_demand, channel):
        """Канал — часть выборки, а не поиск по ней."""
        position(
            make_demand(channel=channel, total_kopecks=250_00),
            make_product(code="2-001"),
            "1",
            250_00,
        )
        position(make_demand(total_kopecks=750_00), make_product(code="3-001"), "1", 750_00)

        coverage = products.page(products.Filters(channel_id=channel.pk))["coverage"]

        assert coverage["revenue_kopecks"] == 250_00
        assert coverage["products_count"] == 1


class TestPositionsAgreeWithDocuments:
    """Сумма позиций против суммы самих отгрузок — сверка с учётом.

    Единственное место, где видна потерянная синхронизацией позиция:
    в остальных числах страницы её отсутствие выглядит просто меньшей
    выручкой (`CLAUDE.md` §9).
    """

    def test_сходятся_до_копейки(self, make_product, make_demand):
        document = make_demand(total_kopecks=500_00)
        position(document, make_product(code="2-001"), "1", 300_00)
        position(document, make_product(code="3-001"), "1", 200_00)

        coverage = products.page(products.Filters())["coverage"]

        assert coverage["revenue_kopecks"] == 500_00
        assert coverage["documents_revenue_kopecks"] == 500_00

    def test_потерянная_позиция_видна(self, make_product, make_demand):
        """Документ на 500 ₽, а позиций доехало на 300: разница обязана быть."""
        position(make_demand(total_kopecks=500_00), make_product(), "1", 300_00)

        coverage = products.page(products.Filters())["coverage"]

        assert coverage["revenue_kopecks"] == 300_00
        assert coverage["documents_revenue_kopecks"] == 500_00

    def test_сверяются_по_одной_выборке(self, make_product, make_demand, channel):
        """Обе стороны сужаются каналом вместе.

        Сузь одну — сверка сравнивала бы позиции Озона с документами всех
        каналов и показывала бы потерю там, где её нет.
        """
        position(
            make_demand(channel=channel, total_kopecks=250_00),
            make_product(code="2-001"),
            "1",
            250_00,
        )
        position(make_demand(total_kopecks=750_00), make_product(code="3-001"), "1", 750_00)

        coverage = products.page(products.Filters(channel_id=channel.pk))["coverage"]

        assert coverage["revenue_kopecks"] == coverage["documents_revenue_kopecks"]


class TestFreePositions:
    """Позиции, ушедшие даром. Без них выручка выглядит заниженной."""

    def test_считаются_отдельно(self, make_product, make_demand):
        document = make_demand(total_kopecks=300_00)
        position(document, make_product(code="2-001"), "1", 300_00)
        position(document, make_product(code="3-001"), "2", 0)

        coverage = products.page(products.Filters())["coverage"]

        assert coverage["positions_count"] == 2
        assert coverage["free_positions_count"] == 1


class TestConsignmentOutstanding:
    """Вычитание по товару на реализации — то же, что на «Каналах продаж»."""

    def test_вычитание_сходится(
        self, make_product, make_demand, make_agent, commission
    ):
        position(
            make_demand(contract=commission, total_kopecks=452_696),
            make_product(),
            "1",
            452_696,
        )
        make_demand(
            kind=DocumentKind.COMMISSION_REPORT,
            contract=commission,
            total_kopecks=171_570,
        )

        outstanding = products.page(products.Filters())["coverage"][
            "consignment_outstanding"
        ]

        assert outstanding.shipped_kopecks == 452_696
        assert outstanding.reported_kopecks == 171_570
        assert outstanding.pending_kopecks == 281_126

    def test_период_вычитание_не_сужает(
        self, make_product, make_demand, commission
    ):
        """Отчёт приходит позже отгрузки, часто в следующем месяце.

        Сузь обе величины периодом — «отгружено за май» сравнивалось бы
        с отчётами за апрель, то есть два разных множества в одном
        вычитании (`DESIGN.md` §8).
        """
        position(
            make_demand(contract=commission, total_kopecks=100_00),
            make_product(),
            "1",
            100_00,
        )
        make_demand(
            kind=DocumentKind.COMMISSION_REPORT,
            contract=commission,
            total_kopecks=40_00,
        )

        narrow = products.page(
            products.Filters(date_from=None, date_to=None, search="ничего-не-найдётся")
        )["coverage"]["consignment_outstanding"]

        assert narrow.pending_kopecks == 60_00


def test_договор_купли_продажи_реализацией_не_считается(
    make_product, make_demand, run, agent
):
    """Умолчание — продажа: договор комиссии есть у двоих контрагентов из 107."""
    from core.models import Contract

    sales = Contract.objects.create(
        ms_id="00000000-0000-0000-0000-0000000000c2",
        name="00002",
        contract_type=ContractType.SALES,
        agent=agent,
        last_seen_run=run,
    )
    position(make_demand(contract=sales, total_kopecks=100_00), make_product(), "1", 100_00)

    coverage = products.page(products.Filters())["coverage"]

    assert coverage["consignment_outstanding"].shipped_kopecks == 0


class TestFreeValue:
    """Во что обошлась раздача. «266 позиций» в деньги не переводится сама."""

    def test_считается_по_цене_платных_продаж_того_же_товара(
        self, make_product, make_demand
    ):
        """Десять штук продали по 100 ₽, две отдали — раздача на 200 ₽.

        Цена своя у каждого товара, а не общая по чеку: раздают дешёвое
        и дорогое в разной пропорции, и одна цена на всех дала бы число,
        которое ни на что не опирается.
        """
        product = make_product()
        position(make_demand(total_kopecks=1000_00), product, "10", 1000_00)
        position(make_demand(), product, "2", 0)

        coverage = products.page(products.Filters())["coverage"]

        assert coverage["free_value_kopecks"] == 200_00
        assert coverage["free_unpriced_products_count"] == 0

    def test_цены_у_каждого_товара_своя(self, make_product, make_demand):
        shampoo = make_product("Шампунь", code="2-001")
        brush = make_product("Щётка", code="3-001")
        position(make_demand(total_kopecks=1000_00), shampoo, "10", 1000_00)
        position(make_demand(), shampoo, "1", 0)
        position(make_demand(total_kopecks=20_00), brush, "10", 20_00)
        position(make_demand(), brush, "1", 0)

        coverage = products.page(products.Filters())["coverage"]

        # 100 ₽ за шампунь плюс 2 ₽ за щётку, а не среднее по обоим.
        assert coverage["free_value_kopecks"] == 102_00

    def test_товар_который_только_раздавали_считается_отдельно(
        self, make_product, make_demand
    ):
        """Цены нет — придумывать её нельзя, но и молчать нельзя.

        Молчание здесь занижает сумму, и объяснить разницу человеку
        было бы нечем.
        """
        position(make_demand(), make_product(code="2-001"), "5", 0)

        coverage = products.page(products.Filters())["coverage"]

        assert coverage["free_value_kopecks"] == 0
        assert coverage["free_unpriced_products_count"] == 1

    def test_округление_одно_на_всю_сумму(self, make_product, make_demand):
        """Цена штуки бывает долями копейки, и округлять можно только в конце.

        Два товара по 0,4 копейки — это копейка. Округли на каждом товаре,
        и оба обнулятся: раздача мелочёвки исчезнет целиком, а по 89
        техкартам такая ошибка ложится прямо в расчёт (`CLAUDE.md` §3).
        """
        for code in ("2-001", "3-001"):
            product = make_product(code=code)
            # Пять штук за копейку — 0,2 копейки за штуку.
            position(make_demand(total_kopecks=1), product, "5", 1)
            position(make_demand(), product, "2", 0)

        coverage = products.page(products.Filters())["coverage"]

        assert coverage["free_value_kopecks"] == 1

    def test_поиск_стоимость_раздачи_не_сужает(self, make_product, make_demand):
        """Как и всё в этом блоке: сводка — про выборку, а не про найденное."""
        shampoo = make_product("Шампунь", code="2-001")
        brush = make_product("Щётка", code="3-001")
        position(make_demand(total_kopecks=1000_00), shampoo, "10", 1000_00)
        position(make_demand(), shampoo, "1", 0)
        position(make_demand(total_kopecks=1000_00), brush, "10", 1000_00)
        position(make_demand(), brush, "1", 0)

        coverage = products.page(products.Filters(search="щётка"))["coverage"]

        assert coverage["free_value_kopecks"] == 200_00
