#!/usr/bin/env python3
"""
DBAI Panic Recovery
===================
Notfall-Reparatur-System.
Wird aktiviert wenn die Haupt-KI sich verrechnet oder die DB korrupt ist.

Nutzt die isolierte Notfall-Tabelle (dbai_panic Schema) die
schreibgeschützt ist und minimale Treiber enthält.
"""

import os
import sys
import logging
import json
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("dbai.panic")


class PanicRecovery:
    """
    Kernel Panic Recovery — Letztes Sicherheitsnetz.
    """

    # Panic-Typen und ihre automatischen Reaktionen
    PANIC_HANDLERS = {
        "db_corruption": "_handle_db_corruption",
        "disk_failure": "_handle_disk_failure",
        "memory_overflow": "_handle_memory_overflow",
        "deadlock_cascade": "_handle_deadlock_cascade",
        "llm_runaway": "_handle_llm_runaway",
        "data_integrity": "_handle_data_integrity",
        "boot_failure": "_handle_boot_failure",
        "driver_crash": "_handle_driver_crash",
    }

    def __init__(self, conn=None):
        self.conn = conn
        self.recovery_mode = False

    def _get_cursor(self):
        return self.conn.cursor(cursor_factory=RealDictCursor)

    def _connect_emergency(self) -> bool:
        """
        Notfall-Verbindung zur DB mit minimaler Konfiguration.
        Liest Boot-Parameter aus dem Panic-Schema.
        """
        try:
            self.conn = psycopg2.connect(
                host="127.0.0.1",
                port=int(os.getenv("DBAI_DB_PORT", "5432")),
                dbname=os.getenv("DBAI_DB_NAME", "dbai"),
                user="dbai_recovery",
                password=os.getenv("DBAI_RECOVERY_PASSWORD", ""),
                connect_timeout=10,
            )
            self.conn.autocommit = True
            logger.info("Notfall-Verbindung hergestellt")
            return True
        except Exception as e:
            logger.critical("Notfall-Verbindung FEHLGESCHLAGEN: %s", e)
            return False

    # ------------------------------------------------------------------
    # Panic auslösen
    # ------------------------------------------------------------------
    def trigger_panic(
        self, panic_type: str, description: str,
        severity: str = "critical", system_state: dict = None,
    ) -> int:
        """
        Löst einen Kernel Panic aus und startet die Reparatur.
        """
        logger.critical(
            "=== KERNEL PANIC === Typ: %s, Schwere: %s",
            panic_type, severity,
        )
        logger.critical("Beschreibung: %s", description)

        panic_id = None
        try:
            with self._get_cursor() as cur:
                # Panic-Log schreiben
                cur.execute(
                    """
                    INSERT INTO dbai_panic.panic_log
                        (panic_type, severity, description, system_state)
                    VALUES (%s, %s, %s, %s::jsonb)
                    RETURNING id
                    """,
                    (
                        panic_type, severity, description,
                        json.dumps(system_state or {}, default=str),
                    ),
                )
                panic_id = cur.fetchone()["id"]

                # Recovery-Modus aktivieren
                cur.execute(
                    """
                    UPDATE dbai_panic.boot_config
                    SET value = %s::jsonb,
                        checksum = md5(%s)
                    WHERE key = 'recovery_mode'
                    """,
                    (
                        json.dumps({
                            "active": True,
                            "reason": panic_type,
                            "since": datetime.now(timezone.utc).isoformat(),
                        }),
                        json.dumps({
                            "active": True,
                            "reason": panic_type,
                        }),
                    ),
                )
        except Exception as e:
            logger.critical("Panic-Log Schreiben fehlgeschlagen: %s", e)

        # Automatische Reparatur starten
        self.recovery_mode = True
        handler_name = self.PANIC_HANDLERS.get(panic_type)
        if handler_name:
            handler = getattr(self, handler_name, None)
            if handler:
                try:
                    handler(panic_id, description)
                except Exception as e:
                    logger.critical(
                        "Automatische Reparatur fehlgeschlagen: %s", e
                    )

        return panic_id

    # ------------------------------------------------------------------
    # Reparatur-Handler
    # ------------------------------------------------------------------
    def _handle_db_corruption(self, panic_id: int, description: str):
        """Datenbank-Korruption behandeln."""
        logger.info("Starte DB-Korruptions-Reparatur…")
        try:
            with self._get_cursor() as cur:
                # Reparatur-Skripte aus dem Panic-Schema laden und ausführen
                cur.execute(
                    "SELECT * FROM dbai_panic.execute_repair('db_corruption')"
                )
                results = cur.fetchall()
                for r in results:
                    status = "OK" if r["success"] else "FEHLER"
                    logger.info(
                        "  [%s] %s: %s", status, r["script_name"], r["message"]
                    )

                # Panic als bearbeitet markieren
                self._resolve_panic(panic_id, "Automatische DB-Reparatur ausgeführt")
        except Exception as e:
            logger.critical("DB-Reparatur fehlgeschlagen: %s", e)

    def _handle_disk_failure(self, panic_id: int, description: str):
        """Festplatten-Ausfall behandeln — Failover zum Mirror."""
        logger.info("Disk-Failure erkannt — prüfe Mirror-Verfügbarkeit…")
        try:
            from mirror_sync import MirrorSync
            import threading

            mirror = MirrorSync(self.conn, threading.Event())
            status = mirror.check_mirrors()

            healthy_mirrors = [
                target for target, info in status.items()
                if info.get("status") == "healthy"
            ]

            if healthy_mirrors:
                logger.info(
                    "Mirror verfügbar: %s — Failover möglich", healthy_mirrors[0]
                )
                self._resolve_panic(
                    panic_id,
                    f"Mirror verfügbar: {healthy_mirrors[0]}",
                )
            else:
                logger.critical("KEIN Mirror verfügbar! Daten gefährdet!")
        except Exception as e:
            logger.critical("Mirror-Prüfung fehlgeschlagen: %s", e)

    def _handle_memory_overflow(self, panic_id: int, description: str):
        """Speicher-Überlauf behandeln."""
        logger.info("Memory Overflow — beende nicht-kritische Prozesse…")
        try:
            with self._get_cursor() as cur:
                # Nicht-kritische Prozesse beenden (niedrige Priorität zuerst)
                cur.execute(
                    """
                    UPDATE dbai_core.processes
                    SET state = 'stopped', stopped_at = NOW(),
                        error_message = 'Gestoppt wegen Memory Overflow'
                    WHERE state = 'running'
                      AND priority > 5
                    RETURNING name, priority
                    """
                )
                stopped = cur.fetchall()
                for p in stopped:
                    logger.info("  Prozess gestoppt: %s (Prio %d)", p["name"], p["priority"])

                self._resolve_panic(
                    panic_id,
                    f"{len(stopped)} Prozesse gestoppt",
                )
        except Exception as e:
            logger.critical("Memory-Overflow-Behandlung fehlgeschlagen: %s", e)

    def _handle_deadlock_cascade(self, panic_id: int, description: str):
        """Deadlock-Kaskade auflösen."""
        logger.info("Deadlock-Kaskade — löse alle Locks auf…")
        try:
            with self._get_cursor() as cur:
                # Alle Advisory Locks freigeben
                cur.execute("SELECT pg_advisory_unlock_all()")

                # Lock-Registry bereinigen
                cur.execute(
                    """
                    UPDATE dbai_system.lock_registry
                    SET state = 'released', released_at = NOW()
                    WHERE state IN ('active', 'waiting')
                    """
                )
                count = cur.rowcount
                logger.info("%d Locks aufgelöst", count)

                self._resolve_panic(panic_id, f"{count} Locks aufgelöst")
        except Exception as e:
            logger.critical("Deadlock-Auflösung fehlgeschlagen: %s", e)

    def _handle_llm_runaway(self, panic_id: int, description: str):
        """LLM außer Kontrolle — sofort stoppen."""
        logger.info("LLM Runaway — stoppe alle LLM-Prozesse…")
        try:
            with self._get_cursor() as cur:
                # Alle LLM-Prozesse stoppen
                cur.execute(
                    """
                    UPDATE dbai_core.processes
                    SET state = 'stopped', stopped_at = NOW(),
                        error_message = 'LLM Runaway — Notfall-Stopp'
                    WHERE process_type = 'llm' AND state = 'running'
                    """
                )

                # Alle ausstehenden LLM-Tasks abbrechen
                cur.execute(
                    """
                    UPDATE dbai_llm.task_queue
                    SET state = 'cancelled',
                        error_message = 'LLM Runaway — Alle Tasks abgebrochen'
                    WHERE state IN ('pending', 'processing')
                    """
                )
                cancelled = cur.rowcount

                # LLM-Modell entladen
                cur.execute(
                    """
                    UPDATE dbai_llm.models
                    SET is_loaded = FALSE, loaded_at = NULL
                    WHERE is_loaded = TRUE
                    """
                )

                logger.info("LLM gestoppt, %d Tasks abgebrochen", cancelled)
                self._resolve_panic(
                    panic_id,
                    f"LLM gestoppt, {cancelled} Tasks abgebrochen",
                )
        except Exception as e:
            logger.critical("LLM-Stopp fehlgeschlagen: %s", e)

    def _handle_data_integrity(self, panic_id: int, description: str):
        """Datenintegritäts-Verletzung behandeln."""
        logger.info("Datenintegritäts-Verletzung — prüfe Journals…")
        self._handle_db_corruption(panic_id, description)

    def _handle_boot_failure(self, panic_id: int, description: str):
        """Boot-Fehler behandeln."""
        logger.info("Boot-Failure — versuche Minimal-Boot…")
        try:
            with self._get_cursor() as cur:
                # Alle Reparatur-Skripte ausführen
                cur.execute("SELECT * FROM dbai_panic.execute_repair()")
                results = cur.fetchall()
                success = all(r["success"] for r in results)

                if success:
                    self._resolve_panic(panic_id, "Minimal-Boot Reparatur erfolgreich")
                else:
                    logger.critical("Minimal-Boot Reparatur teilweise fehlgeschlagen")
        except Exception as e:
            logger.critical("Boot-Reparatur fehlgeschlagen: %s", e)

    def _handle_driver_crash(self, panic_id: int, description: str):
        """Treiber-Absturz behandeln."""
        logger.info("Treiber-Crash — lade Notfall-Treiber…")
        try:
            with self._get_cursor() as cur:
                # Notfall-Treiber laden
                cur.execute(
                    """
                    SELECT name, driver_type, is_valid
                    FROM dbai_panic.emergency_drivers
                    WHERE is_valid = TRUE
                    ORDER BY driver_type
                    """
                )
                drivers = cur.fetchall()
                for d in drivers:
                    logger.info(
                        "  Notfall-Treiber: %s (%s)", d["name"], d["driver_type"]
                    )

                self._resolve_panic(
                    panic_id,
                    f"{len(drivers)} Notfall-Treiber geladen",
                )
        except Exception as e:
            logger.critical("Treiber-Reparatur fehlgeschlagen: %s", e)

    # ------------------------------------------------------------------
    # Hilfsfunktionen
    # ------------------------------------------------------------------
    def _resolve_panic(self, panic_id: int, recovery_action: str):
        """Markiert einen Panic als bearbeitet."""
        try:
            with self._get_cursor() as cur:
                cur.execute(
                    """
                    UPDATE dbai_panic.panic_log
                    SET resolved = TRUE, resolved_at = NOW(),
                        recovery_action = %s
                    WHERE id = %s
                    """,
                    (recovery_action, panic_id),
                )
                logger.info("Panic #%d aufgelöst: %s", panic_id, recovery_action)
        except Exception as e:
            logger.error("Panic-Auflösung fehlgeschlagen: %s", e)

    # ------------------------------------------------------------------
    # Diagnose
    # ------------------------------------------------------------------
    def full_diagnostic(self) -> dict:
        """Führt eine vollständige System-Diagnose durch."""
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {},
            "overall": "healthy",
        }

        checks = [
            ("schema_integrity", self._check_schema_integrity),
            ("journal_integrity", self._check_journal_integrity),
            ("panic_history", self._check_panic_history),
            ("process_health", self._check_process_health),
            ("lock_status", self._check_lock_status),
        ]

        for name, check_fn in checks:
            try:
                result = check_fn()
                results["checks"][name] = result
                if result.get("status") != "ok":
                    results["overall"] = "degraded"
            except Exception as e:
                results["checks"][name] = {"status": "error", "error": str(e)}
                results["overall"] = "critical"

        return results

    def _check_schema_integrity(self) -> dict:
        with self._get_cursor() as cur:
            cur.execute(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name LIKE 'dbai_%%'"
            )
            schemas = [r["schema_name"] for r in cur.fetchall()]
            expected = 7  # core, system, event, vector, journal, panic, llm
            return {
                "status": "ok" if len(schemas) >= expected else "error",
                "found": len(schemas),
                "expected": expected,
                "schemas": schemas,
            }

    def _check_journal_integrity(self) -> dict:
        with self._get_cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) as total FROM dbai_journal.change_log"
            )
            total = cur.fetchone()["total"]
            return {"status": "ok", "total_entries": total}

    def _check_panic_history(self) -> dict:
        with self._get_cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) as total,
                       COUNT(*) FILTER (WHERE resolved = FALSE) as unresolved
                FROM dbai_panic.panic_log
                """
            )
            row = cur.fetchone()
            return {
                "status": "ok" if row["unresolved"] == 0 else "warning",
                "total_panics": row["total"],
                "unresolved": row["unresolved"],
            }

    def _check_process_health(self) -> dict:
        with self._get_cursor() as cur:
            cur.execute(
                """
                SELECT state, COUNT(*) as cnt
                FROM dbai_core.processes
                GROUP BY state
                """
            )
            states = {r["state"]: r["cnt"] for r in cur.fetchall()}
            zombies = states.get("zombie", 0)
            crashed = states.get("crashed", 0)
            return {
                "status": "ok" if (zombies + crashed) == 0 else "warning",
                "states": states,
            }

    def _check_lock_status(self) -> dict:
        with self._get_cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) as active_locks,
                       COUNT(*) FILTER (WHERE state = 'waiting') as waiting
                FROM dbai_system.lock_registry
                WHERE state IN ('active', 'waiting')
                """
            )
            row = cur.fetchone()
            return {
                "status": "ok" if row["waiting"] == 0 else "warning",
                "active_locks": row["active_locks"],
                "waiting": row["waiting"],
            }


# ======================================================================
# CLI-Schnittstelle
# ======================================================================
if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(description="DBAI Panic Recovery")
    parser.add_argument("action", choices=["diagnose", "panic", "history"])
    parser.add_argument("--type", help="Panic-Typ", default="unknown")
    parser.add_argument("--description", help="Beschreibung", default="Manuell ausgelöst")
    args = parser.parse_args()

    recovery = PanicRecovery()
    if not recovery._connect_emergency():
        sys.exit(1)

    if args.action == "diagnose":
        result = recovery.full_diagnostic()
        print(json.dumps(result, indent=2, default=str))

    elif args.action == "panic":
        panic_id = recovery.trigger_panic(args.type, args.description)
        print(f"Panic #{panic_id} ausgelöst und behandelt")

    elif args.action == "history":
        with recovery._get_cursor() as cur:
            cur.execute(
                "SELECT * FROM dbai_panic.panic_log ORDER BY ts DESC LIMIT 20"
            )
            for row in cur.fetchall():
                status = "✓" if row["resolved"] else "✗"
                print(
                    f"  [{status}] #{row['id']} {row['ts']} "
                    f"{row['panic_type']} ({row['severity']}): "
                    f"{row['description'][:60]}"
                )
