"""
web/routers/security.py — Security, Repair, Firewall, Synaptic, Anomaly, Sandbox
================================================================================
61 Routen, extrahiert aus web/routers.py (Phase 2b).
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
    except Exception as e:
        logger.debug("silent-exception: %s", e)

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
    except Exception as e:
        logger.debug("silent-exception: %s", e)

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
        db_execute_rt("DELETE FROM dbai_vector.synaptic_memory WHERE id = %s", (memory_id,))
        return {"status": "ok", "message": f"Memory {memory_id} gelöscht"}
    except Exception as e:
        raise HTTPException(500, str(e))

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
async def anomaly_resolve(detection_id: str, body: anomaly_resolve_req = {}, session: dict = Depends(get_current_session)):
    """Anomalie als gelöst markieren."""
    try:
        resolution = body.get("resolution", "Manuell gelöst")
        db_execute_rt(
            """UPDATE dbai_system.anomaly_detections
               SET auto_resolved = true, resolved_at = NOW(),
                   metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object('resolution_note', %s)
               WHERE id = %s""",
            (resolution, detection_id)
        )
        return {"status": "ok", "message": f"Anomalie {detection_id} als gelöst markiert"}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/sandbox/profiles")
async def sandbox_profiles(session: dict = Depends(get_current_session)):
    """Sandbox-Profile auflisten."""
    try:
        rows = db_query_rt("SELECT * FROM dbai_system.sandbox_profiles ORDER BY profile_name")
        return {"profiles": rows}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/sandbox/launch")
async def sandbox_launch(body: sandbox_launch_req, session: dict = Depends(get_current_session)):
    """App in Sandbox starten."""
    try:
        from bridge.stufe4_utils import AppSandbox
        sandbox = AppSandbox(db_execute_rt, db_query_rt)
        result = sandbox.launch_app(body.get("app_name", ""), body.get("executable_path", ""), body.get("profile_name", "default"))
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
        result = sandbox.stop_app(pid)
        return result
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/firewall/rules")
async def firewall_rules(session: dict = Depends(get_current_session)):
    """Firewall-Regeln auflisten."""
    try:
        rows = db_query_rt("SELECT * FROM dbai_system.firewall_rules WHERE is_active = true ORDER BY priority, chain")
        return {"rules": rows}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/firewall/rules")
async def firewall_add_rule(body: firewall_add_rule_req, session: dict = Depends(get_current_session)):
    """Firewall-Regel hinzufügen."""
    rule_name = body.get("name", body.get("rule_name", "")).strip()
    if not rule_name:
        raise HTTPException(400, "rule_name ist erforderlich")
    try:
        from bridge.stufe4_utils import NetworkFirewall
        fw = NetworkFirewall(db_execute_rt, db_query_rt)
        result = fw.add_rule(
            rule_name=rule_name,
            chain=body.get("chain", "INPUT"),
            action=body.get("action", "DROP"),
            protocol=body.get("protocol"),
            source_ip=body.get("source_ip"),
            dest_ip=body.get("dest_ip"),
            source_port=body.get("source_port", str(body["port"]) if "port" in body else None),
            dest_port=body.get("dest_port"),
            description=body.get("description"),
            priority=body.get("priority", 100)
        )
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

@app.get("/api/security/status")
async def security_status(session: dict = Depends(get_current_session)):
    """Gesamter Security-Status des Immunsystems."""
    try:
        status = db_query_rt("""
            SELECT
                (SELECT COUNT(*) FROM dbai_security.vulnerability_findings
                 WHERE status IN ('open', 'confirmed')) AS open_vulns,
                (SELECT COUNT(*) FROM dbai_security.vulnerability_findings
                 WHERE status = 'open' AND severity = 'critical') AS critical_vulns,
                (SELECT COUNT(*) FROM dbai_security.ip_bans
                 WHERE is_active = TRUE) AS active_bans,
                (SELECT COUNT(*) FROM dbai_security.intrusion_events
                 WHERE detected_at > now() - INTERVAL '24 hours') AS ids_24h,
                (SELECT COUNT(*) FROM dbai_security.failed_auth_log
                 WHERE attempt_at > now() - INTERVAL '24 hours') AS failed_auth_24h,
                (SELECT COUNT(*) FROM dbai_security.scan_jobs
                 WHERE status = 'completed'
                 AND last_run_at > now() - INTERVAL '24 hours') AS scans_24h,
                (SELECT COALESCE(ROUND(100.0 * COUNT(*) FILTER (WHERE compliant)
                 / NULLIF(COUNT(*), 0), 1), 0)
                 FROM dbai_security.security_baselines) AS compliance_pct,
                (SELECT COUNT(*) FROM dbai_security.threat_intelligence
                 WHERE is_active = TRUE) AS threat_indicators,
                (SELECT COUNT(*) FROM dbai_security.honeypot_events
                 WHERE detected_at > now() - INTERVAL '24 hours') AS honeypot_24h
        """)
        return {"security": status[0] if status else {}}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/security/vulnerabilities")
async def security_vulnerabilities(
    status: str = "open",
    severity: str = None,
    limit: int = 50,
    session: dict = Depends(get_current_session),
):
    """Schwachstellen auflisten."""
    try:
        sql = """
            SELECT id, severity, category, title, description,
                   affected_target, affected_param, cve_id, cvss_score,
                   status, auto_mitigated, remediation,
                   first_seen_at, last_seen_at
            FROM dbai_security.vulnerability_findings
            WHERE status = %s
        """
        params = [status]
        if severity:
            sql += " AND severity = %s"
            params.append(severity)
        sql += " ORDER BY CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END, first_seen_at DESC LIMIT %s"
        params.append(limit)
        rows = db_query_rt(sql, tuple(params))
        return {"vulnerabilities": rows}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/security/vulnerabilities/{vuln_id}/mitigate")
async def security_mitigate_vuln(vuln_id: str, body: security_mitigate_vuln_req = {}, session: dict = Depends(get_current_session)):
    """Schwachstelle als mitigiert markieren."""
    try:
        new_status = body.get("status", "mitigated")
        db_execute_rt("""
            UPDATE dbai_security.vulnerability_findings
            SET status = %s, resolved_at = now()
            WHERE id = %s::UUID
        """, (new_status, vuln_id))
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/security/intrusions")
async def security_intrusions(
    hours: int = 24,
    limit: int = 100,
    session: dict = Depends(get_current_session),
):
    """IDS-Events der letzten X Stunden."""
    try:
        rows = db_query_rt("""
            SELECT id, event_type, source_ip, source_port, dest_ip, dest_port,
                   protocol, signature_name, classification, priority,
                   action_taken, detected_at
            FROM dbai_security.intrusion_events
            WHERE detected_at > now() - (%s || ' hours')::INTERVAL
            ORDER BY detected_at DESC LIMIT %s
        """, (str(hours), limit))
        return {"intrusions": rows}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/security/bans")
async def security_bans(session: dict = Depends(get_current_session)):
    """Aktive IP-Bans."""
    try:
        rows = db_query_rt("""
            SELECT id, ip_address, cidr_mask, reason, ban_type, source,
                   banned_at, expires_at
            FROM dbai_security.ip_bans
            WHERE is_active = TRUE
            ORDER BY banned_at DESC
        """)
        return {"bans": rows}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/security/bans")
async def security_ban_ip(body: security_ban_ip_req, session: dict = Depends(get_current_session)):
    """IP manuell bannen."""
    try:
        ip = body.get("ip")
        reason = body.get("reason", "Manueller Ban")
        hours = body.get("hours", 24)
        if not ip:
            raise HTTPException(400, "IP-Adresse erforderlich")
        db_execute_rt("""
            INSERT INTO dbai_security.ip_bans (ip_address, reason, ban_type, source, expires_at)
            VALUES (%s::INET, %s, 'temporary', 'manual',
                    now() + (%s || ' hours')::INTERVAL)
            ON CONFLICT (ip_address, cidr_mask) DO UPDATE SET
                is_active = TRUE, banned_at = now(), reason = EXCLUDED.reason,
                expires_at = EXCLUDED.expires_at
        """, (ip, reason, str(hours)))
        return {"status": "ok", "message": f"IP {ip} gebannt für {hours}h"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.delete("/api/security/bans/{ban_id}")
async def security_unban(ban_id: str, session: dict = Depends(get_current_session)):
    """IP-Ban aufheben."""
    try:
        db_execute_rt("""
            UPDATE dbai_security.ip_bans
            SET is_active = FALSE, unban_reason = 'Manuell aufgehoben', unbanned_at = now()
            WHERE id = %s::UUID
        """, (ban_id,))
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/security/scans")
async def security_scans(session: dict = Depends(get_current_session)):
    """Scan-Jobs auflisten."""
    try:
        rows = db_query_rt("""
            SELECT id, scan_type, target, target_type, status, priority,
                   schedule_cron, last_run_at, next_run_at, findings_count,
                   created_at
            FROM dbai_security.scan_jobs
            ORDER BY priority DESC, created_at DESC LIMIT 50
        """)
        return {"scans": rows}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/security/threats")
async def security_threats(session: dict = Depends(get_current_session)):
    """Threat-Intelligence-Einträge."""
    try:
        rows = db_query_rt("""
            SELECT id, ioc_type, ioc_value, threat_type, confidence,
                   source, hit_count, first_seen_at, last_seen_at
            FROM dbai_security.threat_intelligence
            WHERE is_active = TRUE
            ORDER BY confidence DESC, last_seen_at DESC LIMIT 100
        """)
        return {"threats": rows}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/security/threat-score/{ip}")
async def security_threat_score(ip: str, session: dict = Depends(get_current_session)):
    """Threat-Score für eine IP berechnen."""
    try:
        rows = db_query_rt("SELECT dbai_security.calculate_threat_score(%s::INET) AS score", (ip,))
        return {"ip": ip, "threat_score": rows[0]["score"] if rows else 0}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/security/baselines")
async def security_baselines(session: dict = Depends(get_current_session)):
    """Security-Baselines und Compliance-Status."""
    try:
        rows = db_query_rt("""
            SELECT component, check_name, expected_value, current_value,
                   compliant, severity, last_checked_at
            FROM dbai_security.security_baselines
            ORDER BY
                CASE WHEN NOT compliant THEN 0 ELSE 1 END,
                CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
                component, check_name
        """)
        return {"baselines": rows}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/security/responses")
async def security_responses(limit: int = 50, session: dict = Depends(get_current_session)):
    """Automatische Sicherheits-Reaktionen (Feedback-Loop Log)."""
    try:
        rows = db_query_rt("""
            SELECT id, trigger_type, response_type, description,
                   success, executed_at
            FROM dbai_security.security_responses
            ORDER BY executed_at DESC LIMIT %s
        """, (limit,))
        return {"responses": rows}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/security/honeypot")
async def security_honeypot(hours: int = 24, session: dict = Depends(get_current_session)):
    """Honeypot-Events."""
    try:
        rows = db_query_rt("""
            SELECT id, honeypot_type, source_ip, source_port,
                   interaction, detected_at
            FROM dbai_security.honeypot_events
            WHERE detected_at > now() - (%s || ' hours')::INTERVAL
            ORDER BY detected_at DESC LIMIT 100
        """, (str(hours),))
        return {"honeypot_events": rows}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/security/failed-auth")
async def security_failed_auth(hours: int = 24, session: dict = Depends(get_current_session)):
    """Fehlgeschlagene Authentifizierungs-Versuche."""
    try:
        rows = db_query_rt("""
            SELECT source_ip, auth_type, COUNT(*) as attempts,
                   MAX(attempt_at) as last_attempt
            FROM dbai_security.failed_auth_log
            WHERE attempt_at > now() - (%s || ' hours')::INTERVAL
            GROUP BY source_ip, auth_type
            ORDER BY attempts DESC LIMIT 50
        """, (str(hours),))
        return {"failed_auth": rows}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/security/ai/status")
async def security_ai_status(session: dict = Depends(get_current_session)):
    """Status der Security-KI: Ghost-State, Model, Tasks, Config."""
    try:
        # vw_ai_status View abfragen
        status_rows = db_query_rt("SELECT * FROM dbai_security.vw_ai_status")
        status = status_rows[0] if status_rows else {}

        # Config laden
        config_rows = db_query_rt("SELECT key, value, category, description FROM dbai_security.ai_config")
        config = {r["key"]: r["value"] for r in config_rows}

        # Ghost-Info
        ghost_rows = db_query_rt("""
            SELECT r.name AS role, r.display_name AS role_display, r.icon, r.color,
                   m.name AS model_name, m.display_name AS model_display,
                   m.model_type, m.parameter_count, m.quantization,
                   m.is_loaded, m.state AS model_state,
                   ag.state AS ghost_state, ag.activated_at, ag.tokens_used
            FROM dbai_llm.ghost_roles r
            LEFT JOIN dbai_llm.active_ghosts ag ON ag.role_id = r.id
            LEFT JOIN dbai_llm.ghost_models m ON ag.model_id = m.id
            WHERE r.name = 'security'
        """)
        ghost = ghost_rows[0] if ghost_rows else {}

        return {
            "ai_status": status,
            "ghost": ghost,
            "config": config,
            "config_details": config_rows,
        }
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/security/ai/tasks")
async def security_ai_tasks(
    state: str = None, limit: int = 50,
    session: dict = Depends(get_current_session),
):
    """KI-Analyse-Tasks auflisten."""
    try:
        sql = """
            SELECT id, task_type, state, trigger_source, triggered_by,
                   risk_level, confidence, auto_executed,
                   ai_assessment, recommended_actions,
                   created_at, started_at, completed_at, processing_ms
            FROM dbai_security.ai_tasks
        """
        params = []
        if state:
            sql += " WHERE state = %s"
            params.append(state)
        sql += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)
        rows = db_query_rt(sql, tuple(params))
        return {"tasks": rows}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/security/ai/log")
async def security_ai_log(limit: int = 50, session: dict = Depends(get_current_session)):
    """KI-Analyse-Log (Append-Only Audit)."""
    try:
        rows = db_query_rt("""
            SELECT id, ts, task_id, analysis_type, input_summary,
                   output_summary, risk_level, tokens_used,
                   model_name, duration_ms, auto_action
            FROM dbai_security.ai_analysis_log
            ORDER BY ts DESC LIMIT %s
        """, (limit,))
        return {"log": rows}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/security/ai/task/{task_id}")
async def security_ai_task_detail(task_id: str, session: dict = Depends(get_current_session)):
    """Einzelnen KI-Task abfragen (für Polling während Verarbeitung)."""
    try:
        rows = db_query_rt("""
            SELECT id, task_type, state, trigger_source, triggered_by,
                   risk_level, confidence, auto_executed,
                   ai_assessment, recommended_actions, output_data,
                   error_message, created_at, started_at, completed_at, processing_ms
            FROM dbai_security.ai_tasks WHERE id = %s::UUID
        """, (task_id,))
        if not rows:
            raise HTTPException(404, "Task nicht gefunden")
        return {"task": rows[0]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/security/ai/analyze")
async def security_ai_analyze(body: security_ai_analyze_req, session: dict = Depends(get_current_session)):
    """Manuelle KI-Analyse auslösen — wird sofort vom Security-Ghost verarbeitet."""
    try:
        task_type = body.get("task_type", "risk_scoring")
        input_data = body.get("input_data", {})
        valid_types = [
            'threat_analysis', 'vuln_assessment', 'incident_response',
            'baseline_audit', 'anomaly_detection', 'log_analysis',
            'network_forensics', 'risk_scoring', 'policy_recommendation',
            'periodic_report'
        ]
        if task_type not in valid_types:
            raise HTTPException(400, f"Ungültiger task_type. Erlaubt: {valid_types}")

        # Prüfe ob LLM-Server läuft
        if not _llm_server_health():
            raise HTTPException(503, "LLM-Server nicht erreichbar. Bitte zuerst ein Modell laden.")

        # Task erstellen via DB-Funktion
        rows = db_query_rt(
            "SELECT dbai_security.create_ai_task(%s, %s::JSONB, 'manual', 'user') AS task_id",
            (task_type, json.dumps(input_data, default=str))
        )
        task_id = rows[0]["task_id"] if rows else None
        if not task_id:
            raise HTTPException(500, "Task-Erstellung fehlgeschlagen")

        task_id_str = str(task_id)

        # KI-Analyse asynchron in Thread starten (blockiert nicht den API-Response)
        loop = asyncio.get_event_loop()
        loop.run_in_executor(
            None,
            _security_ai_process_task, task_id_str, task_type, input_data
        )

        return {
            "task_id": task_id_str,
            "status": "processing",
            "task_type": task_type,
            "model": _llm_model_name,
            "message": f"KI-Analyse ({task_type}) gestartet mit {_llm_model_name}"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/security/ai/analyze-ip")
async def security_ai_analyze_ip(body: security_ai_analyze_ip_req, session: dict = Depends(get_current_session)):
    """KI-Analyse für eine spezifische IP-Adresse — wird sofort vom Security-Ghost verarbeitet."""
    try:
        ip = body.get("ip")
        if not ip:
            raise HTTPException(400, "IP-Adresse erforderlich")

        # Prüfe ob LLM-Server läuft
        if not _llm_server_health():
            raise HTTPException(503, "LLM-Server nicht erreichbar. Bitte zuerst ein Modell laden.")

        # Daten über diese IP sammeln
        intrusions = db_query_rt("""
            SELECT event_type, classification, priority, COUNT(*) AS cnt,
                   MAX(detected_at) AS last_seen
            FROM dbai_security.intrusion_events
            WHERE source_ip = %s::INET
            GROUP BY event_type, classification, priority
        """, (ip,))
        auth_fails = db_query_rt("""
            SELECT auth_type, COUNT(*) AS attempts, MAX(attempt_at) AS last_attempt
            FROM dbai_security.failed_auth_log
            WHERE source_ip = %s::INET
            GROUP BY auth_type
        """, (ip,))
        honeypot_hits = db_query_rt("""
            SELECT honeypot_type, interaction, COUNT(*) AS cnt
            FROM dbai_security.honeypot_events
            WHERE source_ip = %s::INET
            GROUP BY honeypot_type, interaction
        """, (ip,))
        score_rows = db_query_rt(
            "SELECT dbai_security.calculate_threat_score(%s::INET) AS score", (ip,)
        )

        input_data = {
            "ip": ip,
            "threat_score": score_rows[0]["score"] if score_rows else 0,
            "intrusion_events": intrusions,
            "failed_auth": auth_fails,
            "honeypot_triggers": honeypot_hits,
        }

        rows = db_query_rt(
            "SELECT dbai_security.create_ai_task('threat_analysis', %s::JSONB, 'manual', 'user') AS task_id",
            (json.dumps(input_data, default=str),)
        )
        task_id = rows[0]["task_id"] if rows else None
        if not task_id:
            raise HTTPException(500, "Task-Erstellung fehlgeschlagen")

        task_id_str = str(task_id)

        # KI-Analyse asynchron in Thread starten
        loop = asyncio.get_event_loop()
        loop.run_in_executor(
            None,
            _security_ai_process_task, task_id_str, "threat_analysis", input_data
        )

        return {
            "task_id": task_id_str,
            "status": "processing",
            "ip": ip,
            "model": _llm_model_name,
            "message": f"IP-Analyse für {ip} gestartet mit {_llm_model_name}"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/security/ai/config")
async def security_ai_config_get(session: dict = Depends(get_current_session)):
    """Security-AI-Konfiguration lesen."""
    try:
        rows = db_query_rt("SELECT key, value, description, category, updated_at FROM dbai_security.ai_config ORDER BY category, key")
        return {"config": rows}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.put("/api/security/ai/config")
async def security_ai_config_update(body: security_ai_config_update_req, session: dict = Depends(get_current_session)):
    """Security-AI-Konfiguration aktualisieren."""
    try:
        key = body.get("key")
        value = body.get("value")
        if not key:
            raise HTTPException(400, "key erforderlich")

        json_val = json.dumps(value) if not isinstance(value, str) else value
        db_execute_rt("""
            INSERT INTO dbai_security.ai_config (key, value, updated_at, updated_by)
            VALUES (%s, %s::JSONB, NOW(), 'user')
            ON CONFLICT (key) DO UPDATE SET
                value = EXCLUDED.value, updated_at = NOW(), updated_by = 'user'
        """, (key, json_val))
        return {"status": "ok", "key": key}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/security/metrics")
async def security_metrics(session: dict = Depends(get_current_session)):
    """Security-Metriken (Aggregiert)."""
    try:
        rows = db_query_rt("""
            SELECT metric_name, metric_value, metric_unit,
                   recorded_at, metadata
            FROM dbai_security.security_metrics
            ORDER BY recorded_at DESC LIMIT 100
        """)
        return {"metrics": rows}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/security/tls")
async def security_tls_certificates(session: dict = Depends(get_current_session)):
    """TLS-Zertifikat-Überwachung."""
    try:
        rows = db_query_rt("""
            SELECT id, domain, issuer, serial_number,
                   issued_at, expires_at, is_valid, check_result,
                   last_checked_at
            FROM dbai_security.tls_certificates
            ORDER BY expires_at ASC
        """)
        return {"certificates": rows}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/security/cve")
async def security_cve_tracking(session: dict = Depends(get_current_session)):
    """CVE-Tracking."""
    try:
        rows = db_query_rt("""
            SELECT id, cve_id, title, description, cvss_score,
                   affected_pkg, affected_ver, fixed_ver,
                   is_relevant, is_patched, patched_at,
                   discovered_at, source_url
            FROM dbai_security.cve_tracking
            ORDER BY cvss_score DESC NULLS LAST, discovered_at DESC
        """)
        return {"cves": rows}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/security/dns-sinkhole")
async def security_dns_sinkhole(session: dict = Depends(get_current_session)):
    """DNS-Sinkhole-Regeln."""
    try:
        rows = db_query_rt("""
            SELECT id, domain_pattern, reason, source,
                   is_active, hit_count, created_at
            FROM dbai_security.dns_sinkhole
            ORDER BY hit_count DESC, created_at DESC
        """)
        return {"sinkhole": rows}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/security/dns-sinkhole")
async def security_dns_sinkhole_add(body: security_dns_sinkhole_add_req, session: dict = Depends(get_current_session)):
    """DNS-Sinkhole-Regel hinzufügen."""
    try:
        domain = body.get("domain_pattern")
        reason = body.get("reason", "Manuell hinzugefügt")
        if not domain:
            raise HTTPException(400, "domain_pattern erforderlich")
        db_execute_rt("""
            INSERT INTO dbai_security.dns_sinkhole (domain_pattern, reason, source)
            VALUES (%s, %s, 'manual')
            ON CONFLICT DO NOTHING
        """, (domain, reason))
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.delete("/api/security/dns-sinkhole/{rule_id}")
async def security_dns_sinkhole_delete(rule_id: str, session: dict = Depends(get_current_session)):
    """DNS-Sinkhole-Regel deaktivieren."""
    try:
        db_execute_rt(
            "UPDATE dbai_security.dns_sinkhole SET is_active = FALSE WHERE id = %s::UUID",
            (rule_id,)
        )
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/security/rate-limits")
async def security_rate_limits(session: dict = Depends(get_current_session)):
    """Rate-Limiting-Konfiguration."""
    try:
        rows = db_query_rt("""
            SELECT id, target_type, target_value, max_requests,
                   window_seconds, current_count, window_start,
                   is_blocked, blocked_until
            FROM dbai_security.rate_limits
            ORDER BY is_blocked DESC, current_count DESC
        """)
        return {"rate_limits": rows}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.put("/api/security/rate-limits/{limit_id}")
async def security_rate_limit_update(limit_id: str, body: security_rate_limit_update_req, session: dict = Depends(get_current_session)):
    """Rate-Limit aktualisieren."""
    try:
        max_req = body.get("max_requests")
        window = body.get("window_seconds")
        if max_req is not None:
            db_execute_rt(
                "UPDATE dbai_security.rate_limits SET max_requests = %s WHERE id = %s::UUID",
                (max_req, limit_id)
            )
        if window is not None:
            db_execute_rt(
                "UPDATE dbai_security.rate_limits SET window_seconds = %s WHERE id = %s::UUID",
                (window, limit_id)
            )
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/security/network-traffic")
async def security_network_traffic(hours: int = 1, limit: int = 100, session: dict = Depends(get_current_session)):
    """Netzwerk-Traffic-Log."""
    try:
        rows = db_query_rt("""
            SELECT id, source_ip, dest_ip, source_port, dest_port,
                   protocol, bytes_sent, bytes_received,
                   connection_duration_ms, geo_country,
                   is_suspicious, recorded_at
            FROM dbai_security.network_traffic_log
            WHERE recorded_at > now() - (%s || ' hours')::INTERVAL
            ORDER BY recorded_at DESC LIMIT %s
        """, (str(hours), limit))
        return {"traffic": rows}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/security/permissions")
async def security_permissions(limit: int = 100, session: dict = Depends(get_current_session)):
    """Permission-Audit-Log."""
    try:
        rows = db_query_rt("""
            SELECT id, schema_name, table_name, role_name,
                   privilege_type, is_granted, checked_at, notes
            FROM dbai_security.permission_audit
            ORDER BY checked_at DESC LIMIT %s
        """, (limit,))
        return {"permissions": rows}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/security/ghost-roles")
async def security_ghost_roles(session: dict = Depends(get_current_session)):
    """Alle Ghost-Rollen für Security-Kontext."""
    try:
        rows = db_query_rt("""
            SELECT r.id, r.name, r.display_name, r.icon, r.color,
                   r.system_prompt, r.priority, r.is_critical,
                   m.name AS active_model, m.display_name AS model_display,
                   ag.state AS ghost_state
            FROM dbai_llm.ghost_roles r
            LEFT JOIN dbai_llm.active_ghosts ag ON ag.role_id = r.id
            LEFT JOIN dbai_llm.ghost_models m ON ag.model_id = m.id
            ORDER BY r.priority ASC
        """)
        return {"roles": rows}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/security/ghost-models")
async def security_ghost_models(session: dict = Depends(get_current_session)):
    """Verfügbare Ghost-Modelle."""
    try:
        rows = db_query_rt("""
            SELECT id, name, display_name, model_type, provider,
                   parameter_count, quantization, context_size,
                   required_vram_mb, state, is_loaded,
                   total_tokens, total_requests, avg_latency_ms,
                   capabilities
            FROM dbai_llm.ghost_models
            ORDER BY name
        """)
        return {"models": rows}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/security/ghost-swap")
async def security_ghost_swap(body: security_ghost_swap_req, session: dict = Depends(get_current_session)):
    """Ghost-Modell für Security-Rolle wechseln — startet tatsächlich das LLM mit dem neuen Modell."""
    try:
        model_name = body.get("model_name")
        reason = body.get("reason", "UI — Security-Modellwechsel")
        if not model_name:
            raise HTTPException(400, "model_name erforderlich")

        # 1. DB-Swap: active_ghosts aktualisieren + ghost_history loggen
        rows = db_query_rt(
            "SELECT dbai_llm.swap_ghost('security', %s, %s, 'user') AS result",
            (model_name, reason)
        )
        result = rows[0]["result"] if rows else {}

        # 2. Modell-Pfad aus DB laden
        model_row = db_query_rt(
            "SELECT name, model_path, display_name FROM dbai_llm.ghost_models WHERE name = %s",
            (model_name,)
        )
        if not model_row or not model_row[0].get("model_path"):
            return {"status": "partial", "swap_result": result,
                    "warning": f"Modell {model_name} hat keinen model_path in der DB"}

        m = model_row[0]
        model_path = m["model_path"]

        # Relative Pfade auflösen
        if not model_path.startswith("/"):
            for base in ["/mnt/nvme/models", "/home/worker/DBAI"]:
                candidate = os.path.join(base, model_path)
                if os.path.exists(candidate):
                    model_path = candidate
                    break

        if not os.path.exists(model_path):
            return {"status": "partial", "swap_result": result,
                    "warning": f"Modell-Datei nicht gefunden: {model_path}"}

        # 3. LLM-Server auf neues Modell umschalten (async in Thread-Pool)
        logger.info(f"[SECURITY-AI] Ghost-Swap: {_llm_model_name} → {model_name} ({reason})")
        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(
            None,
            lambda: _llm_server_start(
                device=_llm_server_device,
                n_gpu_layers=_llm_server_gpu_layers,
                ctx_size=_llm_server_ctx_size,
                threads=_llm_server_threads,
                model_path=model_path,
                model_name=model_name,
            )
        )

        if success:
            # ghost_models State aktualisieren
            try:
                db_execute_rt("""
                    UPDATE dbai_llm.ghost_models SET state = 'unloaded', is_loaded = FALSE, updated_at = NOW()
                    WHERE state = 'loaded' AND name != %s
                """, (model_name,))
                db_execute_rt("""
                    UPDATE dbai_llm.ghost_models SET state = 'loaded', is_loaded = TRUE, updated_at = NOW()
                    WHERE name = %s
                """, (model_name,))
            except Exception as e:
                logger.warning("[SECURITY-AI] Model-State-Update Fehler: %s", e)

            logger.info(f"[SECURITY-AI] ✅ Ghost-Swap erfolgreich: {model_name}")
            return {
                "status": "ok",
                "swap_result": result,
                "model_loaded": True,
                "model": model_name,
                "display_name": m.get("display_name", model_name),
                "message": f"Security-Ghost jetzt aktiv mit {m.get('display_name', model_name)}"
            }
        else:
            logger.error(f"[SECURITY-AI] ❌ Ghost-Swap fehlgeschlagen: {model_name}")
            return {
                "status": "error",
                "swap_result": result,
                "model_loaded": False,
                "error": f"llama-server konnte {model_name} nicht laden"
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
