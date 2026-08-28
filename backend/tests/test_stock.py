"""Остатки на складе."""

from decimal import Decimal

import pytest

from core.models import Product, Stock, SyncKind, SyncRun
from core.services.stock import stock_of

pytestmark = pytest.mark.django_db


@pytest.fixture
def product():
    run = SyncRun.objects.create(kind=SyncKind.STATE)
    return Product.objects.create(
        ms_id="11111111-1111-1111-1111-111111111111", name="Отдушка", last_seen_run=run
    )


def test_available_excludes_reserve(product):
    """Свободный остаток — то, что можно продать или пустить в производство.

    Считать доступным весь остаток значит пообещать покупателю товар,
    уже отложенный под другой заказ.
    """
    stock = Stock.objects.create(
        product=product, quantity=Decimal("100.000"), reserved=Decimal("30.000")
    )
    assert stock.available == Decimal("70.000")


def test_available_can_go_negative(product):
    """Резерв больше остатка — это сигнал, а не повод показать ноль.

    Так бывает при отгрузке задним числом; прятать минус значит скрыть
    расхождение, которое надо разбирать.
    """
    stock = Stock.objects.create(
        product=product, quantity=Decimal("5.000"), reserved=Decimal("8.000")
    )
    assert stock.available == Decimal("-3.000")


def test_cost_keeps_fractional_kopecks(product):
    """Себестоимость хранится в копейках с дробной частью.

    У 150 позиций из 255 она дробная — округление до целой копейки
    ложится прямо в маржу.
    """
    stock = Stock.objects.create(
        product=product, cost_kopecks=Decimal("11841.934783")
    )
    stock.refresh_from_db()
    assert stock.cost_kopecks == Decimal("11841.934783")


def test_one_stock_per_product(product):
    """Остаток у товара один: вторая строка означала бы два ответа
    на вопрос «сколько у нас есть»."""
    Stock.objects.create(product=product, quantity=Decimal("1"))
    with pytest.raises(Exception):
        Stock.objects.create(product=product, quantity=Decimal("2"))


def test_stock_days_may_be_unknown(product):
    """У товара без движения времени лежания может не быть — это не ноль.

    Ноль означал бы «пришёл сегодня», а неизвестность — что данных нет.
    """
    stock = Stock.objects.create(product=product, stock_days=None)
    assert stock.stock_days is None


class TestPartialReport:
    """Защита от неполного отчёта.

    Документация предупреждает прямо: «в отчёт попадают только товары с уже
    пересчитанными остатками на момент запроса». Пересчёт не мгновенный,
    поэтому товар может выпасть из одного прогона и вернуться в следующий.
    Безусловное обнуление стирало бы его остаток каждые 15 минут.
    """

    @pytest.fixture
    def client(self):
        class FakeClient:
            request_count = 0

            def __init__(self, rows):
                self._rows = rows

            def iterate(self, *args, **kwargs):
                yield from self._rows

        return FakeClient

    @pytest.fixture
    def stocked(self):
        run = SyncRun.objects.create(kind=SyncKind.STATE)
        products = []
        for i in range(10):
            product = Product.objects.create(
                ms_id=f"{i:08d}-0000-0000-0000-000000000000",
                name=f"Товар {i}",
                last_seen_run=run,
            )
            Stock.objects.create(
                product=product, quantity=Decimal("100"), stock_days=50
            )
            products.append(product)
        return run, products

    def _row(self, product, stock="100"):
        return {
            "meta": {"href": f"https://api.moysklad.ru/api/remap/1.2/entity/product/{product.ms_id}"},
            "stock": stock,
            "reserve": 0,
            "inTransit": 0,
            "price": 1000,
            "stockDays": 50,
        }

    def test_partial_report_does_not_zero_the_warehouse(self, client, stocked):
        """Отчёт вернул половину — остатки остаются прежними.

        Иначе расчёт закупки увидит ноль там, где товар лежит на складе,
        и закажет то, что уже есть.
        """
        from moysklad.sync.stock import sync_stock

        run, products = stocked
        rows = [self._row(p) for p in products[:4]]  # 4 из 10

        outcome = sync_stock(client(rows), run)

        assert outcome.extra["partial"] is True
        assert outcome.extra["zeroed"] == 0
        assert Stock.objects.filter(quantity=0).count() == 0, (
            "неполный отчёт не должен обнулять склад"
        )

    def test_full_report_zeroes_what_disappeared(self, client, stocked):
        """Полный отчёт — исчезнувшее обнуляется. Товар кончился, это правда."""
        from moysklad.sync.stock import sync_stock

        run, products = stocked
        rows = [self._row(p) for p in products[:9]]  # 9 из 10 — отчёт полный

        outcome = sync_stock(client(rows), run)

        assert outcome.extra["partial"] is False
        assert outcome.extra["zeroed"] == 1

    def test_zeroing_clears_stock_days(self, client, stocked):
        """У обнулённого товара не должно остаться «лежит 50 дней».

        Это прямой вход в «Порог закупки»: строка «0 на складе, лежит 50 дней»
        читается как ошибка данных и подрывает доверие ко всей странице.
        """
        from moysklad.sync.stock import sync_stock

        run, products = stocked
        sync_stock(client([self._row(p) for p in products[:9]]), run)

        zeroed = Stock.objects.filter(quantity=0).first()
        assert zeroed.stock_days is None

    def test_unknown_rows_do_not_make_a_partial_report_look_full(self, client, stocked):
        """Модификации и комплекты не должны выдавать неполный отчёт за полный.

        В отчёт попадает не только номенклатура из зеркала. Считай мы полноту
        по всем строкам, отчёт с четырьмя товарами и сотней модификаций
        выглядел бы исчерпывающим — и остальные шесть позиций склада
        обнулились бы молча, по расписанию, каждые пятнадцать минут.
        """
        from moysklad.sync.stock import sync_stock

        run, products = stocked
        rows = [self._row(p) for p in products[:4]]
        # Строки, которых нет в зеркале: у них свой идентификатор.
        rows += [
            {
                "meta": {
                    "href": "https://api.moysklad.ru/api/remap/1.2/entity/variant/"
                    # Префикс заведомо чужой: товары фикстуры начинаются
                    # с нулей, и «00000000-…-000000000000» — это товар №0.
                    f"ffffffff-0000-0000-0000-{index:012d}"
                },
                "stock": "5",
                "reserve": 0,
                "inTransit": 0,
                "price": 1000,
                "stockDays": 3,
            }
            for index in range(100)
        ]

        outcome = sync_stock(client(rows), run)

        assert outcome.fetched == 104
        assert outcome.extra["skipped"] == 100
        assert outcome.extra["partial"] is True, (
            "полнота должна считаться по узнанным позициям, а не по всем строкам"
        )
        assert outcome.extra["zeroed"] == 0
        assert Stock.objects.filter(quantity=0).count() == 0

    def test_empty_report_changes_nothing(self, client, stocked):
        """Пустой ответ — сбой на стороне API, а не пустой склад."""
        from moysklad.sync.stock import sync_stock

        run, _ = stocked
        outcome = sync_stock(client([]), run)

        assert outcome.extra["zeroed"] == 0
        assert Stock.objects.filter(quantity=Decimal("100")).count() == 10


class TestStockOf:
    """Остаток для разбора строки — общий для всех разделов сервис.

    Живёт здесь, а не у страницы: раньше этот же запрос стоял по копии
    в деталях товара и в деталях материала, и копии разъехались.
    """

    def test_reports_what_lies_on_the_shelf(self, product):
        Stock.objects.create(
            product=product,
            quantity=Decimal("12.000"),
            reserved=Decimal("2.000"),
            stock_days=7,
        )

        row = stock_of(product.pk)

        assert row["quantity"] == Decimal("12.000")
        # Свободное считается моделью, а не переписывается в сервисе:
        # два места вычитания — два ответа на вопрос «сколько можно продать».
        assert row["available"] == Decimal("10.000")
        assert row["stock_days"] == 7

    def test_unknown_stock_is_none_not_zero(self, product):
        """Ноль читался бы как «кончился». Остатка просто нет в отчёте."""
        assert stock_of(product.pk) is None

    def test_days_without_movement_may_be_unknown(self, product):
        """МойСклад отдаёт дни не всегда — поле обязано вместить пустоту."""
        Stock.objects.create(product=product, quantity=Decimal("1.000"))

        assert stock_of(product.pk)["stock_days"] is None
