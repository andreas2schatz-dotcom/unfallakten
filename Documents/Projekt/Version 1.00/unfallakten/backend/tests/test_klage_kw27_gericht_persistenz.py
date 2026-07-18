"""
Bugfix KW-27: Gericht-Persistenz-Rueckweg.

PUT /akten/<az>/klage/gericht speichert das vom Nutzer bestaetigte Gericht als
Beteiligten mit rolle='gericht' in SQLite. GET /akten/<az>/klage/daten soll
dieses gespeicherte Gericht danach als gericht_vorschlag mit quelle=="akte"
zurueckliefern (Prio 1a), statt auf RA-Micro/Unfallort-Fallback (Prio 1b/2)
auszuweichen.

Befund vor dem Fix: Die Rollenzuweisung markiert die Gericht-Zeile als
rolle_klage="nicht_partei"; der direkt danach folgende Filter
"alle_bet = [b for b in alle_bet if b.get('rolle_klage') in (...)]" wirft die
Gericht-Zeile raus, BEVOR der Prio-1a-Loop (der nach rolle=='gericht' sucht)
sie sehen kann -> Loop findet nie etwas, Fallback gewinnt immer.

Test-Strategie: identischer Harness wie test_klage_kw18_route.py (Temp-SQLite,
echter Flask-Test-Client + Login).
"""
import importlib
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"kw27_{test_id}.db")
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
            "VALUES ('61/26', '2026-02-01', 'offen')"
        )

    return client


def _auth_header(client):
    r = client.post("/auth/login", json={
        "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
        "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!"),
    })
    assert r.status_code == 200, f"Login failed: {r.get_json()}"
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


class TestGerichtPersistenz(unittest.TestCase):
    def setUp(self):
        global _tmp_dir

        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        self._old_db_path_env = os.environ.get("DB_PATH")
        self._old_upload_dir_env = os.environ.get("UPLOAD_DIR")

        self._tmp_dir = tempfile.mkdtemp(prefix="klage_kw27_")
        _tmp_dir = self._tmp_dir

        self.client = _setup(self._testMethodName)
        self.headers = _auth_header(self.client)
        self.az = "61/26"

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

    def _gericht_speichern(self):
        return self.client.put(
            f"/akten/{self.az}/klage/gericht",
            json={
                "name": "Amtsgericht Testhausen",
                "strasse": "Gerichtsweg 1",
                "plz": "63065",
                "ort": "Testhausen",
            },
            headers=self.headers,
        )

    def test_gespeichertes_gericht_kommt_als_akte_vorschlag_zurueck(self):
        r = self._gericht_speichern()
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))

        r2 = self.client.get(f"/akten/{self.az}/klage/daten", headers=self.headers)
        self.assertEqual(r2.status_code, 200, r2.get_data(as_text=True))
        d = r2.get_json()

        self.assertEqual(d["gericht_quelle"], "akte")
        self.assertIsNotNone(d["gericht_vorschlag"])
        self.assertEqual(d["gericht_vorschlag"]["name"], "Amtsgericht Testhausen")
        self.assertEqual(d["gericht_vorschlag"]["quelle"], "akte")

    def test_gericht_zeile_erscheint_nicht_in_beteiligten(self):
        r = self._gericht_speichern()
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))

        r2 = self.client.get(f"/akten/{self.az}/klage/daten", headers=self.headers)
        self.assertEqual(r2.status_code, 200, r2.get_data(as_text=True))
        d = r2.get_json()

        namen = [b.get("name") for b in d.get("beteiligte", [])]
        self.assertNotIn("Amtsgericht Testhausen", namen)


if __name__ == "__main__":
    unittest.main()
