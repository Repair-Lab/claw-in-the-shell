-- ============================================================================
-- Migration 68: Mobile Bridge — 5-Dimensionales KI-Betriebssystem (v0.13.0)
-- ============================================================================
--
-- Erweitert GhostShell vom 3-Boot-Stick zum 5-Dimensionalen System:
--
--   Dimension 1-3: PC-Modi (Portable App, Live-Boot, SSD-Installation)
--   Dimension 4:   USB-C Direct Link (RNDIS/ECM, Kabel zum Handy)
--   Dimension 5:   Ghost-Net Hotspot (eigenes WLAN, alle Geräte gleichzeitig)
--
-- Neue Komponenten:
--   1. dbai_net Schema — Netzwerk-Infrastruktur & Mobile Bridge
--   2. Network Interfaces — USB-Gadget, WLAN-Hotspot, mDNS
--   3. Mobile Devices — Registrierte Smartphones/Tablets
--   4. Sensor Pipeline — GPS, Kamera, Mikrofon → PostgreSQL
--   5. PWA Configuration — manifest.json, Service Worker, Icons
--   6. Hotspot Configuration — hostapd, dnsmasq, DHCP-Leases
--   7. USB-Gadget Configuration — dwc2, g_ether, RNDIS/ECM
--   8. mDNS/Avahi Configuration — ghost.local Discovery
--   9. Connection Sessions — Aktive Verbindungen über alle 5 Dimensionen
--  10. Boot-Mode-Erweiterung — Dimension 4+5 als offizielle Modi
--
-- ============================================================================

BEGIN;

-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  1. SCHEMA: dbai_net — Netzwerk-Infrastruktur                           ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝

CREATE SCHEMA IF NOT EXISTS dbai_net;
COMMENT ON SCHEMA dbai_net IS
    'Netzwerk-Infrastruktur: Mobile Bridge, Hotspot, USB-Gadget, mDNS, Sensor-Pipeline. '
    'Erweitert das 3-Boot-System zu 5 Dimensionen (PC + Kabel + WLAN).';

-- Grants
GRANT USAGE ON SCHEMA dbai_net TO dbai_runtime, dbai_system, dbai_monitor;
GRANT SELECT ON ALL TABLES IN SCHEMA dbai_net TO dbai_monitor;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA dbai_net TO dbai_runtime;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA dbai_net TO dbai_system;
ALTER DEFAULT PRIVILEGES IN SCHEMA dbai_net GRANT SELECT ON TABLES TO dbai_monitor;
ALTER DEFAULT PRIVILEGES IN SCHEMA dbai_net GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO dbai_runtime;


-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  2. NETWORK INTERFACES — Alle Netzwerkschnittstellen des Sticks         ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝

CREATE TABLE IF NOT EXISTS dbai_net.network_interfaces (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    iface_name      TEXT NOT NULL UNIQUE,        -- z.B. 'usb0', 'wlan0', 'eth0', 'lo'
    iface_type      TEXT NOT NULL CHECK (iface_type IN (
                        'usb_gadget',    -- USB-C Direct Link (RNDIS/ECM)
                        'wifi_ap',       -- WLAN Access Point (Hotspot)
                        'wifi_client',   -- WLAN Client (externes Netz)
                        'ethernet',      -- Kabel-LAN
                        'loopback',      -- localhost
                        'bridge',        -- Netzwerk-Brücke
                        'vpn',           -- VPN-Tunnel
                        'cellular'       -- Mobilfunk (wenn SIM vorhanden)
                    )),
    ip_address      INET,                        -- z.B. '10.0.0.1' oder '192.168.4.1'
    subnet_mask     INET,                        -- z.B. '255.255.255.0'
    gateway         INET,
    mac_address     MACADDR,
    mtu             INTEGER DEFAULT 1500,
    is_active       BOOLEAN DEFAULT FALSE,
    is_primary      BOOLEAN DEFAULT FALSE,       -- Haupt-Interface für Routing
    dhcp_enabled    BOOLEAN DEFAULT FALSE,
    link_speed_mbps INTEGER,                     -- Geschwindigkeit in Mbit/s
    driver          TEXT,                         -- Kernel-Treiber (dwc2, wlan, e1000e)
    properties      JSONB DEFAULT '{}',          -- Extra-Infos
    last_seen       TIMESTAMPTZ DEFAULT now(),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
COMMENT ON TABLE dbai_net.network_interfaces IS
    'Alle Netzwerkschnittstellen des Ghost-Sticks: USB-Gadget (usb0), WLAN-Hotspot (wlan0), Ethernet, etc.';


-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  3. MOBILE DEVICES — Registrierte Smartphones & Tablets                 ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝

CREATE TABLE IF NOT EXISTS dbai_net.mobile_devices (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_name     TEXT NOT NULL,               -- z.B. 'iPhone 15 Pro', 'Samsung S24'
    device_type     TEXT NOT NULL CHECK (device_type IN (
                        'iphone', 'ipad', 'android_phone', 'android_tablet',
                        'laptop', 'desktop', 'other'
                    )),
    os_name         TEXT,                        -- 'iOS', 'Android', 'iPadOS'
    os_version      TEXT,                        -- '18.3', '15'
    browser         TEXT,                        -- 'Safari', 'Chrome', 'Firefox'
    screen_width    INTEGER,
    screen_height   INTEGER,
    has_camera      BOOLEAN DEFAULT TRUE,
    has_gps         BOOLEAN DEFAULT TRUE,
    has_microphone  BOOLEAN DEFAULT TRUE,
    has_nfc         BOOLEAN DEFAULT FALSE,
    has_biometrics  BOOLEAN DEFAULT FALSE,       -- Face ID / Fingerprint
    pwa_installed   BOOLEAN DEFAULT FALSE,       -- PWA auf Homescreen?
    push_token      TEXT,                        -- Push-Notification Token
    last_ip         INET,
    connection_type TEXT CHECK (connection_type IN (
                        'usb_direct',     -- USB-C Kabel (Dimension 4)
                        'ghost_wifi',     -- Ghost-Net Hotspot (Dimension 5)
                        'local_wifi',     -- Gleiches WLAN (Local Cloud)
                        'remote'          -- Über Internet/VPN
                    )),
    user_id         UUID,                        -- Zugeordneter Benutzer
    is_trusted      BOOLEAN DEFAULT FALSE,       -- Via PIN/QR-Code verifiziert
    paired_at       TIMESTAMPTZ,
    last_seen       TIMESTAMPTZ DEFAULT now(),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
COMMENT ON TABLE dbai_net.mobile_devices IS
    'Registrierte mobile Endgeräte: iOS, Android, Tablets. Zentrale Device-Registry mit Sensor-Capabilities.';

CREATE INDEX IF NOT EXISTS idx_mobile_devices_user ON dbai_net.mobile_devices(user_id);
CREATE INDEX IF NOT EXISTS idx_mobile_devices_last_seen ON dbai_net.mobile_devices(last_seen);


-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  4. SENSOR PIPELINE — Handy-Sensoren → PostgreSQL                       ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝

CREATE TABLE IF NOT EXISTS dbai_net.sensor_data (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id       UUID NOT NULL REFERENCES dbai_net.mobile_devices(id) ON DELETE CASCADE,
    sensor_type     TEXT NOT NULL CHECK (sensor_type IN (
                        'gps',           -- Standort (lat/lon/alt/accuracy)
                        'photo',         -- Kamera-Foto (binary → Vektor)
                        'video',         -- Video-Clip
                        'audio',         -- Sprachnotiz / Mikrofon
                        'accelerometer', -- Beschleunigung
                        'gyroscope',     -- Rotation
                        'compass',       -- Himmelsrichtung
                        'barometer',     -- Luftdruck → Höhe
                        'light',         -- Umgebungslicht
                        'nfc',           -- NFC-Tag Scan
                        'qr_scan',       -- QR-Code Scan
                        'biometric',     -- Fingerprint/Face Event
                        'battery',       -- Akkustand
                        'network_info',  -- WLAN/Mobilfunk-Daten
                        'custom'         -- Benutzerdefiniert
                    )),
    -- GPS-Daten (wenn sensor_type = 'gps')
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    altitude_m      DOUBLE PRECISION,
    accuracy_m      DOUBLE PRECISION,
    -- Binärdaten (Fotos, Audio, Video)
    payload_binary  BYTEA,                       -- Roh-Daten (Foto, Audio)
    payload_mime    TEXT,                         -- z.B. 'image/jpeg', 'audio/webm'
    payload_size_kb INTEGER,
    -- Vektor-Embedding (nach Analyse durch LLM/CLIP)
    embedding       vector(1536),                -- Vektor für Ähnlichkeitssuche
    -- Strukturierte Daten (JSON für alles andere)
    payload_json    JSONB DEFAULT '{}',
    -- Metadaten
    label           TEXT,                        -- Benutzer-Label ('Bauteil Foto', 'Meeting')
    tags            TEXT[] DEFAULT '{}',
    is_processed    BOOLEAN DEFAULT FALSE,       -- Vom Vektor-Kernel analysiert?
    processed_at    TIMESTAMPTZ,
    analysis_result JSONB,                       -- Ergebnis der KI-Analyse
    captured_at     TIMESTAMPTZ DEFAULT now(),   -- Zeitpunkt der Aufnahme
    received_at     TIMESTAMPTZ DEFAULT now(),   -- Zeitpunkt des Empfangs auf dem Stick
    created_at      TIMESTAMPTZ DEFAULT now()
);
COMMENT ON TABLE dbai_net.sensor_data IS
    'Sensor-Pipeline: Handy-Sensoren füttern direkt in PostgreSQL. GPS, Fotos, Sprachnotizen → Vektor-Analyse.';

CREATE INDEX IF NOT EXISTS idx_sensor_data_device ON dbai_net.sensor_data(device_id);
CREATE INDEX IF NOT EXISTS idx_sensor_data_type ON dbai_net.sensor_data(sensor_type);
CREATE INDEX IF NOT EXISTS idx_sensor_data_captured ON dbai_net.sensor_data(captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_sensor_data_unprocessed ON dbai_net.sensor_data(is_processed) WHERE NOT is_processed;


-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  5. PWA CONFIGURATION — Progressive Web App Setup                       ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝

CREATE TABLE IF NOT EXISTS dbai_net.pwa_config (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config_key      TEXT NOT NULL UNIQUE,
    config_value    JSONB NOT NULL,
    description     TEXT,
    updated_at      TIMESTAMPTZ DEFAULT now()
);
COMMENT ON TABLE dbai_net.pwa_config IS
    'PWA-Konfiguration: manifest.json-Werte, Service-Worker-Settings, Icon-Pfade. DB-gesteuert.';

-- PWA Manifest als DB-Einträge (generiert manifest.json dynamisch)
INSERT INTO dbai_net.pwa_config (config_key, config_value, description) VALUES
    ('manifest', '{
        "name": "GhostShell OS",
        "short_name": "GhostShell",
        "description": "Das 5-Dimensionale KI-Betriebssystem — Dein mobiles Gehirn",
        "start_url": "/",
        "display": "standalone",
        "orientation": "any",
        "background_color": "#0a0a0f",
        "theme_color": "#00ff88",
        "lang": "de-DE",
        "dir": "ltr",
        "categories": ["productivity", "developer", "utilities"],
        "icons": [
            {"src": "/assets/icons/ghost-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
            {"src": "/assets/icons/ghost-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}
        ],
        "screenshots": [
            {"src": "/assets/screenshots/desktop.png", "sizes": "1280x720", "type": "image/png", "form_factor": "wide"},
            {"src": "/assets/screenshots/mobile.png", "sizes": "390x844", "type": "image/png", "form_factor": "narrow"}
        ],
        "shortcuts": [
            {"name": "SQL Console", "url": "/sql", "icon": "/assets/icons/sql.png"},
            {"name": "KI Chat", "url": "/chat", "icon": "/assets/icons/chat.png"},
            {"name": "Terminal", "url": "/terminal", "icon": "/assets/icons/terminal.png"}
        ]
    }'::JSONB, 'PWA Web App Manifest — wird als /manifest.json ausgeliefert'),

    ('service_worker', '{
        "enabled": true,
        "cache_strategy": "network-first",
        "cache_name": "ghostshell-v0.13.0",
        "precache_urls": ["/", "/index.html", "/assets/css/global.css"],
        "offline_page": "/offline.html",
        "push_enabled": false,
        "background_sync": true,
        "periodic_sync_interval_ms": 60000
    }'::JSONB, 'Service-Worker-Konfiguration: Caching, Offline, Background-Sync'),

    ('install_prompt', '{
        "enabled": true,
        "delay_seconds": 5,
        "title": "GhostShell installieren?",
        "message": "Füge GhostShell als App zu deinem Homescreen hinzu — voller Zugriff ohne Browser-Leiste.",
        "accept_text": "Installieren",
        "dismiss_text": "Später",
        "show_on_mobile_only": true
    }'::JSONB, 'PWA Install-Prompt Konfiguration'),

    ('mobile_features', '{
        "camera_access": true,
        "gps_access": true,
        "microphone_access": true,
        "vibration": true,
        "fullscreen": true,
        "screen_wake_lock": true,
        "share_api": true,
        "file_system_access": false
    }'::JSONB, 'Mobile Browser-API Feature-Flags')
ON CONFLICT (config_key) DO UPDATE SET
    config_value = EXCLUDED.config_value,
    updated_at = now();


-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  6. HOTSPOT CONFIGURATION — hostapd + dnsmasq                           ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝

CREATE TABLE IF NOT EXISTS dbai_net.hotspot_config (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- hostapd
    ssid            TEXT NOT NULL DEFAULT 'GhostShell-Net',
    passphrase      TEXT NOT NULL DEFAULT 'ghost2026',  -- Min 8 Zeichen WPA2
    channel         INTEGER DEFAULT 6,
    hw_mode         TEXT DEFAULT 'g' CHECK (hw_mode IN ('a', 'b', 'g', 'n', 'ac')),
    wpa_version     INTEGER DEFAULT 2 CHECK (wpa_version IN (2, 3)),
    country_code    TEXT DEFAULT 'DE',
    hidden_ssid     BOOLEAN DEFAULT FALSE,
    max_clients     INTEGER DEFAULT 10,
    interface       TEXT DEFAULT 'wlan0',
    -- dnsmasq / DHCP
    dhcp_range_start INET DEFAULT '192.168.4.100',
    dhcp_range_end   INET DEFAULT '192.168.4.200',
    dhcp_lease_time  TEXT DEFAULT '12h',
    gateway_ip       INET DEFAULT '192.168.4.1',
    dns_server       INET DEFAULT '192.168.4.1',   -- Ghost-Stick ist auch DNS
    -- Status
    is_active       BOOLEAN DEFAULT FALSE,
    auto_start      BOOLEAN DEFAULT TRUE,          -- Bei Boot automatisch starten?
    started_at      TIMESTAMPTZ,
    -- Metriken
    connected_clients INTEGER DEFAULT 0,
    total_connections INTEGER DEFAULT 0,
    bytes_tx        BIGINT DEFAULT 0,
    bytes_rx        BIGINT DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
COMMENT ON TABLE dbai_net.hotspot_config IS
    'Ghost-Net WLAN-Hotspot: hostapd + dnsmasq Konfiguration. Dimension 5 des 5D-Systems.';

-- Default Hotspot
INSERT INTO dbai_net.hotspot_config (ssid, passphrase, channel, gateway_ip, auto_start)
VALUES ('GhostShell-Net', 'ghost2026!secure', 6, '192.168.4.1', true)
ON CONFLICT DO NOTHING;


-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  7. DHCP LEASES — Wer ist im Ghost-Net?                                ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝

CREATE TABLE IF NOT EXISTS dbai_net.dhcp_leases (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mac_address     MACADDR NOT NULL,
    ip_address      INET NOT NULL,
    hostname        TEXT,
    device_id       UUID REFERENCES dbai_net.mobile_devices(id),
    interface       TEXT NOT NULL DEFAULT 'wlan0', -- wlan0 oder usb0
    lease_start     TIMESTAMPTZ DEFAULT now(),
    lease_end       TIMESTAMPTZ,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT now()
);
COMMENT ON TABLE dbai_net.dhcp_leases IS
    'DHCP-Lease-Tabelle: Welches Gerät hat welche IP im Ghost-Net oder USB-Link.';

CREATE INDEX IF NOT EXISTS idx_dhcp_leases_active ON dbai_net.dhcp_leases(is_active) WHERE is_active;
CREATE INDEX IF NOT EXISTS idx_dhcp_leases_mac ON dbai_net.dhcp_leases(mac_address);


-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  8. USB GADGET CONFIGURATION — dwc2 / g_ether / RNDIS                   ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝

CREATE TABLE IF NOT EXISTS dbai_net.usb_gadget_config (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- ConfigFS Gadget
    gadget_name     TEXT NOT NULL DEFAULT 'ghostshell',
    vendor_id       TEXT DEFAULT '0x1d6b',       -- Linux Foundation
    product_id      TEXT DEFAULT '0x0104',       -- Multifunction Composite Gadget
    manufacturer    TEXT DEFAULT 'GhostShell OS',
    product         TEXT DEFAULT 'Ghost-Pi Mobile Bridge',
    serial_number   TEXT DEFAULT 'GHOST-5D-001',
    -- Netzwerk-Gadget
    gadget_type     TEXT NOT NULL DEFAULT 'ecm' CHECK (gadget_type IN (
                        'ecm',      -- Ethernet Control Model (macOS/Linux/iOS nativ)
                        'rndis',    -- Remote NDIS (Windows nativ)
                        'ncm',      -- Network Control Model (moderner ECM)
                        'eem',      -- Ethernet Emulation Model
                        'multi'     -- ECM + RNDIS gleichzeitig (für alle Plattformen)
                    )),
    host_mac        MACADDR,                     -- MAC die der Host sieht
    device_mac      MACADDR,                     -- MAC des Gadgets
    ip_address      INET DEFAULT '10.0.0.1',     -- IP des Sticks über USB
    peer_ip         INET DEFAULT '10.0.0.2',     -- IP die das Handy bekommt
    subnet_mask     INET DEFAULT '255.255.255.252',  -- /30 Punkt-zu-Punkt
    -- Kernel-Module
    dtoverlay       TEXT DEFAULT 'dwc2',
    modules_load    TEXT DEFAULT 'dwc2,g_ether',
    -- Status
    is_active       BOOLEAN DEFAULT FALSE,
    auto_start      BOOLEAN DEFAULT TRUE,
    -- Boot config
    boot_config_txt TEXT DEFAULT 'dtoverlay=dwc2' || E'\n' || 'dr_mode=otg',
    cmdline_append  TEXT DEFAULT 'modules-load=dwc2,g_ether',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
COMMENT ON TABLE dbai_net.usb_gadget_config IS
    'USB-Gadget-Konfiguration (OTG): dwc2, g_ether, RNDIS/ECM. Dimension 4 — Kabel-Direktverbindung zum Handy.';

-- Default USB-Gadget (Multi-Mode: ECM + RNDIS)
INSERT INTO dbai_net.usb_gadget_config (
    gadget_name, gadget_type, ip_address, peer_ip, auto_start
) VALUES (
    'ghostshell', 'multi', '10.0.0.1', '10.0.0.2', true
) ON CONFLICT DO NOTHING;


-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  9. MDNS / AVAHI CONFIGURATION — ghost.local Discovery                  ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝

CREATE TABLE IF NOT EXISTS dbai_net.mdns_config (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hostname        TEXT NOT NULL DEFAULT 'ghost',       -- → ghost.local
    domain          TEXT NOT NULL DEFAULT 'local',
    -- Avahi Service Advertisements
    services        JSONB NOT NULL DEFAULT '[
        {"name": "GhostShell Dashboard", "type": "_http._tcp", "port": 8080, "txt": ["path=/", "version=0.13.0"]},
        {"name": "GhostShell API",       "type": "_http._tcp", "port": 3100, "txt": ["path=/api", "version=0.13.0"]},
        {"name": "GhostShell DB",        "type": "_postgresql._tcp", "port": 5432, "txt": ["db=dbai"]}
    ]'::JSONB,
    -- Konfiguration
    publish_workstation BOOLEAN DEFAULT TRUE,
    publish_hinfo       BOOLEAN DEFAULT FALSE,
    allow_interfaces    TEXT[] DEFAULT ARRAY['usb0', 'wlan0'],  -- Nur Ghost-Interfaces
    deny_interfaces     TEXT[] DEFAULT ARRAY['eth0'],           -- Externes LAN nicht advertisen
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now()
);
COMMENT ON TABLE dbai_net.mdns_config IS
    'mDNS/Avahi: ghost.local Discovery. Handy tippt ghost.local → findet sofort das Dashboard.';

-- Default mDNS
INSERT INTO dbai_net.mdns_config (hostname, domain, is_active)
VALUES ('ghost', 'local', true)
ON CONFLICT DO NOTHING;


-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  10. CONNECTION SESSIONS — Aktive Verbindungen über alle 5 Dimensionen  ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝

CREATE TABLE IF NOT EXISTS dbai_net.connection_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id       UUID REFERENCES dbai_net.mobile_devices(id) ON DELETE SET NULL,
    user_id         UUID,
    dimension       SMALLINT NOT NULL CHECK (dimension BETWEEN 1 AND 5),
    dimension_name  TEXT GENERATED ALWAYS AS (
                        CASE dimension
                            WHEN 1 THEN 'Portable App'
                            WHEN 2 THEN 'Live-Boot'
                            WHEN 3 THEN 'SSD-Installation'
                            WHEN 4 THEN 'USB-C Direct Link'
                            WHEN 5 THEN 'Ghost-Net Hotspot'
                        END
                    ) STORED,
    interface       TEXT,                        -- usb0, wlan0, eth0, etc.
    client_ip       INET,
    client_ua       TEXT,                        -- User-Agent
    is_pwa          BOOLEAN DEFAULT FALSE,       -- Zugriff über PWA?
    is_active       BOOLEAN DEFAULT TRUE,
    started_at      TIMESTAMPTZ DEFAULT now(),
    last_activity   TIMESTAMPTZ DEFAULT now(),
    ended_at        TIMESTAMPTZ,
    bytes_tx        BIGINT DEFAULT 0,
    bytes_rx        BIGINT DEFAULT 0,
    requests_count  INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT now()
);
COMMENT ON TABLE dbai_net.connection_sessions IS
    'Alle aktiven Verbindungen über alle 5 Dimensionen. Tracking: Wer greift worüber auf das System zu.';

CREATE INDEX IF NOT EXISTS idx_conn_sessions_active ON dbai_net.connection_sessions(is_active) WHERE is_active;
CREATE INDEX IF NOT EXISTS idx_conn_sessions_dimension ON dbai_net.connection_sessions(dimension);
CREATE INDEX IF NOT EXISTS idx_conn_sessions_device ON dbai_net.connection_sessions(device_id);


-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  11. BOOT MODE ERWEITERUNG — Dimension 4+5 als offizielle Modi         ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝

CREATE TABLE IF NOT EXISTS dbai_net.boot_dimensions (
    dimension       SMALLINT PRIMARY KEY CHECK (dimension BETWEEN 1 AND 5),
    name            TEXT NOT NULL,
    description     TEXT NOT NULL,
    connection_type TEXT NOT NULL,
    hardware_req    TEXT,
    interface_name  TEXT,
    ip_range        TEXT,
    setup_required  TEXT[],
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT now()
);
COMMENT ON TABLE dbai_net.boot_dimensions IS
    'Die 5 Dimensionen des GhostShell OS: PC-Modi (1-3) + Mobile Bridge (4-5).';

INSERT INTO dbai_net.boot_dimensions (dimension, name, description, connection_type, hardware_req, interface_name, ip_range, setup_required) VALUES
    (1, 'Portable App',
     'Docker-Launcher für Win/Mac/Linux. USB einstecken, Script starten, KI-Dashboard da.',
     'usb_storage', 'USB 3.0+ Stick, Host-OS mit Docker',
     NULL, NULL,
     ARRAY['docker', 'docker-compose']),

    (2, 'Live-Boot',
     'Eigener Linux-Kernel vom USB booten. GhostShell OS läuft im RAM mit optionaler Persistenz.',
     'direct_boot', 'USB 3.0+ Stick, UEFI-fähiger PC',
     NULL, NULL,
     ARRAY['grub', 'squashfs', 'persistence-partition']),

    (3, 'SSD-Installation',
     'Permanent auf interne SSD installiert. Maximale Performance, voller Hardware-Zugriff.',
     'native_install', 'PC/Server mit SSD, min. 64GB',
     NULL, NULL,
     ARRAY['installer-script', 'grub-install']),

    (4, 'USB-C Direct Link',
     'Stick per USB-C ans Handy. RNDIS/ECM macht den Stick zum LAN-Adapter. Max Speed, kein Funk nötig.',
     'usb_gadget', 'USB-C OTG-fähiges Gerät (iPhone 15+, Android mit OTG)',
     'usb0', '10.0.0.0/30',
     ARRAY['dwc2', 'g_ether', 'configfs', 'dnsmasq']),

    (5, 'Ghost-Net Hotspot',
     'Stick spannt eigenes WLAN auf. Alle Geräte gleichzeitig — Teamarbeit ohne Router, Air-Gap-fähig.',
     'wifi_ap', 'WLAN-Chip (BCM43430 oder besser)',
     'wlan0', '192.168.4.0/24',
     ARRAY['hostapd', 'dnsmasq', 'avahi-daemon'])
ON CONFLICT (dimension) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description;


-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  12. HARDWARE SETUP — Raspberry Pi / Compute Stick Konfiguration        ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝

CREATE TABLE IF NOT EXISTS dbai_net.hardware_profiles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_name    TEXT NOT NULL UNIQUE,
    board           TEXT NOT NULL,               -- 'rpi_zero2w', 'radxa_zero', 'compute_stick'
    soc             TEXT,                        -- 'BCM2710A1', 'Amlogic S905Y2'
    cpu_cores       INTEGER,
    ram_mb          INTEGER,
    has_wifi        BOOLEAN DEFAULT TRUE,
    has_bluetooth   BOOLEAN DEFAULT TRUE,
    has_usb_otg     BOOLEAN DEFAULT TRUE,
    gpio_pins       INTEGER DEFAULT 0,
    power_draw_mw   INTEGER,                     -- Max Stromverbrauch in mW
    usb_connector   TEXT DEFAULT 'usb-c',        -- 'usb-a', 'usb-c', 'micro-usb'
    form_factor     TEXT,                        -- 'stick', 'pi-zero', 'compute-module'
    notes           TEXT,
    boot_config     JSONB DEFAULT '{}',          -- /boot/config.txt als JSON
    network_config  JSONB DEFAULT '{}',          -- /etc/network/interfaces als JSON
    packages        TEXT[] DEFAULT '{}',          -- Benötigte Pakete
    created_at      TIMESTAMPTZ DEFAULT now()
);
COMMENT ON TABLE dbai_net.hardware_profiles IS
    'Hardware-Profile für den Ghost-Pi/Compute-Stick: Board-Specs, Boot-Config, Netzwerk-Setup.';

-- Raspberry Pi Zero 2 W Profil
INSERT INTO dbai_net.hardware_profiles (
    profile_name, board, soc, cpu_cores, ram_mb,
    has_wifi, has_bluetooth, has_usb_otg, gpio_pins,
    power_draw_mw, usb_connector, form_factor, notes,
    boot_config, network_config, packages
) VALUES (
    'Ghost-Pi Zero', 'rpi_zero2w', 'BCM2710A1', 4, 512,
    true, true, true, 40,
    500, 'micro-usb', 'pi-zero',
    'Raspberry Pi Zero 2 W mit USB-A/C Stecker-Addon. Klein genug für ein USB-Stick-Gehäuse.',
    '{
        "dtoverlay": ["dwc2"],
        "dr_mode": "otg",
        "gpu_mem": "16",
        "boot_delay": "0",
        "disable_splash": "1",
        "dtparam": "audio=off"
    }'::JSONB,
    '{
        "usb0": {"type": "static", "address": "10.0.0.1/30", "role": "usb_gadget"},
        "wlan0": {"type": "static", "address": "192.168.4.1/24", "role": "hotspot"},
        "lo": {"type": "loopback"}
    }'::JSONB,
    ARRAY['postgresql-16', 'hostapd', 'dnsmasq', 'avahi-daemon', 'nginx', 'python3-pip', 'pgvector']
),
-- Radxa Zero Profil
(
    'Ghost-Radxa', 'radxa_zero', 'Amlogic S905Y2', 4, 4096,
    true, true, true, 40,
    2000, 'usb-c', 'stick',
    'Radxa Zero mit 4GB RAM. USB-C nativ, idealer Compute-Stick für den Ghost-Pi.',
    '{
        "dtoverlay": ["dwc2"],
        "dr_mode": "otg"
    }'::JSONB,
    '{
        "usb0": {"type": "static", "address": "10.0.0.1/30", "role": "usb_gadget"},
        "wlan0": {"type": "static", "address": "192.168.4.1/24", "role": "hotspot"}
    }'::JSONB,
    ARRAY['postgresql-16', 'hostapd', 'dnsmasq', 'avahi-daemon', 'nginx', 'python3-pip', 'pgvector']
)
ON CONFLICT (profile_name) DO NOTHING;


-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  13. VIEWS — Übersichten & Dashboards                                   ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝

-- Alle aktiven Verbindungen mit Dimension & Device-Info
CREATE OR REPLACE VIEW dbai_net.vw_active_connections AS
SELECT
    cs.id,
    cs.dimension,
    cs.dimension_name,
    cs.interface,
    cs.client_ip,
    cs.is_pwa,
    cs.started_at,
    cs.last_activity,
    cs.requests_count,
    md.device_name,
    md.device_type,
    md.os_name,
    md.os_version,
    cs.bytes_tx,
    cs.bytes_rx
FROM dbai_net.connection_sessions cs
LEFT JOIN dbai_net.mobile_devices md ON md.id = cs.device_id
WHERE cs.is_active = TRUE
ORDER BY cs.last_activity DESC;

-- Netzwerk-Status Übersicht
CREATE OR REPLACE VIEW dbai_net.vw_network_status AS
SELECT
    ni.iface_name,
    ni.iface_type,
    ni.ip_address,
    ni.is_active,
    ni.link_speed_mbps,
    (SELECT COUNT(*) FROM dbai_net.dhcp_leases dl WHERE dl.interface = ni.iface_name AND dl.is_active) AS active_leases,
    (SELECT COUNT(*) FROM dbai_net.connection_sessions cs WHERE cs.interface = ni.iface_name AND cs.is_active) AS active_sessions
FROM dbai_net.network_interfaces ni
ORDER BY ni.is_active DESC, ni.iface_name;

-- Sensor-Pipeline Status
CREATE OR REPLACE VIEW dbai_net.vw_sensor_pipeline AS
SELECT
    sd.sensor_type,
    COUNT(*) AS total_entries,
    COUNT(*) FILTER (WHERE NOT sd.is_processed) AS pending_analysis,
    COUNT(*) FILTER (WHERE sd.is_processed) AS analyzed,
    MAX(sd.captured_at) AS latest_capture,
    pg_size_pretty(SUM(COALESCE(sd.payload_size_kb, 0)) * 1024) AS total_data_size
FROM dbai_net.sensor_data sd
GROUP BY sd.sensor_type
ORDER BY total_entries DESC;

-- 5-Dimensionen Dashboard
CREATE OR REPLACE VIEW dbai_net.vw_five_dimensions AS
SELECT
    bd.dimension,
    bd.name,
    bd.description,
    bd.connection_type,
    bd.interface_name,
    bd.ip_range,
    bd.is_active,
    (SELECT COUNT(*) FROM dbai_net.connection_sessions cs
     WHERE cs.dimension = bd.dimension AND cs.is_active) AS active_connections,
    (SELECT MAX(cs.last_activity) FROM dbai_net.connection_sessions cs
     WHERE cs.dimension = bd.dimension) AS last_activity
FROM dbai_net.boot_dimensions bd
ORDER BY bd.dimension;


-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  14. DEFAULT NETWORK INTERFACES — Seed-Daten                            ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝

INSERT INTO dbai_net.network_interfaces (iface_name, iface_type, ip_address, is_active, driver, properties) VALUES
    ('usb0', 'usb_gadget', '10.0.0.1', false, 'dwc2/g_ether',
     '{"description": "USB-C Direct Link (Dimension 4)", "mode": "RNDIS+ECM", "max_speed_mbps": 480}'::JSONB),

    ('wlan0', 'wifi_ap', '192.168.4.1', false, 'brcmfmac',
     '{"description": "Ghost-Net Hotspot (Dimension 5)", "mode": "AP", "channel": 6, "encryption": "WPA2"}'::JSONB),

    ('lo', 'loopback', '127.0.0.1', true, 'kernel',
     '{"description": "Loopback Interface"}'::JSONB)
ON CONFLICT (iface_name) DO NOTHING;


-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  15. DESKTOP APP — Mobile Bridge als Desktop-Symbol                     ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝

INSERT INTO dbai_ui.apps (
    app_id, name, description, icon,
    default_width, default_height, min_width, min_height,
    resizable, source_type, source_target,
    required_role, is_system, is_pinned,
    category, sort_order
) VALUES (
    'mobile_bridge',
    'Mobile Bridge',
    '5-Dimensionale Verbindung: USB-C Direct Link, Ghost-Net Hotspot, PWA, Sensor-Pipeline. '
    'Steuere GhostShell von jedem Endgerät.',
    '📡',
    900, 700, 600, 450,
    true, 'component', 'MobileBridge',
    'user', true, false,
    'system', 56
)
ON CONFLICT (app_id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    icon = EXCLUDED.icon;


-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  16. SYSTEM MEMORY — Wissenseinträge                                    ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝

INSERT INTO dbai_knowledge.system_memory (category, title, content) VALUES
    ('architecture', '5-Dimensionales System',
     'GhostShell OS: 5 Zugangs-Dimensionen. '
     'D1=Portable App (Docker auf Win/Mac/Linux), '
     'D2=Live-Boot (USB-Kernel mit Persistence), '
     'D3=SSD-Installation (Full Power), '
     'D4=USB-C Direct Link (RNDIS/ECM, Kabel zum Handy, 480Mbit/s), '
     'D5=Ghost-Net Hotspot (eigenes WLAN, alle Geräte gleichzeitig). '
     'Dimension 4+5 machen den Stick zum mobilen Server in der Hosentasche.'),

    ('architecture', 'Mobile Bridge Stack',
     'Mobile Bridge Hardware-Stack: '
     'Board: Raspberry Pi Zero 2 W oder Radxa Zero. '
     'USB-Gadget: dwc2 + g_ether (ConfigFS), RNDIS für Windows, ECM für macOS/Linux/iOS. '
     'Hotspot: hostapd (WPA2) + dnsmasq (DHCP). '
     'Discovery: avahi-daemon → ghost.local via mDNS. '
     'Frontend: PWA mit manifest.json + Service Worker + Install Prompt. '
     'Sensor Pipeline: GPS/Kamera/Mikro → /api/sensors → PostgreSQL → pgvector Embedding.'),

    ('workflow', 'Mobile Bridge Workflow',
     'Dimension 4 (Kabel): Stick per USB-C ans Handy → dwc2/g_ether aktiviert → Handy sieht LAN-Adapter → '
     'IP 10.0.0.2, Gateway 10.0.0.1 → Browser öffnen → ghost.local oder 10.0.0.1:8080. '
     'Dimension 5 (WLAN): Stick an Powerbank → hostapd spannt "GhostShell-Net" auf → '
     'Handy/Laptop verbindet sich → DHCP gibt 192.168.4.x → ghost.local öffnen. '
     'PWA: "Zum Startbildschirm hinzufügen" → Icon, kein Browser-Chrome, fühlt sich nativ an.'),

    ('workflow', 'Sensor Pipeline Workflow',
     'Sensor → DB Workflow: '
     '1) Handy PWA nimmt Foto/GPS/Audio auf. '
     '2) POST /api/sensors mit sensor_type + payload (binary/JSON). '
     '3) Server speichert in dbai_net.sensor_data (BYTEA + JSONB). '
     '4) Background Worker: Vektor-Kernel (CLIP/Whisper) generiert Embedding. '
     '5) UPDATE sensor_data SET embedding = vector, is_processed = true. '
     '6) Ähnlichkeitssuche: SELECT * FROM sensor_data ORDER BY embedding <=> query_vector LIMIT 10.'),

    ('operational', 'USB-Gadget Boot Config',
     'USB-Gadget Konfiguration für Raspberry Pi: '
     '/boot/config.txt: dtoverlay=dwc2, dr_mode=otg. '
     '/boot/cmdline.txt: modules-load=dwc2,g_ether (nach rootwait einfügen). '
     'ConfigFS: /sys/kernel/config/usb_gadget/ghostshell/ mit idVendor=0x1d6b, idProduct=0x0104. '
     'Funktion: ECM (macOS/Linux/iOS nativ) + RNDIS (Windows nativ). '
     'IP: Stick=10.0.0.1, Peer=10.0.0.2, Subnet=/30. '
     'dnsmasq auf usb0: interface=usb0, dhcp-range=10.0.0.2,10.0.0.2,255.255.255.252,1h.'),

    ('operational', 'Hotspot Setup',
     'Hotspot-Setup: '
     'apt install hostapd dnsmasq avahi-daemon. '
     'hostapd.conf: interface=wlan0, ssid=GhostShell-Net, wpa_passphrase=ghost2026!secure, '
     'hw_mode=g, channel=6, wpa=2, wpa_key_mgmt=WPA-PSK, rsn_pairwise=CCMP. '
     'dnsmasq.conf: interface=wlan0, dhcp-range=192.168.4.100,192.168.4.200,12h, '
     'address=/ghost.local/192.168.4.1. '
     'avahi: hostname=ghost, allow-interfaces=usb0,wlan0. '
     'systemctl enable hostapd dnsmasq avahi-daemon. '
     'IP-Forwarding: sysctl -w net.ipv4.ip_forward=1.'),

    ('workflow', 'Alexander Zuchowski Demo-Script',
     'Demo-Script für Alexander Zuchowski: '
     '1) Stick zeigen. "Das ist GhostShell — ein 5D-KI-Betriebssystem." '
     '2) In Windows-Laptop stecken → Puff, Docker-Dashboard da (Dimension 1). '
     '3) Rausziehen, in dein iPhone stecken per USB-C → Puff, dieselben Daten auf dem Handy (Dimension 4). '
     '4) Stick an Powerbank legen. "Jetzt können wir beide gleichzeitig über WLAN in der Datenbank arbeiten, '
     'obwohl wir im tiefsten Keller ohne Empfang stehen." (Dimension 5). '
     '5) Foto von einem Bauteil machen → KI analysiert → Ergebnis in SQL. '
     '"Das ist kein Produkt mehr, das ist Magie."')
ON CONFLICT DO NOTHING;


-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  17. CHANGELOG                                                          ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝

INSERT INTO dbai_knowledge.changelog (version, change_type, title, description, author) VALUES
    ('0.13.0', 'feature', 'Mobile Bridge — 5-Dimensionales System',
     'Erweitert GhostShell vom 3-Boot-Stick zum 5-Dimensionalen KI-Betriebssystem. '
     'Neues Schema dbai_net mit 12 Tabellen, 4 Views, Seed-Daten für alle 5 Dimensionen. '
     'Neue Komponenten: USB-Gadget (RNDIS/ECM), WLAN-Hotspot (hostapd/dnsmasq), '
     'mDNS Discovery (ghost.local), PWA-Konfiguration, Sensor-Pipeline (GPS/Kamera/Audio→pgvector), '
     'Mobile Device Registry, DHCP-Lease-Tracking, Connection-Session-Monitoring, '
     'Hardware-Profile (RPi Zero 2 W, Radxa Zero), Boot-Dimensionen-Tabelle.',
     'ghost-system'),

    ('0.13.0', 'feature', 'Progressive Web App (PWA)',
     'PWA-Konfiguration in der Datenbank: manifest.json, Service-Worker-Config, Install-Prompt. '
     'Auf dem Handy erscheint "Zum Startbildschirm hinzufügen" → App-Icon ohne Browser-Leiste. '
     'Offline-fähig durch Network-First Caching. Background-Sync für Sensor-Daten.',
     'ghost-system'),

    ('0.13.0', 'feature', 'Sensor Pipeline — Handy→PostgreSQL',
     'Smartphone-Sensoren als Datenpipeline in PostgreSQL: '
     'GPS-Koordinaten, Kamera-Fotos, Sprachnotizen, QR-Scans, NFC-Tags. '
     'Binärdaten in BYTEA, Vektoren in pgvector (1536D). '
     'Beispiel: Foto von Bauteil → CLIP-Embedding → Ähnlichkeitssuche.',
     'ghost-system'),

    ('0.13.0', 'feature', 'Ghost-Net WLAN-Hotspot',
     'Air-Gap-fähiger WLAN-Hotspot: Stick spannt eigenes "GhostShell-Net" auf. '
     'Alle Geräte gleichzeitig verbunden — Teamarbeit ohne Router. '
     'Konfiguration in DB: SSID, Passphrase, Channel, DHCP-Range, Max-Clients.',
     'ghost-system'),

    ('0.13.0', 'feature', 'USB-C Direct Link (Dimension 4)',
     'Ethernet-over-USB via dwc2/g_ether: Stick per USB-C ans Handy. '
     'RNDIS für Windows, ECM für macOS/Linux/iOS. 480Mbit/s Direktverbindung. '
     'Keine Funkstörungen. Strom kommt direkt vom Handy.',
     'ghost-system'),

    ('0.13.0', 'feature', 'mDNS Discovery (ghost.local)',
     'Avahi/mDNS: Handy findet den Stick automatisch unter ghost.local. '
     'Keine IP-Adresse nötig. Service-Advertisement für Dashboard, API und PostgreSQL.',
     'ghost-system')
ON CONFLICT DO NOTHING;


-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  18. EVENT-LOGGING                                                      ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝

-- Event für die Migration
DO $$
BEGIN
    PERFORM dbai_event.dispatch_event(
        'system'::text, 'migration'::text, 5::smallint,
        jsonb_build_object(
            'migration', '68-mobile-bridge',
            'version', '0.13.0',
            'tables_created', 12,
            'views_created', 4,
            'dimensions', 5,
            'description', '5-Dimensionales KI-Betriebssystem: Mobile Bridge mit USB-Gadget, Hotspot, PWA, Sensor-Pipeline'
        )
    );
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Event dispatch skipped: %', SQLERRM;
END;
$$;


COMMIT;
