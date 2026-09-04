"""Запуск синхронизации по кнопке.

Правило «никаких живых запросов в МойСклад из HTTP-запроса пользователя»
знает одно исключение — кнопку «Обновить», и она обвешана ограничениями:
корзина лимита общая с ботом Agent - StarPony, который проверяет учёт
круглосуточно. Выберем её до дна — бот перестанет работать.

Ограничений три, и каждое закрывает свой способ навредить:
блокировка не даёт двум прогонам идти разом, пауза не даёт долбить кнопку,
а предохранитель внутри клиента останавливает прогон при череде отказов.
"""

from datetime import timedelta

from django.utils import timezone

from core.models import SyncEntityResult, SyncKind, SyncRun, SyncStatus
from moysklad.sync.full import ENTITIES, AlreadyRunning, TokenMissing, run_documents_sync

# Сколько ждать между запусками руками. Три минуты — не про нагрузку на нас,
# а про общий с ботом лимит: ночной проход тратит около двухсот запросов,
# и десять нажатий подряд съели бы корзину, из которой бот работает.
COOLDOWN = timedelta(minutes=3)

# После какого возраста прогон со статусом «идёт» считается брошенным.
# Такой остаётся, если процесс умер, не закрыв запись: воркер убит по таймауту,
# контейнер перезапущен, машина перезагружена. Без срока годности одна такая
# запись выключает кнопку навсегда — до следующего ночного прогона.
# Живой проход занимает секунды; четверть часа — заведомо больше любого.
STALE_AFTER = timedelta(minutes=15)


# Как называется сущность на экране. Ключи — из `ENTITIES`, и второго списка
# здесь нет: порядок и состав задаёт синхронизация, тут только подписи.
# Забыть подпись у новой сущности не даёт `test_every_entity_has_a_label`.
STAGE_LABELS = {
    "uom": "единицы измерения",
    "product": "товары",
    "processingplan": "техкарты",
    "counterparty": "контрагенты",
    "contract": "договоры",
    "saleschannel": "каналы продаж",
    "customerorder": "заказы покупателей",
    "demand": "отгрузки",
    "purchaseorder": "заказы поставщикам",
    "supply": "приёмки",
    "commissionreportin": "отчёты комиссионеров",
    "profit": "прибыльность",
}


class Refused(Exception):
    """Запуск отклонён. Причина — человеку, а не в лог.

    Обычный класс, а не замороженный dataclass: тот запрещает присваивание
    полей, а Python при возбуждении пишет в `__traceback__` самого исключения
    и падает на этом, подменяя настоящую причину.
    """

    def __init__(self, reason: str, retry_after_seconds: int = 0):
        super().__init__(reason)
        self.reason = reason
        self.retry_after_seconds = retry_after_seconds


def last_run() -> SyncRun | None:
    return SyncRun.objects.filter(kind=SyncKind.DOCUMENTS).order_by("-started_at").first()


def _human(seconds: int) -> str:
    """Остаток паузы словами: «2 мин 13 с» вместо «133 с».

    Сто тридцать три секунды человек всё равно переводит в минуты сам —
    и делает это медленнее, чем прочитал бы готовый ответ.
    """
    if seconds < 60:
        return f"{seconds} с"
    minutes, rest = divmod(seconds, 60)
    return f"{minutes} мин" if rest == 0 else f"{minutes} мин {rest} с"


def _abandon(run: SyncRun) -> None:
    """Пометить прогон брошенным: процесс умер, не закрыв запись."""
    run.status = SyncStatus.FAILED
    run.finished_at = timezone.now()
    run.error = "Прогон оборван: процесс завершился, не закрыв запись."
    run.save(update_fields=["status", "finished_at", "error"])


def status() -> dict:
    """Идёт ли синхронизация прямо сейчас и когда данные обновлялись.

    Спрашивается страницей: состояние «идёт» должно жить на сервере, а не
    в памяти вкладки. Иначе перезагрузка стирает его у того, кто запустил,
    а остальные четверо не видят вовсе — и жмут кнопку впустую.
    """
    previous = last_run()
    running = (
        previous is not None
        and previous.status == SyncStatus.RUNNING
        and timezone.now() - previous.started_at < STALE_AFTER
    )
    if not running:
        return {"running": False, "started_at": None, "done": 0, "total": 0, "stage": ""}

    # Сколько сущностей уже закрыто. Строка итога пишется по завершении
    # каждой, поэтому счётчик настоящий, а не выдуманная доля времени:
    # человеку нужен ответ на «идёт или зависло», и его даёт только число,
    # которое меняется.
    done = SyncEntityResult.objects.filter(run=previous).count()
    order = [name for name, _ in ENTITIES]
    stage = STAGE_LABELS.get(order[done], "") if done < len(order) else "заканчиваем"

    return {
        "running": True,
        "started_at": previous.started_at,
        "done": done,
        "total": len(order),
        "stage": stage,
    }


def refresh() -> SyncRun:
    """Запустить полный проход, если можно."""
    previous = last_run()
    if previous is not None:
        # Идущий прогон виден по статусу: блокировка живёт в другом
        # соединении, и спросить её отсюда нельзя.
        waited = timezone.now() - previous.started_at

        if previous.status == SyncStatus.RUNNING and waited < STALE_AFTER:
            raise Refused("Синхронизация уже идёт — подождите, она вот-вот закончится.")

        if previous.status == SyncStatus.RUNNING:
            # Брошенная запись. Закрываем её честно — иначе журнал будет
            # утверждать, что прогон идёт до сих пор, и следующий отказ
            # опять сошлётся на неё.
            _abandon(previous)
            return run_documents_sync(manual=True)
        if waited < COOLDOWN:
            # Минимум секунда: при остатке в доли секунды округление вниз
            # дало бы ноль, а по нему view отличает «слишком часто» от
            # «сейчас нельзя по другой причине» — и отказ уехал бы не тем кодом.
            left = max(1, int((COOLDOWN - waited).total_seconds()))
            raise Refused(
                f"Данные обновлялись меньше трёх минут назад. "
                f"Следующее обновление — через {_human(left)}.",
                retry_after_seconds=left,
            )

    try:
        return run_documents_sync(manual=True)
    except TokenMissing:
        raise Refused("Доступ к МойСкладу не настроен: не задан токен.")
    except AlreadyRunning:
        raise Refused("Синхронизация уже идёт — подождите, она вот-вот закончится.")
