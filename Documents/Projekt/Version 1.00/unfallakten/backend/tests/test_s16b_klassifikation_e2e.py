"""
End-to-end-Test S1.6b: verarbeite_dokument stempelt Klasse + Felder.

Erweiterung des S1.6a-Golden-Tests: nach dem Textgewinnungs-Schritt muss
verarbeite_dokument nun auch klasse, klasse_quelle='auto', konfidenz und
extrahierte Felder im parse_json setzen.

Der LLM-Aufruf wird gemockt, damit der Test in CI/lokal ohne LM Studio laeuft.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")


def _pdf_aus_text(text: str) -> bytes:
    import fitz
    doc = fitz.open()
    seite = doc.new_page(width=595, height=842)
    seite.insert_text((72, 72), text, fontsize=10)
    return doc.write()


class TestS16bKlassifikationE2E(unittest.TestCase):
    def setUp(self):
        import uuid
        self._uid = uuid.uuid4().hex
        fd, self._db_pfad = tempfile.mkstemp(prefix="s16b_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad

        self._tmp = tempfile.mkdtemp(prefix="s16b_files_")
        os.environ["INTAKE_ARTEFAKTE_ROOT"] = self._tmp

        from backend.db.schema_manager import init_db
        init_db()

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt_db_path
        os.environ.pop("DB_PATH", None)
        os.environ.pop("INTAKE_ARTEFAKTE_ROOT", None)
        shutil.rmtree(self._tmp, ignore_errors=True)
        try:
            os.unlink(self._db_pfad)
        except OSError:
            pass

    def _lege_pdf_dokument_an(self, sha_suffix: str, pdf_bytes: bytes) -> int:
        from backend.db.database import get_connection
        pfad = os.path.join(self._tmp, f"arbeit_{sha_suffix}.pdf")
        with open(pfad, "wb") as f:
            f.write(pdf_bytes)
        sha = self._uid + sha_suffix
        sha = sha[:64].ljust(64, "0")
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO intake_dokumente "
                "(sha256, arbeitskopie_pfad, queue_status) "
                "VALUES (?, ?, 'neu')",
                (sha, pfad),
            )
            return cur.lastrowid

    def test_verarbeite_dokument_stempelt_klasse_und_felder(self):
        """Golden abrechnungsschreiben: Stufe 1 erkennt Marker, Stufe 2 (LLM
        gemockt) bestaetigt Klasse, Felder landen in parse_json."""
        from backend.intake.pipeline import verarbeite_dokument
        from backend.db.database import get_connection

        fixture = os.path.join(GOLDEN_DIR, "abrechnungsschreiben",
                               "fixture.txt")
        with open(fixture, "r", encoding="utf-8") as f:
            text = f.read()
        pdf = _pdf_aus_text(text)
        did = self._lege_pdf_dokument_an("abr", pdf)

        with mock.patch(
            "backend.services.llm_service.klassifiziere_geschlossen",
            return_value=("abrechnungsschreiben", 0.92),
        ), mock.patch(
            "backend.services.llm_service.extrahiere_nach_schema",
            return_value={"schadennummer": "12-345-67890-001",
                          "schreibdatum": "22.04.2026"},
        ):
            self.assertTrue(verarbeite_dokument(did))

        with get_connection() as conn:
            row = conn.execute(
                "SELECT queue_status, klasse, klasse_quelle, konfidenz, "
                "parse_json FROM intake_dokumente WHERE id=?", (did,)
            ).fetchone()

        self.assertEqual(row["queue_status"], "bereit_zur_review")
        self.assertEqual(row["klasse"], "abrechnungsschreiben")
        self.assertEqual(row["klasse_quelle"], "auto")
        self.assertAlmostEqual(row["konfidenz"], 0.92, places=3)

        parse = json.loads(row["parse_json"] or "{}")
        # Textgewinnung aus S1.6a bleibt erhalten
        self.assertIn("text_gesamt", parse)
        self.assertIn("seiten", parse)
        # Neu in S1.6b: Klassifikations- und Feld-Ergebnisse
        self.assertIn("klassifikation", parse)
        self.assertIn("felder", parse)
        self.assertEqual(parse["felder"].get("schadennummer"),
                         "12-345-67890-001")

    def test_llm_ausfall_fallback_auf_stufe1_kandidaten(self):
        """LLM liefert None -> Stufe 2 nimmt besten Stufe-1-Kandidaten.
        'HDI Global' + 'Regulierungsschreiben' als Marker in fixture.txt."""
        from backend.intake.pipeline import verarbeite_dokument
        from backend.db.database import get_connection

        fixture = os.path.join(GOLDEN_DIR, "abrechnungsschreiben",
                               "fixture.txt")
        with open(fixture, "r", encoding="utf-8") as f:
            text = f.read()
        pdf = _pdf_aus_text(text)
        did = self._lege_pdf_dokument_an("fbk", pdf)

        with mock.patch(
            "backend.services.llm_service.klassifiziere_geschlossen",
            return_value=(None, 0.0),
        ), mock.patch(
            "backend.services.llm_service.extrahiere_nach_schema",
            return_value=None,
        ):
            self.assertTrue(verarbeite_dokument(did))

        with get_connection() as conn:
            row = conn.execute(
                "SELECT klasse, klasse_quelle FROM intake_dokumente "
                "WHERE id=?", (did,)
            ).fetchone()
        self.assertEqual(row["klasse"], "abrechnungsschreiben")
        self.assertEqual(row["klasse_quelle"], "auto")


if __name__ == "__main__":
    unittest.main()
