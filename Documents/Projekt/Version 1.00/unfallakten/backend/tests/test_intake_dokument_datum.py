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

    def test_leere_handeingabe_faellt_auf_ableitung_zurueck(self):
        d = self._helper()(
            self._dok(felder={"besichtigungsdatum": "14.03.2024"}),
            {"dokument_datum": "   "})
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


if __name__ == "__main__":
    unittest.main()
