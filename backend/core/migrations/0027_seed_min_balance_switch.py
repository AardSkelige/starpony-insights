"""Завести выключатель для записи неснижаемого остатка.

Отдельной миграцией, а не правкой `0014`: та применена на боевом, и менять
её содержимое значило бы полагаться на то, что кто-то догадается прогнать
её заново. Новый вид записи — новая строка, как и требует `CLAUDE.md` §6.

Строка создаётся включённой: запрет — решение человека, а не следствие
пустой таблицы. Выключатель обязан быть виден в админке **до** поломки,
потому что выключать приходится ровно тогда, когда запись уже портит учёт.
"""

from django.db import migrations

KIND = "min_balance"


def create_switch(apps, schema_editor):
    WritebackSwitch = apps.get_model("core", "WritebackSwitch")
    WritebackSwitch.objects.get_or_create(kind=KIND, defaults={"enabled": True})


def drop_switch(apps, schema_editor):
    WritebackSwitch = apps.get_model("core", "WritebackSwitch")
    WritebackSwitch.objects.filter(kind=KIND).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0026_stock_sale_price_kopecks"),
    ]

    operations = [
        migrations.RunPython(create_switch, drop_switch),
    ]
