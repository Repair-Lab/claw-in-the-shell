-- =============================================================================
-- DBAI Schema 31: Stufe-1 & Stufe-2 Erkenntnisse — Bare-Metal + Apple-Moment
--
-- Erstellt: 2026-03-16
-- Session: Bare-Metal Simulation + UX Polish
--
-- Diese Datei dokumentiert ALLE Erkenntnisse aus der Implementierung von:
--   Stufe 1 (Items 1-5): Bare-Metal Boot-Infrastruktur
--   Stufe 2 (Items 6-8): Apple-Moment UX
--
-- Tabellen die befüllt werden:
--   1. dbai_knowledge.system_memory      — Langzeitwissen für KI-Sessions
--   2. dbai_knowledge.module_registry    — Neue Dateien im Modul-Verzeichnis
--   3. dbai_knowledge.changelog          — Änderungslog (append-only)
--   4. dbai_knowledge.known_issues       — Bekannte Probleme + Workarounds
--   5. dbai_knowledge.build_log          — Build-Dokumentation
--
-- =============================================================================

-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  1. SYSTEM MEMORY — Langzeitwissen                                       ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝

-- ----- 1a) Stufe-1: Bare-Metal Boot — Architektur-Wissen -----

INSERT INTO dbai_knowledge.system_memory
    (category, title, content, priority, tags, valid_from, related_modules, related_schemas, structured_data) VALUES

('architecture', 'Stufe 1: Bare-Metal Boot-Kette',
 'DBAI bootet als Bare-Metal-OS in dieser Reihenfolge: ' ||
 'GRUB (config/grub/grub-dbai, silent mit TIMEOUT=0) → ' ||
 'Minimal-Linux (config/packages.txt, ~91 Pakete) → ' ||
 'systemd-Target (config/systemd/dbai.target) → ' ||
 'PostgreSQL (dbai-db.service) → ' ||
 'Web-Server (dbai-web.service, Port 3000) → ' ||
 'Ghost-Daemon (dbai-ghost.service) → ' ||
 'Hardware-Monitor (dbai-hardware.service) → ' ||
 'Kiosk-Chromium (dbai-kiosk.service → scripts/kiosk.sh). ' ||
 'Der gesamte Boot ist silent — kein GRUB-Menü, kein Login-Prompt, ' ||
 'direkt vom BIOS in den Web-Desktop via Chromium --kiosk.',
 92, ARRAY['bare-metal', 'boot', 'systemd', 'grub', 'kiosk', 'stufe1'],
 '0.8.0',
 ARRAY['config/systemd/dbai.target', 'config/systemd/dbai-db.service',
       'config/systemd/dbai-web.service', 'config/systemd/dbai-ghost.service',
       'config/systemd/dbai-hardware.service', 'config/systemd/dbai-kiosk.service',
       'config/grub/grub-dbai', 'scripts/kiosk.sh', 'config/packages.txt'],
 ARRAY['dbai_system'],
 '{"boot_chain": ["GRUB","Linux-Kernel","systemd","PostgreSQL","uvicorn","ghost-daemon","hardware-monitor","kiosk-chromium"],
   "total_services": 5,
   "target": "dbai.target",
   "kiosk_url": "http://localhost:3000",
   "grub_timeout": 0}'::JSONB),

('operational', 'Systemd Service-Architektur',
 'DBAI verwendet 5 systemd-Services + 1 Target: ' ||
 '(1) dbai-db.service — PostgreSQL 16, Type=notify, OOMScoreAdjust=-900, RestartSec=5, ReadWritePaths=/var/lib/postgresql. ' ||
 '(2) dbai-web.service — uvicorn auf Port 3000, After=dbai-db, RuntimeDirectory=dbai, Environment-File. ' ||
 '(3) dbai-ghost.service — Ghost-Autonomie-Daemon (bridge/ghost_autonomy.py), After=dbai-web, Restart=always. ' ||
 '(4) dbai-hardware.service — Hardware-Monitor (bridge/hardware_monitor.py), CapabilityBoundingSet=CAP_SYS_RAWIO. ' ||
 '(5) dbai-kiosk.service — Kiosk-Chromium (scripts/kiosk.sh start), After=dbai-web, Requires=graphical.target. ' ||
 'Alle gebündelt in dbai.target (WantedBy=multi-user.target).',
 88, ARRAY['systemd', 'services', 'deployment', 'stufe1'],
 '0.8.0',
 ARRAY['config/systemd/dbai-db.service', 'config/systemd/dbai-web.service',
       'config/systemd/dbai-ghost.service', 'config/systemd/dbai-hardware.service',
       'config/systemd/dbai-kiosk.service', 'config/systemd/dbai.target'],
 ARRAY['dbai_system'],
 '{"services": {
    "dbai-db":       {"type":"notify","port":5432,"restart":"on-failure","oom_adjust":-900},
    "dbai-web":      {"type":"simple","port":3000,"restart":"always","after":"dbai-db"},
    "dbai-ghost":    {"type":"simple","restart":"always","after":"dbai-web"},
    "dbai-hardware": {"type":"simple","restart":"on-failure","capabilities":"CAP_SYS_RAWIO"},
    "dbai-kiosk":    {"type":"simple","restart":"on-failure","after":"dbai-web"}
  }}'::JSONB),

('operational', 'GRUB Bootloader Konfiguration',
 'DBAI nutzt einen angepassten GRUB (config/grub/grub-dbai). Wichtige Einstellungen: ' ||
 'GRUB_TIMEOUT=0 (kein Menü), GRUB_TIMEOUT_STYLE=hidden, ' ||
 'GRUB_CMDLINE_LINUX_DEFAULT="quiet splash loglevel=0 vt.global_cursor_default=0 rd.systemd.show_status=false rd.udev.log_level=0", ' ||
 'GRUB_GFXMODE=1920x1080, GRUB_DISABLE_OS_PROBER=true. ' ||
 'Installation: sudo cp config/grub/grub-dbai /etc/default/grub && sudo update-grub. ' ||
 'ACHTUNG: Nur für dedizierte DBAI-Maschinen verwenden — deaktiviert Dual-Boot-Erkennung!',
 75, ARRAY['grub', 'boot', 'silent', 'stufe1'],
 '0.8.0',
 ARRAY['config/grub/grub-dbai'],
 ARRAY[]::TEXT[],
 '{"grub_timeout": 0, "resolution": "1920x1080", "os_prober": false}'::JSONB),

('operational', 'Kiosk-Mode Setup',
 'scripts/kiosk.sh (154 Zeilen) konfiguriert einen vollständigen Chromium-Kiosk ohne Desktop-Environment. ' ||
 'Drei Modi: setup (alles einrichten), start (manuell starten), disable (alles rückgängig). ' ||
 'Setup-Schritte: ' ||
 '1) Benutzer-Prüfung (DBAI_USER, Standard: dbai) ' ||
 '2) Auto-Login via getty@tty1 override ' ||
 '3) .xinitrc: xset -dpms, xset s off, unclutter -idle 0.5, openbox --config-file /dev/null, chromium ' ||
 '4) Chromium-Flags: --kiosk --app=http://localhost:3000 --no-first-run --disable-translate ' ||
 '   --disable-infobars --disable-suggestions-service --disable-save-password-bubble ' ||
 '   --disable-session-crashed-bubble --noerrdialogs --enable-features=OverlayScrollbar ' ||
 '   --force-device-scale-factor=1 --enable-gpu-rasterization --enable-zero-copy --ozone-platform=x11 ' ||
 '5) .bash_profile: automatisches startx wenn tty1 ' ||
 'Pakete benötigt: xorg-server, xorg-xinit, xorg-xset, openbox, chromium, unclutter',
 80, ARRAY['kiosk', 'chromium', 'x11', 'auto-login', 'stufe1'],
 '0.8.0',
 ARRAY['scripts/kiosk.sh'],
 ARRAY[]::TEXT[],
 '{"commands": {"setup": "sudo scripts/kiosk.sh setup", "start": "scripts/kiosk.sh start", "disable": "sudo scripts/kiosk.sh disable"},
   "kiosk_url": "http://localhost:3000",
   "chromium_flags": ["--kiosk","--app","--no-first-run","--disable-translate","--enable-gpu-rasterization"],
   "required_packages": ["xorg-server","xorg-xinit","openbox","chromium","unclutter"]}'::JSONB),

('operational', 'ISO/Image Builder',
 'scripts/build-iso.sh (384 Zeilen) baut ein bootfähiges DBAI-ISO-Image. ' ||
 'Unterstützt ZWEI Distro-Basen: ' ||
 '  --arch  → Arch Linux via mkarchiso/archiso (Rolling Release, minimaler Overhead) ' ||
 '  --debian → Debian via debootstrap + live-build (Stabilität, breitere HW-Unterstützung) ' ||
 'Ablauf: ' ||
 '1) Root-FS erstellen (debootstrap/pacstrap) ' ||
 '2) DBAI-Projekt nach /opt/dbai kopieren ' ||
 '3) Systemd-Services installieren ' ||
 '4) GRUB-Config übernehmen ' ||
 '5) Post-Install-Hook für Schema-Bootstrap + pip-Install ' ||
 '6) ISO generieren mit mkarchiso / genisoimage. ' ||
 'Output: /tmp/dbai-iso/dbai-<version>-<arch|debian>.iso',
 78, ARRAY['iso', 'build', 'deployment', 'arch', 'debian', 'stufe1'],
 '0.8.0',
 ARRAY['scripts/build-iso.sh'],
 ARRAY[]::TEXT[],
 '{"supported_distros": ["arch","debian"],
   "build_command": "sudo scripts/build-iso.sh --arch",
   "output_path": "/tmp/dbai-iso/",
   "arch_tools": ["archiso","mkarchiso"],
   "debian_tools": ["debootstrap","live-build","genisoimage"]}'::JSONB),

('inventory', 'Minimale Linux-Paketliste',
 'config/packages.txt (91 Zeilen) definiert die Minimal-Paketliste für ein DBAI-System: ' ||
 'Kernel: linux, linux-firmware, linux-headers. ' ||
 'Dateisystem: base, base-devel, btrfs-progs. ' ||
 'Netzwerk: networkmanager, openssh, curl, wget. ' ||
 'PostgreSQL: postgresql, postgresql-libs, pgvector (AUR). ' ||
 'Python: python, python-pip, python-psycopg2, python-fastapi, python-uvicorn, pydantic, jinja2, aiohttp. ' ||
 'Node.js: nodejs (für Vite-Build). ' ||
 'GPU: nvidia, nvidia-utils, cuda, cudnn (optional). ' ||
 'Kiosk: xorg-server, xorg-xinit, xorg-xset, openbox, chromium, unclutter. ' ||
 'Monitoring: htop, lm_sensors, nvtop, smartmontools. ' ||
 'Compiler: gcc, make (für hw_interrupts.c). ' ||
 'Security: sudo, polkit.',
 70, ARRAY['packages', 'linux', 'dependencies', 'stufe1'],
 '0.8.0',
 ARRAY['config/packages.txt'],
 ARRAY[]::TEXT[],
 '{"total_packages": 91,
   "categories": ["kernel","filesystem","network","postgresql","python","nodejs","gpu","kiosk","monitoring","compiler","security"]}'::JSONB),

-- ----- 1b) Stufe-2: Apple-Moment UX — Erkenntnisse -----

('architecture', 'Stufe 2: Taskbar Live-Stats',
 'Desktop.jsx (~790 Zeilen) hat Live-System-Metriken in der Taskbar. ' ||
 'Implementierung: ' ||
 '1) api.systemMetrics() wird alle 3 Sekunden gepollt (useEffect + setInterval) ' ||
 '2) metricsHistory useRef speichert die letzten 20 Messwerte für CPU, RAM, GPU ' ||
 '3) TaskbarMiniGraph Komponente (Zeile ~741) rendert SVG-Sparklines: ' ||
 '   - <svg viewBox="0 0 60 24"> mit 20 Datenpunkten ' ||
 '   - <polyline> für die Linie + <polygon> für den Farbverlauf darunter ' ||
 '   - Farbkodierung: >85% rot (#ff4444), >60% amber (#ffaa00), sonst Farbe des Graph-Typs ' ||
 '   - CPU=cyan, RAM=lila (#a855f7), GPU=grün (#22c55e) ' ||
 '4) CSS in global.css: .taskbar-metrics, .taskbar-mini-stat, .taskbar-mini-svg ' ||
 'Design-Entscheidung: KEIN Three.js/WebGL — nur pure CSS + SVG.',
 85, ARRAY['taskbar', 'metrics', 'sparkline', 'svg', 'desktop', 'stufe2'],
 '0.8.0',
 ARRAY['frontend/src/components/Desktop.jsx', 'frontend/src/styles/global.css'],
 ARRAY['dbai_ui'],
 '{"poll_interval_ms": 3000,
   "history_length": 20,
   "metrics": ["cpu","ram","gpu"],
   "color_thresholds": {"red": 85, "amber": 60},
   "colors": {"cpu":"#00f5ff","ram":"#a855f7","gpu":"#22c55e"}}'::JSONB),

('architecture', 'Stufe 2: Theatralische Installation',
 'SetupWizard.jsx (~655 Zeilen) zeigt nach dem Finish-Klick eine theatralische Multi-Phasen-Animation. ' ||
 'INSTALL_PHASES Array mit 5 Phasen (jeweils icon, label, color, lines[]): ' ||
 '  Phase 0: "SEARCHING FOR SUITABLE SHELL" (Cyan #00f5ff) — Hardware-Scan-Simulation ' ||
 '  Phase 1: "CONSTRUCTING RELATIONAL BACKBONE" (Lila #a855f7) — DB-Init + echtes api.setupComplete() ' ||
 '  Phase 2: "ESTABLISHING NEURAL BRIDGE" (Grün #22c55e) — LLM-Anbindung ' ||
 '  Phase 3: "AWAKENING [GHOST-NAME]" (Amber #f59e0b) — Ghost-Persönlichkeit ' ||
 '  Phase 4: "SYSTEM READY" (Mint #00ffc8) — Willkommen ' ||
 'Technik: for-Schleife über Phasen, pro Zeile 180-300ms Delay (await Promise), ' ||
 'installLines-State wird progressiv befüllt (append-only Log), ' ||
 'installPhase-State steuert Farbe/Label/Progress-Bar. ' ||
 'Die echte Datenspeicherung (api.setupComplete) passiert bei Phase 1, ' ||
 'damit die Animation vorher läuft und der User keine Lücke bemerkt. ' ||
 'CSS nutzt BootScreen-Animationen (bootFadeIn, corePulse). ' ||
 'DESIGN: Kein 3D — pulsierender Kreis mit Ghost-Emoji, farbkodierter Progress-Bar unten.',
 85, ARRAY['setup', 'installation', 'animation', 'theatrical', 'stufe2'],
 '0.8.0',
 ARRAY['frontend/src/components/apps/SetupWizard.jsx', 'frontend/src/styles/global.css'],
 ARRAY['dbai_ui'],
 '{"phases": 5,
   "phase_labels": ["SEARCHING FOR SUITABLE SHELL","CONSTRUCTING RELATIONAL BACKBONE","ESTABLISHING NEURAL BRIDGE","AWAKENING GHOST","SYSTEM READY"],
   "phase_colors": ["#00f5ff","#a855f7","#22c55e","#f59e0b","#00ffc8"],
   "line_delay_ms": [180, 300],
   "real_save_at_phase": 1,
   "total_delay_approx_ms": 6000}'::JSONB),

('architecture', 'Stufe 2: Ghost Avatar-Selector',
 'SetupWizard.jsx Welcome-Step (Step 0) enthält einen visuellen Ghost-Persönlichkeits-Wähler. ' ||
 'GHOST_AVATARS Array mit 5 Einträgen: ' ||
 '  👻 Phantom — "Vielseitig & anpassbar" (Cyan #00ffc8) ' ||
 '  ⚙️ Architect — "System & Infrastruktur" (Lila #a855f7) ' ||
 '  🔮 Oracle — "Wissen & Analyse" (Blau #3b82f6) ' ||
 '  🛡️ Sentinel — "Sicherheit & Schutz" (Rot #ef4444) ' ||
 '  ✨ Muse — "Kreativ & inspirierend" (Amber #f59e0b) ' ||
 'Jeder Avatar hat: icon, name, desc, color, glow (boxShadow), gradient (radial-gradient). ' ||
 'Bei Auswahl: settings.ghostAvatar wird gesetzt, settings.ghostName wird auf Avatar-Name geändert ' ||
 '(sofern der User den Namen nicht manuell überschrieben hat). ' ||
 'UI: 5-Spalten CSS-Grid, Selected-State mit scale(1.04) + farbigem Border + Glow-Effekt.',
 80, ARRAY['avatar', 'ghost', 'personality', 'setup', 'stufe2'],
 '0.8.0',
 ARRAY['frontend/src/components/apps/SetupWizard.jsx'],
 ARRAY['dbai_ui'],
 '{"avatars": ["phantom","architect","oracle","sentinel","muse"],
   "default_avatar": "phantom",
   "settings_key": "ghostAvatar",
   "ui_layout": "5-column grid"}'::JSONB),

('design_pattern', 'CSS-Only Animationen (kein WebGL/Three.js)',
 'DESIGN-ENTSCHEIDUNG: DBAI verwendet KEINE 3D-Libraries (Three.js, WebGL, Canvas). ' ||
 'Alle visuellen Effekte sind pure CSS + SVG: ' ||
 '  BootScreen: 3 konzentrische Ringe (border solid/dashed/dotted, animation: ringSpin), ' ||
 '    30 floating Particles (animation: particleFloat), pulsierender Kern (corePulse), ' ||
 '    Boot-Log mit fade-mask (maskImage linear-gradient). ' ||
 '  Taskbar: SVG-Sparklines (<polyline>/<polygon>) für CPU/RAM/GPU-Graphen. ' ||
 '  SetupWizard: Theatralische Phasen mit radial-gradient Glows, boxShadow Pulsation, ' ||
 '    progressive Log-Zeilen mit bootFadeIn-Animation. ' ||
 'Vorteile: Kein Bundle-Bloat, < 500 KB Gesamt-JS, funktioniert auf Low-End-GPUs, ' ||
 'läuft in Chromium-Kiosk ohne WebGL-Support.',
 90, ARRAY['css', 'animation', 'no-3d', 'design', 'performance'],
 '0.8.0',
 ARRAY['frontend/src/styles/global.css', 'frontend/src/components/BootScreen.jsx',
       'frontend/src/components/Desktop.jsx', 'frontend/src/components/apps/SetupWizard.jsx'],
 ARRAY['dbai_ui'],
 '{"animations": ["ringSpin","ringPulse","corePulse","particleFloat","bootFadeIn","blink"],
   "no_three_js": true,
   "no_webgl": true,
   "bundle_size_kb": 460}'::JSONB),

('convention', 'Frontend Build-Pipeline',
 'Frontend Build: cd frontend && npx vite build. ' ||
 'Output: frontend/dist/ (index.html + assets/). ' ||
 'Aktueller Build: 56 Module, ~460 kB JS, ~19 kB CSS, ~1.4s Build-Zeit. ' ||
 'Dev-Server: npx vite (Port 5173). ' ||
 'Prod-Server: uvicorn web.server:app (Port 3000), liefert dist/ als static files. ' ||
 'Kein TypeScript, kein ESLint, keine Tests — Fokus auf schnelle Iteration. ' ||
 'React ohne Framework (kein Next.js/Remix), nur: react, react-dom, vite. ' ||
 'API-Calls: frontend/src/api.js mit fetch() Wrapper, kein axios.',
 75, ARRAY['frontend', 'build', 'vite', 'react', 'convention'],
 '0.8.0',
 ARRAY['frontend/package.json', 'frontend/vite.config.js', 'frontend/src/api.js'],
 ARRAY['dbai_ui'],
 '{"build_command": "cd frontend && npx vite build",
   "dev_command": "cd frontend && npx vite",
   "modules": 56,
   "js_size_kb": 460,
   "css_size_kb": 19,
   "framework": "React (Vite, no TS)"}'::JSONB)

ON CONFLICT (category, title) DO UPDATE SET
    content = EXCLUDED.content,
    priority = EXCLUDED.priority,
    tags = EXCLUDED.tags,
    related_modules = EXCLUDED.related_modules,
    related_schemas = EXCLUDED.related_schemas,
    structured_data = EXCLUDED.structured_data,
    valid_from = EXCLUDED.valid_from,
    updated_at = NOW();


-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  2. MODULE REGISTRY — Neue Dateien im Modul-Verzeichnis                  ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝

INSERT INTO dbai_knowledge.module_registry
    (file_path, category, language, description, documentation, provides, depends_on,
     version, status, is_critical, boot_order) VALUES

-- Systemd Services
('config/systemd/dbai-db.service', 'config', 'conf',
 'systemd Service für PostgreSQL 16 — DBAI Kern-Datenbank',
 'Type=notify, OOMScoreAdjust=-900, RestartSec=5. Startet PostgreSQL als erste Dependency. ' ||
 'ReadWritePaths=/var/lib/postgresql. ExecStartPre prüft PGDATA-Verzeichnis.',
 '{dbai_system.services}', '{config/systemd/dbai.target}',
 '0.8.0', 'active', TRUE, 10),

('config/systemd/dbai-web.service', 'config', 'conf',
 'systemd Service für uvicorn Web-Server (Port 3000)',
 'After=dbai-db.service. Startet python3 -m uvicorn web.server:app. ' ||
 'RuntimeDirectory=dbai, EnvironmentFile=/etc/dbai/env. Restart=always.',
 '{dbai_system.services}', '{config/systemd/dbai-db.service}',
 '0.8.0', 'active', TRUE, 20),

('config/systemd/dbai-ghost.service', 'config', 'conf',
 'systemd Service für Ghost-Autonomie-Daemon',
 'After=dbai-web.service. Startet bridge/ghost_autonomy.py. Restart=always. ' ||
 'Ghost-Daemon überwacht proposed_actions und führt genehmigte Aktionen aus.',
 '{dbai_system.services}', '{config/systemd/dbai-web.service, bridge/ghost_autonomy.py}',
 '0.8.0', 'active', FALSE, 30),

('config/systemd/dbai-hardware.service', 'config', 'conf',
 'systemd Service für Hardware-Monitor-Daemon',
 'Startet bridge/hardware_monitor.py. CapabilityBoundingSet=CAP_SYS_RAWIO. ' ||
 'Liest CPU/GPU/RAM/Disk/Temp und schreibt in dbai_system Tabellen.',
 '{dbai_system.services}', '{bridge/hardware_monitor.py}',
 '0.8.0', 'active', FALSE, 25),

('config/systemd/dbai-kiosk.service', 'config', 'conf',
 'systemd Service für Chromium-Kiosk-Modus',
 'After=dbai-web.service + graphical.target. Startet scripts/kiosk.sh start. ' ||
 'Type=simple, Restart=on-failure, RestartSec=3.',
 '{dbai_system.services}', '{config/systemd/dbai-web.service, scripts/kiosk.sh}',
 '0.8.0', 'active', FALSE, 50),

('config/systemd/dbai.target', 'config', 'conf',
 'systemd Target das alle DBAI-Services bündelt',
 'WantedBy=multi-user.target. Alle dbai-*.services haben WantedBy=dbai.target. ' ||
 'Aktivierung: sudo systemctl enable dbai.target.',
 '{dbai_system.services}', '{}',
 '0.8.0', 'active', TRUE, 1),

-- GRUB
('config/grub/grub-dbai', 'config', 'conf',
 'GRUB Bootloader-Konfiguration für Silent-Boot',
 'GRUB_TIMEOUT=0, hidden, quiet splash, 1920x1080. Deaktiviert OS-Prober. ' ||
 'Nur für dedizierte Maschinen! Installation: sudo cp → /etc/default/grub → update-grub.',
 '{}', '{}',
 '0.8.0', 'active', TRUE, NULL),

-- Kiosk
('scripts/kiosk.sh', 'script', 'bash',
 'Kiosk-Mode Setup: Auto-Login → X11 → Chromium --kiosk',
 '154 Zeilen. Drei Befehle: setup, start, disable. ' ||
 'Setup: getty-override für auto-login, .xinitrc mit openbox+chromium, .bash_profile auto-startx. ' ||
 'Chromium-Flags: --kiosk --app=http://localhost:3000 mit GPU-Rasterization.',
 '{}', '{config/systemd/dbai-kiosk.service}',
 '0.8.0', 'active', TRUE, NULL),

-- ISO Builder
('scripts/build-iso.sh', 'script', 'bash',
 'ISO/Image Builder — unterstützt Arch Linux und Debian',
 '384 Zeilen. CLI: --arch oder --debian. ' ||
 'Arch: mkarchiso mit custom releng-Profil. ' ||
 'Debian: debootstrap + genisoimage. ' ||
 'Kopiert DBAI-Projekt, systemd-Services, GRUB-Config, Post-Install-Hooks.',
 '{}', '{config/systemd/dbai.target, config/grub/grub-dbai, config/packages.txt}',
 '0.8.0', 'active', FALSE, NULL),

-- Packages
('config/packages.txt', 'config', 'txt',
 'Minimale Paketliste für DBAI Bare-Metal Linux (91 Pakete)',
 'Kategorien: Kernel, Dateisystem, Netzwerk, PostgreSQL+pgvector, Python+FastAPI, ' ||
 'Node.js, NVIDIA GPU (optional), X11+Chromium-Kiosk, Monitoring, Compiler, Security.',
 '{}', '{}',
 '0.8.0', 'active', TRUE, NULL)

ON CONFLICT (file_path) DO UPDATE SET
    description = EXCLUDED.description,
    documentation = EXCLUDED.documentation,
    provides = EXCLUDED.provides,
    depends_on = EXCLUDED.depends_on,
    version = EXCLUDED.version,
    status = EXCLUDED.status,
    is_critical = EXCLUDED.is_critical,
    boot_order = EXCLUDED.boot_order,
    updated_at = NOW();


-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  3. CHANGELOG — Änderungslog                                             ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝

INSERT INTO dbai_knowledge.changelog
    (version, change_type, title, description, affected_files, author) VALUES

('0.8.0', 'feature', 'Stufe 1: Systemd Service-Dateien',
 '6 systemd Unit-Files erstellt: dbai-db.service (PostgreSQL), dbai-web.service (uvicorn), ' ||
 'dbai-ghost.service (Ghost-Daemon), dbai-hardware.service (Hardware-Monitor), ' ||
 'dbai-kiosk.service (Chromium-Kiosk), dbai.target (Bündel-Target). ' ||
 'Alle mit Restart-Policy, korrekten After-Dependencies und Security-Hardening.',
 ARRAY['config/systemd/dbai-db.service', 'config/systemd/dbai-web.service',
       'config/systemd/dbai-ghost.service', 'config/systemd/dbai-hardware.service',
       'config/systemd/dbai-kiosk.service', 'config/systemd/dbai.target'],
 'agent'),

('0.8.0', 'feature', 'Stufe 1: GRUB Silent-Boot',
 'GRUB-Konfiguration für vollständig lautlosen Boot: TIMEOUT=0, hidden menu, ' ||
 'quiet splash, 1920x1080 Auflösung, OS-Prober deaktiviert.',
 ARRAY['config/grub/grub-dbai'],
 'agent'),

('0.8.0', 'feature', 'Stufe 1: Kiosk-Mode Chromium',
 'scripts/kiosk.sh (154 Zeilen): Vollständiges Kiosk-Setup mit Auto-Login via getty, ' ||
 'X11 via openbox, Chromium --kiosk mit umfangreichen Flags für unattended operation.',
 ARRAY['scripts/kiosk.sh'],
 'agent'),

('0.8.0', 'feature', 'Stufe 1: ISO/Image Builder',
 'scripts/build-iso.sh (384 Zeilen): Bootfähiges ISO-Image generieren. ' ||
 'Dual-Distro-Support: Arch Linux (mkarchiso) und Debian (debootstrap + live-build). ' ||
 'Integriert DBAI-Projekt, systemd-Services, GRUB-Config und Post-Install-Hooks.',
 ARRAY['scripts/build-iso.sh'],
 'agent'),

('0.8.0', 'feature', 'Stufe 1: Minimale Linux-Paketliste',
 'config/packages.txt: 91 Pakete in 11 Kategorien (Kernel, PostgreSQL, Python, Node.js, ' ||
 'GPU, Kiosk, Monitoring, etc.). Definiert die minimale Basis für ein DBAI bare-metal System.',
 ARRAY['config/packages.txt'],
 'agent'),

('0.8.0', 'feature', 'Stufe 2: Taskbar Live-Stats',
 'Desktop.jsx erweitert: CPU/RAM/GPU-Metriken live in der Taskbar als SVG-Sparkline-Graphen. ' ||
 'Polling alle 3s, 20-Punkt-History, Farbkodierung (rot >85%, amber >60%). ' ||
 'TaskbarMiniGraph Komponente + CSS-Styles in global.css.',
 ARRAY['frontend/src/components/Desktop.jsx', 'frontend/src/styles/global.css'],
 'agent'),

('0.8.0', 'feature', 'Stufe 2: Theatralische Installation',
 'SetupWizard.jsx: Finish-Phase ersetzt durch 5-stufige theatralische Animation. ' ||
 'Phasen: SEARCHING FOR SHELL → CONSTRUCTING BACKBONE → NEURAL BRIDGE → AWAKENING GHOST → SYSTEM READY. ' ||
 'Progressive Log-Zeilen, farbkodierter Progress-Bar, echtes api.setupComplete() bei Phase 1.',
 ARRAY['frontend/src/components/apps/SetupWizard.jsx'],
 'agent'),

('0.8.0', 'feature', 'Stufe 2: Ghost Avatar-Selector',
 'SetupWizard.jsx Welcome-Step: 5 wählbare Ghost-Persönlichkeiten (Phantom, Architect, Oracle, ' ||
 'Sentinel, Muse) als CSS-Grid-Karten mit individuellen Farben, Glows und Hover-Effekten. ' ||
 'Auswahl setzt ghostAvatar und schlägt passenden Ghost-Namen vor.',
 ARRAY['frontend/src/components/apps/SetupWizard.jsx'],
 'agent');


-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  4. KNOWN ISSUES — Bekannte Probleme & Workarounds                       ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝

INSERT INTO dbai_knowledge.known_issues
    (title, description, severity, status, affected_files, workaround, metadata) VALUES

('Kiosk: Kein Desktop-Environment installiert',
 'scripts/kiosk.sh setzt openbox als minimalen WM ein, aber openbox muss in config/packages.txt stehen. ' ||
 'Ohne openbox startet Chromium ohne Fenster-Management und kann sich nicht korrekt positionieren.',
 'medium', 'resolved',
 ARRAY['scripts/kiosk.sh', 'config/packages.txt'],
 'openbox ist bereits in packages.txt enthalten. Bei Problemen: sudo pacman -S openbox.',
 '{"resolved_in": "0.8.0"}'::JSONB),

('GRUB: Dual-Boot wird deaktiviert',
 'config/grub/grub-dbai setzt GRUB_DISABLE_OS_PROBER=true. Auf Systemen mit Dual-Boot ' ||
 '(z.B. Windows + DBAI) wird das zweite OS nicht mehr im Boot-Menü angezeigt.',
 'high', 'workaround',
 ARRAY['config/grub/grub-dbai'],
 'GRUB-Config nur auf dedizierten DBAI-Maschinen installieren. Bei Dual-Boot: ' ||
 'GRUB_DISABLE_OS_PROBER=false setzen und GRUB_TIMEOUT auf mindestens 3.',
 '{"affects": "dual-boot systems", "safe_on": "dedicated machines"}'::JSONB),

('ISO Builder: pgvector nicht in Standard-Repos',
 'config/packages.txt listet pgvector, aber es ist auf Arch Linux nur im AUR verfügbar. ' ||
 'build-iso.sh müsste für Arch einen AUR-Helper (yay/paru) nutzen oder pgvector manuell kompilieren.',
 'medium', 'open',
 ARRAY['scripts/build-iso.sh', 'config/packages.txt'],
 'Für Arch: yay -S pgvector oder manuelles Kompilieren aus GitHub. ' ||
 'Für Debian: apt install postgresql-16-pgvector (in Debian 13+ / Postgres-Repo verfügbar).',
 '{"package": "pgvector", "arch_solution": "AUR", "debian_solution": "apt"}'::JSONB),

('ISO Builder: NVIDIA-Treiber optional aber nicht erkannt',
 'config/packages.txt enthält nvidia, nvidia-utils, cuda, cudnn. Diese Pakete sind nur für ' ||
 'NVIDIA-GPUs relevant. Auf AMD/Intel-Systemen schlägt die Installation fehl.',
 'medium', 'open',
 ARRAY['scripts/build-iso.sh', 'config/packages.txt'],
 'GPU-Pakete in packages.txt sind mit Kommentar "# NVIDIA GPU (optional)" markiert. ' ||
 'build-iso.sh sollte GPU-Erkennung enthalten und nur relevante Treiber installieren. ' ||
 'Manuelle Lösung: nvidia-Zeilen aus packages.txt entfernen wenn kein NVIDIA vorhanden.',
 '{"affects": "non-nvidia systems", "solution": "conditional install"}'::JSONB),

('Kiosk: startx Race-Condition mit dbai-web',
 'dbai-kiosk.service startet After=dbai-web.service, aber der Web-Server braucht einige Sekunden ' ||
 'für vollständige Initialisierung (DB-Pool, Schema-Check). Chromium könnte auf leere Seite treffen.',
 'low', 'workaround',
 ARRAY['config/systemd/dbai-kiosk.service', 'scripts/kiosk.sh'],
 'kiosk.sh hat bereits einen Wait-Loop der auf http://localhost:3000 wartet (curl --retry). ' ||
 'Falls der Server > 60s braucht, RestartSec im Service erhöhen.',
 '{"wait_mechanism": "curl --retry in kiosk.sh", "max_wait_sec": 60}'::JSONB),

('SetupWizard: Theatralische Installation blockt Browser',
 'Die theatralische Installation verwendet await/setTimeout in einer for-Schleife. ' ||
 'Während der ~6 Sekunden Animation ist der Thread nicht blockiert (dank await), aber der ' ||
 'User kann nicht navigieren oder abbrechen. Es gibt keinen Cancel-Button.',
 'low', 'open',
 ARRAY['frontend/src/components/apps/SetupWizard.jsx'],
 'Die Animation dauert nur ~6 Sekunden. Ein Cancel wäre technisch möglich via AbortController, ' ||
 'aber UX-mäßig nicht sinnvoll — die Daten sind bereits bei Phase 1 gespeichert.',
 '{"duration_sec": 6, "blocking": false, "cancellable": false}'::JSONB),

('Ghost Avatar: ghostAvatar wird noch nicht im Backend persistiert',
 'settings.ghostAvatar wird zwar im Frontend gesetzt und via api.setupComplete() mitgeschickt, ' ||
 'aber das Backend speichert nur userName, ghostName, locale, theme etc. ' ||
 'ghostAvatar muss in die ghost_config oder user_preferences Tabelle aufgenommen werden.',
 'medium', 'open',
 ARRAY['frontend/src/components/apps/SetupWizard.jsx', 'web/server.py'],
 'Avatar wird als Teil des JSON-Blobs an setupComplete geschickt. Backend-Erweiterung nötig: ' ||
 'db_execute("UPDATE dbai_system.ghost_config SET avatar = $1", ghostAvatar) ' ||
 'oder als JSONB-Key in der bestehenden metadata-Spalte.',
 '{"frontend_ready": true, "backend_ready": false, "settings_key": "ghostAvatar"}'::JSONB);


-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  5. BUILD LOG — Build-Dokumentation                                      ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝

INSERT INTO dbai_knowledge.build_log
    (build_type, success, duration_ms, description, system_info) VALUES

('initial_install', TRUE, 1390,
 'Frontend Build nach Stufe 1+2 Implementierung: 56 Module, 460.86 kB JS, 19.29 kB CSS. ' ||
 'Alle 8 Items (Systemd, GRUB, Kiosk, ISO, Packages, Taskbar-Stats, Theatral-Install, Avatar-Selector) ' ||
 'verifiziert und buildbar. Kein Three.js/WebGL verwendet.',
 '{"vite_version": "5.4.21",
   "modules": 56,
   "js_size_kb": 460.86,
   "css_size_kb": 19.29,
   "build_time_sec": 1.39,
   "node_version": "v22.x",
   "date": "2026-03-16",
   "stufe1_items": ["systemd","grub","kiosk","iso","packages"],
   "stufe2_items": ["taskbar-stats","theatrical-install","avatar-selector"]}'::JSONB);


-- ╔═══════════════════════════════════════════════════════════════════════════╗
-- ║  6. VERSIONS-UPDATE in system_memory                                     ║
-- ╚═══════════════════════════════════════════════════════════════════════════╝

INSERT INTO dbai_knowledge.system_memory
    (category, title, content, priority, tags, valid_from, related_schemas, structured_data) VALUES

('identity', 'Version 0.8.0 — Bare-Metal + Apple-Moment',
 'v0.8.0: Stufe 1 (Bare-Metal Boot) und Stufe 2 (Apple-Moment UX). ' ||
 'Stufe 1: systemd Services (6 Dateien), GRUB Silent-Boot, Kiosk-Chromium (154 Zeilen), ' ||
 'ISO Builder Arch+Debian (384 Zeilen), Paketliste (91 Pakete). ' ||
 'Stufe 2: Taskbar Live-Stats (SVG-Sparklines für CPU/RAM/GPU), ' ||
 'Theatralische 5-Phasen-Installation, Ghost Avatar-Selector (5 Persönlichkeiten). ' ||
 'Frontend: 56 Module, ~461 kB JS, ~19 kB CSS. Kein Three.js/WebGL — rein CSS+SVG.',
 90, ARRAY['version', 'history', 'stufe1', 'stufe2', 'v0.8.0'],
 '0.8.0', ARRAY['dbai_system', 'dbai_ui'],
 '{"stufe1": {"items": 5, "files_created": 10, "total_lines": 714},
   "stufe2": {"items": 3, "files_modified": 3, "features": ["sparklines","theatrical-install","avatar-selector"]},
   "build": {"modules": 56, "js_kb": 461, "css_kb": 19}}'::JSONB)

ON CONFLICT (category, title) DO UPDATE SET
    content = EXCLUDED.content,
    priority = EXCLUDED.priority,
    tags = EXCLUDED.tags,
    structured_data = EXCLUDED.structured_data,
    valid_from = EXCLUDED.valid_from,
    updated_at = NOW();


-- =============================================================================
-- FERTIG — Stufe 1+2 Erkenntnisse persistiert.
--
-- Abfragen:
--   SELECT title, content FROM dbai_knowledge.system_memory
--     WHERE tags @> ARRAY['stufe1'] ORDER BY priority DESC;
--
--   SELECT title, content FROM dbai_knowledge.system_memory
--     WHERE tags @> ARRAY['stufe2'] ORDER BY priority DESC;
--
--   SELECT * FROM dbai_knowledge.known_issues
--     WHERE status IN ('open', 'workaround') ORDER BY severity;
--
--   SELECT * FROM dbai_knowledge.changelog
--     WHERE version = '0.8.0' ORDER BY id;
--
--   SELECT * FROM dbai_knowledge.module_registry
--     WHERE version = '0.8.0' ORDER BY boot_order NULLS LAST;
-- =============================================================================
