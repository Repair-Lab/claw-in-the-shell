<p align="center">
  <img src="docs/assets/ghostshell-banner.svg" alt="GhostShell OS" width="600"/>
</p>

<h1 align="center">🧠 GhostShell OS (G.S.O.S.)</h1>

<p align="center">
  <strong>The Relational AI Operating System</strong><br/>
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
  <img src="https://img.shields.io/badge/GPU-NVIDIA_CUDA-76B900?style=for-the-badge&logo=nvidia&logoColor=white"/>
  <img src="https://img.shields.io/badge/Interface-React_CyberDeck-61DAFB?style=for-the-badge&logo=react&logoColor=black"/>
  <img src="https://img.shields.io/badge/CI%2FCD-Atomic_OTA-ff6600?style=for-the-badge&logo=githubactions&logoColor=white"/>
  <img src="https://img.shields.io/badge/Arch-x86__64_+_ARM64-purple?style=for-the-badge&logo=arm&logoColor=white"/>
  <img src="https://img.shields.io/badge/License-Proprietary-red?style=for-the-badge"/>
</p>

<p align="center">
  <a href="https://github.com/sponsors/Repair-Lab"><img src="https://img.shields.io/badge/♥_Sponsor-GhostShell_OS-ea4aaa?style=for-the-badge&logo=githubsponsors&logoColor=white"/></a>
</p>

---

## 🌊 What is GhostShell?

**GhostShell is not another AI bot.** It is a **post-applicative system architecture** that transforms a PostgreSQL database into a living, relational organism. While projects like OpenClaw run *on* a system, GhostShell **is** the system — the hardware abstraction layer itself.

Every thought. Every file move. Every hardware impulse. All of it — ACID-compliant database transactions. Indestructible. Secure. Consistent.

```
┌─────────────────────────────────────────────────────────┐
│                 🖥️  CYBER-DECK (React UI)                │
│     Desktop · 36 Apps · Ghost Chat · Software Store     │
│     Terminal · LLM Manager · RAG Pipeline · Updater     │
│              WebSocket-powered · Real-time              │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│              ⚡ NEURAL BRIDGE (FastAPI)                   │
│      Dual-Pool Architecture: System + Runtime           │
│   282 REST Endpoints · WebSocket · Command Whitelist    │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│       🎮 GPU LAYER (NVIDIA CUDA · llama.cpp)             │
│   Real-time VRAM Monitoring · Hot-Swap Model Loading    │
│   18 Ghost Models · Multi-Backend (llama.cpp / vLLM)    │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│            🧠 THE SHELL (PostgreSQL 16 + pgvector)       │
│                                                         │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│   │ dbai_core│ │ dbai_llm │ │dbai_system│ │ dbai_ui  │  │
│   │ Identity │ │  Ghosts  │ │ Hardware  │ │ Desktop  │  │
│   │  Config  │ │ 18 Models│ │  Metrics  │ │ Windows  │  │
│   │   Auth   │ │ RAG Pipe │ │  CI/CD    │ │ 36 Apps  │  │
│   └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│   │dbai_event│ │dbai_panic│ │dbai_vector│ │dbai_know.│  │
│   │  Events  │ │ Recovery │ │ Memories  │ │Knowledge │  │
│   │  E-Mail  │ │ Failsafe │ │ Synaptic  │ │ Library  │  │
│   └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│                                                         │
│     152 Tables · 69 Schema Files · Row-Level Security   │
│    Schema Fingerprints · Immutability · OTA Updates     │
└─────────────────────────────────────────────────────────┘
```

---

## 🔥 Why GhostShell, not OpenClaw?

| | OpenClaw | GhostShell OS |
|---|---|---|
| **Architecture** | Application on a system | **Is** the system |
| **Data Storage** | Volatile JSON files | ACID transactions — every thought is permanent |
| **Hardware** | External APIs | Hardware-as-a-Table — `UPDATE cpu SET governor='performance'` |
| **AI Models** | Single model, restart required | Hot-Swap 18 Ghosts — change LLMs without losing context |
| **GPU** | No native support | NVIDIA CUDA — real-time VRAM monitoring, live model loading |
| **Memory** | Flat context window | Synaptic Memory Pipeline + pgvector RAG |
| **Security** | Application-level | 3-layer immutability: Core → Runtime → Ghost |
| **Updates** | Manual reinstall | Atomic OTA with auto-rollback |
| **Self-Repair** | Manual | Autonomous repair pipeline with human approval |
| **Desktop** | None | 36 native apps, windowed UI, taskbar, terminal |

> OpenClaw is a great inspiration. GhostShell is the architecture it needs to be stable.

---

## 🛠 The Architecture

| Layer | Technology | Purpose |
|---|---|---|
| **Kernel** | PostgreSQL 16 + pgvector | The relational core — 10 schemas, 152 tables, 69 migration files |
| **Intelligence** | Local LLMs (llama.cpp CUDA) | 18 Ghost models — hot-swap, GPU-accelerated, RAG-augmented |
| **GPU Engine** | NVIDIA CUDA + llama.cpp | Real-time VRAM monitoring, model loading with live progress bar |
| **Neural Bridge** | FastAPI (Python, 9000+ LOC) | 282 API endpoints, dual-pool security, WebSocket real-time |
| **Sensors** | Python Hardware Bridge + C-Bindings | CPU, GPU, VRAM, temperature, network — all as tables |
| **Interface** | React Cyber-Deck | 36 desktop apps with windowed UI, taskbar, boot screen |
| **Integrity** | Schema Fingerprints + RLS | 176 monitored objects, immutable core protection |
| **Updates** | CI/CD + OTA Agent | Atomic updates with GitHub Actions, migration runner, auto-rollback |
| **Dev Tools** | Docker Compose + QEMU Simulator | Containerized microservices, hardware emulation for testing |
| **Multi-Arch** | x86_64 + ARM64 (Docker buildx) | Same Ghost, same DB — PC, Raspberry Pi, Apple Silicon |

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

## 🚀 Quickstart

### Option 1: One-Command Install

```bash
git clone https://github.com/Repair-Lab/claw-in-the-shell.git
cd claw-in-the-shell
bash scripts/install.sh    # installs all dependencies
bash scripts/bootstrap.sh  # initializes database & schema
bash scripts/start_web.sh  # starts backend + frontend
# → Open http://localhost:3000 — Login: root / dbai2026
```

### Option 2: Docker Compose (Recommended for Dev)

```bash
git clone https://github.com/Repair-Lab/claw-in-the-shell.git
cd claw-in-the-shell
cp .env.example .env       # configure your environment
docker compose up -d       # PostgreSQL + API + Dashboard
# → Open http://localhost:5173
```

### Option 3: Manual Setup

```bash
git clone https://github.com/Repair-Lab/claw-in-the-shell.git
cd claw-in-the-shell

# 1. Python venv
./dev/setup_venv.sh && source .venv/bin/activate

# 2. Init database
for f in schema/*.sql; do psql -U dbai_system -d dbai -f "$f"; done

# 3. Start backend
python3 -m uvicorn web.server:app --host 0.0.0.0 --port 3000

# 4. Start frontend (separate terminal)
cd frontend && npm install && npm run dev
```

---

## 🦾 Features

### Core System
- [x] **Hardware-as-a-Table** — Control fans, CPU clock, drives, GPU via `SQL UPDATE`
- [x] **Hot-Swap Ghosts** — Change your LLM at runtime without losing context
- [x] **3-Layer Immutability** — 176 schema fingerprints, policy violation logging
- [x] **Repair Pipeline** — Ghost proposes → Human approves → Secure execution
- [x] **Row-Level Security** — 71+ tables with RLS policies across 5 database roles
- [x] **WebSocket Command Whitelist** — Every WS command validated against database

### GPU & LLM Engine (NEW)
- [x] **NVIDIA CUDA Acceleration** — llama.cpp compiled with CUDA (Blackwell/Ada/Ampere)
- [x] **Real-Time VRAM Monitor** — Live GPU memory bar via `nvidia-smi` (1s polling)
- [x] **Model Hot-Loading** — Start/stop LLMs on GPU with one click, live VRAM progress bar
- [x] **18 Ghost Models** — Qwen3.5-27B, DeepSeek, Mistral, LLaMA, CodeLlama and more
- [x] **Multi-Backend** — llama.cpp (GGUF), vLLM, OpenAI-compatible API
- [x] **GPU Recommendations** — Automatic `n_gpu_layers`, `ctx_size`, `threads` based on model + hardware
- [x] **CPU/GPU Toggle** — Switch between GPU-accelerated and CPU-only inference

### Desktop Experience (36 Apps)
- [x] **Ghost Chat** — Conversational AI with model selector and full system context
- [x] **Software Store** — Install and manage desktop apps
- [x] **Terminal** — Full Linux terminal with ANSI colors, tab support, 5000-line scrollback
- [x] **SQL Console** — Direct database queries from the desktop
- [x] **System Monitor** — Real-time CPU, RAM, GPU, temperature
- [x] **File Browser** — Navigate the filesystem
- [x] **Network Scanner** — Discover all Web-UIs in your network
- [x] **Firewall Manager** — iptables rules, zones, active connections
- [x] **LLM Manager** — Full GPU model management with VRAM live bar, start/stop, benchmarks
- [x] **WebUI Hub** — Open WebUI, n8n, VS Code Server, Grafana and 10+ WebUIs

### Deep Integration (Stufe 3)
- [x] **Browser Migration** — Import bookmarks, history, passwords from Chrome/Firefox/Edge
- [x] **System Config Import** — Automatically detect and import WiFi, locale, keyboard configs
- [x] **Workspace Mapping** — Index your filesystem without copying files
- [x] **Synaptic Memory Pipeline** — Real-time event vectorization with pgvector
- [x] **RAG Pipeline** — Retrieval-Augmented-Generation across 7 database sources

### Advanced Features (Stufe 4)
- [x] **USB Installer** — Flash ISO/IMG to USB drives (dd/Ventoy)
- [x] **WLAN Hotspot** — Create and manage wireless hotspots
- [x] **Immutable Filesystem** — OverlayFS write-protected root with snapshots
- [x] **i18n Runtime Translation** — 12 languages with database-driven translations
- [x] **Anomaly Detection** — Z-Score based anomaly detection for system metrics
- [x] **App Sandboxing** — Firejail/cgroup-based application isolation
- [x] **Network Firewall** — iptables management with zones and connection tracking

### CI/CD & OTA Updates
- [x] **GitHub Actions Pipeline** — Automated build, test, release on push
- [x] **Atomic OTA Updates** — Download → Backup → Migrate → Build → Verify → Live
- [x] **Migration Runner** — Transactional SQL migrations with SHA256 checksums
- [x] **Auto-Rollback** — Failed updates automatically revert to previous version
- [x] **Ghost Updater Desktop App** — Visual update channel with "Ghost-Evolution verfügbar" banner
- [x] **Ghost Mail** — E-Mail Client mit Ghost LLM Integration (compose, reply, improve via AI)

### Development Environment
- [x] **Docker Compose** — PostgreSQL, Ghost-API, Dashboard-UI orchestrated
- [x] **QEMU/KVM Hardware Simulator** — Emulate x86 hardware for testing
- [x] **4 Hardware Profiles** — minimal, desktop, server, stress
- [x] **Anomaly Injection** — overtemp, disk_fail, mem_leak, cpu_spike, network_flood

### Coming Soon
- [ ] **Autonomous Coding** — Ghost writes its own SQL migrations
- [ ] **Multi-GPU Parallel** — Split models across multiple GPUs
- [ ] **Vision Integration** — Real-time video analysis in `media_metadata`
- [ ] **Distributed Ghosts** — Multiple Ghost instances across nodes
- [ ] **Model Marketplace** — Download and install GGUF models from HuggingFace directly

---

## � Multi-Architecture Support

GhostShell OS is hardware-agnostic by design. The database is the kernel — and PostgreSQL runs everywhere.

```
┌────────────────────────────────────────────────────────────────────┐
│                    🧠 GhostShell OS — Universal Ghost              │
├──────────────────────┬─────────────────────┬───────────────────────┤
│    x86_64 (Tier 1)   │   ARM64 (Tier 2)    │   Portable Layer      │
├──────────────────────┼─────────────────────┼───────────────────────┤
│ • Gaming PCs         │ • Raspberry Pi 4/5  │ • PostgreSQL dump     │
│ • Workstations       │ • Apple Silicon     │ • Schema migrations   │
│ • Cloud VMs          │ • NVIDIA Jetson     │ • Config TOML         │
│ • NVIDIA CUDA        │ • Pine64/Rock Pi    │ • Frontend (Browser)  │
│ • AVX/AVX2 LLM accel │ • ARM NEON LLM      │ • Docker Multi-Arch   │
│ • Bare-Metal ISO     │ • SD-Card .img      │ • pg_dump/pg_restore  │
└──────────────────────┴─────────────────────┴───────────────────────┘
```

| Tier | Architecture | GPU Support | Install Method | LLM Performance |
|------|-------------|-------------|----------------|----------------|
| **Tier 1** | x86_64 (AMD/Intel) | NVIDIA CUDA, AMD ROCm | ISO → USB → GRUB | Full speed (AVX2 + CUDA) |
| **Tier 2** | ARM64 (RPi, Apple M) | VideoCore, Neural Engine | IMG → SD-Card / SSD | Good (NEON, 7B-13B models) |

### Cross-Architecture Portability

```bash
# Train your Ghost on a Raspberry Pi...
pg_dump -U dbai_system dbai > ghost_brain.sql

# ...and migrate it to a powerful x86 workstation
psql -U dbai_system dbai < ghost_brain.sql
# Your Ghost wakes up with all memories intact.
```

### Multi-Arch Docker Build

```bash
# Build for both architectures simultaneously
docker buildx create --name ghostbuilder --use
docker buildx build --platform linux/amd64,linux/arm64 \
    -f dev/Dockerfile.api -t ghcr.io/repair-lab/ghostshell-api:latest --push .
```

### Hardware Detection (Runtime)

The Ghost automatically detects its hardware environment:

```python
import platform
arch = platform.machine()  # 'x86_64' or 'aarch64'

if arch in ('aarch64', 'arm64'):
    # ARM: Use NEON-optimized inference, skip NVIDIA
    llm_backend = 'cpu'  # ARM NEON auto-enabled by llama-cpp
elif arch == 'x86_64':
    # x86: Check for NVIDIA GPU → CUDA, else AVX2
    llm_backend = 'cuda' if has_nvidia() else 'cpu'

# PostgreSQL doesn't care — it's the same on both.
```

### Slim Image (Thin Provisioning)

For production and SD-card deployment, use the slim image builder:

```bash
# 4GB minimal image (expands to full SD-card size on first boot)
sudo bash scripts/build-arm-image-slim.sh

# Headless (no Chromium/X11, server-only)
sudo bash scripts/build-arm-image-slim.sh --headless

# Alpine Linux base (~50MB vs ~600MB Debian)
sudo bash scripts/build-arm-image-slim.sh --base alpine

# Custom size
sudo bash scripts/build-arm-image-slim.sh --size 2G
```

**First-Boot Chain:**
1. `ghostshell-expand` — Root partition auto-expands to full disk
2. `ghostshell-setup` — Interactive wizard (language, WiFi, passwords)
3. Python venv + pip install (from `requirements-slim.txt`)
4. PostgreSQL init + 38 schemas loaded
5. Frontend build (if not pre-built)
6. `ghostshell-models` — Optional LLM model download

**LLM Models (downloaded on demand, not in image):**
| Model | Size | Use Case |
|-------|------|----------|
| TinyLlama 1.1B | 669 MB | Minimal, fast inference on RPi |
| Phi-2 | 1.6 GB | Good quality, small footprint |
| Mistral 7B | 4.1 GB | Best quality for ARM |
| CodeLlama 7B | 4.1 GB | Code generation |

```bash
# On the running GhostShell system:
ghostshell-models list                  # Show available models
ghostshell-models download tinyllama    # Download smallest model
ghostshell-models interactive           # TUI selection
```

---

## �📊 System at a Glance

```sql
SELECT 'GhostShell OS' AS system,
       count(*) FILTER (WHERE schemaname LIKE 'dbai_%') AS tables,
       (SELECT count(*) FROM dbai_ui.apps) AS apps,
       (SELECT count(*) FROM dbai_llm.ghost_models) AS ghosts,
       (SELECT count(*) FROM dbai_core.schema_fingerprints) AS fingerprints
FROM pg_tables;

--  system       | tables | apps | ghosts | fingerprints
-- --------------+--------+------+--------+--------------
--  GhostShell OS|    152 |   36 |     18 |          176
```

---

## 🔄 CI/CD & OTA Update Flow

```
Developer pushes code
         │
         ▼
┌───────────────────┐     ┌──────────────────┐
│  GitHub Actions    │────▶│  Build & Test     │
│  (ghost-ci.yml)    │     │  • Python check   │
│                    │     │  • SQL validation  │
│  Triggered on:     │     │  • Frontend build  │
│  • push to main    │     │  • pytest          │
│  • pull request    │     └────────┬───────────┘
│  • tag v*          │              │
└────────────────────┘              ▼
                           ┌──────────────────┐
                           │  Release Package  │
                           │  tar.gz + SHA256  │
                           │  + GitHub Release │
                           └────────┬───────────┘
                                    │
         ┌──────────────────────────▼──────────────────────────┐
         │              OTA Update Agent (gs-updater)           │
         │                                                      │
         │  1. Check for updates (every 5 min)                  │
         │  2. Download & verify SHA256                         │
         │  3. Backup current state                            │
         │  4. Apply SQL migrations (transactional)            │
         │  5. Rebuild frontend                                │
         │  6. Healthcheck                                     │
         │  7. ✅ Live — or ❌ Auto-Rollback                     │
         └──────────────────────────────────────────────────────┘
```

---

## 💎 Sponsor GhostShell OS

We are building the foundation for the next generation of AI-powered operating systems. Your support funds bare-metal development, OTA infrastructure, and hardware lab testing.

<p align="center">
  <a href="https://github.com/sponsors/Repair-Lab">
    <img src="https://img.shields.io/badge/♥_Become_a_Sponsor-ea4aaa?style=for-the-badge&logo=githubsponsors&logoColor=white" alt="Sponsor"/>
  </a>
</p>

| Tier | Name | What You Get |
|------|------|-------------|
| **$5/mo** | 🐚 Shell-Inhabitant | Your name in the Kernel's `contributors` table. The Ghost thanks you in the system log. |
| **$20/mo** | 🔗 Neural-Link Tech | Early access to bare-metal installer (ISO). Private Discord channel. Roadmap voting rights. |
| **$50/mo** | 👻 Ghost-Architect | Name a system table or skill. Monthly dev check-in. Logo on landing page. |
| **$100+/mo** | 🧠 Cyberbrain Industrialist | Enterprise integration session. Priority feature requests in `task_queue`. |

> *"We're not building another tool. We're building the shell for the AIs of the future."*

See [SPONSOR.md](.github/SPONSOR.md) for full tier details and rewards.

---

## 🎨 Branding

| Element | Value |
|---|---|
| **Codename** | Claw in the Shell |
| **System Name** | GhostShell OS (G.S.O.S.) |
| **Philosophy** | *"The Ghost is the Logic. The Database is the Shell."* |
| **Colors** | Deep Space Black `#0a0a14` · Cyber-Cyan `#00ffcc` · Matrix Green `#00ff41` |
| **Logo** | A glowing data cube with a spectral core |

---

## 🗂 Project Structure

```
claw-in-the-shell/
├── web/                         # FastAPI backend (Neural Bridge)
│   └── server.py                # 9000+ lines, 282 routes, GPU/LLM engine
├── frontend/                    # React Cyber-Deck UI
│   └── src/components/apps/     # 36 desktop applications
├── schema/                      # PostgreSQL schemas (69 numbered files)
│   ├── 00-13                    # Core: extensions, tables, RLS, seeds
│   ├── 14-27                    # Self-healing, ghost, desktop, hardware
│   ├── 28-45                    # AI Workshop, LLM, Stufe 3+4, Settings
│   └── 46-67                    # Knowledge, Ghost Browser, Agent, LLM Mgr
├── bridge/                      # Hardware bridge (Python + C bindings)
│   ├── gs_updater.py            # OTA Update Agent
│   ├── migration_runner.py      # Transactional SQL migrations
│   ├── rag_pipeline.py          # RAG across 7 DB sources
│   ├── synaptic_pipeline.py     # Real-time event vectorization
│   ├── hardware_scanner.py      # Multi-arch hardware detection
│   └── c_bindings/              # libhw_interrupts.so (x86+ARM)
├── scripts/                     # Build & deployment tools
│   ├── build-iso.sh             # x86 ISO builder (Arch + Debian)
│   ├── build-arm-image.sh       # ARM64 SD-card image builder (32GB)
│   ├── build-arm-image-slim.sh  # ARM64 Slim image (4GB, thin provisioning)
│   ├── installer.py             # Python TUI installer (BTRFS/EXT4/ZFS)
│   ├── test-iso-qemu.sh         # QEMU VM test environment
│   ├── flash-arm-usb.sh         # Flash ARM image to USB/SD
│   ├── bootstrap.sh             # Database initialization
│   └── backup.sh                # Backup & restore
├── config/                      # System configuration
│   ├── archiso/                 # Arch Linux ISO profile (mkarchiso)
│   ├── systemd/                 # Service definitions
│   ├── grub/                    # Bootloader config
│   └── dbai.toml                # GhostShell main config
├── dev/                         # Development environment
│   ├── Dockerfile.api           # Ghost-API (Multi-Arch: x86+ARM)
│   ├── Dockerfile.ui            # Dashboard-UI (Multi-Arch)
│   ├── Dockerfile.qemu          # QEMU Simulator (Multi-Arch)
│   └── qemu/hw_simulator.py     # Hardware emulator
├── recovery/                    # Self-healing & panic recovery
├── llm/                         # LLM bridge (llama.cpp)
├── .github/
│   ├── workflows/ghost-ci.yml   # CI/CD pipeline (Multi-Arch)
│   ├── FUNDING.yml              # Sponsoring setup
│   └── SPONSOR.md               # Tier details
├── docs/                        # 12-language documentation
├── docker-compose.yml           # Dev orchestration
└── README.md                    # You are here
```

---

<p align="center">
  <strong>GhostShell OS</strong> — Where every thought becomes a transaction.<br/>
  <em>The Shell is ready. Are you the Ghost?</em><br/><br/>
  <strong>Repair-Lab · 2026</strong>
</p>
