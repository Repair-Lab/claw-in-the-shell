-- ============================================================================
-- DBAI Schema 77: GhostPlay Media Player — App-Registrierung
-- ============================================================================
-- GhostPlay: Media Player mit Internet-Radio, spielt Bild / Video / MP3.
-- Frontend-Komponente: frontend/src/components/apps/GhostPlay.jsx

INSERT INTO dbai_ui.apps (
    app_id, name, description, icon,
    default_width, default_height, min_width, min_height, resizable,
    source_type, source_target, required_role,
    is_system, is_pinned, category, sort_order
) VALUES (
    'ghostplay', 'GhostPlay', 'Media Player: Internet-Radio, Bild-, Video- und MP3-Wiedergabe',
    '🎵', 760, 560, 420, 360, TRUE,
    'component', 'GhostPlay', 'dbai_monitor',
    FALSE, FALSE, 'media', 24
) ON CONFLICT (app_id) DO UPDATE
    SET source_target = 'GhostPlay',
        name = 'GhostPlay',
        icon = '🎵',
        description = 'Media Player: Internet-Radio, Bild-, Video- und MP3-Wiedergabe',
        category = 'media';

SELECT 'GhostPlay Media Player registriert' AS status;
