-- =============================================================================
-- DBAI Schema 76: System-Memory Vervollständigung
-- Fügt alle bisher fehlenden Erkenntnisse aus 76 Schema-Dateien in
-- system_memory ein. Deckt fehlende Schema-Maps, Architektur-Wissen,
-- Inventar-Updates und undokumentierte Subsysteme ab.
-- =============================================================================

-- Changelog
INSERT INTO dbai_knowledge.changelog (version, change_type, title, description) VALUES
('0.15.1', 'feature', 'System-Memory Vervollständigung', 'Alle Schema-Erkenntnisse als system_memory dokumentiert — 76 Dateien analysiert')
ON CONFLICT DO NOTHING;

-- =============================================================================
-- 1. FEHLENDE SCHEMA-MAPS  (3 komplett neue + 4 Updates)
-- =============================================================================

-- ── dbai_workshop — KI-Werkstatt (Schema 28 + 38) ──
INSERT INTO dbai_knowledge.system_memory
  (category, title, content, tags, author, related_schemas, related_modules, valid_from, priority)
VALUES (
  'schema_map',
  'dbai_workshop — KI-Werkstatt',
  E'Schema für die KI-Werkstatt-App. Ermöglicht Benutzern eigene KI-Datenbank-Projekte (Medien, Wissen, Smart-Home, Personal Assistant) zu erstellen.\n\n'
  || E'Tabellen (11):\n'
  || E'• projects — Eigene KI-Datenbank-Projekte mit Template-Auswahl\n'
  || E'• media_items — Medien-Items (Bilder, Videos, Audio, Texte) mit vector(384)-Embedding\n'
  || E'• collections — Sammlungen/Alben/Playlists/Smart Collections\n'
  || E'• collection_items — M:N-Zuordnung Items ↔ Sammlungen\n'
  || E'• smart_devices — Smart-Home-Geräte (Alexa, Google Home, MQTT, HomeAssistant)\n'
  || E'• chat_history — KI-Chat-Verlauf pro Projekt\n'
  || E'• import_jobs — Batch-Import (lokaler Ordner, URL, Google Photos, NAS, USB)\n'
  || E'• templates — Projektvorlagen für schnellen Start\n'
  || E'• api_keys — API-Schlüssel für externe Dienste pro Projekt\n'
  || E'• custom_tables — Benutzerdefinierte Tabellen-Definitionen (Schema als JSONB)\n'
  || E'• custom_rows — Datenzeilen für benutzerdefinierte Tabellen\n\n'
  || E'Design: Jedes Projekt ist isoliert. Medien nutzen pgvector-Embeddings für semantische Suche. Custom Tables erlauben dem User beliebige Datenstrukturen ohne SQL-Kenntnisse.',
  ARRAY['workshop', 'ki-werkstatt', 'media', 'smart-home', 'custom-tables', 'pgvector'],
  'system',
  ARRAY['dbai_workshop'],
  ARRAY['bridge/workspace_mapper.py'],
  '0.8.0', 70
) ON CONFLICT (category, title) DO NOTHING;

-- ── dbai_net — Netzwerk & Mobile Bridge (Schema 68) ──
INSERT INTO dbai_knowledge.system_memory
  (category, title, content, tags, author, related_schemas, related_modules, valid_from, priority)
VALUES (
  'schema_map',
  'dbai_net — Netzwerk & Mobile Bridge',
  E'Schema für das 5-dimensionale Netzwerk-System und die Mobile Bridge.\n\n'
  || E'Tabellen (11):\n'
  || E'• network_interfaces — Alle Netzwerkschnittstellen (usb0, wlan0, eth0)\n'
  || E'• mobile_devices — Registrierte Smartphones/Tablets mit Sensor-Capabilities\n'
  || E'• sensor_data — Sensor-Pipeline: GPS, Kamera, Audio, NFC, QR → PostgreSQL mit vector(1536)\n'
  || E'• pwa_config — PWA-Konfiguration (manifest.json, Service Worker, Install-Prompt)\n'
  || E'• hotspot_config — WLAN-Hotspot (hostapd + dnsmasq)\n'
  || E'• dhcp_leases — DHCP-Leases: Gerät ↔ IP\n'
  || E'• usb_gadget_config — USB-Gadget OTG (dwc2, RNDIS/ECM)\n'
  || E'• mdns_config — mDNS/Avahi: ghost.local Discovery\n'
  || E'• connection_sessions — Aktive Verbindungen über alle 5 Dimensionen\n'
  || E'• boot_dimensions — Die 5 Zugangs-Dimensionen (PC, USB-C, WLAN, LAN, Bluetooth)\n'
  || E'• hardware_profiles — Hardware-Profile (RPi Zero 2 W, Radxa Zero, etc.)\n\n'
  || E'Design: Jedes Gerät kann DBAI über 5 Dimensionen erreichen. Sensor-Daten werden als pgvector-Embeddings gespeichert. PWA macht eine native App überflüssig.',
  ARRAY['network', 'mobile', '5d', 'pwa', 'hotspot', 'usb-gadget', 'mdns', 'sensor'],
  'system',
  ARRAY['dbai_net'],
  ARRAY['bridge/system_bridge.py'],
  '0.13.0', 70
) ON CONFLICT (category, title) DO NOTHING;

-- ── dbai_security — Sicherheits-Immunsystem (Schema 73 + 75) ──
INSERT INTO dbai_knowledge.system_memory
  (category, title, content, tags, author, related_schemas, related_modules, valid_from, priority)
VALUES (
  'schema_map',
  'dbai_security — Sicherheits-Immunsystem',
  E'Schema für das 4-Schichten-Sicherheitssystem mit KI-gestützter Analyse.\n\n'
  || E'Schicht 1 — Proaktiv (Angriffserkennung):\n'
  || E'• scan_jobs — Scheduler für Nmap, SQLMap, Nuclei, Lynis-Scans\n'
  || E'• vulnerability_findings — Schwachstellen mit CVSS-Score + Auto-Mitigation\n'
  || E'• cve_tracking — CVE-Tracking für genutzte Pakete\n'
  || E'• security_baselines — CIS/STIG-Referenzwerte\n\n'
  || E'Schicht 2 — Reaktiv (Echtzeit):\n'
  || E'• intrusion_events — IDS/IPS-Events (Snort/Suricata)\n'
  || E'• threat_intelligence — IOC-Datenbank (IPs, Domains, Hashes)\n'
  || E'• honeypot_events — Honeypot-Fallen (Append-Only)\n'
  || E'• security_responses — Automatische Gegenmaßnahmen-Log\n\n'
  || E'Schicht 3 — Passiv (Monitoring):\n'
  || E'• failed_auth_log — Fehlgeschlagene Logins (Fail2Ban)\n'
  || E'• ip_bans — IP-Sperren (temporär/permanent/Geo)\n'
  || E'• network_traffic_log — Traffic für Anomalie-Erkennung\n'
  || E'• rate_limits — Dynamische Rate-Limits (IP/User/Endpoint)\n'
  || E'• dns_sinkhole — DNS-Blocklisten (Malware, Phishing, C2)\n'
  || E'• tls_certificates — TLS-Verwaltung mit Auto-Renew\n'
  || E'• permission_audit — GRANT/REVOKE-Protokollierung\n'
  || E'• security_metrics — Aggregierte Dashboard-Metriken\n\n'
  || E'Schicht 4 — KI-Analyse (Schema 75):\n'
  || E'• ai_tasks — KI-gesteuerte Sicherheitsanalysen (10 Task-Typen)\n'
  || E'• ai_config — KI-Konfiguration (Schwellenwerte, Auto-Response)\n'
  || E'• ai_analysis_log — Alle KI-Analysen (Append-Only)\n\n'
  || E'Gesamt: 19 Tabellen, 7 Trigger, 5 Funktionen, 3 Views.',
  ARRAY['security', 'firewall', 'ids', 'ips', 'honeypot', 'cve', 'fail2ban', 'ai-security'],
  'system',
  ARRAY['dbai_security'],
  ARRAY['bridge/security_immunsystem.py', 'bridge/security_monitor_ai.py'],
  '0.15.0', 85
) ON CONFLICT (category, title) DO NOTHING;

-- ── CI/CD & OTA Tabellen in dbai_system (Schema 36) ──
INSERT INTO dbai_knowledge.system_memory
  (category, title, content, tags, author, related_schemas, related_modules, valid_from, priority)
VALUES (
  'schema_map',
  'dbai_system — CI/CD & OTA-Update-System',
  E'Ergänzende Tabellen in dbai_system für CI/CD und Over-the-Air Updates (Schema 36).\n\n'
  || E'Tabellen (6):\n'
  || E'• update_channels — Update-Kanäle: stable, beta, nightly, dev\n'
  || E'• system_releases — Veröffentlichte Versionen mit Artefakten (ISO, Checksumms)\n'
  || E'• migration_history — SQL-Migrations-Tracking (Checksum, Duration, Status)\n'
  || E'• ota_nodes — OTA-Empfänger (verbundene Rechner mit Hardware-Info)\n'
  || E'• build_pipeline — CI/CD Build-Ergebnisse (Status, Logs, Artefakte)\n'
  || E'• update_jobs — Konkrete Update-Aufträge pro Node (Download, Apply, Reboot)\n\n'
  || E'Design: Zentrales Update-System. Releases werden über Kanäle verteilt. Jeder OTA-Node pollt auf neue Updates. Migration-History verhindert doppelte Schema-Ausführung.',
  ARRAY['cicd', 'ota', 'updates', 'releases', 'migration'],
  'system',
  ARRAY['dbai_system'],
  ARRAY['bridge/gs_updater.py'],
  '0.9.0', 65
) ON CONFLICT (category, title) DO NOTHING;

-- ── Ghost Browser in dbai_system (Schema 56) ──
INSERT INTO dbai_knowledge.system_memory
  (category, title, content, tags, author, related_schemas, related_modules, valid_from, priority)
VALUES (
  'schema_map',
  'dbai_system — Ghost Browser Subsystem',
  E'KI-gesteuertes Browser-Subsystem in dbai_system (Schema 56).\n\n'
  || E'Tabellen (3):\n'
  || E'• ghost_browser_tasks — Aufträge: Research, Screenshot, Extract, Monitor, Form-Fill\n'
  || E'• ghost_browser_steps — Detailliertes Step-Log pro Task (navigate, click, extract, etc.)\n'
  || E'• ghost_browser_presets — Gespeicherte Browser-Workflows/Templates\n\n'
  || E'Design: Ghost kann autonom browsen. Jeder Task hat Steps die sequenziell abgearbeitet werden. Presets ermöglichen wiederkehrende Workflows.',
  ARRAY['browser', 'ghost', 'automation', 'puppeteer', 'playwright'],
  'system',
  ARRAY['dbai_system'],
  ARRAY['bridge/browser_agent.py'],
  '0.11.0', 55
) ON CONFLICT (category, title) DO NOTHING;

-- ── Ghost Autonomy Tabellen in dbai_llm (Schema 22) ──
INSERT INTO dbai_knowledge.system_memory
  (category, title, content, tags, author, related_schemas, related_modules, valid_from, priority)
VALUES (
  'schema_map',
  'dbai_llm — Ghost-Autonomie-System',
  E'Erweiterung von dbai_llm für autonome Ghost-Aktionen (Schema 22).\n\n'
  || E'Tabellen (4):\n'
  || E'• proposed_actions — Safety-System: kritische Aktionen müssen genehmigt werden\n'
  || E'• ghost_context — Context Injection: was der Ghost beim Laden weiß\n'
  || E'• ghost_thought_log — Thought-Stream (Append-Only): was die KI denkt/tut\n'
  || E'• ghost_feedback — Feedback-Loop: Lernen aus Genehmigungen/Ablehnungen\n\n'
  || E'Design: Safety-First. Jede potenziell destruktive Aktion wird zuerst als proposed_action erstellt und muss vom User genehmigt werden, bevor sie ausgeführt wird.',
  ARRAY['ghost', 'autonomy', 'safety', 'proposed-actions', 'feedback'],
  'system',
  ARRAY['dbai_llm'],
  ARRAY['bridge/ghost_autonomy.py'],
  '0.7.0', 75
) ON CONFLICT (category, title) DO NOTHING;

-- ── Distributed Ghosts / Vision / Multi-GPU in dbai_llm (Schema 69) ──
INSERT INTO dbai_knowledge.system_memory
  (category, title, content, tags, author, related_schemas, related_modules, valid_from, priority)
VALUES (
  'schema_map',
  'dbai_llm — Advanced Features (Vision, Multi-GPU, Distributed, Marketplace)',
  E'Erweiterte KI-Fähigkeiten in dbai_llm (Schema 69).\n\n'
  || E'Multi-GPU (3 Tabellen):\n'
  || E'• gpu_split_configs — Layer-Split-Konfigurationen über mehrere GPUs\n'
  || E'• parallel_inference_sessions — Aktive Multi-GPU-Inferenz-Sessions\n'
  || E'• gpu_sync_events — GPU-zu-GPU-Kommunikation (Tensor-Transfer, KV-Cache)\n\n'
  || E'Vision (3 Tabellen):\n'
  || E'• vision_models — Vision-Modelle (Classification, Detection, OCR, Segmentation)\n'
  || E'• vision_tasks — Vision-Analyse-Queue mit Embeddings\n'
  || E'• vision_detections — Erkannte Objekte mit Bounding-Box + Confidence\n\n'
  || E'Distributed Ghosts (4 Tabellen):\n'
  || E'• ghost_nodes — Node-Registry (Coordinator/Worker/Edge)\n'
  || E'• node_heartbeats — Node-Health (CPU, RAM, GPU, Latenz)\n'
  || E'• distributed_tasks — Task-Routing zwischen Nodes\n'
  || E'• model_replicas — Welches Modell auf welchem Node\n\n'
  || E'Marketplace (3 Tabellen):\n'
  || E'• marketplace_catalog — HuggingFace GGUF-Modell-Katalog\n'
  || E'• model_downloads — Download-Queue mit Fortschritt\n'
  || E'• model_reviews — User/Ghost-Bewertungen für Modelle',
  ARRAY['multi-gpu', 'vision', 'distributed', 'marketplace', 'huggingface'],
  'system',
  ARRAY['dbai_llm'],
  ARRAY['bridge/gpu_manager.py'],
  '0.14.0', 70
) ON CONFLICT (category, title) DO NOTHING;


-- =============================================================================
-- 2. ARCHITEKTUR-WISSEN — Bisher nicht dokumentierte Subsysteme
-- =============================================================================

-- ── App Ecosystem ──
INSERT INTO dbai_knowledge.system_memory
  (category, title, content, tags, author, related_schemas, related_modules, valid_from, priority)
VALUES (
  'architecture',
  'App-Ökosystem Architektur (Schema 23)',
  E'Das App-Ökosystem erweitert DBAI um externe Integrationen.\n\n'
  || E'Tabellen in dbai_core:\n'
  || E'• software_catalog — App Store (apt, pip, npm, GitHub, etc.)\n'
  || E'• browser_sessions — Headless-Browser-Sessions mit Embedding\n'
  || E'• oauth_connections — OAuth (Google, GitHub, Slack, Discord)\n'
  || E'• workspace_sync — Externe Daten-Sync (Drive, Notion, Dropbox)\n\n'
  || E'Tabellen in dbai_llm:\n'
  || E'• command_history — Sprache/Text → interpretierter Befehl → Aktion\n\n'
  || E'Tabellen in dbai_event:\n'
  || E'• email_accounts — E-Mail-Konten (IMAP/SMTP)\n'
  || E'• inbox — Eingehende E-Mails mit KI-Analyse (Embedding, Tags, Sentiment)\n'
  || E'• outbox — Ausgehende E-Mails (Draft, Review, Approved, Sent)\n\n'
  || E'Design: Alles dreht sich um KI-Integration. E-Mails werden per KI analysiert, Befehle per NLU interpretiert, externe Dienste über OAuth angebunden.',
  ARRAY['app-ecosystem', 'oauth', 'email', 'software-catalog', 'sync'],
  'system',
  ARRAY['dbai_core', 'dbai_llm', 'dbai_event'],
  ARRAY['bridge/openclaw_importer.py', 'bridge/config_importer.py'],
  '0.7.0', 60
) ON CONFLICT (category, title) DO NOTHING;

-- ── Autonome Migrationen ──
INSERT INTO dbai_knowledge.system_memory
  (category, title, content, tags, author, related_schemas, related_modules, valid_from, priority)
VALUES (
  'architecture',
  'Autonomous Coding / Migrationen (Schema 69)',
  E'DBAI kann autonom SQL-Migrationen generieren und ausführen.\n\n'
  || E'Tabellen in dbai_core:\n'
  || E'• autonomous_migrations — KI-generierte SQL-Migrationen mit State-Machine\n'
  || E'  States: proposed → reviewing → approved → executing → completed/rolled_back\n'
  || E'• migration_audit_log — Audit-Trail für jede Aktion\n\n'
  || E'Sicherheitspattern:\n'
  || E'• Jede Migration durchläuft Review-Prozess\n'
  || E'• Sandbox-Test vor Produktion\n'
  || E'• Automatisches Rollback bei Fehler\n'
  || E'• Audit-Trail für Compliance',
  ARRAY['autonomous', 'migration', 'code-generation', 'safety'],
  'system',
  ARRAY['dbai_core'],
  ARRAY['bridge/migration_runner.py'],
  '0.14.0', 60
) ON CONFLICT (category, title) DO NOTHING;

-- ── Desktop UI Erweiterungen ──
INSERT INTO dbai_knowledge.system_memory
  (category, title, content, tags, author, related_schemas, related_modules, valid_from, priority)
VALUES (
  'architecture',
  'Desktop UI Erweiterungen (Schema 30, 39, 52)',
  E'Drei Erweiterungen des dbai_ui-Schemas:\n\n'
  || E'1. Desktop-Nodes (Schema 30):\n'
  || E'• desktop_nodes — SVG-basierte Netzwerk-Visualisierung (Services, Devices, Cloud)\n'
  || E'• desktop_scene — Globale Szenen-Konfiguration (Zoom, Pan, Theme)\n\n'
  || E'2. App-Settings (Schema 39):\n'
  || E'• app_user_settings — Per-User, per-App Einstellungen als JSONB\n'
  || E'  → Validiert gegen JSON-Schema in dbai_ui.apps.settings_schema\n\n'
  || E'3. Tab-Isolation (Schema 52):\n'
  || E'• tab_instances — Jeder Browser-Tab = eigener virtueller Desktop\n'
  || E'  → sessionStorage statt localStorage für Tab-Isolation\n'
  || E'  → Eigener Zustand pro Tab (offene Fenster, Positionen)',
  ARRAY['desktop', 'ui', 'tabs', 'settings', 'nodes', 'svg'],
  'system',
  ARRAY['dbai_ui'],
  ARRAY[]::TEXT[],
  '0.8.0', 55
) ON CONFLICT (category, title) DO NOTHING;

-- ── Agent Instances ──
INSERT INTO dbai_knowledge.system_memory
  (category, title, content, tags, author, related_schemas, related_modules, valid_from, priority)
VALUES (
  'architecture',
  'Agent Instances (Schema 58)',
  E'LLM Worker-Prozesse werden als Agent-Instanzen registriert.\n\n'
  || E'Tabelle in dbai_llm:\n'
  || E'• agent_instances — Jeder laufende LLM-Worker:\n'
  || E'  - Backend-Typ (llama.cpp, vLLM, Ollama)\n'
  || E'  - GPU-Zuordnung + VRAM-Nutzung\n'
  || E'  - Port + PID + State\n'
  || E'  - Version + Capabilities\n\n'
  || E'Zweck: Ermöglicht Multi-Agent-Setups wo mehrere LLMs parallel auf verschiedenen GPUs laufen. Der Ghost-Dispatcher routet Anfragen an verfügbare Agenten.',
  ARRAY['agent', 'llm', 'worker', 'multi-agent', 'gpu'],
  'system',
  ARRAY['dbai_llm'],
  ARRAY['web/ghost_dispatcher.py'],
  '0.12.0', 60
) ON CONFLICT (category, title) DO NOTHING;


-- =============================================================================
-- 3. DESIGN-PATTERN — Bisher nicht dokumentierte Muster
-- =============================================================================

INSERT INTO dbai_knowledge.system_memory
  (category, title, content, tags, author, related_schemas, valid_from, priority)
VALUES (
  'design_pattern',
  'Safety-First: proposed_actions Gate',
  E'Jede potenziell destruktive Ghost-Aktion durchläuft ein Genehmigungsgate.\n\n'
  || E'Ablauf:\n'
  || E'1. Ghost erstellt proposed_action (action_type, parameters, risk_level)\n'
  || E'2. User sieht Vorschlag in der UI mit Risikobewertung\n'
  || E'3. User genehmigt oder lehnt ab\n'
  || E'4. Bei Genehmigung: Ausführung + Feedback-Eintrag\n'
  || E'5. Bei Ablehnung: Feedback → Ghost lernt daraus\n\n'
  || E'Risk-Levels: low (auto-approve möglich), medium (UI-Bestätigung), high (Admin-Only), critical (gesperrt)\n\n'
  || E'Tabellen: dbai_llm.proposed_actions, dbai_llm.ghost_feedback',
  ARRAY['safety', 'proposed-actions', 'approval-gate', 'ghost'],
  'system',
  ARRAY['dbai_llm'],
  '0.7.0', 80
) ON CONFLICT (category, title) DO NOTHING;

INSERT INTO dbai_knowledge.system_memory
  (category, title, content, tags, author, related_schemas, valid_from, priority)
VALUES (
  'design_pattern',
  '4-Schichten-Immunsystem',
  E'Das Security-System arbeitet in 4 selbstregulierenden Schichten:\n\n'
  || E'Schicht 1 — Proaktiv: Scanner finden Schwachstellen bevor Angreifer es tun\n'
  || E'  → scan_jobs → vulnerability_findings → KI-Bewertung\n\n'
  || E'Schicht 2 — Reaktiv: Echtzeit-Erkennung und sofortige Reaktion\n'
  || E'  → intrusion_events → ai_tasks → security_responses → ip_bans\n\n'
  || E'Schicht 3 — Passiv: Kontinuierliches Monitoring aller Subsysteme\n'
  || E'  → failed_auth_log, network_traffic_log, tls_certificates, permission_audit\n\n'
  || E'Schicht 4 — KI-Analyse: Security-Monitor-Ghost bewertet und entscheidet\n'
  || E'  → ai_tasks → Ghost Inference → auto_executed Aktionen\n\n'
  || E'Rückkopplungsschleife:\n'
  || E'Event → DB-Trigger → pg_notify("security_ai_task") → SecurityMonitorAI → Ghost → Analyse → Auto-Response → Audit-Log → Feedback → Nächste Analyse',
  ARRAY['security', 'immunsystem', 'feedback-loop', '4-layer'],
  'system',
  ARRAY['dbai_security'],
  '0.15.0', 85
) ON CONFLICT (category, title) DO NOTHING;

INSERT INTO dbai_knowledge.system_memory
  (category, title, content, tags, author, related_schemas, valid_from, priority)
VALUES (
  'design_pattern',
  'Sensor-Pipeline: Physische Welt → DB → KI',
  E'Mobile-Bridge-Pattern für die Verarbeitung von Sensor-Daten:\n\n'
  || E'1. Smartphone sendet Sensor-Daten (GPS, Kamera, Audio, NFC, QR) per WebSocket\n'
  || E'2. server.py schreibt in dbai_net.sensor_data mit vector(1536)-Embedding\n'
  || E'3. Ghost kann Sensor-Daten semantic abfragen ("Wo war ich gestern?")\n'
  || E'4. Echtzeit-Events über pg_notify("sensor_data_new")\n\n'
  || E'Das Pattern macht reale Welt-Daten für die KI zugänglich.',
  ARRAY['sensor', 'mobile', 'embedding', 'pgvector', 'websocket'],
  'system',
  ARRAY['dbai_net'],
  '0.13.0', 55
) ON CONFLICT (category, title) DO NOTHING;


-- =============================================================================
-- 4. INVENTAR-UPDATES — Aktuelle Zahlen
-- =============================================================================

INSERT INTO dbai_knowledge.system_memory
  (category, title, content, tags, author, related_schemas, valid_from, priority)
VALUES (
  'inventory',
  'Schema-Dateien Gesamtzahl: 76',
  E'Stand: v0.15.1 — 76 SQL-Schema-Dateien in /schema/\n\n'
  || E'Aufgliederung:\n'
  || E'• 00-09: Grundlagen (Extensions, Core, System, Events, Vector, WAL, Panic, RLS, LLM, Vacuum)\n'
  || E'• 10-19: Infrastruktur (Sync, Knowledge, Error-Patterns, Seed, Self-Healing, Ghost, Desktop, Ghost-Seed, HW, Neural, HW-Seed)\n'
  || E'• 20-29: Features (OpenClaw, Autonomy, App-Ecosystem, Memory, Memory-Seed, Apps-Seed, Immutability, Workshop, LLM-Providers, Apps-Reg)\n'
  || E'• 30-39: Erweiterungen (Desktop-Nodes, Stufe1/2-Seed, Diagnostic, Stufe3, Stufe4, Stufe3/4-Seed, CI/CD, CI/CD-Seed, Custom-Tables, Settings)\n'
  || E'• 40-55: Iterationen (Settings-Seeds, Knowledge-Sessions v0.9-v0.10.10, Tab-Isolation)\n'
  || E'• 56-72: Reife-Phase (Ghost-Browser, Compat, Agents, Users, Process-Merge, LLM-Manager, USB-Boot, Remote-Access, USB-Fix, Ghost-LLM, Ghost-Chat, GPU-Fix, Sandbox-Fix, Mobile, Advanced, Code-Quality, Hardening, Dedup)\n'
  || E'• 73-76: Security (Immunsystem, Seed, AI-Integration, Memory-Complete)\n\n'
  || E'13 Schemas, ~200+ Tabellen, 50+ Funktionen, 80+ Trigger',
  ARRAY['inventory', 'schema', 'statistics'],
  'system',
  ARRAY['dbai_core', 'dbai_system', 'dbai_event', 'dbai_vector', 'dbai_journal', 'dbai_panic', 'dbai_llm', 'dbai_knowledge', 'dbai_ui', 'dbai_workshop', 'dbai_net', 'dbai_security'],
  '0.15.1', 90
) ON CONFLICT (category, title) DO UPDATE SET
  content = EXCLUDED.content,
  tags = EXCLUDED.tags,
  related_schemas = EXCLUDED.related_schemas,
  valid_from = EXCLUDED.valid_from,
  updated_at = NOW();

INSERT INTO dbai_knowledge.system_memory
  (category, title, content, tags, author, related_schemas, valid_from, priority)
VALUES (
  'inventory',
  'Gesamt-Tabellen-Inventar pro Schema',
  E'Alle Schemas und ihre Tabellenzahl (Stand v0.15.1):\n\n'
  || E'• dbai_core — 15 Tabellen (users, settings, api_keys, sessions, software_catalog, oauth, workspace_sync, ghost_files, browser_sessions, autonomous_migrations, migration_audit_log, ...)\n'
  || E'• dbai_system — 24 Tabellen (hardware_info, gpu_devices, usb_devices, disk_drives, gpu_vram_allocations, system_snapshots, process_importance, energy_consumption, update_channels, system_releases, migration_history, ota_nodes, build_pipeline, update_jobs, ghost_browser_tasks/steps/presets, ...)\n'
  || E'• dbai_event — 8 Tabellen (events, notifications, email_accounts, inbox, outbox, ...)\n'
  || E'• dbai_vector — 4 Tabellen (embeddings, memory_contexts, ...)\n'
  || E'• dbai_journal — 3 Tabellen (wal_entries, checkpoint_history, ...)\n'
  || E'• dbai_panic — 4 Tabellen (panic_log, recovery_plans, safe_state_snapshots, ...)\n'
  || E'• dbai_llm — 30+ Tabellen (ghost_models, ghost_roles, active_ghosts, ghost_history, ghost_compatibility, task_queue, conversations, messages, proposed_actions, ghost_context, ghost_thought_log, ghost_feedback, command_history, agent_instances, gpu_split_configs, parallel_inference_sessions, vision_*, ghost_nodes, distributed_tasks, marketplace_*, model_downloads, model_reviews)\n'
  || E'• dbai_knowledge — 5+ Tabellen (changelog, system_memory, knowledge_entries, error_patterns, ...)\n'
  || E'• dbai_ui — 10+ Tabellen (apps, window_state, desktop_themes, desktop_nodes, desktop_scene, app_user_settings, tab_instances, ...)\n'
  || E'• dbai_workshop — 11 Tabellen (projects, media_items, collections, collection_items, smart_devices, chat_history, import_jobs, templates, api_keys, custom_tables, custom_rows)\n'
  || E'• dbai_net — 11 Tabellen (network_interfaces, mobile_devices, sensor_data, pwa_config, hotspot_config, dhcp_leases, usb_gadget_config, mdns_config, connection_sessions, boot_dimensions, hardware_profiles)\n'
  || E'• dbai_security — 19 Tabellen (scan_jobs, vulnerability_findings, intrusion_events, threat_intelligence, failed_auth_log, ip_bans, network_traffic_log, security_responses, tls_certificates, security_baselines, cve_tracking, permission_audit, security_metrics, honeypot_events, rate_limits, dns_sinkhole, ai_tasks, ai_config, ai_analysis_log)\n\n'
  || E'Gesamt: ~200+ Tabellen über 12 Schemas',
  ARRAY['inventory', 'tables', 'schemas', 'statistics'],
  'system',
  ARRAY['dbai_core', 'dbai_system', 'dbai_event', 'dbai_vector', 'dbai_journal', 'dbai_panic', 'dbai_llm', 'dbai_knowledge', 'dbai_ui', 'dbai_workshop', 'dbai_net', 'dbai_security'],
  '0.15.1', 85
) ON CONFLICT (category, title) DO UPDATE SET
  content = EXCLUDED.content,
  tags = EXCLUDED.tags,
  related_schemas = EXCLUDED.related_schemas,
  valid_from = EXCLUDED.valid_from,
  updated_at = NOW();

INSERT INTO dbai_knowledge.system_memory
  (category, title, content, tags, author, related_schemas, related_modules, valid_from, priority)
VALUES (
  'inventory',
  'Bridge-Module Übersicht (v0.15.1)',
  E'17 Python-Bridge-Module in /bridge/:\n\n'
  || E'• app_manager.py — App-Lifecycle, Install/Remove/Update\n'
  || E'• browser_agent.py — Playwright/Puppeteer Ghost-Browser-Steuerung\n'
  || E'• browser_migration.py — Browser-Daten-Migration\n'
  || E'• config_importer.py — TOML-Konfiguration laden und DB-Sync\n'
  || E'• event_dispatcher.py — Event-Bus: pg_notify → WebSocket → Frontend\n'
  || E'• ghost_autonomy.py — Ghost-Autonomie: proposed_actions, thought_log\n'
  || E'• gpu_manager.py — GPU-Discovery, VRAM-Allocation, Multi-GPU-Split\n'
  || E'• gs_updater.py — GhostShell Update/OTA-System\n'
  || E'• hardware_monitor.py — psutil-basiertes Hardware-Monitoring\n'
  || E'• hardware_scanner.py — USB/Disk/GPU Hardware-Erkennung\n'
  || E'• migration_runner.py — Schema-Migration-Executor\n'
  || E'• openclaw_importer.py — OpenClaw-Daten-Import\n'
  || E'• rag_pipeline.py — RAG: Embedding + Retrieval + Generation\n'
  || E'• security_immunsystem.py — 13 Security-Subsysteme (2083 Zeilen)\n'
  || E'• security_monitor_ai.py — KI-Security-Analyse via Ghost (~600 Zeilen)\n'
  || E'• stufe4_utils.py — Nice-to-Have Features Stufe 4\n'
  || E'• synaptic_pipeline.py — Synaptische Verbindungen zwischen Ghosts\n'
  || E'• system_bridge.py — System-Info, Shutdown, Reboot\n'
  || E'• workspace_mapper.py — Workspace/Datei-Indexierung',
  ARRAY['inventory', 'bridge', 'python', 'modules'],
  'system',
  ARRAY['dbai_core', 'dbai_system', 'dbai_llm', 'dbai_security'],
  ARRAY['bridge/app_manager.py', 'bridge/browser_agent.py', 'bridge/config_importer.py', 'bridge/event_dispatcher.py', 'bridge/ghost_autonomy.py', 'bridge/gpu_manager.py', 'bridge/security_immunsystem.py', 'bridge/security_monitor_ai.py'],
  '0.15.1', 75
) ON CONFLICT (category, title) DO UPDATE SET
  content = EXCLUDED.content,
  tags = EXCLUDED.tags,
  related_modules = EXCLUDED.related_modules,
  valid_from = EXCLUDED.valid_from,
  updated_at = NOW();

INSERT INTO dbai_knowledge.system_memory
  (category, title, content, tags, author, valid_from, priority)
VALUES (
  'inventory',
  'NOTIFY/LISTEN Channels — Vollständig (v0.15.1)',
  E'Alle registrierten PostgreSQL NOTIFY-Channels:\n\n'
  || E'Ghost-System:\n'
  || E'• ghost_swap — Modellwechsel anfordern\n'
  || E'• ghost_query — KI-Anfrage über Task-Queue\n'
  || E'• ghost_gpu_migration — GPU-Umzug eines Modells\n'
  || E'• ghost_thought — Thought-Stream Update\n'
  || E'• ghost_action_proposed — Neue proposed_action\n'
  || E'• ghost_action_decided — Genehmigung/Ablehnung\n\n'
  || E'Hardware:\n'
  || E'• gpu_overheat — GPU Temperatur-Alarm\n'
  || E'• power_profile_change — Energieprofil geändert\n'
  || E'• usb_hotplug — USB-Gerät ein-/ausgesteckt\n'
  || E'• hardware_change — Hardware-Änderung erkannt\n\n'
  || E'System:\n'
  || E'• config_change — Konfiguration geändert\n'
  || E'• panic_triggered — Panic-Mode aktiviert\n'
  || E'• schema_migrated — Schema-Migration abgeschlossen\n'
  || E'• ota_update — OTA-Update verfügbar\n\n'
  || E'Security:\n'
  || E'• security_ai_task — Neue KI-Security-Analyse angefordert\n'
  || E'• security_alert — Kritische Security-Warnung\n'
  || E'• intrusion_detected — IDS-Event erkannt\n\n'
  || E'UI/Events:\n'
  || E'• sensor_data_new — Neuer Sensor-Datenpunkt\n'
  || E'• email_new — Neue E-Mail eingetroffen\n'
  || E'• app_event — App-spezifisches Event',
  ARRAY['notify', 'listen', 'channels', 'events', 'pubsub'],
  'system',
  '0.15.1', 80
) ON CONFLICT (category, title) DO UPDATE SET
  content = EXCLUDED.content,
  tags = EXCLUDED.tags,
  valid_from = EXCLUDED.valid_from,
  updated_at = NOW();


-- =============================================================================
-- 5. RELATIONSHIPS — Fehlende Beziehungen
-- =============================================================================

INSERT INTO dbai_knowledge.system_memory
  (category, title, content, tags, author, related_schemas, valid_from, priority)
VALUES (
  'relationship',
  'Security-Immunsystem ↔ Ghost-System Pipeline',
  E'Wie das Security-Immunsystem mit dem Ghost/LLM-System verbunden ist:\n\n'
  || E'Trigger-Kette:\n'
  || E'1. Event in dbai_security (intrusion, vulnerability, honeypot)\n'
  || E'2. DB-Trigger prüft Priorität/Schwere\n'
  || E'3. create_ai_task() erstellt ai_tasks-Eintrag\n'
  || E'4. pg_notify("security_ai_task") signalisiert SecurityMonitorAI\n'
  || E'5. SecurityMonitorAI baut Kontext + Prompt\n'
  || E'6. Anfrage an Ghost-Dispatcher → Security-Monitor-Ghost\n'
  || E'7. LLM analysiert, bewertet Risiko, empfiehlt Aktionen\n'
  || E'8. Auto-Response (Ban, Mitigate, Alert) wenn aktiviert\n'
  || E'9. Ergebnis in ai_tasks + ai_analysis_log\n\n'
  || E'Beteiligte Tabellen:\n'
  || E'dbai_security.* → dbai_security.ai_tasks → dbai_llm.task_queue → dbai_llm.ghost_roles → dbai_security.security_responses',
  ARRAY['security', 'ghost', 'pipeline', 'ai', 'feedback-loop'],
  'system',
  ARRAY['dbai_security', 'dbai_llm'],
  '0.15.0', 85
) ON CONFLICT (category, title) DO NOTHING;

INSERT INTO dbai_knowledge.system_memory
  (category, title, content, tags, author, related_schemas, valid_from, priority)
VALUES (
  'relationship',
  'Workshop ↔ LLM ↔ Vector Pipeline',
  E'Wie die KI-Werkstatt mit dem KI-System interagiert:\n\n'
  || E'1. User erstellt Projekt in dbai_workshop.projects\n'
  || E'2. Medien werden in media_items mit vector(384)-Embedding gespeichert\n'
  || E'3. KI-Chat in chat_history nutzt Ghost über dbai_llm.task_queue\n'
  || E'4. RAG-Pipeline sucht relevante media_items per Vektor-Ähnlichkeit\n'
  || E'5. Ghost generiert Antwort mit Medien-Kontext\n\n'
  || E'Import-Pipeline:\n'
  || E'import_jobs → Dateien laden → Embeddings generieren → media_items + dbai_vector.embeddings',
  ARRAY['workshop', 'llm', 'vector', 'rag', 'embedding'],
  'system',
  ARRAY['dbai_workshop', 'dbai_llm', 'dbai_vector'],
  '0.8.0', 55
) ON CONFLICT (category, title) DO NOTHING;

INSERT INTO dbai_knowledge.system_memory
  (category, title, content, tags, author, related_schemas, valid_from, priority)
VALUES (
  'relationship',
  'Mobile Bridge ↔ Network ↔ System Pipeline',
  E'Wie mobile Geräte ins DBAI-System integriert werden:\n\n'
  || E'1. Gerät verbindet sich über eine der 5 Dimensionen\n'
  || E'2. Registrierung in dbai_net.mobile_devices\n'
  || E'3. Sensor-Daten → dbai_net.sensor_data → pg_notify("sensor_data_new")\n'
  || E'4. PWA-Config in dbai_net.pwa_config steuert das Frontend\n'
  || E'5. DHCP-Leases tracken aktive Geräte\n\n'
  || E'5 Dimensionen:\n'
  || E'• Dim 1: PC direkt (localhost)\n'
  || E'• Dim 2: USB-C OTG (usb_gadget_config)\n'
  || E'• Dim 3: WLAN-Hotspot (hotspot_config)\n'
  || E'• Dim 4: LAN (network_interfaces)\n'
  || E'• Dim 5: Bluetooth/mDNS (mdns_config)',
  ARRAY['mobile', 'network', '5d', 'sensor', 'pwa'],
  'system',
  ARRAY['dbai_net', 'dbai_system'],
  '0.13.0', 55
) ON CONFLICT (category, title) DO NOTHING;


-- =============================================================================
-- 6. WORKFLOWS — Fehlende Abläufe
-- =============================================================================

INSERT INTO dbai_knowledge.system_memory
  (category, title, content, tags, author, valid_from, priority)
VALUES (
  'workflow',
  'Schema-Migration-Workflow',
  E'So werden neue Schema-Dateien erstellt und deployed:\n\n'
  || E'1. Neue Datei: schema/NN-beschreibung.sql\n'
  || E'2. Changelog-Eintrag: INSERT INTO dbai_knowledge.changelog (version, change_type, title, description)\n'
  || E'3. Tabellen mit IF NOT EXISTS erstellen\n'
  || E'4. Trigger mit DROP IF EXISTS + CREATE für Idempotenz\n'
  || E'5. RLS-Policies mit DROP IF EXISTS + CREATE\n'
  || E'6. Seed-Data mit ON CONFLICT DO NOTHING oder DO UPDATE\n'
  || E'7. System-Memory-Einträge für Dokumentation\n'
  || E'8. Deploy: docker exec -i postgres psql -U root -d dbai_sandbox -f - < schema/NN.sql\n'
  || E'9. Prüfung: Changelog, Tabellen, Seed-Data verifizieren\n\n'
  || E'Wichtig:\n'
  || E'• changelog braucht version + change_type + title + description\n'
  || E'• system_memory braucht category aus erlaubten 14 Werten\n'
  || E'• UNIQUE(category, title) verhindert Duplikate',
  ARRAY['workflow', 'schema', 'migration', 'deploy'],
  'system',
  '0.1.0', 80
) ON CONFLICT (category, title) DO NOTHING;

INSERT INTO dbai_knowledge.system_memory
  (category, title, content, tags, author, valid_from, priority)
VALUES (
  'workflow',
  'Security-KI-Analyse Workflow',
  E'Ablauf einer KI-gestützten Security-Analyse:\n\n'
  || E'Automatisch (Event-getriggert):\n'
  || E'1. Security-Event (Intrusion, Vulnerability, Honeypot) → Tabelle\n'
  || E'2. DB-Trigger prüft: Priorität ≤ Schwellenwert?\n'
  || E'3. create_ai_task() → ai_tasks + pg_notify("security_ai_task")\n'
  || E'4. SecurityMonitorAI empfängt → baut Kontext\n'
  || E'5. Prompt an Ghost-Dispatcher (Security-Monitor-Rolle)\n'
  || E'6. LLM-Analyse → JSON-Response (risk_level, confidence, actions)\n'
  || E'7. Auto-Response wenn erlaubt (ban_ip, mitigate, alert)\n'
  || E'8. Ergebnis + Audit-Log\n\n'
  || E'Manuell (API):\n'
  || E'POST /api/security/ai/analyze → task_type + input_data\n'
  || E'POST /api/security/ai/analyze-ip → IP-spezifische Analyse\n\n'
  || E'10 Task-Typen: threat_analysis, vuln_assessment, incident_response,\n'
  || E'baseline_audit, anomaly_detection, log_analysis, network_forensics,\n'
  || E'risk_scoring, policy_recommendation, periodic_report',
  ARRAY['workflow', 'security', 'ai', 'analysis', 'ghost'],
  'system',
  '0.15.0', 80
) ON CONFLICT (category, title) DO NOTHING;

INSERT INTO dbai_knowledge.system_memory
  (category, title, content, tags, author, valid_from, priority)
VALUES (
  'workflow',
  'OTA-Update Deployment',
  E'So wird ein System-Update über OTA verteilt:\n\n'
  || E'1. CI/CD baut Release → build_pipeline (status: success)\n'
  || E'2. Release wird in system_releases registriert (Kanal, Version, Artefakte)\n'
  || E'3. OTA-Nodes pollen auf neue Versionen für ihren Kanal\n'
  || E'4. update_jobs werden erstellt (download → applying → verifying → completed)\n'
  || E'5. Node lädt Artefakte herunter\n'
  || E'6. Schema-Migrationen werden ausgeführt (migration_history)\n'
  || E'7. Services werden neu gestartet\n'
  || E'8. Rollback bei Fehler über recovery_plans',
  ARRAY['workflow', 'ota', 'update', 'deployment', 'cicd'],
  'system',
  '0.9.0', 60
) ON CONFLICT (category, title) DO NOTHING;


-- =============================================================================
-- 7. ROADMAP — Aktueller Stand
-- =============================================================================

INSERT INTO dbai_knowledge.system_memory
  (category, title, content, tags, author, valid_from, priority)
VALUES (
  'roadmap',
  'Version 0.15.1 — Security-KI-Integration verknüpft',
  E'Was in v0.15.1 passiert ist:\n\n'
  || E'• Schema 75: Security-AI-Integration — 3 neue Tabellen + Trigger + View\n'
  || E'• Schema 76: System-Memory Vervollständigung — alle Erkenntnisse dokumentiert\n'
  || E'• bridge/security_monitor_ai.py — KI-Security-Analyse via Ghost\n'
  || E'• 20+ neue API-Endpoints für Security-AI und Subsysteme\n'
  || E'• FirewallManager.jsx erweitert: 13 → 22 Tabs inkl. KI-Monitor\n'
  || E'• Ghost-Security-Rolle mit erweitertem System-Prompt\n\n'
  || E'Nächste Schritte:\n'
  || E'• Security-Sidecar (Kali Docker) aktiv testen\n'
  || E'• Ghost-Security-Analysen im Live-Betrieb evaluieren\n'
  || E'• Multi-GPU Ghost-Deployment für parallele Analysen\n'
  || E'• Vision-Integration für Screenshot-basierte Security-Audits',
  ARRAY['roadmap', 'v0.15.1', 'security', 'ai', 'release'],
  'system',
  '0.15.1', 90
) ON CONFLICT (category, title) DO UPDATE SET
  content = EXCLUDED.content,
  tags = EXCLUDED.tags,
  valid_from = EXCLUDED.valid_from,
  updated_at = NOW();


-- =============================================================================
-- 8. IDENTITY — Systemidentität aktualisieren
-- =============================================================================

INSERT INTO dbai_knowledge.system_memory
  (category, title, content, tags, author, valid_from, priority)
VALUES (
  'identity',
  'DBAI Systemstatus v0.15.1',
  E'DBAI / TabulaOS / GhostShell — Aktueller Stand:\n\n'
  || E'• 76 Schema-Dateien, 12 Schemas, ~200+ Tabellen\n'
  || E'• 17 Python-Bridge-Module\n'
  || E'• FastAPI-Server: ~12.000+ Zeilen (web/server.py)\n'
  || E'• React-Frontend: Vite-basiert, 78+ Module\n'
  || E'• Ghost-System: 5 Rollen (sysadmin, coder, security, creative, analyst)\n'
  || E'• LLM: llama.cpp via llama-cpp-python, aktuell qwen3.5-27b-q8\n'
  || E'• Security: 4-Schichten-Immunsystem mit KI-Monitor\n'
  || E'• Mobile: 5-Dimensionen-Zugang (PC, USB-C, WLAN, LAN, BT)\n'
  || E'• CI/CD: OTA-Update-System\n'
  || E'• PostgreSQL 16 + pgvector + Append-Only + RLS\n\n'
  || E'Autor: Alexander Zuchowski\n'
  || E'Lizenz: Proprietär',
  ARRAY['identity', 'status', 'overview'],
  'system',
  '0.15.1', 95
) ON CONFLICT (category, title) DO UPDATE SET
  content = EXCLUDED.content,
  tags = EXCLUDED.tags,
  valid_from = EXCLUDED.valid_from,
  updated_at = NOW();


-- =============================================================================
-- 9. CONVENTIONS — Fehlende Konventionen
-- =============================================================================

INSERT INTO dbai_knowledge.system_memory
  (category, title, content, tags, author, valid_from, priority)
VALUES (
  'convention',
  'system_memory INSERT-Pattern',
  E'So werden system_memory-Einträge korrekt erstellt:\n\n'
  || E'Spalten (Pflicht): category, title, content\n'
  || E'Spalten (Optional): structured_data, related_modules, related_schemas, tags, valid_from, valid_until, priority, author\n\n'
  || E'Erlaubte Kategorien (14):\n'
  || E'architecture, convention, schema_map, design_pattern, relationship,\n'
  || E'workflow, inventory, roadmap, identity, operational, agent, import, feature, security\n\n'
  || E'Conflict-Handling:\n'
  || E'• ON CONFLICT (category, title) DO NOTHING — für unveränderliche Einträge\n'
  || E'• ON CONFLICT (category, title) DO UPDATE SET ... — für versionierte Einträge\n\n'
  || E'Tipps:\n'
  || E'• priority: 1-100, höher = wichtiger (90+ = kritisches Systemwissen)\n'
  || E'• author: "system" für automatisch generierte, Name für manuelle\n'
  || E'• valid_from: Version ab der gültig (z.B. "0.15.0")\n'
  || E'• valid_until: Version bis wann gültig, NULL = aktuell gültig',
  ARRAY['convention', 'system-memory', 'insert', 'pattern'],
  'system',
  '0.1.0', 85
) ON CONFLICT (category, title) DO NOTHING;

INSERT INTO dbai_knowledge.system_memory
  (category, title, content, tags, author, valid_from, priority)
VALUES (
  'convention',
  'changelog INSERT-Pattern',
  E'So werden changelog-Einträge korrekt erstellt:\n\n'
  || E'Pflichtfelder: version, change_type, title, description\n\n'
  || E'Erlaubte change_types:\n'
  || E'• feature — Neue Funktionalität\n'
  || E'• fix — Fehlerbehebung\n'
  || E'• schema — Schema-Änderung\n'
  || E'• seed — Seed-Data\n'
  || E'• security — Sicherheits-Patch\n'
  || E'• performance — Performance-Verbesserung\n\n'
  || E'Constraint: UNIQUE(version, title) — verhindert doppelte Einträge\n'
  || E'Schutz: Append-Only via Trigger — UPDATE/DELETE gesperrt\n\n'
  || E'Beispiel:\n'
  || E'INSERT INTO dbai_knowledge.changelog (version, change_type, title, description)\n'
  || E'VALUES (''0.15.0'', ''feature'', ''Security-AI'', ''Beschreibung...'');',
  ARRAY['convention', 'changelog', 'insert', 'pattern'],
  'system',
  '0.1.0', 85
) ON CONFLICT (category, title) DO NOTHING;


-- =============================================================================
-- 10. SECURITY — Ergänzende Dokumentation
-- =============================================================================

INSERT INTO dbai_knowledge.system_memory
  (category, title, content, tags, author, related_schemas, valid_from, priority)
VALUES (
  'security',
  'Security Ghost-Rolle — Konfiguration',
  E'Der Security-Monitor-Ghost ist die KI des Immunsystems.\n\n'
  || E'Rolle in dbai_llm.ghost_roles:\n'
  || E'• name: security\n'
  || E'• display_name: Security Monitor\n'
  || E'• icon: 🔒, color: #ffaa00\n'
  || E'• priority: 2, is_critical: TRUE\n'
  || E'• accessible_schemas: [dbai_security, dbai_system, dbai_core, dbai_event]\n'
  || E'• accessible_tables: 20+ Tabellen aus allen Security-Schichten\n\n'
  || E'System-Prompt definiert:\n'
  || E'• 7 Aufgabenbereiche (Bedrohungsanalyse, Vuln-Bewertung, Incident-Response, ...)\n'
  || E'• 10 Subsystem-Zugriffe\n'
  || E'• 7 Regeln (JSON-Output, Risk-Level, Auto-Response-Entscheidung, ...)\n\n'
  || E'Modellwechsel: POST /api/security/ghost-swap → dbai_llm.swap_ghost()',
  ARRAY['security', 'ghost', 'role', 'configuration'],
  'system',
  ARRAY['dbai_llm', 'dbai_security'],
  '0.15.0', 80
) ON CONFLICT (category, title) DO NOTHING;

INSERT INTO dbai_knowledge.system_memory
  (category, title, content, tags, author, valid_from, priority)
VALUES (
  'security',
  'Firewall-App — 22 Tabs Übersicht',
  E'Die Firewall-App (FirewallManager.jsx) hat 22 Tabs:\n\n'
  || E'Dashboard-Tabs:\n'
  || E'• 🛡️ Dashboard — Security-Score, offene Vulns, Bans, IDS-Events\n\n'
  || E'KI-Tabs (lila):\n'
  || E'• 🤖 KI-Monitor — Ghost-Status, Modellwechsel, manuelle Analyse, Task-History\n'
  || E'• ⚙️ KI-Config — Toggle-Switches (Auto-Ban, Auto-Mitigate), Config-Tabelle\n\n'
  || E'Firewall-Tabs:\n'
  || E'• 📜 Regeln — Firewall-Regeln CRUD + Apply\n'
  || E'• 🌐 Zonen — Netzwerk-Zonen\n'
  || E'• 🔌 Verbindungen — Aktive Verbindungen\n\n'
  || E'Security-Tabs:\n'
  || E'• 🔍 Schwachstellen — Vulnerability-Findings mit Mitigation\n'
  || E'• 🚨 IDS — Intrusion-Events mit Zeitraum-Filter\n'
  || E'• 🚫 IP-Bans — Ban/Unban mit Grund + Ablauf\n'
  || E'• 📡 Scans — Scan-Job-Übersicht\n'
  || E'• ☠️ Bedrohungen — Threat-Intelligence + IP-Score-Lookup\n'
  || E'• 📋 Baselines — CIS-Compliance mit Pass/Fail\n'
  || E'• ⚡ Responses — Auto-Response-Log\n'
  || E'• 🍯 Honeypot — Honeypot-Events\n'
  || E'• 🔐 Auth-Log — Fehlgeschlagene Logins\n\n'
  || E'Zusatz-Tabs:\n'
  || E'• 🔒 TLS — Zertifikat-Überwachung\n'
  || E'• 🐛 CVE — CVE-Tracking mit CVSS-Score\n'
  || E'• 🕳️ DNS-Sinkhole — Domain-Blocklisten CRUD\n'
  || E'• ⏱️ Rate-Limits — Rate-Limiting Übersicht\n'
  || E'• 📶 Traffic — Netzwerk-Traffic-Log\n'
  || E'• 🔑 Berechtigungen — Permission-Audit\n'
  || E'• 📊 Metriken — Aggregierte Security-Metriken',
  ARRAY['security', 'firewall', 'frontend', 'tabs', 'ui'],
  'system',
  '0.15.1', 70
) ON CONFLICT (category, title) DO NOTHING;


-- =============================================================================
-- DONE
-- =============================================================================
