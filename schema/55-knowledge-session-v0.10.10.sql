-- ==========================================================================
-- DBAI Knowledge Session — v0.10.10 (Optional Chaining Null-Safety Fix)
-- Datum: 2026-03-17
-- ==========================================================================

-- Changelog
INSERT INTO dbai_knowledge.changelog (version, change_type, title, description, affected_files, author)
VALUES
('0.10.10', 'fix', 'Settings Null-Safety: settings.xxx → settings?.xxx in 8 Apps',
 'Root Cause: useAppSettings() gibt settings=null zurück solange die DB-Abfrage läuft. Alle Apps die sofort settings.xxx (ohne Optional Chaining) im Initialisierungscode nutzen, crashten mit "TypeError: null is not an object". Fix: Alle 8 betroffenen Komponenten auf settings?.xxx mit Fallback-Werten umgestellt.

Betroffene Apps und Felder:
• SystemMonitor: refresh_interval, warning_threshold, critical_threshold
• GhostManager: default_tab, refresh_interval, show_fitness_score, auto_refresh
• EventViewer: max_events, refresh_interval
• FileBrowser: rows_per_page (2 Stellen)
• HealthDashboard: default_tab, auto_refresh_interval, show_fix_hints, show_score_banner
• KnowledgeBase: default_tab
• OpenClawIntegrator: default_tab
• ProcessManager: default_sort, refresh_interval

Pattern: settings.xxx ?? default → settings?.xxx ?? default
Pattern: settings.xxx || default → settings?.xxx || default
Pattern: settings.xxx !== false → settings?.xxx !== false',
 ARRAY[
   'frontend/src/components/apps/SystemMonitor.jsx',
   'frontend/src/components/apps/GhostManager.jsx',
   'frontend/src/components/apps/EventViewer.jsx',
   'frontend/src/components/apps/FileBrowser.jsx',
   'frontend/src/components/apps/HealthDashboard.jsx',
   'frontend/src/components/apps/KnowledgeBase.jsx',
   'frontend/src/components/apps/OpenClawIntegrator.jsx',
   'frontend/src/components/apps/ProcessManager.jsx'
 ],
 'ghost-agent')
ON CONFLICT DO NOTHING;

-- System Memory — Convention
INSERT INTO dbai_knowledge.system_memory (category, title, content, tags, author)
VALUES
('convention', 'useAppSettings: IMMER Optional Chaining verwenden',
 'KONVENTION: Bei Verwendung von useAppSettings() MUSS auf settings-Properties IMMER mit Optional Chaining zugegriffen werden:

FALSCH: settings.refresh_interval ?? 5000
RICHTIG: settings?.refresh_interval ?? 5000

FALSCH: settings.default_tab || "overview"
RICHTIG: settings?.default_tab || "overview"

Grund: useAppSettings() gibt settings=null zurück während die DB-Abfrage läuft (async). Ohne ?. crasht die Komponente sofort beim ersten Render mit TypeError.

Alternative: Guard mit if (sLoading) return <Loading/> VOR dem Zugriff auf settings — aber Optional Chaining ist robuster und weniger Code.',
 ARRAY['useAppSettings','optional-chaining','null-safety','convention','frontend'],
 'ghost-agent')
ON CONFLICT DO NOTHING;

-- Error Pattern
INSERT INTO dbai_knowledge.error_patterns (name, title, error_regex, error_source, severity, category, description, root_cause, solution_short)
VALUES
('settings_null_crash', 'useAppSettings settings=null TypeError',
 'null is not an object.*settings\.|Cannot read properties of null.*settings',
 'runtime', 'high', 'missing_dependency',
 'App-Komponente crasht beim Start mit TypeError weil settings noch null ist.',
 'useAppSettings() lädt settings asynchron aus der DB. Beim ersten Render ist settings=null. Direkter Property-Zugriff ohne ?. crasht sofort.',
 'settings.xxx → settings?.xxx mit Fallback-Wert (??/||)')
ON CONFLICT (name) DO NOTHING;

-- Build Log
INSERT INTO dbai_knowledge.build_log (build_type, success, duration_ms, description)
VALUES
('hotfix', true, 800,
 'v0.10.10: Optional Chaining Fix in 8 App-Komponenten. settings.xxx → settings?.xxx. Verhindert TypeError-Crashes beim App-Start.')
ON CONFLICT DO NOTHING;

-- Agent Session
INSERT INTO dbai_knowledge.agent_sessions (version_start, version_end, summary, files_created, files_modified, schemas_added, goals, decisions)
VALUES
('0.10.10', '0.10.10',
 'Null-Safety Fix für useAppSettings in 8 Frontend-Komponenten. Alle settings.xxx Zugriffe auf settings?.xxx umgestellt um TypeError-Crashes zu verhindern wenn die DB-Abfrage noch läuft.',
 ARRAY['schema/55-knowledge-session-v0.10.10.sql'],
 ARRAY[
   'frontend/src/components/apps/SystemMonitor.jsx',
   'frontend/src/components/apps/GhostManager.jsx',
   'frontend/src/components/apps/EventViewer.jsx',
   'frontend/src/components/apps/FileBrowser.jsx',
   'frontend/src/components/apps/HealthDashboard.jsx',
   'frontend/src/components/apps/KnowledgeBase.jsx',
   'frontend/src/components/apps/OpenClawIntegrator.jsx',
   'frontend/src/components/apps/ProcessManager.jsx'
 ],
 ARRAY['schema/55-knowledge-session-v0.10.10.sql'],
 ARRAY['8 App-Komponenten Null-Safety fixen','Convention für useAppSettings dokumentieren'],
 ARRAY['Optional Chaining statt Loading-Guard gewählt — weniger Code, gleiche Sicherheit']
)
ON CONFLICT DO NOTHING;

-- Known Issue (resolved)
INSERT INTO dbai_knowledge.known_issues (title, description, severity, status, affected_files, workaround, resolution)
VALUES
('8 Apps crashen beim Öffnen — settings ist null',
 'useAppSettings() gibt settings=null zurück während die DB-Abfrage läuft. Alle Apps die sofort settings.xxx ohne ?. nutzen crashen mit "TypeError: null is not an object (evaluating settings.xxx)". Betroffen: SystemMonitor, GhostManager, EventViewer, FileBrowser, HealthDashboard, KnowledgeBase, OpenClawIntegrator, ProcessManager.',
 'critical', 'resolved',
 ARRAY[
   'frontend/src/components/apps/SystemMonitor.jsx',
   'frontend/src/components/apps/GhostManager.jsx',
   'frontend/src/components/apps/EventViewer.jsx',
   'frontend/src/components/apps/FileBrowser.jsx',
   'frontend/src/components/apps/HealthDashboard.jsx',
   'frontend/src/components/apps/KnowledgeBase.jsx',
   'frontend/src/components/apps/OpenClawIntegrator.jsx',
   'frontend/src/components/apps/ProcessManager.jsx'
 ],
 'Keine — App crasht sofort',
 'Alle settings.xxx Zugriffe auf settings?.xxx mit Fallback-Werten umgestellt (v0.10.10)')
ON CONFLICT DO NOTHING;
