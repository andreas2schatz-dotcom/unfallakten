"""
Tests fuer GET /system/registry/status (S1.5).

Liefert {ok, version, klassen: [...], fehler: [...]}.
Trivial testbar mit pytest.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _make_app():
    os.environ["FLASK_SECRET_KEY"] = "test-registry-status"
    from backend.app import erstelle_app
    return erstelle_app(test_config={"TESTING": True})


class TestRegistryStatusEndpoint(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = _make_app()
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            from backend.db.database import get_connection
            from backend.auth.jwt_handler import erstelle_access_token
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT id FROM benutzer WHERE aktiv=1 LIMIT 1"
                ).fetchone()
                benutzer_id = row["id"] if row else 1
            cls.token = erstelle_access_token(benutzer_id, "admin")

    def _auth(self):
        return {"Authorization": f"Bearer {self.token}"}

    def test_status_ok_liefert_pflichtfelder(self):
        resp = self.client.get("/system/registry/status", headers=self._auth())
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        for feld in ("ok", "version", "klassen", "fehler"):
            self.assertIn(feld, data)
        self.assertTrue(data["ok"])
        self.assertIsInstance(data["version"], str)
        self.assertGreater(len(data["version"]), 0)
        self.assertIsInstance(data["klassen"], list)
        self.assertIsInstance(data["fehler"], list)

    def test_status_enthaelt_alle_startklassen(self):
        resp = self.client.get("/system/registry/status", headers=self._auth())
        data = json.loads(resp.data)
        erwartet = {
            "gutachten", "abrechnungsschreiben", "pruefbericht",
            "rechnung", "sv_rechnung", "abschlepprechnung",
            "standkostenrechnung", "sonstiges",
        }
        self.assertEqual(set(data["klassen"]), erwartet)

    def test_status_ohne_auth_ist_401(self):
        resp = self.client.get("/system/registry/status")
        self.assertEqual(resp.status_code, 401)


if __name__ == "__main__":
    unittest.main()
