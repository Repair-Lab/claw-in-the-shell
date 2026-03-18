-- ==========================================================================
-- DBAI Knowledge Session — v0.10.7 (Ghost Mail E-Mail Feature)
-- Datum: 2026-03-17
-- ==========================================================================

-- Changelog
INSERT INTO dbai_knowledge.changelog (version, change_type, title, description, affected_files, author)
VALUES
('0.10.7', 'feature', 'Ghost Mail — E-Mail Client mit Ghost LLM',
 'Kompletter E-Mail Client mit Posteingang, Postausgang, Entwürfe, Ghost-LLM-Integration zum Verfassen/Verbessern/Antworten. 13 API-Endpoints, Frontend-Komponente GhostMail.jsx, DB-Tabellen existierten bereits (email_accounts, inbox, outbox).',
 ARRAY['web/server.py','frontend/src/api.js','frontend/src/components/apps/GhostMail.jsx','frontend/src/components/Desktop.jsx','README.md'],
 'ghost-agent')
ON CONFLICT DO NOTHING;

INSERT INTO dbai_knowledge.changelog (version, change_type, title, description, affected_files, author)
VALUES
('0.10.7', 'fix', 'Static-Files-Mount überschattete API-Routen',
 'app.mount("/", StaticFiles(..., html=True)) auf Zeile 6294 war VOR den Mail/Power/Workshop-Endpoints definiert. Dadurch fing der SPA-Catch-All alle Requests nach Zeile 6294 ab → 404 für alle danach definierten API-Routen. Fix: Mount-Block ans Datei-Ende verschoben (nach allen @app-Dekoratoren).',
 ARRAY['web/server.py'],
 'ghost-agent')
ON CONFLICT DO NOTHING;

INSERT INTO dbai_knowledge.changelog (version, change_type, title, description, affected_files, author)
VALUES
('0.10.7', 'feature', 'Ghost Mail App-Registrierung in DB',
 'App ghost-mail in dbai_ui.apps registriert: icon=✉️, category=ai, source_target=GhostMail, default_width=1000, default_height=700. APP_COMPONENTS in Desktop.jsx erweitert.',
 ARRAY['schema/51-knowledge-session-v0.10.7.sql','frontend/src/components/Desktop.jsx'],
 'ghost-agent')
ON CONFLICT DO NOTHING;

-- System Memory
INSERT INTO dbai_knowledge.system_memory (category, title, content, tags, author)
VALUES
('architecture', 'Ghost Mail API-Endpoints',
 'Ghost Mail hat 13 API-Endpoints unter /api/mail/*:
- GET /api/mail/accounts — Alle E-Mail-Konten
- POST /api/mail/accounts — Konto hinzufügen
- DELETE /api/mail/accounts/{account_id} — Konto löschen
- GET /api/mail/inbox — Posteingang (mit folder/account_id Filter)
- GET /api/mail/inbox/{mail_id} — E-Mail lesen
- PATCH /api/mail/inbox/{mail_id} — Flags ändern (read/starred/archived/deleted)
- GET /api/mail/outbox — Postausgang
- POST /api/mail/compose — Neue E-Mail als Entwurf
- PATCH /api/mail/outbox/{draft_id} — Entwurf bearbeiten
- DELETE /api/mail/outbox/{draft_id} — Entwurf löschen
- POST /api/mail/send/{draft_id} — E-Mail senden via SMTP
- POST /api/mail/ghost-compose — Ghost LLM schreibt E-Mail
- POST /api/mail/ghost-improve — Ghost LLM verbessert E-Mail
- POST /api/mail/ghost-reply — Ghost LLM schreibt Antwort
- POST /api/mail/sync/{account_id} — IMAP-Sync für Konto

Ghost-LLM nutzt dbai_llm.ask_ghost() mit Rolle "email_writer".',
 ARRAY['ghost-mail','api','email','llm','imap','smtp'],
 'ghost-agent')
ON CONFLICT DO NOTHING;

INSERT INTO dbai_knowledge.system_memory (category, title, content, tags, author)
VALUES
('convention', 'Static-Files-Mount MUSS am Datei-Ende stehen',
 'KRITISCHE KONVENTION: app.mount("/", StaticFiles(..., html=True)) ist ein Catch-All-Route der ALLE Pfade matched. In Starlette/FastAPI werden Routen in Reihenfolge geprüft. Wenn der Mount VOR API-Routen steht, fängt er alle Requests ab → 404 für API-Endpoints. LÖSUNG: Der Static-Files-Mount muss IMMER die LETZTE Route-Definition in server.py sein (direkt vor main()). Gleiches gilt für app.mount("/assets", ...). Neue Endpoints MÜSSEN VOR dem Static-Files-Block eingefügt werden.',
 ARRAY['fastapi','starlette','static-files','routing','critical'],
 'ghost-agent')
ON CONFLICT DO NOTHING;

INSERT INTO dbai_knowledge.system_memory (category, title, content, tags, author)
VALUES
('architecture', 'Ghost Mail Frontend-Komponente',
 'GhostMail.jsx ist eine vollständige E-Mail-App (~500 Zeilen) mit:
- Sidebar: Folder-Navigation (Posteingang, Ungelesen, Markiert, Archiv, Gesendet, Entwürfe) + Konto-Liste
- MessageList: Klickbare E-Mail-Liste mit From/Subject/Preview/Timestamp
- MessageDetail: Volle E-Mail-Ansicht mit Antwort/Weiterleiten/Archiv/Löschen
- ComposeView: Editor mit An/CC/BCC/Betreff/Text + Ghost-LLM-Buttons (Schreiben, Verbessern, Antworten)
- AccountManager: Dialog zum Hinzufügen/Löschen von E-Mail-Konten (IMAP/SMTP)
Import: import GhostMail from "./apps/GhostMail" in Desktop.jsx
APP_COMPONENTS Key: "GhostMail"
source_target in DB: "GhostMail"',
 ARRAY['ghost-mail','frontend','react','component'],
 'ghost-agent')
ON CONFLICT DO NOTHING;

INSERT INTO dbai_knowledge.system_memory (category, title, content, tags, author)
VALUES
('schema_map', 'E-Mail-Tabellen in dbai_event Schema',
 'Drei E-Mail-Tabellen existieren in dbai_event:
1. email_accounts: id(uuid), account_name(UNIQUE), email_address, imap_host, imap_port(993), smtp_host, smtp_port(587), auth_type(password/oauth2/app_password), credentials_ref(fk api_keys), sync_enabled, sync_interval_s(300), sync_state(idle/syncing/error)
2. inbox: id(uuid), account_id(fk), message_id(UNIQUE), from_address/name, to/cc_addresses(text[]), subject, body_text/html, attachments(jsonb), embedding(vector(1536)), auto_summary/tags/priority/category/sentiment, is_read/starred/archived/deleted, ghost_response, received_at
3. outbox: id(uuid), account_id(fk), to/cc/bcc_addresses(text[]), subject, body_text/html, reply_to_id(fk inbox), state(draft/review/approved/sending/sent/failed/cancelled), authored_by(human/ghost/template), ghost_id(fk ghost_models)',
 ARRAY['email','schema','dbai_event','tables'],
 'ghost-agent')
ON CONFLICT DO NOTHING;

-- Build Log
INSERT INTO dbai_knowledge.build_log (build_type, success, duration_ms, description)
VALUES
('schema_migration', true, 2000,
 'v0.10.7: Ghost Mail Feature — 13 API-Endpoints, GhostMail.jsx Frontend, Static-Files-Mount-Fix, App-Registrierung')
ON CONFLICT DO NOTHING;

-- Agent Session
INSERT INTO dbai_knowledge.agent_sessions (version_start, version_end, summary, files_created, files_modified, schemas_added, goals, decisions)
VALUES
('0.10.7', '0.10.7',
 'Ghost Mail E-Mail Feature mit Ghost LLM Integration. 13 API-Endpoints (CRUD für Accounts/Inbox/Outbox, Ghost-Compose/Improve/Reply, SMTP-Send, IMAP-Sync). Frontend GhostMail.jsx mit Sidebar/MessageList/Detail/Compose/AccountManager. Kritischer Bug gefunden: app.mount("/") überschattete alle danach definierten API-Routen → 404. Fix: Mount ans Datei-Ende verschoben.',
 ARRAY['frontend/src/components/apps/GhostMail.jsx','schema/51-knowledge-session-v0.10.7.sql'],
 ARRAY['web/server.py','frontend/src/api.js','frontend/src/components/Desktop.jsx','README.md'],
 ARRAY['schema/51-knowledge-session-v0.10.7.sql'],
 ARRAY['Ghost Mail E-Mail Client implementieren','Ghost LLM Integration für E-Mail-Verfassen','API-404-Bug für Mail-Endpoints beheben','Feature in DB dokumentieren'],
 ARRAY['Bestehende DB-Tabellen (email_accounts, inbox, outbox) wiederverwendet statt neue zu erstellen','Static-Files-Mount ans Datei-Ende verschoben statt Mail-Endpoints vor den Mount','Ghost-LLM Fallback-Text wenn LLM nicht verfügbar statt Error','SMTP-Versand über Standard-Library statt externe Dependency']
)
ON CONFLICT DO NOTHING;

-- Error Pattern
INSERT INTO dbai_knowledge.error_patterns (name, title, error_regex, error_source, severity, category, description, root_cause, solution_short)
VALUES
('static_files_mount_shadowing', 'Static-Files-Mount überschattet API-Routen',
 '404.*Not Found.*(mail|power|workshop|apps)',
 'runtime', 'critical', 'wrong_config',
 'API-Endpoints die nach app.mount("/", StaticFiles(..., html=True)) definiert werden, geben 404 zurück. Der SPA-Catch-All fängt alle Requests ab bevor sie die API-Handler erreichen.',
 'app.mount("/", StaticFiles(directory=..., html=True)) steht in server.py VOR den API-Dekoratoren. Starlette/FastAPI prüft Routen in Reihenfolge der Registrierung. Mount auf "/" matched alle Pfade.',
 'Static-Files-Mount ans Ende von server.py verschieben (nach allen @app.get/@app.post Dekoratoren, direkt vor main()). Keine neue Endpoints NACH dem Mount-Block einfügen.')
ON CONFLICT (name) DO NOTHING;

-- Known Issue
INSERT INTO dbai_knowledge.known_issues (title, description, severity, status, affected_files, workaround, resolution)
VALUES
('Ghost Mail API: 404 für alle Endpoints nach Static-Files-Mount',
 'Alle API-Endpoints die in server.py NACH app.mount("/", StaticFiles(..., html=True)) definiert waren, gaben 404 zurück. Betroffen: /api/mail/*, /api/power/*, /api/workshop/custom-tables/*, /api/apps/*/settings/*.',
 'critical', 'resolved',
 ARRAY['web/server.py'],
 'Endpoints VOR den Mount-Block verschieben oder Mount-Block ans Datei-Ende setzen.',
 'Static-Files-Mount-Block von Zeile 6287-6337 ans Datei-Ende verschoben (direkt vor main()). Alle API-Endpoints werden jetzt VOR dem Catch-All registriert.')
ON CONFLICT DO NOTHING;
