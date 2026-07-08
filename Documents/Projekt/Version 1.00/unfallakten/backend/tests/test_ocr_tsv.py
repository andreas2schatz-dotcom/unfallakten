"""
Tests fuer ocr_seite_mit_tsv (S1.6a).

Der Test mockt ``pytesseract.image_to_data``, damit er auch ohne installierten
Tesseract-Binary laeuft. Der Fluss wird geprueft:

  1. Ergebnis-Text = Konkatenation der 'text'-Spalte des TSV.
  2. TSV wird an den vorgegebenen Pfad geschrieben (bytes-genau).
  3. Ohne Tesseract-Verfuegbarkeit gibt es leeren Text und keine TSV.
"""
import io
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


_TSV_BEISPIEL = (
    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
    "5\t1\t1\t1\t1\t1\t10\t10\t30\t12\t95\tRechnung\n"
    "5\t1\t1\t1\t1\t2\t50\t10\t20\t12\t92\tNr.\n"
    "5\t1\t1\t1\t1\t3\t80\t10\t40\t12\t91\t12345\n"
)


class TestOcrSeiteMitTsv(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="ocr_tsv_")

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _dummy_bild(self):
        from PIL import Image
        return Image.new("RGB", (400, 100), "white")

    def test_liefert_text_und_schreibt_tsv(self):
        from backend.services import ocr_service
        # Verfuegbarkeit erzwingen
        with mock.patch.object(ocr_service, "_pruefeVerfuegbarkeit",
                               return_value=True), \
             mock.patch("pytesseract.image_to_data",
                        return_value=_TSV_BEISPIEL):
            tsv_pfad = os.path.join(self._tmp, "seite_1.tsv")
            text = ocr_service.ocr_seite_mit_tsv(
                self._dummy_bild(), tsv_pfad, lang="deu"
            )
        # Text enthaelt die Woerter aus der TSV
        self.assertIn("Rechnung", text)
        self.assertIn("12345", text)
        # TSV wurde geschrieben
        self.assertTrue(os.path.isfile(tsv_pfad))
        with open(tsv_pfad, "r", encoding="utf-8") as f:
            gespeichert = f.read()
        self.assertEqual(gespeichert, _TSV_BEISPIEL)

    def test_ohne_tesseract_leer_und_kein_tsv(self):
        from backend.services import ocr_service
        with mock.patch.object(ocr_service, "_pruefeVerfuegbarkeit",
                               return_value=False):
            tsv_pfad = os.path.join(self._tmp, "kein.tsv")
            text = ocr_service.ocr_seite_mit_tsv(
                self._dummy_bild(), tsv_pfad, lang="deu"
            )
        self.assertEqual(text, "")
        self.assertFalse(os.path.isfile(tsv_pfad))

    def test_pdf_zu_bild_pro_seite(self):
        """Kleiner Helfer: pdf_zu_bildern liefert PIL-Images pro Seite.

        Skipt lokal ohne poppler; laeuft im Docker-Container.
        """
        try:
            import pdf2image  # noqa: F401
        except ImportError:
            self.skipTest("pdf2image nicht installiert - Docker-only")
        import shutil
        if not shutil.which("pdftoppm"):
            self.skipTest("Poppler (pdftoppm) nicht im PATH - Docker-only")

        import fitz
        doc = fitz.open()
        doc.new_page(width=595, height=842)
        doc.new_page(width=595, height=842)
        pdf_bytes = doc.write()
        from backend.services.ocr_service import pdf_zu_bildern
        bilder = pdf_zu_bildern(pdf_bytes, dpi=100)
        self.assertEqual(len(bilder), 2)


if __name__ == "__main__":
    unittest.main()
