"""
Bugfix 828/24: Synthetischer GHPV-Eintrag duplizierte die Haftpflichtversicherung,
weil der Guard den WDM-Kurznamen (varG-HV, z.B. "ADAC") woertlich mit dem
Beteiligten-Namen ("ADAC Autoversicherung AG") verglich.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.routers.klage_routes import _ghpv_bereits_vorhanden


def _bek(**kw):
    b = {"rolle_klage": "beklagter", "kuerzel": "", "vorname": "",
         "name": "", "firma": "", "versicherung": ""}
    b.update(kw)
    return b


class TestGhpvBereitsVorhanden(unittest.TestCase):
    def test_kz_ghpv_zaehlt_auch_bei_namensabweichung(self):
        # Konstellation 828/24: WDM sagt "ADAC", Beteiligter heisst voll
        alle = [_bek(kuerzel="GHPV", name="ADAC Autoversicherung AG")]
        self.assertTrue(_ghpv_bereits_vorhanden(alle, "ADAC"))

    def test_kz_varianten_gh_und_ghv(self):
        self.assertTrue(_ghpv_bereits_vorhanden([_bek(kuerzel="GH", name="X")], "Y"))
        self.assertTrue(_ghpv_bereits_vorhanden([_bek(kuerzel="GHV", name="X")], "Y"))

    def test_namensgleichheit_ohne_kz(self):
        alle = [_bek(name="Allianz Versicherungs-AG")]
        self.assertTrue(_ghpv_bereits_vorhanden(alle, "Allianz Versicherungs-AG"))

    def test_namens_enthaltensein_ohne_kz(self):
        alle = [_bek(name="ADAC Autoversicherung AG")]
        self.assertTrue(_ghpv_bereits_vorhanden(alle, "ADAC"))
        self.assertTrue(_ghpv_bereits_vorhanden([_bek(name="ADAC")],
                                                "ADAC Autoversicherung AG"))

    def test_person_mit_vorname_zaehlt_nicht(self):
        # Fahrer heisst zufaellig wie im WDM-Feld -> kein Treffer, Person bleibt Person
        alle = [_bek(vorname="Kadir", name="Kuzaytepe")]
        self.assertFalse(_ghpv_bereits_vorhanden(alle, "Kuzaytepe"))

    def test_kein_ghpv_vorhanden(self):
        alle = [_bek(vorname="Kadir", name="Kuzaytepe"),
                _bek(name="Autohaus Mueller GmbH")]
        self.assertFalse(_ghpv_bereits_vorhanden(alle, "ADAC"))

    def test_nicht_beklagte_ignoriert(self):
        alle = [_bek(rolle_klage="klaeger", kuerzel="GHPV", name="ADAC")]
        self.assertFalse(_ghpv_bereits_vorhanden(alle, "ADAC"))

    def test_leerer_wdm_name(self):
        self.assertFalse(_ghpv_bereits_vorhanden([_bek(name="Irgendwas")], ""))
        self.assertTrue(_ghpv_bereits_vorhanden([_bek(kuerzel="GHPV")], ""))


if __name__ == "__main__":
    unittest.main()
