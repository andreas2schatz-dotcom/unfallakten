"""
Tests fuer Migration 48 (S1.6a) — Queue-Felder auf intake_dokumente.

Additiv:
  * versuch_zaehler     INTEGER NOT NULL DEFAULT 0
  * naechster_versuch   TEXT NULL   (ISO-Timestamp; wenn NULL -> sofort faellig)
  * fehler_detail       TEXT NULL   (letzte Fehlermeldung)
  * worker_lease        TEXT NULL   ("<worker_id>|<ablauf_iso>", nur waehrend laeuft)

Idempotent: zweite Ausfuehrung ist No-Op. Explizites conn.commit() umgibt ALTER TABLE.
"""
import os
import sys
import sqlite3
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestMigration48(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="mig48_", suffix=".sqlite")
        os.close(fd)
        # DB mit vorherigem Schema (bis Migration 47) aufsetzen.
        # Wir rufen init_db und stoppen dann visuell den Schema-Level.
        # Fuer den Test reicht es, Migration 46 anzustossen (S1.1 - intake_dokumente).
        os.environ["DB_PATH"] = self._db_pfad
        from backend.db.database import get_connection
        from backend.db.schema_manager import init_db
        init_db()
        with get_connection() as conn:
            row = conn.execute(
                "SELECT MAX(version) AS v FROM schema_version"
            ).fetchone()
            self._version_nach_init = row["v"]

    def tearDown(self):
        os.environ.pop("DB_PATH", None)
        try:
            os.unlink(self._db_pfad)
        except OSError:
            pass

    def _spalten(self, conn) -> set:
        return {r[1] for r in conn.execute(
            "PRAGMA table_info(intake_dokumente)"
        ).fetchall()}

    def test_neue_spalten_vorhanden(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            spalten = self._spalten(conn)
        self.assertIn("versuch_zaehler", spalten,
                      f"versuch_zaehler fehlt; vorhandene: {sorted(spalten)}")
        self.assertIn("naechster_versuch", spalten)
        self.assertIn("fehler_detail", spalten)
        self.assertIn("worker_lease", spalten)

    def test_versuch_zaehler_default_null_gleich_0(self):
        from backend.db.database import get_connection
        # Test-INSERT: versuch_zaehler ist NOT NULL DEFAULT 0
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO intake_dokumente (sha256) VALUES (?)",
                ("deadbeef" * 8,),
            )
            row = conn.execute(
                "SELECT versuch_zaehler, naechster_versuch, fehler_detail, worker_lease "
                "FROM intake_dokumente WHERE sha256=?",
                ("deadbeef" * 8,),
            ).fetchone()
        self.assertEqual(row["versuch_zaehler"], 0)
        self.assertIsNone(row["naechster_versuch"])
        self.assertIsNone(row["fehler_detail"])
        self.assertIsNone(row["worker_lease"])

    def test_migration_idempotent(self):
        # Ein zweiter Aufruf von run_migrations() darf nicht werfen und
        # nichts an den vorhandenen Spalten aendern.
        from backend.db.schema_manager import run_migrations
        run_migrations()
        run_migrations()

    def test_schema_version_48(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT MAX(version) AS v FROM schema_version"
            ).fetchone()
        self.assertGreaterEqual(row["v"], 48)


if __name__ == "__main__":
    unittest.main()
