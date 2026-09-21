#!/usr/bin/env python3
"""
DBAI Ghost Dispatcher — Hot-Swap KI-Manager
=============================================
Hört auf PostgreSQL NOTIFY-Events und verwaltet den Lebenszyklus
der KI-Modelle (Ghosts). Lädt/entlädt Modelle über llama-cpp-python.

Der Dispatcher ist der "Synaptic Bridge" — er verbindet die Tabellen
(welcher Ghost ist aktiv) mit der tatsächlichen KI im RAM.

Channels:
  ghost_swap  → Modell laden/entladen
  ghost_query → Anfrage an aktives Modell weiterleiten
"""

import os
import sys
import json
import time
import signal
import logging
import threading
from pathlib import Path
from datetime import datetime, timezone

import psycopg2
import psycopg2.extensions
from psycopg2.extras import RealDictCursor

# GPU-Manager (optional — läuft auch ohne GPU)
try:
    from bridge.gpu_manager import GPUManager
    HAS_GPU_MANAGER = True
except ImportError:
    HAS_GPU_MANAGER = False

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------
DBAI_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = DBAI_ROOT / "models"

DB_CONFIG = {
    "host": os.getenv("DBAI_DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DBAI_DB_PORT", "5432")),
    "dbname": os.getenv("DBAI_DB_NAME", "dbai"),
    "user": os.getenv("DBAI_DB_USER", "dbai_system"),
    "password": os.getenv("DBAI_DB_PASSWORD", ""),
}

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("dbai.ghost")


class GhostDispatcher:
    """
    Verwaltet geladene KI-Modelle und routet Anfragen.

    Architektur:
    ┌──────────┐   NOTIFY    ┌────────────────┐   llama-cpp    ┌─────────┐
    │ PostgreSQL├────────────►│ GhostDispatcher├──────────────►│ LLM RAM │
    │  Tabellen │◄────────────┤  (dieser Code)  │◄──────────────┤ (GGUF)  │
    └──────────┘   UPDATE    └────────────────┘   Response     └─────────┘
    """

    def __init__(self):
        self.conn = None
        self.work_conn = None
        self._running = False
        self._loaded_models = {}   # model_name → Llama instance
        self._model_configs = {}   # model_name → config dict
        self._lock = threading.Lock()
        self.gpu_manager = None    # GPUManager Instanz (wenn verfügbar)

    # ------------------------------------------------------------------
    # Datenbank
    # ------------------------------------------------------------------
    def connect(self):
        """Stellt die LISTEN-Verbindung her (autocommit für NOTIFY)."""
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.conn.set_isolation_level(
            psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT
        )
        # Separate Verbindung für Queries
        self.work_conn = psycopg2.connect(**DB_CONFIG)
        self.work_conn.autocommit = False
        logger.info("Datenbankverbindungen hergestellt")

        # GPU-Manager initialisieren (optional)
        self._init_gpu_manager()

    def _init_gpu_manager(self):
        """GPU-Manager starten, wenn GPU vorhanden."""
        if not HAS_GPU_MANAGER:
            logger.info("GPU-Manager nicht verfügbar — CPU-only Modus")
            return

        try:
            self.gpu_manager = GPUManager()
            has_gpu = self.gpu_manager.init_nvml()

            if has_gpu:
                self.gpu_manager.connect_db()
                self.gpu_manager.discover_and_register()
                logger.info("Neural Bridge aktiv: %d GPU(s) erkannt", self.gpu_manager.gpu_count)
            else:
                logger.info("Keine GPU erkannt — CPU-only Inferenz")
                self.gpu_manager = None
        except Exception as e:
            logger.warning("GPU-Manager Init fehlgeschlagen: %s — CPU-only", e)
            self.gpu_manager = None

    def db_query(self, sql, params=None):
        """Führt Query auf der Work-Connection aus."""
        try:
            with self.work_conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                try:
                    rows = cur.fetchall()
                    self.work_conn.commit()
                    return [dict(r) for r in rows]
                except psycopg2.ProgrammingError:
                    self.work_conn.commit()
                    return []
        except Exception as e:
            self.work_conn.rollback()
            logger.error("DB Query Fehler: %s", e)
            return []

    def db_execute(self, sql, params=None):
        """Führt ein Statement ohne Ergebnis aus."""
        try:
            with self.work_conn.cursor() as cur:
                cur.execute(sql, params)
            self.work_conn.commit()
        except Exception as e:
            self.work_conn.rollback()
            logger.error("DB Execute Fehler: %s", e)

    # ------------------------------------------------------------------
    # Modell-Verwaltung
    # ------------------------------------------------------------------
    def load_model(self, model_name: str, model_path: str, provider: str,
                   parameters: dict, context_size: int = 4096,
                   requires_gpu: bool = False,
                   required_vram_mb: int = 0,
                   n_gpu_layers: int = None) -> bool:
        """
        Lädt ein LLM-Modell in den RAM.
        Unterstützt: llama.cpp, vLLM (Remote), Ollama (Remote).

        GPU-Awareness (v0.4.0):
          - Prüft VRAM-Verfügbarkeit vor dem Laden
          - Unterstützt Multi-GPU Layer-Splitting
          - Reserviert VRAM in gpu_vram_map
          - Führt Quick-Benchmark nach dem Laden durch
        """
        with self._lock:
            if model_name in self._loaded_models:
                logger.info("Modell '%s' bereits geladen — überspringe", model_name)
                return True

            logger.info("═══ Lade Ghost: %s ═══", model_name)
            start_time = time.monotonic()

            # GPU-VRAM-Check (v0.4.0)
            gpu_layers_resolved = 0
            if requires_gpu and self.gpu_manager and provider == "llama.cpp":
                gpu_layers_resolved = self._resolve_gpu_layers(
                    model_name, required_vram_mb, n_gpu_layers
                )
            elif requires_gpu and not self.gpu_manager:
                logger.warning("GPU angefordert aber kein GPU-Manager — CPU-Fallback")
            elif n_gpu_layers is not None:
                gpu_layers_resolved = n_gpu_layers

            try:
                if provider == "llama.cpp":
                    success = self._load_llama_cpp(
                        model_name, model_path, parameters, context_size,
                        requires_gpu, gpu_layers_resolved
                    )
                elif provider == "vllm":
                    success = self._load_vllm_remote(model_name, parameters)
                elif provider == "ollama":
                    success = self._load_ollama_remote(model_name, parameters)
                else:
                    logger.error("Unbekannter Provider: %s", provider)
                    return False

                # VRAM-Allokation registrieren (v0.4.0)
                if success and requires_gpu and self.gpu_manager and gpu_layers_resolved != 0:
                    self._register_vram_allocation(model_name, required_vram_mb, gpu_layers_resolved)

                # Quick-Benchmark (v0.4.0)
                if success and provider == "llama.cpp":
                    self._run_quick_benchmark(model_name, start_time)

                return success
            except Exception as e:
                logger.error("Fehler beim Laden von '%s': %s", model_name, e)
                self._update_model_state(model_name, "error", str(e))
                return False
            finally:
                elapsed = round((time.monotonic() - start_time) * 1000)
                logger.info("Ladezeit für '%s': %d ms", model_name, elapsed)

    def _resolve_gpu_layers(self, model_name: str, required_vram_mb: int,
                            n_gpu_layers: int = None) -> int:
        """Berechnet optimale GPU-Layer-Anzahl basierend auf VRAM."""
        if not self.gpu_manager or not self.gpu_manager.conn:
            return 0

        if required_vram_mb <= 0:
            if n_gpu_layers is not None:
                return n_gpu_layers
            return -1  # Default: alle Layers auf GPU

        # VRAM-Verfügbarkeit prüfen
        check = self.gpu_manager.check_vram_for_model(required_vram_mb)

        if isinstance(check, dict) and check.get("fits"):
            options = check.get("options", [])
            if isinstance(options, list) and options:
                first = options[0] if isinstance(options, list) else options
                alloc_type = first.get("allocation_type", "full") if isinstance(first, dict) else "full"

                if alloc_type == "full":
                    logger.info("VRAM-Check: ✓ %dMB verfügbar — Full-GPU Modus", required_vram_mb)
                    return -1  # Alle Layers
                elif alloc_type == "split":
                    logger.info("VRAM-Check: ✓ Multi-GPU Split nötig")
                    return -1  # llama.cpp handhabt Split intern
            return -1
        else:
            reason = check.get("reason", "Unbekannt") if isinstance(check, dict) else "Unbekannt"
            logger.warning("VRAM-Check: ✗ Nicht genug VRAM (%s) — berechne Partial-Offload", reason)
            optimal = self.gpu_manager.get_optimal_gpu_layers(required_vram_mb)
            if optimal > 0:
                logger.info("Partial GPU-Offload: %d Layers auf GPU", optimal)
                return optimal
            logger.info("Kein GPU-Offload möglich — CPU-only")
            return 0

    def _register_vram_allocation(self, model_name: str, vram_mb: int, gpu_layers: int):
        """Registriert VRAM-Belegung in der Datenbank."""
        if not self.gpu_manager:
            return

        try:
            # Model-ID und Role-ID aus DB holen
            rows = self.db_query("""
                SELECT gm.id AS model_id, ag.role_id
                FROM dbai_llm.ghost_models gm
                LEFT JOIN dbai_llm.active_ghosts ag ON ag.model_id = gm.id AND ag.is_active = TRUE
                WHERE gm.name = %s
                LIMIT 1
            """, (model_name,))

            if rows:
                model_id = str(rows[0]["model_id"])
                role_id = str(rows[0].get("role_id")) if rows[0].get("role_id") else None

                # Erste verfügbare GPU nehmen
                if self.gpu_manager.gpu_db_ids:
                    gpu_index = next(iter(self.gpu_manager.gpu_db_ids))
                    self.gpu_manager.allocate_for_ghost(
                        gpu_index, model_id, role_id, vram_mb, gpu_layers
                    )
                    logger.info("VRAM-Allokation: %dMB auf GPU %d für '%s'",
                                vram_mb, gpu_index, model_name)
        except Exception as e:
            logger.warning("VRAM-Allokation fehlgeschlagen: %s", e)

    def _run_quick_benchmark(self, model_name: str, load_start_time: float):
        """Führt einen Quick-Benchmark nach dem Modell-Laden durch."""
        try:
            # Prüfe ob Auto-Benchmark aktiviert
            rows = self.db_query("""
                SELECT value FROM dbai_core.neural_bridge_config
                WHERE key = 'ghost.auto_benchmark'
            """)
            if not rows or rows[0].get("value") != True:
                return

            # Benchmark-Prompt laden
            rows = self.db_query("""
                SELECT value FROM dbai_core.neural_bridge_config
                WHERE key = 'ghost.benchmark_prompt'
            """)
            prompt = "Erkläre in einem Satz was DBAI ist."
            if rows and rows[0].get("value"):
                prompt = str(rows[0]["value"]).strip('"')

            bench_start = time.monotonic()
            result = self.generate(model_name, "Antworte kurz und präzise.", prompt)
            bench_elapsed = time.monotonic() - bench_start

            if "error" not in result:
                tokens = result.get("tokens_used", 0)
                tps = tokens / bench_elapsed if bench_elapsed > 0 else 0

                # Benchmark in DB speichern
                self.db_execute("""
                    INSERT INTO dbai_llm.ghost_benchmarks
                        (model_id, tokens_per_second, time_to_first_token_ms,
                         benchmark_duration_sec, notes)
                    VALUES (
                        (SELECT id FROM dbai_llm.ghost_models WHERE name = %s),
                        %s, %s, %s, %s
                    )
                """, (
                    model_name, round(tps, 1),
                    round((time.monotonic() - load_start_time) * 1000),
                    round(bench_elapsed, 2),
                    f"Auto-Benchmark: {tokens} tokens in {bench_elapsed:.1f}s"
                ))

                logger.info("Benchmark '%s': %.1f tok/s (%d tokens in %.1fs)",
                            model_name, tps, tokens, bench_elapsed)
        except Exception as e:
            logger.debug("Benchmark übersprungen: %s", e)

    def _load_llama_cpp(self, model_name: str, model_path: str,
                         parameters: dict, context_size: int,
                         requires_gpu: bool,
                         gpu_layers: int = 0) -> bool:
        """Lädt ein Modell via llama-cpp-python."""
        full_path = DBAI_ROOT / model_path
        if not full_path.exists():
            logger.error("Modell-Datei nicht gefunden: %s", full_path)
            self._update_model_state(model_name, "error", "Datei nicht gefunden")
            return False

        try:
            from llama_cpp import Llama

            # GPU-Layers: -1 = alle auf GPU, 0 = CPU-only, >0 = partial offload
            n_gpu_layers = gpu_layers if gpu_layers != 0 else (-1 if requires_gpu else 0)
            gpu_mode = "GPU-ALL" if n_gpu_layers == -1 else (
                f"GPU-{n_gpu_layers}L" if n_gpu_layers > 0 else "CPU-only"
            )

            logger.info("Lade '%s' mit %s (ctx=%d, threads=%d)",
                        model_name, gpu_mode, context_size, os.cpu_count() or 4)

            model = Llama(
                model_path=str(full_path),
                n_ctx=context_size,
                n_gpu_layers=n_gpu_layers,
                n_threads=os.cpu_count() or 4,
                verbose=False,
            )

            self._loaded_models[model_name] = model
            self._model_configs[model_name] = {
                "provider": "llama.cpp",
                "parameters": parameters,
                "context_size": context_size,
                "n_gpu_layers": n_gpu_layers,
                "gpu_mode": gpu_mode,
            }

            self._update_model_state(model_name, "loaded")
            logger.info("✓ Ghost '%s' geladen (llama.cpp, %s, ctx=%d)",
                        model_name, gpu_mode, context_size)
            return True

        except ImportError:
            logger.error("llama-cpp-python nicht installiert — pip install llama-cpp-python")
            self._update_model_state(model_name, "error", "llama-cpp-python fehlt")
            return False

    def _load_vllm_remote(self, model_name: str, parameters: dict) -> bool:
        """Verbindet mit einem vLLM-Server (Remote-Ghost)."""
        endpoint = parameters.get("endpoint", "http://localhost:8000/v1")
        self._loaded_models[model_name] = {"type": "vllm", "endpoint": endpoint}
        self._model_configs[model_name] = {"provider": "vllm", "parameters": parameters}
        self._update_model_state(model_name, "loaded")
        logger.info("✓ Ghost '%s' verbunden (vLLM: %s)", model_name, endpoint)
        return True

    def _load_ollama_remote(self, model_name: str, parameters: dict) -> bool:
        """Verbindet mit einem Ollama-Server (Remote-Ghost)."""
        endpoint = parameters.get("endpoint", "http://localhost:11434")
        self._loaded_models[model_name] = {"type": "ollama", "endpoint": endpoint}
        self._model_configs[model_name] = {"provider": "ollama", "parameters": parameters}
        self._update_model_state(model_name, "loaded")
        logger.info("✓ Ghost '%s' verbunden (Ollama: %s)", model_name, endpoint)
        return True

    def unload_model(self, model_name: str):
        """Entlädt ein Modell aus dem RAM und gibt VRAM frei."""
        with self._lock:
            if model_name in self._loaded_models:
                model = self._loaded_models.pop(model_name)
                self._model_configs.pop(model_name, None)

                # VRAM freigeben (v0.4.0)
                if self.gpu_manager:
                    self._release_vram_for_model(model_name)

                # llama.cpp Modell explizit freigeben
                if hasattr(model, "close"):
                    model.close()
                del model

                self._update_model_state(model_name, "available")
                logger.info("Ghost '%s' entladen (VRAM freigegeben)", model_name)

    def _release_vram_for_model(self, model_name: str):
        """Gibt VRAM eines Modells frei."""
        try:
            rows = self.db_query(
                "SELECT id FROM dbai_llm.ghost_models WHERE name = %s", (model_name,)
            )
            if rows:
                self.gpu_manager.release_ghost_vram(str(rows[0]["id"]))
        except Exception as e:
            logger.warning("VRAM-Freigabe für '%s' fehlgeschlagen: %s", model_name, e)

    def _update_model_state(self, model_name: str, state: str, error: str = None):
        """Aktualisiert den Modell-Status in der Datenbank."""
        if state == "loaded":
            self.db_execute("""
                UPDATE dbai_llm.ghost_models
                SET state = 'loaded', is_loaded = TRUE, loaded_at = NOW()
                WHERE name = %s
            """, (model_name,))
            # Auch den active_ghost aktualisieren
            self.db_execute("""
                UPDATE dbai_llm.active_ghosts
                SET state = 'active'
                WHERE model_id = (SELECT id FROM dbai_llm.ghost_models WHERE name = %s)
                  AND state = 'activating'
            """, (model_name,))
        elif state == "error":
            self.db_execute("""
                UPDATE dbai_llm.ghost_models
                SET state = 'error', is_loaded = FALSE
                WHERE name = %s
            """, (model_name,))
        else:
            self.db_execute("""
                UPDATE dbai_llm.ghost_models
                SET state = %s, is_loaded = FALSE, loaded_at = NULL
                WHERE name = %s
            """, (state, model_name))

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------
    def generate(self, model_name: str, system_prompt: str, user_prompt: str,
                 parameters: dict = None) -> dict:
        """Generiert eine Antwort mit dem angegebenen Modell."""
        if model_name not in self._loaded_models:
            return {"error": f"Modell '{model_name}' nicht geladen"}

        model = self._loaded_models[model_name]
        config = self._model_configs.get(model_name, {})
        provider = config.get("provider", "llama.cpp")
        params = parameters or config.get("parameters", {})

        start_time = time.monotonic()

        try:
            if provider == "llama.cpp":
                return self._generate_llama_cpp(model, system_prompt, user_prompt, params)
            elif provider == "vllm":
                return self._generate_vllm(model, system_prompt, user_prompt, params)
            elif provider == "ollama":
                return self._generate_ollama(model, system_prompt, user_prompt, params)
            else:
                return {"error": f"Unbekannter Provider: {provider}"}
        except Exception as e:
            logger.error("Inference-Fehler bei '%s': %s", model_name, e)
            return {"error": str(e)}
        finally:
            elapsed = round((time.monotonic() - start_time) * 1000)
            # Statistik aktualisieren
            self.db_execute("""
                UPDATE dbai_llm.ghost_models
                SET avg_latency_ms = CASE
                        WHEN total_requests = 0 THEN %s
                        ELSE (avg_latency_ms * total_requests + %s) / (total_requests + 1)
                    END,
                    total_requests = total_requests + 1,
                    last_used_at = NOW()
                WHERE name = %s
            """, (elapsed, elapsed, model_name))

    def _generate_llama_cpp(self, model, system_prompt: str, user_prompt: str,
                             params: dict) -> dict:
        """Generiert via llama-cpp-python."""
        response = model.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=params.get("temperature", 0.7),
            top_p=params.get("top_p", 0.9),
            max_tokens=params.get("max_tokens", 2048),
            repeat_penalty=params.get("repeat_penalty", 1.1),
        )
        choice = response["choices"][0]
        return {
            "content": choice["message"]["content"],
            "tokens_used": response.get("usage", {}).get("total_tokens", 0),
            "finish_reason": choice.get("finish_reason", "stop"),
        }

    def _generate_vllm(self, model_config: dict, system_prompt: str,
                        user_prompt: str, params: dict) -> dict:
        """Generiert via vLLM OpenAI-kompatible API."""
        import urllib.request
        endpoint = model_config["endpoint"] + "/chat/completions"
        data = json.dumps({
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": params.get("temperature", 0.7),
            "max_tokens": params.get("max_tokens", 2048),
        }).encode()
        req = urllib.request.Request(
            endpoint, data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
        choice = result["choices"][0]
        return {
            "content": choice["message"]["content"],
            "tokens_used": result.get("usage", {}).get("total_tokens", 0),
            "finish_reason": choice.get("finish_reason", "stop"),
        }

    def _generate_ollama(self, model_config: dict, system_prompt: str,
                          user_prompt: str, params: dict) -> dict:
        """Generiert via Ollama HTTP API."""
        import urllib.request
        endpoint = model_config["endpoint"] + "/api/chat"
        data = json.dumps({
            "model": params.get("ollama_model", "llama3"),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
        }).encode()
        req = urllib.request.Request(
            endpoint, data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
        return {
            "content": result.get("message", {}).get("content", ""),
            "tokens_used": result.get("eval_count", 0),
            "finish_reason": "stop",
        }

    # ------------------------------------------------------------------
    # NOTIFY Handler
    # ------------------------------------------------------------------
    def handle_ghost_swap(self, payload: dict):
        """Verarbeitet einen Ghost-Swap NOTIFY."""
        model_name = payload.get("new_model")
        old_model = payload.get("old_model")
        model_path = payload.get("model_path")
        provider = payload.get("provider", "llama.cpp")
        parameters = payload.get("parameters", {})
        context_size = payload.get("context_size", 4096)
        requires_gpu = payload.get("requires_gpu", False)

        logger.info("═══ Ghost-Swap: %s → %s ═══", old_model or "None", model_name)

        # Altes Modell entladen (wenn nicht von einer anderen Rolle verwendet)
        if old_model and old_model in self._loaded_models:
            # Prüfen ob das Modell noch von einer anderen Rolle genutzt wird
            rows = self.db_query("""
                SELECT COUNT(*) AS cnt FROM dbai_llm.active_ghosts ag
                JOIN dbai_llm.ghost_models gm ON ag.model_id = gm.id
                WHERE gm.name = %s AND ag.state = 'active'
            """, (old_model,))
            if not rows or rows[0]["cnt"] == 0:
                self.unload_model(old_model)

        # Neues Modell laden
        if model_name and model_path:
            success = self.load_model(
                model_name, model_path, provider,
                parameters, context_size, requires_gpu
            )
            if success:
                logger.info("✓ Ghost-Swap abgeschlossen: %s aktiv", model_name)
            else:
                logger.error("✗ Ghost-Swap fehlgeschlagen: %s", model_name)

    def handle_ghost_query(self, payload: dict):
        """Verarbeitet eine Ghost-Query (aus der Task-Queue)."""
        task_id = payload.get("task_id")
        role = payload.get("role")
        model_name = payload.get("model")

        if not task_id:
            return

        logger.info("Ghost-Query: task=%s, role=%s, model=%s", task_id, role, model_name)

        # Task-Daten laden
        rows = self.db_query(
            "SELECT * FROM dbai_llm.task_queue WHERE id = %s::UUID", (task_id,)
        )
        if not rows:
            logger.error("Task %s nicht gefunden", task_id)
            return

        task = rows[0]
        input_data = task.get("input_data", {})
        if isinstance(input_data, str):
            input_data = json.loads(input_data)

        system_prompt = input_data.get("system_prompt", "Du bist ein hilfreicher Assistent.")
        question = input_data.get("question", "")

        # Task als "processing" markieren
        self.db_execute(
            "UPDATE dbai_llm.task_queue SET state = 'processing' WHERE id = %s::UUID",
            (task_id,)
        )

        # Generieren
        result = self.generate(model_name, system_prompt, question)

        # Task als abgeschlossen markieren
        if "error" in result:
            self.db_execute("""
                UPDATE dbai_llm.task_queue
                SET state = 'failed', output_data = %s::JSONB
                WHERE id = %s::UUID
            """, (json.dumps(result), task_id))
        else:
            self.db_execute("""
                UPDATE dbai_llm.task_queue
                SET state = 'completed', output_data = %s::JSONB,
                    tokens_used = %s
                WHERE id = %s::UUID
            """, (json.dumps(result), result.get("tokens_used", 0), task_id))

            # Token-Statistik auf Ghost aktualisieren
            self.db_execute("""
                UPDATE dbai_llm.ghost_models
                SET total_tokens = total_tokens + %s
                WHERE name = %s
            """, (result.get("tokens_used", 0), model_name))

        logger.info("Ghost-Query abgeschlossen: task=%s, tokens=%s",
                     task_id, result.get("tokens_used", 0))

    # ------------------------------------------------------------------
    # Haupt-Loop
    # ------------------------------------------------------------------
    def start(self):
        """Startet den Ghost Dispatcher."""
        self.connect()
        self._running = True

        # Signal-Handler
        signal.signal(signal.SIGINT, lambda s, f: self.stop())
        signal.signal(signal.SIGTERM, lambda s, f: self.stop())

        # LISTEN auf Channels
        with self.conn.cursor() as cur:
            cur.execute("LISTEN ghost_swap;")
            cur.execute("LISTEN ghost_query;")
            cur.execute("LISTEN ghost_gpu_migration;")
            cur.execute("LISTEN gpu_overheat;")
            cur.execute("LISTEN power_profile_change;")

        gpu_status = f"{self.gpu_manager.gpu_count} GPU(s)" if self.gpu_manager else "CPU-only"
        logger.info("═══════════════════════════════════════")
        logger.info("  DBAI Ghost Dispatcher v0.4.0")
        logger.info("  Neural Bridge: %s", gpu_status)
        logger.info("  LISTEN: ghost_swap, ghost_query,")
        logger.info("          ghost_gpu_migration, gpu_overheat,")
        logger.info("          power_profile_change")
        logger.info("═══════════════════════════════════════")

        # Boot: Bereits aktive Ghosts laden
        self._load_active_ghosts()

        # Haupt-Loop
        while self._running:
            try:
                if self.conn.closed:
                    self.connect()
                    with self.conn.cursor() as cur:
                        cur.execute("LISTEN ghost_swap;")
                        cur.execute("LISTEN ghost_query;")

                self.conn.poll()

                while self.conn.notifies:
                    notify = self.conn.notifies.pop(0)
                    self._dispatch_notify(notify)

                time.sleep(0.1)

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error("Dispatcher-Fehler: %s", e)
                time.sleep(2)

        self.stop()

    def stop(self):
        """Stoppt den Dispatcher und entlädt alle Modelle."""
        self._running = False
        logger.info("Ghost Dispatcher wird gestoppt...")

        # Alle Modelle entladen (inkl. VRAM-Freigabe)
        for model_name in list(self._loaded_models.keys()):
            self.unload_model(model_name)

        # GPU-Manager herunterfahren
        if self.gpu_manager:
            self.gpu_manager.shutdown()

        # DB-Verbindungen schließen
        for conn in [self.conn, self.work_conn]:
            if conn and not conn.closed:
                conn.close()

        logger.info("Ghost Dispatcher gestoppt")

    def _dispatch_notify(self, notify):
        """Verteilt NOTIFY-Nachrichten an die Handler."""
        try:
            payload = json.loads(notify.payload) if notify.payload else {}
        except json.JSONDecodeError:
            payload = {}

        if notify.channel == "ghost_swap":
            # In Thread ausführen damit der Haupt-Loop nicht blockiert
            threading.Thread(
                target=self.handle_ghost_swap,
                args=(payload,),
                daemon=True,
            ).start()

        elif notify.channel == "ghost_query":
            threading.Thread(
                target=self.handle_ghost_query,
                args=(payload,),
                daemon=True,
            ).start()

        elif notify.channel == "ghost_gpu_migration":
            logger.warning("GPU-Migration angefordert: %s", payload)
            # Ghost auf CPU migrieren wenn GPU ausfällt
            model_name = payload.get("model_name")
            if model_name and model_name in self._loaded_models:
                logger.info("Migriere Ghost '%s' auf CPU...", model_name)
                self.unload_model(model_name)
                config = self._model_configs.get(model_name, {})
                model_path = payload.get("model_path", "")
                self.load_model(
                    model_name, model_path, config.get("provider", "llama.cpp"),
                    config.get("parameters", {}), config.get("context_size", 4096),
                    requires_gpu=False, n_gpu_layers=0
                )

        elif notify.channel == "gpu_overheat":
            logger.warning("GPU-Überhitzung erkannt: %s", payload)

        elif notify.channel == "power_profile_change":
            profile = payload.get("profile", "unknown")
            logger.info("Power-Profil gewechselt: %s", profile)
            if payload.get("prefer_cpu"):
                logger.info("Sparmodus: GPU-Inferenz deaktiviert")

    def _load_active_ghosts(self):
        """Lädt beim Start alle bereits aktiven Ghosts."""
        rows = self.db_query("""
            SELECT gm.name, gm.model_path, gm.provider, gm.parameters,
                   gm.context_size, gm.requires_gpu, gm.required_vram_mb,
                   gm.n_gpu_layers
            FROM dbai_llm.active_ghosts ag
            JOIN dbai_llm.ghost_models gm ON ag.model_id = gm.id
            WHERE ag.state IN ('active', 'activating')
        """)

        for row in rows:
            model_path = row.get("model_path")
            if model_path and (DBAI_ROOT / model_path).exists():
                self.load_model(
                    row["name"], model_path, row["provider"],
                    row.get("parameters", {}),
                    row.get("context_size", 4096),
                    row.get("requires_gpu", False),
                    row.get("required_vram_mb", 0),
                    row.get("n_gpu_layers"),
                )
            else:
                logger.warning(
                    "Ghost '%s': Modell-Datei nicht gefunden (%s) — überspringe",
                    row["name"], model_path
                )
                # Status trotzdem auf "active" setzen (Modell fehlt aber Datenbank-Eintrag existiert)
                self._update_model_state(row["name"], "error", "Modell-Datei nicht gefunden")


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
def main():
    dispatcher = GhostDispatcher()
    dispatcher.start()


if __name__ == "__main__":
    main()
