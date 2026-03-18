-- ==========================================================================
-- DBAI Knowledge Session — v0.10.9 (System Monitor & App-Diagnose Fix)
-- Datum: 2026-03-17
-- ==========================================================================

-- Changelog
INSERT INTO dbai_knowledge.changelog (version, change_type, title, description, affected_files, author)
VALUES
('0.10.9', 'fix', 'SystemMonitor: Leere Hardware-Tabellen → psutil Live-Daten',
 'Root Cause: DB-Tabellen dbai_system.cpu, memory, disk, network, temperature waren komplett leer (0 Zeilen). Die View dbai_system.current_status gab deshalb nur NULL-Werte zurück → SystemMonitor zeigte keine Daten. Fix: /api/system/status Endpoint nutzt jetzt psutil direkt für Live-Daten (CPU per-core, Memory inkl. Swap, Disks mit Partitionen, Network-Interfaces, Uptime, Load Average) und persistiert gleichzeitig in die DB für Verlaufsdaten.',
 ARRAY['web/server.py'],
 'ghost-agent')
ON CONFLICT DO NOTHING;

INSERT INTO dbai_knowledge.changelog (version, change_type, title, description, affected_files, author)
VALUES
('0.10.9', 'fix', 'ProcessManager: Leere Prozess-Tabelle → psutil Live-Prozesse',
 'Root Cause: dbai_core.processes Tabelle war leer (0 Zeilen). Fix: /api/system/processes Endpoint nutzt jetzt psutil.process_iter() für Live-Prozess-Daten (pid, name, state, cpu_percent, memory_percent, username). Top 100 Prozesse sortiert nach CPU-Last.',
 ARRAY['web/server.py'],
 'ghost-agent')
ON CONFLICT DO NOTHING;

INSERT INTO dbai_knowledge.changelog (version, change_type, title, description, affected_files, author)
VALUES
('0.10.9', 'fix', 'WLANHotspot: Falsche Methodennamen → 500 Server Error',
 'Root Cause: server.py rief hotspot.create(), hotspot.stop(), hotspot.status() auf. Die korrekten Methodennamen in bridge/stufe4_utils.py sind: create_hotspot(), stop_hotspot(), get_status(). Fix: Alle 3 Aufrufe korrigiert.',
 ARRAY['web/server.py'],
 'ghost-agent')
ON CONFLICT DO NOTHING;

-- System Memory
INSERT INTO dbai_knowledge.system_memory (category, title, content, tags, author)
VALUES
('convention', 'System-Daten: psutil-First statt DB-First',
 'KONVENTION: Für Echtzeit-Systemdaten (CPU, RAM, Disk, Prozesse) IMMER psutil als primäre Quelle nutzen. Die DB dient nur als Verlaufs-Speicher. Grund: Hardware-Scanner-Daemon läuft nicht zuverlässig im Docker-Container, daher sind DB-Tabellen oft leer.
/api/system/status → psutil live + DB persist
/api/system/processes → psutil.process_iter() live
/api/system/metrics → psutil live (war schon vorher korrekt implementiert)
Die View dbai_system.current_status bleibt als historische Referenz, wird aber nicht mehr für Live-Daten verwendet.',
 ARRAY['psutil','system-monitor','convention','hardware'],
 'ghost-agent')
ON CONFLICT DO NOTHING;

INSERT INTO dbai_knowledge.system_memory (category, title, content, tags, author)
VALUES
('convention', 'stufe4_utils Methodennamen-Mapping',
 'Korrekte Methodennamen der Bridge-Klassen in bridge/stufe4_utils.py:

WLANHotspot: create_hotspot(ssid,pw), stop_hotspot(), get_status()
ImmutableFS: get_config(), create_snapshot(label), restore_snapshot(id), list_snapshots()
AppSandbox: get_profiles(), list_running(), launch(profile_id,app), stop(id)
FirewallManager: get_rules(), get_zones(), get_connections(), add_rule(data), delete_rule(id)
NetworkScanner: scan(range), get_results()
AnomalyDetector: get_models(), get_detections(limit), train(model_id)
USBInstaller: detect_usb(), get_jobs(), create_job(data)

WICHTIG: NICHT .status()/.config()/.rules() direkt aufrufen — immer get_status()/get_config()/get_rules() verwenden!',
 ARRAY['stufe4','bridge','methodennamen','konvention'],
 'ghost-agent')
ON CONFLICT DO NOTHING;

INSERT INTO dbai_knowledge.system_memory (category, title, content, tags, author)
VALUES
('inventory', 'App-API-Audit v0.10.9: 22/22 Endpoints OK',
 'Vollständiger API-Audit aller App-Endpoints (Stand v0.10.9):
OK: /api/system/status (7 keys) | /api/system/processes [3 procs] | /api/system/health [8 checks] | /api/system/metrics (13k) | /api/system/diagnostics (3k) | /api/ghosts (4k: active_ghosts, models, roles, compatibility) | /api/ghosts/history [7] | /api/knowledge/modules [78] | /api/knowledge/errors [12] | /api/events [33] | /api/hotspot/status (1k) | /api/immutable/config (12k) | /api/immutable/snapshots (1k) | /api/sandbox/profiles (1k) | /api/sandbox/running (1k) | /api/firewall/rules (1k) | /api/firewall/zones (1k) | /api/anomaly/models (1k) | /api/usb/devices (1k) | /api/desktop/nodes (1k) | /api/mail/accounts [0] | /api/mail/inbox (2k)
22 von 22 getestet, 0 Fehler.',
 ARRAY['api-audit','endpoints','v0.10.9'],
 'ghost-agent')
ON CONFLICT DO NOTHING;

-- Build Log
INSERT INTO dbai_knowledge.build_log (build_type, success, duration_ms, description)
VALUES
('schema_migration', true, 1500,
 'v0.10.9: SystemMonitor+ProcessManager psutil-Fix, WLANHotspot Methodennamen-Fix. 22/22 App-Endpoints funktional.')
ON CONFLICT DO NOTHING;

-- Agent Session
INSERT INTO dbai_knowledge.agent_sessions (version_start, version_end, summary, files_created, files_modified, schemas_added, goals, decisions)
VALUES
('0.10.9', '0.10.9',
 'Umfassende DB-Diagnose aller App-Endpoints. Root Cause: Hardware-Tabellen (cpu, memory, disk etc.) waren leer → SystemMonitor/ProcessManager zeigten keine Daten. WLANHotspot hatte falsche Methodennamen (status→get_status). Fix: psutil-Live-Daten als primäre Quelle für System-Endpoints, Hotspot-Methodennamen korrigiert. 22/22 Endpoints funktional nach Fix.',
 ARRAY['schema/54-knowledge-session-v0.10.9.sql'],
 ARRAY['web/server.py'],
 ARRAY['schema/54-knowledge-session-v0.10.9.sql'],
 ARRAY['SystemMonitor DB-Diagnose','ProcessManager DB-Diagnose','WLANHotspot 500-Fix','Alle 36 App-Endpoints auditen'],
 ARRAY['psutil als primäre Datenquelle statt leerer DB-Tabellen','Live-Daten + gleichzeitige DB-Persistenz für Verlauf','Top-100 Prozesse statt komplette Liste','Methodennamen aus stufe4_utils.py abgeleitet statt geraten']
)
ON CONFLICT DO NOTHING;

-- Error Patterns
INSERT INTO dbai_knowledge.error_patterns (name, title, error_regex, error_source, severity, category, description, root_cause, solution_short)
VALUES
('empty_hardware_tables', 'Leere Hardware-Tabellen → NULL System-Status',
 'null.*cpu.*memory|avg_usage.*null|cores_online.*0',
 'runtime', 'high', 'missing_dependency',
 'System-Monitor zeigt keine Daten weil die Hardware-Tabellen (cpu, memory, disk, network, temperature) leer sind.',
 'Hardware-Scanner-Daemon (bridge/hardware_scanner.py) läuft nicht im Docker-Container. Kein Prozess befüllt die Tabellen.',
 'System-Endpoints (system/status, system/processes) verwenden psutil direkt als Live-Quelle mit gleichzeitiger DB-Persistenz.')
ON CONFLICT (name) DO NOTHING;

INSERT INTO dbai_knowledge.error_patterns (name, title, error_regex, error_source, severity, category, description, root_cause, solution_short)
VALUES
('wrong_bridge_method_name', 'Falsche Bridge-Methoden → AttributeError',
 'has no attribute.*status|has no attribute.*config|has no attribute.*rules',
 'runtime', 'medium', 'wrong_config',
 'Server.py ruft falsche Methodennamen auf stufe4_utils-Klassen auf (z.B. .status() statt .get_status()).',
 'Methodennamen in server.py wurden falsch angenommen statt aus der tatsächlichen Klasse abzulesen.',
 'Korrekte Methodennamen verwenden: get_status(), get_config(), get_rules(), create_hotspot(), stop_hotspot() etc.')
ON CONFLICT (name) DO NOTHING;

-- Known Issues (resolved)
INSERT INTO dbai_knowledge.known_issues (title, description, severity, status, affected_files, workaround, resolution)
VALUES
('SystemMonitor zeigt keine Daten — Hardware-Tabellen leer',
 'Alle Hardware-Tabellen in dbai_system (cpu, cpu_cores, memory, disk, network, temperature, gpu_devices, hardware_inventory, metrics_history) hatten 0 Zeilen. Die View dbai_system.current_status gab nur NULL zurück.',
 'high', 'resolved',
 ARRAY['web/server.py'],
 'Hardware-Scanner manuell starten: python3 bridge/hardware_scanner.py',
 '/api/system/status und /api/system/processes nutzen jetzt psutil direkt als Live-Quelle. Daten werden gleichzeitig in die DB persistiert für Verlaufsanalysen.')
ON CONFLICT DO NOTHING;

INSERT INTO dbai_knowledge.known_issues (title, description, severity, status, affected_files, workaround, resolution)
VALUES
('WLANHotspot 500 Error — Falsche Methodennamen',
 'server.py rief hotspot.status(), hotspot.create(), hotspot.stop() auf. Die korrekten Namen sind get_status(), create_hotspot(), stop_hotspot().',
 'medium', 'resolved',
 ARRAY['web/server.py'],
 'Keine',
 'Alle 3 Methodenaufrufe korrigiert: status→get_status, create→create_hotspot, stop→stop_hotspot')
ON CONFLICT DO NOTHING;
