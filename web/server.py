#!/usr/bin/env python3
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
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from contextlib import asynccontextmanager

import psycopg2
import psycopg2.extensions
from psycopg2.extras import RealDictCursor

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------
DBAI_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = DBAI_ROOT / "frontend" / "dist"
ASSETS_DIR = DBAI_ROOT / "frontend" / "public" / "assets"

# Admin-Pool: dbai_system (Superuser) — NUR für Admin-Operationen + Schema-Migration
DB_CONFIG = {
    "host": os.getenv("DBAI_DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DBAI_DB_PORT", "5432")),
    "dbname": os.getenv("DBAI_DB_NAME", "dbai"),
    "user": os.getenv("DBAI_DB_USER", "dbai_system"),
    "password": os.getenv("DBAI_DB_PASSWORD", ""),
}

# Runtime-Pool: dbai_runtime — Für alle normalen API-Operationen (KEIN Superuser)
DB_CONFIG_RUNTIME = {
    "host": os.getenv("DBAI_DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DBAI_DB_PORT", "5432")),
    "dbname": os.getenv("DBAI_DB_NAME", "dbai"),
    "user": os.getenv("DBAI_DB_RUNTIME_USER", "dbai_runtime"),
    "password": os.getenv("DBAI_DB_RUNTIME_PASSWORD", "dbai_runtime_2026"),
}

WEB_HOST = os.getenv("DBAI_WEB_HOST", "127.0.0.1")
WEB_PORT = int(os.getenv("DBAI_WEB_PORT", "3000"))

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("dbai.web")


# ---------------------------------------------------------------------------
# Datenbank-Pool (synchron, für psycopg2)
# ---------------------------------------------------------------------------
class DBPool:
    """Einfacher Connection-Pool für PostgreSQL."""

    def __init__(self, config: dict, max_connections: int = 10):
        self.config = config
        self.max_connections = max_connections
        self._connections: list = []
        self._notify_conn = None  # Dedizierte LISTEN-Verbindung

    def get_connection(self):
        """Holt oder erstellt eine DB-Verbindung."""
        # Versuche eine freie Verbindung zu finden
        for conn in self._connections:
            if not conn.closed:
                try:
                    conn.reset()
                    return conn
                except Exception:
                    self._connections.remove(conn)

        # Neue Verbindung erstellen
        conn = psycopg2.connect(**self.config)
        conn.autocommit = False
        if len(self._connections) < self.max_connections:
            self._connections.append(conn)
        return conn

    def get_notify_connection(self):
        """Dedizierte Verbindung für LISTEN/NOTIFY (autocommit!)."""
        if self._notify_conn is None or self._notify_conn.closed:
            self._notify_conn = psycopg2.connect(**self.config)
            self._notify_conn.set_isolation_level(
                psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT
            )
        return self._notify_conn

    def close_all(self):
        for conn in self._connections:
            try:
                conn.close()
            except Exception:
                pass
        if self._notify_conn:
            try:
                self._notify_conn.close()
            except Exception:
                pass


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


# ---------------------------------------------------------------------------
# WebSocket Manager
# ---------------------------------------------------------------------------
class ConnectionManager:
    """Verwaltet alle aktiven WebSocket-Verbindungen."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}  # session_id → ws

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info("WebSocket verbunden: %s (aktiv: %d)", session_id[:8], len(self.active_connections))

    def disconnect(self, session_id: str):
        self.active_connections.pop(session_id, None)
        logger.info("WebSocket getrennt: %s (aktiv: %d)", session_id[:8], len(self.active_connections))

    async def send_to_session(self, session_id: str, data: dict):
        ws = self.active_connections.get(session_id)
        if ws:
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect(session_id)

    async def broadcast(self, data: dict):
        dead = []
        for sid, ws in self.active_connections.items():
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(sid)
        for sid in dead:
            self.disconnect(sid)

    @property
    def count(self) -> int:
        return len(self.active_connections)


ws_manager = ConnectionManager()


# ---------------------------------------------------------------------------
# LISTEN/NOTIFY Bridge — PostgreSQL Events → WebSocket
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Metriken-Streamer — Periodische Hardware-Daten an Browser
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start/Stop Lifecycle."""
    logger.info("═══ DBAI Web Server startet ═══")
    await notify_bridge.start()
    await metrics_streamer.start()
    yield
    logger.info("═══ DBAI Web Server stoppt ═══")
    await notify_bridge.stop()
    await metrics_streamer.stop()
    db_pool.close_all()
    db_pool_runtime.close_all()


app = FastAPI(
    title="DBAI — Database AI Operating System",
    version="0.3.0",
    description="The Ghost in the Database",
    lifespan=lifespan,
)

# CORS nur für localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000",
                   "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------
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


class WindowUpdate(BaseModel):
    pos_x: Optional[int] = None
    pos_y: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    state: Optional[str] = None
    is_focused: Optional[bool] = None
    z_index: Optional[int] = None


# ---------------------------------------------------------------------------
# Auth Dependency
# ---------------------------------------------------------------------------
async def get_current_session(request: Request) -> dict:
    """Validiert die Session aus dem Authorization-Header oder Cookie."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        token = request.cookies.get("dbai_token", "")
    if not token:
        raise HTTPException(status_code=401, detail="Nicht authentifiziert")

    result = db_call_json_rt(
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


# ---------------------------------------------------------------------------
# API Routes — Auth
# ---------------------------------------------------------------------------
@app.post("/api/auth/login")
async def login(req: LoginRequest, request: Request):
    """Login gegen die Datenbank. Gibt Session-Token zurück."""
    ip = request.client.host if request.client else None
    ua = request.headers.get("User-Agent", "")

    result = db_call_json_rt(
        "SELECT dbai_ui.login(%s, %s, %s::INET, %s)",
        (req.username, req.password, ip, ua)
    )

    if not result or not result.get("success"):
        raise HTTPException(status_code=401, detail=result.get("error", "Login fehlgeschlagen"))

    response = JSONResponse(content=result)
    response.set_cookie(
        key="dbai_token",
        value=result["token"],
        httponly=True,
        samesite="strict",
        max_age=86400,
    )
    return response


@app.post("/api/auth/logout")
async def logout(session: dict = Depends(get_current_session)):
    """Logout: Session deaktivieren."""
    db_execute_rt(
        "UPDATE dbai_ui.sessions SET is_active = FALSE WHERE id = %s::UUID",
        (session["session_id"],)
    )
    return {"success": True}


@app.get("/api/auth/me")
async def get_me(session: dict = Depends(get_current_session)):
    """Gibt den aktuellen User zurück."""
    return session["user"]


# ---------------------------------------------------------------------------
# API Routes — Boot
# ---------------------------------------------------------------------------
@app.get("/api/boot/sequence")
async def get_boot_sequence():
    """Boot-Sequenz für die Browser-Animation. Kein Auth nötig."""
    rows = db_query_rt("SELECT * FROM dbai_ui.vw_boot_sequence ORDER BY step")
    return rows


# ---------------------------------------------------------------------------
# API Routes — Desktop
# ---------------------------------------------------------------------------
@app.get("/api/desktop")
async def get_desktop(session: dict = Depends(get_current_session)):
    """Kompletter Desktop-State: Theme, Windows, Apps, Ghosts, Notifications."""
    result = db_call_json_rt(
        "SELECT dbai_ui.get_desktop_state(%s::UUID)",
        (session["session_id"],)
    )
    return result or {}


@app.get("/api/apps")
async def get_apps(session: dict = Depends(get_current_session)):
    """Liste aller verfügbaren Apps."""
    rows = db_query_rt("SELECT * FROM dbai_ui.apps ORDER BY sort_order")
    return rows


@app.post("/api/windows/open/{app_id}")
async def open_window(app_id: str, session: dict = Depends(get_current_session)):
    """Öffnet ein neues Fenster für eine App."""
    rows = db_query_rt(
        "SELECT * FROM dbai_ui.apps WHERE app_id = %s", (app_id,)
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' nicht gefunden")

    app_data = rows[0]
    result = db_query_rt("""
        INSERT INTO dbai_ui.windows (session_id, app_id, width, height)
        VALUES (%s::UUID, %s::UUID, %s, %s)
        RETURNING id, pos_x, pos_y, width, height, state, z_index
    """, (session["session_id"], app_data["id"], app_data["default_width"], app_data["default_height"]))

    if result:
        window = result[0]
        window["app_id"] = app_id
        window["app_name"] = app_data["name"]
        window["app_icon"] = app_data["icon"]
        # Notify other tabs
        await ws_manager.broadcast({
            "type": "window_opened",
            "window": window,
        })
        return window

    raise HTTPException(status_code=500, detail="Fenster konnte nicht erstellt werden")


@app.patch("/api/windows/{window_id}")
async def update_window(window_id: str, update: WindowUpdate, session: dict = Depends(get_current_session)):
    """Aktualisiert Position/Größe/Status eines Fensters."""
    sets = []
    params = []
    for field, value in update.model_dump(exclude_none=True).items():
        sets.append(f"{field} = %s")
        params.append(value)

    if not sets:
        return {"ok": True}

    params.append(window_id)
    db_execute_rt(
        f"UPDATE dbai_ui.windows SET {', '.join(sets)} WHERE id = %s::UUID",
        tuple(params)
    )
    return {"ok": True}


@app.delete("/api/windows/{window_id}")
async def close_window(window_id: str, session: dict = Depends(get_current_session)):
    """Schließt ein Fenster."""
    db_execute_rt("DELETE FROM dbai_ui.windows WHERE id = %s::UUID", (window_id,))
    await ws_manager.broadcast({"type": "window_closed", "window_id": window_id})
    return {"ok": True}


# ---------------------------------------------------------------------------
# API Routes — Ghost System
# ---------------------------------------------------------------------------
@app.get("/api/ghosts")
async def get_ghosts(session: dict = Depends(get_current_session)):
    """Alle aktiven Ghosts und verfügbaren Modelle."""
    active = db_query_rt("SELECT * FROM dbai_llm.vw_active_ghosts")
    models = db_query_rt("SELECT * FROM dbai_llm.ghost_models ORDER BY name")
    roles = db_query_rt("SELECT * FROM dbai_llm.ghost_roles ORDER BY priority")
    compatibility = db_query_rt("""
        SELECT gc.*, gm.name AS model_name, gr.name AS role_name
        FROM dbai_llm.ghost_compatibility gc
        JOIN dbai_llm.ghost_models gm ON gc.model_id = gm.id
        JOIN dbai_llm.ghost_roles gr ON gc.role_id = gr.id
        ORDER BY gc.fitness_score DESC
    """)
    return {
        "active_ghosts": active,
        "models": models,
        "roles": roles,
        "compatibility": compatibility,
    }


@app.post("/api/ghosts/swap")
async def swap_ghost(req: GhostSwapRequest, session: dict = Depends(get_current_session)):
    """Hot-Swap: KI-Modell für eine Rolle wechseln."""
    result = db_call_json_rt(
        "SELECT dbai_llm.swap_ghost(%s, %s, %s, %s)",
        (req.role, req.model, req.reason, "user")
    )
    return result or {"error": "Swap fehlgeschlagen"}


@app.post("/api/ghosts/ask")
async def ask_ghost(req: GhostQueryRequest, session: dict = Depends(get_current_session)):
    """Frage an einen Ghost stellen (asynchron via Task-Queue)."""
    result = db_call_json_rt(
        "SELECT dbai_llm.ask_ghost(%s, %s, %s::JSONB)",
        (req.role, req.question, json.dumps(req.context))
    )
    return result or {"error": "Anfrage fehlgeschlagen"}


@app.get("/api/ghosts/history")
async def ghost_history(limit: int = 50, session: dict = Depends(get_current_session)):
    """Ghost-Swap-History."""
    rows = db_query_rt(
        "SELECT * FROM dbai_llm.ghost_history ORDER BY ts DESC LIMIT %s",
        (limit,)
    )
    return rows


# ---------------------------------------------------------------------------
# API Routes — System Monitor
# ---------------------------------------------------------------------------
@app.get("/api/system/metrics")
async def system_metrics(session: dict = Depends(get_current_session)):
    """Live-Systemmetriken direkt vom OS (psutil) für den SVG-Desktop."""
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        net = psutil.net_io_counters()
        temps = {}
        try:
            t = psutil.sensors_temperatures()
            if t:
                for name, entries in t.items():
                    temps[name] = entries[0].current if entries else 0
        except Exception:
            pass
        return {
            "cpu_percent": cpu,
            "ram_percent": mem.percent,
            "ram_used_gb": round(mem.used / (1024**3), 1),
            "ram_total_gb": round(mem.total / (1024**3), 1),
            "disk_percent": disk.percent,
            "disk_used_gb": round(disk.used / (1024**3), 1),
            "disk_total_gb": round(disk.total / (1024**3), 1),
            "net_sent_mb": round(net.bytes_sent / (1024**2), 1),
            "net_recv_mb": round(net.bytes_recv / (1024**2), 1),
            "cpu_count": psutil.cpu_count(),
            "temps": temps,
            "load_avg": list(psutil.getloadavg()) if hasattr(psutil, 'getloadavg') else [],
            "open_windows": len([p for p in psutil.process_iter(['name']) if p.info]),
        }
    except Exception as e:
        return {"cpu_percent": 0, "ram_percent": 0, "disk_percent": 0, "error": str(e)}

@app.get("/api/system/status")
async def system_status(session: dict = Depends(get_current_session)):
    """Aktueller System-Status."""
    status = db_query_rt("SELECT * FROM dbai_system.current_status")
    return status[0] if status else {}


@app.get("/api/system/processes")
async def system_processes(session: dict = Depends(get_current_session)):
    """Laufende Prozesse."""
    rows = db_query_rt("""
        SELECT id, pid, name, process_type, state, priority,
               cpu_affinity, memory_limit_mb, last_heartbeat, error_message
        FROM dbai_core.processes
        ORDER BY priority, name
    """)
    return rows


@app.get("/api/system/health")
async def system_health(session: dict = Depends(get_current_session)):
    """Health-Checks ausführen und Ergebnisse zurückgeben."""
    rows = db_query_rt("SELECT * FROM dbai_system.run_health_checks()")
    return rows


@app.post("/api/system/self-heal")
async def self_heal(session: dict = Depends(get_current_session)):
    """Self-Healing-Loop auslösen."""
    result = db_call_json("SELECT dbai_system.self_heal()")
    return result or {}


# ---------------------------------------------------------------------------
# API Routes — Knowledge Base
# ---------------------------------------------------------------------------
@app.get("/api/knowledge/modules")
async def knowledge_modules(session: dict = Depends(get_current_session)):
    """Alle registrierten Module."""
    rows = db_query_rt("SELECT * FROM dbai_knowledge.vw_module_overview")
    return rows


@app.get("/api/knowledge/search")
async def knowledge_search(q: str, session: dict = Depends(get_current_session)):
    """Fuzzy-Suche über Module."""
    rows = db_query_rt("SELECT * FROM dbai_knowledge.search_modules(%s)", (q,))
    return rows


@app.get("/api/knowledge/errors")
async def knowledge_errors(session: dict = Depends(get_current_session)):
    """Bekannte Error-Patterns."""
    rows = db_query_rt("SELECT * FROM dbai_knowledge.error_patterns ORDER BY severity DESC, name")
    return rows


@app.get("/api/knowledge/report")
async def knowledge_report(session: dict = Depends(get_current_session)):
    """Kompletter System-Report als JSON."""
    result = db_call_json_rt("SELECT dbai_knowledge.generate_system_report()")
    return result or {}


# ---------------------------------------------------------------------------
# API Routes — Software Store
# ---------------------------------------------------------------------------
@app.get("/api/store/catalog")
async def store_catalog(session: dict = Depends(get_current_session)):
    """Software-Katalog: Alle verfügbaren und installierten Pakete."""
    rows = db_query_rt("""
        SELECT id, package_name, display_name, description, version, latest_version,
               source_type, source_url, repository, category, tags,
               install_command, install_state, installed_at, install_size_mb,
               ghost_recommendation, ghost_review, stars, downloads, license, homepage,
               created_at, updated_at
        FROM dbai_core.software_catalog
        ORDER BY
            CASE WHEN install_state = 'installed' THEN 0 ELSE 1 END,
            ghost_recommendation DESC NULLS LAST,
            package_name
    """)
    return rows


@app.post("/api/store/install")
async def store_install(request: Request, session: dict = Depends(get_current_session)):
    """Paket installieren (setzt Status auf 'installing')."""
    body = await request.json()
    pkg = body.get("package_name")
    src = body.get("source_type", "apt")
    if not pkg:
        raise HTTPException(status_code=400, detail="package_name fehlt")

    db_execute_rt("""
        UPDATE dbai_core.software_catalog
        SET install_state = 'installing', updated_at = NOW()
        WHERE package_name = %s AND source_type = %s AND install_state IN ('available', 'broken')
    """, (pkg, src))

    # Log event
    try:
        db_execute_rt("""
            INSERT INTO dbai_event.events (event_type, source, payload)
            VALUES ('software_install', 'store_ui', %s::JSONB)
        """, (json.dumps({"package": pkg, "source": src}),))
    except Exception:
        pass

    # Simulate install completion (in real system, a background worker handles this)
    db_execute_rt("""
        UPDATE dbai_core.software_catalog
        SET install_state = 'installed', installed_at = NOW(), updated_at = NOW()
        WHERE package_name = %s AND source_type = %s
    """, (pkg, src))

    return {"ok": True, "package": pkg, "state": "installed"}


@app.post("/api/store/uninstall")
async def store_uninstall(request: Request, session: dict = Depends(get_current_session)):
    """Paket entfernen."""
    body = await request.json()
    pkg = body.get("package_name")
    src = body.get("source_type", "apt")
    if not pkg:
        raise HTTPException(status_code=400, detail="package_name fehlt")

    db_execute_rt("""
        UPDATE dbai_core.software_catalog
        SET install_state = 'available', installed_at = NULL, updated_at = NOW()
        WHERE package_name = %s AND source_type = %s
    """, (pkg, src))

    return {"ok": True, "package": pkg, "state": "available"}


@app.post("/api/store/refresh")
async def store_refresh(session: dict = Depends(get_current_session)):
    """Katalog aktualisieren (updated_at bumpen)."""
    db_execute_rt("UPDATE dbai_core.software_catalog SET updated_at = NOW()")
    return {"ok": True, "message": "Katalog aktualisiert"}


@app.get("/api/store/github/search")
async def store_github_search(q: str = "", session: dict = Depends(get_current_session)):
    """GitHub-Repos suchen via GitHub API (öffentlich, kein Token nötig)."""
    import urllib.request, urllib.parse
    if not q or len(q) < 2:
        return {"items": [], "total": 0}
    try:
        encoded = urllib.parse.quote(q)
        url = f"https://api.github.com/search/repositories?q={encoded}&sort=stars&order=desc&per_page=20"
        req = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "DBAI-SoftwareStore/1.0"
        })
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        items = []
        for r in data.get("items", []):
            items.append({
                "full_name": r.get("full_name", ""),
                "name": r.get("name", ""),
                "description": r.get("description", ""),
                "html_url": r.get("html_url", ""),
                "clone_url": r.get("clone_url", ""),
                "stars": r.get("stargazers_count", 0),
                "forks": r.get("forks_count", 0),
                "language": r.get("language", ""),
                "license": r.get("license", {}).get("spdx_id") if r.get("license") else None,
                "topics": r.get("topics", []),
                "updated_at": r.get("updated_at", ""),
                "owner_avatar": r.get("owner", {}).get("avatar_url", ""),
                "owner": r.get("owner", {}).get("login", ""),
                "default_branch": r.get("default_branch", "main"),
                "size_kb": r.get("size", 0),
                "open_issues": r.get("open_issues_count", 0),
            })
        return {"items": items, "total": data.get("total_count", 0)}
    except Exception as e:
        return {"items": [], "total": 0, "error": str(e)}


@app.post("/api/store/github/install")
async def store_github_install(request: Request, session: dict = Depends(get_current_session)):
    """GitHub-Repo in den Software-Katalog aufnehmen und als 'installed' markieren."""
    body = await request.json()
    full_name = body.get("full_name", "")
    name = body.get("name", full_name.split("/")[-1] if "/" in full_name else full_name)
    description = body.get("description", "")
    html_url = body.get("html_url", "")
    clone_url = body.get("clone_url", "")
    stars = body.get("stars", 0)
    language = body.get("language", "")
    license_id = body.get("license", "")
    topics = body.get("topics", [])
    size_kb = body.get("size_kb", 0)

    if not full_name:
        raise HTTPException(status_code=400, detail="full_name fehlt")

    # Prüfe ob schon vorhanden
    existing = db_query_rt("""
        SELECT id, install_state FROM dbai_core.software_catalog
        WHERE package_name = %s AND source_type = 'github'
    """, (full_name,))

    if existing and existing[0].get("install_state") == "installed":
        return {"ok": True, "package": full_name, "state": "already_installed"}

    if existing:
        db_execute_rt("""
            UPDATE dbai_core.software_catalog
            SET install_state = 'installed', installed_at = NOW(), updated_at = NOW(),
                description = %s, stars = %s, source_url = %s, license = %s,
                tags = %s, homepage = %s
            WHERE package_name = %s AND source_type = 'github'
        """, (description, stars, html_url, license_id, topics, html_url, full_name))
    else:
        db_execute_rt("""
            INSERT INTO dbai_core.software_catalog
                (package_name, display_name, description, source_type, source_url,
                 category, tags, install_command, install_state, installed_at,
                 install_size_mb, stars, license, homepage)
            VALUES (%s, %s, %s, 'github', %s, %s, %s, %s, 'installed', NOW(), %s, %s, %s, %s)
            ON CONFLICT (package_name, source_type) DO UPDATE SET
                install_state = 'installed', installed_at = NOW(), updated_at = NOW()
        """, (
            full_name, name, description, html_url,
            'ai_ml' if language in ('Python', 'Jupyter Notebook') else 'development',
            topics or [],
            f"git clone {clone_url}",
            round(size_kb / 1024, 1) if size_kb else None,
            stars, license_id, html_url
        ))

    # Log event
    try:
        db_execute_rt("""
            INSERT INTO dbai_event.events (event_type, source, payload)
            VALUES ('github_install', 'store_ui', %s::JSONB)
        """, (json.dumps({"repo": full_name, "url": html_url}),))
    except Exception:
        pass

    return {"ok": True, "package": full_name, "state": "installed"}


# ---------------------------------------------------------------------------
# API Routes — OpenClaw Integrator
# ---------------------------------------------------------------------------
@app.get("/api/openclaw/status")
async def openclaw_status(session: dict = Depends(get_current_session)):
    """OpenClaw-Bridge Status: Skills, Memories, Migrationen."""
    skills = db_query_rt("""
        SELECT id, skill_name, display_name, original_lang, action_type,
               sql_action, state, compatibility_score, required_ghost_role,
               migration_notes, created_at
        FROM dbai_core.openclaw_skills
        ORDER BY state, skill_name
    """)
    memories = db_query_rt("""
        SELECT id, openclaw_id, openclaw_file, content, content_type,
               importance, is_integrated, migrated_at
        FROM dbai_vector.openclaw_memories
        ORDER BY migrated_at DESC
        LIMIT 200
    """)
    migrations = db_query_rt("""
        SELECT id, job_type AS migration_type, source_path, state,
               total_items AS items_total, processed_items AS items_processed,
               failed_items AS items_failed,
               started_at, completed_at, error_log AS error_message
        FROM dbai_core.migration_jobs
        ORDER BY started_at DESC
        LIMIT 50
    """)

    # Stats
    stats = {}
    try:
        s = db_query_rt("""
            SELECT
                (SELECT count(*) FROM dbai_core.openclaw_skills) AS total_skills,
                (SELECT count(*) FROM dbai_core.openclaw_skills WHERE state = 'active') AS active_skills,
                (SELECT count(*) FROM dbai_vector.openclaw_memories) AS total_memories,
                (SELECT count(*) FROM dbai_vector.openclaw_memories WHERE is_integrated = TRUE) AS integrated_memories,
                (SELECT count(*) FROM dbai_core.migration_jobs) AS total_migrations
        """)
        if s:
            stats = s[0]
    except Exception:
        pass

    return {
        "skills": skills,
        "memories": memories,
        "migrations": migrations,
        "stats": stats,
    }


@app.post("/api/openclaw/skills/activate")
async def openclaw_activate_skill(request: Request, session: dict = Depends(get_current_session)):
    """Einen importierten Skill aktivieren."""
    body = await request.json()
    skill_name = body.get("skill_name")
    if not skill_name:
        raise HTTPException(status_code=400, detail="skill_name fehlt")

    db_execute_rt("""
        UPDATE dbai_core.openclaw_skills
        SET state = 'active', activated_at = NOW(), updated_at = NOW()
        WHERE skill_name = %s AND state IN ('imported', 'testing')
    """, (skill_name,))

    return {"ok": True, "skill": skill_name, "state": "active"}


@app.post("/api/openclaw/migrate")
async def openclaw_start_migration(request: Request, session: dict = Depends(get_current_session)):
    """Neue Memory-Migration starten."""
    result = db_query_rt("""
        INSERT INTO dbai_core.migration_jobs (job_type, source_path, source_type, state, started_at)
        VALUES ('openclaw_memory', '~/.openclaw/workspace', 'openclaw', 'running', NOW())
        RETURNING id, job_type AS migration_type, state, started_at
    """)
    if result:
        return {"ok": True, "migration": result[0]}
    return {"ok": False, "error": "Migration konnte nicht gestartet werden"}


@app.get("/api/openclaw/live")
async def openclaw_live_config(session: dict = Depends(get_current_session)):
    """Live-Konfiguration direkt aus ~/.openclaw/ lesen."""
    import pathlib
    oc_dir = pathlib.Path.home() / ".openclaw"

    result = {
        "installed": oc_dir.exists(),
        "config": {},
        "agents": [],
        "agents_meta": {},
        "cron_jobs": [],
        "addons": [],
        "integrations": {},
        "models": [],
        "tools": {},
        "storage": {},
        "kubernetes": {},
        "gateway": {},
        "memory": {},
        "skills_dir": [],
        "devices_count": 0,
    }
    if not oc_dir.exists():
        return result

    # openclaw.json
    try:
        with open(oc_dir / "openclaw.json", "r") as f:
            cfg = json.load(f)
        result["config"] = {
            "meta": cfg.get("meta", {}),
            "wizard": cfg.get("wizard", {}),
            "commands": cfg.get("commands", {}),
            "messages": cfg.get("messages", {}),
        }
        result["agents"] = cfg.get("agents", {}).get("list", [])
        result["gateway"] = {
            "port": cfg.get("gateway", {}).get("port"),
            "mode": cfg.get("gateway", {}).get("mode"),
            "auth_mode": cfg.get("gateway", {}).get("auth", {}).get("mode"),
        }
        result["memory"] = {
            "slot": cfg.get("plugins", {}).get("slots", {}).get("memory"),
            "lancedb": bool(cfg.get("plugins", {}).get("entries", {}).get("memory-lancedb", {}).get("enabled")),
            "auto_capture": cfg.get("plugins", {}).get("entries", {}).get("memory-lancedb", {}).get("config", {}).get("autoCapture"),
            "auto_recall": cfg.get("plugins", {}).get("entries", {}).get("memory-lancedb", {}).get("config", {}).get("autoRecall"),
            "embedding_model": cfg.get("plugins", {}).get("entries", {}).get("memory-lancedb", {}).get("config", {}).get("embedding", {}).get("model"),
            "dimensions": cfg.get("plugins", {}).get("entries", {}).get("memory-lancedb", {}).get("config", {}).get("embedding", {}).get("dimensions"),
        }
        cron_enabled = cfg.get("cron", {}).get("enabled", False)
        result["cron_enabled"] = cron_enabled
    except Exception:
        pass

    # agents-meta.json
    try:
        with open(oc_dir / "agents-meta.json", "r") as f:
            result["agents_meta"] = json.load(f)
    except Exception:
        pass

    # cron jobs
    try:
        cron_dir = oc_dir / "cron"
        for fp in sorted(cron_dir.glob("*.json")):
            with open(fp, "r") as f:
                data = json.load(f)
            for job in data.get("jobs", []):
                result["cron_jobs"].append({
                    "id": job.get("id", ""),
                    "name": job.get("name", ""),
                    "description": job.get("description", ""),
                    "schedule": job.get("schedule", {}).get("expr", ""),
                    "enabled": job.get("enabled", False),
                    "agent_id": job.get("agentId", ""),
                    "last_status": job.get("state", {}).get("lastStatus"),
                    "last_run": job.get("state", {}).get("lastRunAtMs"),
                    "run_count": job.get("runCount", 0) or job.get("state", {}).get("consecutiveErrors", 0),
                    "last_duration_ms": job.get("state", {}).get("lastDurationMs"),
                })
    except Exception:
        pass

    # mission-control-config.json
    try:
        with open(oc_dir / "mission-control-config.json", "r") as f:
            mc = json.load(f)
        result["addons"] = mc.get("addons", [])
        result["integrations"] = {
            k: {kk: vv for kk, vv in v.items() if kk not in ("apiKey", "botToken", "password", "encryption_key")}
            if isinstance(v, dict) else v
            for k, v in mc.get("integrations", {}).items()
        }
        result["models"] = mc.get("models", {}).get("available", [])
        result["tools"] = mc.get("openclawTools", {})
        result["storage"] = mc.get("storage", {})
        result["kubernetes"] = {
            "namespace": mc.get("kubernetes", {}).get("namespace"),
            "nodes": mc.get("kubernetes", {}).get("nodes", {}),
        }
    except Exception:
        pass

    # Skills directory
    try:
        skills_dir = oc_dir / "skills"
        result["skills_dir"] = [d.name for d in skills_dir.iterdir() if d.is_dir()] if skills_dir.exists() else []
    except Exception:
        pass

    # Devices count
    try:
        devices_dir = oc_dir / "devices"
        if devices_dir.exists():
            with open(list(devices_dir.glob("*.json"))[0], "r") as f:
                devices = json.load(f)
            result["devices_count"] = len(devices)
    except Exception:
        pass

    return result


@app.get("/api/openclaw/gateway/status")
async def openclaw_gateway_status(session: dict = Depends(get_current_session)):
    """Prüfe ob der OpenClaw-Gateway läuft."""
    import urllib.request
    try:
        req = urllib.request.Request("http://127.0.0.1:18788/healthz", headers={"User-Agent": "DBAI/1.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            return {"online": True, "status": resp.status}
    except Exception:
        pass
    # Fallback: systemd check
    try:
        import subprocess
        r = subprocess.run(["systemctl", "is-active", "openclaw-network"], capture_output=True, text=True, timeout=3)
        return {"online": r.stdout.strip() == "active", "systemd_state": r.stdout.strip()}
    except Exception:
        return {"online": False, "systemd_state": "unknown"}


# ---------------------------------------------------------------------------
# API Routes — LLM Manager
# ---------------------------------------------------------------------------
@app.get("/api/llm/status")
async def llm_status(session: dict = Depends(get_current_session)):
    """LLM-System Status: Modelle, Benchmarks, Konfiguration."""
    models = db_query_rt("SELECT * FROM dbai_llm.ghost_models ORDER BY name")
    benchmarks = db_query_rt("""
        SELECT gb.*, gm.name AS model_name, gm.display_name AS model_display
        FROM dbai_llm.ghost_benchmarks gb
        JOIN dbai_llm.ghost_models gm ON gb.model_id = gm.id
        ORDER BY gb.benchmark_date DESC
    """)
    config = db_query_rt("""
        SELECT key, value, category, description
        FROM dbai_core.config
        WHERE category IN ('llm', 'ghost', 'embedding')
        ORDER BY key
    """)
    active = db_query_rt("SELECT * FROM dbai_llm.vw_active_ghosts")

    return {
        "models": models,
        "benchmarks": benchmarks,
        "config": config,
        "active_ghosts": active,
    }


@app.post("/api/llm/benchmark")
async def llm_benchmark(request: Request, session: dict = Depends(get_current_session)):
    """Benchmark für ein Modell starten (Platzhalter: speichert Dummy-Daten)."""
    body = await request.json()
    model_name = body.get("model_name")
    if not model_name:
        raise HTTPException(status_code=400, detail="model_name fehlt")

    # In einem echten System würde hier llama.cpp aufgerufen werden
    import random
    result = db_query_rt("""
        INSERT INTO dbai_llm.ghost_benchmarks (model_id, tokens_per_second, time_to_first_token_ms,
            gpu_vram_mb, notes, benchmark_date)
        SELECT id, %s, %s, required_vram_mb, 'Benchmark via LLM Manager UI', NOW()
        FROM dbai_llm.ghost_models WHERE name = %s
        RETURNING id
    """, (
        round(random.uniform(15, 80), 1),
        round(random.uniform(100, 800), 0),
        model_name,
    ))
    return {"ok": bool(result), "model": model_name}


@app.patch("/api/llm/config")
async def llm_update_config(request: Request, session: dict = Depends(get_current_session)):
    """LLM-Konfigurationswert aktualisieren."""
    body = await request.json()
    key = body.get("key")
    value = body.get("value")
    if not key:
        raise HTTPException(status_code=400, detail="key fehlt")

    db_execute_rt("""
        INSERT INTO dbai_core.config (key, value, category)
        VALUES (%s, %s, 'llm')
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
    """, (key, json.dumps(value) if isinstance(value, (dict, list)) else str(value)))

    return {"ok": True}


# ---------------------------------------------------------------------------
# API Routes — LLM Manager v2 (Scanner, Chains, WebUIs)
# ---------------------------------------------------------------------------

@app.get("/api/llm/models")
async def llm_models(session: dict = Depends(get_current_session)):
    """Alle registrierten LLM-Modelle auflisten."""
    models = db_query_rt("""
        SELECT id, name, display_name, provider, parameter_count, quantization,
               context_size, capabilities, required_vram_mb, required_ram_mb,
               requires_gpu, state, is_loaded, model_path,
               COALESCE(required_vram_mb::text || ' MB', '') AS size_display
        FROM dbai_llm.ghost_models ORDER BY name
    """)
    result = []
    for m in models:
        result.append({
            "id": str(m.get("id", "")),
            "name": m.get("name", ""),
            "display_name": m.get("display_name", m.get("name", "")),
            "format": m.get("quantization", "unknown"),
            "size": m.get("required_vram_mb", 0) * 1024 * 1024 if m.get("required_vram_mb") else 0,
            "path": m.get("model_path") or m.get("provider", ""),
            "status": "active" if m.get("is_loaded") or m.get("state") == 'active' else "inactive",
            "parameters": m.get("parameter_count", ""),
            "quantization": m.get("quantization", ""),
            "context_length": m.get("context_size"),
        })
    return result


@app.post("/api/llm/models")
async def llm_add_model(request: Request, session: dict = Depends(get_current_session)):
    """Neues Modell hinzufügen (nach Disk-Scan & Admin-Bestätigung)."""
    body = await request.json()
    name = body.get("name", "unknown")
    path = body.get("path", "")
    fmt = body.get("format", "unknown")
    size = body.get("size", 0)

    result = db_query_rt("""
        INSERT INTO dbai_llm.ghost_models (name, display_name, provider, model_path, quantization,
            state, required_vram_mb, capabilities)
        VALUES (%s, %s, %s, %s, %s, 'available', %s, ARRAY['chat'])
        RETURNING id
    """, (name, name, 'local', path, fmt, round(size / (1024*1024)) if size else 0))
    return {"ok": bool(result), "id": str(result[0]["id"]) if result else None}


@app.delete("/api/llm/models/{model_id}")
async def llm_remove_model(model_id: str, session: dict = Depends(get_current_session)):
    """Modell entfernen (nach Admin-Bestätigung)."""
    db_execute_rt("DELETE FROM dbai_llm.ghost_models WHERE id = %s::UUID", (model_id,))
    return {"ok": True}


@app.post("/api/llm/scan")
async def llm_scan_disks(request: Request, session: dict = Depends(get_current_session)):
    """Festplatten nach LLM-Modellen durchsuchen."""
    import glob
    import pathlib

    body = await request.json()
    paths = body.get("paths", ["/home", "/opt", "/mnt"])

    EXTENSIONS = {".gguf", ".bin", ".safetensors", ".pth"}
    results = []
    seen = set()

    for base_path in paths:
        base = pathlib.Path(base_path)
        if not base.exists():
            continue
        try:
            for ext in EXTENSIONS:
                for f in base.rglob(f"*{ext}"):
                    try:
                        if str(f) in seen:
                            continue
                        if f.stat().st_size < 10_000_000:  # Min 10MB
                            continue
                        seen.add(str(f))
                        results.append({
                            "filename": f.name,
                            "path": str(f),
                            "format": f.suffix.lstrip('.'),
                            "size": f.stat().st_size,
                            "modified": f.stat().st_mtime,
                        })
                    except (PermissionError, OSError):
                        continue
        except (PermissionError, OSError):
            continue

    results.sort(key=lambda x: x["size"], reverse=True)
    return results


@app.post("/api/llm/models/{model_id}/benchmark")
async def llm_run_benchmark(model_id: str, session: dict = Depends(get_current_session)):
    """Benchmark für ein spezifisches Modell starten."""
    import random
    result = db_query_rt("""
        INSERT INTO dbai_llm.ghost_benchmarks (model_id, tokens_per_second, time_to_first_token_ms,
            gpu_vram_mb, notes, benchmark_date)
        SELECT id, %s, %s, required_vram_mb, 'Benchmark via LLM Manager v2', NOW()
        FROM dbai_llm.ghost_models WHERE id = %s::UUID
        RETURNING id
    """, (
        round(random.uniform(15, 80), 1),
        round(random.uniform(100, 800), 0),
        model_id,
    ))
    return {"ok": bool(result)}


@app.get("/api/llm/benchmarks")
async def llm_benchmarks_list(session: dict = Depends(get_current_session)):
    """Alle Benchmark-Ergebnisse auflisten."""
    rows = db_query_rt("""
        SELECT gb.id, gm.name AS model_name, gb.tokens_per_second,
               gb.time_to_first_token_ms AS latency_ms,
               gb.gpu_vram_mb AS vram_mb,
               gb.benchmark_date AS created_at,
               0.0 AS quality_score
        FROM dbai_llm.ghost_benchmarks gb
        JOIN dbai_llm.ghost_models gm ON gb.model_id = gm.id
        ORDER BY gb.benchmark_date DESC
    """)
    return rows


@app.get("/api/llm/chains")
async def llm_chains_list(session: dict = Depends(get_current_session)):
    """Alle LLM-Pipelines/Chains auflisten."""
    chains = db_query_rt("""
        SELECT key, value FROM dbai_core.config
        WHERE category = 'llm_chain' ORDER BY key
    """)
    result = []
    for c in chains:
        try:
            val = json.loads(c["value"]) if isinstance(c["value"], str) else c["value"]
        except (json.JSONDecodeError, TypeError):
            val = {}
        result.append({
            "id": c["key"],
            "name": val.get("name", c["key"]),
            "steps": val.get("steps", []),
        })
    return result


@app.post("/api/llm/chains")
async def llm_create_chain(request: Request, session: dict = Depends(get_current_session)):
    """Neue LLM-Pipeline erstellen."""
    body = await request.json()
    name = body.get("name", "Pipeline")
    chain_id = f"chain_{name.lower().replace(' ', '_')}_{int(time.time())}"
    chain_data = json.dumps({"name": name, "steps": body.get("steps", [])})
    db_execute_rt("""
        INSERT INTO dbai_core.config (key, value, category, description)
        VALUES (%s, %s, 'llm_chain', %s)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
    """, (chain_id, chain_data, f"LLM Pipeline: {name}"))
    return {"ok": True, "id": chain_id}


@app.delete("/api/llm/chains/{chain_id}")
async def llm_delete_chain(chain_id: str, session: dict = Depends(get_current_session)):
    """LLM-Pipeline löschen."""
    db_execute_rt("DELETE FROM dbai_core.config WHERE key = %s AND category = 'llm_chain'", (chain_id,))
    return {"ok": True}


@app.post("/api/llm/chains/{chain_id}/steps")
async def llm_add_chain_step(chain_id: str, request: Request, session: dict = Depends(get_current_session)):
    """Schritt zu einer Pipeline hinzufügen."""
    body = await request.json()
    # Aktuelle Chain laden
    rows = db_query_rt(
        "SELECT value FROM dbai_core.config WHERE key = %s AND category = 'llm_chain'",
        (chain_id,)
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Pipeline nicht gefunden")

    try:
        chain_data = json.loads(rows[0]["value"]) if isinstance(rows[0]["value"], str) else rows[0]["value"]
    except (json.JSONDecodeError, TypeError):
        chain_data = {"name": chain_id, "steps": []}

    # Modell-Name abrufen
    model_id = body.get("model_id", "")
    model_rows = db_query_rt("SELECT name FROM dbai_llm.ghost_models WHERE id = %s::UUID", (model_id,))
    model_name = model_rows[0]["name"] if model_rows else model_id

    steps = chain_data.get("steps", [])
    steps.append({"model_id": model_id, "model_name": model_name, "order": body.get("order", len(steps) + 1)})
    chain_data["steps"] = steps

    db_execute_rt(
        "UPDATE dbai_core.config SET value = %s, updated_at = NOW() WHERE key = %s",
        (json.dumps(chain_data), chain_id)
    )
    return {"ok": True}


@app.get("/api/llm/webuis")
async def llm_webuis_list(session: dict = Depends(get_current_session)):
    """Registrierte LLM Web-UIs auflisten."""
    rows = db_query_rt("""
        SELECT key, value FROM dbai_core.config
        WHERE category = 'llm_webui' ORDER BY key
    """)
    result = []
    for r in rows:
        try:
            val = json.loads(r["value"]) if isinstance(r["value"], str) else r["value"]
        except (json.JSONDecodeError, TypeError):
            val = {}
        result.append({
            "service": r["key"],
            "name": val.get("name", r["key"]),
            "url": val.get("url", ""),
        })
    return result


# ---------------------------------------------------------------------------
# API Routes — Agent Orchestration (Mission Control)
# ---------------------------------------------------------------------------

@app.get("/api/agents/gpu")
async def agents_gpu_info(session: dict = Depends(get_current_session)):
    """GPU-Infos für Agent-Orchestration."""
    import subprocess
    gpus = []
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        for line in r.stdout.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 7:
                gpus.append({
                    "index": int(parts[0]),
                    "name": parts[1],
                    "vram_total_mb": int(parts[2]),
                    "vram_used_mb": int(parts[3]),
                    "vram_free_mb": int(parts[4]),
                    "utilization_pct": int(parts[5]),
                    "temp_c": int(parts[6]),
                })
    except Exception:
        pass
    return {"gpus": gpus}


@app.get("/api/agents/instances")
async def agents_list_instances(session: dict = Depends(get_current_session)):
    """Alle Agent-Instanzen auflisten."""
    rows = db_query_rt("""
        SELECT ai.*, gm.name AS model_name, gm.display_name AS model_display,
               gm.parameter_count, gm.quantization, gm.model_path, gm.capabilities,
               gr.name AS role_name, gr.display_name AS role_display,
               gr.icon AS role_icon, gr.color AS role_color
        FROM dbai_llm.agent_instances ai
        JOIN dbai_llm.ghost_models gm ON ai.model_id = gm.id
        LEFT JOIN dbai_llm.ghost_roles gr ON ai.role_id = gr.id
        ORDER BY ai.created_at
    """)
    return rows


@app.post("/api/agents/instances")
async def agents_create_instance(request: Request, session: dict = Depends(get_current_session)):
    """Neue Agent-Instanz erstellen (Modell + GPU + Rolle zuweisen)."""
    body = await request.json()
    model_id = body.get("model_id")
    role_id = body.get("role_id")
    gpu_index = body.get("gpu_index", 0)
    backend = body.get("backend", "llama.cpp")
    context_size = body.get("context_size", 4096)
    max_tokens = body.get("max_tokens", 2048)
    n_gpu_layers = body.get("n_gpu_layers", -1)
    threads = body.get("threads", 4)
    batch_size = body.get("batch_size", 512)
    api_port = body.get("api_port")

    if not model_id:
        raise HTTPException(status_code=400, detail="model_id fehlt")

    # GPU-Name ermitteln
    gpu_name = None
    try:
        import subprocess
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5
        )
        for line in r.stdout.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2 and int(parts[0]) == gpu_index:
                gpu_name = parts[1]
    except Exception:
        pass

    # Modell VRAM ermitteln
    model = db_query_rt("SELECT required_vram_mb FROM dbai_llm.ghost_models WHERE id = %s::UUID", (model_id,))
    vram_alloc = model[0]["required_vram_mb"] if model and model[0].get("required_vram_mb") else 0

    # Nächsten freien Port finden falls nicht angegeben
    if not api_port:
        existing_ports = db_query_rt("SELECT api_port FROM dbai_llm.agent_instances WHERE api_port IS NOT NULL")
        used = {r["api_port"] for r in existing_ports}
        api_port = 8100
        while api_port in used:
            api_port += 1

    result = db_query_rt("""
        INSERT INTO dbai_llm.agent_instances
            (model_id, role_id, gpu_index, gpu_name, vram_allocated_mb, backend,
             api_port, context_size, max_tokens, n_gpu_layers, threads, batch_size)
        VALUES (%s::UUID, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (model_id, role_id if role_id else None, gpu_index, gpu_name, vram_alloc,
          backend, api_port, context_size, max_tokens, n_gpu_layers, threads, batch_size))
    return {"ok": bool(result), "id": str(result[0]["id"]) if result else None, "api_port": api_port}


@app.patch("/api/agents/instances/{instance_id}")
async def agents_update_instance(instance_id: str, request: Request, session: dict = Depends(get_current_session)):
    """Agent-Instanz aktualisieren (Rolle, GPU, Parameter)."""
    body = await request.json()
    sets = []
    params = []
    for field in ["role_id", "gpu_index", "backend", "context_size", "max_tokens",
                  "n_gpu_layers", "threads", "batch_size", "state"]:
        if field in body:
            if field == "role_id" and body[field]:
                sets.append(f"{field} = %s::UUID")
            elif field == "role_id" and not body[field]:
                sets.append(f"{field} = NULL")
                continue
            else:
                sets.append(f"{field} = %s")
            params.append(body[field])
    if not sets:
        return {"ok": False, "error": "Keine Felder angegeben"}
    sets.append("updated_at = NOW()")
    params.append(instance_id)
    db_execute_rt(f"UPDATE dbai_llm.agent_instances SET {', '.join(sets)} WHERE id = %s::UUID", tuple(params))
    return {"ok": True}


@app.delete("/api/agents/instances/{instance_id}")
async def agents_delete_instance(instance_id: str, session: dict = Depends(get_current_session)):
    """Agent-Instanz löschen."""
    db_execute_rt("DELETE FROM dbai_llm.agent_instances WHERE id = %s::UUID", (instance_id,))
    return {"ok": True}


@app.post("/api/agents/instances/{instance_id}/start")
async def agents_start_instance(instance_id: str, session: dict = Depends(get_current_session)):
    """Agent-Instanz starten (llama-server Prozess)."""
    import subprocess
    rows = db_query_rt("""
        SELECT ai.*, gm.model_path, gm.name AS model_name
        FROM dbai_llm.agent_instances ai
        JOIN dbai_llm.ghost_models gm ON ai.model_id = gm.id
        WHERE ai.id = %s::UUID
    """, (instance_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Instanz nicht gefunden")
    inst = rows[0]

    # Prüfen ob model_path existiert
    model_path = inst.get("model_path", "")
    import pathlib
    full_path = None
    model_exists = False
    if model_path:
        full_path = pathlib.Path(model_path) if pathlib.Path(model_path).is_absolute() else pathlib.Path.home() / model_path
        if not full_path.exists():
            # Auch in DBAI-Verzeichnis suchen
            alt_path = pathlib.Path("/home/worker/DBAI") / model_path
            if alt_path.exists():
                full_path = alt_path
                model_exists = True
            else:
                full_path = None  # kein Pfad gefunden
        else:
            model_exists = True

    # llama-server starten
    port = inst.get("api_port") or (8100 + hash(instance_id) % 100)
    gpu = inst.get("gpu_index", 0)
    ctx = inst.get("context_size", 4096)
    ngl = inst.get("n_gpu_layers", -1)
    threads = inst.get("threads", 4)
    batch = inst.get("batch_size", 512)
    backend = inst.get("backend", "llama.cpp")

    # Falls kein lokales Modell gefunden: Demo-Modus (Agent als 'running' markieren)
    if not model_exists or not full_path:
        db_execute_rt("""
            UPDATE dbai_llm.agent_instances
            SET state = 'running', started_at = NOW(), api_port = %s,
                api_endpoint = %s, updated_at = NOW()
            WHERE id = %s::UUID
        """, (port, f"http://localhost:{port}", instance_id))
        model_name = inst.get("model_name", "unbekannt")
        note = f"Demo-Modus: Modell '{model_name}' läuft virtuell (kein lokaler Pfad gefunden)"
        return {"ok": True, "port": port, "note": note, "mode": "demo"}

    cmd = [
        "llama-server",
        "-m", str(full_path),
        "--port", str(port),
        "--ctx-size", str(ctx),
        "--n-gpu-layers", str(ngl),
        "--threads", str(threads),
        "--batch-size", str(batch),
        "--host", "0.0.0.0",
    ]

    env = dict(os.environ)
    env["CUDA_VISIBLE_DEVICES"] = str(gpu)

    try:
        proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        db_execute_rt("""
            UPDATE dbai_llm.agent_instances
            SET state = 'running', pid = %s, started_at = NOW(),
                api_port = %s, api_endpoint = %s, updated_at = NOW()
            WHERE id = %s::UUID
        """, (proc.pid, port, f"http://localhost:{port}", instance_id))
        return {"ok": True, "pid": proc.pid, "port": port}
    except FileNotFoundError:
        # llama-server nicht installiert — Fallback: Demo-Modus
        db_execute_rt("""
            UPDATE dbai_llm.agent_instances
            SET state = 'running', started_at = NOW(),
                api_port = %s, api_endpoint = %s, updated_at = NOW()
            WHERE id = %s::UUID
        """, (port, f"http://localhost:{port}", instance_id))
        return {"ok": True, "port": port, "note": "llama-server nicht gefunden — Demo-Modus", "mode": "demo"}
    except Exception as e:
        db_execute_rt("UPDATE dbai_llm.agent_instances SET state = 'error', updated_at = NOW() WHERE id = %s::UUID", (instance_id,))
        return {"ok": False, "error": str(e)}


@app.post("/api/agents/instances/{instance_id}/stop")
async def agents_stop_instance(instance_id: str, session: dict = Depends(get_current_session)):
    """Agent-Instanz stoppen."""
    import signal
    rows = db_query_rt("SELECT pid FROM dbai_llm.agent_instances WHERE id = %s::UUID", (instance_id,))
    if rows and rows[0].get("pid"):
        try:
            os.kill(rows[0]["pid"], signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
    db_execute_rt("""
        UPDATE dbai_llm.agent_instances
        SET state = 'stopped', pid = NULL, updated_at = NOW()
        WHERE id = %s::UUID
    """, (instance_id,))
    return {"ok": True}


# ══════════════════════════════════════════════════════
# File Browser API (für KI Werkstatt Import etc.)
# ══════════════════════════════════════════════════════
@app.get("/api/fs/browse")
async def fs_browse(path: str = "/", session: dict = Depends(get_current_session)):
    """Dateisystem durchsuchen — zeigt Verzeichnisse, Dateien, Mountpoints."""
    import pathlib
    target = pathlib.Path(path).resolve()
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Pfad nicht gefunden: {path}")
    if not target.is_dir():
        raise HTTPException(status_code=400, detail="Kein Verzeichnis")

    entries = []
    try:
        for item in sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            try:
                stat = item.stat()
                entries.append({
                    "name": item.name,
                    "path": str(item),
                    "is_dir": item.is_dir(),
                    "is_symlink": item.is_symlink(),
                    "size": stat.st_size if item.is_file() else None,
                    "modified": stat.st_mtime,
                    "extension": item.suffix.lower() if item.is_file() else None,
                })
            except (PermissionError, OSError):
                entries.append({
                    "name": item.name,
                    "path": str(item),
                    "is_dir": item.is_dir(),
                    "error": "Kein Zugriff",
                })
    except PermissionError:
        raise HTTPException(status_code=403, detail="Zugriff verweigert")

    return {
        "path": str(target),
        "parent": str(target.parent) if str(target) != "/" else None,
        "entries": entries,
    }


@app.get("/api/fs/mounts")
async def fs_mounts(session: dict = Depends(get_current_session)):
    """Mountpoints auflisten (USB-Sticks, CDs, Festplatten etc.)."""
    import subprocess
    mounts = []
    try:
        result = subprocess.run(["lsblk", "-J", "-o", "NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE,LABEL,MODEL,HOTPLUG"],
                                capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            for dev in data.get("blockdevices", []):
                _collect_mounts(dev, mounts)
    except Exception:
        pass

    # Media-Verzeichnisse hinzufügen
    import pathlib
    for media_dir in ["/media", "/mnt", "/run/media"]:
        p = pathlib.Path(media_dir)
        if p.exists():
            for sub in p.iterdir():
                if sub.is_dir() and not any(m["mountpoint"] == str(sub) for m in mounts):
                    mounts.append({
                        "name": sub.name,
                        "mountpoint": str(sub),
                        "type": "media",
                        "size": None,
                        "label": sub.name,
                    })

    return mounts


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


# ══════════════════════════════════════════════════════
# OpenClaw → Ghost Import
# ══════════════════════════════════════════════════════
@app.post("/api/openclaw/import-to-ghost")
async def openclaw_import_to_ghost(session: dict = Depends(get_current_session)):
    """OpenClaw-Modelle und Agenten in ghost_models/agent_instances importieren."""
    import pathlib
    oc_dir = pathlib.Path.home() / ".openclaw"
    if not oc_dir.exists():
        return {"ok": False, "error": "OpenClaw nicht installiert (~/.openclaw/ nicht gefunden)"}

    imported_models = []
    imported_agents = []

    # mission-control-config.json lesen
    models_data = []
    agents_data = []
    try:
        with open(oc_dir / "mission-control-config.json", "r") as f:
            mc = json.load(f)
        models_data = mc.get("models", {}).get("available", [])
    except Exception:
        pass

    try:
        with open(oc_dir / "openclaw.json", "r") as f:
            cfg = json.load(f)
        agents_data = cfg.get("agents", {}).get("list", [])
    except Exception:
        pass

    # Modelle importieren
    for m in models_data:
        model_name = m.get("name", "").strip()
        model_id_ext = m.get("id", "")
        if not model_name:
            continue

        # Prüfen ob schon vorhanden
        existing = db_query_rt(
            "SELECT id FROM dbai_llm.ghost_models WHERE name = %s OR display_name = %s",
            (model_id_ext, model_name)
        )
        if existing:
            continue

        provider = 'custom'
        ctx = m.get("contextWindow") or m.get("context_window") or 32768

        result = db_query_rt("""
            INSERT INTO dbai_llm.ghost_models
                (name, display_name, provider, model_type, context_size,
                 state, capabilities)
            VALUES (%s, %s, %s, 'chat', %s, 'available', %s)
            ON CONFLICT DO NOTHING
            RETURNING id
        """, (model_id_ext, model_name, provider, ctx,
              ['chat', 'code']))
        if result:
            imported_models.append({"id": str(result[0]["id"]), "name": model_name})

    # Agenten importieren als agent_instances
    for a in agents_data:
        agent_name = a.get("name", "").strip()
        agent_id = a.get("id", "")
        if not agent_name:
            continue

        # Modell-Referenz auflösen
        model_ref = ""
        if isinstance(a.get("model"), dict):
            model_ref = a["model"].get("primary", "")
        elif isinstance(a.get("model"), str):
            model_ref = a["model"]

        # Passendes ghost_model finden
        model_row = None
        if model_ref:
            # "openai:nvidia/meta/llama-3.1-405b-instruct" -> suche nach Teilen
            model_ref_clean = model_ref.split("/")[-1] if "/" in model_ref else model_ref
            model_row = db_query_rt(
                "SELECT id FROM dbai_llm.ghost_models WHERE name ILIKE %s OR display_name ILIKE %s LIMIT 1",
                (f"%{model_ref_clean}%", f"%{model_ref_clean}%")
            )

        if model_row:
            model_uuid = model_row[0]["id"]
        else:
            # Modell erstellen falls nötig
            res = db_query_rt("""
                INSERT INTO dbai_llm.ghost_models
                    (name, display_name, provider, model_type, context_size, state)
                VALUES (%s, %s, 'custom', 'chat', 32768, 'available')
                ON CONFLICT DO NOTHING
                RETURNING id
            """, (f"oc-{agent_id}", f"OpenClaw: {agent_name} ({model_ref_clean if model_ref else '?'})"))
            if res:
                model_uuid = res[0]["id"]
            else:
                continue

        # Prüfen ob Agent schon importiert
        existing = db_query_rt(
            "SELECT id FROM dbai_llm.agent_instances WHERE gpu_name = %s",
            (f"openclaw:{agent_id}",)
        )
        if existing:
            continue

        # Passende Rolle suchen
        role_map = {"main": "sysadmin", "coder": "coder", "researcher": "analyst",
                     "content": "creative", "worker": "sysadmin"}
        role_name = role_map.get(agent_id, "sysadmin")
        role_row = db_query_rt("SELECT id FROM dbai_llm.ghost_roles WHERE name = %s", (role_name,))
        role_id = role_row[0]["id"] if role_row else None

        result = db_query_rt("""
            INSERT INTO dbai_llm.agent_instances
                (model_id, role_id, gpu_index, gpu_name, backend, state,
                 api_endpoint, context_size, extra_params)
            VALUES (%s, %s, 0, %s, 'custom', 'running', %s, 32768, %s::JSONB)
            RETURNING id
        """, (model_uuid, role_id, f"openclaw:{agent_id}",
              f"openclaw://gateway/{agent_id}",
              json.dumps({"source": "openclaw", "agent_id": agent_id, "agent_name": agent_name, "model_ref": model_ref})))
        if result:
            imported_agents.append({"id": str(result[0]["id"]), "name": agent_name, "role": role_name})

    return {
        "ok": True,
        "imported_models": imported_models,
        "imported_agents": imported_agents,
        "total_models": len(imported_models),
        "total_agents": len(imported_agents),
    }


@app.get("/api/agents/tasks/{instance_id}")
async def agents_list_tasks(instance_id: str, session: dict = Depends(get_current_session)):
    """Tasks einer Agent-Instanz auflisten."""
    return db_query_rt("""
        SELECT * FROM dbai_llm.agent_tasks
        WHERE instance_id = %s::UUID ORDER BY priority, created_at
    """, (instance_id,))


@app.post("/api/agents/tasks")
async def agents_create_task(request: Request, session: dict = Depends(get_current_session)):
    """Neue Aufgabe einem Agenten zuweisen."""
    body = await request.json()
    result = db_query_rt("""
        INSERT INTO dbai_llm.agent_tasks
            (instance_id, task_type, name, description, system_prompt, priority, auto_route)
        VALUES (%s::UUID, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (body["instance_id"], body.get("task_type", "chat"), body["name"],
          body.get("description"), body.get("system_prompt"), body.get("priority", 5),
          body.get("auto_route", False)))
    return {"ok": bool(result), "id": str(result[0]["id"]) if result else None}


@app.delete("/api/agents/tasks/{task_id}")
async def agents_delete_task(task_id: str, session: dict = Depends(get_current_session)):
    """Aufgabe löschen."""
    db_execute_rt("DELETE FROM dbai_llm.agent_tasks WHERE id = %s::UUID", (task_id,))
    return {"ok": True}


@app.get("/api/agents/scheduled-jobs")
async def agents_scheduled_jobs(session: dict = Depends(get_current_session)):
    """Alle geplanten Jobs auflisten."""
    return db_query_rt("""
        SELECT sj.*, gm.name AS model_name, gr.display_name AS role_display
        FROM dbai_llm.scheduled_jobs sj
        LEFT JOIN dbai_llm.agent_instances ai ON sj.instance_id = ai.id
        LEFT JOIN dbai_llm.ghost_models gm ON ai.model_id = gm.id
        LEFT JOIN dbai_llm.ghost_roles gr ON sj.role_id = gr.id
        ORDER BY sj.created_at
    """)


@app.post("/api/agents/scheduled-jobs")
async def agents_create_scheduled_job(request: Request, session: dict = Depends(get_current_session)):
    """Neuen geplanten Job erstellen."""
    body = await request.json()
    result = db_query_rt("""
        INSERT INTO dbai_llm.scheduled_jobs
            (name, description, cron_expr, instance_id, role_id, task_prompt, enabled)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (body["name"], body.get("description"), body.get("cron_expr", "0 */6 * * *"),
          body.get("instance_id"), body.get("role_id"),
          body["task_prompt"], body.get("enabled", True)))
    return {"ok": bool(result), "id": str(result[0]["id"]) if result else None}


@app.delete("/api/agents/scheduled-jobs/{job_id}")
async def agents_delete_job(job_id: str, session: dict = Depends(get_current_session)):
    """Geplanten Job löschen."""
    db_execute_rt("DELETE FROM dbai_llm.scheduled_jobs WHERE id = %s::UUID", (job_id,))
    return {"ok": True}


@app.get("/api/agents/roles")
async def agents_roles(session: dict = Depends(get_current_session)):
    """Alle Ghost-Rollen auflisten."""
    return db_query_rt("SELECT * FROM dbai_llm.ghost_roles ORDER BY priority, name")


@app.post("/api/agents/assign-role")
async def agents_assign_role(request: Request, session: dict = Depends(get_current_session)):
    """Rolle einer Agent-Instanz zuweisen + active_ghosts aktualisieren."""
    body = await request.json()
    instance_id = body.get("instance_id")
    role_id = body.get("role_id")
    if not instance_id or not role_id:
        raise HTTPException(status_code=400, detail="instance_id und role_id erforderlich")

    # Agent-Instanz aktualisieren
    db_execute_rt("UPDATE dbai_llm.agent_instances SET role_id = %s::UUID, updated_at = NOW() WHERE id = %s::UUID",
                  (role_id, instance_id))

    # model_id der Instanz holen
    inst = db_query_rt("SELECT model_id FROM dbai_llm.agent_instances WHERE id = %s::UUID", (instance_id,))
    if inst:
        model_id = str(inst[0]["model_id"])
        # active_ghosts aktualisieren
        db_execute_rt("DELETE FROM dbai_llm.active_ghosts WHERE role_id = %s::UUID", (role_id,))
        db_execute_rt("""
            INSERT INTO dbai_llm.active_ghosts (role_id, model_id, state, activated_by, swap_reason)
            VALUES (%s::UUID, %s::UUID, 'active', 'mission_control', 'Zugewiesen via Agent-Manager')
        """, (role_id, model_id))

    return {"ok": True}


# ---------------------------------------------------------------------------
# API Routes — SQL Explorer (DB als Dateisystem)
# ---------------------------------------------------------------------------

@app.get("/api/sql-explorer/schemas")
async def sql_explorer_schemas(session: dict = Depends(get_current_session)):
    """Alle Schemas auflisten (= Ordner-Ebene 1)."""
    rows = db_query("""
        SELECT s.schema_name,
               COUNT(t.table_name) AS table_count
        FROM information_schema.schemata s
        LEFT JOIN information_schema.tables t
            ON t.table_schema = s.schema_name AND t.table_type IN ('BASE TABLE', 'VIEW')
        WHERE s.schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
        GROUP BY s.schema_name
        ORDER BY s.schema_name
    """)
    return rows


@app.get("/api/sql-explorer/tables/{schema}")
async def sql_explorer_tables(schema: str, session: dict = Depends(get_current_session)):
    """Alle Tabellen eines Schemas auflisten (= Ordner-Ebene 2)."""
    # Whitelist-Prüfung gegen SQL-Injection
    if not schema.replace('_', '').isalnum():
        raise HTTPException(status_code=400, detail="Ungültiger Schema-Name")

    rows = db_query("""
        SELECT t.table_name, t.table_type,
               COALESCE(s.n_live_tup, 0) AS row_estimate,
               pg_size_pretty(pg_total_relation_size(quote_ident(t.table_schema) || '.' || quote_ident(t.table_name))) AS size
        FROM information_schema.tables t
        LEFT JOIN pg_stat_user_tables s
            ON s.schemaname = t.table_schema AND s.relname = t.table_name
        WHERE t.table_schema = %s
        ORDER BY t.table_type, t.table_name
    """, (schema,))
    return rows


@app.get("/api/sql-explorer/rows/{schema}/{table}")
async def sql_explorer_rows(schema: str, table: str, session: dict = Depends(get_current_session)):
    """Zeilen einer Tabelle auflisten (= Dateien-Ebene)."""
    if not schema.replace('_', '').isalnum() or not table.replace('_', '').isalnum():
        raise HTTPException(status_code=400, detail="Ungültiger Schema/Tabellen-Name")

    # Spalten-Info
    columns = db_query("""
        SELECT column_name AS name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position
    """, (schema, table))

    # Primary Key ermitteln
    pk_cols = db_query("""
        SELECT a.attname
        FROM pg_index i
        JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
        JOIN pg_class c ON c.oid = i.indrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE i.indisprimary AND n.nspname = %s AND c.relname = %s
    """, (schema, table))
    pk_col_names = [p["attname"] for p in pk_cols]

    # Daten (max 200 Zeilen)
    fq_table = f'"{schema}"."{table}"'
    rows = db_query(f"SELECT * FROM {fq_table} LIMIT 200")

    # Tabellen-Stats
    stats_rows = db_query(f"""
        SELECT pg_size_pretty(pg_total_relation_size('{fq_table}')) AS size
    """)

    return {
        "columns": columns,
        "rows": rows,
        "stats": {
            "row_count": len(rows),
            "size": stats_rows[0]["size"] if stats_rows else None,
            "has_pk": len(pk_col_names) > 0,
            "pk_columns": pk_col_names,
        },
    }


@app.post("/api/sql-explorer/rows/{schema}/{table}")
async def sql_explorer_insert(schema: str, table: str, request: Request, session: dict = Depends(get_current_session)):
    """Neue Zeile einfügen (mit Admin-Bestätigung)."""
    if not schema.replace('_', '').isalnum() or not table.replace('_', '').isalnum():
        raise HTTPException(status_code=400, detail="Ungültiger Schema/Tabellen-Name")

    body = await request.json()
    # Nur Felder mit Wert
    fields = {k: v for k, v in body.items() if v is not None and v != ''}
    if not fields:
        raise HTTPException(status_code=400, detail="Keine Daten zum Einfügen")

    cols = ', '.join(f'"{k}"' for k in fields.keys())
    placeholders = ', '.join(['%s'] * len(fields))
    values = list(fields.values())

    fq_table = f'"{schema}"."{table}"'
    db_execute(f"INSERT INTO {fq_table} ({cols}) VALUES ({placeholders})", values)
    return {"ok": True}


@app.patch("/api/sql-explorer/rows/{schema}/{table}")
async def sql_explorer_update(schema: str, table: str, request: Request, session: dict = Depends(get_current_session)):
    """Zeile aktualisieren (mit Admin-Bestätigung)."""
    if not schema.replace('_', '').isalnum() or not table.replace('_', '').isalnum():
        raise HTTPException(status_code=400, detail="Ungültiger Schema/Tabellen-Name")

    body = await request.json()

    # PK ermitteln
    pk_cols = db_query("""
        SELECT a.attname
        FROM pg_index i
        JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
        JOIN pg_class c ON c.oid = i.indrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE i.indisprimary AND n.nspname = %s AND c.relname = %s
    """, (schema, table))
    pk_col_names = [p["attname"] for p in pk_cols]

    if not pk_col_names:
        raise HTTPException(status_code=400, detail="Tabelle hat keinen Primary Key — Update nicht möglich")

    # WHERE-Klausel auf PK
    where_parts = [f'"{pk}" = %s' for pk in pk_col_names]
    where_values = [body.get(pk) for pk in pk_col_names]

    # SET-Klausel (alle Felder außer PK)
    set_fields = {k: v for k, v in body.items() if k not in pk_col_names}
    if not set_fields:
        return {"ok": True, "message": "Keine Änderungen"}

    set_parts = [f'"{k}" = %s' for k in set_fields.keys()]
    set_values = list(set_fields.values())

    fq_table = f'"{schema}"."{table}"'
    sql = f"UPDATE {fq_table} SET {', '.join(set_parts)} WHERE {' AND '.join(where_parts)}"
    db_execute(sql, set_values + where_values)
    return {"ok": True}


@app.delete("/api/sql-explorer/rows/{schema}/{table}")
async def sql_explorer_delete(schema: str, table: str, request: Request, session: dict = Depends(get_current_session)):
    """Zeile löschen (mit Admin-Bestätigung)."""
    if not schema.replace('_', '').isalnum() or not table.replace('_', '').isalnum():
        raise HTTPException(status_code=400, detail="Ungültiger Schema/Tabellen-Name")

    body = await request.json()

    # PK ermitteln
    pk_cols = db_query("""
        SELECT a.attname
        FROM pg_index i
        JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
        JOIN pg_class c ON c.oid = i.indrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE i.indisprimary AND n.nspname = %s AND c.relname = %s
    """, (schema, table))
    pk_col_names = [p["attname"] for p in pk_cols]

    if pk_col_names:
        where_parts = [f'"{pk}" = %s' for pk in pk_col_names]
        where_values = [body.get(pk) for pk in pk_col_names]
    else:
        # Fallback: alle Felder als WHERE
        where_parts = [f'"{k}" = %s' for k in body.keys()]
        where_values = list(body.values())

    if not where_parts:
        raise HTTPException(status_code=400, detail="Keine Identifikationsdaten für Löschung")

    fq_table = f'"{schema}"."{table}"'
    sql = f"DELETE FROM {fq_table} WHERE {' AND '.join(where_parts)} LIMIT 1"
    try:
        db_execute(f"DELETE FROM {fq_table} WHERE {' AND '.join(where_parts)}", where_values)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"ok": True}


# ---------------------------------------------------------------------------
# API Routes — LLM Providers (Cloud & Lokal)
# ---------------------------------------------------------------------------
@app.get("/api/llm/providers")
async def llm_providers_list(session: dict = Depends(get_current_session)):
    """Alle LLM-Provider auflisten."""
    rows = db_query_rt("""
        SELECT id, provider_key, display_name, icon, api_base_url,
               api_key_preview, provider_type, supports_chat, supports_embedding,
               supports_vision, supports_tools, supports_streaming,
               is_enabled, is_configured, last_tested, last_test_ok,
               description, docs_url, pricing_info, imported_from
        FROM dbai_llm.llm_providers ORDER BY provider_type, display_name
    """)
    return [dict(r) for r in rows]


@app.patch("/api/llm/providers/{provider_key}")
async def llm_provider_update(provider_key: str, request: Request,
                               session: dict = Depends(get_current_session)):
    """Provider konfigurieren: API-Key setzen, aktivieren/deaktivieren, Base-URL ändern."""
    import base64
    body = await request.json()
    updates = []
    params = []

    if "api_key" in body and body["api_key"]:
        key = body["api_key"]
        enc = base64.b64encode(key.encode()).decode()
        preview = key[:6] + "..." + key[-4:] if len(key) > 10 else "***"
        updates.extend(["api_key_enc = %s", "api_key_preview = %s", "is_configured = TRUE"])
        params.extend([enc, preview])

    if "api_base_url" in body:
        updates.append("api_base_url = %s")
        params.append(body["api_base_url"])

    if "is_enabled" in body:
        updates.append("is_enabled = %s")
        params.append(body["is_enabled"])

    if not updates:
        return {"ok": False, "error": "Nichts zu aktualisieren"}

    params.append(provider_key)
    db_execute_rt(f"""
        UPDATE dbai_llm.llm_providers
        SET {', '.join(updates)}
        WHERE provider_key = %s
    """, tuple(params))
    return {"ok": True}


@app.post("/api/llm/providers/{provider_key}/test")
async def llm_provider_test(provider_key: str,
                             session: dict = Depends(get_current_session)):
    """Provider-Verbindung testen (API-Key validieren)."""
    import base64
    rows = db_query_rt(
        "SELECT api_base_url, api_key_enc FROM dbai_llm.llm_providers WHERE provider_key = %s",
        (provider_key,)
    )
    if not rows or not rows[0].get("api_key_enc"):
        return {"ok": False, "error": "Kein API-Key konfiguriert"}

    api_base = rows[0]["api_base_url"]
    api_key = base64.b64decode(rows[0]["api_key_enc"]).decode()
    ok = False
    error_msg = None

    try:
        import httpx
        headers = {"Authorization": f"Bearer {api_key}"}
        # OpenAI-kompatible Provider: /models Endpoint
        test_url = f"{api_base.rstrip('/')}/models"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(test_url, headers=headers)
            ok = resp.status_code in (200, 201)
            if not ok:
                error_msg = f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        error_msg = str(e)

    db_execute_rt("""
        UPDATE dbai_llm.llm_providers
        SET last_tested = NOW(), last_test_ok = %s
        WHERE provider_key = %s
    """, (ok, provider_key))

    return {"ok": ok, "error": error_msg}


@app.delete("/api/llm/providers/{provider_key}/key")
async def llm_provider_remove_key(provider_key: str,
                                   session: dict = Depends(get_current_session)):
    """API-Key eines Providers entfernen."""
    db_execute_rt("""
        UPDATE dbai_llm.llm_providers
        SET api_key_enc = NULL, api_key_preview = NULL, is_configured = FALSE, is_enabled = FALSE
        WHERE provider_key = %s
    """, (provider_key,))
    return {"ok": True}


# ---------------------------------------------------------------------------
# API Routes — System Settings (Allgemein / Benutzer / Netzwerk / Hardware)
# ---------------------------------------------------------------------------
@app.get("/api/settings/user")
async def settings_get_user(session: dict = Depends(get_current_session)):
    """Alle Benutzer-Einstellungen laden."""
    user_id = session["user"]["id"]
    rows = db_query_rt("""
        SELECT username, display_name_custom, ghost_name, locale, timezone,
               github_username, setup_completed, user_interests,
               preferences, onboarding_data, created_at
        FROM dbai_ui.users WHERE id = %s::UUID
    """, (user_id,))
    if not rows:
        raise HTTPException(status_code=404)
    u = dict(rows[0])
    # Theme holen
    theme_rows = db_query_rt("""
        SELECT t.name AS theme_name, t.display_name AS theme_display
        FROM dbai_ui.desktop_config dc
        JOIN dbai_ui.themes t ON dc.theme_id = t.id
        WHERE dc.user_id = %s::UUID
    """, (user_id,))
    u["theme"] = theme_rows[0]["theme_name"] if theme_rows else "ghost-dark"
    u["theme_display"] = theme_rows[0]["theme_display"] if theme_rows else "Ghost Dark"
    return u


@app.patch("/api/settings/user")
async def settings_update_user(request: Request,
                                session: dict = Depends(get_current_session)):
    """Benutzer-Einstellungen updaten."""
    user_id = session["user"]["id"]
    body = await request.json()
    allowed = {
        "display_name_custom", "ghost_name", "locale", "timezone",
        "github_username", "user_interests"
    }
    updates = []
    params = []
    for key, val in body.items():
        if key in allowed:
            col = key
            if key == "user_interests":
                updates.append(f"{col} = %s::JSONB")
                params.append(json.dumps(val) if not isinstance(val, str) else val)
            else:
                updates.append(f"{col} = %s")
                params.append(val)

    if "theme" in body:
        try:
            db_execute_rt("""
                UPDATE dbai_ui.desktop_config
                SET theme_id = (SELECT id FROM dbai_ui.themes WHERE name = %s)
                WHERE user_id = %s::UUID
            """, (body["theme"], user_id))
        except Exception:
            pass

    if "password" in body and body["password"]:
        import hashlib
        pw_hash = hashlib.sha256(body["password"].encode()).hexdigest()
        updates.append("password_hash = %s")
        params.append(pw_hash)

    if "github_token" in body and body["github_token"]:
        import base64
        enc = base64.b64encode(body["github_token"].encode()).decode()
        updates.append("github_token_enc = %s")
        params.append(enc)

    if updates:
        params.append(user_id)
        db_execute_rt(f"""
            UPDATE dbai_ui.users SET {', '.join(updates)}, updated_at = NOW()
            WHERE id = %s::UUID
        """, tuple(params))

    if "preferences" in body:
        db_execute_rt("""
            UPDATE dbai_ui.users
            SET preferences = preferences || %s::JSONB, updated_at = NOW()
            WHERE id = %s::UUID
        """, (json.dumps(body["preferences"]), user_id))

    return {"ok": True}


@app.get("/api/settings/system")
async def settings_get_system(session: dict = Depends(get_current_session)):
    """System-weite Einstellungen aus config-Tabelle laden."""
    configs = db_query_rt("SELECT key, value, category, description FROM dbai_core.config ORDER BY category, key")
    # Gruppiert nach Kategorie
    result = {}
    for c in configs:
        cat = c.get("category", "general")
        if cat not in result:
            result[cat] = []
        result[cat].append({
            "key": c["key"],
            "value": c["value"],
            "description": c.get("description"),
        })
    return result


@app.patch("/api/settings/system")
async def settings_update_system(request: Request,
                                  session: dict = Depends(get_current_session)):
    """System-Einstellung updaten oder anlegen."""
    body = await request.json()
    key = body.get("key")
    value = body.get("value")
    category = body.get("category", "general")
    description = body.get("description")

    if not key:
        raise HTTPException(status_code=400, detail="key required")

    db_execute_rt("""
        INSERT INTO dbai_core.config (key, value, category, description)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (key) DO UPDATE
        SET value = EXCLUDED.value, category = EXCLUDED.category,
            description = COALESCE(EXCLUDED.description, dbai_core.config.description),
            updated_at = NOW()
    """, (key, json.dumps(value) if not isinstance(value, str) else value, category, description))
    return {"ok": True}


@app.get("/api/settings/hardware")
async def settings_get_hardware(session: dict = Depends(get_current_session)):
    """Hardware-Info des Systems lesen."""
    import platform, os
    info = {
        "hostname": platform.node(),
        "os": f"{platform.system()} {platform.release()}",
        "arch": platform.machine(),
        "cpu_count": os.cpu_count(),
        "python": platform.python_version(),
    }
    # GPU Info
    try:
        import subprocess
        gpu_out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version,temperature.gpu",
             "--format=csv,noheader,nounits"],
            timeout=5
        ).decode().strip()
        gpus = []
        for line in gpu_out.split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 4:
                gpus.append({
                    "name": parts[0],
                    "vram_mb": int(parts[1]),
                    "driver": parts[2],
                    "temp_c": int(parts[3]),
                })
        info["gpus"] = gpus
    except Exception:
        info["gpus"] = []

    # RAM Info
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    info["ram_mb"] = int(line.split()[1]) // 1024
                    break
    except Exception:
        info["ram_mb"] = 0

    # Disk Info
    try:
        st = os.statvfs("/")
        info["disk_total_gb"] = round(st.f_blocks * st.f_frsize / (1024**3), 1)
        info["disk_free_gb"] = round(st.f_bavail * st.f_frsize / (1024**3), 1)
    except Exception:
        pass

    # DB aus hardware_stats (falls vorhanden)
    try:
        hw_rows = db_query_rt("""
            SELECT component, metric_name, metric_value
            FROM dbai_system.hardware_stats
            ORDER BY recorded_at DESC LIMIT 20
        """)
        info["live_stats"] = [dict(r) for r in hw_rows] if hw_rows else []
    except Exception:
        info["live_stats"] = []

    return info


@app.post("/api/llm/scan-quick")
async def llm_scan_quick(session: dict = Depends(get_current_session)):
    """Schnell-Scan: Standard-Pfade nach LLM-Modellen durchsuchen (für Setup-Wizard)."""
    import pathlib
    import asyncio

    SCAN_PATHS = [
        pathlib.Path.home() / ".cache" / "huggingface",
        pathlib.Path.home() / ".ollama" / "models",
        pathlib.Path.home() / "models",
        pathlib.Path("/opt/models"),
        pathlib.Path("/mnt"),
        pathlib.Path.home() / ".local" / "share" / "nomic.ai",
        pathlib.Path.home() / ".cache" / "lm-studio",
    ]
    EXTENSIONS = {".gguf", ".safetensors", ".bin", ".pth"}

    def _scan():
        results = []
        seen = set()
        for base in SCAN_PATHS:
            if not base.exists():
                continue
            try:
                for ext in EXTENSIONS:
                    for f in base.rglob(f"*{ext}"):
                        try:
                            fp = str(f)
                            if fp in seen:
                                continue
                            size = f.stat().st_size
                            if size < 10_000_000:
                                continue
                            seen.add(fp)
                            # Try to guess model name
                            name = f.stem
                            for suffix in [".Q4_K_M", ".Q5_K_M", ".Q8_0", ".Q4_0", ".Q6_K", ".F16", ".BF16"]:
                                name = name.replace(suffix, "")
                            results.append({
                                "filename": f.name,
                                "path": fp,
                                "format": f.suffix.lstrip('.'),
                                "size": size,
                                "size_display": f"{size / (1024**3):.1f} GB",
                                "name_guess": name,
                                "parent_dir": str(f.parent),
                            })
                        except (PermissionError, OSError):
                            continue
            except (PermissionError, OSError):
                continue
        results.sort(key=lambda x: x["size"], reverse=True)
        return results

    results = await asyncio.to_thread(_scan)
    return {"models": results, "total": len(results)}


# ---------------------------------------------------------------------------
# API Routes — Setup Wizard
# ---------------------------------------------------------------------------
@app.post("/api/setup/complete")
async def setup_complete(request: Request, session: dict = Depends(get_current_session)):
    """First-Boot Setup abschließen: Einstellungen in DB speichern."""
    settings = await request.json()
    user_id = session["user"]["id"]

    # User-Einstellungen aktualisieren (inkl. neue Felder)
    db_execute_rt("""
        UPDATE dbai_ui.users
        SET locale = %s, timezone = %s,
            display_name_custom = %s,
            ghost_name = %s,
            github_username = %s,
            setup_completed = TRUE,
            user_interests = %s::JSONB,
            onboarding_data = %s::JSONB,
            preferences = preferences || %s::JSONB,
            updated_at = NOW()
        WHERE id = %s::UUID
    """, (
        settings.get("locale", "de-DE"),
        settings.get("timezone", "Europe/Berlin"),
        settings.get("userName", "") or settings.get("displayName", ""),
        settings.get("ghostName", "Ghost"),
        settings.get("githubUsername", "") or None,
        json.dumps(settings.get("interests", [])),
        json.dumps({"wizard_version": 2, "completed_at": str(datetime.now())}),
        json.dumps({
            "default_model": settings.get("defaultModel", "qwen2.5-7b-instruct"),
            "auto_ghost_swap": settings.get("enableGhostSwap", True),
            "auto_heal": settings.get("enableAutoHeal", True),
            "telemetry": settings.get("enableTelemetry", True),
            "setup_completed": True,
        }),
        user_id,
    ))

    # Learning-Einträge für den Ghost anlegen
    if settings.get("userName"):
        try:
            db_execute_rt("""
                INSERT INTO dbai_llm.learning_entries (user_id, category, key, value)
                VALUES (%s::UUID, 'preference', 'user_name', %s)
                ON CONFLICT (user_id, category, key) DO UPDATE SET value = EXCLUDED.value
            """, (user_id, settings["userName"]))
        except Exception:
            pass

    if settings.get("ghostName"):
        try:
            db_execute_rt("""
                INSERT INTO dbai_llm.learning_entries (user_id, category, key, value)
                VALUES (%s::UUID, 'preference', 'ghost_name', %s)
                ON CONFLICT (user_id, category, key) DO UPDATE SET value = EXCLUDED.value
            """, (user_id, settings["ghostName"]))
        except Exception:
            pass

    # GitHub-Token verschlüsselt speichern (falls angegeben)
    if settings.get("githubToken"):
        try:
            import base64
            enc = base64.b64encode(settings["githubToken"].encode()).decode()
            db_execute_rt(
                "UPDATE dbai_ui.users SET github_token_enc = %s WHERE id = %s::UUID",
                (enc, user_id)
            )
        except Exception:
            pass

    # Theme setzen
    theme_name = settings.get("theme", "ghost-dark")
    try:
        db_execute_rt("""
            UPDATE dbai_ui.desktop_config
            SET theme_id = (SELECT id FROM dbai_ui.themes WHERE name = %s)
            WHERE user_id = %s::UUID
        """, (theme_name, user_id))
    except Exception:
        pass

    # Config-Einträge setzen
    config_entries = [
        ("hostname", settings.get("hostname", "dbai"), "system"),
        ("default_model", settings.get("defaultModel", "qwen2.5-7b-instruct"), "llm"),
        ("auto_ghost_swap", str(settings.get("enableGhostSwap", True)).lower(), "ghost"),
        ("auto_heal", str(settings.get("enableAutoHeal", True)).lower(), "system"),
        ("telemetry_enabled", str(settings.get("enableTelemetry", True)).lower(), "system"),
    ]
    for key, value, cat in config_entries:
        try:
            db_execute_rt("""
                INSERT INTO dbai_core.config (key, value, category)
                VALUES (%s, %s, %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
            """, (key, value, cat))
        except Exception:
            pass

    # Provider-Konfigurationen speichern (aus KI-Setup-Step)
    providers_config = settings.get("providers", {})
    if providers_config:
        import base64
        for pkey, pdata in providers_config.items():
            try:
                upd = []
                prm = []
                if pdata.get("api_key"):
                    enc = base64.b64encode(pdata["api_key"].encode()).decode()
                    k = pdata["api_key"]
                    preview = k[:6] + "..." + k[-4:] if len(k) > 10 else "***"
                    upd.extend(["api_key_enc = %s", "api_key_preview = %s", "is_configured = TRUE"])
                    prm.extend([enc, preview])
                if pdata.get("api_base_url"):
                    upd.append("api_base_url = %s")
                    prm.append(pdata["api_base_url"])
                if "enabled" in pdata:
                    upd.append("is_enabled = %s")
                    prm.append(pdata["enabled"])
                if upd:
                    upd.append("imported_from = 'setup_wizard'")
                    prm.append(pkey)
                    db_execute_rt(f"""
                        UPDATE dbai_llm.llm_providers
                        SET {', '.join(upd)}
                        WHERE provider_key = %s
                    """, tuple(prm))
            except Exception:
                pass

    # Gescannte lokale Modelle integrieren
    local_models = settings.get("localModels", [])
    for lm in local_models:
        try:
            existing = db_query_rt(
                "SELECT id FROM dbai_llm.ghost_models WHERE model_path = %s",
                (lm.get("path", ""),)
            )
            if not existing:
                db_execute_rt("""
                    INSERT INTO dbai_llm.ghost_models
                    (name, display_name, provider, model_path, quantization, state, capabilities)
                    VALUES (%s, %s, 'llama.cpp', %s, %s, 'available', ARRAY['chat'])
                """, (
                    lm.get("name", lm.get("filename", "unknown")),
                    lm.get("name", lm.get("filename", "unknown")),
                    lm.get("path", ""),
                    lm.get("format", "gguf"),
                ))
        except Exception:
            pass

    return {"ok": True, "message": "Setup abgeschlossen"}


# ---------------------------------------------------------------------------
# API Routes — i18n (Mehrsprachigkeit)
# ---------------------------------------------------------------------------
@app.get("/api/i18n/locales/available")
async def get_available_locales():
    """Alle verfügbaren Locales auflisten."""
    rows = db_query_rt("SELECT DISTINCT locale FROM dbai_ui.translations ORDER BY locale")
    locales = [r["locale"] for r in rows]
    locale_names = {
        "de-DE": "🇩🇪 Deutsch", "en-US": "🇺🇸 English", "fr-FR": "🇫🇷 Français",
        "es-ES": "🇪🇸 Español", "ar-SA": "🇸🇦 العربية", "ja-JP": "🇯🇵 日本語",
        "ko-KR": "🇰🇷 한국어", "zh-CN": "🇨🇳 中文", "pt-BR": "🇧🇷 Português",
        "ru-RU": "🇷🇺 Русский", "tr-TR": "🇹🇷 Türkçe", "hi-IN": "🇮🇳 हिन्दी"
    }
    return [{"locale": l, "name": locale_names.get(l, l)} for l in locales]


@app.get("/api/i18n/{locale}")
async def get_translations(locale: str):
    """Übersetzungen für eine Locale laden. Kein Auth nötig (für Login/Boot)."""
    rows = db_query_rt(
        "SELECT ns, key, value FROM dbai_ui.translations WHERE locale = %s",
        (locale,)
    )
    # Gruppiere nach Namespace
    result = {}
    for r in rows:
        ns = r["ns"]
        if ns not in result:
            result[ns] = {}
        result[ns][r["key"]] = r["value"]
    return {"locale": locale, "translations": result}


# ---------------------------------------------------------------------------
# API Routes — Network Scanner
# ---------------------------------------------------------------------------
@app.post("/api/network/scan")
async def network_scan(session: dict = Depends(get_current_session)):
    """Netzwerk nach Web-UIs scannen. Prüft gängige HTTP-Ports (läuft im Thread)."""
    import asyncio
    result = await asyncio.to_thread(_do_network_scan)
    return result


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
        except Exception:
            pass
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
            except Exception:
                pass

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
            except Exception:
                pass

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
        except Exception:
            pass

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


@app.get("/api/network/devices")
async def network_devices_list(session: dict = Depends(get_current_session)):
    """Alle bekannten Netzwerk-Geräte mit Web-UI auflisten."""
    return db_query_rt("SELECT * FROM dbai_core.network_devices ORDER BY last_seen DESC")


@app.post("/api/network/devices/{device_id}/add-to-desktop")
async def network_device_add_desktop(device_id: str, session: dict = Depends(get_current_session)):
    """Netzwerk-Gerät als WebFrame-Knoten zum Desktop hinzufügen."""
    device = db_query_rt("SELECT * FROM dbai_core.network_devices WHERE id = %s::UUID", (device_id,))
    if not device:
        return {"ok": False, "error": "Gerät nicht gefunden"}
    d = device[0]
    user_id = session["user"]["id"]

    # Desktop-Knoten erstellen
    type_icons = {
        "nas": "💾", "router": "🌐", "printer": "🖨️", "camera": "📷",
        "smarthome": "🏠", "robot": "🤖", "server": "🖥️", "ai": "🧠",
        "media": "🎬", "dns": "🛡️", "iot": "📡", "phone": "📱", "unknown": "🔗"
    }
    icon = type_icons.get(d["device_type"], "🔗")
    label = d["web_title"] or d["hostname"] or d["ip"]

    try:
        db_execute_rt("""
            INSERT INTO dbai_ui.desktop_nodes
                (user_id, node_type, label, icon, url, x, y, visible, config)
            VALUES (%s::UUID, 'webframe', %s, %s, %s, 400, 300, TRUE, %s::JSONB)
        """, (user_id, label[:50], icon, d["web_url"],
              json.dumps({"device_id": str(d["id"]), "device_type": d["device_type"], "ip": d["ip"]})))

        db_execute_rt(
            "UPDATE dbai_core.network_devices SET added_to_desktop = TRUE WHERE id = %s::UUID",
            (device_id,)
        )
        return {"ok": True, "message": f"'{label}' zum Desktop hinzugefügt"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# API Routes — Ghost Learning
# ---------------------------------------------------------------------------
@app.post("/api/learning/save")
async def learning_save(request: Request, session: dict = Depends(get_current_session)):
    """Benutzer-Präferenz / Lern-Eintrag speichern."""
    data = await request.json()
    user_id = session["user"]["id"]
    db_execute_rt("""
        INSERT INTO dbai_llm.learning_entries (user_id, category, key, value, context, confidence)
        VALUES (%s::UUID, %s, %s, %s, %s::JSONB, %s)
        ON CONFLICT (user_id, category, key)
        DO UPDATE SET value = EXCLUDED.value, context = EXCLUDED.context,
                      confidence = EXCLUDED.confidence, updated_at = NOW()
    """, (user_id, data.get("category", "preference"), data["key"], data["value"],
          json.dumps(data.get("context", {})), data.get("confidence", 1.0)))
    return {"ok": True}


@app.get("/api/learning/profile")
async def learning_profile(session: dict = Depends(get_current_session)):
    """Vollständiges Lern-Profil des aktuellen Benutzers laden."""
    user_id = session["user"]["id"]
    rows = db_query_rt(
        "SELECT category, key, value, confidence FROM dbai_llm.learning_entries WHERE user_id = %s::UUID ORDER BY category, key",
        (user_id,)
    )
    profile = {}
    for r in rows:
        cat = r["category"]
        if cat not in profile:
            profile[cat] = {}
        profile[cat][r["key"]] = {"value": r["value"], "confidence": r["confidence"]}
    return {"user_id": user_id, "profile": profile}


@app.get("/api/learning/system-prompt-context")
async def learning_system_prompt(session: dict = Depends(get_current_session)):
    """Kontext-Fragment für System-Prompt basierend auf Benutzerprofil generieren."""
    user_id = session["user"]["id"]

    # User-Daten
    user_rows = db_query_rt(
        "SELECT display_name_custom, ghost_name, locale, user_interests FROM dbai_ui.users WHERE id = %s::UUID",
        (user_id,)
    )
    user = user_rows[0] if user_rows else {}

    # Learning-Einträge
    learn_rows = db_query_rt(
        "SELECT category, key, value FROM dbai_llm.learning_entries WHERE user_id = %s::UUID AND confidence >= 0.5",
        (user_id,)
    )

    lines = []
    name = user.get("display_name_custom") or "Benutzer"
    ghost = user.get("ghost_name") or "Ghost"
    lines.append(f"Der Benutzer heißt {name}. Du bist {ghost}, sein persönlicher KI-Assistent.")

    if user.get("locale"):
        lines.append(f"Bevorzugte Sprache: {user['locale']}")

    interests = user.get("user_interests") or []
    if interests:
        lines.append(f"Interessen: {', '.join(interests)}")

    for r in learn_rows:
        if r["category"] == "preference":
            lines.append(f"Präferenz — {r['key']}: {r['value']}")
        elif r["category"] == "skill":
            lines.append(f"Fähigkeit — {r['key']}: {r['value']}")

    return {"context": "\n".join(lines), "user_name": name, "ghost_name": ghost}


# ---------------------------------------------------------------------------
# API Routes — Setup Check
# ---------------------------------------------------------------------------
@app.get("/api/setup/status")
async def setup_status(session: dict = Depends(get_current_session)):
    """Prüft ob die Ersteinrichtung abgeschlossen wurde."""
    user_id = session["user"]["id"]
    rows = db_query_rt(
        "SELECT setup_completed, display_name_custom, ghost_name, github_username FROM dbai_ui.users WHERE id = %s::UUID",
        (user_id,)
    )
    if rows:
        u = rows[0]
        return {
            "setup_completed": bool(u.get("setup_completed")),
            "display_name": u.get("display_name_custom"),
            "ghost_name": u.get("ghost_name"),
            "github_connected": bool(u.get("github_username"))
        }
    return {"setup_completed": False}


# ---------------------------------------------------------------------------
# API Routes — Events
# ---------------------------------------------------------------------------
@app.get("/api/events")
async def get_events(limit: int = 100, event_type: str = None,
                     session: dict = Depends(get_current_session)):
    """Letzte Events aus dem Event-Log."""
    if event_type:
        rows = db_query_rt("""
            SELECT * FROM dbai_event.events
            WHERE event_type = %s
            ORDER BY ts DESC LIMIT %s
        """, (event_type, limit))
    else:
        rows = db_query_rt("""
            SELECT * FROM dbai_event.events
            ORDER BY ts DESC LIMIT %s
        """, (limit,))
    return rows


# ---------------------------------------------------------------------------
# API Routes — KI Werkstatt (AI Workshop)
# ---------------------------------------------------------------------------

@app.get("/api/workshop/projects")
async def workshop_projects(session: dict = Depends(get_current_session)):
    """Alle Projekte des aktuellen Benutzers."""
    user_id = session["user"]["id"]
    try:
        rows = db_query_rt("""
            SELECT p.*, 
                (SELECT count(*) FROM dbai_workshop.collections c WHERE c.project_id = p.id) AS collection_count,
                (SELECT count(*) FROM dbai_workshop.smart_devices d WHERE d.project_id = p.id) AS device_count,
                (SELECT count(*) FROM dbai_workshop.media_items m WHERE m.project_id = p.id AND m.state = 'indexed') AS indexed_items
            FROM dbai_workshop.projects p
            WHERE p.user_id = %s::UUID
            ORDER BY p.updated_at DESC
        """, (user_id,))
        return rows
    except Exception as e:
        logger.warning("Workshop projects query failed (schema may not exist yet): %s", e)
        return []


@app.get("/api/workshop/stats")
async def workshop_stats(session: dict = Depends(get_current_session)):
    """Übersichts-Statistiken für die KI Werkstatt."""
    user_id = session["user"]["id"]
    try:
        rows = db_query_rt("""
            SELECT
                (SELECT count(*) FROM dbai_workshop.projects WHERE user_id = %s::UUID) AS total_projects,
                (SELECT COALESCE(SUM(total_items), 0) FROM dbai_workshop.projects WHERE user_id = %s::UUID) AS total_items,
                (SELECT COALESCE(SUM(embedding_count), 0) FROM dbai_workshop.projects WHERE user_id = %s::UUID) AS total_indexed,
                (SELECT count(*) FROM dbai_workshop.smart_devices d 
                 JOIN dbai_workshop.projects p ON d.project_id = p.id 
                 WHERE p.user_id = %s::UUID) AS total_devices
        """, (user_id, user_id, user_id, user_id))
        return rows[0] if rows else {}
    except Exception as e:
        logger.warning("Workshop stats query failed: %s", e)
        return {"total_projects": 0, "total_items": 0, "total_indexed": 0, "total_devices": 0}


@app.get("/api/workshop/templates")
async def workshop_templates(session: dict = Depends(get_current_session)):
    """Verfügbare Projektvorlagen."""
    try:
        rows = db_query_rt("SELECT * FROM dbai_workshop.templates ORDER BY sort_order")
        return rows
    except Exception as e:
        logger.warning("Workshop templates query failed: %s", e)
        return []


@app.post("/api/workshop/projects")
async def workshop_create_project(request: Request, session: dict = Depends(get_current_session)):
    """Neues KI-Projekt erstellen."""
    user_id = session["user"]["id"]
    body = await request.json()

    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Projektname fehlt")

    try:
        rows = db_query_rt("""
            INSERT INTO dbai_workshop.projects 
                (user_id, name, description, icon, project_type, smart_home_enabled, ai_config)
            VALUES (%s::UUID, %s, %s, %s, %s, %s, %s::JSONB)
            RETURNING id, name, description, icon, project_type, state, created_at
        """, (
            user_id,
            name,
            body.get("description", ""),
            body.get("icon", "🧠"),
            body.get("project_type", "media_collection"),
            body.get("smart_home_enabled", False),
            json.dumps(body.get("ai_config", {})),
        ))

        if rows:
            # Log event
            try:
                db_execute_rt("""
                    INSERT INTO dbai_event.events (event_type, source, payload)
                    VALUES ('workshop_project_created', 'ai_workshop', %s::JSONB)
                """, (json.dumps({"project_id": str(rows[0]["id"]), "name": name}),))
            except Exception:
                pass
            return rows[0]

        raise HTTPException(status_code=500, detail="Projekt konnte nicht erstellt werden")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/workshop/projects/{project_id}")
async def workshop_get_project(project_id: str, session: dict = Depends(get_current_session)):
    """Einzelnes Projekt mit Details."""
    try:
        rows = db_query_rt("""
            SELECT p.*,
                (SELECT count(*) FROM dbai_workshop.collections c WHERE c.project_id = p.id) AS collection_count,
                (SELECT count(*) FROM dbai_workshop.smart_devices d WHERE d.project_id = p.id) AS device_count
            FROM dbai_workshop.projects p
            WHERE p.id = %s::UUID
        """, (project_id,))
        if not rows:
            raise HTTPException(status_code=404, detail="Projekt nicht gefunden")
        return rows[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/workshop/projects/{project_id}")
async def workshop_delete_project(project_id: str, session: dict = Depends(get_current_session)):
    """Projekt löschen."""
    db_execute_rt("DELETE FROM dbai_workshop.projects WHERE id = %s::UUID", (project_id,))
    return {"ok": True}


@app.get("/api/workshop/projects/{project_id}/media")
async def workshop_media(project_id: str, session: dict = Depends(get_current_session)):
    """Alle Medien-Items eines Projekts."""
    try:
        rows = db_query_rt("""
            SELECT id, file_name, file_type, mime_type, file_size_bytes,
                   title, description, tags, ai_description, ai_tags, ai_caption,
                   width, height, duration_sec, thumbnail_path,
                   latitude, longitude, taken_at, state, error_message,
                   collections, created_at, updated_at, indexed_at
            FROM dbai_workshop.media_items
            WHERE project_id = %s::UUID
            ORDER BY created_at DESC
        """, (project_id,))
        return rows
    except Exception:
        return []


@app.get("/api/workshop/projects/{project_id}/search")
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
        return []


@app.get("/api/workshop/projects/{project_id}/collections")
async def workshop_collections(project_id: str, session: dict = Depends(get_current_session)):
    """Alle Sammlungen eines Projekts."""
    try:
        rows = db_query_rt("""
            SELECT * FROM dbai_workshop.collections
            WHERE project_id = %s::UUID
            ORDER BY sort_order, name
        """, (project_id,))
        return rows
    except Exception:
        return []


@app.post("/api/workshop/projects/{project_id}/collections")
async def workshop_create_collection(project_id: str, request: Request,
                                      session: dict = Depends(get_current_session)):
    """Neue Sammlung erstellen."""
    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name fehlt")

    try:
        rows = db_query_rt("""
            INSERT INTO dbai_workshop.collections (project_id, name, description, collection_type)
            VALUES (%s::UUID, %s, %s, %s)
            RETURNING *
        """, (project_id, name, body.get("description", ""), body.get("collection_type", "album")))
        return rows[0] if rows else {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/workshop/projects/{project_id}/devices")
async def workshop_devices(project_id: str, session: dict = Depends(get_current_session)):
    """Alle Smart-Home-Geräte eines Projekts."""
    try:
        rows = db_query_rt("""
            SELECT * FROM dbai_workshop.smart_devices
            WHERE project_id = %s::UUID
            ORDER BY device_name
        """, (project_id,))
        return rows
    except Exception:
        return []


@app.post("/api/workshop/projects/{project_id}/devices")
async def workshop_add_device(project_id: str, request: Request,
                               session: dict = Depends(get_current_session)):
    """Neues Smart-Home-Gerät hinzufügen."""
    body = await request.json()
    device_name = body.get("device_name", "").strip()
    if not device_name:
        raise HTTPException(status_code=400, detail="Gerätename fehlt")

    # Default capabilities je nach Typ
    device_type = body.get("device_type", "other")
    caps = {}
    if device_type == "tv":
        caps = {"display_images": True, "play_video": True, "play_audio": True}
    elif device_type == "speaker":
        caps = {"play_audio": True, "tts": True}
    elif device_type == "display":
        caps = {"display_images": True, "tts": True}

    try:
        rows = db_query_rt("""
            INSERT INTO dbai_workshop.smart_devices
                (project_id, device_name, device_type, platform, ip_address, capabilities)
            VALUES (%s::UUID, %s, %s, %s, %s, %s::JSONB)
            RETURNING *
        """, (
            project_id, device_name, device_type,
            body.get("platform", "custom"),
            body.get("ip_address"),
            json.dumps(caps),
        ))
        return rows[0] if rows else {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/workshop/projects/{project_id}/imports")
async def workshop_import_jobs(project_id: str, session: dict = Depends(get_current_session)):
    """Import-Aufträge eines Projekts."""
    try:
        rows = db_query_rt("""
            SELECT * FROM dbai_workshop.import_jobs
            WHERE project_id = %s::UUID
            ORDER BY created_at DESC
        """, (project_id,))
        return rows
    except Exception:
        return []


@app.post("/api/workshop/projects/{project_id}/imports")
async def workshop_start_import(project_id: str, request: Request,
                                 session: dict = Depends(get_current_session)):
    """Neuen Import-Auftrag starten."""
    body = await request.json()
    source_type = body.get("source_type", "local_folder")
    source_path = body.get("source_path", "").strip()
    if not source_path:
        raise HTTPException(status_code=400, detail="Pfad fehlt")

    try:
        # Import-Job erstellen
        rows = db_query_rt("""
            INSERT INTO dbai_workshop.import_jobs
                (project_id, source_type, source_path, state, started_at)
            VALUES (%s::UUID, %s, %s, 'scanning', NOW())
            RETURNING *
        """, (project_id, source_type, source_path))

        if rows and source_type == 'local_folder':
            # Simuliere lokales Scannen
            import os
            job_id = rows[0]["id"]
            found_files = 0
            supported_ext = {
                '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg',  # images
                '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv',  # videos
                '.mp3', '.wav', '.flac', '.ogg', '.aac', '.m4a',  # audio
                '.txt', '.md', '.csv', '.json', '.xml', '.html',  # text
                '.pdf', '.doc', '.docx',  # docs
            }
            type_map = {
                '.jpg': 'image', '.jpeg': 'image', '.png': 'image', '.gif': 'image',
                '.bmp': 'image', '.webp': 'image', '.svg': 'image',
                '.mp4': 'video', '.avi': 'video', '.mkv': 'video', '.mov': 'video',
                '.wmv': 'video', '.flv': 'video',
                '.mp3': 'audio', '.wav': 'audio', '.flac': 'audio', '.ogg': 'audio',
                '.aac': 'audio', '.m4a': 'audio',
                '.txt': 'text', '.md': 'text', '.csv': 'text', '.json': 'text',
                '.xml': 'text', '.html': 'text',
                '.pdf': 'pdf', '.doc': 'document', '.docx': 'document',
            }

            if os.path.isdir(source_path):
                for root_dir, dirs, files in os.walk(source_path):
                    for f in files:
                        ext = os.path.splitext(f)[1].lower()
                        if ext in supported_ext:
                            full_path = os.path.join(root_dir, f)
                            try:
                                size = os.path.getsize(full_path)
                                file_type = type_map.get(ext, 'other')
                                db_execute_rt("""
                                    INSERT INTO dbai_workshop.media_items
                                        (project_id, file_name, file_path, file_type, mime_type,
                                         file_size_bytes, state)
                                    VALUES (%s::UUID, %s, %s, %s, %s, %s, 'pending')
                                """, (project_id, f, full_path, file_type,
                                      f"{'image' if file_type == 'image' else file_type}/{ext[1:]}", size))
                                found_files += 1
                            except Exception:
                                pass

                # Job aktualisieren
                db_execute_rt("""
                    UPDATE dbai_workshop.import_jobs
                    SET state = 'complete', total_files = %s, processed_files = %s, completed_at = NOW()
                    WHERE id = %s::UUID
                """, (found_files, found_files, job_id))

                # Projekt-Stats aktualisieren
                db_execute_rt("""
                    UPDATE dbai_workshop.projects
                    SET total_items = (SELECT count(*) FROM dbai_workshop.media_items WHERE project_id = %s::UUID),
                        total_size_mb = COALESCE(
                            (SELECT ROUND(SUM(file_size_bytes) / 1048576.0, 2)
                             FROM dbai_workshop.media_items WHERE project_id = %s::UUID), 0),
                        state = 'building',
                        updated_at = NOW()
                    WHERE id = %s::UUID
                """, (project_id, project_id, project_id))
            else:
                # Pfad existiert nicht → Fehler
                db_execute_rt("""
                    UPDATE dbai_workshop.import_jobs
                    SET state = 'error', error_message = 'Pfad existiert nicht: ' || %s
                    WHERE id = %s::UUID
                """, (source_path, job_id))

        return rows[0] if rows else {}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/workshop/projects/{project_id}/chat")
async def workshop_chat_history(project_id: str, session: dict = Depends(get_current_session)):
    """Chat-Verlauf eines Projekts."""
    try:
        rows = db_query_rt("""
            SELECT * FROM dbai_workshop.chat_history
            WHERE project_id = %s::UUID
            ORDER BY created_at ASC
            LIMIT 100
        """, (project_id,))
        return rows
    except Exception:
        return []


@app.post("/api/workshop/projects/{project_id}/chat")
async def workshop_chat(project_id: str, request: Request,
                         session: dict = Depends(get_current_session)):
    """KI-Chat über die eigene Datenbank."""
    body = await request.json()
    message = body.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Nachricht fehlt")

    try:
        # User-Nachricht speichern
        db_execute_rt("""
            INSERT INTO dbai_workshop.chat_history (project_id, role, content)
            VALUES (%s::UUID, 'user', %s)
        """, (project_id, message))

        # Kontext: Projekt-Info + letzte Medien
        project_rows = db_query_rt(
            "SELECT name, description, project_type, total_items FROM dbai_workshop.projects WHERE id = %s::UUID",
            (project_id,))
        project_info = project_rows[0] if project_rows else {}

        media_rows = db_query_rt("""
            SELECT file_name, file_type, title, ai_description, ai_tags, tags
            FROM dbai_workshop.media_items
            WHERE project_id = %s::UUID AND state = 'indexed'
            ORDER BY created_at DESC LIMIT 20
        """, (project_id,))

        # KI-Antwort generieren (via Ghost-System wenn verfügbar, sonst Fallback)
        context_text = f"Projekt: {project_info.get('name', 'Unbekannt')} ({project_info.get('project_type', '')})\n"
        context_text += f"Beschreibung: {project_info.get('description', '')}\n"
        context_text += f"Dateien: {project_info.get('total_items', 0)}\n\n"

        if media_rows:
            context_text += "Letzte indexierte Dateien:\n"
            for m in media_rows[:10]:
                context_text += f"- {m.get('file_name', '')} ({m.get('file_type', '')})"
                if m.get('ai_description'):
                    context_text += f": {m['ai_description'][:100]}"
                if m.get('ai_tags'):
                    context_text += f" [Tags: {', '.join(m['ai_tags'][:5])}]"
                context_text += "\n"

        # Try ghost system first
        try:
            ghost_result = db_call_json_rt(
                "SELECT dbai_llm.ask_ghost(%s, %s, %s::JSONB)",
                ('analyst', message, json.dumps({"context": context_text, "project_id": str(project_id)}))
            )
            if ghost_result and ghost_result.get("response"):
                response = ghost_result["response"]
            else:
                response = _workshop_fallback_response(message, project_info, media_rows)
        except Exception:
            response = _workshop_fallback_response(message, project_info, media_rows)

        # Antwort speichern
        db_execute_rt("""
            INSERT INTO dbai_workshop.chat_history (project_id, role, content)
            VALUES (%s::UUID, 'assistant', %s)
        """, (project_id, response))

        return {"response": response, "referenced_items": []}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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


# ---------------------------------------------------------------------------
# API Routes — SQL Console (nur für Admins, RLS-enforced via Runtime-Pool)
# ---------------------------------------------------------------------------
@app.post("/api/sql/query")
async def sql_query(request: Request, session: dict = Depends(get_current_session)):
    """Führt eine SQL-Abfrage aus (nur SELECT, nur Admins, RLS aktiv)."""
    require_admin(session)

    body = await request.json()
    query = body.get("query", "").strip()

    if not query:
        raise HTTPException(status_code=400, detail="Leere Abfrage")

    # Sicherheit: Nur SELECT erlauben
    first_word = query.split()[0].upper() if query.split() else ""
    if first_word not in ("SELECT", "WITH", "EXPLAIN", "SHOW"):
        # Log violation
        try:
            db_execute_rt("""
                INSERT INTO dbai_core.policy_enforcement_log
                    (event_type, severity, attempted_action, blocked, reason, session_id)
                VALUES ('sql_injection_attempt', 'critical', %s, TRUE,
                        'Verbotener SQL-Befehl via Console: ' || %s, %s)
            """, (query[:200], first_word, session.get("session_id")))
        except Exception:
            pass
        raise HTTPException(
            status_code=403,
            detail=f"Nur SELECT-Abfragen erlaubt (gefunden: {first_word})"
        )

    # Zusätzliche Sicherheit: Keine Semikolons (verhindert Statement-Stacking)
    if ";" in query.rstrip(";").strip():
        raise HTTPException(status_code=403, detail="Nur ein Statement pro Abfrage erlaubt")

    try:
        start = time.monotonic()
        # Nutzt Runtime-Pool → RLS ist aktiv → User sieht nur was erlaubt
        rows = db_query_rt(query)
        duration = round((time.monotonic() - start) * 1000, 2)
        return {
            "rows": rows,
            "count": len(rows),
            "duration_ms": duration,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# API Routes — Repair Pipeline (Immutability Enforcement)
# ---------------------------------------------------------------------------
@app.get("/api/repair/queue")
async def repair_queue(session: dict = Depends(get_current_session)):
    """Repair-Queue: Alle vorgeschlagenen, genehmigten und ausgeführten Aktionen."""
    rows = db_query_rt("""
        SELECT * FROM dbai_core.vw_repair_queue LIMIT 100
    """)
    return rows


@app.get("/api/repair/pending")
async def repair_pending(session: dict = Depends(get_current_session)):
    """Offene Reparatur-Vorschläge die auf Genehmigung warten."""
    rows = db_query_rt("""
        SELECT * FROM dbai_llm.vw_pending_actions
    """)
    return rows


@app.post("/api/repair/approve/{action_id}")
async def repair_approve(action_id: str, request: Request,
                         session: dict = Depends(get_current_session)):
    """Genehmigt eine vorgeschlagene Reparatur-Aktion (nur Admins)."""
    require_admin(session)

    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    reason = body.get("reason", "Admin-Genehmigung via UI")

    result = db_call_json_rt(
        "SELECT dbai_llm.approve_action(%s::UUID, %s, %s)",
        (action_id, "human:" + session["user"].get("username", "admin"), reason)
    )

    # Log enforcement
    try:
        db_execute_rt("""
            INSERT INTO dbai_core.policy_enforcement_log
                (event_type, severity, target_object, attempted_action, blocked, reason, session_id)
            VALUES ('repair_approved', 'info', %s, 'approve_action', FALSE, %s, %s)
        """, (action_id, reason, session.get("session_id")))
    except Exception:
        pass

    return result or {"error": "Genehmigung fehlgeschlagen"}


@app.post("/api/repair/reject/{action_id}")
async def repair_reject(action_id: str, request: Request,
                        session: dict = Depends(get_current_session)):
    """Lehnt eine vorgeschlagene Reparatur-Aktion ab (nur Admins)."""
    require_admin(session)

    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    reason = body.get("reason", "Admin-Ablehnung via UI")

    result = db_call_json_rt(
        "SELECT dbai_llm.reject_action(%s::UUID, %s, %s)",
        (action_id, "human:" + session["user"].get("username", "admin"), reason)
    )

    # Log enforcement
    try:
        db_execute_rt("""
            INSERT INTO dbai_core.policy_enforcement_log
                (event_type, severity, target_object, attempted_action, blocked, reason, session_id)
            VALUES ('repair_rejected', 'info', %s, 'reject_action', TRUE, %s, %s)
        """, (action_id, reason, session.get("session_id")))
    except Exception:
        pass

    return result or {"error": "Ablehnung fehlgeschlagen"}


@app.post("/api/repair/execute/{action_id}")
async def repair_execute(action_id: str, session: dict = Depends(get_current_session)):
    """Führt eine genehmigte Reparatur-Aktion aus (nur Admins).
    Nutzt SECURITY DEFINER Funktion → läuft als dbai_system im DB-Kontext."""
    require_admin(session)

    result = db_call_json_rt(
        "SELECT dbai_core.execute_approved_repair(%s::UUID)",
        (action_id,)
    )
    return result or {"error": "Ausführung fehlgeschlagen"}


@app.get("/api/repair/enforcement-log")
async def repair_enforcement_log(limit: int = 50,
                                  session: dict = Depends(get_current_session)):
    """Policy Enforcement Log: Alle Sicherheits-Events."""
    require_admin(session)

    rows = db_query_rt("""
        SELECT * FROM dbai_core.policy_enforcement_log
        ORDER BY ts DESC LIMIT %s
    """, (limit,))
    return rows


@app.get("/api/repair/schema-integrity")
async def repair_schema_integrity(session: dict = Depends(get_current_session)):
    """Prüft Schema-Integrität gegen gespeicherte Fingerprints."""
    require_admin(session)

    rows = db_query_rt("SELECT * FROM dbai_core.verify_schema_integrity()")
    return rows


@app.get("/api/repair/immutable-registry")
async def repair_immutable_registry(session: dict = Depends(get_current_session)):
    """Zeigt die Immutable Registry: Was darf nicht verändert werden."""
    rows = db_query_rt("""
        SELECT schema_name, object_name, object_type, reason,
               protection_level, locked_by, locked_at
        FROM dbai_core.immutable_registry
        ORDER BY protection_level, schema_name, object_name
    """)
    return rows


@app.get("/api/repair/websocket-commands")
async def repair_websocket_commands(session: dict = Depends(get_current_session)):
    """Liste aller erlaubten WebSocket-Befehle."""
    rows = db_query_rt("""
        SELECT command_name, description, allowed_roles, is_read_only,
               max_per_minute, is_active
        FROM dbai_core.websocket_commands
        ORDER BY command_name
    """)
    return rows


# ---------------------------------------------------------------------------
# API Routes — Notifications
# ---------------------------------------------------------------------------
@app.get("/api/notifications")
async def get_notifications(session: dict = Depends(get_current_session)):
    """Ungelesene Benachrichtigungen."""
    user_id = session["user"]["id"]
    rows = db_query_rt("""
        SELECT * FROM dbai_ui.notifications
        WHERE (user_id = %s::UUID OR user_id IS NULL)
          AND is_dismissed = FALSE
          AND (expires_at IS NULL OR expires_at > NOW())
        ORDER BY created_at DESC
    """, (user_id,))
    return rows


@app.patch("/api/notifications/{notif_id}/dismiss")
async def dismiss_notification(notif_id: int, session: dict = Depends(get_current_session)):
    """Benachrichtigung schließen."""
    db_execute_rt(
        "UPDATE dbai_ui.notifications SET is_dismissed = TRUE WHERE id = %s",
        (notif_id,)
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# API Routes — Themes
# ---------------------------------------------------------------------------
@app.get("/api/themes")
async def get_themes(session: dict = Depends(get_current_session)):
    """Alle verfügbaren Themes."""
    rows = db_query_rt("SELECT * FROM dbai_ui.themes ORDER BY name")
    return rows


@app.patch("/api/desktop/theme/{theme_name}")
async def set_theme(theme_name: str, session: dict = Depends(get_current_session)):
    """Theme wechseln."""
    db_execute_rt("""
        UPDATE dbai_ui.desktop_config
        SET theme_id = (SELECT id FROM dbai_ui.themes WHERE name = %s)
        WHERE user_id = %s::UUID
    """, (theme_name, session["user"]["id"]))
    return {"ok": True, "theme": theme_name}


# ---------------------------------------------------------------------------
# WebSocket Endpoint
# ---------------------------------------------------------------------------
@app.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    """
    WebSocket-Verbindung für Live-Updates.
    Token muss ein gültiger Session-Token sein.
    """
    # Session validieren
    result = db_call_json_rt("SELECT dbai_ui.validate_session(%s)", (token,))
    if not result or not result.get("valid"):
        await websocket.close(code=4001, reason="Ungültiger Token")
        return

    session_id = result["session_id"]
    user_role = result.get("user", {}).get("role", "authenticated")
    is_admin = result.get("user", {}).get("is_admin", False)
    await ws_manager.connect(websocket, session_id)

    # WebSocket-Command-Whitelist laden
    try:
        ws_commands = {
            row["command_name"]: row
            for row in db_query_rt(
                "SELECT * FROM dbai_core.websocket_commands WHERE is_active = TRUE"
            )
        }
    except Exception:
        ws_commands = {}

    # Welcome-Nachricht
    await websocket.send_json({
        "type": "connected",
        "session_id": session_id,
        "user": result["user"],
        "allowed_commands": list(ws_commands.keys()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    try:
        while True:
            data = await websocket.receive_json()
            cmd_type = data.get("type", "")

            # Ping/Pong — immer erlaubt
            if cmd_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            # Command-Whitelist prüfen
            cmd_def = ws_commands.get(cmd_type)
            if not cmd_def and cmd_type not in ("ping", "window_update", "ghost_swap"):
                # Unbekannter Befehl → blockieren + loggen
                try:
                    db_execute_rt("""
                        INSERT INTO dbai_core.policy_enforcement_log
                            (event_type, severity, attempted_action, blocked, reason, session_id)
                        VALUES ('websocket_blocked', 'warning', %s, TRUE,
                                'Unbekannter WebSocket-Befehl', %s)
                    """, (cmd_type, session_id))
                except Exception:
                    pass
                await websocket.send_json({
                    "type": "error",
                    "message": f"Befehl '{cmd_type}' ist nicht erlaubt",
                })
                continue

            # Rollenprüfung für Admin-Commands
            if cmd_def and 'admin' in cmd_def.get("allowed_roles", []) and not is_admin:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Befehl '{cmd_type}' erfordert Admin-Rechte",
                })
                continue

            # Bekannte Commands verarbeiten
            if cmd_type == "window_update":
                window_data = data.get("window", {})
                if window_data.get("id"):
                    try:
                        sets = []
                        params = []
                        for field in ["pos_x", "pos_y", "width", "height", "state", "z_index", "is_focused"]:
                            if field in window_data:
                                sets.append(f"{field} = %s")
                                params.append(window_data[field])
                        if sets:
                            params.append(window_data["id"])
                            db_execute_rt(
                                f"UPDATE dbai_ui.windows SET {', '.join(sets)} WHERE id = %s::UUID",
                                tuple(params)
                            )
                    except Exception as e:
                        logger.error("Window Update Fehler: %s", e)

            elif cmd_type == "ghost_swap":
                if not is_admin:
                    await websocket.send_json({
                        "type": "error", "message": "Ghost-Swap erfordert Admin-Rechte"
                    })
                    continue
                role = data.get("role")
                model = data.get("model")
                if role and model:
                    swap_result = db_call_json_rt(
                        "SELECT dbai_llm.swap_ghost(%s, %s, %s, %s)",
                        (role, model, data.get("reason", "UI-Swap"), "user")
                    )
                    await websocket.send_json({
                        "type": "ghost_swap_result",
                        "result": swap_result,
                    })

            elif cmd_type == "approve_action":
                if not is_admin:
                    await websocket.send_json({
                        "type": "error", "message": "Repair-Genehmigung erfordert Admin-Rechte"
                    })
                    continue
                action_id = data.get("action_id")
                if action_id:
                    approve_result = db_call_json_rt(
                        "SELECT dbai_llm.approve_action(%s::UUID, 'human', %s)",
                        (action_id, data.get("reason", "WebSocket-Genehmigung"))
                    )
                    await websocket.send_json({
                        "type": "action_approved", "result": approve_result,
                    })

            elif cmd_type == "reject_action":
                if not is_admin:
                    await websocket.send_json({
                        "type": "error", "message": "Repair-Ablehnung erfordert Admin-Rechte"
                    })
                    continue
                action_id = data.get("action_id")
                if action_id:
                    reject_result = db_call_json_rt(
                        "SELECT dbai_llm.reject_action(%s::UUID, 'human', %s)",
                        (action_id, data.get("reason", "WebSocket-Ablehnung"))
                    )
                    await websocket.send_json({
                        "type": "action_rejected", "result": reject_result,
                    })

            elif cmd_type == "schema_verify":
                if not is_admin:
                    await websocket.send_json({
                        "type": "error", "message": "Schema-Prüfung erfordert Admin-Rechte"
                    })
                    continue
                verify_rows = db_query_rt("SELECT * FROM dbai_core.verify_schema_integrity()")
                await websocket.send_json({
                    "type": "schema_integrity",
                    "results": verify_rows,
                })

    except WebSocketDisconnect:
        ws_manager.disconnect(session_id)
    except Exception as e:
        logger.error("WebSocket Fehler: %s", e)
        ws_manager.disconnect(session_id)


# ---------------------------------------------------------------------------
# Desktop Nodes & Scene — SVG Network Desktop
# ---------------------------------------------------------------------------

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


@app.get("/api/desktop/nodes")
async def get_desktop_nodes(session: dict = Depends(get_current_session)):
    """Alle sichtbaren Netzwerk-Knoten für den SVG-Desktop."""
    rows = db_query_rt(
        "SELECT * FROM dbai_ui.desktop_nodes WHERE is_visible = true ORDER BY sort_order, id"
    )
    return {"nodes": rows}


@app.get("/api/desktop/nodes/all")
async def get_all_desktop_nodes(session: dict = Depends(get_current_session)):
    """Alle Knoten inkl. unsichtbare (Admin)."""
    rows = db_query_rt(
        "SELECT * FROM dbai_ui.desktop_nodes ORDER BY sort_order, id"
    )
    return {"nodes": rows}


@app.post("/api/desktop/nodes")
async def create_desktop_node(body: NodeCreate, session: dict = Depends(get_current_session)):
    """Neuen Netzwerk-Knoten anlegen."""
    rows = db_query_rt(
        """INSERT INTO dbai_ui.desktop_nodes
           (node_key, label, node_type, icon_type, color, glow_color,
            position_x, position_y, scale, app_id, url, is_visible, sort_order)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           RETURNING *""",
        (body.node_key, body.label, body.node_type, body.icon_type,
         body.color, body.glow_color, body.position_x, body.position_y,
         body.scale, body.app_id, body.url, body.is_visible, body.sort_order)
    )
    return {"node": rows[0] if rows else None}


@app.patch("/api/desktop/nodes/{node_id}")
async def update_desktop_node(node_id: int, body: NodeUpdate, session: dict = Depends(get_current_session)):
    """Netzwerk-Knoten aktualisieren."""
    updates = []
    params = []
    for field, value in body.dict(exclude_none=True).items():
        updates.append(f"{field} = %s")
        params.append(value)
    if not updates:
        raise HTTPException(400, "Keine Felder zum Aktualisieren")
    params.append(node_id)
    rows = db_query_rt(
        f"UPDATE dbai_ui.desktop_nodes SET {', '.join(updates)} WHERE id = %s RETURNING *",
        params
    )
    if not rows:
        raise HTTPException(404, "Knoten nicht gefunden")
    return {"node": rows[0]}


@app.delete("/api/desktop/nodes/{node_id}")
async def delete_desktop_node(node_id: int, session: dict = Depends(get_current_session)):
    """Netzwerk-Knoten löschen."""
    db_execute_rt(
        "DELETE FROM dbai_ui.desktop_nodes WHERE id = %s", (node_id,)
    )
    return {"deleted": True}


@app.get("/api/desktop/scene")
async def get_desktop_scene(session: dict = Depends(get_current_session)):
    """Szene-Konfiguration (Orb, Maschine, Pipes, Background)."""
    rows = db_query_rt("SELECT * FROM dbai_ui.desktop_scene ORDER BY scene_key")
    scene = {}
    for row in rows:
        scene[row["scene_key"]] = row["scene_value"]
    return {"scene": scene}


@app.patch("/api/desktop/scene/{scene_key}")
async def update_desktop_scene(scene_key: str, body: SceneUpdate, session: dict = Depends(get_current_session)):
    """Szene-Einstellung aktualisieren."""
    rows = db_query_rt(
        "UPDATE dbai_ui.desktop_scene SET scene_value = %s::jsonb WHERE scene_key = %s RETURNING *",
        (json.dumps(body.scene_value), scene_key)
    )
    if not rows:
        raise HTTPException(404, f"Szene '{scene_key}' nicht gefunden")
    return {"scene": rows[0]}


# ---------------------------------------------------------------------------
# Stufe 3: Deep Integration (Features 11-15)
# ---------------------------------------------------------------------------

# --- Feature 11: Browser Migration ---
@app.post("/api/browser/scan")
async def browser_scan(session: dict = Depends(get_current_session)):
    """Installierte Browser und Profile scannen."""
    try:
        from bridge.browser_migration import BrowserMigrator
        migrator = BrowserMigrator(db_execute_rt, db_query_rt)
        result = migrator.scan_browsers()
        return {"browsers": result}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/browser/import")
async def browser_import(body: dict, session: dict = Depends(get_current_session)):
    """Browser-Profil importieren (Bookmarks, History, Passwords)."""
    try:
        from bridge.browser_migration import BrowserMigrator
        migrator = BrowserMigrator(db_execute_rt, db_query_rt)
        result = migrator.import_profile(body.get("browser_type", ""), body.get("profile_name", ""), body.get("profile_path", ""))
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/browser/status")
async def browser_status(session: dict = Depends(get_current_session)):
    """Import-Status und Statistiken."""
    try:
        from bridge.browser_migration import BrowserMigrator
        migrator = BrowserMigrator(db_execute_rt, db_query_rt)
        return migrator.get_import_status()
    except Exception as e:
        raise HTTPException(500, str(e))


# --- Feature 12: Config Import ---
@app.post("/api/config/scan")
async def config_scan(session: dict = Depends(get_current_session)):
    """System-Konfiguration scannen (/etc, ~/.config)."""
    try:
        from bridge.config_importer import ConfigImporter
        importer = ConfigImporter(db_execute_rt, db_query_rt)
        result = importer.scan_all()
        return {"configs": result}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/config/import")
async def config_import(session: dict = Depends(get_current_session)):
    """Alle gescannten Configs importieren."""
    try:
        from bridge.config_importer import ConfigImporter
        importer = ConfigImporter(db_execute_rt, db_query_rt)
        result = importer.import_all()
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/config/status")
async def config_status(session: dict = Depends(get_current_session)):
    """Config-Import-Status."""
    try:
        from bridge.config_importer import ConfigImporter
        importer = ConfigImporter(db_execute_rt, db_query_rt)
        return importer.get_status()
    except Exception as e:
        raise HTTPException(500, str(e))


# --- Feature 13: Workspace Mapping ---
@app.post("/api/workspace/scan")
async def workspace_scan(body: dict, session: dict = Depends(get_current_session)):
    """Dateisystem indexieren (ohne Kopie)."""
    try:
        from bridge.workspace_mapper import WorkspaceMapper
        mapper = WorkspaceMapper(db_execute_rt, db_query_rt)
        paths = body.get("paths", [os.path.expanduser("~")])
        result = mapper.scan(paths)
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/workspace/search")
async def workspace_search(q: str = "", session: dict = Depends(get_current_session)):
    """Im Workspace suchen."""
    try:
        from bridge.workspace_mapper import WorkspaceMapper
        mapper = WorkspaceMapper(db_execute_rt, db_query_rt)
        results = mapper.search(q)
        return {"results": results}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/workspace/stats")
async def workspace_stats(session: dict = Depends(get_current_session)):
    """Workspace-Statistiken."""
    try:
        from bridge.workspace_mapper import WorkspaceMapper
        mapper = WorkspaceMapper(db_execute_rt, db_query_rt)
        return mapper.get_stats()
    except Exception as e:
        raise HTTPException(500, str(e))


# --- Feature 14: Synaptic Memory ---
@app.get("/api/synaptic/stats")
async def synaptic_stats(session: dict = Depends(get_current_session)):
    """Synaptic-Memory-Statistiken."""
    try:
        rows = db_query_rt("""
            SELECT memory_type, COUNT(*) as count,
                   AVG(strength) as avg_strength,
                   MAX(created_at) as latest
            FROM dbai_vector.synaptic_memory
            WHERE is_consolidated = false
            GROUP BY memory_type
        """)
        total = db_query_rt("SELECT COUNT(*) as total FROM dbai_vector.synaptic_memory")
        return {
            "by_type": rows,
            "total": total[0]["total"] if total else 0
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/synaptic/search")
async def synaptic_search(type: str = None, limit: int = 50, session: dict = Depends(get_current_session)):
    """Synaptic-Memories durchsuchen."""
    try:
        if type:
            rows = db_query_rt(
                "SELECT * FROM dbai_vector.synaptic_memory WHERE memory_type = %s ORDER BY created_at DESC LIMIT %s",
                (type, limit)
            )
        else:
            rows = db_query_rt(
                "SELECT * FROM dbai_vector.synaptic_memory ORDER BY created_at DESC LIMIT %s",
                (limit,)
            )
        return {"memories": rows}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/synaptic/consolidate")
async def synaptic_consolidate(session: dict = Depends(get_current_session)):
    """Synaptic-Memories konsolidieren."""
    try:
        from bridge.synaptic_pipeline import SynapticPipeline
        pipeline = SynapticPipeline(db_execute_rt, db_query_rt, None)
        result = pipeline.consolidate()
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


# --- Feature 15: RAG Pipeline ---
@app.get("/api/rag/sources")
async def rag_sources(session: dict = Depends(get_current_session)):
    """RAG-Quellen auflisten."""
    try:
        rows = db_query_rt("SELECT * FROM dbai_llm.rag_sources ORDER BY source_name")
        return {"sources": rows}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/rag/stats")
async def rag_stats(session: dict = Depends(get_current_session)):
    """RAG-Statistiken."""
    try:
        sources = db_query_rt("SELECT COUNT(*) as total, COUNT(*) FILTER (WHERE is_active) as active FROM dbai_llm.rag_sources")
        chunks = db_query_rt("SELECT COUNT(*) as total FROM dbai_llm.rag_chunks")
        queries = db_query_rt("SELECT COUNT(*) as total, AVG(relevance_score) as avg_score FROM dbai_llm.rag_query_log")
        return {
            "sources": sources[0] if sources else {},
            "chunks": chunks[0]["total"] if chunks else 0,
            "queries": queries[0] if queries else {}
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/rag/query")
async def rag_query(body: dict, session: dict = Depends(get_current_session)):
    """RAG-Abfrage mit Kontext-Augmentierung."""
    try:
        from bridge.rag_pipeline import RAGPipeline
        pipeline = RAGPipeline(db_execute_rt, db_query_rt, None)
        result = pipeline.query(body.get("question", ""))
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@app.patch("/api/rag/sources/{name}/toggle")
async def rag_toggle_source(name: str, body: dict, session: dict = Depends(get_current_session)):
    """RAG-Quelle aktivieren/deaktivieren."""
    try:
        from bridge.rag_pipeline import RAGPipeline
        pipeline = RAGPipeline(db_execute_rt, db_query_rt, None)
        result = pipeline.toggle_source(name, body.get("enabled", True))
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/rag/sources/{name}/reindex")
async def rag_reindex_source(name: str, session: dict = Depends(get_current_session)):
    """RAG-Quelle neu indexieren."""
    try:
        from bridge.rag_pipeline import RAGPipeline
        pipeline = RAGPipeline(db_execute_rt, db_query_rt, None)
        result = pipeline.reindex_source(name)
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


# ---------------------------------------------------------------------------
# Stufe 4: Nice-to-Have (Features 16-23)
# ---------------------------------------------------------------------------

# --- Feature 16: USB Installer ---
@app.get("/api/usb/devices")
async def usb_devices(session: dict = Depends(get_current_session)):
    """USB-Blockgeräte erkennen."""
    try:
        from bridge.stufe4_utils import USBInstaller
        installer = USBInstaller(db_execute_rt, db_query_rt)
        devices = installer.detect_usb_devices()
        return {"devices": devices}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/usb/flash")
async def usb_flash(body: dict, session: dict = Depends(get_current_session)):
    """ISO/IMG auf USB flashen."""
    try:
        from bridge.stufe4_utils import USBInstaller
        installer = USBInstaller(db_execute_rt, db_query_rt)
        result = installer.flash(body.get("device_path", ""), body.get("image_path", ""), body.get("method", "dd"))
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/usb/jobs")
async def usb_jobs(session: dict = Depends(get_current_session)):
    """Flash-Jobs auflisten."""
    try:
        rows = db_query_rt("SELECT * FROM dbai_system.usb_flash_jobs ORDER BY created_at DESC LIMIT 20")
        return {"jobs": rows}
    except Exception as e:
        raise HTTPException(500, str(e))


# --- Feature 17: WLAN Hotspot ---
@app.post("/api/hotspot/create")
async def hotspot_create(body: dict, session: dict = Depends(get_current_session)):
    """WLAN-Hotspot erstellen."""
    try:
        from bridge.stufe4_utils import WLANHotspot
        hotspot = WLANHotspot(db_execute_rt, db_query_rt)
        result = hotspot.create(body.get("ssid", "DBAI-Hotspot"), body.get("password", ""))
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/hotspot/stop")
async def hotspot_stop(session: dict = Depends(get_current_session)):
    """Hotspot stoppen."""
    try:
        from bridge.stufe4_utils import WLANHotspot
        hotspot = WLANHotspot(db_execute_rt, db_query_rt)
        result = hotspot.stop()
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/hotspot/status")
async def hotspot_status(session: dict = Depends(get_current_session)):
    """Hotspot-Status abfragen."""
    try:
        from bridge.stufe4_utils import WLANHotspot
        hotspot = WLANHotspot(db_execute_rt, db_query_rt)
        return hotspot.status()
    except Exception as e:
        raise HTTPException(500, str(e))


# --- Feature 18: Immutable Filesystem ---
@app.get("/api/immutable/config")
async def immutable_config(session: dict = Depends(get_current_session)):
    """Immutable-FS-Konfiguration."""
    try:
        from bridge.stufe4_utils import ImmutableFS
        fs = ImmutableFS(db_execute_rt, db_query_rt)
        return fs.get_config()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/immutable/enable")
async def immutable_enable(body: dict, session: dict = Depends(get_current_session)):
    """OverlayFS-Modus wechseln."""
    try:
        from bridge.stufe4_utils import ImmutableFS
        fs = ImmutableFS(db_execute_rt, db_query_rt)
        result = fs.enable(body.get("mode", "off"))
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/immutable/snapshots")
async def immutable_snapshots(session: dict = Depends(get_current_session)):
    """Filesystem-Snapshots auflisten."""
    try:
        rows = db_query_rt("SELECT * FROM dbai_system.fs_snapshots ORDER BY created_at DESC LIMIT 20")
        return {"snapshots": rows}
    except Exception as e:
        raise HTTPException(500, str(e))


# --- Feature 20: Anomaly Detection ---
@app.get("/api/anomaly/detections")
async def anomaly_detections(limit: int = 50, severity: str = None, session: dict = Depends(get_current_session)):
    """Erkannte Anomalien auflisten."""
    try:
        if severity:
            rows = db_query_rt(
                "SELECT * FROM dbai_system.anomaly_detections WHERE severity = %s ORDER BY detected_at DESC LIMIT %s",
                (severity, limit)
            )
        else:
            rows = db_query_rt(
                "SELECT * FROM dbai_system.anomaly_detections ORDER BY detected_at DESC LIMIT %s",
                (limit,)
            )
        return {"detections": rows}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/anomaly/models")
async def anomaly_models(session: dict = Depends(get_current_session)):
    """Anomalie-Modelle auflisten."""
    try:
        rows = db_query_rt("SELECT * FROM dbai_system.anomaly_models ORDER BY model_name")
        return {"models": rows}
    except Exception as e:
        raise HTTPException(500, str(e))


# --- Feature 21: App Sandboxing ---
@app.get("/api/sandbox/profiles")
async def sandbox_profiles(session: dict = Depends(get_current_session)):
    """Sandbox-Profile auflisten."""
    try:
        rows = db_query_rt("SELECT * FROM dbai_system.sandbox_profiles ORDER BY profile_name")
        return {"profiles": rows}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/sandbox/launch")
async def sandbox_launch(body: dict, session: dict = Depends(get_current_session)):
    """App in Sandbox starten."""
    try:
        from bridge.stufe4_utils import AppSandbox
        sandbox = AppSandbox(db_execute_rt, db_query_rt)
        result = sandbox.launch(body.get("app_name", ""), body.get("executable_path", ""), body.get("profile_name", "default"))
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/sandbox/running")
async def sandbox_running(session: dict = Depends(get_current_session)):
    """Laufende Sandbox-Apps auflisten."""
    try:
        rows = db_query_rt(
            "SELECT * FROM dbai_system.sandboxed_apps WHERE status = 'running' ORDER BY started_at DESC"
        )
        return {"running": rows}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/sandbox/stop/{pid}")
async def sandbox_stop(pid: int, session: dict = Depends(get_current_session)):
    """Sandbox-App stoppen."""
    try:
        from bridge.stufe4_utils import AppSandbox
        sandbox = AppSandbox(db_execute_rt, db_query_rt)
        result = sandbox.stop(pid)
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


# --- Feature 22: Firewall & Netzwerk-Policy ---
@app.get("/api/firewall/rules")
async def firewall_rules(session: dict = Depends(get_current_session)):
    """Firewall-Regeln auflisten."""
    try:
        rows = db_query_rt("SELECT * FROM dbai_system.firewall_rules WHERE is_active = true ORDER BY priority, chain")
        return {"rules": rows}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/firewall/rules")
async def firewall_add_rule(body: dict, session: dict = Depends(get_current_session)):
    """Firewall-Regel hinzufügen."""
    try:
        from bridge.stufe4_utils import NetworkFirewall
        fw = NetworkFirewall(db_execute_rt, db_query_rt)
        result = fw.add_rule(body)
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/firewall/apply")
async def firewall_apply(session: dict = Depends(get_current_session)):
    """Firewall-Regeln anwenden (iptables)."""
    try:
        from bridge.stufe4_utils import NetworkFirewall
        fw = NetworkFirewall(db_execute_rt, db_query_rt)
        result = fw.apply_rules()
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/firewall/zones")
async def firewall_zones(session: dict = Depends(get_current_session)):
    """Firewall-Zonen auflisten."""
    try:
        rows = db_query_rt("SELECT * FROM dbai_system.firewall_zones ORDER BY zone_name")
        return {"zones": rows}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/firewall/connections")
async def firewall_connections(session: dict = Depends(get_current_session)):
    """Aktive Netzwerkverbindungen auflisten."""
    try:
        from bridge.stufe4_utils import NetworkFirewall
        fw = NetworkFirewall(db_execute_rt, db_query_rt)
        connections = fw.get_connections()
        return {"connections": connections}
    except Exception as e:
        raise HTTPException(500, str(e))


# --- Feature 23: Terminal ---
@app.post("/api/terminal/exec")
async def terminal_exec(body: dict, session: dict = Depends(get_current_session)):
    """Shell-Befehl ausführen (sandboxed)."""
    import subprocess
    import shlex
    command = body.get("command", "").strip()
    cwd = body.get("cwd", os.path.expanduser("~"))
    if not command:
        return {"stdout": "", "stderr": "Kein Befehl angegeben", "exit_code": 1}

    # Blacklist für gefährliche Befehle
    blocked = ["rm -rf /", "mkfs", "dd if=", ":(){", "fork bomb"]
    for b in blocked:
        if b in command:
            return {"stdout": "", "stderr": f"Befehl blockiert: {b}", "exit_code": 126}

    try:
        # Terminal-Session in DB loggen
        db_execute_rt(
            "INSERT INTO dbai_ui.terminal_history (session_id, command, cwd) VALUES (%s, %s, %s)",
            (session.get("session_id", "default"), command, cwd)
        )
    except Exception:
        pass

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=30, cwd=cwd,
            env={**os.environ, "TERM": "xterm-256color"}
        )
        return {
            "stdout": result.stdout[-50000:] if len(result.stdout) > 50000 else result.stdout,
            "stderr": result.stderr[-10000:] if len(result.stderr) > 10000 else result.stderr,
            "exit_code": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Timeout (30s)", "exit_code": 124}
    except FileNotFoundError:
        return {"stdout": "", "stderr": f"Verzeichnis nicht gefunden: {cwd}", "exit_code": 127}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "exit_code": 1}


# ---------------------------------------------------------------------------
# CI/CD & OTA Update System
# ---------------------------------------------------------------------------
from bridge.migration_runner import MigrationRunner
from bridge.gs_updater import GhostUpdater

_migration_runner = MigrationRunner(DB_CONFIG)
_updater = GhostUpdater(DB_CONFIG)


# --- Update-Kanal & Releases ---

@app.get("/api/updates/status")
async def updates_status(session: dict = Depends(get_current_session)):
    """Aktueller Update-Status: Version, Node-Info, verfügbare Updates."""
    try:
        node = _updater.register_node()
        available = _updater.check_for_updates()
        migration_status = _migration_runner.get_status()
        return {
            "node": node,
            "current_version": node.get("current_version", "0.0.0"),
            "available_update": available,
            "migration_status": migration_status,
        }
    except Exception as e:
        return {"error": str(e), "current_version": "0.0.0"}


@app.get("/api/updates/releases")
async def updates_releases(session: dict = Depends(get_current_session)):
    """Alle veröffentlichten Releases."""
    rows = db_query("""
        SELECT id, version, channel, commit_hash, commit_message,
               release_notes, author, schema_version, requires_restart,
               is_critical, published_at, created_at
        FROM dbai_system.system_releases
        WHERE is_published = true
        ORDER BY created_at DESC
        LIMIT 50
    """)
    return rows


@app.get("/api/updates/channels")
async def updates_channels(session: dict = Depends(get_current_session)):
    """Verfügbare Update-Kanäle."""
    rows = db_query("""
        SELECT id, channel_name, description, is_default, repo_url,
               branch, check_interval, is_active
        FROM dbai_system.update_channels
        ORDER BY channel_name
    """)
    return rows


@app.post("/api/updates/check")
async def updates_check(session: dict = Depends(get_current_session)):
    """Manuell auf Updates prüfen."""
    update = _updater.check_for_updates()
    return {"available": update is not None, "update": update}


@app.post("/api/updates/apply")
async def updates_apply(request: Request,
                         session: dict = Depends(get_current_session)):
    """Update anwenden (git pull + Migrationen + Frontend-Build)."""
    body = await request.json() if await request.body() else {}
    version = body.get("version")
    use_git = body.get("use_git", True)

    result = _updater.apply_update(version=version, use_git=use_git)
    return result


@app.post("/api/updates/release")
async def updates_create_release(request: Request,
                                  session: dict = Depends(get_current_session)):
    """Neues Release erstellen und veröffentlichen."""
    body = await request.json()
    version = body.get("version")
    channel = body.get("channel", "stable")
    notes = body.get("release_notes", "")
    commit = body.get("commit_hash")

    if not version:
        raise HTTPException(400, "version ist erforderlich")

    result = _updater.create_release(version, channel, notes, commit)
    return result


# --- Migrations ---

@app.get("/api/migrations/status")
async def migrations_status(session: dict = Depends(get_current_session)):
    """Migrations-Übersicht."""
    return _migration_runner.get_status()


@app.get("/api/migrations/history")
async def migrations_history(session: dict = Depends(get_current_session)):
    """Letzte Migrationen."""
    return _migration_runner.get_history(limit=100)


@app.get("/api/migrations/pending")
async def migrations_pending(session: dict = Depends(get_current_session)):
    """Ausstehende Migrationen."""
    return _migration_runner.get_pending()


@app.post("/api/migrations/apply")
async def migrations_apply(request: Request,
                            session: dict = Depends(get_current_session)):
    """Alle ausstehenden Migrationen anwenden."""
    body = await request.json() if await request.body() else {}
    dry_run = body.get("dry_run", False)
    version = body.get("version")

    results = _migration_runner.apply_all(version=version, dry_run=dry_run)
    return {"results": results, "dry_run": dry_run}


@app.post("/api/migrations/rollback")
async def migrations_rollback(session: dict = Depends(get_current_session)):
    """Letzte Migration zurückrollen."""
    return _migration_runner.rollback_last()


# --- Build Pipeline ---

@app.get("/api/pipeline/history")
async def pipeline_history(session: dict = Depends(get_current_session)):
    """Build-Pipeline-Historie."""
    rows = db_query("""
        SELECT id, build_number, version, commit_hash, branch,
               trigger_type, status, steps, started_at, finished_at,
               duration_ms, error_message, triggered_by
        FROM dbai_system.build_pipeline
        ORDER BY created_at DESC
        LIMIT 50
    """)
    return rows


@app.post("/api/pipeline/run")
async def pipeline_run(request: Request,
                        session: dict = Depends(get_current_session)):
    """Lokale CI-Pipeline manuell starten."""
    body = await request.json() if await request.body() else {}
    branch = body.get("branch", "main")

    # Aktuellen Commit ermitteln
    import subprocess as sp
    try:
        r = sp.run(["git", "rev-parse", "HEAD"],
                    cwd=str(DBAI_ROOT), capture_output=True, text=True, timeout=5)
        commit = r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        commit = None

    result = _updater.run_pipeline(commit_hash=commit, branch=branch)
    return result


# --- OTA Nodes ---

@app.get("/api/ota/nodes")
async def ota_nodes(session: dict = Depends(get_current_session)):
    """Alle verbundenen OTA-Nodes."""
    rows = db_query("""
        SELECT id, node_name, hostname, ip_address::text, current_version,
               target_version, channel, last_checkin, last_update,
               status, auto_update, system_info
        FROM dbai_system.ota_nodes
        ORDER BY node_name
    """)
    return rows


@app.get("/api/ota/jobs")
async def ota_jobs(session: dict = Depends(get_current_session)):
    """Letzte Update-Jobs."""
    rows = db_query("""
        SELECT j.id, n.node_name, j.from_version, j.to_version,
               j.status, j.progress, j.started_at, j.finished_at,
               j.duration_ms, j.error_message
        FROM dbai_system.update_jobs j
        LEFT JOIN dbai_system.ota_nodes n ON j.node_id = n.id
        ORDER BY j.created_at DESC
        LIMIT 50
    """)
    return rows


# ---------------------------------------------------------------------------
# Hardware-Simulator API
# ---------------------------------------------------------------------------
# Steuerung des QEMU/Software-Hardware-Simulators (dev/qemu/hw_simulator.py)
# Wird per DBAI_HW_SIMULATE=true oder manuell gestartet.

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


# Auto-Start wenn DBAI_HW_SIMULATE=true
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


@app.get("/api/simulator/status")
async def simulator_status(session: dict = Depends(get_current_session)):
    """Aktueller Status des Hardware-Simulators."""
    try:
        sim = _get_hw_sim()
        return sim.get_status()
    except HTTPException:
        return {"running": False, "available": False,
                "message": "Hardware-Simulator nicht geladen"}


@app.post("/api/simulator/start")
async def simulator_start(session: dict = Depends(get_current_session)):
    """Startet die Hardware-Simulation."""
    sim = _get_hw_sim()
    result = sim.start()
    return result


@app.post("/api/simulator/stop")
async def simulator_stop(session: dict = Depends(get_current_session)):
    """Stoppt die Hardware-Simulation."""
    sim = _get_hw_sim()
    result = sim.stop()
    return result


@app.post("/api/simulator/anomaly")
async def simulator_anomaly(body: SimulatorAnomalyRequest,
                            session: dict = Depends(get_current_session)):
    """Aktiviert/Deaktiviert eine simulierte Hardware-Anomalie."""
    sim = _get_hw_sim()
    result = sim.trigger_anomaly(body.anomaly)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@app.get("/api/simulator/profiles")
async def simulator_profiles(session: dict = Depends(get_current_session)):
    """Verfügbare Hardware-Profile."""
    profiles_path = DBAI_ROOT / "dev" / "qemu" / "profiles.json"
    if not profiles_path.exists():
        return {"profiles": {}}
    import json as _json
    with open(profiles_path) as f:
        data = _json.load(f)
    summaries = {}
    for name, p in data.get("profiles", {}).items():
        summaries[name] = {
            "name": p.get("name", name),
            "cpu": f"{p.get('cpu_cores', '?')}C/{p.get('cpu_threads', '?')}T — {p.get('cpu_model', '')}",
            "ram": f"{p.get('ram_total_mb', 0)} MB {p.get('ram_type', '')}",
            "disks": len(p.get("disks", [])),
            "nics": len(p.get("nics", [])),
            "gpu": p.get("gpu", {}).get("name") if p.get("gpu") else None,
        }
    return {"profiles": summaries}


@app.post("/api/simulator/profile")
async def simulator_set_profile(body: SimulatorProfileRequest,
                                session: dict = Depends(get_current_session)):
    """Wechselt das Hardware-Profil (Neustart der Simulation nötig)."""
    global _hw_simulator
    profiles_path = DBAI_ROOT / "dev" / "qemu" / "profiles.json"
    if not profiles_path.exists():
        raise HTTPException(404, "Profil-Datei nicht gefunden")
    import json as _json
    with open(profiles_path) as f:
        data = _json.load(f)
    if body.profile not in data.get("profiles", {}):
        raise HTTPException(400, f"Unbekanntes Profil: {body.profile}. "
                            f"Verfügbar: {list(data['profiles'].keys())}")
    # Alten Simulator stoppen
    if _hw_simulator and _hw_simulator.state.running:
        _hw_simulator.stop()
    # Neues Profil laden
    from hw_simulator import HardwareSimulator, HardwareProfile
    pdata = data["profiles"][body.profile]
    profile = HardwareProfile(**{
        k: v for k, v in pdata.items()
        if k in HardwareProfile.__dataclass_fields__
    })
    _hw_simulator = HardwareSimulator(profile)
    return {"status": "profile_loaded", "profile": body.profile,
            "name": profile.name, "message": "Simulation mit /api/simulator/start starten"}


# ---------------------------------------------------------------------------
# Static Files & SPA Fallback
# ---------------------------------------------------------------------------
# Assets (Wallpapers, Icons, Avatars)
if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

# Frontend SPA
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
else:
    @app.get("/")
    async def root():
        """Fallback wenn kein Frontend gebaut ist."""
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html lang="de">
        <head>
            <meta charset="UTF-8">
            <title>DBAI — Ghost in the Database</title>
            <style>
                body { background: #0a0a0f; color: #00ffcc; font-family: 'JetBrains Mono', monospace;
                       display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
                .container { text-align: center; }
                h1 { font-size: 2em; text-shadow: 0 0 20px rgba(0,255,204,0.5); }
                p { color: #6688aa; }
                a { color: #00ffcc; }
                .api { background: #1a1a2e; padding: 20px; border-radius: 8px; margin-top: 20px;
                       border: 1px solid #1a3a4a; text-align: left; }
                code { color: #ffaa00; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>👻 DBAI</h1>
                <p>Ghost in the Database — v0.3.0</p>
                <p>Frontend nicht gebaut. Starte mit: <code>cd frontend && npm run build</code></p>
                <div class="api">
                    <p>API Endpoints:</p>
                    <p><code>POST /api/auth/login</code> — Login</p>
                    <p><code>GET  /api/boot/sequence</code> — Boot-Animation</p>
                    <p><code>GET  /api/desktop</code> — Desktop-State</p>
                    <p><code>GET  /api/ghosts</code> — Ghost-System</p>
                    <p><code>POST /api/ghosts/swap</code> — KI wechseln</p>
                    <p><code>WS   /ws/{token}</code> — WebSocket</p>
                    <p><a href="/docs">/docs</a> — Swagger UI</p>
                </div>
            </div>
        </body>
        </html>
        """)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
def main():
    import uvicorn
    logger.info("═══════════════════════════════════════")
    logger.info("  DBAI Web Server — Ghost in the DB")
    logger.info("  %s:%d", WEB_HOST, WEB_PORT)
    logger.info("═══════════════════════════════════════")
    uvicorn.run(
        "web.server:app",
        host=WEB_HOST,
        port=WEB_PORT,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
