#!/bin/bash
# =============================================================================
# DBAI — ISO/Image Builder
# =============================================================================
# Erstellt ein bootfähiges Linux-Abbild mit:
#   - Minimaler Linux-Base (Arch oder Debian)
#   - PostgreSQL + DBAI Schema & Daten
#   - Python Backend + Frontend Build
#   - NVIDIA Treiber (optional)
#   - Kiosk-Auto-Boot
# =============================================================================
# Nutzung:
#   sudo bash scripts/build-iso.sh              # Standard-Build (Debian)
#   sudo bash scripts/build-iso.sh --arch        # Arch-basiert
#   sudo bash scripts/build-iso.sh --minimal     # Ohne NVIDIA / nur CPU
#   sudo bash scripts/build-iso.sh --output /tmp # Ausgabe-Verzeichnis
# =============================================================================

set -euo pipefail

# ─── Konfiguration ────────────────────────────────────────────────
DBAI_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="/tmp/dbai-iso-build"
OUTPUT_DIR="${DBAI_ROOT}/dist"
ISO_NAME="dbai-$(date +%Y%m%d).iso"
BASE="debian"
INCLUDE_NVIDIA=true
ARCH="x86_64"

# ─── Argumente parsen ─────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case $1 in
        --arch)       BASE="arch";       shift ;;
        --debian)     BASE="debian";     shift ;;
        --minimal)    INCLUDE_NVIDIA=false; shift ;;
        --output)     OUTPUT_DIR="$2";   shift 2 ;;
        --name)       ISO_NAME="$2";     shift 2 ;;
        *)            echo "Unbekannte Option: $1"; exit 1 ;;
    esac
done

echo "╔══════════════════════════════════════════════╗"
echo "║     DBAI — ISO Builder                       ║"
echo "╠══════════════════════════════════════════════╣"
echo "║  Base:     ${BASE}                           ║"
echo "║  NVIDIA:   ${INCLUDE_NVIDIA}                 ║"
echo "║  Output:   ${OUTPUT_DIR}/${ISO_NAME}         ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ─── Abhängigkeiten prüfen ────────────────────────────────────────
check_deps() {
    local missing=()
    for cmd in debootstrap mksquashfs xorriso grub-mkrescue genisoimage; do
        command -v "$cmd" &>/dev/null || missing+=("$cmd")
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "⚠ Fehlende Tools: ${missing[*]}"
        echo "→ Installiere..."
        apt-get install -y debootstrap squashfs-tools xorriso grub-pc-bin \
            grub-efi-amd64-bin mtools genisoimage 2>/dev/null || {
            echo "❌ Konnte Build-Tools nicht installieren."
            echo "   Bitte manuell: apt install ${missing[*]}"
            exit 1
        }
    fi
}

# ─── Aufräumen ────────────────────────────────────────────────────
cleanup() {
    echo "→ Räume auf..."
    umount -lf "${BUILD_DIR}/rootfs/proc" 2>/dev/null || true
    umount -lf "${BUILD_DIR}/rootfs/sys"  2>/dev/null || true
    umount -lf "${BUILD_DIR}/rootfs/dev/pts" 2>/dev/null || true
    umount -lf "${BUILD_DIR}/rootfs/dev"  2>/dev/null || true
    rm -rf "${BUILD_DIR}"
}
trap cleanup EXIT

# ─── Root-FS erstellen (Debian) ───────────────────────────────────
build_debian_rootfs() {
    echo "═══ Phase 1/6: Debian Root-FS erstellen ═══"
    mkdir -p "${BUILD_DIR}/rootfs"

    debootstrap --arch=amd64 --variant=minbase \
        --include=systemd,systemd-sysv,dbus,locales,sudo,curl,wget,ca-certificates \
        bookworm "${BUILD_DIR}/rootfs" http://deb.debian.org/debian

    # Chroot vorbereiten
    mount --bind /dev  "${BUILD_DIR}/rootfs/dev"
    mount --bind /dev/pts "${BUILD_DIR}/rootfs/dev/pts"
    mount -t proc proc "${BUILD_DIR}/rootfs/proc"
    mount -t sysfs sys "${BUILD_DIR}/rootfs/sys"

    # DBAI Pakete in Chroot installieren
    chroot "${BUILD_DIR}/rootfs" bash -c "
        export DEBIAN_FRONTEND=noninteractive

        # Basis-Pakete
        apt-get update
        apt-get install -y --no-install-recommends \
            postgresql postgresql-contrib \
            python3 python3-pip python3-venv \
            chromium xserver-xorg xinit x11-xserver-utils openbox unclutter \
            linux-image-amd64 grub-pc grub-efi-amd64-bin \
            git pciutils usbutils lm-sensors \
            net-tools iproute2 wireless-tools wpasupplicant \
            firmware-linux-free

        # NVIDIA (optional)
        $(if $INCLUDE_NVIDIA; then echo '
        apt-get install -y --no-install-recommends \
            nvidia-driver nvidia-smi nvidia-cuda-toolkit 2>/dev/null || true
        '; fi)

        # Cleanup
        apt-get clean
        rm -rf /var/lib/apt/lists/*
    "
}

# ─── Root-FS erstellen (Arch) ────────────────────────────────────
build_arch_rootfs() {
    echo "═══ Phase 1/6: Arch Root-FS erstellen ═══"
    mkdir -p "${BUILD_DIR}/rootfs"

    if ! command -v pacstrap &>/dev/null; then
        echo "❌ pacstrap nicht gefunden. Arch-Build benötigt arch-install-scripts."
        exit 1
    fi

    pacstrap "${BUILD_DIR}/rootfs" base linux linux-firmware \
        postgresql python python-pip \
        chromium xorg-server xorg-xinit xorg-xset openbox unclutter \
        grub efibootmgr \
        git pciutils usbutils lm_sensors \
        networkmanager

    if $INCLUDE_NVIDIA; then
        pacstrap "${BUILD_DIR}/rootfs" nvidia nvidia-utils cuda 2>/dev/null || true
    fi

    mount --bind /dev  "${BUILD_DIR}/rootfs/dev"
    mount --bind /dev/pts "${BUILD_DIR}/rootfs/dev/pts"
    mount -t proc proc "${BUILD_DIR}/rootfs/proc"
    mount -t sysfs sys "${BUILD_DIR}/rootfs/sys"
}

# ─── DBAI installieren ───────────────────────────────────────────
install_dbai() {
    echo "═══ Phase 2/6: DBAI kopieren ═══"
    local target="${BUILD_DIR}/rootfs/opt/dbai"
    mkdir -p "$target"

    # Projektdateien kopieren (ohne node_modules, __pycache__, .git)
    rsync -a --exclude='node_modules' \
             --exclude='__pycache__' \
             --exclude='.git' \
             --exclude='dist' \
             --exclude='*.pyc' \
             "${DBAI_ROOT}/" "$target/"

    # Frontend bauen
    echo "→ Frontend Build..."
    chroot "${BUILD_DIR}/rootfs" bash -c "
        cd /opt/dbai/frontend
        if command -v npm &>/dev/null; then
            npm ci --production 2>/dev/null || npm install
            npx vite build
        fi
    " || echo "⚠ Frontend-Build wird beim ersten Start erledigt."

    # Python Dependencies
    echo "→ Python Dependencies..."
    chroot "${BUILD_DIR}/rootfs" bash -c "
        python3 -m venv /opt/dbai/.venv
        /opt/dbai/.venv/bin/pip install --no-cache-dir \
            fastapi uvicorn asyncpg psutil pynvml aiohttp aiofiles httpx toml 2>/dev/null || true
    "
}

# ─── Systemd Services installieren ───────────────────────────────
install_services() {
    echo "═══ Phase 3/6: Systemd konfigurieren ═══"
    local rootfs="${BUILD_DIR}/rootfs"

    # DBAI Services kopieren
    cp "${DBAI_ROOT}/config/systemd/"*.service "${rootfs}/etc/systemd/system/" 2>/dev/null || true
    cp "${DBAI_ROOT}/config/systemd/"*.target  "${rootfs}/etc/systemd/system/" 2>/dev/null || true

    # Services aktivieren
    chroot "$rootfs" bash -c "
        systemctl enable postgresql
        systemctl enable dbai.target 2>/dev/null || true
        systemctl enable dbai-web.service 2>/dev/null || true
        systemctl enable dbai-ghost.service 2>/dev/null || true
        systemctl enable dbai-kiosk.service 2>/dev/null || true
    "

    # GRUB konfigurieren
    cp "${DBAI_ROOT}/config/grub/grub-dbai" "${rootfs}/etc/default/grub"

    # Kiosk Auto-Login
    mkdir -p "${rootfs}/etc/systemd/system/getty@tty1.service.d"
    cat > "${rootfs}/etc/systemd/system/getty@tty1.service.d/autologin.conf" << 'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin dbai --noclear %I $TERM
EOF

    # DBAI User erstellen
    chroot "$rootfs" bash -c "
        useradd -m -s /bin/bash -G audio,video,input,render dbai 2>/dev/null || true
        echo 'dbai:dbai2026' | chpasswd
        echo 'dbai ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/dbai
    "

    # .xinitrc für Kiosk
    cp "${DBAI_ROOT}/scripts/kiosk.sh" "${rootfs}/opt/dbai/scripts/"
    chroot "$rootfs" bash -c "bash /opt/dbai/scripts/kiosk.sh setup" 2>/dev/null || true
}

# ─── Datenbank vorbereiten ────────────────────────────────────────
prepare_database() {
    echo "═══ Phase 4/6: Datenbank vorbereiten ═══"
    local rootfs="${BUILD_DIR}/rootfs"

    # Bootstrap-Script kopieren (wird beim ersten Boot ausgeführt)
    cat > "${rootfs}/opt/dbai/scripts/first-boot.sh" << 'FIRSTBOOT'
#!/bin/bash
# DBAI First-Boot: DB initialisieren
set -e

if [ -f /opt/dbai/.first-boot-done ]; then
    exit 0
fi

echo "DBAI: Erste Initialisierung..."

# PostgreSQL starten
systemctl start postgresql
sleep 2

# DB erstellen
sudo -u postgres psql -c "CREATE ROLE dbai_system WITH LOGIN SUPERUSER PASSWORD 'dbai2026';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE dbai OWNER dbai_system;" 2>/dev/null || true

# Schema laden
for sql in /opt/dbai/schema/*.sql; do
    echo "  → $(basename $sql)"
    sudo -u postgres psql -d dbai -f "$sql" 2>/dev/null || true
done

# PostgreSQL-Config
cp /opt/dbai/config/postgresql.conf /etc/postgresql/*/main/ 2>/dev/null || true
cp /opt/dbai/config/pg_hba.conf /etc/postgresql/*/main/ 2>/dev/null || true
systemctl restart postgresql

touch /opt/dbai/.first-boot-done
echo "DBAI: Initialisierung abgeschlossen!"
FIRSTBOOT
    chmod +x "${rootfs}/opt/dbai/scripts/first-boot.sh"

    # First-Boot Service
    cat > "${rootfs}/etc/systemd/system/dbai-firstboot.service" << 'EOF'
[Unit]
Description=DBAI First Boot Setup
After=postgresql.service
Before=dbai-web.service
ConditionPathExists=!/opt/dbai/.first-boot-done

[Service]
Type=oneshot
ExecStart=/opt/dbai/scripts/first-boot.sh
RemainAfterExit=yes
StandardOutput=journal+console

[Install]
WantedBy=dbai.target
EOF
    chroot "$rootfs" systemctl enable dbai-firstboot.service 2>/dev/null || true
}

# ─── ISO erstellen ────────────────────────────────────────────────
build_iso() {
    echo "═══ Phase 5/6: ISO erstellen ═══"

    # Chroot-Mounts entfernen
    umount -lf "${BUILD_DIR}/rootfs/proc" 2>/dev/null || true
    umount -lf "${BUILD_DIR}/rootfs/sys"  2>/dev/null || true
    umount -lf "${BUILD_DIR}/rootfs/dev/pts" 2>/dev/null || true
    umount -lf "${BUILD_DIR}/rootfs/dev"  2>/dev/null || true

    # SquashFS erstellen
    echo "→ SquashFS komprimieren..."
    mkdir -p "${BUILD_DIR}/iso/live"
    mksquashfs "${BUILD_DIR}/rootfs" "${BUILD_DIR}/iso/live/filesystem.squashfs" \
        -comp xz -b 1M -Xdict-size 100% \
        -e boot/vmlinuz* -e boot/initrd*

    # Kernel & Initrd kopieren
    cp "${BUILD_DIR}/rootfs/boot/vmlinuz-"* "${BUILD_DIR}/iso/live/vmlinuz" 2>/dev/null || true
    cp "${BUILD_DIR}/rootfs/boot/initrd.img-"* "${BUILD_DIR}/iso/live/initrd" 2>/dev/null || true

    # GRUB für ISO
    mkdir -p "${BUILD_DIR}/iso/boot/grub"
    cat > "${BUILD_DIR}/iso/boot/grub/grub.cfg" << 'GRUBCFG'
set timeout=0
set default=0

menuentry "DBAI — Ghost in the Database" {
    linux /live/vmlinuz boot=live quiet splash loglevel=0
    initrd /live/initrd
}
GRUBCFG

    # ISO generieren
    echo "→ ISO generieren..."
    mkdir -p "$OUTPUT_DIR"
    grub-mkrescue -o "${OUTPUT_DIR}/${ISO_NAME}" "${BUILD_DIR}/iso" \
        --compress=xz 2>/dev/null || \
    xorriso -as mkisofs \
        -iso-level 3 \
        -full-iso9660-filenames \
        -volid "DBAI" \
        -eltorito-boot boot/grub/bios.img \
        -eltorito-catalog boot/grub/boot.cat \
        -no-emul-boot -boot-load-size 4 -boot-info-table \
        -output "${OUTPUT_DIR}/${ISO_NAME}" \
        "${BUILD_DIR}/iso"
}

# ─── Checksumme ───────────────────────────────────────────────────
finalize() {
    echo "═══ Phase 6/6: Finalisierung ═══"
    local iso_path="${OUTPUT_DIR}/${ISO_NAME}"

    if [[ -f "$iso_path" ]]; then
        local size=$(du -h "$iso_path" | cut -f1)
        sha256sum "$iso_path" > "${iso_path}.sha256"

        echo ""
        echo "╔══════════════════════════════════════════════╗"
        echo "║  ✅ DBAI ISO erfolgreich erstellt!           ║"
        echo "╠══════════════════════════════════════════════╣"
        echo "║  Datei:    ${iso_path}"
        echo "║  Größe:    ${size}"
        echo "║  SHA256:   $(cat ${iso_path}.sha256 | cut -d' ' -f1 | head -c 16)..."
        echo "╠══════════════════════════════════════════════╣"
        echo "║  USB schreiben:                              ║"
        echo "║    sudo dd if=${iso_path} of=/dev/sdX bs=4M  ║"
        echo "║                                              ║"
        echo "║  VM testen:                                  ║"
        echo "║    qemu-system-x86_64 -m 4G -enable-kvm \\   ║"
        echo "║      -cdrom ${iso_path}                      ║"
        echo "╚══════════════════════════════════════════════╝"
    else
        echo "❌ ISO-Erstellung fehlgeschlagen!"
        exit 1
    fi
}

# ─── Main ─────────────────────────────────────────────────────────
main() {
    if [[ $EUID -ne 0 ]]; then
        echo "❌ Root-Rechte erforderlich: sudo bash $0"
        exit 1
    fi

    check_deps

    case "$BASE" in
        debian) build_debian_rootfs ;;
        arch)   build_arch_rootfs ;;
    esac

    install_dbai
    install_services
    prepare_database
    build_iso
    finalize
}

main
