# DBAI / GhostShell OS — Vollständige Schema-Wissensdatenbank

> Generiert aus der Analyse **aller 77 SQL-Schema-Dateien** (00–75) in `/home/worker/DBAI/schema/`
> Stand: Schema 75 = Version 0.15.0

---

## 1. Vollständige Liste ALLER Schemas und ihr Zweck

| # | Schema | Erstellt in | Zweck |
|---|--------|------------|-------|
| 1 | `dbai_core` | 00-extensions.sql | Objektregister, Prozesse, Konfiguration, Treiber, Browser-Migration, Workspace-Index, System-Config, Ghost-KB, Autonome Migrationen, Netzwerk-Geräte |
| 2 | `dbai_system` | 00-extensions.sql | Live-Hardware-Metriken (CPU, RAM, Disk, Temp, Network), Vacuum, Locks, USB-Devices, Hotspot, Immutable-FS, Anomalie-Erkennung, Sandboxing, Firewall, OTA-Updates, CI/CD, Ghost-Browser |
| 3 | `dbai_event` | 00-extensions.sql | Append-Only Event-Bus (System, Keyboard, Network, Power) |
| 4 | `dbai_vector` | 00-extensions.sql | Vektor-Gedächtnis (pgvector, HNSW), Synaptic Memory Pipeline |
| 5 | `dbai_journal` | 00-extensions.sql | WAL Journal — Change-Log, Event-Log, System-Snapshots (append-only) |
| 6 | `dbai_panic` | 00-extensions.sql | Emergency-Modus: Boot-Config, Repair-Scripts, Panic-Log |
| 7 | `dbai_llm` | 00-extensions.sql | LLM-Integration: Modelle, Conversations, Task-Queue, RAG-Pipeline, Ghost-Rollen, Agent-Instanzen, Lern-Einträge, Vision, Multi-GPU, Distributed Ghosts, Marketplace |
| 8 | `dbai_knowledge` | 11-knowledge-library.sql | Wissens-Bibliothek: Module-Registry, Changelog, ADRs, Glossar, Known-Issues, Build-Log, System-Memory, Agent-Sessions |
| 9 | `dbai_ui` | 16-desktop-ui.sql | Desktop-UI: Users, Sessions, Themes, Apps, Windows, Notifications, Desktop-Config, Desktop-Nodes, Tab-Instanzen, Terminal-Sessions, i18n, App-Settings |
| 10 | `dbai_workshop` | 28-ai-workshop.sql | KI-Werkstatt: Projekte, Medien, Sammlungen, Smart-Devices, Custom-Tabellen |
| 11 | `dbai_net` | 68-mobile-bridge.sql | Mobile Bridge: Netzwerk-Interfaces, Mobile-Devices, Sensor-Pipeline, PWA, Hotspot, USB-Gadget, mDNS, Connection-Sessions, Boot-Dimensionen |
| 12 | `dbai_security` | 73-security-immunsystem.sql | Sicherheits-Immunsystem: Scan-Jobs, Vulnerabilities, IDS/IPS, Threat-Intelligence, Fail2Ban, TLS-Certs, CVE-Tracking, Honeypots, DNS-Sinkhole, AI-Integration |
| 13 | `dbai_ops` | 67-sandbox-hotfix.sql | Kompatibilitäts-Schema (View auf dbai_knowledge.changelog) |

### Rollen (5+1)

| Rolle | Rechte | Erstellt in |
|-------|--------|------------|
| `dbai_system` | Superuser-Zugriff auf alles | 00 |
| `dbai_monitor` | Read-Only Monitoring | 00 |
| `dbai_llm` | Eigene LLM-Daten | 00 |
| `dbai_recovery` | Panic + Journal Zugriff | 00 |
| `dbai_runtime` | Web-Server-Layer (API) | 27 |

### Extensions

| Extension | Zweck |
|-----------|-------|
| `pgvector` | Vektor-Suche (1536-dimensional) |
| `uuid-ossp` | UUID v4 Generierung |
| `pgcrypto` | Kryptographische Funktionen |
| `pg_stat_statements` | Query-Performance-Tracking |
| `pg_cron` | Geplante DB-Jobs |
| `pg_trgm` | Trigramm-Ähnlichkeitssuche |

---

## 2. Vollständige Liste ALLER Tabellen pro Schema

### dbai_core (Schema 01, 33, 57, 67-sandbox, 69)
| Tabelle | Schema-File | Beschreibung |
|---------|------------|-------------|
| `objects` | 01 | UUID-basiertes Objektregister (alle Entitäten) |
| `processes` | 01 | Laufende System-Prozesse |
| `config` | 01 | Key-Value Konfigurationspaare |
| `drivers` | 01 | Geladene Treiber |
| `browser_profiles` | 33 | Importierte Browser-Profile (Chrome/Firefox/etc.) |
| `browser_bookmarks` | 33 | Importierte Lesezeichen |
| `browser_history` | 33 | Importierter Browserverlauf |
| `browser_passwords` | 33 | Importierte Passwörter (AES-256 verschlüsselt) |
| `ghost_knowledge_base` | 33 | Wissensbasis aus Browser-Daten + Vectorsuche |
| `system_config` | 33 | Importierte Systemkonfiguration (/etc, ~/.config) |
| `wifi_profiles` | 33 | Importierte WLAN-Profile |
| `user_permissions` | 33 | Importierte Linux-User-Rechte |
| `workspace_index` | 33 | Dateibaum-Index (ohne Kopie) |
| `autonomous_migrations` | 69 | Ghost-generierte SQL-Migrationen |
| `migration_audit_log` | 69 | Audit-Log für autonome Migrationen |
| `network_devices` | 67-sandbox | Erkannte Netzwerk-Geräte mit Web-UI |

### dbai_system (Schema 02, 09, 10, 18, 19, 34, 36, 56)
| Tabelle | Schema-File | Beschreibung |
|---------|------------|-------------|
| `cpu` | 02 | Live CPU-Metriken |
| `memory` | 02 | Live RAM-Metriken |
| `disk` | 02 | Live Disk-Metriken |
| `temperature` | 02 | Temperatur-Sensoren |
| `network` | 02 | Netzwerk-Traffic |
| `vacuum_log` | 09 | Vacuum-Protokoll |
| `vacuum_config` | 09 | Smart-Vacuum-Konfiguration |
| `lock_registry` | 10 | Distributed-Lock-System |
| `hardware_inventory` | 18 | Hardware-Inventar |
| `gpu_devices` | 18 | GPU-Karten |
| `gpu_vram_map` | 18 | VRAM-Allokation |
| `cpu_cores` | 18 | CPU-Kern-Details |
| `memory_map` | 18 | RAM-Module |
| `storage_health` | 18 | SMART-Festplattengesundheit |
| `fan_control` | 18 | Lüftersteuerung |
| `power_profiles` | 18 | Energieprofile |
| `boot_config` | 19 | Boot-Konfiguration |
| `neural_bridge_config` | 19 | Neural-Bridge-Einstellungen |
| `driver_registry` | 19 | Treiber-Register |
| `system_capabilities` | 19 | System-Fähigkeiten |
| `ghost_benchmarks` | 19 | Ghost-Performance-Benchmarks |
| `usb_devices` | 34 | USB-Geräte-Erkennung |
| `usb_flash_jobs` | 34 | USB-Flash-Aufträge |
| `hotspot_config` | 34 | WLAN-Hotspot-Konfiguration |
| `immutable_config` | 34 | Immutable-FS-Einstellungen |
| `fs_snapshots` | 34 | Dateisystem-Snapshots |
| `anomaly_models` | 34 | ML-Anomalie-Modelle |
| `anomaly_detections` | 34 | Erkannte Anomalien |
| `metrics_history` | 34 | Metriken-Zeitreihe |
| `sandbox_profiles` | 34 | Sandbox-Konfiguration |
| `sandboxed_apps` | 34 | Laufende Sandboxed-Apps |
| `firewall_rules` | 34 | iptables/nftables Regeln |
| `firewall_zones` | 34 | Firewall-Zonen |
| `update_channels` | 36 | OTA Update-Kanäle (stable/beta/nightly/dev) |
| `system_releases` | 36 | Releases/Versionen |
| `migration_history` | 36 | Migration-Tracking |
| `ota_nodes` | 36 | Verbundene Update-Empfänger |
| `build_pipeline` | 36 | CI/CD Build-Log |
| `update_jobs` | 36 | OTA-Update-Aufträge |
| `ghost_browser_tasks` | 56 | Ghost-Browser-Aufträge |
| `ghost_browser_steps` | 56 | Browser-Schritt-Protokoll |
| `ghost_browser_presets` | 56 | Gespeicherte Browser-Workflows |

### dbai_event (Schema 03)
| Tabelle | Schema-File | Beschreibung |
|---------|------------|-------------|
| `events` | 03 | Append-Only Event-Bus |
| `keyboard` | 03 | Keyboard-Events |
| `network` | 03 | Netzwerk-Events |
| `power` | 03 | Power-Events |

### dbai_vector (Schema 04, 33)
| Tabelle | Schema-File | Beschreibung |
|---------|------------|-------------|
| `memories` | 04 | Langzeit-Vektor-Gedächtnis (1536-dim) |
| `knowledge_edges` | 04 | Wissens-Verknüpfungen |
| `synaptic_memory` | 33 | Echtzeit-Synaptic-Memory (Kurzzeitgedächtnis) |

### dbai_journal (Schema 05)
| Tabelle | Schema-File | Beschreibung |
|---------|------------|-------------|
| `change_log` | 05 | Append-Only Änderungslog |
| `event_log` | 05 | Event-Protokoll |
| `system_snapshots` | 05 | System-Zustandsabbilder |

### dbai_panic (Schema 06)
| Tabelle | Schema-File | Beschreibung |
|---------|------------|-------------|
| `emergency_drivers` | 06 | Notfall-Treiber |
| `boot_config` | 06 | Notfall-Boot-Config |
| `repair_scripts` | 06 | Reparatur-Skripte |
| `panic_log` | 06 | Panik-Protokoll |

### dbai_llm (Schema 08, 15, 33, 58, 67-sandbox, 69)
| Tabelle | Schema-File | Beschreibung |
|---------|------------|-------------|
| `models` / `ghost_models` | 08 | Registrierte LLM-Modelle |
| `conversations` | 08 | Chat-Konversationen |
| `task_queue` | 08 | LLM Task-Queue |
| `ghost_roles` | 15 | Ghost-Rollen (sysadmin, coder, security, etc.) |
| `active_ghosts` | 15 | Aktive Ghost-Instanzen |
| `ghost_history` | 15 | Ghost-Wechsel-Historie |
| `ghost_compatibility` | 15 | Modell-Kompatibilitäten |
| `llm_providers` | 29 | 12 LLM-Provider (NVIDIA, OpenAI, Anthropic, etc.) |
| `rag_sources` | 33 | RAG-Quellen-Registry |
| `rag_chunks` | 33 | RAG-Text-Chunks mit Vektoren |
| `rag_query_log` | 33 | RAG-Abfrage-Protokoll |
| `agent_instances` | 58 | Laufende Agent-Instanzen |
| `learning_entries` | 67-sandbox | Benutzer-Lernprofil |
| `scheduled_jobs` | 67-sandbox | Geplante Agent-Jobs (Cron) |
| `agent_tasks` | 67-sandbox | Agent-Aufgaben |
| `gpu_split_configs` | 69 | Multi-GPU Konfigurationen |
| `parallel_inference_sessions` | 69 | Parallele Inferenz-Sessions |
| `gpu_sync_events` | 69 | GPU-Synchronisations-Events |
| `vision_models` | 69 | Vision-Modelle (CLIP, etc.) |
| `vision_tasks` | 69 | Vision-Aufgaben |
| `vision_detections` | 69 | Vision-Erkennungen |
| `ghost_nodes` | 69 | Distributed Ghost Nodes |
| `node_heartbeats` | 69 | Node-Heartbeats |
| `distributed_tasks` | 69 | Verteilte Aufgaben |
| `model_replicas` | 69 | Modell-Replikate |
| `marketplace_catalog` | 69 | Modell-Marketplace-Katalog |
| `model_downloads` | 69 | Download-Tracking |
| `model_reviews` | 69 | Modell-Bewertungen |

### dbai_knowledge (Schema 11, 12, 24)
| Tabelle | Schema-File | Beschreibung |
|---------|------------|-------------|
| `module_registry` | 11 | Datei-Register (alle Projekt-Dateien) |
| `module_dependencies` | 11 | Abhängigkeiten zwischen Modulen |
| `changelog` | 11 | **Versions-Changelog** (append-only) |
| `architecture_decisions` | 11 | Architecture Decision Records (ADR) |
| `system_glossary` | 11 | Begriffsklärungen |
| `known_issues` | 12 | Bekannte Probleme + Workarounds |
| `build_log` | 11 | Build-Dokumentation |
| `error_patterns` | 12 | Bekannte Fehlermuster |
| `runbooks` | 12 | Runbook-Prozeduren |
| `error_log` | 12 | Fehler-Protokoll |
| `error_resolutions` | 12 | Fehler-Lösungen |
| `system_memory` | 24 | **Langzeit-Wissens-Speicher** (KEY TABLE) |
| `agent_sessions` | 24 | Dokumentierte Agent-Sessions |

### dbai_ui (Schema 16, 30, 34, 39, 52)
| Tabelle | Schema-File | Beschreibung |
|---------|------------|-------------|
| `users` | 16 | Benutzer |
| `sessions` | 16 | Login-Sessions |
| `themes` | 16 | UI-Themes (ghost-dark, matrix, frost) |
| `desktop_config` | 16 | Desktop-Konfiguration pro User |
| `apps` | 16 | App-Register |
| `windows` | 16 | Offene Fenster |
| `notifications` | 16 | Desktop-Benachrichtigungen |
| `desktop_nodes` | 30 | SVG-basierte Netzwerk-Knoten |
| `desktop_scene` | 30 | Szenen-Konfiguration |
| `terminal_sessions` | 34 | Terminal-Sessions |
| `terminal_history` | 34 | Terminal-Befehlshistorie |
| `i18n_translations` | 34 | Übersetzungen |
| `i18n_locales` | 34 | Verfügbare Sprachen |
| `app_user_settings` | 39 | User-spezifische App-Einstellungen |
| `tab_instances` | 52 | Browser-Tab-Isolation (Virtual Desktops) |

### dbai_workshop (Schema 28, 38)
| Tabelle | Schema-File | Beschreibung |
|---------|------------|-------------|
| `projects` | 28 | KI-Werkstatt-Projekte |
| `media_items` | 28 | Medien-Dateien |
| `collections` | 28 | Sammlungen |
| `collection_items` | 28 | Sammlungs-Einträge |
| `smart_devices` | 28 | IoT Smart-Devices |
| `custom_tables` | 38 | Benutzerdefinierte Tabellen-Schemata |
| `custom_rows` | 38 | Benutzerdefinierte Datenzeilen |

### dbai_net (Schema 68)
| Tabelle | Schema-File | Beschreibung |
|---------|------------|-------------|
| `network_interfaces` | 68 | Netzwerk-Interfaces (USB-Gadget, WLAN, etc.) |
| `mobile_devices` | 68 | Registrierte Smartphones/Tablets |
| `sensor_data` | 68 | Sensor-Pipeline (GPS, Kamera, Audio → DB) |
| `pwa_config` | 68 | PWA-Konfiguration |
| `hotspot_config` | 68 | Hotspot-Einstellungen |
| `dhcp_leases` | 68 | DHCP-Leases |
| `usb_gadget_config` | 68 | USB-Gadget-Konfiguration |
| `mdns_config` | 68 | mDNS/Avahi-Konfiguration |
| `connection_sessions` | 68 | Aktive Verbindungen über alle Dimensionen |
| `boot_dimensions` | 68 | 5 Boot-Dimensionen |
| `hardware_profiles` | 68 | Hardware-Profile |

### dbai_security (Schema 73, 75)
| Tabelle | Schema-File | Beschreibung |
|---------|------------|-------------|
| `scan_jobs` | 73 | Sicherheits-Scan-Aufträge |
| `vulnerability_findings` | 73 | Gefundene Schwachstellen |
| `intrusion_events` | 73 | IDS/IPS Events |
| `threat_intelligence` | 73 | Threat-Intelligence-Feeds |
| `failed_auth_log` | 73 | Fehlgeschlagene Logins |
| `ip_bans` | 73 | Gesperrte IPs (fail2ban) |
| `network_traffic_log` | 73 | Netzwerk-Traffic-Log |
| `security_responses` | 73 | Automatische Gegenmaßnahmen |
| `tls_certificates` | 73 | TLS-Zertifikate |
| `security_baselines` | 73 | Sicherheits-Baselines |
| `cve_tracking` | 73 | CVE-Datenbank |
| `permission_audit` | 73 | Berechtigungs-Audit |
| `security_metrics` | 73 | Sicherheits-Metriken |
| `honeypot_events` | 73 | Honeypot-Ereignisse |
| `rate_limits` | 73 | Rate-Limiting-Konfiguration |
| `dns_sinkhole` | 73 | DNS-Sinkhole (Malware-Domains) |
| `ai_tasks` | 75 | Security-AI-Aufgaben |
| `ai_config` | 75 | AI-Security-Konfiguration |
| `ai_analysis_log` | 75 | AI-Analyse-Protokoll |

### dbai_ops (Schema 67-sandbox)
| Tabelle/View | Schema-File | Beschreibung |
|---------|------------|-------------|
| `changelog` (VIEW) | 67-sandbox | Kompatibilitäts-View → dbai_knowledge.changelog |

### Sonstige (Schema 07, 27)
| Objekt | Schema-File | Beschreibung |
|---------|------------|-------------|
| `dbai_core.audit_log` | 07 | Append-Only Audit-Log (RLS) |
| `dbai_core.schema_fingerprints` | 27 | Schema-Fingerprints (Immutability) |
| `dbai_core.immutable_registry` | 27 | Immutable-Registry |

---

## 3. Alle system_memory Kategorien

### Aktueller CHECK-Constraint (Stand Schema 74)

```sql
CHECK (category = ANY (ARRAY[
    'architecture', 'convention', 'schema_map', 'design_pattern',
    'relationship', 'workflow', 'inventory', 'roadmap', 'identity',
    'operational', 'agent', 'import', 'feature', 'security'
]))
```

### Kategorie-Beschreibungen

| Kategorie | Beschreibung | Erstmals |
|-----------|-------------|----------|
| `architecture` | Systemarchitektur, Technologie-Entscheidungen, Feature-Architektur | 25 |
| `convention` | Namenskonventionen, Coding-Standards, Dateinamenmuster | 25 |
| `schema_map` | Dokumentation pro Schema (Tabellen, Zweck, Abhängigkeiten) | 25 |
| `design_pattern` | Entwurfsmuster (Append-Only, NOTIFY/LISTEN, Hot-Swap) | 25 |
| `relationship` | Pipeline-Verknüpfungen (Ghost↔Hardware, Autonomy↔Safety) | 25 |
| `workflow` | Arbeitsabläufe (Feature hinzufügen, Seed-Data, Tests) | 25 |
| `inventory` | Technologie-Stacks (DB, Python, Frontend, Bridge-Dateien) | 25 |
| `roadmap` | Geplante Features und nächste Schritte | 25 |
| `identity` | Was ist DBAI/TabulaOS/GhostShell, Versionshistorie | 25 |
| `operational` | Betriebswissen (Server-Neustart, DB-Diagnose, GRUB, Kiosk) | 25 |
| `agent` | Agent-Session-Erkenntnisse | 67-sandbox |
| `import` | Import-Ergebnisse (Browser, Config) | 67-sandbox |
| `feature` | Feature-Dokumentation (Ghost Browser, etc.) | 56 |
| `security` | Sicherheitswissen (Immunsystem, Threat-Intelligence) | 74 |

### Historische Constraint-Erweiterungen

1. **Schema 24**: Initial 10 Kategorien (architecture → operational)
2. **Schema 67-sandbox**: +`agent`, +`import`
3. **Schema 74**: +`feature`, +`security`

---

## 4. Exakte Spaltenstruktur: system_memory

```sql
CREATE TABLE dbai_knowledge.system_memory (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category        TEXT NOT NULL,               -- CHECK: 14 erlaubte Werte (s. oben)
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,
    structured_data JSONB DEFAULT '{}'::JSONB,
    related_modules TEXT[] DEFAULT '{}',          -- Referenzierte Datei-Pfade
    related_schemas TEXT[] DEFAULT '{}',          -- Referenzierte DB-Schemas
    tags            TEXT[] DEFAULT '{}',
    valid_from      TEXT NOT NULL DEFAULT '0.1.0', -- Gültig ab Version
    valid_until     TEXT,                         -- NULL = noch gültig
    priority        INTEGER NOT NULL DEFAULT 50,  -- 1 (niedrig) bis 100 (hoch)
    author          TEXT NOT NULL DEFAULT 'system',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (category, title)
);
```

**Indizes:**
- `UNIQUE (category, title)` — Deduplizierung
- GIN auf `tags` für Tag-Suche

**Trigger:**
- `update_timestamp()` auf UPDATE → setzt `updated_at`

**Key-Funktionen (Schema 24):**
- `remember(category, title, content, ...)` — UPSERT in system_memory
- `recall(search_text)` — Volltextsuche über content + title
- `recall_by_category(category)` — Alle Einträge einer Kategorie
- `recall_by_tags(tags[])` — Suche über Tags

---

## 5. Exakte Spaltenstruktur: changelog

```sql
CREATE TABLE dbai_knowledge.changelog (
    id              BIGSERIAL PRIMARY KEY,
    version         TEXT NOT NULL,
    change_type     TEXT NOT NULL,
    title           TEXT NOT NULL,
    description     TEXT NOT NULL,
    affected_modules UUID[] DEFAULT '{}',
    affected_files  TEXT[] DEFAULT '{}',
    author          TEXT NOT NULL DEFAULT 'system',
    rollback_sql    TEXT,
    rollback_steps  TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**CHECK-Constraint (change_type):**
```
'feature', 'fix', 'refactor', 'schema', 'security', 'performance', 'docs', 'breaking'
```

**Schutz:** Append-Only Trigger (`trg_protect_changelog`) — kein UPDATE/DELETE erlaubt.

**UNIQUE-Constraint (ab Schema 72):**
```sql
UNIQUE (version, title)
```

---

## 6. Wissensbereiche: Was ist NOCH NICHT dokumentiert?

### Schemas ohne eigenen schema_map-Eintrag in system_memory
- `dbai_workshop` (erstellt in 28, kein Schema-Map-Eintrag im Seed 25)
- `dbai_net` (erstellt in 68)
- `dbai_security` (erstellt in 73)
- `dbai_ops` (Kompatibilitäts-Schema, erstellt in 67-sandbox)

### Features ohne system_memory-Dokumentation
- Autonome Migrationen (Schema 69, Feature 1)
- Multi-GPU Parallel Inference (Schema 69, Feature 2)
- Vision Integration (Schema 69, Feature 3)
- Distributed Ghosts (Schema 69, Feature 4)
- Model Marketplace (Schema 69, Feature 5)
- Detailed Security-Immunsystem Baselines/CVE-Tracking (73/74 haben Tabellen, aber nur grobe system_memory)
- Hardware-Profiles für mobile Sticks (68)

### Noch offene known_issues (aus Schema 32, 31)
- pgvector nicht in Standard-Repos (AUR-Problem)
- NVIDIA-Treiber optional aber nicht erkannt
- Ghost Avatar wird nicht im Backend persistiert
- SetupWizard: Kein Cancel-Button bei Installation

### Fehlende Seed-Daten
- dbai_workshop-Tabellen haben keine Seed-Data
- dbai_security: Baselines und CVEs sind initial leer (nur DNS-Sinkhole + Scan-Jobs geseedet)
- dbai_net: Keine Seed-Daten für boot_dimensions, hardware_profiles

---

## 7. Organisationsmuster

### Schema-Datei-Naming-Konvention
```
{NN}-{beschreibung}.sql
```
- **00–14**: Core-Infrastruktur (Extensions, Tabellen, RLS, Events, Vectors, Journal, LLM, Knowledge)
- **15–20**: Ghost-System + Desktop/Hardware + Seed-Daten
- **21–29**: Ökosystem-Erweiterungen (OpenClaw, Autonomie, Apps, Memory, Immutability, Workshop, LLM-Provider)
- **30–42**: Stufe 1–4 Features + CICD + App-Settings + Erste Wissensdokumentation
- **43–55**: Patch-Releases v0.10.0–v0.10.10 (Bugfixes, Knowledge-Sessions)
- **56–66**: v0.11.0–v0.12.x (Ghost Browser, Compat-Layers, Agent-Instanzen, Process-Merge, LLM-Manager, USB-Boot, Remote-Access)
- **67–72**: Sandbox-Hotfix + Mobile-Bridge v0.13.0 + Advanced Features v0.14.x + Hardening
- **73–75**: Security-Immunsystem v0.15.0

### Datenbank-Design-Patterns

| Pattern | Beschreibung | Beispiel |
|---------|-------------|---------|
| **Append-Only** | Tabellen mit Trigger-Schutz gegen UPDATE/DELETE | changelog, event_log, audit_log |
| **NOTIFY/LISTEN** | Asynchrone Events via PostgreSQL | dispatch_event(), ghost swap |
| **RLS (Row-Level Security)** | Pro-Rolle Zugriffskontrolle | Schema 07 auf ALLEN Tabellen |
| **UPSERT (ON CONFLICT)** | Idempotente Inserts | system_memory, apps, configs |
| **Hot-Swap** | Modelle im laufenden Betrieb wechseln | Ghost-Modelle via swap_ghost() |
| **Vektor-Suche** | pgvector + HNSW für Ähnlichkeitssuche | memories, synaptic_memory, RAG |
| **JSON-Schema-UI** | DB-gesteuerte Settings-Formulare | app_user_settings + settings_schema |
| **Immutable Registry** | Schutz gegen Schema-Manipulation | schema_fingerprints |
| **Synaptic Consolidation** | Kurzzeitgedächtnis → Langzeitgedächtnis | consolidate_memories() |
| **Safety-First** | proposed_actions mit Genehmigung | ghost_autonomy |

### Versions-Verlauf (aus Changelogs)

| Version | Beschreibung | Schema-Range |
|---------|-------------|-------------|
| 0.1.0–0.7.0 | Initiale Entwicklung, alle Core-Schemas | 00–25 |
| 0.8.0 | Stufe 1: Bare-Metal Boot + Stufe 2: Apple-Moment UX | 31 |
| 0.8.1 | Diagnose-Session: Server-Ausfall | 32 |
| 0.9.0 | Per-App Settings System | 39–41 |
| 0.10.0–0.10.10 | 14+ neue Features, Notifications, Keyboard Shortcuts, CRUD, Bugfixes | 42–55 |
| 0.11.0 | Ghost Browser (Playwright), Tab-Isolation | 56, 52–53 |
| 0.12.0 | Process-Merge, LLM-Manager, USB 3-Boot, Remote Access, Ghost-LLM-Merge | 60–66 |
| 0.12.1 | USB Discovery Fix | 64 |
| 0.13.0 | Mobile Bridge (5 Dimensionen), dbai_net Schema | 68 |
| 0.14.0 | 5 Advanced Features (Autonomous Coding, Multi-GPU, Vision, Distributed, Marketplace) | 69 |
| 0.14.1–0.14.3 | Code Quality, Security Hardening, Dedup-Constraints | 70–72 |
| 0.15.0 | Security-Immunsystem, dbai_security Schema, AI-Integration | 73–75 |

### Architektur-Schichten

```
┌───────────────────────────────────────────────────────────┐
│  Frontend (React/Vite, Port 8420/3000, Cyberpunk-Theme)   │
├───────────────────────────────────────────────────────────┤
│  Web-Server (FastAPI/Uvicorn, Port 3000)                  │
├───────────────────────────────────────────────────────────┤
│  Bridge-Layer (Python: ghost_autonomy, hardware_monitor,  │
│                browser_agent, rag_pipeline, ...)          │
├───────────────────────────────────────────────────────────┤
│  PostgreSQL 16 + pgvector                                 │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌──────┐ ┌──────────┐ │
│  │  core  │ │ system │ │  llm   │ │  ui  │ │knowledge │ │
│  ├────────┤ ├────────┤ ├────────┤ ├──────┤ ├──────────┤ │
│  │ event  │ │ vector │ │journal │ │panic │ │ workshop │ │
│  ├────────┤ ├────────┤ ├────────┤ ├──────┤ ├──────────┤ │
│  │  net   │ │security│ │  ops   │ │      │ │          │ │
│  └────────┘ └────────┘ └────────┘ └──────┘ └──────────┘ │
├───────────────────────────────────────────────────────────┤
│  Bare-Metal Linux (systemd, GRUB, Chromium-Kiosk)         │
└───────────────────────────────────────────────────────────┘
```

### Tabellen-Count

| Schema | Tabellen | Views |
|--------|---------|-------|
| dbai_core | ~16 | vw_workspace_stats, users (VIEW in 57) |
| dbai_system | ~38 | current_status |
| dbai_event | 4 | — |
| dbai_vector | 3 | — |
| dbai_journal | 3 | — |
| dbai_panic | 4 | — |
| dbai_llm | ~25 | vw_active_ghosts |
| dbai_knowledge | ~13 | vw_knowledge_summary, vw_module_status |
| dbai_ui | ~15 | translations (VIEW) |
| dbai_workshop | 7 | — |
| dbai_net | 11 | — |
| dbai_security | 19 | — |
| dbai_ops | 0 | changelog (VIEW) |
| **TOTAL** | **~158** | **~6** |

---

## Anhang: Dateiliste

| # | Datei | Zeilen | Typ |
|---|-------|--------|-----|
| 00 | 00-extensions.sql | 100 | Core: Schemas, Rollen, Extensions |
| 01 | 01-core-tables.sql | ? | Core-Tabellen |
| 02 | 02-system-tables.sql | ? | System-Metriken |
| 03 | 03-event-tables.sql | ? | Event-System |
| 04 | 04-vector-tables.sql | ? | Vektor-Gedächtnis |
| 05 | 05-wal-journal.sql | ? | WAL Journal |
| 06 | 06-panic-schema.sql | ? | Panic-Modus |
| 07 | 07-row-level-security.sql | ? | RLS + Audit-Log |
| 08 | 08-llm-integration.sql | ? | LLM-Integration |
| 09 | 09-vacuum-schedule.sql | ? | Smart-Vacuum |
| 10 | 10-sync-primitives.sql | ? | Locks/Deadlocks |
| 11 | 11-knowledge-library.sql | 446 | Knowledge-System |
| 12 | 12-error-patterns.sql | ? | Fehlermuster |
| 13 | 13-seed-data.sql | 1492 | Massive Seed-Daten |
| 14 | 14-self-healing.sql | ? | Health-Checks, Alerts |
| 15 | 15-ghost-system.sql | ? | Ghost-System |
| 16 | 16-desktop-ui.sql | ? | Desktop-UI |
| 17 | 17-ghost-desktop-seed.sql | ? | Ghost+Desktop Seed |
| 18 | 18-hardware-abstraction.sql | ? | Hardware-Abstraction |
| 19 | 19-neural-bridge.sql | ? | Neural-Bridge |
| 20 | 20-hw-seed-data.sql | ? | Hardware-Seed |
| 21 | 21-openclaw-bridge.sql | ? | OpenClaw |
| 22 | 22-ghost-autonomy.sql | ? | Ghost-Autonomie |
| 23 | 23-app-ecosystem.sql | ? | App-Ökosystem |
| 24 | 24-system-memory.sql | ? | **system_memory** |
| 25 | 25-system-memory-seed.sql | 580 | Memory-Seed |
| 26 | 26-new-apps-seed.sql | ? | App-Registrierung |
| 27 | 27-immutability-enforcement.sql | 926 | Immutability |
| 28 | 28-ai-workshop.sql | 453 | KI-Werkstatt |
| 29 | 29-llm-providers.sql | ? | LLM-Provider |
| 29 | 29-new-apps-registration.sql | ? | SQL Explorer + WebFrame |
| 30 | 30-desktop-nodes.sql | 66 | Desktop-SVG-Knoten |
| 31 | 31-stufe1-stufe2-seed.sql | 585 | Bare-Metal + UX Seed |
| 32 | 32-diagnostic-session-seed.sql | 251 | Diagnose-Session |
| 33 | 33-stufe3-deep-integration.sql | 467 | Browser-Migration, Config Import, Workspace, Synaptic, RAG |
| 34 | 34-stufe4-nice-to-have.sql | 381 | USB, Hotspot, Immutable-FS, i18n, Anomalie, Sandbox, Firewall, Terminal |
| 35 | 35-stufe3-stufe4-seed.sql | 193 | Stufe 3+4 Seed |
| 36 | 36-cicd-ota-system.sql | 234 | CI/CD + OTA |
| 37 | 37-cicd-seed.sql | 30 | CI/CD Seed |
| 38 | 38-workshop-custom-tables.sql | 39 | Custom-DB-Tabellen |
| 39 | 39-app-settings.sql | 179 | App-Settings-System |
| 40 | 40-app-settings-seed.sql | 1527 | Settings für 16 Apps |
| 41 | 41-knowledge-session-v0.9.0.sql | 679 | v0.9.0 Dokumentation |
| 42 | 42-remaining-app-settings-seed.sql | 91 | Settings für 13 weitere Apps |
| 43 | 43-knowledge-session-v0.10.0.sql | 80 | v0.10.0 Dokumentation |
| 44 | 44-register-missing-apps.sql | 88 | NetworkScanner + NodeManager |
| 45 | 45-knowledge-session-v0.10.1.sql | 206 | v0.10.1 Bugfixes |
| 46 | 46-knowledge-session-v0.10.2.sql | 149 | Schema-Idempotenz |
| 47 | 47-knowledge-session-v0.10.3.sql | 49 | Frontend-Recovery |
| 48 | 48-knowledge-session-v0.10.4.sql | 78 | Export-Fix |
| 49 | 49-knowledge-session-v0.10.5.sql | 83 | Import-Fixes, Error Boundary |
| 50 | 50-knowledge-session-v0.10.6.sql | 44 | Power/Reboot Docker |
| 51 | 51-knowledge-session-v0.10.7.sql | 132 | Ghost Mail E-Mail |
| 52 | 52-tab-isolation.sql | 221 | Tab-Isolation (Virtual Desktops) |
| 53 | 53-knowledge-session-v0.10.8.sql | 115 | Tab-Isolation Doku |
| 54 | 54-knowledge-session-v0.10.9.sql | 132 | System Monitor Fix |
| 55 | 55-knowledge-session-v0.10.10.sql | 115 | Optional Chaining Fix |
| 56 | 56-ghost-browser.sql | 180 | Ghost Browser (Playwright) |
| 57 | 57-compat-dbai-core-users.sql | 73 | Compat-View users |
| 58 | 58-agent-instances.sql | 36 | Agent-Instanzen-Tabelle |
| 59 | 59-add-user-columns.sql | 15 | User-Spalten ergänzt |
| 60 | 60-version-0.12.0-process-merge.sql | 56 | Process-Manager → SystemMonitor |
| 61 | 61-llm-manager-v0.12.0.sql | 72 | LLM-Manager Doku |
| 62 | 62-usb-3boot-stick.sql | 33 | USB 3-Boot Doku |
| 63 | 63-remote-access-app.sql | 46 | Remote-Access-App |
| 64 | 64-usb-discovery-fix.sql | 103 | USB Discovery Bugfix |
| 65 | 65-ghost-llm-manager.sql | 81 | Ghost+LLM Manager Merge |
| 66 | 66-ghost-chat-llm-link.sql | 60 | Ghost Chat ↔ LLM Link |
| 67 | 67-gpu-import-fix.sql | 43 | GPU-Erkennung Fix |
| 67 | 67-sandbox-hotfix.sql | 819 | Sandbox: 9 Bugfixes, neue Tabellen, Constraint-Updates |
| 68 | 68-mobile-bridge.sql | 827 | Mobile Bridge v0.13.0 (dbai_net) |
| 69 | 69-advanced-features.sql | 777 | 5 Advanced Features v0.14.0 |
| 70 | 70-v0.14.1-code-quality.sql | 190 | 14 Code-Quality-Fixes |
| 71 | 71-v0.14.2-hardening.sql | 363 | RLS + Vacuum + Security |
| 72 | 72-v0.14.3-dedup-constraints.sql | 144 | UNIQUE-Constraints |
| 73 | 73-security-immunsystem.sql | 966 | Security-Immunsystem (dbai_security) |
| 74 | 74-security-immunsystem-seed.sql | 197 | Security-Seed |
| 75 | 75-security-ai-integration.sql | 427 | Security-AI-Integration |

**Gesamt: 77 Dateien, ~12.000+ Zeilen SQL**
