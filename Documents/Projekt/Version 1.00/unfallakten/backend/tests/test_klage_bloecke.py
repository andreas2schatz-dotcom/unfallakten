import unittest

from backend.word.klage_bloecke import ooxml_zu_text, Abschnitt


class TestOoxmlZuText(unittest.TestCase):
    def test_leerer_input(self):
        self.assertEqual(ooxml_zu_text(""), "")
        self.assertEqual(ooxml_zu_text(None), "")

    def test_einfacher_absatz(self):
        xml = '<w:p><w:pPr><w:jc w:val="both"/></w:pPr><w:r><w:rPr/><w:t xml:space="preserve">Hallo Welt</w:t></w:r></w:p>'
        self.assertEqual(ooxml_zu_text(xml), "Hallo Welt")

    def test_zwei_absaetze_werden_zeilen(self):
        xml = ('<w:p><w:r><w:t>Erster Satz.</w:t></w:r></w:p>'
               '<w:p><w:r><w:t>Zweiter Satz.</w:t></w:r></w:p>')
        self.assertEqual(ooxml_zu_text(xml), "Erster Satz.\nZweiter Satz.")

    def test_tab_wird_tabulator(self):
        xml = ('<w:p><w:r><w:t>BEWEIS:</w:t></w:r>'
               '<w:r><w:tab/></w:r><w:r><w:t>Zeugnis Meier</w:t></w:r></w:p>')
        self.assertEqual(ooxml_zu_text(xml), "BEWEIS:\tZeugnis Meier")

    def test_entities_werden_zurueckgewandelt(self):
        xml = '<w:p><w:r><w:t>Koch &amp; Schatz &lt;RA&gt;</w:t></w:r></w:p>'
        self.assertEqual(ooxml_zu_text(xml), "Koch & Schatz <RA>")

    def test_leerabsatz_erzeugt_keine_doppelten_leerzeilen(self):
        xml = ('<w:p><w:r><w:t>A</w:t></w:r></w:p>'
               '<w:p><w:pPr><w:jc w:val="both"/></w:pPr></w:p>'
               '<w:p><w:r><w:t>B</w:t></w:r></w:p>')
        self.assertEqual(ooxml_zu_text(xml), "A\n\nB")

    def test_tabellenzeile_und_zelle(self):
        xml = ('<w:tbl><w:tr>'
               '<w:tc><w:p><w:r><w:t>Reparaturkosten</w:t></w:r></w:p></w:tc>'
               '<w:tc><w:p><w:r><w:t>3.000,00 &#8364;</w:t></w:r></w:p></w:tc>'
               '</w:tr></w:tbl>')
        self.assertIn("Reparaturkosten", ooxml_zu_text(xml))
        self.assertIn("3.000,00", ooxml_zu_text(xml))


class TestAbschnitt(unittest.TestCase):
    def test_dataclass_felder(self):
        a = Abschnitt(key="sachverhalt", titel="Sachverhalt",
                      platzhalter="{{EINLEITUNG}}", xml="<w:p/>",
                      editierbar=True, override_feld="sachverhalt_override")
        self.assertEqual(a.key, "sachverhalt")
        self.assertTrue(a.editierbar)
        self.assertEqual(a.override_feld, "sachverhalt_override")


if __name__ == "__main__":
    unittest.main()
