#!/usr/bin/env python3
"""
DBAI Synaptic Memory Pipeline — Feature 14
=============================================
Hintergrund-Daemon der System-Events in Echtzeit vektorisiert
→ synaptic_memory Tabelle.

Architektur:
  Events → Classifier → Embedder → synaptic_memory
                                  → Konsolidierung → memories (Langzeit)
                                  → Decay (Vergessen)
"""

import json
import time
import logging
import threading
import hashlib
from datetime import datetime, timezone
from typing import Optional, Callable
from collections import deque

logger = logging.getLogger("dbai.synaptic")

# ─── Event-Importance Heuristiken ────────────────────────────────────────

IMPORTANCE_WEIGHTS = {
    "error":        0.9,
    "security":     0.95,
    "ghost_thought": 0.7,
    "user_action":  0.6,
    "config_change": 0.75,
    "install":      0.8,
    "login":        0.65,
    "hardware":     0.5,
    "network":      0.4,
    "system_event": 0.3,
    "performance":  0.3,
    "file_change":  0.25,
    "process":      0.2,
    "cron":         0.2,
    "notification": 0.15,
}


class SynapticPipeline:
    """
    Echtzeit-Event-Verarbeitung → Vektorisierung → Synaptic Memory.

    Events werden klassifiziert, mit einem Importance-Score versehen,
    vektorisiert und in die synaptic_memory Tabelle geschrieben.
    Periodisch werden wichtige Memories konsolidiert (→ Langzeitgedächtnis)
    und unwichtige vergessen (Decay).
    """

    def __init__(self, db_execute, db_query, embed_fn: Optional[Callable] = None):
        """
        Args:
            db_execute: DB execute Funktion
            db_query: DB query Funktion
            embed_fn: Embedding-Funktion (text → vector[1536]), oder None für Dummy
        """
        self.db_execute = db_execute
        self.db_query = db_query
        self.embed_fn = embed_fn
        self._event_buffer = deque(maxlen=1000)
        self._running = False
        self._thread = None
        self._process_interval = 2.0  # Sekunden
        self._consolidation_interval = 300  # 5 Minuten
        self._decay_interval = 3600  # 1 Stunde
        self._last_consolidation = 0
        self._last_decay = 0
        self._stats = {
            "events_received": 0,
            "events_processed": 0,
            "events_dropped": 0,
            "consolidations": 0,
            "decays": 0,
        }

    # ── Interface ────────────────────────────────────────────────────────

    def ingest(self, event_type: str, source: str, title: str,
               content: str, importance: float = None, metadata: dict = None):
        """Event in die Pipeline einspeisen."""
        if importance is None:
            importance = IMPORTANCE_WEIGHTS.get(event_type, 0.3)

        event = {
            "event_type": event_type,
            "source": source,
            "title": title,
            "content": content,
            "importance": max(0.0, min(1.0, importance)),
            "metadata": metadata or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._event_buffer.append(event)
        self._stats["events_received"] += 1

    def ingest_system_event(self, title: str, content: str, source: str = "system"):
        """Shortcut für System-Events."""
        self.ingest("system_event", source, title, content)

    def ingest_error(self, title: str, content: str, source: str = "error_handler"):
        """Shortcut für Fehler-Events."""
        self.ingest("error", source, title, content, importance=0.9)

    def ingest_user_action(self, title: str, content: str, user: str = "unknown"):
        """Shortcut für User-Aktionen."""
        self.ingest("user_action", f"user:{user}", title, content)

    def ingest_ghost_thought(self, title: str, content: str, role: str = "system"):
        """Shortcut für Ghost-Gedanken."""
        self.ingest("ghost_thought", f"ghost:{role}", title, content, importance=0.7)

    # ── Processing ───────────────────────────────────────────────────────

    def process_batch(self) -> int:
        """Alle gepufferten Events verarbeiten."""
        count = 0
        while self._event_buffer:
            event = self._event_buffer.popleft()
            try:
                self._process_event(event)
                count += 1
                self._stats["events_processed"] += 1
            except Exception as e:
                logger.error(f"Event-Verarbeitung fehlgeschlagen: {e}")
                self._stats["events_dropped"] += 1
        return count

    def _process_event(self, event: dict):
        """Einzelnes Event verarbeiten und in DB schreiben."""
        text = f"{event['title']}\n{event['content']}"

        # Embedding berechnen (falls Funktion vorhanden)
        embedding = None
        if self.embed_fn:
            try:
                embedding = self.embed_fn(text)
            except Exception as e:
                logger.debug(f"Embedding-Fehler: {e}")

        # Kontext-Fenster: letzte 5 Events als Kontext
        context_window = {
            "recent_events": [
                {"type": e["event_type"], "title": e["title"], "time": e["timestamp"]}
                for e in list(self._event_buffer)[:5]
            ]
        }

        # Emotionale Valenz heuristisch bestimmen
        emotional_valence = self._estimate_valence(event)

        # In DB schreiben
        if embedding is not None:
            self.db_execute(
                """INSERT INTO dbai_vector.synaptic_memory
                   (event_type, source, title, content, embedding,
                    importance, emotional_valence, context_window)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)""",
                (event["event_type"], event["source"], event["title"],
                 event["content"], embedding,
                 event["importance"], emotional_valence,
                 json.dumps(context_window))
            )
        else:
            self.db_execute(
                """INSERT INTO dbai_vector.synaptic_memory
                   (event_type, source, title, content,
                    importance, emotional_valence, context_window)
                   VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)""",
                (event["event_type"], event["source"], event["title"],
                 event["content"],
                 event["importance"], emotional_valence,
                 json.dumps(context_window))
            )

    def _estimate_valence(self, event: dict) -> float:
        """Emotionale Valenz heuristisch schätzen (-1.0 bis 1.0)."""
        text = (event["title"] + " " + event["content"]).lower()

        negative_words = ["error", "fail", "crash", "panic", "critical", "down",
                          "timeout", "denied", "unauthorized", "corrupt", "lost",
                          "fehler", "absturz", "kritisch", "fehlgeschlagen"]
        positive_words = ["success", "complete", "resolved", "healthy", "optimal",
                          "connected", "started", "installed", "active",
                          "erfolgreich", "abgeschlossen", "gesund", "aktiv"]

        neg_count = sum(1 for w in negative_words if w in text)
        pos_count = sum(1 for w in positive_words if w in text)

        if neg_count + pos_count == 0:
            return 0.0
        return max(-1.0, min(1.0, (pos_count - neg_count) / (neg_count + pos_count)))

    # ── Konsolidierung & Decay ───────────────────────────────────────────

    def consolidate(self) -> int:
        """Wichtige Synapsen in Langzeitgedächtnis überführen."""
        rows = self.db_query(
            "SELECT dbai_vector.consolidate_memories(0.7, '24 hours'::interval) AS count"
        )
        count = rows[0]["count"] if rows else 0
        self._stats["consolidations"] += count
        if count > 0:
            logger.info(f"Konsolidiert: {count} Memories → Langzeitgedächtnis")
        return count

    def decay(self) -> int:
        """Unwichtige Synapsen vergessen."""
        rows = self.db_query(
            "SELECT dbai_vector.decay_synaptic() AS deleted"
        )
        deleted = rows[0]["deleted"] if rows else 0
        self._stats["decays"] += deleted
        if deleted > 0:
            logger.info(f"Decay: {deleted} unwichtige Synapsen gelöscht")
        return deleted

    # ── Daemon ───────────────────────────────────────────────────────────

    def start(self):
        """Pipeline als Hintergrund-Thread starten."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._daemon_loop, daemon=True, name="synaptic-pipeline")
        self._thread.start()
        logger.info("Synaptic Memory Pipeline gestartet")

    def stop(self):
        """Pipeline stoppen."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Synaptic Memory Pipeline gestoppt")

    def _daemon_loop(self):
        """Haupt-Loop des Daemons."""
        while self._running:
            try:
                # Events verarbeiten
                if self._event_buffer:
                    self.process_batch()

                # Periodische Konsolidierung
                now = time.time()
                if now - self._last_consolidation > self._consolidation_interval:
                    self.consolidate()
                    self._last_consolidation = now

                # Periodischer Decay
                if now - self._last_decay > self._decay_interval:
                    self.decay()
                    self._last_decay = now

            except Exception as e:
                logger.error(f"Synaptic Pipeline Fehler: {e}")

            time.sleep(self._process_interval)

    # ── Query ────────────────────────────────────────────────────────────

    def search(self, query_embedding=None, event_type: str = None,
               limit: int = 20, min_importance: float = 0.0) -> list:
        """Synaptic Memories durchsuchen."""
        if query_embedding is not None:
            return self.db_query(
                """SELECT id, event_type, source, title, content,
                          importance, emotional_valence, created_at,
                          (1 - (embedding <=> %s))::FLOAT AS similarity
                   FROM dbai_vector.synaptic_memory
                   WHERE importance >= %s
                     AND (%s IS NULL OR event_type = %s)
                   ORDER BY embedding <=> %s
                   LIMIT %s""",
                (query_embedding, min_importance, event_type, event_type,
                 query_embedding, limit)
            )
        else:
            sql = """SELECT id, event_type, source, title, content,
                            importance, emotional_valence, created_at
                     FROM dbai_vector.synaptic_memory
                     WHERE importance >= %s"""
            params = [min_importance]
            if event_type:
                sql += " AND event_type = %s"
                params.append(event_type)
            sql += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)
            return self.db_query(sql, tuple(params))

    def get_stats(self) -> dict:
        """Pipeline-Statistiken."""
        db_stats = self.db_query(
            """SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE NOT consolidated) AS unconsolidated,
                COUNT(*) FILTER (WHERE consolidated) AS consolidated,
                AVG(importance)::FLOAT AS avg_importance,
                AVG(emotional_valence)::FLOAT AS avg_valence,
                MIN(created_at) AS oldest,
                MAX(created_at) AS newest
               FROM dbai_vector.synaptic_memory"""
        )
        return {
            "pipeline": self._stats,
            "buffer_size": len(self._event_buffer),
            "running": self._running,
            "database": db_stats[0] if db_stats else {},
        }
