import sqlite3
import pytest
from backend.db.schema_manager import _run_migration_39


@pytest.fixture
def fresh_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE schema_version (version INTEGER PRIMARY KEY, beschreibung TEXT);
        CREATE TABLE beteiligte (id INTEGER PRIMARY KEY, akte_id TEXT,
            rolle TEXT, name TEXT, email TEXT);
    """)
    return conn


def test_migration_39_fuegt_gutachten_nr_zu_beteiligte(fresh_conn):
    _run_migration_39(fresh_conn)
    spalten = {r[1] for r in fresh_conn.execute("PRAGMA table_info(beteiligte)").fetchall()}
    assert "gutachten_nr" in spalten


def test_migration_39_ist_idempotent(fresh_conn):
    _run_migration_39(fresh_conn)
    _run_migration_39(fresh_conn)  # Darf keinen Fehler werfen


def test_migration_39_schreibt_schema_version(fresh_conn):
    _run_migration_39(fresh_conn)
    row = fresh_conn.execute(
        "SELECT version FROM schema_version WHERE version = 39"
    ).fetchone()
    assert row is not None


def test_migration_39_gutachten_nr_nullable(fresh_conn):
    _run_migration_39(fresh_conn)
    fresh_conn.execute(
        "INSERT INTO beteiligte (akte_id, rolle, name) VALUES ('TEST/001', 'sachverstaendiger', 'Müller')"
    )
    row = fresh_conn.execute(
        "SELECT gutachten_nr FROM beteiligte WHERE akte_id = 'TEST/001'"
    ).fetchone()
    assert row["gutachten_nr"] is None
