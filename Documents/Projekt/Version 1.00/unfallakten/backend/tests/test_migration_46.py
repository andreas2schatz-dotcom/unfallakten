"""
Tests fuer Migration 46 (Intake-Datenmodell S1.1).

Vier neue Tabellen:
    - intake_dokumente  (v7 "DOKUMENT", hash-dedupliziert, akte-unabhaengig)
    - zustellungen      (n:1 auf intake_dokumente, wird nie geloescht)
    - freigaben         (K-P2: eigene Relation intake_dokument <-> akte <-> dokumente)
    - korrektur_log     (Feld, alt/neu, Klasse, Registry-Version)

K-P2 (freigabe.md):
    - intake_dokumente enthaelt KEINE Spalten akte_az, freigegeben_von, freigegeben_am
    - freigaben ist eigene Tabelle: (intake_dokument_id, akte_az, dokument_id, ...)
    - Backfill: sha256-Duplikate ueber Akten hinweg -> EIN intake_dokument, n zustellungen, n freigaben
    - Testkriterium: zustellungen + freigaben = Anzahl bestehender dokumente-Zeilen
"""
import os
import sys
import unittest
import tempfile
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

_tmp_dir = tempfile.mkdtemp()


def _fresh_db(test_id: str):
    """Legt eine frische DB an, laesst create_schema+run_migrations laufen (inkl. 46)."""
    db_path = os.path.join(_tmp_dir, f"m46_{test_id}.db")
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
    return db_mod, sm_mod


def _insert_dokument(conn, akte_az, dokument_id, pdf_hash=None, dateiname="test.pdf",
                     dateipfad="test/test.pdf", typ="sonstiges", dateityp="pdf",
                     parse_json=None, parse_konfidenz=None, dokumentenklasse=None):
    """Fuegt eine Zeile in dokumente ein (fuer Backfill-Tests)."""
    # akte_id existiert erst nach Migration 5 als TEXT; unfallakte-Zeile anlegen
    conn.execute(
        "INSERT OR IGNORE INTO unfallakte (az, unfalldatum, status) VALUES (?, '', 'offen')",
        (akte_az,),
    )
    conn.execute(
        """
        INSERT INTO dokumente
            (id, akte_id, typ, dateiname, dateipfad, dateityp,
             parse_status, parse_konfidenz, parse_json,
             pdf_hash, dokumentenklasse)
        VALUES (?, ?, ?, ?, ?, ?, 'erfolgreich', ?, ?, ?, ?)
        """,
        (dokument_id, akte_az, typ, dateiname, dateipfad, dateityp,
         parse_konfidenz, parse_json, pdf_hash, dokumentenklasse),
    )


class TestMigration46Struktur(unittest.TestCase):
    """Grundlegender Aufbau der vier neuen Tabellen."""

    def test_intake_dokumente_hat_erforderliche_spalten(self):
        db_mod, _ = _fresh_db("struct_intake")
        with db_mod.get_connection() as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(intake_dokumente)").fetchall()}
        pflicht = {
            "id", "sha256", "original_pfad", "arbeitskopie_pfad",
            "payload_typ", "structured_payload",
            "klasse", "klasse_quelle", "konfidenz", "parse_json",
            "textquelle", "registry_version", "llm_stack",
            "queue_status", "prioritaet_frist", "loeschfrist_bis",
            "erstellt_am",
        }
        fehlend = pflicht - cols
        self.assertEqual(fehlend, set(), f"intake_dokumente: fehlende Spalten {fehlend}")

    def test_intake_dokumente_hat_KEINE_akte_freigabe_spalten(self):
        """K-P2: akte_az / freigegeben_* DUERFEN NICHT in intake_dokumente sein."""
        db_mod, _ = _fresh_db("struct_intake_kp2")
        with db_mod.get_connection() as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(intake_dokumente)").fetchall()}
        # Preflight: Tabelle muss existieren, sonst waere der Test trivial gruen.
        self.assertIn("id", cols, "intake_dokumente-Tabelle existiert nicht")
        verboten = {"akte_az", "freigegeben_von", "freigegeben_am"}
        drin = verboten & cols
        self.assertEqual(drin, set(),
                         f"K-P2 verletzt: intake_dokumente enthaelt {drin} — diese gehoeren in freigaben")

    def test_zustellungen_hat_erforderliche_spalten(self):
        db_mod, _ = _fresh_db("struct_zustellungen")
        with db_mod.get_connection() as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(zustellungen)").fetchall()}
        pflicht = {
            "id", "intake_dokument_id", "quelle", "absender", "auth_status",
            "betreff", "empfangen_am", "parent_id", "signale_json",
            "konto", "roh_referenz", "erstellt_am",
        }
        fehlend = pflicht - cols
        self.assertEqual(fehlend, set(), f"zustellungen: fehlende Spalten {fehlend}")

    def test_freigaben_tabelle_existiert_mit_richtigen_spalten(self):
        """K-P2: eigene Relation freigaben (intake_dokument_id, akte_az, dokument_id, ...)."""
        db_mod, _ = _fresh_db("struct_freigaben")
        with db_mod.get_connection() as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(freigaben)").fetchall()}
        pflicht = {
            "id", "intake_dokument_id", "akte_az", "dokument_id",
            "freigegeben_von", "freigegeben_am",
        }
        fehlend = pflicht - cols
        self.assertEqual(fehlend, set(), f"freigaben: fehlende Spalten {fehlend}")

    def test_korrektur_log_hat_erforderliche_spalten(self):
        db_mod, _ = _fresh_db("struct_korrekturlog")
        with db_mod.get_connection() as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(korrektur_log)").fetchall()}
        pflicht = {
            "id", "intake_dokument_id", "feld", "wert_alt", "wert_neu",
            "klasse", "registry_version", "benutzer_id", "zeitstempel",
        }
        fehlend = pflicht - cols
        self.assertEqual(fehlend, set(), f"korrektur_log: fehlende Spalten {fehlend}")


class TestMigration46Constraints(unittest.TestCase):
    """UNIQUE-Constraints und Idempotenz."""

    def test_sha256_ist_global_unique(self):
        """Doppelter sha256 in intake_dokumente wirft IntegrityError."""
        db_mod, _ = _fresh_db("uniq_sha")
        with db_mod.get_connection() as conn:
            conn.execute(
                "INSERT INTO intake_dokumente (sha256, payload_typ) VALUES (?, 'datei')",
                ("a" * 64,),
            )
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO intake_dokumente (sha256, payload_typ) VALUES (?, 'datei')",
                    ("a" * 64,),
                )

    def test_migration_46_ist_idempotent(self):
        """_run_migration_46 zweimal aufrufen darf keinen Fehler werfen."""
        db_mod, sm_mod = _fresh_db("idempotent")
        from backend.db.schema_manager import _run_migration_46
        with db_mod.get_connection() as conn:
            _run_migration_46(conn)  # 2. Aufruf

    def test_migration_46_schreibt_schema_version(self):
        db_mod, _ = _fresh_db("schemaver")
        with db_mod.get_connection() as conn:
            row = conn.execute(
                "SELECT version FROM schema_version WHERE version = 46"
            ).fetchone()
        self.assertIsNotNone(row, "schema_version-Eintrag fuer Migration 46 fehlt")
        self.assertEqual(row[0], 46)


class TestMigration46Backfill(unittest.TestCase):
    """K-P2-Backfill: sha256-Duplikate ueber Akten hinweg = EIN intake_dokument, n zustellungen, n freigaben."""

    def _prepare_docs(self, test_id, doks):
        """Legt Dokumente an, ruft dann Migration 46 erneut auf (Backfill idempotent)."""
        db_mod, _ = _fresh_db(test_id)
        with db_mod.get_connection() as conn:
            for d in doks:
                _insert_dokument(conn, **d)
            conn.commit()
        # Backfill erneut aufrufen (Migration 46 ist idempotent und findet die neuen dokumente-Zeilen)
        from backend.db.schema_manager import _run_migration_46
        with db_mod.get_connection() as conn:
            _run_migration_46(conn)
        return db_mod

    def test_backfill_je_dokument_eine_zustellung_und_eine_freigabe(self):
        """K-P2-Testkriterium: zustellungen + freigaben = Bestand (dokumente-Zeilen)."""
        db_mod = self._prepare_docs("bf_basic", [
            {"akte_az": "10/26", "dokument_id": 1001, "pdf_hash": "b" * 64, "dateiname": "d1.pdf"},
            {"akte_az": "11/26", "dokument_id": 1002, "pdf_hash": "c" * 64, "dateiname": "d2.pdf"},
            {"akte_az": "12/26", "dokument_id": 1003, "pdf_hash": "d" * 64, "dateiname": "d3.pdf"},
        ])
        with db_mod.get_connection() as conn:
            n_dok = conn.execute("SELECT COUNT(*) FROM dokumente").fetchone()[0]
            n_zust = conn.execute("SELECT COUNT(*) FROM zustellungen").fetchone()[0]
            n_frei = conn.execute("SELECT COUNT(*) FROM freigaben").fetchone()[0]
        self.assertEqual(n_dok, 3)
        self.assertEqual(n_zust, 3, "je dokumente-Zeile eine Zustellung")
        self.assertEqual(n_frei, 3, "je dokumente-Zeile eine Freigabe")

    def test_backfill_sha256_duplikat_ueber_akten_hinweg(self):
        """
        K-P2: gleicher sha256 in zwei Akten -> EIN intake_dokument mit 2 Zustellungen und 2 Freigaben.
        """
        shared_hash = "e" * 64
        db_mod = self._prepare_docs("bf_dup", [
            {"akte_az": "20/26", "dokument_id": 2001, "pdf_hash": shared_hash, "dateiname": "a.pdf"},
            {"akte_az": "21/26", "dokument_id": 2002, "pdf_hash": shared_hash, "dateiname": "a.pdf"},
        ])
        with db_mod.get_connection() as conn:
            n_intake = conn.execute(
                "SELECT COUNT(*) FROM intake_dokumente WHERE sha256 = ?", (shared_hash,)
            ).fetchone()[0]
            n_zust = conn.execute("SELECT COUNT(*) FROM zustellungen").fetchone()[0]
            n_frei = conn.execute("SELECT COUNT(*) FROM freigaben").fetchone()[0]
        self.assertEqual(n_intake, 1, "sha-Duplikat -> genau 1 intake_dokument")
        self.assertEqual(n_zust, 2, "aber n Zustellungen (n = Anzahl dokumente-Zeilen mit dem Hash)")
        self.assertEqual(n_frei, 2, "und n Freigaben")

    def test_backfill_ist_idempotent(self):
        """Backfill zweimal auszufuehren erzeugt keine Duplikate."""
        db_mod = self._prepare_docs("bf_idempotent", [
            {"akte_az": "30/26", "dokument_id": 3001, "pdf_hash": "f" * 64, "dateiname": "x.pdf"},
        ])
        # Nochmal
        from backend.db.schema_manager import _run_migration_46
        with db_mod.get_connection() as conn:
            _run_migration_46(conn)
            n_intake = conn.execute("SELECT COUNT(*) FROM intake_dokumente").fetchone()[0]
            n_zust = conn.execute("SELECT COUNT(*) FROM zustellungen").fetchone()[0]
            n_frei = conn.execute("SELECT COUNT(*) FROM freigaben").fetchone()[0]
        self.assertEqual(n_intake, 1)
        self.assertEqual(n_zust, 1)
        self.assertEqual(n_frei, 1)

    def test_backfill_dokumente_ohne_pdf_hash(self):
        """
        Alt-Dokumente ohne pdf_hash (aus der Zeit vor Migration 24) muessen auch backfilled werden.
        Synthese-Hash mit Prefix 'altbestand:' vermeidet Kollision mit echten SHA-256 (hex).
        """
        db_mod = self._prepare_docs("bf_nohash", [
            {"akte_az": "40/26", "dokument_id": 4001, "pdf_hash": None, "dateiname": "alt.pdf"},
            {"akte_az": "41/26", "dokument_id": 4002, "pdf_hash": "",   "dateiname": "alt2.pdf"},
        ])
        with db_mod.get_connection() as conn:
            n_intake = conn.execute("SELECT COUNT(*) FROM intake_dokumente").fetchone()[0]
            n_zust = conn.execute("SELECT COUNT(*) FROM zustellungen").fetchone()[0]
            n_frei = conn.execute("SELECT COUNT(*) FROM freigaben").fetchone()[0]
        self.assertEqual(n_intake, 2, "zwei distinkte intake_dokumente (jedes Alt-Dok ohne Hash bekommt eigenen Synthese-Hash)")
        self.assertEqual(n_zust, 2)
        self.assertEqual(n_frei, 2)

    def test_backfill_zustellung_hat_quelle_altbestand(self):
        db_mod = self._prepare_docs("bf_quelle", [
            {"akte_az": "50/26", "dokument_id": 5001, "pdf_hash": "1" * 64, "dateiname": "y.pdf"},
        ])
        with db_mod.get_connection() as conn:
            quelle = conn.execute("SELECT quelle FROM zustellungen").fetchone()[0]
        self.assertEqual(quelle, "altbestand")

    def test_backfill_freigabe_verweist_auf_dokumente_id(self):
        """K-P2 Kern: freigaben.dokument_id zeigt auf die alte dokumente(id) - die FK-Bruecke."""
        db_mod = self._prepare_docs("bf_fkbruecke", [
            {"akte_az": "60/26", "dokument_id": 6001, "pdf_hash": "2" * 64, "dateiname": "z.pdf"},
        ])
        with db_mod.get_connection() as conn:
            row = conn.execute(
                "SELECT akte_az, dokument_id FROM freigaben"
            ).fetchone()
        self.assertEqual(row[0], "60/26")
        self.assertEqual(row[1], 6001)


class TestMigration46LegacyDokumenteTabelle(unittest.TestCase):
    """
    Regression fuer den Bestandsschaden aus DECISIONS.md F-02:
    Auf der Produktiv-DB ist ``dokumente`` mit ``id INT`` (ohne PRIMARY KEY)
    angelegt. SQLite meldet dann bei jedem INSERT in freigaben "foreign key
    mismatch", selbst bei foreign_keys=OFF. Die Migration muss trotzdem laufen.
    """

    def test_backfill_laeuft_ohne_pk_auf_dokumente(self):
        """Legt dokumente OHNE PRIMARY KEY neu an — Backfill darf nicht scheitern."""
        db_path = os.path.join(_tmp_dir, "m46_legacy_pk.db")
        if os.path.exists(db_path):
            os.remove(db_path)
        os.environ["DB_PATH"] = db_path

        import importlib
        import backend.db.database as db_mod
        import backend.db.schema_manager as sm_mod
        for m in (db_mod, sm_mod):
            importlib.reload(m)

        # 1) sauberes Schema anlegen (via create_schema + alle Migrationen 2..45)
        sm_mod.create_schema()
        # Migrationen bis 45 einzeln aufrufen ist zu invasiv — wir laufen einfach
        # bis Version 45 durch, indem wir Migration 46 vorerst aus MIGRATIONS entfernen.
        entfernt = sm_mod.MIGRATIONS.pop(46, None)
        try:
            sm_mod.run_migrations()
        finally:
            if entfernt is not None:
                sm_mod.MIGRATIONS[46] = entfernt

        # 2) dokumente-Tabelle DESTRUKTIV neu anlegen mit `id INT` ohne PK — Bestandsschaden.
        with db_mod.get_connection() as conn:
            conn.execute("DROP TABLE IF EXISTS dokumente")
            conn.execute("""
                CREATE TABLE dokumente(
                    id INT, typ TEXT, dateiname TEXT, dateipfad TEXT, dateityp TEXT,
                    dateigroesse INT, hochgeladen_am TEXT, hochgeladen_von INT,
                    parse_status TEXT, parse_konfidenz REAL, parse_json TEXT,
                    parse_fehler TEXT, notizen TEXT, akte_id,
                    dokumentenklasse TEXT, pdf_hash TEXT, eakte_nr INTEGER,
                    eakte_pfad TEXT, quelle TEXT DEFAULT 'upload',
                    portal_sichtbar INT NOT NULL DEFAULT 0
                )
            """)
            conn.execute(
                "INSERT OR IGNORE INTO unfallakte (az, unfalldatum, status) VALUES ('99/26', '', 'offen')"
            )
            conn.execute(
                "INSERT INTO dokumente (id, akte_id, typ, dateiname, dateipfad, dateityp, "
                "parse_status, pdf_hash) VALUES (7001, '99/26', 'sonstiges', 'x.pdf', "
                "'a/x.pdf', 'pdf', 'erfolgreich', ?)",
                ("9" * 64,),
            )

        # 3) Migration 46 jetzt anwenden — DARF NICHT MIT FK MISMATCH SCHEITERN
        with db_mod.get_connection() as conn:
            sm_mod._run_migration_46(conn)
            n_frei = conn.execute("SELECT COUNT(*) FROM freigaben").fetchone()[0]
        self.assertEqual(n_frei, 1, "Backfill muss auch bei Legacy-dokumente-Schema laufen")


if __name__ == "__main__":
    unittest.main()
