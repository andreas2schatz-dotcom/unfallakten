"""
IMP-05 Tests: pwa_nachricht_senden + logge_aktivitaet
=====================================================
Testet das Verhalten von logge_aktivitaet() im Kontext des
pwa_nachricht Endpoints. Nutzt in-memory SQLite wie test_migration_38.py.
"""

import os
import sqlite3
import tempfile
import unittest


def _make_conn():
    """Frische in-memory DB mit minimalem Schema für aktivitaeten."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE aktivitaeten (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            akte_id     TEXT,
            benutzer_id INTEGER,
            aktion      TEXT NOT NULL,
            beschreibung TEXT DEFAULT '',
            tabelle     TEXT,
            datensatz_id INTEGER,
            aenderung_json TEXT,
            zeitstempel TEXT DEFAULT (datetime('now','localtime'))
        );
    """)
    return conn


class TestLoggeAktivitaet(unittest.TestCase):
    """Verhaltenstests für logge_aktivitaet – unabhängig vom HTTP-Layer."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.environ["DB_PATH"] = self.db_path
        # Tabelle anlegen
        conn = sqlite3.connect(self.db_path)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS aktivitaeten (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                akte_id     TEXT,
                benutzer_id INTEGER,
                aktion      TEXT NOT NULL,
                beschreibung TEXT DEFAULT '',
                tabelle     TEXT,
                datensatz_id INTEGER,
                aenderung_json TEXT,
                zeitstempel TEXT DEFAULT (datetime('now','localtime'))
            );
        """)
        conn.close()

        # Backend-Module frisch laden
        import importlib
        for mod in ["backend.db.database", "backend.models.dokument"]:
            m = __import__(mod, fromlist=[""])
            importlib.reload(m)

        from backend.models.dokument import logge_aktivitaet
        self.logge = logge_aktivitaet

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_eintrag_wird_geschrieben(self):
        """logge_aktivitaet schreibt einen Eintrag in aktivitaeten."""
        result = self.logge("pwa_nachricht", "[PWA:test] Nachricht.", akte_id="99/25", tabelle="pwa")
        self.assertIsNotNone(result.id, "Rückgabe-Objekt hat keine id")
        self.assertTrue(result.id > 0, f"id ist nicht positiv: {result.id}")

    def test_aktion_und_beschreibung_korrekt(self):
        """Gespeicherter Eintrag enthält aktion und beschreibung."""
        text = "[PWA:dok_anfordern] Bitte Dokument einreichen."
        self.logge("pwa_nachricht", text, akte_id="99/25", tabelle="pwa")

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM aktivitaeten WHERE aktion = 'pwa_nachricht'"
        ).fetchone()
        conn.close()

        self.assertIsNotNone(row, "Kein Eintrag mit aktion='pwa_nachricht' gefunden")
        self.assertEqual(row["aktion"], "pwa_nachricht")
        self.assertEqual(row["beschreibung"], text)
        self.assertEqual(row["akte_id"], "99/25")
        self.assertEqual(row["tabelle"], "pwa")

    def test_tabelle_pwa_wird_gespeichert(self):
        """tabelle='pwa' wird korrekt persistiert."""
        self.logge("pwa_nachricht", "Test", akte_id="1/25", tabelle="pwa")

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT tabelle FROM aktivitaeten LIMIT 1").fetchone()
        conn.close()

        self.assertEqual(row["tabelle"], "pwa")

    def test_benutzer_id_wird_gespeichert(self):
        """benutzer_id wird korrekt mitgespeichert."""
        self.logge("pwa_nachricht", "Test", akte_id="1/25", benutzer_id=42, tabelle="pwa")

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT benutzer_id FROM aktivitaeten LIMIT 1").fetchone()
        conn.close()

        self.assertEqual(row["benutzer_id"], 42)

    def test_mehrere_eintraege_moeglich(self):
        """Mehrere pwa_nachricht Einträge für dieselbe Akte sind möglich."""
        self.logge("pwa_nachricht", "Erste Nachricht.", akte_id="99/25", tabelle="pwa")
        self.logge("pwa_nachricht", "Zweite Nachricht.", akte_id="99/25", tabelle="pwa")

        conn = sqlite3.connect(self.db_path)
        count = conn.execute(
            "SELECT COUNT(*) FROM aktivitaeten WHERE aktion = 'pwa_nachricht'"
        ).fetchone()[0]
        conn.close()

        self.assertEqual(count, 2)


if __name__ == "__main__":
    unittest.main()
