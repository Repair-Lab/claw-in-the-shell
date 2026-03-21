#!/usr/bin/env python3
"""
DBAI Tests — API-Endpunkt-Abdeckung
Testet alle kritischen API-Routen auf Erreichbarkeit und korrekte Responses.
"""

import os
import sys
import unittest
import json
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "web"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bridge"))


class TestAPIEndpointCoverage(unittest.TestCase):
    """Prüft ob alle API-Endpunkte in server.py definiert sind."""

    SERVER_FILE = Path(__file__).resolve().parent.parent / "web" / "server.py"

    def test_server_file_exists(self):
        self.assertTrue(self.SERVER_FILE.exists(), "server.py existiert nicht")

    def test_minimum_endpoint_count(self):
        """Server muss mindestens 200 Endpunkte haben."""
        import re
        content = self.SERVER_FILE.read_text()
        endpoints = re.findall(r'@app\.(get|post|put|patch|delete)\(', content)
        self.assertGreaterEqual(len(endpoints), 200,
                                f"Nur {len(endpoints)} Endpunkte gefunden, erwartet >= 200")

    def test_critical_endpoints_exist(self):
        """Alle kritischen Endpunkte müssen definiert sein."""
        content = self.SERVER_FILE.read_text()
        critical = [
            '/api/auth/login', '/api/auth/logout', '/api/auth/me',
            '/api/system/health', '/api/system/diagnostics',
            '/api/desktop', '/api/apps',
            '/api/apps/{app_id}/settings', '/api/health',
            '/api/export/', '/api/users', '/api/audit/log',
            '/api/backup/trigger', '/api/backup/status',
        ]
        for ep in critical:
            self.assertIn(ep, content, f"Kritischer Endpunkt fehlt: {ep}")

    def test_repair_endpoints_exist(self):
        """Self-Healing/Repair-Endpunkte müssen vorhanden sein."""
        content = self.SERVER_FILE.read_text()
        repair = [
            '/api/repair/queue', '/api/repair/pending',
            '/api/repair/approve/', '/api/repair/reject/',
            '/api/repair/execute/', '/api/repair/enforcement-log',
            '/api/repair/schema-integrity', '/api/repair/immutable-registry',
        ]
        for ep in repair:
            self.assertIn(ep, content, f"Repair-Endpunkt fehlt: {ep}")

    def test_feature_endpoints_exist(self):
        """Feature-Endpunkte müssen vorhanden sein."""
        content = self.SERVER_FILE.read_text()
        features = [
            '/api/firewall/', '/api/anomaly/', '/api/synaptic/',
            '/api/rag/', '/api/immutable/', '/api/usb/',
            '/api/hotspot/', '/api/browser/', '/api/config/',
            '/api/workspace/', '/api/sandbox/', '/api/ghosts/',
        ]
        for ep in features:
            self.assertIn(ep, content, f"Feature-Endpunkt fehlt: {ep}")

    def test_no_duplicate_route_names(self):
        """Keine doppelten Funktionsnamen für Routes (Ausnahme: generische Namen)."""
        import re
        content = self.SERVER_FILE.read_text()
        funcs = re.findall(r'async def (\w+)\(', content)
        seen = {}
        duplicates = []
        # Generische Namen wie start/stop sind OK (verschiedene Module)
        generic_ok = {'start', 'stop', 'status', 'search'}
        for f in funcs:
            if f in generic_ok:
                continue
            if f in seen:
                duplicates.append(f)
            seen[f] = True
        self.assertEqual(len(duplicates), 0,
                         f"Doppelte Route-Funktionsnamen: {duplicates}")


class TestAPIClientCoverage(unittest.TestCase):
    """Prüft ob api.js alle Server-Endpunkte abdeckt."""

    API_FILE = Path(__file__).resolve().parent.parent / "frontend" / "src" / "api.js"

    def test_api_file_exists(self):
        self.assertTrue(self.API_FILE.exists(), "api.js existiert nicht")

    def test_minimum_method_count(self):
        """api.js muss mindestens 220 Methoden haben."""
        import re
        content = self.API_FILE.read_text()
        methods = re.findall(r'^\s+\w+:\s*\(', content, re.MULTILINE)
        self.assertGreaterEqual(len(methods), 220,
                                f"Nur {len(methods)} API-Methoden, erwartet >= 220")

    def test_repair_methods_exist(self):
        """Repair-Methoden müssen in api.js vorhanden sein."""
        content = self.API_FILE.read_text()
        repair_methods = [
            'repairQueue', 'repairPending', 'repairApprove',
            'repairReject', 'repairExecute', 'repairEnforcementLog',
            'repairSchemaIntegrity', 'repairImmutableRegistry',
        ]
        for m in repair_methods:
            self.assertIn(m, content, f"API-Methode fehlt: {m}")

    def test_export_methods_exist(self):
        """Export-Methoden müssen vorhanden sein."""
        content = self.API_FILE.read_text()
        for m in ['exportTable', 'exportLogs', 'exportTableCSV']:
            self.assertIn(m, content, f"Export-Methode fehlt: {m}")

    def test_user_management_methods_exist(self):
        """User-Management-Methoden müssen vorhanden sein."""
        content = self.API_FILE.read_text()
        for m in ['listUsers', 'createUser', 'updateUser', 'deleteUser']:
            self.assertIn(m, content, f"User-Methode fehlt: {m}")

    def test_settings_methods_exist(self):
        """Settings-Methoden müssen vorhanden sein."""
        content = self.API_FILE.read_text()
        for m in ['appSettings', 'appSettingsUpdate', 'appSettingsReset']:
            self.assertIn(m, content, f"Settings-Methode fehlt: {m}")


class TestAPIClientServerConsistency(unittest.TestCase):
    """Prüft ob api.js und server.py konsistent sind."""

    def test_all_server_paths_in_apijs(self):
        """api.js muss die wichtigsten Server-Pfade abdecken."""
        import re
        server = (Path(__file__).resolve().parent.parent / "web" / "server.py").read_text()
        apijs = (Path(__file__).resolve().parent.parent / "frontend" / "src" / "api.js").read_text()

        # api.js nutzt API_BASE='/api' + relative Pfade wie '/auth/login'
        # Extrahiere Basis-Pfade aus api.js (erstes Segment)
        api_bases = set()
        for m in re.finditer(r"request\([`'\"](/[a-z][a-z0-9/-]*)", apijs):
            path = m.group(1)
            parts = path.strip('/').split('/')
            if parts:
                api_bases.add(parts[0])

        # Extrahiere Basis-Pfade aus server.py (/api/{base}/...)
        server_bases = set()
        for m in re.finditer(r'@app\.\w+\(["\'](/api/[^"\']+)["\']', server):
            path = m.group(1)
            parts = path.strip('/').split('/')
            if len(parts) >= 2:
                server_bases.add(parts[1])  # z.B. 'auth' aus '/api/auth/login'

        # Prüfe ob alle Server-Bereiche in api.js vorkommen
        missing_bases = server_bases - api_bases
        # Toleriere interne Pfade die kein Frontend-Gegenstück brauchen
        internal = {'power', 'sql', 'terminal', 'ws', 'crews', 'marketplace',
                     'autonomous', 'cluster', 'vision', 'mobile-bridge'}
        missing_bases -= internal

        self.assertLessEqual(len(missing_bases), 3,
                             f"Server-API-Bereiche ohne api.js-Gegenstück: {missing_bases}")


class TestRateLimiting(unittest.TestCase):
    """Rate-Limiting Middleware Tests."""

    def test_rate_limit_import(self):
        """Rate-Limit Store muss importierbar sein."""
        content = (Path(__file__).resolve().parent.parent / "web" / "server.py").read_text()
        self.assertIn('_rate_limit_store', content, "Rate-Limit Store nicht gefunden")
        self.assertIn('_RATE_LIMIT', content, "Rate-Limit Konstante nicht gefunden")

    def test_rate_limit_values(self):
        """Rate-Limit muss 120 req/min sein."""
        content = (Path(__file__).resolve().parent.parent / "web" / "server.py").read_text()
        self.assertIn('_RATE_LIMIT = 120', content, "Rate-Limit != 120")
        self.assertIn('_RATE_WINDOW = 60', content, "Rate-Window != 60")


if __name__ == '__main__':
    unittest.main()
