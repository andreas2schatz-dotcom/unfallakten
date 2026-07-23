import os
import sqlite3
import tempfile
import unittest


class TestMigration64(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad
        from backend.db.schema_manager import init_db
        init_db()
        self.conn = sqlite3.connect(self._db_pfad)
        self.conn.row_factory = sqlite3.Row

    def tearDown(self):
        self.conn.close()
        os.unlink(self._db_pfad)

    def _spalten(self, tabelle):
        return {r["name"] for r in self.conn.execute(f"PRAGMA table_info({tabelle})")}

    def test_kuerzungsarten_neue_spalten(self):
        self.assertIn("typ_code", self._spalten("kuerzungsarten"))
        self.assertIn("verifiziert_am", self._spalten("kuerzungsarten"))

    def test_bestand_hat_typ_codes_und_stempel(self):
        rows = self.conn.execute(
            "SELECT id, typ_code, verifiziert_am FROM kuerzungsarten WHERE id <= 19"
        ).fetchall()
        self.assertEqual(len(rows), 19)
        erwartet = {1: "A04", 2: "C01", 3: "A01", 4: "A02", 5: "A03", 6: "B01",
                    7: "A05c", 8: "A05b", 9: "A05a", 10: "A06", 11: "A09",
                    12: "E05", 13: "E05b", 14: "E05c", 15: "E06", 16: "D01",
                    17: "E01", 18: "D04", 19: "F03"}
        for r in rows:
            self.assertEqual(r["typ_code"], erwartet[r["id"]])
            self.assertEqual(r["verifiziert_am"], "handgeprüft RA Schatz, Juli 2026")

    def test_neue_typen_vorhanden(self):
        codes = {r["typ_code"] for r in self.conn.execute(
            "SELECT typ_code FROM kuerzungsarten WHERE id > 19")}
        self.assertEqual(codes, {"A07", "A10", "A11", "A04b", "B01b", "C01b",
                                 "D01b", "E01b", "E01c", "E02", "E03", "E06b", "F01"})

    def test_typ_code_unique(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO kuerzungsarten (bezeichnung, kategorie, typ_code) "
                "VALUES ('Dublette', 'fahrzeugschaden', 'A04')")

    def test_pruefdienstleister_tabelle_und_seeds(self):
        namen = {r["name"] for r in self.conn.execute(
            "SELECT name FROM pruefdienstleister")}
        self.assertTrue({"ControlExpert", "DEKRA", "Eucon", "SSH",
                         "Audatex", "GTÜ", "DA Direkt"} <= namen)

    def test_neue_fk_und_pflichtfeld_spalten(self):
        self.assertIn("pruefdienstleister_id", self._spalten("pruefberichte"))
        self.assertIn("pruefdienstleister_id", self._spalten("abrechnungsschreiben"))
        self.assertIn("begruendung_roh", self._spalten("ereignis_positionen"))
        self.assertIn("typ_quelle", self._spalten("regulierung_positionen"))

    def test_schema_version_64(self):
        v = self.conn.execute("SELECT MAX(version) v FROM schema_version").fetchone()["v"]
        self.assertGreaterEqual(v, 64)


if __name__ == "__main__":
    unittest.main()
