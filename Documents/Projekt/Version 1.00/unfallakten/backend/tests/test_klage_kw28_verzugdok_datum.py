"""
Bugfix KW-28 (Fix-Wave, Review-Finding 1): verzug_dokumente ohne Schreibdatum.

Befund: Die verzug_dokumente-Query in klage_routes.py lieferte nur
id/dateiname/dokumentenklasse/hochgeladen_am. hochgeladen_am ist ein reiner
Upload-Zeitstempel, kein Schreibdatum. Das tatsaechliche Schreibdatum steht
(sofern das Dokument als Forderungsschreiben ueber erfasse_forderung() erzeugt
wurde) in forderung_positionen.datum, verknuepft ueber dokument_id.

Fix: Query um ein Feld 'datum' erweitern - MAX(forderung_positionen.datum)
fuer das jeweilige Dokument, NULL wenn keine forderung_position existiert
(z.B. gescanntes Fremdschreiben ohne erfasse_forderung()-Aufruf).

Test-Strategie: identischer Harness wie test_klage_kw27_gericht_persistenz.py
(Temp-SQLite, echter Flask-Test-Client + Login).
"""
import importlib
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"kw28_{test_id}.db")
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


class TestVerzugDokDatum(unittest.TestCase):
    def setUp(self):
        global _tmp_dir

        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        self._old_db_path_env = os.environ.get("DB_PATH")
        self._old_upload_dir_env = os.environ.get("UPLOAD_DIR")

        self._tmp_dir = tempfile.mkdtemp(prefix="klage_kw28_")
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

    def _verzug_dok_by_id(self, dok_id):
        r = self.client.get(f"/akten/{self.az}/klage/daten", headers=self.headers)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        d = r.get_json()
        treffer = [v for v in d.get("verzug_dokumente", []) if v["id"] == dok_id]
        self.assertEqual(len(treffer), 1)
        return treffer[0]

    def test_schreibdatum_aus_forderung_position_statt_upload_zeitstempel(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO dokumente (id, akte_id, dateiname, dateipfad, "
                " typ, dokumentenklasse, hochgeladen_am) "
                "VALUES (42, '61/26', 'forderung.docx', '/tmp/forderung.docx', "
                " 'forderungsschreiben', 'forderungsschreiben', '2026-06-15 09:30:00')"
            )
            conn.execute(
                "INSERT INTO forderung_positionen "
                "(akte_id, dokument_id, datum, position_key, position_label, betrag_gefordert) "
                "VALUES ('61/26', 42, '2026-06-01', 'reparaturkosten', 'Reparaturkosten', 5000.0)"
            )

        vdok = self._verzug_dok_by_id(42)
        self.assertEqual(vdok["datum"], "2026-06-01")
        self.assertNotEqual(vdok["datum"], "2026-06-15 09:30:00")

    def test_mehrere_positionen_liefern_das_spaeteste_datum(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO dokumente (id, akte_id, dateiname, dateipfad, "
                " typ, dokumentenklasse, hochgeladen_am) "
                "VALUES (43, '61/26', 'forderung2.docx', '/tmp/forderung2.docx', "
                " 'forderungsschreiben', 'forderungsschreiben', '2026-06-20 09:30:00')"
            )
            conn.execute(
                "INSERT INTO forderung_positionen "
                "(akte_id, dokument_id, datum, position_key, position_label, betrag_gefordert) "
                "VALUES ('61/26', 43, '2026-06-01', 'reparaturkosten', 'Reparaturkosten', 5000.0)"
            )
            conn.execute(
                "INSERT INTO forderung_positionen "
                "(akte_id, dokument_id, datum, position_key, position_label, betrag_gefordert) "
                "VALUES ('61/26', 43, '2026-06-03', 'wertminderung', 'Wertminderung', 500.0)"
            )

        vdok = self._verzug_dok_by_id(43)
        self.assertEqual(vdok["datum"], "2026-06-03")

    def test_ohne_forderung_position_ist_datum_null(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO dokumente (id, akte_id, dateiname, dateipfad, "
                " typ, dokumentenklasse, hochgeladen_am) "
                "VALUES (44, '61/26', 'mahnschreiben_scan.pdf', '/tmp/mahn.pdf', "
                " 'sonstiges', 'mahnschreiben', '2026-06-20 09:30:00')"
            )

        vdok = self._verzug_dok_by_id(44)
        self.assertIsNone(vdok["datum"])


if __name__ == "__main__":
    unittest.main()
