-- =============================================================================
-- DBAI Schema 16: Desktop & UI — Das "Window-Manager" Schema
-- =============================================================================
-- Verwandelt die Datenbank in ein grafisches Betriebssystem.
-- Jedes "Fenster" im Browser zeigt den Inhalt einer SQL-View/Tabelle.
-- Der Desktop-Zustand liegt IN der DB — nicht im Browser-LocalStorage.
-- =============================================================================

-- Neues Schema für UI-Zustand
CREATE SCHEMA IF NOT EXISTS dbai_ui;
COMMENT ON SCHEMA dbai_ui IS 'Desktop-UI: Fenster, Themes, Widgets, Desktop-Config';

-- Grants
GRANT USAGE ON SCHEMA dbai_ui TO dbai_system;
GRANT USAGE ON SCHEMA dbai_ui TO dbai_llm;
GRANT USAGE ON SCHEMA dbai_ui TO dbai_monitor;

-- =============================================================================
-- 1. USERS & SESSIONS — Benutzer-Verwaltung
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_ui.users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username        TEXT NOT NULL UNIQUE,
    display_name    TEXT NOT NULL,
    password_hash   TEXT NOT NULL,  -- bcrypt via pgcrypto
    avatar_url      TEXT DEFAULT '/assets/default-avatar.svg',
    -- Rollen-Mapping
    db_role         TEXT NOT NULL DEFAULT 'dbai_monitor'
                    CHECK (db_role IN ('dbai_system', 'dbai_monitor', 'dbai_llm', 'dbai_recovery')),
    is_admin        BOOLEAN NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    -- Profil
    locale          TEXT NOT NULL DEFAULT 'de-DE',
    timezone        TEXT NOT NULL DEFAULT 'Europe/Berlin',
    preferences     JSONB NOT NULL DEFAULT '{}'::JSONB,
    -- Zeitstempel
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE dbai_ui.users IS
    'System-Benutzer. Login-Daten werden gegen diese Tabelle geprüft. Passwörter via pgcrypto/bcrypt.';

DROP TRIGGER IF EXISTS trg_users_updated ON dbai_ui.users;
CREATE TRIGGER trg_users_updated
    BEFORE UPDATE ON dbai_ui.users
    FOR EACH ROW EXECUTE FUNCTION dbai_core.update_timestamp();

-- Default-User: root (Passwort wird beim Bootstrap gesetzt)
-- INSERT in Seed-Data, nicht hier

-- =============================================================================
-- 2. SESSIONS — Aktive Sitzungen
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_ui.sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES dbai_ui.users(id) ON DELETE CASCADE,
    token           TEXT NOT NULL UNIQUE DEFAULT encode(gen_random_bytes(32), 'hex'),
    ip_address      INET,
    user_agent      TEXT,
    -- Status
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    last_activity   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '24 hours',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE dbai_ui.sessions IS
    'Aktive Browser-Sitzungen. Token wird als Cookie/Header gesendet.';

-- Abgelaufene Sessions aufräumen
CREATE OR REPLACE FUNCTION dbai_ui.cleanup_sessions()
RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER;
BEGIN
    DELETE FROM dbai_ui.sessions
    WHERE expires_at < NOW() OR (is_active = FALSE AND last_activity < NOW() - INTERVAL '1 hour');
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- 3. THEMES — Erscheinungsbilder
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_ui.themes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL UNIQUE,
    display_name    TEXT NOT NULL,
    description     TEXT,
    -- Farben
    colors          JSONB NOT NULL DEFAULT '{
        "bg_primary":    "#0a0a0f",
        "bg_secondary":  "#12121a",
        "bg_surface":    "#1a1a2e",
        "bg_elevated":   "#252540",
        "text_primary":  "#e0e0e0",
        "text_secondary":"#8888aa",
        "accent":        "#00ffcc",
        "accent_dim":    "#00aa88",
        "danger":        "#ff4444",
        "warning":       "#ffaa00",
        "success":       "#00ff88",
        "info":          "#4488ff",
        "border":        "#333355",
        "glow":          "rgba(0, 255, 204, 0.3)"
    }'::JSONB,
    -- Fonts
    fonts           JSONB NOT NULL DEFAULT '{
        "mono":    "\"JetBrains Mono\", \"Fira Code\", monospace",
        "sans":    "\"Inter\", \"Segoe UI\", sans-serif",
        "display": "\"Orbitron\", \"Rajdhani\", sans-serif"
    }'::JSONB,
    -- Effekte
    effects         JSONB NOT NULL DEFAULT '{
        "blur":         true,
        "glow":         true,
        "scanlines":    false,
        "crt":          false,
        "particles":    true,
        "animations":   true,
        "transparency": 0.85
    }'::JSONB,
    -- Boot-Screen Anpassungen
    boot_config     JSONB NOT NULL DEFAULT '{
        "font_color":  "#00ffcc",
        "speed_ms":    50,
        "show_logo":   true,
        "sound":       false
    }'::JSONB,
    is_default      BOOLEAN NOT NULL DEFAULT FALSE,
    is_builtin      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE dbai_ui.themes IS
    'Cyberpunk-Themes: Jeder User kann sein eigenes Look & Feel haben.';

-- =============================================================================
-- 4. DESKTOP CONFIG — Was liegt auf dem Desktop?
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_ui.desktop_config (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES dbai_ui.users(id) ON DELETE CASCADE,
    -- Hintergrund
    wallpaper_url   TEXT DEFAULT '/assets/wallpapers/grid-neural.svg',
    wallpaper_mode  TEXT NOT NULL DEFAULT 'cover'
                    CHECK (wallpaper_mode IN ('cover', 'contain', 'tile', 'center')),
    -- Grid/Layout
    grid_columns    INTEGER NOT NULL DEFAULT 12,
    grid_rows       INTEGER NOT NULL DEFAULT 8,
    snap_to_grid    BOOLEAN NOT NULL DEFAULT TRUE,
    -- Taskbar
    taskbar_position TEXT NOT NULL DEFAULT 'bottom'
                    CHECK (taskbar_position IN ('top', 'bottom', 'left', 'right')),
    taskbar_autohide BOOLEAN NOT NULL DEFAULT FALSE,
    -- Theme
    theme_id        UUID REFERENCES dbai_ui.themes(id),
    -- Desktop-Icons (Position + App-Referenz)
    icons           JSONB NOT NULL DEFAULT '[]'::JSONB,
    -- Pinned Apps in Taskbar
    pinned_apps     JSONB NOT NULL DEFAULT '[]'::JSONB,
    -- Zeitstempel
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id)
);

COMMENT ON TABLE dbai_ui.desktop_config IS
    'Desktop-Layout pro User: Hintergrund, Icons, Taskbar, Theme.';

DROP TRIGGER IF EXISTS trg_desktop_updated ON dbai_ui.desktop_config;
CREATE TRIGGER trg_desktop_updated
    BEFORE UPDATE ON dbai_ui.desktop_config
    FOR EACH ROW EXECUTE FUNCTION dbai_core.update_timestamp();

-- =============================================================================
-- 5. APPS — Registrierte Anwendungen
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_ui.apps (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    app_id          TEXT NOT NULL UNIQUE,    -- z.B. 'system-monitor', 'ghost-manager'
    name            TEXT NOT NULL,
    description     TEXT,
    icon            TEXT NOT NULL DEFAULT '📦',
    icon_url        TEXT,
    -- Fenster-Defaults
    default_width   INTEGER NOT NULL DEFAULT 800,
    default_height  INTEGER NOT NULL DEFAULT 600,
    min_width       INTEGER NOT NULL DEFAULT 320,
    min_height      INTEGER NOT NULL DEFAULT 240,
    resizable       BOOLEAN NOT NULL DEFAULT TRUE,
    -- Quelle: Welche SQL-View oder URL zeigt die App?
    source_type     TEXT NOT NULL DEFAULT 'component'
                    CHECK (source_type IN (
                        'component',    -- React-Komponente
                        'sql_view',     -- SQL-View wird als Tabelle gerendert
                        'terminal',     -- Eingebettetes Terminal
                        'iframe',       -- Externe URL (nur localhost!)
                        'canvas'        -- HTML5 Canvas Anwendung
                    )),
    source_target   TEXT,                -- View-Name oder Component-Name
    -- Berechtigungen
    required_role   TEXT DEFAULT 'dbai_monitor',
    is_system       BOOLEAN NOT NULL DEFAULT FALSE,
    is_pinned       BOOLEAN NOT NULL DEFAULT FALSE,
    -- Kategorien
    category        TEXT NOT NULL DEFAULT 'utility'
                    CHECK (category IN (
                        'system', 'monitor', 'development', 'ai',
                        'utility', 'settings', 'terminal', 'files'
                    )),
    sort_order      INTEGER NOT NULL DEFAULT 100,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE dbai_ui.apps IS
    'Registrierte Apps die als Fenster im Desktop geöffnet werden können.';

-- =============================================================================
-- 6. WINDOWS — Aktuell geöffnete Fenster pro Session
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_ui.windows (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES dbai_ui.sessions(id) ON DELETE CASCADE,
    app_id          UUID NOT NULL REFERENCES dbai_ui.apps(id),
    -- Position und Größe
    pos_x           INTEGER NOT NULL DEFAULT 100,
    pos_y           INTEGER NOT NULL DEFAULT 100,
    width           INTEGER NOT NULL DEFAULT 800,
    height          INTEGER NOT NULL DEFAULT 600,
    -- Zustand
    state           TEXT NOT NULL DEFAULT 'normal'
                    CHECK (state IN ('normal', 'minimized', 'maximized', 'fullscreen')),
    is_focused      BOOLEAN NOT NULL DEFAULT FALSE,
    z_index         INTEGER NOT NULL DEFAULT 1,
    -- Inhalt
    tab_title       TEXT,
    content_state   JSONB NOT NULL DEFAULT '{}'::JSONB,  -- App-spezifischer Zustand
    -- Zeitstempel
    opened_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE dbai_ui.windows IS
    'Offene Fenster pro Session. Jede Zeile = ein Fenster im Browser. Position/Größe werden bei Drag gespeichert.';

DROP TRIGGER IF EXISTS trg_windows_updated ON dbai_ui.windows;
CREATE TRIGGER trg_windows_updated
    BEFORE UPDATE ON dbai_ui.windows
    FOR EACH ROW EXECUTE FUNCTION dbai_core.update_timestamp();

-- =============================================================================
-- 7. NOTIFICATIONS — System-Benachrichtigungen
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_ui.notifications (
    id              BIGSERIAL PRIMARY KEY,
    user_id         UUID REFERENCES dbai_ui.users(id) ON DELETE CASCADE,
    -- NULL user_id = Broadcast an alle
    title           TEXT NOT NULL,
    message         TEXT NOT NULL,
    icon            TEXT DEFAULT '🔔',
    severity        TEXT NOT NULL DEFAULT 'info'
                    CHECK (severity IN ('info', 'success', 'warning', 'error', 'ghost')),
    -- Aktion bei Klick
    action_type     TEXT DEFAULT NULL
                    CHECK (action_type IS NULL OR action_type IN (
                        'open_app', 'navigate', 'run_sql', 'dismiss'
                    )),
    action_target   TEXT,    -- App-ID, URL oder SQL-Statement
    -- Status
    is_read         BOOLEAN NOT NULL DEFAULT FALSE,
    is_dismissed    BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE dbai_ui.notifications IS
    'Desktop-Benachrichtigungen. Pop-ups rechts unten. Ghost-Wechsel, Alerts, System-Events.';

-- =============================================================================
-- 8. BOOT LOG VIEW — Für die Boot-Animation im Browser
-- =============================================================================

CREATE OR REPLACE VIEW dbai_ui.vw_boot_sequence AS
WITH boot_steps AS (
    SELECT 1 AS step, 'bios'   AS phase, 'Initializing DBAI Kernel v0.3.0...' AS message, 200 AS delay_ms
    UNION ALL SELECT 2, 'bios', 'POST: CPU ' ||
        (SELECT COALESCE(value->>'cores', '?') FROM dbai_core.config WHERE key = 'system.cpu_cores')
        || ' Cores detected', 150
    UNION ALL SELECT 3, 'bios', 'POST: Memory ' ||
        (SELECT COALESCE((value->>'total_mb')::TEXT, '?') FROM dbai_core.config WHERE key = 'system.memory_mb')
        || ' MB available', 150
    UNION ALL SELECT 4, 'bios', 'POST: Storage subsystem OK', 100
    UNION ALL SELECT 5, 'kernel', 'Loading PostgreSQL Kernel...', 300
    UNION ALL SELECT 6, 'kernel', 'Mounting Database: dbai', 200
    UNION ALL SELECT 7, 'kernel', 'Checking schema integrity... ' ||
        (SELECT COUNT(*)::TEXT FROM information_schema.schemata WHERE schema_name LIKE 'dbai_%')
        || ' schemas found', 250
    UNION ALL SELECT 8, 'kernel', 'Initializing Row-Level Security...', 150
    UNION ALL SELECT 9, 'kernel', 'Loading sync primitives (Advisory Locks)...', 100
    UNION ALL SELECT 10, 'services', 'Starting Hardware Monitor...', 200
    UNION ALL SELECT 11, 'services', 'Starting Event Dispatcher...', 150
    UNION ALL SELECT 12, 'services', 'Loading Knowledge Library (' ||
        (SELECT COUNT(*)::TEXT FROM dbai_knowledge.module_registry)
        || ' modules registered)...', 200
    UNION ALL SELECT 13, 'services', 'Loading Error Patterns (' ||
        (SELECT COUNT(*)::TEXT FROM dbai_knowledge.error_patterns)
        || ' patterns known)...', 100
    UNION ALL SELECT 14, 'ghost', 'Detecting Ghost Models...', 300
    UNION ALL SELECT 15, 'ghost', 'Ghost detected: ' ||
        COALESCE(
            (SELECT string_agg(m.display_name, ', ' ORDER BY m.name)
             FROM dbai_llm.ghost_models m WHERE m.state != 'disabled' LIMIT 3),
            'No models registered'
        ), 200
    UNION ALL SELECT 16, 'ghost', 'Synaptic Bridge established...', 250
    UNION ALL SELECT 17, 'ghost', 'Active Ghosts: ' ||
        COALESCE(
            (SELECT COUNT(*)::TEXT FROM dbai_llm.active_ghosts WHERE state = 'active'),
            '0'
        ) || ' roles assigned', 150
    UNION ALL SELECT 18, 'ui', 'Initializing Window Manager...', 200
    UNION ALL SELECT 19, 'ui', 'Loading Desktop Configuration...', 150
    UNION ALL SELECT 20, 'ui', 'Self-Healing Watchdog active', 100
    UNION ALL SELECT 21, 'ready', '═══════════════════════════════════════════', 50
    UNION ALL SELECT 22, 'ready', '  DBAI — Database AI Operating System', 50
    UNION ALL SELECT 23, 'ready', '  "The Ghost in the Database"', 50
    UNION ALL SELECT 24, 'ready', '═══════════════════════════════════════════', 50
    UNION ALL SELECT 25, 'ready', 'System ready. Welcome.', 500
)
SELECT step, phase, message, delay_ms FROM boot_steps ORDER BY step;

COMMENT ON VIEW dbai_ui.vw_boot_sequence IS
    'Boot-Sequenz für die Browser-Animation. Liest Live-Daten aus der DB.';

-- =============================================================================
-- 9. HELPER FUNCTIONS
-- =============================================================================

-- Login-Funktion: Prüft Credentials, erstellt Session
CREATE OR REPLACE FUNCTION dbai_ui.login(
    p_username  TEXT,
    p_password  TEXT,
    p_ip        INET DEFAULT NULL,
    p_user_agent TEXT DEFAULT NULL
)
RETURNS JSONB AS $$
DECLARE
    v_user      dbai_ui.users%ROWTYPE;
    v_session   dbai_ui.sessions%ROWTYPE;
    v_token     TEXT;
BEGIN
    -- 1. User finden
    SELECT * INTO v_user FROM dbai_ui.users
    WHERE username = p_username AND is_active = TRUE;

    IF NOT FOUND THEN
        -- Absichtlich gleiche Meldung wie bei falschem Passwort (Security)
        RETURN jsonb_build_object('error', 'Ungültige Anmeldedaten', 'success', false);
    END IF;

    -- 2. Passwort prüfen (bcrypt via pgcrypto)
    IF v_user.password_hash != crypt(p_password, v_user.password_hash) THEN
        RETURN jsonb_build_object('error', 'Ungültige Anmeldedaten', 'success', false);
    END IF;

    -- 3. Session erstellen
    v_token := encode(gen_random_bytes(32), 'hex');
    INSERT INTO dbai_ui.sessions (user_id, token, ip_address, user_agent)
    VALUES (v_user.id, v_token, p_ip, p_user_agent)
    RETURNING * INTO v_session;

    -- 4. Last-Login aktualisieren
    UPDATE dbai_ui.users SET last_login_at = NOW() WHERE id = v_user.id;

    -- 5. Event dispatchen
    PERFORM dbai_event.dispatch_event(
        'system'::text, 'auth'::text, 3::smallint,
        jsonb_build_object('action', 'login', 'user', p_username)
    );

    -- 6. NOTIFY für WebSocket
    PERFORM pg_notify('user_login', jsonb_build_object(
        'user_id', v_user.id,
        'username', v_user.username,
        'session_id', v_session.id
    )::TEXT);

    RETURN jsonb_build_object(
        'success', true,
        'token', v_token,
        'session_id', v_session.id,
        'user', jsonb_build_object(
            'id', v_user.id,
            'username', v_user.username,
            'display_name', v_user.display_name,
            'is_admin', v_user.is_admin,
            'db_role', v_user.db_role,
            'locale', v_user.locale,
            'avatar_url', v_user.avatar_url
        )
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION dbai_ui.login IS
    'Login gegen die users-Tabelle. Erstellt Session, gibt Token zurück.';

-- Session validieren
CREATE OR REPLACE FUNCTION dbai_ui.validate_session(p_token TEXT)
RETURNS JSONB AS $$
DECLARE
    v_session dbai_ui.sessions%ROWTYPE;
    v_user    dbai_ui.users%ROWTYPE;
BEGIN
    SELECT * INTO v_session FROM dbai_ui.sessions
    WHERE token = p_token AND is_active = TRUE AND expires_at > NOW();

    IF NOT FOUND THEN
        RETURN jsonb_build_object('valid', false);
    END IF;

    -- Activity aktualisieren
    UPDATE dbai_ui.sessions SET last_activity = NOW() WHERE id = v_session.id;

    SELECT * INTO v_user FROM dbai_ui.users WHERE id = v_session.user_id;

    RETURN jsonb_build_object(
        'valid', true,
        'session_id', v_session.id,
        'user', jsonb_build_object(
            'id', v_user.id,
            'username', v_user.username,
            'display_name', v_user.display_name,
            'is_admin', v_user.is_admin,
            'db_role', v_user.db_role,
            'locale', v_user.locale,
            'preferences', v_user.preferences,
            'avatar_url', v_user.avatar_url
        )
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Alle Fenster einer Session laden
CREATE OR REPLACE FUNCTION dbai_ui.get_desktop_state(p_session_id UUID)
RETURNS JSONB AS $$
DECLARE
    v_session   dbai_ui.sessions%ROWTYPE;
    v_user      dbai_ui.users%ROWTYPE;
    v_desktop   dbai_ui.desktop_config%ROWTYPE;
    v_theme     dbai_ui.themes%ROWTYPE;
    v_windows   JSONB;
    v_apps      JSONB;
    v_notifs    JSONB;
BEGIN
    -- Session laden
    SELECT * INTO v_session FROM dbai_ui.sessions WHERE id = p_session_id AND is_active = TRUE;
    IF NOT FOUND THEN
        RETURN jsonb_build_object('error', 'Session ungültig');
    END IF;

    -- User laden
    SELECT * INTO v_user FROM dbai_ui.users WHERE id = v_session.user_id;

    -- Desktop-Config laden (oder Default)
    SELECT * INTO v_desktop FROM dbai_ui.desktop_config WHERE user_id = v_user.id;

    -- Theme laden
    IF v_desktop.theme_id IS NOT NULL THEN
        SELECT * INTO v_theme FROM dbai_ui.themes WHERE id = v_desktop.theme_id;
    ELSE
        SELECT * INTO v_theme FROM dbai_ui.themes WHERE is_default = TRUE LIMIT 1;
    END IF;

    -- Offene Fenster
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
    WHERE w.session_id = p_session_id;

    -- Verfügbare Apps
    SELECT COALESCE(jsonb_agg(jsonb_build_object(
        'id', a.id, 'app_id', a.app_id, 'name', a.name, 'icon', a.icon,
        'icon_url', a.icon_url, 'category', a.category, 'description', a.description,
        'source_type', a.source_type, 'source_target', a.source_target,
        'is_system', a.is_system,
        'default_width', a.default_width, 'default_height', a.default_height
    ) ORDER BY a.sort_order), '[]'::JSONB)
    INTO v_apps
    FROM dbai_ui.apps a;

    -- Ungelesene Notifications
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
        'desktop', jsonb_build_object(
            'wallpaper_url', v_desktop.wallpaper_url,
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

COMMENT ON FUNCTION dbai_ui.get_desktop_state IS
    'Lädt ALLES was der Browser braucht: User, Desktop, Theme, Fenster, Apps, Notifs, Ghosts.';

-- =============================================================================
-- 10. RLS für UI-Tabellen
-- =============================================================================

ALTER TABLE dbai_ui.users ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS users_system ON dbai_ui.users;
CREATE POLICY users_system ON dbai_ui.users FOR ALL TO dbai_system USING (TRUE);

ALTER TABLE dbai_ui.sessions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS sessions_system ON dbai_ui.sessions;
CREATE POLICY sessions_system ON dbai_ui.sessions FOR ALL TO dbai_system USING (TRUE);

ALTER TABLE dbai_ui.themes ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS themes_system ON dbai_ui.themes;
CREATE POLICY themes_system ON dbai_ui.themes FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS themes_read ON dbai_ui.themes;
CREATE POLICY themes_read ON dbai_ui.themes FOR SELECT TO dbai_monitor USING (TRUE);

ALTER TABLE dbai_ui.desktop_config ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS desktop_system ON dbai_ui.desktop_config;
CREATE POLICY desktop_system ON dbai_ui.desktop_config FOR ALL TO dbai_system USING (TRUE);

ALTER TABLE dbai_ui.apps ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS apps_system ON dbai_ui.apps;
CREATE POLICY apps_system ON dbai_ui.apps FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS apps_read ON dbai_ui.apps;
CREATE POLICY apps_read ON dbai_ui.apps FOR SELECT TO dbai_monitor USING (TRUE);
DROP POLICY IF EXISTS apps_llm_read ON dbai_ui.apps;
CREATE POLICY apps_llm_read ON dbai_ui.apps FOR SELECT TO dbai_llm USING (TRUE);

ALTER TABLE dbai_ui.windows ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS windows_system ON dbai_ui.windows;
CREATE POLICY windows_system ON dbai_ui.windows FOR ALL TO dbai_system USING (TRUE);

ALTER TABLE dbai_ui.notifications ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS notifs_system ON dbai_ui.notifications;
CREATE POLICY notifs_system ON dbai_ui.notifications FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS notifs_read ON dbai_ui.notifications;
CREATE POLICY notifs_read ON dbai_ui.notifications FOR SELECT TO dbai_monitor USING (TRUE);

-- Grants
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA dbai_ui TO dbai_system;
GRANT SELECT ON ALL TABLES IN SCHEMA dbai_ui TO dbai_monitor;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA dbai_ui TO dbai_system;
