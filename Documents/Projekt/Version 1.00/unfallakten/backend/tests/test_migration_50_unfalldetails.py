"""
Migration 50: unfalldetails-Tabelle nachtraeglich anlegen.

Root Cause (siehe handover/2026-07-08-datenmodell-bugs-unfalldetails-cleanup.md):
Der aktive backend/db/schema_manager.py hat nie ein CREATE TABLE
unfalldetails gehabt -- nur der tote Root-Legacy-Manager
backend/schema_manager.py, der nie gegen die Live-DB lief.
Migration 28 setzt seit v56 mit einer PRAGMA-table_info-Guard voraus,
dass die Tabelle existiert, findet sie nicht und stempelt sich als
"SKIPPED" in schema_version. Ergebnis: `GET/PUT /akten/<az>/unfalldetails`
und `POST /akten/<az>/klage/generieren` crashen mit 500
(sqlite3.OperationalError: no such table: unfalldetails).

Migration 50 legt die Tabelle vollstaendig an -- inklusive der drei
Aktivlegitimations-Spalten aus Migration 28, damit Fresh-Setups nicht
mehr auf 28 angewiesen sind.

Diese Tests laufen gegen eine frische in-Datei-DB und pruefen:
  1. Nach init_db() existiert `unfalldetails`.
  2. Alle Kern-Spalten sind vorhanden (Schilderung, Zeugen, Ermittlungsakte,
     Fahrer, Vorsteuerabzug, Haftungsquote, Aktivlegitimation).
  3. FK zeigt korrekt auf unfallakte(az), NICHT auf unfallakte(aktenzeichen).
  4. Idempotent: Zweiter init_db()-Aufruf wirft nicht.
  5. Insert + Select laufen ohne Fehler.
"""
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


ERWARTETE_SPALTEN = {
    "id",
    "akte_id",
    "schilderung",
    "zeuge_1", "zeuge_1_anschrift",
    "zeuge_2", "zeuge_2_anschrift",
    "zeuge_3", "zeuge_3_anschrift",
    "ermittlungsakte_az", "ermittlungsakte_behoerde", "ermittlungsakte_ort",
    "fahrer_mandant", "fahrer_gegner",
    "vorsteuerabzug",
    "haftungsquote",
    "haftungsbegruendung",
    "aktivlegitimation_typ",
    "aktivlegitimation_freigabe",
    "aktivlegitimation_datum",
    "erstellt_am",
    "geaendert_am",
}


class TestMigration50Unfalldetails(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="m50_", suffix=".sqlite")
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

    def _spalten(self) -> dict:
        with sqlite3.connect(self._db_pfad) as conn:
            return {row[1]: row[2] for row in conn.execute(
                "PRAGMA table_info(unfalldetails)").fetchall()}

    def test_tabelle_unfalldetails_existiert(self):
        with sqlite3.connect(self._db_pfad) as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='unfalldetails'"
            ).fetchone()
        self.assertIsNotNone(row, "unfalldetails-Tabelle wurde nicht angelegt")

    def test_alle_erwarteten_spalten_vorhanden(self):
        spalten = self._spalten()
        fehlend = ERWARTETE_SPALTEN - set(spalten.keys())
        self.assertEqual(
            fehlend, set(),
            f"Spalten fehlen in unfalldetails: {sorted(fehlend)}",
        )

    def test_fk_zeigt_auf_unfallakte_az(self):
        with sqlite3.connect(self._db_pfad) as conn:
            fks = conn.execute(
                "PRAGMA foreign_key_list(unfalldetails)"
            ).fetchall()
        # FK-Zeile Format: (id, seq, table, from, to, on_update, on_delete, match)
        matching = [fk for fk in fks
                    if fk[2] == "unfallakte" and fk[3] == "akte_id"]
        self.assertTrue(
            matching, "Kein FK von unfalldetails.akte_id auf unfallakte",
        )
        # to-Spalte muss "az" sein, nicht "aktenzeichen" (siehe
        # bugs_and_fixes.md: "FKs auf unfallakte: Immer TEXT REFERENCES
        # unfallakte(az), niemals INTEGER")
        self.assertEqual(
            matching[0][4], "az",
            f"FK zeigt auf {matching[0][4]!r} statt 'az'",
        )

    def test_migration_50_in_schema_version(self):
        with sqlite3.connect(self._db_pfad) as conn:
            row = conn.execute(
                "SELECT version, beschreibung FROM schema_version "
                "WHERE version=50"
            ).fetchone()
        self.assertIsNotNone(row, "Migration 50 nicht in schema_version")

    def test_insert_und_select_funktionieren(self):
        with sqlite3.connect(self._db_pfad) as conn:
            # unfallakte-Zeile muss existieren (FK)
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('AZ-1', '2026-01-01', 'offen')"
            )
            conn.execute(
                "INSERT INTO unfalldetails (akte_id, schilderung, "
                "haftungsquote, aktivlegitimation_typ) "
                "VALUES ('AZ-1', 'Testunfall', 75.0, 'finanziert')"
            )
            row = conn.execute(
                "SELECT schilderung, haftungsquote, aktivlegitimation_typ, "
                "aktivlegitimation_freigabe "
                "FROM unfalldetails WHERE akte_id='AZ-1'"
            ).fetchone()
        self.assertEqual(row[0], "Testunfall")
        self.assertEqual(row[1], 75.0)
        self.assertEqual(row[2], "finanziert")
        # aktivlegitimation_freigabe hat DEFAULT 'freigabe'
        self.assertEqual(row[3], "freigabe")

    def test_zweiter_init_db_aufruf_wirft_nicht(self):
        """Idempotenz: doppelter init_db()-Aufruf ist ein No-Op."""
        from backend.db.schema_manager import init_db
        init_db()  # zweite Runde
        # Wenn wir hier ankommen, ist der Test bestanden.
        spalten = self._spalten()
        self.assertIn("schilderung", spalten)


if __name__ == "__main__":
    unittest.main()
