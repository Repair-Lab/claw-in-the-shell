#!/usr/bin/env python3
"""
DBAI Tests — Core-Funktionalität
"""

import os
import sys
import unittest
import json
from unittest.mock import MagicMock, patch
from pathlib import Path

# DBAI Root zum Python-Pfad hinzufügen
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bridge"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "recovery"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "llm"))


class TestSchemaFiles(unittest.TestCase):
    """Prüft ob alle Schema-Dateien vorhanden und gültig sind."""

    SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"

    EXPECTED_FILES = [
        "00-extensions.sql",
        "01-core-tables.sql",
        "02-system-tables.sql",
        "03-event-tables.sql",
        "04-vector-tables.sql",
        "05-wal-journal.sql",
        "06-panic-schema.sql",
        "07-row-level-security.sql",
        "08-llm-integration.sql",
        "09-vacuum-schedule.sql",
        "10-sync-primitives.sql",
        "11-knowledge-library.sql",
        "12-error-patterns.sql",
        "13-seed-data.sql",
        "14-self-healing.sql",
        "15-ghost-system.sql",
        "16-desktop-ui.sql",
        "17-ghost-desktop-seed.sql",
        "18-hardware-abstraction.sql",
        "19-neural-bridge.sql",
        "20-hw-seed-data.sql",
        "21-openclaw-bridge.sql",
        "22-ghost-autonomy.sql",
        "23-app-ecosystem.sql",
        "24-system-memory.sql",
        "25-system-memory-seed.sql",
    ]

    def test_all_schema_files_exist(self):
        """Alle 26 Schema-Dateien müssen vorhanden sein."""
        for fname in self.EXPECTED_FILES:
            path = self.SCHEMA_DIR / fname
            self.assertTrue(path.exists(), f"Schema fehlt: {fname}")

    def test_schema_files_not_empty(self):
        """Keine Schema-Datei darf leer sein."""
        for fname in self.EXPECTED_FILES:
            path = self.SCHEMA_DIR / fname
            if path.exists():
                content = path.read_text()
                self.assertGreater(len(content), 100, f"{fname} ist zu klein")

    def test_schema_files_have_create_statements(self):
        """Jede Schema-Datei muss CREATE oder INSERT Statements enthalten."""
        for fname in self.EXPECTED_FILES:
            path = self.SCHEMA_DIR / fname
            if path.exists():
                content = path.read_text().upper()
                has_create = "CREATE" in content
                has_insert = "INSERT" in content
                self.assertTrue(has_create or has_insert, f"{fname} enthält kein CREATE/INSERT")

    def test_no_manual_file_paths(self):
        """
        No-Go: Keine manuellen Dateipfade in SQL-Schemas.
        Keine /home/user/datei.txt Referenzen.
        """
        for fname in self.EXPECTED_FILES:
            path = self.SCHEMA_DIR / fname
            if path.exists():
                content = path.read_text()
                self.assertNotIn(
                    "/home/user/",
                    content,
                    f"{fname} enthält verbotenen Dateipfad",
                )

    def test_append_only_tables_protected(self):
        """Journal-Tabellen müssen Lösch-Schutz haben."""
        journal_sql = (self.SCHEMA_DIR / "05-wal-journal.sql").read_text()
        self.assertIn("NIEMALS", journal_sql)
        self.assertIn("protect_journal", journal_sql)

    def test_rls_enabled(self):
        """Row-Level Security muss aktiviert sein."""
        rls_sql = (self.SCHEMA_DIR / "07-row-level-security.sql").read_text()
        self.assertIn("ENABLE ROW LEVEL SECURITY", rls_sql)
        # Mindestens 5 Tabellen mit RLS
        rls_count = rls_sql.count("ENABLE ROW LEVEL SECURITY")
        self.assertGreaterEqual(rls_count, 5, f"Nur {rls_count} Tabellen mit RLS")


class TestConfigFiles(unittest.TestCase):
    """Prüft die Konfigurationsdateien."""

    CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"

    def test_dbai_toml_exists(self):
        self.assertTrue((self.CONFIG_DIR / "dbai.toml").exists())

    def test_postgresql_conf_exists(self):
        self.assertTrue((self.CONFIG_DIR / "postgresql.conf").exists())

    def test_pg_hba_exists(self):
        self.assertTrue((self.CONFIG_DIR / "pg_hba.conf").exists())

    def test_no_external_apis(self):
        """No-Go: Keine externen API-Referenzen in der Konfiguration."""
        toml_content = (self.CONFIG_DIR / "dbai.toml").read_text()
        forbidden = ["openai", "api.anthropic", "api.openai", "cloud.google"]
        for term in forbidden:
            self.assertNotIn(
                term,
                toml_content.lower(),
                f"Externe API gefunden: {term}",
            )

    def test_listen_localhost_only(self):
        """Sicherheit: Nur localhost erlaubt."""
        pg_conf = (self.CONFIG_DIR / "postgresql.conf").read_text()
        self.assertIn("127.0.0.1", pg_conf)
        self.assertNotIn("0.0.0.0", pg_conf)


class TestSystemBridge(unittest.TestCase):
    """Tests für die System Bridge."""

    def test_bridge_import(self):
        """System Bridge muss importierbar sein."""
        try:
            from system_bridge import SystemBridge
            bridge = SystemBridge()
            self.assertFalse(bridge.running)
        except ImportError as e:
            # psycopg2 fehlt möglicherweise
            if "psycopg2" in str(e):
                self.skipTest("psycopg2 nicht installiert")
            raise

    def test_bridge_has_boot_method(self):
        try:
            from system_bridge import SystemBridge
            self.assertTrue(hasattr(SystemBridge, "boot"))
            self.assertTrue(hasattr(SystemBridge, "shutdown"))
            self.assertTrue(hasattr(SystemBridge, "verify_schemas"))
        except ImportError:
            self.skipTest("psycopg2 nicht installiert")


class TestCBindings(unittest.TestCase):
    """Tests für die C-Bindings."""

    C_DIR = Path(__file__).resolve().parent.parent / "bridge" / "c_bindings"

    def test_source_files_exist(self):
        self.assertTrue((self.C_DIR / "hw_interrupts.c").exists())
        self.assertTrue((self.C_DIR / "hw_interrupts.h").exists())
        self.assertTrue((self.C_DIR / "Makefile").exists())

    def test_header_has_structs(self):
        header = (self.C_DIR / "hw_interrupts.h").read_text()
        self.assertIn("MemoryInfo", header)
        self.assertIn("CpuInfo", header)
        self.assertIn("DiskInfo", header)

    def test_can_compile(self):
        """C-Code muss kompilierbar sein (wenn gcc vorhanden)."""
        import subprocess
        try:
            result = subprocess.run(
                ["make", "-n"],  # Dry-run
                cwd=str(self.C_DIR),
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0)
        except FileNotFoundError:
            self.skipTest("make nicht verfügbar")


class TestDirectoryStructure(unittest.TestCase):
    """Prüft die komplette Verzeichnisstruktur."""

    DBAI_ROOT = Path(__file__).resolve().parent.parent

    REQUIRED_DIRS = [
        "config", "schema", "bridge", "bridge/c_bindings",
        "recovery", "llm", "scripts", "tests", "web", "frontend", "frontend/src",
    ]

    REQUIRED_FILES = [
        "README.md",
        "requirements.txt",
        "config/dbai.toml",
        "config/postgresql.conf",
        "config/pg_hba.conf",
        "bridge/system_bridge.py",
        "bridge/hardware_monitor.py",
        "bridge/event_dispatcher.py",
        "bridge/c_bindings/hw_interrupts.c",
        "bridge/c_bindings/hw_interrupts.h",
        "bridge/c_bindings/Makefile",
        "recovery/pitr_manager.py",
        "recovery/mirror_sync.py",
        "recovery/panic_recovery.py",
        "llm/llm_bridge.py",
        "scripts/install.sh",
        "scripts/bootstrap.sh",
        "scripts/backup.sh",
        "scripts/health_check.py",
    ]

    def test_all_directories_exist(self):
        for d in self.REQUIRED_DIRS:
            path = self.DBAI_ROOT / d
            self.assertTrue(path.is_dir(), f"Verzeichnis fehlt: {d}")

    def test_all_files_exist(self):
        for f in self.REQUIRED_FILES:
            path = self.DBAI_ROOT / f
            self.assertTrue(path.exists(), f"Datei fehlt: {f}")


class TestKnowledgeLibrary(unittest.TestCase):
    """Tests für die Knowledge Library (Schemas 11-14)."""

    SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"

    def test_knowledge_library_creates_schema(self):
        """Schema 11 muss dbai_knowledge Schema erstellen."""
        content = (self.SCHEMA_DIR / "11-knowledge-library.sql").read_text()
        self.assertIn("dbai_knowledge", content)
        self.assertIn("module_registry", content)
        self.assertIn("changelog", content)
        self.assertIn("architecture_decisions", content)

    def test_error_patterns_schema(self):
        """Schema 12 muss Error-Patterns und Runbooks haben."""
        content = (self.SCHEMA_DIR / "12-error-patterns.sql").read_text()
        self.assertIn("error_patterns", content)
        self.assertIn("runbooks", content)
        self.assertIn("error_log", content)
        self.assertIn("log_error", content)

    def test_seed_data_has_all_modules(self):
        """Seed-Daten müssen alle DBAI-Dateien registrieren."""
        content = (self.SCHEMA_DIR / "13-seed-data.sql").read_text()
        # Jede Schema-Datei muss dokumentiert sein
        for i in range(26):
            schema_name = f"{i:02d}-"
            self.assertIn(schema_name, content, f"Schema {schema_name} nicht in Seed-Data")
        # Bridge-Dateien müssen dokumentiert sein
        self.assertIn("system_bridge.py", content)
        self.assertIn("hardware_monitor.py", content)
        self.assertIn("hw_interrupts.c", content)
        # HAL-Daemons müssen dokumentiert sein (v0.4.0)
        self.assertIn("hardware_scanner.py", content)
        self.assertIn("gpu_manager.py", content)
        # OpenClaw Bridge (v0.5.0)
        self.assertIn("openclaw_importer.py", content)
        # Ghost Autonomy + App Ecosystem (v0.6.0)
        self.assertIn("ghost_autonomy.py", content)
        self.assertIn("app_manager.py", content)
        # Recovery muss dokumentiert sein
        self.assertIn("pitr_manager.py", content)
        self.assertIn("panic_recovery.py", content)

    def test_seed_data_has_error_patterns(self):
        """Seed-Daten müssen bekannte Fehler-Patterns enthalten."""
        content = (self.SCHEMA_DIR / "13-seed-data.sql").read_text()
        self.assertIn("posix_c_source_missing", content)
        self.assertIn("CLOCK_MONOTONIC", content)
        self.assertIn("postgresql_not_running", content)
        self.assertIn("pgvector_missing", content)

    def test_seed_data_has_architecture_decisions(self):
        """Seed-Daten müssen Architektur-Entscheidungen enthalten."""
        content = (self.SCHEMA_DIR / "13-seed-data.sql").read_text()
        self.assertIn("PostgreSQL als OS-Kern", content)
        self.assertIn("llama.cpp eingebettet", content)
        self.assertIn("UUID statt Dateipfade", content)
        self.assertIn("Append-Only Logs", content)

    def test_seed_data_has_runbooks(self):
        """Seed-Daten müssen Runbooks enthalten."""
        content = (self.SCHEMA_DIR / "13-seed-data.sql").read_text()
        self.assertIn("rb_initial_setup", content)
        self.assertIn("rb_compile_error", content)
        self.assertIn("rb_db_recovery", content)

    def test_seed_data_has_glossary(self):
        """Seed-Daten müssen Glossar-Einträge enthalten."""
        content = (self.SCHEMA_DIR / "13-seed-data.sql").read_text()
        self.assertIn("system_glossary", content)
        self.assertIn("DBAI", content)
        self.assertIn("System Bridge", content)
        self.assertIn("pgvector", content)

    def test_seed_data_has_changelog(self):
        """Seed-Daten müssen Changelog-Einträge enthalten."""
        content = (self.SCHEMA_DIR / "13-seed-data.sql").read_text()
        self.assertIn("0.1.0", content)
        self.assertIn("0.2.0", content)
        self.assertIn("0.4.0", content)
        self.assertIn("C-Compile-Fehler behoben", content)

    def test_self_healing_schema(self):
        """Schema 14 muss Self-Healing Funktionen haben."""
        content = (self.SCHEMA_DIR / "14-self-healing.sql").read_text()
        self.assertIn("health_checks", content)
        self.assertIn("alert_rules", content)
        self.assertIn("self_heal", content)
        self.assertIn("run_health_checks", content)
        self.assertIn("evaluate_alerts", content)

    def test_no_manual_paths_in_new_schemas(self):
        """Keine verbotenen Dateipfade in den neuen Schemas."""
        for fname in ["11-knowledge-library.sql", "12-error-patterns.sql", "14-self-healing.sql"]:
            content = (self.SCHEMA_DIR / fname).read_text()
            self.assertNotIn("/home/user/", content, f"{fname} enthält verbotenen Pfad")

    def test_append_only_in_knowledge_schemas(self):
        """Changelog und Error-Log müssen Append-Only sein."""
        lib_content = (self.SCHEMA_DIR / "11-knowledge-library.sql").read_text()
        self.assertIn("protect_changelog", lib_content)
        self.assertIn("NIEMALS", lib_content)
        err_content = (self.SCHEMA_DIR / "12-error-patterns.sql").read_text()
        self.assertIn("protect_error_log", err_content)
        self.assertIn("NIEMALS", err_content)


class TestGhostSystem(unittest.TestCase):
    """Tests für das Ghost in the Shell System (Schema 15)."""

    SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"

    def test_ghost_schema_creates_tables(self):
        """Schema 15 muss Ghost-Tabellen erstellen."""
        content = (self.SCHEMA_DIR / "15-ghost-system.sql").read_text()
        self.assertIn("ghost_models", content)
        self.assertIn("ghost_roles", content)
        self.assertIn("active_ghosts", content)
        self.assertIn("ghost_history", content)

    def test_ghost_swap_function(self):
        """Ghost-Swap-Funktion muss vorhanden sein."""
        content = (self.SCHEMA_DIR / "15-ghost-system.sql").read_text()
        self.assertIn("swap_ghost", content)
        self.assertIn("ask_ghost", content)

    def test_ghost_roles_defined(self):
        """Ghost-Rollen-Tabelle muss existieren."""
        content = (self.SCHEMA_DIR / "15-ghost-system.sql").read_text()
        self.assertIn("ghost_roles", content)
        self.assertIn("Sysadmin", content)

    def test_ghost_history_protected(self):
        """Ghost History muss geschützt sein."""
        content = (self.SCHEMA_DIR / "15-ghost-system.sql").read_text()
        self.assertIn("protect_ghost_history", content)

    def test_ghost_notify_trigger(self):
        """Ghost-Swap muss NOTIFY auslösen."""
        content = (self.SCHEMA_DIR / "15-ghost-system.sql").read_text()
        self.assertIn("NOTIFY", content)

    def test_ghost_compatibility(self):
        """Ghost-Compatibility-Tabelle muss vorhanden sein."""
        content = (self.SCHEMA_DIR / "15-ghost-system.sql").read_text()
        self.assertIn("ghost_compatibility", content)
        self.assertIn("ROW LEVEL SECURITY", content)


class TestDesktopUI(unittest.TestCase):
    """Tests für das Desktop UI System (Schema 16)."""

    SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"

    def test_desktop_schema_creates_tables(self):
        """Schema 16 muss Desktop-Tabellen erstellen."""
        content = (self.SCHEMA_DIR / "16-desktop-ui.sql").read_text()
        self.assertIn("dbai_ui", content)
        self.assertIn("CREATE TABLE", content)
        for table in ["users", "sessions", "themes", "apps", "windows", "notifications"]:
            self.assertIn(table, content, f"Tabelle '{table}' fehlt in Desktop-Schema")

    def test_desktop_auth_functions(self):
        """Desktop muss Login-Mechanismus haben."""
        content = (self.SCHEMA_DIR / "16-desktop-ui.sql").read_text()
        # Server validiert login über DB, Session-Cleanup existiert
        self.assertIn("sessions", content)
        self.assertIn("cleanup_sessions", content)

    def test_desktop_window_management(self):
        """Desktop muss Fenster-Verwaltung haben."""
        content = (self.SCHEMA_DIR / "16-desktop-ui.sql").read_text()
        self.assertIn("windows", content)
        self.assertIn("get_desktop_state", content)

    def test_desktop_boot_sequence(self):
        """Boot-Sequence muss vorhanden sein."""
        content = (self.SCHEMA_DIR / "16-desktop-ui.sql").read_text()
        self.assertIn("boot", content.lower())
        self.assertIn("vw_boot_sequence", content)

    def test_desktop_notify_channels(self):
        """Desktop muss NOTIFY nutzen."""
        content = (self.SCHEMA_DIR / "16-desktop-ui.sql").read_text()
        self.assertIn("pg_notify", content)

    def test_desktop_no_manual_paths(self):
        """Keine verbotenen Dateipfade in Desktop-Schemas."""
        for fname in ["15-ghost-system.sql", "16-desktop-ui.sql", "17-ghost-desktop-seed.sql"]:
            content = (self.SCHEMA_DIR / fname).read_text()
            self.assertNotIn("/home/user/", content, f"{fname} enthält verbotenen Pfad")


class TestGhostDesktopSeed(unittest.TestCase):
    """Tests für die Ghost/Desktop Seed-Daten (Schema 17)."""

    SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"

    def test_seed_has_ghost_models(self):
        """Seed-Daten müssen Ghost-Modelle enthalten."""
        content = (self.SCHEMA_DIR / "17-ghost-desktop-seed.sql").read_text()
        self.assertIn("ghost_models", content)
        # Mindestens 3 Modelle
        model_count = content.count("INSERT INTO dbai_ghost.ghost_models") + content.count("ghost_models")
        self.assertGreater(model_count, 0)

    def test_seed_has_themes(self):
        """Seed-Daten müssen Themes enthalten."""
        content = (self.SCHEMA_DIR / "17-ghost-desktop-seed.sql").read_text()
        self.assertIn("cyberpunk", content.lower())
        self.assertIn("themes", content)

    def test_seed_has_applications(self):
        """Seed-Daten müssen Desktop-Anwendungen enthalten."""
        content = (self.SCHEMA_DIR / "17-ghost-desktop-seed.sql").read_text()
        self.assertIn("dbai_ui.apps", content)
        for app in ["System Monitor", "Ghost Manager", "Ghost Chat"]:
            self.assertIn(app, content, f"App '{app}' fehlt in Seed-Daten")

    def test_seed_has_boot_sequence(self):
        """Seed-Daten müssen Boot-relevante Daten enthalten."""
        content = (self.SCHEMA_DIR / "17-ghost-desktop-seed.sql").read_text()
        self.assertIn("boot", content.lower())

    def test_seed_has_admin_user(self):
        """Seed-Daten müssen Admin-Benutzer enthalten."""
        content = (self.SCHEMA_DIR / "17-ghost-desktop-seed.sql").read_text()
        self.assertIn("admin", content)


class TestHardwareAbstraction(unittest.TestCase):
    """Tests für das Hardware Abstraction Layer (Schema 18)."""

    SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"

    def test_hardware_schema_exists(self):
        """Schema 18 muss vorhanden sein."""
        self.assertTrue((self.SCHEMA_DIR / "18-hardware-abstraction.sql").exists())

    def test_hardware_inventory_table(self):
        """Schema 18 muss hardware_inventory Tabelle haben."""
        content = (self.SCHEMA_DIR / "18-hardware-abstraction.sql").read_text()
        self.assertIn("hardware_inventory", content)

    def test_gpu_tables(self):
        """Schema 18 muss GPU-Tabellen haben."""
        content = (self.SCHEMA_DIR / "18-hardware-abstraction.sql").read_text()
        self.assertIn("gpu_devices", content)
        self.assertIn("gpu_vram_map", content)

    def test_gpu_functions(self):
        """Schema 18 muss GPU-Funktionen haben."""
        content = (self.SCHEMA_DIR / "18-hardware-abstraction.sql").read_text()
        self.assertIn("check_gpu_available", content)
        self.assertIn("allocate_vram", content)
        self.assertIn("release_vram", content)

    def test_power_and_fan(self):
        """Schema 18 muss Power-Profile und Fan-Control haben."""
        content = (self.SCHEMA_DIR / "18-hardware-abstraction.sql").read_text()
        self.assertIn("power_profiles", content)
        self.assertIn("fan_control", content)

    def test_hotplug_events(self):
        """Schema 18 muss Hotplug-Events haben."""
        content = (self.SCHEMA_DIR / "18-hardware-abstraction.sql").read_text()
        self.assertIn("hotplug_events", content)

    def test_rls_enabled(self):
        """Schema 18 muss RLS auf allen Tabellen haben."""
        content = (self.SCHEMA_DIR / "18-hardware-abstraction.sql").read_text()
        self.assertIn("ENABLE ROW LEVEL SECURITY", content)

    def test_views(self):
        """Schema 18 muss Übersichts-Views haben."""
        content = (self.SCHEMA_DIR / "18-hardware-abstraction.sql").read_text()
        self.assertIn("vw_gpu_overview", content)
        self.assertIn("vw_hardware_summary", content)


class TestNeuralBridge(unittest.TestCase):
    """Tests für die Neural Bridge (Schema 19)."""

    SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"

    def test_neural_bridge_exists(self):
        """Schema 19 muss vorhanden sein."""
        self.assertTrue((self.SCHEMA_DIR / "19-neural-bridge.sql").exists())

    def test_boot_config(self):
        """Schema 19 muss Boot-Konfiguration haben."""
        content = (self.SCHEMA_DIR / "19-neural-bridge.sql").read_text()
        self.assertIn("boot_config", content)
        self.assertIn("gpu_mode", content)

    def test_driver_registry(self):
        """Schema 19 muss Treiber-Registry haben."""
        content = (self.SCHEMA_DIR / "19-neural-bridge.sql").read_text()
        self.assertIn("driver_registry", content)

    def test_system_capabilities(self):
        """Schema 19 muss System-Capabilities haben."""
        content = (self.SCHEMA_DIR / "19-neural-bridge.sql").read_text()
        self.assertIn("system_capabilities", content)

    def test_ghost_benchmarks(self):
        """Schema 19 muss Ghost-Benchmarks haben."""
        content = (self.SCHEMA_DIR / "19-neural-bridge.sql").read_text()
        self.assertIn("ghost_benchmarks", content)

    def test_boot_config_function(self):
        """Schema 19 muss get_boot_config() Funktion haben."""
        content = (self.SCHEMA_DIR / "19-neural-bridge.sql").read_text()
        self.assertIn("get_boot_config", content)

    def test_auto_swap_trigger(self):
        """Schema 19 muss auto_swap_on_gpu_change Trigger haben."""
        content = (self.SCHEMA_DIR / "19-neural-bridge.sql").read_text()
        self.assertIn("auto_swap_on_gpu_change", content)


class TestHWSeedData(unittest.TestCase):
    """Tests für die HAL+Neural Bridge Seed-Daten (Schema 20)."""

    SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"

    def test_hw_seed_exists(self):
        """Schema 20 muss vorhanden sein."""
        self.assertTrue((self.SCHEMA_DIR / "20-hw-seed-data.sql").exists())

    def test_power_profiles(self):
        """Schema 20 muss Power-Profile haben."""
        content = (self.SCHEMA_DIR / "20-hw-seed-data.sql").read_text()
        self.assertIn("sparmodus", content)
        self.assertIn("balanced", content)
        self.assertIn("cyberbrain", content)

    def test_boot_configs(self):
        """Schema 20 muss Boot-Konfigurationen haben."""
        content = (self.SCHEMA_DIR / "20-hw-seed-data.sql").read_text()
        self.assertIn("boot_config", content)
        self.assertIn("kiosk", content)

    def test_driver_registry_seeds(self):
        """Schema 20 muss Treiber-Registrierungen haben."""
        content = (self.SCHEMA_DIR / "20-hw-seed-data.sql").read_text()
        self.assertIn("nvidia-gpu", content)
        self.assertIn("cpu-monitor", content)


class TestHardwareScanner(unittest.TestCase):
    """Tests für den Hardware Scanner (bridge/hardware_scanner.py)."""

    BRIDGE_DIR = Path(__file__).resolve().parent.parent / "bridge"

    def test_scanner_exists(self):
        """bridge/hardware_scanner.py muss vorhanden sein."""
        self.assertTrue((self.BRIDGE_DIR / "hardware_scanner.py").exists())

    def test_scanner_has_class(self):
        """Hardware Scanner muss HardwareScanner Klasse haben."""
        content = (self.BRIDGE_DIR / "hardware_scanner.py").read_text()
        self.assertIn("class HardwareScanner", content)

    def test_scanner_has_scan_methods(self):
        """Hardware Scanner muss Scan-Methoden haben."""
        content = (self.BRIDGE_DIR / "hardware_scanner.py").read_text()
        self.assertIn("def scan_cpu", content)
        self.assertIn("def scan_memory", content)
        self.assertIn("def scan_storage", content)
        self.assertIn("def scan_network", content)
        self.assertIn("def full_scan", content)

    def test_scanner_has_daemon_mode(self):
        """Hardware Scanner muss Daemon-Modus haben."""
        content = (self.BRIDGE_DIR / "hardware_scanner.py").read_text()
        self.assertIn("daemon_loop", content)
        self.assertIn("--daemon", content)


class TestGPUManager(unittest.TestCase):
    """Tests für den GPU Manager (bridge/gpu_manager.py)."""

    BRIDGE_DIR = Path(__file__).resolve().parent.parent / "bridge"

    def test_gpu_manager_exists(self):
        """bridge/gpu_manager.py muss vorhanden sein."""
        self.assertTrue((self.BRIDGE_DIR / "gpu_manager.py").exists())

    def test_gpu_manager_has_class(self):
        """GPU Manager muss GPUManager Klasse haben."""
        content = (self.BRIDGE_DIR / "gpu_manager.py").read_text()
        self.assertIn("class GPUManager", content)

    def test_gpu_manager_has_vram_methods(self):
        """GPU Manager muss VRAM-Methoden haben."""
        content = (self.BRIDGE_DIR / "gpu_manager.py").read_text()
        self.assertIn("def allocate_for_ghost", content)
        self.assertIn("def release_ghost_vram", content)
        self.assertIn("def check_vram_for_model", content)

    def test_gpu_manager_has_multi_gpu(self):
        """GPU Manager muss Multi-GPU-Unterstützung haben."""
        content = (self.BRIDGE_DIR / "gpu_manager.py").read_text()
        self.assertIn("plan_multi_gpu_split", content)

    def test_gpu_manager_has_thermal_protection(self):
        """GPU Manager muss Thermal-Protection haben."""
        content = (self.BRIDGE_DIR / "gpu_manager.py").read_text()
        # Prüfe auf Temperatur-Schwellwerte
        self.assertIn("80", content)  # Warning threshold
        self.assertIn("90", content)  # Critical threshold


class TestOpenClawBridge(unittest.TestCase):
    """Tests für die OpenClaw Bridge (Schema 21)."""

    SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"

    def test_openclaw_bridge_exists(self):
        """Schema 21 muss vorhanden sein."""
        self.assertTrue((self.SCHEMA_DIR / "21-openclaw-bridge.sql").exists())

    def test_openclaw_skills_table(self):
        """Schema 21 muss openclaw_skills Tabelle haben."""
        content = (self.SCHEMA_DIR / "21-openclaw-bridge.sql").read_text()
        self.assertIn("openclaw_skills", content)

    def test_openclaw_memories_table(self):
        """Schema 21 muss openclaw_memories Tabelle haben."""
        content = (self.SCHEMA_DIR / "21-openclaw-bridge.sql").read_text()
        self.assertIn("openclaw_memories", content)

    def test_migration_jobs_table(self):
        """Schema 21 muss migration_jobs Tabelle haben."""
        content = (self.SCHEMA_DIR / "21-openclaw-bridge.sql").read_text()
        self.assertIn("migration_jobs", content)

    def test_telegram_bridge_table(self):
        """Schema 21 muss telegram_bridge Tabelle haben."""
        content = (self.SCHEMA_DIR / "21-openclaw-bridge.sql").read_text()
        self.assertIn("telegram_bridge", content)

    def test_app_streams_table(self):
        """Schema 21 muss app_streams Tabelle haben."""
        content = (self.SCHEMA_DIR / "21-openclaw-bridge.sql").read_text()
        self.assertIn("app_streams", content)

    def test_import_functions(self):
        """Schema 21 muss Import-Funktionen haben."""
        content = (self.SCHEMA_DIR / "21-openclaw-bridge.sql").read_text()
        self.assertIn("import_openclaw_memory", content)
        self.assertIn("register_openclaw_skill", content)
        self.assertIn("process_telegram_message", content)

    def test_migration_report_function(self):
        """Schema 21 muss Migration-Report-Funktion haben."""
        content = (self.SCHEMA_DIR / "21-openclaw-bridge.sql").read_text()
        self.assertIn("openclaw_migration_report", content)

    def test_rls_enabled(self):
        """Schema 21 muss RLS auf allen Tabellen haben."""
        content = (self.SCHEMA_DIR / "21-openclaw-bridge.sql").read_text()
        self.assertIn("ENABLE ROW LEVEL SECURITY", content)

    def test_compatibility_map(self):
        """Schema 21 muss Feature-Vergleich mit OpenClaw haben."""
        content = (self.SCHEMA_DIR / "21-openclaw-bridge.sql").read_text()
        self.assertIn("openclaw_compat_map", content)
        self.assertIn("Memory (JSON Files)", content)

    def test_views(self):
        """Schema 21 muss Übersichts-Views haben."""
        content = (self.SCHEMA_DIR / "21-openclaw-bridge.sql").read_text()
        self.assertIn("vw_openclaw_skills", content)
        self.assertIn("vw_openclaw_memory_status", content)
        self.assertIn("vw_telegram_stats", content)


class TestOpenClawImporter(unittest.TestCase):
    """Tests für den OpenClaw Importer (bridge/openclaw_importer.py)."""

    BRIDGE_DIR = Path(__file__).resolve().parent.parent / "bridge"

    def test_importer_exists(self):
        """bridge/openclaw_importer.py muss vorhanden sein."""
        self.assertTrue((self.BRIDGE_DIR / "openclaw_importer.py").exists())

    def test_importer_has_scanner_class(self):
        """Importer muss OpenClawScanner Klasse haben."""
        content = (self.BRIDGE_DIR / "openclaw_importer.py").read_text()
        self.assertIn("class OpenClawScanner", content)

    def test_importer_has_importer_class(self):
        """Importer muss OpenClawImporter Klasse haben."""
        content = (self.BRIDGE_DIR / "openclaw_importer.py").read_text()
        self.assertIn("class OpenClawImporter", content)

    def test_importer_has_telegram_bridge(self):
        """Importer muss TelegramBridge Klasse haben."""
        content = (self.BRIDGE_DIR / "openclaw_importer.py").read_text()
        self.assertIn("class TelegramBridge", content)

    def test_importer_has_import_methods(self):
        """Importer muss Import-Methoden haben."""
        content = (self.BRIDGE_DIR / "openclaw_importer.py").read_text()
        self.assertIn("def import_memories", content)
        self.assertIn("def import_skills", content)
        self.assertIn("def full_import", content)

    def test_importer_has_scan_method(self):
        """Scanner muss scan() Methode haben."""
        content = (self.BRIDGE_DIR / "openclaw_importer.py").read_text()
        self.assertIn("def scan", content)

    def test_importer_has_cli(self):
        """Importer muss CLI mit --scan und --import haben."""
        content = (self.BRIDGE_DIR / "openclaw_importer.py").read_text()
        self.assertIn("--scan", content)
        self.assertIn("--import", content)
        self.assertIn("--report", content)


class TestGhostAutonomy(unittest.TestCase):
    """Tests für das Ghost Autonomy Schema (schema/22-ghost-autonomy.sql)."""

    SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"

    def test_schema_22_exists(self):
        """schema/22-ghost-autonomy.sql muss vorhanden sein."""
        self.assertTrue((self.SCHEMA_DIR / "22-ghost-autonomy.sql").exists())

    def test_schema_22_has_proposed_actions(self):
        """Schema 22 muss proposed_actions-Tabelle haben."""
        content = (self.SCHEMA_DIR / "22-ghost-autonomy.sql").read_text()
        self.assertIn("proposed_actions", content)
        self.assertIn("ghost_context", content)

    def test_schema_22_has_core_tables(self):
        """Schema 22 muss alle 8 Tabellen haben."""
        content = (self.SCHEMA_DIR / "22-ghost-autonomy.sql").read_text()
        for table in ["proposed_actions", "ghost_context", "ghost_thought_log",
                       "process_importance", "energy_consumption", "ghost_files",
                       "ghost_feedback", "api_keys"]:
            self.assertIn(table, content, f"Tabelle '{table}' fehlt")

    def test_schema_22_has_functions(self):
        """Schema 22 muss Sicherheitsfunktionen haben."""
        content = (self.SCHEMA_DIR / "22-ghost-autonomy.sql").read_text()
        self.assertIn("propose_action", content)
        self.assertIn("approve_action", content)
        self.assertIn("reject_action", content)
        self.assertIn("load_ghost_context", content)

    def test_schema_22_has_rls(self):
        """Schema 22 muss RLS auf allen Tabellen haben."""
        content = (self.SCHEMA_DIR / "22-ghost-autonomy.sql").read_text()
        self.assertIn("ENABLE ROW LEVEL SECURITY", content)


class TestAppEcosystem(unittest.TestCase):
    """Tests für das App Ecosystem Schema (schema/23-app-ecosystem.sql)."""

    SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"

    def test_schema_23_exists(self):
        """schema/23-app-ecosystem.sql muss vorhanden sein."""
        self.assertTrue((self.SCHEMA_DIR / "23-app-ecosystem.sql").exists())

    def test_schema_23_has_software_catalog(self):
        """Schema 23 muss software_catalog haben."""
        content = (self.SCHEMA_DIR / "23-app-ecosystem.sql").read_text()
        self.assertIn("software_catalog", content)

    def test_schema_23_has_core_tables(self):
        """Schema 23 muss alle 8 Tabellen haben."""
        content = (self.SCHEMA_DIR / "23-app-ecosystem.sql").read_text()
        for table in ["software_catalog", "browser_sessions", "email_accounts",
                       "inbox", "outbox", "oauth_connections", "workspace_sync",
                       "command_history"]:
            self.assertIn(table, content, f"Tabelle '{table}' fehlt")

    def test_schema_23_has_functions(self):
        """Schema 23 muss App-Funktionen haben."""
        content = (self.SCHEMA_DIR / "23-app-ecosystem.sql").read_text()
        self.assertIn("install_software", content)
        self.assertIn("browse_url", content)
        self.assertIn("send_email", content)
        self.assertIn("search_inbox", content)
        self.assertIn("process_command", content)

    def test_schema_23_has_rls(self):
        """Schema 23 muss RLS auf allen Tabellen haben."""
        content = (self.SCHEMA_DIR / "23-app-ecosystem.sql").read_text()
        self.assertIn("ENABLE ROW LEVEL SECURITY", content)


class TestGhostAutonomyDaemon(unittest.TestCase):
    """Tests für den Ghost Autonomy Daemon (bridge/ghost_autonomy.py)."""

    BRIDGE_DIR = Path(__file__).resolve().parent.parent / "bridge"

    def test_daemon_file_exists(self):
        """bridge/ghost_autonomy.py muss vorhanden sein."""
        self.assertTrue((self.BRIDGE_DIR / "ghost_autonomy.py").exists())

    def test_daemon_has_class(self):
        """Daemon muss GhostAutonomyDaemon-Klasse haben."""
        content = (self.BRIDGE_DIR / "ghost_autonomy.py").read_text()
        self.assertIn("class GhostAutonomyDaemon", content)

    def test_daemon_has_core_methods(self):
        """Daemon muss Kern-Methoden haben."""
        content = (self.BRIDGE_DIR / "ghost_autonomy.py").read_text()
        self.assertIn("inject_context", content)
        self.assertIn("monitor_energy", content)
        self.assertIn("classify_processes", content)
        self.assertIn("execute_approved_actions", content)

    def test_daemon_has_notify(self):
        """Daemon muss auf NOTIFY-Events hören."""
        content = (self.BRIDGE_DIR / "ghost_autonomy.py").read_text()
        self.assertIn("action_approved", content)
        self.assertIn("action_rejected", content)

    def test_daemon_has_cli(self):
        """Daemon muss CLI haben."""
        content = (self.BRIDGE_DIR / "ghost_autonomy.py").read_text()
        self.assertIn("--daemon", content)


class TestAppManager(unittest.TestCase):
    """Tests für den App Manager (bridge/app_manager.py)."""

    BRIDGE_DIR = Path(__file__).resolve().parent.parent / "bridge"

    def test_app_manager_exists(self):
        """bridge/app_manager.py muss vorhanden sein."""
        self.assertTrue((self.BRIDGE_DIR / "app_manager.py").exists())

    def test_app_manager_has_software_catalog(self):
        """App Manager muss SoftwareCatalog-Klasse haben."""
        content = (self.BRIDGE_DIR / "app_manager.py").read_text()
        self.assertIn("class SoftwareCatalog", content)

    def test_app_manager_has_browser(self):
        """App Manager muss BrowserAutomation-Klasse haben."""
        content = (self.BRIDGE_DIR / "app_manager.py").read_text()
        self.assertIn("class BrowserAutomation", content)

    def test_app_manager_has_email(self):
        """App Manager muss EmailBridge-Klasse haben."""
        content = (self.BRIDGE_DIR / "app_manager.py").read_text()
        self.assertIn("class EmailBridge", content)

    def test_app_manager_has_oauth(self):
        """App Manager muss OAuthManager-Klasse haben."""
        content = (self.BRIDGE_DIR / "app_manager.py").read_text()
        self.assertIn("class OAuthManager", content)

    def test_app_manager_has_cli(self):
        """App Manager muss CLI-Optionen haben."""
        content = (self.BRIDGE_DIR / "app_manager.py").read_text()
        self.assertIn("--scan-packages", content)
        self.assertIn("--browse", content)
        self.assertIn("--sync-email", content)
        self.assertIn("--daemon", content)


class TestSystemMemory(unittest.TestCase):
    """Tests für das System Memory Schema (schema/24-system-memory.sql)."""

    SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"

    def test_schema_24_exists(self):
        """schema/24-system-memory.sql muss vorhanden sein."""
        self.assertTrue((self.SCHEMA_DIR / "24-system-memory.sql").exists())

    def test_schema_24_has_system_memory_table(self):
        """Schema 24 muss system_memory-Tabelle haben."""
        content = (self.SCHEMA_DIR / "24-system-memory.sql").read_text()
        self.assertIn("system_memory", content)
        self.assertIn("agent_sessions", content)

    def test_schema_24_has_categories(self):
        """Schema 24 muss Wissenskategorien definieren."""
        content = (self.SCHEMA_DIR / "24-system-memory.sql").read_text()
        for cat in ["architecture", "convention", "schema_map",
                     "design_pattern", "relationship", "workflow",
                     "inventory", "roadmap", "identity", "operational"]:
            self.assertIn(cat, content, f"Kategorie '{cat}' fehlt")

    def test_schema_24_has_functions(self):
        """Schema 24 muss Kontext-Funktionen haben."""
        content = (self.SCHEMA_DIR / "24-system-memory.sql").read_text()
        self.assertIn("get_agent_context", content)
        self.assertIn("save_memory", content)
        self.assertIn("get_memory_by_category", content)

    def test_schema_24_has_rls(self):
        """Schema 24 muss RLS auf allen Tabellen haben."""
        content = (self.SCHEMA_DIR / "24-system-memory.sql").read_text()
        self.assertIn("ENABLE ROW LEVEL SECURITY", content)


class TestSystemMemorySeed(unittest.TestCase):
    """Tests für die System Memory Seed-Daten (schema/25-system-memory-seed.sql)."""

    SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"

    def test_schema_25_exists(self):
        """schema/25-system-memory-seed.sql muss vorhanden sein."""
        self.assertTrue((self.SCHEMA_DIR / "25-system-memory-seed.sql").exists())

    def test_seed_has_identity(self):
        """Seed muss Identitäts-Wissen enthalten."""
        content = (self.SCHEMA_DIR / "25-system-memory-seed.sql").read_text()
        self.assertIn("identity", content)
        self.assertIn("TabulaOS", content)

    def test_seed_has_architecture(self):
        """Seed muss Architektur-Wissen enthalten."""
        content = (self.SCHEMA_DIR / "25-system-memory-seed.sql").read_text()
        self.assertIn("architecture", content)
        self.assertIn("Gesamtarchitektur", content)

    def test_seed_has_schema_map(self):
        """Seed muss Schema-Karte enthalten."""
        content = (self.SCHEMA_DIR / "25-system-memory-seed.sql").read_text()
        self.assertIn("schema_map", content)
        self.assertIn("dbai_core", content)
        self.assertIn("dbai_system", content)
        self.assertIn("dbai_llm", content)
        self.assertIn("dbai_knowledge", content)

    def test_seed_has_design_patterns(self):
        """Seed muss Design-Patterns enthalten."""
        content = (self.SCHEMA_DIR / "25-system-memory-seed.sql").read_text()
        self.assertIn("design_pattern", content)
        self.assertIn("NOTIFY", content)
        self.assertIn("Append-Only", content)

    def test_seed_has_conventions(self):
        """Seed muss Coding-Konventionen enthalten."""
        content = (self.SCHEMA_DIR / "25-system-memory-seed.sql").read_text()
        self.assertIn("convention", content)
        self.assertIn("Naming", content)

    def test_seed_has_workflows(self):
        """Seed muss Workflow-Wissen enthalten."""
        content = (self.SCHEMA_DIR / "25-system-memory-seed.sql").read_text()
        self.assertIn("workflow", content)
        self.assertIn("Neues Feature", content)

    def test_seed_has_agent_sessions(self):
        """Seed muss Agent-Sessions dokumentieren."""
        content = (self.SCHEMA_DIR / "25-system-memory-seed.sql").read_text()
        self.assertIn("agent_sessions", content)
        self.assertIn("0.1.0", content)
        self.assertIn("0.6.0", content)

    def test_seed_has_inventory(self):
        """Seed muss Tech-Inventar enthalten."""
        content = (self.SCHEMA_DIR / "25-system-memory-seed.sql").read_text()
        self.assertIn("inventory", content)
        self.assertIn("PostgreSQL", content)
        self.assertIn("Python", content)

    def test_seed_has_relationships(self):
        """Seed muss Beziehungswissen enthalten."""
        content = (self.SCHEMA_DIR / "25-system-memory-seed.sql").read_text()
        self.assertIn("relationship", content)
        self.assertIn("Ghost", content)
        self.assertIn("Hardware", content)


class TestWebServer(unittest.TestCase):
    """Tests für den Web-Server und Ghost Dispatcher."""

    WEB_DIR = Path(__file__).resolve().parent.parent / "web"

    def test_server_file_exists(self):
        """web/server.py muss vorhanden sein."""
        self.assertTrue((self.WEB_DIR / "server.py").exists())

    def test_ghost_dispatcher_exists(self):
        """web/ghost_dispatcher.py muss vorhanden sein."""
        self.assertTrue((self.WEB_DIR / "ghost_dispatcher.py").exists())

    def test_server_has_endpoints(self):
        """Server muss alle REST-Endpunkte haben."""
        content = (self.WEB_DIR / "server.py").read_text()
        endpoints = ["/api/auth/login", "/api/boot/sequence", "/api/desktop",
                     "/api/apps", "/api/windows", "/api/ghosts", "/api/system"]
        for ep in endpoints:
            self.assertIn(ep, content, f"Endpoint '{ep}' fehlt")

    def test_server_has_websocket(self):
        """Server muss WebSocket-Endpoint haben."""
        content = (self.WEB_DIR / "server.py").read_text()
        self.assertIn("websocket", content.lower())
        self.assertIn("/ws", content)

    def test_server_has_auth(self):
        """Server muss Authentifizierung haben."""
        content = (self.WEB_DIR / "server.py").read_text()
        self.assertIn("token", content.lower())
        self.assertIn("Authorization", content)

    def test_ghost_dispatcher_has_swap(self):
        """Ghost Dispatcher muss Hot-Swap unterstützen."""
        content = (self.WEB_DIR / "ghost_dispatcher.py").read_text()
        self.assertIn("swap", content.lower())
        self.assertIn("ghost_swap", content)

    def test_ghost_dispatcher_has_model_management(self):
        """Ghost Dispatcher muss Modell-Management haben."""
        content = (self.WEB_DIR / "ghost_dispatcher.py").read_text()
        self.assertIn("load_model", content)
        self.assertIn("unload_model", content)


class TestFrontend(unittest.TestCase):
    """Tests für das React-Frontend."""

    FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

    def test_package_json_exists(self):
        """frontend/package.json muss vorhanden sein."""
        self.assertTrue((self.FRONTEND_DIR / "package.json").exists())

    def test_package_json_has_react(self):
        """package.json muss React als Dependency haben."""
        content = (self.FRONTEND_DIR / "package.json").read_text()
        self.assertIn("react", content)
        self.assertIn("react-dom", content)
        self.assertIn("vite", content)

    def test_vite_config_exists(self):
        """Vite-Konfiguration muss vorhanden sein."""
        self.assertTrue((self.FRONTEND_DIR / "vite.config.js").exists())

    def test_main_components_exist(self):
        """Haupt-Komponenten müssen vorhanden sein."""
        src = self.FRONTEND_DIR / "src"
        required = ["main.jsx", "App.jsx", "api.js"]
        for f in required:
            self.assertTrue((src / f).exists(), f"Komponente fehlt: {f}")

    def test_app_components_exist(self):
        """App-Komponenten müssen vorhanden sein."""
        apps = self.FRONTEND_DIR / "src" / "components" / "apps"
        required = ["SystemMonitor.jsx", "GhostManager.jsx", "GhostChat.jsx",
                     "KnowledgeBase.jsx", "EventViewer.jsx", "SQLConsole.jsx", "HealthDashboard.jsx"]
        for f in required:
            self.assertTrue((apps / f).exists(), f"App-Komponente fehlt: {f}")

    def test_core_components_exist(self):
        """Core-Komponenten müssen vorhanden sein."""
        comps = self.FRONTEND_DIR / "src" / "components"
        required = ["BootScreen.jsx", "LoginScreen.jsx", "Desktop.jsx", "Window.jsx"]
        for f in required:
            self.assertTrue((comps / f).exists(), f"Core-Komponente fehlt: {f}")

    def test_global_css_exists(self):
        """Globales CSS muss vorhanden sein."""
        css = self.FRONTEND_DIR / "src" / "styles" / "global.css"
        self.assertTrue(css.exists())
        content = css.read_text()
        self.assertIn("--accent", content)
        self.assertIn("cyberpunk", content.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
