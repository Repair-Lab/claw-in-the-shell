#!/usr/bin/env python3
"""
DBAI GPU Manager — Echtzeit-GPU-Monitoring und VRAM-Management.

Die "Neural Bridge" zwischen physischen Grafikkarten und dem Ghost-System.
Nutzt pynvml (NVIDIA) oder rocm-smi (AMD) für direkten Zugriff.

Funktionen:
  - GPU-Discovery: Erkennt alle GPUs beim Start
  - Echtzeit-Metriken: VRAM, Auslastung, Temperatur (alle 500ms)
  - VRAM-Reservierung: Koordiniert mit Ghost-Dispatcher
  - Multi-GPU: Layer-Splitting über mehrere GPUs
  - Thermik-Schutz: Automatische Drosselung bei Überhitzung
  - Power-Profile: Setzt GPU Power-Limits

Verwendung:
  python3 -m bridge.gpu_manager          # Einmal scannen
  python3 -m bridge.gpu_manager --daemon  # Periodisches Monitoring
"""

import json
import logging
import os
import signal
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    import psycopg2
    import psycopg2.extras

    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

# pynvml: Offizielle NVIDIA Management Library
try:
    import pynvml

    HAS_PYNVML = True
except ImportError:
    HAS_PYNVML = False

# ─── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [GPU-MGR] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("gpu_manager")

# ─── Konfiguration ───────────────────────────────────────────────────────────

DB_NAME = os.environ.get("DBAI_DB_NAME", "dbai")
DB_USER = os.environ.get("DBAI_DB_USER", "dbai_system")
DB_HOST = os.environ.get("DBAI_DB_HOST", "127.0.0.1")
DB_PORT = os.environ.get("DBAI_DB_PORT", "5432")

UPDATE_INTERVAL_MS = int(os.environ.get("DBAI_GPU_INTERVAL_MS", "500"))
VRAM_RESERVE_MB = int(os.environ.get("DBAI_GPU_VRAM_RESERVE_MB", "256"))
TEMP_WARNING_C = float(os.environ.get("DBAI_GPU_TEMP_WARNING", "80"))
TEMP_CRITICAL_C = float(os.environ.get("DBAI_GPU_TEMP_CRITICAL", "90"))


def _run_cmd(cmd: List[str], timeout: int = 10) -> Optional[str]:
    """Shell-Befehl ausführen."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip() if result.returncode == 0 else None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


class GPUManager:
    """Verwaltet GPU-Ressourcen und koordiniert mit dem Ghost-System."""

    def __init__(self):
        self.conn = None
        self.nvml_initialized = False
        self.gpu_count = 0
        self.gpu_handles = []       # pynvml Handles
        self.gpu_db_ids = {}        # gpu_index → UUID in gpu_devices
        self.hw_inventory_ids = {}  # gpu_index → UUID in hardware_inventory
        self._running = True

    # ─── Initialisierung ──────────────────────────────────────────────────

    def connect_db(self) -> bool:
        """Datenbankverbindung herstellen."""
        if not HAS_PSYCOPG2:
            log.error("psycopg2 nicht installiert!")
            return False
        try:
            self.conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER, host=DB_HOST, port=DB_PORT
            )
            self.conn.autocommit = True
            log.info(f"DB verbunden: {DB_NAME}@{DB_HOST}:{DB_PORT}")
            return True
        except Exception as e:
            log.error(f"DB-Verbindung fehlgeschlagen: {e}")
            return False

    def init_nvml(self) -> bool:
        """NVIDIA Management Library initialisieren."""
        if not HAS_PYNVML:
            log.warning("pynvml nicht installiert. Versuche nvidia-smi Fallback...")
            return self._init_nvidia_smi_fallback()

        try:
            pynvml.nvmlInit()
            self.nvml_initialized = True
            self.gpu_count = pynvml.nvmlDeviceGetCount()

            if self.gpu_count == 0:
                log.info("Keine NVIDIA GPUs gefunden")
                return False

            for i in range(self.gpu_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                self.gpu_handles.append(handle)
                name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode("utf-8")
                log.info(f"GPU {i}: {name}")

            driver = pynvml.nvmlSystemGetDriverVersion()
            if isinstance(driver, bytes):
                driver = driver.decode("utf-8")
            cuda = pynvml.nvmlSystemGetCudaDriverVersion()
            cuda_str = f"{cuda // 1000}.{(cuda % 1000) // 10}"
            log.info(f"NVIDIA Driver: {driver}, CUDA: {cuda_str}")
            log.info(f"{self.gpu_count} GPU(s) erkannt via pynvml")
            return True

        except Exception as e:
            log.warning(f"pynvml Init fehlgeschlagen: {e}")
            return self._init_nvidia_smi_fallback()

    def _init_nvidia_smi_fallback(self) -> bool:
        """Fallback: nvidia-smi CLI statt pynvml."""
        result = _run_cmd(["nvidia-smi", "--query-gpu=index,name", "--format=csv,noheader"])
        if not result:
            # AMD prüfen
            result = _run_cmd(["rocm-smi", "--showid"])
            if result:
                log.info("AMD ROCm GPU erkannt (eingeschränkter Support)")
                return True
            log.info("Keine GPU erkannt (weder NVIDIA noch AMD)")
            return False

        lines = result.strip().split("\n")
        self.gpu_count = len(lines)
        for line in lines:
            parts = line.split(", ")
            log.info(f"GPU {parts[0]}: {parts[1] if len(parts) > 1 else 'unknown'}")

        log.info(f"{self.gpu_count} GPU(s) erkannt via nvidia-smi")
        return True

    # ─── GPU Discovery → DB ──────────────────────────────────────────────

    def discover_and_register(self):
        """Alle GPUs in Hardware-Inventar und gpu_devices eintragen."""
        if not self.conn:
            return

        if HAS_PYNVML and self.nvml_initialized:
            self._register_via_pynvml()
        else:
            self._register_via_nvidia_smi()

        # System Capabilities aktualisieren
        self._update_capabilities()

    def _register_via_pynvml(self):
        """GPUs via pynvml registrieren."""
        driver_version = ""
        cuda_version = ""
        try:
            dv = pynvml.nvmlSystemGetDriverVersion()
            driver_version = dv.decode("utf-8") if isinstance(dv, bytes) else str(dv)
            cv = pynvml.nvmlSystemGetCudaDriverVersion()
            cuda_version = f"{cv // 1000}.{(cv % 1000) // 10}"
        except Exception:
            pass

        for i, handle in enumerate(self.gpu_handles):
            try:
                name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode("utf-8")

                mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                vram_total = mem.total // (1024 * 1024)
                vram_used = mem.used // (1024 * 1024)
                vram_free = mem.free // (1024 * 1024)

                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0  # mW → W
                power_limit = pynvml.nvmlDeviceGetPowerManagementLimit(handle) / 1000.0

                try:
                    fan = pynvml.nvmlDeviceGetFanSpeed(handle)
                except pynvml.NVMLError:
                    fan = 0

                try:
                    clk_graphics = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_GRAPHICS)
                    clk_mem = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_MEM)
                    clk_max = pynvml.nvmlDeviceGetMaxClockInfo(handle, pynvml.NVML_CLOCK_GRAPHICS)
                except pynvml.NVMLError:
                    clk_graphics = clk_mem = clk_max = 0

                try:
                    pstate = pynvml.nvmlDeviceGetPerformanceState(handle)
                    pstate_str = f"P{pstate}"
                except pynvml.NVMLError:
                    pstate_str = "P0"

                try:
                    pci = pynvml.nvmlDeviceGetPciInfo(handle)
                    pci_bus = pci.busId.decode("utf-8") if isinstance(pci.busId, bytes) else str(pci.busId)
                except pynvml.NVMLError:
                    pci_bus = None

                try:
                    cc_major = pynvml.nvmlDeviceGetCudaComputeCapability(handle)
                    compute_cap = f"{cc_major[0]}.{cc_major[1]}"
                except (pynvml.NVMLError, TypeError):
                    compute_cap = None

                arch = self._guess_architecture(name, compute_cap)

                # PCIe Info
                try:
                    pcie_gen = pynvml.nvmlDeviceGetCurrPcieLinkGeneration(handle)
                    pcie_width = pynvml.nvmlDeviceGetCurrPcieLinkWidth(handle)
                except pynvml.NVMLError:
                    pcie_gen = pcie_width = 0

                temp_max = 0
                try:
                    temp_max = pynvml.nvmlDeviceGetTemperatureThreshold(
                        handle, pynvml.NVML_TEMPERATURE_THRESHOLD_GPU_MAX
                    )
                except pynvml.NVMLError:
                    temp_max = 100

                # Hardware-Inventar
                hw_id = self._upsert_hw_inventory(i, name, pci_bus, driver_version, vram_total)
                self.hw_inventory_ids[i] = hw_id

                # GPU-Devices Tabelle
                gpu_id = self._upsert_gpu_device(
                    hw_id=hw_id,
                    gpu_index=i,
                    name=name,
                    vendor="nvidia",
                    architecture=arch,
                    compute_capability=compute_cap,
                    vram_total=vram_total,
                    vram_used=vram_used,
                    vram_free=vram_free,
                    gpu_util=util.gpu,
                    mem_util=util.memory,
                    clk_graphics=clk_graphics,
                    clk_mem=clk_mem,
                    clk_max=clk_max,
                    temperature=temp,
                    temp_max=temp_max,
                    fan_speed=fan,
                    power_draw=power,
                    power_limit=power_limit,
                    power_state=pstate_str,
                    pcie_gen=pcie_gen,
                    pcie_width=pcie_width,
                    cuda_version=cuda_version,
                    driver_version=driver_version,
                )

                self.gpu_db_ids[i] = gpu_id

                log.info(
                    f"  GPU {i}: {name} | VRAM: {vram_used}/{vram_total}MB | "
                    f"Util: {util.gpu}% | Temp: {temp}°C | Power: {power:.0f}W"
                )

            except Exception as e:
                log.error(f"GPU {i} Registrierung fehlgeschlagen: {e}")

    def _register_via_nvidia_smi(self):
        """Fallback: GPUs via nvidia-smi CLI registrieren."""
        result = _run_cmd([
            "nvidia-smi",
            "--query-gpu=index,name,memory.total,memory.used,memory.free,"
            "utilization.gpu,utilization.memory,temperature.gpu,"
            "power.draw,power.limit,pstate,pcie.link.gen.current,"
            "pcie.link.width.current,driver_version,fan.speed,"
            "clocks.current.graphics,clocks.current.memory,clocks.max.graphics",
            "--format=csv,noheader,nounits"
        ])

        if not result:
            return

        for line in result.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 14:
                continue

            try:
                idx = int(parts[0])
                name = parts[1]
                vram_total = int(float(parts[2]))
                vram_used = int(float(parts[3]))
                vram_free = int(float(parts[4]))
                gpu_util = float(parts[5]) if parts[5] != "[N/A]" else 0
                mem_util = float(parts[6]) if parts[6] != "[N/A]" else 0
                temp = float(parts[7]) if parts[7] != "[N/A]" else 0
                power = float(parts[8]) if parts[8] != "[N/A]" else 0
                power_limit = float(parts[9]) if parts[9] != "[N/A]" else 0
                pstate = parts[10]
                pcie_gen = int(parts[11]) if parts[11] != "[N/A]" else 0
                pcie_width = int(parts[12]) if parts[12] != "[N/A]" else 0
                driver = parts[13]
                fan = float(parts[14]) if len(parts) > 14 and parts[14] != "[N/A]" else 0
                clk_g = int(float(parts[15])) if len(parts) > 15 and parts[15] != "[N/A]" else 0
                clk_m = int(float(parts[16])) if len(parts) > 16 and parts[16] != "[N/A]" else 0
                clk_max = int(float(parts[17])) if len(parts) > 17 and parts[17] != "[N/A]" else 0

                hw_id = self._upsert_hw_inventory(idx, name, None, driver, vram_total)
                self.hw_inventory_ids[idx] = hw_id

                gpu_id = self._upsert_gpu_device(
                    hw_id=hw_id, gpu_index=idx, name=name, vendor="nvidia",
                    architecture=self._guess_architecture(name),
                    vram_total=vram_total, vram_used=vram_used, vram_free=vram_free,
                    gpu_util=gpu_util, mem_util=mem_util,
                    clk_graphics=clk_g, clk_mem=clk_m, clk_max=clk_max,
                    temperature=temp, temp_max=100, fan_speed=fan,
                    power_draw=power, power_limit=power_limit, power_state=pstate,
                    pcie_gen=pcie_gen, pcie_width=pcie_width,
                    driver_version=driver,
                )
                self.gpu_db_ids[idx] = gpu_id

            except (ValueError, IndexError) as e:
                log.warning(f"nvidia-smi Parsing-Fehler: {e}")

    def _guess_architecture(self, name: str, compute_cap: str = None) -> str:
        """GPU-Architektur anhand des Namens erraten."""
        name_lower = name.lower()
        if any(x in name_lower for x in ["h100", "h200"]):
            return "Hopper"
        if any(x in name_lower for x in ["l40", "l4", "rtx 40", "rtx 4"]):
            return "Ada Lovelace"
        if any(x in name_lower for x in ["a100", "rtx 30", "rtx 3", "a40", "a30"]):
            return "Ampere"
        if any(x in name_lower for x in ["rtx 20", "rtx 2", "titan rtx", "t4"]):
            return "Turing"
        if any(x in name_lower for x in ["v100", "titan v"]):
            return "Volta"
        if any(x in name_lower for x in ["p100", "gtx 10", "titan x"]):
            return "Pascal"
        return "Unknown"

    def _upsert_hw_inventory(self, idx: int, name: str, pci_bus: str, driver: str, vram: int) -> Optional[str]:
        """GPU in hardware_inventory eintragen."""
        if not self.conn:
            return None
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO dbai_system.hardware_inventory
                        (device_class, device_name, vendor, model, pci_address,
                         driver_name, driver_version, capabilities, properties, status)
                    VALUES ('gpu', %s, 'NVIDIA', %s, %s, 'nvidia', %s,
                            %s, %s, 'active')
                    ON CONFLICT DO NOTHING
                    RETURNING id
                    """,
                    (
                        name, name, pci_bus, driver,
                        json.dumps({"cuda": True, "vram_mb": vram}),
                        json.dumps({"gpu_index": idx, "vram_total_mb": vram}),
                    ),
                )
                row = cur.fetchone()
                if row:
                    return str(row[0])
                # Existing entry
                cur.execute(
                    "SELECT id FROM dbai_system.hardware_inventory "
                    "WHERE device_class = 'gpu' AND device_name = %s "
                    "ORDER BY created_at DESC LIMIT 1",
                    (name,),
                )
                row = cur.fetchone()
                return str(row[0]) if row else None
        except Exception as e:
            log.warning(f"Hardware-Inventar GPU {idx} fehlgeschlagen: {e}")
            return None

    def _upsert_gpu_device(self, hw_id, gpu_index, name, vendor="nvidia", **kwargs) -> Optional[str]:
        """GPU in gpu_devices eintragen oder aktualisieren."""
        if not self.conn or not hw_id:
            return None
        try:
            with self.conn.cursor() as cur:
                # Prüfen ob schon existiert
                cur.execute(
                    "SELECT id FROM dbai_system.gpu_devices WHERE gpu_index = %s",
                    (gpu_index,),
                )
                existing = cur.fetchone()

                if existing:
                    # Update
                    cur.execute(
                        """
                        UPDATE dbai_system.gpu_devices SET
                            vram_used_mb = %s, vram_free_mb = %s,
                            gpu_utilization = %s, memory_utilization = %s,
                            clock_graphics_mhz = %s, clock_memory_mhz = %s,
                            temperature_c = %s, fan_speed_percent = %s,
                            power_draw_watts = %s, power_state = %s,
                            is_available = TRUE, is_healthy = %s,
                            last_updated = now()
                        WHERE id = %s
                        """,
                        (
                            kwargs.get("vram_used", 0),
                            kwargs.get("vram_free", 0),
                            kwargs.get("gpu_util", 0),
                            kwargs.get("mem_util", 0),
                            kwargs.get("clk_graphics", 0),
                            kwargs.get("clk_mem", 0),
                            kwargs.get("temperature", 0),
                            kwargs.get("fan_speed", 0),
                            kwargs.get("power_draw", 0),
                            kwargs.get("power_state", "P0"),
                            kwargs.get("temperature", 0) < TEMP_CRITICAL_C,
                            str(existing[0]),
                        ),
                    )
                    return str(existing[0])
                else:
                    # Insert
                    cur.execute(
                        """
                        INSERT INTO dbai_system.gpu_devices
                            (hw_inventory_id, gpu_index, name, vendor, architecture,
                             compute_capability, vram_total_mb, vram_used_mb, vram_free_mb,
                             gpu_utilization, memory_utilization,
                             clock_graphics_mhz, clock_memory_mhz, clock_max_mhz,
                             temperature_c, temperature_max_c, fan_speed_percent,
                             power_draw_watts, power_limit_watts, power_state,
                             pcie_generation, pcie_width,
                             cuda_version, driver_version,
                             is_available, is_healthy)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, TRUE)
                        RETURNING id
                        """,
                        (
                            hw_id, gpu_index, name, vendor,
                            kwargs.get("architecture"),
                            kwargs.get("compute_capability"),
                            kwargs.get("vram_total", 0),
                            kwargs.get("vram_used", 0),
                            kwargs.get("vram_free", 0),
                            kwargs.get("gpu_util", 0),
                            kwargs.get("mem_util", 0),
                            kwargs.get("clk_graphics", 0),
                            kwargs.get("clk_mem", 0),
                            kwargs.get("clk_max", 0),
                            kwargs.get("temperature", 0),
                            kwargs.get("temp_max", 100),
                            kwargs.get("fan_speed", 0),
                            kwargs.get("power_draw", 0),
                            kwargs.get("power_limit", 0),
                            kwargs.get("power_state", "P0"),
                            kwargs.get("pcie_gen", 0),
                            kwargs.get("pcie_width", 0),
                            kwargs.get("cuda_version"),
                            kwargs.get("driver_version"),
                        ),
                    )
                    row = cur.fetchone()
                    return str(row[0]) if row else None
        except Exception as e:
            log.warning(f"GPU-Device {gpu_index} DB-Fehler: {e}")
            return None

    # ─── Echtzeit-Monitoring ──────────────────────────────────────────────

    def update_metrics(self):
        """GPU-Metriken aktualisieren (alle 500ms aufgerufen)."""
        if HAS_PYNVML and self.nvml_initialized:
            self._update_via_pynvml()
        elif self.gpu_count > 0:
            self._register_via_nvidia_smi()  # Fallback: nvidia-smi neu ausführen

    def _update_via_pynvml(self):
        """Schnelles Metriken-Update via pynvml."""
        for i, handle in enumerate(self.gpu_handles):
            gpu_id = self.gpu_db_ids.get(i)
            if not gpu_id or not self.conn:
                continue

            try:
                mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0

                try:
                    fan = pynvml.nvmlDeviceGetFanSpeed(handle)
                except pynvml.NVMLError:
                    fan = 0

                try:
                    clk = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_GRAPHICS)
                    clk_mem = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_MEM)
                except pynvml.NVMLError:
                    clk = clk_mem = 0

                try:
                    pstate = pynvml.nvmlDeviceGetPerformanceState(handle)
                    pstate_str = f"P{pstate}"
                except pynvml.NVMLError:
                    pstate_str = "P0"

                is_healthy = temp < TEMP_CRITICAL_C

                with self.conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE dbai_system.gpu_devices SET
                            vram_used_mb = %s, vram_free_mb = %s,
                            gpu_utilization = %s, memory_utilization = %s,
                            clock_graphics_mhz = %s, clock_memory_mhz = %s,
                            temperature_c = %s, fan_speed_percent = %s,
                            power_draw_watts = %s, power_state = %s,
                            is_healthy = %s, last_updated = now()
                        WHERE id = %s
                        """,
                        (
                            mem.used // (1024 * 1024),
                            mem.free // (1024 * 1024),
                            util.gpu, util.memory,
                            clk, clk_mem,
                            temp, fan, power, pstate_str,
                            is_healthy, gpu_id,
                        ),
                    )

                # Thermik-Alarm
                if temp >= TEMP_CRITICAL_C:
                    log.warning(f"GPU {i}: KRITISCHE TEMPERATUR {temp}°C! Ghost-Migration erforderlich!")
                    self._notify_overheat(i, temp)
                elif temp >= TEMP_WARNING_C:
                    log.warning(f"GPU {i}: Hohe Temperatur {temp}°C")

            except pynvml.NVMLError as e:
                log.warning(f"GPU {i} Metriken-Update fehlgeschlagen: {e}")
            except Exception as e:
                log.error(f"GPU {i} Update-Fehler: {e}")

    def _notify_overheat(self, gpu_index: int, temperature: float):
        """Benachrichtigt das Ghost-System über Überhitzung."""
        if not self.conn:
            return
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "SELECT pg_notify('gpu_overheat', %s)",
                    (json.dumps({
                        "gpu_index": gpu_index,
                        "temperature_c": temperature,
                        "action": "migrate_to_cpu",
                        "severity": "critical",
                    }),),
                )
        except Exception:
            pass

    # ─── VRAM-Management ─────────────────────────────────────────────────

    def check_vram_for_model(self, required_vram_mb: int, preferred_gpu: int = None) -> Dict:
        """Prüft ob genug VRAM für ein Modell verfügbar ist."""
        if not self.conn:
            return {"fits": False, "reason": "Keine DB-Verbindung"}

        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM dbai_system.check_gpu_available(%s, %s)",
                    (required_vram_mb, preferred_gpu),
                )
                result = cur.fetchone()
                return result[0] if result else {"fits": False, "reason": "Keine GPUs"}
        except Exception as e:
            return {"fits": False, "reason": str(e)}

    def allocate_for_ghost(self, gpu_index: int, model_id: str, role_id: str,
                           vram_mb: int, gpu_layers: int = -1, total_layers: int = 0) -> Optional[str]:
        """VRAM für einen Ghost reservieren."""
        gpu_id = self.gpu_db_ids.get(gpu_index)
        if not gpu_id or not self.conn:
            return None

        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "SELECT dbai_system.allocate_vram(%s, %s, %s, %s, %s, %s, 'full')",
                    (gpu_id, model_id, role_id, vram_mb, gpu_layers, total_layers),
                )
                result = cur.fetchone()
                return str(result[0]) if result else None
        except Exception as e:
            log.error(f"VRAM-Allokation fehlgeschlagen: {e}")
            return None

    def release_ghost_vram(self, model_id: str):
        """VRAM eines entladenen Ghost-Modells freigeben."""
        if not self.conn:
            return
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT dbai_system.release_vram(%s)", (model_id,))
                log.info(f"VRAM freigegeben für Modell {model_id}")
        except Exception as e:
            log.error(f"VRAM-Freigabe fehlgeschlagen: {e}")

    def get_optimal_gpu_layers(self, model_vram_mb: int, gpu_index: int = 0) -> int:
        """Berechnet optimale Anzahl GPU-Layers basierend auf verfügbarem VRAM."""
        gpu_id = self.gpu_db_ids.get(gpu_index)
        if not gpu_id or not self.conn:
            return 0  # CPU-only

        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "SELECT vram_free_mb, vram_reserved_mb FROM dbai_system.gpu_devices WHERE id = %s",
                    (gpu_id,),
                )
                row = cur.fetchone()
                if not row:
                    return 0

                available = row[0] - row[1] - VRAM_RESERVE_MB
                if available <= 0:
                    return 0

                if available >= model_vram_mb:
                    return -1  # Alle Layers auf GPU

                # Anteilig: z.B. 50% VRAM = 50% Layers
                ratio = available / model_vram_mb
                estimated_layers = int(ratio * 40)  # 40 als typische Layer-Anzahl
                return max(1, estimated_layers)

        except Exception:
            return 0

    def plan_multi_gpu_split(self, model_vram_mb: int, total_layers: int = 40) -> List[Dict]:
        """Plant Layer-Verteilung über mehrere GPUs."""
        if not self.conn:
            return []

        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "SELECT id, gpu_index, vram_free_mb - vram_reserved_mb - %s AS available "
                    "FROM dbai_system.gpu_devices "
                    "WHERE is_available = TRUE AND is_healthy = TRUE "
                    "AND (vram_free_mb - vram_reserved_mb) > %s "
                    "ORDER BY (vram_free_mb - vram_reserved_mb) DESC",
                    (VRAM_RESERVE_MB, 100),
                )
                gpus = cur.fetchall()

            if not gpus:
                return []

            # Greedy Layer-Verteilung
            remaining_vram = model_vram_mb
            vram_per_layer = model_vram_mb / total_layers
            remaining_layers = total_layers
            plan = []

            for gpu_id, gpu_index, available in gpus:
                if remaining_layers <= 0:
                    break

                layers_on_this = min(
                    remaining_layers,
                    int(available / vram_per_layer)
                )

                if layers_on_this > 0:
                    vram_needed = int(layers_on_this * vram_per_layer)
                    plan.append({
                        "gpu_id": str(gpu_id),
                        "gpu_index": gpu_index,
                        "layers": layers_on_this,
                        "vram_mb": vram_needed,
                    })
                    remaining_layers -= layers_on_this
                    remaining_vram -= vram_needed

            if remaining_layers > 0:
                plan.append({
                    "gpu_id": None,
                    "gpu_index": -1,  # CPU
                    "layers": remaining_layers,
                    "vram_mb": 0,
                    "note": "CPU-Fallback für übrige Layers",
                })

            return plan

        except Exception as e:
            log.error(f"Multi-GPU Split Planung fehlgeschlagen: {e}")
            return []

    # ─── Power Profile Management ─────────────────────────────────────────

    def apply_gpu_power_limit(self, gpu_index: int, watts: int):
        """GPU Power-Limit setzen (erfordert Root)."""
        if HAS_PYNVML and self.nvml_initialized and gpu_index < len(self.gpu_handles):
            try:
                handle = self.gpu_handles[gpu_index]
                pynvml.nvmlDeviceSetPowerManagementLimit(handle, watts * 1000)
                log.info(f"GPU {gpu_index}: Power-Limit auf {watts}W gesetzt")
            except pynvml.NVMLError as e:
                log.warning(f"GPU Power-Limit fehlgeschlagen (Root nötig?): {e}")
        else:
            result = _run_cmd(["nvidia-smi", "-i", str(gpu_index), "-pl", str(watts)])
            if result is not None:
                log.info(f"GPU {gpu_index}: Power-Limit auf {watts}W gesetzt (nvidia-smi)")

    def set_persistence_mode(self, gpu_index: int, enable: bool):
        """GPU Persistence Mode setzen."""
        mode = "1" if enable else "0"
        _run_cmd(["nvidia-smi", "-i", str(gpu_index), "-pm", mode])

    # ─── System Capabilities ──────────────────────────────────────────────

    def _update_capabilities(self):
        """System-Capabilities für GPU aktualisieren."""
        if not self.conn:
            return

        try:
            with self.conn.cursor() as cur:
                # CUDA Capability
                cur.execute(
                    "UPDATE dbai_core.system_capabilities "
                    "SET is_available = %s, details = %s, last_verified = now() "
                    "WHERE capability = 'cuda'",
                    (
                        self.gpu_count > 0,
                        json.dumps({"gpu_count": self.gpu_count, "backend": "pynvml" if HAS_PYNVML else "nvidia-smi"}),
                    ),
                )

                # Multi-GPU
                cur.execute(
                    "UPDATE dbai_core.system_capabilities "
                    "SET is_available = %s, details = %s, last_verified = now() "
                    "WHERE capability = 'multi_gpu'",
                    (
                        self.gpu_count > 1,
                        json.dumps({"gpu_count": self.gpu_count}),
                    ),
                )

                # P2P (nur mit pynvml prüfbar)
                if HAS_PYNVML and self.gpu_count > 1:
                    try:
                        p2p = pynvml.nvmlDeviceGetP2PStatus(
                            self.gpu_handles[0], self.gpu_handles[1],
                            pynvml.NVML_P2P_CAPS_INDEX_READ
                        )
                        cur.execute(
                            "UPDATE dbai_core.system_capabilities "
                            "SET is_available = %s, last_verified = now() "
                            "WHERE capability = 'gpu_p2p'",
                            (p2p == pynvml.NVML_P2P_STATUS_OK,),
                        )
                    except (pynvml.NVMLError, IndexError):
                        pass
        except Exception as e:
            log.warning(f"Capabilities-Update fehlgeschlagen: {e}")

    # ─── NOTIFY Listener ──────────────────────────────────────────────────

    def listen_for_events(self):
        """Hört auf DB-Events die GPU betreffen."""
        if not self.conn:
            return

        try:
            listen_conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER, host=DB_HOST, port=DB_PORT
            )
            listen_conn.autocommit = True

            with listen_conn.cursor() as cur:
                cur.execute("LISTEN power_profile_change")
                cur.execute("LISTEN fan_control")
                cur.execute("LISTEN gpu_overheat")

            log.info("NOTIFY Listener aktiv: power_profile_change, fan_control, gpu_overheat")

            import select

            while self._running:
                if select.select([listen_conn], [], [], 1.0) != ([], [], []):
                    listen_conn.poll()
                    while listen_conn.notifies:
                        notify = listen_conn.notifies.pop(0)
                        self._handle_notify(notify.channel, notify.payload)

        except Exception as e:
            log.error(f"NOTIFY Listener Fehler: {e}")

    def _handle_notify(self, channel: str, payload: str):
        """Verarbeitet eingehende NOTIFY Events."""
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            data = {"raw": payload}

        if channel == "power_profile_change":
            log.info(f"Power-Profil gewechselt: {data.get('profile')}")
            gpu_limit = data.get("gpu_power_limit")
            if gpu_limit:
                for i in range(self.gpu_count):
                    self.apply_gpu_power_limit(i, gpu_limit)

        elif channel == "gpu_overheat":
            gpu_idx = data.get("gpu_index", 0)
            log.warning(f"GPU {gpu_idx} Überhitzung! Aktion: {data.get('action')}")

    # ─── Daemon Loop ──────────────────────────────────────────────────────

    def daemon_loop(self):
        """Hauptschleife: Periodisches GPU-Monitoring."""
        log.info(f"GPU Manager Daemon gestartet (Intervall: {UPDATE_INTERVAL_MS}ms)")

        def stop_handler(sig, frame):
            self._running = False
            log.info("Stop-Signal empfangen")

        signal.signal(signal.SIGTERM, stop_handler)
        signal.signal(signal.SIGINT, stop_handler)

        # Initiale GPU-Registrierung
        self.discover_and_register()

        # NOTIFY Listener in separatem Thread
        import threading
        listener_thread = threading.Thread(target=self.listen_for_events, daemon=True)
        listener_thread.start()

        interval = UPDATE_INTERVAL_MS / 1000.0

        while self._running:
            try:
                self.update_metrics()
                time.sleep(interval)
            except Exception as e:
                log.error(f"Daemon-Fehler: {e}")
                time.sleep(5)

        self.shutdown()

    def shutdown(self):
        """Aufräumen."""
        if self.nvml_initialized:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass
        if self.conn:
            self.conn.close()
        log.info("GPU Manager beendet")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    mgr = GPUManager()

    # NVML initialisieren
    has_gpu = mgr.init_nvml()

    if not has_gpu:
        log.info("Kein GPU-Support verfügbar — GPU Manager im Standby")
        if "--daemon" not in sys.argv:
            return

    # DB verbinden
    mgr.connect_db()

    try:
        if "--daemon" in sys.argv:
            mgr.daemon_loop()
        else:
            mgr.discover_and_register()
            mgr.update_metrics()

            # Zusammenfassung ausgeben
            if mgr.conn:
                try:
                    with mgr.conn.cursor() as cur:
                        cur.execute("SELECT gpu_index, name, vram_total_mb, vram_used_mb, "
                                    "gpu_utilization, temperature_c FROM dbai_system.gpu_devices "
                                    "ORDER BY gpu_index")
                        for row in cur.fetchall():
                            print(f"  GPU {row[0]}: {row[1]} | "
                                  f"VRAM: {row[3]}/{row[2]}MB | "
                                  f"Util: {row[4]}% | Temp: {row[5]}°C")
                except Exception:
                    pass
    finally:
        mgr.shutdown()


if __name__ == "__main__":
    main()
