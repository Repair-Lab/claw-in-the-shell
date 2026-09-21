-- ============================================================================
-- DBAI Schema 34: Stufe 4 — Nice-to-Have
-- Features: USB Installer (16), WLAN Hotspot (17), Immutable FS (18),
--           i18n Runtime (19), Anomalie-Erkennung (20), App Sandboxing (21),
--           Network Policy/Firewall (22), Terminal (23)
-- ============================================================================

BEGIN;

-- ============================================================================
-- FEATURE 16: USB Installer
-- dd/Ventoy Image → USB-Stick
-- ============================================================================

CREATE TABLE IF NOT EXISTS dbai_system.usb_devices (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    device_path     TEXT NOT NULL,  -- /dev/sdb
    device_name     TEXT,
    vendor          TEXT,
    model           TEXT,
    serial          TEXT,
    size_bytes      BIGINT,
    filesystem      TEXT,
    is_removable    BOOLEAN DEFAULT TRUE,
    is_mounted      BOOLEAN DEFAULT FALSE,
    mount_point     TEXT,
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata        JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS dbai_system.usb_flash_jobs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    device_id       UUID REFERENCES dbai_system.usb_devices(id),
    image_path      TEXT NOT NULL,
    image_type      TEXT NOT NULL CHECK (image_type IN ('iso', 'img', 'ventoy', 'dd')),
    method          TEXT NOT NULL CHECK (method IN ('dd', 'ventoy', 'etcher', 'cp')),
    status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'preparing', 'flashing', 'verifying', 'completed', 'failed', 'cancelled')),
    progress        FLOAT DEFAULT 0.0,
    bytes_written   BIGINT DEFAULT 0,
    speed_bps       BIGINT DEFAULT 0,
    error_message   TEXT,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by      UUID
);

-- ============================================================================
-- FEATURE 17: WLAN Hotspot
-- AP-Mode bei Erstinstallation
-- ============================================================================

CREATE TABLE IF NOT EXISTS dbai_system.hotspot_config (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ssid            TEXT NOT NULL DEFAULT 'DBAI-Setup',
    password        TEXT DEFAULT 'ghost2026',
    band            TEXT DEFAULT '2.4GHz' CHECK (band IN ('2.4GHz', '5GHz', 'auto')),
    channel         INTEGER DEFAULT 6,
    interface       TEXT DEFAULT 'wlan0',
    subnet          TEXT DEFAULT '192.168.73.0/24',
    gateway         TEXT DEFAULT '192.168.73.1',
    dhcp_start      TEXT DEFAULT '192.168.73.10',
    dhcp_end        TEXT DEFAULT '192.168.73.50',
    dns_server      TEXT DEFAULT '192.168.73.1',
    is_active       BOOLEAN DEFAULT FALSE,
    captive_portal  BOOLEAN DEFAULT TRUE,
    max_clients     INTEGER DEFAULT 10,
    started_at      TIMESTAMPTZ,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================================
-- FEATURE 18: Immutable Filesystem
-- OverlayFS/SquashFS — nur PostgreSQL darf schreiben
-- ============================================================================

CREATE TABLE IF NOT EXISTS dbai_system.immutable_config (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    mode            TEXT NOT NULL DEFAULT 'disabled' CHECK (mode IN ('disabled', 'overlay', 'squashfs', 'btrfs_snapshot')),
    protected_paths TEXT[] DEFAULT ARRAY['/usr', '/bin', '/sbin', '/lib', '/etc'],
    writable_paths  TEXT[] DEFAULT ARRAY['/var/lib/postgresql', '/tmp', '/home', '/var/log'],
    overlay_upper   TEXT DEFAULT '/var/overlay/upper',
    overlay_work    TEXT DEFAULT '/var/overlay/work',
    snapshot_count  INTEGER DEFAULT 5,
    auto_rollback   BOOLEAN DEFAULT TRUE,
    last_snapshot   TIMESTAMPTZ,
    is_active       BOOLEAN DEFAULT FALSE,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dbai_system.fs_snapshots (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    snapshot_name   TEXT NOT NULL,
    snapshot_type   TEXT NOT NULL CHECK (snapshot_type IN ('auto', 'manual', 'pre_update', 'pre_install', 'recovery')),
    snapshot_path   TEXT,
    size_bytes      BIGINT DEFAULT 0,
    parent_id       UUID REFERENCES dbai_system.fs_snapshots(id),
    description     TEXT,
    is_bootable     BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ
);

-- ============================================================================
-- FEATURE 19: i18n Runtime-Translation
-- Dynamische Übersetzungen statt hartkodiert
-- ============================================================================

CREATE TABLE IF NOT EXISTS dbai_ui.i18n_translations (
    id              SERIAL PRIMARY KEY,
    locale          TEXT NOT NULL,
    namespace       TEXT NOT NULL DEFAULT 'common',
    key             TEXT NOT NULL,
    value           TEXT NOT NULL,
    plural_forms    JSONB,  -- { "one": "...", "other": "...", "zero": "..." }
    context         TEXT,   -- Disambiguierung
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(locale, namespace, key, context)
);
CREATE INDEX IF NOT EXISTS idx_i18n_locale ON dbai_ui.i18n_translations(locale);
CREATE INDEX IF NOT EXISTS idx_i18n_ns_key ON dbai_ui.i18n_translations(namespace, key);

-- Verfügbare Sprachen
CREATE TABLE IF NOT EXISTS dbai_ui.i18n_locales (
    locale          TEXT PRIMARY KEY,
    name_native     TEXT NOT NULL,
    name_english    TEXT NOT NULL,
    direction       TEXT DEFAULT 'ltr' CHECK (direction IN ('ltr', 'rtl')),
    is_default      BOOLEAN DEFAULT FALSE,
    coverage        FLOAT DEFAULT 0.0,  -- Übersetzungs-Abdeckung 0.0-1.0
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Batch-Übersetzung für ein ganzes Locale
CREATE OR REPLACE FUNCTION dbai_ui.get_translations(p_locale TEXT, p_namespace TEXT DEFAULT 'common')
RETURNS JSONB AS $$
DECLARE
    v_result JSONB;
BEGIN
    SELECT jsonb_object_agg(key, value)
    INTO v_result
    FROM dbai_ui.i18n_translations
    WHERE locale = p_locale AND namespace = p_namespace;
    RETURN COALESCE(v_result, '{}'::jsonb);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- FEATURE 20: Anomalie-Erkennung
-- ML-basiert statt Regex — Patterns in Metriken-Zeitreihen
-- ============================================================================

CREATE TABLE IF NOT EXISTS dbai_system.anomaly_models (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_name      TEXT NOT NULL UNIQUE,
    model_type      TEXT NOT NULL CHECK (model_type IN ('statistical', 'isolation_forest', 'autoencoder', 'lstm', 'prophet', 'custom')),
    target_metric   TEXT NOT NULL,  -- cpu_usage, memory_usage, disk_io, network_rx, etc.
    parameters      JSONB DEFAULT '{}'::jsonb,
    training_data   JSONB DEFAULT '{}'::jsonb,  -- Statistiken über Trainingsdaten
    threshold       FLOAT DEFAULT 2.0,  -- Standard-Abweichungen / Anomalie-Score
    is_active       BOOLEAN DEFAULT TRUE,
    accuracy        FLOAT,
    last_trained    TIMESTAMPTZ,
    last_prediction TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dbai_system.anomaly_detections (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_id        UUID NOT NULL REFERENCES dbai_system.anomaly_models(id) ON DELETE CASCADE,
    metric_name     TEXT NOT NULL,
    metric_value    FLOAT NOT NULL,
    expected_value  FLOAT,
    expected_range  FLOAT[] DEFAULT '{}',  -- [min, max]
    anomaly_score   FLOAT NOT NULL,
    severity        TEXT DEFAULT 'info' CHECK (severity IN ('info', 'warning', 'critical')),
    description     TEXT,
    auto_resolved   BOOLEAN DEFAULT FALSE,
    resolved_at     TIMESTAMPTZ,
    metadata        JSONB DEFAULT '{}'::jsonb,
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_anomaly_time ON dbai_system.anomaly_detections(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_anomaly_severity ON dbai_system.anomaly_detections(severity);

-- Simple statistische Anomalie-Erkennung (Z-Score)
CREATE OR REPLACE FUNCTION dbai_system.detect_anomaly(
    p_metric TEXT,
    p_value FLOAT,
    p_window INTERVAL DEFAULT '1 hour'
)
RETURNS JSONB AS $$
DECLARE
    v_mean FLOAT;
    v_stddev FLOAT;
    v_zscore FLOAT;
    v_is_anomaly BOOLEAN;
BEGIN
    -- Historische Metriken aus system_metrics_history
    SELECT AVG(value), STDDEV(value)
    INTO v_mean, v_stddev
    FROM dbai_system.metrics_history
    WHERE metric_name = p_metric
      AND recorded_at > now() - p_window;

    IF v_stddev IS NULL OR v_stddev = 0 THEN
        RETURN jsonb_build_object('anomaly', FALSE, 'reason', 'insufficient_data');
    END IF;

    v_zscore := ABS(p_value - v_mean) / v_stddev;
    v_is_anomaly := v_zscore > 2.0;

    IF v_is_anomaly THEN
        INSERT INTO dbai_system.anomaly_detections (
            model_id, metric_name, metric_value, expected_value,
            expected_range, anomaly_score, severity, description
        )
        SELECT
            id, p_metric, p_value, v_mean,
            ARRAY[v_mean - 2*v_stddev, v_mean + 2*v_stddev],
            v_zscore,
            CASE WHEN v_zscore > 4.0 THEN 'critical' WHEN v_zscore > 3.0 THEN 'warning' ELSE 'info' END,
            'Z-Score Anomalie: ' || p_metric || ' = ' || p_value || ' (μ=' || ROUND(v_mean::numeric,2) || ', σ=' || ROUND(v_stddev::numeric,2) || ', z=' || ROUND(v_zscore::numeric,2) || ')'
        FROM dbai_system.anomaly_models
        WHERE target_metric = p_metric AND is_active
        LIMIT 1;
    END IF;

    RETURN jsonb_build_object(
        'anomaly', v_is_anomaly,
        'zscore', ROUND(v_zscore::numeric, 4),
        'mean', ROUND(v_mean::numeric, 4),
        'stddev', ROUND(v_stddev::numeric, 4),
        'value', p_value
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Metriken-History für Anomalie-Erkennung
CREATE TABLE IF NOT EXISTS dbai_system.metrics_history (
    id              BIGSERIAL PRIMARY KEY,
    metric_name     TEXT NOT NULL,
    value           FLOAT NOT NULL,
    labels          JSONB DEFAULT '{}'::jsonb,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_metrics_name_time ON dbai_system.metrics_history(metric_name, recorded_at DESC);

-- ============================================================================
-- FEATURE 21: App Sandboxing
-- cgroups/Firejail — Apps isoliert laufen lassen
-- ============================================================================

CREATE TABLE IF NOT EXISTS dbai_system.sandbox_profiles (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    profile_name    TEXT NOT NULL UNIQUE,
    sandbox_type    TEXT NOT NULL CHECK (sandbox_type IN ('firejail', 'cgroup', 'namespace', 'bubblewrap', 'docker', 'none')),
    config          JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- cgroup limits
    cpu_limit       FLOAT,          -- 0.0-1.0 (Anteil)
    memory_limit_mb INTEGER,
    io_limit_mbps   INTEGER,
    -- network
    network_mode    TEXT DEFAULT 'restricted' CHECK (network_mode IN ('none', 'restricted', 'full', 'host')),
    allowed_ports   INTEGER[] DEFAULT '{}',
    allowed_hosts   TEXT[] DEFAULT '{}',
    -- filesystem
    read_only_paths TEXT[] DEFAULT ARRAY['/usr', '/bin', '/lib'],
    writable_paths  TEXT[] DEFAULT ARRAY['/tmp'],
    hidden_paths    TEXT[] DEFAULT ARRAY['/etc/shadow', '/etc/gshadow'],
    -- capabilities
    allowed_caps    TEXT[] DEFAULT '{}',
    denied_caps     TEXT[] DEFAULT ARRAY['SYS_ADMIN', 'NET_RAW', 'SYS_PTRACE'],
    is_default      BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dbai_system.sandboxed_apps (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    app_name        TEXT NOT NULL,
    executable_path TEXT NOT NULL,
    profile_id      UUID REFERENCES dbai_system.sandbox_profiles(id),
    pid             INTEGER,
    cgroup_path     TEXT,
    status          TEXT DEFAULT 'stopped' CHECK (status IN ('stopped', 'starting', 'running', 'paused', 'crashed')),
    cpu_usage       FLOAT DEFAULT 0.0,
    memory_usage_mb FLOAT DEFAULT 0.0,
    started_at      TIMESTAMPTZ,
    stopped_at      TIMESTAMPTZ,
    exit_code       INTEGER,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================================
-- FEATURE 22: Network Policy (Firewall)
-- iptables/nftables — Ghost kontrolliert Netzwerk-Policies
-- ============================================================================

CREATE TABLE IF NOT EXISTS dbai_system.firewall_rules (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    rule_name       TEXT NOT NULL,
    chain           TEXT NOT NULL DEFAULT 'INPUT' CHECK (chain IN ('INPUT', 'OUTPUT', 'FORWARD', 'PREROUTING', 'POSTROUTING')),
    action          TEXT NOT NULL DEFAULT 'DROP' CHECK (action IN ('ACCEPT', 'DROP', 'REJECT', 'LOG', 'MARK', 'MASQUERADE', 'SNAT', 'DNAT')),
    protocol        TEXT CHECK (protocol IN ('tcp', 'udp', 'icmp', 'all', NULL)),
    source_ip       TEXT,
    dest_ip         TEXT,
    source_port     TEXT,
    dest_port       TEXT,
    interface_in    TEXT,
    interface_out   TEXT,
    priority        INTEGER DEFAULT 100,
    is_active       BOOLEAN DEFAULT TRUE,
    applied         BOOLEAN DEFAULT FALSE,
    description     TEXT,
    created_by      TEXT DEFAULT 'ghost',
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_fw_chain ON dbai_system.firewall_rules(chain);
CREATE INDEX IF NOT EXISTS idx_fw_active ON dbai_system.firewall_rules(is_active);

CREATE TABLE IF NOT EXISTS dbai_system.firewall_zones (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    zone_name       TEXT NOT NULL UNIQUE,
    description     TEXT,
    default_policy  TEXT DEFAULT 'DROP' CHECK (default_policy IN ('ACCEPT', 'DROP', 'REJECT')),
    interfaces      TEXT[] DEFAULT '{}',
    trusted_sources TEXT[] DEFAULT '{}',
    services        TEXT[] DEFAULT '{}',  -- ssh, http, https, dns, dhcp, etc.
    is_active       BOOLEAN DEFAULT TRUE,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- network_connections already exists from 18-hardware-abstraction.sql
-- Columns: local_address, remote_address, protocol, status, pid, process_name, etc.
-- We reuse the existing table.

-- ============================================================================
-- FEATURE 23: Terminal
-- Persistente Terminal-Sessions auf dem Desktop
-- ============================================================================

CREATE TABLE IF NOT EXISTS dbai_ui.terminal_sessions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID REFERENCES dbai_ui.users(id),
    session_name    TEXT DEFAULT 'Terminal',
    shell           TEXT DEFAULT '/bin/bash',
    pid             INTEGER,
    pts             TEXT,  -- /dev/pts/X
    cwd             TEXT DEFAULT '/home',
    cols            INTEGER DEFAULT 120,
    rows            INTEGER DEFAULT 40,
    env             JSONB DEFAULT '{}'::jsonb,
    status          TEXT DEFAULT 'active' CHECK (status IN ('active', 'closed', 'error')),
    scrollback_lines INTEGER DEFAULT 10000,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at       TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS dbai_ui.terminal_history (
    id              BIGSERIAL PRIMARY KEY,
    session_id      UUID REFERENCES dbai_ui.terminal_sessions(id) ON DELETE CASCADE,
    command         TEXT NOT NULL,
    output          TEXT,
    exit_code       INTEGER,
    cwd             TEXT,
    executed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    duration_ms     INTEGER
);
CREATE INDEX IF NOT EXISTS idx_term_history_session ON dbai_ui.terminal_history(session_id, executed_at DESC);


COMMIT;
