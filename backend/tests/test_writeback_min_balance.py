"""Обратная запись неснижаемого остатка в карточки товаров.

Здесь ошибка не «показали не то число», а «испортили учёт компании»,
и откатить её можно только руками по 54 карточкам. Поэтому проверяется
не столько результат, сколько то, **чего писаться не должно**: сырьё
с ручным порогом, товары без темпа продаж, архивные позиции.
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from core.dates import today as local_today
from core.models import (
    Counterparty,
    Document,
    DocumentKind,
    DocumentPosition,
    Product,
    ProductKind,
    SyncKind,
    SyncRun,
    Uom,
    WritebackKind,
    WritebackStatus,
    WritebackSwitch,
)
from moysklad.limits import ApiDisabledRisk
from moysklad.writeback.journal import WritebackDisabled
from moysklad.writeback.min_balance import (
    DEMAND_DAYS,
    SAFETY_DAYS,
    run_min_balance_writeback,
    targets,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def run():
    return SyncRun.objects.create(kind=SyncKind.DOCUMENTS)


@pytest.fixture
def piece(run):
    return Uom.objects.create(
        ms_id="00000000-0000-0000-0000-0000000000f2", name="шт", last_seen_run=run
    )


@pytest.fixture
def make_product(run, piece):
    counter = {"n": 0}

    def _make(name="Товар", article="2-001", archived=False, kind=ProductKind.PRODUCT):
        counter["n"] += 1
        return Product.objects.create(
            ms_id=f"00000000-0000-0000-0000-{counter['n']:012d}",
            kind=kind,
            name=name,
            article=article,
            uom=piece,
            archived=archived,
            last_seen_run=run,
        )

    return _make


@pytest.fixture
def buyer(run):
    return Counterparty.objects.create(
        ms_id="50000000-0000-0000-0000-000000000001",
        name="ООО «Конный клуб»",
        last_seen_run=run,
    )


@pytest.fixture
def make_shipment(run, buyer):
    """Отгрузка n-дней назад: от неё считается темп продаж."""
    counter = {"n": 0}

    def _make(product, quantity, days_ago=10):
        counter["n"] += 1
        moment = timezone.make_aware(
            datetime.combine(local_today() - timedelta(days=days_ago), datetime.min.time())
        ) + timedelta(hours=12)
        document = Document.objects.create(
            ms_id=f"40000000-0000-0000-0000-{counter['n']:012d}",
            kind=DocumentKind.DEMAND,
            number=f"{counter['n']:05d}",
            moment=moment,
            agent=buyer,
            last_seen_run=run,
        )
        DocumentPosition.objects.create(
            document=document,
            product=product,
            uom=product.uom,
            quantity=Decimal(str(quantity)),
            price_kopecks=Decimal("65000"),
            total_kopecks=int(Decimal(str(quantity)) * 65000),
        )
        return document

    return _make


class FakeClient:
    """Клиент, помнящий, что у него попросили записать."""

    def __init__(self, products):
        self._products = products
        self.request_count = 0
        self.puts: list[tuple[str, dict]] = []

    def iterate(self, path, params=None):
        # Демон обязан просить только действующие: PUT в архивный товар —
        # запись в общую с ботом корзину ради числа, которого никто не увидит.
        assert params == {"filter": "archived=false"}, params
        yield from self._products

    def put(self, path, payload):
        self.puts.append((path, payload))
        return {}


def card(product, minimum=None):
    row = {"id": str(product.ms_id), "name": product.name}
    if minimum is not None:
        row["minimumBalance"] = minimum
    return row


class TestTargets:
    """Что демон вообще собирается писать."""

    def test_threshold_covers_the_safety_window(self, make_product, make_shipment):
        """Порог — темп продаж на две недели вперёд.

        60 штук за 60 дней — штука в день, значит держать надо `SAFETY_DAYS`.
        """
        product = make_product(name="Кондиционер Сияющая формула 500 мл")
        make_shipment(product, DEMAND_DAYS)

        assert targets()[str(product.ms_id)] == SAFETY_DAYS

    def test_rounds_up(self, make_product, make_shipment):
        """4,2 штуки — это 5.

        Округлив вниз, порог обещал бы, что четырёх хватает, хотя расчёт
        говорит обратное.
        """
        product = make_product(name="Репеллент 500 мл")
        # 30 штук за 60 дней — половина штуки в день, за 14 дней 7.
        make_shipment(product, 31)

        assert targets()[str(product.ms_id)] == 8

    def test_raw_material_is_never_touched(self, make_product, make_shipment):
        """Сырью порог ставит человек, и затирать его расчётом нельзя.

        Правило безопасности из решения 03.09: демон пишет только тем,
        у кого есть артикул. Сырьё артикула не имеет.
        """
        material = make_product(name="Отдушка Банан", article="")
        make_shipment(material, 100)

        assert str(material.ms_id) not in targets()

    def test_product_without_sales_has_no_threshold(self, make_product):
        """Нет темпа — нет порога. Ноль значил бы «держать нечего»."""
        product = make_product(name="Пробник, не продавался")

        assert str(product.ms_id) not in targets()

    def test_sales_outside_the_window_do_not_count(self, make_product, make_shipment):
        """Отгрузка за краем окна в темп не входит.

        Окно включает обе границы: `DEMAND_DAYS` дней — это `today - (N-1)`.
        """
        product = make_product(name="Кондиционер Табак-Ваниль 500 мл")
        make_shipment(product, 600, days_ago=DEMAND_DAYS)

        assert str(product.ms_id) not in targets()


class TestWriteback:
    """Что уходит в учёт."""

    def test_writes_only_the_minimum_balance(self, make_product, make_shipment):
        """В теле запроса одно поле, а не вся карточка.

        Целая карточка — это лишняя работа и риск затереть то, что человек
        поправил между чтением и записью. То же правило, что у себестоимости.
        """
        product = make_product(name="Кондиционер Сияющая формула 500 мл")
        make_shipment(product, DEMAND_DAYS)
        client = FakeClient([card(product)])

        run_min_balance_writeback(client)

        (path, payload), = client.puts
        assert path == f"/entity/product/{product.ms_id}"
        assert payload == {"minimumBalance": SAFETY_DAYS}

    def test_same_value_is_skipped_with_a_reason(self, make_product, make_shipment):
        """Уже стоит то же самое — пропуск с причиной, а не запись.

        Без причины «пропущено 315» не отличает «всё сходится»
        от «запись не работает» (`CLAUDE.md` §6).
        """
        product = make_product(name="Кондиционер Сияющая формула 500 мл")
        make_shipment(product, DEMAND_DAYS)
        client = FakeClient([card(product, minimum=SAFETY_DAYS)])

        run = run_min_balance_writeback(client)

        assert client.puts == []
        assert run.skipped_equal == 1
        assert run.skipped_unknown == 0

    def test_unknown_target_is_skipped_with_its_own_reason(self, make_product):
        """Товар без темпа — «значение неизвестно», а не «уже совпадает».

        Две графы существуют ровно ради этого различия.
        """
        product = make_product(name="Пробник, не продавался")
        client = FakeClient([card(product)])

        run = run_min_balance_writeback(client)

        assert client.puts == []
        assert run.skipped_unknown == 1
        assert run.skipped_equal == 0

    def test_dry_run_writes_nothing_but_records_everything(
        self, make_product, make_shipment
    ):
        """`--dry-run` показывает, что изменилось бы, и не трогает учёт."""
        product = make_product(name="Кондиционер Сияющая формула 500 мл")
        make_shipment(product, DEMAND_DAYS)
        client = FakeClient([card(product, minimum=1)])

        run = run_min_balance_writeback(client, dry_run=True)

        assert client.puts == []
        assert run.changed == 1
        change = run.changes.get()
        assert change.old_value == Decimal(1)
        assert change.new_value == Decimal(SAFETY_DAYS)

    def test_disabled_switch_blocks_the_run(self, make_product, make_shipment):
        """Выключатель выключен — записи нет, и это решение человека.

        Проверять его обязан сам сеанс: демон, спрашивающий разрешение
        у вызывающего, однажды будет вызван без спроса.
        """
        WritebackSwitch.objects.update_or_create(
            kind=WritebackKind.MIN_BALANCE, defaults={"enabled": False}
        )
        product = make_product(name="Кондиционер Сияющая формула 500 мл")
        make_shipment(product, DEMAND_DAYS)
        client = FakeClient([card(product)])

        with pytest.raises(WritebackDisabled):
            run_min_balance_writeback(client)

        assert client.puts == []

    def test_breaker_stops_the_run_and_closes_the_journal(
        self, make_product, make_shipment
    ):
        """Предохранитель сработал — прогон закрыт статусом, а не брошен.

        Незакрытая строка журнала оставляет прогон навсегда «идущим»,
        и следующий не отличит его от живого.
        """
        product = make_product(name="Кондиционер Сияющая формула 500 мл")
        make_shipment(product, DEMAND_DAYS)

        class Breaking(FakeClient):
            def put(self, path, payload):
                raise ApiDisabledRisk("серия ошибок подряд")

        run = run_min_balance_writeback(Breaking([card(product)]))

        assert run.status == WritebackStatus.STOPPED
        assert run.finished_at is not None
