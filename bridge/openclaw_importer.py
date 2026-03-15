#!/usr/bin/env python3
"""
DBAI OpenClaw Importer — "The Database is the Ghost"
Migriert OpenClaw-Daten (Memories, Skills, Config) in die DBAI-Datenbank.

OpenClaw speichert alles als JSON-Dateien auf der Festplatte.
Dieser Importer liest sie ein und schreibt sie als Tabellenzeilen.
Der Ghost stirbt nicht mehr, wenn der Prozess crasht.

Usage:
    python3 -m bridge.openclaw_importer --scan /pfad/zu/openclaw
    python3 -m bridge.openclaw_importer --import /pfad/zu/openclaw
    python3 -m bridge.openclaw_importer --report
    python3 -m bridge.openclaw_importer --telegram-setup BOT_TOKEN
"""

import os
import sys
import json
import glob
import uuid
import hashlib
import logging
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Tuple

try:
    import psycopg2
    import psycopg2.extras
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

logger = logging.getLogger("dbai.openclaw_importer")


class OpenClawScanner:
    """Scannt ein OpenClaw-Verzeichnis und analysiert die Struktur."""

    # Bekannte OpenClaw-Verzeichnisstrukturen
    KNOWN_PATHS = {
        "memories": ["memories/", "memory/", "data/memories/", "long_term_memory/"],
        "skills": ["skills/", "plugins/", "modules/", "src/skills/"],
        "config": ["config.json", "settings.json", ".env", "config.yaml", "config.yml"],
        "characters": ["characters/", "personas/", "personality/"],
        "conversations": ["conversations/", "chat_history/", "history/", "logs/chats/"],
        "models": ["models/", "model_config.json"],
    }

    def __init__(self, base_path: str):
        self.base_path = Path(base_path).resolve()
        self.scan_result = {}

    def scan(self) -> Dict[str, Any]:
        """Scannt das OpenClaw-Verzeichnis und gibt eine Analyse zurueck."""
        if not self.base_path.exists():
            raise FileNotFoundError(f"OpenClaw-Verzeichnis nicht gefunden: {self.base_path}")

        result = {
            "base_path": str(self.base_path),
            "scan_time": datetime.now(timezone.utc).isoformat(),
            "is_openclaw": False,
            "detected_type": "unknown",
            "components": {},
        }

        # Typ erkennen
        result["detected_type"] = self._detect_type()
        result["is_openclaw"] = result["detected_type"] != "unknown"

        # Komponenten scannen
        for component, paths in self.KNOWN_PATHS.items():
            found = self._scan_component(paths)
            if found:
                result["components"][component] = found

        # Zusammenfassung
        result["summary"] = {
            "total_files": sum(
                c.get("file_count", 0) for c in result["components"].values()
            ),
            "total_size_mb": round(sum(
                c.get("total_size_bytes", 0) for c in result["components"].values()
            ) / (1024 * 1024), 2),
            "components_found": list(result["components"].keys()),
            "migration_ready": len(result["components"]) >= 2,
        }

        self.scan_result = result
        return result

    def _detect_type(self) -> str:
        """Erkennt ob es sich um OpenClaw, Oobabooga, KoboldAI etc. handelt."""
        # OpenClaw-Indikatoren
        if (self.base_path / "package.json").exists():
            try:
                pkg = json.loads((self.base_path / "package.json").read_text())
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                if any(k in deps for k in ["grammy", "telegraf", "node-telegram-bot-api"]):
                    return "openclaw_telegram"
                if "openai" in deps or "langchain" in deps:
                    return "openclaw_langchain"
                return "openclaw_generic"
            except (json.JSONDecodeError, KeyError):
                pass

        # Oobabooga
        if (self.base_path / "server.py").exists() and (self.base_path / "characters").is_dir():
            return "oobabooga"

        # KoboldAI
        if (self.base_path / "koboldai_settings.json").exists():
            return "koboldai"

        # SillyTavern
        if (self.base_path / "public").is_dir() and (self.base_path / "src" / "endpoints").is_dir():
            return "sillytavern"

        # Generisches Chatbot-Projekt
        if any((self.base_path / p).exists() for p in ["memories/", "memory/", "config.json"]):
            return "generic_chatbot"

        return "unknown"

    def _scan_component(self, search_paths: List[str]) -> Optional[Dict]:
        """Scannt eine Komponente (memories, skills, etc.)."""
        for rel_path in search_paths:
            full_path = self.base_path / rel_path
            if full_path.is_dir():
                files = list(full_path.rglob("*"))
                regular_files = [f for f in files if f.is_file()]
                return {
                    "path": str(full_path.relative_to(self.base_path)),
                    "file_count": len(regular_files),
                    "total_size_bytes": sum(f.stat().st_size for f in regular_files),
                    "file_types": self._count_extensions(regular_files),
                    "sample_files": [
                        str(f.relative_to(self.base_path))
                        for f in regular_files[:5]
                    ],
                }
            elif full_path.is_file():
                return {
                    "path": str(full_path.relative_to(self.base_path)),
                    "file_count": 1,
                    "total_size_bytes": full_path.stat().st_size,
                    "file_types": {full_path.suffix: 1},
                    "is_config": True,
                }
        return None

    @staticmethod
    def _count_extensions(files: List[Path]) -> Dict[str, int]:
        """Zaehlt Datei-Erweiterungen."""
        ext_count = {}
        for f in files:
            ext = f.suffix.lower() or ".no_ext"
            ext_count[ext] = ext_count.get(ext, 0) + 1
        return ext_count


class OpenClawImporter:
    """Importiert OpenClaw-Daten in die DBAI-Datenbank."""

    def __init__(self, db_dsn: str = "dbname=dbai"):
        self.db_dsn = db_dsn
        self.conn = None
        self.migration_id = None

    def connect(self):
        """Verbindung zur DBAI-Datenbank herstellen."""
        if not HAS_PSYCOPG2:
            raise ImportError("psycopg2 nicht installiert: pip install psycopg2-binary")
        self.conn = psycopg2.connect(self.db_dsn)
        self.conn.autocommit = False
        logger.info("Verbindung zur DBAI-Datenbank hergestellt")

    def disconnect(self):
        """Verbindung schliessen."""
        if self.conn:
            self.conn.close()
            self.conn = None

    # ─── MIGRATION JOB MANAGEMENT ───

    def _create_migration_job(self, job_type: str, source_path: str,
                               source_type: str = "openclaw") -> uuid.UUID:
        """Erstellt einen neuen Migration-Job."""
        with self.conn.cursor() as cur:
            job_id = uuid.uuid4()
            cur.execute("""
                INSERT INTO dbai_core.migration_jobs
                    (id, job_type, source_path, source_type, state, started_at)
                VALUES (%s, %s, %s, %s, 'scanning', NOW())
            """, (str(job_id), job_type, source_path, source_type))
            self.conn.commit()
            self.migration_id = job_id
            return job_id

    def _update_migration_job(self, state: str, total: int = None,
                               processed: int = None, failed: int = None,
                               result: dict = None, errors: list = None):
        """Aktualisiert den Migration-Job-Status."""
        if not self.migration_id:
            return
        with self.conn.cursor() as cur:
            updates = ["state = %s"]
            params = [state]
            if total is not None:
                updates.append("total_items = %s")
                params.append(total)
            if processed is not None:
                updates.append("processed_items = %s")
                params.append(processed)
            if failed is not None:
                updates.append("failed_items = %s")
                params.append(failed)
            if result is not None:
                updates.append("result_summary = %s")
                params.append(json.dumps(result))
            if errors is not None:
                updates.append("error_log = %s")
                params.append(errors)
            if state in ('completed', 'failed'):
                updates.append("completed_at = NOW()")

            params.append(str(self.migration_id))
            cur.execute(
                f"UPDATE dbai_core.migration_jobs SET {', '.join(updates)} WHERE id = %s",
                params
            )
            self.conn.commit()

    # ─── MEMORY IMPORT ───

    def import_memories(self, source_path: str, ghost_name: str = None) -> Dict:
        """Importiert OpenClaw-Memory-Dateien in pgvector."""
        source = Path(source_path)
        job_id = self._create_migration_job("openclaw_memory", str(source))

        # Ghost-ID finden
        ghost_id = self._resolve_ghost(ghost_name)

        # Memory-Verzeichnisse suchen
        memory_dirs = []
        for pattern in OpenClawScanner.KNOWN_PATHS["memories"]:
            search_dir = source / pattern.rstrip("/")
            if search_dir.is_dir():
                memory_dirs.append(search_dir)

        if not memory_dirs:
            self._update_migration_job("failed", errors=["Keine Memory-Verzeichnisse gefunden"])
            return {"error": "Keine Memory-Verzeichnisse gefunden"}

        # Alle JSON-Dateien sammeln
        json_files = []
        for d in memory_dirs:
            json_files.extend(d.rglob("*.json"))

        total = len(json_files)
        self._update_migration_job("importing", total=total, processed=0)

        imported = 0
        failed = 0
        errors = []

        for json_file in json_files:
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                memories = self._extract_memories_from_json(data, str(json_file))

                for mem in memories:
                    self._import_single_memory(
                        ghost_id=ghost_id,
                        content=mem["content"],
                        content_type=mem.get("type", "conversation"),
                        importance=mem.get("importance", 0.5),
                        original_json=data if len(memories) == 1 else mem.get("raw"),
                        openclaw_id=mem.get("id"),
                        openclaw_file=str(json_file.relative_to(source)),
                    )
                imported += 1

            except Exception as e:
                failed += 1
                errors.append(f"{json_file.name}: {str(e)[:200]}")
                logger.warning(f"Fehler bei {json_file}: {e}")

            if (imported + failed) % 50 == 0:
                self._update_migration_job("importing", processed=imported, failed=failed)
                self.conn.commit()

        self.conn.commit()
        self._update_migration_job(
            "completed",
            processed=imported,
            failed=failed,
            result={"imported": imported, "failed": failed, "total_files": total},
            errors=errors[:100]  # Max 100 Fehler speichern
        )

        return {
            "job_id": str(job_id),
            "total_files": total,
            "imported": imported,
            "failed": failed,
            "errors": errors[:10],
        }

    def _extract_memories_from_json(self, data: Any, filepath: str) -> List[Dict]:
        """Extrahiert Erinnerungen aus verschiedenen JSON-Formaten."""
        memories = []

        if isinstance(data, list):
            # Array von Nachrichten (z.B. Chat-History)
            for i, item in enumerate(data):
                if isinstance(item, dict):
                    content = item.get("content") or item.get("text") or item.get("message", "")
                    if content and len(content.strip()) > 5:
                        memories.append({
                            "content": content.strip(),
                            "type": self._classify_memory(item),
                            "importance": self._score_importance(content),
                            "id": item.get("id", f"{filepath}_{i}"),
                            "raw": item,
                        })

        elif isinstance(data, dict):
            # Einzelnes Objekt
            if "messages" in data:
                # OpenAI-kompatibles Format
                return self._extract_memories_from_json(data["messages"], filepath)

            if "memories" in data:
                return self._extract_memories_from_json(data["memories"], filepath)

            if "content" in data or "text" in data:
                content = data.get("content") or data.get("text", "")
                if content and len(content.strip()) > 5:
                    memories.append({
                        "content": content.strip(),
                        "type": self._classify_memory(data),
                        "importance": self._score_importance(content),
                        "id": data.get("id", hashlib.md5(content.encode()).hexdigest()[:12]),
                        "raw": data,
                    })

            # Persoenlichkeit / System-Prompt
            if "system_prompt" in data or "personality" in data:
                prompt = data.get("system_prompt") or data.get("personality", "")
                if prompt:
                    memories.append({
                        "content": prompt,
                        "type": "personality",
                        "importance": 0.9,
                        "id": "system_prompt",
                        "raw": data,
                    })

        return memories

    @staticmethod
    def _classify_memory(item: dict) -> str:
        """Klassifiziert einen Memory-Eintrag."""
        role = item.get("role", "").lower()
        if role == "system":
            return "system_prompt"
        if role in ("assistant", "model"):
            return "conversation"

        content = str(item.get("content", "")).lower()
        if any(w in content for w in ["merke", "remember", "wichtig", "fact"]):
            return "fact"
        if any(w in content for w in ["immer", "niemals", "preference", "mag", "like"]):
            return "preference"
        return "conversation"

    @staticmethod
    def _score_importance(content: str) -> float:
        """Bewertet die Wichtigkeit eines Memory-Eintrags."""
        score = 0.5
        # Laenge = mehr Kontext = wichtiger
        if len(content) > 500:
            score += 0.1
        if len(content) > 2000:
            score += 0.1
        # Schluesselwoerter
        lower = content.lower()
        if any(w in lower for w in ["wichtig", "merke", "important", "remember", "critical"]):
            score += 0.2
        if any(w in lower for w in ["passwort", "password", "secret", "key", "token"]):
            score += 0.15  # Sicherheitsrelevant
        if any(w in lower for w in ["todo", "aufgabe", "task", "deadline"]):
            score += 0.1
        return min(score, 1.0)

    def _import_single_memory(self, ghost_id: Optional[str], content: str,
                               content_type: str, importance: float,
                               original_json: Any, openclaw_id: str,
                               openclaw_file: str):
        """Importiert eine einzelne Erinnerung via SQL-Funktion."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT dbai_vector.import_openclaw_memory(
                    %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, (
                ghost_id,
                content,
                content_type,
                importance,
                json.dumps(original_json) if original_json else None,
                openclaw_id,
                openclaw_file,
                str(self.migration_id) if self.migration_id else None,
            ))

    # ─── SKILL IMPORT ───

    def import_skills(self, source_path: str) -> Dict:
        """Importiert OpenClaw-Skills (JS/TS Module)."""
        source = Path(source_path)
        job_id = self._create_migration_job("openclaw_skills", str(source))

        # Skill-Verzeichnisse suchen
        skill_files = []
        for pattern in OpenClawScanner.KNOWN_PATHS["skills"]:
            search_dir = source / pattern.rstrip("/")
            if search_dir.is_dir():
                for ext in ("*.js", "*.ts", "*.mjs"):
                    skill_files.extend(search_dir.rglob(ext))

        total = len(skill_files)
        self._update_migration_job("importing", total=total, processed=0)

        imported = 0
        failed = 0
        errors = []

        for skill_file in skill_files:
            try:
                code = skill_file.read_text(encoding="utf-8")
                skill_info = self._analyze_skill(skill_file.stem, code)

                with self.conn.cursor() as cur:
                    cur.execute("""
                        SELECT dbai_core.register_openclaw_skill(
                            %s, %s, %s, %s, %s, %s
                        )
                    """, (
                        skill_info["name"],
                        skill_info["display_name"],
                        code[:10000],  # Max 10KB Code archivieren
                        skill_info["action_type"],
                        skill_info.get("sql_action"),
                        skill_info["lang"],
                    ))
                imported += 1

            except Exception as e:
                failed += 1
                errors.append(f"{skill_file.name}: {str(e)[:200]}")
                logger.warning(f"Fehler bei Skill {skill_file}: {e}")

        self.conn.commit()
        self._update_migration_job(
            "completed",
            processed=imported,
            failed=failed,
            result={"imported": imported, "failed": failed, "total_files": total},
            errors=errors[:100]
        )

        return {
            "job_id": str(job_id),
            "total_files": total,
            "imported": imported,
            "failed": failed,
        }

    def _analyze_skill(self, filename: str, code: str) -> Dict:
        """Analysiert einen OpenClaw-Skill und bestimmt die Uebersetzungsstrategie."""
        lower_code = code.lower()

        # Sprache erkennen
        lang = "javascript"
        if filename.endswith(".ts") or "interface " in code or ": string" in code:
            lang = "typescript"

        # Action-Type bestimmen
        action_type = "query"  # Default
        if any(w in lower_code for w in ["fetch(", "axios", "http.", "request("]):
            action_type = "http_proxy"
        elif any(w in lower_code for w in ["exec(", "spawn(", "child_process", "shell"]):
            action_type = "shell_exec"
        elif any(w in lower_code for w in ["pg_notify", "notify", "emit("]):
            action_type = "notify"
        elif any(w in lower_code for w in ["insert ", "update ", "delete "]):
            action_type = "insert"
        elif "module.exports" in code and code.count("function") > 3:
            action_type = "composite"

        # Display-Name generieren
        display_name = filename.replace("_", " ").replace("-", " ").title()

        return {
            "name": filename.lower().replace(" ", "_"),
            "display_name": display_name,
            "lang": lang,
            "action_type": action_type,
            "sql_action": None,  # Wird spaeter manuell zugewiesen
        }

    # ─── CONFIG IMPORT ───

    def import_config(self, source_path: str) -> Dict:
        """Importiert OpenClaw-Konfiguration als Ghost-Parameter."""
        source = Path(source_path)
        job_id = self._create_migration_job("openclaw_config", str(source))

        config_data = {}
        imported = 0

        # Config-Dateien suchen und einlesen
        for pattern in OpenClawScanner.KNOWN_PATHS["config"]:
            config_file = source / pattern
            if config_file.is_file():
                try:
                    if pattern.endswith(".json"):
                        config_data[pattern] = json.loads(
                            config_file.read_text(encoding="utf-8")
                        )
                    elif pattern == ".env":
                        config_data[".env"] = self._parse_env_file(config_file)
                    imported += 1
                except Exception as e:
                    logger.warning(f"Config-Fehler bei {config_file}: {e}")

        # Characters/Personas importieren
        for pattern in OpenClawScanner.KNOWN_PATHS["characters"]:
            char_dir = source / pattern.rstrip("/")
            if char_dir.is_dir():
                for char_file in char_dir.rglob("*.json"):
                    try:
                        char_data = json.loads(char_file.read_text(encoding="utf-8"))
                        # Als Personality-Memory importieren
                        name = char_data.get("name", char_file.stem)
                        prompt = char_data.get("system_prompt") or char_data.get(
                            "personality", "") or char_data.get("description", "")
                        if prompt:
                            self._import_single_memory(
                                ghost_id=None,
                                content=f"[Persona: {name}] {prompt}",
                                content_type="personality",
                                importance=0.9,
                                original_json=char_data,
                                openclaw_id=f"char_{char_file.stem}",
                                openclaw_file=str(char_file.relative_to(source)),
                            )
                            imported += 1
                    except Exception as e:
                        logger.warning(f"Character-Fehler bei {char_file}: {e}")

        self.conn.commit()
        self._update_migration_job(
            "completed",
            processed=imported,
            result={"configs_found": list(config_data.keys()), "imported": imported}
        )

        return {
            "job_id": str(job_id),
            "configs_found": list(config_data.keys()),
            "imported": imported,
        }

    @staticmethod
    def _parse_env_file(env_path: Path) -> Dict[str, str]:
        """Liest eine .env-Datei (ohne Secrets zu loggen)."""
        env_vars = {}
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                # Secrets maskieren
                if any(s in key.lower() for s in ["token", "secret", "password", "key", "api"]):
                    env_vars[key] = "***MASKED***"
                else:
                    env_vars[key] = value.strip().strip("'\"")
        return env_vars

    # ─── FULL IMPORT ───

    def full_import(self, source_path: str, ghost_name: str = None) -> Dict:
        """Fuehrt einen kompletten Import durch: Memories + Skills + Config."""
        results = {
            "source": source_path,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }

        # 1. Scan
        scanner = OpenClawScanner(source_path)
        scan = scanner.scan()
        results["scan"] = scan["summary"]

        if not scan["is_openclaw"] and scan["detected_type"] == "unknown":
            logger.warning(f"Kein bekanntes Format erkannt in {source_path}")

        # 2. Memories importieren
        if "memories" in scan["components"] or "conversations" in scan["components"]:
            results["memories"] = self.import_memories(source_path, ghost_name)

        # 3. Skills importieren
        if "skills" in scan["components"]:
            results["skills"] = self.import_skills(source_path)

        # 4. Config importieren
        if "config" in scan["components"] or "characters" in scan["components"]:
            results["config"] = self.import_config(source_path)

        results["completed_at"] = datetime.now(timezone.utc).isoformat()
        return results

    # ─── HILFSFUNKTIONEN ───

    def _resolve_ghost(self, ghost_name: str = None) -> Optional[str]:
        """Findet die Ghost-ID anhand des Namens."""
        if not ghost_name:
            return None
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM dbai_llm.ghost_models WHERE name = %s",
                (ghost_name,)
            )
            row = cur.fetchone()
            return str(row[0]) if row else None

    def get_migration_report(self) -> Dict:
        """Holt den Migration-Report aus der Datenbank."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT dbai_core.openclaw_migration_report()")
            row = cur.fetchone()
            return row[0] if row else {}


class TelegramBridge:
    """Verbindet einen Telegram-Bot mit der DBAI task_queue.

    Der Bot schreibt Nachrichten direkt in die DB.
    Der Ghost verarbeitet sie ueber die task_queue.
    Antworten gehen ueber NOTIFY zurueck zum Bot.
    """

    def __init__(self, bot_token: str, db_dsn: str = "dbname=dbai"):
        self.bot_token = bot_token
        self.db_dsn = db_dsn
        self.conn = None

    def connect(self):
        """DB-Verbindung herstellen."""
        if not HAS_PSYCOPG2:
            raise ImportError("psycopg2 nicht installiert")
        self.conn = psycopg2.connect(self.db_dsn)
        self.conn.autocommit = True
        logger.info("Telegram Bridge: DB-Verbindung hergestellt")

    def process_message(self, chat_id: int, user_id: int,
                        username: str, message_id: int,
                        text: str, msg_type: str = "text") -> str:
        """Verarbeitet eine eingehende Telegram-Nachricht.

        Schreibt in die DB und gibt die Bridge-ID zurueck.
        """
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT dbai_event.process_telegram_message(
                    %s, %s, %s, %s, %s, %s
                )
            """, (chat_id, user_id, username, message_id, text, msg_type))
            row = cur.fetchone()
            return str(row[0]) if row else None

    def listen_for_responses(self, callback):
        """Hoert auf NOTIFY-Events fuer Telegram-Antworten.

        Args:
            callback: Funktion die (chat_id, response_text) erhaelt
        """
        self.conn.set_isolation_level(0)
        with self.conn.cursor() as cur:
            cur.execute("LISTEN telegram_response;")

        logger.info("Telegram Bridge: Warte auf Antworten via NOTIFY...")
        import select
        while True:
            if select.select([self.conn], [], [], 5) != ([], [], []):
                self.conn.poll()
                while self.conn.notifies:
                    notify = self.conn.notifies.pop(0)
                    try:
                        payload = json.loads(notify.payload)
                        callback(
                            payload.get("chat_id"),
                            payload.get("response_text", "")
                        )
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.warning(f"Telegram NOTIFY Parse-Fehler: {e}")

    def setup_bot_config(self):
        """Speichert die Bot-Konfiguration in der DBAI-Datenbank."""
        with self.conn.cursor() as cur:
            # Bot-Token sicher speichern (als Config-Eintrag)
            cur.execute("""
                INSERT INTO dbai_core.config (key, value, is_readonly)
                VALUES ('telegram.bot_token', %s, TRUE)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """, (self.bot_token,))

            # Telegram als App-Stream markieren
            cur.execute("""
                UPDATE dbai_ui.app_streams
                SET is_active = TRUE, last_data_at = NOW()
                WHERE app_name = 'telegram_bridge'
            """)
        logger.info("Telegram Bot-Konfiguration in DB gespeichert")


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="DBAI OpenClaw Importer — The Database is the Ghost",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  # OpenClaw-Verzeichnis analysieren
  %(prog)s --scan /pfad/zu/openclaw

  # Vollstaendiger Import (Memories + Skills + Config)
  %(prog)s --import /pfad/zu/openclaw

  # Nur Memories importieren
  %(prog)s --import-memories /pfad/zu/openclaw --ghost qwen2.5-7b

  # Migrations-Report anzeigen
  %(prog)s --report

  # Telegram-Bot einrichten
  %(prog)s --telegram-setup YOUR_BOT_TOKEN
        """
    )

    parser.add_argument("--scan", metavar="PATH",
                        help="OpenClaw-Verzeichnis analysieren (ohne Import)")
    parser.add_argument("--import", metavar="PATH", dest="import_path",
                        help="Vollstaendiger Import: Memories + Skills + Config")
    parser.add_argument("--import-memories", metavar="PATH",
                        help="Nur Memories importieren")
    parser.add_argument("--import-skills", metavar="PATH",
                        help="Nur Skills importieren")
    parser.add_argument("--ghost", metavar="NAME", default=None,
                        help="Ghost-Name fuer den Import (z.B. qwen2.5-7b)")
    parser.add_argument("--report", action="store_true",
                        help="Migrations-Report anzeigen")
    parser.add_argument("--telegram-setup", metavar="TOKEN",
                        help="Telegram-Bot einrichten")
    parser.add_argument("--db", default="dbname=dbai",
                        help="PostgreSQL DSN (default: dbname=dbai)")
    parser.add_argument("--json", action="store_true",
                        help="Ausgabe als JSON")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Debug-Ausgaben")

    args = parser.parse_args()

    # Logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    )

    # ─── Scan (kein DB-Zugriff noetig) ───
    if args.scan:
        scanner = OpenClawScanner(args.scan)
        result = scanner.scan()
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            _print_scan_result(result)
        return

    # ─── DB-basierte Operationen ───
    if args.import_path or args.import_memories or args.import_skills or args.report:
        importer = OpenClawImporter(args.db)
        try:
            importer.connect()

            if args.import_path:
                result = importer.full_import(args.import_path, args.ghost)
            elif args.import_memories:
                result = importer.import_memories(args.import_memories, args.ghost)
            elif args.import_skills:
                result = importer.import_skills(args.import_skills)
            elif args.report:
                result = importer.get_migration_report()

            if args.json:
                print(json.dumps(result, indent=2, default=str))
            else:
                _print_import_result(result)

        except Exception as e:
            logger.error(f"Fehler: {e}")
            sys.exit(1)
        finally:
            importer.disconnect()
        return

    # ─── Telegram Setup ───
    if args.telegram_setup:
        bridge = TelegramBridge(args.telegram_setup, args.db)
        try:
            bridge.connect()
            bridge.setup_bot_config()
            print("✓ Telegram-Bot konfiguriert!")
            print(f"  Token in dbai_core.config gespeichert")
            print(f"  App-Stream 'telegram_bridge' aktiviert")
            print(f"\n  Starte den Bot mit:")
            print(f"    python3 -m bridge.telegram_bot")
        except Exception as e:
            logger.error(f"Telegram Setup Fehler: {e}")
            sys.exit(1)
        finally:
            bridge.conn.close() if bridge.conn else None
        return

    parser.print_help()


def _print_scan_result(result: dict):
    """Gibt das Scan-Ergebnis formatiert aus."""
    print(f"\n{'='*60}")
    print(f" OpenClaw Scanner — Analyse")
    print(f"{'='*60}")
    print(f"  Pfad:    {result['base_path']}")
    print(f"  Typ:     {result['detected_type']}")
    print(f"  OpenClaw: {'JA' if result['is_openclaw'] else 'NEIN'}")
    print()

    summary = result.get("summary", {})
    print(f"  Dateien: {summary.get('total_files', 0)}")
    print(f"  Groesse: {summary.get('total_size_mb', 0)} MB")
    print(f"  Bereit:  {'JA' if summary.get('migration_ready') else 'NEIN'}")
    print()

    for comp, info in result.get("components", {}).items():
        print(f"  [{comp.upper()}]")
        print(f"    Pfad:    {info.get('path', '?')}")
        print(f"    Dateien: {info.get('file_count', 0)}")
        if info.get("file_types"):
            types = ", ".join(f"{k}({v})" for k, v in info["file_types"].items())
            print(f"    Typen:   {types}")
        print()

    print(f"{'='*60}")
    if summary.get("migration_ready"):
        print("  → Bereit fuer Import: python3 -m bridge.openclaw_importer --import <pfad>")
    else:
        print("  → Zu wenige Komponenten fuer automatischen Import")
    print()


def _print_import_result(result: dict):
    """Gibt das Import-Ergebnis formatiert aus."""
    print(f"\n{'='*60}")
    print(f" OpenClaw Import — Ergebnis")
    print(f"{'='*60}")
    for key, value in result.items():
        if isinstance(value, dict):
            print(f"\n  [{key.upper()}]")
            for k, v in value.items():
                print(f"    {k}: {v}")
        else:
            print(f"  {key}: {value}")
    print(f"\n{'='*60}")
    print("  → Report: python3 -m bridge.openclaw_importer --report")
    print()


if __name__ == "__main__":
    main()
