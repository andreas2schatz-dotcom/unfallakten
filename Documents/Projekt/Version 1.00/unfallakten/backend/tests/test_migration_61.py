import importlib
import os
import sys
import tempfile
import unittest

_tmp = tempfile.mkdtemp(prefix="mig61_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _fresh_db(name):
    db_path = os.path.join(_tmp, f"{name}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    import backend.db.database as db_mod
    import backend.db.schema_manager as sm
    importlib.reload(db_mod)
    importlib.reload(sm)
    sm.init_db()
    return sm, db_mod


class TestMigration61(unittest.TestCase):
    def test_tabelle_vorhanden_nach_init(self):
        sm, db_mod = _fresh_db("vorhanden")
        with db_mod.get_connection() as conn:
            spalten = {r[1] for r in conn.execute(
                "PRAGMA table_info(klage_entwurf)").fetchall()}
            version = conn.execute(
                "SELECT MAX(version) FROM schema_version").fetchone()[0]
        self.assertEqual(
            spalten,
            {"id", "akte_id", "entwurf_json", "format_version", "gespeichert_am"})
        self.assertGreaterEqual(version, 61)

    def test_akte_id_unique(self):
        sm, db_mod = _fresh_db("unique")
        import sqlite3
        with db_mod.get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('61/26', '2026-02-01', 'offen')")
            conn.execute(
                "INSERT INTO klage_entwurf (akte_id, entwurf_json, format_version) "
                "VALUES ('61/26', '{}', 1)")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO klage_entwurf (akte_id, entwurf_json, format_version) "
                    "VALUES ('61/26', '{}', 1)")

    def test_migration_zieht_fehlende_tabelle_nach(self):
        sm, db_mod = _fresh_db("nachziehen")
        with db_mod.get_connection() as conn:
            conn.execute("DROP TABLE klage_entwurf")
            conn.commit()
            sm._run_migration_61(conn)
            spalten = {r[1] for r in conn.execute(
                "PRAGMA table_info(klage_entwurf)").fetchall()}
        self.assertIn("entwurf_json", spalten)

    def test_idempotent(self):
        sm, db_mod = _fresh_db("idem")
        with db_mod.get_connection() as conn:
            sm._run_migration_61(conn)
            spalten = {r[1] for r in conn.execute(
                "PRAGMA table_info(klage_entwurf)").fetchall()}
        self.assertIn("entwurf_json", spalten)


if __name__ == "__main__":
    unittest.main()
