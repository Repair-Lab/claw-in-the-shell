-- =============================================================================
-- DBAI Schema 11: Knowledge Library (Living Documentation)
-- Selbstdokumentierende Wissensdatenbank — README als Tabelle
--
-- Inspiriert von der DAAI System Library (30-system-library.sql)
-- Alles was das System ausmacht, liegt IN der DB:
--   - Jede Datei dokumentiert
--   - Jeder Fehler mit Lösung hinterlegt
--   - Jede Architektur-Entscheidung protokolliert
--   - Abhängigkeiten zwischen Modulen sichtbar
--   - Changelog direkt in der DB
--
-- Ziel: Bei Fehler sofort handeln, statt suchen.
-- =============================================================================

-- Neues Schema für die Wissensdatenbank
CREATE SCHEMA IF NOT EXISTS dbai_knowledge;

-- Berechtigungen
GRANT USAGE ON SCHEMA dbai_knowledge TO dbai_system, dbai_llm, dbai_monitor;

-- =============================================================================
-- TABELLE: module_registry
-- Jede DBAI-Datei / jedes Modul als dokumentierte Zeile
-- Das ist die "README als Datenbank" — Kein Suchen mehr, nur SELECTen
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_knowledge.module_registry (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    -- Pfad relativ zum DBAI-Root (z.B. 'schema/01-core-tables.sql')
    file_path       TEXT NOT NULL UNIQUE,
    -- Modul-Kategorie
    category        TEXT NOT NULL CHECK (category IN (
                        'schema', 'bridge', 'recovery', 'llm',
                        'config', 'script', 'test', 'c_binding',
                        'documentation', 'data'
                    )),
    -- Programmiersprache
    language        TEXT NOT NULL CHECK (language IN (
                        'sql', 'python', 'c', 'toml', 'conf',
                        'bash', 'markdown', 'txt', 'makefile', 'so'
                    )),
    -- Menschenlesbare Beschreibung: Was macht diese Datei?
    description     TEXT NOT NULL,
    -- Ausführliche Doku (ersetzt README-Abschnitt für dieses Modul)
    documentation   TEXT,
    -- Welche Schemas/Tabellen werden erstellt oder benutzt?
    provides        TEXT[] DEFAULT '{}',    -- z.B. '{dbai_core.objects, dbai_core.processes}'
    depends_on      TEXT[] DEFAULT '{}',    -- z.B. '{schema/00-extensions.sql}'
    -- Versionierung
    version         TEXT NOT NULL DEFAULT '1.0.0',
    content_hash    TEXT,                   -- SHA256 des Dateiinhalts
    -- Status
    status          TEXT NOT NULL DEFAULT 'active' CHECK (status IN (
                        'active', 'deprecated', 'planned', 'broken'
                    )),
    is_critical     BOOLEAN NOT NULL DEFAULT FALSE,
    -- Boot-Reihenfolge (NULL = wird nicht beim Boot geladen)
    boot_order      INTEGER,
    -- Metadaten
    metadata        JSONB DEFAULT '{}',
    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_verified   TIMESTAMPTZ
);

DROP TRIGGER IF EXISTS trg_module_updated ON dbai_knowledge.module_registry;
CREATE TRIGGER trg_module_updated
    BEFORE UPDATE ON dbai_knowledge.module_registry
    FOR EACH ROW EXECUTE FUNCTION dbai_core.update_timestamp();

CREATE INDEX IF NOT EXISTS idx_module_category ON dbai_knowledge.module_registry(category);
CREATE INDEX IF NOT EXISTS idx_module_status ON dbai_knowledge.module_registry(status);
CREATE INDEX IF NOT EXISTS idx_module_critical ON dbai_knowledge.module_registry(is_critical) WHERE is_critical = TRUE;
CREATE INDEX IF NOT EXISTS idx_module_provides ON dbai_knowledge.module_registry USING GIN(provides);
CREATE INDEX IF NOT EXISTS idx_module_depends ON dbai_knowledge.module_registry USING GIN(depends_on);

-- =============================================================================
-- TABELLE: module_dependencies
-- Explizite Abhängigkeiten zwischen Modulen (gerichteter Graph)
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_knowledge.module_dependencies (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id       UUID NOT NULL REFERENCES dbai_knowledge.module_registry(id) ON DELETE CASCADE,
    target_id       UUID NOT NULL REFERENCES dbai_knowledge.module_registry(id) ON DELETE CASCADE,
    dependency_type TEXT NOT NULL CHECK (dependency_type IN (
                        'requires',      -- Muss vorher geladen sein
                        'uses',          -- Benutzt Funktionen/Tabellen
                        'extends',       -- Erweitert die Funktionalität
                        'tests',         -- Testet dieses Modul
                        'configures',    -- Konfiguriert dieses Modul
                        'documents'      -- Dokumentiert dieses Modul
                    )),
    description     TEXT,
    is_critical     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT no_self_dep CHECK (source_id <> target_id),
    UNIQUE (source_id, target_id, dependency_type)
);

CREATE INDEX IF NOT EXISTS idx_dep_source ON dbai_knowledge.module_dependencies(source_id);
CREATE INDEX IF NOT EXISTS idx_dep_target ON dbai_knowledge.module_dependencies(target_id);

-- =============================================================================
-- TABELLE: changelog
-- Jede Änderung am System — append-only wie das Journal
-- Ersetzt die klassische CHANGELOG.md Datei
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_knowledge.changelog (
    id              BIGSERIAL PRIMARY KEY,
    version         TEXT NOT NULL,              -- z.B. '0.1.0', '0.2.0'
    change_type     TEXT NOT NULL CHECK (change_type IN (
                        'feature',    -- Neues Feature
                        'fix',        -- Bugfix
                        'refactor',   -- Code-Umbau
                        'schema',     -- Schema-Änderung
                        'security',   -- Sicherheits-Fix
                        'performance',-- Performance-Verbesserung
                        'docs',       -- Dokumentation
                        'breaking'    -- Breaking Change
                    )),
    title           TEXT NOT NULL,
    description     TEXT NOT NULL,
    -- Betroffene Module
    affected_modules UUID[] DEFAULT '{}',
    affected_files  TEXT[] DEFAULT '{}',
    -- Wer / Was hat die Änderung gemacht
    author          TEXT NOT NULL DEFAULT 'system',
    -- Rollback-Info falls es schiefgeht
    rollback_sql    TEXT,
    rollback_steps  TEXT,
    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Append-Only Schutz: Changelog darf nie gelöscht oder geändert werden
CREATE OR REPLACE FUNCTION dbai_knowledge.protect_changelog()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Changelog-Einträge dürfen NIEMALS gelöscht werden';
    END IF;
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'Changelog-Einträge sind unveränderlich';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_protect_changelog ON dbai_knowledge.changelog;
CREATE TRIGGER trg_protect_changelog
    BEFORE UPDATE OR DELETE ON dbai_knowledge.changelog
    FOR EACH ROW EXECUTE FUNCTION dbai_knowledge.protect_changelog();

CREATE INDEX IF NOT EXISTS idx_changelog_version ON dbai_knowledge.changelog(version);
CREATE INDEX IF NOT EXISTS idx_changelog_type ON dbai_knowledge.changelog(change_type);
CREATE INDEX IF NOT EXISTS idx_changelog_created ON dbai_knowledge.changelog(created_at DESC);

-- =============================================================================
-- TABELLE: architecture_decisions (ADR)
-- Warum wurde was wie gebaut? Kontext geht nie verloren.
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_knowledge.architecture_decisions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    adr_number      SERIAL,
    title           TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'accepted' CHECK (status IN (
                        'proposed', 'accepted', 'deprecated', 'superseded'
                    )),
    -- ADR-Felder
    context         TEXT NOT NULL,      -- Warum ist die Entscheidung nötig?
    decision        TEXT NOT NULL,      -- Was wurde entschieden?
    consequences    TEXT,               -- Welche Folgen hat das?
    alternatives    JSONB DEFAULT '[]', -- Was wurde NICHT gewählt und warum?
    -- Betroffene Module
    affected_modules UUID[] DEFAULT '{}',
    -- Wer hat entschieden
    decided_by      TEXT DEFAULT 'system',
    superseded_by   UUID REFERENCES dbai_knowledge.architecture_decisions(id),
    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_adr_updated ON dbai_knowledge.architecture_decisions;
CREATE TRIGGER trg_adr_updated
    BEFORE UPDATE ON dbai_knowledge.architecture_decisions
    FOR EACH ROW EXECUTE FUNCTION dbai_core.update_timestamp();

CREATE INDEX IF NOT EXISTS idx_adr_status ON dbai_knowledge.architecture_decisions(status);

-- =============================================================================
-- TABELLE: system_glossary
-- Begriffsdefinitionen — damit Mensch und KI dieselbe Sprache sprechen
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_knowledge.system_glossary (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    term            TEXT NOT NULL UNIQUE,
    definition      TEXT NOT NULL,
    context         TEXT,               -- In welchem Kontext wird der Begriff benutzt
    examples        TEXT[],             -- Beispiele
    related_terms   TEXT[] DEFAULT '{}',
    see_also        UUID[] DEFAULT '{}', -- Verweise auf andere Glossar-Einträge
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_glossary_term ON dbai_knowledge.system_glossary(term);

-- =============================================================================
-- TABELLE: known_issues
-- Bekannte Probleme und deren Status — für proaktive Fehlerbehebung
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_knowledge.known_issues (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title           TEXT NOT NULL,
    description     TEXT NOT NULL,
    severity        TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    status          TEXT NOT NULL DEFAULT 'open' CHECK (status IN (
                        'open', 'in_progress', 'resolved', 'wont_fix', 'workaround'
                    )),
    -- Kontext
    affected_modules UUID[] DEFAULT '{}',
    affected_files  TEXT[] DEFAULT '{}',
    -- Lösung
    workaround      TEXT,
    resolution      TEXT,
    resolution_date TIMESTAMPTZ,
    -- Verknüpfung zu Error-Patterns
    error_pattern_id UUID,   -- FK wird in 12-error-patterns.sql gesetzt
    -- Metadaten
    reproducible    BOOLEAN DEFAULT TRUE,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_issues_updated ON dbai_knowledge.known_issues;
CREATE TRIGGER trg_issues_updated
    BEFORE UPDATE ON dbai_knowledge.known_issues
    FOR EACH ROW EXECUTE FUNCTION dbai_core.update_timestamp();

CREATE INDEX IF NOT EXISTS idx_issues_severity ON dbai_knowledge.known_issues(severity);
CREATE INDEX IF NOT EXISTS idx_issues_status ON dbai_knowledge.known_issues(status);

-- =============================================================================
-- TABELLE: build_log
-- Dokumentiert jeden Build / jede Installation
-- =============================================================================
CREATE TABLE IF NOT EXISTS dbai_knowledge.build_log (
    id              BIGSERIAL PRIMARY KEY,
    build_type      TEXT NOT NULL CHECK (build_type IN (
                        'initial_install', 'schema_migration',
                        'c_compile', 'pip_install', 'bootstrap',
                        'backup', 'restore', 'upgrade'
                    )),
    success         BOOLEAN NOT NULL,
    duration_ms     INTEGER,
    -- Was wurde gebaut/installiert
    description     TEXT NOT NULL,
    -- Output/Logs
    stdout          TEXT,
    stderr          TEXT,
    exit_code       INTEGER,
    -- System-Kontext zum Zeitpunkt des Builds
    system_info     JSONB DEFAULT '{}',  -- OS, Python-Version, pg-Version, etc.
    -- Timestamps
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_build_type ON dbai_knowledge.build_log(build_type);
CREATE INDEX IF NOT EXISTS idx_build_success ON dbai_knowledge.build_log(success);
CREATE INDEX IF NOT EXISTS idx_build_started ON dbai_knowledge.build_log(started_at DESC);

-- =============================================================================
-- VIEWS — Wissensdatenbank-Abfragen
-- =============================================================================

-- View: Vollständiges Modul-Verzeichnis (ersetzt README-Struktur)
CREATE OR REPLACE VIEW dbai_knowledge.vw_module_overview AS
SELECT
    m.file_path,
    m.category,
    m.language,
    m.description,
    m.status,
    m.is_critical,
    m.boot_order,
    m.version,
    m.provides,
    m.depends_on,
    COALESCE(array_length(m.provides, 1), 0) AS provides_count,
    COALESCE(array_length(m.depends_on, 1), 0) AS dependency_count,
    (SELECT COUNT(*) FROM dbai_knowledge.module_dependencies d
     WHERE d.source_id = m.id OR d.target_id = m.id) AS relation_count
FROM dbai_knowledge.module_registry m
ORDER BY m.boot_order NULLS LAST, m.category, m.file_path;

-- View: Fehlende Dokumentation erkennen
CREATE OR REPLACE VIEW dbai_knowledge.vw_undocumented_modules AS
SELECT
    m.file_path,
    m.category,
    m.description,
    CASE
        WHEN m.documentation IS NULL THEN 'Keine Doku'
        WHEN LENGTH(m.documentation) < 50 THEN 'Zu kurz'
        ELSE 'OK'
    END AS doc_status,
    CASE
        WHEN m.content_hash IS NULL THEN 'Nicht verifiziert'
        WHEN m.last_verified IS NULL THEN 'Nie verifiziert'
        WHEN m.last_verified < NOW() - INTERVAL '7 days' THEN 'Veraltet'
        ELSE 'Aktuell'
    END AS verification_status
FROM dbai_knowledge.module_registry m
WHERE m.documentation IS NULL
   OR LENGTH(m.documentation) < 50
   OR m.last_verified IS NULL
   OR m.last_verified < NOW() - INTERVAL '7 days'
ORDER BY m.is_critical DESC, m.category;

-- View: System-Gesundheitsübersicht
CREATE OR REPLACE VIEW dbai_knowledge.vw_system_health AS
SELECT
    (SELECT COUNT(*) FROM dbai_knowledge.module_registry WHERE status = 'active') AS active_modules,
    (SELECT COUNT(*) FROM dbai_knowledge.module_registry WHERE status = 'broken') AS broken_modules,
    (SELECT COUNT(*) FROM dbai_knowledge.known_issues WHERE status = 'open') AS open_issues,
    (SELECT COUNT(*) FROM dbai_knowledge.known_issues WHERE severity = 'critical' AND status = 'open') AS critical_issues,
    (SELECT COUNT(*) FROM dbai_knowledge.changelog) AS total_changes,
    (SELECT MAX(created_at) FROM dbai_knowledge.changelog) AS last_change,
    (SELECT COUNT(*) FROM dbai_knowledge.build_log WHERE success = FALSE) AS failed_builds,
    (SELECT COUNT(*) FROM dbai_knowledge.architecture_decisions WHERE status = 'accepted') AS active_adrs;

-- View: Boot-Reihenfolge (welche Dateien werden in welcher Reihenfolge geladen)
CREATE OR REPLACE VIEW dbai_knowledge.vw_boot_sequence AS
SELECT
    m.boot_order,
    m.file_path,
    m.category,
    m.description,
    m.is_critical,
    m.provides,
    m.depends_on
FROM dbai_knowledge.module_registry m
WHERE m.boot_order IS NOT NULL
ORDER BY m.boot_order;

-- =============================================================================
-- FUNKTIONEN — Wissensabfragen
-- =============================================================================

-- Funktion: Was passiert wenn Modul X ausfällt?
CREATE OR REPLACE FUNCTION dbai_knowledge.impact_analysis(p_file_path TEXT)
RETURNS TABLE (
    affected_module TEXT,
    dependency_type TEXT,
    is_critical BOOLEAN,
    depth INTEGER
) AS $$
    WITH RECURSIVE impact AS (
        -- Direkte Abhängigkeiten
        SELECT
            m2.file_path AS affected_module,
            d.dependency_type,
            m2.is_critical,
            1 AS depth
        FROM dbai_knowledge.module_registry m1
        JOIN dbai_knowledge.module_dependencies d ON m1.id = d.target_id
        JOIN dbai_knowledge.module_registry m2 ON d.source_id = m2.id
        WHERE m1.file_path = p_file_path

        UNION ALL

        -- Transitive Abhängigkeiten
        SELECT
            m3.file_path,
            d2.dependency_type,
            m3.is_critical,
            impact.depth + 1
        FROM impact
        JOIN dbai_knowledge.module_registry m_prev ON m_prev.file_path = impact.affected_module
        JOIN dbai_knowledge.module_dependencies d2 ON m_prev.id = d2.target_id
        JOIN dbai_knowledge.module_registry m3 ON d2.source_id = m3.id
        WHERE impact.depth < 5
    )
    SELECT DISTINCT affected_module, dependency_type, is_critical, depth
    FROM impact
    ORDER BY depth, affected_module;
$$ LANGUAGE SQL STABLE;

-- Funktion: Vollständige Systemzusammenfassung (JSON)
-- Generiert eine "README" on-the-fly aus der DB
CREATE OR REPLACE FUNCTION dbai_knowledge.generate_system_report()
RETURNS JSONB AS $$
    SELECT jsonb_build_object(
        'generated_at', NOW(),
        'system', jsonb_build_object(
            'name', 'DBAI — Tabellenbasiertes KI-Betriebssystem',
            'version', (SELECT MAX(version) FROM dbai_knowledge.changelog),
            'description', 'Betriebssystem auf PostgreSQL als Kern. Jeder Systemzustand ist eine Tabellenzeile.'
        ),
        'modules', (
            SELECT jsonb_agg(jsonb_build_object(
                'path', file_path,
                'category', category,
                'description', description,
                'status', status,
                'critical', is_critical
            ) ORDER BY boot_order NULLS LAST, category)
            FROM dbai_knowledge.module_registry WHERE status = 'active'
        ),
        'health', (
            SELECT row_to_json(h)::jsonb FROM dbai_knowledge.vw_system_health h
        ),
        'open_issues', (
            SELECT COALESCE(jsonb_agg(jsonb_build_object(
                'title', title,
                'severity', severity,
                'status', status,
                'workaround', workaround
            ) ORDER BY
                CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                              WHEN 'medium' THEN 2 ELSE 3 END
            ), '[]'::jsonb)
            FROM dbai_knowledge.known_issues WHERE status NOT IN ('resolved', 'wont_fix')
        ),
        'recent_changes', (
            SELECT COALESCE(jsonb_agg(jsonb_build_object(
                'version', version,
                'type', change_type,
                'title', title,
                'date', created_at
            ) ORDER BY created_at DESC), '[]'::jsonb)
            FROM (SELECT * FROM dbai_knowledge.changelog ORDER BY created_at DESC LIMIT 20) recent
        ),
        'architecture_decisions', (
            SELECT COALESCE(jsonb_agg(jsonb_build_object(
                'adr', adr_number,
                'title', title,
                'status', status,
                'decision', LEFT(decision, 200)
            ) ORDER BY adr_number), '[]'::jsonb)
            FROM dbai_knowledge.architecture_decisions WHERE status = 'accepted'
        )
    );
$$ LANGUAGE SQL STABLE;

-- Funktion: Module nach Stichwort suchen (Fuzzy)
CREATE OR REPLACE FUNCTION dbai_knowledge.search_modules(p_query TEXT)
RETURNS TABLE (
    file_path TEXT,
    category TEXT,
    description TEXT,
    relevance REAL
) AS $$
    SELECT
        m.file_path,
        m.category,
        m.description,
        GREATEST(
            similarity(m.file_path, p_query),
            similarity(m.description, p_query),
            similarity(COALESCE(m.documentation, ''), p_query)
        ) AS relevance
    FROM dbai_knowledge.module_registry m
    WHERE m.file_path % p_query
       OR m.description ILIKE '%' || p_query || '%'
       OR m.documentation ILIKE '%' || p_query || '%'
       OR p_query = ANY(m.provides)
    ORDER BY relevance DESC
    LIMIT 20;
$$ LANGUAGE SQL STABLE;

-- Funktion: Abhängigkeitskette eines Moduls
CREATE OR REPLACE FUNCTION dbai_knowledge.get_dependency_chain(p_file_path TEXT)
RETURNS TABLE (
    module_path TEXT,
    dep_type TEXT,
    depth INTEGER
) AS $$
    WITH RECURSIVE chain AS (
        SELECT
            m2.file_path AS module_path,
            d.dependency_type AS dep_type,
            1 AS depth
        FROM dbai_knowledge.module_registry m1
        JOIN dbai_knowledge.module_dependencies d ON m1.id = d.source_id
        JOIN dbai_knowledge.module_registry m2 ON d.target_id = m2.id
        WHERE m1.file_path = p_file_path

        UNION ALL

        SELECT
            m3.file_path,
            d2.dependency_type,
            chain.depth + 1
        FROM chain
        JOIN dbai_knowledge.module_registry m_cur ON m_cur.file_path = chain.module_path
        JOIN dbai_knowledge.module_dependencies d2 ON m_cur.id = d2.source_id
        JOIN dbai_knowledge.module_registry m3 ON d2.target_id = m3.id
        WHERE chain.depth < 10
    )
    SELECT DISTINCT module_path, dep_type, depth
    FROM chain
    ORDER BY depth, module_path;
$$ LANGUAGE SQL STABLE;

-- =============================================================================
-- KOMMENTARE
-- =============================================================================
COMMENT ON SCHEMA dbai_knowledge IS 'Living Documentation — README als Datenbank, Fehler→Lösung, Architektur-Entscheidungen';
COMMENT ON TABLE dbai_knowledge.module_registry IS 'Jede DBAI-Datei als dokumentierte Zeile mit Abhängigkeiten und Status';
COMMENT ON TABLE dbai_knowledge.module_dependencies IS 'Gerichteter Abhängigkeitsgraph zwischen DBAI-Modulen';
COMMENT ON TABLE dbai_knowledge.changelog IS 'Append-only Änderungshistorie des gesamten Systems';
COMMENT ON TABLE dbai_knowledge.architecture_decisions IS 'Architecture Decision Records — warum wurde was wie gebaut';
COMMENT ON TABLE dbai_knowledge.system_glossary IS 'Begriffsdefinitionen damit Mensch und KI dieselbe Sprache sprechen';
COMMENT ON TABLE dbai_knowledge.known_issues IS 'Bekannte Probleme mit Lösungen für proaktive Fehlerbehebung';
COMMENT ON TABLE dbai_knowledge.build_log IS 'Build- und Installationshistorie mit Kontext';
COMMENT ON FUNCTION dbai_knowledge.impact_analysis IS 'Analyse: welche Module sind betroffen wenn Modul X ausfällt';
COMMENT ON FUNCTION dbai_knowledge.generate_system_report IS 'Generiert komplette System-README als JSON on-the-fly';
COMMENT ON FUNCTION dbai_knowledge.search_modules IS 'Fuzzy-Suche über alle registrierten Module';
COMMENT ON FUNCTION dbai_knowledge.get_dependency_chain IS 'Ermittelt die vollständige Abhängigkeitskette eines Moduls';
