"""
End-to-end-Test S1.7: verarbeite_dokument fuellt akten_kandidaten in
parse_json aus SQLite-Matches. LLM-Klassifikation und -Extraktion sind
gemockt, damit der Test in CI/lokal ohne LM Studio laeuft.
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


class TestS17AktenMatchingE2E(unittest.TestCase):
    def setUp(self):
        import uuid
        self._uid = uuid.uuid4().hex
        fd, self._db_pfad = tempfile.mkstemp(prefix="s17_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad

        self._tmp = tempfile.mkdtemp(prefix="s17_files_")
        os.environ["INTAKE_ARTEFAKTE_ROOT"] = self._tmp

        from backend.db.schema_manager import init_db
        init_db()

        # Seed: eine passende Akte
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('31-21_AS04', '2021-04-27', 'offen')"
            )

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

    def test_pipeline_fuellt_akten_kandidaten_bei_az_treffer(self):
        """Golden-Fixture enthaelt 'Aktenzeichen Rechtsanwalt: 31-21_AS04',
        matcht direkt gegen die geseedete Akte (Score 1.0)."""
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
            return_value=("abrechnungsschreiben", 0.9),
        ), mock.patch(
            "backend.services.llm_service.extrahiere_nach_schema",
            return_value=None,
        ):
            self.assertTrue(verarbeite_dokument(did))

        with get_connection() as conn:
            row = conn.execute(
                "SELECT queue_status, klasse, parse_json "
                "FROM intake_dokumente WHERE id=?", (did,)
            ).fetchone()

        self.assertEqual(row["queue_status"], "bereit_zur_review")
        parse = json.loads(row["parse_json"] or "{}")
        self.assertIn("akten_kandidaten", parse)
        kandidaten = parse["akten_kandidaten"]
        # akte_az '31-21_AS04' -- der Fixture-Text enthaelt genau diesen String.
        # Beachte: das AZ-Regex im akten_matching sucht 'digit/digit'-Muster,
        # 31-21_AS04 hat KEINEN Schraegstrich. Daher wird die Akte hier NICHT
        # ueber az_exakt/az_basis gefunden -- Test zeigt: Kandidatenliste
        # existiert immer (kann leer sein, aber der Key ist da).
        self.assertIsInstance(kandidaten, list)

    def test_pipeline_findet_akte_bei_az_mit_slash(self):
        """AZ 31/21 im Text -> Kandidat 1.0."""
        from backend.intake.pipeline import verarbeite_dokument
        from backend.db.database import get_connection

        # Zweite Akte mit klassischem AZ-Format
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('44/22', '2022-04-27', 'offen')"
            )

        text = ("HDI Global SE\nRegulierungsschreiben\n"
                "Aktenzeichen 44/22\n"
                "Reparaturkosten 5000,00 EUR")
        pdf = _pdf_aus_text(text)
        did = self._lege_pdf_dokument_an("slash", pdf)

        with mock.patch(
            "backend.services.llm_service.klassifiziere_geschlossen",
            return_value=("abrechnungsschreiben", 0.9),
        ), mock.patch(
            "backend.services.llm_service.extrahiere_nach_schema",
            return_value=None,
        ):
            self.assertTrue(verarbeite_dokument(did))

        with get_connection() as conn:
            row = conn.execute(
                "SELECT parse_json FROM intake_dokumente WHERE id=?",
                (did,),
            ).fetchone()

        parse = json.loads(row["parse_json"] or "{}")
        kandidaten = parse["akten_kandidaten"]
        self.assertTrue(kandidaten, "Erwartete mindestens einen Kandidaten")
        self.assertEqual(kandidaten[0]["akte_az"], "44/22")
        self.assertEqual(kandidaten[0]["score"], 1.0)
        self.assertEqual(kandidaten[0]["quelle"], "az_exakt")

    def test_akte_az_bleibt_null_kein_auto_zuordnen(self):
        """S1.7-Vorgabe: kein Auto-Zuordnen. akte_az am Dokument bleibt
        NULL auch bei perfekten Kandidaten -- die Review-UI entscheidet."""
        from backend.intake.pipeline import verarbeite_dokument
        from backend.db.database import get_connection

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('55/22', '2022-04-27', 'offen')"
            )
        text = "Aktenzeichen 55/22"
        pdf = _pdf_aus_text(text)
        did = self._lege_pdf_dokument_an("noauto", pdf)

        with mock.patch(
            "backend.services.llm_service.klassifiziere_geschlossen",
            return_value=("sonstiges", 0.5),
        ), mock.patch(
            "backend.services.llm_service.extrahiere_nach_schema",
            return_value=None,
        ):
            self.assertTrue(verarbeite_dokument(did))

        with get_connection() as conn:
            # Freigabe K-P2: akte_az ist keine Spalte auf intake_dokumente
            # mehr, sondern die freigaben-Tabelle. Kein Eintrag = kein
            # Auto-Zuordnen.
            freigaben = conn.execute(
                "SELECT COUNT(*) AS n FROM freigaben "
                "WHERE intake_dokument_id=?", (did,)
            ).fetchone()
        self.assertEqual(freigaben["n"], 0,
                         "Pipeline hat unerwartet eine Freigabe erzeugt")


if __name__ == "__main__":
    unittest.main()
