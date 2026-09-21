#!/usr/bin/env python3
"""
DBAI Migration Runner
=====================
Transaktionale SQL-Schema-Migrationen mit automatischem Rollback.

Funktionen:
- Erkennt neue .sql Dateien im schema/ Ordner
- Berechnet SHA256-Checksums  (keine Doppelausführung)
- Führt jede Migration in einer eigenen Transaktion aus
- Schreibt Status in dbai_system.migration_history
- Unterstützt Dry-Run und Rollback
"""

import os
import hashlib
import time
import logging
import re
from pathlib import Path
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("dbai.migration")

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"


class MigrationRunner:
    """Verwaltet transaktionale SQL-Migrationen für DBAI."""

    def __init__(self, db_config: dict):
        self.db_config = db_config

    # ------------------------------------------------------------------
    # Verbindung
    # ------------------------------------------------------------------
    def _connect(self):
        return psycopg2.connect(**self.db_config)

    # ------------------------------------------------------------------
    # Hilfsfunktionen
    # ------------------------------------------------------------------
    @staticmethod
    def _file_checksum(path: Path) -> str:
        """SHA256 einer Datei."""
        sha = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha.update(chunk)
        return sha.hexdigest()

    @staticmethod
    def _extract_number(filename: str) -> int:
        """Extrahiert die Schema-Nummer aus dem Dateinamen (z.B. 33 aus '33-stufe3.sql')."""
        m = re.match(r"^(\d+)", filename)
        return int(m.group(1)) if m else 0

    # ------------------------------------------------------------------
    # Schema-Dateien erkennen
    # ------------------------------------------------------------------
    def discover(self) -> list[dict]:
        """Findet alle .sql Dateien im schema/ Ordner,
        sortiert nach Nummer."""
        files = []
        if not SCHEMA_DIR.exists():
            return files
        for p in sorted(SCHEMA_DIR.glob("*.sql")):
            num = self._extract_number(p.name)
            files.append({
                "file": p.name,
                "path": str(p),
                "number": num,
                "checksum": self._file_checksum(p),
                "size": p.stat().st_size,
            })
        files.sort(key=lambda x: x["number"])
        return files

    # ------------------------------------------------------------------
    # Bereits angewendete Migrationen
    # ------------------------------------------------------------------
    def get_applied(self) -> dict:
        """Gibt ein Dict {schema_file: checksum} aller erfolgreich
        angewendeten Migrationen zurück."""
        try:
            conn = self._connect()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("""
                SELECT schema_file, checksum, schema_number, finished_at
                FROM dbai_system.migration_history
                WHERE status = 'success'
                ORDER BY schema_number
            """)
            rows = cur.fetchall()
            conn.close()
            return {r["schema_file"]: r for r in rows}
        except psycopg2.errors.UndefinedTable:
            return {}
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Pending Migrationen
    # ------------------------------------------------------------------
    def get_pending(self) -> list[dict]:
        """Gibt alle noch nicht angewendeten Migrationen zurück."""
        applied = self.get_applied()
        pending = []
        for f in self.discover():
            if f["file"] not in applied:
                pending.append(f)
            elif applied[f["file"]]["checksum"] != f["checksum"]:
                f["changed"] = True
                pending.append(f)
        return pending

    # ------------------------------------------------------------------
    # Migration ausführen
    # ------------------------------------------------------------------
    def apply_one(self, schema_file: dict, version: str = None,
                  dry_run: bool = False) -> dict:
        """Führt eine einzelne Migration in einer Transaktion aus.

        Returns: {status, duration_ms, error}
        """
        result = {
            "file": schema_file["file"],
            "number": schema_file["number"],
            "status": "pending",
            "duration_ms": 0,
            "error": None,
        }

        sql_content = Path(schema_file["path"]).read_text(encoding="utf-8")

        if dry_run:
            result["status"] = "dry_run"
            result["sql_preview"] = sql_content[:500]
            return result

        conn = self._connect()
        conn.autocommit = False
        t0 = time.monotonic()

        try:
            # Status → running
            self._record_migration(conn, schema_file, version, "running")

            cur = conn.cursor()

            # SQL-Inhalt bereinigen: BEGIN/COMMIT entfernen,
            # da wir die Transaktion selbst steuern
            cleaned = self._strip_transaction_wrappers(sql_content)
            cur.execute(cleaned)

            conn.commit()
            duration = int((time.monotonic() - t0) * 1000)

            # Status → success
            self._update_migration(conn, schema_file["file"], "success",
                                   duration)
            result["status"] = "success"
            result["duration_ms"] = duration
            logger.info(f"Migration {schema_file['file']} erfolgreich ({duration}ms)")

        except Exception as e:
            conn.rollback()
            duration = int((time.monotonic() - t0) * 1000)
            error_msg = str(e)

            try:
                self._update_migration(conn, schema_file["file"], "failed",
                                       duration, error_msg)
            except Exception:
                pass

            result["status"] = "failed"
            result["duration_ms"] = duration
            result["error"] = error_msg
            logger.error(f"Migration {schema_file['file']} fehlgeschlagen: {error_msg}")

        finally:
            conn.close()

        return result

    # ------------------------------------------------------------------
    # Alle Pending anwenden
    # ------------------------------------------------------------------
    def apply_all(self, version: str = None, dry_run: bool = False,
                  stop_on_error: bool = True) -> list[dict]:
        """Wendet alle ausstehenden Migrationen der Reihe nach an."""
        pending = self.get_pending()
        results = []

        for schema_file in pending:
            r = self.apply_one(schema_file, version=version, dry_run=dry_run)
            results.append(r)
            if r["status"] == "failed" and stop_on_error:
                break

        return results

    # ------------------------------------------------------------------
    # Migrations-Status abfragen
    # ------------------------------------------------------------------
    def get_status(self) -> dict:
        """Gibt den aktuellen Migrations-Status zurück."""
        try:
            conn = self._connect()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM dbai_system.get_migration_status()")
            row = cur.fetchone()
            conn.close()
            return dict(row) if row else {}
        except Exception:
            return {}

    def get_history(self, limit: int = 50) -> list[dict]:
        """Gibt die letzten Migrationen zurück."""
        try:
            conn = self._connect()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("""
                SELECT id, schema_file, schema_number, version, checksum,
                       direction, status, started_at, finished_at,
                       duration_ms, error_message, applied_by
                FROM dbai_system.migration_history
                ORDER BY schema_number DESC, created_at DESC
                LIMIT %s
            """, (limit,))
            rows = cur.fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Rollback: Letzte erfolgreiche Migration als fehlgeschlagen markieren
    # ------------------------------------------------------------------
    def rollback_last(self) -> dict:
        """Markiert die letzte erfolgreiche Migration als rolled_back.
        (Tatsächliches SQL-Rollback erfordert ein Down-Migrations-File.)"""
        try:
            conn = self._connect()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("""
                UPDATE dbai_system.migration_history
                SET status = 'rolled_back', finished_at = now()
                WHERE id = (
                    SELECT id FROM dbai_system.migration_history
                    WHERE status = 'success'
                    ORDER BY schema_number DESC
                    LIMIT 1
                )
                RETURNING schema_file, schema_number
            """)
            row = cur.fetchone()
            conn.commit()
            conn.close()
            if row:
                return {"status": "rolled_back", "file": row["schema_file"]}
            return {"status": "nothing_to_rollback"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ------------------------------------------------------------------
    # Interne Helfer
    # ------------------------------------------------------------------
    def _record_migration(self, conn, schema_file: dict,
                          version: str, status: str):
        """Erstellt einen neuen Eintrag in migration_history."""
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO dbai_system.migration_history
                (schema_file, schema_number, version, checksum,
                 status, started_at)
            VALUES (%s, %s, %s, %s, %s, now())
            ON CONFLICT (schema_file) WHERE status = 'success'
            DO UPDATE SET status = EXCLUDED.status, started_at = now()
        """, (schema_file["file"], schema_file["number"],
              version, schema_file["checksum"], status))
        conn.commit()

    def _update_migration(self, conn, schema_file: str, status: str,
                          duration_ms: int, error: str = None):
        """Aktualisiert den Status einer Migration."""
        cur = conn.cursor()
        cur.execute("""
            UPDATE dbai_system.migration_history
            SET status = %s, finished_at = now(), duration_ms = %s,
                error_message = %s
            WHERE schema_file = %s
              AND status IN ('running', 'pending', 'failed')
            ORDER BY created_at DESC
            LIMIT 1
        """, (status, duration_ms, error, schema_file))
        conn.commit()

    @staticmethod
    def _strip_transaction_wrappers(sql: str) -> str:
        """Entfernt BEGIN/COMMIT Wrapper, da wir die Transaktion
        selbst steuern."""
        # Entferne alleinstehende BEGIN; und COMMIT; Zeilen
        lines = sql.split("\n")
        cleaned = []
        for line in lines:
            stripped = line.strip().upper()
            if stripped in ("BEGIN;", "COMMIT;", "BEGIN", "COMMIT"):
                continue
            cleaned.append(line)
        return "\n".join(cleaned)
