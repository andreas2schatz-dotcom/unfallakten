"""
Tests fuer die Ausfuehrung der YAML-Validierungsregeln (Befund 2026-08-06).

Die Registry-YAMLs deklarieren validierungsregeln (z.B.
summe_positionen_gleich_gesamt beim Abrechnungsschreiben), die bislang
nirgends ausgefuehrt wurden. Praxisfall Akte 1280/25: LLM liess die
Hauptposition (5.448,62 EUR) aus den positionen weg -- Summe 2.302,92
vs. gesamtbetrag 7.751,54, keine Warnung in der Review.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.intake.validierung import pruefe_validierungsregeln


def _regeln(*namen):
    return [{"name": n, "beschreibung": ""} for n in namen]


class TestSummePositionenGleichGesamt(unittest.TestCase):
    def test_abweichung_erzeugt_warnung(self):
        felder = {
            "gesamtbetrag": 7751.54,
            "positionen": [
                {"beschreibung": "Sachverständigengebühren", "betrag": 1316.62},
                {"beschreibung": "Rechtsanwaltsgebühren", "betrag": 756.30},
                {"beschreibung": "Wertminderung", "betrag": 200.0},
                {"beschreibung": "Kostenpauschale", "betrag": 30.0},
            ],
        }
        warnungen = pruefe_validierungsregeln(
            felder, _regeln("summe_positionen_gleich_gesamt"))
        self.assertEqual(len(warnungen), 1)
        self.assertIn("5448,62", warnungen[0].replace(".", ""))

    def test_passende_summe_keine_warnung(self):
        felder = {
            "gesamtbetrag": 230.0,
            "positionen": [{"betrag": 200.0}, {"betrag": 30.0}],
        }
        self.assertEqual(
            pruefe_validierungsregeln(
                felder, _regeln("summe_positionen_gleich_gesamt")), [])

    def test_toleranz_ein_cent(self):
        felder = {
            "gesamtbetrag": 230.01,
            "positionen": [{"betrag": 200.0}, {"betrag": 30.0}],
        }
        self.assertEqual(
            pruefe_validierungsregeln(
                felder, _regeln("summe_positionen_gleich_gesamt")), [])

    def test_betrag_brutto_fallback(self):
        felder = {
            "gesamtbetrag": 230.0,
            "positionen": [{"betrag_brutto": 200.0}, {"betrag_netto": 30.0}],
        }
        self.assertEqual(
            pruefe_validierungsregeln(
                felder, _regeln("summe_positionen_gleich_gesamt")), [])

    def test_fehlende_felder_keine_warnung(self):
        self.assertEqual(
            pruefe_validierungsregeln(
                {}, _regeln("summe_positionen_gleich_gesamt")), [])
        self.assertEqual(
            pruefe_validierungsregeln(
                {"gesamtbetrag": 100.0},
                _regeln("summe_positionen_gleich_gesamt")), [])


class TestAbzugGesamtSumme(unittest.TestCase):
    def test_abweichung_erzeugt_warnung(self):
        felder = {
            "abzug_gesamt": 500.0,
            "abzug_technisch": 100.0,
            "abzug_werkstattalternative": 200.0,
            "abzug_nfa": 0.0,
        }
        warnungen = pruefe_validierungsregeln(
            felder, _regeln("abzug_gesamt_summe"))
        self.assertEqual(len(warnungen), 1)

    def test_passende_summe_keine_warnung(self):
        felder = {
            "abzug_gesamt": 300.0,
            "abzug_technisch": 100.0,
            "abzug_werkstattalternative": 200.0,
        }
        self.assertEqual(
            pruefe_validierungsregeln(felder, _regeln("abzug_gesamt_summe")), [])

    def test_ohne_abzug_gesamt_keine_warnung(self):
        self.assertEqual(
            pruefe_validierungsregeln(
                {"abzug_technisch": 100.0}, _regeln("abzug_gesamt_summe")), [])


class TestNettoNachAbzugKonsistent(unittest.TestCase):
    def test_widerspruch_erzeugt_warnung(self):
        # Praxisfall Dok 516 (Akte 1280/25): LLM errechnete abzug_gesamt aus
        # der Fiktiv-Spalte, reparaturkosten_nach_pruefung stammt aus der
        # Konkret-Spalte -- 7034,51 - 1585,89 = 5448,62 != 6506,29.
        felder = {
            "reparaturkosten_netto_vor_pruefung": 7034.51,
            "abzug_gesamt": 1585.89,
            "reparaturkosten_nach_pruefung": 6506.29,
        }
        warnungen = pruefe_validierungsregeln(
            felder, _regeln("netto_nach_abzug_konsistent"))
        self.assertEqual(len(warnungen), 1)
        self.assertIn("6.506,29", warnungen[0])

    def test_konsistente_werte_keine_warnung(self):
        felder = {
            "reparaturkosten_netto_vor_pruefung": 7034.51,
            "abzug_gesamt": 528.22,
            "reparaturkosten_nach_pruefung": 6506.29,
        }
        self.assertEqual(
            pruefe_validierungsregeln(
                felder, _regeln("netto_nach_abzug_konsistent")), [])

    def test_toleranz_ein_cent(self):
        felder = {
            "reparaturkosten_netto_vor_pruefung": 100.0,
            "abzug_gesamt": 30.0,
            "reparaturkosten_nach_pruefung": 70.01,
        }
        self.assertEqual(
            pruefe_validierungsregeln(
                felder, _regeln("netto_nach_abzug_konsistent")), [])

    def test_fehlende_felder_keine_warnung(self):
        for felder in (
            {},
            {"reparaturkosten_netto_vor_pruefung": 7034.51},
            {"reparaturkosten_netto_vor_pruefung": 7034.51,
             "abzug_gesamt": 528.22},
            {"abzug_gesamt": 528.22,
             "reparaturkosten_nach_pruefung": 6506.29},
        ):
            self.assertEqual(
                pruefe_validierungsregeln(
                    felder, _regeln("netto_nach_abzug_konsistent")), [],
                felder)


class TestNachPruefungGleichKonkreterErstattung(unittest.TestCase):
    def test_fiktive_spalte_uebernommen_erzeugt_warnung(self):
        # Dok 516: LLM griff die fiktive Spalte (5448,62) statt der
        # korrigierten Summe (6506,29).
        felder = {
            "reparaturkosten_nach_pruefung": 5448.62,
            "erstattung_konkrete_reparatur_netto": 6506.29,
        }
        warnungen = pruefe_validierungsregeln(
            felder, _regeln("nach_pruefung_gleich_konkreter_erstattung"))
        self.assertEqual(len(warnungen), 1)
        self.assertIn("5.448,62", warnungen[0])

    def test_gleiche_werte_keine_warnung(self):
        felder = {
            "reparaturkosten_nach_pruefung": 6506.29,
            "erstattung_konkrete_reparatur_netto": 6506.29,
        }
        self.assertEqual(
            pruefe_validierungsregeln(
                felder,
                _regeln("nach_pruefung_gleich_konkreter_erstattung")), [])

    def test_fehlende_felder_keine_warnung(self):
        for felder in ({}, {"reparaturkosten_nach_pruefung": 6506.29},
                       {"erstattung_konkrete_reparatur_netto": 6506.29}):
            self.assertEqual(
                pruefe_validierungsregeln(
                    felder,
                    _regeln("nach_pruefung_gleich_konkreter_erstattung")),
                [], felder)


class TestRobustheit(unittest.TestCase):
    def test_unbekannte_regel_wird_uebersprungen(self):
        self.assertEqual(
            pruefe_validierungsregeln(
                {"gesamtbetrag": 1.0}, _regeln("gibt_es_nicht")), [])

    def test_kaputte_werte_crashen_nicht(self):
        felder = {
            "gesamtbetrag": "kein_betrag",
            "positionen": [{"betrag": None}, "kein_dict", {"betrag": "x"}],
        }
        self.assertEqual(
            pruefe_validierungsregeln(
                felder, _regeln("summe_positionen_gleich_gesamt")), [])

    def test_leere_regelliste(self):
        self.assertEqual(pruefe_validierungsregeln({"a": 1}, []), [])
        self.assertEqual(pruefe_validierungsregeln({"a": 1}, None), [])


if __name__ == "__main__":
    unittest.main()
