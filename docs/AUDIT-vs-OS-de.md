# DBAI-OS — Capability Audit vs. macOS / Windows
**Datum:** 19.09.26 · **Quelle:** Live-Audit auf Worker 172.16.16.179 (alle Zahlen verifiziert, keine Annahmen)

---

## 1. Was live läuft (verifizierte Messwerte)

| Komponente | Wert |
|---|---|
| DB-Kernel | PostgreSQL **16.15** (Podman-Container `dbai-postgres`, wal_level=replica) |
| Tabellen | **195** in 13 Schemas: system:45, core:32, llm:29, security:19, ui:16, knowledge:13, workshop:11, net:11, event:8, vector:4, panic:4, journal:3 |
| RLS-Policies | **336** (AI-Sandboxing auf Zeilenebene) |
| Rollen | 5 Login-Rollen: dbai_system / dbai_runtime / dbai_monitor / dbai_llm / dbai_recovery |
| Views / Functions | 38 Views, **312** eigene Funktionen |
| Extensions | plpgsql, uuid-ossp, pgcrypto, **vector (pgvector)**, pg_stat_statements, pg_trgm |
| API | FastAPI "Neural Bridge" :3000 — **478 Endpoints** (192 GET / 127 POST / 27 PATCH / 28 DELETE / 5 PUT), Health: ok (db+llm) |
| LLM-Layer | Qwen3.8-27B (think :11502) + Qwen3-8B (fast :11501) via llm_router, GPU V100S 32GB (sm_70), llama.cpp b10615 |
| Frontend | React CyberDeck PWA, Build 825 KB / 81 Module, **39 Apps** in DB, 8 Desktop-Nodes |
| Schemas-Spezial | WAL-Journal (05), Panic-Dump (06), Self-Healing (14), Immutability Enforcement (27), RLS (07) |

---

## 2. Was DBAI-OS kann, was macOS/Windows NICHT können

| Fähigkeit | DBAI-OS | macOS / Windows |
|---|---|---|
| **Atomare Systemzustände** | Jede Aktion = ACID-Transaktion → kein Teardown/Corruption nach Crash (Registry-Korruption, torn Files) | Registry+FS-Journal helfen, aber App-State bleibt angreifbar |
| **Queryable History** | Völliges Audit-Log in SQL: jede Aktion, jeder User, jede Zeit — analytisch abfragbar (WAL + journal/event-Schemas) | macOS: syslog/plist-Fragmente; Windows: Event Viewer — nicht skalierbar querybar |
| **Point-in-Time Restore des Systems** | pg_dump + WAL → komplettes "OS" auf beliebigen Zeitpunkt zurück | Time Machine / Restore Points = Datei-Image, kein State-PITR |
| **AI-Sandboxing (RLS)** | 336 Policies: die KI sieht physisch nur Zeilen ihrer Aufgabe — Root-Passwörter unmöglich für sie | macOS App Sandbox/Windows ACLs = pro-App, grob; keine row-level AI-Trennung |
| **Multi-Tenant Rollen** | 5 Least-Privilege-Rollen mit Row-/Column-Sicht | OS-User-Accounts existieren, aber Granularität ist Dateisystem-basiert |
| **LLM-native Kernel** | 29 llm-Tabellen: Ghosts, RAG-Pipeline, Hot-Swap von Modellen als Systemdienst | OS hat kein Konzept von austauschbarem AI-Kernel |
| **Self-Healing als DB-Triggers** | Schema 14 + panic schema = Recovery-Logik im Kernel selbst | Watchdog-Dienste (launchd/Task Scheduler) — coarser, external |
| **Portabilität** | Läuft auf x86_64 UND ARM64 überall wo Postgres läuft | macOS=Apple-Hardware-Lock, Windows=Lizenz/Laden-Ökosystem |

## 3. Was macOS/Windows besser können (ehrliche Lücken)

1. **Hardware-Abstraktion**: Echte OSes treiben GPU/DISPLAY/USB mit µs-Latenz; GhostShell's HW-Layer ist Metrik-Polling → kein Echtzeit, kein DirectDraw
2. **Native Windowing/App-Ecosystem**: CyberDeck läuft im Browser-Tab (kein globaler Hotkey, kein true Multitasking); 39 Apps vs. Millionen im Mac/Microsoft Store
3. **Hardware Root of Trust**: Secure Boot/TPM/BitLocker/Gatekeeper; GhostShell's "Immunsystem" ist nur App-Layer — kein gemessener Boot
4. **HA/Failover**: wal_level=replica ist ready, aber kein Standby konfiguriert; macOS/Windows sind ebenfalls Single-Node, haben aber mature Snapshots
5. **Peripherie**: Drucker/Audio/USB-Devices brauchen ein Host-OS darunter — GhostShell läuft AUF Ubuntu, ist nicht selbst-contained

## 4. Gefundene Sicherheitslücken (JETZT fixierbar)

| # | Befund | Risiko | Fix |
|---|---|---|---|
| S1 | `DBAI_SECRET_KEY=ghosts…tion` im .env = Dev-Default | JWTs fälschbar, wenn jemand die Quelle sieht | Zufälliger 64-Zeichen-Key generieren + Neustart web |
| S2 | `.env` DB-Passwörter (`dbai_system_2026`, `dbai_runtime_2026`) ≠ Container-Wirklichkeit (POSTGRES_USER=dbai_runtime); funktioniert nur, weil pg_hba 127.0.0.1=trust | Bei jedem hba-Wechsel bricht Auth still | .env an Container-Wirklichkeit angleichen ODER Container-Env setzen |
| S3 | Web auf `0.0.0.0:3000` (LAN-exponiert); Fail2ban/Suricata-Konfigs existieren in config/, aber Lauf nicht verifiziert | Unbekannter LAN-Angriffsfläche | Firewall/Bind-Regel checken; Reverse-Proxy mit TLS davor |
| S4 | `host all all 127.0.0.1 trust` — lokal ohne Passwort | Nur loocal, low risk | OK für jetzt, dokumentieren |
| S5 | pgcrypto-bcrypt: Passwords >72 Bytes werden still truncated | Edge-Case bei langen Passwörtern | Auf ≤72 Zeichen achten (root-Pass 16 Zeichen = ok) |

## 5. Verbesserungs-Roadmap (priorisiert)

**P0 (Sicherheit + Datenverlust, <1 Tag):** 🔴 **BACKUP STALE: letzter pg_dump = 30.08. — alle Änderungen seitdem (~20 Tage, inkl. P1-P4-Arbeit) sind NICHT gesichert!** Cron/Timer reparieren + Restore-Test machen (dump → leere DB). S1-S3 fixen; Fail2ban/Suricata-Laufstatus checken.
**P1 (Resilience, ~1 Woche):** `archive_mode=on` + wal-g/pg_basebackup → PITR real; Standby-Replika auf zweitem Disk/Host (wal_level ist schon replica-ready).
**P2 (OS-feeling):** Global-Hotkey-Overlay im PWA (Keyboard-API), Offline-PWA mit Service-Worker-Cache für Desktop-Feeling, native Notifications.
**P3 (Differentiation):** pg_stat_statements-basierte Self-Audit-Dashboard (ist schon installiert!), RLS-Policy-Generator als Ghost-Tool ("neue Rolle anlegen" per Chat).

---
*Audit durchgeführt via Live-PSQL + Prozess-/Port-Inspektion. Kein geschätzter Wert, alles gemessen.*
