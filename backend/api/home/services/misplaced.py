"""«Деньги лежат не там»: сколько упускаем и сколько заморожено.

**Единственное число страницы, которого нет в учёте ни в каком виде.**
Остальное МойСклад показывает сам — остатки, продажи, себестоимость;
чего он не говорит, так это что одно связано с другим. Полмиллиона лежит
в сырье, из которого не сварили то, что кончилось: чтобы это увидеть,
надо сложить отчёт об остатках с отчётом о продажах, и вручную этого
никто не делает.

**Оба окна намеренно длиннее месяца.** За месяц не отличить «кончилось»
от «не продавалось»: товар, проданный трижды и кончившийся, и товар,
не проданный ни разу, дают одинаковый ноль остатка. Поэтому спрос берётся
за шестьдесят дней, а расход сырья — за девяносто, и оба окна названы
на экране.

**Упущенное — оценка, а не факт учёта, и говорит об этом прямо.** Мы
не знаем, сколько бы продали; мы знаем темп, с которым продавали до того,
как товар кончился. Число отвечает на «сколько стоит простой», а не
«сколько мы потеряли», и подпись обязана держать эту разницу.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum

from api.common.selection import within
from core.dates import today as local_today
from core.models import DocumentKind, Product, Stock
from core.services import catalogue, consumption, coverage
from core.services import materials as materials_service
from core.services.documents import alive, positions_in
from core.text import with_plural

# Окно спроса: то же, что у сигналов. Одно число на две карточки — иначе
# «21 позиция кончилась» и список «что сварить» считались бы по разным
# множествам и не сходились бы между собой.
DEMAND_DAYS = 60

# Окно расхода сырья. Шире, чем у спроса: сырьё уходит партиями по варкам,
# и за два месяца половина позиций не двигается просто потому, что варка
# была в третьем.
MATERIAL_DAYS = 90

# Сколько дней запаса считать «заморожено». Год — не круглое число:
# столько живёт отдушка, и сырьё, которого хватит дольше её срока,
# закуплено не под производство, а на всякий случай.
FROZEN_DAYS = 365

# Во сколько дней пересчитывается упущенное для показа. Месяц: суточная
# цифра слишком мелкая, чтобы по ней принимали решение, а годовая
# обещает постоянство, которого у пятимесячной истории нет.
LOST_WINDOW_DAYS = 30

TOP_ROWS = 3

# Сколько строк отдавать в полном списке. Потолок нужен: 173 позиции —
# это уже таблица, а не ответ, и грузить её ради плитки незачем. Полсотни
# покрывают все деньги, ради которых список открывают: хвост из мелочи
# по сто рублей решения не меняет.
FULL_ROWS = 50


@dataclass(frozen=True)
class Row:
    """Строка списка: название и число, по которому она попала в список."""

    name: str
    value: int
    note: str


@dataclass(frozen=True)
class Misplaced:
    """Ответ карточки целиком."""

    lost_kopecks: int
    lost_positions: int
    frozen_kopecks: int
    frozen_positions: int
    stock_kopecks: int
    demand_days: int
    material_days: int
    to_brew: list[Row]
    lying_still: list[Row]
    # Полные списки — для панели «показать все». Верхушка отвечает
    # «на чём мы теряем», список — «что именно за этими числами».
    lost_all: list[Row]
    frozen_all: list[Row]


def of(*, today: date | None = None) -> Misplaced:
    day = today or local_today()
    # Минус один у обоих окон: границы включаются, и без поправки делитель
    # (60 и 90) расходится с числом дней в выборке (61 и 91).
    shipped = within(
        positions_in(alive(DocumentKind.DEMAND)), day - timedelta(days=DEMAND_DAYS - 1), day
    )
    used = within(
        positions_in(alive(DocumentKind.DEMAND)),
        day - timedelta(days=MATERIAL_DAYS - 1),
        day,
    )

    lost, to_brew, lost_all = _lost(shipped)
    frozen, lying_still, stock_kopecks, frozen_all = _frozen(used)

    return Misplaced(
        lost_kopecks=sum(row for _, row in lost),
        lost_positions=len(lost),
        frozen_kopecks=sum(row for _, row in frozen),
        frozen_positions=len(frozen),
        stock_kopecks=stock_kopecks,
        demand_days=DEMAND_DAYS,
        material_days=MATERIAL_DAYS,
        to_brew=to_brew,
        lying_still=lying_still,
        lost_all=lost_all,
        frozen_all=frozen_all,
    )


def _prices(products) -> dict[int, Decimal]:
    """Цена продажи по товару, в копейках за штуку.

    Из карточки, а при пустой цене — по фактическим отгрузкам: у трёх
    позиций цена не проставлена вовсе, и считать их упущенное нулём значило бы
    молча вычеркнуть их из ответа. Ноль остаётся только там, где товар
    не продавали ни разу, — тогда сказать нечего честно.
    """
    from_card = {
        stock.product_id: stock.sale_price_kopecks
        for stock in Stock.objects.filter(product__in=products, sale_price_kopecks__gt=0)
    }
    missing = [product for product in products if product.pk not in from_card]
    if not missing:
        return from_card

    # Только отгрузки и только живых документов. Без вида документа
    # в среднюю попадают приёмки, и перепродажный товар без цены в карточке
    # оценивается по **закупочной** цене: упущенное считается не от той
    # величины. Тот же отбор, что везде в проекте, — `positions_in(alive(…))`.
    actual = (
        positions_in(alive(DocumentKind.DEMAND))
        .filter(product__in=missing)
        .values("product_id")
        .annotate(total=Sum("total_kopecks"), quantity=Sum("quantity"))
    )
    for row in actual:
        if row["quantity"]:
            from_card[row["product_id"]] = Decimal(row["total"]) / row["quantity"]
    return from_card


def _lost(shipped) -> tuple[list[tuple[str, int]], list[Row], list[Row]]:
    """Что кончилось при живом спросе и во сколько обходится простой."""
    goods = list(catalogue.goods())
    left_by_product = coverage.by_product(goods, shipped, DEMAND_DAYS)
    prices = _prices(goods)

    rows: list[tuple[str, int]] = []
    detail: list[tuple[int, str, Decimal, Decimal]] = []
    for product in goods:
        left = left_by_product[product.pk]
        if left.available is None or left.available > 0 or left.per_day <= 0:
            continue
        price = prices.get(product.pk, Decimal(0))
        per_day = left.per_day * price
        rows.append((product.name, int(per_day * LOST_WINDOW_DAYS)))
        detail.append((int(per_day), product.name, left.per_day, price))

    detail.sort(reverse=True)

    # Полосы ведущей плитки показывают **дневной** темп: «1 197 ₽ в день»
    # отвечает на «сколько стоит каждый день простоя».
    top = [
        Row(
            name=name,
            value=per_day,
            note=f"{quantity:.2f} шт в день × {price / 100:,.0f} ₽".replace(",", " "),
        )
        for per_day, name, quantity, price in detail[:TOP_ROWS]
    ]

    # А список — **месячные**, те же, из которых сложен итог карточки.
    # Дневные суммы в списке под заголовком «упускаем 169 650 ₽ в месяц»
    # давали 5 655 ₽ при сложении: показанное обязано складываться
    # в показанный итог (`DESIGN.md` §8), и здесь оно расходилось в тридцать раз.
    everything = [
        Row(
            name=name,
            value=int(per_day * LOST_WINDOW_DAYS),
            note=f"по {quantity:.2f} шт в день × {price / 100:,.0f} ₽".replace(",", " "),
        )
        for per_day, name, quantity, price in detail
    ]
    return rows, top, everything[:FULL_ROWS]


def _consumed_everywhere(positions) -> dict[int, Decimal]:
    """Сколько чего ушло со склада — считая полуфабрикаты наравне с сырьём.

    `consumption.of_shipments` отвечает на «что закупить» и потому доходит
    до листьев дерева; здесь вопрос «что расходуется», и промежуточные узлы
    расходуются тоже.
    """
    plans = materials_service.plans_by_product()
    # Один вызов на оба прохода: `sold` — это группировка по товару,
    # и второй вызов был вторым таким же запросом на каждый показ главной.
    rows = consumption.sold(positions)
    products = {
        product.pk: product
        for product in Product.objects.filter(
            pk__in=[row["product_id"] for row in rows]
        )
    }

    total: dict[int, Decimal] = {}
    for row in rows:
        product = products[row["product_id"]]
        if product.pk not in plans:
            continue
        for pk, quantity in materials_service.consumed_at_every_level(
            product, row["quantity"], plans=plans
        ).items():
            total[pk] = total.get(pk, Decimal(0)) + quantity
    return total


def _frozen(used) -> tuple[list[tuple[str, int]], list[Row], int, list[Row]]:
    """Сырьё, которое не двигается, и сколько в нём денег.

    Стоимость считается по себестоимости остатка, а не по цене последней
    закупки: вопрос здесь «сколько денег стоит на складе», и отвечать
    на него ценой, по которой купят в следующий раз, значило бы смешать
    факт с намерением.

    **Расход берётся по всем уровням техкарт, а не только по сырью.**
    Полуфабрикат — «Основа кондиционера 500 мл» — входит в состав 41 карты
    и уходит каждый день, но `explode` раскрывает его до состава, и в списке
    материалов он не появляется вовсе. Первая версия объявляла его
    «не расходуется вовсе» и предлагала списать 13 135 ₽ живого производства.
    """
    materials = list(catalogue.production_materials())
    stocks = {
        stock.product_id: stock
        for stock in Stock.objects.filter(product__in=materials, quantity__gt=0)
    }
    consumed = _consumed_everywhere(used)

    rows: list[tuple[str, int]] = []
    detail: list[tuple[int, str, str]] = []
    stock_kopecks = 0
    for product in materials:
        stock = stocks.get(product.pk)
        if stock is None:
            continue
        money = int(stock.quantity * stock.cost_kopecks)
        stock_kopecks += money

        left = coverage.of(
            consumed.get(product.pk, Decimal(0)), MATERIAL_DAYS, stock.available
        )
        if left.days_left is not None and left.days_left <= FROZEN_DAYS:
            continue

        rows.append((product.name, money))
        detail.append((
            money,
            product.name,
            "не расходуется вовсе"
            if left.days_left is None
            else "хватит на " + with_plural(left.days_left // 365, "год", "года", "лет"),
        ))

    detail.sort(reverse=True)
    everything = [Row(name=name, value=money, note=note) for money, name, note in detail]
    return rows, everything[: TOP_ROWS + 1], stock_kopecks, everything[:FULL_ROWS]
