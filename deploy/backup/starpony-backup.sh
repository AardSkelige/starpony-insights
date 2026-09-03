#!/bin/bash
#
# Резервная копия базы StarPony Insights.
#
# Своя, а не общая с Horse Bio, намеренно. Скрипт того проекта
# (/root/backup/backup.sh) прямо сейчас бэкапит чужие боевые данные;
# править его ради второй базы — значит рисковать обоими бэкапами разом,
# и выяснится это в день отказа диска. Две копии одного приёма — плата
# за то, что рабочий чужой бэкап остаётся нетронутым.
#
# Порядок и есть суть: снять → **прочитать обратно** → и только потом
# удалять старое. «Файл создался» ничего не значит: пустой архив создаётся
# так же успешно, как настоящий.
#
# Что удалять — решает не этот скрипт, а `manage.py record_backup`:
# единственная необратимая операция здесь живёт в тестируемом коде,
# а не в строке `ls -t | tail | xargs rm`.
#
# Использование: starpony-backup.sh [--dry-run]
set -uo pipefail

PROJECT_DIR=${PROJECT_DIR:-/root/starpony}
# Массивом, а не строкой: в пути каталога может оказаться пробел,
# и тогда неквотированная подстановка разрывает команду посередине.
COMPOSE=(docker compose -f "$PROJECT_DIR/docker-compose.prod.yml")
DEST=${BACKUP_DIR:-/root/backup/starpony}
LOG=${BACKUP_LOG:-/var/log/starpony_backup.log}
LOCK=${BACKUP_LOCK:-/var/lock/starpony-backup.lock}
KEEP=${BACKUP_KEEP:-14}
DRY_RUN=""
[ "${1:-}" = "--dry-run" ] && DRY_RUN="--dry-run"

# Проверочная база: имя постоянное, и перед восстановлением она сносится.
# Случайное имя оставляло бы мусор после каждого падения скрипта.
VERIFY_DB=starpony_backup_verify

log() { echo "[$(date '+%F %T')] $*" >> "$LOG"; }

# Один прогон за раз: снятие копии тяжелее синхронизации, и наложение
# двух дампов на одном ядре кладёт сервер вместе с чужим проектом.
exec 9>"$LOCK"
if ! flock -n 9; then
    log "пропуск: предыдущий прогон ещё идёт"
    exit 0
fi

mkdir -p "$DEST"

DB=$("${COMPOSE[@]}" exec -T db printenv POSTGRES_DB 2>/dev/null | tr -d '\r')
USER=$("${COMPOSE[@]}" exec -T db printenv POSTGRES_USER 2>/dev/null | tr -d '\r')
if [ -z "$DB" ] || [ -z "$USER" ]; then
    log "ОШИБКА: не удалось прочитать POSTGRES_DB/POSTGRES_USER из контейнера базы"
    exit 1
fi

NAME="starpony-$(date '+%Y-%m-%d-%H%M').dump"
FILE="$DEST/$NAME"

# pg_dump запускается ВНУТРИ контейнера базы: там он одной версии с сервером.
# Клиент из образа приложения не годится — Debian отдаёт 17-й, сервер 18-й,
# и такой pg_dump дампить отказывается.
#
# Формат custom, а не текстовый: он сжат, и из него можно восстановить
# выборочно — а именно это и нужно в день, когда потеряли одну таблицу.
if ! "${COMPOSE[@]}" exec -T db pg_dump -U "$USER" -d "$DB" --format=custom > "$FILE" 2>>"$LOG"; then
    log "ОШИБКА: pg_dump не отработал"
    rm -f "$FILE"
    # Неудача обязана попасть в журнал: молчащий бэкап неотличим
    # от не запускавшегося, и заметить это можно только по его отсутствию
    # в день, когда он понадобился.
    "${COMPOSE[@]}" exec -T backend python manage.py record_backup \
        --failed --error "pg_dump не отработал" >>"$LOG" 2>&1
    exit 1
fi

BYTES=$(stat -c%s "$FILE" 2>/dev/null || stat -f%z "$FILE")

# --- Проверка восстановлением. Признак готовности бэкапа — не «файл есть»,
#     а «из него поднялась база». Восстанавливаем в отдельную базу того же
#     кластера и считаем строки в таблице, которая не бывает пустой.
verify() {
    "${COMPOSE[@]}" exec -T db dropdb -U "$USER" --if-exists "$VERIFY_DB" >>"$LOG" 2>&1 || return 1
    "${COMPOSE[@]}" exec -T db createdb -U "$USER" "$VERIFY_DB" >>"$LOG" 2>&1 || return 1
    "${COMPOSE[@]}" exec -T db pg_restore -U "$USER" -d "$VERIFY_DB" --no-owner \
        >>"$LOG" 2>&1 < "$FILE" || return 1
    local rows
    rows=$("${COMPOSE[@]}" exec -T db psql -U "$USER" -d "$VERIFY_DB" -tAc \
        "select count(*) from core_product" 2>>"$LOG" | tr -d '[:space:]')
    [ -n "$rows" ] && [ "$rows" -gt 0 ]
}

VERIFIED=""
if verify; then
    VERIFIED="--verified"
    log "снят и проверен: $NAME ($(awk -v b=$BYTES 'BEGIN{printf "%.1f", b/1048576}') МБ)"
else
    log "ОШИБКА: архив $NAME не восстанавливается — старое не трогаем"
fi
"${COMPOSE[@]}" exec -T db dropdb -U "$USER" --if-exists "$VERIFY_DB" >>"$LOG" 2>&1

# --- Ротация. Список удаляемого приходит из кода, а не собирается здесь.
EXISTING=()
while IFS= read -r line; do EXISTING+=("$line"); done < <(cd "$DEST" && ls -1 ./*.dump 2>/dev/null | sed 's|^\./||')

# Код возврата проверяется обязательно. Бэкап идёт в 4:30, сразу после
# ночного цикла: не поднялся контейнер приложения — строка в журнале
# не появится, ротация ничего не удалит, а скрипт вышел бы нулём.
# «Не запускалось» стало бы неотличимо от «отработало» — ровно то,
# против чего журнал и заведён.
if ! PRUNE=$("${COMPOSE[@]}" exec -T backend python manage.py record_backup \
    --name "$NAME" --bytes "$BYTES" --keep "$KEEP" $VERIFIED $DRY_RUN \
    --existing "${EXISTING[@]}" 2>>"$LOG"); then
    log "ОШИБКА: журнал не записан — архив $NAME снят, старое не тронуто"
    exit 1
fi

while IFS= read -r victim; do
    [ -n "$victim" ] || continue
    rm -f -- "$DEST/$victim" && log "удалён старый архив: $victim"
done <<< "$PRUNE"

[ -n "$VERIFIED" ] || exit 1
exit 0
