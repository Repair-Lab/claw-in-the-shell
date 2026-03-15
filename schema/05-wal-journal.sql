-- =============================================================================
-- DBAI Schema 05: WAL-Journal (Append-Only)
-- Fahrtenbuch aller Änderungen — NIEMALS löschen oder überschreiben
-- Neue Daten werden NUR unten angehängt
-- =============================================================================

-- Haupt-Journal: Jede Datenänderung wird hier protokolliert
CREATE TABLE dbai_journal.change_log (
    id              BIGSERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Welches Schema und welche Tabelle wurde geändert
    schema_name     TEXT NOT NULL,
    table_name      TEXT NOT NULL,
    -- Art der Änderung
    operation       TEXT NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    -- Betroffene Zeilen-ID (falls UUID)
    row_id          TEXT,
    -- Vorheriger Zustand (bei UPDATE/DELETE)
    old_data        JSONB,
    -- Neuer Zustand (bei INSERT/UPDATE)
    new_data        JSONB,
    -- Wer hat die Änderung durchgeführt
    changed_by      TEXT NOT NULL DEFAULT current_user,
    -- Transaktions-ID für Gruppierung
    transaction_id  BIGINT DEFAULT txid_current(),
    -- Prüfsumme für Integritätsvalidierung
    checksum        TEXT
);

-- Append-Only: Absoluter Schutz gegen Löschen und Ändern
CREATE OR REPLACE FUNCTION dbai_journal.protect_journal()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Journal-Einträge dürfen NIEMALS gelöscht werden (Append-Only)';
    END IF;
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'Journal-Einträge dürfen NIEMALS geändert werden (Append-Only)';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_journal_protect
    BEFORE UPDATE OR DELETE ON dbai_journal.change_log
    FOR EACH ROW EXECUTE FUNCTION dbai_journal.protect_journal();

CREATE INDEX idx_journal_ts ON dbai_journal.change_log(ts DESC);
CREATE INDEX idx_journal_table ON dbai_journal.change_log(schema_name, table_name);
CREATE INDEX idx_journal_txid ON dbai_journal.change_log(transaction_id);

-- =============================================================================
-- Event-Journal: Alle Events (Append-Only Kopie)
-- =============================================================================
CREATE TABLE dbai_journal.event_log (
    id              BIGSERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_id        BIGINT NOT NULL,
    event_type      TEXT NOT NULL,
    source          TEXT NOT NULL,
    payload         JSONB NOT NULL DEFAULT '{}'
);

CREATE TRIGGER trg_event_log_protect
    BEFORE UPDATE OR DELETE ON dbai_journal.event_log
    FOR EACH ROW EXECUTE FUNCTION dbai_journal.protect_journal();

CREATE INDEX idx_event_log_ts ON dbai_journal.event_log(ts DESC);
CREATE INDEX idx_event_log_type ON dbai_journal.event_log(event_type);

-- =============================================================================
-- System-Status-Journal: Jede Sekunde ein Statusbericht (PITR)
-- =============================================================================
CREATE TABLE dbai_journal.system_snapshots (
    id              BIGSERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Komprimierter System-Snapshot
    snapshot        JSONB NOT NULL,
    -- WAL-Position zu diesem Zeitpunkt
    wal_lsn         PG_LSN,
    -- Prüfsumme
    checksum        TEXT NOT NULL,
    -- Snapshot-Typ
    snapshot_type   TEXT NOT NULL DEFAULT 'periodic' CHECK (snapshot_type IN (
                        'periodic', 'pre_change', 'post_change',
                        'checkpoint', 'manual', 'panic'
                    ))
);

CREATE TRIGGER trg_snapshots_protect
    BEFORE UPDATE OR DELETE ON dbai_journal.system_snapshots
    FOR EACH ROW EXECUTE FUNCTION dbai_journal.protect_journal();

CREATE INDEX idx_snapshots_ts ON dbai_journal.system_snapshots(ts DESC);
CREATE INDEX idx_snapshots_type ON dbai_journal.system_snapshots(snapshot_type);

-- =============================================================================
-- Automatischer Change-Log Trigger für alle Core-Tabellen
-- =============================================================================
CREATE OR REPLACE FUNCTION dbai_journal.log_change()
RETURNS TRIGGER AS $$
DECLARE
    v_checksum TEXT;
    v_row_id TEXT;
BEGIN
    -- Versuche die ID zu extrahieren
    IF TG_OP = 'DELETE' THEN
        v_row_id := OLD.id::TEXT;
    ELSE
        v_row_id := NEW.id::TEXT;
    END IF;

    -- Prüfsumme berechnen
    IF TG_OP = 'INSERT' THEN
        v_checksum := md5(row_to_json(NEW)::TEXT);
        INSERT INTO dbai_journal.change_log
            (schema_name, table_name, operation, row_id, new_data, checksum)
        VALUES
            (TG_TABLE_SCHEMA, TG_TABLE_NAME, 'INSERT', v_row_id,
             row_to_json(NEW)::JSONB, v_checksum);
        RETURN NEW;

    ELSIF TG_OP = 'UPDATE' THEN
        v_checksum := md5(row_to_json(NEW)::TEXT);
        INSERT INTO dbai_journal.change_log
            (schema_name, table_name, operation, row_id, old_data, new_data, checksum)
        VALUES
            (TG_TABLE_SCHEMA, TG_TABLE_NAME, 'UPDATE', v_row_id,
             row_to_json(OLD)::JSONB, row_to_json(NEW)::JSONB, v_checksum);
        RETURN NEW;

    ELSIF TG_OP = 'DELETE' THEN
        v_checksum := md5(row_to_json(OLD)::TEXT);
        INSERT INTO dbai_journal.change_log
            (schema_name, table_name, operation, row_id, old_data, checksum)
        VALUES
            (TG_TABLE_SCHEMA, TG_TABLE_NAME, 'DELETE', v_row_id,
             row_to_json(OLD)::JSONB, v_checksum);
        RETURN OLD;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Change-Log Trigger für Core-Tabellen aktivieren
CREATE TRIGGER trg_objects_journal
    AFTER INSERT OR UPDATE OR DELETE ON dbai_core.objects
    FOR EACH ROW EXECUTE FUNCTION dbai_journal.log_change();

CREATE TRIGGER trg_processes_journal
    AFTER INSERT OR UPDATE OR DELETE ON dbai_core.processes
    FOR EACH ROW EXECUTE FUNCTION dbai_journal.log_change();

CREATE TRIGGER trg_config_journal
    AFTER INSERT OR UPDATE OR DELETE ON dbai_core.config
    FOR EACH ROW EXECUTE FUNCTION dbai_journal.log_change();

CREATE TRIGGER trg_drivers_journal
    AFTER INSERT OR UPDATE OR DELETE ON dbai_core.drivers
    FOR EACH ROW EXECUTE FUNCTION dbai_journal.log_change();

-- =============================================================================
-- PITR-Funktion: System zu einem bestimmten Zeitpunkt wiederherstellen
-- =============================================================================
CREATE OR REPLACE FUNCTION dbai_journal.find_nearest_snapshot(
    target_time TIMESTAMPTZ
) RETURNS TABLE (
    snapshot_id BIGINT,
    snapshot_ts TIMESTAMPTZ,
    wal_lsn PG_LSN,
    snapshot JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT s.id, s.ts, s.wal_lsn, s.snapshot
    FROM dbai_journal.system_snapshots s
    WHERE s.ts <= target_time
    ORDER BY s.ts DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Alle Änderungen nach einem bestimmten Zeitpunkt anzeigen
CREATE OR REPLACE FUNCTION dbai_journal.changes_since(
    since_time TIMESTAMPTZ
) RETURNS TABLE (
    change_id BIGINT,
    change_ts TIMESTAMPTZ,
    schema_name TEXT,
    table_name TEXT,
    operation TEXT,
    row_id TEXT,
    old_data JSONB,
    new_data JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT c.id, c.ts, c.schema_name, c.table_name,
           c.operation, c.row_id, c.old_data, c.new_data
    FROM dbai_journal.change_log c
    WHERE c.ts >= since_time
    ORDER BY c.ts ASC;
END;
$$ LANGUAGE plpgsql;
