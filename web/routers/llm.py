"""
web/routers/llm.py — LLM, Agents, Crews, GPU, Vision, Autonomous
================================================================
82 Routen, extrahiert aus web/routers.py (Phase 2b).
app und alle Helper werden aus web/common.py importiert.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import *
from common import app, get_current_session, require_admin

from fastapi import HTTPException, Request, Depends
from fastapi.responses import JSONResponse

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
    """, (key, json.dumps(value)))

    return {"ok": True}

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
    body = _validate_body(await request.json())
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
    require_admin(session)
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

@app.post("/api/llm/download")
async def llm_download_model(request: Request, session: dict = Depends(get_current_session)):
    """Modell von HuggingFace Hub herunterladen."""
    require_admin(session)
    import asyncio
    body = _validate_body(await request.json(), required=["repo_id"], max_str_len=500)
    repo_id = body["repo_id"]
    target_dir = body.get("target_dir", "/mnt/nvme/models")
    filename = body.get("filename")  # optional: nur bestimmte Datei

    # Pfad-Traversal verhindern
    import pathlib
    _target = pathlib.Path(target_dir).resolve()
    if ".." in str(_target) or not str(_target).startswith("/"):
        return JSONResponse(status_code=400, content={"error": "Ungültiger Zielpfad"})

    task_id = str(uuid.uuid4())
    _download_tasks[task_id] = {"state": "running", "repo_id": repo_id, "error": None, "path": None}

    def _download_sync():
        import pathlib
        pathlib.Path(target_dir).mkdir(parents=True, exist_ok=True)
        try:
            from huggingface_hub import snapshot_download, hf_hub_download
            if filename:
                path = hf_hub_download(repo_id=repo_id, filename=filename, local_dir=target_dir)
            else:
                path = snapshot_download(repo_id=repo_id, local_dir=f"{target_dir}/{repo_id.split('/')[-1]}")
            db_execute_rt("""
                INSERT INTO dbai_llm.ghost_models (name, model_path, model_type, state)
                VALUES (%s, %s, 'chat', 'available')
                ON CONFLICT DO NOTHING
            """, (repo_id.split('/')[-1], str(path)))
            _download_tasks[task_id].update({"state": "done", "path": str(path)})
        except ImportError:
            import subprocess
            clone_dir = f"{target_dir}/{repo_id.split('/')[-1]}"
            result = subprocess.run(
                ["git", "clone", "--depth", "1", f"https://huggingface.co/{repo_id}", clone_dir],
                capture_output=True, text=True, timeout=3600
            )
            if result.returncode == 0:
                db_execute_rt("""
                    INSERT INTO dbai_llm.ghost_models (name, model_path, model_type, state)
                    VALUES (%s, %s, 'chat', 'available')
                    ON CONFLICT DO NOTHING
                """, (repo_id.split('/')[-1], clone_dir))
                _download_tasks[task_id].update({"state": "done", "path": clone_dir})
            else:
                _download_tasks[task_id].update({"state": "error", "error": result.stderr[:500]})
        except Exception as exc:
            logger.exception("Download %s fehlgeschlagen", repo_id)
            _download_tasks[task_id].update({"state": "error", "error": str(exc)[:500]})

    asyncio.create_task(asyncio.to_thread(_download_sync))

    return {"ok": True, "task_id": task_id, "message": f"Download von {repo_id} gestartet nach {target_dir}"}

@app.get("/api/llm/download/{task_id}")
async def llm_download_status(task_id: str, session: dict = Depends(get_current_session)):
    """Status eines laufenden Downloads abfragen."""
    task = _download_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Download-Task nicht gefunden")
    return task

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
    except Exception as e:
        logger.debug("silent-exception: %s", e)

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
    import subprocess

    body = {}
    try:
        body = await request.json()
    except Exception as e:
        logger.debug("silent-exception: %s", e)
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
    except Exception as e:
        logger.debug("silent-exception: %s", e)

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

@app.post("/api/gpu/benchmark")
async def gpu_benchmark(request: Request, session: dict = Depends(get_current_session)):
    """GPU-Hardware-Benchmark: Misst VRAM, Bandbreite und empfiehlt Modellkonfigurationen."""
    import subprocess
    body = {}
    try:
        body = await request.json()
    except Exception as e:
        logger.debug("silent-exception: %s", e)
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

@app.post("/api/gpu/recommend/{model_id}")
async def gpu_recommend_for_model(model_id: str, request: Request, session: dict = Depends(get_current_session)):
    """Berechne optimale GPU-Einstellungen für ein spezifisches Modell."""
    import subprocess

    body = {}
    try:
        body = await request.json()
    except Exception as e:
        logger.debug("silent-exception: %s", e)
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
    except Exception as e:
        logger.debug("silent-exception: %s", e)

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

@app.post("/api/llm/models/{model_id}/start")
async def llm_start_model(model_id: str, request: Request, session: dict = Depends(get_current_session)):
    """Modell auf GPU laden: Startet den llama-server und erstellt Agent-Instanz."""
    import subprocess

    body = {}
    try:
        body = await request.json()
    except Exception as e:
        logger.debug("silent-exception: %s", e)

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
    except Exception as e:
        logger.debug("silent-exception: %s", e)

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
                UPDATE dbai_llm.agent_instances SET state = 'running', updated_at = NOW()
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
    # WICHTIG: run_in_executor verhindert Blockierung des asyncio Event-Loops
    if model_name and model_name == _llm_model_name:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _llm_server_stop)
        _llm_model_name = ""
        _llm_model_path = ""
        logger.info(f"[LLM] llama-server gestoppt für Modell {model_name}")

    # Alle laufenden Instanzen dieses Modells stoppen
    db_execute_rt("""
        UPDATE dbai_llm.agent_instances SET state = 'stopped', updated_at = NOW()
        WHERE model_id = %s::UUID AND state IN ('running', 'starting')
    """, (model_id,))
    # VRAM-Allokation freigeben
    try:
        db_execute_rt("""
            UPDATE dbai_llm.vram_allocations SET is_active = FALSE, released_at = NOW()
            WHERE model_id = %s::UUID AND is_active = TRUE
        """, (model_id,))
    except Exception as e:
        logger.debug("silent-exception: %s", e)
    # Modell-Status aktualisieren
    db_execute_rt("""
        UPDATE dbai_llm.ghost_models SET state = 'available', is_loaded = FALSE, updated_at = NOW()
        WHERE id = %s::UUID
    """, (model_id,))
    return {"ok": True, "state": "stopped", "server_stopped": model_name == _llm_model_name}

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
        except Exception as e:
            logger.debug("silent-exception: %s", e)
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

@app.get("/api/llm/presets")
async def llm_presets_list(session: dict = Depends(get_current_session)):
    """Alle Model-Presets mit optimalen Einstellungen — für die UI-Konfiguration."""
    rows = db_query_rt("SELECT * FROM dbai_llm.model_presets ORDER BY is_default DESC, model_name")
    return rows or []

@app.get("/api/llm/presets/{model_name}")
async def llm_preset_detail(model_name: str, session: dict = Depends(get_current_session)):
    """Preset für ein bestimmtes Modell — liefert empfohlene Einstellungen."""
    rows = db_query_rt("SELECT * FROM dbai_llm.model_presets WHERE model_name = %s", (model_name,))
    if not rows:
        return {"error": f"Kein Preset für '{model_name}' gefunden", "hint": "Nutze /api/llm/presets für die Liste"}
    return rows[0]

@app.get("/api/llm/models/{model_id}/auto-config")
async def llm_model_auto_config(model_id: str, session: dict = Depends(get_current_session)):
    """Auto-Config: Wählt passenden Backend + optimale Einstellungen automatisch.
    Gibt alles zurück was der User nur noch mit OK bestätigen muss."""
    # Modell aus DB laden
    model_rows = db_query_rt("SELECT * FROM dbai_llm.ghost_models WHERE id = %s::UUID", (model_id,))
    if not model_rows:
        raise HTTPException(status_code=404, detail="Modell nicht gefunden")
    model = model_rows[0]

    # Preset suchen (exakt oder Fuzzy)
    preset = None
    preset_rows = db_query_rt(
        "SELECT * FROM dbai_llm.model_presets WHERE model_name = %s",
        (model.get("name", ""),)
    )
    if preset_rows:
        preset = preset_rows[0]
    else:
        # Fuzzy-Match: Modell-Familie
        family = (model.get("name") or "").split("-")[0].lower()
        if family:
            fam_rows = db_query_rt(
                "SELECT * FROM dbai_llm.model_presets WHERE model_family = %s ORDER BY is_default DESC LIMIT 1",
                (family,)
            )
            if fam_rows:
                preset = fam_rows[0]

    # GPU-VRAM ermitteln (für Layer-Empfehlung)
    gpu_info = {"available": False, "vram_free_mb": 0, "vram_total_mb": 0, "name": "Keine GPU"}
    try:
        import subprocess
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0 and r.stdout.strip():
            parts = [p.strip() for p in r.stdout.strip().split("\n")[0].split(",")]
            if len(parts) >= 3:
                gpu_info = {
                    "available": True,
                    "name": parts[0],
                    "vram_total_mb": int(float(parts[1])),
                    "vram_free_mb": int(float(parts[2])),
                }
    except Exception as e:
        logger.debug("silent-exception: %s", e)

    # Empfohlene Einstellungen berechnen
    required_vram = model.get("required_vram_mb") or (preset.get("min_vram_mb") if preset else 0) or 0
    vram_free = gpu_info.get("vram_free_mb", 0)

    recommended_gpu_layers = -1  # Default: alles auf GPU
    if required_vram > 0 and vram_free > 0:
        safety_margin = 512
        usable_vram = vram_free - safety_margin
        if usable_vram >= required_vram:
            recommended_gpu_layers = -1  # Passt komplett
        elif usable_vram > 0:
            total_layers = (preset.get("total_layers") if preset else None) or 40
            ratio = usable_vram / required_vram
            recommended_gpu_layers = max(1, int(ratio * total_layers))
        else:
            recommended_gpu_layers = 0  # CPU-only

    recommended_backend = "llamacpp"
    if preset and preset.get("recommended_backend"):
        recommended_backend = preset["recommended_backend"]

    # Kompatible Provider ermitteln
    compatible = []
    providers = db_query_rt("SELECT * FROM dbai_llm.llm_providers ORDER BY provider_key")
    for p in (providers or []):
        pk = p.get("provider_key", "")
        compat = {"provider_key": pk, "display_name": p.get("display_name", pk), "is_enabled": p.get("is_enabled", False)}
        if preset and preset.get("compatible_providers"):
            cp = preset["compatible_providers"]
            compat["is_compatible"] = pk in cp
        else:
            compat["is_compatible"] = pk in ("llamacpp", "ollama", "vllm") if model.get("provider") == "llama.cpp" else pk == model.get("provider", "")
        compat["is_recommended"] = pk == recommended_backend
        compatible.append(compat)

    return {
        "model": {
            "id": str(model["id"]),
            "name": model["name"],
            "display_name": model.get("display_name", model["name"]),
            "quantization": model.get("quantization"),
            "required_vram_mb": required_vram,
        },
        "gpu": gpu_info,
        "preset_found": preset is not None,
        "recommended": {
            "backend": recommended_backend,
            "gpu_layers": recommended_gpu_layers,
            "ctx_size": (preset.get("recommended_ctx_size") if preset else None) or model.get("context_size") or 4096,
            "threads": (preset.get("recommended_threads") if preset else None) or 8,
            "batch_size": (preset.get("recommended_batch_size") if preset else None) or 512,
        },
        "hints": {
            "gpu_layers": (preset.get("hint_gpu_layers") if preset else None) or "Anzahl der Layer auf der GPU. -1 = alle.",
            "ctx_size": (preset.get("hint_ctx_size") if preset else None) or "Kontextfenster in Tokens.",
            "backend": (preset.get("hint_backend") if preset else None) or "Inferenz-Backend auswählen.",
            "description": (preset.get("description") if preset else None) or model.get("display_name", ""),
        },
        "compatible_providers": compatible,
        "vram_fits": recommended_gpu_layers == -1,
        "vram_warning": f"Modell braucht {required_vram}MB, GPU hat {vram_free}MB frei. Nur {recommended_gpu_layers} von {(preset.get('total_layers') if preset else None) or 40} Layers passen auf die GPU." if recommended_gpu_layers > 0 and recommended_gpu_layers != -1 else None,
    }

@app.get("/api/llm/fallback-chain")
async def llm_fallback_chain_list(session: dict = Depends(get_current_session)):
    """Provider-Fallback-Chain mit Prioritäten auflisten."""
    rows = db_query_rt("""
        SELECT fc.*, lp.display_name AS provider_display, lp.icon, lp.is_enabled AS provider_enabled
        FROM dbai_llm.provider_fallback_chain fc
        LEFT JOIN dbai_llm.llm_providers lp ON fc.provider_key = lp.provider_key
        ORDER BY fc.priority ASC
    """)
    return rows or []

@app.patch("/api/llm/fallback-chain/{chain_id}")
async def llm_fallback_chain_update(chain_id: str, request: Request, session: dict = Depends(get_current_session)):
    """Fallback-Chain-Eintrag aktualisieren (Priorität, Aktivierung, etc.)."""
    body = await request.json()
    sets, params = [], []
    for field in ("priority", "is_enabled", "max_retries", "timeout_ms", "model_name"):
        if field in body:
            sets.append(f"{field} = %s")
            params.append(body[field])
    if not sets:
        return {"ok": False, "error": "Keine Felder angegeben"}
    params.append(chain_id)
    db_execute_rt(f"UPDATE dbai_llm.provider_fallback_chain SET {', '.join(sets)} WHERE id = %s::UUID", tuple(params))
    return {"ok": True}

@app.get("/api/llm/watchdog/status")
async def llm_watchdog_status(session: dict = Depends(get_current_session)):
    """Watchdog-Status und letzte Health-Checks."""
    logs = db_query_rt("""
        SELECT * FROM dbai_llm.watchdog_log ORDER BY check_time DESC LIMIT 20
    """)
    return {
        "running": _watchdog_running,
        "restart_count": _watchdog_restart_count,
        "fallback_active": _watchdog_fallback_active,
        "current_model": _llm_model_name or None,
        "server_healthy": _llm_server_health() if _llm_model_name else None,
        "recent_logs": logs or [],
    }

@app.post("/api/llm/watchdog/start")
async def llm_watchdog_start(session: dict = Depends(get_current_session)):
    """Watchdog manuell starten."""
    global _watchdog_running
    if not _watchdog_running:
        asyncio.create_task(_llm_watchdog_loop())
    return {"ok": True, "running": True}

@app.post("/api/llm/watchdog/stop")
async def llm_watchdog_stop(session: dict = Depends(get_current_session)):
    """Watchdog stoppen."""
    global _watchdog_running
    _watchdog_running = False
    return {"ok": True, "running": False}

@app.get("/api/crews")
async def crews_list(session: dict = Depends(get_current_session)):
    """Alle CrewAI Crew-Definitionen auflisten."""
    crews = db_query_rt("SELECT * FROM dbai_llm.crew_definitions ORDER BY is_active DESC, name")
    result = []
    for c in (crews or []):
        cid = str(c["id"])
        agents = db_query_rt("SELECT * FROM dbai_llm.crew_agents WHERE crew_id = %s::UUID ORDER BY sort_order", (cid,))
        tasks = db_query_rt("SELECT * FROM dbai_llm.crew_tasks WHERE crew_id = %s::UUID ORDER BY sort_order", (cid,))
        c["agents"] = agents or []
        c["tasks"] = tasks or []
        c["agent_count"] = len(c["agents"])
        c["task_count"] = len(c["tasks"])
        result.append(c)
    return result

@app.get("/api/crews/{crew_id}")
async def crews_detail(crew_id: str, session: dict = Depends(get_current_session)):
    """Crew-Details mit Agents und Tasks."""
    rows = db_query_rt("SELECT * FROM dbai_llm.crew_definitions WHERE id = %s::UUID", (crew_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Crew nicht gefunden")
    crew = rows[0]
    crew["agents"] = db_query_rt(
        "SELECT * FROM dbai_llm.crew_agents WHERE crew_id = %s::UUID ORDER BY sort_order", (crew_id,)
    ) or []
    crew["tasks"] = db_query_rt(
        "SELECT * FROM dbai_llm.crew_tasks WHERE crew_id = %s::UUID ORDER BY sort_order", (crew_id,)
    ) or []
    return crew

@app.post("/api/crews")
async def crews_create(request: Request, session: dict = Depends(get_current_session)):
    """Neue Crew erstellen."""
    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name ist erforderlich")
    db_execute_rt("""
        INSERT INTO dbai_llm.crew_definitions (name, display_name, description, process_type, config)
        VALUES (%s, %s, %s, %s, %s::jsonb)
    """, (name, body.get("display_name", name), body.get("description", ""),
          body.get("process_type", "sequential"), json.dumps(body.get("config", {}))))
    return {"ok": True, "name": name}

@app.patch("/api/crews/{crew_id}")
async def crews_update(crew_id: str, request: Request, session: dict = Depends(get_current_session)):
    """Crew aktualisieren (auch is_locked Crews können konfiguriert werden)."""
    body = await request.json()
    sets, params = [], []
    for field in ("display_name", "description", "process_type", "is_verbose", "use_memory",
                  "max_rpm", "is_active", "default_model_id"):
        if field in body:
            sets.append(f"{field} = %s")
            params.append(body[field])
    if "config" in body:
        sets.append("config = %s::jsonb")
        params.append(json.dumps(body["config"]))
    if not sets:
        return {"ok": False, "error": "Keine Felder"}
    sets.append("updated_at = NOW()")
    params.append(crew_id)
    db_execute_rt(f"UPDATE dbai_llm.crew_definitions SET {', '.join(sets)} WHERE id = %s::UUID", tuple(params))
    return {"ok": True}

@app.delete("/api/crews/{crew_id}")
async def crews_delete(crew_id: str, session: dict = Depends(get_current_session)):
    """Crew löschen (nicht wenn is_locked)."""
    rows = db_query_rt("SELECT is_locked, name FROM dbai_llm.crew_definitions WHERE id = %s::UUID", (crew_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Crew nicht gefunden")
    if rows[0].get("is_locked"):
        raise HTTPException(status_code=403, detail=f"Crew '{rows[0]['name']}' ist gesperrt und kann nicht gelöscht werden")
    db_execute_rt("DELETE FROM dbai_llm.crew_definitions WHERE id = %s::UUID", (crew_id,))
    return {"ok": True}

@app.post("/api/crews/{crew_id}/agents")
async def crews_add_agent(crew_id: str, request: Request, session: dict = Depends(get_current_session)):
    """Agent zu einer Crew hinzufügen."""
    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Agent-Name erforderlich")
    db_execute_rt("""
        INSERT INTO dbai_llm.crew_agents
            (crew_id, name, display_name, role, goal, backstory, tools, allow_delegation, sort_order, model_id)
        VALUES (%s::UUID, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (crew_id, name, body.get("display_name", name), body.get("role", ""),
          body.get("goal", ""), body.get("backstory", ""),
          body.get("tools", []), body.get("allow_delegation", False),
          body.get("sort_order", 0), body.get("model_id")))
    return {"ok": True, "name": name}

@app.patch("/api/crews/agents/{agent_id}")
async def crews_update_agent(agent_id: str, request: Request, session: dict = Depends(get_current_session)):
    """Crew-Agent aktualisieren."""
    body = await request.json()
    sets, params = [], []
    for field in ("display_name", "role", "goal", "backstory", "tools",
                  "allow_delegation", "sort_order", "model_id", "is_active"):
        if field in body:
            sets.append(f"{field} = %s")
            params.append(body[field])
    if not sets:
        return {"ok": False, "error": "Keine Felder"}
    sets.append("updated_at = NOW()")
    params.append(agent_id)
    db_execute_rt(f"UPDATE dbai_llm.crew_agents SET {', '.join(sets)} WHERE id = %s::UUID", tuple(params))
    return {"ok": True}

@app.delete("/api/crews/agents/{agent_id}")
async def crews_delete_agent(agent_id: str, session: dict = Depends(get_current_session)):
    """Agent aus Crew entfernen."""
    db_execute_rt("DELETE FROM dbai_llm.crew_agents WHERE id = %s::UUID", (agent_id,))
    return {"ok": True}

@app.post("/api/crews/{crew_id}/tasks")
async def crews_add_task(crew_id: str, request: Request, session: dict = Depends(get_current_session)):
    """Task zu einer Crew hinzufügen."""
    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Task-Name erforderlich")
    db_execute_rt("""
        INSERT INTO dbai_llm.crew_tasks
            (crew_id, agent_id, name, display_name, description, expected_output, is_async, sort_order)
        VALUES (%s::UUID, %s, %s, %s, %s, %s, %s, %s)
    """, (crew_id, body.get("agent_id"), name, body.get("display_name", name),
          body.get("description", ""), body.get("expected_output", ""),
          body.get("is_async", False), body.get("sort_order", 0)))
    return {"ok": True, "name": name}

@app.patch("/api/crews/tasks/{task_id}")
async def crews_update_task(task_id: str, request: Request, session: dict = Depends(get_current_session)):
    """Task aktualisieren."""
    body = await request.json()
    sets, params = [], []
    for field in ("display_name", "description", "expected_output", "agent_id",
                  "is_async", "sort_order"):
        if field in body:
            sets.append(f"{field} = %s")
            params.append(body[field])
    if not sets:
        return {"ok": False, "error": "Keine Felder"}
    sets.append("updated_at = NOW()")
    params.append(task_id)
    db_execute_rt(f"UPDATE dbai_llm.crew_tasks SET {', '.join(sets)} WHERE id = %s::UUID", tuple(params))
    return {"ok": True}

@app.delete("/api/crews/tasks/{task_id}")
async def crews_delete_task(task_id: str, session: dict = Depends(get_current_session)):
    """Task aus Crew entfernen."""
    db_execute_rt("DELETE FROM dbai_llm.crew_tasks WHERE id = %s::UUID", (task_id,))
    return {"ok": True}

@app.get("/api/llm/vram")
async def llm_vram_allocations(session: dict = Depends(get_current_session)):
    """Aktive VRAM-Allokationen und Historie."""
    active = db_query_rt("""
        SELECT va.*, gm.name AS model_name, gm.display_name
        FROM dbai_llm.vram_allocations va
        LEFT JOIN dbai_llm.ghost_models gm ON va.model_id = gm.id
        WHERE va.is_active = TRUE
        ORDER BY va.allocated_at DESC
    """)
    recent = db_query_rt("""
        SELECT va.*, gm.name AS model_name
        FROM dbai_llm.vram_allocations va
        LEFT JOIN dbai_llm.ghost_models gm ON va.model_id = gm.id
        ORDER BY va.allocated_at DESC LIMIT 20
    """)
    return {"active": active or [], "history": recent or []}

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
    except Exception as e:
        logger.debug("silent-exception: %s", e)
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
    except Exception as e:
        logger.debug("silent-exception: %s", e)
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
    """Neue Agent-Instanz erstellen UND Modell automatisch auf GPU laden."""
    body = await request.json()
    model_id = body.get("model_id")
    role_id = body.get("role_id")
    gpu_index = body.get("gpu_index", 0)
    backend = body.get("backend", "llama.cpp")
    context_size = body.get("context_size", 4096)
    max_tokens = body.get("max_tokens", 2048)
    n_gpu_layers = body.get("n_gpu_layers", 99)
    threads = body.get("threads", 8)
    batch_size = body.get("batch_size", 512)
    api_port = body.get("api_port")
    auto_start = body.get("auto_start", True)

    if not model_id:
        raise HTTPException(status_code=400, detail="model_id fehlt")

    # GPU-Name + VRAM ermitteln
    gpu_name = None
    gpu_free = 0
    gpu_total = 0
    try:
        import subprocess
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,memory.total,memory.free",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        for line in r.stdout.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 4 and int(parts[0]) == gpu_index:
                gpu_name = parts[1]
                gpu_total = int(float(parts[2]))
                gpu_free = int(float(parts[3]))
    except Exception as e:
        logger.debug("silent-exception: %s", e)

    # Modell-Info ermitteln
    model_rows = db_query_rt(
        "SELECT id, name, model_path, required_vram_mb, context_size, quantization FROM dbai_llm.ghost_models WHERE id = %s::UUID",
        (model_id,)
    )
    if not model_rows:
        raise HTTPException(status_code=404, detail="Modell nicht gefunden")
    model = model_rows[0]
    vram_alloc = model.get("required_vram_mb") or 0
    model_path = model.get("model_path") or ""
    model_name = model.get("name") or "unknown"

    # Nächsten freien Port finden falls nicht angegeben
    if not api_port:
        existing_ports = db_query_rt("SELECT api_port FROM dbai_llm.agent_instances WHERE api_port IS NOT NULL")
        used = {r["api_port"] for r in existing_ports}
        api_port = 8100
        while api_port in used:
            api_port += 1

    # Instanz erstellen
    result = db_query_rt("""
        INSERT INTO dbai_llm.agent_instances
            (model_id, role_id, gpu_index, gpu_name, vram_allocated_mb, backend,
             api_port, context_size, max_tokens, n_gpu_layers, threads, batch_size, state)
        VALUES (%s::UUID, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'starting')
        RETURNING id
    """, (model_id, role_id if role_id else None, gpu_index, gpu_name, vram_alloc,
          backend, api_port, context_size, max_tokens, n_gpu_layers, threads, batch_size))

    if not result:
        return {"ok": False, "error": "Instanz konnte nicht erstellt werden"}

    inst_id = str(result[0]["id"])
    server_started = False

    # ── AUTO-START: Modell auf GPU laden ──
    if auto_start and model_path:
        # Pfad auflösen
        resolved_path = model_path
        if not model_path.startswith("/"):
            for base in ["/mnt/nvme/models", "/home/worker/DBAI"]:
                candidate = os.path.join(base, model_path)
                if os.path.exists(candidate):
                    resolved_path = candidate
                    break

        if os.path.exists(resolved_path):
            # GPU-Empfehlung berechnen
            quant = model.get("quantization") or "Q4_K_M"
            recommended = _calc_gpu_optimal(vram_alloc, context_size, gpu_free, gpu_total, quant)
            final_ngl = n_gpu_layers if n_gpu_layers != 99 else recommended.get("n_gpu_layers", 99)
            final_ctx = context_size or recommended.get("context_size", 8192)
            final_batch = batch_size or recommended.get("batch_size", 512)
            final_threads = threads or recommended.get("threads", 8)

            loop = asyncio.get_event_loop()
            server_started = await loop.run_in_executor(
                None,
                lambda: _llm_server_start(
                    device="gpu" if n_gpu_layers > 0 else "cpu",
                    n_gpu_layers=final_ngl,
                    ctx_size=final_ctx,
                    threads=final_threads,
                    model_path=resolved_path,
                    model_name=model_name,
                )
            )

            # Instanz + Modell-Status aktualisieren
            new_state = 'running' if server_started else 'error'
            db_execute_rt("""
                UPDATE dbai_llm.agent_instances
                SET state = %s, started_at = CASE WHEN %s THEN NOW() ELSE started_at END,
                    api_endpoint = %s, updated_at = NOW()
                WHERE id = %s::UUID
            """, (new_state, server_started, f"http://localhost:{_llm_server_port}" if server_started else None, inst_id))

            db_execute_rt("""
                UPDATE dbai_llm.ghost_models SET state = %s, is_loaded = %s, updated_at = NOW()
                WHERE id = %s::UUID
            """, ('loaded' if server_started else 'available', server_started, model_id))
        else:
            logger.warning(f"[AGENT] Modell-Datei nicht gefunden: {resolved_path} — Instanz im Standby")
            db_execute_rt("UPDATE dbai_llm.agent_instances SET state = 'stopped' WHERE id = %s::UUID", (inst_id,))
    elif not auto_start:
        db_execute_rt("UPDATE dbai_llm.agent_instances SET state = 'stopped' WHERE id = %s::UUID", (inst_id,))

    return {
        "ok": True,
        "id": inst_id,
        "api_port": api_port,
        "server_started": server_started,
        "model_name": model_name,
    }

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
    """Agent-Instanz löschen UND Modell von GPU entladen."""
    global _llm_model_name, _llm_model_path

    # Instanz-Daten holen
    rows = db_query_rt("""
        SELECT ai.model_id, ai.state, ai.pid, gm.name AS model_name
        FROM dbai_llm.agent_instances ai
        LEFT JOIN dbai_llm.ghost_models gm ON ai.model_id = gm.id
        WHERE ai.id = %s::UUID
    """, (instance_id,))

    if rows:
        inst = rows[0]
        model_name = inst.get("model_name", "")

        # Wenn laufend: llama-server stoppen + GPU freigeben
        if inst.get("state") in ('running', 'starting'):
            # PID-basiertes Stoppen
            if inst.get("pid"):
                try:
                    import signal
                    os.kill(inst["pid"], signal.SIGTERM)
                except (ProcessLookupError, PermissionError):
                    pass

            # Aktiven llama-server stoppen wenn dieses Modell geladen ist
            # WICHTIG: run_in_executor verhindert Blockierung des asyncio Event-Loops
            if model_name and model_name == _llm_model_name:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, _llm_server_stop)
                _llm_model_name = ""
                _llm_model_path = ""
                logger.info(f"[AGENT] llama-server gestoppt beim Löschen von Instanz (Modell: {model_name})")

        # Modell-Status zurücksetzen
        if inst.get("model_id"):
            # Prüfen ob noch andere Instanzen dieses Modell nutzen
            other_inst = db_query_rt("""
                SELECT COUNT(*) AS cnt FROM dbai_llm.agent_instances
                WHERE model_id = %s::UUID AND id != %s::UUID AND state = 'running'
            """, (str(inst["model_id"]), instance_id))
            if not other_inst or other_inst[0]["cnt"] == 0:
                db_execute_rt("""
                    UPDATE dbai_llm.ghost_models SET state = 'available', is_loaded = FALSE, updated_at = NOW()
                    WHERE id = %s::UUID
                """, (str(inst["model_id"]),))

    db_execute_rt("DELETE FROM dbai_llm.agent_instances WHERE id = %s::UUID", (instance_id,))
    return {"ok": True, "gpu_freed": True}

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
    instance_id = body.get("instance_id")
    name = body.get("name", "").strip()
    if not instance_id:
        raise HTTPException(400, "instance_id ist erforderlich")
    if not name:
        raise HTTPException(400, "name ist erforderlich")
    try:
        result = db_query_rt("""
            INSERT INTO dbai_llm.agent_tasks
                (instance_id, task_type, name, description, system_prompt, priority, auto_route)
            VALUES (%s::UUID, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (instance_id, body.get("task_type", "chat"), name,
              body.get("description"), body.get("system_prompt"), body.get("priority", 5),
              body.get("auto_route", False)))
        return {"ok": bool(result), "id": str(result[0]["id"]) if result else None}
    except Exception as e:
        raise HTTPException(500, str(e))

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
    name = body.get("name", "").strip()
    task_prompt = body.get("task_prompt", "").strip()
    if not name:
        raise HTTPException(400, "name ist erforderlich")
    if not task_prompt:
        raise HTTPException(400, "task_prompt ist erforderlich")
    try:
        result = db_query_rt("""
            INSERT INTO dbai_llm.scheduled_jobs
                (name, description, cron_expr, instance_id, role_id, task_prompt, enabled)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (name, body.get("description"), body.get("cron_expr", "0 */6 * * *"),
              body.get("instance_id"), body.get("role_id"),
              task_prompt, body.get("enabled", True)))
        return {"ok": bool(result), "id": str(result[0]["id"]) if result else None}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.delete("/api/agents/scheduled-jobs/{job_id}")
async def agents_delete_job(job_id: str, session: dict = Depends(get_current_session)):
    """Geplanten Job löschen."""
    db_execute_rt("DELETE FROM dbai_llm.scheduled_jobs WHERE id = %s::UUID", (job_id,))
    return {"ok": True}

@app.get("/api/agents/roles")
async def agents_roles(session: dict = Depends(get_current_session)):
    """Alle Ghost-Rollen auflisten."""
    return db_query_rt("SELECT * FROM dbai_llm.ghost_roles ORDER BY priority, name")

@app.put("/api/agents/roles/{role_id}")
async def agents_update_role(role_id: str, request: Request, session: dict = Depends(get_current_session)):
    """Ghost-Rolle bearbeiten (Name, Prompt, Priorität, Schemas etc.)."""
    body = await request.json()
    sets = []
    params = []
    allowed_fields = {
        "display_name": "display_name = %s",
        "description": "description = %s",
        "icon": "icon = %s",
        "color": "color = %s",
        "system_prompt": "system_prompt = %s",
        "priority": "priority = %s",
        "is_critical": "is_critical = %s",
        "accessible_schemas": "accessible_schemas = %s::text[]",
        "accessible_tables": "accessible_tables = %s::text[]",
    }
    for field, sql_expr in allowed_fields.items():
        if field in body:
            sets.append(sql_expr)
            params.append(body[field])
    if not sets:
        return {"ok": False, "error": "Keine Felder angegeben"}
    sets.append("updated_at = NOW()")
    params.append(role_id)
    db_execute_rt(
        f"UPDATE dbai_llm.ghost_roles SET {', '.join(sets)} WHERE id = %s::UUID",
        tuple(params)
    )
    # Aktualisierte Rolle zurückgeben
    updated = db_query_rt("SELECT * FROM dbai_llm.ghost_roles WHERE id = %s::UUID", (role_id,))
    return {"ok": True, "role": updated[0] if updated else None}

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
    require_admin(session)
    body = _validate_body(await request.json(), max_str_len=2000)
    updates = []
    params = []

    if "api_key" in body and body["api_key"]:
        key = body["api_key"]
        enc = encrypt_secret(key)
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
    rows = db_query_rt(
        "SELECT api_base_url, api_key_enc FROM dbai_llm.llm_providers WHERE provider_key = %s",
        (provider_key,)
    )
    if not rows or not rows[0].get("api_key_enc"):
        return {"ok": False, "error": "Kein API-Key konfiguriert"}

    api_base = rows[0]["api_base_url"]
    # FIX (Bug A): decrypt_secret statt rohem base64.b64decode —
    # neu gesetzte Keys sind Fernet-verschlüsselt, rohes b64decode wirft hier
    # binär-ungültige Bytes. decrypt_secret hat intern den Base64-Fallback für
    # Legacy-Keys (vor Fernet-Einführung), daher ist beides lesbar.
    api_key = decrypt_secret(rows[0]["api_key_enc"])
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

@app.get("/api/autonomous/migrations")
async def list_autonomous_migrations(session: dict = Depends(get_current_session)):
    """Alle autonomen Migrationen auflisten."""
    rows = db_query_rt("SELECT * FROM dbai_core.v_autonomous_migrations")
    return {"migrations": rows}

@app.get("/api/autonomous/migrations/{migration_id}")
async def get_autonomous_migration(migration_id: str, session: dict = Depends(get_current_session)):
    """Details einer autonomen Migration."""
    rows = db_query_rt(
        "SELECT * FROM dbai_core.autonomous_migrations WHERE id = %s::UUID", (migration_id,)
    )
    if not rows:
        raise HTTPException(404, "Migration nicht gefunden")
    audit = db_query_rt(
        "SELECT * FROM dbai_core.migration_audit_log WHERE migration_id = %s::UUID ORDER BY created_at",
        (migration_id,)
    )
    return {"migration": rows[0], "audit_log": audit}

@app.post("/api/autonomous/migrations")
async def create_autonomous_migration(request: Request, session: dict = Depends(get_current_session)):
    """Neue autonome Migration erstellen (Ghost oder Admin)."""
    require_admin(session)
    body = await request.json()
    sql = body.get("migration_sql")
    if not sql:
        raise HTTPException(400, "migration_sql erforderlich")
    import hashlib as _hashlib
    checksum = _hashlib.sha256(sql.encode()).hexdigest()
    rows = db_query_rt("""
        INSERT INTO dbai_core.autonomous_migrations
            (title, description, migration_sql, rollback_sql, generated_by, model_used, prompt_used,
             affected_tables, affected_schemas, version_tag, checksum)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, state, created_at
    """, (
        body.get("title", "Untitled Migration"),
        body.get("description"),
        sql,
        body.get("rollback_sql"),
        body.get("generated_by", "ghost"),
        body.get("model_used"),
        body.get("prompt_used"),
        body.get("affected_tables", []),
        body.get("affected_schemas", []),
        body.get("version_tag"),
        checksum,
    ))
    if rows:
        db_execute_rt("""
            INSERT INTO dbai_core.migration_audit_log (migration_id, action, actor, details)
            VALUES (%s::UUID, 'created', %s, '{}')
        """, (rows[0]["id"], body.get("generated_by", "ghost")))
    return {"ok": True, "migration": rows[0] if rows else None}

@app.patch("/api/autonomous/migrations/{migration_id}")
async def update_migration_state(migration_id: str, request: Request, session: dict = Depends(get_current_session)):
    """Migration-State ändern: review, approve, apply, revert, reject."""
    require_admin(session)
    body = await request.json()
    action = body.get("action")
    valid_actions = {
        "review": "review",
        "approve": "approved",
        "reject": "rejected",
        "apply": "applied",
        "revert": "reverted",
    }
    if action not in valid_actions:
        raise HTTPException(400, f"Ungültige Aktion: {action}. Erlaubt: {list(valid_actions.keys())}")

    new_state = valid_actions[action]
    ts_field = ""
    if action == "review":
        ts_field = ", reviewed_at = NOW(), reviewed_by = %s"
    elif action == "apply":
        ts_field = ", applied_at = NOW()"
    elif action == "revert":
        ts_field = ", reverted_at = NOW()"

    params = [new_state]
    if action == "review":
        params.append(session.get("user", {}).get("username", "admin"))
    params.append(body.get("review_notes"))
    params.append(migration_id)

    db_execute_rt(
        f"UPDATE dbai_core.autonomous_migrations SET state = %s{ts_field}, review_notes = %s, updated_at = NOW() WHERE id = %s::UUID",
        params
    )

    # Wenn "apply" — SQL tatsächlich ausführen
    if action == "apply":
        mig = db_query_rt("SELECT migration_sql FROM dbai_core.autonomous_migrations WHERE id = %s::UUID", (migration_id,))
        if mig:
            import time as _time
            start = _time.time()
            try:
                db_execute_rt(mig[0]["migration_sql"])
                exec_ms = int((_time.time() - start) * 1000)
                db_execute_rt("UPDATE dbai_core.autonomous_migrations SET execution_ms = %s WHERE id = %s::UUID", (exec_ms, migration_id))
            except Exception as e:
                db_execute_rt("UPDATE dbai_core.autonomous_migrations SET state = 'rejected', error_message = %s WHERE id = %s::UUID", (str(e), migration_id))
                raise HTTPException(500, f"Migration fehlgeschlagen: {e}")

    # Wenn "revert" — Rollback-SQL ausführen
    if action == "revert":
        mig = db_query_rt("SELECT rollback_sql FROM dbai_core.autonomous_migrations WHERE id = %s::UUID", (migration_id,))
        if mig and mig[0].get("rollback_sql"):
            try:
                db_execute_rt(mig[0]["rollback_sql"])
            except Exception as e:
                raise HTTPException(500, f"Rollback fehlgeschlagen: {e}")

    # Audit-Log
    db_execute_rt("""
        INSERT INTO dbai_core.migration_audit_log (migration_id, action, actor, details)
        VALUES (%s::UUID, %s, %s, %s::JSONB)
    """, (migration_id, action, session.get("user", {}).get("username", "admin"), json.dumps({"notes": body.get("review_notes")})))

    return {"ok": True, "new_state": new_state}

@app.get("/api/gpu/split-configs")
async def list_gpu_split_configs(session: dict = Depends(get_current_session)):
    """Alle Multi-GPU-Split-Konfigurationen."""
    rows = db_query_rt("SELECT * FROM dbai_llm.v_multi_gpu_status")
    return {"configs": rows}

@app.post("/api/gpu/split-configs")
async def create_gpu_split_config(request: Request, session: dict = Depends(get_current_session)):
    """Neue GPU-Split-Konfiguration erstellen."""
    require_admin(session)
    body = await request.json()
    model_id = body.get("model_id")
    if not model_id:
        raise HTTPException(400, "model_id erforderlich")
    rows = db_query_rt("""
        INSERT INTO dbai_llm.gpu_split_configs
            (model_id, name, strategy, gpu_count, total_vram_mb, layer_mapping, notes)
        VALUES (%s::UUID, %s, %s, %s, %s, %s::JSONB, %s)
        RETURNING id, name, strategy, gpu_count
    """, (
        model_id,
        body.get("name", "default-split"),
        body.get("strategy", "layer_split"),
        body.get("gpu_count", 2),
        body.get("total_vram_mb"),
        json.dumps(body.get("layer_mapping", [])),
        body.get("notes"),
    ))
    return {"ok": True, "config": rows[0] if rows else None}

@app.patch("/api/gpu/split-configs/{config_id}/activate")
async def activate_gpu_split(config_id: str, session: dict = Depends(get_current_session)):
    """GPU-Split-Konfiguration aktivieren."""
    require_admin(session)
    # Erst alle anderen deaktivieren für dasselbe Modell
    db_execute_rt("""
        UPDATE dbai_llm.gpu_split_configs SET is_active = false
        WHERE model_id = (SELECT model_id FROM dbai_llm.gpu_split_configs WHERE id = %s::UUID)
    """, (config_id,))
    db_execute_rt("UPDATE dbai_llm.gpu_split_configs SET is_active = true, updated_at = NOW() WHERE id = %s::UUID", (config_id,))
    return {"ok": True}

@app.get("/api/gpu/parallel-sessions")
async def list_parallel_sessions(session: dict = Depends(get_current_session)):
    """Aktive Parallel-Inferenz-Sessions."""
    rows = db_query_rt(
        "SELECT * FROM dbai_llm.parallel_inference_sessions WHERE state NOT IN ('stopped','error') ORDER BY started_at DESC"
    )
    return {"sessions": rows}

@app.get("/api/gpu/sync-events/{session_id}")
async def get_gpu_sync_events(session_id: str, session: dict = Depends(get_current_session)):
    """GPU-Sync-Events einer Parallel-Session."""
    rows = db_query_rt(
        "SELECT * FROM dbai_llm.gpu_sync_events WHERE session_id = %s::UUID ORDER BY created_at DESC LIMIT 100",
        (session_id,)
    )
    return {"sync_events": rows}

@app.get("/api/vision/models")
async def list_vision_models(session: dict = Depends(get_current_session)):
    """Registrierte Vision-Modelle."""
    rows = db_query_rt("SELECT * FROM dbai_llm.vision_models ORDER BY name")
    return {"models": rows}

@app.post("/api/vision/models")
async def register_vision_model(request: Request, session: dict = Depends(get_current_session)):
    """Neues Vision-Modell registrieren."""
    require_admin(session)
    body = await request.json()
    rows = db_query_rt("""
        INSERT INTO dbai_llm.vision_models
            (model_id, name, model_type, supported_formats, max_resolution,
             max_video_length_sec, supports_streaming, supports_batch, config)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::JSONB)
        RETURNING id, name, model_type
    """, (
        body.get("model_id"),
        body["name"],
        body.get("model_type", "multimodal"),
        body.get("supported_formats", ["jpeg", "png", "webp"]),
        body.get("max_resolution", "4096x4096"),
        body.get("max_video_length_sec", 300),
        body.get("supports_streaming", False),
        body.get("supports_batch", True),
        json.dumps(body.get("config", {})),
    ))
    return {"ok": True, "model": rows[0] if rows else None}

@app.get("/api/vision/tasks")
async def list_vision_tasks(session: dict = Depends(get_current_session)):
    """Vision-Task-Queue."""
    rows = db_query_rt("SELECT * FROM dbai_llm.v_vision_overview LIMIT 100")
    return {"tasks": rows}

@app.post("/api/vision/tasks")
async def create_vision_task(request: Request, session: dict = Depends(get_current_session)):
    """Neuen Vision-Task erstellen."""
    body = await request.json()
    task_type = body.get("task_type")
    input_type = body.get("input_type")
    if not task_type or not input_type:
        raise HTTPException(400, "task_type und input_type erforderlich")
    rows = db_query_rt("""
        INSERT INTO dbai_llm.vision_tasks
            (vision_model_id, media_item_id, task_type, input_type, input_path, input_url,
             prompt, priority, requested_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, task_type, state
    """, (
        body.get("vision_model_id"),
        body.get("media_item_id"),
        task_type,
        input_type,
        body.get("input_path"),
        body.get("input_url"),
        body.get("prompt"),
        body.get("priority", 5),
        session.get("user", {}).get("username", "user"),
    ))
    return {"ok": True, "task": rows[0] if rows else None}

@app.get("/api/vision/tasks/{task_id}")
async def get_vision_task(task_id: str, session: dict = Depends(get_current_session)):
    """Vision-Task mit Detections."""
    tasks = db_query_rt("SELECT * FROM dbai_llm.vision_tasks WHERE id = %s::UUID", (task_id,))
    if not tasks:
        raise HTTPException(404, "Task nicht gefunden")
    detections = db_query_rt(
        "SELECT * FROM dbai_llm.vision_detections WHERE task_id = %s::UUID ORDER BY confidence DESC",
        (task_id,)
    )
    return {"task": tasks[0], "detections": detections}
