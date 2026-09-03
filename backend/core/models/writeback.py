"""Журнал обратной записи в учёт и выключатель к ней.

Обратная запись — единственное место, где мы меняем чужие данные. Ошибка здесь
не «показали не то число», а «испортили учёт компании», и откатить её можно
только руками. Поэтому три вещи обязательны (`CLAUDE.md` §6):

- **журнал** — что, когда, с чего на что; без него не ответить на вопрос
  «кто поменял цену у этого товара», а спросят его обязательно;
- **выключатель** — правится в админке, без деплоя: когда что-то пошло не так,
  выкатывать релиз некогда;
- **пробный прогон** — у каждой команды `--dry-run`, и он пишет в журнал
  наравне с настоящим, только помеченный.

Состояние живёт здесь, а не в файле рядом со скриптом. В Horse Bio история
прогонов лежала в `.sync_state.json` внутри тома, обрезалась до 90 записей
и не пережила бы ни один деплой без смонтированного volume — правило
`CLAUDE.md` §2 заведено ровно из-за этого.
"""

from django.db import models
from django.utils import timezone

from core.models.base import BackupGroup, DomainModel


class WritebackKind(models.TextChoices):
    COST_PRICES = "cost_prices", "Себестоимость → тип цены в карточке товара"


class WritebackStatus(models.TextChoices):
    RUNNING = "running", "Идёт"
    SUCCESS = "success", "Успешно"
    PARTIAL = "partial", "Частично — часть записей не прошла"
    FAILED = "failed", "Не удалось"
    BLOCKED = "blocked", "Отменён — выключатель выключен"
    STOPPED = "stopped", "Остановлен предохранителем"


class WritebackSwitch(DomainModel):
    """Выключатель одного вида записи. Строка на вид, правится в админке.

    Введена людьми — восстановлению синхронизацией не подлежит: выключенная
    запись обязана остаться выключенной и после восстановления из бэкапа.
    Иначе тот, кто выключил её из-за поломки, получит её обратно молча.
    """

    backup_group = BackupGroup.HUMAN

    kind = models.CharField(
        "Вид записи", max_length=32, choices=WritebackKind, unique=True
    )
    enabled = models.BooleanField("Включена", default=True)
    # Почему выключили. Пустое поле через месяц не отличить от «выключили
    # и забыли», а включать обратно вслепую — значит повторить ту же поломку.
    note = models.TextField("Примечание", blank=True)
    updated_at = models.DateTimeField("Изменено", auto_now=True)

    class Meta:
        verbose_name = "Выключатель обратной записи"
        verbose_name_plural = "Выключатели обратной записи"

    def __str__(self) -> str:
        return f"{self.get_kind_display()}: {'включена' if self.enabled else 'выключена'}"

    @classmethod
    def is_enabled(cls, kind: str) -> bool:
        """Включён ли вид записи. Нет строки — считаем включённым.

        Умолчание здесь обратное реестру страниц, и намеренно: там забывчивость
        обязана закрывать доступ, а тут отсутствие строки означает «выключатель
        ещё не заводили», а не «запрещено». Запрет должен быть решением
        человека, а не следствием пустой таблицы.
        """
        row = cls.objects.filter(kind=kind).first()
        return True if row is None else row.enabled


class WritebackRun(DomainModel):
    """Один прогон обратной записи."""

    backup_group = BackupGroup.SNAPSHOT

    kind = models.CharField("Вид записи", max_length=32, choices=WritebackKind)
    status = models.CharField(
        "Итог", max_length=16, choices=WritebackStatus, default=WritebackStatus.RUNNING
    )
    started_at = models.DateTimeField("Начат", default=timezone.now)
    finished_at = models.DateTimeField("Закончен", null=True, blank=True)

    # Пробный прогон пишется в журнал наравне с настоящим: иначе «проверили
    # и ничего не поменялось» неотличимо от «не запускали вовсе».
    dry_run = models.BooleanField("Пробный прогон", default=False)
    triggered_manually = models.BooleanField("Запущен вручную", default=False)

    considered = models.PositiveIntegerField("Рассмотрено", default=0)
    changed = models.PositiveIntegerField("Изменено", default=0)
    skipped = models.PositiveIntegerField("Пропущено", default=0)

    # **Пропуск разбит по причине, потому что склеенный ничего не говорил.**
    # «Изменено 0, пропущено 315» читается одинаково и как «всё уже сходится»,
    # и как «запись не работает», а отличить одно от другого по журналу было
    # нечем: 03.09 на этот вопрос не удалось ответить, не запуская пробный
    # прогон руками. Тот же приём, что у счётчиков пропусков в синхронизации,
    # — они дважды вскрыли потерю данных.
    #
    # Сумма двух равна `skipped`: показанное обязано складываться
    # в показанный итог (`DESIGN.md` §8).
    skipped_unknown = models.PositiveIntegerField(
        "Пропущено: значение неизвестно", default=0
    )
    skipped_equal = models.PositiveIntegerField(
        "Пропущено: уже совпадает", default=0
    )

    failed = models.PositiveIntegerField("Не удалось записать", default=0)

    # Лимит общий с ботом Agent - StarPony. Рост этого числа — первый признак,
    # что запись начала мешать чужой работе.
    request_count = models.PositiveIntegerField("Запросов к API", default=0)
    error = models.TextField("Ошибка", blank=True)

    class Meta:
        verbose_name = "Прогон обратной записи"
        verbose_name_plural = "Прогоны обратной записи"
        indexes = [models.Index(fields=["kind", "-started_at"])]

    def __str__(self) -> str:
        mark = " (пробный)" if self.dry_run else ""
        return f"{self.get_kind_display()} — {self.get_status_display()}{mark}"

    @property
    def duration_seconds(self) -> float | None:
        if not self.finished_at:
            return None
        return (self.finished_at - self.started_at).total_seconds()


class WritebackChange(models.Model):
    """Одна запись в учёт: что поменяли, с чего на что.

    Не зеркало и не домен: строка журнала, живущая ровно столько, сколько
    прогон. Значения хранятся числами, а не текстом, — чтобы на вопрос
    «когда себестоимость этого товара выросла вдвое» можно было ответить
    запросом, а не чтением глазами.
    """

    run = models.ForeignKey(
        WritebackRun, on_delete=models.CASCADE, related_name="changes"
    )

    # Идентификатор в МойСкладе, а не ссылка на нашу строку: журнал обязан
    # пережить и удаление товара из зеркала, и его исчезновение из учёта.
    target_ms_id = models.UUIDField("Идентификатор в МойСкладе")
    target_name = models.CharField("Что меняли", max_length=255)
    field = models.CharField("Какое поле", max_length=64)

    # Шесть знаков, как у остальных удельных величин: себестоимость приходит
    # дробными копейками у 150 позиций из 255, и округление до целого
    # в журнале расходилось бы с тем, что видно в карточке.
    old_value = models.DecimalField(
        "Было", max_digits=18, decimal_places=6, null=True, blank=True
    )
    new_value = models.DecimalField(
        "Стало", max_digits=18, decimal_places=6, null=True, blank=True
    )

    error = models.TextField("Ошибка записи", blank=True)

    class Meta:
        verbose_name = "Запись в учёт"
        verbose_name_plural = "Записи в учёт"
        indexes = [
            models.Index(fields=["run"]),
            models.Index(fields=["target_ms_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.target_name}: {self.old_value} → {self.new_value}"
