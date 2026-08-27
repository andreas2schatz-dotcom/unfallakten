"""Akten-Matching mit den Signalen aus einem Unfallbogen.

RA-MICRO ist gemockt -- keine Netzwerkzugriffe.
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _setup_db(name):
    fd, pfad = tempfile.mkstemp(prefix=f"fbmatch_{name}_", suffix=".sqlite")
    os.close(fd)
    import backend.db.database as _db
    _db.DB_PATH = pfad
    os.environ["DB_PATH"] = pfad
    from backend.db.schema_manager import init_db
    init_db()
    from backend.db.database import get_connection
    with get_connection() as conn:
        conn.execute("INSERT INTO unfallakte (az, unfalldatum, status) "
                      "VALUES ('742/26', '2026-08-03', 'offen')")
        conn.execute("INSERT INTO unfallakte (az, unfalldatum, status) "
                      "VALUES ('900/26', '2026-08-03', 'offen')")
        conn.execute(
            "INSERT INTO beteiligte (akte_id, rolle, name, email, "
            "kfz_kennzeichen) VALUES "
            "('742/26', 'mandant', 'Golovin', 'paulgolovin@web.de', "
            "'WÜ PG 777')")
        conn.execute(
            "INSERT INTO beteiligte (akte_id, rolle, name, kfz_kennzeichen) "
            "VALUES ('742/26', 'gegner', 'Brochner', 'MTK-DB 801')")
        conn.execute(
            "INSERT INTO beteiligte (akte_id, rolle, name) "
            "VALUES ('900/26', 'mandant', 'Schmitt')")
    return pfad


class TestFragebogenMatching(unittest.TestCase):
    def setUp(self):
        _setup_db(self._testMethodName)
        self.patcher = mock.patch(
            "backend.intake.akten_matching._suche_in_ramicro",
            return_value=[])
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def _finde(self, **signal):
        from backend.intake.akten_matching import finde_kandidaten
        return finde_kandidaten("", [dict(dokument_art="fragebogen", **signal)])

    def test_mandanten_mail_trifft(self):
        k = self._finde(mandant_email="paulgolovin@web.de")
        self.assertEqual(k[0].akte_az, "742/26")
        self.assertEqual(k[0].score, 0.8)
        self.assertEqual(k[0].quelle, "mandanten_mail")

    def test_eigenes_kennzeichen_trifft_die_mandantenzeile(self):
        k = self._finde(kfz_mandant="WÜPG777")
        self.assertEqual(k[0].akte_az, "742/26")
        self.assertEqual(k[0].score, 0.8)
        self.assertEqual(k[0].quelle, "kfz_mandant")

    def test_eigenes_kennzeichen_trifft_keine_gegnerzeile(self):
        k = self._finde(kfz_mandant="MTKDB801")
        self.assertEqual(k, [])

    def test_gegnerkennzeichen_trifft_schwach(self):
        k = self._finde(kfz_gegner="MTKDB801")
        self.assertEqual(k[0].akte_az, "742/26")
        self.assertEqual(k[0].score, 0.5)
        self.assertEqual(k[0].quelle, "kfz_gegner")

    def test_unfalltag_mit_name_schlaegt_unfalltag_allein(self):
        k = self._finde(unfalltag="2026-08-03", nachname="Golovin")
        nach_az = {x.akte_az: x for x in k}
        self.assertEqual(nach_az["742/26"].score, 0.7)
        self.assertEqual(nach_az["742/26"].quelle, "unfalltag_name")
        self.assertEqual(nach_az["900/26"].score, 0.5)
        self.assertEqual(nach_az["900/26"].quelle, "unfalltag")

    def test_unfalltag_ohne_treffer(self):
        self.assertEqual(self._finde(unfalltag="2020-01-01"), [])

    def test_bester_score_gewinnt_pro_akte(self):
        k = self._finde(mandant_email="paulgolovin@web.de",
                         unfalltag="2026-08-03", nachname="Golovin")
        treffer = [x for x in k if x.akte_az == "742/26"]
        self.assertEqual(len(treffer), 1)
        self.assertEqual(treffer[0].score, 0.8)

    def test_altweg_bleibt_unberuehrt(self):
        from backend.intake.akten_matching import finde_kandidaten
        k = finde_kandidaten("Kennzeichen WÜ-PG 777 im Gutachten", [])
        self.assertTrue(any(x.quelle == "kfz" for x in k))


if __name__ == "__main__":
    unittest.main()
