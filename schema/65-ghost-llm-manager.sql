-- =============================================================================
-- Migration 65: Ghost LLM Manager — Merge Ghost Manager + LLM Manager
-- =============================================================================
-- Ghost Manager und LLM Manager werden zu einer einzigen App vereint:
--   "Ghost LLM Manager" (app_id: ghost-llm-manager)
--
-- Änderungen:
--   - ghost-manager App-Eintrag entfernen
--   - llm-manager → ghost-llm-manager umbenennen
--   - source_target: GhostLLMManager (neue React-Komponente)
--   - Festplatten-Scanner Fix: Volume-Mounts in docker-compose hinzugefügt
-- =============================================================================

BEGIN;

-- 1) Ghost Manager entfernen (Funktionalität jetzt im Ghost LLM Manager)
DELETE FROM dbai_ui.apps WHERE app_id = 'ghost-manager';

-- 2) LLM Manager → Ghost LLM Manager umbenennen
UPDATE dbai_ui.apps
SET app_id       = 'ghost-llm-manager',
    name         = 'Ghost LLM Manager',
    source_target = 'GhostLLMManager',
    icon         = '👻',
    sort_order   = 2,
    is_system    = true,
    is_pinned    = true
WHERE app_id = 'llm-manager';

-- 3) Falls UPDATE keine Zeile traf (neues System), INSERT
INSERT INTO dbai_ui.apps (
    app_id, name, description, icon, source_type, source_target,
    is_system, is_pinned, category, sort_order,
    default_width, default_height, min_width, min_height, resizable
) VALUES (
    'ghost-llm-manager',
    'Ghost LLM Manager',
    'KI-Agenten orchestrieren, Ghost Hot-Swap, Modelle verwalten, GPU-Monitoring, Benchmarks',
    '👻',
    'component',
    'GhostLLMManager',
    true, true, 'ai', 2,
    1100, 750, 800, 500, true
) ON CONFLICT (app_id) DO NOTHING;

-- 4) Changelog-Eintrag
INSERT INTO dbai_knowledge.changelog (
    version, change_type, title, description,
    affected_modules, affected_files, author
) VALUES (
    '65',
    'refactor',
    'Ghost Manager + LLM Manager → Ghost LLM Manager',
    'Ghost Manager (KI-Modell Hot-Swap, Rollen, History) und LLM Manager (Agenten, GPU, Pipelines, Scanner, Benchmarks) zusammengeführt. Neuer Ghost-Tab. Festplatten-Scanner gefixt durch Volume-Mounts.',
    '{}'::uuid[],
    ARRAY['frontend/src/components/apps/LLMManager.jsx', 'frontend/src/components/Desktop.jsx', 'dev/docker-compose.sandbox.yml'],
    'system'
);

-- 5) System-Memory Einträge
INSERT INTO dbai_knowledge.system_memory (title, content, category, priority) VALUES
(
    'Ghost LLM Manager — App-Merge',
    'Ghost Manager und LLM Manager sind seit Migration 65 eine einzige App: Ghost LLM Manager (ghost-llm-manager). source_target = GhostLLMManager. Die React-Komponente liegt in frontend/src/components/apps/LLMManager.jsx und wird als GhostLLMManager exportiert. GhostManager.jsx existiert noch als Datei, wird aber nicht mehr importiert.',
    'architecture',
    7
),
(
    'Festplatten-Scanner — Volume-Mount Fix',
    'Der Festplatten-Scanner im Ghost LLM Manager (API-Endpoint POST /api/llm/scan) konnte keine Modelle finden, weil die Host-Pfade /mnt/nvme/models und /home/worker nicht in den Docker-API-Container gemountet waren. Fix: Volume-Mounts /mnt/nvme/models:/mnt/nvme/models:ro und /home/worker:/home/worker:ro in docker-compose.sandbox.yml (und Prod docker-compose.yml hat /mnt/nvme/models bereits). Der Scanner erkennt .gguf, .safetensors, .bin Dateien >10MB sowie HuggingFace-Verzeichnisse mit config.json.',
    'operational',
    6
),
(
    'APP_COMPONENTS Registry — GhostLLMManager',
    'In Desktop.jsx wird GhostLLMManager aus ./apps/LLMManager importiert (nicht aus GhostManager). Der alte GhostManager-Import wurde entfernt. APP_COMPONENTS enthält GhostLLMManager als Key, der DB source_target muss ebenfalls GhostLLMManager sein.',
    'convention',
    5
);

COMMIT;
