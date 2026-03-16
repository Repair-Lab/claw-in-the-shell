-- ============================================================================
-- DBAI Schema 29: SQL Explorer & WebFrame Apps Registration
-- ============================================================================

-- ── App-Registrierung: SQL Explorer ──
INSERT INTO dbai_ui.apps (
    app_id, name, icon, category, source_type, source_target,
    default_width, default_height, sort_order, is_system, status
) VALUES (
    'sql-explorer', 'SQL Explorer', '🗄️', 'tools', 'component', 'SQLExplorer',
    1000, 700, 11, false, 'active'
) ON CONFLICT (app_id) DO UPDATE
    SET source_target = 'SQLExplorer', name = 'SQL Explorer', icon = '🗄️', status = 'active';

-- ── App-Registrierung: WebFrame (Browser) ──
INSERT INTO dbai_ui.apps (
    app_id, name, icon, category, source_type, source_target,
    default_width, default_height, sort_order, is_system, status
) VALUES (
    'web-frame', 'Web Browser', '🌐', 'tools', 'component', 'WebFrame',
    1000, 700, 12, false, 'active'
) ON CONFLICT (app_id) DO UPDATE
    SET source_target = 'WebFrame', name = 'Web Browser', icon = '🌐', status = 'active';

-- ── Desktop Icons für neue Apps ──
-- (Optional, da Desktop Icons über dbai_ui.get_desktop_state geladen werden)

SELECT 'SQL Explorer & WebFrame Apps registriert' AS status;
