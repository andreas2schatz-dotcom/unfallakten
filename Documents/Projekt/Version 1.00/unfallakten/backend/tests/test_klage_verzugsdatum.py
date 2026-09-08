"""Verzugsdokumente tragen das Datum des Schreibens."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestVerzugsdokumente(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="klvd_", suffix=".sqlite")
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
                "dateityp, dokumentenklasse, dokument_datum) VALUES "
                "('44/22', 'alt.pdf', 'x', 'pdf', 'forderungsschreiben', "
                " '2024-02-01')"
            )
            conn.execute(
                "INSERT INTO dokumente (akte_id, dateiname, dateipfad, "
                "dateityp, dokumentenklasse, dokument_datum) VALUES "
                "('44/22', 'neu.pdf', 'y', 'pdf', 'forderungsschreiben', "
                " '2024-06-15')"
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

    def test_juengstes_schreiben_steht_vorn(self):
        from backend.routers.klage_routes import _verzug_dokumente
        dokumente = _verzug_dokumente("44/22")
        self.assertEqual(dokumente[0]["dateiname"], "neu.pdf")
        self.assertEqual(dokumente[0]["datum"], "2024-06-15")

    def test_dokument_ohne_datum_faellt_ans_ende(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO dokumente (akte_id, dateiname, dateipfad, "
                "dateityp, dokumentenklasse) VALUES "
                "('44/22', 'ohne.pdf', 'z', 'pdf', 'forderungsschreiben')"
            )
            conn.commit()
        from backend.routers.klage_routes import _verzug_dokumente
        dokumente = _verzug_dokumente("44/22")
        self.assertEqual(dokumente[-1]["dateiname"], "ohne.pdf")
        self.assertIsNone(dokumente[-1]["datum"])

    def test_mahnschreiben_steht_vor_forderungsschreiben(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO dokumente (akte_id, dateiname, dateipfad, "
                "dateityp, dokumentenklasse, dokument_datum) VALUES "
                "('44/22', 'mahn.pdf', 'm', 'pdf', 'mahnschreiben', "
                " '2024-03-01')"
            )
            conn.commit()
        from backend.routers.klage_routes import _verzug_dokumente
        dokumente = _verzug_dokumente("44/22")
        self.assertEqual(dokumente[0]["dokumentenklasse"], "mahnschreiben")


class TestJuengstesVerzugsdatum(unittest.TestCase):
    def _fn(self):
        from backend.routers.klage_routes import _juengstes_verzugsdatum
        return _juengstes_verzugsdatum

    def test_juengstes_datum_gewinnt_gegen_die_klassenreihenfolge(self):
        # So sortiert _verzug_dokumente: Mahnschreiben zuerst, obwohl aelter.
        dokumente = [
            {"dokumentenklasse": "mahnschreiben", "datum": "2023-05-04"},
            {"dokumentenklasse": "forderungsschreiben", "datum": "2025-01-20"},
        ]
        self.assertEqual(self._fn()(dokumente), "2025-01-20")

    def test_dokumente_ohne_datum_werden_uebergangen(self):
        dokumente = [
            {"dokumentenklasse": "mahnschreiben", "datum": None},
            {"dokumentenklasse": "forderungsschreiben", "datum": "2024-02-01"},
        ]
        self.assertEqual(self._fn()(dokumente), "2024-02-01")

    def test_ohne_dokumente_none(self):
        self.assertIsNone(self._fn()([]))
        self.assertIsNone(self._fn()(None))


if __name__ == "__main__":
    unittest.main()
