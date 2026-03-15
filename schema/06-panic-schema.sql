-- =============================================================================
-- DBAI Schema 06: Kernel Panic Schema
-- Isolierte Notfalltabelle — schreibgeschützt nach Initialisierung
-- Enthält minimale Treiber um das System zu reparieren
-- =============================================================================

-- Notfall-Treiber: Minimaler Satz an Treibern für Reparatur
CREATE TABLE dbai_panic.emergency_drivers (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    driver_type     TEXT NOT NULL CHECK (driver_type IN (
                        'storage', 'network_minimal', 'console'
                    )),
    -- Treiber-Binärcode als Bytea (klein genug für Notfall)
    binary_data     BYTEA,
    -- Konfiguration
    config          JSONB NOT NULL DEFAULT '{}',
    -- Prüfsumme zur Validierung
    checksum        TEXT NOT NULL,
    version         TEXT NOT NULL,
    -- Wann wurde dieser Notfall-Treiber zuletzt validiert
    last_validated  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_valid        BOOLEAN NOT NULL DEFAULT TRUE
);

-- Notfall-Konfiguration: Minimale Boot-Parameter
CREATE TABLE dbai_panic.boot_config (
    key             TEXT PRIMARY KEY,
    value           JSONB NOT NULL,
    description     TEXT NOT NULL,
    checksum        TEXT NOT NULL
);

-- Notfall-Reparatur-Skripte
CREATE TABLE dbai_panic.repair_scripts (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    description     TEXT NOT NULL,
    -- SQL-Skript für Reparatur
    script_sql      TEXT NOT NULL,
    -- Reihenfolge der Ausführung
    execution_order INTEGER NOT NULL,
    -- Prüfsumme
    checksum        TEXT NOT NULL,
    -- Bedingung: Wann soll dieses Skript ausgeführt werden
    trigger_condition TEXT NOT NULL DEFAULT 'always'
);

-- Notfall-Log: Dokumentiert Panic-Ereignisse
CREATE TABLE dbai_panic.panic_log (
    id              BIGSERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    panic_type      TEXT NOT NULL CHECK (panic_type IN (
                        'db_corruption', 'disk_failure', 'memory_overflow',
                        'deadlock_cascade', 'llm_runaway', 'data_integrity',
                        'boot_failure', 'driver_crash', 'unknown'
                    )),
    severity        TEXT NOT NULL CHECK (severity IN (
                        'warning', 'critical', 'fatal'
                    )),
    description     TEXT NOT NULL,
    stack_trace     TEXT,
    system_state    JSONB,
    recovery_action TEXT,
    resolved        BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_at     TIMESTAMPTZ
);

-- Append-Only für Panic-Log
CREATE OR REPLACE FUNCTION dbai_panic.protect_panic_log()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Panic-Logs dürfen NIEMALS gelöscht werden';
    END IF;
    -- Nur resolved-Flag darf geändert werden
    IF TG_OP = 'UPDATE' THEN
        IF NEW.panic_type != OLD.panic_type OR
           NEW.description != OLD.description OR
           NEW.ts != OLD.ts THEN
            RAISE EXCEPTION 'Panic-Log-Daten sind unveränderlich';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_panic_log_protect
    BEFORE UPDATE OR DELETE ON dbai_panic.panic_log
    FOR EACH ROW EXECUTE FUNCTION dbai_panic.protect_panic_log();

-- =============================================================================
-- Schreibschutz für Notfall-Tabellen (nach Initialisierung)
-- =============================================================================
CREATE OR REPLACE FUNCTION dbai_panic.lock_after_init()
RETURNS TRIGGER AS $$
DECLARE
    v_locked BOOLEAN;
BEGIN
    SELECT (value->>'locked')::BOOLEAN INTO v_locked
    FROM dbai_panic.boot_config
    WHERE key = 'panic_schema_locked';

    IF v_locked = TRUE THEN
        RAISE EXCEPTION 'Panic-Schema ist gesperrt. Nur im Recovery-Modus änderbar.';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_emergency_drivers_lock
    BEFORE INSERT OR UPDATE OR DELETE ON dbai_panic.emergency_drivers
    FOR EACH ROW EXECUTE FUNCTION dbai_panic.lock_after_init();

CREATE TRIGGER trg_repair_scripts_lock
    BEFORE INSERT OR UPDATE OR DELETE ON dbai_panic.repair_scripts
    FOR EACH ROW EXECUTE FUNCTION dbai_panic.lock_after_init();

-- =============================================================================
-- Notfall-Reparatur ausführen
-- =============================================================================
CREATE OR REPLACE FUNCTION dbai_panic.execute_repair(
    p_panic_type TEXT DEFAULT NULL
) RETURNS TABLE (
    script_name TEXT,
    success BOOLEAN,
    message TEXT
) AS $$
DECLARE
    v_script RECORD;
    v_result TEXT;
BEGIN
    FOR v_script IN
        SELECT rs.name, rs.script_sql, rs.trigger_condition
        FROM dbai_panic.repair_scripts rs
        WHERE p_panic_type IS NULL
           OR rs.trigger_condition = p_panic_type
           OR rs.trigger_condition = 'always'
        ORDER BY rs.execution_order
    LOOP
        BEGIN
            EXECUTE v_script.script_sql;
            script_name := v_script.name;
            success := TRUE;
            message := 'Erfolgreich ausgeführt';
            RETURN NEXT;
        EXCEPTION WHEN OTHERS THEN
            script_name := v_script.name;
            success := FALSE;
            message := SQLERRM;
            RETURN NEXT;
        END;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Initiale Notfall-Konfiguration
-- =============================================================================
INSERT INTO dbai_panic.boot_config (key, value, description, checksum) VALUES
    ('panic_schema_locked', '{"locked": false}'::JSONB,
     'Sperrt das Panic-Schema nach Initialisierung',
     md5('{"locked": false}')),
    ('min_boot_config', '{"db_port": 5432, "db_name": "dbai", "listen": "127.0.0.1"}'::JSONB,
     'Minimale Boot-Konfiguration für Notfall',
     md5('{"db_port": 5432, "db_name": "dbai", "listen": "127.0.0.1"}')),
    ('recovery_mode', '{"active": false, "reason": null, "since": null}'::JSONB,
     'Recovery-Modus Status',
     md5('{"active": false, "reason": null, "since": null}'));

-- Initiale Reparatur-Skripte
INSERT INTO dbai_panic.repair_scripts (name, description, script_sql, execution_order, trigger_condition, checksum) VALUES
    ('verify_core_schema', 'Prüft ob alle Core-Tabellen existieren',
     $$SELECT COUNT(*) FROM information_schema.tables
       WHERE table_schema = 'dbai_core'$$,
     1, 'always', md5('verify_core_schema')),

    ('verify_journal_integrity', 'Prüft Journal-Integrität',
     $$SELECT COUNT(*) FROM dbai_journal.change_log
       WHERE checksum != md5(new_data::TEXT)
       AND new_data IS NOT NULL$$,
     2, 'data_integrity', md5('verify_journal_integrity')),

    ('kill_zombie_processes', 'Beendet Zombie-Prozesse in der Prozesstabelle',
     $$UPDATE dbai_core.processes SET state = 'stopped', stopped_at = NOW()
       WHERE state = 'zombie' OR (state = 'running' AND last_heartbeat < NOW() - INTERVAL '5 minutes')$$,
     3, 'always', md5('kill_zombie_processes')),

    ('reset_stuck_locks', 'Setzt blockierte Advisory Locks zurück',
     $$SELECT pg_advisory_unlock_all()$$,
     4, 'deadlock_cascade', md5('reset_stuck_locks'));
