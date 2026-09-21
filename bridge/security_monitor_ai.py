#!/usr/bin/env python3
"""
DBAI Security Monitor AI — Ghost-gestützte Sicherheitsanalyse
==============================================================
Verbindet das Security-Immunsystem mit dem Ghost-System.
Der Security-Monitor-Ghost (Rolle "security") analysiert Events,
bewertet Bedrohungen und empfiehlt/ergreift Gegenmaßnahmen.

Architektur:
┌─────────────────┐   Trigger/NOTIFY    ┌──────────────────────┐
│  dbai_security   ├────────────────────►│ SecurityMonitorAI    │
│  (Events/Findings)│                    │  (dieser Code)       │
└─────────────────┘                     └──────┬───────────────┘
                                               │ ask_ghost('security', ...)
                                               ▼
                                        ┌──────────────────────┐
                                        │  GhostDispatcher     │
                                        │  (LLM-Inferenz)      │
                                        └──────┬───────────────┘
                                               │ Empfehlungen
                                               ▼
                                        ┌──────────────────────┐
                                        │  Auto-Response       │
                                        │  (IP-Ban, Regeln...) │
                                        └──────────────────────┘
"""

import os
import json
import time
import logging
import threading
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

import psycopg2
import psycopg2.extensions
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("dbai.security.ai")

# ---------------------------------------------------------------------------
# DB-Konfiguration
# ---------------------------------------------------------------------------
DB_CONFIG = {
    "host": os.getenv("DBAI_DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DBAI_DB_PORT", "5432")),
    "dbname": os.getenv("DBAI_DB_NAME", "dbai"),
    "user": os.getenv("DBAI_DB_USER", "dbai_system"),
    "password": os.getenv("DBAI_DB_PASSWORD", ""),
}


class SecurityMonitorAI:
    """
    KI-gesteuerte Sicherheitsanalyse.
    Hört auf pg_notify('security_ai_task') und lässt den Security-Ghost
    Events analysieren, Bedrohungen bewerten und Maßnahmen empfehlen.
    """

    ROLE_NAME = "security"

    # System-Prompt-Fragmente für verschiedene Task-Typen
    TASK_PROMPTS = {
        "threat_analysis": (
            "Analysiere die folgende Bedrohung und bewerte das Risiko. "
            "Berücksichtige bekannte Angriffsmuster (MITRE ATT&CK). "
            "Gib eine strukturierte Bewertung mit risk_level, Beschreibung "
            "und empfohlenen Maßnahmen."
        ),
        "vuln_assessment": (
            "Bewerte die folgende Schwachstelle im Kontext des DBAI-Systems. "
            "Prüfe ob ein bekannter CVE vorliegt, wie ausnutzbar die Schwachstelle ist, "
            "und welche Gegenmaßnahmen sofort ergriffen werden sollten."
        ),
        "incident_response": (
            "Es wurde ein Sicherheitsvorfall erkannt. Analysiere die Daten, "
            "bewerte die Schwere, identifiziere den Angriffsvektor und "
            "empfiehl konkrete Sofortmaßnahmen und langfristige Absicherung."
        ),
        "baseline_audit": (
            "Prüfe die folgenden Security-Baseline-Ergebnisse. "
            "Identifiziere alle nicht-konformen Checks, bewerte deren Risiko "
            "und empfiehl konkrete Korrekturen in Reihenfolge der Dringlichkeit."
        ),
        "anomaly_detection": (
            "Analysiere die folgenden Daten auf Anomalien. "
            "Suche nach ungewöhnlichen Mustern, Zeitabweichungen, "
            "verdächtigen IP-Adressen oder atypischem Verhalten."
        ),
        "log_analysis": (
            "Analysiere die folgenden Log-Daten auf Sicherheitsrelevanz. "
            "Identifiziere Brute-Force-Versuche, Lateral Movement, "
            "Privilege Escalation oder andere verdächtige Aktivitäten."
        ),
        "network_forensics": (
            "Führe eine Netzwerk-Forensik durch. Analysiere Traffic-Muster, "
            "identifiziere verdächtige Verbindungen, C2-Kommunikation "
            "oder Datenexfiltration."
        ),
        "risk_scoring": (
            "Berechne einen Gesamt-Risikoscore für das System basierend "
            "auf den bereitgestellten Metriken. Berücksichtige alle "
            "Sicherheitssubsysteme und gewichte nach Relevanz."
        ),
        "policy_recommendation": (
            "Empfiehl basierend auf den aktuellen Sicherheitsdaten "
            "Verbesserungen der Security-Policies. "
            "Berücksichtige CIS-Benchmarks und Best Practices."
        ),
        "periodic_report": (
            "Erstelle einen strukturierten Sicherheitsbericht. "
            "Fasse die wichtigsten Ereignisse zusammen, bewerte den "
            "Gesamtzustand und gib priorisierte Empfehlungen."
        ),
    }

    def __init__(self, conn=None, ghost_dispatcher=None):
        """
        Args:
            conn: psycopg2-Verbindung (oder None → eigene Verbindung)
            ghost_dispatcher: GhostDispatcher-Instanz für direkte Inferenz
        """
        self._own_conn = conn is None
        self.conn = conn
        self.listen_conn = None
        self.ghost_dispatcher = ghost_dispatcher
        self._running = False
        self._lock = threading.Lock()
        self._config_cache = {}
        self._config_cache_ts = 0

    # ------------------------------------------------------------------
    # Datenbank
    # ------------------------------------------------------------------
    def connect(self):
        """Verbindungen herstellen."""
        if self.conn is None or self.conn.closed:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.conn.autocommit = False

        # Separater LISTEN-Kanal (autocommit)
        self.listen_conn = psycopg2.connect(**DB_CONFIG)
        self.listen_conn.set_isolation_level(
            psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT
        )
        logger.info("Security-Monitor-AI: DB-Verbindungen hergestellt")

    def _query(self, sql: str, params=None) -> list:
        """Führt Query aus, returned list of dicts."""
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
                self.conn.commit()
                return [dict(r) for r in rows]
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception:
                pass
            logger.error("DB-Query Fehler: %s", e)
            return []

    def _execute(self, sql: str, params=None):
        """Führt Statement ohne Ergebnis aus."""
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
            self.conn.commit()
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception:
                pass
            logger.error("DB-Execute Fehler: %s", e)

    # ------------------------------------------------------------------
    # Konfiguration
    # ------------------------------------------------------------------
    def get_config(self, key: str, default=None):
        """Liest einen Config-Wert (mit 60s Cache)."""
        now = time.time()
        if now - self._config_cache_ts > 60:
            rows = self._query("SELECT key, value FROM dbai_security.ai_config")
            self._config_cache = {r["key"]: r["value"] for r in rows}
            self._config_cache_ts = now

        val = self._config_cache.get(key, default)
        # JSONB-Werte auspacken
        if isinstance(val, str):
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
        return val

    def update_config(self, key: str, value, updated_by: str = "system"):
        """Aktualisiert einen Config-Wert."""
        json_val = json.dumps(value) if not isinstance(value, str) else value
        self._execute("""
            INSERT INTO dbai_security.ai_config (key, value, updated_at, updated_by)
            VALUES (%s, %s::JSONB, NOW(), %s)
            ON CONFLICT (key) DO UPDATE SET
                value = EXCLUDED.value, updated_at = NOW(), updated_by = EXCLUDED.updated_by
        """, (key, json_val, updated_by))
        self._config_cache_ts = 0  # Cache invalidieren

    # ------------------------------------------------------------------
    # KI-Analyse
    # ------------------------------------------------------------------
    def analyze(self, task_id: str) -> Dict[str, Any]:
        """
        Analysiert einen Security-AI-Task.
        Baut den Prompt, fragt den Security-Ghost, speichert das Ergebnis.
        """
        # Task laden
        rows = self._query(
            "SELECT * FROM dbai_security.ai_tasks WHERE id = %s::UUID",
            (task_id,)
        )
        if not rows:
            return {"error": f"Task {task_id} nicht gefunden"}

        task = rows[0]
        task_type = task["task_type"]
        input_data = task["input_data"] or {}

        # Task als processing markieren
        self._execute("""
            UPDATE dbai_security.ai_tasks
            SET state = 'processing', started_at = NOW()
            WHERE id = %s::UUID
        """, (task_id,))

        start_time = time.monotonic()

        try:
            # Kontext sammeln (relevante Daten für die Analyse)
            context = self._build_analysis_context(task_type, input_data)

            # Prompt zusammenbauen
            task_prompt = self.TASK_PROMPTS.get(task_type, "Analysiere die folgenden Sicherheitsdaten.")
            user_prompt = self._build_prompt(task_type, task_prompt, input_data, context)

            # KI-Inferenz
            result = self._ask_security_ghost(user_prompt)

            duration_ms = round((time.monotonic() - start_time) * 1000)

            if "error" in result:
                self._execute("""
                    UPDATE dbai_security.ai_tasks
                    SET state = 'failed', error_message = %s,
                        completed_at = NOW(), processing_ms = %s
                    WHERE id = %s::UUID
                """, (result["error"], duration_ms, task_id))
                return result

            # Ergebnis parsen
            ai_text = result.get("content", result.get("text", ""))
            parsed = self._parse_ai_response(ai_text)

            # Ergebnis speichern
            self._execute("""
                UPDATE dbai_security.ai_tasks
                SET state = 'completed',
                    output_data = %s::JSONB,
                    ai_assessment = %s,
                    risk_level = %s,
                    confidence = %s,
                    recommended_actions = %s::JSONB,
                    completed_at = NOW(),
                    processing_ms = %s
                WHERE id = %s::UUID
            """, (
                json.dumps(parsed, default=str),
                ai_text,
                parsed.get("risk_level", "info"),
                parsed.get("confidence", 0.5),
                json.dumps(parsed.get("recommended_actions", []), default=str),
                duration_ms,
                task_id,
            ))

            # Analysis-Log (Append-Only)
            self._execute("""
                INSERT INTO dbai_security.ai_analysis_log
                    (task_id, analysis_type, input_summary, output_summary,
                     risk_level, tokens_used, model_name, duration_ms, metadata)
                VALUES (%s::UUID, %s, %s, %s, %s, %s, %s, %s, %s::JSONB)
            """, (
                task_id, task_type,
                json.dumps(input_data, default=str)[:500],
                ai_text[:1000],
                parsed.get("risk_level", "info"),
                result.get("tokens_used", 0),
                result.get("model", "unknown"),
                duration_ms,
                json.dumps({"confidence": parsed.get("confidence", 0.5)}, default=str),
            ))

            # Auto-Response wenn aktiviert und risk_level >= threshold
            if parsed.get("risk_level") in ("critical", "high"):
                self._handle_auto_response(task_id, task_type, input_data, parsed)

            logger.info(
                "Security-AI: Task %s abgeschlossen — %s, risk=%s, %dms",
                task_id, task_type, parsed.get("risk_level"), duration_ms
            )

            return {
                "task_id": task_id,
                "status": "completed",
                "assessment": ai_text,
                "risk_level": parsed.get("risk_level", "info"),
                "confidence": parsed.get("confidence", 0.5),
                "recommended_actions": parsed.get("recommended_actions", []),
                "duration_ms": duration_ms,
                "tokens_used": result.get("tokens_used", 0),
            }

        except Exception as e:
            duration_ms = round((time.monotonic() - start_time) * 1000)
            self._execute("""
                UPDATE dbai_security.ai_tasks
                SET state = 'failed', error_message = %s,
                    completed_at = NOW(), processing_ms = %s
                WHERE id = %s::UUID
            """, (str(e), duration_ms, task_id))
            logger.error("Security-AI Task %s fehlgeschlagen: %s", task_id, e)
            return {"error": str(e)}

    # ------------------------------------------------------------------
    # Kontext-Builder
    # ------------------------------------------------------------------
    def _build_analysis_context(self, task_type: str, input_data: dict) -> dict:
        """Sammelt relevanten Kontext aus der DB für die Analyse."""
        context = {}

        if task_type in ("threat_analysis", "incident_response", "anomaly_detection"):
            # Aktive Bans
            bans = self._query(
                "SELECT ip_address, reason, source FROM dbai_security.ip_bans "
                "WHERE is_active = TRUE LIMIT 20"
            )
            context["active_bans"] = len(bans)
            context["ban_ips"] = [b["ip_address"] for b in bans[:10]]

            # Letzte Intrusions
            intrusions = self._query("""
                SELECT event_type, source_ip, classification, priority, COUNT(*) AS cnt
                FROM dbai_security.intrusion_events
                WHERE detected_at > NOW() - INTERVAL '6 hours'
                GROUP BY event_type, source_ip, classification, priority
                ORDER BY cnt DESC LIMIT 10
            """)
            context["recent_intrusion_patterns"] = intrusions

            # Failed Auth
            auth = self._query("""
                SELECT source_ip, auth_type, COUNT(*) AS attempts
                FROM dbai_security.failed_auth_log
                WHERE attempt_at > NOW() - INTERVAL '6 hours'
                GROUP BY source_ip, auth_type
                ORDER BY attempts DESC LIMIT 10
            """)
            context["failed_auth_summary"] = auth

        elif task_type == "vuln_assessment":
            # Ähnliche Schwachstellen
            if input_data.get("cve_id"):
                cves = self._query("""
                    SELECT cve_id, title, cvss_score, is_patched
                    FROM dbai_security.cve_tracking
                    WHERE cve_id = %s
                """, (input_data["cve_id"],))
                context["cve_info"] = cves

            # Offene Vulns nach Severity
            vulns = self._query("""
                SELECT severity, COUNT(*) AS cnt
                FROM dbai_security.vulnerability_findings
                WHERE status = 'open'
                GROUP BY severity
            """)
            context["open_vulns_by_severity"] = {v["severity"]: v["cnt"] for v in vulns}

        elif task_type == "baseline_audit":
            baselines = self._query("""
                SELECT component, check_name, expected_value, current_value,
                       compliant, severity
                FROM dbai_security.security_baselines
                WHERE NOT compliant
                ORDER BY CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2
                         WHEN 'medium' THEN 3 ELSE 4 END
                LIMIT 20
            """)
            context["non_compliant_baselines"] = baselines

        elif task_type in ("risk_scoring", "periodic_report"):
            # Alle Subsystem-Metriken
            context["open_vulns"] = self._query(
                "SELECT severity, COUNT(*) AS cnt FROM dbai_security.vulnerability_findings "
                "WHERE status = 'open' GROUP BY severity"
            )
            context["active_bans"] = self._query(
                "SELECT COUNT(*) AS cnt FROM dbai_security.ip_bans WHERE is_active = TRUE"
            )
            context["intrusions_24h"] = self._query(
                "SELECT COUNT(*) AS cnt FROM dbai_security.intrusion_events "
                "WHERE detected_at > NOW() - INTERVAL '24 hours'"
            )
            context["failed_auth_24h"] = self._query(
                "SELECT COUNT(*) AS cnt FROM dbai_security.failed_auth_log "
                "WHERE attempt_at > NOW() - INTERVAL '24 hours'"
            )
            context["compliance"] = self._query("""
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE compliant) AS compliant,
                    ROUND(100.0 * COUNT(*) FILTER (WHERE compliant) / NULLIF(COUNT(*), 0), 1) AS pct
                FROM dbai_security.security_baselines
            """)
            context["honeypot_24h"] = self._query(
                "SELECT COUNT(*) AS cnt FROM dbai_security.honeypot_events "
                "WHERE detected_at > NOW() - INTERVAL '24 hours'"
            )
            context["tls_expiring"] = self._query(
                "SELECT COUNT(*) AS cnt FROM dbai_security.tls_certificates "
                "WHERE expires_at < NOW() + INTERVAL '30 days'"
            )

        return context

    def _build_prompt(self, task_type: str, task_prompt: str,
                      input_data: dict, context: dict) -> str:
        """Baut den vollständigen User-Prompt zusammen."""
        parts = [task_prompt, "", "## Eingabedaten:"]
        parts.append(f"```json\n{json.dumps(input_data, indent=2, default=str)}\n```")

        if context:
            parts.append("")
            parts.append("## Kontext (aktuelle System-Sicherheitslage):")
            parts.append(f"```json\n{json.dumps(context, indent=2, default=str)}\n```")

        parts.append("")
        parts.append("## Gewünschtes Ausgabeformat:")
        parts.append("Antworte als JSON mit folgender Struktur:")
        parts.append("```json")
        parts.append(json.dumps({
            "risk_level": "critical|high|medium|low|info",
            "confidence": 0.85,
            "summary": "Kurze Zusammenfassung der Bedrohung",
            "details": "Ausführliche Analyse",
            "recommended_actions": [
                {"action": "ban_ip", "target": "1.2.3.4", "reason": "...", "priority": 1},
                {"action": "update_rule", "target": "...", "reason": "...", "priority": 2}
            ],
            "indicators_of_compromise": ["..."],
            "mitre_techniques": ["T1110 - Brute Force"],
        }, indent=2))
        parts.append("```")

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Ghost-Kommunikation
    # ------------------------------------------------------------------
    def _ask_security_ghost(self, user_prompt: str) -> dict:
        """
        Fragt den Security-Ghost.
        Nutzt den GhostDispatcher direkt (wenn vorhanden) oder die DB-Task-Queue.
        """
        temperature = self.get_config("analysis_temperature", 0.2)
        max_tokens = self.get_config("analysis_max_tokens", 2048)

        # Direkte Inferenz über GhostDispatcher
        if self.ghost_dispatcher and self.ROLE_NAME in self._get_active_models():
            model_name = self._get_active_models().get(self.ROLE_NAME)
            system_prompt = self._get_role_prompt()
            result = self.ghost_dispatcher.generate(
                model_name, system_prompt, user_prompt,
                {"temperature": temperature, "max_tokens": max_tokens}
            )
            if result and "error" not in result:
                return {
                    "content": result.get("content", ""),
                    "tokens_used": result.get("tokens_used", 0),
                    "model": model_name,
                }
            # Fallback auf Task-Queue bei Fehler
            logger.warning("Direkte Inferenz fehlgeschlagen: %s — Fallback auf Task-Queue",
                           result.get("error") if result else "No result")

        # Fallback: DB-basierte Task-Queue (ask_ghost)
        return self._ask_via_task_queue(user_prompt, temperature, max_tokens)

    def _ask_via_task_queue(self, user_prompt: str, temperature: float, max_tokens: int) -> dict:
        """Fragt den Ghost über die DB-Task-Queue (asynchron → synchron polling)."""
        try:
            rows = self._query(
                "SELECT dbai_llm.ask_ghost(%s, %s, %s::JSONB) AS result",
                (self.ROLE_NAME, user_prompt,
                 json.dumps({"temperature": temperature, "max_tokens": max_tokens}))
            )
            if not rows:
                return {"error": "ask_ghost returned empty"}

            result = rows[0].get("result", {})
            if isinstance(result, str):
                result = json.loads(result)

            task_id = result.get("task_id")
            if not task_id:
                return {"error": result.get("error", "Kein task_id erhalten")}

            # Polling auf Task-Ergebnis (max 120 Sekunden)
            for _ in range(240):
                time.sleep(0.5)
                task_rows = self._query(
                    "SELECT state, output_data, tokens_used, error_message "
                    "FROM dbai_llm.task_queue WHERE id = %s::UUID",
                    (task_id,)
                )
                if not task_rows:
                    continue

                task = task_rows[0]
                if task["state"] == "completed":
                    output = task["output_data"] or {}
                    if isinstance(output, str):
                        output = json.loads(output)
                    return {
                        "content": output.get("content", output.get("response", "")),
                        "tokens_used": task.get("tokens_used", 0),
                        "model": "via_task_queue",
                    }
                elif task["state"] == "failed":
                    return {"error": task.get("error_message", "Task fehlgeschlagen")}

            return {"error": "Timeout — Ghost hat nach 120s nicht geantwortet"}
        except Exception as e:
            return {"error": f"Task-Queue-Fehler: {e}"}

    def _get_active_models(self) -> dict:
        """Gibt dict {role_name → model_name} zurück."""
        rows = self._query("""
            SELECT r.name AS role, m.name AS model
            FROM dbai_llm.active_ghosts ag
            JOIN dbai_llm.ghost_roles r ON ag.role_id = r.id
            JOIN dbai_llm.ghost_models m ON ag.model_id = m.id
            WHERE ag.state = 'active'
        """)
        return {r["role"]: r["model"] for r in rows}

    def _get_role_prompt(self) -> str:
        """Lädt den System-Prompt der Security-Rolle."""
        rows = self._query(
            "SELECT system_prompt FROM dbai_llm.ghost_roles WHERE name = %s",
            (self.ROLE_NAME,)
        )
        if rows:
            return rows[0]["system_prompt"]
        return "Du bist der Security-Monitor von DBAI."

    # ------------------------------------------------------------------
    # Auto-Response
    # ------------------------------------------------------------------
    def _handle_auto_response(self, task_id: str, task_type: str,
                               input_data: dict, parsed: dict):
        """Führt automatische Gegenmaßnahmen aus wenn aktiviert."""
        if not self.get_config("auto_response_enabled", True):
            return

        recommended = parsed.get("recommended_actions", [])
        if not isinstance(recommended, list) or not recommended:
            return

        for action in recommended:
            if not isinstance(action, dict):
                continue

            action_type = action.get("action", "")

            # IP-Ban
            if action_type == "ban_ip" and self.get_config("auto_ban_enabled", True):
                ip = action.get("target", action.get("ip"))
                reason = action.get("reason", f"KI-Analyse: {task_type}")
                max_hours = self.get_config("max_auto_ban_hours", 24)
                if ip:
                    self._auto_ban_ip(ip, reason, max_hours, task_id)

            # Schwachstelle mitigieren
            elif action_type == "mitigate_vuln" and self.get_config("auto_mitigate_enabled", False):
                vuln_id = action.get("target", action.get("vuln_id"))
                if vuln_id:
                    self._auto_mitigate(vuln_id, task_id)

            # Alert erstellen
            elif action_type in ("alert", "notify", "escalate"):
                self._create_alert(action, task_id, task_type)

    def _auto_ban_ip(self, ip: str, reason: str, hours: int, task_id: str):
        """Bannt eine IP automatisch."""
        try:
            self._execute("""
                INSERT INTO dbai_security.ip_bans
                    (ip_address, reason, ban_type, source, expires_at)
                VALUES (%s::INET, %s, 'temporary', 'ai_monitor',
                        NOW() + (%s || ' hours')::INTERVAL)
                ON CONFLICT (ip_address, cidr_mask) DO UPDATE SET
                    is_active = TRUE, banned_at = NOW(),
                    reason = EXCLUDED.reason, expires_at = EXCLUDED.expires_at
            """, (ip, f"[KI] {reason}", str(hours)))

            self._execute("""
                INSERT INTO dbai_security.security_responses
                    (trigger_type, response_type, description, success)
                VALUES ('ai_analysis', 'auto_ban',
                        %s, TRUE)
            """, (f"KI-Auto-Ban: {ip} — {reason} (Task: {task_id})",))

            # AI-Task als auto_executed markieren
            self._execute("""
                UPDATE dbai_security.ai_tasks SET auto_executed = TRUE
                WHERE id = %s::UUID
            """, (task_id,))

            logger.info("KI Auto-Ban: %s — %s", ip, reason)
        except Exception as e:
            logger.error("Auto-Ban fehlgeschlagen für %s: %s", ip, e)

    def _auto_mitigate(self, vuln_id: str, task_id: str):
        """Mitigiert eine Schwachstelle automatisch."""
        try:
            self._execute("""
                UPDATE dbai_security.vulnerability_findings
                SET status = 'mitigated', auto_mitigated = TRUE, resolved_at = NOW()
                WHERE id = %s::UUID AND status = 'open'
            """, (vuln_id,))

            self._execute("""
                INSERT INTO dbai_security.security_responses
                    (trigger_type, response_type, description, success)
                VALUES ('ai_analysis', 'auto_mitigate',
                        %s, TRUE)
            """, (f"KI-Auto-Mitigation: Vuln {vuln_id} (Task: {task_id})",))

            self._execute("""
                UPDATE dbai_security.ai_tasks SET auto_executed = TRUE
                WHERE id = %s::UUID
            """, (task_id,))

            logger.info("KI Auto-Mitigation: Vuln %s", vuln_id)
        except Exception as e:
            logger.error("Auto-Mitigation fehlgeschlagen für %s: %s", vuln_id, e)

    def _create_alert(self, action: dict, task_id: str, task_type: str):
        """Erstellt einen Sicherheits-Alert."""
        try:
            self._execute("""
                INSERT INTO dbai_security.security_responses
                    (trigger_type, response_type, description, success)
                VALUES ('ai_analysis', 'alert', %s, TRUE)
            """, (f"KI-Alert: {action.get('reason', task_type)} (Task: {task_id})",))
        except Exception as e:
            logger.debug("Alert-Erstellung fehlgeschlagen: %s", e)

    # ------------------------------------------------------------------
    # Hilfsfunktionen: Manuelle Analyse-Trigger
    # ------------------------------------------------------------------
    def analyze_current_threats(self) -> str:
        """Erstellt eine sofortige Bedrohungsanalyse."""
        rows = self._query("SELECT dbai_security.create_ai_task('risk_scoring', '{}', 'manual', 'user') AS id")
        task_id = rows[0]["id"] if rows else None
        if task_id:
            return self.analyze(str(task_id))
        return {"error": "Task-Erstellung fehlgeschlagen"}

    def analyze_specific_ip(self, ip: str) -> dict:
        """Analysiert eine spezifische IP-Adresse."""
        # Daten über diese IP sammeln
        intrusions = self._query("""
            SELECT event_type, classification, priority, COUNT(*) AS cnt,
                   MAX(detected_at) AS last_seen
            FROM dbai_security.intrusion_events
            WHERE source_ip = %s::INET
            GROUP BY event_type, classification, priority
        """, (ip,))

        auth_fails = self._query("""
            SELECT auth_type, COUNT(*) AS attempts, MAX(attempt_at) AS last
            FROM dbai_security.failed_auth_log
            WHERE source_ip = %s::INET
            GROUP BY auth_type
        """, (ip,))

        honeypot = self._query("""
            SELECT honeypot_type, interaction, COUNT(*) AS cnt
            FROM dbai_security.honeypot_events
            WHERE source_ip = %s::INET
            GROUP BY honeypot_type, interaction
        """, (ip,))

        threat_score = self._query(
            "SELECT dbai_security.calculate_threat_score(%s::INET) AS score", (ip,)
        )

        input_data = {
            "ip": ip,
            "threat_score": threat_score[0]["score"] if threat_score else 0,
            "intrusion_events": intrusions,
            "failed_auth": auth_fails,
            "honeypot_triggers": honeypot,
        }

        rows = self._query(
            "SELECT dbai_security.create_ai_task('threat_analysis', %s::JSONB, 'manual', 'user') AS id",
            (json.dumps(input_data, default=str),)
        )
        task_id = rows[0]["id"] if rows else None
        if task_id:
            return self.analyze(str(task_id))
        return {"error": "Task-Erstellung fehlgeschlagen"}

    def generate_security_report(self) -> dict:
        """Generiert einen periodischen Sicherheitsbericht."""
        rows = self._query(
            "SELECT dbai_security.create_ai_task('periodic_report', '{}', 'manual', 'user') AS id"
        )
        task_id = rows[0]["id"] if rows else None
        if task_id:
            return self.analyze(str(task_id))
        return {"error": "Task-Erstellung fehlgeschlagen"}

    def audit_baselines(self) -> dict:
        """Führt ein KI-gestütztes Baseline-Audit durch."""
        rows = self._query(
            "SELECT dbai_security.create_ai_task('baseline_audit', '{}', 'manual', 'user') AS id"
        )
        task_id = rows[0]["id"] if rows else None
        if task_id:
            return self.analyze(str(task_id))
        return {"error": "Task-Erstellung fehlgeschlagen"}

    # ------------------------------------------------------------------
    # AI Response Parser
    # ------------------------------------------------------------------
    def _parse_ai_response(self, text: str) -> dict:
        """Parst die KI-Antwort und extrahiert strukturierte Daten."""
        result = {
            "risk_level": "info",
            "confidence": 0.5,
            "summary": "",
            "details": text,
            "recommended_actions": [],
            "indicators_of_compromise": [],
            "mitre_techniques": [],
        }

        # Versuche JSON aus der Antwort zu extrahieren
        try:
            # JSON-Block suchen
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(1))
            else:
                # Versuche die komplette Antwort als JSON zu parsen
                parsed = json.loads(text)

            if isinstance(parsed, dict):
                for key in result:
                    if key in parsed:
                        result[key] = parsed[key]

                # risk_level validieren
                if result["risk_level"] not in ("critical", "high", "medium", "low", "info"):
                    result["risk_level"] = "info"

                # confidence validieren
                try:
                    result["confidence"] = max(0.0, min(1.0, float(result["confidence"])))
                except (ValueError, TypeError):
                    result["confidence"] = 0.5

        except (json.JSONDecodeError, ValueError):
            # Fallback: Risk-Level aus dem Text erkennen
            text_lower = text.lower()
            if "critical" in text_lower or "kritisch" in text_lower:
                result["risk_level"] = "critical"
                result["confidence"] = 0.7
            elif "high" in text_lower or "hoch" in text_lower:
                result["risk_level"] = "high"
                result["confidence"] = 0.6
            elif "medium" in text_lower or "mittel" in text_lower:
                result["risk_level"] = "medium"
                result["confidence"] = 0.5

            result["summary"] = text[:200]

        return result

    # ------------------------------------------------------------------
    # AI-Status
    # ------------------------------------------------------------------
    def get_ai_status(self) -> dict:
        """Gibt den aktuellen Security-AI-Status zurück."""
        rows = self._query("SELECT * FROM dbai_security.vw_ai_status")
        status = rows[0] if rows else {}

        config = {
            "ai_enabled": self.get_config("ai_enabled", True),
            "auto_response_enabled": self.get_config("auto_response_enabled", True),
            "auto_ban_enabled": self.get_config("auto_ban_enabled", True),
            "auto_mitigate_enabled": self.get_config("auto_mitigate_enabled", False),
            "analysis_temperature": self.get_config("analysis_temperature", 0.2),
            "analysis_max_tokens": self.get_config("analysis_max_tokens", 2048),
        }

        return {**status, "config": config}

    def get_ai_tasks(self, state: str = None, limit: int = 50) -> list:
        """Listet Security-AI-Tasks."""
        sql = """
            SELECT id, task_type, state, trigger_source, triggered_by,
                   risk_level, confidence, auto_executed,
                   ai_assessment, recommended_actions,
                   created_at, started_at, completed_at, processing_ms
            FROM dbai_security.ai_tasks
        """
        params = []
        if state:
            sql += " WHERE state = %s"
            params.append(state)
        sql += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)
        return self._query(sql, tuple(params))

    def get_analysis_log(self, limit: int = 50) -> list:
        """Listet den KI-Analyse-Log."""
        return self._query("""
            SELECT id, ts, task_id, analysis_type, input_summary,
                   output_summary, risk_level, tokens_used,
                   model_name, duration_ms, auto_action
            FROM dbai_security.ai_analysis_log
            ORDER BY ts DESC LIMIT %s
        """, (limit,))

    # ------------------------------------------------------------------
    # Event-Loop (für eigenständigen Betrieb)
    # ------------------------------------------------------------------
    def start(self):
        """Startet den Security-AI-Worker als Event-Loop."""
        self.connect()
        self._running = True

        # LISTEN auf den Security-AI Channel
        with self.listen_conn.cursor() as cur:
            cur.execute("LISTEN security_ai_task;")

        logger.info("═══════════════════════════════════════")
        logger.info("  DBAI Security Monitor AI v1.0.0")
        logger.info("  Ghost-Rolle: %s", self.ROLE_NAME)
        logger.info("  LISTEN: security_ai_task")
        logger.info("═══════════════════════════════════════")

        # Ausstehende Tasks verarbeiten
        self._process_pending_tasks()

        while self._running:
            try:
                if self.listen_conn.closed:
                    self.connect()
                    with self.listen_conn.cursor() as cur:
                        cur.execute("LISTEN security_ai_task;")

                self.listen_conn.poll()

                while self.listen_conn.notifies:
                    notify = self.listen_conn.notifies.pop(0)
                    if notify.channel == "security_ai_task":
                        try:
                            payload = json.loads(notify.payload) if notify.payload else {}
                        except json.JSONDecodeError:
                            payload = {}

                        task_id = payload.get("task_id")
                        if task_id:
                            threading.Thread(
                                target=self.analyze,
                                args=(str(task_id),),
                                daemon=True,
                            ).start()

                time.sleep(0.2)

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error("Security-AI Loop-Fehler: %s", e)
                time.sleep(2)

        self.stop()

    def stop(self):
        """Stoppt den Worker."""
        self._running = False
        for conn in [self.conn, self.listen_conn]:
            if conn and not conn.closed:
                try:
                    conn.close()
                except Exception:
                    pass
        logger.info("Security Monitor AI gestoppt")

    def _process_pending_tasks(self):
        """Verarbeitet ausstehende Tasks beim Start."""
        rows = self._query(
            "SELECT id FROM dbai_security.ai_tasks WHERE state = 'pending' "
            "ORDER BY created_at ASC LIMIT 20"
        )
        for row in rows:
            threading.Thread(
                target=self.analyze,
                args=(str(row["id"]),),
                daemon=True,
            ).start()

        if rows:
            logger.info("Verarbeite %d ausstehende Security-AI-Tasks", len(rows))


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
def main():
    import signal
    worker = SecurityMonitorAI()
    signal.signal(signal.SIGINT, lambda s, f: worker.stop())
    signal.signal(signal.SIGTERM, lambda s, f: worker.stop())
    worker.start()


if __name__ == "__main__":
    main()
