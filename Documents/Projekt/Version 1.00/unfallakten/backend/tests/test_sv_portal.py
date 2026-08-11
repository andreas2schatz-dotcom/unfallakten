import os
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key-sv-portal")
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


from backend.app import erstelle_app


@pytest.fixture
def app_client(request, tmp_path):
    """Flask-Testclient mit eigener frischer DB (kein Verlass auf das
    DB_PATH-Environment zuvor gelaufener Testmodule)."""
    import importlib
    os.environ["DB_PATH"] = str(tmp_path / f"svp_{request.node.name}.db")
    os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-minimum-32-chars!!")
    import backend.db.database as db_mod
    import backend.db.schema_manager as sm_mod
    import backend.models.benutzer as ben_mod
    import backend.auth.jwt_handler as jwt_mod
    import backend.auth.middleware as mw_mod
    import backend.auth.service as svc_mod
    import backend.routers.auth_routes as auth_routes_mod
    import backend.app as app_mod
    for m in (db_mod, sm_mod, ben_mod, jwt_mod, mw_mod, svc_mod,
              auth_routes_mod, app_mod):
        importlib.reload(m)
    from backend.db.database import get_connection
    app = app_mod.erstelle_app(test_config={"TESTING": True})

    def _cleanup():
        with app.app_context():
            with get_connection() as conn:
                conn.execute("DELETE FROM sv_portal_accounts")
                conn.commit()

    _cleanup()
    with app.test_client() as c:
        rv = c.post("/auth/login",
                    json={"email": "admin@test.de", "passwort": "Admin123!"},
                    content_type="application/json")
        data = rv.get_json() or {}
        token = data.get("access_token", "")
        c.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        yield c
    _cleanup()


def test_sv_portal_liste_leer(app_client):
    rv = app_client.get("/einstellungen/sv-portal")
    assert rv.status_code == 200
    assert rv.get_json() == []


def test_sv_portal_anlegen_und_loeschen(app_client):
    with patch("backend.routers.sv_portal_routes.hole_adresse_by_nr") as mock_lookup:
        mock_lookup.return_value = {
            "adressnr": 4721,
            "name": "Seifert",
            "vorname": "Karl",
            "email": "k.seifert@sv-buero.de",
        }
        rv = app_client.post("/einstellungen/sv-portal",
                             json={"adressnr": 4721},
                             content_type="application/json")
    assert rv.status_code == 201
    data = rv.get_json()
    assert data["adressnr"] == 4721
    assert data["email"] == "k.seifert@sv-buero.de"

    rv2 = app_client.delete("/einstellungen/sv-portal/4721")
    assert rv2.status_code == 200
    assert rv2.get_json()["geloescht"] is True

    rv3 = app_client.get("/einstellungen/sv-portal")
    assert rv3.get_json() == []


def test_sv_portal_einladung_setzt_zeitstempel(app_client):
    with patch("backend.routers.sv_portal_routes.hole_adresse_by_nr") as mock_lookup:
        mock_lookup.return_value = {
            "adressnr": 100, "name": "X", "vorname": "", "email": "x@test.de"
        }
        app_client.post("/einstellungen/sv-portal",
                        json={"adressnr": 100}, content_type="application/json")
    rv = app_client.post("/einstellungen/sv-portal/100/einladung")
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["einladung_gesendet_am"] is not None


def test_sv_portal_toggle_portal_aktiv_legt_akte_on_demand_an(app_client):
    # Heutige Semantik: Akten kommen aus RA-MICRO (SSOT); die lokale Zeile
    # wird beim Toggle on demand angelegt (INSERT OR IGNORE) statt 404.
    rv = app_client.patch(
        "/einstellungen/sv-portal/akten/999%2F99/portal_aktiv",
        json={"portal_aktiv": 1},
        content_type="application/json",
    )
    assert rv.status_code == 200
    assert rv.get_json() == {"az": "999/99", "portal_aktiv": 1}
    from backend.db.database import get_connection
    with get_connection() as conn:
        row = conn.execute(
            "SELECT portal_aktiv FROM unfallakte WHERE az = '999/99'"
        ).fetchone()
    assert row is not None and row["portal_aktiv"] == 1
