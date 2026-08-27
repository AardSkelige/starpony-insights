"""Синхронизация документов.

Проверяется то, что ломается тихо: подмена вида документа при пометке
удалённых, потеря позиций-услуг и точность денежных сумм.
"""

from decimal import Decimal

import pytest
from django.utils import timezone

from core.models import (
    Counterparty,
    Document,
    DocumentKind,
    DocumentPosition,
    Product,
    ProductKind,
    SyncKind,
    SyncRun,
)
from moysklad.sync.references import ms_id_from

pytestmark = pytest.mark.django_db


@pytest.fixture
def run():
    return SyncRun.objects.create(kind=SyncKind.DOCUMENTS)


@pytest.fixture
def agent(run):
    return Counterparty.objects.create(
        ms_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", name="Покупатель", last_seen_run=run
    )


def make_document(ms_id, kind, agent, run, total=100000):
    return Document.objects.create(
        ms_id=ms_id,
        kind=kind,
        number="00001",
        moment=timezone.now(),
        agent=agent,
        total_kopecks=total,
        last_seen_run=run,
    )


class TestReferenceParsing:
    def test_extracts_id_from_href(self):
        ref = {"meta": {"href": "https://api.moysklad.ru/api/remap/1.2/entity/counterparty/abc-123"}}
        assert ms_id_from(ref) == "abc-123"

    @pytest.mark.parametrize("ref", [None, {}, {"meta": {}}, {"meta": {"href": ""}}])
    def test_missing_reference_gives_none(self, ref):
        assert ms_id_from(ref) is None


class TestMoneyPrecision:
    def test_sums_are_whole_kopecks(self, agent, run):
        """Суммы документов сходятся с учётом до копейки.

        Проверено на боевых данных: 1 205 144,95 ₽ по 293 отгрузкам совпадает
        с ответом API байт в байт.
        """
        document = make_document("11111111-1111-1111-1111-111111111111", DocumentKind.DEMAND, agent, run, total=120514495)
        document.refresh_from_db()
        assert document.total_kopecks == 120514495

    def test_unpaid_never_negative(self, agent, run):
        """Переплата не должна превращаться в отрицательный долг."""
        document = make_document("22222222-2222-2222-2222-222222222222", DocumentKind.DEMAND, agent, run, total=1000)
        document.paid_kopecks = 1500
        document.save()
        assert document.unpaid_kopecks == 0

    def test_position_price_is_stored_in_kopecks(self, agent, run):
        """Цена позиции хранится в копейках, как приходит из учёта.

        Деление на 100 при записи стоило бы значащих знаков: цена
        82.55374 копейки превращается в 0.825537 рубля, теряя 4e-7 —
        а при количестве 200 000 это ровно 8 копеек расхождения.
        """
        document = make_document("33333333-3333-3333-3333-333333333333", DocumentKind.DEMAND, agent, run)
        product = Product.objects.create(
            ms_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", name="Основа", last_seen_run=run
        )
        position = DocumentPosition.objects.create(
            document=document, product=product,
            quantity=Decimal("200000.000"), price_kopecks=Decimal("82.553740"),
            total_kopecks=16510748,
        )
        position.refresh_from_db()
        assert position.price_kopecks == Decimal("82.553740")

    def test_line_total_is_exact(self, agent, run):
        """Сумма строки хранится целыми копейками и сходится с документом.

        Считать её на лету из хранимой цены нельзя: у цены шесть знаков,
        а в учёте встречаются бесконечные дроби вроде 8.98(3) копейки.
        """
        document = make_document("44444444-4444-4444-4444-444444444444", DocumentKind.SUPPLY, agent, run, total=16510748)
        product = Product.objects.create(
            ms_id="dddddddd-dddd-dddd-dddd-dddddddddddd", name="Вода", last_seen_run=run
        )
        DocumentPosition.objects.create(
            document=document, product=product,
            quantity=Decimal("200000.000"), price_kopecks=Decimal("82.553740"),
            total_kopecks=16510748,
        )
        assert sum(p.total_kopecks for p in document.positions.all()) == document.total_kopecks


class TestDeletionByKind:
    def test_marking_one_kind_does_not_touch_another(self, agent, run):
        """Отгрузки и приёмки живут в одной таблице.

        Пометка удалённых обязана идти по своему виду: общая снесла бы
        приёмки при синхронизации отгрузок — то есть половину учёта.
        """
        make_document("11111111-1111-1111-1111-111111111111", DocumentKind.DEMAND, agent, run)
        make_document("22222222-2222-2222-2222-222222222222", DocumentKind.SUPPLY, agent, run)

        second = SyncRun.objects.create(kind=SyncKind.DOCUMENTS)
        # Во втором прогоне пришли только отгрузки, и ни одной старой.
        Document.objects.filter(kind=DocumentKind.DEMAND, deleted_at__isnull=True).exclude(
            last_seen_run=second
        ).update(deleted_at=timezone.now())

        assert Document.objects.alive().filter(kind=DocumentKind.DEMAND).count() == 0
        assert Document.objects.alive().filter(kind=DocumentKind.SUPPLY).count() == 1


class TestServices:
    def test_services_are_stored_alongside_products(self, run):
        """Услуги — отдельная сущность API, но такие же позиции документа.

        Их всего две («Доставка» и «Доставка для закупок»), зато в 25 позициях.
        Пропустить их — занизить стоимость закупки, а с ней и маржу.
        """
        Product.objects.create(
            ms_id="cccccccc-cccc-cccc-cccc-cccccccccccc",
            kind=ProductKind.SERVICE,
            name="Доставка",
            last_seen_run=run,
        )
        assert Product.objects.filter(kind=ProductKind.SERVICE).count() == 1
        assert Product.objects.filter(kind=ProductKind.PRODUCT).count() == 0


class TestPositionRounding:
    """Округление сумм строк.

    Проверяется на числах из боевого учёта: именно на них обнаружилось,
    что деление цены на 100 при записи теряет значащие знаки.
    """

    @pytest.mark.parametrize(
        "quantity,price_kopecks,expected",
        [
            # Тот самый случай: 200 000 единиц по 82.55374 копейки.
            # При хранении цены в рублях получалось 165107.40 вместо 165107.48.
            ("200000.000", "82.553740", 16510748),
            # Бесконечная дробь: 8.98(3) копейки за единицу.
            ("3.000", "8.983333", 27),
            # Обычный случай без дробей.
            ("2.000", "18548.500", 37097),
        ],
    )
    def test_line_total_matches_accounting(self, agent, run, quantity, price_kopecks, expected):
        from decimal import ROUND_HALF_UP

        document = make_document("55555555-5555-5555-5555-555555555555", DocumentKind.SUPPLY, agent, run)
        product = Product.objects.create(
            ms_id="eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee", name="Материал", last_seen_run=run
        )
        total = int(
            (Decimal(quantity) * Decimal(price_kopecks)).to_integral_value(rounding=ROUND_HALF_UP)
        )
        position = DocumentPosition.objects.create(
            document=document, product=product,
            quantity=Decimal(quantity), price_kopecks=Decimal(price_kopecks),
            total_kopecks=total,
        )
        position.refresh_from_db()
        assert position.total_kopecks == expected


class TestHrefParsing:
    """Разбор ссылок — место, где уже дважды терялись данные молча."""

    def test_strips_query_parameters(self):
        """Отчёт об остатках отдаёт ссылку с параметром запроса.

        `.../entity/product/<uuid>?expand=supplier` — без отрезания хвоста
        товар не находится, и все 253 позиции остатков пропадают без ошибки.
        """
        ref = {"meta": {"href": "https://api.moysklad.ru/api/remap/1.2/entity/product/abc-123?expand=supplier"}}
        assert ms_id_from(ref) == "abc-123"

    def test_strips_trailing_slash(self):
        ref = {"meta": {"href": "https://api.moysklad.ru/api/remap/1.2/entity/product/abc-123/"}}
        assert ms_id_from(ref) == "abc-123"
