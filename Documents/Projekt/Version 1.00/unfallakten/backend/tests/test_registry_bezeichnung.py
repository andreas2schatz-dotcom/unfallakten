"""PRD-37: Registry-Loader akzeptiert optionale label/bezeichnung_felder."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.intake.registry_loader import lade_registry

_MINIMAL = """
klasse: {name}
marker: []
regex_felder: {{}}
schema: {{}}
pflichtfelder: []
kritische_felder: []
validierungsregeln: []
fristrelevanz: false
loeschfrist_jahre: 6
"""


def _schreibe(dir_, name, extra=""):
    with open(os.path.join(dir_, f"{name}.yaml"), "w", encoding="utf-8") as f:
        f.write(_MINIMAL.format(name=name) + extra)


class TestBezeichnungFelder(unittest.TestCase):
    def test_optionale_felder_werden_geladen(self):
        d = tempfile.mkdtemp(prefix="reg_bez_")
        _schreibe(d, "rechnung",
                  "label: Rechnung\n"
                  "bezeichnung_felder:\n"
                  "  aussteller: aussteller\n"
                  "  datum: rechnungsdatum\n"
                  "  betrag: bruttobetrag\n")
        reg = lade_registry(d, reload=True)
        r = reg.klassen["rechnung"]
        self.assertEqual(r["label"], "Rechnung")
        self.assertEqual(r["bezeichnung_felder"]["datum"], "rechnungsdatum")

    def test_ohne_optionale_felder_weiter_gueltig(self):
        d = tempfile.mkdtemp(prefix="reg_bez2_")
        _schreibe(d, "sonstiges")
        reg = lade_registry(d, reload=True)
        self.assertNotIn("label", reg.klassen["sonstiges"])

    def test_label_falscher_typ_faellt_auf(self):
        d = tempfile.mkdtemp(prefix="reg_bez3_")
        _schreibe(d, "rechnung", "label: [1, 2]\n")
        with self.assertRaises(RuntimeError):
            lade_registry(d, reload=True)

    def test_bezeichnung_felder_falscher_typ_faellt_auf(self):
        d = tempfile.mkdtemp(prefix="reg_bez4_")
        _schreibe(d, "rechnung", "bezeichnung_felder: nichtsdict\n")
        with self.assertRaises(RuntimeError):
            lade_registry(d, reload=True)

    def test_unbekannte_rolle_faellt_auf(self):
        d = tempfile.mkdtemp(prefix="reg_bez5_")
        _schreibe(d, "rechnung", "bezeichnung_felder:\n  empfaenger: foo\n")
        with self.assertRaises(RuntimeError):
            lade_registry(d, reload=True)

    def test_leerer_rollen_wert_faellt_auf(self):
        d = tempfile.mkdtemp(prefix="reg_bez6_")
        _schreibe(d, "rechnung", "bezeichnung_felder:\n  aussteller: ''\n")
        with self.assertRaises(RuntimeError):
            lade_registry(d, reload=True)


if __name__ == "__main__":
    unittest.main()
