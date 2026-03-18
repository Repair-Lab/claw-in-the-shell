-- ============================================================================
-- DBAI Knowledge-Dokumentation: Session v0.10.3
-- Frontend-Recovery nach versehentlicher Löschung
-- ============================================================================

BEGIN;

INSERT INTO dbai_knowledge.changelog (version, change_type, title, description) VALUES
('0.10.3', 'fix', 'Frontend-Komponenten wiederhergestellt',
 'Der gesamte frontend/src/components/ Ordner wurde versehentlich gelöscht (33 App-Komponenten + 7 Core-Komponenten). Recovery aus laufendem Docker-Container via docker cp. Berechtigungen mit chown korrigiert.'),

('0.10.3', 'fix', 'useAppSettings Named-Import-Fix verifiziert',
 '13 Komponenten hatten zuvor falschen Default-Import (import useAppSettings from). Die Container-Version hatte bereits den korrekten Named-Import ({useAppSettings}). Nach Recovery keine weiteren Import-Fixes nötig.')
ON CONFLICT DO NOTHING;

INSERT INTO dbai_knowledge.system_memory (category, title, content, priority, author) VALUES
('operational', 'Frontend-Recovery aus Docker-Container',
 'Falls frontend/src/components/ gelöscht wird: sudo docker cp dbai-dashboard-ui:/app/frontend/src/components/ frontend/src/ && sudo chown -R worker:worker frontend/src/components/ && sudo docker compose restart dashboard-ui. Container behält Dateien auch bei Host-Löschung solange Volume nicht gelöscht wird.',
 95, 'agent'),

('convention', 'Docker cp erzeugt root-Dateien',
 'docker cp erstellt Dateien mit root:root Besitz. Nach jedem docker cp IMMER chown ausführen: sudo chown -R worker:worker <ziel-pfad>. Ohne chown scheitern sed, Editor-Saves und andere User-Operationen mit Permission denied.',
 90, 'agent')
ON CONFLICT DO NOTHING;

INSERT INTO dbai_knowledge.build_log (build_type, success, duration_ms, description, system_info) VALUES
('restore', true, 5000,
 'v0.10.3: Frontend-Komponenten aus Docker-Container wiederhergestellt. 33 App-JSX + 7 Core-JSX + 3 .bak Dateien. Vite ready, HTTP 200.',
 '{"version": "0.10.3", "recovery_source": "dbai-dashboard-ui container", "files_recovered": 43, "size_mb": 70.5, "method": "docker cp"}'::jsonb)
ON CONFLICT DO NOTHING;

INSERT INTO dbai_knowledge.agent_sessions (session_date, version_start, version_end, summary, files_created, files_modified, schemas_added, goals, decisions) VALUES
(CURRENT_DATE, '0.10.2', '0.10.3',
 'Frontend-Recovery: Gesamter components/-Ordner wurde versehentlich gelöscht. Wiederherstellung aus laufendem Docker-Container. Import-Fix verifiziert. DB-Dokumentation.',
 ARRAY['schema/47-knowledge-session-v0.10.3.sql'],
 ARRAY['frontend/src/components/ (43 Dateien wiederhergestellt)'],
 ARRAY['schema/47-knowledge-session-v0.10.3.sql'],
 ARRAY['Schwarze Seite diagnostizieren', 'Gelöschte Dateien wiederherstellen', 'Container neustarten', 'In DB dokumentieren'],
 ARRAY['Recovery aus laufendem Container statt git', 'chown nach docker cp', 'Import-Fix war bereits in Container-Version enthalten'])
ON CONFLICT DO NOTHING;

INSERT INTO dbai_knowledge.known_issues (title, description, severity, status, workaround) VALUES
('Host-Dateien können unabhängig vom Container gelöscht werden',
 'Bei Volume-Mounts spiegelt der Container das Host-Dateisystem. Wenn Host-Dateien gelöscht werden, sind sie auch im Container weg. Aber: Solange der Container nicht neu gestartet wird, bleiben die Dateien im Container-Overlay verfügbar.',
 'medium', 'resolved',
 'Bei versehentlicher Löschung: SOFORT docker cp nutzen bevor Container neugestartet wird. Danach wären die Dateien auch im Container weg.')
ON CONFLICT DO NOTHING;

COMMIT;
