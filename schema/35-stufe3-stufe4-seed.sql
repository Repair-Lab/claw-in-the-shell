-- =============================================================================
-- DBAI Stufe 3 + Stufe 4 — Seed-Daten
-- =============================================================================
-- RAG-Standard-Quellen, Anomalie-Modelle, Sandbox-Profile, Firewall-Zonen,
-- i18n-Basisübersetzungen und App-Registry-Einträge für das Desktop.
-- Spalten exakt an schema/33 + schema/34 angepasst.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- RAG-Quellen (Feature 15)
-- Spalten: source_name, source_type, enabled, priority, max_chunks, min_relevance, metadata
-- ---------------------------------------------------------------------------
INSERT INTO dbai_llm.rag_sources (source_name, source_type, enabled, priority, max_chunks, min_relevance, metadata) VALUES
  ('knowledge_base',   'knowledge_base',   true,  90, 10, 0.3, '{"description":"DBAI Knowledge Library","query":"SELECT title, content FROM dbai_knowledge.library WHERE content ILIKE ''%%{q}%%'' LIMIT 10"}'),
  ('system_memory',    'system_memory',    true,  80,  8, 0.3, '{"description":"System Memory Langzeitgedächtnis"}'),
  ('synaptic_recent',  'synaptic_memory',  true,  70, 10, 0.25,'{"description":"Synaptic Memory (letzte 24h)"}'),
  ('workspace_context','workspace',        true,  60,  8, 0.3, '{"description":"Workspace-Index (Dateien)"}'),
  ('browser_knowledge','browser',          true,  50,  5, 0.3, '{"description":"Browser-Wissen (importiert)"}'),
  ('config_context',   'config',           true,  40,  5, 0.3, '{"description":"Systemkonfiguration"}'),
  ('event_history',    'events',           true,  30,  5, 0.35,'{"description":"Event-Historie"}')
ON CONFLICT (source_name) DO NOTHING;


-- ---------------------------------------------------------------------------
-- Anomalie-Modelle (Feature 20)
-- Spalten: model_name, model_type, target_metric, parameters, threshold, is_active
-- ---------------------------------------------------------------------------
INSERT INTO dbai_system.anomaly_models (model_name, model_type, target_metric, parameters, threshold, is_active) VALUES
  ('cpu_zscore',      'statistical', 'cpu_percent',    '{"window_minutes": 60, "min_samples": 10}', 3.0,  true),
  ('memory_zscore',   'statistical', 'memory_percent', '{"window_minutes": 60, "min_samples": 10}', 2.5,  true),
  ('disk_zscore',     'statistical', 'disk_percent',   '{"window_minutes": 120, "min_samples": 5}', 2.0,  true),
  ('load_zscore',     'statistical', 'load_avg',       '{"window_minutes": 30, "min_samples": 10}', 3.0,  true),
  ('network_zscore',  'statistical', 'network_bytes',  '{"window_minutes": 15, "min_samples": 10}', 3.5,  true),
  ('io_wait_zscore',  'statistical', 'io_wait',        '{"window_minutes": 30, "min_samples": 10}', 2.5,  true),
  ('pg_connections',  'statistical', 'pg_connections', '{"window_minutes": 60, "min_samples": 10}', 2.0,  true)
ON CONFLICT (model_name) DO NOTHING;


-- ---------------------------------------------------------------------------
-- Sandbox-Profile (Feature 21)
-- Spalten: profile_name, sandbox_type, config, cpu_limit, memory_limit_mb,
--          io_limit_mbps, network_mode, is_default
-- ---------------------------------------------------------------------------
INSERT INTO dbai_system.sandbox_profiles (profile_name, sandbox_type, config, cpu_limit, memory_limit_mb, io_limit_mbps, network_mode, is_default) VALUES
  ('default',     'firejail',
   '{"description":"Standard-Sandbox mit eingeschränktem Netzwerk"}',
   50, 512, 100, 'none', true),
  ('network',     'firejail',
   '{"description":"Sandbox mit Netzwerkzugang"}',
   75, 1024, 200, 'restricted', false),
  ('strict',      'firejail',
   '{"description":"Maximale Isolation — kein Netzwerk, kein IPC"}',
   25, 256, 50, 'none', false),
  ('development', 'cgroup',
   '{"description":"Entwickler-Sandbox mit vollem Zugang"}',
   100, 4096, 500, 'host', false)
ON CONFLICT (profile_name) DO NOTHING;


-- ---------------------------------------------------------------------------
-- Firewall-Zonen (Feature 22)
-- Spalten: zone_name, description, default_policy, interfaces, is_active
-- ---------------------------------------------------------------------------
INSERT INTO dbai_system.firewall_zones (zone_name, description, default_policy, interfaces, is_active) VALUES
  ('trusted',  'Vertrauenswürdiges LAN',          'ACCEPT',  '{"lo"}',        true),
  ('home',     'Heimnetzwerk',                     'ACCEPT',  '{"eth0"}',      true),
  ('public',   'Öffentliches Netz — nur Basis',    'DROP',    '{"wlan0"}',     true),
  ('dmz',      'Demilitarisierte Zone — Server',   'DROP',    '{}',            false),
  ('block',    'Alles blockieren',                  'DROP',    '{}',            false)
ON CONFLICT (zone_name) DO NOTHING;

-- Standard-Firewall-Regeln
-- Spalten: rule_name, chain, action, protocol, source_ip, dest_ip, dest_port, priority, description, is_active
INSERT INTO dbai_system.firewall_rules (rule_name, chain, action, protocol, source_ip, dest_ip, dest_port, priority, description, is_active) VALUES
  ('allow_ssh',      'INPUT', 'ACCEPT', 'tcp',  NULL,          NULL, 22,   10,  'SSH erlauben',               true),
  ('allow_http',     'INPUT', 'ACCEPT', 'tcp',  NULL,          NULL, 80,   20,  'HTTP erlauben',              true),
  ('allow_https',    'INPUT', 'ACCEPT', 'tcp',  NULL,          NULL, 443,  30,  'HTTPS erlauben',             true),
  ('allow_pg_local', 'INPUT', 'ACCEPT', 'tcp',  '127.0.0.1',  NULL, 5432, 40,  'PostgreSQL nur lokal',       true),
  ('allow_web_local','INPUT', 'ACCEPT', 'tcp',  '127.0.0.1',  NULL, 3000, 50,  'DBAI Web nur lokal',         true),
  ('allow_ping',     'INPUT', 'ACCEPT', 'icmp', NULL,          NULL, NULL, 100, 'Ping erlauben',              true),
  ('default_drop',   'INPUT', 'DROP',   'all',  NULL,          NULL, NULL, 999, 'Default: Alles andere blockieren', true)
ON CONFLICT DO NOTHING;


-- ---------------------------------------------------------------------------
-- i18n Locales & Basis-Übersetzungen (Feature 19)
-- Spalten: locale, name_native, name_english, direction, is_default
-- ---------------------------------------------------------------------------
INSERT INTO dbai_ui.i18n_locales (locale, name_native, name_english, direction, is_default) VALUES
  ('de', 'Deutsch',    'German',      'ltr', true),
  ('en', 'English',    'English',     'ltr', false),
  ('fr', 'Français',   'French',      'ltr', false),
  ('es', 'Español',    'Spanish',     'ltr', false),
  ('pt', 'Português',  'Portuguese',  'ltr', false),
  ('ja', '日本語',     'Japanese',    'ltr', false),
  ('ko', '한국어',     'Korean',      'ltr', false),
  ('zh', '中文',       'Chinese',     'ltr', false),
  ('ar', 'العربية',    'Arabic',      'rtl', false),
  ('ru', 'Русский',    'Russian',     'ltr', false),
  ('tr', 'Türkçe',     'Turkish',     'ltr', false),
  ('hi', 'हिन्दी',      'Hindi',       'ltr', false)
ON CONFLICT (locale) DO NOTHING;

-- Beispiel-Übersetzungen (Deutsch ist Basis)
-- Spalten: locale, namespace, key, value
INSERT INTO dbai_ui.i18n_translations (locale, namespace, key, value) VALUES
  -- Desktop
  ('de', 'ui', 'desktop.title', 'DBAI Desktop'),
  ('en', 'ui', 'desktop.title', 'DBAI Desktop'),
  ('de', 'ui', 'desktop.logout', 'Abmelden'),
  ('en', 'ui', 'desktop.logout', 'Sign out'),
  -- Apps
  ('de', 'apps', 'app.terminal', 'Terminal'),
  ('en', 'apps', 'app.terminal', 'Terminal'),
  ('de', 'apps', 'app.browser_migration', 'Browser-Migration'),
  ('en', 'apps', 'app.browser_migration', 'Browser Migration'),
  ('de', 'apps', 'app.config_importer', 'System Config'),
  ('en', 'apps', 'app.config_importer', 'System Config'),
  ('de', 'apps', 'app.workspace_mapper', 'Workspace'),
  ('en', 'apps', 'app.workspace_mapper', 'Workspace'),
  ('de', 'apps', 'app.synaptic_viewer', 'Synaptischer Speicher'),
  ('en', 'apps', 'app.synaptic_viewer', 'Synaptic Memory'),
  ('de', 'apps', 'app.rag_manager', 'RAG Pipeline'),
  ('en', 'apps', 'app.rag_manager', 'RAG Pipeline'),
  ('de', 'apps', 'app.usb_installer', 'USB Installer'),
  ('en', 'apps', 'app.usb_installer', 'USB Installer'),
  ('de', 'apps', 'app.hotspot', 'WLAN Hotspot'),
  ('en', 'apps', 'app.hotspot', 'Wi-Fi Hotspot'),
  ('de', 'apps', 'app.immutable_fs', 'Immutable FS'),
  ('en', 'apps', 'app.immutable_fs', 'Immutable FS'),
  ('de', 'apps', 'app.anomaly', 'Anomalie-Erkennung'),
  ('en', 'apps', 'app.anomaly', 'Anomaly Detection'),
  ('de', 'apps', 'app.sandbox', 'App Sandbox'),
  ('en', 'apps', 'app.sandbox', 'App Sandbox'),
  ('de', 'apps', 'app.firewall', 'Firewall'),
  ('en', 'apps', 'app.firewall', 'Firewall'),
  -- Common
  ('de', 'ui', 'common.save', 'Speichern'),
  ('en', 'ui', 'common.save', 'Save'),
  ('de', 'ui', 'common.cancel', 'Abbrechen'),
  ('en', 'ui', 'common.cancel', 'Cancel'),
  ('de', 'ui', 'common.loading', 'Laden...'),
  ('en', 'ui', 'common.loading', 'Loading...'),
  ('de', 'ui', 'common.error', 'Fehler'),
  ('en', 'ui', 'common.error', 'Error'),
  ('de', 'ui', 'common.success', 'Erfolgreich'),
  ('en', 'ui', 'common.success', 'Success')
ON CONFLICT DO NOTHING;


-- ---------------------------------------------------------------------------
-- App-Registry: Neue Apps für das Desktop
-- Spalten: app_id, name, description, icon, source_type, source_target, category, sort_order, is_system
-- ---------------------------------------------------------------------------
INSERT INTO dbai_ui.apps (app_id, name, description, icon, source_type, source_target, category, sort_order, is_system) VALUES
  ('browser_migration', 'Browser-Migration', 'Chrome/Firefox Lesezeichen, History und Passwörter importieren', '🌐', 'component', 'BrowserMigration', 'utility', 300, false),
  ('config_importer',   'System Config',     'Systemkonfiguration aus /etc und ~/.config importieren',         '⚙️', 'component', 'ConfigImporter',   'utility', 310, false),
  ('workspace_mapper',  'Workspace',         'Dateisystem indexieren ohne Kopie',                              '📂', 'component', 'WorkspaceMapper',  'files', 320, false),
  ('synaptic_viewer',   'Synaptischer Speicher', 'Echtzeit-Speicher-Vektorisierung anzeigen',                  '🧠', 'component', 'SynapticViewer',   'ai',    330, false),
  ('rag_manager',       'RAG Pipeline',      'Retrieval-Augmented-Generation Quellen verwalten',               '🔗', 'component', 'RAGManager',       'ai',    340, false),
  ('usb_installer',     'USB Installer',     'ISO/IMG auf USB-Stick flashen',                                  '💾', 'component', 'USBInstaller',     'utility', 400, false),
  ('wlan_hotspot',      'WLAN Hotspot',      'WLAN-Hotspot erstellen und verwalten',                           '📡', 'component', 'WLANHotspot',      'system', 410, false),
  ('immutable_fs',      'Immutable FS',      'OverlayFS schreibgeschütztes Root-Dateisystem',                  '🛡️', 'component', 'ImmutableFS',      'system', 420, true),
  ('anomaly_detector',  'Anomalie-Erkennung','Z-Score Anomalie-Erkennung für Systemmetriken',                  '🔬', 'component', 'AnomalyDetector',  'monitor', 430, true),
  ('app_sandbox',       'App Sandbox',       'Firejail/cgroup-basierte App-Isolation',                         '📦', 'component', 'AppSandbox',       'system', 440, true),
  ('firewall_manager',  'Firewall',          'iptables Firewall-Regeln und Netzwerk-Policy',                   '🔥', 'component', 'FirewallManager',  'system', 450, true),
  ('terminal',          'Terminal',          'Linux-Terminal auf dem Desktop',                                   '💻', 'component', 'Terminal',          'terminal', 460, false)
ON CONFLICT (app_id) DO UPDATE SET
  name = EXCLUDED.name,
  icon = EXCLUDED.icon,
  source_target = EXCLUDED.source_target,
  category = EXCLUDED.category,
  description = EXCLUDED.description,
  sort_order = EXCLUDED.sort_order;


-- ---------------------------------------------------------------------------
-- Immutable-FS Standardkonfiguration (Feature 18)
-- Spalten: mode, protected_paths, writable_paths, overlay_upper, overlay_work,
--          snapshot_count, auto_rollback, is_active, metadata
-- ---------------------------------------------------------------------------
INSERT INTO dbai_system.immutable_config (mode, protected_paths, writable_paths, overlay_upper, overlay_work, snapshot_count, auto_rollback, is_active, metadata) VALUES
  ('disabled',
   ARRAY['/etc', '/usr', '/bin', '/sbin'],
   ARRAY['/tmp', '/var/tmp', '/home'],
   '/var/dbai/overlay/upper',
   '/var/dbai/overlay/work',
   5,
   true,
   false,
   '{"description": "Standardkonfiguration — Immutable-FS deaktiviert"}'
  )
ON CONFLICT DO NOTHING;
