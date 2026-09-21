#!/bin/bash
# =============================================================================
# DBAI PostgreSQL — Docker Init Script
# =============================================================================
# Wird automatisch beim ersten Start des PostgreSQL-Containers ausgeführt.
# Erstellt Schemas, Rollen und lädt alle SQL-Dateien in sortierter Reihenfolge.
# =============================================================================

set -e

echo "══════════════════════════════════════════════════════════"
echo "  🗄️  DBAI PostgreSQL Initialisierung"
echo "══════════════════════════════════════════════════════════"

# Extensions aktivieren
psql -v ON_ERROR_STOP=0 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-'EOSQL'
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    CREATE EXTENSION IF NOT EXISTS pgcrypto;
    CREATE EXTENSION IF NOT EXISTS vector;
EOSQL

echo "  ✅ Extensions installiert"

# Runtime-User erstellen
psql -v ON_ERROR_STOP=0 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'dbai_runtime') THEN
            CREATE ROLE dbai_runtime WITH LOGIN PASSWORD 'dbai_runtime_2026';
        END IF;
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'dbai_monitor') THEN
            CREATE ROLE dbai_monitor WITH LOGIN PASSWORD 'dbai_monitor_2026';
        END IF;
    END
    \$\$;
EOSQL

echo "  ✅ Rollen erstellt"

# Alle Schema-Dateien in sortierter Reihenfolge laden
SCHEMA_DIR="/docker-entrypoint-initdb.d/schema"
if [ -d "$SCHEMA_DIR" ]; then
    echo "  📂 Lade Schema-Dateien..."
    ERRORS=0
    for f in $(ls "$SCHEMA_DIR"/*.sql 2>/dev/null | sort -V); do
        BASENAME=$(basename "$f")
        echo -n "    → $BASENAME ... "
        if psql -v ON_ERROR_STOP=0 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f "$f" > /dev/null 2>&1; then
            echo "OK"
        else
            echo "WARNUNG"
            ERRORS=$((ERRORS + 1))
        fi
    done
    echo "  ✅ $(($(ls "$SCHEMA_DIR"/*.sql 2>/dev/null | wc -l) - ERRORS)) von $(ls "$SCHEMA_DIR"/*.sql 2>/dev/null | wc -l) Schemas geladen"
fi

# Berechtigungen für Runtime-User
psql -v ON_ERROR_STOP=0 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-'EOSQL'
    -- Schemas
    GRANT USAGE ON SCHEMA dbai_core TO dbai_runtime, dbai_monitor;
    GRANT USAGE ON SCHEMA dbai_system TO dbai_runtime, dbai_monitor;
    GRANT USAGE ON SCHEMA dbai_ui TO dbai_runtime, dbai_monitor;
    GRANT USAGE ON SCHEMA dbai_vector TO dbai_runtime, dbai_monitor;
    GRANT USAGE ON SCHEMA dbai_llm TO dbai_runtime, dbai_monitor;
    GRANT USAGE ON SCHEMA dbai_knowledge TO dbai_runtime, dbai_monitor;

    -- Tabellen (SELECT für alle, INSERT/UPDATE für runtime)
    GRANT SELECT ON ALL TABLES IN SCHEMA dbai_core TO dbai_monitor;
    GRANT SELECT ON ALL TABLES IN SCHEMA dbai_system TO dbai_monitor;
    GRANT SELECT ON ALL TABLES IN SCHEMA dbai_ui TO dbai_monitor;
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA dbai_core TO dbai_runtime;
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA dbai_system TO dbai_runtime;
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA dbai_ui TO dbai_runtime;
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA dbai_vector TO dbai_runtime;
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA dbai_llm TO dbai_runtime;
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA dbai_knowledge TO dbai_runtime;

    -- Sequences
    GRANT USAGE ON ALL SEQUENCES IN SCHEMA dbai_core TO dbai_runtime;
    GRANT USAGE ON ALL SEQUENCES IN SCHEMA dbai_system TO dbai_runtime;
    GRANT USAGE ON ALL SEQUENCES IN SCHEMA dbai_ui TO dbai_runtime;
    GRANT USAGE ON ALL SEQUENCES IN SCHEMA dbai_vector TO dbai_runtime;
    GRANT USAGE ON ALL SEQUENCES IN SCHEMA dbai_llm TO dbai_runtime;
    GRANT USAGE ON ALL SEQUENCES IN SCHEMA dbai_knowledge TO dbai_runtime;
EOSQL

echo "  ✅ Berechtigungen gesetzt"
echo ""
echo "══════════════════════════════════════════════════════════"
echo "  ✅ DBAI Datenbank bereit!"
echo "══════════════════════════════════════════════════════════"
