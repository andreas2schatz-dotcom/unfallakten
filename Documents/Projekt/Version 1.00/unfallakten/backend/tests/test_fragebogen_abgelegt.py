"""Rueckfall auf abgelegte Akten.

Findet die regulaere Suche gar nichts, wird einmal ohne Ablage-Filter
nachgesehen -- sonst bekaeme ein Bogen zu einem abgeschlossenen Fall den
Vorschlag "neue Akte anlegen" und erzeugte eine Dublette.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

MERKMALE = {"dokument_art": "fragebogen",
            "mandant_email": "bernd.ruegner@t-online.de",
            "kfz_mandant": "OFBR1612",
            "nachname": "Rügner",
            "unfalltag": "2026-08-06"}


class TestAbgelegtSuche(unittest.TestCase):
    def test_filter_sucht_nur_abgelegte(self):
        from backend.ramicro import email_matching as em
        aufrufe = []

        class _Cur:
            def execute(self, sql, params=None):
                aufrufe.append(" ".join(sql.split()))
            def fetchall(self):
                return [{"az": "749/26", "bezeichnung": "Rügner/Unbekannt",
                          "abgelegt_am": "2026-08-26"}]

        conn = mock.MagicMock()
        conn.cursor.return_value = _Cur()
        ctx = mock.MagicMock()
        ctx.__enter__.return_value = conn
        ctx.__exit__.return_value = False
        with mock.patch.object(em, "get_ramicro_connection", return_value=ctx):
            treffer = em.suche_abgelegte_in_ramicro(MERKMALE)

        self.assertTrue(treffer)
        az, methode, _tr, bez, abgelegt_am = treffer[0]
        self.assertEqual(az, "749/26")
        self.assertEqual(bez, "Rügner/Unbekannt")
        self.assertEqual(abgelegt_am, "2026-08-26")
        self.assertIn("dtAblage IS NOT NULL", aufrufe[0])
        self.assertNotIn("dtAblage IS NULL", aufrufe[0])

    def test_ohne_merkmale_keine_abfrage(self):
        from backend.ramicro import email_matching as em
        with mock.patch.object(em, "get_ramicro_connection") as verbindung:
            self.assertEqual(em.suche_abgelegte_in_ramicro({}), [])
            verbindung.assert_not_called()


class TestRueckfallInFindeKandidaten(unittest.TestCase):
    def _finde(self, regulaer, abgelegt):
        from backend.intake import akten_matching as am
        with mock.patch.object(am, "_suche_in_ramicro", return_value=regulaer), \
             mock.patch("backend.ramicro.email_matching."
                         "suche_abgelegte_in_ramicro", return_value=abgelegt):
            return am.finde_kandidaten("", [MERKMALE])

    def test_rueckfall_nur_wenn_nichts_gefunden(self):
        k = self._finde([], [("749/26", "mandanten_mail",
                               "bernd.ruegner@t-online.de",
                               "Rügner/Unbekannt", "2026-08-26")])
        self.assertEqual(len(k), 1)
        self.assertEqual(k[0].akte_az, "749/26")
        self.assertTrue(k[0].abgelegt)
        self.assertEqual(k[0].abgelegt_am, "2026-08-26")
        self.assertEqual(k[0].bezeichnung, "Rügner/Unbekannt")

    def test_laufende_akte_verdraengt_den_rueckfall(self):
        from backend.intake import akten_matching as am
        from backend.intake.akten_matching import AktenKandidat
        laufend = [AktenKandidat(akte_az="742/26", score=0.8,
                                  quelle="mandanten_mail", treffer="x",
                                  bezeichnung="Golovin/Brochner")]
        with mock.patch.object(am, "_suche_in_ramicro", return_value=laufend), \
             mock.patch("backend.ramicro.email_matching."
                         "suche_abgelegte_in_ramicro") as abgelegt:
            k = am.finde_kandidaten("", [MERKMALE])
            abgelegt.assert_not_called()
        self.assertEqual([x.akte_az for x in k], ["742/26"])
        self.assertFalse(k[0].abgelegt)

    def test_kein_rueckfall_ohne_bogen(self):
        from backend.intake import akten_matching as am
        with mock.patch.object(am, "_suche_in_ramicro", return_value=[]), \
             mock.patch("backend.ramicro.email_matching."
                         "suche_abgelegte_in_ramicro") as abgelegt:
            am.finde_kandidaten("Sehr geehrte Damen und Herren", [])
            abgelegt.assert_not_called()


if __name__ == "__main__":
    unittest.main()
