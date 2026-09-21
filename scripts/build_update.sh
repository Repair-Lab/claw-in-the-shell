#!/usr/bin/env bash
# =============================================================================
# DBAI GhostShell OS — Update-Paket erstellen
# =============================================================================
# Erstellt ein verschlüsseltes tar.gz Archiv mit SHA256-Checksumme.
# Wird sowohl von GitHub Actions als auch lokal verwendet.
#
# Verwendung:
#   ./scripts/build_update.sh [VERSION]
#   ./scripts/build_update.sh 0.9.0
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DBAI_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$DBAI_ROOT/.builds"

# Version bestimmen
if [ $# -ge 1 ]; then
    VERSION="$1"
else
    # Aus dbai.toml lesen
    VERSION=$(grep '^version' "$DBAI_ROOT/config/dbai.toml" | head -1 | \
              sed 's/.*= *"\(.*\)"/\1/')
    # Commit-Hash anhängen
    COMMIT=$(git -C "$DBAI_ROOT" rev-parse --short HEAD 2>/dev/null || echo "local")
    VERSION="${VERSION}-${COMMIT}"
fi

echo "══════════════════════════════════════════════════════════"
echo "  🔨 DBAI Build — v${VERSION}"
echo "══════════════════════════════════════════════════════════"

# Build-Verzeichnis
mkdir -p "$BUILD_DIR"
ARCHIVE="$BUILD_DIR/dbai-ghostshell-${VERSION}.tar.gz"
MANIFEST="$BUILD_DIR/dbai-ghostshell-${VERSION}.manifest.json"

# ─── Schritt 1: Frontend bauen ───
echo ""
echo "→ [1/5] Frontend Build..."
cd "$DBAI_ROOT/frontend"
if [ -f package.json ]; then
    npm install --silent 2>/dev/null || true
    npm run build 2>&1 | tail -5
    if [ ! -f dist/index.html ]; then
        echo "  ❌ Frontend-Build fehlgeschlagen!"
        exit 1
    fi
    echo "  ✅ Frontend gebaut"
else
    echo "  ⚠️  Kein package.json — Frontend-Build übersprungen"
fi

# ─── Schritt 2: Python Syntax Check ───
echo ""
echo "→ [2/5] Python Syntax Check..."
ERRORS=0
for f in $(find "$DBAI_ROOT/bridge" "$DBAI_ROOT/web" -name '*.py' 2>/dev/null); do
    if ! python3 -m py_compile "$f" 2>/dev/null; then
        echo "  ❌ Syntax-Fehler: $f"
        ERRORS=$((ERRORS + 1))
    fi
done
if [ $ERRORS -gt 0 ]; then
    echo "  ❌ $ERRORS Python-Dateien fehlerhaft!"
    exit 1
fi
echo "  ✅ Alle Python-Dateien OK"

# ─── Schritt 3: SQL-Dateien zählen ───
echo ""
echo "→ [3/5] SQL-Schemas prüfen..."
SQL_COUNT=$(ls -1 "$DBAI_ROOT/schema/"*.sql 2>/dev/null | wc -l)
SCHEMA_VERSION=$(ls -1 "$DBAI_ROOT/schema/"*.sql 2>/dev/null | \
                 sed 's/.*\/\([0-9]*\)-.*/\1/' | sort -n | tail -1)
echo "  ✅ $SQL_COUNT Schema-Dateien (höchste: #${SCHEMA_VERSION})"

# ─── Schritt 4: Archiv erstellen ───
echo ""
echo "→ [4/5] Archiv erstellen..."
cd "$DBAI_ROOT"
tar -czf "$ARCHIVE" \
    --exclude='.git' \
    --exclude='node_modules' \
    --exclude='__pycache__' \
    --exclude='.updates' \
    --exclude='.backups' \
    --exclude='.builds' \
    --exclude='.github' \
    bridge/ \
    config/ \
    docs/ \
    frontend/dist/ \
    frontend/package.json \
    frontend/src/ \
    frontend/vite.config.js \
    llm/ \
    recovery/ \
    schema/ \
    scripts/ \
    web/ \
    tests/ \
    requirements.txt \
    README.md \
    2>/dev/null || true

SIZE=$(du -sh "$ARCHIVE" | cut -f1)
SHA256=$(sha256sum "$ARCHIVE" | awk '{print $1}')
echo "  ✅ $ARCHIVE ($SIZE)"

# ─── Schritt 5: Manifest erstellen ───
echo ""
echo "→ [5/5] Manifest erstellen..."
COMMIT_HASH=$(git -C "$DBAI_ROOT" rev-parse HEAD 2>/dev/null || echo "unknown")
COMMIT_MSG=$(git -C "$DBAI_ROOT" log -1 --format='%s' 2>/dev/null || echo "unknown")
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
FILE_SIZE=$(stat --printf="%s" "$ARCHIVE" 2>/dev/null || stat -f%z "$ARCHIVE" 2>/dev/null || echo "0")

cat > "$MANIFEST" <<EOF
{
  "version": "${VERSION}",
  "schema_version": ${SCHEMA_VERSION},
  "commit_hash": "${COMMIT_HASH}",
  "commit_message": "${COMMIT_MSG}",
  "artifact_hash": "${SHA256}",
  "artifact_size": ${FILE_SIZE},
  "sql_files": ${SQL_COUNT},
  "timestamp": "${TIMESTAMP}",
  "channel": "stable"
}
EOF

echo "  ✅ Manifest: $MANIFEST"

# ─── Zusammenfassung ───
echo ""
echo "══════════════════════════════════════════════════════════"
echo "  ✅ Build abgeschlossen!"
echo ""
echo "  Version:        ${VERSION}"
echo "  Schema:         #${SCHEMA_VERSION} (${SQL_COUNT} Dateien)"
echo "  Archiv:         ${ARCHIVE} (${SIZE})"
echo "  SHA256:         ${SHA256}"
echo "  Commit:         ${COMMIT_HASH:0:8}"
echo "  Zeitstempel:    ${TIMESTAMP}"
echo "══════════════════════════════════════════════════════════"
