#!/bin/bash
# =============================================================================
# GhostShell OS — ISO Builder (build-iso.sh)
# =============================================================================
# Erstellt ein bootfähiges Live-ISO mit vorinstalliertem GhostShell OS.
#
# Unterstützte Build-Modi:
#   Arch Linux:  mkarchiso mit Custom-Profil    (--arch)
#   Debian:      debootstrap + SquashFS + GRUB  (--debian, Standard)
#
# Das ISO enthält:
#   - Minimales Linux (Arch oder Debian Bookworm)
#   - PostgreSQL 16+ mit pgvector
#   - Python 3.11+ Backend (FastAPI/Uvicorn)
#   - React Frontend (vorgebaut)
#   - GhostShell Installer (Python TUI)
#   - BTRFS/EXT4/ZFS Support
#   - Chromium Kiosk-Modus
#   - NVIDIA-Treiber (optional)
#
# Nutzung:
#   sudo bash scripts/build-iso.sh                  # Standard (Debian)
#   sudo bash scripts/build-iso.sh --arch            # Arch-basiert (mkarchiso)
#   sudo bash scripts/build-iso.sh --minimal         # Ohne NVIDIA
#   sudo bash scripts/build-iso.sh --output /tmp     # Anderes Ausgabeverzeichnis
#   sudo bash scripts/build-iso.sh --test            # Nach Build QEMU starten
# =============================================================================

set -euo pipefail

# ─── Konfiguration ────────────────────────────────────────────────

DBAI_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="/tmp/ghostshell-iso-build"
OUTPUT_DIR="${DBAI_ROOT}/dist"
ISO_DATE="$(date +%Y%m%d)"
ISO_NAME="ghostshell-os-${ISO_DATE}.iso"
BASE="debian"                # debian | arch
INCLUDE_NVIDIA=true
INCLUDE_ZFS=false
AUTO_TEST=false
ARCH="x86_64"

# ─── Argumente ────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
    case $1 in
        --arch)       BASE="arch";          shift ;;
        --debian)     BASE="debian";        shift ;;
        --minimal)    INCLUDE_NVIDIA=false;  shift ;;
        --nvidia)     INCLUDE_NVIDIA=true;   shift ;;
        --zfs)        INCLUDE_ZFS=true;      shift ;;
        --test)       AUTO_TEST=true;        shift ;;
        --output)     OUTPUT_DIR="$2";       shift 2 ;;
        --name)       ISO_NAME="$2";         shift 2 ;;
        --arm64|--rpi)
            echo "→ Für ARM64/Raspberry Pi:"
            echo "  sudo bash scripts/build-arm-image.sh $*"
            exit 0 ;;
        -h|--help)
            echo "GhostShell OS — ISO Builder"
            echo ""
            echo "  --arch       Arch-Linux-basiertes ISO (mkarchiso)"
            echo "  --debian     Debian-basiertes ISO (Standard)"
            echo "  --minimal    Ohne NVIDIA-Treiber"
            echo "  --zfs        ZFS-Support einbauen"
            echo "  --test       Nach Build in QEMU testen"
            echo "  --output DIR Ausgabe-Verzeichnis"
            echo "  --name FILE  ISO-Dateiname"
            exit 0 ;;
        *)
            echo "Unbekannte Option: $1 (--help für Hilfe)"
            exit 1 ;;
    esac
done

# ─── Banner ───────────────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║     🧠 GhostShell OS — ISO Builder                  ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  Base:      ${BASE}                                  "
echo "║  NVIDIA:    ${INCLUDE_NVIDIA}                        "
echo "║  ZFS:       ${INCLUDE_ZFS}                           "
echo "║  Arch:      ${ARCH}                                  "
echo "║  Output:    ${OUTPUT_DIR}/${ISO_NAME}                "
echo "║  QEMU-Test: ${AUTO_TEST}                             "
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ─── Root-Check ───────────────────────────────────────────────────

if [[ $EUID -ne 0 ]]; then
    echo "❌ Root-Rechte erforderlich!"
    echo "   sudo bash $0 $*"
    exit 1
fi

# ─── Build-Tools prüfen ──────────────────────────────────────────

check_deps_debian() {
    local missing=()
    for cmd in debootstrap mksquashfs xorriso grub-mkrescue; do
        command -v "$cmd" &>/dev/null || missing+=("$cmd")
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "⚠  Fehlende Tools: ${missing[*]}"
        echo "→  Installiere Build-Abhängigkeiten..."
        apt-get update -qq
        apt-get install -y --no-install-recommends \
            debootstrap squashfs-tools xorriso \
            grub-pc-bin grub-efi-amd64-bin \
            mtools dosfstools genisoimage rsync \
            isolinux syslinux-common
    fi
}

check_deps_arch() {
    if ! command -v mkarchiso &>/dev/null; then
        echo "⚠  mkarchiso nicht gefunden."
        if command -v pacman &>/dev/null; then
            pacman -S --noconfirm archiso
        else
            echo "❌ Arch-Build benötigt ein Arch-Linux-System mit archiso."
            echo "   Alternativ: --debian für Debian-basierten Build."
            exit 1
        fi
    fi
}

# ─── Cleanup ──────────────────────────────────────────────────────

cleanup() {
    echo "→ Räume auf..."
    for mp in proc sys dev/pts dev run; do
        umount -lf "${BUILD_DIR}/rootfs/${mp}" 2>/dev/null || true
    done
    losetup -D 2>/dev/null || true
    rm -rf "${BUILD_DIR}" 2>/dev/null || true
}
trap cleanup EXIT

# ─── Frontend bauen ───────────────────────────────────────────────

build_frontend() {
    echo "═══ Frontend Build ═══"
    local frontend="${DBAI_ROOT}/frontend"

    if [[ -f "${frontend}/dist/index.html" ]]; then
        echo "→ Frontend-Build existiert bereits."
        return 0
    fi

    if command -v npm &>/dev/null; then
        echo "→ Baue Frontend..."
        cd "$frontend"
        npm ci --production 2>/dev/null || npm install
        npx vite build
        cd "$DBAI_ROOT"
    else
        echo "⚠  npm nicht gefunden — Frontend-Build wird übersprungen."
    fi
}

# ═══════════════════════════════════════════════════════════════════
#  DEBIAN BUILD
# ═══════════════════════════════════════════════════════════════════

build_debian_rootfs() {
    echo "═══ Phase 1/7: Debian Root-FS (debootstrap) ═══"
    mkdir -p "${BUILD_DIR}/rootfs"

    debootstrap --arch=amd64 --variant=minbase \
        --include=systemd,systemd-sysv,dbus,locales,sudo,curl,wget,ca-certificates,apt-transport-https,gnupg \
        bookworm "${BUILD_DIR}/rootfs" http://deb.debian.org/debian

    mount --bind /dev       "${BUILD_DIR}/rootfs/dev"
    mount --bind /dev/pts   "${BUILD_DIR}/rootfs/dev/pts"
    mount -t proc proc      "${BUILD_DIR}/rootfs/proc"
    mount -t sysfs sys      "${BUILD_DIR}/rootfs/sys"

    local nvidia_install=""
    if $INCLUDE_NVIDIA; then
        nvidia_install="apt-get install -y --no-install-recommends nvidia-driver nvidia-smi 2>/dev/null || true"
    fi

    local zfs_install=""
    if $INCLUDE_ZFS; then
        zfs_install="apt-get install -y --no-install-recommends zfsutils-linux 2>/dev/null || true"
    fi

    chroot "${BUILD_DIR}/rootfs" bash -c "
        export DEBIAN_FRONTEND=noninteractive

        # PostgreSQL Repo
        curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | \
            gpg --dearmor -o /usr/share/keyrings/postgresql.gpg 2>/dev/null || true
        echo 'deb [signed-by=/usr/share/keyrings/postgresql.gpg] http://apt.postgresql.org/pub/repos/apt bookworm-pgdg main' \
            > /etc/apt/sources.list.d/pgdg.list 2>/dev/null || true

        # Node.js Repo
        curl -fsSL https://deb.nodesource.com/setup_20.x | bash - 2>/dev/null || true

        apt-get update

        # Basis-Pakete
        apt-get install -y --no-install-recommends \
            linux-image-amd64 \
            postgresql-16 postgresql-16-pgvector \
            python3 python3-pip python3-venv python3-psutil python3-dev \
            nodejs \
            chromium xserver-xorg xinit x11-xserver-utils openbox unclutter \
            grub-pc grub-efi-amd64-bin efibootmgr \
            btrfs-progs dosfstools e2fsprogs xfsprogs parted gdisk \
            smartmontools lm-sensors pciutils usbutils \
            networkmanager openssh-server \
            rsync htop nano dialog whiptail arch-install-scripts \
            firmware-linux-free \
            initramfs-tools live-boot

        # ZFS (optional)
        ${zfs_install}

        # NVIDIA (optional)
        ${nvidia_install}

        # Cleanup
        apt-get clean
        rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
    "
}

# ═══════════════════════════════════════════════════════════════════
#  ARCH BUILD (mkarchiso)
# ═══════════════════════════════════════════════════════════════════

build_arch_iso() {
    echo "═══ Arch-Build mit mkarchiso ═══"

    local PROFILE="${DBAI_ROOT}/config/archiso"
    local WORK_DIR="${BUILD_DIR}/archiso-work"
    local OUT="${OUTPUT_DIR}"

    mkdir -p "$WORK_DIR" "$OUT"

    # Installer in airootfs kopieren
    cp "${DBAI_ROOT}/scripts/installer.py" \
       "${PROFILE}/airootfs/usr/local/bin/ghostshell-installer.py"
    chmod +x "${PROFILE}/airootfs/usr/local/bin/ghostshell-installer.py"

    # Wrapper-Skript
    cat > "${PROFILE}/airootfs/usr/local/bin/ghostshell-install" << 'WRAPPER'
#!/bin/bash
echo ""
echo "  🧠 GhostShell OS — Installer wird gestartet..."
echo ""
sleep 1
exec python3 /usr/local/bin/ghostshell-installer.py "$@"
WRAPPER
    chmod +x "${PROFILE}/airootfs/usr/local/bin/ghostshell-install"

    # DBAI-Dateien ins Profil kopieren
    echo "→ Kopiere DBAI-Dateien ins Archiso-Profil..."
    local dbai_air="${PROFILE}/airootfs/opt/dbai"
    rm -rf "$dbai_air"
    mkdir -p "$dbai_air"
    rsync -a \
        --exclude='node_modules' \
        --exclude='__pycache__' \
        --exclude='.git' \
        --exclude='dist/*.img' \
        --exclude='dist/*.iso' \
        "${DBAI_ROOT}/" "$dbai_air/"

    # Frontend-Build
    if [[ -d "${DBAI_ROOT}/frontend/dist" ]]; then
        mkdir -p "$dbai_air/frontend/dist"
        cp -r "${DBAI_ROOT}/frontend/dist/"* "$dbai_air/frontend/dist/"
    fi

    # Installer-Service Symlink
    mkdir -p "${PROFILE}/airootfs/etc/systemd/system/multi-user.target.wants"
    ln -sf /etc/systemd/system/ghostshell-installer.service \
        "${PROFILE}/airootfs/etc/systemd/system/multi-user.target.wants/ghostshell-installer.service"

    # Auto-Login
    mkdir -p "${PROFILE}/airootfs/etc/systemd/system/getty@tty1.service.d"
    cat > "${PROFILE}/airootfs/etc/systemd/system/getty@tty1.service.d/autologin.conf" << 'AUTOL'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin root --noclear %I linux
AUTOL

    # Shell-Autostart als Fallback
    mkdir -p "${PROFILE}/airootfs/root"
    cat > "${PROFILE}/airootfs/root/.bash_profile" << 'BASHPR'
# GhostShell OS Live — Installer Auto-Start
if [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then
    if [ -f /usr/local/bin/ghostshell-installer.py ]; then
        clear
        echo "  ╔══════════════════════════════════════╗"
        echo "  ║   🧠 GhostShell OS v1.0              ║"
        echo "  ║   Installer wird gestartet...        ║"
        echo "  ╚══════════════════════════════════════╝"
        sleep 2
        python3 /usr/local/bin/ghostshell-installer.py
    fi
fi
BASHPR

    echo "→ Starte mkarchiso..."
    mkarchiso -v \
        -w "$WORK_DIR" \
        -o "$OUT" \
        "$PROFILE"

    # Umbenennen
    local built_iso
    built_iso=$(ls -t "$OUT"/ghostshell-os-*.iso 2>/dev/null | head -1)
    if [[ -n "$built_iso" && "$built_iso" != "${OUT}/${ISO_NAME}" ]]; then
        mv "$built_iso" "${OUT}/${ISO_NAME}"
    fi

    echo "✅ Arch-ISO erstellt: ${OUT}/${ISO_NAME}"
}

# ═══════════════════════════════════════════════════════════════════
#  DBAI INSTALLATION (in rootfs)
# ═══════════════════════════════════════════════════════════════════

install_dbai_into_rootfs() {
    echo "═══ Phase 2/7: DBAI-Komponenten installieren ═══"
    local rootfs="${BUILD_DIR}/rootfs"
    local target="${rootfs}/opt/dbai"

    mkdir -p "$target"

    echo "→ Kopiere Projektdateien..."
    rsync -a \
        --exclude='node_modules' \
        --exclude='__pycache__' \
        --exclude='.git' \
        --exclude='dist/*.img' \
        --exclude='dist/*.iso' \
        --exclude='*.pyc' \
        "${DBAI_ROOT}/" "$target/"

    # Frontend-Build
    if [[ -d "${DBAI_ROOT}/frontend/dist" ]]; then
        echo "→ Frontend-Build kopieren..."
        mkdir -p "$target/frontend/dist"
        cp -r "${DBAI_ROOT}/frontend/dist/"* "$target/frontend/dist/"
    fi

    # Python venv
    echo "→ Python-Abhängigkeiten..."
    chroot "$rootfs" bash -c "
        python3 -m venv /opt/dbai/.venv 2>/dev/null || true
        if [ -f /opt/dbai/.venv/bin/pip ]; then
            /opt/dbai/.venv/bin/pip install --no-cache-dir \
                fastapi uvicorn[standard] asyncpg psutil \
                psycopg2-binary pynvml aiohttp aiofiles \
                httpx toml jinja2 2>/dev/null || true
        fi
    "

    # Installer kopieren
    echo "→ Installer installieren..."
    cp "${DBAI_ROOT}/scripts/installer.py" \
       "${rootfs}/usr/local/bin/ghostshell-installer.py"
    chmod +x "${rootfs}/usr/local/bin/ghostshell-installer.py"

    # Wrapper
    cat > "${rootfs}/usr/local/bin/ghostshell-install" << 'WRAPPER'
#!/bin/bash
echo "  🧠 GhostShell OS — Installer wird gestartet..."
sleep 1
exec python3 /usr/local/bin/ghostshell-installer.py "$@"
WRAPPER
    chmod +x "${rootfs}/usr/local/bin/ghostshell-install"
}

# ═══════════════════════════════════════════════════════════════════
#  SYSTEMD SERVICES
# ═══════════════════════════════════════════════════════════════════

install_services() {
    echo "═══ Phase 3/7: Systemd-Services konfigurieren ═══"
    local rootfs="${BUILD_DIR}/rootfs"

    # DBAI Services kopieren
    cp "${DBAI_ROOT}/config/systemd/"*.service "${rootfs}/etc/systemd/system/" 2>/dev/null || true
    cp "${DBAI_ROOT}/config/systemd/"*.target  "${rootfs}/etc/systemd/system/" 2>/dev/null || true

    # Installer-Service (nur Live)
    cat > "${rootfs}/etc/systemd/system/ghostshell-installer.service" << 'INS'
[Unit]
Description=GhostShell OS — Live Installer
After=multi-user.target
ConditionPathExists=/usr/local/bin/ghostshell-installer.py
ConditionPathExists=!/opt/dbai/.installed

[Service]
Type=simple
ExecStart=/usr/bin/python3 /usr/local/bin/ghostshell-installer.py
StandardInput=tty
StandardOutput=tty
TTYPath=/dev/tty1
TTYReset=yes
TTYVHangup=yes
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
INS

    # Live-Services aktivieren
    chroot "$rootfs" bash -c "
        systemctl enable NetworkManager 2>/dev/null || true
        systemctl enable ghostshell-installer.service 2>/dev/null || true
    "

    # Auto-Login (root, Live)
    mkdir -p "${rootfs}/etc/systemd/system/getty@tty1.service.d"
    cat > "${rootfs}/etc/systemd/system/getty@tty1.service.d/autologin.conf" << 'AUTOLOG'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin root --noclear %I linux
AUTOLOG

    # Root-Autostart: Installer in .bash_profile
    cat > "${rootfs}/root/.bash_profile" << 'ROOTPROF'
# GhostShell OS — Live Installer Autostart
if [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then
    if [ -f /usr/local/bin/ghostshell-installer.py ] && \
       [ ! -f /opt/dbai/.installed ]; then
        clear
        echo ""
        echo "  ╔══════════════════════════════════════╗"
        echo "  ║   🧠 GhostShell OS v1.0              ║"
        echo "  ║   Installer wird gestartet...        ║"
        echo "  ╚══════════════════════════════════════╝"
        echo ""
        sleep 2
        python3 /usr/local/bin/ghostshell-installer.py
    fi
fi
ROOTPROF
}

# ═══════════════════════════════════════════════════════════════════
#  FIRST-BOOT (für installiertes System)
# ═══════════════════════════════════════════════════════════════════

install_firstboot() {
    echo "═══ Phase 4/7: First-Boot Script ═══"
    local rootfs="${BUILD_DIR}/rootfs"

    mkdir -p "${rootfs}/opt/dbai/scripts"

    cat > "${rootfs}/opt/dbai/scripts/ghostshell-firstboot.sh" << 'FIRSTBOOT'
#!/bin/bash
# =============================================================================
# GhostShell OS — First Boot Initialization
# =============================================================================
set -e
exec > >(tee -a /var/log/dbai/firstboot.log) 2>&1

DBAI="/opt/dbai"
MARKER="$DBAI/.first-boot-done"
LOG_DIR="/var/log/dbai"

if [[ -f "$MARKER" ]]; then
    echo "[First-Boot] Bereits erledigt."
    exit 0
fi

mkdir -p "$LOG_DIR"
echo "═══ GhostShell OS — First Boot $(date) ═══"

# Phase 1: PostgreSQL
echo "[1/6] PostgreSQL initialisieren..."
for i in $(seq 1 30); do
    pg_isready -q && break
    sleep 1
done

if ! pg_isready -q; then
    sudo -u postgres initdb -D /var/lib/postgresql/data 2>/dev/null || true
    systemctl restart postgresql
    sleep 3
fi

sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='dbai_system'" | \
    grep -q 1 || sudo -u postgres psql -c "CREATE ROLE dbai_system WITH LOGIN SUPERUSER PASSWORD 'dbai2026';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='dbai'" | \
    grep -q 1 || sudo -u postgres psql -c "CREATE DATABASE dbai OWNER dbai_system;"

sudo -u postgres psql -d dbai -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null || true
sudo -u postgres psql -d dbai -c "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";" 2>/dev/null || true

# Phase 2: Schema
echo "[2/6] Datenbank-Schemas laden..."
if [[ -d "$DBAI/schema" ]]; then
    for sql in $(ls "$DBAI/schema"/*.sql 2>/dev/null | sort); do
        echo "  → $(basename $sql)"
        sudo -u postgres psql -d dbai -f "$sql" 2>/dev/null || \
            echo "    ⚠ Fehler bei $(basename $sql)"
    done
fi

# Phase 3: PostgreSQL-Config
echo "[3/6] PostgreSQL konfigurieren..."
PG_CONF_DIR=$(find /etc/postgresql -name "postgresql.conf" -printf "%h\n" 2>/dev/null | head -1)
if [[ -z "$PG_CONF_DIR" ]]; then
    PG_CONF_DIR="/var/lib/postgresql/data"
fi
if [[ -f "$DBAI/config/postgresql.conf" ]] && [[ -d "$PG_CONF_DIR" ]]; then
    cp "$DBAI/config/postgresql.conf" "$PG_CONF_DIR/"
    cp "$DBAI/config/pg_hba.conf" "$PG_CONF_DIR/" 2>/dev/null || true
    systemctl restart postgresql
    sleep 2
fi

# Phase 4: Frontend
echo "[4/6] Frontend prüfen..."
if [[ ! -f "$DBAI/frontend/dist/index.html" ]]; then
    if command -v npm &>/dev/null; then
        cd "$DBAI/frontend"
        npm ci --production 2>/dev/null || npm install
        npx vite build
    fi
fi

# Phase 5: Python venv
echo "[5/6] Python-Umgebung prüfen..."
if [[ ! -d "$DBAI/.venv" ]]; then
    python3 -m venv "$DBAI/.venv"
    "$DBAI/.venv/bin/pip" install --no-cache-dir \
        fastapi uvicorn asyncpg psutil psycopg2-binary \
        pynvml aiohttp aiofiles httpx toml 2>/dev/null || true
fi

# Phase 6: Services
echo "[6/6] DBAI-Services aktivieren..."
systemctl disable ghostshell-installer.service 2>/dev/null || true
rm -f /etc/systemd/system/ghostshell-installer.service

cp "$DBAI/config/systemd/"*.service /etc/systemd/system/ 2>/dev/null || true
cp "$DBAI/config/systemd/"*.target  /etc/systemd/system/ 2>/dev/null || true
systemctl daemon-reload

for svc in postgresql dbai.target dbai-web.service dbai-ghost.service \
           dbai-hardware.service dbai-kiosk.service; do
    systemctl enable "$svc" 2>/dev/null || true
done

# GRUB Silent-Boot
if [[ -f "$DBAI/config/grub/grub-dbai" ]]; then
    cp "$DBAI/config/grub/grub-dbai" /etc/default/grub
    update-grub 2>/dev/null || grub-mkconfig -o /boot/grub/grub.cfg 2>/dev/null || true
fi

mkdir -p /var/log/dbai
touch "$MARKER"
echo "═══ GhostShell OS — First Boot abgeschlossen! ═══"
systemctl start dbai.target 2>/dev/null || true
FIRSTBOOT
    chmod +x "${rootfs}/opt/dbai/scripts/ghostshell-firstboot.sh"

    # Systemd Service
    cat > "${rootfs}/etc/systemd/system/dbai-firstboot.service" << 'FBS'
[Unit]
Description=GhostShell OS — First Boot Setup
After=postgresql.service network-online.target
Wants=network-online.target
Before=dbai-web.service
ConditionPathExists=!/opt/dbai/.first-boot-done

[Service]
Type=oneshot
ExecStart=/opt/dbai/scripts/ghostshell-firstboot.sh
RemainAfterExit=yes
TimeoutStartSec=300
StandardOutput=journal+console

[Install]
WantedBy=multi-user.target
FBS
}

# ═══════════════════════════════════════════════════════════════════
#  LIVE-BOOT VORBEREITEN
# ═══════════════════════════════════════════════════════════════════

prepare_live_boot() {
    echo "═══ Phase 5/7: Live-Boot vorbereiten ═══"
    local rootfs="${BUILD_DIR}/rootfs"
    local iso="${BUILD_DIR}/iso"

    local vmlinuz initrd
    vmlinuz=$(ls "${rootfs}/boot/vmlinuz-"* 2>/dev/null | sort -V | tail -1)
    initrd=$(ls "${rootfs}/boot/initrd.img-"* 2>/dev/null | sort -V | tail -1)

    if [[ -z "$vmlinuz" ]]; then
        echo "❌ Kein Kernel in ${rootfs}/boot/"
        ls -la "${rootfs}/boot/" || true
        exit 1
    fi

    echo "→ Kernel:  $(basename $vmlinuz)"
    echo "→ Initrd:  $(basename ${initrd:-none})"

    mkdir -p "${iso}/live" "${iso}/boot/grub" "${iso}/EFI/BOOT" "${iso}/isolinux"
    cp "$vmlinuz" "${iso}/live/vmlinuz"
    [[ -n "$initrd" ]] && cp "$initrd" "${iso}/live/initrd"
}

# ═══════════════════════════════════════════════════════════════════
#  SQUASHFS + ISO ERSTELLEN
# ═══════════════════════════════════════════════════════════════════

build_squashfs_and_iso() {
    echo "═══ Phase 6/7: SquashFS + ISO erstellen ═══"
    local rootfs="${BUILD_DIR}/rootfs"
    local iso="${BUILD_DIR}/iso"

    # Chroot-Mounts entfernen
    for mp in proc sys dev/pts dev run; do
        umount -lf "${rootfs}/${mp}" 2>/dev/null || true
    done

    echo "→ SquashFS komprimieren (dauert einige Minuten)..."
    mksquashfs "$rootfs" "${iso}/live/filesystem.squashfs" \
        -comp zstd -Xcompression-level 15 -b 1M \
        -e boot/vmlinuz* -e boot/initrd* \
        -e tmp/* -e var/cache/apt/* \
        -no-progress 2>/dev/null || \
    mksquashfs "$rootfs" "${iso}/live/filesystem.squashfs" \
        -comp xz -b 1M \
        -e boot/vmlinuz* -e boot/initrd* \
        -e tmp/* -e var/cache/apt/*

    echo "→ SquashFS: $(du -h ${iso}/live/filesystem.squashfs | cut -f1)"

    # GRUB für ISO
    cat > "${iso}/boot/grub/grub.cfg" << 'GRUBCFG'
set timeout=5
set default=0

insmod all_video
insmod gfxterm
set gfxmode=auto
terminal_output gfxterm

menuentry "🧠 GhostShell OS — Installieren" --class ghostshell {
    linux /live/vmlinuz boot=live toram quiet splash loglevel=3
    initrd /live/initrd
}

menuentry "🧠 GhostShell OS — Safe Mode" --class ghostshell {
    linux /live/vmlinuz boot=live nomodeset loglevel=5
    initrd /live/initrd
}

menuentry "🧠 GhostShell OS — Live (ohne Installation)" --class ghostshell {
    linux /live/vmlinuz boot=live toram quiet splash ghostshell.live=1
    initrd /live/initrd
}

menuentry "Neustart" --class restart {
    reboot
}

menuentry "Herunterfahren" --class shutdown {
    halt
}
GRUBCFG

    # ISOLINUX (BIOS)
    if [[ -f /usr/lib/ISOLINUX/isolinux.bin ]]; then
        cp /usr/lib/ISOLINUX/isolinux.bin "${iso}/isolinux/"
        cp /usr/lib/syslinux/modules/bios/{ldlinux,menu,libutil}.c32 \
           "${iso}/isolinux/" 2>/dev/null || true

        cat > "${iso}/isolinux/isolinux.cfg" << 'ISOCFG'
DEFAULT ghostshell
TIMEOUT 50
PROMPT 0

LABEL ghostshell
    MENU LABEL GhostShell OS - Installieren
    KERNEL /live/vmlinuz
    APPEND initrd=/live/initrd boot=live toram quiet splash

LABEL safe
    MENU LABEL GhostShell OS - Safe Mode
    KERNEL /live/vmlinuz
    APPEND initrd=/live/initrd boot=live nomodeset

LABEL live
    MENU LABEL GhostShell OS - Live
    KERNEL /live/vmlinuz
    APPEND initrd=/live/initrd boot=live toram ghostshell.live=1
ISOCFG
    fi

    # ISO generieren
    echo "→ ISO generieren..."
    mkdir -p "$OUTPUT_DIR"
    local iso_path="${OUTPUT_DIR}/${ISO_NAME}"

    if command -v grub-mkrescue &>/dev/null; then
        grub-mkrescue -o "$iso_path" "${iso}" \
            -volid "GHOSTSHELL" 2>/dev/null && return 0
    fi

    if command -v xorriso &>/dev/null; then
        xorriso -as mkisofs \
            -iso-level 3 -full-iso9660-filenames \
            -volid "GHOSTSHELL" -J -joliet-long \
            -output "$iso_path" "${iso}"
    fi
}

# ═══════════════════════════════════════════════════════════════════
#  FINALISIERUNG
# ═══════════════════════════════════════════════════════════════════

finalize() {
    echo "═══ Phase 7/7: Finalisierung ═══"
    local iso_path="${OUTPUT_DIR}/${ISO_NAME}"

    if [[ ! -f "$iso_path" ]]; then
        echo "❌ ISO-Erstellung fehlgeschlagen!"
        exit 1
    fi

    local size
    size=$(du -h "$iso_path" | cut -f1)
    sha256sum "$iso_path" > "${iso_path}.sha256"

    echo ""
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║  ✅ GhostShell OS — ISO erfolgreich erstellt!            ║"
    echo "╠══════════════════════════════════════════════════════════╣"
    echo "║  Datei:    ${iso_path}"
    echo "║  Größe:    ${size}"
    echo "║  SHA256:   $(head -c 16 < <(cut -d' ' -f1 ${iso_path}.sha256))..."
    echo "║  Base:     ${BASE}"
    echo "╠══════════════════════════════════════════════════════════╣"
    echo "║  USB-Stick:  sudo dd if=${iso_path} of=/dev/sdX bs=4M   "
    echo "║  QEMU-Test:  bash scripts/test-iso-qemu.sh              "
    echo "╚══════════════════════════════════════════════════════════╝"

    if $AUTO_TEST && [[ -f "${DBAI_ROOT}/scripts/test-iso-qemu.sh" ]]; then
        echo "→ Starte QEMU-Test..."
        bash "${DBAI_ROOT}/scripts/test-iso-qemu.sh" "$iso_path"
    fi
}

# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════

main() {
    local start_time
    start_time=$(date +%s)

    echo "→ Build gestartet: $(date)"
    rm -rf "$BUILD_DIR"
    mkdir -p "$BUILD_DIR" "$OUTPUT_DIR"

    case "$BASE" in
        arch)
            check_deps_arch
            build_frontend
            build_arch_iso
            ;;
        debian)
            check_deps_debian
            build_frontend
            build_debian_rootfs
            install_dbai_into_rootfs
            install_services
            install_firstboot
            prepare_live_boot
            build_squashfs_and_iso
            ;;
    esac

    finalize

    local duration=$(( $(date +%s) - start_time ))
    echo "⏱  Build-Dauer: $((duration / 60))m $((duration % 60))s"
}

main
