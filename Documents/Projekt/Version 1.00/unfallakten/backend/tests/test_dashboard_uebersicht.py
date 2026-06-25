"""
Test-Suite für Dashboard-Übersicht-Endpoints
============================================
Tests für die neuen Action-Board Endpoints:
  GET /dashboard/onboarding-offen
  GET /dashboard/nachrichten-neu
"""

import os
import sys
import unittest
import tempfile

_tmp_dir = tempfile.mkdtemp()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _setup(test_id: str):
    """Richtet eine frische DB + Flask-App für einen Test ein."""
    db_path = os.path.join(_tmp_dir, f"dbu_{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    os.environ["JWT_SECRET_KEY"] = "test-secret-key-minimum-32-characters!!"
    os.environ["FLASK_SECRET_KEY"] = "test-flask-secret-key-minimum-32-characters!!"

    import importlib
    import backend.db.database as db_mod
    import backend.models.benutzer as ben_mod
    import backend.models.akte as akte_mod
    import backend.models.schaden as schaden_mod
    import backend.models.dokument as dok_mod
    import backend.auth.jwt_handler as jwt_mod
    import backend.auth.middleware as mw_mod
    import backend.auth.service as svc_mod
    import backend.routers.auth_routes as routes_mod
    import backend.app as app_mod

    for m in (db_mod, ben_mod, akte_mod, schaden_mod,
              dok_mod, jwt_mod, mw_mod, svc_mod, routes_mod, app_mod):
        importlib.reload(m)

    app = app_mod.erstelle_app({"TESTING": True})
    client = app.test_client()

    return client, jwt_mod


class TestDashboardUebersicht(unittest.TestCase):
    """Tests für /dashboard/onboarding-offen und /dashboard/nachrichten-neu"""

    def setUp(self):
        self.client, self.jwt = _setup(f"dbu_{self._testMethodName}")
        # App erstellt automatisch einen Default-Admin:
        # Email: koch@anwalt-offenbach.de
        # Passwort: Kanzlei2024!

    def _auth_header(self):
        """Gibt Authorization-Header mit gültigem Token zurück."""
        r = self.client.post("/auth/login", json={
            "email": "koch@anwalt-offenbach.de", "passwort": "Kanzlei2024!"
        })
        if r.status_code != 200:
            raise RuntimeError(f"Login failed: {r.status_code} - {r.get_json()}")
        data = r.get_json()
        return {"Authorization": f"Bearer {data['access_token']}"}

    def test_onboarding_offen_gibt_liste_zurueck(self):
        """Endpoint /dashboard/onboarding-offen liefert eine Liste."""
        headers = self._auth_header()
        resp = self.client.get("/dashboard/onboarding-offen", headers=headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("eintraege", data)
        self.assertIsInstance(data["eintraege"], list)

    def test_onboarding_offen_ohne_token_401(self):
        """Ohne Token sollte 401 zurückgegeben werden."""
        resp = self.client.get("/dashboard/onboarding-offen")
        self.assertEqual(resp.status_code, 401)

    def test_nachrichten_neu_gibt_liste_zurueck(self):
        """Endpoint /dashboard/nachrichten-neu liefert eine Liste."""
        headers = self._auth_header()
        resp = self.client.get("/dashboard/nachrichten-neu", headers=headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("eintraege", data)
        self.assertIsInstance(data["eintraege"], list)

    def test_nachrichten_neu_ohne_token_401(self):
        """Ohne Token sollte 401 zurückgegeben werden."""
        resp = self.client.get("/dashboard/nachrichten-neu")
        self.assertEqual(resp.status_code, 401)

    def test_ramicro_fristen_gibt_liste_zurueck(self):
        """Endpoint /dashboard/ramicro-fristen liefert eintraege-Liste (leer wenn RA-MICRO nicht verbunden)."""
        headers = self._auth_header()
        resp = self.client.get("/dashboard/ramicro-fristen", headers=headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("eintraege", data)
        self.assertIsInstance(data["eintraege"], list)

    def test_ramicro_fristen_ohne_token_401(self):
        """Ohne Token sollte 401 zurückgegeben werden."""
        resp = self.client.get("/dashboard/ramicro-fristen")
        self.assertEqual(resp.status_code, 401)

    def test_nachrichten_neu_entries_haben_log_id(self):
        """Jeder Eintrag in nachrichten-neu muss ein log_id-Feld haben."""
        from backend.db.database import get_connection
        # Testdaten anlegen: Akte + email_import_log-Eintrag
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, status) VALUES (?, ?)",
                ("99/99", "offen")
            )
            # email_import_log braucht message_id UNIQUE
            conn.execute(
                """INSERT INTO email_import_log
                   (message_id, betreff, absender, empfangen_am, akte_id, status, email_typ)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                ("test-msg-id-123", "Testbetreff", "test@rv.de", "2026-06-12 10:00:00", "99/99", "zugeordnet", "sonstiges")
            )
            conn.commit()

        headers = self._auth_header()
        resp = self.client.get("/dashboard/nachrichten-neu", headers=headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        eintraege = data["eintraege"]
        self.assertTrue(len(eintraege) > 0, "Mindestens ein Eintrag erwartet")
        for e in eintraege:
            self.assertIn("log_id", e, f"log_id fehlt in Eintrag: {e}")
            self.assertIsNotNone(e["log_id"])


    def test_termine_heute_gibt_liste_zurueck(self):
        """GET /dashboard/termine-heute liefert eintraege-Liste (leer wenn RA-MICRO nicht verbunden)."""
        headers = self._auth_header()
        resp = self.client.get("/dashboard/termine-heute", headers=headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("eintraege", data)
        self.assertIsInstance(data["eintraege"], list)

    def test_termine_heute_ohne_token_401(self):
        """Ohne Token sollte 401 zurückgegeben werden."""
        resp = self.client.get("/dashboard/termine-heute")
        self.assertEqual(resp.status_code, 401)

    def test_termine_heute_felder(self):
        """Wenn Einträge vorhanden, müssen az, termin_art, termin_datum, tage_bis vorhanden sein."""
        headers = self._auth_header()
        resp = self.client.get("/dashboard/termine-heute", headers=headers)
        data = resp.get_json()
        for e in data["eintraege"]:
            for feld in ("az", "mandant", "kurzbezeichnung", "termin_art", "termin_datum", "uhrzeit", "tage_bis"):
                self.assertIn(feld, e, f"Feld '{feld}' fehlt in Eintrag: {e}")


if __name__ == "__main__":
    unittest.main()
