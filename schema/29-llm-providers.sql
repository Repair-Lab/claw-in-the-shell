-- =============================================================================
-- 29: LLM PROVIDERS — Cloud- und Lokal-Provider für KI-Modelle
-- =============================================================================
-- Erstellt: 2026-03-16
-- Zweck: Provider-Registry mit API-Key-Management für Setup-Wizard + Settings
-- =============================================================================

CREATE TABLE IF NOT EXISTS dbai_llm.llm_providers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_key    TEXT NOT NULL UNIQUE,
    display_name    TEXT NOT NULL,
    icon            TEXT DEFAULT '🤖',
    -- Konfiguration
    api_base_url    TEXT,
    api_key_enc     TEXT,                     -- Base64 (in Prod: pgcrypto)
    api_key_preview TEXT,                     -- 'nvapi-...XYZ'
    -- Provider-Typ
    provider_type   TEXT NOT NULL DEFAULT 'cloud'
                    CHECK (provider_type IN ('cloud', 'local', 'hybrid')),
    -- Features
    supports_chat       BOOLEAN DEFAULT TRUE,
    supports_embedding  BOOLEAN DEFAULT FALSE,
    supports_vision     BOOLEAN DEFAULT FALSE,
    supports_tools      BOOLEAN DEFAULT FALSE,
    supports_streaming  BOOLEAN DEFAULT TRUE,
    -- Status
    is_enabled      BOOLEAN NOT NULL DEFAULT FALSE,
    is_configured   BOOLEAN NOT NULL DEFAULT FALSE,
    last_tested     TIMESTAMPTZ,
    last_test_ok    BOOLEAN,
    -- Metadaten
    description     TEXT,
    docs_url        TEXT,
    pricing_info    TEXT,
    imported_from   TEXT,
    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Trigger
CREATE OR REPLACE FUNCTION dbai_llm.fn_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_llm_providers_updated ON dbai_llm.llm_providers;
CREATE TRIGGER trg_llm_providers_updated
    BEFORE UPDATE ON dbai_llm.llm_providers
    FOR EACH ROW EXECUTE FUNCTION dbai_llm.fn_set_updated_at();

-- RLS + GRANT
ALTER TABLE dbai_llm.llm_providers ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS llm_providers_system ON dbai_llm.llm_providers;
CREATE POLICY llm_providers_system ON dbai_llm.llm_providers FOR ALL TO dbai_system USING (TRUE);
DROP POLICY IF EXISTS llm_providers_runtime ON dbai_llm.llm_providers;
CREATE POLICY llm_providers_runtime ON dbai_llm.llm_providers FOR SELECT TO dbai_runtime USING (TRUE);
DROP POLICY IF EXISTS llm_providers_runtime_write ON dbai_llm.llm_providers;
CREATE POLICY llm_providers_runtime_write ON dbai_llm.llm_providers FOR ALL TO dbai_runtime USING (TRUE);
GRANT SELECT, INSERT, UPDATE, DELETE ON dbai_llm.llm_providers TO dbai_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON dbai_llm.llm_providers TO dbai_system;
GRANT SELECT ON dbai_llm.llm_providers TO dbai_monitor;

-- =============================================================================
-- SEED: 12 Standard-Provider (alle deaktiviert)
-- =============================================================================
INSERT INTO dbai_llm.llm_providers (provider_key, display_name, icon, api_base_url, provider_type, supports_chat, supports_embedding, supports_vision, supports_tools, description, docs_url, pricing_info)
VALUES
  ('nvidia',      'NVIDIA NIM',       '🟢', 'https://integrate.api.nvidia.com/v1',              'cloud', TRUE, TRUE, TRUE, TRUE,   'NVIDIA NIM — Llama, Qwen, Mistral, Nemotron uvm.',   'https://build.nvidia.com/',          'Free: 1000 Credits/Monat'),
  ('openai',      'OpenAI',           '🧠', 'https://api.openai.com/v1',                        'cloud', TRUE, TRUE, TRUE, TRUE,   'GPT-4o, GPT-4, o1 — OpenAI Cloud',                   'https://platform.openai.com/docs',   '$0.01–$0.06 / 1K Tokens'),
  ('anthropic',   'Anthropic',        '🔮', 'https://api.anthropic.com/v1',                     'cloud', TRUE, FALSE, TRUE, TRUE,  'Claude Opus, Sonnet — Anthropic Cloud',               'https://docs.anthropic.com/',         '$0.003–$0.075 / 1K Tokens'),
  ('google',      'Google AI',        '🔵', 'https://generativelanguage.googleapis.com/v1beta', 'cloud', TRUE, TRUE, TRUE, TRUE,   'Gemini Pro, Gemini Flash — Google AI Studio',         'https://ai.google.dev/',              'Free: 60 req/min'),
  ('groq',        'Groq',             '⚡', 'https://api.groq.com/openai/v1',                   'cloud', TRUE, FALSE, FALSE, TRUE, 'Groq — Ultra-schnelle LPU Inferenz',                  'https://console.groq.com/docs',       'Free: 14.4K Tokens/min'),
  ('together',    'Together AI',      '🤝', 'https://api.together.xyz/v1',                      'cloud', TRUE, TRUE, FALSE, TRUE,  'Together AI — 200+ Open-Source Modelle',              'https://docs.together.ai/',           '$0.0002–$0.025 / 1K Tokens'),
  ('mistral',     'Mistral AI',       '🌊', 'https://api.mistral.ai/v1',                        'cloud', TRUE, TRUE, FALSE, TRUE,  'Mistral Large, Codestral, Pixtral — Mistral Cloud',   'https://docs.mistral.ai/',            'Free: Pixtral, $0.004/1K'),
  ('huggingface', 'Hugging Face',     '🤗', 'https://api-inference.huggingface.co/models',      'cloud', TRUE, TRUE, TRUE, FALSE,  'Hugging Face Inference API — Open-Source Modelle',    'https://huggingface.co/docs/api-inference', 'Free: Rate-limited'),
  ('openrouter',  'OpenRouter',       '🔀', 'https://openrouter.ai/api/v1',                     'cloud', TRUE, TRUE, TRUE, TRUE,   'OpenRouter — 100+ Modelle, ein API-Key',              'https://openrouter.ai/docs',          '$0.0001–$0.05 / 1K Tokens'),
  ('ollama',      'Ollama (Lokal)',   '🦙', 'http://localhost:11434/api',                        'local', TRUE, TRUE, TRUE, FALSE,  'Ollama — Lokale LLMs mit einem Befehl',              'https://ollama.com/',                 'Kostenlos (lokal)'),
  ('vllm',        'vLLM (Lokal)',     '🚀', 'http://localhost:8000/v1',                          'local', TRUE, FALSE, FALSE, TRUE, 'vLLM — GPU-Inferenz-Server',                          'https://docs.vllm.ai/',               'Kostenlos (lokal)'),
  ('llamacpp',    'llama.cpp (Lokal)','🔧', NULL,                                                'local', TRUE, FALSE, FALSE, FALSE,'llama.cpp — GGUF-Ausführung auf CPU/GPU',             'https://github.com/ggerganov/llama.cpp', 'Kostenlos (lokal)')
ON CONFLICT (provider_key) DO NOTHING;

-- Provider-Constraint an ghost_models erweitern
DO $$
BEGIN
  ALTER TABLE dbai_llm.ghost_models DROP CONSTRAINT IF EXISTS ghost_models_provider_check;
  ALTER TABLE dbai_llm.ghost_models ADD CONSTRAINT ghost_models_provider_check
    CHECK (provider IN ('llama.cpp','vllm','ollama','custom','nvidia','openai','anthropic','google','groq','together','mistral','huggingface','openrouter'));
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'Provider constraint update skipped: %', SQLERRM;
END $$;
