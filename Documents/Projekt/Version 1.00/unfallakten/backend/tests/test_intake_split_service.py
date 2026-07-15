import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import fitz  # PyMuPDF
from backend.intake import split_service as ss


def _mehrseitiges_pdf(n: int) -> bytes:
    doc = fitz.open()
    for i in range(n):
        page = doc.new_page()
        page.insert_text((72, 72), f"Seite {i + 1}")
    out = doc.tobytes()
    doc.close()
    return out


class TestPdfPrimitive(unittest.TestCase):
    def test_seiten_zahl(self):
        self.assertEqual(ss.pdf_seiten_zahl(_mehrseitiges_pdf(5)), 5)

    def test_extrahiere_seiten_pdf(self):
        teil = ss.extrahiere_seiten_pdf(_mehrseitiges_pdf(5), 1, 3)
        self.assertEqual(ss.pdf_seiten_zahl(teil), 3)
        teil2 = ss.extrahiere_seiten_pdf(_mehrseitiges_pdf(5), 4, 5)
        self.assertEqual(ss.pdf_seiten_zahl(teil2), 2)

    def test_rendere_thumbnail_ist_png(self):
        png = ss.rendere_thumbnail(_mehrseitiges_pdf(2), 1)
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))


class TestValidiereGruppen(unittest.TestCase):
    def test_gueltig(self):
        ss.validiere_gruppen([[1, 2, 3], [4, 5]], 5)  # kein Fehler

    def test_zu_wenige_gruppen(self):
        with self.assertRaises(ss.SplitFehler) as ctx:
            ss.validiere_gruppen([[1, 2, 3, 4, 5]], 5)
        self.assertEqual(ctx.exception.status, 422)

    def test_luecke(self):
        with self.assertRaises(ss.SplitFehler):
            ss.validiere_gruppen([[1, 2], [4, 5]], 5)  # 3 fehlt

    def test_ueberdeckung_falsch(self):
        with self.assertRaises(ss.SplitFehler):
            ss.validiere_gruppen([[1, 2], [3, 4]], 5)  # 5 fehlt

    def test_nicht_zusammenhaengend(self):
        with self.assertRaises(ss.SplitFehler):
            ss.validiere_gruppen([[1, 3], [2, 4, 5]], 5)

    def test_leere_gruppe(self):
        with self.assertRaises(ss.SplitFehler):
            ss.validiere_gruppen([[1, 2, 3], []], 5)


if __name__ == "__main__":
    unittest.main()
