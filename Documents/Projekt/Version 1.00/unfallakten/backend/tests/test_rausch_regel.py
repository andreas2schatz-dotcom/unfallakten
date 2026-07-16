"""Tests fuer backend/intake/rausch_regel.py (Rausch-Absender-Regel)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.intake import rausch_regel


def _schreibe_yaml(inhalt: str) -> str:
    fd, pfad = tempfile.mkstemp(suffix=".yaml")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(inhalt)
    return pfad


class TestPolicyFuerDomain(unittest.TestCase):
    def test_placetel_ist_nur_body(self):
        self.assertEqual(rausch_regel.policy_fuer_domain("placetel.de"), "nur_body")

    def test_bea_ist_komplett(self):
        self.assertEqual(rausch_regel.policy_fuer_domain("bea-brak.de"), "komplett")

    def test_grossschreibung_egal(self):
        self.assertEqual(rausch_regel.policy_fuer_domain("Placetel.DE"), "nur_body")

    def test_unbekannte_domain_none(self):
        self.assertIsNone(rausch_regel.policy_fuer_domain("versicherung.de"))

    def test_none_domain_none(self):
        self.assertIsNone(rausch_regel.policy_fuer_domain(None))
        self.assertIsNone(rausch_regel.policy_fuer_domain(""))


class TestLadeRegeln(unittest.TestCase):
    def test_gueltige_yaml(self):
        pfad = _schreibe_yaml(
            "- domain: a.de\n  policy: nur_body\n"
            "- domain: b.de\n  policy: komplett\n"
        )
        self.addCleanup(os.remove, pfad)
        regeln = rausch_regel.lade_regeln(pfad, reload=True)
        self.assertEqual(regeln, {"a.de": "nur_body", "b.de": "komplett"})

    def test_unbekannte_policy_wirft(self):
        pfad = _schreibe_yaml("- domain: a.de\n  policy: quatsch\n")
        self.addCleanup(os.remove, pfad)
        with self.assertRaises(RuntimeError):
            rausch_regel.lade_regeln(pfad, reload=True)

    def test_doppelte_domain_wirft(self):
        pfad = _schreibe_yaml(
            "- domain: a.de\n  policy: nur_body\n"
            "- domain: a.de\n  policy: komplett\n"
        )
        self.addCleanup(os.remove, pfad)
        with self.assertRaises(RuntimeError):
            rausch_regel.lade_regeln(pfad, reload=True)

    def test_fehlendes_feld_wirft(self):
        pfad = _schreibe_yaml("- domain: a.de\n")
        self.addCleanup(os.remove, pfad)
        with self.assertRaises(RuntimeError):
            rausch_regel.lade_regeln(pfad, reload=True)

    def test_wurzel_kein_list_wirft(self):
        pfad = _schreibe_yaml("domain: a.de\npolicy: nur_body\n")
        self.addCleanup(os.remove, pfad)
        with self.assertRaises(RuntimeError):
            rausch_regel.lade_regeln(pfad, reload=True)

    def test_standard_registry_laedt(self):
        regeln = rausch_regel.lade_regeln(rausch_regel.standard_pfad(), reload=True)
        self.assertEqual(regeln.get("placetel.de"), "nur_body")
        self.assertEqual(regeln.get("bea-brak.de"), "komplett")


class TestAppStartFailLoud(unittest.TestCase):
    """Fix 2: Rausch-Registry muss beim App-Start fail-loud sein, nicht erst
    bei der ersten E-Mail (siehe backend/app.py, erstelle_app)."""

    def setUp(self):
        fd, self._pfad = tempfile.mkstemp(suffix=".yaml")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("- domain: a.de\n  policy: quatsch\n")
        os.environ["INTAKE_RAUSCH_REGISTRY_PFAD"] = self._pfad
        os.environ["FLASK_SECRET_KEY"] = "test-app-start-rausch"
        self.addCleanup(os.remove, self._pfad)
        self.addCleanup(os.environ.pop, "INTAKE_RAUSCH_REGISTRY_PFAD", None)
        self.addCleanup(os.environ.pop, "FLASK_SECRET_KEY", None)

    def test_defekte_rausch_registry_bricht_app_start_ab(self):
        from backend.app import erstelle_app
        with self.assertRaises(RuntimeError) as ctx:
            erstelle_app(test_config={"TESTING": True})
        self.assertIn("quatsch", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
