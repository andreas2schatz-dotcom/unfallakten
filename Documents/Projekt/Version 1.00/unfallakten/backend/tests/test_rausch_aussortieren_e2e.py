"""E2E: adapter_imap.verarbeite_email sortiert Rausch-Absender automatisch aus."""
import os
import sys
import shutil
import tempfile
import unittest
import uuid
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _fresh_db(test_id, tmp_dir):
    db_path = os.path.join(tmp_dir, f"rausch_{test_id}.db")
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


def _minimales_pdf(sig=b""):
    return (
        b"%PDF-1.4\n%" + sig + b"\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        b"xref\n0 4\n0000000000 65535 f\n"
        b"0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n"
        b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF\n"
    )


def _email(von, body="Body.", anhaenge=None):
    msg = MIMEMultipart()
    msg["Subject"] = "Test"
    msg["From"] = von
    msg["To"] = "info@anwalt-offenbach.de"
    msg["Date"] = "Mon, 15 Mar 2025 10:30:00 +0100"
    msg["Message-ID"] = f"<{uuid.uuid4().hex}@test.de>"
    msg.attach(MIMEText(body, "plain", "utf-8"))
    for name, daten in (anhaenge or []):
        teil = MIMEApplication(daten, _subtype="pdf")
        teil.add_header("Content-Disposition", "attachment", filename=name)
        msg.attach(teil)
    return msg.as_bytes()


class TestRauschAussortieren(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="rausch_e2e_")
        os.environ["INTAKE_ARCHIV_ROOT"] = self._tmp
        self.db = _fresh_db(self._testMethodName, self._tmp)

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)
        os.environ.pop("INTAKE_ARCHIV_ROOT", None)

    def _zaehle(self, tabelle):
        with self.db.get_connection() as conn:
            return conn.execute(f"SELECT COUNT(*) FROM {tabelle}").fetchone()[0]

    def _zustellung(self, intake_id):
        with self.db.get_connection() as conn:
            return conn.execute(
                "SELECT id, parent_id FROM zustellungen WHERE intake_dokument_id=?",
                (intake_id,)).fetchone()

    def _verworfen(self, intake_id):
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT verworfen_am, verworfen_grund, verworfen_von "
                "FROM intake_dokumente WHERE id=?", (intake_id,),
            ).fetchone()
        return row

    def test_placetel_ohne_anhang_wird_gar_nicht_gespeichert(self):
        """Anrufbenachrichtigungen der Telefonanlage: nichts anlegen, auch
        keine Papierkorb-Zeile (Entscheidung RA Schatz, 2026-09-09)."""
        from backend.intake.adapter_imap import verarbeite_email
        res = verarbeite_email(_email("no-reply@placetel.de"), konto="info")
        self.assertIsNone(res["body"])
        self.assertEqual(res["anhaenge"], [])
        self.assertEqual(self._zaehle("intake_dokumente"), 0)
        self.assertEqual(self._zaehle("zustellungen"), 0)

    def test_placetel_mit_fax_nur_das_fax_wird_gespeichert(self):
        """Placetel liefert auch den Faxeingang -- der Anhang muss bleiben."""
        from backend.intake.adapter_imap import verarbeite_email
        res = verarbeite_email(
            _email("no-reply@placetel.de",
                   anhaenge=[("fax.pdf", _minimales_pdf(b"fax1"))]),
            konto="info",
        )
        self.assertIsNone(res["body"])
        self.assertEqual(len(res["anhaenge"]), 1)
        self.assertEqual(self._zaehle("intake_dokumente"), 1)

        anhang_id = res["anhaenge"][0]["intake_dokument_id"]
        self.assertIsNone(self._verworfen(anhang_id)["verworfen_am"])

    def test_placetel_fax_behaelt_absender_und_betreff_ohne_elternteil(self):
        """Ohne Body-Zustellung haengt das Fax an keinem Elternteil mehr; die
        Kopfdaten stehen auf der Anhang-Zustellung selbst."""
        from backend.intake.adapter_imap import verarbeite_email
        res = verarbeite_email(
            _email("no-reply@placetel.de",
                   anhaenge=[("fax.pdf", _minimales_pdf(b"fax2"))]),
            konto="info",
        )
        zust = self._zustellung(res["anhaenge"][0]["intake_dokument_id"])
        self.assertIsNone(zust["parent_id"])
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT absender, betreff, empfangen_am, konto FROM zustellungen "
                "WHERE id=?", (zust["id"],)).fetchone()
        self.assertIn("placetel.de", row["absender"])
        self.assertEqual(row["betreff"], "Test")
        self.assertEqual(row["konto"], "info")
        self.assertIsNotNone(row["empfangen_am"])

    def test_komplett_bleibt_reversibel_im_papierkorb(self):
        """Gegenprobe: komplett legt weiter an und verwirft nur -- Newsletter
        sollen nachlesbar bleiben, falls doch echte Post dabei war."""
        from backend.intake.adapter_imap import verarbeite_email
        verarbeite_email(_email("noreply@bea-brak.de"), konto="info")
        self.assertEqual(self._zaehle("intake_dokumente"), 1)

    def test_bea_mit_anhang_body_und_anhang_verworfen(self):
        from backend.intake.adapter_imap import verarbeite_email
        res = verarbeite_email(
            _email("noreply@bea-brak.de",
                   anhaenge=[("info.pdf", _minimales_pdf(b"bea1"))]),
            konto="info",
        )
        self.assertIsNotNone(
            self._verworfen(res["body"]["intake_dokument_id"])["verworfen_am"])
        anhang_id = res["anhaenge"][0]["intake_dokument_id"]
        self.assertIsNotNone(self._verworfen(anhang_id)["verworfen_am"])

    def test_bea_ohne_anhang_body_verworfen(self):
        from backend.intake.adapter_imap import verarbeite_email
        res = verarbeite_email(_email("noreply@bea-brak.de"), konto="info")
        self.assertIsNotNone(
            self._verworfen(res["body"]["intake_dokument_id"])["verworfen_am"])

    def test_normaler_absender_bleibt(self):
        from backend.intake.adapter_imap import verarbeite_email
        res = verarbeite_email(
            _email("mailer@versicherung.de",
                   anhaenge=[("brief.pdf", _minimales_pdf(b"v1"))]),
            konto="info",
        )
        self.assertIsNone(
            self._verworfen(res["body"]["intake_dokument_id"])["verworfen_am"])
        anhang_id = res["anhaenge"][0]["intake_dokument_id"]
        self.assertIsNone(self._verworfen(anhang_id)["verworfen_am"])


if __name__ == "__main__":
    unittest.main()
