"""Пользователи и постраничные доступы."""

from django.contrib.auth.models import AbstractUser
from django.db import models

from core.models.base import BackupGroup, DomainModel


class User(AbstractUser, DomainModel):
    """Пользователь системы.

    Пустой наследник — намеренно. Django не позволяет безболезненно подменить
    AUTH_USER_MODEL после первой миграции, поэтому своя модель заводится сразу,
    а поля добавляются по мере надобности обычными миграциями.
    """

    backup_group = BackupGroup.HUMAN

    # Подпись под именем в сайдбаре. Пустая — и там остаётся «Сотрудник»
    # или «Полный доступ»: подпись, собранная из прав, отвечает на вопрос,
    # которого человек про себя не задаёт.
    title = models.CharField("Должность", max_length=64, blank=True)

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    @property
    def sidebar_title(self) -> str:
        """Что стоит под именем в меню.

        Должность важнее прав: «Хранитель остатков» человек про себя
        узнаёт, а «Полный доступ» — нет. Права остаются запасным вариантом,
        пока должность не заполнена.
        """
        if self.title:
            return self.title
        return "Полный доступ" if self.is_superuser else "Сотрудник"


class UserPageAccess(DomainModel):
    """Разрешение на одну страницу.

    Наличие строки = доступ есть, отсутствие = доступа нет. Никакого поля
    «запрещено»: два способа сказать «нет» неизбежно разъезжаются.

    `page_key` — ключ из реестра PAGES (`api/access.py`). Внешнего ключа нет
    намеренно: реестр живёт в коде, а не в таблице, иначе появляется второй
    источник правды, который надо синхронизировать миграциями.
    """

    backup_group = BackupGroup.HUMAN

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="page_access")
    page_key = models.CharField("Ключ страницы", max_length=64)
    granted_at = models.DateTimeField("Выдан", auto_now_add=True)
    granted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="access_granted",
        verbose_name="Кто выдал",
    )

    class Meta:
        # В админке отдельным пунктом не показывается: выдают галочками
        # в карточке человека, и там же видно выданное. Второй список
        # с теми же строками — лишний пункт меню, а не ответ на вопрос.
        verbose_name = "Выданный доступ"
        verbose_name_plural = "Выданные доступы"
        constraints = [
            models.UniqueConstraint(fields=["user", "page_key"], name="unique_user_page"),
        ]

    def __str__(self) -> str:
        return f"{self.user} → {self.page_key}"
