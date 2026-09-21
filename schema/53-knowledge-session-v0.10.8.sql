-- ==========================================================================
-- DBAI Knowledge Session — v0.10.8 (Tab-Isolation / Virtual Desktops)
-- Datum: 2026-03-17
-- ==========================================================================

-- Changelog
INSERT INTO dbai_knowledge.changelog (version, change_type, title, description, affected_files, author)
VALUES
('0.10.8', 'feature', 'Tab-Isolation — Jeder Browser-Tab ist ein eigener Rechner',
 'Jeder Browser-Tab bekommt eine einzigartige tab_id (sessionStorage), wird beim Backend als "Tab-Instanz" registriert und erhält seinen eigenen Desktop-State: eigene Fenster, eigene Icon-Reihenfolge, eigene Ordner, eigenen Hostnamen, eigene WebSocket-Verbindung. Mehrere Tabs = mehrere unabhängige virtuelle Rechner.',
 ARRAY['schema/52-tab-isolation.sql','web/server.py','frontend/src/api.js','frontend/src/App.jsx','frontend/src/components/Desktop.jsx'],
 'ghost-agent')
ON CONFLICT DO NOTHING;

INSERT INTO dbai_knowledge.changelog (version, change_type, title, description, affected_files, author)
VALUES
('0.10.8', 'fix', 'WebSocket-Manager: Multi-Tab statt Überschreiben',
 'ConnectionManager umgebaut: active_connections nutzt jetzt tab_id als Key statt session_id. Neues session_tabs Mapping (session_id → set[tab_id]) für Session-weite Broadcasts. send_to_tab() für tab-spezifische Nachrichten, send_to_session() sendet an ALLE Tabs einer Session. Vorher: Tab 2 überschrieb Tab 1 → Tab 1 verlor WS-Events.',
 ARRAY['web/server.py'],
 'ghost-agent')
ON CONFLICT DO NOTHING;

INSERT INTO dbai_knowledge.changelog (version, change_type, title, description, affected_files, author)
VALUES
('0.10.8', 'fix', 'Icon-Order und Folders per Tab statt globalem localStorage',
 'Ordner (dbai_folders) und Icon-Reihenfolge (dbai_icon_order) werden jetzt in sessionStorage (Tab-lokal) gespeichert und per debounced API-Call in dbai_ui.tab_instances synchronisiert. Vorher: Ein globales localStorage wurde von allen Tabs geteilt → Änderungen in Tab 1 überschrieben Tab 2.',
 ARRAY['frontend/src/components/Desktop.jsx'],
 'ghost-agent')
ON CONFLICT DO NOTHING;

-- System Memory
INSERT INTO dbai_knowledge.system_memory (category, title, content, tags, author)
VALUES
('architecture', 'Tab-Isolation Architektur (Virtual Desktops)',
 'Jeder Browser-Tab = eigener virtueller Rechner. Ablauf:
1. App.jsx: sessionStorage.getItem("dbai_tab_id") → eindeutige Tab-ID (überlebt NICHT Tab-Schließen)
2. Login-Token bleibt in localStorage (shared) — User muss sich nicht neu einloggen
3. Alle API-Requests senden X-Tab-Id Header automatisch
4. POST /api/tabs/register: Registriert Tab in dbai_ui.tab_instances, vergibt Hostname (DBAI-1, DBAI-2...)
5. GET /api/desktop: Wenn X-Tab-Id Header → get_tab_desktop_state() mit Tab-isolierten Fenstern
6. WebSocket: /ws/{token}?tab_id=xxx → eigene Verbindung pro Tab
7. Heartbeat alle 60s: POST /api/tabs/{tab_id}/heartbeat
8. beforeunload: Tab wird deaktiviert
9. Cleanup: dbai_ui.cleanup_stale_tabs() löscht Tabs älter als 4h

DB-Tabelle: dbai_ui.tab_instances (id, session_id, tab_id, hostname, label, wallpaper, icon_order, folders, is_active, last_heartbeat)',
 ARRAY['tab-isolation','virtual-desktop','multi-tab','architecture'],
 'ghost-agent')
ON CONFLICT DO NOTHING;

INSERT INTO dbai_knowledge.system_memory (category, title, content, tags, author)
VALUES
('convention', 'sessionStorage vs localStorage — Tab-Isolation',
 'KRITISCHE KONVENTION für Tab-Isolation:
- localStorage: Wird von ALLEN Tabs geteilt → NUR für Daten die überall gleich sein sollen (Login-Token, globale Einstellungen)
- sessionStorage: Pro Tab isoliert → Für Tab-spezifische Daten (tab_id, icon_order, folders)
- Jeder neue Tab bekommt automatisch eine frische sessionStorage
- Duplizierte Tabs (Ctrl+Shift+T / Ctrl+D) erben sessionStorage → tab_id wird NICHT dupliziert da sessionStorage bei Tab-Duplizierung eine Kopie bekommt, aber die tab_id im Backend neu registriert wird',
 ARRAY['sessionStorage','localStorage','tab-isolation','convention'],
 'ghost-agent')
ON CONFLICT DO NOTHING;

INSERT INTO dbai_knowledge.system_memory (category, title, content, tags, author)
VALUES
('architecture', 'Tab-Management API Endpoints',
 'Tab-Verwaltung über 5 Endpoints:
- POST /api/tabs/register — Tab registrieren (tab_id, optional hostname/label). Gibt {tab_id, hostname, label, created} zurück
- GET /api/tabs — Alle aktiven Tabs der Session auflisten
- PATCH /api/tabs/{tab_id} — Tab-Einstellungen ändern (hostname, label, wallpaper, icon_order, folders)
- POST /api/tabs/{tab_id}/heartbeat — Heartbeat (alle 60s vom Frontend)
- DELETE /api/tabs/{tab_id} — Tab deaktivieren + zugehörige Windows löschen',
 ARRAY['tab-management','api','endpoints'],
 'ghost-agent')
ON CONFLICT DO NOTHING;

-- Build Log
INSERT INTO dbai_knowledge.build_log (build_type, success, duration_ms, description)
VALUES
('schema_migration', true, 1500,
 'v0.10.8: Tab-Isolation — dbai_ui.tab_instances Tabelle, 3 DB-Funktionen, WebSocket Multi-Tab, Frontend sessionStorage')
ON CONFLICT DO NOTHING;

-- Agent Session
INSERT INTO dbai_knowledge.agent_sessions (version_start, version_end, summary, files_created, files_modified, schemas_added, goals, decisions)
VALUES
('0.10.8', '0.10.8',
 'Tab-Isolation implementiert: Jeder Browser-Tab ist ein eigener virtueller Rechner. Neue DB-Tabelle tab_instances speichert Hostname, Label, Wallpaper, Icon-Reihenfolge und Ordner pro Tab. WebSocket-Manager auf Multi-Tab umgebaut (tab_id statt session_id). Frontend nutzt sessionStorage für tab_id. 5 neue API-Endpoints für Tab-Management. Desktop.jsx zeigt Tab-Hostname in der Taskbar.',
 ARRAY['schema/52-tab-isolation.sql','schema/53-knowledge-session-v0.10.8.sql'],
 ARRAY['web/server.py','frontend/src/api.js','frontend/src/App.jsx','frontend/src/components/Desktop.jsx'],
 ARRAY['schema/52-tab-isolation.sql','schema/53-knowledge-session-v0.10.8.sql'],
 ARRAY['Multi-Tab Isolation implementieren','Jeder Tab = eigener Rechner','WebSocket pro Tab statt pro Session','Desktop-State pro Tab isolieren'],
 ARRAY['sessionStorage für tab_id (Tab-lokal) statt localStorage (global)','Login-Token bleibt in localStorage (User muss sich nicht neu anmelden)','WebSocket bekommt tab_id als Query-Parameter statt separaten Endpoint','Hostname auto-generiert als DBAI-1, DBAI-2 etc.','Icon-Order und Folders per debounced API-Call in DB synchronisiert','Heartbeat alle 60s um inaktive Tabs zu erkennen']
)
ON CONFLICT DO NOTHING;

-- Known Issues
INSERT INTO dbai_knowledge.known_issues (title, description, severity, status, affected_files, workaround, resolution)
VALUES
('Multi-Tab: WebSocket überschreibt vorherige Verbindungen',
 'Der alte ConnectionManager nutzte session_id als Key für active_connections (dict). Wenn ein zweiter Tab geöffnet wurde, überschrieb er die WS-Verbindung des ersten Tabs. Tab 1 bekam keine Events mehr.',
 'high', 'resolved',
 ARRAY['web/server.py'],
 'Nur einen Tab nutzen',
 'ConnectionManager auf tab_id als Key umgebaut. send_to_session() iteriert über alle tab_ids einer Session. Jeder Tab hat seine eigene WebSocket-Verbindung via /ws/{token}?tab_id=xxx.')
ON CONFLICT DO NOTHING;

INSERT INTO dbai_knowledge.known_issues (title, description, severity, status, affected_files, workaround, resolution)
VALUES
('Multi-Tab: Desktop-State und localStorage geteilt',
 'Alle Tabs teilten denselben Desktop-State (gleiche session_id → gleiche Fenster) und dasselbe localStorage (icon_order, folders). Änderungen in Tab 1 waren sofort in Tab 2 sichtbar.',
 'high', 'resolved',
 ARRAY['frontend/src/components/Desktop.jsx','frontend/src/App.jsx'],
 'Nur einen Tab nutzen',
 'Tab-Instanzen in der DB (dbai_ui.tab_instances) speichern pro-Tab State. Frontend nutzt sessionStorage (Tab-lokal) statt localStorage. API-Requests senden X-Tab-Id Header. GET /api/desktop gibt Tab-isolierten State zurück.')
ON CONFLICT DO NOTHING;
