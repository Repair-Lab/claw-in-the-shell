#!/usr/bin/env python3
"""
DBAI Hardware Scanner — Liest physische Hardware und schreibt sie in die Datenbank.

Beim Systemstart aufgerufen: Scannt CPU, GPU, Storage, Memory, Netzwerk, Lüfter
und registriert alles in dbai_system.hardware_inventory sowie den Detail-Tabellen.

Nutzt:
  - psutil:     CPU, RAM, Disk, Netzwerk (Standard)
  - subprocess: lspci, lsblk, smartctl, sensors (Linux-Tools)
  - pynvml:     NVIDIA GPU (optional, Fallback: nvidia-smi CLI)

Verwendung:
  python3 -m bridge.hardware_scanner          # Einmal scannen
  python3 -m bridge.hardware_scanner --daemon  # Periodisch scannen
"""

import json
import logging
import os
import platform
import re
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import psycopg2
    import psycopg2.extras

    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

# ─── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [HW-SCANNER] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("hardware_scanner")

# ─── Konfiguration ───────────────────────────────────────────────────────────

DB_NAME = os.environ.get("DBAI_DB_NAME", "dbai")
DB_USER = os.environ.get("DBAI_DB_USER", "dbai_system")
DB_HOST = os.environ.get("DBAI_DB_HOST", "127.0.0.1")
DB_PORT = os.environ.get("DBAI_DB_PORT", "5432")

SCAN_INTERVAL_SEC = int(os.environ.get("DBAI_HW_SCAN_INTERVAL", "5"))


def _run_cmd(cmd: List[str], timeout: int = 10) -> Optional[str]:
    """Führt einen Shell-Befehl aus und gibt stdout zurück."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


class HardwareScanner:
    """Scannt physische Hardware und schreibt in die Datenbank."""

    def __init__(self, db_conn=None):
        self.conn = db_conn
        self._inventory_cache: Dict[str, str] = {}  # device_key → UUID

    def connect(self):
        """Verbindung zur Datenbank herstellen."""
        if not HAS_PSYCOPG2:
            log.error("psycopg2 nicht installiert!")
            return False
        try:
            self.conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER, host=DB_HOST, port=DB_PORT
            )
            self.conn.autocommit = True
            log.info(f"Verbunden mit {DB_NAME}@{DB_HOST}:{DB_PORT}")
            return True
        except Exception as e:
            log.error(f"DB-Verbindung fehlgeschlagen: {e}")
            return False

    def _upsert_inventory(
        self,
        device_class: str,
        device_name: str,
        vendor: str = None,
        model: str = None,
        serial_number: str = None,
        pci_address: str = None,
        driver_name: str = None,
        driver_version: str = None,
        firmware_version: str = None,
        capabilities: dict = None,
        properties: dict = None,
    ) -> Optional[str]:
        """Hardware-Gerät in Inventar eintragen oder aktualisieren."""
        if not self.conn:
            return None

        cache_key = f"{device_class}:{device_name}:{pci_address or serial_number or ''}"
        if cache_key in self._inventory_cache:
            # Update last_seen
            try:
                with self.conn.cursor() as cur:
                    cur.execute(
                        "UPDATE dbai_system.hardware_inventory SET last_seen = now(), "
                        "status = 'active' WHERE id = %s",
                        (self._inventory_cache[cache_key],),
                    )
                return self._inventory_cache[cache_key]
            except Exception:
                pass

        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO dbai_system.hardware_inventory
                        (device_class, device_name, vendor, model, serial_number,
                         pci_address, driver_name, driver_version, firmware_version,
                         capabilities, properties, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'active')
                    ON CONFLICT DO NOTHING
                    RETURNING id
                    """,
                    (
                        device_class,
                        device_name,
                        vendor,
                        model,
                        serial_number,
                        pci_address,
                        driver_name,
                        driver_version,
                        firmware_version,
                        json.dumps(capabilities or {}),
                        json.dumps(properties or {}),
                    ),
                )
                row = cur.fetchone()
                if row:
                    hw_id = str(row[0])
                    self._inventory_cache[cache_key] = hw_id
                    return hw_id
                # Falls CONFLICT: existierenden Eintrag finden
                cur.execute(
                    "SELECT id FROM dbai_system.hardware_inventory "
                    "WHERE device_class = %s AND device_name = %s "
                    "ORDER BY created_at DESC LIMIT 1",
                    (device_class, device_name),
                )
                row = cur.fetchone()
                if row:
                    hw_id = str(row[0])
                    self._inventory_cache[cache_key] = hw_id
                    return hw_id
        except Exception as e:
            log.warning(f"Inventar-Eintrag fehlgeschlagen für {device_name}: {e}")
        return None

    # ─── CPU Scanner ─────────────────────────────────────────────────────

    def scan_cpu(self) -> Dict[str, Any]:
        """CPU-Informationen auslesen und in Hardware-Inventar + cpu_cores schreiben."""
        cpu_info = {
            "vendor": "unknown",
            "model": "unknown",
            "cores_physical": 0,
            "cores_logical": 0,
            "architecture": platform.machine(),
            "frequency_mhz": 0,
        }

        # /proc/cpuinfo lesen (Linux)
        cpuinfo_path = Path("/proc/cpuinfo")
        if cpuinfo_path.exists():
            content = cpuinfo_path.read_text()
            for line in content.split("\n"):
                if "model name" in line:
                    cpu_info["model"] = line.split(":")[1].strip()
                elif "vendor_id" in line:
                    cpu_info["vendor"] = line.split(":")[1].strip()
                elif "cpu MHz" in line:
                    try:
                        cpu_info["frequency_mhz"] = int(float(line.split(":")[1].strip()))
                    except ValueError:
                        pass

        if HAS_PSUTIL:
            cpu_info["cores_physical"] = psutil.cpu_count(logical=False) or 0
            cpu_info["cores_logical"] = psutil.cpu_count(logical=True) or 0
            freq = psutil.cpu_freq()
            if freq:
                cpu_info["frequency_max_mhz"] = int(freq.max) if freq.max else 0
                cpu_info["frequency_min_mhz"] = int(freq.min) if freq.min else 0

        # CPU-Features erkennen (AVX2, AVX-512, etc.)
        flags = []
        if cpuinfo_path.exists():
            content = cpuinfo_path.read_text()
            for line in content.split("\n"):
                if line.startswith("flags"):
                    flags = line.split(":")[1].strip().split()
                    break

        capabilities = {
            "avx": "avx" in flags,
            "avx2": "avx2" in flags,
            "avx512f": "avx512f" in flags,
            "sse4_2": "sse4_2" in flags,
            "aes": "aes" in flags,
            "fma": "fma" in flags,
        }

        log.info(
            f"CPU: {cpu_info['model']} — {cpu_info['cores_physical']}C/"
            f"{cpu_info['cores_logical']}T @ {cpu_info.get('frequency_max_mhz', '?')}MHz"
        )

        # In Hardware-Inventar schreiben
        hw_id = self._upsert_inventory(
            device_class="cpu",
            device_name=cpu_info["model"],
            vendor=cpu_info["vendor"],
            model=cpu_info["model"],
            capabilities=capabilities,
            properties=cpu_info,
        )

        # Per-Core Daten schreiben
        if HAS_PSUTIL and self.conn:
            try:
                per_cpu = psutil.cpu_percent(interval=0.1, percpu=True)
                freq_per_cpu = psutil.cpu_freq(percpu=True) or []
                temps = {}
                try:
                    sensors = psutil.sensors_temperatures()
                    for chip, entries in sensors.items():
                        if "coretemp" in chip.lower() or "k10temp" in chip.lower():
                            for entry in entries:
                                core_match = re.search(r"(\d+)", entry.label or "")
                                if core_match:
                                    temps[int(core_match.group(1))] = entry.current
                except Exception:
                    pass

                with self.conn.cursor() as cur:
                    # Alte Einträge löschen
                    cur.execute("DELETE FROM dbai_system.cpu_cores WHERE hw_inventory_id = %s", (hw_id,))

                    for i, usage in enumerate(per_cpu):
                        freq = freq_per_cpu[i] if i < len(freq_per_cpu) else None
                        cur.execute(
                            """
                            INSERT INTO dbai_system.cpu_cores
                                (hw_inventory_id, core_id, physical_core, usage_percent,
                                 frequency_mhz, frequency_max_mhz, temperature_c, is_online)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
                            """,
                            (
                                hw_id,
                                i,
                                i // 2 if cpu_info["cores_logical"] > cpu_info["cores_physical"] else i,
                                usage,
                                int(freq.current) if freq else 0,
                                int(freq.max) if freq and freq.max else 0,
                                temps.get(i),
                            ),
                        )
            except Exception as e:
                log.warning(f"CPU-Core-Daten fehlgeschlagen: {e}")

        # System Capabilities aktualisieren
        if self.conn:
            try:
                with self.conn.cursor() as cur:
                    for cap in ["avx2", "avx512f"]:
                        cap_name = cap.replace("f", "") if cap == "avx512f" else cap
                        cur.execute(
                            "UPDATE dbai_core.system_capabilities "
                            "SET is_available = %s, details = %s, last_verified = now() "
                            "WHERE capability = %s",
                            (capabilities.get(cap, False), json.dumps(cpu_info), cap_name),
                        )
            except Exception as e:
                log.warning(f"System-Capabilities-Update fehlgeschlagen: {e}")

        return cpu_info

    # ─── Memory Scanner ──────────────────────────────────────────────────

    def scan_memory(self) -> Dict[str, Any]:
        """RAM-Informationen auslesen."""
        mem_info = {"total_mb": 0, "used_mb": 0, "free_mb": 0, "swap_total_mb": 0}

        if HAS_PSUTIL:
            vm = psutil.virtual_memory()
            mem_info = {
                "total_mb": vm.total // (1024 * 1024),
                "used_mb": vm.used // (1024 * 1024),
                "free_mb": vm.available // (1024 * 1024),
                "cached_mb": getattr(vm, "cached", 0) // (1024 * 1024),
                "buffers_mb": getattr(vm, "buffers", 0) // (1024 * 1024),
                "percent": vm.percent,
            }
            swap = psutil.swap_memory()
            mem_info["swap_total_mb"] = swap.total // (1024 * 1024)
            mem_info["swap_used_mb"] = swap.used // (1024 * 1024)

        log.info(
            f"RAM: {mem_info['total_mb']}MB total, "
            f"{mem_info['used_mb']}MB used, {mem_info['free_mb']}MB free"
        )

        # In Inventar
        self._upsert_inventory(
            device_class="memory",
            device_name=f"System RAM ({mem_info['total_mb']}MB)",
            properties=mem_info,
            capabilities={"ecc": self._check_ecc_ram()},
        )

        # Memory-Map: Top-Prozesse
        if HAS_PSUTIL and self.conn:
            try:
                with self.conn.cursor() as cur:
                    cur.execute("DELETE FROM dbai_system.memory_map")

                    for proc in psutil.process_iter(["pid", "name", "memory_info", "cpu_percent", "num_threads"]):
                        try:
                            info = proc.info
                            mem = info.get("memory_info")
                            if not mem or mem.rss < 1024 * 1024:  # < 1MB ignorieren
                                continue

                            # Prozess-Typ erkennen
                            pname = (info.get("name") or "").lower()
                            if "postgres" in pname:
                                ptype = "postgresql"
                            elif "python" in pname or "llama" in pname:
                                ptype = "ghost"
                            elif "uvicorn" in pname or "fastapi" in pname:
                                ptype = "bridge"
                            else:
                                ptype = "system"

                            cur.execute(
                                """
                                INSERT INTO dbai_system.memory_map
                                    (pid, process_name, process_type, rss_mb, vms_mb,
                                     shared_mb, cpu_percent, num_threads)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                """,
                                (
                                    info["pid"],
                                    info["name"],
                                    ptype,
                                    mem.rss / (1024 * 1024),
                                    mem.vms / (1024 * 1024),
                                    getattr(mem, "shared", 0) / (1024 * 1024),
                                    info.get("cpu_percent", 0),
                                    info.get("num_threads", 1),
                                ),
                            )
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue
            except Exception as e:
                log.warning(f"Memory-Map fehlgeschlagen: {e}")

        # ECC-RAM Capability
        if self.conn:
            try:
                with self.conn.cursor() as cur:
                    cur.execute(
                        "UPDATE dbai_core.system_capabilities "
                        "SET is_available = %s, details = %s, last_verified = now() "
                        "WHERE capability = 'ecc_ram'",
                        (self._check_ecc_ram(), json.dumps(mem_info)),
                    )
            except Exception:
                pass

        return mem_info

    def _check_ecc_ram(self) -> bool:
        """Prüft ob ECC-RAM vorhanden ist."""
        result = _run_cmd(["dmidecode", "-t", "memory"])
        if result:
            return "Error Correcting Type: Multi-bit ECC" in result
        return False

    # ─── Storage Scanner ─────────────────────────────────────────────────

    def scan_storage(self) -> List[Dict[str, Any]]:
        """Speichermedien und SMART-Werte auslesen."""
        devices = []

        if HAS_PSUTIL:
            for part in psutil.disk_partitions(all=False):
                dev = {
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                }
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    dev["total_gb"] = usage.total / (1024**3)
                    dev["used_gb"] = usage.used / (1024**3)
                    dev["free_gb"] = usage.free / (1024**3)
                    dev["percent"] = usage.percent
                except PermissionError:
                    pass
                devices.append(dev)

        # lsblk für Details
        lsblk = _run_cmd(["lsblk", "-J", "-o", "NAME,SIZE,TYPE,MODEL,SERIAL,ROTA,TRAN"])
        if lsblk:
            try:
                data = json.loads(lsblk)
                for blk in data.get("blockdevices", []):
                    if blk.get("type") == "disk":
                        dev_path = f"/dev/{blk['name']}"
                        dev_type = "hdd" if blk.get("rota") else "ssd"
                        if blk.get("tran") == "nvme":
                            dev_type = "nvme"

                        hw_id = self._upsert_inventory(
                            device_class="storage",
                            device_name=dev_path,
                            model=blk.get("model"),
                            serial_number=blk.get("serial"),
                            properties={"size": blk.get("size"), "type": dev_type, "transport": blk.get("tran")},
                        )

                        # SMART-Werte lesen
                        self._read_smart(dev_path, dev_type, hw_id, blk.get("model"), blk.get("serial"))

                        # NVMe Capability
                        if dev_type == "nvme" and self.conn:
                            try:
                                with self.conn.cursor() as cur:
                                    cur.execute(
                                        "UPDATE dbai_core.system_capabilities "
                                        "SET is_available = TRUE, last_verified = now() "
                                        "WHERE capability = 'nvme'"
                                    )
                            except Exception:
                                pass
            except json.JSONDecodeError:
                pass

        log.info(f"Storage: {len(devices)} Partitionen gefunden")
        return devices

    def _read_smart(self, device: str, dev_type: str, hw_id: str, model: str = None, serial: str = None):
        """SMART-Werte einer Festplatte lesen."""
        if not self.conn:
            return

        smart = _run_cmd(["smartctl", "-j", "-a", device])
        if not smart:
            return

        try:
            data = json.loads(smart)

            # SMART-Status
            smart_ok = data.get("smart_status", {}).get("passed", None)
            status = "healthy" if smart_ok else ("failing" if smart_ok is False else "unknown")

            temp = data.get("temperature", {}).get("current")
            power_on = data.get("power_on_time", {}).get("hours")
            power_cycles = data.get("power_cycle_count")

            # SMART-Attribute parsen
            reallocated = 0
            pending = 0
            uncorrectable = 0
            wear = None

            for attr in data.get("ata_smart_attributes", {}).get("table", []):
                attr_id = attr.get("id")
                raw = attr.get("raw", {}).get("value", 0)
                if attr_id == 5:    # Reallocated Sectors
                    reallocated = raw
                    if raw > 0:
                        status = "warning" if raw < 10 else "critical"
                elif attr_id == 197:  # Current Pending Sectors
                    pending = raw
                elif attr_id == 198:  # Uncorrectable Errors
                    uncorrectable = raw

            # NVMe Wear
            nvme_spare = None
            if "nvme_smart_health_information_log" in data:
                nvme_log = data["nvme_smart_health_information_log"]
                wear = nvme_log.get("percentage_used", 0)
                nvme_spare = nvme_log.get("available_spare")

            # Risk-Score berechnen
            risk = 0.0
            risk += min(reallocated * 10.0, 40.0)
            risk += min(pending * 5.0, 20.0)
            risk += min(uncorrectable * 15.0, 30.0)
            if wear and wear > 80:
                risk += (wear - 80) * 2.0
            risk = min(risk, 100.0)

            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO dbai_system.storage_health
                        (hw_inventory_id, device_path, device_type, model, serial, firmware,
                         smart_status, temperature_c, power_on_hours, power_cycle_count,
                         reallocated_sectors, pending_sectors, uncorrectable_errors,
                         wear_level_percent, nvme_spare_percent, risk_score)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        hw_id, device, dev_type, model, serial,
                        data.get("firmware_version"),
                        status, temp, power_on, power_cycles,
                        reallocated, pending, uncorrectable,
                        wear, nvme_spare, risk,
                    ),
                )

            if risk > 50:
                log.warning(f"STORAGE WARNUNG: {device} Risk-Score={risk:.0f}% "
                            f"(Reallocated={reallocated}, Pending={pending})")
        except (json.JSONDecodeError, KeyError) as e:
            log.warning(f"SMART-Parsing fehlgeschlagen für {device}: {e}")

    # ─── Network Scanner ─────────────────────────────────────────────────

    def scan_network(self) -> List[Dict[str, Any]]:
        """Netzwerk-Interfaces und aktive Verbindungen."""
        interfaces = []

        if HAS_PSUTIL:
            addrs = psutil.net_if_addrs()
            stats = psutil.net_if_stats()

            for name, addr_list in addrs.items():
                if name == "lo":
                    continue

                iface = {"name": name, "addresses": []}
                for addr in addr_list:
                    if addr.family == socket.AF_INET:
                        iface["ipv4"] = addr.address
                    iface["addresses"].append({"family": str(addr.family), "address": addr.address})

                if name in stats:
                    st = stats[name]
                    iface["is_up"] = st.isup
                    iface["speed_mbps"] = st.speed
                    iface["mtu"] = st.mtu

                interfaces.append(iface)

                self._upsert_inventory(
                    device_class="network",
                    device_name=name,
                    properties=iface,
                    capabilities={"speed_10g": iface.get("speed_mbps", 0) >= 10000},
                )

                # 10GbE Capability
                if iface.get("speed_mbps", 0) >= 10000 and self.conn:
                    try:
                        with self.conn.cursor() as cur:
                            cur.execute(
                                "UPDATE dbai_core.system_capabilities "
                                "SET is_available = TRUE, last_verified = now() "
                                "WHERE capability = '10gbe'"
                            )
                    except Exception:
                        pass

            # Aktive Verbindungen
            if self.conn:
                try:
                    with self.conn.cursor() as cur:
                        cur.execute("DELETE FROM dbai_system.network_connections")
                        for conn in psutil.net_connections(kind="inet"):
                            try:
                                cur.execute(
                                    """
                                    INSERT INTO dbai_system.network_connections
                                        (local_address, local_port, remote_address, remote_port,
                                         protocol, status, pid)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                                    """,
                                    (
                                        conn.laddr.ip if conn.laddr else None,
                                        conn.laddr.port if conn.laddr else None,
                                        conn.raddr.ip if conn.raddr else None,
                                        conn.raddr.port if conn.raddr else None,
                                        "tcp" if conn.type == socket.SOCK_STREAM else "udp",
                                        conn.status,
                                        conn.pid,
                                    ),
                                )
                            except Exception:
                                continue
                except Exception as e:
                    log.warning(f"Netzwerk-Verbindungen fehlgeschlagen: {e}")

        log.info(f"Netzwerk: {len(interfaces)} Interfaces gefunden")
        return interfaces

    # ─── Fan Scanner ──────────────────────────────────────────────────────

    def scan_fans(self):
        """Lüfter auslesen und in fan_control schreiben."""
        if not HAS_PSUTIL or not self.conn:
            return

        try:
            fans = psutil.sensors_fans()
            if not fans:
                return

            for chip, fan_list in fans.items():
                for fan in fan_list:
                    fan_name = f"{chip}_{fan.label}" if fan.label else f"{chip}_fan"

                    hw_id = self._upsert_inventory(
                        device_class="fan",
                        device_name=fan_name,
                        vendor=chip,
                        properties={"current_rpm": fan.current},
                    )

                    try:
                        with self.conn.cursor() as cur:
                            cur.execute(
                                """
                                INSERT INTO dbai_system.fan_control
                                    (hw_inventory_id, fan_name, fan_type, current_rpm, is_controllable)
                                VALUES (%s, %s, %s, %s, FALSE)
                                ON CONFLICT DO NOTHING
                                """,
                                (hw_id, fan_name, "cpu" if "cpu" in fan_name.lower() else "chassis", fan.current),
                            )
                    except Exception:
                        pass

            log.info(f"Fans: {sum(len(f) for f in fans.values())} Lüfter gefunden")
        except Exception as e:
            log.warning(f"Fan-Scan fehlgeschlagen: {e}")

    # ─── Motherboard Scanner ──────────────────────────────────────────────

    def scan_motherboard(self):
        """Motherboard-Info aus DMI-Daten."""
        board = _run_cmd(["cat", "/sys/devices/virtual/dmi/id/board_name"])
        vendor = _run_cmd(["cat", "/sys/devices/virtual/dmi/id/board_vendor"])
        bios = _run_cmd(["cat", "/sys/devices/virtual/dmi/id/bios_version"])

        if board:
            self._upsert_inventory(
                device_class="motherboard",
                device_name=board,
                vendor=vendor,
                firmware_version=bios,
                properties={
                    "board_name": board,
                    "board_vendor": vendor,
                    "bios_version": bios,
                    "hostname": socket.gethostname(),
                    "kernel": platform.release(),
                    "os": platform.platform(),
                },
            )
            log.info(f"Mainboard: {vendor} {board} (BIOS: {bios})")

    # ─── PCI-Geräte Scanner ──────────────────────────────────────────────

    def scan_pci_devices(self):
        """Alle PCI-Geräte via lspci scannen."""
        lspci = _run_cmd(["lspci", "-mm", "-nn"])
        if not lspci:
            return

        for line in lspci.split("\n"):
            if not line.strip():
                continue
            # Parse lspci -mm format
            parts = re.findall(r'"([^"]*)"', line)
            if len(parts) >= 3:
                pci_addr = line.split()[0] if line.split() else ""
                device_class = parts[0] if parts else ""
                vendor = parts[1] if len(parts) > 1 else ""
                device = parts[2] if len(parts) > 2 else ""

                self._upsert_inventory(
                    device_class="pci",
                    device_name=device,
                    vendor=vendor,
                    pci_address=pci_addr,
                    properties={"pci_class": device_class},
                )

    # ─── Vollständiger Scan ──────────────────────────────────────────────

    def full_scan(self) -> Dict[str, Any]:
        """Führt einen kompletten Hardware-Scan durch."""
        log.info("=" * 60)
        log.info("DBAI Hardware-Scan gestartet")
        log.info("=" * 60)
        start = time.time()

        results = {}

        # 1. Motherboard zuerst
        self.scan_motherboard()

        # 2. CPU
        results["cpu"] = self.scan_cpu()

        # 3. Memory
        results["memory"] = self.scan_memory()

        # 4. Storage + SMART
        results["storage"] = self.scan_storage()

        # 5. Netzwerk
        results["network"] = self.scan_network()

        # 6. Lüfter
        self.scan_fans()

        # 7. PCI-Geräte (für Hot-Plug Erkennung)
        self.scan_pci_devices()

        elapsed = time.time() - start
        device_count = len(self._inventory_cache)
        log.info("=" * 60)
        log.info(f"Hardware-Scan abgeschlossen: {device_count} Geräte in {elapsed:.1f}s")
        log.info("=" * 60)

        # NOTIFY: Hardware-Scan fertig
        if self.conn:
            try:
                with self.conn.cursor() as cur:
                    cur.execute(
                        "SELECT pg_notify('hardware_scan_complete', %s)",
                        (json.dumps({"device_count": device_count, "scan_time_sec": round(elapsed, 2)}),),
                    )
            except Exception:
                pass

        return results

    def daemon_loop(self):
        """Periodischer Scan-Loop."""
        log.info(f"Hardware-Scanner Daemon gestartet (Intervall: {SCAN_INTERVAL_SEC}s)")

        running = True

        def stop_handler(sig, frame):
            nonlocal running
            log.info("Stop-Signal empfangen, beende Daemon...")
            running = False

        signal.signal(signal.SIGTERM, stop_handler)
        signal.signal(signal.SIGINT, stop_handler)

        # Erster vollständiger Scan
        self.full_scan()

        # Danach nur periodische Updates (leichtgewichtig)
        while running:
            try:
                time.sleep(SCAN_INTERVAL_SEC)
                if not running:
                    break

                # Leichtgewichtiger Periodic-Scan
                if HAS_PSUTIL:
                    self.scan_cpu()  # CPU-Cores aktualisieren
                    self.scan_memory()  # Memory-Map aktualisieren

            except Exception as e:
                log.error(f"Daemon-Fehler: {e}")
                time.sleep(5)

        log.info("Hardware-Scanner Daemon beendet")

    def close(self):
        """Datenbankverbindung schließen."""
        if self.conn:
            self.conn.close()


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    scanner = HardwareScanner()

    if not scanner.connect():
        log.error("Kann nicht ohne Datenbankverbindung arbeiten.")
        log.info("Führe Scan trotzdem aus (nur Ausgabe, kein DB-Write)...")
        scanner.conn = None

    try:
        if "--daemon" in sys.argv:
            scanner.daemon_loop()
        else:
            results = scanner.full_scan()
            if "--json" in sys.argv:
                print(json.dumps(results, indent=2, default=str))
    finally:
        scanner.close()


if __name__ == "__main__":
    main()
