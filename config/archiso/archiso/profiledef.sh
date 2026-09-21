#!/usr/bin/env bash
# =============================================================================
# GhostShell OS — Archiso Profildefinition
# =============================================================================
# Verwendet von mkarchiso zum Erstellen eines bootfähigen Live-ISO.
# Das ISO enthält:
#   - Minimales Arch-System mit PostgreSQL, Python, Node.js
#   - GhostShell OS Installer (Python TUI)
#   - Vorkonfigurierte DBAI-Komponenten unter /opt/dbai
#   - UEFI + BIOS Boot-Support
# =============================================================================

iso_name="ghostshell-os"
iso_label="GHOSTSHELL_$(date +%Y%m)"
iso_publisher="DBAI Project <https://github.com/dbai-project>"
iso_application="GhostShell OS Installer"
iso_version="$(date +%Y.%m.%d)"
install_dir="arch"
buildmodes=('iso')
bootmodes=(
    'bios.syslinux.mbr'
    'bios.syslinux.eltorito'
    'uefi-ia32.grub.esp'
    'uefi-x64.grub.esp'
    'uefi-ia32.grub.eltorito'
    'uefi-x64.grub.eltorito'
)
arch="x86_64"
pacman_conf="pacman.conf"
airootfs_image_type="squashfs"
airootfs_image_tool_options=('-comp' 'zstd' '-Xcompression-level' '15' '-b' '1M')
file_permissions=(
    ["/usr/local/bin/ghostshell-install"]="0:0:755"
    ["/usr/local/bin/ghostshell-installer.py"]="0:0:755"
    ["/opt/dbai"]="0:0:755"
)
