#!/bin/bash
# =============================================================================
# DBAI Security Cron — Automatisierte Scans
# =============================================================================
# Wird im Kali-Sidecar-Container per Cron ausgeführt.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="/var/log/dbai/security-cron.log"
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# ─── Cron-Jobs einrichten ─────────────────────────────────────
setup_cron() {
    log "Richte Security-Cron-Jobs ein…"
    
    cat > /etc/cron.d/dbai-security << 'CRON'
# DBAI Security-Immunsystem — Automatische Scans
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# SQLMap Self-Penetration: Jede Stunde
0 * * * * root python3 /app/security_immunsystem.py --scan sqlmap >> /var/log/dbai/sqlmap.log 2>&1

# Nmap Port-Scan: Alle 30 Minuten
*/30 * * * * root python3 /app/security_immunsystem.py --scan nmap >> /var/log/dbai/nmap.log 2>&1

# Nuclei Web-Scan: Alle 2 Stunden
0 */2 * * * root python3 /app/security_immunsystem.py --scan nuclei >> /var/log/dbai/nuclei.log 2>&1

# Security-Baseline: Täglich um 03:00
0 3 * * * root python3 /app/security_immunsystem.py --scan baseline >> /var/log/dbai/baseline.log 2>&1

# Suricata Regeln updaten: Täglich um 02:00
0 2 * * * root suricata-update && systemctl reload suricata 2>/dev/null || true

# Fail2Ban Status-Check: Alle 5 Minuten
*/5 * * * * root fail2ban-client status >> /var/log/dbai/fail2ban-status.log 2>&1

# Log-Rotation: Täglich
0 0 * * * root find /var/log/dbai/ -name "*.log" -mtime +30 -delete 2>/dev/null || true
CRON

    chmod 644 /etc/cron.d/dbai-security
    log "Cron-Jobs eingerichtet."
}

# ─── Initiale Checks ─────────────────────────────────────────
initial_checks() {
    log "═══ Initiale Security-Checks ═══"
    
    # Tools prüfen
    for tool in sqlmap nmap nuclei suricata fail2ban-client lynis sslscan; do
        if command -v "$tool" &> /dev/null; then
            log "✓ $tool verfügbar"
        else
            log "✗ $tool NICHT verfügbar"
        fi
    done
    
    # DB-Verbindung prüfen
    if psql -h "${DBAI_DB_HOST:-postgres}" -U "${DBAI_DB_USER:-dbai_system}" \
       -d "${DBAI_DB_NAME:-dbai}" -c "SELECT 1" &> /dev/null; then
        log "✓ PostgreSQL-Verbindung OK"
    else
        log "✗ PostgreSQL-Verbindung FEHLGESCHLAGEN"
        exit 1
    fi
    
    # Security-Schema prüfen
    SCHEMA_EXISTS=$(psql -h "${DBAI_DB_HOST:-postgres}" -U "${DBAI_DB_USER:-dbai_system}" \
        -d "${DBAI_DB_NAME:-dbai}" -t -A -c \
        "SELECT EXISTS(SELECT 1 FROM pg_namespace WHERE nspname = 'dbai_security')")
    
    if [ "$SCHEMA_EXISTS" = "t" ]; then
        log "✓ Security-Schema vorhanden"
    else
        log "✗ Security-Schema FEHLT — führe Migration aus…"
        psql -h "${DBAI_DB_HOST:-postgres}" -U "${DBAI_DB_USER:-dbai_system}" \
            -d "${DBAI_DB_NAME:-dbai}" -f /app/schema/73-security-immunsystem.sql
    fi
}

# ─── Start ────────────────────────────────────────────────────
case "${1:-setup}" in
    setup)
        initial_checks
        setup_cron
        ;;
    check)
        initial_checks
        ;;
    *)
        echo "Usage: $0 {setup|check}"
        exit 1
        ;;
esac
