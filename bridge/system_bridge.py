#!/usr/bin/env python3
"""
DBAI System Bridge — Der Zündschlüssel
=======================================
Lädt die PostgreSQL-Engine und alle DBAI-Subsysteme in den Arbeitsspeicher.
Ohne diesen Zündschlüssel startet keine einzige Tabelle.

Verantwortlichkeiten:
1. PostgreSQL-Instanz starten und in RAM laden
2. Schema-Integrität prüfen
3. Hardware-Monitor starten
4. Event-Dispatcher aktivieren
5. LLM-Bridge initialisieren
6. Vacuum-Scheduler starten
7. PITR-Snapshot-Service starten
8. Watchdog für Prozess-Überwachung
"""

import os
import sys
import time
import signal
import logging
import threading
import subprocess
from pathlib import Path
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import RealDictCursor

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------
DBAI_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = DBAI_ROOT / "config"
SCHEMA_DIR = DBAI_ROOT / "schema"

DB_CONFIG = {
    "host": os.getenv("DBAI_DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DBAI_DB_PORT", "5432")),
    "dbname": os.getenv("DBAI_DB_NAME", "dbai"),
    "user": os.getenv("DBAI_DB_USER", "dbai_system"),
    "password": os.getenv("DBAI_DB_PASSWORD", ""),
}

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("dbai.bridge")


class SystemBridge:
    """
    Haupt-Klasse: Bootet das gesamte DBAI-System.
    """

    def __init__(self):
        self.conn = None
        self.running = False
        self.subsystems = {}
        self._shutdown_event = threading.Event()

        # Signal-Handler für sauberes Herunterfahren
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        logger.info("Signal %s empfangen — fahre System herunter…", signum)
        self.shutdown()

    # ------------------------------------------------------------------
    # 1. Datenbank-Verbindung
    # ------------------------------------------------------------------
    def connect_db(self) -> bool:
        """Verbindung zur PostgreSQL-Instanz herstellen."""
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.conn.autocommit = False
            logger.info(
                "Datenbankverbindung hergestellt: %s@%s:%s/%s",
                DB_CONFIG["user"],
                DB_CONFIG["host"],
                DB_CONFIG["port"],
                DB_CONFIG["dbname"],
            )
            return True
        except psycopg2.Error as e:
            logger.error("Datenbankverbindung fehlgeschlagen: %s", e)
            return False

    def get_cursor(self):
        """Neuen Cursor mit Dictionary-Ergebnis erstellen."""
        if self.conn is None or self.conn.closed:
            self.connect_db()
        return self.conn.cursor(cursor_factory=RealDictCursor)

    # ------------------------------------------------------------------
    # 2. Schema-Integrität prüfen
    # ------------------------------------------------------------------
    def verify_schemas(self) -> bool:
        """Prüft ob alle DBAI-Schemas und Tabellen existieren."""
        required_schemas = [
            "dbai_core",
            "dbai_system",
            "dbai_event",
            "dbai_vector",
            "dbai_journal",
            "dbai_panic",
            "dbai_llm",
        ]
        try:
            with self.get_cursor() as cur:
                cur.execute(
                    "SELECT schema_name FROM information_schema.schemata "
                    "WHERE schema_name LIKE 'dbai_%%'"
                )
                existing = {row["schema_name"] for row in cur.fetchall()}

            missing = set(required_schemas) - existing
            if missing:
                logger.error("Fehlende Schemas: %s", missing)
                return False

            logger.info(
                "Schema-Integrität OK: %d/%d Schemas vorhanden",
                len(existing),
                len(required_schemas),
            )
            return True
        except Exception as e:
            logger.error("Schema-Prüfung fehlgeschlagen: %s", e)
            return False

    # ------------------------------------------------------------------
    # 3. System-Prozess registrieren
    # ------------------------------------------------------------------
    def register_process(self, name: str, process_type: str, priority: int = 1):
        """Registriert einen Prozess in der Prozess-Tabelle."""
        try:
            with self.get_cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO dbai_core.processes
                        (name, process_type, priority, state, pid, started_at)
                    VALUES (%s, %s, %s, 'running', %s, NOW())
                    RETURNING id
                    """,
                    (name, process_type, priority, os.getpid()),
                )
                proc_id = cur.fetchone()["id"]
                self.conn.commit()
                self.subsystems[name] = proc_id
                logger.info("Prozess registriert: %s (PID %s)", name, os.getpid())
                return proc_id
        except Exception as e:
            logger.error("Prozess-Registrierung fehlgeschlagen: %s", e)
            self.conn.rollback()
            return None

    # ------------------------------------------------------------------
    # 4. Heartbeat
    # ------------------------------------------------------------------
    def _heartbeat_loop(self):
        """Sendet regelmäßig Heartbeats für alle registrierten Prozesse."""
        while not self._shutdown_event.is_set():
            try:
                with self.get_cursor() as cur:
                    for name, proc_id in self.subsystems.items():
                        cur.execute(
                            """
                            UPDATE dbai_core.processes
                            SET last_heartbeat = NOW()
                            WHERE id = %s AND state = 'running'
                            """,
                            (str(proc_id),),
                        )
                    self.conn.commit()
            except Exception as e:
                logger.warning("Heartbeat fehlgeschlagen: %s", e)
                try:
                    self.conn.rollback()
                except Exception:
                    pass
            self._shutdown_event.wait(5)  # Alle 5 Sekunden

    # ------------------------------------------------------------------
    # 5. PITR Snapshot Service
    # ------------------------------------------------------------------
    def _snapshot_loop(self):
        """Erstellt jede Sekunde einen System-Snapshot für PITR."""
        while not self._shutdown_event.is_set():
            try:
                with self.get_cursor() as cur:
                    # System-Status sammeln
                    cur.execute("SELECT * FROM dbai_system.current_status")
                    status = cur.fetchone()

                    # WAL-Position ermitteln
                    cur.execute("SELECT pg_current_wal_lsn() AS lsn")
                    wal_lsn = cur.fetchone()["lsn"]

                    # Snapshot speichern
                    import json
                    snapshot_data = json.dumps(status if status else {})
                    checksum = self._md5(snapshot_data)

                    cur.execute(
                        """
                        INSERT INTO dbai_journal.system_snapshots
                            (snapshot, wal_lsn, checksum, snapshot_type)
                        VALUES (%s::jsonb, %s, %s, 'periodic')
                        """,
                        (snapshot_data, str(wal_lsn), checksum),
                    )
                    self.conn.commit()
            except Exception as e:
                logger.debug("Snapshot fehlgeschlagen: %s", e)
                try:
                    self.conn.rollback()
                except Exception:
                    pass
            self._shutdown_event.wait(1)  # Jede Sekunde

    # ------------------------------------------------------------------
    # 6. Lock-Cleanup Service
    # ------------------------------------------------------------------
    def _lock_cleanup_loop(self):
        """Bereinigt abgelaufene Locks regelmäßig."""
        while not self._shutdown_event.is_set():
            try:
                with self.get_cursor() as cur:
                    cur.execute("SELECT dbai_system.cleanup_expired_locks()")
                    count = cur.fetchone()["cleanup_expired_locks"]
                    if count > 0:
                        logger.info(
                            "%d abgelaufene Locks bereinigt", count
                        )
                    self.conn.commit()
            except Exception as e:
                logger.debug("Lock-Cleanup fehlgeschlagen: %s", e)
                try:
                    self.conn.rollback()
                except Exception:
                    pass
            self._shutdown_event.wait(10)  # Alle 10 Sekunden

    # ------------------------------------------------------------------
    # 7. Smart Vacuum Service
    # ------------------------------------------------------------------
    def _vacuum_loop(self):
        """Führt intelligentes Vacuum durch."""
        while not self._shutdown_event.is_set():
            try:
                # Vacuum braucht Autocommit
                old_autocommit = self.conn.autocommit
                self.conn.autocommit = True
                with self.get_cursor() as cur:
                    cur.execute("SELECT * FROM dbai_system.smart_vacuum()")
                    results = cur.fetchall()
                    for row in results:
                        logger.info(
                            "Vacuum: %s (%d dead tuples) → %s",
                            row["vacuumed_table"],
                            row["dead_tuples"],
                            row["action_taken"],
                        )
                self.conn.autocommit = old_autocommit
            except Exception as e:
                logger.debug("Vacuum fehlgeschlagen: %s", e)
                try:
                    self.conn.autocommit = False
                except Exception:
                    pass
            self._shutdown_event.wait(300)  # Alle 5 Minuten

    # ------------------------------------------------------------------
    # Hilfsfunktionen
    # ------------------------------------------------------------------
    @staticmethod
    def _md5(data: str) -> str:
        import hashlib
        return hashlib.md5(data.encode()).hexdigest()

    # ------------------------------------------------------------------
    # Boot-Sequenz
    # ------------------------------------------------------------------
    def boot(self) -> bool:
        """
        Komplette Boot-Sequenz des DBAI-Systems.
        Dies ist der Zündschlüssel.
        """
        logger.info("=" * 60)
        logger.info("DBAI System Bridge — Boot-Sequenz gestartet")
        logger.info("=" * 60)

        # Schritt 1: Datenbankverbindung
        logger.info("[1/7] Datenbankverbindung herstellen…")
        if not self.connect_db():
            logger.critical("BOOT FEHLGESCHLAGEN: Keine Datenbankverbindung")
            return False

        # Schritt 2: Schema-Prüfung
        logger.info("[2/7] Schema-Integrität prüfen…")
        if not self.verify_schemas():
            logger.critical("BOOT FEHLGESCHLAGEN: Schema-Integrität verletzt")
            return False

        # Schritt 3: System Bridge als Prozess registrieren
        logger.info("[3/7] System Bridge registrieren…")
        self.register_process("system_bridge", "system", priority=1)

        # Schritt 4: Hardware-Monitor starten
        logger.info("[4/7] Hardware-Monitor starten…")
        try:
            from hardware_monitor import HardwareMonitor

            self.hw_monitor = HardwareMonitor(self.conn, self._shutdown_event)
            hw_thread = threading.Thread(
                target=self.hw_monitor.run, daemon=True, name="hw-monitor"
            )
            hw_thread.start()
            self.register_process("hardware_monitor", "monitor", priority=2)
            logger.info("Hardware-Monitor gestartet")
        except ImportError:
            logger.warning(
                "Hardware-Monitor nicht verfügbar (hardware_monitor.py fehlt)"
            )

        # Schritt 5: Hintergrund-Services starten
        logger.info("[5/7] Hintergrund-Services starten…")
        services = {
            "heartbeat": self._heartbeat_loop,
            "snapshot": self._snapshot_loop,
            "lock_cleanup": self._lock_cleanup_loop,
        }
        for name, target in services.items():
            t = threading.Thread(target=target, daemon=True, name=name)
            t.start()
            logger.info("  → %s gestartet", name)

        # Schritt 6: LLM-Bridge initialisieren
        logger.info("[6/7] LLM-Bridge initialisieren…")
        try:
            sys.path.insert(0, str(DBAI_ROOT / "llm"))
            from llm_bridge import LLMBridge

            self.llm_bridge = LLMBridge(self.conn, self._shutdown_event)
            llm_thread = threading.Thread(
                target=self.llm_bridge.run, daemon=True, name="llm-bridge"
            )
            llm_thread.start()
            self.register_process("llm_bridge", "llm", priority=7)
            logger.info("LLM-Bridge gestartet")
        except ImportError:
            logger.warning("LLM-Bridge nicht verfügbar (llm_bridge.py fehlt)")

        # Schritt 7: Vacuum-Service starten
        logger.info("[7/7] Vacuum-Service starten…")
        vacuum_thread = threading.Thread(
            target=self._vacuum_loop, daemon=True, name="vacuum"
        )
        vacuum_thread.start()

        self.running = True
        logger.info("=" * 60)
        logger.info("DBAI System erfolgreich gebootet!")
        logger.info("=" * 60)
        return True

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------
    def shutdown(self):
        """Sauberes Herunterfahren aller Subsysteme."""
        logger.info("System-Shutdown eingeleitet…")
        self._shutdown_event.set()
        self.running = False

        # Alle Prozesse als gestoppt markieren
        try:
            with self.get_cursor() as cur:
                for name, proc_id in self.subsystems.items():
                    cur.execute(
                        """
                        UPDATE dbai_core.processes
                        SET state = 'stopped', stopped_at = NOW()
                        WHERE id = %s
                        """,
                        (str(proc_id),),
                    )
                self.conn.commit()
        except Exception as e:
            logger.error("Fehler beim Shutdown: %s", e)

        # Datenbankverbindung schließen
        if self.conn and not self.conn.closed:
            self.conn.close()

        logger.info("System-Shutdown abgeschlossen")

    # ------------------------------------------------------------------
    # Hauptschleife
    # ------------------------------------------------------------------
    def run(self):
        """Startet das System und wartet auf Shutdown-Signal."""
        if not self.boot():
            sys.exit(1)

        logger.info("System läuft. Drücke Ctrl+C zum Beenden.")
        try:
            while not self._shutdown_event.is_set():
                self._shutdown_event.wait(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()


# ======================================================================
# Einstiegspunkt
# ======================================================================
def main():
    import argparse

    parser = argparse.ArgumentParser(description="DBAI System Bridge")
    parser.add_argument(
        "action",
        choices=["start", "status", "stop"],
        help="Aktion: start, status, stop",
    )
    args = parser.parse_args()

    bridge = SystemBridge()

    if args.action == "start":
        bridge.run()
    elif args.action == "status":
        if bridge.connect_db():
            with bridge.get_cursor() as cur:
                cur.execute(
                    "SELECT name, state, last_heartbeat "
                    "FROM dbai_core.processes "
                    "WHERE state = 'running' ORDER BY priority"
                )
                processes = cur.fetchall()
                if processes:
                    print("\nLaufende DBAI-Prozesse:")
                    print("-" * 60)
                    for p in processes:
                        print(
                            f"  {p['name']:30s} {p['state']:10s} "
                            f"HB: {p['last_heartbeat']}"
                        )
                else:
                    print("Keine DBAI-Prozesse laufen.")
    elif args.action == "stop":
        if bridge.connect_db():
            with bridge.get_cursor() as cur:
                cur.execute(
                    """
                    UPDATE dbai_core.processes
                    SET state = 'stopped', stopped_at = NOW()
                    WHERE state = 'running'
                    """
                )
                bridge.conn.commit()
                print("Alle DBAI-Prozesse gestoppt.")


if __name__ == "__main__":
    main()
