"""P1.5e — Review-Freigabe erzeugt Ereignisse fuer alle Klassen."""
import importlib
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class _HelperBasis(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="p15e_", suffix=".sqlite")
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
                "dateityp, typ) VALUES ('44/22', 'd.pdf', 'x', 'pdf', 'gutachten')"
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
                "SELECT id FROM dokumente WHERE dateiname='d.pdf'"
            ).fetchone()["id"]

    def _positionen(self, eid):
        from backend.db.database import get_connection
        with get_connection() as conn:
            return conn.execute(
                "SELECT position_key, wirkung, betrag FROM ereignis_positionen "
                "WHERE ereignis_id=? ORDER BY position_key", (eid,)
            ).fetchall()

    def _kopf(self, eid):
        from backend.db.database import get_connection
        with get_connection() as conn:
            return conn.execute(
                "SELECT ereignistyp, herkunft FROM ereignisse WHERE id=?",
                (eid,)
            ).fetchone()


class TestErzeugeAusFreigabe(_HelperBasis):
    def test_gutachten_positionen_gefordert(self):
        from backend.services.eingehende_ereignisse import erzeuge_aus_freigabe
        eid = erzeuge_aus_freigabe(
            akte_az="44/22", dokument_id=self._dok_id(),
            ereignistyp="gutachten_eingegangen", klasse="gutachten",
            felder={"reparaturkosten_netto": "6.200,00",
                    "wertminderung": "500,00"},
            datum="2022-04-30",
        )
        self.assertIsInstance(eid, int)
        rows = self._positionen(eid)
        keys = {r["position_key"] for r in rows}
        self.assertEqual(keys, {"reparaturkosten", "wertminderung"})
        for r in rows:
            self.assertEqual(r["wirkung"], "gefordert")
        self.assertEqual(self._kopf(eid)["herkunft"], "freigabe")

    def test_rechnung_beleg_position_aus_mapping(self):
        from backend.services.eingehende_ereignisse import erzeuge_aus_freigabe
        eid = erzeuge_aus_freigabe(
            akte_az="44/22", dokument_id=self._dok_id(),
            ereignistyp="rechnung_eingegangen", klasse="abschlepprechnung",
            felder={"bruttobetrag": "350,00"}, datum="2022-05-01",
        )
        rows = self._positionen(eid)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["position_key"], "abschleppkosten")
        self.assertEqual(rows[0]["wirkung"], "beleg")
        self.assertEqual(rows[0]["betrag"], 350.0)

    def test_abrechnung_ist_fakt_ohne_positionen(self):
        from backend.services.eingehende_ereignisse import erzeuge_aus_freigabe
        eid = erzeuge_aus_freigabe(
            akte_az="44/22", dokument_id=self._dok_id(),
            ereignistyp="abrechnung_eingegangen", klasse="abrechnungsschreiben",
            felder={"bruttobetrag": "1.000,00"}, datum="2022-05-01",
        )
        self.assertIsInstance(eid, int)
        self.assertEqual(len(self._positionen(eid)), 0)

    def test_rechnung_ohne_mapping_ist_fakt(self):
        from backend.services.eingehende_ereignisse import erzeuge_aus_freigabe
        eid = erzeuge_aus_freigabe(
            akte_az="44/22", dokument_id=self._dok_id(),
            ereignistyp="rechnung_eingegangen", klasse="rechnung",
            felder={"bruttobetrag": "80,00"}, datum="2022-05-01",
        )
        self.assertIsInstance(eid, int)
        self.assertEqual(len(self._positionen(eid)), 0)

    def test_doppelerfassungs_guard(self):
        from backend.services.eingehende_ereignisse import erzeuge_aus_freigabe
        from backend.db.database import get_connection
        did = self._dok_id()
        e1 = erzeuge_aus_freigabe(
            akte_az="44/22", dokument_id=did,
            ereignistyp="abrechnung_eingegangen", klasse="abrechnungsschreiben",
            felder={}, datum="2022-05-01",
        )
        e2 = erzeuge_aus_freigabe(
            akte_az="44/22", dokument_id=did,
            ereignistyp="abrechnung_eingegangen", klasse="abrechnungsschreiben",
            felder={}, datum="2022-05-02",
        )
        self.assertEqual(e1, e2)
        with get_connection() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM ereignisse WHERE dokument_id=? "
                "AND ereignistyp='abrechnung_eingegangen'", (did,)
            ).fetchone()[0]
        self.assertEqual(n, 1)
