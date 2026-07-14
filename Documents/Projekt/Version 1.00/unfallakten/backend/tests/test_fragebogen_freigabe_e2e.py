"""
Fragebogen-Feld-Uebernahme bei Freigabe -- End-to-End.

Task 1: Text-Dokument (Fragebogen) laesst sich freigeben -> dokumente-Zeile
entsteht (Materialisierung der Arbeitskopie). Weitere Tests (Feld-Uebernahme)
kommen in Task 6.
"""
import importlib
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

FRAGEBOGEN_JSON = {
    "meta": {"formular": "unfallbogen", "version": "2.1", "aktenzeichen": "44/22"},
    "mandant": {"name": "Riccio", "vorname": "Marco", "telefon": "069 8402271"},
    "gegner": {"fahrer": "Khaniani",
               "fahrzeug": {"kennzeichen": "OF-KH 1234"},
               "versicherung": {"name": "HUK-Coburg"}},
    "unfall": {"datum": "2026-03-12", "ort": "Kaiserstrasse Offenbach"},
    "personenschaden": None,
}


class _FragebogenFreigabeBasis(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="frb_")
        os.environ["DB_PATH"] = os.path.join(self._tmp, "unfallakten.db")
        os.environ["UPLOAD_DIR"] = os.path.join(self._tmp, "uploads")
        os.makedirs(os.environ["UPLOAD_DIR"], exist_ok=True)

        import backend.db.database as db_mod
        import backend.models.benutzer as ben_mod
        import backend.models.akte as akte_mod
        import backend.models.dokument as dok_mod
        import backend.auth.jwt_handler as jwt_mod
        import backend.auth.middleware as mw_mod
        import backend.auth.service as svc_mod
        import backend.routers.auth_routes as routes_mod
        import backend.app as app_mod
        for m in (db_mod, ben_mod, akte_mod, dok_mod, jwt_mod, mw_mod,
                  svc_mod, routes_mod, app_mod):
            importlib.reload(m)

        self._app = app_mod.erstelle_app({"TESTING": True})
        self.client = self._app.test_client()
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute("INSERT INTO unfallakte (az, status) VALUES ('44/22', 'offen')")

    def tearDown(self):
        import shutil
        for var in ("DB_PATH", "UPLOAD_DIR"):
            os.environ.pop(var, None)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _login(self):
        r = self.client.post("/auth/login", json={
            "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
            "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!"),
        })
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return {"Authorization": f"Bearer {r.get_json()['access_token']}"}

    def _lege_fragebogen_intake_an(self, payload=None, sha="frb1"):
        from backend.db.database import get_connection
        roh = json.dumps(payload or FRAGEBOGEN_JSON, ensure_ascii=False)
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO intake_dokumente "
                "(sha256, payload_typ, structured_payload, queue_status, klasse, parse_json) "
                "VALUES (?, 'text', ?, 'bereit_zur_review', 'sonstiges', '{}')",
                ((sha * 64)[:64], roh),
            )
            return cur.lastrowid


class TestTextFreigabeLegtDokumentAn(_FragebogenFreigabeBasis):
    def test_text_dokument_freigabe_erzeugt_dokumente_zeile(self):
        did = self._lege_fragebogen_intake_an()
        headers = self._login()
        r = self.client.post(f"/intake/dokument/{did}/freigabe",
                             json={"akte_az": "44/22"}, headers=headers)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        from backend.db.database import get_connection
        with get_connection() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM dokumente WHERE akte_id='44/22'").fetchone()[0]
        self.assertEqual(n, 1, "Freigabe eines Text-Dokuments legt eine dokumente-Zeile an")


if __name__ == "__main__":
    unittest.main()
