#!/usr/bin/env python3
"""
DBAI Tests — App-Settings-System
Testet das JSON-Schema-basierte Settings-System (v0.9.0+).
"""

import os
import sys
import unittest
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestSettingsSchemaFiles(unittest.TestCase):
    """Prüft ob Schema-Dateien für Settings vorhanden sind."""

    SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"

    def test_settings_schema_exists(self):
        f = self.SCHEMA_DIR / "39-app-settings.sql"
        self.assertTrue(f.exists(), "39-app-settings.sql fehlt")

    def test_settings_seed_exists(self):
        f = self.SCHEMA_DIR / "40-app-settings-seed.sql"
        self.assertTrue(f.exists(), "40-app-settings-seed.sql fehlt")

    def test_remaining_settings_seed_exists(self):
        f = self.SCHEMA_DIR / "42-remaining-app-settings-seed.sql"
        self.assertTrue(f.exists(), "42-remaining-app-settings-seed.sql fehlt")

    def test_missing_apps_registration_exists(self):
        f = self.SCHEMA_DIR / "44-register-missing-apps.sql"
        self.assertTrue(f.exists(), "44-register-missing-apps.sql fehlt")


class TestSettingsFrontendHook(unittest.TestCase):
    """Prüft ob der useAppSettings-Hook korrekt implementiert ist."""

    HOOK_FILE = Path(__file__).resolve().parent.parent / "frontend" / "src" / "hooks" / "useAppSettings.js"

    def test_hook_exists(self):
        self.assertTrue(self.HOOK_FILE.exists(), "useAppSettings.js fehlt")

    def test_hook_exports(self):
        content = self.HOOK_FILE.read_text()
        self.assertIn('useAppSettings', content, "useAppSettings nicht exportiert")
        self.assertIn('api.appSettings', content, "appSettings-Aufruf fehlt")


class TestSettingsPanelComponent(unittest.TestCase):
    """Prüft ob die AppSettingsPanel-Komponente existiert."""

    PANEL_FILE = Path(__file__).resolve().parent.parent / "frontend" / "src" / "components" / "AppSettingsPanel.jsx"

    def test_panel_exists(self):
        self.assertTrue(self.PANEL_FILE.exists(), "AppSettingsPanel.jsx fehlt")

    def test_panel_props(self):
        content = self.PANEL_FILE.read_text()
        for prop in ['schema', 'settings', 'onUpdate', 'onReset']:
            self.assertIn(prop, content, f"Prop '{prop}' fehlt in AppSettingsPanel")


class TestAllAppsHaveSettings(unittest.TestCase):
    """Prüft ob alle App-Komponenten useAppSettings verwenden."""

    APPS_DIR = Path(__file__).resolve().parent.parent / "frontend" / "src" / "components" / "apps"

    # Apps die KEINE Settings brauchen (System-Komponenten)
    EXEMPT_APPS = {'Settings', 'SetupWizard'}

    def test_all_apps_import_settings(self):
        """Alle nicht-exemptionellen Apps müssen useAppSettings importieren."""
        import re
        missing = []
        for f in self.APPS_DIR.glob("*.jsx"):
            name = f.stem
            if name in self.EXEMPT_APPS:
                continue
            content = f.read_text()
            if 'useAppSettings' not in content:
                missing.append(name)
        self.assertEqual(len(missing), 0,
                         f"Apps ohne useAppSettings: {missing}")

    def test_no_schema_duplicate_bug(self):
        """Kein App darf 'schema' doppelt deklarieren (FileBrowser-Bug-Pattern)."""
        import re
        problematic = []
        for f in self.APPS_DIR.glob("*.jsx"):
            content = f.read_text()
            if 'useAppSettings' not in content:
                continue
            # Prüfe ob schema aus useAppSettings UND als useState existiert
            has_settings_schema = bool(re.search(r'schema\s*[,}]', content)) or bool(re.search(r'schema:', content))
            has_state_schema = bool(re.search(r"const\s+\[\s*schema\s*,\s*set", content))
            if has_settings_schema and has_state_schema and 'settingsSchema' not in content:
                problematic.append(f.stem)
        self.assertEqual(len(problematic), 0,
                         f"Apps mit schema-Duplikat-Bug: {problematic}")

    def test_settings_panel_in_apps(self):
        """Apps mit useAppSettings sollten auch AppSettingsPanel verwenden."""
        missing_panel = []
        for f in self.APPS_DIR.glob("*.jsx"):
            content = f.read_text()
            if 'useAppSettings' in content and 'AppSettingsPanel' not in content:
                missing_panel.append(f.stem)
        self.assertEqual(len(missing_panel), 0,
                         f"Apps mit useAppSettings aber ohne AppSettingsPanel: {missing_panel}")


class TestSettingsAPIEndpoints(unittest.TestCase):
    """Prüft ob Settings-API-Endpunkte in server.py existieren."""

    def test_settings_endpoints_exist(self):
        content = (Path(__file__).resolve().parent.parent / "web" / "server.py").read_text()
        endpoints = [
            '/api/apps/{app_id}/settings',
            '/api/apps/{app_id}/settings/schema',
            '/api/apps/settings/all',
        ]
        for ep in endpoints:
            self.assertIn(ep, content, f"Settings-Endpunkt fehlt: {ep}")

    def test_settings_api_methods(self):
        content = (Path(__file__).resolve().parent.parent / "frontend" / "src" / "api.js").read_text()
        methods = ['appSettings', 'appSettingsUpdate', 'appSettingsReset', 'appSettingsSchema', 'allAppSettings']
        for m in methods:
            self.assertIn(m, content, f"Settings-API-Methode fehlt: {m}")


if __name__ == '__main__':
    unittest.main()
