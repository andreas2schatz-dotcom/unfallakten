"""
Tests fuer Migration 47 (S1.4 - Absender-Registry-Grundgeruest) und das
Konsolidierungsskript konsolidiere_absender_registry.

Aus PIPELINE-REFACTORING-PLAN.md S1.4:
    * Spalte ``vertrauensstufe`` (INTEGER 0-3, Default 1)
    * Konsolidierungsskript uebernimmt marker_typ=domain aus registry.json
      in ``email_absender_vorlagen`` (klasse-Kandidat + ramicro_adressnr
      als neue Spalten).
    * Adapter (S1.3) schreiben die Vertrauensstufe in
      ``zustellungen.signale_json``.
    * registry.json bleibt unveraendert im Alt-Pfad.

Testkriterium aus dem Plan:
    Alle Domain-Marker aus registry.json in der Tabelle; Lookup liefert
    fuer bekannte Domain Kategorie + Vertrauensstufe + Klassen-Kandidat.
"""
import os
import sys
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

_tmp_dir = tempfile.mkdtemp()


def _fresh_db(test_id: str):
    db_path = os.path.join(_tmp_dir, f"m47_{test_id}.db")
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


# ── Migration 47: Spalten ────────────────────────────────────────────────────


class TestMigration47Struktur(unittest.TestCase):
    """Neue Spalten an email_absender_vorlagen (additiv, nicht destruktiv)."""

    def test_neue_spalten_vorhanden(self):
        db = _fresh_db("cols")
        with db.get_connection() as conn:
            cols = {r[1] for r in conn.execute(
                "PRAGMA table_info(email_absender_vorlagen)"
            ).fetchall()}
        self.assertIn("vertrauensstufe", cols)
        self.assertIn("klasse_kandidat", cols)
        self.assertIn("ramicro_adressnr", cols)

    def test_bestehende_spalten_erhalten(self):
        """Migration ist additiv - Alt-Spalten (name, domain, kategorie, ...) bleiben."""
        db = _fresh_db("altspalten")
        with db.get_connection() as conn:
            cols = {r[1] for r in conn.execute(
                "PRAGMA table_info(email_absender_vorlagen)"
            ).fetchall()}
        for pflicht in ("id", "name", "domain", "kategorie", "aktiv"):
            self.assertIn(pflicht, cols)

    def test_vertrauensstufe_default_1(self):
        """Neue Seed-Zeile ohne expliziten Wert erhaelt vertrauensstufe=1 (Default)."""
        db = _fresh_db("default")
        with db.get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO email_absender_vorlagen (name, domain) "
                "VALUES ('Testfirma', 'testfirma.example')"
            )
            row = conn.execute(
                "SELECT vertrauensstufe FROM email_absender_vorlagen "
                "WHERE domain = 'testfirma.example'"
            ).fetchone()
        self.assertEqual(row["vertrauensstufe"], 1)

    def test_schema_version_47_gestempelt(self):
        db = _fresh_db("version")
        with db.get_connection() as conn:
            row = conn.execute(
                "SELECT version FROM schema_version WHERE version = 47"
            ).fetchone()
        self.assertIsNotNone(row)

    def test_migration_idempotent(self):
        """Zweiter run_migrations()-Aufruf darf nicht schmerzhaft neu ALTERen."""
        db = _fresh_db("idempotent")
        import backend.db.schema_manager as sm
        sm.run_migrations()  # zweites Mal
        # Kein Fehler bedeutet Idempotenz.
        with db.get_connection() as conn:
            cnt = conn.execute(
                "SELECT COUNT(*) FROM schema_version WHERE version = 47"
            ).fetchone()[0]
        self.assertEqual(cnt, 1, "schema_version 47 darf nur EINMAL stehen")


# ── Konsolidierungsskript ────────────────────────────────────────────────────


class TestKonsolidierungRegistry(unittest.TestCase):
    """
    Skript uebernimmt marker-Eintraege mit ``domain``-Feld aus registry.json
    in ``email_absender_vorlagen``. Klasse-Kandidat + ramicro_adressnr werden
    mit uebertragen. Bestehende Zeilen werden NICHT ueberschrieben.
    """

    def test_bekannte_domain_wird_uebernommen(self):
        db = _fresh_db("uebernahme")
        from backend.scripts.konsolidiere_absender_registry import konsolidiere
        konsolidiere()

        with db.get_connection() as conn:
            row = conn.execute(
                "SELECT domain, kategorie, klasse_kandidat, vertrauensstufe "
                "FROM email_absender_vorlagen WHERE domain = 'allianz.de'"
            ).fetchone()
        self.assertIsNotNone(row, "allianz.de fehlt in Registry")
        self.assertEqual(row["klasse_kandidat"], "versicherung")
        self.assertEqual(row["kategorie"], "versicherung")
        # Konsolidierte Domain hat hoehere Vertrauensstufe als Default (1).
        self.assertGreaterEqual(row["vertrauensstufe"], 2)

    def test_alle_registry_domains_landen_in_tabelle(self):
        """
        Alle eindeutigen Domains aus dem marker-Baum sind nach Konsolidierung
        in email_absender_vorlagen abrufbar.
        """
        db = _fresh_db("alle")
        from backend.scripts.konsolidiere_absender_registry import konsolidiere
        konsolidiere()

        import json
        from pathlib import Path
        registry_pfad = (Path(__file__).parent.parent
                         / "config" / "registry.json")
        with open(registry_pfad, encoding="utf-8") as f:
            reg = json.load(f)
        registry_domains = {
            (v.get("domain") or "").lower().strip()
            for v in reg.get("marker", {}).values()
            if v.get("domain")
        }
        registry_domains.discard("")

        with db.get_connection() as conn:
            tabellen_domains = {
                r[0].lower() for r in conn.execute(
                    "SELECT domain FROM email_absender_vorlagen"
                ).fetchall()
                if r[0]
            }

        fehlend = registry_domains - tabellen_domains
        self.assertEqual(
            fehlend, set(),
            f"{len(fehlend)} Registry-Domains fehlen in email_absender_vorlagen"
        )

    def test_bestehende_zeile_bleibt_unangetastet_bei_re_run(self):
        """
        Idempotenz: manuell veraenderte Zeile darf nach zweitem
        Konsolidierungslauf nicht ueberschrieben werden.
        """
        db = _fresh_db("nichtueberschreiben")
        from backend.scripts.konsolidiere_absender_registry import konsolidiere
        konsolidiere()

        with db.get_connection() as conn:
            conn.execute(
                "UPDATE email_absender_vorlagen SET notizen = 'MANUELL' "
                "WHERE domain = 'allianz.de'"
            )
        konsolidiere()
        with db.get_connection() as conn:
            row = conn.execute(
                "SELECT notizen FROM email_absender_vorlagen "
                "WHERE domain = 'allianz.de'"
            ).fetchone()
        self.assertEqual(row["notizen"], "MANUELL",
                         "Konsolidierung darf bestehende Notizen nicht ueberschreiben")


# ── Adapter-Anbindung: Signale-Anreicherung ──────────────────────────────────


class TestAdapterImapAbsenderSignale(unittest.TestCase):
    """
    S1.4-Erweiterung: der IMAP-Adapter reichert ``signale_json`` der
    Body-Zustellung mit Kategorie + Vertrauensstufe + Klassen-Kandidat
    an, wenn die Absender-Domain in der Registry bekannt ist.
    Registry.json bleibt unveraendert im Alt-Pfad (Doppelschreiben).
    """

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="s14_adapter_")
        os.environ["INTAKE_ARCHIV_ROOT"] = self._tmp
        self.db = _fresh_db(f"adapter_{self._testMethodName}")
        # Erst nach fresh_db konsolidieren, damit die Testdaten gefuellt sind.
        from backend.scripts.konsolidiere_absender_registry import konsolidiere
        konsolidiere()

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)
        os.environ.pop("INTAKE_ARCHIV_ROOT", None)

    def _mail_mit_absender(self, von: str) -> bytes:
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        msg = MIMEMultipart()
        msg["Subject"] = "Test"
        msg["From"] = von
        msg["To"] = "unfall@anwalt-offenbach.de"
        msg["Date"] = "Mon, 15 Mar 2025 10:30:00 +0100"
        msg["Message-ID"] = "<s14-1@test.de>"
        msg.attach(MIMEText("Body.", "plain", "utf-8"))
        return msg.as_bytes()

    def test_bekannte_domain_reichert_signale_an(self):
        from backend.intake.adapter_imap import verarbeite_email
        roh = self._mail_mit_absender("mailer@allianz.de")
        verarbeite_email(roh, konto="unfall")

        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT signale_json FROM zustellungen "
                "WHERE quelle='imap' AND parent_id IS NULL"
            ).fetchone()
        import json
        signale = json.loads(row["signale_json"] or "{}")
        self.assertEqual(signale.get("absender_kategorie"), "versicherung")
        self.assertEqual(signale.get("klasse_kandidat"), "versicherung")
        self.assertIsNotNone(signale.get("vertrauensstufe"))
        self.assertGreaterEqual(int(signale["vertrauensstufe"]), 1)

    def test_unbekannte_domain_reichert_keine_absender_signale_an(self):
        from backend.intake.adapter_imap import verarbeite_email
        roh = self._mail_mit_absender("fremd@voellig-unbekannt-xyz.example")
        verarbeite_email(roh, konto="unfall")

        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT signale_json FROM zustellungen "
                "WHERE quelle='imap' AND parent_id IS NULL"
            ).fetchone()
        import json
        signale = json.loads(row["signale_json"] or "{}")
        self.assertNotIn("absender_kategorie", signale)
        self.assertNotIn("klasse_kandidat", signale)


if __name__ == "__main__":
    unittest.main()
