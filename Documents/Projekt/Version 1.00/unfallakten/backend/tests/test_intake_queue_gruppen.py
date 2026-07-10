"""
Tests fuer hole_queue: Gruppierungs-Bezuege je Queue-Eintrag.

Jeder Eintrag traegt payload_typ, zustellung_id, parent_zustellung_id,
absender, betreff -- das Frontend gruppiert damit Anhaenge unter ihre E-Mail.

Testaufbau via Flask-Testclient + Auth (Muster test_intake_routes.py).
"""
import importlib
import os
import sys
import tempfile
import unittest

_tmp_dir = tempfile.mkdtemp(prefix="intake_qgruppen_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"qg_{test_id}.db")
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


class TestQueueGruppen(unittest.TestCase):
    def setUp(self):
        self.client = _setup(self._testMethodName)
        self.headers = _auth_header(self.client)
        from backend.db.database import get_connection
        with get_connection() as conn:
            body = conn.execute(
                "INSERT INTO intake_dokumente "
                "(sha256, payload_typ, queue_status, erstellt_am) VALUES "
                "(?, 'text', 'bereit_zur_review', '2026-07-10 08:00')",
                ("1" * 64,),
            ).lastrowid
            anhang = conn.execute(
                "INSERT INTO intake_dokumente "
                "(sha256, payload_typ, queue_status, erstellt_am) VALUES "
                "(?, 'datei', 'bereit_zur_review', '2026-07-10 08:01')",
                ("2" * 64,),
            ).lastrowid
            body_zust = conn.execute(
                "INSERT INTO zustellungen "
                "(intake_dokument_id, quelle, absender, betreff, parent_id) "
                "VALUES (?, 'imap', 'sv@x.de', 'Brief', NULL)",
                (body,),
            ).lastrowid
            conn.execute(
                "INSERT INTO zustellungen "
                "(intake_dokument_id, quelle, parent_id) VALUES (?, 'imap', ?)",
                (anhang, body_zust),
            )
        self.body_id = body
        self.anhang_id = anhang
        self.body_zust = body_zust

    def test_gruppen_bezuege_vorhanden(self):
        r = self.client.get("/intake/queue", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        eintraege = {e["id"]: e for e in r.get_json()["eintraege"]}
        self.assertEqual(eintraege[self.body_id]["payload_typ"], "text")
        self.assertEqual(eintraege[self.body_id]["zustellung_id"],
                         self.body_zust)
        self.assertIsNone(eintraege[self.body_id]["parent_zustellung_id"])
        self.assertEqual(eintraege[self.body_id]["absender"], "sv@x.de")
        self.assertEqual(eintraege[self.body_id]["betreff"], "Brief")
        self.assertEqual(eintraege[self.anhang_id]["parent_zustellung_id"],
                         self.body_zust)


if __name__ == "__main__":
    unittest.main()
