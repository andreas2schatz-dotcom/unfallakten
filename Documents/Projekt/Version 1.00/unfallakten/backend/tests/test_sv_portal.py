import sqlite3
import pytest
from backend.db.schema_manager import _run_migration_41


@pytest.fixture
def fresh_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE schema_version (version INTEGER PRIMARY KEY, beschreibung TEXT);
        CREATE TABLE unfallakte (
            az TEXT PRIMARY KEY,
            unfalldatum TEXT DEFAULT '',
            portal_aktiv INTEGER NOT NULL DEFAULT 0,
            portal_sync_pending INTEGER NOT NULL DEFAULT 0,
            portal_last_sync TEXT,
            kurzbezeichnung TEXT,
            status TEXT DEFAULT 'offen'
        );
        CREATE TABLE beteiligte (
            id INTEGER PRIMARY KEY,
            akte_id TEXT,
            rolle TEXT,
            name TEXT,
            email TEXT
        );
    """)
    return conn


def test_migration_41_erstellt_tabelle(fresh_conn):
    _run_migration_41(fresh_conn)
    tables = {r[0] for r in fresh_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert "sv_portal_accounts" in tables


def test_migration_41_spalten(fresh_conn):
    _run_migration_41(fresh_conn)
    spalten = {r[1] for r in fresh_conn.execute(
        "PRAGMA table_info(sv_portal_accounts)"
    ).fetchall()}
    assert spalten >= {"adressnr", "name", "vorname", "email",
                       "portal_aktiv", "einladung_gesendet_am", "angelegt_am"}


def test_migration_41_default_portal_aktiv(fresh_conn):
    _run_migration_41(fresh_conn)
    fresh_conn.execute(
        "INSERT INTO sv_portal_accounts (adressnr, name, email) VALUES (1, 'Test', 'a@b.de')"
    )
    row = fresh_conn.execute(
        "SELECT portal_aktiv FROM sv_portal_accounts WHERE adressnr = 1"
    ).fetchone()
    assert row["portal_aktiv"] == 1


def test_migration_41_email_unique(fresh_conn):
    _run_migration_41(fresh_conn)
    fresh_conn.execute(
        "INSERT INTO sv_portal_accounts (adressnr, name, email) VALUES (1, 'A', 'x@y.de')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        fresh_conn.execute(
            "INSERT INTO sv_portal_accounts (adressnr, name, email) VALUES (2, 'B', 'x@y.de')"
        )


def test_migration_41_ist_idempotent(fresh_conn):
    _run_migration_41(fresh_conn)
    _run_migration_41(fresh_conn)  # Darf keinen Fehler werfen
