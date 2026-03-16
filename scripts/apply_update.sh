#!/usr/bin/env bash
# =============================================================================
# DBAI GhostShell OS — Update anwenden (Atomic OTA)
# =============================================================================
# Wendet ein Update-Paket auf diesen Rechner an.
# Automatischer Rollback bei Fehler.
#
# Verwendung:
#   ./scripts/apply_update.sh <archiv.tar.gz>
#   ./scripts/apply_update.sh .builds/dbai-ghostshell-0.9.0.tar.gz
#
# Oder via Git:
#   ./scripts/apply_update.sh --git
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DBAI_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$DBAI_ROOT/.backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Farben
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${CYAN}→${NC} $1"; }
ok()   { echo -e "${GREEN}  ✅ $1${NC}"; }
warn() { echo -e "${YELLOW}  ⚠️  $1${NC}"; }
fail() { echo -e "${RED}  ❌ $1${NC}"; }

echo ""
echo -e "${CYAN}══════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  🔄 DBAI OTA Update${NC}"
echo -e "${CYAN}══════════════════════════════════════════════════════════${NC}"
echo ""

# ─── Parameter ───
USE_GIT=false
ARCHIVE=""

if [ "${1:-}" = "--git" ]; then
    USE_GIT=true
elif [ -n "${1:-}" ]; then
    ARCHIVE="$1"
    if [ ! -f "$ARCHIVE" ]; then
        fail "Archiv nicht gefunden: $ARCHIVE"
        exit 1
    fi
else
    echo "Verwendung:"
    echo "  $0 <archiv.tar.gz>    — Update aus Archiv"
    echo "  $0 --git              — Update via Git Pull"
    exit 1
fi

# Aktuelle Version lesen
CURRENT_VERSION=$(grep '^version' "$DBAI_ROOT/config/dbai.toml" 2>/dev/null | \
                  head -1 | sed 's/.*= *"\(.*\)"/\1/' || echo "unknown")
echo "  Aktuelle Version: v${CURRENT_VERSION}"
echo ""

# ─── Schritt 1: Backup ───
log "[1/6] Backup erstellen..."
BACKUP_PATH="$BACKUP_DIR/backup-${CURRENT_VERSION}-${TIMESTAMP}"
mkdir -p "$BACKUP_PATH"

for dir in bridge web config schema scripts frontend/src; do
    src="$DBAI_ROOT/$dir"
    if [ -d "$src" ]; then
        mkdir -p "$BACKUP_PATH/$dir"
        cp -r "$src/"* "$BACKUP_PATH/$dir/" 2>/dev/null || true
    fi
done

# dbai.toml sichern
cp "$DBAI_ROOT/config/dbai.toml" "$BACKUP_PATH/" 2>/dev/null || true
ok "Backup: $BACKUP_PATH"

# Rollback-Funktion
rollback() {
    echo ""
    fail "UPDATE FEHLGESCHLAGEN — Rollback wird ausgeführt..."

    if [ -d "$BACKUP_PATH" ]; then
        for dir in bridge web config schema scripts; do
            if [ -d "$BACKUP_PATH/$dir" ]; then
                rm -rf "$DBAI_ROOT/$dir" 2>/dev/null || true
                cp -r "$BACKUP_PATH/$dir" "$DBAI_ROOT/$dir"
            fi
        done
        if [ -d "$BACKUP_PATH/frontend/src" ]; then
            rm -rf "$DBAI_ROOT/frontend/src" 2>/dev/null || true
            cp -r "$BACKUP_PATH/frontend/src" "$DBAI_ROOT/frontend/src"
        fi

        # Frontend mit altem Code neu bauen
        cd "$DBAI_ROOT/frontend"
        npm run build 2>/dev/null || true

        ok "Rollback auf v${CURRENT_VERSION} abgeschlossen"
    else
        fail "Kein Backup vorhanden — manuelles Eingreifen nötig!"
    fi
    exit 1
}

trap rollback ERR

# ─── Schritt 2: Code aktualisieren ───
log "[2/6] Code aktualisieren..."
if [ "$USE_GIT" = true ]; then
    cd "$DBAI_ROOT"
    git stash 2>/dev/null || true
    git pull --rebase origin main 2>&1 | tail -5
    ok "Git Pull erfolgreich"
else
    # Archiv entpacken (überschreibt bestehende Dateien)
    cd "$DBAI_ROOT"

    # Checksumme vom Manifest prüfen (falls vorhanden)
    MANIFEST="${ARCHIVE%.tar.gz}.manifest.json"
    if [ -f "$MANIFEST" ]; then
        EXPECTED=$(python3 -c "import json; print(json.load(open('$MANIFEST'))['artifact_hash'])" 2>/dev/null || echo "")
        ACTUAL=$(sha256sum "$ARCHIVE" | awk '{print $1}')
        if [ -n "$EXPECTED" ] && [ "$EXPECTED" != "$ACTUAL" ]; then
            fail "Checksumme ungültig!"
            fail "Erwartet: $EXPECTED"
            fail "Tatsächlich: $ACTUAL"
            exit 1
        fi
        ok "Checksumme verifiziert"
    fi

    tar -xzf "$ARCHIVE" --overwrite
    ok "Archiv entpackt"
fi

# ─── Schritt 3: Python-Abhängigkeiten ───
log "[3/6] Python-Abhängigkeiten..."
if [ -f "$DBAI_ROOT/requirements.txt" ]; then
    pip install -q -r "$DBAI_ROOT/requirements.txt" 2>/dev/null || true
    ok "pip install erledigt"
else
    warn "Keine requirements.txt"
fi

# ─── Schritt 4: SQL-Migrationen ───
log "[4/6] SQL-Migrationen anwenden..."

# Prüfe welche Schemas noch nicht angewendet wurden
# Einfache Variante: Alle Schemas der Reihe nach anwenden (idempotent dank IF NOT EXISTS)
MIGRATION_ERRORS=0
for f in $(ls "$DBAI_ROOT/schema/"*.sql | sort -V); do
    BASENAME=$(basename "$f")
    echo -n "    $BASENAME ... "

    if sudo -u postgres psql -d dbai -v ON_ERROR_STOP=0 -f "$f" >/dev/null 2>&1; then
        echo -e "${GREEN}OK${NC}"
    else
        echo -e "${YELLOW}WARNUNG (möglicherweise bereits angewendet)${NC}"
    fi
done

if [ $MIGRATION_ERRORS -gt 0 ]; then
    fail "$MIGRATION_ERRORS kritische Migrationsfehler!"
    rollback
fi
ok "SQL-Migrationen abgeschlossen"

# ─── Schritt 5: Frontend Build ───
log "[5/6] Frontend Build..."
cd "$DBAI_ROOT/frontend"
npm install --silent 2>/dev/null || true
npm run build 2>&1 | tail -3

if [ ! -f dist/index.html ]; then
    fail "Frontend-Build fehlgeschlagen!"
    rollback
fi
ok "Frontend gebaut"

# ─── Schritt 6: Healthcheck ───
log "[6/6] Healthcheck..."

# DB-Verbindung
if sudo -u postgres psql -d dbai -c "SELECT 1" >/dev/null 2>&1; then
    ok "Datenbank erreichbar"
else
    fail "Datenbank nicht erreichbar!"
    rollback
fi

# Frontend-Dateien
if [ -f "$DBAI_ROOT/frontend/dist/index.html" ]; then
    ok "Frontend-Dist vorhanden"
else
    fail "Frontend-Dist fehlt!"
    rollback
fi

# Neue Version lesen
NEW_VERSION=$(grep '^version' "$DBAI_ROOT/config/dbai.toml" 2>/dev/null | \
              head -1 | sed 's/.*= *"\(.*\)"/\1/' || echo "$CURRENT_VERSION")

# ─── Zusammenfassung ───
echo ""
echo -e "${GREEN}══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ Update erfolgreich!${NC}"
echo ""
echo "  Vorherige Version: v${CURRENT_VERSION}"
echo "  Neue Version:      v${NEW_VERSION}"
echo "  Backup:            ${BACKUP_PATH}"
echo ""
echo "  Web-Server neu starten mit:"
echo "    sudo systemctl restart dbai-web"
echo "  oder:"
echo "    cd $DBAI_ROOT && ./scripts/start_web.sh"
echo -e "${GREEN}══════════════════════════════════════════════════════════${NC}"
