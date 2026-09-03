"""Синхронизация прибыльности: отчёт `/report/profit/byproduct` по дням.

**Почему зеркалим чужой отчёт.** Марже нужна себестоимость **на момент
продажи**, а её в проекте взять неоткуда: `/report/stock/all` знает цену
только того, что лежит на складе сейчас. На боевых данных это 24 товара
из 59 проданных — остальные 35 остались бы без маржи вместе с третью
выручки. МойСклад считает FIFO по каждой продаже сам.

**Почему по дням.** Проверено запросами к боевому аккаунту: июль целиком
и сумма тридцати одного дневного запроса совпадают до копейки. Значит день —
неделимый кирпич, из которого собирается любой период, и страница остаётся
на Postgres (`CLAUDE.md` §1).

**Два запроса на день, а не один.** Второй — с фильтром по группе
контрагента: маржа по маркетплейсам завышена на весь процент площадки,
и отделить их обязательно. Признак живёт на контрагенте, и вывести его
из канала продаж нельзя — «Точка продаж» смешанная: 5 документов площадки
против 30 обычных.
"""

import logging
from datetime import date, timedelta

from django.db import transaction

from core.dates import local_date, today as local_today
from core.models import Counterparty, Document, DocumentKind, Product, ProfitDay
from core.models.counterparty import MARKETPLACE_TAG
from moysklad.client import MoySkladClient
from moysklad.limits import ApiDisabledRisk
from moysklad.parsing import parse_decimal, parse_kopecks
from moysklad.sync.references import ms_id_from
from moysklad.sync.runner import EntityOutcome, SyncRun

logger = logging.getLogger(__name__)

REPORT_PATH = "/report/profit/byproduct"

# Сколько последних дней перечитывать каждый прогон.
#
# Прошлый день меняется по двум причинам, и обе настоящие. Первая — отчёт
# комиссионера: он превращает давнюю отгрузку в продажу, но датой самого
# отчёта, то есть недавней. Вторая — пересчёт FIFO в МойСкладе после правки
# приёмки: он тихо меняет себестоимость уже посчитанных продаж.
#
# Две недели — с запасом от наблюдаемой жизни: отчёты комиссионера приходят
# раз в одну-две недели (12 отчётов за пять месяцев). Больше окно — больше
# запросов из общей с ботом корзины каждую ночь, меньше — правка приёмки
# недельной давности осталась бы незамеченной.
RECENT_WINDOW_DAYS = 14

# Потолок на один прогон. Первый проход идёт от первой отгрузки — это 155 дней
# и 310 запросов, минуты три вежливого клиента. Потолок нужен не для него,
# а против дня, когда `earliest` вернёт 2019 год из-за одного документа
# с опечаткой в дате: тогда прогон съел бы корзину лимита вместе с ботом.
MAX_DAYS_PER_RUN = 400


def _bounds(day: date) -> dict:
    """Границы суток для отчёта: с начала дня до начала следующего.

    Верхняя граница строгая и берётся началом следующего дня, а не концом
    текущего, — по той же причине, что в `api/common/selection.py`: продажа
    в 23:59:59.5 иначе выпала бы, не оставив следа.

    Дни местные, а не UTC (`core/dates.py`): МойСклад понимает время
    в московском поясе, и день у него тот же, что у человека.
    """
    return {
        "momentFrom": f"{day} 00:00:00",
        "momentTo": f"{day + timedelta(days=1)} 00:00:00",
    }


def days_to_sync(*, window: int = RECENT_WINDOW_DAYS) -> list[date]:
    """Какие дни перечитать в этом прогоне.

    Отсчёт от последнего дня, за который уже есть продажи, минус окно.
    Отдельной отметки «день опрошен» нет намеренно: день без продаж строк
    не создаёт, и такая отметка была бы вторым источником правды о том же.
    Плата за это — перечитывание хвоста из дней без продаж, и она невелика:
    хвост длиной в неделю стоит семи лишних пар запросов.

    Пустое зеркало — считаем от первой отгрузки: раньше неё продаж не было.
    """
    end = local_today()

    last_sale = ProfitDay.objects.order_by("-date").values_list("date", flat=True).first()
    if last_sale is not None:
        start = last_sale - timedelta(days=window)
    else:
        first = (
            Document.objects.filter(
                kind=DocumentKind.DEMAND, deleted_at__isnull=True, applicable=True
            )
            .order_by("moment")
            .values_list("moment", flat=True)
            .first()
        )
        if first is None:
            # Отгрузок нет вовсе — считать нечего, и ходить в API незачем.
            return []

        start = local_date(first)

    if start > end:
        return []

    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    if len(days) > MAX_DAYS_PER_RUN:
        logger.warning(
            "Прибыльность: к обходу набралось %s дней при потолке %s — берём "
            "последние. Проверьте дату самой ранней отгрузки.",
            len(days), MAX_DAYS_PER_RUN,
        )
        days = days[-MAX_DAYS_PER_RUN:]
    return days


def _fetch_day(client: MoySkladClient, day: date, *, marketplaces: bool) -> dict:
    """Строки отчёта за день, разложенные по идентификатору номенклатуры."""
    params = _bounds(day)
    if marketplaces:
        # Группа контрагента, а не канал продаж: признак площадки живёт
        # на контрагенте. Название группы берётся из того же места, что
        # и признак в модели, — второй копией строки они бы разошлись.
        params["filter"] = f"agentTag={MARKETPLACE_TAG}"

    rows = {}
    for row in client.iterate(REPORT_PATH, params):
        ms_id = ms_id_from(row.get("assortment"))
        if ms_id:
            rows[ms_id] = row
    return rows


def _numbers(row: dict | None, prefix: str) -> dict:
    """Три числа строки отчёта: сколько, почём, по какой себестоимости."""
    if row is None:
        return {f"{prefix}quantity": 0, f"{prefix}revenue_kopecks": 0,
                f"{prefix}cost_kopecks": 0}
    return {
        f"{prefix}quantity": parse_decimal(row.get("sellQuantity")) or 0,
        # Отчёт отдаёт суммы уже в копейках — делить не на что.
        f"{prefix}revenue_kopecks": parse_kopecks(row.get("sellSum")),
        f"{prefix}cost_kopecks": parse_kopecks(row.get("sellCostSum")),
    }


@transaction.atomic
def _save_day(day: date, total: dict, marketplace: dict, products: dict) -> tuple[int, int, int]:
    """Переписать день целиком. Возвращает (создано, обновлено, пропущено).

    Замена, а не сверка: строк за день десяток, а пересчёт FIFO в МойСкладе
    меняет их молча. Удаление старых строк дня обязательно — иначе товар,
    исчезнувший из отчёта после отмены продажи, остался бы в марже навсегда.
    """
    created = updated = skipped = 0
    seen = []

    for ms_id in total.keys() | marketplace.keys():
        product = products.get(ms_id)
        if product is None:
            # Отчёт отдаёт и то, чего нет в зеркале: комплекты, модификации.
            # Пропускаем, но считаем: молча потерянная строка — это выручка,
            # выпавшая из маржи без единого признака.
            skipped += 1
            continue

        fields = _numbers(total.get(ms_id), "")
        fields.update(_numbers(marketplace.get(ms_id), "marketplace_"))
        _, is_new = ProfitDay.objects.update_or_create(
            date=day, product=product, defaults=fields
        )
        created += is_new
        updated += not is_new
        seen.append(product.pk)

    ProfitDay.objects.filter(date=day).exclude(product_id__in=seen).delete()
    return created, updated, skipped


def sync_profit(client: MoySkladClient, run: SyncRun) -> EntityOutcome:
    """Прибыльность по дням: продано, выручка, себестоимость на момент продажи."""
    outcome = EntityOutcome()
    products = {str(p.ms_id): p for p in Product.objects.all()}
    days = days_to_sync()
    skipped = 0
    done = 0
    marketplace_rows = 0

    try:
        for day in days:
            total = _fetch_day(client, day, marketplaces=False)
            marketplace = _fetch_day(client, day, marketplaces=True)
            outcome.fetched += len(total)
            marketplace_rows += len(marketplace)

            created, updated, day_skipped = _save_day(day, total, marketplace, products)
            outcome.created += created
            outcome.updated += updated
            skipped += day_skipped
            done += 1

    except ApiDisabledRisk:
        raise
    except Exception as error:
        outcome.error = f"{type(error).__name__}: {error}"
    finally:
        # Счётчики выставляются и на пути ошибки: молчаливая потеря опаснее
        # падения, а прогон, упавший на сотом дне, обязан сказать, что успел
        # пройти девяносто девять и сколько строк на них потерял.
        outcome.extra = {
            "days": done,
            "planned_days": len(days),
            "skipped": skipped,
            "marketplace_rows": marketplace_rows,
        }

    if skipped:
        logger.warning(
            "Прибыльность: %s строк отчёта не найдены в зеркале — их выручка "
            "не попадёт в маржу", skipped,
        )
    _warn_if_marketplaces_vanished(marketplace_rows, done)
    return outcome


def _warn_if_marketplaces_vanished(rows: int, days: int) -> None:
    """Площадки известны зеркалу, а отчёт по ним пуст — это подозрительно.

    Фильтр `agentTag` сравнивает **название группы**, и оно приходит
    из константы. Переименуй кто-нибудь группу в учёте или заведи её
    с заглавной — второй запрос дня начнёт возвращать ноль строк, и все
    площадочные колонки зеркала станут нулями. Ошибки при этом нет:
    пустой ответ — законный ответ, и без этой проверки потеря была бы
    полностью молчаливой.

    Сверяется с зеркалом, а не с самим собой: контрагенты-площадки в нём
    уже есть, и если они есть, а строк нет — расходятся два признака,
    которые обязаны совпадать.
    """
    if rows or not days:
        return
    known = any(agent.is_marketplace for agent in Counterparty.objects.only("id", "tags"))
    if known:
        logger.warning(
            "Прибыльность: за %s дней отчёт по группе «%s» не вернул ни одной "
            "строки, хотя в зеркале площадки есть. Проверьте название группы "
            "в учёте — все площадочные числа станут нулями.",
            days, MARKETPLACE_TAG,
        )
