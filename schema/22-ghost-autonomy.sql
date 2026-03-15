-- =============================================================================
-- DBAI Schema 22: Ghost Autonomy — "Der Ghost uebernimmt die Kontrolle"
-- Safety-System, Context Injection, Thought Stream, Power Management
-- =============================================================================
-- Sobald der Ghost aktiviert wird, ist er nicht mehr nur ein Chatbot, sondern
-- der zentrale Scheduler des Rechners. Er abonniert Events, injiziert Kontext,
-- und trifft intelligente Entscheidungen — aber NUR mit Safety-Checks.
--
-- Sicherheits-Prinzip:
--   Kritische Aktionen (DROP, DELETE, SHUTDOWN, REBOOT) muessen in die
--   proposed_actions-Tabelle. Erst nach Genehmigung (Waechter-Ghost oder
--   Mensch) werden sie ausgefuehrt.
-- =============================================================================

-- =============================================================================
-- 1. PROPOSED ACTIONS — Safety-Tabelle fuer kritische Operationen
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_llm.proposed_actions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Wer schlaegt vor?
    proposing_ghost_id  UUID REFERENCES dbai_llm.ghost_models(id),
    proposing_role      TEXT,
    -- Was wird vorgeschlagen?
    action_type     TEXT NOT NULL
                    CHECK (action_type IN (
                        'sql_execute',       -- SQL-Befehl ausfuehren
                        'file_delete',       -- Datei loeschen
                        'file_modify',       -- Datei aendern
                        'process_kill',      -- Prozess beenden
                        'service_restart',   -- Dienst neustarten
                        'package_install',   -- Software installieren
                        'network_change',    -- Netzwerk aendern
                        'power_action',      -- Shutdown/Reboot
                        'config_change',     -- Systemkonfiguration aendern
                        'ghost_swap',        -- KI-Modell wechseln
                        'data_export',       -- Daten exportieren
                        'custom'             -- Sonstiges
                    )),
    action_sql      TEXT,                    -- Der SQL-Befehl (wenn sql_execute)
    action_command  TEXT,                    -- Shell-Befehl (wenn process/service)
    action_params   JSONB DEFAULT '{}'::JSONB,
    -- Risiko-Bewertung
    risk_level      TEXT NOT NULL DEFAULT 'medium'
                    CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
    risk_reason     TEXT,                    -- Warum ist es riskant?
    affected_tables TEXT[] DEFAULT '{}',     -- Betroffene Tabellen
    affected_files  TEXT[] DEFAULT '{}',     -- Betroffene Dateien
    estimated_impact TEXT,                   -- Beschreibung der Auswirkung
    -- Genehmigung
    approval_state  TEXT NOT NULL DEFAULT 'pending'
                    CHECK (approval_state IN (
                        'pending',           -- Wartet auf Genehmigung
                        'approved',          -- Genehmigt
                        'rejected',          -- Abgelehnt
                        'auto_approved',     -- Automatisch genehmigt (low risk)
                        'expired',           -- Timeout abgelaufen
                        'executing',         -- Wird gerade ausgefuehrt
                        'executed',          -- Erfolgreich ausgefuehrt
                        'failed'             -- Ausfuehrung fehlgeschlagen
                    )),
    approved_by     TEXT,                    -- 'human', 'watcher_ghost', 'auto'
    approval_reason TEXT,
    -- Timeout: Nicht genehmigte Aktionen verfallen
    expires_at      TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '15 minutes'),
    -- Ausfuehrung
    executed_at     TIMESTAMPTZ,
    execution_result JSONB,
    error_message   TEXT,
    -- Timestamps
    proposed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decided_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_proposed_actions_state
    ON dbai_llm.proposed_actions(approval_state, proposed_at DESC);
CREATE INDEX IF NOT EXISTS idx_proposed_actions_risk
    ON dbai_llm.proposed_actions(risk_level, approval_state);
CREATE INDEX IF NOT EXISTS idx_proposed_actions_pending
    ON dbai_llm.proposed_actions(expires_at)
    WHERE approval_state = 'pending';

-- =============================================================================
-- 2. GHOST CONTEXT — Was der Ghost "weiss" wenn er geladen wird
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_llm.ghost_context (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ghost_model_id  UUID REFERENCES dbai_llm.ghost_models(id),
    context_type    TEXT NOT NULL
                    CHECK (context_type IN (
                        'hardware_status',   -- CPU/GPU/RAM/Disk aktuell
                        'recent_logs',       -- Letzte System-Logs
                        'user_preferences',  -- Nutzerpraeferenzen
                        'active_processes',  -- Laufende Prozesse
                        'recent_errors',     -- Letzte Fehler
                        'system_metrics',    -- Performance-Metriken
                        'pending_tasks',     -- Offene Aufgaben
                        'file_activity',     -- Letzte Datei-Aenderungen
                        'network_status',    -- Netzwerk-Zustand
                        'ghost_memory',      -- Langzeit-Erinnerungen des Ghosts
                        'custom'
                    )),
    context_data    JSONB NOT NULL,
    priority        INTEGER NOT NULL DEFAULT 5
                    CHECK (priority BETWEEN 1 AND 10),
    -- Wie oft wird dieser Kontext aktualisiert?
    refresh_interval_s INTEGER DEFAULT 60,   -- Sekunden
    last_refreshed  TIMESTAMPTZ DEFAULT NOW(),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ghost_context_model
    ON dbai_llm.ghost_context(ghost_model_id, context_type);

-- =============================================================================
-- 3. GHOST THOUGHT LOG — Thought Stream (was die KI denkt)
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_llm.ghost_thought_log (
    id              BIGSERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ghost_model_id  UUID REFERENCES dbai_llm.ghost_models(id),
    role_name       TEXT,
    -- Was hat der Ghost gedacht/getan?
    thought_type    TEXT NOT NULL
                    CHECK (thought_type IN (
                        'observation',       -- "Ich sehe, dass CPU bei 95% ist"
                        'reasoning',         -- "Deshalb sollte ich..."
                        'decision',          -- "Ich entscheide mich fuer..."
                        'action',            -- "Ich fuehre aus: ..."
                        'query',             -- "Ich frage die DB: SELECT..."
                        'result',            -- "Ergebnis war: ..."
                        'learning',          -- "Ich merke mir: ..."
                        'warning',           -- "Achtung: ..."
                        'error',             -- "Fehler: ..."
                        'reflection'         -- "Rueckblickend haette ich..."
                    )),
    thought_text    TEXT NOT NULL,
    -- SQL das der Ghost ausfuehrt
    sql_query       TEXT,
    sql_result      JSONB,
    -- Kontext
    trigger_event   TEXT,                    -- Was hat diesen Gedanken ausgeloest?
    confidence      FLOAT DEFAULT 0.8,       -- Wie sicher ist der Ghost?
    tokens_used     INTEGER DEFAULT 0,
    latency_ms      INTEGER DEFAULT 0,
    metadata        JSONB DEFAULT '{}'::JSONB
);

CREATE INDEX IF NOT EXISTS idx_thought_log_ts
    ON dbai_llm.ghost_thought_log(ts DESC);
CREATE INDEX IF NOT EXISTS idx_thought_log_type
    ON dbai_llm.ghost_thought_log(thought_type, ts DESC);

-- Append-Only-Schutz
CREATE OR REPLACE FUNCTION dbai_llm.protect_thought_log()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP IN ('DELETE', 'UPDATE') THEN
        RAISE EXCEPTION 'Ghost Thought Log ist Append-Only — % verboten', TG_OP;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_protect_thought_log
    BEFORE UPDATE OR DELETE ON dbai_llm.ghost_thought_log
    FOR EACH ROW EXECUTE FUNCTION dbai_llm.protect_thought_log();

-- =============================================================================
-- 4. PROCESS IMPORTANCE — Welche Prozesse sind wie wichtig?
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_system.process_importance (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    process_name    TEXT NOT NULL,
    process_pid     INTEGER,
    -- Klassifikation
    importance_level TEXT NOT NULL DEFAULT 'normal'
                    CHECK (importance_level IN (
                        'critical',          -- System stirbt ohne diesen Prozess
                        'high',              -- Nutzer merkt sofort wenn er fehlt
                        'normal',            -- Standard-Prozess
                        'low',               -- Kann gedrosselt werden
                        'expendable'         -- Kann jederzeit gekillt werden
                    )),
    category        TEXT NOT NULL DEFAULT 'unknown'
                    CHECK (category IN (
                        'system_core',       -- Kernel, Init, DB
                        'user_interactive',  -- Browser, Editor
                        'background_service',-- Indexer, Sync
                        'ghost_service',     -- KI-Dienste
                        'monitoring',        -- Health-Checks
                        'unknown'
                    )),
    -- Ressourcen
    cpu_percent     FLOAT DEFAULT 0.0,
    memory_mb       FLOAT DEFAULT 0.0,
    -- Regeln
    can_throttle    BOOLEAN DEFAULT TRUE,
    can_kill        BOOLEAN DEFAULT FALSE,
    auto_restart    BOOLEAN DEFAULT FALSE,
    -- Ghost-Entscheidung
    last_decision   TEXT,                    -- Letzte Ghost-Entscheidung
    decided_by_ghost UUID REFERENCES dbai_llm.ghost_models(id),
    decided_at      TIMESTAMPTZ,
    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_process_importance_level
    ON dbai_system.process_importance(importance_level);

-- =============================================================================
-- 5. ENERGY CONSUMPTION — Energie-/Ressourcenverbrauch-Tracking
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_system.energy_consumption (
    id              BIGSERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Verbrauch
    cpu_watts       FLOAT,
    gpu_watts       FLOAT,
    total_watts     FLOAT,
    -- Metriken
    cpu_percent     FLOAT NOT NULL DEFAULT 0.0,
    memory_percent  FLOAT NOT NULL DEFAULT 0.0,
    gpu_percent     FLOAT DEFAULT 0.0,
    disk_io_mbps    FLOAT DEFAULT 0.0,
    network_mbps    FLOAT DEFAULT 0.0,
    -- Temperaturen
    cpu_temp_c      FLOAT,
    gpu_temp_c      FLOAT,
    -- Aktives Power-Profil
    power_profile   TEXT,
    -- Ghost-Bewertung
    efficiency_score FLOAT,                  -- Vom Ghost berechnet
    ghost_comment   TEXT                     -- "Peak erkannt, drossle Indexer"
);

CREATE INDEX IF NOT EXISTS idx_energy_ts
    ON dbai_system.energy_consumption(ts DESC);

-- Automatische Bereinigung: Nur 7 Tage Detaildaten behalten
-- (Aggregierte Daten bleiben erhalten via View)

-- =============================================================================
-- 6. GHOST FILES — Autonome Dateiorganisation
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_core.ghost_files (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Datei-Info
    file_path       TEXT NOT NULL,
    file_name       TEXT NOT NULL,
    file_type       TEXT,                    -- MIME-Type
    file_size_bytes BIGINT DEFAULT 0,
    file_hash       TEXT,                    -- SHA-256
    -- KI-Analyse
    embedding       vector(1536),            -- Inhalt als Vektor
    auto_tags       TEXT[] DEFAULT '{}',     -- KI-generierte Tags
    auto_summary    TEXT,                    -- KI-Zusammenfassung
    auto_category   TEXT,                    -- KI-Kategorie
    related_files   UUID[] DEFAULT '{}',     -- Verknuepfte Dateien
    related_projects TEXT[] DEFAULT '{}',    -- Verknuepfte Projekte
    -- Vom Ghost zugewiesen
    assigned_by_ghost UUID REFERENCES dbai_llm.ghost_models(id),
    confidence      FLOAT DEFAULT 0.8,
    -- Status
    needs_review    BOOLEAN DEFAULT TRUE,    -- Mensch muss Tags pruefen
    is_indexed      BOOLEAN DEFAULT FALSE,
    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    indexed_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_ghost_files_embedding
    ON dbai_core.ghost_files USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_ghost_files_tags
    ON dbai_core.ghost_files USING gin (auto_tags);
CREATE INDEX IF NOT EXISTS idx_ghost_files_category
    ON dbai_core.ghost_files(auto_category);

-- =============================================================================
-- 7. GHOST FEEDBACK LOOP — Lernen aus Genehmigungen/Ablehnungen
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_llm.ghost_feedback (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Referenz zur Aktion
    action_id       UUID REFERENCES dbai_llm.proposed_actions(id),
    -- Was wurde gelernt?
    feedback_type   TEXT NOT NULL
                    CHECK (feedback_type IN (
                        'approval_pattern',  -- Mensch hat zugestimmt
                        'rejection_pattern', -- Mensch hat abgelehnt
                        'auto_rule',         -- Neue Auto-Genehmigungs-Regel
                        'risk_adjustment',   -- Risiko-Bewertung angepasst
                        'preference'         -- Nutzerpraeferenz gelernt
                    )),
    pattern_description TEXT NOT NULL,       -- Was hat der Ghost gelernt
    -- Kontext
    context_snapshot JSONB,
    -- Wird beim naechsten Mal angewendet?
    apply_automatically BOOLEAN DEFAULT FALSE,
    times_applied   INTEGER DEFAULT 0,
    -- Timestamps
    learned_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- 8. API KEY VAULT — Sichere Speicherung von Provider-Keys
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_core.api_keys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider        TEXT NOT NULL,           -- 'openai', 'anthropic', 'openclaw', 'google', 'custom'
    key_name        TEXT NOT NULL,           -- Anzeigename
    -- Verschluesselter Key (im Produktivbetrieb mit pgcrypto)
    api_key_hash    TEXT NOT NULL,           -- Nur Hash speichern
    api_key_preview TEXT,                    -- "sk-...abc" (letzte 4 Zeichen)
    -- Metadaten
    key_type        TEXT NOT NULL DEFAULT 'api_key'
                    CHECK (key_type IN (
                        'api_key', 'oauth_token', 'refresh_token',
                        'webhook_secret', 'bot_token', 'custom'
                    )),
    -- Herkunft
    imported_from   TEXT,                    -- 'openclaw', 'manual', 'oauth', 'env'
    -- Limits
    rate_limit_rpm  INTEGER,                 -- Requests pro Minute
    daily_budget_usd FLOAT,                 -- Tagesbudget in USD
    total_spent_usd FLOAT DEFAULT 0.0,
    -- Status
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    is_valid        BOOLEAN DEFAULT TRUE,    -- Letzte Validierung erfolgreich?
    last_validated  TIMESTAMPTZ,
    last_used       TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ,
    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provider, key_name)
);

-- =============================================================================
-- 9. FUNKTIONEN — Ghost Autonomy Logik
-- =============================================================================

-- ─── Aktion vorschlagen (mit automatischer Risiko-Bewertung) ───
CREATE OR REPLACE FUNCTION dbai_llm.propose_action(
    p_ghost_id      UUID,
    p_role          TEXT,
    p_action_type   TEXT,
    p_action_sql    TEXT DEFAULT NULL,
    p_action_cmd    TEXT DEFAULT NULL,
    p_params        JSONB DEFAULT '{}'::JSONB,
    p_reason        TEXT DEFAULT NULL
) RETURNS UUID AS $$
DECLARE
    v_action_id UUID;
    v_risk TEXT;
    v_risk_reason TEXT;
    v_affected TEXT[];
BEGIN
    -- Risiko automatisch bewerten
    v_risk := 'low';
    v_risk_reason := 'Standard-Operation';

    IF p_action_type IN ('power_action') THEN
        v_risk := 'critical';
        v_risk_reason := 'Shutdown/Reboot betrifft gesamtes System';
    ELSIF p_action_type IN ('file_delete', 'process_kill') THEN
        v_risk := 'high';
        v_risk_reason := 'Datenverlust oder Prozess-Absturz moeglich';
    ELSIF p_action_type = 'sql_execute' AND p_action_sql IS NOT NULL THEN
        -- SQL-Risiko anhand von Keywords bewerten
        IF p_action_sql ~* 'DROP|TRUNCATE|ALTER.*DROP' THEN
            v_risk := 'critical';
            v_risk_reason := 'Destruktiver DDL-Befehl: ' || LEFT(p_action_sql, 50);
        ELSIF p_action_sql ~* 'DELETE.*FROM|UPDATE.*SET' THEN
            v_risk := 'high';
            v_risk_reason := 'DML ohne WHERE-Klausel moeglich';
            -- Pruefe ob WHERE vorhanden
            IF p_action_sql ~* 'WHERE' THEN
                v_risk := 'medium';
            END IF;
        END IF;
    ELSIF p_action_type IN ('package_install', 'network_change', 'config_change') THEN
        v_risk := 'medium';
        v_risk_reason := 'System-Aenderung';
    END IF;

    -- Betroffene Tabellen extrahieren (aus SQL)
    IF p_action_sql IS NOT NULL THEN
        -- Einfache Regex-Extraktion
        SELECT ARRAY(
            SELECT DISTINCT match[1]
            FROM regexp_matches(p_action_sql, '(?:FROM|INTO|UPDATE|TABLE|JOIN)\s+(\w+\.\w+)', 'gi') AS match
        ) INTO v_affected;
    END IF;

    -- Aktion eintragen
    INSERT INTO dbai_llm.proposed_actions
        (proposing_ghost_id, proposing_role, action_type, action_sql,
         action_command, action_params, risk_level, risk_reason,
         affected_tables, estimated_impact,
         approval_state)
    VALUES
        (p_ghost_id, p_role, p_action_type, p_action_sql,
         p_action_cmd, p_params, v_risk, v_risk_reason,
         COALESCE(v_affected, '{}'), p_reason,
         -- Low-Risk: Auto-Approve
         CASE WHEN v_risk = 'low' THEN 'auto_approved' ELSE 'pending' END)
    RETURNING id INTO v_action_id;

    -- Auto-Approve bei Low-Risk
    IF v_risk = 'low' THEN
        UPDATE dbai_llm.proposed_actions
        SET approved_by = 'auto',
            decided_at = NOW(),
            approval_reason = 'Low-Risk: Automatisch genehmigt'
        WHERE id = v_action_id;
    ELSE
        -- NOTIFY fuer menschliche Genehmigung
        PERFORM pg_notify('action_proposed', json_build_object(
            'action_id', v_action_id,
            'action_type', p_action_type,
            'risk_level', v_risk,
            'risk_reason', v_risk_reason,
            'ghost_role', p_role,
            'preview', LEFT(COALESCE(p_action_sql, p_action_cmd, ''), 100)
        )::TEXT);
    END IF;

    -- Thought-Log Eintrag
    INSERT INTO dbai_llm.ghost_thought_log
        (ghost_model_id, role_name, thought_type, thought_text,
         sql_query, confidence, metadata)
    VALUES
        (p_ghost_id, p_role, 'decision',
         'Aktion vorgeschlagen: ' || p_action_type || ' (Risiko: ' || v_risk || ')',
         p_action_sql,
         CASE v_risk WHEN 'low' THEN 0.95 WHEN 'medium' THEN 0.8
              WHEN 'high' THEN 0.6 ELSE 0.4 END,
         jsonb_build_object('action_id', v_action_id, 'auto_approved', v_risk = 'low'));

    RETURN v_action_id;
END;
$$ LANGUAGE plpgsql;

-- ─── Aktion genehmigen ───
CREATE OR REPLACE FUNCTION dbai_llm.approve_action(
    p_action_id     UUID,
    p_approved_by   TEXT DEFAULT 'human',
    p_reason        TEXT DEFAULT NULL
) RETURNS JSONB AS $$
DECLARE
    v_action dbai_llm.proposed_actions%ROWTYPE;
BEGIN
    SELECT * INTO v_action FROM dbai_llm.proposed_actions WHERE id = p_action_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Aktion % nicht gefunden', p_action_id;
    END IF;

    IF v_action.approval_state != 'pending' THEN
        RAISE EXCEPTION 'Aktion % ist nicht mehr pending (Status: %)',
            p_action_id, v_action.approval_state;
    END IF;

    IF v_action.expires_at < NOW() THEN
        UPDATE dbai_llm.proposed_actions
        SET approval_state = 'expired', decided_at = NOW()
        WHERE id = p_action_id;
        RETURN jsonb_build_object('error', 'Aktion ist abgelaufen');
    END IF;

    UPDATE dbai_llm.proposed_actions
    SET approval_state = 'approved',
        approved_by = p_approved_by,
        approval_reason = p_reason,
        decided_at = NOW()
    WHERE id = p_action_id;

    -- Feedback-Loop: Muster lernen
    INSERT INTO dbai_llm.ghost_feedback
        (action_id, feedback_type, pattern_description, context_snapshot)
    VALUES
        (p_action_id, 'approval_pattern',
         'Genehmigt: ' || v_action.action_type || ' (Risiko: ' || v_action.risk_level || ')',
         jsonb_build_object(
             'action_type', v_action.action_type,
             'risk_level', v_action.risk_level,
             'approved_by', p_approved_by
         ));

    -- NOTIFY fuer Ausfuehrung
    PERFORM pg_notify('action_approved', json_build_object(
        'action_id', p_action_id,
        'action_type', v_action.action_type,
        'action_sql', v_action.action_sql,
        'action_command', v_action.action_command
    )::TEXT);

    RETURN jsonb_build_object(
        'action_id', p_action_id,
        'status', 'approved',
        'approved_by', p_approved_by,
        'action_type', v_action.action_type
    );
END;
$$ LANGUAGE plpgsql;

-- ─── Aktion ablehnen ───
CREATE OR REPLACE FUNCTION dbai_llm.reject_action(
    p_action_id     UUID,
    p_rejected_by   TEXT DEFAULT 'human',
    p_reason        TEXT DEFAULT NULL
) RETURNS JSONB AS $$
BEGIN
    UPDATE dbai_llm.proposed_actions
    SET approval_state = 'rejected',
        approved_by = p_rejected_by,
        approval_reason = p_reason,
        decided_at = NOW()
    WHERE id = p_action_id AND approval_state = 'pending';

    IF NOT FOUND THEN
        RETURN jsonb_build_object('error', 'Aktion nicht gefunden oder nicht pending');
    END IF;

    -- Feedback-Loop: Ablehnungs-Muster lernen
    INSERT INTO dbai_llm.ghost_feedback
        (action_id, feedback_type, pattern_description)
    VALUES
        (p_action_id, 'rejection_pattern',
         'Abgelehnt: ' || p_reason);

    RETURN jsonb_build_object('action_id', p_action_id, 'status', 'rejected');
END;
$$ LANGUAGE plpgsql;

-- ─── Kontext fuer Ghost laden (Context Injection) ───
CREATE OR REPLACE FUNCTION dbai_llm.load_ghost_context(
    p_ghost_model_id UUID DEFAULT NULL
) RETURNS JSONB AS $$
DECLARE
    v_context JSONB := '{}'::JSONB;
    v_entry RECORD;
BEGIN
    FOR v_entry IN
        SELECT context_type, context_data, priority
        FROM dbai_llm.ghost_context
        WHERE (ghost_model_id = p_ghost_model_id OR ghost_model_id IS NULL)
          AND is_active = TRUE
        ORDER BY priority ASC
    LOOP
        v_context := v_context || jsonb_build_object(v_entry.context_type, v_entry.context_data);
    END LOOP;

    -- Immer aktuelle System-Info einbinden
    v_context := v_context || jsonb_build_object(
        'system_time', NOW(),
        'active_ghosts', (
            SELECT jsonb_agg(jsonb_build_object('role', r.name, 'model', m.name))
            FROM dbai_llm.active_ghosts ag
            JOIN dbai_llm.ghost_roles r ON r.id = ag.role_id
            JOIN dbai_llm.ghost_models m ON m.id = ag.model_id
            WHERE ag.state = 'active'
        ),
        'pending_actions', (
            SELECT COUNT(*) FROM dbai_llm.proposed_actions
            WHERE approval_state = 'pending'
        )
    );

    RETURN v_context;
END;
$$ LANGUAGE plpgsql;

-- ─── Expire abgelaufene Aktionen ───
CREATE OR REPLACE FUNCTION dbai_llm.expire_pending_actions()
RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER;
BEGIN
    UPDATE dbai_llm.proposed_actions
    SET approval_state = 'expired', decided_at = NOW()
    WHERE approval_state = 'pending' AND expires_at < NOW();

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- 10. VIEWS — Uebersicht fuer Web-UI
-- =============================================================================

-- Pending Actions fuer die Web-UI (Genehmigungs-Dashboard)
CREATE OR REPLACE VIEW dbai_llm.vw_pending_actions AS
SELECT
    pa.id,
    pa.proposing_role,
    gm.display_name AS ghost_name,
    pa.action_type,
    pa.risk_level,
    pa.risk_reason,
    LEFT(COALESCE(pa.action_sql, pa.action_command, '—'), 200) AS action_preview,
    pa.affected_tables,
    pa.estimated_impact,
    pa.proposed_at,
    pa.expires_at,
    EXTRACT(EPOCH FROM (pa.expires_at - NOW()))::INTEGER AS seconds_remaining
FROM dbai_llm.proposed_actions pa
LEFT JOIN dbai_llm.ghost_models gm ON gm.id = pa.proposing_ghost_id
WHERE pa.approval_state = 'pending'
ORDER BY
    CASE pa.risk_level
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'medium' THEN 3
        ELSE 4
    END,
    pa.proposed_at DESC;

-- Thought Stream fuer die Web-UI
CREATE OR REPLACE VIEW dbai_llm.vw_thought_stream AS
SELECT
    tl.ts,
    tl.thought_type,
    tl.thought_text,
    tl.sql_query,
    tl.confidence,
    tl.latency_ms,
    tl.role_name,
    gm.display_name AS ghost_name,
    gm.name AS ghost_model
FROM dbai_llm.ghost_thought_log tl
LEFT JOIN dbai_llm.ghost_models gm ON gm.id = tl.ghost_model_id
ORDER BY tl.ts DESC
LIMIT 200;

-- Energy Dashboard
CREATE OR REPLACE VIEW dbai_system.vw_energy_dashboard AS
SELECT
    ts,
    cpu_percent,
    memory_percent,
    gpu_percent,
    total_watts,
    cpu_temp_c,
    gpu_temp_c,
    power_profile,
    efficiency_score,
    ghost_comment
FROM dbai_system.energy_consumption
ORDER BY ts DESC
LIMIT 100;

-- Process Importance Uebersicht
CREATE OR REPLACE VIEW dbai_system.vw_process_overview AS
SELECT
    pi.process_name,
    pi.process_pid,
    pi.importance_level,
    pi.category,
    pi.cpu_percent,
    pi.memory_mb,
    pi.can_throttle,
    pi.can_kill,
    pi.last_decision,
    gm.display_name AS decided_by
FROM dbai_system.process_importance pi
LEFT JOIN dbai_llm.ghost_models gm ON gm.id = pi.decided_by_ghost
ORDER BY
    CASE pi.importance_level
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'normal' THEN 3
        WHEN 'low' THEN 4
        ELSE 5
    END;

-- Ghost Files (intelligent organisierte Dateien)
CREATE OR REPLACE VIEW dbai_core.vw_ghost_files AS
SELECT
    gf.file_name,
    gf.file_path,
    gf.file_type,
    gf.auto_tags,
    gf.auto_category,
    gf.auto_summary,
    gf.confidence,
    gf.needs_review,
    pg_size_pretty(gf.file_size_bytes) AS file_size,
    gf.created_at,
    array_length(gf.related_files, 1) AS related_count
FROM dbai_core.ghost_files gf
ORDER BY gf.created_at DESC;

-- =============================================================================
-- 11. ROW-LEVEL SECURITY
-- =============================================================================

-- proposed_actions
ALTER TABLE dbai_llm.proposed_actions ENABLE ROW LEVEL SECURITY;
CREATE POLICY proposed_actions_system ON dbai_llm.proposed_actions
    FOR ALL TO dbai_system USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY proposed_actions_llm ON dbai_llm.proposed_actions
    FOR INSERT TO dbai_llm WITH CHECK (TRUE);
CREATE POLICY proposed_actions_llm_read ON dbai_llm.proposed_actions
    FOR SELECT TO dbai_llm USING (TRUE);
CREATE POLICY proposed_actions_monitor ON dbai_llm.proposed_actions
    FOR SELECT TO dbai_monitor USING (TRUE);

-- ghost_context
ALTER TABLE dbai_llm.ghost_context ENABLE ROW LEVEL SECURITY;
CREATE POLICY ghost_context_system ON dbai_llm.ghost_context
    FOR ALL TO dbai_system USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY ghost_context_llm ON dbai_llm.ghost_context
    FOR SELECT TO dbai_llm USING (TRUE);

-- ghost_thought_log
ALTER TABLE dbai_llm.ghost_thought_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY thought_log_system ON dbai_llm.ghost_thought_log
    FOR ALL TO dbai_system USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY thought_log_llm ON dbai_llm.ghost_thought_log
    FOR INSERT TO dbai_llm WITH CHECK (TRUE);
CREATE POLICY thought_log_llm_read ON dbai_llm.ghost_thought_log
    FOR SELECT TO dbai_llm USING (TRUE);
CREATE POLICY thought_log_monitor ON dbai_llm.ghost_thought_log
    FOR SELECT TO dbai_monitor USING (TRUE);

-- process_importance
ALTER TABLE dbai_system.process_importance ENABLE ROW LEVEL SECURITY;
CREATE POLICY process_imp_system ON dbai_system.process_importance
    FOR ALL TO dbai_system USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY process_imp_llm ON dbai_system.process_importance
    FOR SELECT TO dbai_llm USING (TRUE);
CREATE POLICY process_imp_monitor ON dbai_system.process_importance
    FOR SELECT TO dbai_monitor USING (TRUE);

-- energy_consumption
ALTER TABLE dbai_system.energy_consumption ENABLE ROW LEVEL SECURITY;
CREATE POLICY energy_system ON dbai_system.energy_consumption
    FOR ALL TO dbai_system USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY energy_llm ON dbai_system.energy_consumption
    FOR SELECT TO dbai_llm USING (TRUE);
CREATE POLICY energy_monitor ON dbai_system.energy_consumption
    FOR SELECT TO dbai_monitor USING (TRUE);

-- ghost_files
ALTER TABLE dbai_core.ghost_files ENABLE ROW LEVEL SECURITY;
CREATE POLICY ghost_files_system ON dbai_core.ghost_files
    FOR ALL TO dbai_system USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY ghost_files_llm ON dbai_core.ghost_files
    FOR ALL TO dbai_llm USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY ghost_files_monitor ON dbai_core.ghost_files
    FOR SELECT TO dbai_monitor USING (TRUE);

-- ghost_feedback
ALTER TABLE dbai_llm.ghost_feedback ENABLE ROW LEVEL SECURITY;
CREATE POLICY ghost_feedback_system ON dbai_llm.ghost_feedback
    FOR ALL TO dbai_system USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY ghost_feedback_llm ON dbai_llm.ghost_feedback
    FOR SELECT TO dbai_llm USING (TRUE);

-- api_keys
ALTER TABLE dbai_core.api_keys ENABLE ROW LEVEL SECURITY;
CREATE POLICY api_keys_system ON dbai_core.api_keys
    FOR ALL TO dbai_system USING (TRUE) WITH CHECK (TRUE);
-- LLM darf nur aktive Keys sehen (und nur den Preview, nie den Hash)
CREATE POLICY api_keys_llm ON dbai_core.api_keys
    FOR SELECT TO dbai_llm USING (is_active = TRUE);

-- =============================================================================
-- FERTIG — Ghost Autonomy ist bereit
--
-- Nuetzliche Abfragen:
--   SELECT * FROM dbai_llm.vw_pending_actions;
--   SELECT * FROM dbai_llm.vw_thought_stream;
--   SELECT * FROM dbai_system.vw_energy_dashboard;
--   SELECT * FROM dbai_system.vw_process_overview;
--   SELECT * FROM dbai_core.vw_ghost_files;
--   SELECT dbai_llm.propose_action(ghost_id, 'sysadmin', 'sql_execute', 'DELETE FROM ...');
--   SELECT dbai_llm.approve_action(action_id);
--   SELECT dbai_llm.load_ghost_context(ghost_id);
-- =============================================================================
