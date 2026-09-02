"""Каждая модель домена знает, в какую группу бэкапа она входит.

Забыть объявление легко, а выясняется это в момент, когда данные уже потеряны:
таблица не попала ни в один набор и просто не бэкапилась.
"""

from django.apps import apps

from core.models import BackupGroup, DomainModel, models_by_backup_group

# Наши приложения: чужие модели (админка, сессии, права) бэкапятся отдельно
# как служебные таблицы Django.
OUR_APPS = {"core", "api", "moysklad"}

# Модели без своей группы — только те, что не живут отдельно от родителя
# и уезжают в бэкап вместе с ним.
EXEMPT = {
    "DocumentPosition",  # существует только внутри документа, каскадом
    "ProcessingPlanMaterial",  # существует только внутри техкарты, каскадом
    "WritebackChange",  # строка журнала, существует только внутри прогона
}


def our_models():
    return [m for m in apps.get_models() if m._meta.app_label in OUR_APPS]


def test_every_model_declares_a_backup_group():
    """Проверка идёт по всем моделям наших приложений, а не по наследникам
    DomainModel.

    Так и было пропущено: `MirrorModel` наследовал `models.Model`, поэтому
    зеркало (товары, документы, контрагенты) выпадало из разбивки целиком —
    а тест, перебиравший только наследников `DomainModel`, проходил вхолостую.
    """
    missing = []
    for model in our_models():
        if model.__name__ in EXEMPT:
            continue
        if not issubclass(model, DomainModel):
            missing.append(f"{model.__name__} не наследует DomainModel")
        elif getattr(model, "backup_group", None) not in BackupGroup.values:
            missing.append(f"{model.__name__} не объявил backup_group")

    assert not missing, (
        "Модели вне разбивки по группам бэкапа:\n  "
        + "\n  ".join(missing)
        + "\nЛибо унаследуйте DomainModel и объявите backup_group, "
          "либо внесите в EXEMPT с объяснением."
    )


def test_mirror_group_is_not_empty():
    """Зеркало МойСклада — самая большая группа, и она обязана быть видна.

    Пустая группа означала бы, что скрипт бэкапа молча пропускает
    все таблицы зеркала.
    """
    mirror = models_by_backup_group()[BackupGroup.MIRROR]
    names = {m.__name__ for m in mirror}
    assert {"Product", "Document", "Counterparty"} <= names, (
        f"В группе mirror не хватает моделей зеркала: {sorted(names)}"
    )


def test_human_data_is_not_empty():
    """Пользователи и доступы — те самые данные, которые ничем не восстановить."""
    human = models_by_backup_group()[BackupGroup.HUMAN]
    assert {model.__name__ for model in human} >= {"User", "UserPageAccess"}


def test_snapshot_group_holds_sync_history():
    """История синхронизаций безвозвратна: заново её не получить."""
    snapshot = models_by_backup_group()[BackupGroup.SNAPSHOT]
    assert {"SyncRun", "SyncEntityResult", "WritebackRun"} <= {
        m.__name__ for m in snapshot
    }


def test_writeback_switch_is_human_data():
    """Выключатель обратной записи вводят люди, и он обязан пережить восстановление.

    Попади он в группу зеркала — восстановление из бэкапа молча вернуло бы
    запись в учёт тому, кто её выключил из-за поломки.
    """
    human = models_by_backup_group()[BackupGroup.HUMAN]
    assert "WritebackSwitch" in {model.__name__ for model in human}
