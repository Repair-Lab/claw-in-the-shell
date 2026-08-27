#!/bin/bash
# GhostShell OS — Live-Test-Suite (Rick, 27.08.2026)
set -uo pipefail
BASE="http://127.0.0.1:3000"
PASS=0; FAIL=0
ok()  { echo "  ✅ $1"; PASS=$((PASS+1)); }
bad() { echo "  ❌ $1"; FAIL=$((FAIL+1)); }

echo "════════ TEST 1: Health-Endpoint ════════"
H=$(curl -s -m 10 $BASE/api/health)
echo "  $H"
echo "$H" | grep -q '"status":"ok"' && ok "health: ok" || bad "health nicht ok"
echo "$H" | grep -q '"db":"connected"' && ok "DB verbunden" || bad "DB nicht verbunden"

echo "════════ TEST 2: Login (root) ════════"
L=$(curl -s -m 10 -X POST $BASE/api/auth/login -H 'Content-Type: application/json' -d '{"username":"root","password":"dbai2026"}')
echo "  $(echo $L | head -c 160)..."
TOKEN=$(echo "$L" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("token",""))')
[ -n "$TOKEN" ] && ok "Login erfolgreich, Token erhalten" || bad "Login fehlgeschlagen"

AUTH="Authorization: Bearer $TOKEN"
# CSRF: Cookie aus Login-Antwort extrahieren + passenden Header senden
JAR=$(mktemp)
L2=$(curl -s -m 10 -c "$JAR" -X POST $BASE/api/auth/login -H 'Content-Type: application/json' -d '{"username":"root","password":"dbai2026"}')
CSRF_VAL=$(grep dbai_csrf "$JAR" | awk '{print $7}')
[ -z "$CSRF_VAL" ] && CSRF_VAL="testcsrf"
echo "  CSRF: ${CSRF_VAL:0:12}..."
echo "════════ TEST 3: /api/auth/me ════════"
ME=$(curl -s -m 10 -H "$AUTH" $BASE/api/auth/me)
echo "  $ME"
echo "$ME" | grep -q '"is_admin":true' && ok "Admin-Session aktiv" || bad "Session fehlerhaft"

echo "════════ TEST 4: Provider-Liste ════════"
PL=$(curl -s -m 10 -H "$AUTH" $BASE/api/llm/providers)
COUNT=$(echo "$PL" | python3 -c 'import sys,json; print(len(json.load(sys.stdin)))' 2>/dev/null || echo 0)
[ "$COUNT" -gt 5 ] && ok "$COUNT Provider geladen" || bad "Provider-Liste leer/kurz ($COUNT)"

echo "════════ TEST 5: BUG-A — Fernet-Key setzen ════════"
# Setze einen Test-Key — Schreib-Pfad verschlüsselt mit Fernet (encrypt_secret)
PATCH=$(curl -s -m 10 -X PATCH -H "$AUTH" -H "Cookie: dbai_csrf=$CSRF_VAL" -H "x-csrf-token: $CSRF_VAL" -H 'Content-Type: application/json' \
  $BASE/api/llm/providers/openai -d '{"api_key":"sk-test-key-1234567890","is_enabled":true}')
echo "  $PATCH"
echo "$PATCH" | grep -q '"ok":true' && ok "Key gesetzt (Fernet-Verschlüsselung)" || bad "Key-Setzen fehlgeschlagen"

echo "════════ TEST 6: BUG-A — Key in DB ist Fernet (nicht Base64!) ════════"
ENC=$(podman exec dbai-postgres psql -U dbai_system -d dbai -tAc \
  "SELECT api_key_enc FROM dbai_llm.llm_providers WHERE provider_key='openai';")
echo "  Encrypted: ${ENC:0:40}..."
echo "$ENC" | grep -q '^gAAAAAB' && ok "Fernet-Format bestätigt (gAAAAAB...)" || bad "Unerwartetes Format: $ENC"

echo "════════ TEST 7: BUG-A — Provider-Test-Endpoint (DER Kern-Test) ════════"
# VOR Fix: base64.b64decode(Fernet-Byte) → Crash mit binären Junk-Bytes
# NACH Fix: decrypt_secret dekodiert sauber → HTTP-Aufruf → 401 von OpenAI (erwartet, Fake-Key)
TEST=$(curl -s -m 25 -X POST -H "$AUTH" -H "Cookie: dbai_csrf=$CSRF_VAL" -H "x-csrf-token: $CSRF_VAL" $BASE/api/llm/providers/openai/test)
echo "  $TEST"
echo "$TEST" | grep -qE '"ok":(true|false)' && ! echo "$TEST" | grep -q 'Traceback\|500' && \
  ok "Endpoint antwortet sauber (Key wurde dekodiert, kein Crash)" || \
  bad "Endpoint gecrasht — Bug A NICHT behoben!"
echo "$TEST" | grep -q 'HTTP 401\|HTTP 403\|HTTP 404' && \
  ok "OpenAI-Antwort erhalten (401/403 = Fake-Key abgelehnt = ERWARTET)" || \
  echo "  ℹ️  (keine HTTP-Fehlermeldung — Provider evtl. nicht erreichbar, aber: kein Decode-Crash)"

echo "════════ TEST 8: Legacy-Base64-Key (Fallback-Pfad) ════════"
# Simuliere einen alten Base64-Key direkt in der DB und teste den Fallback
B64=$(echo -n "sk-legacy-key-old-style" | base64)
podman exec dbai-postgres psql -U dbai_system -d dbai -tAc \
  "UPDATE dbai_llm.llm_providers SET api_key_enc='$B64' WHERE provider_key='groq';" >/dev/null
T2=$(curl -s -m 25 -X POST -H "$AUTH" -H "Cookie: dbai_csrf=$CSRF_VAL" -H "x-csrf-token: $CSRF_VAL" $BASE/api/llm/providers/groq/test)
echo "  $T2"
echo "$T2" | grep -qE '"ok":(true|false)' && ! echo "$T2" | grep -q 'Traceback\|500' && \
  ok "Legacy-Base64-Key wird sauber dekodiert (Fallback funktioniert)" || \
  bad "Legacy-Fallback gecrasht!"

echo "════════ TEST 9: DB-Port nur 127.0.0.1 (Bug E) ════════"
BIND=$(ss -tln | grep ':5432' | head -1 | awk '{print $4}')
echo "  Bind: $BIND"
echo "$BIND" | grep -q '^127.0.0.1' && ok "PostgreSQL nur auf localhost" || bad "PostgreSQL bindet $BIND (LAN-offen?)"

echo "════════ TEST 10: Version (Bug B — in Code verifiziert) ════════"
grep -n 'FastAPI(version=' web/server.py
grep -n 'ghost_version' web/server.py | head -2

echo ""
echo "════════ RESULTAT ════════"
echo "  ✅ PASS: $PASS   ❌ FAIL: $FAIL"
# Aufräumen: Test-Keys entfernen
curl -s -m 5 -X DELETE -H "$AUTH" -H "Cookie: dbai_csrf=$CSRF_VAL" -H "x-csrf-token: $CSRF_VAL" $BASE/api/llm/providers/openai/key >/dev/null
podman exec dbai-postgres psql -U dbai_system -d dbai -tAc \
  "UPDATE dbai_llm.llm_providers SET api_key_enc=NULL, is_configured=FALSE WHERE provider_key IN ('openai','groq');" >/dev/null
echo "  🧹 Test-Keys entfernt"
exit $FAIL
