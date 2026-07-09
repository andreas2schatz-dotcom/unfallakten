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
        r = self.client.get("/akten/99%2F99/positionen/status",
                             headers=self.headers)
        self.assertEqual(r.status_code, 404)


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


if __name__ == "__main__":
    unittest.main()
