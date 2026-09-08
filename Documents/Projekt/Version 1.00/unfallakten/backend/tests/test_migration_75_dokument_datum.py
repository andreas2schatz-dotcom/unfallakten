"""Migration 75 — dokumente.dokument_datum."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestMigration75(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="mig75_", suffix=".sqlite")
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

    def test_spalte_existiert(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            spalten = {r[1] for r in conn.execute(
                "PRAGMA table_info(dokumente)").fetchall()}
        self.assertIn("dokument_datum", spalten)

    def test_index_existiert(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            namen = {r["name"] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'").fetchall()}
        self.assertIn("idx_dokumente_datum", namen)

    def test_datum_ist_schreibbar_und_nullable(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('44/22', '2022-04-27', 'offen')"
            )
            conn.execute(
                "INSERT INTO dokumente (akte_id, dateiname, dateipfad, "
                "dateityp, dokumentenklasse, dokument_datum) "
                "VALUES ('44/22', 'a.pdf', 'x', 'pdf', 'gutachten', '2024-03-14')"
            )
            conn.execute(
                "INSERT INTO dokumente (akte_id, dateiname, dateipfad, "
                "dateityp, dokumentenklasse) "
                "VALUES ('44/22', 'b.pdf', 'y', 'pdf', 'sonstiges')"
            )
            conn.commit()
            zeilen = conn.execute(
                "SELECT dateiname, dokument_datum FROM dokumente "
                "ORDER BY dateiname"
            ).fetchall()
        self.assertEqual(zeilen[0]["dokument_datum"], "2024-03-14")
        self.assertIsNone(zeilen[1]["dokument_datum"])

    def test_version_eingetragen(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT version FROM schema_version WHERE version=75"
            ).fetchone()
        self.assertIsNotNone(row)


if __name__ == "__main__":
    unittest.main()
