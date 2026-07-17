"""
Bugtest KW-14: POST /akten/<az>/klage/generieren muss das
``klage_generiert``-Ereignis MIT Positionen buchen.

Bug: ``hole_schadenpositionen(az)`` liefert eine ``@dataclass
Schadenposition`` (backend/models/schaden.py), der Code in
klage_routes.py ruft aber faelschlich ``.items()`` auf einem
Dataclass-Objekt auf -> AttributeError, den die Best-Effort-Klammer
still schluckt -> Ereignis wird immer mit positionen=None gebucht.

Test-Strategie: Temp-SQLite wie in test_p14_ausgehend_e2e.py, echter
Flask-Test-Client + Login wie in test_klage_overrides_merge.py. Die
Route ist der Angriffspunkt (nicht word_service, dort funktioniert
der Positions-Pfad bereits).
"""
import importlib
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"kep_{test_id}.db")
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
        conn.execute(
            "INSERT INTO schadenpositionen (akte_id, reparaturkosten, "
            "wertminderung) VALUES ('44/22', 5000.0, 300.0)"
        )

    return client


def _auth_header(client):
    r = client.post("/auth/login", json={
        "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
        "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!"),
    })
    assert r.status_code == 200, f"Login failed: {r.get_json()}"
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


class TestKlageEreignisPositionen(unittest.TestCase):
    def setUp(self):
        global _tmp_dir

        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        self._old_db_path_env = os.environ.get("DB_PATH")
        self._old_upload_dir_env = os.environ.get("UPLOAD_DIR")

        self._tmp_dir = tempfile.mkdtemp(prefix="klage_ereignis_pos_")
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
        ), mock.patch.object(
            kr, "registriere_dokument",
            return_value=mock.MagicMock(id=1, dateiname="k.docx")
        ), mock.patch(
            "backend.services.ausgehende_ereignisse.erzeuge"
        ) as mck:
            resp = self.client.post(
                "/akten/44/22/klage/generieren",
                headers=self.headers,
                json={
                    "in_db": True,
                    "klage_config": {"beklagte": [], "positionen": []},
                },
            )
        return resp, mck

    def test_klage_generiert_ereignis_traegt_positionen(self):
        resp, mck = self._post_generieren()
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        mck.assert_called_once()
        kwargs = mck.call_args.kwargs
        self.assertEqual(kwargs["ereignistyp"], "klage_generiert")
        self.assertEqual(kwargs["dokument_id"], 1)

        positionen = kwargs["positionen"]
        self.assertIsInstance(positionen, dict)
        self.assertEqual(positionen.get("reparaturkosten"), 5000.0)
        self.assertEqual(positionen.get("wertminderung"), 300.0)
        self.assertNotIn("id", positionen)
        self.assertNotIn("akte_id", positionen)

    def test_klage_generiert_ereignis_positionen_none_bei_fehler(self):
        import backend.routers.klage_routes as kr
        import backend.models.schaden as schaden_mod

        # Erster Aufruf (Zeile ~1187, ungeschuetzt fuer die Tabellen-Erstellung)
        # muss echte Daten liefern, sonst scheitert die Route schon vor dem
        # P1.4-Block. Erst der ZWEITE Aufruf (im P1.4-Best-Effort-Block)
        # simuliert den Fehlerfall.
        _calls = {"n": 0}

        def _side_effect(az):
            _calls["n"] += 1
            if _calls["n"] == 1:
                return schaden_mod.hole_schadenpositionen(az)
            raise RuntimeError("boom")

        with mock.patch.object(
            kr, "generiere_klageschrift", return_value=b"PK\x03\x04dummy"
        ), mock.patch.object(
            kr, "registriere_dokument",
            return_value=mock.MagicMock(id=2, dateiname="k2.docx")
        ), mock.patch.object(
            kr, "hole_schadenpositionen", side_effect=_side_effect
        ), mock.patch(
            "backend.services.ausgehende_ereignisse.erzeuge"
        ) as mck:
            resp = self.client.post(
                "/akten/44/22/klage/generieren",
                headers=self.headers,
                json={
                    "in_db": True,
                    "klage_config": {"beklagte": [], "positionen": []},
                },
            )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        mck.assert_called_once()
        self.assertIsNone(mck.call_args.kwargs["positionen"])


if __name__ == "__main__":
    unittest.main()
