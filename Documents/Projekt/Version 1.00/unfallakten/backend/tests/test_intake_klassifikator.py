"""
Unit-Tests fuer backend/intake/klassifikator.py (S1.6b).

Stufe 1 -- Regeln ueber VEREINIGTE Zustellungssignale + YAML-Marker.
Stufe 2 -- LLM (Qwen) mit geschlossener Labelliste (Seite 1 + letzte Seite,
je ~3000 Zeichen gekuerzt, F-11 aus freigabe.md).

LLM-Aufrufe sind gemockt -- keine Netzwerkzugriffe im Test.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _mini_registry():
    """Minimale Registry-Attrappe fuer Unit-Tests (kein YAML noetig)."""
    from backend.intake.registry_loader import Registry
    klassen = {
        "abrechnungsschreiben": {
            "klasse": "abrechnungsschreiben",
            "marker": ["Regulierungsschreiben", "HDI Global"],
            "regex_felder": {},
            "schema": {},
            "pflichtfelder": [],
            "kritische_felder": [],
            "validierungsregeln": [],
            "fristrelevanz": True,
            "loeschfrist_jahre": 6,
        },
        "gutachten": {
            "klasse": "gutachten",
            "marker": ["Sachverstaendigengutachten", "Wiederbeschaffungswert"],
            "regex_felder": {},
            "schema": {},
            "pflichtfelder": [],
            "kritische_felder": [],
            "validierungsregeln": [],
            "fristrelevanz": False,
            "loeschfrist_jahre": 6,
        },
        "sonstiges": {
            "klasse": "sonstiges",
            "marker": [],
            "regex_felder": {},
            "schema": {},
            "pflichtfelder": [],
            "kritische_felder": [],
            "validierungsregeln": [],
            "fristrelevanz": False,
            "loeschfrist_jahre": 6,
        },
    }
    return Registry(version="test", klassen=klassen, pfad="")


class TestStufe1(unittest.TestCase):
    def test_marker_treffer_erzeugt_kandidaten(self):
        from backend.intake.klassifikator import klassifiziere_stufe1
        registry = _mini_registry()
        text = "Regulierungsschreiben von HDI Global zu ..."
        kandidaten, hinweise = klassifiziere_stufe1(text, [], registry)
        klassen = [k.klasse for k in kandidaten]
        self.assertIn("abrechnungsschreiben", klassen)
        # Konfidenz durch 2 Marker sollte hoeher sein als bei einem
        top = next(k for k in kandidaten if k.klasse == "abrechnungsschreiben")
        self.assertGreater(top.konfidenz, 0.75)

    def test_ohne_treffer_liefert_leere_kandidaten(self):
        from backend.intake.klassifikator import klassifiziere_stufe1
        registry = _mini_registry()
        text = "Guten Tag, dies ist ein irrelevanter Text."
        kandidaten, _ = klassifiziere_stufe1(text, [], registry)
        self.assertEqual(kandidaten, [])

    def test_signal_allein_ist_niemals_eindeutig(self):
        """Vererbte Signale (Absender/Domain/Kategorie) sind nur KANDIDATEN --
        nie allein eindeutig (Konfidenz max. 0.6, freigabe.md K-P3)."""
        from backend.intake.klassifikator import klassifiziere_stufe1
        registry = _mini_registry()
        signale = [{"klasse_kandidat": "abrechnungsschreiben",
                    "absender_kategorie": "versicherer"}]
        kandidaten, _ = klassifiziere_stufe1("Kein Marker hier drin.",
                                             signale, registry)
        self.assertEqual(len(kandidaten), 1)
        self.assertEqual(kandidaten[0].klasse, "abrechnungsschreiben")
        self.assertLessEqual(kandidaten[0].konfidenz, 0.6)
        self.assertEqual(kandidaten[0].quelle, "signal")

    def test_marker_plus_signal_erhoeht_konfidenz(self):
        from backend.intake.klassifikator import klassifiziere_stufe1
        registry = _mini_registry()
        signale = [{"klasse_kandidat": "abrechnungsschreiben"}]
        text = "Regulierungsschreiben ..."

        nur_marker, _ = klassifiziere_stufe1(text, [], registry)
        marker_plus_signal, _ = klassifiziere_stufe1(text, signale, registry)

        k_marker = next(k for k in nur_marker
                        if k.klasse == "abrechnungsschreiben").konfidenz
        k_kombi = next(k for k in marker_plus_signal
                       if k.klasse == "abrechnungsschreiben").konfidenz
        self.assertGreater(k_kombi, k_marker)

    def test_vereinigte_signale_aus_mehreren_zustellungen(self):
        """Freigabe K-P3: Signale VEREINIGT ueber alle Zustellungen."""
        from backend.intake.klassifikator import klassifiziere_stufe1
        registry = _mini_registry()
        signale = [
            {"klasse_kandidat": "abrechnungsschreiben"},
            {"klasse_kandidat": "gutachten"},
        ]
        kandidaten, _ = klassifiziere_stufe1("neutraler Text", signale,
                                             registry)
        klassen = {k.klasse for k in kandidaten}
        self.assertEqual(klassen,
                         {"abrechnungsschreiben", "gutachten"})

    def test_kandidaten_sind_absteigend_sortiert(self):
        from backend.intake.klassifikator import klassifiziere_stufe1
        registry = _mini_registry()
        # 2 Marker fuer abrechnungsschreiben, 1 fuer gutachten
        text = ("Regulierungsschreiben HDI Global -- "
                "Wiederbeschaffungswert 12.500 EUR")
        kandidaten, _ = klassifiziere_stufe1(text, [], registry)
        self.assertGreaterEqual(len(kandidaten), 2)
        for a, b in zip(kandidaten, kandidaten[1:]):
            self.assertGreaterEqual(a.konfidenz, b.konfidenz)


class TestStufe2(unittest.TestCase):
    def test_llm_ergebnis_wird_zurueckgegeben(self):
        from backend.intake import klassifikator
        with mock.patch(
            "backend.intake.klassifikator.llm_service.klassifiziere_geschlossen",
            return_value=("abrechnungsschreiben", 0.9),
        ):
            klasse, konf = klassifikator.klassifiziere_stufe2(
                text_seite1="Regulierungsschreiben...",
                text_letzte_seite="Mit freundlichen Gruessen",
                kandidaten=[],
                labels=["abrechnungsschreiben", "gutachten", "sonstiges"],
            )
        self.assertEqual(klasse, "abrechnungsschreiben")
        self.assertEqual(konf, 0.9)

    def test_seiten_werden_auf_3000_zeichen_gekuerzt(self):
        """F-11: Pro Seite auf ~3000 Zeichen kuerzen."""
        from backend.intake import klassifikator
        lang = "X" * 10000
        with mock.patch(
            "backend.intake.klassifikator.llm_service.klassifiziere_geschlossen",
            return_value=("sonstiges", 0.5),
        ) as m:
            klassifikator.klassifiziere_stufe2(
                text_seite1=lang, text_letzte_seite=lang,
                kandidaten=[], labels=["sonstiges"],
            )
        _, kwargs = m.call_args
        args = m.call_args.args
        text_arg = args[1] if len(args) >= 2 else kwargs.get("text", "")
        # Beide Seiten zusammen sollten deutlich unter 2 * 10000 sein
        self.assertLess(len(text_arg), 2 * 3200)

    def test_fallback_auf_besten_kandidaten_wenn_llm_none(self):
        from backend.intake import klassifikator
        from backend.intake.klassifikator import Kandidat
        with mock.patch(
            "backend.intake.klassifikator.llm_service.klassifiziere_geschlossen",
            return_value=(None, 0.0),
        ):
            klasse, konf = klassifikator.klassifiziere_stufe2(
                text_seite1="egal", text_letzte_seite="",
                kandidaten=[
                    Kandidat("gutachten", 0.8, "marker"),
                    Kandidat("abrechnungsschreiben", 0.6, "marker"),
                ],
                labels=["abrechnungsschreiben", "gutachten", "sonstiges"],
            )
        self.assertEqual(klasse, "gutachten")
        self.assertEqual(konf, 0.8)

    def test_fallback_sonstiges_wenn_llm_none_und_keine_kandidaten(self):
        from backend.intake import klassifikator
        with mock.patch(
            "backend.intake.klassifikator.llm_service.klassifiziere_geschlossen",
            return_value=(None, 0.0),
        ):
            klasse, konf = klassifikator.klassifiziere_stufe2(
                text_seite1="egal", text_letzte_seite="",
                kandidaten=[],
                labels=["abrechnungsschreiben", "sonstiges"],
            )
        self.assertEqual(klasse, "sonstiges")
        self.assertLessEqual(konf, 0.5)


if __name__ == "__main__":
    unittest.main()
