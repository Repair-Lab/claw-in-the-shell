-- =============================================================================
-- DBAI Schema 28: KI Werkstatt (AI Workshop)
-- Eigene KI-Datenbanken aus persönlichen Medien bauen
-- Stand: 15. März 2026
-- =============================================================================

-- =============================================================================
-- 1. SCHEMA ERSTELLEN
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS dbai_workshop;
GRANT USAGE ON SCHEMA dbai_workshop TO dbai_runtime, dbai_monitor;

-- =============================================================================
-- 2. PROJEKTE (Eigene KI-Datenbanken)
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_workshop.projects (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL,
    name            TEXT NOT NULL,
    description     TEXT DEFAULT '',
    icon            TEXT DEFAULT '🧠',
    
    -- Konfiguration
    project_type    TEXT NOT NULL DEFAULT 'media_collection',
        -- media_collection: Bilder/Videos/Audio-Sammlung
        -- knowledge_base: Wissens-DB (Texte, PDFs, Notizen)
        -- smart_home: Smart-Home Automatisierungen
        -- personal_assistant: Persönlicher KI-Assistent
        -- custom: Benutzerdefiniert
    
    -- Status
    state           TEXT NOT NULL DEFAULT 'draft',
        -- draft, building, ready, published, archived
    
    -- Statistiken
    total_items     INTEGER DEFAULT 0,
    total_size_mb   NUMERIC(12,2) DEFAULT 0,
    embedding_count INTEGER DEFAULT 0,
    
    -- Smart-Home-Anbindung
    smart_home_enabled  BOOLEAN DEFAULT FALSE,
    smart_home_config   JSONB DEFAULT '{}',
        -- { "alexa": true, "google_home": false, "homeassistant": true, ... }
    
    -- KI-Konfiguration
    ai_config       JSONB DEFAULT '{
        "embedding_model": "all-MiniLM-L6-v2",
        "chat_model": "qwen2.5-7b-instruct",
        "auto_tag": true,
        "auto_describe": true,
        "language": "de"
    }',
    
    -- Sharing
    is_public       BOOLEAN DEFAULT FALSE,
    share_token     TEXT UNIQUE,
    
    -- Timestamps
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workshop_projects_user ON dbai_workshop.projects(user_id);
CREATE INDEX IF NOT EXISTS idx_workshop_projects_state ON dbai_workshop.projects(state);

-- =============================================================================
-- 3. MEDIEN-ITEMS (Bilder, Videos, Audio, Texte, PDFs)
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_workshop.media_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES dbai_workshop.projects(id) ON DELETE CASCADE,
    
    -- Datei-Info
    file_name       TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    file_type       TEXT NOT NULL,
        -- image, video, audio, text, pdf, document, url, other
    mime_type       TEXT,
    file_size_bytes BIGINT DEFAULT 0,
    
    -- Metadaten (automatisch + manuell)
    title           TEXT DEFAULT '',
    description     TEXT DEFAULT '',
    tags            TEXT[] DEFAULT '{}',
    
    -- KI-generierte Daten
    ai_description  TEXT DEFAULT '',
    ai_tags         TEXT[] DEFAULT '{}',
    ai_caption      TEXT DEFAULT '',
    ai_transcript   TEXT DEFAULT '',  -- Für Audio/Video
    ai_ocr_text     TEXT DEFAULT '',  -- Für Bilder mit Text
    
    -- Bild/Video-Metadaten
    width           INTEGER,
    height          INTEGER,
    duration_sec    NUMERIC(10,2),  -- Für Video/Audio
    thumbnail_path  TEXT,
    
    -- EXIF / Geo-Daten
    exif_data       JSONB DEFAULT '{}',
    latitude        NUMERIC(10,7),
    longitude       NUMERIC(10,7),
    taken_at        TIMESTAMPTZ,
    
    -- Embedding (Vektor für Ähnlichkeitssuche)
    embedding       vector(384),  -- all-MiniLM-L6-v2 Dimension
    
    -- Status
    state           TEXT DEFAULT 'pending',
        -- pending, processing, indexed, error
    error_message   TEXT,
    
    -- Verknüpfungen
    collections     TEXT[] DEFAULT '{}',
    related_items   UUID[] DEFAULT '{}',
    
    -- Timestamps
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    indexed_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_workshop_media_project ON dbai_workshop.media_items(project_id);
CREATE INDEX IF NOT EXISTS idx_workshop_media_type ON dbai_workshop.media_items(file_type);
CREATE INDEX IF NOT EXISTS idx_workshop_media_state ON dbai_workshop.media_items(state);
CREATE INDEX IF NOT EXISTS idx_workshop_media_tags ON dbai_workshop.media_items USING gin(tags);
CREATE INDEX IF NOT EXISTS idx_workshop_media_ai_tags ON dbai_workshop.media_items USING gin(ai_tags);

-- Vektor-Index für Ähnlichkeitssuche
-- CREATE INDEX IF NOT EXISTS idx_workshop_media_embedding 
--     ON dbai_workshop.media_items USING ivfflat (embedding vector_cosine_ops);

-- =============================================================================
-- 4. SAMMLUNGEN (Alben, Playlists, Ordner)
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_workshop.collections (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES dbai_workshop.projects(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    description     TEXT DEFAULT '',
    icon            TEXT DEFAULT '📁',
    collection_type TEXT DEFAULT 'album',
        -- album, playlist, folder, smart_collection, favorites
    
    -- Smart-Collection Filter (automatisch befüllt)
    smart_filter    JSONB DEFAULT NULL,
        -- { "tags": ["urlaub"], "date_range": ["2024-01-01", "2024-12-31"], "type": "image" }
    
    item_count      INTEGER DEFAULT 0,
    cover_item_id   UUID,
    sort_order      INTEGER DEFAULT 0,
    
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dbai_workshop.collection_items (
    collection_id   UUID NOT NULL REFERENCES dbai_workshop.collections(id) ON DELETE CASCADE,
    item_id         UUID NOT NULL REFERENCES dbai_workshop.media_items(id) ON DELETE CASCADE,
    sort_order      INTEGER DEFAULT 0,
    added_at        TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (collection_id, item_id)
);

-- =============================================================================
-- 5. SMART-HOME-GERÄTE & VERBINDUNGEN
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_workshop.smart_devices (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID REFERENCES dbai_workshop.projects(id) ON DELETE SET NULL,
    
    device_name     TEXT NOT NULL,
    device_type     TEXT NOT NULL,
        -- tv, speaker, display, light, switch, other
    platform        TEXT NOT NULL,
        -- alexa, google_home, homeassistant, apple_homekit, mqtt, custom
    
    -- Verbindung
    device_id       TEXT,  -- Plattform-spezifische ID
    ip_address      TEXT,
    api_endpoint    TEXT,
    auth_token      TEXT,
    
    -- Status
    is_connected    BOOLEAN DEFAULT FALSE,
    last_seen       TIMESTAMPTZ,
    capabilities    JSONB DEFAULT '{}',
        -- { "display_images": true, "play_video": true, "play_audio": true, "tts": true }
    
    -- Automatisierungen
    auto_rules      JSONB DEFAULT '[]',
        -- [{ "trigger": "time:08:00", "action": "show_random_photo", "collection": "favorites" }]
    
    state           TEXT DEFAULT 'configured',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workshop_devices_platform ON dbai_workshop.smart_devices(platform);

-- =============================================================================
-- 6. KI-CHAT-VERLAUF (Pro Projekt)
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_workshop.chat_history (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES dbai_workshop.projects(id) ON DELETE CASCADE,
    
    role            TEXT NOT NULL,  -- user, assistant, system
    content         TEXT NOT NULL,
    
    -- Kontext
    referenced_items UUID[] DEFAULT '{}',
    metadata        JSONB DEFAULT '{}',
    
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workshop_chat_project ON dbai_workshop.chat_history(project_id);

-- =============================================================================
-- 7. IMPORT-JOBS (Batch-Import von Dateien)
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_workshop.import_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES dbai_workshop.projects(id) ON DELETE CASCADE,
    
    source_type     TEXT NOT NULL,
        -- local_folder, url, google_photos, icloud, dropbox, nas, usb
    source_path     TEXT NOT NULL,
    
    -- Progress
    state           TEXT DEFAULT 'pending',
        -- pending, scanning, importing, indexing, complete, error
    total_files     INTEGER DEFAULT 0,
    processed_files INTEGER DEFAULT 0,
    failed_files    INTEGER DEFAULT 0,
    skipped_files   INTEGER DEFAULT 0,
    
    -- Log
    log_entries     JSONB DEFAULT '[]',
    error_message   TEXT,
    
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- 8. VORLAGEN (Templates für schnellen Start)
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_workshop.templates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    description     TEXT DEFAULT '',
    icon            TEXT DEFAULT '📋',
    category        TEXT DEFAULT 'general',
    
    -- Konfiguration die beim Erstellen eines Projekts übernommen wird
    project_type    TEXT NOT NULL DEFAULT 'media_collection',
    default_config  JSONB DEFAULT '{}',
    default_collections JSONB DEFAULT '[]',
    smart_home_preset   JSONB DEFAULT '{}',
    
    -- Anleitung
    setup_steps     JSONB DEFAULT '[]',
        -- [{ "step": 1, "title": "Fotos importieren", "description": "..." }]
    
    is_featured     BOOLEAN DEFAULT FALSE,
    sort_order      INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- 9. API-SCHLÜSSEL (Für externe Dienste)
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_workshop.api_keys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID REFERENCES dbai_workshop.projects(id) ON DELETE CASCADE,
    
    service_name    TEXT NOT NULL,
        -- alexa_skill, google_actions, webhook, custom_api
    api_key         TEXT NOT NULL,
    api_secret      TEXT,
    
    -- Berechtigungen
    permissions     TEXT[] DEFAULT ARRAY['read'],
    rate_limit      INTEGER DEFAULT 100,  -- Requests pro Minute
    
    is_active       BOOLEAN DEFAULT TRUE,
    last_used       TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- 10. BERECHTIGUNGEN
-- =============================================================================
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA dbai_workshop TO dbai_runtime;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA dbai_workshop TO dbai_runtime;
GRANT SELECT ON ALL TABLES IN SCHEMA dbai_workshop TO dbai_monitor;

-- =============================================================================
-- 11. VIEWS
-- =============================================================================
CREATE OR REPLACE VIEW dbai_workshop.vw_project_overview AS
SELECT
    p.id,
    p.name,
    p.description,
    p.icon,
    p.project_type,
    p.state,
    p.total_items,
    p.total_size_mb,
    p.embedding_count,
    p.smart_home_enabled,
    p.smart_home_config,
    p.ai_config,
    p.is_public,
    p.created_at,
    p.updated_at,
    (SELECT count(*) FROM dbai_workshop.collections c WHERE c.project_id = p.id) AS collection_count,
    (SELECT count(*) FROM dbai_workshop.smart_devices d WHERE d.project_id = p.id) AS device_count,
    (SELECT count(*) FROM dbai_workshop.media_items m WHERE m.project_id = p.id AND m.state = 'indexed') AS indexed_items
FROM dbai_workshop.projects p;

CREATE OR REPLACE VIEW dbai_workshop.vw_media_search AS
SELECT
    m.id,
    m.project_id,
    m.file_name,
    m.file_type,
    m.title,
    m.description,
    m.tags,
    m.ai_description,
    m.ai_tags,
    m.ai_caption,
    m.state,
    m.thumbnail_path,
    m.width,
    m.height,
    m.duration_sec,
    m.latitude,
    m.longitude,
    m.taken_at,
    m.created_at
FROM dbai_workshop.media_items m;

-- =============================================================================
-- 12. DESKTOP-APP REGISTRIERUNG
-- =============================================================================
INSERT INTO dbai_ui.apps (
    app_id, name, description, icon,
    default_width, default_height, min_width, min_height,
    resizable, source_type, source_target, required_role,
    is_system, is_pinned, category, sort_order
) VALUES (
    'ai-workshop',
    'KI Werkstatt',
    'Eigene KI-Datenbanken bauen — Bilder, Videos, Texte mit KI verknüpfen und auf Smart-Home-Geräten nutzen',
    '🔬',
    1100, 750, 700, 500,
    TRUE, 'component', 'AIWorkshop',
    'dbai_monitor',
    FALSE, TRUE, 'ai', 10
) ON CONFLICT (app_id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    icon = EXCLUDED.icon,
    default_width = EXCLUDED.default_width,
    default_height = EXCLUDED.default_height;

-- Desktop-Icon (optional — desktop_icons existiert nur in älteren Versionen)
DO $$ BEGIN
    INSERT INTO dbai_ui.desktop_icons (desktop_config_id, app_id, label, position_x, position_y)
    SELECT dc.id, 'ai-workshop', 'KI Werkstatt', 0, 0
    FROM dbai_ui.desktop_config dc
    WHERE NOT EXISTS (
        SELECT 1 FROM dbai_ui.desktop_icons di
        WHERE di.desktop_config_id = dc.id AND di.app_id = 'ai-workshop'
    );
EXCEPTION WHEN undefined_table THEN
    RAISE NOTICE 'desktop_icons existiert nicht — Icon-Registrierung übersprungen';
END $$;

-- =============================================================================
-- 13. VORLAGEN SEED-DATEN
-- =============================================================================
INSERT INTO dbai_workshop.templates (name, description, icon, category, project_type, default_config, setup_steps, is_featured, sort_order) VALUES

('Foto-Bibliothek', 
 'Organisiere deine Fotos mit KI — automatische Tags, Gesichtserkennung, Ortserkennung',
 '📸', 'media', 'media_collection',
 '{"auto_tag": true, "auto_describe": true, "face_detection": true, "geo_clustering": true}',
 '[{"step": 1, "title": "Fotos importieren", "description": "Wähle einen Ordner mit deinen Fotos aus oder verbinde Google Photos / iCloud"},
   {"step": 2, "title": "KI analysieren lassen", "description": "Die KI erkennt automatisch Inhalte, Personen und Orte"},
   {"step": 3, "title": "Sammlungen erstellen", "description": "Erstelle Alben oder nutze Smart-Sammlungen"},
   {"step": 4, "title": "Smart-Home verbinden", "description": "Zeige deine Fotos als Diashow auf dem Fernseher"}]',
 TRUE, 1),

('Video-Archiv',
 'Baue ein durchsuchbares Video-Archiv mit automatischer Transkription und Szenen-Erkennung',
 '🎬', 'media', 'media_collection',
 '{"auto_transcript": true, "scene_detection": true, "thumbnail_generation": true}',
 '[{"step": 1, "title": "Videos importieren", "description": "Importiere Videos von deiner Festplatte oder NAS"},
   {"step": 2, "title": "Transkription starten", "description": "Die KI transkribiert automatisch den gesprochenen Text"},
   {"step": 3, "title": "Durchsuchen", "description": "Suche nach Inhalten in deinen Videos per Text"},
   {"step": 4, "title": "Abspielen", "description": "Streame Videos auf Chromecast, Fire TV oder Apple TV"}]',
 TRUE, 2),

('Wissens-Datenbank',
 'Erstelle eine persönliche Wissensdatenbank aus Texten, PDFs, Notizen und Webseiten',
 '📚', 'knowledge', 'knowledge_base',
 '{"auto_summarize": true, "link_extraction": true, "citation_tracking": true}',
 '[{"step": 1, "title": "Dokumente hinzufügen", "description": "Importiere PDFs, Texte, Markdown-Dateien oder Web-URLs"},
   {"step": 2, "title": "KI verarbeiten lassen", "description": "Die KI erstellt Zusammenfassungen und verknüpft Themen"},
   {"step": 3, "title": "Fragen stellen", "description": "Stelle Fragen an deine Wissensdatenbank"},
   {"step": 4, "title": "Exportieren", "description": "Exportiere als Buch, Website oder API"}]',
 TRUE, 3),

('Smart-Home Zentrale',
 'Verbinde alle deine Smart-Home-Geräte und erstelle KI-gesteuerte Automatisierungen',
 '🏠', 'automation', 'smart_home',
 '{"auto_discover": true, "voice_control": true, "scene_automation": true}',
 '[{"step": 1, "title": "Geräte verbinden", "description": "Verbinde Alexa, Google Home oder HomeAssistant"},
   {"step": 2, "title": "Räume einrichten", "description": "Ordne Geräte Räumen zu"},
   {"step": 3, "title": "Automatisierungen", "description": "Erstelle KI-gesteuerte Regeln (z.B. Fotos auf TV bei Heimkehr)"},
   {"step": 4, "title": "Sprachbefehle", "description": "Konfiguriere eigene Alexa-Skills und Google Actions"}]',
 TRUE, 4),

('Musik-Sammlung',
 'Organisiere deine Musiksammlung mit KI-Tagging, Mood-Erkennung und Smart-Playlists',
 '🎵', 'media', 'media_collection',
 '{"mood_detection": true, "genre_classification": true, "smart_playlists": true}',
 '[{"step": 1, "title": "Musik importieren", "description": "Importiere MP3s, FLACs oder verbinde mit Spotify/Apple Music"},
   {"step": 2, "title": "KI-Analyse", "description": "Die KI erkennt Genre, Stimmung und Ähnlichkeiten"},
   {"step": 3, "title": "Smart-Playlists", "description": "Automatische Playlists basierend auf Stimmung, Genre oder Anlass"},
   {"step": 4, "title": "Abspielen", "description": "Spiele über Alexa, Sonos oder Bluetooth-Lautsprecher"}]',
 FALSE, 5),

('Rezept-Datenbank',
 'Sammle und organisiere Rezepte mit KI — Zutatenerkennung, Ernährungsanalyse, Sprachsteuerung',
 '🍳', 'knowledge', 'knowledge_base',
 '{"ingredient_detection": true, "nutrition_analysis": true, "voice_readout": true}',
 '[{"step": 1, "title": "Rezepte sammeln", "description": "Importiere Rezepte als Text, Foto oder von Webseiten"},
   {"step": 2, "title": "KI strukturieren lassen", "description": "Die KI erkennt Zutaten, Schritte und Nährwerte"},
   {"step": 3, "title": "Kochen mit Alexa", "description": "Lass dir Rezepte Schritt für Schritt vorlesen"},
   {"step": 4, "title": "Einkaufsliste", "description": "Automatische Einkaufslisten basierend auf Rezeptauswahl"}]',
 FALSE, 6)

ON CONFLICT DO NOTHING;
