-- ═══════════════════════════════════════════════════════════════
-- DBAI v0.10.6 — Power/Reboot: Docker + Bare-Metal Dual-Mode
-- Datum: 2026-03-17
-- ═══════════════════════════════════════════════════════════════

BEGIN;

-- ── Changelog ──
INSERT INTO dbai_knowledge.changelog (version, change_type, title, description, affected_files, author)
VALUES
('0.10.6', 'feature', 'Power/Reboot Buttons: Docker-Container stoppen/neustarten oder echtes System',
 'Die /api/power/shutdown und /api/power/reboot Endpunkte erkennen jetzt automatisch ob sie in Docker (/.dockerenv) oder auf echter Hardware laufen. Docker: exit(0)=Shutdown (Container bleibt gestoppt dank unless-stopped Policy), exit(1)=Reboot (Container wird automatisch neu gestartet). Bare-Metal: systemctl poweroff/reboot wie bisher.',
 ARRAY['web/server.py', 'frontend/src/components/Desktop.jsx'], 'ghost-agent'),
('0.10.6', 'feature', 'Visueller Shutdown/Reboot-Screen im Desktop',
 'PowerMenu in Desktop.jsx zeigt jetzt einen Fullscreen-Overlay beim Herunterfahren/Neustarten. Bei Reboot: Lade-Animation + automatischer Retry alle 2s bis die API wieder erreichbar ist, dann automatischer Reload. Bei Shutdown: Hinweis "Du kannst dieses Fenster schließen".',
 ARRAY['frontend/src/components/Desktop.jsx'], 'ghost-agent')
ON CONFLICT DO NOTHING;

-- ── System Memory ──
INSERT INTO dbai_knowledge.system_memory (category, title, content, tags, author)
VALUES
('architecture', 'Power-Management: Docker vs Bare-Metal Dual-Mode',
 'server.py /api/power/shutdown und /api/power/reboot nutzen os.path.exists("/.dockerenv") zur Erkennung. Docker: os._exit(0) für Shutdown (unless-stopped startet NICHT neu bei exit 0), os._exit(1) für Reboot (unless-stopped startet NEU bei non-zero exit). Beide mit 1s Verzögerung in eigenem Thread damit die HTTP-Response noch rausgeht. Bare-Metal: subprocess.Popen systemctl poweroff/reboot.',
 ARRAY['power', 'docker', 'shutdown', 'reboot', 'unless-stopped'], 'ghost-agent')
ON CONFLICT DO NOTHING;

-- ── Build Log ──
INSERT INTO dbai_knowledge.build_log (build_type, success, duration_ms, description)
VALUES
('upgrade', true, 10000,
 'v0.10.6: Power/Reboot Endpunkte für Docker + Bare-Metal. Visueller Shutdown/Reboot-Screen. Auto-Reload bei Reboot. Exit-Code 0=Stop, 1=Restart.')
ON CONFLICT DO NOTHING;

-- ── Agent Session ──
INSERT INTO dbai_knowledge.agent_sessions (version_start, version_end, summary, files_modified, goals, decisions)
VALUES
('0.10.5', '0.10.6',
 'Power/Reboot Buttons funktionieren jetzt sowohl in Docker als auch auf echter Hardware. Docker erkennt sich via /.dockerenv. Shutdown=exit(0) stoppt Container, Reboot=exit(1) startet Container neu. Frontend zeigt visuellen Shutdown/Reboot-Screen.',
 ARRAY['web/server.py', 'frontend/src/components/Desktop.jsx'],
 ARRAY['Power-Button soll Container schließen', 'Reboot-Button soll Container neustarten', 'Auf Festplatte soll es echtes System steuern'],
 ARRAY['/.dockerenv Erkennung statt Umgebungsvariable', 'exit(0) für Stop, exit(1) für Restart — nutzt unless-stopped Policy', 'Verzögerter Exit in Thread damit Response durchgeht', 'Auto-Reload nach Reboot per /api/health Polling'])
ON CONFLICT DO NOTHING;

COMMIT;
