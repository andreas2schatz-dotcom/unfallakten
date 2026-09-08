"""
POST /akten/<az>/belege -- Fehlermeldungen muessen die tatsaechliche
Fehlerursache benennen.

Hintergrund (Review-Nachbesserung zu Task 7, Befund nach I-1/I-2/M-2):
ein zu breiter ``except ValueError`` um den kompletten Try-Block fing
auch die Umwandlungsfehler von ``int(dokument_id)``/``float(betrag)``
ab und meldete faelschlich "Unbekannter position_key", obwohl der
Positionsschlüssel in Ordnung war und der Betrag das Problem war.
"""
import importlib
import os
import sys
import tempfile
import unittest

_tmp_dir = tempfile.mkdtemp(prefix="belege_zuo_route_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"bzr_{test_id}.db")
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


def _seed_dokument(az="44/22", dateiname="r.pdf"):
    from backend.db.database import get_connection
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO unfallakte (az, unfalldatum, status) "
            "VALUES (?, '2022-04-27', 'offen')", (az,),
        )
        cur = conn.execute(
            "INSERT INTO dokumente "
            "(akte_id, dateiname, dateipfad, dateityp, dokumentenklasse) "
            "VALUES (?, ?, 'x', 'pdf', 'sonstiges')",
            (az, dateiname),
        )
        conn.commit()
        return cur.lastrowid


class TestZuordnenFehlermeldungen(unittest.TestCase):

    def test_unbekannter_position_key_liefert_422_mit_key(self):
        client = _setup("unbekannter_key")
        kopf = _auth_header(client)
        dok_id = _seed_dokument()

        r = client.post("/akten/44/22/belege", headers=kopf, json={
            "position_key": "fantasieposten",
            "dokument_id": dok_id,
            "betrag_aus_beleg": 100.0,
        })
        self.assertEqual(r.status_code, 422, r.get_data(as_text=True))
        meldung = r.get_json().get("fehler", "")
        self.assertIn("fantasieposten", meldung)

    def test_ungueltiger_betrag_meldet_nicht_position_key(self):
        client = _setup("ungueltiger_betrag")
        kopf = _auth_header(client)
        dok_id = _seed_dokument()

        r = client.post("/akten/44/22/belege", headers=kopf, json={
            "position_key": "mietwagenkosten",
            "dokument_id": dok_id,
            "betrag_aus_beleg": "1500,00",
        })
        self.assertEqual(r.status_code, 422, r.get_data(as_text=True))
        meldung = r.get_json().get("fehler", "")
        self.assertNotIn("position_key", meldung)
        self.assertNotIn("mietwagenkosten", meldung)

        from backend.db.database import get_connection
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM schadenposition_belege WHERE akte_az='44/22'"
            ).fetchall()
        self.assertEqual(len(rows), 0)


if __name__ == "__main__":
    unittest.main()
