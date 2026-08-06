"""
Tests fuer den Endlos-Poll-Loop im E-Mail-Import (Befund 2026-08-06).

Ursachenkette in Produktion:
  1. RA-MICRO-Match liefert eine Akte, die in SQLite nicht existiert.
  2. Die On-demand-Anlage schlug fehl (totes Modul backend.ramicro.ramicro_liste).
  3. Der email_import_log-INSERT verletzte den FK auf unfallakte(az)
     -> Exception -> Mail weder geloggt noch als gelesen markiert
     -> jeder Poll verarbeitete dieselbe Mail erneut (Dubletten-Flut).

Abgedeckt:
  * _stelle_sqlite_akte_sicher legt die Akte wieder tatsaechlich an.
  * FK-Guard: Bleibt die Akte trotzdem unauffindbar, wird die Mail als
    nicht_zugeordnet geloggt und als gelesen markiert statt zu crashen.

Muster wie test_bugfix_p0_intake_v7.py: eigene DB je Test, Import der
Produktivmodule INNERHALB der Testmethode (nach dem DB-Reload).
"""
import os
import shutil
import sys
import tempfile
import unittest
import uuid
from email.message import EmailMessage
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _fresh_db(test_id: str, tmp_dir: str):
    db_path = os.path.join(tmp_dir, f"fkguard_{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path

    import importlib
    import backend.db.database as db_mod
    import backend.db.schema_manager as sm_mod
    for m in (db_mod, sm_mod):
        importlib.reload(m)

    sm_mod.create_schema()
    sm_mod.run_migrations()
    return db_mod


def _minimales_pdf(sig: bytes = b"") -> bytes:
    return (
        b"%PDF-1.4\n%" + sig + b"\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF\n"
    )


def _baue_rohemail(betreff, body, message_id=None):
    msg = EmailMessage()
    msg["Subject"] = betreff
    msg["From"] = "a@b.de"
    msg["To"] = "unfall@anwalt-offenbach.de"
    msg["Date"] = "Mon, 03 Aug 2026 10:00:00 +0200"
    msg["Message-ID"] = message_id or f"<{uuid.uuid4().hex}@x>"
    msg.set_content(body)
    msg.add_attachment(_minimales_pdf(b"fkguard"),
                       maintype="application", subtype="pdf",
                       filename="beleg.pdf")
    return msg.as_bytes()


class _FkGuardTestBase(unittest.TestCase):
    def setUp(self):
        self._alt_flag = os.environ.get("INTAKE_REVIEW_PFLICHT")
        os.environ.pop("INTAKE_REVIEW_PFLICHT", None)  # Default True
        self._tmp = tempfile.mkdtemp(prefix="fkguard_test_")
        os.environ["INTAKE_ARCHIV_ROOT"] = self._tmp
        os.environ["UPLOAD_DIR"] = self._tmp
        self.db = _fresh_db(self._testMethodName, self._tmp)

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)
        os.environ.pop("INTAKE_ARCHIV_ROOT", None)
        os.environ.pop("UPLOAD_DIR", None)
        if self._alt_flag is None:
            os.environ.pop("INTAKE_REVIEW_PFLICHT", None)
        else:
            os.environ["INTAKE_REVIEW_PFLICHT"] = self._alt_flag


class TestOnDemandAnlage(_FkGuardTestBase):
    def test_stelle_sqlite_akte_sicher_legt_akte_an(self):
        """Die On-demand-Anlage muss die Akte wirklich anlegen -- auch wenn
        RA-MICRO fuer die Stammdaten nicht erreichbar ist."""
        from backend.email_import import import_service as isvc
        isvc._stelle_sqlite_akte_sicher("431/22")
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT az FROM unfallakte WHERE az = '431/22'"
            ).fetchone()
        self.assertIsNotNone(
            row, "Akte muss nach _stelle_sqlite_akte_sicher in SQLite existieren")


class TestFkGuard(_FkGuardTestBase):
    def _verarbeite_mit_ramicro_match(self, az="732/26"):
        """Simuliert den Produktionsfall: RA-MICRO matcht eine Akte, die in
        SQLite nicht existiert und deren On-demand-Anlage fehlschlaegt."""
        from backend.email_import import import_service as isvc
        roh = _baue_rohemail(
            betreff=f"Schaden {az}",
            body=f"Zum Aktenzeichen {az} anbei.",
            message_id=f"<fkguard-{az.replace('/', '-')}@x>",
        )
        bericht = isvc._leerer_bericht()
        imap_mock = mock.MagicMock()
        with mock.patch.object(isvc, "_RAMICRO_VERFUEGBAR", True), \
             mock.patch.object(isvc, "suche_akte_in_ramicro",
                               return_value=(az, az, "az_aktenzeichen")), \
             mock.patch.object(isvc, "_stelle_sqlite_akte_sicher"), \
             mock.patch.object(isvc, "markiere_als_gelesen") as mark_mock, \
             mock.patch.object(isvc, "verschiebe_in_ua"), \
             mock.patch.object(isvc, "starte_pdf_parsing"):
            isvc._verarbeite_eine(
                uid=b"1", roh_bytes=roh, imap=imap_mock, bericht=bericht,
                up_dir=Path(self._tmp), bearbeiter_id=None, konto="unfall",
            )
        return bericht, mark_mock

    def test_fehlende_akte_crasht_nicht_und_wird_geloggt(self):
        bericht, mark_mock = self._verarbeite_mit_ramicro_match()

        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT akte_id, status, erkannt_az FROM email_import_log "
                "WHERE message_id = 'fkguard-732-26@x'"
            ).fetchone()
        self.assertIsNotNone(
            row, "Mail muss trotz fehlender Akte im Import-Log landen "
                 "(sonst Endlos-Poll-Loop)")
        self.assertIsNone(row["akte_id"])
        self.assertEqual(row["status"], "nicht_zugeordnet")
        self.assertEqual(row["erkannt_az"], "732/26",
                         "erkanntes AZ muss fuer manuelle Zuordnung erhalten bleiben")
        self.assertEqual(bericht["fehler"], 0)

    def test_mail_wird_als_gelesen_markiert(self):
        _, mark_mock = self._verarbeite_mit_ramicro_match(az="288/26")
        mark_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
