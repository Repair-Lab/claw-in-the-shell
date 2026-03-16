#!/usr/bin/env python3
"""
DBAI System Config Import — Feature 12
========================================
/etc/ und ~/.config/ parsen → WLAN-Passwörter, Tastaturlayouts,
User-Rechte, Shell-Konfiguration → system_config Tabelle.
"""

import os
import re
import json
import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger("dbai.config_import")


class ConfigImporter:
    """Importiert System-Konfigurationen in die DBAI-Datenbank."""

    def __init__(self, db_execute, db_query):
        self.db_execute = db_execute
        self.db_query = db_query

    # ── Master-Scan ──────────────────────────────────────────────────────

    def scan_all(self) -> dict:
        """Alle verfügbaren Konfigurationen scannen."""
        results = {
            "wifi": self.scan_wifi(),
            "keyboard": self.scan_keyboard(),
            "locale": self.scan_locale(),
            "timezone": self.scan_timezone(),
            "display": self.scan_display(),
            "audio": self.scan_audio(),
            "shell": self.scan_shell(),
            "users": self.scan_users(),
            "network": self.scan_network(),
            "ssh": self.scan_ssh(),
            "systemd": self.scan_systemd_services(),
            "fstab": self.scan_fstab(),
            "dns": self.scan_dns(),
            "hosts": self.scan_hosts(),
            "cron": self.scan_cron(),
        }
        # Zusammenfassung
        total = sum(len(v) if isinstance(v, list) else (1 if v else 0) for v in results.values())
        results["_summary"] = {"total_configs": total, "categories": len(results) - 1}
        return results

    def import_all(self) -> dict:
        """Alle Konfigurationen importieren."""
        scan = self.scan_all()
        imported = {}
        for category, configs in scan.items():
            if category.startswith("_"):
                continue
            if isinstance(configs, list):
                for cfg in configs:
                    self._upsert_config(category, cfg)
                imported[category] = len(configs)
            elif isinstance(configs, dict) and configs:
                self._upsert_config(category, configs)
                imported[category] = 1
        return imported

    def _upsert_config(self, config_type: str, config: dict):
        """Konfiguration in DB speichern (upsert)."""
        name = config.get("name", config.get("ssid", config.get("key", config_type)))
        source = config.get("source_path", "")
        is_sensitive = config.get("is_sensitive", False)
        raw = config.get("raw", "")
        # Sensitive Daten aus dem JSON-Value entfernen
        safe_config = {k: v for k, v in config.items()
                       if k not in ("raw", "source_path", "is_sensitive", "password")}
        self.db_execute(
            """INSERT INTO dbai_core.system_config
               (config_type, config_name, config_value, source_path, is_sensitive, original_raw)
               VALUES (%s, %s, %s::jsonb, %s, %s, %s)
               ON CONFLICT (config_type, config_name)
               DO UPDATE SET config_value = EXCLUDED.config_value,
                             source_path = EXCLUDED.source_path,
                             imported_at = now()""",
            (config_type, str(name), json.dumps(safe_config), source, is_sensitive, raw)
        )

    # ── WLAN ─────────────────────────────────────────────────────────────

    def scan_wifi(self) -> list:
        """WLAN-Profile aus NetworkManager scannen."""
        profiles = []
        nm_path = Path("/etc/NetworkManager/system-connections")
        if nm_path.exists():
            for f in nm_path.iterdir():
                if not f.is_file():
                    continue
                try:
                    content = f.read_text(errors="replace")
                    profile = self._parse_nm_connection(content, str(f))
                    if profile:
                        profiles.append(profile)
                except PermissionError:
                    logger.debug(f"Kein Zugriff: {f}")

        # wpa_supplicant
        wpa_conf = Path("/etc/wpa_supplicant/wpa_supplicant.conf")
        if wpa_conf.exists():
            try:
                content = wpa_conf.read_text(errors="replace")
                profiles.extend(self._parse_wpa_supplicant(content, str(wpa_conf)))
            except PermissionError:
                pass

        # nmcli als Fallback
        if not profiles:
            try:
                result = subprocess.run(
                    ["nmcli", "-t", "-f", "NAME,TYPE,DEVICE", "connection", "show"],
                    capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.strip().splitlines():
                    parts = line.split(":")
                    if len(parts) >= 2 and parts[1] in ("802-11-wireless", "wifi"):
                        profiles.append({
                            "name": parts[0], "ssid": parts[0],
                            "security_type": "unknown", "source_path": "nmcli",
                            "is_sensitive": True
                        })
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

        return profiles

    def _parse_nm_connection(self, content: str, path: str) -> Optional[dict]:
        """NetworkManager .nmconnection Datei parsen."""
        sections = {}
        current = None
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("[") and line.endswith("]"):
                current = line[1:-1]
                sections[current] = {}
            elif "=" in line and current:
                key, val = line.split("=", 1)
                sections[current][key.strip()] = val.strip()

        conn = sections.get("connection", {})
        wifi = sections.get("wifi", {})
        security = sections.get("wifi-security", {})

        if conn.get("type") != "802-11-wireless":
            return None

        return {
            "name": conn.get("id", "Unknown"),
            "ssid": wifi.get("ssid", conn.get("id", "")),
            "security_type": security.get("key-mgmt", "open").replace("wpa-psk", "wpa2"),
            "auto_connect": conn.get("autoconnect", "true") == "true",
            "source_path": path,
            "is_sensitive": True,
            "interface": wifi.get("mac-address", ""),
        }

    def _parse_wpa_supplicant(self, content: str, path: str) -> list:
        """wpa_supplicant.conf parsen."""
        profiles = []
        blocks = re.findall(r"network\s*=\s*\{([^}]+)\}", content, re.DOTALL)
        for block in blocks:
            props = {}
            for line in block.strip().splitlines():
                if "=" in line:
                    key, val = line.strip().split("=", 1)
                    props[key.strip()] = val.strip().strip('"')
            if props.get("ssid"):
                profiles.append({
                    "name": props["ssid"], "ssid": props["ssid"],
                    "security_type": "wpa2" if "psk" in props else "open",
                    "source_path": path, "is_sensitive": True,
                })
        return profiles

    # ── Tastatur ─────────────────────────────────────────────────────────

    def scan_keyboard(self) -> list:
        """Tastaturlayout-Konfiguration scannen."""
        configs = []

        # /etc/default/keyboard
        kb_file = Path("/etc/default/keyboard")
        if kb_file.exists():
            try:
                content = kb_file.read_text(errors="replace")
                config = {"name": "keyboard_default", "source_path": str(kb_file), "raw": content}
                for line in content.splitlines():
                    if "=" in line and not line.strip().startswith("#"):
                        key, val = line.split("=", 1)
                        config[key.strip()] = val.strip().strip('"')
                configs.append(config)
            except PermissionError:
                pass

        # localectl
        try:
            result = subprocess.run(["localectl", "status"], capture_output=True, text=True, timeout=5)
            for line in result.stdout.splitlines():
                line = line.strip()
                if ":" in line:
                    key, val = line.split(":", 1)
                    if "Layout" in key or "Model" in key or "Variant" in key:
                        configs.append({"name": f"localectl_{key.strip()}", "key": key.strip(), "value": val.strip(),
                                        "source_path": "localectl"})
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        return configs

    # ── Locale ───────────────────────────────────────────────────────────

    def scan_locale(self) -> list:
        """System-Locale scannen."""
        configs = []
        try:
            result = subprocess.run(["locale"], capture_output=True, text=True, timeout=5)
            for line in result.stdout.strip().splitlines():
                if "=" in line:
                    key, val = line.split("=", 1)
                    configs.append({"name": key.strip(), "key": key.strip(),
                                    "value": val.strip().strip('"'), "source_path": "locale"})
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return configs

    # ── Timezone ─────────────────────────────────────────────────────────

    def scan_timezone(self) -> dict:
        """System-Zeitzone scannen."""
        tz = ""
        tz_file = Path("/etc/timezone")
        if tz_file.exists():
            tz = tz_file.read_text().strip()
        if not tz:
            localtime = Path("/etc/localtime")
            if localtime.is_symlink():
                target = str(localtime.resolve())
                if "zoneinfo/" in target:
                    tz = target.split("zoneinfo/", 1)[1]
        if not tz:
            try:
                result = subprocess.run(["timedatectl", "show", "--property=Timezone"],
                                        capture_output=True, text=True, timeout=5)
                for line in result.stdout.splitlines():
                    if "=" in line:
                        tz = line.split("=", 1)[1].strip()
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
        return {"name": "timezone", "value": tz, "source_path": "/etc/timezone"} if tz else {}

    # ── Display ──────────────────────────────────────────────────────────

    def scan_display(self) -> list:
        """Display-Konfiguration scannen."""
        configs = []
        try:
            result = subprocess.run(["xrandr", "--query"], capture_output=True, text=True, timeout=5)
            for line in result.stdout.splitlines():
                if " connected" in line:
                    parts = line.split()
                    configs.append({
                        "name": parts[0], "connected": True,
                        "resolution": parts[2] if len(parts) > 2 else "unknown",
                        "source_path": "xrandr"
                    })
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return configs

    # ── Audio ────────────────────────────────────────────────────────────

    def scan_audio(self) -> list:
        """Audio-Konfiguration scannen."""
        configs = []
        try:
            result = subprocess.run(["pactl", "list", "short", "sinks"],
                                    capture_output=True, text=True, timeout=5)
            for line in result.stdout.strip().splitlines():
                parts = line.split("\t")
                if len(parts) >= 2:
                    configs.append({"name": parts[1], "id": parts[0], "source_path": "pactl"})
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return configs

    # ── Shell ────────────────────────────────────────────────────────────

    def scan_shell(self) -> list:
        """Shell-Konfiguration scannen."""
        configs = []
        home = Path.home()
        for rc_file in [".bashrc", ".zshrc", ".profile", ".bash_profile", ".bash_aliases"]:
            path = home / rc_file
            if path.exists():
                try:
                    content = path.read_text(errors="replace")
                    aliases = re.findall(r"alias\s+(\w+)='([^']*)'", content)
                    exports = re.findall(r"export\s+(\w+)=(.+)", content)
                    configs.append({
                        "name": rc_file, "source_path": str(path),
                        "aliases": len(aliases), "exports": len(exports),
                        "lines": len(content.splitlines()),
                        "raw": content[:2000],  # Erste 2000 Zeichen
                    })
                except PermissionError:
                    pass
        return configs

    # ── Users ────────────────────────────────────────────────────────────

    def scan_users(self) -> list:
        """System-User und Rechte scannen."""
        users = []
        try:
            with open("/etc/passwd", "r") as f:
                for line in f:
                    parts = line.strip().split(":")
                    if len(parts) >= 7:
                        uid = int(parts[2])
                        if uid >= 1000 or uid == 0:  # Reguläre User + root
                            user = {
                                "name": parts[0], "linux_user": parts[0],
                                "uid": uid, "gid": int(parts[3]),
                                "home": parts[5], "shell": parts[6],
                                "source_path": "/etc/passwd"
                            }
                            # Gruppen
                            try:
                                result = subprocess.run(["groups", parts[0]],
                                                        capture_output=True, text=True, timeout=3)
                                groups = result.stdout.strip().split(":")[1].strip().split() if ":" in result.stdout else []
                                user["groups"] = groups
                                user["sudo_access"] = "sudo" in groups or "wheel" in groups
                            except (FileNotFoundError, subprocess.TimeoutExpired, IndexError):
                                user["groups"] = []
                                user["sudo_access"] = False

                            # SSH-Keys
                            ssh_dir = Path(parts[5]) / ".ssh"
                            if ssh_dir.exists():
                                user["ssh_keys"] = [f.name for f in ssh_dir.iterdir()
                                                    if f.name.endswith(".pub")]
                            users.append(user)
        except PermissionError:
            pass

        # User-Rechte in DB speichern
        for user in users:
            self.db_execute(
                """INSERT INTO dbai_core.user_permissions
                   (linux_user, linux_uid, linux_gid, groups, home_dir, shell, sudo_access, ssh_keys)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (linux_user) DO UPDATE SET
                       groups = EXCLUDED.groups, sudo_access = EXCLUDED.sudo_access,
                       ssh_keys = EXCLUDED.ssh_keys, imported_at = now()""",
                (user["linux_user"], user.get("uid"), user.get("gid"),
                 user.get("groups", []), user.get("home"), user.get("shell"),
                 user.get("sudo_access", False), user.get("ssh_keys", []))
            )

        return users

    # ── Network ──────────────────────────────────────────────────────────

    def scan_network(self) -> list:
        """Netzwerk-Interfaces scannen."""
        interfaces = []
        try:
            result = subprocess.run(["ip", "-j", "addr"], capture_output=True, text=True, timeout=5)
            data = json.loads(result.stdout)
            for iface in data:
                interfaces.append({
                    "name": iface.get("ifname", ""),
                    "state": iface.get("operstate", ""),
                    "mac": iface.get("address", ""),
                    "addresses": [
                        {"ip": a.get("local", ""), "prefix": a.get("prefixlen")}
                        for a in iface.get("addr_info", [])
                    ],
                    "source_path": "ip addr"
                })
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            pass
        return interfaces

    # ── SSH ───────────────────────────────────────────────────────────────

    def scan_ssh(self) -> list:
        """SSH-Konfiguration scannen."""
        configs = []
        sshd_config = Path("/etc/ssh/sshd_config")
        if sshd_config.exists():
            try:
                content = sshd_config.read_text(errors="replace")
                settings = {}
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        parts = line.split(None, 1)
                        if len(parts) == 2:
                            settings[parts[0]] = parts[1]
                configs.append({
                    "name": "sshd_config", "source_path": str(sshd_config),
                    "port": settings.get("Port", "22"),
                    "permit_root": settings.get("PermitRootLogin", "yes"),
                    "password_auth": settings.get("PasswordAuthentication", "yes"),
                    "pubkey_auth": settings.get("PubkeyAuthentication", "yes"),
                })
            except PermissionError:
                pass
        return configs

    # ── Systemd Services ─────────────────────────────────────────────────

    def scan_systemd_services(self) -> list:
        """Aktive systemd-Services scannen."""
        services = []
        try:
            result = subprocess.run(
                ["systemctl", "list-units", "--type=service", "--state=running", "--no-pager", "--plain", "-q"],
                capture_output=True, text=True, timeout=10
            )
            for line in result.stdout.strip().splitlines():
                parts = line.split()
                if parts and parts[0].endswith(".service"):
                    services.append({
                        "name": parts[0], "state": "running",
                        "source_path": "systemctl"
                    })
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return services[:50]  # Max 50

    # ── fstab ────────────────────────────────────────────────────────────

    def scan_fstab(self) -> list:
        """Festplatten-Mounts aus /etc/fstab scannen."""
        mounts = []
        fstab = Path("/etc/fstab")
        if fstab.exists():
            try:
                for line in fstab.read_text().splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        parts = line.split()
                        if len(parts) >= 4:
                            mounts.append({
                                "name": parts[1], "device": parts[0],
                                "mount_point": parts[1], "fs_type": parts[2],
                                "options": parts[3], "source_path": "/etc/fstab"
                            })
            except PermissionError:
                pass
        return mounts

    # ── DNS ──────────────────────────────────────────────────────────────

    def scan_dns(self) -> list:
        """DNS-Konfiguration scannen."""
        configs = []
        resolv = Path("/etc/resolv.conf")
        if resolv.exists():
            try:
                content = resolv.read_text(errors="replace")
                nameservers = re.findall(r"nameserver\s+(\S+)", content)
                search = re.findall(r"search\s+(.+)", content)
                configs.append({
                    "name": "resolv.conf", "nameservers": nameservers,
                    "search_domains": search[0].split() if search else [],
                    "source_path": "/etc/resolv.conf", "raw": content
                })
            except PermissionError:
                pass
        return configs

    # ── Hosts ────────────────────────────────────────────────────────────

    def scan_hosts(self) -> list:
        """/etc/hosts scannen."""
        entries = []
        hosts = Path("/etc/hosts")
        if hosts.exists():
            try:
                for line in hosts.read_text().splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        parts = line.split()
                        if len(parts) >= 2:
                            entries.append({
                                "name": parts[1], "ip": parts[0],
                                "aliases": parts[2:] if len(parts) > 2 else [],
                                "source_path": "/etc/hosts"
                            })
            except PermissionError:
                pass
        return entries

    # ── Cron ─────────────────────────────────────────────────────────────

    def scan_cron(self) -> list:
        """Cron-Jobs scannen."""
        jobs = []
        try:
            result = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=5)
            for line in result.stdout.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    jobs.append({"name": line[:50], "schedule": line, "source_path": "crontab -l"})
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # System cron
        for cron_dir in ["/etc/cron.d", "/etc/cron.daily", "/etc/cron.hourly"]:
            cron_path = Path(cron_dir)
            if cron_path.exists():
                for f in cron_path.iterdir():
                    if f.is_file():
                        jobs.append({"name": f.name, "source_path": str(f), "type": cron_path.name})
        return jobs

    # ── Status ───────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        """Import-Status abrufen."""
        rows = self.db_query(
            """SELECT config_type, COUNT(*) AS count,
                      MAX(imported_at) AS last_import
               FROM dbai_core.system_config
               GROUP BY config_type ORDER BY config_type"""
        )
        return {"configs": rows, "total": sum(r["count"] for r in rows)}
