-- ============================================================================
-- DBAI Schema 32: Diagnostic Session Erkenntnisse
-- Datum: 2026-03-16
-- Beschreibung: Erkenntnisse aus der Diagnose-Session:
--   - Internal Server Error → Server war nicht gestartet
--   - Passwort root/dbai2026 → funktioniert (SHA256 via dbai_ui.login())
--   - psql hängt bei Table-Queries → Connection-Pool / Pager-Konflikte
--   - Terminal-Sessions werden nach langen Sessions unresponsiv
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. KNOWN ISSUES: Neue Erkenntnisse aus der Diagnose
-- ============================================================================

-- Issue 1: Server startet nicht automatisch
INSERT INTO dbai_knowledge.known_issues (
    title, description, severity, status,
    affected_files, workaround, metadata
) VALUES (
    'Server startet nicht automatisch ohne systemd-Service',
    'Der Uvicorn-Server (web.server:app) wird nicht automatisch gestartet. '
    'Nach einem System-Neustart oder Crash muss der Server manuell mit '
    '`python3 -m uvicorn web.server:app --host 0.0.0.0 --port 3000 --reload --reload-dir web` '
    'gestartet werden. Dies führt zu "Internal Server Error" im Frontend, '
    'da alle API-Calls fehlschlagen wenn kein Backend läuft.',
    'high',
    'workaround',
    ARRAY['scripts/start_web.sh', 'web/server.py'],
    'Manuell starten: cd /home/worker/DBAI && python3 -m uvicorn web.server:app --host 0.0.0.0 --port 3000 --reload --reload-dir web &',
    '{"diagnosed_at": "2026-03-16", "root_cause": "kein systemd-service konfiguriert", "symptom": "Frontend zeigt Internal Server Error", "fix_planned": "systemd-Unit dbai-web.service in Stufe 1 erstellt aber nicht aktiviert"}'::jsonb
);

-- Issue 2: psql Direktverbindung kann hängen
INSERT INTO dbai_knowledge.known_issues (
    title, description, severity, status,
    affected_files, workaround, metadata
) VALUES (
    'psql-Direktverbindung hängt bei Table-Queries',
    'Direkte psql-Verbindungen zur DB können bei Tabellen-Abfragen hängen bleiben, '
    'während der Web-Server über seinen eigenen Connection-Pool (asyncpg) problemlos funktioniert. '
    'Ursachen: (1) Der PAGER (less/more) blockiert nicht-interaktive Ausgaben — Lösung: -t Flag oder PAGER=cat verwenden. '
    '(2) Mögliche Table-Locks durch lang-laufende Transaktionen. '
    '(3) Connection-Pool-Erschöpfung bei zu vielen gleichzeitigen psql-Sessions. '
    'SELECT 1 funktioniert immer, da keine Table-Locks betroffen.',
    'medium',
    'workaround',
    ARRAY['config/postgresql.conf', 'web/server.py'],
    'Immer ``timeout 10 sudo -u postgres psql -d dbai -t -A -c "QUERY"`` verwenden. '
    'Flags: -t (tuple only), -A (unaligned), wrapped in timeout. '
    'Für interaktiv: PAGER=cat sudo -u postgres psql -d dbai',
    '{"diagnosed_at": "2026-03-16", "root_cause": "pager_blocking_and_potential_locks", "symptom": "psql Befehle hängen, API funktioniert normal", "connection_pool": "asyncpg via web/server.py", "flags_required": "-t -A mit timeout"}'::jsonb
);

-- Issue 3: Terminal-Sessions werden unresponsiv
INSERT INTO dbai_knowledge.known_issues (
    title, description, severity, status,
    affected_files, workaround, metadata
) VALUES (
    'Terminal-Sessions werden nach langen Sessions unresponsiv',
    'Nach einer längeren Diagnose-Session mit vielen hintereinander ausgeführten Befehlen '
    'können Terminal-Sessions komplett einfrieren. Selbst einfache Befehle wie echo und ps '
    'geben nur ^C zurück. Ursache: Nicht abgeschlossene Prozesse (z.B. hängende psql-Verbindungen) '
    'blockieren die PTY-Session. Lösung: Neue Background-Terminal-Session starten.',
    'low',
    'workaround',
    ARRAY[]::text[],
    'Neue Background-Terminal-Session starten statt die bestehende zu nutzen. '
    'Hängende Prozesse mit ``kill`` beenden. PTY-Buffer zurücksetzen mit ``reset``.',
    '{"diagnosed_at": "2026-03-16", "root_cause": "pty_blocking_by_zombie_processes", "symptom": "alle Befehle geben ^C zurück", "recovery": "neue Shell starten"}'::jsonb
);

-- ============================================================================
-- 2. SYSTEM MEMORY: Operationales Wissen aus der Diagnose
-- ============================================================================

-- Memory 1: Server-Neustart-Prozedur
INSERT INTO dbai_knowledge.system_memory (
    category, title, content,
    structured_data, related_modules, related_schemas, tags,
    valid_from, priority, author
) VALUES (
    'operational',
    'Server-Neustart-Prozedur',
    'Wenn der DBAI-Server nicht erreichbar ist (Frontend zeigt "Internal Server Error"):\n'
    '1. Prüfen: curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/api/system/status\n'
    '2. Wenn nicht 200/401: Server starten:\n'
    '   cd /home/worker/DBAI && python3 -m uvicorn web.server:app --host 0.0.0.0 --port 3000 --reload --reload-dir web &\n'
    '3. Verifizieren: curl -s http://localhost:3000/api/auth/login -X POST -H "Content-Type: application/json" -d ''{"username":"root","password":"dbai2026"}''\n'
    '4. Erwartetes Ergebnis: HTTP 200 mit Token und Session-ID',
    '{"port": 3000, "command": "python3 -m uvicorn web.server:app --host 0.0.0.0 --port 3000 --reload --reload-dir web", "check_command": "curl -s -o /dev/null -w \"%{http_code}\" http://localhost:3000/api/system/status", "process_name": "uvicorn", "restart_time_seconds": 3}'::jsonb,
    ARRAY['web/server.py', 'scripts/start_web.sh'],
    ARRAY['web'],
    ARRAY['operations', 'restart', 'server', 'uvicorn', 'troubleshooting'],
    '0.8.0', 95, 'diagnostic-session'
);

-- Memory 2: Login-Verifizierung
INSERT INTO dbai_knowledge.system_memory (
    category, title, content,
    structured_data, related_modules, related_schemas, tags,
    valid_from, priority, author
) VALUES (
    'workflow',
    'Login-System Verifizierung',
    'Das DBAI-Login-System verwendet SHA256-Password-Hashing.\n'
    'Standard-Credentials: root / dbai2026\n'
    'Auth-Flow:\n'
    '1. Frontend (LoginScreen.jsx) → POST /api/auth/login mit {username, password}\n'
    '2. Backend (server.py:510) → db_execute_rt("SELECT dbai_ui.login($1,$2,$3,$4)", [user,pass,ip,ua])\n'
    '3. DB-Funktion dbai_ui.login() → SHA256-Hash vergleich, Session erstellen\n'
    '4. Response: {token, session_id, user: {username, display_name, role, is_admin}}\n'
    '5. Frontend speichert Token in localStorage("dbai_token")\n'
    '6. Alle weiteren Requests: Authorization: Bearer <token>\n\n'
    'Bei 401-Fehler: Token wird gelöscht, Seite wird neu geladen → Login-Screen.\n'
    'Wenn "Passwort funktioniert nicht": Server-Status prüfen! Meist liegt es daran, dass der Server nicht läuft.',
    '{"default_user": "root", "default_password": "dbai2026", "hash_algorithm": "sha256", "token_storage": "localStorage(dbai_token)", "cookie": "dbai_session (httponly)", "auth_endpoint": "/api/auth/login", "db_function": "dbai_ui.login()", "verified_at": "2026-03-16", "verified_result": "200 OK"}'::jsonb,
    ARRAY['web/server.py', 'frontend/src/api.js', 'frontend/src/components/LoginScreen.jsx', 'frontend/src/App.jsx'],
    ARRAY['dbai_ui'],
    ARRAY['authentication', 'login', 'password', 'sha256', 'token', 'security'],
    '0.8.0', 90, 'diagnostic-session'
);

-- Memory 3: DB-Verbindungsdiagnose
INSERT INTO dbai_knowledge.system_memory (
    category, title, content,
    structured_data, related_modules, related_schemas, tags,
    valid_from, priority, author
) VALUES (
    'operational',
    'PostgreSQL Verbindungsdiagnose',
    'Diagnose-Ergebnisse für DB-Konnektivität:\n\n'
    '1. pg_isready: Immer zuverlässig für Basic-Check\n'
    '   sudo -u postgres pg_isready -d dbai\n\n'
    '2. psql mit timeout und Flags verwenden:\n'
    '   timeout 10 sudo -u postgres psql -d dbai -t -A -c "QUERY"\n'
    '   -t = tuple only (keine Header)\n'
    '   -A = unaligned (keine Padding-Zeichen)\n'
    '   timeout = Absicherung gegen Hänger\n\n'
    '3. Hängende Connections prüfen:\n'
    '   SELECT pid, state, query, age(clock_timestamp(), query_start) AS duration\n'
    '   FROM pg_stat_activity WHERE datname=''dbai'' AND state != ''idle'';\n\n'
    '4. Web-Server nutzt asyncpg Connection-Pool (db_query_rt/db_execute_rt für RLS,\n'
    '   db_query/db_execute für Admin). Dieser Pool funktioniert unabhängig von psql.\n\n'
    '5. Wenn psql hängt aber API funktioniert: Pager-Problem, kein DB-Problem.',
    '{"check_commands": {"basic": "sudo -u postgres pg_isready -d dbai", "query": "timeout 10 sudo -u postgres psql -d dbai -t -A -c \"SELECT 1\"", "activity": "timeout 10 sudo -u postgres psql -d dbai -t -A -c \"SELECT pid,state,query FROM pg_stat_activity WHERE datname=''dbai'' AND state!=''idle'';\""}, "connection_pools": {"runtime_query": "db_query_rt", "runtime_execute": "db_execute_rt", "admin_query": "db_query", "admin_execute": "db_execute"}, "common_issues": ["pager_blocking", "connection_pool_exhaustion", "table_locks"]}'::jsonb,
    ARRAY['web/server.py', 'config/postgresql.conf'],
    ARRAY['pg_stat_activity'],
    ARRAY['database', 'postgresql', 'psql', 'connection', 'diagnosis', 'troubleshooting'],
    '0.8.0', 85, 'diagnostic-session'
);

-- Memory 4: Frontend-Backend Kommunikation
INSERT INTO dbai_knowledge.system_memory (
    category, title, content,
    structured_data, related_modules, related_schemas, tags,
    valid_from, priority, author
) VALUES (
    'architecture',
    'Frontend-Backend Kommunikationsfluss',
    'DBAI Kommunikationsarchitektur:\n\n'
    'Frontend (React/Vite, Port 5173) → Backend (FastAPI/Uvicorn, Port 3000)\n\n'
    'API-Client (api.js):\n'
    '- Base: request(method, path, data) mit Bearer-Token-Auth\n'
    '- 401-Handler: Token löschen + window.location.reload()\n'
    '- Endpoints: /api/auth/*, /api/desktop/*, /api/system/*, /api/ghost/*\n\n'
    '"Nur lokale Verbindungen. Keine externen APIs." ist ein UI-Text in LoginScreen.jsx,\n'
    'KEIN Fehlersymptom. Es ist eine bewusste Design-Entscheidung und Security-Feature.\n\n'
    'Wenn Frontend "Internal Server Error" zeigt:\n'
    '1. Backend nicht gestartet → Alle Requests scheitern\n'
    '2. Token abgelaufen → 401 → Auto-Reload → Login-Screen\n'
    '3. DB nicht erreichbar → 500 auf spezifischen Endpoints',
    '{"frontend": {"framework": "React", "bundler": "Vite", "port": 5173, "entry": "frontend/src/main.jsx"}, "backend": {"framework": "FastAPI", "server": "Uvicorn", "port": 3000, "entry": "web/server.py"}, "auth_flow": "Bearer Token in localStorage", "websocket": "/ws für Live-Updates", "design_texts": {"login_footer": "Nur lokale Verbindungen. Keine externen APIs."}}'::jsonb,
    ARRAY['frontend/src/api.js', 'frontend/src/App.jsx', 'web/server.py'],
    ARRAY['dbai_ui'],
    ARRAY['architecture', 'frontend', 'backend', 'api', 'communication', 'auth'],
    '0.8.0', 80, 'diagnostic-session'
);

-- Memory 5: Diagnose-Zusammenfassung
INSERT INTO dbai_knowledge.system_memory (
    category, title, content,
    structured_data, related_modules, related_schemas, tags,
    valid_from, priority, author
) VALUES (
    'operational',
    'Diagnose-Session 2026-03-16: Server-Ausfall & Login',
    'Zusammenfassung der Diagnose-Session vom 2026-03-16:\n\n'
    'GEMELDETE PROBLEME:\n'
    '1. "Internal Server Error" → Server war nicht gestartet (kein systemd-Service aktiv)\n'
    '2. "Passwort funktioniert nicht" → Passwort root/dbai2026 ist korrekt, Login scheiterte weil Server down\n'
    '3. "Nur lokale Verbindungen" → Ist ein UI-Text, kein Fehler (LoginScreen.jsx Zeile ~70)\n\n'
    'DIAGNOSE-ERGEBNISSE:\n'
    '- pg_isready: OK (DB läuft)\n'
    '- Server: Nicht gestartet → Manuell mit uvicorn gestartet\n'
    '- curl POST /api/auth/login: 200 OK mit gültigem Token\n'
    '- Alle API-Endpoints: 200 OK nach Server-Start\n'
    '- psql: Hängt manchmal bei Table-Queries (Pager-Problem, -t -A Flags lösen es)\n'
    '- pg_stat_activity: Keine hängenden Queries gefunden\n\n'
    'ROOT CAUSE: Server war nicht gestartet. Kein Code-Bug.\n\n'
    'MASSNAHMEN:\n'
    '- Server manuell neu gestartet\n'
    '- Login erfolgreich verifiziert\n'
    '- Erkenntnisse in DB dokumentiert (Schema 32)',
    '{"incident_date": "2026-03-16", "reported_issues": ["Internal Server Error", "Passwort funktioniert nicht", "Nur lokale Verbindungen"], "root_causes": {"internal_server_error": "server_not_running", "password_not_working": "server_not_running_not_password_issue", "local_connections_only": "ui_text_not_error"}, "resolution": "server_restarted_manually", "verified": true, "password_verified": "root/dbai2026 → 200 OK", "affected_users": ["root"], "downtime_estimate": "unknown", "prevention": "systemd-service aktivieren"}'::jsonb,
    ARRAY['web/server.py', 'scripts/start_web.sh', 'frontend/src/components/LoginScreen.jsx'],
    ARRAY['dbai_ui', 'web'],
    ARRAY['incident', 'diagnosis', 'server-outage', 'login', 'postmortem'],
    '0.8.0', 100, 'diagnostic-session'
);

-- ============================================================================
-- 3. CHANGELOG: Diagnose-Session dokumentieren
-- ============================================================================

INSERT INTO dbai_knowledge.changelog (
    version, change_type, title, description,
    affected_files, author
) VALUES (
    '0.8.1',
    'fix',
    'Diagnose-Session: Server-Ausfall behoben & dokumentiert',
    'Server war nicht gestartet → manueller Neustart. Passwort root/dbai2026 verifiziert. '
    'Drei neue known_issues dokumentiert (Server-Autostart, psql-Hänger, Terminal-Unresponsiveness). '
    'Fünf system_memory Einträge mit operationalem Wissen erstellt (Neustart-Prozedur, '
    'Login-Verifizierung, DB-Diagnose, Frontend-Backend-Kommunikation, Incident-Zusammenfassung).',
    ARRAY['schema/32-diagnostic-session-seed.sql', 'web/server.py', 'scripts/start_web.sh'],
    'diagnostic-session'
),
(
    '0.8.1',
    'docs',
    'Operationales Wissen in system_memory dokumentiert',
    'Server-Neustart-Prozedur, Login-System-Verifizierung, PostgreSQL-Verbindungsdiagnose, '
    'Frontend-Backend-Kommunikationsfluss und Incident-Zusammenfassung als system_memory '
    'Einträge persistiert. Dient als Wissensbasis für zukünftige Diagnose-Sessions.',
    ARRAY['schema/32-diagnostic-session-seed.sql'],
    'diagnostic-session'
);

COMMIT;
