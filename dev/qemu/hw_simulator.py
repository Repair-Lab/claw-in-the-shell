#!/usr/bin/env python3
"""
DBAI QEMU Hardware-Simulator
==============================
Emuliert x86-Hardware-Schichten und injiziert synthetische Daten
in die dbai_system.*-Tabellen (cpu, memory, disk, temperature, network).

Features:
- Startet QEMU-VMs mit konfigurierbarer Hardware
- Liest QMP-Daten (QEMU Machine Protocol) aus den VMs
- Generiert realistische Hardware-Metriken mit Rauschen
- Injiziert Daten in PostgreSQL (wie ein echter Scanner)
- Simuliert Fehlerzustände (Overtemp, Disk-Failure, etc.)
- REST-API zur Steuerung der Simulation

Wird sowohl standalone als auch im Docker-Container genutzt.
"""

import os
import json
import math
import random
import time
import uuid
import signal
import socket
import struct
import logging
import threading
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("dbai.hw-simulator")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")


# ─── Konfiguration ───────────────────────────────────────────────

DB_CONFIG = {
    "host": os.getenv("DBAI_DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DBAI_DB_PORT", "5432")),
    "dbname": os.getenv("DBAI_DB_NAME", "dbai"),
    "user": os.getenv("DBAI_DB_USER", "dbai_system"),
    "password": os.getenv("DBAI_DB_PASSWORD", ""),
}

QEMU_CORES = int(os.getenv("QEMU_CORES", "4"))
QEMU_MEMORY = int(os.getenv("QEMU_MEMORY", "2048"))
QEMU_DISKS = int(os.getenv("QEMU_DISKS", "2"))
QEMU_NICS = int(os.getenv("QEMU_NICS", "1"))
INJECT_INTERVAL = float(os.getenv("INJECT_INTERVAL", "2.0"))
USE_REAL_QEMU = os.getenv("USE_REAL_QEMU", "false").lower() == "true"


# ─── Hardware-Profile ────────────────────────────────────────────

@dataclass
class HardwareProfile:
    """Definiert eine simulierte Hardware-Konfiguration."""
    name: str = "DBAI Virtual Machine"
    cpu_model: str = "Intel Core i7-13700K (Emulated)"
    cpu_cores: int = 4
    cpu_threads: int = 8
    cpu_base_freq: int = 3400        # MHz
    cpu_boost_freq: int = 5400       # MHz
    ram_total_mb: int = 2048
    ram_type: str = "DDR4-3200"
    disks: list = field(default_factory=lambda: [
        {"device": "/dev/vda", "model": "QEMU HARDDISK 0", "size_gb": 64,
         "type": "SSD", "mount": "/", "fs": "ext4"},
        {"device": "/dev/vdb", "model": "QEMU HARDDISK 1", "size_gb": 256,
         "type": "HDD", "mount": "/data", "fs": "xfs"},
    ])
    nics: list = field(default_factory=lambda: [
        {"interface": "eth0", "mac": "52:54:00:12:34:56",
         "driver": "virtio-net", "speed": 1000},
    ])
    gpu: Optional[dict] = None
    motherboard: str = "QEMU Standard PC (Q35 + ICH9, 2009)"
    bios: str = "OVMF (UEFI)"
    sensors: list = field(default_factory=lambda: [
        {"name": "cpu_package", "type": "cpu", "base_temp": 45.0, "max_temp": 100.0},
        {"name": "cpu_core0", "type": "cpu", "base_temp": 42.0, "max_temp": 100.0},
        {"name": "cpu_core1", "type": "cpu", "base_temp": 43.0, "max_temp": 100.0},
        {"name": "mobo_vrm", "type": "mobo", "base_temp": 38.0, "max_temp": 85.0},
        {"name": "disk_vda", "type": "disk", "base_temp": 32.0, "max_temp": 70.0},
    ])


# ─── Simulations-State ──────────────────────────────────────────

@dataclass
class SimulationState:
    """Hält den Zustand der laufenden Hardware-Simulation."""
    running: bool = False
    tick: int = 0
    cpu_load: list = field(default_factory=list)      # Pro Core
    cpu_freq: list = field(default_factory=list)       # Pro Core MHz
    memory_used_mb: int = 0
    memory_cached_mb: int = 0
    swap_used_mb: int = 0
    disk_io: dict = field(default_factory=dict)        # {device: {read_bps, write_bps}}
    net_io: dict = field(default_factory=dict)          # {iface: {rx_bps, tx_bps}}
    temperatures: dict = field(default_factory=dict)    # {sensor: temp}
    anomaly_active: Optional[str] = None               # None, "overtemp", "disk_fail", "mem_leak"
    qemu_pid: Optional[int] = None
    uptime_seconds: float = 0


# ─── Haupt-Simulator ────────────────────────────────────────────

class HardwareSimulator:
    """QEMU/KVM-basierter Hardware-Simulator für GhostShell OS."""

    def __init__(self, profile: HardwareProfile = None):
        self.profile = profile or self._create_profile()
        self.state = SimulationState()
        self._init_state()
        self._db_conn = None
        self._lock = threading.Lock()
        self._inject_thread = None
        self._qemu_process = None
        self.qemu_log = []

    def _create_profile(self) -> HardwareProfile:
        """Erstellt ein Profil basierend auf Umgebungsvariablen."""
        disks = []
        for i in range(QEMU_DISKS):
            disks.append({
                "device": f"/dev/vd{chr(97 + i)}",
                "model": f"QEMU HARDDISK {i}",
                "size_gb": [64, 256, 512, 1024][i % 4],
                "type": "SSD" if i == 0 else "HDD",
                "mount": "/" if i == 0 else f"/data{i}",
                "fs": "ext4" if i == 0 else "xfs",
            })
        nics = []
        for i in range(QEMU_NICS):
            nics.append({
                "interface": f"eth{i}",
                "mac": f"52:54:00:12:34:{56 + i:02x}",
                "driver": "virtio-net",
                "speed": 1000,
            })
        return HardwareProfile(
            cpu_cores=QEMU_CORES,
            cpu_threads=QEMU_CORES * 2,
            ram_total_mb=QEMU_MEMORY,
            disks=disks,
            nics=nics,
        )

    def _init_state(self):
        """Initialisiert den Simulations-State."""
        n_cores = self.profile.cpu_threads
        self.state.cpu_load = [random.uniform(1.0, 15.0) for _ in range(n_cores)]
        self.state.cpu_freq = [self.profile.cpu_base_freq for _ in range(n_cores)]
        self.state.memory_used_mb = int(self.profile.ram_total_mb * 0.35)
        self.state.memory_cached_mb = int(self.profile.ram_total_mb * 0.15)
        self.state.swap_used_mb = 0

        for d in self.profile.disks:
            self.state.disk_io[d["device"]] = {
                "read_bps": 0, "write_bps": 0,
                "read_iops": 0, "write_iops": 0,
                "used_pct": random.uniform(15.0, 55.0),
            }
        for n in self.profile.nics:
            self.state.net_io[n["interface"]] = {
                "rx_bps": 0, "tx_bps": 0,
                "rx_packets": 0, "tx_packets": 0,
                "state": "up",
            }
        for s in self.profile.sensors:
            self.state.temperatures[s["name"]] = s["base_temp"]

    # ─── QEMU VM Management ─────────────────────────────────────

    def start_qemu(self) -> dict:
        """Startet eine echte QEMU-VM (nur wenn USE_REAL_QEMU=true)."""
        if not USE_REAL_QEMU:
            logger.info("QEMU deaktiviert — reine Software-Simulation")
            return {"status": "simulation", "message": "Software-Simulation aktiv"}

        qemu_cmd = [
            "qemu-system-x86_64",
            "-machine", "q35,accel=kvm",
            "-cpu", "host",
            "-smp", f"cores={self.profile.cpu_cores},threads=2",
            "-m", str(self.profile.ram_total_mb),
            "-nographic",
            "-monitor", "unix:/tmp/qemu-monitor.sock,server,nowait",
            "-bios", "/usr/share/ovmf/OVMF.fd",
        ]

        # Virtuelle Disks
        for i, disk in enumerate(self.profile.disks):
            img_path = f"/var/lib/qemu/images/disk{i}.qcow2"
            if not Path(img_path).exists():
                subprocess.run([
                    "qemu-img", "create", "-f", "qcow2",
                    img_path, f"{disk['size_gb']}G"
                ], capture_output=True)
            qemu_cmd += [
                "-drive", f"file={img_path},format=qcow2,if=virtio,id=drive{i}"
            ]

        # Netzwerk-Interfaces
        for i, nic in enumerate(self.profile.nics):
            qemu_cmd += [
                "-netdev", f"user,id=net{i}",
                "-device", f"virtio-net-pci,netdev=net{i},mac={nic['mac']}"
            ]

        try:
            self._qemu_process = subprocess.Popen(
                qemu_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.state.qemu_pid = self._qemu_process.pid
            logger.info(f"QEMU-VM gestartet (PID: {self.state.qemu_pid})")
            return {"status": "running", "pid": self.state.qemu_pid}
        except Exception as e:
            logger.error(f"QEMU-Start fehlgeschlagen: {e}")
            return {"status": "error", "error": str(e)}

    def stop_qemu(self) -> dict:
        """Stoppt die QEMU-VM."""
        if self._qemu_process:
            self._qemu_process.terminate()
            try:
                self._qemu_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._qemu_process.kill()
            self.state.qemu_pid = None
            self._qemu_process = None
            logger.info("QEMU-VM gestoppt")
            return {"status": "stopped"}
        return {"status": "not_running"}

    # ─── Simulations-Engine ──────────────────────────────────────

    def tick(self):
        """Ein Simulations-Tick: Generiert neue Hardware-Daten."""
        with self._lock:
            self.state.tick += 1
            self.state.uptime_seconds += INJECT_INTERVAL
            t = self.state.tick

            # CPU-Last mit realistischem Rauschen
            for i in range(len(self.state.cpu_load)):
                base = 10.0 + 5.0 * math.sin(t * 0.05 + i * 0.7)
                noise = random.gauss(0, 3.0)
                burst = 30.0 if random.random() < 0.02 else 0  # Gelegentlicher Burst
                load = max(0.0, min(100.0, base + noise + burst))
                self.state.cpu_load[i] = round(load, 1)

                # Frequenz korreliert mit Last
                if load > 70:
                    freq = self.profile.cpu_boost_freq
                elif load > 30:
                    freq = self.profile.cpu_base_freq + int(
                        (self.profile.cpu_boost_freq - self.profile.cpu_base_freq) * (load / 100)
                    )
                else:
                    freq = self.profile.cpu_base_freq
                self.state.cpu_freq[i] = freq + random.randint(-50, 50)

            # Memory — langsamer Drift
            target = int(self.profile.ram_total_mb * random.uniform(0.3, 0.6))
            self.state.memory_used_mb += int((target - self.state.memory_used_mb) * 0.05)
            self.state.memory_cached_mb = int(self.profile.ram_total_mb * random.uniform(0.1, 0.25))

            # Disk I/O
            for dev, io in self.state.disk_io.items():
                io["read_bps"] = int(random.expovariate(1 / 500000))
                io["write_bps"] = int(random.expovariate(1 / 300000))
                io["read_iops"] = int(io["read_bps"] / max(1, random.randint(4096, 65536)))
                io["write_iops"] = int(io["write_bps"] / max(1, random.randint(4096, 65536)))
                io["used_pct"] = min(95.0, io["used_pct"] + random.gauss(0, 0.01))

            # Netzwerk
            for iface, nio in self.state.net_io.items():
                nio["rx_bps"] = int(random.expovariate(1 / 200000))
                nio["tx_bps"] = int(random.expovariate(1 / 100000))
                nio["rx_packets"] += nio["rx_bps"] // max(1, random.randint(64, 1500))
                nio["tx_packets"] += nio["tx_bps"] // max(1, random.randint(64, 1500))

            # Temperaturen — korrelieren mit CPU-Last
            avg_load = sum(self.state.cpu_load) / max(1, len(self.state.cpu_load))
            for sensor in self.profile.sensors:
                base = sensor["base_temp"]
                load_factor = (avg_load / 100.0) * 25.0
                noise = random.gauss(0, 0.5)
                temp = base + load_factor + noise
                self.state.temperatures[sensor["name"]] = round(
                    max(20.0, min(sensor["max_temp"], temp)), 1
                )

            # ─── Anomalie-Simulation ───
            if self.state.anomaly_active == "overtemp":
                for s in self.state.temperatures:
                    self.state.temperatures[s] += random.uniform(2.0, 8.0)
                    self.state.temperatures[s] = min(110.0, self.state.temperatures[s])

            elif self.state.anomaly_active == "disk_fail":
                first_dev = list(self.state.disk_io.keys())[0]
                self.state.disk_io[first_dev]["read_bps"] = 0
                self.state.disk_io[first_dev]["write_bps"] = 0
                self.state.disk_io[first_dev]["read_iops"] = 0
                self.state.disk_io[first_dev]["write_iops"] = 0

            elif self.state.anomaly_active == "mem_leak":
                self.state.memory_used_mb = min(
                    self.profile.ram_total_mb - 64,
                    self.state.memory_used_mb + random.randint(5, 20)
                )
                if self.state.memory_used_mb > self.profile.ram_total_mb * 0.9:
                    self.state.swap_used_mb += random.randint(10, 50)

            elif self.state.anomaly_active == "cpu_spike":
                for i in range(len(self.state.cpu_load)):
                    self.state.cpu_load[i] = min(100.0, 85.0 + random.uniform(0, 15))

            elif self.state.anomaly_active == "network_flood":
                for iface in self.state.net_io:
                    self.state.net_io[iface]["rx_bps"] = random.randint(50_000_000, 125_000_000)
                    self.state.net_io[iface]["tx_bps"] = random.randint(50_000_000, 125_000_000)

    # ─── Datenbank-Injektion ─────────────────────────────────────

    def inject_to_db(self):
        """Schreibt den aktuellen State in die dbai_system.*-Tabellen.

        Die Tabellen sind Zeitreihen (BIGSERIAL id + ts). Jeder Tick
        erzeugt neue Zeilen — kein UPSERT, reine INSERTs.
        """
        try:
            conn = self._get_conn()
            cur = conn.cursor()

            # CPU — ein Eintrag pro Core pro Tick
            for core_id in range(len(self.state.cpu_load)):
                load = self.state.cpu_load[core_id]
                temp = self.state.temperatures.get(
                    f"cpu_core{core_id}",
                    self.state.temperatures.get("cpu_package", 45.0))
                state = ("throttled" if load > 95
                         else "idle" if load < 5
                         else "online")
                cur.execute("""
                    INSERT INTO dbai_system.cpu
                        (core_id, usage_percent, frequency_mhz,
                         temperature_c, throttled, state)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    core_id,
                    load,
                    self.state.cpu_freq[core_id],
                    temp,
                    load > 95.0,
                    state,
                ))

            # Memory — eine Zeile pro Tick
            free_mb = max(0, self.profile.ram_total_mb
                          - self.state.memory_used_mb
                          - self.state.memory_cached_mb)
            usage_pct = round(self.state.memory_used_mb
                              / max(1, self.profile.ram_total_mb) * 100, 1)
            pressure = ("critical" if usage_pct > 90
                        else "warning" if usage_pct > 75
                        else "normal")
            cur.execute("""
                INSERT INTO dbai_system.memory
                    (total_mb, used_mb, free_mb, cached_mb, buffers_mb,
                     swap_total_mb, swap_used_mb, usage_percent, pressure_level)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                self.profile.ram_total_mb,
                self.state.memory_used_mb,
                free_mb,
                self.state.memory_cached_mb,
                int(self.profile.ram_total_mb * 0.03),   # buffers ~3%
                self.profile.ram_total_mb // 2,
                self.state.swap_used_mb,
                usage_pct,
                pressure,
            ))

            # Disks — eine Zeile pro Disk pro Tick
            for disk in self.profile.disks:
                dev = disk["device"]
                io = self.state.disk_io.get(dev, {})
                total_gb = float(disk["size_gb"])
                used_pct = io.get("used_pct", 30.0)
                used_gb = round(total_gb * used_pct / 100, 2)
                free_gb = round(total_gb - used_gb, 2)
                read_mbps = round(io.get("read_bps", 0) / 1_048_576, 2)
                write_mbps = round(io.get("write_bps", 0) / 1_048_576, 2)
                health = ("failing" if self.state.anomaly_active == "disk_fail"
                              and dev == self.profile.disks[0]["device"]
                          else "healthy")
                cur.execute("""
                    INSERT INTO dbai_system.disk
                        (device, mount_point, fs_type, total_gb, used_gb,
                         free_gb, usage_percent, read_iops, write_iops,
                         read_mbps, write_mbps, health_state)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    dev, disk["mount"], disk["fs"],
                    total_gb, used_gb, free_gb,
                    round(used_pct, 1),
                    io.get("read_iops", 0),
                    io.get("write_iops", 0),
                    read_mbps, write_mbps,
                    health,
                ))

            # Temperaturen — eine Zeile pro Sensor pro Tick
            for sensor in self.profile.sensors:
                temp = self.state.temperatures.get(sensor["name"], sensor["base_temp"])
                # sensor_type: mobo → motherboard (DB-CHECK constraint)
                stype = sensor["type"]
                if stype == "mobo":
                    stype = "motherboard"
                warning_c = round(sensor["max_temp"] * 0.8, 1)
                critical_c = round(sensor["max_temp"] * 0.95, 1)
                state = ("critical" if temp >= critical_c
                         else "hot" if temp >= warning_c
                         else "warm" if temp >= sensor["base_temp"] + 15
                         else "normal")
                cur.execute("""
                    INSERT INTO dbai_system.temperature
                        (sensor_name, sensor_type, temperature_c,
                         critical_c, warning_c, state)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    sensor["name"], stype, temp,
                    critical_c, warning_c, state,
                ))

            # Network — eine Zeile pro Interface pro Tick
            for nic in self.profile.nics:
                iface = nic["interface"]
                nio = self.state.net_io.get(iface, {})
                cur.execute("""
                    INSERT INTO dbai_system.network
                        (interface, state, mac_address,
                         rx_bytes, tx_bytes, rx_packets, tx_packets,
                         rx_errors, tx_errors, link_speed_mbps)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    iface, nio.get("state", "up"),
                    nic["mac"],
                    nio.get("rx_bps", 0) * int(max(1, self.state.uptime_seconds)),
                    nio.get("tx_bps", 0) * int(max(1, self.state.uptime_seconds)),
                    nio.get("rx_packets", 0),
                    nio.get("tx_packets", 0),
                    0,    # rx_errors
                    0,    # tx_errors
                    nic["speed"],
                ))

            conn.commit()

        except Exception as e:
            logger.error(f"DB-Injection fehlgeschlagen: {e}")
            if self._db_conn:
                try:
                    self._db_conn.rollback()
                except Exception:
                    pass
            self._db_conn = None

    # ─── Steuerung ───────────────────────────────────────────────

    def start(self):
        """Startet die Simulation inkl. periodischer DB-Injektion."""
        if self.state.running:
            return {"status": "already_running"}

        self.state.running = True
        logger.info(f"Hardware-Simulation gestartet — {self.profile.cpu_cores}C/"
                     f"{self.profile.ram_total_mb}MB/{len(self.profile.disks)}D")

        # QEMU starten (optional)
        qemu_result = self.start_qemu()
        self.qemu_log.append({"time": time.time(), **qemu_result})

        # Injections-Thread
        self._inject_thread = threading.Thread(
            target=self._inject_loop, daemon=True, name="hw-inject"
        )
        self._inject_thread.start()

        return {
            "status": "running",
            "profile": asdict(self.profile),
            "qemu": qemu_result,
        }

    def stop(self):
        """Stoppt die Simulation."""
        self.state.running = False
        self.stop_qemu()
        if self._db_conn:
            try:
                self._db_conn.close()
            except Exception:
                pass
            self._db_conn = None
        logger.info("Hardware-Simulation gestoppt")
        return {"status": "stopped"}

    def trigger_anomaly(self, anomaly_type: str) -> dict:
        """Aktiviert eine simulierte Hardware-Anomalie."""
        valid = ["overtemp", "disk_fail", "mem_leak", "cpu_spike", "network_flood", None]
        if anomaly_type not in valid:
            return {"error": f"Unbekannte Anomalie. Gültig: {valid}"}
        self.state.anomaly_active = anomaly_type
        logger.info(f"Anomalie {'aktiviert: ' + anomaly_type if anomaly_type else 'deaktiviert'}")
        return {"status": "ok", "anomaly": anomaly_type}

    def get_status(self) -> dict:
        """Gibt den aktuellen Simulations-Status zurück."""
        with self._lock:
            return {
                "running": self.state.running,
                "tick": self.state.tick,
                "uptime_seconds": round(self.state.uptime_seconds, 1),
                "anomaly_active": self.state.anomaly_active,
                "qemu_pid": self.state.qemu_pid,
                "profile": {
                    "name": self.profile.name,
                    "cpu": f"{self.profile.cpu_cores}C/{self.profile.cpu_threads}T @ {self.profile.cpu_base_freq}MHz",
                    "memory": f"{self.profile.ram_total_mb}MB {self.profile.ram_type}",
                    "disks": len(self.profile.disks),
                    "nics": len(self.profile.nics),
                },
                "current": {
                    "cpu_avg": round(sum(self.state.cpu_load) / max(1, len(self.state.cpu_load)), 1),
                    "cpu_per_core": self.state.cpu_load[:],
                    "memory_used_mb": self.state.memory_used_mb,
                    "memory_total_mb": self.profile.ram_total_mb,
                    "memory_pct": round(self.state.memory_used_mb / max(1, self.profile.ram_total_mb) * 100, 1),
                    "temperatures": dict(self.state.temperatures),
                    "disk_io": dict(self.state.disk_io),
                    "net_io": dict(self.state.net_io),
                },
            }

    # ─── Interne Helfer ──────────────────────────────────────────

    def _inject_loop(self):
        """Injiziert Daten in einer Endlosschleife."""
        while self.state.running:
            try:
                self.tick()
                self.inject_to_db()
            except Exception as e:
                logger.error(f"Injection-Loop-Fehler: {e}")
            time.sleep(INJECT_INTERVAL)

    def _get_conn(self):
        """Lazy DB-Verbindung."""
        if self._db_conn is None or self._db_conn.closed:
            self._db_conn = psycopg2.connect(**DB_CONFIG)
            self._db_conn.autocommit = False
        return self._db_conn


# ─── Singleton & Main ────────────────────────────────────────────

_simulator: Optional[HardwareSimulator] = None


def get_simulator() -> HardwareSimulator:
    global _simulator
    if _simulator is None:
        _simulator = HardwareSimulator()
    return _simulator


if __name__ == "__main__":
    sim = get_simulator()
    result = sim.start()
    logger.info(f"Simulator: {result}")

    # Graceful shutdown
    def _shutdown(sig, frame):
        sim.stop()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Keep alive
    try:
        while sim.state.running:
            time.sleep(5)
            s = sim.get_status()
            logger.info(
                f"Tick #{s['tick']} | CPU: {s['current']['cpu_avg']}% | "
                f"MEM: {s['current']['memory_pct']}% | "
                f"Anomalie: {s['anomaly_active'] or 'keine'}"
            )
    except (KeyboardInterrupt, SystemExit):
        pass
