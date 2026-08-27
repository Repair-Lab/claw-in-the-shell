"""
web/common.py — Gemeinsames Fundament (Phase 2)
=================================================
Alle Infrastruktur-Komponenten, die von den Routen gebraucht werden:
  DB-Pools, Krypto, Auth, LLM-Server, GPU, Watchdog,
  Migration-Runner, HW-Simulator, Pydantic-Modelle,
  FastAPI-App, Middlewares, Lifespan

server.py re-exportiert alle Symbole für Test-Kompatibilität.
routers.py importiert app + Helper von hier.
"""

"""
DBAI Web Server — FastAPI + WebSocket
======================================
Die Brücke zwischen PostgreSQL-Kernel und Browser-UI.

Features:
- REST API für Login, Desktop, Apps, Fenster
- WebSocket für Live-Updates (Events, Metriken, Ghost-Swaps)
- LISTEN/NOTIFY Bridge: PostgreSQL → WebSocket → Browser
- Boot-Sequenz mit Live-Stream an den Client
- Static File Serving für das React-Frontend

Kein externer API-Zugang. Nur localhost.
"""

import os

import json

import asyncio

import logging

import signal

import time

import threading

from pathlib import Path

from datetime import datetime, timezone

from typing import Optional

from contextlib import asynccontextmanager

_cuda_lib_paths = os.getenv("DBAI_CUDA_LIB_PATH", "").split(":") if os.getenv("DBAI_CUDA_LIB_PATH") else [
    "/mnt/nvme/home/asus/Desktop/helios/Helios/venv/lib/python3.12/site-packages/nvidia/cublas/lib",
    "/mnt/nvme/home/asus/Desktop/helios/Helios/venv/lib/python3.12/site-packages/nvidia/cuda_runtime/lib",
]

_existing = os.environ.get("LD_LIBRARY_PATH", "")

os.environ["LD_LIBRARY_PATH"] = ":".join(_cuda_lib_paths + ([_existing] if _existing else []))

import ctypes

for _p in _cuda_lib_paths:
    for _lib in sorted(Path(_p).glob("*.so*")):
        try:
            ctypes.cdll.LoadLibrary(str(_lib))
        except Exception as e:
            logger.debug("silent-exception: %s", e)

import psycopg2

import psycopg2.extensions

from psycopg2.extras import RealDictCursor

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Request, Body

from fastapi.staticfiles import StaticFiles

from fastapi.responses import HTMLResponse, JSONResponse

from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel

DBAI_ROOT = Path(__file__).resolve().parent.parent

FRONTEND_DIR = DBAI_ROOT / "frontend" / "dist"

ASSETS_DIR = DBAI_ROOT / "frontend" / "public" / "assets"

DB_CONFIG = {
    "host": os.getenv("DBAI_DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DBAI_DB_PORT", "5432")),
    "dbname": os.getenv("DBAI_DB_NAME", "dbai"),
    "user": os.getenv("DBAI_DB_USER", "dbai_system"),
    "password": os.getenv("DBAI_DB_PASSWORD", "dbai2026"),
    "connect_timeout": 5,
}

DB_CONFIG_RUNTIME = {
    "host": os.getenv("DBAI_DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DBAI_DB_PORT", "5432")),
    "dbname": os.getenv("DBAI_DB_NAME", "dbai"),
    "user": os.getenv("DBAI_DB_RUNTIME_USER", "dbai_runtime"),
    "password": os.getenv("DBAI_DB_RUNTIME_PASSWORD", "dbai_runtime_2026"),
    "connect_timeout": 5,
}

WEB_HOST = os.getenv("DBAI_WEB_HOST", "127.0.0.1")

WEB_PORT = int(os.getenv("DBAI_WEB_PORT", "3000"))

class _JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)

_use_json_logs = os.getenv("DBAI_LOG_FORMAT", "text") == "json"

if _use_json_logs:
    _handler = logging.StreamHandler()
    _handler.setFormatter(_JSONFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[_handler])
else:
    LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

logger = logging.getLogger("dbai.web")

import re as _re_mod

def _validate_body(body: dict, required: list[str] = None, max_str_len: int = 10000) -> dict:
    """
    Validiert einen Request-Body:
    - Prüft required Keys
    - Sanitized Strings (trimmen, max Länge)
    - Verhindert None-Injection auf required Fields
    Wirft ValueError bei Verstoß.
    """
    if not isinstance(body, dict):
        raise ValueError("Request-Body muss ein JSON-Objekt sein")
    if required:
        missing = [k for k in required if k not in body or body[k] is None]
        if missing:
            raise ValueError(f"Fehlende Pflichtfelder: {', '.join(missing)}")
    # Strings sanitieren
    sanitized = {}
    for k, v in body.items():
        if isinstance(v, str):
            v = v.strip()
            if len(v) > max_str_len:
                v = v[:max_str_len]
        sanitized[k] = v
    return sanitized

_FERNET_KEY_PATH = DBAI_ROOT / "config" / ".fernet.key"

def _load_or_create_fernet_key() -> bytes:
    """Fernet-Key laden oder erstellen. Datei wird mit 0600 geschützt."""
    # 1. Aus Datei laden
    if _FERNET_KEY_PATH.exists():
        return _FERNET_KEY_PATH.read_bytes().strip()
    # 2. Aus Env-Variable (Docker/Container-Umgebung)
    env_key = os.getenv("DBAI_FERNET_KEY")
    if env_key:
        return env_key.encode()
    # 3. Neuen Key erstellen und persistent speichern
    from cryptography.fernet import Fernet
    key = Fernet.generate_key()
    try:
        _FERNET_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
        _FERNET_KEY_PATH.write_bytes(key)
        os.chmod(str(_FERNET_KEY_PATH), 0o600)
        logger.info("Neuer Fernet-Schlüssel erstellt: %s", _FERNET_KEY_PATH)
    except (PermissionError, OSError) as e:
        logger.warning("Fernet-Key konnte nicht gespeichert werden (nur In-Memory): %s", e)
    return key

try:
    from cryptography.fernet import Fernet
    _fernet = Fernet(_load_or_create_fernet_key())
    logger.info("Fernet-Verschlüsselung aktiv")
except ImportError:
    _fernet = None
    logger.warning("cryptography nicht installiert — Fallback auf Base64 (UNSICHER)")
except Exception as _fernet_err:
    _fernet = None
    logger.warning("Fernet-Init fehlgeschlagen: %s — Fallback auf Base64", _fernet_err)

def encrypt_secret(plaintext: str) -> str:
    """Verschlüsselt einen String mit Fernet. Fallback: Base64."""
    if _fernet:
        return _fernet.encrypt(plaintext.encode()).decode()
    import base64
    return base64.b64encode(plaintext.encode()).decode()

def decrypt_secret(ciphertext: str) -> str:
    """Entschlüsselt einen Fernet-Token. Fallback: Base64 (Legacy-Keys)."""
    if _fernet:
        try:
            return _fernet.decrypt(ciphertext.encode()).decode()
        except Exception:
            # Legacy-Key aus der Base64-Ära (vor Fernet) — sicher dekodieren
            import base64
            try:
                return base64.b64decode(ciphertext.encode()).decode()
            except Exception:
                # Noch älteres/ungültiges Format → als Klartext zurückgeben,
                # damit Endpunkte nicht mit binären Bytes crashen (Bug A)
                return ciphertext
    import base64
    return base64.b64decode(ciphertext.encode()).decode()

class DBPool:
    """Connection-Pool für PostgreSQL — Thread-safe mit Checkout/Checkin."""

    def __init__(self, config: dict, max_connections: int = 10):
        self.config = config
        self.max_connections = max_connections
        self._idle: list = []         # Verfügbare Connections
        self._in_use: set = set()     # Aktuell ausgeliehene Connections
        self._lock = threading.Lock()
        self._notify_conn = None

    def get_connection(self):
        """Holt eine exklusive DB-Verbindung (Checkout). Muss mit return_connection zurückgegeben werden."""
        with self._lock:
            # Kaputte idle-Connections entfernen
            alive = []
            for conn in self._idle:
                if conn.closed:
                    continue
                try:
                    if conn.status == psycopg2.extensions.STATUS_READY:
                        alive.append(conn)
                    elif conn.status == psycopg2.extensions.STATUS_IN_TRANSACTION:
                        try:
                            conn.rollback()
                            alive.append(conn)
                        except Exception:
                            try: conn.close()
                            except Exception as e: logger.debug("silent-exception: %s", e)
                    else:
                        try: conn.close()
                        except Exception as e: logger.debug("silent-exception: %s", e)
                except Exception:
                    try: conn.close()
                    except Exception as e: logger.debug("silent-exception: %s", e)
            self._idle = alive

            # Erste verfügbare idle Connection auschecken (mit Health-Ping)
            while self._idle:
                conn = self._idle.pop(0)
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT 1")
                    cur.close()
                    self._in_use.add(id(conn))
                    return conn
                except Exception:
                    # Stale Connection — verwerfen und nächste probieren
                    try: conn.close()
                    except Exception as e: logger.debug("silent-exception: %s", e)
                    continue

            # Neue Connection erstellen falls Limit nicht erreicht
            total = len(self._idle) + len(self._in_use)
            if total < self.max_connections:
                conn = psycopg2.connect(**self.config)
                conn.autocommit = False
                self._in_use.add(id(conn))
                return conn

        # Limit erreicht — blockierend warten (mit Timeout)
        for _ in range(50):  # max 5s warten (50 × 0.1s)
            time.sleep(0.1)
            with self._lock:
                if self._idle:
                    conn = self._idle.pop(0)
                    try:
                        cur = conn.cursor()
                        cur.execute("SELECT 1")
                        cur.close()
                        self._in_use.add(id(conn))
                        return conn
                    except Exception:
                        try: conn.close()
                        except Exception as e: logger.debug("silent-exception: %s", e)
                        # Slot frei → neue Connection probieren
                        total = len(self._idle) + len(self._in_use)
                        if total < self.max_connections:
                            try:
                                conn = psycopg2.connect(**self.config)
                                conn.autocommit = False
                                self._in_use.add(id(conn))
                                return conn
                            except Exception as e:
                                logger.debug("silent-exception: %s", e)
        raise Exception("DBPool: Keine freie Connection verfügbar (Timeout)")

    def return_connection(self, conn):
        """Gibt eine ausgeliehene Connection zurück (Checkin)."""
        with self._lock:
            self._in_use.discard(id(conn))
            if conn.closed:
                return
            try:
                if conn.status == psycopg2.extensions.STATUS_IN_TRANSACTION:
                    conn.rollback()
                self._idle.append(conn)
            except Exception:
                # Rollback fehlgeschlagen → Connection komplett verwerfen (kein Leak)
                try: conn.close()
                except Exception as e: logger.debug("silent-exception: %s", e)

    def get_notify_connection(self):
        """Dedizierte Verbindung für LISTEN/NOTIFY (autocommit!)."""
        if self._notify_conn is None or self._notify_conn.closed:
            self._notify_conn = psycopg2.connect(**self.config)
            self._notify_conn.set_isolation_level(
                psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT
            )
        return self._notify_conn

    def close_all(self):
        with self._lock:
            for conn in self._idle:
                try:
                    conn.close()
                except Exception as e:
                    logger.debug("silent-exception: %s", e)
            self._idle.clear()
            self._in_use.clear()
        if self._notify_conn:
            try:
                self._notify_conn.close()
            except Exception as e:
                logger.debug("silent-exception: %s", e)

db_pool = DBPool(DB_CONFIG)

db_pool_runtime = DBPool(DB_CONFIG_RUNTIME)

def db_query(sql: str, params=None, commit=False) -> list:
    """Führt eine SQL-Abfrage aus (ADMIN-Pool — nur für Admin-Ops nutzen)."""
    conn = db_pool.get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            if commit:
                conn.commit()
                return []
            try:
                rows = cur.fetchall()
                conn.commit()
                return [dict(r) for r in rows]
            except psycopg2.ProgrammingError:
                conn.commit()
                return []
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        db_pool.return_connection(conn)

def db_execute(sql: str, params=None) -> None:
    """Führt ein SQL-Statement ohne Ergebnis aus (ADMIN-Pool)."""
    conn = db_pool.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        db_pool.return_connection(conn)

def db_query_rt(sql: str, params=None, commit=False) -> list:
    """Runtime-Pool: Für alle normalen API-Operationen (KEIN Superuser, RLS aktiv)."""
    conn = db_pool_runtime.get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            if commit:
                conn.commit()
                return []
            try:
                rows = cur.fetchall()
                conn.commit()
                return [dict(r) for r in rows]
            except psycopg2.ProgrammingError:
                conn.commit()
                return []
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        db_pool_runtime.return_connection(conn)

def db_execute_rt(sql: str, params=None) -> None:
    """Runtime-Pool: Statement ohne Ergebnis (KEIN Superuser, RLS aktiv)."""
    conn = db_pool_runtime.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        db_pool_runtime.return_connection(conn)

def db_call_json_rt(sql: str, params=None):
    """Runtime-Pool: Ruft Funktion auf die JSONB zurückgibt."""
    rows = db_query_rt(sql, params)
    if rows and len(rows) > 0:
        first_key = list(rows[0].keys())[0]
        result = rows[0][first_key]
        if isinstance(result, str):
            return json.loads(result)
        return result
    return None

def db_call_json(sql: str, params=None):
    """Ruft eine SQL-Funktion auf die JSONB zurückgibt."""
    rows = db_query(sql, params)
    if rows and len(rows) > 0:
        # Erstes Feld der ersten Zeile
        first_key = list(rows[0].keys())[0]
        result = rows[0][first_key]
        if isinstance(result, str):
            return json.loads(result)
        return result
    return None

async def adb_query_rt(sql: str, params=None, commit=False) -> list:
    """Async-Wrapper: db_query_rt in separatem Thread ausführen."""
    return await asyncio.to_thread(db_query_rt, sql, params, commit)

async def adb_execute_rt(sql: str, params=None) -> None:
    """Async-Wrapper: db_execute_rt in separatem Thread ausführen."""
    return await asyncio.to_thread(db_execute_rt, sql, params)

async def adb_call_json_rt(sql: str, params=None):
    """Async-Wrapper: db_call_json_rt in separatem Thread ausführen."""
    return await asyncio.to_thread(db_call_json_rt, sql, params)

async def adb_query(sql: str, params=None, commit=False) -> list:
    """Async-Wrapper: db_query in separatem Thread ausführen."""
    return await asyncio.to_thread(db_query, sql, params, commit)

async def adb_execute(sql: str, params=None) -> None:
    """Async-Wrapper: db_execute in separatem Thread ausführen."""
    return await asyncio.to_thread(db_execute, sql, params)

async def adb_call_json(sql: str, params=None):
    """Async-Wrapper: db_call_json in separatem Thread ausführen."""
    return await asyncio.to_thread(db_call_json, sql, params)

class ConnectionManager:
    """Verwaltet alle aktiven WebSocket-Verbindungen — Multi-Tab-fähig."""

    def __init__(self):
        # tab_id → WebSocket  (jeder Tab hat seine eigene Verbindung)
        self.active_connections: dict[str, WebSocket] = {}
        # session_id → set[tab_id]  (Mapping für Session-Broadcasts)
        self.session_tabs: dict[str, set] = {}

    async def connect(self, websocket: WebSocket, session_id: str, tab_id: str = None):
        key = tab_id or session_id
        await websocket.accept()
        self.active_connections[key] = websocket
        if session_id not in self.session_tabs:
            self.session_tabs[session_id] = set()
        self.session_tabs[session_id].add(key)
        logger.info("WebSocket verbunden: tab=%s session=%s (aktiv: %d)", key[:8], session_id[:8], len(self.active_connections))

    def disconnect(self, session_id: str, tab_id: str = None):
        key = tab_id or session_id
        self.active_connections.pop(key, None)
        tabs = self.session_tabs.get(session_id, set())
        tabs.discard(key)
        if not tabs:
            self.session_tabs.pop(session_id, None)
        logger.info("WebSocket getrennt: tab=%s (aktiv: %d)", key[:8], len(self.active_connections))

    async def send_to_tab(self, tab_id: str, data: dict):
        """Nachricht an einen bestimmten Tab."""
        ws = self.active_connections.get(tab_id)
        if ws:
            try:
                await ws.send_json(data)
            except Exception:
                self.active_connections.pop(tab_id, None)

    async def send_to_session(self, session_id: str, data: dict):
        """Nachricht an ALLE Tabs einer Session."""
        dead = []
        for tab_id in list(self.session_tabs.get(session_id, set())):
            ws = self.active_connections.get(tab_id)
            if ws:
                try:
                    await ws.send_json(data)
                except Exception:
                    dead.append(tab_id)
            else:
                dead.append(tab_id)
        for tid in dead:
            self.disconnect(session_id, tid)

    async def broadcast(self, data: dict):
        dead = []
        async def _send(key, ws):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(key)
        await asyncio.gather(*[_send(k, w) for k, w in list(self.active_connections.items())])
        for key in dead:
            self.active_connections.pop(key, None)

    @property
    def count(self) -> int:
        return len(self.active_connections)

ws_manager = ConnectionManager()

class NotifyBridge:
    """
    Hört auf PostgreSQL NOTIFY-Channels und leitet sie per WebSocket weiter.
    Läuft als asyncio-Task im Hintergrund.
    """

    CHANNELS = [
        "ghost_swap",       # Ghost-Wechsel
        "ghost_query",      # Ghost-Anfrage dispatcht
        "user_login",       # User hat sich eingeloggt
        "system_event",     # Allgemeine System-Events
        "alert_fired",      # Alert-Regel hat gefeuert
        "health_update",    # Health-Check Update
        "action_proposed",  # LLM schlägt Reparatur vor
        "action_approved",  # Reparatur genehmigt
        "repair_execute",   # Reparatur wird ausgeführt
    ]

    def __init__(self, pool: DBPool, manager: ConnectionManager):
        self.pool = pool
        self.manager = manager
        self._running = False
        self._task = None

    async def start(self):
        """Startet den NOTIFY-Listener als Background-Task."""
        self._running = True
        self._task = asyncio.create_task(self._listen_loop())
        logger.info("NOTIFY Bridge gestartet — Channels: %s", ", ".join(self.CHANNELS))

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _listen_loop(self):
        """Polling-Loop für pg_notify (psycopg2 ist synchron)."""
        conn = self.pool.get_notify_connection()

        # LISTEN auf alle Channels
        with conn.cursor() as cur:
            for channel in self.CHANNELS:
                cur.execute(f"LISTEN {channel};")

        logger.info("LISTEN aktiv auf %d Channels", len(self.CHANNELS))

        while self._running:
            try:
                # select() mit Timeout für non-blocking
                if conn.closed:
                    conn = self.pool.get_notify_connection()
                    with conn.cursor() as cur:
                        for channel in self.CHANNELS:
                            cur.execute(f"LISTEN {channel};")

                # poll() prüft auf neue Notifications
                conn.poll()

                while conn.notifies:
                    notify = conn.notifies.pop(0)
                    await self._handle_notify(notify)

            except Exception as e:
                logger.error("NOTIFY Bridge Fehler: %s", e)
                await asyncio.sleep(2)

            # Kurzes Sleep um CPU nicht zu verbrennen
            await asyncio.sleep(0.1)

    async def _handle_notify(self, notify):
        """Verarbeitet eine einzelne NOTIFY-Nachricht."""
        try:
            payload = json.loads(notify.payload) if notify.payload else {}
        except json.JSONDecodeError:
            payload = {"raw": notify.payload}

        message = {
            "type": "notify",
            "channel": notify.channel,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        logger.info("NOTIFY [%s]: %s", notify.channel, json.dumps(payload)[:200])

        # An alle verbundenen Clients senden
        await self.manager.broadcast(message)

notify_bridge = NotifyBridge(db_pool, ws_manager)

class MetricsStreamer:
    """Sendet periodisch System-Metriken per WebSocket."""

    def __init__(self, manager: ConnectionManager, interval: float = 2.0):
        self.manager = manager
        self.interval = interval
        self._running = False
        self._task = None

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._stream_loop())
        logger.info("Metrics Streamer gestartet (Intervall: %.1fs)", self.interval)

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()

    async def _stream_loop(self):
        while self._running:
            if self.manager.count > 0:
                try:
                    metrics = await asyncio.get_event_loop().run_in_executor(
                        None, self._fetch_metrics
                    )
                    if metrics:
                        await self.manager.broadcast({
                            "type": "metrics",
                            "data": metrics,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
                except Exception as e:
                    logger.error("Metrics Fehler: %s", e)

            await asyncio.sleep(self.interval)

    def _fetch_metrics(self) -> dict:
        """Holt aktuelle System-Metriken aus der DB."""
        try:
            rows = db_query("""
                SELECT * FROM dbai_system.current_status
            """)
            return rows[0] if rows else {}
        except Exception:
            return {}

metrics_streamer = MetricsStreamer(ws_manager)

async def lifespan(app: FastAPI):
    """Start/Stop Lifecycle mit Auto-Recovery."""
    logger.info("═══ DBAI Web Server startet ═══")

    # ── STARTUP-DIAGNOSTIK: Konfigurationsprobleme sofort erkennen ──
    _env = os.getenv("DBAI_ENV", "production")
    logger.info("[CONFIG] DBAI_ENV=%s  Cookie-Secure=%s  Sandbox=%s",
                _env, _COOKIE_SECURE, os.getenv("DBAI_SANDBOX", "false"))
    if _COOKIE_SECURE:
        logger.warning(
            "[CONFIG] ⚠ Cookies setzen Secure-Flag → funktionieren NUR über HTTPS! "
            "Falls kein TLS-Proxy vorhanden: DBAI_ENV=development setzen."
        )
    if _IS_DEVELOPMENT:
        logger.info("[CONFIG] Development-Modus aktiv — Cookies ohne Secure-Flag (HTTP OK)")
    # Prüfe ob DB erreichbar ist
    try:
        db_query_rt("SELECT 1")
        logger.info("[CONFIG] ✓ Datenbank erreichbar")
    except Exception as e:
        logger.error("[CONFIG] ✗ Datenbank NICHT erreichbar: %s", e)

    await notify_bridge.start()
    await metrics_streamer.start()

    # ── AUTO-RECOVERY: Instanzen die als 'running' gespeichert waren wiederherstellen ──
    try:
        running_instances = db_query_rt("""
            SELECT ai.id, ai.model_id, ai.gpu_index, ai.n_gpu_layers, ai.context_size,
                   ai.threads, ai.batch_size, ai.backend,
                   gm.name AS model_name, gm.model_path, gm.required_vram_mb, gm.quantization
            FROM dbai_llm.agent_instances ai
            JOIN dbai_llm.ghost_models gm ON ai.model_id = gm.id
            WHERE ai.state = 'running'
            ORDER BY ai.created_at ASC
            LIMIT 1
        """)
        if running_instances:
            inst = running_instances[0]
            model_path = inst.get("model_path", "")
            if model_path and not model_path.startswith("/"):
                for base in ["/mnt/nvme/models", "/home/worker/DBAI"]:
                    candidate = os.path.join(base, model_path)
                    if os.path.exists(candidate):
                        model_path = candidate
                        break
            if model_path and os.path.exists(model_path):
                logger.info(f"[RECOVERY] Stelle Instanz wieder her: {inst['model_name']} auf GPU {inst['gpu_index']}")
                started = _llm_server_start(
                    device="gpu" if (inst.get("n_gpu_layers") or 99) > 0 else "cpu",
                    n_gpu_layers=inst.get("n_gpu_layers") or 99,
                    ctx_size=inst.get("context_size") or 8192,
                    threads=inst.get("threads") or 8,
                    model_path=model_path,
                    model_name=inst.get("model_name", "unknown"),
                )
                if started:
                    logger.info(f"[RECOVERY] ✅ {inst['model_name']} erfolgreich wiederhergestellt")
                    db_execute_rt("""
                        UPDATE dbai_llm.agent_instances SET state = 'running', updated_at = NOW()
                        WHERE id = %s::UUID
                    """, (str(inst["id"]),))
                    db_execute_rt("""
                        UPDATE dbai_llm.ghost_models SET state = 'loaded', is_loaded = TRUE, updated_at = NOW()
                        WHERE id = %s::UUID
                    """, (str(inst["model_id"]),))
                else:
                    logger.error(f"[RECOVERY] ❌ {inst['model_name']} konnte nicht wiederhergestellt werden")
                    db_execute_rt("""
                        UPDATE dbai_llm.agent_instances SET state = 'error', updated_at = NOW()
                        WHERE id = %s::UUID
                    """, (str(inst["id"]),))
            else:
                logger.warning(f"[RECOVERY] Modell-Pfad nicht gefunden: {model_path}")
        else:
            logger.info("[RECOVERY] Keine laufenden Instanzen zu recovern")
    except Exception as e:
        logger.error(f"[RECOVERY] Fehler bei Auto-Recovery: {e}")

    # ── LLM Watchdog starten wenn konfiguriert ──
    try:
        wd_cfg = db_query_rt("SELECT value FROM dbai_core.config WHERE key = 'llm_watchdog_enabled'")
        if wd_cfg:
            v = wd_cfg[0]["value"]
            enabled = v if isinstance(v, bool) else (str(v).lower().strip('"') == "true") if isinstance(v, str) else bool(v)
            if enabled:
                asyncio.create_task(_llm_watchdog_loop())
                logger.info("[WATCHDOG] LLM Watchdog automatisch gestartet")
    except Exception as e:
        logger.debug(f"[WATCHDOG] Start-Check Fehler: {e}")

    yield
    logger.info("═══ DBAI Web Server stoppt ═══")
    global _watchdog_running
    _watchdog_running = False
    # LLM-Server sauber beenden (VRAM freigeben, Prozess killen)
    try:
        await asyncio.to_thread(_llm_server_stop)
    except Exception as e:
        logger.warning("LLM-Server Stop fehlgeschlagen: %s", e)
    await notify_bridge.stop()
    await metrics_streamer.stop()
    db_pool.close_all()
    db_pool_runtime.close_all()

# Single Source of Truth: web/VERSION (Phase 3)
_API_VERSION = Path(__file__).with_name("VERSION").read_text(encoding="utf-8").strip()

app = FastAPI(
    title="DBAI — Database AI Operating System",
    version=_API_VERSION,
    description="The Ghost in the Database",
    lifespan=lifespan,
)

_cors_origins = [
    "http://localhost:3000", "http://127.0.0.1:3000",
    "http://localhost:5173", "http://127.0.0.1:5173",
    # Sandbox
    "http://localhost:3100", "http://127.0.0.1:3100",
    "http://localhost:5174", "http://127.0.0.1:5174",
]

import os as _cors_os

_host_ip = _cors_os.environ.get("HOST_IP", "")

if _host_ip:
    for port in [3000, 3100, 5173, 5174]:
        _cors_origins.append(f"http://{_host_ip}:{port}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from collections import defaultdict

_rate_limit_store: dict[str, list[float]] = {}

_rate_limit_last_cleanup = 0.0

_RATE_LIMIT = 120  # max Requests

_RATE_WINDOW = 60  # pro Sekunde

_RATE_MAX_ENTRIES = 200  # Hard-Cap → aggressive Bereinigung bei Überschreitung

_download_tasks: dict[str, dict] = {}



_IS_DEVELOPMENT = os.getenv("DBAI_ENV", "production").lower() in ("development", "dev", "sandbox", "local")

_COOKIE_SECURE = not _IS_DEVELOPMENT

if _COOKIE_SECURE and not os.getenv("DBAI_TLS_PROXY"):
    # Prüfe ob wir in Docker ohne TLS-Proxy laufen
    if os.path.exists("/.dockerenv") and os.getenv("DBAI_SANDBOX") == "true":
        _COOKIE_SECURE = False
        logger.warning("[SECURITY] Sandbox erkannt ohne TLS — Cookie Secure=False (OK für lokale Entwicklung)")

async def api_version_middleware(request: Request, call_next):
    """Fügt API-Versioning-Header zu allen Responses hinzu."""
    response = await call_next(request)
    response.headers["X-API-Version"] = _API_VERSION
    response.headers["X-DBAI-Version"] = _API_VERSION
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response

async def csrf_middleware(request: Request, call_next):
    """CSRF-Schutz: State-changing Requests brauchen gültigen X-CSRF-Token Header."""
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        path = request.url.path
        # Whitelist: Login, Health-Check, WS und Static Files brauchen kein CSRF
        csrf_exempt = (
            path.startswith("/api/auth/login") or
            path.startswith("/api/health") or
            path.startswith("/ws") or
            not path.startswith("/api/")
        )
        if not csrf_exempt:
            csrf_cookie = request.cookies.get("dbai_csrf", "")
            csrf_header = request.headers.get("x-csrf-token", "")
            if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
                client_ip = request.client.host if request.client else "unknown"
                # Unterscheide fehlenden Cookie (Config-Problem) von Mismatch (echter Angriff)
                if not csrf_cookie:
                    logger.warning(
                        "[CSRF] Cookie fehlt — wahrscheinlich Secure-Flag Problem! "
                        "path=%s ip=%s cookie_secure=%s env=%s",
                        path, client_ip, _COOKIE_SECURE,
                        os.getenv('DBAI_ENV', 'production')
                    )
                else:
                    logger.warning("[CSRF] Token-Mismatch: path=%s ip=%s", path, client_ip)
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF-Token fehlt oder ungültig",
                             "hint": "Cookie möglicherweise nicht gesetzt (HTTP ohne Secure-Flag?)" if not csrf_cookie else "Token stimmt nicht überein"}
                )
    response = await call_next(request)
    return response

async def rate_limit_middleware(request: Request, call_next):
    """Sliding-Window Rate-Limiting: max 120 Req/Min pro IP, Memory-safe."""
    global _rate_limit_last_cleanup
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()

    # ── Security-Immunsystem: IP-Ban-Prüfung ──
    if client_ip not in ("127.0.0.1", "::1", "unknown"):
        try:
            banned = db_query_rt("""
                SELECT EXISTS(
                    SELECT 1 FROM dbai_security.ip_bans
                    WHERE ip_address = %s::INET AND is_active = TRUE
                    AND (expires_at IS NULL OR expires_at > now())
                ) AS b
            """, (client_ip,))
            if banned and banned[0].get("b"):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Zugriff gesperrt. IP ist gebannt."}
                )
        except Exception:
            pass  # Security-Schema noch nicht vorhanden → weiter

    entry = _rate_limit_store.get(client_ip)
    if entry:
        count, window_start = entry
        if now - window_start >= _RATE_WINDOW:
            # Fenster abgelaufen → Reset
            _rate_limit_store[client_ip] = [1, now]
        elif count >= _RATE_LIMIT:
            return JSONResponse(
                status_code=429,
                content={"detail": "Zu viele Anfragen. Bitte warten."}
            )
        else:
            entry[0] = count + 1
    else:
        _rate_limit_store[client_ip] = [1, now]

    # Periodische Bereinigung: alle 30s oder bei Hard-Cap
    if now - _rate_limit_last_cleanup > 30 or len(_rate_limit_store) > _RATE_MAX_ENTRIES:
        _rate_limit_last_cleanup = now
        cutoff = now - _RATE_WINDOW * 2
        stale = [ip for ip, (_, ws) in _rate_limit_store.items() if ws < cutoff]
        for ip in stale:
            del _rate_limit_store[ip]

    response = await call_next(request)
    return response

import traceback as _tb_mod

def _classify_exception(exc: Exception, request: Request):
    """Klassifiziert eine Exception und gibt (status_code, error_detail) zurück."""
    # ---- KeyError / ValueError / TypeError → 400 Bad Request ----
    if isinstance(exc, (KeyError, ValueError, TypeError)):
        msg = str(exc).strip("'\"") if str(exc) else exc.__class__.__name__
        logging.warning("Input-Fehler in %s %s: %s", request.method, request.url.path, msg)
        return 400, f"Ungültige Eingabe: {msg}"

    # ---- psycopg2-Fehler: semantisches Mapping ----
    if isinstance(exc, psycopg2.Error):
        msg_primary = ""
        pg_code = ""
        if hasattr(exc, 'diag') and exc.diag:
            msg_primary = exc.diag.message_primary or ""
            pg_code = exc.diag.sqlstate or ""
        error_detail = f"Datenbankfehler: {msg_primary}" if msg_primary else str(exc)
        err_lower = error_detail.lower()

        status = 500
        if pg_code.startswith("22") or pg_code.startswith("42"):
            status = 400
        elif pg_code == "23505":
            status = 409
            error_detail = f"Bereits vorhanden: {msg_primary}"
        elif pg_code.startswith("23"):
            status = 422
        elif "invalid input syntax" in err_lower:
            status = 400
        elif "duplicate key" in err_lower:
            status = 409
            error_detail = f"Bereits vorhanden: {msg_primary or str(exc)}"
        elif "violates check constraint" in err_lower or "violates not-null" in err_lower or "null value in column" in err_lower:
            status = 422
        elif "violates foreign key" in err_lower:
            status = 422
        elif "does not exist" in err_lower and not pg_code.startswith("42"):
            # Nur echte "Ressource nicht gefunden"-Fälle, nicht Schema-/Struktur-Fehler
            status = 404

        logging.error("DB-Fehler [%s] in %s %s: %s", pg_code, request.method, request.url.path, error_detail)
        return status, error_detail

    # ---- FileNotFoundError → 404 ----
    if isinstance(exc, FileNotFoundError):
        logging.warning("Datei nicht gefunden in %s %s: %s", request.method, request.url.path, exc)
        return 404, f"Nicht gefunden: {exc}"

    # ---- PermissionError → 403 ----
    if isinstance(exc, PermissionError):
        logging.warning("Zugriff verweigert in %s %s: %s", request.method, request.url.path, exc)
        return 403, f"Zugriff verweigert: {exc}"

    # ---- TimeoutError → 504 ----
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        logging.error("Timeout in %s %s: %s", request.method, request.url.path, exc)
        return 504, "Zeitüberschreitung"

    # ---- Alles andere → 500 ----
    logging.error(
        "Unbehandelte Exception in %s %s:\n%s",
        request.method, request.url.path,
        _tb_mod.format_exc()
    )
    return 500, str(exc) if str(exc) else exc.__class__.__name__

async def catch_all_exceptions_middleware(request: Request, call_next):
    """
    Fängt ALLE Exceptions auf Middleware-Ebene ab, BEVOR Starlettes
    ServerErrorMiddleware sie loggen kann. Verhindert 'Exception in ASGI application'-Spam.
    """
    try:
        response = await call_next(request)
        return response
    except Exception as exc:
        status, detail = _classify_exception(exc, request)
        return JSONResponse(status_code=status, content={"error": detail})

class LoginRequest(BaseModel):
    username: str
    password: str

class GhostSwapRequest(BaseModel):
    role: str
    model: str
    reason: str = "Manueller Wechsel"

class GhostQueryRequest(BaseModel):
    role: str
    question: str
    context: dict = {}
    model: str = None  # Optionales Modell — wenn gesetzt, wird ggf. automatisch gewechselt

class WindowUpdate(BaseModel):
    pos_x: Optional[int] = None
    pos_y: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    state: Optional[str] = None
    is_focused: Optional[bool] = None
    z_index: Optional[int] = None

async def get_current_session(request: Request) -> dict:
    """Validiert die Session aus dem Authorization-Header oder Cookie."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        token = request.cookies.get("dbai_token", "")
    if not token:
        raise HTTPException(status_code=401, detail="Nicht authentifiziert")

    result = await adb_call_json_rt(
        "SELECT dbai_ui.validate_session(%s)",
        (token,)
    )
    if not result or not result.get("valid"):
        raise HTTPException(status_code=401, detail="Session ungültig oder abgelaufen")

    return result

def require_admin(session: dict) -> None:
    """Prüft ob der User Admin ist. Wirft 403 wenn nicht."""
    if not session.get("user", {}).get("is_admin"):
        raise HTTPException(status_code=403, detail="Nur Administratoren")

_llm_model_name = "qwen3.5-27b-q8"

_llm_model_path = "/mnt/nvme/models/qwen3.5-27b-q8/Qwen3.5-27B-Q8_0.gguf"

_llm_server_port = 8081

def _detect_llm_host():
    """Ermittelt die richtige Host-IP für den llama-server."""
    import subprocess as sp
    # Prüfe zuerst ob wir überhaupt in einem Container sind
    try:
        with open("/proc/1/cgroup", "r") as f:
            cgroup = f.read()
        in_container = "docker" in cgroup or "kubepods" in cgroup
    except Exception:
        in_container = False
    if not in_container:
        return "127.0.0.1"  # Direkt auf Host — immer localhost
    # Im Container: Gateway = Host-IP
    try:
        r = sp.run(["ip", "route"], capture_output=True, text=True, timeout=3)
        for line in r.stdout.splitlines():
            if line.startswith("default via"):
                return line.split()[2]
    except Exception as e:
        logger.debug("silent-exception: %s", e)
    return "127.0.0.1"

_llm_host_ip = _detect_llm_host()

_llm_server_url = f"http://{_llm_host_ip}:{_llm_server_port}"

_llm_server_bin = "/tmp/llama.cpp/build/bin/llama-server"

_llm_server_process = None           # subprocess.Popen Referenz

_llm_server_device = "gpu"            # "gpu" oder "cpu"

_llm_server_gpu_layers = 99           # n_gpu_layers (0 = rein CPU)

_llm_server_ctx_size = 8192

_llm_server_threads = 12

_llm_lock = threading.Lock()           # Schützt _llm_server_* Globals (kurze Operationen)

_llm_op_lock = threading.Lock()        # Serialisiert Start/Stop-Operationen (non-blocking)

import urllib.request

import urllib.error

import subprocess as _sp

def _llm_server_health() -> bool:
    """Prüfe ob der llama-server erreichbar ist."""
    try:
        req = urllib.request.Request(f"{_llm_server_url}/health", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            return data.get("status") == "ok"
    except Exception:
        return False

def _llm_server_stop():
    """Laufenden llama-server stoppen + GPU-Speicher korrekt freigeben.

    Lock-Strategie: _llm_lock wird NUR für den Prozess-Zugriff gehalten,
    NICHT für DB-Aufrufe oder time.sleep() — verhindert Deadlocks.
    """
    global _llm_server_process

    # Phase 1: DB-Aufrufe AUSSERHALB des Locks (verhindert Lock-Ordering-Deadlock)
    try:
        db_execute_rt("""
            UPDATE dbai_llm.vram_allocations SET is_active = FALSE, released_at = NOW()
            WHERE is_active = TRUE
        """)
    except Exception as e:
        logger.debug("silent-exception: %s", e)

    # Phase 2: Prozess stoppen UNTER Lock (kurze Dauer, kein sleep/DB)
    with _llm_lock:
        if _llm_server_process and _llm_server_process.poll() is None:
            _llm_server_process.terminate()
            try:
                _llm_server_process.wait(timeout=10)
            except Exception:
                _llm_server_process.kill()
            _llm_server_process = None
        # Auch eventuell extern gestartete Prozesse killen
        try:
            _sp.run(["pkill", "-f", f"llama-server.*--port {_llm_server_port}"], timeout=5, capture_output=True)
        except Exception as e:
            logger.debug("silent-exception: %s", e)

    # Phase 3: Cooldown AUSSERHALB des Locks (blockiert keine anderen Threads)
    import time
    cooldown = 3
    try:
        cd_rows = db_query_rt("SELECT value FROM dbai_core.config WHERE key = 'gpu_cooldown_after_unload_sec'")
        if cd_rows:
            val = cd_rows[0]["value"]
            cooldown = int(val) if isinstance(val, (int, float)) else int(json.loads(val)) if isinstance(val, str) else 3
    except Exception as e:
        logger.debug("silent-exception: %s", e)
    time.sleep(cooldown)

    # Phase 4: Watchdog-Log AUSSERHALB des Locks
    try:
        db_execute_rt("""
            INSERT INTO dbai_llm.watchdog_log (target, is_healthy, action_taken, details)
            VALUES ('llama-server', FALSE, 'stopped', %s::jsonb)
        """, (json.dumps({"reason": "manual_stop", "cooldown_sec": cooldown}),))
    except Exception as e:
        logger.debug("silent-exception: %s", e)

def _llm_server_start(device: str = "gpu", n_gpu_layers: int = 99,
                       ctx_size: int = 8192, threads: int = 12,
                       model_path: str = None, model_name: str = None):
    """llama-server starten mit CPU oder GPU Konfiguration.

    Lock-Strategie:
      _llm_op_lock — Serialisiert ganze Start/Stop-Operationen (non-blocking).
                     Verhindert Race-Condition bei parallelen Start-Aufrufen.
      _llm_lock    — Schützt nur kurz _llm_server_* Globals (State + Popen).
                     NICHT für DB-Aufrufe oder time.sleep() gehalten.
    Verhindert: Deadlock durch Lock-Ordering (llm_lock → db_pool._lock)
                und blockierendes 120s Lock-Halten.
    """
    global _llm_server_process, _llm_server_device, _llm_server_gpu_layers
    global _llm_server_ctx_size, _llm_server_threads, _llm_model_path, _llm_model_name

    # Prüfen ob Binary existiert
    if not Path(_llm_server_bin).exists():
        logger.warning("[LLM] llama-server Binary nicht gefunden: %s — Überspringe Start", _llm_server_bin)
        return False

    # Fail-Fast: Wenn bereits eine Start-Operation läuft, nicht blockierend warten
    if not _llm_op_lock.acquire(blocking=False):
        logger.warning("[LLM] Start-Operation bereits aktiv — überspringe parallelen Start")
        return False

    try:
        # Phase 1: Alten Server stoppen (hat eigene Lock-Strategie)
        _llm_server_stop()

        # Phase 2: State setzen + Prozess starten UNTER Lock (kurze Dauer)
        with _llm_lock:
            if model_path:
                _llm_model_path = model_path
            if model_name:
                _llm_model_name = model_name

            _llm_server_device = device
            gpu_layers = n_gpu_layers if device == "gpu" else 0
            _llm_server_gpu_layers = gpu_layers
            _llm_server_ctx_size = ctx_size
            _llm_server_threads = threads

            cmd = [
                _llm_server_bin,
                "--model", _llm_model_path,
                "--host", "0.0.0.0",
                "--port", str(_llm_server_port),
                "--n-gpu-layers", str(gpu_layers),
                "--ctx-size", str(ctx_size),
                "--threads", str(threads),
                "--alias", _llm_model_name,
            ]

            logger.info(f"[LLM] Starte llama-server: device={device}, gpu_layers={gpu_layers}, ctx={ctx_size}")
            logger.info(f"[LLM] Befehl: {' '.join(cmd)}")

            # ── CUDA / llama.cpp Shared-Libs erreichbar machen ──
            llm_env = os.environ.copy()
            _extra_lib_paths = [
                os.path.dirname(_llm_server_bin),          # libggml-cuda.so neben Binary
                "/usr/local/cuda/lib64",                   # CUDA Toolkit (symlink)
                "/usr/local/cuda-12.8/lib64",              # CUDA 12.8 explizit
                "/usr/local/cuda-12/lib64",                # CUDA 12 generisch
            ]
            existing_ld = llm_env.get("LD_LIBRARY_PATH", "")
            llm_env["LD_LIBRARY_PATH"] = ":".join(
                p for p in _extra_lib_paths + [existing_ld] if p
            )

            log_file = open("/tmp/llama-server.log", "w")
            _llm_server_process = _sp.Popen(
                cmd,
                stdout=log_file,
                stderr=_sp.STDOUT,
                preexec_fn=os.setsid,
                env=llm_env,
            )
            # Lokale Referenz für Health-Check ohne Lock
            proc_ref = _llm_server_process
            started_model = _llm_model_name

        # Phase 3: Health-Wait AUSSERHALB des Locks (bis 120s, blockiert keine anderen Threads)
        import time
        for _ in range(120):
            time.sleep(1)
            if _llm_server_health():
                logger.info(f"[LLM] llama-server bereit auf {_llm_server_url} ({device.upper()})")
                # VRAM-Allokation tracken (DB-Aufrufe außerhalb des Locks)
                try:
                    model_rows = db_query_rt("SELECT id, required_vram_mb FROM dbai_llm.ghost_models WHERE name = %s", (started_model,))
                    if model_rows:
                        mid = str(model_rows[0]["id"])
                        vram = model_rows[0].get("required_vram_mb") or 0
                        db_execute_rt("""
                            INSERT INTO dbai_llm.vram_allocations (gpu_index, model_id, vram_allocated_mb, is_active)
                            VALUES (0, %s::UUID, %s, TRUE)
                        """, (mid, vram))
                    db_execute_rt("""
                        INSERT INTO dbai_llm.watchdog_log (target, is_healthy, response_ms, action_taken, details)
                        VALUES ('llama-server', TRUE, NULL, 'started', %s::jsonb)
                    """, (json.dumps({"model": started_model, "device": device, "gpu_layers": gpu_layers}),))
                except Exception as e:
                    logger.debug(f"[LLM] VRAM-Tracking Fehler: {e}")
                return True
            if proc_ref.poll() is not None:
                logger.error(f"[LLM] llama-server beendet mit Code {proc_ref.returncode}")
                return False

        logger.error("[LLM] llama-server Timeout nach 120s")
        return False
    finally:
        _llm_op_lock.release()

def _llm_chat_completion(messages: list, max_tokens: int = 2048, temperature: float = 0.7) -> dict:
    """Chat-Completion via llama-server HTTP API (OpenAI-kompatibel)."""
    try:
        payload = json.dumps({
            "model": _llm_model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": 0.9,
            "repeat_penalty": 1.1,
            "stream": False,
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{_llm_server_url}/v1/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
        text = ""
        if result.get("choices") and len(result["choices"]) > 0:
            text = result["choices"][0].get("message", {}).get("content", "")
        usage = result.get("usage", {})
        return {
            "response": text,
            "tokens_used": usage.get("total_tokens", 0),
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
        }
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        logger.error(f"[LLM] HTTP-Fehler {e.code}: {body[:300]}")
        return {"error": f"LLM-Server HTTP {e.code}: {body[:200]}", "response": None}
    except urllib.error.URLError as e:
        logger.error(f"[LLM] Server nicht erreichbar: {e}")
        return {"error": "LLM-Server nicht erreichbar. Ist llama-server gestartet?", "response": None}
    except Exception as e:
        logger.error(f"[LLM] Inferenz-Fehler: {e}")
        return {"error": str(e), "response": None}

def _check_gpu_available() -> dict:
    """Prüft ob GPU/CUDA verfügbar ist."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(', ')
            return {
                "available": True, "name": parts[0] if len(parts) > 0 else "GPU",
                "total_mb": int(parts[1]) if len(parts) > 1 else 0,
                "used_mb": int(parts[2]) if len(parts) > 2 else 0,
                "utilization": int(parts[3]) if len(parts) > 3 else 0,
            }
    except Exception as e:
        logger.debug("silent-exception: %s", e)
    return {"available": False, "name": None, "message": "Keine GPU erkannt — CPU-Training verfügbar"}

def _estimate_gpu_bandwidth(gpu_name: str) -> float:
    """Schätze GPU-Speicherbandbreite in GB/s basierend auf Kartenname."""
    name = gpu_name.lower()
    # Bekannte GPUs (ungefähre Bandbreiten)
    bandwidths = {
        "rtx pro 6000": 1700, "b200": 8000, "b100": 3350, "b300": 8000,
        "h100": 3350, "h200": 4800, "a100": 2039, "a6000": 768,
        "5090": 1792, "5080": 960, "5070 ti": 896, "5070": 672,
        "4090": 1008, "4080": 717, "4070 ti": 504, "4070": 504,
        "4060 ti": 288, "4060": 272,
        "3090": 936, "3080": 760, "3070": 448, "3060": 360,
        "2080 ti": 616, "2080": 448, "2070": 448, "2060": 336,
        "1080 ti": 484, "1080": 320, "1070": 256, "1060": 192,
        "a5000": 768, "a4000": 448, "a2000": 288,
        "t4": 300, "v100": 900, "p100": 732,
        "rx 7900": 960, "rx 7800": 624, "rx 6900": 512,
    }
    for key, bw in bandwidths.items():
        if key in name:
            return bw
    return 300  # Konservativer Default

def _calc_gpu_optimal(model_vram_mb: int, model_ctx: int, gpu_free_mb: int,
                      gpu_total_mb: int, quant: str) -> dict:
    """Berechne optimale GPU-Einstellungen basierend auf verfügbarem VRAM."""
    # Sicherheitspuffer: 10% VRAM für System reservieren
    usable_vram = int(gpu_free_mb * 0.90) if gpu_free_mb > 0 else 0

    # Geschätzte Layer-Anzahl basierend auf Modellgröße
    # Typische Modelle: 7B→32 layers, 13B→40, 34B→48, 70B→80
    if model_vram_mb <= 0:
        model_vram_mb = 4000  # Default 4GB
    total_layers = _estimate_layers(model_vram_mb)

    # Wieviel VRAM pro Layer?
    vram_per_layer = model_vram_mb / max(total_layers, 1)

    # Wieviele Layer passen in den VRAM?
    # Context-Buffer benötigt auch VRAM: ~2MB pro 1K Context bei Q4, ~4MB bei F16
    ctx_factor = {"Q2_K": 1.0, "Q3_K_M": 1.5, "Q4_0": 2.0, "Q4_K_M": 2.0,
                  "Q5_K_M": 2.5, "Q6_K": 3.0, "Q8_0": 4.0, "F16": 8.0, "BF16": 8.0}.get(quant, 2.0)

    # Maximale Context-Größe die in den VRAM passt
    # Reserve für Context-Buffer: ctx_size/1024 * ctx_factor MB
    context_options = [131072, 65536, 32768, 16384, 8192, 4096, 2048]

    best_ctx = 2048
    best_layers = 0
    best_batch = 512

    for ctx in context_options:
        if ctx > model_ctx:
            continue
        ctx_vram = (ctx / 1024) * ctx_factor
        remaining_for_model = usable_vram - ctx_vram
        if remaining_for_model <= 0:
            continue
        layers = min(int(remaining_for_model / max(vram_per_layer, 1)), total_layers)
        if layers >= best_layers:
            best_layers = layers
            best_ctx = ctx
            # Batch-Size basierend auf freiem VRAM
            leftover = remaining_for_model - (layers * vram_per_layer)
            if leftover > 2000:
                best_batch = 2048
            elif leftover > 1000:
                best_batch = 1024
            elif leftover > 500:
                best_batch = 512
            else:
                best_batch = 256
            break  # Nimm den größten Context der noch passt

    # Falls Modell komplett in VRAM passt, maximale Context-Größe nutzen
    if best_layers >= total_layers:
        remaining_vram = usable_vram - model_vram_mb
        for ctx in context_options:
            if ctx > model_ctx:
                continue
            ctx_vram = (ctx / 1024) * ctx_factor
            if ctx_vram <= remaining_vram:
                best_ctx = ctx
                break

    # Threads: basierend auf CPU-Kerne
    import os
    cpu_count = os.cpu_count() or 8
    threads = max(4, min(cpu_count - 2, 16))

    # Offload-Prozent
    offload_pct = round((best_layers / max(total_layers, 1)) * 100)

    return {
        "n_gpu_layers": best_layers,
        "total_layers": total_layers,
        "context_size": best_ctx,
        "batch_size": best_batch,
        "threads": threads,
        "vram_needed_mb": int(best_layers * vram_per_layer + (best_ctx / 1024) * ctx_factor),
        "vram_available_mb": usable_vram,
        "offload_pct": offload_pct,
        "fits_fully": best_layers >= total_layers,
        "model_vram_mb": model_vram_mb,
    }

def _estimate_layers(model_vram_mb: int) -> int:
    """Schätze Layer-Anzahl eines Modells basierend auf VRAM-Bedarf."""
    if model_vram_mb <= 2000:
        return 24   # ~1-3B
    elif model_vram_mb <= 5000:
        return 32   # ~7B
    elif model_vram_mb <= 10000:
        return 40   # ~13B
    elif model_vram_mb <= 20000:
        return 48   # ~34B
    elif model_vram_mb <= 40000:
        return 64   # ~70B
    else:
        return 80   # 100B+

def _detect_gpu_arch(name: str) -> str:
    """GPU-Architektur erkennen."""
    name_l = name.lower()
    if any(x in name_l for x in ["b200", "b100", "b300", "blackwell", "rtx pro 6000"]):
        return "Blackwell"
    elif any(x in name_l for x in ["h100", "h200", "h800"]):
        return "Hopper"
    elif any(x in name_l for x in ["5090", "5080", "5070", "5060", "rtx 5000"]):
        return "Blackwell"
    elif any(x in name_l for x in ["4090", "4080", "4070", "4060", "l40", "ada"]):
        return "Ada Lovelace"
    elif any(x in name_l for x in ["3090", "3080", "3070", "3060", "a100", "a6000", "a5000", "a4000", "a2000"]):
        return "Ampere"
    elif any(x in name_l for x in ["2080", "2070", "2060", "t4", "titan rtx"]):
        return "Turing"
    elif any(x in name_l for x in ["v100", "titan v"]):
        return "Volta"
    elif any(x in name_l for x in ["1080", "1070", "1060", "p100", "p40"]):
        return "Pascal"
    return "Unknown"

def _recommend_models_for_gpu(vram_free_mb: int, bandwidth_gbs: float) -> list:
    """Empfehle Modellgrößen basierend auf GPU-Kapazität."""
    recs = []
    configs = [
        {"label": "1-3B (Klein)", "vram_min": 1500, "vram_ideal": 3000, "quant": "Q4_K_M", "ctx": 8192},
        {"label": "7B (Standard)", "vram_min": 4000, "vram_ideal": 6000, "quant": "Q4_K_M", "ctx": 8192},
        {"label": "7B (Qualität)", "vram_min": 6000, "vram_ideal": 8000, "quant": "Q8_0", "ctx": 16384},
        {"label": "13B (Standard)", "vram_min": 8000, "vram_ideal": 10000, "quant": "Q4_K_M", "ctx": 8192},
        {"label": "13B (Qualität)", "vram_min": 10000, "vram_ideal": 14000, "quant": "Q6_K", "ctx": 16384},
        {"label": "34B (Standard)", "vram_min": 18000, "vram_ideal": 22000, "quant": "Q4_K_M", "ctx": 8192},
        {"label": "70B (Standard)", "vram_min": 36000, "vram_ideal": 42000, "quant": "Q4_K_M", "ctx": 8192},
        {"label": "70B (Qualität)", "vram_min": 42000, "vram_ideal": 48000, "quant": "Q6_K", "ctx": 16384},
    ]
    for c in configs:
        if vram_free_mb >= c["vram_min"]:
            fits_fully = vram_free_mb >= c["vram_ideal"]
            est_tps = round(bandwidth_gbs / (c["vram_ideal"] / 1024) * 1.4, 1) if bandwidth_gbs > 0 else 0
            recs.append({
                "label": c["label"],
                "fits": "full" if fits_fully else "partial",
                "quant": c["quant"],
                "context": c["ctx"],
                "est_tps": est_tps,
            })
    return recs

class ServiceInstallRequest(BaseModel):
    name: str
    port: int = 0

_SERVICE_COMMANDS: dict[str, list[str]] = {
    'n8n':                    ['docker', 'run', '-d', '--name', 'n8n', '-p', '5678:5678', 'n8nio/n8n'],
    'Ollama WebUI':           ['docker', 'run', '-d', '--name', 'ollama-webui', '-p', '3000:8080', 'ghcr.io/ollama-webui/ollama-webui:main'],
    'ComfyUI':                ['docker', 'run', '-d', '--name', 'comfyui', '-p', '8188:8188', 'comfyanonymous/comfyui'],
    'text-generation-webui':  ['docker', 'run', '-d', '--name', 'text-gen-webui', '-p', '7860:7860', 'atinoda/text-generation-webui'],
    'Stable Diffusion WebUI': ['docker', 'run', '-d', '--name', 'sd-webui', '-p', '7861:7860', 'sd-webui'],
    'LocalAI':                ['docker', 'run', '-d', '--name', 'localai', '-p', '8080:8080', 'localai/localai'],
    'vLLM Server':            ['docker', 'run', '-d', '--name', 'vllm', '-p', '8000:8000', 'vllm/vllm-openai'],
    'VS Code Server':         ['docker', 'run', '-d', '--name', 'code-server', '-p', '8443:8443', 'codercom/code-server'],
}

class LLMServerRequest(BaseModel):
    device: str = "gpu"            # "gpu" oder "cpu"
    n_gpu_layers: int = 99         # 0 = CPU-only, 99 = alle auf GPU
    ctx_size: int = 8192
    threads: int = 12
    model_path: str = None
    model_name: str = None

_watchdog_running = False

_watchdog_restart_count = 0

_watchdog_fallback_active = False

async def _llm_watchdog_loop():
    """Background-Task: Prüft alle X Sekunden ob der LLM-Server gesund ist."""
    global _watchdog_running, _watchdog_restart_count, _watchdog_fallback_active
    _watchdog_running = True
    _watchdog_fallback_active = False
    logger.info("[WATCHDOG] LLM Watchdog gestartet")

    while _watchdog_running:
        interval = 10
        max_restarts = 3
        auto_fallback = True
        try:
            cfg = db_query_rt("SELECT key, value FROM dbai_core.config WHERE key LIKE 'llm_watchdog%' OR key = 'llm_auto_fallback'")
            for c in (cfg or []):
                v = c["value"]
                if isinstance(v, str):
                    try:
                        v = json.loads(v)
                    except Exception as e:
                        logger.debug("silent-exception: %s", e)
                if c["key"] == "llm_watchdog_interval_sec": interval = int(v)
                elif c["key"] == "llm_watchdog_max_restarts": max_restarts = int(v)
                elif c["key"] == "llm_auto_fallback": auto_fallback = bool(v)
        except Exception as e:
            logger.debug("silent-exception: %s", e)

        await asyncio.sleep(interval)

        # Nur prüfen wenn ein Modell geladen sein sollte
        if not _llm_model_name:
            continue

        import time
        t0 = time.time()
        healthy = _llm_server_health()
        response_ms = int((time.time() - t0) * 1000)

        if healthy:
            if _watchdog_fallback_active:
                logger.info("[WATCHDOG] llama-server wieder erreichbar — Fallback deaktiviert")
                _watchdog_fallback_active = False
            _watchdog_restart_count = 0
            # Erfolg nur selten loggen (jede 6. Prüfung = ~60s)
            import random
            if random.random() < 0.17:
                try:
                    db_execute_rt("""
                        INSERT INTO dbai_llm.watchdog_log (target, is_healthy, response_ms, action_taken) 
                        VALUES ('llama-server', TRUE, %s, 'none')
                    """, (response_ms,))
                except Exception as e:
                    logger.debug("silent-exception: %s", e)
        else:
            # Wenn Fallback bereits aktiv, nicht erneut warnen (nur still weiterchecken)
            if _watchdog_fallback_active:
                continue

            _watchdog_restart_count += 1
            logger.warning(f"[WATCHDOG] llama-server nicht erreichbar! Restart-Versuch {_watchdog_restart_count}/{max_restarts}")
            action = "none"

            if _watchdog_restart_count < max_restarts:
                # Auto-Restart versuch
                action = f"restart_attempt_{_watchdog_restart_count}"
                loop = asyncio.get_event_loop()
                success = await loop.run_in_executor(
                    None,
                    lambda: _llm_server_start(
                        device=_llm_server_device,
                        n_gpu_layers=_llm_server_gpu_layers,
                        ctx_size=_llm_server_ctx_size,
                        threads=_llm_server_threads,
                    )
                )
                if success:
                    action = "restart_success"
                    _watchdog_restart_count = 0
                    logger.info("[WATCHDOG] llama-server erfolgreich neugestartet")
                else:
                    action = "restart_failed"
            else:
                if auto_fallback:
                    action = "fallback_to_cloud"
                    _watchdog_fallback_active = True
                    logger.warning("[WATCHDOG] Alle Restart-Versuche gescheitert → Cloud-Fallback aktiv")

            try:
                db_execute_rt("""
                    INSERT INTO dbai_llm.watchdog_log (target, is_healthy, response_ms, action_taken, details)
                    VALUES ('llama-server', FALSE, %s, %s, %s::jsonb)
                """, (response_ms, action, json.dumps({
                    "model": _llm_model_name,
                    "restart_count": _watchdog_restart_count,
                    "max_restarts": max_restarts,
                })))
            except Exception as e:
                logger.debug("silent-exception: %s", e)

    logger.info("[WATCHDOG] LLM Watchdog gestoppt")

def _collect_mounts(dev, mounts, parent_name=""):
    """Rekursiv Mountpoints aus lsblk-Output sammeln."""
    mp = dev.get("mountpoint")
    if mp and mp not in ("/boot", "/boot/efi", "[SWAP]"):
        mounts.append({
            "name": dev.get("name", ""),
            "mountpoint": mp,
            "type": dev.get("type", ""),
            "fstype": dev.get("fstype", ""),
            "size": dev.get("size", ""),
            "label": dev.get("label") or dev.get("model") or dev.get("name", ""),
            "hotplug": dev.get("hotplug", False),
            "icon": "💾" if dev.get("type") == "disk" else "💿" if dev.get("type") == "rom" else "📱" if dev.get("hotplug") else "📁",
        })
    for child in dev.get("children", []):
        _collect_mounts(child, mounts, dev.get("name", ""))

def _run_cmd(cmd: list[str], timeout: int = 5) -> str:
    """Hilfsfunktion: Shell-Befehl ausführen, stdout zurückgeben."""
    import subprocess
    try:
        return subprocess.check_output(cmd, timeout=timeout, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return ""

def _linux_display() -> dict:
    """Display/Resolution Info via xrandr, xdpyinfo, sysfs."""
    import os
    info = {"current_resolution": "1920x1080", "refresh_rate": "60", "brightness": 80,
            "scaling": "100%", "night_mode": False, "orientation": "landscape", "monitor_name": "Primär"}
    # xrandr
    out = _run_cmd(["xrandr", "--current"])
    if out:
        resolutions = []
        for line in out.split("\n"):
            if "*" in line:
                parts = line.split()
                if parts:
                    info["current_resolution"] = parts[0]
                    for p in parts[1:]:
                        if "*" in p:
                            info["refresh_rate"] = p.replace("*", "").replace("+", "").strip()
                            break
            elif "x" in line and line.strip()[0].isdigit():
                parts = line.split()
                if parts:
                    resolutions.append(parts[0])
        if resolutions:
            info["available_resolutions"] = list(dict.fromkeys(resolutions))
    # Brightness via sysfs
    try:
        bri_path = "/sys/class/backlight"
        if os.path.isdir(bri_path):
            dev = os.listdir(bri_path)
            if dev:
                cur = int(open(f"{bri_path}/{dev[0]}/brightness").read().strip())
                mx = int(open(f"{bri_path}/{dev[0]}/max_brightness").read().strip())
                info["brightness"] = round(cur / mx * 100) if mx > 0 else 80
    except Exception as e:
        logger.debug("silent-exception: %s", e)
    return info

def _linux_sound() -> dict:
    """Audio via pactl / amixer."""
    info = {"volume": 75, "muted": False, "input_volume": 80, "system_sounds": True, "startup_sound": False,
            "output_devices": [{"id": "default", "name": "Standard-Ausgabe"}],
            "input_devices": [{"id": "default", "name": "Standard-Mikrofon"}]}
    # pactl
    out = _run_cmd(["pactl", "get-sink-volume", "@DEFAULT_SINK@"])
    if out and "/" in out:
        for part in out.split("/"):
            p = part.strip().rstrip("%")
            try:
                info["volume"] = int(p)
                break
            except ValueError:
                continue
    out_mute = _run_cmd(["pactl", "get-sink-mute", "@DEFAULT_SINK@"])
    if "yes" in out_mute.lower():
        info["muted"] = True
    # Geräte
    out_sinks = _run_cmd(["pactl", "list", "short", "sinks"])
    if out_sinks:
        devs = []
        for line in out_sinks.split("\n"):
            parts = line.split("\t")
            if len(parts) >= 2:
                devs.append({"id": parts[1], "name": parts[1].replace(".", " ").replace("_", " ")})
        if devs:
            info["output_devices"] = devs
    return info

def _linux_bluetooth() -> dict:
    """Bluetooth via bluetoothctl."""
    info = {"enabled": False, "discoverable": False, "paired_devices": []}
    out = _run_cmd(["bluetoothctl", "show"])
    if out:
        info["enabled"] = "Powered: yes" in out
        info["discoverable"] = "Discoverable: yes" in out
    out_devs = _run_cmd(["bluetoothctl", "devices", "Paired"])
    if not out_devs:
        out_devs = _run_cmd(["bluetoothctl", "paired-devices"])
    if out_devs:
        for line in out_devs.split("\n"):
            parts = line.split(" ", 2)
            if len(parts) >= 3:
                mac = parts[1]
                name = parts[2]
                # Check if connected
                dev_info = _run_cmd(["bluetoothctl", "info", mac])
                connected = "Connected: yes" in dev_info if dev_info else False
                dtype = "audio" if any(x in name.lower() for x in ["buds", "headphone", "speaker", "airpod"]) \
                    else "keyboard" if "keyboard" in name.lower() \
                    else "mouse" if "mouse" in name.lower() \
                    else "phone" if "phone" in name.lower() else "other"
                info["paired_devices"].append({"name": name, "mac": mac, "connected": connected, "type": dtype})
    return info

def _linux_power() -> dict:
    """Energie via upower, logind."""
    info = {"battery_present": False, "screen_off_minutes": "10", "suspend_minutes": "30",
            "power_profile": "balanced", "lid_close_suspend": True}
    out = _run_cmd(["upower", "-i", "/org/freedesktop/UPower/devices/battery_BAT0"])
    if out and "percentage" in out:
        info["battery_present"] = True
        for line in out.split("\n"):
            line = line.strip()
            if line.startswith("percentage:"):
                info["battery_percent"] = int(line.split(":")[1].strip().rstrip("%"))
            elif line.startswith("state:"):
                state = line.split(":")[1].strip()
                info["battery_status"] = {"charging": "Laden", "discharging": "Akkubetrieb",
                                          "fully-charged": "Voll geladen"}.get(state, state)
            elif line.startswith("time to"):
                info["time_remaining"] = line.split(":")[1].strip()
    # Power profile
    profile = _run_cmd(["powerprofilesctl", "get"])
    if profile:
        info["power_profile"] = profile
    return info

def _linux_keyboard() -> dict:
    """Tastatur via localectl."""
    info = {"layout": "de", "repeat_rate": 400, "repeat_delay": 500, "num_lock": False, "caps_warning": True}
    out = _run_cmd(["localectl", "status"])
    if out:
        for line in out.split("\n"):
            if "X11 Layout" in line:
                info["layout"] = line.split(":")[1].strip()
    return info

def _linux_mouse() -> dict:
    """Maus-Einstellungen."""
    return {"speed": 10, "scroll_speed": 5, "natural_scroll": False, "left_handed": False,
            "double_click_speed": 400, "cursor_size": "default"}

def _linux_printers() -> dict:
    """Drucker via lpstat."""
    info = {"printers": []}
    out = _run_cmd(["lpstat", "-p", "-d"])
    if out:
        for line in out.split("\n"):
            if line.startswith("printer"):
                parts = line.split()
                if len(parts) >= 2:
                    name = parts[1]
                    status = "Bereit" if "idle" in line.lower() or "enabled" in line.lower() else "Offline"
                    is_default = False
                    info["printers"].append({"name": name, "status": status, "is_default": is_default, "driver": "Auto"})
            elif line.startswith("system default"):
                default_name = line.split(":")[1].strip() if ":" in line else ""
                for p in info["printers"]:
                    if p["name"] == default_name:
                        p["is_default"] = True
    return info

def _linux_storage() -> dict:
    """Speicher via lsblk, df."""
    import os
    info = {"disks": []}
    out = _run_cmd(["lsblk", "-J", "-o", "NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE,RM,ROTA,MODEL"])
    if out:
        import json
        try:
            data = json.loads(out)
            for dev in data.get("blockdevices", []):
                if dev.get("type") == "disk":
                    for part in dev.get("children", [dev]):
                        mount = part.get("mountpoint") or part.get("mountpoints", [None])[0] if isinstance(part.get("mountpoints"), list) else part.get("mountpoint")
                        if not mount:
                            continue
                        try:
                            st = os.statvfs(mount)
                            total_gb = round(st.f_blocks * st.f_frsize / (1024**3), 1)
                            free_gb = round(st.f_bavail * st.f_frsize / (1024**3), 1)
                            used_gb = round(total_gb - free_gb, 1)
                        except Exception:
                            total_gb = free_gb = used_gb = 0
                        dtype = "nvme" if "nvme" in (part.get("name") or "") else \
                                "ssd" if not dev.get("rota", True) else "hdd"
                        info["disks"].append({
                            "name": dev.get("model") or part.get("name", "?"),
                            "device": f"/dev/{part.get('name', '?')}",
                            "mount": mount,
                            "fs": part.get("fstype") or "?",
                            "type": dtype,
                            "removable": bool(dev.get("rm")),
                            "total_gb": total_gb,
                            "used_gb": used_gb,
                            "free_gb": free_gb,
                        })
        except Exception as e:
            logger.debug("silent-exception: %s", e)
    if not info["disks"]:
        # Fallback: df
        out_df = _run_cmd(["df", "-BG", "--output=source,target,size,used,avail,fstype"])
        if out_df:
            for line in out_df.split("\n")[1:]:
                parts = line.split()
                if len(parts) >= 6 and parts[0].startswith("/"):
                    info["disks"].append({
                        "name": parts[0],
                        "device": parts[0],
                        "mount": parts[1],
                        "fs": parts[5],
                        "type": "ssd",
                        "removable": False,
                        "total_gb": float(parts[2].rstrip("G")),
                        "used_gb": float(parts[3].rstrip("G")),
                        "free_gb": float(parts[4].rstrip("G")),
                    })
    return info

def _linux_users() -> dict:
    """Benutzer aus /etc/passwd."""
    info = {"users": []}
    try:
        with open("/etc/passwd") as f:
            for line in f:
                parts = line.strip().split(":")
                if len(parts) >= 7:
                    uid = int(parts[2])
                    if uid >= 1000 or uid == 0:
                        shell = parts[6]
                        if shell in ("/usr/sbin/nologin", "/bin/false"):
                            continue
                        groups = _run_cmd(["groups", parts[0]])
                        is_admin = "sudo" in groups or "wheel" in groups or uid == 0
                        info["users"].append({
                            "username": parts[0],
                            "name": parts[4].split(",")[0] if parts[4] else parts[0],
                            "uid": uid,
                            "is_admin": is_admin,
                            "groups": groups.split(":")[1].strip() if ":" in groups else groups,
                            "shell": shell,
                            "logged_in": uid == 0 or parts[0] in _run_cmd(["who"]),
                        })
    except Exception as e:
        logger.debug("silent-exception: %s", e)
    return info

def _linux_datetime() -> dict:
    """Datum & Uhrzeit via timedatectl."""
    from datetime import datetime
    info = {
        "time": datetime.now().strftime("%H:%M:%S"),
        "date": datetime.now().strftime("%A, %d. %B %Y"),
        "timezone": "Europe/Berlin",
        "ntp_enabled": True,
        "time_format": "24h",
    }
    out = _run_cmd(["timedatectl", "status"])
    if out:
        for line in out.split("\n"):
            line = line.strip()
            if "Time zone" in line:
                info["timezone"] = line.split(":")[1].strip().split(" ")[0]
            elif "NTP" in line and "active" in line.lower():
                info["ntp_enabled"] = "yes" in line.lower()
    return info

def _linux_updates() -> dict:
    """Update-Status."""
    from datetime import datetime
    info = {"updates_available": False, "update_count": 0,
            "ghost_version": "v" + _API_VERSION,
            "last_check": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "auto_update": False}
    # Kernel version
    import platform
    info["kernel_version"] = platform.release()
    # apt check
    out = _run_cmd(["apt", "list", "--upgradable"])
    if out:
        count = len([l for l in out.split("\n") if "/" in l and "Listing" not in l])
        info["update_count"] = count
        info["updates_available"] = count > 0
    return info

def _linux_security() -> dict:
    """Sicherheits-Einstellungen."""
    info = {"firewall_enabled": False, "ssh_enabled": False, "screen_lock": True,
            "lock_timeout": "5", "ssh_keys_count": 0, "certs_count": 0, "gpg_keys_count": 0}
    # ufw
    out = _run_cmd(["ufw", "status"])
    if out:
        info["firewall_enabled"] = "active" in out.lower() and "inactive" not in out.lower()
    # ssh
    out_ssh = _run_cmd(["systemctl", "is-active", "ssh"])
    if not out_ssh:
        out_ssh = _run_cmd(["systemctl", "is-active", "sshd"])
    info["ssh_enabled"] = out_ssh.strip() == "active"
    # SSH keys
    import os
    ssh_dir = os.path.expanduser("~/.ssh")
    if os.path.isdir(ssh_dir):
        info["ssh_keys_count"] = len([f for f in os.listdir(ssh_dir) if f.endswith(".pub")])
    # GPG keys
    out_gpg = _run_cmd(["gpg", "--list-keys", "--keyid-format", "short"])
    if out_gpg:
        info["gpg_keys_count"] = out_gpg.count("pub ")
    return info

def _linux_notifications() -> dict:
    return {}

def _linux_accessibility() -> dict:
    return {}

_LINUX_GETTERS = {
    "display": _linux_display,
    "sound": _linux_sound,
    "bluetooth": _linux_bluetooth,
    "power": _linux_power,
    "keyboard": _linux_keyboard,
    "mouse": _linux_mouse,
    "printers": _linux_printers,
    "storage": _linux_storage,
    "users": _linux_users,
    "datetime": _linux_datetime,
    "updates": _linux_updates,
    "security": _linux_security,
    "notifications": _linux_notifications,
    "accessibility": _linux_accessibility,
}

def _do_network_scan():
    """Synchroner Netzwerk-Scan mit paralleler Port-Prüfung."""
    import socket
    import subprocess as sp
    import urllib.request
    import ssl
    import re as _re
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Eigene IP ermitteln
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "192.168.1.1"

    subnet = ".".join(local_ip.split(".")[:3])
    ports_to_check = [80, 443, 8080, 8443, 3000, 8000, 8888, 9090, 5000, 8081, 7681, 11434]

    # Schnellen Ping-Sweep machen
    alive_ips = set()
    try:
        result = sp.run(
            ["fping", "-a", "-q", "-g", f"{subnet}.1", f"{subnet}.254", "-t", "80"],
            capture_output=True, text=True, timeout=10
        )
        alive_ips = set(result.stdout.strip().split("\n")) if result.stdout.strip() else set()
    except Exception:
        # Fallback: /proc/net/arp + ARP-Tabelle
        try:
            with open("/proc/net/arp") as f:
                for line in f.readlines()[1:]:
                    parts = line.split()
                    if parts and parts[0].startswith(subnet) and parts[2] != "0x0":
                        alive_ips.add(parts[0])
        except Exception as e:
            logger.debug("silent-exception: %s", e)
        if not alive_ips:
            try:
                result = sp.run(["arp", "-n"], capture_output=True, text=True, timeout=3)
                for line in result.stdout.strip().split("\n")[1:]:
                    parts = line.split()
                    if parts and parts[0].startswith(subnet):
                        alive_ips.add(parts[0])
            except Exception:
                alive_ips = {f"{subnet}.1"}

    # Lokale DBAI-Instanz auch hinzufügen
    alive_ips.add(local_ip)
    alive_ips.discard("")

    # SSL context
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    def _probe_port(ip, port):
        """Prüft einen einzelnen IP:Port auf HTTP-Service."""
        protocol = "https" if port in (443, 8443) else "http"
        url = f"{protocol}://{ip}:{port}"
        try:
            req = urllib.request.Request(url, method="GET")
            req.add_header("User-Agent", "DBAI-NetworkScanner/1.0")
            handler = urllib.request.HTTPSHandler(context=ctx) if protocol == "https" else urllib.request.HTTPHandler()
            opener = urllib.request.build_opener(handler)
            resp = opener.open(req, timeout=1.0)
            title = ""
            content_type = resp.headers.get("Content-Type", "")
            server_header = resp.headers.get("Server", "")
            if "text/html" in content_type:
                body = resp.read(4096).decode("utf-8", errors="ignore")
                m = _re.search(r"<title>(.*?)</title>", body, _re.I | _re.S)
                if m:
                    title = m.group(1).strip()[:200]

            dtype = guess_device_type(title, server_header, port, ip)
            hostname = ""
            try:
                hostname = socket.gethostbyaddr(ip)[0]
            except Exception as e:
                logger.debug("silent-exception: %s", e)

            return {
                "ip": ip, "port": port, "url": url, "title": title or f"Web-UI ({port})",
                "hostname": hostname, "device_type": dtype, "server": server_header
            }
        except Exception:
            return None

    # Parallel alle IP:Port-Kombinationen scannen (max 50 gleichzeitig)
    found_devices = []
    tasks = [(ip, port) for ip in alive_ips for port in ports_to_check]

    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(_probe_port, ip, port): (ip, port) for ip, port in tasks}
        for future in as_completed(futures, timeout=30):
            try:
                result = future.result(timeout=2)
                if result:
                    found_devices.append(result)
            except Exception as e:
                logger.debug("silent-exception: %s", e)

    # In DB speichern
    for d in found_devices:
        try:
            db_execute_rt("""
                INSERT INTO dbai_core.network_devices
                    (ip, hostname, web_port, web_url, web_title, device_type, last_seen)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (ip, web_port)
                DO UPDATE SET web_title = EXCLUDED.web_title, hostname = EXCLUDED.hostname,
                   device_type = EXCLUDED.device_type, last_seen = NOW(), is_reachable = TRUE
            """, (d["ip"], d["hostname"], d["port"], d["url"], d["title"], d["device_type"]))
        except Exception as e:
            logger.debug("silent-exception: %s", e)

    return {"ok": True, "devices": found_devices, "scanned_ips": len(alive_ips), "subnet": f"{subnet}.0/24"}

def guess_device_type(title: str, server: str, port: int, ip: str) -> str:
    """Gerätetyp anhand von Titel/Server/Port erraten."""
    t = (title + " " + server).lower()
    if any(w in t for w in ["synology", "nas", "qnap", "truenas", "openmediavault", "unraid"]):
        return "nas"
    if any(w in t for w in ["router", "openwrt", "ddwrt", "fritz", "gateway", "netgear", "tp-link", "ubiquiti", "mikrotik"]):
        return "router"
    if any(w in t for w in ["printer", "drucker", "cups", "epson", "hp ", "brother", "canon"]):
        return "printer"
    if any(w in t for w in ["camera", "kamera", "cam", "hikvision", "dahua", "reolink", "frigate"]):
        return "camera"
    if any(w in t for w in ["home assistant", "hass", "domoticz", "openhab", "homebridge"]):
        return "smarthome"
    if any(w in t for w in ["robot", "roboter", "ros", "roborock", "vacuum", "mower", "staubsauger"]):
        return "robot"
    if any(w in t for w in ["grafana", "prometheus", "portainer", "proxmox", "cockpit", "webmin"]):
        return "server"
    if any(w in t for w in ["ollama", "llm", "open-webui", "text-generation", "kobold", "oobabooga", "lmstudio"]):
        return "ai"
    if any(w in t for w in ["plex", "jellyfin", "emby", "kodi", "sonarr", "radarr"]):
        return "media"
    if any(w in t for w in ["pi-hole", "adguard"]):
        return "dns"
    if any(w in t for w in ["mqtt", "zigbee", "tasmota", "esphome", "shelly"]):
        return "iot"
    if any(w in t for w in ["phone", "android", "termux"]):
        return "phone"
    return "unknown"

async def workshop_search(project_id: str, q: str = "", session: dict = Depends(get_current_session)):
    """Semantische Suche über Medien-Items."""
    if not q:
        return []
    try:
        rows = db_query_rt("""
            SELECT id, file_name, file_type, title, description, tags,
                   ai_description, ai_tags, ai_caption, state, thumbnail_path,
                   width, height, duration_sec, created_at
            FROM dbai_workshop.media_items
            WHERE project_id = %s::UUID
              AND (
                  title ILIKE '%%' || %s || '%%'
                  OR description ILIKE '%%' || %s || '%%'
                  OR ai_description ILIKE '%%' || %s || '%%'
                  OR ai_caption ILIKE '%%' || %s || '%%'
                  OR %s = ANY(tags)
                  OR %s = ANY(ai_tags)
              )
            ORDER BY created_at DESC
            LIMIT 50
        """, (project_id, q, q, q, q, q, q))
        return rows
    except Exception:
        logger.exception("workshop_search failed for project %s", project_id)
        return []

def _workshop_fallback_response(message: str, project_info: dict, media_rows: list) -> str:
    """Fallback-Antwort wenn kein Ghost verfügbar ist."""
    msg_lower = message.lower()
    project_name = project_info.get('name', 'dein Projekt')
    total = project_info.get('total_items', 0)

    if any(w in msg_lower for w in ['zusammenfassung', 'übersicht', 'summary', 'status']):
        response = f"📊 **Zusammenfassung von {project_name}**\n\n"
        response += f"- Projekttyp: {project_info.get('project_type', 'unbekannt')}\n"
        response += f"- Gesamtdateien: {total}\n"
        if media_rows:
            types = {}
            for m in media_rows:
                t = m.get('file_type', 'other')
                types[t] = types.get(t, 0) + 1
            response += f"- Dateitypen: {', '.join(f'{t}: {c}' for t, c in types.items())}\n"
        return response

    if any(w in msg_lower for w in ['tag', 'schlagwort', 'kategorien']):
        all_tags = set()
        for m in media_rows or []:
            for t in (m.get('ai_tags') or m.get('tags') or []):
                all_tags.add(t)
        if all_tags:
            return f"🏷️ Die häufigsten Tags in {project_name}:\n" + ", ".join(sorted(all_tags)[:20])
        return f"Es wurden noch keine Tags in {project_name} generiert. Importiere zuerst Dateien und lass die KI sie analysieren."

    if any(w in msg_lower for w in ['hilfe', 'help', 'was kannst', 'funktionen']):
        return f"""🤖 **Ich bin dein KI-Assistent für {project_name}!**

Ich kann dir bei Folgendem helfen:
- 📊 Zusammenfassung deiner Datenbank zeigen
- 🔍 Nach bestimmten Dateien oder Inhalten suchen
- 🏷️ Tags und Kategorien analysieren
- 📸 Ähnliche Medien finden
- 💡 Tipps zum Organisieren geben

Frag einfach drauf los!"""

    return f"""Danke für deine Frage zu **{project_name}**!

Dein Projekt enthält aktuell **{total} Dateien**. 
{f'Die letzten Dateien sind: ' + ', '.join(m.get('file_name', '') for m in (media_rows or [])[:5]) if media_rows else 'Es wurden noch keine Dateien importiert.'}

💡 Tipp: Importiere Dateien über den Import-Tab, damit ich dir besser helfen kann!"""

class NodeCreate(BaseModel):
    node_key: str
    label: str
    node_type: str = "service"
    icon_type: str = "circle"
    color: str = "#00f5ff"
    glow_color: Optional[str] = None
    position_x: float = 400
    position_y: float = 300
    scale: float = 1.0
    app_id: Optional[str] = None
    url: Optional[str] = None
    is_visible: bool = True
    sort_order: int = 0

class NodeUpdate(BaseModel):
    label: Optional[str] = None
    node_type: Optional[str] = None
    icon_type: Optional[str] = None
    color: Optional[str] = None
    glow_color: Optional[str] = None
    position_x: Optional[float] = None
    position_y: Optional[float] = None
    scale: Optional[float] = None
    app_id: Optional[str] = None
    url: Optional[str] = None
    is_visible: Optional[bool] = None
    sort_order: Optional[int] = None

class SceneUpdate(BaseModel):
    scene_value: dict

_SECURITY_TASK_PROMPTS = {
    "threat_analysis": (
        "Analysiere die folgende Bedrohung und bewerte das Risiko. "
        "Berücksichtige bekannte Angriffsmuster (MITRE ATT&CK). "
        "Gib eine strukturierte Bewertung mit risk_level, Beschreibung "
        "und empfohlenen Maßnahmen."
    ),
    "vuln_assessment": (
        "Bewerte die folgende Schwachstelle im Kontext des DBAI-Systems. "
        "Prüfe ob ein bekannter CVE vorliegt, wie ausnutzbar die Schwachstelle ist, "
        "und welche Gegenmaßnahmen sofort ergriffen werden sollten."
    ),
    "incident_response": (
        "Es wurde ein Sicherheitsvorfall erkannt. Analysiere die Daten, "
        "bewerte die Schwere, identifiziere den Angriffsvektor und "
        "empfiehl konkrete Sofortmaßnahmen und langfristige Absicherung."
    ),
    "baseline_audit": (
        "Prüfe die folgenden Security-Baseline-Ergebnisse. "
        "Identifiziere alle nicht-konformen Checks, bewerte deren Risiko "
        "und empfiehl konkrete Korrekturen in Reihenfolge der Dringlichkeit."
    ),
    "anomaly_detection": (
        "Analysiere die folgenden Daten auf Anomalien. "
        "Suche nach ungewöhnlichen Mustern, Zeitabweichungen, "
        "verdächtigen IP-Adressen oder atypischem Verhalten."
    ),
    "log_analysis": (
        "Analysiere die folgenden Log-Daten auf Sicherheitsrelevanz. "
        "Identifiziere Brute-Force-Versuche, Lateral Movement, "
        "Privilege Escalation oder andere verdächtige Aktivitäten."
    ),
    "network_forensics": (
        "Führe eine Netzwerk-Forensik durch. Analysiere Traffic-Muster, "
        "identifiziere verdächtige Verbindungen, C2-Kommunikation "
        "oder Datenexfiltration."
    ),
    "risk_scoring": (
        "Berechne einen Gesamt-Risikoscore für das System basierend "
        "auf den bereitgestellten Metriken. Berücksichtige alle "
        "Sicherheitssubsysteme und gewichte nach Relevanz."
    ),
    "policy_recommendation": (
        "Empfiehl basierend auf den aktuellen Sicherheitsdaten "
        "Verbesserungen der Security-Policies. "
        "Berücksichtige CIS-Benchmarks und Best Practices."
    ),
    "periodic_report": (
        "Erstelle einen strukturierten Sicherheitsbericht. "
        "Fasse die wichtigsten Ereignisse zusammen, bewerte den "
        "Gesamtzustand und gib priorisierte Empfehlungen."
    ),
}

def _security_ai_build_context(task_type: str, input_data: dict) -> dict:
    """Sammelt relevanten Kontext aus der DB für die Security-Analyse."""
    context = {}

    if task_type in ("threat_analysis", "incident_response", "anomaly_detection"):
        bans = db_query_rt(
            "SELECT ip_address, reason, source FROM dbai_security.ip_bans "
            "WHERE is_active = TRUE LIMIT 20"
        )
        context["active_bans"] = len(bans)
        context["ban_ips"] = [str(b["ip_address"]) for b in bans[:10]]

        intrusions = db_query_rt("""
            SELECT event_type, source_ip::TEXT, classification, priority, COUNT(*) AS cnt
            FROM dbai_security.intrusion_events
            WHERE detected_at > NOW() - INTERVAL '6 hours'
            GROUP BY event_type, source_ip, classification, priority
            ORDER BY cnt DESC LIMIT 10
        """)
        context["recent_intrusion_patterns"] = intrusions

        auth = db_query_rt("""
            SELECT source_ip::TEXT, auth_type, COUNT(*) AS attempts
            FROM dbai_security.failed_auth_log
            WHERE attempt_at > NOW() - INTERVAL '6 hours'
            GROUP BY source_ip, auth_type
            ORDER BY attempts DESC LIMIT 10
        """)
        context["failed_auth_summary"] = auth

    elif task_type == "vuln_assessment":
        if input_data.get("cve_id"):
            cves = db_query_rt(
                "SELECT cve_id, title, cvss_score, is_patched FROM dbai_security.cve_tracking WHERE cve_id = %s",
                (input_data["cve_id"],)
            )
            context["cve_info"] = cves
        vulns = db_query_rt("""
            SELECT severity, COUNT(*) AS cnt FROM dbai_security.vulnerability_findings
            WHERE status = 'open' GROUP BY severity
        """)
        context["open_vulns_by_severity"] = {v["severity"]: v["cnt"] for v in vulns}

    elif task_type == "baseline_audit":
        baselines = db_query_rt("""
            SELECT component, check_name, expected_value, current_value, compliant, severity
            FROM dbai_security.security_baselines WHERE NOT compliant
            ORDER BY CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2
                     WHEN 'medium' THEN 3 ELSE 4 END LIMIT 20
        """)
        context["non_compliant_baselines"] = baselines

    elif task_type in ("risk_scoring", "periodic_report"):
        context["open_vulns"] = db_query_rt(
            "SELECT severity, COUNT(*) AS cnt FROM dbai_security.vulnerability_findings "
            "WHERE status = 'open' GROUP BY severity"
        )
        context["active_bans"] = db_query_rt(
            "SELECT COUNT(*) AS cnt FROM dbai_security.ip_bans WHERE is_active = TRUE"
        )
        context["intrusions_24h"] = db_query_rt(
            "SELECT COUNT(*) AS cnt FROM dbai_security.intrusion_events "
            "WHERE detected_at > NOW() - INTERVAL '24 hours'"
        )
        context["failed_auth_24h"] = db_query_rt(
            "SELECT COUNT(*) AS cnt FROM dbai_security.failed_auth_log "
            "WHERE attempt_at > NOW() - INTERVAL '24 hours'"
        )
        context["compliance"] = db_query_rt("""
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE compliant) AS compliant,
                   ROUND(100.0 * COUNT(*) FILTER (WHERE compliant) / NULLIF(COUNT(*), 0), 1) AS pct
            FROM dbai_security.security_baselines
        """)
        context["honeypot_24h"] = db_query_rt(
            "SELECT COUNT(*) AS cnt FROM dbai_security.honeypot_events "
            "WHERE detected_at > NOW() - INTERVAL '24 hours'"
        )
        context["tls_expiring"] = db_query_rt(
            "SELECT COUNT(*) AS cnt FROM dbai_security.tls_certificates "
            "WHERE expires_at < NOW() + INTERVAL '30 days'"
        )

    elif task_type == "log_analysis":
        context["recent_auth_failures"] = db_query_rt("""
            SELECT source_ip::TEXT, auth_type, username, COUNT(*) AS attempts,
                   MAX(attempt_at) AS last_attempt
            FROM dbai_security.failed_auth_log
            WHERE attempt_at > NOW() - INTERVAL '24 hours'
            GROUP BY source_ip, auth_type, username ORDER BY attempts DESC LIMIT 20
        """)
        context["recent_responses"] = db_query_rt("""
            SELECT trigger_type, response_type, description, created_at
            FROM dbai_security.security_responses
            ORDER BY created_at DESC LIMIT 10
        """)

    elif task_type == "network_forensics":
        context["traffic_summary"] = db_query_rt("""
            SELECT protocol, direction, COUNT(*) AS conn_count,
                   SUM(bytes_transferred) AS total_bytes
            FROM dbai_security.network_traffic_log
            WHERE logged_at > NOW() - INTERVAL '6 hours'
            GROUP BY protocol, direction ORDER BY conn_count DESC LIMIT 20
        """)
        context["suspicious_traffic"] = db_query_rt("""
            SELECT source_ip::TEXT, dest_ip::TEXT, dest_port, protocol, is_suspicious, flags
            FROM dbai_security.network_traffic_log
            WHERE is_suspicious = TRUE AND logged_at > NOW() - INTERVAL '24 hours'
            ORDER BY logged_at DESC LIMIT 20
        """)

    return context

def _security_ai_build_prompt(task_type: str, input_data: dict, context: dict) -> str:
    """Baut den vollständigen Security-Analyse-Prompt."""
    task_prompt = _SECURITY_TASK_PROMPTS.get(task_type, "Analysiere die folgenden Sicherheitsdaten.")

    parts = [task_prompt, "", "## Eingabedaten:"]
    parts.append(f"```json\n{json.dumps(input_data, indent=2, default=str)}\n```")

    if context:
        parts.append("")
        parts.append("## Kontext (aktuelle System-Sicherheitslage):")
        parts.append(f"```json\n{json.dumps(context, indent=2, default=str)}\n```")

    parts.append("")
    parts.append("## Gewünschtes Ausgabeformat:")
    parts.append("Antworte als JSON mit folgender Struktur:")
    parts.append("```json")
    parts.append(json.dumps({
        "risk_level": "critical|high|medium|low|info",
        "confidence": 0.85,
        "summary": "Kurze Zusammenfassung",
        "details": "Ausführliche Analyse",
        "recommended_actions": [
            {"action": "ban_ip", "target": "1.2.3.4", "reason": "...", "priority": 1}
        ],
        "indicators_of_compromise": ["..."],
        "mitre_techniques": ["T1110 - Brute Force"],
    }, indent=2))
    parts.append("```")

    return "\n".join(parts)

def _security_ai_parse_response(text: str) -> dict:
    """Parst die KI-Antwort und extrahiert strukturierte Daten."""
    import re as _re_parse

    result = {
        "risk_level": "info", "confidence": 0.5, "summary": "",
        "details": text, "recommended_actions": [],
        "indicators_of_compromise": [], "mitre_techniques": [],
    }

    try:
        json_match = _re_parse.search(r'```json\s*(.*?)\s*```', text, _re_parse.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group(1))
        else:
            parsed = json.loads(text)

        if isinstance(parsed, dict):
            for key in result:
                if key in parsed:
                    result[key] = parsed[key]
            if result["risk_level"] not in ("critical", "high", "medium", "low", "info"):
                result["risk_level"] = "info"
            try:
                result["confidence"] = max(0.0, min(1.0, float(result["confidence"])))
            except (ValueError, TypeError):
                result["confidence"] = 0.5
    except (json.JSONDecodeError, ValueError):
        text_lower = text.lower()
        if "critical" in text_lower or "kritisch" in text_lower:
            result["risk_level"] = "critical"
            result["confidence"] = 0.7
        elif "high" in text_lower or "hoch" in text_lower:
            result["risk_level"] = "high"
            result["confidence"] = 0.6
        elif "medium" in text_lower or "mittel" in text_lower:
            result["risk_level"] = "medium"
            result["confidence"] = 0.5
        result["summary"] = text[:200]

    return result

def _security_ai_auto_response(task_id: str, task_type: str, input_data: dict, parsed: dict):
    """Führt automatische Gegenmaßnahmen aus wenn die KI empfiehlt (und Config es erlaubt)."""
    try:
        config_rows = db_query_rt("SELECT key, value FROM dbai_security.ai_config WHERE key IN ('auto_response_enabled', 'auto_ban_enabled', 'auto_mitigate_enabled', 'max_auto_ban_hours')")
        cfg = {}
        for r in config_rows:
            v = r["value"]
            if isinstance(v, str):
                try: v = json.loads(v)
                except: pass
            cfg[r["key"]] = v

        if not cfg.get("auto_response_enabled", True):
            return

        recommended = parsed.get("recommended_actions", [])
        if not isinstance(recommended, list):
            return

        executed = False
        for action in recommended:
            if not isinstance(action, dict):
                continue
            action_type = action.get("action", "")

            if action_type == "ban_ip" and cfg.get("auto_ban_enabled", True):
                ip = action.get("target", action.get("ip"))
                reason = action.get("reason", f"KI-Analyse: {task_type}")
                hours = cfg.get("max_auto_ban_hours", 24)
                if isinstance(hours, str):
                    try: hours = int(hours)
                    except: hours = 24
                if ip:
                    try:
                        db_execute_rt("""
                            INSERT INTO dbai_security.ip_bans (ip_address, reason, ban_type, source, expires_at)
                            VALUES (%s::INET, %s, 'temporary', 'ai_monitor', NOW() + (%s || ' hours')::INTERVAL)
                            ON CONFLICT (ip_address, cidr_mask) DO UPDATE SET
                                is_active = TRUE, banned_at = NOW(), reason = EXCLUDED.reason, expires_at = EXCLUDED.expires_at
                        """, (ip, f"[KI] {reason}", str(hours)))
                        db_execute_rt("""
                            INSERT INTO dbai_security.security_responses (trigger_type, response_type, description, success)
                            VALUES ('ai_analysis', 'auto_ban', %s, TRUE)
                        """, (f"KI-Auto-Ban: {ip} — {reason} (Task: {task_id})",))
                        executed = True
                        logger.info("[SECURITY-AI] Auto-Ban: %s — %s", ip, reason)
                    except Exception as e:
                        logger.error("[SECURITY-AI] Auto-Ban fehlgeschlagen: %s", e)

            elif action_type == "mitigate_vuln" and cfg.get("auto_mitigate_enabled", False):
                vuln_id = action.get("target", action.get("vuln_id"))
                if vuln_id:
                    try:
                        db_execute_rt("""
                            UPDATE dbai_security.vulnerability_findings
                            SET status = 'mitigated', auto_mitigated = TRUE, resolved_at = NOW()
                            WHERE id = %s::UUID AND status = 'open'
                        """, (vuln_id,))
                        executed = True
                    except Exception as e:
                        logger.error("[SECURITY-AI] Auto-Mitigation fehlgeschlagen: %s", e)

            elif action_type in ("alert", "notify", "escalate"):
                try:
                    db_execute_rt("""
                        INSERT INTO dbai_security.security_responses (trigger_type, response_type, description, success)
                        VALUES ('ai_analysis', 'alert', %s, TRUE)
                    """, (f"KI-Alert: {action.get('reason', task_type)} (Task: {task_id})",))
                    executed = True
                except Exception as e:
                    logger.debug("silent-exception: %s", e)

        if executed:
            db_execute_rt(
                "UPDATE dbai_security.ai_tasks SET auto_executed = TRUE WHERE id = %s::UUID",
                (task_id,)
            )
    except Exception as e:
        logger.error("[SECURITY-AI] Auto-Response Fehler: %s", e)

def _security_ai_process_task(task_id: str, task_type: str, input_data: dict):
    """
    Verarbeitet einen Security-AI-Task vollständig:
    Context → Prompt → LLM-Inferenz → Parse → Speichern → Auto-Response.
    Läuft in einem separaten Thread.
    """
    start_time = time.monotonic()
    try:
        # Task als processing markieren
        db_execute_rt(
            "UPDATE dbai_security.ai_tasks SET state = 'processing', started_at = NOW() WHERE id = %s::UUID",
            (task_id,)
        )

        # 1. Security-Ghost System-Prompt laden
        system_prompt = "Du bist der Security-Monitor des DBAI-Systems."
        try:
            role_rows = db_query_rt(
                "SELECT system_prompt FROM dbai_llm.ghost_roles WHERE name = 'security'"
            )
            if role_rows and role_rows[0].get("system_prompt"):
                system_prompt = role_rows[0]["system_prompt"]
        except Exception as e:
            logger.debug("silent-exception: %s", e)

        # 2. Kontext aus DB sammeln
        context = _security_ai_build_context(task_type, input_data)

        # 3. Prompt zusammenbauen
        user_prompt = _security_ai_build_prompt(task_type, input_data, context)

        # 4. LLM-Inferenz via llama-server
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # Config lesen (Temperature, Max-Tokens)
        ai_cfg = {}
        try:
            cfg_rows = db_query_rt("SELECT key, value FROM dbai_security.ai_config WHERE key IN ('analysis_temperature', 'analysis_max_tokens')")
            for r in cfg_rows:
                v = r["value"]
                if isinstance(v, str):
                    try: v = json.loads(v)
                    except: pass
                ai_cfg[r["key"]] = v
        except Exception as e:
            logger.debug("silent-exception: %s", e)

        temperature = float(ai_cfg.get("analysis_temperature", 0.2))
        max_tokens = int(ai_cfg.get("analysis_max_tokens", 2048))

        llm_result = _llm_chat_completion(messages, max_tokens=max_tokens, temperature=temperature)

        duration_ms = round((time.monotonic() - start_time) * 1000)

        if llm_result.get("error") and not llm_result.get("response"):
            db_execute_rt("""
                UPDATE dbai_security.ai_tasks
                SET state = 'failed', error_message = %s, completed_at = NOW(), processing_ms = %s
                WHERE id = %s::UUID
            """, (llm_result["error"], duration_ms, task_id))
            logger.error("[SECURITY-AI] Task %s fehlgeschlagen: %s", task_id[:8], llm_result["error"])
            return

        # 5. Response parsen
        ai_text = llm_result.get("response", "")
        parsed = _security_ai_parse_response(ai_text)
        tokens_used = llm_result.get("tokens_used", 0)

        # 6. Ergebnis in Task speichern
        db_execute_rt("""
            UPDATE dbai_security.ai_tasks
            SET state = 'completed',
                output_data = %s::JSONB,
                ai_assessment = %s,
                risk_level = %s,
                confidence = %s,
                recommended_actions = %s::JSONB,
                completed_at = NOW(),
                processing_ms = %s
            WHERE id = %s::UUID
        """, (
            json.dumps(parsed, default=str),
            ai_text,
            parsed.get("risk_level", "info"),
            parsed.get("confidence", 0.5),
            json.dumps(parsed.get("recommended_actions", []), default=str),
            duration_ms,
            task_id,
        ))

        # 7. Analysis-Log (Append-Only Audit-Trail)
        db_execute_rt("""
            INSERT INTO dbai_security.ai_analysis_log
                (task_id, analysis_type, input_summary, output_summary,
                 risk_level, tokens_used, model_name, duration_ms, metadata)
            VALUES (%s::UUID, %s, %s, %s, %s, %s, %s, %s, %s::JSONB)
        """, (
            task_id, task_type,
            json.dumps(input_data, default=str)[:500],
            ai_text[:1000],
            parsed.get("risk_level", "info"),
            tokens_used,
            _llm_model_name,
            duration_ms,
            json.dumps({"confidence": parsed.get("confidence", 0.5), "model": _llm_model_name}, default=str),
        ))

        # 8. Auto-Response bei kritischen Ergebnissen
        if parsed.get("risk_level") in ("critical", "high"):
            _security_ai_auto_response(task_id, task_type, input_data, parsed)

        logger.info(
            "[SECURITY-AI] ✅ Task %s abgeschlossen — %s, risk=%s, %dms, %d tokens (%s)",
            task_id[:8], task_type, parsed.get("risk_level"), duration_ms, tokens_used, _llm_model_name
        )

    except Exception as e:
        duration_ms = round((time.monotonic() - start_time) * 1000)
        try:
            db_execute_rt("""
                UPDATE dbai_security.ai_tasks
                SET state = 'failed', error_message = %s, completed_at = NOW(), processing_ms = %s
                WHERE id = %s::UUID
            """, (str(e), duration_ms, task_id))
        except Exception as e:
            logger.debug("silent-exception: %s", e)
        logger.error("[SECURITY-AI] Task %s Exception: %s", task_id[:8], e)

import re as _re

_TERMINAL_BLOCKED_PATTERNS = _re.compile(
    r'rm\s+(-\w*\s+)*-\w*[rR]\w*\s+/'   # rm -rf /
    r'|mkfs\b'                             # mkfs
    r'|dd\s+if='                           # dd if=
    r'|:\(\)\s*\{'                         # fork bomb
    r'|>\s*/dev/sd'                        # overwrite disk
    r'|chmod\s+(-\w+\s+)*0?777\s+/'       # chmod 777 /
    r'|curl\b.*\|\s*(ba)?sh'              # curl | sh
    r'|wget\b.*\|\s*(ba)?sh'             # wget | sh
    r'|sudo\s+rm\b'                        # sudo rm
    r'|>\s*/etc/'                           # overwrite system config
    r'|;\s*reboot\b|;\s*shutdown\b'        # reboot/shutdown chained
    r'|&&\s*reboot\b|&&\s*shutdown\b',
    _re.IGNORECASE
)

from bridge.migration_runner import MigrationRunner

from bridge.gs_updater import GhostUpdater

_migration_runner = MigrationRunner(DB_CONFIG)

_updater = GhostUpdater(DB_CONFIG)

import sys

sys.path.insert(0, str(DBAI_ROOT / "dev" / "qemu"))

_hw_simulator = None

def _get_hw_sim():
    """Lazy-Init des Hardware-Simulators."""
    global _hw_simulator
    if _hw_simulator is None:
        try:
            from hw_simulator import HardwareSimulator, HardwareProfile
            import json as _json
            profile = None
            profile_name = os.getenv("QEMU_PROFILE", "")
            profiles_path = DBAI_ROOT / "dev" / "qemu" / "profiles.json"
            if profile_name and profiles_path.exists():
                with open(profiles_path) as f:
                    profiles = _json.load(f)
                if profile_name in profiles.get("profiles", {}):
                    pdata = profiles["profiles"][profile_name]
                    profile = HardwareProfile(**{
                        k: v for k, v in pdata.items()
                        if k in HardwareProfile.__dataclass_fields__
                    })
            _hw_simulator = HardwareSimulator(profile)
            logger.info("Hardware-Simulator initialisiert (Profil: %s)",
                        profile_name or "default")
        except Exception as e:
            logger.warning("Hardware-Simulator nicht verfügbar: %s", e)
            raise HTTPException(503, f"Hardware-Simulator nicht verfügbar: {e}")
    return _hw_simulator

if os.getenv("DBAI_HW_SIMULATE", "false").lower() == "true":
    try:
        _sim = _get_hw_sim()
        _sim.start()
        logger.info("Hardware-Simulator automatisch gestartet")
    except Exception as e:
        logger.warning("Auto-Start des HW-Simulators fehlgeschlagen: %s", e)

class SimulatorAnomalyRequest(BaseModel):
    anomaly: str | None = None  # overtemp, disk_fail, mem_leak, cpu_spike, network_flood, None

class SimulatorProfileRequest(BaseModel):
    profile: str = "desktop"  # minimal, desktop, server, stress

async def workshop_create_custom_table(project_id: str, request: Request,
                                        session: dict = Depends(get_current_session)):
    """Neue Custom-Tabelle erstellen."""
    body = await request.json()
    name = body.get("table_name", "").strip()
    if not name:
        raise HTTPException(400, "Tabellenname fehlt")
    columns = body.get("columns", [])
    rows = db_query_rt("""
        INSERT INTO dbai_workshop.custom_tables (project_id, table_name, description, columns)
        VALUES (%s::UUID, %s, %s, %s::JSONB) RETURNING *
    """, (project_id, name, body.get("description", ""), json.dumps(columns)))
    return rows[0] if rows else {}

import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_browser_bg_tasks: dict = {}

def _browser_db_update(update_type: str, data: dict):
    """Callback für DB-Updates aus dem browser_agent."""
    task_id = data.get("task_id")
    if not task_id:
        return
    try:
        if update_type == "status":
            db_execute_rt(
                """UPDATE dbai_system.ghost_browser_tasks
                   SET status = %s, started_at = NOW(), progress = 5
                   WHERE id = %s::UUID""",
                (data.get("status", "running"), task_id)
            )
        elif update_type == "step":
            db_execute_rt(
                """INSERT INTO dbai_system.ghost_browser_steps
                   (task_id, step_number, action, selector, value, page_url,
                    page_title, screenshot_path, result_data, duration_ms,
                    success, error_message)
                   VALUES (%s::UUID, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)""",
                (task_id, data.get("step_number"), data.get("action"),
                 data.get("selector"), data.get("value"), data.get("page_url"),
                 data.get("page_title"), data.get("screenshot_path"),
                 json.dumps(data.get("result_data")) if data.get("result_data") else None,
                 data.get("duration_ms"), data.get("success", True),
                 data.get("error_message"))
            )
        elif update_type == "complete":
            db_execute_rt(
                """UPDATE dbai_system.ghost_browser_tasks
                   SET status = %s, progress = %s, result_summary = %s,
                       result_path = %s, result_data = %s::jsonb,
                       pages_visited = %s, screenshots = %s::jsonb,
                       steps_log = %s::jsonb, completed_at = NOW(),
                       error_message = %s
                   WHERE id = %s::UUID""",
                (data.get("status", "completed"), data.get("progress", 100),
                 data.get("result_summary"), data.get("result_path"),
                 json.dumps(data.get("result_data")) if data.get("result_data") else None,
                 data.get("pages_visited"),
                 json.dumps(data.get("screenshots")) if data.get("screenshots") else "[]",
                 json.dumps(data.get("steps_log")) if data.get("steps_log") else "[]",
                 data.get("error_message"),
                 task_id)
            )
    except Exception as e:
        logger.error("Browser DB update error: %s", e)


# ── Phase 3: Pydantic-Basismodell (dict-kompatible .get()-Semantik) ──
class GhostBaseModel(BaseModel):
    """BaseModel mit .get(key, default) — so bleibt body.get(...) in Routen
    unverändert funktionieren (Semantik: None → default, wie dict.get)."""
    def get(self, key: str, default=None):
        v = getattr(self, key, default)
        return default if v is None else v

class create_user_req(GhostBaseModel):
    """Request-Body für `create_user` (Phase 3: Pydantic statt dict)."""
    password: str = ''
    display_name: Optional[str] = None
    role: str = 'user'
    username: str = ''

class browser_import_req(GhostBaseModel):
    """Request-Body für `browser_import` (Phase 3: Pydantic statt dict)."""
    browser_type: str = ''
    profile_name: str = ''
    profile_path: str = ''

class browser_import_selective_req(GhostBaseModel):
    """Request-Body für `browser_import_selective` (Phase 3: Pydantic statt dict)."""
    data_types: Optional[str] = None
    browser_type: str = ''
    profile_name: str = ''
    profile_path: str = ''

class workspace_scan_req(GhostBaseModel):
    """Request-Body für `workspace_scan` (Phase 3: Pydantic statt dict)."""
    paths: Optional[str] = None

class workspace_open_file_req(GhostBaseModel):
    """Request-Body für `workspace_open_file` (Phase 3: Pydantic statt dict)."""
    path: str = ''

class rag_query_req(GhostBaseModel):
    """Request-Body für `rag_query` (Phase 3: Pydantic statt dict)."""
    query: Optional[str] = None
    question: str = ''

class rag_toggle_source_req(GhostBaseModel):
    """Request-Body für `rag_toggle_source` (Phase 3: Pydantic statt dict)."""
    enabled: bool = True

class rag_add_source_req(GhostBaseModel):
    """Request-Body für `rag_add_source` (Phase 3: Pydantic statt dict)."""
    source_name: str = ''
    source_type: str = 'file'
    source_path: str = ''

class usb_flash_req(GhostBaseModel):
    """Request-Body für `usb_flash` (Phase 3: Pydantic statt dict)."""
    device_path: str = ''
    image_path: str = ''
    method: str = 'dd'

class hotspot_create_req(GhostBaseModel):
    """Request-Body für `hotspot_create` (Phase 3: Pydantic statt dict)."""
    ssid: str = 'DBAI-Hotspot'
    password: str = ''

class hotspot_update_config_req(GhostBaseModel):
    """Request-Body für `hotspot_update_config` (Phase 3: Pydantic statt dict)."""
    ssid: Optional[str] = None
    password: Optional[str] = None
    channel: Optional[str] = None
    band: Optional[str] = None

class immutable_enable_req(GhostBaseModel):
    """Request-Body für `immutable_enable` (Phase 3: Pydantic statt dict)."""
    mode: str = 'off'

class immutable_create_snapshot_req(GhostBaseModel):
    """Request-Body für `immutable_create_snapshot` (Phase 3: Pydantic statt dict)."""
    label: Optional[str] = None

class terminal_exec_req(GhostBaseModel):
    """Request-Body für `terminal_exec` (Phase 3: Pydantic statt dict)."""
    cwd: Optional[str] = None
    command: str = ''

class ghost_browser_create_task_req(GhostBaseModel):
    """Request-Body für `ghost_browser_create_task` (Phase 3: Pydantic statt dict)."""
    task_type: str = 'research'
    target_url: Optional[str] = None
    sandbox_mode: bool = True
    output_format: str = 'markdown'
    max_pages: int = 10
    max_duration_s: int = 120
    prompt: str = ''

class ghost_browser_quick_task_req(GhostBaseModel):
    """Request-Body für `ghost_browser_quick_task` (Phase 3: Pydantic statt dict)."""
    task_type: str = 'research'
    target_url: Optional[str] = None
    output_format: str = 'markdown'
    max_pages: int = 8
    max_duration_s: int = 120
    prompt: str = ''

class remote_access_verify_pin_req(GhostBaseModel):
    """Request-Body für `remote_access_verify_pin` (Phase 3: Pydantic statt dict)."""
    pin: str = ''

class config_import_selective_req(GhostBaseModel):
    """Request-Body für `config_import_selective` (Phase 3: Pydantic statt dict)."""
    categories: Optional[str] = None

class anomaly_resolve_req(GhostBaseModel):
    """Request-Body für `anomaly_resolve` (Phase 3: Pydantic statt dict)."""
    resolution: str = 'Manuell gelöst'

class sandbox_launch_req(GhostBaseModel):
    """Request-Body für `sandbox_launch` (Phase 3: Pydantic statt dict)."""
    app_name: str = ''
    executable_path: str = ''
    profile_name: str = 'default'

class firewall_add_rule_req(GhostBaseModel):
    """Request-Body für `firewall_add_rule` (Phase 3: Pydantic statt dict)."""
    name: Optional[str] = None
    rule_name: str = ''
    chain: str = 'INPUT'
    action: str = 'DROP'
    protocol: Optional[str] = None
    source_ip: Optional[str] = None
    dest_ip: Optional[str] = None
    source_port: Optional[str] = None
    dest_port: Optional[str] = None
    description: Optional[str] = None
    priority: int = 100

class security_mitigate_vuln_req(GhostBaseModel):
    """Request-Body für `security_mitigate_vuln` (Phase 3: Pydantic statt dict)."""
    status: str = 'mitigated'

class security_ban_ip_req(GhostBaseModel):
    """Request-Body für `security_ban_ip` (Phase 3: Pydantic statt dict)."""
    ip: Optional[str] = None
    reason: str = 'Manueller Ban'
    hours: int = 24

class security_ai_analyze_req(GhostBaseModel):
    """Request-Body für `security_ai_analyze` (Phase 3: Pydantic statt dict)."""
    task_type: str = 'risk_scoring'
    input_data: Optional[str] = None

class security_ai_analyze_ip_req(GhostBaseModel):
    """Request-Body für `security_ai_analyze_ip` (Phase 3: Pydantic statt dict)."""
    ip: Optional[str] = None

class security_ai_config_update_req(GhostBaseModel):
    """Request-Body für `security_ai_config_update` (Phase 3: Pydantic statt dict)."""
    key: Optional[str] = None
    value: Optional[str] = None

class security_dns_sinkhole_add_req(GhostBaseModel):
    """Request-Body für `security_dns_sinkhole_add` (Phase 3: Pydantic statt dict)."""
    domain_pattern: Optional[str] = None
    reason: str = 'Manuell hinzugefügt'

class security_rate_limit_update_req(GhostBaseModel):
    """Request-Body für `security_rate_limit_update` (Phase 3: Pydantic statt dict)."""
    max_requests: Optional[str] = None
    window_seconds: Optional[str] = None

class security_ghost_swap_req(GhostBaseModel):
    """Request-Body für `security_ghost_swap` (Phase 3: Pydantic statt dict)."""
    model_name: Optional[str] = None
    reason: str = 'UI — Security-Modellwechsel'


__all__ = ['_fernet', 'ASSETS_DIR', 'BaseModel', 'Body', 'CORSMiddleware', 'ConnectionManager', 'DBAI_ROOT', 'DBPool', 'DB_CONFIG', 'DB_CONFIG_RUNTIME', 'Depends', 'FRONTEND_DIR', 'FastAPI', 'GhostQueryRequest', 'GhostSwapRequest', 'GhostUpdater', 'HTMLResponse', 'HTTPException', 'JSONResponse', 'LLMServerRequest', 'LoginRequest', 'MetricsStreamer', 'MigrationRunner', 'NodeCreate', 'NodeUpdate', 'NotifyBridge', 'Optional', 'Path', 'RealDictCursor', 'Request', 'SceneUpdate', 'ServiceInstallRequest', 'SimulatorAnomalyRequest', 'SimulatorProfileRequest', 'StaticFiles', 'WEB_HOST', 'WEB_PORT', 'WebSocket', 'WebSocketDisconnect', 'WindowUpdate', '_API_VERSION', '_COOKIE_SECURE', '_FERNET_KEY_PATH', '_IS_DEVELOPMENT', '_JSONFormatter', '_LINUX_GETTERS', '_RATE_LIMIT', '_RATE_MAX_ENTRIES', '_RATE_WINDOW', '_SECURITY_TASK_PROMPTS', '_SERVICE_COMMANDS', '_TERMINAL_BLOCKED_PATTERNS', '_browser_bg_tasks', '_browser_db_update', '_calc_gpu_optimal', '_check_gpu_available', '_classify_exception', '_collect_mounts', '_cors_origins', '_cors_os', '_cuda_lib_paths', '_detect_gpu_arch', '_detect_llm_host', '_do_network_scan', '_download_tasks', '_estimate_gpu_bandwidth', '_estimate_layers', '_existing', '_get_hw_sim', '_host_ip', '_hw_simulator', '_linux_accessibility', '_linux_bluetooth', '_linux_datetime', '_linux_display', '_linux_keyboard', '_linux_mouse', '_linux_notifications', '_linux_power', '_linux_printers', '_linux_security', '_linux_sound', '_linux_storage', '_linux_updates', '_linux_users', '_llm_chat_completion', '_llm_host_ip', '_llm_lock', '_llm_model_name', '_llm_model_path', '_llm_op_lock', '_llm_server_bin', '_llm_server_ctx_size', '_llm_server_device', '_llm_server_gpu_layers', '_llm_server_health', '_llm_server_port', '_llm_server_process', '_llm_server_start', '_llm_server_stop', '_llm_server_threads', '_llm_server_url', '_llm_watchdog_loop', '_load_or_create_fernet_key', '_migration_runner', '_rate_limit_last_cleanup', '_rate_limit_store', '_re', '_re_mod', '_recommend_models_for_gpu', '_run_cmd', '_security_ai_auto_response', '_security_ai_build_context', '_security_ai_build_prompt', '_security_ai_parse_response', '_security_ai_process_task', '_sp', '_tb_mod', '_updater', '_use_json_logs', '_validate_body', '_watchdog_fallback_active', '_watchdog_restart_count', '_watchdog_running', '_workshop_fallback_response', 'adb_call_json', 'adb_call_json_rt', 'adb_execute', 'adb_execute_rt', 'adb_query', 'adb_query_rt', 'api_version_middleware', 'app', 'asynccontextmanager', 'asyncio', 'catch_all_exceptions_middleware', 'csrf_middleware', 'ctypes', 'datetime', 'db_call_json', 'db_call_json_rt', 'db_execute', 'db_execute_rt', 'db_pool', 'db_pool_runtime', 'db_query', 'db_query_rt', 'decrypt_secret', 'defaultdict', 'encrypt_secret', 'get_current_session', 'guess_device_type', 'json', 'lifespan', 'logger', 'logging', 'metrics_streamer', 'notify_bridge', 'os', 'psycopg2', 'rate_limit_middleware', 'require_admin', 'signal', 'sys', 'threading', 'time', 'timezone', 'urllib', 'workshop_create_custom_table', 'workshop_search', 'ws_manager', 'create_user_req', 'browser_import_req', 'browser_import_selective_req', 'workspace_scan_req', 'workspace_open_file_req', 'rag_query_req', 'rag_toggle_source_req', 'rag_add_source_req', 'usb_flash_req', 'hotspot_create_req', 'hotspot_update_config_req', 'immutable_enable_req', 'immutable_create_snapshot_req', 'terminal_exec_req', 'ghost_browser_create_task_req', 'ghost_browser_quick_task_req', 'remote_access_verify_pin_req', 'config_import_selective_req', 'anomaly_resolve_req', 'sandbox_launch_req', 'firewall_add_rule_req', 'security_mitigate_vuln_req', 'security_ban_ip_req', 'security_ai_analyze_req', 'security_ai_analyze_ip_req', 'security_ai_config_update_req', 'security_dns_sinkhole_add_req', 'security_rate_limit_update_req', 'security_ghost_swap_req', 'GhostBaseModel']
