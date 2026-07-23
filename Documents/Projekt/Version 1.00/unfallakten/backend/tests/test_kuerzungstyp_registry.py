import unittest


class TestKuerzungstypRegistry(unittest.TestCase):
    def test_laedt_32_typen(self):
        from backend.services.kuerzungstyp_registry import lade_kuerzungstypen
        reg = lade_kuerzungstypen(reload=True)
        self.assertEqual(len(reg.typen), 32)
        self.assertIn("A04", reg.typen)
        self.assertIn("E01b", reg.typen)

    def test_pflichtfelder_und_kategorien(self):
        from backend.services.kuerzungstyp_registry import (
            lade_kuerzungstypen, KATEGORIEN_AF)
        reg = lade_kuerzungstypen(reload=True)
        for code, typ in reg.typen.items():
            self.assertEqual(code, typ["typ_code"])
            self.assertIn(typ["kategorie_code"], KATEGORIEN_AF)
            self.assertTrue(typ["name"])
            self.assertTrue(typ["verifiziert_am"])
            self.assertIsInstance(typ["keywords"], list)

    def test_fail_loud_bei_fehlendem_verzeichnis(self):
        from backend.services.kuerzungstyp_registry import lade_kuerzungstypen
        with self.assertRaises(RuntimeError):
            lade_kuerzungstypen("/nicht/vorhanden", reload=True)

    def test_konsistenz_registry_gegen_migration_seeds(self):
        from backend.services.kuerzungstyp_registry import lade_kuerzungstypen
        from backend.db.schema_manager import _TYP_CODES_BESTAND, _KUERZUNGSARTEN_NEU
        reg = lade_kuerzungstypen(reload=True)
        erwartet = set(_TYP_CODES_BESTAND.values()) | {c for _, _, c, _ in _KUERZUNGSARTEN_NEU}
        self.assertEqual(set(reg.typen), erwartet)

    def test_baustein_pfad_exaktes_false_set(self):
        from backend.services.kuerzungstyp_registry import lade_kuerzungstypen
        reg = lade_kuerzungstypen(reload=True)
        ohne_baustein = {c for c, t in reg.typen.items() if not t["baustein_pfad"]}
        self.assertEqual(ohne_baustein, {"A07", "A09", "D04", "E05c", "F03"})
