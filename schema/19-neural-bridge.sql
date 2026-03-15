-- =============================================================================
-- DBAI Schema 19: Neural Bridge — Boot-Konfiguration & Treiber-Modell
-- =============================================================================
--
-- "Die erste Tabelle die geladen wird, bestimmt welcher Ghost die Kontrolle
--  übernimmt. Das ist der Zündschlüssel des Systems."
--
-- Dieses Schema definiert:
--   1. Boot-Konfiguration:    Welcher Ghost startet, in welcher Reihenfolge
--   2. Neural-Bridge Config:  Verbindung zwischen Hardware und Ghost-System
--   3. Driver Registry:       Modulare Treiber (Python-Skript + SQL-View)
--   4. System-Capabilities:   Was kann das System? (automatisch erkannt)
--   5. Performance-Benchmarks: Wie schnell ist welcher Ghost auf dieser Hardware?
--
-- KEIN neues Schema — erweitert dbai_core und dbai_llm.
-- =============================================================================

-- =============================================================================
-- 1. BOOT CONFIGURATION — Die allererste Tabelle nach dem Hochfahren
-- =============================================================================
-- Legt fest: Welcher Ghost übernimmt beim Start? CPU-only oder GPU? Welches Profil?

CREATE TABLE IF NOT EXISTS dbai_core.boot_config (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config_name         TEXT NOT NULL UNIQUE,
    description         TEXT,
    -- Ghost-Einstellungen beim Boot
    boot_ghost_role     TEXT DEFAULT 'sysadmin',     -- Welche Rolle beim Boot aktiv
    boot_ghost_model    TEXT,                         -- Welches Modell (Name aus ghost_models)
    auto_load_ghost     BOOLEAN DEFAULT TRUE,         -- Ghost automatisch beim Boot laden?
    -- Hardware-Modus beim Boot
    boot_power_profile  TEXT DEFAULT 'balanced',      -- Power-Profil beim Start
    gpu_mode            TEXT DEFAULT 'auto' CHECK (gpu_mode IN (
                            'auto',       -- Automatisch erkennen und nutzen
                            'force_gpu',  -- GPU erzwingen (Fehler wenn keine vorhanden)
                            'cpu_only',   -- GPU ignorieren (Sparmodus)
                            'multi_gpu',  -- Multi-GPU aktivieren
                            'disabled'    -- Keine KI beim Boot
                        )),
    -- Welche Daemons beim Boot starten
    start_hardware_scanner  BOOLEAN DEFAULT TRUE,
    start_gpu_manager       BOOLEAN DEFAULT TRUE,
    start_ghost_dispatcher  BOOLEAN DEFAULT TRUE,
    start_web_server        BOOLEAN DEFAULT TRUE,
    start_hardware_monitor  BOOLEAN DEFAULT TRUE,
    -- Timeouts
    ghost_load_timeout_sec  INTEGER DEFAULT 120,      -- Max. Wartezeit für Ghost-Laden
    hardware_scan_timeout_sec INTEGER DEFAULT 30,
    -- Kiosk-Modus (Double-Boot Ansatz)
    kiosk_mode              BOOLEAN DEFAULT FALSE,    -- Vollbild, kein Terminal
    kiosk_url               TEXT DEFAULT 'http://localhost:8420',
    auto_login_user         TEXT,                      -- Automatisch einloggen
    -- Status
    is_default              BOOLEAN DEFAULT FALSE,
    boot_count              INTEGER DEFAULT 0,
    last_boot               TIMESTAMPTZ,
    avg_boot_time_sec       REAL,
    created_at              TIMESTAMPTZ DEFAULT now(),
    updated_at              TIMESTAMPTZ DEFAULT now()
);

CREATE TRIGGER trg_boot_config_updated
    BEFORE UPDATE ON dbai_core.boot_config
    FOR EACH ROW EXECUTE FUNCTION dbai_core.update_timestamp();

COMMENT ON TABLE dbai_core.boot_config IS
    'DIE Boot-Tabelle: Bestimmt welcher Ghost beim Start die Kontrolle übernimmt, '
    'welches Power-Profil aktiv ist, ob GPU genutzt wird, und welche Daemons starten. '
    'Im Kiosk-Modus sieht der User NUR das Web-UI — nie ein Terminal.';

-- Nur eine Default-Config erlaubt
CREATE UNIQUE INDEX IF NOT EXISTS idx_boot_config_default
    ON dbai_core.boot_config(is_default) WHERE is_default = TRUE;

-- =============================================================================
-- 2. NEURAL BRIDGE CONFIG — Verbindung Hardware ↔ Ghost
-- =============================================================================
-- Konfiguriert wie die "Nervenbahnen" zwischen Hardware und KI funktionieren.

CREATE TABLE IF NOT EXISTS dbai_core.neural_bridge_config (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key             TEXT NOT NULL UNIQUE,
    value           JSONB NOT NULL,
    category        TEXT NOT NULL CHECK (category IN (
                        'gpu', 'cpu', 'memory', 'storage', 'network',
                        'ghost', 'bridge', 'monitoring', 'security'
                    )),
    description     TEXT,
    is_runtime      BOOLEAN DEFAULT FALSE,   -- Kann zur Laufzeit geändert werden
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TRIGGER trg_neural_bridge_config_updated
    BEFORE UPDATE ON dbai_core.neural_bridge_config
    FOR EACH ROW EXECUTE FUNCTION dbai_core.update_timestamp();

COMMENT ON TABLE dbai_core.neural_bridge_config IS
    'Neural-Bridge-Konfiguration: Wie die Hardware-Daemons mit dem Ghost-System kommunizieren. '
    'GPU-Schwellwerte, Monitoring-Intervalle, Auto-Swap-Regeln.';

-- =============================================================================
-- 3. DRIVER REGISTRY — Modulare Treiber (Python + SQL)
-- =============================================================================
-- Ein "Treiber" in DBAI = Python-Skript (liest/schreibt Hardware) + SQL-View (Darstellung)

CREATE TABLE IF NOT EXISTS dbai_core.driver_registry (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    driver_name     TEXT NOT NULL UNIQUE,
    display_name    TEXT NOT NULL,
    description     TEXT,
    driver_type     TEXT NOT NULL CHECK (driver_type IN (
                        'gpu', 'storage', 'network', 'input', 'display',
                        'audio', 'sensor', 'fan', 'usb', 'power', 'virtual'
                    )),
    -- Python-Seite des Treibers
    python_module   TEXT,                    -- z.B. 'bridge.gpu_manager'
    python_class    TEXT,                    -- z.B. 'GPUManager'
    python_method   TEXT,                    -- z.B. 'scan' (Entry-Point)
    -- SQL-Seite des Treibers
    sql_view        TEXT,                    -- z.B. 'dbai_system.vw_gpu_overview'
    sql_table       TEXT,                    -- z.B. 'dbai_system.gpu_devices'
    -- Hardware-Erkennung
    vendor_match    TEXT,                    -- Regex für Vendor (z.B. 'nvidia|NVIDIA')
    device_match    TEXT,                    -- Regex für Device-Name
    subsystem       TEXT,                    -- udev Subsystem (pci, usb, block, net)
    -- Status
    is_loaded       BOOLEAN DEFAULT FALSE,
    is_essential    BOOLEAN DEFAULT FALSE,    -- System-kritisch?
    auto_load       BOOLEAN DEFAULT TRUE,     -- Automatisch beim Boot laden?
    load_order      INTEGER DEFAULT 50,       -- Reihenfolge (niedriger = früher)
    -- Laufzeit-Info
    pid             INTEGER,                  -- PID des Python-Prozesses
    last_scan       TIMESTAMPTZ,
    scan_interval_ms INTEGER DEFAULT 1000,    -- Wie oft scannt der Treiber
    error_count     INTEGER DEFAULT 0,
    last_error      TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TRIGGER trg_driver_registry_updated
    BEFORE UPDATE ON dbai_core.driver_registry
    FOR EACH ROW EXECUTE FUNCTION dbai_core.update_timestamp();

COMMENT ON TABLE dbai_core.driver_registry IS
    'Modulares Treiber-System: Jeder Treiber ist ein Paar aus Python-Skript und SQL-View. '
    'Hot-Plug: Neue Hardware → vendor_match prüfen → passenden Treiber automatisch laden.';

CREATE INDEX IF NOT EXISTS idx_driver_registry_type ON dbai_core.driver_registry(driver_type);

-- =============================================================================
-- 4. SYSTEM CAPABILITIES — Was kann diese Maschine?
-- =============================================================================
-- Automatisch erkannt: Hat sie CUDA? Wie viel VRAM? NVMe? 10G Netzwerk?

CREATE TABLE IF NOT EXISTS dbai_core.system_capabilities (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    capability      TEXT NOT NULL UNIQUE,
    category        TEXT NOT NULL CHECK (category IN (
                        'compute', 'memory', 'storage', 'network', 'gpu', 'security', 'other'
                    )),
    description     TEXT,
    is_available    BOOLEAN DEFAULT FALSE,
    details         JSONB DEFAULT '{}',      -- Spezifische Werte
    detected_at     TIMESTAMPTZ DEFAULT now(),
    last_verified   TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE dbai_core.system_capabilities IS
    'Automatisch erkannte System-Fähigkeiten: CUDA, AVX-512, NVMe, 10GbE, ECC-RAM, etc. '
    'Der Ghost fragt hier nach, ob eine Aufgabe möglich ist.';

-- =============================================================================
-- 5. PERFORMANCE BENCHMARKS — Wie schnell läuft welcher Ghost?
-- =============================================================================
-- Gespeicherte Benchmark-Ergebnisse für Ghost/Hardware-Kombinationen.

CREATE TABLE IF NOT EXISTS dbai_llm.ghost_benchmarks (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id            UUID NOT NULL REFERENCES dbai_llm.ghost_models(id) ON DELETE CASCADE,
    -- Hardware-Kontext
    gpu_name            TEXT,
    gpu_vram_mb         INTEGER,
    cpu_model           TEXT,
    ram_total_mb        INTEGER,
    -- Benchmark-Ergebnisse
    tokens_per_second   REAL,                -- Generierung
    prompt_eval_tps     REAL,                -- Prompt-Evaluierung
    time_to_first_token_ms REAL,
    context_size        INTEGER,
    batch_size          INTEGER,
    -- Einstellungen
    n_gpu_layers        INTEGER,
    quantization        TEXT,
    backend             TEXT DEFAULT 'llama.cpp',
    -- Meta
    benchmark_date      TIMESTAMPTZ DEFAULT now(),
    benchmark_duration_sec REAL,
    notes               TEXT
);

COMMENT ON TABLE dbai_llm.ghost_benchmarks IS
    'Performance-Daten: Wie schnell läuft Modell X auf Hardware Y? '
    'Wird nach jedem Ghost-Load automatisch gemessen (Warm-up-Prompt). '
    'Die KI nutzt das für optimale Modell-Zuweisung.';

CREATE INDEX IF NOT EXISTS idx_benchmarks_model ON dbai_llm.ghost_benchmarks(model_id);

-- =============================================================================
-- 6. BOOT-FUNKTION — System hochfahren
-- =============================================================================

CREATE OR REPLACE FUNCTION dbai_core.get_boot_config()
RETURNS JSONB AS $$
DECLARE
    v_config RECORD;
    v_ghost RECORD;
    v_profile RECORD;
BEGIN
    -- Default Boot-Config laden
    SELECT * INTO v_config FROM dbai_core.boot_config WHERE is_default = TRUE;

    IF v_config.id IS NULL THEN
        -- Fallback: Erste Config nehmen
        SELECT * INTO v_config FROM dbai_core.boot_config ORDER BY created_at LIMIT 1;
    END IF;

    IF v_config.id IS NULL THEN
        RETURN jsonb_build_object(
            'error', 'Keine Boot-Konfiguration gefunden',
            'action', 'INSERT INTO dbai_core.boot_config (...) VALUES (...)'
        );
    END IF;

    -- Boot-Zähler erhöhen
    UPDATE dbai_core.boot_config
    SET boot_count = boot_count + 1, last_boot = now()
    WHERE id = v_config.id;

    -- Ghost-Modell für Boot-Rolle finden
    SELECT gm.name, gm.required_vram_mb, gm.requires_gpu
    INTO v_ghost
    FROM dbai_llm.active_ghosts ag
    JOIN dbai_llm.ghost_roles gr ON ag.role_id = gr.id
    JOIN dbai_llm.ghost_models gm ON ag.model_id = gm.id
    WHERE gr.name = v_config.boot_ghost_role AND ag.is_active = TRUE;

    RETURN jsonb_build_object(
        'config_name', v_config.config_name,
        'boot_ghost_role', v_config.boot_ghost_role,
        'boot_ghost_model', COALESCE(v_ghost.name, v_config.boot_ghost_model),
        'auto_load_ghost', v_config.auto_load_ghost,
        'gpu_mode', v_config.gpu_mode,
        'boot_power_profile', v_config.boot_power_profile,
        'requires_gpu', COALESCE(v_ghost.requires_gpu, FALSE),
        'required_vram_mb', COALESCE(v_ghost.required_vram_mb, 0),
        'daemons', jsonb_build_object(
            'hardware_scanner', v_config.start_hardware_scanner,
            'gpu_manager', v_config.start_gpu_manager,
            'ghost_dispatcher', v_config.start_ghost_dispatcher,
            'web_server', v_config.start_web_server,
            'hardware_monitor', v_config.start_hardware_monitor
        ),
        'kiosk_mode', v_config.kiosk_mode,
        'kiosk_url', v_config.kiosk_url,
        'timeouts', jsonb_build_object(
            'ghost_load', v_config.ghost_load_timeout_sec,
            'hardware_scan', v_config.hardware_scan_timeout_sec
        ),
        'boot_count', v_config.boot_count
    );
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION dbai_core.get_boot_config IS
    'Liefert die komplette Boot-Konfiguration als JSON. '
    'Wird beim Systemstart als ERSTES aufgerufen — der Zündschlüssel.';

-- =============================================================================
-- 7. AUTO-SWAP — Ghost automatisch wechseln bei Hardware-Änderung
-- =============================================================================

CREATE OR REPLACE FUNCTION dbai_llm.auto_swap_on_gpu_change()
RETURNS TRIGGER AS $$
DECLARE
    v_active RECORD;
    v_better RECORD;
BEGIN
    -- Wenn eine GPU nicht mehr verfügbar ist, prüfe ob betroffene Ghosts migriert werden müssen
    IF NEW.is_available = FALSE AND OLD.is_available = TRUE THEN
        -- Finde alle Ghosts auf dieser GPU
        FOR v_active IN
            SELECT vm.model_id, vm.role_id, gm.name AS model_name, gm.required_vram_mb
            FROM dbai_system.gpu_vram_map vm
            JOIN dbai_llm.ghost_models gm ON vm.model_id = gm.id
            WHERE vm.gpu_id = NEW.id AND vm.is_active = TRUE
        LOOP
            -- NOTIFY: Ghost muss migriert werden
            PERFORM pg_notify('ghost_gpu_migration', json_build_object(
                'model_id', v_active.model_id,
                'model_name', v_active.model_name,
                'role_id', v_active.role_id,
                'reason', 'GPU ' || NEW.gpu_index || ' nicht mehr verfügbar',
                'required_vram_mb', v_active.required_vram_mb,
                'failed_gpu', NEW.gpu_index
            )::TEXT);
        END LOOP;
    END IF;

    -- Wenn eine neue GPU verfügbar wird, benachrichtige Ghost-Dispatcher
    IF NEW.is_available = TRUE AND OLD.is_available = FALSE THEN
        PERFORM pg_notify('ghost_gpu_available', json_build_object(
            'gpu_id', NEW.id,
            'gpu_index', NEW.gpu_index,
            'gpu_name', NEW.name,
            'vram_total_mb', NEW.vram_total_mb,
            'vram_free_mb', NEW.vram_free_mb
        )::TEXT);
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_gpu_availability_change
    AFTER UPDATE OF is_available ON dbai_system.gpu_devices
    FOR EACH ROW EXECUTE FUNCTION dbai_llm.auto_swap_on_gpu_change();

-- =============================================================================
-- 8. HOT-PLUG DRIVER MATCHING — Automatisch passenden Treiber finden
-- =============================================================================

CREATE OR REPLACE FUNCTION dbai_core.match_driver_for_device(
    p_device_class TEXT,
    p_vendor TEXT,
    p_device_name TEXT
)
RETURNS TABLE(driver_name TEXT, driver_type TEXT, python_module TEXT, python_class TEXT) AS $$
BEGIN
    RETURN QUERY
    SELECT
        dr.driver_name,
        dr.driver_type,
        dr.python_module,
        dr.python_class
    FROM dbai_core.driver_registry dr
    WHERE dr.auto_load = TRUE
      AND (
          dr.driver_type = p_device_class
          OR (dr.vendor_match IS NOT NULL AND p_vendor ~* dr.vendor_match)
          OR (dr.device_match IS NOT NULL AND p_device_name ~* dr.device_match)
      )
    ORDER BY
        CASE WHEN dr.vendor_match IS NOT NULL AND p_vendor ~* dr.vendor_match THEN 0 ELSE 1 END,
        dr.load_order;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION dbai_core.match_driver_for_device IS
    'Hot-Plug: Findet den passenden Treiber für ein neues Gerät. '
    'Matcht gegen vendor_match und device_match Regex.';

-- =============================================================================
-- 9. ROW LEVEL SECURITY
-- =============================================================================

ALTER TABLE dbai_core.boot_config ENABLE ROW LEVEL SECURITY;
ALTER TABLE dbai_core.neural_bridge_config ENABLE ROW LEVEL SECURITY;
ALTER TABLE dbai_core.driver_registry ENABLE ROW LEVEL SECURITY;
ALTER TABLE dbai_core.system_capabilities ENABLE ROW LEVEL SECURITY;
ALTER TABLE dbai_llm.ghost_benchmarks ENABLE ROW LEVEL SECURITY;

CREATE POLICY boot_system_all ON dbai_core.boot_config FOR ALL TO dbai_system USING (TRUE);
CREATE POLICY neural_system_all ON dbai_core.neural_bridge_config FOR ALL TO dbai_system USING (TRUE);
CREATE POLICY driver_system_all ON dbai_core.driver_registry FOR ALL TO dbai_system USING (TRUE);
CREATE POLICY caps_system_all ON dbai_core.system_capabilities FOR ALL TO dbai_system USING (TRUE);
CREATE POLICY bench_system_all ON dbai_llm.ghost_benchmarks FOR ALL TO dbai_system USING (TRUE);

CREATE POLICY boot_monitor_read ON dbai_core.boot_config FOR SELECT TO dbai_monitor USING (TRUE);
CREATE POLICY neural_monitor_read ON dbai_core.neural_bridge_config FOR SELECT TO dbai_monitor USING (TRUE);
CREATE POLICY driver_monitor_read ON dbai_core.driver_registry FOR SELECT TO dbai_monitor USING (TRUE);
CREATE POLICY caps_monitor_read ON dbai_core.system_capabilities FOR SELECT TO dbai_monitor USING (TRUE);
CREATE POLICY bench_monitor_read ON dbai_llm.ghost_benchmarks FOR SELECT TO dbai_monitor USING (TRUE);

CREATE POLICY boot_llm_read ON dbai_core.boot_config FOR SELECT TO dbai_llm USING (TRUE);
CREATE POLICY caps_llm_read ON dbai_core.system_capabilities FOR SELECT TO dbai_llm USING (TRUE);
CREATE POLICY bench_llm_all ON dbai_llm.ghost_benchmarks FOR ALL TO dbai_llm USING (TRUE);

-- =============================================================================
-- ENDE Schema 19: Neural Bridge
-- =============================================================================
