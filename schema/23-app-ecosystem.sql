-- =============================================================================
-- DBAI Schema 23: App Ecosystem — Software Catalog, Browser, Email, OAuth
-- =============================================================================
-- Das Rad nicht neu erfinden: Existierende Programme fernsteuern.
-- Browser via Playwright, E-Mails via IMAP/SMTP, Apps via Package Manager.
-- Jede App ist ein Datenstrom in einer Tabelle — die KI sieht Daten, nicht Pixel.
--
-- Komponenten:
--   1. Software Catalog (App Store via GitHub API & APT)
--   2. Browser Sessions (Headless Chromium via Playwright)
--   3. Email Bridge (IMAP/SMTP → inbox/outbox Tabellen)
--   4. OAuth Connections (Google, Drive, Gmail)
--   5. Workspace Sync (externe Daten als lokale Vektoren)
-- =============================================================================

-- =============================================================================
-- 1. SOFTWARE CATALOG — App Store als Repository-Tabelle
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_core.software_catalog (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Paket-Info
    package_name    TEXT NOT NULL,
    display_name    TEXT NOT NULL,
    description     TEXT,
    version         TEXT,
    latest_version  TEXT,
    -- Quelle
    source_type     TEXT NOT NULL DEFAULT 'apt'
                    CHECK (source_type IN (
                        'apt', 'pip', 'npm', 'github', 'flatpak',
                        'snap', 'cargo', 'go', 'custom'
                    )),
    source_url      TEXT,                    -- GitHub URL oder Registry
    repository      TEXT,                    -- z.B. 'main', 'universe'
    -- Klassifikation
    category        TEXT DEFAULT 'utility'
                    CHECK (category IN (
                        'system', 'development', 'productivity', 'media',
                        'communication', 'security', 'ai_ml', 'database',
                        'network', 'utility', 'game', 'custom'
                    )),
    tags            TEXT[] DEFAULT '{}',
    -- Installation
    install_command TEXT,                    -- z.B. 'apt install -y nginx'
    uninstall_command TEXT,
    install_state   TEXT NOT NULL DEFAULT 'available'
                    CHECK (install_state IN (
                        'available', 'installing', 'installed', 'updating',
                        'removing', 'broken', 'blocked'
                    )),
    installed_at    TIMESTAMPTZ,
    install_size_mb FLOAT,
    -- KI-Bewertung
    ghost_recommendation FLOAT DEFAULT 0.5, -- 0-1: Wie nuetzlich fuer den Nutzer
    ghost_review    TEXT,                    -- KI-Kommentar
    -- Metadaten
    stars           INTEGER,                 -- GitHub Stars
    downloads       BIGINT,                  -- Download-Zaehler
    license         TEXT,
    homepage        TEXT,
    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (package_name, source_type)
);

CREATE INDEX IF NOT EXISTS idx_software_state
    ON dbai_core.software_catalog(install_state);
CREATE INDEX IF NOT EXISTS idx_software_category
    ON dbai_core.software_catalog(category);
CREATE INDEX IF NOT EXISTS idx_software_tags
    ON dbai_core.software_catalog USING gin (tags);

-- =============================================================================
-- 2. BROWSER SESSIONS — Headless Browser (Playwright/Selenium)
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_core.browser_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Session
    session_name    TEXT,
    url             TEXT NOT NULL,
    -- Inhalt (die KI "sieht" Text, nicht Pixel)
    page_title      TEXT,
    page_text       TEXT,                    -- Extrahierter Seitentext
    page_html       TEXT,                    -- DOM-Snapshot (optional)
    page_links      JSONB DEFAULT '[]'::JSONB,  -- Gefundene Links
    page_forms      JSONB DEFAULT '[]'::JSONB,  -- Gefundene Formulare
    -- Screenshot
    screenshot_path TEXT,                    -- Pfad zum Screenshot
    -- KI-Analyse
    embedding       vector(1536),            -- Seiteninhalt als Vektor
    auto_summary    TEXT,                    -- KI-Zusammenfassung der Seite
    -- Status
    state           TEXT NOT NULL DEFAULT 'loading'
                    CHECK (state IN (
                        'loading', 'loaded', 'error', 'navigating',
                        'interacting', 'closed'
                    )),
    -- Verknuepfung
    task_id         UUID,                    -- Welcher Task hat das ausgeloest
    ghost_id        UUID REFERENCES dbai_llm.ghost_models(id),
    -- Performance
    load_time_ms    INTEGER,
    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_browser_embedding
    ON dbai_core.browser_sessions USING hnsw (embedding vector_cosine_ops);

-- =============================================================================
-- 3. EMAIL BRIDGE — IMAP/SMTP als Tabellen
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_event.email_accounts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Account
    account_name    TEXT NOT NULL UNIQUE,
    email_address   TEXT NOT NULL,
    display_name    TEXT,
    -- Server-Config (verschluesselt in Produktion)
    imap_host       TEXT NOT NULL,
    imap_port       INTEGER DEFAULT 993,
    smtp_host       TEXT NOT NULL,
    smtp_port       INTEGER DEFAULT 587,
    -- Auth
    auth_type       TEXT NOT NULL DEFAULT 'password'
                    CHECK (auth_type IN ('password', 'oauth2', 'app_password')),
    credentials_ref UUID REFERENCES dbai_core.api_keys(id),
    -- Sync
    sync_enabled    BOOLEAN DEFAULT TRUE,
    sync_interval_s INTEGER DEFAULT 300,     -- Alle 5 Minuten
    last_sync       TIMESTAMPTZ,
    sync_state      TEXT DEFAULT 'idle'
                    CHECK (sync_state IN ('idle', 'syncing', 'error')),
    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Inbox: Eingehende E-Mails als Tabellenzeilen
CREATE TABLE IF NOT EXISTS dbai_event.inbox (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID NOT NULL REFERENCES dbai_event.email_accounts(id),
    -- E-Mail-Daten
    message_id      TEXT UNIQUE,             -- RFC Message-ID
    from_address    TEXT NOT NULL,
    from_name       TEXT,
    to_addresses    TEXT[] NOT NULL DEFAULT '{}',
    cc_addresses    TEXT[] DEFAULT '{}',
    subject         TEXT NOT NULL DEFAULT '(kein Betreff)',
    body_text       TEXT,                    -- Plain-Text
    body_html       TEXT,                    -- HTML
    -- Anhaenge
    attachments     JSONB DEFAULT '[]'::JSONB,
    has_attachments BOOLEAN DEFAULT FALSE,
    -- KI-Analyse
    embedding       vector(1536),            -- Inhalt als Vektor
    auto_summary    TEXT,                    -- KI-Zusammenfassung
    auto_tags       TEXT[] DEFAULT '{}',     -- KI-Tags
    auto_priority   TEXT DEFAULT 'normal'
                    CHECK (auto_priority IN ('urgent', 'high', 'normal', 'low', 'spam')),
    auto_category   TEXT,                    -- KI-Kategorie
    sentiment       TEXT DEFAULT 'neutral'
                    CHECK (sentiment IN ('positive', 'neutral', 'negative', 'urgent')),
    -- Status
    is_read         BOOLEAN DEFAULT FALSE,
    is_starred      BOOLEAN DEFAULT FALSE,
    is_archived     BOOLEAN DEFAULT FALSE,
    is_deleted      BOOLEAN DEFAULT FALSE,
    -- Ghost-Verarbeitung
    ghost_response  TEXT,                    -- Vorgeschlagene Antwort vom Ghost
    needs_response  BOOLEAN DEFAULT FALSE,
    -- Timestamps
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    read_at         TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_inbox_account
    ON dbai_event.inbox(account_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_inbox_unread
    ON dbai_event.inbox(account_id) WHERE NOT is_read AND NOT is_deleted;
CREATE INDEX IF NOT EXISTS idx_inbox_embedding
    ON dbai_event.inbox USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_inbox_tags
    ON dbai_event.inbox USING gin (auto_tags);

-- Outbox: Ausgehende E-Mails
CREATE TABLE IF NOT EXISTS dbai_event.outbox (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID NOT NULL REFERENCES dbai_event.email_accounts(id),
    -- E-Mail-Daten
    to_addresses    TEXT[] NOT NULL,
    cc_addresses    TEXT[] DEFAULT '{}',
    bcc_addresses   TEXT[] DEFAULT '{}',
    subject         TEXT NOT NULL,
    body_text       TEXT,
    body_html       TEXT,
    -- Anhaenge
    attachments     JSONB DEFAULT '[]'::JSONB,
    -- Referenz (Antwort auf)
    reply_to_id     UUID REFERENCES dbai_event.inbox(id),
    -- Status
    state           TEXT NOT NULL DEFAULT 'draft'
                    CHECK (state IN (
                        'draft', 'review', 'approved', 'sending',
                        'sent', 'failed', 'cancelled'
                    )),
    -- Wer hat geschrieben?
    authored_by     TEXT DEFAULT 'human'
                    CHECK (authored_by IN ('human', 'ghost', 'template')),
    ghost_id        UUID REFERENCES dbai_llm.ghost_models(id),
    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at         TIMESTAMPTZ,
    scheduled_for   TIMESTAMPTZ              -- Zeitversetzter Versand
);

-- =============================================================================
-- 4. OAUTH CONNECTIONS — Google, Drive, Gmail
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_core.oauth_connections (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Provider
    provider        TEXT NOT NULL
                    CHECK (provider IN (
                        'google', 'microsoft', 'github', 'gitlab',
                        'slack', 'discord', 'notion', 'custom'
                    )),
    provider_user_id TEXT,                   -- User-ID beim Provider
    display_name    TEXT NOT NULL,
    email           TEXT,
    -- Tokens (verschluesselt in Produktion)
    access_token_ref  UUID REFERENCES dbai_core.api_keys(id),
    refresh_token_ref UUID REFERENCES dbai_core.api_keys(id),
    -- Scopes
    granted_scopes  TEXT[] NOT NULL DEFAULT '{}',
    -- Status
    is_connected    BOOLEAN NOT NULL DEFAULT TRUE,
    last_refresh    TIMESTAMPTZ,
    token_expires   TIMESTAMPTZ,
    -- Timestamps
    connected_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provider, provider_user_id)
);

-- =============================================================================
-- 5. WORKSPACE SYNC — Externe Daten lokal spiegeln
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_core.workspace_sync (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Quelle
    oauth_connection_id UUID REFERENCES dbai_core.oauth_connections(id),
    sync_type       TEXT NOT NULL
                    CHECK (sync_type IN (
                        'google_drive', 'google_docs', 'gmail_labels',
                        'github_repos', 'github_issues', 'notion_pages',
                        'onedrive', 'dropbox', 'custom'
                    )),
    -- Was wird synchronisiert
    remote_path     TEXT,                    -- z.B. '/My Drive/Projects/'
    local_table     TEXT,                    -- Ziel-Tabelle in DBAI
    -- Sync-Status
    sync_state      TEXT NOT NULL DEFAULT 'pending'
                    CHECK (sync_state IN ('pending', 'syncing', 'synced', 'error')),
    last_sync       TIMESTAMPTZ,
    items_synced    INTEGER DEFAULT 0,
    sync_errors     TEXT[] DEFAULT '{}',
    -- Config
    sync_interval_s INTEGER DEFAULT 600,     -- Alle 10 Minuten
    sync_direction  TEXT DEFAULT 'pull'
                    CHECK (sync_direction IN ('pull', 'push', 'bidirectional')),
    filter_pattern  TEXT,                    -- z.B. '*.pdf' oder 'label:important'
    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- 6. COMMAND INTERFACE — Sprache → SQL → Aktion
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_llm.command_history (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Eingabe
    user_input      TEXT NOT NULL,           -- "Suche auf GitHub nach Python-DB-Treibern"
    input_type      TEXT NOT NULL DEFAULT 'text'
                    CHECK (input_type IN ('text', 'voice', 'hotkey', 'scheduled')),
    -- KI-Interpretation
    interpreted_as  TEXT,                    -- Was die KI verstanden hat
    generated_sql   TEXT,                    -- Generiertes SQL
    generated_command TEXT,                  -- Generierter Shell-Befehl
    target_app      TEXT,                    -- Ziel-App (browser, email, system, etc.)
    -- Ausfuehrung
    action_id       UUID REFERENCES dbai_llm.proposed_actions(id),
    execution_state TEXT DEFAULT 'pending'
                    CHECK (execution_state IN (
                        'pending', 'interpreting', 'proposed', 'executing',
                        'completed', 'failed', 'cancelled'
                    )),
    -- Ergebnis
    result_text     TEXT,                    -- Antwort an den User
    result_data     JSONB,                   -- Strukturierte Ergebnisse
    -- Performance
    interpretation_ms INTEGER,
    execution_ms    INTEGER,
    tokens_used     INTEGER,
    -- Ghost
    ghost_id        UUID REFERENCES dbai_llm.ghost_models(id),
    ghost_role      TEXT,
    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_command_history_ts
    ON dbai_llm.command_history(created_at DESC);

-- =============================================================================
-- 7. FUNKTIONEN — App Ecosystem Logik
-- =============================================================================

-- ─── Software installieren (via task_queue) ───
CREATE OR REPLACE FUNCTION dbai_core.install_software(
    p_package_name  TEXT,
    p_source_type   TEXT DEFAULT 'apt'
) RETURNS UUID AS $$
DECLARE
    v_pkg dbai_core.software_catalog%ROWTYPE;
    v_task_id UUID;
BEGIN
    SELECT * INTO v_pkg FROM dbai_core.software_catalog
    WHERE package_name = p_package_name AND source_type = p_source_type;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Paket "%" (%) nicht im Katalog', p_package_name, p_source_type;
    END IF;

    IF v_pkg.install_state = 'installed' THEN
        RAISE EXCEPTION 'Paket "%" ist bereits installiert', p_package_name;
    END IF;

    -- Status aktualisieren
    UPDATE dbai_core.software_catalog
    SET install_state = 'installing', updated_at = NOW()
    WHERE id = v_pkg.id;

    -- Task in Queue
    INSERT INTO dbai_llm.task_queue
        (task_type, priority, input_data, state)
    VALUES
        ('generation', 3,
         jsonb_build_object(
             'action', 'install_software',
             'package', p_package_name,
             'source', p_source_type,
             'command', COALESCE(v_pkg.install_command,
                 CASE p_source_type
                     WHEN 'apt' THEN 'sudo apt install -y ' || p_package_name
                     WHEN 'pip' THEN 'pip install ' || p_package_name
                     WHEN 'npm' THEN 'npm install -g ' || p_package_name
                     WHEN 'github' THEN 'git clone ' || COALESCE(v_pkg.source_url, '')
                     ELSE 'echo "Unbekannte Quelle: ' || p_source_type || '"'
                 END
             ),
             'catalog_id', v_pkg.id
         ),
         'pending')
    RETURNING id INTO v_task_id;

    PERFORM pg_notify('software_install', json_build_object(
        'task_id', v_task_id,
        'package', p_package_name,
        'source', p_source_type
    )::TEXT);

    RETURN v_task_id;
END;
$$ LANGUAGE plpgsql;

-- ─── URL im Headless-Browser oeffnen ───
CREATE OR REPLACE FUNCTION dbai_core.browse_url(
    p_url           TEXT,
    p_session_name  TEXT DEFAULT NULL,
    p_ghost_id      UUID DEFAULT NULL
) RETURNS UUID AS $$
DECLARE
    v_session_id UUID;
    v_task_id UUID;
BEGIN
    -- Session erstellen
    INSERT INTO dbai_core.browser_sessions
        (session_name, url, state, ghost_id)
    VALUES
        (COALESCE(p_session_name, 'browse_' || LEFT(md5(p_url), 8)),
         p_url, 'loading', p_ghost_id)
    RETURNING id INTO v_session_id;

    -- Task fuer Python-Backend
    INSERT INTO dbai_llm.task_queue
        (task_type, priority, input_data, state)
    VALUES
        ('generation', 5,
         jsonb_build_object(
             'action', 'browse_url',
             'url', p_url,
             'session_id', v_session_id,
             'extract_text', TRUE,
             'take_screenshot', TRUE
         ),
         'pending')
    RETURNING id INTO v_task_id;

    PERFORM pg_notify('browser_action', json_build_object(
        'task_id', v_task_id,
        'session_id', v_session_id,
        'url', p_url
    )::TEXT);

    RETURN v_session_id;
END;
$$ LANGUAGE plpgsql;

-- ─── E-Mail senden ───
CREATE OR REPLACE FUNCTION dbai_event.send_email(
    p_account_name  TEXT,
    p_to            TEXT[],
    p_subject       TEXT,
    p_body          TEXT,
    p_reply_to      UUID DEFAULT NULL,
    p_authored_by   TEXT DEFAULT 'human'
) RETURNS UUID AS $$
DECLARE
    v_account dbai_event.email_accounts%ROWTYPE;
    v_outbox_id UUID;
BEGIN
    SELECT * INTO v_account FROM dbai_event.email_accounts
    WHERE account_name = p_account_name;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'E-Mail-Account "%" nicht gefunden', p_account_name;
    END IF;

    INSERT INTO dbai_event.outbox
        (account_id, to_addresses, subject, body_text,
         reply_to_id, authored_by, state)
    VALUES
        (v_account.id, p_to, p_subject, p_body,
         p_reply_to, p_authored_by, 'review')
    RETURNING id INTO v_outbox_id;

    PERFORM pg_notify('email_outbox', json_build_object(
        'outbox_id', v_outbox_id,
        'account', p_account_name,
        'to', p_to,
        'subject', p_subject,
        'authored_by', p_authored_by
    )::TEXT);

    RETURN v_outbox_id;
END;
$$ LANGUAGE plpgsql;

-- ─── Inbox durchsuchen (semantisch) ───
CREATE OR REPLACE FUNCTION dbai_event.search_inbox(
    p_query         TEXT,
    p_limit         INTEGER DEFAULT 20,
    p_account_name  TEXT DEFAULT NULL
) RETURNS TABLE (
    email_id UUID,
    from_address TEXT,
    subject TEXT,
    auto_summary TEXT,
    received_at TIMESTAMPTZ,
    is_read BOOLEAN,
    auto_priority TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        i.id,
        i.from_address,
        i.subject,
        i.auto_summary,
        i.received_at,
        i.is_read,
        i.auto_priority
    FROM dbai_event.inbox i
    LEFT JOIN dbai_event.email_accounts ea ON ea.id = i.account_id
    WHERE NOT i.is_deleted
      AND (p_account_name IS NULL OR ea.account_name = p_account_name)
      AND (
          i.subject ILIKE '%' || p_query || '%'
          OR i.body_text ILIKE '%' || p_query || '%'
          OR i.from_address ILIKE '%' || p_query || '%'
          OR p_query = ANY(i.auto_tags)
      )
    ORDER BY i.received_at DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- ─── Sprach-Befehl verarbeiten ───
CREATE OR REPLACE FUNCTION dbai_llm.process_command(
    p_user_input    TEXT,
    p_ghost_role    TEXT DEFAULT 'operator'
) RETURNS UUID AS $$
DECLARE
    v_cmd_id UUID;
    v_task_id UUID;
BEGIN
    -- Command speichern
    INSERT INTO dbai_llm.command_history
        (user_input, input_type, execution_state, ghost_role)
    VALUES
        (p_user_input, 'text', 'interpreting', p_ghost_role)
    RETURNING id INTO v_cmd_id;

    -- Task fuer Interpretation
    INSERT INTO dbai_llm.task_queue
        (task_type, priority, input_data, state)
    VALUES
        ('analysis', 3,
         jsonb_build_object(
             'action', 'interpret_command',
             'command_id', v_cmd_id,
             'user_input', p_user_input,
             'ghost_role', p_ghost_role,
             'available_apps', (
                 SELECT jsonb_agg(app_name)
                 FROM dbai_ui.app_streams WHERE is_active
             )
         ),
         'pending')
    RETURNING id INTO v_task_id;

    PERFORM pg_notify('user_command', json_build_object(
        'command_id', v_cmd_id,
        'task_id', v_task_id,
        'input', LEFT(p_user_input, 200)
    )::TEXT);

    RETURN v_cmd_id;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- 8. VIEWS
-- =============================================================================

CREATE OR REPLACE VIEW dbai_core.vw_software_catalog AS
SELECT
    sc.package_name,
    sc.display_name,
    sc.source_type,
    sc.category,
    sc.version,
    sc.install_state,
    sc.ghost_recommendation,
    sc.ghost_review,
    sc.stars,
    sc.license,
    sc.tags
FROM dbai_core.software_catalog sc
ORDER BY sc.ghost_recommendation DESC, sc.package_name;

CREATE OR REPLACE VIEW dbai_event.vw_inbox_summary AS
SELECT
    ea.account_name,
    ea.email_address,
    i.id AS email_id,
    i.from_address,
    i.from_name,
    i.subject,
    i.auto_summary,
    i.auto_priority,
    i.auto_tags,
    i.sentiment,
    i.is_read,
    i.is_starred,
    i.needs_response,
    i.ghost_response IS NOT NULL AS has_draft,
    i.received_at
FROM dbai_event.inbox i
JOIN dbai_event.email_accounts ea ON ea.id = i.account_id
WHERE NOT i.is_deleted AND NOT i.is_archived
ORDER BY
    CASE i.auto_priority
        WHEN 'urgent' THEN 1 WHEN 'high' THEN 2
        WHEN 'normal' THEN 3 WHEN 'low' THEN 4
        ELSE 5
    END,
    i.received_at DESC;

CREATE OR REPLACE VIEW dbai_core.vw_browser_sessions AS
SELECT
    bs.id,
    bs.session_name,
    bs.url,
    bs.page_title,
    bs.auto_summary,
    bs.state,
    bs.load_time_ms,
    gm.display_name AS ghost_name,
    bs.created_at
FROM dbai_core.browser_sessions bs
LEFT JOIN dbai_llm.ghost_models gm ON gm.id = bs.ghost_id
ORDER BY bs.created_at DESC;

CREATE OR REPLACE VIEW dbai_core.vw_oauth_status AS
SELECT
    oc.provider,
    oc.display_name,
    oc.email,
    oc.is_connected,
    oc.granted_scopes,
    oc.token_expires,
    CASE WHEN oc.token_expires < NOW() THEN 'expired'
         WHEN oc.token_expires < NOW() + INTERVAL '1 hour' THEN 'expiring_soon'
         ELSE 'valid'
    END AS token_status,
    oc.connected_at,
    oc.last_refresh
FROM dbai_core.oauth_connections oc
ORDER BY oc.provider;

CREATE OR REPLACE VIEW dbai_llm.vw_command_history AS
SELECT
    ch.user_input,
    ch.interpreted_as,
    ch.target_app,
    ch.execution_state,
    ch.result_text,
    ch.interpretation_ms,
    ch.execution_ms,
    ch.tokens_used,
    ch.ghost_role,
    gm.display_name AS ghost_name,
    ch.created_at
FROM dbai_llm.command_history ch
LEFT JOIN dbai_llm.ghost_models gm ON gm.id = ch.ghost_id
ORDER BY ch.created_at DESC;

-- =============================================================================
-- 9. ROW-LEVEL SECURITY
-- =============================================================================

-- software_catalog
ALTER TABLE dbai_core.software_catalog ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS software_system ON dbai_core.software_catalog;
CREATE POLICY software_system ON dbai_core.software_catalog
    FOR ALL TO dbai_system USING (TRUE) WITH CHECK (TRUE);
DROP POLICY IF EXISTS software_llm ON dbai_core.software_catalog;
CREATE POLICY software_llm ON dbai_core.software_catalog
    FOR SELECT TO dbai_llm USING (TRUE);
DROP POLICY IF EXISTS software_monitor ON dbai_core.software_catalog;
CREATE POLICY software_monitor ON dbai_core.software_catalog
    FOR SELECT TO dbai_monitor USING (TRUE);

-- browser_sessions
ALTER TABLE dbai_core.browser_sessions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS browser_system ON dbai_core.browser_sessions;
CREATE POLICY browser_system ON dbai_core.browser_sessions
    FOR ALL TO dbai_system USING (TRUE) WITH CHECK (TRUE);
DROP POLICY IF EXISTS browser_llm ON dbai_core.browser_sessions;
CREATE POLICY browser_llm ON dbai_core.browser_sessions
    FOR ALL TO dbai_llm USING (TRUE) WITH CHECK (TRUE);
DROP POLICY IF EXISTS browser_monitor ON dbai_core.browser_sessions;
CREATE POLICY browser_monitor ON dbai_core.browser_sessions
    FOR SELECT TO dbai_monitor USING (TRUE);

-- email_accounts
ALTER TABLE dbai_event.email_accounts ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS email_acc_system ON dbai_event.email_accounts;
CREATE POLICY email_acc_system ON dbai_event.email_accounts
    FOR ALL TO dbai_system USING (TRUE) WITH CHECK (TRUE);
DROP POLICY IF EXISTS email_acc_monitor ON dbai_event.email_accounts;
CREATE POLICY email_acc_monitor ON dbai_event.email_accounts
    FOR SELECT TO dbai_monitor USING (TRUE);

-- inbox
ALTER TABLE dbai_event.inbox ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS inbox_system ON dbai_event.inbox;
CREATE POLICY inbox_system ON dbai_event.inbox
    FOR ALL TO dbai_system USING (TRUE) WITH CHECK (TRUE);
DROP POLICY IF EXISTS inbox_llm ON dbai_event.inbox;
CREATE POLICY inbox_llm ON dbai_event.inbox
    FOR SELECT TO dbai_llm USING (NOT is_deleted);
DROP POLICY IF EXISTS inbox_monitor ON dbai_event.inbox;
CREATE POLICY inbox_monitor ON dbai_event.inbox
    FOR SELECT TO dbai_monitor USING (TRUE);

-- outbox
ALTER TABLE dbai_event.outbox ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS outbox_system ON dbai_event.outbox;
CREATE POLICY outbox_system ON dbai_event.outbox
    FOR ALL TO dbai_system USING (TRUE) WITH CHECK (TRUE);
DROP POLICY IF EXISTS outbox_llm ON dbai_event.outbox;
CREATE POLICY outbox_llm ON dbai_event.outbox
    FOR ALL TO dbai_llm USING (TRUE) WITH CHECK (TRUE);

-- oauth_connections
ALTER TABLE dbai_core.oauth_connections ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS oauth_system ON dbai_core.oauth_connections;
CREATE POLICY oauth_system ON dbai_core.oauth_connections
    FOR ALL TO dbai_system USING (TRUE) WITH CHECK (TRUE);
DROP POLICY IF EXISTS oauth_monitor ON dbai_core.oauth_connections;
CREATE POLICY oauth_monitor ON dbai_core.oauth_connections
    FOR SELECT TO dbai_monitor USING (TRUE);

-- workspace_sync
ALTER TABLE dbai_core.workspace_sync ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS wsync_system ON dbai_core.workspace_sync;
CREATE POLICY wsync_system ON dbai_core.workspace_sync
    FOR ALL TO dbai_system USING (TRUE) WITH CHECK (TRUE);
DROP POLICY IF EXISTS wsync_monitor ON dbai_core.workspace_sync;
CREATE POLICY wsync_monitor ON dbai_core.workspace_sync
    FOR SELECT TO dbai_monitor USING (TRUE);

-- command_history
ALTER TABLE dbai_llm.command_history ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS cmd_system ON dbai_llm.command_history;
CREATE POLICY cmd_system ON dbai_llm.command_history
    FOR ALL TO dbai_system USING (TRUE) WITH CHECK (TRUE);
DROP POLICY IF EXISTS cmd_llm ON dbai_llm.command_history;
CREATE POLICY cmd_llm ON dbai_llm.command_history
    FOR ALL TO dbai_llm USING (TRUE) WITH CHECK (TRUE);
DROP POLICY IF EXISTS cmd_monitor ON dbai_llm.command_history;
CREATE POLICY cmd_monitor ON dbai_llm.command_history
    FOR SELECT TO dbai_monitor USING (TRUE);

-- =============================================================================
-- FERTIG — App Ecosystem ist bereit
--
-- Nuetzliche Abfragen:
--   SELECT * FROM dbai_core.vw_software_catalog;
--   SELECT * FROM dbai_event.vw_inbox_summary;
--   SELECT * FROM dbai_core.vw_browser_sessions;
--   SELECT * FROM dbai_core.vw_oauth_status;
--   SELECT * FROM dbai_llm.vw_command_history;
--   SELECT dbai_core.install_software('nginx', 'apt');
--   SELECT dbai_core.browse_url('https://github.com/trending');
--   SELECT dbai_event.send_email('main', ARRAY['test@example.com'], 'Test', 'Hallo!');
--   SELECT dbai_event.search_inbox('Rechnung');
--   SELECT dbai_llm.process_command('Suche auf GitHub nach Python-DB-Treibern');
-- =============================================================================
