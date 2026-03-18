-- =============================================================================
-- DBAI Schema 38: KI Werkstatt — Benutzerdefinierte Datenbanken
-- Custom Tables für project_type = 'custom'
-- Stand: 16. März 2026
-- =============================================================================

BEGIN;

-- Benutzerdefinierte Tabellen (Schema-Definition pro Projekt)
CREATE TABLE IF NOT EXISTS dbai_workshop.custom_tables (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES dbai_workshop.projects(id) ON DELETE CASCADE,
    table_name  TEXT NOT NULL,
    description TEXT DEFAULT '',
    columns     JSONB NOT NULL DEFAULT '[]',
    -- columns: [{"name":"titel","type":"text","required":true},{"name":"preis","type":"number"},...]
    -- Typen: text, number, boolean, date, url, email, select, tags, richtext
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_custom_tables_project ON dbai_workshop.custom_tables(project_id);

-- Benutzerdefinierte Zeilen (Daten pro Custom-Tabelle)
CREATE TABLE IF NOT EXISTS dbai_workshop.custom_rows (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_id    UUID NOT NULL REFERENCES dbai_workshop.custom_tables(id) ON DELETE CASCADE,
    data        JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_custom_rows_table ON dbai_workshop.custom_rows(table_id);
CREATE INDEX IF NOT EXISTS idx_custom_rows_data ON dbai_workshop.custom_rows USING gin(data);

-- Berechtigungen
GRANT SELECT, INSERT, UPDATE, DELETE ON dbai_workshop.custom_tables TO dbai_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON dbai_workshop.custom_rows TO dbai_runtime;
GRANT SELECT ON dbai_workshop.custom_tables TO dbai_monitor;
GRANT SELECT ON dbai_workshop.custom_rows TO dbai_monitor;

COMMIT;
