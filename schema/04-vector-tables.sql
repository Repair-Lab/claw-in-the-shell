-- =============================================================================
-- DBAI Schema 04: Vektor-Tabellen
-- KI-Gedanken und Erinnerungen als mathematische Vektoren (pgvector)
-- =============================================================================

-- KI-Erinnerungen: Langzeit-Speicher des LLM
CREATE TABLE dbai_vector.memories (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Vektor-Embedding (1536 Dimensionen, kompatibel mit gängigen Modellen)
    embedding       vector(1536) NOT NULL,
    -- Klartext der Erinnerung
    content         TEXT NOT NULL,
    -- Typ der Erinnerung
    memory_type     TEXT NOT NULL CHECK (memory_type IN (
                        'fact', 'observation', 'decision', 'error',
                        'lesson', 'context', 'conversation', 'task'
                    )),
    -- Relevanz-Score (wird über Zeit angepasst)
    relevance       REAL NOT NULL DEFAULT 1.0 CHECK (relevance BETWEEN 0 AND 1),
    -- Wie oft wurde diese Erinnerung abgerufen
    access_count    INTEGER NOT NULL DEFAULT 0,
    last_accessed   TIMESTAMPTZ,
    -- Verknüpfung zu anderen Erinnerungen
    related_ids     UUID[] DEFAULT '{}',
    -- Kontext-Metadaten
    context         JSONB DEFAULT '{}',
    -- Welche Rolle hat diese Erinnerung erstellt
    created_by      TEXT NOT NULL DEFAULT 'dbai_llm',
    -- Soft-Delete
    is_archived     BOOLEAN NOT NULL DEFAULT FALSE
);

-- HNSW-Index für schnelle Ähnlichkeitssuche (Cosine-Distanz)
CREATE INDEX idx_memories_embedding ON dbai_vector.memories
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);

CREATE INDEX idx_memories_type ON dbai_vector.memories(memory_type);
CREATE INDEX idx_memories_relevance ON dbai_vector.memories(relevance DESC);
CREATE INDEX idx_memories_ts ON dbai_vector.memories(ts DESC);

-- =============================================================================
-- Ähnlichkeitssuche: Finde die nächsten N Erinnerungen zu einem Vektor
-- =============================================================================
CREATE OR REPLACE FUNCTION dbai_vector.search_memories(
    query_embedding vector(1536),
    max_results INTEGER DEFAULT 10,
    min_relevance REAL DEFAULT 0.1,
    filter_type TEXT DEFAULT NULL
) RETURNS TABLE (
    id UUID,
    content TEXT,
    memory_type TEXT,
    relevance REAL,
    similarity REAL,
    ts TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        m.id,
        m.content,
        m.memory_type,
        m.relevance,
        1 - (m.embedding <=> query_embedding) AS similarity,
        m.ts
    FROM dbai_vector.memories m
    WHERE m.is_archived = FALSE
      AND m.relevance >= min_relevance
      AND (filter_type IS NULL OR m.memory_type = filter_type)
    ORDER BY m.embedding <=> query_embedding
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Automatische Relevanz-Verringerung (Vergessen)
-- Erinnerungen die lange nicht abgerufen wurden verlieren Relevanz
-- =============================================================================
CREATE OR REPLACE FUNCTION dbai_vector.decay_relevance()
RETURNS void AS $$
BEGIN
    UPDATE dbai_vector.memories
    SET relevance = GREATEST(0.01, relevance * 0.995)
    WHERE is_archived = FALSE
      AND last_accessed < NOW() - INTERVAL '7 days'
      AND relevance > 0.01;

    -- Archiviere Erinnerungen mit minimaler Relevanz
    UPDATE dbai_vector.memories
    SET is_archived = TRUE
    WHERE relevance <= 0.01
      AND access_count = 0
      AND ts < NOW() - INTERVAL '30 days';
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Wissens-Graphen: Beziehungen zwischen Konzepten
-- =============================================================================
CREATE TABLE dbai_vector.knowledge_edges (
    id              BIGSERIAL PRIMARY KEY,
    source_id       UUID NOT NULL REFERENCES dbai_vector.memories(id),
    target_id       UUID NOT NULL REFERENCES dbai_vector.memories(id),
    relation_type   TEXT NOT NULL CHECK (relation_type IN (
                        'causes', 'requires', 'contradicts',
                        'supports', 'similar_to', 'part_of',
                        'followed_by', 'derived_from'
                    )),
    weight          REAL NOT NULL DEFAULT 1.0 CHECK (weight BETWEEN 0 AND 1),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(source_id, target_id, relation_type)
);

CREATE INDEX idx_knowledge_source ON dbai_vector.knowledge_edges(source_id);
CREATE INDEX idx_knowledge_target ON dbai_vector.knowledge_edges(target_id);
CREATE INDEX idx_knowledge_type ON dbai_vector.knowledge_edges(relation_type);
