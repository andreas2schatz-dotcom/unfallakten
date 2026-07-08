"""
Fail-Loud beim App-Start (S1.5).

Anforderungen aus Handover:
  * Loader mit Fail-Loud beim App-Start (RuntimeError -> app.py bricht ab,
    ERROR-Log).
  * Ein absichtlich defektes YAML in einer Test-Kopie -> Loader wirft,
    App-Start schlaegt fehl.
"""
import os
import sys
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestAppStartFailLoud(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="app_start_test_")
        # Env-Var zeigt auf tmpdir -> App laedt Registry von dort
        os.environ["INTAKE_REGISTRY_PFAD"] = self._tmp
        os.environ["FLASK_SECRET_KEY"] = "test-app-start"

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)
        os.environ.pop("INTAKE_REGISTRY_PFAD", None)

    def test_defektes_yaml_bricht_app_start_ab(self):
        # Ein YAML mit Syntax-Fehler
        pfad = os.path.join(self._tmp, "gutachten.yaml")
        with open(pfad, "w", encoding="utf-8") as f:
            f.write("klasse: gutachten\n  invalid: [nicht: geschlossen\n")

        from backend.app import erstelle_app
        with self.assertRaises(RuntimeError) as ctx:
            erstelle_app(test_config={"TESTING": True})
        self.assertIn("gutachten.yaml", str(ctx.exception))

    def test_leeres_verzeichnis_bricht_app_start_ab(self):
        from backend.app import erstelle_app
        with self.assertRaises(RuntimeError):
            erstelle_app(test_config={"TESTING": True})


if __name__ == "__main__":
    unittest.main()
