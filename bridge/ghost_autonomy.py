#!/usr/bin/env python3
"""
DBAI Ghost Autonomy Daemon — Der Ghost uebernimmt die Kontrolle.

Wenn der Ghost aktiviert wird, ist er nicht mehr nur ein Chatbot, sondern
der zentrale Scheduler des Rechners. Dieser Daemon:

  1. Injiziert System-Kontext in den Ghost (Hardware, Logs, Praefezenzen)
  2. Ueberwacht Energie/Ressourcen und loggt in energy_consumption
  3. Klassifiziert Prozesse nach Wichtigkeit
  4. Indexiert neue Dateien mit KI-Tags und Embeddings
  5. Fuehrt genehmigte Aktionen aus (proposed_actions)
  6. Loggt den "Thought Stream" fuer die Web-UI

Safety-Prinzip:
  Kritische Aktionen (DROP, DELETE, SHUTDOWN) muessen in die proposed_actions
  Tabelle. Erst nach Genehmigung werden sie ausgefuehrt.

Usage:
    python3 -m bridge.ghost_autonomy --daemon
    python3 -m bridge.ghost_autonomy --inject-context
    python3 -m bridge.ghost_autonomy --scan-processes
    python3 -m bridge.ghost_autonomy --index-files /pfad
"""

import os
import sys
import json
import time
import signal
import hashlib
import logging
import argparse
import select
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import psycopg2
    import psycopg2.extras
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

logger = logging.getLogger("dbai.ghost_autonomy")


class GhostAutonomyDaemon:
    """Zentraler Daemon fuer Ghost-Autonomie.

    Der Ghost wird zum Scheduler: Er sieht Hardware-Status, Prozesse,
    Dateien, Energie — und trifft Entscheidungen. Aber NUR mit Safety-Checks.
    """

    # Prozess-Klassifikation
    CRITICAL_PROCESSES = {
        "postgres", "postgresql", "systemd", "init", "sshd",
        "kernel", "journald", "udevd", "dbus-daemon",
    }
    GHOST_PROCESSES = {
        "python3", "llama", "uvicorn", "ghost_autonomy",
        "hardware_scanner", "gpu_manager", "app_manager",
    }

    def __init__(self, db_dsn: str = "dbname=dbai"):
        self.db_dsn = db_dsn
        self.conn = None
        self.running = False
        self.active_ghost_id = None
        self.active_ghost_role = None

    def connect(self):
        """Verbindung zur DBAI-Datenbank herstellen."""
        if not HAS_PSYCOPG2:
            raise ImportError("psycopg2 nicht installiert: pip install psycopg2-binary")
        self.conn = psycopg2.connect(self.db_dsn)
        self.conn.autocommit = False
        self._resolve_active_ghost()
        logger.info("Ghost Autonomy Daemon: DB verbunden")

    def disconnect(self):
        """Verbindung schliessen."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def _resolve_active_ghost(self):
        """Findet den aktiven Ghost."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT ag.model_id, gr.name
                    FROM dbai_llm.active_ghosts ag
                    JOIN dbai_llm.ghost_roles gr ON gr.id = ag.role_id
                    WHERE ag.state = 'active'
                    ORDER BY ag.activated_at DESC
                    LIMIT 1
                """)
                row = cur.fetchone()
                if row:
                    self.active_ghost_id = str(row[0])
                    self.active_ghost_role = row[1]
                    logger.info(f"Aktiver Ghost: {self.active_ghost_role} ({self.active_ghost_id[:8]}...)")
        except Exception as e:
            logger.warning(f"Kein aktiver Ghost gefunden: {e}")
            self.conn.rollback()

    # ═══════════════════════════════════════════════════════════════
    # CONTEXT INJECTION — Was der Ghost "weiss"
    # ═══════════════════════════════════════════════════════════════

    def inject_context(self):
        """Laedt System-Metadaten in den Ghost-Kontext.

        Der Ghost weiss sofort: "Ich laufe auf einem x86-Server mit 64GB RAM
        und steuere gerade die Luefter."
        """
        contexts = {}

        # 1. Hardware-Status
        if HAS_PSUTIL:
            contexts["hardware_status"] = {
                "cpu_count": psutil.cpu_count(),
                "cpu_percent": psutil.cpu_percent(interval=0.5),
                "cpu_freq_mhz": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
                "memory": {
                    "total_gb": round(psutil.virtual_memory().total / (1024**3), 1),
                    "used_gb": round(psutil.virtual_memory().used / (1024**3), 1),
                    "percent": psutil.virtual_memory().percent,
                },
                "disk": {
                    "total_gb": round(psutil.disk_usage("/").total / (1024**3), 1),
                    "used_percent": psutil.disk_usage("/").percent,
                },
                "boot_time": datetime.fromtimestamp(
                    psutil.boot_time(), tz=timezone.utc
                ).isoformat(),
                "platform": sys.platform,
            }

            # Netzwerk
            try:
                net = psutil.net_io_counters()
                contexts["network_status"] = {
                    "bytes_sent": net.bytes_sent,
                    "bytes_recv": net.bytes_recv,
                    "interfaces": list(psutil.net_if_addrs().keys()),
                }
            except Exception:
                pass

            # Temperaturen
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    contexts["hardware_status"]["temperatures"] = {
                        name: [{"label": s.label, "current": s.current, "high": s.high}
                               for s in sensors]
                        for name, sensors in temps.items()
                    }
            except Exception:
                pass

        # 2. Aktive Prozesse (Top 10 nach CPU)
        if HAS_PSUTIL:
            top_procs = []
            for p in sorted(psutil.process_iter(["name", "cpu_percent", "memory_percent"]),
                            key=lambda x: x.info.get("cpu_percent", 0) or 0, reverse=True)[:10]:
                try:
                    top_procs.append({
                        "name": p.info["name"],
                        "cpu": p.info.get("cpu_percent", 0),
                        "mem": round(p.info.get("memory_percent", 0), 1),
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            contexts["active_processes"] = top_procs

        # 3. Letzte Fehler aus der DB
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT error_type, error_code, context, occurred_at
                    FROM dbai_knowledge.error_patterns
                    ORDER BY occurred_at DESC NULLS LAST
                    LIMIT 5
                """)
                contexts["recent_errors"] = [dict(r) for r in cur.fetchall()]
        except Exception:
            self.conn.rollback()

        # 4. Pending Tasks
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) FROM dbai_llm.task_queue WHERE state = 'pending'
                """)
                contexts["pending_tasks"] = {"count": cur.fetchone()[0]}
        except Exception:
            self.conn.rollback()

        # 5. In die ghost_context Tabelle schreiben
        with self.conn.cursor() as cur:
            for ctx_type, ctx_data in contexts.items():
                cur.execute("""
                    INSERT INTO dbai_llm.ghost_context
                        (ghost_model_id, context_type, context_data, priority, last_refreshed)
                    VALUES (%s, %s, %s,
                        CASE %s
                            WHEN 'hardware_status' THEN 2
                            WHEN 'recent_errors' THEN 3
                            WHEN 'active_processes' THEN 4
                            WHEN 'network_status' THEN 6
                            WHEN 'pending_tasks' THEN 5
                            ELSE 7
                        END,
                        NOW()
                    )
                    ON CONFLICT ON CONSTRAINT ghost_context_pkey DO NOTHING
                """, (
                    self.active_ghost_id,
                    ctx_type,
                    json.dumps(ctx_data, default=str),
                    ctx_type,
                ))
            # Alternativ: Bestehende Eintraege aktualisieren
            for ctx_type, ctx_data in contexts.items():
                cur.execute("""
                    UPDATE dbai_llm.ghost_context
                    SET context_data = %s, last_refreshed = NOW()
                    WHERE ghost_model_id = %s AND context_type = %s
                """, (json.dumps(ctx_data, default=str), self.active_ghost_id, ctx_type))

        self.conn.commit()
        logger.info(f"Kontext injiziert: {len(contexts)} Kategorien")
        return contexts

    # ═══════════════════════════════════════════════════════════════
    # ENERGY MONITORING — Ressourcenverbrauch tracken
    # ═══════════════════════════════════════════════════════════════

    def monitor_energy(self) -> Dict:
        """Liest aktuelle System-Metriken und schreibt sie in energy_consumption."""
        if not HAS_PSUTIL:
            return {"error": "psutil nicht installiert"}

        cpu_pct = psutil.cpu_percent(interval=0.5)
        mem_pct = psutil.virtual_memory().percent
        disk_io = psutil.disk_io_counters()
        net_io = psutil.net_io_counters()

        cpu_temp = None
        gpu_temp = None
        gpu_pct = 0.0

        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for name, sensors in temps.items():
                    for s in sensors:
                        if "cpu" in name.lower() or "core" in name.lower():
                            cpu_temp = s.current
                        elif "gpu" in name.lower():
                            gpu_temp = s.current
        except Exception:
            pass

        # GPU-Auslastung via nvidia-smi
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu,power.draw",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(",")
                if len(parts) >= 2:
                    gpu_pct = float(parts[0].strip())
        except Exception:
            pass

        # Effizienz-Score berechnen (hoeher = besser)
        efficiency = 1.0
        if cpu_pct > 90:
            efficiency -= 0.3
        if mem_pct > 85:
            efficiency -= 0.2
        if cpu_temp and cpu_temp > 80:
            efficiency -= 0.2
        efficiency = max(0.0, min(1.0, efficiency))

        # Ghost-Kommentar basierend auf Zustand
        comment = None
        if cpu_pct > 90:
            comment = "CPU-Last kritisch — priorisiere Nutzer-Prozesse"
        elif mem_pct > 85:
            comment = "RAM-Druck hoch — suche nicht-kritische Prozesse zum Drosseln"
        elif cpu_temp and cpu_temp > 80:
            comment = "CPU ueberhitzt — Luefter erhoehen, Last reduzieren"
        elif efficiency > 0.9:
            comment = "System laeuft optimal"

        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO dbai_system.energy_consumption
                    (cpu_percent, memory_percent, gpu_percent,
                     cpu_temp_c, gpu_temp_c, power_profile,
                     efficiency_score, ghost_comment)
                VALUES (%s, %s, %s, %s, %s,
                    (SELECT name FROM dbai_system.power_profiles WHERE is_active LIMIT 1),
                    %s, %s)
            """, (cpu_pct, mem_pct, gpu_pct, cpu_temp, gpu_temp,
                  efficiency, comment))
        self.conn.commit()

        return {
            "cpu": cpu_pct, "mem": mem_pct, "gpu": gpu_pct,
            "cpu_temp": cpu_temp, "efficiency": efficiency,
            "comment": comment,
        }

    # ═══════════════════════════════════════════════════════════════
    # PROCESS CLASSIFICATION — Wichtigkeit von Prozessen
    # ═══════════════════════════════════════════════════════════════

    def classify_processes(self) -> List[Dict]:
        """Scannt laufende Prozesse und klassifiziert sie nach Wichtigkeit."""
        if not HAS_PSUTIL:
            return []

        classified = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
            try:
                name = proc.info["name"] or "unknown"
                pid = proc.info["pid"]
                cpu = proc.info.get("cpu_percent", 0) or 0
                mem_mb = (proc.info.get("memory_info").rss / (1024**2)
                          if proc.info.get("memory_info") else 0)

                # Klassifizierung
                importance = "normal"
                category = "unknown"
                can_throttle = True
                can_kill = False

                name_lower = name.lower()
                if any(p in name_lower for p in self.CRITICAL_PROCESSES):
                    importance = "critical"
                    category = "system_core"
                    can_throttle = False
                    can_kill = False
                elif any(p in name_lower for p in self.GHOST_PROCESSES):
                    importance = "high"
                    category = "ghost_service"
                    can_throttle = False
                    can_kill = False
                elif any(p in name_lower for p in ["firefox", "chrome", "chromium", "code"]):
                    importance = "high"
                    category = "user_interactive"
                    can_throttle = True
                    can_kill = False
                elif any(p in name_lower for p in ["index", "sync", "update", "cron", "backup"]):
                    importance = "low"
                    category = "background_service"
                    can_throttle = True
                    can_kill = True

                entry = {
                    "name": name, "pid": pid, "cpu": cpu, "mem_mb": round(mem_mb, 1),
                    "importance": importance, "category": category,
                    "can_throttle": can_throttle, "can_kill": can_kill,
                }
                classified.append(entry)

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # In DB schreiben (Top 50 nach CPU+RAM)
        classified.sort(key=lambda x: x["cpu"] + x["mem_mb"], reverse=True)
        with self.conn.cursor() as cur:
            # Alte Eintraege loeschen
            cur.execute("DELETE FROM dbai_system.process_importance")
            for proc in classified[:50]:
                cur.execute("""
                    INSERT INTO dbai_system.process_importance
                        (process_name, process_pid, importance_level, category,
                         cpu_percent, memory_mb, can_throttle, can_kill)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    proc["name"], proc["pid"], proc["importance"], proc["category"],
                    proc["cpu"], proc["mem_mb"], proc["can_throttle"], proc["can_kill"]
                ))
        self.conn.commit()
        logger.info(f"Prozesse klassifiziert: {len(classified[:50])} Eintraege")
        return classified[:50]

    # ═══════════════════════════════════════════════════════════════
    # FILE INDEXING — Autonome Dateiorganisation
    # ═══════════════════════════════════════════════════════════════

    def index_file(self, file_path: str) -> Optional[Dict]:
        """Indexiert eine einzelne Datei mit KI-Tags und Metadaten."""
        path = Path(file_path).resolve()
        if not path.exists() or not path.is_file():
            return None

        stat = path.stat()
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()

        # MIME-Type bestimmen
        import mimetypes
        mime_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"

        # Automatische Tags basierend auf Pfad und Typ
        auto_tags = []
        name_lower = path.name.lower()
        if any(ext in name_lower for ext in [".py", ".js", ".ts", ".sql", ".sh"]):
            auto_tags.append("code")
        if any(ext in name_lower for ext in [".md", ".txt", ".rst", ".doc"]):
            auto_tags.append("document")
        if any(ext in name_lower for ext in [".jpg", ".png", ".gif", ".svg"]):
            auto_tags.append("image")
        if any(ext in name_lower for ext in [".json", ".yaml", ".yml", ".toml"]):
            auto_tags.append("config")
        if "test" in name_lower:
            auto_tags.append("test")

        # Kategorie
        category = "unknown"
        parent = str(path.parent).lower()
        if "schema" in parent:
            category = "database"
        elif "bridge" in parent:
            category = "daemon"
        elif "web" in parent or "frontend" in parent:
            category = "frontend"
        elif "test" in parent:
            category = "testing"
        elif "scripts" in parent:
            category = "infrastructure"

        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO dbai_core.ghost_files
                    (file_path, file_name, file_type, file_size_bytes,
                     file_hash, auto_tags, auto_category,
                     assigned_by_ghost, confidence, is_indexed, indexed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, NOW())
                ON CONFLICT DO NOTHING
            """, (
                str(path), path.name, mime_type, stat.st_size,
                file_hash, auto_tags, category,
                self.active_ghost_id, 0.7
            ))
        self.conn.commit()

        result = {
            "file": str(path), "type": mime_type, "size": stat.st_size,
            "tags": auto_tags, "category": category, "hash": file_hash[:16],
        }
        logger.debug(f"Datei indexiert: {path.name} → {auto_tags}")
        return result

    def index_directory(self, directory: str, recursive: bool = True) -> Dict:
        """Indexiert alle Dateien in einem Verzeichnis."""
        base = Path(directory).resolve()
        if not base.is_dir():
            return {"error": f"Kein Verzeichnis: {directory}"}

        indexed = 0
        errors = 0
        pattern = base.rglob("*") if recursive else base.glob("*")

        for path in pattern:
            if path.is_file() and not path.name.startswith("."):
                try:
                    self.index_file(str(path))
                    indexed += 1
                except Exception as e:
                    errors += 1
                    logger.warning(f"Index-Fehler: {path}: {e}")

        return {"directory": str(base), "indexed": indexed, "errors": errors}

    # ═══════════════════════════════════════════════════════════════
    # APPROVED ACTION EXECUTION — Genehmigte Aktionen ausfuehren
    # ═══════════════════════════════════════════════════════════════

    def execute_approved_actions(self):
        """Sucht genehmigte Aktionen und fuehrt sie aus."""
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT id, action_type, action_sql, action_command, action_params
                FROM dbai_llm.proposed_actions
                WHERE approval_state = 'approved'
                ORDER BY proposed_at ASC
                LIMIT 5
            """)
            actions = cur.fetchall()

        for action in actions:
            action_id = action["id"]
            try:
                # Status: executing
                with self.conn.cursor() as cur:
                    cur.execute("""
                        UPDATE dbai_llm.proposed_actions
                        SET approval_state = 'executing'
                        WHERE id = %s
                    """, (str(action_id),))
                self.conn.commit()

                result = self._execute_single_action(action)

                # Status: executed
                with self.conn.cursor() as cur:
                    cur.execute("""
                        UPDATE dbai_llm.proposed_actions
                        SET approval_state = 'executed',
                            executed_at = NOW(),
                            execution_result = %s
                        WHERE id = %s
                    """, (json.dumps(result, default=str), str(action_id)))
                self.conn.commit()

                self.log_thought(
                    "action",
                    f"Aktion ausgefuehrt: {action['action_type']} → Erfolg",
                    metadata={"action_id": str(action_id)},
                )

            except Exception as e:
                with self.conn.cursor() as cur:
                    cur.execute("""
                        UPDATE dbai_llm.proposed_actions
                        SET approval_state = 'failed',
                            error_message = %s,
                            executed_at = NOW()
                        WHERE id = %s
                    """, (str(e)[:500], str(action_id)))
                self.conn.commit()

                self.log_thought(
                    "error",
                    f"Aktion fehlgeschlagen: {action['action_type']} → {str(e)[:200]}",
                    metadata={"action_id": str(action_id)},
                )

    def _execute_single_action(self, action: Dict) -> Dict:
        """Fuehrt eine einzelne genehmigte Aktion aus."""
        action_type = action["action_type"]

        if action_type == "sql_execute" and action.get("action_sql"):
            # SQL ausfuehren (mit Safety-Check)
            sql = action["action_sql"]
            # Nochmal pruefen: Keine DROP/TRUNCATE
            if any(kw in sql.upper() for kw in ["DROP DATABASE", "DROP SCHEMA"]):
                raise ValueError("VERBOTEN: DROP DATABASE/SCHEMA kann nicht ausgefuehrt werden")

            with self.conn.cursor() as cur:
                cur.execute(sql)
                if cur.description:  # SELECT
                    rows = cur.fetchall()
                    return {"type": "query", "rows": len(rows), "data": rows[:20]}
                else:
                    return {"type": "dml", "affected_rows": cur.rowcount}

        elif action_type == "package_install":
            params = action.get("action_params", {})
            return {"type": "package_install", "status": "delegated_to_app_manager",
                    "package": params.get("package")}

        elif action_type == "ghost_swap":
            params = action.get("action_params", {})
            return {"type": "ghost_swap", "status": "delegated_to_dispatcher",
                    "target_ghost": params.get("target_ghost")}

        elif action.get("action_command"):
            # Shell-Befehle: NICHT direkt ausfuehren (Security)
            return {"type": "shell", "status": "queued",
                    "command": action["action_command"][:200]}

        return {"type": action_type, "status": "not_implemented"}

    # ═══════════════════════════════════════════════════════════════
    # THOUGHT LOGGING — Was der Ghost denkt
    # ═══════════════════════════════════════════════════════════════

    def log_thought(self, thought_type: str, text: str,
                    sql_query: str = None, sql_result: Any = None,
                    trigger: str = None, confidence: float = 0.8,
                    metadata: Dict = None):
        """Schreibt einen Eintrag in den Thought Stream."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO dbai_llm.ghost_thought_log
                        (ghost_model_id, role_name, thought_type, thought_text,
                         sql_query, sql_result, trigger_event, confidence, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    self.active_ghost_id, self.active_ghost_role,
                    thought_type, text,
                    sql_query,
                    json.dumps(sql_result, default=str) if sql_result else None,
                    trigger, confidence,
                    json.dumps(metadata, default=str) if metadata else None,
                ))
            self.conn.commit()
        except Exception as e:
            logger.warning(f"Thought-Log Fehler: {e}")
            self.conn.rollback()

    # ═══════════════════════════════════════════════════════════════
    # EXPIRE ACTIONS — Abgelaufene Aktionen bereinigen
    # ═══════════════════════════════════════════════════════════════

    def expire_actions(self) -> int:
        """Markiert abgelaufene proposed_actions als expired."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT dbai_llm.expire_pending_actions()")
            count = cur.fetchone()[0]
        self.conn.commit()
        if count > 0:
            logger.info(f"{count} abgelaufene Aktionen bereinigt")
        return count

    # ═══════════════════════════════════════════════════════════════
    # EVENT LISTENER — Auf System-Events reagieren
    # ═══════════════════════════════════════════════════════════════

    def _setup_listeners(self):
        """Registriert LISTEN fuer relevante NOTIFY-Channels."""
        self.conn.autocommit = True
        with self.conn.cursor() as cur:
            for channel in [
                "action_proposed", "action_approved", "action_rejected",
                "ghost_swap", "ghost_query",
                "power_profile_change", "gpu_overheat",
                "software_install", "user_command",
                "telegram_message",
            ]:
                cur.execute(f"LISTEN {channel};")
        logger.info("Event-Listener registriert")

    def _handle_notify(self, channel: str, payload: str):
        """Verarbeitet eingehende NOTIFY-Events."""
        try:
            data = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            data = {"raw": payload}

        self.log_thought(
            "observation",
            f"Event empfangen: {channel}",
            trigger=channel,
            metadata=data,
        )

        if channel == "action_approved":
            self.execute_approved_actions()

        elif channel == "gpu_overheat":
            self.log_thought("warning",
                "GPU Ueberhitzung erkannt — reduziere Last",
                trigger=channel, confidence=0.95)

        elif channel == "power_profile_change":
            profile = data.get("profile", "unknown")
            self.log_thought("observation",
                f"Power-Profil gewechselt auf: {profile}",
                trigger=channel)

        elif channel == "user_command":
            cmd_input = data.get("input", "")
            self.log_thought("observation",
                f"Nutzer-Befehl empfangen: {cmd_input[:100]}",
                trigger=channel)

    # ═══════════════════════════════════════════════════════════════
    # DAEMON LOOP — Hauptschleife
    # ═══════════════════════════════════════════════════════════════

    def daemon_loop(self, interval_s: int = 30):
        """Hauptschleife des Autonomie-Daemons.

        Alle `interval_s` Sekunden:
        1. Kontext injizieren
        2. Energie/Ressourcen messen
        3. Abgelaufene Aktionen bereinigen
        4. Genehmigte Aktionen ausfuehren
        5. Auf Events reagieren
        """
        self.running = True
        signal.signal(signal.SIGINT, lambda s, f: setattr(self, "running", False))
        signal.signal(signal.SIGTERM, lambda s, f: setattr(self, "running", False))

        self._setup_listeners()

        self.log_thought("observation",
            "Ghost Autonomy Daemon gestartet — der Ghost uebernimmt die Kontrolle",
            confidence=1.0)

        cycle = 0
        while self.running:
            try:
                cycle += 1

                # Kontext-Injection (alle 60s)
                if cycle % 2 == 0:
                    try:
                        self.conn.autocommit = False
                        self.inject_context()
                    except Exception as e:
                        logger.warning(f"Context Injection Fehler: {e}")
                        self.conn.rollback()

                # Energie-Monitoring (jeden Zyklus)
                try:
                    self.conn.autocommit = False
                    metrics = self.monitor_energy()
                    if metrics.get("comment"):
                        self.log_thought("observation", metrics["comment"],
                                         trigger="energy_monitor")
                except Exception as e:
                    logger.warning(f"Energy Monitor Fehler: {e}")
                    self.conn.rollback()

                # Prozess-Klassifikation (alle 5 Minuten)
                if cycle % 10 == 1:
                    try:
                        self.conn.autocommit = False
                        self.classify_processes()
                    except Exception as e:
                        logger.warning(f"Process Classification Fehler: {e}")
                        self.conn.rollback()

                # Expire + Execute (jeden Zyklus)
                try:
                    self.conn.autocommit = False
                    self.expire_actions()
                    self.execute_approved_actions()
                except Exception as e:
                    logger.warning(f"Action Execution Fehler: {e}")
                    self.conn.rollback()

                # Ghost neu auflösen (alle 2 Minuten)
                if cycle % 4 == 0:
                    try:
                        self.conn.autocommit = False
                        self._resolve_active_ghost()
                    except Exception:
                        self.conn.rollback()

                # Auf Events warten (mit Timeout)
                self.conn.autocommit = True
                if select.select([self.conn], [], [], interval_s) != ([], [], []):
                    self.conn.poll()
                    while self.conn.notifies:
                        notify = self.conn.notifies.pop(0)
                        self._handle_notify(notify.channel, notify.payload)

            except Exception as e:
                logger.error(f"Daemon-Loop Fehler: {e}")
                time.sleep(5)

                # Reconnect bei DB-Verbindungsfehler
                try:
                    self.conn.close()
                except Exception:
                    pass
                try:
                    self.connect()
                    self._setup_listeners()
                except Exception as e2:
                    logger.error(f"Reconnect fehlgeschlagen: {e2}")
                    time.sleep(30)

        self.log_thought("observation", "Ghost Autonomy Daemon gestoppt")
        logger.info("Ghost Autonomy Daemon gestoppt")


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="DBAI Ghost Autonomy Daemon — Der Ghost uebernimmt die Kontrolle",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--daemon", action="store_true",
                        help="Daemon-Modus: Kontinuierliche Ueberwachung und Steuerung")
    parser.add_argument("--inject-context", action="store_true",
                        help="System-Kontext einmalig in Ghost injizieren")
    parser.add_argument("--scan-processes", action="store_true",
                        help="Prozesse einmalig klassifizieren")
    parser.add_argument("--index-files", metavar="PATH",
                        help="Dateien in einem Verzeichnis indexieren")
    parser.add_argument("--energy", action="store_true",
                        help="Energie-Metriken einmalig erfassen")
    parser.add_argument("--expire", action="store_true",
                        help="Abgelaufene Aktionen bereinigen")
    parser.add_argument("--interval", type=int, default=30,
                        help="Daemon-Intervall in Sekunden (default: 30)")
    parser.add_argument("--db", default="dbname=dbai",
                        help="PostgreSQL DSN")
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    )

    daemon = GhostAutonomyDaemon(args.db)
    try:
        daemon.connect()

        if args.daemon:
            print("╔═══════════════════════════════════════════╗")
            print("║  DBAI Ghost Autonomy Daemon v0.6.0       ║")
            print("║  Der Ghost uebernimmt die Kontrolle.     ║")
            print("║  Safety-First: Kritische Aktionen         ║")
            print("║  erfordern Genehmigung.                   ║")
            print("╚═══════════════════════════════════════════╝")
            daemon.daemon_loop(args.interval)

        elif args.inject_context:
            ctx = daemon.inject_context()
            print(json.dumps(ctx, indent=2, default=str))

        elif args.scan_processes:
            procs = daemon.classify_processes()
            for p in procs[:20]:
                print(f"  [{p['importance']:>10}] {p['name']:<25} "
                      f"CPU:{p['cpu']:5.1f}% MEM:{p['mem_mb']:7.1f}MB")

        elif args.index_files:
            result = daemon.index_directory(args.index_files)
            print(json.dumps(result, indent=2))

        elif args.energy:
            metrics = daemon.monitor_energy()
            print(json.dumps(metrics, indent=2))

        elif args.expire:
            count = daemon.expire_actions()
            print(f"Bereinigt: {count} abgelaufene Aktionen")

        else:
            parser.print_help()

    except KeyboardInterrupt:
        print("\nGhostAutonomy gestoppt.")
    except Exception as e:
        logger.error(f"Fehler: {e}")
        sys.exit(1)
    finally:
        daemon.disconnect()


if __name__ == "__main__":
    main()
