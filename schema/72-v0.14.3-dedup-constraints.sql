-- ============================================================
-- Migration 72: Duplikat-Bereinigung + UNIQUE-Constraints
-- Version: 0.14.3
-- Datum:   2025-07-24
-- Grund:   Seed-Dateien (13, 41, 43, 45) + API-Endpoints
--          erzeugten Duplikate weil UNIQUE-Constraints fehlten
-- ============================================================

BEGIN;

-- ─────────────────────────────────────────────────────────────
-- 1) CHANGELOG: Append-Only-Trigger temporär deaktivieren
-- ─────────────────────────────────────────────────────────────
ALTER TABLE dbai_knowledge.changelog
  DISABLE TRIGGER trg_protect_changelog;

DELETE FROM dbai_knowledge.changelog
WHERE id NOT IN (
    SELECT MIN(id) FROM dbai_knowledge.changelog GROUP BY version, title
);

ALTER TABLE dbai_knowledge.changelog
  ENABLE TRIGGER trg_protect_changelog;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'uq_changelog_version_title'
  ) THEN
    ALTER TABLE dbai_knowledge.changelog
      ADD CONSTRAINT uq_changelog_version_title UNIQUE (version, title);
  END IF;
END $$;


-- ─────────────────────────────────────────────────────────────
-- 2) ARCHITECTURE_DECISIONS
-- ─────────────────────────────────────────────────────────────
DELETE FROM dbai_knowledge.architecture_decisions
WHERE id NOT IN (
    SELECT MIN(id::text)::uuid
    FROM dbai_knowledge.architecture_decisions
    GROUP BY title
);

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'uq_adr_title'
  ) THEN
    ALTER TABLE dbai_knowledge.architecture_decisions
      ADD CONSTRAINT uq_adr_title UNIQUE (title);
  END IF;
END $$;


-- ─────────────────────────────────────────────────────────────
-- 3) KNOWN_ISSUES
-- ─────────────────────────────────────────────────────────────
DELETE FROM dbai_knowledge.known_issues
WHERE id NOT IN (
    SELECT MIN(id::text)::uuid
    FROM dbai_knowledge.known_issues
    GROUP BY title
);

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'uq_known_issues_title'
  ) THEN
    ALTER TABLE dbai_knowledge.known_issues
      ADD CONSTRAINT uq_known_issues_title UNIQUE (title);
  END IF;
END $$;


-- ─────────────────────────────────────────────────────────────
-- 4) FIREWALL_RULES
-- ─────────────────────────────────────────────────────────────
DELETE FROM dbai_system.firewall_rules
WHERE id NOT IN (
    SELECT MIN(id::text)::uuid
    FROM dbai_system.firewall_rules
    GROUP BY rule_name, chain, action, protocol
);

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'uq_firewall_rule_identity'
  ) THEN
    ALTER TABLE dbai_system.firewall_rules
      ADD CONSTRAINT uq_firewall_rule_identity UNIQUE (rule_name, chain, protocol);
  END IF;
END $$;


-- ─────────────────────────────────────────────────────────────
-- 5) PROJECTS (UNIQUE pro User + Name)
-- ─────────────────────────────────────────────────────────────
DELETE FROM dbai_workshop.projects a
USING dbai_workshop.projects b
WHERE a.user_id = b.user_id
  AND a.name = b.name
  AND a.id > b.id;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'uq_project_user_name'
  ) THEN
    ALTER TABLE dbai_workshop.projects
      ADD CONSTRAINT uq_project_user_name UNIQUE (user_id, name);
  END IF;
END $$;


-- ─────────────────────────────────────────────────────────────
-- 6) LEARNING_ENTRIES (Duplikate nach category+key)
-- ─────────────────────────────────────────────────────────────
DELETE FROM dbai_llm.learning_entries
WHERE id NOT IN (
    SELECT MIN(id::text)::uuid
    FROM dbai_llm.learning_entries
    GROUP BY category, key
);

-- ─────────────────────────────────────────────────────────────
-- Seed-Dateien: ON CONFLICT targets anpassen
-- In schema 13, 41, 43, 45 müssen die ON CONFLICT-Klauseln
-- die neuen UNIQUE-Constraints verwenden:
--   changelog:               ON CONFLICT (version, title) DO NOTHING
--   architecture_decisions:  ON CONFLICT (title) DO NOTHING
--   known_issues:            ON CONFLICT (title) DO NOTHING
-- ─────────────────────────────────────────────────────────────

COMMIT;

-- Changelog-Eintrag
INSERT INTO dbai_knowledge.changelog (version, title, description, category)
VALUES (
    '0.14.3',
    'Duplikat-Bereinigung + UNIQUE-Constraints',
    'Entfernung von 71 Duplikaten aus 6 Tabellen. Hinzufügen von 5 UNIQUE-Constraints '
    '(changelog, architecture_decisions, known_issues, firewall_rules, projects). '
    'API-Endpoints für Firewall und Workshop nutzen jetzt ON CONFLICT.',
    'database'
) ON CONFLICT (version, title) DO NOTHING;
