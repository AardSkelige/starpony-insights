"""Расчёт маржи: подарки, реализация, площадки, неизвестная себестоимость.

Каждая ошибка здесь тихая. Маржа выглядит правдоподобно при любой из них:
включённые подарки занижают её у каждого четвёртого товара, товар
на реализации завышает выручку на 281 126 ₽, а нулевая себестоимость
вместо неизвестной даёт ровно 100 % — самое опасное число на странице.
"""

from datetime import date
from decimal import Decimal

import pytest

from api.profitability.services.profitability import page
from api.profitability.services.selection import Basis, Filters

from .conftest import DAY, moscow, position

pytestmark = pytest.mark.django_db


def rows_by_article(payload) -> dict:
    return {row["article"]: row for row in payload["results"]}


class TestWhatCountsAsAProduct:
    """Товар — это то, у чего есть артикул. Решение владельца 02.09."""

    def test_service_is_not_a_product(self, make_product, make_profit_day):
        """Услуга дала бы маржу 100 %: себестоимости у неё не бывает.

        «Доставка» приносит 12 970 ₽ и возглавила бы список «на чём
        зарабатываем» — неправда о продукте, которую никакая арифметика
        не поймает.
        """
        delivery = make_product(name="Доставка", article="", kind="service")
        make_profit_day(product=delivery, quantity="22", revenue_kopecks=957_000,
                        cost_kopecks=0)

        assert page(Filters())["count"] == 0

    def test_product_with_article_is_counted(self, product, make_profit_day):
        make_profit_day()

        assert page(Filters())["count"] == 1


class TestFreeGoods:
    """Отданное даром: себестоимость настоящая, выручки нет вовсе."""

    @pytest.fixture
    def sold_and_given(self, product, make_profit_day, make_demand):
        """10 штук проданы, 4 из них отданы даром. Себестоимость 300 ₽ за штуку."""
        make_profit_day(quantity="10", revenue_kopecks=54_936, cost_kopecks=300_000)
        paid = make_demand(moment=moscow(2026, 7, 15))
        position(paid, product, 6, 9_156)
        gift = make_demand(moment=moscow(2026, 7, 15))
        position(gift, product, 4, 0)
        return product

    def test_gifts_are_excluded_by_default(self, sold_and_given):
        """Умолчание — без подарков: вопрос страницы про цену, а не про щедрость."""
        row = page(Filters())["results"][0]

        assert row["quantity"] == Decimal("6.000")
        # Выручку править не надо — у подарка её нет: она вся от платных штук.
        assert row["revenue_kopecks"] == 54_936
        # Себестоимость — доля платных штук: 6 из 10 при 300 000 копейках.
        assert row["cost_kopecks"] == 180_000
        assert row["profit_kopecks"] == 54_936 - 180_000

    def test_gifts_are_counted_when_asked(self, sold_and_given):
        row = page(Filters(with_free=True))["results"][0]

        assert row["quantity"] == Decimal("10.000")
        assert row["cost_kopecks"] == 300_000

    def test_gift_cost_is_reported_either_way(self, sold_and_given):
        """Сколько стоило отданное — видно всегда, при любом переключателе.

        Иначе выключенные подарки означали бы, что 86 610 ₽ себестоимости
        исчезли с экрана без следа.
        """
        for filters in (Filters(), Filters(with_free=True)):
            coverage = page(filters)["coverage"]
            assert coverage["free_quantity"] == Decimal("4.000")
            assert coverage["free_cost_kopecks"] == 120_000

    def test_product_given_only_for_free_leaves_the_table(
        self, product, make_profit_day, make_demand
    ):
        """Товар, ушедший только даром, — не строка про заработок.

        Четыре позиции «Амуниция» уходили исключительно даром, и при
        выключенных подарках от них остаются одни нули. Скрыты, но
        сосчитаны: число обязано сходиться.
        """
        make_profit_day(quantity="3", revenue_kopecks=0, cost_kopecks=60_799)
        gift = make_demand(moment=moscow(2026, 7, 15))
        position(gift, product, 3, 0)

        payload = page(Filters())

        assert payload["count"] == 0
        assert payload["coverage"]["hidden_products_count"] == 1
        assert payload["coverage"]["free_quantity"] == Decimal("3.000")


class TestConsignment:
    """Товар на реализации: отгружен, но ещё не продан."""

    @pytest.fixture
    def consigned(self, product, make_profit_day, make_demand, make_contract):
        """Отгружено по комиссии 10 штук, комиссионер продал 4."""
        contract = make_contract()
        shipment = make_demand(moment=moscow(2026, 7, 15), contract=contract)
        position(shipment, product, 10, 65_000)
        report = make_demand(
            moment=moscow(2026, 7, 20), contract=contract,
            kind="commission_report",
        )
        position(report, product, 4, 65_000)
        make_profit_day(quantity="4", revenue_kopecks=260_000, cost_kopecks=100_000)
        return product

    def test_sold_basis_counts_only_what_the_commissioner_sold(self, consigned):
        """Деньги за товар — по отчёту комиссионера, а не по отгрузке.

        Ровно этим «Прибыльность» отличается от «Товаров в отгрузках»:
        там 1 292 550 ₽, здесь 1 011 424 ₽, и обе цифры верны.
        """
        row = page(Filters())["results"][0]

        assert row["quantity"] == Decimal("4.000")
        assert row["revenue_kopecks"] == 260_000

    def test_unsold_part_is_named_not_hidden(self, consigned):
        """Непроданное обязано быть числом на экране, а не расхождением.

        Иначе человек сравнит страницы, увидит разницу в 281 126 ₽
        и решит, что одна из них врёт.
        """
        row = page(Filters())["results"][0]

        assert row["unsold_quantity"] == Decimal("6.000")
        assert row["unsold_kopecks"] == 390_000

    def test_shipped_basis_counts_everything_that_left(self, consigned):
        row = page(Filters(basis=Basis.SHIPPED))["results"][0]

        assert row["quantity"] == Decimal("10.000")
        assert row["revenue_kopecks"] == 650_000
        # Себестоимость отгруженного — расчётная: МойСклад считает её только
        # проданному. Признак приходит с сервера, чтобы оговорка на экране
        # не разошлась с правилом расчёта.
        assert row["cost_is_estimated"] is True
        # 10 штук по средней 25 000 копеек за штуку (100 000 за 4).
        assert row["cost_kopecks"] == 250_000

    def test_report_covering_an_earlier_shipment_does_not_go_negative(
        self, product, make_profit_day, make_demand, make_contract
    ):
        """Комиссионер продал больше, чем взял в этом периоде, — это не минус.

        Отчёт может закрывать отгрузку прошлого месяца. Минус в колонке
        «на реализации» читался бы как ошибка данных.
        """
        contract = make_contract()
        report = make_demand(moment=moscow(2026, 7, 20), contract=contract,
                             kind="commission_report")
        position(report, product, 4, 65_000)
        make_profit_day(quantity="4", revenue_kopecks=260_000, cost_kopecks=100_000)

        row = page(Filters())["results"][0]

        assert row["unsold_quantity"] == Decimal(0)
        assert row["unsold_kopecks"] == 0


class TestMarketplaces:
    """Маржа через площадки завышена на весь их процент."""

    def test_marketplace_part_is_a_subset_not_a_neighbour(
        self, product, make_profit_day
    ):
        """Площадки — часть строки, а не соседняя строка.

        Соседней они дали бы двойной счёт: выручка через Озон вошла бы
        и в общую сумму, и в свою собственную.
        """
        make_profit_day(quantity="10", revenue_kopecks=100_000, cost_kopecks=30_000,
                        marketplace_quantity="4", marketplace_revenue_kopecks=60_000,
                        marketplace_cost_kopecks=10_000)

        payload = page(Filters())
        row, mk = payload["results"][0], payload["marketplaces"]

        assert row["marketplace_revenue_kopecks"] <= row["revenue_kopecks"]
        assert mk["marketplace_revenue_kopecks"] == 60_000
        # Прямые продажи — разность, а не отдельный запрос: два способа
        # получить одно число разошлись бы.
        assert mk["direct_revenue_kopecks"] == 40_000
        assert mk["direct_cost_kopecks"] == 20_000

    def test_both_margins_are_reported_separately(self, product, make_profit_day):
        """Одно число на всех смешало бы факт с завышенным."""
        make_profit_day(quantity="10", revenue_kopecks=100_000, cost_kopecks=30_000,
                        marketplace_quantity="4", marketplace_revenue_kopecks=60_000,
                        marketplace_cost_kopecks=10_000)

        mk = page(Filters())["marketplaces"]

        assert mk["marketplace_margin"] == Decimal(50_000) / Decimal(60_000)
        assert mk["direct_margin"] == Decimal(20_000) / Decimal(40_000)


class TestUnknownCost:
    """Неизвестная себестоимость — `None`, и никогда ноль."""

    def test_never_reports_hundred_percent_margin(
        self, product, make_demand, make_profit_day
    ):
        """Ноль себестоимости дал бы маржу 100 % — самое опасное число здесь.

        Товар отгружали, но ни разу не продали: в отчёте прибыльности его
        нет, и средней цены единицы взять неоткуда.
        """
        shipment = make_demand(moment=moscow(2026, 7, 15))
        position(shipment, product, 5, 65_000)

        row = page(Filters(basis=Basis.SHIPPED))["results"][0]

        assert row["cost_kopecks"] is None
        assert row["profit_kopecks"] is None
        assert row["margin"] is None

    def test_revenue_without_cost_is_named_in_totals(
        self, product, make_demand
    ):
        """Выручка без себестоимости обязана быть видна отдельным числом.

        Иначе маржа считается по части выборки, а выглядит как по всей, —
        дефект «соседние числа о разных множествах», найденный шесть раз
        за четыре сессии.
        """
        shipment = make_demand(moment=moscow(2026, 7, 15))
        position(shipment, product, 5, 65_000)

        totals = page(Filters(basis=Basis.SHIPPED))["totals"]

        assert totals["revenue_without_cost_kopecks"] == 325_000
        assert totals["margin"] is None

    def test_unknown_margin_sorts_last_in_both_directions(
        self, make_product, make_profit_day, make_demand
    ):
        """Строка без маржи не должна возглавлять список самых прибыльных.

        Обе строки обязаны попасть в таблицу — иначе тест сравнивает
        единственную строку с самой собой и проходит вхолостую. На этом
        он и был пойман проверкой на покраснение.
        """
        good = make_product(name="Репеллент", article="300.001.05")
        make_profit_day(product=good, quantity="10", revenue_kopecks=100_000,
                        cost_kopecks=30_000)
        unknown = make_product(name="Воск", article="400.003.15")
        shipment = make_demand(moment=moscow(2026, 7, 15))
        position(shipment, good, 10, 10_000)
        position(shipment, unknown, 5, 65_000)

        for ordering in ("-margin", "margin"):
            rows = page(Filters(basis=Basis.SHIPPED, ordering=ordering))["results"]
            assert len(rows) == 2, "обе строки должны быть в таблице"
            assert rows[-1]["article"] == "400.003.15", ordering


class TestTotalsAddUp:
    """Показанное обязано складываться в показанный итог."""

    @pytest.fixture
    def three_products(self, make_product, make_profit_day):
        for i, (revenue, cost) in enumerate(
            ((100_000, 30_000), (50_000, 20_000), (30_000, 25_000)), start=1
        ):
            product = make_product(name=f"Товар {i}", article=f"300.00{i}.05")
            make_profit_day(product=product, quantity="10",
                            revenue_kopecks=revenue, cost_kopecks=cost)

    def test_column_sums_to_the_footer(self, three_products):
        payload = page(Filters(page_size=200))
        column = sum(row["profit_kopecks"] for row in payload["results"])

        assert column == payload["totals"]["profit_kopecks"]

    def test_shares_add_up_to_one(self, three_products):
        payload = page(Filters(page_size=200))

        assert sum(row["profit_share"] for row in payload["results"]) == Decimal(1)

    def test_search_narrows_rows_but_not_the_share(self, three_products):
        """Знаменатель доли не сужается поиском.

        Иначе, найдя один товар, человек увидел бы «100 %» — дефект,
        пойманный на трёх страницах подряд.
        """
        payload = page(Filters(search="Товар 1", page_size=200))

        assert payload["count"] == 1
        # 70 000 из 105 000 прибыли всей выборки, а не из самой себя.
        assert payload["results"][0]["profit_share"] == Decimal(70_000) / Decimal(105_000)


class TestPeriod:
    """Период режет строки отчёта по дню, а не по моменту."""

    def test_days_outside_the_period_do_not_count(self, product, make_profit_day):
        make_profit_day(day=DAY, revenue_kopecks=100_000, cost_kopecks=30_000)
        make_profit_day(day=date(2026, 8, 20), revenue_kopecks=50_000,
                        cost_kopecks=10_000)

        payload = page(Filters(date_from=DAY, date_to=DAY))

        assert payload["totals"]["revenue_kopecks"] == 100_000

    def test_boundaries_are_inclusive(self, product, make_profit_day):
        """Обе границы входят: день выбран человеком, а не отрезком времени."""
        make_profit_day(day=DAY, revenue_kopecks=100_000, cost_kopecks=30_000)

        payload = page(Filters(date_from=DAY, date_to=DAY))

        assert payload["count"] == 1


class TestLosses:
    """Проданное в минус — отдельным списком, а не сортировкой."""

    def test_losing_products_are_listed_separately(self, make_product, make_profit_day):
        """Страница открывается лидерами, и убыточная строка шестидесятой
        осталась бы незамеченной (`PRD.md` §5.10)."""
        winner = make_product(name="Репеллент", article="300.001.05")
        make_profit_day(product=winner, revenue_kopecks=100_000, cost_kopecks=30_000)
        loser = make_product(name="Воск", article="400.003.15")
        make_profit_day(product=loser, revenue_kopecks=10_000, cost_kopecks=25_000)

        losses = page(Filters())["losses"]

        assert [row["article"] for row in losses] == ["400.003.15"]
        assert losses[0]["profit_kopecks"] == -15_000


class TestFamilies:
    """Линейка — последнее звено пути группы."""

    def test_family_is_the_group_itself_not_the_path_to_it(
        self, make_product, make_profit_day
    ):
        """«Готовая продукция/Репеллент» — это «Репеллент».

        Полный путь превратил бы семь линеек в семь подписей, различающихся
        концом, а первое звено — в одну «Готовую продукцию» на всех.
        """
        repellent = make_product(article="300.001.05",
                                 folder="Готовая продукция/Репеллент")
        make_profit_day(product=repellent, revenue_kopecks=100_000, cost_kopecks=30_000)
        shampoo = make_product(article="100.001.05",
                               folder="Готовая продукция/Шампунь для лошадей")
        make_profit_day(product=shampoo, revenue_kopecks=50_000, cost_kopecks=20_000)

        families = page(Filters())["families"]

        assert [f["name"] for f in families] == ["Репеллент", "Шампунь для лошадей"]

    def test_product_outside_groups_is_named(self, make_product, make_profit_day):
        """Пустая подпись на полосе — это не ответ."""
        product = make_product(article="900.001.05", folder="")
        make_profit_day(product=product, revenue_kopecks=100_000, cost_kopecks=30_000)

        assert page(Filters())["families"][0]["name"] == "Без группы"


class TestMostGivenAway:
    """Чего стоят подарки — по всей выборке, а не по показанной странице."""

    def test_looks_beyond_the_first_page(
        self, make_product, make_profit_day, make_demand
    ):
        """Список считается на сервере именно поэтому.

        Собранный на фронте, он видел бы только показанные строки: товар
        с самыми дорогими подарками, стоящий одиннадцатым по прибыли,
        не попадал бы в него вовсе.
        """
        for i in range(1, 12):
            product = make_product(name=f"Ходовой {i}", article=f"300.{i:03d}.05")
            make_profit_day(product=product, quantity="100",
                            revenue_kopecks=1_000_000 * i, cost_kopecks=100_000)
            shipment = make_demand(moment=moscow(2026, 7, 15))
            position(shipment, product, 100, 10_000)

        # Прибыли мало, подарков много: на первой странице его нет.
        generous = make_product(name="Шампунь всех мастей", article="100.016.05")
        make_profit_day(product=generous, quantity="139", revenue_kopecks=10_000,
                        cost_kopecks=139_000)
        paid = make_demand(moment=moscow(2026, 7, 15))
        position(paid, generous, 66, 152)
        gift = make_demand(moment=moscow(2026, 7, 15))
        position(gift, generous, 73, 0)

        payload = page(Filters(page_size=10))
        shown = {row["article"] for row in payload["results"]}

        assert len(payload["results"]) == 10
        assert "100.016.05" not in shown, "лидер обязан быть за пределами страницы"
        assert payload["coverage"]["most_given_away"][0]["article"] == "100.016.05"

    def test_order_is_by_cost_not_by_share(
        self, make_product, make_profit_day, make_demand
    ):
        """Порядок денежный: доля выводит наверх мелочь.

        Четыре позиции «Амуниции» роздали целиком — по 100 % при трёх
        штуках. Четыре одинаковые полосы не отвечают на «кто из них
        главный», и на боевой странице так и вышло: список из пяти строк,
        где четыре по 100 %. Найдено снимком.
        """
        trinket = make_product(name="Воск для амуниции", article="400.003.15")
        make_profit_day(product=trinket, quantity="3", revenue_kopecks=0,
                        cost_kopecks=60_000)
        gift = make_demand(moment=moscow(2026, 7, 15))
        position(gift, trinket, 3, 0)

        workhorse = make_product(name="Репеллент", article="300.002.05")
        make_profit_day(product=workhorse, quantity="431",
                        revenue_kopecks=20_000_000, cost_kopecks=13_000_000)
        paid = make_demand(moment=moscow(2026, 7, 15))
        position(paid, workhorse, 326, 61_000)
        given = make_demand(moment=moscow(2026, 7, 15))
        position(given, workhorse, 105, 0)

        top = page(Filters(page_size=200))["coverage"]["most_given_away"]

        # У «Воска» доля 100 %, у «Репеллента» — 24 %; наверху денежный.
        assert top[0]["article"] == "300.002.05"
        assert top[0]["share"] < top[1]["share"]
        assert top[0]["free_cost_kopecks"] > top[1]["free_cost_kopecks"]

    def test_share_is_of_shipped_not_of_sold(
        self, product, make_profit_day, make_demand
    ):
        """Доля считается от отгруженного: даром уходит из отгруженного.

        От проданного она была бы больше единицы у товара, который раздали
        целиком, — и полоса вылезла бы за дорожку.
        """
        make_profit_day(quantity="10", revenue_kopecks=50_000, cost_kopecks=20_000)
        paid = make_demand(moment=moscow(2026, 7, 15))
        position(paid, product, 6, 8_333)
        gift = make_demand(moment=moscow(2026, 7, 15))
        position(gift, product, 4, 0)

        entry = page(Filters())["coverage"]["most_given_away"][0]

        assert entry["share"] == Decimal(4) / Decimal(10)
        assert entry["share"] <= 1
