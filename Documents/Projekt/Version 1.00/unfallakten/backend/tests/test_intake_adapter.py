"""
Tests fuer die S1.3-Adapter (intake/adapter_imap.py, adapter_upload.py, adapter_eakte.py).

Anforderungen aus PIPELINE-REFACTORING-PLAN.md S1.3:

  * Adapter erzeugen fuer jede Zustellung eine ``zustellungen``-Zeile und
    fuegen — falls neu (sha256) — eine ``intake_dokumente``-Zeile hinzu.
  * IMAP-Adapter zerlegt eine E-Mail in: **Body als eigene Text-Payload**
    + n Anhaenge als Datei-Payloads. Alle drei sind eigene Zustellungen mit
    gemeinsamer ``parent_id`` (Body ist Parent, Anhaenge haengen daran).
  * Encoding-Handling (UTF-16 BOM) liegt AUSSCHLIESSLICH im IMAP-Adapter —
    email_parser importiert die Helferfunktion, dupliziert sie nicht.
  * Hash-Duplikat -> KEINE neue intake_dokumente-Zeile, aber neue Zustellung.
  * Upload-Adapter und E-Akte-Adapter erzeugen jeweils eine intake_dokumente-
    Zeile (idempotent per sha256) und eine ``zustellungen``-Zeile mit
    ``quelle='upload'`` bzw. ``quelle='eakte'``.
  * Der Alt-Pfad wird NICHT umgestellt (Doppelschreiben); die Regressionstests
    in test_modul7.py bleiben unveraendert.

Testkriterium aus dem Plan (freigabe.md / PIPELINE-REFACTORING-PLAN.md):
    Test-E-Mail mit 2 Anhaengen -> 3 Zustellungen (Body + 2 Anhaenge, gemeinsame
    parent_id) + 3 Dokumente; identischer Anhang aus zweiter E-Mail -> keine
    neue Dokument-Zeile, aber neue Zustellung.
"""
import hashlib
import io
import os
import sys
import tempfile
import shutil
import unittest
import uuid
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ── Test-Datenbank Setup ─────────────────────────────────────────────────────


def _fresh_db(test_id: str, tmp_dir: str):
    """
    Frische DB mit vollem Schema inkl. Migration 46 (intake_dokumente,
    zustellungen, freigaben, korrektur_log). Reload aller relevanten
    Module, damit DB_PATH neu gelesen wird.
    """
    db_path = os.path.join(tmp_dir, f"m7ad_{test_id}.db")
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


# ── Test-Fixtures ────────────────────────────────────────────────────────────


def _erstelle_email(
    betreff: str = "Test",
    von: str = "test@example.de",
    body: str = "Hallo, dies ist ein Test-Body.",
    message_id: str | None = None,
    anhaenge: list | None = None,
    datum: str = "Mon, 15 Mar 2025 10:30:00 +0100",
) -> bytes:
    """Erstellt rohe RFC-822-Bytes fuer Tests."""
    msg = MIMEMultipart()
    msg["Subject"] = betreff
    msg["From"] = von
    msg["To"] = "unfall@anwalt-offenbach.de"
    msg["Date"] = datum
    msg["Message-ID"] = message_id or f"<{uuid.uuid4().hex}@test.de>"
    msg.attach(MIMEText(body, "plain", "utf-8"))
    for dateiname, daten, mime_typ in (anhaenge or []):
        teil = MIMEApplication(daten, _subtype=mime_typ.split("/")[-1])
        teil.add_header("Content-Disposition", "attachment", filename=dateiname)
        msg.attach(teil)
    return msg.as_bytes()


def _minimales_pdf(sig: bytes = b"") -> bytes:
    """Minimal gueltiges PDF; ``sig`` variiert den Inhalt (=> anderer sha256)."""
    return (
        b"%PDF-1.4\n%" + sig + b"\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        b"xref\n0 4\n0000000000 65535 f\n"
        b"0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n"
        b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF\n"
    )


class _AdapterTestBase(unittest.TestCase):
    """Gemeinsames Setup: eigene DB + Archiv-Root je Test."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="adapter_test_")
        os.environ["INTAKE_ARCHIV_ROOT"] = self._tmp
        self.db = _fresh_db(self._testMethodName, self._tmp)

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)
        os.environ.pop("INTAKE_ARCHIV_ROOT", None)


# ── IMAP-Adapter: Kernkriterium aus dem Plan ────────────────────────────────


class TestAdapterImap(_AdapterTestBase):
    """
    Kernkriterium (freigabe.md, PIPELINE-REFACTORING-PLAN.md S1.3):
        Test-E-Mail mit 2 Anhaengen -> 3 Zustellungen (Body + 2 Anhaenge,
        gemeinsame parent_id) + 3 Dokumente; identischer Anhang aus zweiter
        E-Mail -> keine neue Dokument-Zeile, aber neue Zustellung.
    """

    def test_email_mit_zwei_anhaengen_erzeugt_drei_zustellungen_und_drei_dokumente(self):
        from backend.intake.adapter_imap import verarbeite_email
        pdf_a = _minimales_pdf(b"pdf-a-unique-body")
        pdf_b = _minimales_pdf(b"pdf-b-unique-body")
        roh = _erstelle_email(
            betreff="Test S1.3",
            von="mailer@versicherung.de",
            body="Body-Text.",
            message_id="<s13-1@test.de>",
            anhaenge=[
                ("a.pdf", pdf_a, "application/pdf"),
                ("b.pdf", pdf_b, "application/pdf"),
            ],
        )
        verarbeite_email(roh, konto="unfall")

        with self.db.get_connection() as conn:
            n_dok = conn.execute(
                "SELECT COUNT(*) FROM intake_dokumente"
            ).fetchone()[0]
            n_zust = conn.execute(
                "SELECT COUNT(*) FROM zustellungen WHERE quelle = 'imap'"
            ).fetchone()[0]
        self.assertEqual(n_dok, 3, "Body + 2 Anhaenge = 3 intake_dokumente")
        self.assertEqual(n_zust, 3, "Body + 2 Anhaenge = 3 zustellungen (quelle=imap)")

    def test_anhaenge_teilen_parent_id_des_body(self):
        from backend.intake.adapter_imap import verarbeite_email
        roh = _erstelle_email(
            body="Body.",
            message_id="<parent-id-1@test.de>",
            anhaenge=[
                ("a.pdf", _minimales_pdf(b"pdfA"), "application/pdf"),
                ("b.pdf", _minimales_pdf(b"pdfB"), "application/pdf"),
            ],
        )
        verarbeite_email(roh, konto="unfall")

        with self.db.get_connection() as conn:
            body_row = conn.execute(
                "SELECT id FROM zustellungen "
                "WHERE quelle='imap' AND parent_id IS NULL"
            ).fetchone()
            self.assertIsNotNone(body_row, "Body-Zustellung nicht gefunden")

            kinder = conn.execute(
                "SELECT parent_id FROM zustellungen "
                "WHERE quelle='imap' AND parent_id IS NOT NULL"
            ).fetchall()

        self.assertEqual(len(kinder), 2)
        parent_ids = {r[0] for r in kinder}
        self.assertEqual(parent_ids, {body_row[0]},
                         "Beide Anhaenge muessen parent_id = Body-Zustellungs-ID haben")

    def test_identischer_anhang_erzeugt_keine_neue_dokument_zeile_aber_neue_zustellung(self):
        from backend.intake.adapter_imap import verarbeite_email
        pdf_a = _minimales_pdf(b"identisch-A")

        roh1 = _erstelle_email(
            betreff="Erste Mail",
            message_id="<mail-1@test.de>",
            body="Body 1.",
            anhaenge=[("a.pdf", pdf_a, "application/pdf")],
        )
        roh2 = _erstelle_email(
            betreff="Zweite Mail",
            message_id="<mail-2@test.de>",
            body="Body 2 komplett anders.",
            anhaenge=[("a.pdf", pdf_a, "application/pdf")],
        )
        verarbeite_email(roh1, konto="unfall")
        verarbeite_email(roh2, konto="unfall")

        pdf_hash = hashlib.sha256(pdf_a).hexdigest()

        with self.db.get_connection() as conn:
            anhang_dok = conn.execute(
                "SELECT COUNT(*) FROM intake_dokumente WHERE sha256 = ?",
                (pdf_hash,),
            ).fetchone()[0]
            anhang_zust = conn.execute(
                "SELECT COUNT(*) FROM zustellungen z "
                "JOIN intake_dokumente d ON z.intake_dokument_id = d.id "
                "WHERE d.sha256 = ? AND z.quelle = 'imap'",
                (pdf_hash,),
            ).fetchone()[0]

        self.assertEqual(anhang_dok, 1,
                         "Identischer Anhang darf NUR EINE intake_dokumente-Zeile haben")
        self.assertEqual(anhang_zust, 2,
                         "Der identische Anhang muss ZWEI zustellungen-Zeilen haben")

    def test_body_wird_als_text_payload_erfasst(self):
        from backend.intake.adapter_imap import verarbeite_email
        roh = _erstelle_email(
            body="Erkennbarer Body-Text 12345.",
            message_id="<body-typ-1@test.de>",
        )
        verarbeite_email(roh, konto="unfall")

        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT d.payload_typ, d.structured_payload "
                "FROM intake_dokumente d "
                "JOIN zustellungen z ON z.intake_dokument_id = d.id "
                "WHERE z.quelle = 'imap' AND z.parent_id IS NULL"
            ).fetchone()
        self.assertIsNotNone(row, "Body-Datensatz nicht gefunden")
        self.assertEqual(row[0], "text",
                         "Body muss payload_typ='text' haben")
        self.assertIn("Erkennbarer Body-Text 12345.", row[1] or "",
                      "Body-Text muss in structured_payload liegen")

    def test_konto_und_absender_landen_in_zustellungen(self):
        from backend.intake.adapter_imap import verarbeite_email
        roh = _erstelle_email(
            von="max@example.de",
            betreff="Signale-Test",
            message_id="<sig-1@test.de>",
        )
        verarbeite_email(roh, konto="bussgeld")

        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT konto, absender, betreff FROM zustellungen "
                "WHERE quelle='imap' AND parent_id IS NULL"
            ).fetchone()
        self.assertEqual(row["konto"], "bussgeld")
        self.assertIn("max@example.de", row["absender"] or "")
        self.assertEqual(row["betreff"], "Signale-Test")


class TestAdapterImapUtf16(_AdapterTestBase):
    """
    Die UTF-16-BOM-Logik lebt AUSSCHLIESSLICH im IMAP-Adapter. Direkte
    Verifizierung der Helferfunktion, damit ein Regress beim spaeteren
    Umzug sofort auffaellt.
    """

    def test_utf16_bom_wird_dekodiert(self):
        from backend.intake.adapter_imap import dekodiere_email_payload
        text = "Umlauttest Aeoeue"
        payload = b"\xff\xfe" + text.encode("utf-16-le")
        # Adapter darf den charset-Hinweis ignorieren wenn BOM praesent.
        result = dekodiere_email_payload(payload, charset="us-ascii")
        self.assertIn("Umlauttest", result)


# ── Upload-Adapter ────────────────────────────────────────────────────────────


class TestAdapterUpload(_AdapterTestBase):

    def test_upload_erzeugt_intake_und_zustellung(self):
        from backend.intake.adapter_upload import verarbeite_datei
        pdf = _minimales_pdf(b"upload-1")
        verarbeite_datei(pdf, dateiname="mein.pdf")

        with self.db.get_connection() as conn:
            n_dok = conn.execute(
                "SELECT COUNT(*) FROM intake_dokumente"
            ).fetchone()[0]
            n_zust = conn.execute(
                "SELECT COUNT(*) FROM zustellungen WHERE quelle = 'upload'"
            ).fetchone()[0]
        self.assertEqual(n_dok, 1)
        self.assertEqual(n_zust, 1)

    def test_upload_dedupliziert_intake_bei_identischem_hash(self):
        from backend.intake.adapter_upload import verarbeite_datei
        pdf = _minimales_pdf(b"upload-dedup")
        verarbeite_datei(pdf, dateiname="a.pdf")
        verarbeite_datei(pdf, dateiname="b.pdf")

        with self.db.get_connection() as conn:
            n_dok = conn.execute(
                "SELECT COUNT(*) FROM intake_dokumente"
            ).fetchone()[0]
            n_zust = conn.execute(
                "SELECT COUNT(*) FROM zustellungen WHERE quelle = 'upload'"
            ).fetchone()[0]
        self.assertEqual(n_dok, 1, "sha256-Duplikat darf keine zweite Dokument-Zeile erzeugen")
        self.assertEqual(n_zust, 2, "Beide Uploads muessen eigene Zustellungen haben")


# ── E-Akte-Adapter ────────────────────────────────────────────────────────────


class TestAdapterEakte(_AdapterTestBase):

    def test_eakte_erzeugt_intake_und_zustellung(self):
        from backend.intake.adapter_eakte import verarbeite_eakte_dokument
        pdf = _minimales_pdf(b"eakte-1")
        quelldatei = os.path.join(self._tmp, "eakte_src.pdf")
        with open(quelldatei, "wb") as f:
            f.write(pdf)

        verarbeite_eakte_dokument(quelldatei, akte_az="42/25AS", eakte_nr=100)

        with self.db.get_connection() as conn:
            n_dok = conn.execute(
                "SELECT COUNT(*) FROM intake_dokumente"
            ).fetchone()[0]
            row = conn.execute(
                "SELECT quelle, roh_referenz FROM zustellungen "
                "WHERE quelle = 'eakte'"
            ).fetchone()
        self.assertEqual(n_dok, 1)
        self.assertIsNotNone(row)
        # eakte_nr sollte als Referenz-Anhalt in roh_referenz enthalten sein.
        self.assertIn("100", row["roh_referenz"] or "")


if __name__ == "__main__":
    unittest.main()
