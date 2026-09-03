"""Ход обратной записи: выключатель, журнал, потолок изменений за прогон.

Общее для всех видов записи. Сам вид знает только «что и на что менять» —
как это записать в журнал и когда остановиться, решает эта сессия.

Потолок обязателен и не совпадает с предохранителем клиента. Тот стережёт
**ошибки** — серию 429 или 4xx подряд. Этот стережёт **успех**: прогон,
который решил переписать все 380 товаров разом, ошибок не даёт вовсе,
но это ровно та серия PUT, за которую МойСклад отключает доступ (100 PUT
к одной сущности в минуту). Причина остановки при этом всегда одна и та же —
что-то посчиталось не так, и лучше выяснить это на тридцати записях,
чем на всех.
"""

import logging

from django.db import models
from django.utils import timezone

from core.models import (
    WritebackChange,
    WritebackKind,
    WritebackRun,
    WritebackStatus,
    WritebackSwitch,
)

logger = logging.getLogger(__name__)

# Сколько записей за один прогон считаем нормой. Взято с запасом от жизни:
# за 22 дня наблюдений самый крупный прогон себестоимости поменял 16 товаров
# из 315, обычный — от двух до двенадцати. Тридцать — это вдвое больше
# худшего наблюдавшегося случая и втрое меньше того, что вызывает подозрение.
DEFAULT_CHANGE_LIMIT = 30


class SkipReason(models.TextChoices):
    """Почему запись пропущена. Обязательна у каждого пропуска.

    Без обязательности следующий вид записи её забудет, и «пропущено N»
    снова станет числом, по которому нельзя отличить «нечего менять»
    от «не работает». Именно так и вышло у себестоимости.
    """

    # Записывать нечего: исходного числа нет. У себестоимости это позиции
    # без остатка — FIFO неизвестен, и таких постоянно около сотни из 315.
    UNKNOWN = "unknown", "значение неизвестно"
    # В учёте уже стоит то же самое. Нормальное состояние между движениями.
    EQUAL = "equal", "уже совпадает"


class WritebackDisabled(RuntimeError):
    """Выключатель выключен. Не ошибка — решение человека."""


class ChangeLimitReached(RuntimeError):
    """Изменений оказалось больше, чем бывает при нормальной работе."""


class WritebackSession:
    """Прогон записи целиком: открывает журнал, пишет строки, закрывает статусом."""

    def __init__(
        self,
        kind: WritebackKind,
        *,
        dry_run: bool = False,
        manual: bool = False,
        change_limit: int = DEFAULT_CHANGE_LIMIT,
    ):
        self.kind = kind
        self.dry_run = dry_run
        self._limit = change_limit

        self.run = WritebackRun.objects.create(
            kind=kind, dry_run=dry_run, triggered_manually=manual
        )

    def ensure_enabled(self) -> None:
        """Проверить выключатель. Выключен — закрыть прогон и подняться выше.

        Прогон всё равно заводится и закрывается статусом «отменён»: иначе
        выключенная запись выглядела бы в журнале как незапускавшаяся,
        и вопрос «почему себестоимость не обновляется» пришлось бы выяснять
        по конфигурации, а не по журналу.
        """
        if WritebackSwitch.is_enabled(self.kind):
            return
        self._close(WritebackStatus.BLOCKED, error="Выключатель выключен")
        raise WritebackDisabled(
            f"«{WritebackKind(self.kind).label}» выключена в админке. "
            f"Включить: раздел «Выключатели обратной записи»."
        )

    def note_considered(self, count: int = 1) -> None:
        self.run.considered += count

    def note_skipped(self, reason: SkipReason, count: int = 1) -> None:
        """Пропустить позицию, назвав причину.

        Причина — обязательный довод, а не удобство: см. `SkipReason`.
        """
        self.run.skipped += count
        if reason == SkipReason.UNKNOWN:
            self.run.skipped_unknown += count
        else:
            self.run.skipped_equal += count

    def record(
        self,
        *,
        ms_id,
        name: str,
        field: str,
        old_value=None,
        new_value=None,
        error: str = "",
    ) -> None:
        """Записать одно изменение. Строка уходит в базу немедленно.

        Немедленно, а не пачкой в конце: к моменту вызова учёт **уже изменён**,
        и запись, о которой не осталось следа, — это ровно то, что §6 запрещает.
        Копить их в памяти небезопасно: крон запускает команду под `timeout`,
        а `timeout` шлёт SIGTERM, на котором Python завершает процесс
        без исключения — ни `finally`, ни `except` не отработают.

        Дорого это не выходит. В журнал идут только изменения и ошибки,
        а не все сравнения: за 22 дня наблюдений самый крупный прогон
        себестоимости дал 16 строк.
        """
        WritebackChange.objects.create(
            run=self.run,
            target_ms_id=ms_id,
            target_name=name[:255],
            field=field,
            old_value=old_value,
            new_value=new_value,
            error=error[:2000],
        )

        if error:
            self.run.failed += 1
            logger.error("Запись не прошла: %s — %s", name, error)
            return

        self.run.changed += 1
        if not self.dry_run and self.run.changed > self._limit:
            raise ChangeLimitReached(
                f"Изменений больше {self._limit} за прогон. Остановились: "
                f"столько сразу не меняется при нормальной работе, и похоже "
                f"на ошибку в расчёте. Проверьте прогоном с --dry-run."
            )

    def finish(
        self,
        *,
        request_count: int = 0,
        error: str = "",
        stopped: bool = False,
    ) -> WritebackRun:
        if error and stopped:
            status = WritebackStatus.STOPPED
        elif error:
            status = WritebackStatus.FAILED
        elif self.run.failed and self.run.changed:
            # Частичный отказ — отдельный статус, а не «успех с оговоркой»:
            # именно он скрывает поломку, если его не различать.
            status = WritebackStatus.PARTIAL
        elif self.run.failed:
            status = WritebackStatus.FAILED
        else:
            status = WritebackStatus.SUCCESS

        return self._close(status, request_count=request_count, error=error)

    def _close(
        self, status: WritebackStatus, *, request_count: int = 0, error: str = ""
    ) -> WritebackRun:
        self.run.status = status
        self.run.finished_at = timezone.now()
        self.run.request_count = request_count
        self.run.error = error[:2000]
        self.run.save(
            update_fields=[
                "status", "finished_at", "request_count", "error",
                "considered", "changed", "skipped", "failed",
                "skipped_unknown", "skipped_equal",
            ]
        )
        return self.run
