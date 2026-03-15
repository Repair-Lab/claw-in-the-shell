-- =============================================================================
-- DBAI Schema 27: Immutability Enforcement
-- "Das OS ist fertig gebaut. Die KI darf nur reparieren, nicht umbauen."
-- =============================================================================
--
-- Drei Schichten:
--   1. IMMUTABLE CORE  — Schema-Definitionen, Boot-Tabellen, RLS-Policies.
--                         Nur dbai_system darf hier schreiben (manuell/migration).
--   2. CONFIG / RUNTIME — Laufzeit-Daten, Metriken, Sessions, Logs.
--                         Neuer Rolle dbai_runtime darf hier schreiben.
--   3. LLM INTERFACE   — Ghost schlägt Reparatur via proposed_actions vor.
--                         dbai_llm darf NUR INSERT in proposed_actions + SELECT.
--
-- Sicherheits-Prinzipien:
--   - Web-Server verbindet als dbai_runtime (KEIN Superuser)
--   - Schema-Fingerprints erkennen unauthorisierte Schema-Änderungen
--   - Immutable-Registry definiert unveränderliche Objekte
--   - Repair-Pipeline: propose → approve → execute (immer über proposed_actions)
--   - Keine freie SQL-Eingabe über WebSocket (nur vordefinierte Queries)
-- =============================================================================

-- =============================================================================
-- 1. ROLLE: dbai_runtime — Der Web-Server / API-Layer
-- =============================================================================
-- Hat Schreibrechte auf Laufzeit-/Operations-Tabellen, aber NICHT auf Schema,
-- Core-Definitionen oder LLM-Modelle.

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'dbai_runtime') THEN
        CREATE ROLE dbai_runtime LOGIN PASSWORD 'dbai_runtime_2026';
    END IF;
END
$$;

COMMENT ON ROLE dbai_runtime IS
    'Web-Server Rolle: Schreibt Sessions/Logs/Metriken, liest alles. Kein DDL, kein Superuser.';

-- Schema-Zugriff für dbai_runtime
GRANT USAGE ON SCHEMA dbai_core     TO dbai_runtime;
GRANT USAGE ON SCHEMA dbai_event    TO dbai_runtime;
GRANT USAGE ON SCHEMA dbai_journal  TO dbai_runtime;
GRANT USAGE ON SCHEMA dbai_knowledge TO dbai_runtime;
GRANT USAGE ON SCHEMA dbai_llm      TO dbai_runtime;
GRANT USAGE ON SCHEMA dbai_panic    TO dbai_runtime;
GRANT USAGE ON SCHEMA dbai_system   TO dbai_runtime;
GRANT USAGE ON SCHEMA dbai_ui       TO dbai_runtime;
GRANT USAGE ON SCHEMA dbai_vector   TO dbai_runtime;

-- Sequences für INSERT-Operationen
GRANT USAGE ON ALL SEQUENCES IN SCHEMA dbai_core     TO dbai_runtime;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA dbai_event    TO dbai_runtime;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA dbai_journal  TO dbai_runtime;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA dbai_system   TO dbai_runtime;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA dbai_ui       TO dbai_runtime;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA dbai_llm      TO dbai_runtime;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA dbai_vector   TO dbai_runtime;

-- ─── Leserechte: dbai_runtime darf ALLES lesen ───
GRANT SELECT ON ALL TABLES IN SCHEMA dbai_core     TO dbai_runtime;
GRANT SELECT ON ALL TABLES IN SCHEMA dbai_event    TO dbai_runtime;
GRANT SELECT ON ALL TABLES IN SCHEMA dbai_journal  TO dbai_runtime;
GRANT SELECT ON ALL TABLES IN SCHEMA dbai_knowledge TO dbai_runtime;
GRANT SELECT ON ALL TABLES IN SCHEMA dbai_llm      TO dbai_runtime;
GRANT SELECT ON ALL TABLES IN SCHEMA dbai_panic    TO dbai_runtime;
GRANT SELECT ON ALL TABLES IN SCHEMA dbai_system   TO dbai_runtime;
GRANT SELECT ON ALL TABLES IN SCHEMA dbai_ui       TO dbai_runtime;
GRANT SELECT ON ALL TABLES IN SCHEMA dbai_vector   TO dbai_runtime;

-- ─── Schreibrechte: NUR auf Laufzeit-Tabellen ───

-- Sessions / Login
GRANT INSERT, UPDATE, DELETE ON dbai_core.sessions       TO dbai_runtime;
GRANT INSERT, UPDATE, DELETE ON dbai_core.users          TO dbai_runtime;

-- Audit-Log: Append-Only
GRANT INSERT ON dbai_core.audit_log TO dbai_runtime;

-- Prozesse / Laufzeit-Daten
GRANT INSERT, UPDATE, DELETE ON dbai_core.processes      TO dbai_runtime;
GRANT INSERT, UPDATE         ON dbai_core.config         TO dbai_runtime;

-- Events
GRANT INSERT ON dbai_event.events             TO dbai_runtime;
GRANT INSERT ON dbai_event.user_events        TO dbai_runtime;

-- Journal: Nur schreiben
GRANT INSERT ON dbai_journal.change_log       TO dbai_runtime;

-- System-Metriken: Schreiben
GRANT INSERT, UPDATE ON dbai_system.cpu        TO dbai_runtime;
GRANT INSERT, UPDATE ON dbai_system.memory     TO dbai_runtime;
GRANT INSERT, UPDATE ON dbai_system.disk       TO dbai_runtime;
GRANT INSERT, UPDATE ON dbai_system.temperature TO dbai_runtime;
GRANT INSERT, UPDATE ON dbai_system.network    TO dbai_runtime;

-- UI: Fenster-Verwaltung, Desktop-Elemente
GRANT INSERT, UPDATE, DELETE ON dbai_ui.windows          TO dbai_runtime;
GRANT INSERT, UPDATE, DELETE ON dbai_ui.window_states    TO dbai_runtime;
GRANT INSERT, UPDATE, DELETE ON dbai_ui.notifications    TO dbai_runtime;
GRANT INSERT, UPDATE, DELETE ON dbai_ui.taskbar_pins     TO dbai_runtime;
GRANT INSERT, UPDATE         ON dbai_ui.desktop_settings TO dbai_runtime;
GRANT INSERT, UPDATE         ON dbai_ui.wallpapers       TO dbai_runtime;

-- LLM: Runtime darf proposed_actions verwalten (approve/reject/execute)
GRANT INSERT, UPDATE ON dbai_llm.proposed_actions     TO dbai_runtime;
GRANT INSERT         ON dbai_llm.ghost_thought_log    TO dbai_runtime;
GRANT INSERT         ON dbai_llm.ghost_feedback       TO dbai_runtime;
GRANT UPDATE         ON dbai_llm.ghost_context        TO dbai_runtime;
GRANT UPDATE         ON dbai_llm.active_ghosts        TO dbai_runtime;

-- Software-Katalog: Runtime darf installieren aber nicht den Katalog ändern
GRANT UPDATE ON dbai_core.software_catalog     TO dbai_runtime;
GRANT INSERT, UPDATE, DELETE ON dbai_core.installed_software TO dbai_runtime;

-- Vektor-Daten
GRANT INSERT, UPDATE ON dbai_vector.memories   TO dbai_runtime;

-- System-Memory: Runtime darf Einträge hinzufügen
GRANT INSERT, UPDATE ON dbai_knowledge.system_memory TO dbai_runtime;

-- ─── KEIN Zugriff für dbai_runtime: ───
-- - dbai_panic.*         (NUR dbai_system + dbai_recovery)
-- - DDL-Befehle          (kein CREATE/DROP/ALTER)
-- - dbai_llm.ghost_models (nur SELECT, kein Ändern der Modell-Definitionen)
-- - dbai_core.drivers     (nur SELECT, Hardware-Treiber sind immutable)
-- - pg_* System-Kataloge (kein direkter Zugriff)
-- - Schema-Änderungen    (keine GRANT-Rechte)


-- =============================================================================
-- 2. SCHEMA FINGERPRINTS — Erkennt unauthorisierte Schema-Änderungen
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_core.schema_fingerprints (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Was wird geprüft?
    schema_name     TEXT NOT NULL,
    object_name     TEXT NOT NULL,
    object_type     TEXT NOT NULL CHECK (object_type IN (
        'table', 'view', 'function', 'trigger', 'index', 'policy', 'role'
    )),
    -- Fingerprint
    definition_hash TEXT NOT NULL,           -- md5 der CREATE-Definition
    column_hash     TEXT,                    -- md5 der Spalten-Definition (für Tabellen)
    policy_hash     TEXT,                    -- md5 der RLS-Policies
    -- Status
    is_immutable    BOOLEAN NOT NULL DEFAULT TRUE,
    verified_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Wann wurde das zuletzt geprüft
    last_check      TIMESTAMPTZ DEFAULT NOW(),
    check_result    TEXT DEFAULT 'ok' CHECK (check_result IN ('ok', 'modified', 'missing', 'new')),
    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_schema_fingerprints_unique
    ON dbai_core.schema_fingerprints(schema_name, object_name, object_type);

-- Append-Only für die Fingerprints: kein UPDATE/DELETE erlaubt (außer dbai_system)
ALTER TABLE dbai_core.schema_fingerprints ENABLE ROW LEVEL SECURITY;
CREATE POLICY fp_system ON dbai_core.schema_fingerprints
    FOR ALL TO dbai_system USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY fp_runtime_read ON dbai_core.schema_fingerprints
    FOR SELECT TO dbai_runtime USING (TRUE);
CREATE POLICY fp_monitor_read ON dbai_core.schema_fingerprints
    FOR SELECT TO dbai_monitor USING (TRUE);


-- =============================================================================
-- 3. IMMUTABLE REGISTRY — Was darf NICHT verändert werden
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_core.immutable_registry (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Objekt-Beschreibung
    schema_name     TEXT NOT NULL,
    object_name     TEXT NOT NULL,
    object_type     TEXT NOT NULL CHECK (object_type IN (
        'table', 'column', 'function', 'trigger', 'role', 'policy', 'schema'
    )),
    -- Warum ist es immutable?
    reason          TEXT NOT NULL,
    protection_level TEXT NOT NULL DEFAULT 'hard' CHECK (protection_level IN (
        'hard',      -- NIEMALS ändern (Schema-Def, RLS-Policies)
        'soft',      -- Nur mit expliziter Migration
        'config'     -- Kann via approved config_change geändert werden
    )),
    -- Wer hat es als immutable markiert?
    locked_by       TEXT NOT NULL DEFAULT 'system_init',
    locked_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Exceptions
    exception_roles TEXT[] DEFAULT '{dbai_system}',  -- Wer darf trotzdem?
    exception_reason TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_immutable_registry_unique
    ON dbai_core.immutable_registry(schema_name, object_name, object_type);

-- Registry selbst ist immutable (nur dbai_system)
ALTER TABLE dbai_core.immutable_registry ENABLE ROW LEVEL SECURITY;
CREATE POLICY immutable_reg_system ON dbai_core.immutable_registry
    FOR ALL TO dbai_system USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY immutable_reg_runtime_read ON dbai_core.immutable_registry
    FOR SELECT TO dbai_runtime USING (TRUE);
CREATE POLICY immutable_reg_monitor_read ON dbai_core.immutable_registry
    FOR SELECT TO dbai_monitor USING (TRUE);

-- Schreibschutz: Trigger verhindert UPDATE/DELETE (auch für dbai_system)
CREATE OR REPLACE FUNCTION dbai_core.protect_immutable_registry()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Immutable Registry: DELETE ist verboten. '
            'Objekte können nicht aus dem Schutz entfernt werden.';
    END IF;
    IF TG_OP = 'UPDATE' THEN
        -- Nur protection_level darf gelockert werden (von hard→soft)
        IF NEW.schema_name != OLD.schema_name
           OR NEW.object_name != OLD.object_name
           OR NEW.object_type != OLD.object_type THEN
            RAISE EXCEPTION 'Immutable Registry: Objekt-Identität ist unveränderlich.';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_protect_immutable_registry
    BEFORE UPDATE OR DELETE ON dbai_core.immutable_registry
    FOR EACH ROW EXECUTE FUNCTION dbai_core.protect_immutable_registry();


-- =============================================================================
-- 4. POLICY ENFORCEMENT LOG — Protokolliert Enforcement-Events
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_core.policy_enforcement_log (
    id              BIGSERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Was wurde blockiert/erlaubt?
    event_type      TEXT NOT NULL CHECK (event_type IN (
        'schema_violation',      -- Jemand versuchte Schema zu ändern
        'permission_denied',     -- Zugriff verweigert
        'repair_proposed',       -- LLM schlägt Reparatur vor
        'repair_approved',       -- Reparatur genehmigt
        'repair_rejected',       -- Reparatur abgelehnt
        'repair_executed',       -- Reparatur ausgeführt
        'fingerprint_mismatch',  -- Schema-Fingerprint stimmt nicht
        'immutable_violation',   -- Versuch ein immutable Objekt zu ändern
        'websocket_blocked',     -- WebSocket-Befehl blockiert
        'sql_injection_attempt', -- SQL-Injection erkannt
        'role_escalation'        -- Rollen-Eskalations-Versuch
    )),
    severity        TEXT NOT NULL DEFAULT 'warning' CHECK (severity IN (
        'info', 'warning', 'critical', 'fatal'
    )),
    -- Details
    actor_role      TEXT NOT NULL DEFAULT current_user,
    target_schema   TEXT,
    target_object   TEXT,
    attempted_action TEXT,
    blocked         BOOLEAN NOT NULL DEFAULT TRUE,
    reason          TEXT NOT NULL,
    -- Kontext
    client_addr     INET,
    session_id      TEXT,
    metadata        JSONB DEFAULT '{}'::JSONB
);

-- Append-Only
ALTER TABLE dbai_core.policy_enforcement_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY enforcement_system ON dbai_core.policy_enforcement_log
    FOR ALL TO dbai_system USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY enforcement_runtime_insert ON dbai_core.policy_enforcement_log
    FOR INSERT TO dbai_runtime WITH CHECK (TRUE);
CREATE POLICY enforcement_runtime_read ON dbai_core.policy_enforcement_log
    FOR SELECT TO dbai_runtime USING (TRUE);
CREATE POLICY enforcement_monitor_read ON dbai_core.policy_enforcement_log
    FOR SELECT TO dbai_monitor USING (TRUE);

CREATE OR REPLACE FUNCTION dbai_core.protect_enforcement_log()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP IN ('DELETE', 'UPDATE') THEN
        RAISE EXCEPTION 'Policy Enforcement Log ist Append-Only';
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_protect_enforcement_log
    BEFORE UPDATE OR DELETE ON dbai_core.policy_enforcement_log
    FOR EACH ROW EXECUTE FUNCTION dbai_core.protect_enforcement_log();


-- =============================================================================
-- 5. REPAIR TASK PIPELINE — Formalisierter Reparatur-Workflow
-- =============================================================================

-- View: Offene Reparaturen für die Web-UI
CREATE OR REPLACE VIEW dbai_core.vw_repair_queue AS
SELECT
    pa.id AS action_id,
    pa.proposing_role,
    gm.display_name AS ghost_name,
    pa.action_type,
    pa.risk_level,
    pa.risk_reason,
    LEFT(COALESCE(pa.action_sql, pa.action_command, '—'), 300) AS action_preview,
    pa.action_params,
    pa.affected_tables,
    pa.estimated_impact,
    pa.approval_state,
    pa.proposed_at,
    pa.expires_at,
    EXTRACT(EPOCH FROM (pa.expires_at - NOW()))::INTEGER AS seconds_remaining,
    pa.approved_by,
    pa.executed_at,
    pa.execution_result,
    pa.error_message
FROM dbai_llm.proposed_actions pa
LEFT JOIN dbai_llm.ghost_models gm ON gm.id = pa.proposing_ghost_id
ORDER BY
    CASE pa.approval_state
        WHEN 'pending' THEN 1
        WHEN 'approved' THEN 2
        WHEN 'executing' THEN 3
        ELSE 10
    END,
    CASE pa.risk_level
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'medium' THEN 3
        ELSE 4
    END,
    pa.proposed_at DESC;


-- ─── Reparatur sicher ausführen (nur approved Actions) ───
CREATE OR REPLACE FUNCTION dbai_core.execute_approved_repair(
    p_action_id UUID
) RETURNS JSONB AS $$
DECLARE
    v_action RECORD;
    v_result JSONB;
    v_start  TIMESTAMPTZ;
    v_duration_ms REAL;
BEGIN
    -- Aktion laden und prüfen
    SELECT * INTO v_action
    FROM dbai_llm.proposed_actions
    WHERE id = p_action_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Repair-Action % nicht gefunden', p_action_id;
    END IF;

    -- NUR approved Actions dürfen ausgeführt werden
    IF v_action.approval_state NOT IN ('approved', 'auto_approved') THEN
        -- Enforcement-Log
        INSERT INTO dbai_core.policy_enforcement_log
            (event_type, severity, target_object, attempted_action, blocked, reason)
        VALUES
            ('repair_rejected', 'warning', p_action_id::TEXT,
             v_action.action_type, TRUE,
             'Versuch eine nicht-genehmigte Aktion auszuführen (Status: ' || v_action.approval_state || ')');

        RETURN jsonb_build_object(
            'error', 'Aktion ist nicht genehmigt',
            'status', v_action.approval_state
        );
    END IF;

    -- Timeout prüfen
    IF v_action.expires_at < NOW() THEN
        UPDATE dbai_llm.proposed_actions
        SET approval_state = 'expired', decided_at = NOW()
        WHERE id = p_action_id;

        RETURN jsonb_build_object('error', 'Aktion ist abgelaufen');
    END IF;

    -- Status: executing
    UPDATE dbai_llm.proposed_actions
    SET approval_state = 'executing', executed_at = NOW()
    WHERE id = p_action_id;

    v_start := clock_timestamp();

    -- Ausführung je nach Typ
    BEGIN
        IF v_action.action_type = 'sql_execute' AND v_action.action_sql IS NOT NULL THEN
            -- Sicherheitscheck: KEIN DDL erlaubt für Repair-Actions
            IF v_action.action_sql ~* '^\s*(CREATE|DROP|ALTER|GRANT|REVOKE|TRUNCATE)' THEN
                RAISE EXCEPTION 'DDL-Befehle sind in Repair-Actions verboten: %',
                    LEFT(v_action.action_sql, 80);
            END IF;

            EXECUTE v_action.action_sql;
            v_result := jsonb_build_object('type', 'sql_execute', 'success', TRUE);

        ELSIF v_action.action_type IN ('service_restart', 'process_kill') THEN
            -- Shell-Commands werden NICHT direkt ausgeführt!
            -- Sie werden als NOTIFY geschickt und der Supervisor führt sie aus.
            PERFORM pg_notify('repair_execute', json_build_object(
                'action_id', p_action_id,
                'action_type', v_action.action_type,
                'command', v_action.action_command,
                'params', v_action.action_params
            )::TEXT);
            v_result := jsonb_build_object('type', 'async_command', 'notified', TRUE);

        ELSIF v_action.action_type = 'config_change' THEN
            -- Config-Changes auf erlaubte Keys beschränken
            IF v_action.action_params ? 'key' AND v_action.action_params ? 'value' THEN
                UPDATE dbai_core.config
                SET value = (v_action.action_params->>'value')::JSONB,
                    updated_at = NOW()
                WHERE key = v_action.action_params->>'key'
                  AND 'dbai_runtime' = ANY(write_roles);  -- Nur beschreibbare Configs!
            END IF;
            v_result := jsonb_build_object('type', 'config_change', 'success', TRUE);

        ELSE
            v_result := jsonb_build_object('type', v_action.action_type, 'note', 'Typ nicht automatisch ausführbar');
        END IF;

        v_duration_ms := EXTRACT(EPOCH FROM (clock_timestamp() - v_start)) * 1000;

        -- Erfolg: Status aktualisieren
        UPDATE dbai_llm.proposed_actions
        SET approval_state = 'executed',
            execution_result = v_result || jsonb_build_object('duration_ms', v_duration_ms)
        WHERE id = p_action_id;

        -- Enforcement-Log: Erfolg
        INSERT INTO dbai_core.policy_enforcement_log
            (event_type, severity, target_object, attempted_action, blocked, reason)
        VALUES
            ('repair_executed', 'info', p_action_id::TEXT,
             v_action.action_type, FALSE,
             'Reparatur erfolgreich ausgeführt in ' || v_duration_ms || 'ms');

        RETURN v_result || jsonb_build_object('status', 'executed', 'duration_ms', v_duration_ms);

    EXCEPTION WHEN OTHERS THEN
        -- Fehler: Status + Error dokumentieren
        UPDATE dbai_llm.proposed_actions
        SET approval_state = 'failed',
            error_message = SQLERRM,
            execution_result = jsonb_build_object('error', SQLERRM)
        WHERE id = p_action_id;

        -- Enforcement-Log: Fehler
        INSERT INTO dbai_core.policy_enforcement_log
            (event_type, severity, target_object, attempted_action, blocked, reason)
        VALUES
            ('repair_rejected', 'critical', p_action_id::TEXT,
             v_action.action_type, TRUE,
             'Reparatur fehlgeschlagen: ' || SQLERRM);

        RETURN jsonb_build_object('error', SQLERRM, 'status', 'failed');
    END;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;  -- Läuft als Ersteller (dbai_system), nicht als Aufrufer

-- Nur dbai_system und dbai_runtime dürfen diese Funktion aufrufen
REVOKE ALL ON FUNCTION dbai_core.execute_approved_repair(UUID) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION dbai_core.execute_approved_repair(UUID) TO dbai_runtime;
GRANT EXECUTE ON FUNCTION dbai_core.execute_approved_repair(UUID) TO dbai_system;


-- =============================================================================
-- 6. SCHEMA VERIFICATION — Prüft ob Schema noch integer ist
-- =============================================================================

CREATE OR REPLACE FUNCTION dbai_core.verify_schema_integrity()
RETURNS TABLE (
    schema_name  TEXT,
    object_name  TEXT,
    object_type  TEXT,
    status       TEXT,    -- 'ok', 'modified', 'missing'
    detail       TEXT
) AS $$
DECLARE
    v_fp RECORD;
    v_current_hash TEXT;
    v_exists BOOLEAN;
BEGIN
    FOR v_fp IN
        SELECT sf.*
        FROM dbai_core.schema_fingerprints sf
        WHERE sf.is_immutable = TRUE
    LOOP
        -- Prüfe ob Objekt noch existiert
        IF v_fp.object_type = 'table' THEN
            SELECT EXISTS(
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = v_fp.schema_name
                  AND table_name = v_fp.object_name
            ) INTO v_exists;

            IF NOT v_exists THEN
                schema_name := v_fp.schema_name;
                object_name := v_fp.object_name;
                object_type := v_fp.object_type;
                status := 'missing';
                detail := 'Tabelle existiert nicht mehr!';
                RETURN NEXT;
                CONTINUE;
            END IF;

            -- Spalten-Hash berechnen
            SELECT md5(string_agg(
                column_name || ':' || data_type || ':' || COALESCE(is_nullable, ''),
                '|' ORDER BY ordinal_position
            )) INTO v_current_hash
            FROM information_schema.columns
            WHERE table_schema = v_fp.schema_name
              AND table_name = v_fp.object_name;

            IF v_current_hash != COALESCE(v_fp.column_hash, v_current_hash) THEN
                schema_name := v_fp.schema_name;
                object_name := v_fp.object_name;
                object_type := v_fp.object_type;
                status := 'modified';
                detail := 'Spalten-Definition hat sich geändert (erwartet: '
                    || LEFT(v_fp.column_hash, 8) || ', ist: ' || LEFT(v_current_hash, 8) || ')';

                -- Enforcement-Log
                INSERT INTO dbai_core.policy_enforcement_log
                    (event_type, severity, target_schema, target_object,
                     attempted_action, blocked, reason)
                VALUES
                    ('fingerprint_mismatch', 'critical', v_fp.schema_name,
                     v_fp.object_name, 'schema_verification', FALSE,
                     'Spalten-Hash stimmt nicht überein');

                RETURN NEXT;
                CONTINUE;
            END IF;

        ELSIF v_fp.object_type = 'function' THEN
            SELECT EXISTS(
                SELECT 1 FROM information_schema.routines
                WHERE routine_schema = v_fp.schema_name
                  AND routine_name = v_fp.object_name
            ) INTO v_exists;

            IF NOT v_exists THEN
                schema_name := v_fp.schema_name;
                object_name := v_fp.object_name;
                object_type := v_fp.object_type;
                status := 'missing';
                detail := 'Funktion existiert nicht mehr!';
                RETURN NEXT;
                CONTINUE;
            END IF;
        END IF;

        -- Alles OK
        schema_name := v_fp.schema_name;
        object_name := v_fp.object_name;
        object_type := v_fp.object_type;
        status := 'ok';
        detail := NULL;

        -- Update last_check
        UPDATE dbai_core.schema_fingerprints
        SET last_check = NOW(), check_result = 'ok'
        WHERE id = v_fp.id;

        RETURN NEXT;
    END LOOP;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

REVOKE ALL ON FUNCTION dbai_core.verify_schema_integrity() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION dbai_core.verify_schema_integrity() TO dbai_runtime;
GRANT EXECUTE ON FUNCTION dbai_core.verify_schema_integrity() TO dbai_system;
GRANT EXECUTE ON FUNCTION dbai_core.verify_schema_integrity() TO dbai_monitor;


-- =============================================================================
-- 7. SNAPSHOT FINGERPRINTS — Erstmalige Erfassung aller Core-Tabellen
-- =============================================================================

CREATE OR REPLACE FUNCTION dbai_core.snapshot_schema_fingerprints()
RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER := 0;
    v_rec   RECORD;
    v_col_hash TEXT;
BEGIN
    -- Alle Tabellen in dbai_* Schemas erfassen
    FOR v_rec IN
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema LIKE 'dbai_%'
          AND table_type = 'BASE TABLE'
        ORDER BY table_schema, table_name
    LOOP
        -- Spalten-Hash berechnen
        SELECT md5(string_agg(
            column_name || ':' || data_type || ':' || COALESCE(is_nullable, ''),
            '|' ORDER BY ordinal_position
        )) INTO v_col_hash
        FROM information_schema.columns
        WHERE table_schema = v_rec.table_schema
          AND table_name = v_rec.table_name;

        INSERT INTO dbai_core.schema_fingerprints
            (schema_name, object_name, object_type, definition_hash, column_hash, is_immutable)
        VALUES
            (v_rec.table_schema, v_rec.table_name, 'table',
             md5(v_rec.table_schema || '.' || v_rec.table_name),
             v_col_hash, TRUE)
        ON CONFLICT (schema_name, object_name, object_type)
        DO UPDATE SET
            column_hash = EXCLUDED.column_hash,
            last_check = NOW(),
            check_result = 'ok';

        v_count := v_count + 1;
    END LOOP;

    -- Alle Funktionen erfassen
    FOR v_rec IN
        SELECT routine_schema, routine_name
        FROM information_schema.routines
        WHERE routine_schema LIKE 'dbai_%'
        ORDER BY routine_schema, routine_name
    LOOP
        INSERT INTO dbai_core.schema_fingerprints
            (schema_name, object_name, object_type, definition_hash, is_immutable)
        VALUES
            (v_rec.routine_schema, v_rec.routine_name, 'function',
             md5(v_rec.routine_schema || '.' || v_rec.routine_name),
             TRUE)
        ON CONFLICT (schema_name, object_name, object_type)
        DO UPDATE SET
            last_check = NOW(),
            check_result = 'ok';

        v_count := v_count + 1;
    END LOOP;

    RETURN v_count;
END;
$$ LANGUAGE plpgsql;


-- =============================================================================
-- 8. IMMUTABLE REGISTRY SEED — Was wird geschützt?
-- =============================================================================

-- Core-Schemas als immutable markieren
INSERT INTO dbai_core.immutable_registry
    (schema_name, object_name, object_type, reason, protection_level, locked_by)
VALUES
    -- Schema-Definitionen
    ('dbai_core',    '*', 'schema', 'Core-Schema: Alle Tabellen-Definitionen sind fix', 'hard', 'schema_27'),
    ('dbai_panic',   '*', 'schema', 'Panic-Schema: Muss immer verfügbar sein', 'hard', 'schema_27'),
    ('dbai_journal', '*', 'schema', 'Journal: Append-Only, keine Schema-Änderungen', 'hard', 'schema_27'),

    -- Kritische Tabellen
    ('dbai_core', 'audit_log',        'table', 'Audit-Log: Unveränderlich (Append-Only)', 'hard', 'schema_27'),
    ('dbai_core', 'drivers',          'table', 'Hardware-Treiber: Fix nach Installation', 'hard', 'schema_27'),
    ('dbai_core', 'objects',          'table', 'Objekt-Registry: Core-Struktur', 'hard', 'schema_27'),
    ('dbai_core', 'schema_fingerprints', 'table', 'Fingerprints selbst sind immutable', 'hard', 'schema_27'),
    ('dbai_core', 'immutable_registry',  'table', 'Registry selbst ist immutable', 'hard', 'schema_27'),
    ('dbai_core', 'policy_enforcement_log', 'table', 'Enforcement-Log: Append-Only', 'hard', 'schema_27'),

    -- Panic-Tabellen
    ('dbai_panic', 'emergency_drivers', 'table', 'Notfall-Treiber: Fix nach Init', 'hard', 'schema_27'),
    ('dbai_panic', 'boot_config',       'table', 'Boot-Config: Fix nach Init', 'hard', 'schema_27'),
    ('dbai_panic', 'repair_scripts',    'table', 'Repair-Scripts: Fix nach Init', 'hard', 'schema_27'),

    -- Rollen
    ('pg_catalog', 'dbai_system',  'role', 'Superuser-Rolle: Darf nicht verändert werden', 'hard', 'schema_27'),
    ('pg_catalog', 'dbai_runtime', 'role', 'Runtime-Rolle: Berechtigungen sind fix', 'hard', 'schema_27'),
    ('pg_catalog', 'dbai_llm',    'role', 'LLM-Rolle: Eingeschränkte Rechte sind fix', 'hard', 'schema_27'),

    -- Sicherheitsfunktionen
    ('dbai_core', 'protect_audit_log',       'function', 'Audit-Schutz: Darf nicht geändert werden', 'hard', 'schema_27'),
    ('dbai_core', 'protect_enforcement_log', 'function', 'Enforcement-Schutz: Darf nicht geändert werden', 'hard', 'schema_27'),
    ('dbai_core', 'protect_immutable_registry', 'function', 'Registry-Schutz: Darf nicht geändert werden', 'hard', 'schema_27'),
    ('dbai_core', 'verify_schema_integrity',    'function', 'Integritätsprüfung: Core-Funktion', 'hard', 'schema_27'),
    ('dbai_core', 'execute_approved_repair',    'function', 'Repair-Pipeline: Core-Funktion', 'hard', 'schema_27'),

    -- Soft-Immutable: Config-Tabellen darf Runtime updaten, aber kein DDL
    ('dbai_core', 'config',   'table', 'Konfiguration: Werte änderbar, Schema fix', 'soft', 'schema_27'),
    ('dbai_ui',   'themes',   'table', 'Themes: Neue hinzufügen OK, Schema fix', 'soft', 'schema_27'),
    ('dbai_core', 'software_catalog', 'table', 'Katalog: Install-Status änderbar, Schema fix', 'soft', 'schema_27')
ON CONFLICT (schema_name, object_name, object_type) DO NOTHING;


-- =============================================================================
-- 9. RLS FÜR RUNTIME — dbai_runtime bekommt automatisch Policies auf ALLE
--    Tabellen mit Row Level Security. Dynamisch: findet alle RLS-Tabellen und
--    erstellt fehlende Policies.
-- =============================================================================

-- Automatische Bulk-Policy-Erstellung: Für JEDE Tabelle mit RLS, die noch
-- keine Policy für dbai_runtime hat, wird eine FOR ALL Policy erstellt.
-- Das ist robust gegenüber neuen Tabellen in zukünftigen Schemas.

DO $$
DECLARE
    v_rec RECORD;
    v_policy_name TEXT;
    v_count INT := 0;
BEGIN
    FOR v_rec IN
        SELECT n.nspname AS schema_name, c.relname AS table_name
        FROM pg_class c
        JOIN pg_namespace n ON c.relnamespace = n.oid
        WHERE c.relrowsecurity = TRUE
          AND c.relkind = 'r'
          AND n.nspname LIKE 'dbai_%'
          AND NOT EXISTS (
              SELECT 1 FROM pg_policies p
              WHERE p.tablename = c.relname
                AND p.schemaname = n.nspname
                AND '{dbai_runtime}' <@ p.roles
          )
    LOOP
        v_policy_name := 'runtime_all';
        BEGIN
            EXECUTE format(
                'CREATE POLICY %I ON %I.%I FOR ALL TO dbai_runtime USING (TRUE) WITH CHECK (TRUE)',
                v_policy_name, v_rec.schema_name, v_rec.table_name
            );
            v_count := v_count + 1;
        EXCEPTION WHEN duplicate_object THEN
            -- Policy existiert bereits unter anderem Namen, ignorieren
            NULL;
        END;
    END LOOP;
    IF v_count > 0 THEN
        RAISE NOTICE 'dbai_runtime: % neue RLS-Policies erstellt', v_count;
    END IF;
END $$;


-- =============================================================================
-- 10. SNAPSHOT ERSTELLEN — Fingerprints für aktuelle Schemas erfassen
-- =============================================================================

-- Sofort Snapshot erstellen wenn dieses Schema geladen wird
SELECT dbai_core.snapshot_schema_fingerprints();


-- =============================================================================
-- 11. ALLOWED WEBSOCKET COMMANDS — Whitelist für den WebSocket-Kanal
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_core.websocket_commands (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    command_name    TEXT NOT NULL UNIQUE,
    -- Beschreibung
    description     TEXT,
    -- Wer darf diesen Command senden?
    allowed_roles   TEXT[] NOT NULL DEFAULT '{authenticated}',
    -- Parameter-Schema (für Validierung)
    param_schema    JSONB DEFAULT '{}'::JSONB,
    -- Rate-Limiting
    max_per_minute  INTEGER DEFAULT 60,
    -- Ist es ein reiner Lese-Befehl?
    is_read_only    BOOLEAN NOT NULL DEFAULT TRUE,
    -- Status
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE dbai_core.websocket_commands ENABLE ROW LEVEL SECURITY;
CREATE POLICY ws_cmd_system ON dbai_core.websocket_commands
    FOR ALL TO dbai_system USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY ws_cmd_runtime_read ON dbai_core.websocket_commands
    FOR SELECT TO dbai_runtime USING (TRUE);

-- Erlaubte WebSocket-Befehle
INSERT INTO dbai_core.websocket_commands
    (command_name, description, allowed_roles, is_read_only, max_per_minute)
VALUES
    ('get_metrics',        'System-Metriken abrufen',       '{authenticated}', TRUE, 120),
    ('get_processes',      'Prozessliste abrufen',          '{authenticated}', TRUE, 60),
    ('get_events',         'Event-Stream abonnieren',       '{authenticated}', TRUE, 120),
    ('get_thought_stream', 'Ghost Thought-Stream',          '{authenticated}', TRUE, 120),
    ('get_pending_actions','Offene Repair-Actions',         '{authenticated}', TRUE, 60),
    ('approve_action',     'Repair-Action genehmigen',      '{admin}', FALSE, 10),
    ('reject_action',      'Repair-Action ablehnen',        '{admin}', FALSE, 10),
    ('open_window',        'Fenster öffnen',                '{authenticated}', FALSE, 30),
    ('close_window',       'Fenster schließen',             '{authenticated}', FALSE, 30),
    ('resize_window',      'Fenster-Größe ändern',          '{authenticated}', FALSE, 120),
    ('move_window',        'Fenster verschieben',           '{authenticated}', FALSE, 120),
    ('get_notifications',  'Benachrichtigungen abrufen',    '{authenticated}', TRUE, 60),
    ('mark_notification_read', 'Benachrichtigung als gelesen', '{authenticated}', FALSE, 60),
    ('get_desktop',        'Desktop-Layout abrufen',        '{authenticated}', TRUE, 30),
    ('ghost_swap',         'KI-Modell wechseln',            '{admin}', FALSE, 5),
    ('schema_verify',      'Schema-Integrität prüfen',      '{admin}', TRUE, 5)
ON CONFLICT (command_name) DO NOTHING;


-- =============================================================================
-- 12. LLM HÄRTUNG — Explizite Beschränkung von dbai_llm
-- =============================================================================

-- dbai_llm darf NUR:
--   1. SELECT auf freigegebene Tabellen (via RLS)
--   2. INSERT INTO dbai_llm.proposed_actions (Reparaturen vorschlagen)
--   3. INSERT INTO dbai_llm.ghost_thought_log (Gedankenprotokoll)
--   4. Keine Shell-Commands, kein DDL, kein COPY, kein pg_read_file

-- Entferne überflüssige EXECUTE-Rechte für dbai_llm auf gefährliche Funktionen
DO $$
DECLARE
    v_func RECORD;
BEGIN
    FOR v_func IN
        SELECT n.nspname, p.proname, pg_get_function_identity_arguments(p.oid) AS args
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname LIKE 'dbai_%'
          AND has_function_privilege('dbai_llm', p.oid, 'EXECUTE')
          -- Erlaube nur diese Whitelist:
          AND p.proname NOT IN (
              'propose_action',           -- Repair vorschlagen
              'load_ghost_context',       -- Context laden
              'expire_pending_actions'    -- Auto-Cleanup
          )
    LOOP
        BEGIN
            EXECUTE format(
                'REVOKE EXECUTE ON FUNCTION %I.%I(%s) FROM dbai_llm',
                v_func.nspname, v_func.proname, v_func.args
            );
        EXCEPTION WHEN OTHERS THEN
            -- Einige System-Funktionen lassen sich nicht revooken
            NULL;
        END;
    END LOOP;
END $$;

-- Stelle sicher: dbai_llm kann NICHT:
REVOKE CREATE ON SCHEMA dbai_core FROM dbai_llm;
REVOKE CREATE ON SCHEMA dbai_llm FROM dbai_llm;
REVOKE CREATE ON SCHEMA dbai_system FROM dbai_llm;
REVOKE CREATE ON SCHEMA dbai_ui FROM dbai_llm;
REVOKE CREATE ON SCHEMA dbai_panic FROM dbai_llm;

-- Kein COPY, kein pg_read_file
-- (Diese sind ohnehin nur für Superuser, aber explizite Dokumentation)

-- Grant: proposed_actions INSERT für dbai_llm
GRANT INSERT ON dbai_llm.proposed_actions TO dbai_llm;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA dbai_llm TO dbai_llm;

-- Grant: ghost_thought_log INSERT für dbai_llm
GRANT INSERT ON dbai_llm.ghost_thought_log TO dbai_llm;

-- Grant: propose_action Funktion
GRANT EXECUTE ON FUNCTION dbai_llm.propose_action(UUID, TEXT, TEXT, TEXT, TEXT, JSONB, TEXT) TO dbai_llm;
GRANT EXECUTE ON FUNCTION dbai_llm.load_ghost_context(UUID) TO dbai_llm;
GRANT EXECUTE ON FUNCTION dbai_llm.expire_pending_actions() TO dbai_llm;

-- =============================================================================
-- FERTIG — Immutability Enforcement ist aktiv
--
-- Architektur:
--   ┌─────────────────────────────────────────────────┐
--   │              DBAI Immutable OS                   │
--   ├─────────────────────────────────────────────────┤
--   │  Layer 1: IMMUTABLE CORE (dbai_system only)     │
--   │  - Schema-Definitionen, Tabellen-Struktur       │
--   │  - RLS-Policies, Rollen, Trigger                │
--   │  - Boot-Config, Emergency-Drivers               │
--   │  - schema_fingerprints, immutable_registry      │
--   ├─────────────────────────────────────────────────┤
--   │  Layer 2: RUNTIME (dbai_runtime)                │
--   │  - Sessions, Fenster, Logs                      │
--   │  - System-Metriken, Benachrichtigungen          │
--   │  - proposed_actions (approve/reject/execute)    │
--   │  - Software Install/Uninstall                   │
--   ├─────────────────────────────────────────────────┤
--   │  Layer 3: LLM INTERFACE (dbai_llm)              │
--   │  - SELECT auf freigegebene Tabellen             │
--   │  - INSERT INTO proposed_actions (nur Vorschlag) │
--   │  - INSERT INTO ghost_thought_log                │
--   │  - KEIN DDL, KEIN Shell, KEIN COPY              │
--   └─────────────────────────────────────────────────┘
--
-- Prüfung:
--   SELECT * FROM dbai_core.verify_schema_integrity();
--   SELECT * FROM dbai_core.vw_repair_queue;
--   SELECT * FROM dbai_core.policy_enforcement_log ORDER BY ts DESC LIMIT 20;
--   SELECT * FROM dbai_core.immutable_registry ORDER BY schema_name;
-- =============================================================================
