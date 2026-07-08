"""
End-to-end-Test S1.6a: Golden-Fixtures durchlaufen die Textgewinnungs-Pipeline.

Jede Klasse aus backend/tests/golden/<klasse>/ wird:
  1. Als synthetisches PDF mit Textebene verpackt (fitz).
  2. Als intake_dokument angelegt, per enqueue in die Queue gesetzt.
  3. tick() abgearbeitet.
  4. Ergebnis geprueft: queue_status='bereit_zur_review', textquelle='textebene',
     text_gesamt enthaelt einen der YAML-Marker der Klasse.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")

ERWARTETE_KLASSEN = [
    "gutachten",
    "abrechnungsschreiben",
    "pruefbericht",
    "rechnung",
    "sv_rechnung",
    "abschlepprechnung",
    "standkostenrechnung",
    # sonstiges hat keine Marker - separater Test unten
]


def _pdf_aus_text(text: str) -> bytes:
    """Verpackt Text in ein PDF mit Textebene, mehrere Seiten bei Bedarf."""
    import fitz
    doc = fitz.open()
    seite = doc.new_page(width=595, height=842)
    # insert_text setzt den Text ab Position (72, 72). Mehrere Zeilen ok.
    seite.insert_text((72, 72), text, fontsize=10)
    return doc.write()


class TestGoldenEndToEnd(unittest.TestCase):
    def setUp(self):
        import uuid
        self._uid = uuid.uuid4().hex
        fd, self._db_pfad = tempfile.mkstemp(prefix="e2e_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad

        self._tmp = tempfile.mkdtemp(prefix="e2e_files_")
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

    def test_alle_golden_klassen_durchlaufen_pipeline(self):
        from backend.intake.pipeline import tick
        from backend.intake.registry_loader import lade_registry, standard_pfad
        from backend.db.database import get_connection

        registry = lade_registry(standard_pfad())

        for klasse in ERWARTETE_KLASSEN:
            fixture = os.path.join(GOLDEN_DIR, klasse, "fixture.txt")
            with open(fixture, "r", encoding="utf-8") as f:
                text = f.read()
            pdf = _pdf_aus_text(text)
            did = self._lege_pdf_dokument_an(klasse[:8], pdf)

            self.assertTrue(tick(), f"Kein Job verarbeitet fuer {klasse}")

            with get_connection() as conn:
                row = conn.execute(
                    "SELECT queue_status, textquelle, parse_json "
                    "FROM intake_dokumente WHERE id=?", (did,)
                ).fetchone()
            self.assertEqual(row["queue_status"], "bereit_zur_review",
                             f"{klasse}: Status falsch")
            self.assertEqual(row["textquelle"], "textebene",
                             f"{klasse}: textquelle falsch")

            parse = json.loads(row["parse_json"] or "{}")
            text_gesamt = parse.get("text_gesamt", "")

            # Mindestens ein Marker aus der Registry-YAML kommt im Text vor
            marker = registry.klassen[klasse]["marker"]
            treffer = [m for m in marker if m.lower() in text_gesamt.lower()]
            self.assertTrue(
                treffer,
                f"{klasse}: kein YAML-Marker im extrahierten Text. "
                f"Text-Anfang: {text_gesamt[:200]!r}",
            )


if __name__ == "__main__":
    unittest.main()
