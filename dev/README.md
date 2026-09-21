# DBAI — Entwicklungsumgebung

> Setup-Anleitung für die lokale Entwicklung, Hardware-Simulation und Container-Orchestrierung.

---

## Überblick

Die DBAI-Entwicklungsumgebung besteht aus drei Schichten:

| Schicht | Werkzeug | Zweck |
|---------|----------|-------|
| **Local Dev** | Python venv | Isolierte Python-Pakete, C-Bindings, Tests |
| **Hardware-Sim** | QEMU/KVM | Emulierte x86-Hardware für `hardware_live`-Tests |
| **Container** | Docker Compose | Orchestriert PostgreSQL, Ghost-API, Dashboard-UI |

---

## 1. Schnellstart (Local Dev)

```bash
# venv erstellen + Abhängigkeiten installieren
./dev/setup_venv.sh

# Aktivieren
source .venv/bin/activate

# Server starten (PostgreSQL muss laufen)
python web/server.py

# Frontend (separates Terminal)
cd frontend && npm install && npm run dev

# Tests
pytest tests/
```

### Optionen

```bash
./dev/setup_venv.sh --reset    # venv komplett neu erstellen
./dev/setup_venv.sh --minimal  # Nur Python-Deps, keine C-Bindings
```

---

## 2. Docker Compose

Orchestriert alle Services als Container.

```bash
# .env aus Vorlage erstellen
cp .env.example .env

# Alles starten
docker compose up -d

# Logs verfolgen
docker compose logs -f ghost-api

# Status prüfen
docker compose ps

# Stoppen
docker compose down

# Stoppen + Daten löschen
docker compose down -v
```

### Services

| Service | Port | Beschreibung |
|---------|------|-------------|
| `postgres` | 5432 | PostgreSQL 16 + pgvector |
| `ghost-api` | 3000 | FastAPI Server (Hot-Reload) |
| `dashboard-ui` | 5173 | Vite Dev Server (HMR) |
| `hw-simulator` | — | QEMU Hardware-Simulator (opt.) |

### Hardware-Simulator aktivieren

```bash
# Mit Profil "hw-sim" starten
docker compose --profile hw-sim up -d

# Oder einzeln
docker compose --profile hw-sim up -d hw-simulator
```

---

## 3. Hardware-Simulator (QEMU/KVM)

Emuliert x86-Hardware und injiziert realistische Metriken in die
PostgreSQL-Zeitreihentabellen (`cpu`, `memory`, `disk`, `temperature`, `network`).

### Standalone (ohne Docker)

```bash
source .venv/bin/activate

# Software-Simulation (kein QEMU nötig)
python dev/qemu/hw_simulator.py

# Mit echtem QEMU
USE_REAL_QEMU=true python dev/qemu/hw_simulator.py
```

### API-Steuerung (über Ghost-API)

```bash
# Status
curl -s http://localhost:3000/api/simulator/status | jq

# Starten
curl -s -X POST http://localhost:3000/api/simulator/start | jq

# Anomalie auslösen
curl -s -X POST http://localhost:3000/api/simulator/anomaly \
  -H 'Content-Type: application/json' \
  -d '{"anomaly": "overtemp"}' | jq

# Anomalie deaktivieren
curl -s -X POST http://localhost:3000/api/simulator/anomaly \
  -H 'Content-Type: application/json' \
  -d '{"anomaly": null}' | jq

# Hardware-Profile auflisten
curl -s http://localhost:3000/api/simulator/profiles | jq

# Profil wechseln
curl -s -X POST http://localhost:3000/api/simulator/profile \
  -H 'Content-Type: application/json' \
  -d '{"profile": "server"}' | jq

# Stoppen
curl -s -X POST http://localhost:3000/api/simulator/stop | jq
```

### Hardware-Profile

| Profil | CPU | RAM | Disks | Zweck |
|--------|-----|-----|-------|-------|
| `minimal` | 2C/2T Celeron | 1 GB | 1× SSD | Embedded / IoT |
| `desktop` | 8C/16T i7-13700K | 16 GB | NVMe + HDD | Desktop-Workstation |
| `server` | 16C/32T EPYC 9654 | 64 GB | 4× NVMe/HDD | Server / Datacenter |
| `stress` | 4C/8T | 4 GB | 1× SSD | Stress-Tests (hohe Basistemperaturen) |

### Anomalie-Typen

| Anomalie | Effekt |
|----------|--------|
| `overtemp` | Temperaturen steigen auf >100°C |
| `disk_fail` | Erste Disk: I/O stoppt komplett |
| `mem_leak` | RAM steigt stetig, Swap wächst |
| `cpu_spike` | Alle Cores auf 85-100% |
| `network_flood` | 50-125 MB/s auf allen Interfaces |
| `null` | Anomalie deaktivieren |

---

## 4. Umgebungsvariablen

Siehe [.env.example](../.env.example) für alle verfügbaren Variablen.

Wichtige Variablen:

```bash
DBAI_DB_PASSWORD        # PostgreSQL Admin-Passwort
DBAI_DB_RUNTIME_PASSWORD # Runtime-User Passwort
DBAI_HW_SIMULATE        # true = Simulator startet automatisch mit API
QEMU_PROFILE            # Hardware-Profil (minimal/desktop/server/stress)
COMPOSE_PROFILES        # "hw-sim" um QEMU-Container zu starten
```

---

## 5. Projektstruktur (Dev-Dateien)

```
dev/
├── setup_venv.sh          # Python venv Setup-Skript
├── init-db.sh             # Docker PostgreSQL Init-Skript
├── nginx.conf             # Nginx-Konfiguration (Produktion)
├── Dockerfile.api         # Ghost-API Container
├── Dockerfile.ui          # Dashboard-UI Container
├── Dockerfile.qemu        # QEMU Hardware-Simulator Container
└── qemu/
    ├── hw_simulator.py    # Hardware-Simulator (617 Zeilen)
    └── profiles.json      # Hardware-Profile (4 Profile)

docker-compose.yml         # Service-Orchestrierung
.env.example               # Umgebungsvariablen-Vorlage
```

---

## 6. Troubleshooting

### PostgreSQL startet nicht
```bash
docker compose logs postgres
# Häufig: Port 5432 bereits belegt
sudo lsof -i :5432
```

### C-Bindings kompilieren nicht
```bash
sudo apt install build-essential gcc make
cd bridge/c_bindings && make clean && make
```

### Frontend-Build fehlt
```bash
cd frontend && npm install && npm run build
```

### Simulator-DB-Verbindung fehlgeschlagen
```bash
# Prüfe ob PostgreSQL läuft und die Tabellen existieren
pg_isready -h 127.0.0.1 -p 5432
psql -U dbai_system -d dbai -c "SELECT count(*) FROM dbai_system.cpu;"
```
