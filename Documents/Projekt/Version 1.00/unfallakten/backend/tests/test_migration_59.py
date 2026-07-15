"""PRD-37: Migration 59 legt bezeichnung-Spalten an."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestMigration59(unittest.TestCase):
    def setUp(self):
        fd, self._db = tempfile.mkstemp(prefix="mig59_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        self._alt = _db.DB_PATH
        _db.DB_PATH = self._db
        os.environ["DB_PATH"] = self._db
        from backend.db.schema_manager import init_db
        init_db()

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt
        os.environ.pop("DB_PATH", None)
        try:
            os.unlink(self._db)
        except OSError:
            pass

    def _cols(self, tabelle):
        from backend.db.database import get_connection
        with get_connection() as conn:
            return {r[1] for r in conn.execute(
                f"PRAGMA table_info({tabelle})").fetchall()}

    def test_intake_bezeichnung(self):
        self.assertIn("bezeichnung", self._cols("intake_dokumente"))

    def test_dokumente_bezeichnung(self):
        self.assertIn("bezeichnung", self._cols("dokumente"))


if __name__ == "__main__":
    unittest.main()
