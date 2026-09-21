#!/usr/bin/env python3
"""
DBAI App Manager — Software Catalog, Browser Automation, Email Bridge, OAuth.

Das Rad nicht neu erfinden. Existierende Programme fernsteuern:
  - Browser via Playwright (Headless Chromium)
  - E-Mails via IMAP/SMTP → inbox/outbox Tabellen
  - Apps via Package Manager (APT, pip, npm, GitHub)
  - OAuth fuer Google, Drive, Gmail

Jede App ist ein Datenstrom in einer Tabelle — die KI sieht Daten, nicht Pixel.

Usage:
    python3 -m bridge.app_manager --scan-packages
    python3 -m bridge.app_manager --browse https://github.com/trending
    python3 -m bridge.app_manager --sync-email
    python3 -m bridge.app_manager --daemon
"""

import os
import sys
import json
import time
import signal
import logging
import argparse
import subprocess
import select
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Tuple

try:
    import psycopg2
    import psycopg2.extras
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

try:
    import imaplib
    import smtplib
    import email
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    HAS_EMAIL = True
except ImportError:
    HAS_EMAIL = False

logger = logging.getLogger("dbai.app_manager")


class SoftwareCatalog:
    """App Store als Repository-Tabelle.

    Die KI scannt Paketquellen und speichert Metadaten in software_catalog.
    Installation laeuft ueber die task_queue.
    """

    def __init__(self, conn):
        self.conn = conn

    def scan_apt(self, category: str = "utility") -> Dict:
        """Scannt installierte APT-Pakete und registriert sie im Katalog."""
        try:
            result = subprocess.run(
                ["dpkg-query", "-W", "-f",
                 "${Package}\t${Version}\t${Installed-Size}\t${Description}\n"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                return {"error": "dpkg-query fehlgeschlagen"}

            registered = 0
            for line in result.stdout.strip().split("\n"):
                parts = line.split("\t", 3)
                if len(parts) < 4:
                    continue
                pkg_name, version, size_kb, desc = parts

                with self.conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO dbai_core.software_catalog
                            (package_name, display_name, description, version,
                             source_type, install_state, install_size_mb, category)
                        VALUES (%s, %s, %s, %s, 'apt', 'installed', %s, %s)
                        ON CONFLICT (package_name, source_type) DO UPDATE
                        SET version = EXCLUDED.version,
                            install_state = 'installed',
                            updated_at = NOW()
                    """, (
                        pkg_name, pkg_name, desc[:500], version,
                        round(int(size_kb or 0) / 1024, 1), category
                    ))
                registered += 1

            self.conn.commit()
            logger.info(f"APT-Scan: {registered} Pakete registriert")
            return {"source": "apt", "registered": registered}

        except Exception as e:
            self.conn.rollback()
            return {"error": str(e)}

    def scan_pip(self) -> Dict:
        """Scannt installierte pip-Pakete."""
        try:
            result = subprocess.run(
                ["pip", "list", "--format=json"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                return {"error": "pip list fehlgeschlagen"}

            packages = json.loads(result.stdout)
            registered = 0

            for pkg in packages:
                with self.conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO dbai_core.software_catalog
                            (package_name, display_name, version,
                             source_type, install_state, category)
                        VALUES (%s, %s, %s, 'pip', 'installed', 'development')
                        ON CONFLICT (package_name, source_type) DO UPDATE
                        SET version = EXCLUDED.version,
                            install_state = 'installed',
                            updated_at = NOW()
                    """, (pkg["name"], pkg["name"], pkg.get("version", "")))
                registered += 1

            self.conn.commit()
            logger.info(f"pip-Scan: {registered} Pakete registriert")
            return {"source": "pip", "registered": registered}

        except Exception as e:
            self.conn.rollback()
            return {"error": str(e)}

    def scan_github_trending(self, language: str = "python") -> Dict:
        """Registriert Trending-Repos von GitHub im Katalog (ohne API-Key)."""
        # Nutzt github.com/trending direkt — oder die GitHub API wenn Key vorhanden
        try:
            result = subprocess.run(
                ["curl", "-s", f"https://api.github.com/search/repositories?"
                 f"q=language:{language}&sort=stars&per_page=20"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                return {"error": "GitHub API nicht erreichbar"}

            data = json.loads(result.stdout)
            items = data.get("items", [])
            registered = 0

            for repo in items:
                with self.conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO dbai_core.software_catalog
                            (package_name, display_name, description, version,
                             source_type, source_url, category, stars,
                             license, homepage, install_state,
                             install_command, tags)
                        VALUES (%s, %s, %s, %s, 'github', %s, %s, %s, %s, %s,
                                'available', %s, %s)
                        ON CONFLICT (package_name, source_type) DO UPDATE
                        SET stars = EXCLUDED.stars,
                            description = EXCLUDED.description,
                            updated_at = NOW()
                    """, (
                        repo["full_name"],
                        repo["name"],
                        (repo.get("description") or "")[:500],
                        repo.get("default_branch", "main"),
                        repo["html_url"],
                        "ai_ml" if language == "python" else "development",
                        repo.get("stargazers_count", 0),
                        repo.get("license", {}).get("name") if repo.get("license") else None,
                        repo.get("homepage"),
                        f"git clone {repo['clone_url']}",
                        repo.get("topics", [])[:10],
                    ))
                registered += 1

            self.conn.commit()
            logger.info(f"GitHub-Scan ({language}): {registered} Repos registriert")
            return {"source": "github", "language": language, "registered": registered}

        except Exception as e:
            self.conn.rollback()
            return {"error": str(e)}

    def install_package(self, package_name: str, source_type: str = "apt") -> Dict:
        """Installiert ein Paket via task_queue (nicht direkt!)."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT dbai_core.install_software(%s, %s)",
                (package_name, source_type)
            )
            task_id = cur.fetchone()[0]
        self.conn.commit()
        return {"package": package_name, "source": source_type, "task_id": str(task_id)}


class BrowserAutomation:
    """Headless-Browser-Steuerung via Playwright.

    Die KI "sieht" die Webseite als Text/DOM in einer Tabelle
    und kann fuer den Nutzer surfen, Formulare ausfuellen, Daten extrahieren.
    """

    def __init__(self, conn):
        self.conn = conn
        self.browser = None
        self.context = None

    def _ensure_browser(self):
        """Startet Playwright-Browser wenn noetig."""
        if not HAS_PLAYWRIGHT:
            raise ImportError(
                "Playwright nicht installiert. Installiere mit:\n"
                "  pip install playwright && playwright install chromium"
            )
        if self.browser is None:
            self._pw = sync_playwright().start()
            self.browser = self._pw.chromium.launch(headless=True)
            self.context = self.browser.new_context(
                user_agent="DBAI-TabulaOS/0.6 (Ghost Browser Automation)"
            )

    def open_url(self, url: str, session_name: str = None,
                 ghost_id: str = None) -> Dict:
        """Oeffnet eine URL und extrahiert den Seiteninhalt.

        Gibt den Inhalt als strukturierte Daten zurueck — die KI sieht
        Text und Links, nicht Pixel.
        """
        self._ensure_browser()

        page = self.context.new_page()
        try:
            page.goto(url, timeout=30000, wait_until="domcontentloaded")

            title = page.title()
            text = page.inner_text("body")[:50000]  # Max 50KB Text

            # Links extrahieren
            links = page.evaluate("""
                () => Array.from(document.querySelectorAll('a[href]'))
                    .slice(0, 50)
                    .map(a => ({text: a.innerText.trim().slice(0, 100), href: a.href}))
            """)

            # Formulare extrahieren
            forms = page.evaluate("""
                () => Array.from(document.querySelectorAll('form'))
                    .slice(0, 10)
                    .map(f => ({
                        action: f.action,
                        method: f.method,
                        inputs: Array.from(f.querySelectorAll('input,textarea,select'))
                            .slice(0, 20)
                            .map(i => ({name: i.name, type: i.type, placeholder: i.placeholder}))
                    }))
            """)

            load_time = page.evaluate("window.performance.timing.loadEventEnd - window.performance.timing.navigationStart")

            # In DB speichern
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO dbai_core.browser_sessions
                        (session_name, url, page_title, page_text,
                         page_links, page_forms, state, load_time_ms, ghost_id)
                    VALUES (%s, %s, %s, %s, %s, %s, 'loaded', %s, %s)
                    RETURNING id
                """, (
                    session_name or f"browse_{url[:50]}",
                    url, title, text[:10000],
                    json.dumps(links), json.dumps(forms),
                    load_time, ghost_id
                ))
                session_id = cur.fetchone()[0]
            self.conn.commit()

            result = {
                "session_id": str(session_id),
                "url": url,
                "title": title,
                "text_length": len(text),
                "links_count": len(links),
                "forms_count": len(forms),
                "load_time_ms": load_time,
            }
            logger.info(f"URL geladen: {url} → {title}")
            return result

        except Exception as e:
            logger.error(f"Browser-Fehler: {url}: {e}")
            return {"error": str(e), "url": url}
        finally:
            page.close()

    def extract_text(self, url: str) -> str:
        """Extrahiert nur den Text einer Webseite."""
        self._ensure_browser()
        page = self.context.new_page()
        try:
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            return page.inner_text("body")[:50000]
        finally:
            page.close()

    def close(self):
        """Browser schliessen."""
        if self.browser:
            self.browser.close()
            self._pw.stop()
            self.browser = None


class EmailBridge:
    """E-Mail-Integration: IMAP/SMTP → inbox/outbox Tabellen.

    E-Mails werden als Zeilen geladen. Der Ghost liest die inbox-Tabelle,
    fasst zusammen und schreibt Entwuerfe direkt in die outbox.
    """

    def __init__(self, conn):
        self.conn = conn

    def sync_inbox(self, account_name: str, max_messages: int = 50) -> Dict:
        """Synchronisiert die Inbox eines E-Mail-Accounts."""
        if not HAS_EMAIL:
            return {"error": "Email-Module nicht verfuegbar"}

        # Account-Daten laden
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT ea.*, ak.api_key_preview
                FROM dbai_event.email_accounts ea
                LEFT JOIN dbai_core.api_keys ak ON ak.id = ea.credentials_ref
                WHERE ea.account_name = %s
            """, (account_name,))
            account = cur.fetchone()

        if not account:
            return {"error": f"Account '{account_name}' nicht gefunden"}

        # Account-Status aktualisieren
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE dbai_event.email_accounts
                SET sync_state = 'syncing', last_sync = NOW()
                WHERE account_name = %s
            """, (account_name,))
        self.conn.commit()

        try:
            # IMAP verbinden (echte Credentials von API-Key-Vault holen)
            # In Produktion: pgcrypto entschluesseln
            imap = imaplib.IMAP4_SSL(account["imap_host"], account["imap_port"])
            # Login mit gespeicherten Credentials
            # imap.login(email, password)  # In Produktion

            # Fuer Demo: Status setzen
            synced = 0
            result = {
                "account": account_name,
                "status": "connected",
                "synced": synced,
                "message": "IMAP-Verbindung erfolgreich. "
                           "Credentials werden in Produktion aus dem API-Key-Vault geladen."
            }

            with self.conn.cursor() as cur:
                cur.execute("""
                    UPDATE dbai_event.email_accounts
                    SET sync_state = 'idle'
                    WHERE account_name = %s
                """, (account_name,))
            self.conn.commit()

            return result

        except Exception as e:
            with self.conn.cursor() as cur:
                cur.execute("""
                    UPDATE dbai_event.email_accounts
                    SET sync_state = 'error'
                    WHERE account_name = %s
                """, (account_name,))
            self.conn.commit()
            return {"error": str(e), "account": account_name}

    def send_email(self, account_name: str, to: List[str],
                   subject: str, body: str,
                   reply_to_id: str = None) -> Dict:
        """Erstellt einen E-Mail-Entwurf in der outbox."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT dbai_event.send_email(%s, %s, %s, %s, %s, 'ghost')
            """, (account_name, to, subject, body, reply_to_id))
            outbox_id = cur.fetchone()[0]
        self.conn.commit()
        return {"outbox_id": str(outbox_id), "state": "review"}

    def search_inbox(self, query: str, limit: int = 20,
                     account_name: str = None) -> List[Dict]:
        """Durchsucht die Inbox."""
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM dbai_event.search_inbox(%s, %s, %s)
            """, (query, limit, account_name))
            return [dict(r) for r in cur.fetchall()]


class OAuthManager:
    """OAuth-Verbindungen verwalten (Google, GitHub, etc.)."""

    PROVIDERS = {
        "google": {
            "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "scopes": [
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/drive.readonly",
                "https://www.googleapis.com/auth/calendar.readonly",
            ],
        },
        "github": {
            "auth_url": "https://github.com/login/oauth/authorize",
            "token_url": "https://github.com/login/oauth/access_token",
            "scopes": ["repo", "user:email"],
        },
    }

    def __init__(self, conn):
        self.conn = conn

    def get_auth_url(self, provider: str, redirect_uri: str) -> str:
        """Generiert eine OAuth-Autorisierungs-URL."""
        if provider not in self.PROVIDERS:
            raise ValueError(f"Unbekannter Provider: {provider}")

        config = self.PROVIDERS[provider]
        scopes = " ".join(config["scopes"])
        return (
            f"{config['auth_url']}?"
            f"client_id=YOUR_CLIENT_ID&"
            f"redirect_uri={redirect_uri}&"
            f"response_type=code&"
            f"scope={scopes}&"
            f"access_type=offline"
        )

    def register_connection(self, provider: str, display_name: str,
                             email: str = None) -> str:
        """Registriert eine neue OAuth-Verbindung."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO dbai_core.oauth_connections
                    (provider, display_name, email, is_connected)
                VALUES (%s, %s, %s, FALSE)
                RETURNING id
            """, (provider, display_name, email))
            conn_id = cur.fetchone()[0]
        self.conn.commit()
        return str(conn_id)

    def list_connections(self) -> List[Dict]:
        """Listet alle OAuth-Verbindungen."""
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM dbai_core.vw_oauth_status")
            return [dict(r) for r in cur.fetchall()]


class AppManagerDaemon:
    """Haupt-Daemon fuer das App-Ecosystem.

    Hoert auf NOTIFY-Events und fuehrt Aktionen aus:
    - software_install → Package installieren
    - browser_action → URL oeffnen und extrahieren
    - email_outbox → E-Mail senden
    - user_command → Nutzer-Befehl interpretieren
    """

    def __init__(self, db_dsn: str = "dbname=dbai"):
        self.db_dsn = db_dsn
        self.conn = None
        self.running = False
        self.catalog = None
        self.browser = None
        self.email = None
        self.oauth = None

    def connect(self):
        """DB-Verbindung und Module initialisieren."""
        if not HAS_PSYCOPG2:
            raise ImportError("psycopg2 nicht installiert")
        self.conn = psycopg2.connect(self.db_dsn)
        self.conn.autocommit = False

        self.catalog = SoftwareCatalog(self.conn)
        self.browser = BrowserAutomation(self.conn)
        self.email = EmailBridge(self.conn)
        self.oauth = OAuthManager(self.conn)

        logger.info("App Manager Daemon: DB verbunden")

    def disconnect(self):
        """Ressourcen freigeben."""
        if self.browser:
            self.browser.close()
        if self.conn:
            self.conn.close()

    def _setup_listeners(self):
        """LISTEN fuer relevante Channels."""
        self.conn.autocommit = True
        with self.conn.cursor() as cur:
            for ch in ["software_install", "browser_action",
                       "email_outbox", "user_command"]:
                cur.execute(f"LISTEN {ch};")
        logger.info("App Manager: Event-Listener registriert")

    def _handle_notify(self, channel: str, payload: str):
        """Event verarbeiten."""
        try:
            data = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            data = {"raw": payload}

        logger.info(f"Event: {channel}")

        try:
            self.conn.autocommit = False

            if channel == "software_install":
                pkg = data.get("package", "")
                src = data.get("source", "apt")
                logger.info(f"Software-Installation: {pkg} ({src})")
                # In Produktion: subprocess ausfuehren

            elif channel == "browser_action":
                url = data.get("url", "")
                session_id = data.get("session_id")
                if url:
                    result = self.browser.open_url(url)
                    logger.info(f"Browser: {url} → {result.get('title', '?')}")

            elif channel == "email_outbox":
                outbox_id = data.get("outbox_id")
                logger.info(f"E-Mail zum Senden: {outbox_id}")

        except Exception as e:
            logger.error(f"Event-Handler-Fehler ({channel}): {e}")
            self.conn.rollback()

    def daemon_loop(self, interval_s: int = 10):
        """Hauptschleife des App Managers."""
        self.running = True
        signal.signal(signal.SIGINT, lambda s, f: setattr(self, "running", False))
        signal.signal(signal.SIGTERM, lambda s, f: setattr(self, "running", False))

        self._setup_listeners()
        logger.info("App Manager Daemon gestartet")

        while self.running:
            try:
                self.conn.autocommit = True
                if select.select([self.conn], [], [], interval_s) != ([], [], []):
                    self.conn.poll()
                    while self.conn.notifies:
                        notify = self.conn.notifies.pop(0)
                        self._handle_notify(notify.channel, notify.payload)
            except Exception as e:
                logger.error(f"Daemon-Fehler: {e}")
                time.sleep(5)
                try:
                    self.conn.close()
                except Exception:
                    pass
                try:
                    self.connect()
                    self._setup_listeners()
                except Exception:
                    time.sleep(30)

        logger.info("App Manager Daemon gestoppt")


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="DBAI App Manager — Software, Browser, Email, OAuth",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  # Installierte APT-Pakete erfassen
  %(prog)s --scan-packages

  # URL im Headless-Browser oeffnen
  %(prog)s --browse https://github.com/trending

  # E-Mail-Inbox synchronisieren
  %(prog)s --sync-email main

  # GitHub Trending scannen
  %(prog)s --scan-github python

  # Daemon-Modus (auf Events warten)
  %(prog)s --daemon
        """
    )
    parser.add_argument("--daemon", action="store_true",
                        help="Daemon-Modus: Auf Events warten")
    parser.add_argument("--scan-packages", action="store_true",
                        help="Installierte Pakete (APT+pip) scannen")
    parser.add_argument("--scan-github", metavar="LANG", default=None,
                        help="GitHub Trending scannen (z.B. python)")
    parser.add_argument("--browse", metavar="URL",
                        help="URL im Headless-Browser oeffnen")
    parser.add_argument("--sync-email", metavar="ACCOUNT",
                        help="E-Mail-Inbox synchronisieren")
    parser.add_argument("--search-email", metavar="QUERY",
                        help="Inbox durchsuchen")
    parser.add_argument("--oauth-status", action="store_true",
                        help="OAuth-Verbindungen anzeigen")
    parser.add_argument("--db", default="dbname=dbai",
                        help="PostgreSQL DSN")
    parser.add_argument("--json", action="store_true",
                        help="Ausgabe als JSON")
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    )

    mgr = AppManagerDaemon(args.db)
    try:
        mgr.connect()

        if args.daemon:
            print("╔═══════════════════════════════════════════╗")
            print("║  DBAI App Manager v0.6.0                 ║")
            print("║  Browser • E-Mail • Apps • OAuth          ║")
            print("║  Jede App ist ein Datenstrom.             ║")
            print("╚═══════════════════════════════════════════╝")
            mgr.daemon_loop()

        elif args.scan_packages:
            apt_result = mgr.catalog.scan_apt()
            pip_result = mgr.catalog.scan_pip()
            result = {"apt": apt_result, "pip": pip_result}
            if args.json:
                print(json.dumps(result, indent=2, default=str))
            else:
                print(f"APT: {apt_result.get('registered', 0)} Pakete")
                print(f"pip: {pip_result.get('registered', 0)} Pakete")

        elif args.scan_github:
            result = mgr.catalog.scan_github_trending(args.scan_github)
            if args.json:
                print(json.dumps(result, indent=2, default=str))
            else:
                print(f"GitHub ({args.scan_github}): "
                      f"{result.get('registered', 0)} Repos")

        elif args.browse:
            result = mgr.browser.open_url(args.browse)
            if args.json:
                print(json.dumps(result, indent=2, default=str))
            else:
                print(f"Titel: {result.get('title', '?')}")
                print(f"Text:  {result.get('text_length', 0)} Zeichen")
                print(f"Links: {result.get('links_count', 0)}")
                print(f"Forms: {result.get('forms_count', 0)}")
                print(f"Zeit:  {result.get('load_time_ms', 0)}ms")

        elif args.sync_email:
            result = mgr.email.sync_inbox(args.sync_email)
            print(json.dumps(result, indent=2, default=str))

        elif args.search_email:
            results = mgr.email.search_inbox(args.search_email)
            for r in results:
                print(f"  [{r.get('auto_priority', '?'):>6}] "
                      f"{r.get('from_address', '?'):<30} "
                      f"{r.get('subject', '')[:60]}")

        elif args.oauth_status:
            conns = mgr.oauth.list_connections()
            for c in conns:
                print(f"  [{c['provider']:>10}] {c['display_name']:<20} "
                      f"{'✓' if c['is_connected'] else '✗'} "
                      f"({c.get('token_status', '?')})")

        else:
            parser.print_help()

    except KeyboardInterrupt:
        print("\nApp Manager gestoppt.")
    except Exception as e:
        logger.error(f"Fehler: {e}")
        sys.exit(1)
    finally:
        mgr.disconnect()


if __name__ == "__main__":
    main()
