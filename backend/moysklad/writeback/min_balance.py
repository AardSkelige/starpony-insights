"""Неснижаемый остаток в карточку товара: сколько держать на складе.

**Считаем мы, хранит МойСклад.** Поле `minimumBalance` в карточке товара есть,
но заполнять его учёт не умеет — там нет темпа продаж. У нас он есть, и число
нужно самому учёту: по нему МойСклад подсвечивает позиции в интерфейсе,
не открывая нашу страницу.

**Пишем только товарам, у сырья не трогаем.** Правило безопасности из решения
03.09: демон пишет тем, у кого есть артикул, а сырьё артикула не имеет —
там неснижаемый остаток проставляет человек, и затирать его расчётом нельзя.
Тот же предикат, что у всей главной, — `catalogue.goods()`.

**Страховой запас, а не «сколько варить».** Число отвечает на «ниже какого
остатка нельзя опускаться», и берётся оно от темпа продаж: две недели —
столько идёт поставка сырья у большинства поставщиков плюс сама варка.
Опустился ниже — пора ставить партию, и это ровно тот порог, на который
у «Расчёта производства» настроен `CRITICAL_DAYS`.

**Первый прогон упрётся в потолок изменений, и это правильно.** Поле пусто
почти у всех: `--dry-run` на боевых 04.09 показал 43 записи при потолке 30.
Потолок стережёт не ошибку, а успех — прогон, решивший переписать полкаталога
разом, ошибок не даёт вовсе, но это ровно та серия PUT, за которую МойСклад
отключает доступ всей компании (`CLAUDE.md` §6).

Поэтому поле заполнится за два прогона: первый запишет тридцать и остановится
статусом «остановлен предохранителем», второй — остальные тринадцать
и дальше будет пропускать их как «уже совпадает». Это не сбой, и вмешиваться
не нужно; в журнале обе строки видны.
"""

import logging
import math
from datetime import timedelta

from api.common.selection import within
from core.dates import today as local_today
from core.models import DocumentKind, WritebackKind
from core.services import catalogue, coverage
from core.services.documents import alive, positions_in
from moysklad.client import MoySkladClient
from moysklad.limits import ApiDisabledRisk
from moysklad.writeback.journal import (
    ChangeLimitReached,
    SkipReason,
    WritebackRun,
    WritebackSession,
)

logger = logging.getLogger(__name__)

FIELD = "Неснижаемый остаток"

# Окно спроса. То же, что у сигналов главной: 60 дней — иначе не отличить
# «кончилось» от «не продавалось». Одно окно на обе стороны, чтобы порог
# в карточке и число на экране не разошлись.
DEMAND_DAYS = 60

# На сколько дней запаса рассчитан порог. Две недели — срок поставки сырья
# у большинства поставщиков плюс варка; тот же порог, по которому «Расчёт
# производства» красит строку (`coverage.CRITICAL_DAYS`).
SAFETY_DAYS = coverage.CRITICAL_DAYS


def targets() -> dict[str, int]:
    """Сколько держать по каждому товару: {ms_id: штук}.

    Считается из того же зеркала, что и страницы, — в МойСклад за этим
    не ходим (`CLAUDE.md` §1).

    Товар без продаж за окно в ответ не попадает: темпа нет, порог считать
    не из чего. Ноль сюда не годится — он значит «держать нечего», а мы
    просто не знаем.
    """
    day = local_today()
    shipped = within(
        positions_in(alive(DocumentKind.DEMAND)),
        day - timedelta(days=DEMAND_DAYS - 1),
        day,
    )

    goods = list(catalogue.goods())
    left = coverage.by_product(goods, shipped, DEMAND_DAYS)

    result: dict[str, int] = {}
    for product in goods:
        per_day = left[product.pk].per_day
        if per_day <= 0:
            continue
        # Вверх: порог в 4,2 штуки — это 5. Округлив вниз, мы обещали бы,
        # что четырёх хватает, хотя расчёт говорит обратное.
        result[str(product.ms_id)] = math.ceil(per_day * SAFETY_DAYS)
    return result


def run_min_balance_writeback(
    client: MoySkladClient,
    *,
    dry_run: bool = False,
    manual: bool = False,
) -> WritebackRun:
    """Проставить неснижаемый остаток в карточки. Возвращает запись журнала."""
    session = WritebackSession(
        WritebackKind.MIN_BALANCE, dry_run=dry_run, manual=manual
    )
    session.ensure_enabled()

    error, stopped = "", False
    try:
        try:
            _walk_products(session, client, targets())
        except (ApiDisabledRisk, ChangeLimitReached) as risk:
            error, stopped = str(risk), True
            logger.error("Запись неснижаемого остатка остановлена: %s", error)
        except Exception as failure:  # noqa: BLE001 — журнал важнее типа ошибки
            error = f"{type(failure).__name__}: {failure}"
            logger.exception("Запись неснижаемого остатка не удалась")
    finally:
        # `finally` по той же причине, что у себестоимости: на SIGTERM
        # от `timeout` в кроне записи, уже ушедшие в учёт, остались бы
        # без журнальной строки, а прогон — навсегда «идущим».
        run = session.finish(
            request_count=client.request_count, error=error, stopped=stopped
        )

    return run


def _walk_products(
    session: WritebackSession, client: MoySkladClient, wanted: dict[str, int]
) -> None:
    """Обойти действующие товары и записать разошедшиеся.

    Архивные исключены фильтром запроса: PUT в архивный товар — это запись
    в общую с ботом корзину ради числа, которого никто не увидит. Фильтр
    стоит явно, хотя API и так отдаёт по умолчанию действующие: умолчание
    чужого сервиса сменится молча, а заметить это будет нечем.
    """
    for row in client.iterate("/entity/product", {"filter": "archived=false"}):
        ms_id = row.get("id")
        session.note_considered()

        target = wanted.get(ms_id)
        if target is None:
            # Сырьё, услуги и товары без продаж за окно. Не ошибка: сырью
            # порог ставит человек, а без темпа его неоткуда взять.
            session.note_skipped(SkipReason.UNKNOWN)
            continue

        # Учёт отдаёт `minimumBalance` типом Float; отсутствие поля и ноль
        # различать не нужно — ноль означает «порог не задан», и записать
        # туда расчётный можно.
        current = row.get("minimumBalance")
        if current is not None and int(current) == target:
            session.note_skipped(SkipReason.EQUAL)
            continue

        name = row.get("name", "—")
        old_value = int(current) if current is not None else None

        if session.dry_run:
            session.record(
                ms_id=ms_id, name=name, field=FIELD,
                old_value=old_value, new_value=target,
            )
            continue

        try:
            client.put(f"/entity/product/{ms_id}", {"minimumBalance": target})
        except ApiDisabledRisk:
            raise
        except Exception as failure:  # noqa: BLE001
            session.record(
                ms_id=ms_id, name=name, field=FIELD,
                old_value=old_value, new_value=target,
                error=f"{type(failure).__name__}: {failure}",
            )
            continue

        session.record(
            ms_id=ms_id, name=name, field=FIELD,
            old_value=old_value, new_value=target,
        )
