-- =============================================================================
-- DBAI Schema 20: Seed-Daten für Hardware-Abstraktionsschicht & Neural Bridge
-- =============================================================================
--
-- Befüllt:
--   1. Power-Profile (Sparmodus, Balanced, Cyberbrain, Silent)
--   2. Boot-Konfiguration (Default)
--   3. Neural-Bridge-Config (GPU-Schwellwerte, Monitoring-Intervalle)
--   4. Treiber-Registry (GPU, Storage, Network, Fan, Sensor)
--   5. System-Capabilities (werden beim Boot überschrieben)
-- =============================================================================

-- =============================================================================
-- 1. POWER PROFILES
-- =============================================================================

INSERT INTO dbai_system.power_profiles
    (name, display_name, description,
     cpu_governor, cpu_max_freq_mhz, cpu_min_freq_mhz,
     gpu_power_limit_watts, gpu_persistence_mode, gpu_clocks_locked,
     fan_mode, max_loaded_ghosts, prefer_cpu_inference, max_context_size,
     screen_brightness, suspend_timeout_min, is_active)
VALUES
    -- Sparmodus: Alles auf Minimum, GPU schläft
    ('sparmodus', 'Sparmodus', 'Minimaler Stromverbrauch. GPU deaktiviert, '
     'CPU gedrosselt. Nur ein kleiner Ghost auf CPU.',
     'powersave', NULL, 800,
     NULL, FALSE, FALSE,
     'silent', 1, TRUE, 2048,
     30, 15, FALSE),

    -- Balanced: Normalbetrieb
    ('balanced', 'Balanced', 'Ausgewogener Modus. GPU bei Bedarf, '
     'CPU im Ondemand-Modus. Standard für Alltagsbetrieb.',
     'ondemand', NULL, NULL,
     NULL, FALSE, FALSE,
     'auto', 2, FALSE, 4096,
     70, 30, TRUE),    -- DEFAULT

    -- Cyberbrain: Volle Leistung, alle GPUs aktiv
    ('cyberbrain', 'Cyberbrain', 'Maximale Leistung. Alle GPUs voll aktiv, '
     'CPU auf Performance, maximaler Kontext. Fuer Videoanalyse, Code-Generierung, '
     'komplexe Aufgaben. Hoher Stromverbrauch!',
     'performance', NULL, NULL,
     NULL, TRUE, FALSE,
     'performance', 5, FALSE, 32768,
     100, NULL, FALSE),

    -- Silent: Leise wie möglich
    ('silent', 'Silent', 'Geraeuschminimiert. Luefter auf Minimum, '
     'GPU/CPU gedrosselt. Fuer Nachtbetrieb oder Meetings.',
     'powersave', 2000, 800,
     50, FALSE, FALSE,
     'silent', 1, TRUE, 2048,
     50, 30, FALSE)

ON CONFLICT (name) DO NOTHING;

-- =============================================================================
-- 2. BOOT CONFIGURATION
-- =============================================================================

INSERT INTO dbai_core.boot_config
    (config_name, description,
     boot_ghost_role, boot_ghost_model, auto_load_ghost,
     boot_power_profile, gpu_mode,
     start_hardware_scanner, start_gpu_manager, start_ghost_dispatcher,
     start_web_server, start_hardware_monitor,
     ghost_load_timeout_sec, hardware_scan_timeout_sec,
     kiosk_mode, kiosk_url, auto_login_user,
     is_default)
VALUES
    -- Standard-Boot: Sysadmin-Ghost, GPU auto-detect, Web-UI
    ('default', 'Standard DBAI Boot: Sysadmin-Ghost mit Auto-GPU-Erkennung. '
     'Alle Daemons aktiv, Web-UI erreichbar.',
     'sysadmin', NULL, TRUE,
     'balanced', 'auto',
     TRUE, TRUE, TRUE,
     TRUE, TRUE,
     120, 30,
     FALSE, 'http://localhost:8420', NULL,
     TRUE),

    -- Kiosk-Boot: Vollbild, kein Terminal
    ('kiosk', 'Kiosk-Modus: Startet direkt in Web-UI Vollbild. '
     'Der Nutzer sieht NIE ein Terminal — nur das DBAI Interface.',
     'sysadmin', NULL, TRUE,
     'balanced', 'auto',
     TRUE, TRUE, TRUE,
     TRUE, TRUE,
     120, 30,
     TRUE, 'http://localhost:8420', 'root',
     FALSE),

    -- Headless: Kein Web-UI, nur Daemons
    ('headless', 'Server-Modus ohne Web-UI. '
     'Ghost und Hardware-Daemons laufen, aber kein Frontend.',
     'sysadmin', NULL, TRUE,
     'balanced', 'auto',
     TRUE, TRUE, TRUE,
     FALSE, TRUE,
     120, 30,
     FALSE, NULL, NULL,
     FALSE),

    -- Recovery: Minimaler Start ohne Ghost
    ('recovery', 'Notfall-Modus: Kein Ghost, nur Hardware-Monitoring. '
     'Fuer Debugging und Reparatur.',
     'sysadmin', NULL, FALSE,
     'sparmodus', 'cpu_only',
     TRUE, FALSE, FALSE,
     TRUE, TRUE,
     30, 15,
     FALSE, 'http://localhost:8420', NULL,
     FALSE)

ON CONFLICT (config_name) DO NOTHING;

-- =============================================================================
-- 3. NEURAL BRIDGE CONFIG
-- =============================================================================

INSERT INTO dbai_core.neural_bridge_config (key, value, category, description, is_runtime)
VALUES
    -- GPU-Einstellungen
    ('gpu.vram_reserve_mb', '256'::JSONB, 'gpu',
     'VRAM-Reserve in MB: Immer diese Menge frei lassen (fuer System/Display)', TRUE),
    ('gpu.max_utilization_percent', '95'::JSONB, 'gpu',
     'Maximale GPU-Auslastung bevor Warnung', TRUE),
    ('gpu.temperature_warning_c', '80'::JSONB, 'gpu',
     'GPU-Temperatur-Warnschwelle in Grad Celsius', TRUE),
    ('gpu.temperature_critical_c', '90'::JSONB, 'gpu',
     'GPU-Temperatur: Kritisch. Ghost wird auf CPU migriert!', TRUE),
    ('gpu.auto_offload_on_overheat', 'true'::JSONB, 'gpu',
     'Ghost automatisch auf CPU verschieben wenn GPU ueberhitzt', TRUE),
    ('gpu.prefer_largest_vram', 'true'::JSONB, 'gpu',
     'Bei Multi-GPU: Bevorzuge GPU mit meistem freien VRAM', TRUE),

    -- CPU-Einstellungen
    ('cpu.max_load_percent', '90'::JSONB, 'cpu',
     'Maximale CPU-Auslastung bevor Warnung', TRUE),
    ('cpu.inference_thread_count', '0'::JSONB, 'cpu',
     'Threads fuer CPU-Inferenz (0 = auto)', TRUE),

    -- Memory
    ('memory.min_free_mb', '512'::JSONB, 'memory',
     'Minimum freier RAM in MB bevor Ghost entladen wird', TRUE),
    ('memory.swap_warning_percent', '50'::JSONB, 'memory',
     'Swap-Nutzung Warnschwelle in Prozent', TRUE),

    -- Monitoring
    ('monitoring.gpu_interval_ms', '500'::JSONB, 'monitoring',
     'GPU-Metriken Aktualisierungsintervall in Millisekunden', TRUE),
    ('monitoring.cpu_interval_ms', '500'::JSONB, 'monitoring',
     'CPU-Metriken Aktualisierungsintervall', TRUE),
    ('monitoring.memory_interval_ms', '1000'::JSONB, 'monitoring',
     'Memory-Metriken Aktualisierungsintervall', TRUE),
    ('monitoring.storage_interval_ms', '5000'::JSONB, 'monitoring',
     'Storage-Metriken Aktualisierungsintervall', TRUE),
    ('monitoring.network_interval_ms', '1000'::JSONB, 'monitoring',
     'Netzwerk-Metriken Aktualisierungsintervall', TRUE),

    -- Ghost-Einstellungen
    ('ghost.auto_benchmark', 'true'::JSONB, 'ghost',
     'Nach jedem Model-Load einen Quick-Benchmark ausfuehren', TRUE),
    ('ghost.benchmark_prompt', '"Erklaere in einem Satz was DBAI ist."'::JSONB, 'ghost',
     'Prompt fuer den Quick-Benchmark', FALSE),
    ('ghost.max_concurrent_inferences', '3'::JSONB, 'ghost',
     'Maximale gleichzeitige Inferenz-Anfragen', TRUE),
    ('ghost.auto_optimize', 'false'::JSONB, 'ghost',
     'Ghost-Modelle automatisch optimieren basierend auf Benchmarks', TRUE),

    -- Security
    ('security.allow_fan_control', 'true'::JSONB, 'security',
     'Darf die KI Luefter steuern?', FALSE),
    ('security.allow_power_profile', 'true'::JSONB, 'security',
     'Darf die KI Power-Profile wechseln?', FALSE),
    ('security.allow_gpu_overclock', 'false'::JSONB, 'security',
     'Darf die KI GPU uebertakten? (GEFAEHRLICH)', FALSE)

ON CONFLICT (key) DO NOTHING;

-- =============================================================================
-- 4. DRIVER REGISTRY — Alle DBAI-Treiber
-- =============================================================================

INSERT INTO dbai_core.driver_registry
    (driver_name, display_name, description, driver_type,
     python_module, python_class, python_method,
     sql_view, sql_table,
     vendor_match, device_match, subsystem,
     is_essential, auto_load, load_order, scan_interval_ms)
VALUES
    -- GPU-Treiber (NVIDIA)
    ('nvidia-gpu', 'NVIDIA GPU Driver', 'NVIDIA GPU-Monitoring via pynvml/nvidia-smi. '
     'Liest VRAM, Auslastung, Temperatur, Takt.',
     'gpu',
     'bridge.gpu_manager', 'GPUManager', 'scan_gpus',
     'dbai_system.vw_gpu_overview', 'dbai_system.gpu_devices',
     'nvidia|NVIDIA', 'GeForce|Quadro|Tesla|RTX|GTX|A100|H100|L40', 'pci',
     FALSE, TRUE, 10, 500),

    -- GPU-Treiber (AMD)
    ('amd-gpu', 'AMD GPU Driver', 'AMD GPU-Monitoring via rocm-smi. '
     'Liest VRAM, Auslastung, Temperatur.',
     'gpu',
     'bridge.gpu_manager', 'GPUManager', 'scan_gpus',
     'dbai_system.vw_gpu_overview', 'dbai_system.gpu_devices',
     'amd|AMD|Advanced Micro', 'Radeon|RX|Instinct', 'pci',
     FALSE, TRUE, 10, 500),

    -- CPU-Treiber
    ('cpu-monitor', 'CPU Monitor', 'Per-Core CPU-Monitoring via /proc/stat und psutil.',
     'sensor',
     'bridge.hardware_scanner', 'HardwareScanner', 'scan_cpu',
     NULL, 'dbai_system.cpu_cores',
     NULL, NULL, NULL,
     TRUE, TRUE, 5, 500),

    -- Storage-Treiber
    ('storage-health', 'Storage Health Monitor', 'SMART-Werte via smartctl. '
     'Erkennt sterbende Festplatten.',
     'storage',
     'bridge.hardware_scanner', 'HardwareScanner', 'scan_storage',
     NULL, 'dbai_system.storage_health',
     NULL, NULL, 'block',
     TRUE, TRUE, 20, 30000),

    -- Netzwerk-Treiber
    ('network-monitor', 'Network Monitor', 'Netzwerk-Interfaces und Verbindungen.',
     'network',
     'bridge.hardware_scanner', 'HardwareScanner', 'scan_network',
     NULL, 'dbai_system.network_connections',
     NULL, NULL, 'net',
     TRUE, TRUE, 30, 1000),

    -- Lüfter-Treiber
    ('fan-controller', 'Fan Controller', 'Lueftersteuerung per SQL UPDATE. '
     'Liest aktuelle RPM, setzt Ziel-Geschwindigkeit.',
     'fan',
     'bridge.hardware_scanner', 'HardwareScanner', 'scan_fans',
     NULL, 'dbai_system.fan_control',
     NULL, NULL, NULL,
     FALSE, TRUE, 40, 2000),

    -- Power-Management
    ('power-manager', 'Power Manager', 'CPU-Governor und GPU Power-Limit Steuerung. '
     'Setzt Power-Profile um.',
     'power',
     'bridge.hardware_scanner', 'HardwareScanner', 'apply_power_profile',
     'dbai_system.vw_active_power_profile', 'dbai_system.power_profiles',
     NULL, NULL, NULL,
     FALSE, TRUE, 45, 5000)

ON CONFLICT (driver_name) DO NOTHING;

-- =============================================================================
-- 5. SYSTEM CAPABILITIES (Platzhalter — werden beim Boot überschrieben)
-- =============================================================================

INSERT INTO dbai_core.system_capabilities (capability, category, description, is_available, details)
VALUES
    ('cuda', 'gpu', 'NVIDIA CUDA Compute', FALSE, '{}'::JSONB),
    ('rocm', 'gpu', 'AMD ROCm Compute', FALSE, '{}'::JSONB),
    ('avx2', 'compute', 'Intel/AMD AVX2 SIMD', FALSE, '{}'::JSONB),
    ('avx512', 'compute', 'Intel AVX-512 SIMD', FALSE, '{}'::JSONB),
    ('nvme', 'storage', 'NVMe SSD vorhanden', FALSE, '{}'::JSONB),
    ('ecc_ram', 'memory', 'ECC Error-Correcting RAM', FALSE, '{}'::JSONB),
    ('10gbe', 'network', '10 Gigabit Ethernet', FALSE, '{}'::JSONB),
    ('multi_gpu', 'gpu', 'Mehrere GPUs erkannt', FALSE, '{}'::JSONB),
    ('gpu_p2p', 'gpu', 'GPU Peer-to-Peer Transfer', FALSE, '{}'::JSONB),
    ('huge_pages', 'memory', 'Linux Huge Pages aktiviert', FALSE, '{}'::JSONB)
ON CONFLICT (capability) DO NOTHING;

-- =============================================================================
-- ENDE Schema 20: Seed-Daten Hardware-Abstraktionsschicht
-- =============================================================================
