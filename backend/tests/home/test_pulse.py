"""Пульс и «где зарабатываем»: числа месяца против предыдущего.

Главная ловушка раздела — **сложить два разных множества**. Отгрузки и отчёт
прибыльности отвечают на разные вопросы («сколько увезли» и «сколько
заработали»), и разница между ними — товар на реализации, а не ошибка.
"""

from datetime import timedelta
from decimal import Decimal

import pytest

from api.home.services import channels, earnings, pulse
from core.models import ProductKind

pytestmark = pytest.mark.django_db


@pytest.fixture
def month(window):
    return window.current


@pytest.fixture
def earlier(window):
    return window.earlier


def figures(result):
    return {figure.key: figure for figure in result.shipped + result.sold}


def test_compares_the_month_with_the_one_before(
    window, month, earlier, make_product, make_shipment
):
    product = make_product(name="Кондиционер Сияющая формула 500 мл", article="2-001")
    make_shipment(month.first + timedelta(days=3), [(product, 10, 65000)])
    make_shipment(earlier.first + timedelta(days=3), [(product, 5, 65000)])

    row = figures(pulse.of(window))["shipped"]
    assert row.value == 650000
    assert row.earlier == 325000
    assert row.change == Decimal("100.0")


def test_growth_from_zero_has_no_percentage(window, month, make_product, make_shipment):
    """Прошлый месяц пуст — доли не существует, делить не на что.

    Ноль здесь читался бы как «не изменилось», а «+∞ %» — как поломка.
    """
    product = make_product(name="Репеллент 500 мл", article="3-001")
    make_shipment(month.first + timedelta(days=1), [(product, 4, 99000)])

    assert figures(pulse.of(window))["shipped"].change is None


def test_shipments_and_sales_stay_separate(
    window, month, make_product, make_shipment, make_sale
):
    """Отгружено и продано — два числа, а не одно.

    По договору комиссии товар уходит на реализацию и становится проданным
    только с отчётом комиссионера. Смешай их — и человек поделил бы выручку
    отгрузок на себестоимость продаж, получив маржу, которой нет.
    """
    product = make_product(name="Кондиционер Бабл-Гам 500 мл", article="2-002")
    make_shipment(month.first + timedelta(days=2), [(product, 10, 65000)])
    make_sale(product, month.first + timedelta(days=2), quantity=4, revenue=260000, cost=39000)

    result = pulse.of(window)
    assert figures(result)["shipped"].value == 650000
    assert figures(result)["revenue"].value == 260000
    # Разница названа отдельным числом, а не оставлена на вычитание.
    assert result.consignment_kopecks == 390000


def test_margin_is_compared_in_points_not_percent(
    window, month, earlier, make_product, make_sale
):
    """Маржа выросла с 50 % до 75 % — это +25 пунктов, а не +50 %.

    Арифметически «на 50 % больше» верно и читается как ложь: маржа
    не может вырасти вдвое, оставшись в пределах ста процентов.
    """
    product = make_product(name="Кондиционер Табак-Ваниль 500 мл", article="2-003")
    make_sale(product, month.first + timedelta(days=1), quantity=1, revenue=100000, cost=25000)
    make_sale(product, earlier.first + timedelta(days=1), quantity=1, revenue=100000, cost=50000)

    row = figures(pulse.of(window))["margin"]
    assert row.value == 7500
    assert row.earlier == 5000
    assert row.change == Decimal("25")


def test_services_are_excluded_from_sales(window, month, make_product, make_sale):
    """Доставка — услуга: её не производят и не продают.

    Оставь мы её, «продано» включало бы стоимость перевозки, а маржа
    доставки поехала бы в маржу товаров.
    """
    product = make_product(name="Шампунь для лошадей 500 мл", article="1-001")
    delivery = make_product(name="Доставка", kind=ProductKind.SERVICE)
    make_sale(product, month.first + timedelta(days=1), quantity=1, revenue=100000, cost=30000)
    make_sale(delivery, month.first + timedelta(days=1), quantity=1, revenue=50000, cost=0)

    assert figures(pulse.of(window))["revenue"].value == 100000


def test_running_month_is_marked_but_not_dropped(
    window, month, make_product, make_shipment
):
    """Идущий месяц в ряду есть, но помечен: он неполон.

    Выкинуть его значило бы показать, что месяца не было вовсе; поставить
    наравне — объявить падение на 90 % четвёртого числа.
    """
    if window.running is None:
        pytest.skip("первое число: идущего месяца ещё нет")

    product = make_product(name="Репеллент 500 мл", article="3-001")
    make_shipment(month.first + timedelta(days=1), [(product, 10, 99000)])
    make_shipment(window.running.first, [(product, 1, 99000)])

    months = pulse.of(window).months
    assert [row["partial"] for row in months] == [False, True]


def test_receipt_is_the_median_not_the_average(
    window, month, make_product, make_shipment
):
    """Чек считается медианой: одна крупная отгрузка не должна двигать его.

    Найдено продуктовым проходом. На боевых средний чек августа — 3 251 ₽
    при медианном 1 363 ₽: среднее втрое выше, потому что его тянет одна
    отгрузка Озону на 99 496 ₽. «Средний чек упал на 41 %» читалось как
    обеднение покупателя, а означало разовую крупную поставку месяцем
    раньше. С медианой картина обратная и честная: рост на 2,5 %.
    """
    product = make_product(name="Кондиционер Бабл-Гам 500 мл", article="2-002")
    # Четыре обычные отгрузки и одна крупная — как Озон среди розницы.
    for index in range(4):
        make_shipment(month.first + timedelta(days=index + 1), [(product, 2, 65000)])
    make_shipment(month.first + timedelta(days=10), [(product, 200, 65000)])

    receipt = figures(pulse.of(window))["receipt"]

    # Медиана — обычная отгрузка, а не среднее по всем пяти (3 380 000).
    assert receipt.value == 130000


def test_average_receipt_counts_documents_not_lines(
    window, month, make_product, make_shipment
):
    """Средний чек — на документ, а не на строку.

    Одна отгрузка на пять наименований — это один чек. Деление на позиции
    занизило бы его впятеро и сделало бы «падение среднего чека» следствием
    того, что стали брать разнообразнее.
    """
    one = make_product(name="Кондиционер Кока-Кола 500 мл", article="2-004")
    two = make_product(name="Кондиционер Персик 500 мл", article="2-005")
    make_shipment(month.first + timedelta(days=1), [(one, 1, 60000), (two, 1, 40000)])

    assert figures(pulse.of(window))["receipt"].value == 100000


class TestMargins:
    """«Где зарабатываем»: маржа по товарам месяца."""

    def test_shows_both_ends_of_the_range(self, window, month, make_product, make_sale):
        """Карточка обязана показать и лучший край, и худший.

        «Зарабатываем на кондиционерах по 85 %» — половина ответа, пока
        не видно, что шампунь идёт по шесть.
        """
        day = month.first + timedelta(days=2)
        for index in range(8):
            product = make_product(name=f"Кондиционер {index}", article=f"2-{index:03d}")
            make_sale(product, day, quantity=10, revenue=1000000, cost=100000 * (index + 1))
        worst = make_product(name="Шампунь всех мастей 500 мл", article="1-001")
        make_sale(worst, day, quantity=46, revenue=567800, cost=532000)

        rows = earnings.margins(window)
        assert rows[0].margin > rows[-1].margin
        assert rows[-1].name == "Шампунь всех мастей 500 мл"

    def test_single_sale_does_not_hijack_the_card(self, window, month, make_product, make_sale):
        """Продажа на 200 ₽ даёт крайнюю маржу и ничего не значит.

        Без порога выручки карточка каждый месяц показывала бы случайную
        мелочь вместо того, на чём стоит бизнес.
        """
        day = month.first + timedelta(days=2)
        real = make_product(name="Кондиционер Сияющая формула 500 мл", article="2-001")
        make_sale(real, day, quantity=10, revenue=650000, cost=100000)
        noise = make_product(name="Пробник 5 мл", article="9-001")
        make_sale(noise, day, quantity=1, revenue=20000, cost=19900)

        assert [row.name for row in earnings.margins(window)] == [real.name]


class TestChanges:
    """«Что выросло и что упало»: месяц против предыдущего."""

    def test_disappearance_counts_as_a_fall(
        self, window, month, earlier, make_product, make_sale
    ):
        """Товар продавали, а в этом месяце нет — это падение на всю выручку.

        Считай мы только пересечение множеств, страница показывала бы рост
        там, где половина ассортимента остановилась.
        """
        stopped = make_product(name="Кондиционер Персик-Банан 5000 мл", article="2-050")
        make_sale(stopped, earlier.first + timedelta(days=1), quantity=1, revenue=299000, cost=100000)
        grew = make_product(name="Кондиционер Сияющая формула 500 мл", article="2-001")
        make_sale(grew, month.first + timedelta(days=1), quantity=10, revenue=650000, cost=100000)

        rows = {row.name: row for row in earnings.changes(window)}
        assert rows[stopped.name].delta_kopecks == -299000
        assert rows[grew.name].delta_kopecks == 650000

    def test_services_never_appear(self, window, month, earlier, make_product, make_sale):
        """Доставка упала — это «меньше возили», а не «хуже продаём».

        Строка отвечала бы на чужой вопрос и занимала место у той, что
        отвечает на нужный.
        """
        delivery = make_product(name="Доставка", kind=ProductKind.SERVICE)
        make_sale(delivery, earlier.first + timedelta(days=1), quantity=1, revenue=360000, cost=0)
        make_sale(delivery, month.first + timedelta(days=1), quantity=1, revenue=58000, cost=0)

        assert earnings.changes(window) == []


class TestChannels:
    """«Кто дал деньги»: выручка отгрузок по каналам."""

    def test_orders_by_money(self, window, month, make_product, make_shipment, make_channel):
        product = make_product(name="Репеллент 500 мл", article="3-001")
        ozon = make_channel("Озон")
        vk = make_channel("ВКонтакте")
        make_shipment(month.first + timedelta(days=1), [(product, 10, 99000)], channel=ozon)
        make_shipment(month.first + timedelta(days=2), [(product, 3, 99000)], channel=vk)

        rows = channels.of(window)
        assert [row.name for row in rows] == ["Озон", "ВКонтакте"]
        assert rows[0].revenue_kopecks == 990000

    def test_shipments_without_a_channel_are_still_counted(
        self, window, month, make_product, make_shipment
    ):
        """Канал не заведён — это тоже строка.

        Спрячь её, и доли перестали бы давать сто процентов, а причина
        осталась бы невидимой.
        """
        product = make_product(name="Репеллент 500 мл", article="3-001")
        make_shipment(month.first + timedelta(days=1), [(product, 2, 99000)])

        assert [row.name for row in channels.of(window)] == ["Канал не указан"]


def test_equal_deltas_keep_a_stable_order(window, month, earlier, make_product, make_sale):
    """Ничьи разрешаются именем, а не порядком обхода множества.

    Найдено обзором кода. Строки собираются обходом `set(now) | set(was)`,
    и при равных дельтах порядок зависел от хеша строк — а он рандомизирован
    между запусками. Срез «верх и низ» показывал бы разные товары
    от запроса к запросу, и оба списка выглядели бы правдоподобно.
    """
    for name in ("Бабл-Гам", "Аромат вишни", "Ягодный микс", "Зелёный чай"):
        product = make_product(name=name, article=f"2-{len(name):03d}")
        make_sale(product, month.first + timedelta(days=1), quantity=1, revenue=500000, cost=100000)
        make_sale(product, earlier.first + timedelta(days=1), quantity=1, revenue=100000, cost=20000)

    names = [row.name for row in earnings.changes(window)]
    assert names == sorted(names), "при равных дельтах порядок задаётся именем"
