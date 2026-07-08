"""
Tests fuer S1.9b: import_service._verarbeite_eine unter dem Feature-Flag
INTAKE_REVIEW_PFLICHT.

Erwartungen:
  * Unter dem Flag (Default True) legt der Alt-Pfad KEINE neuen
    ``dokumente``-Zeilen mehr fuer E-Mail-Anhaenge an. Der IMAP-Adapter
    (bereits eingebauter Doppelschreiber) erzeugt weiterhin
    ``intake_dokumente`` + ``zustellungen``.
  * Ohne den Flag (Legacy-Betrieb, ``INTAKE_REVIEW_PFLICHT=false``) bleibt
    der Alt-Pfad aktiv und schreibt in ``dokumente`` wie frueher.
"""
import os
import sys
import tempfile
import unittest
from email.message import EmailMessage
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _baue_rohemail(betreff="Test", von="a@b.de",
                    body="Kein AZ hier drin.",
                    anhang_name="beleg.pdf") -> bytes:
    msg = EmailMessage()
    msg["Subject"] = betreff
    msg["From"] = von
    msg["To"] = "unfall@anwalt-offenbach.de"
    msg["Date"] = "Mon, 07 Jul 2026 10:00:00 +0200"
    msg["Message-ID"] = f"<{anhang_name}-mid@x>"
    msg.set_content(body)
    if anhang_name:
        pdf = b"%PDF-1.4\n%dummy\n"
        msg.add_attachment(pdf, maintype="application", subtype="pdf",
                            filename=anhang_name)
    return msg.as_bytes()


class TestImportServiceUnterFlag(unittest.TestCase):
    def setUp(self):
        self._alt_flag = os.environ.get("INTAKE_REVIEW_PFLICHT")
        fd, self._db_pfad = tempfile.mkstemp(prefix="s19b_", suffix=".sqlite")
        os.close(fd)
        self._tmp = tempfile.mkdtemp(prefix="s19b_files_")

        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad
        os.environ["UPLOAD_DIR"] = self._tmp

        from backend.db.schema_manager import init_db
        init_db()

        # Seed: Akte mit AZ, das die E-Mail treffen wird.
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('44/22', '2022-04-27', 'offen')"
            )

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt_db_path
        os.environ.pop("DB_PATH", None)
        os.environ.pop("UPLOAD_DIR", None)
        if self._alt_flag is None:
            os.environ.pop("INTAKE_REVIEW_PFLICHT", None)
        else:
            os.environ["INTAKE_REVIEW_PFLICHT"] = self._alt_flag
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)
        try:
            os.unlink(self._db_pfad)
        except OSError:
            pass

    def _rufe_verarbeite(self):
        """Ruft ``_verarbeite_eine`` mit einer Mock-IMAP-Verbindung auf und
        gibt einen leeren Bericht zurueck. Die Nachricht enthaelt den AZ
        '44/22', damit sie zugeordnet wird und der Anhang-Registrierungs-
        Zweig getriggert wird."""
        roh = _baue_rohemail(
            betreff="Rechnung fuer 44/22",
            body=("Sehr geehrte Damen und Herren,\n"
                  "anbei die Rechnung zu Aktenzeichen 44/22.\n"),
            anhang_name="rechnung.pdf",
        )
        from pathlib import Path
        from backend.email_import import import_service as isvc

        bericht = isvc._leerer_bericht()
        imap_mock = mock.MagicMock()
        with mock.patch.object(isvc, "markiere_als_gelesen"), \
             mock.patch.object(isvc, "verschiebe_in_ua"), \
             mock.patch.object(isvc, "starte_pdf_parsing"):
            isvc._verarbeite_eine(
                uid=b"1",
                roh_bytes=roh,
                imap=imap_mock,
                bericht=bericht,
                up_dir=Path(self._tmp),
                bearbeiter_id=None,
                konto="unfall",
            )
        return bericht

    def test_default_flag_true_schreibt_kein_dokument(self):
        os.environ.pop("INTAKE_REVIEW_PFLICHT", None)
        self._rufe_verarbeite()

        from backend.db.database import get_connection
        with get_connection() as conn:
            n_dok = conn.execute(
                "SELECT COUNT(*) FROM dokumente WHERE akte_id='44/22'"
            ).fetchone()[0]
            n_intake = conn.execute(
                "SELECT COUNT(*) FROM intake_dokumente"
            ).fetchone()[0]
            n_zust = conn.execute(
                "SELECT COUNT(*) FROM zustellungen"
            ).fetchone()[0]

        self.assertEqual(n_dok, 0,
                          "Unter INTAKE_REVIEW_PFLICHT darf keine "
                          "dokumente-Zeile fuer den Anhang entstehen")
        self.assertGreaterEqual(n_intake, 1,
                                 "IMAP-Adapter muss intake_dokumente anlegen")
        self.assertGreaterEqual(n_zust, 1,
                                 "IMAP-Adapter muss zustellungen anlegen")

    def test_flag_false_altpfad_schreibt_dokumente(self):
        os.environ["INTAKE_REVIEW_PFLICHT"] = "false"
        self._rufe_verarbeite()

        from backend.db.database import get_connection
        with get_connection() as conn:
            n_dok = conn.execute(
                "SELECT COUNT(*) FROM dokumente WHERE akte_id='44/22'"
            ).fetchone()[0]
        self.assertGreaterEqual(
            n_dok, 1,
            "Alt-Pfad (Flag=false) muss weiter dokumente-Zeilen anlegen",
        )


if __name__ == "__main__":
    unittest.main()
