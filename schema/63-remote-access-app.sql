-- ============================================================
-- Migration 63: Remote Access App (v0.12.0)
-- Desktop-Symbol für Mobile-Verbindung via QR-Code & PIN
-- ============================================================

BEGIN;

-- App registrieren
INSERT INTO dbai_ui.apps (
  app_id, name, description, icon,
  default_width, default_height, min_width, min_height,
  resizable, source_type, source_target,
  required_role, is_system, is_pinned,
  category, sort_order
) VALUES (
  'remote_access',
  'Remote Access',
  'Verbinde dein Handy oder Tablet mit GhostShell — QR-Code scannen, PIN eingeben, volle Kontrolle über den Browser.',
  '📱',
  750, 650, 500, 400,
  true, 'component', 'RemoteAccess',
  'user', true, false,
  'system', 55
)
ON CONFLICT (app_id) DO UPDATE SET
  name = EXCLUDED.name,
  description = EXCLUDED.description,
  icon = EXCLUDED.icon;

-- Changelog
INSERT INTO dbai_knowledge.changelog (version, change_type, title, description)
VALUES (
  '0.12.0', 'feature', 'Remote Access App',
  'Neue Desktop-App "Remote Access": QR-Code für sofortige Handy-Verbindung, 6-stellige PIN mit 5-Minuten-Ablauf, Netzwerk-Interface-Übersicht, WLAN-Erkennung, Copy-to-Clipboard für URL. Ermöglicht volle GhostShell-Steuerung von iOS/Android über den Browser.'
)
ON CONFLICT DO NOTHING;

-- System Memory
INSERT INTO dbai_knowledge.system_memory (category, title, content)
VALUES (
  'workflow', 'Remote Access Workflow',
  'Mobile-Verbindung: 1) Desktop-Icon "Remote Access" klicken. 2) QR-Code mit Handy scannen ODER URL manuell eingeben. 3) Optional PIN für sichere Authentifizierung. 4) GhostShell Dashboard öffnet sich im mobilen Browser. 5) "Zum Startbildschirm hinzufügen" für PWA-App-Feeling. Voraussetzung: PC und Handy im selben Netzwerk. API-Endpoints: /api/remote-access/info, /api/remote-access/pin, /api/remote-access/verify-pin.'
)
ON CONFLICT DO NOTHING;

COMMIT;
