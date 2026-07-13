"""
Tests fuer backend/routers/positionen_routes.py (P1.3).

Endpoints:
  * GET /akten/<az>/positionen/status
  * GET /akten/<az>/aktionen?dokument_id=...
"""
import importlib
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

_tmp_dir = tempfile.mkdtemp(prefix="p13routes_")


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"p13_{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path

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


def _auth(client):
    r = client.post("/auth/login", json={
        "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
        "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!"),
    })
    assert r.status_code == 200, r.get_data(as_text=True)
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


def _schr(typ, positionen, datum="2022-05-10", dokument_id=42):
    from backend.services.ereignis_service import schreibe_ereignis
    return schreibe_ereignis(
        akte_az="44/22", ereignistyp=typ, quelle="dokument",
        datum=datum, positionen=positionen, dokument_id=dokument_id,
    )


class TestPositionenStatus(unittest.TestCase):
    def setUp(self):
        self.client = _setup(self._testMethodName)
        self.headers = _auth(self.client)

    def test_401_ohne_token(self):
        r = self.client.get("/akten/44%2F22/positionen/status")
        self.assertEqual(r.status_code, 401)

    def test_leere_status_bei_akte_ohne_ereignisse(self):
        r = self.client.get("/akten/44%2F22/positionen/status",
                             headers=self.headers)
        self.assertEqual(r.status_code, 200)
        daten = r.get_json()
        self.assertEqual(daten["positionen"], {})
        self.assertIn("registry_version", daten)

    def test_status_liefert_ableitung(self):
        _schr("gutachten_eingegangen", [
            {"position_key": "reparaturkosten",
             "wirkung": "gefordert", "betrag": 5000.0},
        ], datum="2022-04-30")
        _schr("abrechnung_eingegangen", [
            {"position_key": "reparaturkosten",
             "wirkung": "anerkannt", "betrag": 4100.0},
            {"position_key": "reparaturkosten",
             "wirkung": "gekuerzt",  "betrag": 900.0,
             "kuerzungsart_id": 1},
        ], datum="2022-05-10")

        r = self.client.get("/akten/44%2F22/positionen/status",
                             headers=self.headers)
        self.assertEqual(r.status_code, 200)
        pos = r.get_json()["positionen"]["reparaturkosten"]
        self.assertEqual(pos["zustand"], "teilanerkannt")
        self.assertEqual(pos["anerkannt"], 4100.0)
        self.assertEqual(pos["stand"], "2022-05-10")

    def test_akte_404(self):
        # BUG-22: seit Umstellung auf den gemeinsamen pruefe_akte-Helper
        # gilt ein wohlgeformtes AZ mit Slash als RA-MICRO-only-Akte (200,
        # leer, analog anderer Router). Ein echt unnormalisierbares AZ
        # bleibt 404.
        r = self.client.get("/akten/keinaz/positionen/status",
                             headers=self.headers)
        self.assertEqual(r.status_code, 404)

    def test_bug22_slashlose_az_wird_normalisiert(self):
        # BUG-22: /akten/4422/... muss die Akte 44/22 finden (AZ-Normalisierung
        # ueber den gemeinsamen _helpers.pruefe_akte-Helper), analog anderer Router.
        r = self.client.get("/akten/4422/positionen/status",
                             headers=self.headers)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(r.get_json()["akte_az"], "44/22")


class TestAktionen(unittest.TestCase):
    def setUp(self):
        self.client = _setup(self._testMethodName)
        self.headers = _auth(self.client)

    def test_aktionen_leer_ohne_ereignisse(self):
        r = self.client.get("/akten/44%2F22/aktionen",
                             headers=self.headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["aktionen"], [])

    def test_aktionen_liefert_folgeaktionen_zu_ereignistyp(self):
        _schr("abrechnung_eingegangen", [
            {"position_key": "reparaturkosten",
             "wirkung": "anerkannt", "betrag": 4100.0},
        ])
        r = self.client.get("/akten/44%2F22/aktionen",
                             headers=self.headers)
        self.assertEqual(r.status_code, 200)
        aktionen = r.get_json()["aktionen"]
        akt_ids = {a["aktion"] for a in aktionen}
        self.assertIn("stellungnahme.generieren", akt_ids)


class TestPositionsEreignisse(unittest.TestCase):
    """P1.7-D: GET /akten/<az>/positionen/<key>/ereignisse -- Ebene-2-Liste."""

    def setUp(self):
        self.client = _setup(self._testMethodName)
        self.headers = _auth(self.client)

    def test_401_ohne_token(self):
        r = self.client.get(
            "/akten/44%2F22/positionen/reparaturkosten/ereignisse"
        )
        self.assertEqual(r.status_code, 401)

    def test_leere_liste_bei_position_ohne_ereignisse(self):
        r = self.client.get(
            "/akten/44%2F22/positionen/reparaturkosten/ereignisse",
            headers=self.headers,
        )
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(d["ereignisse"], [])
        self.assertEqual(d["akte_az"], "44/22")
        self.assertEqual(d["position_key"], "reparaturkosten")

    def test_akte_404(self):
        # BUG-22: unnormalisierbares AZ -> 404 (Slash-AZ waere RA-MICRO-only, 200).
        r = self.client.get(
            "/akten/keinaz/positionen/reparaturkosten/ereignisse",
            headers=self.headers,
        )
        self.assertEqual(r.status_code, 404)

    def test_liste_liefert_chronologisch_mit_metadaten(self):
        _schr("gutachten_eingegangen", [
            {"position_key": "reparaturkosten",
             "wirkung": "gefordert", "betrag": 5000.0},
        ], datum="2022-04-30", dokument_id=11)
        _schr("abrechnung_eingegangen", [
            {"position_key": "reparaturkosten",
             "wirkung": "anerkannt", "betrag": 4100.0},
        ], datum="2022-05-14", dokument_id=22)

        r = self.client.get(
            "/akten/44%2F22/positionen/reparaturkosten/ereignisse",
            headers=self.headers,
        )
        self.assertEqual(r.status_code, 200)
        liste = r.get_json()["ereignisse"]
        self.assertEqual(len(liste), 2)
        self.assertEqual(liste[0]["datum"], "2022-04-30")
        self.assertEqual(liste[0]["ereignistyp"], "gutachten_eingegangen")
        self.assertEqual(liste[0]["richtung"], "eingehend")
        self.assertEqual(liste[0]["wirkung"], "gefordert")
        self.assertEqual(liste[0]["dokument_id"], 11)
        self.assertEqual(liste[0]["status"], "aktuell")
        self.assertEqual(liste[1]["betrag"], 4100.0)

    def test_ersetzte_ereignisse_werden_mitgeliefert_mit_status(self):
        """POSITIONSMODELL K-M2a: ersetzte Ereignisse bleiben sichtbar
        (nur die Ableitung ignoriert sie), damit die Ereignisliste die
        Historie zeigen kann."""
        alt = _schr("gutachten_eingegangen", [
            {"position_key": "reparaturkosten",
             "wirkung": "gefordert", "betrag": 5000.0},
        ], datum="2022-04-30", dokument_id=11)
        from backend.services.ereignis_service import schreibe_ereignis
        schreibe_ereignis(
            akte_az="44/22", ereignistyp="gutachten_eingegangen",
            quelle="dokument", datum="2022-05-15", dokument_id=12,
            positionen=[
                {"position_key": "reparaturkosten",
                 "wirkung": "gefordert", "betrag": 6500.0},
            ],
            ersetzt_kopf_id=alt,
        )

        r = self.client.get(
            "/akten/44%2F22/positionen/reparaturkosten/ereignisse",
            headers=self.headers,
        )
        self.assertEqual(r.status_code, 200)
        liste = r.get_json()["ereignisse"]
        self.assertEqual(len(liste), 2)
        status_je_datum = {e["datum"]: e["status"] for e in liste}
        self.assertEqual(status_je_datum["2022-04-30"], "ersetzt")
        self.assertEqual(status_je_datum["2022-05-15"], "aktuell")

    def test_liefert_herkunft_fuer_wdm_kennzeichnung(self):
        from backend.services.ereignis_service import schreibe_ereignis
        schreibe_ereignis(
            akte_az="44/22", ereignistyp="abrechnung_eingegangen",
            quelle="dokument", datum="2022-05-14",
            dokument_id=None, herkunft="wdm",
            positionen=[
                {"position_key": "sonstiges",
                 "wirkung": "anerkannt", "betrag": 65.0},
            ],
        )
        r = self.client.get(
            "/akten/44%2F22/positionen/sonstiges/ereignisse",
            headers=self.headers,
        )
        self.assertEqual(r.status_code, 200)
        liste = r.get_json()["ereignisse"]
        self.assertEqual(liste[0]["herkunft"], "wdm")


if __name__ == "__main__":
    unittest.main()
