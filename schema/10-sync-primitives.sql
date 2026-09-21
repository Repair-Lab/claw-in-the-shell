-- =============================================================================
-- DBAI Schema 10: Synchronisation-Primitive
-- Verhindert Deadlocks wenn KI und Hardware-Treiber gleichzeitig schreiben
-- =============================================================================

-- Lock-Registry: Alle aktiven Sperren
CREATE TABLE IF NOT EXISTS dbai_system.lock_registry (
    id              BIGSERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lock_type       TEXT NOT NULL CHECK (lock_type IN (
                        'table', 'row', 'advisory', 'schema'
                    )),
    schema_name     TEXT NOT NULL,
    table_name      TEXT NOT NULL,
    row_id          TEXT,
    -- Wer hält die Sperre
    holder_role     TEXT NOT NULL DEFAULT current_user,
    holder_pid      INTEGER NOT NULL DEFAULT pg_backend_pid(),
    -- Priorität: Niedrigere Nummer = höhere Priorität
    -- Hardware-Treiber (1-3) > System (4-6) > LLM (7-9)
    priority        SMALLINT NOT NULL DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
    -- Timeout
    expires_at      TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '30 seconds',
    -- Status
    state           TEXT NOT NULL DEFAULT 'active' CHECK (state IN (
                        'active', 'waiting', 'released', 'timed_out'
                    )),
    released_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_locks_active ON dbai_system.lock_registry(state)
    WHERE state IN ('active', 'waiting');
CREATE INDEX IF NOT EXISTS idx_locks_holder ON dbai_system.lock_registry(holder_pid);
CREATE INDEX IF NOT EXISTS idx_locks_table ON dbai_system.lock_registry(schema_name, table_name);
CREATE INDEX IF NOT EXISTS idx_locks_expires ON dbai_system.lock_registry(expires_at)
    WHERE state = 'active';

-- =============================================================================
-- Prioritäts-basiertes Locking
-- Hardware-Treiber (Prio 1-3) schlagen immer KI (Prio 7-9)
-- =============================================================================
CREATE OR REPLACE FUNCTION dbai_system.acquire_lock(
    p_schema TEXT,
    p_table TEXT,
    p_row_id TEXT DEFAULT NULL,
    p_priority SMALLINT DEFAULT 5,
    p_timeout_seconds INTEGER DEFAULT 30
) RETURNS BIGINT AS $$
DECLARE
    v_lock_id BIGINT;
    v_blocking RECORD;
    v_lock_key BIGINT;
BEGIN
    -- Advisory Lock Key aus Schema+Tabelle+Row generieren
    v_lock_key := hashtext(p_schema || '.' || p_table || COALESCE('.' || p_row_id, ''));

    -- Prüfe ob ein Lock mit niedrigerer Priorität (= wichtiger) existiert
    SELECT INTO v_blocking *
    FROM dbai_system.lock_registry
    WHERE schema_name = p_schema
      AND table_name = p_table
      AND (p_row_id IS NULL OR row_id = p_row_id)
      AND state = 'active'
      AND expires_at > NOW()
    ORDER BY priority ASC
    LIMIT 1;

    IF v_blocking IS NOT NULL THEN
        IF v_blocking.priority < p_priority THEN
            -- Höher priorisierter Lock existiert — warten
            INSERT INTO dbai_system.lock_registry
                (lock_type, schema_name, table_name, row_id,
                 priority, state, expires_at)
            VALUES
                ('advisory', p_schema, p_table, p_row_id,
                 p_priority, 'waiting',
                 NOW() + (p_timeout_seconds || ' seconds')::INTERVAL)
            RETURNING id INTO v_lock_id;

            -- Advisory Lock versuchen (blockierend, mit Timeout)
            IF pg_try_advisory_lock(v_lock_key) THEN
                UPDATE dbai_system.lock_registry
                SET state = 'active' WHERE id = v_lock_id;
            ELSE
                UPDATE dbai_system.lock_registry
                SET state = 'timed_out' WHERE id = v_lock_id;
                RAISE EXCEPTION 'Lock-Timeout: %.%.% (blockiert von PID %)',
                    p_schema, p_table, COALESCE(p_row_id, '*'),
                    v_blocking.holder_pid;
            END IF;
        ELSE
            -- Wir haben höhere Priorität — vorhandenen Lock verdrängen
            UPDATE dbai_system.lock_registry
            SET state = 'released', released_at = NOW()
            WHERE id = v_blocking.id;

            -- Advisory Lock übernehmen
            PERFORM pg_advisory_unlock(v_lock_key);
            PERFORM pg_advisory_lock(v_lock_key);

            INSERT INTO dbai_system.lock_registry
                (lock_type, schema_name, table_name, row_id,
                 priority, state, expires_at)
            VALUES
                ('advisory', p_schema, p_table, p_row_id,
                 p_priority, 'active',
                 NOW() + (p_timeout_seconds || ' seconds')::INTERVAL)
            RETURNING id INTO v_lock_id;
        END IF;
    ELSE
        -- Kein bestehender Lock — direkt aquirieren
        PERFORM pg_advisory_lock(v_lock_key);

        INSERT INTO dbai_system.lock_registry
            (lock_type, schema_name, table_name, row_id,
             priority, state, expires_at)
        VALUES
            ('advisory', p_schema, p_table, p_row_id,
             p_priority, 'active',
             NOW() + (p_timeout_seconds || ' seconds')::INTERVAL)
        RETURNING id INTO v_lock_id;
    END IF;

    RETURN v_lock_id;
END;
$$ LANGUAGE plpgsql;

-- Lock freigeben
CREATE OR REPLACE FUNCTION dbai_system.release_lock(p_lock_id BIGINT)
RETURNS BOOLEAN AS $$
DECLARE
    v_lock RECORD;
    v_lock_key BIGINT;
BEGIN
    SELECT * INTO v_lock FROM dbai_system.lock_registry
    WHERE id = p_lock_id AND state = 'active';

    IF v_lock IS NULL THEN
        RETURN FALSE;
    END IF;

    v_lock_key := hashtext(v_lock.schema_name || '.' || v_lock.table_name
                          || COALESCE('.' || v_lock.row_id, ''));

    PERFORM pg_advisory_unlock(v_lock_key);

    UPDATE dbai_system.lock_registry
    SET state = 'released', released_at = NOW()
    WHERE id = p_lock_id;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Automatische abgelaufene Locks bereinigen
-- =============================================================================
CREATE OR REPLACE FUNCTION dbai_system.cleanup_expired_locks()
RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER;
    v_lock RECORD;
    v_lock_key BIGINT;
BEGIN
    v_count := 0;

    FOR v_lock IN
        SELECT * FROM dbai_system.lock_registry
        WHERE state = 'active' AND expires_at < NOW()
    LOOP
        v_lock_key := hashtext(v_lock.schema_name || '.' || v_lock.table_name
                              || COALESCE('.' || v_lock.row_id, ''));

        -- Advisory Lock freigeben (falls noch gehalten)
        BEGIN
            PERFORM pg_advisory_unlock(v_lock_key);
        EXCEPTION WHEN OTHERS THEN
            -- Lock war bereits freigegeben
            NULL;
        END;

        UPDATE dbai_system.lock_registry
        SET state = 'timed_out', released_at = NOW()
        WHERE id = v_lock.id;

        v_count := v_count + 1;
    END LOOP;

    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Deadlock-Erkennung: Zirkuläre Abhängigkeiten finden
-- =============================================================================
CREATE OR REPLACE FUNCTION dbai_system.detect_deadlocks()
RETURNS TABLE (
    pid1 INTEGER,
    pid2 INTEGER,
    table1 TEXT,
    table2 TEXT,
    recommendation TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        l1.holder_pid,
        l2.holder_pid,
        (l1.schema_name || '.' || l1.table_name)::TEXT,
        (l2.schema_name || '.' || l2.table_name)::TEXT,
        CASE
            WHEN l1.priority < l2.priority THEN
                format('PID %s hat höhere Priorität — PID %s sollte warten',
                       l1.holder_pid, l2.holder_pid)
            WHEN l1.priority > l2.priority THEN
                format('PID %s hat höhere Priorität — PID %s sollte warten',
                       l2.holder_pid, l1.holder_pid)
            ELSE
                format('Gleiche Priorität — älterer Lock (PID %s) behält Vorrang',
                       CASE WHEN l1.ts < l2.ts THEN l1.holder_pid
                            ELSE l2.holder_pid END)
        END
    FROM dbai_system.lock_registry l1
    JOIN dbai_system.lock_registry l2
        ON l1.holder_pid != l2.holder_pid
        AND l1.state = 'active'
        AND l2.state = 'waiting'
    WHERE l1.schema_name = l2.schema_name
      AND l1.table_name = l2.table_name;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Prioritäts-Definitionen als Konstanten
-- =============================================================================
INSERT INTO dbai_core.config (key, value, category, description, is_readonly, read_roles) VALUES
    ('sync.priority.kernel', '1'::JSONB, 'sync',
     'Höchste Priorität: Kernel-Operationen', TRUE, ARRAY['dbai_system']),
    ('sync.priority.hardware_driver', '2'::JSONB, 'sync',
     'Hardware-Treiber Priorität', TRUE, ARRAY['dbai_system']),
    ('sync.priority.storage', '3'::JSONB, 'sync',
     'Storage-Operationen Priorität', TRUE, ARRAY['dbai_system']),
    ('sync.priority.system_monitor', '4'::JSONB, 'sync',
     'System-Monitoring Priorität', TRUE, ARRAY['dbai_system']),
    ('sync.priority.event_handler', '5'::JSONB, 'sync',
     'Event-Handler Priorität', TRUE, ARRAY['dbai_system']),
    ('sync.priority.recovery', '6'::JSONB, 'sync',
     'Recovery-Operationen Priorität', TRUE, ARRAY['dbai_system']),
    ('sync.priority.llm_read', '7'::JSONB, 'sync',
     'LLM Lese-Operationen Priorität', TRUE, ARRAY['dbai_system', 'dbai_llm']),
    ('sync.priority.llm_write', '8'::JSONB, 'sync',
     'LLM Schreib-Operationen Priorität', TRUE, ARRAY['dbai_system', 'dbai_llm']),
    ('sync.priority.user_task', '9'::JSONB, 'sync',
     'Benutzer-Aufgaben Priorität', TRUE, ARRAY['dbai_system', 'dbai_llm']),
    ('sync.priority.background', '10'::JSONB, 'sync',
     'Niedrigste Priorität: Hintergrund-Aufgaben', TRUE, ARRAY['dbai_system'])
ON CONFLICT DO NOTHING;
