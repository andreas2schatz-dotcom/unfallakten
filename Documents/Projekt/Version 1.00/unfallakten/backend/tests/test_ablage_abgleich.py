import os
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key-abgleich")
import sqlite3
import pytest
from backend.services import ablage_abgleich


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript("""
        CREATE TABLE unfallakte (
            az TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'offen',
            kurzbezeichnung TEXT,
            unfalldatum TEXT DEFAULT '',
            erstellt_am TEXT DEFAULT (datetime('now','localtime')),
            portal_aktiv INTEGER NOT NULL DEFAULT 0,
            portal_gesperrt INTEGER NOT NULL DEFAULT 0,
            portal_sync_pending INTEGER NOT NULL DEFAULT 0,
            ramicro_abgelegt INTEGER NOT NULL DEFAULT 0,
            ramicro_ablage_datum TEXT,
            status_vor_ablage TEXT
        );
    """)
    return c


def _antwort(monkeypatch, daten):
    monkeypatch.setattr(
        ablage_abgleich, "hole_ablage_status", lambda az_liste: daten
    )


def test_ablegen_setzt_status_und_sichert_den_vorherigen(monkeypatch, conn):
    conn.execute("INSERT INTO unfallakte (az, status) VALUES ('1/25', 'klage')")
    _antwort(monkeypatch, {"1/25": {
        "abgelegt": True, "ablage_datum": "2026-01-05", "kurzbezeichnung": "A/B"
    }})

    bericht = ablage_abgleich.abgleichen(conn)

    row = conn.execute("SELECT * FROM unfallakte WHERE az='1/25'").fetchone()
    assert row["ramicro_abgelegt"] == 1
    assert row["ramicro_ablage_datum"] == "2026-01-05"
    assert row["status"] == "abgeschlossen"
    assert row["status_vor_ablage"] == "klage"
    assert row["portal_sync_pending"] == 1
    assert bericht["abgelegt_neu"] == 1


def test_reaktivierung_stellt_den_vorherigen_status_wieder_her(monkeypatch, conn):
    conn.execute(
        "INSERT INTO unfallakte (az, status, ramicro_abgelegt, status_vor_ablage) "
        "VALUES ('2/25', 'abgeschlossen', 1, 'klage')"
    )
    _antwort(monkeypatch, {"2/25": {
        "abgelegt": False, "ablage_datum": None, "kurzbezeichnung": "C/D"
    }})

    bericht = ablage_abgleich.abgleichen(conn)

    row = conn.execute("SELECT * FROM unfallakte WHERE az='2/25'").fetchone()
    assert row["ramicro_abgelegt"] == 0
    assert row["ramicro_ablage_datum"] is None
    assert row["status"] == "klage"
    assert row["status_vor_ablage"] is None
    assert row["portal_sync_pending"] == 1
    assert bericht["reaktiviert"] == 1


def test_selbst_gesetzter_abschluss_bleibt_bei_reaktivierung(monkeypatch, conn):
    conn.execute(
        "INSERT INTO unfallakte (az, status, ramicro_abgelegt) "
        "VALUES ('3/25', 'abgeschlossen', 1)"
    )
    _antwort(monkeypatch, {"3/25": {
        "abgelegt": False, "ablage_datum": None, "kurzbezeichnung": ""
    }})

    ablage_abgleich.abgleichen(conn)

    row = conn.execute("SELECT * FROM unfallakte WHERE az='3/25'").fetchone()
    assert row["status"] == "abgeschlossen"
    assert row["ramicro_abgelegt"] == 0


def test_bereits_abgeschlossene_akte_bekommt_kein_status_vor_ablage(monkeypatch, conn):
    conn.execute(
        "INSERT INTO unfallakte (az, status) VALUES ('4/25', 'abgeschlossen')"
    )
    _antwort(monkeypatch, {"4/25": {
        "abgelegt": True, "ablage_datum": "2026-02-02", "kurzbezeichnung": ""
    }})

    ablage_abgleich.abgleichen(conn)

    row = conn.execute("SELECT * FROM unfallakte WHERE az='4/25'").fetchone()
    assert row["status_vor_ablage"] is None


def test_kurzbezeichnung_wird_uebernommen(monkeypatch, conn):
    conn.execute("INSERT INTO unfallakte (az) VALUES ('5/25')")
    _antwort(monkeypatch, {"5/25": {
        "abgelegt": False, "ablage_datum": None, "kurzbezeichnung": "Türe/Taskoparan"
    }})

    ablage_abgleich.abgleichen(conn)

    row = conn.execute("SELECT kurzbezeichnung FROM unfallakte WHERE az='5/25'").fetchone()
    assert row["kurzbezeichnung"] == "Türe/Taskoparan"


def test_vorschau_schreibt_nichts(monkeypatch, conn):
    conn.execute("INSERT INTO unfallakte (az, status) VALUES ('6/25', 'offen')")
    _antwort(monkeypatch, {"6/25": {
        "abgelegt": True, "ablage_datum": "2026-01-05", "kurzbezeichnung": "E/F"
    }})

    bericht = ablage_abgleich.abgleichen(conn, vorschau=True)

    row = conn.execute("SELECT * FROM unfallakte WHERE az='6/25'").fetchone()
    assert row["status"] == "offen"
    assert row["ramicro_abgelegt"] == 0
    assert bericht["abgelegt_neu"] == 1
    assert "6/25" in bericht["beispiele"]["abgelegt_neu"]


def test_mit_liste_werden_fehlende_akten_angelegt(monkeypatch, conn):
    _antwort(monkeypatch, {"7/25": {
        "abgelegt": True, "ablage_datum": "2026-03-03", "kurzbezeichnung": "G/H"
    }})

    bericht = ablage_abgleich.abgleichen(conn, az_liste=["7/25"])

    row = conn.execute("SELECT * FROM unfallakte WHERE az='7/25'").fetchone()
    assert row is not None
    assert row["kurzbezeichnung"] == "G/H"
    assert row["status"] == "abgeschlossen"
    assert bericht["angelegt"] == 1


def test_ohne_liste_werden_keine_akten_angelegt(monkeypatch, conn):
    _antwort(monkeypatch, {"8/25": {
        "abgelegt": True, "ablage_datum": None, "kurzbezeichnung": ""
    }})

    bericht = ablage_abgleich.abgleichen(conn)

    assert conn.execute("SELECT COUNT(*) AS n FROM unfallakte").fetchone()["n"] == 0
    assert bericht["angelegt"] == 0


def test_ramicro_nicht_erreichbar_aendert_nichts(monkeypatch, conn):
    conn.execute("INSERT INTO unfallakte (az, status) VALUES ('9/25', 'offen')")
    monkeypatch.setattr(ablage_abgleich, "hole_ablage_status", lambda az_liste: None)

    bericht = ablage_abgleich.abgleichen(conn)

    row = conn.execute("SELECT * FROM unfallakte WHERE az='9/25'").fetchone()
    assert row["status"] == "offen"
    assert bericht["ramicro_erreichbar"] is False
    assert bericht["abgelegt_neu"] == 0


def test_unveraenderte_akte_stoesst_keinen_sync_an(monkeypatch, conn):
    conn.execute(
        "INSERT INTO unfallakte (az, status, kurzbezeichnung, ramicro_abgelegt) "
        "VALUES ('10/25', 'offen', 'I/J', 0)"
    )
    _antwort(monkeypatch, {"10/25": {
        "abgelegt": False, "ablage_datum": None, "kurzbezeichnung": "I/J"
    }})

    ablage_abgleich.abgleichen(conn)

    row = conn.execute("SELECT portal_sync_pending FROM unfallakte WHERE az='10/25'").fetchone()
    assert row["portal_sync_pending"] == 0
