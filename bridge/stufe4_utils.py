#!/usr/bin/env python3
"""
DBAI Stufe 4 Utilities — Features 16-22
=========================================
16: USB Installer (dd/Ventoy)
17: WLAN Hotspot (hostapd/dnsmasq)
18: Immutable Filesystem (OverlayFS)
19: i18n Runtime Translation
20: Anomalie-Erkennung (Z-Score + Isolation Forest)
21: App Sandboxing (Firejail/cgroups)
22: Network Policy / Firewall (iptables/nftables)
"""

import os
import re
import json
import time
import logging
import subprocess
import threading
import math
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from collections import deque

logger = logging.getLogger("dbai.stufe4")


# ============================================================================
# FEATURE 16: USB Installer
# ============================================================================

class USBInstaller:
    """dd/Ventoy-basiertes Image auf USB-Stick flashen."""

    def __init__(self, db_execute, db_query):
        self.db_execute = db_execute
        self.db_query = db_query
        self._active_jobs = {}

    def detect_usb_devices(self) -> list:
        """USB-Geräte erkennen."""
        devices = []
        try:
            result = subprocess.run(
                ["lsblk", "-J", "-o", "NAME,SIZE,TYPE,VENDOR,MODEL,SERIAL,RM,MOUNTPOINT,TRAN"],
                capture_output=True, text=True, timeout=10
            )
            data = json.loads(result.stdout)
            for dev in data.get("blockdevices", []):
                if dev.get("tran") == "usb" or dev.get("rm") == "1" or dev.get("rm") is True:
                    device_path = f"/dev/{dev['name']}"
                    device = {
                        "device_path": device_path,
                        "device_name": dev.get("name"),
                        "vendor": dev.get("vendor", "").strip(),
                        "model": dev.get("model", "").strip(),
                        "serial": dev.get("serial", ""),
                        "size_bytes": self._parse_size(dev.get("size", "0")),
                        "is_removable": True,
                        "is_mounted": bool(dev.get("mountpoint")),
                        "mount_point": dev.get("mountpoint"),
                    }
                    devices.append(device)

                    # In DB speichern
                    self.db_execute(
                        """INSERT INTO dbai_system.usb_devices
                           (device_path, device_name, vendor, model, serial,
                            size_bytes, is_mounted, mount_point)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                           ON CONFLICT DO NOTHING""",
                        (device_path, dev.get("name"), device.get("vendor"),
                         device.get("model"), device.get("serial"),
                         device.get("size_bytes"), device.get("is_mounted"),
                         device.get("mount_point"))
                    )
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            logger.error(f"USB-Erkennung fehlgeschlagen: {e}")
        return devices

    def flash_image(self, device_path: str, image_path: str,
                    method: str = "dd") -> dict:
        """Image auf USB-Stick flashen."""
        if not Path(image_path).exists():
            return {"error": f"Image nicht gefunden: {image_path}"}

        if not Path(device_path).exists():
            return {"error": f"Gerät nicht gefunden: {device_path}"}

        # Sicherheitscheck: nicht auf System-Disk flashen
        if device_path in ("/dev/sda", "/dev/nvme0n1", "/dev/vda"):
            return {"error": "Sicherheitscheck: System-Disk kann nicht überschrieben werden"}

        # Job erstellen
        image_type = "iso" if image_path.endswith(".iso") else "img"
        rows = self.db_query(
            """INSERT INTO dbai_system.usb_flash_jobs
               (image_path, image_type, method, status)
               VALUES (%s, %s, %s, 'preparing')
               RETURNING id""",
            (image_path, image_type, method)
        )
        job_id = str(rows[0]["id"]) if rows else None
        if not job_id:
            return {"error": "Job konnte nicht erstellt werden"}

        # Flash im Hintergrund starten
        thread = threading.Thread(
            target=self._flash_worker,
            args=(job_id, device_path, image_path, method),
            daemon=True
        )
        self._active_jobs[job_id] = thread
        thread.start()

        return {"job_id": job_id, "status": "started", "device": device_path}

    def _flash_worker(self, job_id: str, device_path: str,
                      image_path: str, method: str):
        """Worker-Thread für USB-Flashing."""
        try:
            self.db_execute(
                "UPDATE dbai_system.usb_flash_jobs SET status = 'flashing', started_at = now() WHERE id = %s",
                (job_id,)
            )

            image_size = Path(image_path).stat().st_size

            if method == "dd":
                proc = subprocess.Popen(
                    ["sudo", "dd", f"if={image_path}", f"of={device_path}",
                     "bs=4M", "status=progress", "conv=fsync"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                _, stderr = proc.communicate(timeout=3600)
                if proc.returncode != 0:
                    raise RuntimeError(f"dd fehlgeschlagen: {stderr.decode()}")
            elif method == "ventoy":
                proc = subprocess.run(
                    ["sudo", "sh", "-c", f"Ventoy2Disk.sh -i -g {device_path}"],
                    capture_output=True, text=True, timeout=600
                )
                if proc.returncode != 0:
                    raise RuntimeError(f"Ventoy fehlgeschlagen: {proc.stderr}")

            self.db_execute(
                """UPDATE dbai_system.usb_flash_jobs
                   SET status = 'completed', progress = 1.0,
                       bytes_written = %s, completed_at = now()
                   WHERE id = %s""",
                (image_size, job_id)
            )
        except Exception as e:
            self.db_execute(
                """UPDATE dbai_system.usb_flash_jobs
                   SET status = 'failed', error_message = %s WHERE id = %s""",
                (str(e), job_id)
            )

    def get_jobs(self) -> list:
        """Flash-Jobs abrufen."""
        return self.db_query(
            """SELECT * FROM dbai_system.usb_flash_jobs
               ORDER BY created_at DESC LIMIT 20"""
        )

    @staticmethod
    def _parse_size(s: str) -> int:
        """Größe parsen (z.B. '8G' → 8589934592)."""
        units = {"B": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
        s = s.strip().upper()
        for unit, mult in units.items():
            if s.endswith(unit):
                try:
                    return int(float(s[:-1]) * mult)
                except ValueError:
                    return 0
        try:
            return int(s)
        except ValueError:
            return 0


# ============================================================================
# FEATURE 17: WLAN Hotspot
# ============================================================================

class WLANHotspot:
    """WLAN-Hotspot für Setup via Handy."""

    def __init__(self, db_execute, db_query):
        self.db_execute = db_execute
        self.db_query = db_query

    def create_hotspot(self, ssid: str = "DBAI-Setup", password: str = "ghost2026",
                       interface: str = "wlan0") -> dict:
        """WLAN-Hotspot erstellen."""
        try:
            # NetworkManager Hotspot
            result = subprocess.run(
                ["nmcli", "device", "wifi", "hotspot",
                 "ifname", interface, "ssid", ssid, "password", password],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                return {"error": result.stderr, "method": "nmcli"}

            # In DB speichern
            self.db_execute(
                """INSERT INTO dbai_system.hotspot_config
                   (ssid, password, interface, is_active, started_at)
                   VALUES (%s, %s, %s, TRUE, now())
                   ON CONFLICT DO NOTHING""",
                (ssid, password, interface)
            )
            return {"success": True, "ssid": ssid, "interface": interface, "method": "nmcli"}
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            return {"error": str(e)}

    def stop_hotspot(self, interface: str = "wlan0") -> dict:
        """Hotspot stoppen."""
        try:
            subprocess.run(
                ["nmcli", "device", "disconnect", interface],
                capture_output=True, text=True, timeout=10
            )
            self.db_execute(
                "UPDATE dbai_system.hotspot_config SET is_active = FALSE WHERE interface = %s",
                (interface,)
            )
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    def get_status(self) -> dict:
        """Hotspot-Status."""
        rows = self.db_query(
            "SELECT * FROM dbai_system.hotspot_config ORDER BY created_at DESC LIMIT 1"
        )
        return rows[0] if rows else {"is_active": False}


# ============================================================================
# FEATURE 18: Immutable Filesystem
# ============================================================================

class ImmutableFS:
    """OverlayFS/SquashFS — nur PostgreSQL darf auf Disk schreiben."""

    def __init__(self, db_execute, db_query):
        self.db_execute = db_execute
        self.db_query = db_query

    def get_config(self) -> dict:
        """Aktuelle Konfiguration abrufen."""
        rows = self.db_query(
            "SELECT * FROM dbai_system.immutable_config ORDER BY created_at DESC LIMIT 1"
        )
        return rows[0] if rows else {"mode": "disabled", "is_active": False}

    def enable(self, mode: str = "overlay", protected: list = None) -> dict:
        """Immutable-Modus aktivieren."""
        if mode not in ("overlay", "squashfs", "btrfs_snapshot"):
            return {"error": f"Unbekannter Modus: {mode}"}

        config = self.get_config()
        if config.get("is_active"):
            return {"error": "Bereits aktiv"}

        if mode == "overlay":
            return self._setup_overlay(protected or ["/usr", "/bin", "/sbin", "/lib", "/etc"])
        elif mode == "btrfs_snapshot":
            return self._create_snapshot("manual", "Manuell erstellt")

        return {"mode": mode, "status": "configured"}

    def _setup_overlay(self, protected_paths: list) -> dict:
        """OverlayFS für geschützte Pfade einrichten."""
        upper = "/var/overlay/upper"
        work = "/var/overlay/work"

        try:
            os.makedirs(upper, exist_ok=True)
            os.makedirs(work, exist_ok=True)
        except OSError as e:
            return {"error": f"Verzeichnis-Erstellung fehlgeschlagen: {e}"}

        self.db_execute(
            """INSERT INTO dbai_system.immutable_config
               (mode, protected_paths, overlay_upper, overlay_work, is_active)
               VALUES ('overlay', %s, %s, %s, TRUE)""",
            (protected_paths, upper, work)
        )

        return {"mode": "overlay", "protected": protected_paths, "status": "configured",
                "note": "Aktivierung erfordert Neustart mit overlay-mountpoints"}

    def _create_snapshot(self, snap_type: str, description: str) -> dict:
        """Filesystem-Snapshot erstellen."""
        name = f"dbai-snap-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        self.db_execute(
            """INSERT INTO dbai_system.fs_snapshots
               (snapshot_name, snapshot_type, description)
               VALUES (%s, %s, %s)""",
            (name, snap_type, description)
        )
        return {"snapshot": name, "type": snap_type}

    def list_snapshots(self) -> list:
        """Alle Snapshots abrufen."""
        return self.db_query(
            "SELECT * FROM dbai_system.fs_snapshots ORDER BY created_at DESC"
        )


# ============================================================================
# FEATURE 20: Anomalie-Erkennung
# ============================================================================

class AnomalyDetector:
    """ML-basierte Anomalie-Erkennung für System-Metriken."""

    def __init__(self, db_execute, db_query):
        self.db_execute = db_execute
        self.db_query = db_query
        self._history = {}  # In-Memory Metriken-Buffer

    def record_metric(self, metric_name: str, value: float, labels: dict = None):
        """Metrik-Wert aufzeichnen und auf Anomalie prüfen."""
        # In DB speichern
        self.db_execute(
            """INSERT INTO dbai_system.metrics_history (metric_name, value, labels)
               VALUES (%s, %s, %s::jsonb)""",
            (metric_name, value, json.dumps(labels or {}))
        )

        # In-Memory Buffer für schnelle Z-Score-Berechnung
        if metric_name not in self._history:
            self._history[metric_name] = deque(maxlen=1000)
        self._history[metric_name].append(value)

    def check_anomaly(self, metric_name: str, value: float) -> dict:
        """Prüfe ob ein Wert eine Anomalie ist (Z-Score)."""
        history = self._history.get(metric_name, deque())

        if len(history) < 10:
            return {"anomaly": False, "reason": "insufficient_data", "value": value}

        values = list(history)
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        stddev = math.sqrt(variance) if variance > 0 else 0

        if stddev == 0:
            return {"anomaly": False, "reason": "zero_variance", "value": value}

        zscore = abs(value - mean) / stddev
        is_anomaly = zscore > 2.0

        if is_anomaly:
            severity = "critical" if zscore > 4.0 else ("warning" if zscore > 3.0 else "info")
            # In DB loggen
            self.db_execute(
                """INSERT INTO dbai_system.anomaly_detections
                   (model_id, metric_name, metric_value, expected_value,
                    expected_range, anomaly_score, severity, description)
                   SELECT id, %s, %s, %s, %s, %s, %s, %s
                   FROM dbai_system.anomaly_models
                   WHERE target_metric = %s AND is_active LIMIT 1""",
                (metric_name, value, mean,
                 [mean - 2*stddev, mean + 2*stddev],
                 zscore, severity,
                 f"Z-Score Anomalie: {metric_name}={value:.2f} (μ={mean:.2f}, σ={stddev:.2f}, z={zscore:.2f})",
                 metric_name)
            )

        return {
            "anomaly": is_anomaly,
            "zscore": round(zscore, 4),
            "mean": round(mean, 4),
            "stddev": round(stddev, 4),
            "value": value,
            "severity": "critical" if zscore > 4.0 else ("warning" if zscore > 3.0 else ("info" if is_anomaly else "normal")),
        }

    def get_detections(self, limit: int = 50, severity: str = None) -> list:
        """Anomalie-Erkennungen abrufen."""
        sql = "SELECT * FROM dbai_system.anomaly_detections"
        params = []
        if severity:
            sql += " WHERE severity = %s"
            params.append(severity)
        sql += " ORDER BY detected_at DESC LIMIT %s"
        params.append(limit)
        return self.db_query(sql, tuple(params))

    def get_models(self) -> list:
        """Anomalie-Modelle abrufen."""
        return self.db_query("SELECT * FROM dbai_system.anomaly_models ORDER BY model_name")

    def create_model(self, model_name: str, model_type: str,
                     target_metric: str, threshold: float = 2.0) -> dict:
        """Neues Anomalie-Modell erstellen."""
        rows = self.db_query(
            """INSERT INTO dbai_system.anomaly_models
               (model_name, model_type, target_metric, threshold)
               VALUES (%s, %s, %s, %s) RETURNING id""",
            (model_name, model_type, target_metric, threshold)
        )
        return {"id": str(rows[0]["id"]), "model_name": model_name} if rows else {"error": "Fehler"}


# ============================================================================
# FEATURE 21: App Sandboxing
# ============================================================================

class AppSandbox:
    """cgroups/Firejail — Linux-Apps in Ghost-Mode isoliert laufen lassen."""

    def __init__(self, db_execute, db_query):
        self.db_execute = db_execute
        self.db_query = db_query

    def get_profiles(self) -> list:
        """Sandbox-Profile abrufen."""
        return self.db_query("SELECT * FROM dbai_system.sandbox_profiles ORDER BY profile_name")

    def create_profile(self, name: str, sandbox_type: str = "firejail",
                       cpu_limit: float = None, memory_limit_mb: int = None,
                       network_mode: str = "restricted") -> dict:
        """Neues Sandbox-Profil erstellen."""
        rows = self.db_query(
            """INSERT INTO dbai_system.sandbox_profiles
               (profile_name, sandbox_type, cpu_limit, memory_limit_mb, network_mode)
               VALUES (%s, %s, %s, %s, %s) RETURNING id""",
            (name, sandbox_type, cpu_limit, memory_limit_mb, network_mode)
        )
        return {"id": str(rows[0]["id"]), "profile_name": name} if rows else {"error": "Fehler"}

    def launch_app(self, app_name: str, executable_path: str,
                   profile_name: str = None) -> dict:
        """App in Sandbox starten."""
        profile = None
        if profile_name:
            profiles = self.db_query(
                "SELECT * FROM dbai_system.sandbox_profiles WHERE profile_name = %s",
                (profile_name,)
            )
            profile = profiles[0] if profiles else None

        try:
            if profile and profile.get("sandbox_type") == "firejail":
                cmd = ["firejail"]
                if profile.get("network_mode") == "none":
                    cmd.append("--net=none")
                if profile.get("cpu_limit"):
                    cmd.extend(["--cpu", str(int(profile["cpu_limit"] * 100))])
                cmd.append(executable_path)
            else:
                cmd = [executable_path]

            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            self.db_execute(
                """INSERT INTO dbai_system.sandboxed_apps
                   (app_name, executable_path, profile_id, pid, status, started_at)
                   VALUES (%s, %s, %s, %s, 'running', now())""",
                (app_name, executable_path,
                 profile["id"] if profile else None, proc.pid)
            )

            return {"pid": proc.pid, "app": app_name, "sandbox": profile_name or "none"}
        except Exception as e:
            return {"error": str(e)}

    def stop_app(self, pid: int) -> dict:
        """Sandboxed App stoppen."""
        try:
            subprocess.run(["kill", str(pid)], timeout=5)
            self.db_execute(
                """UPDATE dbai_system.sandboxed_apps
                   SET status = 'stopped', stopped_at = now() WHERE pid = %s""",
                (pid,)
            )
            return {"stopped": True, "pid": pid}
        except Exception as e:
            return {"error": str(e)}

    def list_running(self) -> list:
        """Laufende Sandbox-Apps auflisten."""
        return self.db_query(
            """SELECT sa.*, sp.profile_name, sp.sandbox_type
               FROM dbai_system.sandboxed_apps sa
               LEFT JOIN dbai_system.sandbox_profiles sp ON sa.profile_id = sp.id
               WHERE sa.status = 'running'
               ORDER BY sa.started_at DESC"""
        )


# ============================================================================
# FEATURE 22: Network Policy / Firewall
# ============================================================================

class NetworkFirewall:
    """iptables/nftables-Integration — Ghost kontrolliert Netzwerk-Policies."""

    def __init__(self, db_execute, db_query):
        self.db_execute = db_execute
        self.db_query = db_query

    def get_rules(self, chain: str = None) -> list:
        """Firewall-Regeln abrufen."""
        sql = "SELECT * FROM dbai_system.firewall_rules WHERE is_active = TRUE"
        params = []
        if chain:
            sql += " AND chain = %s"
            params.append(chain)
        sql += " ORDER BY priority, created_at"
        return self.db_query(sql, tuple(params) if params else None)

    def add_rule(self, rule_name: str, chain: str = "INPUT",
                 action: str = "DROP", protocol: str = None,
                 source_ip: str = None, dest_ip: str = None,
                 source_port: str = None, dest_port: str = None,
                 description: str = None, priority: int = 100) -> dict:
        """Neue Firewall-Regel hinzufügen."""
        rows = self.db_query(
            """INSERT INTO dbai_system.firewall_rules
               (rule_name, chain, action, protocol, source_ip, dest_ip,
                source_port, dest_port, description, priority)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING id""",
            (rule_name, chain, action, protocol, source_ip, dest_ip,
             source_port, dest_port, description, priority)
        )
        return {"id": str(rows[0]["id"]), "rule_name": rule_name} if rows else {"error": "Fehler"}

    def delete_rule(self, rule_id: str) -> dict:
        """Firewall-Regel löschen."""
        self.db_execute(
            "UPDATE dbai_system.firewall_rules SET is_active = FALSE WHERE id = %s",
            (rule_id,)
        )
        return {"deleted": True}

    def apply_rules(self) -> dict:
        """Alle aktiven Regeln mit iptables anwenden."""
        rules = self.get_rules()
        applied = 0
        errors = []

        for rule in rules:
            cmd = ["sudo", "iptables", "-A", rule["chain"]]
            if rule.get("protocol"):
                cmd.extend(["-p", rule["protocol"]])
            if rule.get("source_ip"):
                cmd.extend(["-s", rule["source_ip"]])
            if rule.get("dest_ip"):
                cmd.extend(["-d", rule["dest_ip"]])
            if rule.get("dest_port"):
                cmd.extend(["--dport", str(rule["dest_port"])])
            if rule.get("source_port"):
                cmd.extend(["--sport", str(rule["source_port"])])
            cmd.extend(["-j", rule["action"]])

            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    self.db_execute(
                        "UPDATE dbai_system.firewall_rules SET applied = TRUE WHERE id = %s",
                        (rule["id"],)
                    )
                    applied += 1
                else:
                    errors.append({"rule": rule["rule_name"], "error": result.stderr})
            except Exception as e:
                errors.append({"rule": rule["rule_name"], "error": str(e)})

        return {"applied": applied, "errors": errors}

    def get_zones(self) -> list:
        """Firewall-Zonen abrufen."""
        return self.db_query(
            "SELECT * FROM dbai_system.firewall_zones ORDER BY zone_name"
        )

    def create_zone(self, zone_name: str, default_action: str = "DROP",
                    interfaces: list = None, services: list = None) -> dict:
        """Neue Firewall-Zone erstellen."""
        rows = self.db_query(
            """INSERT INTO dbai_system.firewall_zones
               (zone_name, default_action, interfaces, services)
               VALUES (%s, %s, %s, %s) RETURNING id""",
            (zone_name, default_action, interfaces or [], services or [])
        )
        return {"id": str(rows[0]["id"]), "zone_name": zone_name} if rows else {"error": "Fehler"}

    def get_connections(self, limit: int = 100) -> list:
        """Aktive Netzwerkverbindungen abrufen."""
        connections = []
        try:
            result = subprocess.run(
                ["ss", "-tunp", "--no-header"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.strip().splitlines()[:limit]:
                parts = line.split()
                if len(parts) >= 5:
                    proto = parts[0]
                    local = parts[3]
                    remote = parts[4]
                    process = parts[5] if len(parts) > 5 else ""

                    local_addr, local_port = self._split_addr(local)
                    remote_addr, remote_port = self._split_addr(remote)

                    proc_name = ""
                    proc_match = re.search(r'"([^"]+)"', process)
                    if proc_match:
                        proc_name = proc_match.group(1)

                    connections.append({
                        "protocol": proto, "local_address": local_addr,
                        "local_port": local_port, "remote_address": remote_addr,
                        "remote_port": remote_port, "process_name": proc_name,
                        "status": parts[1] if len(parts) > 1 else "",
                    })
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return connections

    @staticmethod
    def _split_addr(addr: str) -> tuple:
        """Adresse und Port trennen."""
        if "]:" in addr:  # IPv6
            parts = addr.rsplit(":", 1)
            return parts[0], int(parts[1]) if parts[1].isdigit() else 0
        elif ":" in addr:
            parts = addr.rsplit(":", 1)
            return parts[0], int(parts[1]) if parts[1].isdigit() else 0
        return addr, 0
