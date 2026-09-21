#!/bin/bash
# =============================================================================
# GhostShell OS — Installer (TUI mit whiptail)
# =============================================================================
# Interaktiver Installer der beim ersten Boot von einem Live-Medium startet.
# Fragt nach Zieldatenträger, Partitionierung, dann kopiert das OS.
# =============================================================================
set -euo pipefail

export TERM=linux
TITLE="🧠 GhostShell OS — Installer"
LIVE_ROOT="/run/live/rootfs"  # SquashFS-Mountpoint des Live-Systems
DBAI_SRC="/opt/dbai"

# ─── Farben ───────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${CYAN}[Installer]${NC} $1"; }
ok()   { echo -e "${GREEN}[✅]${NC} $1"; }
warn() { echo -e "${YELLOW}[⚠]${NC} $1"; }
err()  { echo -e "${RED}[❌]${NC} $1"; }

# ─── Prüfen ob whiptail vorhanden ────────────────────────────────
if ! command -v whiptail &>/dev/null; then
    if command -v dialog &>/dev/null; then
        whiptail() { dialog "$@"; }
    else
        echo "FEHLER: whiptail oder dialog wird benötigt."
        exit 1
    fi
fi

# ─── Root-Check ──────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    whiptail --title "$TITLE" --msgbox "Der Installer muss als root gestartet werden.\n\nsudo ghostshell-install" 10 50
    exit 1
fi

# ═══════════════════════════════════════════════════════════════════
# Schritt 1: Willkommen
# ═══════════════════════════════════════════════════════════════════
whiptail --title "$TITLE" --yesno \
"Willkommen bei GhostShell OS!\n\n\
Dieses Programm installiert GhostShell OS auf deinem Rechner.\n\n\
Was wird passieren:\n\
  1. Festplatte auswählen\n\
  2. Partitionierung wählen\n\
  3. System kopieren\n\
  4. Bootloader installieren\n\
  5. Einrichtung abschließen\n\n\
Möchtest du fortfahren?" 18 60 || exit 0

# ═══════════════════════════════════════════════════════════════════
# Schritt 2: Zieldatenträger auswählen
# ═══════════════════════════════════════════════════════════════════
detect_disks() {
    local disks=()
    while IFS= read -r line; do
        local dev size model
        dev=$(echo "$line" | awk '{print $1}')
        size=$(echo "$line" | awk '{print $4}')
        model=$(echo "$line" | awk '{$1=$2=$3=$4=""; print $0}' | xargs)
        [[ -z "$model" ]] && model="Unbekannt"
        # Boot-Medium ausschließen (wo / gemountet ist)
        local boot_dev
        boot_dev=$(findmnt -n -o SOURCE / 2>/dev/null | sed 's/[0-9]*$//' | sed 's|/dev/||')
        [[ "/dev/$dev" == "/dev/$boot_dev" ]] && continue
        disks+=("$dev" "$size  $model")
    done < <(lsblk -d -n -o NAME,TYPE,TRAN,SIZE,MODEL 2>/dev/null | grep -E 'disk' | grep -v 'loop\|sr\|rom')
    echo "${disks[@]}"
}

DISK_LIST=$(detect_disks)
if [[ -z "$DISK_LIST" ]]; then
    whiptail --title "$TITLE" --msgbox "Keine geeignete Festplatte gefunden!\n\nSind Datenträger angeschlossen?" 10 50
    exit 1
fi

TARGET_DISK=$(whiptail --title "$TITLE — Festplatte wählen" \
    --menu "Auf welche Festplatte soll GhostShell OS installiert werden?\n\n⚠ ACHTUNG: Daten auf der gewählten Festplatte können gelöscht werden!" 18 70 6 \
    $DISK_LIST 3>&1 1>&2 2>&3) || exit 0

TARGET="/dev/$TARGET_DISK"
DISK_SIZE=$(lsblk -b -d -n -o SIZE "$TARGET" 2>/dev/null)
DISK_SIZE_GB=$((DISK_SIZE / 1073741824))

# ═══════════════════════════════════════════════════════════════════
# Schritt 3: Installationsmodus
# ═══════════════════════════════════════════════════════════════════
INSTALL_MODE=$(whiptail --title "$TITLE — Installation" \
    --menu "Wie soll installiert werden?\n\nZiel: $TARGET ($DISK_SIZE_GB GB)" 16 70 3 \
    "erase"    "Festplatte löschen und GhostShell OS installieren" \
    "alongside" "Neben bestehendem System installieren (Dual-Boot)" \
    "manual"    "Manuelle Partitionierung (Experten)" \
    3>&1 1>&2 2>&3) || exit 0

# Bestätigung bei Löschung
if [[ "$INSTALL_MODE" == "erase" ]]; then
    whiptail --title "⚠ WARNUNG" --yesno \
"ACHTUNG!\n\n\
Alle Daten auf $TARGET werden UNWIDERRUFLICH GELÖSCHT!\n\n\
Festplatte: $TARGET ($DISK_SIZE_GB GB)\n\
Modus: Festplatte komplett löschen\n\n\
Bist du sicher?" 14 60 || exit 0
fi

# ═══════════════════════════════════════════════════════════════════
# Schritt 4: Partitionierung
# ═══════════════════════════════════════════════════════════════════
BOOT_PART=""
ROOT_PART=""
BUILD_DIR="/tmp/ghostshell-install"
mkdir -p "$BUILD_DIR"

partition_erase() {
    log "Partitioniere $TARGET (komplett löschen)..."
    # Alte Partitionen entfernen
    wipefs -a "$TARGET" &>/dev/null || true
    
    # GPT erstellen
    parted -s "$TARGET" mklabel gpt
    parted -s "$TARGET" mkpart ESP fat32 1MiB 513MiB
    parted -s "$TARGET" set 1 esp on
    parted -s "$TARGET" mkpart primary ext4 513MiB 100%
    
    partprobe "$TARGET" 2>/dev/null; sleep 2
    
    # Partitionsnamen ermitteln
    if [[ -b "${TARGET}p1" ]]; then
        BOOT_PART="${TARGET}p1"; ROOT_PART="${TARGET}p2"
    elif [[ -b "${TARGET}1" ]]; then
        BOOT_PART="${TARGET}1"; ROOT_PART="${TARGET}2"
    else
        err "Partitionen nicht gefunden!"; exit 1
    fi
    
    # Formatieren
    mkfs.vfat -F 32 -n GHOSTBOOT "$BOOT_PART"
    mkfs.ext4 -L ghostshell-root -F "$ROOT_PART"
    ok "Partitionierung abgeschlossen"
}

partition_alongside() {
    log "Neben bestehendem System installieren..."
    # Letzte unpartitionierte Bereiche oder kleinste Partition schrumpfen
    # Vereinfacht: Neue Partition am Ende erstellen
    local last_end
    last_end=$(parted -s "$TARGET" unit MiB print free 2>/dev/null | grep "Free Space" | tail -1 | awk '{print $1}' | tr -d 'MiB')
    
    if [[ -z "$last_end" || "$last_end" -lt 8192 ]]; then
        whiptail --title "Fehler" --msgbox "Nicht genügend freier Speicherplatz auf $TARGET.\n\nMindestens 8 GB freier Platz werden benötigt.\n\nBitte wähle 'Festplatte löschen' oder erstelle manuell Platz." 12 60
        exit 1
    fi
    
    local part_count
    part_count=$(lsblk -n -o NAME "$TARGET" | wc -l)
    part_count=$((part_count - 1))
    
    parted -s "$TARGET" mkpart GHOSTBOOT fat32 "${last_end}MiB" "$((last_end + 512))MiB"
    parted -s "$TARGET" mkpart ghostshell ext4 "$((last_end + 512))MiB" "100%"
    
    partprobe "$TARGET" 2>/dev/null; sleep 2
    
    local new_boot new_root
    new_boot=$(lsblk -n -o NAME "$TARGET" | tail -2 | head -1 | xargs)
    new_root=$(lsblk -n -o NAME "$TARGET" | tail -1 | xargs)
    BOOT_PART="/dev/$new_boot"
    ROOT_PART="/dev/$new_root"
    
    mkfs.vfat -F 32 -n GHOSTBOOT "$BOOT_PART"
    mkfs.ext4 -L ghostshell-root -F "$ROOT_PART"
    ok "Dual-Boot-Partitionen erstellt"
}

case "$INSTALL_MODE" in
    erase)     partition_erase ;;
    alongside) partition_alongside ;;
    manual)
        whiptail --title "Manuelle Partitionierung" --msgbox \
"Starte jetzt cfdisk/fdisk zum manuellen Partitionieren.\n\n\
Erstelle mindestens:\n\
  1. Boot-Partition (FAT32, 512MB, ESP-Flag)\n\
  2. Root-Partition (ext4, min. 8GB)\n\n\
Nach dem Beenden wird die Installation fortgesetzt." 14 60
        cfdisk "$TARGET" 2>/dev/null || fdisk "$TARGET"
        
        # Partitionen abfragen
        BOOT_PART=$(whiptail --title "Boot-Partition" --inputbox "Boot-Partition (z.B. ${TARGET}p1):" 8 50 "${TARGET}p1" 3>&1 1>&2 2>&3) || exit 0
        ROOT_PART=$(whiptail --title "Root-Partition" --inputbox "Root-Partition (z.B. ${TARGET}p2):" 8 50 "${TARGET}p2" 3>&1 1>&2 2>&3) || exit 0
        
        mkfs.vfat -F 32 -n GHOSTBOOT "$BOOT_PART"
        mkfs.ext4 -L ghostshell-root -F "$ROOT_PART"
        ;;
esac

# ═══════════════════════════════════════════════════════════════════
# Schritt 5: System kopieren
# ═══════════════════════════════════════════════════════════════════
TARGET_MNT="$BUILD_DIR/target"
mkdir -p "$TARGET_MNT"
mount "$ROOT_PART" "$TARGET_MNT"
mkdir -p "$TARGET_MNT/boot/efi"
mount "$BOOT_PART" "$TARGET_MNT/boot/efi"

# Fortschrittsanzeige
(
    echo 10; echo "XXX"; echo "Kopiere System-Dateien..."; echo "XXX"
    rsync -aHAX --exclude='/proc/*' --exclude='/sys/*' --exclude='/dev/*' \
        --exclude='/tmp/*' --exclude='/run/*' --exclude='/mnt/*' \
        --exclude='/media/*' --exclude='/lost+found' \
        / "$TARGET_MNT/" 2>/dev/null
    
    echo 50; echo "XXX"; echo "Erstelle Verzeichnisstruktur..."; echo "XXX"
    mkdir -p "$TARGET_MNT"/{proc,sys,dev,tmp,run,mnt,media}
    
    echo 60; echo "XXX"; echo "Konfiguriere fstab..."; echo "XXX"
    ROOT_UUID=$(blkid -s UUID -o value "$ROOT_PART")
    BOOT_UUID=$(blkid -s UUID -o value "$BOOT_PART")
    cat > "$TARGET_MNT/etc/fstab" << FSTAB
# GhostShell OS — /etc/fstab
UUID=$ROOT_UUID  /          ext4  defaults,noatime  0  1
UUID=$BOOT_UUID  /boot/efi  vfat  defaults          0  2
tmpfs            /tmp       tmpfs defaults,nosuid    0  0
FSTAB
    
    echo 70; echo "XXX"; echo "Installiere Bootloader..."; echo "XXX"
    # Chroot-Mounts
    mount --bind /dev  "$TARGET_MNT/dev"
    mount --bind /dev/pts "$TARGET_MNT/dev/pts"
    mount -t proc proc "$TARGET_MNT/proc"
    mount -t sysfs sys "$TARGET_MNT/sys"
    
    # GRUB installieren (UEFI)
    if [[ -d /sys/firmware/efi ]]; then
        chroot "$TARGET_MNT" grub-install --target=arm64-efi --efi-directory=/boot/efi --bootloader-id=GhostShell --removable 2>/dev/null || \
        chroot "$TARGET_MNT" grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=GhostShell --removable 2>/dev/null || true
    else
        chroot "$TARGET_MNT" grub-install "$TARGET" 2>/dev/null || true
    fi
    
    echo 85; echo "XXX"; echo "Konfiguriere Bootloader..."; echo "XXX"
    # GRUB-Config
    cat > "$TARGET_MNT/etc/default/grub" << 'GRUBCFG'
GRUB_DEFAULT=0
GRUB_TIMEOUT=3
GRUB_DISTRIBUTOR="GhostShell OS"
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash loglevel=3"
GRUB_CMDLINE_LINUX=""
GRUB_GFXMODE=auto
GRUB_TERMINAL_OUTPUT=gfxterm
GRUBCFG
    chroot "$TARGET_MNT" update-grub 2>/dev/null || chroot "$TARGET_MNT" grub-mkconfig -o /boot/grub/grub.cfg 2>/dev/null || true
    
    echo 90; echo "XXX"; echo "Entferne Installer-Autostart..."; echo "XXX"
    # Installer-Service deaktivieren im Zielsystem
    chroot "$TARGET_MNT" systemctl disable ghostshell-installer.service 2>/dev/null || true
    rm -f "$TARGET_MNT/etc/systemd/system/ghostshell-installer.service"
    # First-Boot aktivieren
    rm -f "$TARGET_MNT/opt/dbai/.first-boot-done"
    chroot "$TARGET_MNT" systemctl enable dbai-firstboot.service 2>/dev/null || true
    
    echo 95; echo "XXX"; echo "Räume auf..."; echo "XXX"
    umount -lf "$TARGET_MNT/proc" 2>/dev/null || true
    umount -lf "$TARGET_MNT/sys" 2>/dev/null || true
    umount -lf "$TARGET_MNT/dev/pts" 2>/dev/null || true
    umount -lf "$TARGET_MNT/dev" 2>/dev/null || true
    
    echo 100; echo "XXX"; echo "Installation abgeschlossen!"; echo "XXX"
) | whiptail --title "$TITLE" --gauge "Starte Installation..." 8 60 0

sync

# Unmount
umount -lf "$TARGET_MNT/boot/efi" 2>/dev/null || true
umount -lf "$TARGET_MNT" 2>/dev/null || true

# ═══════════════════════════════════════════════════════════════════
# Schritt 6: Fertig — Neustart anbieten
# ═══════════════════════════════════════════════════════════════════
if whiptail --title "$TITLE — Installation abgeschlossen! ✅" --yesno \
"GhostShell OS wurde erfolgreich installiert!\n\n\
Ziel: $TARGET\n\
Boot: $BOOT_PART\n\
Root: $ROOT_PART\n\n\
Beim nächsten Start wird die Ersteinrichtung gestartet\n\
(Sprache, Benutzer, KI-Modell).\n\n\
Jetzt neustarten?" 16 60; then
    log "Starte neu..."
    reboot
else
    log "Installation abgeschlossen. Manuell neustarten mit: sudo reboot"
fi
