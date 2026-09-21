-- =============================================================================
-- Migration 60: Version 0.12.0 — Prozess-Manager in System Monitor integriert
-- =============================================================================
-- Datum: 2026-03-17
-- Beschreibung:
--   - Prozess-Manager als eigenständige Desktop-App deaktiviert
--   - Funktionalität in System Monitor (Tab "Prozess-Manager") integriert
--   - System-Version auf 0.12.0 aktualisiert
--   - Ein Desktop-Icon weniger → aufgeräumterer Desktop
-- =============================================================================

BEGIN;

-- ─────────────────────────────────────────────────────────────────────────────
-- 1) Prozess-Manager App deaktivieren (bleibt als Datensatz erhalten)
-- ─────────────────────────────────────────────────────────────────────────────
UPDATE dbai_ui.apps
SET is_system  = FALSE,
    is_pinned  = FALSE,
    description = 'Integriert in System Monitor (Tab: Prozess-Manager). Standalone ab v0.12.0 deaktiviert.'
WHERE app_id = 'process-manager';

-- ─────────────────────────────────────────────────────────────────────────────
-- 2) System Monitor Beschreibung aktualisieren
-- ─────────────────────────────────────────────────────────────────────────────
UPDATE dbai_ui.apps
SET description = 'Live-Übersicht: CPU, RAM, Disk, Netzwerk, Prozesse, Health und Prozess-Manager. Aktualisiert sich per WebSocket.',
    default_width = 1100,
    default_height = 750
WHERE app_id = 'system-monitor';

-- ─────────────────────────────────────────────────────────────────────────────
-- 3) Changelog-Einträge
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO dbai_knowledge.changelog (version, change_type, title, description)
VALUES
  ('0.12.0', 'refactor', 'Prozess-Manager → System Monitor',
   'Prozess-Manager in System Monitor integriert — 4 Tabs: Übersicht, Prozesse, Health, Prozess-Manager. Desktop-Icon entfernt.'),
  ('0.12.0', 'refactor', 'Versions-Sync 0.12.0',
   'System-Version auf 0.12.0 aktualisiert: config/dbai.toml, web/server.py, frontend/package.json')
ON CONFLICT DO NOTHING;

-- ─────────────────────────────────────────────────────────────────────────────
-- 4) System-Memory Dokumentation
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO dbai_knowledge.system_memory (category, title, content, valid_from, tags)
VALUES
  ('roadmap', 'Version 0.12.0 veröffentlicht',
   'Prozess-Manager in System Monitor integriert. Versions-Sync über alle Komponenten (config, server, frontend). Ein Desktop-Icon weniger.',
   '0.12.0', ARRAY['version', 'release', '0.12.0']),
  ('architecture', 'ProcessManager → SystemMonitor Merge',
   'ProcessManager.jsx ist ab v0.12.0 ein Tab im SystemMonitor statt eigene Desktop-App. Desktop-Icon entfernt. SystemMonitor hat jetzt 4 Tabs: Übersicht, Prozesse, Health, Prozess-Manager.',
   '0.12.0', ARRAY['frontend', 'refactor', 'process-manager', 'system-monitor'])
ON CONFLICT DO NOTHING;

COMMIT;
