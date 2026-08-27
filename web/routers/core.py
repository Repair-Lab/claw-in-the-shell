"""
web/routers/core.py — Desktop, Settings, Auth, Health, Boot, Config, System
===========================================================================
39 Routen, extrahiert aus web/routers.py (Phase 2b).
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

@app.post("/api/auth/login")
async def login(req: LoginRequest, request: Request):
    """Login gegen die Datenbank. Gibt Session-Token zurück."""
    ip = request.client.host if request.client else None
    ua = request.headers.get("User-Agent", "")

    result = await adb_call_json_rt(
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
        secure=_COOKIE_SECURE,
        samesite="strict",
        max_age=86400,
    )
    # CSRF-Token im separaten Cookie (JS-lesbar, nicht httponly)
    import secrets as _secrets_mod
    csrf_token = _secrets_mod.token_hex(32)
    response.set_cookie(
        key="dbai_csrf",
        value=csrf_token,
        httponly=False,
        secure=_COOKIE_SECURE,
        samesite="strict",
        max_age=86400,
    )
    logger.debug("[AUTH] Login erfolgreich: user=%s, cookie_secure=%s, env=%s",
                 req.username, _COOKIE_SECURE, os.getenv('DBAI_ENV', 'production'))
    return response

@app.post("/api/auth/logout")
async def logout(session: dict = Depends(get_current_session)):
    """Logout: Session deaktivieren + Cookies löschen."""
    await adb_execute_rt(
        "UPDATE dbai_ui.sessions SET is_active = FALSE WHERE id = %s::UUID",
        (session["session_id"],)
    )
    response = JSONResponse(content={"success": True})
    response.delete_cookie("dbai_token")
    response.delete_cookie("dbai_csrf")
    return response

@app.get("/api/auth/me")
async def get_me(session: dict = Depends(get_current_session)):
    """Gibt den aktuellen User zurück."""
    return session["user"]

@app.get("/api/boot/sequence")
async def get_boot_sequence():
    """Boot-Sequenz für die Browser-Animation. Kein Auth nötig."""
    rows = await adb_query_rt("SELECT * FROM dbai_ui.vw_boot_sequence ORDER BY step")
    return rows

@app.get("/api/desktop")
async def get_desktop(request: Request, session: dict = Depends(get_current_session)):
    """Kompletter Desktop-State — Tab-isoliert wenn X-Tab-Id Header vorhanden."""
    tab_id = request.headers.get("X-Tab-Id", "")
    if tab_id:
        result = await adb_call_json_rt(
            "SELECT dbai_ui.get_tab_desktop_state(%s::UUID, %s)",
            (session["session_id"], tab_id)
        )
    else:
        result = await adb_call_json_rt(
            "SELECT dbai_ui.get_desktop_state(%s::UUID)",
            (session["session_id"],)
        )
    return result or {}

@app.get("/api/apps")
async def get_apps(session: dict = Depends(get_current_session)):
    """Liste aller verfügbaren Apps."""
    rows = await adb_query_rt("SELECT * FROM dbai_ui.apps ORDER BY sort_order")
    return rows

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

    # Live-Daten via psutil — blocking call in Thread auslagern
    cpu_percent = await asyncio.to_thread(psutil.cpu_percent, interval=0.3, percpu=True)
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

    # In DB persistieren (Batch-INSERT für CPU-Cores)
    try:
        if cpu_percent:
            cpu_values = ", ".join(
                f"({i}, {pct}, {cpu_freq.current if cpu_freq else 'NULL'}, {max_temp if max_temp else 'NULL'})"
                for i, pct in enumerate(cpu_percent)
            )
            db_execute_rt(f"""
                INSERT INTO dbai_system.cpu (core_id, usage_percent, frequency_mhz, temperature_c)
                VALUES {cpu_values}
            """)
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
    """Erweiterter Health-Check (ohne Auth) für Docker/Systemd Healthchecks.
    Prüft: DB, Disk, Memory. Gibt 503 bei kritischem Problem."""
    checks = {"status": "ok"}

    # 1. Datenbank
    try:
        await asyncio.to_thread(db_query_rt, "SELECT 1")
        checks["db"] = "connected"
    except Exception:
        checks["db"] = "disconnected"
        checks["status"] = "degraded"

    # 2. Disk-Space (/ muss >5% frei haben)
    try:
        st = os.statvfs("/")
        free_pct = (st.f_bavail / st.f_blocks) * 100 if st.f_blocks else 100
        checks["disk_free_pct"] = round(free_pct, 1)
        if free_pct < 5:
            checks["status"] = "critical"
            checks["disk"] = "critical"
        elif free_pct < 15:
            checks["disk"] = "warning"
        else:
            checks["disk"] = "ok"
    except Exception:
        checks["disk"] = "unknown"

    # 3. Memory
    try:
        with open("/proc/meminfo") as f:
            mem = {}
            for line in f:
                parts = line.split()
                if parts[0] in ("MemTotal:", "MemAvailable:"):
                    mem[parts[0]] = int(parts[1])
            total = mem.get("MemTotal:", 0)
            avail = mem.get("MemAvailable:", 0)
            if total > 0:
                used_pct = round((1 - avail / total) * 100, 1)
                checks["memory_used_pct"] = used_pct
                checks["memory"] = "critical" if used_pct > 95 else ("warning" if used_pct > 85 else "ok")
                if used_pct > 95:
                    checks["status"] = "critical"
            else:
                checks["memory"] = "unknown"
    except Exception:
        checks["memory"] = "unknown"

    # 4. LLM-Server (schneller Connect-Check)
    try:
        llm_url = os.environ.get("LLM_SERVER_URL", "http://127.0.0.1:8080")
        import urllib.request
        req = urllib.request.Request(f"{llm_url}/health", method="GET")
        with urllib.request.urlopen(req, timeout=1) as resp:
            checks["llm"] = "ok" if resp.status == 200 else "degraded"
    except Exception:
        checks["llm"] = "offline"

    status_code = 503 if checks["status"] == "critical" else (
        200 if checks["db"] == "connected" else 503
    )
    return JSONResponse(content=checks, status_code=status_code)

@app.get("/api/health/auth-config")
async def health_auth_config(request: Request):
    """Diagnose-Endpoint: Zeigt ob Cookie/Auth-Konfiguration für den aktuellen Client stimmt.
    Kein Auth nötig — hilft beim Debuggen von Login-Problemen."""
    protocol = request.headers.get("x-forwarded-proto", request.url.scheme)
    is_https = protocol == "https"
    problems = []

    if _COOKIE_SECURE and not is_https:
        problems.append({
            "severity": "critical",
            "issue": "Cookie Secure=True aber Client nutzt HTTP",
            "fix": "Entweder HTTPS verwenden oder DBAI_ENV=development setzen"
        })

    csrf_cookie = request.cookies.get("dbai_csrf", "")
    token_cookie = request.cookies.get("dbai_token", "")

    if not csrf_cookie and not token_cookie:
        # Könnte OK sein (noch nicht eingeloggt) oder Problem
        problems.append({
            "severity": "info",
            "issue": "Keine Auth-Cookies vorhanden (noch nicht eingeloggt oder Cookies blockiert)",
            "fix": "Nach Login prüfen ob Cookies gesetzt werden"
        })

    return {
        "cookie_secure_flag": _COOKIE_SECURE,
        "dbai_env": os.getenv("DBAI_ENV", "production"),
        "is_development": _IS_DEVELOPMENT,
        "client_protocol": protocol,
        "client_is_https": is_https,
        "csrf_cookie_present": bool(csrf_cookie),
        "token_cookie_present": bool(token_cookie),
        "problems": problems,
        "verdict": "OK" if not [p for p in problems if p["severity"] == "critical"] else "BROKEN"
    }

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
            SELECT name, is_loaded, required_vram_mb
            FROM dbai_llm.ghost_models WHERE state != 'removed' LIMIT 5
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
                params.append(json.dumps(val))
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
            logger.warning("Profil: Theme-Update fehlgeschlagen", exc_info=True)

    if "password" in body and body["password"]:
        # Passwort-Hash via pgcrypto bcrypt
        updates.append("password_hash = crypt(%s, gen_salt('bf'))")
        params.append(body["password"])

    if "github_token" in body and body["github_token"]:
        enc = encrypt_secret(body["github_token"])
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
    require_admin(session)
    body = _validate_body(await request.json(), required=["key"], max_str_len=5000)
    key = body["key"]
    value = body.get("value")
    category = body.get("category", "general")
    description = body.get("description")

    db_execute_rt("""
        INSERT INTO dbai_core.config (key, value, category, description)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (key) DO UPDATE
        SET value = EXCLUDED.value, category = EXCLUDED.category,
            description = COALESCE(EXCLUDED.description, dbai_core.config.description),
            updated_at = NOW()
    """, (key, json.dumps(value), category, description))
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
    require_admin(session)
    import subprocess
    data = _validate_body(await request.json(), max_str_len=500)
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
    require_admin(session)
    import subprocess
    data = _validate_body(await request.json(), required=["action"], max_str_len=200)
    action = data["action"]

    # Whitelist: Nur erlaubte Aktionen
    _ALLOWED_ACTIONS = {
        "bluetooth": ["scan"],
        "printers": ["scan"],
        "updates": ["check"],
    }
    if category not in _ALLOWED_ACTIONS or action not in _ALLOWED_ACTIONS.get(category, []):
        raise HTTPException(status_code=400, detail=f"Unbekannte Aktion: {category}/{action}")

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

@app.patch("/api/desktop/theme/{theme_name}")
async def set_theme(theme_name: str, session: dict = Depends(get_current_session)):
    """Theme wechseln."""
    db_execute_rt("""
        UPDATE dbai_ui.desktop_config
        SET theme_id = (SELECT id FROM dbai_ui.themes WHERE name = %s)
        WHERE user_id = %s::UUID
    """, (theme_name, session["user"]["id"]))
    return {"ok": True, "theme": theme_name}

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
    """Desktop-Knoten löschen — bei Store-Apps auch Katalog, Settings und Fenster aufräumen."""
    # Node-Daten holen bevor wir löschen
    node_rows = db_query_rt(
        "SELECT node_key, label FROM dbai_ui.desktop_nodes WHERE id = %s", (node_id,)
    )
    node_key = node_rows[0]["node_key"] if node_rows else None
    node_label = node_rows[0]["label"] if node_rows else None

    # Node löschen
    db_execute_rt(
        "DELETE FROM dbai_ui.desktop_nodes WHERE id = %s", (node_id,)
    )

    cleanup = ["desktop_node"]

    # Wenn Store-App (node_key = "store:source:package") → vollständiges Cleanup
    if node_key and node_key.startswith("store:"):
        parts = node_key.split(":", 2)  # ["store", source_type, package_name]
        if len(parts) == 3:
            src, pkg = parts[1], parts[2]

            # Katalog zurücksetzen
            db_execute_rt("""
                UPDATE dbai_core.software_catalog
                SET install_state = 'available', installed_at = NULL, updated_at = NOW()
                WHERE package_name = %s AND source_type = %s
            """, (pkg, src))
            cleanup.append("catalog")

            # App-Settings entfernen
            db_execute_rt(
                "DELETE FROM dbai_ui.app_user_settings WHERE app_id = %s", (node_key,)
            )
            db_execute_rt(
                "DELETE FROM dbai_ui.app_user_settings WHERE app_id = %s", (pkg,)
            )
            cleanup.append("settings")

            # Offene Fenster schließen
            try:
                app_row = db_query_rt(
                    "SELECT id FROM dbai_ui.apps WHERE app_id = %s", (node_key,)
                )
                if app_row:
                    db_execute_rt(
                        "DELETE FROM dbai_ui.windows WHERE app_id = %s", (app_row[0]["id"],)
                    )
                    cleanup.append("windows")
            except Exception:
                pass

            # Event loggen
            try:
                db_execute_rt("""
                    INSERT INTO dbai_event.events (event_type, source, payload)
                    VALUES ('app_removed_from_desktop', 'desktop_ui', %s::JSONB)
                """, (json.dumps({"node_key": node_key, "package": pkg, "source_type": src, "label": node_label, "cleanup": cleanup}),))
            except Exception:
                pass

    return {"deleted": True, "node_key": node_key, "cleanup": cleanup}

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
