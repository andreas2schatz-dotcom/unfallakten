import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.ramicro.oma_xml import erzeuge_oma_xml, schreibe_oma_xml
from backend.tests.test_aktenanlage_routes import FORMULAR


class TestErzeugeOmaXml(unittest.TestCase):
    def _root(self, formular=None):
        return ET.fromstring(erzeuge_oma_xml(formular or FORMULAR))

    def test_grundstruktur(self):
        root = self._root()
        self.assertEqual(root.tag, "Onlinemandat")
        self.assertEqual(
            root.findtext("Rechtsangelegenheiten/Rechtsangelegenheit/value"),
            "VERKEHRSUNFALL")
        self.assertIsNotNone(root.find("Mandantenliste/Mandant"))
        self.assertIsNotNone(root.find("tvm"))

    def test_mandant_felder(self):
        root = self._root()
        m = root.find("Mandantenliste/Mandant")
        self.assertEqual(m.findtext("Person/Nachname"), "Achkour Zejli")
        self.assertEqual(m.findtext("Person/Vorname"), "Abdessamad")
        self.assertEqual(m.findtext("Person/Anrede/value"), "HERR")
        self.assertEqual(m.findtext("Adresse/PLZ"), "60599")
        self.assertEqual(m.findtext("Bekannt/value"), "1")
        self.assertEqual(m.findtext("Bekannt/text"), "Nein")

    def test_anrede_frau_und_firma(self):
        f = {**FORMULAR, "mandant": {**FORMULAR["mandant"], "anrede": "frau"}}
        self.assertEqual(
            self._root(f).findtext("Mandantenliste/Mandant/Person/Anrede/value"),
            "FRAU")
        f = {**FORMULAR, "mandant": {**FORMULAR["mandant"], "anrede": "firma"}}
        self.assertEqual(
            self._root(f).findtext("Mandantenliste/Mandant/Person/Anrede/value"),
            "FIRMA")

    def test_bekannt_ja_mit_adressnr(self):
        f = {**FORMULAR,
             "mandant": {**FORMULAR["mandant"], "bekannt_adressnr": "12345"}}
        root = self._root(f)
        self.assertEqual(
            root.findtext("Mandantenliste/Mandant/Bekannt/value"), "2")
        self.assertEqual(
            root.findtext("Mandantenliste/Mandant/Bekannt/text"), "Ja")
        self.assertIn("12345", root.findtext("Zusatzangaben/Text"))

    def test_unfalldaten_in_zusatzangaben(self):
        text = self._root().findtext("Zusatzangaben/Text")
        self.assertIn("2026-04-10", text)
        self.assertIn("Offenbach", text)
        self.assertIn("F-RX 4243", text)
        self.assertIn("GA-202604-1189", text)

    def test_beteiligte_versicherung_und_gutachter(self):
        root = self._root()
        bez = [b.findtext("Versicherung/Bezeichnung") or
               b.findtext("Andere/Bezeichnung")
               for b in root.findall("Beteiligtenliste/Beteiligter")]
        self.assertIn("KRAVAG-LOGISTIC Versicherungs-AG", bez)
        self.assertIn("KFZ-Sachverständigenbüro Cassese", bez)

    def test_gegner_nur_bei_namen(self):
        self.assertIsNone(self._root().find("Gegnerliste/Gegner"))
        f = {**FORMULAR,
             "gegner": {**FORMULAR["gegner"], "nachname": "Bicer"}}
        self.assertEqual(
            self._root(f).findtext("Gegnerliste/Gegner/Person/Nachname"),
            "Bicer")

    def test_escaping_umlaute_und_ampersand(self):
        f = {**FORMULAR,
             "versicherung": {"name": "Müller & Söhne", "schadennummer": ""}}
        xml_text = erzeuge_oma_xml(f)
        self.assertIn("Müller &amp; Söhne", xml_text)
        ET.fromstring(xml_text)


class TestSchreibeOmaXml(unittest.TestCase):
    def test_atomar_geschrieben(self):
        ordner = tempfile.mkdtemp(prefix="oma_out_")
        pfad = schreibe_oma_xml(FORMULAR, ordner)
        self.assertTrue(pfad.exists())
        self.assertTrue(pfad.name.startswith("onlinemandat_"))
        self.assertTrue(pfad.name.endswith(".xml"))
        self.assertIn("achkour_zejli", pfad.name)
        tmp_reste = [f for f in os.listdir(ordner) if f.endswith(".tmp")]
        self.assertEqual(tmp_reste, [])
        ET.fromstring(pfad.read_text(encoding="utf-8"))

    def test_fehler_bei_fehlendem_ordner(self):
        with self.assertRaises(OSError):
            schreibe_oma_xml(FORMULAR, "/nicht/vorhanden/ordner_xyz")


if __name__ == "__main__":
    unittest.main()
