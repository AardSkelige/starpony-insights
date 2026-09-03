"""Второе и третье звенья: партия → сырьё → что закупить.

Здесь стерегутся тихие ошибки: расход, не поделённый на объём выпуска;
дефицит, посчитанный от общего остатка вместо свободного; строка партии,
выброшенная молча; неснижаемый остаток, засчитанный партии дважды.
Ни одна из них не падает — все показывают правдоподобное число.
"""

from decimal import Decimal

import pytest

from api.production.services import batch
from api.production.services.batch import LineProblem
from tests.production.conftest import moscow, position

pytestmark = pytest.mark.django_db


def needs_by_name(picked):
    return {need.product.name: need for need in batch.of(picked).needs}


class TestExplode:
    """Разворачивание партии до сырья."""

    def test_расход_делится_на_объём_выпуска(self, shampoo):
        """Техкарта «4000 г воды на 10 штук» — это 400 г на штуку.

        Забудь мы про деление, вода вышла бы в десять раз больше,
        и на объёме выпуска 1 это осталось бы незамеченным навсегда.
        """
        needs = needs_by_name({"100.011.05": 5})
        assert needs["Вода дистиллированная"].quantity == Decimal("2000")
        assert needs["Отдушка «Лесные ягоды»"].quantity == Decimal("20")

    def test_полуфабрикат_раскрывается_до_сырья(
        self, make_product, make_plan, piece
    ):
        """Производство в два шага: сырьё → замес → розлив.

        Прямой состав розлива показал бы замес, а закупают не его.
        """
        water = make_product("Вода", code="1-001")
        base = make_product("Основа шампуня", code="1-002")
        bottle = make_product(
            "Шампунь 500 мл", article="100.011.05", code="2-001", uom=piece
        )
        make_plan(base, [(water, 1000)], output=1, name="Замес")
        make_plan(bottle, [(base, 2)], output=1, name="Розлив")

        needs = needs_by_name({"100.011.05": 3})
        # Замеса в списке нет — он раскрыт до воды: 3 шт × 2 × 1000 г.
        assert set(needs) == {"Вода"}
        assert needs["Вода"].quantity == Decimal("6000")

    def test_архивная_техкарта_не_считается(
        self, make_product, make_plan, piece
    ):
        """Убранная в архив карта описывает то, как делали раньше."""
        old = make_product("Старое сырьё", code="1-001")
        new = make_product("Новое сырьё", code="1-002")
        bottle = make_product(
            "Шампунь", article="100.011.05", code="2-001", uom=piece
        )
        make_plan(bottle, [(old, 100)], archived=True, name="Старая")
        make_plan(bottle, [(new, 100)], name="Новая")

        assert set(needs_by_name({"100.011.05": 1})) == {"Новое сырьё"}

    def test_два_товара_складываются_по_материалу(
        self, shampoo, make_product, make_plan, piece
    ):
        water = batch.Product.objects.get(name="Вода дистиллированная")
        other = make_product(
            "Кондиционер", article="200.040.05", code="2-002", uom=piece
        )
        make_plan(other, [(water, 100)], output=1)

        needs = needs_by_name({"100.011.05": 10, "200.040.05": 3})
        # 10 шт × 400 г + 3 шт × 100 г
        assert needs["Вода дистиллированная"].quantity == Decimal("4300")
        # И объяснение обязано сходиться с объясняемым числом.
        assert sum(
            path.quantity for path in needs["Вода дистиллированная"].via
        ) == Decimal("4300")

    def test_одна_позиция_дважды_складывается_а_не_удваивает_расчёт(
        self, shampoo
    ):
        """Разбор адресной строки уже сложил повторы — расчёт видит одно число."""
        from api.production.services.selection import parse_batch

        picked = parse_batch(["100.011.05:5", "100.011.05:3"])
        assert picked == {"100.011.05": 8}
        assert needs_by_name(picked)["Вода дистиллированная"].quantity == Decimal(
            "3200"
        )


class TestLines:
    """Строка партии не выбрасывается молча ни в одном случае."""

    def test_неизвестный_артикул_возвращается_названным(self, shampoo):
        lines = {line.article: line for line in batch.of({"999.999.99": 1}).lines}
        assert lines["999.999.99"].problem == LineProblem.UNKNOWN
        assert lines["999.999.99"].product is None

    def test_архивный_товар_отличается_от_ненайденного(
        self, shampoo, make_product
    ):
        """«Не найден» отправил бы человека искать то, что он и так видит."""
        make_product("Старый шампунь", article="100.004.05", archived=True)
        lines = {line.article: line for line in batch.of({"100.004.05": 2}).lines}
        assert lines["100.004.05"].problem == LineProblem.ARCHIVED
        # Имя приходит: «Старый шампунь — в архиве» человек поймёт,
        # «100.004.05 — в архиве» отправит его в учёт за названием.
        assert lines["100.004.05"].product.name == "Старый шампунь"

    def test_товар_без_техкарты_отличается_от_архивного(
        self, shampoo, make_product
    ):
        make_product("Таблетка-мыло", article="100.022.03")
        lines = {line.article: line for line in batch.of({"100.022.03": 5}).lines}
        assert lines["100.022.03"].problem == LineProblem.NO_PLAN

    def test_негодная_строка_не_попадает_в_расчёт(self, shampoo, make_product):
        make_product("Таблетка-мыло", article="100.022.03")
        result = batch.of({"100.011.05": 5, "100.022.03": 100})
        assert len(result.lines) == 2
        # Сто таблеток не добавили ни грамма сырья.
        assert needs_by_name({"100.011.05": 5})[
            "Вода дистиллированная"
        ].quantity == next(
            need.quantity
            for need in result.needs
            if need.product.name == "Вода дистиллированная"
        )

    def test_порядок_строк_сохраняется(self, shampoo, make_product):
        make_product("Таблетка-мыло", article="100.022.03")
        picked = {"100.022.03": 1, "100.011.05": 2}
        assert [line.article for line in batch.of(picked).lines] == [
            "100.022.03",
            "100.011.05",
        ]


class TestShortage:
    """Чего не хватает — главное число страницы."""

    def test_нехватка_от_свободного_остатка(self, shampoo):
        # Воды нужно 400 × 100 = 40 000 г, лежит 30 000.
        need = needs_by_name({"100.011.05": 100})["Вода дистиллированная"]
        assert need.shortage == Decimal("10000")
        assert need.after == Decimal(0)

    def test_резерв_не_свой(self, shampoo):
        from core.models import Product, Stock

        water = Product.objects.get(name="Вода дистиллированная")
        Stock.objects.filter(product=water).update(reserved=Decimal("5000"))
        # Свободно 25 000, а не 30 000: зарезервированное уже обещано,
        # и считать его своим значит обнаружить нехватку в день отгрузки.
        need = needs_by_name({"100.011.05": 100})["Вода дистиллированная"]
        assert need.available == Decimal("25000")
        assert need.shortage == Decimal("15000")

    def test_хватает_остаток_после_партии(self, shampoo):
        need = needs_by_name({"100.011.05": 10})["Вода дистиллированная"]
        assert need.shortage == Decimal(0)
        assert need.after == Decimal("26000")

    def test_остатка_нет_в_отчёте_это_не_ноль(
        self, make_product, make_plan, piece
    ):
        water = make_product("Вода", code="1-001")
        bottle = make_product(
            "Шампунь", article="100.011.05", code="2-001", uom=piece
        )
        make_plan(bottle, [(water, 100)])

        need = needs_by_name({"100.011.05": 1})["Вода"]
        # Прочерк, а не «не хватает всего»: сказать нечего.
        assert need.available is None
        assert need.shortage is None
        assert need.after is None

    def test_недостающее_идёт_первым(self, shampoo):
        result = batch.of({"100.011.05": 100})
        # Не хватает обоих: воды 10 000 г, отдушки 397,6 г. Сверху та,
        # которой не хватает сильнее, — список читают до первой строки,
        # не требующей действия.
        assert [need.product.name for need in result.shortages] == [
            "Вода дистиллированная",
            "Отдушка «Лесные ягоды»",
        ]
        assert result.needs[0].product.name == "Вода дистиллированная"


class TestMinimumBalance:
    """Неснижаемый остаток — второй сигнал, а не часть нехватки."""

    def test_уже_пробит_к_партии_отношения_не_имеет(self, shampoo):
        """Отдушки 2,4 г при минимуме 70 — дыра была до всякой партии."""
        need = needs_by_name({"100.011.05": 1})["Отдушка «Лесные ягоды»"]
        assert need.below_min_now is True
        # И в нехватку эти 67,6 г не вошли: нужно 4 г, лежит 2,4.
        assert need.shortage == Decimal("1.6")

    def test_уже_пробитый_минимум_не_приписывается_партии(
        self, make_product, make_plan, make_stock, piece
    ):
        """Дыра была до партии — и остаётся её же дырой, а не следствием.

        Загорись здесь второй сигнал, строка сказала бы «партия опустит
        запас ниже минимума» про запас, который ниже минимума и без неё.
        """
        extract = make_product("Экстракт", code="1-001", min_balance=500)
        bottle = make_product(
            "Кондиционер", article="200.040.05", code="2-001", uom=piece
        )
        make_plan(bottle, [(extract, 10)], output=1)
        make_stock(extract, 300)

        # Нужно 100 г, лежит 300 — партия помещается, но и до неё было 300
        # при минимуме 500.
        need = needs_by_name({"200.040.05": 10})["Экстракт"]
        assert need.shortage == Decimal(0)
        assert need.after == Decimal("200")
        assert need.below_min_now is True
        assert need.below_min_after is False

    def test_станет_ниже_минимума_хотя_хватает(
        self, make_product, make_plan, make_stock, piece
    ):
        """Экстракта 1048 г при минимуме 500, партия съест 560 — останется 488.

        Написать «хватает» и замолчать — молчаливая полуправда: закупаться
        придётся сразу же.
        """
        extract = make_product("Экстракт зелёного чая", code="1-001", min_balance=500)
        bottle = make_product(
            "Кондиционер", article="200.040.05", code="2-001", uom=piece
        )
        make_plan(bottle, [(extract, 10)], output=1)
        make_stock(extract, 1048)

        need = needs_by_name({"200.040.05": 56})["Экстракт зелёного чая"]
        assert need.shortage == Decimal(0)
        assert need.after == Decimal("488")
        assert need.below_min_after is True
        assert need.below_min_now is False

    def test_не_хватает_вовсе_второй_значок_не_загорается(
        self, make_product, make_plan, make_stock, piece
    ):
        """Строка и так говорит «докупить»; повтор — не второй довод."""
        dimethicone = make_product("Диметикон", code="1-001", min_balance=5000)
        bottle = make_product(
            "Кондиционер", article="200.040.05", code="2-001", uom=piece
        )
        make_plan(bottle, [(dimethicone, 100)], output=1)
        make_stock(dimethicone, 7100)

        need = needs_by_name({"200.040.05": 142})["Диметикон"]
        assert need.shortage == Decimal("7100")
        # `after` равен нулю не потому, что партия съела запас, а потому,
        # что её не выпустить.
        assert need.below_min_after is False

    def test_минимум_не_задан_молчим(self, shampoo):
        need = needs_by_name({"100.011.05": 1})["Вода дистиллированная"]
        assert need.min_balance is None
        assert need.below_min_now is False
        assert need.below_min_after is False


class TestArchivedMaterial:
    """Архивное сырьё в действующей техкарте — рассогласование учёта."""

    def test_архивный_материал_помечен(self, shampoo):
        """Карту забыли поправить вместе с линейкой.

        Молчать нельзя: остатка по архивному МойСклад не отдаёт, и строка
        выглядела бы загадочным «не знаем». На боевых данных так и было —
        этикетки «(Старое)» и триггер висели в трёх кондиционерах,
        и причина была в архиве, а не в пробеле учёта.
        """
        from core.models import Product

        Product.objects.filter(name="Отдушка «Лесные ягоды»").update(archived=True)

        needs = needs_by_name({"100.011.05": 1})
        assert needs["Отдушка «Лесные ягоды»"].archived is True
        # Из расчёта не выбрасывается: техкарта его требует, и закупать
        # придётся, пока карту не поправят.
        assert needs["Отдушка «Лесные ягоды»"].quantity == Decimal("4")
        assert needs["Вода дистиллированная"].archived is False


class TestPriceAndLeadTime:
    """Во сколько обойдётся и когда приедет."""

    def test_цена_из_последней_приёмки(self, shampoo, make_document, supplier):
        from core.models import DocumentKind, Product

        water = Product.objects.get(name="Вода дистиллированная")
        position(
            make_document(kind=DocumentKind.SUPPLY, moment=moscow(2026, 4, 1),
                          agent=supplier),
            water, 1000, price_kopecks="2.0",
        )
        position(
            make_document(kind=DocumentKind.SUPPLY, moment=moscow(2026, 6, 1),
                          agent=supplier),
            water, 1000, price_kopecks="2.5",
        )

        need = needs_by_name({"100.011.05": 100})["Вода дистиллированная"]
        # Последняя, а не первая и не средняя.
        assert need.price.price_kopecks == Decimal("2.500000")
        # Не хватает 10 000 г по 2,5 копейки = 25 000 копеек.
        assert need.cost_kopecks == 25000

    def test_цены_нет_стоимость_прочерк_а_не_ноль(self, shampoo):
        """Ноль читался бы как «материал достался даром»."""
        need = needs_by_name({"100.011.05": 100})["Вода дистиллированная"]
        assert need.price is None
        assert need.cost_kopecks is None

    def test_срок_по_своему_поставщику(
        self, shampoo, make_document, supplier, run
    ):
        """Два материала у двух поставщиков — и сроки у них разные.

        Проверять на одном нельзя: медиана «по всем» совпала бы с медианой
        «по своему», и подмена прошла бы незамеченной. Именно так этот тест
        и проходил вхолостую, пока в расчёт попадал один поставщик.

        Общая медиана по обоим дала бы 3,5 дня — срок, которого нет ни
        у одного из них: первый везёт неделю, у второго забирают.
        """
        from core.models import Counterparty, DocumentKind, Product

        water = Product.objects.get(name="Вода дистиллированная")
        scent = Product.objects.get(name="Отдушка «Лесные ягоды»")
        fast = Counterparty.objects.create(
            ms_id="50000000-0000-0000-0000-000000000009",
            name="ООО «Принтец»", last_seen_run=run,
        )

        for product, agent, ordered, arrived in (
            (water, supplier, moscow(2026, 6, 1), moscow(2026, 6, 8)),
            (scent, fast, moscow(2026, 6, 10), moscow(2026, 6, 10)),
        ):
            order = make_document(
                kind=DocumentKind.PURCHASE_ORDER, moment=ordered, agent=agent
            )
            position(
                make_document(
                    kind=DocumentKind.SUPPLY,
                    moment=arrived,
                    agent=agent,
                    purchase_order=order,
                ),
                product, 1000, price_kopecks="2.0",
            )

        needs = needs_by_name({"100.011.05": 100})
        assert needs["Вода дистиллированная"].price.supplier == "ООО «Химпитерторг»"
        assert needs["Вода дистиллированная"].waiting.days == Decimal("7")
        assert needs["Отдушка «Лесные ягоды»"].price.supplier == "ООО «Принтец»"
        assert needs["Отдушка «Лесные ягоды»"].waiting.days == Decimal("0")
