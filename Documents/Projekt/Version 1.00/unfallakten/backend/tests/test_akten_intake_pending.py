import importlib
import json
import os
import sys
import tempfile
import unittest

_tmp_dir = tempfile.mkdtemp(prefix="akten_intake_pending_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"ip_{test_id}.db")
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


def _seed_akte(az="44/22"):
    from backend.db.database import get_connection
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO unfallakte (az, unfalldatum, status) "
            "VALUES (?, '2022-04-27', 'offen')", (az,),
        )


def _lege_intake_an(sha_suffix, klasse="abrechnungsschreiben",
                    queue_status="bereit_zur_review", parse_json=None,
                    bezeichnung=None, verworfen_am=None):
    from backend.db.database import get_connection
    sha = (sha_suffix * 64)[:64]
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO intake_dokumente "
            "(sha256, arbeitskopie_pfad, klasse, klasse_quelle, konfidenz, "
            " queue_status, parse_json, registry_version, bezeichnung, "
            " verworfen_am) "
            "VALUES (?, '/tmp/x.pdf', ?, 'auto', 0.9, ?, ?, 'v1', ?, ?)",
            (sha, klasse, queue_status, parse_json, bezeichnung, verworfen_am),
        )
        return cur.lastrowid


def _lege_zustellung_an(intake_id, quelle, signale=None, roh_referenz=None):
    from backend.db.database import get_connection
    signale_json = json.dumps(signale, ensure_ascii=False) if signale else None
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO zustellungen "
            "(intake_dokument_id, quelle, signale_json, roh_referenz) "
            "VALUES (?, ?, ?, ?)",
            (intake_id, quelle, signale_json, roh_referenz),
        )


class TestIntakePending(unittest.TestCase):
    def setUp(self):
        self.client = _setup(self._testMethodName)
        self.headers = _auth_header(self.client)
        _seed_akte("44/22")

    def test_eakte_signal_az_wird_zugeordnet(self):
        did = _lege_intake_an("a")
        _lege_zustellung_an(did, "eakte", signale={"az": "44/22"})
        r = self.client.get("/akten/44/22/intake-pending", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        ids = [e["intake_id"] for e in r.get_json()]
        self.assertIn(did, ids)

    def test_manueller_upload_ziel_akte(self):
        did = _lege_intake_an("b")
        _lege_zustellung_an(did, "upload", signale={"az": "44/22"},
                            roh_referenz="upload/akte:44/22")
        r = self.client.get("/akten/44/22/intake-pending", headers=self.headers)
        ids = [e["intake_id"] for e in r.get_json()]
        self.assertIn(did, ids)

    def test_freigegeben_und_verworfen_erscheinen_nicht(self):
        frei = _lege_intake_an("c", queue_status="freigegeben")
        _lege_zustellung_an(frei, "eakte", signale={"az": "44/22"})
        verw = _lege_intake_an("d", verworfen_am="2026-08-01 10:00:00")
        _lege_zustellung_an(verw, "eakte", signale={"az": "44/22"})
        r = self.client.get("/akten/44/22/intake-pending", headers=self.headers)
        ids = [e["intake_id"] for e in r.get_json()]
        self.assertNotIn(frei, ids)
        self.assertNotIn(verw, ids)

    def test_fremde_akte_erscheint_nicht(self):
        did = _lege_intake_an("e")
        _lege_zustellung_an(did, "eakte", signale={"az": "99/22"})
        r = self.client.get("/akten/44/22/intake-pending", headers=self.headers)
        ids = [e["intake_id"] for e in r.get_json()]
        self.assertNotIn(did, ids)


if __name__ == "__main__":
    unittest.main()
