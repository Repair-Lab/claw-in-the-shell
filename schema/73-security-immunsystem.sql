-- ============================================================
-- Migration 73: Security-Immunsystem (Rückkopplungsschleife)
-- Version: 0.15.0
-- Datum:   2026-03-21
-- Grund:   Selbstschutz-Mechanismus — GhostShell OS bekommt
--          ein Immunsystem. Kali-Container als Security-Wächter,
--          automatisierte Penetrationstests, IDS/IPS, fail2ban,
--          Netzwerk-Firewall, Threat-Intelligence.
-- ============================================================

BEGIN;

-- =============================================================================
-- Schema: dbai_security — Dediziertes Security-Schema
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS dbai_security;

COMMENT ON SCHEMA dbai_security IS
  'GhostShell Immunsystem: Selbstschutz durch automatisierte '
  'Penetrationstests, IDS/IPS, Fail2Ban, Threat-Intelligence. '
  'Rückkopplungsschleife zur Selbstregulierung.';

-- Berechtigungen
GRANT USAGE ON SCHEMA dbai_security TO dbai_system;
GRANT USAGE ON SCHEMA dbai_security TO dbai_runtime;
GRANT USAGE ON SCHEMA dbai_security TO dbai_monitor;

-- =============================================================================
-- 1) SCAN_JOBS — Geplante & abgeschlossene Sicherheits-Scans
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_security.scan_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_type       TEXT NOT NULL CHECK (scan_type IN (
                        'sqlmap', 'nmap', 'nikto', 'nuclei',
                        'snort', 'suricata', 'lynis', 'openvas',
                        'ssl_check', 'port_scan', 'brute_force_test',
                        'dependency_audit', 'config_audit', 'custom'
                    )),
    target          TEXT NOT NULL,              -- z.B. IP, URL, Endpoint
    target_type     TEXT NOT NULL DEFAULT 'api' CHECK (target_type IN (
                        'api', 'database', 'network', 'host', 'container', 'router'
                    )),
    status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
                        'pending', 'running', 'completed', 'failed', 'cancelled'
                    )),
    priority        INTEGER NOT NULL DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
    schedule_cron   TEXT,                       -- NULL = einmalig, sonst Cron-Ausdruck
    last_run_at     TIMESTAMPTZ,
    next_run_at     TIMESTAMPTZ,
    duration_ms     INTEGER,
    findings_count  INTEGER DEFAULT 0,
    config          JSONB NOT NULL DEFAULT '{}', -- Tool-spezifische Konfiguration
    created_by      TEXT NOT NULL DEFAULT 'system',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_scan_jobs_status ON dbai_security.scan_jobs (status);
CREATE INDEX idx_scan_jobs_next_run ON dbai_security.scan_jobs (next_run_at) WHERE status != 'cancelled';
CREATE INDEX idx_scan_jobs_type ON dbai_security.scan_jobs (scan_type);

COMMENT ON TABLE dbai_security.scan_jobs IS
  'Zentraler Scheduler für alle Security-Scans. '
  'Unterstützt Cron-basierte Wiederholung und Prioritäten.';

-- =============================================================================
-- 2) VULNERABILITY_FINDINGS — Gefundene Schwachstellen
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_security.vulnerability_findings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_job_id     UUID REFERENCES dbai_security.scan_jobs(id) ON DELETE SET NULL,
    severity        TEXT NOT NULL CHECK (severity IN (
                        'critical', 'high', 'medium', 'low', 'info'
                    )),
    category        TEXT NOT NULL CHECK (category IN (
                        'sql_injection', 'xss', 'csrf', 'auth_bypass',
                        'path_traversal', 'rce', 'ssrf', 'idor',
                        'open_port', 'weak_cipher', 'missing_header',
                        'default_credential', 'misconfiguration',
                        'outdated_software', 'information_disclosure',
                        'privilege_escalation', 'dos', 'buffer_overflow',
                        'dns_rebinding', 'open_redirect', 'other'
                    )),
    title           TEXT NOT NULL,
    description     TEXT,
    affected_target TEXT NOT NULL,              -- z.B. /api/users, port 5432
    affected_param  TEXT,                       -- z.B. ?id=, Header, Cookie
    evidence        TEXT,                       -- Beweis (gekürzt)
    cve_id          TEXT,                       -- z.B. CVE-2024-1234
    cvss_score      NUMERIC(3,1) CHECK (cvss_score BETWEEN 0.0 AND 10.0),
    tool_output     JSONB DEFAULT '{}',         -- Rohe Tool-Ausgabe
    remediation     TEXT,                       -- Empfohlene Gegenmaßnahme
    status          TEXT NOT NULL DEFAULT 'open' CHECK (status IN (
                        'open', 'confirmed', 'mitigated', 'false_positive',
                        'accepted_risk', 'reopened'
                    )),
    auto_mitigated  BOOLEAN NOT NULL DEFAULT FALSE,
    mitigation_log  JSONB DEFAULT '[]',         -- Was das System automatisch getan hat
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at     TIMESTAMPTZ
);

CREATE INDEX idx_vuln_severity ON dbai_security.vulnerability_findings (severity);
CREATE INDEX idx_vuln_status ON dbai_security.vulnerability_findings (status);
CREATE INDEX idx_vuln_category ON dbai_security.vulnerability_findings (category);
CREATE INDEX idx_vuln_scan_job ON dbai_security.vulnerability_findings (scan_job_id);
CREATE INDEX idx_vuln_cve ON dbai_security.vulnerability_findings (cve_id) WHERE cve_id IS NOT NULL;

COMMENT ON TABLE dbai_security.vulnerability_findings IS
  'Alle gefundenen Schwachstellen aus Self-Penetration-Tests. '
  'Rückkopplungsschleife: Findings triggern automatische Gegenmaßnahmen.';

-- =============================================================================
-- 3) INTRUSION_EVENTS — IDS/IPS Erkennungen (Snort/Suricata)
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_security.intrusion_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type      TEXT NOT NULL CHECK (event_type IN (
                        'alert', 'drop', 'reject', 'pass', 'log'
                    )),
    source_ip       INET NOT NULL,
    source_port     INTEGER,
    dest_ip         INET,
    dest_port       INTEGER,
    protocol        TEXT CHECK (protocol IN ('tcp', 'udp', 'icmp', 'other')),
    signature_id    INTEGER,                   -- Snort/Suricata SID
    signature_name  TEXT,
    classification  TEXT,                      -- z.B. "attempted-recon"
    priority        INTEGER DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    payload_hash    TEXT,                      -- SHA256 des Payloads
    payload_preview TEXT,                      -- Erste 512 Bytes
    action_taken    TEXT DEFAULT 'logged' CHECK (action_taken IN (
                        'logged', 'blocked', 'rate_limited',
                        'ip_banned', 'account_locked', 'alert_sent'
                    )),
    raw_alert       JSONB DEFAULT '{}',
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_intrusion_source ON dbai_security.intrusion_events (source_ip);
CREATE INDEX idx_intrusion_time ON dbai_security.intrusion_events (detected_at DESC);
CREATE INDEX idx_intrusion_type ON dbai_security.intrusion_events (event_type);
CREATE INDEX idx_intrusion_priority ON dbai_security.intrusion_events (priority) WHERE priority <= 2;

-- Partitionierung-Hint: Bei hohem Volumen nach detected_at partitionieren
COMMENT ON TABLE dbai_security.intrusion_events IS
  'IDS/IPS-Erkennungen von Snort/Suricata. '
  'Eingehende Angriffe werden hier protokolliert und lösen Auto-Reaktionen aus.';

-- =============================================================================
-- 4) THREAT_INTELLIGENCE — IOC-Datenbank (Indicators of Compromise)
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_security.threat_intelligence (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ioc_type        TEXT NOT NULL CHECK (ioc_type IN (
                        'ip', 'domain', 'url', 'hash_md5', 'hash_sha256',
                        'email', 'cidr', 'user_agent', 'ja3_hash', 'pattern'
                    )),
    ioc_value       TEXT NOT NULL,
    threat_type     TEXT NOT NULL CHECK (threat_type IN (
                        'malware', 'phishing', 'botnet', 'scanner',
                        'brute_force', 'exploit', 'c2', 'spam', 'tor_exit',
                        'vpn_proxy', 'known_attacker', 'other'
                    )),
    confidence      INTEGER NOT NULL DEFAULT 70 CHECK (confidence BETWEEN 0 AND 100),
    source          TEXT NOT NULL DEFAULT 'internal',  -- z.B. 'abuseipdb', 'internal'
    description     TEXT,
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ,               -- NULL = nie
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    hit_count       INTEGER NOT NULL DEFAULT 0,
    UNIQUE (ioc_type, ioc_value)
);

CREATE INDEX idx_threat_ioc_value ON dbai_security.threat_intelligence (ioc_value);
CREATE INDEX idx_threat_active ON dbai_security.threat_intelligence (is_active) WHERE is_active = TRUE;
CREATE INDEX idx_threat_type ON dbai_security.threat_intelligence (threat_type);

COMMENT ON TABLE dbai_security.threat_intelligence IS
  'IOC-Datenbank: Bekannte bösartige IPs, Domains, Hashes. '
  'Wird durch IDS-Erkennungen und externe Feeds befüllt.';

-- =============================================================================
-- 5) FAILED_AUTH_LOG — Fehlgeschlagene Authentifizierungen (Fail2Ban-Basis)
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_security.failed_auth_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_ip       INET NOT NULL,
    username        TEXT,
    auth_type       TEXT NOT NULL CHECK (auth_type IN (
                        'postgresql', 'api', 'ssh', 'web_ui', 'vpn', 'other'
                    )),
    service_port    INTEGER,
    failure_reason  TEXT,
    user_agent      TEXT,
    geo_country     TEXT,                      -- GeoIP-Land (optional)
    attempt_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_failed_auth_ip ON dbai_security.failed_auth_log (source_ip);
CREATE INDEX idx_failed_auth_time ON dbai_security.failed_auth_log (attempt_at DESC);
CREATE INDEX idx_failed_auth_type ON dbai_security.failed_auth_log (auth_type);

-- Composite-Index für schnelle Ban-Prüfung: IP + Zeitfenster
CREATE INDEX idx_failed_auth_ban_check
  ON dbai_security.failed_auth_log (source_ip, attempt_at DESC);

COMMENT ON TABLE dbai_security.failed_auth_log IS
  'Fail2Ban-Basis: Alle fehlgeschlagenen Login-Versuche. '
  '3 Fehlversuche innerhalb von 5 Minuten → automatischer IP-Ban.';

-- =============================================================================
-- 6) IP_BANS — Aktive IP-Sperren
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_security.ip_bans (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ip_address      INET NOT NULL,
    cidr_mask       INTEGER DEFAULT 32,        -- /32 = einzelne IP, /24 = Subnetz
    reason          TEXT NOT NULL,
    ban_type        TEXT NOT NULL DEFAULT 'temporary' CHECK (ban_type IN (
                        'temporary', 'permanent', 'geo_block', 'threat_intel'
                    )),
    source          TEXT NOT NULL DEFAULT 'fail2ban', -- fail2ban, ids, manual, threat_intel
    banned_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ,               -- NULL = permanent
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    unban_reason    TEXT,
    unbanned_at     TIMESTAMPTZ,
    UNIQUE (ip_address, cidr_mask) 
);

CREATE INDEX idx_ip_bans_active ON dbai_security.ip_bans (is_active) WHERE is_active = TRUE;
CREATE INDEX idx_ip_bans_expires ON dbai_security.ip_bans (expires_at)
  WHERE is_active = TRUE AND expires_at IS NOT NULL;

COMMENT ON TABLE dbai_security.ip_bans IS
  'Aktive IP-Sperren. Wird von Fail2Ban, IDS und Threat-Intel befüllt. '
  'Temporäre Bans laufen automatisch ab.';

-- =============================================================================
-- 7) NETWORK_TRAFFIC_LOG — Netzwerk-Verkehrsanalyse
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_security.network_traffic_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_ip       INET NOT NULL,
    source_port     INTEGER,
    dest_ip         INET NOT NULL,
    dest_port       INTEGER,
    protocol        TEXT CHECK (protocol IN ('tcp', 'udp', 'icmp', 'other')),
    direction       TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound', 'internal')),
    bytes_sent      BIGINT DEFAULT 0,
    bytes_received  BIGINT DEFAULT 0,
    packets         INTEGER DEFAULT 0,
    flags           TEXT,                      -- TCP-Flags (SYN, ACK, RST, etc.)
    is_encrypted    BOOLEAN DEFAULT FALSE,
    is_suspicious   BOOLEAN DEFAULT FALSE,
    threat_score    INTEGER DEFAULT 0 CHECK (threat_score BETWEEN 0 AND 100),
    logged_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Partitionierung nach Zeit empfohlen bei hohem Volumen
CREATE INDEX idx_traffic_time ON dbai_security.network_traffic_log (logged_at DESC);
CREATE INDEX idx_traffic_suspicious ON dbai_security.network_traffic_log (is_suspicious)
  WHERE is_suspicious = TRUE;
CREATE INDEX idx_traffic_source ON dbai_security.network_traffic_log (source_ip);
CREATE INDEX idx_traffic_dest ON dbai_security.network_traffic_log (dest_ip, dest_port);

COMMENT ON TABLE dbai_security.network_traffic_log IS
  'Netzwerk-Traffic-Log für Anomalie-Erkennung. '
  'Alles was am Router angeschlossen ist wird überwacht.';

-- =============================================================================
-- 8) SECURITY_RESPONSES — Automatische Gegenmaßnahmen (Feedback-Loop)
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_security.security_responses (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trigger_type    TEXT NOT NULL CHECK (trigger_type IN (
                        'vulnerability', 'intrusion', 'failed_auth',
                        'anomaly', 'threat_intel', 'traffic_anomaly',
                        'manual', 'escalation'
                    )),
    trigger_id      UUID,                      -- Referenz auf auslösendes Event
    response_type   TEXT NOT NULL CHECK (response_type IN (
                        'ip_ban', 'rate_limit', 'firewall_rule',
                        'pg_hba_update', 'account_lock', 'port_close',
                        'service_restart', 'config_patch', 'alert_admin',
                        'isolate_container', 'rotate_credentials',
                        'enable_2fa', 'ssl_upgrade', 'waf_rule',
                        'quarantine', 'snapshot'
                    )),
    description     TEXT NOT NULL,
    details         JSONB NOT NULL DEFAULT '{}',
    success         BOOLEAN,
    error_message   TEXT,
    rollback_info   JSONB DEFAULT '{}',        -- Info für Rückgängigmachen
    executed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    rolled_back_at  TIMESTAMPTZ
);

CREATE INDEX idx_response_trigger ON dbai_security.security_responses (trigger_type, trigger_id);
CREATE INDEX idx_response_time ON dbai_security.security_responses (executed_at DESC);
CREATE INDEX idx_response_type ON dbai_security.security_responses (response_type);

COMMENT ON TABLE dbai_security.security_responses IS
  'Feedback-Loop: Alle automatisch ausgeführten Gegenmaßnahmen. '
  'Jede Reaktion wird protokolliert und kann rückgängig gemacht werden.';

-- =============================================================================
-- 9) TLS_CERTIFICATES — Zertifikats-Management
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_security.tls_certificates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain          TEXT NOT NULL,
    common_name     TEXT,
    issuer          TEXT,
    serial_number   TEXT,
    fingerprint     TEXT,
    algorithm       TEXT DEFAULT 'RSA-2048',
    not_before      TIMESTAMPTZ,
    not_after       TIMESTAMPTZ,
    auto_renew      BOOLEAN DEFAULT TRUE,
    cert_path       TEXT,
    key_path        TEXT,
    status          TEXT NOT NULL DEFAULT 'active' CHECK (status IN (
                        'active', 'expired', 'revoked', 'pending_renewal'
                    )),
    last_checked_at TIMESTAMPTZ DEFAULT now(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (domain, serial_number)
);

CREATE INDEX idx_tls_expiry ON dbai_security.tls_certificates (not_after)
  WHERE status = 'active';

COMMENT ON TABLE dbai_security.tls_certificates IS
  'TLS-Zertifikats-Verwaltung mit automatischer Erneuerung.';

-- =============================================================================
-- 10) SECURITY_BASELINES — System-Sicherheits-Referenzwerte
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_security.security_baselines (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    component       TEXT NOT NULL,             -- z.B. 'postgresql', 'docker', 'network'
    check_name      TEXT NOT NULL,
    expected_value  TEXT NOT NULL,
    current_value   TEXT,
    compliant       BOOLEAN DEFAULT TRUE,
    severity        TEXT DEFAULT 'medium' CHECK (severity IN (
                        'critical', 'high', 'medium', 'low', 'info'
                    )),
    last_checked_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (component, check_name)
);

COMMENT ON TABLE dbai_security.security_baselines IS
  'CIS/STIG-inspirierte Sicherheits-Baselines. '
  'Regelmäßig geprüft — Abweichungen lösen Alerts aus.';

-- =============================================================================
-- 11) CVE_TRACKING — Bekannte Schwachstellen verfolgen
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_security.cve_tracking (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cve_id          TEXT NOT NULL UNIQUE,       -- CVE-2024-XXXX
    title           TEXT NOT NULL,
    description     TEXT,
    cvss_score      NUMERIC(3,1) CHECK (cvss_score BETWEEN 0.0 AND 10.0),
    affected_pkg    TEXT,                      -- z.B. 'postgresql-16', 'python-3.11'
    affected_ver    TEXT,                      -- z.B. '< 16.2'
    fixed_ver       TEXT,                      -- z.B. '>= 16.2'
    is_relevant     BOOLEAN DEFAULT TRUE,
    is_patched      BOOLEAN DEFAULT FALSE,
    patched_at      TIMESTAMPTZ,
    discovered_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    source_url      TEXT
);

CREATE INDEX idx_cve_relevant ON dbai_security.cve_tracking (is_relevant)
  WHERE is_relevant = TRUE AND is_patched = FALSE;

COMMENT ON TABLE dbai_security.cve_tracking IS
  'CVE-Tracking: Bekannte Schwachstellen in genutzten Paketen. '
  'Automatisch abgeglichen mit installierter Software.';

-- =============================================================================
-- 12) PERMISSION_AUDIT — Berechtigungsänderungen protokollieren
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_security.permission_audit (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    db_role         TEXT NOT NULL,
    object_type     TEXT NOT NULL,             -- TABLE, SCHEMA, FUNCTION
    object_name     TEXT NOT NULL,
    privilege       TEXT NOT NULL,             -- SELECT, INSERT, EXECUTE, etc.
    action          TEXT NOT NULL CHECK (action IN ('GRANT', 'REVOKE')),
    granted_by      TEXT NOT NULL DEFAULT current_user,
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_perm_audit_role ON dbai_security.permission_audit (db_role);
CREATE INDEX idx_perm_audit_time ON dbai_security.permission_audit (changed_at DESC);

COMMENT ON TABLE dbai_security.permission_audit IS
  'Protokolliert jede Berechtigungsänderung in der Datenbank (GRANT/REVOKE).';

-- =============================================================================
-- 13) SECURITY_METRICS — Dashboard-Kennzahlen
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_security.security_metrics (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_name     TEXT NOT NULL,
    metric_value    NUMERIC NOT NULL,
    unit            TEXT DEFAULT 'count',
    dimension       TEXT,                      -- z.B. 'by_severity', 'by_source'
    dimension_value TEXT,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_sec_metrics_name ON dbai_security.security_metrics (metric_name, recorded_at DESC);

COMMENT ON TABLE dbai_security.security_metrics IS
  'Aggregierte Security-Metriken für das Dashboard.';

-- =============================================================================
-- 14) HONEYPOT_EVENTS — Honeypot-Fallen für Angreifer
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_security.honeypot_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    honeypot_type   TEXT NOT NULL CHECK (honeypot_type IN (
                        'fake_ssh', 'fake_db', 'fake_api', 'fake_admin',
                        'canary_token', 'decoy_file'
                    )),
    source_ip       INET NOT NULL,
    source_port     INTEGER,
    interaction     TEXT NOT NULL,             -- Was der Angreifer versucht hat
    payload         TEXT,
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_honeypot_ip ON dbai_security.honeypot_events (source_ip);
CREATE INDEX idx_honeypot_time ON dbai_security.honeypot_events (detected_at DESC);

COMMENT ON TABLE dbai_security.honeypot_events IS
  'Honeypot-Fallen: Fake-Services die Angreifer anlocken. '
  'Jede Interaktion → sofortiger Ban + Threat-Intel-Eintrag.';

-- =============================================================================
-- 15) RATE_LIMITS — Dynamische Rate-Limits
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_security.rate_limits (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    target_type     TEXT NOT NULL CHECK (target_type IN (
                        'ip', 'user', 'endpoint', 'api_key', 'global'
                    )),
    target_value    TEXT NOT NULL,             -- z.B. IP, Username, /api/login
    max_requests    INTEGER NOT NULL DEFAULT 100,
    window_seconds  INTEGER NOT NULL DEFAULT 60,
    current_count   INTEGER NOT NULL DEFAULT 0,
    window_start    TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_blocked      BOOLEAN NOT NULL DEFAULT FALSE,
    blocked_until   TIMESTAMPTZ,
    UNIQUE (target_type, target_value)
);

CREATE INDEX idx_rate_limits_blocked ON dbai_security.rate_limits (is_blocked)
  WHERE is_blocked = TRUE;

COMMENT ON TABLE dbai_security.rate_limits IS
  'Dynamische Rate-Limits pro IP, User oder Endpoint. '
  'Überschreitung → temporärer Block + Logging.';

-- =============================================================================
-- 16) DNS_SINKHOLE — DNS-basierte Schutzmechanismen
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_security.dns_sinkhole (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain          TEXT NOT NULL UNIQUE,
    category        TEXT NOT NULL CHECK (category IN (
                        'malware', 'phishing', 'c2', 'tracking',
                        'ads', 'cryptomining', 'custom'
                    )),
    source          TEXT DEFAULT 'internal',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    added_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    hit_count       INTEGER NOT NULL DEFAULT 0,
    last_hit_at     TIMESTAMPTZ
);

CREATE INDEX idx_dns_sinkhole_active ON dbai_security.dns_sinkhole (is_active)
  WHERE is_active = TRUE;

COMMENT ON TABLE dbai_security.dns_sinkhole IS
  'DNS-Sinkhole: Blockierte Domains (Malware, Phishing, C2). '
  'Integriert mit Netzwerk-Firewall.';

-- =============================================================================
-- FUNKTIONEN: Automatische Sicherheits-Reaktionen
-- =============================================================================

-- ─── Fail2Ban: Automatischer IP-Ban bei zu vielen Fehlversuchen ───
CREATE OR REPLACE FUNCTION dbai_security.check_and_ban_ip(
    p_source_ip INET,
    p_max_attempts INTEGER DEFAULT 3,
    p_window_minutes INTEGER DEFAULT 5,
    p_ban_duration_hours INTEGER DEFAULT 24
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_attempt_count INTEGER;
    v_already_banned BOOLEAN;
BEGIN
    -- Prüfe ob IP bereits gebannt
    SELECT EXISTS(
        SELECT 1 FROM dbai_security.ip_bans
        WHERE ip_address = p_source_ip
          AND is_active = TRUE
          AND (expires_at IS NULL OR expires_at > now())
    ) INTO v_already_banned;

    IF v_already_banned THEN
        RETURN TRUE;  -- Bereits gebannt
    END IF;

    -- Zähle fehlgeschlagene Versuche im Zeitfenster
    SELECT COUNT(*) INTO v_attempt_count
    FROM dbai_security.failed_auth_log
    WHERE source_ip = p_source_ip
      AND attempt_at > now() - (p_window_minutes || ' minutes')::INTERVAL;

    -- Ban wenn Schwelle überschritten
    IF v_attempt_count >= p_max_attempts THEN
        INSERT INTO dbai_security.ip_bans (
            ip_address, reason, ban_type, source, expires_at
        ) VALUES (
            p_source_ip,
            format('%s fehlgeschlagene Versuche in %s Minuten',
                   v_attempt_count, p_window_minutes),
            'temporary',
            'fail2ban',
            now() + (p_ban_duration_hours || ' hours')::INTERVAL
        )
        ON CONFLICT (ip_address, cidr_mask) DO UPDATE SET
            is_active = TRUE,
            reason = EXCLUDED.reason,
            banned_at = now(),
            expires_at = EXCLUDED.expires_at,
            unban_reason = NULL,
            unbanned_at = NULL;

        -- Protokolliere die Reaktion
        INSERT INTO dbai_security.security_responses (
            trigger_type, response_type, description, details
        ) VALUES (
            'failed_auth',
            'ip_ban',
            format('IP %s gebannt: %s Fehlversuche', p_source_ip, v_attempt_count),
            jsonb_build_object(
                'ip', p_source_ip::TEXT,
                'attempts', v_attempt_count,
                'window_minutes', p_window_minutes,
                'ban_hours', p_ban_duration_hours
            )
        );

        RETURN TRUE;  -- Gebannt
    END IF;

    RETURN FALSE;  -- Nicht gebannt
END;
$$;

-- ─── Threat-Score für eine IP berechnen ───
CREATE OR REPLACE FUNCTION dbai_security.calculate_threat_score(p_ip INET)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_score INTEGER := 0;
    v_failed_auths INTEGER;
    v_intrusion_events INTEGER;
    v_threat_intel_match BOOLEAN;
    v_honeypot_hits INTEGER;
    v_traffic_anomalies INTEGER;
BEGIN
    -- Fehlgeschlagene Logins (letzte 24h)
    SELECT COUNT(*) INTO v_failed_auths
    FROM dbai_security.failed_auth_log
    WHERE source_ip = p_ip AND attempt_at > now() - INTERVAL '24 hours';
    v_score := v_score + LEAST(v_failed_auths * 10, 30);

    -- IDS-Alerts (letzte 24h)
    SELECT COUNT(*) INTO v_intrusion_events
    FROM dbai_security.intrusion_events
    WHERE source_ip = p_ip AND detected_at > now() - INTERVAL '24 hours';
    v_score := v_score + LEAST(v_intrusion_events * 15, 40);

    -- Threat-Intel-Match
    SELECT EXISTS(
        SELECT 1 FROM dbai_security.threat_intelligence
        WHERE ioc_value = p_ip::TEXT AND is_active = TRUE
    ) INTO v_threat_intel_match;
    IF v_threat_intel_match THEN
        v_score := v_score + 50;
    END IF;

    -- Honeypot-Interaktionen
    SELECT COUNT(*) INTO v_honeypot_hits
    FROM dbai_security.honeypot_events
    WHERE source_ip = p_ip AND detected_at > now() - INTERVAL '24 hours';
    v_score := v_score + LEAST(v_honeypot_hits * 25, 50);

    -- Verdächtiger Traffic
    SELECT COUNT(*) INTO v_traffic_anomalies
    FROM dbai_security.network_traffic_log
    WHERE source_ip = p_ip AND is_suspicious = TRUE
      AND logged_at > now() - INTERVAL '24 hours';
    v_score := v_score + LEAST(v_traffic_anomalies * 5, 20);

    RETURN LEAST(v_score, 100);
END;
$$;

-- ─── Abgelaufene Bans automatisch aufheben ───
CREATE OR REPLACE FUNCTION dbai_security.cleanup_expired_bans()
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_count INTEGER;
BEGIN
    UPDATE dbai_security.ip_bans
    SET is_active = FALSE,
        unban_reason = 'Ban abgelaufen',
        unbanned_at = now()
    WHERE is_active = TRUE
      AND expires_at IS NOT NULL
      AND expires_at <= now();

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$;

-- ─── Security-Metriken aggregieren ───
CREATE OR REPLACE FUNCTION dbai_security.update_security_metrics()
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    -- Offene Vulnerabilities nach Severity
    INSERT INTO dbai_security.security_metrics (metric_name, metric_value, dimension, dimension_value)
    SELECT 'open_vulnerabilities', COUNT(*), 'severity', severity
    FROM dbai_security.vulnerability_findings
    WHERE status IN ('open', 'confirmed', 'reopened')
    GROUP BY severity;

    -- Aktive IP-Bans
    INSERT INTO dbai_security.security_metrics (metric_name, metric_value)
    SELECT 'active_ip_bans', COUNT(*)
    FROM dbai_security.ip_bans WHERE is_active = TRUE;

    -- IDS-Events letzte Stunde
    INSERT INTO dbai_security.security_metrics (metric_name, metric_value)
    SELECT 'ids_events_last_hour', COUNT(*)
    FROM dbai_security.intrusion_events
    WHERE detected_at > now() - INTERVAL '1 hour';

    -- Fehlgeschlagene Logins letzte Stunde
    INSERT INTO dbai_security.security_metrics (metric_name, metric_value)
    SELECT 'failed_auths_last_hour', COUNT(*)
    FROM dbai_security.failed_auth_log
    WHERE attempt_at > now() - INTERVAL '1 hour';

    -- Threat-Intel-Einträge
    INSERT INTO dbai_security.security_metrics (metric_name, metric_value)
    SELECT 'active_threat_indicators', COUNT(*)
    FROM dbai_security.threat_intelligence WHERE is_active = TRUE;

    -- Baseline-Compliance
    INSERT INTO dbai_security.security_metrics (metric_name, metric_value)
    SELECT 'baseline_compliance_pct',
           ROUND(100.0 * COUNT(*) FILTER (WHERE compliant) / NULLIF(COUNT(*), 0), 1)
    FROM dbai_security.security_baselines;

    -- Security-Score (0-100, höher = sicherer)
    INSERT INTO dbai_security.security_metrics (metric_name, metric_value)
    SELECT 'overall_security_score',
           GREATEST(0, 100
             - (SELECT COUNT(*) * 20 FROM dbai_security.vulnerability_findings
                WHERE status IN ('open','confirmed') AND severity = 'critical')
             - (SELECT COUNT(*) * 10 FROM dbai_security.vulnerability_findings
                WHERE status IN ('open','confirmed') AND severity = 'high')
             - (SELECT COUNT(*) * 5 FROM dbai_security.vulnerability_findings
                WHERE status IN ('open','confirmed') AND severity = 'medium')
             - (SELECT COUNT(*) FROM dbai_security.security_baselines
                WHERE compliant = FALSE AND severity IN ('critical','high'))
           );
END;
$$;

-- ─── Selbstheilung: Automatische Reaktion auf Findings ───
CREATE OR REPLACE FUNCTION dbai_security.auto_respond_to_finding()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    -- Bei kritischen SQL-Injections: Sofort den betroffenen Endpoint loggen
    IF NEW.severity = 'critical' AND NEW.category = 'sql_injection' THEN
        INSERT INTO dbai_security.security_responses (
            trigger_type, trigger_id, response_type, description, details
        ) VALUES (
            'vulnerability', NEW.id, 'waf_rule',
            format('Kritische SQL-Injection in %s — WAF-Regel erstellt', NEW.affected_target),
            jsonb_build_object(
                'endpoint', NEW.affected_target,
                'param', NEW.affected_param,
                'action', 'block_pattern'
            )
        );

        -- Markiere als auto-mitigiert
        NEW.auto_mitigated := TRUE;
        NEW.mitigation_log := NEW.mitigation_log || jsonb_build_array(
            jsonb_build_object(
                'action', 'waf_rule_created',
                'timestamp', now()::TEXT,
                'details', 'Automatische WAF-Regel gegen SQL-Injection-Pattern'
            )
        );
    END IF;

    -- Bei offenen Ports: Firewall-Regel vorschlagen
    IF NEW.category = 'open_port' AND NEW.severity IN ('critical', 'high') THEN
        INSERT INTO dbai_security.security_responses (
            trigger_type, trigger_id, response_type, description, details
        ) VALUES (
            'vulnerability', NEW.id, 'port_close',
            format('Unerwarteter offener Port: %s', NEW.affected_target),
            jsonb_build_object(
                'port', NEW.affected_target,
                'action', 'close_port'
            )
        );
    END IF;

    RETURN NEW;
END;
$$;

CREATE OR REPLACE TRIGGER trg_auto_respond_vuln
    BEFORE INSERT ON dbai_security.vulnerability_findings
    FOR EACH ROW
    EXECUTE FUNCTION dbai_security.auto_respond_to_finding();

-- ─── Auto-Respond auf Intrusion Events ───
CREATE OR REPLACE FUNCTION dbai_security.auto_respond_to_intrusion()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    -- Bei hoher Priorität: Sofort bannen
    IF NEW.priority <= 2 THEN
        PERFORM dbai_security.check_and_ban_ip(
            NEW.source_ip, 1, 60, 168  -- 1 Versuch, 60min Fenster, 1 Woche Ban
        );
        NEW.action_taken := 'ip_banned';

        -- Threat-Intel aktualisieren
        INSERT INTO dbai_security.threat_intelligence (
            ioc_type, ioc_value, threat_type, confidence, source, description
        ) VALUES (
            'ip', NEW.source_ip::TEXT,
            CASE
                WHEN NEW.classification LIKE '%recon%' THEN 'scanner'
                WHEN NEW.classification LIKE '%exploit%' THEN 'exploit'
                ELSE 'known_attacker'
            END,
            90, 'ids',
            format('Automatisch erkannt: %s', NEW.signature_name)
        )
        ON CONFLICT (ioc_type, ioc_value) DO UPDATE SET
            confidence = GREATEST(dbai_security.threat_intelligence.confidence, 90),
            last_seen_at = now(),
            hit_count = dbai_security.threat_intelligence.hit_count + 1;
    END IF;

    -- Bei Honeypot-ähnlichen Signaturen: Sofort bannen
    IF NEW.signature_name ILIKE '%honeypot%' OR NEW.signature_name ILIKE '%decoy%' THEN
        PERFORM dbai_security.check_and_ban_ip(
            NEW.source_ip, 1, 1440, 720  -- Sofort, 30 Tage Ban
        );
        NEW.action_taken := 'ip_banned';
    END IF;

    RETURN NEW;
END;
$$;

CREATE OR REPLACE TRIGGER trg_auto_respond_intrusion
    BEFORE INSERT ON dbai_security.intrusion_events
    FOR EACH ROW
    EXECUTE FUNCTION dbai_security.auto_respond_to_intrusion();

-- ─── Auto-Ban bei Honeypot-Interaktion ───
CREATE OR REPLACE FUNCTION dbai_security.auto_respond_to_honeypot()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    -- Jeder Honeypot-Kontakt = sofortiger Ban + Threat-Intel
    PERFORM dbai_security.check_and_ban_ip(
        NEW.source_ip, 1, 1, 720  -- 30 Tage Ban
    );

    INSERT INTO dbai_security.threat_intelligence (
        ioc_type, ioc_value, threat_type, confidence, source, description
    ) VALUES (
        'ip', NEW.source_ip::TEXT, 'known_attacker', 95, 'honeypot',
        format('Honeypot-Interaktion: %s — %s', NEW.honeypot_type, NEW.interaction)
    )
    ON CONFLICT (ioc_type, ioc_value) DO UPDATE SET
        confidence = 99,
        last_seen_at = now(),
        hit_count = dbai_security.threat_intelligence.hit_count + 1;

    RETURN NEW;
END;
$$;

CREATE OR REPLACE TRIGGER trg_auto_respond_honeypot
    BEFORE INSERT ON dbai_security.honeypot_events
    FOR EACH ROW
    EXECUTE FUNCTION dbai_security.auto_respond_to_honeypot();

-- =============================================================================
-- ROW LEVEL SECURITY
-- =============================================================================

-- Alle Security-Tabellen: System hat vollen Zugriff
ALTER TABLE dbai_security.scan_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE dbai_security.vulnerability_findings ENABLE ROW LEVEL SECURITY;
ALTER TABLE dbai_security.intrusion_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE dbai_security.threat_intelligence ENABLE ROW LEVEL SECURITY;
ALTER TABLE dbai_security.failed_auth_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE dbai_security.ip_bans ENABLE ROW LEVEL SECURITY;
ALTER TABLE dbai_security.network_traffic_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE dbai_security.security_responses ENABLE ROW LEVEL SECURITY;
ALTER TABLE dbai_security.tls_certificates ENABLE ROW LEVEL SECURITY;
ALTER TABLE dbai_security.security_baselines ENABLE ROW LEVEL SECURITY;
ALTER TABLE dbai_security.cve_tracking ENABLE ROW LEVEL SECURITY;
ALTER TABLE dbai_security.permission_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE dbai_security.security_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE dbai_security.honeypot_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE dbai_security.rate_limits ENABLE ROW LEVEL SECURITY;
ALTER TABLE dbai_security.dns_sinkhole ENABLE ROW LEVEL SECURITY;

-- System: Voll-Zugriff
DO $$ 
DECLARE
    t TEXT;
BEGIN
    FOR t IN SELECT unnest(ARRAY[
        'scan_jobs', 'vulnerability_findings', 'intrusion_events',
        'threat_intelligence', 'failed_auth_log', 'ip_bans',
        'network_traffic_log', 'security_responses', 'tls_certificates',
        'security_baselines', 'cve_tracking', 'permission_audit',
        'security_metrics', 'honeypot_events', 'rate_limits', 'dns_sinkhole'
    ])
    LOOP
        EXECUTE format(
            'DROP POLICY IF EXISTS %I_system_full ON dbai_security.%I; '
            'CREATE POLICY %I_system_full ON dbai_security.%I FOR ALL TO dbai_system USING (TRUE);',
            t, t, t, t
        );
        -- Monitor: Nur Lesen
        EXECUTE format(
            'DROP POLICY IF EXISTS %I_monitor_read ON dbai_security.%I; '
            'CREATE POLICY %I_monitor_read ON dbai_security.%I FOR SELECT TO dbai_monitor USING (TRUE);',
            t, t, t, t
        );
        -- Runtime: Lesen + Einfügen (für API-Events)
        EXECUTE format(
            'DROP POLICY IF EXISTS %I_runtime_rw ON dbai_security.%I; '
            'CREATE POLICY %I_runtime_rw ON dbai_security.%I FOR ALL TO dbai_runtime USING (TRUE);',
            t, t, t, t
        );
        -- Grants
        EXECUTE format(
            'GRANT ALL ON dbai_security.%I TO dbai_system; '
            'GRANT SELECT ON dbai_security.%I TO dbai_monitor; '
            'GRANT SELECT, INSERT, UPDATE ON dbai_security.%I TO dbai_runtime;',
            t, t, t
        );
    END LOOP;
END $$;

-- =============================================================================
-- APPEND-ONLY SCHUTZ für kritische Security-Tabellen
-- =============================================================================
CREATE OR REPLACE FUNCTION dbai_security.protect_append_only()
RETURNS TRIGGER
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Security-Log-Tabellen sind Append-Only — Löschen verboten!';
    RETURN NULL;
END;
$$;

-- Intrusion Events: Append-Only
DROP TRIGGER IF EXISTS trg_protect_intrusion_log ON dbai_security.intrusion_events;
CREATE TRIGGER trg_protect_intrusion_log
    BEFORE DELETE ON dbai_security.intrusion_events
    FOR EACH ROW EXECUTE FUNCTION dbai_security.protect_append_only();

-- Failed Auth Log: Append-Only
DROP TRIGGER IF EXISTS trg_protect_failed_auth ON dbai_security.failed_auth_log;
CREATE TRIGGER trg_protect_failed_auth
    BEFORE DELETE ON dbai_security.failed_auth_log
    FOR EACH ROW EXECUTE FUNCTION dbai_security.protect_append_only();

-- Security Responses: Append-Only
DROP TRIGGER IF EXISTS trg_protect_responses ON dbai_security.security_responses;
CREATE TRIGGER trg_protect_responses
    BEFORE DELETE ON dbai_security.security_responses
    FOR EACH ROW EXECUTE FUNCTION dbai_security.protect_append_only();

-- Honeypot Events: Append-Only
DROP TRIGGER IF EXISTS trg_protect_honeypot ON dbai_security.honeypot_events;
CREATE TRIGGER trg_protect_honeypot
    BEFORE DELETE ON dbai_security.honeypot_events
    FOR EACH ROW EXECUTE FUNCTION dbai_security.protect_append_only();

-- Permission Audit: Append-Only
DROP TRIGGER IF EXISTS trg_protect_perm_audit ON dbai_security.permission_audit;
CREATE TRIGGER trg_protect_perm_audit
    BEFORE DELETE ON dbai_security.permission_audit
    FOR EACH ROW EXECUTE FUNCTION dbai_security.protect_append_only();

-- =============================================================================
-- CHANGELOG-EINTRAG
-- =============================================================================
INSERT INTO dbai_knowledge.changelog (version, title, description, change_type)
VALUES (
    '0.15.0',
    'Security-Immunsystem: Rückkopplungsschleife zur Selbstregulierung',
    'Neues dbai_security-Schema mit 16 Tabellen: Automatisierte Penetrationstests '
    '(SQLMap, Nmap, Nuclei), IDS/IPS-Integration (Snort/Suricata), Fail2Ban mit '
    'PostgreSQL-Log-Verknüpfung, Threat-Intelligence-Datenbank, Honeypot-Fallen, '
    'DNS-Sinkhole, TLS-Zertifikats-Management, CVE-Tracking, Rate-Limiting, '
    'Netzwerk-Traffic-Analyse. Rückkopplungsschleife: Findings → Auto-Mitigation → '
    'Firewall-Updates → Erneuter Scan. Kali-Linux-Sidecar-Container als Security-Wächter.',
    'feature'
)
ON CONFLICT (version, title) DO NOTHING;

COMMIT;
