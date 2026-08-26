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

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"


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
        verbose_name = "Доступ к странице"
        verbose_name_plural = "Доступы к страницам"
        constraints = [
            models.UniqueConstraint(fields=["user", "page_key"], name="unique_user_page"),
        ]

    def __str__(self) -> str:
        return f"{self.user} → {self.page_key}"
