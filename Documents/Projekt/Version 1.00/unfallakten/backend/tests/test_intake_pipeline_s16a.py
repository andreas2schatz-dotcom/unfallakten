"""
Tests fuer intake/pipeline.py (S1.6a) – Textgewinnungs-Schritt.

Der Pipeline-Schritt in S1.6a:
  1. Liest arbeitskopie_pfad, ruft extrahiere_seiten().
  2. Fuer OCR-Seiten: pdf_zu_bildern + ocr_seite_mit_tsv (TSV je Seite).
  3. Aggregiert Text, stempelt textquelle + registry_version.
  4. markiere_bereit() bei Erfolg, markiere_fehler() bei Exception.

Keine Klassifikation/Extraktion (das kommt in S1.6b).
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


class _BasePipelineTest(unittest.TestCase):
    def setUp(self):
        import uuid
        self._uid = uuid.uuid4().hex
        fd, self._db_pfad = tempfile.mkstemp(prefix="pipe_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad

        self._tmp_dir = tempfile.mkdtemp(prefix="pipe_files_")
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

    def _lege_dokument_mit_arbeitskopie_an(self, pdf_bytes: bytes) -> int:
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


class TestTextebenePfad(_BasePipelineTest):
    def test_textebene_pdf_wird_als_textebene_markiert(self):
        from backend.intake.pipeline import verarbeite_dokument
        from backend.db.database import get_connection

        pdf = _pdf_mit_text(
            "Rechnung Nr. 12345 vom 05.05.2026 "
            "Betrag 268,35 EUR fuer erbrachte Leistungen."
        )
        did = self._lege_dokument_mit_arbeitskopie_an(pdf)

        ergebnis = verarbeite_dokument(did)
        self.assertTrue(ergebnis)

        with get_connection() as conn:
            row = conn.execute(
                "SELECT queue_status, textquelle, registry_version, parse_json "
                "FROM intake_dokumente WHERE id=?", (did,)
            ).fetchone()
        self.assertEqual(row["queue_status"], "bereit_zur_review")
        self.assertEqual(row["textquelle"], "textebene")
        self.assertTrue(row["registry_version"])
        parse = json.loads(row["parse_json"] or "{}")
        self.assertIn("text_gesamt", parse)
        self.assertIn("seiten", parse)
        self.assertIn("Rechnung", parse["text_gesamt"])
        self.assertEqual(len(parse["seiten"]), 1)


class TestOcrPfad(_BasePipelineTest):
    def test_bild_pdf_geht_durch_ocr_und_schreibt_tsv(self):
        from backend.intake import pipeline
        from backend.db.database import get_connection

        # Bild-PDF ohne Textebene
        import fitz
        doc = fitz.open()
        doc.new_page(width=200, height=200)
        pdf = doc.write()
        did = self._lege_dokument_mit_arbeitskopie_an(pdf)

        # OCR-Aufruf mocken – pdf_zu_bildern liefert Dummies, ocr_seite_daten
        # liefert (Text, Boxen) und "schreibt" TSV.
        from PIL import Image
        dummy_img = Image.new("RGB", (10, 10), "white")

        def _ocr_mock(bild, tsv_pfad, lang="deu"):
            os.makedirs(os.path.dirname(tsv_pfad), exist_ok=True)
            with open(tsv_pfad, "w", encoding="utf-8") as f:
                f.write("dummy-tsv")
            return "OCR-Text von Seite", []

        with mock.patch("backend.services.ocr_service.pdf_zu_bildern",
                        return_value=[dummy_img]), \
             mock.patch("backend.services.ocr_service.ocr_seite_daten",
                        side_effect=_ocr_mock):
            ergebnis = pipeline.verarbeite_dokument(did)

        self.assertTrue(ergebnis)
        with get_connection() as conn:
            row = conn.execute(
                "SELECT queue_status, textquelle, parse_json "
                "FROM intake_dokumente WHERE id=?", (did,)
            ).fetchone()
        self.assertEqual(row["queue_status"], "bereit_zur_review")
        self.assertEqual(row["textquelle"], "ocr")
        parse = json.loads(row["parse_json"] or "{}")
        self.assertIn("OCR-Text", parse["text_gesamt"])


class TestSeitenauswahlExtraktion(_BasePipelineTest):
    def test_llm_extraktion_bekommt_nur_ausgewaehlte_seiten(self):
        """N-06: mehrseitiges Dokument -> LLM-Extraktion erhaelt Seite 1 +
        letzte Seite (+ Regex-/Tabellen-Seiten), nicht die irrelevanten
        Fuellseiten dazwischen."""
        from backend.intake import pipeline
        from backend.db.database import get_connection
        import fitz

        seiten_texte = [
            "Schadennummer: 12-345-67890 Datum 22.04.2026 Betrag 268,35 EUR",
            "FUELLSEITEZWEI ohne relevanten Inhalt nur Fliesstext hier drin",
            "FUELLSEITEDREI ebenfalls voellig irrelevanter Fliesstext Seite",
            "Mit freundlichen Gruessen ABSCHLUSSSEITE Ihre Kanzlei am Ende",
        ]
        doc = fitz.open()
        for t in seiten_texte:
            p = doc.new_page(width=595, height=842)
            p.insert_text((72, 72), t, fontsize=11)
        pdf = doc.write()

        did = self._lege_dokument_mit_arbeitskopie_an(pdf)
        # Manuelle Klasse fixieren -> Extraktion nutzt das abrechnungs-Schema.
        with get_connection() as conn:
            conn.execute(
                "UPDATE intake_dokumente SET klasse='abrechnungsschreiben', "
                "klasse_quelle='manuell' WHERE id=?", (did,))

        erhalten = {}

        def _fake_extrakt(schema, text):
            erhalten["text"] = text
            return None

        with mock.patch(
            "backend.intake.extraktion.llm_service.extrahiere_nach_schema",
            side_effect=_fake_extrakt,
        ):
            self.assertTrue(pipeline.verarbeite_dokument(did))

        self.assertIn("Schadennummer", erhalten["text"])
        self.assertIn("ABSCHLUSSSEITE", erhalten["text"])
        self.assertNotIn("FUELLSEITEZWEI", erhalten["text"])


class TestTick(_BasePipelineTest):
    def test_tick_leer_gibt_false(self):
        from backend.intake.pipeline import tick
        self.assertFalse(tick())

    def test_tick_arbeitet_neues_dokument_ab(self):
        from backend.intake.pipeline import tick
        from backend.db.database import get_connection

        pdf = _pdf_mit_text("Rechnung Nr 4711 Betrag 100,00 EUR")
        # Als 'neu' anlegen (nicht 'laeuft' wie _lege_dokument_mit_arbeitskopie_an)
        from backend.intake.queue import enqueue
        did = self._lege_dokument_mit_arbeitskopie_an(pdf)
        enqueue(did)

        self.assertTrue(tick())
        with get_connection() as conn:
            row = conn.execute(
                "SELECT queue_status FROM intake_dokumente WHERE id=?", (did,)
            ).fetchone()
        self.assertEqual(row["queue_status"], "bereit_zur_review")


class TestFehlerpfad(_BasePipelineTest):
    def test_ohne_arbeitskopie_sofort_pipeline_fehler_kein_retry(self):
        """Fehlende Arbeitskopie ist reproduzierbar (N-03) -> sofort
        pipeline_fehler beim ersten Versuch, ohne Backoff-Retries."""
        from backend.intake.pipeline import verarbeite_dokument
        from backend.db.database import get_connection

        # Dokument ohne arbeitskopie_pfad
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO intake_dokumente (sha256, queue_status) VALUES (?, 'laeuft')",
                (self._uid + "1" * (64 - len(self._uid)),),
            )
            did = cur.lastrowid

        self.assertFalse(verarbeite_dokument(did))

        with get_connection() as conn:
            row = conn.execute(
                "SELECT queue_status, versuch_zaehler, fehler_detail "
                "FROM intake_dokumente WHERE id=?", (did,)
            ).fetchone()
        self.assertEqual(row["queue_status"], "pipeline_fehler")
        self.assertEqual(row["versuch_zaehler"], 0)
        self.assertTrue(row["fehler_detail"])
        self.assertIn("Arbeitskopie fehlt", row["fehler_detail"])


if __name__ == "__main__":
    unittest.main()
