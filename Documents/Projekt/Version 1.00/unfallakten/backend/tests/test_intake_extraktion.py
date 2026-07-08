"""
Unit-Tests fuer backend/intake/extraktion.py (S1.6b).

extrahiere_felder(text, klasse, registry) -> {"felder": {...},
                                                "llm_konflikt": {...}?}
LLM ist Primaerquelle (Umkehrung des heutigen Shadow-Modes -- gilt NUR im
Neu-Pfad), Regex dient als Anker und Konsistenzcheck.

LLM-Aufrufe sind gemockt.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _mini_registry_mit_abrechnung():
    from backend.intake.registry_loader import Registry
    klassen = {
        "abrechnungsschreiben": {
            "klasse": "abrechnungsschreiben",
            "marker": [],
            "regex_felder": {
                "schadennummer": [
                    r"Schadennummer[:\s]+([A-Z0-9\-/]+)",
                    r"Schaden-Nr\.?[:\s]+([A-Z0-9\-/]+)",
                ],
                "schreibdatum": [r"\b(\d{2}\.\d{2}\.\d{4})\b"],
            },
            "schema": {
                "schadennummer": "string",
                "schreibdatum": "date",
                "gesamtbetrag": "number",
            },
            "pflichtfelder": [],
            "kritische_felder": [],
            "validierungsregeln": [],
            "fristrelevanz": True,
            "loeschfrist_jahre": 6,
        }
    }
    return Registry(version="test", klassen=klassen, pfad="", fehler=[])


class TestExtraktion(unittest.TestCase):
    def test_regex_felder_werden_extrahiert_wenn_llm_none(self):
        from backend.intake import extraktion
        registry = _mini_registry_mit_abrechnung()
        text = ("Schadennummer: 12-345-67890 "
                "Datum 22.04.2026 Gesamtbetrag 7.280 EUR")
        with mock.patch(
            "backend.intake.extraktion.llm_service.extrahiere_nach_schema",
            return_value=None,
        ):
            ergebnis = extraktion.extrahiere_felder(
                text, "abrechnungsschreiben", registry,
            )
        felder = ergebnis["felder"]
        self.assertEqual(felder["schadennummer"], "12-345-67890")
        self.assertEqual(felder["schreibdatum"], "22.04.2026")

    def test_llm_ist_primaer_quelle_wenn_erfolgreich(self):
        """LLM primaer, Regex Fallback -- Freigabe-Vorgabe fuer den Neu-Pfad."""
        from backend.intake import extraktion
        registry = _mini_registry_mit_abrechnung()
        text = ("Schadennummer: 12-345-67890 "
                "Datum 22.04.2026 Gesamtbetrag 7.280,00 EUR")
        with mock.patch(
            "backend.intake.extraktion.llm_service.extrahiere_nach_schema",
            return_value={
                "schadennummer": "12-345-67890-LLM",
                "schreibdatum": "2026-04-22",
                "gesamtbetrag": 7280.00,
            },
        ):
            ergebnis = extraktion.extrahiere_felder(
                text, "abrechnungsschreiben", registry,
            )
        felder = ergebnis["felder"]
        self.assertEqual(felder["schadennummer"], "12-345-67890-LLM")
        self.assertEqual(felder["gesamtbetrag"], 7280.00)

    def test_llm_konflikt_wird_gestempelt_bei_divergenz(self):
        from backend.intake import extraktion
        registry = _mini_registry_mit_abrechnung()
        text = "Schadennummer: 12-345-67890 Datum 22.04.2026"
        with mock.patch(
            "backend.intake.extraktion.llm_service.extrahiere_nach_schema",
            return_value={
                "schadennummer": "99-999-99999",
                "schreibdatum": "22.04.2026",
            },
        ):
            ergebnis = extraktion.extrahiere_felder(
                text, "abrechnungsschreiben", registry,
            )
        self.assertIn("llm_konflikt", ergebnis)
        self.assertIn("schadennummer", ergebnis["llm_konflikt"])
        konflikt = ergebnis["llm_konflikt"]["schadennummer"]
        self.assertEqual(konflikt["llm"], "99-999-99999")
        self.assertEqual(konflikt["regex"], "12-345-67890")

    def test_kein_llm_konflikt_wenn_werte_identisch(self):
        from backend.intake import extraktion
        registry = _mini_registry_mit_abrechnung()
        text = "Schadennummer: 12-345-67890 Datum 22.04.2026"
        with mock.patch(
            "backend.intake.extraktion.llm_service.extrahiere_nach_schema",
            return_value={"schadennummer": "12-345-67890",
                          "schreibdatum": "22.04.2026"},
        ):
            ergebnis = extraktion.extrahiere_felder(
                text, "abrechnungsschreiben", registry,
            )
        self.assertNotIn("llm_konflikt", ergebnis)

    def test_unbekannte_klasse_liefert_leere_felder(self):
        from backend.intake import extraktion
        registry = _mini_registry_mit_abrechnung()
        with mock.patch(
            "backend.intake.extraktion.llm_service.extrahiere_nach_schema",
            return_value=None,
        ):
            ergebnis = extraktion.extrahiere_felder(
                "text", "fantasieklasse", registry,
            )
        self.assertEqual(ergebnis["felder"], {})

    def test_llm_service_bekommt_das_yaml_schema(self):
        from backend.intake import extraktion
        registry = _mini_registry_mit_abrechnung()
        with mock.patch(
            "backend.intake.extraktion.llm_service.extrahiere_nach_schema",
            return_value=None,
        ) as m:
            extraktion.extrahiere_felder(
                "text", "abrechnungsschreiben", registry,
            )
        # Erstes Argument ist das schema-dict
        args = m.call_args.args
        kwargs = m.call_args.kwargs
        schema_arg = args[0] if args else kwargs.get("schema", {})
        # Muss alle YAML-Schemafelder enthalten
        for feld in ("schadennummer", "schreibdatum", "gesamtbetrag"):
            self.assertIn(feld, schema_arg)


if __name__ == "__main__":
    unittest.main()
