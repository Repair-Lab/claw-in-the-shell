# DBAI Changelog

Alle wesentlichen Änderungen am Projekt werden hier dokumentiert.

---

## [v0.10.0] — 2025-01-XX

### ✨ Neue Features

#### System-Features
- **Notification-System**: `NotificationProvider` + `useNotification` Hook mit Toast-Benachrichtigungen (success/error/warning/info), Auto-Dismiss, Bottom-Right-Positionierung
- **Keyboard Shortcuts**: Globaler Shortcut-Handler (`Ctrl+K` Spotlight, `Ctrl+T` Terminal, `Ctrl+,` Settings, `Ctrl+L` Lock, `Ctrl+M` Monitor, `Escape` Schließen)
- **SpotlightSearch**: App-Launcher mit Fuzzy-Suche, Keyboard-Navigation, Quick-Actions (`>terminal`, `>monitor`, `>settings`, `>ghost`)
- **Netzwerk-Widget**: Desktop-Taskbar-Widget mit IP/Hostname-Anzeige
- **Rate-Limiting Middleware**: 120 Requests/Minute pro IP

#### CRUD-Operationen (14 neue API-Endpoints)
- `DELETE /api/firewall/rules/{id}` — Firewall-Regel löschen
- `POST /api/anomaly/detections/{id}/resolve` — Anomalie als gelöst markieren
- `DELETE /api/synaptic/memories/{id}` — Synaptic Memory löschen
- `POST /api/rag/sources` — RAG-Quelle hinzufügen
- `DELETE /api/rag/sources/{name}` — RAG-Quelle löschen
- `POST /api/immutable/snapshots` — Snapshot erstellen
- `DELETE /api/immutable/snapshots/{id}` — Snapshot löschen
- `POST /api/immutable/snapshots/{id}/restore` — Snapshot wiederherstellen
- `DELETE /api/usb/jobs/{id}` — Flash-Job abbrechen
- `GET /api/usb/jobs/{id}/progress` — Job-Fortschritt abfragen
- `PATCH /api/hotspot/config` — Hotspot-Konfiguration ändern
- `POST /api/browser/import/selective` — Selektiver Browser-Import
- `POST /api/config/import/selective` — Selektiver Config-Import
- `POST /api/workspace/open` — Datei öffnen

#### Export & Datenmanagement
- `GET /api/export/{schema}/{table}?format=json|csv` — Tabellenexport als CSV/JSON
- `GET /api/export/logs?format=json|csv` — System-Logs exportieren

#### User Management
- `GET /api/users` — Benutzer auflisten
- `POST /api/users` — Benutzer anlegen
- `PATCH /api/users/{id}` — Benutzer aktualisieren
- `DELETE /api/users/{id}` — Benutzer deaktivieren

#### Audit & Backup
- `GET /api/audit/log` — Audit-Log abfragen
- `GET /api/audit/changes` — Change-Log abfragen
- `POST /api/backup/trigger` — Manuelles Backup auslösen
- `GET /api/backup/status` — Backup-Status abfragen

### 🔧 Verbesserungen

#### App-Settings (13 weitere Apps)
Alle verbleibenden Apps haben jetzt vollständige Settings-Unterstützung:
- AIWorkshop, AnomalyDetector, AppSandbox, BrowserMigration, ConfigImporter
- FirewallManager, GhostUpdater, ImmutableFS, RAGManager, SynapticViewer
- USBInstaller, WLANHotspot, WorkspaceMapper

#### UI-Erweiterungen in 10 Komponenten
- **FirewallManager**: Delete-Button pro Regel (🗑)
- **AnomalyDetector**: „Lösen"-Button pro Anomalie (✓)
- **SynapticViewer**: Memory-Lösch-Button (🗑)
- **RAGManager**: „+ Quelle"-Dialog + Delete-Button pro Quelle
- **ImmutableFS**: „+ Snapshot"-Button, Restore (♻️) und Delete (🗑) pro Snapshot
- **USBInstaller**: Cancel-Button pro laufendem Job (✗)
- **BrowserMigration**: Selektive Import-Checkboxen (Bookmarks/History/Passwörter)
- **ConfigImporter**: Import-per-Kategorie-Button (📥)
- **WLANHotspot**: Erweiterte Konfiguration (Band/Kanal) im aktiven Zustand
- **WorkspaceMapper**: „Öffnen"-Button pro Suchergebnis (📂)

### 📦 Datenbank-Schemas
- `schema/42-remaining-app-settings-seed.sql` — Settings-Seed für 13 Apps

### 📁 Neue Dateien
- `frontend/src/hooks/useNotification.jsx`
- `frontend/src/hooks/useKeyboardShortcuts.js`
- `frontend/src/components/SpotlightSearch.jsx`
- `CHANGELOG.md`

---

## [v0.9.0] — 2025-01-XX

### ✨ Neue Features

#### Per-App Settings System
- JSON-Schema-basiertes Settings-System für alle 29+ Apps
- `dbai_ui.app_user_settings` Tabelle für Benutzereinstellungen
- Server-seitiges Merging (Default ← User-Override)
- `useAppSettings()` React-Hook mit Debounced-Save
- `AppSettingsPanel` generische UI-Komponente
- 5 API-Endpoints: GET/PATCH/DELETE settings, GET schema, GET all

#### Knowledge Documentation
- 41 Wissenseinträge in 8 Tabellen (system_memory, module_registry, changelog, architecture_decisions, system_glossary, known_issues, build_log, agent_sessions)

### 📦 Datenbank-Schemas
- `schema/39-app-settings.sql` — Settings-Infrastruktur
- `schema/40-app-settings-seed.sql` — Settings-Seed (16 Apps)
- `schema/41-knowledge-session-v0.9.0.sql` — Knowledge-Session

---

## [v0.8.0] — Stufe 4 Features

### ✨ Features
- USB Installer, WLAN Hotspot, Immutable FS, App Sandbox
- Anomaly Detection, Firewall Manager, Terminal
- CI/CD & OTA Update System
- Desktop Nodes, Workshop Custom Tables

---

## [v0.7.0] — Stufe 3 Features

### ✨ Features
- Browser Migration, Config Import, Workspace Mapping
- Synaptic Memory, RAG Pipeline
- Ghost Autonomy System

---

## [v0.6.0] — Core System

### ✨ Features
- Login/Boot-System, Desktop-UI, Window-Manager
- SQL Explorer, LLM Integration, Hardware Monitor
- Event-System, WebSocket-Bridge
- Ghost AI Core
