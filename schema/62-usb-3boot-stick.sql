-- ============================================================
-- Migration 62: USB 3-Boot-Stick Dokumentation (v0.12.0)
-- ============================================================

BEGIN;

-- Changelog-Einträge
INSERT INTO dbai_knowledge.changelog (version, change_type, title, description)
VALUES
  ('0.12.0', 'feature', 'USB 3-Boot-Technologie',
   'USB 3-Boot-Technologie: 64GB-Stick mit drei Boot-Modi — App-Mode (Docker-Launcher für Win/Mac/Linux), Live-System (mit optionaler Persistenz auf P3), und Installer (Permanent-Installation auf interne SSD/HDD)'),
  ('0.12.0', 'feature', 'GRUB 3-Boot-Konfiguration',
   'GRUB 3-Boot-Konfiguration: 4 Hauptmenüs (Live+Persistence, Live RAM-only, Installer, Recovery) plus Advanced-Submenü (Debug, Memtest, HDD-Chainload, UEFI-Firmware)'),
  ('0.12.0', 'feature', 'GPT-3-Partitionierung',
   'GPT-Partitionierung: P1 FAT32 ESP 512MB (App-Mode Launcher + EFI), P2 EXT4 GHOSTSHELL 44.5GB (Live-OS + SquashFS), P3 EXT4 GHOSTPERSIST 13.6GB (PostgreSQL, Vektoren, LLM-Modelle, Sessions)'),
  ('0.12.0', 'feature', 'GhostShell Permanent-Installer',
   'GhostShell Installer-Script: Erkennt interne Laufwerke, partitioniert (EFI+System+Swap+Data), entpackt SquashFS, installiert GRUB, übernimmt Persistence-Daten, richtet systemd-Service ein'),
  ('0.12.0', 'feature', 'Persistence-Layer',
   'Persistence-Layer: Union-Mounts für /home, /var/lib/postgresql, /etc, /var/log, /opt, /root auf GHOSTPERSIST-Partition — alle Benutzeränderungen überleben Neustarts'),
  ('0.12.0', 'feature', 'App-Mode Launcher',
   'App-Mode Launcher: platform-spezifische Scripts (GhostShell.bat, ghostshell.sh, GhostShell.command) starten portable Docker-Compose-Umgebung direkt vom USB-Stick ohne Installation')
ON CONFLICT DO NOTHING;

-- System Memory
INSERT INTO dbai_knowledge.system_memory (category, title, content)
VALUES
  ('inventory', 'USB 3-Boot-Stick Layout',
   'USB 3-Boot-Stick (64GB): P1=FAT32 ESP 512MB (App-Mode), P2=EXT4 GHOSTSHELL 44.5GB (Live-OS), P3=EXT4 GHOSTPERSIST 13.6GB (Persistence). GRUB-Konfiguration mit 4 Boot-Modi. Installer-Script für Permanent-Installation. UUIDs: P1=1A36-55B6, P2=8879ba29-9073-43e9-801b-f146a19f3484, P3=d9a1e5d7-83e8-443e-9a90-005f8ba14b1f'),
  ('workflow', 'USB 3-Boot Workflow',
   'Boot-Workflow: 1) App-Mode → USB einstecken, Launcher starten, Docker-Container laufen portabel. 2) Live-System → Vom USB booten, GhostShell OS läuft im RAM mit optionaler Persistenz. 3) Installer → Vom USB booten, Menüpunkt Installer wählen, GhostShell permanent auf SSD installieren.')
ON CONFLICT DO NOTHING;

COMMIT;
