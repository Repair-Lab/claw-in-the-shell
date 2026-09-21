-- ============================================================
-- Migration 74: Security-Immunsystem Seed-Data
-- Version: 0.15.0
-- Datum:   2026-03-21
-- Grund:   Initiale Baselines, Default-Scan-Jobs, Threat-Intel,
--          DNS-Sinkhole, Rate-Limits, Standard-CVEs
-- ============================================================

BEGIN;

-- =============================================================================
-- 0) CHECK-Constraint erweitern: 'security' als Kategorie erlauben
-- =============================================================================
ALTER TABLE dbai_knowledge.system_memory DROP CONSTRAINT IF EXISTS system_memory_category_check;
ALTER TABLE dbai_knowledge.system_memory ADD CONSTRAINT system_memory_category_check
    CHECK (category = ANY (ARRAY[
        'architecture', 'convention', 'schema_map', 'design_pattern',
        'relationship', 'workflow', 'inventory', 'roadmap', 'identity',
        'operational', 'agent', 'import', 'feature', 'security'
    ]));

-- =============================================================================
-- 1) Standard Scan-Jobs (Cron-basiert)
-- =============================================================================
INSERT INTO dbai_security.scan_jobs (scan_type, target, target_type, status, schedule_cron, priority, config) VALUES
    ('sqlmap',    'http://ghost-api:3000', 'api',       'pending', '0 * * * *',    8, '{"level": 3, "risk": 2, "threads": 4}'::JSONB),
    ('nmap',      '172.28.0.0/24',        'network',   'pending', '*/30 * * * *', 7, '{"flags": "-sV -sC --script=vuln"}'::JSONB),
    ('nmap',      '127.0.0.1',            'host',      'pending', '*/30 * * * *', 9, '{"flags": "-sV -O --open"}'::JSONB),
    ('nuclei',    'http://ghost-api:3000', 'api',       'pending', '0 */2 * * *',  6, '{"severity": "critical,high,medium"}'::JSONB),
    ('ssl_check', 'ghost-api:3000',        'api',       'pending', '0 */12 * * *', 5, '{"check_ciphers": true}'::JSONB),
    ('lynis',     'localhost',             'host',      'pending', '0 3 * * *',    4, '{"quick": true}'::JSONB),
    ('config_audit', 'postgresql',         'database',  'pending', '0 4 * * *',    8, '{"check_rls": true, "check_ssl": true}'::JSONB),
    ('port_scan', '192.168.1.0/24',        'network',   'pending', '0 */6 * * *',  5, '{"description": "LAN-Netzwerk-Scan"}'::JSONB),
    ('dependency_audit', 'pip:packages',   'host',      'pending', '0 5 * * *',    6, '{"check_python": true}'::JSONB)
ON CONFLICT DO NOTHING;

-- =============================================================================
-- 2) Security-Baselines (PostgreSQL CIS Benchmark)
-- =============================================================================
INSERT INTO dbai_security.security_baselines (component, check_name, expected_value, severity) VALUES
    -- PostgreSQL Hardening
    ('postgresql', 'listen_addresses',       '127.0.0.1',     'critical'),
    ('postgresql', 'ssl',                    'on',            'critical'),
    ('postgresql', 'password_encryption',    'scram-sha-256', 'critical'),
    ('postgresql', 'row_security',           'on',            'critical'),
    ('postgresql', 'log_connections',        'on',            'high'),
    ('postgresql', 'log_disconnections',     'on',            'high'),
    ('postgresql', 'log_statement',          'ddl',           'high'),
    ('postgresql', 'statement_timeout',      '60s',           'medium'),
    ('postgresql', 'max_connections',        '100',           'medium'),
    ('postgresql', 'log_min_duration_statement', '100',       'medium'),
    ('postgresql', 'lock_timeout',           '10s',           'medium'),
    ('postgresql', 'deadlock_timeout',       '1s',            'medium'),
    ('postgresql', 'log_lock_waits',         'on',            'medium'),
    ('postgresql', 'shared_preload_libraries', 'pg_stat_statements,vector', 'info'),
    -- Docker Hardening
    ('docker', 'user_namespace',             'enabled',       'high'),
    ('docker', 'no_new_privileges',          'true',          'high'),
    ('docker', 'read_only_rootfs',           'true',          'medium'),
    ('docker', 'seccomp_profile',            'default',       'medium'),
    ('docker', 'apparmor_profile',           'docker-default','medium'),
    -- Netzwerk Hardening
    ('network', 'ip_forward',                '0',             'critical'),
    ('network', 'tcp_syncookies',            '1',             'critical'),
    ('network', 'accept_redirects',          '0',             'high'),
    ('network', 'rp_filter',                 '1',             'high'),
    ('network', 'log_martians',              '1',             'medium'),
    ('network', 'accept_source_route',       '0',             'high'),
    ('network', 'icmp_echo_ignore_broadcasts', '1',           'medium'),
    -- System Hardening
    ('system', 'selinux_mode',               'enforcing',     'high'),
    ('system', 'umask',                      '027',           'medium'),
    ('system', 'core_dumps_restricted',      'true',          'medium'),
    ('system', 'aslr_enabled',               'true',          'high'),
    ('system', 'suid_binaries_audited',      'true',          'medium')
ON CONFLICT (component, check_name) DO NOTHING;

-- =============================================================================
-- 3) Standard Rate-Limits
-- =============================================================================
INSERT INTO dbai_security.rate_limits (target_type, target_value, max_requests, window_seconds) VALUES
    ('endpoint', '/api/auth/login',      10,   60),    -- 10 Login-Versuche/min
    ('endpoint', '/api/auth/register',   5,    60),    -- 5 Registrierungen/min
    ('endpoint', '/api/chat/send',       30,   60),    -- 30 Chat-Nachrichten/min
    ('endpoint', '/api/apps/install',    5,    300),   -- 5 App-Installs/5min
    ('endpoint', '/api/firewall/rules',  10,   60),    -- 10 Firewall-Änderungen/min
    ('endpoint', '/api/system/shutdown',  1,    300),   -- 1 Shutdown/5min
    ('global',   'total',               1000,  60),    -- 1000 Requests/min global
    ('global',   'websocket',           500,   60)     -- 500 WebSocket-Msgs/min
ON CONFLICT (target_type, target_value) DO NOTHING;

-- =============================================================================
-- 4) DNS-Sinkhole Basis-Einträge
-- =============================================================================
INSERT INTO dbai_security.dns_sinkhole (domain, category, source) VALUES
    -- Bekannte Cryptominer
    ('coinhive.com',            'cryptomining', 'builtin'),
    ('coin-hive.com',           'cryptomining', 'builtin'),
    ('crypto-loot.com',         'cryptomining', 'builtin'),
    ('jsecoin.com',             'cryptomining', 'builtin'),
    ('authedmine.com',          'cryptomining', 'builtin'),
    ('coinhive.min.js',         'cryptomining', 'builtin'),
    ('webmine.pro',             'cryptomining', 'builtin'),
    ('ppoi.org',                'cryptomining', 'builtin'),
    -- Bekannte Malware-Domains (Beispiele)
    ('malware.wicar.org',       'malware',      'builtin'),
    ('eicar.org',               'malware',      'builtin'),
    -- Tracking-Domains
    ('tracking.example.invalid','tracking',     'builtin')
ON CONFLICT (domain) DO NOTHING;

-- =============================================================================
-- 5) Bekannte CVEs für installierte Pakete
-- =============================================================================
INSERT INTO dbai_security.cve_tracking (cve_id, title, affected_pkg, source_url, is_relevant) VALUES
    ('CVE-2024-10979', 'PostgreSQL PL/Perl env variable bypass', 'postgresql-16', 'https://www.postgresql.org/support/security/', true),
    ('CVE-2024-7348',  'PostgreSQL pg_dump role access', 'postgresql-16', 'https://www.postgresql.org/support/security/', true),
    ('CVE-2024-4317',  'PostgreSQL pg_stats_ext view leak', 'postgresql-16', 'https://www.postgresql.org/support/security/', true)
ON CONFLICT (cve_id) DO NOTHING;

-- =============================================================================
-- 6) System-Memory Eintrag (Knowledge-Schema)
-- =============================================================================
INSERT INTO dbai_knowledge.system_memory (category, title, content, tags, author)
VALUES (
    'security',
    'Immunsystem-Architektur v0.15.0',
    'GhostShell OS v0.15.0 besitzt ein Security-Immunsystem basierend auf einer '
    'Rückkopplungsschleife zur Selbstregulierung. Komponenten: '
    '(1) Kali-Linux-Sidecar-Container mit sqlmap, nmap, nuclei, suricata, fail2ban, lynis. '
    '(2) Automatisierte Self-Penetration-Tests gegen eigene API-Endpunkte. '
    '(3) Fail2Ban direkt mit PostgreSQL-Logs verknüpft — 3 Fehlversuche = IP-Ban auf Hardware-Ebene. '
    '(4) Intrusion Detection System (Suricata) für Netzwerkverkehr. '
    '(5) Honeypot-Fallen auf typischen Angriffs-Ports (SSH, MySQL, Admin). '
    '(6) DNS-Sinkhole für Malware/Phishing/Cryptomining-Domains. '
    '(7) Netzwerk-Firewall mit Anti-Scanning, SYN-Flood-Schutz, Brute-Force-Schutz. '
    '(8) TLS-Zertifikats-Überwachung mit Auto-Renewal. '
    '(9) CVE-Tracking für installierte Pakete. '
    '(10) Security-Baseline-Audits (CIS Benchmark). '
    'Schema: dbai_security mit 16 Tabellen, 3 Auto-Response-Triggern, Append-Only-Schutz. '
    'Feedback-Loop: Scan → Finding → Auto-Mitigation → Firewall-Update → Erneuter Scan.',
    ARRAY['security', 'immunsystem', 'firewall', 'ids', 'fail2ban'],
    'system'
)
ON CONFLICT DO NOTHING;

INSERT INTO dbai_knowledge.system_memory (category, title, content, tags, author)
VALUES (
    'architecture',
    'Security-Sidecar Docker-Architektur',
    'Der Kali-Linux-Sidecar-Container (dbai-security-sidecar) läuft neben dem Hauptsystem als '
    'Security-Wächter. Er hat privilegierten Zugriff auf das Netzwerk (NET_ADMIN, NET_RAW) und '
    'wird über docker compose --profile security aktiviert. Der Container enthält: '
    'sqlmap, nmap, nikto, nuclei, suricata, fail2ban, hydra, lynis, sslscan, testssl.sh. '
    'Alle Scan-Ergebnisse werden in dbai_security-Tabellen geschrieben. '
    'Cron-Jobs steuern die automatische Wiederholung der Scans.',
    ARRAY['architecture', 'docker', 'kali', 'security'],
    'system'
)
ON CONFLICT DO NOTHING;

INSERT INTO dbai_knowledge.system_memory (category, title, content, tags, author)
VALUES (
    'security',
    'Fail2Ban PostgreSQL Integration',
    'Fail2Ban ist direkt mit den PostgreSQL-Logs verknüpft. '
    'Wenn jemand 3 Mal ein falsches Passwort am SQL-Port (5432) versucht, '
    'sperrt das System die IP sofort auf Hardware-Ebene (iptables) aus. '
    'Konfiguration: /etc/fail2ban/jail.d/dbai.conf mit Filtern für '
    'PostgreSQL (dbai-postgresql), API (dbai-api), SSH (dbai-ssh), Port-Scans (dbai-portscan). '
    'Bans werden in dbai_security.ip_bans gespeichert und mit iptables synchronisiert. '
    'Wiederholungstäter (recidive) werden für 30 Tage gebannt.',
    ARRAY['fail2ban', 'postgresql', 'iptables', 'security'],
    'system'
)
ON CONFLICT DO NOTHING;

-- =============================================================================
-- 7) App-Registrierung: Security-Dashboard
-- =============================================================================
INSERT INTO dbai_ui.apps (app_id, name, description, icon, category, is_system, source_type, source_target, default_width, default_height)
VALUES (
    'security-dashboard',
    'Sicherheit',
    'Security-Immunsystem Dashboard: Schwachstellen, IDS-Alerts, IP-Bans, '
    'Firewall-Regeln, Threat-Intelligence, Scan-Status, Compliance-Score.',
    'shield',
    'system',
    true,
    'component',
    'SecurityDashboard',
    1100,
    750
)
ON CONFLICT DO NOTHING;

COMMIT;
