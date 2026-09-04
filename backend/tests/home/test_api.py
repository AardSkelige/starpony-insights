"""Главная целиком: права и форма ответа.

**Самый дорогой дефект страницы — утечка через плитку.** Главная показывает
числа восьми разделов сразу, и человек без «Прибыльности» не должен получить
маржу ни на экране, ни в теле ответа: скрытая плитка, чьи данные приехали,
защищает ровно ни от чего.
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model

from core.models import UserPageAccess

pytestmark = pytest.mark.django_db

URL = "/api/home/"


@pytest.fixture
def make_user():
    """Пользователь с доступами.

    `home` добавляется всегда: главная — своя строка в реестре `PAGES`,
    и без неё middleware закроет сам адрес, не дав проверить содержимое
    ответа. Это не поблажка тесту: человек, которому не выдали главную,
    не увидит и её плиток, и проверять там нечего.
    """

    def _make(username, pages=(), superuser=False):
        user = get_user_model().objects.create_user(
            username=username, password="test-password-not-a-secret"
        )
        if superuser:
            user.is_superuser = True
            user.is_staff = True
            user.save(update_fields=["is_superuser", "is_staff"])
        for key in ("home", *pages):
            UserPageAccess.objects.create(user=user, page_key=key)
        return user

    return _make


@pytest.fixture
def filled(window, make_product, make_stock, make_shipment, make_sale, make_channel):
    """Немного всего: чтобы каждая плитка нашла, что показать."""
    month = window.current
    product = make_product(name="Кондиционер Сияющая формула 500 мл", article="2-001")
    make_stock(product, quantity=0, sale_price=65000)
    make_shipment(month.first + timedelta(days=2), [(product, 10, 65000)],
                  channel=make_channel("Озон"))
    make_sale(product, month.first + timedelta(days=2), quantity=10, revenue=650000, cost=100000)
    return product


def test_requires_login(client):
    assert client.get(URL).status_code == 401


def test_superuser_sees_every_tile(client, synced, filled, make_user):
    user = make_user("owner", superuser=True)
    client.force_login(user)

    body = client.get(URL).json()

    assert body["misplaced"] is not None
    assert body["pulse"] is not None
    assert body["margins"] is not None
    assert body["channels"] is not None


def test_tiles_of_forbidden_pages_are_absent_from_the_payload(
    client, synced, filled, make_user
):
    """Не «скрыты на фронте», а не приехали вовсе.

    Иначе выручка и маржа лежат в теле ответа, и посмотреть их может кто
    угодно, у кого открыт инструмент разработчика.
    """
    client.force_login(make_user("yana", pages=["production"]))

    body = client.get(URL).json()

    assert body["margins"] is None, "маржа без доступа к «Прибыльности»"
    assert body["changes"] is None
    assert body["channels"] is None, "каналы без доступа к «Каналам продаж»"
    assert body["pulse"] is None


def test_tile_appears_when_its_page_is_granted(client, synced, filled, make_user):
    client.force_login(make_user("lena", pages=["profitability"]))

    body = client.get(URL).json()

    assert body["margins"] is not None
    assert body["channels"] is None


def test_signals_are_filtered_one_by_one(client, synced, filled, make_user):
    """Урезаются поштучно, а не блоком целиком.

    У человека с одним «Расчётом производства» есть свои проверки, и пустой
    блок вместо них означал бы «всё в порядке» там, где мы просто не показали.
    """
    client.force_login(make_user("yana", pages=["production"]))

    body = client.get(URL).json()
    routes = {row["route"] for row in body["signals"]}

    assert routes == {"/production"}
    assert body["signals"], "проверки своего раздела обязаны остаться"


def test_empty_database_says_it_does_not_know(client, make_user):
    """До первого синка — «данных нет», а не «всё в порядке».

    Счётчики в обоих случаях равны нулю, и различить их может только сервер:
    на фронте для этого нет ни одного признака.
    """
    client.force_login(make_user("owner", superuser=True))

    body = client.get(URL).json()

    assert body["known"] is False
    assert body["signals"] == []
    assert body["misplaced"] is None


def test_period_names_the_month_it_reports(client, synced, filled, make_user, window):
    """Число без месяца ни к чему не привязано."""
    client.force_login(make_user("owner", superuser=True))

    body = client.get(URL).json()

    assert body["period"]["label"] == window.current.label
    assert body["period"]["earlier_label"] == window.earlier.label


def test_home_itself_needs_to_be_granted(client, synced, filled):
    """Без страницы «Главная» в доступах адрес закрыт.

    Умолчание реестра — запрет (`api/access.py`), и главная не исключение:
    она показывает числа восьми разделов сразу, и «раз это точка входа,
    пусть будет всем» открыло бы их разом.
    """
    user = get_user_model().objects.create_user(
        username="nobody", password="test-password-not-a-secret"
    )
    UserPageAccess.objects.create(user=user, page_key="production")
    client.force_login(user)

    assert client.get(URL).status_code == 403


def test_every_signal_leads_where_its_rows_are_visible(client, synced, filled, make_user):
    """Переход ведёт туда, где эти строки видно, — с сортировкой.

    Владелец указал на дыру: кнопка открывала раздел, а искать нужные
    позиции приходилось глазами среди полусотни. Три разреза для этого
    пришлось завести: запас в днях у «Материалов в приёмках», цена карточки
    у «Товаров в отгрузках», резерв в строке «Расчёта производства».

    Тест сторожит не текст ссылки, а то, что параметр сортировки понимает
    сама страница: разойдись имена, ссылка осталась бы рабочей и молча
    открывала сортировку по умолчанию — ровно так и было с `ordering`
    вместо `sort`.
    """
    from api.shipments.services.products import ORDERING as SHIPMENTS
    from api.supplies.services.materials import ORDERING as SUPPLIES

    client.force_login(make_user("owner", superuser=True))
    routes = {row["key"]: row["route"] for row in client.get(URL).json()["signals"]}

    assert routes["materials-out"] == "/supplies/materials?sort=days_left"
    assert "days_left" in SUPPLIES

    assert routes["without-price"] == "/shipments/products?sort=card_price"
    assert "card_price" in SHIPMENTS
