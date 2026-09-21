-- =============================================================================
-- DBAI CI/CD & OTA Update System
-- =============================================================================
-- Tabellen für Versionsverwaltung, Update-Kanäle, Migrations-Tracking,
-- Build-Artefakte und verbundene Nodes (OTA-Empfänger).
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- Update-Kanäle: stable, beta, nightly, dev
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dbai_system.update_channels (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    channel_name    TEXT NOT NULL UNIQUE,
    description     TEXT,
    is_default      BOOLEAN DEFAULT false,
    repo_url        TEXT,                       -- GitHub/GitLab Repo URL
    branch          TEXT DEFAULT 'main',        -- Git Branch
    check_interval  INTEGER DEFAULT 300,        -- Sekunden zwischen Checks
    is_active       BOOLEAN DEFAULT true,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- System-Releases: Jede Version die veröffentlicht wird
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dbai_system.system_releases (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    version         TEXT NOT NULL UNIQUE,       -- Semver: 0.8.2
    channel         TEXT NOT NULL DEFAULT 'stable',
    commit_hash     TEXT,                       -- Git SHA
    commit_message  TEXT,
    release_notes   TEXT,
    author          TEXT,
    build_number    INTEGER,
    artifact_url    TEXT,                       -- Download-URL des Pakets
    artifact_hash   TEXT,                       -- SHA256 des Archivs
    artifact_size   BIGINT,                    -- Bytes
    schema_version  INTEGER,                   -- Höchste Schema-Nummer
    requires_restart BOOLEAN DEFAULT false,
    is_critical     BOOLEAN DEFAULT false,     -- Sicherheitsupdate
    is_published    BOOLEAN DEFAULT false,
    published_at    TIMESTAMPTZ,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT system_releases_channel_fk
        FOREIGN KEY (channel) REFERENCES dbai_system.update_channels(channel_name)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_releases_channel ON dbai_system.system_releases(channel);
CREATE INDEX IF NOT EXISTS idx_releases_published ON dbai_system.system_releases(is_published, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_releases_version ON dbai_system.system_releases(version);

-- ---------------------------------------------------------------------------
-- Migration-History: Jede SQL-Migration die ausgeführt wurde
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dbai_system.migration_history (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    schema_file     TEXT NOT NULL,              -- z.B. "33-stufe3-deep-integration.sql"
    schema_number   INTEGER NOT NULL,           -- z.B. 33
    version         TEXT,                       -- Zugehörige Release-Version
    checksum        TEXT NOT NULL,              -- SHA256 des SQL-Files
    direction       TEXT DEFAULT 'up' CHECK (direction IN ('up', 'down', 'hotfix')),
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'running', 'success', 'failed', 'rolled_back')),
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    duration_ms     INTEGER,
    error_message   TEXT,
    applied_by      TEXT DEFAULT current_user,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_migration_schema_file
    ON dbai_system.migration_history(schema_file) WHERE status = 'success';
CREATE INDEX IF NOT EXISTS idx_migration_status ON dbai_system.migration_history(status);

-- ---------------------------------------------------------------------------
-- OTA Nodes: Verbundene Rechner die Updates empfangen
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dbai_system.ota_nodes (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    node_name       TEXT NOT NULL UNIQUE,
    hostname        TEXT,
    ip_address      INET,
    current_version TEXT,
    target_version  TEXT,                       -- NULL = auf dem neuesten Stand
    channel         TEXT NOT NULL DEFAULT 'stable',
    last_checkin    TIMESTAMPTZ,
    last_update     TIMESTAMPTZ,
    status          TEXT DEFAULT 'online'
                    CHECK (status IN ('online', 'offline', 'updating', 'error', 'rollback')),
    auto_update     BOOLEAN DEFAULT true,
    system_info     JSONB DEFAULT '{}',        -- CPU, RAM, Disk, OS
    update_log      JSONB DEFAULT '[]',        -- Letzte Update-Ergebnisse
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ota_nodes_channel ON dbai_system.ota_nodes(channel);
CREATE INDEX IF NOT EXISTS idx_ota_nodes_status ON dbai_system.ota_nodes(status);

-- ---------------------------------------------------------------------------
-- Build-Pipeline-Log: CI/CD Build-Ergebnisse
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dbai_system.build_pipeline (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    build_number    SERIAL,
    version         TEXT,
    commit_hash     TEXT,
    branch          TEXT DEFAULT 'main',
    trigger_type    TEXT DEFAULT 'push'
                    CHECK (trigger_type IN ('push', 'manual', 'schedule', 'webhook', 'tag')),
    status          TEXT DEFAULT 'queued'
                    CHECK (status IN ('queued', 'running', 'success', 'failed', 'cancelled')),
    steps           JSONB DEFAULT '[]',        -- Array von {name, status, duration_ms, log}
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    duration_ms     INTEGER,
    artifact_url    TEXT,
    error_message   TEXT,
    triggered_by    TEXT,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_build_status ON dbai_system.build_pipeline(status);
CREATE INDEX IF NOT EXISTS idx_build_branch ON dbai_system.build_pipeline(branch);

-- ---------------------------------------------------------------------------
-- Update-Aufträge: Konkrete Update-Jobs für Nodes
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dbai_system.update_jobs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    node_id         UUID REFERENCES dbai_system.ota_nodes(id) ON DELETE CASCADE,
    release_id      UUID REFERENCES dbai_system.system_releases(id) ON DELETE CASCADE,
    from_version    TEXT,
    to_version      TEXT NOT NULL,
    status          TEXT DEFAULT 'pending'
                    CHECK (status IN ('pending', 'downloading', 'applying', 'migrating',
                                      'restarting', 'verifying', 'success', 'failed', 'rolled_back')),
    progress        INTEGER DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    steps_completed JSONB DEFAULT '[]',
    error_message   TEXT,
    rollback_data   JSONB DEFAULT '{}',        -- Snapshot-Daten für Rollback
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    duration_ms     INTEGER,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_update_jobs_node ON dbai_system.update_jobs(node_id);
CREATE INDEX IF NOT EXISTS idx_update_jobs_status ON dbai_system.update_jobs(status);

-- ---------------------------------------------------------------------------
-- Funktion: Nächstes verfügbares Update für einen Node
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION dbai_system.get_available_update(p_node_id UUID)
RETURNS TABLE(
    release_id UUID,
    version TEXT,
    release_notes TEXT,
    is_critical BOOLEAN,
    requires_restart BOOLEAN,
    artifact_size BIGINT,
    published_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT r.id, r.version, r.release_notes, r.is_critical,
           r.requires_restart, r.artifact_size, r.published_at
    FROM dbai_system.system_releases r
    JOIN dbai_system.ota_nodes n ON n.id = p_node_id
    WHERE r.channel = n.channel
      AND r.is_published = true
      AND r.version > COALESCE(n.current_version, '0.0.0')
    ORDER BY r.created_at DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- Funktion: Migration-Status-Übersicht
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION dbai_system.get_migration_status()
RETURNS TABLE(
    total_migrations BIGINT,
    successful BIGINT,
    failed BIGINT,
    pending BIGINT,
    last_migration TEXT,
    last_migration_at TIMESTAMPTZ,
    current_schema_version INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::BIGINT,
        COUNT(*) FILTER (WHERE m.status = 'success')::BIGINT,
        COUNT(*) FILTER (WHERE m.status = 'failed')::BIGINT,
        COUNT(*) FILTER (WHERE m.status = 'pending')::BIGINT,
        (SELECT mh.schema_file FROM dbai_system.migration_history mh
         WHERE mh.status = 'success' ORDER BY mh.schema_number DESC LIMIT 1),
        (SELECT mh.finished_at FROM dbai_system.migration_history mh
         WHERE mh.status = 'success' ORDER BY mh.schema_number DESC LIMIT 1),
        (SELECT MAX(mh.schema_number) FROM dbai_system.migration_history mh
         WHERE mh.status = 'success')
    FROM dbai_system.migration_history m;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- Trigger: updated_at für ota_nodes automatisch setzen
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION dbai_system.update_ota_node_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ota_node_updated ON dbai_system.ota_nodes;
CREATE TRIGGER trg_ota_node_updated
    BEFORE UPDATE ON dbai_system.ota_nodes
    FOR EACH ROW EXECUTE FUNCTION dbai_system.update_ota_node_timestamp();

COMMIT;
