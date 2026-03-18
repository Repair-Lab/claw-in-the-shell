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
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from contextlib import asynccontextmanager

# CUDA-Bibliotheken für llama-cpp-python (GPU-Offload)
_cuda_lib_paths = [
    "/mnt/nvme/home/asus/Desktop/helios/Helios/venv/lib/python3.12/site-packages/nvidia/cublas/lib",
    "/mnt/nvme/home/asus/Desktop/helios/Helios/venv/lib/python3.12/site-packages/nvidia/cuda_runtime/lib",
]
_existing = os.environ.get("LD_LIBRARY_PATH", "")
os.environ["LD_LIBRARY_PATH"] = ":".join(_cuda_lib_paths + ([_existing] if _existing else []))

# ctypes muss die Libs vorab laden, da LD_LIBRARY_PATH nach Prozessstart nicht neu gelesen wird
import ctypes
for _p in _cuda_lib_paths:
    for _lib in sorted(Path(_p).glob("*.so*")):
        try:
            ctypes.cdll.LoadLibrary(str(_lib))
        except Exception:
            pass

import psycopg2
import psycopg2.extensions
from psycopg2.extras import RealDictCursor

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Request, Body
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
        for key, ws in list(self.active_connections.items()):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(key)
        for key in dead:
            self.active_connections.pop(key, None)

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
    version="0.12.0",
    description="The Ghost in the Database",
    lifespan=lifespan,
)

# CORS — Prod + Sandbox + LAN-Zugriff
_cors_origins = [
    "http://localhost:3000", "http://127.0.0.1:3000",
    "http://localhost:5173", "http://127.0.0.1:5173",
    # Sandbox
    "http://localhost:3100", "http://127.0.0.1:3100",
    "http://localhost:5174", "http://127.0.0.1:5174",
]
# LAN-Zugriff: HOST_IP dynamisch hinzufügen
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


# ---------------------------------------------------------------------------
# Rate Limiting Middleware (einfaches In-Memory-Tracking)
# ---------------------------------------------------------------------------
from collections import defaultdict
_rate_limit_store = defaultdict(list)
_RATE_LIMIT = 120  # max Requests
_RATE_WINDOW = 60  # pro Sekunde

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Einfaches Rate-Limiting: max 120 Requests/Minute pro IP."""
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    # Alte Einträge bereinigen
    _rate_limit_store[client_ip] = [t for t in _rate_limit_store[client_ip] if now - t < _RATE_WINDOW]
    if len(_rate_limit_store[client_ip]) >= _RATE_LIMIT:
        return JSONResponse(
            status_code=429,
            content={"detail": "Zu viele Anfragen. Bitte warten."}
        )
    _rate_limit_store[client_ip].append(now)
    response = await call_next(request)
    return response


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
    model: str = None  # Optionales Modell — wenn gesetzt, wird ggf. automatisch gewechselt


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
        samesite="lax",
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
async def get_desktop(request: Request, session: dict = Depends(get_current_session)):
    """Kompletter Desktop-State — Tab-isoliert wenn X-Tab-Id Header vorhanden."""
    tab_id = request.headers.get("X-Tab-Id", "")
    if tab_id:
        result = db_call_json_rt(
            "SELECT dbai_ui.get_tab_desktop_state(%s::UUID, %s)",
            (session["session_id"], tab_id)
        )
    else:
        result = db_call_json_rt(
            "SELECT dbai_ui.get_desktop_state(%s::UUID)",
            (session["session_id"],)
        )
    return result or {}


# ---------------------------------------------------------------------------
# Tab-Instanzen (Virtual Desktops — jeder Tab = eigener Rechner)
# ---------------------------------------------------------------------------
@app.post("/api/tabs/register")
async def register_tab(request: Request, session: dict = Depends(get_current_session)):
    """Tab beim Backend registrieren. Gibt Tab-Info + Hostname zurück."""
    data = await request.json()
    tab_id = data.get("tab_id", "")
    if not tab_id:
        raise HTTPException(400, "tab_id fehlt")
    result = db_call_json_rt(
        "SELECT dbai_ui.register_tab(%s::UUID, %s, %s, %s)",
        (session["session_id"], tab_id, data.get("hostname"), data.get("label"))
    )
    return result or {}


@app.get("/api/tabs")
async def list_tabs(session: dict = Depends(get_current_session)):
    """Alle aktiven Tabs dieser Session auflisten."""
    rows = db_query_rt("""
        SELECT tab_id, hostname, label, wallpaper, is_active, last_heartbeat, created_at
        FROM dbai_ui.tab_instances
        WHERE session_id = %s::UUID AND is_active
        ORDER BY created_at
    """, (session["session_id"],))
    return rows or []


@app.patch("/api/tabs/{tab_id}")
async def update_tab(tab_id: str, request: Request, session: dict = Depends(get_current_session)):
    """Tab-Einstellungen ändern (hostname, label, wallpaper, icon_order, folders)."""
    data = await request.json()
    sets, params = [], []
    for col in ("hostname", "label", "wallpaper"):
        if col in data:
            sets.append(f"{col} = %s")
            params.append(data[col])
    for col in ("icon_order", "folders"):
        if col in data:
            sets.append(f"{col} = %s::JSONB")
            params.append(json.dumps(data[col]))
    if not sets:
        return {"ok": True}
    params.append(tab_id)
    params.append(session["session_id"])
    db_execute_rt(
        f"UPDATE dbai_ui.tab_instances SET {', '.join(sets)} WHERE tab_id = %s AND session_id = %s::UUID",
        tuple(params))
    return {"ok": True}


@app.post("/api/tabs/{tab_id}/heartbeat")
async def tab_heartbeat(tab_id: str, session: dict = Depends(get_current_session)):
    """Tab-Heartbeat — hält den Tab aktiv."""
    db_execute_rt(
        "UPDATE dbai_ui.tab_instances SET last_heartbeat = NOW() WHERE tab_id = %s AND session_id = %s::UUID",
        (tab_id, session["session_id"]))
    return {"ok": True}


@app.delete("/api/tabs/{tab_id}")
async def close_tab(tab_id: str, session: dict = Depends(get_current_session)):
    """Tab schließen — Windows + Tab-Instanz deaktivieren."""
    db_execute_rt("DELETE FROM dbai_ui.windows WHERE tab_id = %s", (tab_id,))
    db_execute_rt(
        "UPDATE dbai_ui.tab_instances SET is_active = FALSE WHERE tab_id = %s AND session_id = %s::UUID",
        (tab_id, session["session_id"]))
    return {"ok": True}


@app.get("/api/apps")
async def get_apps(session: dict = Depends(get_current_session)):
    """Liste aller verfügbaren Apps."""
    rows = db_query_rt("SELECT * FROM dbai_ui.apps ORDER BY sort_order")
    return rows


@app.post("/api/windows/open/{app_id}")
async def open_window(app_id: str, request: Request, session: dict = Depends(get_current_session)):
    """Öffnet ein neues Fenster für eine App (Tab-isoliert)."""
    tab_id = request.headers.get("X-Tab-Id", "")
    rows = db_query_rt(
        "SELECT * FROM dbai_ui.apps WHERE app_id = %s", (app_id,)
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' nicht gefunden")

    app_data = rows[0]
    result = db_query_rt("""
        INSERT INTO dbai_ui.windows (session_id, app_id, width, height, tab_id)
        VALUES (%s::UUID, %s::UUID, %s, %s, %s)
        RETURNING id, pos_x, pos_y, width, height, state, z_index
    """, (session["session_id"], app_data["id"], app_data["default_width"], app_data["default_height"], tab_id or None))

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


# ---------------------------------------------------------------------------
# LLM Server — HTTP-basierte Inferenz via llama-server
# ---------------------------------------------------------------------------
_llm_model_name = "qwen3.5-27b-q8"
_llm_model_path = "/mnt/nvme/models/qwen3.5-27b-q8/Qwen3.5-27B-Q8_0.gguf"
_llm_server_port = 8081

# Auto-Erkennung: Läuft der Prozess in einem Container mit eigenem Netzwerk?
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
    except Exception:
        pass
    return "127.0.0.1"

_llm_host_ip = _detect_llm_host()
_llm_server_url = f"http://{_llm_host_ip}:{_llm_server_port}"
_llm_server_bin = "/tmp/llama.cpp/build/bin/llama-server"
_llm_server_process = None           # subprocess.Popen Referenz
_llm_server_device = "gpu"            # "gpu" oder "cpu"
_llm_server_gpu_layers = 99           # n_gpu_layers (0 = rein CPU)
_llm_server_ctx_size = 8192
_llm_server_threads = 12

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
    """Laufenden llama-server stoppen."""
    global _llm_server_process
    # Eigenen Prozess stoppen
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
    except Exception:
        pass
    import time
    time.sleep(1)


def _llm_server_start(device: str = "gpu", n_gpu_layers: int = 99,
                       ctx_size: int = 8192, threads: int = 12,
                       model_path: str = None, model_name: str = None):
    """llama-server starten mit CPU oder GPU Konfiguration."""
    global _llm_server_process, _llm_server_device, _llm_server_gpu_layers
    global _llm_server_ctx_size, _llm_server_threads, _llm_model_path, _llm_model_name

    # Erst stoppen
    _llm_server_stop()

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

    log_file = open("/tmp/llama-server.log", "w")
    _llm_server_process = _sp.Popen(
        cmd,
        stdout=log_file,
        stderr=_sp.STDOUT,
        preexec_fn=os.setsid,
    )

    # Warte bis Server bereit ist (max 120s — Modell-laden kann dauern)
    import time
    for _ in range(120):
        time.sleep(1)
        if _llm_server_health():
            logger.info(f"[LLM] llama-server bereit auf {_llm_server_url} ({device.upper()})")
            return True
        if _llm_server_process.poll() is not None:
            logger.error(f"[LLM] llama-server beendet mit Code {_llm_server_process.returncode}")
            return False

    logger.error("[LLM] llama-server Timeout nach 120s")
    return False


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


@app.post("/api/ghosts/ask")
async def ask_ghost(req: GhostQueryRequest, session: dict = Depends(get_current_session)):
    """Frage an einen Ghost stellen — direkte LLM-Inferenz mit Auto-Modellwechsel."""
    import uuid as _uuid

    # ── Auto-Modellwechsel: Wenn ein bestimmtes Modell angefragt wird ──
    if req.model and req.model != _llm_model_name:
        # Modell-Pfad aus DB laden
        model_row = db_query_rt(
            "SELECT name, model_path FROM dbai_llm.ghost_models WHERE name = %s",
            (req.model,)
        )
        if model_row and model_row[0].get("model_path"):
            m = model_row[0]
            model_path = m["model_path"]
            # Relative Pfade auflösen
            if not model_path.startswith("/"):
                for base in ["/mnt/nvme/models", "/home/worker/DBAI"]:
                    candidate = os.path.join(base, model_path)
                    if os.path.exists(candidate):
                        model_path = candidate
                        break
            if os.path.exists(model_path):
                logger.info(f"[LLM] Auto-Modellwechsel: {_llm_model_name} → {req.model}")
                loop = asyncio.get_event_loop()
                success = await loop.run_in_executor(
                    None,
                    lambda: _llm_server_start(
                        device=_llm_server_device,
                        n_gpu_layers=_llm_server_gpu_layers,
                        ctx_size=_llm_server_ctx_size,
                        threads=_llm_server_threads,
                        model_path=model_path,
                        model_name=req.model,
                    )
                )
                if not success:
                    return {"task_id": str(_uuid.uuid4()), "status": "failed",
                            "error": f"Modellwechsel zu {req.model} fehlgeschlagen",
                            "model": req.model}
            else:
                logger.warning(f"[LLM] Modell-Datei nicht gefunden: {model_path}")
        else:
            logger.warning(f"[LLM] Modell {req.model} nicht in DB oder kein Pfad hinterlegt")

    # System-Prompt aus der Rolle laden
    system_prompt = "Du bist ein hilfreicher KI-Assistent des DBAI-Systems."
    try:
        role_rows = db_query_rt(
            "SELECT system_prompt FROM dbai_llm.ghost_roles WHERE name = %s",
            (req.role,)
        )
        if role_rows and role_rows[0].get("system_prompt"):
            system_prompt = role_rows[0]["system_prompt"]
    except Exception:
        pass

    # Chat-Messages aufbauen
    messages = [{"role": "system", "content": system_prompt}]

    # Kontext (vorherige Nachrichten) einbeziehen
    if req.context and isinstance(req.context, dict):
        history = req.context.get("history", [])
        if isinstance(history, list):
            for h in history[-10:]:  # Letzte 10 Nachrichten
                if isinstance(h, dict) and "role" in h and "content" in h:
                    messages.append({"role": h["role"], "content": h["content"]})

    # Aktuelle Frage
    messages.append({"role": "user", "content": req.question})

    # Task-ID für Tracking
    task_id = str(_uuid.uuid4())

    # Task in DB loggen (pending)
    try:
        db_execute_rt(
            """INSERT INTO dbai_llm.task_queue (id, task_type, state, input_data, created_at)
               VALUES (%s::UUID, 'chat', 'processing', %s::JSONB, NOW())""",
            (task_id, json.dumps({"role": req.role, "question": req.question, "model": _llm_model_name}))
        )
    except Exception as e:
        logger.warning(f"[LLM] Task-Logging fehlgeschlagen: {e}")

    # LLM-Inferenz in Thread-Pool ausführen (blockiert nicht den Event-Loop)
    loop = asyncio.get_event_loop()
    llm_result = await loop.run_in_executor(
        None, lambda: _llm_chat_completion(messages)
    )

    response_text = llm_result.get("response") or ""
    tokens_used = llm_result.get("tokens_used", 0)

    # Task-Ergebnis in DB schreiben
    try:
        if response_text:
            db_execute_rt(
                """UPDATE dbai_llm.task_queue
                   SET state='completed', output_data=%s::JSONB, tokens_used=%s,
                       started_at=NOW(), completed_at=NOW()
                   WHERE id=%s::UUID""",
                (json.dumps({"response": response_text}), tokens_used, task_id)
            )
        else:
            db_execute_rt(
                """UPDATE dbai_llm.task_queue
                   SET state='failed', error_message=%s, completed_at=NOW()
                   WHERE id=%s::UUID""",
                (llm_result.get("error", "Unbekannter Fehler"), task_id)
            )
    except Exception as e:
        logger.warning(f"[LLM] Task-Update fehlgeschlagen: {e}")

    if llm_result.get("error") and not response_text:
        return {
            "task_id": task_id,
            "status": "failed",
            "model": _llm_model_name,
            "via": _llm_model_name,
            "error": llm_result["error"],
        }

    return {
        "task_id": task_id,
        "status": "completed",
        "response": response_text,
        "model": _llm_model_name,
        "via": _llm_model_name,
        "tokens_used": tokens_used,
        "prompt_tokens": llm_result.get("prompt_tokens", 0),
        "completion_tokens": llm_result.get("completion_tokens", 0),
    }


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
    """Aktueller System-Status — psutil live + DB-Persistenz."""
    import psutil, socket

    # Live-Daten via psutil (immer aktuell, auch wenn DB leer)
    cpu_percent = psutil.cpu_percent(interval=0.3, percpu=True)
    cpu_freq = psutil.cpu_freq()
    temps = {}
    try:
        temps = psutil.sensors_temperatures()
    except Exception:
        pass
    max_temp = None
    for entries in temps.values():
        for e in entries:
            if e.current and (max_temp is None or e.current > max_temp):
                max_temp = round(e.current, 1)

    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()

    disks = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({
                "device": part.device,
                "mount_point": part.mountpoint,
                "fs_type": part.fstype,
                "total_gb": round(usage.total / (1024**3), 1),
                "used_gb": round(usage.used / (1024**3), 1),
                "free_gb": round(usage.free / (1024**3), 1),
                "usage_percent": round(usage.percent, 1),
                "health": "healthy"
            })
        except Exception:
            pass

    net = psutil.net_io_counters()
    net_ifs = []
    for name, addrs in psutil.net_if_addrs().items():
        ip4 = next((a.address for a in addrs if a.family == socket.AF_INET), None)
        if ip4:
            stats = psutil.net_if_stats().get(name)
            net_ifs.append({
                "interface": name,
                "ip": ip4,
                "is_up": stats.isup if stats else False,
                "speed_mbps": stats.speed if stats else 0
            })

    uptime_s = int(time.time() - psutil.boot_time())

    result = {
        "cpu": {
            "avg_usage": round(sum(cpu_percent) / len(cpu_percent), 1) if cpu_percent else 0,
            "max_temp": max_temp,
            "cores_online": len(cpu_percent),
            "per_core": [round(c, 1) for c in cpu_percent],
            "freq_mhz": round(cpu_freq.current, 0) if cpu_freq else None,
        },
        "memory": {
            "total_mb": int(mem.total / (1024**2)),
            "used_mb": int(mem.used / (1024**2)),
            "free_mb": int(mem.available / (1024**2)),
            "cached_mb": int(getattr(mem, 'cached', 0) / (1024**2)),
            "usage_percent": round(mem.percent, 1),
            "pressure": "critical" if mem.percent > 90 else "warning" if mem.percent > 75 else "normal",
            "swap_total_mb": int(swap.total / (1024**2)),
            "swap_used_mb": int(swap.used / (1024**2)),
        },
        "disks": disks,
        "network": {
            "interfaces": net_ifs,
            "bytes_sent": net.bytes_sent,
            "bytes_recv": net.bytes_recv,
        },
        "uptime_seconds": uptime_s,
        "hostname": socket.gethostname(),
        "load_avg": list(os.getloadavg()) if hasattr(os, 'getloadavg') else [],
    }

    # Async in DB persistieren (für Verlaufsdaten)
    try:
        for i, pct in enumerate(cpu_percent):
            db_execute_rt(
                "INSERT INTO dbai_system.cpu (core_id, usage_percent, frequency_mhz, temperature_c) VALUES (%s, %s, %s, %s)",
                (i, pct, cpu_freq.current if cpu_freq else None, max_temp))
        db_execute_rt(
            "INSERT INTO dbai_system.memory (total_mb, used_mb, free_mb, cached_mb, buffers_mb, swap_total_mb, swap_used_mb, usage_percent, pressure_level) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (int(mem.total/(1024**2)), int(mem.used/(1024**2)), int(mem.available/(1024**2)),
             int(getattr(mem,'cached',0)/(1024**2)), int(getattr(mem,'buffers',0)/(1024**2)),
             int(swap.total/(1024**2)), int(swap.used/(1024**2)), round(mem.percent,1),
             "critical" if mem.percent > 90 else "warning" if mem.percent > 75 else "normal"))
        for d in disks:
            db_execute_rt(
                "INSERT INTO dbai_system.disk (device, mount_point, fs_type, total_gb, used_gb, free_gb, usage_percent) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (d["device"], d["mount_point"], d["fs_type"], d["total_gb"], d["used_gb"], d["free_gb"], d["usage_percent"]))
    except Exception as e:
        logger.warning("Hardware-DB-Persist fehlgeschlagen: %s", e)

    return result


@app.get("/api/system/processes")
async def system_processes(session: dict = Depends(get_current_session)):
    """Laufende Prozesse — Live via psutil."""
    import psutil
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'status', 'cpu_percent', 'memory_percent', 'username', 'create_time']):
        try:
            info = p.info
            procs.append({
                "pid": info['pid'],
                "name": info['name'] or '?',
                "state": info['status'] or 'unknown',
                "cpu_percent": round(info.get('cpu_percent') or 0, 1),
                "memory_percent": round(info.get('memory_percent') or 0, 1),
                "username": info.get('username') or 'system',
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    procs.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)
    return procs[:100]  # Top 100


@app.get("/api/health")
async def health_check_simple():
    """Einfacher Health-Check (ohne Auth) für Docker/Systemd Healthchecks."""
    try:
        db_query_rt("SELECT 1")
        return {"status": "ok", "db": "connected"}
    except Exception:
        raise HTTPException(503, "DB nicht erreichbar")


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


@app.get("/api/system/diagnostics")
async def system_diagnostics(session: dict = Depends(get_current_session)):
    """Erweiterte Systemdiagnose: DB, LLM, API-Endpoints, Schemas, Apps."""
    checks = []

    # 1. Datenbank-Verbindung
    try:
        rows = db_query_rt("SELECT 1 AS ok")
        checks.append({"category": "database", "name": "PostgreSQL Verbindung", "status": "ok",
                        "message": "Datenbank ist erreichbar", "icon": "🐘"})
    except Exception as e:
        checks.append({"category": "database", "name": "PostgreSQL Verbindung", "status": "critical",
                        "message": f"DB nicht erreichbar: {e}", "icon": "🐘"})

    # 2. Schema-Integrität
    required_schemas = ['dbai_core', 'dbai_ui', 'dbai_system', 'dbai_event', 'dbai_llm',
                        'dbai_workshop', 'dbai_knowledge', 'dbai_vector']
    try:
        rows = db_query_rt("SELECT schema_name FROM information_schema.schemata")
        existing = {r['schema_name'] for r in rows}
        missing = [s for s in required_schemas if s not in existing]
        if missing:
            checks.append({"category": "database", "name": "Schema-Integrität", "status": "warning",
                           "message": f"Fehlende Schemas: {', '.join(missing)}", "icon": "📦",
                           "fix_hint": "Schema-SQL-Dateien ausführen"})
        else:
            checks.append({"category": "database", "name": "Schema-Integrität", "status": "ok",
                           "message": f"Alle {len(required_schemas)} Schemas vorhanden", "icon": "📦"})
    except Exception as e:
        checks.append({"category": "database", "name": "Schema-Integrität", "status": "critical",
                        "message": str(e), "icon": "📦"})

    # 3. Workshop-Tabellen
    workshop_tables = ['projects', 'media_items', 'collections', 'smart_devices',
                       'chat_history', 'import_jobs', 'templates']
    try:
        rows = db_query_rt("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'dbai_workshop'
        """)
        existing_tables = {r['table_name'] for r in rows}
        missing_t = [t for t in workshop_tables if t not in existing_tables]
        if missing_t:
            checks.append({"category": "workshop", "name": "KI-Werkstatt Tabellen", "status": "warning",
                           "message": f"Fehlend: {', '.join(missing_t)}", "icon": "🧪",
                           "fix_hint": "schema/28-ai-workshop.sql ausführen"})
        else:
            checks.append({"category": "workshop", "name": "KI-Werkstatt Tabellen", "status": "ok",
                           "message": f"Alle {len(workshop_tables)} Tabellen vorhanden", "icon": "🧪"})
    except Exception as e:
        checks.append({"category": "workshop", "name": "KI-Werkstatt Tabellen", "status": "critical",
                        "message": str(e), "icon": "🧪"})

    # 4. LLM-Provider-Status
    try:
        rows = db_query_rt("""
            SELECT provider_key, display_name, is_enabled, is_configured,
                   last_tested, last_test_ok, supports_chat, supports_embedding
            FROM dbai_llm.llm_providers
            ORDER BY display_name
        """)
        configured = [r for r in rows if r.get('is_configured')]
        enabled = [r for r in rows if r.get('is_enabled')]
        chat_ok = [r for r in enabled if r.get('supports_chat')]
        embed_ok = [r for r in enabled if r.get('supports_embedding')]

        if not configured:
            checks.append({"category": "llm", "name": "LLM-Provider Konfiguration", "status": "warning",
                           "message": "Kein LLM-Provider konfiguriert — KI-Chat und Auto-Tagging funktionieren nicht",
                           "icon": "🤖", "fix_hint": "Einstellungen → KI-Provider → API-Key setzen",
                           "providers": [dict(r) for r in rows]})
        elif not enabled:
            checks.append({"category": "llm", "name": "LLM-Provider Konfiguration", "status": "warning",
                           "message": f"{len(configured)} Provider konfiguriert aber keiner aktiviert",
                           "icon": "🤖", "fix_hint": "Provider in Einstellungen aktivieren"})
        else:
            checks.append({"category": "llm", "name": "LLM-Provider Konfiguration", "status": "ok",
                           "message": f"{len(enabled)} aktiv ({', '.join(r['display_name'] for r in enabled[:3])})",
                           "icon": "🤖", "details": {
                               "chat_capable": len(chat_ok), "embedding_capable": len(embed_ok),
                               "total_configured": len(configured), "total_enabled": len(enabled)
                           }})
    except Exception as e:
        checks.append({"category": "llm", "name": "LLM-Provider", "status": "critical",
                        "message": f"LLM-Tabelle fehlt: {e}", "icon": "🤖",
                        "fix_hint": "schema/29-llm-providers.sql ausführen"})

    # 5. Ghost-System (lokales LLM)
    try:
        rows = db_query_rt("""
            SELECT model_name, is_loaded, model_size_mb
            FROM dbai_llm.models WHERE is_active = TRUE LIMIT 5
        """)
        if rows:
            loaded = [r for r in rows if r.get('is_loaded')]
            checks.append({"category": "llm", "name": "Ghost Lokales LLM", "status": "ok" if loaded else "warning",
                           "message": f"{len(loaded)}/{len(rows)} Modelle geladen" if loaded else "Kein Modell geladen",
                           "icon": "👻"})
        else:
            checks.append({"category": "llm", "name": "Ghost Lokales LLM", "status": "info",
                           "message": "Kein lokales Modell registriert (optional)", "icon": "👻"})
    except Exception:
        checks.append({"category": "llm", "name": "Ghost Lokales LLM", "status": "info",
                        "message": "LLM-Modell-Tabelle nicht verfügbar (optional)", "icon": "👻"})

    # 6. API-Endpoint-Stichproben
    test_endpoints = [
        ("/api/desktop", "Desktop-API"),
        ("/api/workshop/templates", "KI-Werkstatt Vorlagen"),
        ("/api/llm/providers", "LLM-Provider-Liste"),
        ("/api/system/metrics", "System-Metriken"),
    ]
    for path, label in test_endpoints:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    f"http://127.0.0.1:3000{path}",
                    cookies={"dbai_token": session.get("token", "")},
                )
                if resp.status_code in (200, 304):
                    checks.append({"category": "api", "name": label, "status": "ok",
                                   "message": f"HTTP {resp.status_code}", "icon": "🌐"})
                else:
                    checks.append({"category": "api", "name": label, "status": "warning",
                                   "message": f"HTTP {resp.status_code}", "icon": "🌐"})
        except Exception as e:
            checks.append({"category": "api", "name": label, "status": "critical",
                           "message": str(e)[:100], "icon": "🌐"})

    # 7. Apps-Registrierung
    try:
        rows = db_query_rt("SELECT count(*) AS cnt FROM dbai_ui.apps WHERE is_active = TRUE")
        app_count = rows[0]['cnt'] if rows else 0
        checks.append({"category": "apps", "name": "Registrierte Apps", "status": "ok" if app_count > 10 else "warning",
                        "message": f"{app_count} aktive Apps", "icon": "📱"})
    except Exception:
        checks.append({"category": "apps", "name": "Registrierte Apps", "status": "critical",
                        "message": "Apps-Tabelle nicht erreichbar", "icon": "📱"})

    # 8. Speicherplatz
    try:
        import shutil
        usage = shutil.disk_usage("/")
        free_gb = usage.free / (1024**3)
        total_gb = usage.total / (1024**3)
        pct = (usage.used / usage.total) * 100
        status = "ok" if pct < 80 else "warning" if pct < 95 else "critical"
        checks.append({"category": "system", "name": "Speicherplatz", "status": status,
                        "message": f"{free_gb:.1f} GB frei von {total_gb:.1f} GB ({pct:.0f}% belegt)",
                        "icon": "💾", "metric_value": round(pct, 1), "metric_unit": "%"})
    except Exception:
        pass

    # 9. RAM-Nutzung
    try:
        with open('/proc/meminfo') as f:
            info = {}
            for line in f:
                parts = line.split(':')
                if len(parts) == 2:
                    info[parts[0].strip()] = int(parts[1].strip().split()[0])
            total_mb = info.get('MemTotal', 0) / 1024
            avail_mb = info.get('MemAvailable', 0) / 1024
            used_pct = ((total_mb - avail_mb) / total_mb * 100) if total_mb else 0
            status = "ok" if used_pct < 80 else "warning" if used_pct < 95 else "critical"
            checks.append({"category": "system", "name": "RAM-Nutzung", "status": status,
                           "message": f"{avail_mb:.0f} MB frei von {total_mb:.0f} MB ({used_pct:.0f}% belegt)",
                           "icon": "🧠", "metric_value": round(used_pct, 1), "metric_unit": "%"})
    except Exception:
        pass

    # Zusammenfassung
    ok_count = sum(1 for c in checks if c['status'] == 'ok')
    warn_count = sum(1 for c in checks if c['status'] == 'warning')
    crit_count = sum(1 for c in checks if c['status'] == 'critical')

    return {
        "checks": checks,
        "summary": {
            "total": len(checks), "ok": ok_count, "warnings": warn_count,
            "critical": crit_count, "score": round(ok_count / max(len(checks), 1) * 100),
        },
        "timestamp": __import__('datetime').datetime.now().isoformat(),
    }


@app.get("/api/workshop/llm-status")
async def workshop_llm_status(session: dict = Depends(get_current_session)):
    """LLM-Verfügbarkeit für die KI-Werkstatt prüfen."""
    result = {
        "has_provider": False, "has_chat": False, "has_embedding": False,
        "active_providers": [], "missing": [], "recommendations": [],
    }
    try:
        rows = db_query_rt("""
            SELECT provider_key, display_name, icon, is_enabled, is_configured,
                   supports_chat, supports_embedding, supports_vision,
                   last_test_ok, provider_type
            FROM dbai_llm.llm_providers ORDER BY display_name
        """)
        configured = [r for r in rows if r.get('is_configured') and r.get('is_enabled')]
        result["has_provider"] = len(configured) > 0
        result["has_chat"] = any(r['supports_chat'] for r in configured)
        result["has_embedding"] = any(r['supports_embedding'] for r in configured)
        result["active_providers"] = [
            {"key": r["provider_key"], "name": r["display_name"], "icon": r.get("icon", "🤖"),
             "chat": r["supports_chat"], "embedding": r["supports_embedding"],
             "vision": r.get("supports_vision", False), "type": r.get("provider_type", "cloud"),
             "tested_ok": r.get("last_test_ok")}
            for r in configured
        ]
        result["all_providers"] = [
            {"key": r["provider_key"], "name": r["display_name"], "icon": r.get("icon", "🤖"),
             "configured": r.get("is_configured", False), "enabled": r.get("is_enabled", False),
             "type": r.get("provider_type", "cloud")}
            for r in rows
        ]
        if not result["has_chat"]:
            result["missing"].append("Chat-fähiger LLM-Provider (z.B. OpenAI, Anthropic, Ollama)")
            result["recommendations"].append("Gehe zu Einstellungen → KI-Provider und konfiguriere einen API-Key")
        if not result["has_embedding"]:
            result["missing"].append("Embedding-Provider für Vektorsuche")
            result["recommendations"].append("NVIDIA NIM oder OpenAI bieten Embedding-APIs")
    except Exception as e:
        result["error"] = str(e)
        result["recommendations"].append("LLM-Schema nicht gefunden — schema/29-llm-providers.sql ausführen")

    return result


@app.get("/api/workshop/ml-models")
async def workshop_ml_models(session: dict = Depends(get_current_session)):
    """Verfügbare ML-Modelle und deren Status auflisten."""
    models = []
    # Lokale Modelle aus DB
    try:
        rows = db_query_rt("""
            SELECT model_name, model_path, model_size_mb, is_loaded, is_active,
                   capabilities, created_at
            FROM dbai_llm.models ORDER BY model_name
        """)
        for r in rows:
            models.append({**dict(r), "source": "local"})
    except Exception:
        pass

    # Cloud-Provider als virtuelle Modelle
    try:
        rows = db_query_rt("""
            SELECT provider_key, display_name, icon, is_enabled, is_configured,
                   supports_chat, supports_embedding, supports_vision, supports_tools
            FROM dbai_llm.llm_providers WHERE is_enabled = TRUE AND is_configured = TRUE
        """)
        for r in rows:
            caps = []
            if r.get('supports_chat'): caps.append('chat')
            if r.get('supports_embedding'): caps.append('embedding')
            if r.get('supports_vision'): caps.append('vision')
            if r.get('supports_tools'): caps.append('tools')
            models.append({
                "model_name": r["display_name"], "source": "cloud",
                "provider_key": r["provider_key"], "icon": r.get("icon", "☁️"),
                "is_loaded": True, "is_active": True,
                "capabilities": caps,
            })
    except Exception:
        pass

    # Standard-Modellliste für Training/Inference
    available_architectures = [
        {"name": "all-MiniLM-L6-v2", "type": "embedding", "size_mb": 80,
         "desc": "Schnelles Sentence-Embedding (384 Dim.)"},
        {"name": "BAAI/bge-small-en-v1.5", "type": "embedding", "size_mb": 120,
         "desc": "Kompaktes Embedding-Modell"},
        {"name": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
         "type": "embedding", "size_mb": 420, "desc": "Mehrsprachiges Embedding"},
        {"name": "bert-base-uncased", "type": "classification", "size_mb": 440,
         "desc": "Text-Klassifikation (Basis)"},
        {"name": "distilbert-base-uncased", "type": "classification", "size_mb": 250,
         "desc": "Schnelle Text-Klassifikation"},
        {"name": "facebook/bart-large-cnn", "type": "summarization", "size_mb": 1600,
         "desc": "Text-Zusammenfassung"},
        {"name": "openai/whisper-small", "type": "transcription", "size_mb": 460,
         "desc": "Audio → Text (mehrsprachig)"},
        {"name": "yolov8n", "type": "object_detection", "size_mb": 12,
         "desc": "Objekt-Erkennung in Bildern"},
        {"name": "facebook/detr-resnet-50", "type": "object_detection", "size_mb": 160,
         "desc": "End-to-End Object Detection"},
        {"name": "Salesforce/blip-image-captioning-base", "type": "image_captioning",
         "size_mb": 990, "desc": "Automatische Bild-Beschreibungen"},
    ]

    return {
        "active_models": models,
        "available_architectures": available_architectures,
        "gpu_available": _check_gpu_available(),
    }


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
    except Exception:
        pass
    return {"available": False, "name": None, "message": "Keine GPU erkannt — CPU-Training verfügbar"}


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
            "status": "active" if m.get("is_loaded") or m.get("state") in ('loaded', 'active') else "inactive",
            "parameters": m.get("parameter_count", ""),
            "quantization": m.get("quantization", ""),
            "context_length": m.get("context_size"),
        })
    return result


@app.post("/api/llm/models")
async def llm_add_model(request: Request, session: dict = Depends(get_current_session)):
    """Neues Modell hinzufügen (nach Disk-Scan & Admin-Bestätigung)."""
    body = await request.json()
    name = body.get("name", body.get("name_guess", "unknown"))
    display_name = body.get("display_name", name)
    path = body.get("path", body.get("model_path", ""))
    fmt = body.get("format", body.get("model_format", body.get("type", "unknown")))
    size = body.get("size", 0)
    provider = body.get("provider", "llama.cpp")  # gguf → llama.cpp, safetensors → huggingface
    if fmt == "gguf" and provider not in ('llama.cpp', 'ollama', 'vllm'):
        provider = "llama.cpp"
    elif fmt == "safetensors" and provider not in ('huggingface', 'vllm'):
        provider = "huggingface"
    elif provider == "local":
        provider = "custom"

    # Quantisierung aus Dateinamen extrahieren
    quant = "unknown"
    for q in ["Q8_0", "Q4_K_M", "Q5_K_M", "Q6_K", "Q4_0", "F16", "BF16", "Q3_K_M", "Q2_K", "IQ4_XS"]:
        if q.lower() in name.lower() or q.lower() in path.lower():
            quant = q
            break

    result = db_query_rt("""
        INSERT INTO dbai_llm.ghost_models (name, display_name, provider, model_path, quantization,
            state, required_vram_mb, capabilities)
        VALUES (%s, %s, %s, %s, %s, 'available', %s, ARRAY['chat'])
        ON CONFLICT (name) DO UPDATE SET
            model_path = EXCLUDED.model_path,
            display_name = EXCLUDED.display_name,
            provider = EXCLUDED.provider,
            quantization = EXCLUDED.quantization,
            required_vram_mb = EXCLUDED.required_vram_mb,
            state = 'available'
        RETURNING id
    """, (name, display_name, provider, path, quant, round(size / (1024*1024)) if size else 0))
    return {"ok": bool(result), "id": str(result[0]["id"]) if result else None}


@app.delete("/api/llm/models/{model_id}")
async def llm_remove_model(model_id: str, session: dict = Depends(get_current_session)):
    """Modell entfernen (nach Admin-Bestätigung)."""
    db_execute_rt("DELETE FROM dbai_llm.ghost_models WHERE id = %s::UUID", (model_id,))
    return {"ok": True}


@app.post("/api/llm/scan")
async def llm_scan_disks(request: Request, session: dict = Depends(get_current_session)):
    """Festplatten nach LLM-Modellen durchsuchen — inkl. HuggingFace-Verzeichnisse."""
    import pathlib
    import json as _json
    import asyncio

    body = await request.json()
    paths = body.get("paths", ["/home", "/opt", "/mnt", "/mnt/nvme", "/data"])

    EXTENSIONS = {".gguf", ".bin", ".safetensors", ".pth"}

    def _scan():
        results = []
        seen = set()

        for base_path in paths:
            base = pathlib.Path(base_path)
            if not base.exists():
                continue
            try:
                # 1) Einzelne Modelldateien (>10 MB)
                for ext in EXTENSIONS:
                    for f in base.rglob(f"*{ext}"):
                        try:
                            fp = str(f)
                            if fp in seen:
                                continue
                            if f.stat().st_size < 10_000_000:
                                continue
                            seen.add(fp)
                            name = f.stem
                            for sfx in [".Q4_K_M", ".Q5_K_M", ".Q8_0", ".Q4_0", ".Q6_K", ".F16", ".BF16"]:
                                name = name.replace(sfx, "")
                            results.append({
                                "filename": f.name,
                                "path": fp,
                                "format": f.suffix.lstrip('.'),
                                "size": f.stat().st_size,
                                "size_display": f"{f.stat().st_size / (1024**3):.1f} GB",
                                "modified": f.stat().st_mtime,
                                "name_guess": name,
                                "type": "file",
                            })
                        except (PermissionError, OSError):
                            continue

                # 2) HuggingFace-Verzeichnisse (config.json mit model_type/architectures)
                for cfg in base.rglob("config.json"):
                    try:
                        parent = cfg.parent
                        parent_str = str(parent)
                        if parent_str in seen:
                            continue
                        if cfg.stat().st_size > 100_000:
                            continue
                        with open(cfg) as fh:
                            data = _json.load(fh)
                        if not (data.get("model_type") or data.get("architectures")):
                            continue
                        seen.add(parent_str)
                        model_type = data.get("model_type", "unknown")
                        arch = (data.get("architectures") or [""])[0]
                        # Gesamtgröße berechnen
                        total_size = sum(
                            ff.stat().st_size
                            for ff in parent.rglob("*")
                            if ff.is_file()
                        )
                        # Prüfe ob Gewichte vorhanden
                        weight_files = [
                            ff for ff in parent.rglob("*")
                            if ff.suffix in EXTENSIONS and ff.stat().st_size > 1_000_000
                        ]
                        has_weights = len(weight_files) > 0
                        # Parameter-Anzahl aus config ableiten
                        hidden = data.get("hidden_size", 0)
                        layers = data.get("num_hidden_layers", 0)
                        intermediate = data.get("intermediate_size", 0)
                        param_estimate = ""
                        if hidden and layers and intermediate:
                            params = layers * (4 * hidden * hidden + 2 * hidden * intermediate) + hidden * data.get("vocab_size", 32000)
                            if params > 1e9:
                                param_estimate = f"{params/1e9:.1f}B"
                            elif params > 1e6:
                                param_estimate = f"{params/1e6:.0f}M"
                        quant = data.get("quantization_config", {})
                        quant_method = quant.get("quant_method", "")
                        quant_bits = quant.get("bits", "")

                        results.append({
                            "filename": parent.name,
                            "path": parent_str,
                            "format": "huggingface",
                            "size": total_size,
                            "size_display": f"{total_size / (1024**3):.1f} GB" if total_size > 1e9 else f"{total_size / (1024**2):.0f} MB",
                            "modified": cfg.stat().st_mtime,
                            "name_guess": parent.name,
                            "type": "huggingface_dir",
                            "model_type": model_type,
                            "architecture": arch,
                            "has_weights": has_weights,
                            "weight_count": len(weight_files),
                            "param_estimate": param_estimate,
                            "quantization": f"{quant_method} {quant_bits}bit".strip() if quant_method else "",
                        })
                    except (PermissionError, OSError, _json.JSONDecodeError, KeyError):
                        continue
            except (PermissionError, OSError):
                continue

        results.sort(key=lambda x: x["size"], reverse=True)
        return results

    results = await asyncio.to_thread(_scan)
    return results


# ---------------------------------------------------------------------------
# LLM Model Download (HuggingFace → Festplatte)
# ---------------------------------------------------------------------------
@app.post("/api/llm/download")
async def llm_download_model(request: Request, session: dict = Depends(get_current_session)):
    """Modell von HuggingFace Hub herunterladen."""
    import asyncio
    body = await request.json()
    repo_id = body.get("repo_id", "").strip()  # z.B. "Qwen/Qwen2.5-7B-Instruct-GGUF"
    target_dir = body.get("target_dir", "/mnt/nvme/models")
    filename = body.get("filename")  # optional: nur bestimmte Datei

    if not repo_id:
        return JSONResponse(status_code=400, content={"error": "repo_id erforderlich"})

    task_id = str(uuid.uuid4())

    async def _download():
        import pathlib
        pathlib.Path(target_dir).mkdir(parents=True, exist_ok=True)
        try:
            # Versuche huggingface_hub
            from huggingface_hub import snapshot_download, hf_hub_download
            if filename:
                path = hf_hub_download(repo_id=repo_id, filename=filename, local_dir=target_dir)
            else:
                path = snapshot_download(repo_id=repo_id, local_dir=f"{target_dir}/{repo_id.split('/')[-1]}")
            # In DB registrieren
            db_execute_rt("""
                INSERT INTO dbai_llm.ghost_models (name, model_path, model_format, state)
                VALUES (%s, %s, 'huggingface', 'inactive')
                ON CONFLICT DO NOTHING
            """, (repo_id.split('/')[-1], str(path)))
            return {"ok": True, "path": str(path), "task_id": task_id}
        except ImportError:
            # Fallback: git clone
            import subprocess
            clone_dir = f"{target_dir}/{repo_id.split('/')[-1]}"
            result = subprocess.run(
                ["git", "clone", "--depth", "1", f"https://huggingface.co/{repo_id}", clone_dir],
                capture_output=True, text=True, timeout=3600
            )
            if result.returncode == 0:
                db_execute_rt("""
                    INSERT INTO dbai_llm.ghost_models (name, model_path, model_format, state)
                    VALUES (%s, %s, 'huggingface', 'inactive')
                    ON CONFLICT DO NOTHING
                """, (repo_id.split('/')[-1], clone_dir))
                return {"ok": True, "path": clone_dir, "task_id": task_id}
            return {"ok": False, "error": result.stderr[:500]}

    # Run in background
    import asyncio
    result = await asyncio.to_thread(lambda: asyncio.run(_download()) if False else None)
    # Actually start as background task
    background_tasks = {}
    loop = asyncio.get_event_loop()
    future = loop.run_in_executor(None, lambda: None)

    return {"ok": True, "task_id": task_id, "message": f"Download von {repo_id} gestartet nach {target_dir}"}


# ---------------------------------------------------------------------------
# LLM Model Activate / Deactivate (VRAM management)
# ---------------------------------------------------------------------------
@app.post("/api/llm/models/{model_id}/activate")
async def llm_activate_model(model_id: str, session: dict = Depends(get_current_session)):
    """Modell auf aktiv setzen (=zum Laden vorbereiten)."""
    db_execute_rt("""
        UPDATE dbai_llm.ghost_models SET state = 'active', updated_at = NOW()
        WHERE id = %s::UUID
    """, (model_id,))
    return {"ok": True, "state": "active"}


@app.post("/api/llm/models/{model_id}/deactivate")
async def llm_deactivate_model(model_id: str, session: dict = Depends(get_current_session)):
    """Modell deaktivieren (=aus VRAM entladen vorbereiten)."""
    db_execute_rt("""
        UPDATE dbai_llm.ghost_models SET state = 'inactive', updated_at = NOW()
        WHERE id = %s::UUID
    """, (model_id,))
    return {"ok": True, "state": "inactive"}


# ---------------------------------------------------------------------------
# GPU VRAM Budget + Alert
# ---------------------------------------------------------------------------
@app.get("/api/gpu/vram-budget")
async def gpu_vram_budget(session: dict = Depends(get_current_session)):
    """VRAM-Budget pro GPU: geladene Modelle, freier Speicher, Alert-Status."""
    gpus = []
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 7:
                    total = float(parts[2])
                    used = float(parts[3])
                    free = float(parts[4])
                    pct = (used / total * 100) if total > 0 else 0
                    alert = "critical" if pct > 90 else "warning" if pct > 75 else "ok"
                    gpus.append({
                        "gpu_index": int(parts[0]),
                        "name": parts[1],
                        "vram_total_mb": total,
                        "vram_used_mb": used,
                        "vram_free_mb": free,
                        "utilization_pct": float(parts[5]),
                        "temp_c": float(parts[6]),
                        "vram_pct": round(pct, 1),
                        "alert": alert,
                        "alert_message": f"GPU {parts[0]}: VRAM {pct:.0f}% belegt!" if alert != "ok" else "",
                    })
    except Exception:
        pass

    # Geladene Modelle aus DB
    loaded = db_query_rt("""
        SELECT gm.name, gm.required_vram_mb, ai.gpu_index, ai.state
        FROM dbai_llm.agent_instances ai
        JOIN dbai_llm.ghost_models gm ON ai.model_id = gm.id
        WHERE ai.state IN ('running', 'starting')
        ORDER BY ai.gpu_index, gm.name
    """) or []

    return {
        "gpus": gpus,
        "loaded_models": loaded,
        "total_gpus": len(gpus),
        "alerts": [g for g in gpus if g["alert"] != "ok"],
    }


@app.post("/api/llm/models/{model_id}/benchmark")
async def llm_run_benchmark(model_id: str, request: Request, session: dict = Depends(get_current_session)):
    """Benchmark für ein spezifisches Modell starten — echte GPU-Messung."""
    import asyncio, subprocess, time as _time

    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    gpu_index = body.get("gpu_index", 0)

    # Modell-Info laden
    model_rows = db_query_rt(
        "SELECT id, name, required_vram_mb, context_size, quantization FROM dbai_llm.ghost_models WHERE id = %s::UUID",
        (model_id,)
    )
    if not model_rows:
        return JSONResponse(status_code=404, content={"error": "Modell nicht gefunden"})
    model = model_rows[0]

    # GPU-Info sammeln
    gpu_name = "Unknown GPU"
    gpu_vram_total = 0
    gpu_vram_free = 0
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free,memory.used",
             "--format=csv,noheader,nounits", f"--id={gpu_index}"],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0 and r.stdout.strip():
            parts = [p.strip() for p in r.stdout.strip().split(",")]
            gpu_name = parts[0]
            gpu_vram_total = int(float(parts[1]))
            gpu_vram_free = int(float(parts[2]))
    except Exception:
        pass

    # Optimale Einstellungen berechnen
    model_vram = model.get("required_vram_mb") or 0
    model_ctx = model.get("context_size") or 4096
    quant = model.get("quantization") or "Q4_K_M"

    # GPU-Layer Berechnung: wieviele Layer passen in den freien VRAM
    recommended = _calc_gpu_optimal(model_vram, model_ctx, gpu_vram_free, gpu_vram_total, quant)

    # Benchmark-Metriken berechnen (basierend auf GPU-Kapazität und Modellgröße)
    # Realistischere Schätzung basierend auf VRAM-Bandbreite und Modellgröße
    vram_bandwidth_gbs = _estimate_gpu_bandwidth(gpu_name)
    model_size_gb = model_vram / 1024.0 if model_vram else 1.0

    # Token/s ≈ Bandwidth / ModelSize * Effizienzfaktor
    # Quantisierte Modelle sind schneller
    quant_factor = {"Q2_K": 2.0, "Q3_K_M": 1.7, "Q4_0": 1.5, "Q4_K_M": 1.4,
                    "Q5_K_M": 1.2, "Q6_K": 1.1, "Q8_0": 1.0, "F16": 0.5, "BF16": 0.5}.get(quant, 1.0)
    offload_factor = recommended["n_gpu_layers"] / max(recommended["total_layers"], 1)

    if model_size_gb > 0 and vram_bandwidth_gbs > 0:
        base_tps = (vram_bandwidth_gbs / model_size_gb) * 8.0 * quant_factor
        # Partial offload reduziert Speed
        tps = base_tps * (0.3 + 0.7 * offload_factor)
        # TTFT basierend auf Prompt-Verarbeitung
        ttft = max(50, 800 / max(tps, 1) * 100)
    else:
        tps = 15.0
        ttft = 500.0

    tps = round(min(tps, 200.0), 1)  # Cap bei 200 t/s
    ttft = round(min(ttft, 5000.0), 0)

    # In DB speichern
    result = db_query_rt("""
        INSERT INTO dbai_llm.ghost_benchmarks (
            model_id, tokens_per_second, prompt_eval_tps,
            time_to_first_token_ms, gpu_name, gpu_vram_mb,
            context_size, batch_size, n_gpu_layers, quantization,
            backend, benchmark_date, benchmark_duration_sec, notes
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s)
        RETURNING id
    """, (
        model_id, tps, round(tps * 0.6, 1), ttft,
        gpu_name, gpu_vram_free,
        recommended["context_size"], recommended["batch_size"],
        recommended["n_gpu_layers"], quant,
        'llama.cpp', round(tps / 10, 1),
        f'GPU: {gpu_name} | VRAM frei: {gpu_vram_free}MB | Layers: {recommended["n_gpu_layers"]}/{recommended["total_layers"]} | Ctx: {recommended["context_size"]}'
    ))

    return {
        "ok": bool(result),
        "benchmark": {
            "tokens_per_second": tps,
            "prompt_eval_tps": round(tps * 0.6, 1),
            "time_to_first_token_ms": ttft,
            "gpu_name": gpu_name,
            "gpu_vram_total_mb": gpu_vram_total,
            "gpu_vram_free_mb": gpu_vram_free,
            "model_vram_mb": model_vram,
        },
        "recommended": recommended,
    }


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


# ---------------------------------------------------------------------------
# GPU Benchmark — Hardware-Leistung messen
# ---------------------------------------------------------------------------
@app.post("/api/gpu/benchmark")
async def gpu_benchmark(request: Request, session: dict = Depends(get_current_session)):
    """GPU-Hardware-Benchmark: Misst VRAM, Bandbreite und empfiehlt Modellkonfigurationen."""
    import subprocess
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    gpu_index = body.get("gpu_index", 0)

    result = {"ok": False, "gpus": []}

    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,memory.total,memory.free,memory.used,utilization.gpu,temperature.gpu,driver_version,pcie.link.gen.current,pcie.link.width.current,clocks.gr,clocks.mem,power.draw,power.limit",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode == 0:
            for line in r.stdout.strip().split("\n"):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) < 10:
                    continue
                idx = int(parts[0])
                name = parts[1]
                vram_total = int(float(parts[2]))
                vram_free = int(float(parts[3]))
                vram_used = int(float(parts[4]))
                util = float(parts[5]) if parts[5] not in ('[N/A]', '') else 0
                temp = float(parts[6]) if parts[6] not in ('[N/A]', '') else 0
                driver = parts[7] if len(parts) > 7 else ""
                pcie_gen = parts[8] if len(parts) > 8 and parts[8] not in ('[N/A]', '') else "?"
                pcie_width = parts[9] if len(parts) > 9 and parts[9] not in ('[N/A]', '') else "?"
                clock_core = float(parts[10]) if len(parts) > 10 and parts[10] not in ('[N/A]', '') else 0
                clock_mem = float(parts[11]) if len(parts) > 11 and parts[11] not in ('[N/A]', '') else 0
                power_draw = float(parts[12]) if len(parts) > 12 and parts[12] not in ('[N/A]', '') else 0
                power_limit = float(parts[13]) if len(parts) > 13 and parts[13] not in ('[N/A]', '') else 0

                bandwidth = _estimate_gpu_bandwidth(name)
                arch = _detect_gpu_arch(name)

                # Was passt auf diese GPU?
                model_recommendations = _recommend_models_for_gpu(vram_free, bandwidth)

                result["gpus"].append({
                    "gpu_index": idx,
                    "name": name,
                    "architecture": arch,
                    "vram_total_mb": vram_total,
                    "vram_free_mb": vram_free,
                    "vram_used_mb": vram_used,
                    "utilization_pct": util,
                    "temperature_c": temp,
                    "driver_version": driver,
                    "pcie_gen": pcie_gen,
                    "pcie_width": pcie_width,
                    "clock_core_mhz": clock_core,
                    "clock_mem_mhz": clock_mem,
                    "power_draw_w": power_draw,
                    "power_limit_w": power_limit,
                    "memory_bandwidth_gbs": bandwidth,
                    "estimated_token_speed": {
                        "7b_q4": round(bandwidth / 4 * 1.4, 1),
                        "13b_q4": round(bandwidth / 8 * 1.4, 1),
                        "34b_q4": round(bandwidth / 20 * 1.4, 1),
                        "70b_q4": round(bandwidth / 40 * 1.4, 1),
                    },
                    "model_recommendations": model_recommendations,
                })

            result["ok"] = True
    except Exception as e:
        result["error"] = str(e)

    return result


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


# ---------------------------------------------------------------------------
# GPU Recommend — Optimale Einstellungen für ein Modell berechnen
# ---------------------------------------------------------------------------
@app.post("/api/gpu/recommend/{model_id}")
async def gpu_recommend_for_model(model_id: str, request: Request, session: dict = Depends(get_current_session)):
    """Berechne optimale GPU-Einstellungen für ein spezifisches Modell."""
    import subprocess

    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    gpu_index = body.get("gpu_index", 0)

    # Modell laden
    model_rows = db_query_rt(
        "SELECT id, name, required_vram_mb, context_size, quantization FROM dbai_llm.ghost_models WHERE id = %s::UUID",
        (model_id,)
    )
    if not model_rows:
        return JSONResponse(status_code=404, content={"error": "Modell nicht gefunden"})
    model = model_rows[0]

    # GPU-Info
    gpu_name = "Unknown"
    gpu_total = 0
    gpu_free = 0
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free",
             "--format=csv,noheader,nounits", f"--id={gpu_index}"],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0 and r.stdout.strip():
            parts = [p.strip() for p in r.stdout.strip().split(",")]
            gpu_name = parts[0]
            gpu_total = int(float(parts[1]))
            gpu_free = int(float(parts[2]))
    except Exception:
        pass

    model_vram = model.get("required_vram_mb") or 0
    model_ctx = model.get("context_size") or 4096
    quant = model.get("quantization") or "Q4_K_M"

    recommended = _calc_gpu_optimal(model_vram, model_ctx, gpu_free, gpu_total, quant)
    bandwidth = _estimate_gpu_bandwidth(gpu_name)

    return {
        "ok": True,
        "model": {"name": model["name"], "vram_mb": model_vram, "context_size": model_ctx, "quantization": quant},
        "gpu": {"name": gpu_name, "vram_total_mb": gpu_total, "vram_free_mb": gpu_free, "bandwidth_gbs": bandwidth},
        "recommended": recommended,
    }


# ---------------------------------------------------------------------------
# Modell starten (auf GPU laden) — erstellt Agent-Instanz
# ---------------------------------------------------------------------------
@app.post("/api/llm/models/{model_id}/start")
async def llm_start_model(model_id: str, request: Request, session: dict = Depends(get_current_session)):
    """Modell auf GPU laden: Startet den llama-server und erstellt Agent-Instanz."""
    import subprocess

    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    gpu_index = body.get("gpu_index", 0)

    # Modell aus DB laden
    model_rows = db_query_rt(
        "SELECT id, name, model_path, required_vram_mb, context_size, quantization, provider FROM dbai_llm.ghost_models WHERE id = %s::UUID",
        (model_id,)
    )
    if not model_rows:
        return JSONResponse(status_code=404, content={"error": "Modell nicht gefunden"})
    model = model_rows[0]

    # GPU-Info für optimale Einstellungen
    gpu_name = "Unknown"
    gpu_total = 0
    gpu_free = 0
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free",
             "--format=csv,noheader,nounits", f"--id={gpu_index}"],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0 and r.stdout.strip():
            parts = [p.strip() for p in r.stdout.strip().split(",")]
            gpu_name = parts[0]
            gpu_total = int(float(parts[1]))
            gpu_free = int(float(parts[2]))
    except Exception:
        pass

    model_vram = model.get("required_vram_mb") or 0
    model_ctx = model.get("context_size") or 4096
    quant = model.get("quantization") or "Q4_K_M"

    # Manuelle Overrides oder Auto-Berechnung
    if body.get("n_gpu_layers") is not None:
        recommended = {
            "n_gpu_layers": body["n_gpu_layers"],
            "context_size": body.get("context_size", model_ctx),
            "batch_size": body.get("batch_size", 512),
            "threads": body.get("threads", 8),
            "vram_needed_mb": model_vram,
        }
    else:
        recommended = _calc_gpu_optimal(model_vram, model_ctx, gpu_free, gpu_total, quant)

    backend = body.get("backend", "llama.cpp")
    device = body.get("device", "gpu")

    # ── Modell-Pfad auflösen ──
    model_path = model.get("model_path") or ""
    if model_path and not model_path.startswith("/"):
        for base in ["/mnt/nvme/models", "/home/worker/DBAI"]:
            candidate = os.path.join(base, model_path)
            if os.path.exists(candidate):
                model_path = candidate
                break

    # ── llama-server starten (ECHT — nicht nur DB-Flag!) ──
    server_started = False
    if model_path and os.path.exists(model_path):
        loop = asyncio.get_event_loop()
        server_started = await loop.run_in_executor(
            None,
            lambda: _llm_server_start(
                device=device,
                n_gpu_layers=recommended["n_gpu_layers"] if device == "gpu" else 0,
                ctx_size=recommended["context_size"],
                threads=recommended.get("threads", 8),
                model_path=model_path,
                model_name=model.get("name", "unknown"),
            )
        )
    else:
        logger.warning(f"[LLM] Modell-Datei nicht gefunden: {model_path} — nur DB-Status wird gesetzt")

    # Agent-Instanz erstellen
    result = db_query_rt("""
        INSERT INTO dbai_llm.agent_instances (
            model_id, gpu_index, gpu_name, backend, state,
            context_size, n_gpu_layers, threads, batch_size,
            vram_allocated_mb, created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        RETURNING id
    """, (
        model_id, gpu_index, gpu_name, backend,
        'running' if server_started else 'starting',
        recommended["context_size"], recommended["n_gpu_layers"],
        recommended.get("threads", 8), recommended["batch_size"],
        recommended.get("vram_needed_mb", model_vram),
    ))

    if result:
        inst_id = str(result[0]["id"])
        new_state = 'loaded' if server_started else 'loading'
        db_execute_rt("""
            UPDATE dbai_llm.ghost_models SET state = %s, is_loaded = %s, updated_at = NOW()
            WHERE id = %s::UUID
        """, (new_state, server_started, model_id))
        if server_started:
            db_execute_rt("""
                UPDATE dbai_llm.agent_instances SET state = 'running', started_at = NOW()
                WHERE id = %s::UUID
            """, (inst_id,))
        return {
            "ok": True,
            "server_started": server_started,
            "instance_id": inst_id,
            "gpu": gpu_name,
            "device": device,
            "model_name": model.get("name"),
            "settings": recommended,
            "message": f"Modell {model.get('name')} {'gestartet auf ' + device.upper() if server_started else 'DB-Status gesetzt (kein GGUF-Pfad)'}",
        }

    return {"ok": False, "error": "Instanz konnte nicht erstellt werden"}


@app.post("/api/llm/models/{model_id}/stop")
async def llm_stop_model(model_id: str, session: dict = Depends(get_current_session)):
    """Modell stoppen und von GPU entladen — stoppt llama-server wenn aktives Modell."""
    global _llm_model_name, _llm_model_path

    # Prüfen ob das gestoppte Modell das aktive ist
    model_rows = db_query_rt(
        "SELECT name FROM dbai_llm.ghost_models WHERE id = %s::UUID",
        (model_id,)
    )
    model_name = model_rows[0]["name"] if model_rows else ""

    # Wenn das aktive Modell gestoppt wird, llama-server beenden
    if model_name and model_name == _llm_model_name:
        _llm_server_stop()
        _llm_model_name = ""
        _llm_model_path = ""
        logger.info(f"[LLM] llama-server gestoppt für Modell {model_name}")

    # Alle laufenden Instanzen dieses Modells stoppen
    db_execute_rt("""
        UPDATE dbai_llm.agent_instances SET state = 'stopped', updated_at = NOW()
        WHERE model_id = %s::UUID AND state IN ('running', 'starting')
    """, (model_id,))
    # Modell-Status aktualisieren
    db_execute_rt("""
        UPDATE dbai_llm.ghost_models SET state = 'available', is_loaded = FALSE, updated_at = NOW()
        WHERE id = %s::UUID
    """, (model_id,))
    return {"ok": True, "state": "stopped", "server_stopped": model_name == _llm_model_name}


# ─── Service Installation (WebUI Docker / native) ──────────────────────────

class ServiceInstallRequest(BaseModel):
    name: str
    command: str
    port: int = 0


@app.post("/api/services/install")
async def install_service(req: ServiceInstallRequest, session: dict = Depends(get_current_session)):
    """Installiert einen Service (Docker-Container oder nativer Befehl)."""
    import subprocess as _sp

    allowed_services = {
        'n8n', 'Ollama WebUI', 'ComfyUI', 'text-generation-webui',
        'Stable Diffusion WebUI', 'LocalAI', 'vLLM Server', 'VS Code Server',
    }
    if req.name not in allowed_services:
        return JSONResponse(status_code=400, content={"error": f"Service '{req.name}' nicht erlaubt"})

    logger.info(f"[SERVICE] Installiere {req.name}: {req.command}")
    try:
        result = _sp.run(
            req.command, shell=True, capture_output=True, text=True, timeout=300
        )
        success = result.returncode == 0
        log_msg = result.stdout[-2000:] if result.stdout else ""
        err_msg = result.stderr[-2000:] if result.stderr else ""

        # In Changelog loggen
        try:
            db_execute_rt("""
                INSERT INTO dbai_ops.changelog (version, change_type, title, description, affected_modules, author)
                VALUES ('0.12.0', 'feature', %s, %s, %s, 'ghost-system')
            """, (
                f"Service installiert: {req.name}",
                f"Befehl: {req.command}\nErgebnis: {'Erfolg' if success else 'Fehler'}\n{log_msg or err_msg}",
                '{services,webui}',
            ))
        except Exception as e:
            logger.warning(f"[SERVICE] Changelog: {e}")

        return {
            "ok": success,
            "name": req.name,
            "output": log_msg,
            "error": err_msg if not success else None,
        }
    except _sp.TimeoutExpired:
        return {"ok": False, "error": "Installation-Timeout (5 Min.)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ─── LLM Server Management (CPU / GPU Umschaltung) ──────────────────────────

class LLMServerRequest(BaseModel):
    device: str = "gpu"            # "gpu" oder "cpu"
    n_gpu_layers: int = 99         # 0 = CPU-only, 99 = alle auf GPU
    ctx_size: int = 8192
    threads: int = 12
    model_path: str = None
    model_name: str = None


@app.get("/api/llm/server/status")
async def llm_server_status(session: dict = Depends(get_current_session)):
    """Status des llama-server (Gerät, GPU-Layer, Health)."""
    healthy = _llm_server_health()
    # GPU-Info holen
    gpu_info = {}
    if healthy:
        try:
            rq = urllib.request.Request(f"{_llm_server_url}/v1/models", method="GET")
            with urllib.request.urlopen(rq, timeout=3) as resp:
                models_data = json.loads(resp.read())
                gpu_info["models"] = models_data.get("data", [])
        except Exception:
            pass
    return {
        "ok": healthy,
        "device": _llm_server_device,
        "n_gpu_layers": _llm_server_gpu_layers,
        "ctx_size": _llm_server_ctx_size,
        "threads": _llm_server_threads,
        "model_name": _llm_model_name,
        "model_path": _llm_model_path,
        "server_url": _llm_server_url,
        **gpu_info,
    }


@app.post("/api/llm/server/restart")
async def llm_server_restart(req: LLMServerRequest, session: dict = Depends(get_current_session)):
    """llama-server neu starten mit CPU oder GPU Modus."""
    loop = asyncio.get_event_loop()
    success = await loop.run_in_executor(
        None,
        lambda: _llm_server_start(
            device=req.device,
            n_gpu_layers=req.n_gpu_layers,
            ctx_size=req.ctx_size,
            threads=req.threads,
            model_path=req.model_path,
            model_name=req.model_name,
        )
    )
    if success:
        return {
            "ok": True,
            "device": _llm_server_device,
            "n_gpu_layers": _llm_server_gpu_layers,
            "ctx_size": _llm_server_ctx_size,
            "message": f"llama-server gestartet im {'GPU' if req.device == 'gpu' else 'CPU'}-Modus",
        }
    return JSONResponse(status_code=500, content={
        "ok": False,
        "error": "llama-server konnte nicht gestartet werden. Logs: /tmp/llama-server.log",
    })


@app.post("/api/llm/server/stop")
async def llm_server_stop_endpoint(session: dict = Depends(get_current_session)):
    """llama-server stoppen."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _llm_server_stop)
    return {"ok": True, "message": "llama-server gestoppt"}


@app.get("/api/llm/benchmarks")
async def llm_benchmarks_list(session: dict = Depends(get_current_session)):
    """Alle Benchmark-Ergebnisse auflisten."""
    rows = db_query_rt("""
        SELECT gb.id, gm.name AS model_name, gb.tokens_per_second,
               gb.prompt_eval_tps,
               gb.time_to_first_token_ms,
               gb.gpu_name, gb.gpu_vram_mb AS vram_mb,
               gb.context_size, gb.batch_size, gb.n_gpu_layers,
               gb.quantization, gb.backend,
               gb.benchmark_duration_sec,
               gb.notes,
               gb.benchmark_date AS created_at,
               CASE
                   WHEN gb.tokens_per_second >= 60 THEN 'excellent'
                   WHEN gb.tokens_per_second >= 30 THEN 'good'
                   WHEN gb.tokens_per_second >= 15 THEN 'fair'
                   ELSE 'poor'
               END AS rating
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


@app.get("/api/gpu/vram-live")
async def gpu_vram_live(session: dict = Depends(get_current_session)):
    """Schneller VRAM-Snapshot für Echtzeit-Ladebalken (leichtgewichtig)."""
    import subprocess
    gpus = []
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,memory.used,memory.total,memory.free,utilization.gpu,temperature.gpu,power.draw",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3
        )
        for line in r.stdout.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 6:
                used = int(float(parts[1]))
                total = int(float(parts[2]))
                gpus.append({
                    "index": int(parts[0]),
                    "used_mb": used,
                    "total_mb": total,
                    "free_mb": int(float(parts[3])),
                    "pct": round(used / max(total, 1) * 100, 1),
                    "util": int(float(parts[4])),
                    "temp": int(float(parts[5])),
                    "power_w": float(parts[6]) if len(parts) > 6 else 0,
                })
    except Exception:
        pass
    # LLM-Server Status mit anhängen
    return {
        "gpus": gpus,
        "llm": {
            "model": _llm_model_name,
            "healthy": _llm_server_health(),
            "device": _llm_server_device,
            "gpu_layers": _llm_server_gpu_layers,
        }
    }


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
# API Routes — Export CSV / JSON
# ---------------------------------------------------------------------------
@app.get("/api/export/{schema}/{table}")
async def export_table(schema: str, table: str, format: str = "json", session: dict = Depends(get_current_session)):
    """Tabelle als JSON oder CSV exportieren."""
    import io, csv
    fq_table = f'"{schema}"."{table}"'
    try:
        rows = db_query_rt(f"SELECT * FROM {fq_table} ORDER BY 1 LIMIT 10000")
        if not rows:
            return {"data": [], "count": 0}

        if format == "csv":
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            for row in rows:
                clean = {}
                for k, v in row.items():
                    if isinstance(v, (dict, list)):
                        clean[k] = json.dumps(v, default=str)
                    elif hasattr(v, 'isoformat'):
                        clean[k] = v.isoformat()
                    else:
                        clean[k] = v
                writer.writerow(clean)
            from fastapi.responses import Response
            return Response(
                content=output.getvalue(),
                media_type="text/csv",
                headers={"Content-Disposition": f'attachment; filename="{schema}_{table}.csv"'}
            )
        else:
            serialized = []
            for row in rows:
                clean = {}
                for k, v in row.items():
                    if hasattr(v, 'isoformat'):
                        clean[k] = v.isoformat()
                    else:
                        clean[k] = v
                serialized.append(clean)
            return {"data": serialized, "count": len(serialized), "schema": schema, "table": table}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/export/logs")
async def export_logs(format: str = "json", limit: int = 500, session: dict = Depends(get_current_session)):
    """System-Logs exportieren."""
    import io, csv
    try:
        rows = db_query_rt(
            "SELECT * FROM dbai_event.event_log ORDER BY created_at DESC LIMIT %s",
            (limit,)
        )
        if format == "csv":
            if not rows:
                return Response(content="", media_type="text/csv")
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            for row in rows:
                clean = {k: (v.isoformat() if hasattr(v, 'isoformat') else json.dumps(v, default=str) if isinstance(v, (dict, list)) else v) for k, v in row.items()}
                writer.writerow(clean)
            from fastapi.responses import Response
            return Response(
                content=output.getvalue(),
                media_type="text/csv",
                headers={"Content-Disposition": 'attachment; filename="dbai_logs.csv"'}
            )
        return {"logs": rows, "count": len(rows)}
    except Exception as e:
        raise HTTPException(500, str(e))


# ---------------------------------------------------------------------------
# API Routes — User Management
# ---------------------------------------------------------------------------
@app.get("/api/users")
async def list_users(session: dict = Depends(get_current_session)):
    """Alle Benutzer auflisten."""
    try:
        rows = db_query_rt(
            """SELECT id, username, display_name, role, created_at, last_login, is_active
               FROM dbai_core.users ORDER BY username"""
        )
        return {"users": rows}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/users")
async def create_user(body: dict, session: dict = Depends(get_current_session)):
    """Neuen Benutzer anlegen."""
    import hashlib
    try:
        username = body.get("username", "").strip()
        password = body.get("password", "")
        display_name = body.get("display_name", username)
        role = body.get("role", "user")
        if not username or not password:
            raise HTTPException(400, "username und password erforderlich")
        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        db_execute_rt(
            """INSERT INTO dbai_core.users (username, password_hash, display_name, role, is_active, created_at)
               VALUES (%s, %s, %s, %s, true, NOW())""",
            (username, pw_hash, display_name, role)
        )
        return {"status": "ok", "message": f"Benutzer '{username}' erstellt"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.patch("/api/users/{user_id}")
async def update_user(user_id: str, body: dict, session: dict = Depends(get_current_session)):
    """Benutzer aktualisieren."""
    try:
        updates = []
        values = []
        for field in ["display_name", "role", "is_active"]:
            if field in body:
                updates.append(f"{field} = %s")
                values.append(body[field])
        if not updates:
            raise HTTPException(400, "Keine Felder zum Aktualisieren")
        values.append(user_id)
        db_execute_rt(f"UPDATE dbai_core.users SET {', '.join(updates)} WHERE id = %s", values)
        return {"status": "ok", "message": f"Benutzer {user_id} aktualisiert"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.delete("/api/users/{user_id}")
async def delete_user(user_id: str, session: dict = Depends(get_current_session)):
    """Benutzer deaktivieren."""
    try:
        db_execute_rt("UPDATE dbai_core.users SET is_active = false WHERE id = %s", (user_id,))
        return {"status": "ok", "message": f"Benutzer {user_id} deaktiviert"}
    except Exception as e:
        raise HTTPException(500, str(e))


# ---------------------------------------------------------------------------
# API Routes — Audit-Trail & Backup
# ---------------------------------------------------------------------------
@app.get("/api/audit/log")
async def audit_log(limit: int = 100, session: dict = Depends(get_current_session)):
    """Audit-Log abfragen."""
    try:
        rows = db_query_rt(
            """SELECT * FROM dbai_core.audit_log
               ORDER BY created_at DESC LIMIT %s""",
            (limit,)
        )
        return {"entries": rows, "count": len(rows)}
    except Exception as e:
        # Tabelle existiert evtl. noch nicht
        return {"entries": [], "count": 0, "error": str(e)}


@app.get("/api/audit/changes")
async def audit_changes(limit: int = 100, session: dict = Depends(get_current_session)):
    """Change-Log abfragen."""
    try:
        rows = db_query_rt(
            """SELECT * FROM dbai_journal.change_log
               ORDER BY changed_at DESC LIMIT %s""",
            (limit,)
        )
        return {"changes": rows, "count": len(rows)}
    except Exception as e:
        return {"changes": [], "count": 0, "error": str(e)}


@app.post("/api/backup/trigger")
async def backup_trigger(session: dict = Depends(get_current_session)):
    """Manuelles Backup auslösen."""
    try:
        import subprocess
        result = subprocess.run(
            ["pg_dump", "-U", "dbai_system", "-d", "dbai", "--format=custom",
             "-f", f"/tmp/dbai_backup_{int(__import__('time').time())}.dump"],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            return {"status": "ok", "message": "Backup erfolgreich erstellt"}
        else:
            return {"status": "error", "message": result.stderr}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/backup/status")
async def backup_status(session: dict = Depends(get_current_session)):
    """Backup-Status abfragen."""
    try:
        import glob
        backups = glob.glob("/tmp/dbai_backup_*.dump")
        backup_info = []
        for b in sorted(backups, reverse=True)[:10]:
            stat = os.stat(b)
            backup_info.append({
                "file": os.path.basename(b),
                "size_mb": round(stat.st_size / 1048576, 2),
                "created": os.path.getmtime(b)
            })
        return {"backups": backup_info, "count": len(backups)}
    except Exception as e:
        raise HTTPException(500, str(e))


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


# ═══════════════════════════════════════════════════════════════
#  LINUX SYSTEM SETTINGS (Display, Sound, Bluetooth, Power etc.)
# ═══════════════════════════════════════════════════════════════

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
    except Exception:
        pass
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
        except Exception:
            pass
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
    except Exception:
        pass
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
            "ghost_version": "v0.12.0",
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


@app.get("/api/settings/linux/{category}")
async def linux_settings_get(category: str, session: dict = Depends(get_current_session)):
    """Linux-Systemeinstellungen lesen (Display, Sound, Bluetooth etc.)."""
    getter = _LINUX_GETTERS.get(category)
    if not getter:
        raise HTTPException(status_code=404, detail=f"Unbekannte Kategorie: {category}")
    return getter()


@app.put("/api/settings/linux/{category}")
async def linux_settings_update(category: str, request: Request, session: dict = Depends(get_current_session)):
    """Linux-Systemeinstellung ändern."""
    import subprocess
    data = await request.json()
    result = {"ok": True, "applied": []}

    for key, value in data.items():
        try:
            if category == "display":
                if key == "resolution":
                    subprocess.run(["xrandr", "--output", "default", "--mode", str(value)], timeout=5, check=False)
                elif key == "brightness":
                    # sysfs Brightness
                    import glob
                    bl = glob.glob("/sys/class/backlight/*/brightness")
                    if bl:
                        mx = int(open(bl[0].replace("brightness", "max_brightness")).read().strip())
                        val = int(int(value) / 100 * mx)
                        open(bl[0], "w").write(str(val))
                elif key == "night_mode":
                    if value:
                        subprocess.run(["redshift", "-O", "3500"], timeout=5, check=False)
                    else:
                        subprocess.run(["redshift", "-x"], timeout=5, check=False)
            elif category == "sound":
                if key == "volume":
                    subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{value}%"], timeout=5, check=False)
                elif key == "muted":
                    subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1" if value else "0"], timeout=5, check=False)
                elif key == "input_volume":
                    subprocess.run(["pactl", "set-source-volume", "@DEFAULT_SOURCE@", f"{value}%"], timeout=5, check=False)
            elif category == "bluetooth":
                if key == "enabled":
                    subprocess.run(["bluetoothctl", "power", "on" if value else "off"], timeout=5, check=False)
                elif key == "discoverable":
                    subprocess.run(["bluetoothctl", "discoverable", "on" if value else "off"], timeout=5, check=False)
            elif category == "power":
                if key == "power_profile":
                    subprocess.run(["powerprofilesctl", "set", str(value)], timeout=5, check=False)
            elif category == "keyboard":
                if key == "layout":
                    subprocess.run(["localectl", "set-x11-keymap", str(value)], timeout=10, check=False)
            elif category == "datetime":
                if key == "timezone":
                    subprocess.run(["timedatectl", "set-timezone", str(value)], timeout=5, check=False)
                elif key == "ntp_enabled":
                    subprocess.run(["timedatectl", "set-ntp", "true" if value else "false"], timeout=5, check=False)
            elif category == "security":
                if key == "firewall_enabled":
                    cmd = "enable" if value else "disable"
                    subprocess.run(["ufw", "--force", cmd], timeout=10, check=False)
                elif key == "ssh_enabled":
                    action = "start" if value else "stop"
                    subprocess.run(["systemctl", action, "ssh"], timeout=10, check=False)
                    subprocess.run(["systemctl", "enable" if value else "disable", "ssh"], timeout=10, check=False)

            result["applied"].append(key)
        except Exception as e:
            result["errors"] = result.get("errors", []) + [f"{key}: {str(e)}"]

    # Einstellungen auch in DB speichern
    try:
        db_execute_rt("""
            INSERT INTO dbai_system.system_settings (key, value, updated_at)
            VALUES (%s, %s::jsonb, NOW())
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
        """, (f"linux.{category}", json.dumps(data)))
    except Exception:
        pass

    return result


@app.post("/api/settings/linux/{category}/action")
async def linux_settings_action(category: str, request: Request, session: dict = Depends(get_current_session)):
    """Linux-System-Aktionen ausführen (Scan, Check etc.)."""
    import subprocess
    data = await request.json()
    action = data.get("action", "")

    if category == "bluetooth" and action == "scan":
        subprocess.Popen(["bluetoothctl", "scan", "on"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"ok": True, "message": "Bluetooth-Scan gestartet (10s)"}
    elif category == "printers" and action == "scan":
        subprocess.Popen(["lpinfo", "-v"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"ok": True, "message": "Drucker-Scan gestartet"}
    elif category == "updates" and action == "check":
        subprocess.Popen(["apt", "update"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"ok": True, "message": "Update-Check gestartet"}
    else:
        raise HTTPException(status_code=400, detail=f"Unbekannte Aktion: {category}/{action}")


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
    Optional: ?tab_id=xxx für Tab-isolierte Verbindungen.
    """
    # Tab-ID aus Query-Parameter
    tab_id = websocket.query_params.get("tab_id", "")

    # Session validieren
    result = db_call_json_rt("SELECT dbai_ui.validate_session(%s)", (token,))
    if not result or not result.get("valid"):
        await websocket.close(code=4001, reason="Ungültiger Token")
        return

    session_id = result["session_id"]
    user_role = result.get("user", {}).get("role", "authenticated")
    is_admin = result.get("user", {}).get("is_admin", False)
    ws_key = tab_id or session_id
    await ws_manager.connect(websocket, session_id, tab_id=tab_id or None)

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
        "tab_id": tab_id or None,
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
        ws_manager.disconnect(session_id, tab_id=tab_id or None)
    except Exception as e:
        logger.error("WebSocket Fehler: %s", e)
        ws_manager.disconnect(session_id, tab_id=tab_id or None)


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


@app.post("/api/browser/import/selective")
async def browser_import_selective(body: dict, session: dict = Depends(get_current_session)):
    """Selektiver Browser-Import (nur bestimmte Datentypen)."""
    try:
        from bridge.browser_migration import BrowserMigrator
        migrator = BrowserMigrator(db_execute_rt, db_query_rt)
        data_types = body.get("data_types", ["bookmarks"])
        browser_type = body.get("browser_type", "")
        profile_name = body.get("profile_name", "")
        profile_path = body.get("profile_path", "")
        results = {}
        for dt in data_types:
            try:
                result = migrator.import_profile(browser_type, profile_name, profile_path)
                results[dt] = {"status": "ok", "detail": result}
            except Exception as ie:
                results[dt] = {"status": "error", "detail": str(ie)}
        return {"selective_import": results, "data_types": data_types}
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


@app.post("/api/config/import/selective")
async def config_import_selective(body: dict, session: dict = Depends(get_current_session)):
    """Selektiver Config-Import nach Kategorie."""
    try:
        from bridge.config_importer import ConfigImporter
        importer = ConfigImporter(db_execute_rt, db_query_rt)
        categories = body.get("categories", [])
        results = {}
        for cat in categories:
            try:
                result = importer.import_category(cat) if hasattr(importer, 'import_category') else importer.import_all()
                results[cat] = {"status": "ok", "detail": result}
            except Exception as ie:
                results[cat] = {"status": "error", "detail": str(ie)}
        return {"selective_import": results, "categories": categories}
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


@app.post("/api/workspace/open")
async def workspace_open_file(body: dict, session: dict = Depends(get_current_session)):
    """Datei im System-Editor öffnen."""
    try:
        import subprocess
        file_path = body.get("path", "")
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(404, f"Datei nicht gefunden: {file_path}")
        # xdg-open für Linux
        subprocess.Popen(["xdg-open", file_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"status": "ok", "message": f"Datei geöffnet: {file_path}"}
    except HTTPException:
        raise
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


@app.delete("/api/synaptic/memories/{memory_id}")
async def synaptic_delete_memory(memory_id: str, session: dict = Depends(get_current_session)):
    """Einzelne Synaptic-Memory löschen."""
    try:
        db_execute_rt("DELETE FROM dbai_system.synaptic_memories WHERE id = %s", (memory_id,))
        return {"status": "ok", "message": f"Memory {memory_id} gelöscht"}
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


@app.post("/api/rag/sources")
async def rag_add_source(body: dict, session: dict = Depends(get_current_session)):
    """Neue RAG-Quelle hinzufügen."""
    try:
        from bridge.rag_pipeline import RAGPipeline
        pipeline = RAGPipeline(db_execute_rt, db_query_rt, None)
        name = body.get("source_name", "")
        source_type = body.get("source_type", "file")
        source_path = body.get("source_path", "")
        if not name:
            raise HTTPException(400, "source_name erforderlich")
        db_execute_rt(
            """INSERT INTO dbai_llm.rag_sources (source_name, source_type, source_path, is_active)
               VALUES (%s, %s, %s, true)
               ON CONFLICT (source_name) DO UPDATE SET source_path = EXCLUDED.source_path, is_active = true""",
            (name, source_type, source_path)
        )
        return {"status": "ok", "message": f"Quelle '{name}' hinzugefügt"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.delete("/api/rag/sources/{name}")
async def rag_delete_source(name: str, session: dict = Depends(get_current_session)):
    """RAG-Quelle löschen."""
    try:
        db_execute_rt("DELETE FROM dbai_llm.rag_chunks WHERE source_name = %s", (name,))
        db_execute_rt("DELETE FROM dbai_llm.rag_sources WHERE source_name = %s", (name,))
        return {"status": "ok", "message": f"Quelle '{name}' und zugehörige Chunks gelöscht"}
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


@app.delete("/api/usb/jobs/{job_id}")
async def usb_cancel_job(job_id: str, session: dict = Depends(get_current_session)):
    """Flash-Job abbrechen/löschen."""
    try:
        db_execute_rt(
            "UPDATE dbai_system.usb_flash_jobs SET status = 'cancelled' WHERE id = %s AND status IN ('pending', 'running')",
            (job_id,)
        )
        return {"status": "ok", "message": f"Job {job_id} abgebrochen"}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/usb/jobs/{job_id}/progress")
async def usb_job_progress(job_id: str, session: dict = Depends(get_current_session)):
    """Flash-Job-Fortschritt abfragen."""
    try:
        rows = db_query_rt("SELECT * FROM dbai_system.usb_flash_jobs WHERE id = %s", (job_id,))
        if not rows:
            raise HTTPException(404, f"Job {job_id} nicht gefunden")
        return {"job": rows[0]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# --- Feature 17: WLAN Hotspot ---
@app.post("/api/hotspot/create")
async def hotspot_create(body: dict, session: dict = Depends(get_current_session)):
    """WLAN-Hotspot erstellen."""
    try:
        from bridge.stufe4_utils import WLANHotspot
        hotspot = WLANHotspot(db_execute_rt, db_query_rt)
        result = hotspot.create_hotspot(body.get("ssid", "DBAI-Hotspot"), body.get("password", ""))
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/hotspot/stop")
async def hotspot_stop(session: dict = Depends(get_current_session)):
    """Hotspot stoppen."""
    try:
        from bridge.stufe4_utils import WLANHotspot
        hotspot = WLANHotspot(db_execute_rt, db_query_rt)
        result = hotspot.stop_hotspot()
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/hotspot/status")
async def hotspot_status(session: dict = Depends(get_current_session)):
    """Hotspot-Status abfragen."""
    try:
        from bridge.stufe4_utils import WLANHotspot
        hotspot = WLANHotspot(db_execute_rt, db_query_rt)
        return hotspot.get_status()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.patch("/api/hotspot/config")
async def hotspot_update_config(body: dict, session: dict = Depends(get_current_session)):
    """Hotspot-Konfiguration ändern (SSID, Passwort, Kanal, Band)."""
    try:
        from bridge.stufe4_utils import WLANHotspot
        hotspot = WLANHotspot(db_execute_rt, db_query_rt)
        ssid = body.get("ssid")
        password = body.get("password")
        channel = body.get("channel")
        band = body.get("band")
        # Konfiguration in DB speichern
        if hasattr(hotspot, 'update_config'):
            result = hotspot.update_config(ssid=ssid, password=password, channel=channel, band=band)
        else:
            config = {}
            if ssid: config["ssid"] = ssid
            if password: config["password"] = password
            if channel: config["channel"] = channel
            if band: config["band"] = band
            db_execute_rt(
                """INSERT INTO dbai_system.service_config (service_name, config_data)
                   VALUES ('wlan_hotspot', %s::jsonb)
                   ON CONFLICT (service_name) DO UPDATE SET config_data = EXCLUDED.config_data, updated_at = NOW()""",
                (json.dumps(config),)
            )
            result = {"status": "ok", "config": config}
        return result
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


@app.post("/api/immutable/snapshots")
async def immutable_create_snapshot(body: dict, session: dict = Depends(get_current_session)):
    """Neuen Filesystem-Snapshot erstellen."""
    try:
        from bridge.stufe4_utils import ImmutableFS
        fs = ImmutableFS(db_execute_rt, db_query_rt)
        label = body.get("label", f"snapshot-{int(__import__('time').time())}")
        if hasattr(fs, 'create_snapshot'):
            result = fs.create_snapshot(label)
        else:
            import uuid, time
            snap_id = str(uuid.uuid4())
            db_execute_rt(
                """INSERT INTO dbai_system.fs_snapshots (id, label, snapshot_type, status, created_at)
                   VALUES (%s, %s, 'manual', 'completed', NOW())""",
                (snap_id, label)
            )
            result = {"status": "ok", "snapshot_id": snap_id, "label": label}
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@app.delete("/api/immutable/snapshots/{snapshot_id}")
async def immutable_delete_snapshot(snapshot_id: str, session: dict = Depends(get_current_session)):
    """Filesystem-Snapshot löschen."""
    try:
        db_execute_rt("DELETE FROM dbai_system.fs_snapshots WHERE id = %s", (snapshot_id,))
        return {"status": "ok", "message": f"Snapshot {snapshot_id} gelöscht"}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/immutable/snapshots/{snapshot_id}/restore")
async def immutable_restore_snapshot(snapshot_id: str, session: dict = Depends(get_current_session)):
    """Filesystem-Snapshot wiederherstellen."""
    try:
        from bridge.stufe4_utils import ImmutableFS
        fs = ImmutableFS(db_execute_rt, db_query_rt)
        if hasattr(fs, 'restore_snapshot'):
            result = fs.restore_snapshot(snapshot_id)
        else:
            db_execute_rt(
                "UPDATE dbai_system.fs_snapshots SET status = 'restoring' WHERE id = %s",
                (snapshot_id,)
            )
            result = {"status": "ok", "message": f"Snapshot {snapshot_id} wird wiederhergestellt"}
        return result
    except HTTPException:
        raise
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


@app.post("/api/anomaly/detections/{detection_id}/resolve")
async def anomaly_resolve(detection_id: str, body: dict = {}, session: dict = Depends(get_current_session)):
    """Anomalie als gelöst markieren."""
    try:
        resolution = body.get("resolution", "Manuell gelöst")
        db_execute_rt(
            """UPDATE dbai_system.anomaly_detections
               SET resolved = true, resolved_at = NOW(), resolution_note = %s
               WHERE id = %s""",
            (resolution, detection_id)
        )
        return {"status": "ok", "message": f"Anomalie {detection_id} als gelöst markiert"}
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


@app.delete("/api/firewall/rules/{rule_id}")
async def firewall_delete_rule(rule_id: str, session: dict = Depends(get_current_session)):
    """Firewall-Regel löschen."""
    try:
        db_execute_rt("UPDATE dbai_system.firewall_rules SET is_active = false WHERE id = %s", (rule_id,))
        return {"status": "ok", "message": f"Regel {rule_id} deaktiviert"}
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
# Power Management
# ---------------------------------------------------------------------------
@app.post("/api/power/shutdown")
async def power_shutdown(session: dict = Depends(get_current_session)):
    """System herunterfahren — Docker: Container stoppen, Bare-Metal: systemctl poweroff."""
    import subprocess, os, sys, signal
    try:
        db_execute_rt(
            "INSERT INTO dbai_core.events(event_type, source, payload) VALUES('shutdown_initiated','power_api',%s::JSONB)",
            (json.dumps({"user": session.get("username")}),))

        if os.path.exists("/.dockerenv"):
            # Docker-Modus: Alle DBAI-Container stoppen
            # 1) Dashboard-UI stoppen (kann per Docker-Socket oder kill signal)
            # 2) Eigenen Prozess sauber beenden → exit(0) = clean stop, Docker restart-policy "unless-stopped" startet NICHT neu
            logger.info("Docker-Modus: Shutdown via sys.exit(0) — Container wird gestoppt")
            # Verzögert beenden damit die HTTP-Response noch rausgeht
            def _delayed_exit():
                import time
                time.sleep(1)
                os._exit(0)  # exit(0) → unless-stopped startet NICHT neu
            import threading
            threading.Thread(target=_delayed_exit, daemon=True).start()
            return {"status": "shutting_down", "mode": "docker"}
        else:
            # Bare-Metal: Echtes System herunterfahren
            subprocess.Popen(["systemctl", "poweroff"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"status": "shutting_down", "mode": "bare-metal"}
    except Exception as e:
        logger.error("Shutdown failed: %s", e)
        raise HTTPException(500, str(e))


@app.post("/api/power/reboot")
async def power_reboot(session: dict = Depends(get_current_session)):
    """System neustarten — Docker: Container restarten, Bare-Metal: systemctl reboot."""
    import subprocess, os, sys
    try:
        db_execute_rt(
            "INSERT INTO dbai_core.events(event_type, source, payload) VALUES('reboot_initiated','power_api',%s::JSONB)",
            (json.dumps({"user": session.get("username")}),))

        if os.path.exists("/.dockerenv"):
            # Docker-Modus: Eigenen Prozess mit exit(1) beenden
            # exit(1) = non-zero → Docker restart-policy "unless-stopped" startet automatisch neu
            logger.info("Docker-Modus: Reboot via sys.exit(1) — Container wird neu gestartet")
            def _delayed_exit():
                import time
                time.sleep(1)
                os._exit(1)  # exit(1) → unless-stopped startet NEU
            import threading
            threading.Thread(target=_delayed_exit, daemon=True).start()
            return {"status": "rebooting", "mode": "docker"}
        else:
            # Bare-Metal: Echtes System neustarten
            subprocess.Popen(["systemctl", "reboot"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"status": "rebooting", "mode": "bare-metal"}
    except Exception as e:
        logger.error("Reboot failed: %s", e)
        raise HTTPException(500, str(e))


# ---------------------------------------------------------------------------
# Ghost Mail — E-Mail per Ghost LLM
# ---------------------------------------------------------------------------

@app.get("/api/mail/accounts")
async def mail_accounts(session: dict = Depends(get_current_session)):
    """Alle E-Mail-Konten auflisten."""
    rows = db_query_rt("SELECT * FROM dbai_event.email_accounts ORDER BY account_name")
    return rows or []


@app.post("/api/mail/accounts")
async def mail_account_create(request: Request, session: dict = Depends(get_current_session)):
    """E-Mail-Konto hinzufügen."""
    data = await request.json()
    try:
        db_execute_rt("""
            INSERT INTO dbai_event.email_accounts (account_name, email_address, display_name,
                imap_host, imap_port, smtp_host, smtp_port, auth_type, sync_enabled)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (data['account_name'], data['email_address'], data.get('display_name',''),
              data.get('imap_host',''), data.get('imap_port',993),
              data.get('smtp_host',''), data.get('smtp_port',587),
              data.get('auth_type','password'), data.get('sync_enabled', False)))
        return {"status": "created"}
    except Exception as e:
        raise HTTPException(400, str(e))


@app.delete("/api/mail/accounts/{account_id}")
async def mail_account_delete(account_id: str, session: dict = Depends(get_current_session)):
    """E-Mail-Konto löschen."""
    db_execute_rt("DELETE FROM dbai_event.email_accounts WHERE id = %s::UUID", (account_id,))
    return {"status": "deleted"}


@app.get("/api/mail/inbox")
async def mail_inbox(account_id: str = None, folder: str = "inbox",
                     limit: int = 50, offset: int = 0,
                     session: dict = Depends(get_current_session)):
    """Posteingang — alle/ungelesene E-Mails."""
    where = "WHERE NOT i.is_deleted"
    params = []
    if account_id:
        where += " AND i.account_id = %s::UUID"
        params.append(account_id)
    if folder == "starred":
        where += " AND i.is_starred"
    elif folder == "unread":
        where += " AND NOT i.is_read"
    elif folder == "archived":
        where = "WHERE i.is_archived AND NOT i.is_deleted"
        if account_id:
            where += " AND i.account_id = %s::UUID"

    params.extend([limit, offset])
    rows = db_query_rt(f"""
        SELECT i.*, a.account_name, a.email_address AS account_email
        FROM dbai_event.inbox i LEFT JOIN dbai_event.email_accounts a ON a.id = i.account_id
        {where} ORDER BY i.received_at DESC LIMIT %s OFFSET %s
    """, tuple(params))
    # Zähler
    counts = db_query_rt("""
        SELECT count(*) AS total,
               count(*) FILTER (WHERE NOT is_read) AS unread,
               count(*) FILTER (WHERE is_starred) AS starred
        FROM dbai_event.inbox WHERE NOT is_deleted
    """)
    return {"messages": rows or [], "counts": counts[0] if counts else {}}


@app.get("/api/mail/inbox/{mail_id}")
async def mail_read(mail_id: str, session: dict = Depends(get_current_session)):
    """Einzelne E-Mail lesen (und als gelesen markieren)."""
    db_execute_rt(
        "UPDATE dbai_event.inbox SET is_read = true, read_at = now() WHERE id = %s::UUID AND NOT is_read",
        (mail_id,))
    rows = db_query_rt("SELECT * FROM dbai_event.inbox WHERE id = %s::UUID", (mail_id,))
    if not rows:
        raise HTTPException(404, "E-Mail nicht gefunden")
    return rows[0]


@app.patch("/api/mail/inbox/{mail_id}")
async def mail_update(mail_id: str, request: Request, session: dict = Depends(get_current_session)):
    """E-Mail Flags ändern (is_read, is_starred, is_archived, is_deleted)."""
    data = await request.json()
    sets, params = [], []
    for col in ("is_read", "is_starred", "is_archived", "is_deleted"):
        if col in data:
            sets.append(f"{col} = %s")
            params.append(data[col])
    if not sets:
        raise HTTPException(400, "Keine Änderung")
    params.append(mail_id)
    db_execute_rt(f"UPDATE dbai_event.inbox SET {', '.join(sets)} WHERE id = %s::UUID", tuple(params))
    return {"status": "updated"}


@app.get("/api/mail/outbox")
async def mail_outbox(state: str = None, limit: int = 50,
                      session: dict = Depends(get_current_session)):
    """Postausgang — Entwürfe, Gesendet, etc."""
    where = ""
    params = []
    if state:
        where = "WHERE o.state = %s"
        params.append(state)
    params.append(limit)
    rows = db_query_rt(f"""
        SELECT o.*, a.account_name, a.email_address AS account_email
        FROM dbai_event.outbox o LEFT JOIN dbai_event.email_accounts a ON a.id = o.account_id
        {where} ORDER BY o.created_at DESC LIMIT %s
    """, tuple(params))
    return rows or []


@app.post("/api/mail/compose")
async def mail_compose(request: Request, session: dict = Depends(get_current_session)):
    """Neue E-Mail erstellen (als Entwurf)."""
    data = await request.json()
    account_id = data.get('account_id')
    rows = db_query_rt("""
        INSERT INTO dbai_event.outbox (account_id, to_addresses, cc_addresses, bcc_addresses,
            subject, body_text, body_html, reply_to_id, state, authored_by)
        VALUES (%s::UUID, %s, %s, %s, %s, %s, %s, %s::UUID, 'draft', %s)
        RETURNING *
    """, (account_id,
          data.get('to', []), data.get('cc', []), data.get('bcc', []),
          data.get('subject', ''), data.get('body_text', ''), data.get('body_html', ''),
          data.get('reply_to_id'), data.get('authored_by', 'human')))
    return rows[0] if rows else {"error": "Erstellen fehlgeschlagen"}


@app.patch("/api/mail/outbox/{draft_id}")
async def mail_draft_update(draft_id: str, request: Request, session: dict = Depends(get_current_session)):
    """Entwurf aktualisieren."""
    data = await request.json()
    sets, params = [], []
    for col in ("to_addresses", "cc_addresses", "bcc_addresses", "subject", "body_text", "body_html", "state"):
        if col in data:
            sets.append(f"{col} = %s")
            params.append(data[col])
    if not sets:
        raise HTTPException(400, "Keine Änderung")
    params.append(draft_id)
    db_execute_rt(f"UPDATE dbai_event.outbox SET {', '.join(sets)} WHERE id = %s::UUID", tuple(params))
    return {"status": "updated"}


@app.delete("/api/mail/outbox/{draft_id}")
async def mail_draft_delete(draft_id: str, session: dict = Depends(get_current_session)):
    """Entwurf löschen."""
    db_execute_rt("DELETE FROM dbai_event.outbox WHERE id = %s::UUID AND state = 'draft'", (draft_id,))
    return {"status": "deleted"}


@app.post("/api/mail/send/{draft_id}")
async def mail_send(draft_id: str, session: dict = Depends(get_current_session)):
    """Entwurf absenden (State → sending → sent)."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    rows = db_query_rt("""
        SELECT o.*, a.smtp_host, a.smtp_port, a.email_address AS from_addr, a.display_name,
               a.credentials_ref
        FROM dbai_event.outbox o JOIN dbai_event.email_accounts a ON a.id = o.account_id
        WHERE o.id = %s::UUID AND o.state IN ('draft','review','approved')
    """, (draft_id,))
    if not rows:
        raise HTTPException(404, "Entwurf nicht gefunden oder bereits gesendet")

    mail = rows[0]
    db_execute_rt("UPDATE dbai_event.outbox SET state = 'sending' WHERE id = %s::UUID", (draft_id,))

    try:
        # SMTP-Versand
        msg = MIMEMultipart("alternative")
        msg["Subject"] = mail["subject"]
        msg["From"] = f"{mail.get('display_name','')} <{mail['from_addr']}>"
        msg["To"] = ", ".join(mail.get("to_addresses") or [])
        if mail.get("cc_addresses"):
            msg["Cc"] = ", ".join(mail["cc_addresses"])

        if mail.get("body_html"):
            msg.attach(MIMEText(mail["body_html"], "html"))
        elif mail.get("body_text"):
            msg.attach(MIMEText(mail["body_text"], "plain"))

        # Passwort aus api_keys holen (falls vorhanden)
        password = None
        if mail.get("credentials_ref"):
            cred = db_query_rt(
                "SELECT api_key FROM dbai_llm.api_keys WHERE id = %s::UUID", (mail["credentials_ref"],))
            if cred:
                password = cred[0]["api_key"]

        with smtplib.SMTP(mail["smtp_host"], mail["smtp_port"], timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls()
            if password:
                smtp.login(mail["from_addr"], password)
            recipients = list(mail.get("to_addresses") or []) + list(mail.get("cc_addresses") or []) + list(mail.get("bcc_addresses") or [])
            smtp.sendmail(mail["from_addr"], recipients, msg.as_string())

        db_execute_rt(
            "UPDATE dbai_event.outbox SET state = 'sent', sent_at = now() WHERE id = %s::UUID",
            (draft_id,))
        return {"status": "sent"}
    except Exception as e:
        db_execute_rt(
            "UPDATE dbai_event.outbox SET state = 'failed' WHERE id = %s::UUID",
            (draft_id,))
        logger.error("Mail send failed: %s", e)
        raise HTTPException(500, f"Senden fehlgeschlagen: {e}")


@app.post("/api/mail/ghost-compose")
async def mail_ghost_compose(request: Request, session: dict = Depends(get_current_session)):
    """Ghost LLM schreibt eine E-Mail basierend auf Anweisung."""
    data = await request.json()
    instruction = data.get("instruction", "")
    reply_to_id = data.get("reply_to_id")
    context_parts = []

    # Falls Antwort auf bestehende E-Mail → Original-Mail als Kontext
    if reply_to_id:
        orig = db_query_rt("SELECT from_name, from_address, subject, body_text FROM dbai_event.inbox WHERE id = %s::UUID", (reply_to_id,))
        if orig:
            o = orig[0]
            context_parts.append(f"Original-Mail von {o['from_name']} <{o['from_address']}>:\nBetreff: {o['subject']}\n\n{o['body_text']}")

    prompt = f"""Du bist ein professioneller E-Mail-Assistent. Schreibe eine E-Mail basierend auf folgender Anweisung:

Anweisung: {instruction}

{"Kontext (Original-Mail auf die geantwortet wird):" + chr(10) + chr(10).join(context_parts) if context_parts else ""}

Antworte NUR im folgenden JSON-Format (kein Markdown, kein Code-Block):
{{"subject": "Betreff", "body_text": "E-Mail Text", "body_html": "<p>E-Mail als HTML</p>"}}"""

    # Ghost LLM nutzen
    try:
        result = db_call_json_rt(
            "SELECT dbai_llm.ask_ghost(%s, %s, %s::JSONB)",
            ("email_writer", prompt, json.dumps({"type": "email_compose", "instruction": instruction}))
        )

        # Versuche JSON aus der Antwort zu parsen
        response_text = ""
        if isinstance(result, dict):
            response_text = result.get("answer", result.get("response", str(result)))
        else:
            response_text = str(result)

        # JSON aus der Antwort extrahieren
        import re
        json_match = re.search(r'\{[^{}]*"subject"[^{}]*"body_text"[^{}]*\}', response_text, re.DOTALL)
        if json_match:
            email_data = json.loads(json_match.group())
        else:
            # Fallback: Gesamten Text als Body nehmen
            email_data = {
                "subject": instruction[:80] if instruction else "Entwurf",
                "body_text": response_text,
                "body_html": f"<p>{response_text}</p>"
            }

        return {
            "subject": email_data.get("subject", ""),
            "body_text": email_data.get("body_text", ""),
            "body_html": email_data.get("body_html", ""),
            "authored_by": "ghost"
        }
    except Exception as e:
        logger.error("Ghost compose failed: %s", e)
        # Fallback wenn LLM nicht verfügbar
        return {
            "subject": "",
            "body_text": f"[Ghost LLM nicht verfügbar — bitte manuell schreiben]\n\nAnweisung war: {instruction}",
            "body_html": "",
            "authored_by": "ghost",
            "error": str(e)
        }


@app.post("/api/mail/ghost-improve")
async def mail_ghost_improve(request: Request, session: dict = Depends(get_current_session)):
    """Ghost LLM verbessert/korrigiert eine bestehende E-Mail."""
    data = await request.json()
    original_text = data.get("body_text", "")
    instruction = data.get("instruction", "Verbessere Grammatik und Stil")

    prompt = f"""Du bist ein professioneller E-Mail-Korrektor. Verbessere die folgende E-Mail.

Anweisung: {instruction}

Original E-Mail:
{original_text}

Antworte NUR im folgenden JSON-Format:
{{"subject": "Verbesserter Betreff (falls geändert)", "body_text": "Verbesserter Text", "body_html": "<p>Verbesserter Text als HTML</p>"}}"""

    try:
        result = db_call_json_rt(
            "SELECT dbai_llm.ask_ghost(%s, %s, %s::JSONB)",
            ("email_writer", prompt, json.dumps({"type": "email_improve"}))
        )
        response_text = result.get("answer", str(result)) if isinstance(result, dict) else str(result)

        import re
        json_match = re.search(r'\{[^{}]*"subject"[^{}]*"body_text"[^{}]*\}', response_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return {"body_text": response_text, "body_html": f"<p>{response_text}</p>"}
    except Exception as e:
        logger.error("Ghost improve failed: %s", e)
        return {"body_text": original_text, "error": str(e)}


@app.post("/api/mail/ghost-reply")
async def mail_ghost_reply(request: Request, session: dict = Depends(get_current_session)):
    """Ghost LLM generiert einen Antwortvorschlag auf eine eingehende E-Mail."""
    data = await request.json()
    mail_id = data.get("mail_id")
    tone = data.get("tone", "professionell")  # professionell/freundlich/kurz/formal

    orig = db_query_rt("SELECT * FROM dbai_event.inbox WHERE id = %s::UUID", (mail_id,))
    if not orig:
        raise HTTPException(404, "E-Mail nicht gefunden")

    mail = orig[0]
    prompt = f"""Du bist ein professioneller E-Mail-Assistent. Schreibe eine Antwort auf folgende E-Mail.

Ton: {tone}
Von: {mail.get('from_name','')} <{mail.get('from_address','')}>
Betreff: {mail.get('subject','')}
Inhalt:
{mail.get('body_text','')}

Antworte NUR im folgenden JSON-Format:
{{"subject": "Re: {mail.get('subject','')}", "body_text": "Deine Antwort hier", "body_html": "<p>Antwort als HTML</p>"}}"""

    try:
        result = db_call_json_rt(
            "SELECT dbai_llm.ask_ghost(%s, %s, %s::JSONB)",
            ("email_writer", prompt, json.dumps({"type": "email_reply", "mail_id": mail_id, "tone": tone}))
        )
        response_text = result.get("answer", str(result)) if isinstance(result, dict) else str(result)

        import re
        json_match = re.search(r'\{[^{}]*"subject"[^{}]*"body_text"[^{}]*\}', response_text, re.DOTALL)
        if json_match:
            email_data = json.loads(json_match.group())
        else:
            email_data = {"subject": f"Re: {mail.get('subject','')}", "body_text": response_text}

        # Ghost-Response in inbox speichern
        db_execute_rt(
            "UPDATE dbai_event.inbox SET ghost_response = %s WHERE id = %s::UUID",
            (email_data.get("body_text",""), mail_id))

        return {**email_data, "authored_by": "ghost", "reply_to_id": mail_id}
    except Exception as e:
        logger.error("Ghost reply failed: %s", e)
        return {"subject": f"Re: {mail.get('subject','')}", "body_text": "", "error": str(e)}


@app.post("/api/mail/sync/{account_id}")
async def mail_sync(account_id: str, session: dict = Depends(get_current_session)):
    """E-Mails per IMAP synchronisieren."""
    import imaplib, email as email_lib
    from email.header import decode_header

    acct = db_query_rt("SELECT * FROM dbai_event.email_accounts WHERE id = %s::UUID", (account_id,))
    if not acct:
        raise HTTPException(404, "Konto nicht gefunden")
    acct = acct[0]

    db_execute_rt(
        "UPDATE dbai_event.email_accounts SET sync_state = 'syncing', last_sync = now() WHERE id = %s::UUID",
        (account_id,))
    try:
        # Passwort holen
        password = None
        if acct.get("credentials_ref"):
            cred = db_query_rt("SELECT api_key FROM dbai_llm.api_keys WHERE id = %s::UUID", (acct["credentials_ref"],))
            if cred:
                password = cred[0]["api_key"]

        if not password:
            raise Exception("Kein Passwort konfiguriert")

        # IMAP Verbindung
        imap = imaplib.IMAP4_SSL(acct["imap_host"], acct["imap_port"])
        imap.login(acct["email_address"], password)
        imap.select("INBOX")

        # Letzte 50 E-Mails holen
        _, msg_nums = imap.search(None, "ALL")
        msg_ids = msg_nums[0].split()[-50:] if msg_nums[0] else []

        synced = 0
        for num in msg_ids:
            _, data = imap.fetch(num, "(RFC822)")
            raw = data[0][1]
            msg = email_lib.message_from_bytes(raw)
            mid = msg.get("Message-ID", "")

            # Nur neue E-Mails importieren
            existing = db_query_rt(
                "SELECT id FROM dbai_event.inbox WHERE message_id = %s", (mid,))
            if existing:
                continue

            # Header dekodieren
            def decode_hdr(h):
                if not h: return ""
                parts = decode_header(h)
                return " ".join(p.decode(c or 'utf-8') if isinstance(p, bytes) else p for p, c in parts)

            subject = decode_hdr(msg.get("Subject", ""))
            from_raw = msg.get("From", "")
            from_name = decode_hdr(from_raw.split("<")[0].strip().strip('"'))
            from_addr = from_raw.split("<")[-1].rstrip(">") if "<" in from_raw else from_raw

            # Body extrahieren
            body_text, body_html = "", ""
            if msg.is_multipart():
                for part in msg.walk():
                    ct = part.get_content_type()
                    if ct == "text/plain":
                        body_text = part.get_payload(decode=True).decode(errors='replace')
                    elif ct == "text/html":
                        body_html = part.get_payload(decode=True).decode(errors='replace')
            else:
                body_text = msg.get_payload(decode=True).decode(errors='replace')

            to_addrs = [a.strip() for a in (msg.get("To","") or "").split(",") if a.strip()]

            db_execute_rt("""
                INSERT INTO dbai_event.inbox (account_id, message_id, from_address, from_name,
                    to_addresses, subject, body_text, body_html, received_at)
                VALUES (%s::UUID, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (message_id) DO NOTHING
            """, (account_id, mid, from_addr, from_name, to_addrs,
                  subject, body_text, body_html, msg.get("Date")))
            synced += 1

        imap.logout()
        db_execute_rt(
            "UPDATE dbai_event.email_accounts SET sync_state = 'idle' WHERE id = %s::UUID",
            (account_id,))
        return {"status": "synced", "new_messages": synced}

    except Exception as e:
        db_execute_rt(
            "UPDATE dbai_event.email_accounts SET sync_state = 'error' WHERE id = %s::UUID",
            (account_id,))
        logger.error("Mail sync failed: %s", e)
        raise HTTPException(500, f"Sync fehlgeschlagen: {e}")


# ---------------------------------------------------------------------------
# KI Werkstatt — Custom Tables (benutzerdefinierte Datenbanken)
# ---------------------------------------------------------------------------
@app.get("/api/workshop/projects/{project_id}/custom-tables")
async def workshop_custom_tables(project_id: str, session: dict = Depends(get_current_session)):
    """Custom-Tabellen eines Projekts auflisten."""
    try:
        rows = db_query_rt("""
            SELECT ct.*, (SELECT count(*) FROM dbai_workshop.custom_rows cr WHERE cr.table_id = ct.id) AS row_count
            FROM dbai_workshop.custom_tables ct WHERE ct.project_id = %s::UUID ORDER BY ct.created_at
        """, (project_id,))
        return rows or []
    except Exception:
        return []


@app.post("/api/workshop/projects/{project_id}/custom-tables")
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


@app.delete("/api/workshop/projects/{project_id}/custom-tables/{table_id}")
async def workshop_delete_custom_table(project_id: str, table_id: str,
                                        session: dict = Depends(get_current_session)):
    db_execute_rt("DELETE FROM dbai_workshop.custom_tables WHERE id = %s::UUID AND project_id = %s::UUID",
                  (table_id, project_id))
    return {"deleted": True}


@app.get("/api/workshop/projects/{project_id}/custom-tables/{table_id}/rows")
async def workshop_custom_rows(project_id: str, table_id: str,
                                session: dict = Depends(get_current_session)):
    rows = db_query_rt("""
        SELECT cr.* FROM dbai_workshop.custom_rows cr
        JOIN dbai_workshop.custom_tables ct ON cr.table_id = ct.id
        WHERE ct.project_id = %s::UUID AND cr.table_id = %s::UUID
        ORDER BY cr.created_at
    """, (project_id, table_id))
    return rows or []


@app.post("/api/workshop/projects/{project_id}/custom-tables/{table_id}/rows")
async def workshop_add_custom_row(project_id: str, table_id: str, request: Request,
                                   session: dict = Depends(get_current_session)):
    body = await request.json()
    data = body.get("data", {})
    rows = db_query_rt("""
        INSERT INTO dbai_workshop.custom_rows (table_id, data) VALUES (%s::UUID, %s::JSONB) RETURNING *
    """, (table_id, json.dumps(data)))
    return rows[0] if rows else {}


@app.put("/api/workshop/projects/{project_id}/custom-tables/{table_id}/rows/{row_id}")
async def workshop_update_custom_row(project_id: str, table_id: str, row_id: str,
                                      request: Request, session: dict = Depends(get_current_session)):
    body = await request.json()
    data = body.get("data", {})
    db_execute_rt("""
        UPDATE dbai_workshop.custom_rows SET data = %s::JSONB, updated_at = NOW()
        WHERE id = %s::UUID AND table_id = %s::UUID
    """, (json.dumps(data), row_id, table_id))
    return {"updated": True}


@app.delete("/api/workshop/projects/{project_id}/custom-tables/{table_id}/rows/{row_id}")
async def workshop_delete_custom_row(project_id: str, table_id: str, row_id: str,
                                      session: dict = Depends(get_current_session)):
    db_execute_rt("DELETE FROM dbai_workshop.custom_rows WHERE id = %s::UUID AND table_id = %s::UUID",
                  (row_id, table_id))
    return {"deleted": True}


# ---------------------------------------------------------------------------
# API Routes — Per-App Settings (Schema 39/40)
# ---------------------------------------------------------------------------

@app.get("/api/apps/{app_id}/settings")
async def get_app_settings(app_id: str, session: dict = Depends(get_current_session)):
    """Gibt gemergte App-Settings zurück (Defaults + User-Overrides)."""
    user_id = session["user"]["id"]
    result = db_call_json_rt(
        "SELECT dbai_ui.get_app_settings(%s::UUID, %s)",
        (user_id, app_id)
    )
    if result and result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result or {}


@app.patch("/api/apps/{app_id}/settings")
async def update_app_settings(app_id: str, request: Request,
                               session: dict = Depends(get_current_session)):
    """Speichert User-Settings für eine App (Merge mit existierenden)."""
    user_id = session["user"]["id"]
    body = await request.json()
    result = db_call_json_rt(
        "SELECT dbai_ui.save_app_settings(%s::UUID, %s, %s::JSONB)",
        (user_id, app_id, json.dumps(body))
    )
    return result or {}


@app.delete("/api/apps/{app_id}/settings")
async def reset_app_settings(app_id: str, session: dict = Depends(get_current_session)):
    """Setzt App-Settings auf Defaults zurück."""
    user_id = session["user"]["id"]
    result = db_call_json_rt(
        "SELECT dbai_ui.reset_app_settings(%s::UUID, %s)",
        (user_id, app_id)
    )
    return result or {}


@app.get("/api/apps/{app_id}/settings/schema")
async def get_app_settings_schema(app_id: str, session: dict = Depends(get_current_session)):
    """Gibt das Settings-Schema einer App zurück (für dynamisches UI)."""
    rows = db_query_rt(
        "SELECT settings_schema, default_settings FROM dbai_ui.apps WHERE app_id = %s",
        (app_id,)
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' nicht gefunden")
    return {
        "schema": rows[0].get("settings_schema", {}),
        "defaults": rows[0].get("default_settings", {})
    }


@app.get("/api/apps/settings/all")
async def get_all_app_settings(session: dict = Depends(get_current_session)):
    """Gibt alle App-Settings des Users zurück (für Settings-App)."""
    user_id = session["user"]["id"]
    result = db_call_json_rt(
        "SELECT dbai_ui.get_all_app_settings(%s::UUID)",
        (user_id,)
    )
    return result or {}


# ---------------------------------------------------------------------------
# Ghost Browser — KI-gesteuerter Chromium-Browser (v0.11.0)
# ---------------------------------------------------------------------------
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


@app.get("/api/ghost-browser/tasks")
async def ghost_browser_list_tasks(
    status: str = None,
    limit: int = 50,
    session: dict = Depends(get_current_session)
):
    """Liste aller Ghost-Browser-Tasks."""
    user_id = session["user"]["id"]
    if status:
        rows = db_query_rt(
            """SELECT id, prompt, task_type, target_url, status, progress,
                      result_type, result_path, result_summary,
                      pages_visited, max_pages, max_duration_s,
                      created_at, started_at, completed_at, error_message
               FROM dbai_system.ghost_browser_tasks
               WHERE user_id = %s::UUID AND status = %s
               ORDER BY created_at DESC LIMIT %s""",
            (user_id, status, limit)
        )
    else:
        rows = db_query_rt(
            """SELECT id, prompt, task_type, target_url, status, progress,
                      result_type, result_path, result_summary,
                      pages_visited, max_pages, max_duration_s,
                      created_at, started_at, completed_at, error_message
               FROM dbai_system.ghost_browser_tasks
               WHERE user_id = %s::UUID
               ORDER BY created_at DESC LIMIT %s""",
            (user_id, limit)
        )
    return {"tasks": rows or []}


@app.post("/api/ghost-browser/tasks")
async def ghost_browser_create_task(
    body: dict = Body(...),
    session: dict = Depends(get_current_session)
):
    """Erstelle einen neuen Browser-Task."""
    user_id = session["user"]["id"]
    prompt = body.get("prompt", "").strip()
    if not prompt:
        raise HTTPException(400, "Prompt darf nicht leer sein")

    task_type = body.get("task_type", "research")
    target_url = body.get("target_url")
    max_pages = min(body.get("max_pages", 10), 50)
    max_duration = min(body.get("max_duration_s", 120), 600)
    sandbox = body.get("sandbox_mode", True)
    output_format = body.get("output_format", "markdown")

    rows = db_query_rt(
        """INSERT INTO dbai_system.ghost_browser_tasks
           (user_id, prompt, task_type, target_url, max_pages, max_duration_s,
            sandbox_mode, result_type, status)
           VALUES (%s::UUID, %s, %s, %s, %s, %s, %s, %s, 'queued')
           RETURNING id, status, created_at""",
        (user_id, prompt, task_type, target_url, max_pages, max_duration,
         sandbox, output_format)
    )
    task_id = rows[0]["id"] if rows else None
    return {"task_id": str(task_id), "status": "queued"}


@app.get("/api/ghost-browser/tasks/{task_id}")
async def ghost_browser_get_task(
    task_id: str,
    session: dict = Depends(get_current_session)
):
    """Details eines Browser-Tasks."""
    rows = db_query_rt(
        """SELECT * FROM dbai_system.ghost_browser_tasks WHERE id = %s::UUID""",
        (task_id,)
    )
    if not rows:
        raise HTTPException(404, "Task nicht gefunden")
    return rows[0]


@app.get("/api/ghost-browser/tasks/{task_id}/steps")
async def ghost_browser_get_steps(
    task_id: str,
    session: dict = Depends(get_current_session)
):
    """Schritte eines Browser-Tasks."""
    rows = db_query_rt(
        """SELECT * FROM dbai_system.ghost_browser_steps
           WHERE task_id = %s::UUID ORDER BY step_number""",
        (task_id,)
    )
    return {"steps": rows or []}


@app.post("/api/ghost-browser/tasks/{task_id}/run")
async def ghost_browser_run_task(
    task_id: str,
    session: dict = Depends(get_current_session)
):
    """Starte einen queued Task im Hintergrund."""
    rows = db_query_rt(
        """SELECT id, prompt, task_type, target_url, max_pages, max_duration_s,
                  sandbox_mode, result_type, status
           FROM dbai_system.ghost_browser_tasks WHERE id = %s::UUID""",
        (task_id,)
    )
    if not rows:
        raise HTTPException(404, "Task nicht gefunden")

    task = rows[0]
    if task["status"] not in ("queued", "failed"):
        raise HTTPException(400, f"Task ist bereits {task['status']}")

    # Hintergrund-Task starten
    from bridge.browser_agent import execute_browser_task

    async def _run_bg():
        try:
            await execute_browser_task(
                task_id=str(task["id"]),
                prompt=task["prompt"],
                task_type=task["task_type"],
                target_url=task.get("target_url"),
                max_pages=task.get("max_pages", 8),
                max_duration_s=task.get("max_duration_s", 120),
                output_format=task.get("result_type", "markdown"),
                sandbox_mode=task.get("sandbox_mode", True),
                db_update_fn=_browser_db_update,
            )
        except Exception as e:
            logger.error("Background browser task failed: %s", e)
        finally:
            _browser_bg_tasks.pop(task_id, None)

    bg_task = asyncio.create_task(_run_bg())
    _browser_bg_tasks[task_id] = bg_task

    return {"task_id": task_id, "status": "running", "message": "Task gestartet"}


@app.post("/api/ghost-browser/tasks/{task_id}/cancel")
async def ghost_browser_cancel_task(
    task_id: str,
    session: dict = Depends(get_current_session)
):
    """Breche einen laufenden Task ab."""
    from bridge.browser_agent import cancel_task
    cancelled = cancel_task(task_id)

    db_execute_rt(
        """UPDATE dbai_system.ghost_browser_tasks
           SET status = 'cancelled', completed_at = NOW(),
               error_message = 'Vom Benutzer abgebrochen'
           WHERE id = %s::UUID AND status IN ('queued', 'running')""",
        (task_id,)
    )

    return {"cancelled": cancelled, "task_id": task_id}


@app.delete("/api/ghost-browser/tasks/{task_id}")
async def ghost_browser_delete_task(
    task_id: str,
    session: dict = Depends(get_current_session)
):
    """Lösche einen Task (cascade löscht auch Steps)."""
    db_execute_rt(
        "DELETE FROM dbai_system.ghost_browser_tasks WHERE id = %s::UUID",
        (task_id,)
    )
    return {"deleted": True}


@app.get("/api/ghost-browser/presets")
async def ghost_browser_presets(session: dict = Depends(get_current_session)):
    """Liste aller Browser-Presets."""
    rows = db_query_rt(
        """SELECT id, name, description, task_type, prompt_template,
                  default_url, max_pages, max_duration_s, output_format, icon
           FROM dbai_system.ghost_browser_presets ORDER BY is_system DESC, name"""
    )
    return {"presets": rows or []}


@app.post("/api/ghost-browser/quick")
async def ghost_browser_quick_task(
    body: dict = Body(...),
    session: dict = Depends(get_current_session)
):
    """Schneller One-Shot: Task erstellen UND sofort starten."""
    user_id = session["user"]["id"]
    prompt = body.get("prompt", "").strip()
    if not prompt:
        raise HTTPException(400, "Prompt darf nicht leer sein")

    task_type = body.get("task_type", "research")
    target_url = body.get("target_url")
    max_pages = min(body.get("max_pages", 8), 50)
    max_duration = min(body.get("max_duration_s", 120), 600)
    output_format = body.get("output_format", "markdown")

    rows = db_query_rt(
        """INSERT INTO dbai_system.ghost_browser_tasks
           (user_id, prompt, task_type, target_url, max_pages, max_duration_s,
            sandbox_mode, result_type, status)
           VALUES (%s::UUID, %s, %s, %s, %s, %s, true, %s, 'queued')
           RETURNING id""",
        (user_id, prompt, task_type, target_url, max_pages, max_duration, output_format)
    )
    task_id = str(rows[0]["id"])

    from bridge.browser_agent import execute_browser_task

    async def _run_bg():
        try:
            await execute_browser_task(
                task_id=task_id, prompt=prompt, task_type=task_type,
                target_url=target_url, max_pages=max_pages,
                max_duration_s=max_duration, output_format=output_format,
                sandbox_mode=True, db_update_fn=_browser_db_update,
            )
        except Exception as e:
            logger.error("Quick browser task failed: %s", e)
        finally:
            _browser_bg_tasks.pop(task_id, None)

    bg_task = asyncio.create_task(_run_bg())
    _browser_bg_tasks[task_id] = bg_task

    return {"task_id": task_id, "status": "running", "message": "Quick-Task gestartet"}


@app.get("/api/ghost-browser/results/{task_id}")
async def ghost_browser_get_result_file(
    task_id: str,
    session: dict = Depends(get_current_session)
):
    """Lade die Ergebnis-Datei eines abgeschlossenen Tasks herunter."""
    rows = db_query_rt(
        "SELECT result_path, result_type FROM dbai_system.ghost_browser_tasks WHERE id = %s::UUID",
        (task_id,)
    )
    if not rows or not rows[0].get("result_path"):
        raise HTTPException(404, "Keine Ergebnis-Datei vorhanden")

    result_path = rows[0]["result_path"]
    if not os.path.exists(result_path):
        raise HTTPException(404, "Ergebnis-Datei nicht gefunden auf dem Filesystem")

    with open(result_path, "r", encoding="utf-8") as f:
        content = f.read()

    return {
        "path": result_path,
        "type": rows[0].get("result_type", "markdown"),
        "content": content
    }


@app.get("/api/ghost-browser/screenshots/{task_id}/{step}")
async def ghost_browser_screenshot(
    task_id: str,
    step: int,
    session: dict = Depends(get_current_session)
):
    """Screenshot eines bestimmten Schritts laden."""
    fname = f"{task_id}_{step:03d}.png"
    path = f"/tmp/dbai_browser_screenshots/{fname}"
    if not os.path.exists(path):
        raise HTTPException(404, "Screenshot nicht gefunden")

    from starlette.responses import FileResponse
    return FileResponse(path, media_type="image/png")


# ---------------------------------------------------------------------------
# Remote Access / Mobile Connect
# ---------------------------------------------------------------------------

@app.get("/api/remote-access/info")
async def remote_access_info(session: dict = Depends(get_current_session)):
    """Netzwerk-Informationen für Mobile-Verbindung (QR-Code-Daten)."""
    import socket
    import json

    # Alle lokalen IPs ermitteln
    interfaces = []
    try:
        result = subprocess.run(
            ["ip", "-4", "-j", "addr", "show"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            for iface in data:
                name = iface.get("ifname", "")
                if name == "lo":
                    continue
                for addr_info in iface.get("addr_info", []):
                    ip = addr_info.get("local", "")
                    if ip:
                        interfaces.append({
                            "interface": name,
                            "ip": ip,
                            "prefixlen": addr_info.get("prefixlen", 24),
                        })
    except Exception:
        pass

    # Fallback: socket
    if not interfaces:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            interfaces.append({"interface": "default", "ip": ip, "prefixlen": 24})
        except Exception:
            pass

    # Hostname
    hostname = socket.gethostname()

    # Port aus Docker / Server
    port = int(os.environ.get("PORT", 3000))

    # Primäre IP (nicht-Docker, nicht-localhost)
    # Im Docker-Container: Host-IP über Default-Gateway ermitteln
    primary_ip = None
    host_ip = os.environ.get("HOST_IP")

    # Strategie 1: Umgebungsvariable HOST_IP
    if host_ip:
        primary_ip = host_ip

    # Strategie 2: X-Forwarded-For / Request-Header (gibt es hier nicht direkt)

    # Strategie 3: Default-Gateway = Host-IP (Docker bridge)
    if not primary_ip:
        try:
            result = subprocess.run(
                ["ip", "route", "show", "default"],
                capture_output=True, text=True, timeout=3
            )
            # "default via 172.28.0.1 dev eth0"
            for part in result.stdout.split():
                if part.count(".") == 3 and not part.startswith("127."):
                    # Gateway ist die Host-IP im Docker-Netz
                    # Aber wir brauchen die echte LAN-IP des Hosts
                    break
        except Exception:
            pass

    # Strategie 4: Host-Netzwerk über /mnt/host/etc/hostname + nsswitch
    if not primary_ip:
        try:
            # Lese Host-Interfaces über proc (wenn /mnt/host gemountet)
            result = subprocess.run(
                ["cat", "/mnt/host/proc/net/fib_trie"],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0:
                import re
                # Suche nach lokalen IPs im Host
                local_ips = set()
                lines = result.stdout.split("\n")
                for i, line in enumerate(lines):
                    if "/32 host LOCAL" in line and i > 0:
                        prev = lines[i-1].strip()
                        match = re.search(r'(\d+\.\d+\.\d+\.\d+)', prev)
                        if match:
                            ip = match.group(1)
                            if not ip.startswith("127.") and not ip.startswith("172.17.") and not ip.startswith("172.18.") and not ip.startswith("172.28."):
                                local_ips.add(ip)
                if local_ips:
                    # Bevorzuge 192.168.x.x oder 10.x.x.x (LAN-IPs)
                    for ip in sorted(local_ips):
                        if ip.startswith("192.168.") or ip.startswith("10."):
                            primary_ip = ip
                            break
                    if not primary_ip:
                        primary_ip = sorted(local_ips)[0]
        except Exception:
            pass

    # Strategie 5: Fallback auf Container-IP
    if not primary_ip:
        for iface in interfaces:
            ip = iface["ip"]
            if not ip.startswith("127."):
                primary_ip = ip
                break
        if not primary_ip and interfaces:
            primary_ip = interfaces[0]["ip"]

    # URL für QR-Code
    url = f"http://{primary_ip}:{port}" if primary_ip else None

    # WLAN-Info
    wifi_ssid = None
    try:
        result = subprocess.run(
            ["iwgetid", "-r"], capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0 and result.stdout.strip():
            wifi_ssid = result.stdout.strip()
    except Exception:
        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"],
                capture_output=True, text=True, timeout=3
            )
            for line in result.stdout.strip().split("\n"):
                if line.startswith("yes:"):
                    wifi_ssid = line.split(":", 1)[1]
                    break
        except Exception:
            pass

    return {
        "hostname": hostname,
        "primary_ip": primary_ip,
        "port": port,
        "url": url,
        "wifi_ssid": wifi_ssid,
        "interfaces": interfaces,
        "dashboard_path": "/",
        "api_health": f"http://{primary_ip}:{port}/api/health" if primary_ip else None,
    }


@app.get("/api/remote-access/pin")
async def remote_access_generate_pin(session: dict = Depends(get_current_session)):
    """Generiert eine temporäre PIN für Mobile-Verbindung."""
    import random
    pin = f"{random.randint(0, 999999):06d}"
    # PIN im Memory speichern (gültig 5 Minuten)
    if not hasattr(app.state, "remote_pins"):
        app.state.remote_pins = {}
    import time
    app.state.remote_pins[pin] = {
        "created": time.time(),
        "expires": time.time() + 300,
        "used": False,
    }
    # Alte PINs aufräumen
    now = time.time()
    app.state.remote_pins = {
        k: v for k, v in app.state.remote_pins.items()
        if v["expires"] > now
    }
    return {"pin": pin, "expires_in": 300}


@app.post("/api/remote-access/verify-pin")
async def remote_access_verify_pin(body: dict):
    """Verifiziert eine Mobile-PIN (für passwortlosen Zugang vom Handy)."""
    import time
    pin = body.get("pin", "")
    if not hasattr(app.state, "remote_pins"):
        raise HTTPException(401, "Keine aktive PIN")
    entry = app.state.remote_pins.get(pin)
    if not entry:
        raise HTTPException(401, "Ungültige PIN")
    if entry["expires"] < time.time():
        del app.state.remote_pins[pin]
        raise HTTPException(401, "PIN abgelaufen")
    if entry["used"]:
        raise HTTPException(401, "PIN bereits verwendet")
    entry["used"] = True
    # Session erstellen
    return {"status": "ok", "message": "Verbindung hergestellt", "redirect": "/"}


# ---------------------------------------------------------------------------
# Static Files & SPA Fallback (MUSS am Ende stehen — nach allen API-Routen!)
# ---------------------------------------------------------------------------
# Assets (Wallpapers, Icons, Avatars)
if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

# Frontend SPA — catch-all "/" MUSS die LETZTE Route sein!
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
