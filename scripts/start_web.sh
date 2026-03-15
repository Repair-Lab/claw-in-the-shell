#!/usr/bin/env bash
# =============================================================================
# DBAI Web-Server Startscript
# Startet FastAPI Backend + Ghost Dispatcher
# =============================================================================

set -euo pipefail

DBAI_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$DBAI_ROOT/logs"
PID_DIR="$DBAI_ROOT/run"

# Farben
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
PURPLE='\033[0;35m'
NC='\033[0m'

log_info()  { echo -e "${CYAN}[DBAI-WEB]${NC} $1"; }
log_ok()    { echo -e "${GREEN}[✓]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }
log_ghost() { echo -e "${PURPLE}[👻]${NC} $1"; }

# Verzeichnisse erstellen
mkdir -p "$LOG_DIR" "$PID_DIR"

# =============================================================================
# Konfiguration
# =============================================================================
WEB_HOST="${DBAI_WEB_HOST:-0.0.0.0}"
WEB_PORT="${DBAI_WEB_PORT:-8420}"
DB_NAME="${DBAI_DB_NAME:-dbai}"
DB_HOST="${DBAI_DB_HOST:-127.0.0.1}"
DB_PORT="${DBAI_DB_PORT:-5432}"

export DBAI_DB_NAME="$DB_NAME"
export DBAI_DB_HOST="$DB_HOST"
export DBAI_DB_PORT="$DB_PORT"

# =============================================================================
# Funktionen
# =============================================================================

check_dependencies() {
    log_info "Prüfe Abhängigkeiten..."

    # Python
    if ! command -v python3 &>/dev/null; then
        log_error "python3 nicht gefunden"
        exit 1
    fi

    # FastAPI
    if ! python3 -c "import fastapi" 2>/dev/null; then
        log_error "FastAPI nicht installiert. Bitte: pip install fastapi uvicorn"
        exit 1
    fi

    # psycopg2
    if ! python3 -c "import psycopg2" 2>/dev/null; then
        log_error "psycopg2 nicht installiert. Bitte: pip install psycopg2-binary"
        exit 1
    fi

    log_ok "Alle Abhängigkeiten vorhanden"
}

check_database() {
    log_info "Prüfe Datenbankverbindung..."
    if pg_isready -h "$DB_HOST" -p "$DB_PORT" -d "$DB_NAME" &>/dev/null; then
        log_ok "PostgreSQL erreichbar ($DB_HOST:$DB_PORT/$DB_NAME)"
    else
        log_error "PostgreSQL nicht erreichbar auf $DB_HOST:$DB_PORT"
        log_info "Bitte PostgreSQL starten: sudo systemctl start postgresql"
        exit 1
    fi
}

start_ghost_dispatcher() {
    log_ghost "Starte Ghost Dispatcher..."
    python3 "$DBAI_ROOT/web/ghost_dispatcher.py" \
        > "$LOG_DIR/ghost_dispatcher.log" 2>&1 &
    echo $! > "$PID_DIR/ghost_dispatcher.pid"
    log_ok "Ghost Dispatcher gestartet (PID: $(cat "$PID_DIR/ghost_dispatcher.pid"))"
}

start_web_server() {
    log_info "Starte DBAI Web-Server auf $WEB_HOST:$WEB_PORT..."
    python3 -m uvicorn web.server:app \
        --host "$WEB_HOST" \
        --port "$WEB_PORT" \
        --log-level info \
        --app-dir "$DBAI_ROOT" \
        > "$LOG_DIR/web_server.log" 2>&1 &
    echo $! > "$PID_DIR/web_server.pid"
    log_ok "Web-Server gestartet (PID: $(cat "$PID_DIR/web_server.pid"))"
}

stop_all() {
    log_info "Stoppe DBAI Web-Services..."

    for service in web_server ghost_dispatcher; do
        pidfile="$PID_DIR/${service}.pid"
        if [ -f "$pidfile" ]; then
            pid=$(cat "$pidfile")
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid"
                log_ok "$service gestoppt (PID: $pid)"
            fi
            rm -f "$pidfile"
        fi
    done
}

status() {
    echo ""
    echo "╔══════════════════════════════════════════╗"
    echo "║     DBAI Web-Services Status             ║"
    echo "╠══════════════════════════════════════════╣"

    for service in web_server ghost_dispatcher; do
        pidfile="$PID_DIR/${service}.pid"
        if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
            echo -e "║  ${GREEN}●${NC} $service (PID: $(cat "$pidfile"))     "
        else
            echo -e "║  ${RED}●${NC} $service (nicht aktiv)            "
        fi
    done

    echo "╠══════════════════════════════════════════╣"
    echo "║  Web-UI:  http://localhost:$WEB_PORT          ║"
    echo "║  API:     http://localhost:$WEB_PORT/api      ║"
    echo "╚══════════════════════════════════════════╝"
    echo ""
}

# =============================================================================
# CLI
# =============================================================================

case "${1:-start}" in
    start)
        echo ""
        echo "  ╔═══════════════════════════════════════╗"
        echo "  ║   👻 DBAI — Ghost in the Database 👻  ║"
        echo "  ║         Web-Server v0.3.0              ║"
        echo "  ╚═══════════════════════════════════════╝"
        echo ""
        check_dependencies
        check_database
        start_ghost_dispatcher
        sleep 1
        start_web_server
        sleep 1
        echo ""
        log_ok "DBAI Web-System bereit!"
        echo ""
        echo "  🌐 Web-UI:  http://localhost:$WEB_PORT"
        echo "  📡 API:     http://localhost:$WEB_PORT/api"
        echo "  🔌 WS:      ws://localhost:$WEB_PORT/ws"
        echo ""
        echo "  Logs: $LOG_DIR/"
        echo "  Stoppen: $0 stop"
        echo ""
        ;;
    stop)
        stop_all
        ;;
    restart)
        stop_all
        sleep 2
        exec "$0" start
        ;;
    status)
        status
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
