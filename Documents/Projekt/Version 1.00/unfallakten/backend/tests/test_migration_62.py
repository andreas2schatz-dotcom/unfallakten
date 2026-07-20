import importlib
import os
import sys
import tempfile
import unittest

_tmp = tempfile.mkdtemp(prefix="mig62_")
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


class TestMigration62(unittest.TestCase):
    def test_tabelle_vorhanden_nach_init(self):
        sm, db_mod = _fresh_db("vorhanden")
        with db_mod.get_connection() as conn:
            spalten = {r[1] for r in conn.execute(
                "PRAGMA table_info(firmen_vertreter)").fetchall()}
            version = conn.execute(
                "SELECT MAX(version) FROM schema_version").fetchone()[0]
        self.assertEqual(
            spalten,
            {"firma_norm", "firma_anzeige", "vertreter_name",
             "vertreter_funktion", "aktualisiert_am"})
        self.assertGreaterEqual(version, 62)

    def test_firma_norm_ist_primary_key(self):
        sm, db_mod = _fresh_db("pk")
        import sqlite3
        with db_mod.get_connection() as conn:
            conn.execute(
                "INSERT INTO firmen_vertreter "
                "(firma_norm, firma_anzeige, vertreter_name) "
                "VALUES ('adac autoversicherung ag', 'ADAC Autoversicherung AG', 'X')")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO firmen_vertreter "
                    "(firma_norm, firma_anzeige, vertreter_name) "
                    "VALUES ('adac autoversicherung ag', 'ADAC', 'Y')")

    def test_migration_zieht_fehlende_tabelle_nach(self):
        sm, db_mod = _fresh_db("nachziehen")
        with db_mod.get_connection() as conn:
            conn.execute("DROP TABLE firmen_vertreter")
            conn.commit()
            sm._run_migration_62(conn)
            spalten = {r[1] for r in conn.execute(
                "PRAGMA table_info(firmen_vertreter)").fetchall()}
        self.assertIn("vertreter_name", spalten)


if __name__ == "__main__":
    unittest.main()
