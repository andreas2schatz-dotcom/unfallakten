"""
Unit-Tests fuer die S1.6b-Erweiterungen von llm_service.py:

* klassifiziere_geschlossen(labels, text) -> (label, konfidenz)
* extrahiere_nach_schema(schema, text)    -> dict oder None

Beide Funktionen kapseln einen LLM-Call. Die Tests patchen ``_post_chat``,
damit KEIN Netzwerkzugriff stattfindet.
"""
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestKlassifiziereGeschlossen(unittest.TestCase):
    def test_gibt_label_und_konfidenz_zurueck_bei_gueltigem_json(self):
        from backend.services import llm_service

        antwort = json.dumps({"label": "abrechnungsschreiben", "konfidenz": 0.87})
        with mock.patch.object(llm_service, "_post_chat", return_value=antwort):
            label, konfidenz = llm_service.klassifiziere_geschlossen(
                labels=["abrechnungsschreiben", "gutachten", "rechnung"],
                text="Regulierungsschreiben ...",
            )
        self.assertEqual(label, "abrechnungsschreiben")
        self.assertAlmostEqual(konfidenz, 0.87, places=4)

    def test_liefert_none_wenn_llm_leer(self):
        from backend.services import llm_service
        with mock.patch.object(llm_service, "_post_chat", return_value=None):
            label, konfidenz = llm_service.klassifiziere_geschlossen(
                labels=["a", "b"], text="egal"
            )
        self.assertIsNone(label)
        self.assertEqual(konfidenz, 0.0)

    def test_ignoriert_label_das_nicht_in_labels_ist(self):
        # Model halluziniert ein Label ausserhalb der geschlossenen Liste ->
        # Rueckgabe muss None sein, damit die Pipeline auf Kandidaten fallback.
        from backend.services import llm_service
        antwort = json.dumps({"label": "fantasieklasse", "konfidenz": 0.99})
        with mock.patch.object(llm_service, "_post_chat", return_value=antwort):
            label, konfidenz = llm_service.klassifiziere_geschlossen(
                labels=["abrechnungsschreiben"], text="egal"
            )
        self.assertIsNone(label)
        self.assertEqual(konfidenz, 0.0)

    def test_umgeht_json_syntaxmuell(self):
        from backend.services import llm_service
        with mock.patch.object(llm_service, "_post_chat", return_value="kein json"):
            label, konfidenz = llm_service.klassifiziere_geschlossen(
                labels=["a"], text="egal"
            )
        self.assertIsNone(label)
        self.assertEqual(konfidenz, 0.0)

    def test_labels_werden_dem_llm_uebergeben(self):
        # Der Prompt an das LLM muss die vollstaendige Labelliste enthalten,
        # sonst ist die "geschlossene" Klassifikation nicht geschlossen.
        from backend.services import llm_service
        antwort = json.dumps({"label": "b", "konfidenz": 0.5})
        with mock.patch.object(llm_service, "_post_chat",
                               return_value=antwort) as m:
            llm_service.klassifiziere_geschlossen(
                labels=["a", "b", "c"], text="Text zum Klassifizieren."
            )
        _, kwargs = m.call_args
        args = m.call_args.args
        messages = args[0] if args else kwargs.get("messages", [])
        prompt = "\n".join(msg.get("content", "") for msg in messages)
        for label in ["a", "b", "c"]:
            self.assertIn(label, prompt, f"Label {label!r} fehlt im Prompt")


class TestExtrahiereNachSchema(unittest.TestCase):
    def test_gibt_dict_zurueck_wenn_llm_valides_json_liefert(self):
        from backend.services import llm_service
        antwort = json.dumps({
            "schadennummer": "12-345",
            "gesamtbetrag": 7280.00,
        })
        with mock.patch.object(llm_service, "_post_chat", return_value=antwort):
            ergebnis = llm_service.extrahiere_nach_schema(
                schema={"schadennummer": "string", "gesamtbetrag": "number"},
                text="Schadennummer: 12-345 Gesamtbetrag 7.280,00 EUR",
            )
        self.assertEqual(ergebnis, {"schadennummer": "12-345",
                                    "gesamtbetrag": 7280.00})

    def test_gibt_none_zurueck_bei_leerem_llm(self):
        from backend.services import llm_service
        with mock.patch.object(llm_service, "_post_chat", return_value=None):
            self.assertIsNone(
                llm_service.extrahiere_nach_schema(
                    schema={"x": "string"}, text="egal"
                )
            )

    def test_gibt_none_zurueck_bei_muell(self):
        from backend.services import llm_service
        with mock.patch.object(llm_service, "_post_chat",
                               return_value="das ist kein json"):
            self.assertIsNone(
                llm_service.extrahiere_nach_schema(
                    schema={"x": "string"}, text="egal"
                )
            )

    def test_feldbeschreibungen_landen_im_prompt(self):
        # Schema-Werte duerfen statt reiner Typangabe ein Mapping
        # {typ, beschreibung} sein -- die Beschreibung steuert das LLM
        # (Befund 1280/25: abzug_gesamt wurde frei errechnet).
        from backend.services import llm_service
        with mock.patch.object(llm_service, "_post_chat",
                               return_value='{"abzug_gesamt": 1}') as m:
            llm_service.extrahiere_nach_schema(
                schema={
                    "abzug_gesamt": {
                        "typ": "number",
                        "beschreibung": "nur uebernehmen wenn ausgewiesen",
                    },
                    "vorgangsnummer": "string",
                },
                text="Text",
            )
        args = m.call_args.args
        messages = args[0] if args else m.call_args.kwargs.get("messages", [])
        prompt = "\n".join(msg.get("content", "") for msg in messages)
        self.assertIn(
            "abzug_gesamt (number): nur uebernehmen wenn ausgewiesen", prompt)
        self.assertIn("vorgangsnummer (string)", prompt)
        self.assertNotIn("{'typ'", prompt)

    def test_systemprompt_verbietet_eigenes_rechnen(self):
        from backend.services import llm_service
        with mock.patch.object(llm_service, "_post_chat",
                               return_value='{"a": 1}') as m:
            llm_service.extrahiere_nach_schema(
                schema={"a": "number"}, text="Text")
        args = m.call_args.args
        messages = args[0] if args else m.call_args.kwargs.get("messages", [])
        prompt = "\n".join(msg.get("content", "") for msg in messages)
        self.assertIn("Errechne keine Werte", prompt)

    def test_schema_felder_landen_im_prompt(self):
        from backend.services import llm_service
        with mock.patch.object(llm_service, "_post_chat",
                               return_value='{"a": 1}') as m:
            llm_service.extrahiere_nach_schema(
                schema={"schadennummer": "string", "gesamtbetrag": "number"},
                text="Text",
            )
        args = m.call_args.args
        messages = args[0] if args else m.call_args.kwargs.get("messages", [])
        prompt = "\n".join(msg.get("content", "") for msg in messages)
        self.assertIn("schadennummer", prompt)
        self.assertIn("gesamtbetrag", prompt)


if __name__ == "__main__":
    unittest.main()
