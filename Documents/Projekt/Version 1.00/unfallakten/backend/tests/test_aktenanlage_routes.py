import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

_tmp_dir = tempfile.mkdtemp(prefix="aktenanlage_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"aa_{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    os.environ["UPLOAD_DIR"] = os.path.join(_tmp_dir, f"uploads_{test_id}")
    export_dir = os.path.join(_tmp_dir, f"oma_{test_id}")
    shutil.rmtree(export_dir, ignore_errors=True)
    os.makedirs(export_dir, exist_ok=True)
    os.environ["OMA_EXPORT_PFAD"] = export_dir

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


FORMULAR = {
    "mandant": {"anrede": "herr", "titel": "", "vorname": "Abdessamad",
                "nachname": "Achkour Zejli", "strasse": "Wiener Straße 61",
                "plz": "60599", "ort": "Frankfurt am Main", "telefon": "",
                "email": "", "geburtstag": "", "iban": "", "bank": "",
                "rsv_name": "", "rsv_nummer": "", "bekannt_adressnr": ""},
    "unfall": {"unfalldatum": "2026-04-10", "unfallort": "Offenbach",
               "kennzeichen": "F-RX 4243"},
    "gegner": {"anrede": "", "vorname": "", "nachname": "", "strasse": "",
               "plz": "", "ort": "", "kennzeichen": ""},
    "versicherung": {"name": "KRAVAG-LOGISTIC Versicherungs-AG",
                     "schadennummer": "45-11-22"},
    "gutachter": {"bezeichnung": "KFZ-Sachverständigenbüro Cassese",
                  "strasse": "Frankfurter Straße 97", "plz": "63067",
                  "ort": "Offenbach am Main", "telefon": "", "email": "",
                  "gutachten_nr": "GA-202604-1189"},
}


class TestMigration66(unittest.TestCase):
    def setUp(self):
        self.client = _setup("mig66")

    def test_tabelle_und_spalten_vorhanden(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            spalten = {r["name"] for r in
                       conn.execute("PRAGMA table_info(aktenanlage_vorgaenge)")}
        for spalte in ("id", "intake_dokument_id", "zustellung_id", "status",
                       "formular_json", "xml_pfad", "mandant_nachname",
                       "mandant_vorname", "mandant_adressnr", "erkanntes_az",
                       "angelegt_am", "angelegt_von", "erkannt_am"):
            self.assertIn(spalte, spalten)

    def test_schema_version_66_gestempelt(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT MAX(version) AS v FROM schema_version").fetchone()
        self.assertGreaterEqual(row["v"], 66)


if __name__ == "__main__":
    unittest.main()
