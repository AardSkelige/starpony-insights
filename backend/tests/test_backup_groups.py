"""Каждая модель домена знает, в какую группу бэкапа она входит.

Забыть объявление легко, а выясняется это в момент, когда данные уже потеряны:
таблица не попала ни в один набор и просто не бэкапилась.
"""

from django.apps import apps

from core.models import BackupGroup, DomainModel, models_by_backup_group


def test_every_domain_model_declares_group():
    for model in apps.get_models():
        if not issubclass(model, DomainModel):
            continue
        group = getattr(model, "backup_group", None)
        assert group in BackupGroup.values, (
            f"{model.__name__} не объявил backup_group. Выберите группу "
            f"в core/models/base.py: mirror, human или snapshot."
        )


def test_human_data_is_not_empty():
    """Пользователи и доступы — те самые данные, которые ничем не восстановить."""
    human = models_by_backup_group()[BackupGroup.HUMAN]
    assert {model.__name__ for model in human} >= {"User", "UserPageAccess"}
