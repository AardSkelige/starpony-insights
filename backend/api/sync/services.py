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

from core.models import SyncKind, SyncRun, SyncStatus
from moysklad.sync.full import AlreadyRunning, TokenMissing, run_documents_sync

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


def _abandon(run: SyncRun) -> None:
    """Пометить прогон брошенным: процесс умер, не закрыв запись."""
    run.status = SyncStatus.FAILED
    run.finished_at = timezone.now()
    run.error = "Прогон оборван: процесс завершился, не закрыв запись."
    run.save(update_fields=["status", "finished_at", "error"])


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
                f"Следующее обновление — через {left} с.",
                retry_after_seconds=left,
            )

    try:
        return run_documents_sync(manual=True)
    except TokenMissing:
        raise Refused("Доступ к МойСкладу не настроен: не задан токен.")
    except AlreadyRunning:
        raise Refused("Синхронизация уже идёт — подождите, она вот-вот закончится.")
