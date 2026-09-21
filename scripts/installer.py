#!/usr/bin/env python3
"""
=============================================================================
GhostShell OS — Installer (Python TUI)
=============================================================================
Interaktiver Installer der beim Boot vom Live-Medium (USB/ISO) startet.
Verwendet subprocess + dialog/whiptail für die TUI-Oberfläche.

Ablauf:
  1. Willkommen + Sprachauswahl
  2. Festplatte auswählen (lsblk)
  3. Installationsmodus (Löschen / Dual-Boot / Manuell)
  4. Dateisystem wählen (BTRFS / EXT4 / ZFS)
  5. Partitionierung + Formatierung
  6. System kopieren (SquashFS → Ziel)
  7. Bootloader installieren (GRUB)
  8. Benutzer einrichten
  9. First-Boot vorbereiten
  10. Neustart

Getestet in QEMU und auf echter Hardware.
=============================================================================
"""

import os
import sys
import json
import shutil
import subprocess
import time
import re
import signal
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Tuple

# ─── Konstanten ──────────────────────────────────────────────────

VERSION = "1.0.0"
TITLE = "🧠 GhostShell OS — Installer"
LIVE_SQUASHFS = "/run/archiso/airootfs"  # Arch Live-SquashFS Mountpoint
LIVE_SQUASHFS_ALT = [
    "/run/live/rootfs/filesystem.squashfs",  # Debian Live
    "/run/archiso/cowspace",
    "/",  # Fallback: Live-Root direkt
]
DBAI_SRC = "/opt/dbai"
MIN_DISK_GB = 8
RECOMMENDED_DISK_GB = 32
LOG_FILE = "/tmp/ghostshell-install.log"

# ─── Farben ──────────────────────────────────────────────────────

class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    RED    = "\033[91m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    CYAN   = "\033[96m"
    BLUE   = "\033[94m"
    DIM    = "\033[2m"


# ─── Logging ─────────────────────────────────────────────────────

def log(msg: str, level: str = "INFO"):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")
    if level == "ERROR":
        print(f"{C.RED}[❌] {msg}{C.RESET}")
    elif level == "WARN":
        print(f"{C.YELLOW}[⚠] {msg}{C.RESET}")
    else:
        print(f"{C.CYAN}[→] {msg}{C.RESET}")


# ─── Dialog-Wrapper ──────────────────────────────────────────────

class Dialog:
    """Wrapper für dialog/whiptail CLI-Befehle."""

    def __init__(self):
        if shutil.which("dialog"):
            self.cmd = "dialog"
        elif shutil.which("whiptail"):
            self.cmd = "whiptail"
        else:
            print("FEHLER: Weder dialog noch whiptail gefunden!")
            sys.exit(1)

    def _run(self, args: list, capture: bool = True) -> Tuple[int, str]:
        """Dialog-Befehl ausführen, Ergebnis von stderr lesen."""
        full = [self.cmd] + args
        log(f"Dialog: {' '.join(full)}", "DEBUG")
        proc = subprocess.run(
            full,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE if not capture else None,
            text=True,
        )
        output = (proc.stderr or "").strip()
        return proc.returncode, output

    def msgbox(self, text: str, height: int = 12, width: int = 60) -> bool:
        code, _ = self._run([
            "--title", TITLE,
            "--msgbox", text,
            str(height), str(width),
        ])
        return code == 0

    def yesno(self, text: str, height: int = 12, width: int = 60,
              yes_label: str = "Ja", no_label: str = "Nein") -> bool:
        code, _ = self._run([
            "--title", TITLE,
            "--yes-label", yes_label,
            "--no-label", no_label,
            "--yesno", text,
            str(height), str(width),
        ])
        return code == 0

    def menu(self, text: str, choices: list, height: int = 18,
             width: int = 70, menu_height: int = 8) -> Optional[str]:
        args = [
            "--title", TITLE,
            "--menu", text,
            str(height), str(width), str(menu_height),
        ]
        for tag, desc in choices:
            args.extend([tag, desc])
        code, output = self._run(args)
        return output if code == 0 else None

    def inputbox(self, text: str, default: str = "",
                 height: int = 10, width: int = 60) -> Optional[str]:
        code, output = self._run([
            "--title", TITLE,
            "--inputbox", text,
            str(height), str(width), default,
        ])
        return output if code == 0 else None

    def passwordbox(self, text: str, height: int = 10,
                    width: int = 60) -> Optional[str]:
        code, output = self._run([
            "--title", TITLE,
            "--passwordbox", text,
            str(height), str(width),
        ])
        return output if code == 0 else None

    def gauge(self, text: str, percent: int = 0,
              height: int = 8, width: int = 60):
        """Gibt einen Popen zurück, schreibe Prozente in stdin."""
        proc = subprocess.Popen(
            [self.cmd, "--title", TITLE, "--gauge", text,
             str(height), str(width), str(percent)],
            stdin=subprocess.PIPE,
            text=True,
        )
        return proc

    def radiolist(self, text: str, choices: list, height: int = 18,
                  width: int = 70, list_height: int = 6) -> Optional[str]:
        args = [
            "--title", TITLE,
            "--radiolist", text,
            str(height), str(width), str(list_height),
        ]
        for tag, desc, on in choices:
            args.extend([tag, desc, "ON" if on else "OFF"])
        code, output = self._run(args)
        return output if code == 0 else None


# ─── Datenklassen ────────────────────────────────────────────────

@dataclass
class DiskInfo:
    device: str
    size_bytes: int
    size_human: str
    model: str
    transport: str  # sata, nvme, usb, ...
    removable: bool

    @property
    def size_gb(self) -> float:
        return self.size_bytes / (1024 ** 3)


@dataclass
class InstallConfig:
    target_disk: str = ""
    install_mode: str = "erase"      # erase | alongside | manual
    filesystem: str = "btrfs"        # btrfs | ext4 | zfs
    boot_part: str = ""
    root_part: str = ""
    hostname: str = "ghostshell"
    username: str = "ghost"
    password: str = ""
    timezone: str = "Europe/Berlin"
    locale: str = "de_DE.UTF-8"
    enable_ssh: bool = True
    enable_snapshots: bool = True     # BTRFS-Snapshots


# ─── Disk-Erkennung ─────────────────────────────────────────────

def detect_disks() -> List[DiskInfo]:
    """Alle installierbaren Datenträger erkennen."""
    disks = []
    try:
        result = subprocess.run(
            ["lsblk", "-J", "-b", "-d", "-o",
             "NAME,SIZE,MODEL,TRAN,TYPE,RM,HOTPLUG"],
            capture_output=True, text=True,
        )
        data = json.loads(result.stdout)
        # Boot-Medium identifizieren
        boot_dev = ""
        try:
            mnt = subprocess.run(
                ["findmnt", "-n", "-o", "SOURCE", "/run/archiso/airootfs"],
                capture_output=True, text=True,
            )
            if mnt.stdout.strip():
                boot_dev = re.sub(r"[0-9p]+$", "", mnt.stdout.strip())
        except Exception:
            pass

        for dev in data.get("blockdevices", []):
            if dev.get("type") != "disk":
                continue
            name = dev["name"]
            if name.startswith(("loop", "sr", "rom", "zram")):
                continue

            full_path = f"/dev/{name}"
            # Boot-Medium ausschließen
            if boot_dev and full_path == boot_dev:
                continue

            size = int(dev.get("size", 0))
            if size < MIN_DISK_GB * (1024 ** 3):
                continue

            model = (dev.get("model") or "Unbekannt").strip()
            transport = (dev.get("tran") or "").strip()
            removable = dev.get("rm", False) or dev.get("hotplug", False)

            disks.append(DiskInfo(
                device=full_path,
                size_bytes=size,
                size_human=_human_size(size),
                model=model,
                transport=transport,
                removable=removable,
            ))
    except Exception as e:
        log(f"Disk-Erkennung fehlgeschlagen: {e}", "ERROR")

    return sorted(disks, key=lambda d: d.device)


def _human_size(b: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if b < 1024.0:
            return f"{b:.1f} {unit}"
        b /= 1024.0
    return f"{b:.1f} PB"


# ─── Shell-Helfer ────────────────────────────────────────────────

def run(cmd: str, check: bool = True, env: dict = None) -> subprocess.CompletedProcess:
    """Shell-Befehl ausführen mit Logging."""
    log(f"$ {cmd}")
    merged_env = {**os.environ, **(env or {})}
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, env=merged_env,
    )
    if result.stdout.strip():
        log(f"  stdout: {result.stdout.strip()[:200]}", "DEBUG")
    if result.returncode != 0:
        log(f"  FEHLER (code {result.returncode}): {result.stderr.strip()[:300]}", "ERROR")
        if check:
            raise RuntimeError(f"Befehl fehlgeschlagen: {cmd}")
    return result


def run_quiet(cmd: str) -> bool:
    """Befehl ausführen, nur True/False zurückgeben."""
    try:
        run(cmd, check=True)
        return True
    except Exception:
        return False


# ─── Partitionierung ─────────────────────────────────────────────

def partition_erase(cfg: InstallConfig) -> bool:
    """Festplatte komplett löschen + GPT + EFI + Root."""
    disk = cfg.target_disk
    log(f"Partitioniere {disk} (komplett löschen)...")

    # Alte Signaturen löschen
    run(f"wipefs -af {disk}", check=False)
    run(f"sgdisk -Z {disk}", check=False)
    time.sleep(1)

    # GPT-Tabelle erstellen
    run(f"parted -s {disk} mklabel gpt")

    # Partition 1: EFI System Partition (512 MB)
    run(f"parted -s {disk} mkpart 'EFI' fat32 1MiB 513MiB")
    run(f"parted -s {disk} set 1 esp on")

    # Partition 2: Root (Rest)
    run(f"parted -s {disk} mkpart 'GhostShell' {cfg.filesystem} 513MiB 100%")

    time.sleep(2)
    run("partprobe " + disk, check=False)
    time.sleep(1)

    # Partitionspfade ermitteln
    cfg.boot_part = _find_partition(disk, 1)
    cfg.root_part = _find_partition(disk, 2)

    if not cfg.boot_part or not cfg.root_part:
        log("Partitionen nicht gefunden!", "ERROR")
        return False

    log(f"EFI: {cfg.boot_part}, Root: {cfg.root_part}")
    return True


def partition_alongside(cfg: InstallConfig) -> bool:
    """GhostShell neben bestehendem OS installieren."""
    disk = cfg.target_disk
    log(f"Installiere neben bestehendem System auf {disk}...")

    # Freien Platz am Ende suchen
    result = run(f"parted -s {disk} unit MiB print free", check=False)
    free_spaces = []
    for line in result.stdout.split("\n"):
        if "Free Space" in line:
            parts = line.split()
            try:
                start = int(parts[0].replace("MiB", ""))
                end = int(parts[1].replace("MiB", ""))
                size = end - start
                free_spaces.append((start, end, size))
            except (ValueError, IndexError):
                pass

    # Größten freien Bereich finden
    if not free_spaces:
        log("Kein freier Speicherplatz gefunden!", "ERROR")
        return False

    biggest = max(free_spaces, key=lambda x: x[2])
    if biggest[2] < MIN_DISK_GB * 1024:
        log(f"Nur {biggest[2]} MiB frei, mindestens {MIN_DISK_GB * 1024} MiB nötig!", "ERROR")
        return False

    start = biggest[0]
    # EFI-Partition (512 MiB)
    run(f"parted -s {disk} mkpart 'GhostBoot' fat32 {start}MiB {start + 512}MiB")
    run(f"parted -s {disk} set {{}} esp on".format(
        _count_partitions(disk)
    ), check=False)

    # Root-Partition (Rest)
    run(f"parted -s {disk} mkpart 'GhostShell' {cfg.filesystem} {start + 512}MiB {biggest[1]}MiB")

    time.sleep(2)
    run("partprobe " + disk, check=False)
    time.sleep(1)

    # Letzte 2 Partitionen
    n = _count_partitions(disk)
    cfg.boot_part = _find_partition(disk, n - 1)
    cfg.root_part = _find_partition(disk, n)
    return cfg.boot_part and cfg.root_part


def _find_partition(disk: str, num: int) -> str:
    """Partitionspfad ermitteln (/dev/sda1 oder /dev/nvme0n1p1)."""
    candidates = [
        f"{disk}p{num}",
        f"{disk}{num}",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    # Warte und versuche erneut
    time.sleep(2)
    run("partprobe " + disk, check=False)
    for c in candidates:
        if os.path.exists(c):
            return c
    return ""


def _count_partitions(disk: str) -> int:
    result = run(f"lsblk -n -o NAME {disk}", check=False)
    return max(0, len(result.stdout.strip().split("\n")) - 1)


# ─── Formatierung ────────────────────────────────────────────────

def format_partitions(cfg: InstallConfig) -> bool:
    """Partitionen formatieren."""
    log(f"Formatiere {cfg.boot_part} (FAT32) und {cfg.root_part} ({cfg.filesystem})...")

    # EFI
    run(f"mkfs.vfat -F 32 -n GHOSTBOOT {cfg.boot_part}")

    # Root
    if cfg.filesystem == "btrfs":
        run(f"mkfs.btrfs -f -L ghostshell {cfg.root_part}")
    elif cfg.filesystem == "ext4":
        run(f"mkfs.ext4 -F -L ghostshell {cfg.root_part}")
    elif cfg.filesystem == "zfs":
        # ZFS-Pool erstellen
        run(f"zpool create -f -o ashift=12 "
            f"-O acltype=posixacl -O compression=zstd -O dnodesize=auto "
            f"-O normalization=formD -O relatime=on -O xattr=sa "
            f"-O mountpoint=none ghostpool {cfg.root_part}", check=False)
        run("zfs create -o mountpoint=/ ghostpool/root", check=False)
        run("zfs create -o mountpoint=/home ghostpool/home", check=False)
        run("zpool export ghostpool", check=False)
    else:
        log(f"Unbekanntes Dateisystem: {cfg.filesystem}", "ERROR")
        return False

    log("Formatierung abgeschlossen!")
    return True


# ─── BTRFS Subvolumes ────────────────────────────────────────────

def setup_btrfs_subvolumes(cfg: InstallConfig, mount_point: str) -> bool:
    """BTRFS-Subvolumes für Snapshots erstellen."""
    if cfg.filesystem != "btrfs":
        return True

    log("Erstelle BTRFS-Subvolumes...")

    # Temporär mounten
    run(f"mount {cfg.root_part} {mount_point}")

    # Subvolumes
    subvols = {
        "@":         "/",
        "@home":     "/home",
        "@snapshots": "/.snapshots",
        "@var_log":  "/var/log",
        "@var_cache": "/var/cache",
        "@dbai_data": "/opt/dbai/data",
    }

    for sv in subvols:
        run(f"btrfs subvolume create {mount_point}/{sv}")

    run(f"umount {mount_point}")

    # Jetzt mit Subvolumes mounten
    opts = "compress=zstd:3,noatime,space_cache=v2,ssd"
    run(f"mount -o subvol=@,{opts} {cfg.root_part} {mount_point}")

    for sv, mp in subvols.items():
        if sv == "@":
            continue
        full = f"{mount_point}{mp}"
        os.makedirs(full, exist_ok=True)
        run(f"mount -o subvol={sv},{opts} {cfg.root_part} {full}")

    # EFI mounten
    efi_dir = f"{mount_point}/boot/efi"
    os.makedirs(efi_dir, exist_ok=True)
    run(f"mount {cfg.boot_part} {efi_dir}")

    log("BTRFS-Subvolumes erstellt: " + ", ".join(subvols.keys()))
    return True


def mount_target(cfg: InstallConfig, mount_point: str) -> bool:
    """Zielpartitionen mounten (für nicht-BTRFS)."""
    if cfg.filesystem == "btrfs":
        return setup_btrfs_subvolumes(cfg, mount_point)

    if cfg.filesystem == "zfs":
        run(f"zpool import -R {mount_point} ghostpool")
        efi_dir = f"{mount_point}/boot/efi"
        os.makedirs(efi_dir, exist_ok=True)
        run(f"mount {cfg.boot_part} {efi_dir}")
        return True

    # EXT4
    run(f"mount {cfg.root_part} {mount_point}")
    efi_dir = f"{mount_point}/boot/efi"
    os.makedirs(efi_dir, exist_ok=True)
    run(f"mount {cfg.boot_part} {efi_dir}")
    return True


# ─── System kopieren ─────────────────────────────────────────────

def find_live_root() -> str:
    """SquashFS / Live-Root finden."""
    for path in [LIVE_SQUASHFS] + LIVE_SQUASHFS_ALT:
        if os.path.isdir(path) and os.path.exists(f"{path}/usr"):
            return path
    return "/"


def copy_system(cfg: InstallConfig, mount_point: str, dlg: Dialog) -> bool:
    """System vom Live-Medium auf die Ziel-Festplatte kopieren."""
    source = find_live_root()
    log(f"Kopiere System von {source} nach {mount_point}...")

    # Fortschrittsanzeige
    gauge = dlg.gauge("Kopiere GhostShell OS...", 0)

    try:
        exclude = [
            "--exclude=/proc/*",
            "--exclude=/sys/*",
            "--exclude=/dev/*",
            "--exclude=/tmp/*",
            "--exclude=/run/*",
            "--exclude=/mnt/*",
            "--exclude=/media/*",
            "--exclude=/lost+found",
            "--exclude=/swapfile",
        ]

        # Phase 1: System kopieren (0-60%)
        gauge.stdin.write("5\nXXX\nKopiere Basissystem...\nXXX\n")
        gauge.stdin.flush()

        rsync_cmd = [
            "rsync", "-aHAXx", "--info=progress2", "--no-inc-recursive",
        ] + exclude + [f"{source}/", f"{mount_point}/"]

        proc = subprocess.Popen(
            rsync_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )

        last_pct = 5
        for line in proc.stdout:
            # rsync --info=progress2 gibt "X%" aus
            match = re.search(r"(\d+)%", line)
            if match:
                pct = min(60, int(int(match.group(1)) * 0.6))
                if pct > last_pct:
                    gauge.stdin.write(f"{pct}\nXXX\nKopiere System ({pct}%)...\nXXX\n")
                    gauge.stdin.flush()
                    last_pct = pct

        proc.wait()

        # Phase 2: Verzeichnisse erstellen (60-65%)
        gauge.stdin.write("62\nXXX\nErstelle Verzeichnisstruktur...\nXXX\n")
        gauge.stdin.flush()

        for d in ["proc", "sys", "dev", "tmp", "run", "mnt", "media"]:
            os.makedirs(f"{mount_point}/{d}", exist_ok=True)

        # Phase 3: DBAI-Dateien sicherstellen (65-75%)
        gauge.stdin.write("65\nXXX\nPrüfe DBAI-Komponenten...\nXXX\n")
        gauge.stdin.flush()

        dbai_target = f"{mount_point}/opt/dbai"
        if not os.path.isdir(f"{dbai_target}/schema"):
            log("DBAI-Dateien fehlen, kopiere von /opt/dbai...")
            if os.path.isdir(DBAI_SRC):
                run(f"rsync -a --exclude='node_modules' --exclude='__pycache__' "
                    f"--exclude='.git' --exclude='dist/*.img' "
                    f"{DBAI_SRC}/ {dbai_target}/")

        gauge.stdin.write("75\nXXX\nDBGI-Komponenten installiert\nXXX\n")
        gauge.stdin.flush()

        # Phase 4: fstab generieren (75-80%)
        gauge.stdin.write("78\nXXX\nErstelle fstab...\nXXX\n")
        gauge.stdin.flush()

        _generate_fstab(cfg, mount_point)

        # Phase 5: Konfiguration (80-90%)
        gauge.stdin.write("82\nXXX\nKonfiguriere System...\nXXX\n")
        gauge.stdin.flush()

        _configure_system(cfg, mount_point)

        gauge.stdin.write("90\nXXX\nSystem kopiert!\nXXX\n")
        gauge.stdin.flush()

        gauge.stdin.write("100\n")
        gauge.stdin.flush()
        gauge.stdin.close()
        gauge.wait()

        log("System-Kopie abgeschlossen!")
        return True

    except Exception as e:
        log(f"System-Kopie fehlgeschlagen: {e}", "ERROR")
        try:
            gauge.stdin.close()
            gauge.kill()
        except Exception:
            pass
        return False


def _generate_fstab(cfg: InstallConfig, mount_point: str):
    """fstab generieren."""
    root_uuid = _get_uuid(cfg.root_part)
    boot_uuid = _get_uuid(cfg.boot_part)

    fstab_lines = [
        "# GhostShell OS — /etc/fstab",
        f"# Generiert am {time.strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    if cfg.filesystem == "btrfs":
        opts = "compress=zstd:3,noatime,space_cache=v2,ssd"
        subvols = {
            "@": "/",
            "@home": "/home",
            "@snapshots": "/.snapshots",
            "@var_log": "/var/log",
            "@var_cache": "/var/cache",
            "@dbai_data": "/opt/dbai/data",
        }
        for sv, mp in subvols.items():
            fstab_lines.append(
                f"UUID={root_uuid}  {mp:<20s}  btrfs  subvol={sv},{opts}  0  0"
            )
    elif cfg.filesystem == "zfs":
        fstab_lines.append("# ZFS verwaltet seine Mounts selbst")
        fstab_lines.append("# ghostpool/root  /      zfs  defaults  0  0")
        fstab_lines.append("# ghostpool/home  /home  zfs  defaults  0  0")
    else:
        fstab_lines.append(
            f"UUID={root_uuid}  /  ext4  defaults,noatime  0  1"
        )

    fstab_lines.extend([
        f"UUID={boot_uuid}  /boot/efi  vfat  defaults  0  2",
        "tmpfs  /tmp  tmpfs  defaults,nosuid,nodev,size=2G  0  0",
        "",
    ])

    fstab_path = f"{mount_point}/etc/fstab"
    os.makedirs(os.path.dirname(fstab_path), exist_ok=True)
    with open(fstab_path, "w") as f:
        f.write("\n".join(fstab_lines))

    log("fstab geschrieben")


def _get_uuid(device: str) -> str:
    result = subprocess.run(
        ["blkid", "-s", "UUID", "-o", "value", device],
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def _configure_system(cfg: InstallConfig, mnt: str):
    """System-Grundkonfiguration im Chroot."""

    # Hostname
    with open(f"{mnt}/etc/hostname", "w") as f:
        f.write(cfg.hostname + "\n")
    with open(f"{mnt}/etc/hosts", "w") as f:
        f.write(
            f"127.0.0.1  localhost\n"
            f"127.0.1.1  {cfg.hostname}\n"
            f"::1        localhost\n"
        )

    # Locale
    locale_gen = f"{mnt}/etc/locale.gen"
    if os.path.exists(locale_gen):
        with open(locale_gen, "a") as f:
            f.write(f"\n{cfg.locale} UTF-8\n")
            f.write("en_US.UTF-8 UTF-8\n")

    locale_conf = f"{mnt}/etc/locale.conf"
    with open(locale_conf, "w") as f:
        f.write(f"LANG={cfg.locale}\n")
        f.write("LC_MESSAGES=en_US.UTF-8\n")

    # Timezone
    tz_src = f"/usr/share/zoneinfo/{cfg.timezone}"
    tz_dst = f"{mnt}/etc/localtime"
    if os.path.exists(tz_src):
        if os.path.exists(tz_dst):
            os.remove(tz_dst)
        os.symlink(tz_src, tz_dst)

    # Keyboard
    with open(f"{mnt}/etc/vconsole.conf", "w") as f:
        f.write("KEYMAP=de-latin1\n")

    log("System konfiguriert")


# ─── Chroot-Operationen ─────────────────────────────────────────

def chroot_setup(mnt: str):
    """Chroot-Mounts vorbereiten."""
    for fs_type, target in [
        ("--bind", "dev"),
        ("--bind", "dev/pts"),
        ("-t proc", "proc"),
        ("-t sysfs", "sys"),
        ("--bind", "run"),
    ]:
        full_target = f"{mnt}/{target}"
        os.makedirs(full_target, exist_ok=True)
        if "-t" in fs_type:
            parts = fs_type.split()
            run(f"mount {parts[0]} {parts[1]} {full_target}", check=False)
        else:
            run(f"mount {fs_type} /{target} {full_target}", check=False)


def chroot_cleanup(mnt: str):
    """Chroot-Mounts entfernen."""
    for target in ["proc", "sys", "dev/pts", "dev", "run"]:
        run(f"umount -lf {mnt}/{target}", check=False)


def chroot_run(mnt: str, cmd: str, check: bool = True):
    """Befehl im Chroot ausführen."""
    return run(f"arch-chroot {mnt} bash -c '{cmd}'", check=check)


# ─── Bootloader ──────────────────────────────────────────────────

def install_bootloader(cfg: InstallConfig, mnt: str, dlg: Dialog) -> bool:
    """GRUB-Bootloader installieren."""
    log("Installiere Bootloader (GRUB)...")

    gauge = dlg.gauge("Installiere Bootloader...", 0)

    try:
        chroot_setup(mnt)

        gauge.stdin.write("10\nXXX\nGeneriere locale...\nXXX\n")
        gauge.stdin.flush()
        chroot_run(mnt, "locale-gen", check=False)

        gauge.stdin.write("20\nXXX\nInstalliere GRUB...\nXXX\n")
        gauge.stdin.flush()

        # UEFI oder BIOS erkennen
        is_uefi = os.path.isdir("/sys/firmware/efi")

        if is_uefi:
            chroot_run(mnt,
                "grub-install --target=x86_64-efi "
                "--efi-directory=/boot/efi "
                "--bootloader-id=GhostShell "
                "--removable",
                check=False,
            )
        else:
            chroot_run(mnt,
                f"grub-install --target=i386-pc {cfg.target_disk}",
                check=False,
            )

        gauge.stdin.write("50\nXXX\nKonfiguriere GRUB...\nXXX\n")
        gauge.stdin.flush()

        # GRUB-Konfiguration
        grub_default = f"{mnt}/etc/default/grub"
        with open(grub_default, "w") as f:
            f.write(
                'GRUB_DEFAULT=0\n'
                'GRUB_TIMEOUT=3\n'
                'GRUB_TIMEOUT_STYLE=menu\n'
                'GRUB_DISTRIBUTOR="GhostShell OS"\n'
                'GRUB_CMDLINE_LINUX_DEFAULT="quiet splash loglevel=3"\n'
                'GRUB_CMDLINE_LINUX=""\n'
                'GRUB_GFXMODE=auto\n'
                'GRUB_GFXPAYLOAD_LINUX=keep\n'
                'GRUB_TERMINAL_OUTPUT=gfxterm\n'
                'GRUB_DISABLE_OS_PROBER=false\n'
            )

        gauge.stdin.write("70\nXXX\nGeneriere grub.cfg...\nXXX\n")
        gauge.stdin.flush()

        chroot_run(mnt, "grub-mkconfig -o /boot/grub/grub.cfg", check=False)

        gauge.stdin.write("85\nXXX\nErstelle initramfs...\nXXX\n")
        gauge.stdin.flush()

        # mkinitcpio mit BTRFS-Hook
        if cfg.filesystem == "btrfs":
            mkinit_conf = f"{mnt}/etc/mkinitcpio.conf"
            if os.path.exists(mkinit_conf):
                with open(mkinit_conf, "r") as f:
                    content = f.read()
                content = content.replace(
                    "HOOKS=(base udev",
                    "HOOKS=(base udev btrfs",
                )
                with open(mkinit_conf, "w") as f:
                    f.write(content)

        chroot_run(mnt, "mkinitcpio -P", check=False)

        gauge.stdin.write("100\nXXX\nBootloader installiert!\nXXX\n")
        gauge.stdin.flush()
        gauge.stdin.close()
        gauge.wait()

        chroot_cleanup(mnt)
        log("Bootloader installiert!")
        return True

    except Exception as e:
        log(f"Bootloader-Installation fehlgeschlagen: {e}", "ERROR")
        try:
            gauge.stdin.close()
            gauge.kill()
        except Exception:
            pass
        chroot_cleanup(mnt)
        return False


# ─── Benutzer einrichten ─────────────────────────────────────────

def setup_user(cfg: InstallConfig, mnt: str) -> bool:
    """Benutzer erstellen und konfigurieren."""
    log(f"Erstelle Benutzer '{cfg.username}'...")

    chroot_setup(mnt)

    try:
        # Benutzer erstellen
        chroot_run(mnt,
            f"useradd -m -s /bin/bash "
            f"-G wheel,audio,video,input,render,storage "
            f"{cfg.username}",
            check=False,
        )

        # Passwort setzen
        chroot_run(mnt,
            f"echo '{cfg.username}:{cfg.password}' | chpasswd",
            check=False,
        )

        # Root-Passwort = gleiches Passwort
        chroot_run(mnt,
            f"echo 'root:{cfg.password}' | chpasswd",
            check=False,
        )

        # Sudo konfigurieren
        sudoers = f"{mnt}/etc/sudoers.d/ghostshell"
        os.makedirs(os.path.dirname(sudoers), exist_ok=True)
        with open(sudoers, "w") as f:
            f.write(f"{cfg.username} ALL=(ALL) NOPASSWD: ALL\n")
        os.chmod(sudoers, 0o440)

        log(f"Benutzer '{cfg.username}' erstellt")
        return True

    except Exception as e:
        log(f"Benutzer-Einrichtung fehlgeschlagen: {e}", "ERROR")
        return False
    finally:
        chroot_cleanup(mnt)


# ─── Services konfigurieren ──────────────────────────────────────

def setup_services(cfg: InstallConfig, mnt: str) -> bool:
    """Systemd-Services für GhostShell konfigurieren."""
    log("Konfiguriere Systemd-Services...")

    chroot_setup(mnt)

    try:
        # DBAI systemd Services kopieren
        service_src = f"{mnt}/opt/dbai/config/systemd"
        service_dst = f"{mnt}/etc/systemd/system"

        if os.path.isdir(service_src):
            for f in os.listdir(service_src):
                if f.endswith((".service", ".target")):
                    shutil.copy2(f"{service_src}/{f}", f"{service_dst}/{f}")
                    log(f"  Service kopiert: {f}")

        # Services aktivieren
        services = [
            "NetworkManager",
            "postgresql",
            "dbai.target",
            "dbai-firstboot.service",
        ]
        if cfg.enable_ssh:
            services.append("sshd")

        for svc in services:
            chroot_run(mnt, f"systemctl enable {svc}", check=False)

        # Installer-Service DEAKTIVIEREN im Ziel
        chroot_run(mnt, "systemctl disable ghostshell-installer.service", check=False)
        run(f"rm -f {mnt}/etc/systemd/system/ghostshell-installer.service", check=False)

        # Auto-Login für Kiosk
        autologin_dir = f"{mnt}/etc/systemd/system/getty@tty1.service.d"
        os.makedirs(autologin_dir, exist_ok=True)
        with open(f"{autologin_dir}/autologin.conf", "w") as f:
            f.write(
                "[Service]\n"
                "ExecStart=\n"
                f"ExecStart=-/sbin/agetty --autologin {cfg.username} "
                "--noclear %I $TERM\n"
            )

        # Kiosk .bash_profile
        bash_profile = f"{mnt}/home/{cfg.username}/.bash_profile"
        os.makedirs(os.path.dirname(bash_profile), exist_ok=True)
        with open(bash_profile, "w") as f:
            f.write(
                "# GhostShell OS — Auto-Start Kiosk\n"
                'if [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then\n'
                "    exec startx -- -nocursor 2>/var/log/dbai/xorg.log\n"
                "fi\n"
            )

        # .xinitrc
        xinitrc = f"{mnt}/home/{cfg.username}/.xinitrc"
        with open(xinitrc, "w") as f:
            f.write(
                "#!/bin/bash\n"
                "xset s off; xset s noblank; xset -dpms\n"
                "unclutter -idle 3 -root &\n"
                "openbox --config-file /dev/null &\n"
                "sleep 0.5\n"
                '# Warte auf DBAI Web-Server\n'
                "for i in $(seq 1 60); do\n"
                '    curl -sf http://localhost:3000/api/health > /dev/null && break\n'
                "    sleep 1\n"
                "done\n"
                "exec chromium --kiosk --app=http://localhost:3000 "
                "--no-first-run --disable-translate --disable-infobars "
                "--disable-component-update --noerrdialogs "
                "--user-data-dir=/home/${USER}/.dbai-browser\n"
            )
        os.chmod(xinitrc, 0o755)

        # Eigentümer setzen
        chroot_run(mnt,
            f"chown -R {cfg.username}:{cfg.username} /home/{cfg.username}",
            check=False,
        )

        # First-Boot-Marker entfernen
        run(f"rm -f {mnt}/opt/dbai/.first-boot-done", check=False)

        # BTRFS Snapshot-Timer (wenn BTRFS)
        if cfg.filesystem == "btrfs" and cfg.enable_snapshots:
            _setup_btrfs_snapshots(mnt)

        log("Services konfiguriert!")
        return True

    except Exception as e:
        log(f"Service-Konfiguration fehlgeschlagen: {e}", "ERROR")
        return False
    finally:
        chroot_cleanup(mnt)


def _setup_btrfs_snapshots(mnt: str):
    """BTRFS-Snapshot-Timer erstellen."""
    # Snapshot-Skript
    snap_script = f"{mnt}/usr/local/bin/ghostshell-snapshot"
    with open(snap_script, "w") as f:
        f.write(
            '#!/bin/bash\n'
            '# GhostShell OS — BTRFS Snapshot\n'
            'SNAP_DIR="/.snapshots"\n'
            'TIMESTAMP=$(date +%Y%m%d-%H%M%S)\n'
            'REASON="${1:-auto}"\n'
            'mkdir -p "$SNAP_DIR"\n'
            'btrfs subvolume snapshot -r / "$SNAP_DIR/${TIMESTAMP}_${REASON}"\n'
            '# Alte Snapshots aufräumen (behalte letzte 20)\n'
            'ls -1d "$SNAP_DIR"/*_auto 2>/dev/null | head -n -20 | '
            'xargs -r btrfs subvolume delete\n'
            'echo "Snapshot erstellt: ${TIMESTAMP}_${REASON}"\n'
        )
    os.chmod(snap_script, 0o755)

    # Systemd-Timer
    timer_path = f"{mnt}/etc/systemd/system/ghostshell-snapshot.timer"
    with open(timer_path, "w") as f:
        f.write(
            "[Unit]\n"
            "Description=GhostShell OS — Stündlicher BTRFS-Snapshot\n\n"
            "[Timer]\n"
            "OnCalendar=hourly\n"
            "Persistent=true\n\n"
            "[Install]\n"
            "WantedBy=timers.target\n"
        )

    service_path = f"{mnt}/etc/systemd/system/ghostshell-snapshot.service"
    with open(service_path, "w") as f:
        f.write(
            "[Unit]\n"
            "Description=GhostShell OS — BTRFS Snapshot erstellen\n\n"
            "[Service]\n"
            "Type=oneshot\n"
            "ExecStart=/usr/local/bin/ghostshell-snapshot auto\n"
        )


# ─── Cleanup ─────────────────────────────────────────────────────

def cleanup_mounts(mnt: str, cfg: InstallConfig):
    """Alle Mounts sauber trennen."""
    log("Räume Mounts auf...")

    chroot_cleanup(mnt)

    # BTRFS-Subvolumes
    if cfg.filesystem == "btrfs":
        for subvol in ["opt/dbai/data", "var/cache", "var/log",
                       ".snapshots", "home", "boot/efi"]:
            run(f"umount -lf {mnt}/{subvol}", check=False)

    run(f"umount -lf {mnt}/boot/efi", check=False)
    run(f"umount -lf {mnt}", check=False)

    if cfg.filesystem == "zfs":
        run("zpool export ghostpool", check=False)

    run("sync")


# ═══════════════════════════════════════════════════════════════════
# HAUPT-INSTALLER
# ═══════════════════════════════════════════════════════════════════

class GhostShellInstaller:
    """Hauptklasse des Installers."""

    def __init__(self):
        self.dlg = Dialog()
        self.cfg = InstallConfig()
        self.mount_point = "/mnt/ghostshell"

    def run(self):
        """Installer-Hauptablauf."""
        try:
            if os.geteuid() != 0:
                self.dlg.msgbox(
                    "Der Installer muss als root gestartet werden!\n\n"
                    "  sudo python3 ghostshell-installer.py"
                )
                sys.exit(1)

            # Log starten
            with open(LOG_FILE, "w") as f:
                f.write(f"GhostShell OS Installer v{VERSION}\n")
                f.write(f"Start: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            if not self.step_welcome():
                return
            if not self.step_select_disk():
                return
            if not self.step_install_mode():
                return
            if not self.step_select_filesystem():
                return
            if not self.step_user_setup():
                return
            if not self.step_confirm():
                return
            if not self.step_install():
                return
            self.step_finish()

        except KeyboardInterrupt:
            self.dlg.msgbox("Installation abgebrochen.")
            log("Abgebrochen durch Benutzer", "WARN")
        except Exception as e:
            log(f"Fataler Fehler: {e}", "ERROR")
            self.dlg.msgbox(
                f"Fataler Fehler!\n\n{str(e)[:200]}\n\n"
                f"Log: {LOG_FILE}"
            )

    # ─── Schritt 1: Willkommen ───────────────────────────────────

    def step_welcome(self) -> bool:
        return self.dlg.yesno(
            "╔══════════════════════════════════════╗\n"
            "║   🧠 GhostShell OS — Installer       ║\n"
            "╚══════════════════════════════════════╝\n\n"
            "Willkommen! Dieses Programm installiert\n"
            "GhostShell OS auf deinem Computer.\n\n"
            "Was passiert:\n"
            "  1. Festplatte auswählen\n"
            "  2. Dateisystem wählen (BTRFS/EXT4/ZFS)\n"
            "  3. System kopieren & konfigurieren\n"
            "  4. Bootloader installieren (GRUB)\n"
            "  5. Benutzer einrichten\n"
            "  6. Neustart in GhostShell OS\n\n"
            f"Version: {VERSION}\n\n"
            "Fortfahren?",
            height=22, width=58,
            yes_label="Installieren",
            no_label="Abbrechen",
        )

    # ─── Schritt 2: Festplatte wählen ────────────────────────────

    def step_select_disk(self) -> bool:
        disks = detect_disks()
        if not disks:
            self.dlg.msgbox(
                "Keine geeignete Festplatte gefunden!\n\n"
                f"Mindestgröße: {MIN_DISK_GB} GB\n"
                "USB-Boot-Medium wird ausgeschlossen.\n\n"
                "Tipp: Schließe eine Festplatte an und starte den Installer neu."
            )
            return False

        choices = []
        for d in disks:
            transport = f"[{d.transport.upper()}]" if d.transport else ""
            removable = " (USB)" if d.removable else ""
            desc = f"{d.size_human}  {d.model} {transport}{removable}"
            choices.append((d.device, desc))

        chosen = self.dlg.menu(
            "Auf welche Festplatte soll GhostShell OS\n"
            "installiert werden?\n\n"
            f"⚠  Empfohlen: ≥{RECOMMENDED_DISK_GB} GB\n"
            "   Minimum:   8 GB",
            choices,
        )

        if not chosen:
            return False

        self.cfg.target_disk = chosen

        # Disk-Objekt für Anzeige
        self.selected_disk = next(d for d in disks if d.device == chosen)
        return True

    # ─── Schritt 3: Installationsmodus ───────────────────────────

    def step_install_mode(self) -> bool:
        d = self.selected_disk
        mode = self.dlg.menu(
            f"Ziel: {d.device}  ({d.size_human}, {d.model})\n\n"
            "Wie soll installiert werden?",
            [
                ("erase",     "✖  Festplatte löschen — GhostShell OS pur"),
                ("alongside", "⊞  Neben bestehendem System (Dual-Boot)"),
                ("manual",    "⚙  Manuelle Partitionierung (Experten)"),
            ],
        )

        if not mode:
            return False

        self.cfg.install_mode = mode

        # Warnung bei Erase
        if mode == "erase":
            return self.dlg.yesno(
                "⚠  WARNUNG — DATENVERLUST! ⚠\n\n"
                f"Alle Daten auf {d.device} werden\n"
                "UNWIDERRUFLICH GELÖSCHT!\n\n"
                f"Festplatte: {d.device}\n"
                f"Größe:      {d.size_human}\n"
                f"Modell:     {d.model}\n\n"
                "Wirklich fortfahren?",
                height=16, width=55,
                yes_label="Ja, LÖSCHEN",
                no_label="Abbrechen",
            )

        return True

    # ─── Schritt 4: Dateisystem wählen ───────────────────────────

    def step_select_filesystem(self) -> bool:
        fs = self.dlg.radiolist(
            "Welches Dateisystem soll verwendet werden?\n\n"
            "BTRFS wird empfohlen — es unterstützt:\n"
            "  • Snapshots (Rollback/Undo)\n"
            "  • Transparente Kompression\n"
            "  • Copy-on-Write\n"
            "  • Online Defragmentierung",
            [
                ("btrfs", "BTRFS — Snapshots, Kompression, CoW (empfohlen)", True),
                ("ext4",  "EXT4  — Klassisch, bewährt, schnell", False),
                ("zfs",   "ZFS   — Enterprise, Pools, RAID-Z (experimentell)", False),
            ],
        )

        if not fs:
            return False

        self.cfg.filesystem = fs

        # BTRFS Snapshot-Option
        if fs == "btrfs":
            self.cfg.enable_snapshots = self.dlg.yesno(
                "BTRFS-Snapshots aktivieren?\n\n"
                "Snapshots erstellen stündlich automatisch\n"
                "eine Sicherungskopie des Systemzustands.\n\n"
                "Du kannst jederzeit zu einem früheren\n"
                "Zustand zurückkehren (Rollback).\n\n"
                "Empfohlen: Ja",
                yes_label="Aktivieren",
                no_label="Deaktivieren",
            )

        return True

    # ─── Schritt 5: Benutzer einrichten ──────────────────────────

    def step_user_setup(self) -> bool:
        # Hostname
        hostname = self.dlg.inputbox(
            "Wie soll dein Computer heißen?\n\n"
            "Dies ist der Netzwerkname des Systems.",
            default="ghostshell",
        )
        if hostname is None:
            return False
        self.cfg.hostname = hostname or "ghostshell"

        # Benutzername
        username = self.dlg.inputbox(
            "Wähle einen Benutzernamen.\n\n"
            "Dieser wird für die Anmeldung verwendet.",
            default="ghost",
        )
        if username is None:
            return False
        self.cfg.username = username or "ghost"

        # Passwort
        while True:
            pw1 = self.dlg.passwordbox("Passwort eingeben:")
            if pw1 is None:
                return False
            if len(pw1) < 4:
                self.dlg.msgbox("Passwort muss mindestens 4 Zeichen lang sein!")
                continue

            pw2 = self.dlg.passwordbox("Passwort bestätigen:")
            if pw2 is None:
                return False
            if pw1 != pw2:
                self.dlg.msgbox("Passwörter stimmen nicht überein!")
                continue

            self.cfg.password = pw1
            break

        # Zeitzone
        tz = self.dlg.menu(
            "Zeitzone wählen:",
            [
                ("Europe/Berlin",    "Deutschland, Österreich, Schweiz"),
                ("Europe/London",    "Großbritannien"),
                ("America/New_York", "US Ostküste"),
                ("America/Los_Angeles", "US Westküste"),
                ("Asia/Tokyo",       "Japan"),
                ("UTC",              "UTC (Server)"),
            ],
        )
        if tz:
            self.cfg.timezone = tz

        # SSH
        self.cfg.enable_ssh = self.dlg.yesno(
            "SSH-Zugang aktivieren?\n\n"
            "Ermöglicht Fernzugriff über das Netzwerk.\n"
            "Empfohlen für Server und Fernwartung.",
            yes_label="Aktivieren",
            no_label="Deaktivieren",
        )

        return True

    # ─── Schritt 6: Bestätigung ──────────────────────────────────

    def step_confirm(self) -> bool:
        d = self.selected_disk
        mode_text = {
            "erase": "Festplatte LÖSCHEN",
            "alongside": "Neben bestehendem System",
            "manual": "Manuelle Partitionierung",
        }
        snap_text = "Ja" if self.cfg.enable_snapshots else "Nein"
        ssh_text = "Ja" if self.cfg.enable_ssh else "Nein"

        return self.dlg.yesno(
            "═══ Zusammenfassung ═══\n\n"
            f"Festplatte:    {d.device} ({d.size_human})\n"
            f"Modell:        {d.model}\n"
            f"Modus:         {mode_text.get(self.cfg.install_mode, '?')}\n"
            f"Dateisystem:   {self.cfg.filesystem.upper()}\n"
            f"Snapshots:     {snap_text}\n"
            f"Hostname:      {self.cfg.hostname}\n"
            f"Benutzer:      {self.cfg.username}\n"
            f"Zeitzone:      {self.cfg.timezone}\n"
            f"SSH:           {ssh_text}\n\n"
            "Installation jetzt starten?",
            height=20, width=55,
            yes_label="INSTALLIEREN",
            no_label="Abbrechen",
        )

    # ─── Schritt 7: Installation ─────────────────────────────────

    def step_install(self) -> bool:
        os.makedirs(self.mount_point, exist_ok=True)

        steps = [
            ("Partitionierung...",     self._do_partition),
            ("Formatierung...",        self._do_format),
            ("Mounten...",             self._do_mount),
            ("System kopieren...",     self._do_copy),
            ("Bootloader...",          self._do_bootloader),
            ("Benutzer einrichten...", self._do_user),
            ("Services...",            self._do_services),
        ]

        for i, (desc, func) in enumerate(steps):
            log(f"Phase {i+1}/{len(steps)}: {desc}")
            success = func()
            if not success:
                self.dlg.msgbox(
                    f"Fehler in Phase {i+1}: {desc}\n\n"
                    f"Die Installation wurde abgebrochen.\n"
                    f"Log: {LOG_FILE}"
                )
                cleanup_mounts(self.mount_point, self.cfg)
                return False

        cleanup_mounts(self.mount_point, self.cfg)
        return True

    def _do_partition(self) -> bool:
        if self.cfg.install_mode == "erase":
            return partition_erase(self.cfg)
        elif self.cfg.install_mode == "alongside":
            return partition_alongside(self.cfg)
        elif self.cfg.install_mode == "manual":
            # Manuell: cfdisk starten
            subprocess.run(["cfdisk", self.cfg.target_disk])
            bp = self.dlg.inputbox(
                "Boot-Partition (EFI):",
                default=f"{self.cfg.target_disk}1",
            )
            rp = self.dlg.inputbox(
                "Root-Partition:",
                default=f"{self.cfg.target_disk}2",
            )
            if bp and rp:
                self.cfg.boot_part = bp
                self.cfg.root_part = rp
                return True
            return False
        return False

    def _do_format(self) -> bool:
        return format_partitions(self.cfg)

    def _do_mount(self) -> bool:
        return mount_target(self.cfg, self.mount_point)

    def _do_copy(self) -> bool:
        return copy_system(self.cfg, self.mount_point, self.dlg)

    def _do_bootloader(self) -> bool:
        return install_bootloader(self.cfg, self.mount_point, self.dlg)

    def _do_user(self) -> bool:
        return setup_user(self.cfg, self.mount_point)

    def _do_services(self) -> bool:
        return setup_services(self.cfg, self.mount_point)

    # ─── Schritt 8: Fertig ───────────────────────────────────────

    def step_finish(self):
        reboot = self.dlg.yesno(
            "╔══════════════════════════════════════╗\n"
            "║   ✅ Installation abgeschlossen!      ║\n"
            "╚══════════════════════════════════════╝\n\n"
            f"GhostShell OS wurde auf {self.cfg.target_disk}\n"
            "installiert.\n\n"
            f"Dateisystem:  {self.cfg.filesystem.upper()}\n"
            f"Benutzer:     {self.cfg.username}\n"
            f"Hostname:     {self.cfg.hostname}\n\n"
            "Beim nächsten Start:\n"
            "  1. BIOS/UEFI lädt GRUB\n"
            "  2. Linux-Kernel startet\n"
            "  3. PostgreSQL startet (Datenbank-Kernel)\n"
            "  4. GhostShell Web-Dashboard startet\n"
            "  5. Chromium öffnet im Kiosk-Modus\n\n"
            "USB-Stick entfernen und neustarten?",
            height=22, width=55,
            yes_label="Neustart",
            no_label="Shell öffnen",
        )

        if reboot:
            log("Neustart eingeleitet...")
            run("reboot", check=False)
        else:
            log("Installation abgeschlossen — Shell offen.")
            self.dlg.msgbox(
                "Du kannst jetzt eine Shell öffnen.\n\n"
                "Das installierte System ist unter:\n"
                f"  {self.mount_point}\n\n"
                "Zum Neustarten:\n"
                "  sudo reboot"
            )


# ═══════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    installer = GhostShellInstaller()
    installer.run()
