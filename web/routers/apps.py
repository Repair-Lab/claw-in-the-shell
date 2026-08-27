"""
web/routers/apps.py — Workshop, Mail, Mobile, Ghost, Store, Market, SQL, RAG, USB, Browser, ...
===============================================================================================
195 Routen, extrahiert aus web/routers.py (Phase 2b).
app und alle Helper werden aus web/common.py importiert.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import *
from common import app, get_current_session, require_admin

from fastapi import HTTPException, Request, Body, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional

@app.post("/api/tabs/register")
async def register_tab(request: Request, session: dict = Depends(get_current_session)):
    """Tab beim Backend registrieren. Gibt Tab-Info + Hostname zurück."""
    data = await request.json()
    tab_id = data.get("tab_id", "")
    if not tab_id:
        raise HTTPException(400, "tab_id fehlt")
    result = await adb_call_json_rt(
        "SELECT dbai_ui.register_tab(%s::UUID, %s, %s, %s)",
        (session["session_id"], tab_id, data.get("hostname"), data.get("label"))
    )
    return result or {}

@app.get("/api/tabs")
async def list_tabs(session: dict = Depends(get_current_session)):
    """Alle aktiven Tabs dieser Session auflisten."""
    rows = await adb_query_rt("""
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
    await adb_execute_rt(
        f"UPDATE dbai_ui.tab_instances SET {', '.join(sets)} WHERE tab_id = %s AND session_id = %s::UUID",
        tuple(params))
    return {"ok": True}

@app.post("/api/tabs/{tab_id}/heartbeat")
async def tab_heartbeat(tab_id: str, session: dict = Depends(get_current_session)):
    """Tab-Heartbeat — hält den Tab aktiv."""
    await adb_execute_rt(
        "UPDATE dbai_ui.tab_instances SET last_heartbeat = NOW() WHERE tab_id = %s AND session_id = %s::UUID",
        (tab_id, session["session_id"]))
    return {"ok": True}

@app.delete("/api/tabs/{tab_id}")
async def close_tab(tab_id: str, session: dict = Depends(get_current_session)):
    """Tab schließen — Windows + Tab-Instanz deaktivieren."""
    await adb_execute_rt("DELETE FROM dbai_ui.windows WHERE tab_id = %s", (tab_id,))
    await adb_execute_rt(
        "UPDATE dbai_ui.tab_instances SET is_active = FALSE WHERE tab_id = %s AND session_id = %s::UUID",
        (tab_id, session["session_id"]))
    return {"ok": True}

@app.post("/api/windows/open/{app_id}")
async def open_window(app_id: str, request: Request, session: dict = Depends(get_current_session)):
    """Öffnet ein neues Fenster für eine App (Tab-isoliert)."""
    tab_id = request.headers.get("X-Tab-Id", "")
    rows = await adb_query_rt(
        "SELECT * FROM dbai_ui.apps WHERE app_id = %s", (app_id,)
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' nicht gefunden")

    app_data = rows[0]
    result = await adb_query_rt("""
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
    await adb_execute_rt(
        f"UPDATE dbai_ui.windows SET {', '.join(sets)} WHERE id = %s::UUID",
        tuple(params)
    )
    return {"ok": True}

@app.delete("/api/windows/{window_id}")
async def close_window(window_id: str, session: dict = Depends(get_current_session)):
    """Schließt ein Fenster."""
    await adb_execute_rt("DELETE FROM dbai_ui.windows WHERE id = %s::UUID", (window_id,))
    await ws_manager.broadcast({"type": "window_closed", "window_id": window_id})
    return {"ok": True}

@app.get("/api/ghosts")
async def get_ghosts(session: dict = Depends(get_current_session)):
    """Alle aktiven Ghosts und verfügbaren Modelle."""
    active = await adb_query_rt("SELECT * FROM dbai_llm.vw_active_ghosts")
    models = await adb_query_rt("SELECT * FROM dbai_llm.ghost_models ORDER BY name")
    roles = await adb_query_rt("SELECT * FROM dbai_llm.ghost_roles ORDER BY priority")
    compatibility = await adb_query_rt("""
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
            SELECT name, model_path, required_vram_mb, is_loaded,
                   CASE WHEN state != 'removed' THEN TRUE ELSE FALSE END AS is_active,
                   capabilities, created_at
            FROM dbai_llm.ghost_models ORDER BY name
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
    body = _validate_body(await request.json(), required=["package_name"])
    pkg = body["package_name"]
    src = body.get("source_type", "apt")

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

    # Desktop-Icon erstellen (Node), falls noch nicht vorhanden
    node_key = f"store:{src}:{pkg}"
    existing_node = db_query_rt(
        "SELECT id FROM dbai_ui.desktop_nodes WHERE node_key = %s", (node_key,)
    )
    if not existing_node:
        icon_map = {
            'apt': 'server', 'flatpak': 'cloud', 'snap': 'cloud',
            'pip': 'play', 'github': 'web', 'system': 'server',
        }
        db_execute_rt("""
            INSERT INTO dbai_ui.desktop_nodes
                (node_key, label, node_type, icon_type, color, is_visible, sort_order)
            VALUES (%s, %s, 'app', %s, '#00f5ff', true,
                    COALESCE((SELECT MAX(sort_order) FROM dbai_ui.desktop_nodes), 0) + 1)
        """, (node_key, pkg, icon_map.get(src, 'circle')))

    return {"ok": True, "package": pkg, "state": "installed"}

@app.post("/api/store/uninstall")
async def store_uninstall(request: Request, session: dict = Depends(get_current_session)):
    """Paket vollständig entfernen: Katalog, Desktop-Icon, Settings, offene Fenster."""
    require_admin(session)
    body = await request.json()
    pkg = body.get("package_name")
    src = body.get("source_type", "apt")
    if not pkg:
        raise HTTPException(status_code=400, detail="package_name fehlt")

    # 1) Katalog-Status zurücksetzen
    db_execute_rt("""
        UPDATE dbai_core.software_catalog
        SET install_state = 'available', installed_at = NULL, updated_at = NOW()
        WHERE package_name = %s AND source_type = %s
    """, (pkg, src))

    # 2) Desktop-Icon (Node) entfernen
    node_key = f"store:{src}:{pkg}"
    db_execute_rt(
        "DELETE FROM dbai_ui.desktop_nodes WHERE node_key = %s", (node_key,)
    )

    # 3) App-spezifische Einstellungen entfernen
    #    app_id in app_user_settings ist text, node_key als Identifier nutzen
    db_execute_rt(
        "DELETE FROM dbai_ui.app_user_settings WHERE app_id = %s", (node_key,)
    )
    #    Auch nach package_name suchen (manche Apps nutzen den als app_id)
    db_execute_rt(
        "DELETE FROM dbai_ui.app_user_settings WHERE app_id = %s", (pkg,)
    )

    # 4) Offene Fenster dieser App schließen (content_state enthält ggf. node_key)
    #    windows.app_id ist UUID → über apps-Tabelle joinen wenn app_id == node_key
    try:
        app_row = db_query_rt(
            "SELECT id FROM dbai_ui.apps WHERE app_id = %s", (node_key,)
        )
        if app_row:
            db_execute_rt(
                "DELETE FROM dbai_ui.windows WHERE app_id = %s", (app_row[0]["id"],)
            )
    except Exception:
        pass  # Kein registriertes App-Fenster — OK

    # 5) Event loggen
    try:
        db_execute_rt("""
            INSERT INTO dbai_event.events (event_type, source, payload)
            VALUES ('app_uninstall', 'store_ui', %s::JSONB)
        """, (json.dumps({"package": pkg, "source_type": src, "cleanup": ["catalog", "desktop_node", "settings", "windows"]}),))
    except Exception:
        pass

    return {"ok": True, "package": pkg, "state": "available", "cleanup": ["catalog", "desktop_node", "settings", "windows"]}

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
    body = _validate_body(await request.json(), required=["full_name"])
    full_name = body["full_name"]
    name = body.get("name", full_name.split("/")[-1] if "/" in full_name else full_name)
    description = body.get("description", "")
    html_url = body.get("html_url", "")
    clone_url = body.get("clone_url", "")
    stars = body.get("stars", 0)
    language = body.get("language", "")
    license_id = body.get("license", "")
    topics = body.get("topics", [])
    size_kb = body.get("size_kb", 0)

    # Prüfe ob schon vorhanden
    existing = db_query_rt("""
        SELECT id, install_state FROM dbai_core.software_catalog
        WHERE package_name = %s AND source_type = 'github'
    """, (full_name,))

    if existing and existing[0].get("install_state") == "installed":
        # Sicherstellen, dass das Desktop-Icon existiert (Nachrüstung)
        node_key = f"store:github:{full_name}"
        existing_node = db_query_rt(
            "SELECT id FROM dbai_ui.desktop_nodes WHERE node_key = %s", (node_key,)
        )
        if not existing_node:
            display = name or (full_name.split("/")[-1] if "/" in full_name else full_name)
            db_execute_rt("""
                INSERT INTO dbai_ui.desktop_nodes
                    (node_key, label, node_type, icon_type, color, url, is_visible, sort_order)
                VALUES (%s, %s, 'app', 'web', '#00f5ff', %s, true,
                        COALESCE((SELECT MAX(sort_order) FROM dbai_ui.desktop_nodes), 0) + 1)
            """, (node_key, display, html_url))
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

    # Desktop-Icon erstellen (Node), falls noch nicht vorhanden
    node_key = f"store:github:{full_name}"
    existing_node = db_query_rt(
        "SELECT id FROM dbai_ui.desktop_nodes WHERE node_key = %s", (node_key,)
    )
    if not existing_node:
        display = name or full_name.split("/")[-1] if "/" in full_name else full_name
        db_execute_rt("""
            INSERT INTO dbai_ui.desktop_nodes
                (node_key, label, node_type, icon_type, color, url, is_visible, sort_order)
            VALUES (%s, %s, 'app', 'web', '#00f5ff', %s, true,
                    COALESCE((SELECT MAX(sort_order) FROM dbai_ui.desktop_nodes), 0) + 1)
        """, (node_key, display, html_url))

    return {"ok": True, "package": full_name, "state": "installed"}

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

@app.post("/api/services/install")
async def install_service(req: ServiceInstallRequest, session: dict = Depends(get_current_session)):
    """Installiert einen Service (Docker-Container oder nativer Befehl)."""
    require_admin(session)
    import subprocess as _sp

    cmd = _SERVICE_COMMANDS.get(req.name)
    if cmd is None:
        return JSONResponse(status_code=400, content={"error": f"Service '{req.name}' nicht erlaubt"})

    logger.info(f"[SERVICE] Installiere {req.name} (server-side command)")
    try:
        result = _sp.run(
            cmd, shell=False, capture_output=True, text=True, timeout=300
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
                f"Ergebnis: {'Erfolg' if success else 'Fehler'}\n{log_msg or err_msg}",
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

@app.get("/api/fs/browse")
async def fs_browse(path: str = "/", session: dict = Depends(get_current_session)):
    """Dateisystem durchsuchen — zeigt Verzeichnisse, Dateien, Mountpoints."""
    require_admin(session)
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
    columns = db_query_rt("""
        SELECT column_name AS name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position
    """, (schema, table))

    # Primary Key ermitteln
    pk_cols = db_query_rt("""
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
    rows = db_query_rt(f"SELECT * FROM {fq_table} LIMIT 200")

    # Tabellen-Stats
    stats_rows = db_query_rt(f"""
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
    require_admin(session)
    if not schema.replace('_', '').isalnum() or not table.replace('_', '').isalnum():
        raise HTTPException(status_code=400, detail="Ungültiger Schema/Tabellen-Name")

    body = await request.json()
    # Nur Felder mit Wert
    fields = {k: v for k, v in body.items() if v is not None and v != ''}
    if not fields:
        raise HTTPException(status_code=400, detail="Keine Daten zum Einfügen")

    # Spaltenvalidierung gegen information_schema (verhindert SQL-Injection via Spaltennamen)
    valid_cols_rows = db_query_rt(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = %s",
        (schema, table)
    )
    valid_cols = {r["column_name"] for r in valid_cols_rows}
    invalid = set(fields.keys()) - valid_cols
    if invalid:
        raise HTTPException(status_code=400, detail=f"Ungültige Spalten: {', '.join(sorted(invalid))}")

    cols = ', '.join(f'"{k}"' for k in fields.keys())
    placeholders = ', '.join(['%s'] * len(fields))
    values = [json.dumps(v) if isinstance(v, (dict, list)) else v for v in fields.values()]

    fq_table = f'"{schema}"."{table}"'
    db_execute_rt(f"INSERT INTO {fq_table} ({cols}) VALUES ({placeholders})", values)
    return {"ok": True}

@app.patch("/api/sql-explorer/rows/{schema}/{table}")
async def sql_explorer_update(schema: str, table: str, request: Request, session: dict = Depends(get_current_session)):
    """Zeile aktualisieren (mit Admin-Bestätigung)."""
    require_admin(session)
    if not schema.replace('_', '').isalnum() or not table.replace('_', '').isalnum():
        raise HTTPException(status_code=400, detail="Ungültiger Schema/Tabellen-Name")

    body = await request.json()

    # Spaltenvalidierung gegen information_schema
    valid_cols_rows = db_query_rt(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = %s",
        (schema, table)
    )
    valid_cols = {r["column_name"] for r in valid_cols_rows}
    invalid = set(body.keys()) - valid_cols
    if invalid:
        raise HTTPException(status_code=400, detail=f"Ungültige Spalten: {', '.join(sorted(invalid))}")

    # PK ermitteln
    pk_cols = db_query_rt("""
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
    db_execute_rt(sql, set_values + where_values)
    return {"ok": True}

@app.delete("/api/sql-explorer/rows/{schema}/{table}")
async def sql_explorer_delete(schema: str, table: str, request: Request, session: dict = Depends(get_current_session)):
    """Zeile löschen (mit Admin-Bestätigung)."""
    require_admin(session)
    if not schema.replace('_', '').isalnum() or not table.replace('_', '').isalnum():
        raise HTTPException(status_code=400, detail="Ungültiger Schema/Tabellen-Name")

    body = await request.json()

    # Spaltenvalidierung gegen information_schema
    valid_cols_rows = db_query_rt(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = %s",
        (schema, table)
    )
    valid_cols = {r["column_name"] for r in valid_cols_rows}
    invalid = set(body.keys()) - valid_cols
    if invalid:
        raise HTTPException(status_code=400, detail=f"Ungültige Spalten: {', '.join(sorted(invalid))}")

    # PK ermitteln
    pk_cols = db_query_rt("""
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
    try:
        db_execute_rt(f"DELETE FROM {fq_table} WHERE {' AND '.join(where_parts)}", where_values)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"ok": True}

@app.get("/api/export/{schema}/{table}")
async def export_table(schema: str, table: str, format: str = "json", session: dict = Depends(get_current_session)):
    """Tabelle als JSON oder CSV exportieren."""
    import io, csv
    fq_table = f'"{schema}"."{table}"'
    try:
        # Prüfe ob Tabelle existiert
        exists = db_query_rt(
            "SELECT 1 FROM information_schema.tables WHERE table_schema = %s AND table_name = %s",
            (schema, table)
        )
        if not exists:
            raise HTTPException(404, f"Tabelle {schema}.{table} nicht gefunden")
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
    except HTTPException:
        raise
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

@app.get("/api/users")
async def list_users(session: dict = Depends(get_current_session)):
    """Alle Benutzer auflisten."""
    require_admin(session)
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
    require_admin(session)
    # Mapping: Frontend-Rollen → DB-Rollen
    ROLE_MAP = {
        "admin": "dbai_system", "system": "dbai_system",
        "user": "dbai_monitor", "viewer": "dbai_monitor", "monitor": "dbai_monitor",
        "editor": "dbai_llm", "llm": "dbai_llm",
        "recovery": "dbai_recovery",
    }
    try:
        username = body.get("username", "").strip()
        password = body.get("password", "")
        display_name = body.get("display_name", username)
        role = body.get("role", "user")
        db_role = ROLE_MAP.get(role, "dbai_monitor")
        if not username or not password:
            raise HTTPException(400, "username und password erforderlich")
        # Passwort-Hash via pgcrypto bcrypt (gen_salt('bf') = Blowfish/bcrypt)
        db_execute_rt(
            """INSERT INTO dbai_core.users (username, password_hash, display_name, role, is_active, created_at)
               VALUES (%s, crypt(%s, gen_salt('bf')), %s, %s, true, NOW())""",
            (username, password, display_name, db_role)
        )
        return {"status": "ok", "message": f"Benutzer '{username}' erstellt"}
    except HTTPException:
        raise
    except Exception as e:
        err = str(e)
        if "duplicate key" in err or "already exists" in err:
            raise HTTPException(409, f"Benutzer '{username}' existiert bereits")
        raise HTTPException(500, err)

@app.patch("/api/users/{user_id}")
async def update_user(user_id: str, body: dict, session: dict = Depends(get_current_session)):
    """Benutzer aktualisieren."""
    require_admin(session)
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
    require_admin(session)
    try:
        db_execute_rt("UPDATE dbai_core.users SET is_active = false WHERE id = %s", (user_id,))
        return {"status": "ok", "message": f"Benutzer {user_id} deaktiviert"}
    except Exception as e:
        raise HTTPException(500, str(e))

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
    import shutil, subprocess
    pg_dump = shutil.which("pg_dump")
    if not pg_dump:
        # Häufige Pfade prüfen
        for p in ["/usr/bin/pg_dump", "/usr/lib/postgresql/16/bin/pg_dump",
                   "/usr/lib/postgresql/15/bin/pg_dump", "/usr/local/bin/pg_dump"]:
            if os.path.isfile(p):
                pg_dump = p
                break
    if not pg_dump:
        raise HTTPException(503, "pg_dump nicht verfügbar — postgresql-client muss im Container installiert sein")
    try:
        ts = int(__import__('time').time())
        dump_file = f"/tmp/dbai_backup_{ts}.dump"
        result = subprocess.run(
            [pg_dump, "-h", os.environ.get("DB_HOST", "postgres"), "-p", os.environ.get("DB_PORT", "5432"),
             "-U", os.environ.get("DB_USER", "dbai_system"), "-d", os.environ.get("DB_NAME", "dbai"),
             "--format=custom", "-f", dump_file],
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "PGPASSWORD": os.environ.get("DB_PASSWORD", "dbai2026")}
        )
        if result.returncode == 0:
            return {"status": "ok", "message": "Backup erfolgreich erstellt", "file": os.path.basename(dump_file)}
        else:
            return {"status": "error", "message": result.stderr}
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "Backup-Timeout (120s überschritten)")
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
            logger.warning("Setup: user_name speichern fehlgeschlagen", exc_info=True)

    if settings.get("ghostName"):
        try:
            db_execute_rt("""
                INSERT INTO dbai_llm.learning_entries (user_id, category, key, value)
                VALUES (%s::UUID, 'preference', 'ghost_name', %s)
                ON CONFLICT (user_id, category, key) DO UPDATE SET value = EXCLUDED.value
            """, (user_id, settings["ghostName"]))
        except Exception:
            logger.warning("Setup: ghost_name speichern fehlgeschlagen", exc_info=True)

    # GitHub-Token verschlüsselt speichern (falls angegeben)
    if settings.get("githubToken"):
        try:
            enc = encrypt_secret(settings["githubToken"])
            db_execute_rt(
                "UPDATE dbai_ui.users SET github_token_enc = %s WHERE id = %s::UUID",
                (enc, user_id)
            )
        except Exception:
            logger.warning("Setup: github_token speichern fehlgeschlagen", exc_info=True)

    # Theme setzen
    theme_name = settings.get("theme", "ghost-dark")
    try:
        db_execute_rt("""
            UPDATE dbai_ui.desktop_config
            SET theme_id = (SELECT id FROM dbai_ui.themes WHERE name = %s)
            WHERE user_id = %s::UUID
        """, (theme_name, user_id))
    except Exception:
        logger.warning("Setup: Theme setzen fehlgeschlagen", exc_info=True)

    # Config-Einträge setzen
    config_entries = [
        ("hostname", json.dumps(settings.get("hostname", "dbai")), "system"),
        ("default_model", json.dumps(settings.get("defaultModel", "qwen2.5-7b-instruct")), "llm"),
        ("auto_ghost_swap", json.dumps(settings.get("enableGhostSwap", True)), "ghost"),
        ("auto_heal", json.dumps(settings.get("enableAutoHeal", True)), "system"),
        ("telemetry_enabled", json.dumps(settings.get("enableTelemetry", True)), "system"),
    ]
    for key, value, cat in config_entries:
        try:
            db_execute_rt("""
                INSERT INTO dbai_core.config (key, value, category)
                VALUES (%s, %s, %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
            """, (key, value, cat))
        except Exception:
            logger.warning("Setup: Config '%s' speichern fehlgeschlagen", key, exc_info=True)

    # Provider-Konfigurationen speichern (aus KI-Setup-Step)
    providers_config = settings.get("providers", {})
    if providers_config:
        for pkey, pdata in providers_config.items():
            try:
                upd = []
                prm = []
                if pdata.get("api_key"):
                    enc = encrypt_secret(pdata["api_key"])
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

@app.post("/api/network/scan")
async def network_scan(session: dict = Depends(get_current_session)):
    """Netzwerk nach Web-UIs scannen. Prüft gängige HTTP-Ports (läuft im Thread)."""
    import asyncio
    result = await asyncio.to_thread(_do_network_scan)
    return result

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

@app.post("/api/learning/save")
async def learning_save(request: Request, session: dict = Depends(get_current_session)):
    """Benutzer-Präferenz / Lern-Eintrag speichern."""
    data = await request.json()
    key = data.get("key", "").strip() if isinstance(data.get("key"), str) else data.get("key")
    value = data.get("value")
    if not key:
        raise HTTPException(400, "key ist erforderlich")
    if value is None:
        raise HTTPException(400, "value ist erforderlich")
    user_id = session["user"]["id"]
    try:
        db_execute_rt("""
            INSERT INTO dbai_llm.learning_entries (user_id, category, key, value, context, confidence)
            VALUES (%s::UUID, %s, %s, %s, %s::JSONB, %s)
            ON CONFLICT (user_id, category, key)
            DO UPDATE SET value = EXCLUDED.value, context = EXCLUDED.context,
                          confidence = EXCLUDED.confidence, updated_at = NOW()
        """, (user_id, data.get("category", "preference"), key, value,
              json.dumps(data.get("context", {})), data.get("confidence", 1.0)))
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))

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
            ON CONFLICT (user_id, name) DO NOTHING
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

        # ON CONFLICT → Projekt existiert bereits, existierendes zurückgeben
        existing = db_query_rt("""
            SELECT id, name, description, icon, project_type, state, created_at
            FROM dbai_workshop.projects WHERE user_id = %s::UUID AND name = %s LIMIT 1
        """, (user_id, name))
        if existing:
            return existing[0]

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
        logger.exception("workshop_media query failed for project %s", project_id)
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
        logger.exception("workshop_collections query failed for project %s", project_id)
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
        logger.exception("workshop_devices query failed for project %s", project_id)
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
        logger.exception("workshop_import_jobs query failed for project %s", project_id)
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
        logger.exception("workshop_chat_history query failed for project %s", project_id)
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

@app.get("/api/themes")
async def get_themes(session: dict = Depends(get_current_session)):
    """Alle verfügbaren Themes."""
    rows = db_query_rt("SELECT * FROM dbai_ui.themes ORDER BY name")
    return rows

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
        try:
            await websocket.close(code=1011, reason="Server-Fehler")
        except Exception:
            pass

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
        browser_type = body.get("browser_type", "")
        valid_types = ("chrome", "firefox", "chromium", "brave", "edge", "vivaldi", "opera")
        if browser_type not in valid_types:
            raise HTTPException(422, f"Ungültiger Browser-Typ. Erlaubt: {', '.join(valid_types)}")
        result = migrator.import_profile(browser_type, body.get("profile_name", ""), body.get("profile_path", ""))
        return result
    except HTTPException:
        raise
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
    question = body.get("query", body.get("question", "")).strip()
    if not question:
        raise HTTPException(400, "Leere Abfrage")
    try:
        from bridge.rag_pipeline import RAGPipeline
        pipeline = RAGPipeline(db_execute_rt, db_query_rt, None)
        result = pipeline.query(question)
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
    """RAG-Quelle löschen (Chunks werden per FK CASCADE mitgelöscht)."""
    try:
        db_execute_rt("DELETE FROM dbai_llm.rag_sources WHERE source_name = %s", (name,))
        return {"status": "ok", "message": f"Quelle '{name}' und zugehörige Chunks gelöscht"}
    except Exception as e:
        raise HTTPException(500, str(e))

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
                """UPDATE dbai_system.hotspot_config
                   SET ssid = COALESCE(%s, ssid),
                       password = COALESCE(%s, password),
                       channel = COALESCE(%s, channel),
                       band = COALESCE(%s, band)
                   WHERE is_active = true""",
                (config.get("ssid"), config.get("password"), config.get("channel"), config.get("band"))
            )
            result = {"status": "ok", "config": config}
        return result
    except Exception as e:
        raise HTTPException(500, str(e))

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
                """INSERT INTO dbai_system.fs_snapshots (id, snapshot_name, label, snapshot_type, status, created_at)
                   VALUES (%s, %s, %s, 'manual', 'completed', NOW())""",
                (snap_id, label, label)
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

@app.post("/api/terminal/exec")
async def terminal_exec(body: dict, session: dict = Depends(get_current_session)):
    """Shell-Befehl ausführen (sandboxed). Nur Admins."""
    require_admin(session)
    import subprocess
    import shlex
    command = body.get("command", "").strip()
    cwd = body.get("cwd", os.path.expanduser("~"))
    if not command:
        return {"stdout": "", "stderr": "Kein Befehl angegeben", "exit_code": 1}

    # Blocklist prüfen (Regex-basiert, nicht trivial umgehbar)
    if _TERMINAL_BLOCKED_PATTERNS.search(command):
        return {"stdout": "", "stderr": "Befehl blockiert (Sicherheitsrichtlinie)", "exit_code": 126}

    try:
        # Terminal-Session in DB loggen
        db_execute_rt(
            "INSERT INTO dbai_ui.terminal_history (session_id, command, cwd) VALUES (%s, %s, %s)",
            (session.get("session_id", "default"), command, cwd)
        )
    except Exception:
        pass

    try:
        # shell=False + shlex.split() verhindert Shell-Expansion-Angriffe
        result = subprocess.run(
            shlex.split(command), shell=False, capture_output=True, text=True,
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

@app.post("/api/power/shutdown")
async def power_shutdown(session: dict = Depends(get_current_session)):
    """System herunterfahren — Docker: Container stoppen, Bare-Metal: systemctl poweroff."""
    import subprocess, os, sys, signal
    try:
        db_execute_rt(
            "INSERT INTO dbai_event.events(event_type, source, payload) VALUES('shutdown_initiated','power_api',%s::JSONB)",
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
            "INSERT INTO dbai_event.events(event_type, source, payload) VALUES('reboot_initiated','power_api',%s::JSONB)",
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
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(400, "Ungültiger JSON-Body")
    if not data or not isinstance(data, dict):
        raise HTTPException(400, "JSON-Objekt erforderlich")
    account_id = data.get('account_id')
    if not account_id:
        # Fallback: erstes verfügbares Konto verwenden
        accts = db_query_rt("SELECT id FROM dbai_event.email_accounts LIMIT 1")
        if accts:
            account_id = str(accts[0]["id"])
        else:
            raise HTTPException(400, "account_id erforderlich — kein E-Mail-Konto vorhanden")
    to_addrs = data.get('to', [])
    if isinstance(to_addrs, str):
        to_addrs = [to_addrs]
    if not to_addrs:
        raise HTTPException(400, "Empfänger (to) ist erforderlich")
    try:
        rows = db_query_rt("""
            INSERT INTO dbai_event.outbox (account_id, to_addresses, cc_addresses, bcc_addresses,
                subject, body_text, body_html, reply_to_id, state, authored_by)
            VALUES (%s::UUID, %s, %s, %s, %s, %s, %s, %s::UUID, 'draft', %s)
            RETURNING *
        """, (account_id,
              to_addrs, data.get('cc', []), data.get('bcc', []),
              data.get('subject', ''), data.get('body_text', data.get('body', '')),
              data.get('body_html', ''),
              data.get('reply_to_id'), data.get('authored_by', 'human')))
        return rows[0] if rows else {"error": "Erstellen fehlgeschlagen"}
    except Exception as e:
        raise HTTPException(500, str(e))

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
                "SELECT api_key FROM dbai_workshop.api_keys WHERE id = %s::UUID", (mail["credentials_ref"],))
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
            cred = db_query_rt("SELECT api_key FROM dbai_workshop.api_keys WHERE id = %s::UUID", (acct["credentials_ref"],))
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
        logger.exception("workshop_custom_tables query failed for project %s", project_id)
        return []

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

    async def _run_bg_quick():
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

    bg_task = asyncio.create_task(_run_bg_quick())
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

@app.get("/api/mobile-bridge/dimensions")
async def get_dimensions(session: dict = Depends(get_current_session)):
    """Alle 5 Dimensionen mit aktiven Verbindungen."""
    rows = db_query_rt("SELECT * FROM dbai_net.vw_five_dimensions")
    return {"dimensions": rows}

@app.get("/api/mobile-bridge/network")
async def get_network_status(session: dict = Depends(get_current_session)):
    """Netzwerk-Status: Interfaces, Hotspot, USB-Gadget."""
    interfaces = db_query_rt("SELECT * FROM dbai_net.vw_network_status")
    hotspot = db_query_rt("SELECT * FROM dbai_net.hotspot_config LIMIT 1")
    usb_gadget = db_query_rt("SELECT * FROM dbai_net.usb_gadget_config LIMIT 1")
    mdns = db_query_rt("SELECT * FROM dbai_net.mdns_config LIMIT 1")
    return {
        "interfaces": interfaces,
        "hotspot": hotspot[0] if hotspot else None,
        "usb_gadget": usb_gadget[0] if usb_gadget else None,
        "mdns": mdns[0] if mdns else None,
    }

@app.get("/api/mobile-bridge/devices")
async def get_mobile_devices(session: dict = Depends(get_current_session)):
    """Registrierte mobile Endgeräte."""
    rows = db_query_rt(
        "SELECT * FROM dbai_net.mobile_devices ORDER BY last_seen DESC"
    )
    return {"devices": rows}

@app.post("/api/mobile-bridge/devices/register")
async def register_mobile_device(request: Request, session: dict = Depends(get_current_session)):
    """Neues Mobilgerät registrieren (via User-Agent Erkennung)."""
    body = await request.json()
    ua = request.headers.get("User-Agent", "")

    # Device-Type aus User-Agent ableiten
    device_type = "other"
    os_name = "Unknown"
    if "iPhone" in ua:
        device_type, os_name = "iphone", "iOS"
    elif "iPad" in ua:
        device_type, os_name = "ipad", "iPadOS"
    elif "Android" in ua:
        if "Mobile" in ua:
            device_type, os_name = "android_phone", "Android"
        else:
            device_type, os_name = "android_tablet", "Android"

    try:
        result = db_query_rt("""
            INSERT INTO dbai_net.mobile_devices
                (device_name, device_type, os_name, browser, screen_width, screen_height,
                 has_camera, has_gps, has_microphone, last_ip, connection_type, user_id, is_trusted)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::INET, %s, %s::UUID, FALSE)
            RETURNING id
        """, (
            body.get("device_name", f"{os_name} Device"),
            device_type, os_name,
            body.get("browser", ua[:100]),
            body.get("screen_width"), body.get("screen_height"),
            body.get("has_camera", True), body.get("has_gps", True), body.get("has_microphone", True),
            request.client.host if request.client else None,
            body.get("connection_type", "local_wifi"),
            session.get("user", {}).get("id"),
        ))
        return {"ok": True, "device_id": result[0]["id"] if result else None}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/mobile-bridge/connections")
async def get_active_connections(session: dict = Depends(get_current_session)):
    """Aktive Verbindungen über alle 5 Dimensionen."""
    rows = db_query_rt("SELECT * FROM dbai_net.vw_active_connections")
    return {"connections": rows}

@app.get("/api/mobile-bridge/pwa-config")
async def get_pwa_config():
    """PWA-Konfiguration (kein Auth nötig — wird vom Browser beim Install geladen)."""
    rows = db_query_rt("SELECT config_key, config_value FROM dbai_net.pwa_config")
    return {r["config_key"]: r["config_value"] for r in rows}

@app.get("/api/mobile-bridge/hotspot")
async def get_hotspot_status(session: dict = Depends(get_current_session)):
    """Hotspot-Status und DHCP-Leases."""
    hotspot = db_query_rt("SELECT * FROM dbai_net.hotspot_config LIMIT 1")
    leases = db_query_rt("SELECT * FROM dbai_net.dhcp_leases WHERE is_active ORDER BY lease_start DESC")
    return {
        "hotspot": hotspot[0] if hotspot else None,
        "leases": leases,
    }

@app.patch("/api/mobile-bridge/hotspot")
async def update_hotspot(body: dict, session: dict = Depends(get_current_session)):
    """Hotspot-Konfiguration ändern (nur Admin)."""
    require_admin(session)
    allowed = {"ssid", "passphrase", "channel", "hidden_ssid", "max_clients", "auto_start"}
    updates, values = [], []
    for k, v in body.items():
        if k in allowed:
            updates.append(f"{k} = %s")
            values.append(v)
    if not updates:
        raise HTTPException(400, "Keine gültigen Felder")
    values.append(True)  # WHERE is immer der einzige Eintrag
    db_execute_rt(
        f"UPDATE dbai_net.hotspot_config SET {', '.join(updates)}, updated_at = NOW() WHERE id = (SELECT id FROM dbai_net.hotspot_config LIMIT 1)",
        values
    )
    return {"ok": True}

@app.post("/api/mobile-bridge/sensors")
async def receive_sensor_data(request: Request, session: dict = Depends(get_current_session)):
    """Sensor-Daten vom Handy empfangen (GPS, Foto, Audio, etc.)."""
    body = await request.json()
    sensor_type = body.get("sensor_type")
    device_id = body.get("device_id")

    if not sensor_type or not device_id:
        raise HTTPException(400, "sensor_type und device_id erforderlich")

    try:
        result = db_query_rt("""
            INSERT INTO dbai_net.sensor_data
                (device_id, sensor_type, latitude, longitude, altitude_m, accuracy_m,
                 payload_mime, payload_size_kb, payload_json, label, tags)
            VALUES (%s::UUID, %s, %s, %s, %s, %s, %s, %s, %s::JSONB, %s, %s)
            RETURNING id
        """, (
            device_id, sensor_type,
            body.get("latitude"), body.get("longitude"),
            body.get("altitude_m"), body.get("accuracy_m"),
            body.get("mime_type"), body.get("size_kb"),
            json.dumps(body.get("data", {})),
            body.get("label"), body.get("tags", []),
        ))
        return {"ok": True, "sensor_id": result[0]["id"] if result else None}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/mobile-bridge/sensors/pipeline")
async def get_sensor_pipeline(session: dict = Depends(get_current_session)):
    """Sensor-Pipeline Status: Welche Daten warten auf Analyse."""
    rows = db_query_rt("SELECT * FROM dbai_net.vw_sensor_pipeline")
    return {"pipeline": rows}

@app.get("/api/mobile-bridge/hardware-profiles")
async def get_hardware_profiles(session: dict = Depends(get_current_session)):
    """Hardware-Profile für Ghost-Pi / Compute-Stick."""
    rows = db_query_rt("SELECT * FROM dbai_net.hardware_profiles ORDER BY profile_name")
    return {"profiles": rows}

@app.get("/manifest.json")
async def serve_manifest():
    """PWA manifest.json aus der DB generieren."""
    rows = db_query_rt("SELECT config_value FROM dbai_net.pwa_config WHERE config_key = 'manifest'")
    if rows:
        return JSONResponse(content=rows[0]["config_value"], media_type="application/manifest+json")
    return JSONResponse(content={}, status_code=404)

@app.get("/api/cluster/nodes")
async def list_cluster_nodes(session: dict = Depends(get_current_session)):
    """Cluster-Node-Übersicht."""
    rows = db_query_rt("SELECT * FROM dbai_llm.v_cluster_overview")
    return {"nodes": rows}

@app.post("/api/cluster/nodes")
async def register_cluster_node(request: Request, session: dict = Depends(get_current_session)):
    """Neuen Node im Cluster registrieren."""
    require_admin(session)
    body = await request.json()
    ip = body.get("ip_address")
    if not ip:
        raise HTTPException(400, "ip_address erforderlich")
    rows = db_query_rt("""
        INSERT INTO dbai_llm.ghost_nodes
            (node_name, hostname, ip_address, port, api_endpoint, role,
             gpu_count, total_vram_mb, total_ram_mb, cpu_cores, os_info, dbai_version,
             capabilities, max_models, priority)
        VALUES (%s, %s, %s::INET, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, node_name, role, state
    """, (
        body.get("node_name", f"node-{ip}"),
        body.get("hostname", ip),
        ip,
        body.get("port", 3100),
        body.get("api_endpoint", f"http://{ip}:{body.get('port', 3100)}"),
        body.get("role", "worker"),
        body.get("gpu_count", 0),
        body.get("total_vram_mb", 0),
        body.get("total_ram_mb", 0),
        body.get("cpu_cores", 0),
        body.get("os_info"),
        body.get("dbai_version"),
        body.get("capabilities", []),
        body.get("max_models", 4),
        body.get("priority", 5),
    ))
    return {"ok": True, "node": rows[0] if rows else None}

@app.patch("/api/cluster/nodes/{node_id}")
async def update_cluster_node(node_id: str, request: Request, session: dict = Depends(get_current_session)):
    """Node-Status aktualisieren."""
    require_admin(session)
    body = await request.json()
    allowed = {"state", "role", "max_models", "priority", "capabilities"}
    updates, values = [], []
    for k, v in body.items():
        if k in allowed:
            updates.append(f"{k} = %s")
            values.append(v)
    if not updates:
        raise HTTPException(400, "Keine gültigen Felder")
    values.append(node_id)
    db_execute_rt(
        f"UPDATE dbai_llm.ghost_nodes SET {', '.join(updates)}, updated_at = NOW() WHERE id = %s::UUID",
        values
    )
    return {"ok": True}

@app.post("/api/cluster/nodes/{node_id}/heartbeat")
async def node_heartbeat(node_id: str, request: Request):
    """Heartbeat von einem Worker-Node empfangen (kein Auth — Node-intern)."""
    body = await request.json()
    db_execute_rt("""
        INSERT INTO dbai_llm.node_heartbeats
            (node_id, cpu_usage, ram_usage_mb, ram_total_mb, gpu_usage, disk_usage_gb,
             network_rx_mbps, network_tx_mbps, active_requests, loaded_models, latency_ms, is_healthy)
        VALUES (%s::UUID, %s, %s, %s, %s::JSONB, %s, %s, %s, %s, %s, %s, %s)
    """, (
        node_id,
        body.get("cpu_usage"),
        body.get("ram_usage_mb"),
        body.get("ram_total_mb"),
        json.dumps(body.get("gpu_usage", [])),
        body.get("disk_usage_gb"),
        body.get("network_rx_mbps"),
        body.get("network_tx_mbps"),
        body.get("active_requests", 0),
        body.get("loaded_models", []),
        body.get("latency_ms"),
        body.get("is_healthy", True),
    ))
    # Update last_seen auf dem Node
    db_execute_rt("UPDATE dbai_llm.ghost_nodes SET last_seen_at = NOW(), loaded_models = %s WHERE id = %s::UUID",
                  (body.get("loaded_models", 0) if isinstance(body.get("loaded_models"), int) else len(body.get("loaded_models", [])), node_id))
    return {"ok": True}

@app.get("/api/cluster/tasks")
async def list_distributed_tasks(session: dict = Depends(get_current_session)):
    """Distributed Tasks auflisten."""
    rows = db_query_rt(
        "SELECT * FROM dbai_llm.distributed_tasks ORDER BY created_at DESC LIMIT 100"
    )
    return {"tasks": rows}

@app.get("/api/cluster/stats")
async def get_cluster_stats(session: dict = Depends(get_current_session)):
    """Cluster-Statistiken."""
    stats = db_query_rt("SELECT * FROM dbai_llm.v_task_routing_stats")
    nodes = db_query_rt("SELECT state, COUNT(*) as count FROM dbai_llm.ghost_nodes GROUP BY state")
    replicas = db_query_rt("SELECT state, COUNT(*) as count FROM dbai_llm.model_replicas GROUP BY state")
    return {"task_stats": stats, "node_states": nodes, "replica_states": replicas}

@app.get("/api/cluster/replicas")
async def list_model_replicas(session: dict = Depends(get_current_session)):
    """Modell-Repliken über alle Nodes."""
    rows = db_query_rt("""
        SELECT mr.*, gn.node_name, gm.name AS model_name
        FROM dbai_llm.model_replicas mr
        JOIN dbai_llm.ghost_nodes gn ON gn.id = mr.node_id
        JOIN dbai_llm.ghost_models gm ON gm.id = mr.model_id
        ORDER BY gn.node_name, gm.name
    """)
    return {"replicas": rows}

@app.get("/api/marketplace")
async def list_marketplace_models(session: dict = Depends(get_current_session)):
    """Marketplace-Modelle browsen."""
    rows = db_query_rt("SELECT * FROM dbai_llm.v_marketplace")
    return {"models": rows}

@app.get("/api/marketplace/search")
async def search_marketplace(q: str = "", session: dict = Depends(get_current_session)):
    """Marketplace durchsuchen (Fulltext)."""
    if not q:
        return await list_marketplace_models(session)
    rows = db_query_rt("""
        SELECT * FROM dbai_llm.marketplace_catalog
        WHERE to_tsvector('english', coalesce(model_name,'') || ' ' || coalesce(description,'') || ' ' || coalesce(author,''))
              @@ plainto_tsquery('english', %s)
           OR model_name ILIKE %s
           OR author ILIKE %s
           OR model_type ILIKE %s
        ORDER BY hf_downloads DESC
    """, (q, f"%{q}%", f"%{q}%", f"%{q}%"))
    return {"models": rows}

@app.get("/api/marketplace/{catalog_id}")
async def get_marketplace_model(catalog_id: str, session: dict = Depends(get_current_session)):
    """Details eines Marketplace-Modells."""
    models = db_query_rt("SELECT * FROM dbai_llm.marketplace_catalog WHERE id = %s::UUID", (catalog_id,))
    if not models:
        raise HTTPException(404, "Modell nicht gefunden")
    reviews = db_query_rt(
        "SELECT * FROM dbai_llm.model_reviews WHERE catalog_id = %s::UUID ORDER BY created_at DESC",
        (catalog_id,)
    )
    downloads = db_query_rt(
        "SELECT * FROM dbai_llm.model_downloads WHERE catalog_id = %s::UUID ORDER BY created_at DESC LIMIT 5",
        (catalog_id,)
    )
    return {"model": models[0], "reviews": reviews, "downloads": downloads}

@app.post("/api/marketplace/{catalog_id}/download")
async def start_marketplace_download(catalog_id: str, request: Request, session: dict = Depends(get_current_session)):
    """Download eines Marketplace-Modells starten."""
    body = await request.json() if await request.body() else {}
    model = db_query_rt("SELECT * FROM dbai_llm.marketplace_catalog WHERE id = %s::UUID", (catalog_id,))
    if not model:
        raise HTTPException(404, "Modell nicht gefunden")
    m = model[0]
    rows = db_query_rt("""
        INSERT INTO dbai_llm.model_downloads
            (catalog_id, hf_repo_id, hf_filename, target_path, auto_load, auto_config, requested_by)
        VALUES (%s::UUID, %s, %s, %s, %s, %s::JSONB, %s)
        RETURNING id, state, hf_repo_id, hf_filename
    """, (
        catalog_id,
        m["hf_repo_id"],
        m.get("hf_filename", ""),
        body.get("target_path", f"/models/{m['model_name']}.gguf"),
        body.get("auto_load", False),
        json.dumps(body.get("auto_config", {})),
        session.get("user", {}).get("username", "user"),
    ))
    return {"ok": True, "download": rows[0] if rows else None}

@app.get("/api/marketplace/downloads/queue")
async def get_download_queue(session: dict = Depends(get_current_session)):
    """Aktive Download-Queue."""
    rows = db_query_rt("SELECT * FROM dbai_llm.v_download_queue")
    return {"queue": rows}

@app.patch("/api/marketplace/downloads/{download_id}")
async def update_download_state(download_id: str, request: Request, session: dict = Depends(get_current_session)):
    """Download-Status aktualisieren (Progress, State)."""
    body = await request.json()
    allowed = {"state", "progress_percent", "downloaded_bytes", "speed_mbps", "eta_seconds", "error_message"}
    updates, values = [], []
    for k, v in body.items():
        if k in allowed:
            updates.append(f"{k} = %s")
            values.append(v)
    if not updates:
        raise HTTPException(400, "Keine gültigen Felder")
    if body.get("state") == "downloading" and "started_at" not in body:
        updates.append("started_at = NOW()")
    if body.get("state") == "completed":
        updates.append("completed_at = NOW()")
    values.append(download_id)
    db_execute_rt(
        f"UPDATE dbai_llm.model_downloads SET {', '.join(updates)} WHERE id = %s::UUID",
        values
    )
    return {"ok": True}

@app.post("/api/marketplace/{catalog_id}/review")
async def create_model_review(catalog_id: str, request: Request, session: dict = Depends(get_current_session)):
    """Bewertung für ein Marketplace-Modell abgeben."""
    body = await request.json()
    rating = body.get("rating")
    if rating is None or not (0 <= float(rating) <= 5):
        raise HTTPException(400, "rating (0-5) erforderlich")
    rows = db_query_rt("""
        INSERT INTO dbai_llm.model_reviews
            (catalog_id, model_id, reviewer, rating, title, review_text,
             benchmark_results, use_case, hardware_info)
        VALUES (%s::UUID, %s, %s, %s, %s, %s, %s::JSONB, %s, %s)
        RETURNING id, rating
    """, (
        catalog_id,
        body.get("model_id"),
        session.get("user", {}).get("username", "user"),
        rating,
        body.get("title"),
        body.get("review_text"),
        json.dumps(body.get("benchmark_results", {})),
        body.get("use_case"),
        body.get("hardware_info"),
    ))
    return {"ok": True, "review": rows[0] if rows else None}
