"""
Unfallort im Unfalldetails-Reiter: editierbares Feld, aus WDM (varU-ORT)
vorbefuellt, gespeichert in unfallakte.unfallort (die unfalldetails-Tabelle
hat keine Orts-Spalte) -- exakt der Weg, den das Unfalldatum schon geht,
siehe test_unfalldetails_unfalldatum.py.

Bisher las das Backend varU-ORT zwar aus, legte den Wert aber nur in das
Anzeige-Feld _wdm_u_ort, das niemand verwendete. Geschrieben werden konnte
der Unfallort ausschliesslich bei der Aktenanlage.

Harness analog test_unfalldetails_unfalldatum.py (Temp-SQLite, echter
Flask-Test-Client + Login, _lade_wdm_klage_vars gepatcht statt RA-Micro).
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
    db_path = os.path.join(_tmp_dir, f"udort_{test_id}.db")
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


class TestUnfalldetailsUnfallort(unittest.TestCase):
    def setUp(self):
        global _tmp_dir
        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        self._old_db_path_env = os.environ.get("DB_PATH")
        self._old_upload_dir_env = os.environ.get("UPLOAD_DIR")
        self._tmp_dir = tempfile.mkdtemp(prefix="udort_")
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

    def _get(self, wdm, query=""):
        import backend.routers.klage_routes as kr
        with mock.patch.object(kr, "_lade_wdm_klage_vars", return_value=wdm):
            r = self.client.get(f"/akten/55/24/unfalldetails{query}", headers=self.headers)
        self.assertEqual(r.status_code, 200, r.get_json())
        return r.get_json()["unfalldetails"]

    def _put(self, nutzlast):
        import backend.routers.klage_routes as kr
        with mock.patch.object(kr, "_lade_wdm_klage_vars", return_value={}):
            r = self.client.put("/akten/55/24/unfalldetails",
                                json=nutzlast, headers=self.headers)
        self.assertEqual(r.status_code, 200, r.get_json())
        return r.get_json()["unfalldetails"]

    def _gespeicherter_ort(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            return conn.execute(
                "SELECT unfallort FROM unfallakte WHERE az='55/24'").fetchone()["unfallort"]

    def test_get_prefillt_unfallort_aus_wdm_wenn_db_leer(self):
        ud = self._get({"varU-ORT": "Heusenstamm"})
        self.assertEqual(ud["unfallort"], "Heusenstamm")

    def test_get_liefert_leeren_ort_wenn_weder_db_noch_wdm_etwas_haben(self):
        ud = self._get({})
        self.assertEqual(ud["unfallort"], "")

    def test_put_speichert_unfallort_in_unfallakte(self):
        self._put({"unfallort": "Theodor-Stern-Kai 1, Frankfurt am Main"})
        self.assertEqual(self._gespeicherter_ort(),
                         "Theodor-Stern-Kai 1, Frankfurt am Main")

    def test_gespeicherter_ort_hat_vorrang_vor_wdm_prefill(self):
        self._put({"unfallort": "Offenbach, Kaiserstr."})
        ud = self._get({"varU-ORT": "Heusenstamm"})
        self.assertEqual(ud["unfallort"], "Offenbach, Kaiserstr.")

    def test_force_wdm_ueberschreibt_den_gespeicherten_ort(self):
        """Der Knopf "WDM laden" holt den Ort bewusst frisch aus RA-Micro."""
        self._put({"unfallort": "Offenbach, Kaiserstr."})
        ud = self._get({"varU-ORT": "Heusenstamm"}, query="?force_wdm=1")
        self.assertEqual(ud["unfallort"], "Heusenstamm")

    def test_put_ohne_das_feld_laesst_den_gespeicherten_ort_stehen(self):
        """Teil-Speicherungen anderer Masken duerfen den Ort nicht loeschen."""
        self._put({"unfallort": "Offenbach, Kaiserstr."})
        self._put({"schilderung": "Auffahrunfall"})
        self.assertEqual(self._gespeicherter_ort(), "Offenbach, Kaiserstr.")

    def test_put_gibt_den_gespeicherten_ort_zurueck(self):
        ud = self._put({"unfallort": "  Dietzenbach  "})
        self.assertEqual(ud["unfallort"], "Dietzenbach")


if __name__ == "__main__":
    unittest.main()
