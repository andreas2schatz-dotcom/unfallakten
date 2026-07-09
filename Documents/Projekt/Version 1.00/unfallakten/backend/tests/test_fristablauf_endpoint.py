"""
Tests fuer GET /system/fristablauf/manual (P1.6).

Manueller Trigger fuer den Fristablauf-Scheduler-Job. Nur Admin.
Liefert die Anzahl neu erzeugter Ereignisse.
"""
import json
import os
import sys
import unittest
from datetime import date, timedelta
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _make_app():
    os.environ["FLASK_SECRET_KEY"] = "test-fristablauf-endpoint"
    from backend.app import erstelle_app
    return erstelle_app(test_config={"TESTING": True})


class TestFristablaufEndpoint(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = _make_app()
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            from backend.auth.jwt_handler import erstelle_access_token
            cls.admin_token = erstelle_access_token(1, "admin")
            cls.sb_token = erstelle_access_token(1, "sachbearbeiter")

    def _auth(self, admin: bool = True):
        tok = self.admin_token if admin else self.sb_token
        return {"Authorization": f"Bearer {tok}"}

    def test_ohne_auth_ist_401(self):
        resp = self.client.get("/system/fristablauf/manual")
        self.assertEqual(resp.status_code, 401)

    def test_ohne_admin_ist_403(self):
        resp = self.client.get(
            "/system/fristablauf/manual", headers=self._auth(admin=False),
        )
        self.assertEqual(resp.status_code, 403)

    def test_mit_admin_liefert_verarbeitet_zaehler(self):
        with mock.patch(
            "backend.routers.system_routes.verarbeite_faellige_todos",
            return_value=3,
        ) as m:
            resp = self.client.get(
                "/system/fristablauf/manual", headers=self._auth(admin=True),
            )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data.get("verarbeitet"), 3)
        m.assert_called_once()


if __name__ == "__main__":
    unittest.main()
