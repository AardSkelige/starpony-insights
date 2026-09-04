"""Проверки блока «Требует решения».

Ошибки здесь тихие: счётчик остаётся правдоподобным числом, а означает
не то. Поэтому проверяется не «что-то посчиталось», а **что именно попало
в счётчик и что из него исключено**.
"""

from datetime import timedelta

import pytest

from api.home.services import signals
from core.dates import today as local_today
from core.models import ProductKind, SyncKind, SyncRun, SyncStatus

pytestmark = pytest.mark.django_db


def by_key(rows):
    return {row.key: row for row in rows}


@pytest.fixture
def sold_out(make_product, make_stock, make_shipment):
    """Ходовой товар, которого не осталось: спрос есть, остаток ноль."""
    product = make_product(name="Кондиционер Кокосовое молоко 500 мл", article="2-031")
    make_stock(product, quantity=0, sale_price=65000)
    make_shipment(local_today() - timedelta(days=10), [(product, 30, 65000)])
    return product


def test_counts_goods_that_ran_out(sold_out):
    """Товар кончился — это первая строка блока и самая срочная."""
    row = by_key(signals.of())["out-of-stock"]

    assert row.count == 1
    assert row.tone == "bad"


def test_ignores_goods_that_never_sold(make_product, make_stock):
    """Ноль остатка без спроса — не сигнал.

    Позицию, которую никогда не держат на складе, счётчик обязан пропустить:
    иначе он перестаёт означать упущенную продажу и превращается в перепись
    пустых строк остатка.
    """
    never = make_product(name="Пробник, не продавался", article="9-999")
    make_stock(never, quantity=0, sale_price=10000)

    assert by_key(signals.of())["out-of-stock"].count == 0


def test_ignores_materials(make_product, make_stock, make_shipment):
    """Сырьё в «товар кончился» не попадает: у него нет артикула.

    Без этого условия сюда пришли бы 276 позиций сырья, и блок перестал бы
    читаться целиком.
    """
    material = make_product(name="Отдушка Банан", article="")
    make_stock(material, quantity=0)
    make_shipment(local_today() - timedelta(days=5), [(material, 10, 100)])

    assert by_key(signals.of())["out-of-stock"].count == 0


def test_running_out_excludes_what_already_ran_out(sold_out, make_product, make_stock, make_shipment):
    """Одна позиция не попадает в два счётчика сразу.

    Кончившееся считается своей строкой; окажись оно и в «хватит меньше
    чем на 14 дней», сумма строк перестала бы сходиться с числом позиций,
    и человек, сложив их, получил бы больше, чем есть на складе.
    """
    low = make_product(name="Кондиционер Табак-Ваниль 500 мл", article="2-027")
    make_stock(low, quantity=5, sale_price=65000)
    make_shipment(local_today() - timedelta(days=10), [(low, 60, 65000)])

    rows = by_key(signals.of())
    assert rows["out-of-stock"].count == 1
    assert rows["running-out"].count == 1


def test_materials_are_counted_through_bills_of_materials(
    make_product, make_stock, make_shipment, make_plan
):
    """Расход сырья считается по техкартам, а не по отгрузкам.

    Сырьё не продают: оно уходит, когда из него варят проданный товар.
    Считай мы его по позициям отгрузок, в расход попали бы только редкие
    случаи прямой продажи сырья — и счётчик показывал бы почти ноль
    при пустеющем складе.
    """
    material = make_product(name="Основа шампуня", article="")
    make_stock(material, quantity=100)
    product = make_product(name="Шампунь для лошадей 500 мл", article="1-001")
    make_stock(product, quantity=50)
    make_plan(product, [(material, 10)], output=1)

    # Продали 30 штук: по техкарте это 300 единиц основы при остатке 100.
    make_shipment(local_today() - timedelta(days=15), [(product, 30, 50000)])

    assert by_key(signals.of())["materials-out"].count == 1


def test_without_price_needs_both_article_and_stock(make_product, make_stock):
    """«Без цены продажи» — только товар и только тот, что лежит на складе.

    Сырью цена продажи не положена вовсе, а карточка без остатка — это ещё
    не вопрос: продавать нечего.
    """
    lying = make_product(name="Пенка для очистки амуниции 200 мл", article="400.001.20")
    make_stock(lying, quantity=41, sale_price=0)

    empty = make_product(name="Масло для амуниции 250 мл", article="400.004.25")
    make_stock(empty, quantity=0, sale_price=0)

    material = make_product(name="Глиттер", article="")
    make_stock(material, quantity=497, sale_price=0)

    assert by_key(signals.of())["without-price"].count == 1


def test_over_reserved_finds_promises_beyond_stock(make_product, make_stock):
    """Обещано больше, чем есть, — это сигнал, а не округление."""
    product = make_product(name="Кондиционер Сибирский лес 500 мл", article="2-027")
    make_stock(product, quantity=6, reserved=8)

    row = by_key(signals.of())["over-reserved"]
    assert row.count == 1
    assert row.tone == "bad"


def test_clean_check_says_so_instead_of_going_silent(make_product, make_stock):
    """Ноль — это ответ «проверено и чисто», а не отсутствие проверки."""
    product = make_product(name="Кондиционер Сибирский лес 500 мл", article="2-027")
    make_stock(product, quantity=6, reserved=1)

    row = by_key(signals.of())["over-reserved"]
    assert row.count == 0
    assert row.tone == "ok"


def test_clean_check_changes_its_wording(make_product, make_stock):
    """При нуле подпись становится утвердительной.

    «резерв больше остатка» с зелёной галочкой читается как утверждение,
    что резерв больше остатка — и это хорошо. Галочка не должна спорить
    с текстом: раз ответ поменялся, обязана поменяться и формулировка.
    """
    product = make_product(name="Кондиционер Сибирский лес 500 мл", article="2-027")
    make_stock(product, quantity=6, reserved=1)

    row = by_key(signals.of())["over-reserved"]
    assert row.label_clean == "остатка хватает на все заказы"
    assert row.label != row.label_clean
    # Пояснение под подписью тоже меняется: «остатка хватает на все заказы»
    # рядом с «в резерве обещано больше, чем лежит» противоречит само себе.
    assert row.note != row.note_clean


def test_signal_carries_what_exactly_it_found(sold_out):
    """Сигнал перечисляет найденное, а не только считает.

    Переход в раздел без списка показывает страницу, а не проблему: человек
    приходит и ищет двадцать одну позицию среди пятидесяти четырёх строк.
    Владелец указал на это прямо.
    """
    row = by_key(signals.of())["out-of-stock"]

    assert row.count == 1
    assert [item.name for item in row.items] == [sold_out.name]
    # У каждой позиции сказано, почему она в списке.
    assert row.items[0].note


def test_loss_making_products_come_from_the_profit_report(
    make_product, make_sale
):
    """В убыток — там, где выручка меньше себестоимости.

    По всей истории, а не за месяц: убыточная цена — свойство прайса,
    и в коротком окне товар с двумя продажами то попадает в список,
    то исчезает без единого изменения в учёте.
    """
    day = local_today() - timedelta(days=200)
    losing = make_product(name="Кондиционер пробник 50 мл", article="3-001")
    make_sale(losing, day, quantity=10, revenue=10000, cost=97285)

    earning = make_product(name="Кондиционер Сияющая формула 500 мл", article="2-001")
    make_sale(earning, day, quantity=10, revenue=650000, cost=85000)

    assert by_key(signals.of())["at-a-loss"].count == 1


def test_signals_carry_the_page_they_need(sold_out):
    """У каждой проверки есть страница — по ней сборка режет ответ по правам."""
    from api.access import PAGES_BY_KEY

    for row in signals.of():
        assert row.page_key in PAGES_BY_KEY, row.key
        assert PAGES_BY_KEY[row.page_key].route == row.route.split("?")[0]


class TestSyncTrouble:
    """Отставшая синхронизация — единственный сигнал про саму систему."""

    def _run(self, kind, hours_ago):
        from django.utils import timezone

        moment = timezone.now() - timedelta(hours=hours_ago)
        return SyncRun.objects.create(
            kind=kind, status=SyncStatus.SUCCESS, started_at=moment, finished_at=moment
        )

    def test_silence_beyond_the_limit_is_reported(self):
        """Остатки идут каждые 15 минут: два часа молчания — уже поломка."""
        self._run(SyncKind.STATE, hours_ago=5)
        self._run(SyncKind.DOCUMENTS, hours_ago=1)

        trouble = signals.sync_trouble()
        assert trouble is not None
        assert trouble.kind == SyncKind.STATE
        assert trouble.hours == 5

    def test_message_says_what_broke_and_what_to_do(self):
        """Полоса объясняется человеческими словами, а не именем сущности.

        Первая версия писала «Синхронизация „остатки и себестоимость“ молчит
        2 ч» — владелец не понял ни что сломалось, ни чем это грозит. Три
        части обязательны: **что** устарело, **насколько это необычно**
        и **чему теперь нельзя верить**.
        """
        self._run(SyncKind.STATE, hours_ago=5)

        trouble = signals.sync_trouble()

        assert trouble is not None
        assert trouble.label == "Остатки на складе"
        assert trouble.usual == "каждые 15 минут"
        # Законченное предложение, а не кусок фразы: собранное на фронте
        # из обрывка, оно давало «могли измениться что лежит на складе».
        assert trouble.affects.endswith(".")

    def test_thresholds_differ_by_schedule(self):
        """Документы идут раз в сутки — пять часов для них норма.

        Один порог на оба вида означал бы либо ложную тревогу по документам
        каждую ночь, либо слепоту к остаткам на целые сутки.
        """
        self._run(SyncKind.STATE, hours_ago=0)
        self._run(SyncKind.DOCUMENTS, hours_ago=5)

        assert signals.sync_trouble() is None

    def test_never_run_is_not_the_same_as_fresh(self):
        """Синхронизации не было ни разу — это тревога, а не тишина."""
        trouble = signals.sync_trouble()

        assert trouble is not None
        assert trouble.hours == -1


def test_known_is_false_until_the_first_sync():
    """До первого синка нули означают незнание, а не благополучие."""
    assert signals.known() is False


def test_known_becomes_true_after_a_successful_run(synced):
    assert signals.known() is True


class TestWhatCountsAsMaterial:
    """Что считать сырьём — и что не считать.

    Оба случая нашёл владелец на первом показе, и оба давали правдоподобное
    число, означающее не то.
    """

    def test_semi_finished_goods_are_consumed_too(
        self, make_product, make_stock, make_shipment, make_plan
    ):
        """Полуфабрикат расходуется, даже если сам сделан по техкарте.

        «Основа кондиционера 500 мл» входит в состав 41 карты и уходит
        каждый день. Разворот до сырья (`explode`) раскрывает её до состава
        и в списке материалов не оставляет — главная объявляла её
        «не расходуется вовсе» и предлагала списать 13 135 ₽ живого
        производства.
        """
        from api.home.services import misplaced

        raw = make_product(name="БТМС", article="")
        base = make_product(name="Основа кондиционера 500 мл", article="")
        product = make_product(name="Кондиционер Сияющая формула 500 мл", article="2-001")

        make_plan(base, [(raw, 5)], output=1)
        make_plan(product, [(base, 1)], output=1)

        make_stock(base, quantity=100, cost=3090)
        make_stock(raw, quantity=1000, cost=100)
        make_shipment(local_today() - timedelta(days=30), [(product, 200, 65000)])

        frozen = {row.name for row in misplaced.of().frozen_all}
        assert "Основа кондиционера 500 мл" not in frozen, (
            "полуфабрикат расходуется — он не может лежать без движения"
        )

    def test_household_items_are_not_raw_material(self, make_product, make_stock):
        """Визитки и перчатки — не сырьё, хотя артикула у них тоже нет.

        «Визитка StarPony, 12 140 ₽, не расходуется» — правда, которая
        ничего не значит: визитки и не должны расходоваться по техкартам.
        В списке замороженного сырья они читаются как ошибка закупки.
        """
        from api.home.services import misplaced

        card = make_product(name="Визитка StarPony", article="")
        card.folder = "Хоз. товары/Упаковка"
        card.save(update_fields=["folder"])
        make_stock(card, quantity=100, cost=12140)

        raw = make_product(name="Отдушка Банан", article="")
        raw.folder = "Производство/Сырьё"
        raw.save(update_fields=["folder"])
        make_stock(raw, quantity=96, cost=1000)

        names = {row.name for row in misplaced.of().frozen_all}
        assert "Визитка StarPony" not in names
        assert "Отдушка Банан" in names, "настоящее сырьё обязано остаться"


def test_lost_list_sums_up_to_the_headline(
    make_product, make_stock, make_shipment
):
    """Список упущенного складывается в число из заголовка.

    Найдено продуктовым проходом: в списке стояли **дневные** суммы,
    а в заголовке — месячная, и сложение списка давало 5 655 ₽ вместо
    169 650 ₽. Расхождение в тридцать раз, и оба числа выглядели
    правдоподобно. Правило `DESIGN.md` §8: показанное обязано складываться
    в показанный итог.
    """
    from api.home.services import misplaced

    for index in range(3):
        product = make_product(name=f"Кондиционер {index} 500 мл", article=f"2-{index:03d}")
        make_stock(product, quantity=0, sale_price=65000)
        make_shipment(local_today() - timedelta(days=20), [(product, 30 + index, 65000)])

    result = misplaced.of()
    listed = sum(row.value for row in result.lost_all)

    # Допуск в рубль на строку: каждая округляется до целых копеек отдельно.
    assert abs(listed - result.lost_kopecks) <= 100 * len(result.lost_all)


def test_tiny_losses_do_not_light_up_the_block(make_product, make_sale):
    """Убыток в десять рублей не повод для строки в блоке решений.

    Найдено продуктовым проходом: из пяти убыточных позиций три стоили
    64 ₽, 52 ₽ и 10 ₽ — строка была вечно красной наравне с «21 товар
    кончился» на 169 650 ₽ в месяц, а решения из неё не следовало.
    """
    day = local_today() - timedelta(days=100)

    real = make_product(name="Кондиционер пробник 50 мл", article="3-001")
    make_sale(real, day, quantity=10, revenue=10000, cost=97285)

    tiny = make_product(name="Воск для амуниции 150 г", article="400.003.15")
    make_sale(tiny, day, quantity=1, revenue=90000, cost=91000)

    row = by_key(signals.of())["at-a-loss"]
    assert [item.name for item in row.items] == [real.name]


def test_material_signal_says_what_to_order(
    make_product, make_stock, make_shipment, make_plan
):
    """Сигнал по сырью доводится до заказа, а не до тревоги.

    «Кончится за 30 дней» — ещё не ответ: чтобы заказать, нужны сколько,
    у кого и почём. Продуктовый проход показал, что ни одного из трёх
    на главной нет, и человек шёл собирать это по трём страницам.
    """
    material = make_product(name="Диметикон 350 CST", article="")
    make_stock(material, quantity=100)
    product = make_product(name="Кондиционер Сияющая формула 500 мл", article="2-001")
    make_stock(product, quantity=50)
    make_plan(product, [(material, 10)], output=1)
    make_shipment(local_today() - timedelta(days=15), [(product, 30, 65000)])

    row = by_key(signals.of())["materials-out"]

    assert row.count == 1
    assert "заказать" in row.items[0].note


class TestSelectionMatchesTheTargetPage:
    """Сигнал не должен звать разбираться с тем, чего в разделе нет.

    Все три случая нашёл обзор кода: отбор в сигналах шёл своими условиями,
    а не общим `catalogue.goods()`, и расходился с тем, что показывает
    страница перехода.
    """

    def test_archived_goods_stay_out_of_price_signal(self, make_product, make_stock):
        """Архивный товар без цены — не сигнал: его нет на целевой странице."""
        archived = make_product(name="Кондиционер снят с продажи", article="2-900")
        archived.archived = True
        archived.save(update_fields=["archived"])
        make_stock(archived, quantity=10, sale_price=0)

        live = make_product(name="Пенка для очистки амуниции 200 мл", article="400.001.20")
        make_stock(live, quantity=41, sale_price=0)

        row = by_key(signals.of())["without-price"]
        assert [item.name for item in row.items] == [live.name]

    def test_archived_goods_stay_out_of_reserve_signal(self, make_product, make_stock):
        """То же у резерва: архивный товар — долг по документу, не задача склада."""
        archived = make_product(name="Кондиционер снят с продажи", article="2-900")
        archived.archived = True
        archived.save(update_fields=["archived"])
        make_stock(archived, quantity=1, reserved=5)

        assert by_key(signals.of())["over-reserved"].count == 0

    def test_services_stay_out_of_loss_signal(self, make_product, make_sale):
        """Доставка дороже себестоимости — не «товар в убыток».

        Услуги исключены везде — в пульсе и в марже; здесь условие забыли,
        и доставка увела бы чинить цену услуги на «Прибыльности».
        """
        day = local_today() - timedelta(days=100)
        delivery = make_product(name="Доставка", kind=ProductKind.SERVICE)
        make_sale(delivery, day, quantity=1, revenue=10000, cost=90000)

        product = make_product(name="Кондиционер пробник 50 мл", article="3-001")
        make_sale(product, day, quantity=10, revenue=10000, cost=97285)

        row = by_key(signals.of())["at-a-loss"]
        assert [item.name for item in row.items] == [product.name]


def test_demand_window_matches_its_divisor(make_product, make_stock, make_shipment):
    """Дней в выборке ровно столько, на сколько делят.

    Обе границы включаются, поэтому окно в 60 дней — это `today - 59`.
    Без поправки в выборку попадал 61 день, а делитель оставался 60,
    и дневной темп был завышен на 1,7 %. Ошибка тихая: число правдоподобно.
    """
    from api.home.services import misplaced

    product = make_product(name="Кондиционер Кокосовое молоко 500 мл", article="2-031")
    make_stock(product, quantity=0, sale_price=65000)

    # Ровно на границе окна — попадает.
    make_shipment(local_today() - timedelta(days=signals.DEMAND_DAYS - 1), [(product, 60, 65000)])
    # На день раньше — уже нет.
    make_shipment(local_today() - timedelta(days=signals.DEMAND_DAYS), [(product, 600, 65000)])

    lost = misplaced.of().lost_all
    # 60 штук за 60 дней — штука в день, по 650 ₽, за 30 дней 19 500 ₽.
    assert lost[0].value == 1_950_000
