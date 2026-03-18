-- =============================================================================
-- DBAI Schema 24: System Memory — Das vollständige Gehirn des Systems
--
-- "Wenn du vergisst, wer du bist, lies deine eigene Datenbank."
--
-- Dieses Schema speichert das Meta-Wissen über das GESAMTE System:
--   - Architektur-Überblick (Schemas, Rollen, Patterns)
--   - Coding-Konventionen (Naming, Testing, Datei-Struktur)
--   - Design-Patterns (NOTIFY/LISTEN, RLS, Append-Only)
--   - Schema-Karte (welcher Schema hat welche Tabellen)
--   - Beziehungen zwischen Komponenten
--   - Agent-Workflow-Wissen (wie arbeitet die KI an diesem Code)
--   - Projekt-Roadmap (Was kommt als nächstes)
--
-- Unterschied zu Schema 11 (Knowledge Library):
--   Schema 11 = Einzelne Dateien dokumentiert (File → Row)
--   Schema 24 = System als Ganzes verstanden (Architecture → Memory)
--
-- Ziel: Eine neue KI-Session kann durch SELECT * FROM
--   dbai_knowledge.system_memory alles rekonstruieren.
-- =============================================================================

-- =============================================================================
-- TABELLE: system_memory
-- Langzeitgedächtnis des KI-Agenten — alles was zwischen Sessions überleben muss
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_knowledge.system_memory (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    -- Wissenskategorie
    category        TEXT NOT NULL CHECK (category IN (
                        'architecture',     -- Wie das System als Ganzes aufgebaut ist
                        'convention',       -- Namensregeln, Code-Style, Test-Patterns
                        'schema_map',       -- Welcher Schema hat welche Tabellen
                        'design_pattern',   -- Wiederverwendbare Muster (NOTIFY, RLS, etc.)
                        'relationship',     -- Wie Komponenten zusammenhängen
                        'workflow',         -- Wie man am Code arbeitet (Agent-Wissen)
                        'inventory',        -- Technischer Stack, Versionen, Tools
                        'roadmap',          -- Zukunftspläne
                        'identity',         -- Wer/Was ist DBAI, Positionierung
                        'operational'       -- Deployment, Runtime, Monitoring
                    )),
    -- Kurzer Titel (max. 100 Zeichen)
    title           TEXT NOT NULL,
    -- Das eigentliche Wissen (Freitext, kann lang sein)
    content         TEXT NOT NULL,
    -- Maschinenlesbarer Kontext (JSON)
    structured_data JSONB DEFAULT '{}',
    -- Verknüpfungen
    related_modules TEXT[] DEFAULT '{}',    -- Betroffene Dateien
    related_schemas TEXT[] DEFAULT '{}',    -- Betroffene DB-Schemas
    tags            TEXT[] DEFAULT '{}',    -- Freitext-Tags
    -- Gültigkeit
    valid_from      TEXT NOT NULL DEFAULT '0.1.0',  -- Ab welcher Version gilt das
    valid_until     TEXT,                             -- NULL = noch gültig
    -- Priorität (höher = wichtiger für Kontext-Injektion)
    priority        INTEGER NOT NULL DEFAULT 50 CHECK (priority BETWEEN 1 AND 100),
    -- Metadaten
    author          TEXT NOT NULL DEFAULT 'system',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Einzigartig pro Kategorie+Titel
    UNIQUE (category, title)
);

DROP TRIGGER IF EXISTS trg_sysmem_updated ON dbai_knowledge.system_memory;
CREATE TRIGGER trg_sysmem_updated
    BEFORE UPDATE ON dbai_knowledge.system_memory
    FOR EACH ROW EXECUTE FUNCTION dbai_core.update_timestamp();

CREATE INDEX IF NOT EXISTS idx_sysmem_category ON dbai_knowledge.system_memory(category);
CREATE INDEX IF NOT EXISTS idx_sysmem_priority ON dbai_knowledge.system_memory(priority DESC);
CREATE INDEX IF NOT EXISTS idx_sysmem_tags ON dbai_knowledge.system_memory USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_sysmem_schemas ON dbai_knowledge.system_memory USING GIN(related_schemas);
CREATE INDEX IF NOT EXISTS idx_sysmem_valid ON dbai_knowledge.system_memory(valid_from);

-- =============================================================================
-- TABELLE: agent_sessions
-- Dokumentiert jede KI-Agent-Session die am Codebase gearbeitet hat
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_knowledge.agent_sessions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_date    DATE NOT NULL DEFAULT CURRENT_DATE,
    version_start   TEXT NOT NULL,          -- Version zu Beginn der Session
    version_end     TEXT,                   -- Version am Ende
    -- Was wurde gemacht
    summary         TEXT NOT NULL,
    files_created   TEXT[] DEFAULT '{}',
    files_modified  TEXT[] DEFAULT '{}',
    schemas_added   TEXT[] DEFAULT '{}',
    tests_before    INTEGER,
    tests_after     INTEGER,
    -- Kontext
    goals           TEXT[] DEFAULT '{}',     -- Was war das Ziel
    decisions       TEXT[] DEFAULT '{}',     -- Welche Entscheidungen wurden getroffen
    blockers        TEXT[] DEFAULT '{}',     -- Was hat blockiert
    -- Timestamps
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_session_date ON dbai_knowledge.agent_sessions(session_date DESC);
CREATE INDEX IF NOT EXISTS idx_session_version ON dbai_knowledge.agent_sessions(version_end);

-- =============================================================================
-- VIEW: System Memory als Kontext-Block
-- Generiert den kompletten Kontext den eine KI braucht um sofort arbeitsfähig zu sein
-- =============================================================================
CREATE OR REPLACE VIEW dbai_knowledge.vw_system_context AS
SELECT
    sm.category,
    sm.title,
    sm.content,
    sm.structured_data,
    sm.priority,
    sm.valid_from,
    sm.tags
FROM dbai_knowledge.system_memory sm
WHERE sm.valid_until IS NULL  -- Nur noch gültige Einträge
ORDER BY sm.priority DESC, sm.category, sm.title;

-- =============================================================================
-- VIEW: Letzte Agent-Session
-- =============================================================================
CREATE OR REPLACE VIEW dbai_knowledge.vw_last_session AS
SELECT *
FROM dbai_knowledge.agent_sessions
ORDER BY session_date DESC, started_at DESC
LIMIT 1;

-- =============================================================================
-- FUNKTION: Kontext-Zusammenfassung für neuen Agent
-- Gibt die wichtigsten Wissensbrocken als Text zurück
-- =============================================================================
CREATE OR REPLACE FUNCTION dbai_knowledge.get_agent_context(p_max_entries INTEGER DEFAULT 50)
RETURNS TEXT AS $$
DECLARE
    v_result TEXT := '';
    v_entry RECORD;
BEGIN
    v_result := '=== DBAI SYSTEM MEMORY ===';
    v_result := v_result || E'\nGeneriert: ' || NOW()::TEXT;
    v_result := v_result || E'\n\n';

    FOR v_entry IN
        SELECT category, title, content, priority
        FROM dbai_knowledge.system_memory
        WHERE valid_until IS NULL
        ORDER BY priority DESC, category
        LIMIT p_max_entries
    LOOP
        v_result := v_result || '[' || UPPER(v_entry.category) || '] '
                  || v_entry.title || E'\n'
                  || v_entry.content || E'\n\n';
    END LOOP;

    -- Letzte Session anfügen
    v_result := v_result || E'\n=== LETZTE AGENT-SESSION ===\n';
    SELECT v_result || COALESCE(summary, 'Keine Session dokumentiert')
    INTO v_result
    FROM dbai_knowledge.agent_sessions
    ORDER BY session_date DESC LIMIT 1;

    RETURN COALESCE(v_result, 'Kein System-Memory vorhanden');
END;
$$ LANGUAGE plpgsql STABLE;

-- =============================================================================
-- FUNKTION: Memory nach Kategorie abrufen
-- =============================================================================
CREATE OR REPLACE FUNCTION dbai_knowledge.get_memory_by_category(p_category TEXT)
RETURNS TABLE (title TEXT, content TEXT, priority INTEGER) AS $$
    SELECT sm.title, sm.content, sm.priority
    FROM dbai_knowledge.system_memory sm
    WHERE sm.category = p_category
      AND sm.valid_until IS NULL
    ORDER BY sm.priority DESC, sm.title;
$$ LANGUAGE SQL STABLE;

-- =============================================================================
-- FUNKTION: Memory speichern/aktualisieren (UPSERT)
-- =============================================================================
CREATE OR REPLACE FUNCTION dbai_knowledge.save_memory(
    p_category TEXT,
    p_title TEXT,
    p_content TEXT,
    p_priority INTEGER DEFAULT 50,
    p_tags TEXT[] DEFAULT '{}',
    p_valid_from TEXT DEFAULT '0.1.0'
) RETURNS UUID AS $$
DECLARE
    v_id UUID;
BEGIN
    INSERT INTO dbai_knowledge.system_memory
        (category, title, content, priority, tags, valid_from)
    VALUES (p_category, p_title, p_content, p_priority, p_tags, p_valid_from)
    ON CONFLICT (category, title) DO UPDATE
    SET content = p_content,
        priority = p_priority,
        tags = p_tags,
        updated_at = NOW()
    RETURNING id INTO v_id;

    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- RLS
-- =============================================================================
ALTER TABLE dbai_knowledge.system_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE dbai_knowledge.agent_sessions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS sysmem_system_full ON dbai_knowledge.system_memory;
CREATE POLICY sysmem_system_full ON dbai_knowledge.system_memory
    FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS sysmem_llm_read ON dbai_knowledge.system_memory;
CREATE POLICY sysmem_llm_read ON dbai_knowledge.system_memory
    FOR SELECT TO dbai_llm USING (TRUE);
DROP POLICY IF EXISTS sysmem_monitor_read ON dbai_knowledge.system_memory;
CREATE POLICY sysmem_monitor_read ON dbai_knowledge.system_memory
    FOR SELECT TO dbai_monitor USING (TRUE);

DROP POLICY IF EXISTS session_system_full ON dbai_knowledge.agent_sessions;
CREATE POLICY session_system_full ON dbai_knowledge.agent_sessions
    FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS session_llm_read ON dbai_knowledge.agent_sessions;
CREATE POLICY session_llm_read ON dbai_knowledge.agent_sessions
    FOR SELECT TO dbai_llm USING (TRUE);

-- =============================================================================
-- KOMMENTARE
-- =============================================================================
COMMENT ON TABLE dbai_knowledge.system_memory IS
    'Langzeitgedächtnis des KI-Agenten: Architektur, Konventionen, Patterns, Schema-Map — alles was zwischen Sessions überleben muss';
COMMENT ON TABLE dbai_knowledge.agent_sessions IS
    'Dokumentiert jede KI-Agent-Session: Was wurde getan, welche Dateien, welche Entscheidungen';
COMMENT ON FUNCTION dbai_knowledge.get_agent_context IS
    'Gibt den kompletten System-Kontext als Text zurück — eine neue KI kann sofort loslegen';
COMMENT ON FUNCTION dbai_knowledge.save_memory IS
    'UPSERT für System-Memory: speichert/aktualisiert einen Wissenseintrag';
