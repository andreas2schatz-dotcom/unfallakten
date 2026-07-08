"""
Tests fuer backend/ramicro/output_adapter.py (S1.8, F-08).

Der output_adapter kapselt die eine Schreib-Operation Richtung Akte
(die dokumente-Zeile). Stufe-1-Impl schreibt lokal ueber
models.dokument.registriere_dokument; der XML-Scanner-Adapter kommt
spaeter (F-08) hinter demselben Interface.
"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestOutputAdapterSchreibeDokument(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="oa_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad

        self._tmp = tempfile.mkdtemp(prefix="oa_uploads_")
        self._alt_upload = os.environ.get("UPLOAD_DIR")
        os.environ["UPLOAD_DIR"] = self._tmp

        from backend.db.schema_manager import init_db
        init_db()

        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('31/21', '2021-04-27', 'offen')"
            )
            conn.execute(
                "INSERT INTO benutzer (id, email, name, passwort_hash, "
                "rolle, aktiv) VALUES (1, 'admin@test.de', 'Admin', 'x', "
                "'admin', 1)"
            )

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt_db_path
        os.environ.pop("DB_PATH", None)
        if self._alt_upload is None:
            os.environ.pop("UPLOAD_DIR", None)
        else:
            os.environ["UPLOAD_DIR"] = self._alt_upload
        shutil.rmtree(self._tmp, ignore_errors=True)
        try:
            os.unlink(self._db_pfad)
        except OSError:
            pass

    def _lege_intake_an(self, klasse="abrechnungsschreiben"):
        arbeit = os.path.join(self._tmp, "arbeit.pdf")
        original = os.path.join(self._tmp, "original.pdf")
        for p in (arbeit, original):
            with open(p, "wb") as f:
                f.write(b"%PDF-1.4\ndummy")
        from backend.db.database import get_connection
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO intake_dokumente "
                "(sha256, original_pfad, arbeitskopie_pfad, klasse, "
                " queue_status) "
                "VALUES (?, ?, ?, ?, 'bereit_zur_review')",
                ("a" * 64, original, arbeit, klasse),
            )
            return cur.lastrowid

    def test_schreibt_dokumente_zeile_und_liefert_id(self):
        from backend.ramicro.output_adapter import schreibe_dokument
        from backend.db.database import get_connection

        did = self._lege_intake_an("abrechnungsschreiben")
        with get_connection() as conn:
            intake = dict(conn.execute(
                "SELECT * FROM intake_dokumente WHERE id=?", (did,)
            ).fetchone())

        dokument_id = schreibe_dokument(intake, "31/21", freigegeben_von=1)

        self.assertIsInstance(dokument_id, int)
        self.assertGreater(dokument_id, 0)
        with get_connection() as conn:
            row = conn.execute(
                "SELECT akte_id, typ, dateipfad, dateiname "
                "FROM dokumente WHERE id=?", (dokument_id,)
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["akte_id"], "31/21")
        self.assertEqual(row["typ"], "abrechnungsschreiben")
        self.assertTrue(row["dateipfad"])
        self.assertTrue(row["dateiname"])

    def test_unbekannte_klasse_mappt_auf_sonstiges(self):
        from backend.ramicro.output_adapter import schreibe_dokument
        from backend.db.database import get_connection

        did = self._lege_intake_an("pruefbericht")
        with get_connection() as conn:
            intake = dict(conn.execute(
                "SELECT * FROM intake_dokumente WHERE id=?", (did,)
            ).fetchone())

        dokument_id = schreibe_dokument(intake, "31/21", freigegeben_von=1)

        with get_connection() as conn:
            row = conn.execute(
                "SELECT typ FROM dokumente WHERE id=?", (dokument_id,)
            ).fetchone()
        self.assertEqual(row["typ"], "sonstiges")

    def test_gutachten_klasse_wird_uebernommen(self):
        from backend.ramicro.output_adapter import schreibe_dokument
        from backend.db.database import get_connection

        did = self._lege_intake_an("gutachten")
        with get_connection() as conn:
            intake = dict(conn.execute(
                "SELECT * FROM intake_dokumente WHERE id=?", (did,)
            ).fetchone())

        dokument_id = schreibe_dokument(intake, "31/21", freigegeben_von=1)

        with get_connection() as conn:
            row = conn.execute(
                "SELECT typ FROM dokumente WHERE id=?", (dokument_id,)
            ).fetchone()
        self.assertEqual(row["typ"], "gutachten")

    def test_arbeitskopie_fehlt_wirft(self):
        from backend.ramicro.output_adapter import schreibe_dokument

        intake = {
            "id": 999, "sha256": "b" * 64,
            "arbeitskopie_pfad": os.path.join(self._tmp, "no_such.pdf"),
            "original_pfad": None, "klasse": "abrechnungsschreiben",
        }
        with self.assertRaises(FileNotFoundError):
            schreibe_dokument(intake, "31/21", freigegeben_von=1)


if __name__ == "__main__":
    unittest.main()
