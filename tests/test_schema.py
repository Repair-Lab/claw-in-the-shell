#!/usr/bin/env python3
"""
DBAI Tests — Datenbank-Schema-Integrität
Testet ob alle Schema-Dateien vorhanden und korrekt aufgebaut sind.
"""

import os
import sys
import re
import unittest
from pathlib import Path


class TestSchemaFilesExist(unittest.TestCase):
    """Prüft ob alle Schema-Dateien vorhanden sind."""

    SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"

    REQUIRED_SCHEMAS = [
        '00-extensions.sql',
        '01-core-tables.sql',
        '02-system-tables.sql',
        '03-event-tables.sql',
        '04-vector-tables.sql',
        '05-wal-journal.sql',
        '06-panic-schema.sql',
        '07-row-level-security.sql',
        '08-llm-integration.sql',
        '09-vacuum-schedule.sql',
        '10-sync-primitives.sql',
        '11-knowledge-library.sql',
        '12-error-patterns.sql',
        '13-seed-data.sql',
        '14-self-healing.sql',
        '15-ghost-system.sql',
        '16-desktop-ui.sql',
        '17-ghost-desktop-seed.sql',
        '18-hardware-abstraction.sql',
        '19-neural-bridge.sql',
        '20-hw-seed-data.sql',
    ]

    def test_all_schemas_exist(self):
        missing = []
        for schema in self.REQUIRED_SCHEMAS:
            if not (self.SCHEMA_DIR / schema).exists():
                missing.append(schema)
        self.assertEqual(len(missing), 0, f"Fehlende Schema-Dateien: {missing}")

    def test_schema_ordering(self):
        """Schema-Dateien müssen numerisch geordnet sein."""
        files = sorted(f.name for f in self.SCHEMA_DIR.glob("*.sql"))
        numbers = []
        for f in files:
            m = re.match(r'(\d+)', f)
            if m:
                numbers.append(int(m.group(1)))
        # Prüfe keine Lücken in Basis-Schemas (0-20)
        for i in range(21):
            self.assertIn(i, numbers, f"Schema {i:02d}-*.sql fehlt")


class TestSchemaSyntax(unittest.TestCase):
    """Prüft grundlegende SQL-Syntax der Schema-Dateien."""

    SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"

    def test_no_empty_schemas(self):
        """Keine leeren Schema-Dateien."""
        empty = []
        for f in self.SCHEMA_DIR.glob("*.sql"):
            if f.stat().st_size < 50:
                empty.append(f.name)
        self.assertEqual(len(empty), 0, f"Leere Schema-Dateien: {empty}")

    def test_schemas_contain_sql(self):
        """Schema-Dateien müssen gültiges SQL enthalten."""
        invalid = []
        sql_keywords = ['CREATE', 'INSERT', 'ALTER', 'SELECT', 'UPDATE', 'DELETE',
                        'DROP', 'GRANT', 'SET', 'BEGIN', 'DO']
        for f in self.SCHEMA_DIR.glob("*.sql"):
            content = f.read_text().upper()
            if not any(kw in content for kw in sql_keywords):
                invalid.append(f.name)
        self.assertEqual(len(invalid), 0, f"Schema-Dateien ohne SQL: {invalid}")


class TestSchemaNamespaces(unittest.TestCase):
    """Prüft ob alle erwarteten DB-Schemas referenziert werden."""

    SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"

    def test_core_schemas_referenced(self):
        """Alle Kern-Schemas müssen in Schema-Dateien referenziert sein."""
        all_content = ""
        for f in self.SCHEMA_DIR.glob("*.sql"):
            all_content += f.read_text()

        expected = ['dbai_core', 'dbai_system', 'dbai_ui', 'dbai_event',
                     'dbai_llm', 'dbai_knowledge', 'dbai_journal', 'dbai_panic',
                     'dbai_vector', 'dbai_workshop']
        missing = [s for s in expected if s not in all_content]
        self.assertEqual(len(missing), 0,
                         f"Fehlende Schema-Referenzen: {missing}")


class TestConfigFiles(unittest.TestCase):
    """Prüft Konfigurationsdateien."""

    PROJECT_DIR = Path(__file__).resolve().parent.parent

    def test_docker_compose_exists(self):
        self.assertTrue((self.PROJECT_DIR / "docker-compose.yml").exists())

    def test_dbai_toml_exists(self):
        self.assertTrue((self.PROJECT_DIR / "config" / "dbai.toml").exists())

    def test_requirements_exists(self):
        self.assertTrue((self.PROJECT_DIR / "requirements.txt").exists())

    def test_package_json_exists(self):
        self.assertTrue((self.PROJECT_DIR / "frontend" / "package.json").exists())

    def test_docker_compose_services(self):
        """docker-compose.yml muss alle Services enthalten."""
        content = (self.PROJECT_DIR / "docker-compose.yml").read_text()
        for svc in ['postgres', 'api', 'ui']:
            self.assertIn(svc, content, f"Docker-Service fehlt: {svc}")


class TestBridgeModules(unittest.TestCase):
    """Prüft ob Bridge-Module vorhanden sind."""

    BRIDGE_DIR = Path(__file__).resolve().parent.parent / "bridge"

    REQUIRED_MODULES = [
        'system_bridge.py', 'hardware_scanner.py', 'hardware_monitor.py',
        'gpu_manager.py', 'event_dispatcher.py', 'ghost_autonomy.py',
        'browser_migration.py', 'config_importer.py', 'workspace_mapper.py',
        'synaptic_pipeline.py', 'rag_pipeline.py', 'gs_updater.py',
        'openclaw_importer.py', 'migration_runner.py', 'app_manager.py',
        'stufe4_utils.py',
    ]

    def test_all_bridge_modules_exist(self):
        missing = []
        for mod in self.REQUIRED_MODULES:
            if not (self.BRIDGE_DIR / mod).exists():
                missing.append(mod)
        self.assertEqual(len(missing), 0, f"Fehlende Bridge-Module: {missing}")


if __name__ == '__main__':
    unittest.main()
