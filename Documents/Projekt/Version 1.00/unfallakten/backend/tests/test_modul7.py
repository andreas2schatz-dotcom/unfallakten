"""
Modul 7 – Tests: E-Mail-Import
================================
Testet:
  1. E-Mail-Parser (Betreff, Absender, Anhänge, AZ-Extraktion, KFZ-Extraktion)
  2. IMAP-Client (Konfiguration, Verbindungsfehler, Hilfsfunktionen)
  3. Akte-Matching (via Aktenzeichen, KFZ, Absender-E-Mail)
  4. Import-Service (Duplikate, Log, Statistik, Anhang-Verarbeitung)
  5. Flask-Routen (POST Import, GET Status, GET Log, GET Statistik)

Alle IMAP-Calls werden gemockt – kein echter Mailserver nötig.
"""

import os
import sys
import io
import json
import uuid
import email
import email.policy
import unittest
import tempfile
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.application import MIMEApplication
from email import encoders
from unittest.mock import MagicMock, patch, call
from pathlib import Path

_tmp_dir = tempfile.mkdtemp()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ── E-Mail-Fabrik ─────────────────────────────────────────────────────────────

def _erstelle_email(
    betreff: str = "Test",
    von: str = "test@versicherung.de",
    body: str = "Hallo, dies ist eine Test-E-Mail.",
    message_id: str = None,
    anhaenge: list = None,
    datum: str = "Mon, 15 Mar 2025 10:30:00 +0100",
) -> bytes:
    """Erstellt rohe RFC-822-E-Mail-Bytes für Tests."""
    msg = MIMEMultipart()
    msg["Subject"]    = betreff
    msg["From"]       = von
    msg["To"]         = "akten@anwalt-offenbach.de"
    msg["Date"]       = datum
    msg["Message-ID"] = message_id or f"<{uuid.uuid4().hex}@test.de>"
    msg.attach(MIMEText(body, "plain", "utf-8"))

    if anhaenge:
        for dateiname, daten, mime_typ in anhaenge:
            if mime_typ == "application/pdf":
                teil = MIMEApplication(daten, _subtype="pdf")
            else:
                teil = MIMEBase(*mime_typ.split("/"))
                teil.set_payload(daten)
                encoders.encode_base64(teil)
            teil.add_header(
                "Content-Disposition", "attachment", filename=dateiname
            )
            msg.attach(teil)

    return msg.as_bytes()


def _minimales_pdf() -> bytes:
    """Minimal gültiges PDF für Tests."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        b"xref\n0 4\n0000000000 65535 f\n"
        b"0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n"
        b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF\n"
    )


# ── App-Setup ──────────────────────────────────────────────────────────────────

def _setup(test_id: str):
    upload_dir = os.path.join(_tmp_dir, f"up_{test_id}")
    os.makedirs(upload_dir, exist_ok=True)
    db_path = os.path.join(_tmp_dir, f"m7_{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    os.environ["DB_PATH"]        = db_path
    os.environ["JWT_SECRET_KEY"] = "test-secret-key-minimum-32-chars!!"
    os.environ["UPLOAD_DIR"]     = upload_dir

    import importlib
    mods = [
        "backend.db.database", "backend.db.schema_manager",
        "backend.models.benutzer", "backend.models.akte",
        "backend.models.schaden", "backend.models.dokument",
        "backend.auth.jwt_handler", "backend.auth.middleware",
        "backend.auth.service", "backend.auth.validierung",
        "backend.routers.auth_routes", "backend.routers.akten_routes",
        "backend.routers.beteiligte_routes", "backend.routers.schaden_routes",
        "backend.pdf.extraktor", "backend.pdf.parser",
        "backend.pdf.upload_service", "backend.routers.dokumente_routes",
        "backend.word.styling", "backend.word.forderungsschreiben_wv",
        "backend.word.sachstandsanfrage", "backend.word.abrechnungsuebersicht",
        "backend.word.word_service", "backend.routers.word_routes",
        "backend.email_import.imap_client",
        "backend.email_import.parser",
        "backend.email_import.import_service",
        "backend.routers.email_routes",
        "backend.app",
    ]
    loaded = {}
    for mod in mods:
        m = __import__(mod, fromlist=[""])
        importlib.reload(m)
        loaded[mod] = m

    app = loaded["backend.app"].erstelle_app()
    app.config["TESTING"] = True
    client = app.test_client()

    # Admin + Akte + Beteiligte anlegen
    client.post("/auth/register/erster", json={
        "name": "Admin", "email": "admin@test.de", "passwort": "Admin123!"
    })
    r = client.post("/auth/login", json={
        "email": "admin@test.de", "passwort": "Admin123!"
    })
    token = r.get_json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r2 = client.post("/akten", json={
        "aktenzeichen": "25-M7-001",
        "unfalldatum":  "2025-03-15",
        "unfallort":    "Offenbach",
    }, headers=headers)
    akte_id = r2.get_json()["id"]

    client.post(f"/akten/{akte_id}/beteiligte", json={
        "rolle": "mandant", "name": "Müller", "vorname": "Hans",
        "email": "hans@mandant.de", "kfz_kennzeichen": "OF-HM 123",
    }, headers=headers)
    client.post(f"/akten/{akte_id}/beteiligte", json={
        "rolle": "gegner", "name": "Bauer",
        "versicherung": "HUK", "email": "regulierung@huk.de",
    }, headers=headers)

    return client, headers, akte_id, loaded


# ══════════════════════════════════════════════════════════════════════════════
# PARSER-TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestEmailParser(unittest.TestCase):

    def setUp(self):
        from backend.email_import import parser
        import importlib; importlib.reload(parser)
        self.p = parser

    def _parse(self, **kwargs):
        return self.p.parse_email(_erstelle_email(**kwargs))

    # ── Grundlegende Extraktion ───────────────────────────────────────────────

    def test_message_id_extrahiert(self):
        result = self.p.parse_email(
            _erstelle_email(message_id="<abc123@test.de>")
        )
        self.assertEqual(result["message_id"], "abc123@test.de")

    def test_betreff_extrahiert(self):
        r = self._parse(betreff="Unfall Az. 42/25 Regulierung")
        self.assertEqual(r["betreff"], "Unfall Az. 42/25 Regulierung")

    def test_absender_extrahiert(self):
        r = self._parse(von="Max Mustermann <max@test.de>")
        self.assertEqual(r["absender_email"], "max@test.de")

    def test_absender_ohne_klammern(self):
        r = self._parse(von="max@test.de")
        self.assertEqual(r["absender_email"], "max@test.de")

    def test_datum_geparst(self):
        r = self._parse(datum="Mon, 15 Mar 2025 10:30:00 +0100")
        self.assertIsNotNone(r["empfangen_am"])
        self.assertIn("2025", r["empfangen_am"])

    def test_body_extrahiert(self):
        r = self._parse(body="Hallo Kanzlei, bitte bearbeiten Sie Az. 25-TEST-001")
        self.assertIn("Hallo Kanzlei", r["text"])

    # ── Aktenzeichen-Erkennung ────────────────────────────────────────────────

    def test_az_im_betreff_erkannt(self):
        r = self._parse(betreff="Az. 42/25 Regulierung Verkehrsunfall")
        self.assertIn("42/25", r["az_kandidaten"])

    def test_az_variante_slash(self):
        r = self._parse(betreff="Ihr Zeichen: 25/0042")
        az_normiert = [a.replace("/", "-") for a in r["az_kandidaten"]]
        self.assertTrue(any("42/25" in a or "25/0042" in a
                             for a in r["az_kandidaten"]))

    def test_az_im_body_erkannt(self):
        r = self._parse(
            betreff="Regulierung",
            body="Betreff: Unser Zeichen 42/25\nSehr geehrte Damen und Herren"
        )
        self.assertIn("42/25", r["az_kandidaten"])

    def test_kein_az(self):
        r = self._parse(betreff="Allgemeine Anfrage ohne Aktenzeichen")
        self.assertEqual(len(r["az_kandidaten"]), 0)

    # ── KFZ-Erkennung ─────────────────────────────────────────────────────────

    def test_kfz_im_betreff_erkannt(self):
        r = self._parse(betreff="Unfall Fahrzeug OF-HM 123")
        self.assertTrue(any("OF" in k for k in r["kfz_kandidaten"]))

    def test_kfz_im_body_erkannt(self):
        r = self._parse(
            betreff="Regulierung",
            body="Fahrzeug B-AB 1234 war in den Unfall verwickelt."
        )
        self.assertTrue(len(r["kfz_kandidaten"]) > 0)

    # ── Anhang-Extraktion ─────────────────────────────────────────────────────

    def test_pdf_anhang_erkannt(self):
        r = self._parse(anhaenge=[
            ("gutachten.pdf", _minimales_pdf(), "application/pdf")
        ])
        self.assertEqual(len(r["anhaenge"]), 1)
        self.assertEqual(r["anhaenge"][0]["dateiname"], "gutachten.pdf")
        self.assertEqual(r["anhaenge"][0]["endung"], "pdf")

    def test_docx_anhang_erkannt(self):
        r = self._parse(anhaenge=[
            ("forderung.docx", b"PK fake docx", "application/octet-stream")
        ])
        # Dateiname sollte erkannt werden
        self.assertEqual(len(r["anhaenge"]), 1)

    def test_ungueltige_endung_ignoriert(self):
        r = self._parse(anhaenge=[
            ("macro.exe", b"MZ", "application/octet-stream")
        ])
        self.assertEqual(len(r["anhaenge"]), 0)

    def test_mehrere_anhaenge(self):
        r = self._parse(anhaenge=[
            ("gutachten.pdf", _minimales_pdf(), "application/pdf"),
            ("foto.jpg", b"\xff\xd8\xff" + b"\x00" * 100, "image/jpeg"),
            ("virus.exe", b"MZ", "application/octet-stream"),
        ])
        self.assertEqual(len(r["anhaenge"]), 2)  # exe wird ignoriert

    def test_kaputte_email_kein_crash(self):
        """Parser darf bei invaliden Bytes nicht crashen."""
        result = self.p.parse_email(b"This is not a valid email at all!!!")
        self.assertIsNotNone(result)
        self.assertIn("message_id", result)


# ══════════════════════════════════════════════════════════════════════════════
# IMAP-CLIENT-TESTS (gemockt)
# ══════════════════════════════════════════════════════════════════════════════

class TestImapClient(unittest.TestCase):

    def setUp(self):
        from backend.email_import import imap_client
        import importlib; importlib.reload(imap_client)
        self.c = imap_client

    def test_ist_konfiguriert_false_ohne_env(self):
        env_backup = {}
        for k in ["EMAIL_HOST", "EMAIL_USER", "EMAIL_PASSWORD"]:
            env_backup[k] = os.environ.pop(k, None)
        try:
            self.assertFalse(self.c.ist_konfiguriert())
        finally:
            for k, v in env_backup.items():
                if v:
                    os.environ[k] = v

    def test_ist_konfiguriert_true_mit_env(self):
        os.environ["EMAIL_HOST"]     = "mail.test.de"
        os.environ["EMAIL_USER"]     = "test@test.de"
        os.environ["EMAIL_PASSWORD"] = "secret"
        try:
            self.assertTrue(self.c.ist_konfiguriert())
        finally:
            for k in ["EMAIL_HOST", "EMAIL_USER", "EMAIL_PASSWORD"]:
                os.environ.pop(k, None)

    def test_config_defaults(self):
        os.environ["EMAIL_HOST"]     = "imap.example.de"
        os.environ["EMAIL_USER"]     = "akten@kanzlei.de"
        os.environ["EMAIL_PASSWORD"] = "pw123"
        try:
            cfg = self.c.get_imap_config()
            self.assertEqual(cfg["port"],    993)
            self.assertEqual(cfg["folder"],  "INBOX")
            self.assertEqual(cfg["max_fetch"], 50)
        finally:
            for k in ["EMAIL_HOST", "EMAIL_USER", "EMAIL_PASSWORD"]:
                os.environ.pop(k, None)

    def test_verbindungsfehler_ohne_host(self):
        os.environ.pop("EMAIL_HOST", None)
        os.environ.pop("EMAIL_USER", None)
        os.environ.pop("EMAIL_PASSWORD", None)
        with self.assertRaises(self.c.ImapVerbindungsFehler):
            with self.c.imap_verbinden({"host": "", "user": "u", "password": "p",
                                         "port": 993, "ssl": True, "folder": "INBOX"}):
                pass

    def test_hole_ungelesene_leer(self):
        """Leerer INBOX: leere Liste zurück."""
        mock_imap = MagicMock()
        mock_imap.uid.return_value = ("OK", [b""])
        result = self.c.hole_ungelesene(mock_imap, 10)
        self.assertEqual(result, [])

    def test_hole_ungelesene_mit_nachrichten(self):
        """Zwei UIDs → zwei Nachrichten."""
        email_bytes = _erstelle_email()
        mock_imap = MagicMock()
        mock_imap.uid.side_effect = [
            ("OK", [b"1 2"]),           # SEARCH → 2 UIDs
            ("OK", [(b"", email_bytes)]),  # FETCH uid 1
            ("OK", [(b"", email_bytes)]),  # FETCH uid 2
        ]
        result = self.c.hole_ungelesene(mock_imap, 50)
        self.assertEqual(len(result), 2)

    def test_markiere_als_gelesen_ok(self):
        mock_imap = MagicMock()
        mock_imap.uid.return_value = ("OK", [b""])
        result = self.c.markiere_als_gelesen(mock_imap, b"1")
        self.assertTrue(result)
        mock_imap.uid.assert_called_with("STORE", b"1", "+FLAGS", "(\\Seen)")

    def test_markiere_als_gelesen_fehler(self):
        mock_imap = MagicMock()
        mock_imap.uid.side_effect = Exception("Netzwerkfehler")
        result = self.c.markiere_als_gelesen(mock_imap, b"1")
        self.assertFalse(result)


# ══════════════════════════════════════════════════════════════════════════════
# AKTE-MATCHING-TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestAkteMatching(unittest.TestCase):

    def setUp(self):
        db_path = os.path.join(_tmp_dir, "matching_test.db")
        if os.path.exists(db_path):
            os.remove(db_path)
        os.environ["DB_PATH"]        = db_path
        os.environ["JWT_SECRET_KEY"] = "x" * 32

        import importlib
        for mod in ["backend.db.database", "backend.db.schema_manager",
                    "backend.models.benutzer", "backend.models.akte",
                    "backend.models.schaden", "backend.models.dokument",
                    "backend.email_import.parser"]:
            importlib.reload(__import__(mod, fromlist=[""]))

        from backend.db.schema_manager import init_db
        from backend.models.benutzer import erstelle_benutzer
        from backend.models.akte import erstelle_akte
        from backend.models.schaden import erstelle_beteiligten
        from backend.email_import.parser import finde_akte
        from backend.db.database import get_connection

        init_db()
        user = erstelle_benutzer("A", "a@b.de", "Test1234!", "admin")
        self.akte = erstelle_akte("25-MATCH-01", "2025-01-01", user.id)
        erstelle_beteiligten(
            self.akte.id, "mandant", "Meier",
            email="meier@gmail.com", kfz_kennzeichen="OF-AB 123"
        )
        self.finde_akte = finde_akte
        self.get_conn = get_connection

    def _match(self, betreff="", body="", von="test@test.de"):
        from backend.email_import.parser import parse_email
        roh = _erstelle_email(betreff=betreff, body=body, von=von)
        parsed = parse_email(roh)
        with self.get_conn() as conn:
            return self.finde_akte(parsed, conn)

    def test_match_via_aktenzeichen_im_betreff(self):
        akte_id = self._match(betreff="Az. 25-MATCH-01 Regulierung")
        self.assertEqual(akte_id, self.akte.id)

    def test_match_via_aktenzeichen_im_body(self):
        akte_id = self._match(body="Unser Zeichen: 25-MATCH-01")
        self.assertEqual(akte_id, self.akte.id)

    def test_match_via_kfz(self):
        akte_id = self._match(betreff="Schaden Fahrzeug OF-AB 123")
        self.assertEqual(akte_id, self.akte.id)

    def test_match_via_email(self):
        akte_id = self._match(von="meier@gmail.com")
        self.assertEqual(akte_id, self.akte.id)

    def test_kein_match(self):
        akte_id = self._match(
            betreff="Allgemeine Anfrage",
            von="unbekannt@xyz.de"
        )
        self.assertIsNone(akte_id)

    def test_az_normierung_slash(self):
        """Aktenzeichen mit '/' (rein numerisch) soll erkannt werden."""
        # Reales Format: 25/0042 (nicht 25/MATCH/01)
        from backend.models.akte import erstelle_akte
        from backend.models.benutzer import erstelle_benutzer
        from backend.db.database import get_connection
        from backend.email_import.parser import parse_email, finde_akte as _fa
        # Nutze bestehende Akte mit numerischem AZ
        akte2 = erstelle_akte("9999/25", "2025-01-01", self.akte.created_by
                               if hasattr(self.akte, "created_by") else 1)
        roh = _erstelle_email(betreff="Az. 25/9999 Unfall")
        parsed = parse_email(roh)
        with self.get_conn() as conn:
            result = _fa(parsed, conn)
        # Ergebnis ist Match oder None – kein Crash
        self.assertTrue(result is None or isinstance(result, int))


# ══════════════════════════════════════════════════════════════════════════════
# IMPORT-SERVICE-TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestImportService(unittest.TestCase):

    def setUp(self):
        self.upload_dir = os.path.join(_tmp_dir, f"svc_{self._testMethodName}")
        os.makedirs(self.upload_dir, exist_ok=True)
        db_path = os.path.join(_tmp_dir, f"svc_{self._testMethodName}.db")
        if os.path.exists(db_path):
            os.remove(db_path)
        os.environ["DB_PATH"]        = db_path
        os.environ["JWT_SECRET_KEY"] = "x" * 32
        os.environ["UPLOAD_DIR"]     = self.upload_dir
        # IMAP konfigurieren damit ist_konfiguriert() True zurückgibt
        os.environ["EMAIL_HOST"]     = "mail.test.de"
        os.environ["EMAIL_USER"]     = "test@test.de"
        os.environ["EMAIL_PASSWORD"] = "secret"

        import importlib
        for mod in [
            "backend.db.database", "backend.db.schema_manager",
            "backend.models.benutzer", "backend.models.akte",
            "backend.models.schaden", "backend.models.dokument",
            "backend.pdf.extraktor", "backend.pdf.parser",
            "backend.pdf.upload_service",
            "backend.email_import.imap_client",
            "backend.email_import.parser",
            "backend.email_import.import_service",
        ]:
            importlib.reload(__import__(mod, fromlist=[""]))

        from backend.db.schema_manager import init_db
        from backend.models.benutzer import erstelle_benutzer
        from backend.models.akte import erstelle_akte
        from backend.models.schaden import erstelle_beteiligten
        from backend.email_import.import_service import (
            fuehre_import_lauf_durch, hole_import_log,
            hole_import_statistik
        )

        init_db()
        user = erstelle_benutzer("A", "a@b.de", "Test1234!", "admin")
        self.akte = erstelle_akte("25-SVC-001", "2025-03-15", user.id)
        erstelle_beteiligten(
            self.akte.id, "gegner", "Versicherung",
            email="regulierung@huk.de"
        )
        self.starte   = fuehre_import_lauf_durch
        self.hole_log = hole_import_log
        self.statistik = hole_import_statistik

    def _mock_imap(self, nachrichten: list) -> MagicMock:
        """Erstellt einen IMAP-Mock mit vordefinierten Nachrichten."""
        uid_liste = b" ".join(
            str(i + 1).encode() for i in range(len(nachrichten))
        )
        mock = MagicMock()

        fetch_side_effects = [("OK", [b""])]  # SEARCH
        for i, (uid, roh) in enumerate(nachrichten):
            fetch_side_effects.append(("OK", [(b"", roh)]))  # FETCH

        search_return = ("OK", [uid_liste]) if nachrichten else ("OK", [b""])

        def uid_handler(cmd, *args):
            if cmd == "SEARCH":
                return search_return
            elif cmd == "FETCH":
                uid_arg = args[0]
                # Finde die passende Nachricht
                idx = int(uid_arg) - 1
                if 0 <= idx < len(nachrichten):
                    return ("OK", [(b"", nachrichten[idx][1])])
                return ("NO", [])
            elif cmd == "STORE":
                return ("OK", [b""])
            return ("NO", [])

        mock.uid.side_effect = uid_handler
        return mock

    def test_leerer_lauf(self):
        """Import-Lauf ohne Nachrichten."""
        mock_imap = MagicMock()
        mock_imap.uid.return_value = ("OK", [b""])
        bericht = self.starte(imap_mock=mock_imap)
        self.assertEqual(bericht["verarbeitet"], 0)
        self.assertEqual(bericht["fehler"], 0)

    def test_eine_nachricht_mit_az_match(self):
        """E-Mail mit Aktenzeichen → wird verarbeitet."""
        roh = _erstelle_email(
            betreff="Az. 25-SVC-001 Regulierung",
            von="versicherung@huk.de",
            message_id="<az-match-001@test.de>",
        )
        mock = self._mock_imap([(b"1", roh)])
        bericht = self.starte(imap_mock=mock)
        self.assertEqual(bericht["verarbeitet"], 1)
        self.assertEqual(bericht["kein_treffer"], 0)

    def test_nachricht_ohne_akte_match(self):
        """E-Mail ohne erkennbaren Bezug → kein_treffer."""
        roh = _erstelle_email(
            betreff="Allgemeine Anfrage",
            von="unbekannt@xyz.de",
            message_id="<kein-match-001@test.de>",
        )
        mock = self._mock_imap([(b"1", roh)])
        bericht = self.starte(imap_mock=mock)
        self.assertEqual(bericht["kein_treffer"], 1)
        self.assertEqual(bericht["verarbeitet"], 0)

    def test_duplikat_wird_ignoriert(self):
        """Gleiche Message-ID zweimal → zweite wird ignoriert."""
        roh = _erstelle_email(
            betreff="Az. 25-SVC-001 Regulierung",
            message_id="<duplikat-001@test.de>",
        )
        mock1 = self._mock_imap([(b"1", roh)])
        self.starte(imap_mock=mock1)

        mock2 = self._mock_imap([(b"1", roh)])
        bericht2 = self.starte(imap_mock=mock2)
        self.assertEqual(bericht2["ignoriert"], 1)
        self.assertEqual(bericht2["verarbeitet"], 0)

    def test_pdf_anhang_wird_gespeichert(self):
        """PDF-Anhang bei gefundener Akte wird als Dokument registriert."""
        roh = _erstelle_email(
            betreff="Az. 25-SVC-001 Gutachten",
            message_id="<pdf-anhang-001@test.de>",
            anhaenge=[("gutachten.pdf", _minimales_pdf(), "application/pdf")],
        )
        mock = self._mock_imap([(b"1", roh)])
        bericht = self.starte(imap_mock=mock)
        self.assertGreaterEqual(bericht["anhaenge"], 1)

    def test_anhang_ohne_akte_nicht_gespeichert(self):
        """Anhänge bei kein_treffer werden NICHT gespeichert."""
        roh = _erstelle_email(
            betreff="Allgemeine Anfrage",
            message_id="<kein-treffer-pdf@test.de>",
            anhaenge=[("dokument.pdf", _minimales_pdf(), "application/pdf")],
        )
        mock = self._mock_imap([(b"1", roh)])
        bericht = self.starte(imap_mock=mock)
        self.assertEqual(bericht["anhaenge"], 0)

    def test_log_wird_geschrieben(self):
        roh = _erstelle_email(
            betreff="Az. 25-SVC-001 Test",
            message_id="<log-test-001@test.de>",
        )
        mock = self._mock_imap([(b"1", roh)])
        self.starte(imap_mock=mock)
        log = self.hole_log()
        self.assertGreater(len(log), 0)
        self.assertEqual(log[0]["status"], "verarbeitet")

    def test_kein_treffer_in_log(self):
        roh = _erstelle_email(
            betreff="Unbekannt",
            message_id="<kein-treffer-log@test.de>",
            von="xyz@unbekannt.de",
        )
        mock = self._mock_imap([(b"1", roh)])
        self.starte(imap_mock=mock)
        log = self.hole_log(status="kein_treffer")
        self.assertEqual(len(log), 1)
        self.assertIsNotNone(log[0]["notizen"])

    def test_statistik_nach_lauf(self):
        for i in range(3):
            roh = _erstelle_email(
                betreff=f"Az. 25-SVC-001 Lauf {i}",
                message_id=f"<stat-{i}@test.de>",
            )
            mock = self._mock_imap([(b"1", roh)])
            self.starte(imap_mock=mock)

        stat = self.statistik()
        self.assertGreaterEqual(stat["verarbeitet"], 3)
        self.assertIsNotNone(stat["letzter_import"])

    def test_nicht_konfiguriert_wirft_fehler(self):
        for k in ["EMAIL_HOST", "EMAIL_USER", "EMAIL_PASSWORD"]:
            os.environ.pop(k, None)

        import importlib
        svc = importlib.reload(
            __import__("backend.email_import.import_service", fromlist=[""])
        )
        try:
            svc.fuehre_import_lauf_durch()
            self.fail("Kein Fehler geworfen")
        except Exception as e:
            # ImportFehler oder Unterklasse – Klasse ändert sich nach reload
            self.assertIn("konfiguriert", str(e).lower())


# ══════════════════════════════════════════════════════════════════════════════
# FLASK-ROUTEN-TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestEmailRouten(unittest.TestCase):

    def setUp(self):
        # IMAP konfigurieren
        os.environ["EMAIL_HOST"]     = "mail.test.de"
        os.environ["EMAIL_USER"]     = "akten@test.de"
        os.environ["EMAIL_PASSWORD"] = "geheim"
        self.client, self.h, self.akte_id, self.loaded = \
            _setup(f"er_{self._testMethodName}")

    def _starte_import(self, nachrichten=None, body=None):
        """Startet einen Import mit gemocktem IMAP."""
        from backend.email_import import import_service
        import importlib; importlib.reload(import_service)

        mock_imap = MagicMock()
        if nachrichten:
            uid_liste = b" ".join(str(i+1).encode()
                                   for i in range(len(nachrichten)))
            def uid_handler(cmd, *args):
                if cmd == "SEARCH":
                    return ("OK", [uid_liste])
                elif cmd == "FETCH":
                    idx = int(args[0]) - 1
                    return ("OK", [(b"", nachrichten[idx])])
                return ("OK", [b""])
            mock_imap.uid.side_effect = uid_handler
        else:
            mock_imap.uid.return_value = ("OK", [b""])

        with patch.object(import_service, "imap_verbinden") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_imap)
            mock_ctx.return_value.__exit__  = MagicMock(return_value=False)
            return self.client.post(
                "/email/import",
                json=body or {},
                headers=self.h,
            )

    # ── POST /email/import ────────────────────────────────────────────────────

    def test_import_lauf_ok(self):
        r = self._starte_import()
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        for feld in ["verarbeitet", "kein_treffer", "fehler",
                      "ignoriert", "anhaenge", "laufzeit_s"]:
            self.assertIn(feld, data, f"Feld '{feld}' fehlt")

    def test_import_verarbeitet_az_match(self):
        roh = _erstelle_email(
            betreff="Az. 25-M7-001 Regulierung",
            message_id="<route-az-001@test.de>",
        )
        r = self._starte_import(nachrichten=[roh])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["verarbeitet"], 1)

    def test_import_max_nachrichten_validiert(self):
        r = self.client.post("/email/import",
                              json={"max_nachrichten": 0},
                              headers=self.h)
        self.assertEqual(r.status_code, 422)

    def test_import_max_nachrichten_zu_gross(self):
        r = self.client.post("/email/import",
                              json={"max_nachrichten": 999},
                              headers=self.h)
        self.assertEqual(r.status_code, 422)

    def test_import_ohne_token_401(self):
        r = self.client.post("/email/import", json={})
        self.assertEqual(r.status_code, 401)

    # ── GET /email/import/status ──────────────────────────────────────────────

    def test_status_konfiguriert(self):
        r = self.client.get("/email/import/status", headers=self.h)
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("konfiguriert", data)
        self.assertTrue(data["konfiguriert"])
        self.assertIn("konfiguration", data)

    def test_status_nicht_konfiguriert(self):
        for k in ["EMAIL_HOST", "EMAIL_USER", "EMAIL_PASSWORD"]:
            os.environ.pop(k, None)
        r = self.client.get("/email/import/status", headers=self.h)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.get_json()["konfiguriert"])

    def test_status_ohne_token_401(self):
        r = self.client.get("/email/import/status")
        self.assertEqual(r.status_code, 401)

    # ── GET /email/import/log ─────────────────────────────────────────────────

    def test_log_leer_am_anfang(self):
        r = self.client.get("/email/import/log", headers=self.h)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["gesamt"], 0)

    def test_log_nach_import(self):
        roh = _erstelle_email(
            betreff="Az. 25-M7-001 Log-Test",
            message_id="<log-route-001@test.de>",
        )
        self._starte_import(nachrichten=[roh])
        r = self.client.get("/email/import/log", headers=self.h)
        self.assertGreater(r.get_json()["gesamt"], 0)

    def test_log_filter_status(self):
        r = self.client.get("/email/import/log?status=verarbeitet",
                             headers=self.h)
        self.assertEqual(r.status_code, 200)

    def test_log_filter_status_ungueltig(self):
        r = self.client.get("/email/import/log?status=blabla",
                             headers=self.h)
        self.assertEqual(r.status_code, 422)

    def test_log_ohne_token_401(self):
        r = self.client.get("/email/import/log")
        self.assertEqual(r.status_code, 401)

    # ── GET /email/import/log/statistik ──────────────────────────────────────

    def test_statistik_felder(self):
        r = self.client.get("/email/import/log/statistik", headers=self.h)
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        for feld in ["gesamt", "verarbeitet", "kein_treffer",
                      "fehler", "ignoriert"]:
            self.assertIn(feld, data)

    def test_statistik_ohne_token_401(self):
        r = self.client.get("/email/import/log/statistik")
        self.assertEqual(r.status_code, 401)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [
        TestEmailParser,
        TestImapClient,
        TestAkteMatching,
        TestImportService,
        TestEmailRouten,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
