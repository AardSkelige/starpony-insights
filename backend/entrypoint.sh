#!/bin/sh
set -e

# Postgres поднимается дольше приложения, и depends_on ждёт лишь запуска
# контейнера, а не готовности базы принимать запросы. Без этой петли первый
# же migrate падает, а рестарт-политика превращает старт в череду падений.
echo "Ожидание базы данных..."
until python -c "
import os, sys, psycopg
try:
    psycopg.connect(
        dbname=os.environ['POSTGRES_DB'],
        user=os.environ['POSTGRES_USER'],
        password=os.environ['POSTGRES_PASSWORD'],
        host=os.environ.get('POSTGRES_HOST', 'db'),
        port=os.environ.get('POSTGRES_PORT', '5432'),
        connect_timeout=3,
    ).close()
except Exception as exc:
    print(exc, file=sys.stderr)
    sys.exit(1)
"; do
    sleep 1
done
echo "База отвечает."

python manage.py migrate --noinput
# Идемпотентно: если таблица есть, команда просто сообщает об этом.
python manage.py createcachetable
python manage.py collectstatic --noinput --clear

exec "$@"
