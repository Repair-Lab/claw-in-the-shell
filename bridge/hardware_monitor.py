#!/usr/bin/env python3
"""
DBAI Hardware Monitor
=====================
Liest Hardware-Sensoren (CPU, RAM, Disk, Temperatur, Netzwerk)
und schreibt sie als INSERT-Befehle in die System-Tabellen.

Nutzt ctypes für C-Bindings bei Low-Level-Hardware-Zugriff.
"""

import os
import time
import ctypes
import logging
import threading
from pathlib import Path
from typing import Optional

import psycopg2

logger = logging.getLogger("dbai.hardware")

# ---------------------------------------------------------------------------
# Versuch, psutil zu importieren (Fallback auf /proc)
# ---------------------------------------------------------------------------
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    logger.warning("psutil nicht verfügbar — nutze /proc Fallback")


class HardwareMonitor:
    """
    Liest Hardware-Werte und schreibt sie in die System-Tabellen.
    """

    def __init__(self, conn, shutdown_event: threading.Event):
        self.conn = conn
        self.shutdown_event = shutdown_event
        self.c_lib = self._load_c_bindings()

    def _load_c_bindings(self) -> Optional[ctypes.CDLL]:
        """Versucht die C-Library für Hardware-Interrupts zu laden."""
        lib_path = Path(__file__).parent / "c_bindings" / "libhw_interrupts.so"
        if lib_path.exists():
            try:
                lib = ctypes.CDLL(str(lib_path))
                logger.info("C-Bindings geladen: %s", lib_path)
                return lib
            except OSError as e:
                logger.warning("C-Bindings laden fehlgeschlagen: %s", e)
        return None

    def _get_cursor(self):
        """Cursor erstellen, bei Bedarf Verbindung wiederherstellen."""
        if self.conn.closed:
            from system_bridge import DB_CONFIG
            self.conn = psycopg2.connect(**DB_CONFIG)
        return self.conn.cursor()

    # ------------------------------------------------------------------
    # CPU-Monitoring
    # ------------------------------------------------------------------
    def _read_cpu(self):
        """CPU-Auslastung und Temperatur lesen."""
        try:
            if HAS_PSUTIL:
                # CPU-Auslastung pro Core
                per_cpu = psutil.cpu_percent(interval=0.1, percpu=True)
                # CPU-Frequenz
                freqs = psutil.cpu_freq(percpu=True)
                # Temperaturen
                temps = {}
                try:
                    sensor_temps = psutil.sensors_temperatures()
                    if "coretemp" in sensor_temps:
                        for entry in sensor_temps["coretemp"]:
                            core_id = entry.label.replace("Core ", "")
                            if core_id.isdigit():
                                temps[int(core_id)] = entry.current
                except Exception:
                    pass

                with self._get_cursor() as cur:
                    for core_id, usage in enumerate(per_cpu):
                        freq = freqs[core_id].current if freqs and core_id < len(freqs) else None
                        temp = temps.get(core_id)
                        cur.execute(
                            """
                            INSERT INTO dbai_system.cpu
                                (core_id, usage_percent, frequency_mhz, temperature_c, throttled)
                            VALUES (%s, %s, %s, %s, %s)
                            """,
                            (core_id, usage, freq, temp, usage > 95),
                        )
                    self.conn.commit()
            else:
                # /proc/stat Fallback
                self._read_cpu_from_proc()
        except Exception as e:
            logger.debug("CPU-Lesung fehlgeschlagen: %s", e)
            try:
                self.conn.rollback()
            except Exception:
                pass

    def _read_cpu_from_proc(self):
        """CPU-Daten aus /proc/stat lesen."""
        try:
            with open("/proc/stat") as f:
                lines = f.readlines()

            with self._get_cursor() as cur:
                for line in lines:
                    if line.startswith("cpu") and line[3] != " ":
                        parts = line.split()
                        core_id = int(parts[0][3:])
                        # Vereinfachte Berechnung
                        total = sum(int(x) for x in parts[1:])
                        idle = int(parts[4])
                        usage = ((total - idle) / total) * 100 if total > 0 else 0

                        cur.execute(
                            """
                            INSERT INTO dbai_system.cpu
                                (core_id, usage_percent, throttled)
                            VALUES (%s, %s, %s)
                            """,
                            (core_id, round(usage, 1), usage > 95),
                        )
                self.conn.commit()
        except Exception as e:
            logger.debug("CPU /proc Lesung fehlgeschlagen: %s", e)
            try:
                self.conn.rollback()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # RAM-Monitoring
    # ------------------------------------------------------------------
    def _read_memory(self):
        """RAM-Belegung lesen."""
        try:
            if HAS_PSUTIL:
                mem = psutil.virtual_memory()
                swap = psutil.swap_memory()
                pressure = "normal"
                if mem.percent > 90:
                    pressure = "critical"
                elif mem.percent > 80:
                    pressure = "warning"

                with self._get_cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO dbai_system.memory
                            (total_mb, used_mb, free_mb, cached_mb, buffers_mb,
                             swap_total_mb, swap_used_mb, usage_percent, pressure_level)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            mem.total // (1024 * 1024),
                            mem.used // (1024 * 1024),
                            mem.free // (1024 * 1024),
                            getattr(mem, "cached", 0) // (1024 * 1024),
                            getattr(mem, "buffers", 0) // (1024 * 1024),
                            swap.total // (1024 * 1024),
                            swap.used // (1024 * 1024),
                            mem.percent,
                            pressure,
                        ),
                    )
                    self.conn.commit()
            else:
                self._read_memory_from_proc()
        except Exception as e:
            logger.debug("RAM-Lesung fehlgeschlagen: %s", e)
            try:
                self.conn.rollback()
            except Exception:
                pass

    def _read_memory_from_proc(self):
        """RAM-Daten aus /proc/meminfo lesen."""
        try:
            info = {}
            with open("/proc/meminfo") as f:
                for line in f:
                    parts = line.split()
                    key = parts[0].rstrip(":")
                    value = int(parts[1])  # in kB
                    info[key] = value

            total = info.get("MemTotal", 0) // 1024
            free = info.get("MemFree", 0) // 1024
            cached = info.get("Cached", 0) // 1024
            buffers = info.get("Buffers", 0) // 1024
            used = total - free - cached - buffers
            usage = (used / total * 100) if total > 0 else 0

            pressure = "normal"
            if usage > 90:
                pressure = "critical"
            elif usage > 80:
                pressure = "warning"

            with self._get_cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO dbai_system.memory
                        (total_mb, used_mb, free_mb, cached_mb, buffers_mb,
                         swap_total_mb, swap_used_mb, usage_percent, pressure_level)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        total, used, free, cached, buffers,
                        info.get("SwapTotal", 0) // 1024,
                        info.get("SwapFree", 0) // 1024,
                        round(usage, 1),
                        pressure,
                    ),
                )
                self.conn.commit()
        except Exception as e:
            logger.debug("RAM /proc Lesung fehlgeschlagen: %s", e)
            try:
                self.conn.rollback()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Disk-Monitoring
    # ------------------------------------------------------------------
    def _read_disk(self):
        """Festplatten-Status lesen."""
        try:
            if HAS_PSUTIL:
                partitions = psutil.disk_partitions()
                with self._get_cursor() as cur:
                    for p in partitions:
                        try:
                            usage = psutil.disk_usage(p.mountpoint)
                            io = psutil.disk_io_counters(perdisk=False)
                            cur.execute(
                                """
                                INSERT INTO dbai_system.disk
                                    (device, mount_point, fs_type,
                                     total_gb, used_gb, free_gb, usage_percent,
                                     health_state)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                """,
                                (
                                    p.device,
                                    p.mountpoint,
                                    p.fstype or "unknown",
                                    round(usage.total / (1024**3), 2),
                                    round(usage.used / (1024**3), 2),
                                    round(usage.free / (1024**3), 2),
                                    usage.percent,
                                    "healthy" if usage.percent < 90 else "degraded",
                                ),
                            )
                        except PermissionError:
                            pass
                    self.conn.commit()
        except Exception as e:
            logger.debug("Disk-Lesung fehlgeschlagen: %s", e)
            try:
                self.conn.rollback()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Temperatur-Monitoring
    # ------------------------------------------------------------------
    def _read_temperature(self):
        """Temperatur-Sensoren lesen."""
        try:
            if HAS_PSUTIL:
                temps = psutil.sensors_temperatures()
                if not temps:
                    return

                with self._get_cursor() as cur:
                    for chip_name, entries in temps.items():
                        for entry in entries:
                            state = "normal"
                            if entry.critical and entry.current >= entry.critical:
                                state = "critical"
                            elif entry.high and entry.current >= entry.high:
                                state = "hot"
                            elif entry.current > 70:
                                state = "warm"

                            sensor_type = "cpu"
                            if "gpu" in chip_name.lower():
                                sensor_type = "gpu"
                            elif "disk" in chip_name.lower() or "nvme" in chip_name.lower():
                                sensor_type = "disk"

                            cur.execute(
                                """
                                INSERT INTO dbai_system.temperature
                                    (sensor_name, sensor_type, temperature_c,
                                     critical_c, warning_c, state)
                                VALUES (%s, %s, %s, %s, %s, %s)
                                """,
                                (
                                    f"{chip_name}/{entry.label}",
                                    sensor_type,
                                    entry.current,
                                    entry.critical,
                                    entry.high,
                                    state,
                                ),
                            )
                    self.conn.commit()
            else:
                # Fallback: /sys/class/thermal
                self._read_temp_from_sys()
        except Exception as e:
            logger.debug("Temperatur-Lesung fehlgeschlagen: %s", e)
            try:
                self.conn.rollback()
            except Exception:
                pass

    def _read_temp_from_sys(self):
        """Temperatur aus /sys/class/thermal lesen."""
        thermal_dir = Path("/sys/class/thermal")
        if not thermal_dir.exists():
            return
        try:
            with self._get_cursor() as cur:
                for zone in thermal_dir.glob("thermal_zone*"):
                    temp_file = zone / "temp"
                    type_file = zone / "type"
                    if temp_file.exists():
                        temp_c = int(temp_file.read_text().strip()) / 1000
                        zone_type = type_file.read_text().strip() if type_file.exists() else "unknown"
                        state = "normal"
                        if temp_c > 90:
                            state = "critical"
                        elif temp_c > 80:
                            state = "hot"
                        elif temp_c > 70:
                            state = "warm"

                        cur.execute(
                            """
                            INSERT INTO dbai_system.temperature
                                (sensor_name, sensor_type, temperature_c, state)
                            VALUES (%s, 'cpu', %s, %s)
                            """,
                            (zone_type, temp_c, state),
                        )
                self.conn.commit()
        except Exception as e:
            logger.debug("Temperatur /sys Lesung fehlgeschlagen: %s", e)
            try:
                self.conn.rollback()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Netzwerk-Monitoring
    # ------------------------------------------------------------------
    def _read_network(self):
        """Netzwerk-Interfaces lesen."""
        try:
            if HAS_PSUTIL:
                stats = psutil.net_if_stats()
                counters = psutil.net_io_counters(pernic=True)
                addrs = psutil.net_if_addrs()

                with self._get_cursor() as cur:
                    for iface, stat in stats.items():
                        if iface == "lo":
                            continue

                        cnt = counters.get(iface)
                        ip_addr = None
                        mac_addr = None
                        if iface in addrs:
                            for addr in addrs[iface]:
                                if addr.family.name == "AF_INET":
                                    ip_addr = addr.address
                                elif addr.family.name == "AF_PACKET":
                                    mac_addr = addr.address

                        cur.execute(
                            """
                            INSERT INTO dbai_system.network
                                (interface, state, ip_address, mac_address,
                                 rx_bytes, tx_bytes, rx_packets, tx_packets,
                                 rx_errors, tx_errors, link_speed_mbps)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                iface,
                                "up" if stat.isup else "down",
                                ip_addr,
                                mac_addr,
                                cnt.bytes_recv if cnt else 0,
                                cnt.bytes_sent if cnt else 0,
                                cnt.packets_recv if cnt else 0,
                                cnt.packets_sent if cnt else 0,
                                cnt.errin if cnt else 0,
                                cnt.errout if cnt else 0,
                                stat.speed if stat.speed else None,
                            ),
                        )
                    self.conn.commit()
        except Exception as e:
            logger.debug("Netzwerk-Lesung fehlgeschlagen: %s", e)
            try:
                self.conn.rollback()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Hauptschleife
    # ------------------------------------------------------------------
    def run(self):
        """Hauptschleife: Liest alle Sensoren in definierten Intervallen."""
        logger.info("Hardware-Monitor gestartet")
        iteration = 0

        while not self.shutdown_event.is_set():
            # CPU: Alle 500ms
            self._read_cpu()

            # RAM: Alle 1s
            if iteration % 2 == 0:
                self._read_memory()

            # Temperatur: Alle 2s
            if iteration % 4 == 0:
                self._read_temperature()

            # Netzwerk: Alle 1s
            if iteration % 2 == 0:
                self._read_network()

            # Disk: Alle 5s
            if iteration % 10 == 0:
                self._read_disk()

            iteration += 1
            self.shutdown_event.wait(0.5)

        logger.info("Hardware-Monitor gestoppt")
