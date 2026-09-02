"""Обратная запись себестоимости в карточки товаров.

Здесь ошибка не «показали не то число», а «испортили учёт компании»,
и откатить её можно только руками. Поэтому проверяется не только результат,
но и то, чего писаться не должно: ноль вместо неизвестного, лишние цены
в теле запроса, запись при выключенном выключателе.
"""

from decimal import Decimal

import pytest

from core.models import (
    Product,
    ProductKind,
    Stock,
    SyncKind,
    SyncRun,
    WritebackKind,
    WritebackStatus,
    WritebackSwitch,
)
from moysklad.limits import ApiDisabledRisk
from moysklad.writeback.cost_prices import (
    COST_PRICE_TYPE,
    ReferenceMissing,
    _round_kopecks,
    run_cost_prices_writeback,
)
from moysklad.writeback.journal import WritebackDisabled

pytestmark = pytest.mark.django_db

BASE = "https://api.moysklad.ru/api/remap/1.2"
PRICE_TYPE_HREF = f"{BASE}/context/companysettings/pricetype/cost-type-id"
OTHER_TYPE_HREF = f"{BASE}/context/companysettings/pricetype/retail-type-id"
CURRENCY_HREF = f"{BASE}/entity/currency/rub-id"
DATE_FIELD_HREF = f"{BASE}/entity/product/metadata/attributes/date-field-id"


def price(href: str, value: int) -> dict:
    return {"value": value, "priceType": {"meta": {"href": href}}}


class FakeClient:
    """Клиент с заданными ответами. Запоминает всё, что у него просили записать."""

    def __init__(self, products, *, date_field=True, put_fails=()):
        self._products = products
        self._date_field = date_field
        self._put_fails = set(put_fails)
        self.puts: list[tuple[str, dict]] = []
        self.iterations: list[tuple[str, dict | None]] = []
        self.request_count = 0

    def get(self, path, params=None):
        if path == "/context/companysettings/pricetype":
            return [
                {"name": "Розница", "meta": {"href": OTHER_TYPE_HREF}},
                {"name": COST_PRICE_TYPE, "meta": {"href": PRICE_TYPE_HREF}},
            ]
        raise AssertionError(f"Неожиданный GET: {path}")

    def iterate(self, path, params=None):
        self.iterations.append((path, params))
        if path == "/entity/currency":
            yield {"default": True, "meta": {"href": CURRENCY_HREF}}
        elif path == "/entity/product/metadata/attributes":
            if self._date_field:
                yield {
                    "name": "Дата обновления себестоимости",
                    "meta": {"href": DATE_FIELD_HREF},
                }
        elif path == "/entity/product":
            yield from self._products
        else:
            raise AssertionError(f"Неожиданный обход: {path}")

    def put(self, path, payload):
        ms_id = path.rsplit("/", 1)[-1]
        if ms_id in self._put_fails:
            raise RuntimeError("МойСклад ответил 400")
        self.puts.append((ms_id, payload))
        return {}


@pytest.fixture
def run():
    return SyncRun.objects.create(kind=SyncKind.DOCUMENTS)


@pytest.fixture
def make_product(run):
    def _make(ms_id, name, cost, *, kind=ProductKind.PRODUCT, deleted=False):
        product = Product.objects.create(
            ms_id=ms_id, name=name, kind=kind, last_seen_run=run
        )
        if deleted:
            from django.utils import timezone

            product.deleted_at = timezone.now()
            product.save(update_fields=["deleted_at"])
        Stock.objects.create(product=product, cost_kopecks=Decimal(cost))
        return product

    return _make


class TestRounding:
    def test_fractional_kopecks_round_half_up(self):
        """Тип цены хранит целые копейки, а FIFO приходит дробным.

        У 150 позиций из 255 себестоимость дробная, вплоть до бесконечной
        дроби. Усечение вместо округления давало бы копейку расхождения
        с отчётом у каждого второго товара.
        """
        assert _round_kopecks(Decimal("11841.934782608696")) == 11842
        assert _round_kopecks(Decimal("18548.5")) == 18549
        assert _round_kopecks(Decimal("18548.4")) == 18548


class TestWhatGetsWritten:
    def test_writes_only_changed_products(self, make_product):
        make_product("11111111-1111-1111-1111-111111111111", "Воск", "18548.5")
        make_product("22222222-2222-2222-2222-222222222222", "Основа", "3000")

        client = FakeClient([
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "name": "Воск",
                "salePrices": [price(PRICE_TYPE_HREF, 18000)],
            },
            {
                "id": "22222222-2222-2222-2222-222222222222",
                "name": "Основа",
                "salePrices": [price(PRICE_TYPE_HREF, 3000)],
            },
        ])

        run = run_cost_prices_writeback(client)

        assert [ms_id for ms_id, _ in client.puts] == [
            "11111111-1111-1111-1111-111111111111"
        ]
        assert run.status == WritebackStatus.SUCCESS
        assert run.changed == 1
        assert run.skipped == 1

    def test_payload_carries_only_the_cost_price(self, make_product):
        """В теле уходит одна цена, а не весь набор.

        Документация обещает: тип цены, не переданный в теле, не изменяется.
        Прежний демон слал все цены товара целиком и мог затереть ту,
        которую человек поправил между чтением и записью.
        """
        make_product("11111111-1111-1111-1111-111111111111", "Воск", "18548.5")

        client = FakeClient([{
            "id": "11111111-1111-1111-1111-111111111111",
            "name": "Воск",
            "salePrices": [
                price(OTHER_TYPE_HREF, 99000),
                price(PRICE_TYPE_HREF, 18000),
            ],
        }])

        run_cost_prices_writeback(client)

        _, payload = client.puts[0]
        assert len(payload["salePrices"]) == 1
        assert payload["salePrices"][0]["value"] == 18549
        hrefs = {p["priceType"]["meta"]["href"] for p in payload["salePrices"]}
        assert OTHER_TYPE_HREF not in hrefs

    def test_empty_cost_price_gets_filled(self, make_product):
        """У товара цены ещё нет вовсе — это не «совпало», а «надо записать»."""
        make_product("11111111-1111-1111-1111-111111111111", "Воск", "18548.5")

        client = FakeClient([{
            "id": "11111111-1111-1111-1111-111111111111",
            "name": "Воск",
            "salePrices": [price(OTHER_TYPE_HREF, 99000)],
        }])

        run = run_cost_prices_writeback(client)

        assert run.changed == 1
        assert run.changes.get().old_value is None

    def test_date_is_written_when_field_exists(self, make_product):
        make_product("11111111-1111-1111-1111-111111111111", "Воск", "18548.5")
        client = FakeClient([{
            "id": "11111111-1111-1111-1111-111111111111",
            "name": "Воск",
            "salePrices": [],
        }])

        run_cost_prices_writeback(client)

        _, payload = client.puts[0]
        assert payload["attributes"][0]["meta"]["href"] == DATE_FIELD_HREF

    def test_missing_date_field_does_not_stop_the_price(self, make_product):
        """Нет доп. поля — пишем цену без даты, а не падаем.

        Поле заводится руками в учёте, и его отсутствие не повод оставить
        себестоимость пустой.
        """
        make_product("11111111-1111-1111-1111-111111111111", "Воск", "18548.5")
        client = FakeClient(
            [{"id": "11111111-1111-1111-1111-111111111111", "name": "Воск",
              "salePrices": []}],
            date_field=False,
        )

        run = run_cost_prices_writeback(client)

        assert run.changed == 1
        assert "attributes" not in client.puts[0][1]


class TestWhatMustNotBeWritten:
    def test_zero_cost_is_never_written(self, make_product):
        """Ноль в остатках означает «FIFO неизвестен», а не «товар бесплатный».

        У 103 позиций из 315 остатка нет постоянно. Записать им ноль значит
        заменить незнание уверенной ложью — и обнулить себестоимость
        в карточке товара, который просто закончился на складе.
        """
        make_product("11111111-1111-1111-1111-111111111111", "Воск", "0")

        client = FakeClient([{
            "id": "11111111-1111-1111-1111-111111111111",
            "name": "Воск",
            "salePrices": [price(PRICE_TYPE_HREF, 18000)],
        }])

        run = run_cost_prices_writeback(client)

        assert client.puts == []
        assert run.skipped == 1

    def test_product_missing_from_mirror_is_skipped(self):
        """Товар есть в учёте, но ещё не доехал в зеркало — пропускаем."""
        client = FakeClient([{
            "id": "33333333-3333-3333-3333-333333333333",
            "name": "Новый товар",
            "salePrices": [],
        }])

        run = run_cost_prices_writeback(client)

        assert client.puts == []
        assert run.considered == 1
        assert run.skipped == 1

    def test_deleted_product_is_skipped(self, make_product):
        """Исчезнувший из учёта товар не получает записи."""
        make_product(
            "11111111-1111-1111-1111-111111111111", "Воск", "18548.5", deleted=True
        )
        client = FakeClient([{
            "id": "11111111-1111-1111-1111-111111111111",
            "name": "Воск",
            "salePrices": [],
        }])

        run_cost_prices_writeback(client)

        assert client.puts == []

    def test_dry_run_writes_nothing(self, make_product):
        make_product("11111111-1111-1111-1111-111111111111", "Воск", "18548.5")
        client = FakeClient([{
            "id": "11111111-1111-1111-1111-111111111111",
            "name": "Воск",
            "salePrices": [price(PRICE_TYPE_HREF, 18000)],
        }])

        run = run_cost_prices_writeback(client, dry_run=True)

        assert client.puts == []
        assert run.dry_run is True
        assert run.changed == 1, "пробный прогон обязан показать, что изменилось бы"
        assert run.changes.count() == 1


class TestSwitch:
    def test_every_kind_of_writeback_has_a_switch_row(self):
        """У каждого вида записи обязана быть строка выключателя.

        Правило `CLAUDE.md` §6. Без строки выключатель есть только в коде:
        в админке его не видно, и остановить запись в момент поломки нечем.
        Новый вид записи = новая строка в миграции `0014_seed_writeback_switches`.
        """
        existing = set(WritebackSwitch.objects.values_list("kind", flat=True))
        missing = set(WritebackKind.values) - existing

        assert not missing, (
            f"Виды записи без выключателя: {sorted(missing)}. "
            f"Добавьте их в KINDS миграции 0014_seed_writeback_switches."
        )

    def test_disabled_switch_blocks_the_run(self, make_product):
        WritebackSwitch.objects.update_or_create(
            kind=WritebackKind.COST_PRICES, defaults={"enabled": False}
        )
        make_product("11111111-1111-1111-1111-111111111111", "Воск", "18548.5")
        client = FakeClient([{
            "id": "11111111-1111-1111-1111-111111111111",
            "name": "Воск",
            "salePrices": [],
        }])

        with pytest.raises(WritebackDisabled):
            run_cost_prices_writeback(client)

        assert client.puts == []

    def test_blocked_run_is_still_journalled(self, make_product):
        """Выключенная запись обязана быть видна в журнале.

        Иначе «почему себестоимость не обновляется» приходится выяснять
        по конфигурации: в журнале выключенный прогон выглядел бы так же,
        как незапускавшийся.
        """
        from core.models import WritebackRun

        WritebackSwitch.objects.update_or_create(
            kind=WritebackKind.COST_PRICES, defaults={"enabled": False}
        )
        client = FakeClient([])

        with pytest.raises(WritebackDisabled):
            run_cost_prices_writeback(client)

        assert WritebackRun.objects.get().status == WritebackStatus.BLOCKED

    def test_missing_switch_row_means_enabled(self, make_product):
        """Нет строки — запись работает: запрет должен быть решением человека.

        Умолчание обратное реестру страниц, и намеренно: там забывчивость
        обязана закрывать доступ, а здесь отсутствие строки означает
        «выключатель ещё не заводили», а не «запрещено».
        """
        WritebackSwitch.objects.filter(kind=WritebackKind.COST_PRICES).delete()
        make_product("11111111-1111-1111-1111-111111111111", "Воск", "18548.5")
        client = FakeClient([{
            "id": "11111111-1111-1111-1111-111111111111",
            "name": "Воск",
            "salePrices": [],
        }])

        run_cost_prices_writeback(client)

        assert len(client.puts) == 1


class TestFailures:
    def test_missing_price_type_reaches_the_operator(self):
        """Нет типа цены — человеку говорят, что завести, а не «итог: не удалось».

        Ошибка обязана подняться наружу: команда превращает её в понятное
        указание. Спрячь мы её в статус прогона — оператор получил бы
        «Итог прогона: Не удалось» и пошёл читать логи.

        Тест сначала был написан с костылём, который сам же и перевыбрасывал
        ошибку из статуса, — то есть проверял не то, что нужно. Костыль
        и был признаком дефекта.
        """
        class NoPriceType(FakeClient):
            def get(self, path, params=None):
                return [{"name": "Розница", "meta": {"href": OTHER_TYPE_HREF}}]

        with pytest.raises(ReferenceMissing):
            run_cost_prices_writeback(NoPriceType([]))

    def test_failed_lookup_still_closes_the_journal(self):
        """Даже когда ошибка уходит наружу, прогон не остаётся «идущим»."""
        from core.models import WritebackRun

        class NoPriceType(FakeClient):
            def get(self, path, params=None):
                return [{"name": "Розница", "meta": {"href": OTHER_TYPE_HREF}}]

        with pytest.raises(ReferenceMissing):
            run_cost_prices_writeback(NoPriceType([]))

        assert WritebackRun.objects.get().status == WritebackStatus.FAILED

    def test_single_failed_put_does_not_stop_the_rest(self, make_product):
        make_product("11111111-1111-1111-1111-111111111111", "Воск", "18548.5")
        make_product("22222222-2222-2222-2222-222222222222", "Основа", "3000")

        client = FakeClient(
            [
                {"id": "11111111-1111-1111-1111-111111111111", "name": "Воск",
                 "salePrices": []},
                {"id": "22222222-2222-2222-2222-222222222222", "name": "Основа",
                 "salePrices": []},
            ],
            put_fails=["11111111-1111-1111-1111-111111111111"],
        )

        run = run_cost_prices_writeback(client)

        assert run.failed == 1
        assert run.changed == 1
        assert run.status == WritebackStatus.PARTIAL

    def test_breaker_stops_everything(self, make_product):
        """Серия 429 останавливает прогон целиком, а не одну запись.

        Продолжить — значит добить общий с ботом лимит и потерять доступ
        к API для всей компании. Включают обратно только через поддержку.
        """
        make_product("11111111-1111-1111-1111-111111111111", "Воск", "18548.5")
        make_product("22222222-2222-2222-2222-222222222222", "Основа", "3000")

        class Breaking(FakeClient):
            def put(self, path, payload):
                raise ApiDisabledRisk("3 ответа 429 подряд")

        client = Breaking([
            {"id": "11111111-1111-1111-1111-111111111111", "name": "Воск",
             "salePrices": []},
            {"id": "22222222-2222-2222-2222-222222222222", "name": "Основа",
             "salePrices": []},
        ])

        run = run_cost_prices_writeback(client)

        assert run.status == WritebackStatus.STOPPED
        assert run.changed == 0

    def test_change_limit_stops_the_run(self, make_product):
        """Слишком много изменений разом — остановка, а не запись.

        За 22 дня наблюдений самый крупный прогон менял 16 товаров из 315.
        Прогон, решивший переписать сотню, ошибок не даёт вовсе — но это
        ровно та серия PUT, за которую МойСклад отключает доступ.
        """
        products = []
        for index in range(40):
            ms_id = f"{index:08d}-1111-1111-1111-111111111111"
            make_product(ms_id, f"Товар {index}", "1000")
            products.append({"id": ms_id, "name": f"Товар {index}", "salePrices": []})

        client = FakeClient(products)
        run = run_cost_prices_writeback(client)

        assert run.status == WritebackStatus.STOPPED
        assert len(client.puts) <= 31, "после потолка запись обязана прекратиться"


class TestReviewFindings:
    """Дефекты, найденные обзором 02.09. Каждый закреплён до починки."""

    def test_journal_row_is_written_immediately(self, make_product):
        """Строка журнала уходит в базу до конца прогона, а не пачкой в конце.

        Крон запускает команду под `timeout`, а тот шлёт SIGTERM, на котором
        Python завершает процесс без исключения: ни `finally`, ни `except`
        не отработают. Накопленные в памяти строки пропали бы — и запись,
        уже ушедшая в учёт, осталась бы без следа.
        """
        from core.models import WritebackChange

        make_product("11111111-1111-1111-1111-111111111111", "Воск", "18548.5")
        make_product("22222222-2222-2222-2222-222222222222", "Основа", "3000")
        seen: list[int] = []

        class CountingClient(FakeClient):
            def put(self, path, payload):
                # Сколько строк уже в базе к началу очередной записи в учёт.
                seen.append(WritebackChange.objects.count())
                return super().put(path, payload)

        run_cost_prices_writeback(CountingClient([
            {"id": "11111111-1111-1111-1111-111111111111", "name": "Воск",
             "salePrices": []},
            {"id": "22222222-2222-2222-2222-222222222222", "name": "Основа",
             "salePrices": []},
        ]))

        assert seen == [0, 1], (
            "к моменту второй записи в учёт строка о первой обязана уже лежать "
            f"в базе, а не ждать конца прогона: {seen}"
        )

    def test_fractional_existing_price_is_not_rewritten_forever(self, make_product):
        """Дробная цена в карточке читается тем же округлением, что и пишется.

        Человек поставил 11841.6; расчёт даёт 11842. При чтении через `int()`
        стороны сравнения расходятся, и товар переписывался бы каждый прогон —
        вечно, незаметно и за счёт общей с ботом корзины лимита.
        """
        make_product("11111111-1111-1111-1111-111111111111", "Воск", "11841.6")

        client = FakeClient([{
            "id": "11111111-1111-1111-1111-111111111111",
            "name": "Воск",
            "salePrices": [price(PRICE_TYPE_HREF, 11841.6)],
        }])

        run = run_cost_prices_writeback(client)

        assert client.puts == [], "товар с дробной ценой переписывается вхолостую"
        assert run.skipped == 1

    def test_archived_products_are_excluded_explicitly(self, make_product):
        """Архивные исключаются фильтром, а не надеждой на умолчание API.

        Умолчание чужого сервиса сменится молча, и заметить это будет нечем,
        а PUT в архивный товар и жжёт общий лимит, и занимает место
        под потолком изменений.
        """
        client = FakeClient([])

        run_cost_prices_writeback(client)

        assert ("/entity/product", {"filter": "archived=false"}) in client.iterations

    def test_cron_run_is_not_marked_as_manual(self, make_product):
        """Прогон по расписанию не числится запущенным человеком.

        Иначе поле отвечает «вручную» на все четыре суточных прогона
        и перестаёт отвечать на вопрос, ради которого заведено.
        """
        run = run_cost_prices_writeback(FakeClient([]), manual=False)
        assert run.triggered_manually is False

        manual = run_cost_prices_writeback(FakeClient([]), manual=True)
        assert manual.triggered_manually is True
