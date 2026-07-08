"""
Regressions-Guard: test_prd23b.py darf sys.modules nicht auf Modul-Ebene
kontaminieren.

Historisch schrieb test_prd23b.py auf Import-Zeit Stub-Module fuer
pdfplumber/flask/werkzeug/jwt in ``sys.modules``, ohne sie in einem
teardown zurueckzunehmen. Sobald test_prd23b.py in der pytest-Sammelphase
VOR einem Test importiert wurde, dessen Modul echtes pdfplumber/flask
brauchte, sah der spaetere Test nur die Attrappe -- Massenfails in
test_sv_portal, test_modul8, test_s16a/b_e2e u. a.

Wir prueflen den Modul-Text statisch: die kontaminierenden Zeilen duerfen
nicht mehr existieren. Dieser Test ist bewusst statisch, damit er nicht
selbst von der Kontamination betroffen ist, die er prueft.
"""
import os
import re
import unittest


PRD23B_PFAD = os.path.join(os.path.dirname(__file__), "test_prd23b.py")


class TestPrd23bKontaminiertSysModulesNicht(unittest.TestCase):
    def test_datei_existiert(self):
        self.assertTrue(os.path.isfile(PRD23B_PFAD),
                        f"test_prd23b.py fehlt: {PRD23B_PFAD}")

    def test_kein_globaler_sys_modules_stub(self):
        with open(PRD23B_PFAD, "r", encoding="utf-8") as f:
            quelltext = f.read()

        # Kontaminierendes Muster: sys.modules[irgendwas] = _stub(...) oder
        # sys.modules.setdefault(...) auf Modulebene. Wir suchen absichtlich
        # etwas breit, damit auch Varianten (mit/ohne setdefault, mit
        # Klammern) erkannt werden.
        muster_zuweisung = re.compile(
            r"^\s*sys\.modules\[[^\]]+\]\s*=", re.MULTILINE,
        )
        muster_setdefault = re.compile(
            r"^\s*sys\.modules\.setdefault\s*\(", re.MULTILINE,
        )

        treffer = (muster_zuweisung.findall(quelltext)
                   + muster_setdefault.findall(quelltext))
        self.assertEqual(
            treffer, [],
            "test_prd23b.py schreibt auf Modul-Ebene in sys.modules und "
            "kontaminiert damit alle nachfolgend importierten Tests. "
            "Nutze installierte Dependencies (pdfplumber, flask, werkzeug, "
            "jwt sind alle in requirements.txt) statt Stubs.",
        )


if __name__ == "__main__":
    unittest.main()
