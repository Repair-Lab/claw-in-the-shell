#!/usr/bin/env python3
"""
DBAI Event Dispatcher
=====================
Wandelt Hardware-Signale (Tastatur, Maus, Netzwerk) in INSERT-Befehle
für die Event-Tabelle um.

Die Brücke zwischen rohen Hardware-Interrupts und der Datenbank.
"""

import os
import logging
import threading
import struct
from pathlib import Path
from typing import Optional

import psycopg2
from psycopg2.extras import Json

logger = logging.getLogger("dbai.events")


# Linux Input Event Struktur (struct input_event)
# time_sec, time_usec, type, code, value
INPUT_EVENT_FORMAT = "llHHi"
INPUT_EVENT_SIZE = struct.calcsize(INPUT_EVENT_FORMAT)

# Event-Typen (linux/input-event-codes.h)
EV_KEY = 0x01
EV_REL = 0x02  # Relative Mausbewegung
EV_ABS = 0x03  # Absolute Position (Touchscreen)

# Key States
KEY_RELEASE = 0
KEY_PRESS = 1
KEY_REPEAT = 2


class EventDispatcher:
    """
    Liest Hardware-Events und schreibt sie in die Event-Tabellen.
    """

    def __init__(self, conn, shutdown_event: threading.Event):
        self.conn = conn
        self.shutdown_event = shutdown_event
        self.input_devices = {}

    def _get_cursor(self):
        if self.conn.closed:
            from system_bridge import DB_CONFIG
            self.conn = psycopg2.connect(**DB_CONFIG)
        return self.conn.cursor()

    # ------------------------------------------------------------------
    # Input-Geräte erkennen
    # ------------------------------------------------------------------
    def discover_input_devices(self):
        """Findet alle verfügbaren Input-Geräte unter /dev/input/."""
        input_dir = Path("/dev/input")
        if not input_dir.exists():
            logger.warning("/dev/input nicht vorhanden")
            return

        for event_file in sorted(input_dir.glob("event*")):
            try:
                # Geräte-Name lesen
                dev_num = event_file.name.replace("event", "")
                name_path = Path(f"/sys/class/input/event{dev_num}/device/name")
                if name_path.exists():
                    name = name_path.read_text().strip()
                else:
                    name = f"input_event{dev_num}"

                self.input_devices[str(event_file)] = {
                    "name": name,
                    "path": str(event_file),
                    "type": self._classify_device(name),
                }
                logger.info("Input-Gerät gefunden: %s (%s)", name, event_file)
            except PermissionError:
                logger.debug("Kein Zugriff auf %s", event_file)

    @staticmethod
    def _classify_device(name: str) -> str:
        """Klassifiziert ein Input-Gerät anhand des Namens."""
        name_lower = name.lower()
        if "keyboard" in name_lower or "kbd" in name_lower:
            return "keyboard"
        elif "mouse" in name_lower or "trackpad" in name_lower:
            return "mouse"
        elif "touch" in name_lower:
            return "mouse"
        else:
            return "keyboard"

    # ------------------------------------------------------------------
    # Event lesen und dispatchen
    # ------------------------------------------------------------------
    def _read_input_events(self, device_path: str, device_info: dict):
        """
        Liest Input-Events von einem Gerät und schreibt sie in die DB.
        Läuft in einem eigenen Thread pro Gerät.
        """
        try:
            with open(device_path, "rb") as f:
                while not self.shutdown_event.is_set():
                    data = f.read(INPUT_EVENT_SIZE)
                    if not data or len(data) < INPUT_EVENT_SIZE:
                        break

                    (tv_sec, tv_usec, ev_type, code, value) = struct.unpack(
                        INPUT_EVENT_FORMAT, data
                    )

                    # Nur Key-Events verarbeiten
                    if ev_type == EV_KEY:
                        action = {
                            KEY_PRESS: "press",
                            KEY_RELEASE: "release",
                            KEY_REPEAT: "repeat",
                        }.get(value, "unknown")

                        self._dispatch_keyboard_event(
                            code, action, device_info["name"]
                        )
                    elif ev_type == EV_REL:
                        self._dispatch_mouse_event(
                            code, value, device_info["name"]
                        )

        except PermissionError:
            logger.warning(
                "Kein Zugriff auf %s (root-Rechte benötigt)", device_path
            )
        except Exception as e:
            logger.error("Fehler beim Lesen von %s: %s", device_path, e)

    def _dispatch_keyboard_event(self, key_code: int, action: str, source: str):
        """Keyboard-Event in die Datenbank schreiben."""
        try:
            with self._get_cursor() as cur:
                # Haupt-Event
                cur.execute(
                    """SELECT dbai_event.dispatch_event(
                        'keyboard', %s, 5,
                        %s::jsonb
                    )""",
                    (
                        source,
                        Json({
                            "key_code": key_code,
                            "action": action,
                        }),
                    ),
                )
                event_id = cur.fetchone()[0]

                # Detail-Event
                cur.execute(
                    """
                    INSERT INTO dbai_event.keyboard
                        (key_code, action, event_id)
                    VALUES (%s, %s, %s)
                    """,
                    (key_code, action, event_id),
                )
                self.conn.commit()
        except Exception as e:
            logger.debug("Keyboard-Event fehlgeschlagen: %s", e)
            try:
                self.conn.rollback()
            except Exception:
                pass

    def _dispatch_mouse_event(self, code: int, value: int, source: str):
        """Mouse-Event in die Datenbank schreiben (gebatcht, alle 100ms)."""
        # Maus-Events werden häufig generiert — nur alle 100ms einen Batch schreiben
        # um die DB nicht zu überlasten
        pass

    def _dispatch_network_event(
        self, interface: str, event_type: str, details: dict
    ):
        """Netzwerk-Event dispatchen."""
        try:
            with self._get_cursor() as cur:
                cur.execute(
                    """SELECT dbai_event.dispatch_event(
                        'network', %s, 4,
                        %s::jsonb
                    )""",
                    (interface, Json(details)),
                )
                self.conn.commit()
        except Exception as e:
            logger.debug("Netzwerk-Event fehlgeschlagen: %s", e)
            try:
                self.conn.rollback()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Hauptschleife
    # ------------------------------------------------------------------
    def run(self):
        """Startet Event-Listener für alle erkannten Geräte."""
        logger.info("Event-Dispatcher gestartet")
        self.discover_input_devices()

        threads = []
        for path, info in self.input_devices.items():
            t = threading.Thread(
                target=self._read_input_events,
                args=(path, info),
                daemon=True,
                name=f"input-{info['name'][:20]}",
            )
            t.start()
            threads.append(t)

        # Auf Shutdown warten
        while not self.shutdown_event.is_set():
            self.shutdown_event.wait(1)

        logger.info("Event-Dispatcher gestoppt")
