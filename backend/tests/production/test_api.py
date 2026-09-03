"""Расчёт производства: доступ, разбор запроса, контракт ответа.

Контракт проверяется через API, а не через сервис. Причина в дефекте
соседней страницы: доля больше единицы не влезала в `DecimalField(9, 8)`,
и весь ответ уходил пятисотой — падала сериализация, которой тест
на сервисе не видит вовсе.
"""

import pytest

from tests.production.conftest import moscow, position

pytestmark = pytest.mark.django_db

PAGE_KEY = "production"
PRODUCTS = "/api/production/products/"
BATCH = "/api/production/batch/"


class TestAccess:
    def test_требует_входа(self, client):
        assert client.get(PRODUCTS).status_code == 401
        assert client.get(BATCH).status_code == 401

    def test_права_соседнего_раздела_не_открывают_этот(self, client, make_user):
        """Проверяется «Материалами в отгрузках»: они считают по тем же
        отгрузкам и по тем же техкартам, и перепутать ключ в реестре легко."""
        client.force_login(make_user(pages=["shipments-materials"]))
        assert client.get(PRODUCTS).status_code == 403
        assert client.get(BATCH).status_code == 403

    def test_пускает_с_правом_на_раздел(self, client, make_user):
        client.force_login(make_user(pages=[PAGE_KEY]))
        assert client.get(PRODUCTS).status_code == 200
        assert client.get(BATCH).status_code == 200


class TestQuery:
    @pytest.fixture(autouse=True)
    def logged_in(self, client, make_user):
        client.force_login(make_user(pages=[PAGE_KEY]))

    def test_перевёрнутый_период_это_ошибка_а_не_пустой_список(self, client):
        response = client.get(
            PRODUCTS, {"date_from": "2026-07-01", "date_to": "2026-06-01"}
        )
        assert response.status_code == 400

    def test_горизонт_вне_границ_отклоняется(self, client):
        """Не обрезается молча: ответ на `horizon=4000` должен сказать,
        что столько не считаем, — иначе человек решит, что посчитали."""
        assert client.get(PRODUCTS, {"horizon": 0}).status_code == 400
        assert client.get(PRODUCTS, {"horizon": 4000}).status_code == 400

    def test_горизонт_по_умолчанию_шестьдесят(self, client):
        assert client.get(PRODUCTS).json()["horizon"] == 60

    @pytest.mark.parametrize(
        "item",
        [
            "100.011.05:",         # двоеточие без количества
            ":5",                  # без артикула
            " :5",                 # артикул из пробелов
            "100.011.05:0",        # ноль штук
            "100.011.05:-3",       # минус
            "100.011.05:2.5",      # половина флакона
            "100.011.05:5:7",      # лишнее двоеточие
        ],
    )
    def test_сломанная_строка_партии_отклоняется_целиком(self, client, item):
        """Сломанная ссылка — не выбор человека.

        Пропусти мы непонятную строку молча, расчёт по половине партии
        выглядел бы точно так же, как расчёт по целой.

        Артикул без количества сюда не относится — он законен и означает
        «посчитай сам»; а вот артикул из пробелов отвергается: пустая строка
        совпала бы с позициями, у которых артикула нет вовсе, то есть
        с сырьём, которое товаром здесь не считается.
        """
        assert client.get(BATCH, {"item": item}).status_code == 400

    def test_партия_сверх_потолка_отклоняется(self, client):
        response = client.get(BATCH, {"item": [f"1.{n:03d}.01:1" for n in range(201)]})
        assert response.status_code == 400

    def test_вся_партия_доезжает_а_не_последняя_позиция(
        self, client, shampoo, make_product, make_plan, piece
    ):
        """Партия едет повторяющимся `item`, и доехать обязана целиком.

        Потеряй разбор все строки, кроме последней, расчёт по одной позиции
        выглядел бы точно так же, как расчёт по двадцати, — и ошибка была бы
        не в числах, а в том, какие числа сложили.
        """
        water = shampoo.produced_by.first().materials.first().product
        other = make_product(
            "Кондиционер", article="200.040.05", code="2-002", uom=piece
        )
        make_plan(other, [(water, 100)], output=1)

        payload = client.get(
            BATCH, {"item": ["100.011.05:10", "200.040.05:3"]}
        ).json()
        assert [line["article"] for line in payload["lines"]] == [
            "100.011.05",
            "200.040.05",
        ]
        assert payload["summary"]["products_count"] == 2


class TestContract:
    @pytest.fixture(autouse=True)
    def logged_in(self, client, make_user):
        client.force_login(make_user(pages=[PAGE_KEY]))

    def test_пустая_партия_это_пустой_ответ_а_не_ошибка(self, client):
        """Страницу открывают до того, как что-то отобрали."""
        payload = client.get(BATCH).json()
        assert payload["lines"] == []
        assert payload["materials"] == []
        assert payload["summary"]["shortages_count"] == 0

    def test_строка_товара_несёт_составляющие_своих_чисел(self, client, shampoo, sell):
        """Формула собирается из полученного, а не пересчитывается на фронте."""
        sell(shampoo, 30, day=1)
        row = client.get(
            PRODUCTS,
            {"date_from": "2026-05-01", "date_to": "2026-05-30", "horizon": 60},
        ).json()["rows"][0]

        assert row["article"] == "100.011.05"
        assert row["coverage"]["per_day"] is not None
        assert row["coverage"]["days_of_period"] == 30
        assert row["coverage"]["level"] == "critical"
        # Горизонт едет в строке: без него «варить 57» не складывается
        # в формулу.
        assert row["horizon"] == 60
        assert row["suggested"] == 57

    def test_строка_материала_объясняет_себя(self, client, shampoo):
        material = next(
            row
            for row in client.get(BATCH, {"item": "100.011.05:100"}).json()["materials"]
            if row["name"] == "Вода дистиллированная"
        )
        assert material["shortage"] == "10000.000000"
        assert material["uom"] == "г"
        # Откуда столько: цепочка техкарт и товар партии, давший этот расход.
        assert material["via"] == [
            {"chain": ["Техкарта 1"], "quantity": "40000.000000"}
        ]
        assert material["sources"][0]["name"] == "Шампунь для лошадей 500 мл"

    def test_негодная_строка_приходит_названной(self, client, shampoo, make_product):
        make_product("Старый шампунь", article="100.004.05", archived=True)
        lines = {
            line["article"]: line
            for line in client.get(
                BATCH, {"item": ["100.004.05:2", "999.999.99:1"]}
            ).json()["lines"]
        }
        assert lines["100.004.05"]["problem"] == "archived"
        assert lines["100.004.05"]["name"] == "Старый шампунь"
        assert lines["999.999.99"]["problem"] == "unknown"
        assert lines["999.999.99"]["product_id"] is None

    def test_свежесть_считается_по_обоим_источникам(self, client, shampoo):
        """Страница свежа настолько, насколько свеж её самый отставший источник.

        Продажи берутся из документов, остатки — из отчёта, и прогоны у них
        разные. Возьми страница только время документов, она выглядела бы
        свежей при остатках недельной давности — ровно то, что случилось
        03.09, когда семнадцать кончившихся товаров показались «без остатка
        в отчёте».
        """
        from django.utils import timezone

        from core.models import SyncKind, SyncRun, SyncStatus

        SyncRun.objects.create(
            kind=SyncKind.DOCUMENTS,
            status=SyncStatus.SUCCESS,
            finished_at=timezone.now(),
        )
        # Остатки не синхронизировались ни разу — обещать свежесть нечем.
        for url in (PRODUCTS, BATCH):
            assert client.get(url).json()["synced_at"] is None

        stock = timezone.now()
        SyncRun.objects.create(
            kind=SyncKind.STATE, status=SyncStatus.SUCCESS, finished_at=stock
        )
        for url in (PRODUCTS, BATCH):
            assert client.get(url).json()["synced_at"] is not None


class TestSuggestedInBatch:
    """Позиция без количества: «посчитай сам» — и поиск на это не влияет."""

    @pytest.fixture(autouse=True)
    def logged_in(self, client, make_user):
        client.force_login(make_user(pages=[PAGE_KEY]))

    def test_голый_артикул_считается_по_горизонту(self, client, shampoo, sell):
        sell(shampoo, 30, day=1)
        period = {"date_from": "2026-05-01", "date_to": "2026-05-30"}

        # 1 шт/день × 60 дней − 3 на складе = 57 штук.
        wide = client.get(BATCH, {"item": "100.011.05", "horizon": 60, **period})
        assert wide.json()["summary"]["units_count"] == 57
        # Тот же подбор на другом сроке даёт другую партию.
        short = client.get(BATCH, {"item": "100.011.05", "horizon": 30, **period})
        assert short.json()["summary"]["units_count"] == 27

    def test_поиск_не_урезает_партию(
        self, client, shampoo, make_product, make_plan, make_stock, sell
    ):
        """Партия собрана до поиска и от него зависеть не должна.

        Разрешай количества по найденному — «Взять всё» на тридцати позициях
        и следом запрос «шампунь» пересчитали бы закупку по трём. Без единого
        признака, что считали не то.
        """
        water = shampoo.produced_by.first().materials.first().product
        other = make_product(
            "Кондиционер", article="200.040.05", code="2-002", uom=shampoo.uom
        )
        make_plan(other, [(water, 100)], output=1)
        make_stock(other, 1)
        sell(shampoo, 30, day=1)
        sell(other, 30, day=1)

        picked = {
            "item": ["100.011.05", "200.040.05"],
            "horizon": 60,
            "date_from": "2026-05-01",
            "date_to": "2026-05-30",
        }
        whole = client.get(BATCH, picked).json()["summary"]
        found = client.get(BATCH, {**picked, "search": "шампунь"}).json()["summary"]

        assert whole["products_count"] == 2
        assert found["products_count"] == 2
        assert found["units_count"] == whole["units_count"]

    def test_введённое_руками_горизонт_не_трогает(
        self, client, shampoo, make_product, make_plan, make_stock, sell
    ):
        """Закреплённое рядом с несвязанным: первое стоит, второе едет.

        Проверять на одной закреплённой позиции нельзя — разрешение
        количеств до расчёта предложений вообще не доходит, и подмена
        «предложение перебивает введённое» прошла бы незамеченной.
        """
        water = shampoo.produced_by.first().materials.first().product
        other = make_product(
            "Кондиционер", article="200.040.05", code="2-002", uom=shampoo.uom
        )
        make_plan(other, [(water, 100)], output=1)
        make_stock(other, 0)
        sell(shampoo, 30, day=1)
        sell(other, 30, day=1)
        period = {"date_from": "2026-05-01", "date_to": "2026-05-30"}

        # Шампунь закреплён на 120, кондиционер считается сам: 1 шт/день
        # × горизонт − 0 на складе.
        picked = {"item": ["100.011.05:120", "200.040.05"], **period}
        assert client.get(BATCH, {**picked, "horizon": 30}).json()["summary"][
            "units_count"
        ] == 150
        assert client.get(BATCH, {**picked, "horizon": 90}).json()["summary"][
            "units_count"
        ] == 210


class TestNothingToSuggest:
    """Отмечено, а предложить нечего — строка возвращается названной."""

    @pytest.fixture(autouse=True)
    def logged_in(self, client, make_user):
        client.force_login(make_user(pages=[PAGE_KEY]))

    def test_позиция_без_предложения_не_исчезает_молча(
        self, client, make_product, make_plan, piece
    ):
        """Галочка стоит — значит человек вправе знать, почему её нет в расчёте.

        Раньше такая позиция выпадала в `resolve`: ни в `lines`, ни
        в предупреждениях, а `products_count` её не считал. Ровно то,
        против чего заведён `LineProblem`.
        """
        water = make_product("Вода", code="1-001")
        bottle = make_product(
            "Шампунь", article="100.011.05", code="2-001", uom=piece
        )
        make_plan(bottle, [(water, 100)])
        # Ни продаж, ни остатка — предлагать нечего.

        payload = client.get(BATCH, {"item": "100.011.05"}).json()
        line = payload["lines"][0]
        assert line["article"] == "100.011.05"
        assert line["problem"] == "no_quantity"
        assert line["quantity"] is None
        assert line["name"] == "Шампунь"
        # И в партию она не попала: считать нечего.
        assert payload["summary"]["products_count"] == 0
        assert payload["materials"] == []

    def test_введённое_руками_считается_даже_без_предложения(
        self, client, make_product, make_plan, make_stock, piece
    ):
        water = make_product("Вода", code="1-001")
        bottle = make_product(
            "Шампунь", article="100.011.05", code="2-001", uom=piece
        )
        make_plan(bottle, [(water, 100)])
        make_stock(water, 10000)

        payload = client.get(BATCH, {"item": "100.011.05:5"}).json()
        assert payload["lines"][0]["problem"] is None
        assert payload["summary"]["units_count"] == 5


class TestLeadTimeDenominator:
    """Срок партии обязан сказать, по скольким позициям он известен."""

    @pytest.fixture(autouse=True)
    def logged_in(self, client, make_user):
        client.force_login(make_user(pages=[PAGE_KEY]))

    def test_рядом_со_сроком_сколько_позиций_его_составили(
        self, client, shampoo, make_document, supplier
    ):
        """Срок известен только там, где известен поставщик.

        А поставщик берётся из последней приёмки: без цены нет и его.
        «Ждать 3 дня» по одной позиции из двух без знаменателя читается
        как срок по всем.
        """
        from core.models import DocumentKind, Product

        water = Product.objects.get(name="Вода дистиллированная")
        order = make_document(
            kind=DocumentKind.PURCHASE_ORDER, moment=moscow(2026, 6, 1),
            agent=supplier,
        )
        position(
            make_document(
                kind=DocumentKind.SUPPLY,
                moment=moscow(2026, 6, 4),
                agent=supplier,
                purchase_order=order,
            ),
            water, 1000, price_kopecks="2.0",
        )

        # Не хватает воды и отдушки; поставщик известен только у воды.
        summary = client.get(BATCH, {"item": "100.011.05:100"}).json()["summary"]
        assert summary["shortages_count"] == 2
        assert summary["max_lead_time_days"] == "3.0"
        assert summary["timed_shortages_count"] == 1
