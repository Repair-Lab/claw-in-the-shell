#!/usr/bin/env bash
# =============================================================================
# DBAI Development Environment — venv Setup
# =============================================================================
# Erstellt eine isolierte Python-Umgebung, kompiliert C-Bindings,
# installiert Abhängigkeiten und konfiguriert die Umgebung.
#
# Nutzung:
#   ./dev/setup_venv.sh            # Standard-Setup
#   ./dev/setup_venv.sh --reset    # venv neu erstellen
#   ./dev/setup_venv.sh --minimal  # Nur Python-Deps, keine C-Bindings
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$PROJECT_ROOT/.venv"
PYTHON="${PYTHON:-python3}"
RESET=false
MINIMAL=false

# Farben
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${CYAN}[DBAI-venv]${NC} $1"; }
ok()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn(){ echo -e "${YELLOW}[!]${NC} $1"; }
err() { echo -e "${RED}[✗]${NC} $1" >&2; }

# ─── Args ────────────────────────────────────────────────────
for arg in "$@"; do
    case "$arg" in
        --reset)   RESET=true ;;
        --minimal) MINIMAL=true ;;
        --help|-h) echo "Usage: $0 [--reset] [--minimal]"; exit 0 ;;
    esac
done

# ─── Voraussetzungen ────────────────────────────────────────
log "Prüfe Voraussetzungen..."

if ! command -v "$PYTHON" &>/dev/null; then
    err "Python3 nicht gefunden. Bitte installieren: sudo apt install python3 python3-venv"
    exit 1
fi

PY_VERSION=$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [[ "$PY_MAJOR" -lt 3 ]] || [[ "$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 10 ]]; then
    err "Python >= 3.10 erforderlich (gefunden: $PY_VERSION)"
    exit 1
fi
ok "Python $PY_VERSION"

# prüfe ob python3-venv installiert ist
if ! "$PYTHON" -m venv --help &>/dev/null 2>&1; then
    warn "python3-venv nicht installiert — versuche Installation..."
    if command -v apt &>/dev/null; then
        sudo apt-get update -qq && sudo apt-get install -y -qq python3-venv
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y python3-venv
    else
        err "Kann python3-venv nicht installieren. Bitte manuell installieren."
        exit 1
    fi
fi

# ─── venv erstellen ─────────────────────────────────────────
if [[ "$RESET" == "true" ]] && [[ -d "$VENV_DIR" ]]; then
    warn "Lösche bestehendes venv..."
    rm -rf "$VENV_DIR"
fi

if [[ ! -d "$VENV_DIR" ]]; then
    log "Erstelle Python Virtual Environment..."
    "$PYTHON" -m venv "$VENV_DIR"
    ok "venv erstellt: $VENV_DIR"
else
    ok "venv existiert bereits: $VENV_DIR"
fi

# Aktivieren
source "$VENV_DIR/bin/activate"
ok "venv aktiviert"

# ─── pip upgraden ────────────────────────────────────────────
log "Aktualisiere pip + setuptools..."
pip install --upgrade pip setuptools wheel --quiet
ok "pip $(pip --version | awk '{print $2}')"

# ─── Python-Abhängigkeiten ──────────────────────────────────
log "Installiere Python-Abhängigkeiten..."
if [[ -f "$PROJECT_ROOT/requirements.txt" ]]; then
    pip install -r "$PROJECT_ROOT/requirements.txt" --quiet 2>&1 | tail -5 || {
        warn "Einige Pakete konnten nicht installiert werden (nicht-kritisch)"
    }
    ok "requirements.txt installiert"
else
    warn "requirements.txt nicht gefunden"
fi

# Zusätzliche Dev-Abhängigkeiten
log "Installiere Dev-Abhängigkeiten..."
pip install --quiet \
    pytest \
    pytest-asyncio \
    httpx \
    black \
    ruff \
    mypy \
    2>&1 | tail -3 || true
ok "Dev-Tools installiert"

# ─── C-Bindings kompilieren ─────────────────────────────────
if [[ "$MINIMAL" != "true" ]]; then
    C_DIR="$PROJECT_ROOT/bridge/c_bindings"
    if [[ -f "$C_DIR/Makefile" ]]; then
        log "Kompiliere C-Bindings..."
        if command -v gcc &>/dev/null; then
            (cd "$C_DIR" && make clean && make) 2>&1 | tail -5
            if [[ -f "$C_DIR/libhw_interrupts.so" ]]; then
                ok "libhw_interrupts.so kompiliert"
            else
                warn "C-Bindings konnten nicht kompiliert werden"
            fi
        else
            warn "gcc nicht installiert — C-Bindings übersprungen"
            warn "  Installation: sudo apt install build-essential"
        fi
    fi
fi

# ─── .env Datei ─────────────────────────────────────────────
ENV_FILE="$PROJECT_ROOT/.env"
if [[ ! -f "$ENV_FILE" ]]; then
    log "Erstelle .env aus .env.example..."
    if [[ -f "$PROJECT_ROOT/.env.example" ]]; then
        cp "$PROJECT_ROOT/.env.example" "$ENV_FILE"
        ok ".env erstellt (bitte Werte anpassen)"
    else
        cat > "$ENV_FILE" << 'ENVEOF'
# DBAI Ghost OS — Lokale Entwicklungsumgebung
DBAI_DB_HOST=127.0.0.1
DBAI_DB_PORT=5432
DBAI_DB_NAME=dbai
DBAI_DB_USER=dbai_system
DBAI_DB_PASSWORD=
DBAI_RUNTIME_USER=dbai_runtime
DBAI_RUNTIME_PASSWORD=dbai_runtime_2026
DBAI_SECRET_KEY=dev-secret-key-change-in-production
DBAI_LOG_LEVEL=DEBUG
DBAI_ENV=development
ENVEOF
        ok ".env erstellt (Standardwerte)"
    fi
else
    ok ".env existiert bereits"
fi

# ─── Datenbank prüfen ───────────────────────────────────────
log "Prüfe PostgreSQL-Verbindung..."
if command -v pg_isready &>/dev/null; then
    DB_HOST="${DBAI_DB_HOST:-127.0.0.1}"
    DB_PORT="${DBAI_DB_PORT:-5432}"
    if pg_isready -h "$DB_HOST" -p "$DB_PORT" -q 2>/dev/null; then
        ok "PostgreSQL erreichbar ($DB_HOST:$DB_PORT)"
    else
        warn "PostgreSQL nicht erreichbar — ignoriert (Docker?)"
    fi
else
    warn "pg_isready nicht verfügbar — DB-Check übersprungen"
fi

# ─── Zusammenfassung ────────────────────────────────────────
echo ""
echo -e "${GREEN}════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  DBAI Dev-Umgebung bereit!${NC}"
echo -e "${GREEN}════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${CYAN}Aktivieren:${NC}  source .venv/bin/activate"
echo -e "  ${CYAN}Server:${NC}      python web/server.py"
echo -e "  ${CYAN}Tests:${NC}       pytest tests/"
echo -e "  ${CYAN}Frontend:${NC}    cd frontend && npm run dev"
echo -e "  ${CYAN}Simulator:${NC}   python dev/qemu/hw_simulator.py"
echo -e "  ${CYAN}Docker:${NC}      docker compose up -d"
echo ""
echo -e "  ${YELLOW}Hinweis:${NC} .env prüfen + ggf. DB-Passwort setzen"
echo ""
