"""
Regressionstest fuer den kritischen Bug im Code-Review von Task 4
(globaler Vertreter-Lookup im Klage-Serializer).

_wende_globalen_vertreter_an(conn, alle_bet) wurde in hole_klage_daten()
ausserhalb des "with get_connection() as conn:"-Blocks aufgerufen -> conn
war zu diesem Zeitpunkt bereits geschlossen (contextmanager-finally), was
bei jedem Aufruf mit synthetischem GHPV-Eintrag zu einem
sqlite3.ProgrammingError und damit zu HTTP 500 fuehrte.

Test-Strategie: identischer Harness wie test_klage_kw18_route.py (Temp-
SQLite, echter Flask-Test-Client + Login). _lade_wdm_klage_vars wird im
Router-Modul gepatcht, um ohne RA-Micro einen synthetischen GHPV-Eintrag
zu erzwingen (WDM liefert eine Haftpflichtversicherung, aber es existiert
kein eigenstaendiger Versicherungs-Beteiligter in SQLite).
"""
import importlib
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

FIRMA = "ADAC Autoversicherung AG"


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"fvroute_{test_id}.db")
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
    from backend.models.firmen_vertreter import upsert_firmen_vertreter
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO unfallakte (az, unfalldatum, status) "
            "VALUES ('44/22', '2022-04-27', 'offen')"
        )
        upsert_firmen_vertreter(conn, FIRMA, "Stefan Daehne", "Vorstand")

    return client


def _auth_header(client):
    r = client.post("/auth/login", json={
        "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
        "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!"),
    })
    assert r.status_code == 200, f"Login failed: {r.get_json()}"
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


class TestKlageDatenRouteGlobalerVertreter(unittest.TestCase):
    def setUp(self):
        global _tmp_dir

        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        self._old_db_path_env = os.environ.get("DB_PATH")
        self._old_upload_dir_env = os.environ.get("UPLOAD_DIR")

        self._tmp_dir = tempfile.mkdtemp(prefix="klage_fvroute_")
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

    def test_synthetischer_ghpv_route_liefert_200_mit_globalem_vertreter(self):
        import backend.routers.klage_routes as kr

        with mock.patch.object(
            kr, "_lade_wdm_klage_vars",
            return_value={"varG-HV": FIRMA},
        ):
            resp = self.client.get(
                "/akten/44/22/klage/daten", headers=self.headers
            )

        self.assertEqual(
            resp.status_code, 200,
            f"Erwartet 200, bekam {resp.status_code}: {resp.get_json()}"
        )
        daten = resp.get_json()
        beklagte = [
            b for b in daten.get("beteiligte", [])
            if b.get("kuerzel") == "GHPV"
        ]
        self.assertTrue(beklagte, "Synthetischer GHPV-Eintrag fehlt in der Antwort.")
        self.assertEqual(beklagte[0]["vertreter_name"], "Stefan Daehne")
        self.assertEqual(beklagte[0]["vertreter_funktion"], "Vorstand")


if __name__ == "__main__":
    unittest.main()
