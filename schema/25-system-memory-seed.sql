-- =============================================================================
-- DBAI Schema 25: System Memory Seed — Das vollständige Gehirn
--
-- "Wenn ich vergesse wer ich bin, lese ich SELECT * FROM system_memory."
--
-- Diese Datei enthält ALLES was eine KI-Session wissen muss,
-- um sofort produktiv am DBAI-Codebase arbeiten zu können:
--
--   1. IDENTITÄT — Was ist DBAI / TabulaOS
--   2. ARCHITEKTUR — Wie das System aufgebaut ist
--   3. SCHEMA-KARTE — Alle 9 Schemas mit ~70 Tabellen
--   4. ROLLEN & SICHERHEIT — Wer darf was
--   5. DESIGN-PATTERNS — Wiederkehrende Muster
--   6. KONVENTIONEN — Naming, Testing, File-Struktur
--   7. BEZIEHUNGEN — Wie Komponenten zusammenhängen
--   8. TECH-INVENTAR — Stack, Versionen, Dependencies
--   9. WORKFLOW — Wie man am Code arbeitet
--  10. ROADMAP — Was kommt als nächstes
--  11. AGENT-SESSIONS — Dokumentierte Arbeitssitzungen
--
-- =============================================================================

-- =============================================================================
-- 1. IDENTITÄT — Wer ist DBAI
-- =============================================================================

INSERT INTO dbai_knowledge.system_memory
    (category, title, content, priority, tags, valid_from, related_schemas) VALUES

('identity', 'Was ist DBAI / TabulaOS',
 'DBAI (Database AI) ist ein tabellenbasiertes KI-Betriebssystem auf PostgreSQL 16+. ' ||
 'Jeder Systemzustand — Hardware, Prozesse, Ghost-Modelle, Erinnerungen, Events, Fehler — ' ||
 'ist eine Tabellenzeile. Kein Dateisystem, keine Config-Files, keine External APIs. ' ||
 'Markenname für Endanwender: TabulaOS. ' ||
 'Motto: "Das Rad nicht neu erfinden — existierendes fernsteuern." ' ||
 'Positionierung: "Upgrade für Erwachsene" gegenüber OpenClaw/SillyTavern.',
 95, ARRAY['core', 'identity', 'tabula'], '0.1.0',
 ARRAY['dbai_core', 'dbai_system', 'dbai_llm']),

('identity', 'Versionshistorie',
 'v0.1.0: Core-Tabellen, Hardware-Monitor, Events, Journal, Panic, Recovery, LLM-Bridge (42 Tests). ' ||
 'v0.2.0: Knowledge Library, Error-Patterns, Runbooks, Self-Healing, Seed-Data (52 Tests). ' ||
 'v0.3.0: Ghost System, Desktop UI, Ghost-Desktop-Seed, Web-Server, React-Frontend (60 Tests). ' ||
 'v0.4.0: Hardware Abstraction Layer, Neural Bridge, GPU Management, Hardware Scanner (88 Tests). ' ||
 'v0.5.0: OpenClaw Bridge, TabulaOS-Migration, Telegram-Bridge (106 Tests). ' ||
 'v0.6.0: Ghost Autonomy, App Ecosystem, Safety-Tabellen, Browser/Email/OAuth (127 Tests). ' ||
 'v0.7.0: System Memory — das vollständige Gehirn in der DB.',
 90, ARRAY['version', 'history', 'changelog'], '0.1.0', ARRAY[]::TEXT[]),

-- =============================================================================
-- 2. ARCHITEKTUR — Wie das System aufgebaut ist
-- =============================================================================

('architecture', 'Gesamtarchitektur',
 'DBAI besteht aus 4 Schichten: ' ||
 '1) PostgreSQL-Kern: 9 Schemas, ~70 Tabellen, RLS, Append-Only Journal. ' ||
 '2) Python-Bridges: Daemons die physische Hardware ↔ DB verbinden (system_bridge, hardware_scanner, gpu_manager, ghost_autonomy, app_manager, openclaw_importer). ' ||
 '3) Web-Server: FastAPI + WebSocket (server.py, ghost_dispatcher.py). ' ||
 '4) Frontend: React/Vite Desktop-UI mit Cyberpunk-Theme. ' ||
 'Kommunikation: NOTIFY/LISTEN für async Events. ' ||
 'Pattern: Alles ist eine Tabellenzeile. Kein State außerhalb der DB.',
 95, ARRAY['architecture', 'layers', 'overview'], '0.1.0',
 ARRAY['dbai_core', 'dbai_system', 'dbai_llm', 'dbai_event', 'dbai_vector', 'dbai_journal', 'dbai_panic', 'dbai_knowledge', 'dbai_ui']),

('architecture', 'Verzeichnisstruktur',
 'DBAI/ (Root) ' ||
 '├── schema/     — 25 SQL-Dateien (00-24), Boot-Reihenfolge durch Nummerierung ' ||
 '├── bridge/     — Python-Daemons (system_bridge, hardware_scanner, gpu_manager, ghost_autonomy, app_manager, openclaw_importer) ' ||
 '│   └── c_bindings/ — C-Shared-Library (hw_interrupts.c → libhw_interrupts.so) ' ||
 '├── web/        — FastAPI Server (server.py, ghost_dispatcher.py) ' ||
 '├── frontend/   — React/Vite App (src/, components/, styles/) ' ||
 '├── config/     — TOML-Konfiguration (dbai.toml) ' ||
 '├── recovery/   — PITR + Panic Recovery (pitr_manager.py, panic_recovery.py) ' ||
 '├── scripts/    — Bootstrap + Utilities (bootstrap.sh) ' ||
 '├── tests/      — Unittest Suite (test_core.py) ' ||
 '└── docs/       — Dokumentation (README.md, ARCHITECTURE.md usw.)',
 80, ARRAY['directory', 'structure', 'layout'], '0.1.0', ARRAY[]::TEXT[]),

('architecture', 'Boot-Sequenz',
 'bootstrap.sh lädt Schemas in Reihenfolge 00-24: ' ||
 '00-extensions (Schemas+Extensions+Rollen) → 01-core (Objects/Processes/Config/Drivers) → ' ||
 '02-system (CPU/Memory/Disk/Temp/Network) → 03-events → 04-vectors → ' ||
 '05-journal (Append-Only) → 06-panic (Emergency) → 07-rls (Row Level Security) → ' ||
 '08-llm (Models/Conversations/TaskQueue) → 09-vacuum → 10-sync (Locks) → ' ||
 '11-knowledge (Module Registry) → 12-errors (Error Patterns) → ' ||
 '13-seed-data (Vorgeladenes Wissen) → 14-self-healing → ' ||
 '15-ghost (Ghost Modelle) → 16-desktop → 17-ghost-seed (Default-Daten) → ' ||
 '18-hal (Hardware Tabellen) → 19-neural-bridge → 20-hw-seed → ' ||
 '21-openclaw → 22-ghost-autonomy → 23-app-ecosystem → ' ||
 '24-system-memory → 25-system-memory-seed (dieses File). ' ||
 'Nach DB-Setup: bridge/system_bridge.py startet die Python-Daemons.',
 85, ARRAY['boot', 'bootstrap', 'sequence', 'startup'], '0.1.0',
 ARRAY['dbai_core', 'dbai_system']),

-- =============================================================================
-- 3. SCHEMA-KARTE — Alle 9 Schemas mit ihren Tabellen
-- =============================================================================

('schema_map', 'dbai_core — Kern-Tabellen',
 'Schema: dbai_core (erstellt in 00-extensions.sql). Zentrale Objekte und Konfiguration. ' ||
 'Tabellen: objects (abstraktes Objektsystem mit UUID), processes (laufende Prozesse mit Heartbeat), ' ||
 'config (Schlüssel-Wert Konfiguration), drivers (Gerätetreiber). ' ||
 'Hinzu (v0.6.0): ghost_files (KI-organisierte Dateien), api_keys (verschlüsselte API-Schlüssel), ' ||
 'software_catalog (App Store Repository), browser_sessions (Headless-Browser Daten), ' ||
 'oauth_connections (Google/GitHub), workspace_sync (Datei-Sync). ' ||
 'Insgesamt ~10 Tabellen.',
 75, ARRAY['schema', 'core', 'objects'], '0.1.0', ARRAY['dbai_core']),

('schema_map', 'dbai_system — Hardware & Monitoring',
 'Schema: dbai_system (erstellt in 00-extensions.sql). Physische Hardware als Tabellenzeilen. ' ||
 'Tabellen: cpu, memory, disk, temperature, network (02-system-tables). ' ||
 'lock_registry (10-sync-primitives). ' ||
 'health_checks, alert_rules, alert_history, telemetry (14-self-healing). ' ||
 'vacuum_log, vacuum_config (09-vacuum-schedule). ' ||
 'hardware_inventory, gpu_devices, gpu_vram_map, cpu_cores, memory_map, storage_health, ' ||
 'fan_control, power_profiles, network_connections, hotplug_events (18-hardware-abstraction). ' ||
 'process_importance, energy_consumption (22-ghost-autonomy). ' ||
 'Insgesamt ~22 Tabellen — größtes Schema.',
 75, ARRAY['schema', 'system', 'hardware', 'monitoring'], '0.1.0', ARRAY['dbai_system']),

('schema_map', 'dbai_event — Events & Kommunikation',
 'Schema: dbai_event (erstellt in 00-extensions.sql). Alle systemweiten Ereignisse. ' ||
 'Tabellen: events (Basis-Event-Tabelle), keyboard, network, power (03-event-tables). ' ||
 'telegram_bridge, app_streams (21-openclaw-bridge). ' ||
 'email_accounts, inbox, outbox (23-app-ecosystem). ' ||
 'Insgesamt ~9 Tabellen.',
 70, ARRAY['schema', 'events', 'communication'], '0.1.0', ARRAY['dbai_event']),

('schema_map', 'dbai_vector — KI-Erinnerungen (pgvector)',
 'Schema: dbai_vector (erstellt in 00-extensions.sql). Semantischer Speicher mit HNSW-Index. ' ||
 'Tabellen: memories (vector(1536) Embeddings), knowledge_edges (Wissens-Graph). ' ||
 'Insgesamt 2 Tabellen.',
 70, ARRAY['schema', 'vector', 'embeddings', 'memory'], '0.1.0', ARRAY['dbai_vector']),

('schema_map', 'dbai_journal — Append-Only Audit Trail',
 'Schema: dbai_journal (erstellt in 00-extensions.sql). Unveränderliches Protokoll. ' ||
 'Tabellen: change_log (alle DB-Änderungen), event_log (System-Events), ' ||
 'system_snapshots (Zustandsschnappschüsse für PITR). ' ||
 'Trigger verhindern DELETE/UPDATE. Insgesamt 3 Tabellen.',
 70, ARRAY['schema', 'journal', 'audit', 'append-only'], '0.1.0', ARRAY['dbai_journal']),

('schema_map', 'dbai_panic — Notfall & Recovery',
 'Schema: dbai_panic (erstellt in 00-extensions.sql). Minimaler Selbstheilungskern. ' ||
 'Tabellen: emergency_drivers (Not-Treiber), boot_config (minimale Boot-Daten), ' ||
 'repair_scripts (automatische Reparatur), panic_log (Crash-Protokoll). ' ||
 'Insgesamt 4 Tabellen.',
 65, ARRAY['schema', 'panic', 'recovery', 'emergency'], '0.1.0', ARRAY['dbai_panic']),

('schema_map', 'dbai_llm — Ghost/KI System',
 'Schema: dbai_llm (erstellt in 00-extensions.sql). LLM-Integration und Ghost-System. ' ||
 'Tabellen: models (LLM-Modelle), conversations (Chat-Verlauf), task_queue (Aufgaben-Warteschlange). ' ||
 'ghost_models (verfügbare Ghosts mit VRAM/RAM/GPU-Requirements), ghost_roles, ' ||
 'active_ghosts, ghost_history, ghost_compatibility (15-ghost-system). ' ||
 'proposed_actions (Safety-First Scheduling), ghost_context (LLM-Prompt-Injektion), ' ||
 'ghost_thought_log (transparentes Denken), ghost_feedback (22-ghost-autonomy). ' ||
 'command_history (Natural Language → SQL/Python, 23-app-ecosystem). ' ||
 'Insgesamt ~14 Tabellen.',
 75, ARRAY['schema', 'llm', 'ghost', 'ai'], '0.1.0', ARRAY['dbai_llm']),

('schema_map', 'dbai_knowledge — Wissensdatenbank',
 'Schema: dbai_knowledge (erstellt in 11-knowledge-library.sql). Living Documentation. ' ||
 'Tabellen: module_registry (50+ Dateien dokumentiert), module_dependencies (Abhängigkeitsgraph), ' ||
 'changelog (append-only Versionshistorie), architecture_decisions (11 ADRs), ' ||
 'system_glossary (25+ Begriffe), known_issues, build_log (11-knowledge-library). ' ||
 'error_patterns, runbooks, error_log, error_resolutions (12-error-patterns). ' ||
 'system_memory, agent_sessions (24-system-memory — DIESE Daten). ' ||
 'Insgesamt ~13 Tabellen.',
 75, ARRAY['schema', 'knowledge', 'documentation', 'self-aware'], '0.2.0', ARRAY['dbai_knowledge']),

('schema_map', 'dbai_ui — Desktop & Benutzeroberfläche',
 'Schema: dbai_ui (erstellt in 16-desktop-ui.sql). Alias: dbai_desktop in frühen Docs. ' ||
 'Tabellen: users (mit bcrypt-Passwort-Hash), sessions (JWT-Token), themes (Cyberpunk/Matrix/Frost), ' ||
 'desktop_config (Wallpaper/Sidebar/Pinned-Apps), apps (13 registrierte), ' ||
 'windows (Window-Manager State), notifications (Toast-Benachrichtigungen). ' ||
 'Web-UI: React/Vite unter http://localhost:8420. ' ||
 'Insgesamt 7 Tabellen.',
 70, ARRAY['schema', 'ui', 'desktop', 'frontend'], '0.3.0', ARRAY['dbai_ui']),

-- =============================================================================
-- 4. ROLLEN & SICHERHEIT
-- =============================================================================

('architecture', 'Rollen und Berechtigungen',
 '4 Datenbankrollen, definiert in 00-extensions.sql, RLS-Policies in 07-row-level-security.sql: ' ||
 'dbai_system — Vollzugriff auf alle Schemas. Wird von Bridges und Admin benutzt. ' ||
 'dbai_monitor — Nur SELECT auf System-Tabellen. Für Monitoring-Dashboards. ' ||
 'dbai_llm — Zugriff auf eigene Conversations, Task-Queue, Ghost-Modelle. Für LLM-Prozesse. ' ||
 'dbai_recovery — Zugriff auf Panic-Schema, Journal-Reads. Für Notfall-Recovery. ' ||
 'Jede Tabelle in jedem Schema hat RLS aktiviert (ALTER TABLE ... ENABLE ROW LEVEL SECURITY). ' ||
 'Pattern: system_full (dbai_system), llm_read/write (dbai_llm), monitor_read (dbai_monitor).',
 85, ARRAY['security', 'roles', 'rls', 'permissions'], '0.1.0',
 ARRAY['dbai_core', 'dbai_system', 'dbai_llm']),

-- =============================================================================
-- 5. DESIGN-PATTERNS — Wiederkehrende Architektur-Muster
-- =============================================================================

('design_pattern', 'NOTIFY/LISTEN Async Events',
 'PostgreSQL NOTIFY/LISTEN für asynchrone Kommunikation zwischen Daemons. ' ||
 'Bekannte Channels: ghost_swap, ghost_query, ghost_gpu_migration, gpu_overheat, ' ||
 'power_profile_change, fan_control, hotplug_event, hardware_scan_complete, ' ||
 'action_proposed, action_approved, action_rejected, ghost_thought, ' ||
 'software_installed, software_install, email_received, command_result, ' ||
 'browser_action, email_outbox, user_command, telegram_message. ' ||
 'Pattern: cur.execute("LISTEN channel_name;"), dann select.select([conn], [], [], timeout).',
 90, ARRAY['notify', 'listen', 'async', 'events', 'channels'], '0.1.0', ARRAY[]::TEXT[]),

('design_pattern', 'Append-Only mit Trigger-Schutz',
 'Kritische Tabellen sind unveränderlich durch Trigger: ' ||
 'dbai_journal.change_log, dbai_journal.event_log, dbai_knowledge.changelog. ' ||
 'Pattern: CREATE TRIGGER protect_* BEFORE UPDATE OR DELETE → RAISE EXCEPTION. ' ||
 'Sinn: Audit-Trail kann nie manipuliert werden. Jeder Systemzustand ist rekonstruierbar.',
 80, ARRAY['append-only', 'immutable', 'audit', 'trigger'], '0.1.0',
 ARRAY['dbai_journal', 'dbai_knowledge']),

('design_pattern', 'Safety-First Scheduling (proposed_actions)',
 'Kritische KI-Aktionen werden NICHT sofort ausgeführt. Pattern: ' ||
 '1) KI schlägt Aktion vor → INSERT INTO proposed_actions (state=pending). ' ||
 '2) Wächter-Ghost ODER Mensch prüft und genehmigt → approve_action(). ' ||
 '3) Erst nach Genehmigung wird die Aktion ausgeführt → execute_approved_actions(). ' ||
 'Nicht genehmigte Aktionen verfallen nach Timeout → expire_pending_actions(). ' ||
 'Aktionstypen: shell_command, file_operation, network_request, system_config, package_install.',
 85, ARRAY['safety', 'proposed-actions', 'approval', 'wächter'], '0.6.0',
 ARRAY['dbai_llm']),

('design_pattern', 'Alles ist eine Tabellenzeile',
 'Kernprinzip von DBAI/TabulaOS: Kein State lebt außerhalb der Datenbank. ' ||
 'Hardware → Tabellenzeile (hardware_inventory). GPU → Tabellenzeile (gpu_devices). ' ||
 'Ghost-Modell → Tabellenzeile (ghost_models). Browser-Session → Tabellenzeile (browser_sessions). ' ||
 'E-Mail → Tabellenzeile (inbox/outbox). App → Tabellenzeile (software_catalog). ' ||
 'Fenster auf dem Desktop → Tabellenzeile (windows). Fehler → Tabellenzeile (error_log). ' ||
 'Vorteil: Ein SELECT reicht um den kompletten Systemzustand zu sehen.',
 95, ARRAY['core-principle', 'table-row', 'state', 'design'], '0.1.0', ARRAY[]::TEXT[]),

('design_pattern', 'Ghost Hot-Swap via DB',
 'Ghost-Modelle können zur Laufzeit gewechselt werden ohne Datenverlust. ' ||
 'Pattern: swap_ghost() Function → aktuellen Ghost entladen, neuen laden. ' ||
 'State-Transfer: Ghost-State lebt in der DB (ghost_context, ghost_thought_log), ' ||
 'nicht im RAM des Python-Prozesses. Neuer Ghost liest State per SELECT. ' ||
 'NOTIFY ghost_swap informiert alle Listener. GPU-VRAM wird automatisch freigegeben/allokiert.',
 80, ARRAY['ghost', 'hot-swap', 'state-transfer', 'model'], '0.3.0',
 ARRAY['dbai_llm']),

('design_pattern', 'Remote-Control statt Rebuild',
 'DBAI baut keine eigenen Apps. Stattdessen: existierende Programme fernsteuern. ' ||
 'Browser → Playwright (Headless Chromium), KI sieht Text/DOM, nicht Pixel. ' ||
 'E-Mail → IMAP/SMTP, Nachrichten werden in inbox/outbox Tabellen gespiegelt. ' ||
 'Apps → APT/pip/GitHub, Software-Katalog als DB-Tabelle. ' ||
 'OAuth → Google/GitHub Token-Management in der DB. ' ||
 'Die KI arbeitet mit strukturierten Daten, nicht mit GUIs.',
 80, ARRAY['remote-control', 'playwright', 'imap', 'oauth', 'app-mode'], '0.6.0',
 ARRAY['dbai_core', 'dbai_event']),

-- =============================================================================
-- 6. KONVENTIONEN — Naming, Testing, Dateistruktur
-- =============================================================================

('convention', 'Schema-Datei Naming',
 'Schema-Dateien: schema/NN-name.sql wobei NN = 00-99 (Boot-Reihenfolge). ' ||
 'Nummer definiert Ladereihenfolge in bootstrap.sh. ' ||
 'Konvention: 00-09 = Core/Infrastructure, 10-14 = Knowledge/Self-Healing, ' ||
 '15-17 = Ghost/Desktop, 18-20 = Hardware, 21 = OpenClaw, 22-23 = Autonomy/Apps, ' ||
 '24-25 = System Memory. Jede Schema-Datei hat Header-Kommentar mit Beschreibung.',
 70, ARRAY['naming', 'convention', 'schema', 'files'], '0.1.0', ARRAY[]::TEXT[]),

('convention', 'Tabellen-Naming',
 'Tabellen: schema_name.table_name (lowercase, underscores). ' ||
 'Views: vw_name (z.B. vw_gpu_overview, vw_system_context). ' ||
 'Trigger: trg_name (z.B. trg_module_updated, trg_protect_changelog). ' ||
 'Funktionen: schema.function_name() (z.B. dbai_core.acquire_lock()). ' ||
 'Index: idx_table_column (z.B. idx_module_category). ' ||
 'Policy: table_role_access (z.B. sysmem_llm_read). ' ||
 'Alle Tabellen haben: created_at TIMESTAMPTZ DEFAULT NOW(), id UUID PRIMARY KEY DEFAULT uuid_generate_v4().',
 75, ARRAY['naming', 'convention', 'tables', 'sql'], '0.1.0', ARRAY[]::TEXT[]),

('convention', 'Python Bridge Konventionen',
 'Bridge-Dateien: bridge/name.py. Klassen: CamelCase (z.B. HardwareScanner, GPUManager). ' ||
 'Jede Bridge hat: __init__(db_dsn), connect(), disconnect(), daemon_loop(). ' ||
 'CLI via argparse mit --daemon Flag für Endlos-Betrieb. ' ||
 'Conditional Imports mit HAS_MODULE-Flags (z.B. HAS_PSYCOPG2, HAS_PLAYWRIGHT). ' ||
 'Logging via logging.getLogger("dbai.module_name"). ' ||
 'Signal-Handler: SIGINT/SIGTERM setzen self.running = False. ' ||
 'DB-Pattern: psycopg2, conn.autocommit wechselt je nach Operation.',
 75, ARRAY['naming', 'convention', 'python', 'bridge'], '0.1.0', ARRAY[]::TEXT[]),

('convention', 'Test-Konventionen',
 'Alle Tests in tests/test_core.py (eine Datei, unittest-basiert). ' ||
 'Klassen: Test<Feature>(unittest.TestCase). ' ||
 'EXPECTED_FILES-Array listet alle Schema-Dateien. ' ||
 'Test-Pattern: Datei existiert → Datei nicht leer → Inhalt hat Keywords. ' ||
 'Ausführung: python3 -m unittest tests.test_core -v. ' ||
 'Nach jedem Edit: Tests laufen lassen, 0 Failures erwartet. ' ||
 'Counts aktuell halten: "Alle NN Schema-Dateien" Docstring, range(NN) in Seed-Check.',
 80, ARRAY['testing', 'convention', 'unittest', 'workflow'], '0.1.0', ARRAY[]::TEXT[]),

('convention', 'Seed-Data Konventionen',
 '13-seed-data.sql hat 8 Sektionen: ' ||
 '1) MODULE REGISTRY — Jede Datei als Zeile (50+ Einträge). ' ||
 '2) ADRs — Architektur-Entscheidungen (11 Einträge). ' ||
 '3) ERROR PATTERNS — Bekannte Fehler mit Regex (9 Einträge). ' ||
 '4) RUNBOOKS — Schritt-für-Schritt (5 Einträge). ' ||
 '5) GLOSSAR — Begriffsdefinitionen (25+ Einträge). ' ||
 '6) CHANGELOG — Versionshistorie (v0.1.0 bis v0.6.0). ' ||
 '7) KNOWN ISSUES — Bekannte Probleme. ' ||
 '8) BUILD LOG — Build-Dokumentation. ' ||
 'Bei jedem neuen Feature: Modul-Registry + ADR + Changelog + Build-Log aktualisieren.',
 75, ARRAY['seed-data', 'convention', 'documentation'], '0.2.0', ARRAY[]::TEXT[]),

-- =============================================================================
-- 7. BEZIEHUNGEN — Wie Komponenten zusammenhängen
-- =============================================================================

('relationship', 'Ghost ↔ Hardware Pipeline',
 'Ghost-Modelle (15-ghost-system) brauchen GPU-VRAM (18-hardware-abstraction). ' ||
 'Flow: ghost_models.required_vram_mb → gpu_devices.vram_total_mb → gpu_vram_map.allocated_mb. ' ||
 'GPU Manager (bridge/gpu_manager.py) überwacht Temperatur, migriert Ghost bei Überhitzung. ' ||
 'Neural Bridge (19) bestimmt welcher Ghost beim Boot die Kontrolle übernimmt. ' ||
 'Power Profiles beeinflussen GPU-Taktung → beeinflussen Ghost-Performance.',
 75, ARRAY['relationship', 'ghost', 'gpu', 'hardware'], '0.4.0',
 ARRAY['dbai_llm', 'dbai_system']),

('relationship', 'Autonomy ↔ Safety Pipeline',
 'Ghost Autonomy (22) plant Aktionen → proposed_actions (state=pending). ' ||
 'Wächter-Ghost (anderes Modell) oder Mensch genehmigt → state=approved/rejected. ' ||
 'Ghost Autonomy Daemon hört LISTEN action_approved → führt aus. ' ||
 'ghost_thought_log macht Entscheidungsprozess transparent. ' ||
 'ghost_feedback ermöglicht Lernen: war die Aktion hilfreich? ' ||
 'energy_consumption limitiert Aktionen bei niedrigem Akku.',
 80, ARRAY['relationship', 'autonomy', 'safety', 'approval'], '0.6.0',
 ARRAY['dbai_llm', 'dbai_system']),

('relationship', 'Web-Server ↔ DB ↔ Frontend Pipeline',
 'React-Frontend (localhost:8420) → FastAPI REST API (server.py) → PostgreSQL. ' ||
 'WebSocket: /ws/{session_id} für Echtzeit-Updates (Ghost-Chat, System-Events). ' ||
 'Auth: JWT-Token, Users in dbai_ui.users (bcrypt-Hash). ' ||
 'Ghost-Dispatcher: Modell laden/entladen, Chat, Swap — alles über DB. ' ||
 'NOTIFY-Events werden via WebSocket an Frontend gepusht.',
 75, ARRAY['relationship', 'web', 'frontend', 'api', 'websocket'], '0.3.0',
 ARRAY['dbai_ui', 'dbai_llm']),

('relationship', 'Knowledge Library ↔ Self-Healing Pipeline',
 'Fehler wird geloggt → error_log (12-error-patterns). ' ||
 'Pattern-Matching findet bekannten error_pattern → runbook wird vorgeschlagen. ' ||
 'Wenn can_auto_fix=TRUE → auto_fix_shell wird ausgeführt. ' ||
 'health_checks (14-self-healing) laufen periodisch → bei Threshold → alert_rules feuern. ' ||
 'telemetry speichert Zeitreihen für Trend-Erkennung.',
 70, ARRAY['relationship', 'self-healing', 'error', 'monitoring'], '0.2.0',
 ARRAY['dbai_knowledge', 'dbai_system']),

-- =============================================================================
-- 8. TECH-INVENTAR — Stack, Versionen, Dependencies
-- =============================================================================

('inventory', 'Datenbank-Stack',
 'PostgreSQL 16+ mit Extensions: vector (pgvector für Embeddings), uuid-ossp (UUID-Gen), ' ||
 'pgcrypto (Verschlüsselung), pg_stat_statements (Query-Analyse), pg_cron (Cron-Jobs), ' ||
 'pg_trgm (Fuzzy-Suche). Datenbank: dbai. Schemas: 9 Stück, ~70 Tabellen.',
 80, ARRAY['stack', 'postgresql', 'extensions', 'database'], '0.1.0', ARRAY[]::TEXT[]),

('inventory', 'Python-Stack',
 'Python 3.10+. Dependencies (requirements.txt): ' ||
 'psycopg2-binary (DB-Treiber), psutil (System-Monitor), llama-cpp-python (LLM-Inferenz), ' ||
 'toml (Config-Parser), fastapi + uvicorn[standard] (Web-Server), websockets (Echtzeit), ' ||
 'PyJWT (Auth-Token), bcrypt (Passwort-Hash), pytest + pytest-cov (Testing), ' ||
 'nvidia-ml-py3>=12.535.0 (GPU-Management). ' ||
 'Optional: playwright (Browser-Automation), imaplib/smtplib (Email-Standard-Lib).',
 80, ARRAY['stack', 'python', 'dependencies', 'pip'], '0.1.0', ARRAY[]::TEXT[]),

('inventory', 'Frontend-Stack',
 'React 18+ mit Vite als Bundler. Keine Component-Library — eigenes Cyberpunk-CSS. ' ||
 'Komponenten: BootScreen, LoginScreen, Desktop, Window (Core). ' ||
 'Apps: SystemMonitor, GhostManager, GhostChat, KnowledgeBase, EventViewer, SQLConsole, HealthDashboard. ' ||
 'API-Client: fetch-basiert (src/api.js). Port: 8420.',
 70, ARRAY['stack', 'react', 'vite', 'frontend', 'cyberpunk'], '0.3.0', ARRAY[]::TEXT[]),

('inventory', 'Bridge-Dateien Übersicht',
 'bridge/system_bridge.py — Der Zündschlüssel: Bootet DBAI, startet Monitor + LLM. ' ||
 'bridge/hardware_scanner.py — Scannt CPU/RAM/Disk/Network/Fans, schreibt in hardware_inventory. ' ||
 'bridge/gpu_manager.py — NVIDIA GPU Management: VRAM-Tracking, Thermal Protection, Multi-GPU. ' ||
 'bridge/ghost_autonomy.py — Ghost als Scheduler: Kontext-Injektion, Energie, Prozesse, proposed_actions. ' ||
 'bridge/app_manager.py — Software-Katalog, Headless Browser, Email, OAuth. ' ||
 'bridge/openclaw_importer.py — Migriert OpenClaw/SillyTavern/Oobabooga → DBAI. ' ||
 'bridge/c_bindings/hw_interrupts.c → libhw_interrupts.so (Hardware-Interrupts via kqueue/epoll).',
 80, ARRAY['bridges', 'daemons', 'python', 'inventory'], '0.1.0', ARRAY[]::TEXT[]),

-- =============================================================================
-- 9. WORKFLOW — Wie man am Code arbeitet
-- =============================================================================

('workflow', 'Neues Feature hinzufügen',
 'Schritt-für-Schritt Workflow für neue Features: ' ||
 '1) Schema-Datei erstellen: schema/NN-name.sql (Header, Tabellen, Views, Functions, RLS, Comments). ' ||
 '2) Bridge-Datei erstellen: bridge/name.py (Klasse, CLI, Daemon, NOTIFY-Listener). ' ||
 '3) bootstrap.sh: Schema zur SCHEMA_FILES-Liste hinzufügen. ' ||
 '4) test_core.py: EXPECTED_FILES erweitern, Count hochzählen, range() anpassen, neue TestClass. ' ||
 '5) 13-seed-data.sql: Module-Registry (+Einträge), ADR, Changelog, Build-Log. ' ||
 '6) Tests ausführen: python3 -m unittest tests.test_core -v → 0 Failures. ' ||
 'Wichtig: Immer exakte Textstellen mit grep_search finden bevor man editiert!',
 90, ARRAY['workflow', 'feature', 'development', 'checklist'], '0.1.0', ARRAY[]::TEXT[]),

('workflow', 'Seed-Data bearbeiten',
 'Kritische Edit-Stellen in 13-seed-data.sql: ' ||
 '1) Module-Count: Suche "alle NN Modul-Registrierungen" und "NN Architektur-Entscheidungen". ' ||
 '2) Letzte Modul-Zeile: Suche "active);" am Ende des INSERT INTO module_registry → Semikolon durch Komma ersetzen, neue Zeilen anfügen. ' ||
 '3) Letzte ADR: Suche "human+system);" vor "3. ERROR PATTERNS" → gleich. ' ||
 '4) Changelog: Suche letzte Version vor "7. KNOWN ISSUES". ' ||
 '5) Build-Log: Suche letztes Entry vor "FERTIG". ' ||
 'Immer mit grep_search die exakten Zeilen finden!',
 85, ARRAY['workflow', 'seed-data', 'editing', 'checklist'], '0.2.0', ARRAY[]::TEXT[]),

('workflow', 'Test-Datei bearbeiten',
 'Edit-Stellen in tests/test_core.py: ' ||
 '1) EXPECTED_FILES: Array am Anfang der Datei — neue Schema-Dateinamen anfügen. ' ||
 '2) "Alle NN Schema-Dateien" Docstring → Count aktualisieren. ' ||
 '3) range(NN) im Seed-Data-Test → Count aktualisieren. ' ||
 '4) assertIn-Checks für Bridge-Dateien nach "openclaw_importer.py" Check. ' ||
 '5) Neue TestClass VOR "class TestWebServer" einfügen. ' ||
 'Pattern pro TestClass: test_exists, test_has_tables, test_has_functions, test_has_rls.',
 80, ARRAY['workflow', 'testing', 'editing', 'checklist'], '0.1.0', ARRAY[]::TEXT[]),

-- =============================================================================
-- 10. OPERATIONAL — Deployment, Runtime
-- =============================================================================

('operational', 'NOTIFY Channels Referenz',
 'Vollständige Liste aller NOTIFY Channels im System: ' ||
 'ghost_swap — Ghost-Modell-Wechsel (15-ghost-system). ' ||
 'ghost_query — LLM-Anfrage (08-llm, ghost_dispatcher). ' ||
 'ghost_gpu_migration — GPU-Migration bei Überhitzung (19-neural-bridge). ' ||
 'gpu_overheat — GPU-Temperatur kritisch (18-hal, gpu_manager). ' ||
 'power_profile_change — Energieprofil geändert (18-hal). ' ||
 'fan_control — Lüftersteuerung (18-hal). ' ||
 'hotplug_event — Gerät angesteckt/abgezogen (18-hal). ' ||
 'hardware_scan_complete — Hardware-Scan fertig (hardware_scanner). ' ||
 'action_proposed — KI schlägt Aktion vor (22-autonomy). ' ||
 'action_approved — Aktion genehmigt (22-autonomy). ' ||
 'action_rejected — Aktion abgelehnt (22-autonomy). ' ||
 'ghost_thought — KI-Gedanke geloggt (22-autonomy). ' ||
 'software_installed — Paket installiert (23-ecosystem). ' ||
 'software_install — Installationsauftrag (app_manager). ' ||
 'email_received — Neue E-Mail (23-ecosystem). ' ||
 'email_outbox — E-Mail zum Senden (app_manager). ' ||
 'command_result — Befehl ausgeführt (23-ecosystem). ' ||
 'browser_action — Browser-Aktion (app_manager). ' ||
 'user_command — Nutzer-Befehl (app_manager). ' ||
 'telegram_message — Telegram-Nachricht (openclaw_importer).',
 85, ARRAY['notify', 'channels', 'reference', 'operational'], '0.1.0', ARRAY[]::TEXT[]),

('operational', 'Default-Konfiguration',
 'DB-Name: dbai. DB-DSN: dbname=dbai. ' ||
 'Web-Server: http://localhost:8420. ' ||
 'Default-User: root / dbai2026 (Rolle: dbai_system). ' ||
 'Default-Ghost: Qwen 2.5 7B Instruct (Q4_K_M GGUF) als Sysadmin. ' ||
 'Default-Theme: ghost-dark (Cyberpunk-Farben, Neon-Akzente). ' ||
 'Config-Datei: config/dbai.toml. ' ||
 'GPU-Thresholds: 80°C Warning, 90°C Critical (auto-migration).',
 70, ARRAY['config', 'defaults', 'operational'], '0.1.0', ARRAY[]::TEXT[]),

-- =============================================================================
-- ROADMAP
-- =============================================================================

('roadmap', 'Nächste geplante Features',
 'Mögliche nächste Schritte (nicht final): ' ||
 '- Cyber-Deck Web-UI: Thought-Stream des Ghosts als Echtzeit-Feed im Frontend. ' ||
 '- Command Interface: Natural Language → SQL → Python Pipeline im Frontend. ' ||
 '- Workspace Sync: Google Drive/GitHub Repo-Sync via OAuth. ' ||
 '- Wächter-Ghost: Dediziertes Security-Modell das proposed_actions bewertet. ' ||
 '- Multi-User: Mehrere Benutzer mit eigenen Ghosts und Desktop-Configs. ' ||
 '- Plugin-System: Apps als registrierte Module mit eigenen Schemas. ' ||
 '- Mobile: Telegram/Signal als Remote-Terminal für unterwegs.',
 60, ARRAY['roadmap', 'future', 'planned'], '0.7.0', ARRAY[]::TEXT[]);

-- =============================================================================
-- 11. AGENT-SESSIONS — Dokumentierte Arbeitssitzungen
-- =============================================================================

INSERT INTO dbai_knowledge.agent_sessions
    (session_date, version_start, version_end, summary,
     files_created, files_modified, schemas_added,
     tests_before, tests_after, goals, decisions) VALUES

('2026-03-15', '0.0.0', '0.1.0',
 'Initiales Setup: PostgreSQL-Schemas 00-10 erstellt. Core-Tabellen, System-Monitor, Events, ' ||
 'Vektor-Speicher, WAL-Journal, Panic-Schema, RLS, LLM-Integration, Vacuum, Sync-Primitives. ' ||
 'System Bridge, Hardware Monitor, C-Bindings. 42 Tests.',
 ARRAY['schema/00-extensions.sql', 'schema/01-core-tables.sql', 'schema/02-system-tables.sql',
       'schema/03-event-tables.sql', 'schema/04-vector-tables.sql', 'schema/05-wal-journal.sql',
       'schema/06-panic-schema.sql', 'schema/07-row-level-security.sql', 'schema/08-llm-integration.sql',
       'schema/09-vacuum-schedule.sql', 'schema/10-sync-primitives.sql',
       'bridge/system_bridge.py', 'bridge/c_bindings/hw_interrupts.c',
       'config/dbai.toml', 'recovery/pitr_manager.py', 'recovery/panic_recovery.py'],
 ARRAY['scripts/bootstrap.sh', 'tests/test_core.py'],
 ARRAY['00', '01', '02', '03', '04', '05', '06', '07', '08', '09', '10'],
 0, 42,
 ARRAY['PostgreSQL als OS-Kern aufsetzen', 'Alle Systemzustände als Tabellenzeilen'],
 ARRAY['PostgreSQL statt Custom DB', 'RLS für Sicherheit', 'Append-Only Journal', 'C-Bindings für Hardware']),

('2026-03-15', '0.1.0', '0.2.0',
 'Knowledge Library: Self-documenting Wissensdatenbank. Schemas 11-14 erstellt. ' ||
 'Module Registry, Error Patterns, Runbooks, Glossar, Self-Healing. Seed-Data. 52 Tests.',
 ARRAY['schema/11-knowledge-library.sql', 'schema/12-error-patterns.sql',
       'schema/13-seed-data.sql', 'schema/14-self-healing.sql'],
 ARRAY['tests/test_core.py', 'scripts/bootstrap.sh'],
 ARRAY['11', '12', '13', '14'],
 42, 52,
 ARRAY['Alles Wissen in die DB', 'README als Tabelle', 'Fehler automatisch lösen'],
 ARRAY['Knowledge Library als eigenes Schema', 'Error Patterns mit Regex', 'Seed Data als SQL statt JSON']),

('2026-03-15', '0.2.0', '0.3.0',
 'Ghost System + Desktop UI + Web-Server + React-Frontend. ' ||
 'Ghost-Modelle in DB, Hot-Swap, Desktop-Env, React/Vite mit Cyberpunk-Theme. 60 Tests.',
 ARRAY['schema/15-ghost-system.sql', 'schema/16-desktop-ui.sql', 'schema/17-ghost-desktop-seed.sql',
       'web/server.py', 'web/ghost_dispatcher.py',
       'frontend/package.json', 'frontend/vite.config.js', 'frontend/src/main.jsx'],
 ARRAY['tests/test_core.py', 'scripts/bootstrap.sh', 'schema/13-seed-data.sql'],
 ARRAY['15', '16', '17'],
 52, 60,
 ARRAY['Ghost-System in DB', 'Desktop-UI für TabulaOS', 'Web-Server für Frontend'],
 ARRAY['Ghost-Modelle als Tabellenzeilen', 'React/Vite statt Electron', 'JWT für Auth', 'WebSocket für Echtzeit']),

('2026-03-15', '0.3.0', '0.4.0',
 'Hardware Abstraction Layer + Neural Bridge + GPU Management. ' ||
 'Alle Hardware als Tabellenzeilen, NVIDIA GPU mit VRAM-Tracking und Thermal Protection. 88 Tests.',
 ARRAY['schema/18-hardware-abstraction.sql', 'schema/19-neural-bridge.sql', 'schema/20-hw-seed-data.sql',
       'bridge/hardware_scanner.py', 'bridge/gpu_manager.py'],
 ARRAY['tests/test_core.py', 'scripts/bootstrap.sh', 'schema/13-seed-data.sql',
       'web/ghost_dispatcher.py', 'requirements.txt'],
 ARRAY['18', '19', '20'],
 60, 88,
 ARRAY['Jedes Gerät als Tabellenzeile', 'GPU-Management für LLM-Inferenz', 'Thermal Protection'],
 ARRAY['HAL als eigene Tabellen', 'pynvml + nvidia-smi Fallback', 'NOTIFY für Hardware-Events']),

('2026-03-15', '0.4.0', '0.5.0',
 'OpenClaw Bridge + TabulaOS-Strategie. Migration von OpenClaw/SillyTavern/Oobabooga. ' ||
 'Telegram-Bridge direkt in DB. Positionierung als "Upgrade für Erwachsene". 106 Tests.',
 ARRAY['schema/21-openclaw-bridge.sql', 'bridge/openclaw_importer.py'],
 ARRAY['tests/test_core.py', 'scripts/bootstrap.sh', 'schema/13-seed-data.sql'],
 ARRAY['21'],
 88, 106,
 ARRAY['OpenClaw-User kapern', 'Memories JSON→pgvector migrieren', 'Telegram als Kommunikationskanal'],
 ARRAY['Migration statt Neubau', 'Compatibility-Map für Feature-Vergleich', 'App-Mode: Datenstrom statt Pixel']),

('2026-03-15', '0.5.0', '0.6.0',
 'Ghost Autonomy + App Ecosystem. Ghost wird zentraler Scheduler mit Safety-Tabellen. ' ||
 'proposed_actions, Browser-Automation, Email-Integration, OAuth, Software-Katalog. 127 Tests.',
 ARRAY['schema/22-ghost-autonomy.sql', 'schema/23-app-ecosystem.sql',
       'bridge/ghost_autonomy.py', 'bridge/app_manager.py'],
 ARRAY['tests/test_core.py', 'scripts/bootstrap.sh', 'schema/13-seed-data.sql'],
 ARRAY['22', '23'],
 106, 127,
 ARRAY['Ghost als Scheduler', 'Safety-First mit proposed_actions', 'Browser/Email/OAuth fernsteuern'],
 ARRAY['Wächter-Ghost für Genehmigungen', 'Playwright für Browser', 'IMAP/SMTP für Email', 'Append-Only Thought-Log']),

('2026-03-15', '0.6.0', '0.7.0',
 'System Memory: Vollständiges KI-Gehirn in die DB gespeichert. ' ||
 'Schema 24 (system_memory + agent_sessions Tabellen), Schema 25 (Seed mit komplettem Wissen). ' ||
 'Architektur, Schema-Karte, Design-Patterns, Konventionen, Workflows, Beziehungen, Inventar — alles als Zeilen.',
 ARRAY['schema/24-system-memory.sql', 'schema/25-system-memory-seed.sql'],
 ARRAY['tests/test_core.py', 'scripts/bootstrap.sh', 'schema/13-seed-data.sql'],
 ARRAY['24', '25'],
 127, NULL,  -- Tests werden noch gezählt
 ARRAY['Alles Wissen persistent machen', 'Neue KI-Session kann sofort loslegen', 'Kein Kontext geht verloren'],
 ARRAY['system_memory Tabelle für Meta-Wissen', 'agent_sessions für Session-Dokumentation', 'get_agent_context() für Kontext-Abruf']);

-- =============================================================================
-- FERTIG — Das vollständige Gehirn liegt jetzt in der Datenbank.
--
-- Eine neue KI-Session kann loslegen mit:
--   SELECT dbai_knowledge.get_agent_context();
--
-- Oder gezielt abfragen:
--   SELECT * FROM dbai_knowledge.get_memory_by_category('architecture');
--   SELECT * FROM dbai_knowledge.get_memory_by_category('workflow');
--   SELECT * FROM dbai_knowledge.get_memory_by_category('convention');
--   SELECT * FROM dbai_knowledge.vw_last_session;
-- =============================================================================
