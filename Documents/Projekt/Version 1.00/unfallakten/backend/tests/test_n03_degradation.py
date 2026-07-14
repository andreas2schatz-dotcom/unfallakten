import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class _BaseDbTest(unittest.TestCase):
    def setUp(self):
        fd, self._db = tempfile.mkstemp(prefix="n03_", suffix=".sqlite")
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


class TestMigration57(_BaseDbTest):
    def test_spalte_existiert_und_nullable(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            spalten = {r[1]: r for r in conn.execute(
                "PRAGMA table_info(intake_dokumente)").fetchall()}
        self.assertIn("llm_degradiert", spalten)
        self.assertEqual(spalten["llm_degradiert"][3], 0)  # notnull=0

    def test_idempotent(self):
        from backend.db.schema_manager import _run_migration_57
        from backend.db.database import get_connection
        with get_connection() as conn:
            _run_migration_57(conn)  # zweiter Lauf darf nicht werfen
            self.assertIn("llm_degradiert", {r[1] for r in conn.execute(
                "PRAGMA table_info(intake_dokumente)").fetchall()})
