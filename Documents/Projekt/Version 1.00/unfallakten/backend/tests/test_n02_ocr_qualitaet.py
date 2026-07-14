"""
N-02 (FREIGABE-NACHTRAG-1 A): OCR-Qualitaetsmetriken persistieren.

Zeichensalat-Ratio und Woerterbuch-Quote werden je Dokument (Schlechteste-
Seite-Aggregat) an ``intake_dokumente`` gespeichert und ueber die Review-
Queue als Hinweissignal bereitgestellt (Badge bei schlechter OCR-Qualitaet).

Testkriterien:
  1) Migration 56 legt ocr_ratio_salat + ocr_quote_woerter (REAL, nullable) an.
  2) verarbeite_dokument stempelt beide Werte am Dokument.
  3) hole_queue liefert beide Werte je Eintrag.
"""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _pdf_mit_text(text: str) -> bytes:
    import fitz
    doc = fitz.open()
    p = doc.new_page(width=595, height=842)
    p.insert_text((72, 72), text, fontsize=11)
    return doc.write()


class _BaseIntakeDb(unittest.TestCase):
    def setUp(self):
        import uuid
        self._uid = uuid.uuid4().hex
        fd, self._db_pfad = tempfile.mkstemp(prefix="n02_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad

        self._tmp_dir = tempfile.mkdtemp(prefix="n02_files_")
        os.environ["INTAKE_ARTEFAKTE_ROOT"] = self._tmp_dir

        from backend.db.schema_manager import init_db
        init_db()

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt_db_path
        os.environ.pop("DB_PATH", None)
        os.environ.pop("INTAKE_ARTEFAKTE_ROOT", None)
        shutil.rmtree(self._tmp_dir, ignore_errors=True)
        try:
            os.unlink(self._db_pfad)
        except OSError:
            pass

    def _lege_dokument_an(self, pdf_bytes: bytes) -> int:
        from backend.db.database import get_connection
        arbeit = os.path.join(self._tmp_dir, "arbeitskopie.pdf")
        with open(arbeit, "wb") as f:
            f.write(pdf_bytes)
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO intake_dokumente "
                "(sha256, arbeitskopie_pfad, queue_status) "
                "VALUES (?, ?, 'laeuft')",
                (self._uid + "0" * (64 - len(self._uid)), arbeit),
            )
            return cur.lastrowid


class TestMigration56(_BaseIntakeDb):
    def test_spalten_existieren(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            cols = {r[1]: r[2] for r in conn.execute(
                "PRAGMA table_info(intake_dokumente)").fetchall()}
        self.assertIn("ocr_ratio_salat", cols)
        self.assertIn("ocr_quote_woerter", cols)
        self.assertEqual(cols["ocr_ratio_salat"].upper(), "REAL")
        self.assertEqual(cols["ocr_quote_woerter"].upper(), "REAL")


class TestPipelinePersistiert(_BaseIntakeDb):
    def test_verarbeite_dokument_stempelt_qualitaet(self):
        from backend.intake.pipeline import verarbeite_dokument
        from backend.db.database import get_connection

        pdf = _pdf_mit_text(
            "Sehr geehrte Damen und Herren wir uebersenden Ihnen die Rechnung "
            "fuer die Reparatur des Fahrzeugs nach dem Unfall vom Mai.")
        did = self._lege_dokument_an(pdf)

        self.assertTrue(verarbeite_dokument(did))

        with get_connection() as conn:
            row = conn.execute(
                "SELECT ocr_ratio_salat, ocr_quote_woerter "
                "FROM intake_dokumente WHERE id=?", (did,)
            ).fetchone()
        self.assertIsNotNone(row["ocr_ratio_salat"])
        self.assertIsNotNone(row["ocr_quote_woerter"])
        # Sauberer deutscher Text -> gute Werte.
        self.assertLess(row["ocr_ratio_salat"], 0.05)
        self.assertGreater(row["ocr_quote_woerter"], 0.3)


if __name__ == "__main__":
    unittest.main()
