import importlib
import os
import sys
import tempfile
import unittest

_tmp = tempfile.mkdtemp(prefix="mig65_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestMigration65(unittest.TestCase):
    def setUp(self):
        self._db_pfad = os.path.join(_tmp, f"{self._testMethodName}.db")
        if os.path.exists(self._db_pfad):
            os.remove(self._db_pfad)
        os.environ["DB_PATH"] = self._db_pfad
        import backend.db.database as db_mod
        import backend.db.schema_manager as sm
        importlib.reload(db_mod)
        importlib.reload(sm)
        from backend.app import erstelle_app
        self.app = erstelle_app({"TESTING": True})

    def test_tabelle_und_version(self):
        import sqlite3
        conn = sqlite3.connect(self._db_pfad)
        conn.row_factory = sqlite3.Row
        spalten = {r[1] for r in conn.execute(
            "PRAGMA table_info(standardtext_override)").fetchall()}
        self.assertEqual({"id", "baustein_key", "text", "geaendert_am"}, spalten)
        version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
        self.assertGreaterEqual(version, 65)
        conn.execute(
            "INSERT INTO standardtext_override (baustein_key, text) VALUES (?, ?)",
            ("schluss_hinweis", "X"))
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO standardtext_override (baustein_key, text) VALUES (?, ?)",
                ("schluss_hinweis", "Y"))
        conn.close()

    def test_model_roundtrip(self):
        from backend.models import standardtext_override as m
        self.assertEqual({}, m.hole_alle_overrides())
        m.setze_override("schluss_hinweis2", "Eigener Text.")
        m.setze_override("schluss_hinweis2", "Eigener Text v2.")
        self.assertEqual({"schluss_hinweis2": "Eigener Text v2."}, m.hole_alle_overrides())
        meta = m.hole_alle_overrides_mit_meta()["schluss_hinweis2"]
        self.assertEqual("Eigener Text v2.", meta["text"])
        self.assertTrue(meta["geaendert_am"])
        self.assertTrue(m.loesche_override("schluss_hinweis2"))
        self.assertFalse(m.loesche_override("schluss_hinweis2"))
        self.assertEqual({}, m.hole_alle_overrides())


if __name__ == "__main__":
    unittest.main()
