"""PRD-37: reine Vorschlags-Funktion baue_bezeichnung."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.intake.registry_loader import Registry
from backend.services.dokument_bezeichnung import baue_bezeichnung


def _reg():
    return Registry(version="test", pfad="", klassen={
        "rechnung": {
            "klasse": "rechnung", "label": "Rechnung",
            "bezeichnung_felder": {"aussteller": "aussteller",
                                    "datum": "rechnungsdatum",
                                    "betrag": "bruttobetrag"},
        },
        "gutachten": {
            "klasse": "gutachten", "label": "Gutachten",
            "bezeichnung_felder": {"aussteller": "sv_buero",
                                    "datum": "besichtigungsdatum"},
        },
        "abrechnungsschreiben": {
            "klasse": "abrechnungsschreiben", "label": "Abrechnungsschreiben",
            "bezeichnung_felder": {"aussteller": "versicherer",
                                    "datum": "schreibdatum",
                                    "betrag": "gesamtbetrag"},
        },
        "sonstiges": {
            "klasse": "sonstiges", "label": "Sonstiges",
            "bezeichnung_felder": {"datum": "datum"},
        },
    })


class TestBaueBezeichnung(unittest.TestCase):
    def test_alle_teile(self):
        s = baue_bezeichnung("rechnung",
            {"aussteller": "Autohaus Müller", "rechnungsdatum": "12.03.2026",
             "bruttobetrag": "1.234,56"},
            {"ist_email": False, "eingangsdatum": None}, _reg())
        self.assertEqual(s, "Rechnung Autohaus Müller vom 12.03.2026 (1.234,56 €)")

    def test_fehlende_teile_fallen_weg(self):
        s = baue_bezeichnung("gutachten",
            {"besichtigungsdatum": "12.03.2026"},
            {"ist_email": False, "eingangsdatum": None}, _reg())
        self.assertEqual(s, "Gutachten vom 12.03.2026")

    def test_ohne_datum(self):
        s = baue_bezeichnung("abrechnungsschreiben",
            {"versicherer": "Allianz", "gesamtbetrag": "8.500,00"},
            {"ist_email": False, "eingangsdatum": None}, _reg())
        self.assertEqual(s, "Abrechnungsschreiben Allianz (8.500,00 €)")

    def test_betrag_als_zahl(self):
        s = baue_bezeichnung("rechnung",
            {"aussteller": "X", "bruttobetrag": 1234.5},
            {"ist_email": False, "eingangsdatum": None}, _reg())
        self.assertEqual(s, "Rechnung X (1.234,50 €)")

    def test_iso_datum_wird_deutsch(self):
        s = baue_bezeichnung("rechnung",
            {"rechnungsdatum": "2026-03-12"},
            {"ist_email": False, "eingangsdatum": None}, _reg())
        self.assertEqual(s, "Rechnung vom 12.03.2026")

    def test_unbekannte_klasse_fallback_auf_rohklasse(self):
        s = baue_bezeichnung("mahnung", {"betrag": "5,00"},
            {"ist_email": False, "eingangsdatum": None}, _reg())
        self.assertEqual(s, "mahnung")

    def test_sonstiges_email_mit_eingangsdatum(self):
        s = baue_bezeichnung("sonstiges", {},
            {"ist_email": True, "eingangsdatum": "2026-03-12 09:30:00"}, _reg())
        self.assertEqual(s, "E-Mail vom 12.03.2026")

    def test_sonstiges_schreiben_mit_schriftdatum(self):
        s = baue_bezeichnung("sonstiges", {"datum": "05.03.2026"},
            {"ist_email": False, "eingangsdatum": "2026-03-12"}, _reg())
        self.assertEqual(s, "Schreiben vom 05.03.2026")

    def test_sonstiges_schriftdatum_hat_vorrang_vor_eingang(self):
        s = baue_bezeichnung("sonstiges", {"datum": "05.03.2026"},
            {"ist_email": True, "eingangsdatum": "2026-03-12"}, _reg())
        self.assertEqual(s, "E-Mail vom 05.03.2026")

    def test_sonstiges_ohne_jedes_datum(self):
        s = baue_bezeichnung("sonstiges", {},
            {"ist_email": False, "eingangsdatum": None}, _reg())
        self.assertEqual(s, "Schreiben")

    def test_registry_none_liefert_rohklasse(self):
        s = baue_bezeichnung("rechnung", {"aussteller": "X"},
            {"ist_email": False, "eingangsdatum": None}, None)
        self.assertEqual(s, "rechnung")


if __name__ == "__main__":
    unittest.main()
