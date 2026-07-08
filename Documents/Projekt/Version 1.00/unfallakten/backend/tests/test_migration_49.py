"""
Tests fuer Migration 49 (S1.9a):

Erweitert ``email_import_log`` um eine Spalte ``ausgeblendet INTEGER NOT
NULL DEFAULT 0``. Zustellungen werden nie geloescht -- der frontseitige
Loesch-Button wird ein Ausblenden-Toggle.

Additiv, idempotent, kein Datenverlust.
"""
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestMigration49(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="mig49_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad

        # Init laesst alle Migrationen laufen (Schema-Version steigt bis
        # zur aktuellen Zielversion, in der 49 enthalten sein muss).
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

    def test_spalte_ausgeblendet_existiert(self):
        with sqlite3.connect(self._db_pfad) as conn:
            conn.row_factory = sqlite3.Row
            spalten = {r["name"]: r
                        for r in conn.execute(
                            "PRAGMA table_info(email_import_log)"
                        ).fetchall()}
        self.assertIn("ausgeblendet", spalten,
                      "Migration 49: Spalte 'ausgeblendet' fehlt")
        col = spalten["ausgeblendet"]
        self.assertEqual(col["type"].upper(), "INTEGER")
        self.assertEqual(col["notnull"], 1,
                         "Spalte muss NOT NULL sein")
        self.assertEqual(col["dflt_value"], "0",
                         "Default 0 (nicht ausgeblendet)")

    def test_schema_version_49(self):
        with sqlite3.connect(self._db_pfad) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT beschreibung FROM schema_version WHERE version = 49"
            ).fetchone()
        self.assertIsNotNone(row, "schema_version 49 fehlt")

    def test_bestandsdaten_bleiben_erhalten(self):
        with sqlite3.connect(self._db_pfad) as conn:
            konto_col = {r[1] for r in conn.execute(
                "PRAGMA table_info(email_import_log)"
            ).fetchall()}
        self.assertIn("message_id", konto_col,
                      "email_import_log.message_id muss weiter existieren")

    def test_idempotent_bei_wiederholtem_init(self):
        from backend.db.schema_manager import init_db
        init_db()  # zweiter Lauf
        init_db()  # dritter Lauf
        with sqlite3.connect(self._db_pfad) as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM schema_version WHERE version = 49"
            ).fetchone()[0]
        self.assertEqual(n, 1,
                         "Migration 49 darf nur einmal registriert sein")


if __name__ == "__main__":
    unittest.main()
