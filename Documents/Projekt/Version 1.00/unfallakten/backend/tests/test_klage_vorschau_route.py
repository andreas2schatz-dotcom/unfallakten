"""
Task 5: POST /akten/<az>/klage/vorschau liefert eine strukturierte Text-
Vorschau der Klageschrift (kein DB-Write).

Test-Strategie: identischer Harness wie test_klage_kw18_route.py
(Temp-SQLite, echter Flask-Test-Client + Login).
"""
import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"vorschau_{test_id}.db")
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
    client = app.test_client()

    from backend.db.database import get_connection
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO unfallakte (az, unfalldatum, status) "
            "VALUES ('44/22', '2022-04-27', 'offen')"
        )

    return client


def _auth_header(client):
    r = client.post("/auth/login", json={
        "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
        "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!"),
    })
    assert r.status_code == 200, f"Login failed: {r.get_json()}"
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


class TestKlageVorschauRoute(unittest.TestCase):
    def setUp(self):
        global _tmp_dir

        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        self._old_db_path_env = os.environ.get("DB_PATH")
        self._old_upload_dir_env = os.environ.get("UPLOAD_DIR")

        self._tmp_dir = tempfile.mkdtemp(prefix="klage_vorschau_")
        _tmp_dir = self._tmp_dir

        self.client = _setup(self._testMethodName)
        self.headers = _auth_header(self.client)

    def tearDown(self):
        import backend.db.database as _db

        _db.DB_PATH = self._alt_db_path

        if self._old_db_path_env is not None:
            os.environ["DB_PATH"] = self._old_db_path_env
        else:
            os.environ.pop("DB_PATH", None)

        if self._old_upload_dir_env is not None:
            os.environ["UPLOAD_DIR"] = self._old_upload_dir_env
        else:
            os.environ.pop("UPLOAD_DIR", None)

        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def test_vorschau_liefert_abschnitte_json(self):
        body = {"klage_config": {
            "beklagte": [
                {"rolle_klage": "klaeger", "vorname": "Max", "name": "Mustermann",
                 "anschrift": "Musterstr. 1", "plz": "63067", "ort": "Offenbach",
                 "anrede": "1"},
                {"rolle_klage": "beklagter", "versicherung": "Test-Versicherung AG",
                 "anschrift": "Teststr. 2", "plz": "12345", "ort": "Teststadt"},
            ],
            "positionen": [{"key": "fahrzeugschaden", "label": "Fahrzeugschaden",
                            "betrag": 3000.0, "betragOriginal": 3000.0, "checked": True}],
        }}
        resp = self.client.post(
            "/akten/44/22/klage/vorschau",
            data=json.dumps(body), content_type="application/json",
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200, resp.get_json())
        data = resp.get_json()
        self.assertIn("abschnitte", data)
        keys = [a["key"] for a in data["abschnitte"]]
        self.assertIn("sachverhalt", keys)
        self.assertTrue(any(a["editierbar"] for a in data["abschnitte"]))

    def test_unbekannte_akte_404(self):
        resp = self.client.post(
            "/akten/999-99/klage/vorschau",
            data=json.dumps({"klage_config": {}}),
            content_type="application/json", headers=self.headers,
        )
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
