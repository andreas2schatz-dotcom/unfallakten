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

    def test_gegnerliste_fehlt_ohne_gegner(self):
        # RA-MICROs Referenz-Export ohne Gegner enthaelt KEINE Gegnerliste;
        # eine leere <Gegnerliste></Gegnerliste> laesst der Import nicht zu.
        root = self._root()
        self.assertIsNone(root.find("Gegnerliste"))

    def test_gegner_volles_geruest_bei_namen(self):
        f = {**FORMULAR,
             "gegner": {**FORMULAR["gegner"], "nachname": "Bicer"}}
        g = self._root(f).find("Gegnerliste/Gegner")
        self.assertIsNotNone(g)
        self.assertEqual(g.findtext("Person/Nachname"), "Bicer")

    def test_tvm_selbstschliessend(self):
        # Referenz hat <tvm/>, nicht <tvm></tvm>.
        xml_text = erzeuge_oma_xml(FORMULAR)
        self.assertIn("<tvm/>", xml_text)
        self.assertNotIn("<tvm></tvm>", xml_text)

    def test_escaping_umlaute_und_ampersand(self):
        f = {**FORMULAR,
             "versicherung": {"name": "Müller & Söhne", "schadennummer": ""}}
        xml_text = erzeuge_oma_xml(f)
        self.assertIn("Müller &amp; Söhne", xml_text)
        ET.fromstring(xml_text)

    def test_leere_elemente_nicht_selbstschliessend(self):
        xml_text = erzeuge_oma_xml(FORMULAR)
        self.assertIn('<Nr typ="data"></Nr>', xml_text)
        self.assertNotIn("<Nr typ=\"data\" />", xml_text)

    def test_zusatzangaben_name_attribute_verbatim(self):
        root = self._root()
        el = root.find("Zusatzangaben/VerbindlicheAnfrageAkzeptiert")
        self.assertIn("rechtsverbindliche Anfrage", el.get("name"))
        self.assertIn("14-tägigen Widerrufsfrist", el.get("name"))
        el2 = root.find("Zusatzangaben/DatenschutzVereinbarungAkzeptiert")
        self.assertIn("RA-MICRO Server", el2.get("name"))

    def test_gegner_volles_geruest(self):
        f = {**FORMULAR,
             "gegner": {**FORMULAR["gegner"], "nachname": "Bicer"}}
        g = self._root(f).find("Gegnerliste/Gegner")
        for pfad in ("Konto/IBAN", "Versicherung/Name", "Hinweise/Text",
                     "Anwalt/KanzleiBezeichnung", "Anwalt/Aktenzeichen"):
            self.assertIsNotNone(g.find(pfad), pfad)


class TestStrukturgleichZurVorlage(unittest.TestCase):
    """Sichert, dass die erzeugte XML strukturgleich zu beispieloma.xml ist
    (RA-MICRO nimmt sonst den Import nicht an). Verglichen werden Tags +
    typ/name-Attribute + Reihenfolge -- NICHT die Textwerte."""

    VORLAGE = os.path.join(os.path.dirname(__file__), "..", "..",
                           "beispieloma.xml")

    def _sig(self, el):
        return (el.tag, tuple(sorted(el.attrib.items())),
                tuple(self._sig(c) for c in el))

    def _finde(self, root, tag):
        return root.find(f".//{tag}")

    def setUp(self):
        if not os.path.isfile(self.VORLAGE):
            self.skipTest("beispieloma.xml nicht auffindbar")
        self.ref = ET.parse(self.VORLAGE).getroot()
        # Voll befuelltes Formular, damit alle Bloecke erscheinen.
        f = {**FORMULAR,
             "gegner": {**FORMULAR["gegner"], "nachname": "Bicer"}}
        self.gen = ET.fromstring(erzeuge_oma_xml(f))

    def test_toplevel_kinder_gleich(self):
        self.assertEqual([c.tag for c in self.ref],
                         [c.tag for c in self.gen])

    def test_mandant_struktur_identisch(self):
        r = self._finde(self.ref, "Mandantenliste").find("Mandant")
        g = self._finde(self.gen, "Mandantenliste").find("Mandant")
        self.assertEqual(self._sig(r), self._sig(g))

    def test_gegner_struktur_identisch(self):
        r = self._finde(self.ref, "Gegnerliste").find("Gegner")
        g = self._finde(self.gen, "Gegnerliste").find("Gegner")
        self.assertEqual(self._sig(r), self._sig(g))

    def test_andere_beteiligter_struktur_identisch(self):
        # Vergleicht den Gutachter-"Andere"-Block mit einem Andere-Block
        # der Vorlage (Feld-Satz muss identisch sein).
        r_andere = next(b.find("Andere") for b in
                        self.ref.findall(".//Beteiligtenliste/Beteiligter")
                        if b.find("Andere") is not None)
        g_andere = next(b.find("Andere") for b in
                        self.gen.findall(".//Beteiligtenliste/Beteiligter")
                        if b.find("Andere") is not None)
        self.assertEqual([(c.tag, c.get("name")) for c in r_andere],
                         [(c.tag, c.get("name")) for c in g_andere])


class TestSchreibeOmaXml(unittest.TestCase):
    def test_atomar_geschrieben(self):
        ordner = tempfile.mkdtemp(prefix="oma_out_")
        pfad = schreibe_oma_xml(FORMULAR, ordner)
        self.assertTrue(pfad.exists())
        # RA-MICRO-Watcher braucht das "Oma_"-Praefix.
        self.assertTrue(pfad.name.startswith("Oma_"))
        self.assertTrue(pfad.name.endswith(".xml"))
        self.assertIn("achkour_zejli", pfad.name)
        tmp_reste = [f for f in os.listdir(ordner)
                     if f.endswith(".tmp") or f.endswith(".part")]
        self.assertEqual(tmp_reste, [])
        ET.fromstring(pfad.read_text(encoding="utf-8"))

    def test_fehler_bei_fehlendem_ordner(self):
        with self.assertRaises(OSError):
            schreibe_oma_xml(FORMULAR, "/nicht/vorhanden/ordner_xyz")

    def test_dateinamen_kollidieren_nicht(self):
        ordner = tempfile.mkdtemp(prefix="oma_uniq_")
        p1 = schreibe_oma_xml(FORMULAR, ordner)
        p2 = schreibe_oma_xml(FORMULAR, ordner)
        self.assertNotEqual(p1, p2)
        self.assertEqual(
            len([f for f in os.listdir(ordner) if f.endswith(".xml")]), 2)


if __name__ == "__main__":
    unittest.main()
