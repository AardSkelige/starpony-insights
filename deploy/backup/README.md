# Бэкап базы StarPony

## Установка на сервере

```bash
mkdir -p /root/backup/starpony
crontab -l > /tmp/c && cat /root/starpony/deploy/cron/starpony.cron >> /tmp/c && crontab /tmp/c
crontab -l | grep starpony-backup   # должна быть одна строка
```

## Приёмка — прогоном, а не наличием файла

Три раза подряд в этом проекте файл лежал в репозитории и не был установлен
на сервере. Поэтому готовым бэкап считается только после этого:

```bash
/root/starpony/deploy/backup/starpony-backup.sh
tail -20 /var/log/starpony_backup.log     # «снят и проверен: …»
ls -lh /root/backup/starpony/
```

И в админке, «Журналы» → «Бэкапы базы»: строка со статусом «Готово»
и галочкой **«Проверен восстановлением»**. Без галочки бэкапа нет —
пустой архив создаётся так же успешно, как настоящий.

## Восстановление

```bash
cd /root/starpony
docker compose -f docker-compose.prod.yml exec -T db \
    dropdb -U starpony --if-exists starpony_restore
docker compose -f docker-compose.prod.yml exec -T db \
    createdb -U starpony starpony_restore
docker compose -f docker-compose.prod.yml exec -T db \
    pg_restore -U starpony -d starpony_restore --no-owner \
    < /root/backup/starpony/starpony-2026-09-03-0430.dump
```

Восстанавливается в отдельную базу намеренно: поверх рабочей — операция,
которую нельзя отменить, и делать её одной командой из инструкции не стоит.
Убедились, что данные на месте, — тогда переключаем.

## Почему не общий скрипт с Horse Bio

`/root/backup/backup.sh` прямо сейчас бэкапит боевые данные другого проекта.
Править его ради второй базы — рисковать обоими бэкапами разом, и выяснится
это в день отказа диска. Две копии одного приёма — плата за то, что рабочий
чужой бэкап остаётся нетронутым.

## Что где

| | |
|---|---|
| Архивы | `/root/backup/starpony/`, формат custom, 14 последних |
| Журнал скрипта | `/var/log/starpony_backup.log` |
| Журнал в базе | админка → «Журналы» → «Бэкапы базы» |
| Что удалять | решает `manage.py record_backup`, не оболочка |
