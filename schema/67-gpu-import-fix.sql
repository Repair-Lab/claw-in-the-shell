-- =============================================================================
-- Migration 67: GPU-Erkennung + Modell-Import Fix
-- =============================================================================
-- Drei Bugs behoben:
--   1. GPU nicht erkannt: DBAI_HW_SIMULATE war "true", NVIDIA Container Toolkit
--      nicht konfiguriert, kein GPU deploy block in docker-compose
--   2. Modell-Import 500: ghost_models.provider "local" verletzt CHECK-Constraint
--      → Automatische Provider-Erkennung + ON CONFLICT DO UPDATE
--   3. Disk-Scanner: Findet korrekt 3 Modelle (das ist die tatsächliche Dateilage)
-- =============================================================================

BEGIN;

-- Changelog
INSERT INTO dbai_knowledge.changelog (
    version, change_type, title, description,
    affected_modules, affected_files, author
) VALUES (
    '67',
    'fix',
    'GPU-Erkennung + Modell-Import Fix',
    'GPU: DBAI_HW_SIMULATE "true"→"false", NVIDIA env vars, GPU deploy block, nvidia-ctk konfiguriert. Import: provider="local" → automatische Erkennung (gguf→llama.cpp, safetensors→huggingface), ON CONFLICT DO UPDATE, Quantisierung aus Dateinamen.',
    '{}'::uuid[],
    ARRAY['web/server.py', 'dev/docker-compose.sandbox.yml'],
    'system'
);

-- System-Memory
INSERT INTO dbai_knowledge.system_memory (title, content, category, priority) VALUES
(
    'GPU Docker-Passthrough Setup',
    'GPU im Container: (1) nvidia-container-toolkit + nvidia-ctk runtime configure, (2) docker-compose: deploy.resources.reservations.devices [nvidia], (3) DBAI_HW_SIMULATE="false", (4) NVIDIA_VISIBLE_DEVICES=all + NVIDIA_DRIVER_CAPABILITIES=compute,utility. GPU: RTX PRO 6000 Blackwell 97887 MiB.',
    'operational',
    9
),
(
    'ghost_models Provider CHECK Constraint',
    'Erlaubt: llama.cpp, vllm, ollama, custom, nvidia, openai, anthropic, google, groq, together, mistral, huggingface, openrouter. Mapping: GGUF→llama.cpp, Safetensors→huggingface. POST /api/llm/models nutzt automatische Erkennung + ON CONFLICT DO UPDATE.',
    'convention',
    8
);

COMMIT;
