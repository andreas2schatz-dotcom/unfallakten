"""
Tests fuer Migration 51 (P1.2): Ereignis-Datenmodell.

Legt drei Tabellen an:
  * ``ereignisse``            Ebene 1 Kopf (POSITIONSMODELL-PLAN 4.1)
  * ``ereignis_positionen``   Ebene 1 n:m (POSITIONSMODELL-PLAN 4.2, K-M1)
  * ``position_ereignis_cache`` Ebene 2 (POSITIONSMODELL-PLAN 4.4, K-M1)

Additiv, idempotent, kein Datenverlust an bestehenden Tabellen.
"""
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestMigration51(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="mig51_", suffix=".sqlite")
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

    def test_ereignisse_tabelle_existiert(self):
        with sqlite3.connect(self._db_pfad) as conn:
            conn.row_factory = sqlite3.Row
            spalten = {r["name"]: r for r in conn.execute(
                "PRAGMA table_info(ereignisse)"
            ).fetchall()}
        pflicht = {
            "id", "akte_az", "ereignistyp", "richtung", "quelle",
            "datum", "dokument_id", "herkunft", "betragswirkung_gesamt",
            "ersetzt_durch", "versand_bestaetigt_am", "notiz",
            "erfasst_von", "erfasst_am",
        }
        fehlend = pflicht - set(spalten)
        self.assertFalse(fehlend, f"ereignisse: Spalten fehlen: {fehlend}")

    def test_ereignis_positionen_tabelle_existiert(self):
        with sqlite3.connect(self._db_pfad) as conn:
            conn.row_factory = sqlite3.Row
            spalten = {r["name"] for r in conn.execute(
                "PRAGMA table_info(ereignis_positionen)"
            ).fetchall()}
        pflicht = {"id", "ereignis_id", "position_key", "wirkung",
                    "betrag", "kuerzungsart_id", "ersetzt_durch"}
        fehlend = pflicht - spalten
        self.assertFalse(fehlend,
                          f"ereignis_positionen: Spalten fehlen: {fehlend}")

    def test_position_ereignis_cache_tabelle_existiert(self):
        with sqlite3.connect(self._db_pfad) as conn:
            conn.row_factory = sqlite3.Row
            spalten = {r["name"] for r in conn.execute(
                "PRAGMA table_info(position_ereignis_cache)"
            ).fetchall()}
        pflicht = {"akte_az", "position_key", "ereignis_id",
                    "ereignistyp", "richtung", "datum", "dokument_id",
                    "wirkung", "betrag", "status", "kuerzungsart_id"}
        fehlend = pflicht - spalten
        self.assertFalse(
            fehlend,
            f"position_ereignis_cache: Spalten fehlen: {fehlend}",
        )

    def test_km1_unique_ereignis_positionen(self):
        """K-M1 (freigabe.md): mehrere Kuerzungsarten auf derselben
        Position im selben Ereignis sind ok. UNIQUE greift nur bei
        gleicher (ereignis_id, position_key, wirkung, kuerzungsart)."""
        with sqlite3.connect(self._db_pfad) as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('44/22', '2022-01-01', 'offen')"
            )
            conn.execute(
                "INSERT INTO ereignisse "
                "(akte_az, ereignistyp, richtung, quelle, datum) "
                "VALUES ('44/22', 'pruefbericht_eingegangen', 'eingehend', "
                "'dokument', '2022-04-27')"
            )
            eid = conn.execute(
                "SELECT id FROM ereignisse ORDER BY id DESC LIMIT 1"
            ).fetchone()[0]

            # Zwei Kuerzungen mit unterschiedlichen kuerzungsart_id:
            conn.execute(
                "INSERT INTO ereignis_positionen "
                "(ereignis_id, position_key, wirkung, betrag, kuerzungsart_id) "
                "VALUES (?, 'reparaturkosten', 'gekuerzt', 100, 1)",
                (eid,)
            )
            # Sollte NICHT crashen:
            conn.execute(
                "INSERT INTO ereignis_positionen "
                "(ereignis_id, position_key, wirkung, betrag, kuerzungsart_id) "
                "VALUES (?, 'reparaturkosten', 'gekuerzt', 50, 2)",
                (eid,)
            )
            # Dritte mit derselben kuerzungsart_id wie erste -> UNIQUE-Verletzung
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO ereignis_positionen "
                    "(ereignis_id, position_key, wirkung, betrag, kuerzungsart_id) "
                    "VALUES (?, 'reparaturkosten', 'gekuerzt', 33, 1)",
                    (eid,)
                )
            conn.commit()

    def test_schema_version_51(self):
        with sqlite3.connect(self._db_pfad) as conn:
            row = conn.execute(
                "SELECT beschreibung FROM schema_version WHERE version = 51"
            ).fetchone()
        self.assertIsNotNone(row, "schema_version 51 fehlt")

    def test_idempotent(self):
        from backend.db.schema_manager import init_db
        init_db()
        init_db()
        with sqlite3.connect(self._db_pfad) as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM schema_version WHERE version = 51"
            ).fetchone()[0]
        self.assertEqual(n, 1)


if __name__ == "__main__":
    unittest.main()
