#!/usr/bin/env python3
"""
DBAI Security-Immunsystem — Rückkopplungsschleife zur Selbstregulierung
========================================================================
GhostShell OS schützt sich selbst durch:

1. Automatisierte Penetrationstests (SQLMap, Nmap, Nuclei, Nikto)
2. Intrusion Detection (Suricata)
3. Fail2Ban mit PostgreSQL-Log-Verknüpfung
4. Netzwerk-Firewall-Management (iptables/nftables)
5. Threat-Intelligence-Feeds
6. Honeypot-Service
7. TLS-Zertifikats-Überwachung
8. DNS-Sinkhole
9. Security-Baseline-Audits (Lynis)
10. CVE-Tracking für installierte Pakete

Rückkopplungsschleife:
  Scan → Finding → Auto-Mitigation → Firewall-Update → Erneuter Scan
  
Dieses Modul läuft im Kali-Sidecar-Container UND wird vom
ghost-api Container als Bridge-Modul importiert.
"""

import os
import sys
import json
import time
import socket
import signal
import logging
import hashlib
import subprocess
import threading
import ipaddress
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

import psycopg2
from psycopg2.extras import RealDictCursor, Json, execute_values

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("dbai.security")

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------
DB_CONFIG = {
    "host": os.getenv("DBAI_DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DBAI_DB_PORT", "5432")),
    "dbname": os.getenv("DBAI_DB_NAME", "dbai"),
    "user": os.getenv("DBAI_DB_USER", "dbai_system"),
    "password": os.getenv("DBAI_DB_PASSWORD", ""),
}

# Netzwerk-Konfiguration
INTERNAL_SUBNET = os.getenv("DBAI_INTERNAL_SUBNET", "172.28.0.0/16")
TRUSTED_IPS = os.getenv("DBAI_TRUSTED_IPS", "127.0.0.1,::1").split(",")
API_BASE_URL = os.getenv("DBAI_API_URL", "http://ghost-api:3000")
ROUTER_IP = os.getenv("DBAI_ROUTER_IP", "192.168.1.1")

# Scan-Intervalle (Sekunden)
SQLMAP_INTERVAL = int(os.getenv("DBAI_SQLMAP_INTERVAL", "3600"))      # 1 Stunde
NMAP_INTERVAL = int(os.getenv("DBAI_NMAP_INTERVAL", "1800"))          # 30 Minuten
BASELINE_INTERVAL = int(os.getenv("DBAI_BASELINE_INTERVAL", "86400")) # 24 Stunden
METRICS_INTERVAL = int(os.getenv("DBAI_METRICS_INTERVAL", "300"))     # 5 Minuten
CLEANUP_INTERVAL = int(os.getenv("DBAI_CLEANUP_INTERVAL", "600"))     # 10 Minuten
TLS_CHECK_INTERVAL = int(os.getenv("DBAI_TLS_CHECK_INTERVAL", "43200"))  # 12 Stunden

# Fail2Ban Schwellen
F2B_MAX_ATTEMPTS = int(os.getenv("DBAI_F2B_MAX_ATTEMPTS", "3"))
F2B_WINDOW_MINUTES = int(os.getenv("DBAI_F2B_WINDOW_MINUTES", "5"))
F2B_BAN_HOURS = int(os.getenv("DBAI_F2B_BAN_HOURS", "24"))


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class ScanType(str, Enum):
    SQLMAP = "sqlmap"
    NMAP = "nmap"
    NIKTO = "nikto"
    NUCLEI = "nuclei"
    SSL_CHECK = "ssl_check"
    PORT_SCAN = "port_scan"
    CONFIG_AUDIT = "config_audit"
    DEPENDENCY_AUDIT = "dependency_audit"
    LYNIS = "lynis"
    CUSTOM = "custom"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class ScanResult:
    """Ergebnis eines einzelnen Scan-Findings."""
    severity: str
    category: str
    title: str
    description: str = ""
    affected_target: str = ""
    affected_param: str = ""
    evidence: str = ""
    cve_id: str = ""
    cvss_score: float = 0.0
    tool_output: dict = field(default_factory=dict)
    remediation: str = ""


# ===========================================================================
# HAUPTKLASSE: Security-Immunsystem
# ===========================================================================
class SecurityImmunsystem:
    """
    Das Immunsystem von GhostShell OS.
    Koordiniert alle Security-Module und die Rückkopplungsschleife.
    """

    def __init__(self, db_config: dict = None):
        self.db_config = db_config or DB_CONFIG
        self.conn: Optional[psycopg2.extensions.connection] = None
        self._shutdown = threading.Event()
        self._threads: List[threading.Thread] = []

        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum, frame):
        logger.info("Signal %s — Security-Immunsystem fährt herunter…", signum)
        self._shutdown.set()

    # ------------------------------------------------------------------
    # Datenbankverbindung
    # ------------------------------------------------------------------
    def _get_conn(self) -> psycopg2.extensions.connection:
        """Thread-sichere DB-Verbindung."""
        if self.conn is None or self.conn.closed:
            self.conn = psycopg2.connect(**self.db_config)
            self.conn.autocommit = True
        return self.conn

    def _get_cursor(self) -> RealDictCursor:
        conn = self._get_conn()
        return conn.cursor(cursor_factory=RealDictCursor)

    def _execute(self, sql: str, params=None) -> List[dict]:
        """SQL ausführen und Ergebnisse als Liste von Dicts zurückgeben."""
        with self._get_cursor() as cur:
            cur.execute(sql, params)
            if cur.description:
                return cur.fetchall()
            return []

    # ==================================================================
    # 1. SQLMap Self-Penetration
    # ==================================================================
    def run_sqlmap_scan(self, target_url: str = None, endpoints: List[str] = None) -> List[ScanResult]:
        """
        Startet SQLMap gegen eigene API-Endpunkte.
        Ergebnisse werden in vulnerability_findings gespeichert.
        """
        logger.info("═══ SQLMap Self-Penetration gestartet ═══")

        if target_url is None:
            target_url = API_BASE_URL

        # Standard-Endpunkte die getestet werden
        if endpoints is None:
            endpoints = self._discover_api_endpoints()

        # Scan-Job anlegen
        job_id = self._create_scan_job("sqlmap", target_url, "api")
        results = []

        for endpoint in endpoints:
            url = f"{target_url}{endpoint}"
            logger.info("SQLMap testet: %s", url)

            try:
                cmd = [
                    "sqlmap",
                    "-u", url,
                    "--batch",               # Nicht-interaktiv
                    "--random-agent",         # User-Agent randomisieren
                    "--level", "3",           # Testtiefe
                    "--risk", "2",            # Risiko (2 = medium, kein DROP)
                    "--threads", "4",
                    "--timeout", "30",
                    "--retries", "2",
                    "--output-dir", "/tmp/sqlmap_output",
                    "--flush-session",
                    "--forms",               # Auch Formulare testen
                    "--crawl=2",             # 2 Ebenen tief crawlen
                    "--tamper=space2comment", # WAF-Bypass-Versuch
                    "--technique=BEUSTQ",     # Alle Injection-Techniken
                ]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 Minuten Timeout pro Endpoint
                )

                findings = self._parse_sqlmap_output(result.stdout, result.stderr, url)
                results.extend(findings)

            except subprocess.TimeoutExpired:
                logger.warning("SQLMap Timeout für %s", url)
            except FileNotFoundError:
                logger.error("sqlmap nicht installiert — überspringe")
                break
            except Exception as e:
                logger.error("SQLMap Fehler für %s: %s", url, e)

        # Ergebnisse in DB speichern
        findings_count = self._store_findings(job_id, results)
        self._complete_scan_job(job_id, findings_count)

        logger.info("═══ SQLMap abgeschlossen: %d Findings ═══", findings_count)
        return results

    def _parse_sqlmap_output(self, stdout: str, stderr: str, target: str) -> List[ScanResult]:
        """Parst SQLMap-Ausgabe und extrahiert Findings."""
        findings = []

        # SQLMap-spezifische Muster erkennen
        injection_patterns = [
            ("sql_injection", "Parameter.*is vulnerable", Severity.CRITICAL),
            ("sql_injection", "injectable", Severity.HIGH),
            ("sql_injection", "blind SQL injection", Severity.HIGH),
            ("sql_injection", "time-based blind", Severity.HIGH),
            ("sql_injection", "UNION query", Severity.CRITICAL),
            ("sql_injection", "error-based", Severity.HIGH),
            ("sql_injection", "stacked queries", Severity.CRITICAL),
        ]

        output = stdout + stderr
        for category, pattern, severity in injection_patterns:
            if pattern.lower() in output.lower():
                param = ""
                # Parameter extrahieren
                for line in output.split("\n"):
                    if "parameter" in line.lower() and "vulnerable" in line.lower():
                        param = line.strip()
                        break

                findings.append(ScanResult(
                    severity=severity.value,
                    category=category,
                    title=f"SQL-Injection gefunden: {pattern}",
                    description=f"SQLMap hat eine SQL-Injection-Schwachstelle erkannt.",
                    affected_target=target,
                    affected_param=param,
                    evidence=output[:2000],
                    tool_output={"stdout": stdout[:5000], "stderr": stderr[:2000]},
                    remediation="Prepared Statements verwenden. Parameterisierte Queries nutzen. "
                                "Input-Validierung implementieren.",
                ))

        # Wenn keine Injection gefunden → Info-Level
        if not findings and "all tested parameters do not appear to be injectable" in output:
            findings.append(ScanResult(
                severity=Severity.INFO.value,
                category="sql_injection",
                title=f"Keine SQL-Injection in {target}",
                description="Alle getesteten Parameter sind nicht anfällig.",
                affected_target=target,
                tool_output={"result": "clean"},
            ))

        return findings

    def _discover_api_endpoints(self) -> List[str]:
        """Ermittelt API-Endpunkte für den Test."""
        # Standard-Endpunkte die in jedem DBAI-System existieren
        endpoints = [
            "/api/health",
            "/api/system/status",
            "/api/hardware/status",
            "/api/processes",
            "/api/audit/log",
            "/api/apps",
            "/api/firewall/rules",
            "/api/chat/sessions",
        ]

        # Dynamisch Endpunkte aus der DB laden
        try:
            rows = self._execute("""
                SELECT DISTINCT endpoint FROM dbai_core.config
                WHERE key LIKE 'api.endpoint.%'
                AND value->>'enabled' = 'true'
            """)
            for row in rows:
                if row.get("endpoint"):
                    endpoints.append(row["endpoint"])
        except Exception:
            pass

        return endpoints

    # ==================================================================
    # 2. Nmap Port-Scanner
    # ==================================================================
    def run_nmap_scan(self, targets: List[str] = None) -> List[ScanResult]:
        """
        Nmap-Scan auf eigenes Netzwerk und Router.
        Findet offene Ports und unsichere Services.
        """
        logger.info("═══ Nmap Port-Scan gestartet ═══")

        if targets is None:
            targets = [
                "127.0.0.1",           # Localhost
                "172.28.0.0/24",       # Docker-Netzwerk
                ROUTER_IP,             # Router
            ]

        all_results = []

        for target in targets:
            job_id = self._create_scan_job("nmap", target, "network")

            try:
                cmd = [
                    "nmap",
                    "-sV",                  # Service-Version erkennen
                    "-sC",                  # Default-Scripts
                    "-O",                   # OS-Erkennung
                    "--script=vuln",        # Vulnerability-Scripts
                    "-T4",                  # Aggressive Timing
                    "--open",               # Nur offene Ports
                    "-oX", "-",             # XML-Ausgabe auf stdout
                    target,
                ]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=600,  # 10 Minuten
                )

                findings = self._parse_nmap_output(result.stdout, target)
                all_results.extend(findings)

                findings_count = self._store_findings(job_id, findings)
                self._complete_scan_job(job_id, findings_count)

            except subprocess.TimeoutExpired:
                logger.warning("Nmap Timeout für %s", target)
                self._fail_scan_job(job_id, "Timeout")
            except FileNotFoundError:
                logger.error("nmap nicht installiert")
                break
            except Exception as e:
                logger.error("Nmap Fehler für %s: %s", target, e)
                self._fail_scan_job(job_id, str(e))

        logger.info("═══ Nmap abgeschlossen: %d Findings ═══", len(all_results))
        return all_results

    def _parse_nmap_output(self, output: str, target: str) -> List[ScanResult]:
        """Parst Nmap-XML-Ausgabe."""
        findings = []

        # Erwartete offene Ports (alles andere ist verdächtig)
        expected_ports = {5432, 3000, 5173}  # PostgreSQL, API, UI

        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(output)

            for host in root.findall(".//host"):
                ip_elem = host.find("address[@addrtype='ipv4']")
                ip = ip_elem.get("addr", target) if ip_elem is not None else target

                for port_elem in host.findall(".//port"):
                    port = int(port_elem.get("portid", "0"))
                    protocol = port_elem.get("protocol", "tcp")
                    state_elem = port_elem.find("state")
                    state = state_elem.get("state", "unknown") if state_elem is not None else "unknown"
                    service_elem = port_elem.find("service")
                    service = service_elem.get("name", "unknown") if service_elem is not None else "unknown"
                    version = service_elem.get("version", "") if service_elem is not None else ""

                    if state == "open" and port not in expected_ports:
                        severity = Severity.HIGH.value if port < 1024 else Severity.MEDIUM.value

                        findings.append(ScanResult(
                            severity=severity,
                            category="open_port",
                            title=f"Unerwarteter offener Port: {port}/{protocol} ({service})",
                            description=f"Port {port} ist offen und nicht in der Whitelist. "
                                        f"Service: {service} {version}",
                            affected_target=f"{ip}:{port}",
                            tool_output={
                                "port": port, "protocol": protocol,
                                "service": service, "version": version,
                                "state": state,
                            },
                            remediation=f"Port {port} schließen falls nicht benötigt. "
                                        f"Firewall-Regel hinzufügen.",
                        ))

                    # Version-Check für bekannte Schwachstellen
                    if version and service == "postgresql":
                        findings.extend(
                            self._check_service_version(service, version, f"{ip}:{port}")
                        )

                # Vulnerability-Script-Ergebnisse
                for script in host.findall(".//script"):
                    script_id = script.get("id", "")
                    script_output = script.get("output", "")

                    if "VULNERABLE" in script_output.upper():
                        cve = ""
                        for line in script_output.split("\n"):
                            if "CVE-" in line:
                                cve = line.strip()
                                break

                        findings.append(ScanResult(
                            severity=Severity.HIGH.value,
                            category="misconfiguration",
                            title=f"Nmap-Script-Fund: {script_id}",
                            description=script_output[:500],
                            affected_target=ip,
                            cve_id=cve,
                            tool_output={"script": script_id, "output": script_output},
                            remediation="Service patchen oder Konfiguration anpassen.",
                        ))

        except Exception as e:
            logger.warning("Nmap XML-Parsing fehlgeschlagen, Fallback auf Text: %s", e)
            # Text-basiertes Fallback-Parsing
            for line in output.split("\n"):
                if "/tcp" in line and "open" in line:
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        port_proto = parts[0]
                        service = parts[2] if len(parts) > 2 else "unknown"
                        port = int(port_proto.split("/")[0])

                        if port not in expected_ports:
                            findings.append(ScanResult(
                                severity=Severity.MEDIUM.value,
                                category="open_port",
                                title=f"Offener Port: {port_proto} ({service})",
                                affected_target=f"{target}:{port}",
                            ))

        return findings

    def _check_service_version(self, service: str, version: str, target: str) -> List[ScanResult]:
        """Prüft ob eine Service-Version bekannte Schwachstellen hat."""
        findings = []
        # Kann mit CVE-Datenbank erweitert werden
        try:
            rows = self._execute("""
                SELECT cve_id, title, cvss_score FROM dbai_security.cve_tracking
                WHERE affected_pkg ILIKE %s AND is_patched = FALSE AND is_relevant = TRUE
            """, (f"%{service}%",))

            for row in rows:
                findings.append(ScanResult(
                    severity=Severity.HIGH.value if (row.get("cvss_score") or 0) >= 7 else Severity.MEDIUM.value,
                    category="outdated_software",
                    title=f"CVE gefunden: {row['cve_id']} in {service} {version}",
                    description=row.get("title", ""),
                    affected_target=target,
                    cve_id=row.get("cve_id", ""),
                    cvss_score=float(row.get("cvss_score") or 0),
                ))
        except Exception:
            pass

        return findings

    # ==================================================================
    # 3. Nuclei Vulnerability Scanner
    # ==================================================================
    def run_nuclei_scan(self, target_url: str = None) -> List[ScanResult]:
        """Nuclei-Scan für Web-Schwachstellen."""
        logger.info("═══ Nuclei-Scan gestartet ═══")

        if target_url is None:
            target_url = API_BASE_URL

        job_id = self._create_scan_job("nuclei", target_url, "api")
        results = []

        try:
            cmd = [
                "nuclei",
                "-u", target_url,
                "-severity", "critical,high,medium",
                "-silent",
                "-json",
                "-rate-limit", "50",
                "-timeout", "10",
                "-retries", "2",
            ]

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=600,
            )

            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    finding = json.loads(line)
                    severity_map = {
                        "critical": Severity.CRITICAL.value,
                        "high": Severity.HIGH.value,
                        "medium": Severity.MEDIUM.value,
                        "low": Severity.LOW.value,
                        "info": Severity.INFO.value,
                    }
                    results.append(ScanResult(
                        severity=severity_map.get(
                            finding.get("info", {}).get("severity", "info"),
                            Severity.INFO.value
                        ),
                        category="misconfiguration",
                        title=finding.get("info", {}).get("name", "Nuclei Finding"),
                        description=finding.get("info", {}).get("description", ""),
                        affected_target=finding.get("matched-at", target_url),
                        cve_id=finding.get("info", {}).get("classification", {}).get("cve-id", [""])[0]
                        if isinstance(finding.get("info", {}).get("classification", {}).get("cve-id"), list)
                        else "",
                        tool_output=finding,
                        remediation=finding.get("info", {}).get("remediation", ""),
                    ))
                except json.JSONDecodeError:
                    continue

        except FileNotFoundError:
            logger.warning("nuclei nicht installiert — überspringe")
        except subprocess.TimeoutExpired:
            logger.warning("Nuclei Timeout")
        except Exception as e:
            logger.error("Nuclei Fehler: %s", e)

        findings_count = self._store_findings(job_id, results)
        self._complete_scan_job(job_id, findings_count)

        logger.info("═══ Nuclei abgeschlossen: %d Findings ═══", len(results))
        return results

    # ==================================================================
    # 4. Fail2Ban Integration
    # ==================================================================
    def monitor_postgresql_logs(self):
        """
        Überwacht PostgreSQL-Logs auf fehlgeschlagene Authentifizierungen.
        Verknüpft fail2ban direkt mit der Datenbank.
        """
        logger.info("═══ PostgreSQL-Log-Monitor gestartet ═══")

        log_patterns = [
            "FATAL:  password authentication failed",
            "FATAL:  no pg_hba.conf entry",
            "FATAL:  role .* does not exist",
            "LOG:  connection received",
        ]

        pg_log_path = os.getenv("PG_LOG_PATH", "/var/lib/postgresql/data/log")

        while not self._shutdown.is_set():
            try:
                self._check_pg_log_entries(pg_log_path, log_patterns)
                self._check_api_auth_failures()
                self._enforce_bans()
            except Exception as e:
                logger.error("Log-Monitor Fehler: %s", e)

            self._shutdown.wait(10)  # Alle 10 Sekunden prüfen

    def _check_pg_log_entries(self, log_dir: str, patterns: List[str]):
        """Parst PostgreSQL-Logdateien für Sicherheits-Events."""
        log_path = Path(log_dir)
        if not log_path.exists():
            return

        for log_file in sorted(log_path.glob("postgresql-*.log"))[-1:]:  # Nur neueste
            try:
                with open(log_file, "r") as f:
                    # Lese nur die letzten 1000 Zeilen
                    lines = f.readlines()[-1000:]

                for line in lines:
                    if "password authentication failed" in line:
                        ip = self._extract_ip_from_log(line)
                        user = self._extract_user_from_log(line)
                        if ip:
                            self._log_failed_auth(ip, user, "postgresql", 5432)

                    elif "no pg_hba.conf entry" in line:
                        ip = self._extract_ip_from_log(line)
                        if ip:
                            self._log_failed_auth(ip, None, "postgresql", 5432)

            except Exception as e:
                logger.debug("Log-Datei Fehler: %s", e)

    def _check_api_auth_failures(self):
        """Prüft API-Auth-Failures aus der Datenbank."""
        try:
            # Prüfe ob neue fehlgeschlagene Versuche einen Ban auslösen
            rows = self._execute("""
                SELECT source_ip, COUNT(*) as cnt
                FROM dbai_security.failed_auth_log
                WHERE attempt_at > now() - interval '%s minutes'
                GROUP BY source_ip
                HAVING COUNT(*) >= %s
            """, (F2B_WINDOW_MINUTES, F2B_MAX_ATTEMPTS))

            for row in rows:
                ip = row["source_ip"]
                self._execute(
                    "SELECT dbai_security.check_and_ban_ip(%s, %s, %s, %s)",
                    (ip, F2B_MAX_ATTEMPTS, F2B_WINDOW_MINUTES, F2B_BAN_HOURS)
                )
                logger.warning("IP %s gebannt: %d Fehlversuche", ip, row["cnt"])

                # Firewall-Regel setzen
                self._apply_iptables_ban(str(ip))

        except Exception as e:
            logger.error("Auth-Failure-Check Fehler: %s", e)

    def _log_failed_auth(self, ip: str, username: str, auth_type: str, port: int):
        """Fehlgeschlagenen Login in die Datenbank schreiben."""
        try:
            self._execute("""
                INSERT INTO dbai_security.failed_auth_log
                    (source_ip, username, auth_type, service_port)
                VALUES (%s, %s, %s, %s)
            """, (ip, username, auth_type, port))

            # Sofort prüfen ob Ban nötig
            result = self._execute(
                "SELECT dbai_security.check_and_ban_ip(%s, %s, %s, %s) AS banned",
                (ip, F2B_MAX_ATTEMPTS, F2B_WINDOW_MINUTES, F2B_BAN_HOURS)
            )
            if result and result[0].get("banned"):
                self._apply_iptables_ban(ip)
                logger.warning("FAIL2BAN: IP %s gesperrt auf Hardware-Ebene", ip)

        except Exception as e:
            logger.error("Failed-Auth-Logging Fehler: %s", e)

    def _enforce_bans(self):
        """Synchronisiert DB-Bans mit iptables."""
        try:
            # Aktive Bans aus DB laden
            bans = self._execute("""
                SELECT ip_address::TEXT as ip, cidr_mask
                FROM dbai_security.ip_bans
                WHERE is_active = TRUE
                AND (expires_at IS NULL OR expires_at > now())
            """)

            for ban in bans:
                ip = ban["ip"]
                cidr = ban.get("cidr_mask", 32)
                target = f"{ip}/{cidr}" if cidr < 32 else ip
                self._apply_iptables_ban(target)

            # Abgelaufene Bans aufheben
            expired = self._execute("SELECT dbai_security.cleanup_expired_bans() AS count")
            if expired and expired[0].get("count", 0) > 0:
                logger.info("Abgelaufene Bans aufgehoben: %d", expired[0]["count"])
                self._sync_iptables_with_db()

        except Exception as e:
            logger.error("Ban-Enforcement Fehler: %s", e)

    def _extract_ip_from_log(self, line: str) -> Optional[str]:
        """Extrahiert IP-Adresse aus einer Log-Zeile."""
        import re
        match = re.search(r'host\s+"?(\d+\.\d+\.\d+\.\d+)"?', line)
        if match:
            return match.group(1)
        match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
        if match:
            ip = match.group(1)
            if ip not in ("127.0.0.1", "0.0.0.0"):
                return ip
        return None

    def _extract_user_from_log(self, line: str) -> Optional[str]:
        """Extrahiert Benutzernamen aus einer Log-Zeile."""
        import re
        match = re.search(r'user\s+"?(\w+)"?', line)
        return match.group(1) if match else None

    # ==================================================================
    # 5. Netzwerk-Firewall-Manager (iptables/nftables)
    # ==================================================================
    def setup_firewall(self):
        """
        Initialisiert die Netzwerk-Firewall mit Basis-Regeln.
        Schützt alles was am Router angeschlossen ist.
        """
        logger.info("═══ Firewall-Setup gestartet ═══")

        rules = [
            # --- Basis-Policy ---
            # Standard: Alles blockieren, nur explizit erlaubtes durchlassen
            ("INPUT", "-m state --state ESTABLISHED,RELATED -j ACCEPT",
             "Bestehende Verbindungen erlauben"),
            ("INPUT", "-i lo -j ACCEPT",
             "Loopback erlauben"),

            # --- Anti-Scanning ---
            ("INPUT", "-p tcp --tcp-flags ALL NONE -j DROP",
             "NULL-Scan blockieren"),
            ("INPUT", "-p tcp --tcp-flags SYN,FIN SYN,FIN -j DROP",
             "SYN-FIN-Scan blockieren"),
            ("INPUT", "-p tcp --tcp-flags SYN,RST SYN,RST -j DROP",
             "SYN-RST-Scan blockieren"),
            ("INPUT", "-p tcp --tcp-flags ALL FIN,URG,PSH -j DROP",
             "XMAS-Scan blockieren"),
            ("INPUT", "-p tcp --tcp-flags ALL ALL -j DROP",
             "XMAS-Tree-Scan blockieren"),
            ("INPUT", "-p tcp --tcp-flags ALL SYN,RST,ACK,FIN,URG -j DROP",
             "Ungültige TCP-Flags blockieren"),

            # --- ICMP Rate-Limiting ---
            ("INPUT", "-p icmp --icmp-type echo-request -m limit --limit 1/s --limit-burst 4 -j ACCEPT",
             "Ping Rate-Limit"),
            ("INPUT", "-p icmp --icmp-type echo-request -j DROP",
             "Ping-Flood blockieren"),

            # --- SYN-Flood Schutz ---
            ("INPUT", "-p tcp --syn -m limit --limit 25/s --limit-burst 50 -j ACCEPT",
             "SYN-Flood Schutz"),

            # --- Brute-Force Schutz für PostgreSQL ---
            ("INPUT", "-p tcp --dport 5432 -m connlimit --connlimit-above 10 -j DROP",
             "PostgreSQL Verbindungslimit"),
            ("INPUT", "-p tcp --dport 5432 -m recent --name pg_brute --set",
             "PostgreSQL Brute-Force Tracking"),
            ("INPUT", "-p tcp --dport 5432 -m recent --name pg_brute --rcheck --seconds 60 --hitcount 5 -j DROP",
             "PostgreSQL Brute-Force Block"),

            # --- Brute-Force Schutz für API ---
            ("INPUT", "-p tcp --dport 3000 -m connlimit --connlimit-above 50 -j DROP",
             "API Verbindungslimit"),

            # --- SSH-Schutz (falls aktiv) ---
            ("INPUT", "-p tcp --dport 22 -m connlimit --connlimit-above 3 -j DROP",
             "SSH Verbindungslimit"),
            ("INPUT", "-p tcp --dport 22 -m recent --name ssh_brute --set",
             "SSH Brute-Force Tracking"),
            ("INPUT", "-p tcp --dport 22 -m recent --name ssh_brute --rcheck --seconds 120 --hitcount 4 -j DROP",
             "SSH Brute-Force Block"),

            # --- Spoofing-Schutz ---
            ("INPUT", "-s 10.0.0.0/8 -i eth0 -j DROP",
             "RFC1918 Spoofing blockieren (10.x)"),
            ("INPUT", "-s 169.254.0.0/16 -j DROP",
             "Link-Local Spoofing blockieren"),
            ("INPUT", "-s 224.0.0.0/4 -j DROP",
             "Multicast-Spoofing blockieren"),
            ("INPUT", "-s 240.0.0.0/5 -j DROP",
             "Reservierte Adressen blockieren"),

            # --- Port-Scan-Erkennung ---
            ("INPUT", "-m recent --name portscan --rcheck --seconds 86400 -j DROP",
             "Bekannte Portscanner blockieren"),
            ("INPUT", "-m recent --name portscan --remove",
             "Portscanner-Liste bereinigen"),

            # --- Erlaubte Services ---
            ("INPUT", "-p tcp --dport 5432 -s 172.28.0.0/16 -j ACCEPT",
             "PostgreSQL nur aus Docker-Netzwerk"),
            ("INPUT", "-p tcp --dport 3000 -j ACCEPT",
             "API-Port erlauben"),
            ("INPUT", "-p tcp --dport 5173 -j ACCEPT",
             "UI-Port erlauben (Dev)"),

            # --- Default Drop ---
            ("INPUT", "-j DROP",
             "Alles andere blockieren"),

            # --- OUTPUT Regeln ---
            ("OUTPUT", "-m state --state ESTABLISHED,RELATED -j ACCEPT",
             "Bestehende ausgehende Verbindungen"),
            ("OUTPUT", "-o lo -j ACCEPT",
             "Loopback-Output"),
            ("OUTPUT", "-p tcp --dport 53 -j ACCEPT",
             "DNS erlauben"),
            ("OUTPUT", "-p udp --dport 53 -j ACCEPT",
             "DNS UDP erlauben"),
            ("OUTPUT", "-p tcp --dport 443 -j ACCEPT",
             "HTTPS erlauben (Updates)"),
            ("OUTPUT", "-p tcp --dport 80 -j ACCEPT",
             "HTTP erlauben (Updates)"),
            ("OUTPUT", "-p tcp --dport 5432 -d 172.28.0.0/16 -j ACCEPT",
             "PostgreSQL innerhalb Docker"),

            # --- FORWARD (Router-Schutz) ---
            ("FORWARD", "-m state --state ESTABLISHED,RELATED -j ACCEPT",
             "Bestehende Forward-Verbindungen"),
            ("FORWARD", "-p tcp --dport 445 -j DROP",
             "SMB blockieren"),
            ("FORWARD", "-p tcp --dport 135:139 -j DROP",
             "NetBIOS blockieren"),
            ("FORWARD", "-p udp --dport 137:138 -j DROP",
             "NetBIOS UDP blockieren"),
            ("FORWARD", "-p tcp --dport 23 -j DROP",
             "Telnet blockieren"),
        ]

        for chain, rule, description in rules:
            self._add_firewall_rule(chain, rule, description)

        # Kernel-Parameter für Netzwerk-Härtung
        self._harden_kernel_network()

        # Firewall-Regeln in DB synchronisieren
        self._sync_firewall_to_db(rules)

        logger.info("═══ Firewall-Setup abgeschlossen: %d Regeln ═══", len(rules))

    def _add_firewall_rule(self, chain: str, rule: str, description: str):
        """Fügt eine iptables-Regel hinzu (idempotent)."""
        try:
            # Prüfe ob Regel bereits existiert
            check = subprocess.run(
                f"iptables -C {chain} {rule}",
                shell=True, capture_output=True, text=True,
            )
            if check.returncode != 0:
                # Regel existiert nicht → hinzufügen
                result = subprocess.run(
                    f"iptables -A {chain} {rule}",
                    shell=True, capture_output=True, text=True,
                )
                if result.returncode == 0:
                    logger.debug("Firewall-Regel hinzugefügt: %s %s", chain, description)
                else:
                    logger.warning("Firewall-Regel fehlgeschlagen: %s — %s",
                                   description, result.stderr.strip())
        except Exception as e:
            logger.debug("iptables nicht verfügbar: %s", e)

    def _apply_iptables_ban(self, ip: str):
        """Bannt eine IP auf iptables-Ebene."""
        try:
            # Prüfe ob bereits gebannt
            check = subprocess.run(
                f"iptables -C INPUT -s {ip} -j DROP",
                shell=True, capture_output=True,
            )
            if check.returncode != 0:
                subprocess.run(
                    f"iptables -I INPUT 1 -s {ip} -j DROP",
                    shell=True, capture_output=True,
                )
                logger.info("iptables: IP %s gesperrt", ip)
        except Exception as e:
            logger.debug("iptables Ban fehlgeschlagen (Container ohne Capabilities?): %s", e)

    def _sync_iptables_with_db(self):
        """Synchronisiert iptables mit der DB (entfernt abgelaufene Bans)."""
        try:
            # Aktive Bans aus DB
            active_bans = set()
            rows = self._execute("""
                SELECT ip_address::TEXT as ip
                FROM dbai_security.ip_bans
                WHERE is_active = TRUE
                AND (expires_at IS NULL OR expires_at > now())
            """)
            for row in rows:
                active_bans.add(row["ip"])

            # Aktuelle iptables-Regeln lesen
            result = subprocess.run(
                "iptables -L INPUT -n --line-numbers",
                shell=True, capture_output=True, text=True,
            )

            import re
            for line in result.stdout.split("\n"):
                match = re.search(r"^(\d+)\s+DROP\s+.*\s+(\d+\.\d+\.\d+\.\d+)\s+", line)
                if match:
                    rule_num = match.group(1)
                    ip = match.group(2)
                    if ip not in active_bans and ip not in TRUSTED_IPS:
                        subprocess.run(
                            f"iptables -D INPUT {rule_num}",
                            shell=True, capture_output=True,
                        )
                        logger.info("iptables: Ban für %s aufgehoben", ip)

        except Exception as e:
            logger.debug("iptables-Sync Fehler: %s", e)

    def _harden_kernel_network(self):
        """Setzt Kernel-Parameter für Netzwerk-Härtung."""
        sysctl_params = {
            # SYN-Flood-Schutz
            "net.ipv4.tcp_syncookies": "1",
            # Kein IP-Forwarding (außer Router)
            "net.ipv4.ip_forward": "0",
            # Keine ICMP-Redirects akzeptieren
            "net.ipv4.conf.all.accept_redirects": "0",
            "net.ipv6.conf.all.accept_redirects": "0",
            "net.ipv4.conf.all.send_redirects": "0",
            # Source-Routing deaktivieren
            "net.ipv4.conf.all.accept_source_route": "0",
            "net.ipv6.conf.all.accept_source_route": "0",
            # Log Martians (ungültige Absende-Adressen)
            "net.ipv4.conf.all.log_martians": "1",
            # Reverse-Path-Filtering
            "net.ipv4.conf.all.rp_filter": "1",
            "net.ipv4.conf.default.rp_filter": "1",
            # TCP-Timestamps gegen Fingerprinting
            "net.ipv4.tcp_timestamps": "0",
            # Broadcast-ICMP ignorieren (Smurf-Schutz)
            "net.ipv4.icmp_echo_ignore_broadcasts": "1",
            # Bogus ICMP-Antworten ignorieren
            "net.ipv4.icmp_ignore_bogus_error_responses": "1",
            # TCP-Window-Scaling
            "net.ipv4.tcp_window_scaling": "1",
            # Maximale SYN-Backlog-Größe
            "net.ipv4.tcp_max_syn_backlog": "4096",
            # Time-Wait-Sockets wiederverwenden
            "net.ipv4.tcp_tw_reuse": "1",
            # Keepalive-Interval
            "net.ipv4.tcp_keepalive_time": "600",
            "net.ipv4.tcp_keepalive_intvl": "60",
            "net.ipv4.tcp_keepalive_probes": "5",
        }

        for param, value in sysctl_params.items():
            try:
                subprocess.run(
                    f"sysctl -w {param}={value}",
                    shell=True, capture_output=True,
                )
            except Exception:
                pass

    def _sync_firewall_to_db(self, rules: List[Tuple[str, str, str]]):
        """Synchronisiert Firewall-Regeln in die Datenbank."""
        try:
            for chain, rule, description in rules:
                self._execute("""
                    INSERT INTO dbai_system.firewall_rules 
                        (rule_name, chain, action, protocol, description, is_active)
                    VALUES (%s, %s, %s, %s, %s, TRUE)
                    ON CONFLICT (rule_name, chain, protocol) DO UPDATE SET
                        description = EXCLUDED.description,
                        is_active = TRUE
                """, (
                    description[:100],
                    chain,
                    "DROP" if "DROP" in rule else "ACCEPT" if "ACCEPT" in rule else "LOG",
                    "tcp" if "--dport" in rule or "-p tcp" in rule else
                    "udp" if "-p udp" in rule else
                    "icmp" if "-p icmp" in rule else "all",
                    description,
                ))
        except Exception as e:
            logger.warning("Firewall-DB-Sync Fehler: %s", e)

    # ==================================================================
    # 6. Intrusion Detection (Suricata)
    # ==================================================================
    def start_ids_monitor(self):
        """
        Startet Suricata IDS und überwacht dessen Output.
        Leitet Netzwerkverkehr durch das IDS.
        """
        logger.info("═══ IDS-Monitor (Suricata) gestartet ═══")

        # Suricata starten
        suricata_conf = "/etc/suricata/suricata.yaml"
        eve_log = "/var/log/suricata/eve.json"

        try:
            subprocess.Popen(
                ["suricata", "-c", suricata_conf, "-i", "eth0", "--init-errors-fatal"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("Suricata gestartet auf eth0")
        except FileNotFoundError:
            logger.warning("Suricata nicht installiert — IDS deaktiviert")
            return
        except Exception as e:
            logger.error("Suricata Start fehlgeschlagen: %s", e)
            return

        # Eve-Log überwachen (JSON-basierte Alerts)
        time.sleep(5)  # Suricata hochfahren lassen

        while not self._shutdown.is_set():
            try:
                self._process_suricata_eve(eve_log)
            except Exception as e:
                logger.error("Suricata-Monitor Fehler: %s", e)

            self._shutdown.wait(5)

    def _process_suricata_eve(self, eve_log: str):
        """Verarbeitet Suricata EVE-JSON-Log."""
        eve_path = Path(eve_log)
        if not eve_path.exists():
            return

        try:
            with open(eve_path, "r") as f:
                # Letzte 100 Zeilen
                lines = f.readlines()[-100:]

            for line in lines:
                try:
                    event = json.loads(line.strip())

                    if event.get("event_type") == "alert":
                        alert = event.get("alert", {})

                        self._execute("""
                            INSERT INTO dbai_security.intrusion_events (
                                event_type, source_ip, source_port,
                                dest_ip, dest_port, protocol,
                                signature_id, signature_name,
                                classification, priority, raw_alert
                            ) VALUES (
                                'alert', %s, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s
                            )
                        """, (
                            event.get("src_ip"),
                            event.get("src_port"),
                            event.get("dest_ip"),
                            event.get("dest_port"),
                            event.get("proto", "tcp").lower(),
                            alert.get("signature_id"),
                            alert.get("signature"),
                            alert.get("category"),
                            alert.get("severity", 3),
                            Json(event),
                        ))

                except json.JSONDecodeError:
                    continue

        except Exception as e:
            logger.debug("Eve-Log Verarbeitung: %s", e)

    # ==================================================================
    # 7. Honeypot-Services
    # ==================================================================
    def start_honeypots(self):
        """
        Startet Honeypot-Fallen auf typischen Angriffs-Ports.
        Jede Interaktion → sofortiger Ban.
        """
        logger.info("═══ Honeypot-Services gestartet ═══")

        honeypot_ports = {
            2222: ("fake_ssh", "SSH Honeypot"),
            3306: ("fake_db", "MySQL Honeypot"),
            8080: ("fake_api", "Fake Admin Panel"),
            8443: ("fake_admin", "Fake HTTPS Admin"),
            21: ("fake_ssh", "FTP Honeypot"),
            23: ("fake_ssh", "Telnet Honeypot"),
        }

        for port, (hp_type, description) in honeypot_ports.items():
            t = threading.Thread(
                target=self._run_honeypot,
                args=(port, hp_type, description),
                daemon=True,
                name=f"honeypot-{port}",
            )
            t.start()
            self._threads.append(t)

    def _run_honeypot(self, port: int, hp_type: str, description: str):
        """Einzelner Honeypot-Listener."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(1.0)
            sock.bind(("0.0.0.0", port))
            sock.listen(5)
            logger.info("Honeypot aktiv: Port %d (%s)", port, description)

            while not self._shutdown.is_set():
                try:
                    conn, addr = sock.accept()
                    ip, src_port = addr

                    # Kurz warten und Daten lesen
                    conn.settimeout(5.0)
                    try:
                        data = conn.recv(4096)
                        payload = data.decode("utf-8", errors="replace")[:512]
                    except Exception:
                        payload = ""

                    # Banner senden (Fake-Service)
                    try:
                        if hp_type == "fake_ssh":
                            conn.send(b"SSH-2.0-OpenSSH_8.9p1 Ubuntu-3ubuntu0.4\r\n")
                        elif hp_type == "fake_db":
                            conn.send(b"\x00\x00\x00\x0a5.7.99\x00")
                        elif hp_type == "fake_api":
                            conn.send(b"HTTP/1.1 401 Unauthorized\r\n\r\n")
                        elif hp_type == "fake_admin":
                            conn.send(b"HTTP/1.1 200 OK\r\n\r\n<html><title>Admin Login</title></html>")
                    except Exception:
                        pass

                    conn.close()

                    # In DB loggen (Trigger reagiert automatisch)
                    logger.warning("HONEYPOT: %s:%d → Port %d (%s)", ip, src_port, port, hp_type)
                    try:
                        self._execute("""
                            INSERT INTO dbai_security.honeypot_events
                                (honeypot_type, source_ip, source_port, interaction, payload)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (hp_type, ip, src_port,
                              f"Verbindung zu {description}", payload))
                    except Exception as e:
                        logger.error("Honeypot DB-Fehler: %s", e)

                except socket.timeout:
                    continue
                except Exception as e:
                    if not self._shutdown.is_set():
                        logger.debug("Honeypot %d Fehler: %s", port, e)

        except OSError as e:
            logger.debug("Honeypot Port %d nicht verfügbar: %s", port, e)
        finally:
            try:
                sock.close()
            except Exception:
                pass

    # ==================================================================
    # 8. TLS-Zertifikats-Überwachung
    # ==================================================================
    def check_tls_certificates(self):
        """Prüft TLS-Zertifikate auf Ablauf und Schwachstellen."""
        logger.info("═══ TLS-Zertifikats-Prüfung ═══")

        try:
            certs = self._execute("""
                SELECT id, domain, not_after, cert_path
                FROM dbai_security.tls_certificates
                WHERE status = 'active'
            """)

            for cert in certs:
                domain = cert["domain"]
                not_after = cert.get("not_after")

                # Ablauf prüfen
                if not_after:
                    days_left = (not_after - datetime.now(timezone.utc)).days
                    if days_left <= 0:
                        self._execute("""
                            UPDATE dbai_security.tls_certificates
                            SET status = 'expired' WHERE id = %s
                        """, (cert["id"],))
                        logger.warning("TLS-Zertifikat abgelaufen: %s", domain)
                    elif days_left <= 30:
                        self._execute("""
                            UPDATE dbai_security.tls_certificates
                            SET status = 'pending_renewal' WHERE id = %s
                        """, (cert["id"],))
                        logger.warning("TLS-Zertifikat läuft in %d Tagen ab: %s", days_left, domain)

                # SSL-Scan (Cipher-Prüfung)
                try:
                    result = subprocess.run(
                        ["sslscan", "--no-colour", domain],
                        capture_output=True, text=True, timeout=30,
                    )
                    if "SSLv2" in result.stdout or "SSLv3" in result.stdout:
                        self._store_findings(None, [ScanResult(
                            severity=Severity.HIGH.value,
                            category="weak_cipher",
                            title=f"Veraltetes SSL-Protokoll auf {domain}",
                            description="SSLv2/SSLv3 ist unsicher und sollte deaktiviert werden.",
                            affected_target=domain,
                            remediation="Nur TLS 1.2+ erlauben.",
                        )])
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    pass

                # Last-checked aktualisieren
                self._execute("""
                    UPDATE dbai_security.tls_certificates
                    SET last_checked_at = now() WHERE id = %s
                """, (cert["id"],))

        except Exception as e:
            logger.error("TLS-Check Fehler: %s", e)

    # ==================================================================
    # 9. Security-Baseline-Audit (Lynis)
    # ==================================================================
    def run_baseline_audit(self):
        """
        Führt ein System-Hardening-Audit durch (Lynis-basiert).
        Ergebnisse werden als Baselines in der DB gespeichert.
        """
        logger.info("═══ Security-Baseline-Audit (Lynis) ═══")

        job_id = self._create_scan_job("lynis", "localhost", "host")

        # PostgreSQL-spezifische Checks
        pg_checks = [
            ("postgresql", "listen_addresses", "127.0.0.1",
             "Nur localhost erlaubt"),
            ("postgresql", "ssl", "on",
             "SSL muss aktiviert sein"),
            ("postgresql", "password_encryption", "scram-sha-256",
             "SCRAM-SHA-256 Authentifizierung"),
            ("postgresql", "row_security", "on",
             "Row-Level-Security muss aktiv sein"),
            ("postgresql", "log_connections", "on",
             "Verbindungen müssen geloggt werden"),
            ("postgresql", "log_disconnections", "on",
             "Trennungen müssen geloggt werden"),
            ("postgresql", "log_statement", "ddl",
             "DDL-Statements müssen geloggt werden"),
            ("postgresql", "statement_timeout", "60s",
             "Query-Timeout muss gesetzt sein"),
            ("postgresql", "max_connections", "100",
             "Verbindungslimit prüfen"),
        ]

        for component, check_name, expected, description in pg_checks:
            try:
                current = self._get_pg_setting(check_name)
                compliant = current == expected if current else False

                severity = "high" if check_name in ("ssl", "row_security", "password_encryption") else "medium"

                self._execute("""
                    INSERT INTO dbai_security.security_baselines
                        (component, check_name, expected_value, current_value, compliant, severity)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (component, check_name) DO UPDATE SET
                        current_value = EXCLUDED.current_value,
                        compliant = EXCLUDED.compliant,
                        last_checked_at = now()
                """, (component, check_name, expected, current, compliant, severity))

                if not compliant:
                    logger.warning("Baseline-Abweichung: %s.%s = %s (erwartet: %s)",
                                   component, check_name, current, expected)

            except Exception as e:
                logger.debug("Baseline-Check Fehler für %s: %s", check_name, e)

        # Docker-Sicherheits-Checks
        docker_checks = [
            ("docker", "user_namespace", "enabled",
             "User-Namespaces aktiviert"),
            ("docker", "no_new_privileges", "true",
             "No-New-Privileges Flag"),
            ("docker", "read_only_rootfs", "true",
             "Read-Only Root-Filesystem"),
        ]

        for component, check_name, expected, description in docker_checks:
            try:
                current = self._check_docker_security(check_name)
                self._execute("""
                    INSERT INTO dbai_security.security_baselines
                        (component, check_name, expected_value, current_value, compliant, severity)
                    VALUES (%s, %s, %s, %s, %s, 'medium')
                    ON CONFLICT (component, check_name) DO UPDATE SET
                        current_value = EXCLUDED.current_value,
                        compliant = EXCLUDED.compliant,
                        last_checked_at = now()
                """, (component, check_name, expected, current or "unknown",
                      current == expected if current else False))
            except Exception:
                pass

        # Netzwerk-Sicherheits-Checks
        network_checks = [
            ("network", "ip_forward", "0", "IP-Forwarding deaktiviert"),
            ("network", "tcp_syncookies", "1", "SYN-Cookies aktiviert"),
            ("network", "accept_redirects", "0", "ICMP-Redirects deaktiviert"),
            ("network", "rp_filter", "1", "Reverse-Path-Filtering"),
        ]

        sysctl_map = {
            "ip_forward": "net.ipv4.ip_forward",
            "tcp_syncookies": "net.ipv4.tcp_syncookies",
            "accept_redirects": "net.ipv4.conf.all.accept_redirects",
            "rp_filter": "net.ipv4.conf.all.rp_filter",
        }

        for component, check_name, expected, description in network_checks:
            try:
                sysctl_key = sysctl_map.get(check_name, "")
                result = subprocess.run(
                    f"sysctl -n {sysctl_key}",
                    shell=True, capture_output=True, text=True,
                )
                current = result.stdout.strip()
                self._execute("""
                    INSERT INTO dbai_security.security_baselines
                        (component, check_name, expected_value, current_value, compliant, severity)
                    VALUES (%s, %s, %s, %s, %s, 'high')
                    ON CONFLICT (component, check_name) DO UPDATE SET
                        current_value = EXCLUDED.current_value,
                        compliant = EXCLUDED.compliant,
                        last_checked_at = now()
                """, (component, check_name, expected, current, current == expected))
            except Exception:
                pass

        # Lynis ausführen (falls installiert)
        try:
            result = subprocess.run(
                ["lynis", "audit", "system", "--quick", "--no-colors", "--report-file", "/tmp/lynis-report.dat"],
                capture_output=True, text=True, timeout=300,
            )

            # Lynis-Score extrahieren
            for line in result.stdout.split("\n"):
                if "Hardening index" in line:
                    import re
                    match = re.search(r"(\d+)", line)
                    if match:
                        score = int(match.group(1))
                        self._execute("""
                            INSERT INTO dbai_security.security_baselines
                                (component, check_name, expected_value, current_value, compliant, severity)
                            VALUES ('system', 'lynis_hardening_score', '>= 70', %s, %s, 'high')
                            ON CONFLICT (component, check_name) DO UPDATE SET
                                current_value = EXCLUDED.current_value,
                                compliant = EXCLUDED.compliant,
                                last_checked_at = now()
                        """, (str(score), score >= 70))

        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.debug("Lynis nicht verfügbar")

        self._complete_scan_job(job_id, 0)
        logger.info("═══ Baseline-Audit abgeschlossen ═══")

    def _get_pg_setting(self, setting: str) -> Optional[str]:
        """Liest eine PostgreSQL-Einstellung."""
        try:
            rows = self._execute("SHOW %s" % setting)  # SHOW akzeptiert keine Parameter
            if rows:
                return list(rows[0].values())[0]
        except Exception:
            pass
        return None

    def _check_docker_security(self, check: str) -> Optional[str]:
        """Prüft Docker-Sicherheitseinstellungen."""
        try:
            if check == "user_namespace":
                result = subprocess.run(
                    "docker info --format '{{.SecurityOptions}}'",
                    shell=True, capture_output=True, text=True,
                )
                return "enabled" if "userns" in result.stdout else "disabled"
            elif check == "no_new_privileges":
                result = subprocess.run(
                    "docker info --format '{{.SecurityOptions}}'",
                    shell=True, capture_output=True, text=True,
                )
                return "true" if "no-new-privileges" in result.stdout else "false"
        except Exception:
            pass
        return None

    # ==================================================================
    # 10. DNS-Sinkhole Management
    # ==================================================================
    def update_dns_sinkhole(self):
        """Aktualisiert DNS-Sinkhole mit bekannten bösartigen Domains."""
        logger.info("DNS-Sinkhole Update…")

        # Basis-Blocklisten (können durch Feeds erweitert werden)
        base_domains = {
            "malware": [
                "malware-domain.example",
                "botnet-c2.example",
            ],
            "tracking": [
                "analytics-spy.example",
                "tracker-beacon.example",
            ],
            "cryptomining": [
                "coinhive.com",
                "crypto-loot.com",
                "coin-hive.com",
            ],
        }

        for category, domains in base_domains.items():
            for domain in domains:
                try:
                    self._execute("""
                        INSERT INTO dbai_security.dns_sinkhole (domain, category, source)
                        VALUES (%s, %s, 'builtin')
                        ON CONFLICT (domain) DO NOTHING
                    """, (domain, category))
                except Exception:
                    pass

        # Threat-Intel-Domains übernehmen
        try:
            self._execute("""
                INSERT INTO dbai_security.dns_sinkhole (domain, category, source)
                SELECT ioc_value, 
                    CASE threat_type
                        WHEN 'malware' THEN 'malware'
                        WHEN 'phishing' THEN 'phishing'
                        WHEN 'c2' THEN 'c2'
                        ELSE 'custom'
                    END,
                    'threat_intel'
                FROM dbai_security.threat_intelligence
                WHERE ioc_type = 'domain' AND is_active = TRUE
                ON CONFLICT (domain) DO NOTHING
            """)
        except Exception:
            pass

    # ==================================================================
    # 11. Dependency-Audit (CVE-Tracking)
    # ==================================================================
    def run_dependency_audit(self):
        """
        Prüft installierte Pakete auf bekannte Schwachstellen.
        """
        logger.info("═══ Dependency-Audit ═══")

        job_id = self._create_scan_job("dependency_audit", "system", "host")
        results = []

        # Python-Pakete prüfen
        try:
            result = subprocess.run(
                ["pip", "list", "--format=json"],
                capture_output=True, text=True, timeout=30,
            )
            packages = json.loads(result.stdout)

            # pip audit (falls vorhanden)
            audit_result = subprocess.run(
                ["pip-audit", "--format=json", "--desc"],
                capture_output=True, text=True, timeout=120,
            )

            if audit_result.returncode == 0:
                vulns = json.loads(audit_result.stdout)
                for vuln in vulns.get("vulnerabilities", []):
                    results.append(ScanResult(
                        severity=Severity.HIGH.value,
                        category="outdated_software",
                        title=f"CVE in {vuln.get('name', 'unknown')}: {vuln.get('id', '')}",
                        description=vuln.get("description", ""),
                        affected_target=f"pip:{vuln.get('name')}",
                        cve_id=vuln.get("id", ""),
                        remediation=f"Update auf {vuln.get('fix_versions', ['neueste Version'])}",
                    ))

                    # In CVE-Tracking eintragen
                    try:
                        self._execute("""
                            INSERT INTO dbai_security.cve_tracking
                                (cve_id, title, affected_pkg, affected_ver, source_url)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (cve_id) DO NOTHING
                        """, (
                            vuln.get("id", ""),
                            f"Vulnerability in {vuln.get('name', '')}",
                            vuln.get("name", ""),
                            vuln.get("version", ""),
                            vuln.get("more_info", ""),
                        ))
                    except Exception:
                        pass

        except (FileNotFoundError, json.JSONDecodeError):
            logger.debug("pip-audit nicht verfügbar")
        except Exception as e:
            logger.error("Dependency-Audit Fehler: %s", e)

        findings_count = self._store_findings(job_id, results)
        self._complete_scan_job(job_id, findings_count)

        logger.info("═══ Dependency-Audit abgeschlossen: %d Findings ═══", len(results))

    # ==================================================================
    # 12. Rate-Limiter
    # ==================================================================
    def check_rate_limit(self, target_type: str, target_value: str) -> bool:
        """
        Prüft ob ein Rate-Limit überschritten ist.
        Returns True wenn blockiert.
        """
        try:
            rows = self._execute("""
                SELECT id, max_requests, window_seconds, current_count,
                       window_start, is_blocked, blocked_until
                FROM dbai_security.rate_limits
                WHERE target_type = %s AND target_value = %s
            """, (target_type, target_value))

            if not rows:
                # Neues Rate-Limit anlegen
                default_limits = {
                    "ip": (100, 60),
                    "user": (200, 60),
                    "endpoint": (50, 60),
                    "global": (1000, 60),
                }
                max_req, window = default_limits.get(target_type, (100, 60))
                self._execute("""
                    INSERT INTO dbai_security.rate_limits
                        (target_type, target_value, max_requests, window_seconds)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (target_type, target_value) DO NOTHING
                """, (target_type, target_value, max_req, window))
                return False

            rl = rows[0]

            # Blockiert?
            if rl["is_blocked"]:
                if rl.get("blocked_until") and rl["blocked_until"] < datetime.now(timezone.utc):
                    # Block abgelaufen
                    self._execute("""
                        UPDATE dbai_security.rate_limits
                        SET is_blocked = FALSE, current_count = 0, window_start = now()
                        WHERE id = %s
                    """, (rl["id"],))
                    return False
                return True

            # Zeitfenster prüfen
            window_start = rl["window_start"]
            if window_start:
                elapsed = (datetime.now(timezone.utc) - window_start.replace(tzinfo=timezone.utc)).total_seconds()
                if elapsed > rl["window_seconds"]:
                    # Neues Fenster
                    self._execute("""
                        UPDATE dbai_security.rate_limits
                        SET current_count = 1, window_start = now()
                        WHERE id = %s
                    """, (rl["id"],))
                    return False

            # Counter erhöhen
            new_count = (rl["current_count"] or 0) + 1
            if new_count > rl["max_requests"]:
                # Rate-Limit überschritten
                self._execute("""
                    UPDATE dbai_security.rate_limits
                    SET is_blocked = TRUE,
                        blocked_until = now() + interval '5 minutes',
                        current_count = %s
                    WHERE id = %s
                """, (new_count, rl["id"]))

                # Logging
                self._execute("""
                    INSERT INTO dbai_security.security_responses
                        (trigger_type, response_type, description, details)
                    VALUES ('anomaly', 'rate_limit', %s, %s)
                """, (
                    f"Rate-Limit überschritten: {target_type}={target_value}",
                    Json({"type": target_type, "value": target_value, "count": new_count}),
                ))
                return True
            else:
                self._execute("""
                    UPDATE dbai_security.rate_limits
                    SET current_count = %s WHERE id = %s
                """, (new_count, rl["id"]))
                return False

        except Exception as e:
            logger.error("Rate-Limit Fehler: %s", e)
            return False

    # ==================================================================
    # DB-Hilfsfunktionen
    # ==================================================================
    def _create_scan_job(self, scan_type: str, target: str, target_type: str) -> str:
        """Erstellt einen neuen Scan-Job in der DB."""
        try:
            rows = self._execute("""
                INSERT INTO dbai_security.scan_jobs (scan_type, target, target_type, status)
                VALUES (%s, %s, %s, 'running')
                RETURNING id::TEXT
            """, (scan_type, target, target_type))
            return rows[0]["id"] if rows else ""
        except Exception as e:
            logger.error("Scan-Job Erstellung fehlgeschlagen: %s", e)
            return ""

    def _complete_scan_job(self, job_id: str, findings_count: int):
        """Markiert einen Scan-Job als abgeschlossen."""
        if not job_id:
            return
        try:
            self._execute("""
                UPDATE dbai_security.scan_jobs
                SET status = 'completed', findings_count = %s,
                    last_run_at = now(), updated_at = now()
                WHERE id = %s::UUID
            """, (findings_count, job_id))
        except Exception as e:
            logger.debug("Scan-Job Update Fehler: %s", e)

    def _fail_scan_job(self, job_id: str, error: str):
        """Markiert einen Scan-Job als fehlgeschlagen."""
        if not job_id:
            return
        try:
            self._execute("""
                UPDATE dbai_security.scan_jobs
                SET status = 'failed', config = config || %s, updated_at = now()
                WHERE id = %s::UUID
            """, (Json({"error": error}), job_id))
        except Exception as e:
            logger.debug("Scan-Job Fail-Update Fehler: %s", e)

    def _store_findings(self, job_id: Optional[str], findings: List[ScanResult]) -> int:
        """Speichert Scan-Ergebnisse in der Datenbank."""
        count = 0
        for f in findings:
            if f.severity == Severity.INFO.value:
                continue  # Info-Level nicht speichern

            try:
                self._execute("""
                    INSERT INTO dbai_security.vulnerability_findings (
                        scan_job_id, severity, category, title, description,
                        affected_target, affected_param, evidence, cve_id,
                        cvss_score, tool_output, remediation
                    ) VALUES (
                        %s::UUID, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    job_id if job_id else None,
                    f.severity, f.category, f.title, f.description,
                    f.affected_target, f.affected_param, f.evidence,
                    f.cve_id if f.cve_id else None,
                    f.cvss_score if f.cvss_score > 0 else None,
                    Json(f.tool_output), f.remediation,
                ))
                count += 1
            except Exception as e:
                logger.error("Finding Speicherung fehlgeschlagen: %s", e)

        return count

    # ==================================================================
    # 13. Rückkopplungsschleife (Feedback-Loop)
    # ==================================================================
    def run_feedback_loop(self):
        """
        Die zentrale Rückkopplungsschleife:
        1. Scans ausführen
        2. Findings analysieren
        3. Automatische Gegenmaßnahmen
        4. Firewall aktualisieren
        5. Erneut scannen
        """
        logger.info("════════════════════════════════════════════")
        logger.info("  SECURITY-IMMUNSYSTEM — Feedback-Loop     ")
        logger.info("  GhostShell OS Selbstschutz aktiv         ")
        logger.info("════════════════════════════════════════════")

        last_sqlmap = 0
        last_nmap = 0
        last_baseline = 0
        last_metrics = 0
        last_cleanup = 0
        last_tls = 0
        last_nuclei = 0
        last_dependency = 0

        while not self._shutdown.is_set():
            now = time.time()

            try:
                # --- SQLMap Self-Penetration ---
                if now - last_sqlmap >= SQLMAP_INTERVAL:
                    threading.Thread(
                        target=self._safe_run, args=(self.run_sqlmap_scan,),
                        daemon=True, name="sqlmap-scan",
                    ).start()
                    last_sqlmap = now

                # --- Nmap Port-Scan ---
                if now - last_nmap >= NMAP_INTERVAL:
                    threading.Thread(
                        target=self._safe_run, args=(self.run_nmap_scan,),
                        daemon=True, name="nmap-scan",
                    ).start()
                    last_nmap = now

                # --- Nuclei Web-Scan ---
                if now - last_nuclei >= SQLMAP_INTERVAL:
                    threading.Thread(
                        target=self._safe_run, args=(self.run_nuclei_scan,),
                        daemon=True, name="nuclei-scan",
                    ).start()
                    last_nuclei = now

                # --- Security-Baseline-Audit ---
                if now - last_baseline >= BASELINE_INTERVAL:
                    threading.Thread(
                        target=self._safe_run, args=(self.run_baseline_audit,),
                        daemon=True, name="baseline-audit",
                    ).start()
                    last_baseline = now

                # --- TLS-Check ---
                if now - last_tls >= TLS_CHECK_INTERVAL:
                    threading.Thread(
                        target=self._safe_run, args=(self.check_tls_certificates,),
                        daemon=True, name="tls-check",
                    ).start()
                    last_tls = now

                # --- Dependency-Audit ---
                if now - last_dependency >= BASELINE_INTERVAL:
                    threading.Thread(
                        target=self._safe_run, args=(self.run_dependency_audit,),
                        daemon=True, name="dep-audit",
                    ).start()
                    last_dependency = now

                # --- Security-Metriken ---
                if now - last_metrics >= METRICS_INTERVAL:
                    self._safe_run(self._update_metrics)
                    last_metrics = now

                # --- Cleanup ---
                if now - last_cleanup >= CLEANUP_INTERVAL:
                    self._safe_run(self._run_cleanup)
                    last_cleanup = now

                # --- Adaptive Reaktion ---
                self._adaptive_response()

            except Exception as e:
                logger.error("Feedback-Loop Fehler: %s", e)

            self._shutdown.wait(30)  # 30 Sekunden Pause zwischen Zyklen

    def _safe_run(self, func, *args, **kwargs):
        """Führt eine Funktion sicher aus (fängt alle Exceptions)."""
        try:
            func(*args, **kwargs)
        except Exception as e:
            logger.error("Sichere Ausführung fehlgeschlagen (%s): %s", func.__name__, e)

    def _update_metrics(self):
        """Security-Metriken aktualisieren."""
        try:
            self._execute("SELECT dbai_security.update_security_metrics()")
        except Exception as e:
            logger.debug("Metriken-Update Fehler: %s", e)

    def _run_cleanup(self):
        """Alte Daten bereinigen."""
        try:
            # Abgelaufene Bans aufheben
            self._execute("SELECT dbai_security.cleanup_expired_bans()")

            # Alte Traffic-Logs löschen (> 7 Tage)
            self._execute("""
                DELETE FROM dbai_security.network_traffic_log
                WHERE logged_at < now() - INTERVAL '7 days'
            """)

            # Alte Metriken löschen (> 30 Tage)
            self._execute("""
                DELETE FROM dbai_security.security_metrics
                WHERE recorded_at < now() - INTERVAL '30 days'
            """)

            # Alte Rate-Limit-Counter zurücksetzen
            self._execute("""
                UPDATE dbai_security.rate_limits
                SET current_count = 0, is_blocked = FALSE
                WHERE window_start < now() - INTERVAL '1 hour'
                AND is_blocked = FALSE
            """)

            # Abgelaufene Threat-Intel entfernen
            self._execute("""
                UPDATE dbai_security.threat_intelligence
                SET is_active = FALSE
                WHERE expires_at IS NOT NULL AND expires_at < now()
            """)

        except Exception as e:
            logger.debug("Cleanup Fehler: %s", e)

    def _adaptive_response(self):
        """
        Adaptive Reaktion: Analysiert aktuelle Bedrohungslage
        und passt Schutzmaßnahmen dynamisch an.
        """
        try:
            # Prüfe Bedrohungslevel der letzten Stunde
            rows = self._execute("""
                SELECT
                    (SELECT COUNT(*) FROM dbai_security.intrusion_events
                     WHERE detected_at > now() - INTERVAL '1 hour') AS ids_events,
                    (SELECT COUNT(*) FROM dbai_security.failed_auth_log
                     WHERE attempt_at > now() - INTERVAL '1 hour') AS auth_failures,
                    (SELECT COUNT(*) FROM dbai_security.honeypot_events
                     WHERE detected_at > now() - INTERVAL '1 hour') AS honeypot_hits,
                    (SELECT COUNT(*) FROM dbai_security.vulnerability_findings
                     WHERE status = 'open' AND severity IN ('critical', 'high')) AS critical_vulns
            """)

            if not rows:
                return

            status = rows[0]
            ids_events = status.get("ids_events", 0) or 0
            auth_failures = status.get("auth_failures", 0) or 0
            honeypot_hits = status.get("honeypot_hits", 0) or 0
            critical_vulns = status.get("critical_vulns", 0) or 0

            threat_level = (
                ids_events * 2 + auth_failures + honeypot_hits * 5 + critical_vulns * 10
            )

            if threat_level > 100:
                logger.warning("HOHE BEDROHUNGSLAGE (Score: %d) — Verschärfe Schutzmaßnahmen", threat_level)
                # Aggressivere Rate-Limits
                self._execute("""
                    UPDATE dbai_security.rate_limits
                    SET max_requests = GREATEST(max_requests / 2, 10)
                    WHERE target_type = 'global'
                """)

                # Kürzere Ban-Zeiten → mehr Bans
                global F2B_MAX_ATTEMPTS
                F2B_MAX_ATTEMPTS = max(1, F2B_MAX_ATTEMPTS - 1)

            elif threat_level > 50:
                logger.info("ERHÖHTE BEDROHUNGSLAGE (Score: %d)", threat_level)

            elif threat_level < 5:
                # Normale Lage — Limits zurücksetzen
                F2B_MAX_ATTEMPTS = int(os.getenv("DBAI_F2B_MAX_ATTEMPTS", "3"))

        except Exception as e:
            logger.debug("Adaptive Response Fehler: %s", e)

    # ==================================================================
    # Daemon-Modus
    # ==================================================================
    def start_daemon(self):
        """
        Startet das Security-Immunsystem als Daemon.
        Alle Module laufen parallel.
        """
        logger.info("════════════════════════════════════════════════")
        logger.info("  DBAI SECURITY-IMMUNSYSTEM v0.15.0            ")
        logger.info("  GhostShell OS — Betriebssystem mit Immunsystem")
        logger.info("════════════════════════════════════════════════")

        # 1. Firewall aufsetzen
        self._safe_run(self.setup_firewall)

        # 2. DNS-Sinkhole laden
        self._safe_run(self.update_dns_sinkhole)

        # 3. Honeypots starten
        hp_thread = threading.Thread(
            target=self._safe_run, args=(self.start_honeypots,),
            daemon=True, name="honeypots",
        )
        hp_thread.start()
        self._threads.append(hp_thread)

        # 4. IDS-Monitor starten
        ids_thread = threading.Thread(
            target=self._safe_run, args=(self.start_ids_monitor,),
            daemon=True, name="ids-monitor",
        )
        ids_thread.start()
        self._threads.append(ids_thread)

        # 5. PostgreSQL-Log-Monitor (Fail2Ban)
        f2b_thread = threading.Thread(
            target=self._safe_run, args=(self.monitor_postgresql_logs,),
            daemon=True, name="fail2ban",
        )
        f2b_thread.start()
        self._threads.append(f2b_thread)

        # 6. Feedback-Loop (Hauptschleife)
        self.run_feedback_loop()

    def shutdown(self):
        """Fährt das Immunsystem sauber herunter."""
        logger.info("Security-Immunsystem wird heruntergefahren…")
        self._shutdown.set()

        for t in self._threads:
            t.join(timeout=5)

        if self.conn and not self.conn.closed:
            self.conn.close()

        logger.info("Security-Immunsystem heruntergefahren.")


# ===========================================================================
# API-Funktionen (für Import durch ghost-api)
# ===========================================================================
def get_security_status(conn) -> dict:
    """Liefert den aktuellen Security-Status für das Dashboard."""
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    (SELECT COUNT(*) FROM dbai_security.vulnerability_findings
                     WHERE status IN ('open', 'confirmed')) AS open_vulns,
                    (SELECT COUNT(*) FROM dbai_security.vulnerability_findings
                     WHERE status = 'open' AND severity = 'critical') AS critical_vulns,
                    (SELECT COUNT(*) FROM dbai_security.ip_bans
                     WHERE is_active = TRUE) AS active_bans,
                    (SELECT COUNT(*) FROM dbai_security.intrusion_events
                     WHERE detected_at > now() - INTERVAL '24 hours') AS ids_24h,
                    (SELECT COUNT(*) FROM dbai_security.failed_auth_log
                     WHERE attempt_at > now() - INTERVAL '24 hours') AS failed_auth_24h,
                    (SELECT COUNT(*) FROM dbai_security.scan_jobs
                     WHERE status = 'completed'
                     AND last_run_at > now() - INTERVAL '24 hours') AS scans_24h,
                    (SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE compliant) / NULLIF(COUNT(*), 0), 1)
                     FROM dbai_security.security_baselines) AS compliance_pct,
                    (SELECT COUNT(*) FROM dbai_security.threat_intelligence
                     WHERE is_active = TRUE) AS threat_indicators,
                    (SELECT COUNT(*) FROM dbai_security.honeypot_events
                     WHERE detected_at > now() - INTERVAL '24 hours') AS honeypot_24h
            """)
            return dict(cur.fetchone())
    except Exception as e:
        logger.error("Security-Status Abfrage fehlgeschlagen: %s", e)
        return {"error": str(e)}


def log_failed_auth_attempt(conn, source_ip: str, username: str = None,
                             auth_type: str = "api", port: int = 3000) -> bool:
    """
    API-Funktion: Fehlgeschlagenen Login registrieren.
    Returns True wenn IP gebannt wurde.
    """
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO dbai_security.failed_auth_log
                    (source_ip, username, auth_type, service_port)
                VALUES (%s, %s, %s, %s)
            """, (source_ip, username, auth_type, port))

            cur.execute(
                "SELECT dbai_security.check_and_ban_ip(%s) AS banned",
                (source_ip,)
            )
            result = cur.fetchone()
            conn.commit()
            return result.get("banned", False) if result else False
    except Exception as e:
        logger.error("Failed-Auth-Logging Fehler: %s", e)
        return False


def is_ip_banned(conn, ip: str) -> bool:
    """Prüft ob eine IP gebannt ist."""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM dbai_security.ip_bans
                    WHERE ip_address = %s::INET
                    AND is_active = TRUE
                    AND (expires_at IS NULL OR expires_at > now())
                )
            """, (ip,))
            return cur.fetchone()[0]
    except Exception:
        return False


def get_threat_score(conn, ip: str) -> int:
    """Berechnet den Threat-Score einer IP."""
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT dbai_security.calculate_threat_score(%s::INET)", (ip,))
            return cur.fetchone()[0] or 0
    except Exception:
        return 0


# ===========================================================================
# Hauptprogramm (Daemon-Modus)
# ===========================================================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="DBAI Security-Immunsystem")
    parser.add_argument("--daemon", action="store_true", help="Als Daemon starten")
    parser.add_argument("--scan", choices=["sqlmap", "nmap", "nuclei", "baseline", "all"],
                        help="Einzelnen Scan ausführen")
    parser.add_argument("--setup-firewall", action="store_true", help="Firewall einrichten")
    parser.add_argument("--status", action="store_true", help="Security-Status anzeigen")
    args = parser.parse_args()

    immunsystem = SecurityImmunsystem()

    if args.daemon:
        immunsystem.start_daemon()
    elif args.scan:
        if args.scan == "sqlmap":
            immunsystem.run_sqlmap_scan()
        elif args.scan == "nmap":
            immunsystem.run_nmap_scan()
        elif args.scan == "nuclei":
            immunsystem.run_nuclei_scan()
        elif args.scan == "baseline":
            immunsystem.run_baseline_audit()
        elif args.scan == "all":
            immunsystem.run_sqlmap_scan()
            immunsystem.run_nmap_scan()
            immunsystem.run_nuclei_scan()
            immunsystem.run_baseline_audit()
            immunsystem.run_dependency_audit()
    elif args.setup_firewall:
        immunsystem.setup_firewall()
    elif args.status:
        conn = psycopg2.connect(**DB_CONFIG)
        status = get_security_status(conn)
        print(json.dumps(status, indent=2, default=str))
        conn.close()
    else:
        parser.print_help()
