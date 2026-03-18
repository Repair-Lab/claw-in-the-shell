-- Changelog entry for frontend integration
INSERT INTO dbai_knowledge.changelog (version, change_type, title, description, affected_files, author)
VALUES (
  '0.11.1', 'update', 'Ghost Browser — Frontend-Integration',
  'Frontend-Integration für Ghost Browser: UI-Komponente, API-Client-Helfer und Desktop-Registry hinzugefügt. Ermöglicht Erstellen/Starten/Abbrechen von Tasks, Presets, Ergebnis-Download und Screenshot-Ansicht.',
  ARRAY['frontend/src/components/apps/GhostBrowser.jsx','frontend/src/api.js','frontend/src/components/Desktop.jsx'],
  'ghost-agent'
) ON CONFLICT DO NOTHING;

-- System memory entry documenting files and actions
INSERT INTO dbai_knowledge.system_memory (category, title, content, structured_data, tags, author)
VALUES (
  'convention',
  'Ghost Browser Frontend-Integration',
  'Die Ghost Browser Funktionalität wurde im Frontend implementiert: neue Komponente `GhostBrowser.jsx`, API-Client-Erweiterungen in `api.js` und Registrierung in `Desktop.jsx`. Die UI erlaubt das Anlegen, Starten und Verwalten von Browser-Tasks sowie das Herunterladen von Ergebnissen.',
  jsonb_build_object(
    'files', jsonb_build_array('frontend/src/components/apps/GhostBrowser.jsx','frontend/src/api.js','frontend/src/components/Desktop.jsx'),
    'actions', jsonb_build_array('create component','extend api client','register in desktop'),
    'notes', 'Playwright/Chromium bereits im ghost-api installiert; Backend-Endpunkte unter /api/ghost-browser/* verfügbar.'
  ),
  ARRAY['ghost-browser','frontend','ui','v0.11.1'],
  'ghost-agent'
) ON CONFLICT DO NOTHING;

-- Return recent entries for verification
SELECT id, version, change_type, title, author, created_at FROM dbai_knowledge.changelog WHERE version = '0.11.1' ORDER BY created_at DESC LIMIT 5;
SELECT id, category, title, author, created_at FROM dbai_knowledge.system_memory WHERE title LIKE 'Ghost Browser Frontend Integration%' OR title LIKE 'Ghost Browser Frontend-Integration' ORDER BY created_at DESC LIMIT 5;
