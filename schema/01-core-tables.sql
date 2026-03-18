-- =============================================================================
-- DBAI Schema 01: Core-Tabellen
-- Das Fundament — Objekt-Registry statt Dateipfade
-- =============================================================================

-- Objekt-Registry: JEDE Ressource bekommt eine UUID statt einem Dateipfad
-- No-Go: Niemals manuelle Dateipfade benutzen — immer eine ID aus dieser Tabelle
CREATE TABLE IF NOT EXISTS dbai_core.objects (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    object_type     TEXT NOT NULL CHECK (object_type IN (
                        'file', 'config', 'model', 'driver',
                        'process', 'service', 'device', 'stream'
                    )),
    name            TEXT NOT NULL,
    mime_type       TEXT,
    size_bytes      BIGINT DEFAULT 0,
    -- Hash/Pointer für externe Daten (Videos, Bilder)
    -- No-Go: Keine riesigen Binärdaten direkt in Tabellen
    storage_hash    TEXT,
    storage_backend TEXT DEFAULT 'local' CHECK (storage_backend IN (
                        'local', 'zfs_pool', 'btrfs_subvol'
                    )),
    -- Metadaten als JSONB (durchsuchbar)
    metadata        JSONB DEFAULT '{}',
    owner_role      TEXT NOT NULL DEFAULT 'dbai_system',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE,
    -- Soft-Delete: Objekte werden nie physisch gelöscht
    deleted_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_objects_type ON dbai_core.objects(object_type);
CREATE INDEX IF NOT EXISTS idx_objects_name ON dbai_core.objects(name);
CREATE INDEX IF NOT EXISTS idx_objects_hash ON dbai_core.objects(storage_hash);
CREATE INDEX IF NOT EXISTS idx_objects_metadata ON dbai_core.objects USING GIN(metadata);

-- Trigger: updated_at automatisch setzen
CREATE OR REPLACE FUNCTION dbai_core.update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_objects_updated ON dbai_core.objects;
CREATE TRIGGER trg_objects_updated
    BEFORE UPDATE ON dbai_core.objects
    FOR EACH ROW EXECUTE FUNCTION dbai_core.update_timestamp();

-- =============================================================================
-- Prozess-Tabelle: Laufende Systemdienste und Aufgaben
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_core.processes (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pid             INTEGER,
    name            TEXT NOT NULL,
    process_type    TEXT NOT NULL CHECK (process_type IN (
                        'system', 'driver', 'monitor', 'llm',
                        'user_task', 'recovery', 'vacuum'
                    )),
    state           TEXT NOT NULL DEFAULT 'created' CHECK (state IN (
                        'created', 'running', 'paused', 'stopped',
                        'crashed', 'zombie'
                    )),
    priority        INTEGER NOT NULL DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
    -- 1 = höchste Priorität (Kernel), 10 = niedrigste
    cpu_affinity    INTEGER[],
    memory_limit_mb INTEGER,
    started_at      TIMESTAMPTZ,
    stopped_at      TIMESTAMPTZ,
    last_heartbeat  TIMESTAMPTZ DEFAULT NOW(),
    error_message   TEXT,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_processes_state ON dbai_core.processes(state);
CREATE INDEX IF NOT EXISTS idx_processes_type ON dbai_core.processes(process_type);
CREATE INDEX IF NOT EXISTS idx_processes_priority ON dbai_core.processes(priority);

-- =============================================================================
-- Konfigurations-Tabelle: Schlüssel-Wert-Paare statt Config-Dateien
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_core.config (
    key             TEXT PRIMARY KEY,
    value           JSONB NOT NULL,
    category        TEXT NOT NULL DEFAULT 'general',
    description     TEXT,
    is_readonly     BOOLEAN NOT NULL DEFAULT FALSE,
    -- Wer darf diesen Wert lesen/ändern
    read_roles      TEXT[] DEFAULT ARRAY['dbai_system'],
    write_roles     TEXT[] DEFAULT ARRAY['dbai_system'],
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_config_updated ON dbai_core.config;
CREATE TRIGGER trg_config_updated
    BEFORE UPDATE ON dbai_core.config
    FOR EACH ROW EXECUTE FUNCTION dbai_core.update_timestamp();

-- Schutz: Readonly-Werte nicht überschreibbar
CREATE OR REPLACE FUNCTION dbai_core.protect_readonly_config()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.is_readonly = TRUE AND NEW.value IS DISTINCT FROM OLD.value THEN
        RAISE EXCEPTION 'Config-Wert "%" ist schreibgeschützt', OLD.key;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_config_readonly ON dbai_core.config;
CREATE TRIGGER trg_config_readonly
    BEFORE UPDATE ON dbai_core.config
    FOR EACH ROW EXECUTE FUNCTION dbai_core.protect_readonly_config();

-- =============================================================================
-- Treiber-Registry: Alle Hardware-Treiber als Tabelleneinträge
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_core.drivers (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT NOT NULL UNIQUE,
    driver_type     TEXT NOT NULL CHECK (driver_type IN (
                        'storage', 'network', 'input', 'display',
                        'audio', 'sensor', 'gpu', 'usb', 'console'
                    )),
    version         TEXT NOT NULL,
    state           TEXT NOT NULL DEFAULT 'unloaded' CHECK (state IN (
                        'unloaded', 'loading', 'loaded', 'active',
                        'error', 'disabled'
                    )),
    -- Objekt-ID des Treiber-Binaries
    binary_object_id UUID REFERENCES dbai_core.objects(id),
    config          JSONB DEFAULT '{}',
    is_critical     BOOLEAN NOT NULL DEFAULT FALSE,
    loaded_at       TIMESTAMPTZ,
    error_count     INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_drivers_state ON dbai_core.drivers(state);
CREATE INDEX IF NOT EXISTS idx_drivers_type ON dbai_core.drivers(driver_type);
