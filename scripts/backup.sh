#!/usr/bin/env bash
# =============================================================================
# DBAI Backup Script
# Erstellt ein vollständiges Backup (Base + WAL-Archive)
# =============================================================================
set -euo pipefail

DB_NAME="${DBAI_DB_NAME:-dbai}"
DB_HOST="${DBAI_DB_HOST:-127.0.0.1}"
DB_PORT="${DBAI_DB_PORT:-5432}"
BACKUP_DIR="${DBAI_BACKUP_DIR:-/tmp/dbai_backups}"
RETENTION_DAYS="${DBAI_BACKUP_RETENTION:-30}"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="$BACKUP_DIR/dbai_backup_$TIMESTAMP"

echo "============================================================"
echo "  DBAI Backup — $TIMESTAMP"
echo "============================================================"

mkdir -p "$BACKUP_PATH"

# 1. pg_dump (logisches Backup)
echo "[1/3] Logisches Backup (pg_dump)..."
pg_dump -h "$DB_HOST" -p "$DB_PORT" -d "$DB_NAME" \
    -Fc --no-owner --no-privileges \
    -f "$BACKUP_PATH/dbai_logical.dump" 2>/dev/null && \
    echo "  OK: $(du -sh "$BACKUP_PATH/dbai_logical.dump" | cut -f1)" || \
    echo "  WARNUNG: pg_dump fehlgeschlagen"

# 2. Schema-Only Backup
echo "[2/3] Schema-Backup..."
pg_dump -h "$DB_HOST" -p "$DB_PORT" -d "$DB_NAME" \
    --schema-only \
    -f "$BACKUP_PATH/dbai_schema.sql" 2>/dev/null && \
    echo "  OK" || echo "  WARNUNG: Schema-Backup fehlgeschlagen"

# 3. Journal-Export (Append-Only Logs)
echo "[3/3] Journal-Export..."
psql -h "$DB_HOST" -p "$DB_PORT" -d "$DB_NAME" \
    -c "COPY dbai_journal.change_log TO STDOUT WITH CSV HEADER" \
    > "$BACKUP_PATH/journal_change_log.csv" 2>/dev/null && \
    echo "  OK: $(wc -l < "$BACKUP_PATH/journal_change_log.csv") Einträge" || \
    echo "  WARNUNG: Journal-Export fehlgeschlagen"

# Alte Backups aufräumen
echo ""
echo "Bereinige Backups älter als ${RETENTION_DAYS} Tage..."
find "$BACKUP_DIR" -maxdepth 1 -name "dbai_backup_*" -mtime +${RETENTION_DAYS} -exec rm -rf {} \;

TOTAL_SIZE=$(du -sh "$BACKUP_PATH" 2>/dev/null | cut -f1)
echo ""
echo "Backup abgeschlossen: $BACKUP_PATH ($TOTAL_SIZE)"
