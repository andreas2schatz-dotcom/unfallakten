import os
import tempfile
import unittest
import unittest.mock


class _DBBasis(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad
        from backend.db.schema_manager import init_db
        init_db()

    def tearDown(self):
        os.unlink(self._db_pfad)


class TestRegelMatching(_DBBasis):
    def _vorschlaege(self, text, klasse="pruefbericht"):
        from backend.services.kuerzungstyp_matching import schlage_typen_vor
        return schlage_typen_vor(text, dokumentklasse=klasse, llm_fallback=False)

    def test_wortgrenze_kleinteilepauschale_ist_A06_nicht_E06(self):
        codes = {v.typ_code for v in self._vorschlaege(
            "Die Kleinteilekostenpauschale in Höhe von 30,00 € wurde gekürzt.")}
        self.assertIn("A06", codes)
        self.assertNotIn("E06", codes)

    def test_kostenpauschale_allein_ist_E06(self):
        codes = {v.typ_code for v in self._vorschlaege(
            "Die Kostenpauschale erstatten wir mit 25,00 €.",
            klasse="abrechnungsschreiben")}
        self.assertIn("E06", codes)

    def test_kennzeichen_im_briefkopf_matcht_nicht(self):
        text = "Amtl. Kennzeichen: OF-AB 123\nSchaden-Nr. 4711\n" + "x" * 200
        self.assertEqual(self._vorschlaege(text), [])

    def test_kennzeichen_mit_schilder_kontext_matcht(self):
        codes = {v.typ_code for v in self._vorschlaege(
            "Die Kosten für die Erneuerung der Kennzeichen (Schilderkosten) "
            "kürzen wir auf 20,00 €.")}
        self.assertIn("E05b", codes)

    def test_neu_fuer_alt(self):
        codes = {v.typ_code for v in self._vorschlaege(
            "Wir nehmen einen Abzug neu für alt in Höhe von 200,00 € vor.")}
        self.assertIn("A07", codes)

    def test_snippet_liefert_begruendung_roh(self):
        v = self._vorschlaege("Vorlauf. " * 30 +
                              "Die Verbringungskosten sind nicht erforderlich. " +
                              "Nachlauf. " * 30)
        treffer = next(x for x in v if x.typ_code == "A02")
        self.assertIn("Verbringungskosten", treffer.snippet)
        self.assertLessEqual(len(treffer.snippet), 260)

    def test_zahlmitteilung_ohne_begruendung_liefert_nichts(self):
        self.assertEqual(
            self._vorschlaege("Verbringungskosten 50,00 €", klasse="gutachten"), [])

    def test_dedup_pro_typ(self):
        v = self._vorschlaege("Verbringung hier. Verbringungskosten dort.")
        self.assertEqual(len([x for x in v if x.typ_code == "A02"]), 1)

    def test_briefkopf_ohne_signal_wird_unterdrueckt(self):
        text = ("Wertminderung\nSchaden-Nr. 4711\nAmtl. Kennzeichen OF-AB 123\n"
                "Sachverhalt: " + "Fahrzeug am Werktag besichtigt. " * 30)
        self.assertGreater(len(text), 600)
        self.assertEqual(self._vorschlaege(text), [])


class TestLlmFallback(_DBBasis):
    def test_fallback_nur_wenn_regeln_leer(self):
        from backend.services import kuerzungstyp_matching as m
        aufrufe = []

        def fake_klassifiziere(labels, text):
            aufrufe.append(labels)
            return ("A02", 0.8)

        with unittest.mock.patch.object(
                m, "_klassifiziere_via_llm", side_effect=fake_klassifiziere):
            v = m.schlage_typen_vor(
                "Die Position wird nicht anerkannt, unklarer Grund.",
                dokumentklasse="pruefbericht", llm_fallback=True)
        self.assertEqual([x.typ_code for x in v], ["A02"])
        self.assertEqual(v[0].quelle, "llm")
        self.assertEqual(len(aufrufe), 1)


class TestPositionsSynonymik(unittest.TestCase):
    def test_versicherer_synonyme(self):
        from backend.services.kuerzungstyp_matching import normalisiere_positionslabel
        self.assertEqual(normalisiere_positionslabel("Differenzbetrag"), "fahrzeugschaden")
        self.assertEqual(normalisiere_positionslabel("Kostenpauschale"), "kostenpauschale")
        self.assertEqual(normalisiere_positionslabel("Sachverständigenkosten"), "sv_kosten")
        self.assertIsNone(normalisiere_positionslabel("Völlig Unbekanntes"))


if __name__ == "__main__":
    unittest.main()
