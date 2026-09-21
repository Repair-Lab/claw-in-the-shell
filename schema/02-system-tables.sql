-- =============================================================================
-- DBAI Schema 02: System-Tabellen
-- Live-Hardware-Werte — CPU, RAM, Temperatur, Disk, Netzwerk
-- Diese Tabellen enthalten KEINE statischen Daten, nur Live-Werte
-- =============================================================================

-- CPU-Auslastung (Live)
CREATE TABLE IF NOT EXISTS dbai_system.cpu (
    id              BIGSERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    core_id         SMALLINT NOT NULL,
    usage_percent   REAL NOT NULL CHECK (usage_percent BETWEEN 0 AND 100),
    frequency_mhz   REAL,
    temperature_c   REAL,
    throttled       BOOLEAN NOT NULL DEFAULT FALSE,
    state           TEXT NOT NULL DEFAULT 'online' CHECK (state IN (
                        'online', 'offline', 'idle', 'throttled'
                    ))
);

-- Partitionierung nach Zeit für effizientes Cleanup
-- Alte Werte werden nach 24h automatisch gelöscht
CREATE INDEX IF NOT EXISTS idx_cpu_ts ON dbai_system.cpu(ts DESC);
CREATE INDEX IF NOT EXISTS idx_cpu_core ON dbai_system.cpu(core_id);

-- RAM-Belegung (Live)
CREATE TABLE IF NOT EXISTS dbai_system.memory (
    id              BIGSERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    total_mb        INTEGER NOT NULL,
    used_mb         INTEGER NOT NULL,
    free_mb         INTEGER NOT NULL,
    cached_mb       INTEGER NOT NULL DEFAULT 0,
    buffers_mb      INTEGER NOT NULL DEFAULT 0,
    swap_total_mb   INTEGER NOT NULL DEFAULT 0,
    swap_used_mb    INTEGER NOT NULL DEFAULT 0,
    usage_percent   REAL NOT NULL CHECK (usage_percent BETWEEN 0 AND 100),
    pressure_level  TEXT NOT NULL DEFAULT 'normal' CHECK (pressure_level IN (
                        'normal', 'warning', 'critical', 'oom'
                    ))
);

CREATE INDEX IF NOT EXISTS idx_memory_ts ON dbai_system.memory(ts DESC);
CREATE INDEX IF NOT EXISTS idx_memory_pressure ON dbai_system.memory(pressure_level);

-- Festplatten-Status (Live)
CREATE TABLE IF NOT EXISTS dbai_system.disk (
    id              BIGSERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    device          TEXT NOT NULL,
    mount_point     TEXT NOT NULL,
    fs_type         TEXT NOT NULL,  -- zfs, btrfs, ext4, etc.
    total_gb        REAL NOT NULL,
    used_gb         REAL NOT NULL,
    free_gb         REAL NOT NULL,
    usage_percent   REAL NOT NULL,
    read_iops       INTEGER DEFAULT 0,
    write_iops      INTEGER DEFAULT 0,
    read_mbps       REAL DEFAULT 0,
    write_mbps      REAL DEFAULT 0,
    -- ZFS/BTRFS Self-Healing Status
    scrub_errors    INTEGER DEFAULT 0,
    self_heal_count INTEGER DEFAULT 0,
    health_state    TEXT NOT NULL DEFAULT 'healthy' CHECK (health_state IN (
                        'healthy', 'degraded', 'failing', 'offline'
                    ))
);

CREATE INDEX IF NOT EXISTS idx_disk_ts ON dbai_system.disk(ts DESC);
CREATE INDEX IF NOT EXISTS idx_disk_device ON dbai_system.disk(device);
CREATE INDEX IF NOT EXISTS idx_disk_health ON dbai_system.disk(health_state);

-- Temperatur-Sensoren (Live)
CREATE TABLE IF NOT EXISTS dbai_system.temperature (
    id              BIGSERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sensor_name     TEXT NOT NULL,
    sensor_type     TEXT NOT NULL CHECK (sensor_type IN (
                        'cpu', 'gpu', 'disk', 'motherboard', 'ambient', 'psu'
                    )),
    temperature_c   REAL NOT NULL,
    critical_c      REAL,          -- Schwellwert kritisch
    warning_c       REAL,          -- Schwellwert Warnung
    state           TEXT NOT NULL DEFAULT 'normal' CHECK (state IN (
                        'normal', 'warm', 'hot', 'critical', 'shutdown'
                    ))
);

CREATE INDEX IF NOT EXISTS idx_temp_ts ON dbai_system.temperature(ts DESC);
CREATE INDEX IF NOT EXISTS idx_temp_state ON dbai_system.temperature(state);

-- Netzwerk-Status (Live)
CREATE TABLE IF NOT EXISTS dbai_system.network (
    id              BIGSERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    interface       TEXT NOT NULL,
    state           TEXT NOT NULL DEFAULT 'up' CHECK (state IN (
                        'up', 'down', 'dormant', 'unknown'
                    )),
    ip_address      INET,
    mac_address     MACADDR,
    rx_bytes        BIGINT DEFAULT 0,
    tx_bytes        BIGINT DEFAULT 0,
    rx_packets      BIGINT DEFAULT 0,
    tx_packets      BIGINT DEFAULT 0,
    rx_errors       BIGINT DEFAULT 0,
    tx_errors       BIGINT DEFAULT 0,
    link_speed_mbps INTEGER
);

CREATE INDEX IF NOT EXISTS idx_network_ts ON dbai_system.network(ts DESC);
CREATE INDEX IF NOT EXISTS idx_network_iface ON dbai_system.network(interface);

-- =============================================================================
-- Automatische Cleanup-Funktion für System-Tabellen
-- Daten älter als 24h werden gelöscht (außer Anomalien)
-- =============================================================================
CREATE OR REPLACE FUNCTION dbai_system.cleanup_old_metrics()
RETURNS void AS $$
BEGIN
    DELETE FROM dbai_system.cpu
        WHERE ts < NOW() - INTERVAL '24 hours';
    DELETE FROM dbai_system.memory
        WHERE ts < NOW() - INTERVAL '24 hours'
        AND pressure_level = 'normal';
    DELETE FROM dbai_system.disk
        WHERE ts < NOW() - INTERVAL '24 hours'
        AND health_state = 'healthy';
    DELETE FROM dbai_system.temperature
        WHERE ts < NOW() - INTERVAL '24 hours'
        AND state = 'normal';
    DELETE FROM dbai_system.network
        WHERE ts < NOW() - INTERVAL '24 hours';
END;
$$ LANGUAGE plpgsql;

-- Cleanup alle 6 Stunden
-- SELECT cron.schedule('dbai_metrics_cleanup', '0 */6 * * *',
--     'SELECT dbai_system.cleanup_old_metrics()');

-- =============================================================================
-- View: Aktuelle System-Zusammenfassung
-- =============================================================================
CREATE OR REPLACE VIEW dbai_system.current_status AS
SELECT
    (SELECT json_build_object(
        'avg_usage', ROUND(AVG(usage_percent)::numeric, 1),
        'max_temp', MAX(temperature_c),
        'cores_online', COUNT(DISTINCT core_id)
    ) FROM dbai_system.cpu
    WHERE ts > NOW() - INTERVAL '5 seconds') AS cpu,

    (SELECT json_build_object(
        'used_mb', used_mb,
        'free_mb', free_mb,
        'usage_percent', ROUND(usage_percent::numeric, 1),
        'pressure', pressure_level
    ) FROM dbai_system.memory
    ORDER BY ts DESC LIMIT 1) AS memory,

    (SELECT json_agg(json_build_object(
        'device', device,
        'usage_percent', ROUND(usage_percent::numeric, 1),
        'health', health_state
    )) FROM (
        SELECT DISTINCT ON (device) device, usage_percent, health_state
        FROM dbai_system.disk ORDER BY device, ts DESC
    ) d) AS disks;
