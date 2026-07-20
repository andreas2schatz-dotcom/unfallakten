import importlib
import os
import sys
import tempfile
import unittest

_tmp = tempfile.mkdtemp(prefix="fvspeichern_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _fresh_app(name):
    db_path = os.path.join(_tmp, f"{name}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    import backend.db.database as db_mod
    import backend.db.schema_manager as sm
    importlib.reload(db_mod)
    importlib.reload(sm)
    sm.init_db()
    from flask import Flask
    import backend.routers.firmen_routes as fr
    importlib.reload(fr)
    app = Flask(__name__)
    app.register_blueprint(fr.firmen_bp)
    return app.test_client(), db_mod


class TestSpeichernGlobal(unittest.TestCase):
    def test_firma_ohne_beteiligter_wird_global_gespeichert(self):
        client, db_mod = _fresh_app("global_only")
        r = client.post("/firmen/vertreter/speichern", json={
            "beteiligter_id": -1,
            "firma": "ADAC Autoversicherung AG",
            "vertreter_name": "Stefan Daehne",
            "vertreter_funktion": "Vorstand",
        })
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["global_gespeichert"])
        with db_mod.get_connection() as conn:
            row = conn.execute(
                "SELECT vertreter_name FROM firmen_vertreter "
                "WHERE firma_norm = 'adac autoversicherung ag'").fetchone()
        self.assertEqual(row["vertreter_name"], "Stefan Daehne")

    def test_echter_beteiligter_wird_zusaetzlich_aktualisiert(self):
        client, db_mod = _fresh_app("mit_beteiligter")
        with db_mod.get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('1/26', '2026-01-01', 'offen')")
            conn.execute(
                "INSERT INTO beteiligte (id, akte_id, rolle, name, firma) "
                "VALUES (77, '1/26', 'gegner', '', 'Muster GmbH')")
        r = client.post("/firmen/vertreter/speichern", json={
            "beteiligter_id": 77,
            "firma": "Muster GmbH",
            "vertreter_name": "Erika Muster",
            "vertreter_funktion": "Geschaeftsfuehrer",
        })
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertTrue(body["global_gespeichert"])
        self.assertTrue(body["beteiligter_gespeichert"])
        with db_mod.get_connection() as conn:
            row = conn.execute(
                "SELECT vertreter_name FROM beteiligte WHERE id = 77").fetchone()
        self.assertEqual(row["vertreter_name"], "Erika Muster")

    def test_ohne_firma_und_ohne_beteiligter_fehler(self):
        client, _ = _fresh_app("kein_ziel")
        r = client.post("/firmen/vertreter/speichern", json={
            "vertreter_name": "X",
        })
        self.assertEqual(r.status_code, 400)

    def test_leerer_vertreter_name_fehler(self):
        client, _ = _fresh_app("leer_name")
        r = client.post("/firmen/vertreter/speichern", json={
            "firma": "Muster AG", "vertreter_name": "  ",
        })
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
