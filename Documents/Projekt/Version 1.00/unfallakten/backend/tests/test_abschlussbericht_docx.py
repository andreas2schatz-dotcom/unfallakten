"""DOCX-Smoke-Tests für den Abschluss-/Sachstandsbericht."""
import io
import os
import re
import sys
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

from backend.word.abschlussbericht import generiere_abschlussbericht


def _daten(schluss_typ="endgueltig"):
    return {
        "akte": {"aktenzeichen": "42/26", "unfalldatum": "2026-01-10",
                 "unfallort": "Offenbach", "haftungsquote": 100.0,
                 "sachbearbeiter": "AS",
                 "kurzbezeichnung": "Muster/Gegner",
                 "aktenbezeichnung": "Unfall vom 10.01.26"},
        "mandant": {"name": "Muster", "vorname": "Max", "anrede": "1",
                    "anschrift": "Weg 1", "plz": "63065", "ort": "Offenbach",
                    "vorsteuer": "N"},
        "gegner": {"versicherung": "HUK-COBURG"},
        "schaden": {"nutzungsausfall": 300.0, "mietwagenkosten": 500.0},
        "abrechnungen": [{
            "datum": "2026-02-01", "versicherung": "HUK-COBURG",
            "gesamt_reguliert": 650.0, "haftungsquote": 100.0,
            "positionen": [
                {"position_key": "nutzungsausfall",
                 "betrag_gefordert": 300.0, "betrag_reguliert": 300.0},
                {"position_key": "mietwagenkosten",
                 "betrag_gefordert": 500.0, "betrag_reguliert": 350.0,
                 "kuerzungsart_bezeichnung": "Überhöhter Tagessatz"}],
        }],
        "wdm_roh": {},
        "abschluss_status": {"schluss_typ": schluss_typ,
                             "schluss_text": "Damit ist die Sache erledigt.",
                             "naechste_schritte_text": "Wir warten auf die HUK."},
        "gebuehren_kontext": {"faktor": 1.3, "streitwert": 800.0,
                              "erstellt_am": "2026-01-15"},
        "kanzlei": None,
    }


def _daten_voll_reguliert():
    """Alles gefordert, alles gezahlt — Voraussetzung für den Bewertungshinweis."""
    daten = _daten("endgueltig")
    daten["schaden"] = {"nutzungsausfall": 300.0, "mietwagenkosten": 500.0,
                        "unkostenpauschale": 30.0}
    daten["abrechnungen"] = [{
        "datum": "2026-02-01", "versicherung": "HUK-COBURG",
        "gesamt_reguliert": 830.0, "haftungsquote": 100.0,
        "positionen": [
            {"position_key": "nutzungsausfall",
             "betrag_gefordert": 300.0, "betrag_reguliert": 300.0},
            {"position_key": "mietwagenkosten",
             "betrag_gefordert": 500.0, "betrag_reguliert": 500.0},
            {"position_key": "unkostenpauschale",
             "betrag_gefordert": 30.0, "betrag_reguliert": 30.0}],
    }]
    return daten


def _volltext(docx_bytes):
    doc = Document(io.BytesIO(docx_bytes))
    teile = [p.text for p in doc.paragraphs]
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                teile.append(cell.text)
    return "\n".join(teile)


class TestAbschlussberichtDocx(unittest.TestCase):

    def test_abschluss_variante(self):
        b = generiere_abschlussbericht(_daten("endgueltig"))
        self.assertGreater(len(b), 5000)
        text = _volltext(b)
        self.assertIn("42/26", text)
        self.assertIn("Abschlussbericht", text)
        self.assertIn("650,00", text)
        self.assertIn("Überhöhter Tagessatz", text)
        self.assertIn("Damit ist die Sache erledigt.", text)
        self.assertIn("Mit freundlichen Grüßen", text)
        self.assertIn("Andreas Schatz", text)

    def test_sachstand_variante(self):
        b = generiere_abschlussbericht(_daten("offen"))
        text = _volltext(b)
        self.assertIn("Sachstandsbericht", text)
        self.assertNotIn("Abschlussbericht", text)
        self.assertIn("Wir warten auf die HUK.", text)
        self.assertNotIn("Für Sie durchgesetzt", text)

    def test_teilhaftung_mit_kostenfrei_aussage(self):
        daten = _daten("endgueltig")
        daten["abrechnungen"][0]["haftungsquote"] = 70.0
        b = generiere_abschlussbericht(daten)
        text = _volltext(b)
        self.assertIn("kostenfrei", text)
        self.assertIn("regulierten Betrag", text)
        self.assertNotIn("informieren wir Sie gesondert", text)

    def test_sachstand_ohne_kuratiertes_feld(self):
        daten = _daten()
        daten["abschluss_status"] = None
        b = generiere_abschlussbericht(daten)
        self.assertIn("Sachstandsbericht", _volltext(b))

    def test_betreffblock_unter_der_kurzbezeichnung(self):
        doc = Document(io.BytesIO(generiere_abschlussbericht(_daten())))
        texte = [p.text for p in doc.paragraphs]
        kurz = next(i for i, t in enumerate(texte)
                    if t.startswith("Muster/Gegner"))
        # Kurzbezeichnung, darunter Langbezeichnung, darunter die Berichtsart
        self.assertEqual("Unfall vom 10.01.2026", texte[kurz + 1].strip())
        self.assertEqual("Abschlussbericht", texte[kurz + 2].strip())
        # ... und alles vor der Anrede
        self.assertLess(kurz + 2, texte.index("Sehr geehrter Herr Muster,"))

    def test_betreffblock_im_sachstandsbericht(self):
        doc = Document(io.BytesIO(generiere_abschlussbericht(_daten("offen"))))
        texte = [p.text.strip() for p in doc.paragraphs]
        kurz = next(i for i, t in enumerate(texte)
                    if t.startswith("Muster/Gegner"))
        self.assertEqual("Sachstandsbericht", texte[kurz + 2])

    def test_zweistelliges_jahr_der_langbezeichnung_wird_ergaenzt(self):
        # RA-Micro fuehrt "Unfall vom 10.01.26" — im Brief steht TT.MM.JJJJ
        text = _volltext(generiere_abschlussbericht(_daten()))
        self.assertIn("Unfall vom 10.01.2026", text)
        self.assertNotIn("Unfall vom 10.01.26\n", text)

    def test_einleitungssatz_nur_beim_abschluss(self):
        doc = Document(io.BytesIO(generiere_abschlussbericht(_daten())))
        texte = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        anrede = texte.index("Sehr geehrter Herr Muster,")
        self.assertEqual(
            "Ihre Unfallsache ist abgeschlossen. Nachfolgend erhalten Sie "
            "eine Übersicht über den Regulierungsverlauf:", texte[anrede + 1])
        self.assertNotIn("Ihre Unfallsache ist abgeschlossen",
                         _volltext(generiere_abschlussbericht(_daten("offen"))))

    def test_verjaehrungshinweis_auch_ohne_schlusstext(self):
        daten = _daten("vorbehalt_spaetfolgen")
        daten["abschluss_status"]["schluss_text"] = ""
        daten["abschluss_status"]["verjaehrung_datum"] = "2029-06-30"
        text = _volltext(generiere_abschlussbericht(daten))
        self.assertIn("verjähren am", text)
        self.assertIn("30.06.2029", text)


class TestAbschlussberichtLayout(unittest.TestCase):
    """Schriftgröße, Anrede, Tabellenausrichtung und Grußformel."""

    def _dokument(self, daten=None):
        return Document(io.BytesIO(generiere_abschlussbericht(daten or _daten())))

    def test_vorlage_setzt_zwoelf_punkt_als_grundgroesse(self):
        # Die Felder des Briefbogens (Empfänger, Az., Datum) tragen keine
        # eigene Größe, sondern erben sie aus der Formatvorlage.
        self.assertEqual(12, self._dokument().styles["Normal"].font.size.pt)

    def test_brieftext_durchgehend_zwoelf_punkt(self):
        doc = self._dokument()
        abweichler = []

        def pruefe(runs):
            for r in runs:
                if r.text.strip() and r.font.size is not None                         and r.font.size.pt != 12:
                    abweichler.append((r.text[:40], r.font.size.pt))

        for p in doc.paragraphs:
            pruefe(p.runs)
        for tab in doc.tables:
            for row in tab.rows:
                for zelle in row.cells:
                    for p in zelle.paragraphs:
                        pruefe(p.runs)
        self.assertEqual([], abweichler)

    def test_anrede_aus_briefanrede_uebernommen(self):
        daten = _daten()
        daten["mandant"]["briefanrede"] = "Sehr geehrter Herr Muster,"
        self.assertIn("Sehr geehrter Herr Muster,", _volltext(
            generiere_abschlussbericht(daten)))

    def test_anrede_aus_textueller_anrede(self):
        daten = _daten()
        daten["mandant"]["anrede"] = "Frau"
        text = _volltext(generiere_abschlussbericht(daten))
        self.assertIn("Sehr geehrte Frau Muster,", text)
        self.assertNotIn("Sehr geehrte Damen und Herren,", text)

    def test_anrede_aus_ramicro_code(self):
        daten = _daten()
        daten["mandant"]["anrede"] = "1"
        self.assertIn("Sehr geehrter Herr Muster,",
                      _volltext(generiere_abschlussbericht(daten)))

    def test_anrede_firma_bleibt_generisch(self):
        daten = _daten()
        daten["mandant"] = {"firma": "Muster GmbH", "name": "Muster GmbH",
                            "anrede": "4", "anschrift": "Weg 1",
                            "plz": "63065", "ort": "Offenbach", "vorsteuer": "N"}
        self.assertIn("Sehr geehrte Damen und Herren,",
                      _volltext(generiere_abschlussbericht(daten)))

    def test_tabellen_erste_spalte_links_rest_rechts(self):
        doc = self._dokument()
        # Gegenüberstellung (5 Spalten) und Zahlungsverlauf (4 Spalten)
        datentabellen = [t for t in doc.tables if len(t.columns) >= 4]
        self.assertGreaterEqual(len(datentabellen), 2)
        for tab in datentabellen:
            for row in tab.rows:                      # inkl. Kopfzeile
                for s_idx, zelle in enumerate(row.cells):
                    for p in zelle.paragraphs:
                        if not p.text.strip():
                            continue
                        if s_idx == 0:
                            self.assertIn(p.alignment,
                                          (None, WD_ALIGN_PARAGRAPH.LEFT),
                                          f"Spalte 0 nicht links: {p.text!r}")
                        else:
                            self.assertEqual(WD_ALIGN_PARAGRAPH.RIGHT, p.alignment,
                                             f"Spalte {s_idx} nicht rechts: {p.text!r}")

    def test_tabellen_haben_feste_spaltenbreiten(self):
        # Ohne tblLayout=fixed verteilen Word und LibreOffice die Spalten
        # gleichmäßig und trennen lange Positionsnamen mitten im Wort.
        doc = self._dokument()
        for tab in [t for t in doc.tables if len(t.columns) >= 4]:
            xml = tab._tbl.xml
            self.assertIn('<w:tblLayout w:type="fixed"/>', xml)
            breiten = [int(g.get(
                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}w"))
                for g in tab._tbl.find(
                    "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tblGrid")]
            self.assertGreater(len(set(breiten)), 1, "Spalten alle gleich breit")
            # 16 cm Textbreite = 9070 Twips; kleine Rundung erlaubt
            self.assertLessEqual(sum(breiten), 9100)

    def test_tabellenkopf_wiederholt_sich_auf_folgeseiten(self):
        doc = self._dokument()
        for tab in [t for t in doc.tables if len(t.columns) >= 4]:
            self.assertIn("tblHeader", tab.rows[0]._tr.xml)
            for zeile in tab.rows:
                self.assertIn("cantSplit", zeile._tr.xml)

    def test_abschnittstitel_bleiben_bei_ihrem_inhalt(self):
        doc = self._dokument()
        titel = [p for p in doc.paragraphs
                 if p.text.strip() in ("Regulierungsverlauf",
                                       "Gegenüberstellung Ihrer Ansprüche")]
        self.assertEqual(2, len(titel))
        for p in titel:
            self.assertTrue(p.paragraph_format.keep_with_next)

    def test_grussformel_zeigt_aktensachbearbeiter(self):
        text = _volltext(generiere_abschlussbericht(_daten()))
        self.assertIn("Mit freundlichen Grüßen", text)
        self.assertIn("Andreas Schatz", text)
        self.assertIn("Rechtsanwalt", text)
        self.assertNotIn("Rechtsanwälte Koch, Schatz & Kollegen", text)

    def test_grussformel_ohne_sachbearbeiter_faellt_auf_kanzlei_zurueck(self):
        daten = _daten()
        daten["akte"]["sachbearbeiter"] = ""
        text = _volltext(generiere_abschlussbericht(daten))
        self.assertIn("Mit freundlichen Grüßen", text)
        self.assertIn("Koch, Schatz", text)

    def test_grussformel_enthaelt_unterschriftsbild(self):
        doc = self._dokument()
        self.assertTrue(
            any("image" in r.target_ref for r in doc.part.rels.values()),
            "kein Unterschriftsbild eingebettet")


class TestAbschlussberichtBriefbogen(unittest.TestCase):
    """Der Bericht sitzt auf dem echten Kanzlei-Briefbogen."""

    def _teile(self, daten=None):
        b = generiere_abschlussbericht(daten or _daten())
        with zipfile.ZipFile(io.BytesIO(b)) as z:
            return {i.filename: z.read(i.filename) for i in z.infolist()}

    def test_briefbogen_bestandteile_uebernommen(self):
        teile = self._teile()
        # Kopf-/Fußzeilen und Logos des Briefbogens müssen erhalten bleiben
        for pfad in ("word/header2.xml", "word/header3.xml", "word/footer3.xml"):
            self.assertIn(pfad, teile, f"{pfad} fehlt im erzeugten Dokument")
        fuss = teile["word/footer3.xml"].decode("utf-8")
        self.assertIn("Bankverbindung", fuss)
        self.assertIn("DE65 5001 0060 0633 3156 00", fuss)

    def test_sozietaetsleiste_bleibt_erhalten(self):
        body = self._teile()["word/document.xml"].decode("utf-8")
        for name in ("Peter Koch", "Andreas Schatz", "Claudia Ostarek"):
            self.assertIn(name, body, f"Sozietätsleiste ohne {name}")
        self.assertIn("UST-ID-Nr.", body)

    def test_keine_platzhalter_im_ergebnis(self):
        for pfad, inhalt in self._teile().items():
            if pfad.endswith(".xml"):
                offen = re.findall(r"\{\{[^}]{1,40}\}\}", inhalt.decode("utf-8"))
                self.assertEqual([], offen, f"unersetzte Platzhalter in {pfad}")

    def test_empfaenger_und_aktenzeichen_im_briefkopffeld(self):
        body = self._teile()["word/document.xml"].decode("utf-8")
        self.assertIn("Max Muster", body)
        self.assertIn("Weg 1", body)
        self.assertIn("63065 Offenbach", body)
        self.assertIn("42/26", body)

    def test_folgeseiten_kopfzeile_traegt_briefdatum(self):
        kopf = self._teile()["word/header2.xml"].decode("utf-8")
        self.assertIn("zum Schreiben vom", kopf)
        self.assertNotIn("TIME yyyy", kopf)       # Feld lieferte das Öffnungsdatum
        self.assertNotIn("12. März 2026", kopf)   # eingefrorener Vorlagenstand
        self.assertIn("PAGE", kopf)               # Seitenzahl bleibt automatisch

    def test_arial_als_schriftart(self):
        doc = Document(io.BytesIO(generiere_abschlussbericht(_daten())))
        falsch = [(r.text[:30], r.font.name)
                  for p in doc.paragraphs for r in p.runs
                  if r.text.strip() and r.font.name != "Arial"]
        for tab in doc.tables:
            for row in tab.rows:
                for zelle in row.cells:
                    for p in zelle.paragraphs:
                        falsch += [(r.text[:30], r.font.name) for r in p.runs
                                   if r.text.strip() and r.font.name != "Arial"]
        self.assertEqual([], falsch)


class TestAbschlussberichtFormulierung(unittest.TestCase):
    """Datumsformat, Summenzeile, Schlussformel und Bewertungslink."""

    def test_regulierungsverlauf_zeigt_datum_vierstellig(self):
        text = _volltext(generiere_abschlussbericht(_daten()))
        self.assertIn("Abrechnung", text)          # Spalte statt "Datum"
        self.assertIn("01.02.2026", text)
        self.assertNotIn("Zahlungsverlauf", text)

    def test_regulierungsverlauf_datum_stammt_vom_abrechnungsschreiben(self):
        daten = _daten()
        daten["abrechnungen"][0]["datum"] = "2026-03-07"
        self.assertIn("07.03.2026",
                      _volltext(generiere_abschlussbericht(daten)))

    def test_summenzeile_ist_fett_abgesetzt(self):
        doc = Document(io.BytesIO(generiere_abschlussbericht(_daten())))
        gegen = [t for t in doc.tables if len(t.columns) == 5][0]
        letzte = gegen.rows[-1]
        self.assertEqual("Gesamt", letzte.cells[0].text)
        for zelle in letzte.cells:
            for p in zelle.paragraphs:
                for r in p.runs:
                    self.assertTrue(r.font.bold, f"nicht fett: {r.text!r}")
            self.assertIn("EBF2FB", zelle._tc.xml)
        # Datenzeilen bleiben normal
        for zelle in gegen.rows[1].cells:
            for p in zelle.paragraphs:
                for r in p.runs:
                    self.assertFalse(r.font.bold)

    def test_schlussformel_vor_der_grussformel(self):
        doc = Document(io.BytesIO(generiere_abschlussbericht(_daten())))
        texte = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        schluss = next(i for i, t in enumerate(texte)
                       if t.startswith("Wir freuen uns, ein für Sie positives"))
        gruss = texte.index("Mit freundlichen Grüßen")
        self.assertLess(schluss, gruss)
        self.assertIn("auch in Zukunft anwaltlich beraten zu dürfen",
                      texte[schluss])
        self.assertIn("Sollten Sie noch Rückfragen haben, stehen wir Ihnen "
                      "gerne zur Verfügung.", texte[schluss])
        self.assertNotIn("Für Rückfragen stehen wir Ihnen gerne zur Verfügung.",
                         texte)

    def test_sachstandsbericht_ohne_erfolgsbehauptung(self):
        # Bei laufender Sache darf kein "positives Ergebnis" behauptet werden
        text = _volltext(generiere_abschlussbericht(_daten("offen")))
        self.assertNotIn("positives Ergebnis", text)
        self.assertIn("Sollten Sie noch Rückfragen haben, stehen wir Ihnen "
                      "gerne zur Verfügung.", text)

    def test_bewertungslink_ist_klickbar(self):
        b = generiere_abschlussbericht(_daten_voll_reguliert())
        url = "https://g.page/r/CaCarkH1DYGQEBM/review"
        self.assertIn(url, _volltext(b))
        doc = Document(io.BytesIO(b))
        ziele = [r.target_ref for r in doc.part.rels.values() if r.is_external]
        self.assertIn(url, ziele)

    def test_bewertungsabsatz_wortlaut_und_farbe(self):
        doc = Document(io.BytesIO(
            generiere_abschlussbericht(_daten_voll_reguliert())))
        absatz = next(p for p in doc.paragraphs
                      if p.text.startswith("Waren Sie mit unserer Leistung"))
        self.assertIn("bewerten Sie unsere Kanzlei auf Google:", absatz.text)
        # schwarz, nicht mehr grau abgesetzt
        for r in absatz.runs:
            self.assertIsNone(r.font.color.rgb)

    def test_anwaltskosten_ohne_vorsteuer_bleiben_kostenfrei(self):
        daten = _daten_voll_reguliert()
        daten["mandant"]["vorsteuer"] = "N"
        text = _volltext(generiere_abschlussbericht(daten))
        self.assertIn("für Sie kostenfrei", text)
        self.assertNotIn("Vorsteuerabzug", text)

    def test_anwaltskosten_mit_vorsteuer_nennen_netto_und_umsatzsteuer(self):
        daten = _daten_voll_reguliert()
        daten["mandant"]["vorsteuer"] = "J"
        text = _volltext(generiere_abschlussbericht(daten))
        self.assertIn("netto", text)
        self.assertIn("Die Umsatzsteuer erstattet die Gegenseite nicht, da "
                      "Sie zum Vorsteuerabzug berechtigt sind; wir stellen "
                      "sie Ihnen gesondert in Rechnung.", text)
        # "kostenfrei" waere hier die falsche Aussage
        self.assertNotIn("kostenfrei", text)

    def test_anwaltskosten_mit_vorsteuer_nennen_den_nettobetrag(self):
        from backend.services.abschluss_uebersicht import baue_abschluss_uebersicht
        from backend.word.styling import fmt_euro
        daten = _daten_voll_reguliert()
        daten["mandant"]["vorsteuer"] = "J"
        ak = baue_abschluss_uebersicht(daten)["anwaltskosten"]
        text = _volltext(generiere_abschlussbericht(daten))
        self.assertIn(fmt_euro(ak["rvg_netto"]), text)
        self.assertNotIn(fmt_euro(ak["rvg_brutto"]), text)

    def test_wort_freuen_nur_einmal_am_briefende(self):
        text = _volltext(generiere_abschlussbericht(_daten_voll_reguliert()))
        self.assertEqual(1, text.lower().count("freuen"))

    def test_kein_bewertungslink_im_sachstandsbericht(self):
        text = _volltext(generiere_abschlussbericht(_daten("offen")))
        self.assertNotIn("g.page", text)
        self.assertNotIn("Google-Bewertung", text)


if __name__ == "__main__":
    unittest.main()
