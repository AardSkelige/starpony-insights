"""Календарный день из момента — и то, что от него зависит.

Дефект найден обзором кода 29.08 и был **тихим**: `moment.date()` возвращает
UTC-дату, и всё, что попадает между полуночью и тремя ночи по Москве,
числится предыдущим днём. В базе таких документов сейчас нет ни одного,
поэтому ни один тест не краснел — фикстуры ставят полдень.

Проверки ниже намеренно берут **час ночи**: это единственное время, на котором
ошибка видна, и именно поэтому она дожила до обзора.
"""

from datetime import datetime, timezone as tz
from decimal import Decimal

import pytest
from django.utils import timezone

from core.dates import days_between, local_date
from core.models import Counterparty, Document, DocumentKind, SyncKind, SyncRun
from core.services import lead_time

pytestmark = pytest.mark.django_db


def moscow(year, month, day, hour=12):
    return timezone.make_aware(datetime(year, month, day, hour))


class TestLocalDate:
    def test_night_hours_stay_in_their_own_day(self):
        """Час ночи по Москве — это четыре часа вечера предыдущих суток
        по UTC. `.date()` у такого значения врёт на день."""
        night = moscow(2026, 3, 10, hour=1)

        assert local_date(night).day == 10
        # Ровно то, что делал прежний код и что было неверно.
        assert night.astimezone(tz.utc).date().day == 9

    def test_matches_what_the_database_returns(self, db):
        """Главное: день обязан совпасть у объекта в памяти и у него же,
        прочитанного из базы. Иначе расчёт зависит от того, откуда взялась
        строка, — и в тестах он верен, а в production нет."""
        run = SyncRun.objects.create(kind=SyncKind.DOCUMENTS)
        agent = Counterparty.objects.create(
            ms_id="cccccccc-0000-0000-0000-000000000001", name="Поставщик",
            last_seen_run=run,
        )
        Document.objects.create(
            ms_id="dddddddd-0000-0000-0000-000000000001",
            kind=DocumentKind.SUPPLY,
            number="00001",
            moment=moscow(2026, 3, 10, hour=1),
            agent=agent,
            last_seen_run=run,
        )

        stored = Document.objects.get(number="00001")

        assert local_date(stored.moment).day == 10
        # Ровно то, что делал прежний код и что было неверно.
        assert stored.moment.date().day == 9


class TestDaysBetween:
    def test_counts_calendar_days(self):
        assert days_between(moscow(2026, 4, 1, hour=23), moscow(2026, 4, 2, hour=9)) == 1

    def test_same_night_is_zero(self):
        """Заказ и приёмка одной ночью — «в тот же день». Через UTC выходил
        один день, и «в тот же день» на экране превращалось в срок."""
        assert days_between(moscow(2026, 3, 10, hour=1), moscow(2026, 3, 10, hour=15)) == 0


class TestLeadTimeAtNight:
    def test_night_order_does_not_add_a_day(self, db):
        """Контракт `lead_time` — «ноль дней это ответ». Заказ в час ночи
        превращал его в единицу и сдвигал медиану поставщика."""
        run = SyncRun.objects.create(kind=SyncKind.DOCUMENTS)
        agent = Counterparty.objects.create(
            ms_id="cccccccc-0000-0000-0000-000000000002", name="Поставщик",
            last_seen_run=run,
        )
        order = Document.objects.create(
            ms_id="eeeeeeee-0000-0000-0000-000000000001",
            kind=DocumentKind.PURCHASE_ORDER,
            number="З-00001",
            moment=moscow(2026, 3, 10, hour=1),
            agent=agent,
            last_seen_run=run,
        )
        Document.objects.create(
            ms_id="eeeeeeee-0000-0000-0000-000000000002",
            kind=DocumentKind.SUPPLY,
            number="00001",
            moment=moscow(2026, 3, 10, hour=15),
            agent=agent,
            purchase_order=order,
            last_seen_run=run,
        )

        supplies = list(
            Document.objects.filter(kind=DocumentKind.SUPPLY).select_related(
                "purchase_order"
            )
        )

        assert lead_time.of(supplies).days == Decimal("0")


class TestRegularityAtNight:
    def test_same_day_at_night_is_one_delivery(self, db):
        """Три приёмки одним днём — одна поставка. Одна из них в час ночи
        давала два «дня поставок» и лишний интервал в сутки — ровно то,
        ради чего дедупликация и вводилась."""
        from api.suppliers.services import regularity

        run = SyncRun.objects.create(kind=SyncKind.DOCUMENTS)
        agent = Counterparty.objects.create(
            ms_id="cccccccc-0000-0000-0000-000000000003", name="Поставщик",
            last_seen_run=run,
        )
        for index, hour in enumerate((1, 12, 18)):
            Document.objects.create(
                ms_id=f"ffffffff-0000-0000-0000-{index:012d}",
                kind=DocumentKind.SUPPLY,
                number=f"{index:05d}",
                moment=moscow(2026, 3, 10, hour=hour),
                agent=agent,
                last_seen_run=run,
            )

        supplies = list(Document.objects.filter(kind=DocumentKind.SUPPLY))

        assert regularity.of(supplies).delivery_days == 1
        assert regularity.of(supplies).days is None


class TestCoverageSpanAtNight:
    def test_span_counts_calendar_days(self, db):
        """Длина выборки в днях — знаменатель дневного расхода. Ошибка
        на день тихо искажает «хватит на N дней» на обеих страницах."""
        from core.services import coverage

        run = SyncRun.objects.create(kind=SyncKind.DOCUMENTS)
        agent = Counterparty.objects.create(
            ms_id="cccccccc-0000-0000-0000-000000000004", name="Покупатель",
            last_seen_run=run,
        )
        from core.models import Product, Uom

        uom = Uom.objects.create(
            ms_id="cccccccc-0000-0000-0000-0000000000f1", name="шт", last_seen_run=run
        )
        product = Product.objects.create(
            ms_id="cccccccc-0000-0000-0000-0000000000f2", name="Товар", uom=uom,
            last_seen_run=run,
        )
        from core.models import DocumentPosition

        for index, moment in enumerate(
            (moscow(2026, 3, 10, hour=1), moscow(2026, 3, 12, hour=1))
        ):
            document = Document.objects.create(
                ms_id=f"aaaaaaaa-1111-0000-0000-{index:012d}",
                kind=DocumentKind.DEMAND,
                number=f"O-{index:05d}",
                moment=moment,
                agent=agent,
                last_seen_run=run,
            )
            DocumentPosition.objects.create(
                document=document, product=product, quantity=Decimal(1),
                total_kopecks=100,
            )

        # 10, 11 и 12 марта — три календарных дня.
        assert coverage.days_of(DocumentPosition.objects.all()) == 3


def test_night_shipment_is_not_lost_by_the_timeline(db):
    """Столбики теряли отгрузку целиком: границы ряда считались по UTC,
    а корзины `Trunc*` — по московской, и цикл до последней не доходил."""
    from api.common import timeline
    from core.models import DocumentPosition, Product, Uom

    run = SyncRun.objects.create(kind=SyncKind.DOCUMENTS)
    agent = Counterparty.objects.create(
        ms_id="cccccccc-0000-0000-0000-000000000005", name="Покупатель",
        last_seen_run=run,
    )
    uom = Uom.objects.create(
        ms_id="cccccccc-0000-0000-0000-0000000000f3", name="шт", last_seen_run=run
    )
    product = Product.objects.create(
        ms_id="cccccccc-0000-0000-0000-0000000000f4", name="Товар", uom=uom,
        last_seen_run=run,
    )
    for index, (moment, quantity) in enumerate(
        ((moscow(2026, 6, 1, hour=12), 1), (moscow(2026, 6, 3, hour=1), 5))
    ):
        document = Document.objects.create(
            ms_id=f"bbbbbbbb-1111-0000-0000-{index:012d}",
            kind=DocumentKind.DEMAND,
            number=f"O-{index:05d}",
            moment=moment,
            agent=agent,
            last_seen_run=run,
        )
        DocumentPosition.objects.create(
            document=document, product=product, quantity=Decimal(quantity),
            total_kopecks=100,
        )

    line = timeline.of(DocumentPosition.objects.all(), date_from=None, date_to=None)

    assert sum(point["quantity"] for point in line.points) == Decimal(6)
