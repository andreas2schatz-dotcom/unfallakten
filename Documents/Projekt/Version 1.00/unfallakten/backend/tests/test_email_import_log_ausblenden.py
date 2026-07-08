"""
Tests fuer POST /email/import/log/<id>/loeschen (S1.9a).

Unter INTAKE_REVIEW_PFLICHT (Default True) setzt die Route
``ausgeblendet=1``. Zustellungen werden nie geloescht. Der Alt-Pfad
(IMAP-Move + status='ignoriert') laeuft nur noch bei
INTAKE_REVIEW_PFLICHT=false.
"""
import importlib
import os
import sys
import tempfile
import unittest

_tmp_dir = tempfile.mkdtemp(prefix="eilausbl_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"eil_{test_id}.db")
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
    return client


def _auth(client):
    r = client.post("/auth/login", json={
        "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
        "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!"),
    })
    assert r.status_code == 200, r.get_data(as_text=True)
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


def _lege_log_an():
    from backend.db.database import get_connection
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO email_import_log "
            "(message_id, betreff, absender, empfangen_am, konto, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("<mid1>", "Test", "test@x.de", "2026-01-01", "unfall",
             "zugeordnet"),
        )
        return cur.lastrowid


class TestAusblenden(unittest.TestCase):
    def setUp(self):
        self._alt_flag = os.environ.get("INTAKE_REVIEW_PFLICHT")
        # Default: Flag nicht gesetzt = True.
        os.environ.pop("INTAKE_REVIEW_PFLICHT", None)
        self.client = _setup(self._testMethodName)
        self.headers = _auth(self.client)

    def tearDown(self):
        if self._alt_flag is None:
            os.environ.pop("INTAKE_REVIEW_PFLICHT", None)
        else:
            os.environ["INTAKE_REVIEW_PFLICHT"] = self._alt_flag

    def test_loeschen_setzt_ausgeblendet_default(self):
        log_id = _lege_log_an()
        r = self.client.post(
            f"/email/import/log/{log_id}/loeschen",
            headers=self.headers,
        )
        self.assertEqual(r.status_code, 200)

        from backend.db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT ausgeblendet, status FROM email_import_log WHERE id=?",
                (log_id,)
            ).fetchone()
        self.assertEqual(row["ausgeblendet"], 1,
                         "ausgeblendet muss auf 1 gesetzt sein")

    def test_altpfad_mit_flag_false(self):
        """Bei INTAKE_REVIEW_PFLICHT=false verhaelt sich die Route wie frueher
        (status='ignoriert')."""
        os.environ["INTAKE_REVIEW_PFLICHT"] = "false"
        log_id = _lege_log_an()
        r = self.client.post(
            f"/email/import/log/{log_id}/loeschen",
            headers=self.headers,
        )
        self.assertEqual(r.status_code, 200)

        from backend.db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT status FROM email_import_log WHERE id=?", (log_id,)
            ).fetchone()
        self.assertEqual(row["status"], "ignoriert")

    def test_404_wenn_log_nicht_existiert(self):
        r = self.client.post(
            "/email/import/log/99999/loeschen",
            headers=self.headers,
        )
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
