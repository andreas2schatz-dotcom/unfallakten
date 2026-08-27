"""
Guard-Tests fuer den Dispatch-Mechanismus in run_migrations().

Sichert die Reloader-Falle ab, die bereits die Migrationen 54, 55, 58, 60,
66 und 71 getroffen hat: ein Kommentar-Platzhalter im MIGRATIONS-Dict ohne
zugehoerigen if/elif-Zweig darf nicht mehr stillschweigend als erledigt
gestempelt werden, sondern muss run_migrations() mit einer klaren
Fehlermeldung abbrechen lassen.
"""
import inspect
import os
import re
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

_tmp_dir = tempfile.mkdtemp(prefix="migdispatch_")


def _frische_module(test_id: str):
    db_path = os.path.join(_tmp_dir, f"{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path

    import importlib
    import backend.db.database as db_mod
    import backend.db.schema_manager as sm_mod

    for m in (db_mod, sm_mod):
        importlib.reload(m)

    return db_mod, sm_mod


class TestAlleKommentarPlatzhalterHabenEinenZweig(unittest.TestCase):
    """
    Die eigentliche Zusicherung aus der Auszaehlung: jeder einzeilige
    Kommentar-Platzhalter im MIGRATIONS-Dict hat einen ausfuehrenden
    if/elif-Zweig in run_migrations(). Faellt beim naechsten Mal auf, wenn
    jemand einen MIGRATIONS-Eintrag hinzufuegt und den Zweig vergisst.
    """

    def test_jeder_platzhalter_hat_einen_dispatch_zweig(self):
        from backend.db.schema_manager import (
            MIGRATIONS, _ist_reiner_kommentar_platzhalter, run_migrations,
        )

        quelltext = inspect.getsource(run_migrations)
        dispatchte_versionen = {
            int(n) for n in re.findall(
                r"^\s*(?:if|elif) version == (\d+):\s*$", quelltext, re.MULTILINE
            )
        }
        self.assertGreater(len(dispatchte_versionen), 0)

        platzhalter_ohne_zweig = [
            v for v, sql in MIGRATIONS.items()
            if _ist_reiner_kommentar_platzhalter(sql)
            and v not in dispatchte_versionen
        ]
        self.assertEqual(
            platzhalter_ohne_zweig, [],
            f"Kommentar-Platzhalter ohne Dispatch-Zweig gefunden: "
            f"{platzhalter_ohne_zweig} -- das ist die Reloader-Falle.",
        )

    def test_echtes_sql_wird_nicht_als_platzhalter_erkannt(self):
        from backend.db.schema_manager import (
            MIGRATIONS, _ist_reiner_kommentar_platzhalter,
        )
        # Bekannte echte SQL-Migrationen (mehrzeilig, kein reiner Kommentar).
        for v in (2, 3, 7, 37):
            with self.subTest(version=v):
                self.assertFalse(_ist_reiner_kommentar_platzhalter(MIGRATIONS[v]))

    def test_bekannter_platzhalter_wird_erkannt(self):
        from backend.db.schema_manager import _ist_reiner_kommentar_platzhalter
        self.assertTrue(
            _ist_reiner_kommentar_platzhalter("-- migration_54_textquelle_email_text")
        )


class TestBestandsstartOhneAenderung(unittest.TestCase):
    def test_datenbank_auf_aktuellem_stand_startet_unveraendert_durch(self):
        db_mod, sm_mod = _frische_module("bestand_unveraendert")
        sm_mod.create_schema()
        sm_mod.run_migrations()

        with db_mod.get_connection() as conn:
            vor_version = sm_mod.get_schema_version(conn)
            vor_anzahl = conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]

        # Zweiter Lauf auf bereits vollstaendig migrierter Datenbank: pending
        # ist leer, der Dispatch-Loop wird gar nicht erst betreten.
        sm_mod.run_migrations()

        with db_mod.get_connection() as conn:
            nach_version = sm_mod.get_schema_version(conn)
            nach_anzahl = conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]

        self.assertEqual(vor_version, nach_version)
        self.assertEqual(vor_anzahl, nach_anzahl)


class TestPlatzhalterOhneZweigBrichtAb(unittest.TestCase):
    def test_platzhalter_ohne_zweig_bricht_ab_und_stempelt_nicht(self):
        db_mod, sm_mod = _frische_module("platzhalter_ohne_zweig")
        sm_mod.create_schema()
        sm_mod.run_migrations()

        with mock.patch.dict(
            sm_mod.MIGRATIONS,
            {9999: "-- fake_migration_ohne_dispatch_zweig"},
        ):
            with self.assertRaises(RuntimeError) as ctx:
                sm_mod.run_migrations()
            self.assertIn("9999", str(ctx.exception))

        with db_mod.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM schema_version WHERE version=9999"
            ).fetchone()
        self.assertIsNone(
            row, "Die abgebrochene Migration darf nicht gestempelt werden."
        )


if __name__ == "__main__":
    unittest.main()
