"""
Bugfix KW-39 (im Rahmen der PRD-33-Task-2-Review vorgezogen): Vorsteuer-Divergenz
Nebenkosten-Gruppen.

_baue_tabelle() rechnet Mietwagen/SV-Kosten/Abschlepp/Standkosten/An-Abmeldung
bei vorsteuer=True netto (_netto_oder_brutto), waehrend pos_definitionen im
GET /akten/<az>/klage/daten-Endpunkt (klage_routes.py) diese Keys immer brutto
lieferte -> betragOriginal/Antrag 1 (brutto) != Tabelle (netto).

Test-Strategie: Flask-Test-Client + Login, Temp-SQLite (wie
test_klage_s2_unkostenpauschale.py), echter GET-Call gegen
/akten/<az>/klage/daten, "positionen"-Liste inspiziert.
"""
import importlib
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"kw39_{test_id}.db")
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
            "VALUES ('55/26', '2026-01-10', 'offen')"
        )

    return client


def _auth_header(client):
    r = client.post("/auth/login", json={
        "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
        "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!"),
    })
    assert r.status_code == 200, f"Login failed: {r.get_json()}"
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


class TestKW39PosDefinitionenVorsteuerbewusst(unittest.TestCase):
    def setUp(self):
        global _tmp_dir

        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        self._old_db_path_env = os.environ.get("DB_PATH")
        self._old_upload_dir_env = os.environ.get("UPLOAD_DIR")

        self._tmp_dir = tempfile.mkdtemp(prefix="klage_kw39_")
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

    def _erfasse_mandant(self, vorsteuer: str):
        from backend.models.schaden import erstelle_beteiligten
        from backend.db.database import get_connection
        b = erstelle_beteiligten(
            "55/26", "mandant", "Mustermann", vorname="Max",
            anschrift="Musterstr. 1", plz="63067", ort="Offenbach",
        )
        with get_connection() as conn:
            conn.execute(
                "UPDATE beteiligte SET vorsteuer = ? WHERE id = ?",
                (vorsteuer, b.id),
            )

    def _erfasse_nebenkosten(self):
        from backend.models.schaden import setze_schadenpositionen
        setze_schadenpositionen(
            "55/26",
            sv_kosten_netto=200.0, sv_kosten_ust=38.0, sv_kosten=999.0,
            mietwagenkosten_netto=100.0, mietwagenkosten_ust=19.0, mietwagenkosten=999.0,
            abschleppkosten_netto=50.0, abschleppkosten_ust=9.5, abschleppkosten=999.0,
            standkosten_netto=30.0, standkosten_ust=5.7, standkosten=999.0,
            anabmeldekosten_netto=20.0, anabmeldekosten_ust=3.8, anabmeldekosten=999.0,
        )

    def _positionen_by_key(self):
        resp = self.client.get("/akten/55/26/klage/daten", headers=self.headers)
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        data = resp.get_json()
        return {p["key"]: p["betrag"] for p in data["positionen"]}

    def test_vorsteuer_mandant_liefert_netto(self):
        self._erfasse_mandant("J")
        self._erfasse_nebenkosten()

        pos = self._positionen_by_key()

        self.assertEqual(pos["sv_kosten"], 200.0)
        self.assertEqual(pos["mietwagenkosten"], 100.0)
        self.assertEqual(pos["abschleppkosten"], 50.0)
        self.assertEqual(pos["standkosten"], 30.0)
        self.assertEqual(pos["anabmeldekosten"], 20.0)

    def test_nicht_vorsteuer_mandant_liefert_brutto(self):
        self._erfasse_mandant("N")
        self._erfasse_nebenkosten()

        pos = self._positionen_by_key()

        self.assertEqual(pos["sv_kosten"], 238.0)
        self.assertEqual(pos["mietwagenkosten"], 119.0)
        self.assertEqual(pos["abschleppkosten"], 59.5)
        self.assertEqual(pos["standkosten"], 35.7)
        self.assertEqual(pos["anabmeldekosten"], 23.8)


if __name__ == "__main__":
    unittest.main()
