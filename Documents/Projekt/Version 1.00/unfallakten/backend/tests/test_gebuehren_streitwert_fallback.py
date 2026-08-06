"""
Regressionstests: Streitwert-Fallback im Gebührenassistenten (PRD-28).

Der Fallback (kein Forderungsschreiben → Summe aus schadenpositionen) enthielt
einen toten COALESCE: rep_rechnung_brutto ist NOT NULL DEFAULT 0.0, daher griff
rep_gutachten_netto nie — bei fiktiver Abrechnung fehlte der Fahrzeugschaden.
Gefixt analog word_service._lade_gebuehren_kontext (>0-Vorrang-CASE).
Betroffen: gebuehren_routes.py (Anzeige) + gebuehren_word.py (Kostennote-DOCX).
"""
import importlib
import os
import sys
import tempfile
import unittest
import zipfile

_tmp_dir = tempfile.mkdtemp(prefix="gebuehren_fallback_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"gf_{test_id}.db")
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


def _seed(az, rep_gutachten_netto=0.0, rep_rechnung_brutto=None):
    from backend.db.database import get_connection
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO unfallakte (az, unfalldatum, status) "
            "VALUES (?, '2026-01-10', 'offen')", (az,))
        cols, vals = ["akte_id", "rep_gutachten_netto"], [az, rep_gutachten_netto]
        if rep_rechnung_brutto is not None:
            cols.append("rep_rechnung_brutto")
            vals.append(rep_rechnung_brutto)
        conn.execute(
            f"INSERT INTO schadenpositionen ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(vals))})", vals)


class TestStreitwertFallback(unittest.TestCase):
    def setUp(self):
        self.client = _setup(self._testMethodName)
        self.headers = _auth_header(self.client)

    def test_route_fiktiv_gutachten_fliesst_ein(self):
        _seed("66/26", rep_gutachten_netto=4000.0)
        r = self.client.get("/akten/66/26/gebuehren", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(r.get_json()["rvg"]["streitwert"], 4000.0)

    def test_route_rechnung_hat_vorrang(self):
        _seed("67/26", rep_gutachten_netto=3000.0, rep_rechnung_brutto=3570.0)
        r = self.client.get("/akten/67/26/gebuehren", headers=self.headers)
        streitwert = r.get_json()["rvg"]["streitwert"]
        self.assertGreaterEqual(streitwert, 3570.0)
        self.assertLess(streitwert, 6570.0)

    def test_kostennote_fiktiv_gegenstandswert_aus_gutachten(self):
        _seed("68/26", rep_gutachten_netto=4000.0)
        from backend.word.gebuehren_word import generiere_kostennote
        result = generiere_kostennote(
            "68/26", {"vuregel_id": "VU-01", "faktor_final": 1.3})
        self.assertTrue(result.get("dateiname"))
        from backend.db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT dateipfad FROM dokumente WHERE akte_id = '68/26' "
                "ORDER BY id DESC LIMIT 1").fetchone()
        self.assertIsNotNone(row)
        with zipfile.ZipFile(row["dateipfad"]) as z:
            xml = z.read("word/document.xml").decode("utf-8")
        self.assertIn("4.000,00", xml)


if __name__ == "__main__":
    unittest.main()
