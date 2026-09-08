"""Bestandsdokumente bekommen ihr Datum aus parse_json."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestNachziehen(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="nz_", suffix=".sqlite")
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
                "dateityp, dokumentenklasse, parse_json) VALUES "
                "('44/22', 'g.pdf', 'x', 'pdf', 'gutachten', ?)",
                (json.dumps({"felder": {"besichtigungsdatum": "14.03.2024"}}),)
            )
            conn.execute(
                "INSERT INTO dokumente (akte_id, dateiname, dateipfad, "
                "dateityp, dokumentenklasse) VALUES "
                "('44/22', 'leer.pdf', 'y', 'pdf', 'gutachten')"
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

    def _datum(self, dateiname):
        from backend.db.database import get_connection
        with get_connection() as conn:
            return conn.execute(
                "SELECT dokument_datum FROM dokumente WHERE dateiname=?",
                (dateiname,)
            ).fetchone()["dokument_datum"]

    def test_trockenlauf_aendert_nichts(self):
        from tools.dokument_datum_nachziehen import nachziehen
        bericht = nachziehen(trockenlauf=True)
        self.assertEqual(bericht["gesetzt"], 1)
        self.assertIsNone(self._datum("g.pdf"))

    def test_schreiblauf_setzt_das_datum(self):
        from tools.dokument_datum_nachziehen import nachziehen
        bericht = nachziehen(trockenlauf=False)
        self.assertEqual(bericht["gesetzt"], 1)
        self.assertEqual(bericht["ohne_datum"], 1)
        self.assertEqual(self._datum("g.pdf"), "2024-03-14")
        self.assertIsNone(self._datum("leer.pdf"))

    def test_zweiter_lauf_ueberschreibt_nichts(self):
        from tools.dokument_datum_nachziehen import nachziehen
        nachziehen(trockenlauf=False)
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "UPDATE dokumente SET dokument_datum='2020-01-01' "
                "WHERE dateiname='g.pdf'"
            )
            conn.commit()
        bericht = nachziehen(trockenlauf=False)
        self.assertEqual(bericht["gesetzt"], 0)
        self.assertEqual(self._datum("g.pdf"), "2020-01-01")


if __name__ == "__main__":
    unittest.main()
