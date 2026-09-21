-- ============================================================
-- Migration 64: USB index.html Network-Discovery Bugfix
-- Datum: 2026-03-17
-- ============================================================

-- ── 1. Changelog: Bug-Report ──
INSERT INTO dbai_knowledge.changelog (version, change_type, title, description, affected_files, author)
VALUES (
  'v0.12.1',
  'fix',
  'USB index.html Network-Discovery repariert',
  E'PROBLEM:\n'
  '  - User öffnete index.html auf Laptop (172.16.16.20)\n'
  '  - GhostShell-Server läuft auf 172.16.16.179:3000\n'
  '  - Discovery scannte NUR: 192.168.1.x, 192.168.0.x, 192.168.178.x, 10.42.1.x, 10.0.0.x\n'
  '  - Jeweils nur IPs 1-5 → max 25 Kandidaten\n'
  '  - 172.16.16.0/24 Subnet fehlte komplett → Server nicht gefunden\n\n'
  'ROOT CAUSE:\n'
  '  - Hardcodierte IP-Prefixes ohne 172.16.x.x (RFC 1918 Class B)\n'
  '  - Zu kleiner Scan-Bereich (nur .1-.5)\n'
  '  - Keine dynamische Subnet-Erkennung\n\n'
  'FIX (v2 Smart Subnet Detection):\n'
  '  1. KNOWN_PREFIXES erweitert um 172.16.x.x Bereiche\n'
  '  2. Scan-Range: .1-.10 + .50, .100, .150, .179, .200, .250, .254\n'
  '  3. WebRTC Local-IP-Erkennung via RTCPeerConnection\n'
  '  4. Full /24 Subnet-Scan in 50er-Batches\n'
  '  5. Manuelle IP-Eingabe als Fallback-UI',
  ARRAY['recovery/usb/index.html'],
  'ghostshell-ai'
);

-- ── 2. Changelog: Netzwerk-Architektur ──
INSERT INTO dbai_knowledge.changelog (version, change_type, title, description, author)
VALUES (
  'v0.12.1',
  'docs',
  'Netzwerk-Architektur für USB-Discovery dokumentiert',
  E'Server-Netzwerk (worker@172.16.16.179):\n'
  '  - enp8s0: 172.16.16.179/24 (Haupt-LAN)\n'
  '  - cni0: 10.42.1.1 (Kubernetes)\n'
  '  - br-xxx: 172.28.0.1 (Docker Bridge dbai_dbai-net)\n'
  '  - docker0: 172.17.0.1\n\n'
  'RFC 1918 Private Ranges (ALLE scannen):\n'
  '  - Class A: 10.0.0.0/8\n'
  '  - Class B: 172.16.0.0/12 ← WIRD OFT VERGESSEN\n'
  '  - Class C: 192.168.0.0/16\n\n'
  'LESSON LEARNED: Bei Discovery IMMER alle 3 RFC-1918-Bereiche abdecken.',
  'ghostshell-ai'
);

-- ── 3. System Memory: Bugfix ──
INSERT INTO dbai_knowledge.system_memory (category, title, content, related_modules, tags, priority, author)
VALUES (
  'operational',
  'USB index.html Network-Discovery Fix v0.12.1',
  E'Network-Discovery in USB-Stick Landing-Page repariert.\n\n'
  'VORHER: 5 Subnetze, je 5 IPs (25 Kandidaten).\n'
  'NACHHER: 15 Subnetze + WebRTC Subnet-Erkennung + Full /24 Scan + Manual Input.\n\n'
  'Fix in: recovery/usb/index.html\n'
  'USB-Update: sudo mount /dev/sdgX /mnt/ghost-app && cp recovery/usb/index.html /mnt/ghost-app/',
  ARRAY['usb-stick', 'network-discovery'],
  ARRAY['usb', 'bugfix', 'network', 'discovery', 'webrtc'],
  8,
  'ghostshell-ai'
);

-- ── 4. System Memory: Discovery-Regeln ──
INSERT INTO dbai_knowledge.system_memory (category, title, content, related_modules, tags, priority, author)
VALUES (
  'architecture',
  'Regeln für Network-Discovery in Web-Clients',
  E'REGELN (Lessons Learned):\n'
  '1. IMMER alle RFC-1918 scannen: 10.x, 172.16-31.x, 192.168.x\n'
  '2. WebRTC RTCPeerConnection für lokales Subnet\n'
  '3. IMMER Manual-Input-Fallback\n'
  '4. Typische Server-IPs: .1, .50, .100, .150, .179, .200, .250, .254\n'
  '5. Batched parallel (50 gleichzeitig)\n'
  '6. Timeout: 2s via AbortController\n'
  '7. HOST_IP env: ${HOST_IP:-10.42.1.1}',
  ARRAY['network-discovery', 'web-client'],
  ARRAY['network', 'rfc1918', 'webrtc', 'best-practice'],
  9,
  'ghostshell-ai'
);

-- ── 5. System Memory: Laptop ──
INSERT INTO dbai_knowledge.system_memory (category, title, content, related_modules, tags, priority, author)
VALUES (
  'inventory',
  'Laptop kayo@172.16.16.20 - Zugangs-Status',
  E'Laptop kayo@172.16.16.20:\n'
  '- MAC: c6:5d:56:75:1d:9e\n'
  '- SSH: GESCHLOSSEN, Ping: BLOCKIERT\n'
  '- ARP: REACHABLE aber Firewall blockiert\n'
  '- Datum: 2026-03-17\n\n'
  'SSH aktivieren:\n'
  '  macOS: Systemeinstellungen → Sharing → Entfernte Anmeldung\n'
  '  Linux: sudo systemctl enable --now sshd',
  ARRAY['hardware', 'network'],
  ARRAY['laptop', 'ssh', 'firewall'],
  5,
  'ghostshell-ai'
);
