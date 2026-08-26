"""
Belege-Endpunkte liefern die nutzersichtbare Dokument-Bezeichnung mit.

Hintergrund: Dokumente aus der Intake-Pipeline tragen als ``dateiname``
den SHA-256-Hash. Fuer die Beleg-Zuordnung in der SchadenSection braucht
das Frontend die ``bezeichnung`` (z. B. "Gutachten AXA vom 30.06.2026").
"""
import importlib
import os
import sys
import tempfile
import unittest

_tmp_dir = tempfile.mkdtemp(prefix="belege_bez_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"bb_{test_id}.db")
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


_HASH_NAME = "6ac609eab7a73ba1ff5d1cdf3476c842732eeb2e07c9ce56f45bf881cfad58ac.pdf"


def _seed(az="44/22", klasse="sv_rechnung",
          bezeichnung="Rechnung SV-HO vom 18.06.2026 (992,34 EUR)"):
    from backend.db.database import get_connection
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO unfallakte (az, unfalldatum, status) "
            "VALUES (?, '2022-04-27', 'offen')", (az,),
        )
        cur = conn.execute(
            "INSERT INTO dokumente "
            "(akte_id, dateiname, dateipfad, dateityp, typ, "
            " dokumentenklasse, bezeichnung) "
            "VALUES (?, ?, 'x', 'pdf', 'sonstiges', ?, ?)",
            (az, _HASH_NAME, klasse, bezeichnung),
        )
        conn.commit()
        return cur.lastrowid


class TestBelegeListeBezeichnung(unittest.TestCase):

    def test_liste_liefert_bezeichnung(self):
        client = _setup("liste")
        kopf = _auth_header(client)
        dok_id = _seed()

        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO schadenposition_belege "
                "(akte_az, position_key, dokument_id, betrag_aus_beleg, notiz) "
                "VALUES ('44/22', 'sv_kosten', ?, 992.34, '')", (dok_id,),
            )
            conn.commit()

        r = client.get("/akten/44/22/belege", headers=kopf)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        belege = r.get_json()["belege"]
        self.assertEqual(len(belege), 1)
        self.assertEqual(belege[0]["dateiname"], _HASH_NAME)
        self.assertEqual(belege[0]["bezeichnung"],
                         "Rechnung SV-HO vom 18.06.2026 (992,34 EUR)")


class TestKandidatenBezeichnung(unittest.TestCase):

    def test_kandidaten_liefern_bezeichnung(self):
        client = _setup("kandidaten")
        kopf = _auth_header(client)
        _seed()

        r = client.get("/akten/44/22/belege/kandidaten", headers=kopf)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        kandidaten = r.get_json()["kandidaten"]
        lokal = [k for k in kandidaten if k.get("quelle") == "lokal"]
        self.assertTrue(lokal, "kein lokaler Kandidat erzeugt")
        for k in lokal:
            self.assertEqual(k["bezeichnung"],
                             "Rechnung SV-HO vom 18.06.2026 (992,34 EUR)")

    def test_gutachten_kandidaten_tragen_bezeichnung(self):
        client = _setup("gutachten")
        kopf = _auth_header(client)
        _seed(klasse="gutachten", bezeichnung="Gutachten NEUBAUER vom 17.06.2026")

        r = client.get("/akten/44/22/belege/kandidaten", headers=kopf)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        lokal = [k for k in r.get_json()["kandidaten"] if k.get("quelle") == "lokal"]
        self.assertTrue(lokal)
        for k in lokal:
            self.assertEqual(k["bezeichnung"], "Gutachten NEUBAUER vom 17.06.2026")

    def test_abrechnungsschreiben_kandidat_traegt_bezeichnung(self):
        client = _setup("abrechnung")
        kopf = _auth_header(client)
        _seed(klasse="abrechnungsschreiben",
              bezeichnung="Abrechnungsschreiben AXA vom 30.06.2026")

        r = client.get("/akten/44/22/belege/kandidaten", headers=kopf)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        lokal = [k for k in r.get_json()["kandidaten"] if k.get("quelle") == "lokal"]
        self.assertTrue(lokal)
        for k in lokal:
            self.assertIsNone(k["position_key"])
            self.assertEqual(k["bezeichnung"],
                             "Abrechnungsschreiben AXA vom 30.06.2026")


if __name__ == "__main__":
    unittest.main()
