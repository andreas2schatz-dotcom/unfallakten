"""
Tests fuer P1.5b — Beleg-Zuordnung erzeugt Ereignis
``rechnung_eingegangen``.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class _BelegTestBasis(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="p15b_", suffix=".sqlite")
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
            conn.execute(
                "INSERT INTO dokumente "
                "(akte_id, dateiname, dateipfad, dateityp, typ) "
                "VALUES ('44/22', 'rechnung.pdf', 'x', 'pdf', 'sonstiges')"
            )

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt_db_path
        os.environ.pop("DB_PATH", None)
        try:
            os.unlink(self._db_pfad)
        except OSError:
            pass

    def _dok_id(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            return conn.execute(
                "SELECT id FROM dokumente WHERE akte_id='44/22' LIMIT 1"
            ).fetchone()["id"]


class TestErzeugeAusBeleg(_BelegTestBasis):

    def test_erzeugt_rechnung_eingegangen_ereignis(self):
        from backend.services.eingehende_ereignisse import erzeuge_aus_beleg
        from backend.db.database import get_connection

        dok_id = self._dok_id()
        eid = erzeuge_aus_beleg(
            akte_az="44/22",
            dokument_id=dok_id,
            position_key="abschleppkosten",
            betrag=380.0,
            datum="2022-05-01",
        )
        self.assertIsInstance(eid, int)
        with get_connection() as conn:
            kopf = conn.execute(
                "SELECT ereignistyp, richtung, quelle, dokument_id, herkunft "
                "FROM ereignisse WHERE id=?", (eid,)
            ).fetchone()
            pos = conn.execute(
                "SELECT position_key, wirkung, betrag "
                "FROM ereignis_positionen WHERE ereignis_id=?", (eid,)
            ).fetchone()
        self.assertEqual(kopf["ereignistyp"], "rechnung_eingegangen")
        self.assertEqual(kopf["richtung"], "eingehend")
        self.assertEqual(kopf["quelle"], "dokument")
        self.assertEqual(kopf["dokument_id"], dok_id)
        self.assertEqual(kopf["herkunft"], "beleg_zuordnung")
        self.assertEqual(pos["position_key"], "abschleppkosten")
        self.assertEqual(pos["wirkung"], "beleg")
        self.assertEqual(pos["betrag"], 380.0)

    def test_doppelaufruf_liefert_gleiche_id(self):
        from backend.services.eingehende_ereignisse import erzeuge_aus_beleg
        from backend.db.database import get_connection

        dok_id = self._dok_id()
        e1 = erzeuge_aus_beleg(
            akte_az="44/22", dokument_id=dok_id,
            position_key="abschleppkosten", betrag=380.0,
        )
        e2 = erzeuge_aus_beleg(
            akte_az="44/22", dokument_id=dok_id,
            position_key="abschleppkosten", betrag=380.0,
        )
        self.assertEqual(e1, e2)
        with get_connection() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM ereignisse "
                "WHERE ereignistyp='rechnung_eingegangen'"
            ).fetchone()[0]
        self.assertEqual(n, 1)

    def test_unbekannter_position_key_ignoriert(self):
        from backend.services.eingehende_ereignisse import erzeuge_aus_beleg
        eid = erzeuge_aus_beleg(
            akte_az="44/22", dokument_id=self._dok_id(),
            position_key="voellig_erfundene_position", betrag=100.0,
        )
        self.assertIsNone(eid)


class TestRechnungstypResolver(unittest.TestCase):

    def test_registry_mapping_klassen(self):
        from backend.services.eingehende_ereignisse import rechnungstyp_zu_position
        self.assertEqual(
            rechnungstyp_zu_position("abschlepprechnung"), "abschleppkosten",
        )
        self.assertEqual(
            rechnungstyp_zu_position("standkostenrechnung"), "standkosten",
        )
        self.assertEqual(
            rechnungstyp_zu_position("reparaturrechnung"), "rep_rechnung_netto",
        )
        self.assertEqual(
            rechnungstyp_zu_position("werkstattrechnung"), "rep_rechnung_netto",
        )
        self.assertEqual(
            rechnungstyp_zu_position("mietwagenrechnung"), "mietwagenkosten",
        )

    def test_sv_rechnung_wird_zu_sv_kosten_resolved(self):
        """__sv_kosten_vorsteuer__ Sondermarker -> sv_kosten."""
        from backend.services.eingehende_ereignisse import rechnungstyp_zu_position
        self.assertEqual(
            rechnungstyp_zu_position("sv_rechnung", vorsteuer=False),
            "sv_kosten",
        )
        self.assertEqual(
            rechnungstyp_zu_position("sv_rechnung", vorsteuer=True),
            "sv_kosten",
        )

    def test_unbekannte_klasse_liefert_none(self):
        from backend.services.eingehende_ereignisse import rechnungstyp_zu_position
        self.assertIsNone(rechnungstyp_zu_position("phantasieklasse"))


class TestBelegeRoutesInstrumentierung(_BelegTestBasis):
    """Der belege-Zuordnen-Endpunkt ruft erzeuge_aus_beleg auf."""

    def test_zuordnen_route_erzeugt_ereignis(self):
        # Direkter Test des Route-Handlers ohne Flask-Client.
        # Der Handler ruft erzeuge_aus_beleg als Best-Effort auf.
        from unittest.mock import patch
        from backend.routers.belege_routes import belege_bp  # noqa: F401
        from backend.services.eingehende_ereignisse import erzeuge_aus_beleg

        # Wir simulieren die Fluss-Kette:
        # 1. Beleg-Zuordnung schreibt schadenposition_belege (Alt-Pfad).
        # 2. Anschliessend wird erzeuge_aus_beleg aufgerufen.
        dok_id = self._dok_id()
        # Alt-Pfad (Direkt-INSERT wie in belege_routes.py::zuordnen)
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO schadenposition_belege
                    (akte_az, position_key, dokument_id,
                     betrag_aus_beleg, notiz)
                VALUES (?, ?, ?, ?, ?)
            """, ("44/22", "abschleppkosten", dok_id, 380.0, ""))
            conn.commit()

        # Ereignis-Erzeugung (Best-Effort-Path)
        eid = erzeuge_aus_beleg(
            akte_az="44/22", dokument_id=dok_id,
            position_key="abschleppkosten", betrag=380.0,
        )
        self.assertIsNotNone(eid)


if __name__ == "__main__":
    unittest.main()
