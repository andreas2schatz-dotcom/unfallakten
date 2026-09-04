"""
Die im Intake vergebene Klasse muss die Review-Freigabe ueberleben.

Regressionstest zum Befund vom 2026-09-02: _map_klasse() im output_adapter
liess 17 der 23 Registry-Klassen auf 'sonstiges' fallen und schrieb
dokumente.dokumentenklasse ueberhaupt nicht.
"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestKlasseUeberlebtFreigabe(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="ssot_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad

        self._tmp = tempfile.mkdtemp(prefix="ssot_uploads_")
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

    def _lege_intake_an(self, klasse="abrechnungsschreiben",
                        parse_json=None, konfidenz=None):
        arbeit = os.path.join(self._tmp, "arbeit_%s.pdf" % klasse)
        original = os.path.join(self._tmp, "original_%s.pdf" % klasse)
        for p in (arbeit, original):
            with open(p, "wb") as f:
                f.write(b"%PDF-1.4\ndummy")
        from backend.db.database import get_connection
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO intake_dokumente "
                "(sha256, original_pfad, arbeitskopie_pfad, klasse, "
                " parse_json, konfidenz, queue_status) "
                "VALUES (?, ?, ?, ?, ?, ?, 'bereit_zur_review')",
                (klasse.ljust(64, "x")[:64], original, arbeit, klasse,
                 parse_json, konfidenz),
            )
            return cur.lastrowid

    def test_feinklasse_landet_in_dokumentenklasse(self):
        from backend.ramicro.output_adapter import schreibe_dokument
        from backend.db.database import get_connection

        for klasse in ("sv_rechnung", "pruefbericht", "mietwagenrechnung",
                       "fragebogen", "verdienstausfall_nachweis"):
            with self.subTest(klasse=klasse):
                did = self._lege_intake_an(klasse)
                with get_connection() as conn:
                    intake = dict(conn.execute(
                        "SELECT * FROM intake_dokumente WHERE id=?", (did,)
                    ).fetchone())
                dokument_id = schreibe_dokument(intake, "31/21",
                                                freigegeben_von=1)
                with get_connection() as conn:
                    row = conn.execute(
                        "SELECT dokumentenklasse FROM dokumente WHERE id=?",
                        (dokument_id,)
                    ).fetchone()
                self.assertEqual(row["dokumentenklasse"], klasse)

    def test_unbekannte_klasse_wird_abgelehnt(self):
        from backend.models.dokument import registriere_dokument

        with self.assertRaises(ValueError):
            registriere_dokument(
                akte_id="31/21", dokumentenklasse="gibt_es_nicht",
                dateiname="x.pdf", dateipfad="/tmp/x.pdf", bearbeiter_id=1,
            )

    def test_parse_ergebnis_wandert_in_die_akte(self):
        from backend.ramicro.output_adapter import schreibe_dokument
        from backend.db.database import get_connection

        did = self._lege_intake_an(
            "sv_rechnung",
            parse_json='{"felder": {"bruttobetrag": 992.34}}',
            konfidenz=0.91,
        )
        with get_connection() as conn:
            intake = dict(conn.execute(
                "SELECT * FROM intake_dokumente WHERE id=?", (did,)
            ).fetchone())

        dokument_id = schreibe_dokument(intake, "31/21", freigegeben_von=1)

        with get_connection() as conn:
            row = conn.execute(
                "SELECT parse_json, parse_konfidenz, parse_status "
                "FROM dokumente WHERE id=?", (dokument_id,)
            ).fetchone()
        self.assertIn("bruttobetrag", row["parse_json"])
        self.assertAlmostEqual(row["parse_konfidenz"], 0.91)
        self.assertEqual(row["parse_status"], "erfolgreich")

    def test_ohne_parse_json_bleibt_status_ausstehend(self):
        from backend.ramicro.output_adapter import schreibe_dokument
        from backend.db.database import get_connection

        did = self._lege_intake_an("sonstiges")
        with get_connection() as conn:
            intake = dict(conn.execute(
                "SELECT * FROM intake_dokumente WHERE id=?", (did,)
            ).fetchone())

        dokument_id = schreibe_dokument(intake, "31/21", freigegeben_von=1)

        with get_connection() as conn:
            row = conn.execute(
                "SELECT parse_json, parse_status FROM dokumente WHERE id=?",
                (dokument_id,)
            ).fetchone()
        self.assertIsNone(row["parse_json"])
        self.assertEqual(row["parse_status"], "ausstehend")


if __name__ == "__main__":
    unittest.main()
