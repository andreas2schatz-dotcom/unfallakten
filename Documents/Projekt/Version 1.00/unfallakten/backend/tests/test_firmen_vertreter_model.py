import importlib
import os
import sys
import tempfile
import unittest

_tmp = tempfile.mkdtemp(prefix="fvmodel_")
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
    return db_mod


class TestFirmaNorm(unittest.TestCase):
    def test_lower_und_whitespace_kollaps(self):
        from backend.models.firmen_vertreter import firma_norm
        self.assertEqual(
            firma_norm("  ADAC   Autoversicherung  AG "),
            "adac autoversicherung ag")

    def test_leer_und_none(self):
        from backend.models.firmen_vertreter import firma_norm
        self.assertEqual(firma_norm(""), "")
        self.assertEqual(firma_norm(None), "")

    def test_rechtsform_bleibt_erhalten(self):
        from backend.models.firmen_vertreter import firma_norm
        self.assertNotEqual(firma_norm("Muster GmbH"), firma_norm("Muster AG"))


class TestUpsertUndLookup(unittest.TestCase):
    def test_roundtrip(self):
        db_mod = _fresh_db("roundtrip")
        from backend.models.firmen_vertreter import (
            upsert_firmen_vertreter, hole_firmen_vertreter)
        with db_mod.get_connection() as conn:
            ok = upsert_firmen_vertreter(
                conn, "ADAC Autoversicherung AG", "Stefan Daehne", "Vorstand")
            self.assertTrue(ok)
            treffer = hole_firmen_vertreter(conn, "  adac   autoversicherung ag ")
        self.assertEqual(
            treffer,
            {"vertreter_name": "Stefan Daehne", "vertreter_funktion": "Vorstand"})

    def test_upsert_aktualisiert_bestehenden(self):
        db_mod = _fresh_db("update")
        from backend.models.firmen_vertreter import (
            upsert_firmen_vertreter, hole_firmen_vertreter)
        with db_mod.get_connection() as conn:
            upsert_firmen_vertreter(conn, "Muster AG", "Alt Name", "Vorstand")
            upsert_firmen_vertreter(conn, "Muster AG", "Neu Name", "Vorstand")
            treffer = hole_firmen_vertreter(conn, "Muster AG")
            anzahl = conn.execute(
                "SELECT COUNT(*) FROM firmen_vertreter").fetchone()[0]
        self.assertEqual(treffer["vertreter_name"], "Neu Name")
        self.assertEqual(anzahl, 1)

    def test_leerer_name_wird_abgelehnt(self):
        db_mod = _fresh_db("leername")
        from backend.models.firmen_vertreter import (
            upsert_firmen_vertreter, hole_firmen_vertreter)
        with db_mod.get_connection() as conn:
            self.assertFalse(upsert_firmen_vertreter(conn, "Muster AG", "  "))
            self.assertIsNone(hole_firmen_vertreter(conn, "Muster AG"))

    def test_lookup_ohne_treffer(self):
        db_mod = _fresh_db("kein_treffer")
        from backend.models.firmen_vertreter import hole_firmen_vertreter
        with db_mod.get_connection() as conn:
            self.assertIsNone(hole_firmen_vertreter(conn, "Unbekannt GmbH"))
            self.assertIsNone(hole_firmen_vertreter(conn, ""))


if __name__ == "__main__":
    unittest.main()
