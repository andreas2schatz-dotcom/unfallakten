"""
Tests für die Sachbearbeiter-Verwaltung (Migration 68, Modul, Endpunkte).
"""

import importlib
import os
import tempfile
import unittest

_tmp_dir = tempfile.mkdtemp()


def _setup(test_id: str):
    """Frische DB + Flask-App (Muster: test_dashboard_uebersicht._setup)."""
    db_path = os.path.join(_tmp_dir, f"sb_{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    os.environ["JWT_SECRET_KEY"] = "test-secret-key-minimum-32-characters!!"
    os.environ["FLASK_SECRET_KEY"] = "test-flask-secret-key-minimum-32-characters!!"

    import backend.db.database as db_mod
    import backend.db.schema_manager as schema_mod
    import backend.ramicro.sachbearbeiter as sb_mod
    import backend.routers.einstellungen_routes as eins_mod
    import backend.app as app_mod

    for m in (db_mod, schema_mod, sb_mod, eins_mod, app_mod):
        importlib.reload(m)

    app = app_mod.erstelle_app({"TESTING": True})
    return app.test_client()


class TestMigration68(unittest.TestCase):

    def setUp(self):
        self.client = _setup(self._testMethodName)

    def test_tabelle_und_elf_startzeilen(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            rows = [dict(r) for r in conn.execute(
                "SELECT kuerzel, name, titel, rolle, aktiv, dashboard_vorauswahl, "
                "kalender_name FROM sachbearbeiter ORDER BY sortierung"
            ).fetchall()]

        self.assertEqual(len(rows), 11)
        self.assertEqual([r["kuerzel"] for r in rows][:5], ["AS", "PK", "CO", "MM", "AH"])

        nach_kuerzel = {r["kuerzel"]: r for r in rows}
        self.assertEqual(nach_kuerzel["CS"]["name"], "Carina Salvagnin")
        self.assertEqual(nach_kuerzel["JH"]["name"], "Jochen Hofmann")
        self.assertEqual(nach_kuerzel["JH"]["aktiv"], 0)
        self.assertEqual(nach_kuerzel["TB"]["rolle"], "refa")
        self.assertEqual(nach_kuerzel["AS"]["kalender_name"], "RA.Schatz")
        vorausgewaehlt = {r["kuerzel"] for r in rows if r["dashboard_vorauswahl"]}
        self.assertEqual(vorausgewaehlt, {"AS", "PK", "CO", "MM", "AH"})

    def test_zweiter_lauf_aendert_nichts(self):
        from backend.db.database import get_connection
        from backend.db.schema_manager import _run_migration_68
        with get_connection() as conn:
            conn.execute("UPDATE sachbearbeiter SET name = 'Geändert' WHERE kuerzel = 'AS'")
            conn.commit()
            _run_migration_68(conn)
            name = conn.execute(
                "SELECT name FROM sachbearbeiter WHERE kuerzel = 'AS'"
            ).fetchone()["name"]
            anzahl = conn.execute("SELECT COUNT(*) AS n FROM sachbearbeiter").fetchone()["n"]
            versionen = conn.execute(
                "SELECT COUNT(*) AS n FROM schema_version WHERE version = 68"
            ).fetchone()["n"]
        self.assertEqual(name, "Geändert")
        self.assertEqual(anzahl, 11)
        self.assertEqual(versionen, 1)

    def test_kalender_name_ist_eindeutig(self):
        import sqlite3
        from backend.db.database import get_connection
        with get_connection() as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO sachbearbeiter (kuerzel, name, kalender_name) "
                    "VALUES ('ZZ', 'Doppelkalender', 'RA.Schatz')"
                )


if __name__ == "__main__":
    unittest.main()
