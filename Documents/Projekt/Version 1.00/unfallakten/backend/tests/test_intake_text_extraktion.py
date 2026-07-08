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


if __name__ == "__main__":
    unittest.main()
