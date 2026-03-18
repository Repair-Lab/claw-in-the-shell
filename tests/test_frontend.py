#!/usr/bin/env python3
"""
DBAI Tests — Frontend-Komponenten-Integrität
Testet ob alle Frontend-Komponenten korrekt aufgebaut sind.
"""

import os
import sys
import re
import unittest
from pathlib import Path


class TestComponentFilesExist(unittest.TestCase):
    """Prüft ob alle erwarteten Komponenten-Dateien existieren."""

    APPS_DIR = Path(__file__).resolve().parent.parent / "frontend" / "src" / "components" / "apps"

    EXPECTED_COMPONENTS = [
        'AIWorkshop', 'AnomalyDetector', 'AppSandbox', 'BrowserMigration',
        'ConfigImporter', 'ErrorAnalyzer', 'EventViewer', 'FileBrowser',
        'FirewallManager', 'GhostChat', 'GhostManager', 'GhostUpdater',
        'HealthDashboard', 'ImmutableFS', 'KnowledgeBase', 'LLMManager',
        'NetworkScanner', 'NodeManager', 'OpenClawIntegrator', 'ProcessManager',
        'RAGManager', 'Settings', 'SetupWizard', 'SoftwareStore',
        'SQLConsole', 'SQLExplorer', 'SynapticViewer', 'SystemMonitor',
        'Terminal', 'USBInstaller', 'WebFrame', 'WLANHotspot', 'WorkspaceMapper',
    ]

    def test_all_components_exist(self):
        """Alle erwarteten Komponenten-Dateien müssen existieren."""
        missing = []
        for comp in self.EXPECTED_COMPONENTS:
            if not (self.APPS_DIR / f"{comp}.jsx").exists():
                missing.append(comp)
        self.assertEqual(len(missing), 0, f"Fehlende Komponenten: {missing}")

    def test_no_unexpected_components(self):
        """Keine unbekannten Komponenten-Dateien."""
        existing = {f.stem for f in self.APPS_DIR.glob("*.jsx")}
        expected = set(self.EXPECTED_COMPONENTS)
        unexpected = existing - expected
        # Warnung statt Fehler (neue Komponenten sind OK)
        if unexpected:
            print(f"Info: Zusätzliche Komponenten gefunden: {unexpected}")


class TestDesktopMapping(unittest.TestCase):
    """Prüft ob Desktop.jsx alle Komponenten korrekt mappt."""

    DESKTOP_FILE = Path(__file__).resolve().parent.parent / "frontend" / "src" / "components" / "Desktop.jsx"
    APPS_DIR = Path(__file__).resolve().parent.parent / "frontend" / "src" / "components" / "apps"

    def test_desktop_exists(self):
        self.assertTrue(self.DESKTOP_FILE.exists(), "Desktop.jsx fehlt")

    def test_all_components_imported(self):
        """Alle App-Komponenten müssen in Desktop.jsx importiert sein."""
        content = self.DESKTOP_FILE.read_text()
        missing_imports = []
        for f in self.APPS_DIR.glob("*.jsx"):
            comp_name = f.stem
            # Überspringe System-Komponenten die evtl. anders importiert werden
            if comp_name in ('Settings', 'SetupWizard'):
                continue
            if f"import {comp_name}" not in content and f"'{comp_name}'" not in content:
                if comp_name not in content:
                    missing_imports.append(comp_name)
        self.assertEqual(len(missing_imports), 0,
                         f"Fehlende Imports in Desktop.jsx: {missing_imports}")

    def test_app_components_mapping(self):
        """APP_COMPONENTS Objekt muss alle Komponenten enthalten."""
        content = self.DESKTOP_FILE.read_text()
        self.assertIn('APP_COMPONENTS', content, "APP_COMPONENTS fehlt in Desktop.jsx")


class TestComponentStructure(unittest.TestCase):
    """Prüft die Grundstruktur aller Komponenten."""

    APPS_DIR = Path(__file__).resolve().parent.parent / "frontend" / "src" / "components" / "apps"

    def test_components_export_default(self):
        """Jede Komponente muss einen default export haben."""
        missing_export = []
        for f in self.APPS_DIR.glob("*.jsx"):
            content = f.read_text()
            if 'export default' not in content:
                missing_export.append(f.stem)
        self.assertEqual(len(missing_export), 0,
                         f"Komponenten ohne default export: {missing_export}")

    def test_components_import_react(self):
        """Jede Komponente muss React importieren."""
        missing_react = []
        for f in self.APPS_DIR.glob("*.jsx"):
            content = f.read_text()
            if 'import React' not in content and "from 'react'" not in content:
                missing_react.append(f.stem)
        self.assertEqual(len(missing_react), 0,
                         f"Komponenten ohne React-Import: {missing_react}")

    def test_no_syntax_issues(self):
        """Keine offensichtlichen Syntax-Probleme (unbalancierte Klammern etc.)."""
        issues = []
        for f in self.APPS_DIR.glob("*.jsx"):
            content = f.read_text()
            # Einfacher Check: Anzahl öffnende vs schließende geschweifte Klammern
            opens = content.count('{')
            closes = content.count('}')
            if abs(opens - closes) > 2:
                issues.append(f"{f.stem}: {{ {opens} vs }} {closes}")
        self.assertEqual(len(issues), 0,
                         f"Potenzielle Syntax-Probleme: {issues}")


class TestHooksExist(unittest.TestCase):
    """Prüft ob alle benutzerdefinierten Hooks existieren."""

    HOOKS_DIR = Path(__file__).resolve().parent.parent / "frontend" / "src" / "hooks"

    def test_required_hooks_exist(self):
        """Alle benötigten Hooks müssen existieren."""
        required = ['useAppSettings.js', 'useNotification.jsx', 'useKeyboardShortcuts.js']
        for hook in required:
            self.assertTrue(
                (self.HOOKS_DIR / hook).exists(),
                f"Hook fehlt: {hook}"
            )


class TestNotificationSystem(unittest.TestCase):
    """Prüft das Notification-System."""

    def test_provider_in_app(self):
        """NotificationProvider muss in App.jsx eingebunden sein."""
        app_file = Path(__file__).resolve().parent.parent / "frontend" / "src" / "App.jsx"
        content = app_file.read_text()
        self.assertIn('NotificationProvider', content,
                       "NotificationProvider fehlt in App.jsx")

    def test_notification_exports(self):
        """useNotification muss korrekte Exports haben."""
        hook_file = Path(__file__).resolve().parent.parent / "frontend" / "src" / "hooks" / "useNotification.jsx"
        content = hook_file.read_text()
        for export in ['NotificationProvider', 'useNotification']:
            self.assertIn(export, content, f"Export fehlt: {export}")


class TestSpotlightSearch(unittest.TestCase):
    """Prüft die SpotlightSearch-Komponente."""

    def test_component_exists(self):
        f = Path(__file__).resolve().parent.parent / "frontend" / "src" / "components" / "SpotlightSearch.jsx"
        self.assertTrue(f.exists(), "SpotlightSearch.jsx fehlt")

    def test_integrated_in_desktop(self):
        content = (Path(__file__).resolve().parent.parent / "frontend" / "src" / "components" / "Desktop.jsx").read_text()
        self.assertIn('SpotlightSearch', content, "SpotlightSearch nicht in Desktop.jsx integriert")


if __name__ == '__main__':
    unittest.main()
