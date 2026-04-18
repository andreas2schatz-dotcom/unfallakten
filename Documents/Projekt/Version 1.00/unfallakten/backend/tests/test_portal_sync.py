import sqlite3
import pytest
from unittest.mock import patch
from backend.services.portal_sync import (
    _berechne_ampel, _portal_flag, queue_sync, _build_payload, process_queue, _send_to_portal
)


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE unfallakte (
            az TEXT PRIMARY KEY, status TEXT DEFAULT 'offen',
            portal_aktiv INTEGER DEFAULT 0, portal_sync_pending INTEGER DEFAULT 0,
            portal_last_sync TEXT, unfalldatum TEXT DEFAULT '',
            haftungsquote REAL DEFAULT 100.0, sachbearbeiter TEXT, erstellt_am TEXT
        );
        CREATE TABLE beteiligte (
            id INTEGER PRIMARY KEY, akte_id TEXT, rolle TEXT, name TEXT,
            vorname TEXT, firma TEXT, email TEXT, telefon TEXT
        );
        CREATE TABLE abrechnungsschreiben (
            id INTEGER PRIMARY KEY, akte_id TEXT, datum TEXT, versicherung TEXT
        );
        CREATE TABLE regulierung_positionen (
            id INTEGER PRIMARY KEY, abrechnungsschreiben_id INTEGER,
            position_key TEXT, betrag_reguliert REAL
        );
        CREATE TABLE schadenpositionen (
            id INTEGER PRIMARY KEY, akte_id TEXT,
            reparaturkosten REAL DEFAULT 0, wiederbeschaffung REAL DEFAULT 0,
            restwert REAL DEFAULT 0, wertminderung REAL DEFAULT 0,
            nutzungsausfall REAL DEFAULT 0, mietwagenkosten REAL DEFAULT 0,
            sv_kosten REAL DEFAULT 0, abschleppkosten REAL DEFAULT 0,
            standkosten REAL DEFAULT 0, anabmeldekosten REAL DEFAULT 0,
            schmerzensgeld REAL DEFAULT 0, sonstiges REAL DEFAULT 0
        );
        CREATE TABLE dokumente (
            id INTEGER PRIMARY KEY, akte_id TEXT, typ TEXT, dateiname TEXT,
            hochgeladen_am TEXT, portal_sichtbar INTEGER DEFAULT 0
        );
        CREATE TABLE portal_sync_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT, akte_id TEXT, sync_version INTEGER,
            status TEXT DEFAULT 'pending', created_at TEXT, sent_at TEXT,
            retry_count INTEGER DEFAULT 0, last_error TEXT
        );
        INSERT INTO unfallakte (az, status, portal_aktiv) VALUES ('TEST/001', 'offen', 1);
    """)
    return conn


def test_ampel_akte_eroeffnet(db):
    r = _berechne_ampel(db, "TEST/001")
    assert r["status"] == "akte_eroeffnet"
    assert r["farbe"] == "grau"


def test_ampel_klage(db):
    db.execute("UPDATE unfallakte SET status = 'klage' WHERE az = 'TEST/001'")
    r = _berechne_ampel(db, "TEST/001")
    assert r["status"] == "klage_eingereicht"
    assert r["farbe"] == "rot"


def test_ampel_teilreguliert(db):
    db.execute("INSERT INTO schadenpositionen (akte_id, reparaturkosten) VALUES ('TEST/001', 5000)")
    ab_id = db.execute(
        "INSERT INTO abrechnungsschreiben (akte_id, datum) VALUES ('TEST/001', '2026-01-01')"
    ).lastrowid
    db.execute(
        "INSERT INTO regulierung_positionen (abrechnungsschreiben_id, position_key, betrag_reguliert)"
        " VALUES (?, 'reparaturkosten', 3000)", (ab_id,)
    )
    r = _berechne_ampel(db, "TEST/001")
    assert r["status"] == "teilreguliert"
    assert r["farbe"] == "orange"


def test_ampel_vollreguliert(db):
    db.execute("UPDATE unfallakte SET status = 'abgeschlossen' WHERE az = 'TEST/001'")
    db.execute("INSERT INTO schadenpositionen (akte_id, reparaturkosten) VALUES ('TEST/001', 5000)")
    ab_id = db.execute(
        "INSERT INTO abrechnungsschreiben (akte_id, datum) VALUES ('TEST/001', '2026-01-01')"
    ).lastrowid
    db.execute(
        "INSERT INTO regulierung_positionen (abrechnungsschreiben_id, position_key, betrag_reguliert)"
        " VALUES (?, 'reparaturkosten', 5000)", (ab_id,)
    )
    r = _berechne_ampel(db, "TEST/001")
    assert r["status"] == "vollreguliert"
    assert r["farbe"] == "gruen"


def test_ampel_regulierung_laeuft(db):
    db.execute("INSERT INTO abrechnungsschreiben (akte_id, datum) VALUES ('TEST/001', '2026-01-01')")
    r = _berechne_ampel(db, "TEST/001")
    assert r["status"] == "regulierung_laeuft"
    assert r["farbe"] == "gelb"


def test_portal_flag_setzt_pending(db):
    _portal_flag(db, "TEST/001")
    row = db.execute("SELECT portal_sync_pending FROM unfallakte WHERE az = 'TEST/001'").fetchone()
    assert row["portal_sync_pending"] == 1


def test_portal_flag_ignoriert_inaktive_akte(db):
    db.execute("UPDATE unfallakte SET portal_aktiv = 0 WHERE az = 'TEST/001'")
    _portal_flag(db, "TEST/001")
    row = db.execute("SELECT portal_sync_pending FROM unfallakte WHERE az = 'TEST/001'").fetchone()
    assert row["portal_sync_pending"] == 0


def test_build_payload_struktur(db):
    db.execute("INSERT INTO schadenpositionen (akte_id, reparaturkosten) VALUES ('TEST/001', 1000)")
    payload = _build_payload(db, "TEST/001")
    assert payload["akte"]["az"] == "TEST/001"
    assert "ampel" in payload
    assert "beteiligte" in payload
    assert "schaden" in payload
    assert payload["sync_version"] == 1


def test_process_queue_mit_mock(db):
    db.execute("UPDATE unfallakte SET portal_sync_pending = 1 WHERE az = 'TEST/001'")
    with patch("backend.services.portal_sync._send_to_portal", return_value=True):
        n = process_queue(db)
    assert n == 1
    row = db.execute("SELECT portal_sync_pending FROM unfallakte WHERE az = 'TEST/001'").fetchone()
    assert row["portal_sync_pending"] == 0


def test_process_queue_failed_send(db):
    db.execute("UPDATE unfallakte SET portal_sync_pending = 1 WHERE az = 'TEST/001'")
    with patch("backend.services.portal_sync._send_to_portal", return_value=False):
        n = process_queue(db)
    assert n == 0
    row = db.execute("SELECT portal_sync_pending FROM unfallakte WHERE az = 'TEST/001'").fetchone()
    assert row["portal_sync_pending"] == 1
    queue_row = db.execute(
        "SELECT status, retry_count FROM portal_sync_queue WHERE akte_id = 'TEST/001'"
    ).fetchone()
    assert queue_row["status"] == "failed"
    assert queue_row["retry_count"] == 1


def test_build_payload_leer_fuer_unbekannte_akte(db):
    payload = _build_payload(db, "UNBEKANNT/999")
    assert payload == {}


def test_ampel_gutachten_beauftragt(db):
    db.execute("INSERT INTO beteiligte (akte_id, rolle, name) VALUES ('TEST/001', 'sachverstaendiger', 'Müller')")
    r = _berechne_ampel(db, "TEST/001")
    assert r["status"] == "gutachten_beauftragt"
    assert r["farbe"] == "grau"
