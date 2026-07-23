"""
Tests: Genus-Platzhalter (Weg 2, Phase-1-Nachtrag).
<PRON>/<POSS_EM>/<ANREDE> etc. aus RA-MICRO sAnrede bzw. Text-Anrede.
"""
import unittest
from types import SimpleNamespace


class TestBestimmeGeschlecht(unittest.TestCase):
    def _g(self, *a, **kw):
        from backend.word.forderungsschreiben_wv import bestimme_geschlecht
        return bestimme_geschlecht(*a, **kw)

    def test_numerische_codes(self):
        self.assertEqual(self._g("1"), "m")
        self.assertEqual(self._g("2"), "f")
        self.assertEqual(self._g("8"), "p")

    def test_text_anreden(self):
        self.assertEqual(self._g("Herr"), "m")
        self.assertEqual(self._g("Herrn"), "m")
        self.assertEqual(self._g("Frau"), "f")

    def test_firma_ev_maennlich_sonst_weiblich(self):
        self.assertEqual(self._g("4", name="ADAC e.V."), "m")
        self.assertEqual(self._g("4", name="Muster GmbH"), "f")

    def test_briefanrede_fallback(self):
        self.assertEqual(self._g("", briefanrede="Sehr geehrter Herr Muster,"), "m")
        self.assertEqual(self._g("", briefanrede="Sehr geehrte Frau Muster,"), "f")


class TestGenusPlatzhalter(unittest.TestCase):
    def _p(self, *a, **kw):
        from backend.word.stellungnahme_service import genus_platzhalter
        return genus_platzhalter(*a, **kw)

    def test_maennlich(self):
        p = self._p("1")
        self.assertEqual(p["ANREDE"], "Herr")
        self.assertEqual(p["ANREDE_DEKL"], "Herrn")
        self.assertEqual(p["PRON"], "er")
        self.assertEqual(p["PRON_DAT"], "ihm")
        self.assertEqual(p["PRON_AKK"], "ihn")
        self.assertEqual(p["POSS"], "sein")
        self.assertEqual(p["POSS_EM"], "seinem")
        self.assertEqual(p["POSS_ER"], "seiner")

    def test_weiblich(self):
        p = self._p("2")
        self.assertEqual(p["ANREDE"], "Frau")
        self.assertEqual(p["ANREDE_DEKL"], "Frau")
        self.assertEqual(p["PRON"], "sie")
        self.assertEqual(p["PRON_DAT"], "ihr")
        self.assertEqual(p["POSS_EM"], "ihrem")
        self.assertEqual(p["POSS_ES"], "ihres")

    def test_plural(self):
        p = self._p("8")
        self.assertEqual(p["PRON_DAT"], "ihnen")
        self.assertEqual(p["ANREDE"], "")

    def test_mandant_und_artikel_formen(self):
        m, f, p = self._p("1"), self._p("2"), self._p("8")
        self.assertEqual(m["MANDANT_NOM"], "Mandant")
        self.assertEqual(f["MANDANT_NOM"], "Mandantin")
        self.assertEqual(m["MANDANT_OBL"], "Mandanten")
        self.assertEqual(f["MANDANT_OBL"], "Mandantin")
        self.assertEqual(p["MANDANT_OBL"], "Mandanten")
        self.assertEqual(m["UNSER"], "unser")
        self.assertEqual(f["UNSER"], "unsere")
        self.assertEqual(m["UNSER_GROSS"], "Unser")
        self.assertEqual(m["UNSERES"], "unseres")
        self.assertEqual(f["UNSERES"], "unserer")
        self.assertEqual(m["UNSEREM"], "unserem")
        self.assertEqual(f["UNSEREM"], "unserer")
        self.assertEqual(m["PRON_GROSS"], "Er")
        self.assertEqual(f["PRON_GROSS"], "Sie")

    def test_alle_formen_in_beiden_genera(self):
        m, f = self._p("1"), self._p("2")
        self.assertEqual(set(m.keys()), set(f.keys()))
        self.assertEqual(len(m), 18)


class TestKontextIntegration(unittest.TestCase):
    def test_kontext_traegt_genus_formen_der_mandantin(self):
        from backend.word.stellungnahme_service import (
            _baue_kontext, ersetze_platzhalter)
        mandantin = SimpleNamespace(
            rolle="mandant", anrede="2", vorname="Eva", name="Muster",
            briefanrede="")
        kontext = _baue_kontext("971/25", SimpleNamespace(), [mandantin])
        self.assertEqual(kontext["PRON"], "sie")
        self.assertEqual(kontext["ANREDE"], "Frau")
        self.assertEqual(
            ersetze_platzhalter("Das Fahrzeug an <POSS_EM> Wohnort.", kontext),
            "Das Fahrzeug an ihrem Wohnort.")

    def test_kontext_ohne_mandant_maskuline_formen(self):
        from backend.word.stellungnahme_service import _baue_kontext
        kontext = _baue_kontext("971/25", SimpleNamespace(), [])
        self.assertEqual(kontext["PRON"], "er")
        self.assertEqual(kontext["POSS_EM"], "seinem")


class TestKatalog(unittest.TestCase):
    def test_genus_platzhalter_im_katalog(self):
        from backend.routers.kuerzungsarten_routes import PLATZHALTER_KATALOG
        keys = {p["key"] for p in PLATZHALTER_KATALOG}
        self.assertTrue({"ANREDE", "ANREDE_DEKL", "PRON", "PRON_DAT",
                         "PRON_AKK", "POSS", "POSS_E", "POSS_EM", "POSS_EN",
                         "POSS_ER", "POSS_ES", "MANDANT_NOM", "MANDANT_OBL",
                         "UNSER", "UNSER_GROSS", "UNSERES", "UNSEREM",
                         "PRON_GROSS"} <= keys)
        for p in PLATZHALTER_KATALOG:
            self.assertTrue(p["beschreibung"], p["key"])
            self.assertTrue(p["beispiel"], p["key"])


if __name__ == "__main__":
    unittest.main()
