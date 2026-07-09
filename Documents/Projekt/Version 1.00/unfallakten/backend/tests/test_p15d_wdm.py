"""
Tests fuer P1.5d — WDM-Import erzeugt Ereignis ``abrechnung_eingegangen``
mit ``herkunft='wdm'`` (unbestaetigter Vorschlag, PF-08).

Grundregeln:
  * quelle='dokument', dokument_id=NULL (WDM ist inhaltlich ein
    Abrechnungsschreiben, aber es liegt kein Dokument im System vor).
  * herkunft='wdm' -- die Ableitung markiert Cache-Zeilen mit
    herkunft='wdm' spaeter (P1.7) als unbestaetigt.
  * Doppelerfassungs-Guard laeuft NICHT (dokument_id=NULL). Der WDM-
    Alt-Pfad selbst verhindert Mehrfach-Imports per HTTP 409.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class _WdmTestBasis(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="p15d_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad
        from backend.db.schema_manager import init_db
        init_db()

        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('44/22', '2022-04-27', 'offen')"
            )

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt_db_path
        os.environ.pop("DB_PATH", None)
        try:
            os.unlink(self._db_pfad)
        except OSError:
            pass


class TestErzeugeAusWdm(_WdmTestBasis):

    def test_wdm_ereignis_hat_herkunft_wdm_und_null_dokument_id(self):
        from backend.services.eingehende_ereignisse import erzeuge_aus_wdm
        from backend.db.database import get_connection

        eid = erzeuge_aus_wdm(
            akte_az="44/22", datum="2021-03-23",
            haftungsart="vollhaftung",
            positionen=[
                {"position_key": "reparaturkosten",
                 "betrag_gefordert": 3000.0, "betrag_reguliert": 2616.71,
                 "kuerzungsart_id": None},
                {"position_key": "sv_kosten",
                 "betrag_gefordert": 650.0, "betrag_reguliert": 650.0,
                 "kuerzungsart_id": None},
                {"position_key": "wertminderung",
                 "betrag_gefordert": 350.0, "betrag_reguliert": 350.0,
                 "kuerzungsart_id": None},
            ],
        )
        self.assertIsInstance(eid, int)
        with get_connection() as conn:
            kopf = conn.execute(
                "SELECT ereignistyp, quelle, dokument_id, herkunft "
                "FROM ereignisse WHERE id=?", (eid,)
            ).fetchone()
        self.assertEqual(kopf["ereignistyp"], "abrechnung_eingegangen")
        self.assertEqual(kopf["quelle"], "dokument")
        self.assertIsNone(kopf["dokument_id"])
        self.assertEqual(kopf["herkunft"], "wdm")

    def test_leere_positionen_akten_scope_ereignis(self):
        from backend.services.eingehende_ereignisse import erzeuge_aus_wdm
        from backend.db.database import get_connection

        eid = erzeuge_aus_wdm(
            akte_az="44/22", datum="2021-03-23", positionen=[],
        )
        self.assertIsNotNone(eid)
        with get_connection() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM ereignis_positionen WHERE ereignis_id=?",
                (eid,)
            ).fetchone()[0]
        self.assertEqual(n, 0)

    def test_mehrere_wdm_importe_erzeugen_mehrere_ereignisse(self):
        """Der Guard schlaegt NICHT an (dokument_id=NULL) -- 409 kommt
        aus dem Alt-Pfad. Der Helper produziert bei jedem Aufruf ein
        neues Ereignis (kein stiller Skip)."""
        from backend.services.eingehende_ereignisse import erzeuge_aus_wdm
        from backend.db.database import get_connection

        eid1 = erzeuge_aus_wdm(
            akte_az="44/22", datum="2021-03-23",
            positionen=[{"position_key": "reparaturkosten",
                          "betrag_gefordert": 3000.0,
                          "betrag_reguliert": 2616.71,
                          "kuerzungsart_id": None}],
        )
        eid2 = erzeuge_aus_wdm(
            akte_az="44/22", datum="2021-03-24",
            positionen=[{"position_key": "reparaturkosten",
                          "betrag_gefordert": 3000.0,
                          "betrag_reguliert": 2700.0,
                          "kuerzungsart_id": None}],
        )
        self.assertNotEqual(eid1, eid2)
        with get_connection() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM ereignisse "
                "WHERE herkunft='wdm'"
            ).fetchone()[0]
        self.assertEqual(n, 2)

    def test_wdm_positionen_gemapped_wie_regulierung(self):
        """WDM-Positionen haben dieselbe Struktur wie ReguWizard-Positionen
        -- der Helper nutzt dieselbe Wirkungs-Ableitung."""
        from backend.services.eingehende_ereignisse import erzeuge_aus_wdm
        from backend.db.database import get_connection

        eid = erzeuge_aus_wdm(
            akte_az="44/22", datum="2021-03-23",
            positionen=[
                # Volle Regulierung -> anerkannt.
                {"position_key": "reparaturkosten",
                 "betrag_gefordert": 3000.0, "betrag_reguliert": 3000.0,
                 "kuerzungsart_id": None},
                # Teilweise reguliert ohne Kuerzungsart -> nur anerkannt,
                # KEIN gekuerzt/abgelehnt-Eintrag (weil kuerzungsart_id fehlt).
                {"position_key": "sv_kosten",
                 "betrag_gefordert": 800.0, "betrag_reguliert": 500.0,
                 "kuerzungsart_id": None},
            ],
        )
        with get_connection() as conn:
            wirkungen = [
                dict(r) for r in conn.execute(
                    "SELECT position_key, wirkung, betrag "
                    "FROM ereignis_positionen WHERE ereignis_id=? "
                    "ORDER BY position_key, wirkung", (eid,)
                ).fetchall()
            ]
        # reparaturkosten -> anerkannt 3000
        self.assertIn(
            {"position_key": "reparaturkosten", "wirkung": "anerkannt",
             "betrag": 3000.0}, wirkungen,
        )
        # sv_kosten -> nur anerkannt 500, kein gekuerzt (ohne Kuerzungsart).
        sv_rows = [w for w in wirkungen if w["position_key"] == "sv_kosten"]
        self.assertEqual(len(sv_rows), 1)
        self.assertEqual(sv_rows[0]["wirkung"], "anerkannt")


class TestWdmRouteInstrumentierung(unittest.TestCase):
    """Statischer Import-Check: wdm_import ruft erzeuge_aus_wdm auf."""

    def test_abrechnungsschreiben_routes_ruft_erzeuge_aus_wdm(self):
        import inspect
        from backend.routers import abrechnungsschreiben_routes
        src = inspect.getsource(abrechnungsschreiben_routes)
        self.assertIn(
            "erzeuge_aus_wdm", src,
            "abrechnungsschreiben_routes.py enthaelt keinen Aufruf von "
            "erzeuge_aus_wdm -- P1.5d-Instrumentierung fehlt.",
        )


if __name__ == "__main__":
    unittest.main()
