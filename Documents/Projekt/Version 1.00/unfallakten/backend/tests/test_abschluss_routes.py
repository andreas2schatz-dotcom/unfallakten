"""Route-Tests: GET abschluss-uebersicht + PUT abschluss-status."""
import importlib
import os
import sys
import tempfile
import unittest

_tmp_dir = tempfile.mkdtemp(prefix="abschluss_routes_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"ar_{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    os.environ["UPLOAD_DIR"] = os.path.join(_tmp_dir, f"uploads_{test_id}")

    import backend.db.database as db_mod
    import backend.models.benutzer as ben_mod
    import backend.models.akte as akte_mod
    import backend.models.dokument as dok_mod
    import backend.auth.jwt_handler as jwt_mod
    import backend.auth.middleware as mw_mod
    import backend.auth.service as svc_mod
    import backend.routers.auth_routes as routes_mod
    import backend.app as app_mod
    for m in (db_mod, ben_mod, akte_mod, dok_mod,
              jwt_mod, mw_mod, svc_mod, routes_mod, app_mod):
        importlib.reload(m)
    app = app_mod.erstelle_app({"TESTING": True})
    return app.test_client()


def _auth_header(client):
    r = client.post("/auth/login", json={
        "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
        "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!"),
    })
    assert r.status_code == 200, f"Login failed: {r.get_json()}"
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


def _seed_akte(az="55/26"):
    from backend.db.database import get_connection
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO unfallakte (az, unfalldatum, status) "
            "VALUES (?, '2026-01-10', 'offen')", (az,))


class TestAbschlussRouten(unittest.TestCase):
    def setUp(self):
        self.client = _setup(self._testMethodName)
        self.headers = _auth_header(self.client)
        _seed_akte()

    def test_get_uebersicht_liefert_objekt(self):
        r = self.client.get("/akten/55/26/abschluss-uebersicht",
                            headers=self.headers)
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertEqual(body["modus"], "sachstand")
        self.assertIn("positionen", body)
        self.assertIn("summen", body)
        self.assertIn("plausi", body)

    def test_get_uebersicht_404_bei_unbekannter_akte(self):
        r = self.client.get("/akten/99/99/abschluss-uebersicht",
                            headers=self.headers)
        self.assertEqual(r.status_code, 404)

    def test_put_status_upsert_und_modus_wechsel(self):
        r = self.client.put("/akten/55/26/abschluss-status",
                            headers=self.headers,
                            json={"schluss_typ": "endgueltig",
                                  "schluss_text": "Erledigt."})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["abschluss_status"]["schluss_typ"],
                         "endgueltig")
        r2 = self.client.get("/akten/55/26/abschluss-uebersicht",
                             headers=self.headers)
        self.assertEqual(r2.get_json()["modus"], "abschluss")
        r3 = self.client.put("/akten/55/26/abschluss-status",
                             headers=self.headers,
                             json={"schluss_typ": "offen"})
        self.assertEqual(r3.status_code, 200)

    def test_put_status_422_bei_ungueltigem_typ(self):
        r = self.client.put("/akten/55/26/abschluss-status",
                            headers=self.headers,
                            json={"schluss_typ": "quatsch"})
        self.assertEqual(r.status_code, 422)


if __name__ == "__main__":
    unittest.main()
