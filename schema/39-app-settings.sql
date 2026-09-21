-- =============================================================================
-- DBAI Schema 39: Per-App Settings System
-- Generisches Einstellungs-Framework für alle Desktop-Apps
-- =============================================================================
-- Jede App definiert ein JSON-Schema für ihre Einstellungen.
-- User-spezifische Werte werden in app_user_settings gespeichert.
-- Defaults kommen aus der apps-Tabelle (default_settings).
-- =============================================================================

-- ── 1. Apps-Tabelle um Settings-Spalten erweitern ──

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'dbai_ui' AND table_name = 'apps' AND column_name = 'default_settings'
    ) THEN
        ALTER TABLE dbai_ui.apps ADD COLUMN default_settings JSONB NOT NULL DEFAULT '{}'::JSONB;
        COMMENT ON COLUMN dbai_ui.apps.default_settings IS
            'Standard-Einstellungen der App als JSONB. Wird als Fallback genutzt wenn User keine eigenen Settings hat.';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'dbai_ui' AND table_name = 'apps' AND column_name = 'settings_schema'
    ) THEN
        ALTER TABLE dbai_ui.apps ADD COLUMN settings_schema JSONB NOT NULL DEFAULT '{}'::JSONB;
        COMMENT ON COLUMN dbai_ui.apps.settings_schema IS
            'JSON-Schema-Definition für App-Settings. Beschreibt Typen, Labels, Gruppen, min/max etc.';
    END IF;
END$$;


-- ── 2. Tabelle: User-spezifische App-Settings ──

CREATE TABLE IF NOT EXISTS dbai_ui.app_user_settings (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES dbai_ui.users(id) ON DELETE CASCADE,
    app_id      TEXT NOT NULL,  -- Referenz auf dbai_ui.apps.app_id
    settings    JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, app_id)
);

COMMENT ON TABLE dbai_ui.app_user_settings IS
    'Per-User, per-App Einstellungen. Überschreibt default_settings aus dbai_ui.apps.';

CREATE INDEX IF NOT EXISTS idx_app_user_settings_user ON dbai_ui.app_user_settings(user_id);
CREATE INDEX IF NOT EXISTS idx_app_user_settings_app  ON dbai_ui.app_user_settings(app_id);

-- Trigger für updated_at
CREATE OR REPLACE FUNCTION dbai_ui.update_app_settings_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_app_user_settings_updated ON dbai_ui.app_user_settings;
CREATE TRIGGER trg_app_user_settings_updated
    BEFORE UPDATE ON dbai_ui.app_user_settings
    FOR EACH ROW EXECUTE FUNCTION dbai_ui.update_app_settings_timestamp();


-- ── 3. Funktion: Merged Settings laden (Default + User-Override) ──

CREATE OR REPLACE FUNCTION dbai_ui.get_app_settings(
    p_user_id UUID,
    p_app_id  TEXT
)
RETURNS JSONB AS $$
DECLARE
    v_defaults JSONB;
    v_user     JSONB;
BEGIN
    -- Defaults aus App-Registrierung
    SELECT COALESCE(default_settings, '{}'::JSONB)
    INTO v_defaults
    FROM dbai_ui.apps WHERE app_id = p_app_id;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('error', 'App nicht gefunden');
    END IF;

    -- User-Settings (falls vorhanden)
    SELECT settings INTO v_user
    FROM dbai_ui.app_user_settings
    WHERE user_id = p_user_id AND app_id = p_app_id;

    -- Merge: User-Werte überschreiben Defaults
    IF v_user IS NOT NULL THEN
        RETURN v_defaults || v_user;
    ELSE
        RETURN v_defaults;
    END IF;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION dbai_ui.get_app_settings IS
    'Gibt gemergede App-Settings zurück: defaults aus apps-Tabelle + user-overrides aus app_user_settings.';


-- ── 4. Funktion: User-Settings speichern (UPSERT) ──

CREATE OR REPLACE FUNCTION dbai_ui.save_app_settings(
    p_user_id  UUID,
    p_app_id   TEXT,
    p_settings JSONB
)
RETURNS JSONB AS $$
BEGIN
    INSERT INTO dbai_ui.app_user_settings (user_id, app_id, settings)
    VALUES (p_user_id, p_app_id, p_settings)
    ON CONFLICT (user_id, app_id) DO UPDATE
        SET settings = dbai_ui.app_user_settings.settings || p_settings;

    RETURN dbai_ui.get_app_settings(p_user_id, p_app_id);
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION dbai_ui.save_app_settings IS
    'Speichert User-Settings für eine App (UPSERT mit Merge). Gibt gemergede Settings zurück.';


-- ── 5. Funktion: Settings auf Default zurücksetzen ──

CREATE OR REPLACE FUNCTION dbai_ui.reset_app_settings(
    p_user_id UUID,
    p_app_id  TEXT
)
RETURNS JSONB AS $$
BEGIN
    DELETE FROM dbai_ui.app_user_settings
    WHERE user_id = p_user_id AND app_id = p_app_id;

    RETURN dbai_ui.get_app_settings(p_user_id, p_app_id);
END;
$$ LANGUAGE plpgsql;


-- ── 6. Funktion: Alle App-Settings eines Users laden ──

CREATE OR REPLACE FUNCTION dbai_ui.get_all_app_settings(p_user_id UUID)
RETURNS JSONB AS $$
BEGIN
    RETURN (
        SELECT jsonb_object_agg(
            a.app_id,
            jsonb_build_object(
                'settings', dbai_ui.get_app_settings(p_user_id, a.app_id),
                'schema', a.settings_schema,
                'has_custom', EXISTS (
                    SELECT 1 FROM dbai_ui.app_user_settings aus
                    WHERE aus.user_id = p_user_id AND aus.app_id = a.app_id
                )
            )
        )
        FROM dbai_ui.apps a
        WHERE a.settings_schema != '{}'::JSONB
    );
END;
$$ LANGUAGE plpgsql STABLE;


-- ── 7. RLS & Grants ──

ALTER TABLE dbai_ui.app_user_settings ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS app_settings_system ON dbai_ui.app_user_settings;
CREATE POLICY app_settings_system ON dbai_ui.app_user_settings FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS app_settings_read ON dbai_ui.app_user_settings;
CREATE POLICY app_settings_read ON dbai_ui.app_user_settings FOR SELECT TO dbai_monitor USING (TRUE);

GRANT SELECT, INSERT, UPDATE, DELETE ON dbai_ui.app_user_settings TO dbai_system;
GRANT SELECT ON dbai_ui.app_user_settings TO dbai_monitor;


SELECT 'Schema 39: App-Settings-System erstellt' AS status;
