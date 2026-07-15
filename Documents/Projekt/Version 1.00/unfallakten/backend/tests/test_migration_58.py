# backend/tests/test_migration_58.py
import importlib
import os
import sys
import tempfile
import unittest

_tmp = tempfile.mkdtemp(prefix="mig58_")
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


class TestMigration58(unittest.TestCase):
    def test_spalte_vorhanden(self):
        sm, db_mod = _fresh_db("vorhanden")
        with db_mod.get_connection() as conn:
            cols = {r[1] for r in conn.execute(
                "PRAGMA table_info(intake_dokumente)").fetchall()}
            version = conn.execute(
                "SELECT MAX(version) FROM schema_version").fetchone()[0]
        self.assertIn("aufgeteilt_aus_id", cols)
        self.assertGreaterEqual(version, 58)

    def test_idempotent(self):
        sm, db_mod = _fresh_db("idem")
        with db_mod.get_connection() as conn:
            sm._run_migration_58(conn)  # zweiter Lauf darf nicht werfen
            cols = {r[1] for r in conn.execute(
                "PRAGMA table_info(intake_dokumente)").fetchall()}
        self.assertIn("aufgeteilt_aus_id", cols)


if __name__ == "__main__":
    unittest.main()
