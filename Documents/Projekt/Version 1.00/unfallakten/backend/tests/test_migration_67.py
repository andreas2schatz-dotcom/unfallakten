"""Tests für Migration 67 (abschluss_status)."""
import os
import sys
import tempfile
import unittest

_tmp_dir = tempfile.mkdtemp(prefix="mig67_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _ns(test_id: str):
    db_path = os.path.join(_tmp_dir, f"{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path

    import importlib
    import backend.db.database as db_mod
    import backend.db.schema_manager as sm_mod
    for m in (db_mod, sm_mod):
        importlib.reload(m)

    sm_mod.create_schema()
    sm_mod.run_migrations()

    class NS:
        get_connection = staticmethod(db_mod.get_connection)
    return NS()


class TestMigration67(unittest.TestCase):

    def test_tabelle_und_spalten_existieren(self):
        ns = _ns("m67_spalten")
        with ns.get_connection() as conn:
            cols = {r[1] for r in conn.execute(
                "PRAGMA table_info(abschluss_status)").fetchall()}
        self.assertEqual(cols, {
            "akte_az", "schluss_typ", "schluss_text", "verjaehrung_datum",
            "naechste_schritte_text", "kuratiert_am", "kuratiert_von"})

    def test_default_schluss_typ_offen(self):
        ns = _ns("m67_default")
        with ns.get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('67/26', '', 'offen')")
            conn.execute(
                "INSERT INTO abschluss_status (akte_az) VALUES ('67/26')")
            row = conn.execute(
                "SELECT schluss_typ FROM abschluss_status "
                "WHERE akte_az = '67/26'").fetchone()
        self.assertEqual(row[0], "offen")

    def test_check_constraint_lehnt_unbekannten_typ_ab(self):
        import sqlite3
        ns = _ns("m67_check")
        with ns.get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('68/26', '', 'offen')")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO abschluss_status (akte_az, schluss_typ) "
                    "VALUES ('68/26', 'quatsch')")

    def test_migration_67_idempotent_und_versioniert(self):
        ns = _ns("m67_idem")
        from backend.db.schema_manager import _run_migration_67
        with ns.get_connection() as conn:
            _run_migration_67(conn)
            row = conn.execute(
                "SELECT version FROM schema_version WHERE version = 67"
            ).fetchone()
        self.assertIsNotNone(row)


if __name__ == "__main__":
    unittest.main()
