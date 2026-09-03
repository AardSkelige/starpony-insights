"""Синхронизация прибыльности: что спрашиваем и что сохраняем.

Ошибки здесь тихие все до одной: неверные границы дня теряют продажу без
следа, потерянный запрос по площадкам оставляет их маржу завышенной,
а не удалённая строка прошлого дня переживает отмену продажи.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from core.models import ProfitDay, SyncKind, SyncRun
from moysklad.sync.profit import RECENT_WINDOW_DAYS, days_to_sync, sync_profit

from .conftest import DAY, moscow  # noqa: F401

pytestmark = pytest.mark.django_db


class RecordingClient:
    """Клиент, который помнит запросы и отвечает заготовленным."""

    def __init__(self, answers=None):
        self.calls = []
        self._answers = answers or {}

    def iterate(self, path, params=None):
        self.calls.append((path, dict(params or {})))
        key = (params or {}).get("momentFrom", ""), (params or {}).get("filter", "")
        yield from self._answers.get(key, [])


def report_row(product, *, quantity=10, revenue=54_936, cost=30_716):
    """Строка отчёта прибыльности, как её отдаёт API."""
    return {
        "assortment": {
            "meta": {
                "href": "https://api.moysklad.ru/api/remap/1.2/entity/product/"
                f"{product.ms_id}"
            },
            "name": product.name,
            "article": product.article,
        },
        "sellQuantity": quantity,
        "sellSum": revenue,
        "sellCostSum": cost,
    }


class TestRequest:
    """Что именно спрашивается у отчёта."""

    def test_day_ends_at_the_start_of_the_next_one(self, product, make_demand):
        """Верхняя граница строгая: продажа в 23:59:59.5 обязана войти в день.

        Конец суток «23:59:59» отрезал бы её молча — тот же дефект, что
        уже разобран в `api/common/selection.py`.
        """
        make_demand(moment=moscow(2026, 7, 15))
        client = RecordingClient()

        sync_profit(client, SyncRun.objects.create(kind=SyncKind.DOCUMENTS))

        first = client.calls[0][1]
        assert first["momentFrom"] == "2026-07-15 00:00:00"
        assert first["momentTo"] == "2026-07-16 00:00:00"

    def test_marketplaces_are_asked_separately(self, product, make_demand):
        """Второй запрос на день — с фильтром по группе контрагента.

        Без него маржа площадок сливается с прямыми продажами, и завышенное
        на процент площадки число выдаётся за факт.
        """
        make_demand(moment=moscow(2026, 7, 15))
        client = RecordingClient()

        sync_profit(client, SyncRun.objects.create(kind=SyncKind.DOCUMENTS))

        filters = [params.get("filter") for _, params in client.calls]
        assert "agentTag=маркетплейсы" in filters
        # Ровно два запроса на день: общий и по площадкам. Третий означал бы,
        # что расход лимита, общего с ботом, вырос незамеченным.
        assert len(client.calls) == 2 * len(set(p["momentFrom"] for _, p in client.calls))


class TestDaysToSync:
    """Какие дни перечитываются."""

    def test_empty_mirror_starts_from_the_first_shipment(self, make_demand):
        """Раньше первой отгрузки продаж не было — ходить туда незачем."""
        make_demand(moment=moscow(2026, 7, 15))

        days = days_to_sync()

        assert days[0] == date(2026, 7, 15)

    def test_nothing_to_sync_without_shipments(self):
        """Пустой учёт — пустой список, а не поход в API за всей историей."""
        assert days_to_sync() == []

    def test_recent_days_are_reread(self, make_profit_day):
        """Хвост перечитывается: отчёт комиссионера и пересчёт FIFO меняют прошлое.

        Без этого продажа, возникшая отчётом комиссионера за прошлую неделю,
        не появилась бы в марже никогда — а на боевых данных это 171 570 ₽.
        """
        make_profit_day(day=DAY)

        days = days_to_sync()

        assert days[0] == DAY - timedelta(days=RECENT_WINDOW_DAYS)

    def test_window_is_configurable_and_respected(self, make_profit_day):
        make_profit_day(day=DAY)

        assert days_to_sync(window=3)[0] == DAY - timedelta(days=3)


class TestSaving:
    """Что попадает в зеркало."""

    def test_totals_and_marketplace_part_land_in_one_row(
        self, product, make_demand
    ):
        """Площадки — подмножество строки, а не соседняя строка.

        Отдельной строкой они дали бы двойной счёт при сложении: выручка
        через Озон вошла бы и в общую сумму, и в свою собственную.
        """
        make_demand(moment=moscow(2026, 7, 15))
        day = "2026-07-15 00:00:00"
        client = RecordingClient({
            (day, ""): [report_row(product, quantity=10, revenue=54_936, cost=30_716)],
            (day, "agentTag=маркетплейсы"): [
                report_row(product, quantity=4, revenue=21_974, cost=12_286)
            ],
        })

        sync_profit(client, SyncRun.objects.create(kind=SyncKind.DOCUMENTS))

        row = ProfitDay.objects.get(date=date(2026, 7, 15), product=product)
        assert row.quantity == Decimal("10.000")
        assert row.revenue_kopecks == 54_936
        assert row.cost_kopecks == 30_716
        assert row.marketplace_quantity == Decimal("4.000")
        assert row.marketplace_revenue_kopecks == 21_974
        assert row.marketplace_cost_kopecks == 12_286
        # Подмножество, а не соседнее множество: сложение общего и площадок
        # не должно давать больше проданного.
        assert row.marketplace_quantity <= row.quantity

    def test_product_sold_only_through_marketplaces_keeps_its_totals(
        self, product, make_demand
    ):
        """Товар, ушедший только через площадку, попадает в общие числа тоже.

        Иначе строка была бы с нулевой выручкой и ненулевой маржой площадки —
        два числа об одном товаре, противоречащие друг другу.
        """
        make_demand(moment=moscow(2026, 7, 15))
        day = "2026-07-15 00:00:00"
        client = RecordingClient({
            (day, ""): [report_row(product, quantity=4, revenue=21_974, cost=12_286)],
            (day, "agentTag=маркетплейсы"): [
                report_row(product, quantity=4, revenue=21_974, cost=12_286)
            ],
        })

        sync_profit(client, SyncRun.objects.create(kind=SyncKind.DOCUMENTS))

        row = ProfitDay.objects.get(product=product)
        assert row.quantity == row.marketplace_quantity == Decimal("4.000")

    def test_disappeared_row_is_removed(self, product, make_demand, make_profit_day):
        """Продажа, исчезнувшая из отчёта, исчезает и из маржи.

        Отмена продажи или откат документа в учёте иначе жили бы в наших
        числах вечно: строка прошлого дня осталась бы нетронутой.
        """
        make_demand(moment=moscow(2026, 7, 15))
        stale = make_profit_day(day=date(2026, 7, 15), quantity="99")
        client = RecordingClient()

        sync_profit(client, SyncRun.objects.create(kind=SyncKind.DOCUMENTS))

        assert not ProfitDay.objects.filter(pk=stale.pk).exists()

    def test_unknown_assortment_is_counted_not_swallowed(self, product, make_demand):
        """Комплекты и модификации в зеркале не живут — но их пропуск считается.

        Молчаливая потеря строки означает выручку, выпавшую из маржи
        без единого признака (`CLAUDE.md` §9).
        """
        make_demand(moment=moscow(2026, 7, 15))
        day = "2026-07-15 00:00:00"
        unknown = {
            "assortment": {
                "meta": {
                    "href": "https://api.moysklad.ru/api/remap/1.2/entity/bundle/"
                    "ffffffff-0000-0000-0000-000000000001"
                }
            },
            "sellQuantity": 3,
            "sellSum": 1000,
            "sellCostSum": 400,
        }
        client = RecordingClient({(day, ""): [unknown]})

        outcome = sync_profit(client, SyncRun.objects.create(kind=SyncKind.DOCUMENTS))

        assert outcome.extra["skipped"] == 1
        assert ProfitDay.objects.count() == 0

    def test_fractional_cost_survives(self, product, make_demand):
        """Себестоимость приходит дробной — округлять её нельзя.

        Отчёт отдаёт суммы в копейках, и это уже целые копейки: округление
        идёт при разборе, один раз и в одном месте.
        """
        make_demand(moment=moscow(2026, 7, 15))
        day = "2026-07-15 00:00:00"
        client = RecordingClient({
            (day, ""): [report_row(product, quantity="12.5", revenue=54_936.4, cost=30_716.6)]
        })

        sync_profit(client, SyncRun.objects.create(kind=SyncKind.DOCUMENTS))

        row = ProfitDay.objects.get(product=product)
        assert row.quantity == Decimal("12.500")
        # round, а не усечение: суммы приходят типом Float.
        assert row.revenue_kopecks == 54_936
        assert row.cost_kopecks == 30_717


class TestCountersSurviveFailure:
    """Счётчики выставляются и на пути ошибки.

    Молчаливая потеря опаснее падения (`CLAUDE.md` §9): прогон, упавший
    на сотом дне, обязан сказать, что прошёл девяносто девять и сколько
    строк на них потерял. Без этого счётчик пропусков теряется ровно
    на том прогоне, ради которого он и заведён.
    """

    def test_extra_is_filled_when_the_run_breaks(self, product, make_demand):
        make_demand(moment=moscow(2026, 7, 15))

        class BreakingClient:
            def iterate(self, path, params=None):
                raise RuntimeError("сеть отвалилась")

        outcome = sync_profit(BreakingClient(), SyncRun.objects.create(kind=SyncKind.DOCUMENTS))

        assert outcome.error
        assert "days" in outcome.extra
        assert "skipped" in outcome.extra


class TestMarketplacesVanished:
    """Пустой ответ по группе — законный ответ, и потому опасный.

    Фильтр `agentTag` сравнивает название группы. Переименуй её в учёте —
    второй запрос дня начнёт возвращать ноль строк, все площадочные числа
    станут нулями, и ошибки не будет никакой.
    """

    def test_warns_when_mirror_knows_marketplaces_but_report_does_not(
        self, product, make_demand, make_agent, caplog
    ):
        ozon = make_agent("ООО «Интернет Решения»", tags=["маркетплейсы"])
        make_demand(moment=moscow(2026, 7, 15), agent=ozon)

        client = RecordingClient()
        with caplog.at_level("WARNING"):
            sync_profit(client, SyncRun.objects.create(kind=SyncKind.DOCUMENTS))

        assert "площадки есть" in caplog.text

    def test_stays_quiet_when_there_are_no_marketplaces_at_all(
        self, product, make_demand, caplog
    ):
        """Предупреждение без повода перестают читать — вместе со всеми."""
        make_demand(moment=moscow(2026, 7, 15))

        client = RecordingClient()
        with caplog.at_level("WARNING"):
            sync_profit(client, SyncRun.objects.create(kind=SyncKind.DOCUMENTS))

        assert "площадки есть" not in caplog.text
