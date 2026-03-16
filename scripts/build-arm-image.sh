#!/bin/bash
# =============================================================================
# DBAI GhostShell OS — Raspberry Pi 3 ARM64 SD-Card Image Builder
# =============================================================================
# Erstellt ein bootfähiges 32GB SD-Card-Image für Raspberry Pi 3 (aarch64).
#
# Voraussetzungen (Host):
#   sudo apt install debootstrap qemu-user-static binfmt-support \
#                    kpartx dosfstools parted e2fsprogs rsync
#
# Nutzung:
#   sudo bash scripts/build-arm-image.sh
#   sudo bash scripts/build-arm-image.sh --size 16G     # Andere Größe
#   sudo bash scripts/build-arm-image.sh --write /dev/sdX  # Direkt auf SD
#
# Ergebnis:
#   dist/ghostshell-rpi3-arm64-YYYYMMDD.img  (32GB Image)
#   dist/ghostshell-rpi3-arm64-YYYYMMDD.img.sha256
# =============================================================================

set -euo pipefail

# ─── Konfiguration ────────────────────────────────────────────────
DBAI_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="/tmp/dbai-arm-build"
OUTPUT_DIR="${DBAI_ROOT}/dist"
IMAGE_SIZE="32G"
IMAGE_NAME="ghostshell-rpi3-arm64-$(date +%Y%m%d).img"
WRITE_DEV=""
BOOT_SIZE="512M"
DEBIAN_RELEASE="bookworm"

# RPi3 Firmware
RPI_FIRMWARE_URL="https://github.com/raspberrypi/firmware/archive/refs/heads/stable.tar.gz"
RPI_KERNEL_BRANCH="stable"

# ─── Argumente ────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case $1 in
        --size)   IMAGE_SIZE="$2"; shift 2 ;;
        --write)  WRITE_DEV="$2";  shift 2 ;;
        --output) OUTPUT_DIR="$2"; shift 2 ;;
        --name)   IMAGE_NAME="$2"; shift 2 ;;
        *)        echo "Unbekannt: $1"; exit 1 ;;
    esac
done

# ─── Root Check ───────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    echo "❌ Root-Rechte erforderlich: sudo bash $0"
    exit 1
fi

echo "╔══════════════════════════════════════════════════════════╗"
echo "║    🧠 GhostShell OS — Raspberry Pi 3 Image Builder      ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  Architektur:  arm64 (aarch64)                          ║"
echo "║  Ziel:         Raspberry Pi 3 Model B/B+                ║"
echo "║  Image-Größe:  ${IMAGE_SIZE}                                    ║"
echo "║  Debian:       ${DEBIAN_RELEASE}                              ║"
echo "║  Output:       ${OUTPUT_DIR}/${IMAGE_NAME}              ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ─── Abhängigkeiten ───────────────────────────────────────────────
check_deps() {
    local missing=()
    for cmd in debootstrap qemu-aarch64-static kpartx parted mkfs.vfat mkfs.ext4 rsync; do
        command -v "$cmd" &>/dev/null || missing+=("$cmd")
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "❌ Fehlende Tools: ${missing[*]}"
        echo "→ sudo apt install debootstrap qemu-user-static binfmt-support kpartx dosfstools parted e2fsprogs rsync"
        exit 1
    fi

    # binfmt für aarch64 prüfen
    if [[ ! -f /proc/sys/fs/binfmt_misc/qemu-aarch64 ]]; then
        echo "⚠ binfmt für aarch64 nicht registriert, versuche Aktivierung..."
        update-binfmts --enable qemu-aarch64 2>/dev/null || \
        echo ':qemu-aarch64:M::\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\xb7\x00:\xff\xff\xff\xff\xff\xff\xff\x00\xff\xff\xff\xff\xff\xff\xff\xff\xfe\xff\xff\xff:/usr/bin/qemu-aarch64-static:CF' \
            > /proc/sys/fs/binfmt_misc/register
    fi
    echo "✅ Alle Build-Abhängigkeiten vorhanden"
}

# ─── Cleanup ──────────────────────────────────────────────────────
LOOP_DEV=""
cleanup() {
    echo ""
    echo "→ Räume auf..."
    set +e

    # WICHTIG: sync vor umount
    sync

    # Chroot-Mounts
    umount -lf "${BUILD_DIR}/rootfs/boot/firmware" 2>/dev/null
    umount -lf "${BUILD_DIR}/rootfs/proc" 2>/dev/null
    umount -lf "${BUILD_DIR}/rootfs/sys" 2>/dev/null
    umount -lf "${BUILD_DIR}/rootfs/dev/pts" 2>/dev/null
    umount -lf "${BUILD_DIR}/rootfs/dev" 2>/dev/null
    umount -lf "${BUILD_DIR}/rootfs" 2>/dev/null
    umount -lf "${BUILD_DIR}/boot" 2>/dev/null

    # Loop-Device
    if [[ -n "$LOOP_DEV" ]]; then
        kpartx -d "$LOOP_DEV" 2>/dev/null
        losetup -d "$LOOP_DEV" 2>/dev/null
    fi

    # Build-Dir NICHT automatisch löschen (zu groß, manuell: rm -rf /tmp/dbai-arm-build)
    set -e
}
trap cleanup EXIT

# ═══════════════════════════════════════════════════════════════════
# Phase 1: Image-Datei & Partitionen erstellen
# ═══════════════════════════════════════════════════════════════════
create_image() {
    echo "═══ Phase 1/8: Image erstellen (${IMAGE_SIZE}) ═══"
    mkdir -p "$OUTPUT_DIR" "$BUILD_DIR"

    local img="${OUTPUT_DIR}/${IMAGE_NAME}"

    # Sparse-Image erstellen (schnell, belegt erst bei Beschreibung Platz)
    echo "→ Erstelle Sparse-Image (${IMAGE_SIZE})..."
    truncate -s "$IMAGE_SIZE" "$img"

    # Partitionstabelle
    echo "→ Partitionstabelle (MBR)..."
    parted -s "$img" mklabel msdos
    parted -s "$img" mkpart primary fat32 4MiB ${BOOT_SIZE}
    parted -s "$img" set 1 boot on
    parted -s "$img" set 1 lba on
    parted -s "$img" mkpart primary ext4 ${BOOT_SIZE} 100%

    # Loop-Device
    LOOP_DEV=$(losetup --find --show --partscan "$img")
    echo "→ Loop-Device: ${LOOP_DEV}"

    # Warten auf Partition-Devices
    sleep 2
    partprobe "$LOOP_DEV" 2>/dev/null || true
    sleep 1

    local boot_part="${LOOP_DEV}p1"
    local root_part="${LOOP_DEV}p2"

    # Falls kein p1/p2, kpartx verwenden
    if [[ ! -b "$boot_part" ]]; then
        echo "→ Verwende kpartx..."
        kpartx -as "$LOOP_DEV"
        local loop_name=$(basename "$LOOP_DEV")
        boot_part="/dev/mapper/${loop_name}p1"
        root_part="/dev/mapper/${loop_name}p2"
        sleep 1
    fi

    # Formatieren
    echo "→ Boot-Partition (FAT32, ${BOOT_SIZE})..."
    mkfs.vfat -F 32 -n GHOSTBOOT "$boot_part"

    echo "→ Root-Partition (ext4, Rest)..."
    mkfs.ext4 -L ghostshell-root -O ^metadata_csum "$root_part"

    # Mounten
    mkdir -p "${BUILD_DIR}/rootfs" "${BUILD_DIR}/boot"
    mount "$root_part" "${BUILD_DIR}/rootfs"
    mkdir -p "${BUILD_DIR}/rootfs/boot/firmware"
    mount "$boot_part" "${BUILD_DIR}/rootfs/boot/firmware"

    echo "✅ Image partitioniert und gemountet"
}

# ═══════════════════════════════════════════════════════════════════
# Phase 2: Debian ARM64 Root-FS via debootstrap
# ═══════════════════════════════════════════════════════════════════
create_rootfs() {
    echo "═══ Phase 2/8: Debian ARM64 Rootfs (debootstrap) ═══"
    local rootfs="${BUILD_DIR}/rootfs"

    debootstrap --arch=arm64 \
        --foreign \
        --variant=minbase \
        --include=systemd,systemd-sysv,dbus,locales,sudo,curl,wget,ca-certificates,gnupg \
        "$DEBIAN_RELEASE" "$rootfs" http://deb.debian.org/debian

    # QEMU-Static für Chroot kopieren
    cp /usr/bin/qemu-aarch64-static "${rootfs}/usr/bin/"

    # Second stage
    echo "→ Debootstrap second stage (QEMU-emuliert)..."
    chroot "$rootfs" /debootstrap/debootstrap --second-stage

    echo "✅ ARM64 Base-System installiert"
}

# ═══════════════════════════════════════════════════════════════════
# Phase 3: System konfigurieren
# ═══════════════════════════════════════════════════════════════════
configure_system() {
    echo "═══ Phase 3/8: System konfigurieren ═══"
    local rootfs="${BUILD_DIR}/rootfs"

    # Chroot-Mounts
    mount --bind /dev     "${rootfs}/dev"
    mount --bind /dev/pts "${rootfs}/dev/pts"
    mount -t proc proc    "${rootfs}/proc"
    mount -t sysfs sys    "${rootfs}/sys"

    # APT Sources
    cat > "${rootfs}/etc/apt/sources.list" << EOF
deb http://deb.debian.org/debian ${DEBIAN_RELEASE} main contrib non-free non-free-firmware
deb http://deb.debian.org/debian ${DEBIAN_RELEASE}-updates main contrib non-free non-free-firmware
deb http://security.debian.org/debian-security ${DEBIAN_RELEASE}-security main contrib non-free non-free-firmware
EOF

    # Hostname & Hosts
    echo "ghostshell" > "${rootfs}/etc/hostname"
    cat > "${rootfs}/etc/hosts" << EOF
127.0.0.1   localhost ghostshell
::1         localhost ghostshell
EOF

    # Locale
    chroot "$rootfs" bash -c "
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -qq

        # Basis-System
        apt-get install -y -qq --no-install-recommends \
            linux-image-arm64 \
            firmware-brcm80211 firmware-misc-nonfree \
            systemd-timesyncd \
            locales console-setup keyboard-configuration \
            net-tools iproute2 wireless-tools wpasupplicant \
            iputils-ping dnsutils openssh-server \
            lm-sensors i2c-tools \
            git pciutils usbutils htop nano less \
            parted fdisk gdisk

        # PostgreSQL 16
        apt-get install -y -qq --no-install-recommends \
            postgresql-16 postgresql-16-pgvector \
            postgresql-contrib-16

        # Python 3
        apt-get install -y -qq --no-install-recommends \
            python3 python3-pip python3-venv python3-dev \
            python3-psycopg2 python3-psutil

        # Node.js 20 (für Frontend-Build)
        curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
        apt-get install -y -qq nodejs

        # Display (Kiosk-Mode)
        apt-get install -y -qq --no-install-recommends \
            chromium xserver-xorg xinit x11-xserver-utils \
            openbox unclutter xfonts-base

        # Netzwerk
        apt-get install -y -qq --no-install-recommends \
            network-manager hostapd dnsmasq iptables

        # Cleanup
        apt-get clean
        rm -rf /var/lib/apt/lists/*
    "

    # Locale setzen
    chroot "$rootfs" bash -c "
        sed -i 's/# en_US.UTF-8/en_US.UTF-8/' /etc/locale.gen
        sed -i 's/# de_DE.UTF-8/de_DE.UTF-8/' /etc/locale.gen
        locale-gen
        update-locale LANG=en_US.UTF-8
    "

    # Timezone
    chroot "$rootfs" ln -sf /usr/share/zoneinfo/Europe/Berlin /etc/localtime

    echo "✅ System konfiguriert"
}

# ═══════════════════════════════════════════════════════════════════
# Phase 4: Raspberry Pi 3 Boot-Firmware
# ═══════════════════════════════════════════════════════════════════
install_rpi_firmware() {
    echo "═══ Phase 4/8: Raspberry Pi 3 Firmware ═══"
    local rootfs="${BUILD_DIR}/rootfs"
    local bootdir="${rootfs}/boot/firmware"
    local fw_dir="${BUILD_DIR}/rpi-firmware"

    # RPi Firmware herunterladen
    echo "→ Lade Raspberry Pi Firmware herunter..."
    mkdir -p "$fw_dir"
    if [[ ! -d "${fw_dir}/firmware-stable" ]]; then
        curl -sL "$RPI_FIRMWARE_URL" | tar xz -C "$fw_dir"
    fi

    local fw_src="${fw_dir}/firmware-stable/boot"

    # Boot-Dateien kopieren
    echo "→ Kopiere Boot-Firmware..."
    cp "${fw_src}/bootcode.bin"  "$bootdir/"
    cp "${fw_src}/start.elf"     "$bootdir/"
    cp "${fw_src}/start_x.elf"   "$bootdir/"
    cp "${fw_src}/fixup.dat"     "$bootdir/"
    cp "${fw_src}/fixup_x.dat"   "$bootdir/"

    # Device Tree für RPi3
    cp "${fw_src}/bcm2710-rpi-3-b.dtb"     "$bootdir/" 2>/dev/null || true
    cp "${fw_src}/bcm2710-rpi-3-b-plus.dtb" "$bootdir/" 2>/dev/null || true
    mkdir -p "${bootdir}/overlays"
    cp "${fw_src}/overlays/"* "${bootdir}/overlays/" 2>/dev/null || true

    # Kernel kopieren (aus debootstrap installiertem linux-image-arm64)
    local kernel=$(ls ${rootfs}/boot/vmlinuz-* 2>/dev/null | head -1)
    local initrd=$(ls ${rootfs}/boot/initrd.img-* 2>/dev/null | head -1)

    if [[ -n "$kernel" ]]; then
        cp "$kernel" "${bootdir}/kernel8.img"
        echo "→ Kernel: $(basename $kernel) → kernel8.img"
    fi
    if [[ -n "$initrd" ]]; then
        cp "$initrd" "${bootdir}/initramfs8"
        echo "→ Initrd: $(basename $initrd) → initramfs8"
    fi

    # config.txt — RPi3 ARM64 Boot-Konfiguration
    cat > "${bootdir}/config.txt" << 'RPICFG'
# ═══════════════════════════════════════════════════════════
# GhostShell OS — Raspberry Pi 3 Boot Configuration
# ═══════════════════════════════════════════════════════════

# ARM64 Mode (64-bit)
arm_64bit=1

# Kernel
kernel=kernel8.img
initramfs initramfs8 followkernel

# GPU Memory (minimal für Server, mehr für Kiosk)
gpu_mem=128

# HDMI (immer aktiv, auch ohne Monitor)
hdmi_force_hotplug=1
hdmi_drive=2
hdmi_group=2
hdmi_mode=82

# Übertaktung (moderat für Stabilität)
arm_freq=1300
over_voltage=2
core_freq=400
sdram_freq=450

# USB-Strom (für externe Geräte)
max_usb_current=1

# I2C, SPI aktivieren (für Hardware-Sensoren)
dtparam=i2c_arm=on
dtparam=spi=on
dtparam=audio=on

# UART (für Serial-Debug)
enable_uart=1
dtoverlay=miniuart-bt

# Disable splash
disable_splash=1

# Device Tree
dtoverlay=vc4-fkms-v3d
RPICFG

    # cmdline.txt — Kernel-Parameter
    cat > "${bootdir}/cmdline.txt" << 'CMDLINE'
console=serial0,115200 console=tty1 root=LABEL=ghostshell-root rootfstype=ext4 rootwait fsck.repair=yes quiet loglevel=3 logo.nologo plymouth.ignore-serial-consoles systemd.show_status=auto
CMDLINE

    # fstab
    cat > "${rootfs}/etc/fstab" << 'FSTAB'
# GhostShell OS — /etc/fstab
LABEL=ghostshell-root  /               ext4  defaults,noatime,commit=600  0  1
LABEL=GHOSTBOOT        /boot/firmware  vfat  defaults                     0  2
tmpfs                  /tmp            tmpfs defaults,nosuid,size=256m    0  0
tmpfs                  /var/log        tmpfs defaults,nosuid,size=128m    0  0
FSTAB

    echo "✅ Raspberry Pi 3 Firmware installiert"
}

# ═══════════════════════════════════════════════════════════════════
# Phase 5: GhostShell OS installieren
# ═══════════════════════════════════════════════════════════════════
install_ghostshell() {
    echo "═══ Phase 5/8: GhostShell OS installieren ═══"
    local rootfs="${BUILD_DIR}/rootfs"
    local target="${rootfs}/opt/dbai"

    mkdir -p "$target"

    # Projektdateien kopieren
    echo "→ Kopiere GhostShell-Dateien..."
    rsync -a --exclude='node_modules' \
             --exclude='__pycache__' \
             --exclude='.git' \
             --exclude='dist' \
             --exclude='*.pyc' \
             --exclude='.venv' \
             --exclude='pics' \
             "${DBAI_ROOT}/" "$target/"

    # Python venv erstellen
    echo "→ Python Virtual Environment..."
    chroot "$rootfs" bash -c "
        python3 -m venv /opt/dbai/.venv
        /opt/dbai/.venv/bin/pip install --no-cache-dir \
            psycopg2-binary psutil toml \
            fastapi uvicorn websockets \
            PyJWT bcrypt aiofiles httpx 2>/dev/null || {
            # Fallback: System-Pakete nutzen
            echo '⚠ venv-pip fehlgeschlagen, System-Pakete werden genutzt'
            pip3 install --break-system-packages \
                psycopg2-binary psutil toml \
                fastapi uvicorn websockets \
                PyJWT bcrypt aiofiles httpx 2>/dev/null || true
        }
    "

    # Frontend Build — NATIV auf x86 (nicht im ARM-Chroot, ~100x schneller)
    echo "→ Frontend Build (nativ auf Host)..."
    local fe_tmp="/tmp/dbai-fe-build"
    rm -rf "$fe_tmp"
    cp -r "${DBAI_ROOT}/frontend" "$fe_tmp"
    cd "$fe_tmp"
    npm install 2>/dev/null || npm install --legacy-peer-deps
    npx --yes vite build
    cd "$DBAI_ROOT"

    # dist-Ordner ins ARM-rootfs kopieren
    mkdir -p "${target}/frontend/dist"
    cp -r "$fe_tmp/dist/"* "${target}/frontend/dist/"
    rm -rf "$fe_tmp"
    echo "→ Frontend dist nach ARM-rootfs kopiert"

    echo "✅ GhostShell OS installiert"
}

# ═══════════════════════════════════════════════════════════════════
# Phase 6: Systemd Services & Auto-Boot
# ═══════════════════════════════════════════════════════════════════
install_services() {
    echo "═══ Phase 6/8: Services konfigurieren ═══"
    local rootfs="${BUILD_DIR}/rootfs"

    # ─── User erstellen ───
    chroot "$rootfs" bash -c "
        useradd -m -s /bin/bash -G audio,video,input,i2c,spi,gpio,dialout dbai 2>/dev/null || true
        echo 'dbai:dbai2026' | chpasswd
        echo 'dbai ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/dbai
        chmod 440 /etc/sudoers.d/dbai

        # Root-Passwort
        echo 'root:ghostshell2026' | chpasswd
    "

    # ─── PostgreSQL für ARM konfigurieren ───
    cat > "${rootfs}/opt/dbai/config/postgresql-arm.conf" << 'PGCONF'
# GhostShell OS — PostgreSQL ARM64 Config (Raspberry Pi 3, 1GB RAM)
# Optimiert für begrenzte Ressourcen

listen_addresses = 'localhost'
port = 5432
max_connections = 30

# Memory (konservativ für 1GB RAM)
shared_buffers = 128MB
effective_cache_size = 256MB
work_mem = 4MB
maintenance_work_mem = 32MB

# WAL
wal_buffers = 4MB
checkpoint_completion_target = 0.9
max_wal_size = 256MB
min_wal_size = 64MB

# Planner
random_page_cost = 1.1
effective_io_concurrency = 1
default_statistics_target = 100

# Logging
log_timezone = 'Europe/Berlin'
log_destination = 'stderr'
logging_collector = on
log_directory = '/var/log/postgresql'
log_filename = 'ghostshell-%Y-%m-%d.log'
log_min_duration_statement = 1000

# Locale
datestyle = 'iso, dmy'
timezone = 'Europe/Berlin'
lc_messages = 'en_US.UTF-8'
lc_monetary = 'en_US.UTF-8'
lc_numeric = 'en_US.UTF-8'
lc_time = 'de_DE.UTF-8'
PGCONF

    # ─── DBAI Systemd Services (ARM-angepasst) ───

    # DB Service
    cat > "${rootfs}/etc/systemd/system/dbai-db.service" << 'EOF'
[Unit]
Description=GhostShell — PostgreSQL Kernel
After=network.target
Before=dbai-web.service

[Service]
Type=oneshot
RemainAfterExit=yes
User=root
ExecStart=/bin/bash -c "systemctl start postgresql && sleep 2"
ExecStop=/bin/bash -c "systemctl stop postgresql"

[Install]
WantedBy=dbai.target
EOF

    # Web Service (ARM-angepasst, kein GPU)
    cat > "${rootfs}/etc/systemd/system/dbai-web.service" << 'EOF'
[Unit]
Description=GhostShell — Neural Bridge (FastAPI)
After=dbai-db.service postgresql.service
Requires=dbai-db.service

[Service]
Type=simple
User=dbai
Group=dbai
WorkingDirectory=/opt/dbai
Environment=PYTHONUNBUFFERED=1
Environment=DBAI_ENV=production
Environment=DBAI_ARCH=arm64
Environment=DBAI_DB_USER=dbai_system
Environment=DBAI_DB_PASSWORD=dbai2026
Environment=DBAI_DB_HOST=127.0.0.1
Environment=DBAI_DB_NAME=dbai
Environment=DBAI_DB_RUNTIME_USER=dbai_runtime
Environment=DBAI_DB_RUNTIME_PASSWORD=dbai_runtime_2026
ExecStart=/opt/dbai/.venv/bin/python3 -m uvicorn web.server:app --host 0.0.0.0 --port 3000 --workers 2
Restart=always
RestartSec=5
MemoryMax=256M

[Install]
WantedBy=dbai.target
EOF

    # Hardware Monitor (ARM-angepasst, kein GPU/NVIDIA)
    cat > "${rootfs}/etc/systemd/system/dbai-hardware.service" << 'EOF'
[Unit]
Description=GhostShell — Hardware Monitor (ARM)
After=dbai-db.service
Requires=dbai-db.service

[Service]
Type=simple
User=dbai
Group=dbai
WorkingDirectory=/opt/dbai
SupplementaryGroups=i2c spi gpio
Environment=PYTHONUNBUFFERED=1
Environment=DBAI_ARCH=arm64
ExecStart=/opt/dbai/.venv/bin/python3 -c "from bridge.hardware_monitor import HardwareMonitor; import asyncio; m = HardwareMonitor(); asyncio.get_event_loop().run_until_complete(m.run())"
Restart=always
RestartSec=10

[Install]
WantedBy=dbai.target
EOF

    # Kiosk Service (Chromium im Fullscreen)
    cat > "${rootfs}/etc/systemd/system/dbai-kiosk.service" << 'EOF'
[Unit]
Description=GhostShell — Cyber-Deck Kiosk (Chromium)
After=dbai-web.service
Requires=dbai-web.service

[Service]
Type=simple
User=dbai
Group=dbai
Environment=DISPLAY=:0
ExecStartPre=/bin/sleep 5
ExecStart=/bin/bash -c "startx /usr/bin/chromium --no-sandbox --kiosk --disable-gpu --noerrdialogs --disable-infobars --no-first-run --disable-translate --disable-features=TranslateUI http://localhost:3000"
Restart=on-failure
RestartSec=10

[Install]
WantedBy=dbai.target
EOF

    # Target
    cat > "${rootfs}/etc/systemd/system/dbai.target" << 'EOF'
[Unit]
Description=GhostShell OS — Full System Target
After=multi-user.target
AllowIsolate=yes

[Install]
WantedBy=multi-user.target
EOF

    # First-Boot Service (DB initialisieren)
    cat > "${rootfs}/opt/dbai/scripts/first-boot-arm.sh" << 'FIRSTBOOT'
#!/bin/bash
# ═══════════════════════════════════════════════════════════
# GhostShell OS — First Boot (ARM64)
# ═══════════════════════════════════════════════════════════
set -e

if [ -f /opt/dbai/.first-boot-done ]; then
    exit 0
fi

echo "══════════════════════════════════════════════"
echo "  🧠 GhostShell OS — Erste Initialisierung   "
echo "══════════════════════════════════════════════"

# Warten auf PostgreSQL
for i in $(seq 1 30); do
    pg_isready -q && break
    sleep 1
done

# PostgreSQL-Config für ARM kopieren
PG_CONF_DIR=$(find /etc/postgresql -name "postgresql.conf" -exec dirname {} \; | head -1)
if [[ -n "$PG_CONF_DIR" ]]; then
    cp /opt/dbai/config/postgresql-arm.conf "${PG_CONF_DIR}/conf.d/ghostshell.conf" 2>/dev/null || \
    cp /opt/dbai/config/postgresql-arm.conf "${PG_CONF_DIR}/postgresql.conf"
    systemctl restart postgresql
    sleep 3
fi

# Rollen & DB erstellen
sudo -u postgres psql -c "CREATE ROLE dbai_system WITH LOGIN SUPERUSER PASSWORD 'dbai2026';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE ROLE dbai_runtime WITH LOGIN PASSWORD 'dbai_runtime_2026';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE ROLE dbai_ghost WITH LOGIN PASSWORD 'dbai_ghost_2026';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE dbai OWNER dbai_system;" 2>/dev/null || true

# Erweiterungen
sudo -u postgres psql -d dbai -c "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";" 2>/dev/null || true
sudo -u postgres psql -d dbai -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;" 2>/dev/null || true
sudo -u postgres psql -d dbai -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null || true

# Schemas laden
echo "→ Lade SQL-Schemas..."
SCHEMA_COUNT=0
for sql in /opt/dbai/schema/*.sql; do
    echo "  → $(basename $sql)"
    sudo -u postgres psql -d dbai -f "$sql" 2>/dev/null || true
    SCHEMA_COUNT=$((SCHEMA_COUNT + 1))
done
echo "→ ${SCHEMA_COUNT} Schemas geladen"

# pg_hba.conf anpassen
if [[ -n "$PG_CONF_DIR" ]]; then
    cat >> "${PG_CONF_DIR}/pg_hba.conf" << 'PGHBA'
# GhostShell OS
local   dbai    dbai_system                 md5
local   dbai    dbai_runtime                md5
local   dbai    dbai_ghost                  md5
host    dbai    dbai_runtime    127.0.0.1/32    md5
host    dbai    dbai_system     127.0.0.1/32    md5
PGHBA
    systemctl restart postgresql
fi

# Rechte
chown -R dbai:dbai /opt/dbai
chmod 750 /opt/dbai

# SD-Karte expandieren (gesamten Platz nutzen)
if command -v raspi-config &>/dev/null; then
    raspi-config --expand-rootfs 2>/dev/null || true
else
    # Manuell Root-Partition expandieren
    ROOT_PART=$(findmnt / -o SOURCE -n)
    ROOT_DISK=$(echo "$ROOT_PART" | sed 's/[0-9]*$//')
    PART_NUM=$(echo "$ROOT_PART" | grep -o '[0-9]*$')
    if [[ -n "$ROOT_DISK" && -n "$PART_NUM" ]]; then
        echo "→ Expandiere Root-Partition..."
        growpart "$ROOT_DISK" "$PART_NUM" 2>/dev/null || true
        resize2fs "$ROOT_PART" 2>/dev/null || true
    fi
fi

touch /opt/dbai/.first-boot-done
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  ✅ GhostShell OS initialisiert!             ║"
echo "║  → http://localhost:3000                     ║"
echo "║  → Login: root / dbai2026                    ║"
echo "╚══════════════════════════════════════════════╝"
FIRSTBOOT
    chmod +x "${rootfs}/opt/dbai/scripts/first-boot-arm.sh"

    cat > "${rootfs}/etc/systemd/system/dbai-firstboot.service" << 'EOF'
[Unit]
Description=GhostShell OS — First Boot Setup
After=postgresql.service network-online.target
Before=dbai-web.service
ConditionPathExists=!/opt/dbai/.first-boot-done

[Service]
Type=oneshot
ExecStart=/opt/dbai/scripts/first-boot-arm.sh
RemainAfterExit=yes
StandardOutput=journal+console
TimeoutStartSec=300

[Install]
WantedBy=dbai.target
EOF

    # Services aktivieren
    chroot "$rootfs" bash -c "
        systemctl enable postgresql
        systemctl enable ssh
        systemctl enable NetworkManager 2>/dev/null || true
        systemctl enable dbai.target
        systemctl enable dbai-firstboot.service
        systemctl enable dbai-db.service
        systemctl enable dbai-web.service
        systemctl enable dbai-hardware.service
        systemctl enable dbai-kiosk.service 2>/dev/null || true
        # Default target
        systemctl set-default dbai.target
    "

    # Auto-Login auf TTY1
    mkdir -p "${rootfs}/etc/systemd/system/getty@tty1.service.d"
    cat > "${rootfs}/etc/systemd/system/getty@tty1.service.d/autologin.conf" << 'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin dbai --noclear %I $TERM
EOF

    # MOTD
    cat > "${rootfs}/etc/motd" << 'MOTD'

  ╔══════════════════════════════════════════════════════════╗
  ║                                                          ║
  ║   🧠  G h o s t S h e l l   O S   (ARM64)               ║
  ║                                                          ║
  ║   "The Ghost is the Logic. The Database is the Shell."   ║
  ║                                                          ║
  ║   Dashboard:  http://localhost:3000                       ║
  ║   Login:      root / dbai2026                             ║
  ║   SSH:        ssh dbai@<ip>                               ║
  ║                                                          ║
  ║   Status:     systemctl status dbai.target                ║
  ║   Logs:       journalctl -u dbai-web -f                   ║
  ║                                                          ║
  ╚══════════════════════════════════════════════════════════╝

MOTD

    echo "✅ Services konfiguriert & aktiviert"
}

# ═══════════════════════════════════════════════════════════════════
# Phase 7: Netzwerk & SSH
# ═══════════════════════════════════════════════════════════════════
configure_network() {
    echo "═══ Phase 7/8: Netzwerk konfigurieren ═══"
    local rootfs="${BUILD_DIR}/rootfs"

    # SSH erlauben
    chroot "$rootfs" bash -c "
        mkdir -p /etc/ssh/sshd_config.d
        echo 'PermitRootLogin yes' > /etc/ssh/sshd_config.d/ghostshell.conf
        echo 'PasswordAuthentication yes' >> /etc/ssh/sshd_config.d/ghostshell.conf
    "

    # WiFi-Konfiguration vorbereiten
    mkdir -p "${rootfs}/etc/NetworkManager/system-connections"

    # DNS
    cat > "${rootfs}/etc/resolv.conf" << 'EOF'
nameserver 1.1.1.1
nameserver 8.8.8.8
EOF

    # Ethernet DHCP (NetworkManager)
    cat > "${rootfs}/etc/NetworkManager/system-connections/Wired.nmconnection" << 'EOF'
[connection]
id=Wired
type=ethernet
autoconnect=true

[ipv4]
method=auto

[ipv6]
method=auto
EOF
    chmod 600 "${rootfs}/etc/NetworkManager/system-connections/Wired.nmconnection"

    echo "✅ Netzwerk konfiguriert (DHCP + SSH)"
}

# ═══════════════════════════════════════════════════════════════════
# Phase 8: Image finalisieren
# ═══════════════════════════════════════════════════════════════════
finalize_image() {
    echo "═══ Phase 8/8: Image finalisieren ═══"
    local rootfs="${BUILD_DIR}/rootfs"
    local img="${OUTPUT_DIR}/${IMAGE_NAME}"

    # QEMU-Static entfernen
    rm -f "${rootfs}/usr/bin/qemu-aarch64-static"

    # Temporäre Dateien aufräumen
    chroot "$rootfs" bash -c "
        apt-get clean 2>/dev/null || true
        rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
        rm -rf /var/cache/apt/archives/*.deb
    " 2>/dev/null || true

    # Disk-Usage anzeigen
    echo ""
    echo "→ Belegung im Image:"
    du -sh "${rootfs}" 2>/dev/null || true
    df -h "${rootfs}" 2>/dev/null || true

    # Unmount
    echo "→ Unmounting..."
    sync
    umount -lf "${rootfs}/proc" 2>/dev/null || true
    umount -lf "${rootfs}/sys" 2>/dev/null || true
    umount -lf "${rootfs}/dev/pts" 2>/dev/null || true
    umount -lf "${rootfs}/dev" 2>/dev/null || true
    umount -lf "${rootfs}/boot/firmware" 2>/dev/null || true
    umount -lf "${rootfs}" 2>/dev/null || true

    # Loop-Device freigeben
    if [[ -n "$LOOP_DEV" ]]; then
        kpartx -d "$LOOP_DEV" 2>/dev/null || true
        losetup -d "$LOOP_DEV" 2>/dev/null || true
        LOOP_DEV=""
    fi

    # SHA256
    echo "→ Berechne SHA256..."
    sha256sum "$img" > "${img}.sha256"

    local size=$(du -h "$img" | cut -f1)
    local sha=$(cat "${img}.sha256" | cut -d' ' -f1 | head -c 16)

    echo ""
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║  ✅ GhostShell OS — SD-Card Image erstellt!             ║"
    echo "╠══════════════════════════════════════════════════════════╣"
    echo "║                                                          ║"
    echo "║  Datei:   ${img}"
    echo "║  Größe:   ${size}"
    echo "║  SHA256:  ${sha}..."
    echo "║                                                          ║"
    echo "║  ── Auf SD-Karte schreiben ──                            ║"
    echo "║                                                          ║"
    echo "║  Linux:                                                  ║"
    echo "║    sudo dd if=${img} of=/dev/sdX bs=4M status=progress   ║"
    echo "║                                                          ║"
    echo "║  macOS:                                                  ║"
    echo "║    sudo dd if=${img} of=/dev/rdiskN bs=4m                ║"
    echo "║                                                          ║"
    echo "║  Windows:                                                ║"
    echo "║    Raspberry Pi Imager → Custom Image                    ║"
    echo "║    oder Win32DiskImager                                  ║"
    echo "║                                                          ║"
    echo "║  ── Erster Start ──                                      ║"
    echo "║                                                          ║"
    echo "║  1. SD-Karte einlegen, LAN-Kabel anschließen            ║"
    echo "║  2. Raspberry Pi starten                                 ║"
    echo "║  3. Warten (~2-3 Min für First-Boot-Setup)               ║"
    echo "║  4. http://<raspberry-ip>:3000 aufrufen                  ║"
    echo "║  5. Login: root / dbai2026                               ║"
    echo "║                                                          ║"
    echo "║  SSH: ssh dbai@<raspberry-ip> (Passwort: dbai2026)       ║"
    echo "║                                                          ║"
    echo "╚══════════════════════════════════════════════════════════╝"

    # Optional: Direkt auf SD-Karte schreiben
    if [[ -n "$WRITE_DEV" ]]; then
        echo ""
        echo "⚠ Schreibe auf ${WRITE_DEV} in 5 Sekunden... (Ctrl+C zum Abbrechen)"
        sleep 5
        dd if="$img" of="$WRITE_DEV" bs=4M status=progress conv=fsync
        sync
        echo "✅ Image auf ${WRITE_DEV} geschrieben!"
    fi
}

# ═══════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════
main() {
    local start_time=$(date +%s)

    check_deps
    create_image
    create_rootfs
    configure_system
    install_rpi_firmware
    install_ghostshell
    install_services
    configure_network
    finalize_image

    local end_time=$(date +%s)
    local duration=$(( (end_time - start_time) / 60 ))
    echo ""
    echo "⏱ Build-Dauer: ${duration} Minuten"
}

main "$@"
