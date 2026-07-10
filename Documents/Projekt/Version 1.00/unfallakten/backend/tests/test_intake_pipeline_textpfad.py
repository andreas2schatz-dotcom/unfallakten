"""
Tests fuer den Text-Zweig der Intake-Pipeline (payload_typ='text').

Reine E-Mail-Texte (kein PDF, keine Arbeitskopie) muessen die Pipeline
durchlaufen: Klassifikation + Feld-Extraktion + Akten-Matching arbeiten
bereits auf reinem Text. Ab der Textgewinnung ist der Code identisch zum
Datei-Weg.

DB-Bereitstellung folgt dem Fixture-Muster aus test_intake_pipeline_s16a.py
(echte Temp-SQLite via DB_PATH + init_db) statt get_connection zu mocken --
pipeline.py bindet get_connection beim Import, ein Patch auf database.get_connection
traefe die gebundene Referenz nicht.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class _BaseTextPfadTest(unittest.TestCase):
    def setUp(self):
        import uuid
        self._uid = uuid.uuid4().hex
        fd, self._db_pfad = tempfile.mkstemp(prefix="pipetext_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad

        self._tmp_dir = tempfile.mkdtemp(prefix="pipetext_files_")
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

    def _lege_text_dokument_an(self, text: str) -> int:
        from backend.db.database import get_connection
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO intake_dokumente "
                "(sha256, payload_typ, structured_payload, queue_status) "
                "VALUES (?, 'text', ?, 'laeuft')",
                (self._uid + "0" * (64 - len(self._uid)), text),
            )
            return cur.lastrowid


class TestTextPfad(_BaseTextPfadTest):
    def test_text_payload_wird_bereit_ohne_arbeitskopie(self):
        from backend.intake.pipeline import verarbeite_dokument
        from backend.db.database import get_connection

        did = self._lege_text_dokument_an(
            "Sehr geehrte Damen und Herren, unser Zeichen 285/26. MfG"
        )

        ok = verarbeite_dokument(did)
        self.assertTrue(ok)

        with get_connection() as conn:
            row = conn.execute(
                "SELECT queue_status, klasse, textquelle, parse_json "
                "FROM intake_dokumente WHERE id=?", (did,)
            ).fetchone()
        self.assertEqual(row["queue_status"], "bereit_zur_review")
        self.assertEqual(row["textquelle"], "email_text")
        parse = json.loads(row["parse_json"] or "{}")
        self.assertIn("285/26", parse["text_gesamt"])

    def test_text_payload_ohne_inhalt_ist_fehler(self):
        from backend.intake.pipeline import verarbeite_dokument
        from backend.db.database import get_connection

        did = self._lege_text_dokument_an("   ")
        self.assertFalse(verarbeite_dokument(did))
        with get_connection() as conn:
            row = conn.execute(
                "SELECT fehler_detail FROM intake_dokumente WHERE id=?", (did,)
            ).fetchone()
        self.assertTrue(row["fehler_detail"])


if __name__ == "__main__":
    unittest.main()
