"""Tests: PRD-27 Replacement-Engine + Vorschau-Endpoint"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestErsetzePlatzhalter(unittest.TestCase):

    def setUp(self):
        from backend.word.stellungnahme_service import ersetze_platzhalter
        self.fn = ersetze_platzhalter

    def test_einfache_ersetzung(self):
        text = "Sehr geehrte Damen und Herren von <VERSICHERER>,"
        kontext = {"VERSICHERER": "Allianz AG"}
        result = self.fn(text, kontext)
        self.assertEqual(result, "Sehr geehrte Damen und Herren von Allianz AG,")

    def test_mehrere_platzhalter(self):
        text = "Mandant: <MANDANT>, AZ: <AZ>"
        kontext = {"MANDANT": "Max Mustermann", "AZ": "31/21"}
        result = self.fn(text, kontext)
        self.assertEqual(result, "Mandant: Max Mustermann, AZ: 31/21")

    def test_unbekannter_platzhalter_wird_markiert(self):
        text = "Wert: <UNBEKANNT>"
        result = self.fn(text, {})
        self.assertIn("[FEHLT: <UNBEKANNT>]", result)

    def test_leerer_text(self):
        self.assertIsNone(self.fn(None, {"X": "y"}))

    def test_leerer_wert_bleibt_leer(self):
        text = "Hallo <MANDANT>"
        result = self.fn(text, {"MANDANT": ""})
        self.assertEqual(result, "Hallo ")


import tempfile
import json


class TestVorschauEndpoint(unittest.TestCase):
    """Integration-Test: GET /akten/<az>/stellungnahme/vorschau"""

    def setUp(self):
        tmp = tempfile.mkdtemp()
        db_path = os.path.join(tmp, "test_prd27.db")
        os.environ["DB_PATH"] = db_path

        import importlib
        import backend.db.database as db_mod
        import backend.db.schema_manager as sm_mod
        importlib.reload(db_mod)
        importlib.reload(sm_mod)

        with db_mod.get_connection() as conn:
            sm_mod.initialisiere_schema(conn)

        import backend.app as app_mod
        importlib.reload(app_mod)
        app = app_mod.erstelle_app()
        app.config["TESTING"] = True
        self.client = app.test_client()
        self.db_mod = db_mod

    def _login(self) -> dict:
        r = self.client.post("/auth/login",
                             json={"benutzername": "admin", "passwort": "admin123"})
        return json.loads(r.data)

    def test_vorschau_ohne_akte_gibt_404(self):
        token = self._login()["access_token"]
        r = self.client.get(
            "/akten/NICHT_VORHANDEN/stellungnahme/vorschau",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
