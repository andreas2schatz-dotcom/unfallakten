"""schreibe_dokument uebernimmt das Dokumentdatum."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestSchreibeDokumentDatum(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="oa_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad
        from backend.db.schema_manager import init_db
        init_db()
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('44/22', '2022-04-27', 'offen')"
            )
            conn.commit()
        self._tmpdir = tempfile.mkdtemp(prefix="oa_files_")
        self._quelle = os.path.join(self._tmpdir, "gutachten.pdf")
        with open(self._quelle, "wb") as fh:
            fh.write(b"%PDF-1.4 test")
        self._upload_dir = tempfile.mkdtemp(prefix="oa_uploads_")
        self._alt_upload_dir = os.environ.get("UPLOAD_DIR")
        os.environ["UPLOAD_DIR"] = self._upload_dir

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt_db_path
        os.environ.pop("DB_PATH", None)
        try:
            os.unlink(self._db_pfad)
        except OSError:
            pass
        if self._alt_upload_dir is None:
            os.environ.pop("UPLOAD_DIR", None)
        else:
            os.environ["UPLOAD_DIR"] = self._alt_upload_dir
        shutil.rmtree(self._upload_dir, ignore_errors=True)
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _dok(self):
        return {"klasse": "gutachten", "arbeitskopie_pfad": self._quelle,
                "parse_json": None, "konfidenz": None}

    def test_datum_wird_gespeichert(self):
        from backend.ramicro.output_adapter import schreibe_dokument
        dok_id = schreibe_dokument(self._dok(), "44/22", freigegeben_von=None,
                                    bezeichnung="Gutachten",
                                    dokument_datum="2024-03-14")
        from backend.db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT dokument_datum FROM dokumente WHERE id=?", (dok_id,)
            ).fetchone()
        self.assertEqual(row["dokument_datum"], "2024-03-14")

    def test_ohne_datum_bleibt_null(self):
        from backend.ramicro.output_adapter import schreibe_dokument
        dok_id = schreibe_dokument(self._dok(), "44/22", freigegeben_von=None,
                                    bezeichnung="Gutachten")
        from backend.db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT dokument_datum FROM dokumente WHERE id=?", (dok_id,)
            ).fetchone()
        self.assertIsNone(row["dokument_datum"])


if __name__ == "__main__":
    unittest.main()
