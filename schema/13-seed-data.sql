-- =============================================================================
-- DBAI Schema 13: Seed Data — Komplettes Systemwissen
-- Alle DBAI-Komponenten, Fehler, ADRs und Abhängigkeiten vorgeladen
--
-- Diese Datei IST die README in Tabellenform.
-- SELECT * FROM dbai_knowledge.vw_module_overview;  → Ersetzt README.md
-- SELECT * FROM dbai_knowledge.error_patterns;       → Bekannte Fehler
-- SELECT * FROM dbai_knowledge.architecture_decisions; → Warum-Entscheidungen
-- =============================================================================

-- =============================================================================
-- 1. MODULE REGISTRY — Alle 44 DBAI-Dateien dokumentiert
-- =============================================================================

-- ─── Schemas (SQL) ───
INSERT INTO dbai_knowledge.module_registry
    (file_path, category, language, description, documentation, provides, depends_on, version, is_critical, boot_order, status) VALUES

('schema/00-extensions.sql', 'schema', 'sql',
 'Extensions, Schemas und Rollen — Fundament des gesamten Systems',
 'Erstellt alle PostgreSQL-Extensions (vector, uuid-ossp, pgcrypto, pg_stat_statements, pg_cron, pg_trgm), ' ||
 'die 7 Kern-Schemas (dbai_core, dbai_system, dbai_event, dbai_vector, dbai_journal, dbai_panic, dbai_llm) ' ||
 'und 4 DB-Rollen (dbai_system, dbai_monitor, dbai_llm, dbai_recovery) mit exakten Schema-Grants. ' ||
 'MUSS als erstes geladen werden, da alles andere darauf aufbaut.',
 ARRAY['dbai_core', 'dbai_system', 'dbai_event', 'dbai_vector', 'dbai_journal', 'dbai_panic', 'dbai_llm',
       'role:dbai_system', 'role:dbai_monitor', 'role:dbai_llm', 'role:dbai_recovery'],
 '{}',
 '1.0.0', TRUE, 1, 'active'),

('schema/01-core-tables.sql', 'schema', 'sql',
 'Core-Tabellen: Objects, Processes, Config, Drivers — das Fundament',
 'Vier zentrale Tabellen: ' ||
 '1) dbai_core.objects — UUID-Registry die Dateipfade ersetzt, jede Ressource hat eine ID statt /pfad/datei. ' ||
 '2) dbai_core.processes — Laufende Systemdienste mit Heartbeat und Priority (1-10). ' ||
 '3) dbai_core.config — Schlüssel-Wert-Konfiguration mit readonly-Schutz. ' ||
 '4) dbai_core.drivers — Hardware-Treiber-Registry mit Zuständen und Fehler-Tracking. ' ||
 'Enthält update_timestamp() Trigger und protect_readonly_config().',
 ARRAY['dbai_core.objects', 'dbai_core.processes', 'dbai_core.config', 'dbai_core.drivers',
       'function:dbai_core.update_timestamp', 'function:dbai_core.protect_readonly_config'],
 ARRAY['schema/00-extensions.sql'],
 '1.0.0', TRUE, 2, 'active'),

('schema/02-system-tables.sql', 'schema', 'sql',
 'System-Tabellen: Live-Hardware-Werte (CPU, RAM, Disk, Temperatur, Netz)',
 'Fünf Tabellen für Echtzeit-Hardware-Monitoring: ' ||
 'cpu, memory, disk, temperature, network. Jede Zeile = ein Messwert. ' ||
 'cleanup_old_metrics() löscht Daten älter als 24h. ' ||
 'View current_status zeigt den aktuellsten Wert jeder Kategorie.',
 ARRAY['dbai_system.cpu', 'dbai_system.memory', 'dbai_system.disk',
       'dbai_system.temperature', 'dbai_system.network',
       'function:dbai_system.cleanup_old_metrics', 'view:dbai_system.current_status'],
 ARRAY['schema/00-extensions.sql'],
 '1.0.0', TRUE, 3, 'active'),

('schema/03-event-tables.sql', 'schema', 'sql',
 'Event-Tabellen: Append-Only (Keyboard, Netzwerk, Power) mit Löschschutz',
 'Vier Event-Tabellen: events (Haupt), keyboard_events, network_events, power_events. ' ||
 'ALLE sind APPEND-ONLY: protect_events() Trigger verhindert DELETE/UPDATE. ' ||
 'dispatch_event() Funktion routet Events in die richtige Tabelle.',
 ARRAY['dbai_event.events', 'dbai_event.keyboard_events', 'dbai_event.network_events',
       'dbai_event.power_events', 'function:dbai_event.protect_events', 'function:dbai_event.dispatch_event'],
 ARRAY['schema/00-extensions.sql'],
 '1.0.0', TRUE, 4, 'active'),

('schema/04-vector-tables.sql', 'schema', 'sql',
 'Vektor-Tabellen: KI-Erinnerungen mit pgvector (1536 Dimensionen)',
 'Tabelle memories mit vector(1536) Spalte und HNSW-Index (Cosine). ' ||
 'search_memories() findet ähnliche Erinnerungen. ' ||
 'decay_relevance() reduziert automatisch die Relevanz alter Einträge. ' ||
 'knowledge_edges baut einen Wissensgraphen zwischen Erinnerungen.',
 ARRAY['dbai_vector.memories', 'dbai_vector.knowledge_edges',
       'function:dbai_vector.search_memories', 'function:dbai_vector.decay_relevance'],
 ARRAY['schema/00-extensions.sql'],
 '1.0.0', TRUE, 5, 'active'),

('schema/05-wal-journal.sql', 'schema', 'sql',
 'WAL-Journal: Append-Only Change-Log, Event-Log, Snapshots — PITR-Basis',
 'Drei Append-Only Tabellen: change_log, event_log, system_snapshots. ' ||
 'protect_journal() Trigger auf ALLEN Tabellen — NIEMALS löschbar. ' ||
 'log_change() Trigger wird automatisch auf Core-Tabellen installiert. ' ||
 'find_nearest_snapshot() und changes_since() ermöglichen Point-in-Time Recovery.',
 ARRAY['dbai_journal.change_log', 'dbai_journal.event_log', 'dbai_journal.system_snapshots',
       'function:dbai_journal.protect_journal', 'function:dbai_journal.log_change',
       'function:dbai_journal.find_nearest_snapshot', 'function:dbai_journal.changes_since'],
 ARRAY['schema/00-extensions.sql', 'schema/01-core-tables.sql'],
 '1.0.0', TRUE, 6, 'active'),

('schema/06-panic-schema.sql', 'schema', 'sql',
 'Kernel-Panic: Notfall-Treiber, Boot-Config, Repair-Scripts — schreibgeschützt nach Init',
 'Isoliertes Notfall-Schema: emergency_drivers (minimale Treiber), boot_config (Boot-Parameter), ' ||
 'repair_scripts (4 initiale Reparatur-Skripte), panic_log (Append-Only). ' ||
 'lock_after_init() sperrt das Schema nach Initialisierung. ' ||
 'execute_repair() führt Reparatur-Skripte aus. ' ||
 'Repair-Scripts: verify_core_schema, verify_journal_integrity, kill_zombie_processes, reset_stuck_locks.',
 ARRAY['dbai_panic.emergency_drivers', 'dbai_panic.boot_config', 'dbai_panic.repair_scripts',
       'dbai_panic.panic_log', 'function:dbai_panic.lock_after_init', 'function:dbai_panic.execute_repair'],
 ARRAY['schema/00-extensions.sql'],
 '1.0.0', TRUE, 7, 'active'),

('schema/07-row-level-security.sql', 'schema', 'sql',
 'Row-Level Security auf ALLEN Tabellen + Audit-Log',
 'RLS aktiviert auf allen Core-, System-, Event-, Vector-, Journal- und Panic-Tabellen. ' ||
 'Policies: dbai_system = voller Zugriff, dbai_llm = nur eigene Daten, dbai_monitor = read-only. ' ||
 'audit_log Tabelle (Append-Only) dokumentiert alle Zugriffe.',
 ARRAY['dbai_journal.audit_log', 'policy:rls_all_tables'],
 ARRAY['schema/01-core-tables.sql', 'schema/02-system-tables.sql', 'schema/03-event-tables.sql',
       'schema/04-vector-tables.sql', 'schema/05-wal-journal.sql', 'schema/06-panic-schema.sql'],
 '1.0.0', TRUE, 8, 'active'),

('schema/08-llm-integration.sql', 'schema', 'sql',
 'LLM-Integration: Models, Conversations, Task-Queue + SQL-Funktionen',
 'LLM direkt in der DB: models (Registry), conversations (mit Embeddings), ' ||
 'task_queue (mit Priorität). SQL-Funktionen: prompt() ruft LLM auf, ' ||
 'embed() erzeugt Vektoren, remember() speichert Erinnerungen mit Embedding, ' ||
 'recall() ist das RAG-Pattern (sucht ähnliche Erinnerungen).',
 ARRAY['dbai_llm.models', 'dbai_llm.conversations', 'dbai_llm.task_queue',
       'function:dbai_llm.prompt', 'function:dbai_llm.embed',
       'function:dbai_llm.remember', 'function:dbai_llm.recall'],
 ARRAY['schema/00-extensions.sql', 'schema/01-core-tables.sql', 'schema/04-vector-tables.sql'],
 '1.0.0', TRUE, 9, 'active'),

('schema/09-vacuum-schedule.sql', 'schema', 'sql',
 'Vacuum-Scheduling: Log, Konfiguration und Smart-Vacuum-Funktion',
 'vacuum_log speichert Ausführungshistorie, vacuum_config definiert Zeitpläne pro Tabelle. ' ||
 'System-Tabellen: aggressive (alle 5 Min), Journal: nur ANALYZE (kein Löschen!). ' ||
 'smart_vacuum() wählt automatisch die richtige Strategie. check_database_size() prüft Plattenplatz.',
 ARRAY['dbai_system.vacuum_log', 'dbai_system.vacuum_config',
       'function:dbai_system.smart_vacuum', 'function:dbai_system.check_database_size'],
 ARRAY['schema/00-extensions.sql'],
 '1.0.0', FALSE, 10, 'active'),

('schema/10-sync-primitives.sql', 'schema', 'sql',
 'Synchronisations-Primitiven: Advisory Locks mit Priorität + Deadlock-Erkennung',
 'lock_registry mit Priority-basiertem Locking: HW-Treiber (Prio 1-3) > System (4-6) > LLM (7-9). ' ||
 'acquire_lock() und release_lock() verwenden PostgreSQL Advisory Locks. ' ||
 'cleanup_expired_locks() räumt auf, detect_deadlocks() erkennt Verklemmungen.',
 ARRAY['dbai_core.lock_registry', 'dbai_core.lock_priority_config',
       'function:dbai_core.acquire_lock', 'function:dbai_core.release_lock',
       'function:dbai_core.cleanup_expired_locks', 'function:dbai_core.detect_deadlocks'],
 ARRAY['schema/00-extensions.sql', 'schema/01-core-tables.sql'],
 '1.0.0', FALSE, 11, 'active'),

('schema/11-knowledge-library.sql', 'schema', 'sql',
 'Knowledge Library: Selbstdokumentierende Wissensdatenbank (README als DB)',
 'Schema dbai_knowledge mit: module_registry (jede Datei dokumentiert), ' ||
 'module_dependencies (Abhängigkeitsgraph), changelog (Append-Only), ' ||
 'architecture_decisions (ADRs), system_glossary (Begriffe), known_issues, build_log. ' ||
 'Views: vw_module_overview, vw_undocumented_modules, vw_system_health, vw_boot_sequence. ' ||
 'Funktionen: impact_analysis(), generate_system_report(), search_modules(), get_dependency_chain().',
 ARRAY['dbai_knowledge', 'dbai_knowledge.module_registry', 'dbai_knowledge.module_dependencies',
       'dbai_knowledge.changelog', 'dbai_knowledge.architecture_decisions',
       'dbai_knowledge.system_glossary', 'dbai_knowledge.known_issues', 'dbai_knowledge.build_log',
       'function:dbai_knowledge.impact_analysis', 'function:dbai_knowledge.generate_system_report'],
 ARRAY['schema/00-extensions.sql', 'schema/01-core-tables.sql'],
 '1.0.0', TRUE, 12, 'active'),

('schema/12-error-patterns.sql', 'schema', 'sql',
 'Error Patterns & Runbooks: Automatische Fehlererkennung und -behebung',
 'error_patterns (Regex-basiertes Pattern-Matching), runbooks (Schritt-für-Schritt), ' ||
 'error_log (Append-Only, alle aufgetretenen Fehler), error_resolutions (Lösungshistorie). ' ||
 'log_error() matcht automatisch gegen Patterns und liefert Lösung. ' ||
 'find_runbook() findet passendes Runbook. error_statistics() zeigt Häufigkeiten.',
 ARRAY['dbai_knowledge.error_patterns', 'dbai_knowledge.runbooks',
       'dbai_knowledge.error_log', 'dbai_knowledge.error_resolutions',
       'function:dbai_knowledge.log_error', 'function:dbai_knowledge.find_runbook'],
 ARRAY['schema/00-extensions.sql', 'schema/01-core-tables.sql', 'schema/11-knowledge-library.sql'],
 '1.0.0', TRUE, 13, 'active'),

('schema/13-seed-data.sql', 'schema', 'sql',
 'Seed Data: Vorgeladenes Systemwissen — alle Module, Fehler, ADRs',
 'Diese Datei lädt das komplette Systemwissen in die Knowledge Library: ' ||
 'alle 52 Modul-Registrierungen, Abhängigkeiten, 12 Architektur-Entscheidungen, ' ||
 'bekannte Fehler-Patterns, Runbooks, Glossar und den initialen Changelog.',
 ARRAY['data:module_registry', 'data:error_patterns', 'data:architecture_decisions',
       'data:glossary', 'data:changelog', 'data:runbooks'],
 ARRAY['schema/11-knowledge-library.sql', 'schema/12-error-patterns.sql'],
 '1.0.0', FALSE, 14, 'active'),

('schema/14-self-healing.sql', 'schema', 'sql',
 'Self-Healing & Observability — Automatische Problemerkennung und Reparatur',
 'Health-Checks (8 Prüfungen: PG alive, Schema-Integrität, Zombies, Deadlocks, Connections, Panics, DB-Größe, offene Fehler), ' ||
 'Alert-Rules mit Schwellwerten und Auto-Heal, Alert-History (Append-Only), Telemetrie-Aggregation. ' ||
 'self_heal() führt kompletten Loop: Checks → Alerts → Fix.',
 ARRAY['table:dbai_system.health_checks', 'table:dbai_system.alert_rules',
       'table:dbai_system.alert_history', 'table:dbai_system.telemetry',
       'function:dbai_system.run_health_checks', 'function:dbai_system.evaluate_alerts',
       'function:dbai_system.self_heal'],
 ARRAY['schema/00-extensions.sql', 'schema/11-knowledge-library.sql'],
 '1.0.0', TRUE, 15, 'active'),

-- ─── Bridge (Python) ───
('bridge/system_bridge.py', 'bridge', 'python',
 'System Bridge — Der Zündschlüssel: Bootet DBAI in 7 Schritten',
 'Hauptprogramm das DBAI startet. 7-stufiger Boot-Prozess: ' ||
 '1) DB-Verbindung herstellen, 2) Schemas verifizieren, 3) Prozess registrieren, ' ||
 '4) Hardware-Monitor starten, 5) Hintergrund-Services (Heartbeat, PITR, Lock-Cleanup), ' ||
 '6) LLM-Bridge starten, 7) Vacuum-Scheduler. ' ||
 'CLI: start/status/stop. Config aus config/dbai.toml.',
 ARRAY['class:SystemBridge', 'function:boot', 'function:shutdown', 'function:verify_schemas'],
 ARRAY['schema/01-core-tables.sql', 'config/dbai.toml', 'bridge/hardware_monitor.py', 'llm/llm_bridge.py'],
 '1.0.0', TRUE, NULL, 'active'),

('bridge/hardware_monitor.py', 'bridge', 'python',
 'Hardware-Monitor: Liest CPU/RAM/Disk/Temp via psutil und schreibt in System-Tabellen',
 'Periodischer Monitor der Hardware-Werte in die dbai_system Tabellen schreibt. ' ||
 'Nutzt psutil für plattformunabhängige Hardware-Abfragen. ' ||
 'Wird von system_bridge.py als Hintergrund-Thread gestartet.',
 ARRAY['class:HardwareMonitor'],
 ARRAY['schema/02-system-tables.sql', 'bridge/c_bindings/libhw_interrupts.so'],
 '1.0.0', TRUE, NULL, 'active'),

('bridge/event_dispatcher.py', 'bridge', 'python',
 'Event Dispatcher: Liest /dev/input Events und schreibt sie als Tabellenzeilen',
 'Liest Hardware-Events über struct.unpack aus /dev/input Devices. ' ||
 'Dispatcht keyboard, mouse und network Events als INSERT in dbai_event Tabellen.',
 ARRAY['class:EventDispatcher'],
 ARRAY['schema/03-event-tables.sql'],
 '1.0.0', FALSE, NULL, 'active'),

-- ─── C-Bindings ───
('bridge/c_bindings/hw_interrupts.c', 'c_binding', 'c',
 'C-Bindings: Direkter Hardware-Zugriff (Memory, CPU, Disk, Interrupts)',
 'C-Code mit #define _POSIX_C_SOURCE 199309L für CLOCK_MONOTONIC. ' ||
 'Funktionen: get_memory_info() (aus /proc/meminfo), get_cpu_count(), get_cpu_info() (aus /proc/stat), ' ||
 'get_disk_info() (via statvfs), get_interrupt_count() (aus /proc/interrupts), ' ||
 'get_uptime_seconds() (aus /proc/uptime), get_timestamp_ns() (clock_gettime). ' ||
 'WICHTIG: _POSIX_C_SOURCE muss GANZ OBEN stehen, sonst Compile-Fehler.',
 ARRAY['function:get_memory_info', 'function:get_cpu_info', 'function:get_disk_info',
       'function:get_interrupt_count', 'function:get_uptime_seconds', 'function:get_timestamp_ns'],
 '{}',
 '1.0.0', TRUE, NULL, 'active'),

('bridge/c_bindings/hw_interrupts.h', 'c_binding', 'c',
 'C-Header: Struct-Definitionen für Hardware-Daten (MemoryInfo, CpuInfo, DiskInfo)',
 'Definiert drei Structs: MemoryInfo (total/free/available/swap), CpuInfo (user/system/idle/cores), ' ||
 'DiskInfo (total/free/used/used_percent). Alle Funktionen als extern deklariert.',
 ARRAY['struct:MemoryInfo', 'struct:CpuInfo', 'struct:DiskInfo'],
 '{}',
 '1.0.0', FALSE, NULL, 'active'),

('bridge/c_bindings/Makefile', 'c_binding', 'makefile',
 'Makefile: Kompiliert hw_interrupts.c zu libhw_interrupts.so (shared library)',
 'Flags: -Wall -Wextra -O2 -fPIC -std=c11 -shared. ' ||
 'Target: libhw_interrupts.so. Clean entfernt .o und .so.',
 ARRAY['target:libhw_interrupts.so'],
 ARRAY['bridge/c_bindings/hw_interrupts.c', 'bridge/c_bindings/hw_interrupts.h'],
 '1.0.0', FALSE, NULL, 'active'),

('bridge/c_bindings/libhw_interrupts.so', 'c_binding', 'so',
 'Kompilierte Shared Library — wird von Python via ctypes geladen',
 'Kompiliertes Binary aus hw_interrupts.c. Wird von hardware_monitor.py geladen.',
 ARRAY['library:libhw_interrupts'],
 ARRAY['bridge/c_bindings/hw_interrupts.c'],
 '1.0.0', TRUE, NULL, 'active'),

-- ─── Recovery ───
('recovery/pitr_manager.py', 'recovery', 'python',
 'PITR Manager: Point-in-Time Recovery, Snapshots, Base-Backups',
 'PITRManager-Klasse: create_snapshot() speichert aktuellen Zustand, ' ||
 'show_changes_since() zeigt Änderungen seit Zeitpunkt, ' ||
 'find_snapshot() findet nächsten Snapshot, create_base_backup() nutzt pg_basebackup, ' ||
 'restore_to_point() gibt Schritt-für-Schritt-Anleitung.',
 ARRAY['class:PITRManager'],
 ARRAY['schema/05-wal-journal.sql'],
 '1.0.0', TRUE, NULL, 'active'),

('recovery/mirror_sync.py', 'recovery', 'python',
 'Mirror Sync: Disk-Mirroring, Streaming-Replikation, rsync-Fallback',
 'MirrorSync-Klasse: check_mirrors() prüft Mirror-Zustand, ' ||
 'setup_streaming_replication() konfiguriert PG Streaming, ' ||
 'sync_with_rsync() als Fallback, verify_mirror_integrity() verifiziert, ' ||
 'failover_to_mirror() schaltet auf Mirror um.',
 ARRAY['class:MirrorSync'],
 ARRAY['config/dbai.toml'],
 '1.0.0', TRUE, NULL, 'active'),

('recovery/panic_recovery.py', 'recovery', 'python',
 'Panic Recovery: 9 Panic-Handler + Volldiagnose mit CLI',
 'PanicRecovery-Klasse mit 9 spezialisierten Handlern: ' ||
 'db_corruption, disk_failure, memory_overflow, deadlock_cascade, ' ||
 'llm_runaway, data_integrity, boot_failure, driver_crash, unknown. ' ||
 'full_diagnostic() führt 5 Prüfungen durch. CLI: diagnose/recover/status.',
 ARRAY['class:PanicRecovery'],
 ARRAY['schema/06-panic-schema.sql'],
 '1.0.0', TRUE, NULL, 'active'),

-- ─── LLM ───
('llm/llm_bridge.py', 'llm', 'python',
 'LLM Bridge: llama.cpp Integration — Modell bleibt in RAM, Daten in der DB',
 'LLMBridge-Klasse: load_model() lädt GGUF via llama-cpp-python, ' ||
 'generate() generiert Text, embed() erzeugt Embeddings (normalisiert auf 1536 Dim), ' ||
 '_process_task_queue() liest aus dbai_llm.task_queue, ' ||
 '_execute_task() führt query/embedding/analysis tasks aus.',
 ARRAY['class:LLMBridge'],
 ARRAY['schema/08-llm-integration.sql'],
 '1.0.0', TRUE, NULL, 'active'),

-- ─── Config ───
('config/dbai.toml', 'config', 'toml',
 'TOML-Konfiguration: Alle DBAI-Subsysteme zentral konfiguriert',
 'Sektionen: [database], [wal], [pitr], [mirror], [hardware_monitor], ' ||
 '[vacuum], [llm], [security], [panic]. Wird von system_bridge.py gelesen.',
 ARRAY['config:database', 'config:wal', 'config:pitr', 'config:mirror',
       'config:hardware_monitor', 'config:vacuum', 'config:llm', 'config:security'],
 '{}',
 '1.0.0', TRUE, NULL, 'active'),

('config/postgresql.conf', 'config', 'conf',
 'PostgreSQL-Konfiguration: Optimiert für DBAI (4GB shared_buffers, WAL, RLS)',
 'shared_buffers=4GB, WAL-Archivierung aktiviert, autovacuum aggressiv, ' ||
 'row_security=on, deadlock_timeout=1s, shared_preload_libraries=pg_stat_statements,vector. ' ||
 'KEIN listen auf 0.0.0.0 — nur 127.0.0.1.',
 ARRAY['config:postgresql'],
 '{}',
 '1.0.0', TRUE, NULL, 'active'),

('config/pg_hba.conf', 'config', 'conf',
 'Client-Auth: peer für local, SCRAM-SHA-256 für localhost, KEINE externen Verbindungen',
 'Drei Regeln: 1) local → peer (Unix-Socket). 2) host 127.0.0.1/32 → scram-sha-256. ' ||
 '3) KEINE Regel für 0.0.0.0/0 oder externe IPs. Maximale Sicherheit.',
 ARRAY['config:pg_hba'],
 '{}',
 '1.0.0', TRUE, NULL, 'active'),

-- ─── Scripts ───
('scripts/install.sh', 'script', 'bash',
 'Install-Script: PostgreSQL, pgvector, Python-venv, C-Bindings',
 'Installiert: PostgreSQL (apt/dnf), pgvector (aus Source falls nötig), ' ||
 'Python-venv mit pip install -r requirements.txt, kompiliert C-Bindings via make.',
 ARRAY['action:install_postgresql', 'action:install_pgvector', 'action:create_venv', 'action:compile_c'],
 '{}',
 '1.0.0', FALSE, NULL, 'active'),

('scripts/bootstrap.sh', 'script', 'bash',
 'Bootstrap: DB erstellen, alle 14 Schemas laden, Config schreiben, Integrität prüfen',
 'Fünf Schritte: 1) PostgreSQL-Erreichbarkeit prüfen. 2) Datenbank "dbai" erstellen. ' ||
 '3) Alle SQL-Schemas in Reihenfolge (00-13) laden. 4) Initiale dbai_core.config. ' ||
 '5) Schema-Integrität prüfen (Anzahl Schemas und Tabellen).',
 ARRAY['action:create_database', 'action:load_schemas', 'action:verify_integrity'],
 ARRAY['scripts/install.sh', 'schema/00-extensions.sql'],
 '1.0.0', FALSE, NULL, 'active'),

('scripts/backup.sh', 'script', 'bash',
 'Backup: pg_dump + Schema-Only + Journal-CSV-Export mit Retention',
 'Drei Backup-Arten: 1) pg_dump komplett. 2) Schema-Only Backup. 3) Journal-CSV Export. ' ||
 'Retention-Cleanup löscht alte Backups.',
 ARRAY['action:pg_dump', 'action:schema_backup', 'action:journal_export'],
 '{}',
 '1.0.0', FALSE, NULL, 'active'),

('scripts/health_check.py', 'script', 'python',
 'Health Check: Prüft Filesystem, PostgreSQL, Schemas, Tabellen, Extensions, Prozesse',
 'Prüft: 1) Filesystem-Zustand. 2) PostgreSQL-Erreichbarkeit. 3) Alle Schemas vorhanden. ' ||
 '4) Tabellen-Integrität. 5) Extensions geladen. 6) Prozess-Heartbeats. ' ||
 '7) Journal-Konsistenz. 8) Panic-Status. 9) DB-Größe. 10) Python-Pakete.',
 ARRAY['function:check_filesystem', 'function:check_postgresql', 'function:check_schemas'],
 ARRAY['schema/00-extensions.sql'],
 '1.0.0', FALSE, NULL, 'active'),

-- ─── Tests ───
('tests/test_core.py', 'test', 'python',
 'Unit-Tests: 18 Tests in 5 Klassen (Schema, Config, Bridge, C-Bindings, Struktur)',
 'TestSchemaFiles: 6 Tests (Dateien existieren, nicht leer, CREATE vorhanden, keine Dateipfade, Append-Only, RLS). ' ||
 'TestConfigFiles: 4 Tests (TOML/PG-Conf existieren, keine ext. APIs, nur localhost). ' ||
 'TestSystemBridge: 2 Tests (Import, Methoden). ' ||
 'TestCBindings: 3 Tests (Dateien, Structs, Kompilierbarkeit). ' ||
 'TestDirectoryStructure: 2 Tests (alle Dirs, alle Files). ' ||
 'Alle 18 Tests bestanden.',
 ARRAY['class:TestSchemaFiles', 'class:TestConfigFiles', 'class:TestSystemBridge',
       'class:TestCBindings', 'class:TestDirectoryStructure'],
 ARRAY['schema/00-extensions.sql', 'bridge/system_bridge.py', 'bridge/c_bindings/hw_interrupts.c'],
 '1.0.0', FALSE, NULL, 'active'),

-- ─── Dokumentation ───
('README.md', 'documentation', 'markdown',
 'Projekt-README: Architektur-Übersicht, Technische Bausteine, Schnellstart',
 'Enthält: ASCII-Architektur-Diagramm, Baustein-Tabelle, 3-Schichten-Sicherheit, ' ||
 'No-Go-Liste, Verzeichnisstruktur, Schnellstart-Anleitung, Voraussetzungen. ' ||
 'HINWEIS: Die vollständige, aktuelle Doku ist jetzt in der DB: SELECT dbai_knowledge.generate_system_report();',
 ARRAY['doc:architecture', 'doc:quickstart', 'doc:nogo_list'],
 '{}',
 '1.0.0', FALSE, NULL, 'active'),

('requirements.txt', 'config', 'txt',
 'Python-Abhängigkeiten: psycopg2, psutil, llama-cpp-python, toml, pytest',
 'Pakete: psycopg2-binary, psutil, llama-cpp-python, toml, pytest, pytest-cov.',
 ARRAY['dep:psycopg2', 'dep:psutil', 'dep:llama-cpp-python', 'dep:toml', 'dep:pytest'],
 '{}',
 '1.0.0', FALSE, NULL, 'active'),

-- ─── Ghost System (v0.3.0) ───
('schema/15-ghost-system.sql', 'schema', 'sql',
 'Ghost in the Shell: Hot-Swap KI-System mit Rollen-basiertem Model-Management',
 'Schema dbai_ghost mit: ghost_models (GGUF-Registry), ghost_assignments (Rolle→Modell, UNIQUE), ' ||
 'ghost_swap_log (Append-Only), ghost_conversations (Chat+Embeddings), ghost_capabilities, ghost_compatibility. ' ||
 'Funktionen: swap_ghost() atomarer Tausch + NOTIFY, ask_ghost() routet an aktiven Ghost, ' ||
 'evaluate_ghost_health(), auto_optimize_ghosts(). Rollen: system_admin/operator/analyst/creative/security.',
 ARRAY['dbai_ghost', 'dbai_ghost.ghost_models', 'dbai_ghost.ghost_assignments',
       'dbai_ghost.ghost_swap_log', 'dbai_ghost.ghost_conversations',
       'function:dbai_ghost.swap_ghost', 'function:dbai_ghost.ask_ghost'],
 ARRAY['schema/00-extensions.sql', 'schema/08-llm-integration.sql'],
 '0.3.0', TRUE, 16, 'active'),

('schema/16-desktop-ui.sql', 'schema', 'sql',
 'Desktop UI: Browser-basiertes Window-Management mit Boot-Sequenz und Auth',
 'Schema dbai_desktop mit: users (bcrypt), sessions (JWT), themes (JSONB-Colors), ' ||
 'desktop_config, applications (7 Apps), windows (Draggable+State), notifications, boot_sequence. ' ||
 'Funktionen: authenticate_user(), create_session(), get_desktop_state(), open_window(), close_window(). ' ||
 'NOTIFY-Channels: desktop_notification, window_update.',
 ARRAY['dbai_desktop', 'dbai_desktop.users', 'dbai_desktop.sessions', 'dbai_desktop.themes',
       'dbai_desktop.applications', 'dbai_desktop.windows', 'dbai_desktop.boot_sequence',
       'function:dbai_desktop.authenticate_user', 'function:dbai_desktop.open_window'],
 ARRAY['schema/00-extensions.sql'],
 '0.3.0', TRUE, 17, 'active'),

('schema/17-ghost-desktop-seed.sql', 'schema', 'sql',
 'Seed-Daten fuer Ghost+Desktop: 5 KI-Modelle, 3 Themes, 7 Apps, Boot-Sequenz',
 'Laedt: 5 Ghost-Modelle (Qwen2.5, Mistral, Phi-3, CodeLlama, Llama-Guard), ' ||
 '5 Ghost-Assignments, Capabilities, 3 Themes (Cyberpunk/Light/Matrix), ' ||
 '7 Desktop-Apps, 15 Boot-Steps, Admin-User (admin/admin).',
 ARRAY['data:ghost_models', 'data:ghost_assignments', 'data:themes', 'data:applications', 'data:boot_sequence'],
 ARRAY['schema/15-ghost-system.sql', 'schema/16-desktop-ui.sql'],
 '0.3.0', FALSE, 18, 'active'),

-- ─── Web-Server (v0.3.0) ───
('web/server.py', 'web', 'python',
 'FastAPI Web-Server: REST API + WebSocket Bridge fuer Desktop UI',
 'Endpunkte: /api/auth/login, /api/boot/sequence, /api/desktop, /api/apps, /api/windows/*, ' ||
 '/api/ghosts (list/swap/ask), /api/system/*, /api/knowledge/*, /api/sql/execute (SELECT only). ' ||
 'WebSocket /ws mit JWT-Auth streamt PG NOTIFY Events (ghost_swap, desktop_notification, window_update). ' ||
 'Port 8420.',
 ARRAY['endpoint:/api/auth/login', 'endpoint:/api/desktop', 'endpoint:/api/ghosts',
       'endpoint:/ws', 'class:FastAPI'],
 ARRAY['schema/15-ghost-system.sql', 'schema/16-desktop-ui.sql'],
 '0.3.0', TRUE, NULL, 'active'),

('web/ghost_dispatcher.py', 'web', 'python',
 'Ghost Dispatcher: Hot-Swap Manager fuer KI-Modelle via llama-cpp-python',
 'Hoert auf PG NOTIFY ghost_swap Channel, laedt/entlaedt GGUF-Modelle in RAM. ' ||
 'Thread-basiertes Laden, VRAM-Tracking, Task-Queue aus dbai_llm.task_queue.',
 ARRAY['class:GhostDispatcher', 'function:load_model', 'function:unload_model'],
 ARRAY['schema/15-ghost-system.sql', 'schema/08-llm-integration.sql'],
 '0.3.0', TRUE, NULL, 'active'),

-- ─── Hardware Abstraction Layer (v0.4.0) ───
('schema/18-hardware-abstraction.sql', 'schema', 'sql',
 'Hardware Abstraction Layer: Alle physischen Geräte als Tabellenzeilen',
 '10 Tabellen: hardware_inventory (alle Geräte), gpu_devices (NVIDIA/AMD mit VRAM), ' ||
 'gpu_vram_map (Belegung pro Modell), cpu_cores (pro Kern), memory_map (Prozess→RAM), ' ||
 'storage_health (SMART), fan_control, power_profiles (4 Modi), network_connections, hotplug_events. ' ||
 'Funktionen: check_gpu_available(), allocate_vram(), release_vram(), activate_power_profile(). ' ||
 'Views: vw_gpu_overview, vw_hardware_summary, vw_active_power_profile. RLS auf allen Tabellen.',
 ARRAY['dbai_system.hardware_inventory', 'dbai_system.gpu_devices', 'dbai_system.gpu_vram_map',
       'dbai_system.cpu_cores', 'dbai_system.memory_map', 'dbai_system.storage_health',
       'dbai_system.fan_control', 'dbai_system.power_profiles', 'dbai_system.network_connections',
       'dbai_system.hotplug_events',
       'function:dbai_system.check_gpu_available', 'function:dbai_system.allocate_vram',
       'function:dbai_system.release_vram', 'function:dbai_system.activate_power_profile',
       'view:dbai_system.vw_gpu_overview', 'view:dbai_system.vw_hardware_summary'],
 ARRAY['schema/00-extensions.sql', 'schema/02-system-tables.sql'],
 '0.4.0', TRUE, 19, 'active'),

('schema/19-neural-bridge.sql', 'schema', 'sql',
 'Neural Bridge: Boot-Konfiguration, Treiber-Registry, Capabilities, Benchmarks',
 '5 Tabellen: boot_config (gpu_mode, kiosk, daemon-flags), neural_bridge_config (Kategorien), ' ||
 'driver_registry (Python+SQL Treiber-Paare), system_capabilities (Hardware-Features), ' ||
 'ghost_benchmarks (Token/s pro Modell+GPU). ' ||
 'Funktionen: get_boot_config() (JSON), auto_swap_on_gpu_change() (Trigger), match_driver_for_device(). ' ||
 'NOTIFY: ghost_gpu_migration, ghost_gpu_available.',
 ARRAY['dbai_core.boot_config', 'dbai_core.neural_bridge_config', 'dbai_core.driver_registry',
       'dbai_core.system_capabilities', 'dbai_llm.ghost_benchmarks',
       'function:dbai_core.get_boot_config', 'function:dbai_llm.auto_swap_on_gpu_change',
       'function:dbai_core.match_driver_for_device'],
 ARRAY['schema/00-extensions.sql', 'schema/18-hardware-abstraction.sql'],
 '0.4.0', TRUE, 20, 'active'),

('schema/20-hw-seed-data.sql', 'schema', 'sql',
 'Seed-Daten fuer HAL+Neural Bridge: Power-Profile, Boot-Configs, Treiber, Capabilities',
 '4 Power-Profile (sparmodus/balanced/cyberbrain/silent), 4 Boot-Configs (default/kiosk/headless/recovery), ' ||
 '22 Neural-Bridge-Config-Eintraege, 7 Treiber-Registry-Eintraege, 10 System-Capabilities.',
 ARRAY['data:power_profiles', 'data:boot_config', 'data:neural_bridge_config',
       'data:driver_registry', 'data:system_capabilities'],
 ARRAY['schema/18-hardware-abstraction.sql', 'schema/19-neural-bridge.sql'],
 '0.4.0', FALSE, 21, 'active'),

-- ─── Bridge: HAL Daemons (v0.4.0) ───
('bridge/hardware_scanner.py', 'bridge', 'python',
 'Hardware Scanner: Scannt CPU/RAM/Disk/Netz/PCI und schreibt in Hardware-Inventory',
 'HardwareScanner-Klasse: scan_cpu() (Kerne, Features, AVX2/AVX-512), scan_memory() (Prozess-Map), ' ||
 'scan_storage() (SMART-Risiko), scan_network(), scan_fans(), scan_motherboard(), scan_pci_devices(). ' ||
 'full_scan() aktualisiert alle hardware_inventory-Eintraege. daemon_loop() fuer periodisches Scanning. ' ||
 'CLI: python3 -m bridge.hardware_scanner [--daemon] [--json].',
 ARRAY['class:HardwareScanner', 'function:scan_cpu', 'function:scan_memory',
       'function:scan_storage', 'function:scan_network', 'function:full_scan'],
 ARRAY['schema/18-hardware-abstraction.sql'],
 '0.4.0', TRUE, NULL, 'active'),

('bridge/gpu_manager.py', 'bridge', 'python',
 'GPU Manager: VRAM-Tracking, Multi-GPU, Thermal Protection, Power-Profile',
 'GPUManager-Klasse: discover_and_register() (pynvml + nvidia-smi Fallback), update_metrics(), ' ||
 'check_vram_for_model(), allocate_for_ghost(), release_ghost_vram(), get_optimal_gpu_layers(), ' ||
 'plan_multi_gpu_split(), apply_gpu_power_limit(), set_persistence_mode(). ' ||
 'Thermal Protection: Warning 80C, Critical 90C mit Auto-Migration. ' ||
 'NOTIFY Listener: power_profile_change, fan_control, gpu_overheat.',
 ARRAY['class:GPUManager', 'function:discover_and_register', 'function:allocate_for_ghost',
       'function:plan_multi_gpu_split', 'function:update_metrics'],
 ARRAY['schema/18-hardware-abstraction.sql', 'schema/19-neural-bridge.sql'],
 '0.4.0', TRUE, NULL, 'active'),

-- ─── OpenClaw Bridge (v0.5.0) ───
('schema/21-openclaw-bridge.sql', 'schema', 'sql',
 'OpenClaw Bridge: Migration, Skill-Uebersetzung, Telegram-Sync, App-Mode',
 '6 Tabellen: openclaw_skills (JS/TS→SQL), openclaw_memories (JSON→pgvector), ' ||
 'migration_jobs (Import-Tracking), telegram_bridge (Bot→DB), app_streams (App=Datenstrom), ' ||
 'openclaw_compat_map (Feature-Vergleich). ' ||
 'Funktionen: import_openclaw_memory(), register_openclaw_skill(), process_telegram_message(), ' ||
 'openclaw_migration_report(). Views: vw_openclaw_skills, vw_openclaw_memory_status, ' ||
 'vw_telegram_stats, vw_migration_overview. RLS auf allen 6 Tabellen. 10 Compat-Map-Eintraege.',
 ARRAY['dbai_core.openclaw_skills', 'dbai_vector.openclaw_memories', 'dbai_core.migration_jobs',
       'dbai_event.telegram_bridge', 'dbai_ui.app_streams', 'dbai_core.openclaw_compat_map',
       'function:dbai_vector.import_openclaw_memory', 'function:dbai_core.register_openclaw_skill',
       'function:dbai_event.process_telegram_message', 'function:dbai_core.openclaw_migration_report'],
 ARRAY['schema/00-extensions.sql', 'schema/15-ghost-system.sql', 'schema/04-vector-tables.sql'],
 '0.5.0', TRUE, 22, 'active'),

('bridge/openclaw_importer.py', 'bridge', 'python',
 'OpenClaw Importer: Scannt und migriert OpenClaw/SillyTavern/Oobabooga-Daten in DBAI',
 'OpenClawScanner: Erkennt Projekttyp (openclaw_telegram, oobabooga, koboldai, sillytavern), ' ||
 'scannt Memories/Skills/Config/Characters. OpenClawImporter: import_memories() migriert JSON→pgvector, ' ||
 'import_skills() analysiert JS/TS und bewertet Kompatibilitaet, import_config() liest Personas. ' ||
 'TelegramBridge: process_message() schreibt in DB, listen_for_responses() via NOTIFY. ' ||
 'CLI: --scan, --import, --import-memories, --import-skills, --report, --telegram-setup.',
 ARRAY['class:OpenClawScanner', 'class:OpenClawImporter', 'class:TelegramBridge',
       'function:import_memories', 'function:import_skills', 'function:full_import'],
 ARRAY['schema/21-openclaw-bridge.sql'],
 '0.5.0', TRUE, NULL, 'active'),

('schema/22-ghost-autonomy.sql', 'schema', 'sql',
 'Ghost Autonomy: Safety-First Scheduling mit proposed_actions',
 'Ghost wird zentraler Scheduler mit Sicherheitsmechanismen. ' ||
 'proposed_actions definiert Aktionen die vor Ausfuehrung genehmigt werden muessen. ' ||
 'ghost_context injiziert Hardware/Logs/Praeferenzen in den LLM-Prompt. ' ||
 'ghost_thought_log fuer transparentes KI-Denken, energy_consumption fuer intelligentes Power-Management. ' ||
 'ghost_files fuer autonome Dateiorganisation, ghost_feedback fuer Lernen aus Feedback.',
 ARRAY['dbai_core.proposed_actions', 'dbai_core.ghost_context', 'dbai_core.ghost_thought_log',
       'dbai_core.process_importance', 'dbai_core.energy_consumption', 'dbai_core.ghost_files',
       'dbai_core.ghost_feedback', 'dbai_core.api_keys',
       'function:dbai_core.propose_action', 'function:dbai_core.approve_action',
       'function:dbai_core.reject_action', 'function:dbai_core.load_ghost_context'],
 ARRAY['schema/15-ghost-system.sql', 'schema/18-hardware-abstraction.sql'],
 '0.6.0', TRUE, 24, 'active'),

('schema/23-app-ecosystem.sql', 'schema', 'sql',
 'App Ecosystem: Software-Katalog, Browser, Email, OAuth, Command Interface',
 'Jede App ist ein Datenstrom in einer Tabelle — die KI sieht Daten, nicht Pixel. ' ||
 'software_catalog als App Store Repository. browser_sessions fuer Headless-Browser-Steuerung. ' ||
 'email_accounts + inbox + outbox fuer IMAP/SMTP Integration. ' ||
 'oauth_connections fuer Google/GitHub/Drive. workspace_sync fuer Dateisynchronisation. ' ||
 'command_history fuer Natural Language → SQL → Python Command Interface.',
 ARRAY['dbai_core.software_catalog', 'dbai_core.browser_sessions', 'dbai_event.email_accounts',
       'dbai_event.inbox', 'dbai_event.outbox', 'dbai_core.oauth_connections',
       'dbai_core.workspace_sync', 'dbai_core.command_history',
       'function:dbai_core.install_software', 'function:dbai_core.browse_url',
       'function:dbai_event.send_email', 'function:dbai_event.search_inbox',
       'function:dbai_core.process_command'],
 ARRAY['schema/22-ghost-autonomy.sql'],
 '0.6.0', TRUE, 24, 'active'),

('bridge/ghost_autonomy.py', 'bridge', 'python',
 'Ghost Autonomy Daemon: Kontext-Injektion, Energie-Monitoring, Prozessklassifikation',
 'GhostAutonomyDaemon Klasse mit: inject_context() laedt Hardware/Logs/Praeferenzen als LLM-Prompt, ' ||
 'monitor_energy() trackt CPU/RAM/GPU-Verbrauch pro Prozess, ' ||
 'classify_processes() bewertet Wichtigkeit mit KI, index_file() organisiert Dateien, ' ||
 'execute_approved_actions() fuehrt genehmigte Aktionen aus, log_thought() speichert KI-Gedanken. ' ||
 'Daemon: LISTEN action_approved/action_rejected/ghost_swap. CLI: --daemon.',
 ARRAY['class:GhostAutonomyDaemon',
       'function:inject_context', 'function:monitor_energy', 'function:classify_processes',
       'function:execute_approved_actions', 'function:index_file'],
 ARRAY['schema/22-ghost-autonomy.sql'],
 '0.6.0', TRUE, NULL, 'active'),

('bridge/app_manager.py', 'bridge', 'python',
 'App Manager: Software-Katalog, Browser-Automation, Email-Bridge, OAuth',
 'SoftwareCatalog: scan_apt/scan_pip/scan_github_trending/install_package fuer Paketquellen. ' ||
 'BrowserAutomation: open_url/extract_text via Playwright (Headless Chromium) — KI sieht Text, nicht Pixel. ' ||
 'EmailBridge: sync_inbox/send_email/search_inbox via IMAP/SMTP → inbox/outbox Tabellen. ' ||
 'OAuthManager: connect_google/refresh_token/sync_drive. AppManagerDaemon: LISTEN Events fuer automation. ' ||
 'CLI: --scan-packages, --browse URL, --sync-email, --scan-github, --daemon.',
 ARRAY['class:SoftwareCatalog', 'class:BrowserAutomation', 'class:EmailBridge',
       'class:OAuthManager', 'class:AppManagerDaemon'],
 ARRAY['schema/23-app-ecosystem.sql'],
 '0.6.0', TRUE, NULL, 'active'),

('schema/24-system-memory.sql', 'schema', 'sql',
 'System Memory: Langzeitgedaechtnis der KI mit agent_sessions',
 'Tabelle system_memory: Speichert Architektur, Konventionen, Design-Patterns, Schema-Map, ' ||
 'Workflows, Tech-Inventar, Beziehungen — alles was zwischen KI-Sessions ueberleben muss. ' ||
 'Tabelle agent_sessions: Dokumentiert jede Arbeitssitzung. ' ||
 'Funktionen: get_agent_context() gibt kompletten Kontext als Text, ' ||
 'save_memory() UPSERT fuer Wissenseintraege, get_memory_by_category() nach Kategorie.' ,
 ARRAY['dbai_knowledge.system_memory', 'dbai_knowledge.agent_sessions',
       'function:dbai_knowledge.get_agent_context', 'function:dbai_knowledge.save_memory',
       'function:dbai_knowledge.get_memory_by_category',
       'view:dbai_knowledge.vw_system_context', 'view:dbai_knowledge.vw_last_session'],
 ARRAY['schema/11-knowledge-library.sql'],
 '0.7.0', TRUE, 26, 'active'),

('schema/25-system-memory-seed.sql', 'data', 'sql',
 'System Memory Seed: Vollstaendiges KI-Gehirn als Daten',
 'Laedt ~35 Wissenseintraege in system_memory: Identitaet (Was ist DBAI/TabulaOS), ' ||
 'Architektur (4-Schichten, Verzeichnisstruktur, Boot-Sequenz), Schema-Karte (alle 9 Schemas mit Tabellen), ' ||
 'Rollen & Sicherheit, Design-Patterns (NOTIFY, Append-Only, Safety-First, Hot-Swap, Remote-Control), ' ||
 'Konventionen (Naming, Testing, Seed-Data), Beziehungen (Ghost↔Hardware, Autonomy↔Safety), ' ||
 'Tech-Inventar (DB, Python, Frontend, Bridges), Workflows (Feature hinzufuegen, Seed-Data editieren), ' ||
 'Operational (NOTIFY-Channels, Defaults), Roadmap. Plus 7 agent_sessions (v0.1.0-v0.7.0).',
 ARRAY['data:system_memory', 'data:agent_sessions'],
 ARRAY['schema/24-system-memory.sql'],
 '0.7.0', FALSE, 26, 'active')
ON CONFLICT DO NOTHING;

-- =============================================================================
-- 2. ARCHITEKTUR-ENTSCHEIDUNGEN (ADRs) — Warum wurde was wie gebaut
-- =============================================================================

INSERT INTO dbai_knowledge.architecture_decisions
    (title, status, context, decision, consequences, alternatives, decided_by) VALUES

('PostgreSQL als OS-Kern statt Custom DB',
 'accepted',
 'DBAI braucht einen relationalen Kern der Transaktionen, MVCC, WAL und Row-Level Security bietet. ' ||
 'Optionen waren: PostgreSQL, DuckDB, SQLite, Custom Engine.',
 'PostgreSQL 16+ als Kern-Datenbank. Gründe: ausgereiftes MVCC, WAL-basierte Recovery, ' ||
 'pgvector für KI-Vektoren, pg_cron für Scheduling, Row-Level Security, breite Extension-Library.',
 'Pro: Robust, erprobt, große Community. Contra: Overhead für einfache Operationen, Speicherverbrauch.',
 '[{"option":"DuckDB","pros":["Schnell für Analytics","Embedded"],"cons":["Kein Server-Modus","Keine RLS","Kein pgvector"]},
   {"option":"SQLite","pros":["Minimal","Embedded"],"cons":["Keine RLS","Kein pgvector","Single-Writer"]},
   {"option":"Custom","pros":["Volle Kontrolle"],"cons":["Jahrelange Entwicklung","Keine Community"]}]'::JSONB,
 'system'),

('Python + C-Bindings statt reines C oder Rust',
 'accepted',
 'Die System Bridge braucht sowohl High-Level DB-Zugriff als auch Low-Level Hardware-Zugriff.',
 'Python 3.11+ als Hauptsprache für Bridge, Recovery, LLM. C (gcc) für Hardware-Interrupt-Handler ' ||
 'als Shared Library (.so), geladen via ctypes. Python bietet schnelle Entwicklung und psycopg2, ' ||
 'C bietet direkten /proc und /dev Zugriff.',
 'Pro: Schnelle Entwicklung, gute DB-Libraries. Contra: Python-GIL limitiert echte Parallelität.',
 '[{"option":"Reines C","pros":["Maximal schnell","Kein GIL"],"cons":["Langsame Entwicklung","Keine psycopg2"]},
   {"option":"Rust","pros":["Sicher","Schnell"],"cons":["Steile Lernkurve","Weniger DB-Libraries"]},
   {"option":"Go","pros":["Goroutines","Kompiliert"],"cons":["Kein ctypes","Weniger DB-Ökosystem"]}]'::JSONB,
 'human+system'),

('llama.cpp eingebettet statt externer LLM-API',
 'accepted',
 'DBAI braucht ein LLM für KI-Funktionen. No-Go: Keine externen API-Abhängigkeiten.',
 'llama.cpp via llama-cpp-python eingebettet. Modell (GGUF) bleibt im RAM, ' ||
 'Daten verlassen NIEMALS die Datenbank. Kein OpenAI, kein Cloud-Service.',
 'Pro: Volle Datenkontrolle, keine Latenz, kein API-Key. Contra: Braucht lokale GPU/CPU, begrenzte Modellgröße.',
 '[{"option":"OpenAI API","pros":["Leistungsstark","Einfach"],"cons":["DATEN VERLASSEN DAS SYSTEM","Kosten","Abhängigkeit"]},
   {"option":"vLLM Server","pros":["Schnell","GPU-optimiert"],"cons":["Externer Service","Netzwerk nötig"]},
   {"option":"Ollama","pros":["Einfach"],"cons":["Externer Prozess","Weniger Kontrolle"]}]'::JSONB,
 'human'),

('UUID statt Dateipfade als Objekt-Identifikator',
 'accepted',
 'Klassische OS nutzen Dateipfade (z.B. absolute Pfade im Dateisystem). Das ist fehleranfällig, ' ||
 'schwer zu tracken und bricht bei Umbenennungen.',
 'Jede Ressource bekommt eine UUID in dbai_core.objects. Dateipfade sind verboten (No-Go). ' ||
 'Metadaten in JSONB, Hash+Pointer für externe Binärdaten.',
 'Pro: Keine broken Links, durchsuchbare Metadaten, Versionierung. Contra: Braucht Lookup.',
 '[{"option":"Dateipfade","pros":["Vertraut","Direkt"],"cons":["Bricht bei Rename","Nicht durchsuchbar","No-Go!"]},
   {"option":"Content-Addressable","pros":["Deduplizierung"],"cons":["Komplex","Kein Name"]}]'::JSONB,
 'human'),

('Append-Only Logs statt löschbare Logs',
 'accepted',
 'System-Logs, Journal und Panic-Logs dürfen nie verloren gehen. ' ||
 'Klassische Logs können rotiert oder gelöscht werden.',
 'Alle Journal- und Event-Tabellen sind Append-Only. Trigger verhindern DELETE und UPDATE ' ||
 'auf Kernfeldern. Nur Resolution-Flags dürfen aktualisiert werden.',
 'Pro: Vollständige Audit-Trail, PITR möglich, forensische Analyse. Contra: Wachsender Speicher.',
 '[{"option":"Löschbare Logs","pros":["Spart Platz"],"cons":["Beweise gehen verloren","Kein PITR"]},
   {"option":"Log-Rotation","pros":["Kompromiss"],"cons":["Alte Daten weg","Komplexität"]}]'::JSONB,
 'human+system'),

('Wissensdatenbank in der DB statt README.md Dateien',
 'accepted',
 'Klassische Projekte dokumentieren in README.md, CHANGELOG.md, ADR-Dateien. ' ||
 'Problem: Dokumentation wird vergessen, veraltet, ist nicht durchsuchbar, ' ||
 'und bei Fehlern muss man erst suchen statt direkt zu handeln.',
 'Die gesamte Dokumentation liegt IN der Datenbank (dbai_knowledge Schema). ' ||
 'Jede Datei ist eine Zeile in module_registry. Fehler-Patterns, Runbooks, ' ||
 'Glossar, ADRs, Changelog — alles durchsuchbar via SQL. ' ||
 'generate_system_report() generiert eine vollständige README als JSON on-the-fly.',
 'Pro: Immer aktuell, durchsuchbar, verknüpfbar mit Fehlern. Contra: Braucht DB-Zugang.',
 '[{"option":"README.md","pros":["Vertraut","Git-freundlich"],"cons":["Veraltet schnell","Nicht durchsuchbar","Kein Error-Matching"]},
   {"option":"Wiki","pros":["Hyperlinks"],"cons":["Externer Service","Nicht in DB"]},
   {"option":"Confluence","pros":["Reichhaltig"],"cons":["Extern","Keine DB-Integration"]}]'::JSONB,
 'human+system'),

('Ghost in the Shell: Hot-Swap KI statt statisches LLM',
 'accepted',
 'DBAI braucht verschiedene KI-Modelle fuer verschiedene Aufgaben. ' ||
 'Ein einzelnes LLM ist nicht fuer alle Rollen optimal.',
 'Hot-Swap System: Jede Rolle (system_admin, operator, analyst, creative, security) hat ein ' ||
 'zugewiesenes Modell. Modelle koennen per SQL-Funktion swap_ghost() im laufenden Betrieb getauscht werden. ' ||
 'Swap-Log ist Append-Only, NOTIFY benachrichtigt den Python-Dispatcher der das Modell laedt/entlaedt.',
 'Pro: Optimale Modelle pro Aufgabe, kein Neustart noetig. Contra: Mehr RAM-Verbrauch, Komplexitaet.',
 '[{"option":"Ein LLM fuer alles","pros":["Einfach","Wenig RAM"],"cons":["Suboptimal fuer Spezialaufgaben"]},
   {"option":"Microservice pro Modell","pros":["Isolation"],"cons":["Netzwerk-Overhead","Externe Services"]}]'::JSONB,
 'human+system'),

('Browser-Desktop statt Terminal-Only',
 'accepted',
 'DBAI war bisher nur per CLI/SQL zugreifbar. Fuer eine OS-Erfahrung braucht es ein visuelles Interface.',
 'React SPA als Window Manager: Boot-Sequenz aus DB, Login via bcrypt+JWT, Draggable Windows, ' ||
 'WebSocket-Bridge fuer Echtzeit-Updates via PostgreSQL LISTEN/NOTIFY. ' ||
 'FastAPI Backend auf Port 8420, Vite Dev-Server auf 5173.',
 'Pro: Echte OS-Erfahrung, Echtzeit-Updates, portable im Browser. Contra: Mehr Abhaengigkeiten (Node.js, React).',
 '[{"option":"Terminal TUI","pros":["Minimalistisch","Kein Browser"],"cons":["Kein Window-Management","Nicht visuell"]},
   {"option":"Electron Desktop App","pros":["Nativ"],"cons":["Schwergewichtig","500MB+ Binary"]},
   {"option":"Vue.js statt React","pros":["Einfacher"],"cons":["Weniger Ecosystem","Weniger Entwickler"]}]'::JSONB,
 'human+system'),

('Hardware Abstraction Layer: Alles ist eine Tabellenzeile',
 'accepted',
 'DBAI braucht direkten Zugriff auf Hardware-Informationen (GPU, CPU, RAM, Disk, Netzwerk). ' ||
 'Klassische OS nutzen /proc, /sys oder WMI — das ist unstrukturiert und schwer abfragbar.',
 'Jedes physische Geraet wird als Zeile in dbai_system.hardware_inventory repraesentiert. ' ||
 'Spezialtabellen fuer GPU (VRAM-Map), CPU (pro Kern), Storage (SMART), Fan, Power, Network. ' ||
 'Python-Daemons (hardware_scanner.py, gpu_manager.py) bridgen physische Hardware zu DB-Tabellen.',
 'Pro: SQL-abfragbar, RLS-geschuetzt, historisierbar, NOTIFY-faehig. Contra: Latenz gegenueber direktem /proc-Zugriff.',
 '[{"option":"/proc direkt lesen","pros":["Schnell","Kein DB-Overhead"],"cons":["Unstrukturiert","Kein RLS","Nicht durchsuchbar"]},
   {"option":"Prometheus/Grafana","pros":["Etabliert","Dashboards"],"cons":["Externer Service","Nicht in DB integriert"]},
   {"option":"Custom Kernel Module","pros":["Maximal schnell"],"cons":["Komplex","Kernel-abhaengig","Instabil"]}]'::JSONB,
 'human+system'),

('Neural Bridge: GPU als First-Class Citizen',
 'accepted',
 'Ghost-Modelle brauchen GPU-Offloading fuer Performance. Bisher war GPU-Nutzung nicht in der DB abgebildet.',
 'Boot-Config bestimmt GPU-Modus (auto/force_gpu/cpu_only/multi_gpu). ' ||
 'Treiber-Registry paart Python-Scanner mit SQL-Views. System-Capabilities werden automatisch erkannt. ' ||
 'ghost_benchmarks speichert Token/s pro Modell+GPU-Kombination. ' ||
 'auto_swap_on_gpu_change() Trigger migriert Ghosts wenn GPUs ausfallen.',
 'Pro: GPU-aware Scheduling, automatische Migration, Benchmark-basierte Optimierung. Contra: Komplexitaet, pynvml-Abhaengigkeit.',
 '[{"option":"Statische GPU-Config","pros":["Einfach"],"cons":["Kein Hot-Plug","Kein Auto-Swap"]},
   {"option":"NVIDIA MPS","pros":["Multi-Process GPU"],"cons":["NVIDIA-only","Kein DB-Tracking"]},
   {"option":"Kubernetes GPU Plugin","pros":["Container-native"],"cons":["Overkill fuer Single-Node","Extern"]}]'::JSONB,
 'human+system'),

('OpenClaw Bridge: The Database is the Ghost',
 'accepted',
 'OpenClaw-Nutzer lieben KI-Interaktivitaet, hassen aber Instabilitaet. ' ||
 'JSON-Dateien werden korrupt bei Crashes. Es fehlt transaktionale Sicherheit.',
 'TabulaOS (DBAI) als "Upgrade fuer Erwachsene": Jeder Ghost lebt in einer Tabellenzeile, ' ||
 'nicht in einer JSON-Datei. OpenClaw-Importer migriert Memories (JSON→pgvector, 100x schneller), ' ||
 'Skills (JS/TS→SQL-Aktionen), Config (Personas→Ghost-Parameter). ' ||
 'Telegram-Bridge schreibt direkt in die DB. App-Mode: Jede App ist ein Datenstrom statt Pixel.',
 'Pro: Crash-sichere Ghosts, 100x schnellere Suche, MVCC, RLS. Contra: PostgreSQL-Abhaengigkeit, Lernkurve.',
 '[{"option":"OpenClaw beibehalten","pros":["Bekannt","Einfach"],"cons":["JSON-Korruption","Kein MVCC","Kein RLS","Keine Audit-Trails"]},
   {"option":"SillyTavern","pros":["Web-UI","Plugin-System"],"cons":["Gleiche JSON-Probleme","Keine DB"]},
   {"option":"Eigener LLM-Server","pros":["Volle Kontrolle"],"cons":["Kein Memory-System","Kein Window-Manager"]}]'::JSONB,
 'human+system'),

('Ghost Autonomy: Safety-First Scheduling',
 'accepted',
 'Die KI soll vom Chatbot zum zentralen Scheduler aufsteigen. Aber: unkontrollierte Autonomie ist gefaehrlich. ' ||
 'Root-Kommandos, Dateiloeschungen, Netzwerkzugriffe — alles muss abgesichert sein.',
 'proposed_actions-Tabelle: Jede kritische Aktion wird zuerst als Vorschlag gespeichert. ' ||
 'Waechter-Ghost oder Mensch muss genehmigen. Aktion wird erst nach approval ausgefuehrt. ' ||
 'ghost_context injiziert aktuelle Hardware/Logs/Praeferenzen automatisch in den LLM-Prompt. ' ||
 'ghost_thought_log macht KI-Denken transparent. expire_pending_actions() raumt alte Vorschlaege auf.',
 'Pro: Sichere Autonomie, transparentes Denken, Feedback-Loop. ' ||
 'Contra: Latenz durch Genehmigung, UX-Komplexitaet.',
 '[{"option":"Keine Safety-Tabelle","pros":["Schneller","Einfacher"],"cons":["Unkontrolliert","Gefaehrlich","Kein Audit"]},
   {"option":"Nur Logging","pros":["Einfach"],"cons":["Keine Praevention","Nur Post-Mortem"]},
   {"option":"Volle Sandbox (Container)","pros":["Maximal sicher"],"cons":["Zu langsam","Kein HW-Zugriff"]}]'::JSONB,
 'human+system'),

('App Ecosystem: Dont Rebuild — Remote-Control',
 'accepted',
 'Die KI braucht Zugriff auf Browser, Email, Apps. Aber: eigenen Browser/Mail-Client bauen ist Wahnsinn.',
 'Existierende Programme fernsteuern statt neu bauen. Browser via Playwright (Headless Chromium), ' ||
 'E-Mail via IMAP/SMTP, Apps via Paketmanager. Jede App wird ein Datenstrom in einer Tabelle. ' ||
 'Die KI sieht Text und Struktur, nicht Pixel. OAuth fuer Google/GitHub, workspace_sync fuer Dateien. ' ||
 'command_history trackt Natural Language → SQL → Python Transformation.',
 'Pro: Sofort funktionsfaehig, keine UI-Entwicklung, alle Apps nutzbar. ' ||
 'Contra: Abhaengigkeit von externen Tools, Playwright muss installiert sein.',
 '[{"option":"Eigener Browser","pros":["Volle Kontrolle"],"cons":["10 Jahre Entwicklung","Sinnlos"]},
   {"option":"Nur CLI","pros":["Einfach"],"cons":["Kein Web","Kein Email","Kein OAuth"]},
   {"option":"Electron-Wrapper","pros":["Web-UI"],"cons":["RAM-Verschwendung","Kein Headless"]}]'::JSONB,
 'human+system'),

('System Memory: KI-Gehirn in der Datenbank',
 'accepted',
 'Zwischen KI-Sessions geht Kontext verloren. Architektur, Konventionen, Schema-Map, Design-Patterns, ' ||
 'Workflows — alles muss bei jeder Session neu erklaert werden. Das ist ineffizient und fehleranfaellig.',
 'system_memory Tabelle: Strukturiertes Langzeitgedaechtnis mit Kategorien (architecture, convention, ' ||
 'schema_map, design_pattern, relationship, workflow, inventory, operational, identity, roadmap). ' ||
 'agent_sessions: Jede Arbeitssitzung wird dokumentiert (was wurde getan, welche Dateien, Entscheidungen). ' ||
 'get_agent_context(): Funktion die den kompletten Kontext als Text zurueckgibt — neue Session sofort arbeitsfaehig. ' ||
 'Seed-Datei 25 laedt ~35 Wissenseintraege und 7 Session-Dokumentationen.',
 'Pro: Kein Kontextverlust, sofortige Arbeitsfaehigkeit, durchsuchbar. ' ||
 'Contra: Muss aktuell gehalten werden, wächst mit jeder Session.',
 '[{"option":"Markdown-Dateien","pros":["Einfach","Lesbar"],"cons":["Nicht durchsuchbar","Nicht strukturiert","Kein UPSERT"]},
   {"option":"JSON-Dateien","pros":["Strukturiert"],"cons":["Kein SQL","Kein RLS","Keine Relationen"]},
   {"option":"Kein Gedaechtnis","pros":["Kein Aufwand"],"cons":["Kontextverlust","Ineffizient","Fehleranfaellig"]}]'::JSONB,
 'human+system')
ON CONFLICT DO NOTHING;

-- =============================================================================
-- 3. ERROR PATTERNS — Bekannte Fehler und ihre Lösungen
-- =============================================================================

INSERT INTO dbai_knowledge.error_patterns
    (name, title, error_regex, error_source, severity, category,
     affected_component, description, root_cause, solution_short, solution_detail,
     auto_fix_shell, can_auto_fix, tags, occurrence_count, first_occurred) VALUES

-- Fehler 1: Der C-Compile-Fehler den wir tatsächlich hatten
('posix_c_source_missing',
 'CLOCK_MONOTONIC undeclared — fehlende _POSIX_C_SOURCE Definition',
 'CLOCK_MONOTONIC.*undeclared|_POSIX_C_SOURCE|clock_gettime.*implicit',
 'compile', 'high', 'compatibility',
 'bridge/c_bindings/hw_interrupts.c',
 'Der C-Compiler findet CLOCK_MONOTONIC nicht, weil _POSIX_C_SOURCE nicht definiert ist.',
 'Bei -std=c11 wird POSIX nicht automatisch aktiviert. CLOCK_MONOTONIC und clock_gettime() ' ||
 'brauchen _POSIX_C_SOURCE >= 199309L.',
 'Am Anfang der .c Datei einfügen: #define _POSIX_C_SOURCE 199309L',
 'Die Zeile "#define _POSIX_C_SOURCE 199309L" muss VOR allen #include Anweisungen stehen. ' ||
 'Alternativ: Compiler-Flag -D_POSIX_C_SOURCE=199309L im Makefile. ' ||
 'ACHTUNG: Nicht _GNU_SOURCE verwenden, das ist zu breit.',
 'sed -i ''1i #define _POSIX_C_SOURCE 199309L'' bridge/c_bindings/hw_interrupts.c && cd bridge/c_bindings && make clean && make',
 TRUE,
 ARRAY['c', 'compile', 'posix', 'clock'],
 1, '2026-03-15'),

-- Fehler 2: Der Test-Fehler den wir hatten
('forbidden_file_path_in_sql',
 'Verbotener Dateipfad in SQL-Schema gefunden',
 '/home/[a-z]+/|/root/|/tmp/.*\.txt|manual.*file.*path',
 'python', 'medium', 'logic_error',
 'tests/test_core.py',
 'Ein SQL-Schema enthält einen manuellen Dateipfad (absolute Pfade), was gegen die No-Go-Regeln verstößt.',
 'Kommentare oder Beispiele in SQL enthalten versehentlich reale Pfade.',
 'Dateipfade aus SQL-Kommentaren entfernen und durch Beschreibungen ersetzen',
 'Durchsuche alle SQL-Dateien: grep -rn "/home/" schema/ ' ||
 'Ersetze gefundene Pfade durch allgemeine Beschreibungen (z.B. "Niemals manuelle Dateipfade"). ' ||
 'Test erneut ausführen: python3 -m unittest tests.test_core -v',
 NULL, FALSE,
 ARRAY['test', 'nogo', 'file_path', 'sql'],
 1, '2026-03-15'),

-- Fehler 3: PostgreSQL nicht erreichbar
('postgresql_not_running',
 'PostgreSQL Server nicht erreichbar',
 'connection refused|could not connect|pg_isready.*failed|FATAL.*no pg_hba',
 'postgresql', 'critical', 'network',
 'scripts/bootstrap.sh',
 'PostgreSQL-Server antwortet nicht auf Verbindungsversuche.',
 'Server nicht gestartet, falscher Port, pg_hba.conf blockiert, oder Socket-Datei fehlt.',
 'systemctl start postgresql && pg_isready -h 127.0.0.1 -p 5432',
 '1) Prüfen: systemctl status postgresql. ' ||
 '2) Port prüfen: ss -tlnp | grep 5432. ' ||
 '3) pg_hba.conf prüfen: cat /etc/postgresql/*/main/pg_hba.conf. ' ||
 '4) Logs: journalctl -u postgresql -n 50.',
 'sudo systemctl start postgresql',
 TRUE,
 ARRAY['postgresql', 'connection', 'bootstrap'],
 0, NULL),

-- Fehler 4: pgvector Extension fehlt
('pgvector_missing',
 'Extension "vector" nicht verfügbar',
 'extension "vector" is not available|could not open extension.*vector|CREATE EXTENSION.*vector.*ERROR',
 'sql', 'high', 'missing_dependency',
 'schema/00-extensions.sql',
 'pgvector ist nicht installiert, aber wird für KI-Vektoren benötigt.',
 'pgvector muss als PostgreSQL-Extension kompiliert und installiert werden.',
 'pgvector aus Source bauen: cd /tmp && git clone https://github.com/pgvector/pgvector && cd pgvector && make && sudo make install',
 'Schritt-für-Schritt: ' ||
 '1) apt install postgresql-server-dev-16. ' ||
 '2) git clone https://github.com/pgvector/pgvector.git /tmp/pgvector. ' ||
 '3) cd /tmp/pgvector && make && sudo make install. ' ||
 '4) psql -c "CREATE EXTENSION vector;" dbai. ' ||
 '5) Verifizieren: psql -c "SELECT extversion FROM pg_extension WHERE extname=''vector'';" dbai.',
 'cd /tmp && git clone --branch v0.8.0 https://github.com/pgvector/pgvector.git && cd pgvector && make && sudo make install',
 TRUE,
 ARRAY['pgvector', 'extension', 'install'],
 0, NULL),

-- Fehler 5: Python-Modul fehlt
('python_import_error',
 'Python ImportError — Modul nicht installiert',
 'ModuleNotFoundError|ImportError.*No module named|cannot import name',
 'python', 'medium', 'missing_dependency',
 'bridge/system_bridge.py',
 'Ein Python-Modul konnte nicht importiert werden.',
 'Das Modul ist nicht im aktiven venv installiert.',
 'source .venv/bin/activate && pip install -r requirements.txt',
 'Prüfe: 1) Ist venv aktiv? which python3 sollte auf .venv/bin/python3 zeigen. ' ||
 '2) pip list | grep <modul>. 3) pip install -r requirements.txt.',
 'cd /home/worker/kubernetic/DBAI && source .venv/bin/activate && pip install -r requirements.txt',
 TRUE,
 ARRAY['python', 'import', 'pip', 'venv'],
 0, NULL),

-- Fehler 6: Speicherplatz voll
('disk_space_exhausted',
 'Kein freier Speicherplatz — Disk Full',
 'No space left on device|disk.*full|ENOSPC|could not write.*no space',
 'system', 'critical', 'resource_exhaustion',
 NULL,
 'Festplatte ist voll, keine Schreiboperationen mehr möglich.',
 'WAL-Dateien, Backups oder Metriken belegen zu viel Platz. Vacuum nicht ausgeführt.',
 'VACUUM FULL auf große Tabellen + alte Backups löschen',
 '1) df -h → welche Partition ist voll? ' ||
 '2) du -sh /var/lib/postgresql/*/main/pg_wal/ → WAL-Größe prüfen. ' ||
 '3) VACUUM FULL dbai; ' ||
 '4) pg_archivecleanup für alte WAL-Segmente. ' ||
 '5) Alte Backups löschen: find /var/backups -mtime +30 -delete.',
 NULL, FALSE,
 ARRAY['disk', 'space', 'vacuum', 'wal'],
 0, NULL),

-- Fehler 7: Deadlock
('postgresql_deadlock',
 'Deadlock zwischen Transaktionen erkannt',
 'deadlock detected|ERROR.*deadlock|waiting for.*lock.*timeout',
 'postgresql', 'high', 'concurrency',
 'schema/10-sync-primitives.sql',
 'Zwei oder mehr Transaktionen blockieren sich gegenseitig.',
 'Mehrere Prozesse versuchen gleichzeitig Locks in unterschiedlicher Reihenfolge zu erhalten.',
 'SELECT dbai_core.detect_deadlocks(); und dann Locks in einheitlicher Reihenfolge anfordern',
 '1) SELECT * FROM pg_stat_activity WHERE wait_event_type = ''Lock''; ' ||
 '2) SELECT dbai_core.detect_deadlocks(); ' ||
 '3) Im Notfall: SELECT dbai_core.cleanup_expired_locks(); ' ||
 '4) Langfristig: Lock-Reihenfolge standardisieren (Priority-System).',
 NULL, FALSE,
 ARRAY['deadlock', 'lock', 'concurrency'],
 0, NULL),

-- Fehler 8: LLM-Modell nicht geladen
('llm_model_not_loaded',
 'LLM-Modell nicht geladen — keine Inferenz möglich',
 'Modell.*nicht geladen|model.*not loaded|llama.*failed|GGUF.*not found',
 'llm', 'medium', 'missing_dependency',
 'llm/llm_bridge.py',
 'Das LLM-Modell konnte nicht geladen werden.',
 'GGUF-Datei fehlt, falscher Pfad in Config, oder nicht genug RAM.',
 'GGUF-Modelldatei in config/dbai.toml prüfen und Modell herunterladen',
 '1) Config prüfen: grep model_path config/dbai.toml. ' ||
 '2) Datei existiert? ls -la <pfad>. ' ||
 '3) Genug RAM? free -h (Modell braucht ~Modellgröße × 1.2 RAM). ' ||
 '4) Modell herunterladen: wget <URL> -O models/<name>.gguf.',
 NULL, FALSE,
 ARRAY['llm', 'model', 'gguf', 'llama'],
 0, NULL),

-- Fehler 9: Schema-Migration fehlgeschlagen
('schema_migration_failed',
 'SQL-Schema konnte nicht geladen werden',
 'already exists|ERROR.*CREATE|relation.*does not exist|type.*does not exist',
 'sql', 'high', 'compatibility',
 'scripts/bootstrap.sh',
 'Ein SQL-Schema konnte nicht geladen werden (Objekt existiert bereits oder fehlt).',
 'Schema wurde bereits geladen (exists) oder Abhängigkeit fehlt (does not exist).',
 'Bei "already exists": Ignorieren (Schema bereits vorhanden). Bei "does not exist": Vorige Schemas prüfen.',
 '1) "already exists" → OK, Schema ist schon da. Bootstrap ist idempotent. ' ||
 '2) "does not exist" → Schemas in falscher Reihenfolge geladen? Prüfe: ' ||
 '   SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE ''dbai_%''; ' ||
 '3) Manuelles Nachladen: psql -d dbai -f schema/<fehlendes_schema>.sql.',
 NULL, FALSE,
 ARRAY['schema', 'migration', 'bootstrap', 'sql'],
 0, NULL)
ON CONFLICT DO NOTHING;

-- =============================================================================
-- 4. RUNBOOKS — Schritt-für-Schritt Anleitungen
-- =============================================================================

INSERT INTO dbai_knowledge.runbooks
    (name, title, description, category, estimated_minutes, steps, error_pattern_ids) VALUES

('rb_initial_setup',
 'DBAI Erstinstallation',
 'Komplette Erstinstallation von DBAI auf einem frischen Linux-Server',
 'deployment', 30,
 '[{"step":1,"action":"System-Pakete installieren","type":"shell","command":"sudo apt update && sudo apt install -y postgresql postgresql-server-dev-16 gcc make python3-dev python3-venv"},
   {"step":2,"action":"pgvector installieren","type":"shell","command":"cd /tmp && git clone https://github.com/pgvector/pgvector && cd pgvector && make && sudo make install"},
   {"step":3,"action":"DBAI-Verzeichnis vorbereiten","type":"shell","command":"cd /home/worker/kubernetic/DBAI && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"},
   {"step":4,"action":"C-Bindings kompilieren","type":"shell","command":"cd bridge/c_bindings && make clean && make"},
   {"step":5,"action":"PostgreSQL konfigurieren","type":"manual","command":"Kopiere config/postgresql.conf und config/pg_hba.conf nach /etc/postgresql/16/main/ und starte PostgreSQL neu"},
   {"step":6,"action":"Datenbank bootstrappen","type":"shell","command":"bash scripts/bootstrap.sh"},
   {"step":7,"action":"System starten","type":"shell","command":"source .venv/bin/activate && python3 bridge/system_bridge.py start"},
   {"step":8,"action":"Gesundheitscheck","type":"shell","command":"python3 scripts/health_check.py"}]'::JSONB,
 '{}'),

('rb_compile_error',
 'C-Compile-Fehler beheben',
 'Wenn die C-Bindings nicht kompilieren',
 'error_resolution', 5,
 '[{"step":1,"action":"Fehler identifizieren","type":"shell","command":"cd bridge/c_bindings && make 2>&1"},
   {"step":2,"action":"_POSIX_C_SOURCE prüfen","type":"shell","command":"head -5 hw_interrupts.c | grep POSIX"},
   {"step":3,"action":"Falls fehlend: Definition einfügen","type":"shell","command":"sed -i ''1i #define _POSIX_C_SOURCE 199309L'' hw_interrupts.c"},
   {"step":4,"action":"Neu kompilieren","type":"shell","command":"make clean && make"},
   {"step":5,"action":"Bibliothek testen","type":"shell","command":"python3 -c \"import ctypes; lib = ctypes.CDLL(''./libhw_interrupts.so''); print(''OK:'', lib.get_cpu_count())\""}]'::JSONB,
 (SELECT ARRAY[id] FROM dbai_knowledge.error_patterns WHERE name = 'posix_c_source_missing')),

('rb_db_recovery',
 'Datenbank-Recovery nach Crash',
 'Wiederherstellung der DBAI-Datenbank nach unerwartetem Shutdown',
 'disaster_recovery', 15,
 '[{"step":1,"action":"PostgreSQL-Status prüfen","type":"shell","command":"systemctl status postgresql"},
   {"step":2,"action":"PostgreSQL starten","type":"shell","command":"sudo systemctl start postgresql"},
   {"step":3,"action":"Datenbank-Integrität prüfen","type":"shell","command":"psql -d dbai -c \"SELECT dbai_panic.execute_repair();\""},
   {"step":4,"action":"Panic-Log prüfen","type":"shell","command":"psql -d dbai -c \"SELECT * FROM dbai_panic.panic_log ORDER BY ts DESC LIMIT 10;\""},
   {"step":5,"action":"Zombie-Prozesse aufräumen","type":"sql","command":"UPDATE dbai_core.processes SET state = ''stopped'', stopped_at = NOW() WHERE state IN (''running'', ''zombie'') AND last_heartbeat < NOW() - INTERVAL ''5 minutes'';"},
   {"step":6,"action":"Health-Check ausführen","type":"shell","command":"python3 scripts/health_check.py"},
   {"step":7,"action":"System Bridge neu starten","type":"shell","command":"source .venv/bin/activate && python3 bridge/system_bridge.py start"}]'::JSONB,
 (SELECT ARRAY[id] FROM dbai_knowledge.error_patterns WHERE name = 'postgresql_not_running')),

('rb_disk_full',
 'Speicherplatz freigeben',
 'Notfall-Prozedur wenn die Festplatte voll ist',
 'error_resolution', 10,
 '[{"step":1,"action":"Speicherverbrauch analysieren","type":"shell","command":"df -h && du -sh /var/lib/postgresql/*/main/ 2>/dev/null | sort -rh | head -10"},
   {"step":2,"action":"WAL-Größe prüfen","type":"shell","command":"du -sh /var/lib/postgresql/*/main/pg_wal/ 2>/dev/null"},
   {"step":3,"action":"Alte WAL-Segmente aufräumen","type":"shell","command":"psql -d dbai -c \"SELECT pg_switch_wal();\" && pg_archivecleanup /var/lib/postgresql/16/main/pg_wal/ $(psql -t -c \"SELECT file_name FROM pg_walfile_name(pg_current_wal_lsn());\" dbai)"},
   {"step":4,"action":"VACUUM FULL ausführen","type":"sql","command":"VACUUM FULL dbai_system.cpu; VACUUM FULL dbai_system.memory; VACUUM FULL dbai_system.disk;"},
   {"step":5,"action":"Alte Metriken löschen","type":"sql","command":"SELECT dbai_system.cleanup_old_metrics();"},
   {"step":6,"action":"Alte Backups entfernen","type":"shell","command":"find /var/backups/dbai -mtime +30 -name \"*.sql.gz\" -delete 2>/dev/null; echo \"Alte Backups gelöscht\""},
   {"step":7,"action":"Speicher erneut prüfen","type":"shell","command":"df -h"}]'::JSONB,
 (SELECT ARRAY[id] FROM dbai_knowledge.error_patterns WHERE name = 'disk_space_exhausted')),

('rb_test_failures',
 'Test-Fehler beheben',
 'Wenn Tests fehlschlagen — systematische Fehlersuche',
 'debugging', 10,
 '[{"step":1,"action":"Alle Tests ausführen","type":"shell","command":"cd /home/worker/kubernetic/DBAI && python3 -m unittest tests.test_core -v 2>&1"},
   {"step":2,"action":"Fehlermeldung analysieren","type":"manual","command":"Die FAIL/ERROR-Zeilen genau lesen — der Testname verrät was geprüft wird"},
   {"step":3,"action":"Betroffene Datei identifizieren","type":"manual","command":"test_no_manual_file_paths → schema/*.sql durchsuchen mit grep"},
   {"step":4,"action":"Fix anwenden","type":"manual","command":"Verbotene Inhalte entfernen/ersetzen"},
   {"step":5,"action":"Tests erneut ausführen","type":"shell","command":"python3 -m unittest tests.test_core -v"},
   {"step":6,"action":"Fehler dokumentieren","type":"sql","command":"INSERT INTO dbai_knowledge.error_log (error_source, error_message, module_path, is_resolved, resolved_by) VALUES (''python'', ''<Fehlermeldung>'', ''tests/test_core.py'', TRUE, ''manual'');"}]'::JSONB,
 (SELECT ARRAY[id] FROM dbai_knowledge.error_patterns WHERE name = 'forbidden_file_path_in_sql'))
ON CONFLICT DO NOTHING;

-- =============================================================================
-- 5. SYSTEM-GLOSSAR — Begriffe die Mensch und KI verstehen müssen
-- =============================================================================

INSERT INTO dbai_knowledge.system_glossary (term, definition, context, examples, related_terms) VALUES

('DBAI', 'Tabellenbasiertes KI-Betriebssystem auf PostgreSQL. Jeder Systemzustand ist eine Tabellenzeile.',
 'Gesamtprojekt', ARRAY['SELECT * FROM dbai_core.config;', 'python3 bridge/system_bridge.py start'],
 ARRAY['System Bridge', 'PostgreSQL', 'pgvector']),

('System Bridge', 'Der Zündschlüssel — Python-Programm das DBAI bootet. Startet Hardware-Monitor, LLM, Vacuum.',
 'Boot-Prozess', ARRAY['bridge/system_bridge.py start', 'bridge/system_bridge.py status'],
 ARRAY['Boot', 'Hardware Monitor', 'Heartbeat']),

('Append-Only', 'Tabellen in die nur eingefügt, aber nie gelöscht oder geändert werden kann. Schutz durch Trigger.',
 'Journal, Events, Error-Log', ARRAY['dbai_journal.change_log', 'dbai_event.events', 'dbai_knowledge.error_log'],
 ARRAY['Journal', 'protect_journal', 'protect_events']),

('PITR', 'Point-in-Time Recovery — Zeitmaschine für die Datenbank. Kann jeden Zustand wiederherstellen.',
 'Recovery', ARRAY['SELECT dbai_journal.find_nearest_snapshot(NOW() - INTERVAL ''1 hour'');'],
 ARRAY['WAL', 'Snapshot', 'Base-Backup']),

('pgvector', 'PostgreSQL-Extension für Vektoren. Speichert KI-Embeddings als mathematische Punkte im 1536D-Raum.',
 'KI-Erinnerungen', ARRAY['CREATE EXTENSION vector;', 'vector(1536)', 'HNSW Index'],
 ARRAY['Embedding', 'HNSW', 'Cosine Similarity']),

('Row-Level Security', 'Jede Zeile hat Zugriffsregeln. dbai_system darf alles, dbai_llm nur eigene Daten.',
 'Sicherheit', ARRAY['ALTER TABLE ... ENABLE ROW LEVEL SECURITY;', 'CREATE POLICY ...'],
 ARRAY['RLS', 'Policy', 'Rolle']),

('Kernel Panic', 'Notfallzustand wenn kritische Systeme ausfallen. Panic-Schema hat minimale Treiber.',
 'Recovery', ARRAY['SELECT dbai_panic.execute_repair();', 'recovery/panic_recovery.py diagnose'],
 ARRAY['Panic Schema', 'Emergency Drivers', 'Repair Scripts']),

('Advisory Lock', 'PostgreSQL-basierter Lock-Mechanismus für Synchronisation zwischen DBAI-Prozessen.',
 'Concurrency', ARRAY['SELECT dbai_core.acquire_lock(''resource'', 5);', 'SELECT dbai_core.release_lock(''resource'');'],
 ARRAY['Lock Registry', 'Priority', 'Deadlock']),

('Heartbeat', 'Regelmäßiges Signal das zeigt dass ein Prozess noch lebt. Alle 30s in last_heartbeat aktualisiert.',
 'Monitoring', ARRAY['UPDATE dbai_core.processes SET last_heartbeat = NOW() WHERE id = ...;'],
 ARRAY['Process', 'Zombie', 'Watchdog']),

('GGUF', 'Dateiformat für quantisierte LLM-Modelle. Von llama.cpp verwendet. Kompakt genug für lokale Inferenz.',
 'LLM', ARRAY['Qwen2.5-7B-Instruct.Q4_K_M.gguf'],
 ARRAY['llama.cpp', 'Quantisierung', 'LLM Bridge']),

('No-Go', 'Verbotene Praktiken in DBAI: keine Dateipfade, keine ext. APIs, keine Root-Passwörter, keine Rohdaten.',
 'Architektur-Regeln', ARRAY['Absolute Dateipfade → VERBOTEN', 'api.openai.com → VERBOTEN'],
 ARRAY['UUID', 'RLS', 'Append-Only']),

('Knowledge Library', 'Die Wissensdatenbank innerhalb DBAI: Dokumentation, Fehler, ADRs, Changelog — alles in Tabellen.',
 'Selbstdokumentation', ARRAY['SELECT dbai_knowledge.generate_system_report();', 'SELECT * FROM dbai_knowledge.vw_module_overview;'],
 ARRAY['Module Registry', 'Error Patterns', 'Runbooks']),

('Error Pattern', 'Bekanntes Fehlermuster mit Regex-Signatur. Wenn ein Fehler auftritt, wird automatisch die Lösung gefunden.',
 'Fehlerbehebung', ARRAY['SELECT * FROM dbai_knowledge.log_error(''compile'', ''CLOCK_MONOTONIC undeclared'');'],
 ARRAY['Runbook', 'Auto-Fix', 'Error Log']),

('Runbook', 'Schritt-für-Schritt Anleitung zur Fehlerbehebung oder Wartung. Liegt als JSON-Steps in der DB.',
 'Operations', ARRAY['SELECT steps FROM dbai_knowledge.runbooks WHERE name = ''rb_initial_setup'';'],
 ARRAY['Error Pattern', 'Disaster Recovery', 'Deployment']),

('TabulaOS', 'Markenname fuer DBAI als Endanwender-Produkt. PostgreSQL als OS-Kern mit Ghost-KI, Desktop-UI und Hardware-Abstraktion.',
 'Marketing, Positionierung', ARRAY['http://localhost:8420 → TabulaOS Desktop'],
 ARRAY['DBAI', 'Ghost', 'Desktop UI']),

('OpenClaw', 'Open-Source KI-Chat-System basierend auf Node.js/Telegram. Speichert Daten als JSON-Dateien. ' ||
 'Bekannt fuer Instabilitaet und Datenverlust bei Crashes.',
 'Konkurrenz, Migration', ARRAY['OpenClaw Skills', 'OpenClaw Memory Files'],
 ARRAY['TabulaOS', 'SillyTavern', 'Oobabooga']),

('Telegram Bridge', 'Verbindung zwischen Telegram-Bot und DBAI task_queue. Nachrichten werden direkt in die DB geschrieben, ' ||
 'der Ghost verarbeitet sie, Antworten gehen ueber NOTIFY zurueck.',
 'Kommunikation', ARRAY['SELECT dbai_event.process_telegram_message(...);'],
 ARRAY['Task Queue', 'Ghost', 'NOTIFY']),

('App-Mode', 'Konzept in dem jede Anwendung ein Datenstrom ist statt Pixel auf dem Bildschirm. ' ||
 'Die KI "sieht" die App als strukturierte Daten in einer Tabelle.',
 'Desktop-Architektur', ARRAY['SELECT * FROM dbai_ui.app_streams;'],
 ARRAY['Desktop UI', 'Ghost', 'Datenstrom']),

('Neural Bridge', 'Boot-Konfiguration und Treiber-System das Hardware mit der DB verbindet. ' ||
 'Bestimmt welcher Ghost die Kontrolle uebernimmt, GPU-Modus, Kiosk-Mode.',
 'Boot, Hardware', ARRAY['SELECT dbai_core.get_boot_config();'],
 ARRAY['Boot Config', 'Driver Registry', 'HAL']),

('Hardware Abstraction Layer', 'HAL — Jedes physische Geraet ist eine Tabellenzeile. ' ||
 'GPU-VRAM-Tracking, Fan-Control, Power-Profile, Hotplug-Events — alles via SQL abfragbar.',
 'Hardware', ARRAY['SELECT * FROM dbai_system.vw_gpu_overview;', 'SELECT * FROM dbai_system.vw_hardware_summary;'],
 ARRAY['Neural Bridge', 'GPU Manager', 'Hardware Scanner']),

('Synaptic Memory', 'KI-Gedaechtnis basierend auf pgvector mit HNSW-Index. 100x schneller als JSON-File-Scan. ' ||
 'Semantische Suche in 1536-dimensionalem Vektorraum.',
 'KI, Erinnerungen', ARRAY['SELECT dbai_vector.search_memories(embedding, 10);'],
 ARRAY['pgvector', 'Embedding', 'Ghost'])
ON CONFLICT DO NOTHING;

-- =============================================================================
-- 6. CHANGELOG — Alles was wir bisher gebaut haben
-- =============================================================================

INSERT INTO dbai_knowledge.changelog
    (version, change_type, title, description, affected_files, author) VALUES

('0.1.0', 'feature', 'DBAI Grundstruktur erstellt',
 'Verzeichnisstruktur angelegt: config/, schema/, bridge/, recovery/, llm/, scripts/, tests/. ' ||
 'README.md und requirements.txt erstellt.',
 ARRAY['README.md', 'requirements.txt'],
 'system'),

('0.1.0', 'feature', 'Konfigurationsdateien erstellt',
 'dbai.toml (alle Subsysteme), postgresql.conf (optimiert für DBAI), pg_hba.conf (nur localhost).',
 ARRAY['config/dbai.toml', 'config/postgresql.conf', 'config/pg_hba.conf'],
 'system'),

('0.1.0', 'schema', 'Core-Schemas 00-04 erstellt',
 'Extensions+Rollen (00), Core-Tabellen (01), System-Hardware (02), Events Append-Only (03), pgvector (04).',
 ARRAY['schema/00-extensions.sql', 'schema/01-core-tables.sql', 'schema/02-system-tables.sql',
       'schema/03-event-tables.sql', 'schema/04-vector-tables.sql'],
 'system'),

('0.1.0', 'schema', 'Recovery+Security Schemas 05-07 erstellt',
 'WAL-Journal Append-Only (05), Kernel-Panic mit Repair-Scripts (06), RLS auf allen Tabellen (07).',
 ARRAY['schema/05-wal-journal.sql', 'schema/06-panic-schema.sql', 'schema/07-row-level-security.sql'],
 'system'),

('0.1.0', 'schema', 'LLM+Vacuum+Sync Schemas 08-10 erstellt',
 'LLM-Integration mit prompt/embed/remember/recall (08), Vacuum-Scheduling (09), Advisory Locks mit Priority (10).',
 ARRAY['schema/08-llm-integration.sql', 'schema/09-vacuum-schedule.sql', 'schema/10-sync-primitives.sql'],
 'system'),

('0.1.0', 'feature', 'System Bridge implementiert',
 'Python System Bridge mit 7-Schritt-Boot, Heartbeat-Loop, PITR-Integration. CLI: start/status/stop.',
 ARRAY['bridge/system_bridge.py'],
 'system'),

('0.1.0', 'feature', 'Hardware Monitor und Event Dispatcher',
 'psutil-basierter Hardware-Monitor, Event-Dispatcher für /dev/input.',
 ARRAY['bridge/hardware_monitor.py', 'bridge/event_dispatcher.py'],
 'system'),

('0.1.0', 'feature', 'C-Bindings für Hardware-Zugriff',
 'hw_interrupts.c mit Memory/CPU/Disk/Interrupt-Funktionen. Kompiliert als libhw_interrupts.so.',
 ARRAY['bridge/c_bindings/hw_interrupts.c', 'bridge/c_bindings/hw_interrupts.h',
       'bridge/c_bindings/Makefile'],
 'system'),

('0.1.0', 'fix', 'C-Compile-Fehler behoben: _POSIX_C_SOURCE fehlte',
 'CLOCK_MONOTONIC undeclared weil _POSIX_C_SOURCE 199309L nicht definiert war. ' ||
 'Fix: #define am Anfang der .c Datei. Fehler-Pattern in error_patterns dokumentiert.',
 ARRAY['bridge/c_bindings/hw_interrupts.c'],
 'system'),

('0.1.0', 'feature', 'Recovery-System implementiert',
 'PITR Manager (Snapshots, Base-Backup), Mirror Sync (Streaming-Replikation, rsync), ' ||
 'Panic Recovery (9 Handler, Volldiagnose, CLI).',
 ARRAY['recovery/pitr_manager.py', 'recovery/mirror_sync.py', 'recovery/panic_recovery.py'],
 'system'),

('0.1.0', 'feature', 'LLM Bridge implementiert',
 'llama.cpp Integration via llama-cpp-python. Modell im RAM, Task-Queue-Verarbeitung.',
 ARRAY['llm/llm_bridge.py'],
 'system'),

('0.1.0', 'feature', 'Install/Bootstrap/Backup Scripts',
 'install.sh (PostgreSQL, pgvector, venv), bootstrap.sh (DB+Schemas), backup.sh (pg_dump+Journal).',
 ARRAY['scripts/install.sh', 'scripts/bootstrap.sh', 'scripts/backup.sh', 'scripts/health_check.py'],
 'system'),

('0.1.0', 'feature', 'Tests: 18 Unit-Tests',
 '5 Testklassen: Schema, Config, Bridge, C-Bindings, Verzeichnisstruktur. Alle 18 bestanden.',
 ARRAY['tests/test_core.py'],
 'system'),

('0.1.0', 'fix', 'Test-Fix: Verbotenen Dateipfad aus SQL-Kommentar entfernt',
 'test_no_manual_file_paths fand verbotenen absoluten Pfad in Kommentar von 01-core-tables.sql. ' ||
 'Fix: Kommentar geändert zu "Niemals manuelle Dateipfade benutzen".',
 ARRAY['schema/01-core-tables.sql'],
 'system'),

('0.2.0', 'feature', 'Knowledge Library: Selbstdokumentierende Wissensdatenbank',
 'Neues Schema dbai_knowledge: module_registry (alle Dateien dokumentiert), ' ||
 'module_dependencies, changelog (Append-Only), architecture_decisions, ' ||
 'system_glossary, known_issues, build_log. Views und Analyse-Funktionen.',
 ARRAY['schema/11-knowledge-library.sql'],
 'system'),

('0.2.0', 'feature', 'Error Patterns & Runbooks',
 'Automatische Fehlererkennung via Regex-Patterns, Runbooks für Schritt-für-Schritt-Behebung, ' ||
 'Append-Only Error-Log, Resolution-Tracking. log_error() matcht und liefert Lösung.',
 ARRAY['schema/12-error-patterns.sql'],
 'system'),

('0.2.0', 'feature', 'Seed Data: Komplettes Systemwissen vorgeladen',
 'Alle 38 Module registriert, 6 ADRs, 9 Error-Patterns, 5 Runbooks, 14 Glossar-Einträge, ' ||
 '16 Changelog-Einträge. Das gesamte bisherige Wissen liegt jetzt IN der DB.',
 ARRAY['schema/13-seed-data.sql'],
 'system'),

('0.2.0', 'feature', 'Self-Healing & Observability',
 'Health-Checks, Alert-Rules, Auto-Heal, Telemetrie. ' ||
 'self_heal() orchestriert automatische Problemerkennung und Reparatur.',
 ARRAY['schema/14-self-healing.sql'],
 'system'),

('0.3.0', 'feature', 'Ghost in the Shell: Hot-Swap KI-System',
 'Neues Schema dbai_ghost: ghost_models, ghost_assignments (Rolle zu Modell), ' ||
 'ghost_swap_log (Append-Only), ghost_conversations, ghost_capabilities, ghost_compatibility. ' ||
 'swap_ghost() tauscht Modelle atomar, ask_ghost() routet an aktiven Ghost.',
 ARRAY['schema/15-ghost-system.sql'],
 'system'),

('0.3.0', 'feature', 'Desktop UI: Browser-basierter Window Manager',
 'Neues Schema dbai_desktop: users + bcrypt, sessions + JWT, themes, applications, ' ||
 'draggable windows, notifications, boot_sequence. Vollstaendige OS-Erfahrung im Browser.',
 ARRAY['schema/16-desktop-ui.sql'],
 'system'),

('0.3.0', 'feature', 'Ghost+Desktop Seed-Daten',
 '5 KI-Modelle, 3 Themes (Cyberpunk/Light/Matrix), 7 Desktop-Apps, 15 Boot-Steps, Admin-User.',
 ARRAY['schema/17-ghost-desktop-seed.sql'],
 'system'),

('0.3.0', 'feature', 'FastAPI Web-Server mit WebSocket-Bridge',
 'REST API fuer alle Desktop-Operationen + WebSocket-Bridge fuer PG NOTIFY Events. ' ||
 'JWT-Auth, Boot-Sequenz, Window-Management, Ghost-Swap, SQL-Console.',
 ARRAY['web/server.py'],
 'system'),

('0.3.0', 'feature', 'Ghost Dispatcher: KI Hot-Swap Manager',
 'Python-Daemon der PG NOTIFY hoert und GGUF-Modelle via llama-cpp-python laedt/entlaedt. ' ||
 'Thread-basiertes Laden, VRAM-Tracking, Task-Queue-Verarbeitung.',
 ARRAY['web/ghost_dispatcher.py'],
 'system'),

('0.3.0', 'feature', 'React Frontend: Cyberpunk Desktop',
 'React 18 SPA mit Vite: BootScreen, LoginScreen, Desktop mit Taskbar, ' ||
 'Draggable Windows, 7 App-Komponenten (SystemMonitor, GhostManager, GhostChat, ' ||
 'KnowledgeBase, EventViewer, SQLConsole, HealthDashboard). Neon-Cyan Cyberpunk Theme.',
 ARRAY['frontend/package.json', 'frontend/src/App.jsx', 'frontend/src/styles/global.css'],
 'system'),

-- v0.4.0: Hardware Abstraction Layer + Neural Bridge
('0.4.0', 'schema', 'Hardware Abstraction Layer: 10 Tabellen für physische Hardware',
 '10 Tabellen in dbai_system: hardware_inventory, gpu_devices, gpu_vram_map, cpu_cores, ' ||
 'memory_map, storage_health, fan_control, power_profiles, network_connections, hotplug_events. ' ||
 'Funktionen: check_gpu_available() (Single+Multi-GPU), allocate_vram(), release_vram(), activate_power_profile(). ' ||
 'Views: vw_gpu_overview, vw_hardware_summary, vw_active_power_profile. RLS auf allen 10 Tabellen.',
 ARRAY['schema/18-hardware-abstraction.sql'],
 'system'),

('0.4.0', 'schema', 'Neural Bridge: Boot-Config, Treiber, Capabilities, Benchmarks',
 '5 Tabellen: boot_config (gpu_mode, kiosk, daemon-flags), neural_bridge_config, ' ||
 'driver_registry (Python+SQL Paare), system_capabilities, ghost_benchmarks. ' ||
 'get_boot_config() liefert komplettes Boot-JSON. auto_swap_on_gpu_change() Trigger.',
 ARRAY['schema/19-neural-bridge.sql'],
 'system'),

('0.4.0', 'schema', 'HAL+Neural Bridge Seed-Daten',
 '4 Power-Profile (sparmodus/balanced/cyberbrain/silent), 4 Boot-Configs, ' ||
 '22 Neural-Bridge-Config-Eintraege, 7 Treiber, 10 System-Capabilities.',
 ARRAY['schema/20-hw-seed-data.sql'],
 'system'),

('0.4.0', 'feature', 'Hardware Scanner: CPU/RAM/Disk/Netz-Daemon',
 'Python-Daemon der via psutil und /proc alle Hardware scannt und in hardware_inventory schreibt. ' ||
 'CPU-Feature-Erkennung (AVX2, AVX-512), SMART-Risiko-Score, Memory-Map mit Prozesstypen. ' ||
 'CLI: --daemon fuer periodisches Scanning, --json fuer Ausgabe.',
 ARRAY['bridge/hardware_scanner.py'],
 'system'),

('0.4.0', 'feature', 'GPU Manager: VRAM-Tracking und Multi-GPU',
 'pynvml-basierter GPU-Daemon: GPU-Discovery, VRAM-Allokation pro Ghost, Thermal Protection ' ||
 '(Warning 80C, Critical 90C mit Auto-Migration), Multi-GPU Layer-Splitting, Power-Limit-Control. ' ||
 'NOTIFY-Listener fuer power_profile_change, fan_control, gpu_overheat.',
 ARRAY['bridge/gpu_manager.py'],
 'system'),

('0.4.0', 'feature', 'Ghost Dispatcher GPU-Awareness',
 'ghost_dispatcher.py erweitert um GPU-Integration: VRAM-Check vor Model-Load, ' ||
 'automatische GPU-Layer-Berechnung, VRAM-Allokation/Release, Quick-Benchmarks, ' ||
 'Thermal-Migration bei GPU-Overheat, Power-Profile-Reaktion.',
 ARRAY['web/ghost_dispatcher.py'],
 'system'),

-- v0.5.0: OpenClaw Bridge + TabulaOS
('0.5.0', 'schema', 'OpenClaw Bridge: Migration + Telegram + App-Mode',
 '6 Tabellen: openclaw_skills, openclaw_memories, migration_jobs, telegram_bridge, ' ||
 'app_streams, openclaw_compat_map. 4 Funktionen: import_openclaw_memory(), ' ||
 'register_openclaw_skill(), process_telegram_message(), openclaw_migration_report(). ' ||
 '4 Views, RLS auf allen Tabellen. 10 Feature-Vergleiche OpenClaw vs TabulaOS.',
 ARRAY['schema/21-openclaw-bridge.sql'],
 'system'),

('0.5.0', 'feature', 'OpenClaw Importer: Scanner + Migrator + Telegram Bridge',
 'Python-Tool das OpenClaw/SillyTavern/Oobabooga/KoboldAI-Installationen erkennt und migriert. ' ||
 'Memories (JSON→pgvector), Skills (JS/TS→SQL), Config (Personas). ' ||
 'TelegramBridge: Bot-Nachrichten direkt in die DB, Antworten via NOTIFY.',
 ARRAY['bridge/openclaw_importer.py'],
 'system'),

('0.5.0', 'feature', 'TabulaOS Strategie: The Database is the Ghost',
 'Positionierung als "Upgrade fuer Erwachsene" gegenueber OpenClaw. ' ||
 'Verkaufsargument: Ghost stirbt nicht bei Crash, lebt in der Tabelle weiter. ' ||
 '100x schnellere Memory-Suche, atomarer Model-Swap, Append-Only Audit-Trail.',
 ARRAY['schema/21-openclaw-bridge.sql', 'bridge/openclaw_importer.py'],
 'human+system'),

-- v0.6.0: Ghost Autonomy + App Ecosystem
('0.6.0', 'schema', 'Ghost Autonomy: Safety-First Scheduling + App Ecosystem',
 '8+8 Tabellen: proposed_actions, ghost_context, ghost_thought_log, process_importance, ' ||
 'energy_consumption, ghost_files, ghost_feedback, api_keys, software_catalog, browser_sessions, ' ||
 'email_accounts, inbox, outbox, oauth_connections, workspace_sync, command_history. ' ||
 '10 Funktionen, 10 Views, RLS auf allen 16 Tabellen.',
 ARRAY['schema/22-ghost-autonomy.sql', 'schema/23-app-ecosystem.sql'],
 'system'),

('0.6.0', 'feature', 'Ghost Autonomy Daemon: KI als zentraler Scheduler',
 'Python-Daemon der den Ghost zum Scheduler macht. Kontext-Injektion (Hardware/Logs in LLM-Prompt), ' ||
 'Energie-Monitoring (CPU/RAM/GPU pro Prozess), Prozessklassifikation mit KI-Bewertung, ' ||
 'autonome Dateiorganisation, Safety via proposed_actions. LISTEN auf Events.',
 ARRAY['bridge/ghost_autonomy.py'],
 'system'),

('0.6.0', 'feature', 'App Manager: Browser + Email + OAuth + Software-Katalog',
 'Python-Tool fuer App-Ecosystem. SoftwareCatalog (APT/pip/GitHub Scanner), ' ||
 'BrowserAutomation (Playwright Headless — KI sieht Text, nicht Pixel), ' ||
 'EmailBridge (IMAP/SMTP → inbox/outbox Tabellen), OAuthManager (Google/GitHub). ' ||
 'AppManagerDaemon hoert auf Events und automatisiert Aktionen.',
 ARRAY['bridge/app_manager.py'],
 'system'),

-- v0.7.0: System Memory
('0.7.0', 'schema', 'System Memory: KI-Langzeitgedaechtnis in der DB',
 'Tabelle system_memory fuer strukturiertes Wissen (Architektur, Konventionen, Patterns, Schema-Map). ' ||
 'Tabelle agent_sessions fuer Session-Dokumentation. get_agent_context() fuer sofortigen Kontext-Abruf.',
 ARRAY['schema/24-system-memory.sql'],
 'system'),

('0.7.0', 'feature', 'System Memory Seed: 35+ Wissenseintraege, 7 Sessions dokumentiert',
 'Vollstaendiges KI-Gehirn als Seed-Daten: Identitaet, Architektur, Schema-Karte (9 Schemas, ~70 Tabellen), ' ||
 'Design-Patterns (NOTIFY, Append-Only, Safety-First, Hot-Swap, Remote-Control), ' ||
 'Konventionen, Beziehungen, Tech-Inventar, Workflows, Operational Knowledge, Roadmap. ' ||
 'Plus dokumentierte Agent-Sessions von v0.1.0 bis v0.7.0.',
 ARRAY['schema/25-system-memory-seed.sql'],
 'system')
ON CONFLICT DO NOTHING;

-- =============================================================================
-- 7. KNOWN ISSUES — Bekannte Probleme und Workarounds
-- =============================================================================

INSERT INTO dbai_knowledge.known_issues
    (title, description, severity, status, affected_files, workaround, resolution, resolution_date, error_pattern_id) VALUES

('C-Compile: _POSIX_C_SOURCE muss definiert sein',
 'Ohne #define _POSIX_C_SOURCE 199309L am Anfang von hw_interrupts.c kompiliert der Code nicht mit -std=c11.',
 'high', 'resolved',
 ARRAY['bridge/c_bindings/hw_interrupts.c'],
 '#define _POSIX_C_SOURCE 199309L als erste Zeile einfügen',
 '#define _POSIX_C_SOURCE 199309L wurde als erste Zeile eingefügt. Kompiliert jetzt fehlerfrei.',
 NOW(),
 (SELECT id FROM dbai_knowledge.error_patterns WHERE name = 'posix_c_source_missing')),

('SQL-Kommentar enthielt verbotenen Dateipfad',
 'In schema/01-core-tables.sql stand ein absoluter Dateipfad als Beispiel im Kommentar, was den No-Go-Test brach.',
 'medium', 'resolved',
 ARRAY['schema/01-core-tables.sql'],
 'Pfad aus Kommentar entfernen',
 'Kommentar geändert zu "Niemals manuelle Dateipfade benutzen" ohne konkreten Pfad.',
 NOW(),
 (SELECT id FROM dbai_knowledge.error_patterns WHERE name = 'forbidden_file_path_in_sql')),

('pg_cron möglicherweise nicht verfügbar',
 'pg_cron ist nicht in allen PostgreSQL-Installationen verfügbar. bootstrap.sh kann mit NOTICE durchlaufen.',
 'low', 'workaround',
 ARRAY['schema/00-extensions.sql'],
 'pg_cron-Extension manuell installieren: apt install postgresql-16-cron',
 NULL, NULL, NULL),

('plpython3u nicht standardmäßig installiert',
 'Die LLM SQL-Funktionen könnten plpython3u nutzen, das nicht standardmäßig verfügbar ist.',
 'low', 'workaround',
 ARRAY['schema/08-llm-integration.sql'],
 'Die LLM-Funktionen arbeiten über den Python LLM-Bridge Service statt direkt über plpython3u.',
 NULL, NULL, NULL)
ON CONFLICT DO NOTHING;

-- =============================================================================
-- 8. BUILD LOG — Initialer Build dokumentiert
-- =============================================================================

INSERT INTO dbai_knowledge.build_log
    (build_type, success, description, system_info) VALUES

('initial_install', TRUE,
 'DBAI v0.1.0 Erstinstallation: 35 Dateien erstellt, C-Bindings kompiliert, 18/18 Tests bestanden.',
 '{"os":"Linux x86_64","python":"3.11+","postgresql":"16+","gcc":"available","date":"2026-03-15"}'::JSONB),

('c_compile', FALSE,
 'Erster Compile-Versuch fehlgeschlagen: CLOCK_MONOTONIC undeclared (fehlende _POSIX_C_SOURCE).',
 '{"file":"bridge/c_bindings/hw_interrupts.c","error":"CLOCK_MONOTONIC undeclared","fix":"#define _POSIX_C_SOURCE 199309L"}'::JSONB),

('c_compile', TRUE,
 'Zweiter Compile-Versuch erfolgreich nach _POSIX_C_SOURCE Fix. libhw_interrupts.so erstellt.',
 '{"file":"bridge/c_bindings/hw_interrupts.c","output":"libhw_interrupts.so"}'::JSONB),

('schema_migration', TRUE,
 'DBAI v0.2.0: Knowledge Library Schemas (11, 12, 13) erstellt und Seed-Daten geladen.',
 '{"schemas_added":["11-knowledge-library.sql","12-error-patterns.sql","13-seed-data.sql","14-self-healing.sql"],"date":"2026-03-15"}'::JSONB),

('schema_migration', TRUE,
 'DBAI v0.3.0: Ghost System + Desktop UI + Web-Server + React Frontend.',
 '{"schemas_added":["15-ghost-system.sql","16-desktop-ui.sql","17-ghost-desktop-seed.sql"],"files_added":["web/server.py","web/ghost_dispatcher.py","frontend/"],"tests":"60/60","date":"2026-03-15"}'::JSONB),

('schema_migration', TRUE,
 'DBAI v0.4.0: Hardware Abstraction Layer + Neural Bridge + GPU Management.',
 '{"schemas_added":["18-hardware-abstraction.sql","19-neural-bridge.sql","20-hw-seed-data.sql"],"files_added":["bridge/hardware_scanner.py","bridge/gpu_manager.py"],"tests":"88/88","date":"2026-03-15"}'::JSONB),

('schema_migration', TRUE,
 'DBAI v0.5.0: OpenClaw Bridge + TabulaOS Strategie. Migration von OpenClaw/SillyTavern/Oobabooga.',
 '{"schemas_added":["21-openclaw-bridge.sql"],"files_added":["bridge/openclaw_importer.py"],"strategy":"The Database is the Ghost","date":"2026-03-15"}'::JSONB),

('schema_migration', TRUE,
 'DBAI v0.6.0: Ghost Autonomy + App Ecosystem. KI wird zentraler Scheduler mit Safety-Tabellen, Browser-Automation, Email-Integration, OAuth.',
 '{"schemas_added":["22-ghost-autonomy.sql","23-app-ecosystem.sql"],"files_added":["bridge/ghost_autonomy.py","bridge/app_manager.py"],"strategy":"Safety-First Autonomy + Remote-Control Apps","date":"2026-03-15"}'::JSONB),

('schema_migration', TRUE,
 'DBAI v0.7.0: System Memory. Vollstaendiges KI-Gehirn in die DB gespeichert.',
 '{"schemas_added":["24-system-memory.sql","25-system-memory-seed.sql"],"strategy":"Kein Kontextverlust zwischen Sessions","date":"2026-03-15"}'::JSONB)
ON CONFLICT DO NOTHING;

-- =============================================================================
-- FERTIG — Alles Wissen liegt jetzt in der Datenbank
--
-- Nützliche Abfragen:
--   SELECT * FROM dbai_knowledge.vw_module_overview;
--   SELECT * FROM dbai_knowledge.vw_system_health;
--   SELECT * FROM dbai_knowledge.vw_boot_sequence;
--   SELECT dbai_knowledge.generate_system_report();
--   SELECT * FROM dbai_knowledge.log_error('compile', 'CLOCK_MONOTONIC undeclared');
--   SELECT * FROM dbai_knowledge.find_runbook('compile', 'CLOCK_MONOTONIC');
--   SELECT * FROM dbai_knowledge.impact_analysis('schema/00-extensions.sql');
-- =============================================================================
