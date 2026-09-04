"""
Migration 73 (Nachfuellen) und 74 (dokumente.typ entfernen).

Prueft auf einer Frisch-Datenbank mit kuenstlichem Altbestand, dass die
Feinklasse aus der Freigabe uebernommen wird, Altwerte ohne Registry-
Entsprechung bereinigt werden und die Spalte danach verschwindet.
"""
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestMigration73Nachfuellen(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="mig73_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        self._alt = _db.DB_PATH
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad
        from backend.db.schema_manager import init_db
        init_db()
        self._stelle_typ_spalte_wieder_her()

    def _stelle_typ_spalte_wieder_her(self):
        """Bildet den Zustand VOR Migration 74 nach.

        init_db() faehrt auf einer Frisch-Datenbank alle Migrationen durch,
        also auch 74 -- dort ist typ danach weg. Migration 73 arbeitet aber
        gerade auf Datenbanken, die die Spalte noch fuehren; ohne sie liefe
        der Test am zu pruefenden Zweig vorbei.
        """
        from backend.db.database import get_connection
        with get_connection() as conn:
            spalten = {r[1] for r in conn.execute(
                "PRAGMA table_info(dokumente)").fetchall()}
            if "typ" not in spalten:
                conn.execute("ALTER TABLE dokumente ADD COLUMN typ TEXT")
                conn.commit()

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt
        os.environ.pop("DB_PATH", None)
        try:
            os.unlink(self._db_pfad)
        except OSError:
            pass

    def test_klasse_kommt_aus_der_freigabe(self):
        from backend.db.database import get_connection
        from backend.db.schema_manager import _run_migration_73
        with get_connection() as conn:
            conn.execute("INSERT INTO unfallakte (az, unfalldatum, status) "
                         "VALUES ('31/21','2021-04-27','offen')")
            conn.execute(
                "INSERT INTO dokumente (id, akte_id, typ, dokumentenklasse, "
                " dateiname, dateipfad) "
                "VALUES (1,'31/21','sonstiges',NULL,'a.pdf','/tmp/a.pdf')")
            conn.execute(
                "INSERT INTO intake_dokumente (id, sha256, arbeitskopie_pfad, "
                " klasse, queue_status) "
                "VALUES (7, ?, '/tmp/a.pdf','sv_rechnung','freigegeben')",
                ("a" * 64,))
            conn.execute("INSERT INTO freigaben (intake_dokument_id, akte_az, "
                         "dokument_id) VALUES (7,'31/21',1)")
            conn.commit()
            _run_migration_73(conn)
            row = conn.execute("SELECT dokumentenklasse FROM dokumente "
                               "WHERE id=1").fetchone()
        self.assertEqual(row["dokumentenklasse"], "sv_rechnung")

    def test_altwerte_ohne_registry_werden_bereinigt(self):
        from backend.db.database import get_connection
        from backend.db.schema_manager import _run_migration_73
        with get_connection() as conn:
            conn.execute("INSERT INTO unfallakte (az, unfalldatum, status) "
                         "VALUES ('31/21','2021-04-27','offen')")
            for i, k in ((1, "gutachterrechnung"), (2, "versicherung")):
                conn.execute(
                    "INSERT INTO dokumente (id, akte_id, typ, "
                    " dokumentenklasse, dateiname, dateipfad) "
                    "VALUES (?,'31/21','sonstiges',?,'a.pdf','/tmp/a.pdf')",
                    (i, k))
            conn.commit()
            _run_migration_73(conn)
            werte = [r["dokumentenklasse"] for r in conn.execute(
                "SELECT dokumentenklasse FROM dokumente ORDER BY id")]
        self.assertEqual(werte, ["sv_rechnung", "sonstiges"])

    def test_ohne_freigabe_faellt_auf_typ_zurueck(self):
        from backend.db.database import get_connection
        from backend.db.schema_manager import _run_migration_73
        with get_connection() as conn:
            conn.execute("INSERT INTO unfallakte (az, unfalldatum, status) "
                         "VALUES ('31/21','2021-04-27','offen')")
            conn.execute(
                "INSERT INTO dokumente (id, akte_id, typ, dokumentenklasse, "
                " dateiname, dateipfad) "
                "VALUES (1,'31/21','klage',NULL,'k.pdf','/tmp/k.pdf')")
            conn.commit()
            _run_migration_73(conn)
            row = conn.execute("SELECT dokumentenklasse FROM dokumente "
                               "WHERE id=1").fetchone()
        self.assertEqual(row["dokumentenklasse"], "klage")

    def test_index_auf_dokumentenklasse_existiert(self):
        from backend.db.database import get_connection
        from backend.db.schema_manager import _run_migration_73
        with get_connection() as conn:
            _run_migration_73(conn)
            namen = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND tbl_name='dokumente'")]
        self.assertIn("idx_dok_klasse", namen)


class TestMigration74SpalteFaellt(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="mig74_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        self._alt = _db.DB_PATH
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad
        from backend.db.schema_manager import init_db
        init_db()

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt
        os.environ.pop("DB_PATH", None)
        try:
            os.unlink(self._db_pfad)
        except OSError:
            pass

    def test_typ_ist_weg_und_daten_bleiben(self):
        from backend.db.database import get_connection
        from backend.db.schema_manager import _run_migration_74
        with get_connection() as conn:
            vorher = conn.execute("SELECT COUNT(*) FROM dokumente").fetchone()[0]
            _run_migration_74(conn)
            spalten = {r[1] for r in conn.execute(
                "PRAGMA table_info(dokumente)").fetchall()}
            nachher = conn.execute("SELECT COUNT(*) FROM dokumente").fetchone()[0]
            indizes = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND tbl_name='dokumente'")]
        self.assertNotIn("typ", spalten)
        self.assertIn("dokumentenklasse", spalten)
        self.assertEqual(vorher, nachher)
        self.assertNotIn("idx_dokumente_typ", indizes)

    def test_zweiter_aufruf_ist_folgenlos(self):
        from backend.db.database import get_connection
        from backend.db.schema_manager import _run_migration_74
        with get_connection() as conn:
            _run_migration_74(conn)
            _run_migration_74(conn)
            spalten = {r[1] for r in conn.execute(
                "PRAGMA table_info(dokumente)").fetchall()}
        self.assertNotIn("typ", spalten)

    def test_fremdschluessel_bleiben_heil(self):
        from backend.db.database import get_connection
        from backend.db.schema_manager import _run_migration_74
        with get_connection() as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            _run_migration_74(conn)
            verletzungen = conn.execute("PRAGMA foreign_key_check").fetchall()
        self.assertEqual(verletzungen, [])


if __name__ == "__main__":
    unittest.main()
