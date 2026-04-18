import sqlite3
import pytest
from backend.db.schema_manager import _run_migration_38


@pytest.fixture
def fresh_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE schema_version (version INTEGER PRIMARY KEY, beschreibung TEXT);
        CREATE TABLE benutzer (id INTEGER PRIMARY KEY, name TEXT, email TEXT UNIQUE,
            passwort_hash TEXT, rolle TEXT DEFAULT 'sachbearbeiter',
            aktiv INTEGER DEFAULT 1, erstellt_am TEXT, zuletzt_login TEXT);
        CREATE TABLE unfallakte (az TEXT PRIMARY KEY, unfalldatum TEXT DEFAULT '',
            status TEXT DEFAULT 'offen', haftungsquote REAL DEFAULT 100.0,
            erstellt_am TEXT DEFAULT (datetime('now','localtime')));
        CREATE TABLE dokumente (id INTEGER PRIMARY KEY, akte_id TEXT, typ TEXT,
            dateiname TEXT, dateipfad TEXT, dateityp TEXT DEFAULT 'pdf');
        CREATE TABLE beteiligte (id INTEGER PRIMARY KEY, akte_id TEXT,
            rolle TEXT, name TEXT, email TEXT);
    """)
    return conn


def test_migration_38_fuegt_portal_spalten_zu_unfallakte(fresh_conn):
    _run_migration_38(fresh_conn)
    spalten = {r[1] for r in fresh_conn.execute("PRAGMA table_info(unfallakte)").fetchall()}
    assert "portal_aktiv" in spalten
    assert "portal_sync_pending" in spalten
    assert "portal_last_sync" in spalten


def test_migration_38_fuegt_portal_sichtbar_zu_dokumente(fresh_conn):
    _run_migration_38(fresh_conn)
    spalten = {r[1] for r in fresh_conn.execute("PRAGMA table_info(dokumente)").fetchall()}
    assert "portal_sichtbar" in spalten


def test_migration_38_erstellt_portal_tabellen(fresh_conn):
    _run_migration_38(fresh_conn)
    tables = {r[0] for r in fresh_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert "portal_sync_queue" in tables
    assert "portal_einladungen" in tables


def test_migration_38_ist_idempotent(fresh_conn):
    _run_migration_38(fresh_conn)
    _run_migration_38(fresh_conn)  # Darf keinen Fehler werfen


def test_migration_38_default_werte(fresh_conn):
    _run_migration_38(fresh_conn)
    fresh_conn.execute("INSERT INTO unfallakte (az) VALUES ('TEST/001')")
    row = fresh_conn.execute(
        "SELECT portal_aktiv, portal_sync_pending FROM unfallakte WHERE az = 'TEST/001'"
    ).fetchone()
    assert row["portal_aktiv"] == 0
    assert row["portal_sync_pending"] == 0


def test_portal_sync_queue_check_constraint(fresh_conn):
    _run_migration_38(fresh_conn)
    with pytest.raises(sqlite3.IntegrityError):
        fresh_conn.execute(
            "INSERT INTO portal_sync_queue (akte_id, sync_version, status) VALUES (?,?,?)",
            ("X/01", 1, "ungueltig")
        )
        fresh_conn.commit()
