"""
N-07 (FREIGABE-NACHTRAG-1): Bestandsakten-Hinweis statt Backfill.

Da P1.8 (Backfill) zurueckgestellt ist, zeigt das Positions-Dashboard bei
Akten, deren Anlage vor dem Einfuehrungsdatum des Ereignismodells liegt,
einen Hinweis: "Ereignishistorie beginnt am [Datum] -- aeltere Vorgaenge
siehe Regulierung." Der Hinweis verschwindet automatisch, sobald P1.8
rueckwirkende Ereignisse (herkunft='backfill') mit alten Daten einspielt.

Backend-Logik: ``berechne_historie_hinweis`` + Auslieferung ueber
GET /akten/<az>/positionen/status als Feld ``historie_hinweis``.

Testkriterien:
  1) Bestandsakte (Anlage < Einfuehrung) mit Ereignissen -> zeige=True,
     beginnt_am = fruehestes Ereignis-Datum.
  2) Neue Akte (Anlage >= Einfuehrung) -> zeige=False.
  3) Bestandsakte ohne Ereignisse -> zeige=False (nichts zu bevormunden).
  4) GET /positionen/status liefert das Feld historie_hinweis.
"""
import importlib
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

EINGEFUEHRT = "2026-07-09"


class TestBerechneHistorieHinweis(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="n07_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad
        from backend.db.schema_manager import init_db
        init_db()

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt_db_path
        os.environ.pop("DB_PATH", None)
        try:
            os.unlink(self._db_pfad)
        except OSError:
            pass

    def _akte(self, az, erstellt_am):
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status, erstellt_am) "
                "VALUES (?, '2022-04-27', 'offen', ?)",
                (az, erstellt_am),
            )

    def _ereignis(self, az, datum):
        from backend.services.ereignis_service import schreibe_ereignis
        schreibe_ereignis(
            akte_az=az, ereignistyp="gutachten_eingegangen", quelle="dokument",
            datum=datum, dokument_id=42,
            positionen=[{"position_key": "reparaturkosten",
                         "wirkung": "gefordert", "betrag": 5000.0}],
        )

    def _hinweis(self, az):
        from backend.services.positionsstatus_service import (
            berechne_historie_hinweis,
        )
        return berechne_historie_hinweis(az, eingefuehrt_am=EINGEFUEHRT)

    def test_bestandsakte_mit_ereignissen_zeigt_hinweis(self):
        self._akte("44/22", "2025-01-15 09:00:00")
        self._ereignis("44/22", "2026-07-09")
        h = self._hinweis("44/22")
        self.assertTrue(h["zeige"])
        self.assertEqual(h["beginnt_am"], "2026-07-09")

    def test_neue_akte_zeigt_keinen_hinweis(self):
        self._akte("99/26", "2026-07-20 09:00:00")
        self._ereignis("99/26", "2026-07-21")
        h = self._hinweis("99/26")
        self.assertFalse(h["zeige"])

    def test_bestandsakte_ohne_ereignisse_zeigt_keinen_hinweis(self):
        self._akte("77/24", "2024-03-01 09:00:00")
        h = self._hinweis("77/24")
        self.assertFalse(h["zeige"])
        self.assertIsNone(h["beginnt_am"])

    def test_unbekannte_akte_kein_hinweis(self):
        h = self._hinweis("00/00")
        self.assertFalse(h["zeige"])


class TestHistorieHinweisRoute(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="n07route_")
        self._db_pfad = os.path.join(self._tmp, "unfallakten.db")
        os.environ["DB_PATH"] = self._db_pfad

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

        self._app = app_mod.erstelle_app({"TESTING": True})
        self.client = self._app.test_client()

        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status, erstellt_am) "
                "VALUES ('44/22', '2022-04-27', 'offen', '2025-01-15 09:00:00')"
            )

    def tearDown(self):
        import shutil
        os.environ.pop("DB_PATH", None)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _auth(self):
        r = self.client.post("/auth/login", json={
            "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
            "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!"),
        })
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return {"Authorization": f"Bearer {r.get_json()['access_token']}"}

    def test_status_enthaelt_historie_hinweis(self):
        r = self.client.get("/akten/44%2F22/positionen/status",
                            headers=self._auth())
        self.assertEqual(r.status_code, 200)
        daten = r.get_json()
        self.assertIn("historie_hinweis", daten)
        self.assertIn("zeige", daten["historie_hinweis"])
        self.assertIn("beginnt_am", daten["historie_hinweis"])


if __name__ == "__main__":
    unittest.main()
