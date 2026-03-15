-- =============================================================================
-- DBAI Schema 00: Extensions
-- Alle benötigten PostgreSQL-Erweiterungen
-- =============================================================================

-- Vektor-Extension für KI-Gedanken und Erinnerungen
CREATE EXTENSION IF NOT EXISTS vector;

-- UUID-Generierung (keine manuellen Dateipfade, nur IDs)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Kryptographische Funktionen
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Statistiken für Query-Analyse
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Zeitbasierte Trigger für Hardware-Monitoring
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Volltextsuche
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- =============================================================================
-- Schemas erstellen
-- =============================================================================

-- Haupt-Schema: Alle Core-Tabellen
CREATE SCHEMA IF NOT EXISTS dbai_core;

-- System-Schema: Hardware-Live-Werte
CREATE SCHEMA IF NOT EXISTS dbai_system;

-- Event-Schema: Hardware-Interrupts und Events
CREATE SCHEMA IF NOT EXISTS dbai_event;

-- Vektor-Schema: KI-Erinnerungen
CREATE SCHEMA IF NOT EXISTS dbai_vector;

-- Journal-Schema: Append-Only Logs (NIEMALS löschen)
CREATE SCHEMA IF NOT EXISTS dbai_journal;

-- Panic-Schema: Notfall-Reparatur (schreibgeschützt nach Init)
CREATE SCHEMA IF NOT EXISTS dbai_panic;

-- LLM-Schema: In-Database LLM Funktionen
CREATE SCHEMA IF NOT EXISTS dbai_llm;

-- =============================================================================
-- Rollen erstellen (Row-Level Security)
-- =============================================================================

-- System-Rolle: Voller Zugriff auf Core und System
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'dbai_system') THEN
        CREATE ROLE dbai_system LOGIN;
    END IF;
END $$;

-- Monitor-Rolle: Nur Lesen von System-Tabellen
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'dbai_monitor') THEN
        CREATE ROLE dbai_monitor LOGIN;
    END IF;
END $$;

-- LLM-Rolle: Zugriff nur auf zugewiesene Zeilen
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'dbai_llm') THEN
        CREATE ROLE dbai_llm LOGIN;
    END IF;
END $$;

-- Recovery-Rolle: Zugriff auf Panic-Schema und Journale
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'dbai_recovery') THEN
        CREATE ROLE dbai_recovery LOGIN;
    END IF;
END $$;

-- Schema-Berechtigungen
GRANT USAGE ON SCHEMA dbai_core TO dbai_system, dbai_llm;
GRANT USAGE ON SCHEMA dbai_system TO dbai_system, dbai_monitor;
GRANT USAGE ON SCHEMA dbai_event TO dbai_system, dbai_monitor;
GRANT USAGE ON SCHEMA dbai_vector TO dbai_system, dbai_llm;
GRANT USAGE ON SCHEMA dbai_journal TO dbai_system, dbai_recovery;
GRANT USAGE ON SCHEMA dbai_panic TO dbai_system, dbai_recovery;
GRANT USAGE ON SCHEMA dbai_llm TO dbai_system, dbai_llm;
