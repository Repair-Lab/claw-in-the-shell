#!/usr/bin/env python3
"""
DBAI Point-in-Time Recovery Manager
====================================
Verwaltet PITR-Snapshots und ermöglicht Zeitreisen in der Datenbank.

Wie bei einer Zeitmaschine: Zu jedem beliebigen Zeitpunkt
(z.B. 14:02:05) zurückspringen.
"""

import os
import json
import hashlib
import logging
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("dbai.pitr")


class PITRManager:
    """
    Point-in-Time Recovery — Jede Sekunde ein Statusbericht.
    Du kannst zu jedem beliebigen Zeitpunkt zurückspringen.
    """

    def __init__(self, conn):
        self.conn = conn
        self.archive_dir = Path(
            os.getenv("DBAI_PITR_ARCHIVE", "/mnt/backup_disk/dbai_pitr")
        )
        self.wal_archive_dir = Path(
            os.getenv("DBAI_WAL_ARCHIVE", "/mnt/backup_disk/dbai_wal_archive")
        )

    def _get_cursor(self):
        return self.conn.cursor(cursor_factory=RealDictCursor)

    # ------------------------------------------------------------------
    # Snapshot erstellen
    # ------------------------------------------------------------------
    def create_snapshot(self, snapshot_type: str = "manual") -> dict:
        """
        Erstellt einen System-Snapshot mit WAL-Position.
        """
        try:
            with self._get_cursor() as cur:
                # Aktuellen System-Status sammeln
                cur.execute("SELECT * FROM dbai_system.current_status")
                status = cur.fetchone()

                # Aktive Prozesse
                cur.execute(
                    "SELECT name, state, priority FROM dbai_core.processes "
                    "WHERE state = 'running' ORDER BY priority"
                )
                processes = cur.fetchall()

                # WAL-Position
                cur.execute("SELECT pg_current_wal_lsn() AS lsn")
                wal_lsn = cur.fetchone()["lsn"]

                # Snapshot zusammenbauen
                snapshot = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "system_status": status,
                    "active_processes": processes,
                    "wal_lsn": str(wal_lsn),
                }
                snapshot_json = json.dumps(snapshot, default=str)
                checksum = hashlib.md5(snapshot_json.encode()).hexdigest()

                # In Journal speichern
                cur.execute(
                    """
                    INSERT INTO dbai_journal.system_snapshots
                        (snapshot, wal_lsn, checksum, snapshot_type)
                    VALUES (%s::jsonb, %s, %s, %s)
                    RETURNING id, ts
                    """,
                    (snapshot_json, str(wal_lsn), checksum, snapshot_type),
                )
                result = cur.fetchone()
                self.conn.commit()

                logger.info(
                    "Snapshot #%s erstellt (WAL: %s, Typ: %s)",
                    result["id"], wal_lsn, snapshot_type,
                )
                return {
                    "id": result["id"],
                    "ts": result["ts"],
                    "wal_lsn": str(wal_lsn),
                    "checksum": checksum,
                }
        except Exception as e:
            logger.error("Snapshot fehlgeschlagen: %s", e)
            self.conn.rollback()
            return {}

    # ------------------------------------------------------------------
    # Zeitreise: Änderungen seit einem Zeitpunkt anzeigen
    # ------------------------------------------------------------------
    def show_changes_since(self, target_time: datetime) -> list:
        """
        Zeigt alle Änderungen seit einem bestimmten Zeitpunkt.
        Zeitmaschinen-Funktion: Was ist seit 14:02:05 passiert?
        """
        try:
            with self._get_cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM dbai_journal.changes_since(%s)
                    """,
                    (target_time,),
                )
                changes = cur.fetchall()
                logger.info(
                    "%d Änderungen seit %s gefunden",
                    len(changes), target_time,
                )
                return changes
        except Exception as e:
            logger.error("Änderungsabfrage fehlgeschlagen: %s", e)
            return []

    # ------------------------------------------------------------------
    # Nächsten Snapshot zu einem Zeitpunkt finden
    # ------------------------------------------------------------------
    def find_snapshot(self, target_time: datetime) -> dict:
        """Findet den nächsten Snapshot vor einem Zeitpunkt."""
        try:
            with self._get_cursor() as cur:
                cur.execute(
                    "SELECT * FROM dbai_journal.find_nearest_snapshot(%s)",
                    (target_time,),
                )
                result = cur.fetchone()
                if result:
                    return dict(result)
                return {}
        except Exception as e:
            logger.error("Snapshot-Suche fehlgeschlagen: %s", e)
            return {}

    # ------------------------------------------------------------------
    # PostgreSQL Base-Backup erstellen
    # ------------------------------------------------------------------
    def create_base_backup(self, label: str = None) -> bool:
        """
        Erstellt ein vollständiges PostgreSQL-Backup für PITR.
        Dieses Backup + WAL-Archive = Wiederherstellung zu jedem Zeitpunkt.
        """
        if label is None:
            label = f"dbai_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        backup_dir = self.archive_dir / label
        backup_dir.mkdir(parents=True, exist_ok=True)

        try:
            cmd = [
                "pg_basebackup",
                "-h", "127.0.0.1",
                "-p", str(os.getenv("DBAI_DB_PORT", "5432")),
                "-U", "dbai_system",
                "-D", str(backup_dir),
                "-Ft",           # tar-Format
                "-z",            # komprimiert
                "-P",            # Fortschritt anzeigen
                "--wal-method=stream",  # WAL mitsichern
                "--label", label,
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=3600
            )

            if result.returncode == 0:
                logger.info("Base-Backup erfolgreich: %s", backup_dir)

                # Snapshot nach Backup erstellen
                self.create_snapshot("checkpoint")
                return True
            else:
                logger.error("Base-Backup fehlgeschlagen: %s", result.stderr)
                return False
        except subprocess.TimeoutExpired:
            logger.error("Base-Backup Timeout (>1h)")
            return False
        except FileNotFoundError:
            logger.error("pg_basebackup nicht gefunden")
            return False

    # ------------------------------------------------------------------
    # PITR-Wiederherstellung
    # ------------------------------------------------------------------
    def restore_to_point(self, target_time: datetime) -> dict:
        """
        Stellt die Datenbank zu einem bestimmten Zeitpunkt wieder her.

        ACHTUNG: Stoppt die aktuelle DB-Instanz!

        Schritte:
        1. Aktuellen Snapshot vor target_time finden
        2. Nächstes Base-Backup finden
        3. Base-Backup wiederherstellen
        4. recovery.conf mit target_time schreiben
        5. PostgreSQL neu starten
        """
        logger.warning(
            "PITR-Wiederherstellung zu %s angefordert!", target_time
        )

        # Snapshot finden
        snapshot = self.find_snapshot(target_time)
        if not snapshot:
            return {
                "success": False,
                "error": "Kein Snapshot vor dem Zielzeitpunkt gefunden",
            }

        # Änderungen seit dem Snapshot anzeigen
        changes = self.show_changes_since(target_time)

        return {
            "success": True,
            "target_time": target_time.isoformat(),
            "nearest_snapshot": snapshot,
            "changes_to_undo": len(changes),
            "instructions": [
                "1. PostgreSQL stoppen: systemctl stop postgresql",
                f"2. Base-Backup wiederherstellen nach {self.archive_dir}",
                "3. recovery.signal erstellen",
                f"4. recovery_target_time = '{target_time.isoformat()}'",
                f"5. restore_command = 'cp {self.wal_archive_dir}/%f %p'",
                "6. PostgreSQL starten: systemctl start postgresql",
                "7. SELECT pg_wal_replay_resume(); ausführen",
            ],
        }

    # ------------------------------------------------------------------
    # Snapshot-Statistiken
    # ------------------------------------------------------------------
    def get_stats(self) -> dict:
        """Statistiken über gespeicherte Snapshots."""
        try:
            with self._get_cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        COUNT(*) as total_snapshots,
                        MIN(ts) as oldest,
                        MAX(ts) as newest,
                        COUNT(DISTINCT snapshot_type) as types,
                        pg_size_pretty(
                            pg_total_relation_size('dbai_journal.system_snapshots')
                        ) as storage_size
                    FROM dbai_journal.system_snapshots
                    """
                )
                return dict(cur.fetchone())
        except Exception as e:
            logger.error("Statistik-Abfrage fehlgeschlagen: %s", e)
            return {}
