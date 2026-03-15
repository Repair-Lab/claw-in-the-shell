<p align="center">
  <img src="docs/assets/ghostshell-banner.svg" alt="GhostShell OS" width="600"/>
</p>

<h1 align="center">🧠 GhostShell OS (G.S.O.S.)</h1>

<p align="center">
  <em>"The Ghost is the Logic. The Database is the Shell."</em>
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="docs/README_de.md">Deutsch</a> ·
  <a href="docs/README_tr.md">Türkçe</a> ·
  <a href="docs/README_zh.md">中文</a> ·
  <a href="docs/README_ja.md">日本語</a> ·
  <a href="docs/README_ko.md">한국어</a> ·
  <a href="docs/README_es.md">Español</a> ·
  <a href="docs/README_fr.md">Français</a> ·
  <a href="docs/README_ru.md">Русский</a> ·
  <a href="docs/README_pt.md">Português</a> ·
  <a href="docs/README_ar.md">العربية</a> ·
  <a href="docs/README_hi.md">हिन्दी</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Kernel-PostgreSQL_16-336791?style=for-the-badge&logo=postgresql&logoColor=white"/>
  <img src="https://img.shields.io/badge/Ghost-LLM_Powered-00ff88?style=for-the-badge&logo=openai&logoColor=black"/>
  <img src="https://img.shields.io/badge/Interface-React_CyberDeck-61DAFB?style=for-the-badge&logo=react&logoColor=black"/>
  <img src="https://img.shields.io/badge/License-Proprietary-red?style=for-the-badge"/>
</p>

---

## 🌊 What is GhostShell?

**GhostShell is a relational AI operating system.** While projects like OpenClaw run *on* a system, GhostShell **is** the system. It transforms a PostgreSQL database into a living organism where hardware drivers, file systems, and AI models ("Ghosts") communicate through SQL tables.

Every thought. Every file move. Every hardware impulse. All of it — ACID-compliant database transactions. Indestructible. Secure. Consistent.

```
┌─────────────────────────────────────────────────────────┐
│                 🖥️  CYBER-DECK (React UI)                │
│         Desktop · Apps · Ghost Chat · Store             │
│              WebSocket-powered · Real-time              │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│              ⚡ NEURAL BRIDGE (FastAPI)                   │
│      Dual-Pool Architecture: System + Runtime           │
│   REST API · WebSocket · Command Whitelist Security     │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│            🧠 THE SHELL (PostgreSQL 16 + pgvector)       │
│                                                         │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│   │ dbai_core│ │ dbai_llm │ │dbai_system│ │ dbai_ui  │  │
│   │ Identity │ │  Ghosts  │ │ Hardware  │ │ Desktop  │  │
│   │  Config  │ │ Thoughts │ │  Metrics  │ │ Windows  │  │
│   │   Auth   │ │ Actions  │ │   Temps   │ │   Apps   │  │
│   └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│   │dbai_event│ │dbai_panic│ │dbai_vector│ │dbai_journal│ │
│   │  Events  │ │ Recovery │ │ Memories  │ │ Audit Log│  │
│   │  E-Mail  │ │ Failsafe │ │ Embeddings│ │ Changes  │  │
│   └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│                                                         │
│        100+ Tables · Row-Level Security · RLS           │
│     Schema Fingerprints · Immutability Enforcement      │
└─────────────────────────────────────────────────────────┘
```

---

## 🔥 Why GhostShell, not OpenClaw?

| | OpenClaw | GhostShell OS |
|---|---|---|
| **Architecture** | Application on a system | **Is** the system |
| **Data Persistence** | Volatile memory | ACID transactions — every thought is permanent |
| **Hardware** | External APIs | Hardware-as-a-Table — `UPDATE cpu SET governor='performance'` |
| **AI Models** | Single model, restart required | Hot-Swap Ghosts — change LLMs without losing context |
| **Security** | Application-level | 3-layer immutability: Core → Runtime → Ghost |
| **Video/Sensors** | File-based | Integrated table views — real-time in the database |
| **Self-Repair** | Manual | Autonomous repair pipeline with human approval |

---

## 🛠 The Architecture

| Layer | Technology | Purpose |
|---|---|---|
| **Kernel** | PostgreSQL 16 + pgvector | The relational core — 9 schemas, 100+ tables |
| **Intelligence** | Local LLMs (vLLM, llama.cpp) | Ghost consciousness — thoughts, decisions, actions |
| **Neural Bridge** | FastAPI (Python) | Dual-pool security layer between UI and kernel |
| **Sensors** | Python Hardware Bindings | CPU, GPU, VRAM, temperature, network — all as tables |
| **Interface** | React Cyber-Deck | WebSocket-powered desktop with windows, apps, taskbar |
| **Integrity** | Schema Fingerprints + RLS | 176 monitored objects, immutable core protection |

---

## 🔒 Three Security Layers

```
   ┌─────────────────────────────────────┐
   │     IMMUTABLE CORE (dbai_system)     │  ← Schema owner, full control
   │  Schema fingerprints, boot config   │
   ├─────────────────────────────────────┤
   │     RUNTIME LAYER (dbai_runtime)     │  ← Web server operations
   │  RLS-enforced, read/write via policy│
   ├─────────────────────────────────────┤
   │     GHOST LAYER (dbai_llm)           │  ← AI can ONLY propose actions
   │  INSERT into proposed_actions only  │
   │  Cannot ALTER, DROP, or CREATE      │
   └─────────────────────────────────────┘
```

**The Ghost can repair — but never rebuild.** Every proposed change goes through:

```
Ghost proposes → Human approves → SECURITY DEFINER executes → Audit logged
```

---

## 🚀 Quickstart: "Plug into the Shell"

```bash
# 1. Clone the Shell
git clone https://github.com/Repair-Lab/claw-in-the-shell.git
cd claw-in-the-shell

# 2. Initialize the Matrix
psql -U postgres -c "CREATE DATABASE dbai;"
for f in schema/*.sql; do psql -U dbai_system -d dbai -f "$f"; done

# 3. Boot the Ghost
export DBAI_DB_USER=dbai_system
export DBAI_DB_PASSWORD=<your_password>
export DBAI_DB_HOST=127.0.0.1
export DBAI_DB_NAME=dbai
export DBAI_DB_RUNTIME_USER=dbai_runtime
export DBAI_DB_RUNTIME_PASSWORD=<your_password>
python3 -m uvicorn web.server:app --host 0.0.0.0 --port 3000

# 4. Enter the Deck
cd frontend && npm install && npx vite --host 0.0.0.0 --port 5173
# → Open http://localhost:5173
```

---

## 🦾 Features

- [x] **Hardware-as-a-Table** — Control fans, CPU clock, and drives via `SQL UPDATE`
- [x] **17 Desktop Apps** — Ghost Chat, Software Store, LLM Manager, SQL Console, and more
- [x] **Hot-Swap Ghosts** — Change your LLM at runtime without losing context
- [x] **Immutability Enforcement** — 176 schema fingerprints, policy violation logging
- [x] **Repair Pipeline** — Ghost proposes → Human approves → Secure execution
- [x] **WebSocket Command Whitelist** — Every WS command validated against database
- [x] **OpenClaw Bridge** — Import your OpenClaw skills into a safer environment
- [x] **Real-time Metrics** — CPU, RAM, GPU, temperature streamed via WebSocket
- [x] **Knowledge Base** — Vector-powered system memory with pgvector
- [x] **Row-Level Security** — 71 tables with RLS policies across 5 database roles
- [ ] **Autonomous Coding** *(In Progress)* — Ghost writes its own SQL migrations
- [ ] **Vision Integration** *(Planned)* — Real-time video analysis in `media_metadata`
- [ ] **Distributed Ghosts** *(Planned)* — Multiple Ghost instances across nodes

---

## 📊 System at a Glance

```sql
SELECT 'GhostShell OS' AS system,
       count(*) FILTER (WHERE schemaname LIKE 'dbai_%') AS tables,
       (SELECT count(*) FROM dbai_ui.apps) AS apps,
       (SELECT count(*) FROM dbai_llm.ghost_models) AS ghosts,
       (SELECT count(*) FROM dbai_core.schema_fingerprints) AS fingerprints
FROM pg_tables;

--  system       | tables | apps | ghosts | fingerprints
-- --------------+--------+------+--------+--------------
--  GhostShell OS|    100+|   17 |      6 |          176
```

---

## 🎨 Branding

| Element | Value |
|---|---|
| **Codename** | Claw in the Shell |
| **System Name** | GhostShell OS (G.S.O.S.) |
| **Philosophy** | *"The Ghost is the Logic. The Database is the Shell."* |
| **Colors** | Deep Space Black `#0a0a0f` · Cyber-Cyan `#00ffcc` · Matrix Green `#00ff41` |
| **Logo Concept** | A glowing data cube with a spectral core |

---

## 🗂 Project Structure

```
claw-in-the-shell/
├── web/                    # FastAPI backend (Neural Bridge)
│   └── server.py           # Dual-pool server, REST + WebSocket
├── frontend/               # React Cyber-Deck UI
│   └── src/
│       └── components/     # Desktop, Apps, Ghost Chat, Store…
├── schema/                 # PostgreSQL schema files (numbered)
│   ├── 01-10               # Core: roles, tables, RLS
│   ├── 22                  # Ghost Autonomy & proposed actions
│   ├── 23-26               # Apps, store, ghost models
│   └── 27                  # Immutability enforcement layer
├── bridge/                 # Hardware bridge (C bindings)
├── docs/                   # Translations & documentation
└── README.md               # You are here
```

---

<p align="center">
  <strong>GhostShell OS</strong> — Where every thought becomes a transaction.<br/>
  <em>Repair-Lab · 2026</em>
</p>
