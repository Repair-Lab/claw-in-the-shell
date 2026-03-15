-- =============================================================================
-- DBAI Schema 17: Seed Data — Ghost-System & Desktop UI
-- Vorgeladene Daten für das Betriebssystem-Erlebnis
-- =============================================================================

-- =============================================================================
-- 1. GHOST MODELS — Verfügbare KI-Modelle
-- =============================================================================

INSERT INTO dbai_llm.ghost_models
    (name, display_name, model_path, model_type, provider,
     parameter_count, quantization, context_size, max_tokens,
     required_vram_mb, required_ram_mb, requires_gpu,
     capabilities, supported_languages, parameters) VALUES

('qwen2.5-7b-instruct',
 'Qwen 2.5 — 7B Instruct',
 'models/Qwen2.5-7B-Instruct.Q4_K_M.gguf',
 'chat', 'llama.cpp',
 '7B', 'Q4_K_M', 8192, 4096,
 6000, 8000, FALSE,
 ARRAY['chat', 'code', 'analysis', 'german', 'tool_use'],
 ARRAY['de', 'en', 'zh'],
 '{"temperature": 0.7, "top_p": 0.9, "repeat_penalty": 1.1}'::JSONB),

('llama3-8b-instruct',
 'Llama 3 — 8B Instruct',
 'models/Meta-Llama-3-8B-Instruct.Q4_K_M.gguf',
 'chat', 'llama.cpp',
 '8B', 'Q4_K_M', 8192, 4096,
 6000, 8000, FALSE,
 ARRAY['chat', 'reasoning', 'code', 'english'],
 ARRAY['en', 'de'],
 '{"temperature": 0.7, "top_p": 0.9}'::JSONB),

('mistral-7b-instruct',
 'Mistral — 7B Instruct v0.3',
 'models/Mistral-7B-Instruct-v0.3.Q4_K_M.gguf',
 'chat', 'llama.cpp',
 '7B', 'Q4_K_M', 32768, 8192,
 6000, 8000, FALSE,
 ARRAY['chat', 'creative', 'analysis', 'long_context'],
 ARRAY['en', 'de', 'fr'],
 '{"temperature": 0.8, "top_p": 0.95}'::JSONB),

('phi3-mini',
 'Phi-3 Mini — 3.8B',
 'models/Phi-3-mini-4k-instruct.Q4_K_M.gguf',
 'chat', 'llama.cpp',
 '3.8B', 'Q4_K_M', 4096, 2048,
 3000, 4000, FALSE,
 ARRAY['chat', 'fast', 'code', 'sensor_analysis'],
 ARRAY['en'],
 '{"temperature": 0.5, "top_p": 0.9}'::JSONB),

('codestral-22b',
 'Codestral — 22B Code',
 'models/Codestral-22B-v0.1.Q4_K_M.gguf',
 'code', 'llama.cpp',
 '22B', 'Q4_K_M', 32768, 8192,
 14000, 16000, TRUE,
 ARRAY['code', 'sql', 'python', 'bash', 'debugging'],
 ARRAY['en'],
 '{"temperature": 0.2, "top_p": 0.95}'::JSONB),

('nomic-embed-text',
 'Nomic Embed — Text Embeddings',
 'models/nomic-embed-text-v1.5.Q8_0.gguf',
 'embedding', 'llama.cpp',
 '137M', 'Q8_0', 8192, 0,
 500, 1000, FALSE,
 ARRAY['embedding', 'semantic_search', 'rag'],
 ARRAY['en', 'de'],
 '{"batch_size": 512}'::JSONB);

-- =============================================================================
-- 2. GHOST ROLES — Vordefinierte KI-Rollen
-- =============================================================================

INSERT INTO dbai_llm.ghost_roles
    (name, display_name, description, icon, color,
     accessible_schemas, accessible_tables, system_prompt, priority, is_critical) VALUES

('sysadmin',
 'System Administrator',
 'Überwacht Hardware, Prozesse, Speicher. Kann Self-Healing auslösen.',
 '🛡️', '#ff4444',
 ARRAY['dbai_system', 'dbai_core', 'dbai_event', 'dbai_panic'],
 ARRAY['dbai_system.cpu', 'dbai_system.memory', 'dbai_system.disk', 'dbai_core.processes',
       'dbai_system.health_checks', 'dbai_system.alert_rules'],
 'Du bist der System-Administrator von DBAI. Du überwachst CPU, RAM, Disk, Netzwerk und Prozesse. ' ||
 'Bei Problemen führst du Self-Healing aus oder eskalierst an den Benutzer. ' ||
 'Antworte präzise und technisch. Du hast Zugriff auf dbai_system und dbai_core.',
 1, TRUE),

('coder',
 'Code Assistant',
 'Schreibt und analysiert Code. SQL, Python, C, Bash.',
 '💻', '#4488ff',
 ARRAY['dbai_knowledge', 'dbai_llm'],
 ARRAY['dbai_knowledge.module_registry', 'dbai_knowledge.error_patterns',
       'dbai_knowledge.architecture_decisions'],
 'Du bist der Code-Assistent von DBAI. Du hilfst beim Schreiben von SQL, Python, C und Bash. ' ||
 'Du kennst die gesamte DBAI-Architektur und kannst Module, Fehler und ADRs durchsuchen. ' ||
 'Halte dich an die No-Go-Regeln: keine absoluten Pfade, keine externen APIs, kein Root.',
 3, FALSE),

('security',
 'Security Monitor',
 'Überwacht Zugriffe, RLS, verdächtige Aktivitäten.',
 '🔒', '#ffaa00',
 ARRAY['dbai_core', 'dbai_event', 'dbai_journal'],
 ARRAY['dbai_event.events', 'dbai_journal.event_log', 'dbai_core.config'],
 'Du bist der Security-Monitor von DBAI. Du analysierst Events auf verdächtige Muster, ' ||
 'prüfst RLS-Policies und überwachst Login-Versuche. Melde jede Anomalie sofort.',
 2, TRUE),

('creative',
 'Creative Ghost',
 'Kreative Aufgaben: Texte, Namensfindung, Brainstorming.',
 '🎨', '#ff66cc',
 ARRAY['dbai_knowledge'],
 ARRAY['dbai_knowledge.system_glossary', 'dbai_knowledge.architecture_decisions'],
 'Du bist der kreative Ghost von DBAI. Du hilfst bei Namensfindung, Texten, ' ||
 'Konzepten und Brainstorming. Sei kreativ aber bleibe im DBAI-Kontext. ' ||
 'Denke wie ein Designer der Technik versteht.',
 5, FALSE),

('analyst',
 'Data Analyst',
 'Analysiert Metriken, Trends, Anomalien. Erstellt Reports.',
 '📊', '#00ff88',
 ARRAY['dbai_system', 'dbai_event', 'dbai_knowledge', 'dbai_journal'],
 ARRAY['dbai_system.cpu', 'dbai_system.memory', 'dbai_system.disk',
       'dbai_system.telemetry', 'dbai_knowledge.build_log'],
 'Du bist der Datenanalyst von DBAI. Du wertest Hardware-Metriken aus, ' ||
 'erkennst Trends und Anomalien, und erstellst verständliche Reports. ' ||
 'Nutze SQL-Abfragen um Statistiken zu liefern.',
 4, FALSE);

-- =============================================================================
-- 3. GHOST COMPATIBILITY — Welches Modell passt zu welcher Rolle?
-- =============================================================================

INSERT INTO dbai_llm.ghost_compatibility
    (model_id, role_id, fitness_score, notes, tested) VALUES

-- Qwen: Allrounder, besonders gut für Deutsch
((SELECT id FROM dbai_llm.ghost_models WHERE name = 'qwen2.5-7b-instruct'),
 (SELECT id FROM dbai_llm.ghost_roles WHERE name = 'sysadmin'),
 0.85, 'Gut für Systemanalyse, versteht Deutsch perfekt', TRUE),

((SELECT id FROM dbai_llm.ghost_models WHERE name = 'qwen2.5-7b-instruct'),
 (SELECT id FROM dbai_llm.ghost_roles WHERE name = 'coder'),
 0.80, 'Solide Code-Fähigkeiten, besser als Llama für SQL', TRUE),

((SELECT id FROM dbai_llm.ghost_models WHERE name = 'qwen2.5-7b-instruct'),
 (SELECT id FROM dbai_llm.ghost_roles WHERE name = 'analyst'),
 0.85, 'Sehr gut für Datenanalyse und Reports', TRUE),

-- Llama 3: Reasoning-fokussiert
((SELECT id FROM dbai_llm.ghost_models WHERE name = 'llama3-8b-instruct'),
 (SELECT id FROM dbai_llm.ghost_roles WHERE name = 'sysadmin'),
 0.80, 'Gutes Reasoning für Problemanalyse', TRUE),

((SELECT id FROM dbai_llm.ghost_models WHERE name = 'llama3-8b-instruct'),
 (SELECT id FROM dbai_llm.ghost_roles WHERE name = 'security'),
 0.85, 'Starkes logisches Denken für Sicherheitsanalyse', TRUE),

-- Mistral: Kreativ, langer Kontext
((SELECT id FROM dbai_llm.ghost_models WHERE name = 'mistral-7b-instruct'),
 (SELECT id FROM dbai_llm.ghost_roles WHERE name = 'creative'),
 0.90, 'Exzellent für kreative Aufgaben', TRUE),

((SELECT id FROM dbai_llm.ghost_models WHERE name = 'mistral-7b-instruct'),
 (SELECT id FROM dbai_llm.ghost_roles WHERE name = 'analyst'),
 0.80, 'Langer Kontext ideal für große Analysen', TRUE),

-- Phi-3: Schnell, ressourcenschonend
((SELECT id FROM dbai_llm.ghost_models WHERE name = 'phi3-mini'),
 (SELECT id FROM dbai_llm.ghost_roles WHERE name = 'sysadmin'),
 0.65, 'Schnell genug für Sensor-Monitoring, aber begrenzt', TRUE),

-- Codestral: Code-Spezialist
((SELECT id FROM dbai_llm.ghost_models WHERE name = 'codestral-22b'),
 (SELECT id FROM dbai_llm.ghost_roles WHERE name = 'coder'),
 0.95, 'Bestes Modell für Code-Aufgaben, braucht GPU', TRUE);

-- =============================================================================
-- 4. THEMES — Cyberpunk & Professional
-- =============================================================================

INSERT INTO dbai_ui.themes
    (name, display_name, description, colors, fonts, effects, boot_config, is_default, is_builtin) VALUES

('ghost-dark',
 'Ghost in the Shell',
 'Neon-Türkis auf Schwarz. Cyberpunk-Ästhetik mit Glow-Effekten.',
 '{
    "bg_primary":    "#0a0a0f",
    "bg_secondary":  "#0f0f1a",
    "bg_surface":    "#1a1a2e",
    "bg_elevated":   "#252540",
    "text_primary":  "#e0e0e0",
    "text_secondary":"#6688aa",
    "accent":        "#00ffcc",
    "accent_dim":    "#00aa88",
    "danger":        "#ff4444",
    "warning":       "#ffaa00",
    "success":       "#00ff88",
    "info":          "#4488ff",
    "border":        "#1a3a4a",
    "glow":          "rgba(0, 255, 204, 0.15)"
 }'::JSONB,
 '{
    "mono":    "\"JetBrains Mono\", \"Fira Code\", monospace",
    "sans":    "\"Inter\", \"Segoe UI\", sans-serif",
    "display": "\"Orbitron\", \"Rajdhani\", sans-serif"
 }'::JSONB,
 '{"blur": true, "glow": true, "scanlines": false, "crt": false, "particles": true, "animations": true, "transparency": 0.88}'::JSONB,
 '{"font_color": "#00ffcc", "speed_ms": 40, "show_logo": true, "sound": false}'::JSONB,
 TRUE, TRUE),

('matrix',
 'Matrix – Green Rain',
 'Klassischer Matrix-Look mit grünem Text auf Schwarz.',
 '{
    "bg_primary":    "#000000",
    "bg_secondary":  "#0a0a0a",
    "bg_surface":    "#111111",
    "bg_elevated":   "#1a1a1a",
    "text_primary":  "#00ff41",
    "text_secondary":"#008f11",
    "accent":        "#00ff41",
    "accent_dim":    "#00aa2a",
    "danger":        "#ff0000",
    "warning":       "#ffff00",
    "success":       "#00ff41",
    "info":          "#00ccff",
    "border":        "#003300",
    "glow":          "rgba(0, 255, 65, 0.2)"
 }'::JSONB,
 '{
    "mono":    "\"Courier New\", \"VT323\", monospace",
    "sans":    "\"Courier New\", monospace",
    "display": "\"VT323\", \"Share Tech Mono\", monospace"
 }'::JSONB,
 '{"blur": false, "glow": true, "scanlines": true, "crt": true, "particles": false, "animations": true, "transparency": 0.95}'::JSONB,
 '{"font_color": "#00ff41", "speed_ms": 30, "show_logo": true, "sound": false}'::JSONB,
 FALSE, TRUE),

('frost',
 'Frost – Clean Professional',
 'Heller glasmorphism-Look mit Blur-Effekten. Für produktives Arbeiten.',
 '{
    "bg_primary":    "#f0f2f5",
    "bg_secondary":  "#ffffff",
    "bg_surface":    "rgba(255, 255, 255, 0.72)",
    "bg_elevated":   "rgba(255, 255, 255, 0.9)",
    "text_primary":  "#1a1a2e",
    "text_secondary":"#555577",
    "accent":        "#0066ff",
    "accent_dim":    "#0044bb",
    "danger":        "#ee3333",
    "warning":       "#ff8800",
    "success":       "#22aa44",
    "info":          "#2266dd",
    "border":        "rgba(0, 0, 0, 0.08)",
    "glow":          "rgba(0, 102, 255, 0.1)"
 }'::JSONB,
 '{
    "mono":    "\"JetBrains Mono\", \"SF Mono\", monospace",
    "sans":    "\"Inter\", \"SF Pro Display\", sans-serif",
    "display": "\"Inter\", sans-serif"
 }'::JSONB,
 '{"blur": true, "glow": false, "scanlines": false, "crt": false, "particles": false, "animations": true, "transparency": 0.72}'::JSONB,
 '{"font_color": "#0066ff", "speed_ms": 25, "show_logo": true, "sound": false}'::JSONB,
 FALSE, TRUE);

-- =============================================================================
-- 5. DEFAULT USER — root
-- =============================================================================

INSERT INTO dbai_ui.users
    (username, display_name, password_hash, db_role, is_admin, avatar_url) VALUES
('root', 'System Administrator',
 crypt('dbai2026', gen_salt('bf')),
 'dbai_system', TRUE, '/assets/avatars/root.svg');

-- =============================================================================
-- 6. DEFAULT DESKTOP CONFIG
-- =============================================================================

INSERT INTO dbai_ui.desktop_config
    (user_id, wallpaper_url, theme_id, icons, pinned_apps)
VALUES (
    (SELECT id FROM dbai_ui.users WHERE username = 'root'),
    '/assets/wallpapers/grid-neural.svg',
    (SELECT id FROM dbai_ui.themes WHERE name = 'ghost-dark'),
    '[
        {"app_id": "system-monitor", "x": 0, "y": 0, "label": "System Monitor"},
        {"app_id": "ghost-manager",  "x": 1, "y": 0, "label": "Ghost Manager"},
        {"app_id": "terminal",       "x": 2, "y": 0, "label": "Terminal"},
        {"app_id": "file-browser",   "x": 0, "y": 1, "label": "Dateien"},
        {"app_id": "knowledge-base", "x": 1, "y": 1, "label": "Knowledge Base"},
        {"app_id": "settings",       "x": 2, "y": 1, "label": "Einstellungen"}
    ]'::JSONB,
    '["system-monitor", "ghost-manager", "terminal"]'::JSONB
);

-- =============================================================================
-- 7. APPS — Registrierte Anwendungen
-- =============================================================================

INSERT INTO dbai_ui.apps
    (app_id, name, description, icon, category, source_type, source_target,
     default_width, default_height, is_system, is_pinned, sort_order, required_role) VALUES

('system-monitor',
 'System Monitor',
 'Live-Übersicht: CPU, RAM, Disk, Netzwerk, Prozesse. Aktualisiert sich per WebSocket.',
 '📊', 'monitor', 'component', 'SystemMonitor',
 1000, 700, TRUE, TRUE, 1, 'dbai_monitor'),

('ghost-manager',
 'Ghost Manager',
 'KI-Modelle verwalten: Laden, entladen, Rollen zuweisen, Hot-Swap.',
 '👻', 'ai', 'component', 'GhostManager',
 900, 650, TRUE, TRUE, 2, 'dbai_system'),

('terminal',
 'Terminal',
 'Eingebettetes Terminal: SQL-Konsole und Shell-Zugang.',
 '⌨️', 'terminal', 'terminal', NULL,
 800, 500, TRUE, TRUE, 3, 'dbai_system'),

('file-browser',
 'Datei-Browser',
 'Durchsucht die Objekt-Registry (dbai_core.objects). Dateien sind UUIDs, keine Pfade.',
 '📁', 'files', 'component', 'FileBrowser',
 850, 600, TRUE, FALSE, 4, 'dbai_monitor'),

('knowledge-base',
 'Knowledge Base',
 'Durchsucht Module, ADRs, Glossar, Error-Patterns, Runbooks.',
 '📚', 'utility', 'component', 'KnowledgeBase',
 950, 650, TRUE, FALSE, 5, 'dbai_monitor'),

('event-viewer',
 'Event Viewer',
 'Live-Stream aller System-Events. Filter nach Typ, Quelle, Priorität.',
 '📡', 'monitor', 'component', 'EventViewer',
 900, 600, FALSE, FALSE, 6, 'dbai_monitor'),

('process-manager',
 'Prozess-Manager',
 'Laufende Prozesse verwalten: Starten, stoppen, Priorität ändern.',
 '⚙️', 'system', 'component', 'ProcessManager',
 800, 550, TRUE, FALSE, 7, 'dbai_system'),

('health-dashboard',
 'Health Dashboard',
 'Self-Healing Status, Alert-Regeln, Health-Checks, Telemetrie.',
 '🏥', 'monitor', 'component', 'HealthDashboard',
 950, 700, FALSE, FALSE, 8, 'dbai_monitor'),

('ghost-chat',
 'Ghost Chat',
 'Chat-Interface: Sprich mit dem aktiven Ghost. Wähle eine Rolle, stelle Fragen.',
 '💬', 'ai', 'component', 'GhostChat',
 700, 800, FALSE, FALSE, 9, 'dbai_monitor'),

('sql-console',
 'SQL-Konsole',
 'Direkte SQL-Abfragen gegen die Datenbank. Ergebnisse als Tabelle.',
 '🗃️', 'development', 'component', 'SQLConsole',
 900, 600, FALSE, FALSE, 10, 'dbai_system'),

('settings',
 'Einstellungen',
 'System-Konfiguration: Theme, Desktop, Benutzer, Netzwerk.',
 '⚙️', 'settings', 'component', 'Settings',
 700, 550, TRUE, FALSE, 11, 'dbai_system'),

('error-analyzer',
 'Error Analyzer',
 'Fehler-Log durchsuchen, Patterns matchen, Runbooks anzeigen.',
 '🔍', 'development', 'component', 'ErrorAnalyzer',
 850, 600, FALSE, FALSE, 12, 'dbai_monitor'),

('boot-log',
 'Boot Log',
 'Zeigt die letzte Boot-Sequenz als Terminal-Animation.',
 '🚀', 'system', 'sql_view', 'dbai_ui.vw_boot_sequence',
 700, 500, FALSE, FALSE, 13, 'dbai_monitor');

-- =============================================================================
-- 8. DEFAULT ACTIVE GHOSTS — System startet mit Qwen als Sysadmin
-- =============================================================================

INSERT INTO dbai_llm.active_ghosts (role_id, model_id, state, activated_by, swap_reason)
VALUES (
    (SELECT id FROM dbai_llm.ghost_roles WHERE name = 'sysadmin'),
    (SELECT id FROM dbai_llm.ghost_models WHERE name = 'qwen2.5-7b-instruct'),
    'active', 'system', 'System-Boot: Default-Ghost für Sysadmin-Rolle'
);

-- Ghost History Eintrag
INSERT INTO dbai_llm.ghost_history
    (role_id, role_name, new_model_id, new_model_name, swap_reason, swap_duration_ms, initiated_by)
VALUES (
    (SELECT id FROM dbai_llm.ghost_roles WHERE name = 'sysadmin'),
    'sysadmin',
    (SELECT id FROM dbai_llm.ghost_models WHERE name = 'qwen2.5-7b-instruct'),
    'qwen2.5-7b-instruct',
    'System-Boot: Default-Ghost aktiviert', 0, 'system'
);

-- =============================================================================
-- 9. WELCOME NOTIFICATION
-- =============================================================================

INSERT INTO dbai_ui.notifications
    (user_id, title, message, icon, severity, action_type, action_target) VALUES
((SELECT id FROM dbai_ui.users WHERE username = 'root'),
 'Willkommen bei DBAI',
 'Ghost in the Database ist einsatzbereit. Öffne den Ghost Manager um KI-Modelle zu verwalten.',
 '👻', 'ghost', 'open_app', 'ghost-manager');
