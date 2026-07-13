"""
Tests fuer S1.9d: POST /email/import/log/<id>/in-akte unter dem
Feature-Flag INTAKE_REVIEW_PFLICHT.

Erwartungen:
  * Unter dem Flag (Default True) antwortet die Route mit HTTP 202
    ``{in_review: True, hinweis: "..."}``  -- kein direkter Aufruf von
    ``importiere_in_akte()`` mehr.
  * Alt-Pfad (Flag=false) laeuft weiter.
"""
import importlib
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

_tmp_dir = tempfile.mkdtemp(prefix="s19d_ia_")


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"ia_{test_id}.db")
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
        conn.execute(
            "INSERT INTO email_import_log "
            "(message_id, betreff, absender, empfangen_am, konto, "
            " akte_id, status) "
            "VALUES ('<mid1>', 'x', 'test@x', '2026-01-01', 'unfall', "
            "'44/22', 'zugeordnet')"
        )
    return client


def _seed_intake_fuer_log(log_id: int, eml_pfad: str = "/tmp/mail1.eml"):
    """Verknuepft einen Log-Eintrag mit einem Intake-Dokument in der Queue.

    Der Link laeuft ueber ``zustellungen.roh_referenz == email_import_log.eml_pfad``
    (so ruft der Import-Service den IMAP-Adapter auf: roh_referenz=eml_pfad).
    """
    from backend.db.database import get_connection
    with get_connection() as conn:
        conn.execute(
            "UPDATE email_import_log SET eml_pfad = ? WHERE id = ?",
            (eml_pfad, log_id),
        )
        conn.execute(
            "INSERT INTO intake_dokumente (sha256, payload_typ, queue_status) "
            "VALUES (?, 'text', 'neu')",
            (f"sha-{log_id}",),
        )
        row = conn.execute(
            "SELECT id FROM intake_dokumente WHERE sha256 = ?",
            (f"sha-{log_id}",),
        ).fetchone()
        conn.execute(
            "INSERT INTO zustellungen (intake_dokument_id, quelle, roh_referenz) "
            "VALUES (?, 'imap', ?)",
            (row["id"], eml_pfad),
        )


def _auth(client):
    r = client.post("/auth/login", json={
        "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
        "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!"),
    })
    assert r.status_code == 200, r.get_data(as_text=True)
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


class TestInAkteFlag(unittest.TestCase):
    def setUp(self):
        self._alt_flag = os.environ.get("INTAKE_REVIEW_PFLICHT")
        os.environ.pop("INTAKE_REVIEW_PFLICHT", None)
        self.client = _setup(self._testMethodName)
        self.headers = _auth(self.client)

    def tearDown(self):
        if self._alt_flag is None:
            os.environ.pop("INTAKE_REVIEW_PFLICHT", None)
        else:
            os.environ["INTAKE_REVIEW_PFLICHT"] = self._alt_flag

    def test_default_flag_true_liefert_202_review(self):
        _seed_intake_fuer_log(1)
        r = self.client.post(
            "/email/import/log/1/in-akte",
            headers=self.headers,
        )
        self.assertEqual(r.status_code, 202, r.get_data(as_text=True))
        body = r.get_json()
        self.assertTrue(body.get("in_review"))

    def test_default_flag_true_ruft_importiere_in_akte_nicht_auf(self):
        _seed_intake_fuer_log(1)
        with mock.patch(
            "backend.email_import.import_service.importiere_in_akte"
        ) as mck:
            r = self.client.post(
                "/email/import/log/1/in-akte",
                headers=self.headers,
            )
        self.assertEqual(r.status_code, 202, r.get_data(as_text=True))
        mck.assert_not_called()

    def test_flag_true_ohne_intake_faellt_auf_altpfad_zurueck(self):
        # BUG-04: Alt-Mail (kein Intake-Dokument in der Queue) muss weiterhin
        # ueber den Alt-Pfad importierbar sein, sonst sind ihre Anhaenge
        # dauerhaft nicht in die Akte uebernehmbar.
        with mock.patch(
            "backend.routers.email_routes.importiere_in_akte",
            return_value={"ok": True, "dok_ids": [1], "importiert_am": "12:00"},
        ) as mck:
            r = self.client.post(
                "/email/import/log/1/in-akte",
                headers=self.headers,
            )
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        mck.assert_called_once()

    def test_flag_true_mit_intake_bleibt_202_review(self):
        # Ist das Dokument in der Review-Queue vorhanden -> weiterhin 202.
        _seed_intake_fuer_log(1)
        r = self.client.post(
            "/email/import/log/1/in-akte",
            headers=self.headers,
        )
        self.assertEqual(r.status_code, 202, r.get_data(as_text=True))
        self.assertTrue(r.get_json().get("in_review"))

    def test_flag_false_ruft_importiere_in_akte_auf(self):
        os.environ["INTAKE_REVIEW_PFLICHT"] = "false"
        with mock.patch(
            "backend.routers.email_routes.importiere_in_akte",
            return_value={"ok": True, "dok_ids": [], "importiert_am": "12:00"},
        ) as mck:
            r = self.client.post(
                "/email/import/log/1/in-akte",
                headers=self.headers,
            )
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        mck.assert_called_once()


if __name__ == "__main__":
    unittest.main()
