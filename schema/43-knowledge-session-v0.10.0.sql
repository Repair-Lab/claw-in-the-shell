-- ═══════════════════════════════════════════════════════════════
-- DBAI Knowledge Session v0.10.0
-- Dokumentation aller Änderungen aus der v0.10.0-Session
-- ═══════════════════════════════════════════════════════════════

-- ─── 1. Changelog-Einträge ───
INSERT INTO dbai_knowledge.changelog (version, change_type, title, description)
VALUES
  ('0.10.0', 'feature', 'Notification-System', 'NotificationProvider + useNotification Hook mit Toast-Benachrichtigungen (success/error/warning/info), Auto-Dismiss, Bottom-Right UI. Datei: frontend/src/hooks/useNotification.jsx'),
  ('0.10.0', 'feature', 'Keyboard Shortcuts', 'Globaler Keyboard-Shortcut-Handler: Ctrl+K(Spotlight), Ctrl+T(Terminal), Ctrl+,(Settings), Ctrl+L(Lock), Ctrl+M(Monitor), Escape(Close). Datei: frontend/src/hooks/useKeyboardShortcuts.js'),
  ('0.10.0', 'feature', 'SpotlightSearch', 'App-Launcher mit Fuzzy-Suche, Keyboard-Navigation, Quick-Actions (>terminal, >monitor, >settings, >ghost). Datei: frontend/src/components/SpotlightSearch.jsx'),
  ('0.10.0', 'feature', 'Desktop Netzwerk-Widget', 'Netzwerk-Widget in Taskbar mit IP/Hostname-Anzeige, SpotlightSearch-Integration, KeyboardShortcuts-Integration'),
  ('0.10.0', 'feature', '14 neue CRUD-Endpoints', 'DELETE firewall/rules, POST anomaly/resolve, DELETE synaptic/memories, POST+DELETE rag/sources, POST+DELETE+POST immutable/snapshots, DELETE+GET usb/jobs, PATCH hotspot/config, POST browser+config/selective, POST workspace/open'),
  ('0.10.0', 'feature', 'Export CSV/JSON', 'GET /api/export/{schema}/{table}?format=json|csv + GET /api/export/logs. CSV-Download mit Content-Disposition Header, max 10000 Zeilen.'),
  ('0.10.0', 'feature', 'User Management API', 'GET/POST/PATCH/DELETE /api/users — Benutzer anlegen, auflisten, aktualisieren, deaktivieren (Soft-Delete)'),
  ('0.10.0', 'feature', 'Audit & Backup API', 'GET /api/audit/log, GET /api/audit/changes, POST /api/backup/trigger, GET /api/backup/status'),
  ('0.10.0', 'security', 'Rate-Limiting Middleware', 'In-Memory Rate-Limiter: 120 Requests/Minute pro IP. HTTP-429 bei Überschreitung. defaultdict(list) mit Timestamps.'),
  ('0.10.0', 'feature', '24 neue API-Client-Methoden', '24 neue Methoden in frontend/src/api.js: CRUD für alle 10 Apps + Export + User + Audit + Backup'),
  ('0.10.0', 'feature', 'UI-CRUD in 10 Komponenten', 'Delete/Resolve/Cancel/Add-Buttons, Selective Import Checkboxen, Config-Edit, Open-File in: FirewallManager, AnomalyDetector, SynapticViewer, RAGManager, ImmutableFS, USBInstaller, BrowserMigration, ConfigImporter, WLANHotspot, WorkspaceMapper'),
  ('0.10.0', 'feature', 'Settings für 13 Apps', 'useAppSettings Hook + AppSettingsPanel + Settings-Button für: AIWorkshop, AnomalyDetector, AppSandbox, BrowserMigration, ConfigImporter, FirewallManager, GhostUpdater, ImmutableFS, RAGManager, SynapticViewer, USBInstaller, WLANHotspot, WorkspaceMapper'),
  ('0.10.0', 'schema', 'schema/42 + schema/43', 'schema/42-remaining-app-settings-seed.sql (13 Apps) + schema/43-knowledge-session-v0.10.0.sql'),
  ('0.10.0', 'docs', 'CHANGELOG.md', 'Vollständiges Changelog erstellt mit History von v0.6.0 bis v0.10.0')
ON CONFLICT DO NOTHING;

-- ─── 2. System Memory ───
INSERT INTO dbai_knowledge.system_memory (category, title, content, structured_data, valid_from, priority)
VALUES
  ('architecture', 'v0.10.0 Notification System', 'Toast-Notification-System mit Provider-Pattern. NotificationProvider wrappt App.jsx, useNotification() Hook bietet notify/success/error/warning/info/dismiss/dismissAll. Container rendert Toasts als fixed-Position Overlay bottom-right.', '{"provider": "NotificationProvider", "hook": "useNotification", "types": ["success","error","warning","info"], "auto_dismiss": true, "position": "bottom-right", "file": "frontend/src/hooks/useNotification.jsx"}', '0.10.0', 85),
  ('architecture', 'v0.10.0 Keyboard Shortcuts', 'Globaler Keyboard-Shortcut-Handler mit Registry-Map. Ein document.addEventListener. useKeyboardShortcuts() registriert Handler auf Mount, räumt auf bei Unmount. Shortcuts: Ctrl+K, Ctrl+T, Ctrl+Comma, Ctrl+L, Ctrl+M, Escape.', '{"hook": "useKeyboardShortcuts", "registry": "global Map", "file": "frontend/src/hooks/useKeyboardShortcuts.js"}', '0.10.0', 80),
  ('architecture', 'v0.10.0 SpotlightSearch', 'App-Launcher mit Fuzzy-Suche über app_id/name/description. Keyboard-Navigation, Quick-Actions. Modal-Overlay mit Auto-Focus.', '{"component": "SpotlightSearch", "quick_actions": [">terminal", ">monitor", ">settings", ">ghost"], "file": "frontend/src/components/SpotlightSearch.jsx"}', '0.10.0', 80),
  ('inventory', 'v0.10.0 CRUD Endpoints', '14 neue CRUD-Endpoints in server.py: Firewall DELETE, Anomaly POST resolve, Synaptic DELETE, RAG POST+DELETE, Immutable POST+DELETE+POST, USB DELETE+GET, Hotspot PATCH, Browser+Config POST selective, Workspace POST open.', '{"total_new": 14}', '0.10.0', 90),
  ('inventory', 'v0.10.0 System APIs', 'Export CSV/JSON (2 Endpoints), User Management (4), Audit+Backup (4), Rate-Limiting Middleware. server.py jetzt ca. 6500 Zeilen, ca. 235 Endpoints.', '{"export": 2, "user_mgmt": 4, "audit_backup": 4, "rate_limiting": "120/min/ip", "total_endpoints_approx": 235}', '0.10.0', 85),
  ('inventory', 'v0.10.0 Neue Dateien', '6 neue Dateien: useNotification.jsx, useKeyboardShortcuts.js, SpotlightSearch.jsx, CHANGELOG.md, schema/42, schema/43. 17 modifizierte Dateien.', '{"new_files_count": 6, "modified_files_count": 17}', '0.10.0', 75),
  ('convention', 'v0.10.0 Settings Completion', 'Alle 29+ Apps haben jetzt vollständige Settings-Unterstützung. Pattern: useAppSettings(appId) Hook + AppSettingsPanel Komponente + Button im App-Header.', '{"total_apps": 29, "all_have_settings": true}', '0.10.0', 90),
  ('operational', 'v0.10.0 Rate Limiting', 'In-Memory Rate-Limiter: defaultdict(list) mit Timestamps. 120 Requests/Minute pro IP. Nicht persistent über Restarts. Für Production: Redis-basiert.', '{"type": "in-memory", "limit": 120, "window_seconds": 60, "per": "ip", "response_code": 429}', '0.10.0', 85)
ON CONFLICT (category, title) DO NOTHING;

-- ─── 3. Module Registry ───
INSERT INTO dbai_knowledge.module_registry (file_path, category, language, description, provides, depends_on, version, metadata)
VALUES
  ('frontend/src/hooks/useNotification.jsx', 'frontend', 'jsx', 'Toast-Notification-System mit Provider-Pattern. Typen: success/error/warning/info. Auto-Dismiss konfigurierbar.', ARRAY['NotificationProvider', 'useNotification'], ARRAY['react'], '0.10.0', '{"methods": ["notify", "success", "error", "warning", "info", "dismiss", "dismissAll"]}'),
  ('frontend/src/hooks/useKeyboardShortcuts.js', 'frontend', 'javascript', 'Globaler Keyboard-Shortcut-Handler mit Registry-Map. Unterstuetzt Ctrl/Meta/Shift-Combos. Cleanup bei Unmount.', ARRAY['useKeyboardShortcuts', 'registerShortcut', 'unregisterShortcut', 'DEFAULT_SHORTCUTS'], ARRAY['react'], '0.10.0', '{"default_shortcuts": ["Ctrl+K", "Ctrl+T", "Ctrl+,", "Ctrl+L", "Escape", "Ctrl+M"]}'),
  ('frontend/src/components/SpotlightSearch.jsx', 'frontend', 'jsx', 'App-Launcher mit Fuzzy-Suche, Keyboard-Navigation, Quick-Actions. Modal-Overlay mit Auto-Focus.', ARRAY['SpotlightSearch'], ARRAY['react', 'api'], '0.10.0', '{"props": ["isOpen", "onClose", "onLaunchApp", "apps"]}')
ON CONFLICT (file_path) DO UPDATE SET version = '0.10.0', description = EXCLUDED.description;

-- ─── 4. Architecture Decisions ───
INSERT INTO dbai_knowledge.architecture_decisions (title, context, decision, consequences, status)
VALUES
  ('NotificationProvider als App-weiter Context', 'Toast-Benachrichtigungen muessen von jeder Komponente ausloesbar sein, ohne Props durchzureichen.', 'React Context + Provider in App.jsx, useNotification() Hook. Container rendert Toasts als fixed-Position Overlay.', 'Alle Komponenten koennen notify()/success()/error() aufrufen. Kein Props-Drilling. Provider muss ganz oben in der Baum-Hierarchie stehen.', 'accepted'),
  ('Globaler Shortcut-Handler statt per-Component', 'Keyboard-Shortcuts sollten systemweit funktionieren, auch wenn keine App fokussiert ist.', 'Globale Registry (Map) mit einem einzigen document.addEventListener. useKeyboardShortcuts() registriert Handler auf Mount, raeumt auf bei Unmount.', 'Einheitliche Shortcut-Verwaltung. Moegliche Konflikte bei gleichen Shortcuts in verschiedenen Kontexten.', 'accepted'),
  ('In-Memory Rate-Limiting statt Redis', 'Einfaches Rate-Limiting fuer Single-Server-Deployment. Keine Redis-Abhaengigkeit.', 'defaultdict(list) mit Timestamps. Zeitfenster-basierte Bereinigung bei jedem Request. 120 req/min pro IP.', 'Kein zusaetzlicher Service noetig. Nicht persistent ueber Restarts. Nicht fuer Multi-Instance.', 'accepted'),
  ('CSV-Export via Server statt Client-Side', 'Grosse Datenmengen (bis 10000 Zeilen) sollen als CSV herunterladbar sein.', 'Server generiert CSV via io.StringIO + csv.DictWriter. Content-Disposition Header fuer automatischen Download.', 'Server-Last bei grossen Exports. Dafuer korrekte Serialisierung von JSONB/Timestamp-Feldern.', 'accepted'),
  ('Soft-Delete fuer User statt Hard-Delete', 'Benutzer sollen deaktivierbar sein, ohne Referenzen zu verlieren.', 'DELETE /api/users/{id} setzt is_active=false statt tatsaechlichem DELETE.', 'Audit-Trail bleibt erhalten. Benutzer koennen reaktiviert werden. Keine Orphan-Records.', 'accepted')
ON CONFLICT DO NOTHING;

-- ─── 5. Build Log ───
INSERT INTO dbai_knowledge.build_log (build_type, success, duration_ms, description, system_info)
VALUES
  ('upgrade', true, 0, 'v0.10.0 Feature-Batch: 6 neue Dateien, 17 modifizierte, 24 neue Endpoints, 2 neue Hooks, 1 neue Komponente, Rate-Limiting Middleware, CHANGELOG.md', '{"session": "v0.10.0-implementation", "new_files": 6, "modified_files": 17, "new_endpoints": 24}')
ON CONFLICT DO NOTHING;

-- ─── 6. Agent Session ───
INSERT INTO dbai_knowledge.agent_sessions (session_date, version_start, version_end, summary, files_created, files_modified, schemas_added, goals, decisions)
VALUES
  (CURRENT_DATE, '0.9.0', '0.10.0',
   'Vollstaendige Implementierung aller identifizierten Luecken: 14 CRUD-Endpoints, Export CSV/JSON, User-Management, Audit+Backup API, Rate-Limiting, Notification-System, Keyboard-Shortcuts, SpotlightSearch, Netzwerk-Widget, Settings fuer 13 Apps, UI-CRUD fuer 10 Apps, CHANGELOG.md',
   ARRAY['frontend/src/hooks/useNotification.jsx', 'frontend/src/hooks/useKeyboardShortcuts.js', 'frontend/src/components/SpotlightSearch.jsx', 'CHANGELOG.md', 'schema/42-remaining-app-settings-seed.sql', 'schema/43-knowledge-session-v0.10.0.sql'],
   ARRAY['web/server.py', 'frontend/src/api.js', 'frontend/src/App.jsx', 'frontend/src/components/Desktop.jsx', 'frontend/src/components/apps/FirewallManager.jsx', 'frontend/src/components/apps/AnomalyDetector.jsx', 'frontend/src/components/apps/SynapticViewer.jsx', 'frontend/src/components/apps/RAGManager.jsx', 'frontend/src/components/apps/ImmutableFS.jsx', 'frontend/src/components/apps/USBInstaller.jsx', 'frontend/src/components/apps/BrowserMigration.jsx', 'frontend/src/components/apps/ConfigImporter.jsx', 'frontend/src/components/apps/WLANHotspot.jsx', 'frontend/src/components/apps/WorkspaceMapper.jsx', 'frontend/src/components/apps/AIWorkshop.jsx', 'frontend/src/components/apps/AppSandbox.jsx', 'frontend/src/components/apps/GhostUpdater.jsx'],
   ARRAY['schema/42-remaining-app-settings-seed.sql', 'schema/43-knowledge-session-v0.10.0.sql'],
   ARRAY['14 CRUD-Endpoints', 'Export CSV/JSON', 'User Management CRUD', 'Audit + Backup API', 'Rate-Limiting', 'Notification-System', 'Keyboard Shortcuts', 'SpotlightSearch', 'Settings 13 Apps', 'UI-CRUD 10 Apps', 'CHANGELOG.md', 'DB-Dokumentation'],
   ARRAY['NotificationProvider als App-weiter Context', 'Globaler Shortcut-Handler', 'In-Memory Rate-Limiting', 'CSV-Export Server-Side', 'Soft-Delete fuer User'])
ON CONFLICT DO NOTHING;

-- ─── 7. Known Issues ───
INSERT INTO dbai_knowledge.known_issues (title, description, severity, workaround, status)
VALUES
  ('Rate-Limiting nicht persistent', 'Rate-Limiting ist In-Memory (defaultdict) und nicht persistent. Bei Server-Restart wird der Counter zurueckgesetzt.', 'low', 'Fuer Produktionseinsatz Redis-basiertes Rate-Limiting implementieren.', 'workaround'),
  ('Backup in /tmp nicht persistent', 'Backup-Trigger (POST /api/backup/trigger) speichert Dumps in /tmp, was bei Container-Restart verloren geht.', 'medium', 'Backup-Pfad auf persistentes Volume aendern oder S3-Upload implementieren.', 'workaround'),
  ('User-Passwoerter SHA256 statt bcrypt', 'User-Passwoerter in POST /api/users werden mit einfachem SHA256 gehasht statt bcrypt/argon2.', 'medium', 'Fuer Produktionseinsatz passlib mit bcrypt verwenden.', 'workaround')
ON CONFLICT DO NOTHING;
