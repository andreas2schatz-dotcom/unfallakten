# backend/tests/test_migration_60.py
import importlib
import os
import sys
import tempfile
import unittest

_tmp = tempfile.mkdtemp(prefix="mig60_")
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


class TestMigration60(unittest.TestCase):
    def test_spalte_vorhanden_nach_init(self):
        sm, db_mod = _fresh_db("vorhanden")
        with db_mod.get_connection() as conn:
            cols = {r[1] for r in conn.execute(
                "PRAGMA table_info(personenschaden)").fetchall()}
            version = conn.execute(
                "SELECT MAX(version) FROM schema_version").fetchone()[0]
        self.assertIn("krankenhaus_aufenthalt", cols)
        self.assertGreaterEqual(version, 60)

    def test_migration_zieht_fehlende_spalte_nach(self):
        """Simuliert die gedriftete Live-DB: Spalte fehlt -> Migration ergaenzt
        sie (Kern des Personenschaden-Bugs)."""
        sm, db_mod = _fresh_db("drift")
        with db_mod.get_connection() as conn:
            conn.execute(
                "ALTER TABLE personenschaden DROP COLUMN krankenhaus_aufenthalt")
            conn.commit()
            vorher = {r[1] for r in conn.execute(
                "PRAGMA table_info(personenschaden)").fetchall()}
            self.assertNotIn("krankenhaus_aufenthalt", vorher)

            sm._run_migration_60(conn)

            nachher = {r[1] for r in conn.execute(
                "PRAGMA table_info(personenschaden)").fetchall()}
        self.assertIn("krankenhaus_aufenthalt", nachher)

    def test_idempotent(self):
        sm, db_mod = _fresh_db("idem")
        with db_mod.get_connection() as conn:
            sm._run_migration_60(conn)  # zweiter Lauf darf nicht werfen
            cols = {r[1] for r in conn.execute(
                "PRAGMA table_info(personenschaden)").fetchall()}
        self.assertIn("krankenhaus_aufenthalt", cols)


if __name__ == "__main__":
    unittest.main()
