-- ============================================================================
-- DBAI Schema 56: Ghost Browser — KI-gesteuerter Chromium-Browser
-- Version: 0.11.0
-- Datum:   2026-03-17
-- ============================================================================
-- Ghost kann per Playwright/Chromium Webseiten aufrufen, navigieren,
-- Daten extrahieren und Ergebnis-Dateien generieren.
-- ============================================================================

SET search_path TO dbai_system, dbai_knowledge, dbai_ui, public;

-- ── Tabelle: Browser-Tasks ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dbai_system.ghost_browser_tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL,
    -- Auftragsbeschreibung
    prompt          TEXT NOT NULL,                          -- Was soll Ghost tun?
    task_type       TEXT NOT NULL DEFAULT 'research'
        CHECK (task_type IN ('research', 'screenshot', 'extract', 'form_fill', 'monitor', 'download')),
    -- Ziel-URL (optional, Ghost kann auch selbst googeln)
    target_url      TEXT,
    -- Status
    status          TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'paused', 'completed', 'failed', 'cancelled')),
    progress        INTEGER DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    -- Ergebnis
    result_type     TEXT CHECK (result_type IN ('markdown', 'json', 'pdf', 'screenshot', 'html', 'csv')),
    result_path     TEXT,                                  -- Dateipfad im DBAI-Filesystem
    result_summary  TEXT,                                  -- Kurzzusammenfassung
    result_data     JSONB,                                 -- Strukturierte Daten
    -- Browser-Session
    steps_log       JSONB DEFAULT '[]'::jsonb,             -- Chronologische Schritte
    screenshots     JSONB DEFAULT '[]'::jsonb,             -- Screenshot-Pfade je Schritt
    pages_visited   TEXT[] DEFAULT '{}',                   -- Besuchte URLs
    cookies_used    BOOLEAN DEFAULT false,
    -- Sicherheit
    approved_by     UUID,                                  -- Wer hat den Task freigegeben?
    approved_at     TIMESTAMPTZ,
    sandbox_mode    BOOLEAN DEFAULT true,                  -- Kein Login auf externen Seiten
    max_pages       INTEGER DEFAULT 10,                    -- Max besuchte Seiten
    max_duration_s  INTEGER DEFAULT 120,                   -- Max Laufzeit in Sekunden
    -- Timestamps
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    error_message   TEXT
);

-- ── Tabelle: Browser-Step-Log (detailliert) ─────────────────────────────────
CREATE TABLE IF NOT EXISTS dbai_system.ghost_browser_steps (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id         UUID NOT NULL REFERENCES dbai_system.ghost_browser_tasks(id) ON DELETE CASCADE,
    step_number     INTEGER NOT NULL,
    action          TEXT NOT NULL
        CHECK (action IN ('navigate', 'click', 'type', 'scroll', 'wait', 'screenshot',
                          'extract', 'evaluate', 'download', 'back', 'forward', 'close')),
    selector        TEXT,                                  -- CSS/XPath Selektor
    value           TEXT,                                  -- Eingabewert / URL
    page_url        TEXT,                                  -- Aktuelle Seite
    page_title      TEXT,                                  -- Seitentitel
    screenshot_path TEXT,                                  -- Screenshot nach dem Schritt
    result_data     JSONB,                                 -- Extrahierte Daten
    duration_ms     INTEGER,                               -- Dauer des Schritts
    success         BOOLEAN DEFAULT true,
    error_message   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Tabelle: Browser-Presets (gespeicherte Workflows) ───────────────────────
CREATE TABLE IF NOT EXISTS dbai_system.ghost_browser_presets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL UNIQUE,
    description     TEXT,
    task_type       TEXT NOT NULL DEFAULT 'research',
    prompt_template TEXT NOT NULL,                         -- Prompt mit {variables}
    default_url     TEXT,
    max_pages       INTEGER DEFAULT 10,
    max_duration_s  INTEGER DEFAULT 120,
    output_format   TEXT DEFAULT 'markdown',
    icon            TEXT DEFAULT '🌐',
    is_system       BOOLEAN DEFAULT false,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Indizes ─────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_ghost_browser_tasks_status
    ON dbai_system.ghost_browser_tasks (status);
CREATE INDEX IF NOT EXISTS idx_ghost_browser_tasks_user
    ON dbai_system.ghost_browser_tasks (user_id);
CREATE INDEX IF NOT EXISTS idx_ghost_browser_tasks_created
    ON dbai_system.ghost_browser_tasks (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ghost_browser_steps_task
    ON dbai_system.ghost_browser_steps (task_id, step_number);

-- ── Permissions ─────────────────────────────────────────────────────────────
GRANT ALL ON dbai_system.ghost_browser_tasks TO dbai_runtime;
GRANT ALL ON dbai_system.ghost_browser_steps TO dbai_runtime;
GRANT ALL ON dbai_system.ghost_browser_presets TO dbai_runtime;

-- ── Seed: Voreingestellte Presets ───────────────────────────────────────────
INSERT INTO dbai_system.ghost_browser_presets (name, description, task_type, prompt_template, default_url, max_pages, output_format, icon, is_system)
VALUES
  ('web_research', 'Thema recherchieren und Zusammenfassung erstellen',
   'research', 'Recherchiere zum Thema: {topic}. Besuche die Top-Ergebnisse, extrahiere die wichtigsten Informationen und erstelle eine strukturierte Zusammenfassung als Markdown-Datei.',
   'https://www.google.com', 8, 'markdown', '🔍', true),

  ('screenshot_page', 'Screenshot einer Webseite erstellen',
   'screenshot', 'Öffne die URL {url} und erstelle einen Full-Page-Screenshot.',
   NULL, 1, 'screenshot', '📸', true),

  ('price_compare', 'Preisvergleich für ein Produkt',
   'research', 'Suche nach "{product}" und vergleiche die Preise auf verschiedenen Shops. Erstelle eine Vergleichstabelle mit Preis, Shop, Link und Verfügbarkeit.',
   'https://www.google.com', 10, 'markdown', '💰', true),

  ('extract_data', 'Daten von einer Webseite extrahieren',
   'extract', 'Extrahiere alle {data_type} von der Seite {url}. Gib die Daten als strukturierte JSON/CSV-Datei zurück.',
   NULL, 3, 'json', '📊', true),

  ('news_digest', 'Nachrichten-Digest zu einem Thema',
   'research', 'Suche aktuelle Nachrichten zum Thema: {topic}. Sammle die 5 wichtigsten Artikel, extrahiere Titel, Quelle, Datum und eine Zusammenfassung. Erstelle einen News-Digest.',
   'https://news.google.com', 8, 'markdown', '📰', true)
ON CONFLICT (name) DO NOTHING;

-- ── App-Registrierung ───────────────────────────────────────────────────────
INSERT INTO dbai_ui.apps (
    app_id, name, description, icon, category,
    source_type, source_target, is_system, is_pinned,
    default_width, default_height, min_width, min_height,
    sort_order, default_settings, settings_schema
) VALUES (
    'ghost-browser',
    'Ghost Browser',
    'KI-gesteuerter Chromium-Browser — Ghost recherchiert, extrahiert Daten und erstellt Dateien',
    '🤖',
    'ai',
    'component', 'GhostBrowser',
    false, false,
    1100, 750, 800, 500,
    15,
    '{"default_tab": "tasks", "max_pages": 10, "max_duration": 120, "sandbox_mode": true, "auto_screenshot": true, "output_format": "markdown"}'::jsonb,
    '{"fields": [
        {"key": "default_tab", "label": "Standard-Tab", "type": "select", "options": ["tasks", "presets", "history"]},
        {"key": "max_pages", "label": "Max. Seiten pro Auftrag", "type": "number", "min": 1, "max": 50},
        {"key": "max_duration", "label": "Max. Dauer (Sekunden)", "type": "number", "min": 30, "max": 600},
        {"key": "sandbox_mode", "label": "Sandbox-Modus (kein Login)", "type": "boolean"},
        {"key": "auto_screenshot", "label": "Auto-Screenshots", "type": "boolean"},
        {"key": "output_format", "label": "Standard-Ausgabeformat", "type": "select", "options": ["markdown", "json", "csv", "html"]}
    ]}'::jsonb
) ON CONFLICT (app_id) DO UPDATE SET
    description = EXCLUDED.description,
    default_settings = EXCLUDED.default_settings,
    settings_schema = EXCLUDED.settings_schema;

-- ── Changelog ───────────────────────────────────────────────────────────────
INSERT INTO dbai_knowledge.changelog (version, change_type, title, description, affected_files, author)
VALUES (
    '0.11.0', 'feature', 'Ghost Browser — KI-gesteuerte Web-Recherche',
    'Neues Feature: Playwright-basierter Chromium-Browser, von Ghost per KI steuerbar. '
    'User gibt Auftrag → Ghost navigiert, extrahiert Daten, erstellt Ergebnis-Dateien. '
    '3 DB-Tabellen (ghost_browser_tasks, ghost_browser_steps, ghost_browser_presets), '
    'bridge/browser_agent.py, 8 API-Endpoints, GhostBrowser.jsx Frontend-Komponente.',
    ARRAY['schema/56-ghost-browser.sql', 'bridge/browser_agent.py', 'web/server.py',
          'frontend/src/components/apps/GhostBrowser.jsx', 'frontend/src/api.js',
          'frontend/src/components/Desktop.jsx'],
    'ghost-agent'
) ON CONFLICT DO NOTHING;

-- ── System Memory ───────────────────────────────────────────────────────────
INSERT INTO dbai_knowledge.system_memory (category, title, content, structured_data, tags, author)
VALUES (
    'feature', 'Ghost Browser Architecture',
    'Ghost Browser nutzt Playwright (headless Chromium) im Backend. '
    'Der User gibt einen Auftrag per Prompt, Ghost navigiert automatisch, '
    'extrahiert Daten und erstellt Ergebnis-Dateien (MD/JSON/CSV). '
    'Sicherheit: Sandbox-Modus (kein Login), max_pages, max_duration. '
    'Screenshots werden bei jedem Schritt gespeichert.',
    '{"components": {"backend": "bridge/browser_agent.py", "api": "web/server.py /api/ghost-browser/*", "frontend": "GhostBrowser.jsx", "schema": "schema/56-ghost-browser.sql"}, "tables": ["dbai_system.ghost_browser_tasks", "dbai_system.ghost_browser_steps", "dbai_system.ghost_browser_presets"]}'::jsonb,
    ARRAY['ghost-browser', 'playwright', 'chromium', 'ai-agent', 'v0.11.0'],
    'ghost-agent'
) ON CONFLICT DO NOTHING;
