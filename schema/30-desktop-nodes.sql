-- ═══════════════════════════════════════════════════════════════
-- DBAI Schema 30 — Desktop Network Nodes & Scene Config
-- SVG-basierter Desktop mit dynamischen Netzwerk-Knoten
-- ═══════════════════════════════════════════════════════════════

-- ── desktop_nodes: Jeder Knoten auf dem SVG-Desktop ──
CREATE TABLE IF NOT EXISTS dbai_ui.desktop_nodes (
    id              SERIAL PRIMARY KEY,
    node_key        TEXT NOT NULL UNIQUE,          -- z.B. 'youtube', 'nas', 'google'
    label           TEXT NOT NULL,                  -- Anzeigename
    node_type       TEXT NOT NULL DEFAULT 'service', -- service, device, cloud, custom
    icon_type       TEXT NOT NULL DEFAULT 'circle',  -- circle, rect, phone, server, play, search, nas, cloud, printer, camera, iot, custom
    color           TEXT NOT NULL DEFAULT '#00f5ff',  -- Hauptfarbe (hex)
    glow_color      TEXT DEFAULT NULL,               -- Glow-Farbe (falls anders als color)
    position_x      REAL NOT NULL DEFAULT 400,       -- SVG X-Position (0-1920)
    position_y      REAL NOT NULL DEFAULT 300,       -- SVG Y-Position (0-1080)
    scale           REAL NOT NULL DEFAULT 1.0,       -- Skalierung
    app_id          TEXT DEFAULT NULL,               -- Verknüpfte App (öffnet bei Click)
    url             TEXT DEFAULT NULL,               -- Externe URL (für WebFrame)
    is_visible      BOOLEAN NOT NULL DEFAULT true,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT valid_node_type CHECK (node_type IN ('service', 'device', 'cloud', 'custom')),
    CONSTRAINT valid_position_x CHECK (position_x >= 0 AND position_x <= 1920),
    CONSTRAINT valid_position_y CHECK (position_y >= 0 AND position_y <= 1080)
);

-- ── desktop_scene: Globale Szenen-Konfiguration ──
CREATE TABLE IF NOT EXISTS dbai_ui.desktop_scene (
    id              SERIAL PRIMARY KEY,
    scene_key       TEXT NOT NULL UNIQUE,           -- Konfig-Schlüssel
    scene_value     JSONB NOT NULL DEFAULT '{}',    -- Konfig-Wert
    description     TEXT DEFAULT NULL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indizes
CREATE INDEX IF NOT EXISTS idx_desktop_nodes_visible ON dbai_ui.desktop_nodes(is_visible) WHERE is_visible = true;
CREATE INDEX IF NOT EXISTS idx_desktop_nodes_key ON dbai_ui.desktop_nodes(node_key);

-- Trigger für updated_at
CREATE OR REPLACE FUNCTION dbai_ui.update_desktop_node_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_desktop_nodes_updated ON dbai_ui.desktop_nodes;
CREATE TRIGGER trg_desktop_nodes_updated
    BEFORE UPDATE ON dbai_ui.desktop_nodes
    FOR EACH ROW EXECUTE FUNCTION dbai_ui.update_desktop_node_timestamp();

DROP TRIGGER IF EXISTS trg_desktop_scene_updated ON dbai_ui.desktop_scene;
CREATE TRIGGER trg_desktop_scene_updated
    BEFORE UPDATE ON dbai_ui.desktop_scene
    FOR EACH ROW EXECUTE FUNCTION dbai_ui.update_desktop_node_timestamp();

-- ── Rechte für Runtime-User ──
GRANT SELECT, INSERT, UPDATE, DELETE ON dbai_ui.desktop_nodes TO dbai_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON dbai_ui.desktop_scene TO dbai_runtime;
GRANT USAGE, SELECT ON SEQUENCE dbai_ui.desktop_nodes_id_seq TO dbai_runtime;
GRANT USAGE, SELECT ON SEQUENCE dbai_ui.desktop_scene_id_seq TO dbai_runtime;
