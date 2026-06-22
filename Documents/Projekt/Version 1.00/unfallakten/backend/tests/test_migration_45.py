"""
Tests für Migration 45 und regulierung_status-Logik.
"""
import os
import sys
import unittest
import tempfile

_tmp_dir = tempfile.mkdtemp()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _ns(test_id: str):
    db_path = os.path.join(_tmp_dir, f"{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path

    import importlib
    import backend.db.database as db_mod
    import backend.db.schema_manager as sm_mod
    import backend.models.akte as akte_mod

    for m in (db_mod, sm_mod, akte_mod):
        importlib.reload(m)

    sm_mod.create_schema()
    sm_mod.run_migrations()

    class NS:
        get_connection    = staticmethod(db_mod.get_connection)
        create_schema     = staticmethod(sm_mod.create_schema)
        aktualisiere_akte = staticmethod(akte_mod.aktualisiere_akte)
        hole_akte_by_id   = staticmethod(akte_mod.hole_akte_by_id)

        @staticmethod
        def neue_akte(az="99/99"):
            with db_mod.get_connection() as conn:
                conn.execute(
                    "INSERT INTO unfallakte (az, unfalldatum, status) VALUES (?, '', 'offen')",
                    (az,)
                )
            return akte_mod.hole_akte_by_id(az)

    return NS()


class TestMigration45(unittest.TestCase):

    def test_spalte_existiert_nach_migration(self):
        """regulierung_status-Spalte muss nach create_schema vorhanden sein."""
        ns = _ns("m45_spalte")
        with ns.get_connection() as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(unfallakte)").fetchall()}
        self.assertIn("regulierung_status", cols)

    def test_default_wert_ist_offen(self):
        """Neue Akte hat regulierung_status='offen' als Default."""
        ns = _ns("m45_default")
        akte = ns.neue_akte("11/11")
        self.assertEqual(akte.regulierung_status, "offen")

    def test_aktualisiere_abgelehnt_und_teilhaftung(self):
        """aktualisiere_akte speichert abgelehnt und teilhaftung korrekt."""
        ns = _ns("m45_update")
        ns.neue_akte("22/22")
        res = ns.aktualisiere_akte("22/22", regulierung_status="abgelehnt", haftungsquote=0.0)
        self.assertEqual(res.regulierung_status, "abgelehnt")
        self.assertEqual(res.haftungsquote, 0.0)
        res2 = ns.aktualisiere_akte("22/22", regulierung_status="teilhaftung", haftungsquote=70.0)
        self.assertEqual(res2.regulierung_status, "teilhaftung")
        self.assertEqual(res2.haftungsquote, 70.0)

    def test_ungueltige_status_wirft_valueerror(self):
        """aktualisiere_akte wirft ValueError bei ungültigem regulierung_status."""
        ns = _ns("m45_invalid")
        ns.neue_akte("33/33")
        with self.assertRaises(ValueError):
            ns.aktualisiere_akte("33/33", regulierung_status="ungueltig")


if __name__ == "__main__":
    unittest.main()
