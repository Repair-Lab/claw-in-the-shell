#!/bin/bash
# =============================================================================
# GhostShell OS — QEMU Test Script
# =============================================================================
# Testet das GhostShell OS ISO in einer QEMU-VM.
# Erstellt eine virtuelle Festplatte und bootet vom ISO.
#
# Nutzung:
#   bash scripts/test-iso-qemu.sh                        # Automatisch ISO finden
#   bash scripts/test-iso-qemu.sh dist/ghostshell.iso    # Bestimmtes ISO
#   bash scripts/test-iso-qemu.sh --uefi                 # UEFI-Modus
#   bash scripts/test-iso-qemu.sh --vnc                  # VNC statt SDL
#   bash scripts/test-iso-qemu.sh --headless             # Kein Display
#   bash scripts/test-iso-qemu.sh --install              # Auto-Install testen
# =============================================================================

set -euo pipefail

DBAI_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="${DBAI_ROOT}/dist"
VM_DIR="${DBAI_ROOT}/dist/vm"
DISK_SIZE="32G"
RAM="4096"
CPUS="4"
DISPLAY_MODE="sdl"      # sdl | vnc | none
UEFI=false
ISO_PATH=""
DISK_IMAGE=""
INSTALL_MODE=false
VNC_PORT=5900

# ─── Argumente ────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
    case $1 in
        --uefi)       UEFI=true;             shift ;;
        --vnc)        DISPLAY_MODE="vnc";     shift ;;
        --sdl)        DISPLAY_MODE="sdl";     shift ;;
        --headless)   DISPLAY_MODE="none";    shift ;;
        --install)    INSTALL_MODE=true;      shift ;;
        --ram)        RAM="$2";               shift 2 ;;
        --cpus)       CPUS="$2";              shift 2 ;;
        --disk-size)  DISK_SIZE="$2";         shift 2 ;;
        -h|--help)
            echo "GhostShell OS — QEMU Test"
            echo ""
            echo "  test-iso-qemu.sh [ISO_PATH] [OPTIONS]"
            echo ""
            echo "  --uefi       UEFI-Boot (mit OVMF)"
            echo "  --vnc        VNC-Display (Port 5900)"
            echo "  --sdl        SDL-Display (Standard)"
            echo "  --headless   Kein Display"
            echo "  --install    Automatische Installation testen"
            echo "  --ram N      RAM in MB (Standard: 4096)"
            echo "  --cpus N     CPU-Kerne (Standard: 4)"
            echo "  --disk-size  Disk-Größe (Standard: 32G)"
            exit 0 ;;
        *)
            if [[ -f "$1" ]]; then
                ISO_PATH="$1"
            else
                echo "❌ Datei nicht gefunden: $1"
                exit 1
            fi
            shift ;;
    esac
done

# ─── ISO finden ───────────────────────────────────────────────────

if [[ -z "$ISO_PATH" ]]; then
    ISO_PATH=$(ls -t "${DIST_DIR}"/ghostshell-os-*.iso 2>/dev/null | head -1)
    if [[ -z "$ISO_PATH" ]]; then
        ISO_PATH=$(ls -t "${DIST_DIR}"/*.iso 2>/dev/null | head -1)
    fi
fi

if [[ -z "$ISO_PATH" || ! -f "$ISO_PATH" ]]; then
    echo "❌ Kein ISO gefunden!"
    echo "   Zuerst bauen: sudo bash scripts/build-iso.sh"
    echo "   Oder: bash $0 /pfad/zum/iso"
    exit 1
fi

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║     🧠 GhostShell OS — QEMU Testumgebung            ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  ISO:      $(basename "$ISO_PATH")"
echo "║  RAM:      ${RAM} MB"
echo "║  CPUs:     ${CPUS}"
echo "║  Disk:     ${DISK_SIZE}"
echo "║  Display:  ${DISPLAY_MODE}"
echo "║  UEFI:     ${UEFI}"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ─── QEMU prüfen ─────────────────────────────────────────────────

if ! command -v qemu-system-x86_64 &>/dev/null; then
    echo "⚠  QEMU nicht installiert."
    echo "→  Installiere..."
    if command -v apt-get &>/dev/null; then
        sudo apt-get install -y qemu-system-x86 qemu-utils ovmf
    elif command -v pacman &>/dev/null; then
        sudo pacman -S --noconfirm qemu-full edk2-ovmf
    else
        echo "❌ Bitte QEMU manuell installieren."
        exit 1
    fi
fi

# ─── VM-Verzeichnis + Disk erstellen ─────────────────────────────

mkdir -p "$VM_DIR"
DISK_IMAGE="${VM_DIR}/ghostshell-test.qcow2"

if [[ ! -f "$DISK_IMAGE" ]]; then
    echo "→ Erstelle virtuelle Festplatte (${DISK_SIZE})..."
    qemu-img create -f qcow2 "$DISK_IMAGE" "$DISK_SIZE"
elif $INSTALL_MODE; then
    echo "→ Lösche alte VM-Disk für Neuinstallation..."
    rm -f "$DISK_IMAGE"
    qemu-img create -f qcow2 "$DISK_IMAGE" "$DISK_SIZE"
fi

# ─── QEMU-Befehl zusammenbauen ───────────────────────────────────

QEMU_CMD=(
    qemu-system-x86_64
    -name "GhostShell OS Test"
    -machine q35,accel=kvm:tcg
    -cpu host,+aes,+avx,+avx2 2>/dev/null || -cpu max
    -smp "$CPUS"
    -m "$RAM"

    # Festplatte
    -drive file="$DISK_IMAGE",format=qcow2,if=virtio,cache=writeback
    # ISO als CD-ROM
    -cdrom "$ISO_PATH"
    # Boot-Reihenfolge: CD zuerst
    -boot order=d,menu=on

    # Netzwerk (User-Mode, Port-Forwarding)
    -netdev user,id=net0,hostfwd=tcp::3080-:3000,hostfwd=tcp::2222-:22
    -device virtio-net-pci,netdev=net0

    # Audio
    -audiodev pa,id=snd0 2>/dev/null || true
    -device intel-hda -device hda-duplex,audiodev=snd0 2>/dev/null || true

    # USB
    -usb -device usb-tablet

    # RNG (Random Number Generator)
    -object rng-random,filename=/dev/urandom,id=rng0
    -device virtio-rng-pci,rng=rng0

    # Monitor
    -monitor stdio
)

# UEFI
if $UEFI; then
    OVMF_CODE=""
    OVMF_VARS=""
    for path in \
        /usr/share/OVMF/OVMF_CODE.fd \
        /usr/share/edk2/ovmf/OVMF_CODE.fd \
        /usr/share/edk2-ovmf/x64/OVMF_CODE.fd \
        /usr/share/qemu/OVMF_CODE.fd; do
        if [[ -f "$path" ]]; then
            OVMF_CODE="$path"
            OVMF_VARS="${path/CODE/VARS}"
            break
        fi
    done

    if [[ -n "$OVMF_CODE" ]]; then
        # Kopiere VARS für beschreibbare Kopie
        VARS_COPY="${VM_DIR}/OVMF_VARS.fd"
        if [[ ! -f "$VARS_COPY" ]]; then
            cp "$OVMF_VARS" "$VARS_COPY" 2>/dev/null || \
            cp "${OVMF_CODE/CODE/VARS}" "$VARS_COPY" 2>/dev/null || true
        fi

        QEMU_CMD+=(
            -drive if=pflash,format=raw,readonly=on,file="$OVMF_CODE"
        )
        if [[ -f "$VARS_COPY" ]]; then
            QEMU_CMD+=(
                -drive if=pflash,format=raw,file="$VARS_COPY"
            )
        fi
        echo "→ UEFI-Modus mit $(basename $OVMF_CODE)"
    else
        echo "⚠  OVMF nicht gefunden — falle auf BIOS zurück."
    fi
fi

# Display
case "$DISPLAY_MODE" in
    sdl)
        QEMU_CMD+=(-display sdl,gl=on 2>/dev/null || -display sdl)
        ;;
    vnc)
        QEMU_CMD+=(-display vnc=:0)
        echo "→ VNC verfügbar auf: localhost:${VNC_PORT}"
        ;;
    none)
        QEMU_CMD+=(-nographic)
        ;;
esac

# ─── QEMU starten ────────────────────────────────────────────────

echo ""
echo "→ Starte QEMU..."
echo "  Porte:"
echo "    Web:  http://localhost:3080  (→ :3000 in VM)"
echo "    SSH:  ssh -p 2222 ghost@localhost"
echo ""
echo "  QEMU-Monitor: Ctrl+A → H für Hilfe"
echo "  Beenden: Ctrl+A → X oder 'quit' im Monitor"
echo ""

# Vereinfachter Befehl (ohne optionale Fehler)
qemu-system-x86_64 \
    -name "GhostShell OS Test" \
    -machine q35 \
    -cpu max \
    -smp "$CPUS" \
    -m "$RAM" \
    -drive file="$DISK_IMAGE",format=qcow2,if=virtio,cache=writeback \
    -cdrom "$ISO_PATH" \
    -boot order=d,menu=on \
    -netdev user,id=net0,hostfwd=tcp::3080-:3000,hostfwd=tcp::2222-:22 \
    -device virtio-net-pci,netdev=net0 \
    -usb -device usb-tablet \
    -object rng-random,filename=/dev/urandom,id=rng0 \
    -device virtio-rng-pci,rng=rng0 \
    -monitor stdio \
    $(if $UEFI && [[ -n "${OVMF_CODE:-}" ]]; then \
        echo "-drive if=pflash,format=raw,readonly=on,file=$OVMF_CODE"; \
    fi) \
    $( case "$DISPLAY_MODE" in
        sdl)  echo "-display gtk" ;;
        vnc)  echo "-display vnc=:0" ;;
        none) echo "-nographic" ;;
    esac )

echo ""
echo "✅ QEMU beendet."
