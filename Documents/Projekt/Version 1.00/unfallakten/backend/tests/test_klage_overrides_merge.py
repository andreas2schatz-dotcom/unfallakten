"""
Vertragstest KW-01: POST /akten/<az>/klage/generieren muss ALLE sechs vom
Klage-Wizard in ``overrides`` gesendeten cfg-Felder nach ``klage_config``
mergen: rvg_ausserg, rvg_ausserg_override, rvg_bereits_gezahlt (bereits
gemergt) sowie antraege_override, mit_feststellung_sg, mit_feststellung_sach
(fehlten bislang -> Bug KW-01, Antragstext-Bearbeitung im Wizard war Placebo).

Test-Strategie: Temp-SQLite wie in test_p14_ausgehend_e2e.py, echter Flask-
Test-Client + Login wie in test_intake_routes.py. generiere_klageschrift wird
gepatcht und akte_daten["klage_config"] eingefangen.
"""
import importlib
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

_tmp_dir = tempfile.mkdtemp(prefix="klage_overrides_")


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"kov_{test_id}.db")
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
    client = app.test_client()

    from backend.db.database import get_connection
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO unfallakte (az, unfalldatum, status) "
            "VALUES ('44/22', '2022-04-27', 'offen')"
        )

    return client


def _auth_header(client):
    r = client.post("/auth/login", json={
        "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
        "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!"),
    })
    assert r.status_code == 200, f"Login failed: {r.get_json()}"
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


_OVERRIDES = {
    "antraege_override": "1. Die Beklagte wird verurteilt, an den "
                          "Kläger 1.000,00 € zu zahlen.",
    "mit_feststellung_sg": True,
    "mit_feststellung_sach": True,
    "rvg_ausserg": {"gesamt": 100.0},
    "rvg_ausserg_override": 123.45,
    "rvg_bereits_gezahlt": 10.0,
}


class TestKlageOverridesMerge(unittest.TestCase):
    def setUp(self):
        global _tmp_dir

        # Sichere alte Werte vor _setup
        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        self._old_db_path_env = os.environ.get("DB_PATH")
        self._old_upload_dir_env = os.environ.get("UPLOAD_DIR")

        # Erstelle neues tmp_dir für diesen Test
        self._tmp_dir = tempfile.mkdtemp(prefix="klage_overrides_")
        _tmp_dir = self._tmp_dir

        # Rufe _setup auf (nutzt jetzt das neue _tmp_dir)
        self.client = _setup(self._testMethodName)
        self.headers = _auth_header(self.client)

    def tearDown(self):
        import backend.db.database as _db

        # Stelle _db.DB_PATH zurück
        _db.DB_PATH = self._alt_db_path

        # Stelle Env-Werte zurück
        if self._old_db_path_env is not None:
            os.environ["DB_PATH"] = self._old_db_path_env
        else:
            os.environ.pop("DB_PATH", None)

        if self._old_upload_dir_env is not None:
            os.environ["UPLOAD_DIR"] = self._old_upload_dir_env
        else:
            os.environ.pop("UPLOAD_DIR", None)

        # Lösche temp-dir
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def _post_generieren(self, overrides):
        import backend.routers.klage_routes as kr
        with mock.patch.object(
            kr, "generiere_klageschrift", return_value=b"PK\x03\x04dummy"
        ) as mck:
            resp = self.client.post(
                "/akten/44/22/klage/generieren",
                headers=self.headers,
                json={
                    "in_db": False,
                    "klage_config": {"beklagte": [], "positionen": []},
                    "overrides": overrides,
                },
            )
        return resp, mck

    def test_alle_sechs_override_keys_kommen_in_klage_config_an(self):
        resp, mck = self._post_generieren(_OVERRIDES)
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        mck.assert_called_once()
        akte_daten = mck.call_args.args[0]
        klage_config = akte_daten["klage_config"]

        # Regressions-Anker: waren schon vorher korrekt gemergt.
        self.assertEqual(klage_config.get("rvg_ausserg"), {"gesamt": 100.0})
        self.assertEqual(klage_config.get("rvg_ausserg_override"), 123.45)
        self.assertEqual(klage_config.get("rvg_bereits_gezahlt"), 10.0)

        # KW-01: fehlten bislang.
        self.assertEqual(
            klage_config.get("antraege_override"),
            "1. Die Beklagte wird verurteilt, an den Kläger 1.000,00 € "
            "zu zahlen.",
        )
        self.assertTrue(klage_config.get("mit_feststellung_sg"))
        self.assertTrue(klage_config.get("mit_feststellung_sach"))

    def test_antraege_override_null_erzwingt_keinen_override(self):
        overrides = dict(_OVERRIDES)
        overrides["antraege_override"] = None
        resp, mck = self._post_generieren(overrides)
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        akte_daten = mck.call_args.args[0]
        klage_config = akte_daten["klage_config"]
        self.assertIsNone(klage_config.get("antraege_override"))


if __name__ == "__main__":
    unittest.main()
