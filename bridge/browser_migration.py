#!/usr/bin/env python3
"""
DBAI Browser Migration — Feature 11
====================================
Chrome/Firefox Bookmarks + History + Passwörter → ghost_knowledge_base
Ghost kann Lesezeichen "lesen" und kontextuell nutzen.

Unterstützte Browser:
- Chrome / Chromium / Brave / Edge / Vivaldi / Opera (Chromium-basiert)
- Firefox (SQLite Places DB)
"""

import os
import json
import sqlite3
import hashlib
import logging
import shutil
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger("dbai.browser_migration")

# ─── Browser Profile Pfade ───────────────────────────────────────────────────

CHROME_PATHS = {
    "chrome": [
        Path.home() / ".config/google-chrome",
        Path.home() / ".config/google-chrome-beta",
    ],
    "chromium": [
        Path.home() / ".config/chromium",
    ],
    "brave": [
        Path.home() / ".config/BraveSoftware/Brave-Browser",
    ],
    "edge": [
        Path.home() / ".config/microsoft-edge",
    ],
    "vivaldi": [
        Path.home() / ".config/vivaldi",
    ],
    "opera": [
        Path.home() / ".config/opera",
    ],
}

FIREFOX_PATHS = [
    Path.home() / ".mozilla/firefox",
    Path.home() / "snap/firefox/common/.mozilla/firefox",
]

# Chrome epoch: 1601-01-01 UTC
CHROME_EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)


def chrome_time_to_datetime(microseconds: int) -> Optional[datetime]:
    """Chrome-Timestamp (Mikrosekunden seit 1601-01-01) → Python datetime."""
    if not microseconds or microseconds <= 0:
        return None
    try:
        return CHROME_EPOCH + timedelta(microseconds=microseconds)
    except (OverflowError, OSError):
        return None


def firefox_time_to_datetime(microseconds: int) -> Optional[datetime]:
    """Firefox/Places-Timestamp (Mikrosekunden seit Unix-Epoch) → Python datetime."""
    if not microseconds or microseconds <= 0:
        return None
    try:
        return datetime.fromtimestamp(microseconds / 1_000_000, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


class BrowserMigrator:
    """Importiert Browser-Daten in die DBAI-Datenbank."""

    def __init__(self, db_execute, db_query):
        self.db_execute = db_execute
        self.db_query = db_query

    # ── Scanner ──────────────────────────────────────────────────────────

    def scan_browsers(self) -> list:
        """Alle installierten Browser-Profile finden."""
        profiles = []

        # Chromium-basierte Browser
        for browser_type, paths in CHROME_PATHS.items():
            for base_path in paths:
                if not base_path.exists():
                    continue
                # Standard-Profile
                for profile_dir in base_path.iterdir():
                    if not profile_dir.is_dir():
                        continue
                    if profile_dir.name.startswith("Profile ") or profile_dir.name == "Default":
                        bookmarks_file = profile_dir / "Bookmarks"
                        history_file = profile_dir / "History"
                        if bookmarks_file.exists() or history_file.exists():
                            profiles.append({
                                "browser_type": browser_type,
                                "profile_name": profile_dir.name,
                                "profile_path": str(profile_dir),
                                "has_bookmarks": bookmarks_file.exists(),
                                "has_history": history_file.exists(),
                                "has_passwords": (profile_dir / "Login Data").exists(),
                            })

        # Firefox
        for firefox_base in FIREFOX_PATHS:
            if not firefox_base.exists():
                continue
            profiles_ini = firefox_base / "profiles.ini"
            if profiles_ini.exists():
                # Parse profiles.ini
                current_section = {}
                for line in profiles_ini.read_text(errors="replace").splitlines():
                    line = line.strip()
                    if line.startswith("[Profile"):
                        if current_section.get("Path"):
                            profile_path = firefox_base / current_section["Path"]
                            if profile_path.exists():
                                profiles.append({
                                    "browser_type": "firefox",
                                    "profile_name": current_section.get("Name", "Default"),
                                    "profile_path": str(profile_path),
                                    "has_bookmarks": (profile_path / "places.sqlite").exists(),
                                    "has_history": (profile_path / "places.sqlite").exists(),
                                    "has_passwords": (profile_path / "logins.json").exists(),
                                })
                        current_section = {}
                    elif "=" in line:
                        key, val = line.split("=", 1)
                        current_section[key.strip()] = val.strip()
                # Letztes Profil
                if current_section.get("Path"):
                    profile_path = firefox_base / current_section["Path"]
                    if profile_path.exists():
                        profiles.append({
                            "browser_type": "firefox",
                            "profile_name": current_section.get("Name", "Default"),
                            "profile_path": str(profile_path),
                            "has_bookmarks": (profile_path / "places.sqlite").exists(),
                            "has_history": (profile_path / "places.sqlite").exists(),
                            "has_passwords": (profile_path / "logins.json").exists(),
                        })

        logger.info(f"Gefunden: {len(profiles)} Browser-Profile")
        return profiles

    # ── Chrome/Chromium Bookmarks ────────────────────────────────────────

    def _import_chrome_bookmarks(self, profile_id: str, profile_path: str) -> int:
        """Chrome/Chromium Bookmarks (JSON) importieren."""
        bookmarks_file = Path(profile_path) / "Bookmarks"
        if not bookmarks_file.exists():
            return 0

        try:
            data = json.loads(bookmarks_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"Bookmarks-Parse-Fehler: {e}")
            return 0

        count = 0
        roots = data.get("roots", {})
        for root_name, root_data in roots.items():
            if isinstance(root_data, dict):
                count += self._walk_chrome_bookmarks(profile_id, root_data, f"/{root_name}")
        return count

    def _walk_chrome_bookmarks(self, profile_id: str, node: dict, folder_path: str) -> int:
        """Rekursiv Chrome-Bookmarks durchlaufen."""
        count = 0
        if node.get("type") == "url":
            url = node.get("url", "")
            title = node.get("name", url)
            date_added = chrome_time_to_datetime(int(node.get("date_added", 0)))

            self.db_execute(
                """INSERT INTO dbai_core.browser_bookmarks
                   (profile_id, title, url, folder_path, date_added)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT DO NOTHING""",
                (profile_id, title, url, folder_path, date_added)
            )
            count += 1
        elif node.get("type") == "folder":
            children = node.get("children", [])
            subfolder = f"{folder_path}/{node.get('name', 'Unnamed')}"
            for child in children:
                count += self._walk_chrome_bookmarks(profile_id, child, subfolder)
        return count

    # ── Chrome/Chromium History ──────────────────────────────────────────

    def _import_chrome_history(self, profile_id: str, profile_path: str, max_entries: int = 10000) -> int:
        """Chrome/Chromium History (SQLite) importieren."""
        history_file = Path(profile_path) / "History"
        if not history_file.exists():
            return 0

        # SQLite braucht eine Kopie (Browser lockt die DB)
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            shutil.copy2(history_file, tmp_path)
            conn = sqlite3.connect(f"file:{tmp_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.url, u.title, v.visit_time, v.visit_duration,
                       v.transition & 0xFF AS transition_type
                FROM visits v
                JOIN urls u ON v.url = u.id
                ORDER BY v.visit_time DESC
                LIMIT ?
            """, (max_entries,))

            count = 0
            for row in cursor:
                visit_time = chrome_time_to_datetime(row["visit_time"])
                if not visit_time:
                    continue
                transition_map = {0: "link", 1: "typed", 2: "auto_bookmark", 3: "auto_subframe",
                                  4: "manual_subframe", 5: "generated", 6: "auto_toplevel",
                                  7: "form_submit", 8: "reload"}
                transition = transition_map.get(row["transition_type"], "link")

                self.db_execute(
                    """INSERT INTO dbai_core.browser_history
                       (profile_id, url, title, visit_time, visit_duration, transition_type)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (profile_id, row["url"], row["title"], visit_time,
                     row["visit_duration"] // 1_000_000, transition)
                )
                count += 1

            conn.close()
            return count
        except Exception as e:
            logger.error(f"Chrome-History-Import-Fehler: {e}")
            return 0
        finally:
            os.unlink(tmp_path)

    # ── Firefox Bookmarks + History ──────────────────────────────────────

    def _import_firefox_places(self, profile_id: str, profile_path: str, max_history: int = 10000) -> tuple:
        """Firefox Places (Bookmarks + History aus places.sqlite)."""
        places_file = Path(profile_path) / "places.sqlite"
        if not places_file.exists():
            return 0, 0

        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            shutil.copy2(places_file, tmp_path)
            conn = sqlite3.connect(f"file:{tmp_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row

            # Bookmarks
            cursor = conn.cursor()
            cursor.execute("""
                SELECT b.title, p.url, b.dateAdded, b.parent,
                       (SELECT group_concat(bp.title, '/')
                        FROM moz_bookmarks bp
                        WHERE bp.id = b.parent) AS folder
                FROM moz_bookmarks b
                JOIN moz_places p ON b.fk = p.id
                WHERE b.type = 1 AND p.url NOT LIKE 'place:%'
            """)

            bm_count = 0
            for row in cursor:
                date_added = firefox_time_to_datetime(row["dateAdded"])
                folder = "/" + (row["folder"] or "Unsortiert")
                self.db_execute(
                    """INSERT INTO dbai_core.browser_bookmarks
                       (profile_id, title, url, folder_path, date_added)
                       VALUES (%s, %s, %s, %s, %s)
                       ON CONFLICT DO NOTHING""",
                    (profile_id, row["title"] or row["url"], row["url"], folder, date_added)
                )
                bm_count += 1

            # History
            cursor.execute("""
                SELECT p.url, p.title, h.visit_date, h.visit_type
                FROM moz_historyvisits h
                JOIN moz_places p ON h.place_id = p.id
                ORDER BY h.visit_date DESC
                LIMIT ?
            """, (max_history,))

            transition_map = {1: "link", 2: "typed", 3: "auto_bookmark",
                              4: "embed", 5: "redirect_permanent",
                              6: "redirect_temporary", 7: "download", 8: "framed_link"}

            hist_count = 0
            for row in cursor:
                visit_time = firefox_time_to_datetime(row["visit_date"])
                if not visit_time:
                    continue
                transition = transition_map.get(row["visit_type"], "link")
                self.db_execute(
                    """INSERT INTO dbai_core.browser_history
                       (profile_id, url, title, visit_time, transition_type)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (profile_id, row["url"], row["title"], visit_time, transition)
                )
                hist_count += 1

            conn.close()
            return bm_count, hist_count
        except Exception as e:
            logger.error(f"Firefox-Places-Import-Fehler: {e}")
            return 0, 0
        finally:
            os.unlink(tmp_path)

    # ── Import-Orchestrierung ────────────────────────────────────────────

    def import_profile(self, browser_type: str, profile_name: str, profile_path: str,
                       user_id: str = None) -> dict:
        """Ein Browser-Profil komplett importieren."""
        # Profil in DB anlegen
        rows = self.db_query(
            """INSERT INTO dbai_core.browser_profiles (browser_type, profile_name, profile_path, user_id)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (browser_type, profile_path) DO UPDATE SET imported_at = now()
               RETURNING id""",
            (browser_type, profile_name, profile_path, user_id)
        )
        profile_id = rows[0]["id"] if rows else None
        if not profile_id:
            return {"error": "Profil konnte nicht angelegt werden"}

        result = {"profile_id": str(profile_id), "browser": browser_type, "profile": profile_name}

        if browser_type == "firefox":
            bm, hist = self._import_firefox_places(str(profile_id), profile_path)
            result["bookmarks"] = bm
            result["history"] = hist
        else:
            result["bookmarks"] = self._import_chrome_bookmarks(str(profile_id), profile_path)
            result["history"] = self._import_chrome_history(str(profile_id), profile_path)

        # Zähler aktualisieren
        self.db_execute(
            """UPDATE dbai_core.browser_profiles
               SET bookmark_count = %s, history_count = %s
               WHERE id = %s""",
            (result.get("bookmarks", 0), result.get("history", 0), profile_id)
        )

        # In Ghost Knowledge Base überführen
        kb_count = self._populate_knowledge_base(str(profile_id))
        result["knowledge_base_entries"] = kb_count

        logger.info(f"Browser-Import abgeschlossen: {result}")
        return result

    def _populate_knowledge_base(self, profile_id: str) -> int:
        """Importierte Browser-Daten in die Ghost Knowledge Base überführen."""
        count = 0

        # Top-Bookmarks als Knowledge
        bookmarks = self.db_query(
            """SELECT id, title, url, folder_path, tags
               FROM dbai_core.browser_bookmarks
               WHERE profile_id = %s
               ORDER BY date_added DESC LIMIT 500""",
            (profile_id,)
        )
        for bm in bookmarks:
            self.db_execute(
                """INSERT INTO dbai_core.ghost_knowledge_base
                   (source_type, source_id, title, url, category, tags, metadata)
                   VALUES ('bookmark', %s, %s, %s, %s, %s, %s)
                   ON CONFLICT DO NOTHING""",
                (bm["id"], bm["title"], bm["url"], bm.get("folder_path", "/"),
                 bm.get("tags", []),
                 json.dumps({"folder": bm.get("folder_path", "/")}))
            )
            count += 1

        # Browser-Patterns als Knowledge
        patterns = self.db_query(
            "SELECT dbai_core.analyze_browser_patterns(%s) AS patterns",
            (profile_id,)
        )
        if patterns and patterns[0].get("patterns"):
            self.db_execute(
                """INSERT INTO dbai_core.ghost_knowledge_base
                   (source_type, title, content, category, tags, metadata)
                   VALUES ('browser_pattern', %s, %s, 'analytics', %s, %s)""",
                (f"Browser-Analyse Profil {profile_id}",
                 json.dumps(patterns[0]["patterns"], indent=2),
                 ["browser", "analytics", "pattern"],
                 json.dumps(patterns[0]["patterns"]))
            )
            count += 1

        return count

    def get_import_status(self) -> list:
        """Status aller importierten Profile."""
        return self.db_query(
            """SELECT id, browser_type, profile_name, profile_path,
                      bookmark_count, history_count, password_count,
                      imported_at, metadata
               FROM dbai_core.browser_profiles
               ORDER BY imported_at DESC"""
        )
