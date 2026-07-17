"""
Bugfix KW-11: Unkostenpauschale-None-Semantik (nicht gesetzt != explizit 0).

_baue_tabelle() nutzte bislang ``_f("unkostenpauschale") or 30.0``, was eine
explizit auf 0,00 EUR gesetzte Pauschale wieder in den 30-EUR-Default
verwandelte. Die Router-Weiche in klage_routes.py (generiere_klage) war toter
Code, weil der Helfer ``s()`` nie None liefert.

Test-Strategie Unit-Teil: _baue_tabelle direkt mit dict aufrufen, XML +
Gesamtsumme prüfen.
Test-Strategie Router-Teil: wie test_klage_overrides_merge.py -
Flask-Test-Client + Login, Temp-SQLite, generiere_klageschrift gepatcht,
akte_daten = mock.call_args.args[0] inspizieren.
"""
import importlib
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.word.forderungsschreiben_wv import _baue_tabelle


class TestBaueTabelleUnkostenpauschale(unittest.TestCase):
    def test_key_fehlt_ergibt_30_euro_default(self):
        xml, gesamt = _baue_tabelle({})
        self.assertIn("Unkostenpauschale", xml)
        self.assertIn("30,00\xa0€", xml)
        self.assertEqual(gesamt, 30.0)

    def test_key_none_ergibt_30_euro_default(self):
        xml, gesamt = _baue_tabelle({"unkostenpauschale": None})
        self.assertIn("Unkostenpauschale", xml)
        self.assertIn("30,00\xa0€", xml)
        self.assertEqual(gesamt, 30.0)

    def test_key_explizit_0_ergibt_keine_zeile(self):
        xml, gesamt = _baue_tabelle({"unkostenpauschale": 0.0})
        self.assertNotIn("Unkostenpauschale", xml)
        self.assertEqual(gesamt, 0.0)

    def test_key_explizit_25_wird_uebernommen(self):
        xml, gesamt = _baue_tabelle({"unkostenpauschale": 25.0})
        self.assertIn("Unkostenpauschale", xml)
        self.assertIn("25,00\xa0€", xml)
        self.assertEqual(gesamt, 25.0)


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"kup_{test_id}.db")
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
            "VALUES ('55/26', '2026-01-10', 'offen')"
        )

    return client


def _auth_header(client):
    r = client.post("/auth/login", json={
        "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
        "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!"),
    })
    assert r.status_code == 200, f"Login failed: {r.get_json()}"
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


class TestRouterUnkostenpauschale(unittest.TestCase):
    def setUp(self):
        global _tmp_dir

        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        self._old_db_path_env = os.environ.get("DB_PATH")
        self._old_upload_dir_env = os.environ.get("UPLOAD_DIR")

        self._tmp_dir = tempfile.mkdtemp(prefix="klage_unkosten_")
        _tmp_dir = self._tmp_dir

        self.client = _setup(self._testMethodName)
        self.headers = _auth_header(self.client)

    def tearDown(self):
        import backend.db.database as _db

        _db.DB_PATH = self._alt_db_path

        if self._old_db_path_env is not None:
            os.environ["DB_PATH"] = self._old_db_path_env
        else:
            os.environ.pop("DB_PATH", None)

        if self._old_upload_dir_env is not None:
            os.environ["UPLOAD_DIR"] = self._old_upload_dir_env
        else:
            os.environ.pop("UPLOAD_DIR", None)

        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def _post_generieren(self):
        import backend.routers.klage_routes as kr
        with mock.patch.object(
            kr, "generiere_klageschrift", return_value=b"PK\x03\x04dummy"
        ) as mck:
            resp = self.client.post(
                "/akten/55/26/klage/generieren",
                headers=self.headers,
                json={
                    "in_db": False,
                    "klage_config": {"beklagte": [], "positionen": []},
                    "overrides": {},
                },
            )
        return resp, mck

    def test_db_wert_0_bleibt_0_im_schaden_dict(self):
        # Bestandsverhalten: DB unterscheidet "nie angefasst" nicht von "0"
        # (Spalte NOT NULL DEFAULT 0.0) → falsy DB-Wert wird als "nicht gesetzt"
        # behandelt, damit _baue_tabelle weiterhin den 30€-Default zieht.
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO schadenpositionen (akte_id, unkostenpauschale) "
                "VALUES ('55/26', 0.0)"
            )

        resp, mck = self._post_generieren()
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        akte_daten = mck.call_args.args[0]
        self.assertIsNone(akte_daten["schaden"]["unkostenpauschale"])

    def test_db_wert_25_wird_uebernommen_im_schaden_dict(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO schadenpositionen (akte_id, unkostenpauschale) "
                "VALUES ('55/26', 25.0)"
            )

        resp, mck = self._post_generieren()
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        akte_daten = mck.call_args.args[0]
        self.assertEqual(akte_daten["schaden"]["unkostenpauschale"], 25.0)

    def test_keine_schadenposition_ergibt_none_im_schaden_dict(self):
        resp, mck = self._post_generieren()
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        akte_daten = mck.call_args.args[0]
        self.assertIsNone(akte_daten["schaden"]["unkostenpauschale"])


class TestWordServiceUnkostenpauschale(unittest.TestCase):
    """
    Regressionstest Forderungsschreiben-Pfad (word_service._lade_akte_daten /
    s_dict): eine nie angefasste Schadenzeile (unkostenpauschale=0.0, DB-Default)
    darf im schaden-Dict NICHT als explizite 0 ankommen, sonst entfällt die
    30€-Pauschale im Forderungsschreiben (Bestandsverhalten).
    """

    def setUp(self):
        global _tmp_dir

        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        self._old_db_path_env = os.environ.get("DB_PATH")
        self._old_upload_dir_env = os.environ.get("UPLOAD_DIR")

        self._tmp_dir = tempfile.mkdtemp(prefix="klage_unkosten_ws_")
        _tmp_dir = self._tmp_dir

        self.client = _setup(self._testMethodName)

    def tearDown(self):
        import backend.db.database as _db

        _db.DB_PATH = self._alt_db_path

        if self._old_db_path_env is not None:
            os.environ["DB_PATH"] = self._old_db_path_env
        else:
            os.environ.pop("DB_PATH", None)

        if self._old_upload_dir_env is not None:
            os.environ["UPLOAD_DIR"] = self._old_upload_dir_env
        else:
            os.environ.pop("UPLOAD_DIR", None)

        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def test_nie_angefasste_schadenzeile_ergibt_none_und_30_euro_tabelle(self):
        from backend.db.database import get_connection
        from backend.models.akte import hole_akte_by_id
        import backend.word.word_service as ws

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO schadenpositionen (akte_id, reparaturkosten) "
                "VALUES ('55/26', 500.0)"
            )

        akte = hole_akte_by_id("55/26")
        akte_daten = ws._lade_akte_daten("55/26", akte, dok_typ="")

        self.assertIsNone(akte_daten["schaden"]["unkostenpauschale"])

        xml, gesamt = _baue_tabelle(akte_daten["schaden"])
        self.assertIn("Unkostenpauschale", xml)
        self.assertIn("30,00\xa0€", xml)


if __name__ == "__main__":
    unittest.main()
