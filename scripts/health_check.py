#!/usr/bin/env python3
"""
DBAI Health Check
=================
Prüft alle Komponenten des DBAI-Systems.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone

# Ergebnis-Sammlung
results = {}
overall = "healthy"


def check(name: str, condition: bool, detail: str = ""):
    """Registriert ein Check-Ergebnis."""
    global overall
    status = "OK" if condition else "FAIL"
    if not condition:
        overall = "degraded"
    results[name] = {"status": status, "detail": detail}
    icon = "✓" if condition else "✗"
    print(f"  [{icon}] {name}: {detail}")


def main():
    global overall

    print("=" * 60)
    print("  DBAI System Health Check")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    DBAI_ROOT = Path(__file__).resolve().parent.parent

    # ------------------------------------------------------------------
    # 1. Dateisystem-Prüfung
    # ------------------------------------------------------------------
    print("[Dateisystem]")
    required_dirs = [
        "config", "schema", "bridge", "bridge/c_bindings",
        "recovery", "llm", "scripts", "tests",
    ]
    for d in required_dirs:
        path = DBAI_ROOT / d
        check(f"dir:{d}", path.is_dir(), str(path))

    # Schema-Dateien
    schema_count = len(list((DBAI_ROOT / "schema").glob("*.sql")))
    check("schema_files", schema_count >= 11, f"{schema_count} SQL-Dateien")

    # C-Bindings
    so_file = DBAI_ROOT / "bridge" / "c_bindings" / "libhw_interrupts.so"
    check("c_bindings", so_file.exists(), str(so_file))

    print()

    # ------------------------------------------------------------------
    # 2. PostgreSQL-Prüfung
    # ------------------------------------------------------------------
    print("[PostgreSQL]")

    # pg_isready
    pg_host = os.getenv("DBAI_DB_HOST", "127.0.0.1")
    pg_port = os.getenv("DBAI_DB_PORT", "5432")
    try:
        result = subprocess.run(
            ["pg_isready", "-h", pg_host, "-p", pg_port],
            capture_output=True, text=True, timeout=5,
        )
        check("pg_running", result.returncode == 0, f"{pg_host}:{pg_port}")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        check("pg_running", False, "pg_isready nicht verfügbar")

    # Datenbank-Verbindung
    db_name = os.getenv("DBAI_DB_NAME", "dbai")
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        conn = psycopg2.connect(
            host=pg_host, port=pg_port, dbname=db_name,
            user=os.getenv("DBAI_DB_USER", "dbai_system"),
            password=os.getenv("DBAI_DB_PASSWORD", ""),
            connect_timeout=5,
        )
        check("db_connection", True, f"Verbunden mit {db_name}")

        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Schemas prüfen
        cur.execute(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name LIKE 'dbai_%%'"
        )
        schemas = [r["schema_name"] for r in cur.fetchall()]
        check("db_schemas", len(schemas) >= 7, f"{len(schemas)} Schemas: {', '.join(schemas)}")

        # Tabellen prüfen
        cur.execute(
            "SELECT COUNT(*) as cnt FROM information_schema.tables "
            "WHERE table_schema LIKE 'dbai_%%'"
        )
        table_count = cur.fetchone()["cnt"]
        check("db_tables", table_count >= 20, f"{table_count} Tabellen")

        # Extensions prüfen
        cur.execute("SELECT extname FROM pg_extension")
        extensions = [r["extname"] for r in cur.fetchall()]
        check("ext_vector", "vector" in extensions, "pgvector")
        check("ext_uuid", "uuid-ossp" in extensions, "uuid-ossp")

        # Prozesse prüfen
        cur.execute(
            "SELECT name, state FROM dbai_core.processes "
            "WHERE state = 'running'"
        )
        processes = cur.fetchall()
        check(
            "running_processes",
            len(processes) > 0,
            f"{len(processes)} laufend",
        )

        # Journal prüfen
        cur.execute("SELECT COUNT(*) as cnt FROM dbai_journal.change_log")
        journal_count = cur.fetchone()["cnt"]
        check("journal", True, f"{journal_count} Einträge")

        # Panic-Status
        cur.execute(
            "SELECT COUNT(*) FILTER (WHERE resolved = FALSE) as unresolved "
            "FROM dbai_panic.panic_log"
        )
        unresolved = cur.fetchone()["unresolved"]
        check("no_panics", unresolved == 0, f"{unresolved} ungelöste Panics")

        # DB-Größe
        cur.execute(
            "SELECT pg_size_pretty(pg_database_size(%s)) as size", (db_name,)
        )
        db_size = cur.fetchone()["size"]
        check("db_size", True, db_size)

        conn.close()

    except ImportError:
        check("db_connection", False, "psycopg2 nicht installiert")
    except Exception as e:
        check("db_connection", False, str(e))

    print()

    # ------------------------------------------------------------------
    # 3. Python-Abhängigkeiten
    # ------------------------------------------------------------------
    print("[Python]")
    check("python_version", sys.version_info >= (3, 11), sys.version.split()[0])

    for pkg in ["psycopg2", "psutil"]:
        try:
            __import__(pkg)
            check(f"pkg:{pkg}", True, "installiert")
        except ImportError:
            check(f"pkg:{pkg}", False, "nicht installiert")

    # llama-cpp-python (optional)
    try:
        import llama_cpp
        check("pkg:llama_cpp", True, "installiert")
    except ImportError:
        check("pkg:llama_cpp", False, "nicht installiert (optional)")

    print()

    # ------------------------------------------------------------------
    # Zusammenfassung
    # ------------------------------------------------------------------
    fail_count = sum(1 for r in results.values() if r["status"] == "FAIL")
    ok_count = sum(1 for r in results.values() if r["status"] == "OK")

    print("=" * 60)
    if fail_count == 0:
        print(f"  Ergebnis: GESUND ({ok_count}/{ok_count + fail_count} Checks OK)")
    else:
        print(
            f"  Ergebnis: PROBLEME ({fail_count} Fehler, "
            f"{ok_count} OK von {ok_count + fail_count})"
        )
    print("=" * 60)

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
