import os
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key-zugriff")
import sqlite3
import pytest
from backend.services import sv_zugriff_sync


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript("""
        CREATE TABLE unfallakte (
            az TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'offen',
            kurzbezeichnung TEXT,
            portal_aktiv INTEGER NOT NULL DEFAULT 0,
            portal_gesperrt INTEGER NOT NULL DEFAULT 0,
            portal_sync_pending INTEGER NOT NULL DEFAULT 0,
            ramicro_abgelegt INTEGER NOT NULL DEFAULT 0,
            ramicro_ablage_datum TEXT,
            status_vor_ablage TEXT
        );
        CREATE TABLE sv_portal_accounts (
            adressnr INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            vorname TEXT,
            email TEXT NOT NULL,
            portal_aktiv INTEGER NOT NULL DEFAULT 1
        );
    """)
    c.execute(
        "INSERT INTO sv_portal_accounts (adressnr, name, vorname, email) "
        "VALUES (25982, 'Ninnivaggi', 'KFZ-SV', 'info@gn-gutachter.de')"
    )
    return c


def _ra_micro(monkeypatch, az_liste):
    monkeypatch.setattr(
        sv_zugriff_sync, "hole_akten_fuer_sv",
        lambda adressnr: [{"az": az, "ra_bezeichnung": ""} for az in az_liste],
    )


def _kein_abgleich(monkeypatch):
    monkeypatch.setattr(
        sv_zugriff_sync, "abgleichen",
        lambda conn, az_liste=None, vorschau=False: {"angelegt": 0},
    )


def _sendung_auffangen(monkeypatch, speicher):
    def _senden(payload):
        speicher.append(payload)
        return {"user_id": "u1", "angelegt": len(payload["akten"]),
                "entzogen": 0, "unbekannt": []}
    monkeypatch.setattr(sv_zugriff_sync, "_sende_zugriffe", _senden)


def test_gesperrte_akten_werden_nicht_uebertragen(monkeypatch, conn):
    for az, gesperrt in [("1/25", 0), ("2/25", 1), ("3/25", 0)]:
        conn.execute(
            "INSERT INTO unfallakte (az, portal_gesperrt) VALUES (?, ?)", (az, gesperrt)
        )
    _ra_micro(monkeypatch, ["1/25", "2/25", "3/25"])
    _kein_abgleich(monkeypatch)
    gesendet = []
    _sendung_auffangen(monkeypatch, gesendet)

    bericht = sv_zugriff_sync.zugriffe_abgleichen(conn, 25982)

    assert sorted(gesendet[0]["akten"]) == ["1/25", "3/25"]
    assert bericht["gesperrt"] == 1
    assert bericht["uebertragen"] == 2


def test_portal_aktiv_folgt_der_sperre(monkeypatch, conn):
    conn.execute("INSERT INTO unfallakte (az, portal_gesperrt) VALUES ('1/25', 0)")
    conn.execute("INSERT INTO unfallakte (az, portal_gesperrt) VALUES ('2/25', 1)")
    _ra_micro(monkeypatch, ["1/25", "2/25"])
    _kein_abgleich(monkeypatch)
    _sendung_auffangen(monkeypatch, [])

    sv_zugriff_sync.zugriffe_abgleichen(conn, 25982)

    werte = {r["az"]: r["portal_aktiv"] for r in conn.execute(
        "SELECT az, portal_aktiv FROM unfallakte"
    )}
    assert werte == {"1/25": 1, "2/25": 0}


def test_sendung_enthaelt_die_stammdaten(monkeypatch, conn):
    conn.execute("INSERT INTO unfallakte (az) VALUES ('1/25')")
    _ra_micro(monkeypatch, ["1/25"])
    _kein_abgleich(monkeypatch)
    gesendet = []
    _sendung_auffangen(monkeypatch, gesendet)

    sv_zugriff_sync.zugriffe_abgleichen(conn, 25982)

    assert gesendet[0]["adressnr"] == 25982
    assert gesendet[0]["email"] == "info@gn-gutachter.de"
    assert gesendet[0]["name"] == "Ninnivaggi"


def test_unbekannter_sv_liefert_leeren_bericht(monkeypatch, conn):
    _ra_micro(monkeypatch, [])
    _kein_abgleich(monkeypatch)
    _sendung_auffangen(monkeypatch, [])

    bericht = sv_zugriff_sync.zugriffe_abgleichen(conn, 999)

    assert bericht["gesamt"] == 0
    assert bericht["gesendet"] is False


def test_ablage_abgleich_wird_vorher_aufgerufen(monkeypatch, conn):
    conn.execute("INSERT INTO unfallakte (az) VALUES ('1/25')")
    _ra_micro(monkeypatch, ["1/25"])
    aufrufe = []
    monkeypatch.setattr(
        sv_zugriff_sync, "abgleichen",
        lambda conn, az_liste=None, vorschau=False: aufrufe.append(list(az_liste or [])) or {"angelegt": 0},
    )
    _sendung_auffangen(monkeypatch, [])

    sv_zugriff_sync.zugriffe_abgleichen(conn, 25982)

    assert aufrufe == [["1/25"]]
