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


@pytest.fixture
def conn_beteiligte_ohne_pk():
    """
    Bildet den tatsaechlich vorgefundenen Live-Zustand nach: beteiligte.id
    ist ein reines INT ohne PRIMARY KEY/AUTOINCREMENT.
    """
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
            id INT,
            akte_id TEXT,
            rolle TEXT,
            name TEXT
        );
        CREATE INDEX idx_beteiligte_akte_id ON beteiligte(akte_id);
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
    conn.execute("INSERT INTO unfallakte (az) VALUES ('4/26')")
    conn.execute(
        "INSERT INTO abrechnungsschreiben (akte_id, datum, versicherung) "
        "VALUES ('4/26', '2026-02-01', 'Allianz')"
    )
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
    zeilen = conn.execute(
        "SELECT akte_id, versicherung FROM v_regulierungsstatus"
    ).fetchall()
    assert len(zeilen) == 1
    assert zeilen[0]["akte_id"] == "4/26"
    assert zeilen[0]["versicherung"] == "Allianz"


def test_fk_reparatur_liegengebliebene_neu69_wird_bereinigt(conn):
    conn.execute("INSERT INTO unfallakte (az) VALUES ('5/26')")
    conn.execute(
        "INSERT INTO abrechnungsschreiben (akte_id, datum, versicherung) "
        "VALUES ('5/26', '2026-03-01', 'HUK')"
    )
    conn.execute("CREATE TABLE abrechnungsschreiben_neu69 (rest_eines_abbruchs INTEGER)")
    _run_migration_69(conn)
    ziele = {r["table"] for r in conn.execute(
        'PRAGMA foreign_key_list("abrechnungsschreiben")'
    ).fetchall()}
    assert "dokumente" in ziele
    row = conn.execute(
        "SELECT versicherung FROM abrechnungsschreiben WHERE akte_id = '5/26'"
    ).fetchone()
    assert row["versicherung"] == "HUK"


def test_unfalldetails_fehlt_migration_bricht_nicht_ab(conn):
    conn.execute("DROP TABLE unfalldetails")
    _run_migration_69(conn)
    row = conn.execute(
        "SELECT beschreibung FROM schema_version WHERE version = 69"
    ).fetchone()
    assert row is not None


def test_beteiligte_id_reparatur_bestand_bleibt_erhalten(conn_beteiligte_ohne_pk):
    c = conn_beteiligte_ohne_pk
    c.execute("INSERT INTO unfallakte (az) VALUES ('1/26')")
    c.execute(
        "INSERT INTO beteiligte (id, akte_id, rolle, name) "
        "VALUES (1, '1/26', 'mandant', 'Mueller')"
    )
    c.execute(
        "INSERT INTO beteiligte (id, akte_id, rolle, name) "
        "VALUES (5, '1/26', 'gegner', 'Bauer')"
    )
    c.execute(
        "INSERT INTO beteiligte (id, akte_id, rolle, name) "
        "VALUES (NULL, '1/26', 'gericht', 'Amtsgericht X')"
    )
    c.execute(
        "INSERT INTO beteiligte (id, akte_id, rolle, name) "
        "VALUES (NULL, '1/26', 'gericht', 'Amtsgericht Y')"
    )
    _run_migration_69(c)
    alle = c.execute("SELECT id, name FROM beteiligte").fetchall()
    assert len(alle) == 4
    nach_name = {r["name"]: r["id"] for r in alle}
    assert nach_name["Mueller"] == 1
    assert nach_name["Bauer"] == 5
    assert nach_name["Amtsgericht X"] is not None
    assert nach_name["Amtsgericht Y"] is not None
    assert nach_name["Amtsgericht X"] != nach_name["Amtsgericht Y"]
    assert len({r["id"] for r in alle}) == 4


def test_beteiligte_id_reparatur_neue_zeile_bekommt_nummer(conn_beteiligte_ohne_pk):
    c = conn_beteiligte_ohne_pk
    c.execute("INSERT INTO unfallakte (az) VALUES ('1/26')")
    c.execute(
        "INSERT INTO beteiligte (id, akte_id, rolle, name) "
        "VALUES (3, '1/26', 'mandant', 'Mueller')"
    )
    _run_migration_69(c)
    c.execute(
        "INSERT INTO beteiligte (akte_id, rolle, name) VALUES ('1/26', 'zeuge', 'Neu')"
    )
    row = c.execute("SELECT id FROM beteiligte WHERE name = 'Neu'").fetchone()
    assert row["id"] is not None
    assert row["id"] > 3


def test_beteiligte_id_reparatur_liegengebliebene_neu69_wird_bereinigt(
    conn_beteiligte_ohne_pk
):
    c = conn_beteiligte_ohne_pk
    c.execute("INSERT INTO unfallakte (az) VALUES ('1/26')")
    c.execute(
        "INSERT INTO beteiligte (id, akte_id, rolle, name) "
        "VALUES (NULL, '1/26', 'mandant', 'Mueller')"
    )
    c.execute("CREATE TABLE beteiligte_neu69 (rest_eines_abbruchs INTEGER)")
    _run_migration_69(c)
    row = c.execute("SELECT id FROM beteiligte WHERE name = 'Mueller'").fetchone()
    assert row["id"] is not None


def test_portal_einladungen_beschreibbar_nach_beteiligte_reparatur(
    conn_beteiligte_ohne_pk
):
    c = conn_beteiligte_ohne_pk
    c.execute("INSERT INTO unfallakte (az) VALUES ('1/26')")
    c.execute(
        "INSERT INTO beteiligte (id, akte_id, rolle, name) "
        "VALUES (NULL, '1/26', 'sachverstaendiger', 'Dekra')"
    )
    _run_migration_69(c)
    c.execute("PRAGMA foreign_keys=ON")
    beteiligter_id = c.execute(
        "SELECT id FROM beteiligte WHERE name = 'Dekra'"
    ).fetchone()["id"]
    c.execute(
        "INSERT INTO portal_einladungen (akte_id, beteiligter_id, email, rolle) "
        "VALUES ('1/26', ?, 'sv@example.de', 'sachverstaendiger')",
        (beteiligter_id,),
    )
    row = c.execute("SELECT COUNT(*) AS n FROM portal_einladungen").fetchone()
    assert row["n"] == 1


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
