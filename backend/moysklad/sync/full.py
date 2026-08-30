"""Полный проход по справочникам и документам.

Живёт здесь, а не в management-команде: тот же проход запускает кнопка
«Обновить» на странице, и вторая копия порядка сущностей рано или поздно
разошлась бы с первой — а порядок тут не украшение, документы ссылаются
на справочники.
"""

import logging
import os

from core.models import SyncKind, SyncRun
from moysklad.client import MoySkladClient
from moysklad.limits import ApiDisabledRisk
from moysklad.sync.catalog import sync_products, sync_uoms
from moysklad.sync.documents import (
    sync_demands,
    sync_purchase_orders,
    sync_supplies,
)
from moysklad.sync.lock import advisory_lock
from moysklad.sync.production import sync_processing_plans
from moysklad.sync.references import sync_counterparties, sync_sales_channels
from moysklad.sync.runner import SyncSession

logger = logging.getLogger(__name__)

LOCK_NAME = "sync:documents"

# Порядок обязателен, а не для красоты: документы ссылаются на товары,
# контрагентов и каналы, а товары — на единицы измерения. Справочники
# идут первыми, иначе документ не на что будет повесить.
#
# Заказы поставщикам — перед приёмками по той же причине: приёмка ссылается
# на заказ, и в обратном порядке связь не установилась бы ни у одной из них.
ENTITIES = (
    ("uom", sync_uoms),
    ("product", sync_products),
    ("processingplan", sync_processing_plans),
    ("counterparty", sync_counterparties),
    ("saleschannel", sync_sales_channels),
    ("demand", sync_demands),
    ("purchaseorder", sync_purchase_orders),
    ("supply", sync_supplies),
)


class TokenMissing(RuntimeError):
    """Без токена ходить некуда. Отдельный тип — чтобы отличить от сбоя сети."""


class AlreadyRunning(RuntimeError):
    """Прогон уже идёт. Второй разом — двойной расход общего с ботом лимита."""


def run_documents_sync(*, manual: bool = False) -> SyncRun:
    """Пройти справочники и документы. Возвращает запись журнала.

    Блокировка не ждёт очереди намеренно: очередь из синхронизаций хуже
    пропущенного запуска — следующий всё равно случится по расписанию.
    """
    token = os.getenv("MOYSKLAD_TOKEN")
    if not token:
        raise TokenMissing("MOYSKLAD_TOKEN не задан")

    with advisory_lock(LOCK_NAME) as acquired:
        if not acquired:
            raise AlreadyRunning("Синхронизация уже идёт")

        client = MoySkladClient(token=token)
        session = SyncSession(SyncKind.DOCUMENTS, manual=manual)
        stopped = ""

        for name, sync in ENTITIES:
            try:
                session.record(name, sync(client, session.run))
            except ApiDisabledRisk as risk:
                # Предохранитель сработал: продолжать нельзя, иначе
                # МойСклад отключит доступ всей компании, включая бота.
                stopped = str(risk)
                logger.error("Прогон остановлен предохранителем: %s", stopped)
                break

        return session.finish(request_count=client.request_count, error=stopped)
