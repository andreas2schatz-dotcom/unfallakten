"""Tests: PRD-27 Replacement-Engine + Vorschau-Endpoint"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestErsetzePlatzhalter(unittest.TestCase):

    def setUp(self):
        from backend.word.stellungnahme_service import ersetze_platzhalter
        self.fn = ersetze_platzhalter

    def test_einfache_ersetzung(self):
        text = "Sehr geehrte Damen und Herren von <VERSICHERER>,"
        kontext = {"VERSICHERER": "Allianz AG"}
        result = self.fn(text, kontext)
        self.assertEqual(result, "Sehr geehrte Damen und Herren von Allianz AG,")

    def test_mehrere_platzhalter(self):
        text = "Mandant: <MANDANT>, AZ: <AZ>"
        kontext = {"MANDANT": "Max Mustermann", "AZ": "31/21"}
        result = self.fn(text, kontext)
        self.assertEqual(result, "Mandant: Max Mustermann, AZ: 31/21")

    def test_unbekannter_platzhalter_wird_markiert(self):
        text = "Wert: <UNBEKANNT>"
        result = self.fn(text, {})
        self.assertIn("[FEHLT: <UNBEKANNT>]", result)

    def test_leerer_text(self):
        self.assertIsNone(self.fn(None, {"X": "y"}))

    def test_leerer_wert_bleibt_leer(self):
        text = "Hallo <MANDANT>"
        result = self.fn(text, {"MANDANT": ""})
        self.assertEqual(result, "Hallo ")


if __name__ == "__main__":
    unittest.main()
