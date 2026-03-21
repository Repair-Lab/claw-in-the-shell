-- ============================================================================
-- DBAI v0.14.1 — Code Quality & Security Hardening
-- ============================================================================
-- 14 Fixes: Security, Performance, Reliability, Code Quality
-- Ausgeführt als: dbai_system (Superuser)
-- ============================================================================

BEGIN;

-- ──────────────────────────────────────────────────────────────────────────
-- 1) system_memory — Dokumentation aller Fixes
-- ──────────────────────────────────────────────────────────────────────────

-- Fix-Übersicht als Architektur-Dokument
INSERT INTO dbai_knowledge.system_memory (category, title, content, structured_data, related_modules, related_schemas, tags, priority, author)
VALUES (
    'architecture',
    'v0.14.1 Code Quality & Security Hardening',
    'Umfassende Code-Qualitäts-Überarbeitung mit 14 Fixes in 4 Kategorien: ' ||
    '(1) Security: require_admin auf 3 destruktiven Endpoints, Download-Endpoint repariert, ' ||
    'Base64 durch Fernet-Verschlüsselung ersetzt, LLM-State mit RLock geschützt. ' ||
    '(2) Performance: psutil.cpu_percent in asyncio.to_thread, N+1 CPU-INSERT als Batch, ' ||
    'WebSocket-Broadcast mit asyncio.gather, Health-Check async. ' ||
    '(3) Reliability: DBPool Checkout/Checkin-Pattern mit connect_timeout, ' ||
    'Lifespan ruft _llm_server_stop() beim Shutdown, Rate-Limit-Store mit Lock + Cleanup. ' ||
    '(4) Code Quality: 12 stille Exception-Handler mit Logger versehen.',
    '{
        "version": "0.14.1",
        "total_fixes": 14,
        "categories": {
            "security": 4,
            "performance": 4,
            "reliability": 3,
            "code_quality": 1
        },
        "p0_critical": [
            "require_admin auf DELETE /api/llm/models, POST /api/store/uninstall, GET /api/fs/browse",
            "Download-Endpoint if-False Dead-Code durch asyncio.create_task ersetzt",
            "Base64-Encoding durch Fernet-Verschlüsselung ersetzt (4 Stellen)",
            "LLM Global State durch threading.RLock geschützt"
        ],
        "p1_important": [
            "psutil.cpu_percent(interval=0.3) in asyncio.to_thread verlagert",
            "N+1 CPU-INSERT durch Batch-INSERT ersetzt",
            "DBPool: Checkout/Checkin + connect_timeout=5s",
            "Lifespan: _llm_server_stop() beim Shutdown",
            "Rate-Limit-Store: asyncio.Lock + periodischer Cleanup"
        ],
        "p2_medium": [
            "12 stille except-Handler mit logger.exception/warning versehen",
            "WebSocket-Broadcast: sequentiell → asyncio.gather",
            "Health-Check: sync DB-Call → asyncio.to_thread"
        ],
        "dependencies_added": ["cryptography>=42.0.0"],
        "files_changed": ["web/server.py", "requirements.txt"],
        "encryption": {
            "algorithm": "Fernet (AES-128-CBC + HMAC-SHA256)",
            "key_location": "config/.fernet.key",
            "key_permissions": "0600",
            "fallback": "Base64 wenn cryptography nicht installiert"
        }
    }'::jsonb,
    ARRAY['web/server.py', 'requirements.txt'],
    ARRAY['dbai_llm', 'dbai_ui', 'dbai_system', 'dbai_core'],
    ARRAY['security', 'performance', 'reliability', 'code-quality', 'v0.14.1'],
    9,
    'copilot'
);

-- Security Fix: require_admin
INSERT INTO dbai_knowledge.system_memory (category, title, content, structured_data, related_modules, tags, priority, author)
VALUES (
    'convention',
    'require_admin() Pflicht für destruktive Endpoints',
    'Alle Endpoints die Daten löschen, System-Konfiguration ändern oder das Dateisystem exponieren ' ||
    'MÜSSEN require_admin(session) als erste Zeile nach dem Docstring aufrufen. ' ||
    'Gefixt in v0.14.1: DELETE /api/llm/models/{id}, POST /api/store/uninstall, GET /api/fs/browse.',
    '{
        "rule": "Jeder destruktive oder system-kritische Endpoint braucht require_admin(session)",
        "affected_endpoints": [
            "DELETE /api/llm/models/{model_id}",
            "POST /api/store/uninstall",
            "GET /api/fs/browse"
        ],
        "helper_location": "web/server.py:require_admin()",
        "http_status_on_fail": 403
    }'::jsonb,
    ARRAY['web/server.py'],
    ARRAY['security', 'admin', 'authorization', 'convention'],
    10,
    'copilot'
);

-- Security Fix: Fernet Encryption
INSERT INTO dbai_knowledge.system_memory (category, title, content, structured_data, related_modules, tags, priority, author)
VALUES (
    'convention',
    'API-Key Verschlüsselung via Fernet',
    'Alle API-Keys und Tokens werden mit Fernet (AES-128-CBC + HMAC-SHA256) verschlüsselt. ' ||
    'Schlüssel liegt in config/.fernet.key (chmod 0600). Helfer: encrypt_secret() / decrypt_secret(). ' ||
    'Ersetzt Base64-Encoding das KEINE Verschlüsselung war.',
    '{
        "encrypt_function": "encrypt_secret(plaintext: str) -> str",
        "decrypt_function": "decrypt_secret(ciphertext: str) -> str",
        "affected_columns": [
            "dbai_llm.llm_providers.api_key_enc",
            "dbai_ui.users.github_token_enc"
        ],
        "affected_endpoints": [
            "PATCH /api/llm/providers/{key}",
            "PATCH /api/settings/profile",
            "POST /api/setup/complete"
        ]
    }'::jsonb,
    ARRAY['web/server.py'],
    ARRAY['security', 'encryption', 'fernet', 'api-keys'],
    10,
    'copilot'
);

-- Performance Fix: DBPool
INSERT INTO dbai_knowledge.system_memory (category, title, content, structured_data, related_modules, tags, priority, author)
VALUES (
    'architecture',
    'DBPool Checkout/Checkin Pattern',
    'Der DBPool verwendet jetzt ein Checkout/Checkin-Pattern mit getrennten _idle und _in_use Listen. ' ||
    'Verhindert dass zwei Threads gleichzeitig dieselbe Connection nutzen. ' ||
    'connect_timeout=5s verhindert endloses Hängen bei DB-Ausfall. ' ||
    'Alle db_query/db_execute Helfer nutzen try/finally mit return_connection().',
    '{
        "pool_type": "Checkout/Checkin",
        "max_connections": 10,
        "connect_timeout_sec": 5,
        "wait_timeout_sec": 5,
        "methods": ["get_connection()", "return_connection(conn)", "close_all()"],
        "thread_safe": true
    }'::jsonb,
    ARRAY['web/server.py'],
    ARRAY['database', 'pool', 'thread-safety', 'reliability'],
    8,
    'copilot'
);

-- ──────────────────────────────────────────────────────────────────────────
-- 2) changelog — Alle Änderungen dokumentieren
-- ──────────────────────────────────────────────────────────────────────────

INSERT INTO dbai_knowledge.changelog (version, change_type, title, description, affected_files, author)
VALUES
('0.14.1', 'security', 'require_admin auf 3 Endpoints',
 'DELETE /api/llm/models/{id}, POST /api/store/uninstall und GET /api/fs/browse erfordern jetzt Admin-Rechte.',
 ARRAY['web/server.py'], 'copilot'),

('0.14.1', 'security', 'Download-Endpoint repariert',
 'if-False Dead-Code im Download-Endpoint durch echten Background-Task (asyncio.create_task + to_thread) ersetzt. Neuer Status-Endpoint GET /api/llm/download/{task_id}.',
 ARRAY['web/server.py'], 'copilot'),

('0.14.1', 'security', 'Fernet-Verschlüsselung für API-Keys',
 'Base64-Encoding durch Fernet (AES-128-CBC + HMAC-SHA256) ersetzt. Betrifft: LLM-Provider API-Keys, GitHub-Tokens, Setup-Wizard. Dependency: cryptography>=42.0.0.',
 ARRAY['web/server.py', 'requirements.txt'], 'copilot'),

('0.14.1', 'security', 'LLM Global State Thread-Safety',
 '_llm_server_start/stop durch threading.RLock geschützt. Verhindert Race-Conditions bei gleichzeitigen Modell-Wechseln.',
 ARRAY['web/server.py'], 'copilot'),

('0.14.1', 'performance', 'Blocking I/O aus Event-Loop entfernt',
 'psutil.cpu_percent(interval=0.3) → asyncio.to_thread. Health-Check DB-Query → asyncio.to_thread. WebSocket-Broadcast → asyncio.gather.',
 ARRAY['web/server.py'], 'copilot'),

('0.14.1', 'performance', 'N+1 CPU-INSERT → Batch',
 'Einzelne INSERT pro CPU-Core durch einen Batch-INSERT ersetzt. Reduziert DB-Roundtrips von N auf 1.',
 ARRAY['web/server.py'], 'copilot'),

('0.14.1', 'fix', 'DBPool Checkout/Checkin + connect_timeout',
 'DBPool refaktoriert mit exklusivem Connection-Checkout, connect_timeout=5s, und try/finally return_connection in allen Helfern.',
 ARRAY['web/server.py'], 'copilot'),

('0.14.1', 'fix', 'Lifespan: LLM-Server Shutdown',
 '_llm_server_stop() wird jetzt beim Server-Shutdown aufgerufen. Verhindert verwaiste llama-server Prozesse und VRAM-Leaks.',
 ARRAY['web/server.py'], 'copilot'),

('0.14.1', 'fix', 'Rate-Limit-Store Memory-Leak behoben',
 'asyncio.Lock schützt Store vor Race-Conditions. Periodischer Cleanup entfernt inaktive IPs bei >500 Einträgen.',
 ARRAY['web/server.py'], 'copilot'),

('0.14.1', 'fix', 'Silent Exception Handler mit Logging',
 '12 stille except-Handler (7× return [], 5× pass) mit logger.exception/warning versehen. Betrifft Workshop-Endpoints und Setup-Wizard.',
 ARRAY['web/server.py'], 'copilot');

COMMIT;
