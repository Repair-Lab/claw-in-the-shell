-- =============================================================================
-- DBAI Schema 00: Schemas, Rollen & Extensions
-- MUSS fehlerfrei durchlaufen — alle Elemente sind idempotent
-- =============================================================================

-- =============================================================================
-- 1. Schemas erstellen (MUSS zuerst kommen — alles andere hängt davon ab)
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS dbai_core;
CREATE SCHEMA IF NOT EXISTS dbai_system;
CREATE SCHEMA IF NOT EXISTS dbai_event;
CREATE SCHEMA IF NOT EXISTS dbai_vector;
CREATE SCHEMA IF NOT EXISTS dbai_journal;
CREATE SCHEMA IF NOT EXISTS dbai_panic;
CREATE SCHEMA IF NOT EXISTS dbai_llm;
CREATE SCHEMA IF NOT EXISTS dbai_knowledge;
CREATE SCHEMA IF NOT EXISTS dbai_ui;
CREATE SCHEMA IF NOT EXISTS dbai_workshop;

-- =============================================================================
-- 2. Rollen erstellen (Row-Level Security)
-- =============================================================================

DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'dbai_system')   THEN CREATE ROLE dbai_system   LOGIN; END IF; END $$;
DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'dbai_monitor')  THEN CREATE ROLE dbai_monitor  LOGIN; END IF; END $$;
DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'dbai_llm')      THEN CREATE ROLE dbai_llm      LOGIN; END IF; END $$;
DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'dbai_recovery') THEN CREATE ROLE dbai_recovery LOGIN; END IF; END $$;
DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'dbai_runtime')  THEN CREATE ROLE dbai_runtime  LOGIN; END IF; END $$;

-- =============================================================================
-- 3. Schema-Berechtigungen
-- =============================================================================

GRANT USAGE ON SCHEMA dbai_core     TO dbai_system, dbai_llm;
GRANT USAGE ON SCHEMA dbai_system   TO dbai_system, dbai_monitor;
GRANT USAGE ON SCHEMA dbai_event    TO dbai_system, dbai_monitor;
GRANT USAGE ON SCHEMA dbai_vector   TO dbai_system, dbai_llm;
GRANT USAGE ON SCHEMA dbai_journal  TO dbai_system, dbai_recovery;
GRANT USAGE ON SCHEMA dbai_panic    TO dbai_system, dbai_recovery;
GRANT USAGE ON SCHEMA dbai_llm      TO dbai_system, dbai_llm;
GRANT USAGE ON SCHEMA dbai_knowledge TO dbai_system, dbai_llm;
GRANT USAGE ON SCHEMA dbai_ui       TO dbai_system, dbai_runtime;
GRANT USAGE ON SCHEMA dbai_workshop TO dbai_system, dbai_runtime;

-- =============================================================================
-- 4. Extensions (alle optional-safe — Fehler werden abgefangen)
-- =============================================================================

-- Pflicht-Extensions (in jedem PG16 verfügbar)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Vektor-Extension (pgvector muss installiert sein)
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'vector') THEN
        EXECUTE 'CREATE EXTENSION IF NOT EXISTS vector';
    ELSE
        RAISE NOTICE 'pgvector nicht verfügbar — wird übersprungen';
    END IF;
END $$;

-- Statistiken (in den meisten PG-Installationen verfügbar)
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'pg_stat_statements') THEN
        EXECUTE 'CREATE EXTENSION IF NOT EXISTS pg_stat_statements';
    ELSE
        RAISE NOTICE 'pg_stat_statements nicht verfügbar — wird übersprungen';
    END IF;
END $$;

-- Cron-Jobs (nur auf echten Servern, nicht in CI/Docker)
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'pg_cron') THEN
        EXECUTE 'CREATE EXTENSION IF NOT EXISTS pg_cron';
    ELSE
        RAISE NOTICE 'pg_cron nicht verfügbar — wird übersprungen (kein Problem für Basis-Betrieb)';
    END IF;
END $$;

-- Trigram-Suche
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'pg_trgm') THEN
        EXECUTE 'CREATE EXTENSION IF NOT EXISTS pg_trgm';
    ELSE
        RAISE NOTICE 'pg_trgm nicht verfügbar — wird übersprungen';
    END IF;
END $$;
