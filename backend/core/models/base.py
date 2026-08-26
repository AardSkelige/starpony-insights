"""Группа бэкапа — свойство модели, а не знание скрипта.

Данные в базе не равноценны. Зеркало МойСклада занимает почти весь объём, но
восстанавливается кнопкой «Обновить». Введённое людьми и снимки состояния
занимают мало места и не восстанавливаются ничем.

Поэтому каждая модель домена объявляет, к какой группе относится, — и скрипт
бэкапа собирает список таблиц отсюда, а не перебором вручную. Забывчивость
ловится тестом `test_backup_groups`, а не выясняется в момент восстановления.
"""

from django.apps import apps
from django.core.exceptions import ImproperlyConfigured
from django.db import models


class BackupGroup(models.TextChoices):
    MIRROR = "mirror", "Зеркало МойСклада — восстанавливается синхронизацией"
    HUMAN = "human", "Введено людьми — не восстанавливается ничем"
    SNAPSHOT = "snapshot", "Снимок состояния — безвозвратен"


class DomainModel(models.Model):
    """База для моделей домена. Наследник обязан объявить `backup_group`."""

    backup_group: str

    class Meta:
        abstract = True


def models_by_backup_group() -> dict[str, list[type[models.Model]]]:
    """Модели домена, разложенные по группам бэкапа."""
    grouped: dict[str, list[type[models.Model]]] = {group: [] for group in BackupGroup.values}
    for model in apps.get_models():
        if not issubclass(model, DomainModel):
            continue
        group = getattr(model, "backup_group", None)
        if group not in grouped:
            raise ImproperlyConfigured(
                f"{model.__name__} не объявил backup_group. Выберите группу "
                f"в core/models/base.py: {', '.join(BackupGroup.values)}."
            )
        grouped[group].append(model)
    return grouped
