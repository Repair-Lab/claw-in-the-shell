-- =============================================================================
-- DBAI Schema 07: Row-Level Security (RLS)
-- Die KI darf nur Zeilen sehen, die sie für ihre Aufgabe braucht
-- Keine Root-Passwörter — granulare Zugriffskontrolle
-- =============================================================================

-- =============================================================================
-- RLS für Core-Tabellen
-- =============================================================================

-- Objekt-Registry: LLM sieht nur Objekte die ihm zugewiesen sind
ALTER TABLE dbai_core.objects ENABLE ROW LEVEL SECURITY;

CREATE POLICY objects_system_full ON dbai_core.objects
    FOR ALL TO dbai_system
    USING (TRUE);

CREATE POLICY objects_llm_restricted ON dbai_core.objects
    FOR SELECT TO dbai_llm
    USING (
        owner_role = 'dbai_llm'
        OR owner_role = 'public'
        OR id IN (
            SELECT (value->>'object_id')::UUID
            FROM dbai_core.config
            WHERE key LIKE 'llm.accessible_objects.%'
        )
    );

-- Prozess-Tabelle: LLM sieht nur eigene Prozesse
ALTER TABLE dbai_core.processes ENABLE ROW LEVEL SECURITY;

CREATE POLICY processes_system_full ON dbai_core.processes
    FOR ALL TO dbai_system
    USING (TRUE);

CREATE POLICY processes_llm_own ON dbai_core.processes
    FOR SELECT TO dbai_llm
    USING (process_type = 'llm' OR process_type = 'user_task');

CREATE POLICY processes_monitor_read ON dbai_core.processes
    FOR SELECT TO dbai_monitor
    USING (TRUE);

-- Konfigurations-Tabelle: LLM sieht nur freigegebene Configs
ALTER TABLE dbai_core.config ENABLE ROW LEVEL SECURITY;

CREATE POLICY config_system_full ON dbai_core.config
    FOR ALL TO dbai_system
    USING (TRUE);

CREATE POLICY config_llm_restricted ON dbai_core.config
    FOR SELECT TO dbai_llm
    USING ('dbai_llm' = ANY(read_roles) OR 'public' = ANY(read_roles));

-- Treiber: LLM hat keinen Zugriff
ALTER TABLE dbai_core.drivers ENABLE ROW LEVEL SECURITY;

CREATE POLICY drivers_system_full ON dbai_core.drivers
    FOR ALL TO dbai_system
    USING (TRUE);

CREATE POLICY drivers_monitor_read ON dbai_core.drivers
    FOR SELECT TO dbai_monitor
    USING (TRUE);

-- =============================================================================
-- RLS für System-Tabellen
-- =============================================================================

ALTER TABLE dbai_system.cpu ENABLE ROW LEVEL SECURITY;
CREATE POLICY cpu_system ON dbai_system.cpu FOR ALL TO dbai_system USING (TRUE);
CREATE POLICY cpu_monitor ON dbai_system.cpu FOR SELECT TO dbai_monitor USING (TRUE);

ALTER TABLE dbai_system.memory ENABLE ROW LEVEL SECURITY;
CREATE POLICY memory_system ON dbai_system.memory FOR ALL TO dbai_system USING (TRUE);
CREATE POLICY memory_monitor ON dbai_system.memory FOR SELECT TO dbai_monitor USING (TRUE);

ALTER TABLE dbai_system.disk ENABLE ROW LEVEL SECURITY;
CREATE POLICY disk_system ON dbai_system.disk FOR ALL TO dbai_system USING (TRUE);
CREATE POLICY disk_monitor ON dbai_system.disk FOR SELECT TO dbai_monitor USING (TRUE);

ALTER TABLE dbai_system.temperature ENABLE ROW LEVEL SECURITY;
CREATE POLICY temp_system ON dbai_system.temperature FOR ALL TO dbai_system USING (TRUE);
CREATE POLICY temp_monitor ON dbai_system.temperature FOR SELECT TO dbai_monitor USING (TRUE);

ALTER TABLE dbai_system.network ENABLE ROW LEVEL SECURITY;
CREATE POLICY network_system ON dbai_system.network FOR ALL TO dbai_system USING (TRUE);
CREATE POLICY network_monitor ON dbai_system.network FOR SELECT TO dbai_monitor USING (TRUE);

-- =============================================================================
-- RLS für Vektor-Tabellen
-- =============================================================================

ALTER TABLE dbai_vector.memories ENABLE ROW LEVEL SECURITY;

CREATE POLICY memories_system_full ON dbai_vector.memories
    FOR ALL TO dbai_system
    USING (TRUE);

-- LLM darf nur eigene Erinnerungen lesen und erstellen
CREATE POLICY memories_llm_own ON dbai_vector.memories
    FOR SELECT TO dbai_llm
    USING (created_by = 'dbai_llm');

CREATE POLICY memories_llm_insert ON dbai_vector.memories
    FOR INSERT TO dbai_llm
    WITH CHECK (created_by = 'dbai_llm');

-- =============================================================================
-- RLS für Journal (Append-Only + Lesezugriff)
-- =============================================================================

ALTER TABLE dbai_journal.change_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY journal_system ON dbai_journal.change_log
    FOR ALL TO dbai_system USING (TRUE);

CREATE POLICY journal_recovery ON dbai_journal.change_log
    FOR SELECT TO dbai_recovery USING (TRUE);

-- LLM darf Journal NICHT lesen (Sicherheit)

-- =============================================================================
-- Audit-Tabelle: Wer hat wann auf was zugegriffen
-- =============================================================================
CREATE TABLE dbai_core.audit_log (
    id              BIGSERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_role       TEXT NOT NULL DEFAULT current_user,
    action          TEXT NOT NULL,
    schema_name     TEXT,
    table_name      TEXT,
    row_count       INTEGER,
    query_hash      TEXT,
    client_addr     INET,
    duration_ms     REAL
);

-- Audit-Log ist Append-Only
ALTER TABLE dbai_core.audit_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY audit_system ON dbai_core.audit_log
    FOR ALL TO dbai_system USING (TRUE);

CREATE POLICY audit_recovery ON dbai_core.audit_log
    FOR SELECT TO dbai_recovery USING (TRUE);

CREATE OR REPLACE FUNCTION dbai_core.protect_audit_log()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP IN ('DELETE', 'UPDATE') THEN
        RAISE EXCEPTION 'Audit-Log ist unveränderlich (Append-Only)';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_protect
    BEFORE UPDATE OR DELETE ON dbai_core.audit_log
    FOR EACH ROW EXECUTE FUNCTION dbai_core.protect_audit_log();
