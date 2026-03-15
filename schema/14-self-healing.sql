-- =============================================================================
-- DBAI Schema 14: Self-Healing & Observability
-- KI-Verbesserung: Was dem System noch fehlte
--
-- Automatische Erkennung + Behebung von Problemen ohne manuellen Eingriff
-- Telemetrie, Health-Checks als Tabellen, Alerting-Regeln
-- =============================================================================

-- =============================================================================
-- TABELLE: dbai_system.health_checks
-- Regelmäßige Gesundheitsprüfungen — Ergebnisse als Tabelle
-- =============================================================================
CREATE TABLE dbai_system.health_checks (
    id              BIGSERIAL PRIMARY KEY,
    check_name      TEXT NOT NULL,                   -- z.B. 'postgresql_alive', 'disk_usage', 'schema_integrity'
    check_category  TEXT NOT NULL CHECK (check_category IN (
                        'database', 'filesystem', 'hardware', 'network',
                        'schema', 'process', 'llm', 'security'
                    )),
    status          TEXT NOT NULL CHECK (status IN ('ok', 'warning', 'critical', 'unknown')),
    message         TEXT,
    metric_value    REAL,                            -- z.B. 85.3 (Prozent)
    metric_unit     TEXT,                            -- z.B. '%', 'ms', 'MB', 'count'
    checked_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    duration_ms     INTEGER,                         -- Wie lange dauerte der Check
    metadata        JSONB DEFAULT '{}'
);

CREATE INDEX idx_hc_name ON dbai_system.health_checks(check_name, checked_at DESC);
CREATE INDEX idx_hc_status ON dbai_system.health_checks(status) WHERE status != 'ok';
CREATE INDEX idx_hc_checked ON dbai_system.health_checks(checked_at DESC);

-- =============================================================================
-- TABELLE: dbai_system.alert_rules
-- Alerting-Regeln: Wann soll das System reagieren
-- =============================================================================
CREATE TABLE dbai_system.alert_rules (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT NOT NULL UNIQUE,
    description     TEXT NOT NULL,
    -- Bedingung
    check_name      TEXT NOT NULL,                   -- Welcher Health-Check
    condition       TEXT NOT NULL CHECK (condition IN ('>', '<', '>=', '<=', '=', '!=')),
    threshold       REAL NOT NULL,                   -- Schwellenwert
    -- Reaktion
    severity        TEXT NOT NULL DEFAULT 'warning' CHECK (severity IN ('info', 'warning', 'critical')),
    action_type     TEXT NOT NULL DEFAULT 'log' CHECK (action_type IN (
                        'log', 'auto_heal', 'panic', 'notify'
                    )),
    auto_heal_sql   TEXT,                            -- SQL bei auto_heal
    auto_heal_shell TEXT,                            -- Shell-Befehl bei auto_heal
    -- Cooldown (nicht öfter als alle X Sekunden auslösen)
    cooldown_seconds INTEGER NOT NULL DEFAULT 300,
    last_triggered  TIMESTAMPTZ,
    trigger_count   INTEGER NOT NULL DEFAULT 0,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Initiale Alert-Regeln
INSERT INTO dbai_system.alert_rules
    (name, description, check_name, condition, threshold, severity, action_type, auto_heal_sql, cooldown_seconds) VALUES

('disk_usage_warning', 'Warnung bei > 80% Disk-Belegung',
 'disk_usage', '>', 80.0, 'warning', 'log', NULL, 600),

('disk_usage_critical', 'Kritisch bei > 95% Disk-Belegung — Auto-Vacuum',
 'disk_usage', '>', 95.0, 'critical', 'auto_heal',
 'SELECT dbai_system.cleanup_old_metrics(); SELECT dbai_system.smart_vacuum();', 60),

('memory_usage_critical', 'Kritisch bei > 90% RAM-Belegung',
 'memory_usage', '>', 90.0, 'critical', 'log', NULL, 120),

('zombie_processes', 'Zombie-Prozesse gefunden — Auto-Cleanup',
 'zombie_count', '>', 0, 'warning', 'auto_heal',
 'UPDATE dbai_core.processes SET state = ''stopped'', stopped_at = NOW() ' ||
 'WHERE state = ''zombie'' OR (state = ''running'' AND last_heartbeat < NOW() - INTERVAL ''5 minutes'');', 300),

('deadlock_detected', 'Deadlock erkannt — Locks resetten',
 'deadlock_count', '>', 0, 'critical', 'auto_heal',
 'SELECT dbai_core.cleanup_expired_locks();', 60),

('unresolved_panics', 'Ungelöste Panic-Einträge',
 'unresolved_panic_count', '>', 0, 'critical', 'log', NULL, 3600),

('db_connection_count', 'Zu viele DB-Verbindungen',
 'active_connections', '>', 80, 'warning', 'log', NULL, 300),

('schema_integrity', 'Schema-Prüfung fehlgeschlagen',
 'schema_check', '<', 7, 'critical', 'panic', NULL, 60);

-- =============================================================================
-- TABELLE: dbai_system.alert_history
-- Ausgelöste Alerts (Append-Only)
-- =============================================================================
CREATE TABLE dbai_system.alert_history (
    id              BIGSERIAL PRIMARY KEY,
    rule_id         UUID NOT NULL REFERENCES dbai_system.alert_rules(id),
    rule_name       TEXT NOT NULL,
    severity        TEXT NOT NULL,
    message         TEXT NOT NULL,
    metric_value    REAL,
    threshold       REAL,
    action_taken    TEXT,                             -- Was wurde automatisch getan
    action_success  BOOLEAN,
    triggered_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_alert_hist_rule ON dbai_system.alert_history(rule_id, triggered_at DESC);
CREATE INDEX idx_alert_hist_severity ON dbai_system.alert_history(severity);

-- =============================================================================
-- TABELLE: dbai_system.telemetry
-- System-Telemetrie: Aggregierte Metriken über Zeit
-- Für Trend-Analyse und Kapazitätsplanung
-- =============================================================================
CREATE TABLE dbai_system.telemetry (
    id              BIGSERIAL PRIMARY KEY,
    metric_name     TEXT NOT NULL,                   -- z.B. 'boot_time_ms', 'queries_per_second', 'error_rate'
    metric_value    REAL NOT NULL,
    metric_unit     TEXT,
    dimension       TEXT DEFAULT 'system',           -- Dimension / Subsystem
    tags            JSONB DEFAULT '{}',
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_telemetry_name ON dbai_system.telemetry(metric_name, recorded_at DESC);
CREATE INDEX idx_telemetry_dim ON dbai_system.telemetry(dimension);

-- =============================================================================
-- FUNKTION: run_health_checks()
-- Führt alle Gesundheitsprüfungen aus und schreibt Ergebnisse
-- =============================================================================
CREATE OR REPLACE FUNCTION dbai_system.run_health_checks()
RETURNS TABLE (check_name TEXT, status TEXT, message TEXT) AS $$
DECLARE
    v_check_name TEXT;
    v_status TEXT;
    v_message TEXT;
    v_value REAL;
    v_count INTEGER;
BEGIN
    -- 1. PostgreSQL Alive
    v_check_name := 'postgresql_alive';
    BEGIN
        PERFORM 1;
        v_status := 'ok';
        v_message := 'PostgreSQL antwortet';
        v_value := 1;
    EXCEPTION WHEN OTHERS THEN
        v_status := 'critical';
        v_message := 'PostgreSQL antwortet NICHT: ' || SQLERRM;
        v_value := 0;
    END;
    INSERT INTO dbai_system.health_checks (check_name, check_category, status, message, metric_value, metric_unit)
    VALUES (v_check_name, 'database', v_status, v_message, v_value, 'bool');
    check_name := v_check_name; status := v_status; message := v_message; RETURN NEXT;

    -- 2. Schema-Integrität
    v_check_name := 'schema_check';
    SELECT COUNT(*) INTO v_count FROM information_schema.schemata WHERE schema_name LIKE 'dbai_%';
    IF v_count >= 7 THEN
        v_status := 'ok';
        v_message := v_count || ' DBAI-Schemas gefunden';
    ELSE
        v_status := 'critical';
        v_message := 'Nur ' || v_count || ' von 8 DBAI-Schemas gefunden!';
    END IF;
    v_value := v_count;
    INSERT INTO dbai_system.health_checks (check_name, check_category, status, message, metric_value, metric_unit)
    VALUES (v_check_name, 'schema', v_status, v_message, v_value, 'count');
    check_name := v_check_name; status := v_status; message := v_message; RETURN NEXT;

    -- 3. Zombie-Prozesse
    v_check_name := 'zombie_count';
    SELECT COUNT(*) INTO v_count FROM dbai_core.processes
    WHERE state = 'zombie' OR (state = 'running' AND last_heartbeat < NOW() - INTERVAL '5 minutes');
    IF v_count = 0 THEN
        v_status := 'ok';
        v_message := 'Keine Zombie-Prozesse';
    ELSE
        v_status := 'warning';
        v_message := v_count || ' Zombie-Prozesse gefunden';
    END IF;
    v_value := v_count;
    INSERT INTO dbai_system.health_checks (check_name, check_category, status, message, metric_value, metric_unit)
    VALUES (v_check_name, 'process', v_status, v_message, v_value, 'count');
    check_name := v_check_name; status := v_status; message := v_message; RETURN NEXT;

    -- 4. Deadlocks
    v_check_name := 'deadlock_count';
    SELECT COUNT(*) INTO v_count FROM pg_stat_activity WHERE wait_event_type = 'Lock';
    IF v_count = 0 THEN
        v_status := 'ok';
        v_message := 'Keine Lock-Waits';
    ELSE
        v_status := 'warning';
        v_message := v_count || ' Prozesse warten auf Locks';
    END IF;
    v_value := v_count;
    INSERT INTO dbai_system.health_checks (check_name, check_category, status, message, metric_value, metric_unit)
    VALUES (v_check_name, 'database', v_status, v_message, v_value, 'count');
    check_name := v_check_name; status := v_status; message := v_message; RETURN NEXT;

    -- 5. Aktive Verbindungen
    v_check_name := 'active_connections';
    SELECT COUNT(*) INTO v_count FROM pg_stat_activity WHERE state = 'active';
    IF v_count < 80 THEN
        v_status := 'ok';
    ELSIF v_count < 95 THEN
        v_status := 'warning';
    ELSE
        v_status := 'critical';
    END IF;
    v_message := v_count || ' aktive Verbindungen';
    v_value := v_count;
    INSERT INTO dbai_system.health_checks (check_name, check_category, status, message, metric_value, metric_unit)
    VALUES (v_check_name, 'database', v_status, v_message, v_value, 'count');
    check_name := v_check_name; status := v_status; message := v_message; RETURN NEXT;

    -- 6. Ungelöste Panics
    v_check_name := 'unresolved_panic_count';
    SELECT COUNT(*) INTO v_count FROM dbai_panic.panic_log WHERE resolved = FALSE;
    IF v_count = 0 THEN
        v_status := 'ok';
        v_message := 'Keine ungelösten Panics';
    ELSE
        v_status := 'critical';
        v_message := v_count || ' ungelöste Panic-Einträge!';
    END IF;
    v_value := v_count;
    INSERT INTO dbai_system.health_checks (check_name, check_category, status, message, metric_value, metric_unit)
    VALUES (v_check_name, 'database', v_status, v_message, v_value, 'count');
    check_name := v_check_name; status := v_status; message := v_message; RETURN NEXT;

    -- 7. DB-Größe
    v_check_name := 'database_size';
    SELECT pg_database_size(current_database())::REAL / (1024*1024) INTO v_value;
    v_status := 'ok';
    v_message := ROUND(v_value::numeric, 1) || ' MB Datenbankgröße';
    INSERT INTO dbai_system.health_checks (check_name, check_category, status, message, metric_value, metric_unit)
    VALUES (v_check_name, 'database', v_status, v_message, v_value, 'MB');
    check_name := v_check_name; status := v_status; message := v_message; RETURN NEXT;

    -- 8. Offene Error-Logs
    v_check_name := 'unresolved_errors';
    SELECT COUNT(*) INTO v_count FROM dbai_knowledge.error_log WHERE is_resolved = FALSE;
    IF v_count = 0 THEN
        v_status := 'ok';
        v_message := 'Keine ungelösten Fehler';
    ELSIF v_count < 5 THEN
        v_status := 'warning';
        v_message := v_count || ' ungelöste Fehler';
    ELSE
        v_status := 'critical';
        v_message := v_count || ' ungelöste Fehler!';
    END IF;
    v_value := v_count;
    INSERT INTO dbai_system.health_checks (check_name, check_category, status, message, metric_value, metric_unit)
    VALUES (v_check_name, 'database', v_status, v_message, v_value, 'count');
    check_name := v_check_name; status := v_status; message := v_message; RETURN NEXT;

END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- FUNKTION: evaluate_alerts()
-- Prüft Health-Check-Ergebnisse gegen Alert-Regeln und reagiert
-- =============================================================================
CREATE OR REPLACE FUNCTION dbai_system.evaluate_alerts()
RETURNS TABLE (alert_name TEXT, severity TEXT, action TEXT, result TEXT) AS $$
DECLARE
    v_rule RECORD;
    v_latest_value REAL;
    v_triggered BOOLEAN;
    v_action_result TEXT;
BEGIN
    FOR v_rule IN
        SELECT * FROM dbai_system.alert_rules WHERE is_active = TRUE
    LOOP
        -- Neuesten Wert für diesen Check holen
        SELECT hc.metric_value INTO v_latest_value
        FROM dbai_system.health_checks hc
        WHERE hc.check_name = v_rule.check_name
        ORDER BY hc.checked_at DESC
        LIMIT 1;

        IF v_latest_value IS NULL THEN
            CONTINUE;
        END IF;

        -- Bedingung prüfen
        v_triggered := CASE v_rule.condition
            WHEN '>'  THEN v_latest_value > v_rule.threshold
            WHEN '<'  THEN v_latest_value < v_rule.threshold
            WHEN '>=' THEN v_latest_value >= v_rule.threshold
            WHEN '<=' THEN v_latest_value <= v_rule.threshold
            WHEN '='  THEN v_latest_value = v_rule.threshold
            WHEN '!=' THEN v_latest_value != v_rule.threshold
            ELSE FALSE
        END;

        IF v_triggered THEN
            -- Cooldown prüfen
            IF v_rule.last_triggered IS NOT NULL AND
               v_rule.last_triggered > NOW() - (v_rule.cooldown_seconds || ' seconds')::INTERVAL THEN
                CONTINUE;  -- Noch im Cooldown
            END IF;

            -- Alert auslösen
            v_action_result := 'Alert ausgelöst';

            -- Auto-Heal ausführen
            IF v_rule.action_type = 'auto_heal' AND v_rule.auto_heal_sql IS NOT NULL THEN
                BEGIN
                    EXECUTE v_rule.auto_heal_sql;
                    v_action_result := 'Auto-Heal ausgeführt: ' || LEFT(v_rule.auto_heal_sql, 100);
                EXCEPTION WHEN OTHERS THEN
                    v_action_result := 'Auto-Heal FEHLGESCHLAGEN: ' || SQLERRM;
                END;
            END IF;

            -- Panic auslösen
            IF v_rule.action_type = 'panic' THEN
                INSERT INTO dbai_panic.panic_log (panic_type, severity, description, system_state)
                VALUES ('data_integrity', v_rule.severity,
                        'Alert "' || v_rule.name || '" ausgelöst: Wert=' || v_latest_value || ' Schwelle=' || v_rule.threshold,
                        jsonb_build_object('rule', v_rule.name, 'value', v_latest_value, 'threshold', v_rule.threshold));
                v_action_result := 'PANIC ausgelöst!';
            END IF;

            -- Alert-Historie schreiben
            INSERT INTO dbai_system.alert_history
                (rule_id, rule_name, severity, message, metric_value, threshold, action_taken,
                 action_success)
            VALUES
                (v_rule.id, v_rule.name, v_rule.severity,
                 v_rule.description || ': Wert=' || v_latest_value,
                 v_latest_value, v_rule.threshold, v_action_result,
                 v_action_result NOT LIKE '%FEHLGESCHLAGEN%');

            -- Cooldown aktualisieren
            UPDATE dbai_system.alert_rules
            SET last_triggered = NOW(), trigger_count = trigger_count + 1
            WHERE id = v_rule.id;

            -- Auch in Error-Log schreiben (falls kritisch)
            IF v_rule.severity = 'critical' THEN
                PERFORM dbai_knowledge.log_error(
                    'system',
                    'Alert "' || v_rule.name || '": ' || v_rule.description,
                    'Wert: ' || v_latest_value || ', Schwelle: ' || v_rule.threshold,
                    NULL, 'evaluate_alerts'
                );
            END IF;

            alert_name := v_rule.name;
            severity := v_rule.severity;
            action := v_rule.action_type;
            result := v_action_result;
            RETURN NEXT;
        END IF;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- FUNKTION: self_heal()
-- Führt Health-Checks + Alert-Auswertung + Auto-Healing in einem Durchlauf aus
-- Das ist der "Self-Healing Loop" — periodisch via pg_cron aufrufen
-- =============================================================================
CREATE OR REPLACE FUNCTION dbai_system.self_heal()
RETURNS JSONB AS $$
DECLARE
    v_checks INTEGER;
    v_alerts INTEGER;
    v_result JSONB;
BEGIN
    -- 1. Health-Checks ausführen
    SELECT COUNT(*) INTO v_checks FROM dbai_system.run_health_checks();

    -- 2. Alerts auswerten und ggf. Auto-Heal
    SELECT COUNT(*) INTO v_alerts FROM dbai_system.evaluate_alerts();

    -- 3. Telemetrie schreiben
    INSERT INTO dbai_system.telemetry (metric_name, metric_value, metric_unit, dimension)
    VALUES
        ('self_heal_checks', v_checks, 'count', 'self_healing'),
        ('self_heal_alerts', v_alerts, 'count', 'self_healing');

    -- 4. Ergebnis
    v_result := jsonb_build_object(
        'timestamp', NOW(),
        'health_checks_run', v_checks,
        'alerts_triggered', v_alerts,
        'status', CASE WHEN v_alerts = 0 THEN 'healthy' ELSE 'issues_found' END
    );

    RETURN v_result;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- KOMMENTARE
-- =============================================================================
COMMENT ON TABLE dbai_system.health_checks IS 'Ergebnisse regelmäßiger Gesundheitsprüfungen';
COMMENT ON TABLE dbai_system.alert_rules IS 'Alerting-Regeln mit Schwellenwerten und Auto-Heal-Aktionen';
COMMENT ON TABLE dbai_system.alert_history IS 'Append-Only Historie ausgelöster Alerts';
COMMENT ON TABLE dbai_system.telemetry IS 'Aggregierte Telemetrie-Metriken für Trend-Analyse';
COMMENT ON FUNCTION dbai_system.run_health_checks IS 'Führt alle Gesundheitsprüfungen aus und schreibt Ergebnisse';
COMMENT ON FUNCTION dbai_system.evaluate_alerts IS 'Wertet Health-Checks gegen Alert-Regeln aus und reagiert';
COMMENT ON FUNCTION dbai_system.self_heal IS 'Self-Healing-Loop: Checks + Alerts + Auto-Fix in einem Durchlauf';
