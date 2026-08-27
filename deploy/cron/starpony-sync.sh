#!/bin/bash
#
# Обёртка для запуска синхронизации по расписанию.
#
# Делает три вещи, которых не умеет голый cron:
#   1. Не даёт двум прогонам наложиться (flock) — advisory-блокировка в коде
#      защищает базу, но не защищает от лишнего процесса в памяти;
#   2. Сообщает внешнему наблюдателю, что прогон был и чем кончился;
#   3. Пишет вывод в журнал с отметкой времени.
#
# Использование: starpony-sync.sh documents|state
set -uo pipefail

COMMAND="${1:?Укажите, что синхронизировать: documents или state}"
PROJECT_DIR=/root/starpony
LOG=/var/log/starpony_sync.log

case "$COMMAND" in
  documents) LOCK=/var/lock/starpony-sync-documents.lock; TIMEOUT=1800 ;;
  state)     LOCK=/var/lock/starpony-sync-state.lock;     TIMEOUT=600  ;;
  *) echo "Неизвестная синхронизация: $COMMAND" >&2; exit 2 ;;
esac

# Адрес проверки живости задаётся окружением. Пусто — ничего не отправляем:
# так внешний наблюдатель подключается без единой правки в коде.
#   HEALTHCHECK_DOCUMENTS=https://hc-ping.com/<uuid>
#   HEALTHCHECK_STATE=https://hc-ping.com/<uuid>
VAR="HEALTHCHECK_$(echo "$COMMAND" | tr '[:lower:]' '[:upper:]')"
PING_URL="${!VAR:-}"

ping_healthcheck() {
    [ -n "$PING_URL" ] || return 0
    # Молча и с коротким таймаутом: недоступность наблюдателя не должна
    # задерживать синхронизацию и не должна попадать в журнал как ошибка.
    curl -fsS -m 10 --retry 3 "${PING_URL}${1:-}" >/dev/null 2>&1 || true
}

log() { echo "[$(date '+%F %T')] $COMMAND: $*" >> "$LOG"; }

# Сигнал «прогон начался»: по нему наблюдатель отличает долгий синк
# от несостоявшегося.
ping_healthcheck "/start"

# Код, которым flock сообщает «замок занят». Свой, а не общий 1: иначе
# пропущенный запуск неотличим от упавшей синхронизации, и каждый тик
# поднимал бы ложную тревогу, пока идёт долгий прогон.
LOCK_BUSY=75

# timeout запускается ВНУТРИ контейнера. Снаружи он убил бы только клиента
# docker compose, а сама команда продолжила бы работать: держать блокировку
# в Postgres и выбирать лимит запросов, общий с ботом. При этом наружу
# это выглядело бы как завершённый сбой.
OUTPUT=$(flock -n -E "$LOCK_BUSY" "$LOCK" \
    docker compose -f "$PROJECT_DIR/docker-compose.prod.yml" \
        exec -T backend timeout "$TIMEOUT" python manage.py "sync_$COMMAND" 2>&1)
STATUS=$?

case $STATUS in
  0)
    log "$OUTPUT"
    ping_healthcheck
    ;;
  "$LOCK_BUSY")
    # Предыдущий прогон ещё идёт. Это штатное поведение, а не сбой:
    # очередь синхронизаций хуже пропущенного запуска.
    log "пропуск: предыдущий прогон ещё идёт"
    ping_healthcheck
    STATUS=0
    ;;
  124)
    # timeout внутри контейнера прервал команду по сроку.
    log "ОШИБКА: превышен срок $TIMEOUT с"
    ping_healthcheck "/$STATUS"
    ;;
  *)
    log "ОШИБКА (код $STATUS): $OUTPUT"
    ping_healthcheck "/$STATUS"
    ;;
esac

exit $STATUS
