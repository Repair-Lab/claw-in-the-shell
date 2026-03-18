-- ═══════════════════════════════════════════════════════════════
-- DBAI v0.10.1 — Fehlende App-Registrierungen + Settings
-- NetworkScanner + NodeManager in DB eintragen
-- ═══════════════════════════════════════════════════════════════

-- ─── 1. NetworkScanner registrieren ───
INSERT INTO dbai_ui.apps (
  app_id, name, description, icon, source_type, source_target,
  category, default_width, default_height, min_width, min_height,
  resizable, required_role, is_system, is_pinned, sort_order,
  default_settings, settings_schema
) VALUES (
  'network-scanner',
  'Netzwerk Scanner',
  'Entdeckt Web-UIs im lokalen Netzwerk: Router, NAS, Drucker, Kameras, Smart Home, Roboter, AI-Server',
  '🌐',
  'component',
  'NetworkScanner',
  'utility',
  950, 600, 500, 350,
  true, 'dbai_monitor', false, false, 58,
  '{
    "auto_scan_on_open": false,
    "scan_timeout_seconds": 30,
    "default_subnet": "auto",
    "show_offline_devices": true,
    "group_by_type": true,
    "refresh_interval_seconds": 0,
    "enable_web_ui_preview": true,
    "max_concurrent_scans": 5
  }'::jsonb,
  '{
    "properties": {
      "auto_scan_on_open": {"type": "boolean", "title": "Auto-Scan beim Öffnen", "description": "Netzwerk automatisch scannen wenn die App geöffnet wird"},
      "scan_timeout_seconds": {"type": "number", "title": "Scan-Timeout (Sek.)", "description": "Maximale Dauer eines Scans", "minimum": 5, "maximum": 120},
      "default_subnet": {"type": "string", "title": "Standard-Subnetz", "description": "auto = automatisch erkennen, oder z.B. 192.168.1.0/24"},
      "show_offline_devices": {"type": "boolean", "title": "Offline-Geräte anzeigen", "description": "Geräte anzeigen die beim letzten Scan nicht erreichbar waren"},
      "group_by_type": {"type": "boolean", "title": "Nach Typ gruppieren", "description": "Geräte nach Typ (Router, NAS, etc.) gruppieren"},
      "refresh_interval_seconds": {"type": "number", "title": "Auto-Refresh (Sek.)", "description": "0 = deaktiviert, sonst Intervall in Sekunden", "minimum": 0, "maximum": 3600},
      "enable_web_ui_preview": {"type": "boolean", "title": "Web-UI Preview", "description": "Vorschau der Web-Oberfläche im Tooltip anzeigen"},
      "max_concurrent_scans": {"type": "number", "title": "Max. parallele Scans", "description": "Maximale Anzahl gleichzeitiger Port-Scans", "minimum": 1, "maximum": 50}
    }
  }'::jsonb
) ON CONFLICT (app_id) DO UPDATE SET
  default_settings = EXCLUDED.default_settings,
  settings_schema = EXCLUDED.settings_schema;

-- ─── 2. NodeManager registrieren ───
INSERT INTO dbai_ui.apps (
  app_id, name, description, icon, source_type, source_target,
  category, default_width, default_height, min_width, min_height,
  resizable, required_role, is_system, is_pinned, sort_order,
  default_settings, settings_schema
) VALUES (
  'node-manager',
  'Node Manager',
  'Verwaltet Desktop-Netzwerkknoten: Services, Geräte, Cloud-Verbindungen als visuelle Nodes auf dem Desktop',
  '🔧',
  'component',
  'NodeManager',
  'system',
  800, 600, 400, 300,
  true, 'dbai_monitor', false, false, 59,
  '{
    "default_node_type": "service",
    "default_icon": "circle",
    "default_color": "#00f5ff",
    "snap_to_grid": false,
    "grid_size": 20,
    "show_templates": true,
    "confirm_delete": true,
    "auto_position": true
  }'::jsonb,
  '{
    "properties": {
      "default_node_type": {"type": "string", "title": "Standard Node-Typ", "enum": ["service", "device", "cloud", "custom"], "description": "Vorausgewählter Typ bei neuen Knoten"},
      "default_icon": {"type": "string", "title": "Standard Icon", "enum": ["circle", "play", "search", "nas", "phone", "server", "cloud", "printer", "camera", "iot", "chat", "message"], "description": "Vorausgewähltes Icon bei neuen Knoten"},
      "default_color": {"type": "string", "title": "Standard Farbe", "description": "Hex-Farbe für neue Knoten"},
      "snap_to_grid": {"type": "boolean", "title": "Am Raster einrasten", "description": "Knoten am Raster ausrichten"},
      "grid_size": {"type": "number", "title": "Rastergröße (px)", "description": "Abstand des Rasters in Pixeln", "minimum": 5, "maximum": 100},
      "show_templates": {"type": "boolean", "title": "Vorlagen anzeigen", "description": "Schnellvorlagen-Bereich anzeigen"},
      "confirm_delete": {"type": "boolean", "title": "Löschen bestätigen", "description": "Sicherheitsabfrage vor dem Löschen"},
      "auto_position": {"type": "boolean", "title": "Auto-Positionierung", "description": "Neue Knoten automatisch platzieren"}
    }
  }'::jsonb
) ON CONFLICT (app_id) DO UPDATE SET
  default_settings = EXCLUDED.default_settings,
  settings_schema = EXCLUDED.settings_schema;
