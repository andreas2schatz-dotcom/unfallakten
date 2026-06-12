import os, sys, unittest
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _reload():
    import importlib
    import backend.system.health_service as hs
    importlib.reload(hs)
    return hs


class TestCheckRamicro(unittest.TestCase):

    def test_ok_setzt_cache_ok_true(self):
        hs = _reload()
        with patch.object(hs, "verbindung_pruefen", return_value={"status": "ok", "host": "x", "datenbank": "RAMICRO"}):
            hs.check_ramicro()
        self.assertTrue(hs._cache["ramicro"]["ok"])
        self.assertIsNone(hs._cache["ramicro"]["fehler"])
        self.assertIsNotNone(hs._cache["ramicro"]["letzter_sync_ts"])

    def test_fehler_setzt_cache_ok_false(self):
        hs = _reload()
        with patch.object(hs, "verbindung_pruefen", return_value={"status": "fehler", "meldung": "Connection refused"}):
            hs.check_ramicro()
        self.assertFalse(hs._cache["ramicro"]["ok"])
        self.assertEqual(hs._cache["ramicro"]["fehler"], "Connection refused")

    def test_deaktiviert_setzt_cache_ok_false(self):
        hs = _reload()
        with patch.object(hs, "verbindung_pruefen", return_value={"status": "deaktiviert", "meldung": "RAMICRO_AKTIV ist nicht 'true'"}):
            hs.check_ramicro()
        self.assertFalse(hs._cache["ramicro"]["ok"])


class TestGetStatus(unittest.TestCase):

    def test_letzter_sync_vor_s_ist_none_wenn_nie_gecheckt(self):
        hs = _reload()
        status = hs.get_status()
        self.assertIsNone(status["ramicro"]["letzter_sync_vor_s"])

    def test_letzter_sync_vor_s_wird_aus_timestamp_berechnet(self):
        hs = _reload()
        hs._cache["ramicro"] = {
            "ok": True,
            "letzter_sync_ts": datetime.now() - timedelta(seconds=120),
            "fehler": None,
        }
        status = hs.get_status()
        self.assertAlmostEqual(status["ramicro"]["letzter_sync_vor_s"], 120, delta=3)

    def test_response_enthaelt_imap_und_sv_portal_keys(self):
        hs = _reload()
        status = hs.get_status()
        self.assertIn("imap", status)
        self.assertIn("sv_portal", status)
        self.assertFalse(status["sv_portal"]["konfiguriert"])


if __name__ == "__main__":
    unittest.main()
