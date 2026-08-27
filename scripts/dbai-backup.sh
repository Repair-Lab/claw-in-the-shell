#!/usr/bin/env bash
# DBAI Backup — logischer Dump via pg_dump im dbai-postgres-Container
# Laufzeit: täglich (systemd-Timer dbai-backup.timer)
set -uo pipefail

REPO="/home/worker/claw-in-the-shell"
DB="${DBAI_DB_NAME:-dbai}"
DB_SUPER="${DBAI_DB_SUPERUSER:-dbai_system}"   # Superuser für pg_dump (Socket-Trust)
BACKUP_DIR="/home/worker/dbai-backups"
RETENTION_DAYS="${DBAI_BACKUP_RETENTION:-30}"
LOG="$REPO/logs/backup.log"

ts() { date '+%F %T'; }

log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

mkdir -p "$BACKUP_DIR"

TS="$(date +%Y%m%d_%H%M%S)"
DUMP="$BACKUP_DIR/dbai_${TS}.dump"
SCHEMA="$BACKUP_DIR/dbai_${TS}_schema.sql"

log "BACKUP START (DB=$DB, dump=$DUMP)"

# 1. Logischer Dump (custom-Format, komprimiert, portabel)
#    Als dbai_system (Superuser) via Socket-Trust im Container:
#    dbai_runtime fehlt das Recht, Sequenzen zu lesen.
if podman exec -e PGUSER="$DB_SUPER" -e PGDATABASE="$DB" \
     dbai-postgres pg_dump -Fc --no-owner --no-privileges > "$DUMP" 2>>"$LOG"; then
    SIZE=$(du -h "$DUMP" | cut -f1)
    # Integrität: Header prüfen
    if head -c 8 "$DUMP" | grep -q 'PGDMP'; then
        log "LOGIC-OK size=$SIZE"
    else
        log "LOGIC-BAD: Header fehlend — Dump verworfen"
        rm -f "$DUMP"
        exit 1
    fi
else
    log "LOGIC-FAIL: pg_dump fehlerhaft — Dump verworfen"
    rm -f "$DUMP"
    exit 1
fi

# 2. Schema-only (schnell, für Recovery-Analyse)
podman exec -e PGUSER="$DB_SUPER" -e PGDATABASE="$DB" \
     dbai-postgres pg_dump --schema-only > "$SCHEMA" 2>>"$LOG" \
    && log "SCHEMA-OK $(wc -l < "$SCHEMA") Zeilen" \
    || log "SCHEMA-WARN (nicht fatal)"

# 3. Retention: ältere als RETENTION_DAYS löschen
DELETED=$(find "$BACKUP_DIR" -name 'dbai_*.dump' -mtime +"$RETENTION_DAYS" -delete -print 2>/dev/null | wc -l)
find "$BACKUP_DIR" -name 'dbai_*_schema.sql' -mtime +"$RETENTION_DAYS" -delete >/dev/null 2>&1
log "RETENTION: $DELETED alte Dump(s) gelöscht (>$RETENTION_DAYS Tage)"

# 4. Status-Zusammenfassung
COUNT=$(ls -1 "$BACKUP_DIR"/dbai_*.dump 2>/dev/null | wc -l)
TOTAL=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)
log "BACKUP DONE: $COUNT Dumps vorhanden, $TOTAL gesamt"
exit 0
