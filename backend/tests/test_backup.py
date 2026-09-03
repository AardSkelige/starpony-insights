"""Ротация резервных копий и журнал.

Единственная необратимая операция во всём бэкапе — удаление старого архива.
Ошибка здесь тихая: копии продолжают сниматься, журнал зелёный, а истории
за прошлый месяц уже нет, и выясняется это в день, когда она понадобилась.

Поэтому проверяется не «удалилось ли», а **когда удалять нельзя**.
"""

import pytest

from core.models import BackupRun, BackupStatus
from core.services import backup_rotation
from django.core.management import call_command
from io import StringIO

pytestmark = pytest.mark.django_db


def names(count: int, start: int = 1) -> list[str]:
    """Архивы по дням: имя несёт отметку времени, порядок — алфавитный."""
    return [f"starpony-2026-09-{day:02d}-0330.dump" for day in range(start, start + count)]


class TestRotationPlan:
    def test_лишнее_сверх_порога_уходит(self):
        rotation = backup_rotation.plan(names(16), verified=True, keep=14)

        assert len(rotation.keep) == 14
        assert rotation.prune == (
            "starpony-2026-09-02-0330.dump",
            "starpony-2026-09-01-0330.dump",
        )

    def test_удаляется_самое_старое_а_не_самое_новое(self):
        rotation = backup_rotation.plan(names(3), verified=True, keep=2)

        assert rotation.prune == ("starpony-2026-09-01-0330.dump",)
        assert "starpony-2026-09-03-0330.dump" in rotation.keep

    def test_непроверенный_прогон_не_удаляет_ничего(self):
        """Главное правило: старое живёт, пока новое не прочитано обратно.

        Пустой архив создаётся так же успешно, как настоящий. Удали мы
        по факту создания — единственная годная копия могла оказаться
        как раз самой старой.
        """
        rotation = backup_rotation.plan(names(30), verified=False, keep=14)

        assert rotation.prune == ()
        assert len(rotation.keep) == 30

    def test_архивов_меньше_порога_удалять_нечего(self):
        assert backup_rotation.plan(names(3), verified=True, keep=14).prune == ()

    def test_каталог_пуст(self):
        rotation = backup_rotation.plan([], verified=True, keep=14)

        assert rotation.keep == ()
        assert rotation.prune == ()


class TestCommandJournalsAndNames:
    def run(self, **kwargs) -> tuple[str, BackupRun]:
        out = StringIO()
        call_command("record_backup", stdout=out, **kwargs)
        return out.getvalue().split(), BackupRun.objects.latest("started_at")

    def test_печатает_только_то_что_удалять(self):
        printed, _ = self.run(
            name=names(1)[0], bytes=1024, existing=names(16), verified=True, keep=14
        )

        assert printed == [
            "starpony-2026-09-02-0330.dump",
            "starpony-2026-09-01-0330.dump",
        ]

    def test_журнал_помнит_что_удалили_именами(self):
        """«Куда делся архив за прошлый вторник» — вопрос к именам, не к числу."""
        _, run = self.run(existing=names(16), verified=True, keep=14)

        assert run.pruned == [
            "starpony-2026-09-02-0330.dump",
            "starpony-2026-09-01-0330.dump",
        ]
        assert run.kept == 14

    def test_неудачный_прогон_не_считается_проверенным(self):
        printed, run = self.run(existing=names(30), verified=True, failed=True, keep=14)

        assert printed == []
        assert run.status == BackupStatus.FAILED
        assert run.verified is False

    def test_пробный_прогон_ничего_не_называет_но_пишется(self):
        """«Проверили, ничего не поменялось» обязано отличаться от «не запускали»."""
        printed, run = self.run(existing=names(16), verified=True, dry_run=True, keep=14)

        assert printed == []
        assert run.dry_run is True
        assert run.pruned == []

    def test_размер_и_имя_попадают_в_журнал(self):
        _, run = self.run(name="starpony-2026-09-03-0330.dump", bytes=7_340_032, verified=True)

        assert run.name == "starpony-2026-09-03-0330.dump"
        assert run.size_bytes == 7_340_032
        assert run.status == BackupStatus.SUCCESS
