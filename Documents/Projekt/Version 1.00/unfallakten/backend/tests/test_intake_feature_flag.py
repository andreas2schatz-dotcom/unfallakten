"""
Tests fuer den zentralen Umschalt-Flag INTAKE_REVIEW_PFLICHT (S1.9a).

Der Flag steuert, ob die Auto-Pfade (import_service Schritt 13,
upload_service Auto-Import, etc.) noch aktiv sind. Default TRUE ab S1.9
(BREAKING). Setzt der Betreiber INTAKE_REVIEW_PFLICHT=false, laufen die
Alt-Pfade weiter (Rollback-Anker).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestFeatureFlag(unittest.TestCase):
    def setUp(self):
        self._alt = os.environ.get("INTAKE_REVIEW_PFLICHT")

    def tearDown(self):
        if self._alt is None:
            os.environ.pop("INTAKE_REVIEW_PFLICHT", None)
        else:
            os.environ["INTAKE_REVIEW_PFLICHT"] = self._alt

    def test_default_ist_true(self):
        os.environ.pop("INTAKE_REVIEW_PFLICHT", None)
        from backend.intake.feature_flags import review_pflicht_aktiv
        self.assertTrue(review_pflicht_aktiv())

    def test_false_wird_erkannt(self):
        for wert in ("false", "0", "no", "False", "NO", "off"):
            os.environ["INTAKE_REVIEW_PFLICHT"] = wert
            from backend.intake.feature_flags import review_pflicht_aktiv
            self.assertFalse(review_pflicht_aktiv(),
                             f"Wert {wert!r} sollte False sein")

    def test_true_wird_erkannt(self):
        for wert in ("true", "1", "yes", "on", "True"):
            os.environ["INTAKE_REVIEW_PFLICHT"] = wert
            from backend.intake.feature_flags import review_pflicht_aktiv
            self.assertTrue(review_pflicht_aktiv(),
                            f"Wert {wert!r} sollte True sein")


if __name__ == "__main__":
    unittest.main()
