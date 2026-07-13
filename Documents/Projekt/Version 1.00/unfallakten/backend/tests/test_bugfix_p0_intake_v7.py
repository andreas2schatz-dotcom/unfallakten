"""
Tests fuer die P0-Bugfixes aus docs/BUGFIX_INTAKE_V7.md (Code-Review 2026-07-12).

Abgedeckt:
  * BUG-03 -- Upload-Ziel-Akte wird als AZ-Signal durchgereicht (Falschablage).
  * BUG-02 -- Anhang-Registrierungsfehler wird nicht mehr stumm verschluckt.
  * BUG-01 -- Fragebogen-Mails landen in der Review-Queue statt verloren zu gehen.

Muster wie test_intake_adapter.py: eigene DB + Archiv-Root je Test, Import der
Produktivmodule INNERHALB der Testmethode (nach dem DB-Reload).
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
import uuid
from email.message import EmailMessage

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _fresh_db(test_id: str, tmp_dir: str):
    db_path = os.path.join(tmp_dir, f"p0_{test_id}.db")
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


class _P0TestBase(unittest.TestCase):
    def setUp(self):
        self._alt_flag = os.environ.get("INTAKE_REVIEW_PFLICHT")
        os.environ.pop("INTAKE_REVIEW_PFLICHT", None)  # Default True
        self._tmp = tempfile.mkdtemp(prefix="p0_test_")
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


# ── BUG-03: Upload-Ziel-Akte als Signal ──────────────────────────────────────


class TestBug03UploadZielAkte(_P0TestBase):
    def test_ziel_akte_wird_als_az_signal_geschrieben(self):
        from backend.intake.adapter_upload import verarbeite_datei
        verarbeite_datei(
            _minimales_pdf(b"bug03-a"),
            dateiname="brief.pdf",
            ziel_akte="285/26",
        )
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT signale_json FROM zustellungen WHERE quelle='upload'"
            ).fetchone()
        self.assertIsNotNone(row)
        signale = json.loads(row["signale_json"])
        self.assertEqual(signale.get("az"), "285/26",
                         "Ziel-Akte muss als 'az'-Signal durchgereicht werden")

    def test_ziel_akte_wird_top_kandidat_im_matching(self):
        with self.db.get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, status) VALUES ('285/26', 'offen')"
            )
        from backend.intake.adapter_upload import verarbeite_datei
        verarbeite_datei(
            _minimales_pdf(b"bug03-b"),
            dateiname="brief.pdf",
            ziel_akte="285/26",
        )
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT signale_json FROM zustellungen WHERE quelle='upload'"
            ).fetchone()
        signale = json.loads(row["signale_json"])

        from backend.intake.akten_matching import finde_kandidaten
        # Brieftext nennt nur ein FREMDES Schadenaktenzeichen -> ohne Signal
        # gaebe es keinen oder einen falschen Kandidaten.
        kandidaten = finde_kandidaten("Ihr Schaden-Az 999/99", [signale])
        self.assertTrue(kandidaten, "Ziel-Akte muss als Kandidat erscheinen")
        self.assertEqual(kandidaten[0].akte_az, "285/26")
        self.assertGreaterEqual(kandidaten[0].score, 0.9)


# ── BUG-02: Registrierungsfehler nicht stumm verschlucken ────────────────────


def _baue_rohemail(betreff, body, anhang_name="beleg.pdf", message_id=None):
    msg = EmailMessage()
    msg["Subject"] = betreff
    msg["From"] = "a@b.de"
    msg["To"] = "unfall@anwalt-offenbach.de"
    msg["Date"] = "Mon, 07 Jul 2026 10:00:00 +0200"
    msg["Message-ID"] = message_id or f"<{uuid.uuid4().hex}@x>"
    msg.set_content(body)
    if anhang_name:
        msg.add_attachment(_minimales_pdf(anhang_name.encode()),
                           maintype="application", subtype="pdf",
                           filename=anhang_name)
    return msg.as_bytes()


class TestBug02StillerFehler(_P0TestBase):
    def _rufe_mit_defektem_adapter(self):
        """Ruft ``_verarbeite_eine`` fuer eine Mail mit AZ-Treffer, waehrend der
        Intake-Adapter (einziger Registrierungspfad unter Review-Pflicht)
        wirft. Liefert (bericht, markiere_mock)."""
        from unittest import mock
        from pathlib import Path
        from backend.email_import import import_service as isvc

        with self.db.get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('44/22', '2022-04-27', 'offen')"
            )

        roh = _baue_rohemail(
            betreff="Rechnung fuer 44/22",
            body="Anbei die Rechnung zu Aktenzeichen 44/22.",
            message_id="<bug02-mid@x>",
        )
        bericht = isvc._leerer_bericht()
        imap_mock = mock.MagicMock()
        with mock.patch.object(isvc, "markiere_als_gelesen") as mark_mock, \
             mock.patch.object(isvc, "verschiebe_in_ua") as move_mock, \
             mock.patch.object(isvc, "starte_pdf_parsing"), \
             mock.patch(
                 "backend.intake.adapter_imap.verarbeite_email",
                 side_effect=RuntimeError("DB locked"),
             ):
            isvc._verarbeite_eine(
                uid=b"1", roh_bytes=roh, imap=imap_mock, bericht=bericht,
                up_dir=Path(self._tmp), bearbeiter_id=None, konto="unfall",
            )
        return bericht, mark_mock, move_mock

    def test_mail_bleibt_ungelesen_bei_registrierungsfehler(self):
        bericht, mark_mock, move_mock = self._rufe_mit_defektem_adapter()
        mark_mock.assert_not_called()
        move_mock.assert_not_called()

    def test_status_fehler_und_bericht_zaehlt_fehler(self):
        bericht, _mark, _move = self._rufe_mit_defektem_adapter()
        self.assertEqual(bericht["fehler"], 1)
        self.assertEqual(bericht["verarbeitet"], 0)
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT status FROM email_import_log"
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "fehler")


# ── BUG-01: Fragebogen landet in der Review-Queue statt verloren ─────────────


def _fragebogen_json(az="44/22", name="Mustermann"):
    return json.dumps({
        "meta": {"formular": "unfallbogen", "version": "2.1",
                 "aktenzeichen": az},
        "mandant": {"name": name, "vorname": "Max", "email": "max@x.de"},
        "gegner": {},
        "unfall": {"datum": "2022-04-27", "ort": "Offenbach"},
        "sachschaden": {},
        "personenschaden": None,
    }, ensure_ascii=False).encode("utf-8")


def _baue_fragebogen_mail(json_bytes,
                          betreff="Unfallbogen: Max Mustermann - 2022-04-27"):
    msg = EmailMessage()
    msg["Subject"] = betreff
    msg["From"] = "max@x.de"
    msg["To"] = "unfall@anwalt-offenbach.de"
    msg["Date"] = "Mon, 07 Jul 2026 10:00:00 +0200"
    msg["Message-ID"] = "<fragebogen-mid@x>"
    msg.set_content("Anbei mein Unfallbogen.")
    msg.add_attachment(json_bytes, maintype="application", subtype="json",
                       filename="unfallbogen_test.json")
    return msg.as_bytes()


class TestBug01FragebogenInQueue(_P0TestBase):
    def _verarbeite(self, json_bytes=None):
        from unittest import mock
        from pathlib import Path
        from backend.email_import import import_service as isvc

        with self.db.get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('44/22', '2022-04-27', 'offen')"
            )
        roh = _baue_fragebogen_mail(json_bytes or _fragebogen_json())
        bericht = isvc._leerer_bericht()
        imap_mock = mock.MagicMock()
        with mock.patch.object(isvc, "markiere_als_gelesen"), \
             mock.patch.object(isvc, "verschiebe_in_ua"):
            isvc._verarbeite_eine(
                uid=b"1", roh_bytes=roh, imap=imap_mock, bericht=bericht,
                up_dir=Path(self._tmp), bearbeiter_id=None, konto="unfall",
            )
        return bericht

    def test_fragebogen_landet_als_intake_dokument_in_queue(self):
        self._verarbeite()
        with self.db.get_connection() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM intake_dokumente"
            ).fetchone()[0]
        self.assertGreaterEqual(
            n, 1, "Fragebogen muss als intake_dokument in der Queue liegen")

    def test_zustellung_traegt_az_signal(self):
        self._verarbeite()
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT signale_json FROM zustellungen"
            ).fetchall()
        az_treffer = any(
            json.loads(r["signale_json"] or "{}").get("az") == "44/22"
            for r in rows
        )
        self.assertTrue(az_treffer,
                        "Zustellung muss az='44/22' als Signal tragen "
                        "(Akte im Review vorbelegt)")

    def test_fragebogen_inhalt_bleibt_erhalten(self):
        self._verarbeite()
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT structured_payload FROM intake_dokumente "
                "WHERE structured_payload IS NOT NULL"
            ).fetchall()
        gesamt = " ".join(r["structured_payload"] or "" for r in rows)
        self.assertIn("Mustermann", gesamt,
                      "Fragebogen-Antworten duerfen nicht verloren gehen")

    def test_beteiligte_werden_nicht_auto_befuellt(self):
        # Unter Review-Pflicht bleibt das Auto-Enrichment aus (K-P1) --
        # Uebernahme erst mit Freigabe.
        self._verarbeite()
        with self.db.get_connection() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM beteiligte WHERE akte_id='44/22'"
            ).fetchone()[0]
        self.assertEqual(n, 0,
                         "Fragebogen darf Beteiligte nicht automatisch anlegen")


if __name__ == "__main__":
    unittest.main()
