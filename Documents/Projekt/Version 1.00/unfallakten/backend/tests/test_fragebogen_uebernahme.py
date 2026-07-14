"""Service fragebogen_uebernahme -- Vorschau + Schreiben (Task 2-4)."""
import importlib
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class _ServiceBasis(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="frbsvc_")
        os.environ["DB_PATH"] = os.path.join(self._tmp, "unfallakten.db")
        os.environ["UPLOAD_DIR"] = os.path.join(self._tmp, "uploads")

        import backend.db.database as db_mod
        import backend.models.akte as akte_mod
        import backend.app as app_mod
        for m in (db_mod, akte_mod, app_mod):
            importlib.reload(m)
        app_mod.erstelle_app({"TESTING": True})  # legt Schema an

        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute("INSERT INTO unfallakte (az, status) VALUES ('44/22', 'offen')")

    def tearDown(self):
        import shutil
        for var in ("DB_PATH", "UPLOAD_DIR"):
            os.environ.pop(var, None)
        shutil.rmtree(self._tmp, ignore_errors=True)


class TestErkennung(_ServiceBasis):
    def test_parse_erkennt_unfallbogen(self):
        from backend.services.fragebogen_uebernahme import parse_fragebogen_payload
        roh = '{"meta":{"formular":"unfallbogen","version":"2.1"},"mandant":{"name":"X"}}'
        parsed = parse_fragebogen_payload(roh)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["mandant"]["name"], "X")

    def test_parse_lehnt_fremdes_json_ab(self):
        from backend.services.fragebogen_uebernahme import parse_fragebogen_payload
        self.assertIsNone(parse_fragebogen_payload('{"meta":{"formular":"rechnung"}}'))
        self.assertIsNone(parse_fragebogen_payload(None))


class TestVorschauBeteiligte(_ServiceBasis):
    def test_mandant_leer_und_konflikt(self):
        from backend.db.database import get_connection
        from backend.services.fragebogen_uebernahme import (
            _geparst_mandant, _akte_mandant, _vorschau_felder)
        with get_connection() as conn:
            conn.execute("INSERT INTO beteiligte (akte_id, rolle, name, ort) "
                         "VALUES ('44/22', 'mandant', 'Riccio', 'Offenbach')")
            akte = _akte_mandant(conn, "44/22")
        felder = _vorschau_felder(
            _geparst_mandant({"name": "Riccio", "ort": "Neu-Isenburg",
                              "telefon": "069 1"}),
            akte)
        nach_feld = {f["feld"]: f for f in felder}
        self.assertTrue(nach_feld["telefon"]["ist_leer"])
        self.assertFalse(nach_feld["telefon"]["konflikt"])
        self.assertFalse(nach_feld["name"]["ist_leer"])
        self.assertFalse(nach_feld["name"]["konflikt"])   # gleich
        self.assertTrue(nach_feld["ort"]["konflikt"])     # Offenbach != Neu-Isenburg
        self.assertNotIn("iban", nach_feld)               # kein geparster Wert -> nicht gelistet

    def test_gegner_ohne_akte_zeile_alles_leer(self):
        from backend.db.database import get_connection
        from backend.services.fragebogen_uebernahme import (
            _geparst_gegner, _akte_gegner, _vorschau_felder)
        with get_connection() as conn:
            akte = _akte_gegner(conn, "44/22")
        felder = _vorschau_felder(
            _geparst_gegner({"fahrer": "K", "versicherung": {"name": "HUK"}}), akte)
        self.assertTrue(all(f["ist_leer"] for f in felder))


class TestSchreibeBeteiligte(_ServiceBasis):
    def test_insert_und_fill_empty(self):
        from backend.db.database import get_connection
        from backend.services.fragebogen_uebernahme import _schreibe_beteiligte
        with get_connection() as conn:
            _schreibe_beteiligte(conn, "44/22", "mandant",
                                 {"name": "Riccio", "telefon": "069 1"})
            row = conn.execute("SELECT name, telefon FROM beteiligte "
                               "WHERE akte_id='44/22' AND rolle='mandant'").fetchone()
        self.assertEqual(row["name"], "Riccio")
        self.assertEqual(row["telefon"], "069 1")

    def test_update_ueberschreibt_gesetzte_spalte(self):
        from backend.db.database import get_connection
        from backend.services.fragebogen_uebernahme import _schreibe_beteiligte
        with get_connection() as conn:
            conn.execute("INSERT INTO beteiligte (akte_id, rolle, name, ort) "
                         "VALUES ('44/22', 'mandant', 'Riccio', 'Offenbach')")
            _schreibe_beteiligte(conn, "44/22", "mandant", {"ort": "Neu-Isenburg"})
            row = conn.execute("SELECT ort FROM beteiligte "
                               "WHERE akte_id='44/22' AND rolle='mandant'").fetchone()
        self.assertEqual(row["ort"], "Neu-Isenburg")

    def test_insert_ohne_name_in_aenderungen(self):
        from backend.db.database import get_connection
        from backend.services.fragebogen_uebernahme import _schreibe_beteiligte
        with get_connection() as conn:
            _schreibe_beteiligte(conn, "44/22", "gegner", {"versicherung": "HUK"})
            row = conn.execute("SELECT name, versicherung FROM beteiligte "
                               "WHERE akte_id='44/22' AND rolle='gegner'").fetchone()
        self.assertEqual(row["versicherung"], "HUK")
        self.assertEqual(row["name"], "")


class TestVorschauUnfall(_ServiceBasis):
    def test_schilderung_mit_uhrzeit_prefix(self):
        from backend.db.database import get_connection
        from backend.services.fragebogen_uebernahme import (
            _geparst_unfall, _akte_unfall, _vorschau_felder)
        with get_connection() as conn:
            akte = _akte_unfall(conn, "44/22")
        felder = _vorschau_felder(
            _geparst_unfall({"datum": "2026-03-12", "ort": "OF",
                             "zeit": "14:20", "schilderung": "Auffahrunfall"}), akte)
        nach = {f["feld"]: f for f in felder}
        self.assertEqual(nach["schilderung"]["geparst"], "[Uhrzeit: 14:20] Auffahrunfall")
        self.assertTrue(nach["unfalldatum"]["ist_leer"])

    def test_schreibe_unfall_beide_tabellen(self):
        from backend.db.database import get_connection
        from backend.services.fragebogen_uebernahme import _schreibe_unfall
        with get_connection() as conn:
            _schreibe_unfall(conn, "44/22",
                             {"unfalldatum": "2026-03-12", "schilderung": "X"})
            a = conn.execute("SELECT unfalldatum FROM unfallakte WHERE az='44/22'").fetchone()
            d = conn.execute("SELECT schilderung FROM unfalldetails WHERE akte_id='44/22'").fetchone()
        self.assertEqual(a["unfalldatum"], "2026-03-12")
        self.assertEqual(d["schilderung"], "X")


class TestVorschauPersonenschaden(_ServiceBasis):
    def test_schreibe_setzt_abgeleitete_flags(self):
        from backend.db.database import get_connection
        from backend.services.fragebogen_uebernahme import _schreibe_personenschaden
        with get_connection() as conn:
            _schreibe_personenschaden(conn, "44/22",
                                      {"krankenhaus_name": "Klinikum", "krank_von": "2026-03-13"})
            row = conn.execute(
                "SELECT krankenhaus_name, krankenhaus_aufenthalt, krankgeschrieben "
                "FROM personenschaden WHERE akte_id='44/22'").fetchone()
        self.assertEqual(row["krankenhaus_name"], "Klinikum")
        self.assertEqual(row["krankenhaus_aufenthalt"], 1)
        self.assertEqual(row["krankgeschrieben"], 1)


if __name__ == "__main__":
    unittest.main()
