"""
Tests fuer das deterministische Positions-Sicherungsnetz (Befund 1280/25).

Die VHV rechnet mit der Zeile "Abrechnung nach Prüfbericht 5.448,62 EUR" ab.
Die LLM-Extraktion hat diese Zeile als ``abrechnungsart`` interpretiert --
der Hauptbetrag fehlte in ``felder.positionen`` und die Validierung meldete
eine Differenz von exakt 5.448,62 EUR.

Zwei Schichten:
  1. abrechnungsschreiben_parser kennt das Label als Position (reparatur_netto).
  2. extrahiere_felder gleicht LLM-Positionen gegen die Regex-Positionen ab
     und ergaenzt fehlende Betraege nur, wenn sie die Differenz zum
     Gesamtbetrag exakt erklaeren (kein Junk).
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


VHV_TEXT = (
    "Schadennummer\n"
    "SD0 0003 2129 28 T01\n"
    "Ihr Zeichen\n"
    "1280/25AS\n"
    "Sehr geehrte Damen und Herren,\n"
    "die Abrechnung zum oben genannten Schaden nehmen wir wie folgt vor:\n"
    "Abrechnung nach Prüfbericht 5.448,62 EUR\n"
    "Sachverständigengebühren 1.316,62 EUR\n"
    "Rechtsanwaltsgebühren 756,30 EUR\n"
    "Wertminderung 200,00 EUR\n"
    "Kostenpauschale 30,00 EUR\n"
    "Zahlung per Überweisung 7.751,54 EUR\n"
    "Wir haben die Kalkulation zum Fahrzeugschaden geprüft.\n"
)

LLM_POSITIONEN_OHNE_HAUPTBETRAG = [
    {"bezeichnung": "Sachverständigengebühren", "betrag": 1316.62},
    {"bezeichnung": "Rechtsanwaltsgebühren", "betrag": 756.30},
    {"bezeichnung": "Wertminderung", "betrag": 200.00},
    {"bezeichnung": "Kostenpauschale", "betrag": 30.00},
]


def _registry_abrechnung():
    from backend.intake.registry_loader import Registry
    klassen = {
        "abrechnungsschreiben": {
            "klasse": "abrechnungsschreiben",
            "marker": [],
            "regex_felder": {},
            "schema": {
                "versicherer_kuerzel": "string",
                "abrechnungsart": "string",
                "gesamtbetrag": "number",
                "positionen": "array",
            },
            "pflichtfelder": [],
            "kritische_felder": [],
            "validierungsregeln": [],
            "fristrelevanz": True,
            "loeschfrist_jahre": 6,
        }
    }
    return Registry(version="test", klassen=klassen, pfad="")


class TestParserAbrechnungNachPruefbericht(unittest.TestCase):
    def test_abrechnung_nach_pruefbericht_wird_als_position_erkannt(self):
        from backend.parsers.abrechnungsschreiben_parser import (
            parse_abrechnungsschreiben,
        )
        r = parse_abrechnungsschreiben(VHV_TEXT)
        nach_art = {p.art: p for p in r.positionen}
        self.assertIn("reparatur_netto", nach_art,
                      f"Positionen: {[(p.art, p.bezeichnung) for p in r.positionen]}")
        self.assertEqual(nach_art["reparatur_netto"].betrag_netto, 5448.62)

    def test_uebrige_vhv_positionen_bleiben_erhalten(self):
        from backend.parsers.abrechnungsschreiben_parser import (
            parse_abrechnungsschreiben,
        )
        r = parse_abrechnungsschreiben(VHV_TEXT)
        betraege = sorted(
            (p.betrag_netto or p.betrag_brutto) for p in r.positionen
        )
        self.assertEqual(betraege, [30.00, 200.00, 756.30, 1316.62, 5448.62])


class TestPositionsSicherungsnetz(unittest.TestCase):
    def _extrahiere(self, llm_ergebnis):
        from backend.intake import extraktion
        with mock.patch(
            "backend.intake.extraktion.llm_service.extrahiere_nach_schema",
            return_value=llm_ergebnis,
        ):
            return extraktion.extrahiere_felder(
                VHV_TEXT, "abrechnungsschreiben", _registry_abrechnung(),
            )

    def test_fehlender_hauptbetrag_wird_ergaenzt(self):
        """Befund 1280/25: Differenz zum Gesamtbetrag entspricht exakt einer
        Regex-Position -> diese wird angehaengt."""
        ergebnis = self._extrahiere({
            "abrechnungsart": "Abrechnung nach Prüfbericht",
            "gesamtbetrag": 7751.54,
            "positionen": list(LLM_POSITIONEN_OHNE_HAUPTBETRAG),
        })
        positionen = ergebnis["felder"]["positionen"]
        betraege = [p.get("betrag") for p in positionen]
        self.assertIn(5448.62, betraege)
        self.assertEqual(len(positionen), 5)

    def test_keine_aenderung_wenn_summe_bereits_stimmt(self):
        ergebnis = self._extrahiere({
            "gesamtbetrag": 2302.92,
            "positionen": list(LLM_POSITIONEN_OHNE_HAUPTBETRAG),
        })
        self.assertEqual(len(ergebnis["felder"]["positionen"]), 4)

    def test_mehrere_fehlende_positionen_wenn_summe_exakt_passt(self):
        """LLM hat nur die SV-Gebuehren -- die vier fehlenden Regex-Positionen
        erklaeren die Differenz exakt und werden gemeinsam ergaenzt."""
        ergebnis = self._extrahiere({
            "gesamtbetrag": 7751.54,
            "positionen": [
                {"bezeichnung": "Sachverständigengebühren", "betrag": 1316.62},
            ],
        })
        positionen = ergebnis["felder"]["positionen"]
        betraege = sorted(p.get("betrag") for p in positionen)
        self.assertEqual(betraege, [30.00, 200.00, 756.30, 1316.62, 5448.62])

    def test_kein_junk_wenn_differenz_nicht_erklaerbar(self):
        """Erklaert keine Kandidaten-Kombination die Differenz, wird nichts
        angehaengt -- die Validierungswarnung bleibt der ehrliche Zustand."""
        ergebnis = self._extrahiere({
            "gesamtbetrag": 9999.99,
            "positionen": list(LLM_POSITIONEN_OHNE_HAUPTBETRAG),
        })
        self.assertEqual(len(ergebnis["felder"]["positionen"]), 4)

    def test_llm_ausgefallen_regex_positionen_als_fallback(self):
        ergebnis = self._extrahiere(None)
        positionen = ergebnis["felder"].get("positionen") or []
        betraege = sorted(p.get("betrag") for p in positionen)
        self.assertEqual(betraege, [30.00, 200.00, 756.30, 1316.62, 5448.62])

    def test_abzugszeilen_werden_nicht_als_position_ergaenzt(self):
        """MwSt-/Pruefbericht-Abzuege sind keine Auszahlungspositionen."""
        text = (
            "die Abrechnung nehmen wir wie folgt vor:\n"
            "Reparaturkosten gemäß Gutachten 3.574,95 EUR\n"
            "./. Mehrwertsteuer (19%) 570,79 EUR\n"
            "Kostenpauschale 30,00 EUR\n"
        )
        from backend.intake import extraktion
        with mock.patch(
            "backend.intake.extraktion.llm_service.extrahiere_nach_schema",
            return_value=None,
        ):
            ergebnis = extraktion.extrahiere_felder(
                text, "abrechnungsschreiben", _registry_abrechnung(),
            )
        positionen = ergebnis["felder"].get("positionen") or []
        bezeichnungen = [p.get("bezeichnung", "").lower() for p in positionen]
        self.assertFalse(
            any("mehrwertsteuer" in b for b in bezeichnungen),
            f"Abzug als Position uebernommen: {positionen!r}",
        )


if __name__ == "__main__":
    unittest.main()
