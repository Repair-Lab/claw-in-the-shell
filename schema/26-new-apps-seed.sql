-- =============================================================================
-- DBAI Schema 26: Neue Desktop-Apps + Software-Katalog Seed-Daten
-- Stand: 15. März 2026
-- =============================================================================

-- =============================================================================
-- 1. NEUE DESKTOP-APPS REGISTRIEREN
-- =============================================================================

-- Software Store
INSERT INTO dbai_ui.apps (app_id, name, description, icon, default_width, default_height,
    min_width, min_height, resizable, source_type, source_target, required_role,
    is_system, is_pinned, category, sort_order)
VALUES (
    'software-store', 'Software Store', 'Pakete suchen, installieren und verwalten',
    '🏪', 1000, 700, 600, 400, TRUE, 'component', 'SoftwareStore',
    'dbai_monitor', FALSE, FALSE, 'utility', 20
) ON CONFLICT (app_id) DO NOTHING;

-- OpenClaw Integrator
INSERT INTO dbai_ui.apps (app_id, name, description, icon, default_width, default_height,
    min_width, min_height, resizable, source_type, source_target, required_role,
    is_system, is_pinned, category, sort_order)
VALUES (
    'openclaw-integrator', 'OpenClaw Integrator', 'OpenClaw-Skills migrieren und Memories importieren',
    '🦞', 950, 650, 600, 400, TRUE, 'component', 'OpenClawIntegrator',
    'dbai_system', FALSE, FALSE, 'ai', 21
) ON CONFLICT (app_id) DO NOTHING;

-- LLM Manager
INSERT INTO dbai_ui.apps (app_id, name, description, icon, default_width, default_height,
    min_width, min_height, resizable, source_type, source_target, required_role,
    is_system, is_pinned, category, sort_order)
VALUES (
    'llm-manager', 'LLM Manager', 'KI-Modelle verwalten, benchmarken und konfigurieren',
    '🤖', 1000, 650, 600, 400, TRUE, 'component', 'LLMManager',
    'dbai_system', TRUE, FALSE, 'ai', 22
) ON CONFLICT (app_id) DO NOTHING;

-- Setup Wizard
INSERT INTO dbai_ui.apps (app_id, name, description, icon, default_width, default_height,
    min_width, min_height, resizable, source_type, source_target, required_role,
    is_system, is_pinned, category, sort_order)
VALUES (
    'setup-wizard', 'Ersteinrichtung', 'First-Boot Setup: Sprache, Theme, KI konfigurieren',
    '🧙', 800, 600, 600, 450, TRUE, 'component', 'SetupWizard',
    'dbai_monitor', TRUE, FALSE, 'settings', 23
) ON CONFLICT (app_id) DO NOTHING;


-- =============================================================================
-- 2. SOFTWARE-KATALOG SEED-DATEN
-- =============================================================================

-- System & Development Tools (apt)
INSERT INTO dbai_core.software_catalog
    (package_name, display_name, description, version, latest_version,
     source_type, category, tags, install_state, install_size_mb,
     ghost_recommendation, ghost_review, license) VALUES

('postgresql-16', 'PostgreSQL 16', 'Das Herz von DBAI — Relationale Datenbank mit MVCC',
 '16.4', '16.4', 'apt', 'database', ARRAY['database', 'sql', 'core'],
 'installed', 45.0, 1.0, 'Unverzichtbar. DBAI existiert nicht ohne PostgreSQL.', 'PostgreSQL License'),

('python3', 'Python 3.11', 'System Bridge, API-Server, Automatisierung',
 '3.11.9', '3.12.3', 'apt', 'development', ARRAY['python', 'scripting', 'core'],
 'installed', 120.0, 0.95, 'Standard-Sprache für alle DBAI-Brücken.', 'PSF License'),

('nginx', 'Nginx', 'Reverse-Proxy und Static-File-Server',
 '1.24.0', '1.26.0', 'apt', 'network', ARRAY['web', 'proxy', 'server'],
 'installed', 5.0, 0.8, 'Gut für TLS-Terminierung, optional falls Uvicorn direkt exposed.', 'BSD-2'),

('git', 'Git', 'Versionskontrolle — Grundlage für GitOps',
 '2.43.0', '2.45.0', 'apt', 'development', ARRAY['git', 'vcs', 'core'],
 'installed', 35.0, 0.9, 'Essentiell für Code-Tracking und GitOps-Pipeline.', 'GPL-2.0'),

('htop', 'htop', 'Interaktiver Prozess-Monitor für die Konsole',
 '3.3.0', '3.3.0', 'apt', 'system', ARRAY['monitoring', 'terminal', 'processes'],
 'installed', 1.0, 0.7, 'Nützlich, aber DBAI hat einen eigenen Prozess-Manager.', 'GPL-2.0'),

('curl', 'curl', 'HTTP-Client für API-Tests und Downloads',
 '8.5.0', '8.8.0', 'apt', 'network', ARRAY['http', 'api', 'download'],
 'installed', 2.0, 0.75, 'Standardtool, immer praktisch.', 'MIT'),

('build-essential', 'build-essential', 'GCC, Make, C-Header — für llama.cpp Kompilierung',
 '12.10', '12.10', 'apt', 'development', ARRAY['compiler', 'c', 'build'],
 'installed', 200.0, 0.85, 'Notwendig für C-Bindings und llama.cpp.', 'GPL'),

('zfsutils-linux', 'ZFS Utils', 'Self-Healing Dateisystem — DBAI empfiehlt ZFS',
 '2.2.3', '2.2.4', 'apt', 'system', ARRAY['filesystem', 'zfs', 'self-healing'],
 'available', 80.0, 0.9, 'Sehr empfohlen für Self-Healing und Snapshots.', 'CDDL'),

('prometheus-node-exporter', 'Node Exporter', 'Hardware-Metriken für Prometheus',
 '1.7.0', '1.8.0', 'apt', 'utility', ARRAY['monitoring', 'prometheus', 'metrics'],
 'available', 12.0, 0.65, 'Optional — DBAI hat eigene Telemetrie-Tabellen.', 'Apache-2.0'),

('tmux', 'tmux', 'Terminal-Multiplexer — Sessions im Hintergrund',
 '3.4', '3.4', 'apt', 'utility', ARRAY['terminal', 'multiplexer', 'session'],
 'available', 1.5, 0.6, 'Praktisch für SSH-Sessions, aber nicht essentiell.', 'ISC')

ON CONFLICT (package_name, source_type) DO NOTHING;


-- Python Packages (pip)
INSERT INTO dbai_core.software_catalog
    (package_name, display_name, description, version, latest_version,
     source_type, category, tags, install_state, install_size_mb,
     ghost_recommendation, license) VALUES

('fastapi', 'FastAPI', 'Web-Framework für den DBAI API-Server',
 '0.115.0', '0.115.0', 'pip', 'development', ARRAY['web', 'api', 'async', 'core'],
 'installed', 3.0, 0.95, 'MIT'),

('psycopg2-binary', 'psycopg2', 'PostgreSQL-Adapter für Python — DB-Brücke',
 '2.9.9', '2.9.9', 'pip', 'database', ARRAY['postgresql', 'database', 'core'],
 'installed', 8.0, 1.0, 'LGPL'),

('uvicorn', 'Uvicorn', 'ASGI-Server für FastAPI — schnell und async',
 '0.30.0', '0.30.0', 'pip', 'development', ARRAY['web', 'server', 'async'],
 'installed', 2.0, 0.9, 'BSD-3'),

('llama-cpp-python', 'llama-cpp-python', 'Python-Bindings für llama.cpp — lokales LLM',
 '0.2.85', '0.2.90', 'pip', 'ai_ml', ARRAY['llm', 'llama', 'inference', 'core'],
 'installed', 150.0, 0.95, 'MIT'),

('pgvector', 'pgvector (Python)', 'Vektor-Operationen für Embeddings',
 '0.3.0', '0.3.2', 'pip', 'ai_ml', ARRAY['vector', 'embedding', 'similarity'],
 'installed', 1.0, 0.85, 'MIT'),

('playwright', 'Playwright', 'Headless-Browser-Steuerung für Web-Scraping',
 '1.44.0', '1.45.0', 'pip', 'utility', ARRAY['browser', 'automation', 'scraping'],
 'available', 250.0, 0.7, 'Apache-2.0'),

('sentence-transformers', 'Sentence Transformers', 'Embedding-Modelle für Semantic Search',
 '3.0.0', '3.1.0', 'pip', 'ai_ml', ARRAY['embedding', 'nlp', 'transformer'],
 'available', 500.0, 0.75, 'Apache-2.0'),

('crewai', 'CrewAI', 'Multi-Agent KI-Framework',
 '0.28.0', '0.36.0', 'pip', 'ai_ml', ARRAY['agents', 'crew', 'orchestration'],
 'available', 80.0, 0.6, 'MIT')

ON CONFLICT (package_name, source_type) DO NOTHING;


-- GitHub Repos
INSERT INTO dbai_core.software_catalog
    (package_name, display_name, description, version, latest_version,
     source_type, source_url, category, tags, install_state,
     ghost_recommendation, ghost_review, stars, license) VALUES

('ggerganov/llama.cpp', 'llama.cpp', 'LLM-Inference-Engine — das Rückgrat der Ghost-KI',
 'b3600', 'b3650', 'github', 'https://github.com/ggerganov/llama.cpp',
 'ai_ml', ARRAY['llm', 'inference', 'cpp', 'core'],
 'installed', 1.0, 'Unverzichtbar. Ohne llama.cpp kein Ghost.', 68000, 'MIT'),

('pgvector/pgvector', 'pgvector', 'PostgreSQL-Extension für Vektoren — KI-Gedächtnis',
 '0.7.0', '0.7.4', 'github', 'https://github.com/pgvector/pgvector',
 'database', ARRAY['vector', 'postgresql', 'extension', 'core'],
 'installed', 0.95, 'Macht PostgreSQL zum Vektor-Speicher.', 12000, 'PostgreSQL License'),

('microsoft/playwright', 'Playwright', 'Browser-Automatisierung — die Augen des Ghost',
 '1.44.0', '1.45.0', 'github', 'https://github.com/microsoft/playwright',
 'utility', ARRAY['browser', 'automation', 'testing'],
 'available', 0.7, 'Für Browser-Sessions und Web-Interaktion.', 65000, 'Apache-2.0'),

('n8n-io/n8n', 'n8n', 'Workflow-Automatisierung — Low-Code Integration',
 '1.40.0', '1.50.0', 'github', 'https://github.com/n8n-io/n8n',
 'productivity', ARRAY['automation', 'workflow', 'integration'],
 'available', 0.5, 'Bereits im Cluster deployed, optional lokal.', 45000, 'Sustainable Use License'),

('vllm-project/vllm', 'vLLM', 'Hochperformante LLM-Serving-Engine mit PagedAttention',
 '0.5.0', '0.6.0', 'github', 'https://github.com/vllm-project/vllm',
 'ai_ml', ARRAY['llm', 'serving', 'gpu', 'inference'],
 'available', 0.85, 'Alternative zu llama.cpp für GPU-schwere Workloads.', 30000, 'Apache-2.0')

ON CONFLICT (package_name, source_type) DO NOTHING;


-- npm packages
INSERT INTO dbai_core.software_catalog
    (package_name, display_name, description, version, latest_version,
     source_type, category, tags, install_state, install_size_mb,
     ghost_recommendation, license) VALUES

('react', 'React', 'UI-Library für den Desktop-Frontend',
 '18.3.0', '19.0.0', 'npm', 'development', ARRAY['frontend', 'ui', 'core'],
 'installed', 5.0, 0.95, 'MIT'),

('vite', 'Vite', 'Blitzschneller Frontend-Bundler',
 '5.3.0', '5.4.0', 'npm', 'development', ARRAY['bundler', 'frontend', 'build'],
 'installed', 20.0, 0.9, 'MIT')

ON CONFLICT (package_name, source_type) DO NOTHING;


-- ghost_benchmarks existiert bereits mit anderem Schema — kein CREATE nötig


-- =============================================================================
-- 4. CONFIG-Tabelle: updated_at Spalte sicherstellen
-- =============================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'dbai_core' AND table_name = 'config' AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE dbai_core.config ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW();
    END IF;
END$$;
