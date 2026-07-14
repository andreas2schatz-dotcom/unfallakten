"""Tests fuer N-04: Seiten-Triage vor OCR (Bildseiten-Erkennung)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

_KOPF = "\t".join([
    "level", "page_num", "block_num", "par_num", "line_num", "word_num",
    "left", "top", "width", "height", "conf", "text",
])


class TestParseTsv(unittest.TestCase):
    def test_text_und_boxen(self):
        from backend.services.ocr_service import _parse_tsv
        tsv = "\n".join([
            _KOPF,
            "\t".join(["5", "1", "1", "1", "1", "1",
                       "10", "20", "40", "15", "95", "Hallo"]),
            # Strukturzeile ohne Text, conf -1 -> keine Box, kein Wort
            "\t".join(["4", "1", "1", "1", "1", "0",
                       "0", "0", "0", "0", "-1", ""]),
        ])
        text, boxen = _parse_tsv(tsv)
        self.assertEqual(text, "Hallo")
        self.assertEqual(
            boxen,
            [{"breite": 40, "hoehe": 15, "conf": 95.0, "text": "Hallo"}])

    def test_leeres_tsv(self):
        from backend.services.ocr_service import _parse_tsv
        self.assertEqual(_parse_tsv(""), ("", []))
