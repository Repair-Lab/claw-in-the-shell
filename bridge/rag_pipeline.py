#!/usr/bin/env python3
"""
DBAI RAG Pipeline — Feature 15
================================
Automatische Retrieval-Augmented-Generation:
Relevante Chunks aus Vector-DB in Ghost-Prompt injizieren.

Architektur:
  Query → Embedding → Vector-Suche → Chunk-Ranking → Prompt-Assembly
"""

import json
import time
import logging
import hashlib
from typing import Optional, Callable, List

logger = logging.getLogger("dbai.rag")


class RAGPipeline:
    """
    Retrieval-Augmented-Generation Pipeline.

    Sucht relevante Kontext-Chunks aus verschiedenen Quellen
    und injiziert sie in den Ghost-Prompt.
    """

    def __init__(self, db_execute, db_query, embed_fn: Optional[Callable] = None):
        self.db_execute = db_execute
        self.db_query = db_query
        self.embed_fn = embed_fn
        self._stats = {
            "queries": 0,
            "chunks_retrieved": 0,
            "avg_latency_ms": 0,
            "cache_hits": 0,
        }
        self._cache = {}  # Einfacher Query-Cache
        self._cache_ttl = 300  # 5 Minuten

    # ── Quellen-Management ───────────────────────────────────────────────

    def init_sources(self):
        """Standard-RAG-Quellen initialisieren."""
        default_sources = [
            ("knowledge_base", "knowledge_base", True, 90, 5, 0.3),
            ("system_memory", "system_memory", True, 80, 5, 0.3),
            ("synaptic_recent", "synaptic_memory", True, 70, 3, 0.4),
            ("workspace_context", "workspace", True, 60, 3, 0.3),
            ("browser_knowledge", "browser", True, 40, 2, 0.4),
            ("config_context", "config", True, 30, 2, 0.3),
            ("event_history", "events", True, 20, 2, 0.5),
        ]
        for name, stype, enabled, priority, max_chunks, min_rel in default_sources:
            self.db_execute(
                """INSERT INTO dbai_llm.rag_sources
                   (source_name, source_type, enabled, priority, max_chunks, min_relevance)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (source_name) DO NOTHING""",
                (name, stype, enabled, priority, max_chunks, min_rel)
            )
        logger.info("RAG-Quellen initialisiert")

    def get_sources(self) -> list:
        """Alle RAG-Quellen abrufen."""
        return self.db_query(
            """SELECT id, source_name, source_type, enabled, priority,
                      max_chunks, min_relevance, created_at
               FROM dbai_llm.rag_sources
               ORDER BY priority DESC"""
        )

    def toggle_source(self, source_name: str, enabled: bool):
        """RAG-Quelle aktivieren/deaktivieren."""
        self.db_execute(
            "UPDATE dbai_llm.rag_sources SET enabled = %s WHERE source_name = %s",
            (enabled, source_name)
        )

    # ── Chunk-Indexierung ────────────────────────────────────────────────

    def index_chunk(self, source_name: str, content: str,
                    metadata: dict = None, source_ref: str = None) -> Optional[str]:
        """Einen Chunk in die RAG-DB indexieren."""
        # Source-ID holen
        sources = self.db_query(
            "SELECT id FROM dbai_llm.rag_sources WHERE source_name = %s",
            (source_name,)
        )
        if not sources:
            logger.warning(f"RAG-Quelle nicht gefunden: {source_name}")
            return None

        source_id = sources[0]["id"]

        # Embedding berechnen
        embedding = None
        if self.embed_fn:
            try:
                embedding = self.embed_fn(content)
            except Exception as e:
                logger.error(f"Embedding-Fehler: {e}")

        # Token-Schätzung (4 Zeichen ≈ 1 Token)
        token_count = len(content) // 4

        if embedding is not None:
            rows = self.db_query(
                """INSERT INTO dbai_llm.rag_chunks
                   (source_id, content, embedding, token_count, metadata, source_ref)
                   VALUES (%s, %s, %s, %s, %s::jsonb, %s)
                   RETURNING id""",
                (source_id, content, embedding, token_count,
                 json.dumps(metadata or {}), source_ref)
            )
        else:
            rows = self.db_query(
                """INSERT INTO dbai_llm.rag_chunks
                   (source_id, content, token_count, metadata, source_ref)
                   VALUES (%s, %s, %s, %s::jsonb, %s)
                   RETURNING id""",
                (source_id, content, token_count,
                 json.dumps(metadata or {}), source_ref)
            )

        return str(rows[0]["id"]) if rows else None

    def reindex_source(self, source_name: str) -> int:
        """Eine Quelle komplett neu indexieren."""
        sources = self.db_query(
            "SELECT id, source_type FROM dbai_llm.rag_sources WHERE source_name = %s",
            (source_name,)
        )
        if not sources:
            return 0

        source = sources[0]
        source_type = source["source_type"]

        # Alte Chunks löschen
        self.db_execute(
            "DELETE FROM dbai_llm.rag_chunks WHERE source_id = %s",
            (source["id"],)
        )

        count = 0

        if source_type == "knowledge_base":
            count = self._index_knowledge_base(source_name)
        elif source_type == "system_memory":
            count = self._index_system_memory(source_name)
        elif source_type == "synaptic_memory":
            count = self._index_synaptic_memory(source_name)
        elif source_type == "browser":
            count = self._index_browser_knowledge(source_name)

        logger.info(f"Reindexiert: {source_name} → {count} Chunks")
        return count

    def _index_knowledge_base(self, source_name: str) -> int:
        """Ghost Knowledge Base indexieren."""
        rows = self.db_query(
            """SELECT id, title, content, url, category, tags
               FROM dbai_core.ghost_knowledge_base
               ORDER BY created_at DESC LIMIT 1000"""
        )
        count = 0
        for row in rows:
            text = f"{row['title']}\n{row.get('content', '')}\n{row.get('url', '')}"
            self.index_chunk(source_name, text,
                             metadata={"category": row.get("category"), "tags": row.get("tags", [])},
                             source_ref=f"ghost_knowledge_base:{row['id']}")
            count += 1
        return count

    def _index_system_memory(self, source_name: str) -> int:
        """System Memory indexieren."""
        rows = self.db_query(
            """SELECT id, category, title, content, tags
               FROM dbai_knowledge.system_memory
               WHERE valid_until IS NULL OR valid_until >= '999.0'
               ORDER BY priority DESC LIMIT 500"""
        )
        count = 0
        for row in rows:
            text = f"[{row['category']}] {row['title']}\n{row['content']}"
            self.index_chunk(source_name, text,
                             metadata={"category": row["category"], "tags": row.get("tags", [])},
                             source_ref=f"system_memory:{row['id']}")
            count += 1
        return count

    def _index_synaptic_memory(self, source_name: str) -> int:
        """Wichtige Synaptic Memories indexieren."""
        rows = self.db_query(
            """SELECT id, event_type, source, title, content
               FROM dbai_vector.synaptic_memory
               WHERE importance >= 0.6
               ORDER BY created_at DESC LIMIT 200"""
        )
        count = 0
        for row in rows:
            text = f"[{row['event_type']}] {row['title']}\n{row['content']}"
            self.index_chunk(source_name, text,
                             metadata={"event_type": row["event_type"], "source": row["source"]},
                             source_ref=f"synaptic_memory:{row['id']}")
            count += 1
        return count

    def _index_browser_knowledge(self, source_name: str) -> int:
        """Browser-Knowledge indexieren."""
        rows = self.db_query(
            """SELECT id, title, url, category, tags
               FROM dbai_core.ghost_knowledge_base
               WHERE source_type IN ('bookmark', 'browser_pattern')
               ORDER BY created_at DESC LIMIT 500"""
        )
        count = 0
        for row in rows:
            text = f"{row['title']} — {row.get('url', '')}"
            self.index_chunk(source_name, text,
                             metadata={"category": row.get("category"), "url": row.get("url")},
                             source_ref=f"browser_knowledge:{row['id']}")
            count += 1
        return count

    # ── Query / Retrieval ────────────────────────────────────────────────

    def query(self, question: str, role_name: str = None,
              max_chunks: int = 10, max_tokens: int = 2000,
              source_types: list = None) -> dict:
        """
        RAG-Query: Relevante Chunks für eine Frage finden und Kontext zusammenbauen.

        Returns:
            {
                "context": str,     # Zusammengebauter Kontext-Text
                "chunks": list,     # Gefundene Chunks mit Scores
                "stats": dict,      # Statistiken
            }
        """
        start_time = time.time()

        # Cache prüfen
        cache_key = hashlib.md5(f"{question}:{role_name}:{max_chunks}".encode()).hexdigest()
        cached = self._cache.get(cache_key)
        if cached and (time.time() - cached["time"]) < self._cache_ttl:
            self._stats["cache_hits"] += 1
            return cached["result"]

        # Embedding berechnen
        if not self.embed_fn:
            return self._fallback_query(question, max_chunks)

        try:
            query_embedding = self.embed_fn(question)
        except Exception as e:
            logger.error(f"Query-Embedding-Fehler: {e}")
            return self._fallback_query(question, max_chunks)

        # Vector-Suche via DB-Funktion
        chunks = self.db_query(
            """SELECT chunk_id, content, score, source_name, source_type, metadata
               FROM dbai_llm.rag_search(%s, %s, 0.3, %s)""",
            (query_embedding, max_chunks, source_types)
        )

        # Kontext zusammenbauen (Token-Budget beachten)
        context_parts = []
        total_tokens = 0
        chunk_ids = []
        chunk_scores = []

        for chunk in chunks:
            token_estimate = len(chunk["content"]) // 4
            if total_tokens + token_estimate > max_tokens:
                break
            context_parts.append(
                f"--- [{chunk['source_type']}: {chunk['source_name']} | "
                f"Score: {chunk['score']:.3f}] ---\n{chunk['content']}"
            )
            total_tokens += token_estimate
            chunk_ids.append(chunk["chunk_id"])
            chunk_scores.append(chunk["score"])

        context = "\n\n".join(context_parts)

        # Query-Log
        latency_ms = int((time.time() - start_time) * 1000)
        self.db_execute(
            """INSERT INTO dbai_llm.rag_query_log
               (query_text, query_embedding, retrieved_chunks, chunk_scores,
                total_tokens, role_name, latency_ms)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (question, query_embedding, chunk_ids, chunk_scores,
             total_tokens, role_name, latency_ms)
        )

        self._stats["queries"] += 1
        self._stats["chunks_retrieved"] += len(chunks)
        self._stats["avg_latency_ms"] = (
            (self._stats["avg_latency_ms"] * (self._stats["queries"] - 1) + latency_ms)
            / self._stats["queries"]
        )

        result = {
            "context": context,
            "chunks": [
                {"id": str(c["chunk_id"]), "content": c["content"][:200],
                 "score": c["score"], "source": c["source_name"]}
                for c in chunks
            ],
            "stats": {
                "chunks_found": len(chunks),
                "total_tokens": total_tokens,
                "latency_ms": latency_ms,
            },
        }

        # Cache
        self._cache[cache_key] = {"result": result, "time": time.time()}

        return result

    def _fallback_query(self, question: str, max_chunks: int) -> dict:
        """Fallback wenn kein Embedding verfügbar: Textsuche."""
        words = question.lower().split()[:5]
        if not words:
            return {
                "context": "",
                "chunks": [],
                "stats": {"chunks_found": 0, "total_tokens": 0,
                          "latency_ms": 0, "mode": "fallback_text_search"},
            }
        conditions = " OR ".join(["content ILIKE %s"] * len(words))
        params = [f"%{w}%" for w in words] + [max_chunks]

        chunks = self.db_query(
            f"""SELECT c.id AS chunk_id, c.content, s.source_name, s.source_type,
                       0.5::FLOAT AS score, c.metadata
                FROM dbai_llm.rag_chunks c
                JOIN dbai_llm.rag_sources s ON c.source_id = s.id
                WHERE s.enabled = TRUE AND ({conditions})
                LIMIT %s""",
            tuple(params)
        )

        context = "\n\n".join([
            f"--- [{c['source_type']}: {c['source_name']}] ---\n{c['content']}"
            for c in chunks
        ])

        return {
            "context": context,
            "chunks": [{"id": str(c["chunk_id"]), "content": c["content"][:200],
                        "score": 0.5, "source": c["source_name"]} for c in chunks],
            "stats": {"chunks_found": len(chunks), "total_tokens": len(context) // 4,
                      "latency_ms": 0, "mode": "fallback_text_search"},
        }

    # ── Ghost-Prompt mit RAG ────────────────────────────────────────────

    def augment_prompt(self, system_prompt: str, user_message: str,
                       role_name: str = None, max_context_tokens: int = 2000) -> str:
        """
        System-Prompt mit RAG-Kontext anreichern.

        Returns:
            Angereicherter System-Prompt mit injiziertem Kontext.
        """
        rag_result = self.query(user_message, role_name, max_tokens=max_context_tokens)
        context = rag_result.get("context", "")

        if not context:
            return system_prompt

        augmented = (
            f"{system_prompt}\n\n"
            f"═══ KONTEXT AUS DEM SYSTEM-GEDÄCHTNIS ═══\n"
            f"Die folgenden Informationen wurden aus der DBAI-Wissensbasis abgerufen.\n"
            f"Nutze sie nur, wenn sie für die Anfrage relevant sind.\n\n"
            f"{context}\n"
            f"═══ ENDE KONTEXT ═══"
        )

        return augmented

    # ── Stats ────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Pipeline-Statistiken."""
        source_stats = self.db_query(
            """SELECT s.source_name, s.source_type, s.enabled,
                      COUNT(c.id) AS chunk_count,
                      SUM(c.token_count) AS total_tokens
               FROM dbai_llm.rag_sources s
               LEFT JOIN dbai_llm.rag_chunks c ON s.id = c.source_id
               GROUP BY s.id ORDER BY s.priority DESC"""
        )
        query_stats = self.db_query(
            """SELECT COUNT(*) AS total_queries,
                      AVG(latency_ms)::INTEGER AS avg_latency,
                      AVG(array_length(retrieved_chunks, 1))::FLOAT AS avg_chunks
               FROM dbai_llm.rag_query_log"""
        )
        return {
            "pipeline": self._stats,
            "sources": source_stats,
            "query_stats": query_stats[0] if query_stats else {},
        }
