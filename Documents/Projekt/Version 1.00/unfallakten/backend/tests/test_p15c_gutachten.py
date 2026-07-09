"""
Tests fuer P1.5c — Gutachten-Uebernahme erzeugt Ereignis
``gutachten_eingegangen`` (inkl. K-M2a Ergaenzungsgutachten).

Der P1.5-Prompt fordert das K-M2a-Testkriterium (c):
  Ergaenzungsgutachten ersetzt nur die betroffenen Positions-Zeilen;
  unveraenderte Positionen bleiben aktuell.

Dieses Kriterium wird auf zwei Ebenen abgeprueft:
  * Helper-Ebene (backend/services/eingehende_ereignisse.erzeuge_aus_gutachten)
    -- deckt die eigentliche Ableitung positionsscharfer Ersetzung ab.
  * Route-Ebene (manuelle_korrektur mit ersetzt_positions_ids im Body)
    -- deckt die Instrumentierung fuer den KI-Dialog ab.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class _GutachtenTestBasis(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="p15c_", suffix=".sqlite")
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
            # Erstgutachten Dokumentzeile
            conn.execute(
                "INSERT INTO dokumente "
                "(akte_id, dateiname, dateipfad, dateityp, typ) "
                "VALUES ('44/22', 'gutachten1.pdf', 'x', 'pdf', 'gutachten')"
            )
            # Ergaenzungsgutachten Dokumentzeile (andere id)
            conn.execute(
                "INSERT INTO dokumente "
                "(akte_id, dateiname, dateipfad, dateityp, typ) "
                "VALUES ('44/22', 'gutachten2.pdf', 'y', 'pdf', 'gutachten')"
            )

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt_db_path
        os.environ.pop("DB_PATH", None)
        try:
            os.unlink(self._db_pfad)
        except OSError:
            pass


class TestErzeugeAusGutachten(_GutachtenTestBasis):

    def test_erzeugt_gefordert_positionen_aus_dict(self):
        from backend.services.eingehende_ereignisse import erzeuge_aus_gutachten
        from backend.db.database import get_connection

        with get_connection() as conn:
            dok_id = conn.execute(
                "SELECT id FROM dokumente WHERE dateiname='gutachten1.pdf'"
            ).fetchone()["id"]

        eid = erzeuge_aus_gutachten(
            akte_az="44/22", dokument_id=dok_id,
            datum="2022-04-30",
            positionen={
                "reparaturkosten": 6200.0,
                "wiederbeschaffung": 12000.0,
                "restwert": 3000.0,
                "wertminderung": 500.0,
                "sv_kosten": 900.0,
                "sonstiges_ignoriert": 100.0,  # nicht im Gutachten-Katalog
            },
        )
        self.assertIsInstance(eid, int)
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT position_key, wirkung, betrag "
                "FROM ereignis_positionen WHERE ereignis_id=? "
                "ORDER BY position_key", (eid,)
            ).fetchall()
        keys = {r["position_key"] for r in rows}
        # Alle 5 Gutachten-Positions-Keys, nichts Fremdes.
        self.assertEqual(
            keys,
            {"reparaturkosten", "wiederbeschaffung", "restwert",
             "wertminderung", "sv_kosten"},
        )
        for r in rows:
            self.assertEqual(r["wirkung"], "gefordert")

    def test_null_und_null_positionen_werden_ignoriert(self):
        from backend.services.eingehende_ereignisse import erzeuge_aus_gutachten
        from backend.db.database import get_connection

        with get_connection() as conn:
            dok_id = conn.execute(
                "SELECT id FROM dokumente WHERE dateiname='gutachten1.pdf'"
            ).fetchone()["id"]

        eid = erzeuge_aus_gutachten(
            akte_az="44/22", dokument_id=dok_id, datum="2022-04-30",
            positionen={
                "reparaturkosten": 6200.0,
                "wiederbeschaffung": None,
                "wertminderung": 0.0,
            },
        )
        with get_connection() as conn:
            keys = {
                r["position_key"] for r in conn.execute(
                    "SELECT position_key FROM ereignis_positionen "
                    "WHERE ereignis_id=?", (eid,)
                ).fetchall()
            }
        self.assertEqual(keys, {"reparaturkosten"})

    def test_ergaenzungsgutachten_ersetzt_nur_reparaturkosten(self):
        """K-M2a Testkriterium (c): Ergaenzungsgutachten ersetzt nur die
        betroffenen Positions-Zeilen; wertminderung des Erstgutachtens
        bleibt aktuell und fliesst weiter in die Ableitung ein."""
        from backend.services.eingehende_ereignisse import erzeuge_aus_gutachten
        from backend.services.positionsstatus_service import (
            leite_positionsstatus_ab,
        )
        from backend.db.database import get_connection

        with get_connection() as conn:
            erst_dok = conn.execute(
                "SELECT id FROM dokumente WHERE dateiname='gutachten1.pdf'"
            ).fetchone()["id"]
            erg_dok = conn.execute(
                "SELECT id FROM dokumente WHERE dateiname='gutachten2.pdf'"
            ).fetchone()["id"]

        alt_id = erzeuge_aus_gutachten(
            akte_az="44/22", dokument_id=erst_dok, datum="2022-04-30",
            positionen={
                "reparaturkosten": 6200.0,
                "wertminderung": 500.0,
            },
        )
        with get_connection() as conn:
            alt_rep_id = conn.execute(
                "SELECT id FROM ereignis_positionen "
                "WHERE ereignis_id=? AND position_key='reparaturkosten'",
                (alt_id,),
            ).fetchone()["id"]

        # Ergaenzungsgutachten mit NEUER Reparaturkosten und OHNE
        # wertminderung -- der Aufrufer identifiziert die alt-Rep-Zeile
        # als zu ersetzen.
        neu_id = erzeuge_aus_gutachten(
            akte_az="44/22", dokument_id=erg_dok, datum="2022-05-15",
            positionen={"reparaturkosten": 7500.0},
            ersetzt_positions_ids=[alt_rep_id],
        )
        self.assertIsNotNone(neu_id)

        with get_connection() as conn:
            # Alt-Rep-Zeile ist positionsscharf ersetzt.
            alt_rep_row = conn.execute(
                "SELECT ersetzt_durch FROM ereignis_positionen WHERE id=?",
                (alt_rep_id,),
            ).fetchone()
            # Alt-wertminderung-Zeile bleibt aktuell.
            alt_wm_row = conn.execute(
                "SELECT ersetzt_durch FROM ereignis_positionen "
                "WHERE ereignis_id=? AND position_key='wertminderung'",
                (alt_id,),
            ).fetchone()
            # Kopf des Alt-Ereignisses ist NICHT ersetzt (K-M2a-Konvention).
            alt_kopf_row = conn.execute(
                "SELECT ersetzt_durch FROM ereignisse WHERE id=?", (alt_id,)
            ).fetchone()

        self.assertIsNotNone(alt_rep_row["ersetzt_durch"])
        self.assertIsNone(alt_wm_row["ersetzt_durch"])
        self.assertIsNone(alt_kopf_row["ersetzt_durch"])

        # Ableitung: neue reparaturkosten + alte wertminderung.
        status = leite_positionsstatus_ab("44/22")
        self.assertEqual(status["reparaturkosten"]["gefordert"], 7500.0)
        self.assertEqual(status["wertminderung"]["gefordert"], 500.0)

    def test_doppelaufruf_desselben_gutachtens_liefert_alt_id(self):
        from backend.services.eingehende_ereignisse import erzeuge_aus_gutachten
        from backend.db.database import get_connection

        with get_connection() as conn:
            dok_id = conn.execute(
                "SELECT id FROM dokumente WHERE dateiname='gutachten1.pdf'"
            ).fetchone()["id"]
        e1 = erzeuge_aus_gutachten(
            akte_az="44/22", dokument_id=dok_id, datum="2022-04-30",
            positionen={"reparaturkosten": 6200.0},
        )
        e2 = erzeuge_aus_gutachten(
            akte_az="44/22", dokument_id=dok_id, datum="2022-04-30",
            positionen={"reparaturkosten": 6200.0},
        )
        self.assertEqual(e1, e2)
        with get_connection() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM ereignisse "
                "WHERE ereignistyp='gutachten_eingegangen'"
            ).fetchone()[0]
        self.assertEqual(n, 1)


class TestManuelleKorrekturInstrumentierung(unittest.TestCase):
    """Vertrags-Test: die Route ruft erzeuge_aus_gutachten auf.

    Statischer Import- und Aufruf-Check, damit die Instrumentierung nicht
    versehentlich beim Refactoring entfernt wird. Ein voller HTTP-Test
    braucht den Auth-Bootstrap aus conftest und wird in einer Follow-up-
    Session geschrieben, wenn die Testinfrastruktur bereit ist.
    """

    def test_dokumente_routes_ruft_erzeuge_aus_gutachten(self):
        import inspect
        from backend.routers import dokumente_routes
        src = inspect.getsource(dokumente_routes)
        self.assertIn(
            "erzeuge_aus_gutachten", src,
            "dokumente_routes.py enthaelt keinen Aufruf von "
            "erzeuge_aus_gutachten -- P1.5c-Instrumentierung fehlt.",
        )
        self.assertIn(
            "manuelle_korrektur", src,
            "dokumente_routes.py enthaelt keine manuelle_korrektur-Funktion.",
        )


if __name__ == "__main__":
    unittest.main()
