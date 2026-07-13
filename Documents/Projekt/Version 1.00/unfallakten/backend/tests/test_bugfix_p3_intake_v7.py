"""
Tests fuer die P3-Bugfixes aus docs/BUGFIX_INTAKE_V7.md (Code-Review 2026-07-12).

Abgedeckt (Matching-/Signal-Qualitaet & UI-Korrektheit):
  * BUG-14 -- Absender-Registry-Signale werden an Anhang-Zustellungen vererbt
              (nicht mehr nur an die Body-Zustellung).
  * BUG-15 -- Absender-Mail-Match (Score 0.6) ist kein toter Code mehr: der
              IMAP-Adapter schreibt die geparste Absenderadresse als
              Signal-Key ``absender_email``, den finde_kandidaten auswertet.
  * BUG-16 -- E-Akte-Adapter schreibt das bekannte Aktenzeichen als Key ``az``
              (statt ``akte_az``) -> finde_kandidaten liefert den Vorschlag.
  * BUG-17 -- KFZ-Muster erkennt Umlaut-Kennzeichen (TOEL, FUE, BOE, GOE).
  * BUG-18 -- Kurze E-Mail-Bodies (<10 Zeichen) werden im Meta-Endpoint nicht
              mehr unterdrueckt.
  * BUG-19 -- Queue-Sortierung: bei gleichem erstellt_am entscheidet die
              Konfidenz (absteigend) vor der id.

Muster wie test_bugfix_p2_intake_v7.py: eigene DB je Test, Import der
Produktivmodule nach DB-Reload.
"""
import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from email.message import EmailMessage

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ─── Basis-Klassen ───────────────────────────────────────────────────────────


class _DBBasis(unittest.TestCase):
    """Frische SQLite-DB je Test (ohne Flask-App)."""

    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="p3bug_", suffix=".sqlite")
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


class _RouteBasis(unittest.TestCase):
    """Flask-App + Test-Client mit Auth (wie test_bugfix_p2_intake_v7)."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="p3bug_route_")
        self._db_pfad = os.path.join(self._tmp, "unfallakten.db")
        self._uploads = os.path.join(self._tmp, "uploads")
        self._artefakte = os.path.join(self._tmp, "artefakte")
        os.makedirs(self._uploads, exist_ok=True)
        os.makedirs(self._artefakte, exist_ok=True)
        os.environ["DB_PATH"] = self._db_pfad
        os.environ["UPLOAD_DIR"] = self._uploads
        os.environ["INTAKE_ARTEFAKTE_ROOT"] = self._artefakte

        import backend.db.database as db_mod
        import backend.models.benutzer as ben_mod
        import backend.models.akte as akte_mod
        import backend.models.dokument as dok_mod
        import backend.auth.jwt_handler as jwt_mod
        import backend.auth.middleware as mw_mod
        import backend.auth.service as svc_mod
        import backend.routers.auth_routes as routes_mod
        import backend.app as app_mod
        for m in (db_mod, ben_mod, akte_mod, dok_mod,
                  jwt_mod, mw_mod, svc_mod, routes_mod, app_mod):
            importlib.reload(m)
        self._app = app_mod.erstelle_app({"TESTING": True})
        self.client = self._app.test_client()

    def tearDown(self):
        for var in ("DB_PATH", "UPLOAD_DIR", "INTAKE_ARTEFAKTE_ROOT"):
            os.environ.pop(var, None)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _login(self):
        r = self.client.post("/auth/login", json={
            "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
            "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!"),
        })
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


def _mail_mit_anhang(from_header: str, body: str) -> bytes:
    msg = EmailMessage()
    msg["From"] = from_header
    msg["Subject"] = "Abrechnung Ihres Schadens"
    msg["Message-ID"] = "<p3bug@test>"
    msg.set_content(body)
    msg.add_attachment(b"%PDF-1.4 fake", maintype="application",
                       subtype="pdf", filename="abrechnung.pdf")
    return msg.as_bytes()


# ─── BUG-14: Absender-Signale erreichen Anhaenge ─────────────────────────────


class TestBug14AbsenderSignaleAnAnhaenge(_DBBasis):
    def test_registry_signale_an_anhang_zustellung(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO email_absender_vorlagen "
                "(name, domain, kategorie, versicherer_name, klasse_kandidat, "
                " vertrauensstufe, aktiv) "
                "VALUES ('VX', 'versicherung-x.de', 'versicherung', "
                "        'Versicherung X', 'abrechnungsschreiben', 2, 1)"
            )

        from backend.intake import adapter_imap
        importlib.reload(adapter_imap)
        raw = _mail_mit_anhang(
            "Schaden <schaden@versicherung-x.de>",
            "Sehr geehrte Damen und Herren, anbei die Abrechnung.")
        ergebnis = adapter_imap.verarbeite_email(raw)

        anhang = ergebnis["anhaenge"][0]
        with get_connection() as conn:
            row = conn.execute(
                "SELECT signale_json FROM zustellungen WHERE id=?",
                (anhang["zustellung_id"],),
            ).fetchone()
        signale = json.loads(row["signale_json"])
        self.assertEqual(signale.get("klasse_kandidat"), "abrechnungsschreiben",
                         "Anhang-Zustellung muss das Registry-Signal erben")
        self.assertEqual(signale.get("versicherer_name"), "Versicherung X")
        self.assertEqual(signale.get("dateiname"), "abrechnung.pdf",
                         "dateiname-Signal darf nicht verloren gehen")


# ─── BUG-15: Absender-Mail-Match ist kein toter Code mehr ────────────────────


class TestBug15AbsenderMailSignal(_DBBasis):
    def test_adapter_schreibt_absender_email_signal(self):
        from backend.intake import adapter_imap
        importlib.reload(adapter_imap)
        raw = _mail_mit_anhang(
            "Max Mustermann <max@example.de>", "Kurztext.")
        ergebnis = adapter_imap.verarbeite_email(raw)

        from backend.db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT signale_json FROM zustellungen WHERE id=?",
                (ergebnis["body"]["zustellung_id"],),
            ).fetchone()
        signale = json.loads(row["signale_json"])
        self.assertEqual(signale.get("absender_email"), "max@example.de",
                         "Body-Zustellung muss die geparste Absenderadresse "
                         "als absender_email fuehren (nicht das From-Roh-Feld)")

    def test_finde_kandidaten_matcht_beteiligten_mail(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute("INSERT INTO unfallakte (az, status) "
                         "VALUES ('88/26', 'offen')")
            conn.execute(
                "INSERT INTO beteiligte (akte_id, name, rolle, email) "
                "VALUES ('88/26', 'Mustermann', 'mandant', 'kunde@example.de')"
            )
        from backend.intake import akten_matching
        importlib.reload(akten_matching)
        # Signal, wie es der IMAP-Adapter nach dem Fix schreibt.
        signale = [{"absender_email": "kunde@example.de"}]
        kandidaten = akten_matching.finde_kandidaten("", signale)
        quellen = {(k.akte_az, k.quelle) for k in kandidaten}
        self.assertIn(("88/26", "beteiligten_mail"), quellen,
                      "Absender-Mail-Signal muss den 0.6-Treffer ausloesen")


# ─── BUG-16: E-Akte-Key-Mismatch akte_az vs az ──────────────────────────────


class TestBug16EakteKeyMismatch(_DBBasis):
    def test_eakte_adapter_schreibt_az_signal(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute("INSERT INTO unfallakte (az, status) "
                         "VALUES ('285/26', 'offen')")

        fd, quellpfad = tempfile.mkstemp(prefix="eakte_", suffix=".pdf")
        os.write(fd, b"%PDF-1.4 fake")
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(quellpfad) and os.unlink(quellpfad))

        from backend.intake import adapter_eakte, akten_matching
        importlib.reload(adapter_eakte)
        importlib.reload(akten_matching)
        ergebnis = adapter_eakte.verarbeite_eakte_dokument(
            quellpfad, akte_az="285/26", eakte_nr=3, dateiname="a.pdf")

        with get_connection() as conn:
            row = conn.execute(
                "SELECT signale_json FROM zustellungen WHERE id=?",
                (ergebnis["zustellung_id"],),
            ).fetchone()
        signale = json.loads(row["signale_json"])
        kandidaten = akten_matching.finde_kandidaten("", [signale])
        treffer = {(k.akte_az, k.quelle) for k in kandidaten}
        self.assertIn(("285/26", "az_exakt"), treffer,
                      "E-Akte-Signal muss den az-Vorschlag liefern")


# ─── BUG-17: Umlaut-Kennzeichen ─────────────────────────────────────────────


class TestBug17UmlautKfz(_DBBasis):
    def test_kfz_muster_matcht_umlaut(self):
        from backend.intake import akten_matching
        importlib.reload(akten_matching)
        for kfz in ("TÖL-A 123", "FÜ-XY 99", "BÖ-Z 1", "GÖ-AB 4321"):
            self.assertIsNotNone(
                akten_matching._KFZ_MUSTER.search(kfz),
                f"Umlaut-Kennzeichen {kfz!r} muss matchen")

    def test_finde_kandidaten_matcht_umlaut_kfz(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute("INSERT INTO unfallakte (az, status) "
                         "VALUES ('12/26', 'offen')")
            conn.execute(
                "INSERT INTO beteiligte (akte_id, name, rolle, kfz_kennzeichen) "
                "VALUES ('12/26', 'Huber', 'mandant', 'TÖL-A 123')"
            )
        from backend.intake import akten_matching
        importlib.reload(akten_matching)
        kandidaten = akten_matching.finde_kandidaten(
            "Unfall mit Fahrzeug TÖL-A 123 am Montag.", [])
        treffer = {(k.akte_az, k.quelle) for k in kandidaten}
        self.assertIn(("12/26", "kfz"), treffer,
                      "Umlaut-KFZ muss einen kfz-Kandidaten liefern")


# ─── BUG-18: Kurze Bodies nicht unterdruecken ───────────────────────────────


class TestBug18KurzerBody(_RouteBasis):
    def test_kurzer_body_wird_geliefert(self):
        eml_pfad = os.path.join(self._tmp, "kurz.eml")
        msg = EmailMessage()
        msg["From"] = "kunde@example.de"
        msg["Subject"] = "AW: Ihr Schreiben"
        msg["Message-ID"] = "<kurz@test>"
        msg.set_content("Ja")
        with open(eml_pfad, "wb") as f:
            f.write(msg.as_bytes())

        from backend.db.database import get_connection
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO email_import_log (message_id, eml_pfad) "
                "VALUES ('<kurz@test>', ?)", (eml_pfad,))
            log_id = cur.lastrowid

        h = self._login()
        r = self.client.get(f"/email/import/log/{log_id}/meta", headers=h)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(r.get_json()["body_text"], "Ja",
                         "Kurzer Body 'Ja' darf nicht unterdrueckt werden")


# ─── BUG-19: Queue-Sortierung ───────────────────────────────────────────────


class TestBug19QueueSortierung(_RouteBasis):
    def test_konfidenz_entscheidet_vor_id(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            # Gleiche erstellt_am-Sekunde, aufsteigende id-Reihenfolge, aber
            # die zuerst eingefuegte (kleinere id) hat die NIEDRIGERE Konfidenz.
            conn.execute(
                "INSERT INTO intake_dokumente (sha256, queue_status, klasse, "
                " konfidenz, erstellt_am) "
                "VALUES (?, 'bereit_zur_review', 'sonstiges', 0.20, "
                "        '2026-07-13 10:00:00')", ("a" * 64,))
            conn.execute(
                "INSERT INTO intake_dokumente (sha256, queue_status, klasse, "
                " konfidenz, erstellt_am) "
                "VALUES (?, 'bereit_zur_review', 'abrechnungsschreiben', 0.95, "
                "        '2026-07-13 10:00:00')", ("b" * 64,))

        h = self._login()
        r = self.client.get("/intake/queue", headers=h)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        eintraege = r.get_json()["eintraege"]
        self.assertGreaterEqual(len(eintraege), 2)
        self.assertEqual(
            eintraege[0]["konfidenz"], 0.95,
            "Bei gleichem erstellt_am muss die hoehere Konfidenz zuerst kommen")


if __name__ == "__main__":
    unittest.main()
