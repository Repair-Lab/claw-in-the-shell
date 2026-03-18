-- =============================================================================
-- DBAI Schema 58: Agent Instances — Tabelle für laufende Agent-Instanzen
-- Erstellt von Reparatur-Skript um fehlende Tabelle 'dbai_llm.agent_instances'
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS dbai_llm;

CREATE TABLE IF NOT EXISTS dbai_llm.agent_instances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id UUID NOT NULL REFERENCES dbai_llm.ghost_models(id) ON DELETE SET NULL,
    role_id UUID REFERENCES dbai_llm.ghost_roles(id),
    gpu_index INTEGER DEFAULT 0,
    gpu_name TEXT,
    vram_allocated_mb INTEGER DEFAULT 0,
    backend TEXT NOT NULL DEFAULT 'llama.cpp',
    api_port INTEGER,
    context_size INTEGER DEFAULT 4096,
    max_tokens INTEGER DEFAULT 2048,
    n_gpu_layers INTEGER DEFAULT -1,
    threads INTEGER DEFAULT 4,
    batch_size INTEGER DEFAULT 512,
    pid INTEGER,
    state TEXT NOT NULL DEFAULT 'stopped',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE dbai_llm.agent_instances IS 'Agent-Instanzen (LLM worker processes) verwaltet durch Ghost-API';

CREATE INDEX IF NOT EXISTS idx_agent_instances_model_id ON dbai_llm.agent_instances(model_id);
CREATE INDEX IF NOT EXISTS idx_agent_instances_role_id ON dbai_llm.agent_instances(role_id);
CREATE INDEX IF NOT EXISTS idx_agent_instances_api_port ON dbai_llm.agent_instances(api_port);

-- Ensure runtime role can read/write
GRANT USAGE ON SCHEMA dbai_llm TO dbai_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE dbai_llm.agent_instances TO dbai_runtime;
