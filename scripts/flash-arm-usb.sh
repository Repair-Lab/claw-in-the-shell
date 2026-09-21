#!/bin/bash
# =============================================================================
# GhostShell OS — ARM64 Image auf USB-Stick/SD-Karte flashen
# =============================================================================
# Schreibt das ARM64-Image auf einen 32GB+ USB-Stick oder SD-Karte.
#
# Nutzung:
#   sudo bash scripts/flash-arm-usb.sh                # Automatisch erkennen
#   sudo bash scripts/flash-arm-usb.sh /dev/sdb       # Bestimmtes Device
#   sudo bash scripts/flash-arm-usb.sh --verify        # Mit Verifikation
# =============================================================================

set -euo pipefail

DBAI_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMG_DIR="${DBAI_ROOT}/dist"
IMG_FILE=""
TARGET_DEV=""
VERIFY=false

# ─── Argumente ────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
    case $1 in
        --verify|-v) VERIFY=true; shift ;;
        /dev/*)      TARGET_DEV="$1"; shift ;;
        *.img)       IMG_FILE="$1"; shift ;;
        -h|--help)
            echo "GhostShell OS — ARM64 USB/SD-Card Flash Tool"
            echo ""
            echo "  sudo bash $0 [/dev/sdX] [--verify]"
            echo ""
            echo "  /dev/sdX     Ziel-Device (USB-Stick/SD-Karte)"
            echo "  --verify     Nach dem Flashen SHA256 verifizieren"
            exit 0 ;;
        *) echo "Unbekannt: $1"; exit 1 ;;
    esac
done

# ─── Root-Check ───────────────────────────────────────────────────

if [[ $EUID -ne 0 ]]; then
    echo "❌ Root-Rechte erforderlich!"
    echo "   sudo bash $0 $*"
    exit 1
fi

# ─── Image finden ─────────────────────────────────────────────────

if [[ -z "$IMG_FILE" ]]; then
    IMG_FILE=$(ls -t "${IMG_DIR}"/ghostshell-*arm64*.img 2>/dev/null | head -1)
fi

if [[ -z "$IMG_FILE" || ! -f "$IMG_FILE" ]]; then
    echo "❌ Kein ARM64-Image gefunden!"
    echo "   Zuerst bauen: sudo bash scripts/build-arm-image.sh"
    exit 1
fi

IMG_SIZE=$(du -h "$IMG_FILE" | cut -f1)
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║     🧠 GhostShell OS — ARM64 Flash Tool              ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  Image:    $(basename "$IMG_FILE")"
echo "║  Größe:    ${IMG_SIZE}"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ─── USB/SD-Karte finden ─────────────────────────────────────────

if [[ -z "$TARGET_DEV" ]]; then
    echo "Verfügbare Wechselmedien:"
    echo ""

    # Removable + USB Devices auflisten
    DEVICES=()
    while IFS= read -r line; do
        dev=$(echo "$line" | awk '{print $1}')
        size=$(echo "$line" | awk '{print $2}')
        tran=$(echo "$line" | awk '{print $3}')
        model=$(echo "$line" | awk '{$1=$2=$3=""; print}' | xargs)

        # Nur Wechselmedien (USB, SD-Card) anzeigen
        if [[ "$tran" == "usb" ]] || [[ -f "/sys/block/$(basename $dev)/removable" && "$(cat /sys/block/$(basename $dev)/removable 2>/dev/null)" == "1" ]]; then
            idx=${#DEVICES[@]}
            DEVICES+=("/dev/$dev")
            echo "  [$idx] /dev/$dev  ${size}  ${model}  (${tran})"
        fi
    done < <(lsblk -d -n -o NAME,SIZE,TRAN,MODEL 2>/dev/null | grep -v "loop\|sr\|rom\|zram")

    if [[ ${#DEVICES[@]} -eq 0 ]]; then
        echo ""
        echo "⚠  Keine USB-Sticks/SD-Karten gefunden!"
        echo ""
        echo "Alle Datenträger:"
        lsblk -d -o NAME,SIZE,TRAN,MODEL,RM | grep -v "loop\|sr\|rom"
        echo ""
        echo "Manuell angeben: sudo bash $0 /dev/sdX"
        exit 1
    fi

    echo ""
    read -p "Device-Nummer wählen [0-$((${#DEVICES[@]}-1))]: " choice
    TARGET_DEV="${DEVICES[$choice]}"
fi

# ─── Sicherheitscheck ────────────────────────────────────────────

if [[ ! -b "$TARGET_DEV" ]]; then
    echo "❌ $TARGET_DEV ist kein Block-Device!"
    exit 1
fi

# Nicht das Boot-Device!
BOOT_DEV=$(findmnt -n -o SOURCE / 2>/dev/null | sed 's/[0-9]*$//')
if [[ "$TARGET_DEV" == "$BOOT_DEV" ]]; then
    echo "❌ $TARGET_DEV ist das Boot-Laufwerk! ABBRUCH!"
    exit 1
fi

DEV_SIZE=$(lsblk -b -d -n -o SIZE "$TARGET_DEV" 2>/dev/null)
DEV_SIZE_GB=$(( DEV_SIZE / 1073741824 ))
DEV_MODEL=$(lsblk -d -n -o MODEL "$TARGET_DEV" 2>/dev/null | xargs)

echo ""
echo "  ⚠  WARNUNG — DATENVERLUST!"
echo ""
echo "  Ziel:    $TARGET_DEV"
echo "  Größe:   ${DEV_SIZE_GB} GB"
echo "  Modell:  ${DEV_MODEL:-Unbekannt}"
echo "  Image:   $(basename $IMG_FILE) (${IMG_SIZE})"
echo ""
echo "  ALLE DATEN AUF $TARGET_DEV WERDEN GELÖSCHT!"
echo ""
read -p "  Wirklich fortfahren? (ja/NEIN): " confirm
if [[ "$confirm" != "ja" ]]; then
    echo "Abgebrochen."
    exit 0
fi

# ─── Unmount ──────────────────────────────────────────────────────

echo "→ Unmounte $TARGET_DEV..."
for part in $(lsblk -n -o NAME "$TARGET_DEV" | tail -n +2); do
    umount "/dev/$part" 2>/dev/null || true
done

# ─── Flash ────────────────────────────────────────────────────────

echo ""
echo "→ Schreibe Image auf $TARGET_DEV..."
echo "  Dies dauert ca. 5-15 Minuten je nach USB-Speed."
echo ""

dd if="$IMG_FILE" of="$TARGET_DEV" bs=4M status=progress conv=fsync

echo ""
echo "→ Sync..."
sync

# ─── Verify (optional) ───────────────────────────────────────────

if $VERIFY; then
    echo "→ Verifiziere..."
    IMG_BYTES=$(stat -c%s "$IMG_FILE")
    IMG_SHA=$(sha256sum "$IMG_FILE" | cut -d' ' -f1)
    DEV_SHA=$(dd if="$TARGET_DEV" bs=4M count=$((IMG_BYTES / 4194304 + 1)) 2>/dev/null | head -c "$IMG_BYTES" | sha256sum | cut -d' ' -f1)

    if [[ "$IMG_SHA" == "$DEV_SHA" ]]; then
        echo "  ✅ Verifikation erfolgreich!"
    else
        echo "  ❌ Verifikation fehlgeschlagen! Image möglicherweise korrupt."
        echo "  IMG: $IMG_SHA"
        echo "  DEV: $DEV_SHA"
        exit 1
    fi
fi

# ─── Fertig ───────────────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  ✅ GhostShell OS — ARM64 erfolgreich geflasht!      ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║                                                      ║"
echo "║  Device:    $TARGET_DEV"
echo "║  Image:     $(basename $IMG_FILE)"
echo "║                                                      ║"
echo "║  Nächste Schritte:                                   ║"
echo "║    1. USB-Stick/SD-Karte sicher entfernen            ║"
echo "║    2. In Raspberry Pi/ARM-Board einstecken           ║"
echo "║    3. Einschalten — GhostShell OS startet!           ║"
echo "║                                                      ║"
echo "║  Boot-Reihenfolge:                                   ║"
echo "║    BIOS/UEFI → U-Boot → Linux → PostgreSQL → Ghost  ║"
echo "║                                                      ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
