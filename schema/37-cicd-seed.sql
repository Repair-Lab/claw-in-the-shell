-- =============================================================================
-- DBAI CI/CD & OTA — Seed-Daten
-- =============================================================================

-- Update-Kanäle
INSERT INTO dbai_system.update_channels (channel_name, description, is_default, branch, check_interval) VALUES
  ('stable',  'Stabile Releases — getestet und verifiziert',  true,  'main',    300),
  ('beta',    'Beta-Releases — neue Features, leicht getestet', false, 'develop', 180),
  ('nightly', 'Nightly Builds — automatisch aus develop',       false, 'develop', 60),
  ('dev',     'Entwickler-Kanal — ungetestet, nur lokal',       false, 'main',    30)
ON CONFLICT (channel_name) DO NOTHING;

-- Initiales Release (aktuelle Version)
INSERT INTO dbai_system.system_releases
  (version, channel, release_notes, author, schema_version, is_published, published_at)
VALUES
  ('0.1.0', 'stable',
   'Initiales Release von GhostShell OS mit vollständigem PostgreSQL-Kernel, React-Desktop, Ghost-KI, Hardware-Abstraction, LLM-Bridge, Stufe 3+4 Features und CI/CD-System.',
   'ghost-system', 36, true, now())
ON CONFLICT (version) DO NOTHING;

-- App-Registry: Ghost Updater
INSERT INTO dbai_ui.apps (app_id, name, description, icon, source_type, source_target, category, sort_order, is_system) VALUES
  ('ghost_updater', 'Ghost Updater', 'CI/CD Pipeline & OTA Update-Kanal', '🚀', 'component', 'GhostUpdater', 'system', 470, true)
ON CONFLICT (app_id) DO UPDATE SET
  name = EXCLUDED.name,
  icon = EXCLUDED.icon,
  source_target = EXCLUDED.source_target,
  description = EXCLUDED.description,
  sort_order = EXCLUDED.sort_order;
