"""
Tests fuer Migration 52 (P1.6): todos.fristablauf_ereignis_id.

Neue Spalte fuer Idempotenz des Fristablauf-Scheduler-Jobs:
jede todo-Zeile darf nur EIN fristablauf-Ereignis erzeugen. Der Job
liest todos WHERE quelle='system' AND erledigt=0 AND faellig_am<=heute
AND fristablauf_ereignis_id IS NULL und setzt beim Anlegen des
Ereignisses die Referenz.

Additiv, idempotent, kein Datenverlust an bestehenden todos.
"""
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestMigration52(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="mig52_", suffix=".sqlite")
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
        with sqlite3.connect(self._db_pfad) as conn:
            conn.row_factory = sqlite3.Row
            spalten = {r["name"] for r in conn.execute(
                "PRAGMA table_info(todos)"
            ).fetchall()}
        self.assertIn(
            "fristablauf_ereignis_id", spalten,
            "todos.fristablauf_ereignis_id fehlt nach Migration 52",
        )

    def test_spalte_ist_nullable(self):
        """Existierende todos ohne fristablauf_ereignis_id muessen erlaubt sein."""
        with sqlite3.connect(self._db_pfad) as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('44/22', '2022-04-27', 'offen')"
            )
            conn.execute(
                "INSERT INTO todos (akte_az, text, faellig_am, frist_typ, "
                " quelle, regel_key) "
                "VALUES ('44/22', 'Verjaehrung heute', '2026-12-31', "
                " 'verjaehrung', 'system', 'verjaehrung')"
            )
            row = conn.execute(
                "SELECT fristablauf_ereignis_id FROM todos"
            ).fetchone()
        self.assertIsNone(row[0])

    def test_fk_auf_ereignisse(self):
        """fristablauf_ereignis_id ist FK auf ereignisse(id)."""
        with sqlite3.connect(self._db_pfad) as conn:
            fks = conn.execute("PRAGMA foreign_key_list(todos)").fetchall()
        ziele = {(fk[2], fk[4]) for fk in fks}
        self.assertIn(
            ("ereignisse", "id"), ziele,
            f"FK todos.fristablauf_ereignis_id -> ereignisse(id) fehlt. "
            f"Gefundene FKs: {ziele}",
        )

    def test_index_fuer_scheduler(self):
        """Index auf (quelle, erledigt, faellig_am, fristablauf_ereignis_id)
        beschleunigt den Scheduler-Scan spuerbar."""
        with sqlite3.connect(self._db_pfad) as conn:
            idx_namen = {r[1] for r in conn.execute(
                "PRAGMA index_list(todos)"
            ).fetchall()}
        self.assertIn("idx_todos_fristablauf_pending", idx_namen)

    def test_schema_version_52(self):
        with sqlite3.connect(self._db_pfad) as conn:
            row = conn.execute(
                "SELECT beschreibung FROM schema_version WHERE version = 52"
            ).fetchone()
        self.assertIsNotNone(row, "schema_version 52 fehlt")

    def test_idempotent(self):
        from backend.db.schema_manager import init_db
        init_db()
        init_db()
        with sqlite3.connect(self._db_pfad) as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM schema_version WHERE version = 52"
            ).fetchone()[0]
        self.assertEqual(n, 1)


if __name__ == "__main__":
    unittest.main()
