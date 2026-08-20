import os
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key-migration-69")
import sqlite3
import pytest
from backend.db.schema_manager import _run_migration_69


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript("""
        CREATE TABLE schema_version (version INTEGER PRIMARY KEY, beschreibung TEXT);
        CREATE TABLE unfallakte (
            az TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'offen',
            kurzbezeichnung TEXT,
            portal_aktiv INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE beteiligte (
            id INTEGER PRIMARY KEY,
            akte_id TEXT,
            rolle TEXT,
            email TEXT
        );
        CREATE TABLE dokumente (
            id INTEGER PRIMARY KEY,
            akte_id TEXT,
            dateiname TEXT
        );
        CREATE TABLE unfalldetails (
            akte_id TEXT PRIMARY KEY
        );
        CREATE TABLE forderung_positionen (
            id INTEGER PRIMARY KEY,
            akte_id TEXT REFERENCES unfallakte(az) ON DELETE CASCADE,
            dokument_id INTEGER REFERENCES dokumente_alt(id) ON DELETE SET NULL,
            position_key TEXT
        );
        CREATE TABLE abrechnungsschreiben (
            id INTEGER PRIMARY KEY,
            akte_id TEXT REFERENCES unfallakte(az) ON DELETE CASCADE,
            dokument_id INTEGER REFERENCES dokumente_alt(id) ON DELETE SET NULL,
            datum TEXT,
            versicherung TEXT
        );
    """)
    return c


def _spalten(c, tabelle):
    return {r[1] for r in c.execute(f"PRAGMA table_info({tabelle})").fetchall()}


def _tabellen(c):
    return {r[0] for r in c.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}


def test_neue_spalten_fuer_ablage_und_sperre(conn):
    _run_migration_69(conn)
    assert _spalten(conn, "unfallakte") >= {
        "ramicro_abgelegt", "ramicro_ablage_datum",
        "status_vor_ablage", "portal_gesperrt",
    }


def test_portal_gesperrt_standard_ist_frei(conn):
    _run_migration_69(conn)
    conn.execute("INSERT INTO unfallakte (az) VALUES ('1/26')")
    row = conn.execute(
        "SELECT portal_gesperrt FROM unfallakte WHERE az = '1/26'"
    ).fetchone()
    assert row["portal_gesperrt"] == 0


def test_nachgeholte_spalten_aus_migration_38_39_45(conn):
    _run_migration_69(conn)
    assert "gutachten_nr" in _spalten(conn, "beteiligte")
    assert "portal_sichtbar" in _spalten(conn, "dokumente")
    assert "regulierung_status" in _spalten(conn, "unfallakte")
    assert "erstellt_am" in _spalten(conn, "unfalldetails")


def test_nachgeholte_tabellen(conn):
    _run_migration_69(conn)
    assert _tabellen(conn) >= {
        "portal_sync_queue", "portal_einladungen", "fragebogen_erstkontakt",
    }


def test_fremdschluessel_zeigt_auf_dokumente(conn):
    _run_migration_69(conn)
    for tabelle in ("forderung_positionen", "abrechnungsschreiben"):
        ziele = {r["table"] for r in conn.execute(
            f'PRAGMA foreign_key_list("{tabelle}")'
        ).fetchall()}
        assert "dokumente_alt" not in ziele
        assert "dokumente" in ziele


def test_akte_ist_loeschbar_mit_fremdschluesselpruefung(conn):
    _run_migration_69(conn)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("INSERT INTO unfallakte (az) VALUES ('2/26')")
    conn.execute(
        "INSERT INTO forderung_positionen (akte_id, position_key) VALUES ('2/26', 'sv_kosten')"
    )
    conn.execute("DELETE FROM unfallakte WHERE az = '2/26'")
    rest = conn.execute(
        "SELECT COUNT(*) AS n FROM forderung_positionen WHERE akte_id = '2/26'"
    ).fetchone()
    assert rest["n"] == 0


def test_bestandsdaten_bleiben_erhalten(conn):
    conn.execute("INSERT INTO unfallakte (az) VALUES ('3/26')")
    conn.execute(
        "INSERT INTO abrechnungsschreiben (akte_id, datum, versicherung) "
        "VALUES ('3/26', '2026-01-02', 'HUK')"
    )
    _run_migration_69(conn)
    row = conn.execute(
        "SELECT datum, versicherung FROM abrechnungsschreiben WHERE akte_id = '3/26'"
    ).fetchone()
    assert row["datum"] == "2026-01-02"
    assert row["versicherung"] == "HUK"


def test_fk_reparatur_mit_abhaengiger_view(conn):
    conn.execute("""
        CREATE VIEW v_regulierungsstatus AS
        SELECT ab.akte_id, ab.versicherung
        FROM abrechnungsschreiben ab
    """)
    _run_migration_69(conn)
    ziele = {r["table"] for r in conn.execute(
        'PRAGMA foreign_key_list("abrechnungsschreiben")'
    ).fetchall()}
    assert "dokumente" in ziele
    assert conn.execute("SELECT * FROM v_regulierungsstatus").fetchall() == []


def test_ist_wiederholbar(conn):
    _run_migration_69(conn)
    _run_migration_69(conn)
    assert "portal_gesperrt" in _spalten(conn, "unfallakte")


def test_stempelt_version_69(conn):
    _run_migration_69(conn)
    row = conn.execute(
        "SELECT beschreibung FROM schema_version WHERE version = 69"
    ).fetchone()
    assert row is not None
    assert row["beschreibung"] != "Migration 69"
