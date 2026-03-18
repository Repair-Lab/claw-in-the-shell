#!/usr/bin/env bash
# =============================================================================
# DBAI GhostShell — Sandbox Manager
# =============================================================================
# Steuert die lokale, isolierte Testumgebung.
# Daten bleiben in dev/.sandbox-data/ und landen nie im Git.
#
#   ./dev/sandbox.sh up       — Sandbox starten
#   ./dev/sandbox.sh down     — Stoppen (Daten bleiben)
#   ./dev/sandbox.sh nuke     — Alles löschen (DB + Volumes + Daten)
#   ./dev/sandbox.sh restart  — Neustart
#   ./dev/sandbox.sh psql     — Direkt in die Sandbox-DB
#   ./dev/sandbox.sh logs     — Logs folgen
#   ./dev/sandbox.sh status   — Container-Status anzeigen
#   ./dev/sandbox.sh test-html— index.html im lokalen Testserver öffnen
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.sandbox.yml"
SANDBOX_DATA="$SCRIPT_DIR/.sandbox-data"

# Farben
C="\033[36m"  # Cyan
G="\033[32m"  # Green
R="\033[31m"  # Red
Y="\033[33m"  # Yellow
N="\033[0m"   # Reset

header() {
  echo -e "\n${C}══════════════════════════════════════════════════════${N}"
  echo -e "  ${C}🧪 DBAI Sandbox${N} — $1"
  echo -e "${C}══════════════════════════════════════════════════════${N}\n"
}

case "${1:-help}" in

  up)
    header "Starten"
    mkdir -p "$SANDBOX_DATA/pgdata"
    
    echo -e "${Y}📦 Baue Container...${N}"
    cd "$PROJECT_DIR"
    docker compose -f "$COMPOSE_FILE" up -d --build 2>&1
    
    echo ""
    echo -e "${G}✅ Sandbox läuft!${N}"
    echo ""
    echo -e "  ${C}API:${N}        http://localhost:3100"
    echo -e "  ${C}Dashboard:${N}  http://localhost:5174"
    echo -e "  ${C}PostgreSQL:${N} localhost:5433 (User: admin / PW: dbai2026)"
    echo -e "  ${C}DB-Name:${N}    dbai_sandbox"
    echo ""
    echo -e "  ${Y}Tipp:${N} ./dev/sandbox.sh psql  → Direkt in die DB"
    echo -e "  ${Y}Tipp:${N} ./dev/sandbox.sh logs  → Logs folgen"
    echo ""
    ;;

  down)
    header "Stoppen (Daten bleiben)"
    docker compose -f "$COMPOSE_FILE" down 2>&1
    echo -e "${G}✅ Sandbox gestoppt. Daten in dev/.sandbox-data/ sind erhalten.${N}"
    ;;

  nuke)
    header "☠️  Alles löschen"
    echo -e "${R}WARNUNG: Löscht ALLE Sandbox-Daten (DB, Volumes, Container)!${N}"
    read -p "Sicher? (ja/nein): " confirm
    if [[ "$confirm" == "ja" ]]; then
      docker compose -f "$COMPOSE_FILE" down -v --remove-orphans 2>&1 || true
      rm -rf "$SANDBOX_DATA"
      echo -e "${G}✅ Sandbox komplett gelöscht. Kein Krümel übrig.${N}"
    else
      echo -e "${Y}Abgebrochen.${N}"
    fi
    ;;

  restart)
    header "Neustart"
    docker compose -f "$COMPOSE_FILE" down 2>&1
    mkdir -p "$SANDBOX_DATA/pgdata"
    cd "$PROJECT_DIR"
    docker compose -f "$COMPOSE_FILE" up -d --build 2>&1
    echo -e "${G}✅ Sandbox neugestartet.${N}"
    ;;

  psql)
    header "PostgreSQL Shell"
    PGPASSWORD=dbai2026 psql -h 127.0.0.1 -p 5433 -U admin -d dbai_sandbox
    ;;

  logs)
    header "Logs (Ctrl+C zum Beenden)"
    docker compose -f "$COMPOSE_FILE" logs -f --tail=50
    ;;

  status)
    header "Status"
    docker compose -f "$COMPOSE_FILE" ps
    echo ""
    if [ -d "$SANDBOX_DATA/pgdata" ]; then
      SIZE=$(du -sh "$SANDBOX_DATA" 2>/dev/null | cut -f1)
      echo -e "  ${C}Sandbox-Daten:${N} $SANDBOX_DATA ($SIZE)"
    else
      echo -e "  ${Y}Keine Sandbox-Daten vorhanden.${N}"
    fi
    ;;

  test-html)
    header "index.html Test-Server"
    echo -e "Starte lokalen HTTP-Server für USB-Stick index.html..."
    echo -e "Öffne ${C}http://localhost:8888${N} im Browser."
    echo -e "(Ctrl+C zum Beenden)\n"
    cd "$PROJECT_DIR/recovery/usb"
    python3 -m http.server 8888
    ;;

  help|*)
    header "Hilfe"
    echo "Verwendung: ./dev/sandbox.sh <command>"
    echo ""
    echo "Commands:"
    echo -e "  ${G}up${N}         Sandbox starten (baut Container)"
    echo -e "  ${G}down${N}       Sandbox stoppen (Daten bleiben erhalten)"
    echo -e "  ${R}nuke${N}       Alles löschen (DB + Volumes + lokale Daten)"
    echo -e "  ${G}restart${N}    Neustart (down + up)"
    echo -e "  ${C}psql${N}       PostgreSQL Shell öffnen"
    echo -e "  ${C}logs${N}       Container-Logs folgen"
    echo -e "  ${C}status${N}     Container-Status + Datengröße"
    echo -e "  ${Y}test-html${N}  HTTP-Server für index.html auf :8888"
    echo ""
    echo "Ports:"
    echo -e "  API:        ${C}http://localhost:3100${N}"
    echo -e "  Dashboard:  ${C}http://localhost:5174${N}"
    echo -e "  PostgreSQL: ${C}localhost:5433${N}"
    echo ""
    echo "Daten: dev/.sandbox-data/ (in .gitignore, bleibt lokal)"
    ;;
esac
