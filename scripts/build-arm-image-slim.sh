#!/bin/bash
# =============================================================================
# DBAI GhostShell OS — Slim ARM64 Image Builder (Thin Provisioning)
# =============================================================================
# Erstellt ein minimales 4GB SD-Card-Image, das beim ersten Boot automatisch
# auf die volle Kartengröße expandiert. LLM-Modelle werden NICHT mitgeliefert,
# sondern beim First-Boot-Setup heruntergeladen.
#
# Voraussetzungen:
#   sudo apt install debootstrap qemu-user-static binfmt-support \
#                    kpartx dosfstools parted e2fsprogs rsync
#
# Nutzung:
#   sudo bash scripts/build-arm-image-slim.sh
#   sudo bash scripts/build-arm-image-slim.sh --base alpine   # Alpine statt Debian
#   sudo bash scripts/build-arm-image-slim.sh --size 2G       # Kleinstes Image
#   sudo bash scripts/build-arm-image-slim.sh --write /dev/sdX
#
# Ergebnis:
#   dist/ghostshell-slim-arm64-YYYYMMDD.img   (< 4GB, flashbar auf jede SD)
#   dist/ghostshell-slim-arm64-YYYYMMDD.img.sha256
#   dist/ghostshell-slim-arm64-YYYYMMDD.img.xz  (komprimiert, ~1.5GB)
# =============================================================================

set -euo pipefail

# ─── Konfiguration ────────────────────────────────────────────────
DBAI_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="/tmp/dbai-arm-slim"
OUTPUT_DIR="${DBAI_ROOT}/dist"
IMAGE_SIZE="4G"                 # Thin: nur 4GB statt 32GB
IMAGE_NAME="ghostshell-slim-arm64-$(date +%Y%m%d).img"
WRITE_DEV=""
BOOT_SIZE="256M"                # Boot kleiner (nur Firmware+Kernel)
BASE_SYSTEM="debian"            # "debian" oder "alpine"
DEBIAN_RELEASE="bookworm"
COMPRESS="yes"                  # xz-Kompression am Ende
SKIP_CHROMIUM="no"              # --headless: kein Chromium/X11

# RPi3 Firmware
RPI_FIRMWARE_URL="https://github.com/raspberrypi/firmware/archive/refs/heads/stable.tar.gz"

# ─── Argumente ────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case $1 in
        --size)       IMAGE_SIZE="$2"; shift 2 ;;
        --write)      WRITE_DEV="$2";  shift 2 ;;
        --output)     OUTPUT_DIR="$2"; shift 2 ;;
        --name)       IMAGE_NAME="$2"; shift 2 ;;
        --base)       BASE_SYSTEM="$2"; shift 2 ;;
        --headless)   SKIP_CHROMIUM="yes"; shift ;;
        --no-compress) COMPRESS="no"; shift ;;
        *)            echo "Unbekannt: $1"; exit 1 ;;
    esac
done

# ─── Root Check ───────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    echo "❌ Root-Rechte erforderlich: sudo bash $0"
    exit 1
fi

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  🧠 GhostShell OS — Slim ARM64 Image Builder            ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  Modus:      Thin Provisioning (${IMAGE_SIZE} → auto-expand)"
echo "║  Base:       ${BASE_SYSTEM}                              ║"
echo "║  Headless:   ${SKIP_CHROMIUM}                            ║"
echo "║  Komprimiert: ${COMPRESS}                                ║"
echo "║  Output:     ${OUTPUT_DIR}/${IMAGE_NAME}                 ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ─── Abhängigkeiten ───────────────────────────────────────────────
check_deps() {
    local missing=()
    local required=(debootstrap kpartx parted mkfs.vfat mkfs.ext4 rsync)

    # Alpine braucht kein debootstrap
    if [[ "$BASE_SYSTEM" == "alpine" ]]; then
        required=(kpartx parted mkfs.vfat mkfs.ext4 rsync curl)
    fi

    for cmd in "${required[@]}"; do
        command -v "$cmd" &>/dev/null || missing+=("$cmd")
    done

    # QEMU für Cross-Build
    if [[ ! -f /usr/bin/qemu-aarch64-static ]]; then
        missing+=("qemu-user-static")
    fi

    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "❌ Fehlende Tools: ${missing[*]}"
        echo "→ sudo apt install debootstrap qemu-user-static binfmt-support kpartx dosfstools parted e2fsprogs rsync"
        exit 1
    fi

    # binfmt für aarch64
    if [[ ! -f /proc/sys/fs/binfmt_misc/qemu-aarch64 ]]; then
        echo "⚠ binfmt für aarch64 nicht registriert..."
        update-binfmts --enable qemu-aarch64 2>/dev/null || \
        echo ':qemu-aarch64:M::\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\xb7\x00:\xff\xff\xff\xff\xff\xff\xff\x00\xff\xff\xff\xff\xff\xff\xff\xff\xfe\xff\xff\xff:/usr/bin/qemu-aarch64-static:CF' \
            > /proc/sys/fs/binfmt_misc/register 2>/dev/null || true
    fi
    echo "✅ Build-Abhängigkeiten OK"
}

# ─── Cleanup ──────────────────────────────────────────────────────
LOOP_DEV=""
cleanup() {
    echo "→ Räume auf..."
    set +e
    sync
    umount -lf "${BUILD_DIR}/rootfs/boot/firmware" 2>/dev/null
    umount -lf "${BUILD_DIR}/rootfs/proc" 2>/dev/null
    umount -lf "${BUILD_DIR}/rootfs/sys" 2>/dev/null
    umount -lf "${BUILD_DIR}/rootfs/dev/pts" 2>/dev/null
    umount -lf "${BUILD_DIR}/rootfs/dev" 2>/dev/null
    umount -lf "${BUILD_DIR}/rootfs" 2>/dev/null
    umount -lf "${BUILD_DIR}/boot" 2>/dev/null
    if [[ -n "$LOOP_DEV" ]]; then
        kpartx -d "$LOOP_DEV" 2>/dev/null
        losetup -d "$LOOP_DEV" 2>/dev/null
    fi
    set -e
}
trap cleanup EXIT

# ═══════════════════════════════════════════════════════════════════
# Phase 1: Dünnes Image erstellen (4GB)
# ═══════════════════════════════════════════════════════════════════
create_slim_image() {
    echo "═══ Phase 1/9: Slim Image erstellen (${IMAGE_SIZE}) ═══"
    mkdir -p "$OUTPUT_DIR" "$BUILD_DIR"

    local img="${OUTPUT_DIR}/${IMAGE_NAME}"
    rm -f "$img"

    # Echte 4GB-Datei (KEINE sparse — für dd-Flash)
    echo "→ Erstelle ${IMAGE_SIZE} Image..."
    truncate -s "$IMAGE_SIZE" "$img"

    # Partitionstabelle (MBR für RPi3-Kompatibilität)
    echo "→ Partitionstabelle (MBR)..."
    parted -s "$img" mklabel msdos
    parted -s "$img" mkpart primary fat32 4MiB ${BOOT_SIZE}
    parted -s "$img" set 1 boot on
    parted -s "$img" set 1 lba on
    parted -s "$img" mkpart primary ext4 ${BOOT_SIZE} 100%

    # Loop-Device
    LOOP_DEV=$(losetup --find --show --partscan "$img")
    echo "→ Loop: ${LOOP_DEV}"
    sleep 2
    partprobe "$LOOP_DEV" 2>/dev/null || true
    sleep 1

    local boot_part="${LOOP_DEV}p1"
    local root_part="${LOOP_DEV}p2"

    if [[ ! -b "$boot_part" ]]; then
        echo "→ Verwende kpartx..."
        kpartx -as "$LOOP_DEV"
        local loop_name=$(basename "$LOOP_DEV")
        boot_part="/dev/mapper/${loop_name}p1"
        root_part="/dev/mapper/${loop_name}p2"
        sleep 1
    fi

    # Formatieren
    echo "→ Boot: FAT32 (${BOOT_SIZE})..."
    mkfs.vfat -F 32 -n GHOSTBOOT "$boot_part"

    echo "→ Root: ext4 (Rest)..."
    mkfs.ext4 -L ghostshell-root -O ^metadata_csum -m 1 -J size=16 "$root_part"
    # -m 1: nur 1% reserved (statt 5%), spart ~150MB
    # -J size=16: kleineres Journal

    # Mounten
    mkdir -p "${BUILD_DIR}/rootfs" "${BUILD_DIR}/boot"
    mount "$root_part" "${BUILD_DIR}/rootfs"
    mkdir -p "${BUILD_DIR}/rootfs/boot/firmware"
    mount "$boot_part" "${BUILD_DIR}/rootfs/boot/firmware"

    echo "✅ Slim Image partitioniert"
}

# ═══════════════════════════════════════════════════════════════════
# Phase 2: Minimales Root-FS (Debian oder Alpine)
# ═══════════════════════════════════════════════════════════════════
create_rootfs() {
    echo "═══ Phase 2/9: Base System (${BASE_SYSTEM}) ═══"
    local rootfs="${BUILD_DIR}/rootfs"

    if [[ "$BASE_SYSTEM" == "alpine" ]]; then
        create_rootfs_alpine "$rootfs"
    else
        create_rootfs_debian "$rootfs"
    fi
}

create_rootfs_debian() {
    local rootfs="$1"
    echo "→ Debian ${DEBIAN_RELEASE} ARM64 (minbase)..."

    debootstrap --arch=arm64 \
        --foreign \
        --variant=minbase \
        --include=systemd,systemd-sysv,dbus,locales,sudo,curl,wget,ca-certificates,gnupg \
        "$DEBIAN_RELEASE" "$rootfs" http://deb.debian.org/debian

    cp /usr/bin/qemu-aarch64-static "${rootfs}/usr/bin/"
    echo "→ Debootstrap second stage..."
    chroot "$rootfs" /debootstrap/debootstrap --second-stage

    echo "✅ Debian ARM64 Base installiert"
}

create_rootfs_alpine() {
    local rootfs="$1"
    local ALPINE_VERSION="3.20"
    local ALPINE_MIRROR="https://dl-cdn.alpinelinux.org/alpine"
    local ALPINE_ARCH="aarch64"

    echo "→ Alpine Linux ${ALPINE_VERSION} ARM64 (~50MB statt ~600MB)..."
    mkdir -p "$rootfs"

    # Alpine minirootfs herunterladen
    local mini_url="${ALPINE_MIRROR}/v${ALPINE_VERSION}/releases/${ALPINE_ARCH}/alpine-minirootfs-${ALPINE_VERSION}.0-${ALPINE_ARCH}.tar.gz"
    local mini_tar="${BUILD_DIR}/alpine-minirootfs.tar.gz"

    if [[ ! -f "$mini_tar" ]]; then
        echo "→ Lade Alpine minirootfs..."
        curl -sL -o "$mini_tar" "$mini_url" || {
            # Fallback: neueste Version suchen
            echo "→ Suche neueste Version..."
            mini_url=$(curl -sL "${ALPINE_MIRROR}/v${ALPINE_VERSION}/releases/${ALPINE_ARCH}/" | \
                grep -o 'alpine-minirootfs-[0-9.]*-aarch64.tar.gz' | sort -V | tail -1)
            curl -sL -o "$mini_tar" "${ALPINE_MIRROR}/v${ALPINE_VERSION}/releases/${ALPINE_ARCH}/${mini_url}"
        }
    fi

    # Entpacken
    tar xzf "$mini_tar" -C "$rootfs"

    # QEMU für Cross-Build
    cp /usr/bin/qemu-aarch64-static "${rootfs}/usr/bin/"

    # DNS für Chroot
    cp /etc/resolv.conf "${rootfs}/etc/resolv.conf"

    # APK Repository
    mkdir -p "${rootfs}/etc/apk"
    echo "${ALPINE_MIRROR}/v${ALPINE_VERSION}/main" > "${rootfs}/etc/apk/repositories"
    echo "${ALPINE_MIRROR}/v${ALPINE_VERSION}/community" >> "${rootfs}/etc/apk/repositories"

    # Chroot-Mounts
    mount --bind /dev     "${rootfs}/dev"
    mount --bind /dev/pts "${rootfs}/dev/pts"
    mount -t proc proc    "${rootfs}/proc"
    mount -t sysfs sys    "${rootfs}/sys"

    # Basis-Pakete
    chroot "$rootfs" apk update
    chroot "$rootfs" apk add --no-cache \
        openrc busybox-initscripts \
        linux-rpi4 linux-firmware-brcm \
        sudo bash curl wget ca-certificates \
        openssh shadow e2fsprogs parted \
        python3 py3-pip py3-psycopg2 \
        postgresql16 postgresql16-contrib \
        nodejs npm \
        networkmanager \
        htop nano less util-linux coreutils

    # OpenRC statt systemd (Alpine Default)
    chroot "$rootfs" rc-update add networking boot
    chroot "$rootfs" rc-update add sshd default

    # Unmount
    umount -lf "${rootfs}/proc" "${rootfs}/sys" "${rootfs}/dev/pts" "${rootfs}/dev" 2>/dev/null || true

    echo "✅ Alpine Linux Base installiert (~50MB)"
}

# ═══════════════════════════════════════════════════════════════════
# Phase 3: Minimale Pakete installieren (Debian-Pfad)
# ═══════════════════════════════════════════════════════════════════
install_packages() {
    echo "═══ Phase 3/9: Pakete installieren (minimal) ═══"
    local rootfs="${BUILD_DIR}/rootfs"

    if [[ "$BASE_SYSTEM" == "alpine" ]]; then
        echo "→ Alpine: Pakete bereits in Phase 2 installiert"
        return
    fi

    # Chroot-Mounts
    mount --bind /dev     "${rootfs}/dev"
    mount --bind /dev/pts "${rootfs}/dev/pts"
    mount -t proc proc    "${rootfs}/proc"
    mount -t sysfs sys    "${rootfs}/sys"

    # APT Sources
    cat > "${rootfs}/etc/apt/sources.list" << EOF
deb http://deb.debian.org/debian ${DEBIAN_RELEASE} main contrib non-free non-free-firmware
deb http://security.debian.org/debian-security ${DEBIAN_RELEASE}-security main contrib non-free non-free-firmware
EOF

    chroot "$rootfs" bash -c "
        export DEBIAN_FRONTEND=noninteractive

        apt-get update -qq

        # ── Absolutes Minimum ──
        apt-get install -y -qq --no-install-recommends \
            linux-image-arm64 \
            firmware-brcm80211 \
            systemd-timesyncd \
            locales \
            net-tools iproute2 wireless-tools wpasupplicant \
            openssh-server \
            parted fdisk cloud-guest-utils \
            git nano less htop

        # ── Datenbank (Kern von GhostShell) ──
        apt-get install -y -qq --no-install-recommends \
            postgresql-16 postgresql-16-pgvector \
            postgresql-contrib-16

        # ── Python (minimal — nur Runtime, kein -dev) ──
        apt-get install -y -qq --no-install-recommends \
            python3-minimal python3-pip python3-venv \
            python3-psycopg2

        # ── Node.js (nur für Frontend-Serving) ──
        curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
        apt-get install -y -qq --no-install-recommends nodejs

        # ── Netzwerk ──
        apt-get install -y -qq --no-install-recommends \
            network-manager

        # ── Display (optional, nur wenn nicht headless) ──
        $( [[ "$SKIP_CHROMIUM" == "yes" ]] && echo "echo '→ Headless-Modus: kein X11/Chromium'" || echo "
        apt-get install -y -qq --no-install-recommends \
            chromium xserver-xorg-core xinit x11-xserver-utils \
            openbox xfonts-base
        ")

        # ── AGGRESSIVES Cleanup ──
        apt-get clean
        apt-get autoremove -y
        rm -rf /var/lib/apt/lists/*
        rm -rf /var/cache/apt/archives/*.deb
        rm -rf /usr/share/doc/*
        rm -rf /usr/share/man/*
        rm -rf /usr/share/info/*
        rm -rf /usr/share/locale/!(en|de|locale.alias)
        rm -rf /var/log/*.log
        rm -rf /tmp/* /var/tmp/*

        # Node.js Cache aufräumen
        npm cache clean --force 2>/dev/null || true
        rm -rf /root/.npm
    "

    # Locale
    chroot "$rootfs" bash -c "
        sed -i 's/# en_US.UTF-8/en_US.UTF-8/' /etc/locale.gen
        sed -i 's/# de_DE.UTF-8/de_DE.UTF-8/' /etc/locale.gen
        locale-gen
        update-locale LANG=en_US.UTF-8
    "

    chroot "$rootfs" ln -sf /usr/share/zoneinfo/Europe/Berlin /etc/localtime

    echo "✅ Minimale Pakete installiert"
}

# ═══════════════════════════════════════════════════════════════════
# Phase 4: RPi3 Boot-Firmware
# ═══════════════════════════════════════════════════════════════════
install_firmware() {
    echo "═══ Phase 4/9: RPi3 Firmware ═══"
    local rootfs="${BUILD_DIR}/rootfs"
    local bootdir="${rootfs}/boot/firmware"
    local fw_dir="${BUILD_DIR}/rpi-firmware"

    echo "→ Lade RPi Firmware..."
    mkdir -p "$fw_dir"
    if [[ ! -d "${fw_dir}/firmware-stable" ]]; then
        curl -sL "$RPI_FIRMWARE_URL" | tar xz -C "$fw_dir"
    fi

    local fw_src="${fw_dir}/firmware-stable/boot"
    cp "${fw_src}/bootcode.bin"  "$bootdir/"
    cp "${fw_src}/start.elf"     "$bootdir/"
    cp "${fw_src}/fixup.dat"     "$bootdir/"

    # Device Tree RPi3
    cp "${fw_src}/bcm2710-rpi-3-b.dtb"     "$bootdir/" 2>/dev/null || true
    cp "${fw_src}/bcm2710-rpi-3-b-plus.dtb" "$bootdir/" 2>/dev/null || true
    mkdir -p "${bootdir}/overlays"
    cp "${fw_src}/overlays/"* "${bootdir}/overlays/" 2>/dev/null || true

    # Kernel
    local kernel=$(ls ${rootfs}/boot/vmlinuz-* 2>/dev/null | head -1)
    local initrd=$(ls ${rootfs}/boot/initrd.img-* 2>/dev/null | head -1)
    [[ -n "$kernel" ]] && cp "$kernel" "${bootdir}/kernel8.img"
    [[ -n "$initrd" ]] && cp "$initrd" "${bootdir}/initramfs8"

    # config.txt
    cat > "${bootdir}/config.txt" << 'RPICFG'
# GhostShell OS — RPi3 ARM64 (Slim)
arm_64bit=1
kernel=kernel8.img
initramfs initramfs8 followkernel
gpu_mem=64
hdmi_force_hotplug=1
hdmi_drive=2
enable_uart=1
dtoverlay=miniuart-bt
dtoverlay=vc4-fkms-v3d
disable_splash=1
RPICFG

    # cmdline.txt
    cat > "${bootdir}/cmdline.txt" << 'CMDLINE'
console=serial0,115200 console=tty1 root=LABEL=ghostshell-root rootfstype=ext4 rootwait fsck.repair=yes quiet loglevel=3 systemd.show_status=auto
CMDLINE

    # fstab (minimierte tmpfs)
    cat > "${rootfs}/etc/fstab" << 'FSTAB'
LABEL=ghostshell-root  /               ext4  defaults,noatime,commit=600  0  1
LABEL=GHOSTBOOT        /boot/firmware  vfat  defaults                     0  2
tmpfs                  /tmp            tmpfs defaults,nosuid,size=128m    0  0
tmpfs                  /var/log        tmpfs defaults,nosuid,size=64m     0  0
FSTAB

    echo "✅ RPi3 Firmware installiert"
}

# ═══════════════════════════════════════════════════════════════════
# Phase 5: GhostShell Core (ohne Modelle, ohne node_modules)
# ═══════════════════════════════════════════════════════════════════
install_ghostshell_core() {
    echo "═══ Phase 5/9: GhostShell Core (lean) ═══"
    local rootfs="${BUILD_DIR}/rootfs"
    local target="${rootfs}/opt/dbai"
    mkdir -p "$target"

    # NUR Source-Code kopieren (kein dist, kein venv, keine Modelle)
    echo "→ Kopiere Core-Dateien..."
    rsync -a \
        --exclude='node_modules' \
        --exclude='__pycache__' \
        --exclude='.git' \
        --exclude='dist' \
        --exclude='*.pyc' \
        --exclude='.venv' \
        --exclude='pics' \
        --exclude='*.img' \
        --exclude='*.iso' \
        --exclude='*.tar.gz' \
        --exclude='*.xz' \
        --exclude='llm/models' \
        "${DBAI_ROOT}/" "$target/"

    # requirements.txt für First-Boot venv-Build
    cat > "${target}/requirements-slim.txt" << 'REQS'
# GhostShell OS — Slim Requirements (First-Boot Install)
psycopg2-binary>=2.9
psutil>=5.9
toml>=0.10
fastapi>=0.104
uvicorn[standard]>=0.24
websockets>=12.0
PyJWT>=2.8
bcrypt>=4.1
aiofiles>=23.2
httpx>=0.25
REQS

    # Frontend: Pre-Built dist wenn möglich (auf Host bauen)
    echo "→ Frontend Build (nativ auf Host)..."
    local fe_tmp="/tmp/dbai-fe-slim"
    rm -rf "$fe_tmp"
    cp -r "${DBAI_ROOT}/frontend" "$fe_tmp"
    cd "$fe_tmp"
    if npm install --omit=dev 2>/dev/null || npm install --legacy-peer-deps --omit=dev 2>/dev/null; then
        npx --yes vite build 2>/dev/null && {
            mkdir -p "${target}/frontend/dist"
            cp -r dist/* "${target}/frontend/dist/"
            echo "→ Frontend dist gebaut und kopiert"
        }
    else
        echo "⚠ Frontend-Build fehlgeschlagen — wird beim First-Boot gebaut"
    fi
    cd "$DBAI_ROOT"
    rm -rf "$fe_tmp"

    echo "✅ GhostShell Core installiert (ohne Modelle, ohne venv)"
}

# ═══════════════════════════════════════════════════════════════════
# Phase 6: First-Boot Filesystem Expansion + Setup Wizard
# ═══════════════════════════════════════════════════════════════════
install_firstboot_system() {
    echo "═══ Phase 6/9: First-Boot System ═══"
    local rootfs="${BUILD_DIR}/rootfs"

    # ─── 6a: Filesystem Auto-Expand ──────────────────────────────
    cat > "${rootfs}/usr/local/sbin/ghostshell-expand" << 'EXPAND'
#!/bin/bash
# =================================================================
# GhostShell OS — Auto-Expand Root-Partition
# Expandiert die Root-Partition auf die volle SD-Karten-Größe
# Läuft EINMAL beim ersten Boot, entfernt sich dann selbst
# =================================================================
set -e

MARKER="/opt/dbai/.expanded"
if [[ -f "$MARKER" ]]; then
    exit 0
fi

echo "╔══════════════════════════════════════════════╗"
echo "║  🔧 Filesystem wird auf volle Größe          ║"
echo "║     expandiert... Bitte warten.               ║"
echo "╚══════════════════════════════════════════════╝"

# Root-Device ermitteln
ROOT_PART=$(findmnt / -o SOURCE -n | head -1)
ROOT_DISK=$(echo "$ROOT_PART" | sed 's/p\?[0-9]*$//')
PART_NUM=$(echo "$ROOT_PART" | grep -o '[0-9]*$')

if [[ -z "$ROOT_DISK" || -z "$PART_NUM" ]]; then
    echo "⚠ Konnte Root-Partition nicht ermitteln"
    touch "$MARKER"
    exit 0
fi

echo "→ Root: ${ROOT_PART}"
echo "→ Disk: ${ROOT_DISK}"
echo "→ Partition: ${PART_NUM}"

# Partition vergrößern
if command -v growpart &>/dev/null; then
    echo "→ growpart ${ROOT_DISK} ${PART_NUM}..."
    growpart "$ROOT_DISK" "$PART_NUM" 2>/dev/null || true
elif command -v parted &>/dev/null; then
    echo "→ parted resizepart..."
    parted -s "$ROOT_DISK" resizepart "$PART_NUM" 100% 2>/dev/null || true
else
    # Fallback: fdisk
    echo "→ fdisk resize..."
    {
        echo d       # delete
        echo "$PART_NUM"
        echo n       # new
        echo p       # primary
        echo "$PART_NUM"
        echo         # default start
        echo         # default end (full disk)
        echo w       # write
    } | fdisk "$ROOT_DISK" 2>/dev/null || true
    partprobe "$ROOT_DISK" 2>/dev/null || true
fi

# Filesystem vergrößern
echo "→ resize2fs ${ROOT_PART}..."
resize2fs "$ROOT_PART" 2>/dev/null || {
    # Für BTRFS
    btrfs filesystem resize max / 2>/dev/null || true
}

# Ergebnis
NEW_SIZE=$(df -h / | tail -1 | awk '{print $2}')
echo "✅ Filesystem expandiert auf ${NEW_SIZE}"

touch "$MARKER"

# Log
echo "$(date): Root-Partition expandiert auf ${NEW_SIZE}" >> /opt/dbai/logs/firstboot.log
EXPAND
    chmod +x "${rootfs}/usr/local/sbin/ghostshell-expand"

    # Systemd Service für Auto-Expand (läuft VOR allem anderen)
    cat > "${rootfs}/etc/systemd/system/ghostshell-expand.service" << 'EOF'
[Unit]
Description=GhostShell OS — Root Partition Auto-Expand
DefaultDependencies=no
Before=local-fs-pre.target
After=systemd-remount-fs.service
ConditionPathExists=!/opt/dbai/.expanded

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/ghostshell-expand
RemainAfterExit=yes
StandardOutput=journal+console
TimeoutStartSec=120

[Install]
WantedBy=local-fs.target
EOF

    # ─── 6b: First-Boot Setup Wizard ─────────────────────────────
    cat > "${rootfs}/usr/local/sbin/ghostshell-setup" << 'SETUP_WIZARD'
#!/bin/bash
# =================================================================
# GhostShell OS — First-Boot Setup Wizard
# Interaktives Setup beim ersten Start
# =================================================================
set -e

MARKER="/opt/dbai/.setup-done"
LOG="/opt/dbai/logs/firstboot.log"
mkdir -p /opt/dbai/logs

if [[ -f "$MARKER" ]]; then
    exit 0
fi

# TUI-Tool wählen
TUI=""
if command -v whiptail &>/dev/null; then
    TUI="whiptail"
elif command -v dialog &>/dev/null; then
    TUI="dialog"
else
    TUI="plain"
fi

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"
    echo "$*"
}

show_msg() {
    if [[ "$TUI" == "plain" ]]; then
        echo -e "\n$2\n"
        sleep 2
    else
        $TUI --title "$1" --msgbox "$2" 12 60
    fi
}

show_input() {
    if [[ "$TUI" == "plain" ]]; then
        echo -n "$2 [$3]: "
        read -r ans
        echo "${ans:-$3}"
    else
        $TUI --title "$1" --inputbox "$2" 10 60 "$3" 3>&1 1>&2 2>&3
    fi
}

show_password() {
    if [[ "$TUI" == "plain" ]]; then
        echo -n "$2: "
        read -rs ans
        echo ""
        echo "$ans"
    else
        $TUI --title "$1" --passwordbox "$2" 10 60 3>&1 1>&2 2>&3
    fi
}

show_yesno() {
    if [[ "$TUI" == "plain" ]]; then
        echo -n "$2 [J/n]: "
        read -r ans
        [[ "$ans" != "n" && "$ans" != "N" ]]
    else
        $TUI --title "$1" --yesno "$2" 10 60
    fi
}

show_menu() {
    local title="$1"
    local text="$2"
    shift 2
    if [[ "$TUI" == "plain" ]]; then
        echo "$text"
        local i=1
        while [[ $# -gt 0 ]]; do
            echo "  $1) $2"
            shift 2
            i=$((i+1))
        done
        echo -n "Auswahl: "
        read -r ans
        echo "$ans"
    else
        $TUI --title "$title" --menu "$text" 18 70 10 "$@" 3>&1 1>&2 2>&3
    fi
}

show_gauge() {
    local title="$1"
    local pct="$2"
    if [[ "$TUI" != "plain" ]]; then
        echo "$pct" | $TUI --title "$title" --gauge "Bitte warten..." 8 60 0
    else
        echo "[$pct%] $title"
    fi
}

# ═════════════════════════════════════════════════════════
# Wizard Start
# ═════════════════════════════════════════════════════════

show_msg "Willkommen" "
╔════════════════════════════════════════════╗
║                                            ║
║   🧠  G h o s t S h e l l   O S           ║
║                                            ║
║   Erster Start — Einrichtungsassistent     ║
║                                            ║
║   Das System wird jetzt konfiguriert.      ║
║   Dies dauert etwa 5-10 Minuten.           ║
║                                            ║
╚════════════════════════════════════════════╝"

log "═══ GhostShell Setup gestartet ═══"

# ─── 1. Sprache ──────────────────────────────────────────
LANG_CHOICE=$(show_menu "Sprache" "Systemsprache wählen:" \
    "de" "Deutsch" \
    "en" "English" \
    "fr" "Français" \
    "es" "Español") || LANG_CHOICE="de"

case "$LANG_CHOICE" in
    de) SYS_LANG="de_DE.UTF-8"; SYS_TZ="Europe/Berlin" ;;
    en) SYS_LANG="en_US.UTF-8"; SYS_TZ="America/New_York" ;;
    fr) SYS_LANG="fr_FR.UTF-8"; SYS_TZ="Europe/Paris" ;;
    es) SYS_LANG="es_ES.UTF-8"; SYS_TZ="Europe/Madrid" ;;
    *)  SYS_LANG="en_US.UTF-8"; SYS_TZ="UTC" ;;
esac
log "Sprache: ${SYS_LANG}"

# ─── 2. Hostname ─────────────────────────────────────────
HOSTNAME=$(show_input "Hostname" "Hostname für dieses System:" "ghostshell") || HOSTNAME="ghostshell"
echo "$HOSTNAME" > /etc/hostname
sed -i "s/ghostshell/${HOSTNAME}/g" /etc/hosts 2>/dev/null || true
hostnamectl set-hostname "$HOSTNAME" 2>/dev/null || true
log "Hostname: ${HOSTNAME}"

# ─── 3. Benutzer-Passwort ────────────────────────────────
USER_PASS=$(show_password "Passwort" "Neues Passwort für Benutzer 'dbai':") || USER_PASS="dbai2026"
echo "dbai:${USER_PASS}" | chpasswd
log "Benutzer-Passwort gesetzt"

# ─── 4. Root-Passwort ────────────────────────────────────
if show_yesno "Root" "Eigenes Root-Passwort setzen? (Empfohlen für Sicherheit)"; then
    ROOT_PASS=$(show_password "Root-Passwort" "Neues Root-Passwort:") || ROOT_PASS="ghostshell2026"
    echo "root:${ROOT_PASS}" | chpasswd
    log "Root-Passwort geändert"
fi

# ─── 5. WiFi ─────────────────────────────────────────────
if show_yesno "WiFi" "WiFi jetzt einrichten?"; then
    WIFI_SSID=$(show_input "WiFi SSID" "Name des WiFi-Netzwerks:" "") || WIFI_SSID=""
    if [[ -n "$WIFI_SSID" ]]; then
        WIFI_PASS=$(show_password "WiFi Passwort" "WiFi-Passwort für '${WIFI_SSID}':") || WIFI_PASS=""
        # NetworkManager Connection
        nmcli device wifi connect "$WIFI_SSID" password "$WIFI_PASS" 2>/dev/null || {
            # Fallback: wpa_supplicant Config
            cat > /etc/wpa_supplicant/wpa_supplicant.conf << WPAEOF
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=DE

network={
    ssid="${WIFI_SSID}"
    psk="${WIFI_PASS}"
    key_mgmt=WPA-PSK
}
WPAEOF
            log "WiFi konfiguriert: ${WIFI_SSID}"
        }
    fi
fi

# ─── 6. Timezone ─────────────────────────────────────────
TZ=$(show_input "Zeitzone" "Zeitzone (z.B. Europe/Berlin):" "$SYS_TZ") || TZ="$SYS_TZ"
ln -sf "/usr/share/zoneinfo/${TZ}" /etc/localtime
timedatectl set-timezone "$TZ" 2>/dev/null || true
log "Zeitzone: ${TZ}"

# ═════════════════════════════════════════════════════════
# System-Setup (automatisch)
# ═════════════════════════════════════════════════════════

log "→ Python Virtual Environment..."
show_msg "Setup" "Python-Umgebung wird eingerichtet...\nDies kann einige Minuten dauern."

# Python venv
if [[ ! -d /opt/dbai/.venv ]]; then
    python3 -m venv /opt/dbai/.venv 2>/dev/null || true
    /opt/dbai/.venv/bin/pip install --no-cache-dir \
        -r /opt/dbai/requirements-slim.txt 2>/dev/null || {
        # Fallback: System-pip
        pip3 install --break-system-packages --no-cache-dir \
            -r /opt/dbai/requirements-slim.txt 2>/dev/null || true
    }
    log "Python venv erstellt"
fi

# PostgreSQL Setup
log "→ PostgreSQL einrichten..."
systemctl start postgresql 2>/dev/null || true
sleep 3

# Warten auf PostgreSQL
for i in $(seq 1 30); do
    pg_isready -q 2>/dev/null && break
    sleep 1
done

# DB + Rollen
sudo -u postgres psql -c "CREATE ROLE dbai_system WITH LOGIN SUPERUSER PASSWORD 'dbai2026';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE ROLE dbai_runtime WITH LOGIN PASSWORD 'dbai_runtime_2026';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE ROLE dbai_ghost WITH LOGIN PASSWORD 'dbai_ghost_2026';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE dbai OWNER dbai_system;" 2>/dev/null || true

# Extensions
sudo -u postgres psql -d dbai -c "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";" 2>/dev/null || true
sudo -u postgres psql -d dbai -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;" 2>/dev/null || true
sudo -u postgres psql -d dbai -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null || true

# Schemas laden
log "→ SQL-Schemas laden..."
SCHEMA_COUNT=0
for sql in /opt/dbai/schema/*.sql; do
    if [[ -f "$sql" ]]; then
        sudo -u postgres psql -d dbai -f "$sql" 2>/dev/null || true
        SCHEMA_COUNT=$((SCHEMA_COUNT + 1))
    fi
done
log "${SCHEMA_COUNT} Schemas geladen"

# PostgreSQL ARM-Config
PG_CONF_DIR=$(find /etc/postgresql -name "postgresql.conf" -exec dirname {} \; 2>/dev/null | head -1)
if [[ -n "$PG_CONF_DIR" && -f /opt/dbai/config/postgresql-arm.conf ]]; then
    mkdir -p "${PG_CONF_DIR}/conf.d"
    cp /opt/dbai/config/postgresql-arm.conf "${PG_CONF_DIR}/conf.d/ghostshell.conf"
    # pg_hba.conf
    cat >> "${PG_CONF_DIR}/pg_hba.conf" << 'PGHBA'
# GhostShell OS
local   dbai    dbai_system                 md5
local   dbai    dbai_runtime                md5
host    dbai    dbai_runtime    127.0.0.1/32    md5
host    dbai    dbai_system     127.0.0.1/32    md5
PGHBA
    systemctl restart postgresql 2>/dev/null || true
fi

# Frontend Build (falls noch nicht vorhanden)
if [[ ! -d /opt/dbai/frontend/dist ]]; then
    log "→ Frontend Build..."
    cd /opt/dbai/frontend
    npm install --omit=dev 2>/dev/null || npm install --legacy-peer-deps --omit=dev 2>/dev/null || true
    npx --yes vite build 2>/dev/null || true
    npm cache clean --force 2>/dev/null || true
    rm -rf /root/.npm /opt/dbai/frontend/node_modules/.cache
    cd /
fi

# Rechte
chown -R dbai:dbai /opt/dbai
chmod 750 /opt/dbai

touch "$MARKER"

# ═════════════════════════════════════════════════════════
# Fertig
# ═════════════════════════════════════════════════════════

# IP ermitteln
SYS_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[[ -z "$SYS_IP" ]] && SYS_IP="<IP>"

show_msg "Fertig!" "
╔════════════════════════════════════════════╗
║                                            ║
║  ✅ GhostShell OS eingerichtet!            ║
║                                            ║
║  Dashboard: http://${SYS_IP}:3000          ║
║  SSH:       ssh dbai@${SYS_IP}             ║
║                                            ║
║  Das System wird jetzt neu gestartet.      ║
║                                            ║
╚════════════════════════════════════════════╝"

log "═══ Setup abgeschlossen ═══"

# Services starten (kein Reboot nötig)
systemctl daemon-reload
systemctl start dbai.target 2>/dev/null || true
SETUP_WIZARD
    chmod +x "${rootfs}/usr/local/sbin/ghostshell-setup"

    # Systemd Service für Setup Wizard
    cat > "${rootfs}/etc/systemd/system/ghostshell-setup.service" << 'EOF'
[Unit]
Description=GhostShell OS — First-Boot Setup Wizard
After=network-online.target ghostshell-expand.service
Wants=network-online.target
ConditionPathExists=!/opt/dbai/.setup-done

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/ghostshell-setup
StandardInput=tty
StandardOutput=tty
TTYPath=/dev/tty1
RemainAfterExit=yes
TimeoutStartSec=600

[Install]
WantedBy=multi-user.target
EOF

    # ─── 6c: LLM Model-Download Service ─────────────────────────
    cat > "${rootfs}/usr/local/sbin/ghostshell-models" << 'MODEL_DL'
#!/bin/bash
# =================================================================
# GhostShell OS — LLM Model Downloader
# Lädt KI-Modelle erst beim Bedarf herunter, nicht beim Image-Build
# =================================================================

MODEL_DIR="/opt/dbai/llm/models"
LOG="/opt/dbai/logs/models.log"
mkdir -p "$MODEL_DIR" "$(dirname $LOG)"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"
    echo "$*"
}

# Verfügbare Modelle
declare -A MODELS=(
    ["tinyllama"]="https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf|669MB"
    ["phi-2"]="https://huggingface.co/TheBloke/phi-2-GGUF/resolve/main/phi-2.Q4_K_M.gguf|1.6GB"
    ["mistral-7b"]="https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf|4.1GB"
    ["codellama-7b"]="https://huggingface.co/TheBloke/CodeLlama-7B-Instruct-GGUF/resolve/main/codellama-7b-instruct.Q4_K_M.gguf|4.1GB"
)

list_models() {
    echo ""
    echo "Verfügbare Modelle:"
    echo "─────────────────────────────────────────"
    for name in "${!MODELS[@]}"; do
        IFS='|' read -r url size <<< "${MODELS[$name]}"
        local status="❌ Nicht installiert"
        local filename=$(basename "$url")
        [[ -f "${MODEL_DIR}/${filename}" ]] && status="✅ Installiert"
        printf "  %-15s %8s  %s\n" "$name" "$size" "$status"
    done
    echo ""
}

download_model() {
    local name="$1"
    if [[ -z "${MODELS[$name]}" ]]; then
        echo "❌ Unbekanntes Modell: $name"
        list_models
        return 1
    fi

    IFS='|' read -r url size <<< "${MODELS[$name]}"
    local filename=$(basename "$url")
    local target="${MODEL_DIR}/${filename}"

    if [[ -f "$target" ]]; then
        echo "✅ ${name} bereits vorhanden (${target})"
        return 0
    fi

    echo "→ Lade ${name} (${size})..."
    log "Download: ${name} (${size})"

    curl -L --progress-bar -o "${target}.tmp" "$url" && {
        mv "${target}.tmp" "$target"
        log "OK: ${name} → ${target}"
        echo "✅ ${name} heruntergeladen"

        # In DB registrieren
        sudo -u postgres psql -d dbai -c "
            INSERT INTO dbai_llm.providers (name, provider_type, model_name, endpoint_url, is_active, config)
            VALUES ('${name}', 'local', '${filename}', 'file://${target}', true,
                    '{\"format\":\"gguf\",\"size\":\"${size}\",\"quantization\":\"Q4_K_M\"}'::jsonb)
            ON CONFLICT (name) DO UPDATE SET endpoint_url = EXCLUDED.endpoint_url, is_active = true;
        " 2>/dev/null || true
    } || {
        rm -f "${target}.tmp"
        log "FEHLER: ${name}"
        echo "❌ Download fehlgeschlagen"
        return 1
    }
}

download_interactive() {
    list_models

    # TUI-Auswahl
    if command -v whiptail &>/dev/null; then
        local items=()
        for name in "${!MODELS[@]}"; do
            IFS='|' read -r url size <<< "${MODELS[$name]}"
            items+=("$name" "${size}" "OFF")
        done
        local choices=$(whiptail --title "KI-Modelle" --checklist \
            "Welche Modelle herunterladen?" 18 60 6 \
            "${items[@]}" 3>&1 1>&2 2>&3) || return 0

        for choice in $choices; do
            choice=$(echo "$choice" | tr -d '"')
            download_model "$choice"
        done
    else
        echo "Modell zum Herunterladen eingeben (oder 'alle' / 'keine'):"
        read -r choice
        case "$choice" in
            alle|all)
                for name in "${!MODELS[@]}"; do
                    download_model "$name"
                done ;;
            keine|none|"") ;;
            *) download_model "$choice" ;;
        esac
    fi
}

# ─── Main ────────────────────────────────────────────────
case "${1:-interactive}" in
    list)         list_models ;;
    download)     download_model "$2" ;;
    interactive)  download_interactive ;;
    all)
        for name in "${!MODELS[@]}"; do
            download_model "$name"
        done ;;
    *)
        echo "Nutzung: ghostshell-models [list|download <name>|interactive|all]"
        list_models ;;
esac
MODEL_DL
    chmod +x "${rootfs}/usr/local/sbin/ghostshell-models"

    # Model-Download Service (optional, manuell oder via Setup)
    cat > "${rootfs}/etc/systemd/system/ghostshell-models.service" << 'EOF'
[Unit]
Description=GhostShell OS — LLM Model Downloader
After=network-online.target ghostshell-setup.service
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/ghostshell-models interactive
StandardInput=tty
StandardOutput=tty
TTYPath=/dev/tty1
TimeoutStartSec=3600

[Install]
WantedBy=multi-user.target
EOF

    echo "✅ First-Boot System (Expand + Wizard + Model-Download)"
}

# ═══════════════════════════════════════════════════════════════════
# Phase 7: Services & User
# ═══════════════════════════════════════════════════════════════════
install_services() {
    echo "═══ Phase 7/9: Services konfigurieren ═══"
    local rootfs="${BUILD_DIR}/rootfs"

    # User erstellen
    chroot "$rootfs" bash -c "
        useradd -m -s /bin/bash -G audio,video,input,dialout dbai 2>/dev/null || true
        echo 'dbai:dbai2026' | chpasswd
        echo 'dbai ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/dbai
        chmod 440 /etc/sudoers.d/dbai
        echo 'root:ghostshell2026' | chpasswd
    " 2>/dev/null || true

    # PostgreSQL ARM-Config
    mkdir -p "${rootfs}/opt/dbai/config"
    cat > "${rootfs}/opt/dbai/config/postgresql-arm.conf" << 'PGCONF'
# GhostShell ARM64 — PostgreSQL (RPi3, 1GB RAM)
listen_addresses = 'localhost'
port = 5432
max_connections = 30
shared_buffers = 128MB
effective_cache_size = 256MB
work_mem = 4MB
maintenance_work_mem = 32MB
wal_buffers = 4MB
checkpoint_completion_target = 0.9
max_wal_size = 256MB
min_wal_size = 64MB
random_page_cost = 1.1
log_timezone = 'Europe/Berlin'
timezone = 'Europe/Berlin'
PGCONF

    # ─── Systemd Services ────────────────────────────────────────

    # DBAI Web (FastAPI)
    cat > "${rootfs}/etc/systemd/system/dbai-web.service" << 'EOF'
[Unit]
Description=GhostShell — Neural Bridge (FastAPI)
After=postgresql.service
Requires=postgresql.service

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
ExecStart=/opt/dbai/.venv/bin/python3 -m uvicorn web.server:app --host 0.0.0.0 --port 3000 --workers 2
Restart=always
RestartSec=5
MemoryMax=256M

[Install]
WantedBy=multi-user.target
EOF

    # Hardware Monitor
    cat > "${rootfs}/etc/systemd/system/dbai-hardware.service" << 'EOF'
[Unit]
Description=GhostShell — Hardware Monitor
After=postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=dbai
WorkingDirectory=/opt/dbai
Environment=DBAI_ARCH=arm64
ExecStart=/opt/dbai/.venv/bin/python3 -c "from bridge.hardware_monitor import HardwareMonitor; import asyncio; m = HardwareMonitor(); asyncio.get_event_loop().run_until_complete(m.run())"
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    # Kiosk (optional)
    if [[ "$SKIP_CHROMIUM" != "yes" ]]; then
        cat > "${rootfs}/etc/systemd/system/dbai-kiosk.service" << 'EOF'
[Unit]
Description=GhostShell — Kiosk (Chromium)
After=dbai-web.service
Requires=dbai-web.service

[Service]
Type=simple
User=dbai
Environment=DISPLAY=:0
ExecStartPre=/bin/sleep 5
ExecStart=/bin/bash -c "startx /usr/bin/chromium --no-sandbox --kiosk --disable-gpu --noerrdialogs --no-first-run http://localhost:3000"
Restart=on-failure
RestartSec=10

[Install]
WantedBy=graphical.target
EOF
    fi

    # Services aktivieren
    chroot "$rootfs" bash -c "
        systemctl enable postgresql 2>/dev/null || true
        systemctl enable ssh 2>/dev/null || true
        systemctl enable NetworkManager 2>/dev/null || true
        systemctl enable ghostshell-expand.service 2>/dev/null || true
        systemctl enable ghostshell-setup.service 2>/dev/null || true
        # dbai-web wird NACH Setup aktiviert (im setup-wizard)
        # systemctl enable dbai-web.service
    " 2>/dev/null || true

    # Auto-Login TTY1
    mkdir -p "${rootfs}/etc/systemd/system/getty@tty1.service.d"
    cat > "${rootfs}/etc/systemd/system/getty@tty1.service.d/autologin.conf" << 'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin root --noclear %I $TERM
EOF

    # MOTD
    cat > "${rootfs}/etc/motd" << 'MOTD'

  ╔══════════════════════════════════════════════════════════╗
  ║                                                          ║
  ║   🧠  G h o s t S h e l l   O S   (ARM64 Slim)          ║
  ║                                                          ║
  ║   "The Ghost is the Logic. The Database is the Shell."   ║
  ║                                                          ║
  ║   Setup:    ghostshell-setup     (Ersteinrichtung)       ║
  ║   Modelle:  ghostshell-models    (KI-Modelle laden)      ║
  ║   Dashboard: http://localhost:3000                       ║
  ║                                                          ║
  ╚══════════════════════════════════════════════════════════╝

MOTD

    echo "✅ Services konfiguriert"
}

# ═══════════════════════════════════════════════════════════════════
# Phase 8: Netzwerk
# ═══════════════════════════════════════════════════════════════════
configure_network() {
    echo "═══ Phase 8/9: Netzwerk ═══"
    local rootfs="${BUILD_DIR}/rootfs"

    chroot "$rootfs" bash -c "
        mkdir -p /etc/ssh/sshd_config.d
        echo 'PermitRootLogin yes' > /etc/ssh/sshd_config.d/ghostshell.conf
        echo 'PasswordAuthentication yes' >> /etc/ssh/sshd_config.d/ghostshell.conf
    " 2>/dev/null || true

    mkdir -p "${rootfs}/etc/NetworkManager/system-connections"
    cat > "${rootfs}/etc/resolv.conf" << 'EOF'
nameserver 1.1.1.1
nameserver 8.8.8.8
EOF

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

    echo "✅ Netzwerk konfiguriert"
}

# ═══════════════════════════════════════════════════════════════════
# Phase 9: Image finalisieren & komprimieren
# ═══════════════════════════════════════════════════════════════════
finalize_image() {
    echo "═══ Phase 9/9: Finalisieren ═══"
    local rootfs="${BUILD_DIR}/rootfs"
    local img="${OUTPUT_DIR}/${IMAGE_NAME}"

    # QEMU entfernen
    rm -f "${rootfs}/usr/bin/qemu-aarch64-static"

    # AGGRESSIVES Cleanup
    chroot "$rootfs" bash -c "
        apt-get clean 2>/dev/null || true
        apt-get autoremove -y 2>/dev/null || true
        rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
        rm -rf /var/cache/apt/archives/*.deb
        rm -rf /usr/share/doc/* /usr/share/man/* /usr/share/info/*
        rm -rf /usr/share/locale/!(en|de|locale.alias)
        rm -rf /root/.npm /root/.cache
        rm -rf /var/log/*.log /var/log/**/*.log
        # Journal leeren
        journalctl --vacuum-size=1M 2>/dev/null || true
    " 2>/dev/null || true

    # Belegung anzeigen
    echo ""
    echo "→ Image-Belegung:"
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

    if [[ -n "$LOOP_DEV" ]]; then
        kpartx -d "$LOOP_DEV" 2>/dev/null || true
        losetup -d "$LOOP_DEV" 2>/dev/null || true
        LOOP_DEV=""
    fi

    # Image-Größe
    local raw_size=$(du -h "$img" | cut -f1)
    local apparent=$(du --apparent-size -h "$img" | cut -f1)

    # SHA256
    echo "→ SHA256..."
    sha256sum "$img" > "${img}.sha256"

    # xz-Kompression
    if [[ "$COMPRESS" == "yes" ]]; then
        echo "→ Komprimiere mit xz (kann 5-15 Min dauern)..."
        xz -T0 -9 --keep "$img" 2>/dev/null && {
            local xz_size=$(du -h "${img}.xz" | cut -f1)
            sha256sum "${img}.xz" > "${img}.xz.sha256"
            echo "→ Komprimiert: ${img}.xz (${xz_size})"
        } || echo "⚠ xz nicht verfügbar, Image unkomprimiert"
    fi

    local sha=$(cat "${img}.sha256" | cut -d' ' -f1 | head -c 16)

    echo ""
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║  ✅ GhostShell OS — Slim Image erstellt!                ║"
    echo "╠══════════════════════════════════════════════════════════╣"
    echo "║                                                          ║"
    echo "║  Image:    ${img}"
    echo "║  Roh:      ${raw_size} (apparent: ${apparent})"
    [[ -f "${img}.xz" ]] && \
    echo "║  xz:       $(du -h "${img}.xz" | cut -f1)"
    echo "║  SHA256:   ${sha}..."
    echo "║                                                          ║"
    echo "║  ── Flash auf SD-Karte ──                                ║"
    echo "║                                                          ║"
    echo "║  sudo dd if=${img} of=/dev/sdX bs=4M status=progress     ║"
    echo "║  oder:  sudo bash scripts/flash-arm-usb.sh               ║"
    echo "║                                                          ║"
    echo "║  ── Was passiert beim ersten Start? ──                   ║"
    echo "║                                                          ║"
    echo "║  1. Root-Partition expandiert auf volle SD-Größe         ║"
    echo "║  2. Setup-Wizard startet (Sprache, WiFi, Passwort)       ║"
    echo "║  3. Python venv wird erstellt                            ║"
    echo "║  4. PostgreSQL + Schemas werden initialisiert            ║"
    echo "║  5. Frontend wird gebaut                                 ║"
    echo "║  6. KI-Modelle können heruntergeladen werden             ║"
    echo "║  7. Dashboard unter http://<ip>:3000 erreichbar          ║"
    echo "║                                                          ║"
    echo "║  First-Boot Dauer: ~5-15 Min (je nach Internetanbindung) ║"
    echo "║                                                          ║"
    echo "╚══════════════════════════════════════════════════════════╝"

    # Optional: Direkt flashen
    if [[ -n "$WRITE_DEV" ]]; then
        echo ""
        echo "⚠ Flash auf ${WRITE_DEV} in 5 Sek... (Ctrl+C abbrechen)"
        sleep 5
        dd if="$img" of="$WRITE_DEV" bs=4M status=progress conv=fsync
        sync
        echo "✅ Auf ${WRITE_DEV} geflasht"
    fi
}

# ═══════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════
main() {
    local start_time=$(date +%s)

    check_deps
    create_slim_image
    create_rootfs
    install_packages
    install_firmware
    install_ghostshell_core
    install_firstboot_system
    install_services
    configure_network
    finalize_image

    local end_time=$(date +%s)
    local duration=$(( (end_time - start_time) / 60 ))
    echo ""
    echo "⏱ Build-Dauer: ${duration} Minuten"
    echo ""
    echo "Tipps:"
    echo "  ghostshell-models list       → Verfügbare KI-Modelle"
    echo "  ghostshell-models download tinyllama  → Kleinstes Modell (669MB)"
    echo "  ghostshell-setup            → Setup-Wizard nochmal starten"
}

main "$@"
