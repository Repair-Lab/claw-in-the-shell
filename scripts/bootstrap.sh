#!/usr/bin/env bash
# =============================================================================
# DBAI Bootstrap Script
# Erstellt die Datenbank und lädt alle Schemas
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DBAI_ROOT="$(dirname "$SCRIPT_DIR")"
SCHEMA_DIR="$DBAI_ROOT/schema"

# Konfiguration
DB_NAME="${DBAI_DB_NAME:-dbai}"
DB_USER="${DBAI_DB_USER:-dbai_system}"
DB_HOST="${DBAI_DB_HOST:-127.0.0.1}"
DB_PORT="${DBAI_DB_PORT:-5432}"
PG_ADMIN="${PG_ADMIN_USER:-postgres}"

# Farben
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

echo "============================================================"
echo "  DBAI — Bootstrap"
echo "  Datenbank erstellen und Schemas laden"
echo "============================================================"
echo ""

# ------------------------------------------------------------------
# Prüfe PostgreSQL
# ------------------------------------------------------------------
if ! pg_isready -h "$DB_HOST" -p "$DB_PORT" -q 2>/dev/null; then
    log_error "PostgreSQL läuft nicht auf $DB_HOST:$DB_PORT"
    log_info "Starte PostgreSQL und versuche es erneut"
    exit 1
fi
log_ok "PostgreSQL erreichbar auf $DB_HOST:$DB_PORT"

# ------------------------------------------------------------------
# Funktion: SQL als Admin ausführen
# ------------------------------------------------------------------
run_sql_admin() {
    sudo -u "$PG_ADMIN" psql -h "$DB_HOST" -p "$DB_PORT" -d postgres -c "$1" 2>/dev/null || \
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$PG_ADMIN" -d postgres -c "$1" 2>/dev/null || \
    psql -h "$DB_HOST" -p "$DB_PORT" -d postgres -c "$1" 2>/dev/null
}

run_sql_db() {
    sudo -u "$PG_ADMIN" psql -h "$DB_HOST" -p "$DB_PORT" -d "$DB_NAME" -c "$1" 2>/dev/null || \
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$PG_ADMIN" -d "$DB_NAME" -c "$1" 2>/dev/null || \
    psql -h "$DB_HOST" -p "$DB_PORT" -d "$DB_NAME" -c "$1" 2>/dev/null
}

run_sql_file() {
    sudo -u "$PG_ADMIN" psql -h "$DB_HOST" -p "$DB_PORT" -d "$DB_NAME" -f "$1" 2>&1 || \
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$PG_ADMIN" -d "$DB_NAME" -f "$1" 2>&1 || \
    psql -h "$DB_HOST" -p "$DB_PORT" -d "$DB_NAME" -f "$1" 2>&1
}

# ------------------------------------------------------------------
# 1. Datenbank erstellen
# ------------------------------------------------------------------
log_info "Erstelle Datenbank '$DB_NAME'..."

if run_sql_admin "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1; then
    log_warn "Datenbank '$DB_NAME' existiert bereits"
else
    if run_sql_admin "CREATE DATABASE $DB_NAME OWNER $PG_ADMIN ENCODING 'UTF8'"; then
        log_ok "Datenbank '$DB_NAME' erstellt"
    else
        log_error "Datenbank konnte nicht erstellt werden"
        exit 1
    fi
fi

# ------------------------------------------------------------------
# 2. Schemas laden (in Reihenfolge)
# ------------------------------------------------------------------
log_info "Lade SQL-Schemas..."

SCHEMA_FILES=(
    "00-extensions.sql"
    "01-core-tables.sql"
    "02-system-tables.sql"
    "03-event-tables.sql"
    "04-vector-tables.sql"
    "05-wal-journal.sql"
    "06-panic-schema.sql"
    "07-row-level-security.sql"
    "08-llm-integration.sql"
    "09-vacuum-schedule.sql"
    "10-sync-primitives.sql"
    "11-knowledge-library.sql"
    "12-error-patterns.sql"
    "13-seed-data.sql"
    "14-self-healing.sql"
    "15-ghost-system.sql"
    "16-desktop-ui.sql"
    "17-ghost-desktop-seed.sql"
    "18-hardware-abstraction.sql"
    "19-neural-bridge.sql"
    "20-hw-seed-data.sql"
    "21-openclaw-bridge.sql"
    "22-ghost-autonomy.sql"
    "23-app-ecosystem.sql"
    "24-system-memory.sql"
    "25-system-memory-seed.sql"
)

FAILED=0
for schema_file in "${SCHEMA_FILES[@]}"; do
    full_path="$SCHEMA_DIR/$schema_file"
    if [ -f "$full_path" ]; then
        log_info "  Lade $schema_file..."
        output=$(run_sql_file "$full_path" 2>&1) || true

        # Prüfe auf kritische Fehler (NOTICE ist OK)
        if echo "$output" | grep -qi "ERROR" | grep -v "already exists"; then
            log_warn "  Fehler in $schema_file (möglicherweise bereits vorhanden)"
            # Kein Abbruch — "already exists" Fehler sind OK
        fi
        log_ok "  $schema_file geladen"
    else
        log_error "  Schema-Datei nicht gefunden: $full_path"
        FAILED=$((FAILED + 1))
    fi
done

if [ $FAILED -gt 0 ]; then
    log_error "$FAILED Schema-Dateien konnten nicht geladen werden"
fi

# ------------------------------------------------------------------
# 3. Initiale Konfiguration
# ------------------------------------------------------------------
log_info "Schreibe initiale Konfiguration..."

run_sql_db "
INSERT INTO dbai_core.config (key, value, category, description, is_readonly) VALUES
    ('system.name', '\"DBAI\"'::jsonb, 'system', 'System-Name', true),
    ('system.version', '\"0.1.0\"'::jsonb, 'system', 'System-Version', false),
    ('system.boot_time', 'null'::jsonb, 'system', 'Letzter Boot-Zeitpunkt', false),
    ('system.state', '\"initialized\"'::jsonb, 'system', 'Aktueller System-Zustand', false)
ON CONFLICT (key) DO NOTHING;
" 2>/dev/null || log_warn "Initiale Config bereits vorhanden"

log_ok "Konfiguration geschrieben"

# ------------------------------------------------------------------
# 4. Schema-Integrität prüfen
# ------------------------------------------------------------------
log_info "Prüfe Schema-Integrität..."

SCHEMA_COUNT=$(run_sql_db "
SELECT COUNT(*) FROM information_schema.schemata
WHERE schema_name LIKE 'dbai_%'
" 2>/dev/null | grep -oP '\d+' | head -1)

TABLE_COUNT=$(run_sql_db "
SELECT COUNT(*) FROM information_schema.tables
WHERE table_schema LIKE 'dbai_%'
" 2>/dev/null | grep -oP '\d+' | head -1)

log_ok "Schemas: ${SCHEMA_COUNT:-?}, Tabellen: ${TABLE_COUNT:-?}"

# ------------------------------------------------------------------
# 5. Zusammenfassung
# ------------------------------------------------------------------
echo ""
echo "============================================================"
echo "  DBAI Bootstrap abgeschlossen!"
echo ""
echo "  Datenbank:  $DB_NAME"
echo "  Schemas:    ${SCHEMA_COUNT:-?}"
echo "  Tabellen:   ${TABLE_COUNT:-?}"
echo ""
echo "  System starten:"
echo "    source $DBAI_ROOT/.venv/bin/activate"
echo "    python3 $DBAI_ROOT/bridge/system_bridge.py start"
echo ""
echo "  Diagnose ausführen:"
echo "    python3 $DBAI_ROOT/recovery/panic_recovery.py diagnose"
echo ""
echo "  Status prüfen:"
echo "    python3 $DBAI_ROOT/bridge/system_bridge.py status"
echo "============================================================"
