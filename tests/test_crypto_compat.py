#!/usr/bin/env python3
"""
DBAI Tests — Krypto-Regressionsschutz (Phase 1, Bug A)

Sichert ab:
  1. encrypt_secret/decrypt_secret Roundtrip (Fernet)
  2. decrypt_secret dekodiert Legacy-Base64-Keys (vor Fernet-Einführung)
  3. decrypt_secret crascht NICHT bei Müll/ungültigen Werten
  4. Der Provider-Test-Pfad (llm_provider_test) verwendet decrypt_secret,
     nicht mehr rohes base64.b64decode (Statische Code-Prüfung)
"""
import os
import re
import sys
import base64
import unittest
from pathlib import Path

# web/ zum Python-Pfad (server.py importiert dbai-* Module aus bridge/)
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "bridge"))
sys.path.insert(0, str(_ROOT / "web"))
sys.path.insert(0, str(_ROOT / "llm"))

# Saubere Test-Umgebung: Sandbox + frischer Fernet-Key via Env
os.environ["DBAI_ENV"] = "sandbox"
os.environ.pop("DBAI_FERNET_KEY", None)


def _web_src() -> str:
    """Liest alle web/*.py-Module zusammen (Phase 2: server.py + routers.py + common.py)."""
    web_dir = Path(__file__).resolve().parent.parent / "web"
    return "\n".join(f.read_text(encoding="utf-8") for f in sorted(web_dir.glob("*.py")))


class TestSecretCrypto(unittest.TestCase):
    """Roundtrip + Legacy-Kompatibilität der Key-Verschlüsselung."""

    @classmethod
    def setUpClass(cls):
        from cryptography.fernet import Fernet
        os.environ["DBAI_FERNET_KEY"] = Fernet.generate_key().decode()
        import server
        cls.server = server

    def test_roundtrip_fernet(self):
        enc = self.server.encrypt_secret("sk-abc-123-def")
        self.assertNotEqual(enc, "sk-abc-123-def")
        self.assertEqual(self.server.decrypt_secret(enc), "sk-abc-123-def")

    def test_roundtrip_unicode(self):
        secret = "sk-Ümlaut-ÖÄÜ-123"
        self.assertEqual(self.server.decrypt_secret(self.server.encrypt_secret(secret)), secret)

    def test_legacy_base64_key_still_readable(self):
        """Alte Keys (Base64-Ära) müssen nach wie vor lesbar sein."""
        if not self.server._fernet:
            self.skipTest("Fernet nicht aktiv")
        legacy = base64.b64encode(b"sk-legacy-plain-key").decode()
        self.assertEqual(self.server.decrypt_secret(legacy), "sk-legacy-plain-key")

    def test_garbage_input_does_not_crash(self):
        """Müll-Werte dürfen keine Exception werfen (sonst crasht der
        Provider-Test-Endpoint — der ursprüngliche Bug A)."""
        for bad in ("total-müll-###", "", "gAAAAAB", base64.b64encode(b"\x00\xff\xfe").decode()):
            try:
                result = self.server.decrypt_secret(bad)
            except Exception as e:
                self.fail(f"decrypt_secret({bad!r}) warf {type(e).__name__}: {e}")
            self.assertIsInstance(result, str)


class TestProviderTestEndpointUsesDecrypt(unittest.TestCase):
    """Statische Prüfung: llm_provider_test dekodiert via decrypt_secret."""

    @classmethod
    def setUpClass(cls):
        cls.server_src = _web_src()

    def test_no_raw_b64decode_of_api_key_enc(self):
        # Ein roher b64decode direkt auf api_key_enc wäre der Bug
        bad = re.findall(r"base64\.b64decode\(rows\[0\][^\n]*api_key_enc", self.server_src)
        self.assertEqual(bad, [], f"Roh-Base64-Dekodierung von api_key_enc gefunden: {bad}")

    def test_decrypt_secret_has_fallback(self):
        # decrypt_secret muss den Base64-Fallback enthalten
        m = re.search(r"def decrypt_secret.*?(?=\n# ---|\ndef )", self.server_src, re.S)
        self.assertIsNotNone(m, "decrypt_secret nicht gefunden")
        self.assertIn("base64.b64decode", m.group(0), "Base64-Legacy-Fallback fehlt")
        self.assertIn("try", m.group(0), "Try/Except-Fallback fehlt")


if __name__ == "__main__":
    unittest.main(verbosity=2)
