-- ==========================================================================
-- DBAI Schema 52 — Tab-Isolation (Virtual Desktops)
-- Jeder Browser-Tab = eigener virtueller Rechner
-- ==========================================================================

-- ── Tab-Instanzen ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dbai_ui.tab_instances (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES dbai_ui.sessions(id) ON DELETE CASCADE,
    tab_id          TEXT NOT NULL UNIQUE,           -- Frontend-generierte Tab-ID (sessionStorage)
    hostname        TEXT DEFAULT 'DBAI',            -- Virtueller Hostname pro Tab
    label           TEXT DEFAULT '',                -- User-wählbarer Name ("Arbeit", "Privat" etc.)
    wallpaper       TEXT DEFAULT '',                -- Eigenes Wallpaper pro Tab
    icon_order      JSONB DEFAULT '[]',             -- Icon-Reihenfolge (statt localStorage)
    folders         JSONB DEFAULT '{}',             -- Ordner-Konfiguration (statt localStorage)
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    last_heartbeat  TIMESTAMPTZ DEFAULT NOW(),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tab_instances_session ON dbai_ui.tab_instances(session_id);
CREATE INDEX IF NOT EXISTS idx_tab_instances_tab_id  ON dbai_ui.tab_instances(tab_id);

-- ── Windows: tab_id Spalte hinzufügen ──────────────────────────────────────
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'dbai_ui' AND table_name = 'windows' AND column_name = 'tab_id'
    ) THEN
        ALTER TABLE dbai_ui.windows ADD COLUMN tab_id TEXT;
    END IF;
END$$;

-- Index für tab-basierte Window-Queries
CREATE INDEX IF NOT EXISTS idx_windows_tab_id ON dbai_ui.windows(tab_id);

-- ── Funktion: Tab registrieren ─────────────────────────────────────────────
CREATE OR REPLACE FUNCTION dbai_ui.register_tab(
    p_session_id UUID,
    p_tab_id     TEXT,
    p_hostname   TEXT DEFAULT NULL,
    p_label      TEXT DEFAULT NULL
) RETURNS JSONB AS $$
DECLARE
    v_tab dbai_ui.tab_instances%ROWTYPE;
    v_count INTEGER;
BEGIN
    -- Prüfe ob Tab schon existiert
    SELECT * INTO v_tab FROM dbai_ui.tab_instances WHERE tab_id = p_tab_id;

    IF FOUND THEN
        -- Heartbeat updaten
        UPDATE dbai_ui.tab_instances
        SET last_heartbeat = NOW(), is_active = TRUE, session_id = p_session_id
        WHERE tab_id = p_tab_id;

        RETURN jsonb_build_object(
            'tab_id',   v_tab.tab_id,
            'id',       v_tab.id,
            'hostname', v_tab.hostname,
            'label',    v_tab.label,
            'created',  false
        );
    END IF;

    -- Zähle bestehende Tabs dieser Session für Auto-Hostname
    SELECT count(*) INTO v_count FROM dbai_ui.tab_instances WHERE session_id = p_session_id AND is_active;

    INSERT INTO dbai_ui.tab_instances (session_id, tab_id, hostname, label)
    VALUES (
        p_session_id,
        p_tab_id,
        COALESCE(p_hostname, 'DBAI-' || (v_count + 1)),
        COALESCE(p_label, 'Desktop ' || (v_count + 1))
    )
    RETURNING * INTO v_tab;

    RETURN jsonb_build_object(
        'tab_id',   v_tab.tab_id,
        'id',       v_tab.id,
        'hostname', v_tab.hostname,
        'label',    v_tab.label,
        'created',  true
    );
END;
$$ LANGUAGE plpgsql;

-- ── Funktion: Desktop-State pro Tab ────────────────────────────────────────
-- Basiert auf get_desktop_state(), aber filtert Windows per tab_id
-- und liefert Tab-spezifische Einstellungen (hostname, wallpaper etc.)
CREATE OR REPLACE FUNCTION dbai_ui.get_tab_desktop_state(
    p_session_id UUID,
    p_tab_id     TEXT
) RETURNS JSONB AS $$
DECLARE
    v_session   dbai_ui.sessions%ROWTYPE;
    v_user      dbai_ui.users%ROWTYPE;
    v_desktop   dbai_ui.desktop_config%ROWTYPE;
    v_theme     dbai_ui.themes%ROWTYPE;
    v_tab       dbai_ui.tab_instances%ROWTYPE;
    v_windows   JSONB;
    v_apps      JSONB;
    v_notifs    JSONB;
BEGIN
    SELECT * INTO v_session FROM dbai_ui.sessions WHERE id = p_session_id AND is_active = TRUE;
    IF NOT FOUND THEN RETURN jsonb_build_object('error', 'Session ungültig'); END IF;

    SELECT * INTO v_user FROM dbai_ui.users WHERE id = v_session.user_id;
    SELECT * INTO v_tab FROM dbai_ui.tab_instances WHERE tab_id = p_tab_id AND session_id = p_session_id;
    SELECT * INTO v_desktop FROM dbai_ui.desktop_config WHERE user_id = v_user.id;

    IF v_desktop.theme_id IS NOT NULL THEN
        SELECT * INTO v_theme FROM dbai_ui.themes WHERE id = v_desktop.theme_id;
    ELSE
        SELECT * INTO v_theme FROM dbai_ui.themes WHERE is_default = TRUE LIMIT 1;
    END IF;

    -- Fenster NUR für diesen Tab
    SELECT COALESCE(jsonb_agg(jsonb_build_object(
        'id', w.id, 'app_id', a.app_id, 'app_name', a.name, 'app_icon', a.icon,
        'pos_x', w.pos_x, 'pos_y', w.pos_y, 'width', w.width, 'height', w.height,
        'state', w.state, 'is_focused', w.is_focused, 'z_index', w.z_index,
        'tab_title', COALESCE(w.tab_title, a.name),
        'content_state', w.content_state,
        'source_type', a.source_type, 'source_target', a.source_target
    ) ORDER BY w.z_index), '[]'::JSONB)
    INTO v_windows
    FROM dbai_ui.windows w
    JOIN dbai_ui.apps a ON w.app_id = a.id
    WHERE w.session_id = p_session_id AND w.tab_id = p_tab_id;

    -- Alle Apps
    SELECT COALESCE(jsonb_agg(jsonb_build_object(
        'id', a.id, 'app_id', a.app_id, 'name', a.name, 'icon', a.icon,
        'icon_url', a.icon_url, 'category', a.category, 'description', a.description,
        'source_type', a.source_type, 'source_target', a.source_target,
        'is_system', a.is_system,
        'default_width', a.default_width, 'default_height', a.default_height
    ) ORDER BY a.sort_order), '[]'::JSONB)
    INTO v_apps
    FROM dbai_ui.apps a;

    -- Notifications
    SELECT COALESCE(jsonb_agg(jsonb_build_object(
        'id', n.id, 'title', n.title, 'message', n.message, 'icon', n.icon,
        'severity', n.severity, 'action_type', n.action_type,
        'action_target', n.action_target, 'created_at', n.created_at
    ) ORDER BY n.created_at DESC), '[]'::JSONB)
    INTO v_notifs
    FROM dbai_ui.notifications n
    WHERE (n.user_id = v_user.id OR n.user_id IS NULL)
      AND n.is_dismissed = FALSE
      AND (n.expires_at IS NULL OR n.expires_at > NOW());

    RETURN jsonb_build_object(
        'user', jsonb_build_object(
            'id', v_user.id, 'username', v_user.username,
            'display_name', v_user.display_name, 'avatar_url', v_user.avatar_url
        ),
        'tab', CASE WHEN v_tab.tab_id IS NOT NULL THEN jsonb_build_object(
            'tab_id', v_tab.tab_id,
            'hostname', v_tab.hostname,
            'label', v_tab.label,
            'wallpaper', v_tab.wallpaper,
            'icon_order', v_tab.icon_order,
            'folders', v_tab.folders
        ) ELSE '{}'::JSONB END,
        'desktop', jsonb_build_object(
            'wallpaper_url', COALESCE(v_tab.wallpaper, v_desktop.wallpaper_url),
            'wallpaper_mode', v_desktop.wallpaper_mode,
            'grid_columns', v_desktop.grid_columns,
            'taskbar_position', v_desktop.taskbar_position,
            'icons', v_desktop.icons,
            'pinned_apps', v_desktop.pinned_apps
        ),
        'theme', jsonb_build_object(
            'name', v_theme.name, 'colors', v_theme.colors,
            'fonts', v_theme.fonts, 'effects', v_theme.effects,
            'boot_config', v_theme.boot_config
        ),
        'windows', v_windows,
        'apps', v_apps,
        'notifications', v_notifs,
        'ghosts', (SELECT COALESCE(jsonb_agg(row_to_json(g)), '[]'::JSONB)
                   FROM dbai_llm.vw_active_ghosts g)
    );
END;
$$ LANGUAGE plpgsql;

-- ── Inaktive Tabs aufräumen (älter als 4 Stunden) ─────────────────────────
CREATE OR REPLACE FUNCTION dbai_ui.cleanup_stale_tabs() RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER;
BEGIN
    -- Windows der inaktiven Tabs löschen
    DELETE FROM dbai_ui.windows
    WHERE tab_id IN (
        SELECT tab_id FROM dbai_ui.tab_instances
        WHERE last_heartbeat < NOW() - INTERVAL '4 hours'
    );

    -- Inaktive Tabs löschen
    WITH deleted AS (
        DELETE FROM dbai_ui.tab_instances
        WHERE last_heartbeat < NOW() - INTERVAL '4 hours'
        RETURNING id
    )
    SELECT count(*) INTO v_count FROM deleted;

    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

-- ── Berechtigungen für Runtime-User ────────────────────────────────────────
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dbai_runtime') THEN
        EXECUTE 'GRANT ALL ON dbai_ui.tab_instances TO dbai_runtime';
    END IF;
END$$;
