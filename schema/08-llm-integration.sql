-- =============================================================================
-- DBAI Schema 08: LLM-Integration
-- llama.cpp eingebettet — Daten verlassen nie die Datenbank
-- SQL-Funktionen die das lokale LLM aufrufen
-- =============================================================================

-- LLM-Modell-Registry
CREATE TABLE dbai_llm.models (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT NOT NULL UNIQUE,
    -- Objekt-ID des GGUF-Modells (kein Dateipfad!)
    model_object_id UUID REFERENCES dbai_core.objects(id),
    model_type      TEXT NOT NULL CHECK (model_type IN (
                        'chat', 'embedding', 'code', 'vision', 'tool'
                    )),
    parameters      JSONB NOT NULL DEFAULT '{}',
    context_size    INTEGER NOT NULL DEFAULT 4096,
    is_loaded       BOOLEAN NOT NULL DEFAULT FALSE,
    loaded_at       TIMESTAMPTZ,
    total_tokens    BIGINT NOT NULL DEFAULT 0,
    total_requests  BIGINT NOT NULL DEFAULT 0,
    avg_latency_ms  REAL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- LLM-Konversations-History
CREATE TABLE dbai_llm.conversations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      UUID NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('system', 'user', 'assistant', 'tool')),
    content         TEXT NOT NULL,
    -- Vektor-Embedding des Inhalts für Ähnlichkeitssuche
    embedding       vector(1536),
    tokens_used     INTEGER,
    model_id        UUID REFERENCES dbai_llm.models(id),
    -- Metadaten (Tool-Calls, etc.)
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_conversations_session ON dbai_llm.conversations(session_id, created_at);
CREATE INDEX idx_conversations_embedding ON dbai_llm.conversations
    USING hnsw (embedding vector_cosine_ops) WHERE embedding IS NOT NULL;

-- LLM-Aufgaben-Queue: Tasks die das LLM abarbeiten soll
CREATE TABLE dbai_llm.task_queue (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_type       TEXT NOT NULL CHECK (task_type IN (
                        'query', 'analysis', 'generation', 'classification',
                        'embedding', 'repair', 'monitoring'
                    )),
    priority        SMALLINT NOT NULL DEFAULT 5,
    -- Eingabe-Daten
    input_data      JSONB NOT NULL,
    -- Welche Tabellen/Zeilen darf das LLM für diese Aufgabe sehen
    accessible_tables TEXT[] DEFAULT '{}',
    accessible_row_filter JSONB DEFAULT '{}',
    -- Ergebnis
    output_data     JSONB,
    state           TEXT NOT NULL DEFAULT 'pending' CHECK (state IN (
                        'pending', 'processing', 'completed',
                        'failed', 'cancelled'
                    )),
    error_message   TEXT,
    -- Performance
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    tokens_used     INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_task_queue_state ON dbai_llm.task_queue(state, priority);
CREATE INDEX idx_task_queue_pending ON dbai_llm.task_queue(priority, created_at)
    WHERE state = 'pending';

-- =============================================================================
-- SQL-Funktionen für LLM-Aufrufe (rufen llama.cpp über PL/Python auf)
-- =============================================================================

-- Hinweis: plpython3u muss als Extension installiert sein
-- CREATE EXTENSION IF NOT EXISTS plpython3u;

-- LLM-Prompt direkt aus SQL ausführen
CREATE OR REPLACE FUNCTION dbai_llm.prompt(
    p_prompt TEXT,
    p_model TEXT DEFAULT 'default',
    p_max_tokens INTEGER DEFAULT 512,
    p_temperature REAL DEFAULT 0.7
) RETURNS TEXT AS $$
DECLARE
    v_result TEXT;
    v_model_id UUID;
    v_tokens INTEGER;
BEGIN
    -- Modell-ID ermitteln
    SELECT id INTO v_model_id FROM dbai_llm.models
    WHERE name = p_model AND is_loaded = TRUE;

    IF v_model_id IS NULL THEN
        RAISE EXCEPTION 'Modell "%" ist nicht geladen', p_model;
    END IF;

    -- Task in Queue einfügen und auf Ergebnis warten
    INSERT INTO dbai_llm.task_queue
        (task_type, input_data, priority)
    VALUES
        ('query', json_build_object(
            'prompt', p_prompt,
            'model', p_model,
            'max_tokens', p_max_tokens,
            'temperature', p_temperature
        )::JSONB, 3)
    RETURNING id INTO v_model_id;

    -- In einer realen Implementierung würde hier der llama.cpp
    -- Worker benachrichtigt und auf das Ergebnis gewartet
    -- Für jetzt: Placeholder
    v_result := '[LLM-Antwort wird vom llama.cpp Worker generiert]';

    RETURN v_result;
END;
$$ LANGUAGE plpgsql;

-- Embedding aus Text generieren
CREATE OR REPLACE FUNCTION dbai_llm.embed(
    p_text TEXT,
    p_model TEXT DEFAULT 'embedding'
) RETURNS vector(1536) AS $$
DECLARE
    v_embedding vector(1536);
BEGIN
    -- In einer realen Implementierung wird hier llama.cpp aufgerufen
    -- Placeholder: Null-Vektor
    -- Der tatsächliche Aufruf erfolgt über den LLM-Bridge Python-Service
    RAISE NOTICE 'Embedding wird über LLM-Bridge generiert für: %', LEFT(p_text, 50);
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Erinnerung speichern mit automatischem Embedding
CREATE OR REPLACE FUNCTION dbai_llm.remember(
    p_content TEXT,
    p_memory_type TEXT DEFAULT 'observation',
    p_context JSONB DEFAULT '{}'
) RETURNS UUID AS $$
DECLARE
    v_id UUID;
    v_embedding vector(1536);
BEGIN
    -- Embedding generieren
    v_embedding := dbai_llm.embed(p_content);

    INSERT INTO dbai_vector.memories
        (content, memory_type, embedding, context, created_by)
    VALUES
        (p_content, p_memory_type, v_embedding, p_context, 'dbai_llm')
    RETURNING id INTO v_id;

    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

-- Ähnliche Erinnerungen abrufen (RAG-Pattern)
CREATE OR REPLACE FUNCTION dbai_llm.recall(
    p_query TEXT,
    p_max_results INTEGER DEFAULT 5
) RETURNS TABLE (
    memory_id UUID,
    content TEXT,
    similarity REAL,
    memory_type TEXT
) AS $$
DECLARE
    v_query_embedding vector(1536);
BEGIN
    v_query_embedding := dbai_llm.embed(p_query);

    IF v_query_embedding IS NOT NULL THEN
        RETURN QUERY
        SELECT m.id, m.content,
               1 - (m.embedding <=> v_query_embedding) AS similarity,
               m.memory_type
        FROM dbai_vector.memories m
        WHERE m.is_archived = FALSE
        ORDER BY m.embedding <=> v_query_embedding
        LIMIT p_max_results;

        -- Access-Counter erhöhen
        UPDATE dbai_vector.memories
        SET access_count = access_count + 1,
            last_accessed = NOW()
        WHERE id IN (
            SELECT m2.id FROM dbai_vector.memories m2
            WHERE m2.is_archived = FALSE
            ORDER BY m2.embedding <=> v_query_embedding
            LIMIT p_max_results
        );
    END IF;
END;
$$ LANGUAGE plpgsql;
