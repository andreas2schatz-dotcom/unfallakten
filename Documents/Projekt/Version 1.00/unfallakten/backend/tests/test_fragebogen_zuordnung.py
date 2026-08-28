"""Verdichtung der Kandidatenliste zur Ampel."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.intake.fragebogen_zuordnung import bewerte


def _k(az, score, quelle, bezeichnung=None, abgelegt=False,
        abgelegt_am=None):
    return {"akte_az": az, "score": score, "quelle": quelle, "treffer": "x",
            "bezeichnung": bezeichnung, "abgelegt": abgelegt,
            "abgelegt_am": abgelegt_am}


class TestBewerte(unittest.TestCase):
    def test_ohne_kandidaten_neue_akte(self):
        e = bewerte([])
        self.assertEqual(e["ampel"], "neu")
        self.assertIsNone(e["akte_az"])
        self.assertIsNone(e["kurzbezeichnung"])
        self.assertEqual(e["kandidaten_anzahl"], 0)

    def test_none_wie_leer(self):
        self.assertEqual(bewerte(None)["ampel"], "neu")

    def test_ein_starker_kandidat_ist_gruen(self):
        e = bewerte([_k("742/26", 0.8, "mandanten_mail", "Golovin/Brochner")])
        self.assertEqual(e["ampel"], "gruen")
        self.assertEqual(e["akte_az"], "742/26")
        self.assertEqual(e["kurzbezeichnung"], "Golovin/Brochner")
        self.assertEqual(e["begruendung"], "Mandanten-E-Mail")

    def test_ohne_kurzbezeichnung_kein_absturz(self):
        e = bewerte([_k("742/26", 0.8, "mandanten_mail")])
        self.assertEqual(e["ampel"], "gruen")
        self.assertIsNone(e["kurzbezeichnung"])

    def test_aktenzeichen_ist_gruen(self):
        e = bewerte([_k("641/26", 1.0, "aktenzeichen")])
        self.assertEqual(e["ampel"], "gruen")
        self.assertEqual(e["begruendung"], "Aktenzeichen im Bogen")

    def test_unfalltag_mit_name_ist_gruen(self):
        e = bewerte([_k("742/26", 0.7, "unfalltag_name")])
        self.assertEqual(e["ampel"], "gruen")
        self.assertEqual(e["begruendung"], "Unfalltag + Name")

    def test_schwacher_kandidat_ist_pruefen(self):
        e = bewerte([_k("900/26", 0.5, "unfalltag")])
        self.assertEqual(e["ampel"], "pruefen")
        self.assertEqual(e["akte_az"], "900/26")
        self.assertEqual(e["begruendung"], "Unfalltag")

    def test_gegnerkennzeichen_allein_ist_pruefen(self):
        self.assertEqual(
            bewerte([_k("742/26", 0.5, "kfz_gegner")])["ampel"], "pruefen")

    def test_zwei_starke_kandidaten_sind_pruefen(self):
        e = bewerte([_k("751/26", 0.8, "mandanten_mail"),
                      _k("848/25", 0.8, "mandanten_mail")])
        self.assertEqual(e["ampel"], "pruefen")
        self.assertEqual(e["kandidaten_anzahl"], 2)

    def test_starker_kandidat_neben_schwachem_bleibt_gruen(self):
        e = bewerte([_k("742/26", 0.8, "mandanten_mail"),
                      _k("900/26", 0.5, "unfalltag")])
        self.assertEqual(e["ampel"], "gruen")
        self.assertEqual(e["akte_az"], "742/26")
        self.assertEqual(e["kandidaten_anzahl"], 2)

    def test_nur_abgelegte_kandidaten_ergeben_abgelegt(self):
        e = bewerte([_k("749/26", 0.8, "mandanten_mail", "Rügner/Unbekannt",
                         abgelegt=True, abgelegt_am="2026-08-26")])
        self.assertEqual(e["ampel"], "abgelegt")
        self.assertEqual(e["akte_az"], "749/26")
        self.assertEqual(e["kurzbezeichnung"], "Rügner/Unbekannt")
        self.assertEqual(e["abgelegt_am"], "2026-08-26")

    def test_laufender_kandidat_schlaegt_abgelegten(self):
        e = bewerte([_k("742/26", 0.8, "mandanten_mail", "Golovin/Brochner"),
                      _k("749/26", 0.8, "mandanten_mail", "Rügner/Unbekannt",
                         abgelegt=True, abgelegt_am="2026-08-26")])
        self.assertEqual(e["ampel"], "gruen")
        self.assertEqual(e["akte_az"], "742/26")
        self.assertIsNone(e["abgelegt_am"])

    def test_abgelegt_am_fehlt_kein_absturz(self):
        e = bewerte([_k("749/26", 0.8, "mandanten_mail", abgelegt=True)])
        self.assertEqual(e["ampel"], "abgelegt")
        self.assertIsNone(e["abgelegt_am"])

    def test_unbekannte_quelle_bekommt_lesbaren_ersatz(self):
        e = bewerte([_k("742/26", 0.9, "irgendwas")])
        self.assertEqual(e["begruendung"], "irgendwas")

    def test_kandidaten_anzahl_zaehlt_bei_gemischter_liste_alle(self):
        """W-Nachtrag-Punkt 2: kandidaten_anzahl zaehlte bisher bei einer
        Mischung aus laufenden und abgelegten Kandidaten nur die laufenden
        -- die Zeile zeigte dann eine kleinere Zahl als die Kandidatenliste
        im Detail. Muss durchgaengig ALLE Kandidaten zaehlen, egal ob
        laufend oder abgelegt."""
        e = bewerte([_k("742/26", 0.8, "mandanten_mail", "Golovin/Brochner"),
                      _k("749/26", 0.8, "mandanten_mail", "Rügner/Unbekannt",
                         abgelegt=True, abgelegt_am="2026-08-26")])
        self.assertEqual(e["kandidaten_anzahl"], 2)


if __name__ == "__main__":
    unittest.main()
