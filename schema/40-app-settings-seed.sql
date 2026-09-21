-- =============================================================================
-- DBAI Schema 40: App-Settings Seed — Defaults & Schemas für alle Apps
-- =============================================================================
-- Jede App bekommt:
--   1. default_settings  → JSONB mit Standardwerten
--   2. settings_schema   → JSONB mit UI-Schema (Typ, Label, Gruppe, min/max etc.)
--
-- Schema-Format pro Setting:
-- {
--   "key": {
--     "type": "number|boolean|string|select|color",
--     "label": "Anzeigename",
--     "group": "Gruppierung im UI",
--     "description": "Beschreibung",
--     "min": 0, "max": 100, "step": 1,       -- für number
--     "options": [{"value":"x","label":"X"}],  -- für select
--     "default": <wert>
--   }
-- }
-- =============================================================================

-- ═══════════════════════════════════════════════════════════════
-- 1. SYSTEM MONITOR
-- ═══════════════════════════════════════════════════════════════

UPDATE dbai_ui.apps SET
default_settings = '{
    "refresh_interval_ms": 5000,
    "temp_unit": "celsius",
    "size_unit": "auto",
    "warning_threshold": 70,
    "danger_threshold": 90,
    "show_cpu": true,
    "show_memory": true,
    "show_disk": true,
    "show_network": true,
    "show_temperature": true,
    "default_tab": "overview",
    "compact_mode": false,
    "chart_history_points": 60,
    "notify_on_threshold": true
}'::JSONB,
settings_schema = '{
    "refresh_interval_ms": {
        "type": "select",
        "label": "Aktualisierungs-Intervall",
        "group": "Allgemein",
        "description": "Wie oft werden die Metriken aktualisiert",
        "options": [
            {"value": 1000, "label": "1 Sekunde"},
            {"value": 2000, "label": "2 Sekunden"},
            {"value": 5000, "label": "5 Sekunden"},
            {"value": 10000, "label": "10 Sekunden"},
            {"value": 30000, "label": "30 Sekunden"},
            {"value": 60000, "label": "1 Minute"}
        ],
        "default": 5000
    },
    "temp_unit": {
        "type": "select",
        "label": "Temperatur-Einheit",
        "group": "Anzeige",
        "options": [
            {"value": "celsius", "label": "°C (Celsius)"},
            {"value": "fahrenheit", "label": "°F (Fahrenheit)"}
        ],
        "default": "celsius"
    },
    "size_unit": {
        "type": "select",
        "label": "Speichereinheit",
        "group": "Anzeige",
        "options": [
            {"value": "auto", "label": "Automatisch"},
            {"value": "mb", "label": "MB"},
            {"value": "gb", "label": "GB"}
        ],
        "default": "auto"
    },
    "warning_threshold": {
        "type": "number",
        "label": "Warnungsschwelle",
        "group": "Schwellenwerte",
        "description": "Ab diesem Prozentwert wird Gelb angezeigt",
        "min": 30, "max": 95, "step": 5, "unit": "%",
        "default": 70
    },
    "danger_threshold": {
        "type": "number",
        "label": "Kritische Schwelle",
        "group": "Schwellenwerte",
        "description": "Ab diesem Prozentwert wird Rot angezeigt",
        "min": 50, "max": 99, "step": 1, "unit": "%",
        "default": 90
    },
    "show_cpu":         {"type": "boolean", "label": "CPU anzeigen",         "group": "Metriken", "default": true},
    "show_memory":      {"type": "boolean", "label": "Speicher anzeigen",    "group": "Metriken", "default": true},
    "show_disk":        {"type": "boolean", "label": "Disk anzeigen",        "group": "Metriken", "default": true},
    "show_network":     {"type": "boolean", "label": "Netzwerk anzeigen",    "group": "Metriken", "default": true},
    "show_temperature": {"type": "boolean", "label": "Temperatur anzeigen",  "group": "Metriken", "default": true},
    "default_tab": {
        "type": "select",
        "label": "Standard-Tab",
        "group": "Allgemein",
        "options": [
            {"value": "overview",  "label": "📊 Übersicht"},
            {"value": "processes", "label": "⚙️ Prozesse"},
            {"value": "health",    "label": "🏥 Health"}
        ],
        "default": "overview"
    },
    "compact_mode": {
        "type": "boolean",
        "label": "Kompaktmodus",
        "group": "Anzeige",
        "description": "Reduzierter Abstand für mehr Informationen",
        "default": false
    },
    "chart_history_points": {
        "type": "number",
        "label": "Diagramm-Verlaufspunkte",
        "group": "Anzeige",
        "description": "Wie viele Messwerte im Diagramm angezeigt werden",
        "min": 10, "max": 300, "step": 10,
        "default": 60
    },
    "notify_on_threshold": {
        "type": "boolean",
        "label": "Desktop-Benachrichtigung",
        "group": "Schwellenwerte",
        "description": "Zeigt eine Benachrichtigung bei Schwellenwert-Überschreitung",
        "default": true
    }
}'::JSONB
WHERE app_id = 'system-monitor';


-- ═══════════════════════════════════════════════════════════════
-- 2. GHOST MANAGER
-- ═══════════════════════════════════════════════════════════════

UPDATE dbai_ui.apps SET
default_settings = '{
    "auto_swap_enabled": false,
    "swap_notification": true,
    "min_fitness_score": 0.60,
    "reload_interval_ms": 30000,
    "show_inactive_models": true,
    "default_tab": "roles",
    "confirm_swap": true,
    "auto_unload_inactive_min": 0
}'::JSONB,
settings_schema = '{
    "auto_swap_enabled": {
        "type": "boolean",
        "label": "Auto-Swap aktiviert",
        "group": "Automatisierung",
        "description": "Automatisches Modell-Wechseln basierend auf Aufgabentyp",
        "default": false
    },
    "swap_notification": {
        "type": "boolean",
        "label": "Swap-Benachrichtigung",
        "group": "Benachrichtigungen",
        "description": "Desktop-Notification bei jedem Ghost-Wechsel",
        "default": true
    },
    "min_fitness_score": {
        "type": "number",
        "label": "Min. Fitness-Score",
        "group": "Automatisierung",
        "description": "Modelle unter diesem Score werden nicht für Auto-Swap vorgeschlagen",
        "min": 0.0, "max": 1.0, "step": 0.05,
        "default": 0.60
    },
    "reload_interval_ms": {
        "type": "select",
        "label": "Aktualisierungs-Intervall",
        "group": "Allgemein",
        "options": [
            {"value": 10000, "label": "10 Sekunden"},
            {"value": 30000, "label": "30 Sekunden"},
            {"value": 60000, "label": "1 Minute"},
            {"value": 120000, "label": "2 Minuten"}
        ],
        "default": 30000
    },
    "show_inactive_models": {
        "type": "boolean",
        "label": "Inaktive Modelle anzeigen",
        "group": "Anzeige",
        "description": "Deaktivierte oder nicht geladene Modelle in der Liste anzeigen",
        "default": true
    },
    "default_tab": {
        "type": "select",
        "label": "Standard-Tab",
        "group": "Allgemein",
        "options": [
            {"value": "roles",   "label": "🎭 Rollen"},
            {"value": "models",  "label": "🧠 Modelle"},
            {"value": "history", "label": "📜 History"}
        ],
        "default": "roles"
    },
    "confirm_swap": {
        "type": "boolean",
        "label": "Swap bestätigen",
        "group": "Sicherheit",
        "description": "Vor jedem Modell-Wechsel nachfragen",
        "default": true
    },
    "auto_unload_inactive_min": {
        "type": "number",
        "label": "Auto-Entladen nach",
        "group": "Automatisierung",
        "description": "Inaktive Modelle automatisch entladen (0 = deaktiviert)",
        "min": 0, "max": 1440, "step": 5, "unit": "min",
        "default": 0
    }
}'::JSONB
WHERE app_id = 'ghost-manager';


-- ═══════════════════════════════════════════════════════════════
-- 3. TERMINAL
-- ═══════════════════════════════════════════════════════════════

UPDATE dbai_ui.apps SET
default_settings = '{
    "font_size": 13,
    "font_family": "JetBrains Mono",
    "terminal_theme": "ghost-dark",
    "scrollback_lines": 5000,
    "cursor_style": "block",
    "cursor_blink": true,
    "shell": "/bin/bash",
    "bell_enabled": false,
    "default_cwd": "~",
    "line_height": 1.3,
    "opacity": 1.0,
    "show_tab_bar": true,
    "confirm_close": true,
    "copy_on_select": false
}'::JSONB,
settings_schema = '{
    "font_size": {
        "type": "number",
        "label": "Schriftgröße",
        "group": "Darstellung",
        "min": 8, "max": 28, "step": 1, "unit": "px",
        "default": 13
    },
    "font_family": {
        "type": "select",
        "label": "Schriftart",
        "group": "Darstellung",
        "options": [
            {"value": "JetBrains Mono",  "label": "JetBrains Mono"},
            {"value": "Fira Code",       "label": "Fira Code"},
            {"value": "Cascadia Code",   "label": "Cascadia Code"},
            {"value": "Source Code Pro", "label": "Source Code Pro"},
            {"value": "IBM Plex Mono",   "label": "IBM Plex Mono"},
            {"value": "Courier New",     "label": "Courier New"}
        ],
        "default": "JetBrains Mono"
    },
    "terminal_theme": {
        "type": "select",
        "label": "Terminal-Theme",
        "group": "Darstellung",
        "description": "Farbschema des Terminal-Hintergrunds und der Schrift",
        "options": [
            {"value": "ghost-dark",  "label": "🌑 Ghost Dark (Standard)"},
            {"value": "matrix",      "label": "🟢 Matrix"},
            {"value": "solarized",   "label": "🌅 Solarized Dark"},
            {"value": "dracula",     "label": "🧛 Dracula"},
            {"value": "monokai",     "label": "🎨 Monokai"},
            {"value": "nord",        "label": "🧊 Nord"}
        ],
        "default": "ghost-dark"
    },
    "scrollback_lines": {
        "type": "number",
        "label": "Scrollback-Buffer",
        "group": "Verhalten",
        "description": "Maximale Anzahl gespeicherter Zeilen",
        "min": 500, "max": 50000, "step": 500, "unit": "Zeilen",
        "default": 5000
    },
    "cursor_style": {
        "type": "select",
        "label": "Cursor-Stil",
        "group": "Darstellung",
        "options": [
            {"value": "block",     "label": "█ Block"},
            {"value": "underline", "label": "_ Underline"},
            {"value": "bar",       "label": "│ Bar"}
        ],
        "default": "block"
    },
    "cursor_blink": {
        "type": "boolean",
        "label": "Cursor blinkt",
        "group": "Darstellung",
        "default": true
    },
    "shell": {
        "type": "select",
        "label": "Standard-Shell",
        "group": "Verhalten",
        "options": [
            {"value": "/bin/bash", "label": "Bash"},
            {"value": "/bin/zsh",  "label": "Zsh"},
            {"value": "/bin/fish", "label": "Fish"},
            {"value": "/bin/sh",   "label": "Sh (POSIX)"}
        ],
        "default": "/bin/bash"
    },
    "bell_enabled": {
        "type": "boolean",
        "label": "Terminal-Glocke",
        "group": "Verhalten",
        "description": "Spielt einen Ton bei Bell-Zeichen (\\a)",
        "default": false
    },
    "default_cwd": {
        "type": "string",
        "label": "Start-Verzeichnis",
        "group": "Verhalten",
        "description": "Das Arbeitsverzeichnis beim Öffnen eines neuen Tabs",
        "default": "~"
    },
    "line_height": {
        "type": "number",
        "label": "Zeilenabstand",
        "group": "Darstellung",
        "min": 1.0, "max": 2.5, "step": 0.1,
        "default": 1.3
    },
    "opacity": {
        "type": "number",
        "label": "Transparenz",
        "group": "Darstellung",
        "description": "1.0 = undurchsichtig, 0.5 = halbtransparent",
        "min": 0.3, "max": 1.0, "step": 0.05,
        "default": 1.0
    },
    "show_tab_bar": {
        "type": "boolean",
        "label": "Tab-Leiste anzeigen",
        "group": "Darstellung",
        "description": "Zeigt die Tab-Leiste auch bei einzelnem Tab",
        "default": true
    },
    "confirm_close": {
        "type": "boolean",
        "label": "Schließen bestätigen",
        "group": "Verhalten",
        "description": "Warnung bevor laufende Terminals geschlossen werden",
        "default": true
    },
    "copy_on_select": {
        "type": "boolean",
        "label": "Beim Markieren kopieren",
        "group": "Verhalten",
        "description": "Markierter Text wird automatisch kopiert",
        "default": false
    }
}'::JSONB
WHERE app_id = 'terminal';


-- ═══════════════════════════════════════════════════════════════
-- 4. DATEI-BROWSER
-- ═══════════════════════════════════════════════════════════════

UPDATE dbai_ui.apps SET
default_settings = '{
    "default_schema": "dbai_core",
    "rows_per_page": 50,
    "view_mode": "table",
    "sort_column": "name",
    "sort_direction": "asc",
    "show_system_tables": false,
    "show_row_count": true,
    "preview_on_click": true,
    "show_column_types": true,
    "favorites": []
}'::JSONB,
settings_schema = '{
    "default_schema": {
        "type": "select",
        "label": "Standard-Schema",
        "group": "Allgemein",
        "options": [
            {"value": "dbai_core",      "label": "dbai_core"},
            {"value": "dbai_system",    "label": "dbai_system"},
            {"value": "dbai_event",     "label": "dbai_event"},
            {"value": "dbai_ui",        "label": "dbai_ui"},
            {"value": "dbai_llm",       "label": "dbai_llm"},
            {"value": "dbai_knowledge", "label": "dbai_knowledge"},
            {"value": "dbai_journal",   "label": "dbai_journal"},
            {"value": "dbai_panic",     "label": "dbai_panic"},
            {"value": "public",         "label": "public"}
        ],
        "default": "dbai_core"
    },
    "rows_per_page": {
        "type": "select",
        "label": "Zeilen pro Seite",
        "group": "Anzeige",
        "options": [
            {"value": 10,  "label": "10"},
            {"value": 25,  "label": "25"},
            {"value": 50,  "label": "50"},
            {"value": 100, "label": "100"},
            {"value": 250, "label": "250"}
        ],
        "default": 50
    },
    "view_mode": {
        "type": "select",
        "label": "Ansichtsmodus",
        "group": "Anzeige",
        "options": [
            {"value": "table", "label": "📋 Tabelle"},
            {"value": "grid",  "label": "📦 Grid"},
            {"value": "list",  "label": "📝 Liste"}
        ],
        "default": "table"
    },
    "sort_column":    {"type": "string", "label": "Standard-Sortierung (Spalte)", "group": "Anzeige", "default": "name"},
    "sort_direction": {
        "type": "select",
        "label": "Sortierrichtung",
        "group": "Anzeige",
        "options": [
            {"value": "asc",  "label": "↑ Aufsteigend"},
            {"value": "desc", "label": "↓ Absteigend"}
        ],
        "default": "asc"
    },
    "show_system_tables": {"type": "boolean", "label": "System-Tabellen anzeigen",    "group": "Filter", "default": false},
    "show_row_count":     {"type": "boolean", "label": "Zeilenanzahl anzeigen",        "group": "Anzeige", "default": true},
    "preview_on_click":   {"type": "boolean", "label": "Vorschau bei Klick",            "group": "Verhalten", "default": true},
    "show_column_types":  {"type": "boolean", "label": "Spaltentypen anzeigen",         "group": "Anzeige", "default": true}
}'::JSONB
WHERE app_id = 'file-browser';


-- ═══════════════════════════════════════════════════════════════
-- 5. KNOWLEDGE BASE
-- ═══════════════════════════════════════════════════════════════

UPDATE dbai_ui.apps SET
default_settings = '{
    "default_tab": "files",
    "default_path": "/home/worker/DBAI",
    "show_sidebar": true,
    "file_filter": "all",
    "auto_refresh": false,
    "auto_refresh_interval_ms": 30000,
    "search_history_size": 20,
    "show_hidden_files": false,
    "models_only": false,
    "syntax_highlight": true
}'::JSONB,
settings_schema = '{
    "default_tab": {
        "type": "select",
        "label": "Standard-Tab",
        "group": "Allgemein",
        "options": [
            {"value": "files",   "label": "📂 Dateien"},
            {"value": "modules", "label": "📦 Module"},
            {"value": "errors",  "label": "🐛 Fehler"},
            {"value": "report",  "label": "📊 Report"}
        ],
        "default": "files"
    },
    "default_path": {
        "type": "string",
        "label": "Standard-Pfad",
        "group": "Allgemein",
        "description": "Startverzeichnis beim Öffnen",
        "default": "/home/worker/DBAI"
    },
    "show_sidebar":     {"type": "boolean", "label": "Sidebar anzeigen",      "group": "Anzeige", "default": true},
    "show_hidden_files": {"type": "boolean", "label": "Versteckte Dateien",   "group": "Filter",  "default": false},
    "models_only":      {"type": "boolean", "label": "Nur Modelle anzeigen",  "group": "Filter",  "default": false},
    "file_filter": {
        "type": "select",
        "label": "Dateifilter",
        "group": "Filter",
        "options": [
            {"value": "all",     "label": "Alle Dateien"},
            {"value": "code",    "label": "Code (.py/.js/.sql/.sh)"},
            {"value": "config",  "label": "Config (.toml/.json/.yaml)"},
            {"value": "docs",    "label": "Dokumente (.md/.txt)"},
            {"value": "models",  "label": "KI-Modelle (.gguf/.bin)"}
        ],
        "default": "all"
    },
    "auto_refresh":              {"type": "boolean", "label": "Auto-Refresh", "group": "Verhalten", "default": false},
    "auto_refresh_interval_ms": {
        "type": "select",
        "label": "Refresh-Intervall",
        "group": "Verhalten",
        "options": [
            {"value": 10000, "label": "10 Sekunden"},
            {"value": 30000, "label": "30 Sekunden"},
            {"value": 60000, "label": "1 Minute"}
        ],
        "default": 30000
    },
    "search_history_size": {
        "type": "number",
        "label": "Suchverlauf-Größe",
        "group": "Verhalten",
        "min": 0, "max": 100, "step": 5,
        "default": 20
    },
    "syntax_highlight": {"type": "boolean", "label": "Syntax-Highlighting", "group": "Anzeige", "default": true}
}'::JSONB
WHERE app_id = 'knowledge-base';


-- ═══════════════════════════════════════════════════════════════
-- 6. EVENT VIEWER
-- ═══════════════════════════════════════════════════════════════

UPDATE dbai_ui.apps SET
default_settings = '{
    "event_limit": 200,
    "auto_refresh_enabled": true,
    "auto_refresh_interval_ms": 3000,
    "default_type_filter": "all",
    "default_priority_filter": "all",
    "highlight_critical": true,
    "show_source": true,
    "show_timestamps": true,
    "time_format": "relative",
    "notify_critical": true,
    "export_format": "json",
    "compact_rows": false
}'::JSONB,
settings_schema = '{
    "event_limit": {
        "type": "select",
        "label": "Max. Events anzeigen",
        "group": "Allgemein",
        "options": [
            {"value": 50,   "label": "50"},
            {"value": 100,  "label": "100"},
            {"value": 200,  "label": "200"},
            {"value": 500,  "label": "500"},
            {"value": 1000, "label": "1000"}
        ],
        "default": 200
    },
    "auto_refresh_enabled": {
        "type": "boolean",
        "label": "Auto-Refresh",
        "group": "Allgemein",
        "default": true
    },
    "auto_refresh_interval_ms": {
        "type": "select",
        "label": "Refresh-Intervall",
        "group": "Allgemein",
        "options": [
            {"value": 1000,  "label": "1 Sekunde"},
            {"value": 3000,  "label": "3 Sekunden"},
            {"value": 5000,  "label": "5 Sekunden"},
            {"value": 10000, "label": "10 Sekunden"},
            {"value": 30000, "label": "30 Sekunden"}
        ],
        "default": 3000
    },
    "default_type_filter": {
        "type": "select",
        "label": "Standard-Typ-Filter",
        "group": "Filter",
        "options": [
            {"value": "all",      "label": "Alle Typen"},
            {"value": "system",   "label": "System"},
            {"value": "auth",     "label": "Auth"},
            {"value": "ghost",    "label": "Ghost"},
            {"value": "hardware", "label": "Hardware"},
            {"value": "network",  "label": "Netzwerk"}
        ],
        "default": "all"
    },
    "default_priority_filter": {
        "type": "select",
        "label": "Standard-Priorität",
        "group": "Filter",
        "options": [
            {"value": "all",      "label": "Alle Prioritäten"},
            {"value": "critical", "label": "🔴 Nur Kritisch"},
            {"value": "warning",  "label": "🟡 Warning+"},
            {"value": "info",     "label": "🔵 Info+"}
        ],
        "default": "all"
    },
    "highlight_critical": {"type": "boolean", "label": "Kritische hervorheben",     "group": "Anzeige", "default": true},
    "show_source":        {"type": "boolean", "label": "Quelle anzeigen",            "group": "Anzeige", "default": true},
    "show_timestamps":    {"type": "boolean", "label": "Zeitstempel anzeigen",       "group": "Anzeige", "default": true},
    "time_format": {
        "type": "select",
        "label": "Zeitformat",
        "group": "Anzeige",
        "options": [
            {"value": "relative", "label": "Relativ (vor 3 Min.)"},
            {"value": "absolute", "label": "Absolut (14:32:05)"},
            {"value": "iso",      "label": "ISO 8601"}
        ],
        "default": "relative"
    },
    "notify_critical":    {"type": "boolean", "label": "Benachrichtigung bei Kritisch", "group": "Benachrichtigungen", "default": true},
    "export_format": {
        "type": "select",
        "label": "Export-Format",
        "group": "Export",
        "options": [
            {"value": "json", "label": "JSON"},
            {"value": "csv",  "label": "CSV"}
        ],
        "default": "json"
    },
    "compact_rows":  {"type": "boolean", "label": "Kompakte Zeilen", "group": "Anzeige", "default": false}
}'::JSONB
WHERE app_id = 'event-viewer';


-- ═══════════════════════════════════════════════════════════════
-- 7. PROZESS-MANAGER
-- ═══════════════════════════════════════════════════════════════

UPDATE dbai_ui.apps SET
default_settings = '{
    "refresh_interval_ms": 5000,
    "default_sort_column": "cpu",
    "default_sort_direction": "desc",
    "show_pid": true,
    "show_cpu": true,
    "show_memory": true,
    "show_state": true,
    "show_type": true,
    "show_heartbeat": true,
    "confirm_kill": true,
    "cpu_warning_threshold": 80,
    "memory_warning_threshold": 80,
    "group_by": "none",
    "auto_kill_zombies": false
}'::JSONB,
settings_schema = '{
    "refresh_interval_ms": {
        "type": "select",
        "label": "Aktualisierung",
        "group": "Allgemein",
        "options": [
            {"value": 1000,  "label": "1 Sekunde"},
            {"value": 3000,  "label": "3 Sekunden"},
            {"value": 5000,  "label": "5 Sekunden"},
            {"value": 10000, "label": "10 Sekunden"},
            {"value": 30000, "label": "30 Sekunden"}
        ],
        "default": 5000
    },
    "default_sort_column": {
        "type": "select",
        "label": "Standard-Sortierung",
        "group": "Anzeige",
        "options": [
            {"value": "name",   "label": "Name"},
            {"value": "pid",    "label": "PID"},
            {"value": "cpu",    "label": "CPU-Auslastung"},
            {"value": "memory", "label": "RAM-Verbrauch"},
            {"value": "state",  "label": "Status"}
        ],
        "default": "cpu"
    },
    "default_sort_direction": {
        "type": "select",
        "label": "Sortierrichtung",
        "group": "Anzeige",
        "options": [{"value": "asc", "label": "↑ Aufsteigend"}, {"value": "desc", "label": "↓ Absteigend"}],
        "default": "desc"
    },
    "show_pid":       {"type": "boolean", "label": "PID-Spalte",       "group": "Spalten", "default": true},
    "show_cpu":       {"type": "boolean", "label": "CPU-Spalte",       "group": "Spalten", "default": true},
    "show_memory":    {"type": "boolean", "label": "Memory-Spalte",    "group": "Spalten", "default": true},
    "show_state":     {"type": "boolean", "label": "Status-Spalte",    "group": "Spalten", "default": true},
    "show_type":      {"type": "boolean", "label": "Typ-Spalte",       "group": "Spalten", "default": true},
    "show_heartbeat": {"type": "boolean", "label": "Heartbeat-Spalte", "group": "Spalten", "default": true},
    "confirm_kill": {
        "type": "boolean",
        "label": "Kill bestätigen",
        "group": "Sicherheit",
        "description": "Nachfrage bevor ein Prozess beendet wird",
        "default": true
    },
    "cpu_warning_threshold": {
        "type": "number",
        "label": "CPU-Warnschwelle",
        "group": "Schwellenwerte",
        "min": 30, "max": 100, "step": 5, "unit": "%",
        "default": 80
    },
    "memory_warning_threshold": {
        "type": "number",
        "label": "RAM-Warnschwelle",
        "group": "Schwellenwerte",
        "min": 30, "max": 100, "step": 5, "unit": "%",
        "default": 80
    },
    "group_by": {
        "type": "select",
        "label": "Gruppierung",
        "group": "Anzeige",
        "options": [
            {"value": "none",   "label": "Keine"},
            {"value": "type",   "label": "Nach Typ"},
            {"value": "state",  "label": "Nach Status"}
        ],
        "default": "none"
    },
    "auto_kill_zombies": {
        "type": "boolean",
        "label": "Zombies auto-killen",
        "group": "Automatisierung",
        "description": "Zombie-Prozesse automatisch beenden",
        "default": false
    }
}'::JSONB
WHERE app_id = 'process-manager';


-- ═══════════════════════════════════════════════════════════════
-- 8. HEALTH DASHBOARD
-- ═══════════════════════════════════════════════════════════════

UPDATE dbai_ui.apps SET
default_settings = '{
    "diagnostics_interval_ms": 30000,
    "auto_self_heal": false,
    "score_alarm_threshold": 50,
    "notify_on_degraded": true,
    "notify_sound": false,
    "repair_strategy": "cautious",
    "history_retention_days": 30,
    "show_resolved": true,
    "compact_mode": false,
    "default_tab": "overview"
}'::JSONB,
settings_schema = '{
    "diagnostics_interval_ms": {
        "type": "select",
        "label": "Diagnose-Intervall",
        "group": "Allgemein",
        "options": [
            {"value": 10000,  "label": "10 Sekunden"},
            {"value": 30000,  "label": "30 Sekunden"},
            {"value": 60000,  "label": "1 Minute"},
            {"value": 120000, "label": "2 Minuten"},
            {"value": 300000, "label": "5 Minuten"}
        ],
        "default": 30000
    },
    "auto_self_heal": {
        "type": "boolean",
        "label": "Auto-Self-Heal",
        "group": "Automatisierung",
        "description": "Automatische Reparatur bei Problemen auslösen",
        "default": false
    },
    "score_alarm_threshold": {
        "type": "number",
        "label": "Score-Alarmschwelle",
        "group": "Schwellenwerte",
        "description": "Alarm wenn der Health-Score unter diesen Wert fällt",
        "min": 10, "max": 90, "step": 5,
        "default": 50
    },
    "notify_on_degraded":  {"type": "boolean", "label": "Benachrichtigung bei Warnung",  "group": "Benachrichtigungen", "default": true},
    "notify_sound":        {"type": "boolean", "label": "Benachrichtigungs-Sound",        "group": "Benachrichtigungen", "default": false},
    "repair_strategy": {
        "type": "select",
        "label": "Reparatur-Strategie",
        "group": "Automatisierung",
        "description": "Wie aggressiv soll Self-Heal eingreifen",
        "options": [
            {"value": "cautious",   "label": "🟢 Vorsichtig (nur sichere Fixes)"},
            {"value": "balanced",   "label": "🟡 Ausgewogen"},
            {"value": "aggressive", "label": "🔴 Aggressiv (alles versuchen)"},
            {"value": "manual",     "label": "⚪ Manuell (nur Vorschläge)"}
        ],
        "default": "cautious"
    },
    "history_retention_days": {
        "type": "number",
        "label": "Verlaufs-Aufbewahrung",
        "group": "Daten",
        "min": 1, "max": 365, "step": 1, "unit": "Tage",
        "default": 30
    },
    "show_resolved": {"type": "boolean", "label": "Gelöste anzeigen",  "group": "Anzeige", "default": true},
    "compact_mode":  {"type": "boolean", "label": "Kompaktmodus",       "group": "Anzeige", "default": false},
    "default_tab": {
        "type": "select",
        "label": "Standard-Tab",
        "group": "Allgemein",
        "options": [
            {"value": "overview", "label": "📊 Übersicht"},
            {"value": "checks",  "label": "✅ Checks"},
            {"value": "history", "label": "📜 Verlauf"}
        ],
        "default": "overview"
    }
}'::JSONB
WHERE app_id = 'health-dashboard';


-- ═══════════════════════════════════════════════════════════════
-- 9. GHOST CHAT (Ergänzungen zu bestehenden Settings)
-- ═══════════════════════════════════════════════════════════════

UPDATE dbai_ui.apps SET
default_settings = '{
    "max_tokens": 2048,
    "top_p": 0.9,
    "top_k": 40,
    "markdown_enabled": true,
    "auto_title": true,
    "code_highlight_style": "monokai",
    "persist_history": true,
    "max_history_messages": 100,
    "show_token_count": false,
    "stream_response": true,
    "tts_enabled": false,
    "tts_voice": "de-DE",
    "send_shortcut": "enter",
    "show_typing_indicator": true
}'::JSONB,
settings_schema = '{
    "max_tokens": {
        "type": "number",
        "label": "Max. Antwortlänge",
        "group": "Modell",
        "description": "Maximale Tokens pro Antwort",
        "min": 128, "max": 8192, "step": 128, "unit": "Tokens",
        "default": 2048
    },
    "top_p": {
        "type": "number",
        "label": "Top-P (Nucleus Sampling)",
        "group": "Modell",
        "description": "Diversität der Antwort (0.1 = fokussiert, 1.0 = kreativ)",
        "min": 0.1, "max": 1.0, "step": 0.05,
        "default": 0.9
    },
    "top_k": {
        "type": "number",
        "label": "Top-K",
        "group": "Modell",
        "description": "Anzahl der betrachteten Token-Optionen pro Schritt",
        "min": 1, "max": 100, "step": 1,
        "default": 40
    },
    "markdown_enabled":  {"type": "boolean", "label": "Markdown-Rendering",       "group": "Anzeige", "default": true},
    "auto_title":        {"type": "boolean", "label": "Auto-Titel für Chats",     "group": "Verhalten", "default": true},
    "code_highlight_style": {
        "type": "select",
        "label": "Code-Highlighting",
        "group": "Anzeige",
        "options": [
            {"value": "monokai",    "label": "Monokai"},
            {"value": "github",     "label": "GitHub"},
            {"value": "dracula",    "label": "Dracula"},
            {"value": "solarized",  "label": "Solarized"},
            {"value": "nord",       "label": "Nord"}
        ],
        "default": "monokai"
    },
    "persist_history":      {"type": "boolean", "label": "Chat-Verlauf speichern",   "group": "Verhalten", "default": true},
    "max_history_messages": {
        "type": "number",
        "label": "Max. Verlaufsnachrichten",
        "group": "Verhalten",
        "min": 10, "max": 500, "step": 10,
        "default": 100
    },
    "show_token_count":     {"type": "boolean", "label": "Token-Zähler anzeigen",     "group": "Anzeige", "default": false},
    "stream_response":      {"type": "boolean", "label": "Streaming-Ausgabe",          "group": "Verhalten", "description": "Antwort Wort für Wort anzeigen", "default": true},
    "tts_enabled":          {"type": "boolean", "label": "Sprachausgabe (TTS)",        "group": "Sprache", "default": false},
    "tts_voice": {
        "type": "select",
        "label": "TTS-Stimme",
        "group": "Sprache",
        "options": [
            {"value": "de-DE", "label": "🇩🇪 Deutsch"},
            {"value": "en-US", "label": "🇺🇸 Englisch"},
            {"value": "en-GB", "label": "🇬🇧 Britisch"}
        ],
        "default": "de-DE"
    },
    "send_shortcut": {
        "type": "select",
        "label": "Sende-Tastenkürzel",
        "group": "Verhalten",
        "options": [
            {"value": "enter",       "label": "Enter"},
            {"value": "ctrl_enter",  "label": "Ctrl+Enter"},
            {"value": "shift_enter", "label": "Shift+Enter"}
        ],
        "default": "enter"
    },
    "show_typing_indicator": {"type": "boolean", "label": "Tipp-Animation",  "group": "Anzeige", "default": true}
}'::JSONB
WHERE app_id = 'ghost-chat';


-- ═══════════════════════════════════════════════════════════════
-- 10. SQL-KONSOLE
-- ═══════════════════════════════════════════════════════════════

UPDATE dbai_ui.apps SET
default_settings = '{
    "history_size": 50,
    "default_limit": 100,
    "font_size": 13,
    "syntax_highlighting": true,
    "auto_complete": true,
    "export_format": "json",
    "execution_timeout_s": 30,
    "persist_history": true,
    "confirm_destructive": true,
    "default_schema": "dbai_core",
    "show_execution_time": true,
    "tab_size": 2,
    "word_wrap": true
}'::JSONB,
settings_schema = '{
    "history_size": {
        "type": "number",
        "label": "Verlaufs-Größe",
        "group": "Verhalten",
        "min": 10, "max": 200, "step": 10, "unit": "Einträge",
        "default": 50
    },
    "default_limit": {
        "type": "select",
        "label": "Standard-LIMIT",
        "group": "Abfragen",
        "description": "Wird automatisch an SELECT-Abfragen angehängt",
        "options": [
            {"value": 0,    "label": "Keins"},
            {"value": 50,   "label": "50 Zeilen"},
            {"value": 100,  "label": "100 Zeilen"},
            {"value": 500,  "label": "500 Zeilen"},
            {"value": 1000, "label": "1000 Zeilen"}
        ],
        "default": 100
    },
    "font_size": {
        "type": "number",
        "label": "Schriftgröße",
        "group": "Darstellung",
        "min": 10, "max": 22, "step": 1, "unit": "px",
        "default": 13
    },
    "syntax_highlighting": {"type": "boolean", "label": "Syntax-Highlighting", "group": "Darstellung", "default": true},
    "auto_complete":       {"type": "boolean", "label": "Auto-Complete",        "group": "Darstellung", "default": true},
    "export_format": {
        "type": "select",
        "label": "Export-Format",
        "group": "Export",
        "options": [
            {"value": "json", "label": "JSON"},
            {"value": "csv",  "label": "CSV"},
            {"value": "sql",  "label": "SQL (INSERT)"}
        ],
        "default": "json"
    },
    "execution_timeout_s": {
        "type": "number",
        "label": "Abfrage-Timeout",
        "group": "Abfragen",
        "min": 5, "max": 300, "step": 5, "unit": "Sekunden",
        "default": 30
    },
    "persist_history":    {"type": "boolean", "label": "Verlauf speichern",          "group": "Verhalten", "default": true},
    "confirm_destructive": {"type": "boolean", "label": "Destruktive Abfragen bestätigen", "group": "Sicherheit", "description": "Warnung bei DELETE, DROP, TRUNCATE", "default": true},
    "default_schema": {
        "type": "select",
        "label": "Standard-Schema",
        "group": "Abfragen",
        "options": [
            {"value": "dbai_core",   "label": "dbai_core"},
            {"value": "dbai_system", "label": "dbai_system"},
            {"value": "dbai_ui",     "label": "dbai_ui"},
            {"value": "public",      "label": "public"}
        ],
        "default": "dbai_core"
    },
    "show_execution_time": {"type": "boolean", "label": "Ausführungszeit anzeigen", "group": "Darstellung", "default": true},
    "tab_size":           {"type": "number",   "label": "Tab-Breite", "group": "Darstellung", "min": 1, "max": 8, "step": 1, "unit": "Zeichen", "default": 2},
    "word_wrap":          {"type": "boolean",  "label": "Zeilenumbruch",   "group": "Darstellung", "default": true}
}'::JSONB
WHERE app_id = 'sql-console';


-- ═══════════════════════════════════════════════════════════════
-- 11. ERROR ANALYZER
-- ═══════════════════════════════════════════════════════════════

UPDATE dbai_ui.apps SET
default_settings = '{
    "retention_days": 90,
    "default_severity": "all",
    "auto_refresh_enabled": true,
    "auto_refresh_interval_ms": 15000,
    "notify_critical": true,
    "show_resolved": false,
    "default_tab": "log",
    "export_format": "json",
    "max_entries": 200,
    "group_by_pattern": true
}'::JSONB,
settings_schema = '{
    "retention_days": {
        "type": "number",
        "label": "Aufbewahrung",
        "group": "Daten",
        "min": 1, "max": 365, "step": 1, "unit": "Tage",
        "default": 90
    },
    "default_severity": {
        "type": "select",
        "label": "Standard-Severity",
        "group": "Filter",
        "options": [
            {"value": "all",      "label": "Alle"},
            {"value": "critical", "label": "🔴 Kritisch"},
            {"value": "error",    "label": "🟠 Fehler"},
            {"value": "warning",  "label": "🟡 Warnung"}
        ],
        "default": "all"
    },
    "auto_refresh_enabled":      {"type": "boolean", "label": "Auto-Refresh",          "group": "Allgemein", "default": true},
    "auto_refresh_interval_ms": {
        "type": "select",
        "label": "Refresh-Intervall",
        "group": "Allgemein",
        "options": [
            {"value": 5000,  "label": "5 Sekunden"},
            {"value": 15000, "label": "15 Sekunden"},
            {"value": 30000, "label": "30 Sekunden"},
            {"value": 60000, "label": "1 Minute"}
        ],
        "default": 15000
    },
    "notify_critical":    {"type": "boolean", "label": "Alarm bei kritischen Fehlern", "group": "Benachrichtigungen", "default": true},
    "show_resolved":      {"type": "boolean", "label": "Gelöste Fehler anzeigen",      "group": "Filter", "default": false},
    "default_tab": {
        "type": "select",
        "label": "Standard-Tab",
        "group": "Allgemein",
        "options": [
            {"value": "log",      "label": "📋 Fehler-Log"},
            {"value": "patterns", "label": "🧩 Error Patterns"},
            {"value": "runbooks", "label": "📖 Runbooks"}
        ],
        "default": "log"
    },
    "export_format": {
        "type": "select",
        "label": "Export-Format",
        "group": "Export",
        "options": [{"value": "json", "label": "JSON"}, {"value": "csv", "label": "CSV"}],
        "default": "json"
    },
    "max_entries": {
        "type": "number",
        "label": "Max. Einträge",
        "group": "Allgemein",
        "min": 50, "max": 1000, "step": 50,
        "default": 200
    },
    "group_by_pattern":  {"type": "boolean", "label": "Nach Pattern gruppieren", "group": "Anzeige", "default": true}
}'::JSONB
WHERE app_id = 'error-analyzer';


-- ═══════════════════════════════════════════════════════════════
-- 12. SOFTWARE STORE
-- ═══════════════════════════════════════════════════════════════

UPDATE dbai_ui.apps SET
default_settings = '{
    "github_token": "",
    "default_tab": "catalog",
    "install_path": "/opt/dbai-apps",
    "auto_update_check": true,
    "auto_update_interval_hours": 24,
    "confirm_install": true,
    "confirm_uninstall": true,
    "preferred_categories": [],
    "show_ghost_recommendations": true,
    "show_stars": true
}'::JSONB,
settings_schema = '{
    "github_token": {
        "type": "string",
        "label": "GitHub API-Token",
        "group": "GitHub",
        "description": "Für höhere Rate-Limits und private Repos (Optional)",
        "default": ""
    },
    "default_tab": {
        "type": "select",
        "label": "Standard-Tab",
        "group": "Allgemein",
        "options": [
            {"value": "catalog",   "label": "📦 Katalog"},
            {"value": "installed", "label": "✅ Installiert"},
            {"value": "github",    "label": "🔍 GitHub-Suche"}
        ],
        "default": "catalog"
    },
    "install_path": {
        "type": "string",
        "label": "Installations-Pfad",
        "group": "Installation",
        "description": "Wohin GitHub-Repos geklont werden",
        "default": "/opt/dbai-apps"
    },
    "auto_update_check":           {"type": "boolean", "label": "Auto-Update-Check",      "group": "Updates", "default": true},
    "auto_update_interval_hours": {
        "type": "select",
        "label": "Update-Check-Intervall",
        "group": "Updates",
        "options": [
            {"value": 6,  "label": "Alle 6 Stunden"},
            {"value": 12, "label": "Alle 12 Stunden"},
            {"value": 24, "label": "Täglich"},
            {"value": 168, "label": "Wöchentlich"}
        ],
        "default": 24
    },
    "confirm_install":   {"type": "boolean", "label": "Installation bestätigen",  "group": "Sicherheit", "default": true},
    "confirm_uninstall": {"type": "boolean", "label": "Deinstallation bestätigen", "group": "Sicherheit", "default": true},
    "show_ghost_recommendations": {"type": "boolean", "label": "Ghost-Empfehlungen", "group": "Anzeige", "description": "Zeigt die KI-Bewertung für jedes Paket", "default": true},
    "show_stars":        {"type": "boolean", "label": "GitHub-Stars anzeigen",     "group": "Anzeige", "default": true}
}'::JSONB
WHERE app_id = 'software-store';


-- ═══════════════════════════════════════════════════════════════
-- 13. OPENCLAW INTEGRATOR
-- ═══════════════════════════════════════════════════════════════

UPDATE dbai_ui.apps SET
default_settings = '{
    "openclaw_path": "~/.openclaw",
    "gateway_url": "http://localhost:8765",
    "auto_sync_enabled": false,
    "auto_sync_interval_min": 30,
    "import_skills": true,
    "import_memories": true,
    "import_agents": true,
    "import_cron": true,
    "auth_token": "",
    "notify_on_sync": true,
    "default_tab": "overview"
}'::JSONB,
settings_schema = '{
    "openclaw_path": {
        "type": "string",
        "label": "OpenClaw-Pfad",
        "group": "Verbindung",
        "description": "Pfad zum OpenClaw-Verzeichnis",
        "default": "~/.openclaw"
    },
    "gateway_url": {
        "type": "string",
        "label": "Gateway-URL",
        "group": "Verbindung",
        "description": "URL des OpenClaw-Gateways",
        "default": "http://localhost:8765"
    },
    "auto_sync_enabled": {"type": "boolean", "label": "Auto-Sync",      "group": "Synchronisation", "default": false},
    "auto_sync_interval_min": {
        "type": "select",
        "label": "Sync-Intervall",
        "group": "Synchronisation",
        "options": [
            {"value": 5,   "label": "5 Minuten"},
            {"value": 15,  "label": "15 Minuten"},
            {"value": 30,  "label": "30 Minuten"},
            {"value": 60,  "label": "1 Stunde"},
            {"value": 360, "label": "6 Stunden"}
        ],
        "default": 30
    },
    "import_skills":   {"type": "boolean", "label": "Skills importieren",   "group": "Import-Optionen", "default": true},
    "import_memories": {"type": "boolean", "label": "Memories importieren", "group": "Import-Optionen", "default": true},
    "import_agents":   {"type": "boolean", "label": "Agents importieren",   "group": "Import-Optionen", "default": true},
    "import_cron":     {"type": "boolean", "label": "Cron-Jobs importieren", "group": "Import-Optionen", "default": true},
    "auth_token": {
        "type": "string",
        "label": "Auth-Token",
        "group": "Verbindung",
        "description": "Bearer-Token für Gateway-Authentifizierung",
        "default": ""
    },
    "notify_on_sync":  {"type": "boolean", "label": "Benachrichtigung nach Sync", "group": "Benachrichtigungen", "default": true},
    "default_tab": {
        "type": "select",
        "label": "Standard-Tab",
        "group": "Allgemein",
        "options": [
            {"value": "overview", "label": "📊 Übersicht"},
            {"value": "skills",   "label": "🛠️ Skills"},
            {"value": "memories", "label": "🧠 Memories"},
            {"value": "live",     "label": "📡 Live"}
        ],
        "default": "overview"
    }
}'::JSONB
WHERE app_id = 'openclaw-integrator';


-- ═══════════════════════════════════════════════════════════════
-- 14. SQL EXPLORER
-- ═══════════════════════════════════════════════════════════════

UPDATE dbai_ui.apps SET
default_settings = '{
    "default_schema": "dbai_core",
    "rows_per_page": 50,
    "confirm_writes": true,
    "read_only_mode": false,
    "show_column_types": true,
    "json_pretty_print": true,
    "sort_column": "",
    "sort_direction": "asc",
    "inline_editing": true,
    "show_null_as": "(NULL)",
    "max_cell_width": 300,
    "show_row_numbers": true
}'::JSONB,
settings_schema = '{
    "default_schema": {
        "type": "select",
        "label": "Standard-Schema",
        "group": "Allgemein",
        "options": [
            {"value": "dbai_core",      "label": "dbai_core"},
            {"value": "dbai_system",    "label": "dbai_system"},
            {"value": "dbai_event",     "label": "dbai_event"},
            {"value": "dbai_ui",        "label": "dbai_ui"},
            {"value": "dbai_llm",       "label": "dbai_llm"},
            {"value": "dbai_knowledge", "label": "dbai_knowledge"}
        ],
        "default": "dbai_core"
    },
    "rows_per_page": {
        "type": "select",
        "label": "Zeilen pro Seite",
        "group": "Anzeige",
        "options": [
            {"value": 10,  "label": "10"},
            {"value": 25,  "label": "25"},
            {"value": 50,  "label": "50"},
            {"value": 100, "label": "100"},
            {"value": 250, "label": "250"},
            {"value": 500, "label": "500"}
        ],
        "default": 50
    },
    "confirm_writes":    {"type": "boolean", "label": "Schreiboperationen bestätigen",  "group": "Sicherheit", "default": true},
    "read_only_mode":    {"type": "boolean", "label": "Nur-Lese-Modus",                 "group": "Sicherheit", "description": "Verhindert alle Schreiboperationen", "default": false},
    "show_column_types": {"type": "boolean", "label": "Spaltentypen anzeigen",           "group": "Anzeige", "default": true},
    "json_pretty_print": {"type": "boolean", "label": "JSON formatiert anzeigen",        "group": "Anzeige", "default": true},
    "sort_direction": {
        "type": "select",
        "label": "Standard-Sortierung",
        "group": "Anzeige",
        "options": [{"value": "asc", "label": "↑ Aufsteigend"}, {"value": "desc", "label": "↓ Absteigend"}],
        "default": "asc"
    },
    "inline_editing":   {"type": "boolean", "label": "Inline-Bearbeitung",     "group": "Verhalten", "description": "Direkte Bearbeitung in der Tabelle", "default": true},
    "show_null_as": {
        "type": "select",
        "label": "NULL darstellen als",
        "group": "Anzeige",
        "options": [
            {"value": "(NULL)", "label": "(NULL)"},
            {"value": "",       "label": "(leer)"},
            {"value": "∅",     "label": "∅"}
        ],
        "default": "(NULL)"
    },
    "max_cell_width": {
        "type": "number",
        "label": "Max. Zellenbreite",
        "group": "Anzeige",
        "min": 100, "max": 800, "step": 50, "unit": "px",
        "default": 300
    },
    "show_row_numbers": {"type": "boolean", "label": "Zeilennummern", "group": "Anzeige", "default": true}
}'::JSONB
WHERE app_id = 'sql-explorer';


-- ═══════════════════════════════════════════════════════════════
-- 15. WEB BROWSER (WebFrame)
-- ═══════════════════════════════════════════════════════════════

UPDATE dbai_ui.apps SET
default_settings = '{
    "homepage": "https://search.brave.com",
    "bookmarks": [
        {"url": "https://search.brave.com",  "title": "🔍 Brave Search"},
        {"url": "https://github.com",        "title": "🐙 GitHub"},
        {"url": "https://wikipedia.org",     "title": "📚 Wikipedia"},
        {"url": "https://stackoverflow.com", "title": "💬 Stack Overflow"}
    ],
    "zoom_level": 100,
    "javascript_enabled": true,
    "blocked_domains": [],
    "save_history": true,
    "history_retention_days": 30,
    "load_timeout_ms": 10000,
    "show_url_bar": true,
    "open_links_in_new_tab": false,
    "user_agent": "default"
}'::JSONB,
settings_schema = '{
    "homepage": {
        "type": "string",
        "label": "Startseite",
        "group": "Allgemein",
        "description": "URL die beim Öffnen geladen wird",
        "default": "https://search.brave.com"
    },
    "zoom_level": {
        "type": "number",
        "label": "Zoom-Stufe",
        "group": "Anzeige",
        "min": 50, "max": 200, "step": 10, "unit": "%",
        "default": 100
    },
    "javascript_enabled": {"type": "boolean", "label": "JavaScript erlaubt", "group": "Sicherheit", "default": true},
    "save_history":       {"type": "boolean", "label": "Verlauf speichern",  "group": "Privatsphäre", "default": true},
    "history_retention_days": {
        "type": "number",
        "label": "Verlauf aufbewahren",
        "group": "Privatsphäre",
        "min": 1, "max": 365, "step": 1, "unit": "Tage",
        "default": 30
    },
    "load_timeout_ms": {
        "type": "select",
        "label": "Lade-Timeout",
        "group": "Netzwerk",
        "options": [
            {"value": 5000,  "label": "5 Sekunden"},
            {"value": 10000, "label": "10 Sekunden"},
            {"value": 20000, "label": "20 Sekunden"},
            {"value": 30000, "label": "30 Sekunden"}
        ],
        "default": 10000
    },
    "show_url_bar":          {"type": "boolean", "label": "URL-Leiste anzeigen",      "group": "Anzeige", "default": true},
    "open_links_in_new_tab": {"type": "boolean", "label": "Links in neuem Tab öffnen", "group": "Verhalten", "default": false},
    "user_agent": {
        "type": "select",
        "label": "User-Agent",
        "group": "Netzwerk",
        "options": [
            {"value": "default", "label": "Standard (DBAI Browser)"},
            {"value": "chrome",  "label": "Chrome"},
            {"value": "firefox", "label": "Firefox"},
            {"value": "minimal", "label": "Minimal"}
        ],
        "default": "default"
    }
}'::JSONB
WHERE app_id = 'web-frame';


-- ═══════════════════════════════════════════════════════════════
-- 16. LLM MANAGER
-- ═══════════════════════════════════════════════════════════════

UPDATE dbai_ui.apps SET
default_settings = '{
    "default_backend": "llama.cpp",
    "scan_paths": ["/home", "/opt", "/mnt", "/data"],
    "gpu_temp_throttle_c": 85,
    "auto_scaling": false,
    "default_context_size": 4096,
    "default_gpu_layers": 0,
    "default_threads": 4,
    "default_batch_size": 512,
    "model_download_path": "/home/worker/models",
    "benchmark_iterations": 3,
    "default_tab": "instances",
    "show_performance_overlay": true,
    "vram_reservation_mb": 512,
    "auto_start_instances": false
}'::JSONB,
settings_schema = '{
    "default_backend": {
        "type": "select",
        "label": "Standard-Backend",
        "group": "Modelle",
        "options": [
            {"value": "llama.cpp", "label": "llama.cpp"},
            {"value": "ollama",    "label": "Ollama"},
            {"value": "vllm",      "label": "vLLM"},
            {"value": "custom",    "label": "Custom"}
        ],
        "default": "llama.cpp"
    },
    "gpu_temp_throttle_c": {
        "type": "number",
        "label": "GPU-Drosselung bei",
        "group": "Hardware",
        "description": "GPU-Temperatur ab der gedrosselt wird",
        "min": 60, "max": 100, "step": 5, "unit": "°C",
        "default": 85
    },
    "auto_scaling":     {"type": "boolean", "label": "Auto-Scaling",     "group": "Automatisierung", "description": "Automatisch Instanzen bei Last starten", "default": false},
    "default_context_size": {
        "type": "select",
        "label": "Standard Context-Size",
        "group": "Modelle",
        "options": [
            {"value": 2048,   "label": "2K"},
            {"value": 4096,   "label": "4K"},
            {"value": 8192,   "label": "8K"},
            {"value": 16384,  "label": "16K"},
            {"value": 32768,  "label": "32K"},
            {"value": 131072, "label": "128K"}
        ],
        "default": 4096
    },
    "default_gpu_layers": {
        "type": "number",
        "label": "Standard GPU-Layers",
        "group": "Hardware",
        "min": 0, "max": 999, "step": 1,
        "default": 0
    },
    "default_threads": {
        "type": "number",
        "label": "Standard CPU-Threads",
        "group": "Hardware",
        "min": 1, "max": 64, "step": 1,
        "default": 4
    },
    "default_batch_size": {
        "type": "select",
        "label": "Standard Batch-Size",
        "group": "Modelle",
        "options": [
            {"value": 128,  "label": "128"},
            {"value": 256,  "label": "256"},
            {"value": 512,  "label": "512"},
            {"value": 1024, "label": "1024"},
            {"value": 2048, "label": "2048"}
        ],
        "default": 512
    },
    "model_download_path": {
        "type": "string",
        "label": "Download-Pfad",
        "group": "Speicher",
        "description": "Verzeichnis für heruntergeladene Modelle",
        "default": "/home/worker/models"
    },
    "benchmark_iterations": {
        "type": "number",
        "label": "Benchmark-Durchläufe",
        "group": "Benchmark",
        "min": 1, "max": 10, "step": 1,
        "default": 3
    },
    "default_tab": {
        "type": "select",
        "label": "Standard-Tab",
        "group": "Allgemein",
        "options": [
            {"value": "instances",  "label": "🤖 Instanzen"},
            {"value": "models",     "label": "📦 Modelle"},
            {"value": "benchmarks", "label": "📊 Benchmarks"},
            {"value": "chains",     "label": "🔗 Chains"},
            {"value": "gpus",       "label": "🎮 GPUs"}
        ],
        "default": "instances"
    },
    "show_performance_overlay": {"type": "boolean", "label": "Performance-Overlay",  "group": "Anzeige", "default": true},
    "vram_reservation_mb": {
        "type": "number",
        "label": "VRAM-Reservierung",
        "group": "Hardware",
        "description": "MB VRAM die für das System reserviert bleiben",
        "min": 0, "max": 4096, "step": 128, "unit": "MB",
        "default": 512
    },
    "auto_start_instances": {"type": "boolean", "label": "Instanzen beim Boot starten", "group": "Automatisierung", "default": false}
}'::JSONB
WHERE app_id = 'llm-manager';


-- ═══════════════════════════════════════════════════════════════
-- DONE
-- ═══════════════════════════════════════════════════════════════

SELECT 'Schema 40: App-Settings Seed-Daten eingefügt (' ||
    (SELECT COUNT(*) FROM dbai_ui.apps WHERE settings_schema != '{}'::JSONB) ||
    ' Apps konfiguriert)' AS status;
