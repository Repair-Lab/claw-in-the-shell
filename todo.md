# DBAI — Aufgaben & Status (von Rick verifiziert, 27.08.2026)

> ⚠️ Diese todo.md wurde am 27.08.2026 durch einen Code-Audit ersetzt.
> Die alte Version listete 6 "KRITISCH" Items als offen, die im Code ALLE
> bereits gefixt waren. Status unten = Code-geprüft, nicht README-Annahme.

## ERLEDIGT (verifiziert im Code, 27.08.2026)
| # | Fix | Ort | Status |
|---|---|---|---|
| 1 | Shell-Injection /api/services/install | server.py | ✅ 0× shell=True, 74× subprocess alle Args-basiert |
| 2 | Shell-Injection /api/terminal/exec | server.py | ✅ require_admin + shell=False |
| 3 | SQL-Injection SQL Explorer | server.py | ✅ Spaltenvalidierung vs information_schema |
| 4 | SQL Explorer RLS-Bypass | server.py | ✅ Runtime-Pool (db_query_rt) |
| 5 | SHA-256 unsalted | server.py | ✅ pgcrypto crypt()/gen_salt (bcrypt) |
| 6 | User-CRUD ohne Admin-Check | server.py | ✅ require_admin auf alle Endpoints |
| 7 | Pool-Race Condition | server.py DBPool | ✅ Lock + Checkout/Checkin + Health-Ping |
| 11 | Fehlende RLS (ui/llm/knowledge/net/workshop) | schema/71 | ✅ RLS vollständig |
| 12 | Health-Check nur DB | server.py /api/health | ✅ DB + Disk + Memory + LLM |
| 13 | 50+ except:pass | server.py | ✅ nur 8× |
| 15 | Rate-Limiter Memory-Leak | server.py | ✅ Hard-Cap 200 + Cleanup |
| 16 | Vacuum-Config fehlend | schema/71 §7 | ✅ alle Schemas |
| 18 | sessions.expires_at Index | schema/71 §6 | ✅ |
| 22 | Cookie Secure-Flag | server.py | ✅ env-gesteuert (DBAI_TLS_PROXY) |
| 23 | AbortController api.js | frontend/src/api.js | ✅ signal-Passthrough |

## ERLEDIGT (Phase 1, Rick, 27.08.2026, Branch rick/phase1-fixes)
| # | Fix | Ort | Status |
|---|---|---|---|
| A | API-Key-Test brach bei Fernet-Keys (base64.b64decode) | server.py llm_provider_test | ✅ decrypt_secret mit Legacy-Fallback |
| A2 | decrypt_secret crashte bei Legacy-Base64-Keys | server.py | ✅ 3-stufiger Fallback (Fernet→Base64→Klartext) |
| B | Version-Chaos (0.12.0/0.14.3) | server.py:793/:6512 | ✅ einheitlich 0.14.3 |
| E | PostgreSQL-Port 0.0.0.0 | docker-compose.yml | ✅ 127.0.0.1 only |
| F | Doppelte Schema-29 | schema/ | ✅ 29-new-apps-registration → 80-new-apps-registration |
| C | todo.md veraltet | todo.md | ✅ durch diesen Stand ersetzt |
| T | Regression-Test für Key-Dekodierung | tests/test_crypto_compat.py | ✅ neu |

## OFFEN (Phase 2 — siehe PLAN.md)
| # | Problem | Ort | Impact |
|---|---|---|---|
| D | server.py = 12.806 Zeilen God Object, 306× except Exception | web/server.py | Wartbarkeit |
| G | Kein Responsive Design (0× @media) | frontend/src/styles/global.css | Mobile |
| H | /opt/models hardcoded | server.py:6700 | Portabilität |
| 21 | API-Version in 3 Stellen (nun 0.14.3, aber keine Single-Source) | server.py | Wartbarkeit |

## OFFEN (Phase 3)
- Pydantic-Modelle für Request/Response-Bodies
- ruff + black in CI
- OpenAPI-Doku vervollständigen
- p95-Latenz-Profiling LLM-Endpoints

## TESTSTATUS (27.08.2026)
- 181 Unit-Tests (test_core 142, test_api 15, test_schema 11, test_settings 13) = ALLE GRÜN
- tests/test_crypto_compat.py = neu, Phase-1-Regressionsschutz
