-- =============================================================================
-- DBAI Schema 75: Security-AI-Integration
-- Verbindet das Security-Immunsystem mit dem Ghost/LLM-System
-- Der Security-Monitor-Ghost analysiert Events, bewertet Bedrohungen,
-- leitet autonome Gegenmaßnahmen ein.
-- =============================================================================

-- Changelog
INSERT INTO dbai_knowledge.changelog (version, change_type, title, description) VALUES
('0.15.0', 'feature', 'Security-AI-Integration', 'Ghost-Monitor ↔ Immunsystem Brücke');

-- =============================================================================
-- 1. SECURITY AI TASKS — KI-gesteuerte Sicherheitsanalysen
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_security.ai_tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_type       TEXT NOT NULL
                    CHECK (task_type IN (
                        'threat_analysis',       -- Bedrohungsanalyse
                        'vuln_assessment',       -- Schwachstellenbewertung
                        'incident_response',     -- Incident-Analyse + Empfehlung
                        'baseline_audit',        -- Baseline-Compliance-Prüfung
                        'anomaly_detection',     -- Anomalie-Erkennung
                        'log_analysis',          -- Log-Analyse (Auth, IDS)
                        'network_forensics',     -- Netzwerk-Forensik
                        'risk_scoring',          -- Risikobewertung
                        'policy_recommendation', -- Policy-Empfehlung
                        'periodic_report'        -- Periodischer Sicherheitsbericht
                    )),
    -- Kontext: Was soll analysiert werden?
    input_data      JSONB NOT NULL DEFAULT '{}'::JSONB,
    -- Referenz auf die LLM Task-Queue
    llm_task_id     UUID,
    -- Ergebnis der KI-Analyse
    output_data     JSONB,
    ai_assessment   TEXT,            -- Freitext-Bewertung der KI
    risk_level      TEXT CHECK (risk_level IN ('critical', 'high', 'medium', 'low', 'info')),
    confidence      DOUBLE PRECISION CHECK (confidence BETWEEN 0.0 AND 1.0),
    recommended_actions JSONB,       -- Array von empfohlenen Maßnahmen
    auto_executed   BOOLEAN NOT NULL DEFAULT FALSE,
    -- Status
    state           TEXT NOT NULL DEFAULT 'pending'
                    CHECK (state IN ('pending', 'processing', 'completed', 'failed', 'cancelled')),
    error_message   TEXT,
    -- Auslöser
    trigger_source  TEXT NOT NULL DEFAULT 'manual'
                    CHECK (trigger_source IN (
                        'manual', 'scheduled', 'event_trigger', 'threshold', 'anomaly'
                    )),
    triggered_by    TEXT NOT NULL DEFAULT 'system',
    -- Zeitstempel
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    processing_ms   INTEGER
);

CREATE INDEX IF NOT EXISTS idx_security_ai_tasks_state ON dbai_security.ai_tasks(state);
CREATE INDEX IF NOT EXISTS idx_security_ai_tasks_type ON dbai_security.ai_tasks(task_type);
CREATE INDEX IF NOT EXISTS idx_security_ai_tasks_created ON dbai_security.ai_tasks(created_at DESC);

COMMENT ON TABLE dbai_security.ai_tasks IS
    'KI-gesteuerte Sicherheitsanalysen: Der Security-Monitor-Ghost bewertet Bedrohungen und empfiehlt Maßnahmen.';

-- =============================================================================
-- 2. SECURITY AI CONFIG — Konfiguration der KI-gesteuerten Sicherheit
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_security.ai_config (
    key             TEXT PRIMARY KEY,
    value           JSONB NOT NULL,
    description     TEXT,
    category        TEXT NOT NULL DEFAULT 'general'
                    CHECK (category IN (
                        'general', 'auto_response', 'thresholds',
                        'analysis', 'scheduling', 'notifications'
                    )),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by      TEXT NOT NULL DEFAULT 'system'
);

COMMENT ON TABLE dbai_security.ai_config IS
    'Konfiguration der KI-gesteuerten Sicherheit: Schwellenwerte, Auto-Response, Scheduling.';

-- =============================================================================
-- 3. SECURITY AI ANALYSIS LOG — Alle KI-Analysen (Append-Only)
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_security.ai_analysis_log (
    id              BIGSERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    task_id         UUID REFERENCES dbai_security.ai_tasks(id),
    analysis_type   TEXT NOT NULL,
    input_summary   TEXT,
    output_summary  TEXT,
    risk_level      TEXT,
    tokens_used     INTEGER DEFAULT 0,
    model_name      TEXT,
    duration_ms     INTEGER,
    auto_action     TEXT,
    metadata        JSONB DEFAULT '{}'::JSONB
);

CREATE INDEX IF NOT EXISTS idx_security_ai_log_ts ON dbai_security.ai_analysis_log(ts DESC);

-- Append-Only Schutz
CREATE OR REPLACE FUNCTION dbai_security.protect_ai_analysis_log()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'dbai_security.ai_analysis_log ist Append-Only: % verboten', TG_OP;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_protect_ai_analysis_log ON dbai_security.ai_analysis_log;
CREATE TRIGGER trg_protect_ai_analysis_log
    BEFORE UPDATE OR DELETE ON dbai_security.ai_analysis_log
    FOR EACH ROW EXECUTE FUNCTION dbai_security.protect_ai_analysis_log();

-- =============================================================================
-- 4. FUNKTION: Security-AI-Task erstellen
-- =============================================================================

CREATE OR REPLACE FUNCTION dbai_security.create_ai_task(
    p_task_type     TEXT,
    p_input_data    JSONB DEFAULT '{}'::JSONB,
    p_trigger       TEXT DEFAULT 'manual',
    p_triggered_by  TEXT DEFAULT 'system'
)
RETURNS UUID AS $$
DECLARE
    v_task_id UUID;
    v_config  JSONB;
BEGIN
    -- Prüfen ob AI-Analyse aktiviert ist
    SELECT value INTO v_config FROM dbai_security.ai_config WHERE key = 'ai_enabled';
    IF v_config IS NOT NULL AND (v_config)::TEXT = 'false' THEN
        RAISE NOTICE 'Security-AI deaktiviert — Task nicht erstellt';
        RETURN NULL;
    END IF;

    INSERT INTO dbai_security.ai_tasks (task_type, input_data, trigger_source, triggered_by)
    VALUES (p_task_type, p_input_data, p_trigger, p_triggered_by)
    RETURNING id INTO v_task_id;

    -- NOTIFY an den Security-AI-Worker
    PERFORM pg_notify('security_ai_task', jsonb_build_object(
        'task_id', v_task_id,
        'task_type', p_task_type,
        'trigger', p_trigger
    )::TEXT);

    RETURN v_task_id;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- 5. TRIGGER: Automatische AI-Analyse bei kritischen Events
-- =============================================================================

-- Bei kritischen Intrusion-Events
CREATE OR REPLACE FUNCTION dbai_security.trigger_ai_on_intrusion()
RETURNS TRIGGER AS $$
DECLARE
    v_threshold INTEGER;
BEGIN
    -- Threshold aus Config laden (default: priority <= 2 = critical)
    SELECT COALESCE((value->>'intrusion_priority_threshold')::INTEGER, 2)
    INTO v_threshold
    FROM dbai_security.ai_config WHERE key = 'auto_analysis_thresholds';

    IF NEW.priority <= v_threshold THEN
        PERFORM dbai_security.create_ai_task(
            'incident_response',
            jsonb_build_object(
                'intrusion_id', NEW.id,
                'event_type', NEW.event_type,
                'source_ip', NEW.source_ip,
                'dest_ip', NEW.dest_ip,
                'signature_name', NEW.signature_name,
                'classification', NEW.classification,
                'priority', NEW.priority,
                'detected_at', NEW.detected_at
            ),
            'event_trigger',
            'intrusion_detector'
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ai_intrusion_analysis ON dbai_security.intrusion_events;
CREATE TRIGGER trg_ai_intrusion_analysis
    AFTER INSERT ON dbai_security.intrusion_events
    FOR EACH ROW EXECUTE FUNCTION dbai_security.trigger_ai_on_intrusion();

-- Bei kritischen Schwachstellen
CREATE OR REPLACE FUNCTION dbai_security.trigger_ai_on_vulnerability()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.severity IN ('critical', 'high') THEN
        PERFORM dbai_security.create_ai_task(
            'vuln_assessment',
            jsonb_build_object(
                'vuln_id', NEW.id,
                'severity', NEW.severity,
                'category', NEW.category,
                'title', NEW.title,
                'description', NEW.description,
                'affected_target', NEW.affected_target,
                'cve_id', NEW.cve_id,
                'cvss_score', NEW.cvss_score
            ),
            'event_trigger',
            'vuln_scanner'
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ai_vuln_analysis ON dbai_security.vulnerability_findings;
CREATE TRIGGER trg_ai_vuln_analysis
    AFTER INSERT ON dbai_security.vulnerability_findings
    FOR EACH ROW EXECUTE FUNCTION dbai_security.trigger_ai_on_vulnerability();

-- Bei Honeypot-Events (immer analysieren)
CREATE OR REPLACE FUNCTION dbai_security.trigger_ai_on_honeypot()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM dbai_security.create_ai_task(
        'threat_analysis',
        jsonb_build_object(
            'honeypot_id', NEW.id,
            'honeypot_type', NEW.honeypot_type,
            'source_ip', NEW.source_ip,
            'interaction', NEW.interaction,
            'detected_at', NEW.detected_at
        ),
        'event_trigger',
        'honeypot'
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ai_honeypot_analysis ON dbai_security.honeypot_events;
CREATE TRIGGER trg_ai_honeypot_analysis
    AFTER INSERT ON dbai_security.honeypot_events
    FOR EACH ROW EXECUTE FUNCTION dbai_security.trigger_ai_on_honeypot();

-- =============================================================================
-- 6. SECURITY AI STATUS VIEW
-- =============================================================================

CREATE OR REPLACE VIEW dbai_security.vw_ai_status AS
SELECT
    -- Ghost-Status
    (SELECT state FROM dbai_llm.active_ghosts ag
     JOIN dbai_llm.ghost_roles r ON ag.role_id = r.id
     WHERE r.name = 'security') AS ghost_state,
    (SELECT m.name FROM dbai_llm.active_ghosts ag
     JOIN dbai_llm.ghost_roles r ON ag.role_id = r.id
     JOIN dbai_llm.ghost_models m ON ag.model_id = m.id
     WHERE r.name = 'security') AS active_model,
    (SELECT m.display_name FROM dbai_llm.active_ghosts ag
     JOIN dbai_llm.ghost_roles r ON ag.role_id = r.id
     JOIN dbai_llm.ghost_models m ON ag.model_id = m.id
     WHERE r.name = 'security') AS model_display,
    -- Task-Statistiken
    (SELECT COUNT(*) FROM dbai_security.ai_tasks WHERE state = 'pending') AS pending_tasks,
    (SELECT COUNT(*) FROM dbai_security.ai_tasks WHERE state = 'processing') AS processing_tasks,
    (SELECT COUNT(*) FROM dbai_security.ai_tasks WHERE state = 'completed'
     AND completed_at > NOW() - INTERVAL '24 hours') AS completed_24h,
    (SELECT COUNT(*) FROM dbai_security.ai_tasks WHERE auto_executed = TRUE
     AND completed_at > NOW() - INTERVAL '24 hours') AS auto_executed_24h,
    -- Analyse-Stats
    (SELECT COALESCE(SUM(tokens_used), 0) FROM dbai_security.ai_analysis_log
     WHERE ts > NOW() - INTERVAL '24 hours') AS tokens_24h,
    (SELECT COALESCE(AVG(duration_ms), 0)::INTEGER FROM dbai_security.ai_analysis_log
     WHERE ts > NOW() - INTERVAL '24 hours') AS avg_analysis_ms,
    -- Letzte Analyse
    (SELECT ts FROM dbai_security.ai_analysis_log ORDER BY ts DESC LIMIT 1) AS last_analysis_at,
    (SELECT analysis_type FROM dbai_security.ai_analysis_log ORDER BY ts DESC LIMIT 1) AS last_analysis_type;

-- =============================================================================
-- 7. RLS
-- =============================================================================

ALTER TABLE dbai_security.ai_tasks ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS aitasks_system ON dbai_security.ai_tasks;
CREATE POLICY aitasks_system ON dbai_security.ai_tasks FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS aitasks_runtime ON dbai_security.ai_tasks;
CREATE POLICY aitasks_runtime ON dbai_security.ai_tasks FOR ALL TO dbai_runtime USING (TRUE) WITH CHECK (TRUE);

ALTER TABLE dbai_security.ai_config ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS aiconfig_system ON dbai_security.ai_config;
CREATE POLICY aiconfig_system ON dbai_security.ai_config FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS aiconfig_runtime ON dbai_security.ai_config;
CREATE POLICY aiconfig_runtime ON dbai_security.ai_config FOR ALL TO dbai_runtime USING (TRUE) WITH CHECK (TRUE);

ALTER TABLE dbai_security.ai_analysis_log ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ailog_system ON dbai_security.ai_analysis_log;
CREATE POLICY ailog_system ON dbai_security.ai_analysis_log FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS ailog_runtime ON dbai_security.ai_analysis_log;
CREATE POLICY ailog_runtime ON dbai_security.ai_analysis_log FOR SELECT TO dbai_runtime USING (TRUE);

-- Grants
GRANT SELECT, INSERT, UPDATE ON dbai_security.ai_tasks TO dbai_system;
GRANT SELECT, INSERT, UPDATE ON dbai_security.ai_tasks TO dbai_runtime;
GRANT SELECT, INSERT, UPDATE ON dbai_security.ai_config TO dbai_system;
GRANT SELECT, INSERT, UPDATE ON dbai_security.ai_config TO dbai_runtime;
GRANT SELECT, INSERT ON dbai_security.ai_analysis_log TO dbai_system;
GRANT SELECT, INSERT ON dbai_security.ai_analysis_log TO dbai_runtime;
GRANT SELECT ON dbai_security.vw_ai_status TO dbai_system;
GRANT SELECT ON dbai_security.vw_ai_status TO dbai_runtime;
GRANT SELECT ON dbai_security.vw_ai_status TO dbai_monitor;
GRANT USAGE ON SEQUENCE dbai_security.ai_analysis_log_id_seq TO dbai_system;
GRANT USAGE ON SEQUENCE dbai_security.ai_analysis_log_id_seq TO dbai_runtime;

-- =============================================================================
-- 8. SEED: Default-Konfiguration
-- =============================================================================

INSERT INTO dbai_security.ai_config (key, value, description, category) VALUES
('ai_enabled', 'true', 'Security-AI global aktiviert', 'general'),
('auto_response_enabled', 'true', 'Automatische Reaktionen durch KI erlaubt', 'auto_response'),
('auto_ban_enabled', 'true', 'KI darf IPs automatisch bannen', 'auto_response'),
('auto_mitigate_enabled', 'false', 'KI darf Schwachstellen automatisch mitigieren', 'auto_response'),
('max_auto_ban_hours', '24', 'Maximale Auto-Ban-Dauer in Stunden', 'auto_response'),
('auto_analysis_thresholds', '{"intrusion_priority_threshold": 2, "vuln_severity": ["critical","high"], "failed_auth_count": 10}',
 'Schwellenwerte für automatische KI-Analyse', 'thresholds'),
('risk_score_weights', '{"intrusions": 0.3, "vulns": 0.25, "failed_auth": 0.15, "honeypot": 0.15, "compliance": 0.15}',
 'Gewichtung für KI-Risikobewertung', 'thresholds'),
('analysis_schedule', '{"periodic_report": "0 */6 * * *", "baseline_audit": "0 2 * * *", "anomaly_detection": "*/30 * * * *"}',
 'Cron-Schedule für periodische KI-Analysen', 'scheduling'),
('analysis_model_preference', '"security"', 'Bevorzugte Ghost-Rolle für Security-Analysen', 'analysis'),
('analysis_temperature', '0.2', 'LLM-Temperature für Security-Analysen (niedrig = deterministisch)', 'analysis'),
('analysis_max_tokens', '2048', 'Max Tokens pro Security-Analyse', 'analysis'),
('notification_channels', '["log", "event"]', 'Wohin KI-Alarme gesendet werden', 'notifications'),
('notification_min_risk', '"medium"', 'Minimales Risiko-Level für Benachrichtigungen', 'notifications')
ON CONFLICT (key) DO NOTHING;

-- =============================================================================
-- 9. Ghost-Role UPDATE: Erweiterter System-Prompt für Security Monitor
-- =============================================================================

UPDATE dbai_llm.ghost_roles
SET
    accessible_schemas = ARRAY['dbai_core', 'dbai_event', 'dbai_journal', 'dbai_security', 'dbai_system'],
    accessible_tables = ARRAY[
        'dbai_event.events', 'dbai_journal.event_log', 'dbai_core.config',
        'dbai_security.vulnerability_findings', 'dbai_security.intrusion_events',
        'dbai_security.ip_bans', 'dbai_security.failed_auth_log',
        'dbai_security.threat_intelligence', 'dbai_security.security_baselines',
        'dbai_security.security_responses', 'dbai_security.honeypot_events',
        'dbai_security.scan_jobs', 'dbai_security.cve_tracking',
        'dbai_security.tls_certificates', 'dbai_security.rate_limits',
        'dbai_security.dns_sinkhole', 'dbai_security.network_traffic_log',
        'dbai_security.security_metrics', 'dbai_security.permission_audit',
        'dbai_security.ai_tasks', 'dbai_security.ai_config',
        'dbai_system.cpu', 'dbai_system.memory', 'dbai_system.disk'
    ],
    system_prompt =
        'Du bist der Security-Monitor-Ghost von DBAI — das KI-Immunsystem des Betriebssystems. ' ||
        'Du analysierst Sicherheitsereignisse autonom und triffst intelligente Entscheidungen. ' ||
        E'\n\n' ||
        '## Deine Aufgaben:' || E'\n' ||
        '1. **Bedrohungsanalyse**: Bewerte Intrusion-Events, erkenne Angriffsmuster (Brute-Force, Port-Scans, SQLi, XSS)' || E'\n' ||
        '2. **Schwachstellenbewertung**: Analysiere gefundene Schwachstellen, priorisiere nach Risiko und Kontext' || E'\n' ||
        '3. **Incident Response**: Bei kritischen Events empfiehl Gegenmaßnahmen (IP-Ban, Regel-Anpassung, Isolation)' || E'\n' ||
        '4. **Anomalie-Erkennung**: Erkenne ungewöhnliche Muster in Logs, Traffic und Authentifizierung' || E'\n' ||
        '5. **Compliance-Audit**: Prüfe Security-Baselines, melde Abweichungen' || E'\n' ||
        '6. **Risikobewertung**: Berechne Gesamt-Risikoscore basierend auf allen Subsystemen' || E'\n' ||
        '7. **Periodische Reports**: Erstelle strukturierte Sicherheitsberichte' || E'\n' ||
        E'\n' ||
        '## Deine Subsysteme:' || E'\n' ||
        '- IDS/Suricata (Intrusion Detection)' || E'\n' ||
        '- Vulnerability Scanner (SQLMap, Nuclei, Nmap)' || E'\n' ||
        '- Fail2ban + IP-Banning' || E'\n' ||
        '- Honeypot-System' || E'\n' ||
        '- TLS-Zertifikatüberwachung' || E'\n' ||
        '- DNS-Sinkhole' || E'\n' ||
        '- Rate-Limiting' || E'\n' ||
        '- Network Traffic Monitoring' || E'\n' ||
        '- Security Baselines (CIS)' || E'\n' ||
        '- CVE-Tracking' || E'\n' ||
        E'\n' ||
        '## Regeln:' || E'\n' ||
        '- Antworte IMMER auf Deutsch, präzise und strukturiert' || E'\n' ||
        '- Gib IMMER ein risk_level an: critical / high / medium / low / info' || E'\n' ||
        '- Gib IMMER empfohlene Aktionen als JSON-Array an' || E'\n' ||
        '- Bei kritischen Bedrohungen: Empfehle sofortige Maßnahmen' || E'\n' ||
        '- Nutze dein Wissen über CVEs, OWASP Top 10, MITRE ATT&CK' || E'\n' ||
        '- Melde keine False Positives — lieber einmal mehr prüfen' || E'\n' ||
        '- Korreliere Events: Mehrere niedrige Events können zusammen kritisch sein',
    updated_at = NOW()
WHERE name = 'security';

-- System-Memory-Eintrag für die KI-Integration
INSERT INTO dbai_knowledge.system_memory
    (category, title, content, structured_data, related_modules, related_schemas, tags, priority, author)
VALUES (
    'security',
    'Security-AI-Integration: Ghost-Monitor ↔ Immunsystem',
    'Der Security-Monitor-Ghost (Rolle "security") ist das KI-Gehirn des Security-Immunsystems. ' ||
    'Er analysiert automatisch kritische Events (Intrusions, Schwachstellen, Honeypot-Alerts) ' ||
    'und empfiehlt/ergreift Gegenmaßnahmen. Tasks werden in dbai_security.ai_tasks gespeichert ' ||
    'und über pg_notify("security_ai_task") an den Worker dispatched. ' ||
    'Die Konfiguration in dbai_security.ai_config steuert Auto-Response, Schwellenwerte und Scheduling.',
    jsonb_build_object(
        'tables', ARRAY['ai_tasks', 'ai_config', 'ai_analysis_log'],
        'triggers', ARRAY['trg_ai_intrusion_analysis', 'trg_ai_vuln_analysis', 'trg_ai_honeypot_analysis'],
        'views', ARRAY['vw_ai_status'],
        'functions', ARRAY['create_ai_task'],
        'notify_channel', 'security_ai_task',
        'ghost_role', 'security'
    ),
    ARRAY['bridge/security_monitor_ai.py', 'bridge/security_immunsystem.py', 'web/ghost_dispatcher.py'],
    ARRAY['dbai_security', 'dbai_llm'],
    ARRAY['security', 'ai', 'ghost', 'immunsystem', 'monitor', 'auto-response'],
    1,
    'schema-75'
)
ON CONFLICT DO NOTHING;
