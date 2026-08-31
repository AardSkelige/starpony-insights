"""Детали строки: разбивка по каналам, последние отгрузки, остаток."""

from datetime import date
from decimal import Decimal

import pytest

from api.common import timeline
from api.shipments.services import product_detail, products
from tests.shipments.conftest import moscow, position

pytestmark = pytest.mark.django_db

PAGE_KEY = "shipments-products"


def test_channels_are_sorted_by_quantity(make_product, make_demand, channel, make_channel):
    """Полосы читаются сверху вниз, и порядок сам отвечает, какой канал главный.

    Канал с бо́льшим количеством заведён вторым намеренно: иначе порядок
    по количеству совпал бы с порядком заведения, и тест прошёл бы
    при любой сортировке.
    """
    bigger = make_channel("Telegram")
    product = make_product()
    position(make_demand(channel=channel), product, "2.000", 20000)
    position(make_demand(channel=bigger), product, "10.000", 100000)

    rows = product_detail.channels(products.Filters(), product.id)

    assert [row["name"] for row in rows] == ["Telegram", "Озон"]
    assert rows[0]["quantity"] == Decimal("10.000")


def test_channels_sum_up_to_the_row(make_product, make_demand, channel, make_channel):
    """Разбивка обязана сходиться с числом в строке таблицы.

    Разойдись они — человек увидит «продано 43», сложит полосы и получит 39,
    и дальше не поверит ни одному числу на странице.
    """
    product = make_product()
    position(make_demand(channel=channel), product, "7.000", 70000)
    position(make_demand(channel=make_channel("ВКонтакте")), product, "3.000", 30000)

    rows = product_detail.channels(products.Filters(), product.id)
    (line,), _, _ = products.rows(products.Filters())

    assert sum(row["quantity"] for row in rows) == line["quantity"]
    assert sum(row["revenue_kopecks"] for row in rows) == line["revenue_kopecks"]


def test_shipment_without_a_channel_is_not_dropped(make_product, make_demand, channel):
    """Отгрузка без канала остаётся видимой отдельной строкой.

    Выбросить её значит потерять штуки, которые в итоге строки посчитаны, —
    и разбивка перестанет сходиться.
    """
    product = make_product()
    position(make_demand(channel=channel), product, "5.000", 50000)
    position(make_demand(), product, "2.000", 20000)

    rows = product_detail.channels(products.Filters(), product.id)

    assert [row["name"] for row in rows] == ["Озон", "Без канала"]
    assert sum(row["quantity"] for row in rows) == Decimal("7.000")


def test_channels_respect_the_period(make_product, make_demand, channel, make_channel):
    """Детали объясняют ту строку, которую видно, — с теми же фильтрами."""
    product = make_product()
    position(make_demand(moment=moscow(2026, 6, 15), channel=channel), product, "5.000", 50000)
    position(
        make_demand(moment=moscow(2026, 1, 15), channel=make_channel("Яндекс")),
        product, "9.000", 90000,
    )

    rows = product_detail.channels(
        products.Filters(date_from=date(2026, 6, 1), date_to=date(2026, 6, 30)), product.id
    )

    assert [row["name"] for row in rows] == ["Озон"]


def test_timeline_point_carries_both_bounds(make_product, make_demand):
    """У столбика две границы, а не одна. «29.06.26: 6 шт» под подписью
    «по неделям» читалось как продажа двадцать девятого, хотя это неделя
    с 29 июня по 5 июля."""
    product = make_product()
    position(make_demand(moment=moscow(2026, 6, 29)), product, "6.000", 60000)
    position(make_demand(moment=moscow(2026, 8, 20)), product, "1.000", 10000)

    line = timeline.of(
        products.positions(products.Filters()).filter(product_id=product.pk),
        date_from=None,
        date_to=None,
    )
    first = line.points[0]

    assert line.step == "week"
    # Понедельник и воскресенье той же недели — семь дней, не восемь.
    assert first["start"] == date(2026, 6, 29)
    assert first["end"] == date(2026, 7, 5)


class TestTimelineEdgeBuckets:
    """Крайние корзины подписываются тем, что в них попало, а не всей неделей.

    Выборка обрезана `date_from`/`date_to`, и полный интервал в подписи
    описывал бы дни, которых в столбике нет: период с середины недели давал
    «29.06 – 05.07» там, где посчитана только среда–воскресенье.

    Периоды в проверках длиннее месяца намеренно: шаг подбирается по длине,
    и на трёх неделях он был бы «день», где подрезать нечего.
    """

    @pytest.fixture
    def sold(self, make_product, make_demand):
        """По штуке на четырёх датах: две попадают в крайние корзины."""
        product = make_product()
        for day in (date(2026, 7, 1), date(2026, 7, 8), date(2026, 8, 5), date(2026, 8, 11)):
            position(
                make_demand(moment=moscow(day.year, day.month, day.day)),
                product,
                "1.000",
                10000,
            )
        return product

    def _timeline(self, product, date_from, date_to):
        filters = products.Filters(date_from=date_from, date_to=date_to)
        return timeline.of(
            products.positions(filters).filter(product_id=product.pk),
            date_from=date_from,
            date_to=date_to,
        )

    def test_week_edges_are_clamped(self, sold):
        """1 июля 2026 — среда, 11 августа — вторник. Обе корзины неполные."""
        line = self._timeline(sold, date(2026, 7, 1), date(2026, 8, 11))

        assert line.step == "week"
        assert (line.points[0]["start"], line.points[0]["end"]) == (
            date(2026, 7, 1),
            date(2026, 7, 5),
        )
        assert (line.points[-1]["start"], line.points[-1]["end"]) == (
            date(2026, 8, 10),
            date(2026, 8, 11),
        )

    def test_inner_weeks_stay_whole(self, sold):
        """Внутренние корзины не трогаются: они и правда полные."""
        line = self._timeline(sold, date(2026, 7, 1), date(2026, 8, 11))

        assert (line.points[1]["start"], line.points[1]["end"]) == (
            date(2026, 7, 6),
            date(2026, 7, 12),
        )

    def test_month_edges_are_clamped(self, make_product, make_demand):
        product = make_product()
        for month in range(3, 10):
            position(
                make_demand(moment=moscow(2026, month, 15)), product, "1.000", 10000
            )

        line = self._timeline(product, date(2026, 3, 10), date(2026, 9, 20))

        assert line.step == "month"
        assert (line.points[0]["start"], line.points[0]["end"]) == (
            date(2026, 3, 10),
            date(2026, 3, 31),
        )
        assert (line.points[-1]["start"], line.points[-1]["end"]) == (
            date(2026, 9, 1),
            date(2026, 9, 20),
        )

    def test_single_bucket_is_clamped_on_both_sides(self, sold):
        """Когда корзина одна, она и первая, и последняя: подрезать надо
        с обеих сторон, а не с одной."""
        line = self._timeline(sold, date(2026, 7, 8), date(2026, 7, 8))

        assert len(line.points) == 1
        assert (line.points[0]["start"], line.points[0]["end"]) == (
            date(2026, 7, 8),
            date(2026, 7, 8),
        )

    def test_open_period_keeps_whole_buckets(self, sold):
        """Без фильтра корзина честно охватывает всю неделю — просто в первых
        её днях продаж не было. Подрезать здесь значило бы соврать в другую
        сторону: сказать, что неделя неполная, когда она полная."""
        line = timeline.of(
            products.positions(products.Filters()).filter(product_id=sold.pk),
            date_from=None,
            date_to=None,
        )

        # 1 июля — среда, корзина начинается с понедельника 29 июня.
        assert line.points[0]["start"] == date(2026, 6, 29)

    def test_clamping_does_not_move_the_numbers(self, sold):
        """Подписи меняются, суммы — нет: иначе график перестал бы сходиться
        с числом строки."""
        line = self._timeline(sold, date(2026, 7, 1), date(2026, 8, 11))

        assert sum(point["quantity"] for point in line.points) == Decimal("4")


def test_timeline_step_follows_the_period():
    """Шаг подбирается под период: пять месяцев по дням — это полторы сотни
    столбиков шириной в пиксель, а неделя по месяцам — один столбик."""
    assert timeline.step_for(14) == "day"
    assert timeline.step_for(150) == "week"
    assert timeline.step_for(400) == "month"


def test_timeline_fills_the_gaps(make_product, make_demand):
    """Неделя без продаж — это факт, а не отсутствие данных. Выбрось её,
    и провал в спросе превратится в непрерывный ряд, где ничего не случилось.
    """
    product = make_product()
    position(make_demand(moment=moscow(2026, 6, 1)), product, "1.000", 10000)
    position(make_demand(moment=moscow(2026, 8, 1)), product, "2.000", 20000)

    line = timeline.of(
        products.positions(products.Filters()).filter(product_id=product.pk),
        date_from=None,
        date_to=None,
    )

    assert line.step == "week"
    assert len(line.points) > 5
    assert any(point["quantity"] == 0 for point in line.points)


def test_timeline_adds_up_to_the_row(make_product, make_demand):
    """Сумма столбиков обязана сойтись с количеством строки: иначе график
    описывает не то, что над ним написано."""
    product = make_product()
    for day in (1, 5, 20):
        position(make_demand(moment=moscow(2026, 6, day)), product, "4.000", 40000)

    line = timeline.of(
        products.positions(products.Filters()).filter(product_id=product.pk),
        date_from=None,
        date_to=None,
    )

    assert sum(point["quantity"] for point in line.points) == Decimal("12")


def test_detail_refuses_a_product_outside_the_selection(make_product, make_demand, channel):
    """Товар не в выборке — 404, а не пустые блоки.

    Пустая разбивка читалась бы как «продаж не было», хотя на деле запрос
    просто не про эту выборку.
    """
    product = make_product()
    position(make_demand(channel=channel), product, "1.000", 10000)

    with pytest.raises(product_detail.ProductNotSold):
        product_detail.detail(
            products.Filters(date_from=date(2020, 1, 1), date_to=date(2020, 12, 31)),
            product.id,
        )


def test_detail_endpoint_requires_the_page(client, make_user, make_product, make_demand):
    product = make_product()
    position(make_demand(), product, "1.000", 10000)
    client.force_login(make_user(pages=["deadlines"]))

    assert client.get(f"/api/shipments/products/{product.id}/").status_code == 403


def test_detail_endpoint_returns_the_breakdown(
    client, make_user, make_product, make_demand, channel
):
    product = make_product()
    position(make_demand(channel=channel), product, "3.000", 30000)
    client.force_login(make_user(pages=[PAGE_KEY]))

    body = client.get(f"/api/shipments/products/{product.id}/").json()

    assert [row["name"] for row in body["channels"]] == ["Озон"]
    assert body["buyers"]["agents"][0]["name"] == "Покупатель"
    # Подпись говорит, чем измерен один столбик: «по дням» рядом с одной
    # датой в подсказке читалось как день и путало.
    assert body["timeline"]["step_label"] == "столбик — день"
    assert body["stock"] is None


def test_detail_endpoint_answers_404_outside_the_selection(
    client, make_user, make_product, make_demand
):
    product = make_product()
    position(make_demand(moment=moscow(2026, 6, 15)), product, "1.000", 10000)
    client.force_login(make_user(pages=[PAGE_KEY]))

    response = client.get(
        f"/api/shipments/products/{product.id}/",
        {"date_from": "2020-01-01", "date_to": "2020-12-31"},
    )

    assert response.status_code == 404


class TestFreeRecipients:
    """Кому товар уходит даром — 532 штуки из 2369 на боевых данных.

    Число «в т.ч. даром» страница показывала и раньше, но не отвечала «кому»,
    а ответ оказался осмысленным: конные клубы, фонды, центры реабилитации.
    """

    def test_none_when_nothing_was_free(self, make_demand, make_product):
        product = make_product()
        position(make_demand(), product, 5, 50_000)

        assert product_detail.free_recipients(products.Filters(), product.pk) is None

    def test_groups_by_recipient(self, make_demand, make_product, make_agent):
        product = make_product()
        club = make_agent('ООО "Хорсека Резорт"')
        fund = make_agent('Фонд "Шанс на жизнь"')

        position(make_demand(buyer=club), product, 20, 0)
        position(make_demand(buyer=club), product, 17, 0)
        position(make_demand(buyer=fund), product, 24, 0)
        # Платная отгрузка тому же клубу в подарки не входит.
        position(make_demand(buyer=club), product, 5, 50_000)

        free = product_detail.free_recipients(products.Filters(), product.pk)

        assert [a["name"] for a in free["agents"]] == [
            'ООО "Хорсека Резорт"',
            'Фонд "Шанс на жизнь"',
        ]
        assert free["agents"][0]["quantity"] == Decimal("37")
        assert free["agents"][0]["documents_count"] == 2
        assert free["quantity"] == Decimal("61")

    def test_folds_the_long_tail_of_recipients(
        self, make_demand, make_product, make_agent
    ):
        """Получателей у Репеллента 23. Показать всех — список вместо ответа;
        обрезать молча — потерянные штуки, которые в строке посчитаны."""
        product = make_product()
        for i in range(product_detail.AGENT_LIMIT + 3):
            position(make_demand(buyer=make_agent(f"Клуб {i}")), product, i + 1, 0)

        free = product_detail.free_recipients(products.Filters(), product.pk)

        assert len(free["agents"]) == product_detail.AGENT_LIMIT
        assert free["rest_agents_count"] == 3
        # Показанное плюс свёрнутое обязано дать всё: 1+2+…+8 = 36.
        shown = sum(a["quantity"] for a in free["agents"])
        assert shown + free["rest_quantity"] == free["quantity"] == Decimal("36")

    def test_period_narrows_it(self, make_demand, make_product, make_agent):
        product = make_product()
        club = make_agent("Клуб")
        position(make_demand(moment=moscow(2026, 4, 1), buyer=club), product, 10, 0)
        position(make_demand(moment=moscow(2026, 7, 1), buyer=club), product, 3, 0)

        free = product_detail.free_recipients(
            products.Filters(date_from=moscow(2026, 6, 1).date()), product.pk
        )

        assert free["quantity"] == Decimal("3")


class TestBuyers:
    """Кому продавали — заменило журнал последних отгрузок.

    Тот отвечал списком из десяти строк при 109 отгрузках у ходового товара,
    и по строке «00278 · Ложис Софья · 1 шт» решение не принимают.
    """

    def test_free_shipments_stay_out(self, make_demand, make_product, make_agent):
        """Смешай подарки с покупками — «КСК Отрада» встанет в список крупных
        клиентов с выручкой ноль. У бесплатного свой блок."""
        product = make_product()
        buyer = make_agent("КРМОО «Каприоль»")
        club = make_agent('ООО "КСК «Отрада»"')

        position(make_demand(buyer=buyer), product, 10, 60_000)
        position(make_demand(buyer=club), product, 18, 0)

        result = product_detail.buyers(products.Filters(), product.pk)

        assert [a["name"] for a in result["agents"]] == ["КРМОО «Каприоль»"]
        assert result["quantity"] == Decimal("10")

    def test_paid_and_free_add_up_to_the_row(
        self, make_demand, make_product, make_agent
    ):
        """Проданное плюс отданное даром обязано дать количество строки:
        на боевых у Репеллента 325 + 105 = 430 штук."""
        product = make_product()
        position(make_demand(buyer=make_agent("Покупатель")), product, 325, 900_000)
        position(make_demand(buyer=make_agent("Клуб")), product, 105, 0)

        paid = product_detail.buyers(products.Filters(), product.pk)
        free = product_detail.free_recipients(products.Filters(), product.pk)

        assert paid["quantity"] + free["quantity"] == Decimal("430")

    def test_none_when_everything_was_free(self, make_demand, make_product):
        product = make_product()
        position(make_demand(), product, 5, 0)

        assert product_detail.buyers(products.Filters(), product.pk) is None


class TestRecipientsAreGroupedById:
    """Контрагенты различаются идентификатором, а не названием.

    `Counterparty.name` не уникален — ни в модели, ни в самом МойСкладе:
    два «ИП Иванов» там заводятся спокойно. Группировка по имени слепила бы
    их отгрузки в одну строку и исказила количество, выручку, число
    документов и состав первой пятёрки.

    В аккаунте дублей сейчас нет — все 104 имени уникальны, — и потому
    ошибка была бы тихой ровно до первого тёзки.
    """

    def test_namesakes_stay_two_rows(self, make_demand, make_product, make_agent):
        product = make_product()
        first = make_agent("ИП Иванов")
        second = make_agent("ИП Иванов")

        position(make_demand(buyer=first), product, 10, 100_000)
        position(make_demand(buyer=second), product, 3, 30_000)

        result = product_detail.buyers(products.Filters(), product.pk)

        assert len(result["agents"]) == 2
        assert [a["quantity"] for a in result["agents"]] == [
            Decimal("10"),
            Decimal("3"),
        ]
        # Идентификаторы разные — по ним фронт и различает строки списка.
        assert {a["agent_id"] for a in result["agents"]} == {first.pk, second.pk}

    def test_namesakes_do_not_crowd_out_the_top(
        self, make_demand, make_product, make_agent
    ):
        """Слипшиеся тёзки поднимались бы наверх суммой двух и вытесняли
        настоящего крупнейшего покупателя из первой пятёрки."""
        product = make_product()
        big = make_agent("ООО «Крупный»")
        position(make_demand(buyer=big), product, 15, 150_000)
        for _ in range(2):
            position(make_demand(buyer=make_agent("ИП Иванов")), product, 9, 90_000)

        result = product_detail.buyers(products.Filters(), product.pk)

        assert result["agents"][0]["name"] == "ООО «Крупный»"


class TestOrderNotes:
    """Комментарий берётся из заказа, а не из отгрузки.

    В отгрузке пишут про накладные расходы («самовывоз», «доставку оплачивал
    получатель»), а зачем товар ушёл — пишут в заказе. На боевых данных
    у всех 53 отгрузок с нулевой ценой заказ есть, и комментарий тоже:
    «на призы на ЧР-2026 по конкуру», «подарок потенциальному оптовику»,
    «замена взамен вытекшей бутылки».
    """

    def test_note_comes_from_the_order_not_the_shipment(
        self, make_product, make_demand, make_agent, run
    ):
        from core.models import Document, DocumentKind

        product = make_product()
        club = make_agent("ООО «Хорсека Резорт»")
        order = Document.objects.create(
            ms_id="cafe0000-0000-0000-0000-000000000001",
            kind=DocumentKind.CUSTOMER_ORDER,
            number="З-00001",
            moment=moscow(2026, 6, 1),
            agent=club,
            description="Лена: на призы на ЧР-2026 по конкуру.",
            last_seen_run=run,
        )
        demand = make_demand(buyer=club)
        demand.customer_order = order
        demand.description = "Накладные расходы 0 — самовывоз."
        demand.save(update_fields=["customer_order", "description"])
        position(demand, product, 10, 0)

        free = product_detail.free_recipients(products.Filters(), product.pk)

        assert free["agents"][0]["notes"] == ["Лена: на призы на ЧР-2026 по конкуру."]

    def test_repeated_orders_do_not_repeat_the_note(
        self, make_product, make_demand, make_agent, run
    ):
        """Три отгрузки одного заказа несут один текст — печатать его трижды
        значит превратить объяснение в шум."""
        from core.models import Document, DocumentKind

        product = make_product()
        club = make_agent("Клуб")
        order = Document.objects.create(
            ms_id="cafe0000-0000-0000-0000-000000000002",
            kind=DocumentKind.CUSTOMER_ORDER,
            number="З-00002",
            moment=moscow(2026, 6, 1),
            agent=club,
            description="Лена: спонсорство.",
            last_seen_run=run,
        )
        for _ in range(3):
            demand = make_demand(buyer=club)
            demand.customer_order = order
            demand.save(update_fields=["customer_order"])
            position(demand, product, 2, 0)

        free = product_detail.free_recipients(products.Filters(), product.pk)

        assert free["agents"][0]["notes"] == ["Лена: спонсорство."]

    def test_missing_order_is_not_an_error(self, make_product, make_demand):
        """Отгрузка без заказа — просто отгрузка без объяснения, а не сбой."""
        product = make_product()
        position(make_demand(), product, 5, 0)

        free = product_detail.free_recipients(products.Filters(), product.pk)

        assert free["agents"][0]["notes"] == []
