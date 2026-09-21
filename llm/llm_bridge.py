#!/usr/bin/env python3
"""
DBAI LLM Bridge — llama.cpp Integration
=========================================
Das Gehirn, das direkt in der Datenbank sitzt.
Daten verlassen den sicheren Bereich der DB NIEMALS.

Architektur:
1. llama.cpp wird als Python-Modul eingebunden (llama-cpp-python)
2. Modell wird in RAM geladen und bleibt dort
3. SQL-Funktionen aus dem LLM-Schema rufen diese Bridge auf
4. Die Bridge liest Aufgaben aus der Task-Queue und schreibt Ergebnisse zurück

Keine externe API-Abhängigkeit — alles lokal.
"""

import os
import sys
import json
import time
import logging
import threading
from pathlib import Path
from typing import Optional, List

import psycopg2
from psycopg2.extras import RealDictCursor, Json

logger = logging.getLogger("dbai.llm")

# ---------------------------------------------------------------------------
# Versuch llama-cpp-python zu importieren
# ---------------------------------------------------------------------------
try:
    from llama_cpp import Llama
    HAS_LLAMA = True
except ImportError:
    HAS_LLAMA = False
    logger.warning(
        "llama-cpp-python nicht installiert. "
        "Install: pip install llama-cpp-python"
    )


class LLMBridge:
    """
    Verbindet llama.cpp mit der PostgreSQL-Datenbank.
    Das LLM hat nur Zugriff auf die Zeilen, die es für seine Aufgabe braucht.
    """

    def __init__(self, conn, shutdown_event: threading.Event):
        self.conn = conn
        self.shutdown_event = shutdown_event
        self.model: Optional[Llama] = None
        self.model_name: str = ""
        self.model_config: dict = {}

    def _get_cursor(self):
        if self.conn.closed:
            from bridge.system_bridge import DB_CONFIG
            self.conn = psycopg2.connect(**DB_CONFIG)
        return self.conn.cursor(cursor_factory=RealDictCursor)

    # ------------------------------------------------------------------
    # Modell laden
    # ------------------------------------------------------------------
    def load_model(self, model_path: str = None, **kwargs) -> bool:
        """
        Lädt ein GGUF-Modell in den Arbeitsspeicher.
        Das Modell bleibt geladen bis zum Shutdown.
        """
        if not HAS_LLAMA:
            logger.error("llama-cpp-python nicht verfügbar")
            return False

        if model_path is None:
            model_path = os.getenv(
                "DBAI_LLM_MODEL",
                "/opt/dbai/models/current.gguf"
            )

        if not Path(model_path).exists():
            logger.error("Modell nicht gefunden: %s", model_path)
            return False

        try:
            config = {
                "n_ctx": int(kwargs.get("context_size", os.getenv("DBAI_LLM_CTX", "4096"))),
                "n_threads": int(kwargs.get("n_threads", os.getenv("DBAI_LLM_THREADS", "4"))),
                "n_gpu_layers": int(kwargs.get("n_gpu_layers", os.getenv("DBAI_LLM_GPU_LAYERS", "0"))),
                "verbose": False,
            }

            logger.info("Lade LLM-Modell: %s (ctx=%d, threads=%d)", 
                        model_path, config["n_ctx"], config["n_threads"])

            self.model = Llama(
                model_path=model_path,
                **config,
            )
            self.model_name = Path(model_path).stem
            self.model_config = config

            # Modell in DB registrieren
            self._register_model(model_path, config)

            logger.info("LLM-Modell erfolgreich geladen: %s", self.model_name)
            return True

        except Exception as e:
            logger.error("Modell laden fehlgeschlagen: %s", e)
            return False

    def _register_model(self, model_path: str, config: dict):
        """Registriert das geladene Modell in der Datenbank."""
        try:
            with self._get_cursor() as cur:
                # Objekt-ID für das Modell erstellen (kein Dateipfad in der DB!)
                cur.execute(
                    """
                    INSERT INTO dbai_core.objects
                        (object_type, name, storage_hash, metadata)
                    VALUES ('model', %s, %s, %s::jsonb)
                    ON CONFLICT (id) DO NOTHING
                    RETURNING id
                    """,
                    (
                        self.model_name,
                        self._hash_file(model_path),
                        json.dumps({"original_path": model_path, **config}),
                    ),
                )
                row = cur.fetchone()
                object_id = row["id"] if row else None

                # Modell-Registry aktualisieren
                cur.execute(
                    """
                    INSERT INTO dbai_llm.models
                        (name, model_type, parameters, context_size,
                         is_loaded, loaded_at, model_object_id)
                    VALUES (%s, 'chat', %s::jsonb, %s, TRUE, NOW(), %s)
                    ON CONFLICT (name) DO UPDATE SET
                        is_loaded = TRUE,
                        loaded_at = NOW(),
                        parameters = EXCLUDED.parameters
                    """,
                    (
                        self.model_name,
                        json.dumps(config),
                        config.get("n_ctx", 4096),
                        object_id,
                    ),
                )
                self.conn.commit()
        except Exception as e:
            logger.error("Modell-Registrierung fehlgeschlagen: %s", e)
            self.conn.rollback()

    # ------------------------------------------------------------------
    # Text generieren
    # ------------------------------------------------------------------
    def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        stop: List[str] = None,
    ) -> dict:
        """
        Generiert Text mit dem geladenen Modell.
        Alles lokal — keine externe API.
        """
        if self.model is None:
            return {"error": "Kein Modell geladen", "text": ""}

        try:
            start_time = time.time()
            result = self.model(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=stop or ["</s>", "\n\nUser:", "\n\nHuman:"],
                echo=False,
            )
            duration_ms = (time.time() - start_time) * 1000

            text = result["choices"][0]["text"].strip()
            tokens_used = result["usage"]["total_tokens"]

            # Statistiken aktualisieren
            self._update_stats(tokens_used, duration_ms)

            return {
                "text": text,
                "tokens_used": tokens_used,
                "duration_ms": round(duration_ms, 1),
                "model": self.model_name,
            }
        except Exception as e:
            logger.error("Text-Generierung fehlgeschlagen: %s", e)
            return {"error": str(e), "text": ""}

    # ------------------------------------------------------------------
    # Embedding generieren
    # ------------------------------------------------------------------
    def embed(self, text: str) -> Optional[list]:
        """
        Generiert ein Vektor-Embedding für den gegebenen Text.
        Wird für die Ähnlichkeitssuche in dbai_vector.memories verwendet.
        """
        if self.model is None:
            return None

        try:
            embedding = self.model.embed(text)
            if isinstance(embedding, list) and len(embedding) > 0:
                # Auf 1536 Dimensionen normalisieren (pgvector Kompatibilität)
                if isinstance(embedding[0], list):
                    embedding = embedding[0]

                # Padding/Truncating auf 1536 Dimensionen
                target_dim = 1536
                if len(embedding) < target_dim:
                    embedding.extend([0.0] * (target_dim - len(embedding)))
                elif len(embedding) > target_dim:
                    embedding = embedding[:target_dim]

                return embedding
            return None
        except Exception as e:
            logger.error("Embedding-Generierung fehlgeschlagen: %s", e)
            return None

    # ------------------------------------------------------------------
    # Task-Queue verarbeiten
    # ------------------------------------------------------------------
    def _process_task_queue(self):
        """Verarbeitet ausstehende Tasks aus der LLM-Task-Queue."""
        try:
            with self._get_cursor() as cur:
                # Nächsten Task holen (höchste Priorität zuerst)
                cur.execute(
                    """
                    UPDATE dbai_llm.task_queue
                    SET state = 'processing', started_at = NOW()
                    WHERE id = (
                        SELECT id FROM dbai_llm.task_queue
                        WHERE state = 'pending'
                        ORDER BY priority ASC, created_at ASC
                        LIMIT 1
                        FOR UPDATE SKIP LOCKED
                    )
                    RETURNING *
                    """
                )
                task = cur.fetchone()
                self.conn.commit()

                if task is None:
                    return  # Keine ausstehenden Tasks

                logger.info(
                    "Verarbeite Task %s (Typ: %s, Prio: %d)",
                    task["id"], task["task_type"], task["priority"],
                )

                # Task verarbeiten
                result = self._execute_task(task)

                # Ergebnis speichern
                state = "completed" if "error" not in result else "failed"
                cur.execute(
                    """
                    UPDATE dbai_llm.task_queue
                    SET state = %s,
                        output_data = %s::jsonb,
                        completed_at = NOW(),
                        tokens_used = %s,
                        error_message = %s
                    WHERE id = %s
                    """,
                    (
                        state,
                        json.dumps(result, default=str),
                        result.get("tokens_used"),
                        result.get("error"),
                        str(task["id"]),
                    ),
                )
                self.conn.commit()

        except Exception as e:
            logger.error("Task-Verarbeitung fehlgeschlagen: %s", e)
            try:
                self.conn.rollback()
            except Exception:
                pass

    def _execute_task(self, task: dict) -> dict:
        """Führt einen einzelnen Task aus."""
        input_data = task["input_data"]
        task_type = task["task_type"]

        if task_type == "query":
            return self.generate(
                prompt=input_data.get("prompt", ""),
                max_tokens=input_data.get("max_tokens", 512),
                temperature=input_data.get("temperature", 0.7),
            )
        elif task_type == "embedding":
            embedding = self.embed(input_data.get("text", ""))
            return {
                "embedding": embedding,
                "dimensions": len(embedding) if embedding else 0,
            }
        elif task_type == "analysis":
            return self.generate(
                prompt=f"Analysiere folgende Daten:\n{json.dumps(input_data)}",
                max_tokens=1024,
                temperature=0.3,
            )
        else:
            return {"error": f"Unbekannter Task-Typ: {task_type}"}

    # ------------------------------------------------------------------
    # Statistiken
    # ------------------------------------------------------------------
    def _update_stats(self, tokens: int, duration_ms: float):
        """Aktualisiert Modell-Statistiken in der Datenbank."""
        try:
            with self._get_cursor() as cur:
                cur.execute(
                    """
                    UPDATE dbai_llm.models
                    SET total_tokens = total_tokens + %s,
                        total_requests = total_requests + 1,
                        avg_latency_ms = CASE
                            WHEN avg_latency_ms IS NULL THEN %s
                            ELSE (avg_latency_ms * 0.9 + %s * 0.1)
                        END
                    WHERE name = %s AND is_loaded = TRUE
                    """,
                    (tokens, duration_ms, duration_ms, self.model_name),
                )
                self.conn.commit()
        except Exception as e:
            logger.debug("Statistik-Update fehlgeschlagen: %s", e)
            try:
                self.conn.rollback()
            except Exception:
                pass

    @staticmethod
    def _hash_file(path: str) -> str:
        """Berechnet den MD5-Hash einer Datei."""
        import hashlib
        h = hashlib.md5()
        try:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            return h.hexdigest()
        except Exception:
            return "unknown"

    # ------------------------------------------------------------------
    # Hauptschleife
    # ------------------------------------------------------------------
    def run(self):
        """
        Hauptschleife: Verarbeitet die Task-Queue kontinuierlich.
        Das Modell bleibt im RAM geladen (keep_in_memory).
        """
        logger.info("LLM-Bridge gestartet")

        # Modell laden
        if HAS_LLAMA:
            model_path = os.getenv("DBAI_LLM_MODEL")
            if model_path and Path(model_path).exists():
                self.load_model(model_path)
            else:
                logger.info(
                    "Kein LLM-Modell konfiguriert. "
                    "Setze DBAI_LLM_MODEL=/pfad/zum/modell.gguf"
                )

        # Task-Queue verarbeiten
        while not self.shutdown_event.is_set():
            if self.model is not None:
                self._process_task_queue()
            self.shutdown_event.wait(0.5)  # 500ms Polling

        # Aufräumen
        if self.model is not None:
            try:
                with self._get_cursor() as cur:
                    cur.execute(
                        """
                        UPDATE dbai_llm.models
                        SET is_loaded = FALSE
                        WHERE name = %s
                        """,
                        (self.model_name,),
                    )
                    self.conn.commit()
            except Exception:
                pass

        logger.info("LLM-Bridge gestoppt")
