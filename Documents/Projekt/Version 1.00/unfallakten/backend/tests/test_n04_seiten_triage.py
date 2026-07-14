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


import json
import shutil
import tempfile
from unittest import mock


def _pdf_leerseiten(n: int) -> bytes:
    import fitz
    doc = fitz.open()
    for _ in range(n):
        doc.new_page(width=595, height=842)
    return doc.write()


class _FakeBild:
    size = (1000, 1000)


class TestPipelineTriage(unittest.TestCase):
    def setUp(self):
        import uuid
        self._uid = uuid.uuid4().hex
        fd, self._db = tempfile.mkstemp(prefix="n04_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        self._alt = _db.DB_PATH
        _db.DB_PATH = self._db
        os.environ["DB_PATH"] = self._db
        self._tmp = tempfile.mkdtemp(prefix="n04_files_")
        os.environ["INTAKE_ARTEFAKTE_ROOT"] = self._tmp
        from backend.db.schema_manager import init_db
        init_db()

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt
        os.environ.pop("DB_PATH", None)
        os.environ.pop("INTAKE_ARTEFAKTE_ROOT", None)
        shutil.rmtree(self._tmp, ignore_errors=True)
        try:
            os.unlink(self._db)
        except OSError:
            pass

    def _anlegen(self, pdf_bytes):
        from backend.db.database import get_connection
        arbeit = os.path.join(self._tmp, "arbeit.pdf")
        with open(arbeit, "wb") as f:
            f.write(pdf_bytes)
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO intake_dokumente "
                "(sha256, arbeitskopie_pfad, queue_status) "
                "VALUES (?, ?, 'laeuft')",
                (self._uid + "0" * (64 - len(self._uid)), arbeit))
            return cur.lastrowid

    def test_fotoseite_ueberspringt_glm(self):
        from backend.intake import pipeline
        from backend.db.database import get_connection

        did = self._anlegen(_pdf_leerseiten(2))

        foto = ("Abb. 3", [{"breite": 10, "hoehe": 10, "conf": 90, "text": "Abb"}])
        text = ("voller Seitentext hier",
                [{"breite": 600, "hoehe": 400, "conf": 90, "text": "viel"}])

        with mock.patch.object(pipeline.ocr_service, "pdf_zu_bildern",
                               return_value=[_FakeBild()]), \
             mock.patch.object(pipeline.ocr_service, "ocr_seite_daten",
                               side_effect=[foto, text]) as m_ocr, \
             mock.patch.object(pipeline.glm_ocr_service, "glm_ocr_seite",
                               return_value="GLM-TEXT") as m_glm:
            self.assertTrue(pipeline.verarbeite_dokument(did))

        self.assertEqual(m_ocr.call_count, 2)
        self.assertEqual(m_glm.call_count, 1)  # nur die Textseite

        with get_connection() as conn:
            row = conn.execute(
                "SELECT parse_json, queue_status FROM intake_dokumente WHERE id=?",
                (did,)).fetchone()
        self.assertEqual(row["queue_status"], "bereit_zur_review")
        parse = json.loads(row["parse_json"])
        self.assertEqual(parse["bildseiten_anzahl"], 1)
        self.assertTrue(parse["seiten"][0]["ist_bildseite"])
        self.assertFalse(parse["seiten"][1]["ist_bildseite"])
