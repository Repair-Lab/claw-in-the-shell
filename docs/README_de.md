<p align="center">
  <img src="assets/ghostshell-banner.svg" alt="GhostShell OS" width="600"/>
</p>

<h1 align="center">🧠 GhostShell OS (G.S.O.S.)</h1>

<p align="center">
  <em>„Der Ghost ist die Logik. Die Datenbank ist die Shell."</em>
</p>

<p align="center">
  <a href="../README.md">English</a> ·
  <a href="README_de.md"><strong>Deutsch</strong></a> ·
  <a href="README_tr.md">Türkçe</a> ·
  <a href="README_zh.md">中文</a> ·
  <a href="README_ja.md">日本語</a> ·
  <a href="README_ko.md">한국어</a> ·
  <a href="README_es.md">Español</a> ·
  <a href="README_fr.md">Français</a> ·
  <a href="README_ru.md">Русский</a> ·
  <a href="README_pt.md">Português</a> ·
  <a href="README_ar.md">العربية</a> ·
  <a href="README_hi.md">हिन्दी</a>
</p>

---

## 🌊 Was ist GhostShell?

**GhostShell ist ein relationales KI-Betriebssystem.** Während Projekte wie OpenClaw *auf* einem System laufen, **ist** GhostShell das System. Es verwandelt eine PostgreSQL-Datenbank in einen lebendigen Organismus, in dem Hardware-Treiber, Dateisysteme und KI-Modelle („Ghosts") über SQL-Tabellen miteinander kommunizieren.

Jeder Gedanke. Jede Dateiverschiebung. Jeder Hardware-Impuls. Alles — ACID-konforme Datenbanktransaktionen. Unzerstörbar. Sicher. Konsistent.

```
┌─────────────────────────────────────────────────────────┐
│               🖥️  CYBER-DECK (React-Oberfläche)          │
│        Desktop · Apps · Ghost Chat · Software-Store     │
│            WebSocket-betrieben · Echtzeit               │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│             ⚡ NEURALE BRÜCKE (FastAPI)                   │
│     Dual-Pool-Architektur: System + Runtime             │
│   REST-API · WebSocket · Befehls-Whitelist-Sicherung    │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│          🧠 DIE SHELL (PostgreSQL 16 + pgvector)         │
│                                                         │
│   9 Schemas · 100+ Tabellen · Row-Level Security        │
│   Schema-Fingerabdrücke · Unveränderlichkeits-Schutz    │
└─────────────────────────────────────────────────────────┘
```

---

## 🔥 Warum GhostShell statt OpenClaw?

| | OpenClaw | GhostShell OS |
|---|---|---|
| **Architektur** | Applikation auf einem System | **Ist** das System |
| **Datenpersistenz** | Flüchtiger Speicher | ACID-Transaktionen — jeder Gedanke ist permanent |
| **Hardware** | Externe APIs | Hardware-als-Tabelle — `UPDATE cpu SET governor='performance'` |
| **KI-Modelle** | Ein Modell, Neustart nötig | Hot-Swap Ghosts — LLMs im laufenden Betrieb wechseln |
| **Sicherheit** | Applikations-Ebene | 3-Schichten-Unveränderlichkeit: Core → Runtime → Ghost |
| **Video/Sensoren** | Datei-basiert | Integrierte Tabellen-Views — Echtzeit in der Datenbank |
| **Selbstreparatur** | Manuell | Autonome Repair-Pipeline mit menschlicher Freigabe |

---

## 🛠 Die Architektur

| Schicht | Technologie | Zweck |
|---|---|---|
| **Kernel** | PostgreSQL 16 + pgvector | Der relationale Kern — 9 Schemas, 100+ Tabellen |
| **Intelligenz** | Lokale LLMs (vLLM, llama.cpp) | Ghost-Bewusstsein — Gedanken, Entscheidungen, Aktionen |
| **Neurale Brücke** | FastAPI (Python) | Dual-Pool-Sicherheitsschicht zwischen UI und Kernel |
| **Sensoren** | Python Hardware-Bindings | CPU, GPU, VRAM, Temperatur, Netzwerk — alles als Tabellen |
| **Oberfläche** | React Cyber-Deck | WebSocket-betriebener Desktop mit Fenstern, Apps, Taskbar |
| **Integrität** | Schema-Fingerabdrücke + RLS | 176 überwachte Objekte, unveränderlicher Core-Schutz |

---

## 🔒 Drei Sicherheitsebenen

```
   ┌─────────────────────────────────────────┐
   │   UNVERÄNDERLICHER KERN (dbai_system)    │  ← Schema-Eigentümer
   │   Schema-Fingerabdrücke, Boot-Konfig    │
   ├─────────────────────────────────────────┤
   │   LAUFZEIT-SCHICHT (dbai_runtime)        │  ← Web-Server-Betrieb
   │   RLS-geschützt, Lesen/Schreiben        │
   ├─────────────────────────────────────────┤
   │   GHOST-SCHICHT (dbai_llm)               │  ← KI darf NUR vorschlagen
   │   INSERT in proposed_actions only       │
   │   Kein ALTER, DROP oder CREATE          │
   └─────────────────────────────────────────┘
```

**Der Ghost darf reparieren — aber niemals umbauen.** Jede vorgeschlagene Änderung durchläuft:

```
Ghost schlägt vor → Mensch genehmigt → SECURITY DEFINER führt aus → Audit-Log
```

---

## 🚀 Schnellstart: „Steck dich in die Shell"

```bash
# 1. Shell klonen
git clone https://github.com/Repair-Lab/claw-in-the-shell.git
cd claw-in-the-shell

# 2. Die Matrix initialisieren
psql -U postgres -c "CREATE DATABASE dbai;"
for f in schema/*.sql; do psql -U dbai_system -d dbai -f "$f"; done

# 3. Den Ghost booten
export DBAI_DB_USER=dbai_system
export DBAI_DB_PASSWORD=<dein_passwort>
export DBAI_DB_HOST=127.0.0.1
export DBAI_DB_NAME=dbai
export DBAI_DB_RUNTIME_USER=dbai_runtime
export DBAI_DB_RUNTIME_PASSWORD=<dein_passwort>
python3 -m uvicorn web.server:app --host 0.0.0.0 --port 3000

# 4. Das Deck betreten
cd frontend && npm install && npx vite --host 0.0.0.0 --port 5173
# → Öffne http://localhost:5173
```

---

## 🦾 Features

- [x] **Hardware-als-Tabelle** — Lüfter, CPU-Takt und Festplatten per `SQL UPDATE` steuern
- [x] **17 Desktop-Apps** — Ghost Chat, Software Store, LLM Manager, SQL-Konsole und mehr
- [x] **Hot-Swap Ghosts** — LLMs im laufenden Betrieb wechseln ohne Kontextverlust
- [x] **Unveränderlichkeits-Schutz** — 176 Schema-Fingerabdrücke, Verletzungs-Protokollierung
- [x] **Repair-Pipeline** — Ghost schlägt vor → Mensch genehmigt → Sichere Ausführung
- [x] **WebSocket-Befehls-Whitelist** — Jeder WS-Befehl gegen die Datenbank validiert
- [x] **OpenClaw-Brücke** — OpenClaw-Skills in eine sicherere Umgebung importieren
- [x] **Echtzeit-Metriken** — CPU, RAM, GPU, Temperatur via WebSocket gestreamt
- [x] **Wissensbasis** — Vektor-gestütztes Systemgedächtnis mit pgvector
- [x] **Row-Level Security** — 71 Tabellen mit RLS-Richtlinien über 5 Datenbankrollen
- [ ] **Autonomes Coding** *(In Arbeit)* — Ghost schreibt seine eigenen SQL-Migrationen
- [ ] **Vision-Integration** *(Geplant)* — Echtzeit-Videoanalyse in `media_metadata`
- [ ] **Verteilte Ghosts** *(Geplant)* — Mehrere Ghost-Instanzen über Knoten hinweg

---

## 🎨 Branding

| Element | Wert |
|---|---|
| **Codename** | Claw in the Shell |
| **Systemname** | GhostShell OS (G.S.O.S.) |
| **Philosophie** | *„Der Ghost ist die Logik. Die Datenbank ist die Shell."* |
| **Farben** | Deep Space Black `#0a0a0f` · Cyber-Cyan `#00ffcc` · Matrix Green `#00ff41` |
| **Logo-Konzept** | Ein leuchtender Datenwürfel mit spektralem Kern |

---

<p align="center">
  <strong>GhostShell OS</strong> — Wo jeder Gedanke zur Transaktion wird.<br/>
  <em>Repair-Lab · 2026</em>
</p>
