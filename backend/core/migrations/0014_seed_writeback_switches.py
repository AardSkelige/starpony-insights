"""Завести выключатель на каждый вид обратной записи.

Без строки выключатель существует только в коде: в админке его не видно,
и человек, которому запись прямо сейчас портит учёт, не может её остановить —
разве что догадается нажать «Добавить» и выбрать нужный вид из списка.
Выключатель, которого не найти в момент поломки, не выключатель.

Строки создаются включёнными: умолчание «работает» здесь осознанное —
запрет должен быть решением человека, а не следствием пустой таблицы.
"""

from django.db import migrations

KINDS = [
    ("cost_prices", "Себестоимость → тип цены в карточке товара"),
]


def create_switches(apps, schema_editor):
    WritebackSwitch = apps.get_model("core", "WritebackSwitch")
    for kind, _label in KINDS:
        WritebackSwitch.objects.get_or_create(kind=kind, defaults={"enabled": True})


def drop_switches(apps, schema_editor):
    WritebackSwitch = apps.get_model("core", "WritebackSwitch")
    WritebackSwitch.objects.filter(kind__in=[kind for kind, _ in KINDS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0013_counterparty_deferral_days_document_deferral_days_and_more"),
    ]

    operations = [
        migrations.RunPython(create_switches, drop_switches),
    ]
