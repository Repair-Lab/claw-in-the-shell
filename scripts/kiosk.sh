#!/bin/bash
# =============================================================================
# DBAI — Kiosk-Mode Setup Script
# =============================================================================
# Konfiguriert das System für den Kiosk-Modus:
# - Minimaler X-Server (oder Wayland) ohne Desktop-Manager
# - Chromium im Vollbild → http://localhost:3000
# - Auto-Login ohne Passwort
# - Maus-Cursor ausblenden nach Inaktivität
# =============================================================================
# Nutzung:
#   sudo bash scripts/kiosk.sh setup    # Einmalig einrichten
#   sudo bash scripts/kiosk.sh start    # Manueller Start
#   sudo bash scripts/kiosk.sh disable  # Kiosk deaktivieren
# =============================================================================

set -e

DBAI_USER="${DBAI_USER:-worker}"
DBAI_URL="${DBAI_URL:-http://localhost:3000}"
LOG_DIR="/var/log/dbai"

case "${1:-setup}" in

# ─── Setup ────────────────────────────────────────────────────────
setup)
    echo "╔══════════════════════════════════════╗"
    echo "║  DBAI — Kiosk-Mode Setup             ║"
    echo "╚══════════════════════════════════════╝"

    # Pakete installieren
    echo "→ Installiere Kiosk-Pakete..."
    if command -v apt-get &>/dev/null; then
        apt-get install -y --no-install-recommends \
            xserver-xorg xinit x11-xserver-utils \
            chromium unclutter \
            openbox 2>/dev/null || true
    elif command -v pacman &>/dev/null; then
        pacman -S --noconfirm --needed \
            xorg-server xorg-xinit xorg-xset \
            chromium unclutter \
            openbox 2>/dev/null || true
    fi

    # Auto-Login via Getty (kein Display-Manager nötig)
    echo "→ Konfiguriere Auto-Login..."
    mkdir -p /etc/systemd/system/getty@tty1.service.d
    cat > /etc/systemd/system/getty@tty1.service.d/autologin.conf << EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin ${DBAI_USER} --noclear %I \$TERM
EOF

    # .xinitrc für den User
    echo "→ Erstelle .xinitrc..."
    cat > /home/${DBAI_USER}/.xinitrc << 'XINITRC'
#!/bin/bash
# DBAI Kiosk — X11 Startup

# Bildschirmschoner und DPMS deaktivieren
xset s off
xset s noblank
xset -dpms

# Maus-Cursor nach 3 Sekunden ausblenden
unclutter -idle 3 -root &

# Minimaler Window Manager (nur für Fullscreen-Support)
openbox --config-file /dev/null &
sleep 0.5

# Alle Browser-Crashmeldungen verhindern
sed -i 's/"exited_cleanly":false/"exited_cleanly":true/' \
    /home/${USER}/.dbai-browser/Default/Preferences 2>/dev/null || true

# Warte auf DBAI Web-Server
echo "Warte auf DBAI..."
for i in $(seq 1 60); do
    curl -sf http://localhost:3000/ > /dev/null 2>&1 && break
    sleep 1
done

# Chromium im Kiosk-Modus starten
exec chromium \
    --kiosk \
    --app=http://localhost:3000 \
    --no-first-run \
    --disable-translate \
    --disable-infobars \
    --disable-suggestions-service \
    --disable-save-password-bubble \
    --disable-session-crashed-bubble \
    --disable-component-update \
    --noerrdialogs \
    --no-default-browser-check \
    --autoplay-policy=no-user-gesture-required \
    --enable-features=OverlayScrollbar \
    --disable-gpu-sandbox \
    --enable-gpu-rasterization \
    --enable-zero-copy \
    --ignore-gpu-blocklist \
    --user-data-dir=/home/${USER}/.dbai-browser
XINITRC
    chmod +x /home/${DBAI_USER}/.xinitrc
    chown ${DBAI_USER}:${DBAI_USER} /home/${DBAI_USER}/.xinitrc

    # Auto-startx in .bash_profile
    echo "→ Konfiguriere Auto-Start..."
    if ! grep -q "startx" /home/${DBAI_USER}/.bash_profile 2>/dev/null; then
        cat >> /home/${DBAI_USER}/.bash_profile << 'PROFILE'

# DBAI Kiosk Auto-Start
if [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then
    exec startx -- -nocursor 2>/var/log/dbai/xorg.log
fi
PROFILE
    fi

    # Log-Verzeichnis
    mkdir -p ${LOG_DIR}
    chown ${DBAI_USER}:${DBAI_USER} ${LOG_DIR}

    # Swap-Nutzung reduzieren (für Performance)
    echo "vm.swappiness=10" > /etc/sysctl.d/99-dbai.conf
    sysctl -p /etc/sysctl.d/99-dbai.conf 2>/dev/null || true

    echo ""
    echo "✅ Kiosk-Mode eingerichtet!"
    echo "   Beim nächsten Boot startet DBAI automatisch im Vollbild."
    echo "   Zum Deaktivieren: sudo bash scripts/kiosk.sh disable"
    echo ""
    echo "   Escape-Tastenkombination: Ctrl+Alt+F2 → Linux-Terminal"
    ;;

# ─── Start (manuell) ─────────────────────────────────────────────
start)
    echo "→ Starte DBAI im Kiosk-Modus..."
    sudo -u ${DBAI_USER} startx -- -nocursor 2>${LOG_DIR}/xorg.log
    ;;

# ─── Disable ─────────────────────────────────────────────────────
disable)
    echo "→ Deaktiviere Kiosk-Modus..."
    rm -f /etc/systemd/system/getty@tty1.service.d/autologin.conf
    sed -i '/DBAI Kiosk Auto-Start/,/^fi$/d' /home/${DBAI_USER}/.bash_profile 2>/dev/null || true
    systemctl daemon-reload
    echo "✅ Kiosk-Modus deaktiviert. Normaler Login beim nächsten Boot."
    ;;

*)
    echo "Nutzung: $0 {setup|start|disable}"
    exit 1
    ;;
esac
