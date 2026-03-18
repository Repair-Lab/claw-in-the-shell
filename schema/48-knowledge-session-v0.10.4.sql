-- ═══════════════════════════════════════════════════════════════
-- DBAI v0.10.4 — Standfester useAppSettings Export-Fix
-- Datum: 2026-03-17
-- ═══════════════════════════════════════════════════════════════

BEGIN;

-- ── Changelog ──
INSERT INTO dbai_knowledge.changelog (version, change_type, title, description, affected_files, author)
VALUES
('0.10.4', 'fix', 'useAppSettings: Default Export hinzugefügt (standfester Fix)',
 'useAppSettings.js hatte nur einen Named Export (export function useAppSettings). Jeder Code der import useAppSettings from "..." verwendete (Default Import) brach mit "No matching export for import default". Jetzt exportiert die Datei BEIDES: Named + Default Export. Beide Import-Varianten funktionieren dauerhaft.',
 ARRAY['frontend/src/hooks/useAppSettings.js'], 'ghost-agent'),
('0.10.4', 'fix', 'Verschachtelte Duplikate in components/apps/ gelöscht',
 'docker cp hatte bei früherer Wiederherstellung (v0.10.3) einen rekursiv verschachtelten frontend/src/components/apps/frontend/...-Ordner erzeugt (67MB). Dieser wurde gelöscht.',
 ARRAY['frontend/src/components/apps/'], 'ghost-agent')
ON CONFLICT DO NOTHING;

-- ── System Memory ──
INSERT INTO dbai_knowledge.system_memory (category, title, content, tags, author)
VALUES
('convention', 'useAppSettings Export-Muster',
 'useAppSettings.js exportiert BEIDES: Named (export function useAppSettings) UND Default (export default useAppSettings). Damit funktionieren import { useAppSettings } from ... UND import useAppSettings from ... gleichermaßen. Identisches Muster wie useKeyboardShortcuts.js.',
 ARRAY['useAppSettings', 'import', 'export', 'default', 'named'], 'ghost-agent'),
('operational', 'docker cp erzeugt verschachtelte Duplikate',
 'docker cp kann rekursive Verschachtelungen erzeugen wenn das Zielverzeichnis existiert (apps/frontend/src/components/apps/frontend/...). Nach docker cp immer prüfen: find <dir> -mindepth 1 -maxdepth 1 -type d -name frontend. Duplikate sofort löschen.',
 ARRAY['docker', 'cp', 'duplikate', 'verschachtelt'], 'ghost-agent')
ON CONFLICT DO NOTHING;

-- ── Build Log ──
INSERT INTO dbai_knowledge.build_log (build_type, success, duration_ms, description)
VALUES
('upgrade', true, 8000,
 'Default Export zu useAppSettings.js hinzugefügt. 67MB verschachtelte Duplikate aus docker cp gelöscht. Vite kompiliert fehlerfrei. HTTP 200.')
ON CONFLICT DO NOTHING;

-- ── Agent Session ──
INSERT INTO dbai_knowledge.agent_sessions (version_start, version_end, summary, files_modified, goals, decisions)
VALUES
('0.10.3', '0.10.4',
 'Standfester Fix: useAppSettings exportiert jetzt Named + Default. Verschachtelte Duplikate (67MB) gelöscht. Problem kann nicht mehr auftreten egal welche Import-Variante verwendet wird.',
 ARRAY['frontend/src/hooks/useAppSettings.js'],
 ARRAY['Schwarzen Bildschirm beheben', 'Fehler standfest fixen dass er nicht wiederkommt'],
 ARRAY['Default Export hinzugefügt statt alle Imports zu ändern — robuster', 'Gleiche Pattern wie useKeyboardShortcuts.js'])
ON CONFLICT DO NOTHING;

-- ── Known Issue (aktualisiert) ──
INSERT INTO dbai_knowledge.known_issues (title, description, severity, status, affected_files, workaround, resolution, resolution_date)
VALUES
('useAppSettings fehlender Default Export verursacht schwarzen Bildschirm',
 'useAppSettings.js hatte nur export function (Named Export). Code der import useAppSettings from "..." (Default Import) verwendet, bekommt undefined und die App rendert nicht → schwarzer Bildschirm. Trat in v0.10.2 auf (13 Dateien), wurde damals per Import-Fix behoben, trat erneut in v0.10.4 auf nach Container-Wiederherstellung.',
 'high', 'resolved',
 ARRAY['frontend/src/hooks/useAppSettings.js'],
 'Alle Imports auf Named Import { useAppSettings } ändern',
 'Standfester Fix: Default Export (export default useAppSettings) zur Datei hinzugefügt. Beide Import-Varianten funktionieren jetzt dauerhaft.',
 now())
ON CONFLICT DO NOTHING;

-- ── Error Pattern (neues Muster registriert) ──
INSERT INTO dbai_knowledge.error_patterns (name, title, error_regex, error_source, severity, category, affected_component, description, root_cause, solution_short, solution_detail, can_auto_fix, auto_fix_shell, tags)
VALUES
('js_missing_default_export', 'No matching export for import "default"',
 'No matching export in ".*" for import "default"',
 'compile', 'high', 'missing_dependency',
 'frontend/src/hooks/useAppSettings.js',
 'Vite/esbuild Kompilierfehler: Eine JS-Datei wird mit Default Import (import X from "...") importiert aber hat keinen Default Export.',
 'Die Quelldatei exportiert nur Named Exports (export function X) ohne Default Export (export default X). Default Import bekommt undefined.',
 'export default <functionName> am Ende der fehlenden Datei hinzufügen.',
 'Beide Export-Varianten bereitstellen: Named (export function X) UND Default (export default X). Damit funktionieren BEIDE Import-Muster. Siehe useKeyboardShortcuts.js als Vorbild.',
 true,
 'grep -rn "export function" <FILE> | head -1 && echo "export default <FUNCTION>" >> <FILE>',
 ARRAY['vite', 'esbuild', 'import', 'export', 'default', 'named', 'javascript', 'frontend', 'black-screen'])
ON CONFLICT (name) DO UPDATE SET
  occurrence_count = dbai_knowledge.error_patterns.occurrence_count + 1,
  last_occurred = now(),
  updated_at = now();

COMMIT;
