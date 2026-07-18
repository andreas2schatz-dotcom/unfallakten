"""
PRD-33 Session 3 (KW-06/15/16/21): Reine Grammatik-Helfer in klage_service.
"""
import unittest

from backend.word.klage_service import (
    _anrede_norm,
    _ist_maennliche_privatperson,
    _rechtsform_klasse,
    _funktion_aus_rechtsform_str,
    _vertretungs_hinweis,
    _beklagten_grammatik,
    _beklagten_rolle,
    _vertreter_suffix,
)
from backend.word.sg_text_builder import baue_sg_abschnitt


class TestAnredeNorm(unittest.TestCase):
    def test_numerisch_und_klartext(self):
        self.assertEqual(_anrede_norm("1"), "herr")
        self.assertEqual(_anrede_norm("2"), "frau")
        self.assertEqual(_anrede_norm("Herr"), "herr")
        self.assertEqual(_anrede_norm("Herrn"), "herr")
        self.assertEqual(_anrede_norm("FRAU"), "frau")
        self.assertEqual(_anrede_norm(""), "")
        self.assertEqual(_anrede_norm(None), "")
        self.assertEqual(_anrede_norm("Firma"), "")


class TestMaennlichePrivatperson(unittest.TestCase):
    def test_herr_ohne_firma(self):
        self.assertTrue(_ist_maennliche_privatperson({"name": "Huber", "anrede": "1"}))
        self.assertTrue(_ist_maennliche_privatperson({"name": "Huber", "anrede": "Herr"}))

    def test_firma_oder_versicherung_nie_maennlich(self):
        self.assertFalse(_ist_maennliche_privatperson({"firma": "Muster GmbH", "anrede": "1"}))
        self.assertFalse(_ist_maennliche_privatperson({"versicherung": "Test AG", "anrede": "1"}))

    def test_frau_oder_unbekannt(self):
        self.assertFalse(_ist_maennliche_privatperson({"name": "Meier", "anrede": "2"}))
        self.assertFalse(_ist_maennliche_privatperson({"name": "Meier"}))


class TestRechtsformKlasse(unittest.TestCase):
    def test_kw21_ug_nicht_in_fahrzeugbau(self):
        self.assertEqual(_rechtsform_klasse("Autohaus Fahrzeugbau"), "sonstige")

    def test_kw21_bindestrich_ag(self):
        self.assertEqual(_rechtsform_klasse("Allianz Versicherungs-AG"), "vorstand")

    def test_gf_formen(self):
        self.assertEqual(_rechtsform_klasse("Fahrzeugbau Müller GmbH"), "gf")
        self.assertEqual(_rechtsform_klasse("Muster UG (haftungsbeschränkt)"), "gf")
        self.assertEqual(_rechtsform_klasse("Spedition Krause GmbH & Co. KG"), "gf")
        self.assertEqual(_rechtsform_klasse("Bau OHG"), "gf")
        self.assertEqual(_rechtsform_klasse("Praxis GbR"), "gf")

    def test_vorstand_formen(self):
        self.assertEqual(_rechtsform_klasse("Muster AG"), "vorstand")
        self.assertEqual(_rechtsform_klasse("Muster SE"), "vorstand")
        self.assertEqual(_rechtsform_klasse("Muster KGaA"), "vorstand")
        self.assertEqual(_rechtsform_klasse("Sportfreunde e.V."), "vorstand")

    def test_se_nicht_in_hanse(self):
        self.assertEqual(_rechtsform_klasse("HANSE SPEDITION GMBH"), "gf")
        self.assertEqual(_rechtsform_klasse("HANSE SPEDITION"), "sonstige")

    def test_wrapper_funktionen(self):
        self.assertEqual(_funktion_aus_rechtsform_str("Muster GmbH"), "Geschäftsführer")
        self.assertEqual(_funktion_aus_rechtsform_str("Versicherungs-AG"), "Vorstand")
        self.assertEqual(_funktion_aus_rechtsform_str("Autohaus Fahrzeugbau"),
                         "gesetzlichen Vertreter")
        self.assertEqual(_vertretungs_hinweis("Muster GmbH"),
                         "– vertreten durch den/die Geschäftsführer –")
        self.assertEqual(_vertretungs_hinweis("Versicherungs-AG"),
                         "– vertreten durch den Vorstand –")
        self.assertEqual(_vertretungs_hinweis("Autohaus Fahrzeugbau"),
                         "– vertreten durch den gesetzlichen Vertreter –")


class TestBeklagtenGrammatik(unittest.TestCase):
    VERS = {"versicherung": "Test-Versicherung AG"}
    MANN = {"name": "Huber", "vorname": "Hans", "anrede": "1"}
    FRAU = {"name": "Meier", "vorname": "Eva", "anrede": "2"}

    def test_mehrere_gesamtschuldner(self):
        g = _beklagten_grammatik([self.VERS, self.MANN])
        self.assertEqual(g["verurteilt"], "Die Beklagten werden als Gesamtschuldner verurteilt")
        self.assertEqual(g["verpflichtet"], "die Beklagten als Gesamtschuldner verpflichtet sind")
        self.assertEqual(g["kosten"], "Die Beklagten tragen die Kosten des Rechtsstreits.")
        self.assertEqual(g["nom_klein"], "die Beklagten")
        self.assertEqual(g["haftet"], "haften")

    def test_einzeln_versicherung_wie_bisher(self):
        g = _beklagten_grammatik([self.VERS])
        self.assertEqual(g["verurteilt"], "Die Beklagte wird verurteilt")
        self.assertEqual(g["kosten"], "Die Beklagte trägt die Kosten des Rechtsstreits.")
        self.assertEqual(g["haftet"], "haftet")

    def test_einzeln_maennlich(self):
        g = _beklagten_grammatik([self.MANN])
        self.assertEqual(g["verurteilt"], "Der Beklagte wird verurteilt")
        self.assertEqual(g["verpflichtet"], "der Beklagte verpflichtet ist")
        self.assertEqual(g["kosten"], "Der Beklagte trägt die Kosten des Rechtsstreits.")
        self.assertEqual(g["nom_klein"], "der Beklagte")

    def test_leere_liste_wie_einzeln_feminin(self):
        g = _beklagten_grammatik([])
        self.assertEqual(g["verurteilt"], "Die Beklagte wird verurteilt")

    def test_rolle(self):
        self.assertEqual(_beklagten_rolle(self.MANN), "Beklagter")
        self.assertEqual(_beklagten_rolle(self.FRAU), "Beklagte")
        self.assertEqual(_beklagten_rolle(self.VERS), "Beklagte")


class TestVertreterSuffix(unittest.TestCase):
    def test_kw16_feminine_funktion(self):
        self.assertEqual(
            _vertreter_suffix("Geschäftsführerin", "Erika Musterfrau", "Muster GmbH"),
            ", vertreten durch die Geschäftsführerin Frau Erika Musterfrau",
        )

    def test_maskuline_funktion(self):
        self.assertEqual(
            _vertreter_suffix("Geschäftsführer", "Max Mustermann", "Muster GmbH"),
            ", vertreten durch den Geschäftsführer Herrn Max Mustermann",
        )

    def test_vorsitzende_feminin(self):
        self.assertEqual(
            _vertreter_suffix("Vorstandsvorsitzende", "Erika Musterfrau", "Muster AG"),
            ", vertreten durch die Vorstandsvorsitzende Frau Erika Musterfrau",
        )

    def test_kw16_leere_funktion_keine_anrede_geraten(self):
        s = _vertreter_suffix("", "Erika Musterfrau", "Muster GmbH")
        self.assertEqual(s, ", vertreten durch den Geschäftsführer Erika Musterfrau")
        self.assertNotIn("Herrn", s)
        self.assertNotIn("Frau ", s)

    def test_ohne_name(self):
        self.assertEqual(_vertreter_suffix("", "", "Muster AG"),
                         ", vertreten durch den Vorstand")


class TestSgTextBuilderNumerus(unittest.TestCase):
    def test_default_singular(self):
        absaetze, _, _ = baue_sg_abschnitt({}, "Der Kläger", 0.0)
        self.assertTrue(absaetze[0].startswith("Der Kläger hat durch den Unfall"))

    def test_plural_verb(self):
        absaetze, _, _ = baue_sg_abschnitt({}, "Die Kläger", 0.0, verb_hat="haben")
        self.assertTrue(absaetze[0].startswith("Die Kläger haben durch den Unfall"))

    def test_plural_mit_verletzungen(self):
        absaetze, _, _ = baue_sg_abschnitt(
            {"verletzungen_text": "HWS-Distorsion"}, "Die Kläger", 0.0, verb_hat="haben")
        self.assertIn("Die Kläger haben durch den Unfall folgende Verletzungen "
                      "erlitten: HWS-Distorsion.", absaetze[0])


class TestKW12SgBuilderDefaultAnlage(unittest.TestCase):
    def test_kw12_sg_builder_default_anlage_bleibt_k2(self):
        absaetze, beweis, _vgl = baue_sg_abschnitt(None, "Die Klägerin", 0.0)
        self.assertTrue(beweis.endswith("(Anlage K 2)"))


if __name__ == "__main__":
    unittest.main()
