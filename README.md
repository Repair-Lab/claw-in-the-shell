# DBAI — Tabellenbasiertes KI-Betriebssystem

## Architektur-Übersicht

DBAI ist ein Betriebssystem, das auf einer relationalen Datenbank (PostgreSQL) als Kern basiert.
Jeder Systemzustand, jedes Hardware-Event und jede KI-Erinnerung ist eine Zeile in einer Tabelle.

```
┌──────────────────────────────────────────────────────────────┐
│                    DBAI Betriebssystem                        │
├──────────────┬───────────────┬───────────────┬───────────────┤
│  System      │  Event        │  Vektor       │  LLM          │
│  Tabellen    │  Tabellen     │  Tabellen     │  (llama.cpp)  │
│  (HW-Live)   │  (Interrupts) │  (pgvector)   │  In-Database  │
├──────────────┴───────────────┴───────────────┴───────────────┤
│              PostgreSQL + pgvector (Herzstück)               │
├──────────────────────────────────────────────────────────────┤
│  WAL (Write-Ahead Log) ──── Separates Laufwerk               │
├──────────────────────────────────────────────────────────────┤
│  ZFS / BTRFS (Self-Healing Dateisystem)                      │
├──────────────────────────────────────────────────────────────┤
│  System Bridge (Python + C) ── Bootet DB in RAM              │
└──────────────────────────────────────────────────────────────┘
```

## Technische Bausteine

| Baustein | Technologie | Funktion |
|---|---|---|
| DB-Kern | PostgreSQL 16+ | Verwaltet alle Tabellen, MVCC, Transaktionen |
| Vektor-Extension | pgvector | KI-Gedanken als mathematische Vektoren |
| System-Tabellen | Custom Schema | Live-Hardware-Werte (CPU, RAM, Temp) |
| Dateisystem | ZFS/BTRFS | Self-Healing, Bit-Rot-Erkennung |
| WAL | pg_wal auf sep. Disk | Fahrtenbuch aller Änderungen |
| In-DB LLM | llama.cpp embedded | Lokales LLM, Daten verlassen nie die DB |
| System Bridge | Python + C | Bootet DB, Hardware-Interrupt-Handler |

## Sicherheit gegen Datenverlust (3 Schichten)

1. **PITR (Point-in-Time Recovery)** — Jede Sekunde ein Statusbericht, Zeitmaschine
2. **Disk Mirroring** — Echtzeit auf 2+ Festplatten, 0ms Failover
3. **Append-Only Logs** — System-Logs nie löschbar, nur anhängbar

## No-Go Liste

- ❌ Keine manuellen Dateipfade (`/home/user/datei.txt`)
- ❌ Keine externe API-Abhängigkeit (kein OpenAI, alles lokal)
- ❌ Keine Root-Passwörter — Row-Level Security stattdessen
- ❌ Keine unstrukturierten Daten direkt in Tabellen (nur Hash/Pointer + Metadaten)

## Verzeichnisstruktur

```
DBAI/
├── config/          # PostgreSQL & DBAI Konfiguration
├── schema/          # Alle SQL-Schemas (00-10)
├── bridge/          # System Bridge (Python + C-Bindings)
├── recovery/        # PITR, Mirror, Panic Recovery
├── llm/             # llama.cpp Integration
├── scripts/         # Install, Bootstrap, Backup
└── tests/           # Automatische Tests
```

## Schnellstart

```bash
cd DBAI
bash scripts/install.sh      # PostgreSQL + Extensions installieren
bash scripts/bootstrap.sh    # Datenbank erstellen und Schemas laden
python3 bridge/system_bridge.py start   # System Bridge starten
```

## Voraussetzungen

- Linux x86_64
- PostgreSQL 16+
- Python 3.11+
- gcc (für C-Bindings)
- ZFS oder BTRFS Dateisystem (empfohlen)
- llama.cpp + GGUF-Modell
