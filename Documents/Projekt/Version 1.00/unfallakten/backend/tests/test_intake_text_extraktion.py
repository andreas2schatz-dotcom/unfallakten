"""
Tests fuer intake/text_extraktion.py (S1.6a).

Kern: pro Seite entscheiden, ob die Textebene brauchbar ist oder OCR noetig.

Regeln aus dem Plan:
  * Textebene falls "brauchbar" (Zeichensalat-Ratio-Check).
  * Sonst OCR-Zweig.
  * ``textquelle`` wird pro Seite gestempelt (textebene/ocr).
"""
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.intake.text_extraktion import MAX_ZEICHENSALAT_RATIO


def _pdf_mit_text(seiten_texte: list) -> bytes:
    """Erzeugt ein PDF mit Textebene via PyMuPDF (fitz).

    Ein Aufruf pro Seite; die Textebene ist auslesbar mit pdfplumber.
    """
    import fitz
    doc = fitz.open()
    for text in seiten_texte:
        page = doc.new_page(width=595, height=842)  # A4
        page.insert_text((72, 72), text, fontsize=11)
    return doc.write()


def _pdf_nur_bild(seiten: int = 1) -> bytes:
    """Erzeugt ein PDF ohne Textebene (nur leere Seiten)."""
    import fitz
    doc = fitz.open()
    for _ in range(seiten):
        doc.new_page(width=595, height=842)
    return doc.write()


class TestZeichensalatRatio(unittest.TestCase):
    def test_sauberer_text_hat_niedrige_ratio(self):
        from backend.intake.text_extraktion import zeichensalat_ratio
        text = "Rechnung Nr. 12345 vom 05.05.2026, Betrag 1.234,56 EUR"
        self.assertLess(zeichensalat_ratio(text), 0.1)

    def test_zeichensalat_hat_hohe_ratio(self):
        from backend.intake.text_extraktion import zeichensalat_ratio
        # Viele Nicht-ASCII/Sonderzeichen -> Rauschen
        text = "^^~~###@@@\x00\x01\x02\x03��אבגד"
        self.assertGreater(zeichensalat_ratio(text), 0.5)

    def test_leer_ist_1_0(self):
        from backend.intake.text_extraktion import zeichensalat_ratio
        self.assertEqual(zeichensalat_ratio(""), 1.0)


class TestExtrahiereSeiten(unittest.TestCase):
    def test_pdf_mit_textebene_liefert_seiten(self):
        from backend.intake.text_extraktion import extrahiere_seiten
        pdf = _pdf_mit_text([
            "Erste Seite - Rechnung Nr. 12345 vom 05.05.2026, Betrag 6.545,00 EUR",
            "Zweite Seite - Nettobetrag 5.500,00 19% MwSt 1.045,00",
        ])
        seiten = extrahiere_seiten(pdf)
        self.assertEqual(len(seiten), 2)
        self.assertIn("Rechnung", seiten[0].text)
        self.assertEqual(seiten[0].textquelle, "textebene")
        self.assertFalse(seiten[0].braucht_ocr)
        self.assertEqual(seiten[0].nr, 1)
        self.assertEqual(seiten[1].nr, 2)

    def test_bild_pdf_wird_als_ocr_markiert(self):
        """Leere Seiten (keine Textebene) -> braucht_ocr=True, textquelle bleibt None
        bis der OCR-Zweig sie ausfuellt (Pipeline-Schritt macht das)."""
        from backend.intake.text_extraktion import extrahiere_seiten
        pdf = _pdf_nur_bild(seiten=2)
        seiten = extrahiere_seiten(pdf)
        self.assertEqual(len(seiten), 2)
        for s in seiten:
            self.assertTrue(s.braucht_ocr)
            self.assertEqual(s.text, "")

    def test_gemischt_pdf(self):
        """Eine Seite mit Text, eine leer -> gemischtes Ergebnis."""
        from backend.intake.text_extraktion import extrahiere_seiten
        import fitz
        doc = fitz.open()
        p1 = doc.new_page(width=595, height=842)
        p1.insert_text((72, 72),
                       "Rechnung Nr. 4711 vom 05.05.2026 Betrag 100,00 EUR",
                       fontsize=11)
        doc.new_page(width=595, height=842)  # leer
        pdf = doc.write()

        seiten = extrahiere_seiten(pdf)
        self.assertEqual(len(seiten), 2)
        self.assertFalse(seiten[0].braucht_ocr)
        self.assertTrue(seiten[1].braucht_ocr)


class TestWoerterbuchQuote(unittest.TestCase):
    def test_deutscher_text_hat_hohe_quote(self):
        from backend.intake.text_extraktion import woerterbuch_quote
        text = ("Sehr geehrte Damen und Herren, in der oben genannten "
                "Angelegenheit uebersenden wir Ihnen die Rechnung ueber "
                "den Betrag fuer die Reparatur des Fahrzeugs.")
        self.assertGreater(woerterbuch_quote(text), 0.3)

    def test_gibberish_hat_niedrige_quote(self):
        from backend.intake.text_extraktion import woerterbuch_quote
        text = ("xkfjq wrtpl mnbvc zxcvb qwrtz plkjh gfdsa lkjhg "
                "poiuz trewq vbnml sdfgh")
        self.assertLess(woerterbuch_quote(text), 0.05)

    def test_leerer_text_ist_0(self):
        from backend.intake.text_extraktion import woerterbuch_quote
        self.assertEqual(woerterbuch_quote(""), 0.0)


class TestKorrupteFontKodierung(unittest.TestCase):
    """Golden-File N-01: hohe Textdichte, niedrige Zeichensalat-Ratio, aber
    keine Woerterbuch-Treffer -> korruptes Font-Encoding -> OCR-Fallback."""

    def test_dichter_gibberish_text_braucht_ocr(self):
        from backend.intake.text_extraktion import extrahiere_seiten
        # Simuliert korrupte Font-Kodierung: viele gueltige ASCII-"Woerter"
        # ohne Sinn (niedrige Zeichensalat-Ratio, aber keine echten Woerter).
        zeilen = ["xkfjq wrtpl mnbvc zxcvb qwrtz plkjh gfdsa lkjhg"] * 12
        pdf = _pdf_mit_text(["\n".join(zeilen)])
        seiten = extrahiere_seiten(pdf)
        self.assertEqual(len(seiten), 1)
        self.assertLess(seiten[0].ratio_salat, MAX_ZEICHENSALAT_RATIO,
                        "Zeichensalat-Check allein wuerde nicht greifen")
        self.assertTrue(seiten[0].braucht_ocr)
        self.assertLess(seiten[0].quote_woerter, 0.05)

    def test_echter_dichter_deutscher_text_nicht_ocr(self):
        from backend.intake.text_extraktion import extrahiere_seiten
        zeilen = [
            "Sehr geehrte Damen und Herren in der oben genannten",
            "Angelegenheit uebersenden wir Ihnen die Rechnung ueber",
            "den Betrag fuer die Reparatur des Fahrzeugs nach dem",
            "Unfall vom fuenften Mai. Wir bitten um Zahlung des",
            "offenen Betrages an unsere Kanzlei bis zum Ende des Monats.",
        ]
        pdf = _pdf_mit_text(["\n".join(zeilen)])
        seiten = extrahiere_seiten(pdf)
        self.assertFalse(seiten[0].braucht_ocr)
        self.assertGreater(seiten[0].quote_woerter, 0.3)


class TestDokumentOcrQualitaet(unittest.TestCase):
    """N-02: Dokument-Level OCR-Qualitaet als schlechteste-Seite-Aggregat.

    ratio_salat = groesster (schlechtester) Wert ueber alle texttragenden
    Seiten; quote_woerter = kleinster (schlechtester) Wert. Gerechnet auf dem
    FINALEN Seitentext (nach OCR), damit ein sauber OCR'tes Scan-Dokument
    nicht faelschlich als schlecht gilt.
    """

    def _seite(self, nr, text, ratio_salat=0.0, quote_woerter=1.0):
        from backend.intake.text_extraktion import SeitenText
        return SeitenText(nr=nr, text=text, braucht_ocr=False,
                          ratio_salat=ratio_salat, quote_woerter=quote_woerter,
                          textquelle="textebene")

    def test_gute_einzelseite(self):
        from backend.intake.text_extraktion import dokument_ocr_qualitaet
        seiten = [self._seite(1,
            "Sehr geehrte Damen und Herren wir uebersenden Ihnen die "
            "Rechnung fuer die Reparatur des Fahrzeugs nach dem Unfall.")]
        ratio, quote = dokument_ocr_qualitaet(seiten)
        self.assertLess(ratio, 0.05)
        self.assertGreater(quote, 0.3)

    def test_schlechteste_seite_gewinnt(self):
        from backend.intake.text_extraktion import dokument_ocr_qualitaet
        gut = ("Sehr geehrte Damen und Herren wir uebersenden Ihnen die "
               "Rechnung fuer die Reparatur des Fahrzeugs.")
        salat = "\x01\x02\x03 §$%&/ ~~~ \x07\x0b ###@@@ ^^^ °°° |||"
        seiten = [self._seite(1, gut), self._seite(2, salat)]
        ratio, quote = dokument_ocr_qualitaet(seiten)
        # ratio_salat = Maximum (schlechteste Seite = die Salat-Seite)
        from backend.intake.text_extraktion import (
            zeichensalat_ratio, woerterbuch_quote)
        self.assertAlmostEqual(ratio, round(zeichensalat_ratio(salat), 3))
        # quote_woerter = Minimum (Salat-Seite hat 0 Woerterbuch-Treffer)
        self.assertAlmostEqual(quote, round(woerterbuch_quote(salat), 3))

    def test_ignoriert_gestempelte_werte_und_rechnet_auf_finaltext(self):
        # Stale-Stempel (ratio_salat=1.0/quote=0.0 aus Vor-OCR-Textebene),
        # aber der finale Text ist gut -> Funktion rechnet neu und liefert gut.
        from backend.intake.text_extraktion import dokument_ocr_qualitaet
        seiten = [self._seite(1,
            "Sehr geehrte Damen und Herren wir uebersenden die Rechnung fuer "
            "die Reparatur des Fahrzeugs nach dem Unfall an unsere Kanzlei.",
            ratio_salat=1.0, quote_woerter=0.0)]
        ratio, quote = dokument_ocr_qualitaet(seiten)
        self.assertLess(ratio, 0.05)
        self.assertGreater(quote, 0.3)

    def test_leere_seiten_geben_none(self):
        from backend.intake.text_extraktion import dokument_ocr_qualitaet
        self.assertEqual(dokument_ocr_qualitaet([]), (None, None))
        self.assertEqual(
            dokument_ocr_qualitaet([self._seite(1, ""),
                                    self._seite(2, "   ")]),
            (None, None))


class TestTextquelleGesamt(unittest.TestCase):
    def test_alle_textebene_ergibt_textebene(self):
        from backend.intake.text_extraktion import (
            extrahiere_seiten, aggregierte_textquelle,
        )
        pdf = _pdf_mit_text(["Seite 1 mit ordentlich Text drin für die Extraktion."])
        seiten = extrahiere_seiten(pdf)
        # Nach Pipeline-Schritt haetten Seiten textquelle gesetzt.
        for s in seiten:
            s.textquelle = "textebene"
        self.assertEqual(aggregierte_textquelle(seiten), "textebene")

    def test_alle_ocr_ergibt_ocr(self):
        from backend.intake.text_extraktion import (
            extrahiere_seiten, aggregierte_textquelle,
        )
        pdf = _pdf_nur_bild(1)
        seiten = extrahiere_seiten(pdf)
        for s in seiten:
            s.textquelle = "ocr"
        self.assertEqual(aggregierte_textquelle(seiten), "ocr")

    def test_gemischt_ergibt_gemischt(self):
        from backend.intake.text_extraktion import (
            extrahiere_seiten, aggregierte_textquelle, SeitenText,
        )
        seiten = [
            SeitenText(nr=1, text="a", braucht_ocr=False, ratio_salat=0.0,
                       textquelle="textebene"),
            SeitenText(nr=2, text="b", braucht_ocr=True, ratio_salat=0.0,
                       textquelle="ocr"),
        ]
        self.assertEqual(aggregierte_textquelle(seiten), "gemischt")


class TestWaehleExtraktionsText(unittest.TestCase):
    """N-06: Seitenauswahl fuer die Feld-Extraktion (Seite 1 + letzte +
    Regex-Treffer-Seiten + Tabellen-Seiten)."""

    def _seite(self, nr, text, hat_tabelle=False):
        from backend.intake.text_extraktion import SeitenText
        return SeitenText(nr=nr, text=text, braucht_ocr=False,
                          ratio_salat=0.0, textquelle="textebene",
                          hat_tabelle=hat_tabelle)

    def test_einzelseite_liefert_ganzen_text(self):
        from backend.intake.text_extraktion import waehle_extraktions_text
        seiten = [self._seite(1, "nur eine seite mit inhalt")]
        self.assertEqual(waehle_extraktions_text(seiten, []),
                         "nur eine seite mit inhalt")

    def test_leere_seitenliste(self):
        from backend.intake.text_extraktion import waehle_extraktions_text
        self.assertEqual(waehle_extraktions_text([], []), "")

    def test_erste_und_letzte_immer_dabei_mitte_faellt_weg(self):
        from backend.intake.text_extraktion import waehle_extraktions_text
        seiten = [self._seite(i + 1, f"seite{i + 1}") for i in range(5)]
        text = waehle_extraktions_text(seiten, [])
        self.assertIn("seite1", text)
        self.assertIn("seite5", text)
        self.assertNotIn("seite3", text)

    def test_regex_treffer_seite_wird_aufgenommen(self):
        from backend.intake.text_extraktion import waehle_extraktions_text
        seiten = [self._seite(i + 1, f"seite{i + 1}") for i in range(5)]
        seiten[2].text = "Rechnungsbetrag 1.234,56 EUR"
        text = waehle_extraktions_text(seiten, [r"\d+,\d{2}\s*EUR"])
        self.assertIn("Rechnungsbetrag", text)

    def test_tabellen_seite_wird_aufgenommen(self):
        from backend.intake.text_extraktion import waehle_extraktions_text
        seiten = [self._seite(i + 1, f"seite{i + 1}") for i in range(5)]
        seiten[3].hat_tabelle = True
        text = waehle_extraktions_text(seiten, [])
        self.assertIn("seite4", text)

    def test_reihenfolge_bleibt_seitenweise(self):
        from backend.intake.text_extraktion import waehle_extraktions_text
        seiten = [self._seite(i + 1, f"seite{i + 1}") for i in range(5)]
        seiten[3].hat_tabelle = True
        text = waehle_extraktions_text(seiten, [])
        self.assertLess(text.index("seite1"), text.index("seite4"))
        self.assertLess(text.index("seite4"), text.index("seite5"))


class TestTabellenErkennung(unittest.TestCase):
    def test_seite_mit_tabellen_gitter_setzt_hat_tabelle(self):
        from backend.intake.text_extraktion import extrahiere_seiten
        import fitz
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        # Einfaches 3x3-Gitter (Linien) + Zellentext -> pdfplumber-Tabelle.
        x0, y0, dx, dy = 72, 72, 120, 40
        for r in range(4):
            y = y0 + r * dy
            page.draw_line((x0, y), (x0 + 3 * dx, y))
        for c in range(4):
            x = x0 + c * dx
            page.draw_line((x, y0), (x, y0 + 3 * dy))
        for r in range(3):
            for c in range(3):
                page.insert_text((x0 + c * dx + 8, y0 + r * dy + 25),
                                 f"Z{r}{c}", fontsize=10)
        pdf = doc.write()
        seiten = extrahiere_seiten(pdf)
        self.assertEqual(len(seiten), 1)
        self.assertTrue(seiten[0].hat_tabelle)

    def test_reine_textseite_ohne_tabelle(self):
        from backend.intake.text_extraktion import extrahiere_seiten
        pdf = _pdf_mit_text([
            "Sehr geehrte Damen und Herren dies ist ein Fliesstext "
            "ohne jede Tabelle und ohne Gitterlinien im Dokument."
        ])
        seiten = extrahiere_seiten(pdf)
        self.assertFalse(seiten[0].hat_tabelle)


if __name__ == "__main__":
    unittest.main()
