"""
Tests fuer extrahiere_verweisbetrieb (werkstatt_service).

VHV-Blockformat (Befund Akte 1280/25, Dok 516): Der verwendete
Reparaturbetrieb steht nach "Fuer die Korrekturberechnung haben wir den
Reparaturbetrieb", gefolgt von Name/Strasse/PLZ-Block und
"Entfernungskilometer: X km", abgeschlossen mit "beruecksichtigt.".
Danach folgen Alternativ-Betriebe, die NICHT gezogen werden duerfen.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

VHV_TEXT = (
    "Wird eine Referenzwerkstatt benannt, berücksichtigen wir bei der\n"
    "Höhe der Stundenverrechnungssätze die Preise dieser Werkstatt.\n"
    "Die Stundenverrechnungssätze der benannten Werkstätten entsprechen\n"
    "der Preisangabenverordnung und sind für alle Verbraucher zugänglich.\n"
    "Detaillierte Angaben zum Reparaturbetrieb, zur Garantie und der\n"
    "räumlichen Nähe sind im Prüfbericht aufgeführt.\n"
    "Für die Korrekturberechnung haben wir den Reparaturbetrieb\n"
    "\n"
    "Möser Arno - Karosseriefachbetrieb\n"
    "Philipp-Reis-Straße 9\n"
    "63128 Dietzenbach\n"
    "Telefon: 06074-25936\n"
    "Web: www.kbmoeser.de\n"
    "Reparaturkosten (Netto): 5448,62 EUR\n"
    "Lohn Mechanik: 130,00 EUR/Stunde\n"
    "Lohn Lackierung: 135,00 EUR/Stunde\n"
    "Qualitätsmerkmale: ZKF\n"
    "Entfernungskilometer: 16,00 km\n"
    "Garantieleistung: 5-5 Jahre\n"
    "berücksichtigt.\n"
    "Ferner stehen Ihnen weitere Reparaturbetriebe zur Auswahl:\n"
    "Rauch Karosseriebau GmbH\n"
    "Industriestraße 18\n"
    "61381 Friedrichsdorf\n"
    "Telefon: 06172-72500\n"
    "Entfernungskilometer: 29,69 km\n"
)


class TestVhvBlock(unittest.TestCase):
    def test_vhv_block_wird_extrahiert(self):
        from backend.services.werkstatt_service import extrahiere_verweisbetrieb
        t = extrahiere_verweisbetrieb(VHV_TEXT)
        self.assertTrue(t["gefunden"])
        self.assertEqual(t["quelle"], "vhv_block")
        self.assertEqual(t["name"], "Möser Arno - Karosseriefachbetrieb")
        self.assertEqual(t["adresse"], "Philipp-Reis-Straße 9")
        self.assertEqual(t["plz_ort"], "63128 Dietzenbach")
        self.assertEqual(t["telefon"], "06074-25936")

    def test_vhv_block_nimmt_verwendeten_betrieb_nicht_alternative(self):
        from backend.services.werkstatt_service import extrahiere_verweisbetrieb
        t = extrahiere_verweisbetrieb(VHV_TEXT)
        self.assertEqual(t["km_genannt"], 16.0)
        self.assertNotIn("Rauch", t["name"])

    def test_controlexpert_format_weiterhin_erkannt(self):
        from backend.services.werkstatt_service import extrahiere_verweisbetrieb
        text = (
            "Verwendeter Referenzbetrieb\n"
            "Karosseriebau Muster GmbH\n"
            "Musterstraße 12\n"
            "60311 Frankfurt\n"
            "069/123456\n"
            "Entfernung zum Anspruchsteller: 7,5 km\n"
        )
        t = extrahiere_verweisbetrieb(text)
        self.assertTrue(t["gefunden"])
        self.assertEqual(t["quelle"], "controlexpert")
        self.assertEqual(t["name"], "Karosseriebau Muster GmbH")
        self.assertEqual(t["km_genannt"], 7.5)


if __name__ == "__main__":
    unittest.main()
