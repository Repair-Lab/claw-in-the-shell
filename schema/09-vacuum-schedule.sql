-- =============================================================================
-- DBAI Schema 09: Vacuum-Scheduling
-- Automatische Bereinigung — ohne diese füllt sich der Speicher in Tagen
-- =============================================================================

-- Vacuum-Status-Tabelle: Dokumentiert alle Vacuum-Läufe
CREATE TABLE dbai_system.vacuum_log (
    id              BIGSERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    schema_name     TEXT NOT NULL,
    table_name      TEXT NOT NULL,
    vacuum_type     TEXT NOT NULL CHECK (vacuum_type IN (
                        'auto', 'manual', 'full', 'analyze'
                    )),
    -- Statistiken
    dead_tuples_before  BIGINT,
    dead_tuples_after   BIGINT,
    pages_removed       INTEGER,
    duration_ms         REAL,
    -- Speicher-Einsparung
    space_freed_mb      REAL,
    success             BOOLEAN NOT NULL DEFAULT TRUE,
    error_message       TEXT
);

CREATE INDEX idx_vacuum_log_ts ON dbai_system.vacuum_log(ts DESC);
CREATE INDEX idx_vacuum_log_table ON dbai_system.vacuum_log(schema_name, table_name);

-- =============================================================================
-- Tabellen-spezifische Vacuum-Konfiguration
-- =============================================================================
CREATE TABLE dbai_system.vacuum_config (
    id              SERIAL PRIMARY KEY,
    schema_name     TEXT NOT NULL,
    table_name      TEXT NOT NULL,
    -- Wie oft soll Vacuum laufen (Cron-Ausdruck)
    schedule        TEXT NOT NULL DEFAULT '*/30 * * * *',  -- Alle 30 Min
    -- Schwellwerte
    vacuum_threshold    INTEGER NOT NULL DEFAULT 50,
    analyze_threshold   INTEGER NOT NULL DEFAULT 50,
    scale_factor        REAL NOT NULL DEFAULT 0.1,
    -- Priorität: System-Tabellen haben höhere Priorität
    priority            SMALLINT NOT NULL DEFAULT 5,
    enabled             BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE(schema_name, table_name)
);

-- Standard-Vacuum-Konfigurationen
INSERT INTO dbai_system.vacuum_config
    (schema_name, table_name, schedule, vacuum_threshold, priority) VALUES
    -- System-Tabellen: Aggressives Vacuum (viele kurzlebige Daten)
    ('dbai_system', 'cpu', '*/10 * * * *', 100, 2),
    ('dbai_system', 'memory', '*/10 * * * *', 100, 2),
    ('dbai_system', 'disk', '*/30 * * * *', 50, 3),
    ('dbai_system', 'temperature', '*/15 * * * *', 100, 2),
    ('dbai_system', 'network', '*/10 * * * *', 100, 2),
    -- Event-Tabellen: Mäßiges Vacuum
    ('dbai_event', 'events', '*/30 * * * *', 200, 4),
    ('dbai_event', 'keyboard', '*/30 * * * *', 500, 5),
    ('dbai_event', 'network', '*/30 * * * *', 200, 4),
    -- Core-Tabellen: Konservatives Vacuum
    ('dbai_core', 'objects', '0 * * * *', 50, 5),
    ('dbai_core', 'processes', '*/30 * * * *', 100, 3),
    -- Vektor-Tabellen: Selten (wenige Löschungen)
    ('dbai_vector', 'memories', '0 */6 * * *', 50, 6),
    -- Journal: KEIN Vacuum (Append-Only, aber Analyze erlaubt)
    ('dbai_journal', 'change_log', '0 */12 * * *', 99999999, 8),
    ('dbai_journal', 'event_log', '0 */12 * * *', 99999999, 8);

-- =============================================================================
-- Intelligente Vacuum-Funktion
-- Prüft welche Tabellen Vacuum benötigen und führt es priorisiert aus
-- =============================================================================
CREATE OR REPLACE FUNCTION dbai_system.smart_vacuum()
RETURNS TABLE (
    vacuumed_table TEXT,
    dead_tuples BIGINT,
    action_taken TEXT
) AS $$
DECLARE
    v_record RECORD;
    v_dead_tuples BIGINT;
    v_start_time TIMESTAMPTZ;
    v_duration REAL;
BEGIN
    FOR v_record IN
        SELECT vc.schema_name, vc.table_name, vc.vacuum_threshold, vc.priority
        FROM dbai_system.vacuum_config vc
        WHERE vc.enabled = TRUE
        ORDER BY vc.priority ASC
    LOOP
        -- Dead tuples zählen
        SELECT n_dead_tup INTO v_dead_tuples
        FROM pg_stat_user_tables
        WHERE schemaname = v_record.schema_name
          AND relname = v_record.table_name;

        IF v_dead_tuples IS NOT NULL AND v_dead_tuples > v_record.vacuum_threshold THEN
            v_start_time := clock_timestamp();

            -- Vacuum + Analyze ausführen
            EXECUTE format('VACUUM ANALYZE %I.%I',
                          v_record.schema_name, v_record.table_name);

            v_duration := EXTRACT(EPOCH FROM (clock_timestamp() - v_start_time)) * 1000;

            -- Vacuum-Log schreiben
            INSERT INTO dbai_system.vacuum_log
                (schema_name, table_name, vacuum_type,
                 dead_tuples_before, duration_ms)
            VALUES
                (v_record.schema_name, v_record.table_name, 'auto',
                 v_dead_tuples, v_duration);

            vacuumed_table := v_record.schema_name || '.' || v_record.table_name;
            dead_tuples := v_dead_tuples;
            action_taken := format('VACUUM ANALYZE (%.1fms)', v_duration);
            RETURN NEXT;
        END IF;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Speicher-Überwachung: Warnt wenn DB zu groß wird
-- =============================================================================
CREATE OR REPLACE FUNCTION dbai_system.check_database_size()
RETURNS TABLE (
    schema_name TEXT,
    table_name TEXT,
    size_mb REAL,
    row_count BIGINT,
    dead_tuples BIGINT,
    bloat_percent REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        s.schemaname::TEXT,
        s.relname::TEXT,
        pg_total_relation_size(s.schemaname || '.' || s.relname)::REAL / (1024*1024),
        s.n_live_tup,
        s.n_dead_tup,
        CASE WHEN s.n_live_tup > 0
            THEN (s.n_dead_tup::REAL / s.n_live_tup * 100)
            ELSE 0
        END
    FROM pg_stat_user_tables s
    WHERE s.schemaname LIKE 'dbai_%'
    ORDER BY pg_total_relation_size(s.schemaname || '.' || s.relname) DESC;
END;
$$ LANGUAGE plpgsql;
