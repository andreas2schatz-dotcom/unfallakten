"""Freigabe ermittelt das Dokumentdatum und nimmt Handkorrekturen an."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestDokumentDatumHelper(unittest.TestCase):
    def _helper(self):
        from backend.routers.intake_routes import _dokument_datum
        return _dokument_datum

    def _dok(self, klasse="gutachten", felder=None):
        import json
        return {
            "id": None,
            "klasse": klasse,
            "parse_json": json.dumps({"felder": felder or {}}),
        }

    def test_aus_geparsten_feldern(self):
        d = self._helper()(
            self._dok(felder={"besichtigungsdatum": "14.03.2024"}), {})
        self.assertEqual(d, "2024-03-14")

    def test_handeingabe_gewinnt(self):
        d = self._helper()(
            self._dok(felder={"besichtigungsdatum": "14.03.2024"}),
            {"dokument_datum": "02.05.2024"})
        self.assertEqual(d, "2024-05-02")

    def test_handeingabe_iso(self):
        d = self._helper()(self._dok(), {"dokument_datum": "2024-05-02"})
        self.assertEqual(d, "2024-05-02")

    def test_leeres_feld_loescht_das_datum(self):
        d = self._helper()(
            self._dok(felder={"besichtigungsdatum": "14.03.2024"}),
            {"dokument_datum": ""})
        self.assertIsNone(d)

    def test_nur_leerzeichen_loescht_das_datum(self):
        d = self._helper()(
            self._dok(felder={"besichtigungsdatum": "14.03.2024"}),
            {"dokument_datum": "   "})
        self.assertIsNone(d)

    def test_fehlender_schluessel_leitet_ab(self):
        d = self._helper()(
            self._dok(felder={"besichtigungsdatum": "14.03.2024"}), {})
        self.assertEqual(d, "2024-03-14")

    def test_unlesbare_handeingabe_wirft(self):
        with self.assertRaises(ValueError):
            self._helper()(self._dok(), {"dokument_datum": "irgendwann"})

    def test_ohne_alles_none(self):
        self.assertIsNone(self._helper()(self._dok(), {}))


class TestFreigabeSchreibtDatum(unittest.TestCase):
    def setUp(self):
        import tempfile
        fd, self._db_pfad = tempfile.mkstemp(prefix="idd_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad
        from backend.db.schema_manager import init_db
        init_db()

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt_db_path
        os.environ.pop("DB_PATH", None)
        try:
            os.unlink(self._db_pfad)
        except OSError:
            pass

    def test_unlesbares_datum_liefert_422(self):
        from backend.routers.intake_routes import _dokument_datum
        with self.assertRaises(ValueError):
            _dokument_datum({"id": None, "klasse": "gutachten",
                             "parse_json": "{}"},
                            {"dokument_datum": "32.13.2024"})

    def _intake_dokument(self, klasse="sonstiges", payload_typ="datei",
                         textquelle=None, empfangen_am=None):
        import json
        from backend.db.database import get_connection
        with get_connection() as conn:
            did = conn.execute(
                "INSERT INTO intake_dokumente "
                "(sha256, arbeitskopie_pfad, payload_typ, klasse, "
                " klasse_quelle, konfidenz, queue_status, parse_json, "
                " textquelle, registry_version) "
                "VALUES (?, 'x.pdf', ?, ?, 'auto', 0.9, "
                " 'bereit_zur_review', ?, ?, 'v1')",
                ("sha-" + klasse + "-" + payload_typ, payload_typ, klasse,
                 json.dumps({"felder": {}}), textquelle),
            ).lastrowid
            if empfangen_am is not None:
                conn.execute(
                    "INSERT INTO zustellungen "
                    "(intake_dokument_id, quelle, empfangen_am) "
                    "VALUES (?, 'imap', ?)",
                    (did, empfangen_am),
                )
            conn.commit()
        return {"id": did, "klasse": klasse, "payload_typ": payload_typ,
                "textquelle": textquelle, "parse_json": json.dumps({"felder": {}})}

    def test_email_dokument_bekommt_zustelldatum(self):
        from backend.routers.intake_routes import _dokument_datum
        dok = self._intake_dokument(
            payload_typ="text", empfangen_am="2026-09-08 16:50:29")
        d = _dokument_datum(dok, {})
        self.assertEqual(d, "2026-09-08")

    def test_datei_dokument_ohne_feldtreffer_bleibt_none(self):
        from backend.routers.intake_routes import _dokument_datum
        dok = self._intake_dokument(
            payload_typ="datei", empfangen_am="2026-09-08 16:50:29")
        d = _dokument_datum(dok, {})
        self.assertIsNone(d)


if __name__ == "__main__":
    unittest.main()
