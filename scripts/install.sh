#!/usr/bin/env bash
# =============================================================================
# DBAI Installation Script
# Installiert PostgreSQL, Extensions und alle Abhängigkeiten
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DBAI_ROOT="$(dirname "$SCRIPT_DIR")"

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
echo "  DBAI — Tabellenbasiertes KI-Betriebssystem"
echo "  Installation"
echo "============================================================"
echo ""

# ------------------------------------------------------------------
# 1. System-Pakete prüfen und installieren
# ------------------------------------------------------------------
log_info "Prüfe System-Pakete..."

install_packages() {
    if command -v apt-get &>/dev/null; then
        sudo apt-get update -qq
        sudo apt-get install -y -qq \
            postgresql postgresql-contrib \
            postgresql-server-dev-all \
            build-essential gcc make \
            python3 python3-pip python3-venv \
            rsync curl wget
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y \
            postgresql-server postgresql-contrib \
            postgresql-devel \
            gcc make \
            python3 python3-pip \
            rsync curl wget
    elif command -v pacman &>/dev/null; then
        sudo pacman -Sy --noconfirm \
            postgresql \
            gcc make \
            python python-pip \
            rsync curl wget
    else
        log_error "Kein unterstützter Paketmanager gefunden (apt/dnf/pacman)"
        exit 1
    fi
}

# PostgreSQL prüfen
if ! command -v psql &>/dev/null; then
    log_warn "PostgreSQL nicht gefunden — installiere..."
    install_packages
else
    PG_VERSION=$(psql --version | grep -oP '\d+' | head -1)
    log_ok "PostgreSQL $PG_VERSION gefunden"
fi

# gcc prüfen
if ! command -v gcc &>/dev/null; then
    log_warn "gcc nicht gefunden — installiere..."
    install_packages
else
    log_ok "gcc gefunden"
fi

# Python prüfen
if ! command -v python3 &>/dev/null; then
    log_error "Python 3 nicht gefunden!"
    exit 1
else
    PY_VERSION=$(python3 --version)
    log_ok "$PY_VERSION gefunden"
fi

# ------------------------------------------------------------------
# 2. pgvector Extension installieren
# ------------------------------------------------------------------
log_info "Prüfe pgvector Extension..."

if psql -U postgres -d postgres -c "CREATE EXTENSION IF NOT EXISTS vector" 2>/dev/null; then
    log_ok "pgvector verfügbar"
else
    log_warn "pgvector nicht installiert — kompiliere aus Source..."
    TEMP_DIR=$(mktemp -d)
    cd "$TEMP_DIR"
    git clone --branch v0.7.4 https://github.com/pgvector/pgvector.git 2>/dev/null || true
    if [ -d pgvector ]; then
        cd pgvector
        make
        sudo make install
        log_ok "pgvector installiert"
    else
        log_warn "pgvector konnte nicht installiert werden (git nicht verfügbar?)"
    fi
    cd "$DBAI_ROOT"
    rm -rf "$TEMP_DIR"
fi

# ------------------------------------------------------------------
# 3. Python Virtual Environment
# ------------------------------------------------------------------
log_info "Erstelle Python Virtual Environment..."

VENV_DIR="$DBAI_ROOT/.venv"
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    log_ok "Virtual Environment erstellt: $VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

log_info "Installiere Python-Abhängigkeiten..."
pip install --quiet --upgrade pip
pip install --quiet -r "$DBAI_ROOT/requirements.txt"
log_ok "Python-Abhängigkeiten installiert"

# ------------------------------------------------------------------
# 4. C-Bindings kompilieren
# ------------------------------------------------------------------
log_info "Kompiliere C-Bindings..."

cd "$DBAI_ROOT/bridge/c_bindings"
if make; then
    log_ok "C-Bindings kompiliert: libhw_interrupts.so"
else
    log_warn "C-Bindings Kompilierung fehlgeschlagen (nicht kritisch)"
fi
cd "$DBAI_ROOT"

# ------------------------------------------------------------------
# 5. Verzeichnisse erstellen
# ------------------------------------------------------------------
log_info "Erstelle Verzeichnisse..."

mkdir -p /tmp/dbai_wal_archive
mkdir -p /tmp/dbai_pitr
mkdir -p /tmp/dbai_mirror_1
mkdir -p /tmp/dbai_mirror_2
log_ok "Verzeichnisse erstellt (temporär unter /tmp)"

# ------------------------------------------------------------------
# 6. PostgreSQL Konfiguration
# ------------------------------------------------------------------
log_info "PostgreSQL wird konfiguriert..."

# Prüfe ob PostgreSQL läuft
if pg_isready -q 2>/dev/null; then
    log_ok "PostgreSQL läuft"
else
    log_warn "PostgreSQL läuft nicht — versuche zu starten..."
    if sudo systemctl start postgresql 2>/dev/null; then
        log_ok "PostgreSQL gestartet"
    elif pg_ctlcluster $(pg_lsclusters -h | head -1 | awk '{print $1, $2}') start 2>/dev/null; then
        log_ok "PostgreSQL gestartet (pg_ctlcluster)"
    else
        log_error "PostgreSQL konnte nicht gestartet werden"
        log_info "Bitte starte PostgreSQL manuell und führe dann bootstrap.sh aus"
    fi
fi

echo ""
echo "============================================================"
echo "  Installation abgeschlossen!"
echo ""
echo "  Nächster Schritt:"
echo "    bash $DBAI_ROOT/scripts/bootstrap.sh"
echo "============================================================"
