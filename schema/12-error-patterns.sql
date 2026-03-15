-- =============================================================================
-- DBAI Schema 12: Error Patterns & Runbooks
-- Automatische Fehlererkennung und -behebung
--
-- Das System erkennt Fehler anhand von Mustern und weiß sofort was zu tun ist.
-- Kein Googlen, kein Stack Overflow — die Lösung steht in der DB.
--
-- Workflow:
--   1. Fehler tritt auf → log_error()
--   2. System matcht gegen error_patterns → match_error()
--   3. Passender Runbook gefunden → Schritte anzeigen / auto-ausführen
--   4. Lösung dokumentiert → Wissen wächst mit jedem Fehler
-- =============================================================================

-- =============================================================================
-- TABELLE: error_patterns
-- Bekannte Fehlermuster mit Regex-Signaturen
-- Wenn ein Fehler auftritt, wird er gegen diese Muster gematcht
-- =============================================================================
CREATE TABLE dbai_knowledge.error_patterns (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    -- Identifikation
    name            TEXT NOT NULL UNIQUE,             -- z.B. 'posix_c_source_missing'
    title           TEXT NOT NULL,                    -- z.B. 'CLOCK_MONOTONIC undeclared'
    -- Fehlermuster (Regex zur Erkennung)
    error_regex     TEXT NOT NULL,                    -- Regex auf stderr/error_message
    error_source    TEXT NOT NULL CHECK (error_source IN (
                        'compile', 'runtime', 'sql', 'config',
                        'network', 'hardware', 'filesystem', 'llm',
                        'python', 'bash', 'postgresql', 'system'
                    )),
    -- Kategorisierung
    severity        TEXT NOT NULL DEFAULT 'medium' CHECK (severity IN (
                        'low', 'medium', 'high', 'critical'
                    )),
    category        TEXT NOT NULL CHECK (category IN (
                        'missing_dependency', 'wrong_config', 'permission',
                        'resource_exhaustion', 'corruption', 'network',
                        'compatibility', 'logic_error', 'timeout',
                        'concurrency', 'security', 'hardware'
                    )),
    -- Kontext
    affected_component TEXT,                         -- z.B. 'bridge/c_bindings'
    description     TEXT NOT NULL,                   -- Was bedeutet dieser Fehler
    root_cause      TEXT NOT NULL,                   -- Warum tritt er auf
    -- Lösung
    solution_short  TEXT NOT NULL,                   -- Einzeiler-Fix
    solution_detail TEXT,                            -- Ausführliche Erklärung
    -- Auto-Fix (SQL oder Shell, das automatisch ausgeführt werden kann)
    auto_fix_sql    TEXT,                            -- SQL-Statement zum Fixen
    auto_fix_shell  TEXT,                            -- Shell-Befehl zum Fixen
    can_auto_fix    BOOLEAN NOT NULL DEFAULT FALSE,
    -- Statistiken
    occurrence_count INTEGER NOT NULL DEFAULT 0,
    last_occurred   TIMESTAMPTZ,
    first_occurred  TIMESTAMPTZ DEFAULT NOW(),
    -- Verknüpfungen
    related_patterns UUID[] DEFAULT '{}',
    tags            TEXT[] DEFAULT '{}',
    metadata        JSONB DEFAULT '{}',
    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER trg_error_pattern_updated
    BEFORE UPDATE ON dbai_knowledge.error_patterns
    FOR EACH ROW EXECUTE FUNCTION dbai_core.update_timestamp();

CREATE INDEX idx_ep_source ON dbai_knowledge.error_patterns(error_source);
CREATE INDEX idx_ep_severity ON dbai_knowledge.error_patterns(severity);
CREATE INDEX idx_ep_category ON dbai_knowledge.error_patterns(category);
CREATE INDEX idx_ep_tags ON dbai_knowledge.error_patterns USING GIN(tags);
CREATE INDEX idx_ep_component ON dbai_knowledge.error_patterns(affected_component);

-- =============================================================================
-- TABELLE: runbooks
-- Schritt-für-Schritt Anleitungen zur Fehlerbehebung
-- Wie ein Notfall-Handbuch, aber in der Datenbank
-- =============================================================================
CREATE TABLE dbai_knowledge.runbooks (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    description     TEXT NOT NULL,
    -- Wann wird dieses Runbook relevant
    trigger_conditions JSONB NOT NULL DEFAULT '[]',  -- [{field: 'error_source', op: '=', value: 'compile'}]
    -- Schritte (geordnet)
    steps           JSONB NOT NULL DEFAULT '[]',     -- [{step: 1, action: '...', type: 'manual|sql|shell', command: '...'}]
    -- Kategorisierung
    category        TEXT NOT NULL CHECK (category IN (
                        'error_resolution', 'maintenance',
                        'disaster_recovery', 'performance',
                        'security_incident', 'deployment',
                        'debugging', 'monitoring'
                    )),
    -- Geschätzte Dauer
    estimated_minutes INTEGER,
    -- Verknüpfungen
    error_pattern_ids UUID[] DEFAULT '{}',
    -- Statistiken
    execution_count INTEGER NOT NULL DEFAULT 0,
    success_count   INTEGER NOT NULL DEFAULT 0,
    last_executed   TIMESTAMPTZ,
    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER trg_runbook_updated
    BEFORE UPDATE ON dbai_knowledge.runbooks
    FOR EACH ROW EXECUTE FUNCTION dbai_core.update_timestamp();

CREATE INDEX idx_runbook_category ON dbai_knowledge.runbooks(category);

-- =============================================================================
-- TABELLE: error_log
-- Tatsächlich aufgetretene Fehler (Append-Only)
-- =============================================================================
CREATE TABLE dbai_knowledge.error_log (
    id              BIGSERIAL PRIMARY KEY,
    -- Fehlerdetails
    error_source    TEXT NOT NULL,                    -- Wo trat der Fehler auf
    error_message   TEXT NOT NULL,                    -- Fehlermeldung
    error_detail    TEXT,                             -- Stack-Trace / Details
    -- Kontext
    module_path     TEXT,                             -- Welches Modul war betroffen
    function_name   TEXT,                             -- Welche Funktion
    input_data      JSONB,                            -- Was war der Input
    system_state    JSONB,                            -- Systemzustand zum Zeitpunkt
    -- Automatisches Pattern-Matching
    matched_pattern_id UUID REFERENCES dbai_knowledge.error_patterns(id),
    matched_runbook_id UUID REFERENCES dbai_knowledge.runbooks(id),
    match_confidence REAL,                            -- 0.0 - 1.0
    -- Auflösung
    is_resolved     BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_by     TEXT,                             -- 'auto' | 'manual' | 'runbook'
    resolution_note TEXT,
    resolved_at     TIMESTAMPTZ,
    -- Timestamps
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Append-Only
CREATE OR REPLACE FUNCTION dbai_knowledge.protect_error_log()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Error-Logs dürfen NIEMALS gelöscht werden';
    END IF;
    IF TG_OP = 'UPDATE' THEN
        -- Nur Resolution-Felder dürfen geändert werden
        IF NEW.error_message != OLD.error_message OR
           NEW.error_source != OLD.error_source OR
           NEW.occurred_at != OLD.occurred_at THEN
            RAISE EXCEPTION 'Error-Log Kernfelder sind unveränderlich';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_protect_error_log
    BEFORE UPDATE OR DELETE ON dbai_knowledge.error_log
    FOR EACH ROW EXECUTE FUNCTION dbai_knowledge.protect_error_log();

CREATE INDEX idx_errlog_source ON dbai_knowledge.error_log(error_source);
CREATE INDEX idx_errlog_pattern ON dbai_knowledge.error_log(matched_pattern_id);
CREATE INDEX idx_errlog_resolved ON dbai_knowledge.error_log(is_resolved) WHERE is_resolved = FALSE;
CREATE INDEX idx_errlog_occurred ON dbai_knowledge.error_log(occurred_at DESC);

-- =============================================================================
-- TABELLE: error_resolutions
-- Dokumentiert wie Fehler gelöst wurden — Wissen wächst
-- =============================================================================
CREATE TABLE dbai_knowledge.error_resolutions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    error_log_id    BIGINT NOT NULL REFERENCES dbai_knowledge.error_log(id),
    -- Was wurde getan
    resolution_type TEXT NOT NULL CHECK (resolution_type IN (
                        'auto_fix_sql', 'auto_fix_shell', 'manual_fix',
                        'config_change', 'code_change', 'restart',
                        'rollback', 'escalated', 'ignored'
                    )),
    description     TEXT NOT NULL,
    -- Ausgeführte Aktionen
    commands_executed TEXT[],
    sql_executed    TEXT[],
    files_modified  TEXT[],
    -- Ergebnis
    success         BOOLEAN NOT NULL,
    side_effects    TEXT,
    -- Zeitaufwand
    resolution_time_minutes INTEGER,
    -- Wird zur Verbesserung des error_patterns genutzt
    should_create_pattern BOOLEAN DEFAULT FALSE,
    new_pattern_suggestion JSONB,
    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_resolution_error ON dbai_knowledge.error_resolutions(error_log_id);
CREATE INDEX idx_resolution_type ON dbai_knowledge.error_resolutions(resolution_type);

-- =============================================================================
-- FUNKTIONEN — Fehler-Management
-- =============================================================================

-- Funktion: Fehler loggen und automatisch gegen Patterns matchen
CREATE OR REPLACE FUNCTION dbai_knowledge.log_error(
    p_source TEXT,
    p_message TEXT,
    p_detail TEXT DEFAULT NULL,
    p_module TEXT DEFAULT NULL,
    p_function TEXT DEFAULT NULL,
    p_context JSONB DEFAULT '{}'
) RETURNS TABLE (
    error_id BIGINT,
    matched_pattern TEXT,
    solution TEXT,
    can_auto_fix BOOLEAN
) AS $$
DECLARE
    v_error_id BIGINT;
    v_pattern RECORD;
    v_best_pattern UUID := NULL;
    v_best_confidence REAL := 0;
    v_solution TEXT := NULL;
    v_can_auto BOOLEAN := FALSE;
    v_pattern_name TEXT := NULL;
BEGIN
    -- 1. Fehler ins Log schreiben
    INSERT INTO dbai_knowledge.error_log
        (error_source, error_message, error_detail, module_path, function_name, input_data)
    VALUES
        (p_source, p_message, p_detail, p_module, p_function, p_context)
    RETURNING id INTO v_error_id;

    -- 2. Gegen bekannte Patterns matchen
    FOR v_pattern IN
        SELECT ep.id, ep.name, ep.error_regex, ep.solution_short,
               ep.can_auto_fix, ep.severity
        FROM dbai_knowledge.error_patterns ep
        WHERE ep.error_source = p_source OR ep.error_source = 'system'
    LOOP
        -- Regex-Match
        IF p_message ~* v_pattern.error_regex
           OR COALESCE(p_detail, '') ~* v_pattern.error_regex THEN
            -- Confidence basiert auf Spezifität des Patterns
            DECLARE
                v_conf REAL;
            BEGIN
                v_conf := 0.5 + (LENGTH(v_pattern.error_regex)::REAL / 200.0);
                IF v_conf > 1.0 THEN v_conf := 1.0; END IF;

                IF v_conf > v_best_confidence THEN
                    v_best_confidence := v_conf;
                    v_best_pattern := v_pattern.id;
                    v_solution := v_pattern.solution_short;
                    v_can_auto := v_pattern.can_auto_fix;
                    v_pattern_name := v_pattern.name;
                END IF;
            END;
        END IF;
    END LOOP;

    -- 3. Match-Ergebnis im Error-Log aktualisieren
    IF v_best_pattern IS NOT NULL THEN
        UPDATE dbai_knowledge.error_log
        SET matched_pattern_id = v_best_pattern,
            match_confidence = v_best_confidence
        WHERE id = v_error_id;

        -- Pattern-Statistik aktualisieren
        UPDATE dbai_knowledge.error_patterns
        SET occurrence_count = occurrence_count + 1,
            last_occurred = NOW()
        WHERE id = v_best_pattern;
    END IF;

    -- 4. Ergebnis zurückgeben
    error_id := v_error_id;
    matched_pattern := v_pattern_name;
    solution := v_solution;
    can_auto_fix := v_can_auto;
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- Funktion: Fehler-Statistiken (welche Fehler treten am häufigsten auf)
CREATE OR REPLACE FUNCTION dbai_knowledge.error_statistics()
RETURNS TABLE (
    pattern_name TEXT,
    pattern_title TEXT,
    severity TEXT,
    total_occurrences BIGINT,
    last_seen TIMESTAMPTZ,
    has_auto_fix BOOLEAN,
    unresolved_count BIGINT
) AS $$
    SELECT
        ep.name,
        ep.title,
        ep.severity,
        ep.occurrence_count::BIGINT,
        ep.last_occurred,
        ep.can_auto_fix,
        (SELECT COUNT(*) FROM dbai_knowledge.error_log el
         WHERE el.matched_pattern_id = ep.id AND el.is_resolved = FALSE)
    FROM dbai_knowledge.error_patterns ep
    ORDER BY ep.occurrence_count DESC;
$$ LANGUAGE SQL STABLE;

-- Funktion: Runbook für einen bestimmten Fehler finden
CREATE OR REPLACE FUNCTION dbai_knowledge.find_runbook(p_error_source TEXT, p_error_message TEXT)
RETURNS TABLE (
    runbook_name TEXT,
    runbook_title TEXT,
    steps JSONB,
    estimated_minutes INTEGER
) AS $$
    SELECT
        rb.name,
        rb.title,
        rb.steps,
        rb.estimated_minutes
    FROM dbai_knowledge.runbooks rb
    WHERE EXISTS (
        SELECT 1
        FROM dbai_knowledge.error_patterns ep
        WHERE ep.id = ANY(rb.error_pattern_ids)
          AND (ep.error_source = p_error_source OR ep.error_source = 'system')
          AND (p_error_message ~* ep.error_regex)
    )
    ORDER BY rb.execution_count DESC
    LIMIT 5;
$$ LANGUAGE SQL STABLE;

-- =============================================================================
-- FK: known_issues → error_patterns
-- =============================================================================
ALTER TABLE dbai_knowledge.known_issues
    ADD CONSTRAINT fk_issue_pattern
    FOREIGN KEY (error_pattern_id)
    REFERENCES dbai_knowledge.error_patterns(id)
    ON DELETE SET NULL;

-- =============================================================================
-- KOMMENTARE
-- =============================================================================
COMMENT ON TABLE dbai_knowledge.error_patterns IS 'Bekannte Fehlermuster mit Regex-Signaturen und Lösungen';
COMMENT ON TABLE dbai_knowledge.runbooks IS 'Schritt-für-Schritt Anleitungen zur Fehlerbehebung';
COMMENT ON TABLE dbai_knowledge.error_log IS 'Append-only Log aller aufgetretenen Fehler';
COMMENT ON TABLE dbai_knowledge.error_resolutions IS 'Wie Fehler gelöst wurden — akkumuliertes Wissen';
COMMENT ON FUNCTION dbai_knowledge.log_error IS 'Loggt Fehler und matcht automatisch gegen bekannte Patterns';
COMMENT ON FUNCTION dbai_knowledge.error_statistics IS 'Häufigkeitsstatistiken der Fehlermuster';
COMMENT ON FUNCTION dbai_knowledge.find_runbook IS 'Findet passendes Runbook für einen bestimmten Fehler';
