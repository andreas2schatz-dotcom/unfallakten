"""Unter INTAKE_REVIEW_PFLICHT laeuft der Fragebogen-Flow ausschliesslich
ueber die Review-Queue. Der Erstkontakt-Weg ist stillgelegt.
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

BOGEN_OHNE_AZ = {
    "meta": {"formular": "unfallbogen", "version": "2.1"},
    "hat_aktenzeichen": False,
    "aktenzeichen": None,
    "mandant": {"name": "Golovin", "email": "paulgolovin@web.de"},
    "gegner": {"fahrzeug": {"kennzeichen": "MTK-DB801"}},
    "unfall": {"datum": "2026-08-03"},
    "sachschaden": {},
    "personenschaden": None,
    "_roh": {"meta": {"formular": "unfallbogen"}},
}


def _setup(name):
    fd, pfad = tempfile.mkstemp(prefix=f"fbdoppel_{name}_", suffix=".sqlite")
    os.close(fd)
    import backend.db.database as _db
    _db.DB_PATH = pfad
    os.environ["DB_PATH"] = pfad
    from backend.db.schema_manager import init_db
    init_db()
    return pfad


class TestKeinDoppelweg(unittest.TestCase):
    def setUp(self):
        self._alt = os.environ.pop("INTAKE_REVIEW_PFLICHT", None)
        _setup(self._testMethodName)

    def tearDown(self):
        if self._alt is not None:
            os.environ["INTAKE_REVIEW_PFLICHT"] = self._alt
        else:
            os.environ.pop("INTAKE_REVIEW_PFLICHT", None)

    def _zaehle_erstkontakt(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM fragebogen_erstkontakt").fetchone()[0]

    def test_stub_schreibt_nicht_unter_review_pflicht(self):
        from backend.email_import import import_service as isvc
        isvc._fragebogen_neuer_mandant_stub(
            BOGEN_OHNE_AZ,
            {"absender_email": "unfall@anwalt-offenbach.de",
             "message_id": "<a@b>", "betreff": "Unfallbogen: Golovin"},
            isvc._leerer_bericht(),
        )
        self.assertEqual(self._zaehle_erstkontakt(), 0)

    def test_altpfad_schreibt_weiterhin(self):
        os.environ["INTAKE_REVIEW_PFLICHT"] = "false"
        from backend.email_import import import_service as isvc
        isvc._fragebogen_neuer_mandant_stub(
            BOGEN_OHNE_AZ,
            {"absender_email": "unfall@anwalt-offenbach.de",
             "message_id": "<a@b>", "betreff": "Unfallbogen: Golovin"},
            isvc._leerer_bericht(),
        )
        self.assertEqual(self._zaehle_erstkontakt(), 1)

    def test_dashboard_zaehlt_keine_erstkontakte_mehr(self):
        from backend.routers import dashboard_routes
        from backend.db.database import get_connection
        with get_connection() as conn:
            block = dashboard_routes._lade_eingaenge(conn)
        self.assertNotIn("fragebogen_neu", block)
        self.assertEqual(block["gesamt"], block["emails_nicht_zugeordnet"])


if __name__ == "__main__":
    unittest.main()
