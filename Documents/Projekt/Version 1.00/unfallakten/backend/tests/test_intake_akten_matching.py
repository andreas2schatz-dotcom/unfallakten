"""
Unit-Tests fuer backend/intake/akten_matching.py (S1.7).

Score-Staffel (Plan-Vorgabe):
    az_exakt:           1.0
    az_basis (Kuerzel): 0.9
    kfz:                0.7
    beteiligten_mail:   0.6
    name_unfalldatum:   0.5

Kein Auto-Zuordnen: die Funktion liefert eine sortierte KANDIDATENLISTE.

RA-Micro-Zugriffe sind gemockt -- keine Netzwerkzugriffe im Test.
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _setup_test_db():
    """Legt eine Mini-DB mit unfallakte + beteiligte + minimalen Test-Zeilen an."""
    fd, pfad = tempfile.mkstemp(prefix="s17_", suffix=".sqlite")
    os.close(fd)
    import backend.db.database as _db
    _db.DB_PATH = pfad
    os.environ["DB_PATH"] = pfad
    from backend.db.schema_manager import init_db
    init_db()

    from backend.db.database import get_connection
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO unfallakte (az, unfalldatum, status) "
            "VALUES ('31/21', '2021-04-27', 'offen')"
        )
        conn.execute(
            "INSERT INTO unfallakte (az, unfalldatum, status) "
            "VALUES ('285/26', '2026-06-15', 'offen')"
        )
        conn.execute(
            "INSERT INTO beteiligte (akte_id, rolle, name, vorname, "
            "email, kfz_kennzeichen) VALUES "
            "('31/21', 'mandant', 'Riccio', 'Marco', 'riccio@example.com', 'OF-MU 1234')"
        )
        conn.execute(
            "INSERT INTO beteiligte (akte_id, rolle, name, vorname, "
            "email, kfz_kennzeichen) VALUES "
            "('285/26', 'mandant', 'Mustermann', 'Max', 'mustermann@example.com', 'F-XY 9876')"
        )
    return pfad


class TestAktenMatching(unittest.TestCase):
    def setUp(self):
        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        self._db_pfad = _setup_test_db()
        # Im Dev-Container ist RA-MICRO real erreichbar -- ohne Mock wuerden
        # echte Kanzleidaten die Score-Erwartungen kippen (z.B. az_exakt 1.0
        # statt az_basis 0.9). Einzelne Tests ueberschreiben den Mock lokal.
        from backend.intake import akten_matching
        self._ramicro_patcher = mock.patch.object(
            akten_matching, "_suche_in_ramicro", return_value=[])
        self._ramicro_patcher.start()

    def tearDown(self):
        self._ramicro_patcher.stop()
        import backend.db.database as _db
        _db.DB_PATH = self._alt_db_path
        os.environ.pop("DB_PATH", None)
        try:
            os.unlink(self._db_pfad)
        except OSError:
            pass

    def test_az_treffer_exakt_liefert_score_1_0(self):
        from backend.intake.akten_matching import finde_kandidaten
        kandidaten = finde_kandidaten(
            text="Bezug: Aktenzeichen 31/21", signale=[],
        )
        self.assertTrue(kandidaten, "Kein Kandidat gefunden")
        top = kandidaten[0]
        self.assertEqual(top.akte_az, "31/21")
        self.assertEqual(top.score, 1.0)
        self.assertEqual(top.quelle, "az_exakt")

    def test_az_mit_sb_kuerzel_liefert_az_basis_0_9(self):
        # "31/21AS" -> Basis "31/21" matcht
        from backend.intake.akten_matching import finde_kandidaten
        kandidaten = finde_kandidaten(
            text="Ihr Aktenzeichen: 31/21AS ...", signale=[],
        )
        self.assertTrue(kandidaten)
        top = kandidaten[0]
        self.assertEqual(top.akte_az, "31/21")
        self.assertEqual(top.score, 0.9)
        self.assertEqual(top.quelle, "az_basis")

    def test_kfz_treffer_liefert_score_0_7(self):
        from backend.intake.akten_matching import finde_kandidaten
        kandidaten = finde_kandidaten(
            text="Fahrzeug OF-MU 1234 wurde beschaedigt",
            signale=[],
        )
        self.assertTrue(kandidaten)
        top = kandidaten[0]
        self.assertEqual(top.akte_az, "31/21")
        self.assertEqual(top.score, 0.7)
        self.assertEqual(top.quelle, "kfz")

    def test_beteiligten_mail_liefert_score_0_6(self):
        # Mail als Zustellungs-Signal (absender), nicht im Text
        from backend.intake.akten_matching import finde_kandidaten
        kandidaten = finde_kandidaten(
            text="egal", signale=[{"absender": "riccio@example.com"}],
        )
        self.assertTrue(kandidaten)
        top = kandidaten[0]
        self.assertEqual(top.akte_az, "31/21")
        self.assertEqual(top.score, 0.6)
        self.assertEqual(top.quelle, "beteiligten_mail")

    def test_name_und_unfalldatum_liefert_score_0_5(self):
        # Name im Text + Unfalldatum-Match
        from backend.intake.akten_matching import finde_kandidaten
        kandidaten = finde_kandidaten(
            text="Betrifft Mustermann, Unfall vom 15.06.2026", signale=[],
        )
        # 285/26 hat 2026-06-15 als unfalldatum + Beteiligter Mustermann
        top = next((k for k in kandidaten if k.akte_az == "285/26"), None)
        self.assertIsNotNone(top, f"Kandidatenliste: {kandidaten}")
        self.assertEqual(top.score, 0.5)
        self.assertEqual(top.quelle, "name_unfalldatum")

    def test_mehrere_signale_hoechster_score_gewinnt(self):
        # AZ + KFZ beide passen, aber AZ hat hoeheren Score
        from backend.intake.akten_matching import finde_kandidaten
        kandidaten = finde_kandidaten(
            text="Aktenzeichen 31/21 KFZ OF-MU 1234", signale=[],
        )
        # Erster Kandidat: 31/21 mit 1.0 (AZ)
        self.assertEqual(kandidaten[0].akte_az, "31/21")
        self.assertEqual(kandidaten[0].score, 1.0)
        # Duplikate werden zusammengefasst -- eine akte_az, hoechster Score
        akten_ids = [k.akte_az for k in kandidaten]
        self.assertEqual(len(akten_ids), len(set(akten_ids)),
                         "Duplikate in Kandidatenliste")

    def test_kein_treffer_liefert_leere_liste(self):
        from backend.intake.akten_matching import finde_kandidaten
        kandidaten = finde_kandidaten(
            text="voellig unbeteiligter Text", signale=[],
        )
        self.assertEqual(kandidaten, [])

    def test_kandidaten_sind_absteigend_sortiert(self):
        # AZ 31/21 (score 1.0) + Mail von 31/21 (score 0.6) -> dedupliziert,
        # nur 1 Kandidat. Kombination mit anderer Akte pruefen:
        from backend.intake.akten_matching import finde_kandidaten
        kandidaten = finde_kandidaten(
            text="31/21 -- OF-MU 1234", signale=[
                {"absender": "mustermann@example.com"},
            ],
        )
        # 31/21 durch AZ (1.0), 285/26 durch Mail (0.6)
        for a, b in zip(kandidaten, kandidaten[1:]):
            self.assertGreaterEqual(a.score, b.score)

    def test_mandantenname_ohne_datum_fallback_score_0_4(self):
        """Fallback: Text enthaelt weder AZ noch KFZ noch Datum, aber einen
        Mandanten-Nachnamen aus der DB. Score 0.4 (schwaechstes Signal,
        aber besser als leere Kandidatenliste)."""
        from backend.intake.akten_matching import finde_kandidaten
        kandidaten = finde_kandidaten(
            text="Anfrage vom Mandanten Riccio bezueglich Regulierung",
            signale=[],
        )
        self.assertTrue(kandidaten,
                        "Namens-Fallback muss Kandidat liefern")
        top = kandidaten[0]
        self.assertEqual(top.akte_az, "31/21")
        self.assertEqual(top.quelle, "mandantenname")
        self.assertAlmostEqual(top.score, 0.4, places=2)

    def test_mandantenname_fallback_greift_nicht_bei_az_treffer(self):
        """Wenn ein AZ trifft, brauchen wir den schwachen Namens-Fallback
        nicht (sonst Kandidaten-Verwaesserung)."""
        from backend.intake.akten_matching import finde_kandidaten
        kandidaten = finde_kandidaten(
            text="Bezug 31/21 -- Anfrage von Riccio", signale=[],
        )
        # 31/21 kommt nur EINMAL, mit Score 1.0 (nicht 0.4)
        akten_31 = [k for k in kandidaten if k.akte_az == "31/21"]
        self.assertEqual(len(akten_31), 1)
        self.assertEqual(akten_31[0].score, 1.0)

    def test_mandantenname_matcht_nur_mandant_rolle(self):
        """Gegner/SV-Namen im Text duerfen den Fallback NICHT triggern --
        wir wollen die Akte des Mandanten finden, nicht die vom Gegner."""
        from backend.intake.akten_matching import finde_kandidaten
        # Beteiligte-Zeile 'Gegner Meier' in Akte 31/21 anlegen
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO beteiligte (akte_id, rolle, name) "
                "VALUES ('31/21', 'gegner', 'Meier')"
            )
        kandidaten = finde_kandidaten(
            text="Anschreiben an Gegner Meier", signale=[],
        )
        # Meier ist Gegner -> darf keinen Fallback ausloesen
        self.assertEqual(kandidaten, [])

    def test_ra_micro_wird_bei_akte_nicht_lokal_konsultiert(self):
        """Wenn die SQLite-Akte fehlt, aber RA-Micro sie kennt, kommt sie
        als Kandidat mit dem SQLite-Score. RA-Micro-Aufruf ist gemockt."""
        from backend.intake import akten_matching
        # 999/99 gibt es NUR in RA-Micro-Mock, nicht in SQLite
        with mock.patch.object(
            akten_matching, "_suche_in_ramicro",
            return_value=[("999/99", 1.0, "az_exakt", "999/99")],
        ):
            kandidaten = akten_matching.finde_kandidaten(
                text="Aktenzeichen 999/99", signale=[],
            )
        self.assertTrue(any(k.akte_az == "999/99" for k in kandidaten))

    def test_ra_micro_fehler_ignoriert(self):
        # Kein Crash wenn RA-Micro nicht erreichbar.
        from backend.intake import akten_matching
        with mock.patch.object(
            akten_matching, "_suche_in_ramicro",
            side_effect=Exception("RA-Micro offline"),
        ):
            kandidaten = akten_matching.finde_kandidaten(
                text="31/21", signale=[],
            )
        self.assertTrue(any(k.akte_az == "31/21" for k in kandidaten))


if __name__ == "__main__":
    unittest.main()
