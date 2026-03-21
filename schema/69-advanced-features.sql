-- ============================================================================
-- DBAI v0.14.0 — 5 Advanced Features Migration
-- ============================================================================
-- Feature 1: Autonomous Coding     — Ghost schreibt eigene SQL-Migrationen
-- Feature 2: Multi-GPU Parallel    — Modelle über mehrere GPUs verteilen
-- Feature 3: Vision Integration    — Echtzeit-Video/Bild-Analyse
-- Feature 4: Distributed Ghosts    — Ghost-Instanzen über mehrere Nodes
-- Feature 5: Model Marketplace     — GGUF-Modelle direkt von HuggingFace
-- ============================================================================

BEGIN;

-- ============================================================================
-- FEATURE 1: AUTONOMOUS CODING
-- Ghost kann eigene SQL-Migrationen generieren, reviewen, anwenden
-- ============================================================================

CREATE TABLE IF NOT EXISTS dbai_core.autonomous_migrations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT NOT NULL,
    description     TEXT,
    migration_sql   TEXT NOT NULL,
    rollback_sql    TEXT,
    generated_by    TEXT NOT NULL DEFAULT 'ghost',          -- ghost | user | system
    model_used      TEXT,                                    -- welches LLM hat den SQL generiert
    prompt_used     TEXT,                                    -- Original-Prompt
    state           TEXT NOT NULL DEFAULT 'draft'
        CHECK (state IN ('draft','review','approved','applied','reverted','rejected')),
    review_notes    TEXT,
    reviewed_by     TEXT,
    reviewed_at     TIMESTAMPTZ,
    applied_at      TIMESTAMPTZ,
    reverted_at     TIMESTAMPTZ,
    execution_ms    INTEGER,
    affected_tables TEXT[],                                  -- welche Tabellen betroffen
    affected_schemas TEXT[],                                 -- welche Schemas betroffen
    checksum        TEXT,                                    -- SHA-256 des migration_sql
    parent_id       UUID REFERENCES dbai_core.autonomous_migrations(id),  -- Kette
    version_tag     TEXT,                                    -- z.B. "v0.14.0-auto-001"
    error_message   TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_auto_mig_state ON dbai_core.autonomous_migrations(state);
CREATE INDEX IF NOT EXISTS idx_auto_mig_created ON dbai_core.autonomous_migrations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_auto_mig_model ON dbai_core.autonomous_migrations(model_used);

-- Migration-Audit-Log: jede Änderung wird protokolliert
CREATE TABLE IF NOT EXISTS dbai_core.migration_audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    migration_id    UUID NOT NULL REFERENCES dbai_core.autonomous_migrations(id) ON DELETE CASCADE,
    action          TEXT NOT NULL CHECK (action IN ('created','reviewed','approved','applied','reverted','rejected','edited')),
    actor           TEXT NOT NULL,                           -- wer hat die Aktion ausgeführt
    details         JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_mig_audit_migration ON dbai_core.migration_audit_log(migration_id);

-- View: Migrations-Übersicht
CREATE OR REPLACE VIEW dbai_core.v_autonomous_migrations AS
SELECT
    am.id,
    am.title,
    am.state,
    am.generated_by,
    am.model_used,
    am.affected_tables,
    am.affected_schemas,
    am.version_tag,
    am.execution_ms,
    am.created_at,
    am.applied_at,
    am.reverted_at,
    (SELECT COUNT(*) FROM dbai_core.migration_audit_log mal WHERE mal.migration_id = am.id) AS audit_count
FROM dbai_core.autonomous_migrations am
ORDER BY am.created_at DESC;


-- ============================================================================
-- FEATURE 2: MULTI-GPU PARALLEL
-- Modelle über mehrere GPUs splitten (Tensor-Parallelism / Layer-Split)
-- ============================================================================

CREATE TABLE IF NOT EXISTS dbai_llm.gpu_split_configs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id        UUID NOT NULL REFERENCES dbai_llm.ghost_models(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,                           -- z.B. "70B-dual-gpu-split"
    strategy        TEXT NOT NULL DEFAULT 'layer_split'
        CHECK (strategy IN ('layer_split','tensor_parallel','pipeline_parallel','auto')),
    gpu_count       INTEGER NOT NULL CHECK (gpu_count >= 2),
    total_vram_mb   INTEGER,
    layer_mapping   JSONB NOT NULL DEFAULT '[]',
    -- Format: [{"gpu_index": 0, "layers": "0-19", "vram_mb": 8000},
    --          {"gpu_index": 1, "layers": "20-39", "vram_mb": 8000}]
    is_active       BOOLEAN DEFAULT false,
    is_default      BOOLEAN DEFAULT false,
    performance_score NUMERIC(5,2),                          -- Benchmark-Score
    avg_tokens_per_sec NUMERIC(8,2),
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(model_id, name)
);

CREATE INDEX IF NOT EXISTS idx_gpu_split_model ON dbai_llm.gpu_split_configs(model_id);
CREATE INDEX IF NOT EXISTS idx_gpu_split_active ON dbai_llm.gpu_split_configs(is_active) WHERE is_active = true;

-- Parallel-Inference-Sessions: Tracking von Multi-GPU-Inferenz
CREATE TABLE IF NOT EXISTS dbai_llm.parallel_inference_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    split_config_id UUID NOT NULL REFERENCES dbai_llm.gpu_split_configs(id) ON DELETE CASCADE,
    model_id        UUID NOT NULL REFERENCES dbai_llm.ghost_models(id) ON DELETE CASCADE,
    state           TEXT NOT NULL DEFAULT 'initializing'
        CHECK (state IN ('initializing','loading','ready','inferring','error','stopped')),
    gpu_allocations JSONB DEFAULT '[]',
    -- Format: [{"gpu_index": 0, "vram_used_mb": 7500, "utilization": 85},...]
    total_vram_used_mb INTEGER DEFAULT 0,
    tokens_generated BIGINT DEFAULT 0,
    requests_served  BIGINT DEFAULT 0,
    avg_latency_ms   NUMERIC(10,2),
    peak_throughput  NUMERIC(8,2),                           -- tokens/sec
    error_message   TEXT,
    started_at      TIMESTAMPTZ DEFAULT now(),
    stopped_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_par_sess_model ON dbai_llm.parallel_inference_sessions(model_id);
CREATE INDEX IF NOT EXISTS idx_par_sess_state ON dbai_llm.parallel_inference_sessions(state);

-- GPU-Sync-Events: Kommunikation zwischen GPUs bei Parallel-Inferenz
CREATE TABLE IF NOT EXISTS dbai_llm.gpu_sync_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES dbai_llm.parallel_inference_sessions(id) ON DELETE CASCADE,
    source_gpu      INTEGER NOT NULL,
    target_gpu      INTEGER NOT NULL,
    sync_type       TEXT NOT NULL CHECK (sync_type IN ('tensor_transfer','gradient_sync','activation_pass','kv_cache_sync')),
    data_size_mb    NUMERIC(10,2),
    latency_us      INTEGER,                                 -- Mikrosekunden
    bandwidth_gbps  NUMERIC(6,2),
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_gpu_sync_session ON dbai_llm.gpu_sync_events(session_id);

-- View: Multi-GPU Status-Übersicht
CREATE OR REPLACE VIEW dbai_llm.v_multi_gpu_status AS
SELECT
    gsc.id AS config_id,
    gsc.name AS config_name,
    gm.name AS model_name,
    gsc.strategy,
    gsc.gpu_count,
    gsc.total_vram_mb,
    gsc.is_active,
    gsc.avg_tokens_per_sec,
    pis.state AS session_state,
    pis.total_vram_used_mb,
    pis.tokens_generated,
    pis.requests_served,
    pis.avg_latency_ms
FROM dbai_llm.gpu_split_configs gsc
JOIN dbai_llm.ghost_models gm ON gm.id = gsc.model_id
LEFT JOIN dbai_llm.parallel_inference_sessions pis
    ON pis.split_config_id = gsc.id AND pis.state NOT IN ('stopped','error')
ORDER BY gsc.is_active DESC, gsc.created_at DESC;


-- ============================================================================
-- FEATURE 3: VISION INTEGRATION
-- Echtzeit-Video/Bild-Analyse mit LLM-Vision-Modellen
-- ============================================================================

CREATE TABLE IF NOT EXISTS dbai_llm.vision_models (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id        UUID REFERENCES dbai_llm.ghost_models(id) ON DELETE SET NULL,
    name            TEXT NOT NULL UNIQUE,
    model_type      TEXT NOT NULL CHECK (model_type IN ('image_classification','object_detection','ocr','image_generation','video_analysis','multimodal','depth_estimation','segmentation')),
    supported_formats TEXT[] DEFAULT ARRAY['jpeg','png','webp'],
    max_resolution  TEXT DEFAULT '4096x4096',
    max_video_length_sec INTEGER DEFAULT 300,
    supports_streaming BOOLEAN DEFAULT false,
    supports_batch   BOOLEAN DEFAULT true,
    avg_inference_ms INTEGER,
    is_available    BOOLEAN DEFAULT true,
    config          JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Vision-Tasks: Analyse-Queue
CREATE TABLE IF NOT EXISTS dbai_llm.vision_tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vision_model_id UUID REFERENCES dbai_llm.vision_models(id) ON DELETE SET NULL,
    media_item_id   UUID,                                    -- Optional: Ref auf media_items
    task_type       TEXT NOT NULL CHECK (task_type IN ('classify','detect','describe','ocr','analyze_video','generate','segment','depth','compare','search')),
    input_type      TEXT NOT NULL CHECK (input_type IN ('image','video','stream','url','base64')),
    input_path      TEXT,
    input_url       TEXT,
    prompt          TEXT,                                     -- User-Prompt für Multimodal
    priority        INTEGER DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
    state           TEXT NOT NULL DEFAULT 'queued'
        CHECK (state IN ('queued','processing','completed','failed','cancelled')),
    result          JSONB,
    -- Format: {"objects": [...], "labels": [...], "confidence": 0.95, "description": "..."}
    result_text     TEXT,                                     -- Human-readable Zusammenfassung
    result_embedding vector(1536),                            -- Vektor-Embedding des Ergebnisses
    confidence      NUMERIC(5,4),
    processing_ms   INTEGER,
    error_message   TEXT,
    retry_count     INTEGER DEFAULT 0,
    max_retries     INTEGER DEFAULT 3,
    requested_by    TEXT DEFAULT 'ghost',
    created_at      TIMESTAMPTZ DEFAULT now(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_vision_task_state ON dbai_llm.vision_tasks(state);
CREATE INDEX IF NOT EXISTS idx_vision_task_type ON dbai_llm.vision_tasks(task_type);
CREATE INDEX IF NOT EXISTS idx_vision_task_media ON dbai_llm.vision_tasks(media_item_id) WHERE media_item_id IS NOT NULL;

-- Vision-Detections: Einzelne erkannte Objekte pro Task
CREATE TABLE IF NOT EXISTS dbai_llm.vision_detections (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id         UUID NOT NULL REFERENCES dbai_llm.vision_tasks(id) ON DELETE CASCADE,
    label           TEXT NOT NULL,
    confidence      NUMERIC(5,4) NOT NULL,
    bbox_x          INTEGER,                                 -- Bounding Box
    bbox_y          INTEGER,
    bbox_width      INTEGER,
    bbox_height     INTEGER,
    frame_number    INTEGER,                                 -- Bei Video: Frame-Nummer
    timestamp_sec   NUMERIC(10,3),                           -- Bei Video: Zeitstempel
    attributes      JSONB DEFAULT '{}',                      -- Zusätzliche Attribute
    embedding       vector(1536),
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_vision_det_task ON dbai_llm.vision_detections(task_id);
CREATE INDEX IF NOT EXISTS idx_vision_det_label ON dbai_llm.vision_detections(label);

-- View: Vision-Analyse-Übersicht
CREATE OR REPLACE VIEW dbai_llm.v_vision_overview AS
SELECT
    vt.id,
    vt.task_type,
    vt.input_type,
    vt.state,
    vt.confidence,
    vt.processing_ms,
    vm.name AS model_name,
    vm.model_type,
    vt.result_text,
    (SELECT COUNT(*) FROM dbai_llm.vision_detections vd WHERE vd.task_id = vt.id) AS detection_count,
    vt.created_at,
    vt.completed_at
FROM dbai_llm.vision_tasks vt
LEFT JOIN dbai_llm.vision_models vm ON vm.id = vt.vision_model_id
ORDER BY vt.created_at DESC;


-- ============================================================================
-- FEATURE 4: DISTRIBUTED GHOSTS
-- Ghost-Instanzen über mehrere Nodes verteilen
-- ============================================================================

CREATE TABLE IF NOT EXISTS dbai_llm.ghost_nodes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_name       TEXT NOT NULL UNIQUE,
    hostname        TEXT NOT NULL,
    ip_address      INET NOT NULL,
    port            INTEGER DEFAULT 3100,
    api_endpoint    TEXT,                                     -- z.B. http://192.168.1.10:3100
    role            TEXT NOT NULL DEFAULT 'worker'
        CHECK (role IN ('coordinator','worker','hybrid','standby')),
    state           TEXT NOT NULL DEFAULT 'offline'
        CHECK (state IN ('online','offline','draining','error','maintenance')),
    gpu_count       INTEGER DEFAULT 0,
    total_vram_mb   INTEGER DEFAULT 0,
    available_vram_mb INTEGER DEFAULT 0,
    total_ram_mb    INTEGER DEFAULT 0,
    cpu_cores       INTEGER DEFAULT 0,
    os_info         TEXT,
    dbai_version    TEXT,
    capabilities    TEXT[] DEFAULT '{}',                      -- z.B. {'inference','training','vision','embedding'}
    max_models      INTEGER DEFAULT 4,                       -- max gleichzeitig geladene Modelle
    loaded_models   INTEGER DEFAULT 0,
    priority        INTEGER DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
    auth_token_hash TEXT,                                    -- bcrypt-Hash für Node-Auth
    tls_enabled     BOOLEAN DEFAULT false,
    last_seen_at    TIMESTAMPTZ,
    joined_at       TIMESTAMPTZ DEFAULT now(),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ghost_nodes_state ON dbai_llm.ghost_nodes(state);
CREATE INDEX IF NOT EXISTS idx_ghost_nodes_role ON dbai_llm.ghost_nodes(role);

-- Node-Heartbeats: Gesundheitsüberwachung
CREATE TABLE IF NOT EXISTS dbai_llm.node_heartbeats (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id         UUID NOT NULL REFERENCES dbai_llm.ghost_nodes(id) ON DELETE CASCADE,
    cpu_usage       NUMERIC(5,2),
    ram_usage_mb    INTEGER,
    ram_total_mb    INTEGER,
    gpu_usage       JSONB DEFAULT '[]',
    -- Format: [{"gpu_index": 0, "utilization": 75, "vram_used_mb": 6000, "temp_c": 65}]
    disk_usage_gb   NUMERIC(10,2),
    network_rx_mbps NUMERIC(8,2),
    network_tx_mbps NUMERIC(8,2),
    active_requests INTEGER DEFAULT 0,
    loaded_models   TEXT[],
    latency_ms      INTEGER,                                 -- Latenz zum Coordinator
    is_healthy      BOOLEAN DEFAULT true,
    error_message   TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_heartbeat_node ON dbai_llm.node_heartbeats(node_id);
CREATE INDEX IF NOT EXISTS idx_heartbeat_time ON dbai_llm.node_heartbeats(created_at DESC);

-- Alte Heartbeats automatisch aufräumen (nur letzte 1000 pro Node behalten)
-- Das wird per Vacuum-Schedule gemacht

-- Distributed Tasks: Aufgaben-Verteilung
CREATE TABLE IF NOT EXISTS dbai_llm.distributed_tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_node_id  UUID REFERENCES dbai_llm.ghost_nodes(id) ON DELETE SET NULL,
    target_node_id  UUID REFERENCES dbai_llm.ghost_nodes(id) ON DELETE SET NULL,
    task_type       TEXT NOT NULL CHECK (task_type IN ('inference','embedding','vision','training','migration','health_check','model_sync')),
    model_name      TEXT,
    payload         JSONB NOT NULL DEFAULT '{}',
    result          JSONB,
    state           TEXT NOT NULL DEFAULT 'pending'
        CHECK (state IN ('pending','assigned','running','completed','failed','timeout','cancelled')),
    priority        INTEGER DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
    timeout_sec     INTEGER DEFAULT 300,
    retry_count     INTEGER DEFAULT 0,
    max_retries     INTEGER DEFAULT 3,
    execution_ms    INTEGER,
    error_message   TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    assigned_at     TIMESTAMPTZ,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_dist_task_state ON dbai_llm.distributed_tasks(state);
CREATE INDEX IF NOT EXISTS idx_dist_task_target ON dbai_llm.distributed_tasks(target_node_id);
CREATE INDEX IF NOT EXISTS idx_dist_task_type ON dbai_llm.distributed_tasks(task_type);

-- Model-Replikation: Welches Modell ist auf welchem Node
CREATE TABLE IF NOT EXISTS dbai_llm.model_replicas (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id        UUID NOT NULL REFERENCES dbai_llm.ghost_models(id) ON DELETE CASCADE,
    node_id         UUID NOT NULL REFERENCES dbai_llm.ghost_nodes(id) ON DELETE CASCADE,
    model_path      TEXT,                                    -- Lokaler Pfad auf dem Node
    state           TEXT NOT NULL DEFAULT 'syncing'
        CHECK (state IN ('syncing','ready','loaded','error','outdated')),
    sync_progress   NUMERIC(5,2) DEFAULT 0,                  -- 0-100%
    file_size_mb    INTEGER,
    checksum        TEXT,
    is_loaded       BOOLEAN DEFAULT false,
    vram_used_mb    INTEGER DEFAULT 0,
    last_synced_at  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(model_id, node_id)
);

CREATE INDEX IF NOT EXISTS idx_model_replica_node ON dbai_llm.model_replicas(node_id);
CREATE INDEX IF NOT EXISTS idx_model_replica_model ON dbai_llm.model_replicas(model_id);

-- View: Cluster-Übersicht
CREATE OR REPLACE VIEW dbai_llm.v_cluster_overview AS
SELECT
    gn.id AS node_id,
    gn.node_name,
    gn.ip_address,
    gn.role,
    gn.state,
    gn.gpu_count,
    gn.total_vram_mb,
    gn.available_vram_mb,
    gn.loaded_models,
    gn.max_models,
    gn.last_seen_at,
    (SELECT COUNT(*) FROM dbai_llm.model_replicas mr WHERE mr.node_id = gn.id AND mr.is_loaded = true) AS active_models,
    (SELECT COUNT(*) FROM dbai_llm.distributed_tasks dt WHERE dt.target_node_id = gn.id AND dt.state = 'running') AS running_tasks,
    nh.cpu_usage,
    nh.ram_usage_mb,
    nh.latency_ms,
    nh.is_healthy
FROM dbai_llm.ghost_nodes gn
LEFT JOIN LATERAL (
    SELECT * FROM dbai_llm.node_heartbeats
    WHERE node_id = gn.id
    ORDER BY created_at DESC LIMIT 1
) nh ON true
ORDER BY gn.role, gn.node_name;

-- View: Task-Routing-Statistik
CREATE OR REPLACE VIEW dbai_llm.v_task_routing_stats AS
SELECT
    gn.node_name,
    dt.task_type,
    COUNT(*) AS total_tasks,
    COUNT(*) FILTER (WHERE dt.state = 'completed') AS completed,
    COUNT(*) FILTER (WHERE dt.state = 'failed') AS failed,
    AVG(dt.execution_ms) FILTER (WHERE dt.state = 'completed') AS avg_exec_ms,
    MAX(dt.execution_ms) FILTER (WHERE dt.state = 'completed') AS max_exec_ms
FROM dbai_llm.distributed_tasks dt
JOIN dbai_llm.ghost_nodes gn ON gn.id = dt.target_node_id
GROUP BY gn.node_name, dt.task_type
ORDER BY gn.node_name, total_tasks DESC;


-- ============================================================================
-- FEATURE 5: MODEL MARKETPLACE
-- GGUF-Modelle direkt von HuggingFace browsen, downloaden, installieren
-- ============================================================================

CREATE TABLE IF NOT EXISTS dbai_llm.marketplace_catalog (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hf_repo_id      TEXT NOT NULL,                           -- z.B. "TheBloke/Llama-2-7B-GGUF"
    hf_filename     TEXT,                                    -- z.B. "llama-2-7b.Q4_K_M.gguf"
    model_name      TEXT NOT NULL,
    display_name    TEXT,
    author          TEXT,
    description     TEXT,
    model_type      TEXT,                                    -- llama, mistral, phi, gemma, etc.
    parameters      TEXT,                                    -- "7B", "13B", "70B"
    quantization    TEXT,                                    -- Q4_K_M, Q5_K_S, Q8_0, etc.
    file_size_mb    INTEGER,
    required_vram_mb INTEGER,
    required_ram_mb  INTEGER,
    context_size    INTEGER DEFAULT 4096,
    license         TEXT,
    tags            TEXT[] DEFAULT '{}',
    capabilities    TEXT[] DEFAULT '{}',                      -- chat, code, instruct, vision, etc.
    supported_languages TEXT[] DEFAULT ARRAY['en'],
    hf_likes        INTEGER DEFAULT 0,
    hf_downloads    BIGINT DEFAULT 0,
    hf_trending_score NUMERIC(8,2) DEFAULT 0,
    ghost_rating    NUMERIC(3,2),                            -- Ghost-eigene Bewertung 0-5
    ghost_review    TEXT,
    is_featured     BOOLEAN DEFAULT false,
    is_recommended  BOOLEAN DEFAULT false,
    is_compatible   BOOLEAN DEFAULT true,                    -- Kompatibel mit DBAI?
    last_hf_sync    TIMESTAMPTZ,
    hf_metadata     JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(hf_repo_id, hf_filename)
);

CREATE INDEX IF NOT EXISTS idx_mp_catalog_type ON dbai_llm.marketplace_catalog(model_type);
CREATE INDEX IF NOT EXISTS idx_mp_catalog_quant ON dbai_llm.marketplace_catalog(quantization);
CREATE INDEX IF NOT EXISTS idx_mp_catalog_params ON dbai_llm.marketplace_catalog(parameters);
CREATE INDEX IF NOT EXISTS idx_mp_catalog_featured ON dbai_llm.marketplace_catalog(is_featured) WHERE is_featured = true;
CREATE INDEX IF NOT EXISTS idx_mp_catalog_search ON dbai_llm.marketplace_catalog USING gin(to_tsvector('english', coalesce(model_name,'') || ' ' || coalesce(description,'') || ' ' || coalesce(author,'')));

-- Model-Downloads: Download-Queue mit Progress
CREATE TABLE IF NOT EXISTS dbai_llm.model_downloads (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    catalog_id      UUID REFERENCES dbai_llm.marketplace_catalog(id) ON DELETE SET NULL,
    hf_repo_id      TEXT NOT NULL,
    hf_filename     TEXT NOT NULL,
    target_path     TEXT,                                    -- Lokaler Speicherpfad
    state           TEXT NOT NULL DEFAULT 'queued'
        CHECK (state IN ('queued','downloading','verifying','installing','completed','failed','cancelled','paused')),
    progress_percent NUMERIC(5,2) DEFAULT 0,
    downloaded_bytes BIGINT DEFAULT 0,
    total_bytes     BIGINT,
    speed_mbps      NUMERIC(8,2),
    eta_seconds     INTEGER,
    checksum_expected TEXT,
    checksum_actual  TEXT,
    auto_load       BOOLEAN DEFAULT false,                   -- Nach Download automatisch laden?
    auto_config     JSONB DEFAULT '{}',                      -- GPU-Konfiguration für Auto-Load
    retry_count     INTEGER DEFAULT 0,
    max_retries     INTEGER DEFAULT 3,
    error_message   TEXT,
    requested_by    TEXT DEFAULT 'user',
    created_at      TIMESTAMPTZ DEFAULT now(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_model_dl_state ON dbai_llm.model_downloads(state);
CREATE INDEX IF NOT EXISTS idx_model_dl_repo ON dbai_llm.model_downloads(hf_repo_id);

-- Model-Reviews: User-Bewertungen
CREATE TABLE IF NOT EXISTS dbai_llm.model_reviews (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    catalog_id      UUID REFERENCES dbai_llm.marketplace_catalog(id) ON DELETE CASCADE,
    model_id        UUID REFERENCES dbai_llm.ghost_models(id) ON DELETE SET NULL,
    reviewer        TEXT NOT NULL DEFAULT 'ghost',           -- ghost | user
    rating          NUMERIC(3,2) NOT NULL CHECK (rating BETWEEN 0 AND 5),
    title           TEXT,
    review_text     TEXT,
    benchmark_results JSONB DEFAULT '{}',
    -- Format: {"tokens_per_sec": 45.2, "perplexity": 5.8, "context_test": "pass"}
    use_case        TEXT,                                    -- chat, code, creative, etc.
    hardware_info   TEXT,                                    -- Auf welcher Hardware getestet
    is_verified     BOOLEAN DEFAULT false,                   -- Von Ghost verifiziert
    helpful_votes   INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_model_reviews_catalog ON dbai_llm.model_reviews(catalog_id);
CREATE INDEX IF NOT EXISTS idx_model_reviews_rating ON dbai_llm.model_reviews(rating DESC);

-- View: Marketplace-Übersicht
CREATE OR REPLACE VIEW dbai_llm.v_marketplace AS
SELECT
    mc.id,
    mc.model_name,
    mc.display_name,
    mc.author,
    mc.model_type,
    mc.parameters,
    mc.quantization,
    mc.file_size_mb,
    mc.required_vram_mb,
    mc.context_size,
    mc.license,
    mc.capabilities,
    mc.hf_likes,
    mc.hf_downloads,
    mc.ghost_rating,
    mc.is_featured,
    mc.is_recommended,
    mc.is_compatible,
    (SELECT AVG(mr.rating) FROM dbai_llm.model_reviews mr WHERE mr.catalog_id = mc.id) AS avg_user_rating,
    (SELECT COUNT(*) FROM dbai_llm.model_reviews mr WHERE mr.catalog_id = mc.id) AS review_count,
    EXISTS(SELECT 1 FROM dbai_llm.model_downloads md WHERE md.catalog_id = mc.id AND md.state = 'completed') AS is_downloaded,
    EXISTS(SELECT 1 FROM dbai_llm.ghost_models gm WHERE gm.name = mc.model_name AND gm.is_loaded = true) AS is_loaded
FROM dbai_llm.marketplace_catalog mc
ORDER BY mc.is_featured DESC, mc.hf_downloads DESC;

-- View: Download-Queue
CREATE OR REPLACE VIEW dbai_llm.v_download_queue AS
SELECT
    md.id,
    md.hf_repo_id,
    md.hf_filename,
    md.state,
    md.progress_percent,
    md.speed_mbps,
    md.eta_seconds,
    md.downloaded_bytes,
    md.total_bytes,
    mc.model_name,
    mc.display_name,
    mc.file_size_mb,
    md.created_at,
    md.started_at,
    md.completed_at
FROM dbai_llm.model_downloads md
LEFT JOIN dbai_llm.marketplace_catalog mc ON mc.id = md.catalog_id
ORDER BY
    CASE md.state
        WHEN 'downloading' THEN 1
        WHEN 'verifying' THEN 2
        WHEN 'installing' THEN 3
        WHEN 'queued' THEN 4
        WHEN 'paused' THEN 5
        ELSE 6
    END,
    md.created_at DESC;


-- ============================================================================
-- SEED DATA: Marketplace-Vorschläge (Top-Modelle)
-- ============================================================================

INSERT INTO dbai_llm.marketplace_catalog
    (hf_repo_id, hf_filename, model_name, display_name, author, description, model_type, parameters, quantization, file_size_mb, required_vram_mb, required_ram_mb, context_size, license, tags, capabilities, supported_languages, hf_likes, hf_downloads, is_featured, is_recommended, ghost_rating, ghost_review)
VALUES
    ('bartowski/Llama-3.3-70B-Instruct-GGUF', 'Llama-3.3-70B-Instruct-Q4_K_M.gguf', 'llama-3.3-70b-instruct', 'Llama 3.3 70B Instruct', 'Meta', 'Metas bestes Open-Source-Modell. Exzellent für Chat, Code und Reasoning.', 'llama', '70B', 'Q4_K_M', 42080, 44000, 8192, 131072, 'Llama 3.3 Community', ARRAY['chat','instruct','flagship'], ARRAY['chat','code','reasoning','multilingual'], ARRAY['en','de','fr','es','it','pt','hi','th'], 5200, 890000, true, true, 4.8, 'Ghost-Empfehlung: Bestes Allround-Modell für leistungsstarke Hardware.'),

    ('bartowski/Qwen2.5-Coder-32B-Instruct-GGUF', 'Qwen2.5-Coder-32B-Instruct-Q4_K_M.gguf', 'qwen2.5-coder-32b', 'Qwen 2.5 Coder 32B', 'Qwen', 'Spezialisiertes Code-Modell von Alibaba. Top-Performance bei Programmieraufgaben.', 'qwen', '32B', 'Q4_K_M', 19850, 22000, 6144, 32768, 'Apache 2.0', ARRAY['code','instruct'], ARRAY['code','reasoning','analysis'], ARRAY['en','zh'], 3100, 420000, true, true, 4.7, 'Ghost-Empfehlung: Bestes Code-Modell, ideal für Autonomous Coding.'),

    ('bartowski/gemma-2-27b-it-GGUF', 'gemma-2-27b-it-Q4_K_M.gguf', 'gemma-2-27b-it', 'Gemma 2 27B IT', 'Google', 'Googles effizientes Modell mit starker Multilingualität.', 'gemma', '27B', 'Q4_K_M', 16320, 18000, 4096, 8192, 'Gemma', ARRAY['chat','instruct'], ARRAY['chat','reasoning','multilingual'], ARRAY['en','de','fr','es','ja','ko','zh'], 2800, 310000, true, false, 4.5, 'Effizient und multilingual. Gute Wahl für mittlere Hardware.'),

    ('bartowski/Mistral-Small-24B-Instruct-2501-GGUF', 'Mistral-Small-24B-Instruct-2501-Q4_K_M.gguf', 'mistral-small-24b', 'Mistral Small 24B', 'Mistral AI', 'Kompaktes aber leistungsstarkes Modell von Mistral AI.', 'mistral', '24B', 'Q4_K_M', 14400, 16000, 4096, 32768, 'Apache 2.0', ARRAY['chat','instruct'], ARRAY['chat','code','reasoning'], ARRAY['en','fr','de','es','it'], 1900, 280000, true, true, 4.6, 'Ghost-Empfehlung: Bestes Preis-Leistungs-Verhältnis.'),

    ('bartowski/Phi-4-mini-instruct-GGUF', 'Phi-4-mini-instruct-Q4_K_M.gguf', 'phi-4-mini', 'Phi 4 Mini', 'Microsoft', 'Microsofts kleinstes Modell mit überraschend starker Leistung.', 'phi', '3.8B', 'Q4_K_M', 2360, 3500, 2048, 16384, 'MIT', ARRAY['chat','instruct','small'], ARRAY['chat','code','reasoning'], ARRAY['en'], 4100, 650000, true, true, 4.3, 'Perfekt für schwache Hardware. Erstaunlich gut für die Größe.'),

    ('bartowski/DeepSeek-R1-Distill-Llama-8B-GGUF', 'DeepSeek-R1-Distill-Llama-8B-Q4_K_M.gguf', 'deepseek-r1-distill-8b', 'DeepSeek R1 Distill 8B', 'DeepSeek', 'Destilliertes Reasoning-Modell. Chain-of-Thought ohne 600B Parameter.', 'llama', '8B', 'Q4_K_M', 4920, 6000, 2048, 32768, 'MIT', ARRAY['reasoning','instruct'], ARRAY['reasoning','code','analysis'], ARRAY['en','zh'], 3500, 520000, false, true, 4.4, 'Bestes Reasoning für wenig VRAM. Denkt Schritt für Schritt.'),

    ('mys/ggml_llava-v1.5-13b', 'ggml-model-q4_k.gguf', 'llava-v1.5-13b', 'LLaVA 1.5 13B Vision', 'LLaVA Team', 'Multimodales Vision+Language Modell. Kann Bilder verstehen und beschreiben.', 'llava', '13B', 'Q4_K', 7360, 10000, 4096, 4096, 'Apache 2.0', ARRAY['vision','multimodal'], ARRAY['vision','chat','describe'], ARRAY['en'], 1200, 180000, true, true, 4.2, 'Ghost-Empfehlung: Bestes Vision-Modell für lokale Ausführung.'),

    ('bartowski/Llama-3.2-3B-Instruct-GGUF', 'Llama-3.2-3B-Instruct-Q4_K_M.gguf', 'llama-3.2-3b-instruct', 'Llama 3.2 3B Instruct', 'Meta', 'Kleines, schnelles Modell. Ideal als Embedded-Ghost oder für Edge-Devices.', 'llama', '3B', 'Q4_K_M', 1920, 2500, 1024, 131072, 'Llama 3.2 Community', ARRAY['chat','instruct','small','edge'], ARRAY['chat','multilingual'], ARRAY['en','de','fr','es','it','pt','hi','th'], 2100, 380000, false, true, 4.0, 'Ideal für Distributed Ghosts auf schwachen Nodes.')
ON CONFLICT (hf_repo_id, hf_filename) DO NOTHING;


-- ============================================================================
-- DOKUMENTATION IN DER DB: system_memory + changelog
-- ============================================================================

-- === SYSTEM MEMORY: Feature-Dokumentation ===

-- Feature 1: Autonomous Coding
INSERT INTO dbai_knowledge.system_memory (id, category, title, content, related_schemas, tags, author) VALUES
(gen_random_uuid(), 'feature', 'Autonomous Coding',
'AUTONOMOUS CODING (v0.14.0)
==========================
Ghost kann eigene SQL-Migrationen generieren, reviewen und anwenden.

TABELLEN:
- dbai_core.autonomous_migrations — Generierte Migrationen mit State-Machine (draft→review→approved→applied)
- dbai_core.migration_audit_log — Vollständiges Audit-Log jeder Migration-Aktion

VIEWS:
- dbai_core.v_autonomous_migrations — Übersicht aller Migrationen mit Audit-Count

WORKFLOW:
1. Ghost generiert SQL basierend auf User-Prompt oder eigenem Bedarf
2. Migration wird als "draft" gespeichert mit Rollback-SQL
3. Review-Phase: Ghost oder Admin prüft den SQL
4. Nach Approval wird Migration applied und execution_ms gemessen
5. Bei Problemen: Revert über rollback_sql möglich
6. Jede Aktion wird im migration_audit_log protokolliert

SICHERHEIT:
- Nur Admin kann Migrationen approven/applyen
- Checksum-Verifizierung des SQL vor Ausführung
- Rollback-SQL ist Pflicht für approved Migrationen
- Audit-Log ist unveränderbar (kein UPDATE/DELETE)',
ARRAY['dbai_core'], ARRAY['autonomous','coding','migration','ghost'], 'ghost');

-- Feature 2: Multi-GPU Parallel
INSERT INTO dbai_knowledge.system_memory (id, category, title, content, related_schemas, tags, author) VALUES
(gen_random_uuid(), 'feature', 'Multi-GPU Parallel',
'MULTI-GPU PARALLEL (v0.14.0)
============================
Modelle über mehrere GPUs verteilen für größere Modelle und höohere Performance.

TABELLEN:
- dbai_llm.gpu_split_configs — Layer-Verteilung pro GPU (layer_split, tensor_parallel, pipeline_parallel, auto)
- dbai_llm.parallel_inference_sessions — Aktive Multi-GPU-Inferenz-Sessions
- dbai_llm.gpu_sync_events — GPU-zu-GPU-Kommunikation (Tensor-Transfer, KV-Cache-Sync)

VIEWS:
- dbai_llm.v_multi_gpu_status — Live-Status aller Multi-GPU-Konfigurationen

STRATEGIEN:
1. layer_split: Layers werden auf GPUs verteilt (Standard für GGUF/llama.cpp)
2. tensor_parallel: Tensor-Operationen parallel auf allen GPUs (schnellste Inferenz)
3. pipeline_parallel: Pipeline-Stages auf verschiedenen GPUs
4. auto: Ghost wählt beste Strategie basierend auf Hardware

LAYER-MAPPING FORMAT:
[{"gpu_index": 0, "layers": "0-19", "vram_mb": 8000},
 {"gpu_index": 1, "layers": "20-39", "vram_mb": 8000}]

BENCHMARK:
- performance_score und avg_tokens_per_sec werden automatisch gemessen
- Sync-Events zeigen Bandbreite und Latenz zwischen GPUs',
ARRAY['dbai_llm'], ARRAY['multi-gpu','parallel','tensor','split'], 'ghost');

-- Feature 3: Vision Integration
INSERT INTO dbai_knowledge.system_memory (id, category, title, content, related_schemas, tags, author) VALUES
(gen_random_uuid(), 'feature', 'Vision Integration',
'VISION INTEGRATION (v0.14.0)
============================
Echtzeit-Video/Bild-Analyse mit lokalen LLM-Vision-Modellen.

TABELLEN:
- dbai_llm.vision_models — Registrierte Vision-Modelle mit Fähigkeiten
- dbai_llm.vision_tasks — Analyse-Queue (classify, detect, describe, ocr, segment, etc.)
- dbai_llm.vision_detections — Einzelne erkannte Objekte mit Bounding-Box und Embedding

VIEWS:
- dbai_llm.v_vision_overview — Übersicht aller Vision-Aufgaben mit Detection-Count

TASK-TYPEN:
- classify: Bild-Klassifizierung
- detect: Objekt-Erkennung mit Bounding-Boxes
- describe: Bildbeschreibung (Multimodal)
- ocr: Texterkennung
- analyze_video: Video-Analyse (Frame-by-Frame)
- segment: Semantische Segmentierung
- depth: Tiefenschätzung
- compare: Bildvergleich
- search: Visuelle Suche per Embedding

INTEGRATION:
- media_item_id verknüpft mit dbai_workshop.media_items
- result_embedding (vector(1536)) für semantische Bildsuche
- Detections haben eigene Embeddings für Objekt-Suche
- Unterstützt Streaming für Echtzeit-Video-Analyse',
ARRAY['dbai_llm','dbai_workshop'], ARRAY['vision','image','video','detection','ocr'], 'ghost');

-- Feature 4: Distributed Ghosts
INSERT INTO dbai_knowledge.system_memory (id, category, title, content, related_schemas, tags, author) VALUES
(gen_random_uuid(), 'feature', 'Distributed Ghosts',
'DISTRIBUTED GHOSTS (v0.14.0)
============================
Multiple Ghost-Instanzen über mehrere Nodes im Netzwerk verteilen.

TABELLEN:
- dbai_llm.ghost_nodes — Node-Registry (Coordinator/Worker/Hybrid/Standby)
- dbai_llm.node_heartbeats — Gesundheitsüberwachung (CPU, RAM, GPU, Latenz)
- dbai_llm.distributed_tasks — Aufgaben-Verteilung und Routing
- dbai_llm.model_replicas — Welches Modell auf welchem Node

VIEWS:
- dbai_llm.v_cluster_overview — Live-Cluster-Status mit letztem Heartbeat
- dbai_llm.v_task_routing_stats — Statistik der Task-Verteilung pro Node

ROLLEN:
- coordinator: Verteilt Tasks an Worker, hat Cluster-Überblick
- worker: Führt Inferenz/Tasks aus
- hybrid: Koordinator + Worker (Standardmodus für einzelnen Node)
- standby: Bereit, aber nicht aktiv (Failover)

TASK-ROUTING:
1. Coordinator empfängt Anfrage
2. Prüft Node-Verfügbarkeit und Modell-Repliken
3. Wählt besten Node basierend auf: Latenz, VRAM, Load, Priority
4. Task wird an target_node gesendet
5. Ergebnis wird zurückgemeldet und aggregiert

SICHERHEIT:
- auth_token_hash (bcrypt) für Node-Authentifizierung
- TLS-Support für verschlüsselte Node-Kommunikation
- Heartbeat-Timeout erkennt ausgefallene Nodes automatisch',
ARRAY['dbai_llm'], ARRAY['distributed','cluster','nodes','failover'], 'ghost');

-- Feature 5: Model Marketplace
INSERT INTO dbai_knowledge.system_memory (id, category, title, content, related_schemas, tags, author) VALUES
(gen_random_uuid(), 'feature', 'Model Marketplace',
'MODEL MARKETPLACE (v0.14.0) - GGUF-Modelle direkt von HuggingFace browsen, downloaden und installieren. Tabellen: marketplace_catalog, model_downloads, model_reviews. Views: v_marketplace, v_download_queue. 8 vorinstallierte Top-Modelle. Download-Workflow: queued, downloading, verifying, installing, completed. Auto-Load Support. Ghost-Bewertungen mit Benchmark-Ergebnissen.',
ARRAY['dbai_llm'], ARRAY['marketplace','huggingface','download','gguf','models'], 'ghost');

-- === Schema-Map ===
INSERT INTO dbai_knowledge.system_memory (id, category, title, content, related_schemas, tags, author) VALUES
(gen_random_uuid(), 'schema_map', 'v0.14.0 Schema-Map',
'SCHEMA-MAP v0.14.0: 15 neue Tabellen, 8 neue Views, 28 Indizes, 8 Seed-Modelle. dbai_core: autonomous_migrations, migration_audit_log. dbai_llm: gpu_split_configs, parallel_inference_sessions, gpu_sync_events, vision_models, vision_tasks, vision_detections, ghost_nodes, node_heartbeats, distributed_tasks, model_replicas, marketplace_catalog, model_downloads, model_reviews.',
ARRAY['dbai_core','dbai_llm'], ARRAY['schema','v0.14.0','tables','views'], 'ghost');

-- === Architektur ===
INSERT INTO dbai_knowledge.system_memory (id, category, title, content, related_schemas, tags, author) VALUES
(gen_random_uuid(), 'architecture', 'v0.14.0 System-Architektur',
'ARCHITEKTUR v0.14.0: Marketplace liefert Modelle. Multi-GPU verteilt grosse Modelle (layer_split, tensor_parallel, pipeline_parallel). Distributed Ghosts repliziert ueber Nodes (Koordinator/Worker). Vision analysiert Bilder/Videos. Autonomous Coding generiert SQL-Migrationen. Skalierung: Single-Node Multi-GPU, Multi-Node Distributed, Edge 3B-Modelle, Hybrid Koordinator+Worker.',
ARRAY['dbai_core','dbai_llm'], ARRAY['architecture','v0.14.0','design','cluster'], 'ghost');

-- === CHANGELOG ENTRIES ===
INSERT INTO dbai_knowledge.changelog (version, change_type, title, description, author) VALUES
('0.14.0', 'feature', 'Autonomous Coding',
'Ghost kann eigene SQL-Migrationen generieren, reviewen und anwenden. Neue Tabellen: autonomous_migrations, migration_audit_log. State-Machine: draft, review, approved, applied. Vollstaendiger Audit-Trail. Rollback-Support.',
'ghost'),
('0.14.0', 'feature', 'Multi-GPU Parallel',
'Modelle ueber mehrere GPUs verteilen. Strategien: layer_split, tensor_parallel, pipeline_parallel, auto. Neue Tabellen: gpu_split_configs, parallel_inference_sessions, gpu_sync_events.',
'ghost'),
('0.14.0', 'feature', 'Vision Integration',
'Echtzeit-Video/Bild-Analyse mit lokalen Vision-Modellen. Task-Queue fuer classify, detect, describe, ocr, segment, depth. Neue Tabellen: vision_models, vision_tasks, vision_detections.',
'ghost'),
('0.14.0', 'feature', 'Distributed Ghosts',
'Ghost-Instanzen ueber mehrere Nodes verteilen. Koordinator/Worker-Architektur mit automatischem Task-Routing. Neue Tabellen: ghost_nodes, node_heartbeats, distributed_tasks, model_replicas.',
'ghost'),
('0.14.0', 'feature', 'Model Marketplace',
'GGUF-Modelle direkt von HuggingFace browsen und installieren. Kuratierter Katalog mit Ghost-Bewertungen. Download-Queue mit Echtzeit-Progress. 8 vorinstallierte Top-Modelle.',
'ghost'),
('0.14.0', 'schema', 'v0.14.0 Schema-Erweiterung',
'15 neue Tabellen, 8 neue Views, 28 Indizes, 8 Seed-Modelle. Schemas erweitert: dbai_core (+2 Tabellen), dbai_llm (+13 Tabellen). Full-Text-Search auf Marketplace. Vector-Embeddings fuer Vision-Detections.',
'ghost');

COMMIT;
