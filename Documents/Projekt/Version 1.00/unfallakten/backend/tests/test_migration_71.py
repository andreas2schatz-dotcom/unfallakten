"""Tests fuer die klasse_quelle-Check-Reparatur (Migration 71/72).

Deckt den Bestandsfall ab, der in der Praxis schiefging: eine Datenbank
mit der ALTEN CHECK-Klausel und vorhandenen Zeilen, nicht nur die frische
Test-DB, auf der die Migration ohnehin sauber durchlaeuft.
"""
import os
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key-migration-71")
import sqlite3

import pytest

from backend.db.schema_manager import (
    _repariere_klasse_quelle_check, _run_migration_71, _run_migration_72,
)

_ALTE_DDL = """
    CREATE TABLE intake_dokumente (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        sha256              TEXT NOT NULL UNIQUE,
        klasse              TEXT,
        klasse_quelle       TEXT CHECK (klasse_quelle IN ('auto','manuell')),
        konfidenz           REAL,
        queue_status        TEXT NOT NULL DEFAULT 'neu',
        erstellt_am         TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    )
"""


@pytest.fixture
def conn_bestand():
    """Bildet den Live-Zustand nach: alte Klausel, mehrere Zeilen."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY, beschreibung TEXT)")
    c.execute(_ALTE_DDL)
    c.execute("CREATE INDEX idx_intake_dok_sha ON intake_dokumente(sha256)")
    c.execute("CREATE INDEX idx_intake_dok_queue ON intake_dokumente(queue_status)")
    for i in range(5):
        c.execute(
            "INSERT INTO intake_dokumente (sha256, klasse, klasse_quelle) "
            "VALUES (?, 'sonstiges', 'auto')",
            (f"hash-{i}",),
        )
    c.commit()
    return c


class TestReparaturAufBestandsdatenbank:
    def test_klausel_wird_erweitert(self, conn_bestand):
        _repariere_klasse_quelle_check(conn_bestand)
        ddl = conn_bestand.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='intake_dokumente'"
        ).fetchone()[0]
        assert "klasse_quelle IN ('auto','manuell','fragebogen')" in ddl

    def test_zeilenzahl_bleibt_erhalten(self, conn_bestand):
        _repariere_klasse_quelle_check(conn_bestand)
        n = conn_bestand.execute("SELECT COUNT(*) FROM intake_dokumente").fetchone()[0]
        assert n == 5

    def test_bestandsdaten_bleiben_inhaltlich_gleich(self, conn_bestand):
        _repariere_klasse_quelle_check(conn_bestand)
        rows = conn_bestand.execute(
            "SELECT sha256, klasse, klasse_quelle FROM intake_dokumente ORDER BY sha256"
        ).fetchall()
        assert [r["sha256"] for r in rows] == [f"hash-{i}" for i in range(5)]
        assert all(r["klasse_quelle"] == "auto" for r in rows)

    def test_indizes_bleiben_erhalten(self, conn_bestand):
        _repariere_klasse_quelle_check(conn_bestand)
        namen = {
            r["name"] for r in conn_bestand.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='intake_dokumente'"
            ).fetchall()
        }
        assert "idx_intake_dok_sha" in namen
        assert "idx_intake_dok_queue" in namen

    def test_einschub_mit_fragebogen_geht_danach_durch(self, conn_bestand):
        _repariere_klasse_quelle_check(conn_bestand)
        conn_bestand.execute(
            "INSERT INTO intake_dokumente (sha256, klasse, klasse_quelle) "
            "VALUES ('neu-fragebogen', 'fragebogen', 'fragebogen')"
        )
        row = conn_bestand.execute(
            "SELECT klasse_quelle FROM intake_dokumente WHERE sha256='neu-fragebogen'"
        ).fetchone()
        assert row["klasse_quelle"] == "fragebogen"

    def test_zweiter_lauf_ist_no_op(self, conn_bestand):
        _repariere_klasse_quelle_check(conn_bestand)
        n_vorher = conn_bestand.execute("SELECT COUNT(*) FROM intake_dokumente").fetchone()[0]
        _repariere_klasse_quelle_check(conn_bestand)
        n_nachher = conn_bestand.execute("SELECT COUNT(*) FROM intake_dokumente").fetchone()[0]
        assert n_vorher == n_nachher == 5


class TestFailLoudBeiUnerwarteterDdl:
    def test_bricht_hart_ab_wenn_klausel_nicht_gefunden_wird(self):
        c = sqlite3.connect(":memory:")
        c.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY, beschreibung TEXT)")
        c.execute("""
            CREATE TABLE intake_dokumente (
                id INTEGER PRIMARY KEY,
                sha256 TEXT,
                klasse_quelle TEXT CHECK (klasse_quelle IN ('auto', 'manuell'))
            )
        """)
        c.commit()
        with pytest.raises(RuntimeError):
            _repariere_klasse_quelle_check(c)
        n = c.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='intake_dokumente'"
        ).fetchone()[0]
        assert n == 1, "Originaltabelle darf bei Abbruch nicht verloren gehen"


class TestMigration71Und72:
    def test_migration_71_stempelt_version_71(self, conn_bestand):
        _run_migration_71(conn_bestand)
        v = conn_bestand.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
        assert v == 71
        ddl = conn_bestand.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='intake_dokumente'"
        ).fetchone()[0]
        assert "klasse_quelle IN ('auto','manuell','fragebogen')" in ddl

    def test_migration_72_repariert_falsch_gestempelte_71(self, conn_bestand):
        """
        Bildet exakt die Reloader-Falle nach: schema_version traegt schon
        71 (generischer Text aus dem else-Zweig), aber die Klausel wurde
        nie erweitert, weil _run_migration_71 nie lief.
        """
        conn_bestand.execute(
            "INSERT INTO schema_version (version, beschreibung) VALUES (71, 'Migration 71')"
        )
        conn_bestand.commit()
        ddl_vorher = conn_bestand.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='intake_dokumente'"
        ).fetchone()[0]
        assert "'fragebogen'" not in ddl_vorher

        _run_migration_72(conn_bestand)

        ddl_nachher = conn_bestand.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='intake_dokumente'"
        ).fetchone()[0]
        assert "klasse_quelle IN ('auto','manuell','fragebogen')" in ddl_nachher
        v = conn_bestand.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
        assert v == 72
        n = conn_bestand.execute("SELECT COUNT(*) FROM intake_dokumente").fetchone()[0]
        assert n == 5
