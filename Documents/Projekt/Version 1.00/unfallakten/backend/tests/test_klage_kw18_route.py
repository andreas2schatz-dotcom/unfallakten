"""
Bugfix KW-18: generiere_klageschrift() wirft ValueError, wenn weder Klaeger-
Beteiligter noch brauchbare Mandantendaten vorhanden sind ("Kein Klaeger
ermittelbar"). Die Route /akten/<az>/klage/generieren muss diesen Fall als
HTTP 422 beantworten statt in den generischen 500er-Zweig zu fallen.

Test-Strategie: identischer Harness wie test_klage_overrides_merge.py
(Temp-SQLite, echter Flask-Test-Client + Login, generiere_klageschrift wird
im Router-Modul gepatcht).
"""
import importlib
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"kw18_{test_id}.db")
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


class TestKW18RouteValueErrorWird422(unittest.TestCase):
    def setUp(self):
        global _tmp_dir

        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        self._old_db_path_env = os.environ.get("DB_PATH")
        self._old_upload_dir_env = os.environ.get("UPLOAD_DIR")

        self._tmp_dir = tempfile.mkdtemp(prefix="klage_kw18_")
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

    def test_valueerror_wird_422(self):
        import backend.routers.klage_routes as kr
        with mock.patch.object(
            kr, "generiere_klageschrift",
            side_effect=ValueError(
                "Kein Kläger ermittelbar – bitte Mandanten-/Parteidaten prüfen."
            ),
        ):
            resp = self.client.post(
                "/akten/44/22/klage/generieren",
                headers=self.headers,
                json={
                    "in_db": False,
                    "klage_config": {"beklagte": [], "positionen": []},
                    "overrides": {},
                },
            )
        self.assertEqual(resp.status_code, 422)
        self.assertIn("Kein Kläger ermittelbar", resp.get_json()["fehler"])


if __name__ == "__main__":
    unittest.main()
