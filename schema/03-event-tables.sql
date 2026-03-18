-- =============================================================================
-- DBAI Schema 03: Event-Tabellen
-- Hardware-Interrupts und System-Events als INSERT-Befehle
-- Der Hardware-Interrupt-Handler schreibt hier hinein
-- =============================================================================

-- Haupt-Event-Tabelle: Alle Hardware- und System-Events
CREATE TABLE IF NOT EXISTS dbai_event.events (
    id              BIGSERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type      TEXT NOT NULL CHECK (event_type IN (
                        'keyboard', 'mouse', 'network', 'disk',
                        'usb', 'power', 'thermal', 'timer',
                        'process', 'system', 'error', 'llm'
                    )),
    source          TEXT NOT NULL,          -- z.B. 'eth0', 'sda', 'keyboard0'
    priority        SMALLINT NOT NULL DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
    payload         JSONB NOT NULL DEFAULT '{}',
    processed       BOOLEAN NOT NULL DEFAULT FALSE,
    processed_by    TEXT,
    processed_at    TIMESTAMPTZ,
    -- Append-Only: Diese Spalte verhindert Updates
    is_immutable    BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_events_ts ON dbai_event.events(ts DESC);
CREATE INDEX IF NOT EXISTS idx_events_type ON dbai_event.events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_unprocessed ON dbai_event.events(processed) WHERE processed = FALSE;
CREATE INDEX IF NOT EXISTS idx_events_priority ON dbai_event.events(priority);
CREATE INDEX IF NOT EXISTS idx_events_payload ON dbai_event.events USING GIN(payload);

-- Schutz: Events dürfen nicht gelöscht oder inhaltlich geändert werden
-- Nur das 'processed' Flag darf gesetzt werden
CREATE OR REPLACE FUNCTION dbai_event.protect_events()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Events dürfen nicht gelöscht werden (Append-Only)';
    END IF;
    IF TG_OP = 'UPDATE' THEN
        -- Nur processed-Flag darf geändert werden
        IF NEW.event_type != OLD.event_type OR
           NEW.source != OLD.source OR
           NEW.payload != OLD.payload OR
           NEW.ts != OLD.ts THEN
            RAISE EXCEPTION 'Event-Daten sind unveränderlich (Append-Only)';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_events_protect ON dbai_event.events;
CREATE TRIGGER trg_events_protect
    BEFORE UPDATE OR DELETE ON dbai_event.events
    FOR EACH ROW EXECUTE FUNCTION dbai_event.protect_events();

-- =============================================================================
-- Tastatur-Events (spezifisch)
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_event.keyboard (
    id              BIGSERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    key_code        INTEGER NOT NULL,
    key_name        TEXT,
    action          TEXT NOT NULL CHECK (action IN ('press', 'release', 'repeat')),
    modifiers       TEXT[] DEFAULT '{}',    -- ['ctrl', 'shift', 'alt']
    event_id        BIGINT REFERENCES dbai_event.events(id)
);

CREATE INDEX IF NOT EXISTS idx_keyboard_ts ON dbai_event.keyboard(ts DESC);

-- =============================================================================
-- Netzwerk-Events
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_event.network (
    id              BIGSERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    interface       TEXT NOT NULL,
    event_subtype   TEXT NOT NULL CHECK (event_subtype IN (
                        'packet_in', 'packet_out', 'connect',
                        'disconnect', 'error', 'dns_resolve'
                    )),
    src_addr        INET,
    dst_addr        INET,
    src_port        INTEGER,
    dst_port        INTEGER,
    protocol        TEXT,
    size_bytes      INTEGER,
    event_id        BIGINT REFERENCES dbai_event.events(id)
);

CREATE INDEX IF NOT EXISTS idx_net_events_ts ON dbai_event.network(ts DESC);
CREATE INDEX IF NOT EXISTS idx_net_events_iface ON dbai_event.network(interface);

-- =============================================================================
-- Power/Strom-Events
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_event.power (
    id              BIGSERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_subtype   TEXT NOT NULL CHECK (event_subtype IN (
                        'ac_connected', 'ac_disconnected',
                        'battery_low', 'battery_critical',
                        'ups_active', 'shutdown_initiated',
                        'hibernate', 'wake'
                    )),
    battery_percent REAL,
    voltage         REAL,
    wattage         REAL,
    event_id        BIGINT REFERENCES dbai_event.events(id)
);

CREATE INDEX IF NOT EXISTS idx_power_ts ON dbai_event.power(ts DESC);

-- =============================================================================
-- Event-Dispatcher Funktion: Verteilt Events an die richtigen Unter-Tabellen
-- =============================================================================
CREATE OR REPLACE FUNCTION dbai_event.dispatch_event(
    p_event_type TEXT,
    p_source TEXT,
    p_priority SMALLINT DEFAULT 5,
    p_payload JSONB DEFAULT '{}'
) RETURNS BIGINT AS $$
DECLARE
    v_event_id BIGINT;
BEGIN
    -- Haupt-Event einfügen
    INSERT INTO dbai_event.events (event_type, source, priority, payload)
    VALUES (p_event_type, p_source, p_priority, p_payload)
    RETURNING id INTO v_event_id;

    -- Event in Journal schreiben (Append-Only, separater Schritt)
    INSERT INTO dbai_journal.event_log (event_id, event_type, source, payload)
    VALUES (v_event_id, p_event_type, p_source, p_payload);

    RETURN v_event_id;
END;
$$ LANGUAGE plpgsql;
