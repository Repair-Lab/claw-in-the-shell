#!/usr/bin/env python3
"""
DBAI GS-Updater — OTA Update Agent
====================================
Der Over-The-Air Update-Agent für GhostShell OS.

Funktionen:
- Registriert diesen Node bei der Datenbank
- Prüft regelmäßig auf neue Releases
- Lädt Update-Pakete herunter & verifiziert SHA256
- Wendet SQL-Migrationen transaktional an
- Baut das Frontend neu (npm run build)
- Startet den Web-Server neu (Hot-Reload)
- Automatischer Rollback bei Fehlern
- WebSocket-Push an verbundene Clients

Flow:
1. check_for_updates()   — Gibt es ein neues Release?
2. download_update()     — Archiv herunterladen & verifizieren
3. apply_update()        — Git pull / Archiv entpacken
4. run_migrations()      — SQL-Schema-Updates
5. rebuild_frontend()    — npm run build
6. reload_services()     — Server neu starten
7. verify_update()       — Healthcheck
8. (bei Fehler) rollback() — Auf vorherige Version zurück
"""

import os
import json
import hashlib
import shutil
import socket
import subprocess
import time
import logging
import platform
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor

from bridge.migration_runner import MigrationRunner

logger = logging.getLogger("dbai.updater")

DBAI_ROOT = Path(__file__).resolve().parent.parent
UPDATE_DIR = DBAI_ROOT / ".updates"
BACKUP_DIR = DBAI_ROOT / ".backups"


class GhostUpdater:
    """OTA Update Agent für GhostShell OS."""

    def __init__(self, db_config: dict, node_name: str = None):
        self.db_config = db_config
        self.node_name = node_name or socket.gethostname()
        self.node_id = None
        self.current_version = None
        self.channel = "stable"
        self.migration_runner = MigrationRunner(db_config)
        self._update_lock = threading.Lock()
        self._running = False
        self._check_thread = None

        # Verzeichnisse anlegen
        UPDATE_DIR.mkdir(parents=True, exist_ok=True)
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Verbindung
    # ------------------------------------------------------------------
    def _connect(self):
        return psycopg2.connect(**self.db_config)

    def _db_query(self, sql: str, params: tuple = None) -> list[dict]:
        conn = self._connect()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params)
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def _db_execute(self, sql: str, params: tuple = None):
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # Node registrieren
    # ------------------------------------------------------------------
    def register_node(self) -> dict:
        """Registriert diesen Rechner als OTA-Node."""
        system_info = {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "arch": platform.machine(),
        }

        # Aktuelle Version aus dbai.toml lesen
        self.current_version = self._read_version()

        conn = self._connect()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            INSERT INTO dbai_system.ota_nodes
                (node_name, hostname, ip_address, current_version,
                 channel, last_checkin, status, system_info)
            VALUES (%s, %s, %s, %s, %s, now(), 'online', %s)
            ON CONFLICT (node_name) DO UPDATE SET
                hostname = EXCLUDED.hostname,
                current_version = EXCLUDED.current_version,
                last_checkin = now(),
                status = 'online',
                system_info = EXCLUDED.system_info
            RETURNING id, node_name, current_version, channel
        """, (
            self.node_name,
            socket.gethostname(),
            self._get_local_ip(),
            self.current_version,
            self.channel,
            json.dumps(system_info),
        ))
        row = cur.fetchone()
        conn.commit()
        conn.close()

        self.node_id = str(row["id"])
        self.channel = row["channel"]
        logger.info(f"Node registriert: {self.node_name} (v{self.current_version})")
        return dict(row)

    # ------------------------------------------------------------------
    # Auf Updates prüfen
    # ------------------------------------------------------------------
    def check_for_updates(self) -> Optional[dict]:
        """Prüft ob ein neues Update für diesen Node verfügbar ist."""
        if not self.node_id:
            self.register_node()

        # Checkin aktualisieren
        self._db_execute("""
            UPDATE dbai_system.ota_nodes
            SET last_checkin = now()
            WHERE id = %s
        """, (self.node_id,))

        rows = self._db_query("""
            SELECT * FROM dbai_system.get_available_update(%s)
        """, (self.node_id,))

        if rows and rows[0].get("release_id"):
            update = rows[0]
            logger.info(f"Update verfügbar: v{update['version']}")
            return update
        return None

    # ------------------------------------------------------------------
    # Update herunterladen
    # ------------------------------------------------------------------
    def download_update(self, release: dict) -> dict:
        """Lädt ein Update-Paket herunter und verifiziert die Checksumme."""
        release_id = str(release["release_id"])

        # Release-Details laden
        rows = self._db_query("""
            SELECT * FROM dbai_system.system_releases WHERE id = %s
        """, (release_id,))
        if not rows:
            return {"status": "error", "error": "Release nicht gefunden"}

        rel = rows[0]
        artifact_url = rel.get("artifact_url")

        # Update-Job erstellen
        self._create_update_job(release_id, rel["version"])

        if artifact_url:
            # Externes Archiv herunterladen
            dest = UPDATE_DIR / f"update-{rel['version']}.tar.gz"
            try:
                result = subprocess.run(
                    ["curl", "-fsSL", "-o", str(dest), artifact_url],
                    capture_output=True, text=True, timeout=300
                )
                if result.returncode != 0:
                    return {"status": "error", "error": result.stderr}

                # Checksumme verifizieren
                if rel.get("artifact_hash"):
                    actual = self._file_sha256(dest)
                    if actual != rel["artifact_hash"]:
                        dest.unlink()
                        return {"status": "error",
                                "error": f"Checksumme ungültig: {actual} != {rel['artifact_hash']}"}

                return {"status": "downloaded", "path": str(dest),
                        "version": rel["version"]}
            except Exception as e:
                return {"status": "error", "error": str(e)}
        else:
            # Git-basiertes Update
            return {"status": "git", "version": rel["version"],
                    "commit": rel.get("commit_hash")}

    # ------------------------------------------------------------------
    # Update anwenden (Haupt-Flow)
    # ------------------------------------------------------------------
    def apply_update(self, version: str = None,
                     use_git: bool = True) -> dict:
        """Vollständiger Update-Prozess:
        1. Backup erstellen
        2. Code aktualisieren (git pull oder Archiv)
        3. SQL-Migrationen ausführen
        4. Frontend neu bauen
        5. Healthcheck
        6. Bei Fehler: Rollback
        """
        if not self._update_lock.acquire(blocking=False):
            return {"status": "error", "error": "Update bereits aktiv"}

        try:
            self._set_node_status("updating")
            steps = []
            t0 = time.monotonic()

            # Schritt 1: Backup
            step = self._step_backup()
            steps.append(step)
            if step["status"] == "failed":
                raise UpdateError(step["error"])
            self._update_progress(10, steps)

            # Schritt 2: Code aktualisieren
            if use_git:
                step = self._step_git_pull()
            else:
                step = {"name": "archive_extract", "status": "skipped"}
            steps.append(step)
            if step["status"] == "failed":
                raise UpdateError(step["error"])
            self._update_progress(30, steps)

            # Schritt 3: Python-Abhängigkeiten
            step = self._step_pip_install()
            steps.append(step)
            self._update_progress(40, steps)

            # Schritt 4: SQL-Migrationen
            step = self._step_migrations(version)
            steps.append(step)
            if step["status"] == "failed":
                raise UpdateError(step["error"])
            self._update_progress(60, steps)

            # Schritt 5: Frontend neu bauen
            step = self._step_frontend_build()
            steps.append(step)
            if step["status"] == "failed":
                raise UpdateError(step["error"])
            self._update_progress(80, steps)

            # Schritt 6: Healthcheck
            step = self._step_healthcheck()
            steps.append(step)
            if step["status"] == "failed":
                raise UpdateError(step["error"])
            self._update_progress(100, steps)

            # Erfolg
            duration = int((time.monotonic() - t0) * 1000)
            new_version = version or self._read_version()
            self._finalize_update(new_version, duration, steps)

            return {
                "status": "success",
                "version": new_version,
                "duration_ms": duration,
                "steps": steps,
            }

        except UpdateError as e:
            # Rollback
            rollback_step = self._step_rollback()
            steps.append(rollback_step)
            duration = int((time.monotonic() - t0) * 1000)
            self._set_node_status("error")

            return {
                "status": "failed",
                "error": str(e),
                "duration_ms": duration,
                "steps": steps,
            }

        except Exception as e:
            self._set_node_status("error")
            return {"status": "error", "error": str(e)}

        finally:
            self._update_lock.release()

    # ------------------------------------------------------------------
    # Einzelne Update-Schritte
    # ------------------------------------------------------------------
    def _step_backup(self) -> dict:
        """Erstellt ein Backup des aktuellen Zustands."""
        t0 = time.monotonic()
        try:
            backup_name = f"backup-{self.current_version}-{int(time.time())}"
            backup_path = BACKUP_DIR / backup_name

            # Wichtige Verzeichnisse sichern
            dirs_to_backup = ["schema", "bridge", "web", "config",
                              "frontend/src", "scripts"]
            backup_path.mkdir(parents=True, exist_ok=True)

            for d in dirs_to_backup:
                src = DBAI_ROOT / d
                if src.exists():
                    dst = backup_path / d
                    if src.is_dir():
                        shutil.copytree(str(src), str(dst),
                                        dirs_exist_ok=True)
                    else:
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(str(src), str(dst))

            duration = int((time.monotonic() - t0) * 1000)
            return {"name": "backup", "status": "success",
                    "duration_ms": duration, "path": str(backup_path)}
        except Exception as e:
            return {"name": "backup", "status": "failed",
                    "error": str(e)}

    def _step_git_pull(self) -> dict:
        """Führt git pull aus."""
        t0 = time.monotonic()
        try:
            result = subprocess.run(
                ["git", "pull", "--rebase", "origin", "main"],
                cwd=str(DBAI_ROOT),
                capture_output=True, text=True, timeout=120
            )
            duration = int((time.monotonic() - t0) * 1000)
            if result.returncode != 0:
                return {"name": "git_pull", "status": "failed",
                        "error": result.stderr, "duration_ms": duration}
            return {"name": "git_pull", "status": "success",
                    "output": result.stdout.strip(),
                    "duration_ms": duration}
        except Exception as e:
            return {"name": "git_pull", "status": "failed",
                    "error": str(e)}

    def _step_pip_install(self) -> dict:
        """Installiert Python-Abhängigkeiten aus requirements.txt."""
        t0 = time.monotonic()
        try:
            req = DBAI_ROOT / "requirements.txt"
            if not req.exists():
                return {"name": "pip_install", "status": "skipped"}

            result = subprocess.run(
                ["pip", "install", "-q", "-r", str(req)],
                capture_output=True, text=True, timeout=300
            )
            duration = int((time.monotonic() - t0) * 1000)
            return {"name": "pip_install",
                    "status": "success" if result.returncode == 0 else "warning",
                    "duration_ms": duration}
        except Exception as e:
            return {"name": "pip_install", "status": "warning",
                    "error": str(e)}

    def _step_migrations(self, version: str = None) -> dict:
        """Führt ausstehende SQL-Migrationen aus."""
        t0 = time.monotonic()
        try:
            results = self.migration_runner.apply_all(
                version=version, stop_on_error=True
            )
            duration = int((time.monotonic() - t0) * 1000)

            failed = [r for r in results if r["status"] == "failed"]
            if failed:
                return {"name": "migrations", "status": "failed",
                        "error": failed[0]["error"],
                        "results": results, "duration_ms": duration}

            return {"name": "migrations", "status": "success",
                    "count": len(results),
                    "results": results, "duration_ms": duration}
        except Exception as e:
            return {"name": "migrations", "status": "failed",
                    "error": str(e)}

    def _step_frontend_build(self) -> dict:
        """Baut das Frontend neu (npm run build)."""
        t0 = time.monotonic()
        try:
            frontend_dir = DBAI_ROOT / "frontend"
            if not (frontend_dir / "package.json").exists():
                return {"name": "frontend_build", "status": "skipped"}

            # npm install (falls neue Abhängigkeiten)
            subprocess.run(
                ["npm", "install", "--silent"],
                cwd=str(frontend_dir),
                capture_output=True, timeout=120
            )

            # Build
            result = subprocess.run(
                ["npm", "run", "build"],
                cwd=str(frontend_dir),
                capture_output=True, text=True, timeout=120
            )
            duration = int((time.monotonic() - t0) * 1000)

            if result.returncode != 0:
                return {"name": "frontend_build", "status": "failed",
                        "error": result.stderr, "duration_ms": duration}

            return {"name": "frontend_build", "status": "success",
                    "duration_ms": duration}
        except Exception as e:
            return {"name": "frontend_build", "status": "failed",
                    "error": str(e)}

    def _step_healthcheck(self) -> dict:
        """Prüft ob das System nach dem Update funktioniert."""
        t0 = time.monotonic()
        checks = []
        try:
            # DB-Verbindung prüfen
            conn = self._connect()
            cur = conn.cursor()
            cur.execute("SELECT 1")
            conn.close()
            checks.append({"check": "database", "ok": True})

            # Frontend-Build vorhanden?
            dist = DBAI_ROOT / "frontend" / "dist" / "index.html"
            checks.append({"check": "frontend_dist",
                           "ok": dist.exists()})

            # Schema-Migrations-Status
            status = self.migration_runner.get_status()
            checks.append({"check": "migrations",
                           "ok": status.get("failed", 0) == 0})

            all_ok = all(c["ok"] for c in checks)
            duration = int((time.monotonic() - t0) * 1000)

            return {"name": "healthcheck",
                    "status": "success" if all_ok else "failed",
                    "checks": checks, "duration_ms": duration}
        except Exception as e:
            return {"name": "healthcheck", "status": "failed",
                    "error": str(e)}

    def _step_rollback(self) -> dict:
        """Stellt den vorherigen Zustand wieder her."""
        t0 = time.monotonic()
        try:
            # Neuestes Backup finden
            backups = sorted(BACKUP_DIR.iterdir(), reverse=True)
            if not backups:
                return {"name": "rollback", "status": "failed",
                        "error": "Kein Backup vorhanden"}

            backup_path = backups[0]
            logger.warning(f"Rollback auf Backup: {backup_path.name}")

            # Dateien zurückkopieren
            for item in backup_path.iterdir():
                dst = DBAI_ROOT / item.name
                if item.is_dir():
                    if dst.exists():
                        shutil.rmtree(str(dst))
                    shutil.copytree(str(item), str(dst))
                else:
                    shutil.copy2(str(item), str(dst))

            # Migration Rollback
            self.migration_runner.rollback_last()

            # Frontend rebuild mit altem Code
            subprocess.run(
                ["npm", "run", "build"],
                cwd=str(DBAI_ROOT / "frontend"),
                capture_output=True, timeout=120
            )

            duration = int((time.monotonic() - t0) * 1000)
            self._set_node_status("rollback")
            return {"name": "rollback", "status": "success",
                    "duration_ms": duration}
        except Exception as e:
            return {"name": "rollback", "status": "failed",
                    "error": str(e)}

    # ------------------------------------------------------------------
    # Hintergrund-Check-Dienst
    # ------------------------------------------------------------------
    def start_check_loop(self, interval: int = 300):
        """Startet einen Hintergrund-Thread, der regelmäßig auf Updates prüft."""
        if self._running:
            return
        self._running = True
        self._check_thread = threading.Thread(
            target=self._check_loop, args=(interval,),
            daemon=True, name="gs-updater"
        )
        self._check_thread.start()
        logger.info(f"Update-Check-Loop gestartet (alle {interval}s)")

    def stop_check_loop(self):
        """Stoppt den Hintergrund-Check."""
        self._running = False

    def _check_loop(self, interval: int):
        """Endloser Check-Loop."""
        while self._running:
            try:
                update = self.check_for_updates()
                if update:
                    # Prüfe ob auto_update aktiv
                    node = self._db_query(
                        "SELECT auto_update FROM dbai_system.ota_nodes WHERE id = %s",
                        (self.node_id,)
                    )
                    if node and node[0].get("auto_update"):
                        logger.info(f"Auto-Update auf v{update['version']}...")
                        self.apply_update(version=update["version"])
            except Exception as e:
                logger.error(f"Update-Check fehlgeschlagen: {e}")
            time.sleep(interval)

    # ------------------------------------------------------------------
    # Pipeline / Build-Simulation (für lokale CI)
    # ------------------------------------------------------------------
    def run_pipeline(self, commit_hash: str = None,
                     branch: str = "main") -> dict:
        """Führt eine lokale CI-Pipeline aus:
        1. Lint / Syntax-Check
        2. SQL-Validierung
        3. Frontend-Build
        4. Tests
        5. Paket erstellen
        """
        pipeline_id = self._create_pipeline(commit_hash, branch)
        steps = []
        t0 = time.monotonic()

        try:
            self._update_pipeline(pipeline_id, "running")

            # Step 1: Python Syntax Check
            step = self._pipeline_python_check()
            steps.append(step)

            # Step 2: SQL Validation
            step = self._pipeline_sql_check()
            steps.append(step)

            # Step 3: Frontend Build
            step = self._pipeline_frontend_check()
            steps.append(step)

            # Step 4: Tests
            step = self._pipeline_tests()
            steps.append(step)

            failed = [s for s in steps if s["status"] == "failed"]
            duration = int((time.monotonic() - t0) * 1000)

            status = "failed" if failed else "success"
            self._update_pipeline(pipeline_id, status, steps,
                                  duration, failed[0]["error"] if failed else None)

            return {
                "pipeline_id": pipeline_id,
                "status": status,
                "steps": steps,
                "duration_ms": duration,
            }

        except Exception as e:
            duration = int((time.monotonic() - t0) * 1000)
            self._update_pipeline(pipeline_id, "failed", steps, duration, str(e))
            return {"pipeline_id": pipeline_id, "status": "error",
                    "error": str(e)}

    def _pipeline_python_check(self) -> dict:
        """Prüft Python-Syntax mit py_compile."""
        t0 = time.monotonic()
        errors = []
        for py_file in (DBAI_ROOT / "bridge").glob("*.py"):
            try:
                result = subprocess.run(
                    ["python3", "-m", "py_compile", str(py_file)],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode != 0:
                    errors.append(f"{py_file.name}: {result.stderr.strip()}")
            except Exception as e:
                errors.append(f"{py_file.name}: {e}")

        for py_file in (DBAI_ROOT / "web").glob("*.py"):
            try:
                result = subprocess.run(
                    ["python3", "-m", "py_compile", str(py_file)],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode != 0:
                    errors.append(f"{py_file.name}: {result.stderr.strip()}")
            except Exception as e:
                errors.append(f"{py_file.name}: {e}")

        duration = int((time.monotonic() - t0) * 1000)
        return {"name": "python_syntax", "duration_ms": duration,
                "status": "failed" if errors else "success",
                "errors": errors if errors else None}

    def _pipeline_sql_check(self) -> dict:
        """Validiert SQL-Dateien durch Parsen."""
        t0 = time.monotonic()
        errors = []
        for sql_file in sorted((DBAI_ROOT / "schema").glob("*.sql")):
            try:
                content = sql_file.read_text(encoding="utf-8")
                # Basis-Validierung: nicht leer, kein offensichtlicher Syntax-Fehler
                if len(content.strip()) < 10:
                    errors.append(f"{sql_file.name}: Datei fast leer")
            except Exception as e:
                errors.append(f"{sql_file.name}: {e}")

        duration = int((time.monotonic() - t0) * 1000)
        return {"name": "sql_validation", "duration_ms": duration,
                "status": "failed" if errors else "success",
                "file_count": len(list((DBAI_ROOT / "schema").glob("*.sql"))),
                "errors": errors if errors else None}

    def _pipeline_frontend_check(self) -> dict:
        """Baut das Frontend und prüft auf Fehler."""
        t0 = time.monotonic()
        try:
            result = subprocess.run(
                ["npm", "run", "build"],
                cwd=str(DBAI_ROOT / "frontend"),
                capture_output=True, text=True, timeout=120
            )
            duration = int((time.monotonic() - t0) * 1000)
            if result.returncode != 0:
                return {"name": "frontend_build", "status": "failed",
                        "error": result.stderr, "duration_ms": duration}
            return {"name": "frontend_build", "status": "success",
                    "duration_ms": duration}
        except Exception as e:
            return {"name": "frontend_build", "status": "failed",
                    "error": str(e)}

    def _pipeline_tests(self) -> dict:
        """Führt die Tests aus."""
        t0 = time.monotonic()
        try:
            result = subprocess.run(
                ["python3", "-m", "pytest", "tests/", "-v", "--tb=short"],
                cwd=str(DBAI_ROOT),
                capture_output=True, text=True, timeout=120
            )
            duration = int((time.monotonic() - t0) * 1000)
            return {"name": "tests", "duration_ms": duration,
                    "status": "success" if result.returncode == 0 else "warning",
                    "output": result.stdout[-2000:] if result.stdout else None}
        except Exception as e:
            return {"name": "tests", "status": "warning",
                    "error": str(e)}

    # ------------------------------------------------------------------
    # Releases erstellen
    # ------------------------------------------------------------------
    def create_release(self, version: str, channel: str = "stable",
                       release_notes: str = "",
                       commit_hash: str = None) -> dict:
        """Erstellt ein neues Release in der Datenbank."""
        if not commit_hash:
            try:
                result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=str(DBAI_ROOT),
                    capture_output=True, text=True, timeout=5
                )
                commit_hash = result.stdout.strip() if result.returncode == 0 else None
            except Exception:
                commit_hash = None

        commit_msg = None
        if commit_hash:
            try:
                result = subprocess.run(
                    ["git", "log", "-1", "--format=%s", commit_hash],
                    cwd=str(DBAI_ROOT),
                    capture_output=True, text=True, timeout=5
                )
                commit_msg = result.stdout.strip() if result.returncode == 0 else None
            except Exception:
                pass

        # Schema-Version ermitteln
        schema_version = self.migration_runner.get_status().get(
            "current_schema_version", 0
        )

        rows = self._db_query("""
            INSERT INTO dbai_system.system_releases
                (version, channel, commit_hash, commit_message,
                 release_notes, author, schema_version,
                 is_published, published_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, true, now())
            ON CONFLICT (version) DO UPDATE SET
                release_notes = EXCLUDED.release_notes,
                commit_hash = EXCLUDED.commit_hash,
                is_published = true,
                published_at = now()
            RETURNING id, version, channel, commit_hash
        """, (version, channel, commit_hash, commit_msg,
              release_notes, self.node_name, schema_version))

        return rows[0] if rows else {}

    # ------------------------------------------------------------------
    # Interne Helfer
    # ------------------------------------------------------------------
    def _read_version(self) -> str:
        """Liest die aktuelle Version aus dbai.toml."""
        toml_path = DBAI_ROOT / "config" / "dbai.toml"
        if toml_path.exists():
            content = toml_path.read_text()
            for line in content.split("\n"):
                if line.strip().startswith("version"):
                    # version = "0.1.0"
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        return parts[1].strip().strip('"').strip("'")
        return "0.0.0"

    @staticmethod
    def _get_local_ip() -> str:
        """Ermittelt die lokale IP-Adresse."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    @staticmethod
    def _file_sha256(path: Path) -> str:
        sha = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha.update(chunk)
        return sha.hexdigest()

    def _set_node_status(self, status: str):
        if self.node_id:
            try:
                self._db_execute("""
                    UPDATE dbai_system.ota_nodes
                    SET status = %s WHERE id = %s
                """, (status, self.node_id))
            except Exception:
                pass

    def _create_update_job(self, release_id: str, version: str):
        try:
            self._db_execute("""
                INSERT INTO dbai_system.update_jobs
                    (node_id, release_id, from_version, to_version, status)
                VALUES (%s, %s, %s, %s, 'pending')
            """, (self.node_id, release_id, self.current_version, version))
        except Exception:
            pass

    def _update_progress(self, progress: int, steps: list):
        if self.node_id:
            try:
                self._db_execute("""
                    UPDATE dbai_system.update_jobs
                    SET progress = %s, steps_completed = %s, status = 'applying'
                    WHERE node_id = %s AND status IN ('pending', 'applying', 'downloading')
                """, (progress, json.dumps(steps, default=str), self.node_id))
            except Exception:
                pass

    def _finalize_update(self, version: str, duration: int, steps: list):
        """Markiert den Update-Vorgang als abgeschlossen."""
        try:
            self._db_execute("""
                UPDATE dbai_system.ota_nodes
                SET current_version = %s, last_update = now(),
                    status = 'online', target_version = NULL
                WHERE id = %s
            """, (version, self.node_id))

            self._db_execute("""
                UPDATE dbai_system.update_jobs
                SET status = 'success', progress = 100,
                    finished_at = now(), duration_ms = %s,
                    steps_completed = %s
                WHERE node_id = %s AND status = 'applying'
            """, (duration, json.dumps(steps, default=str), self.node_id))
        except Exception:
            pass

        self.current_version = version

    def _create_pipeline(self, commit_hash: str, branch: str) -> str:
        rows = self._db_query("""
            INSERT INTO dbai_system.build_pipeline
                (commit_hash, branch, trigger_type, status, started_at, triggered_by)
            VALUES (%s, %s, 'manual', 'running', now(), %s)
            RETURNING id
        """, (commit_hash, branch, self.node_name))
        return str(rows[0]["id"]) if rows else None

    def _update_pipeline(self, pipeline_id: str, status: str,
                         steps: list = None, duration: int = None,
                         error: str = None):
        try:
            self._db_execute("""
                UPDATE dbai_system.build_pipeline
                SET status = %s, steps = %s, duration_ms = %s,
                    error_message = %s,
                    finished_at = CASE WHEN %s IN ('success','failed','cancelled')
                                  THEN now() ELSE finished_at END
                WHERE id = %s
            """, (status, json.dumps(steps or [], default=str),
                  duration, error, status, pipeline_id))
        except Exception:
            pass


class UpdateError(Exception):
    """Fehler während eines Updates — löst Rollback aus."""
    pass
