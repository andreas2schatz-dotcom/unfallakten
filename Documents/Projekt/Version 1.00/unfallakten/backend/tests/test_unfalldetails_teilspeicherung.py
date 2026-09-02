"""
PUT /akten/<az>/unfalldetails darf nur die Felder anfassen, die der Client
auch geschickt hat.

Bisher schrieb der UPDATE-Zweig ALLE Textfelder, fehlende als NULL. Die
Maske sendet aktivlegitimation_typ/-freigabe nie; beide Spalten sind
NOT NULL. Das erste Speichern lief deshalb (INSERT laesst None weg), jedes
weitere Speichern derselben Akte endete in einem 500er --
"NOT NULL constraint failed: unfalldetails.aktivlegitimation_typ".
Nebenbei loeschte eine Teil-Speicherung alle nicht gesendeten Felder.
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
    db_path = os.path.join(_tmp_dir, f"udteil_{test_id}.db")
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
            "INSERT INTO unfallakte (az, unfallort, status) "
            "VALUES ('55/24', '', 'offen')"
        )
    return client


def _auth_header(client):
    r = client.post("/auth/login", json={
        "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
        "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!"),
    })
    assert r.status_code == 200, f"Login failed: {r.get_json()}"
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


class TestUnfalldetailsTeilspeicherung(unittest.TestCase):
    def setUp(self):
        global _tmp_dir
        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        self._old_db_path_env = os.environ.get("DB_PATH")
        self._old_upload_dir_env = os.environ.get("UPLOAD_DIR")
        self._tmp_dir = tempfile.mkdtemp(prefix="udteil_")
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

    def _put(self, nutzlast, erwarte=200):
        import backend.routers.klage_routes as kr
        with mock.patch.object(kr, "_lade_wdm_klage_vars", return_value={}):
            r = self.client.put("/akten/55/24/unfalldetails",
                                json=nutzlast, headers=self.headers)
        self.assertEqual(r.status_code, erwarte, r.get_json())
        return r.get_json().get("unfalldetails", {})

    def _zeile(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            return dict(conn.execute(
                "SELECT * FROM unfalldetails WHERE akte_id='55/24'").fetchone())

    # Die Maske schickt genau diese Schluessel -- ohne aktivlegitimation_*.
    MASKE = {
        "schilderung": "Auffahrunfall", "zeuge_1": "", "zeuge_1_anschrift": "",
        "zeuge_2": "", "zeuge_2_anschrift": "", "zeuge_3": "", "zeuge_3_anschrift": "",
        "ermittlungsakte_az": "", "ermittlungsakte_behoerde": "", "ermittlungsakte_ort": "",
        "fahrer_mandant": "", "fahrer_gegner": "", "haftungsbegruendung": "",
        "vorsteuerabzug": False, "haftungsquote": 100, "unfalldatum": "",
    }

    def test_zweites_speichern_derselben_akte_liefert_keinen_serverfehler(self):
        self._put(dict(self.MASKE))
        self._put(dict(self.MASKE, schilderung="Auffahrunfall, korrigiert"))
        self.assertEqual(self._zeile()["schilderung"], "Auffahrunfall, korrigiert")

    def test_aktivlegitimation_behaelt_ihren_vorgabewert(self):
        self._put(dict(self.MASKE))
        self._put(dict(self.MASKE))
        zeile = self._zeile()
        self.assertEqual(zeile["aktivlegitimation_typ"], "eigentum")
        self.assertEqual(zeile["aktivlegitimation_freigabe"], "freigabe")

    def test_nicht_gesendete_felder_bleiben_stehen(self):
        self._put({"zeuge_1": "Meier", "schilderung": "Auffahrunfall"})
        self._put({"schilderung": "Auffahrunfall, korrigiert"})
        self.assertEqual(self._zeile()["zeuge_1"], "Meier")

    def test_leer_gesendetes_feld_wird_weiterhin_geloescht(self):
        self._put({"zeuge_1": "Meier"})
        self._put({"zeuge_1": ""})
        self.assertIsNone(self._zeile()["zeuge_1"])

    def test_haftungsquote_bleibt_ohne_das_feld_erhalten(self):
        self._put({"haftungsquote": 75})
        self._put({"schilderung": "Auffahrunfall"})
        self.assertEqual(self._zeile()["haftungsquote"], 75.0)

    def test_vorsteuerabzug_bleibt_ohne_das_feld_erhalten(self):
        self._put({"vorsteuerabzug": True})
        self._put({"schilderung": "Auffahrunfall"})
        self.assertEqual(self._zeile()["vorsteuerabzug"], 1)


if __name__ == "__main__":
    unittest.main()
