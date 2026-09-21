-- ============================================================================
-- DBAI Schema 33: Stufe 3 — Deep Integration
-- Features: Browser-Migration (11), System Config Import (12),
--           Workspace Mapping (13), Synaptic Memory Pipeline (14),
--           RAG Pipeline (15)
-- ============================================================================

BEGIN;

-- ============================================================================
-- FEATURE 11: Browser-Migration
-- Chrome/Firefox Bookmarks + History + Passwörter → ghost_knowledge_base
-- Ghost kann Lesezeichen "lesen" und kontextuell nutzen
-- ============================================================================

CREATE TABLE IF NOT EXISTS dbai_core.browser_profiles (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    browser_type    TEXT NOT NULL CHECK (browser_type IN ('chrome', 'firefox', 'chromium', 'brave', 'edge', 'vivaldi', 'opera')),
    profile_name    TEXT NOT NULL DEFAULT 'Default',
    profile_path    TEXT NOT NULL,
    user_id         UUID REFERENCES dbai_ui.users(id),
    imported_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    bookmark_count  INTEGER DEFAULT 0,
    history_count   INTEGER DEFAULT 0,
    password_count  INTEGER DEFAULT 0,
    metadata        JSONB DEFAULT '{}'::jsonb,
    UNIQUE(browser_type, profile_path)
);

CREATE TABLE IF NOT EXISTS dbai_core.browser_bookmarks (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    profile_id      UUID NOT NULL REFERENCES dbai_core.browser_profiles(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    url             TEXT NOT NULL,
    folder_path     TEXT DEFAULT '/',
    date_added      TIMESTAMPTZ,
    icon_url        TEXT,
    tags            TEXT[] DEFAULT '{}',
    description     TEXT,
    visit_count     INTEGER DEFAULT 0,
    last_visited    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_bookmarks_url ON dbai_core.browser_bookmarks(url);
CREATE INDEX IF NOT EXISTS idx_bookmarks_tags ON dbai_core.browser_bookmarks USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_bookmarks_folder ON dbai_core.browser_bookmarks(folder_path);

CREATE TABLE IF NOT EXISTS dbai_core.browser_history (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    profile_id      UUID NOT NULL REFERENCES dbai_core.browser_profiles(id) ON DELETE CASCADE,
    url             TEXT NOT NULL,
    title           TEXT,
    visit_time      TIMESTAMPTZ NOT NULL,
    visit_duration  INTEGER DEFAULT 0,  -- Sekunden
    transition_type TEXT DEFAULT 'link', -- link, typed, auto_bookmark, auto_subframe, manual_subframe, generated, auto_toplevel, form_submit, reload
    referrer_url    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_history_url ON dbai_core.browser_history(url);
CREATE INDEX IF NOT EXISTS idx_history_time ON dbai_core.browser_history(visit_time DESC);

CREATE TABLE IF NOT EXISTS dbai_core.browser_passwords (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    profile_id      UUID NOT NULL REFERENCES dbai_core.browser_profiles(id) ON DELETE CASCADE,
    origin_url      TEXT NOT NULL,
    username        TEXT,
    password_enc    BYTEA,  -- AES-256 verschlüsselt mit DBAI Master Key
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used       TIMESTAMPTZ,
    times_used      INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_passwords_origin ON dbai_core.browser_passwords(origin_url);

-- Ghost Knowledge Base für Browser-Daten (erweitert bestehende Vector-Tabelle)
CREATE TABLE IF NOT EXISTS dbai_core.ghost_knowledge_base (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_type     TEXT NOT NULL CHECK (source_type IN ('bookmark', 'history', 'password', 'config', 'workspace', 'manual', 'system', 'browser_pattern')),
    source_id       UUID,
    title           TEXT NOT NULL,
    content         TEXT,
    url             TEXT,
    category        TEXT,
    tags            TEXT[] DEFAULT '{}',
    embedding       vector(1536),
    relevance       FLOAT DEFAULT 1.0,
    access_count    INTEGER DEFAULT 0,
    last_accessed   TIMESTAMPTZ,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_gkb_source ON dbai_core.ghost_knowledge_base(source_type);
CREATE INDEX IF NOT EXISTS idx_gkb_tags ON dbai_core.ghost_knowledge_base USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_gkb_embedding ON dbai_core.ghost_knowledge_base USING hnsw (embedding vector_cosine_ops);

-- Funktion: Browser-Muster erkennen (häufige Domains, Surfverhalten)
CREATE OR REPLACE FUNCTION dbai_core.analyze_browser_patterns(p_profile_id UUID)
RETURNS JSONB AS $$
DECLARE
    v_result JSONB;
BEGIN
    SELECT jsonb_build_object(
        'top_domains', (
            SELECT jsonb_agg(jsonb_build_object('domain', domain, 'visits', cnt))
            FROM (
                SELECT substring(url FROM '://([^/]+)') AS domain, COUNT(*) AS cnt
                FROM dbai_core.browser_history WHERE profile_id = p_profile_id
                GROUP BY domain ORDER BY cnt DESC LIMIT 20
            ) AS domains
        ),
        'bookmarks_by_folder', (
            SELECT jsonb_agg(jsonb_build_object('folder', folder_path, 'count', cnt))
            FROM (
                SELECT folder_path, COUNT(*) AS cnt
                FROM dbai_core.browser_bookmarks WHERE profile_id = p_profile_id
                GROUP BY folder_path ORDER BY cnt DESC LIMIT 20
            ) AS folders
        ),
        'daily_activity', (
            SELECT jsonb_agg(jsonb_build_object('hour', hr, 'visits', cnt))
            FROM (
                SELECT EXTRACT(HOUR FROM visit_time)::INTEGER AS hr, COUNT(*) AS cnt
                FROM dbai_core.browser_history WHERE profile_id = p_profile_id
                GROUP BY hr ORDER BY hr
            ) AS hourly
        ),
        'total_bookmarks', (SELECT COUNT(*) FROM dbai_core.browser_bookmarks WHERE profile_id = p_profile_id),
        'total_history', (SELECT COUNT(*) FROM dbai_core.browser_history WHERE profile_id = p_profile_id),
        'analyzed_at', now()
    ) INTO v_result;
    RETURN v_result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- FEATURE 12: System Config Import
-- /etc/ und ~/.config/ parsen → WLAN, Tastatur, User-Rechte
-- ============================================================================

CREATE TABLE IF NOT EXISTS dbai_core.system_config (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    config_type     TEXT NOT NULL CHECK (config_type IN (
        'wifi', 'keyboard', 'locale', 'timezone', 'display', 'audio',
        'network', 'bluetooth', 'power', 'user_rights', 'shell',
        'desktop_env', 'package_manager', 'firewall', 'ssh', 'cron',
        'systemd_service', 'fstab', 'hosts', 'dns', 'proxy', 'vpn', 'other'
    )),
    config_name     TEXT NOT NULL,
    config_value    JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_path     TEXT,
    is_sensitive    BOOLEAN DEFAULT FALSE,
    imported_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    applied         BOOLEAN DEFAULT FALSE,
    applied_at      TIMESTAMPTZ,
    original_raw    TEXT,  -- Original-Inhalt (für Diff/Restore)
    metadata        JSONB DEFAULT '{}'::jsonb,
    UNIQUE(config_type, config_name)
);
CREATE INDEX IF NOT EXISTS idx_sysconfig_type ON dbai_core.system_config(config_type);

-- WLAN-Profile separat für strukturierten Zugriff
CREATE TABLE IF NOT EXISTS dbai_core.wifi_profiles (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ssid            TEXT NOT NULL,
    security_type   TEXT DEFAULT 'wpa2',  -- open, wep, wpa, wpa2, wpa3, enterprise
    password_enc    BYTEA,                -- AES-256 verschlüsselt
    auto_connect    BOOLEAN DEFAULT TRUE,
    priority        INTEGER DEFAULT 0,
    last_connected  TIMESTAMPTZ,
    interface_name  TEXT,
    ip_config       JSONB DEFAULT '{}'::jsonb,  -- static IP, DNS, Gateway
    imported_from   TEXT,  -- NetworkManager, wpa_supplicant, etc.
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(ssid, interface_name)
);

-- User-Rechte-Import
CREATE TABLE IF NOT EXISTS dbai_core.user_permissions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    linux_user      TEXT NOT NULL,
    linux_uid       INTEGER,
    linux_gid       INTEGER,
    groups          TEXT[] DEFAULT '{}',
    home_dir        TEXT,
    shell           TEXT,
    sudo_access     BOOLEAN DEFAULT FALSE,
    ssh_keys        TEXT[] DEFAULT '{}',
    cron_jobs       JSONB DEFAULT '[]'::jsonb,
    imported_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(linux_user)
);

-- ============================================================================
-- FEATURE 13: Workspace Mapping
-- Vorhandene Dateien indexieren (ohne Kopie), Setup-Wizard Integration
-- ============================================================================

CREATE TABLE IF NOT EXISTS dbai_core.workspace_index (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_path       TEXT NOT NULL UNIQUE,
    file_name       TEXT NOT NULL,
    file_ext        TEXT,
    mime_type       TEXT,
    file_size       BIGINT DEFAULT 0,
    is_directory    BOOLEAN DEFAULT FALSE,
    parent_path     TEXT,
    depth           INTEGER DEFAULT 0,
    modified_at     TIMESTAMPTZ,
    indexed_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    content_hash    TEXT,  -- SHA256
    tags            TEXT[] DEFAULT '{}',
    category        TEXT,  -- code, document, image, video, audio, archive, config, other
    language        TEXT,  -- Programmiersprache (für Code-Dateien)
    line_count      INTEGER,
    metadata        JSONB DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_workspace_path ON dbai_core.workspace_index(file_path);
CREATE INDEX IF NOT EXISTS idx_workspace_ext ON dbai_core.workspace_index(file_ext);
CREATE INDEX IF NOT EXISTS idx_workspace_category ON dbai_core.workspace_index(category);
CREATE INDEX IF NOT EXISTS idx_workspace_parent ON dbai_core.workspace_index(parent_path);
CREATE INDEX IF NOT EXISTS idx_workspace_tags ON dbai_core.workspace_index USING GIN(tags);

-- Workspace-Statistiken-View
CREATE OR REPLACE VIEW dbai_core.vw_workspace_stats AS
SELECT
    category,
    file_ext,
    COUNT(*) AS file_count,
    SUM(file_size) AS total_size,
    SUM(line_count) AS total_lines,
    MAX(modified_at) AS last_modified
FROM dbai_core.workspace_index
WHERE NOT is_directory
GROUP BY category, file_ext
ORDER BY file_count DESC;

-- Workspace-Baum als JSON
CREATE OR REPLACE FUNCTION dbai_core.get_workspace_tree(p_root TEXT DEFAULT '/', p_max_depth INTEGER DEFAULT 3)
RETURNS JSONB AS $$
DECLARE
    v_result JSONB;
BEGIN
    SELECT jsonb_agg(jsonb_build_object(
        'path', file_path,
        'name', file_name,
        'is_dir', is_directory,
        'size', file_size,
        'ext', file_ext,
        'category', category,
        'modified', modified_at
    ) ORDER BY is_directory DESC, file_name)
    INTO v_result
    FROM dbai_core.workspace_index
    WHERE file_path LIKE p_root || '%'
      AND depth <= p_max_depth;
    RETURN COALESCE(v_result, '[]'::jsonb);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- FEATURE 14: Synaptic Memory Pipeline
-- Hintergrund-Daemon der System-Events in Echtzeit vektorisiert
-- ============================================================================

CREATE TABLE IF NOT EXISTS dbai_vector.synaptic_memory (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type      TEXT NOT NULL CHECK (event_type IN (
        'system_event', 'user_action', 'ghost_thought', 'error',
        'performance', 'security', 'network', 'hardware',
        'file_change', 'process', 'login', 'config_change',
        'install', 'cron', 'notification'
    )),
    source          TEXT NOT NULL,  -- Quelle: server.py, ghost_autonomy, hardware_monitor, etc.
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,
    embedding       vector(1536),
    importance      FLOAT DEFAULT 0.5 CHECK (importance >= 0.0 AND importance <= 1.0),
    emotional_valence FLOAT DEFAULT 0.0 CHECK (emotional_valence >= -1.0 AND emotional_valence <= 1.0),
    associations    UUID[] DEFAULT '{}',  -- Verknüpfungen zu anderen Memories
    context_window  JSONB DEFAULT '{}'::jsonb,  -- Zeitfenster-Kontext
    decay_rate      FLOAT DEFAULT 0.995,
    access_count    INTEGER DEFAULT 0,
    last_accessed   TIMESTAMPTZ,
    consolidated    BOOLEAN DEFAULT FALSE,  -- Wurde in Langzeitgedächtnis überführt
    consolidated_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_synaptic_type ON dbai_vector.synaptic_memory(event_type);
CREATE INDEX IF NOT EXISTS idx_synaptic_importance ON dbai_vector.synaptic_memory(importance DESC);
CREATE INDEX IF NOT EXISTS idx_synaptic_time ON dbai_vector.synaptic_memory(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_synaptic_embedding ON dbai_vector.synaptic_memory USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_synaptic_consolidated ON dbai_vector.synaptic_memory(consolidated) WHERE NOT consolidated;

-- Synaptische Konsolidierung: Kurzzeitgedächtnis → Langzeitgedächtnis
CREATE OR REPLACE FUNCTION dbai_vector.consolidate_memories(p_threshold FLOAT DEFAULT 0.7, p_max_age INTERVAL DEFAULT '24 hours')
RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER := 0;
    v_mem RECORD;
BEGIN
    FOR v_mem IN
        SELECT * FROM dbai_vector.synaptic_memory
        WHERE NOT consolidated
          AND importance >= p_threshold
          AND created_at < now() - p_max_age
        ORDER BY importance DESC
        LIMIT 100
    LOOP
        -- In Langzeit-Speicher (dbai_vector.memories) überführen
        INSERT INTO dbai_vector.memories (
            memory_type, content, embedding, relevance, context, metadata
        ) VALUES (
            CASE v_mem.event_type
                WHEN 'error' THEN 'error'
                WHEN 'ghost_thought' THEN 'observation'
                WHEN 'user_action' THEN 'context'
                WHEN 'security' THEN 'fact'
                ELSE 'observation'
            END,
            v_mem.title || E'\n' || v_mem.content,
            v_mem.embedding,
            v_mem.importance,
            v_mem.context_window,
            jsonb_build_object('source', v_mem.source, 'event_type', v_mem.event_type, 'synaptic_id', v_mem.id)
        );

        UPDATE dbai_vector.synaptic_memory
        SET consolidated = TRUE, consolidated_at = now()
        WHERE id = v_mem.id;

        v_count := v_count + 1;
    END LOOP;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Automatisches Vergessen: unwichtige Synapsen verfallen
CREATE OR REPLACE FUNCTION dbai_vector.decay_synaptic()
RETURNS INTEGER AS $$
DECLARE
    v_deleted INTEGER;
BEGIN
    -- Alte, unwichtige, unkonsolidierte Einträge löschen
    DELETE FROM dbai_vector.synaptic_memory
    WHERE NOT consolidated
      AND importance < 0.2
      AND created_at < now() - INTERVAL '7 days';
    GET DIAGNOSTICS v_deleted = ROW_COUNT;

    -- Importance-Decay für alle nicht-konsolidierten
    UPDATE dbai_vector.synaptic_memory
    SET importance = importance * decay_rate
    WHERE NOT consolidated
      AND created_at < now() - INTERVAL '1 hour';

    RETURN v_deleted;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- FEATURE 15: RAG Pipeline
-- Automatische Retrieval-Augmented-Generation
-- ============================================================================

CREATE TABLE IF NOT EXISTS dbai_llm.rag_sources (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_name     TEXT NOT NULL UNIQUE,
    source_type     TEXT NOT NULL CHECK (source_type IN (
        'knowledge_base', 'system_memory', 'synaptic_memory',
        'workspace', 'browser', 'config', 'events', 'manual'
    )),
    enabled         BOOLEAN DEFAULT TRUE,
    priority        INTEGER DEFAULT 50,
    max_chunks      INTEGER DEFAULT 5,
    min_relevance   FLOAT DEFAULT 0.3,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dbai_llm.rag_chunks (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id       UUID NOT NULL REFERENCES dbai_llm.rag_sources(id) ON DELETE CASCADE,
    content         TEXT NOT NULL,
    embedding       vector(1536),
    token_count     INTEGER DEFAULT 0,
    metadata        JSONB DEFAULT '{}'::jsonb,
    source_ref      TEXT,  -- Referenz auf Original-Datensatz
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_source ON dbai_llm.rag_chunks(source_id);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_embedding ON dbai_llm.rag_chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS dbai_llm.rag_query_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_text      TEXT NOT NULL,
    query_embedding vector(1536),
    retrieved_chunks UUID[] DEFAULT '{}',
    chunk_scores    FLOAT[] DEFAULT '{}',
    total_tokens    INTEGER DEFAULT 0,
    role_name       TEXT,
    response_quality FLOAT,  -- User-Feedback 0.0-1.0
    latency_ms      INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- RAG-Suche: Relevante Chunks für einen Query finden
CREATE OR REPLACE FUNCTION dbai_llm.rag_search(
    p_query_embedding vector(1536),
    p_max_chunks INTEGER DEFAULT 10,
    p_min_relevance FLOAT DEFAULT 0.3,
    p_source_types TEXT[] DEFAULT NULL
)
RETURNS TABLE(chunk_id UUID, content TEXT, score FLOAT, source_name TEXT, source_type TEXT, metadata JSONB) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.content,
        (1 - (c.embedding <=> p_query_embedding))::FLOAT AS score,
        s.source_name,
        s.source_type,
        c.metadata
    FROM dbai_llm.rag_chunks c
    JOIN dbai_llm.rag_sources s ON c.source_id = s.id
    WHERE s.enabled = TRUE
      AND (p_source_types IS NULL OR s.source_type = ANY(p_source_types))
      AND (1 - (c.embedding <=> p_query_embedding)) >= p_min_relevance
    ORDER BY c.embedding <=> p_query_embedding
    LIMIT p_max_chunks;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- RAG-Kontext zusammenbauen für Ghost-Prompt
CREATE OR REPLACE FUNCTION dbai_llm.build_rag_context(
    p_query_embedding vector(1536),
    p_role_name TEXT DEFAULT NULL,
    p_max_tokens INTEGER DEFAULT 2000
)
RETURNS TEXT AS $$
DECLARE
    v_context TEXT := '';
    v_tokens INTEGER := 0;
    v_chunk RECORD;
BEGIN
    FOR v_chunk IN
        SELECT content, score, source_name, source_type
        FROM dbai_llm.rag_search(p_query_embedding, 20, 0.3, NULL)
        ORDER BY score DESC
    LOOP
        -- Grobe Token-Schätzung: ~4 Zeichen pro Token
        IF v_tokens + (LENGTH(v_chunk.content) / 4) > p_max_tokens THEN
            EXIT;
        END IF;

        v_context := v_context || E'\n--- [' || v_chunk.source_type || ': ' || v_chunk.source_name || ' | Score: ' || ROUND(v_chunk.score::numeric, 3) || E'] ---\n';
        v_context := v_context || v_chunk.content || E'\n';
        v_tokens := v_tokens + (LENGTH(v_chunk.content) / 4);
    END LOOP;

    RETURN v_context;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


COMMIT;
