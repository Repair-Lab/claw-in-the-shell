-- ============================================================================
-- DBAI v0.9.0 – Wissensdokumentation: Per-App Settings System
-- Erstellt durch KI-Agent-Session
-- Alle Erkenntnisse, Änderungen, Entscheidungen und Muster
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. CONSTRAINTS ERWEITERN (für JS/Frontend-Module)
-- ============================================================================

ALTER TABLE dbai_knowledge.module_registry
  DROP CONSTRAINT IF EXISTS module_registry_language_check;
ALTER TABLE dbai_knowledge.module_registry
  ADD CONSTRAINT module_registry_language_check
  CHECK (language = ANY (ARRAY[
    'sql','python','c','toml','conf','bash','markdown','txt',
    'makefile','so','javascript','jsx','css','html','json'
  ]));

ALTER TABLE dbai_knowledge.module_registry
  DROP CONSTRAINT IF EXISTS module_registry_category_check;
ALTER TABLE dbai_knowledge.module_registry
  ADD CONSTRAINT module_registry_category_check
  CHECK (category = ANY (ARRAY[
    'schema','bridge','recovery','llm','config','script','test',
    'c_binding','documentation','data','frontend','web'
  ]));

-- ============================================================================
-- 2. AGENT SESSION  (v0.9.0)
-- ============================================================================

INSERT INTO dbai_knowledge.agent_sessions (
  session_date, version_start, version_end, summary,
  files_created, files_modified, schemas_added,
  goals, decisions, blockers
) VALUES (
  CURRENT_DATE,
  '0.8.0',
  '0.9.0',
  $$Vollständige Analyse aller 19 registrierten Apps auf fehlende Einstellungen. Implementierung eines generischen, JSON-Schema-gesteuerten Per-App Settings Systems: DB-Schema (Tabellen, Funktionen, RLS), 5 API-Endpunkte, React-Hook, generische UI-Komponente, Integration in alle 16 App-Komponenten, zentrales App-Einstellungen-Tab in Settings.jsx. Abschließende Wissensdokumentation in die Datenbank.$$,

  ARRAY[
    'schema/39-app-settings.sql',
    'schema/40-app-settings-seed.sql',
    'schema/41-knowledge-session-v0.9.0.sql',
    'frontend/src/hooks/useAppSettings.js',
    'frontend/src/components/AppSettingsPanel.jsx'
  ],

  ARRAY[
    'web/server.py',
    'frontend/src/api.js',
    'frontend/src/components/apps/SystemMonitor.jsx',
    'frontend/src/components/apps/Terminal.jsx',
    'frontend/src/components/apps/GhostManager.jsx',
    'frontend/src/components/apps/EventViewer.jsx',
    'frontend/src/components/apps/ProcessManager.jsx',
    'frontend/src/components/apps/HealthDashboard.jsx',
    'frontend/src/components/apps/SQLConsole.jsx',
    'frontend/src/components/apps/FileBrowser.jsx',
    'frontend/src/components/apps/KnowledgeBase.jsx',
    'frontend/src/components/apps/ErrorAnalyzer.jsx',
    'frontend/src/components/apps/GhostChat.jsx',
    'frontend/src/components/apps/SoftwareStore.jsx',
    'frontend/src/components/apps/OpenClawIntegrator.jsx',
    'frontend/src/components/apps/SQLExplorer.jsx',
    'frontend/src/components/apps/WebFrame.jsx',
    'frontend/src/components/apps/LLMManager.jsx',
    'frontend/src/components/apps/Settings.jsx'
  ],

  ARRAY[
    'schema/39-app-settings.sql',
    'schema/40-app-settings-seed.sql',
    'schema/41-knowledge-session-v0.9.0.sql'
  ],

  ARRAY[
    'Analyse aller 19 Apps auf fehlende Einstellungen',
    'Generisches Per-App Settings System implementieren',
    'DB-Schema mit Tabellen, Funktionen und RLS erstellen',
    'REST-API Endpunkte fuer Settings CRUD',
    'React useAppSettings Hook mit debounced save',
    'Generische AppSettingsPanel UI-Komponente',
    'Alle 16 App-Komponenten mit Settings integrieren',
    'Zentrales App-Einstellungen-Tab in Settings.jsx',
    'Wissensdokumentation in die Datenbank'
  ],

  ARRAY[
    'JSON Schema-getriebener Ansatz statt hardcoded Forms',
    'Server-side Merge: defaults + user overrides (COALESCE/||)',
    'UPSERT-Pattern fuer save_app_settings (ON CONFLICT DO UPDATE)',
    'Row-Level Security auf app_user_settings (user sieht nur eigene)',
    'Debounced Save (500ms) im React Hook statt expliziter Save-Button',
    'Gruppierung der Settings nach group-Feld aus Schema',
    'Bestehende GhostChat Settings-View beibehalten (separater Button)',
    'sql-explorer und web-frame mussten manuell in dbai_ui.apps eingefuegt werden'
  ],

  ARRAY[
    'sql-explorer und web-frame fehlten in dbai_ui.apps (schema/29 hatte non-existent status-Spalte)',
    'KnowledgeBase.jsx hatte JSX-Fragment-Fehler beim ersten Versuch (verschachtelte Conditionals)'
  ]
);

-- ============================================================================
-- 3. CHANGELOG  (15 Eintraege)
-- ============================================================================

INSERT INTO dbai_knowledge.changelog (version, change_type, title, description, affected_files, author)
VALUES
('0.9.0', 'schema', 'Per-App Settings: DB-Infrastruktur',
 $$Neue Spalten default_settings (JSONB) und settings_schema (JSONB) auf dbai_ui.apps. Neue Tabelle dbai_ui.app_user_settings (user_id, app_id, settings JSONB) mit UNIQUE-Constraint. RLS-Policies: Benutzer sehen nur eigene Einstellungen.$$,
 ARRAY['schema/39-app-settings.sql'], 'copilot-agent'),

('0.9.0', 'schema', 'Per-App Settings: DB-Funktionen',
 $$Vier Funktionen: get_app_settings(user_uuid, app_text) merged defaults + user overrides mit COALESCE/||. save_app_settings(user_uuid, app_text, jsonb) UPSERT mit merge. reset_app_settings(user_uuid, app_text) DELETE der User-Overrides. get_all_app_settings(user_uuid) Alle Apps mit merged Settings und Schemas.$$,
 ARRAY['schema/39-app-settings.sql'], 'copilot-agent'),

('0.9.0', 'schema', 'Per-App Settings: Seed-Daten fuer 16 Apps',
 $$Default-Settings und Settings-Schemas fuer alle 16 Apps konfiguriert: system-monitor, ghost-manager, terminal, file-browser, knowledge-base, event-viewer, process-manager, health-dashboard, ghost-chat, sql-console, error-analyzer, software-store, openclaw-integrator, sql-explorer, web-frame, llm-manager.$$,
 ARRAY['schema/40-app-settings-seed.sql'], 'copilot-agent'),

('0.9.0', 'feature', 'Per-App Settings: 5 REST-API Endpunkte',
 $$GET /api/apps/{app_id}/settings lesen. PATCH /api/apps/{app_id}/settings speichern. DELETE /api/apps/{app_id}/settings zuruecksetzen. GET /api/apps/{app_id}/settings/schema Schema abrufen. GET /api/apps/settings/all Alle Apps komplett.$$,
 ARRAY['web/server.py'], 'copilot-agent'),

('0.9.0', 'feature', 'Per-App Settings: useAppSettings React Hook',
 $$Custom React Hook mit automatischem Laden von Settings + Schema, 500ms debounced auto-save via useRef/setTimeout, update/set/reset Methoden.$$,
 ARRAY['frontend/src/hooks/useAppSettings.js'], 'copilot-agent'),

('0.9.0', 'feature', 'Per-App Settings: AppSettingsPanel Komponente',
 $$Generische React-Komponente: Boolean->Toggle, Number->Slider, Select->Dropdown, String->Text, Color->Picker. Gruppierung nach group-Feld, Sidebar bei mehreren Gruppen, Reset-Button.$$,
 ARRAY['frontend/src/components/AppSettingsPanel.jsx'], 'copilot-agent'),

('0.9.0', 'feature', 'Per-App Settings: SystemMonitor + Terminal + GhostManager',
 $$SystemMonitor: refreshInterval, warningThreshold, criticalThreshold, showNetwork. Terminal: fontSize, fontFamily, scrollbackLines, showStatusBar, cursorStyle. GhostManager: autoRefresh, refreshInterval, showFitnessScore, defaultTab, confirmBeforeSwap.$$,
 ARRAY['frontend/src/components/apps/SystemMonitor.jsx', 'frontend/src/components/apps/Terminal.jsx', 'frontend/src/components/apps/GhostManager.jsx'], 'copilot-agent'),

('0.9.0', 'feature', 'Per-App Settings: EventViewer + ProcessManager + HealthDashboard',
 $$EventViewer: maxEvents, refreshInterval, timestampFormat. ProcessManager: refreshInterval, defaultSort, hideIdle. HealthDashboard: autoRefreshInterval, showScoreBanner, showFixHints, defaultTab.$$,
 ARRAY['frontend/src/components/apps/EventViewer.jsx', 'frontend/src/components/apps/ProcessManager.jsx', 'frontend/src/components/apps/HealthDashboard.jsx'], 'copilot-agent'),

('0.9.0', 'feature', 'Per-App Settings: SQLConsole + FileBrowser + KnowledgeBase',
 $$SQLConsole: maxHistory, fontSize, highlightNull, autoUppercase. FileBrowser: rows_per_page, show_hidden_tables, default_schema. KnowledgeBase: defaultTab, autoScan, previewLimit, showOnlyModels.$$,
 ARRAY['frontend/src/components/apps/SQLConsole.jsx', 'frontend/src/components/apps/FileBrowser.jsx', 'frontend/src/components/apps/KnowledgeBase.jsx'], 'copilot-agent'),

('0.9.0', 'feature', 'Per-App Settings: ErrorAnalyzer + GhostChat + SoftwareStore',
 $$ErrorAnalyzer: autoRefresh, severityFilter, maxEntries, showContext. GhostChat: fontSize, maxMessages, showTimestamps, enableMarkdown, defaultRole. SoftwareStore: defaultTab, showRecommendations, autoUpdate.$$,
 ARRAY['frontend/src/components/apps/ErrorAnalyzer.jsx', 'frontend/src/components/apps/GhostChat.jsx', 'frontend/src/components/apps/SoftwareStore.jsx'], 'copilot-agent'),

('0.9.0', 'feature', 'Per-App Settings: OpenClaw + SQLExplorer + WebFrame + LLM',
 $$OpenClawIntegrator: defaultTab, autoRefresh, gatewayMonitoring. SQLExplorer: rowsPerPage, showNullAs, timestampFormat, enableSearch. WebFrame: defaultUrl, detectBlocked, loadTimeout, enableJavascript. LLMManager: defaultTab, gpuMonitoringInterval, autoRefresh.$$,
 ARRAY['frontend/src/components/apps/OpenClawIntegrator.jsx', 'frontend/src/components/apps/SQLExplorer.jsx', 'frontend/src/components/apps/WebFrame.jsx', 'frontend/src/components/apps/LLMManager.jsx'], 'copilot-agent'),

('0.9.0', 'feature', 'Per-App Settings: Zentrales App-Einstellungen-Tab',
 $$Neues Tab App-Einstellungen in Settings.jsx. AllAppSettingsTab-Komponente: Laedt alle Apps via GET /api/apps/settings/all, zeigt expandierbare Karten pro App mit AppSettingsPanel und Reset-Button.$$,
 ARRAY['frontend/src/components/apps/Settings.jsx'], 'copilot-agent'),

('0.9.0', 'docs', 'Wissensdokumentation v0.9.0',
 $$Vollstaendige Dokumentation aller Erkenntnisse in die Datenbank: agent_sessions, changelog, system_memory, module_registry, architecture_decisions, system_glossary, known_issues, build_log.$$,
 ARRAY['schema/41-knowledge-session-v0.9.0.sql'], 'copilot-agent')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 4. SYSTEM MEMORY  (via save_memory UPSERT-Funktion)
-- ============================================================================

SELECT dbai_knowledge.save_memory(
  'architecture',
  'Per-App Settings Architektur',
  $$Das Per-App Settings System basiert auf einem JSON-Schema-gesteuerten Ansatz:

DATENBANK-SCHICHT:
- dbai_ui.apps hat default_settings (JSONB) und settings_schema (JSONB)
- dbai_ui.app_user_settings speichert User-Overrides (user_id + app_id UNIQUE)
- get_app_settings() merged: defaults || user_overrides (Server-Side Merge)
- save_app_settings() macht UPSERT mit Merge (bestehende + neue Werte)
- RLS: Benutzer sehen nur eigene Einstellungen

API-SCHICHT:
- GET /api/apps/{app_id}/settings -> merged settings
- PATCH /api/apps/{app_id}/settings -> UPSERT user overrides
- DELETE /api/apps/{app_id}/settings -> Reset to defaults
- GET /api/apps/{app_id}/settings/schema -> JSON Schema
- GET /api/apps/settings/all -> Alle Apps komplett

FRONTEND-SCHICHT:
- useAppSettings(appId) Hook: laedt Settings+Schema, 500ms debounced save
- AppSettingsPanel: generische UI aus Schema (bool->toggle, number->slider, select->dropdown)
- Jede App hat Zahnrad-Button der Panel ein/ausblendet
- Settings.jsx hat AllAppSettingsTab fuer zentrale Verwaltung$$,
  90,
  ARRAY['settings', 'architecture', 'json-schema', 'per-app', 'frontend', 'api', 'database'],
  '0.9.0'
);

SELECT dbai_knowledge.save_memory(
  'convention',
  'Neue App-Settings hinzufuegen (Anleitung)',
  $$So fuegt man Settings fuer eine neue App hinzu:

1. DATENBANK:
   UPDATE dbai_ui.apps SET
     default_settings = '{"key": "default_value"}'::jsonb,
     settings_schema = '{"key": {"type":"boolean","label":"Name","group":"Gruppe","description":"Hilfe","default":true}}'::jsonb
   WHERE app_id = 'neue-app';

2. KOMPONENTE:
   import useAppSettings from '../../hooks/useAppSettings';
   import AppSettingsPanel from '../AppSettingsPanel';
   const { settings, schema, update, reset } = useAppSettings('neue-app');
   // Settings nutzen: settings.mySetting
   // Zahnrad-Button + bedingte Anzeige von AppSettingsPanel

3. Schema-Typen: boolean (Toggle), number (Slider mit min/max/step),
   select (Dropdown mit options[]), string (Textfeld), color (Farbwaehler)

4. Gruppen: Settings werden nach "group"-Feld gruppiert.
   Bei mehr als 1 Gruppe erscheint eine Sidebar-Navigation.$$,
  95,
  ARRAY['convention', 'howto', 'settings', 'anleitung', 'neue-app'],
  '0.9.0'
);

SELECT dbai_knowledge.save_memory(
  'schema_map',
  'App-Settings Tabellen und Spalten',
  $$NEUE TABELLE:
- dbai_ui.app_user_settings (user_id UUID FK->users, app_id TEXT FK->apps, settings JSONB)
  UNIQUE(user_id, app_id), RLS: auth.uid() = user_id

NEUE SPALTEN auf dbai_ui.apps:
- default_settings JSONB DEFAULT '{}' - App-weite Standard-Einstellungen
- settings_schema JSONB DEFAULT '{}' - UI-Schema pro Setting-Key

NEUE FUNKTIONEN:
- dbai_ui.get_app_settings(p_user_id UUID, p_app_id TEXT) -> JSONB (merged defaults||overrides)
- dbai_ui.save_app_settings(p_user_id UUID, p_app_id TEXT, p_settings JSONB) -> VOID (UPSERT)
- dbai_ui.reset_app_settings(p_user_id UUID, p_app_id TEXT) -> VOID (DELETE overrides)
- dbai_ui.get_all_app_settings(p_user_id UUID) -> JSONB (Array aller Apps)$$,
  85,
  ARRAY['schema', 'tabellen', 'settings', 'dbai_ui', 'funktionen'],
  '0.9.0'
);

SELECT dbai_knowledge.save_memory(
  'design_pattern',
  'JSON-Schema-getriebene UI-Generierung',
  $$PATTERN: Schema-Driven Form Rendering

Das Settings-Schema definiert pro Key ein Objekt:
  type: boolean|number|select|string|color
  label: Benutzer-sichtbarer Name
  group: Kategorie/Tab-Gruppe
  description: Tooltip/Hilfetext
  default: Standardwert
  min/max/step: nur bei number
  options: [{value,label}] nur bei select

Die AppSettingsPanel-Komponente:
1. Gruppiert Settings nach group Feld
2. Bei mehr als 1 Gruppe: Sidebar mit Gruppe-Buttons
3. Rendert pro Typ den passenden Control:
   boolean -> Label + Toggle-Switch (CSS-animiert)
   number  -> Label + Range-Slider + Wert-Anzeige
   select  -> Label + dropdown mit option-Liste
   string  -> Label + input text
   color   -> Label + input color
4. onChange -> update(key, value) -> debounced API PATCH
5. Reset-Button -> reset() -> API DELETE -> Settings neu laden

VORTEIL: Neue Settings brauchen NUR DB-Aenderung, kein Frontend-Code.$$,
  88,
  ARRAY['pattern', 'schema-driven', 'ui-generierung', 'react', 'form-rendering'],
  '0.9.0'
);

SELECT dbai_knowledge.save_memory(
  'workflow',
  'Settings-Datenfluss DB API Hook UI',
  $$FLOW: Wie App-Settings vom DB zum User fliessen:

1. APP OEFFNEN:
   useAppSettings("app-id") Hook initialisiert
   -> GET /api/apps/{app_id}/settings
   -> server.py: db_call_json_rt("dbai_ui.get_app_settings", [user_id, app_id])
   -> PostgreSQL: SELECT a.default_settings || COALESCE(u.settings, '{}')
   -> Merged JSON -> API Response -> Hook state: settings + schema

2. SETTING AENDERN:
   User aendert Toggle/Slider/Select in AppSettingsPanel
   -> onChange -> update(key, value) -> setSettings({...prev, key: value})
   -> 500ms Debounce (clearTimeout/setTimeout in useRef)
   -> PATCH /api/apps/{app_id}/settings Body: gesamtes settings-Objekt
   -> server.py: db_execute_rt("SELECT dbai_ui.save_app_settings($1,$2,$3)")
   -> PostgreSQL: INSERT ON CONFLICT DO UPDATE SET settings = settings || $3

3. RESET:
   User klickt Zuruecksetzen in AppSettingsPanel
   -> reset() -> DELETE /api/apps/{app_id}/settings
   -> PostgreSQL: DELETE FROM app_user_settings WHERE ...
   -> Hook laedt Settings neu -> nur defaults greifen$$,
  85,
  ARRAY['workflow', 'datenfluss', 'settings', 'api', 'hook', 'debounce'],
  '0.9.0'
);

SELECT dbai_knowledge.save_memory(
  'inventory',
  'Per-App Settings Inventar (16 Apps)',
  $$VOLLSTAENDIGES INVENTAR aller konfigurierten App-Settings:

system-monitor: refreshInterval(5s), warningThreshold(80%), criticalThreshold(95%), showNetwork(true)
terminal: fontSize(14), fontFamily(monospace), scrollbackLines(1000), showStatusBar(true), cursorStyle(block)
ghost-manager: autoRefresh(true), refreshInterval(30s), showFitnessScore(true), defaultTab(overview), confirmBeforeSwap(true)
event-viewer: maxEvents(500), refreshInterval(5s), timestampFormat(iso)
process-manager: refreshInterval(3s), defaultSort(cpu), hideIdle(false)
health-dashboard: autoRefreshInterval(30s), showScoreBanner(true), showFixHints(true), defaultTab(checks)
sql-console: maxHistory(50), fontSize(14), highlightNull(true), autoUppercase(false)
file-browser: rows_per_page(50), show_hidden_tables(false), default_schema(public)
knowledge-base: defaultTab(modules), autoScan(false), previewLimit(500), showOnlyModels(false)
error-analyzer: autoRefresh(true), severityFilter(all), maxEntries(200), showContext(true)
ghost-chat: fontSize(14), maxMessages(200), showTimestamps(true), enableMarkdown(true), defaultRole(ghost_core)
software-store: defaultTab(available), showRecommendations(true), autoUpdate(false)
openclaw-integrator: defaultTab(overview), autoRefresh(true), gatewayMonitoring(true)
sql-explorer: rowsPerPage(25), showNullAs(NULL), timestampFormat(locale), enableSearch(true)
web-frame: defaultUrl(https://dbai.dev), detectBlocked(true), loadTimeout(15), enableJavascript(true)
llm-manager: defaultTab(providers), gpuMonitoringInterval(5), autoRefresh(true)$$,
  80,
  ARRAY['inventar', 'settings', 'apps', 'konfiguration', 'vollstaendig'],
  '0.9.0'
);

SELECT dbai_knowledge.save_memory(
  'relationship',
  'App-Settings System-Abhaengigkeiten',
  $$ABHAENGIGKEITEN des Per-App Settings Systems:

DATENBANK:
- schema/39-app-settings.sql haengt ab von dbai_ui.apps (muss existieren)
- schema/40-app-settings-seed.sql haengt ab von schema/39 UND allen App-Eintraegen in dbai_ui.apps
- RLS-Policies haengen ab von auth.uid() Funktion in dbai_core Schema

BACKEND:
- web/server.py Endpunkte haengen ab von db_query_rt/db_execute_rt/db_call_json_rt Helfern
- Session-Authentifizierung: get_current_session() -> session["user"]["id"]

FRONTEND:
- useAppSettings.js haengt ab von api.js (appSettings, appSettingsUpdate, etc.)
- AppSettingsPanel.jsx eigenstaendig, braucht nur settings, schema, onUpdate Props
- Jede App-Komponente importiert useAppSettings + AppSettingsPanel
- Settings.jsx AllAppSettingsTab nutzt api.allAppSettings() + AppSettingsPanel

BEKANNTE ABHAENGIGKEIT:
- sql-explorer und web-frame hatten keine Eintraege in dbai_ui.apps
- Diese mussten manuell eingefuegt werden bevor Settings-Seed moeglich war$$,
  75,
  ARRAY['abhaengigkeiten', 'dependencies', 'settings', 'system'],
  '0.9.0'
);

SELECT dbai_knowledge.save_memory(
  'operational',
  'App-Settings Deployment und Wartung',
  $$DEPLOYMENT-HINWEISE fuer das App-Settings System:

SCHEMA ANWENDEN:
  sudo docker exec -i dbai-postgres psql -U dbai_system -d dbai < schema/39-app-settings.sql
  sudo docker exec -i dbai-postgres psql -U dbai_system -d dbai < schema/40-app-settings-seed.sql

NEUES SETTING HINZUFUEGEN (ohne Frontend-Aenderung!):
  UPDATE dbai_ui.apps SET
    default_settings = default_settings || '{"newKey": "defaultVal"}'::jsonb,
    settings_schema = settings_schema || '{"newKey": {"type":"string","label":"Neu","group":"Allgemein"}}'::jsonb
  WHERE app_id = 'meine-app';

DEBUGGING:
  SELECT * FROM dbai_ui.get_all_app_settings('user-uuid');
  SELECT * FROM dbai_ui.app_user_settings WHERE user_id = '...';
  SELECT settings_schema FROM dbai_ui.apps WHERE app_id = 'terminal';

BACKUP: app_user_settings wird durch regulaeres pg_dump erfasst.$$,
  80,
  ARRAY['deployment', 'wartung', 'operational', 'debugging', 'settings'],
  '0.9.0'
);

SELECT dbai_knowledge.save_memory(
  'convention',
  'API-Endpunkte Pattern in server.py',
  $$API-ENDPUNKTE KONVENTION in web/server.py:

AUTHENTIFIZIERUNG:
  session = await get_current_session(request)
  user_id = session["user"]["id"]

DB-ZUGRIFF (3 Helfer):
  db_query_rt(sql, params) -> List[dict]  (SELECT, mehrere Zeilen)
  db_execute_rt(sql, params) -> None       (INSERT/UPDATE/DELETE)
  db_call_json_rt(func, params) -> dict    (Funktion die JSON zurueckgibt)

RESPONSE-FORMAT:
  return JSONResponse({"data": result})      Erfolg
  return JSONResponse({"error": msg}, 500)   Fehler

NEUE SETTINGS-ENDPUNKTE:
  @app.get("/api/apps/{app_id}/settings")
  @app.patch("/api/apps/{app_id}/settings")
  @app.delete("/api/apps/{app_id}/settings")
  @app.get("/api/apps/{app_id}/settings/schema")
  @app.get("/api/apps/settings/all")$$,
  70,
  ARRAY['convention', 'api', 'server-py', 'endpunkte', 'authentifizierung'],
  '0.9.0'
);

SELECT dbai_knowledge.save_memory(
  'inventory',
  'Frontend Dateistruktur und Imports',
  $$FRONTEND DATEISTRUKTUR:

frontend/src/
  api.js                     - API-Client (fetch-Wrapper)
  hooks/
    useAppSettings.js        - Settings Hook (NEU v0.9.0)
  components/
    AppSettingsPanel.jsx     - Generische Settings UI (NEU v0.9.0)
    apps/
      SystemMonitor.jsx      - refreshInterval, warningThreshold
      Terminal.jsx           - fontSize, fontFamily, scrollbackLines
      GhostManager.jsx       - autoRefresh, refreshInterval
      EventViewer.jsx        - maxEvents, refreshInterval
      ProcessManager.jsx     - refreshInterval, defaultSort
      HealthDashboard.jsx    - autoRefreshInterval, showScoreBanner
      SQLConsole.jsx         - maxHistory, fontSize
      FileBrowser.jsx        - rows_per_page, default_schema
      KnowledgeBase.jsx      - defaultTab, autoScan
      ErrorAnalyzer.jsx      - autoRefresh, severityFilter
      GhostChat.jsx          - fontSize, maxMessages (sep. Button)
      SoftwareStore.jsx      - defaultTab, showRecommendations
      OpenClawIntegrator.jsx - defaultTab, autoRefresh
      SQLExplorer.jsx        - rowsPerPage, showNullAs
      WebFrame.jsx           - defaultUrl, loadTimeout
      LLMManager.jsx         - defaultTab, gpuMonitoringInterval
      Settings.jsx           - AllAppSettingsTab (zentrale Verwaltung)$$,
  75,
  ARRAY['frontend', 'dateistruktur', 'komponenten', 'inventar'],
  '0.9.0'
);

SELECT dbai_knowledge.save_memory(
  'operational',
  'PostgreSQL Docker-Zugang',
  $$POSTGRESQL DOCKER-ZUGANG:

PostgreSQL laeuft NUR im Docker-Container, NICHT lokal.
Der docker-proxy belegt Port 5432 auf dem Host.

ZUGANG:
  sudo docker exec dbai-postgres psql -U dbai_system -d dbai
  sudo docker exec dbai-postgres psql -U dbai_system -d dbai -c "SQL"
  sudo docker exec -i dbai-postgres psql -U dbai_system -d dbai < datei.sql

CONTAINER:
  dbai-postgres     -> PostgreSQL 16 (Port 5432)
  dbai-ghost-api    -> FastAPI Backend (Port 3000)
  dbai-dashboard-ui -> Vite/React Frontend (Port 5173)

WICHTIG: psql lokal funktioniert NICHT (Connection refused).
Immer ueber docker exec zugreifen.$$,
  95,
  ARRAY['docker', 'postgresql', 'zugang', 'container', 'operational'],
  '0.1.0'
);

SELECT dbai_knowledge.save_memory(
  'identity',
  'DBAI v0.9.0 Feature-Stand',
  $$DBAI v0.9.0 FEATURE-STAND:

Das System ist ein autonomes, datenbankzentriertes Linux-Desktop-OS mit:
- Ghost AI System (KI-Modelle, Autonomie, Chat)
- 19 Desktop-Applikationen (alle mit Per-App Settings ab v0.9.0)
- PostgreSQL 16 als zentrale Datenhaltung (Schemas: dbai_core, dbai_ui,
  dbai_knowledge, dbai_journal, dbai_vector, dbai_llm, dbai_system,
  dbai_ghost, dbai_hardware, dbai_cicd)
- Self-Healing System (Health Checks, Error Patterns, Runbooks)
- Knowledge Management (System Memory, Module Registry, Changelog, ADRs)
- Vektorsuche (pgvector, HNSW-Index, 1536d Embeddings)
- OpenClaw Integration (Hardware-Gateway)
- LLM Provider Management (Ollama, OpenAI, etc.)
- CI/CD und OTA-Update System
- Immutable Audit-Logging (WAL-Journal)

NEU in v0.9.0: Vollstaendiges Per-App Settings System mit JSON-Schema-UI.$$,
  100,
  ARRAY['identitaet', 'version', 'features', 'ueberblick'],
  '0.9.0'
);

-- ============================================================================
-- 5. MODULE REGISTRY  (neue Dateien registrieren)
-- ============================================================================

INSERT INTO dbai_knowledge.module_registry (
  file_path, category, language, description, documentation,
  provides, depends_on, version, status, is_critical
) VALUES
(
  'schema/39-app-settings.sql',
  'schema', 'sql',
  'Per-App Settings Infrastruktur: Tabelle app_user_settings, Spalten auf apps, Funktionen, RLS.',
  $$Erweitert dbai_ui.apps um default_settings und settings_schema. Erstellt dbai_ui.app_user_settings fuer User-Overrides. Server-Side Merge via COALESCE. RLS fuer Isolation.$$,
  ARRAY['dbai_ui.app_user_settings', 'dbai_ui.get_app_settings', 'dbai_ui.save_app_settings', 'dbai_ui.reset_app_settings', 'dbai_ui.get_all_app_settings'],
  ARRAY['schema/23-app-ecosystem.sql'],
  '1.0.0', 'active', true
),
(
  'schema/40-app-settings-seed.sql',
  'data', 'sql',
  'Seed-Daten: Default-Settings und Settings-Schemas fuer 16 Apps.',
  $$UPDATE-Statements fuer 16 Apps mit default_settings und settings_schema. Jedes Schema-Feld: type, label, group, description, default, min/max/step/options.$$,
  ARRAY['app-settings-defaults', 'app-settings-schemas'],
  ARRAY['schema/39-app-settings.sql'],
  '1.0.0', 'active', false
),
(
  'schema/41-knowledge-session-v0.9.0.sql',
  'documentation', 'sql',
  'Wissensdokumentation der v0.9.0 Session.',
  $$Dokumentiert Erkenntnisse, Entscheidungen und Details in Knowledge-Tabellen: agent_sessions, changelog, system_memory, module_registry, ADR, glossary, known_issues, build_log.$$,
  ARRAY['knowledge-v0.9.0-documentation'],
  ARRAY['schema/39-app-settings.sql', 'schema/40-app-settings-seed.sql'],
  '1.0.0', 'active', false
),
(
  'frontend/src/hooks/useAppSettings.js',
  'frontend', 'javascript',
  'React Custom Hook fuer Per-App Settings mit debounced auto-save.',
  $$Exportiert useAppSettings(appId). useEffect fuer Laden, useRef fuer debounce. Returns: settings, schema, loading, error, update, set, reset.$$,
  ARRAY['useAppSettings-hook'],
  ARRAY['frontend/src/api.js'],
  '1.0.0', 'active', true
),
(
  'frontend/src/components/AppSettingsPanel.jsx',
  'frontend', 'jsx',
  'Generische Schema-getriebene Settings-UI Komponente.',
  $$Props: settings, schema, onUpdate, onReset. Gruppiert nach group-Feld, Sidebar bei mehreren Gruppen. Typen: boolean->Toggle, number->Slider, select->Dropdown, string->Text, color->Picker.$$,
  ARRAY['AppSettingsPanel-component'],
  ARRAY['frontend/src/hooks/useAppSettings.js'],
  '1.0.0', 'active', true
)
ON CONFLICT (file_path) DO UPDATE SET
  description = EXCLUDED.description,
  documentation = EXCLUDED.documentation,
  provides = EXCLUDED.provides,
  depends_on = EXCLUDED.depends_on,
  version = EXCLUDED.version,
  updated_at = NOW();

-- ============================================================================
-- 6. ARCHITECTURE DECISION RECORD
-- ============================================================================

INSERT INTO dbai_knowledge.architecture_decisions (
  title, status, context, decision, consequences, alternatives, decided_by
) VALUES (
  'JSON-Schema-getriebenes Per-App Settings System',
  'accepted',
  $$Alle 19 registrierten Apps in DBAI hatten keine individuellen Einstellungsmoeglichkeiten. Benutzer konnten weder Refresh-Intervalle, Schriftgroessen, Standard-Tabs noch andere App-spezifische Praeferenzen konfigurieren. Jede App haette eigene Settings-Logik und UI-Formulare benoetigt = massive Code-Duplikation.$$,
  $$Generisches JSON-Schema-getriebenes Settings-System: (1) Jede App definiert settings_schema in DB mit Typen, Validierung, UI-Gruppierung. (2) React-Hook useAppSettings handhabt Laden/Speichern/Debouncing. (3) AppSettingsPanel rendert automatisch Controls aus Schema. (4) Server-Side Merge: Defaults || User-Overrides via JSONB-Operator. (5) Neue Settings brauchen NUR DB-UPDATE, kein Frontend-Deployment.$$,
  $$POSITIV: Zero-Code Erweiterung, konsistente UI, automatische Validierung, zentrale Verwaltung, RLS-Isolation. NEGATIV: Schema-Format muss gelernt werden, komplexe verschachtelte Settings nicht abgedeckt, 500ms Debounce-Verzoegerung.$$,
  '[{"name":"Hardcoded Forms pro App","reason_rejected":"Massive Code-Duplikation"},{"name":"Zentrale Settings ohne App-Integration","reason_rejected":"Nicht kontextuell verfuegbar"},{"name":"LocalStorage Settings","reason_rejected":"Keine Synchronisation, kein Backup, kein RLS"},{"name":"GraphQL API","reason_rejected":"Overengineered fuer Use-Case"}]'::jsonb,
  'copilot-agent'
)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 7. SYSTEM GLOSSARY
-- ============================================================================

INSERT INTO dbai_knowledge.system_glossary (term, definition, context, examples, related_terms)
VALUES
(
  'Per-App Settings',
  'System zur individuellen Konfiguration jeder Desktop-App. JSON-Schema UI + Server-Side Merge.',
  'DBAI Desktop, dbai_ui Schema',
  ARRAY['useAppSettings("terminal") -> { settings: {fontSize:14}, schema: {fontSize:{type:"number"}} }'],
  ARRAY['Settings Schema', 'App User Settings', 'Server-Side Merge']
),
(
  'Settings Schema',
  $$JSON-Objekt pro Setting-Key mit Typ, Label, Gruppe, Beschreibung, Validierung. In dbai_ui.apps.settings_schema gespeichert.$$,
  'dbai_ui.apps.settings_schema',
  ARRAY['{"fontSize":{"type":"number","label":"Schriftgroesse","min":8,"max":32}}'],
  ARRAY['Per-App Settings', 'JSON Schema', 'AppSettingsPanel']
),
(
  'Server-Side Merge',
  $$Default-Einstellungen werden auf dem Server mit User-Overrides zusammengefuehrt: default_settings || COALESCE(user_settings, '{}'::jsonb).$$,
  'dbai_ui.get_app_settings()',
  ARRAY['defaults {"a":1,"b":2} + overrides {"b":3} = merged {"a":1,"b":3}'],
  ARRAY['Per-App Settings', 'JSONB Merge', 'COALESCE']
),
(
  'Debounced Save',
  'Speichervorgaenge werden 500ms verzoegert um API-Aufrufe zu reduzieren. Timer wird bei jeder Aenderung zurueckgesetzt.',
  'useAppSettings.js Hook',
  ARRAY['User aendert Slider 5x schnell -> nur 1 API-Call nach 500ms Pause'],
  ARRAY['useAppSettings', 'Auto-Save', 'Performance']
),
(
  'AppSettingsPanel',
  'Generische React-Komponente: JSON-Schema -> Settings-Formular. 5 Typen: boolean, number, select, string, color.',
  'frontend/src/components/AppSettingsPanel.jsx',
  ARRAY['<AppSettingsPanel settings={s} schema={sc} onUpdate={fn} onReset={fn} />'],
  ARRAY['Per-App Settings', 'Settings Schema', 'Schema-Driven UI']
)
ON CONFLICT (term) DO UPDATE SET
  definition = EXCLUDED.definition,
  context = EXCLUDED.context,
  examples = EXCLUDED.examples,
  related_terms = EXCLUDED.related_terms;

-- ============================================================================
-- 8. KNOWN ISSUES
-- ============================================================================

INSERT INTO dbai_knowledge.known_issues (
  title, description, severity, status,
  affected_files, workaround, resolution
) VALUES
(
  'sql-explorer und web-frame fehlten in dbai_ui.apps',
  $$schema/29-new-apps-registration.sql referenzierte nicht existierende status-Spalte. INSERTs schlugen fehl. Settings-Seed konnte erst nach manuellem Insert greifen.$$,
  'medium', 'resolved',
  ARRAY['schema/29-new-apps-registration.sql', 'schema/40-app-settings-seed.sql'],
  'Manueller INSERT in dbai_ui.apps mit korrekten Spalten.',
  'Apps manuell eingefuegt. Schema/29 sollte bei naechster Migration korrigiert werden.'
),
(
  'KnowledgeBase.jsx JSX-Fragment-Fehler',
  'JSX-Fragment-Mismatch durch verschachtelte ternaere Operatoren beim Settings-View.',
  'low', 'resolved',
  ARRAY['frontend/src/components/apps/KnowledgeBase.jsx'],
  NULL,
  'Bedingtes Rendering mit showSettings-Variable statt verschachtelter Ternaere.'
),
(
  'GhostChat doppelte Settings-Konzepte',
  $$GhostChat hatte bereits eigenes settings-View (roleInstructions, Modell). Neue Per-App Settings als separater Button, um Konflikte zu vermeiden. Sollte langfristig vereinheitlicht werden.$$,
  'low', 'workaround',
  ARRAY['frontend/src/components/apps/GhostChat.jsx'],
  'Separater Zahnrad-Button neben bestehendem Settings-Button.',
  NULL
)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 9. BUILD LOG
-- ============================================================================

INSERT INTO dbai_knowledge.build_log (
  build_type, success, description, system_info, completed_at
) VALUES (
  'schema_migration', true,
  'Per-App Settings: schema/39 + schema/40 angewendet. 16 Apps konfiguriert. 4 Funktionen, 3 RLS-Policies.',
  '{"schemas_applied":["schema/39-app-settings.sql","schema/40-app-settings-seed.sql"],"apps_configured":16,"functions_created":4,"rls_policies":3,"container":"dbai-postgres"}'::jsonb,
  NOW()
)
ON CONFLICT DO NOTHING;

COMMIT;
