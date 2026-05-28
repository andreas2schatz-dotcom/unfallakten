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


from unittest.mock import patch, MagicMock
from backend.ramicro.adress_service import hole_adresse_by_nr
from backend.ramicro.connector import RaMicroNichtAktiv, RaMicroVerbindungsFehler


def _mock_cursor(row):
    """Hilfsfunktion: gibt Cursor-Mock mit fetchone()-Ergebnis zurück."""
    cur = MagicMock()
    cur.fetchone.return_value = row
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn


def test_hole_adresse_by_nr_gibt_dict_zurueck():
    fake_row = {
        "adressnr": 4721,
        "name": "Seifert",
        "vorname": "Karl",
        "email": "k.seifert@sv-buero.de",
    }
    mock_conn = _mock_cursor(fake_row)
    with patch("backend.ramicro.adress_service.get_ramicro_connection") as mock_ctx:
        mock_ctx.return_value.__enter__ = lambda s: mock_conn
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        result = hole_adresse_by_nr(4721)
    assert result == {
        "adressnr": 4721,
        "name": "Seifert",
        "vorname": "Karl",
        "email": "k.seifert@sv-buero.de",
    }


def test_hole_adresse_by_nr_gibt_none_bei_nicht_gefunden():
    mock_conn = _mock_cursor(None)
    with patch("backend.ramicro.adress_service.get_ramicro_connection") as mock_ctx:
        mock_ctx.return_value.__enter__ = lambda s: mock_conn
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        result = hole_adresse_by_nr(9999)
    assert result is None


def test_hole_adresse_by_nr_gibt_none_bei_ramicro_inaktiv():
    with patch("backend.ramicro.adress_service.get_ramicro_connection") as mock_ctx:
        mock_ctx.side_effect = RaMicroNichtAktiv("deaktiviert")
        result = hole_adresse_by_nr(1)
    assert result is None
