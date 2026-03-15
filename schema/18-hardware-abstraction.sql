-- =============================================================================
-- DBAI Schema 18: Hardware-Abstraktionsschicht (HAL)
-- Die Brücke zwischen physischer Hardware und Datenbank-Tabellen
-- =============================================================================
--
-- "Die Datenbank IST das Betriebssystem. Sie muss ihre Hardware kennen."
--
-- Dieses Schema erweitert dbai_system um:
--   1. GPU-Devices:        Grafikkarten mit VRAM, CUDA-Cores, Takt, Temperatur
--   2. GPU-VRAM-Map:       Welcher Ghost belegt wie viel VRAM auf welcher GPU
--   3. Hardware-Inventory:  Alle Geräte im System als durchsuchbare Tabelle
--   4. CPU-Cores:          Per-Core-Load (nicht nur Durchschnitt)
--   5. Memory-Map:         Prozess → RAM-Verbrauch Zuordnung
--   6. Storage-Health:     SMART-Werte der Festplatten
--   7. Fan-Control:        Lüftersteuerung per SQL UPDATE
--   8. Power-Profile:      Sparmodus ↔ Cyberbrain-Modus
--
-- KEIN neues Schema — alles erweitert dbai_system und dbai_core.
-- =============================================================================

-- =============================================================================
-- 1. HARDWARE INVENTORY — Alle Geräte im System als Tabellenzeilen
-- =============================================================================
-- Jede physische Komponente = eine Zeile. Beim Boot gescannt, bei Hot-Plug aktualisiert.

CREATE TABLE IF NOT EXISTS dbai_system.hardware_inventory (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_class    TEXT NOT NULL CHECK (device_class IN (
                        'cpu', 'gpu', 'memory', 'storage', 'network', 'usb',
                        'pci', 'audio', 'sensor', 'fan', 'motherboard', 'psu', 'other'
                    )),
    device_name     TEXT NOT NULL,
    vendor          TEXT,
    model           TEXT,
    serial_number   TEXT,
    pci_address     TEXT,                   -- z.B. '0000:01:00.0'
    usb_address     TEXT,                   -- z.B. 'Bus 003 Device 002'
    driver_name     TEXT,                   -- Kernel-Treiber (nvidia, nvme, e1000e)
    driver_version  TEXT,
    firmware_version TEXT,
    status          TEXT NOT NULL DEFAULT 'active' CHECK (status IN (
                        'active', 'standby', 'error', 'disabled', 'not_found', 'initializing'
                    )),
    capabilities    JSONB DEFAULT '{}',     -- Gerätespezifische Fähigkeiten
    properties      JSONB DEFAULT '{}',     -- Alle Detail-Infos (flexibel)
    power_state     TEXT DEFAULT 'on' CHECK (power_state IN ('on', 'off', 'standby', 'suspended')),
    discovered_at   TIMESTAMPTZ DEFAULT now(),
    last_seen       TIMESTAMPTZ DEFAULT now(),
    object_id       UUID REFERENCES dbai_core.objects(id), -- Verknüpfung zur Objekt-Registry
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TRIGGER trg_hw_inventory_updated
    BEFORE UPDATE ON dbai_system.hardware_inventory
    FOR EACH ROW EXECUTE FUNCTION dbai_core.update_timestamp();

COMMENT ON TABLE dbai_system.hardware_inventory IS
    'Komplettes Hardware-Inventar: Jedes physische Gerät ist eine Zeile. '
    'Beim Boot von hardware_scanner.py befüllt, bei Hot-Plug aktualisiert.';

-- Index für schnelle Device-Class-Abfragen
CREATE INDEX IF NOT EXISTS idx_hw_inventory_class ON dbai_system.hardware_inventory(device_class);
CREATE INDEX IF NOT EXISTS idx_hw_inventory_status ON dbai_system.hardware_inventory(status);

-- =============================================================================
-- 2. GPU DEVICES — Dedizierte Grafikkarten-Tabelle mit VRAM + Auslastung
-- =============================================================================
-- Jede GPU = eine Zeile. Wird alle 500ms von gpu_manager.py aktualisiert.

CREATE TABLE IF NOT EXISTS dbai_system.gpu_devices (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hw_inventory_id     UUID NOT NULL REFERENCES dbai_system.hardware_inventory(id) ON DELETE CASCADE,
    gpu_index           INTEGER NOT NULL,           -- nvidia-smi Index (0, 1, 2, ...)
    name                TEXT NOT NULL,               -- z.B. 'NVIDIA GeForce RTX 4090'
    vendor              TEXT NOT NULL DEFAULT 'unknown' CHECK (vendor IN ('nvidia', 'amd', 'intel', 'unknown')),
    architecture        TEXT,                        -- z.B. 'Ada Lovelace', 'Ampere', 'RDNA3'
    compute_capability  TEXT,                        -- z.B. '8.9' (CUDA)
    -- VRAM
    vram_total_mb       INTEGER NOT NULL DEFAULT 0,
    vram_used_mb        INTEGER NOT NULL DEFAULT 0,
    vram_free_mb        INTEGER NOT NULL DEFAULT 0,
    vram_reserved_mb    INTEGER NOT NULL DEFAULT 0,  -- Für Ghost-Reservierungen
    -- Auslastung
    gpu_utilization     REAL DEFAULT 0.0   CHECK (gpu_utilization BETWEEN 0 AND 100),
    memory_utilization  REAL DEFAULT 0.0   CHECK (memory_utilization BETWEEN 0 AND 100),
    -- Takt
    clock_graphics_mhz  INTEGER DEFAULT 0,
    clock_memory_mhz    INTEGER DEFAULT 0,
    clock_max_mhz       INTEGER DEFAULT 0,
    -- Thermik & Energie
    temperature_c       REAL DEFAULT 0.0,
    temperature_max_c   REAL DEFAULT 0.0,
    fan_speed_percent   REAL DEFAULT 0.0,
    power_draw_watts    REAL DEFAULT 0.0,
    power_limit_watts   REAL DEFAULT 0.0,
    power_state         TEXT DEFAULT 'P0',           -- P0-P12 NVIDIA Power States
    -- PCIe
    pcie_generation     INTEGER DEFAULT 0,
    pcie_width          INTEGER DEFAULT 0,           -- x16, x8, x4
    pcie_bandwidth_gbps REAL DEFAULT 0.0,
    -- Software
    cuda_version        TEXT,
    driver_version      TEXT,
    -- Status
    is_available        BOOLEAN DEFAULT TRUE,
    is_healthy          BOOLEAN DEFAULT TRUE,
    error_message       TEXT,
    last_updated        TIMESTAMPTZ DEFAULT now(),
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE TRIGGER trg_gpu_devices_updated
    BEFORE UPDATE ON dbai_system.gpu_devices
    FOR EACH ROW EXECUTE FUNCTION dbai_core.update_timestamp();

COMMENT ON TABLE dbai_system.gpu_devices IS
    'Echtzeit GPU-Metriken: VRAM, Auslastung, Thermik, Takt, PCIe. '
    'Jede Grafikkarte eine Zeile. Wird von gpu_manager.py alle 500ms aktualisiert. '
    'VRAM-Reservierungen werden von Ghost-Swap verwaltet.';

CREATE INDEX IF NOT EXISTS idx_gpu_devices_available ON dbai_system.gpu_devices(is_available);

-- =============================================================================
-- 3. GPU VRAM MAP — Welcher Ghost belegt wie viel VRAM auf welcher GPU
-- =============================================================================
-- Wenn ein Ghost geladen wird, reserviert er VRAM. Hier wird das getracked.

CREATE TABLE IF NOT EXISTS dbai_system.gpu_vram_map (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gpu_id          UUID NOT NULL REFERENCES dbai_system.gpu_devices(id) ON DELETE CASCADE,
    model_id        UUID REFERENCES dbai_llm.ghost_models(id) ON DELETE SET NULL,
    role_id         UUID REFERENCES dbai_llm.ghost_roles(id) ON DELETE SET NULL,
    vram_allocated_mb INTEGER NOT NULL DEFAULT 0,
    gpu_layers      INTEGER DEFAULT 0,      -- Wie viele Layers auf dieser GPU
    total_layers    INTEGER DEFAULT 0,      -- Gesamtanzahl Layers im Modell
    allocation_type TEXT DEFAULT 'full' CHECK (allocation_type IN (
                        'full',      -- Ganzes Modell auf einer GPU
                        'split',     -- Modell über mehrere GPUs verteilt
                        'partial',   -- Nur einige Layers auf GPU, Rest CPU
                        'kv_cache'   -- Nur KV-Cache auf GPU
                    )),
    priority        INTEGER DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
    is_active       BOOLEAN DEFAULT TRUE,
    allocated_at    TIMESTAMPTZ DEFAULT now(),
    released_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE dbai_system.gpu_vram_map IS
    'VRAM-Belegungskarte: Welcher Ghost nutzt wie viel Speicher auf welcher GPU. '
    'Bei Multi-GPU hat ein Ghost mehrere Einträge (split). '
    'gpu_layers/total_layers zeigen die Layer-Verteilung.';

CREATE INDEX IF NOT EXISTS idx_vram_map_active ON dbai_system.gpu_vram_map(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_vram_map_gpu ON dbai_system.gpu_vram_map(gpu_id);

-- =============================================================================
-- 4. CPU CORES — Per-Core Auslastung (nicht nur Durchschnitt)
-- =============================================================================
-- Die KI sieht JEDEN einzelnen Kern und seine Last.

CREATE TABLE IF NOT EXISTS dbai_system.cpu_cores (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hw_inventory_id UUID REFERENCES dbai_system.hardware_inventory(id) ON DELETE CASCADE,
    core_id         INTEGER NOT NULL,
    physical_core   INTEGER,                -- Physischer Kern (Hyperthreading-Zuordnung)
    usage_percent   REAL DEFAULT 0.0 CHECK (usage_percent BETWEEN 0 AND 100),
    frequency_mhz   INTEGER DEFAULT 0,
    frequency_max_mhz INTEGER DEFAULT 0,
    temperature_c   REAL,
    -- CPU-Zeiten (Ticks seit letztem Update)
    time_user       BIGINT DEFAULT 0,
    time_system     BIGINT DEFAULT 0,
    time_idle       BIGINT DEFAULT 0,
    time_iowait     BIGINT DEFAULT 0,
    time_irq        BIGINT DEFAULT 0,
    -- Status
    is_online       BOOLEAN DEFAULT TRUE,
    governor        TEXT DEFAULT 'performance', -- powersave/performance/schedutil
    last_updated    TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE dbai_system.cpu_cores IS
    'Per-Core CPU-Metriken: Die KI sieht jeden einzelnen Kern, seine Frequenz, '
    'Temperatur und Governor. Hyperthreading-Mapping über physical_core.';

CREATE INDEX IF NOT EXISTS idx_cpu_cores_hw ON dbai_system.cpu_cores(hw_inventory_id);

-- =============================================================================
-- 5. MEMORY MAP — Welcher Prozess frisst wie viel RAM
-- =============================================================================
-- Das Äquivalent zu 'top' als Tabelle.

CREATE TABLE IF NOT EXISTS dbai_system.memory_map (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pid             INTEGER NOT NULL,
    process_name    TEXT NOT NULL,
    process_type    TEXT DEFAULT 'unknown' CHECK (process_type IN (
                        'system', 'postgresql', 'ghost', 'bridge', 'user', 'unknown'
                    )),
    rss_mb          REAL DEFAULT 0.0,       -- Resident Set Size
    vms_mb          REAL DEFAULT 0.0,       -- Virtual Memory Size
    shared_mb       REAL DEFAULT 0.0,       -- Shared Memory
    swap_mb         REAL DEFAULT 0.0,
    cpu_percent     REAL DEFAULT 0.0,
    num_threads     INTEGER DEFAULT 1,
    -- Zuordnung zum Ghost-System
    ghost_model_id  UUID REFERENCES dbai_llm.ghost_models(id) ON DELETE SET NULL,
    last_updated    TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE dbai_system.memory_map IS
    'Prozess-Memory-Map: Zeigt welcher Prozess wie viel RAM frisst. '
    'ghost_model_id verknüpft LLM-Prozesse mit dem Ghost-System.';

CREATE INDEX IF NOT EXISTS idx_memory_map_type ON dbai_system.memory_map(process_type);

-- =============================================================================
-- 6. STORAGE HEALTH — SMART-Werte der Festplatten
-- =============================================================================
-- Die KI weiß, wann eine Platte stirbt, BEVOR sie ausfällt.

CREATE TABLE IF NOT EXISTS dbai_system.storage_health (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hw_inventory_id UUID REFERENCES dbai_system.hardware_inventory(id) ON DELETE CASCADE,
    device_path     TEXT NOT NULL,           -- /dev/sda, /dev/nvme0n1
    device_type     TEXT DEFAULT 'unknown' CHECK (device_type IN (
                        'hdd', 'ssd', 'nvme', 'usb', 'unknown'
                    )),
    model           TEXT,
    serial          TEXT,
    firmware        TEXT,
    capacity_gb     REAL DEFAULT 0.0,
    -- SMART-Werte (die wichtigsten)
    smart_status    TEXT DEFAULT 'unknown' CHECK (smart_status IN (
                        'healthy', 'warning', 'critical', 'failing', 'unknown'
                    )),
    temperature_c           REAL,
    power_on_hours          INTEGER,
    power_cycle_count       INTEGER,
    reallocated_sectors     INTEGER DEFAULT 0,      -- Defekte Sektoren (kritisch!)
    pending_sectors         INTEGER DEFAULT 0,       -- Verdächtige Sektoren
    uncorrectable_errors    INTEGER DEFAULT 0,
    wear_level_percent      REAL,                    -- SSD/NVMe Verschleiß (0-100)
    total_bytes_written_tb  REAL,                    -- Total Bytes Written
    total_bytes_read_tb     REAL,
    -- NVMe-spezifisch
    nvme_spare_percent      REAL,                    -- Available Spare
    nvme_critical_warning   INTEGER DEFAULT 0,
    -- Vorhersage
    estimated_remaining_life_days INTEGER,
    risk_score              REAL DEFAULT 0.0 CHECK (risk_score BETWEEN 0 AND 100),
    last_updated            TIMESTAMPTZ DEFAULT now(),
    created_at              TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE dbai_system.storage_health IS
    'SMART-Werte und Gesundheitsstatus aller Speichermedien. '
    'Die KI erkennt an reallocated_sectors und wear_level ob eine Platte stirbt. '
    'risk_score wird vom Hardware-Scanner berechnet.';

CREATE INDEX IF NOT EXISTS idx_storage_health_status ON dbai_system.storage_health(smart_status);

-- =============================================================================
-- 7. FAN CONTROL — Lüftersteuerung per SQL
-- =============================================================================
-- UPDATE fans SET target_speed = 100 WHERE name = 'cpu_fan';  →  Realer Lüfter dreht hoch!

CREATE TABLE IF NOT EXISTS dbai_system.fan_control (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hw_inventory_id UUID REFERENCES dbai_system.hardware_inventory(id) ON DELETE CASCADE,
    fan_name        TEXT NOT NULL,            -- cpu_fan, gpu_fan_0, chassis_fan_1
    fan_type        TEXT DEFAULT 'unknown' CHECK (fan_type IN (
                        'cpu', 'gpu', 'chassis', 'psu', 'unknown'
                    )),
    -- Ist-Werte (gelesen)
    current_rpm     INTEGER DEFAULT 0,
    current_percent REAL DEFAULT 0.0 CHECK (current_percent BETWEEN 0 AND 100),
    -- Soll-Werte (geschrieben → Daemon setzt um)
    target_percent  REAL CHECK (target_percent BETWEEN 0 AND 100),
    control_mode    TEXT DEFAULT 'auto' CHECK (control_mode IN ('auto', 'manual', 'curve')),
    -- Kurve (JSON Array von {temp_c, speed_percent} Paaren)
    fan_curve       JSONB DEFAULT '[{"temp_c":30,"speed_percent":20},{"temp_c":50,"speed_percent":50},{"temp_c":70,"speed_percent":80},{"temp_c":85,"speed_percent":100}]',
    min_rpm         INTEGER DEFAULT 0,
    max_rpm         INTEGER DEFAULT 0,
    is_controllable BOOLEAN DEFAULT FALSE,   -- Nicht alle Lüfter sind steuerbar
    last_updated    TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE dbai_system.fan_control IS
    'Lüftersteuerung per SQL UPDATE. Der Hardware-Daemon liest target_percent und '
    'setzt den realen Lüfter entsprechend. Kurven in fan_curve als JSON.';

-- Trigger: NOTIFY wenn jemand target_percent ändert
CREATE OR REPLACE FUNCTION dbai_system.notify_fan_change()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.target_percent IS DISTINCT FROM NEW.target_percent
       OR OLD.control_mode IS DISTINCT FROM NEW.control_mode THEN
        PERFORM pg_notify('fan_control', json_build_object(
            'fan_id', NEW.id,
            'fan_name', NEW.fan_name,
            'target_percent', NEW.target_percent,
            'control_mode', NEW.control_mode
        )::TEXT);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_fan_control_notify
    AFTER UPDATE ON dbai_system.fan_control
    FOR EACH ROW EXECUTE FUNCTION dbai_system.notify_fan_change();

-- =============================================================================
-- 8. POWER PROFILES — Sparmodus ↔ Cyberbrain-Modus
-- =============================================================================
-- Der "Leistungsmodus" des Systems, von der KI gesteuert.

CREATE TABLE IF NOT EXISTS dbai_system.power_profiles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL UNIQUE,
    display_name    TEXT NOT NULL,
    description     TEXT,
    -- CPU-Einstellungen
    cpu_governor    TEXT DEFAULT 'performance' CHECK (cpu_governor IN (
                        'powersave', 'conservative', 'ondemand', 'performance', 'schedutil'
                    )),
    cpu_max_freq_mhz INTEGER,                -- NULL = kein Limit
    cpu_min_freq_mhz INTEGER,
    -- GPU-Einstellungen
    gpu_power_limit_watts INTEGER,           -- NULL = Default
    gpu_persistence_mode  BOOLEAN DEFAULT FALSE,
    gpu_clocks_locked     BOOLEAN DEFAULT FALSE,
    -- Lüfter
    fan_mode        TEXT DEFAULT 'auto' CHECK (fan_mode IN ('auto', 'silent', 'performance', 'full')),
    -- LLM / Ghost
    max_loaded_ghosts INTEGER DEFAULT 1,
    prefer_cpu_inference BOOLEAN DEFAULT FALSE, -- Sparmodus: GPU schlafen lassen
    max_context_size INTEGER DEFAULT 4096,
    -- System
    screen_brightness INTEGER CHECK (screen_brightness BETWEEN 0 AND 100),
    suspend_timeout_min INTEGER,             -- NULL = nie
    is_active       BOOLEAN DEFAULT FALSE,
    activated_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE dbai_system.power_profiles IS
    'Leistungsprofile: Sparmodus → Cyberbrain-Modus. Die KI wechselt das Profil '
    'je nach Aufgabe. CPU-Governor, GPU-Power-Limit, Lüfter und Ghost-Limits.';

-- NOTIFY wenn Profil gewechselt wird
CREATE OR REPLACE FUNCTION dbai_system.activate_power_profile(p_profile_name TEXT)
RETURNS JSONB AS $$
DECLARE
    v_profile dbai_system.power_profiles;
    v_old_profile TEXT;
BEGIN
    -- Altes Profil deaktivieren
    SELECT name INTO v_old_profile FROM dbai_system.power_profiles WHERE is_active = TRUE;
    UPDATE dbai_system.power_profiles SET is_active = FALSE, activated_at = NULL WHERE is_active = TRUE;

    -- Neues Profil aktivieren
    UPDATE dbai_system.power_profiles
    SET is_active = TRUE, activated_at = now()
    WHERE name = p_profile_name
    RETURNING * INTO v_profile;

    IF v_profile.id IS NULL THEN
        RAISE EXCEPTION 'Power-Profil "%" nicht gefunden', p_profile_name;
    END IF;

    -- NOTIFY an alle Daemons
    PERFORM pg_notify('power_profile_change', json_build_object(
        'profile', p_profile_name,
        'old_profile', v_old_profile,
        'cpu_governor', v_profile.cpu_governor,
        'gpu_power_limit', v_profile.gpu_power_limit_watts,
        'fan_mode', v_profile.fan_mode,
        'max_ghosts', v_profile.max_loaded_ghosts,
        'prefer_cpu', v_profile.prefer_cpu_inference
    )::TEXT);

    RETURN json_build_object(
        'success', TRUE,
        'activated', p_profile_name,
        'deactivated', v_old_profile
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION dbai_system.activate_power_profile IS
    'Wechselt das aktive Power-Profil. Sendet NOTIFY an Hardware-Daemons.';

-- =============================================================================
-- 9. NETWORK TRAFFIC — Live-Datenströme als Tabelle (erweitert)
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_system.network_connections (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hw_inventory_id UUID REFERENCES dbai_system.hardware_inventory(id) ON DELETE CASCADE,
    local_address   TEXT,
    local_port      INTEGER,
    remote_address  TEXT,
    remote_port     INTEGER,
    protocol        TEXT DEFAULT 'tcp' CHECK (protocol IN ('tcp', 'udp', 'tcp6', 'udp6')),
    status          TEXT,                    -- ESTABLISHED, LISTEN, TIME_WAIT, etc.
    pid             INTEGER,
    process_name    TEXT,
    bytes_sent      BIGINT DEFAULT 0,
    bytes_recv      BIGINT DEFAULT 0,
    last_updated    TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE dbai_system.network_connections IS
    'Aktive Netzwerkverbindungen als Tabelle — das Äquivalent zu netstat/ss.';

-- =============================================================================
-- 10. HOT-PLUG EVENTS — Append-Only Log für Hardware-Änderungen
-- =============================================================================
-- Wenn eine neue Platte eingesteckt wird, erscheint sie hier.

CREATE TABLE IF NOT EXISTS dbai_system.hotplug_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type      TEXT NOT NULL CHECK (event_type IN ('add', 'remove', 'change', 'bind', 'unbind')),
    device_class    TEXT NOT NULL,
    device_name     TEXT NOT NULL,
    subsystem       TEXT,                    -- block, usb, pci, net
    vendor          TEXT,
    model           TEXT,
    serial          TEXT,
    properties      JSONB DEFAULT '{}',
    -- Wie hat das System reagiert?
    action_taken    TEXT,                     -- z.B. 'auto_mount', 'driver_loaded', 'ignored'
    ghost_notified  BOOLEAN DEFAULT FALSE,    -- Wurde die KI benachrichtigt?
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Append-Only: NIEMALS Hot-Plug-Events löschen
CREATE OR REPLACE FUNCTION dbai_system.protect_hotplug_events()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Hot-Plug Events sind Append-Only — NIEMALS löschen oder ändern!';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_protect_hotplug
    BEFORE UPDATE OR DELETE ON dbai_system.hotplug_events
    FOR EACH ROW EXECUTE FUNCTION dbai_system.protect_hotplug_events();

COMMENT ON TABLE dbai_system.hotplug_events IS
    'Append-Only Log aller Hot-Plug-Ereignisse. NIEMALS löschbar. '
    'Neue Hardware → neue Zeile → Ghost wird benachrichtigt.';

-- NOTIFY bei Hot-Plug
CREATE OR REPLACE FUNCTION dbai_system.notify_hotplug()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM pg_notify('hotplug_event', json_build_object(
        'event_type', NEW.event_type,
        'device_class', NEW.device_class,
        'device_name', NEW.device_name,
        'subsystem', NEW.subsystem,
        'vendor', NEW.vendor,
        'model', NEW.model
    )::TEXT);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_hotplug_notify
    AFTER INSERT ON dbai_system.hotplug_events
    FOR EACH ROW EXECUTE FUNCTION dbai_system.notify_hotplug();

-- =============================================================================
-- 11. VIEWS — Hardware auf einen Blick
-- =============================================================================

-- GPU-Übersicht mit VRAM-Belegung
CREATE OR REPLACE VIEW dbai_system.vw_gpu_overview AS
SELECT
    g.gpu_index,
    g.name AS gpu_name,
    g.vendor,
    g.vram_total_mb,
    g.vram_used_mb,
    g.vram_free_mb,
    g.vram_reserved_mb,
    ROUND((g.vram_used_mb::NUMERIC / NULLIF(g.vram_total_mb, 0) * 100), 1) AS vram_usage_percent,
    g.gpu_utilization,
    g.temperature_c,
    g.power_draw_watts,
    g.power_state,
    g.is_available,
    g.is_healthy,
    -- Geladene Ghosts auf dieser GPU
    COALESCE(
        (SELECT json_agg(json_build_object(
            'model', gm.name,
            'role', gr.name,
            'vram_mb', vm.vram_allocated_mb,
            'layers', vm.gpu_layers
        ))
        FROM dbai_system.gpu_vram_map vm
        JOIN dbai_llm.ghost_models gm ON vm.model_id = gm.id
        LEFT JOIN dbai_llm.ghost_roles gr ON vm.role_id = gr.id
        WHERE vm.gpu_id = g.id AND vm.is_active = TRUE),
        '[]'::JSON
    ) AS loaded_ghosts
FROM dbai_system.gpu_devices g
ORDER BY g.gpu_index;

COMMENT ON VIEW dbai_system.vw_gpu_overview IS
    'GPU-Dashboard: VRAM, Auslastung, Temperatur, geladene Ghosts — alles auf einen Blick.';

-- Hardware-Gesamtübersicht
CREATE OR REPLACE VIEW dbai_system.vw_hardware_summary AS
SELECT
    device_class,
    COUNT(*) AS device_count,
    COUNT(*) FILTER (WHERE status = 'active') AS active_count,
    COUNT(*) FILTER (WHERE status = 'error') AS error_count,
    json_agg(json_build_object(
        'name', device_name,
        'vendor', vendor,
        'model', model,
        'status', status
    ) ORDER BY device_name) AS devices
FROM dbai_system.hardware_inventory
GROUP BY device_class
ORDER BY device_class;

COMMENT ON VIEW dbai_system.vw_hardware_summary IS
    'Hardware-Inventar gruppiert nach Geräteklasse mit Zähler und Details.';

-- Aktives Power-Profil
CREATE OR REPLACE VIEW dbai_system.vw_active_power_profile AS
SELECT * FROM dbai_system.power_profiles WHERE is_active = TRUE;

-- =============================================================================
-- 12. FUNKTIONEN — GPU-Ressourcen-Management
-- =============================================================================

-- Prüft ob genug VRAM auf einer GPU frei ist
CREATE OR REPLACE FUNCTION dbai_system.check_gpu_available(
    p_required_vram_mb INTEGER,
    p_preferred_gpu_index INTEGER DEFAULT NULL
)
RETURNS JSONB AS $$
DECLARE
    v_gpu RECORD;
    v_result JSONB := '[]'::JSONB;
BEGIN
    FOR v_gpu IN
        SELECT
            g.id,
            g.gpu_index,
            g.name,
            g.vram_total_mb,
            g.vram_used_mb,
            g.vram_free_mb - g.vram_reserved_mb AS available_mb,
            g.is_available,
            g.is_healthy
        FROM dbai_system.gpu_devices g
        WHERE g.is_available = TRUE AND g.is_healthy = TRUE
        ORDER BY
            CASE WHEN p_preferred_gpu_index IS NOT NULL AND g.gpu_index = p_preferred_gpu_index THEN 0 ELSE 1 END,
            (g.vram_free_mb - g.vram_reserved_mb) DESC
    LOOP
        IF v_gpu.available_mb >= p_required_vram_mb THEN
            v_result := v_result || jsonb_build_object(
                'gpu_id', v_gpu.id,
                'gpu_index', v_gpu.gpu_index,
                'gpu_name', v_gpu.name,
                'available_mb', v_gpu.available_mb,
                'fits', TRUE,
                'allocation_type', 'full'
            );
        END IF;
    END LOOP;

    -- Multi-GPU Splitting prüfen wenn kein einzelner GPU reicht
    IF jsonb_array_length(v_result) = 0 THEN
        DECLARE
            v_total_available INTEGER := 0;
            v_gpu_list JSONB := '[]'::JSONB;
        BEGIN
            FOR v_gpu IN
                SELECT g.id, g.gpu_index, g.name,
                       g.vram_free_mb - g.vram_reserved_mb AS available_mb
                FROM dbai_system.gpu_devices g
                WHERE g.is_available = TRUE AND g.is_healthy = TRUE
                  AND (g.vram_free_mb - g.vram_reserved_mb) > 100  -- Mindestens 100MB frei
                ORDER BY (g.vram_free_mb - g.vram_reserved_mb) DESC
            LOOP
                v_total_available := v_total_available + v_gpu.available_mb;
                v_gpu_list := v_gpu_list || jsonb_build_object(
                    'gpu_id', v_gpu.id,
                    'gpu_index', v_gpu.gpu_index,
                    'available_mb', v_gpu.available_mb
                );
            END LOOP;

            IF v_total_available >= p_required_vram_mb THEN
                v_result := jsonb_build_array(jsonb_build_object(
                    'fits', TRUE,
                    'allocation_type', 'split',
                    'total_available_mb', v_total_available,
                    'gpus', v_gpu_list
                ));
            END IF;
        END;
    END IF;

    IF jsonb_array_length(v_result) = 0 THEN
        RETURN jsonb_build_object(
            'fits', FALSE,
            'required_mb', p_required_vram_mb,
            'reason', 'Nicht genug VRAM verfügbar — weder Single-GPU noch Multi-GPU Split'
        );
    END IF;

    RETURN jsonb_build_object('fits', TRUE, 'options', v_result);
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION dbai_system.check_gpu_available IS
    'Prüft ob ein Ghost auf eine GPU passt. Unterstützt Single-GPU und Multi-GPU Splitting.';

-- VRAM für einen Ghost reservieren
CREATE OR REPLACE FUNCTION dbai_system.allocate_vram(
    p_gpu_id UUID,
    p_model_id UUID,
    p_role_id UUID,
    p_vram_mb INTEGER,
    p_gpu_layers INTEGER DEFAULT -1,
    p_total_layers INTEGER DEFAULT 0,
    p_allocation_type TEXT DEFAULT 'full'
)
RETURNS UUID AS $$
DECLARE
    v_allocation_id UUID;
    v_gpu RECORD;
BEGIN
    -- GPU prüfen
    SELECT * INTO v_gpu FROM dbai_system.gpu_devices WHERE id = p_gpu_id;
    IF v_gpu.id IS NULL THEN
        RAISE EXCEPTION 'GPU % nicht gefunden', p_gpu_id;
    END IF;

    IF (v_gpu.vram_free_mb - v_gpu.vram_reserved_mb) < p_vram_mb THEN
        RAISE EXCEPTION 'Nicht genug VRAM auf GPU % (frei: %MB, benötigt: %MB)',
            v_gpu.gpu_index, (v_gpu.vram_free_mb - v_gpu.vram_reserved_mb), p_vram_mb;
    END IF;

    -- Alte Allokation für gleiche Rolle deaktivieren
    UPDATE dbai_system.gpu_vram_map
    SET is_active = FALSE, released_at = now()
    WHERE role_id = p_role_id AND is_active = TRUE;

    -- Neue Allokation erstellen
    INSERT INTO dbai_system.gpu_vram_map
        (gpu_id, model_id, role_id, vram_allocated_mb, gpu_layers, total_layers, allocation_type)
    VALUES
        (p_gpu_id, p_model_id, p_role_id, p_vram_mb, p_gpu_layers, p_total_layers, p_allocation_type)
    RETURNING id INTO v_allocation_id;

    -- Reservierung auf GPU aktualisieren
    UPDATE dbai_system.gpu_devices
    SET vram_reserved_mb = vram_reserved_mb + p_vram_mb
    WHERE id = p_gpu_id;

    RETURN v_allocation_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- VRAM freigeben
CREATE OR REPLACE FUNCTION dbai_system.release_vram(p_model_id UUID)
RETURNS VOID AS $$
DECLARE
    v_alloc RECORD;
BEGIN
    FOR v_alloc IN
        SELECT * FROM dbai_system.gpu_vram_map
        WHERE model_id = p_model_id AND is_active = TRUE
    LOOP
        -- Allokation deaktivieren
        UPDATE dbai_system.gpu_vram_map
        SET is_active = FALSE, released_at = now()
        WHERE id = v_alloc.id;

        -- Reservierung zurückgeben
        UPDATE dbai_system.gpu_devices
        SET vram_reserved_mb = GREATEST(0, vram_reserved_mb - v_alloc.vram_allocated_mb)
        WHERE id = v_alloc.gpu_id;
    END LOOP;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION dbai_system.release_vram IS
    'Gibt den VRAM eines entladenen Ghost-Modells frei. Aktualisiert gpu_devices.vram_reserved_mb.';

-- =============================================================================
-- 13. ROW LEVEL SECURITY
-- =============================================================================

ALTER TABLE dbai_system.hardware_inventory ENABLE ROW LEVEL SECURITY;
ALTER TABLE dbai_system.gpu_devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE dbai_system.gpu_vram_map ENABLE ROW LEVEL SECURITY;
ALTER TABLE dbai_system.cpu_cores ENABLE ROW LEVEL SECURITY;
ALTER TABLE dbai_system.memory_map ENABLE ROW LEVEL SECURITY;
ALTER TABLE dbai_system.storage_health ENABLE ROW LEVEL SECURITY;
ALTER TABLE dbai_system.fan_control ENABLE ROW LEVEL SECURITY;
ALTER TABLE dbai_system.power_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE dbai_system.network_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE dbai_system.hotplug_events ENABLE ROW LEVEL SECURITY;

-- System-Rolle: Voller Zugriff
CREATE POLICY hal_system_all ON dbai_system.hardware_inventory FOR ALL TO dbai_system USING (TRUE);
CREATE POLICY gpu_system_all ON dbai_system.gpu_devices FOR ALL TO dbai_system USING (TRUE);
CREATE POLICY vram_system_all ON dbai_system.gpu_vram_map FOR ALL TO dbai_system USING (TRUE);
CREATE POLICY cores_system_all ON dbai_system.cpu_cores FOR ALL TO dbai_system USING (TRUE);
CREATE POLICY memmap_system_all ON dbai_system.memory_map FOR ALL TO dbai_system USING (TRUE);
CREATE POLICY storage_system_all ON dbai_system.storage_health FOR ALL TO dbai_system USING (TRUE);
CREATE POLICY fan_system_all ON dbai_system.fan_control FOR ALL TO dbai_system USING (TRUE);
CREATE POLICY power_system_all ON dbai_system.power_profiles FOR ALL TO dbai_system USING (TRUE);
CREATE POLICY netconn_system_all ON dbai_system.network_connections FOR ALL TO dbai_system USING (TRUE);
CREATE POLICY hotplug_system_all ON dbai_system.hotplug_events FOR ALL TO dbai_system USING (TRUE);

-- Monitor-Rolle: Nur lesen
CREATE POLICY hal_monitor_read ON dbai_system.hardware_inventory FOR SELECT TO dbai_monitor USING (TRUE);
CREATE POLICY gpu_monitor_read ON dbai_system.gpu_devices FOR SELECT TO dbai_monitor USING (TRUE);
CREATE POLICY vram_monitor_read ON dbai_system.gpu_vram_map FOR SELECT TO dbai_monitor USING (TRUE);
CREATE POLICY cores_monitor_read ON dbai_system.cpu_cores FOR SELECT TO dbai_monitor USING (TRUE);
CREATE POLICY memmap_monitor_read ON dbai_system.memory_map FOR SELECT TO dbai_monitor USING (TRUE);
CREATE POLICY storage_monitor_read ON dbai_system.storage_health FOR SELECT TO dbai_monitor USING (TRUE);
CREATE POLICY fan_monitor_read ON dbai_system.fan_control FOR SELECT TO dbai_monitor USING (TRUE);
CREATE POLICY power_monitor_read ON dbai_system.power_profiles FOR SELECT TO dbai_monitor USING (TRUE);
CREATE POLICY netconn_monitor_read ON dbai_system.network_connections FOR SELECT TO dbai_monitor USING (TRUE);
CREATE POLICY hotplug_monitor_read ON dbai_system.hotplug_events FOR SELECT TO dbai_monitor USING (TRUE);

-- LLM-Rolle: GPU und VRAM lesen (braucht es für Swap-Entscheidungen)
CREATE POLICY gpu_llm_read ON dbai_system.gpu_devices FOR SELECT TO dbai_llm USING (TRUE);
CREATE POLICY vram_llm_read ON dbai_system.gpu_vram_map FOR SELECT TO dbai_llm USING (TRUE);
CREATE POLICY power_llm_read ON dbai_system.power_profiles FOR SELECT TO dbai_llm USING (TRUE);

-- =============================================================================
-- ENDE Schema 18: Hardware-Abstraktionsschicht
-- =============================================================================
