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
# API Routes — Setup Wizard
# ---------------------------------------------------------------------------
@app.post("/api/setup/complete")
async def setup_complete(request: Request, session: dict = Depends(get_current_session)):
    """First-Boot Setup abschließen: Einstellungen in DB speichern."""
    settings = await request.json()
    user_id = session["user"]["id"]

    # User-Einstellungen aktualisieren
    db_execute_rt("""
        UPDATE dbai_ui.users
        SET locale = %s, timezone = %s, preferences = preferences || %s::JSONB,
            updated_at = NOW()
        WHERE id = %s::UUID
    """, (
        settings.get("locale", "de-DE"),
        settings.get("timezone", "Europe/Berlin"),
        json.dumps({
            "default_model": settings.get("defaultModel", "qwen2.5-7b-instruct"),
            "auto_ghost_swap": settings.get("enableGhostSwap", True),
            "auto_heal": settings.get("enableAutoHeal", True),
            "telemetry": settings.get("enableTelemetry", True),
            "setup_completed": True,
        }),
        user_id,
    ))

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

    return {"ok": True, "message": "Setup abgeschlossen"}


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
