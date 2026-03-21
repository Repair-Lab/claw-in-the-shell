ERLEDIGT (v0.12.11) — 6 Kritische Security-Fixes
#	Fix	Status
1	Shell-Injection /api/services/install → command-Feld entfernt, server-seitige Lookup-Tabelle, shell=False, require_admin	✅
2	Shell-Injection /api/terminal/exec → require_admin, shell=False+shlex.split, Regex-Blocklist (12 Patterns)	✅
3	SQL-Injection SQL Explorer → Spaltenvalidierung gegen information_schema.columns	✅
4	SQL Explorer Admin-Pool → Runtime-Pool (db_query→db_query_rt, db_execute→db_execute_rt) + require_admin	✅
5	SHA-256 ohne Salt → pgcrypto crypt()/gen_salt('bf') (bcrypt)	✅
6	User-CRUD ohne Admin-Check → require_admin() auf alle 4 Endpoints	✅

ERLEDIGT (v0.13.0) — Mobile Bridge: 5-Dimensionales System
#	Feature	Status
1	Schema dbai_net mit 11 Tabellen + 4 Views	✅
2	5 Boot-Dimensionen (Portable, Live, SSD, USB-C Link, Ghost-Net Hotspot)	✅
3	USB-Gadget Config (dwc2, g_ether, RNDIS/ECM)	✅
4	Hotspot Config (hostapd, dnsmasq, WPA2)	✅
5	mDNS/Avahi (ghost.local Discovery)	✅
6	Mobile Device Registry (iOS, Android, Tablets)	✅
7	Sensor Pipeline (GPS, Kamera, Audio → PostgreSQL → pgvector)	✅
8	PWA (manifest.json, Service Worker, Install Prompt, Offline-Seite)	✅
9	Hardware Profiles (RPi Zero 2W, Radxa Zero)	✅
10	12 neue API-Endpoints (/api/mobile-bridge/*)	✅
11	DHCP Lease Tracking + Connection Sessions	✅
12	Demo-Script für Alexander Zuchowski in system_memory	✅

KRITISCH — Sofort fixen
#	Problem	Ort	Impact
1	Shell-Injection via /api/services/install — Client sendet command direkt an shell=True	server.py:3426	Remote Code Execution
2	Shell-Injection via /api/terminal/exec — Blacklist trivial umgehbar, kein Admin-Check	server.py:8550	Remote Code Execution
3	SQL-Injection im SQL Explorer — Spaltennamen aus User-Input direkt in Query	server.py:5035	Datenbank-Übernahme
4	SQL Explorer nutzt Admin-Pool statt Runtime-Pool → RLS greift nicht	server.py:4999	Privilege Escalation
5	SHA-256 ohne Salt für Passwörter — in Sekunden knackbar	server.py:5240	Account-Übernahme
6	User-CRUD ohne Admin-Check — jeder User kann Admins anlegen/löschen	server.py:5207	Privilege Escalation
HOCH — Sollte bald folgen
#	Problem	Ort	Impact
7	Connection-Pool Race Condition — get_connection() teilt Connections zwischen Threads	server.py:97	Abgestürzte Queries, Datenverlust
8	API-Keys nur Base64-encoded — keine echte Verschlüsselung	server.py:5402	Klartext-Keys bei DB-Leak
9	time.sleep() blockiert Event-Loop an mehreren Stellen	server.py:1102	Alle Requests hängen
10	Keine Error Boundary pro Fenster — eine App crasht → ganzer Desktop schwarz	Desktop.jsx	UX-Totalausfall
11	Fehlende RLS auf desktop_nodes, desktop_scene, agent_instances	Schema	Security-Bypass
12	Health-Check prüft nur DB — WS-Bridge, LLM-Server, Disk werden ignoriert	server.py:1538	Stille Teilausfälle
MITTEL — Optimierungspotential
#	Problem	Ort	Impact
13	50+ except: pass verschlucken Fehler unsichtbar	Überall in server.py	Unsichtbare Bugs
14	Synchrone DB-Aufrufe in async def — blockiert Event-Loop	Alle Endpoints	Performance
15	Rate-Limiter Memory-Leak — _rate_limit_store wächst unbegrenzt	server.py:609	Memory-Exhaustion
16	Vacuum-Schedule fehlt für dbai_ui, dbai_llm, dbai_knowledge	09-vacuum-schedule.sql	Tote Tupel, Bloat
17	Doppelte Schema-Nummerierung (zwei 29er-Dateien)	Schema-Ordner	Nicht-deterministische Migration
18	Fehlender Index auf sessions.expires_at	Schema	Cleanup wird Full-Table-Scan
19	Kein Responsive Design — null @media-Queries	global.css	Mobile unbenutzbar
20	Hardcodierte CUDA-Pfade — bricht auf jedem anderen System	server.py:35	Nicht-portabel
21	server.py = 10.200 Zeilen God Object — sollte in Router-Module aufgeteilt werden	server.py	Wartbarkeit
22	Cookie fehlt Secure-Flag	server.py:787	Token im Klartext über HTTP
23	Fehlende AbortController im API-Client → alte Requests laufen bei Unmount weiter	api.js	State-Corruption