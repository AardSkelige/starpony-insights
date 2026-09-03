"""Записать бэкап в журнал и решить, что из старого удалить.

Разделение с оболочкой намеренное. Сам `pg_dump` запускается снаружи,
внутри контейнера базы: там он одной версии с сервером, и клиент нужной
версии не приходится тащить в образ приложения (Debian отдаёт 17-й, сервер
у нас 18-й, и такой `pg_dump` дампить отказывается).

А сюда переезжает то, что стоит проверять: журнал и **решение об удалении**.
Снять копию — операция без последствий, удалить старую — необратимая,
и она не должна жить строкой `ls -t | tail | xargs rm`.

Список удаляемого печатается в stdout по имени на строку — оболочка удаляет
ровно то, что здесь названо, и ничего кроме.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import BackupRun, BackupStatus
from core.services import backup_rotation


class Command(BaseCommand):
    help = "Записать результат снятия бэкапа и назвать архивы к удалению"

    def add_arguments(self, parser):
        parser.add_argument("--name", default="", help="Имя созданного архива")
        parser.add_argument("--bytes", type=int, default=0, help="Размер архива")
        parser.add_argument(
            "--existing",
            nargs="*",
            default=[],
            help="Все архивы в каталоге, включая только что снятый",
        )
        parser.add_argument(
            "--keep",
            type=int,
            default=backup_rotation.DEFAULT_KEEP,
            help="Сколько снимков держать",
        )
        parser.add_argument(
            "--verified",
            action="store_true",
            help="Архив прочитан обратно: опись читается, содержимое на месте",
        )
        parser.add_argument("--failed", action="store_true", help="Прогон не удался")
        parser.add_argument("--error", default="", help="Текст ошибки")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Ничего не удалять: список печатается, но помечен пробным",
        )

    def handle(self, *args, **options):
        failed = options["failed"]
        verified = options["verified"] and not failed

        rotation = backup_rotation.plan(
            options["existing"], verified=verified, keep=options["keep"]
        )

        # Пробный прогон ничего не удаляет, но пишется в журнал наравне
        # с настоящим: «проверили, и ничего не поменялось» обязано быть
        # отличимо от «не запускали вовсе».
        prune = () if options["dry_run"] else rotation.prune

        BackupRun.objects.create(
            finished_at=timezone.now(),
            status=BackupStatus.FAILED if failed else BackupStatus.SUCCESS,
            name=options["name"],
            size_bytes=options["bytes"],
            verified=verified,
            pruned=list(prune),
            kept=len(rotation.keep),
            dry_run=options["dry_run"],
            error=options["error"],
        )

        for name in prune:
            self.stdout.write(name)
