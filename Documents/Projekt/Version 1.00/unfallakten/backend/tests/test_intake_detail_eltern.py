"""
Tests fuer hole_detail: payload_typ + eltern_email-Kontext am Anhang.

Ein Anhang (payload_typ='datei') findet ueber zustellung.parent_id die
Body-Zustellung und zieht aus deren intake_dokument den vollen E-Mail-Kontext
(Absender, Betreff, Datum, Text, Akten-AZ). Die E-Mail selbst hat kein eltern.

Testaufbau via Flask-Testclient + Auth (Muster test_intake_routes.py) -- der
direkte Funktionsaufruf scheitert am @login_erforderlich-Decorator.
"""
import importlib
import json
import os
import sys
import tempfile
import unittest

_tmp_dir = tempfile.mkdtemp(prefix="intake_eltern_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"ie_{test_id}.db")
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


class TestElternEmail(unittest.TestCase):
    def setUp(self):
        self.client = _setup(self._testMethodName)
        self.headers = _auth_header(self.client)
        from backend.db.database import get_connection
        body_parse = json.dumps({
            "text_gesamt": "Body mit 285/26",
            "akten_kandidaten": [{"akte_az": "285/26", "score": 1.0,
                                  "quelle": "az_exakt", "treffer": "285/26"}],
        }, ensure_ascii=False)
        with get_connection() as conn:
            body = conn.execute(
                "INSERT INTO intake_dokumente "
                "(sha256, payload_typ, structured_payload, parse_json, "
                " queue_status) VALUES (?, 'text', 'Body-Text', ?, "
                "'bereit_zur_review')",
                ("b" * 64, body_parse),
            ).lastrowid
            anhang = conn.execute(
                "INSERT INTO intake_dokumente "
                "(sha256, payload_typ, queue_status) "
                "VALUES (?, 'datei', 'bereit_zur_review')",
                ("a" * 64,),
            ).lastrowid
            body_zust = conn.execute(
                "INSERT INTO zustellungen "
                "(intake_dokument_id, quelle, absender, betreff, empfangen_am, "
                " parent_id) VALUES (?, 'imap', 'sv@example.de', 'Ihr Brief', "
                "'2026-07-10', NULL)",
                (body,),
            ).lastrowid
            conn.execute(
                "INSERT INTO zustellungen "
                "(intake_dokument_id, quelle, parent_id) "
                "VALUES (?, 'imap', ?)",
                (anhang, body_zust),
            )
        self.body_id = body
        self.anhang_id = anhang

    def test_anhang_liefert_eltern_email(self):
        r = self.client.get(f"/intake/dokument/{self.anhang_id}",
                            headers=self.headers)
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual(data["payload_typ"], "datei")
        self.assertIsNotNone(data["eltern_email"])
        self.assertEqual(data["eltern_email"]["absender"], "sv@example.de")
        self.assertEqual(data["eltern_email"]["betreff"], "Ihr Brief")
        self.assertEqual(data["eltern_email"]["akte_az"], "285/26")
        self.assertIn("285/26", data["eltern_email"]["text"])

    def test_email_selbst_hat_keine_eltern(self):
        r = self.client.get(f"/intake/dokument/{self.body_id}",
                            headers=self.headers)
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual(data["payload_typ"], "text")
        self.assertIsNone(data["eltern_email"])


if __name__ == "__main__":
    unittest.main()
