"""Остатки в разрезе складов — знаменатель для «сколько склада пересчитано».

Отдельно от `sync_stock`, хотя оба про остаток, и **в ночном прогоне,
а не в пятнадцатиминутном**. Причина в цене: отчёт весит из общей с ботом
корзины, а вопрос, ради которого он берётся, — «что на складе ещё
не пересчитали» — не меняется за четверть часа. Свежесть страница показывает
честно, отдельной отметкой.

Склад приходит именем прямо в строке отчёта, поэтому справочника складов
у нас нет: заводить сущность ради одного поля, которое и так приезжает, —
лишняя синхронизация, которая начнёт расходиться с этим именем.
"""

import logging

from django.db import transaction

from core.models import Product, StoreStock
from moysklad.client import MoySkladClient
from moysklad.limits import ApiDisabledRisk
from moysklad.parsing import parse_decimal
from moysklad.sync.references import ms_id_from
from moysklad.sync.runner import EntityOutcome, SyncRun

logger = logging.getLogger(__name__)

# Какую долю известных пар «товар × склад» отчёт должен вернуть, чтобы
# заменять таблицу целиком. Тот же порог и та же причина, что у `sync_stock`:
# документация предупреждает, что в отчёт попадают только товары с уже
# пересчитанными остатками, а пересчёт не мгновенный.
MIN_REPORT_COMPLETENESS = 0.8


def sync_store_stock(client: MoySkladClient, run: SyncRun) -> EntityOutcome:
    """Что и сколько лежит на каждом складе.

    Умолчание отчёта — `nonEmpty`, и оно здесь верное: позиция с нулём
    на складе там не лежит, и включать её в знаменатель «сколько склада
    пересчитано» значило бы требовать пересчёта того, чего нет.
    """
    outcome = EntityOutcome()
    products = {str(p.ms_id): p for p in Product.objects.all()}
    skipped = 0
    rows: list[StoreStock] = []
    stores: set[str] = set()

    try:
        for row in client.iterate("/report/stock/bystore"):
            outcome.fetched += 1

            product = products.get(ms_id_from(row))
            if product is None:
                # Отчёт отдаёт и то, чего нет в зеркале: модификации,
                # комплекты. Пропускаем, но считаем: потерянная строка
                # занижает знаменатель, и склад покажется пересчитанным
                # лучше, чем он есть.
                skipped += 1
                continue

            for entry in row.get("stockByStore") or []:
                name = entry.get("name") or ""
                quantity = parse_decimal(entry.get("stock")) or 0
                if not name or not quantity:
                    # Ноль на складе — не «лежит здесь». Строка без имени
                    # склада в отчёте означает резервы, не привязанные
                    # к складу (так написано в документации).
                    continue
                stores.add(name)
                rows.append(
                    StoreStock(
                        product=product,
                        store_name=name,
                        quantity=quantity,
                        reserved=parse_decimal(entry.get("reserve")) or 0,
                    )
                )

    except ApiDisabledRisk:
        raise
    except Exception as error:
        outcome.error = f"{type(error).__name__}: {error}"
        return outcome

    # Короткий, но успешный отчёт не заменяет таблицу.
    #
    # МойСклад отдаёт только товары с уже пересчитанными остатками, и
    # пересчёт не мгновенный: прогон, поймавший его середину, вернёт треть
    # строк без единой ошибки. Заменив таблицу этой третью, страница
    # показала бы склад пересчитанным почти полностью, а «не проверено» —
    # почти нулём. Ошибка, выглядящая хорошей новостью, и по расписанию.
    #
    # Порог считается по парам «товар × склад», а не по строкам отчёта:
    # в отчёт попадают модификации и комплекты, которых в зеркале нет, и
    # они раздували бы счётчик.
    known = StoreStock.objects.count()
    complete_enough = bool(rows) and (
        known == 0 or len(rows) >= known * MIN_REPORT_COMPLETENESS
    )
    if not complete_enough and known:
        logger.warning(
            "Остатки по складам: отчёт вернул %s пар против %s в базе — "
            "похоже на пересчёт в МойСкладе. Замена пропущена, прежние "
            "остатки сохранены до следующего прогона.",
            len(rows), known,
        )
        outcome.extra = {
            "skipped": skipped, "stores": len(stores), "partial": True
        }
        return outcome

    # Замена целиком, а не upsert: позиция, увезённая с одного склада
    # на другой, обязана исчезнуть с первого, а построчная сверка стоила бы
    # запроса на каждую пару «товар × склад».
    #
    # Одной транзакцией: без неё сбой между удалением и вставкой оставляет
    # таблицу пустой — та же ошибка, что выше, только от падения.
    with transaction.atomic():
        StoreStock.objects.all().delete()
        StoreStock.objects.bulk_create(rows)

    outcome.created = len(rows)
    outcome.extra = {"skipped": skipped, "stores": len(stores), "partial": False}
    if skipped:
        logger.warning(
            "Остатки по складам: пропущено %s строк — знаменатель «сколько "
            "склада пересчитано» занижен, склад покажется чище, чем он есть",
            skipped,
        )
    return outcome
