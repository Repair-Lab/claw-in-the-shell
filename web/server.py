#!/usr/bin/env python3
"""
DBAI Web Server — FastAPI + WebSocket (Phase 2: dünne Shell)
=============================================================
Phase 2: Infrastruktur → web/common.py
       Routen      → web/routers.py (377 Routen)
       Diese Datei → Re-Export + Static Files + main()

WICHTIG: Die Static-Files-Mounts stehen HIER (nicht in common.py),
weil Starlette in Registrierungs-Reihenfolge matcht — die SPA-Catch-all-
Mounts MÜSSEN nach allen API-Routen kommen.

Re-exportiert alle common-Symbole für Test-Kompatibilität
(import server; server.decrypt_secret, server.app, etc.)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Import common (definiert app, alle Helper, alle State)
from common import *

# Import routers (registriert alle 377 Routen auf app)
from routers import llm, security, apps, core  # noqa: F401

# ---------------------------------------------------------------------------
# Static Files & SPA Fallback (MUSS am Ende stehen — nach allen API-Routen!)
# ---------------------------------------------------------------------------
if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

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
    logger.info("═══════════════════════════════════════════")
    logger.info("  DBAI Web Server — Ghost in the DB")
    logger.info("  %s:%d", WEB_HOST, WEB_PORT)
    logger.info("═══════════════════════════════════════════")
    uvicorn.run(
        app,
        host=WEB_HOST,
        port=WEB_PORT,
        reload=False,
        log_level="info",
    )

if __name__ == "__main__":
    main()
