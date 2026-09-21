#!/usr/bin/env python3
"""
DBAI Workspace Mapper — Feature 13
====================================
Vorhandene Dateien indexieren (ohne Kopie) → workspace_index Tabelle.
Integriert sich in den Setup-Wizard für initiales Scanning.
"""

import os
import hashlib
import mimetypes
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("dbai.workspace_mapper")

# ─── Konfiguration ───────────────────────────────────────────────────────

DEFAULT_SCAN_PATHS = [
    str(Path.home()),
    "/home",
]

IGNORE_DIRS = {
    ".git", ".svn", ".hg", "__pycache__", "node_modules", ".cache",
    ".local/share/Trash", ".Trash", "venv", ".venv", "env",
    ".npm", ".yarn", ".cargo", ".rustup", ".gradle",
    "snap", ".snap", ".wine", ".steam",
}

IGNORE_PREFIXES = {".", "~"}

MAX_HASH_SIZE = 50 * 1024 * 1024  # 50 MB max für Hash-Berechnung

# Programmiersprachen nach Extension
LANGUAGE_MAP = {
    ".py": "python", ".pyw": "python",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".rs": "rust",
    ".go": "go",
    ".java": "java", ".kt": "kotlin", ".kts": "kotlin",
    ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".r": "r", ".R": "r",
    ".lua": "lua",
    ".pl": "perl", ".pm": "perl",
    ".sh": "bash", ".bash": "bash", ".zsh": "zsh",
    ".sql": "sql",
    ".html": "html", ".htm": "html",
    ".css": "css", ".scss": "scss", ".sass": "sass", ".less": "less",
    ".xml": "xml", ".xsl": "xml",
    ".json": "json",
    ".yaml": "yaml", ".yml": "yaml",
    ".toml": "toml",
    ".md": "markdown", ".rst": "restructuredtext",
    ".tex": "latex",
    ".vim": "vim", ".el": "emacs-lisp",
    ".zig": "zig", ".nim": "nim", ".ex": "elixir", ".exs": "elixir",
    ".erl": "erlang", ".hs": "haskell", ".ml": "ocaml",
    ".dart": "dart", ".v": "v", ".jl": "julia",
    ".sol": "solidity", ".vy": "vyper",
    ".dockerfile": "dockerfile",
    ".tf": "terraform", ".hcl": "hcl",
}

# Datei-Kategorien
CATEGORY_MAP = {
    "code": {".py", ".js", ".jsx", ".ts", ".tsx", ".rs", ".go", ".java", ".c", ".h",
             ".cpp", ".cc", ".cs", ".rb", ".php", ".swift", ".kt", ".lua", ".pl",
             ".sh", ".bash", ".zsh", ".sql", ".r", ".ex", ".hs", ".dart", ".zig",
             ".nim", ".sol", ".jl", ".v", ".ml", ".erl", ".el", ".vim"},
    "document": {".md", ".rst", ".txt", ".doc", ".docx", ".pdf", ".odt", ".rtf",
                 ".tex", ".epub", ".pages"},
    "image": {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp", ".ico",
              ".tiff", ".psd", ".ai", ".raw", ".heic", ".avif"},
    "video": {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v",
              ".mpg", ".mpeg", ".3gp"},
    "audio": {".mp3", ".wav", ".flac", ".ogg", ".aac", ".wma", ".m4a", ".opus",
              ".mid", ".midi"},
    "archive": {".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".zst",
                ".tgz", ".deb", ".rpm"},
    "config": {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
               ".env", ".properties", ".xml"},
    "data": {".csv", ".tsv", ".parquet", ".arrow", ".sqlite", ".db", ".hdf5",
             ".npy", ".npz", ".pkl", ".feather"},
    "web": {".html", ".htm", ".css", ".scss", ".sass", ".less", ".wasm"},
    "model": {".gguf", ".onnx", ".pt", ".pth", ".h5", ".pb", ".safetensors",
              ".bin", ".ckpt"},
}

def _get_category(ext: str) -> str:
    """Datei-Kategorie nach Extension bestimmen."""
    ext_lower = ext.lower()
    for cat, exts in CATEGORY_MAP.items():
        if ext_lower in exts:
            return cat
    return "other"


def _count_lines(filepath: Path) -> Optional[int]:
    """Zeilenanzahl für Text-Dateien zählen."""
    try:
        if filepath.stat().st_size > 10 * 1024 * 1024:  # > 10 MB
            return None
        with open(filepath, "r", errors="replace") as f:
            return sum(1 for _ in f)
    except (OSError, UnicodeDecodeError):
        return None


def _file_hash(filepath: Path) -> Optional[str]:
    """SHA256-Hash einer Datei berechnen."""
    if filepath.stat().st_size > MAX_HASH_SIZE:
        return None
    try:
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


class WorkspaceMapper:
    """Indexiert Dateien im Filesystem ohne sie zu kopieren."""

    def __init__(self, db_execute, db_query):
        self.db_execute = db_execute
        self.db_query = db_query
        self._stats = {"files": 0, "dirs": 0, "errors": 0, "total_size": 0}

    def scan(self, paths: list = None, max_depth: int = 8,
             compute_hash: bool = False, count_lines: bool = True) -> dict:
        """Dateien scannen und in die DB indexieren."""
        scan_paths = paths or DEFAULT_SCAN_PATHS
        self._stats = {"files": 0, "dirs": 0, "errors": 0, "total_size": 0}

        for scan_path in scan_paths:
            root = Path(scan_path)
            if not root.exists():
                logger.warning(f"Pfad existiert nicht: {scan_path}")
                continue
            self._walk(root, depth=0, max_depth=max_depth,
                       compute_hash=compute_hash, count_lines=count_lines)

        logger.info(f"Workspace-Scan abgeschlossen: {self._stats}")
        return self._stats

    def _walk(self, path: Path, depth: int, max_depth: int,
              compute_hash: bool, count_lines: bool):
        """Rekursiv durch Verzeichnisbaum wandern."""
        if depth > max_depth:
            return

        try:
            entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            self._stats["errors"] += 1
            return

        for entry in entries:
            try:
                name = entry.name

                # Ignorierte Verzeichnisse
                if entry.is_dir():
                    if name in IGNORE_DIRS or name.startswith("."):
                        continue
                    rel = str(entry)
                    if any(ign in rel for ign in IGNORE_DIRS):
                        continue

                    self._index_entry(entry, depth, is_dir=True)
                    self._stats["dirs"] += 1
                    self._walk(entry, depth + 1, max_depth, compute_hash, count_lines)

                elif entry.is_file():
                    if name.startswith("~") or name.endswith("~"):
                        continue

                    stat = entry.stat()
                    ext = entry.suffix.lower()
                    category = _get_category(ext)
                    language = LANGUAGE_MAP.get(ext)

                    lines = None
                    if count_lines and category in ("code", "config", "document", "web"):
                        lines = _count_lines(entry)

                    content_hash = None
                    if compute_hash:
                        content_hash = _file_hash(entry)

                    mime = mimetypes.guess_type(str(entry))[0]

                    self._index_entry(
                        entry, depth,
                        is_dir=False,
                        file_size=stat.st_size,
                        modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                        ext=ext, mime=mime, category=category,
                        language=language, line_count=lines,
                        content_hash=content_hash
                    )
                    self._stats["files"] += 1
                    self._stats["total_size"] += stat.st_size

            except (PermissionError, OSError) as e:
                self._stats["errors"] += 1
                logger.debug(f"Fehler bei {entry}: {e}")

    def _index_entry(self, path: Path, depth: int, is_dir: bool = False, **kwargs):
        """Eintrag in die workspace_index Tabelle schreiben."""
        self.db_execute(
            """INSERT INTO dbai_core.workspace_index
               (file_path, file_name, file_ext, mime_type, file_size,
                is_directory, parent_path, depth, modified_at,
                content_hash, category, language, line_count)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (file_path) DO UPDATE SET
                   file_size = EXCLUDED.file_size,
                   modified_at = EXCLUDED.modified_at,
                   content_hash = EXCLUDED.content_hash,
                   line_count = EXCLUDED.line_count,
                   indexed_at = now()""",
            (str(path), path.name,
             kwargs.get("ext", ""), kwargs.get("mime"),
             kwargs.get("file_size", 0),
             is_dir, str(path.parent), depth,
             kwargs.get("modified_at"),
             kwargs.get("content_hash"),
             kwargs.get("category", "directory" if is_dir else "other"),
             kwargs.get("language"),
             kwargs.get("line_count"))
        )

    def get_stats(self) -> dict:
        """Workspace-Statistiken aus der DB abrufen."""
        rows = self.db_query("SELECT * FROM dbai_core.vw_workspace_stats")
        total = self.db_query(
            """SELECT COUNT(*) AS files, SUM(file_size) AS total_size,
                      COUNT(DISTINCT category) AS categories
               FROM dbai_core.workspace_index WHERE NOT is_directory"""
        )
        return {
            "by_category": rows,
            "total": total[0] if total else {},
        }

    def search(self, query: str, category: str = None, limit: int = 50) -> list:
        """Dateien im Workspace suchen."""
        sql = """SELECT file_path, file_name, file_ext, file_size,
                        category, language, line_count, modified_at
                 FROM dbai_core.workspace_index
                 WHERE NOT is_directory
                   AND (file_name ILIKE %s OR file_path ILIKE %s)"""
        params = [f"%{query}%", f"%{query}%"]

        if category:
            sql += " AND category = %s"
            params.append(category)

        sql += " ORDER BY modified_at DESC NULLS LAST LIMIT %s"
        params.append(limit)

        return self.db_query(sql, tuple(params))

    def get_tree(self, root: str = "/", max_depth: int = 3) -> list:
        """Verzeichnisbaum als JSON."""
        rows = self.db_query(
            "SELECT dbai_core.get_workspace_tree(%s, %s) AS tree",
            (root, max_depth)
        )
        return rows[0]["tree"] if rows else []
