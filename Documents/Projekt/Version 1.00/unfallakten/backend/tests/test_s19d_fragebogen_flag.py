"""
Tests fuer S1.9d / K-P1: Fragebogen-Auto-Enrichment unter
INTAKE_REVIEW_PFLICHT.

K-P1 aus freigabe.md:
    Das Auto-Enrichment (fragebogen_parser -> direkte Schreibvorgaenge in
    Beteiligten-/Unfalldetail-Tabellen) entfaellt. Fragebogen-Mails laufen
    durch die Review-Queue; geparste Antworten erscheinen als Vorschlag im
    Freigabe-Dialog, Uebernahme erst mit Freigabe.

Erwartungen:
  * Unter dem Flag (Default True) schreiben ``_ergaenze_mandant``,
    ``_ergaenze_gegner``, ``_ergaenze_unfalldetails`` und
    ``_ergaenze_personenschaden`` NICHT in die Akte.
  * Alt-Pfad (Flag=false) bleibt aktiv und ergaenzt leere Felder wie zuvor.
"""
import importlib
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


_tmp_dir = tempfile.mkdtemp(prefix="s19d_")


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"s19d_{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path

    import backend.db.database as db_mod
    for m in (db_mod,):
        importlib.reload(m)

    from backend.db.schema_manager import init_db
    init_db()

    from backend.db.database import get_connection
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO unfallakte (az, unfalldatum, status) "
            "VALUES ('44/22', '2022-04-27', 'offen')"
        )


class TestFragebogenAutoEnrichmentFlag(unittest.TestCase):
    def setUp(self):
        self._alt_flag = os.environ.get("INTAKE_REVIEW_PFLICHT")
        os.environ.pop("INTAKE_REVIEW_PFLICHT", None)
        _setup(self._testMethodName)

    def tearDown(self):
        if self._alt_flag is None:
            os.environ.pop("INTAKE_REVIEW_PFLICHT", None)
        else:
            os.environ["INTAKE_REVIEW_PFLICHT"] = self._alt_flag

    def _mandant_seeden(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO beteiligte (akte_id, rolle, name) "
                "VALUES ('44/22', 'mandant', 'Alt')"
            )

    def test_ergaenze_mandant_default_flag_true_skippt(self):
        os.environ.pop("INTAKE_REVIEW_PFLICHT", None)
        self._mandant_seeden()

        from backend.email_import.import_service import _ergaenze_mandant
        _ergaenze_mandant("44/22", {
            "email": "neu@x.de", "telefon": "0999",
            "vorname": "Neu",
        })

        from backend.db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT email, telefon, vorname FROM beteiligte "
                "WHERE akte_id='44/22' AND rolle='mandant'"
            ).fetchone()

        # Alle Felder waren leer, sind aber unter dem Flag NICHT befuellt worden.
        self.assertIsNone(row["email"],
                          "E-Mail darf unter Flag nicht ergaenzt werden")
        self.assertIsNone(row["telefon"],
                          "Telefon darf unter Flag nicht ergaenzt werden")
        self.assertIsNone(row["vorname"],
                          "Vorname darf unter Flag nicht ergaenzt werden")

    def test_ergaenze_mandant_flag_false_ergaenzt(self):
        os.environ["INTAKE_REVIEW_PFLICHT"] = "false"
        self._mandant_seeden()

        from backend.email_import.import_service import _ergaenze_mandant
        _ergaenze_mandant("44/22", {
            "email": "neu@x.de", "telefon": "0999",
            "vorname": "Neu",
        })

        from backend.db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT email, telefon, vorname FROM beteiligte "
                "WHERE akte_id='44/22' AND rolle='mandant'"
            ).fetchone()

        self.assertEqual(row["email"], "neu@x.de",
                          "Alt-Pfad muss die leere E-Mail ergaenzen")
        self.assertEqual(row["telefon"], "0999")

    def test_ergaenze_gegner_default_flag_true_skippt(self):
        os.environ.pop("INTAKE_REVIEW_PFLICHT", None)
        from backend.email_import.import_service import _ergaenze_gegner
        _ergaenze_gegner("44/22", {
            "name": "Gegner GmbH", "kfz": {"kennzeichen": "OF-XY 123"},
        })

        from backend.db.database import get_connection
        with get_connection() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM beteiligte "
                "WHERE akte_id='44/22' AND rolle='gegner'"
            ).fetchone()[0]
        self.assertEqual(n, 0,
                          "Gegner-Insert unter Flag verboten (K-P1)")

    def test_ergaenze_unfalldetails_default_flag_true_skippt(self):
        os.environ.pop("INTAKE_REVIEW_PFLICHT", None)
        from backend.email_import.import_service import _ergaenze_unfalldetails
        _ergaenze_unfalldetails("44/22", {"datum": "2022-04-27",
                                           "ort": "Offenbach"})

        from backend.db.database import get_connection
        with get_connection() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM unfalldetails WHERE akte_id='44/22'"
            ).fetchone()[0]
        self.assertEqual(n, 0,
                          "Unfalldetails-Insert unter Flag verboten (K-P1)")

    def test_ergaenze_personenschaden_default_flag_true_skippt(self):
        os.environ.pop("INTAKE_REVIEW_PFLICHT", None)
        from backend.email_import.import_service import _ergaenze_personenschaden
        _ergaenze_personenschaden("44/22", {"verletzungen": "Nackenschmerz"})

        from backend.db.database import get_connection
        with get_connection() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM personenschaden WHERE akte_id='44/22'"
            ).fetchone()[0]
        self.assertEqual(n, 0,
                          "Personenschaden-Insert unter Flag verboten (K-P1)")


if __name__ == "__main__":
    unittest.main()
