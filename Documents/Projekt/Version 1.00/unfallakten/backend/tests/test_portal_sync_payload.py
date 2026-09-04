import os
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key-payload")
import sqlite3
import pytest
from backend.services import portal_sync


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript("""
        CREATE TABLE unfallakte (
            az TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'offen',
            unfalldatum TEXT,
            haftungsquote INTEGER,
            sachbearbeiter TEXT,
            kurzbezeichnung TEXT,
            ramicro_abgelegt INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE portal_sync_queue (
            akte_id TEXT, sync_version INTEGER, status TEXT
        );
        CREATE TABLE beteiligte (
            id INTEGER PRIMARY KEY, akte_id TEXT, rolle TEXT, name TEXT,
            vorname TEXT, firma TEXT, email TEXT, gutachten_nr TEXT
        );
        CREATE TABLE schadenpositionen (
            akte_id TEXT, reparaturkosten REAL, wiederbeschaffung REAL,
            restwert REAL, wertminderung REAL, nutzungsausfall REAL,
            mietwagenkosten REAL, sv_kosten REAL, abschleppkosten REAL,
            standkosten REAL, anabmeldekosten REAL, schmerzensgeld REAL,
            sonstiges REAL
        );
        CREATE TABLE abrechnungsschreiben (
            id INTEGER PRIMARY KEY, akte_id TEXT, datum TEXT, versicherung TEXT
        );
        CREATE TABLE regulierung_positionen (
            abrechnungsschreiben_id INTEGER, position_key TEXT, betrag_reguliert REAL
        );
        CREATE TABLE dokumente (
            id INTEGER PRIMARY KEY, akte_id TEXT, dokumentenklasse TEXT,
            dateiname TEXT, hochgeladen_am TEXT, portal_sichtbar INTEGER DEFAULT 0
        );
    """)
    return c


def test_payload_enthaelt_kurzbezeichnung(conn):
    conn.execute(
        "INSERT INTO unfallakte (az, kurzbezeichnung) VALUES ('1/25', 'Türe/Taskoparan')"
    )
    payload = portal_sync._build_payload(conn, "1/25")
    assert payload["akte"]["kurzbezeichnung"] == "Türe/Taskoparan"


def test_abgelegte_akte_wird_als_abgeschlossen_gesendet(conn):
    conn.execute(
        "INSERT INTO unfallakte (az, status, ramicro_abgelegt) VALUES ('2/25', 'offen', 1)"
    )
    payload = portal_sync._build_payload(conn, "2/25")
    assert payload["akte"]["status"] == "abgeschlossen"


def test_laufende_akte_behaelt_ihren_status(conn):
    conn.execute(
        "INSERT INTO unfallakte (az, status, ramicro_abgelegt) VALUES ('3/25', 'klage', 0)"
    )
    payload = portal_sync._build_payload(conn, "3/25")
    assert payload["akte"]["status"] == "klage"


def test_payload_baut_ohne_fehler_bei_leerer_akte(conn):
    conn.execute("INSERT INTO unfallakte (az) VALUES ('4/25')")
    payload = portal_sync._build_payload(conn, "4/25")
    assert payload["akte"]["az"] == "4/25"
    assert payload["beteiligte"] == []
    assert payload["dokumente"] == []


def test_abgelegte_klageakte_behaelt_klage_kennzeichnung(conn):
    conn.execute(
        "INSERT INTO unfallakte (az, status, ramicro_abgelegt) VALUES ('5/25', 'klage', 1)"
    )
    conn.execute("""
        INSERT INTO schadenpositionen
            (akte_id, reparaturkosten, wiederbeschaffung, restwert, wertminderung,
             nutzungsausfall, mietwagenkosten, sv_kosten, abschleppkosten,
             standkosten, anabmeldekosten, schmerzensgeld, sonstiges)
        VALUES ('5/25', 1000, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    """)
    cur = conn.execute(
        "INSERT INTO abrechnungsschreiben (akte_id, datum, versicherung) "
        "VALUES ('5/25', '2026-01-01', 'Test-Versicherung')"
    )
    conn.execute(
        "INSERT INTO regulierung_positionen (abrechnungsschreiben_id, position_key, betrag_reguliert) "
        "VALUES (?, 'reparaturkosten', 1000)",
        (cur.lastrowid,),
    )
    ampel = portal_sync._berechne_ampel(conn, "5/25")
    assert ampel["status"] == "klage_eingereicht"
    assert ampel["farbe"] == "rot"


def test_payload_liefert_klasse_und_label_statt_typ(conn):
    conn.execute("INSERT INTO unfallakte (az) VALUES ('31/21')")
    conn.execute(
        "INSERT INTO dokumente (id, akte_id, dokumentenklasse, dateiname, "
        " hochgeladen_am, portal_sichtbar) "
        "VALUES (1, '31/21', 'sv_rechnung', 'r.pdf', '2026-08-01', 1)")
    dok = portal_sync._build_payload(conn, "31/21")["dokumente"][0]
    assert dok["klasse"] == "sv_rechnung"
    assert dok["klasse_label"] == "SV-/Gutachterrechnung"
    assert "typ" not in dok
