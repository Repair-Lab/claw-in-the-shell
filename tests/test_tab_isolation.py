#!/usr/bin/env python3
"""Test Tab-Isolation: Beweist dass jeder Tab ein eigener Rechner ist."""
import urllib.request, json, sys

BASE = "http://localhost:3000"

def api(method, path, data=None, headers=None):
    h = headers or {}
    h["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{BASE}{path}", data=json.dumps(data).encode() if data else None, headers=h, method=method)
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

if __name__ == '__main__':
    # Login
    tok = api("POST", "/api/auth/login", {"username":"root","password":"dbai2026"}).get("token")
    if not tok:
        print("FEHLER: Login fehlgeschlagen")
        sys.exit(1)
    print(f"Login OK")

    h = {"Authorization": f"Bearer {tok}"}

    # Register 2 Tabs
    t1 = api("POST", "/api/tabs/register", {"tab_id":"iso-test-A"}, h)
    print(f"Tab A: hostname={t1.get('hostname')}, label={t1.get('label')}")

    t2 = api("POST", "/api/tabs/register", {"tab_id":"iso-test-B"}, h)
    print(f"Tab B: hostname={t2.get('hostname')}, label={t2.get('label')}")

    # Open terminal in Tab A
    api("POST", "/api/windows/open/terminal", None, {**h, "X-Tab-Id": "iso-test-A"})
    print("Terminal in Tab A geoeffnet")

    # Desktop Tab A
    d1 = api("GET", "/api/desktop", None, {**h, "X-Tab-Id": "iso-test-A"})
    w1 = len(d1.get("windows", []))
    h1 = d1.get("tab", {}).get("hostname", "?")

    # Desktop Tab B
    d2 = api("GET", "/api/desktop", None, {**h, "X-Tab-Id": "iso-test-B"})
    w2 = len(d2.get("windows", []))
    h2 = d2.get("tab", {}).get("hostname", "?")

    print(f"\n=== ISOLATION TEST ===")
    print(f"Tab A ({h1}): {w1} Fenster")
    print(f"Tab B ({h2}): {w2} Fenster")

    ok = w1 > 0 and w2 == 0 and h1 != h2
    print(f"Isolation: {'PASS' if ok else 'FAIL'}")

    # Tab-Liste
    tabs = api("GET", "/api/tabs", None, h)
    print(f"Aktive Tabs: {len(tabs)}")

    # Cleanup
    api("DELETE", f"/api/tabs/iso-test-A", None, h)
    api("DELETE", f"/api/tabs/iso-test-B", None, h)
    print("Cleanup done")

    sys.exit(0 if ok else 1)
