-- ═══════════════════════════════════════════════════════════════
-- DBAI v0.10.5 — Desktop.jsx fehlende Imports + Error Boundary + api.js 401-Fix
-- Datum: 2026-03-17
-- ═══════════════════════════════════════════════════════════════

BEGIN;

-- ── Changelog ──
INSERT INTO dbai_knowledge.changelog (version, change_type, title, description, affected_files, author)
VALUES
('0.10.5', 'fix', 'Desktop.jsx: fehlende Imports für useKeyboardShortcuts und SpotlightSearch',
 'Desktop.jsx verwendete useKeyboardShortcuts (Zeile 102) und SpotlightSearch (Zeile 704) ohne Import-Deklaration. Beim Rendern des Desktops warf dies sofort ReferenceError → React unmountete komplett → schwarzer Bildschirm. Die Imports fehlten nach der docker cp Wiederherstellung in v0.10.3, da die Originaldatei im Container diese Imports nicht hatte (sie wurden beim initialen Build entfernt).',
 ARRAY['frontend/src/components/Desktop.jsx'], 'ghost-agent'),
('0.10.5', 'feature', 'Error Boundary für Runtime-Crashes statt schwarzer Bildschirm',
 'React Error Boundary in App.jsx hinzugefügt. Wenn eine Komponente crasht, wird jetzt ein Fehlerbild mit Stack-Trace angezeigt statt schwarzer Bildschirm. Button zum Neuladen. Console.error mit vollem Component Stack.',
 ARRAY['frontend/src/App.jsx'], 'ghost-agent'),
('0.10.5', 'fix', 'api.js: window.location.reload() bei 401 entfernt',
 'Bei 401-Antworten hat api.js bisher window.location.reload() aufgerufen, was Flash-Reload-Zyklen verursachte wenn ein staler Token vorhanden war. Jetzt wird nur der Token entfernt und der Fehler geworfen — App.jsx catch-Handler regelt den UI-Zustand sauber.',
 ARRAY['frontend/src/api.js'], 'ghost-agent')
ON CONFLICT DO NOTHING;

-- ── System Memory ──
INSERT INTO dbai_knowledge.system_memory (category, title, content, tags, author)
VALUES
('convention', 'Desktop.jsx benötigt useKeyboardShortcuts + SpotlightSearch Imports',
 'Desktop.jsx importiert useKeyboardShortcuts aus ../hooks/useKeyboardShortcuts (Default Import) und SpotlightSearch aus ./SpotlightSearch (Default Import). Diese Imports MÜSSEN vorhanden sein, da beide direkt im Render verwendet werden. Bei Recovery via docker cp IMMER prüfen ob alle Imports korrekt sind.',
 ARRAY['desktop', 'import', 'useKeyboardShortcuts', 'SpotlightSearch'], 'ghost-agent'),
('architecture', 'Error Boundary in App.jsx',
 'App.jsx hat jetzt eine ErrorBoundary-Klasse (React class component mit getDerivedStateFromError und componentDidCatch). Wraps den gesamten Render-Tree. Bei Runtime-Crashes wird ein roter Fehler-Screen mit Stack-Trace und Reload-Button angezeigt statt schwarzer Bildschirm. Dadurch ist jeder zukünftige Crash sofort sichtbar und debuggbar.',
 ARRAY['error-boundary', 'react', 'crash', 'debug'], 'ghost-agent'),
('convention', 'api.js darf KEIN window.location.reload() bei 401 machen',
 'Bei 401-Responses nur Token entfernen (localStorage.removeItem) und Error werfen. Die aufrufende Komponente (App.jsx useEffect .catch) handhabt den UI-Zustandswechsel zurück zu Login. window.location.reload() verursacht Flash-Loops besonders wenn mehrere API-Calls gleichzeitig 401 bekommen.',
 ARRAY['api', '401', 'reload', 'token', 'auth'], 'ghost-agent')
ON CONFLICT DO NOTHING;

-- ── Build Log ──
INSERT INTO dbai_knowledge.build_log (build_type, success, duration_ms, description)
VALUES
('upgrade', true, 15000,
 'v0.10.5: 2 fehlende Imports in Desktop.jsx hinzugefügt (useKeyboardShortcuts, SpotlightSearch). Error Boundary in App.jsx. window.location.reload() aus api.js entfernt. Vite kompiliert fehlerfrei, HTTP 200.')
ON CONFLICT DO NOTHING;

-- ── Agent Session ──
INSERT INTO dbai_knowledge.agent_sessions (version_start, version_end, summary, files_modified, goals, decisions)
VALUES
('0.10.4', '0.10.5',
 'Root-Cause des schwarzen Bildschirms nach Reload gefunden und behoben: Desktop.jsx hatte keine Import-Deklarationen für useKeyboardShortcuts und SpotlightSearch. Beim Rendern des Desktops warf dies ReferenceError → React Unmount → schwarz. Error Boundary hinzugefügt damit zukünftige Crashes sichtbar werden. api.js 401-Reload entfernt.',
 ARRAY['frontend/src/components/Desktop.jsx', 'frontend/src/App.jsx', 'frontend/src/api.js'],
 ARRAY['Schwarzen Bildschirm beim Neuladen beheben', 'Standfeste Lösung dass es nicht wieder passiert'],
 ARRAY['Error Boundary statt schwarzer Bildschirm', 'window.location.reload() entfernt — App-State-Management statt Page-Reload', 'Default Imports verwendet da beide Hooks/Komponenten Default Exports haben'])
ON CONFLICT DO NOTHING;

-- ── Known Issue (resolved) ──
INSERT INTO dbai_knowledge.known_issues (title, description, severity, status, affected_files, workaround, resolution, resolution_date)
VALUES
('Desktop.jsx fehlende Imports verursachen schwarzen Bildschirm',
 'Desktop.jsx hatte keine import-Deklarationen für useKeyboardShortcuts (Hook) und SpotlightSearch (Komponente), obwohl beide im Code verwendet werden. Die Dateien fehlten nach einer docker cp Wiederherstellung. Beim Rendern des Desktops (nach Login oder bei Reload mit gespeichertem Token) warf dies sofort einen ReferenceError. Da keine Error Boundary vorhanden war, mountete React den gesamten Komponentenbaum ab → schwarzer Bildschirm.',
 'critical', 'resolved',
 ARRAY['frontend/src/components/Desktop.jsx'],
 'Manuell die fehlenden Imports hinzufügen',
 'Imports für useKeyboardShortcuts und SpotlightSearch hinzugefügt. Error Boundary in App.jsx eingebaut damit zukünftige Crashes sichtbar werden statt schwarzer Bildschirm.',
 now())
ON CONFLICT DO NOTHING;

-- ── Error Pattern ──
INSERT INTO dbai_knowledge.error_patterns (name, title, error_regex, error_source, severity, category, affected_component, description, root_cause, solution_short, solution_detail, can_auto_fix, tags)
VALUES
('js_missing_import_reference_error', 'ReferenceError: X is not defined (fehlender Import)',
 'ReferenceError: .* is not defined',
 'runtime', 'critical', 'missing_dependency',
 'frontend/src/components/Desktop.jsx',
 'Eine Variable/Funktion wird im Code verwendet aber nie importiert. JavaScript wirft ReferenceError. Ohne Error Boundary crasht die gesamte React-App → schwarzer Bildschirm.',
 'Import-Deklaration fehlt im Datei-Header. Häufig nach docker cp Recovery wenn die wiederhergestellten Dateien nicht die neuesten waren.',
 'Fehlenden Import hinzufügen und Error Boundary für zukünftige Crashes einbauen.',
 'Alle verwendeten Bezeichner in einer Komponente gegen die Import-Liste prüfen. grep nach Funktionsaufrufen (use*) und JSX-Tags (<Component) die nicht in den Import-Zeilen vorkommen. Error Boundary wrappen.',
 true,
 ARRAY['import', 'reference-error', 'crash', 'black-screen', 'react', 'runtime'])
ON CONFLICT (name) DO UPDATE SET
  occurrence_count = dbai_knowledge.error_patterns.occurrence_count + 1,
  last_occurred = now(),
  updated_at = now();

COMMIT;
