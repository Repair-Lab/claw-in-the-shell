"""
bridge/browser_agent.py — Ghost Browser Agent (Playwright-basiert)

KI-gesteuerter Chromium-Browser: Ghost navigiert, extrahiert Daten,
erstellt Screenshots und generiert Ergebnis-Dateien.
"""

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("dbai.browser_agent")

# Screenshot-Verzeichnis
SCREENSHOTS_DIR = Path("/tmp/dbai_browser_screenshots")
RESULTS_DIR = Path("/tmp/dbai_browser_results")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Global: Laufende Tasks
_running_tasks: dict = {}


class BrowserAgent:
    """
    Playwright-basierter Browser-Agent.
    Führt Aufgaben wie Recherche, Screenshots, Datenextraktion aus.
    """

    def __init__(self, task_id: str, db_update_fn=None):
        self.task_id = task_id
        self.db_update = db_update_fn
        self.browser = None
        self.context = None
        self.page = None
        self.steps: list = []
        self.pages_visited: list = []
        self.screenshots: list = []
        self.cancelled = False
        self._step_counter = 0

    async def _log_step(self, action: str, selector: str = None,
                        value: str = None, result_data: dict = None,
                        screenshot: bool = True, success: bool = True,
                        error_msg: str = None):
        """Logge einen Browser-Schritt."""
        self._step_counter += 1
        step_start = time.time()

        page_url = ""
        page_title = ""
        screenshot_path = None

        try:
            if self.page:
                page_url = self.page.url
                page_title = await self.page.title()
        except Exception:
            pass

        # Screenshot erstellen
        if screenshot and self.page and success:
            try:
                fname = f"{self.task_id}_{self._step_counter:03d}.png"
                screenshot_path = str(SCREENSHOTS_DIR / fname)
                await self.page.screenshot(path=screenshot_path, full_page=False)
                self.screenshots.append(screenshot_path)
            except Exception as e:
                logger.warning("Screenshot fehlgeschlagen: %s", e)
                screenshot_path = None

        duration_ms = int((time.time() - step_start) * 1000)

        step = {
            "step_number": self._step_counter,
            "action": action,
            "selector": selector,
            "value": value,
            "page_url": page_url,
            "page_title": page_title,
            "screenshot_path": screenshot_path,
            "result_data": result_data,
            "duration_ms": duration_ms,
            "success": success,
            "error_message": error_msg,
        }
        self.steps.append(step)

        if page_url and page_url not in self.pages_visited:
            self.pages_visited.append(page_url)

        # DB-Step speichern
        if self.db_update:
            try:
                self.db_update("step", {
                    "task_id": self.task_id,
                    **step
                })
            except Exception as e:
                logger.warning("DB step write failed: %s", e)

        return step

    async def launch(self, headless: bool = True):
        """Starte den Browser."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("Playwright nicht installiert. Bitte: pip install playwright && playwright install chromium")
            raise RuntimeError("Playwright nicht verfügbar. Installation: pip install playwright && playwright install chromium")

        self._pw = await async_playwright().start()
        self.browser = await self._pw.chromium.launch(
            headless=headless,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-extensions',
                '--disable-background-networking',
            ]
        )
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 DBAI-Ghost/1.0",
            locale="de-DE",
            timezone_id="Europe/Berlin",
        )
        self.page = await self.context.new_page()

        # Blockiere Tracker/Ads für schnelleres Browsen
        await self.page.route("**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2}", lambda route: route.abort())

        logger.info("[Ghost Browser] Browser gestartet für Task %s", self.task_id)

    async def close(self):
        """Browser beenden."""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if hasattr(self, '_pw') and self._pw:
                await self._pw.stop()
        except Exception as e:
            logger.warning("Browser close error: %s", e)
        logger.info("[Ghost Browser] Browser geschlossen für Task %s", self.task_id)

    async def navigate(self, url: str, wait_for: str = "domcontentloaded"):
        """Navigiere zu einer URL."""
        await self.page.goto(url, wait_until=wait_for, timeout=15000)
        await self._log_step("navigate", value=url)

    async def click(self, selector: str, wait_after: int = 1000):
        """Klicke auf ein Element."""
        await self.page.click(selector, timeout=5000)
        await self.page.wait_for_timeout(wait_after)
        await self._log_step("click", selector=selector)

    async def type_text(self, selector: str, text: str, delay: int = 50):
        """Tippe Text in ein Feld."""
        await self.page.fill(selector, text)
        await self._log_step("type", selector=selector, value=text)

    async def scroll_down(self, pixels: int = 500):
        """Scrolle nach unten."""
        await self.page.evaluate(f"window.scrollBy(0, {pixels})")
        await self.page.wait_for_timeout(500)
        await self._log_step("scroll", value=str(pixels))

    async def extract_text(self, selector: str = "body") -> str:
        """Extrahiere Text aus einem Element."""
        try:
            text = await self.page.inner_text(selector, timeout=5000)
            text = text.strip()[:5000]  # Limit
            await self._log_step("extract", selector=selector,
                                 result_data={"text_length": len(text)})
            return text
        except Exception as e:
            await self._log_step("extract", selector=selector,
                                 success=False, error_msg=str(e))
            return ""

    async def extract_links(self, selector: str = "a") -> list:
        """Extrahiere alle Links."""
        links = await self.page.evaluate(f"""
            Array.from(document.querySelectorAll('{selector}')).map(a => ({{
                text: a.innerText.trim().substring(0, 200),
                href: a.href
            }})).filter(l => l.href && l.href.startsWith('http'))
        """)
        await self._log_step("extract", selector=selector,
                             result_data={"links_count": len(links)})
        return links

    async def take_screenshot(self, full_page: bool = True) -> str:
        """Erstelle einen Screenshot und gib den Pfad zurück."""
        fname = f"{self.task_id}_manual_{int(time.time())}.png"
        path = str(SCREENSHOTS_DIR / fname)
        await self.page.screenshot(path=path, full_page=full_page)
        self.screenshots.append(path)
        await self._log_step("screenshot", value=path, screenshot=False)
        return path

    async def wait(self, ms: int = 1000):
        """Warte eine bestimmte Zeit."""
        await self.page.wait_for_timeout(ms)
        await self._log_step("wait", value=str(ms), screenshot=False)

    # ── Hochlevel-Aktionen ───────────────────────────────────────────────

    async def google_search(self, query: str) -> list:
        """Google-Suche durchführen, Ergebnisse extrahieren."""
        await self.navigate("https://www.google.com/search?q=" + query.replace(" ", "+"))
        await self.page.wait_for_timeout(2000)

        # Cookie-Banner akzeptieren (falls vorhanden)
        try:
            accept_btn = self.page.locator("button:has-text('Alle akzeptieren'), button:has-text('Accept all')")
            if await accept_btn.count() > 0:
                await accept_btn.first.click()
                await self.page.wait_for_timeout(1000)
        except Exception:
            pass

        # Ergebnisse extrahieren
        results = await self.page.evaluate("""
            Array.from(document.querySelectorAll('div.g, div[data-sokoban-container]')).slice(0, 10).map(el => {
                const link = el.querySelector('a');
                const title = el.querySelector('h3');
                const snippet = el.querySelector('[data-sncf], .VwiC3b, [style*="-webkit-line-clamp"]');
                return {
                    title: title ? title.innerText.trim() : '',
                    url: link ? link.href : '',
                    snippet: snippet ? snippet.innerText.trim().substring(0, 300) : ''
                };
            }).filter(r => r.title && r.url && r.url.startsWith('http'))
        """)

        await self._log_step("extract", value=f"Google: {query}",
                             result_data={"results_count": len(results), "query": query})
        return results

    async def visit_and_extract(self, url: str, max_chars: int = 3000) -> dict:
        """Besuche eine Seite und extrahiere den Hauptinhalt."""
        try:
            await self.navigate(url)
            await self.page.wait_for_timeout(1500)

            content = await self.page.evaluate("""
                (() => {
                    // Versuche den Hauptinhalt zu finden
                    const selectors = ['article', 'main', '[role="main"]', '.post-content',
                                       '.entry-content', '.article-body', '#content', '.content'];
                    for (const sel of selectors) {
                        const el = document.querySelector(sel);
                        if (el && el.innerText.trim().length > 200) {
                            return el.innerText.trim();
                        }
                    }
                    // Fallback: body text
                    return document.body.innerText.trim();
                })()
            """)

            title = await self.page.title()
            content = content[:max_chars]

            await self._log_step("extract", value=url,
                                 result_data={"title": title, "content_length": len(content)})

            return {"title": title, "url": url, "content": content}
        except Exception as e:
            logger.warning("Extract failed for %s: %s", url, e)
            await self._log_step("extract", value=url, success=False, error_msg=str(e))
            return {"title": "", "url": url, "content": "", "error": str(e)}

    # ── Task-Runner ──────────────────────────────────────────────────────

    async def run_research(self, prompt: str, target_url: str = None,
                           max_pages: int = 8, output_format: str = "markdown") -> dict:
        """
        Führe eine Web-Recherche durch.
        1. Google-Suche basierend auf dem Prompt
        2. Top-Ergebnisse besuchen und Inhalte extrahieren
        3. Zusammenfassung als Datei erstellen
        """
        results = {
            "query": prompt,
            "sources": [],
            "summary": "",
            "output_path": "",
        }

        try:
            # 1. Bei vorgegebener URL direkt dort starten
            if target_url:
                data = await self.visit_and_extract(target_url)
                results["sources"].append(data)

            # 2. Google-Suche
            search_query = prompt.replace("Recherchiere zum Thema:", "").strip()[:100]
            search_results = await self.google_search(search_query)

            # 3. Top-Ergebnisse besuchen
            visited = 0
            for sr in search_results[:max_pages]:
                if self.cancelled:
                    break
                if visited >= max_pages:
                    break
                if not sr.get("url"):
                    continue

                data = await self.visit_and_extract(sr["url"])
                if data.get("content"):
                    results["sources"].append({
                        **data,
                        "search_title": sr.get("title", ""),
                        "search_snippet": sr.get("snippet", ""),
                    })
                    visited += 1

            # 4. Ergebnis-Datei erstellen
            if output_format == "markdown":
                results["output_path"] = self._create_markdown_report(prompt, results["sources"])
                results["summary"] = f"Recherche abgeschlossen: {len(results['sources'])} Quellen analysiert."
            elif output_format == "json":
                results["output_path"] = self._create_json_report(prompt, results["sources"])
                results["summary"] = f"JSON-Export: {len(results['sources'])} Einträge."
            elif output_format == "csv":
                results["output_path"] = self._create_csv_report(prompt, results["sources"])
                results["summary"] = f"CSV-Export: {len(results['sources'])} Zeilen."

        except Exception as e:
            logger.error("Research task failed: %s", e)
            results["summary"] = f"Fehler: {e}"
            raise

        return results

    async def run_screenshot(self, url: str) -> dict:
        """Erstelle einen Full-Page-Screenshot einer URL."""
        await self.navigate(url)
        await self.page.wait_for_timeout(2000)
        path = await self.take_screenshot(full_page=True)
        title = await self.page.title()
        return {
            "url": url,
            "title": title,
            "screenshot_path": path,
            "summary": f"Screenshot von {title} erstellt.",
        }

    async def run_extract(self, url: str, prompt: str) -> dict:
        """Daten von einer Webseite extrahieren."""
        await self.navigate(url)
        await self.page.wait_for_timeout(2000)

        # Text extrahieren
        text = await self.extract_text("body")
        links = await self.extract_links()
        title = await self.page.title()

        # JSON-Report
        data = {
            "url": url,
            "title": title,
            "text_content": text,
            "links": links[:50],
            "prompt": prompt,
        }
        output_path = self._create_json_report(prompt, [data])

        return {
            "url": url,
            "title": title,
            "output_path": output_path,
            "summary": f"Daten extrahiert: {len(text)} Zeichen, {len(links)} Links.",
        }

    # ── Report-Generatoren ───────────────────────────────────────────────

    def _create_markdown_report(self, topic: str, sources: list) -> str:
        """Erstelle einen Markdown-Report."""
        fname = f"ghost_research_{int(time.time())}.md"
        path = str(RESULTS_DIR / fname)

        lines = [
            f"# Ghost Browser — Recherche-Ergebnis\n",
            f"**Thema:** {topic}\n",
            f"**Datum:** {datetime.now().strftime('%d.%m.%Y %H:%M')}\n",
            f"**Quellen:** {len(sources)}\n",
            "---\n",
        ]

        for i, src in enumerate(sources, 1):
            title = src.get("title") or src.get("search_title") or "Ohne Titel"
            url = src.get("url", "")
            snippet = src.get("search_snippet", "")
            content = src.get("content", "")[:1500]

            lines.append(f"\n## {i}. {title}\n")
            lines.append(f"**URL:** [{url}]({url})\n")
            if snippet:
                lines.append(f"**Snippet:** {snippet}\n")
            lines.append(f"\n{content}\n")
            lines.append("\n---\n")

        lines.append(f"\n*Automatisch erstellt von Ghost Browser am {datetime.now().strftime('%d.%m.%Y %H:%M')}*\n")

        with open(path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        logger.info("Markdown-Report erstellt: %s", path)
        return path

    def _create_json_report(self, topic: str, sources: list) -> str:
        """Erstelle einen JSON-Report."""
        fname = f"ghost_extract_{int(time.time())}.json"
        path = str(RESULTS_DIR / fname)

        report = {
            "topic": topic,
            "date": datetime.now().isoformat(),
            "sources_count": len(sources),
            "data": sources,
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info("JSON-Report erstellt: %s", path)
        return path

    def _create_csv_report(self, topic: str, sources: list) -> str:
        """Erstelle einen CSV-Report."""
        fname = f"ghost_data_{int(time.time())}.csv"
        path = str(RESULTS_DIR / fname)

        import csv
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Nr", "Titel", "URL", "Snippet", "Inhalt (gekürzt)"])
            for i, src in enumerate(sources, 1):
                writer.writerow([
                    i,
                    src.get("title", ""),
                    src.get("url", ""),
                    src.get("search_snippet", "")[:200],
                    src.get("content", "")[:500],
                ])

        logger.info("CSV-Report erstellt: %s", path)
        return path


# ── Task-Executor (wird async aus dem API-Endpoint gestartet) ────────────

async def execute_browser_task(task_id: str, prompt: str, task_type: str,
                               target_url: str = None, max_pages: int = 8,
                               max_duration_s: int = 120,
                               output_format: str = "markdown",
                               sandbox_mode: bool = True,
                               db_update_fn=None) -> dict:
    """
    Hauptfunktion: Führt einen kompletten Browser-Task aus.
    Wird als asyncio.Task im Hintergrund gestartet.
    """
    agent = BrowserAgent(task_id, db_update_fn=db_update_fn)
    _running_tasks[task_id] = agent
    result = {}

    try:
        # Status: running
        if db_update_fn:
            db_update_fn("status", {"task_id": task_id, "status": "running",
                                     "started_at": datetime.now().isoformat()})

        await agent.launch(headless=True)

        # Timeout via asyncio
        async def _run():
            nonlocal result
            if task_type == "research":
                result = await agent.run_research(prompt, target_url, max_pages, output_format)
            elif task_type == "screenshot":
                url = target_url or "about:blank"
                result = await agent.run_screenshot(url)
            elif task_type == "extract":
                url = target_url or "about:blank"
                result = await agent.run_extract(url, prompt)
            elif task_type == "download":
                # Einfacher Download: Seite besuchen und Volltext speichern
                result = await agent.run_extract(target_url or "about:blank", prompt)
            else:
                # Fallback: Research
                result = await agent.run_research(prompt, target_url, max_pages, output_format)

        await asyncio.wait_for(_run(), timeout=max_duration_s)

        # Erfolg
        result["steps"] = agent.steps
        result["pages_visited"] = agent.pages_visited
        result["screenshots"] = agent.screenshots

        if db_update_fn:
            db_update_fn("complete", {
                "task_id": task_id,
                "status": "completed",
                "result_summary": result.get("summary", ""),
                "result_path": result.get("output_path", ""),
                "result_data": result,
                "pages_visited": agent.pages_visited,
                "screenshots": agent.screenshots,
                "steps_log": agent.steps,
                "progress": 100,
            })

    except asyncio.TimeoutError:
        result = {"error": f"Timeout nach {max_duration_s}s", "steps": agent.steps}
        if db_update_fn:
            db_update_fn("complete", {
                "task_id": task_id, "status": "failed",
                "error_message": f"Timeout: Task hat {max_duration_s}s überschritten",
                "progress": agent._step_counter,
                "steps_log": agent.steps,
                "pages_visited": agent.pages_visited,
            })
    except Exception as e:
        logger.error("Browser task %s failed: %s", task_id, e, exc_info=True)
        result = {"error": str(e), "steps": agent.steps}
        if db_update_fn:
            db_update_fn("complete", {
                "task_id": task_id, "status": "failed",
                "error_message": str(e),
                "steps_log": agent.steps,
                "pages_visited": agent.pages_visited,
            })
    finally:
        await agent.close()
        _running_tasks.pop(task_id, None)

    return result


def cancel_task(task_id: str) -> bool:
    """Markiere einen laufenden Task als abgebrochen."""
    agent = _running_tasks.get(task_id)
    if agent:
        agent.cancelled = True
        return True
    return False


def get_running_tasks() -> list:
    """Liste aller aktuell laufenden Tasks."""
    return list(_running_tasks.keys())
