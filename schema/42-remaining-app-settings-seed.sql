-- ============================================================================
-- DBAI v0.10.0 – Settings für restliche 13 Apps
-- ============================================================================
BEGIN;

-- 1. AI Workshop
UPDATE dbai_ui.apps SET
  default_settings = '{"editorTheme":"dark","autoSave":true,"autoSaveInterval":30,"defaultTemplate":"blank","chatMaxTokens":2048,"showPreview":true}'::jsonb,
  settings_schema = '{"editorTheme":{"type":"select","label":"Editor-Theme","group":"Editor","description":"Farbschema des Code-Editors","default":"dark","options":[{"value":"dark","label":"Dunkel"},{"value":"light","label":"Hell"},{"value":"monokai","label":"Monokai"}]},"autoSave":{"type":"boolean","label":"Auto-Speichern","group":"Editor","description":"Projekte automatisch speichern","default":true},"autoSaveInterval":{"type":"number","label":"Auto-Save Intervall (s)","group":"Editor","description":"Sekunden zwischen automatischen Speicherungen","default":30,"min":5,"max":300,"step":5},"defaultTemplate":{"type":"select","label":"Standard-Template","group":"Projekte","description":"Template für neue Projekte","default":"blank","options":[{"value":"blank","label":"Leer"},{"value":"chatbot","label":"Chatbot"},{"value":"classifier","label":"Klassifikator"},{"value":"pipeline","label":"Pipeline"}]},"chatMaxTokens":{"type":"number","label":"Max Tokens (Chat)","group":"KI","description":"Maximale Token-Anzahl für Chat-Antworten","default":2048,"min":256,"max":8192,"step":256},"showPreview":{"type":"boolean","label":"Vorschau anzeigen","group":"Editor","description":"Live-Vorschau beim Bearbeiten","default":true}}'::jsonb
WHERE app_id = 'ai-workshop';

-- 2. Anomaly Detector
UPDATE dbai_ui.apps SET
  default_settings = '{"refreshInterval":10,"severityFilter":"all","maxEntries":100,"autoRefresh":true,"showResolved":false}'::jsonb,
  settings_schema = '{"refreshInterval":{"type":"number","label":"Aktualisierung (s)","group":"Anzeige","description":"Sekunden zwischen Aktualisierungen","default":10,"min":5,"max":120,"step":5},"severityFilter":{"type":"select","label":"Schweregrad-Filter","group":"Anzeige","description":"Standard-Schweregrad-Filter","default":"all","options":[{"value":"all","label":"Alle"},{"value":"critical","label":"Kritisch"},{"value":"high","label":"Hoch"},{"value":"medium","label":"Mittel"},{"value":"low","label":"Niedrig"}]},"maxEntries":{"type":"number","label":"Max Einträge","group":"Anzeige","description":"Maximale Anzahl angezeigter Anomalien","default":100,"min":10,"max":1000,"step":10},"autoRefresh":{"type":"boolean","label":"Auto-Aktualisierung","group":"Anzeige","description":"Automatische Datenaktualisierung","default":true},"showResolved":{"type":"boolean","label":"Gelöste anzeigen","group":"Anzeige","description":"Bereits aufgelöste Anomalien anzeigen","default":false}}'::jsonb
WHERE app_id = 'anomaly_detector';

-- 3. App Sandbox
UPDATE dbai_ui.apps SET
  default_settings = '{"defaultProfile":"minimal","cpuLimit":2,"memoryLimitMB":512,"autoCleanup":true,"showLogs":true}'::jsonb,
  settings_schema = '{"defaultProfile":{"type":"select","label":"Standard-Profil","group":"Sandbox","description":"Profil für neue Sandboxes","default":"minimal","options":[{"value":"minimal","label":"Minimal"},{"value":"standard","label":"Standard"},{"value":"full","label":"Vollständig"}]},"cpuLimit":{"type":"number","label":"CPU-Limit (Cores)","group":"Ressourcen","description":"Max CPU-Kerne pro Sandbox","default":2,"min":1,"max":8,"step":1},"memoryLimitMB":{"type":"number","label":"RAM-Limit (MB)","group":"Ressourcen","description":"Max RAM pro Sandbox in MB","default":512,"min":128,"max":4096,"step":128},"autoCleanup":{"type":"boolean","label":"Auto-Cleanup","group":"Sandbox","description":"Gestoppte Sandboxes automatisch aufräumen","default":true},"showLogs":{"type":"boolean","label":"Logs anzeigen","group":"Sandbox","description":"Live-Logs laufender Sandboxes zeigen","default":true}}'::jsonb
WHERE app_id = 'app_sandbox';

-- 4. Browser Migration
UPDATE dbai_ui.apps SET
  default_settings = '{"defaultBrowser":"auto","importBookmarks":true,"importHistory":true,"importPasswords":false,"backupBeforeImport":true}'::jsonb,
  settings_schema = '{"defaultBrowser":{"type":"select","label":"Standard-Browser","group":"Import","description":"Bevorzugter Quell-Browser","default":"auto","options":[{"value":"auto","label":"Automatisch"},{"value":"chrome","label":"Chrome"},{"value":"firefox","label":"Firefox"},{"value":"edge","label":"Edge"}]},"importBookmarks":{"type":"boolean","label":"Lesezeichen importieren","group":"Import","description":"Browser-Lesezeichen übernehmen","default":true},"importHistory":{"type":"boolean","label":"Verlauf importieren","group":"Import","description":"Browser-Verlauf übernehmen","default":true},"importPasswords":{"type":"boolean","label":"Passwörter importieren","group":"Import","description":"Gespeicherte Passwörter übernehmen","default":false},"backupBeforeImport":{"type":"boolean","label":"Backup vor Import","group":"Sicherheit","description":"Sicherung erstellen bevor Import startet","default":true}}'::jsonb
WHERE app_id = 'browser_migration';

-- 5. Config Importer
UPDATE dbai_ui.apps SET
  default_settings = '{"importStrategy":"merge","backupBeforeImport":true,"showDiff":true,"autoApply":false}'::jsonb,
  settings_schema = '{"importStrategy":{"type":"select","label":"Import-Strategie","group":"Import","description":"Wie Konflikte behandelt werden","default":"merge","options":[{"value":"merge","label":"Zusammenführen"},{"value":"overwrite","label":"Überschreiben"},{"value":"skip","label":"Überspringen"}]},"backupBeforeImport":{"type":"boolean","label":"Backup vor Import","group":"Sicherheit","description":"Bestehende Konfiguration sichern","default":true},"showDiff":{"type":"boolean","label":"Diff anzeigen","group":"Anzeige","description":"Änderungen vor Import anzeigen","default":true},"autoApply":{"type":"boolean","label":"Automatisch anwenden","group":"Import","description":"Importierte Configs sofort aktivieren","default":false}}'::jsonb
WHERE app_id = 'config_importer';

-- 6. Firewall Manager
UPDATE dbai_ui.apps SET
  default_settings = '{"defaultPolicy":"deny","logLevel":"warning","autoApply":false,"refreshInterval":15,"showConnections":true}'::jsonb,
  settings_schema = '{"defaultPolicy":{"type":"select","label":"Standard-Policy","group":"Firewall","description":"Standard-Regel für unbekannten Traffic","default":"deny","options":[{"value":"deny","label":"Blockieren"},{"value":"allow","label":"Erlauben"},{"value":"reject","label":"Ablehnen"}]},"logLevel":{"type":"select","label":"Log-Level","group":"Firewall","description":"Detailgrad der Firewall-Logs","default":"warning","options":[{"value":"debug","label":"Debug"},{"value":"info","label":"Info"},{"value":"warning","label":"Warnung"},{"value":"error","label":"Fehler"}]},"autoApply":{"type":"boolean","label":"Auto-Apply","group":"Firewall","description":"Regeländerungen sofort anwenden","default":false},"refreshInterval":{"type":"number","label":"Aktualisierung (s)","group":"Anzeige","description":"Sekunden zwischen Verbindungs-Updates","default":15,"min":5,"max":120,"step":5},"showConnections":{"type":"boolean","label":"Verbindungen anzeigen","group":"Anzeige","description":"Aktive Netzwerkverbindungen einblenden","default":true}}'::jsonb
WHERE app_id = 'firewall_manager';

-- 7. Ghost Updater
UPDATE dbai_ui.apps SET
  default_settings = '{"updateChannel":"stable","autoCheck":true,"checkInterval":3600,"autoApply":false,"showChangelog":true,"defaultTab":"updates"}'::jsonb,
  settings_schema = '{"updateChannel":{"type":"select","label":"Update-Kanal","group":"Updates","description":"Welcher Update-Kanal genutzt wird","default":"stable","options":[{"value":"stable","label":"Stabil"},{"value":"beta","label":"Beta"},{"value":"nightly","label":"Nightly"},{"value":"dev","label":"Entwicklung"}]},"autoCheck":{"type":"boolean","label":"Automatisch prüfen","group":"Updates","description":"Regelmäßig nach Updates suchen","default":true},"checkInterval":{"type":"number","label":"Prüfintervall (s)","group":"Updates","description":"Sekunden zwischen Auto-Checks","default":3600,"min":300,"max":86400,"step":300},"autoApply":{"type":"boolean","label":"Auto-Anwenden","group":"Updates","description":"Updates automatisch installieren","default":false},"showChangelog":{"type":"boolean","label":"Changelog zeigen","group":"Anzeige","description":"Änderungen vor Update anzeigen","default":true},"defaultTab":{"type":"select","label":"Standard-Tab","group":"Anzeige","description":"Tab beim Öffnen","default":"updates","options":[{"value":"updates","label":"Updates"},{"value":"releases","label":"Releases"},{"value":"migrations","label":"Migrationen"},{"value":"pipeline","label":"Pipeline"},{"value":"ota","label":"OTA"}]}}'::jsonb
WHERE app_id = 'ghost_updater';

-- 8. Immutable FS
UPDATE dbai_ui.apps SET
  default_settings = '{"snapshotInterval":0,"autoRollbackOnError":false,"showDetails":true,"defaultMode":"hybrid"}'::jsonb,
  settings_schema = '{"snapshotInterval":{"type":"number","label":"Snapshot-Intervall (Min)","group":"Snapshots","description":"Automatisches Snapshot-Intervall (0=deaktiviert)","default":0,"min":0,"max":1440,"step":15},"autoRollbackOnError":{"type":"boolean","label":"Auto-Rollback","group":"Sicherheit","description":"Bei Fehler automatisch auf letzten Snapshot zurücksetzen","default":false},"showDetails":{"type":"boolean","label":"Details anzeigen","group":"Anzeige","description":"Erweiterte Informationen einblenden","default":true},"defaultMode":{"type":"select","label":"Standard-Modus","group":"Dateisystem","description":"Standard-Immutability-Modus","default":"hybrid","options":[{"value":"full","label":"Vollständig"},{"value":"hybrid","label":"Hybrid"},{"value":"off","label":"Deaktiviert"}]}}'::jsonb
WHERE app_id = 'immutable_fs';

-- 9. RAG Manager
UPDATE dbai_ui.apps SET
  default_settings = '{"chunkSize":512,"overlapSize":50,"topK":5,"embeddingModel":"default","autoReindex":false,"defaultTab":"sources"}'::jsonb,
  settings_schema = '{"chunkSize":{"type":"number","label":"Chunk-Größe","group":"Indexierung","description":"Textblockgröße für Embedding in Token","default":512,"min":128,"max":2048,"step":64},"overlapSize":{"type":"number","label":"Overlap-Größe","group":"Indexierung","description":"Überlappung zwischen Chunks in Token","default":50,"min":0,"max":256,"step":10},"topK":{"type":"number","label":"Top-K Ergebnisse","group":"Suche","description":"Anzahl der zurückgegebenen Suchergebnisse","default":5,"min":1,"max":20,"step":1},"embeddingModel":{"type":"select","label":"Embedding-Modell","group":"Indexierung","description":"Modell für Vektorisierung","default":"default","options":[{"value":"default","label":"Standard"},{"value":"openai","label":"OpenAI Ada"},{"value":"local","label":"Lokales Modell"}]},"autoReindex":{"type":"boolean","label":"Auto-Reindex","group":"Indexierung","description":"Quellen automatisch neu indexieren bei Änderungen","default":false},"defaultTab":{"type":"select","label":"Standard-Tab","group":"Anzeige","description":"Tab beim Öffnen","default":"sources","options":[{"value":"sources","label":"Quellen"},{"value":"query","label":"Abfrage"},{"value":"stats","label":"Statistiken"}]}}'::jsonb
WHERE app_id = 'rag_manager';

-- 10. Synaptic Viewer
UPDATE dbai_ui.apps SET
  default_settings = '{"retentionDays":90,"autoConsolidate":false,"consolidateInterval":24,"searchDepth":50,"showDecayed":false}'::jsonb,
  settings_schema = '{"retentionDays":{"type":"number","label":"Aufbewahrung (Tage)","group":"Speicher","description":"Wie lange Erinnerungen behalten werden","default":90,"min":7,"max":365,"step":7},"autoConsolidate":{"type":"boolean","label":"Auto-Konsolidierung","group":"Speicher","description":"Erinnerungen automatisch konsolidieren","default":false},"consolidateInterval":{"type":"number","label":"Konsolidierungs-Intervall (h)","group":"Speicher","description":"Stunden zwischen automatischer Konsolidierung","default":24,"min":1,"max":168,"step":1},"searchDepth":{"type":"number","label":"Suchtiefe","group":"Suche","description":"Maximale Ergebnisse bei Suche","default":50,"min":10,"max":500,"step":10},"showDecayed":{"type":"boolean","label":"Verfallene zeigen","group":"Anzeige","description":"Stark verfallene Erinnerungen anzeigen","default":false}}'::jsonb
WHERE app_id = 'synaptic_viewer';

-- 11. USB Installer
UPDATE dbai_ui.apps SET
  default_settings = '{"defaultImagePath":"/home/worker/DBAI/dist","verifyAfterFlash":true,"compressionEnabled":true,"autoEject":true}'::jsonb,
  settings_schema = '{"defaultImagePath":{"type":"string","label":"Standard-Image-Pfad","group":"Allgemein","description":"Verzeichnis für ISO/IMG Dateien","default":"/home/worker/DBAI/dist"},"verifyAfterFlash":{"type":"boolean","label":"Verifizieren nach Flash","group":"Sicherheit","description":"Image nach dem Schreiben prüfen","default":true},"compressionEnabled":{"type":"boolean","label":"Komprimierung","group":"Allgemein","description":"Komprimierte Images unterstützen","default":true},"autoEject":{"type":"boolean","label":"Auto-Auswerfen","group":"Allgemein","description":"USB-Stick nach Flash automatisch auswerfen","default":true}}'::jsonb
WHERE app_id = 'usb_installer';

-- 12. WLAN Hotspot
UPDATE dbai_ui.apps SET
  default_settings = '{"defaultBand":"2.4","defaultChannel":6,"maxClients":10,"dhcpRangeStart":"192.168.4.2","dhcpRangeEnd":"192.168.4.20","hideSSID":false}'::jsonb,
  settings_schema = '{"defaultBand":{"type":"select","label":"Frequenzband","group":"Netzwerk","description":"WLAN-Frequenzband","default":"2.4","options":[{"value":"2.4","label":"2.4 GHz"},{"value":"5","label":"5 GHz"},{"value":"auto","label":"Automatisch"}]},"defaultChannel":{"type":"number","label":"Kanal","group":"Netzwerk","description":"WLAN-Kanal (0=Auto)","default":6,"min":0,"max":165,"step":1},"maxClients":{"type":"number","label":"Max Clients","group":"Netzwerk","description":"Maximale gleichzeitige Verbindungen","default":10,"min":1,"max":50,"step":1},"dhcpRangeStart":{"type":"string","label":"DHCP Start","group":"DHCP","description":"Erste IP-Adresse im DHCP-Bereich","default":"192.168.4.2"},"dhcpRangeEnd":{"type":"string","label":"DHCP Ende","group":"DHCP","description":"Letzte IP-Adresse im DHCP-Bereich","default":"192.168.4.20"},"hideSSID":{"type":"boolean","label":"SSID verstecken","group":"Sicherheit","description":"Netzwerkname nicht sichtbar","default":false}}'::jsonb
WHERE app_id = 'wlan_hotspot';

-- 13. Workspace Mapper
UPDATE dbai_ui.apps SET
  default_settings = '{"excludePatterns":"node_modules,.git,__pycache__,.venv","autoScan":false,"defaultView":"tree","showHiddenFiles":false}'::jsonb,
  settings_schema = '{"excludePatterns":{"type":"string","label":"Ausschluss-Muster","group":"Scan","description":"Komma-getrennte Muster zum Ausschließen","default":"node_modules,.git,__pycache__,.venv"},"autoScan":{"type":"boolean","label":"Auto-Scan","group":"Scan","description":"Workspace automatisch scannen bei Änderungen","default":false},"defaultView":{"type":"select","label":"Standard-Ansicht","group":"Anzeige","description":"Ansicht beim Öffnen","default":"tree","options":[{"value":"tree","label":"Baumansicht"},{"value":"list","label":"Liste"},{"value":"stats","label":"Statistiken"}]},"showHiddenFiles":{"type":"boolean","label":"Versteckte Dateien","group":"Scan","description":"Versteckte Dateien/Ordner anzeigen","default":false}}'::jsonb
WHERE app_id = 'workspace_mapper';

-- Bestätige Ergebnis
SELECT app_id, 
  CASE WHEN settings_schema IS NOT NULL AND settings_schema != '{}' THEN 'OK' ELSE 'FEHLT' END AS status
FROM dbai_ui.apps 
WHERE app_id IN ('ai-workshop','anomaly_detector','app_sandbox','browser_migration','config_importer','firewall_manager','ghost_updater','immutable_fs','rag_manager','synaptic_viewer','usb_installer','wlan_hotspot','workspace_mapper')
ORDER BY app_id;

COMMIT;
