"""R2 — die Review-Freigabe traegt ihre Belege in die Belegliste ein."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class _Basis(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="belzu_", suffix=".sqlite")
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
                "INSERT INTO dokumente (akte_id, dateiname, dateipfad, "
                "dateityp, dokumentenklasse) "
                "VALUES ('44/22', 'r.pdf', 'x', 'pdf', 'mietwagenrechnung')"
            )
            conn.commit()

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
                "SELECT id FROM dokumente WHERE dateiname='r.pdf'"
            ).fetchone()["id"]

    def _belege(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT position_key, dokument_id, betrag_aus_beleg "
                "FROM schadenposition_belege WHERE akte_az='44/22' "
                "ORDER BY position_key"
            ).fetchall()]


class TestOrdneBelegZu(_Basis):
    def test_legt_zuordnung_an(self):
        from backend.services.beleg_zuordnung import ordne_beleg_zu
        ordne_beleg_zu(akte_az="44/22", position_key="mietwagenkosten",
                       dokument_id=self._dok_id(), betrag=812.50)
        belege = self._belege()
        self.assertEqual(len(belege), 1)
        self.assertEqual(belege[0]["position_key"], "mietwagenkosten")
        self.assertEqual(belege[0]["betrag_aus_beleg"], 812.50)

    def test_zweiter_aufruf_aktualisiert_statt_zu_doppeln(self):
        from backend.services.beleg_zuordnung import ordne_beleg_zu
        ordne_beleg_zu(akte_az="44/22", position_key="mietwagenkosten",
                       dokument_id=self._dok_id(), betrag=812.50)
        ordne_beleg_zu(akte_az="44/22", position_key="mietwagenkosten",
                       dokument_id=self._dok_id(), betrag=900.00)
        belege = self._belege()
        self.assertEqual(len(belege), 1)
        self.assertEqual(belege[0]["betrag_aus_beleg"], 900.00)

    def test_unbekannte_position_wird_abgelehnt(self):
        from backend.services.beleg_zuordnung import ordne_beleg_zu
        with self.assertRaises(ValueError):
            ordne_beleg_zu(akte_az="44/22", position_key="fantasieposten",
                           dokument_id=self._dok_id())


class TestBelegeAusFreigabe(_Basis):
    def test_rechnung_erzeugt_einen_beleg(self):
        from backend.services.beleg_zuordnung import belege_aus_freigabe
        keys = belege_aus_freigabe(
            akte_az="44/22", dokument_id=self._dok_id(),
            klasse="mietwagenrechnung",
            felder={"bruttobetrag": "812,50"},
        )
        self.assertEqual(keys, ["mietwagenkosten"])
        self.assertEqual(self._belege()[0]["betrag_aus_beleg"], 812.50)

    def test_gutachten_belegt_mehrere_positionen(self):
        from backend.services.beleg_zuordnung import belege_aus_freigabe
        keys = belege_aus_freigabe(
            akte_az="44/22", dokument_id=self._dok_id(), klasse="gutachten",
            felder={"wiederbeschaffungswert": "12000,00",
                    "restwert_brutto": "3000,00",
                    "wertminderung": "800,00"},
        )
        self.assertGreater(len(keys), 1)
        self.assertEqual(len(self._belege()), len(keys))

    def test_klasse_ohne_positionsbezug_schreibt_nichts(self):
        from backend.services.beleg_zuordnung import belege_aus_freigabe
        keys = belege_aus_freigabe(
            akte_az="44/22", dokument_id=self._dok_id(), klasse="arztbericht",
            felder={"datum": "01.02.2024"},
        )
        self.assertEqual(keys, [])
        self.assertEqual(self._belege(), [])

    def test_auffangklasse_rechnung_schreibt_nichts(self):
        from backend.services.beleg_zuordnung import belege_aus_freigabe
        keys = belege_aus_freigabe(
            akte_az="44/22", dokument_id=self._dok_id(), klasse="rechnung",
            felder={"bruttobetrag": "100,00"},
        )
        self.assertEqual(keys, [])


if __name__ == "__main__":
    unittest.main()
