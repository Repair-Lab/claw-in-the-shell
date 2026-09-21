-- =============================================================================
-- DBAI Schema 59: Ergänze fehlende Spalten in dbai_ui.users
-- Einige API-Endpunkte erwarten zusätzliche Felder (display_name_custom, ghost_name, ...)
-- =============================================================================

ALTER TABLE dbai_ui.users
  ADD COLUMN IF NOT EXISTS display_name_custom TEXT,
  ADD COLUMN IF NOT EXISTS ghost_name TEXT,
  ADD COLUMN IF NOT EXISTS github_username TEXT,
  ADD COLUMN IF NOT EXISTS setup_completed BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS user_interests JSONB NOT NULL DEFAULT '[]'::JSONB,
  ADD COLUMN IF NOT EXISTS onboarding_data JSONB NOT NULL DEFAULT '{}'::JSONB;

-- Grant runtime access to allow reads/updates via API
GRANT SELECT, UPDATE ON dbai_ui.users TO dbai_runtime;
