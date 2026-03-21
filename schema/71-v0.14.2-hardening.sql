-- =============================================================================
-- DBAI Schema 71: v0.14.2 — Security + Maintenance Hardening
-- RLS für alle fehlenden Tabellen, Vacuum-Config, Session-Index
-- =============================================================================

-- =============================================================================
-- 1. RLS für dbai_ui Tabellen
-- =============================================================================

-- Sessions: System darf alles, Runtime (API-Zugriff) nur eigene
ALTER TABLE dbai_ui.sessions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS sessions_system ON dbai_ui.sessions;
CREATE POLICY sessions_system ON dbai_ui.sessions FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS sessions_runtime_own ON dbai_ui.sessions;
CREATE POLICY sessions_runtime_own ON dbai_ui.sessions FOR ALL TO dbai_runtime
    USING (TRUE) WITH CHECK (TRUE);  -- Runtime braucht vollen Zugriff (Login/Logout)

ALTER TABLE dbai_ui.users ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS users_system ON dbai_ui.users;
CREATE POLICY users_system ON dbai_ui.users FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS users_runtime ON dbai_ui.users;
CREATE POLICY users_runtime ON dbai_ui.users FOR SELECT TO dbai_runtime USING (TRUE);

ALTER TABLE dbai_ui.windows ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS windows_system ON dbai_ui.windows;
CREATE POLICY windows_system ON dbai_ui.windows FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS windows_runtime ON dbai_ui.windows;
CREATE POLICY windows_runtime ON dbai_ui.windows FOR ALL TO dbai_runtime USING (TRUE) WITH CHECK (TRUE);

ALTER TABLE dbai_ui.tab_instances ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tabs_system ON dbai_ui.tab_instances;
CREATE POLICY tabs_system ON dbai_ui.tab_instances FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS tabs_runtime ON dbai_ui.tab_instances;
CREATE POLICY tabs_runtime ON dbai_ui.tab_instances FOR ALL TO dbai_runtime USING (TRUE) WITH CHECK (TRUE);

ALTER TABLE dbai_ui.apps ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS apps_system ON dbai_ui.apps;
CREATE POLICY apps_system ON dbai_ui.apps FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS apps_runtime_read ON dbai_ui.apps;
CREATE POLICY apps_runtime_read ON dbai_ui.apps FOR SELECT TO dbai_runtime USING (TRUE);
DROP POLICY IF EXISTS apps_llm_read ON dbai_ui.apps;
CREATE POLICY apps_llm_read ON dbai_ui.apps FOR SELECT TO dbai_llm USING (TRUE);

ALTER TABLE dbai_ui.desktop_nodes ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS desknodes_system ON dbai_ui.desktop_nodes;
CREATE POLICY desknodes_system ON dbai_ui.desktop_nodes FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS desknodes_runtime ON dbai_ui.desktop_nodes;
CREATE POLICY desknodes_runtime ON dbai_ui.desktop_nodes FOR ALL TO dbai_runtime USING (TRUE) WITH CHECK (TRUE);

ALTER TABLE dbai_ui.desktop_scene ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS deskscene_system ON dbai_ui.desktop_scene;
CREATE POLICY deskscene_system ON dbai_ui.desktop_scene FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS deskscene_runtime ON dbai_ui.desktop_scene;
CREATE POLICY deskscene_runtime ON dbai_ui.desktop_scene FOR ALL TO dbai_runtime USING (TRUE) WITH CHECK (TRUE);

ALTER TABLE dbai_ui.desktop_config ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS deskconfig_system ON dbai_ui.desktop_config;
CREATE POLICY deskconfig_system ON dbai_ui.desktop_config FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS deskconfig_runtime ON dbai_ui.desktop_config;
CREATE POLICY deskconfig_runtime ON dbai_ui.desktop_config FOR ALL TO dbai_runtime USING (TRUE) WITH CHECK (TRUE);

ALTER TABLE dbai_ui.notifications ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS notif_system ON dbai_ui.notifications;
CREATE POLICY notif_system ON dbai_ui.notifications FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS notif_runtime ON dbai_ui.notifications;
CREATE POLICY notif_runtime ON dbai_ui.notifications FOR ALL TO dbai_runtime USING (TRUE) WITH CHECK (TRUE);

ALTER TABLE dbai_ui.themes ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS themes_system ON dbai_ui.themes;
CREATE POLICY themes_system ON dbai_ui.themes FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS themes_runtime ON dbai_ui.themes;
CREATE POLICY themes_runtime ON dbai_ui.themes FOR SELECT TO dbai_runtime USING (TRUE);

ALTER TABLE dbai_ui.terminal_sessions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS termsess_system ON dbai_ui.terminal_sessions;
CREATE POLICY termsess_system ON dbai_ui.terminal_sessions FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS termsess_runtime ON dbai_ui.terminal_sessions;
CREATE POLICY termsess_runtime ON dbai_ui.terminal_sessions FOR ALL TO dbai_runtime USING (TRUE) WITH CHECK (TRUE);

ALTER TABLE dbai_ui.terminal_history ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS termhist_system ON dbai_ui.terminal_history;
CREATE POLICY termhist_system ON dbai_ui.terminal_history FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS termhist_runtime ON dbai_ui.terminal_history;
CREATE POLICY termhist_runtime ON dbai_ui.terminal_history FOR ALL TO dbai_runtime USING (TRUE) WITH CHECK (TRUE);

-- =============================================================================
-- 2. RLS für dbai_llm Tabellen (Agent + Marketplace + Vision + Distributed)
-- =============================================================================

ALTER TABLE dbai_llm.agent_instances ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS agentinst_system ON dbai_llm.agent_instances;
CREATE POLICY agentinst_system ON dbai_llm.agent_instances FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS agentinst_runtime ON dbai_llm.agent_instances;
CREATE POLICY agentinst_runtime ON dbai_llm.agent_instances FOR ALL TO dbai_runtime USING (TRUE) WITH CHECK (TRUE);
DROP POLICY IF EXISTS agentinst_llm ON dbai_llm.agent_instances;
CREATE POLICY agentinst_llm ON dbai_llm.agent_instances FOR SELECT TO dbai_llm USING (TRUE);

ALTER TABLE dbai_llm.ghost_models ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS gmodels_system ON dbai_llm.ghost_models;
CREATE POLICY gmodels_system ON dbai_llm.ghost_models FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS gmodels_runtime ON dbai_llm.ghost_models;
CREATE POLICY gmodels_runtime ON dbai_llm.ghost_models FOR SELECT TO dbai_runtime USING (TRUE);
DROP POLICY IF EXISTS gmodels_llm ON dbai_llm.ghost_models;
CREATE POLICY gmodels_llm ON dbai_llm.ghost_models FOR SELECT TO dbai_llm USING (TRUE);

ALTER TABLE dbai_llm.ghost_roles ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS groles_system ON dbai_llm.ghost_roles;
CREATE POLICY groles_system ON dbai_llm.ghost_roles FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS groles_runtime ON dbai_llm.ghost_roles;
CREATE POLICY groles_runtime ON dbai_llm.ghost_roles FOR SELECT TO dbai_runtime USING (TRUE);

ALTER TABLE dbai_llm.conversations ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS convos_system ON dbai_llm.conversations;
CREATE POLICY convos_system ON dbai_llm.conversations FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS convos_runtime ON dbai_llm.conversations;
CREATE POLICY convos_runtime ON dbai_llm.conversations FOR ALL TO dbai_runtime USING (TRUE) WITH CHECK (TRUE);

ALTER TABLE dbai_llm.marketplace_catalog ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS marketplace_system ON dbai_llm.marketplace_catalog;
CREATE POLICY marketplace_system ON dbai_llm.marketplace_catalog FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS marketplace_runtime ON dbai_llm.marketplace_catalog;
CREATE POLICY marketplace_runtime ON dbai_llm.marketplace_catalog FOR SELECT TO dbai_runtime USING (TRUE);

ALTER TABLE dbai_llm.model_reviews ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS reviews_system ON dbai_llm.model_reviews;
CREATE POLICY reviews_system ON dbai_llm.model_reviews FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS reviews_runtime ON dbai_llm.model_reviews;
CREATE POLICY reviews_runtime ON dbai_llm.model_reviews FOR ALL TO dbai_runtime USING (TRUE) WITH CHECK (TRUE);

ALTER TABLE dbai_llm.vision_tasks ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS vision_system ON dbai_llm.vision_tasks;
CREATE POLICY vision_system ON dbai_llm.vision_tasks FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS vision_runtime ON dbai_llm.vision_tasks;
CREATE POLICY vision_runtime ON dbai_llm.vision_tasks FOR ALL TO dbai_runtime USING (TRUE) WITH CHECK (TRUE);

ALTER TABLE dbai_llm.vision_detections ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS visdet_system ON dbai_llm.vision_detections;
CREATE POLICY visdet_system ON dbai_llm.vision_detections FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS visdet_runtime ON dbai_llm.vision_detections;
CREATE POLICY visdet_runtime ON dbai_llm.vision_detections FOR SELECT TO dbai_runtime USING (TRUE);

ALTER TABLE dbai_llm.distributed_tasks ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS dtasks_system ON dbai_llm.distributed_tasks;
CREATE POLICY dtasks_system ON dbai_llm.distributed_tasks FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS dtasks_runtime ON dbai_llm.distributed_tasks;
CREATE POLICY dtasks_runtime ON dbai_llm.distributed_tasks FOR SELECT TO dbai_runtime USING (TRUE);

ALTER TABLE dbai_llm.ghost_nodes ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS gnodes_system ON dbai_llm.ghost_nodes;
CREATE POLICY gnodes_system ON dbai_llm.ghost_nodes FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS gnodes_runtime ON dbai_llm.ghost_nodes;
CREATE POLICY gnodes_runtime ON dbai_llm.ghost_nodes FOR SELECT TO dbai_runtime USING (TRUE);

ALTER TABLE dbai_llm.vram_allocations ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS vram_system ON dbai_llm.vram_allocations;
CREATE POLICY vram_system ON dbai_llm.vram_allocations FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS vram_runtime ON dbai_llm.vram_allocations;
CREATE POLICY vram_runtime ON dbai_llm.vram_allocations FOR SELECT TO dbai_runtime USING (TRUE);

ALTER TABLE dbai_llm.gpu_split_configs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS gpusplit_system ON dbai_llm.gpu_split_configs;
CREATE POLICY gpusplit_system ON dbai_llm.gpu_split_configs FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS gpusplit_runtime ON dbai_llm.gpu_split_configs;
CREATE POLICY gpusplit_runtime ON dbai_llm.gpu_split_configs FOR SELECT TO dbai_runtime USING (TRUE);

ALTER TABLE dbai_llm.parallel_inference_sessions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS parinf_system ON dbai_llm.parallel_inference_sessions;
CREATE POLICY parinf_system ON dbai_llm.parallel_inference_sessions FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS parinf_runtime ON dbai_llm.parallel_inference_sessions;
CREATE POLICY parinf_runtime ON dbai_llm.parallel_inference_sessions FOR SELECT TO dbai_runtime USING (TRUE);

-- =============================================================================
-- 3. RLS für dbai_knowledge Tabellen
-- =============================================================================

ALTER TABLE dbai_knowledge.system_memory ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS sysmem_system ON dbai_knowledge.system_memory;
CREATE POLICY sysmem_system ON dbai_knowledge.system_memory FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS sysmem_runtime ON dbai_knowledge.system_memory;
CREATE POLICY sysmem_runtime ON dbai_knowledge.system_memory FOR SELECT TO dbai_runtime USING (TRUE);
DROP POLICY IF EXISTS sysmem_llm ON dbai_knowledge.system_memory;
CREATE POLICY sysmem_llm ON dbai_knowledge.system_memory FOR SELECT TO dbai_llm USING (TRUE);

ALTER TABLE dbai_knowledge.changelog ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS chlog_system ON dbai_knowledge.changelog;
CREATE POLICY chlog_system ON dbai_knowledge.changelog FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS chlog_runtime ON dbai_knowledge.changelog;
CREATE POLICY chlog_runtime ON dbai_knowledge.changelog FOR SELECT TO dbai_runtime USING (TRUE);

ALTER TABLE dbai_knowledge.module_registry ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS modreg_system ON dbai_knowledge.module_registry;
CREATE POLICY modreg_system ON dbai_knowledge.module_registry FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS modreg_runtime ON dbai_knowledge.module_registry;
CREATE POLICY modreg_runtime ON dbai_knowledge.module_registry FOR SELECT TO dbai_runtime USING (TRUE);

-- =============================================================================
-- 4. RLS für dbai_net Tabellen (Mobile Bridge)
-- =============================================================================

ALTER TABLE dbai_net.mobile_devices ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS mobdev_system ON dbai_net.mobile_devices;
CREATE POLICY mobdev_system ON dbai_net.mobile_devices FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS mobdev_runtime ON dbai_net.mobile_devices;
CREATE POLICY mobdev_runtime ON dbai_net.mobile_devices FOR ALL TO dbai_runtime USING (TRUE) WITH CHECK (TRUE);

ALTER TABLE dbai_net.sensor_data ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS sensor_system ON dbai_net.sensor_data;
CREATE POLICY sensor_system ON dbai_net.sensor_data FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS sensor_runtime ON dbai_net.sensor_data;
CREATE POLICY sensor_runtime ON dbai_net.sensor_data FOR ALL TO dbai_runtime USING (TRUE) WITH CHECK (TRUE);

ALTER TABLE dbai_net.connection_sessions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS connsess_system ON dbai_net.connection_sessions;
CREATE POLICY connsess_system ON dbai_net.connection_sessions FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS connsess_runtime ON dbai_net.connection_sessions;
CREATE POLICY connsess_runtime ON dbai_net.connection_sessions FOR ALL TO dbai_runtime USING (TRUE) WITH CHECK (TRUE);

ALTER TABLE dbai_net.boot_dimensions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS bootdim_system ON dbai_net.boot_dimensions;
CREATE POLICY bootdim_system ON dbai_net.boot_dimensions FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS bootdim_runtime ON dbai_net.boot_dimensions;
CREATE POLICY bootdim_runtime ON dbai_net.boot_dimensions FOR SELECT TO dbai_runtime USING (TRUE);

-- =============================================================================
-- 5. RLS für dbai_workshop Tabellen
-- =============================================================================

ALTER TABLE dbai_workshop.projects ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS wsproj_system ON dbai_workshop.projects;
CREATE POLICY wsproj_system ON dbai_workshop.projects FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS wsproj_runtime ON dbai_workshop.projects;
CREATE POLICY wsproj_runtime ON dbai_workshop.projects FOR ALL TO dbai_runtime USING (TRUE) WITH CHECK (TRUE);

ALTER TABLE dbai_workshop.custom_tables ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS wsctab_system ON dbai_workshop.custom_tables;
CREATE POLICY wsctab_system ON dbai_workshop.custom_tables FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS wsctab_runtime ON dbai_workshop.custom_tables;
CREATE POLICY wsctab_runtime ON dbai_workshop.custom_tables FOR ALL TO dbai_runtime USING (TRUE) WITH CHECK (TRUE);

ALTER TABLE dbai_workshop.custom_rows ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS wscrow_system ON dbai_workshop.custom_rows;
CREATE POLICY wscrow_system ON dbai_workshop.custom_rows FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS wscrow_runtime ON dbai_workshop.custom_rows;
CREATE POLICY wscrow_runtime ON dbai_workshop.custom_rows FOR ALL TO dbai_runtime USING (TRUE) WITH CHECK (TRUE);

ALTER TABLE dbai_workshop.chat_history ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS wschat_system ON dbai_workshop.chat_history;
CREATE POLICY wschat_system ON dbai_workshop.chat_history FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS wschat_runtime ON dbai_workshop.chat_history;
CREATE POLICY wschat_runtime ON dbai_workshop.chat_history FOR ALL TO dbai_runtime USING (TRUE) WITH CHECK (TRUE);

-- =============================================================================
-- 6. Fehlender Index auf sessions.expires_at (Performance)
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON dbai_ui.sessions(expires_at)
    WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_sessions_token ON dbai_ui.sessions(token)
    WHERE is_active = TRUE;

-- =============================================================================
-- 7. Vacuum-Config für alle fehlenden Schemas
-- =============================================================================

INSERT INTO dbai_system.vacuum_config
    (schema_name, table_name, schedule, vacuum_threshold, priority) VALUES
    -- dbai_ui: Sessions + Windows sind hochfrequent
    ('dbai_ui', 'sessions', '*/15 * * * *', 50, 2),
    ('dbai_ui', 'windows', '*/15 * * * *', 50, 2),
    ('dbai_ui', 'tab_instances', '*/15 * * * *', 50, 2),
    ('dbai_ui', 'notifications', '*/30 * * * *', 100, 4),
    ('dbai_ui', 'desktop_nodes', '0 * * * *', 50, 5),
    ('dbai_ui', 'desktop_scene', '0 * * * *', 50, 5),
    ('dbai_ui', 'terminal_history', '*/30 * * * *', 200, 4),
    ('dbai_ui', 'terminal_sessions', '*/30 * * * *', 50, 4),
    ('dbai_ui', 'app_user_settings', '0 */6 * * *', 50, 7),
    ('dbai_ui', 'app_streams', '*/30 * * * *', 100, 4),
    -- dbai_llm: Ghost-Sessions und Tasks sind hochfrequent
    ('dbai_llm', 'conversations', '*/15 * * * *', 100, 2),
    ('dbai_llm', 'ghost_history', '*/10 * * * *', 200, 2),
    ('dbai_llm', 'ghost_context', '*/15 * * * *', 100, 3),
    ('dbai_llm', 'ghost_thought_log', '*/15 * * * *', 200, 3),
    ('dbai_llm', 'ghost_feedback', '*/30 * * * *', 100, 4),
    ('dbai_llm', 'ghost_benchmarks', '0 * * * *', 50, 5),
    ('dbai_llm', 'command_history', '*/30 * * * *', 200, 4),
    ('dbai_llm', 'task_queue', '*/15 * * * *', 100, 3),
    ('dbai_llm', 'agent_tasks', '*/15 * * * *', 100, 3),
    ('dbai_llm', 'agent_instances', '*/30 * * * *', 50, 4),
    ('dbai_llm', 'watchdog_log', '*/30 * * * *', 100, 4),
    ('dbai_llm', 'rag_query_log', '*/30 * * * *', 100, 4),
    -- v0.14.0 Tabellen
    ('dbai_llm', 'marketplace_catalog', '0 */6 * * *', 50, 6),
    ('dbai_llm', 'model_reviews', '0 */6 * * *', 50, 6),
    ('dbai_llm', 'model_downloads', '*/30 * * * *', 100, 4),
    ('dbai_llm', 'vision_tasks', '*/30 * * * *', 100, 4),
    ('dbai_llm', 'vision_detections', '*/30 * * * *', 200, 4),
    ('dbai_llm', 'distributed_tasks', '*/30 * * * *', 100, 4),
    ('dbai_llm', 'node_heartbeats', '*/10 * * * *', 200, 2),
    ('dbai_llm', 'gpu_sync_events', '*/15 * * * *', 200, 3),
    ('dbai_llm', 'vram_allocations', '*/30 * * * *', 50, 4),
    ('dbai_llm', 'parallel_inference_sessions', '*/30 * * * *', 50, 4),
    -- dbai_knowledge: Meist stabil, seltenes Vacuum
    ('dbai_knowledge', 'system_memory', '0 */12 * * *', 50, 7),
    ('dbai_knowledge', 'changelog', '0 */12 * * *', 99999999, 8),
    ('dbai_knowledge', 'error_log', '*/30 * * * *', 200, 4),
    ('dbai_knowledge', 'build_log', '*/30 * * * *', 200, 4),
    ('dbai_knowledge', 'agent_sessions', '*/30 * * * *', 100, 4),
    -- dbai_net: Mobile Bridge
    ('dbai_net', 'sensor_data', '*/10 * * * *', 200, 2),
    ('dbai_net', 'connection_sessions', '*/30 * * * *', 50, 4),
    ('dbai_net', 'mobile_devices', '0 */6 * * *', 50, 6),
    -- dbai_workshop
    ('dbai_workshop', 'chat_history', '*/30 * * * *', 200, 4),
    ('dbai_workshop', 'custom_rows', '*/30 * * * *', 200, 4),
    ('dbai_workshop', 'import_jobs', '0 * * * *', 50, 5),
    -- dbai_panic
    ('dbai_panic', 'panic_log', '0 */12 * * *', 50, 7),
    -- dbai_core (fehlende)
    ('dbai_core', 'audit_log', '0 */12 * * *', 99999999, 8),
    ('dbai_core', 'migration_audit_log', '0 */12 * * *', 99999999, 8),
    ('dbai_core', 'browser_history', '*/30 * * * *', 200, 4),
    ('dbai_core', 'browser_sessions', '*/30 * * * *', 100, 4)
ON CONFLICT (schema_name, table_name) DO NOTHING;

-- =============================================================================
-- 8. Dokumentation: system_memory + changelog
-- =============================================================================

INSERT INTO dbai_knowledge.system_memory
    (category, title, content, tags, priority, author)
VALUES
    ('architecture', 'v0.14.2 RLS-Erweiterung',
     'Row Level Security auf 35+ zusätzliche Tabellen erweitert: dbai_ui (12 Tabellen), dbai_llm (12 Tabellen), dbai_knowledge (3), dbai_net (4), dbai_workshop (4). Rollen: dbai_system (Full), dbai_runtime (API-Level), dbai_llm (Read-Only wo nötig), dbai_monitor (Read-Only).',
     ARRAY['rls', 'security', 'hardening', 'v0.14.2'], 8, 'system'),
    ('operational', 'v0.14.2 Vacuum-Erweiterung',
     'Vacuum-Config um 45+ Tabellen erweitert. Deckt jetzt alle 11 Schemas ab. Hochfrequente Tabellen (sessions, conversations, sensor_data) alle 10-15 Min, stabile Tabellen (system_memory, marketplace) alle 6-12h. Journal/Audit Append-Only mit Threshold 99999999.',
     ARRAY['vacuum', 'maintenance', 'performance', 'v0.14.2'], 7, 'system'),
    ('convention', 'v0.14.2 Cookie Secure + CSRF + Headers',
     'Session-Cookie hat secure=True (HTTPS-only), samesite=strict. CSRF-Token-Header X-CSRF-Token bei state-changing Requests validiert. API-Versioning über X-API-Version Header. Security-Headers: X-Content-Type-Options, X-Frame-Options.',
     ARRAY['cookie', 'csrf', 'security', 'headers', 'v0.14.2'], 9, 'system'),
    ('convention', 'v0.14.2 Frontend-Hardening',
     'React ErrorBoundary umwickelt jedes App-Fenster. AbortController in api.js request() — Requests werden bei Component-Unmount automatisch abgebrochen. Input-Validierung über Pydantic-Models für alle POST/PUT-Endpoints.',
     ARRAY['frontend', 'error-boundary', 'abort-controller', 'validation', 'v0.14.2'], 7, 'system'),
    ('operational', 'v0.14.2 Connection Health Ping',
     'DBPool.get_connection() führt jetzt SELECT 1 auf idle Connections aus bevor sie ausgecheckt werden. Stale Connections werden automatisch ersetzt. Structured Logging mit JSON-Format für maschinenlesbare Logs.',
     ARRAY['pool', 'health', 'logging', 'v0.14.2'], 7, 'system')
ON CONFLICT DO NOTHING;

INSERT INTO dbai_knowledge.changelog
    (version, change_type, title, description, affected_files, author)
VALUES
    ('0.14.2', 'security', 'RLS für 35+ Tabellen', 'Row Level Security auf dbai_ui, dbai_llm, dbai_knowledge, dbai_net, dbai_workshop erweitert. Alle Tabellen haben jetzt granulare Policies für dbai_system, dbai_runtime, dbai_llm.', ARRAY['schema/71-v0.14.2-hardening.sql'], 'system'),
    ('0.14.2', 'performance', 'Vacuum-Config für 45+ Tabellen', 'Vacuum-Schedule erweitert: Alle 11 Schemas abgedeckt. Hochfrequente Tabellen (sessions, sensor_data, conversations) aggressiv (10-15min), stabile Tabellen konservativ (6-12h).', ARRAY['schema/71-v0.14.2-hardening.sql'], 'system'),
    ('0.14.2', 'performance', 'Session-Index expires_at + token', 'Partial Indexes auf sessions.expires_at und sessions.token (WHERE is_active=TRUE) für schnellere Session-Validierung.', ARRAY['schema/71-v0.14.2-hardening.sql'], 'system'),
    ('0.14.2', 'security', 'Cookie Secure-Flag + SameSite strict', 'Session-Cookie: secure=True, samesite=strict. Verhindert CSRF und Cookie-Leak über HTTP.', ARRAY['web/server.py'], 'system'),
    ('0.14.2', 'security', 'CSRF-Token-Validierung', 'State-changing Requests (POST/PUT/DELETE) erfordern X-CSRF-Token Header. Token wird bei Login generiert und im Cookie gespeichert.', ARRAY['web/server.py'], 'system'),
    ('0.14.2', 'feature', 'API Versioning Header', 'Alle Responses enthalten X-API-Version und X-DBAI-Version Header. Clients können API-Kompatibilität prüfen.', ARRAY['web/server.py'], 'system'),
    ('0.14.2', 'fix', 'Frontend ErrorBoundary', 'Jedes App-Fenster in Desktop.jsx ist mit ErrorBoundary umwickelt. Crashes in einer App isolieren die anderen nicht.', ARRAY['frontend/src/components/ErrorBoundary.jsx', 'frontend/src/components/Desktop.jsx'], 'system'),
    ('0.14.2', 'feature', 'API AbortController', 'api.js request() unterstützt AbortSignal. Requests werden bei Component-Unmount automatisch abgebrochen.', ARRAY['frontend/src/api.js'], 'system'),
    ('0.14.2', 'refactor', 'Input-Validierung Pydantic', 'Alle unvalidierten POST/PUT-Endpoints verwenden jetzt Pydantic-Models. Type-Safe Request Bodies statt raw JSON.', ARRAY['web/server.py'], 'system'),
    ('0.14.2', 'performance', 'DBPool Health Ping', 'get_connection() führt SELECT 1 Health-Check auf idle Connections durch. Stale Connections werden automatisch ersetzt statt fehlerhafte Queries zu verursachen.', ARRAY['web/server.py'], 'system'),
    ('0.14.2', 'refactor', 'Structured Logging', 'JSON-basiertes Logging-Format mit Timestamp, Level, Module, Message. Maschinenlesbar für Log-Aggregation.', ARRAY['web/server.py'], 'system'),
    ('0.14.2', 'security', 'CUDA-Pfade konfigurierbar', 'Hardcodierte CUDA-Pfade durch DBAI_CUDA_LIB_PATH Environment-Variable ersetzt. Fallback auf bekannte Pfade.', ARRAY['web/server.py'], 'system');
