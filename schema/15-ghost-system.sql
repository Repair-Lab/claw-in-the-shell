-- =============================================================================
-- DBAI Schema 15: Ghost System — "Ghost in the Shell"
-- Hot-Swap KI-Modelle, rollenbasierte KI-Zuweisung, Modell-Lifecycle
-- =============================================================================
-- Der "Ghost" (KI/Bewusstsein) ist vom "Shell" (Hardware/System) getrennt.
-- Jeder Ghost kann auf Knopfdruck gewechselt werden. Das System erkennt
-- automatisch per Trigger, wenn ein neuer Ghost aktiviert wird, und sendet
-- NOTIFY an den Python-Dispatcher.
-- =============================================================================

-- Schema: Wir erweitern dbai_llm um Ghost-Konzepte
-- und nutzen dbai_core für die Objekt-Registrierung

-- =============================================================================
-- 1. GHOST MODELS — Alle verfügbaren KI-Modelle im System
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_llm.ghost_models (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL UNIQUE,
    display_name    TEXT NOT NULL,
    model_path      TEXT,                    -- Relativer Pfad zur GGUF-Datei
    model_object_id UUID REFERENCES dbai_core.objects(id),
    model_type      TEXT NOT NULL DEFAULT 'chat'
                    CHECK (model_type IN (
                        'chat', 'code', 'vision', 'embedding',
                        'reasoning', 'tool_use', 'multimodal'
                    )),
    provider        TEXT NOT NULL DEFAULT 'llama.cpp'
                    CHECK (provider IN (
                        'llama.cpp', 'vllm', 'ollama', 'custom'
                    )),
    parameters      JSONB NOT NULL DEFAULT '{}'::JSONB,
    -- Modell-Metadaten
    parameter_count TEXT,                    -- z.B. '7B', '13B', '70B'
    quantization    TEXT,                    -- z.B. 'Q4_K_M', 'Q8_0', 'F16'
    context_size    INTEGER NOT NULL DEFAULT 4096,
    max_tokens      INTEGER NOT NULL DEFAULT 2048,
    -- Ressourcen-Anforderungen
    required_vram_mb    INTEGER DEFAULT 0,
    required_ram_mb     INTEGER DEFAULT 0,
    requires_gpu        BOOLEAN NOT NULL DEFAULT FALSE,
    -- Status
    state           TEXT NOT NULL DEFAULT 'available'
                    CHECK (state IN (
                        'available', 'loading', 'loaded', 'unloading',
                        'error', 'disabled', 'downloading'
                    )),
    is_loaded       BOOLEAN NOT NULL DEFAULT FALSE,
    loaded_at       TIMESTAMPTZ,
    -- Statistiken
    total_tokens    BIGINT NOT NULL DEFAULT 0,
    total_requests  BIGINT NOT NULL DEFAULT 0,
    avg_latency_ms  DOUBLE PRECISION DEFAULT 0,
    last_used_at    TIMESTAMPTZ,
    -- Fähigkeiten
    capabilities    TEXT[] NOT NULL DEFAULT '{}',
    supported_languages TEXT[] NOT NULL DEFAULT ARRAY['de', 'en'],
    -- Zeitstempel
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE dbai_llm.ghost_models IS
    'Alle verfügbaren KI-Modelle (Ghosts). Jedes Modell kann als Ghost aktiviert werden.';

CREATE TRIGGER trg_ghost_models_updated
    BEFORE UPDATE ON dbai_llm.ghost_models
    FOR EACH ROW EXECUTE FUNCTION dbai_core.update_timestamp();

-- =============================================================================
-- 2. GHOST ROLES — Welche Rollen kann ein Ghost übernehmen?
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_llm.ghost_roles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL UNIQUE,
    display_name    TEXT NOT NULL,
    description     TEXT,
    icon            TEXT NOT NULL DEFAULT '🤖',
    color           TEXT NOT NULL DEFAULT '#00ffcc',
    -- Welche Tabellen/Schemas darf dieser Role-Ghost lesen?
    accessible_schemas  TEXT[] NOT NULL DEFAULT '{}',
    accessible_tables   TEXT[] NOT NULL DEFAULT '{}',
    -- System-Prompt für diese Rolle
    system_prompt   TEXT NOT NULL,
    -- Priorität (niedrig = wichtiger)
    priority        INTEGER NOT NULL DEFAULT 5
                    CHECK (priority BETWEEN 1 AND 10),
    is_critical     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE dbai_llm.ghost_roles IS
    'Definiert Rollen die ein Ghost übernehmen kann: Sysadmin, Coder, Security, Creative, etc.';

CREATE TRIGGER trg_ghost_roles_updated
    BEFORE UPDATE ON dbai_llm.ghost_roles
    FOR EACH ROW EXECUTE FUNCTION dbai_core.update_timestamp();

-- =============================================================================
-- 3. ACTIVE GHOSTS — Welcher Ghost ist gerade in welcher Shell aktiv?
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_llm.active_ghosts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id         UUID NOT NULL REFERENCES dbai_llm.ghost_roles(id),
    model_id        UUID NOT NULL REFERENCES dbai_llm.ghost_models(id),
    -- Session-Info
    session_id      UUID NOT NULL DEFAULT gen_random_uuid(),
    activated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deactivated_at  TIMESTAMPTZ,
    -- Status
    state           TEXT NOT NULL DEFAULT 'activating'
                    CHECK (state IN (
                        'activating', 'active', 'swapping', 'deactivating',
                        'inactive', 'error'
                    )),
    -- Kontext: Was hat der Ghost gerade im "Gedächtnis"?
    context_window  JSONB NOT NULL DEFAULT '[]'::JSONB,
    tokens_used     INTEGER NOT NULL DEFAULT 0,
    -- Wer hat den Swap initiiert?
    activated_by    TEXT NOT NULL DEFAULT 'system',
    swap_reason     TEXT,
    -- Constraint: Pro Rolle nur ein aktiver Ghost
    UNIQUE (role_id) -- wird durch Trigger weiter eingeschränkt
);

COMMENT ON TABLE dbai_llm.active_ghosts IS
    'Zeigt welcher Ghost (KI-Modell) gerade in welcher Rolle aktiv ist. Hot-Swap per UPDATE.';

-- =============================================================================
-- 4. GHOST HISTORY — Audit-Trail aller Ghost-Wechsel (Append-Only)
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_llm.ghost_history (
    id              BIGSERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    role_id         UUID NOT NULL,
    role_name       TEXT NOT NULL,
    old_model_id    UUID,
    old_model_name  TEXT,
    new_model_id    UUID NOT NULL,
    new_model_name  TEXT NOT NULL,
    swap_reason     TEXT,
    swap_duration_ms INTEGER,
    initiated_by    TEXT NOT NULL DEFAULT 'system',
    success         BOOLEAN NOT NULL DEFAULT TRUE,
    error_message   TEXT,
    metadata        JSONB DEFAULT '{}'::JSONB
);

COMMENT ON TABLE dbai_llm.ghost_history IS
    'Append-Only Audit-Trail aller Ghost-Wechsel. Wer hat wann welche KI gewechselt?';

-- Append-Only Schutz
CREATE OR REPLACE FUNCTION dbai_llm.protect_ghost_history()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Ghost-History ist Append-Only — DELETE verboten';
    END IF;
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'Ghost-History ist Append-Only — UPDATE verboten';
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_protect_ghost_history
    BEFORE UPDATE OR DELETE ON dbai_llm.ghost_history
    FOR EACH ROW EXECUTE FUNCTION dbai_llm.protect_ghost_history();

-- =============================================================================
-- 5. GHOST SWAP — Die zentrale Funktion zum KI-Wechsel
-- =============================================================================

CREATE OR REPLACE FUNCTION dbai_llm.swap_ghost(
    p_role_name     TEXT,
    p_model_name    TEXT,
    p_reason        TEXT DEFAULT 'Manueller Wechsel',
    p_initiated_by  TEXT DEFAULT 'user'
)
RETURNS JSONB AS $$
DECLARE
    v_role          dbai_llm.ghost_roles%ROWTYPE;
    v_model         dbai_llm.ghost_models%ROWTYPE;
    v_current       dbai_llm.active_ghosts%ROWTYPE;
    v_old_model_id  UUID;
    v_old_model_name TEXT;
    v_start_ts      TIMESTAMPTZ := clock_timestamp();
    v_duration_ms   INTEGER;
    v_result        JSONB;
BEGIN
    -- 1. Rolle finden
    SELECT * INTO v_role FROM dbai_llm.ghost_roles WHERE name = p_role_name;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Ghost-Rolle "%" nicht gefunden', p_role_name;
    END IF;

    -- 2. Neues Modell finden
    SELECT * INTO v_model FROM dbai_llm.ghost_models WHERE name = p_model_name;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Ghost-Modell "%" nicht gefunden', p_model_name;
    END IF;

    -- 3. Prüfen ob Modell verfügbar
    IF v_model.state = 'disabled' THEN
        RAISE EXCEPTION 'Ghost-Modell "%" ist deaktiviert', p_model_name;
    END IF;

    -- 4. Aktuellen Ghost für diese Rolle finden
    SELECT * INTO v_current FROM dbai_llm.active_ghosts
    WHERE role_id = v_role.id AND state IN ('active', 'activating');

    IF FOUND THEN
        v_old_model_id := v_current.model_id;
        SELECT name INTO v_old_model_name FROM dbai_llm.ghost_models WHERE id = v_old_model_id;

        -- Aktuellen Ghost deaktivieren
        UPDATE dbai_llm.active_ghosts
        SET state = 'swapping', deactivated_at = NOW()
        WHERE id = v_current.id;
    END IF;

    -- 5. Alten Eintrag löschen (wegen UNIQUE constraint auf role_id)
    DELETE FROM dbai_llm.active_ghosts WHERE role_id = v_role.id;

    -- 6. Neuen Ghost aktivieren
    INSERT INTO dbai_llm.active_ghosts (role_id, model_id, state, activated_by, swap_reason)
    VALUES (v_role.id, v_model.id, 'activating', p_initiated_by, p_reason);

    -- 7. Modell-Status aktualisieren
    UPDATE dbai_llm.ghost_models SET state = 'loading' WHERE id = v_model.id;

    -- 8. Duration berechnen
    v_duration_ms := EXTRACT(MILLISECONDS FROM clock_timestamp() - v_start_ts)::INTEGER;

    -- 9. History-Eintrag (Append-Only)
    INSERT INTO dbai_llm.ghost_history
        (role_id, role_name, old_model_id, old_model_name, new_model_id, new_model_name,
         swap_reason, swap_duration_ms, initiated_by)
    VALUES
        (v_role.id, v_role.name, v_old_model_id, v_old_model_name,
         v_model.id, v_model.name, p_reason, v_duration_ms, p_initiated_by);

    -- 10. NOTIFY an den Python-Dispatcher senden
    v_result := jsonb_build_object(
        'action', 'ghost_swap',
        'role', v_role.name,
        'old_model', v_old_model_name,
        'new_model', v_model.name,
        'model_path', v_model.model_path,
        'provider', v_model.provider,
        'parameters', v_model.parameters,
        'context_size', v_model.context_size,
        'requires_gpu', v_model.requires_gpu,
        'swap_duration_ms', v_duration_ms
    );

    PERFORM pg_notify('ghost_swap', v_result::TEXT);

    -- 11. Event dispatchen
    PERFORM dbai_event.dispatch_event(
        'llm', 'ghost_system', 2, v_result
    );

    RETURN v_result;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION dbai_llm.swap_ghost IS
    'Hot-Swap: Wechselt den Ghost (KI-Modell) für eine bestimmte Rolle. Sendet NOTIFY an Dispatcher.';

-- =============================================================================
-- 6. GHOST QUERY — Anfrage an den aktiven Ghost einer Rolle
-- =============================================================================

CREATE OR REPLACE FUNCTION dbai_llm.ask_ghost(
    p_role_name TEXT,
    p_question  TEXT,
    p_context   JSONB DEFAULT '{}'::JSONB
)
RETURNS JSONB AS $$
DECLARE
    v_ghost         dbai_llm.active_ghosts%ROWTYPE;
    v_role          dbai_llm.ghost_roles%ROWTYPE;
    v_model         dbai_llm.ghost_models%ROWTYPE;
    v_result        JSONB;
    v_task_id       UUID;
BEGIN
    -- 1. Rolle und aktiven Ghost finden
    SELECT r.* INTO v_role FROM dbai_llm.ghost_roles r WHERE r.name = p_role_name;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Ghost-Rolle "%" nicht gefunden', p_role_name;
    END IF;

    SELECT ag.* INTO v_ghost FROM dbai_llm.active_ghosts ag
    WHERE ag.role_id = v_role.id AND ag.state = 'active';
    IF NOT FOUND THEN
        RETURN jsonb_build_object(
            'error', 'Kein aktiver Ghost für Rolle "' || p_role_name || '"',
            'hint', 'Nutze dbai_llm.swap_ghost() um einen Ghost zu aktivieren'
        );
    END IF;

    SELECT * INTO v_model FROM dbai_llm.ghost_models WHERE id = v_ghost.model_id;

    -- 2. Task in die Queue stellen
    INSERT INTO dbai_llm.task_queue
        (task_type, priority, input_data, accessible_tables, state)
    VALUES
        ('query', v_role.priority,
         jsonb_build_object(
             'role', p_role_name,
             'system_prompt', v_role.system_prompt,
             'question', p_question,
             'context', p_context,
             'model', v_model.name,
             'model_id', v_model.id,
             'session_id', v_ghost.session_id
         ),
         v_role.accessible_tables,
         'pending')
    RETURNING id INTO v_task_id;

    -- 3. NOTIFY an Dispatcher
    PERFORM pg_notify('ghost_query', jsonb_build_object(
        'task_id', v_task_id,
        'role', p_role_name,
        'model', v_model.name,
        'provider', v_model.provider
    )::TEXT);

    -- 4. Statistik aktualisieren
    UPDATE dbai_llm.ghost_models
    SET total_requests = total_requests + 1, last_used_at = NOW()
    WHERE id = v_model.id;

    RETURN jsonb_build_object(
        'task_id', v_task_id,
        'role', p_role_name,
        'model', v_model.name,
        'status', 'queued',
        'message', 'Anfrage an Ghost "' || v_model.display_name || '" gesendet'
    );
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION dbai_llm.ask_ghost IS
    'Stellt eine Anfrage an den aktiven Ghost einer bestimmten Rolle. Asynchron via Task-Queue.';

-- =============================================================================
-- 7. GHOST STATUS VIEW — Übersicht aller aktiven Ghosts
-- =============================================================================

CREATE OR REPLACE VIEW dbai_llm.vw_active_ghosts AS
SELECT
    r.name          AS role_name,
    r.display_name  AS role_display,
    r.icon          AS role_icon,
    r.color         AS role_color,
    m.name          AS model_name,
    m.display_name  AS model_display,
    m.model_type,
    m.provider,
    m.parameter_count,
    m.quantization,
    m.is_loaded,
    ag.state        AS ghost_state,
    ag.activated_at,
    ag.tokens_used,
    m.total_requests,
    m.avg_latency_ms,
    m.capabilities,
    r.system_prompt
FROM dbai_llm.active_ghosts ag
JOIN dbai_llm.ghost_roles r ON ag.role_id = r.id
JOIN dbai_llm.ghost_models m ON ag.model_id = m.id
WHERE ag.state IN ('active', 'activating');

COMMENT ON VIEW dbai_llm.vw_active_ghosts IS
    'Live-Übersicht: Welches KI-Modell sitzt gerade in welcher Rolle?';

-- =============================================================================
-- 8. GHOST COMPATIBILITY — Welches Modell kann welche Rolle?
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_llm.ghost_compatibility (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id        UUID NOT NULL REFERENCES dbai_llm.ghost_models(id) ON DELETE CASCADE,
    role_id         UUID NOT NULL REFERENCES dbai_llm.ghost_roles(id) ON DELETE CASCADE,
    fitness_score   DOUBLE PRECISION NOT NULL DEFAULT 0.5
                    CHECK (fitness_score BETWEEN 0.0 AND 1.0),
    notes           TEXT,
    tested          BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (model_id, role_id)
);

COMMENT ON TABLE dbai_llm.ghost_compatibility IS
    'Fitness-Matrix: Wie gut passt welches Modell zu welcher Rolle? 0.0 = unbrauchbar, 1.0 = perfekt.';

-- =============================================================================
-- 9. RLS — Row Level Security für Ghost-Tabellen
-- =============================================================================

ALTER TABLE dbai_llm.ghost_models ENABLE ROW LEVEL SECURITY;
CREATE POLICY ghost_models_system ON dbai_llm.ghost_models FOR ALL TO dbai_system USING (TRUE);
CREATE POLICY ghost_models_llm_read ON dbai_llm.ghost_models FOR SELECT TO dbai_llm USING (TRUE);
CREATE POLICY ghost_models_monitor ON dbai_llm.ghost_models FOR SELECT TO dbai_monitor USING (TRUE);

ALTER TABLE dbai_llm.ghost_roles ENABLE ROW LEVEL SECURITY;
CREATE POLICY ghost_roles_system ON dbai_llm.ghost_roles FOR ALL TO dbai_system USING (TRUE);
CREATE POLICY ghost_roles_llm_read ON dbai_llm.ghost_roles FOR SELECT TO dbai_llm USING (TRUE);

ALTER TABLE dbai_llm.active_ghosts ENABLE ROW LEVEL SECURITY;
CREATE POLICY active_ghosts_system ON dbai_llm.active_ghosts FOR ALL TO dbai_system USING (TRUE);
CREATE POLICY active_ghosts_llm_read ON dbai_llm.active_ghosts FOR SELECT TO dbai_llm USING (TRUE);
CREATE POLICY active_ghosts_monitor ON dbai_llm.active_ghosts FOR SELECT TO dbai_monitor USING (TRUE);

ALTER TABLE dbai_llm.ghost_history ENABLE ROW LEVEL SECURITY;
CREATE POLICY ghost_history_system ON dbai_llm.ghost_history FOR ALL TO dbai_system USING (TRUE);
CREATE POLICY ghost_history_monitor ON dbai_llm.ghost_history FOR SELECT TO dbai_monitor USING (TRUE);

ALTER TABLE dbai_llm.ghost_compatibility ENABLE ROW LEVEL SECURITY;
CREATE POLICY ghost_compat_system ON dbai_llm.ghost_compatibility FOR ALL TO dbai_system USING (TRUE);
CREATE POLICY ghost_compat_llm ON dbai_llm.ghost_compatibility FOR SELECT TO dbai_llm USING (TRUE);

-- Grants
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA dbai_llm TO dbai_system;
GRANT SELECT ON ALL TABLES IN SCHEMA dbai_llm TO dbai_llm;
GRANT SELECT ON ALL TABLES IN SCHEMA dbai_llm TO dbai_monitor;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA dbai_llm TO dbai_system;
