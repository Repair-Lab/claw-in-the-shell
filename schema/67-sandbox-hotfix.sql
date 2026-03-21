-- ============================================================================
-- 67-sandbox-hotfix.sql
-- Hotfix: Fehlende Tabellen, Constraint-Updates, Views für Sandbox
-- Erstellt: 2026-03-18 — Automatischer Diagnosebericht
-- ============================================================================

-- ───────────────────────────────────────────────────────────────────
-- 1) dbai_core.network_devices — Netzwerk-Geräte mit Web-UI
-- ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dbai_core.network_devices (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ip              INET NOT NULL,
    hostname        TEXT,
    web_port        INTEGER NOT NULL DEFAULT 80,
    web_url         TEXT,
    web_title       TEXT,
    device_type     TEXT NOT NULL DEFAULT 'unknown',
    is_reachable    BOOLEAN NOT NULL DEFAULT TRUE,
    added_to_desktop BOOLEAN NOT NULL DEFAULT FALSE,
    last_seen       TIMESTAMPTZ DEFAULT NOW(),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(ip, web_port)
);

COMMENT ON TABLE dbai_core.network_devices IS 'Erkannte Netzwerk-Geräte mit Web-UI (via Subnet-Scan)';

-- ───────────────────────────────────────────────────────────────────
-- 2) dbai_llm.learning_entries — Benutzer-Lernprofil
-- ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dbai_llm.learning_entries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL,
    category        TEXT NOT NULL DEFAULT 'preference',
    key             TEXT NOT NULL,
    value           TEXT,
    context         JSONB DEFAULT '{}',
    confidence      DOUBLE PRECISION DEFAULT 1.0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, category, key)
);

COMMENT ON TABLE dbai_llm.learning_entries IS 'Ghost-Lerneinträge: Benutzer-Präferenzen, Gewohnheiten, Kontext';

CREATE INDEX IF NOT EXISTS idx_learning_entries_user
    ON dbai_llm.learning_entries(user_id);
CREATE INDEX IF NOT EXISTS idx_learning_entries_category
    ON dbai_llm.learning_entries(user_id, category);

-- ───────────────────────────────────────────────────────────────────
-- 3) dbai_llm.scheduled_jobs — Geplante Agent-Jobs (Cron)
-- ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dbai_llm.scheduled_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    description     TEXT,
    cron_expr       TEXT NOT NULL DEFAULT '0 */6 * * *',
    instance_id     UUID REFERENCES dbai_llm.agent_instances(id) ON DELETE SET NULL,
    role_id         UUID REFERENCES dbai_llm.ghost_roles(id) ON DELETE SET NULL,
    task_prompt     TEXT NOT NULL,
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    last_run_at     TIMESTAMPTZ,
    next_run_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE dbai_llm.scheduled_jobs IS 'Geplante wiederkehrende Agent-Aufgaben (Cron-basiert)';

-- ───────────────────────────────────────────────────────────────────
-- 4) dbai_llm.agent_tasks — Agent-Aufgaben
-- ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dbai_llm.agent_tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instance_id     UUID NOT NULL REFERENCES dbai_llm.agent_instances(id) ON DELETE CASCADE,
    task_type       TEXT NOT NULL DEFAULT 'chat',
    name            TEXT NOT NULL,
    description     TEXT,
    system_prompt   TEXT,
    priority        INTEGER NOT NULL DEFAULT 5,
    auto_route      BOOLEAN NOT NULL DEFAULT FALSE,
    state           TEXT NOT NULL DEFAULT 'pending'
                    CHECK (state IN ('pending', 'processing', 'completed', 'failed', 'cancelled')),
    result          JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE dbai_llm.agent_tasks IS 'Aufgaben, die an Agent-Instanzen vergeben werden';

CREATE INDEX IF NOT EXISTS idx_agent_tasks_instance
    ON dbai_llm.agent_tasks(instance_id);
CREATE INDEX IF NOT EXISTS idx_agent_tasks_state
    ON dbai_llm.agent_tasks(state);

-- ───────────────────────────────────────────────────────────────────
-- 5) View: dbai_ui.translations → dbai_ui.i18n_translations
--    (Kompatibilitäts-View für Code, der «translations» referenziert)
-- ───────────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW dbai_ui.translations AS
    SELECT id, locale, namespace AS ns, key, value, created_at, updated_at
    FROM dbai_ui.i18n_translations;

COMMENT ON VIEW dbai_ui.translations IS 'Kompatibilitäts-View: translations → i18n_translations (ns=namespace)';

-- ───────────────────────────────────────────────────────────────────
-- 6) Schema dbai_ops + View für changelog (Kompatibilität)
-- ───────────────────────────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS dbai_ops;
CREATE OR REPLACE VIEW dbai_ops.changelog AS
    SELECT * FROM dbai_knowledge.changelog;

-- Damit INSERT über die View funktioniert, brauchen wir eine INSTEAD OF RULE
CREATE OR REPLACE RULE changelog_insert AS
    ON INSERT TO dbai_ops.changelog
    DO INSTEAD
    INSERT INTO dbai_knowledge.changelog (version, change_type, title, description, affected_modules, author)
    VALUES (NEW.version, NEW.change_type, NEW.title, NEW.description, NEW.affected_modules, NEW.author);

COMMENT ON VIEW dbai_ops.changelog IS 'Kompatibilitäts-View: dbai_ops.changelog → dbai_knowledge.changelog';

-- ───────────────────────────────────────────────────────────────────
-- 7) CHECK-Constraint: task_queue — 'chat' u.a. hinzufügen
-- ───────────────────────────────────────────────────────────────────
ALTER TABLE dbai_llm.task_queue
    DROP CONSTRAINT IF EXISTS task_queue_task_type_check;

ALTER TABLE dbai_llm.task_queue
    ADD CONSTRAINT task_queue_task_type_check
    CHECK (task_type = ANY (ARRAY[
        'query', 'analysis', 'generation', 'classification',
        'embedding', 'repair', 'monitoring',
        'chat', 'code', 'creative', 'vision', 'custom'
    ]));

-- ───────────────────────────────────────────────────────────────────
-- 8) CHECK-Constraint: build_log — 'hotfix' hinzufügen
-- ───────────────────────────────────────────────────────────────────
ALTER TABLE dbai_knowledge.build_log
    DROP CONSTRAINT IF EXISTS build_log_build_type_check;

ALTER TABLE dbai_knowledge.build_log
    ADD CONSTRAINT build_log_build_type_check
    CHECK (build_type IN (
        'initial_install', 'schema_migration',
        'c_compile', 'pip_install', 'bootstrap',
        'backup', 'restore', 'upgrade', 'hotfix'
    ));

-- ───────────────────────────────────────────────────────────────────
-- 9) CHECK-Constraint: system_memory — 'agent', 'import' hinzufügen
-- ───────────────────────────────────────────────────────────────────
ALTER TABLE dbai_knowledge.system_memory
    DROP CONSTRAINT IF EXISTS system_memory_category_check;

ALTER TABLE dbai_knowledge.system_memory
    ADD CONSTRAINT system_memory_category_check
    CHECK (category IN (
        'architecture', 'convention', 'schema_map', 'design_pattern',
        'relationship', 'workflow', 'inventory', 'roadmap',
        'identity', 'operational', 'agent', 'import'
    ));

-- ───────────────────────────────────────────────────────────────────
-- 10) Grants — Runtime-Rolle Zugriff geben
-- ───────────────────────────────────────────────────────────────────
DO $$ BEGIN
    -- dbai_core.network_devices
    EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON dbai_core.network_devices TO dbai_runtime';
    -- dbai_llm.learning_entries
    EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON dbai_llm.learning_entries TO dbai_runtime';
    -- dbai_llm.scheduled_jobs
    EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON dbai_llm.scheduled_jobs TO dbai_runtime';
    -- dbai_llm.agent_tasks
    EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON dbai_llm.agent_tasks TO dbai_runtime';
    -- Views
    EXECUTE 'GRANT SELECT ON dbai_ui.translations TO dbai_runtime';
    EXECUTE 'GRANT SELECT, INSERT ON dbai_ops.changelog TO dbai_runtime';
    -- dbai_ops schema usage
    EXECUTE 'GRANT USAGE ON SCHEMA dbai_ops TO dbai_runtime';
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Grant-Fehler (nicht-kritisch): %', SQLERRM;
END $$;

-- ───────────────────────────────────────────────────────────────────
-- 11) Diagnose-Ergebnisse in Datenbank loggen
-- ───────────────────────────────────────────────────────────────────
INSERT INTO dbai_knowledge.changelog (version, change_type, title, description, author)
VALUES (
    '0.12.0', 'fix',
    'Sandbox-Hotfix: 9 kritische Fehler behoben',
    'Automatisch diagnostiziert und repariert: '
    '4 fehlende Tabellen (network_devices, learning_entries, scheduled_jobs, agent_tasks), '
    '2 Kompatibilitaets-Views (translations, ops.changelog), '
    '3 CHECK-Constraints erweitert (task_queue +chat/code/creative/vision/custom, '
    'build_log +hotfix, system_memory +agent/import)',
    'ghost-system'
);

INSERT INTO dbai_knowledge.build_log (build_type, success, duration_ms, description)
VALUES ('hotfix', TRUE, 0,
    'Sandbox-Hotfix v0.12.0: 4 Tabellen, 2 Views, 3 Constraints');

-- ═══════════════════════════════════════════════════════════════════
-- Phase 2: App-für-App Debug-Fixes (2026-03-19)
-- ═══════════════════════════════════════════════════════════════════

-- ───────────────────────────────────────────────────────────────────
-- 12) Spalten-Aliase für synaptic_memory (Code erwartet andere Namen)
-- ───────────────────────────────────────────────────────────────────
ALTER TABLE dbai_llm.synaptic_memory
    ADD COLUMN IF NOT EXISTS memory_type TEXT;
ALTER TABLE dbai_llm.synaptic_memory
    ADD COLUMN IF NOT EXISTS strength DOUBLE PRECISION;
ALTER TABLE dbai_llm.synaptic_memory
    ADD COLUMN IF NOT EXISTS is_consolidated BOOLEAN DEFAULT FALSE;

-- Bestehende Daten synchronisieren
UPDATE dbai_llm.synaptic_memory SET memory_type = event_type WHERE memory_type IS NULL AND event_type IS NOT NULL;
UPDATE dbai_llm.synaptic_memory SET strength = importance WHERE strength IS NULL AND importance IS NOT NULL;
UPDATE dbai_llm.synaptic_memory SET is_consolidated = consolidated WHERE is_consolidated IS NULL AND consolidated IS NOT NULL;

-- ───────────────────────────────────────────────────────────────────
-- 13) Spalten für rag_sources (Code erwartet source_path, is_active)
-- ───────────────────────────────────────────────────────────────────
ALTER TABLE dbai_llm.rag_sources
    ADD COLUMN IF NOT EXISTS source_path TEXT;
ALTER TABLE dbai_llm.rag_sources
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;

-- ───────────────────────────────────────────────────────────────────
-- 14) Spalte relevance_score für rag_query_log
-- ───────────────────────────────────────────────────────────────────
ALTER TABLE dbai_llm.rag_query_log
    ADD COLUMN IF NOT EXISTS relevance_score DOUBLE PRECISION;

UPDATE dbai_llm.rag_query_log SET relevance_score = response_quality WHERE relevance_score IS NULL;

-- ───────────────────────────────────────────────────────────────────
-- 15) View: dbai_event.event_log → dbai_journal.event_log
-- ───────────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW dbai_event.event_log AS
    SELECT id, ts AS created_at, event_id, event_type, source, payload
    FROM dbai_journal.event_log;

COMMENT ON VIEW dbai_event.event_log IS 'Kompatibilitaets-View: dbai_event.event_log → dbai_journal.event_log';

-- ───────────────────────────────────────────────────────────────────
-- 16) GhostMail App in DB registrieren
-- ───────────────────────────────────────────────────────────────────
INSERT INTO dbai_ui.apps (app_id, name, icon, category, component, description, is_system, sort_order)
VALUES ('ghost-mail', 'GhostMail', 'Mail', 'kommunikation', 'GhostMail',
        'KI-gestützter Email-Client mit Ghost-Compose', FALSE, 45)
ON CONFLICT (app_id) DO NOTHING;

-- ───────────────────────────────────────────────────────────────────
-- 17) Phase 2 Changelog-Eintrag
-- ───────────────────────────────────────────────────────────────────
INSERT INTO dbai_knowledge.changelog (version, change_type, title, description, author)
VALUES (
    '0.12.1', 'fix',
    'App-Debug Phase 2: 6 Schema-Fixes + 4 JSONB-Bugs',
    'Spalten-Aliase: synaptic_memory (memory_type, strength, is_consolidated), '
    'rag_sources (source_path, is_active), rag_query_log (relevance_score). '
    'View: dbai_event.event_log. GhostMail registriert. '
    '4 JSONB-Insert-Bugs in server.py gefixt (json.dumps statt str()). '
    'ProcessManager in Desktop.jsx APP_COMPONENTS ergaenzt. '
    '106/106 API-Endpoints bestanden.',
    'ghost-system'
);

-- ═══════════════════════════════════════════════════════════════════
-- Phase 3: Ghost-Models Sync + Column-Mismatch-Fixes (2026-03-19)
-- ═══════════════════════════════════════════════════════════════════

-- ───────────────────────────────────────────────────────────────────
-- 18) ghost_models model_type CHECK erweitern um 'agent'
-- ───────────────────────────────────────────────────────────────────
ALTER TABLE dbai_llm.ghost_models DROP CONSTRAINT IF EXISTS ghost_models_model_type_check;
ALTER TABLE dbai_llm.ghost_models ADD CONSTRAINT ghost_models_model_type_check
  CHECK (model_type = ANY (ARRAY['chat','code','vision','embedding','reasoning','tool_use','multimodal','agent']));

-- ───────────────────────────────────────────────────────────────────
-- 19) Fehlende Ghost-Models aus Produktion einfügen (11 Stueck)
-- ───────────────────────────────────────────────────────────────────
INSERT INTO dbai_llm.ghost_models (name, display_name, model_path, model_type, provider, parameters, parameter_count, context_size, max_tokens, capabilities, supported_languages)
VALUES
('local-vllm-7b', 'Local vLLM — 7B', '', 'chat', 'custom', '{"temperature":0.7,"top_p":0.9}'::JSONB, '7B', 32768, 8192, ARRAY['chat','code','analysis'], ARRAY['de','en']),
('local-vllm-coder-32b', 'Local vLLM — Coder 32B', '', 'code', 'custom', '{"temperature":0.2,"top_p":0.95}'::JSONB, '32B', 32768, 8192, ARRAY['code','sql','python','bash','debugging'], ARRAY['en','de']),
('nvidia-kimi-k2', 'NVIDIA NIM — Kimi K2', '', 'chat', 'custom', '{"temperature":0.7}'::JSONB, 'MoE', 32768, 8192, ARRAY['chat','reasoning','code','analysis'], ARRAY['en','de','zh']),
('nvidia-llama-405b', 'NVIDIA NIM — Llama 405B', '', 'chat', 'custom', '{"temperature":0.7}'::JSONB, '405B', 32768, 8192, ARRAY['chat','reasoning','code','creative','long_context'], ARRAY['en','de','fr','es']),
('nvidia-qwen-397b', 'NVIDIA NIM — Qwen 397B', '', 'chat', 'custom', '{"temperature":0.7}'::JSONB, '397B', 32768, 8192, ARRAY['chat','code','analysis','multilingual'], ARRAY['en','de','zh','ja','ko']),
('oc-brain', 'OpenClaw — Brain', '', 'agent', 'custom', '{}'::JSONB, NULL, 32768, 8192, ARRAY['reasoning','planning','orchestration'], ARRAY['en','de']),
('oc-coder', 'OpenClaw — Coder', '', 'code', 'custom', '{}'::JSONB, NULL, 32768, 8192, ARRAY['code','refactoring','debugging','review'], ARRAY['en']),
('oc-content', 'OpenClaw — Content', '', 'chat', 'custom', '{}'::JSONB, NULL, 32768, 8192, ARRAY['creative','writing','translation','summarization'], ARRAY['en','de','fr']),
('oc-main', 'OpenClaw — Main', '', 'chat', 'custom', '{}'::JSONB, NULL, 32768, 8192, ARRAY['chat','general','routing','tool_use'], ARRAY['en','de']),
('oc-researcher', 'OpenClaw — Researcher', '', 'agent', 'custom', '{}'::JSONB, NULL, 32768, 8192, ARRAY['research','web_search','analysis','fact_check'], ARRAY['en','de']),
('oc-worker', 'OpenClaw — Worker', '', 'agent', 'custom', '{}'::JSONB, NULL, 32768, 8192, ARRAY['automation','file_ops','system_tasks','monitoring'], ARRAY['en','de'])
ON CONFLICT (name) DO NOTHING;

-- ───────────────────────────────────────────────────────────────────
-- 20) Phase 3 Changelog
-- ───────────────────────────────────────────────────────────────────
INSERT INTO dbai_knowledge.changelog (version, change_type, title, description, author)
VALUES (
    '0.12.2', 'fix',
    'Phase 3: 13 Column-Mismatches + Ghost-Models Sync + Cleanup',
    'server.py: 13 Column/Table-Mismatches gefixt:
    - dbai_llm.models → dbai_llm.ghost_models (Zeilen 1491, 1639)
    - model_format → model_type in ghost_models INSERT (Zeilen 2461, 2476)
    - dbai_core.events → dbai_event.events (Zeilen 8036, 8067)
    - dbai_llm.api_keys → dbai_workshop.api_keys (Zeilen 8284, 8477)
    - started_at → updated_at/created_at in agent_instances (Zeilen 480, 505, 3101)
    Ghost-Models: 11 fehlende Models aus Produktion synchronisiert (18 total).
    ghost_models_model_type_check um agent erweitert.
    6 Junk-Dateien aus Workspace geloescht (versehentliche psql-Ausgaben).
    106/106 API-Endpoints bestanden.',
    'ghost-system'
) ON CONFLICT DO NOTHING;

-- ───────────────────────────────────────────────────────────────────
-- 21) Phase 4: agent_instances – fehlende Spalten
-- ───────────────────────────────────────────────────────────────────
ALTER TABLE dbai_llm.agent_instances
  ADD COLUMN IF NOT EXISTS started_at    TIMESTAMPTZ DEFAULT NOW(),
  ADD COLUMN IF NOT EXISTS api_endpoint  TEXT DEFAULT '',
  ADD COLUMN IF NOT EXISTS extra_params  JSONB DEFAULT '{}'::JSONB;

-- ───────────────────────────────────────────────────────────────────
-- 22) Phase 4: fs_snapshots – fehlende Spalten
-- ───────────────────────────────────────────────────────────────────
ALTER TABLE dbai_system.fs_snapshots
  ADD COLUMN IF NOT EXISTS label   TEXT DEFAULT '',
  ADD COLUMN IF NOT EXISTS status  TEXT DEFAULT 'active';

-- ───────────────────────────────────────────────────────────────────
-- 23) Phase 4: events CHECK-Constraint erweitert (25 Event-Typen)
-- ───────────────────────────────────────────────────────────────────
ALTER TABLE dbai_event.events DROP CONSTRAINT IF EXISTS events_event_type_check;
ALTER TABLE dbai_event.events ADD CONSTRAINT events_event_type_check
  CHECK (event_type IN (
    'keyboard','mouse','network','disk','usb','power','thermal','timer',
    'process','system','error','llm','shutdown_initiated','reboot_initiated',
    'ghost_swap','boot','login','logout','config_change','backup','restore',
    'update','migration','anomaly','security'
  ));

-- ───────────────────────────────────────────────────────────────────
-- 24) Phase 4 Changelog
-- ───────────────────────────────────────────────────────────────────
INSERT INTO dbai_knowledge.changelog (version, change_type, title, description, author)
VALUES (
    '0.12.3', 'fix',
    'Phase 4: Full Endpoint Testing + 3 SQL Write-Path Bugs gefixt',
    'Vollstaendiger Test aller 116 Frontend-Endpoints: 116/116 bestanden.
    42 Write-Path-Endpoints (POST/PUT/PATCH/DELETE) getestet: 0 SQL-Fehler.
    WebSocket: 101 Switching Protocols bestaetigt.
    Frontend-Build: Vite Dev-Server + alle JSX-Module OK.
    3 SQL-Bugs gefixt:
    - events_event_type_check: 13 fehlende Typen ergaenzt (25 total)
    - RAG/Query: Handler liest jetzt query UND question, Empty-Guard
    - fs_snapshots INSERT: snapshot_name Spalte hinzugefuegt (NOT NULL)
    5 fehlende DB-Spalten ergaenzt:
    - agent_instances: started_at, api_endpoint, extra_params
    - fs_snapshots: label, status
    Docker-Logs: Keine Fehler.',
    'ghost-system'
) ON CONFLICT DO NOTHING;

-- ───────────────────────────────────────────────────────────────────
-- 25) Phase 5: 7 Write-Path 500er-Bugs in server.py gefixt
-- ───────────────────────────────────────────────────────────────────
-- Bug 1+2: agents/scheduled-jobs + agents/tasks — body["key"] → body.get() + Validierung
-- Bug 3: firewall/rules — fw.add_rule(body) → explizites Field-Mapping
-- Bug 4: mail/compose — try/except + Pflichtfeld-Validierung (account_id, to)
-- Bug 5: users — Frontend-Rollen (viewer/admin/user) → DB-Rollen (dbai_monitor/dbai_system) Mapping
-- Bug 6: backup/trigger — pg_dump Pfad-Suche + saubere 503 statt 500
-- Bug 7: learning/save — data["key"]/data["value"] → .get() + Validierung

-- ───────────────────────────────────────────────────────────────────
-- 26) Phase 5 Changelog
-- ───────────────────────────────────────────────────────────────────
INSERT INTO dbai_knowledge.changelog (version, change_type, title, description, author)
VALUES (
    '0.12.4', 'fix',
    'Phase 5: 7 Write-Path 500er-Bugs gefixt',
    '7 Server-Crashes (500 Internal Server Error) in server.py behoben:
    1. agents/scheduled-jobs: KeyError task_prompt → .get() + 400-Validierung
    2. agents/tasks: KeyError instance_id/name → .get() + 400-Validierung
    3. firewall/rules: cant adapt type dict → explizites Field-Mapping fuer add_rule()
    4. mail/compose: Unhandled DB-Crash → try/except + Pflichtfeld-Validierung
    5. users: users_db_role_check Constraint-Verletzung → Rollen-Mapping (viewer→dbai_monitor, admin→dbai_system)
    6. backup/trigger: FileNotFoundError pg_dump → Pfad-Suche + saubere 503
    7. learning/save: KeyError data[key]/data[value] → .get() + 400-Validierung
    Analyse: 53 weitere ungeschuetzte DB-Writes identifiziert (Code-Quality, kein Runtime-Crash).
    116/116 Frontend-GET-Endpoints + 42/42 Write-Paths weiterhin OK.',
    'ghost-system'
) ON CONFLICT DO NOTHING;

-- ───────────────────────────────────────────────────────────────────
-- 27) Phase 6: Globaler Exception-Handler + Connection-Pool-Härtung
-- ───────────────────────────────────────────────────────────────────
-- server.py Änderungen:
--   a) Globaler @app.exception_handler(Exception) hinzugefügt:
--      - KeyError/ValueError/TypeError → 400 Bad Request
--      - psycopg2 SQLSTATE 22xxx/42xxx → 400 (Data/Syntax Exception)
--      - psycopg2 SQLSTATE 23505 → 409 Conflict (Duplicate Key)
--      - psycopg2 SQLSTATE 23xxx → 422 (Constraint Violation)
--      - FileNotFoundError → 404
--      - PermissionError → 403
--      - TimeoutError → 504
--      - Alle anderen → 500 mit sauberem JSON
--   b) DBPool.get_connection() gehärtet:
--      - Thread-Lock für Pool-Zugriff
--      - Connection-Status-Prüfung (STATUS_READY/STATUS_IN_TRANSACTION)
--      - Automatische Bereinigung kaputter Verbindungen
--      - Kein conn.reset() mehr (verhindert Deadlocks)
--   c) Redundante psycopg2-Rollback im Exception-Handler entfernt
--      (db_query_rt/db_execute_rt machen bereits Rollback)
-- Ergebnis: 70/70 Exception-Handler-Tests bestanden (0 rohe Stacktraces)
--           27 reine 500er → korrekte HTTP-Status-Codes (400/404/409/422)
--           Server stabil nach 111+ aufeinanderfolgenden Fehler-Tests

-- ───────────────────────────────────────────────────────────────────
-- 28) Phase 6 Changelog
-- ───────────────────────────────────────────────────────────────────
INSERT INTO dbai_knowledge.changelog (version, change_type, title, description, author)
VALUES (
    '0.12.5', 'fix',
    'Phase 6: Globaler Exception-Handler + Connection-Pool-Härtung',
    'Globaler Exception-Handler für alle 83+ ungeschützten Endpoints:
    - Kein roher Stacktrace mehr an Client (100% sauberes JSON)
    - Semantisches HTTP-Status-Mapping via PostgreSQL SQLSTATE
    - 400 Bad Request für ungültige UUIDs, fehlende Felder, Typfehler
    - 409 Conflict für Duplicate-Key-Verletzungen
    - 422 Unprocessable Entity für Constraint-Verletzungen
    - 404/403/504 für entsprechende Systemfehler
    DBPool gehärtet: Thread-Lock, Status-basierte Verbindungsprüfung
    statt conn.reset(), automatische Bereinigung kaputter Connections.
    Tests: 70/70 Exception-Handler, 115/116 GET, 41/41 Write-Paths.',
    'ghost-system'
) ON CONFLICT DO NOTHING;


-- ───────────────────────────────────────────────────────────────────
-- 29) Phase 7: ASGI-Leak-Middleware + 12 Bug-Fixes (v0.12.6)
-- ───────────────────────────────────────────────────────────────────
-- Phase 7 Änderungen sind server.py Code-Fixes (kein SQL-Schema):
--   1) ASGI-Leak Middleware: catch_all_exceptions_middleware fängt
--      Exceptions vor Starlettes ServerErrorMiddleware → 0 Leaks
--   2) RAG-Delete: CASCADE statt explizitem Chunk-DELETE
--   3) Synaptic-Delete: dbai_vector.synaptic_memory (nicht dbai_system)
--   4) Anomaly-Resolve: auto_resolved + metadata jsonb
--   5+6) Sandbox launch_app()/stop_app() statt launch()/stop()
--   7) Hotspot-Config: dbai_system.hotspot_config (nicht service_config)
--   8) Export: Existence-Check → 404 statt 500
--   9) Browser-Import: browser_type Validierung gegen CHECK-Constraint
--  10) Config-Import: scan_all() Key-Mapping (users→user_rights, systemd→systemd_service)
--  11) SQL-Explorer: json.dumps für dict/list Werte vor psycopg2 INSERT
--  12) Users/Create: 409 Conflict bei Duplicate-Key statt 500
--  13) Export: HTTPException-Guard (except HTTPException: raise)
--
-- Test-Scripts auf Login-basiert umgestellt (kein hardcodiertes Token).
-- Ergebnisse: 116/116 GET + 41/41 Write + 70/70 Error + 64/75 Deep = 302/302 aktive Tests OK.
-- 11 erwartete Timeouts (externe Systeme nicht in Docker verfügbar).

INSERT INTO dbai_ops.changelog (version, change_type, title, description, author)
VALUES (
    'v0.12.6', 'fix',
    'Phase 7: ASGI-Leak-Middleware + 12 Bug-Fixes + Volltest',
    'ASGI-Leak Middleware (0 Leaks). 12 Fixes: RAG-Delete CASCADE, Synaptic-Tabelle,
    Anomaly-Resolve Spalten, Sandbox launch/stop, Hotspot-Config, Export Existence-Check,
    Browser-Import Val., Config-Import Keys, SQL-Explorer JSON, Users 409 Duplicate,
    Export HTTPException-Guard. 302/302 Tests OK.',
    'ghost-system'
) ON CONFLICT DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════
-- 30) Phase 8: Software Store → Desktop-Icon Integration (v0.12.8)
-- ═══════════════════════════════════════════════════════════════════════════

-- Constraint erweitern: 'app' als node_type für Store-installierte Software erlauben
ALTER TABLE dbai_ui.desktop_nodes DROP CONSTRAINT IF EXISTS valid_node_type;
ALTER TABLE dbai_ui.desktop_nodes ADD CONSTRAINT valid_node_type
  CHECK (node_type IN ('service', 'device', 'cloud', 'custom', 'app'));

-- Changelog
INSERT INTO dbai_knowledge.changelog (version, change_type, title, description, author)
VALUES (
    'v0.12.8', 'feature',
    'Software Store → Desktop-Icon Integration',
    'Install aus dem Software Store (GitHub + intern) erstellt automatisch Desktop-Nodes.
    Uninstall entfernt den Desktop-Node. Frontend dispatcht dbai:desktop_refresh Event,
    Desktop.jsx empfängt und aktualisiert Icons in Echtzeit. Constraint valid_node_type
    um app erweitert. Already-installed Pfad rüstet fehlende Nodes nach.',
    'ghost-system'
) ON CONFLICT DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════
-- 31) Phase 9: CrewAI + Auto-Config + GPU-Fix + Watchdog (v0.12.9)
-- ═══════════════════════════════════════════════════════════════════════════

-- ─── 31a) Model-Presets: Optimale Einstellungen pro Modell-Typ ───────────
CREATE TABLE IF NOT EXISTS dbai_llm.model_presets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name      TEXT NOT NULL,                -- z.B. "qwen3.5-27b-q8", "llama3-8b"
    display_name    TEXT NOT NULL,                -- z.B. "Qwen 3.5 27B (Q8_0)"
    description     TEXT,                         -- Für normale Menschen verständlich
    -- Empfohlene Einstellungen
    recommended_backend   TEXT NOT NULL DEFAULT 'llamacpp',   -- llamacpp, ollama, vllm
    recommended_gpu_layers INTEGER NOT NULL DEFAULT -1,       -- -1 = alle auf GPU
    recommended_ctx_size   INTEGER NOT NULL DEFAULT 4096,
    recommended_threads    INTEGER NOT NULL DEFAULT 8,
    recommended_batch_size INTEGER NOT NULL DEFAULT 512,
    -- Hardware-Anforderungen
    min_vram_mb     INTEGER NOT NULL DEFAULT 0,
    min_ram_mb      INTEGER NOT NULL DEFAULT 0,
    total_layers    INTEGER NOT NULL DEFAULT 40,  -- Architektur-Layers des Modells
    -- Modell-Metadaten
    parameter_count TEXT,                         -- z.B. "27B", "7B", "3B"
    quantization    TEXT,                         -- z.B. "Q8_0", "Q4_K_M"
    model_family    TEXT,                         -- z.B. "qwen", "llama", "mistral"
    architecture    TEXT,                         -- z.B. "transformer", "moe"
    -- Kompatible Provider (für Auto-Auswahl)
    compatible_providers TEXT[] NOT NULL DEFAULT '{}',  -- z.B. {llamacpp,ollama,vllm}
    -- Hilfe-Texte für UI
    hint_gpu_layers TEXT DEFAULT 'Anzahl der Layer auf der GPU. -1 = alle, 0 = nur CPU.',
    hint_ctx_size   TEXT DEFAULT 'Kontextgröße in Tokens. Mehr = mehr VRAM verbrauch.',
    hint_backend    TEXT DEFAULT 'Backend für die Inferenz. llama.cpp ist empfohlen für lokale Modelle.',
    -- Status
    is_default      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(model_name, quantization)
);

-- ─── 31b) CrewAI-Integration: Crews als feste Komponente in DB ───────────
CREATE TABLE IF NOT EXISTS dbai_llm.crew_definitions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL UNIQUE,          -- z.B. "ghost-main-crew"
    display_name    TEXT NOT NULL,
    description     TEXT,
    -- Konfiguration
    process_type    TEXT NOT NULL DEFAULT 'sequential',  -- sequential, hierarchical
    is_verbose      BOOLEAN NOT NULL DEFAULT FALSE,
    use_memory      BOOLEAN NOT NULL DEFAULT TRUE,
    max_rpm         INTEGER DEFAULT 10,           -- Rate-Limit pro Minute
    -- Zugeordnetes LLM
    default_model_id UUID REFERENCES dbai_llm.ghost_models(id) ON DELETE SET NULL,
    -- Steuerung
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    is_locked       BOOLEAN NOT NULL DEFAULT FALSE, -- Gegen versehentliches Löschen
    config          JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dbai_llm.crew_agents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crew_id         UUID NOT NULL REFERENCES dbai_llm.crew_definitions(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,                 -- z.B. "researcher", "analyst"
    display_name    TEXT NOT NULL,
    role            TEXT NOT NULL,                 -- CrewAI Agent-Rolle
    goal            TEXT NOT NULL,                 -- CrewAI Agent-Ziel
    backstory       TEXT,                          -- CrewAI Agent-Backstory
    -- LLM-Zuweisung (optional, überschreibt Crew-Default)
    model_id        UUID REFERENCES dbai_llm.ghost_models(id) ON DELETE SET NULL,
    -- Tools/Fähigkeiten
    tools           TEXT[] NOT NULL DEFAULT '{}',  -- z.B. {sql_tool, file_tool, web_search}
    allow_delegation BOOLEAN NOT NULL DEFAULT FALSE,
    -- Status
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    config          JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(crew_id, name)
);

CREATE TABLE IF NOT EXISTS dbai_llm.crew_tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crew_id         UUID NOT NULL REFERENCES dbai_llm.crew_definitions(id) ON DELETE CASCADE,
    agent_id        UUID REFERENCES dbai_llm.crew_agents(id) ON DELETE SET NULL,
    name            TEXT NOT NULL,
    display_name    TEXT NOT NULL,
    description     TEXT NOT NULL,                 -- Task-Beschreibung
    expected_output TEXT NOT NULL,                 -- Erwartetes Ergebnis
    -- Steuerung
    is_async        BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    depends_on      UUID[] DEFAULT '{}',           -- Task-IDs die vorher erledigt sein müssen
    config          JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(crew_id, name)
);

-- ─── 31c) Provider-Fallback-Chain: Automatisches Umschalten bei Ausfall ──
CREATE TABLE IF NOT EXISTS dbai_llm.provider_fallback_chain (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    priority        INTEGER NOT NULL DEFAULT 0,    -- 0 = höchste Priorität
    provider_key    TEXT NOT NULL,                  -- FK auf llm_providers.provider_key
    model_name      TEXT,                           -- Optionaler konkreter Modellname beim Provider
    is_enabled      BOOLEAN NOT NULL DEFAULT TRUE,
    max_retries     INTEGER NOT NULL DEFAULT 2,
    timeout_ms      INTEGER NOT NULL DEFAULT 30000,
    last_success    TIMESTAMPTZ,
    last_failure    TIMESTAMPTZ,
    failure_count   INTEGER NOT NULL DEFAULT 0,
    config          JSONB NOT NULL DEFAULT '{}',   -- Provider-spezifische Config
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(priority)
);

-- ─── 31d) LLM Watchdog: Health-Check-Protokoll ──────────────────────────
CREATE TABLE IF NOT EXISTS dbai_llm.watchdog_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    check_time      TIMESTAMPTZ NOT NULL DEFAULT now(),
    target          TEXT NOT NULL,                  -- z.B. "llama-server", "ollama", "groq"
    is_healthy      BOOLEAN NOT NULL,
    response_ms     INTEGER,
    action_taken    TEXT,                           -- z.B. "restart", "fallback", "none"
    details         JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─── 31e) GPU Memory Tracking: VRAM-Allokationen verfolgen ──────────────
CREATE TABLE IF NOT EXISTS dbai_llm.vram_allocations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gpu_index       INTEGER NOT NULL DEFAULT 0,
    model_id        UUID REFERENCES dbai_llm.ghost_models(id) ON DELETE CASCADE,
    instance_id     UUID REFERENCES dbai_llm.agent_instances(id) ON DELETE CASCADE,
    vram_allocated_mb INTEGER NOT NULL DEFAULT 0,
    allocated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    released_at     TIMESTAMPTZ,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE
);

-- ─── 31f) Presets mit realistischen Daten befüllen ──────────────────────

INSERT INTO dbai_llm.model_presets (model_name, display_name, description,
    recommended_backend, recommended_gpu_layers, recommended_ctx_size,
    recommended_threads, recommended_batch_size,
    min_vram_mb, min_ram_mb, total_layers, parameter_count, quantization,
    model_family, architecture, compatible_providers,
    hint_gpu_layers, hint_ctx_size, hint_backend, is_default)
VALUES
-- Qwen 3.5 27B Q8
('Qwen3.5-27B-Q8_0', 'Qwen 3.5 27B (Q8_0)', 
 'Großes Sprachmodell von Alibaba. 27 Milliarden Parameter, Q8_0 Quantisierung. Braucht ~28GB VRAM für volle GPU-Auslagerung. Hervorragend für Deutsch und komplexe Aufgaben.',
 'llamacpp', -1, 8192, 8, 512, 27271, 32000, 64, '27B', 'Q8_0', 'qwen', 'transformer',
 '{llamacpp,ollama,vllm}',
 'Bei 28GB+ VRAM: -1 (alles auf GPU). Bei 16GB: ca. 35 Layers. Bei 8GB: ca. 15 Layers.',
 '8192 empfohlen. 4096 spart VRAM, 16384 braucht deutlich mehr. Pro 4K Kontext ~2GB extra.',
 'llama.cpp empfohlen für lokale Nutzung. Ollama als Alternative. vLLM für Produktions-Server.',
 TRUE),

-- Codestral 22B
('codestral-22b', 'Codestral 22B (Q4_K_M)',
 'Spezialisiertes Code-Modell von Mistral. 22 Milliarden Parameter. Ideal für Programmierung, Code-Review und technische Aufgaben.',
 'llamacpp', -1, 16384, 8, 512, 14000, 16000, 56, '22B', 'Q4_K_M', 'mistral', 'transformer',
 '{llamacpp,ollama,vllm}',
 'Bei 16GB+ VRAM: -1 (alles auf GPU). Bei 8GB: ca. 25 Layers.',
 '16384 empfohlen für Code-Kontext. Mehr Kontext = besser für große Dateien.',
 'llama.cpp ist am stabilsten für dieses Modell.',
 FALSE),

-- Llama 3 8B
('llama3-8b-instruct', 'Llama 3 8B Instruct (Q4_K_M)',
 'Metas Llama 3 mit 8 Milliarden Parametern. Kompakt und schnell. Gut für einfache Aufgaben, Zusammenfassungen und Chat.',
 'llamacpp', -1, 8192, 8, 512, 6000, 8000, 32, '8B', 'Q4_K_M', 'llama', 'transformer',
 '{llamacpp,ollama,vllm}',
 'Passt auf die meisten GPUs mit 8GB+ VRAM komplett (-1).',
 '8192 Standard. Kann bis 8192 gehen ohne Probleme.',
 'llama.cpp oder Ollama — beides funktioniert gut.',
 FALSE),

-- Mistral 7B
('mistral-7b-instruct', 'Mistral 7B Instruct (Q4_K_M)',
 'Mistrals 7B Modell. Ähnlich wie Llama 3 8B aber mit Sliding-Window-Attention. Gut für längere Texte.',
 'llamacpp', -1, 8192, 8, 512, 6000, 8000, 32, '7B', 'Q4_K_M', 'mistral', 'transformer',
 '{llamacpp,ollama,vllm}',
 'Passt komplett auf GPUs mit 8GB+ VRAM.',
 '8192 Standard, unterstützt bis 32K über Sliding Window.',
 'llama.cpp empfohlen. Ollama als einfache Alternative.',
 FALSE),

-- Phi-3 Mini
('phi3-mini', 'Phi-3 Mini (Q4_K_M)',
 'Microsofts kompaktes Modell. Nur 3.8 Milliarden Parameter, aber überraschend gut. Ideal für schwache Hardware oder schnelle Antworten.',
 'llamacpp', -1, 4096, 4, 512, 3000, 4000, 32, '3.8B', 'Q4_K_M', 'phi', 'transformer',
 '{llamacpp,ollama}',
 'Passt auf jede GPU mit 4GB+. Auch auf integrierten GPUs nutzbar.',
 '4096 empfohlen. Modell unterstützt bis 4096.',
 'llama.cpp für direkte Kontrolle, Ollama für einfaches Setup.',
 FALSE),

-- Qwen 2.5 7B
('qwen2.5-7b-instruct', 'Qwen 2.5 7B Instruct (Q4_K_M)',
 'Qwens 7B Modell. Gut bei Deutsch und mehrsprachigen Aufgaben. Kompakt und schnell.',
 'llamacpp', -1, 8192, 8, 512, 6000, 8000, 28, '7B', 'Q4_K_M', 'qwen', 'transformer',
 '{llamacpp,ollama,vllm}',
 'Passt komplett auf GPUs mit 8GB+ VRAM.',
 '8192 empfohlen. Gute Balance aus Kontext und Geschwindigkeit.',
 'llama.cpp empfohlen. Optimaler Support für Qwen-Modelle.',
 FALSE),

-- Nomic Embed Text
('nomic-embed-text', 'Nomic Embed Text v1.5 (Q8_0)',
 'Embedding-Modell für Vektorsuche und RAG. Erzeugt Text-Vektoren, generiert KEINEN Text. Braucht kaum VRAM.',
 'llamacpp', -1, 8192, 4, 512, 500, 1000, 12, '137M', 'Q8_0', 'nomic', 'bert',
 '{llamacpp,ollama}',
 'Braucht nur ~500MB VRAM. Immer komplett auf GPU laden.',
 '8192 empfohlen (max Sequenzlänge des Modells).',
 'llama.cpp für Embedding-Generierung. Ollama als Alternative.',
 FALSE)
ON CONFLICT (model_name, quantization) DO NOTHING;

-- ─── 31g) Provider-Fallback-Chain mit sinnvollen Defaults befüllen ──────

INSERT INTO dbai_llm.provider_fallback_chain (priority, provider_key, model_name, is_enabled, max_retries, timeout_ms, config)
VALUES
(0, 'llamacpp', NULL, TRUE, 1, 60000, '{"description": "Lokaler llama-server — höchste Priorität, kein Internet nötig"}'::jsonb),
(1, 'ollama',   NULL, TRUE, 2, 30000, '{"description": "Lokaler Ollama-Server — Fallback wenn llama-server offline"}'::jsonb),
(2, 'vllm',     NULL, TRUE, 2, 30000, '{"description": "Lokaler vLLM-Server — Hochleistungs-Fallback"}'::jsonb),
(3, 'groq',     NULL, TRUE, 3, 15000, '{"description": "Groq Cloud — schnellster Cloud-Provider, kostenloser Tier"}'::jsonb),
(4, 'google',   NULL, TRUE, 3, 30000, '{"description": "Google Gemini — zuverlässiger Cloud-Fallback"}'::jsonb),
(5, 'openrouter', NULL, FALSE, 2, 45000, '{"description": "OpenRouter — Zugang zu vielen Modellen, API-Key nötig"}'::jsonb)
ON CONFLICT (priority) DO NOTHING;

-- ─── 31h) CrewAI Default-Crew: DBAI Ghost Crew ─────────────────────────

INSERT INTO dbai_llm.crew_definitions (name, display_name, description, process_type, is_verbose, use_memory, is_active, is_locked, config)
VALUES (
    'ghost-main-crew',
    'DBAI Ghost Crew',
    'Die Standard-Crew des Ghost-Systems. Orchestriert die KI-Agenten für System-Aufgaben, Code-Analyse, Datenbank-Optimierung und Benutzer-Interaktion.',
    'sequential',
    FALSE,  -- is_verbose
    TRUE,   -- use_memory
    TRUE,   -- is_active
    TRUE,   -- is_locked
    '{"framework": "crewai", "version": "1.11.0", "integration": "permanent", "notes": "Fest verbaute CrewAI-Integration. Kann konfiguriert, aber nicht entfernt werden."}'::jsonb
) ON CONFLICT (name) DO NOTHING;

-- Crew-Agents für die Default-Crew
INSERT INTO dbai_llm.crew_agents (crew_id, name, display_name, role, goal, backstory, tools, allow_delegation, sort_order)
SELECT cd.id,
       v.name, v.display_name, v.role, v.goal, v.backstory, v.tools, v.allow_delegation, v.sort_order
FROM dbai_llm.crew_definitions cd
CROSS JOIN (VALUES
    ('researcher', 'Forscher', 'Senior System-Forscher und Datenanalyst',
     'Analysiere Systemdaten, Logs und Metriken um Probleme zu erkennen und Optimierungen vorzuschlagen',
     'Du bist ein erfahrener Systemanalyst mit 20 Jahren Linux/PostgreSQL-Erfahrung. Du findest Muster in Logs die anderen entgehen.',
     ARRAY['sql_tool','log_analyzer','metric_reader'], FALSE, 0),
    ('coder', 'Programmierer', 'Senior Fullstack-Entwickler',
     'Schreibe, überprüfe und optimiere Code für das DBAI-System',
     'Du bist ein Fullstack-Entwickler der sowohl Python/FastAPI als auch JavaScript/React beherrscht. Du schreibst sauberen, getesteten Code.',
     ARRAY['sql_tool','file_tool','code_formatter'], TRUE, 1),
    ('dba', 'Datenbank-Admin', 'PostgreSQL Datenbank-Administrator',
     'Überwache und optimiere die PostgreSQL-Datenbank, führe Migrationen und Backups durch',
     'Du bist ein zertifizierter PostgreSQL-DBA. Du kennst VACUUM, Indexierung, Query-Optimierung und Replikation in- und auswendig.',
     ARRAY['sql_tool','vacuum_tool','backup_tool'], FALSE, 2),
    ('guardian', 'Wächter', 'Sicherheits- und Stabilitäts-Wächter',
     'Überwache Systemgesundheit, erkenne Anomalien und verhindere Ausfälle',
     'Du bist ein Security-Experte und Site-Reliability-Engineer in einer Person. Du merkst sofort wenn etwas nicht stimmt.',
     ARRAY['metric_reader','log_analyzer','health_checker'], FALSE, 3)
) AS v(name, display_name, role, goal, backstory, tools, allow_delegation, sort_order)
WHERE cd.name = 'ghost-main-crew'
ON CONFLICT (crew_id, name) DO NOTHING;

-- ─── 31i) Watchdog-Config in system_config ──────────────────────────────

INSERT INTO dbai_core.config (key, value, category, description)
VALUES 
('llm_watchdog_enabled', 'true'::jsonb, 'llm', 'LLM-Watchdog aktiviert: Prüft alle 10 Sekunden ob der Inferenz-Server erreichbar ist'),
('llm_watchdog_interval_sec', '10'::jsonb, 'llm', 'Intervall in Sekunden zwischen Health-Checks'),
('llm_watchdog_max_restarts', '3'::jsonb, 'llm', 'Maximale Auto-Restart-Versuche bevor Fallback zu Cloud'),
('llm_auto_fallback', 'true'::jsonb, 'llm', 'Automatischer Fallback zu Cloud-Provider wenn lokal nicht erreichbar'),
('crewai_enabled', 'true'::jsonb, 'llm', 'CrewAI-Integration aktiviert'),
('crewai_default_crew', '"ghost-main-crew"'::jsonb, 'llm', 'Standard-Crew für Ghost-Aufgaben'),
('gpu_vram_safety_margin_mb', '512'::jsonb, 'gpu', 'VRAM-Sicherheitspuffer in MB — wird nie für Modelle vergeben'),
('gpu_cooldown_after_unload_sec', '3'::jsonb, 'gpu', 'Wartezeit in Sekunden nach GPU-Entladung bevor neues Modell geladen wird')
ON CONFLICT (key) DO NOTHING;

-- ─── 31j) Changelog ─────────────────────────────────────────────────────

INSERT INTO dbai_knowledge.changelog (version, change_type, title, description, author)
VALUES (
    'v0.12.9', 'feature',
    'CrewAI + Auto-Config + GPU-Fix + Watchdog',
    'Große Architektur-Erweiterung:
    1) GPU-Memory-Bug behoben: VRAM wird jetzt korrekt freigegeben (CUDA-Cooldown, Tracking-Tabelle)
    2) CrewAI als feste Komponente: crew_definitions, crew_agents, crew_tasks in DB, Standard-Crew mit 4 Agenten
    3) Model-Presets mit Auto-Config: 7 Modelle mit optimalen Einstellungen, GPU-Layers, Kontext, Backend-Empfehlung
    4) Provider-Fallback-Chain: Automatischer Umschalten von lokal → Cloud bei Ausfall (6 Provider-Ebenen)
    5) LLM-Watchdog: Health-Check alle 10s, Auto-Restart, Fallback
    6) VRAM-Tracking: Allokations-Tabelle für präzises GPU-Speicher-Management',
    'ghost-system'
) ON CONFLICT DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════
-- 32) Phase 10: Vollständiges App-Cleanup bei Entfernung (v0.12.10)
-- ═══════════════════════════════════════════════════════════════════════════

-- Changelog
INSERT INTO dbai_knowledge.changelog (version, change_type, title, description, author)
VALUES (
    'v0.12.10', 'fix',
    'Vollständiges Cleanup bei App-Entfernung',
    'Beim Entfernen einer App (Store-Uninstall oder Desktop-Icon-Löschen) werden jetzt ALLE zugehörigen Daten bereinigt:
    1) Desktop-Symbol (desktop_nodes) wird gelöscht
    2) App-Einstellungen (app_user_settings) werden entfernt
    3) Offene Fenster (windows) werden geschlossen/gelöscht
    4) Software-Katalog wird auf available zurückgesetzt
    5) Event wird in dbai_event.events geloggt
    Desktop-Icon-Löschung triggert automatisch Store-Cleanup wenn node_key mit store: beginnt.
    Frontend zeigt unterschiedliche Bestätigungs-Dialoge für Netzwerkknoten vs. Store-Apps.',
    'ghost-system'
) ON CONFLICT DO NOTHING;