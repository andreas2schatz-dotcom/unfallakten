# SV-Portal für Sachverständige — Umsetzungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Der Sachverständige Ninnivaggi sieht im Portal standardmäßig seine 111 laufenden Akten; die 467 abgeschlossenen liegen hinter dem Chip „Abgeschlossen".

**Architecture:** RA-MICRO bleibt alleinige Quelle für Ablage-Status und SV-Zuordnung. Ein nächtlicher Abgleich spiegelt den Ablage-Status nach SQLite (beidseitig, mit Wiederherstellung des vorherigen Aktenstatus bei Reaktivierung). Ein davon getrennter Zugriffs-Abgleich meldet dem Portal, welcher Zugang welche Akten sehen darf. Freigabe wird zur Ausnahme-Sperre.

**Tech Stack:** Python 3 / Flask / SQLite (Kanzlei-System), pymssql gegen RA-MICRO SQL Server (read-only), Next.js 15 / TypeScript / better-sqlite3 (Portal), pytest + vitest.

**Spec:** `docs/superpowers/specs/2026-08-20-sv-portal-laufende-akten-design.md`

## Global Constraints

- **RA-MICRO ist read-only.** Niemals schreibend zugreifen. Nur `SELECT`.
- **Zielsprache Deutsch** in allen Bezeichnern, Meldungen und der Oberfläche.
- **Keine Kommentare im Code** außer bei nicht-offensichtlichem Verhalten.
- **Keine unnötigen Abstraktionen.** Nur umsetzen, was hier steht.
- **Migrationen:** kein `executescript()`; `conn.commit()` vor und nach jedem DDL; die Migration in **einem** Schreibvorgang in die Datei schreiben (Flask-Reloader stempelt sonst einen Zwischenstand). Nach der Migration Spalten und `schema_version` in der Live-Datenbank nachprüfen.
- **Zwei Registrierungsstellen je Migration:** ein Eintrag in `_MIGRATIONS` (Datei `backend/db/schema_manager.py`, ~Zeile 325) **und** ein `elif version == N:`-Zweig (~Zeile 1845). Fehlt der `elif`-Zweig, führt der `else`-Zweig den Kommentar-Platzhalter aus, stempelt die Version — und die Migration passiert nie. Genau so sind die Befunde D-1, D-2 und D-7 entstanden.
- **Tests im Container ausführen** (dort liegen alle Abhängigkeiten):
  `docker exec -w /app unfallakten-backend-dev python -m pytest backend/tests/<datei> -v`
  Aus Git Bash unter Windows `MSYS_NO_PATHCONV=1` voranstellen, sonst verbiegt die Shell den Pfad.
- **Tests dürfen RA-MICRO nicht wirklich befragen.** Verbindungen mocken (`monkeypatch` auf `get_ramicro_connection`).
- **Portal-Tests:** `cd "C:/Users/HAL9000/Documents/Projekt/Version 1.00/stakeholder-portal" && npm test`
- **Häufig committen**, je Task mindestens einmal.

## Reihenfolge und Abhängigkeiten

Task 1 ist Voraussetzung für alles Weitere. Task 7 (Portal-Endpunkt) muss vor Task 6 (Kanzlei-Gegenstelle) fertig sein, damit Task 6 gegen etwas Echtes prüfen kann. Task 10 setzt alle vorherigen voraus.

Beim Betrieb gilt: **Erst Aktensync, dann Zugriffs-Abgleich.** Im Portal verweist `akte_zugriff.az` per Fremdschlüssel auf `akten(az)` und `foreign_keys` steht auf `ON` (`src/lib/db.ts:18`) — ein Zugriff auf eine noch nicht übertragene Akte scheitert. Task 6 stellt diese Reihenfolge her.

---

## Task 1: Migration 69 — Schema-Reparatur und neue Spalten

Die Live-Datenbank weicht vom Soll ab: Drei Tabellen und vier Spalten fehlen, obwohl die zugehörigen Migrationen als ausgeführt gestempelt sind. Zusätzlich verweisen zwei Tabellen auf eine Tabelle `dokumente_alt`, die es nicht mehr gibt.

**Files:**
- Modify: `backend/db/schema_manager.py` (neue Funktion `_run_migration_69`, Eintrag in `_MIGRATIONS` ~Zeile 325, `elif`-Zweig ~Zeile 1845)
- Test: `backend/tests/test_migration_69.py` (neu)

**Interfaces:**
- Consumes: nichts
- Produces: `_run_migration_69(conn: sqlite3.Connection) -> None`. Danach existieren in `unfallakte` die Spalten `ramicro_abgelegt` (INTEGER NOT NULL DEFAULT 0), `ramicro_ablage_datum` (TEXT), `status_vor_ablage` (TEXT), `portal_gesperrt` (INTEGER NOT NULL DEFAULT 0), `regulierung_status` (TEXT NOT NULL DEFAULT 'offen'); in `beteiligte` die Spalte `gutachten_nr` (TEXT); in `dokumente` die Spalte `portal_sichtbar` (INTEGER NOT NULL DEFAULT 0); in `unfalldetails` die Spalte `erstellt_am` (TEXT); die Tabellen `portal_sync_queue`, `portal_einladungen`, `fragebogen_erstkontakt`.

- [ ] **Step 1: Testdatei anlegen mit den fehlschlagenden Tests**

Datei `backend/tests/test_migration_69.py`:

```python
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
```

- [ ] **Step 2: Tests laufen lassen — sie müssen fehlschlagen**

Run: `docker exec -w /app unfallakten-backend-dev python -m pytest backend/tests/test_migration_69.py -v`
Expected: FAIL mit `ImportError: cannot import name '_run_migration_69'`

- [ ] **Step 3: Migration schreiben**

In `backend/db/schema_manager.py`, direkt nach `_run_migration_68`, in **einem** Schreibvorgang einfügen:

```python
def _run_migration_69(conn: sqlite3.Connection) -> None:
    """
    Migration 69 - SV-Portal: Ablage-Status und Ausnahme-Sperre.

    Holt zugleich nach, was die als ausgefuehrt gestempelten Migrationen
    38, 39, 45 und 46 in Bestands-Datenbanken nie angelegt haben, und
    repariert den Fremdschluessel auf die entfallene Tabelle dokumente_alt.
    Kein executescript, explizite Commits um DDL (Reloader-Falle).
    """
    conn.commit()

    neue_spalten = [
        ("unfallakte",    "ramicro_abgelegt",     "INTEGER NOT NULL DEFAULT 0"),
        ("unfallakte",    "ramicro_ablage_datum", "TEXT"),
        ("unfallakte",    "status_vor_ablage",    "TEXT"),
        ("unfallakte",    "portal_gesperrt",      "INTEGER NOT NULL DEFAULT 0"),
        ("unfallakte",    "regulierung_status",   "TEXT NOT NULL DEFAULT 'offen'"),
        ("beteiligte",    "gutachten_nr",         "TEXT"),
        ("dokumente",     "portal_sichtbar",      "INTEGER NOT NULL DEFAULT 0"),
        ("unfalldetails", "erstellt_am",          "TEXT"),
    ]
    for tabelle, spalte, typ in neue_spalten:
        vorhanden = {r[1] for r in conn.execute(
            "PRAGMA table_info({})".format(tabelle)
        ).fetchall()}
        if not vorhanden:
            continue
        if spalte not in vorhanden:
            conn.commit()
            conn.execute("ALTER TABLE {} ADD COLUMN {} {}".format(tabelle, spalte, typ))
            conn.commit()
            logger.info("Migration 69: %s.%s hinzugefuegt.", tabelle, spalte)

    # unfalldetails.erstellt_am traegt in der Frisch-DB datetime('now','localtime')
    # als Vorgabe. ALTER TABLE erlaubt keine nicht-konstante Vorgabe, deshalb
    # wird der Bestand hier einmalig gefuellt.
    conn.execute(
        "UPDATE unfalldetails SET erstellt_am = datetime('now','localtime') "
        "WHERE erstellt_am IS NULL"
    )
    conn.commit()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS portal_sync_queue (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            akte_id      TEXT    NOT NULL,
            sync_version INTEGER NOT NULL,
            status       TEXT    DEFAULT 'pending'
                         CHECK(status IN ('pending','sending','confirmed','failed')),
            created_at   TEXT    DEFAULT (datetime('now','localtime')),
            sent_at      TEXT,
            retry_count  INTEGER DEFAULT 0,
            last_error   TEXT
        )
    """)
    conn.commit()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS portal_einladungen (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            akte_id        TEXT    NOT NULL REFERENCES unfallakte(az) ON DELETE CASCADE,
            beteiligter_id INTEGER NOT NULL REFERENCES beteiligte(id) ON DELETE CASCADE,
            email          TEXT    NOT NULL,
            rolle          TEXT    NOT NULL
                           CHECK(rolle IN ('sachverstaendiger','privatmandant')),
            status         TEXT    DEFAULT 'ausstehend'
                           CHECK(status IN ('ausstehend','gesendet','angenommen')),
            eingeladen_am  TEXT    DEFAULT (datetime('now','localtime')),
            eingeladen_von INTEGER
        )
    """)
    conn.commit()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS fragebogen_erstkontakt (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            empfangen_am    TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            absender_email  TEXT,
            absender_name   TEXT,
            message_id      TEXT UNIQUE,
            json_roh        TEXT NOT NULL,
            mandant_name    TEXT,
            mandant_email   TEXT,
            kfz_kennzeichen TEXT,
            schadentag      TEXT,
            status          TEXT NOT NULL DEFAULT 'neu',
            akte_az         TEXT
        )
    """)
    conn.commit()

    _migration_69_fk_reparatur(conn)

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) VALUES (?, ?)",
        (69, "Migration 69 - SV-Portal Ablage/Sperre + Schema-Reparatur 38/39/45"),
    )
    conn.commit()
    logger.info("Migration 69 abgeschlossen.")


def _migration_69_fk_reparatur(conn: sqlite3.Connection) -> None:
    """
    Baut forderung_positionen und abrechnungsschreiben neu auf, wenn ihr
    dokument_id-Fremdschluessel noch auf die entfallene Tabelle dokumente_alt
    zeigt. Solange er das tut, scheitert jedes DELETE auf unfallakte bei
    eingeschalteter Fremdschluesselpruefung.
    """
    for tabelle in ("forderung_positionen", "abrechnungsschreiben"):
        vorhanden = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name = ?",
            (tabelle,),
        ).fetchone()
        if not vorhanden or "dokumente_alt" not in (vorhanden[0] or ""):
            continue

        neues_ddl = vorhanden[0].replace("dokumente_alt", "dokumente")
        neues_ddl = neues_ddl.replace(
            'CREATE TABLE "{}"'.format(tabelle), 'CREATE TABLE "{}_neu69"'.format(tabelle)
        ).replace(
            "CREATE TABLE {}".format(tabelle), "CREATE TABLE {}_neu69".format(tabelle)
        )
        spalten = [r[1] for r in conn.execute(
            "PRAGMA table_info({})".format(tabelle)
        ).fetchall()]
        spaltenliste = ", ".join('"{}"'.format(s) for s in spalten)

        conn.commit()
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute(neues_ddl)
        conn.execute(
            "INSERT INTO {t}_neu69 ({s}) SELECT {s} FROM {t}".format(
                t=tabelle, s=spaltenliste
            )
        )
        conn.execute("DROP TABLE {}".format(tabelle))
        conn.execute("ALTER TABLE {t}_neu69 RENAME TO {t}".format(t=tabelle))
        conn.execute("PRAGMA foreign_keys=ON")
        conn.commit()
        logger.info("Migration 69: Fremdschluessel von %s auf dokumente korrigiert.", tabelle)
```

- [ ] **Step 4: Migration registrieren — beide Stellen**

In `_MIGRATIONS` (nach dem Eintrag für 68, ~Zeile 325):

```python
    69: "-- migration_69_sv_portal_ablage",  # Handled by _run_migration_69
```

Im Dispatch (nach dem `elif` für 68, ~Zeile 1845):

```python
            elif version == 69:
                _run_migration_69(conn)
```

Ohne den `elif`-Zweig führt der `else`-Zweig nur den Kommentar aus und stempelt die Version — die Migration passiert dann nie.

- [ ] **Step 5: Tests laufen lassen — sie müssen bestehen**

Run: `docker exec -w /app unfallakten-backend-dev python -m pytest backend/tests/test_migration_69.py -v`
Expected: PASS, 9 Tests

- [ ] **Step 6: Live-Datenbank sichern und Migration anwenden**

```bash
docker exec unfallakten-backend-dev python -c "import sqlite3; s=sqlite3.connect('/app/data/unfallakten.db'); d=sqlite3.connect('/app/data/unfallakten.db.bak_vor_mig69'); s.backup(d); d.close(); s.close(); print('Backup erstellt.')"
docker restart unfallakten-backend-dev
```

- [ ] **Step 7: In der Live-Datenbank nachprüfen, dass die Migration wirklich gelaufen ist**

```bash
docker exec unfallakten-backend-dev python -c "
import sqlite3
c=sqlite3.connect('/app/data/unfallakten.db'); c.row_factory=sqlite3.Row
print(dict(c.execute('SELECT version, beschreibung FROM schema_version WHERE version=69').fetchone()))
print(sorted({r[1] for r in c.execute('PRAGMA table_info(unfallakte)')} & {'ramicro_abgelegt','portal_gesperrt','regulierung_status'}))
print('gutachten_nr:', 'gutachten_nr' in {r[1] for r in c.execute('PRAGMA table_info(beteiligte)')})
print('portal_sichtbar:', 'portal_sichtbar' in {r[1] for r in c.execute('PRAGMA table_info(dokumente)')})
print('Tabellen:', {r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")} >= {'portal_sync_queue','portal_einladungen','fragebogen_erstkontakt'})
print('FK:', [r['table'] for r in c.execute('PRAGMA foreign_key_list(abrechnungsschreiben)')])
"
```

Erwartet: Beschreibung endet auf „Schema-Reparatur 38/39/45", alle drei Spalten vorhanden, beide Spaltenprüfungen `True`, Tabellenprüfung `True`, im Fremdschlüssel steht `dokumente` statt `dokumente_alt`.

Steht die Beschreibung auf `Migration 69`, wurde der `elif`-Zweig vergessen: Zeile aus `schema_version` löschen, Zweig ergänzen, Backend neu starten.

- [ ] **Step 8: Commit**

```bash
git add backend/db/schema_manager.py backend/tests/test_migration_69.py
git commit -m "feat(db): Migration 69 - Ablage/Sperre-Spalten + Schema-Reparatur 38/39/45 + FK dokumente_alt"
```

---

## Task 2: Ablage-Status aus RA-MICRO lesen

**Files:**
- Create: `backend/ramicro/ablage_service.py`
- Test: `backend/tests/test_ablage_service.py`

**Interfaces:**
- Consumes: `get_ramicro_connection`, `RaMicroNichtAktiv`, `RaMicroVerbindungsFehler` aus `backend/ramicro/connector.py`
- Produces: `hole_ablage_status(az_liste: list[str]) -> dict[str, dict] | None`. Rückgabe je Aktenzeichen `{"abgelegt": bool, "ablage_datum": str | None, "kurzbezeichnung": str}`. Gibt `None` zurück, wenn RA-MICRO nicht erreichbar ist — ein leeres `dict` bedeutet dagegen „erreichbar, aber keine der Akten gefunden".

- [ ] **Step 1: Test schreiben**

Datei `backend/tests/test_ablage_service.py`:

```python
import os
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key-ablage")
import datetime
import pytest
from backend.ramicro import ablage_service
from backend.ramicro.connector import RaMicroNichtAktiv


class _Cursor:
    def __init__(self, zeilen):
        self._zeilen = zeilen
        self.sql = None
        self.params = None

    def execute(self, sql, params=None):
        self.sql = sql
        self.params = params

    def fetchall(self):
        return self._zeilen


class _Conn:
    def __init__(self, zeilen):
        self._cursor = _Cursor(zeilen)

    def cursor(self):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _mit_zeilen(monkeypatch, zeilen):
    conn = _Conn(zeilen)
    monkeypatch.setattr(ablage_service, "get_ramicro_connection", lambda: conn)
    return conn


def test_abgelegt_wird_an_der_ablagenummer_erkannt(monkeypatch):
    _mit_zeilen(monkeypatch, [{
        "az": "100/24", "iAblageNummer": 4711,
        "dtAblage": datetime.datetime(2025, 3, 4),
        "kurz": "Meier/Schulz",
    }])
    ergebnis = ablage_service.hole_ablage_status(["100/24"])
    assert ergebnis["100/24"]["abgelegt"] is True
    assert ergebnis["100/24"]["ablage_datum"] == "2025-03-04"
    assert ergebnis["100/24"]["kurzbezeichnung"] == "Meier/Schulz"


def test_nullwert_1899_gilt_nicht_als_ablage(monkeypatch):
    _mit_zeilen(monkeypatch, [{
        "az": "101/24", "iAblageNummer": 0,
        "dtAblage": datetime.datetime(1899, 12, 30),
        "kurz": "Nticha/Meyer",
    }])
    ergebnis = ablage_service.hole_ablage_status(["101/24"])
    assert ergebnis["101/24"]["abgelegt"] is False
    assert ergebnis["101/24"]["ablage_datum"] is None


def test_ablagenummer_null_gilt_nicht_als_ablage(monkeypatch):
    _mit_zeilen(monkeypatch, [{
        "az": "102/24", "iAblageNummer": None,
        "dtAblage": None, "kurz": "",
    }])
    ergebnis = ablage_service.hole_ablage_status(["102/24"])
    assert ergebnis["102/24"]["abgelegt"] is False


def test_ramicro_nicht_erreichbar_gibt_none(monkeypatch):
    def _kaputt():
        raise RaMicroNichtAktiv("kein RA-MICRO")
    monkeypatch.setattr(ablage_service, "get_ramicro_connection", _kaputt)
    assert ablage_service.hole_ablage_status(["100/24"]) is None


def test_leere_eingabe_fragt_ra_micro_nicht(monkeypatch):
    def _darf_nicht_aufgerufen_werden():
        raise AssertionError("RA-MICRO wurde trotz leerer Liste befragt")
    monkeypatch.setattr(
        ablage_service, "get_ramicro_connection", _darf_nicht_aufgerufen_werden
    )
    assert ablage_service.hole_ablage_status([]) == {}


def test_fragt_in_bloecken_an(monkeypatch):
    zeilen = [{"az": f"{i}/24", "iAblageNummer": 0, "dtAblage": None, "kurz": ""}
              for i in range(1, 5)]
    conn = _mit_zeilen(monkeypatch, zeilen)
    ablage_service.hole_ablage_status([f"{i}/24" for i in range(1, 5)])
    assert conn.cursor().params is not None
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `docker exec -w /app unfallakten-backend-dev python -m pytest backend/tests/test_ablage_service.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'backend.ramicro.ablage_service'`

- [ ] **Step 3: Dienst schreiben**

Datei `backend/ramicro/ablage_service.py`:

```python
"""
Ablage-Status aus RA-MICRO (read-only).

RA-MICRO traegt in dtAblage fuer nicht abgelegte Akten den Nullwert
1899-12-30 ein. Massgeblich ist deshalb allein iAblageNummer.
"""
import logging

from .connector import (
    get_ramicro_connection,
    RaMicroNichtAktiv,
    RaMicroVerbindungsFehler,
)

logger = logging.getLogger(__name__)

BLOCKGROESSE = 500


def _datum(wert):
    if wert is None:
        return None
    if getattr(wert, "year", 0) < 1900:
        return None
    return wert.strftime("%Y-%m-%d")


def hole_ablage_status(az_liste):
    # type: (list) -> dict | None
    """
    Liefert je Aktenzeichen {'abgelegt', 'ablage_datum', 'kurzbezeichnung'}.
    None bedeutet: RA-MICRO nicht erreichbar. {} bedeutet: nichts gefunden.
    """
    if not az_liste:
        return {}

    ergebnis = {}
    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            for start in range(0, len(az_liste), BLOCKGROESSE):
                block = az_liste[start:start + BLOCKGROESSE]
                platzhalter = ",".join(["%s"] * len(block))
                cur.execute(
                    "SELECT sAktenNummer AS az, iAblageNummer, dtAblage, "
                    "sAktenKurzBezeichnung AS kurz "
                    "FROM tblAkten WHERE sAktenNummer IN ({})".format(platzhalter),
                    tuple(block),
                )
                for zeile in cur.fetchall():
                    abgelegt = (zeile["iAblageNummer"] or 0) > 0
                    ergebnis[zeile["az"]] = {
                        "abgelegt": abgelegt,
                        "ablage_datum": _datum(zeile["dtAblage"]) if abgelegt else None,
                        "kurzbezeichnung": (zeile["kurz"] or "").strip(),
                    }
    except (RaMicroNichtAktiv, RaMicroVerbindungsFehler) as exc:
        logger.warning("Ablage-Abgleich: RA-MICRO nicht erreichbar (%s).", exc)
        return None
    except Exception as exc:
        logger.warning("Ablage-Abgleich: Abfrage fehlgeschlagen (%s).", exc)
        return None

    return ergebnis
```

- [ ] **Step 4: Test laufen lassen — muss bestehen**

Run: `docker exec -w /app unfallakten-backend-dev python -m pytest backend/tests/test_ablage_service.py -v`
Expected: PASS, 6 Tests

- [ ] **Step 5: Commit**

```bash
git add backend/ramicro/ablage_service.py backend/tests/test_ablage_service.py
git commit -m "feat(ramicro): Ablage-Status lesen (iAblageNummer, 1899-Nullwert beachtet)"
```

---

## Task 3: Abgleichlauf mit Vorschau

**Files:**
- Create: `backend/services/ablage_abgleich.py`
- Modify: `backend/app.py` (CLI-Befehl, neben `sync_portal_cmd` ~Zeile 302)
- Test: `backend/tests/test_ablage_abgleich.py`

**Interfaces:**
- Consumes: `hole_ablage_status(az_liste)` aus Task 2; `queue_sync(conn, akte_id)` aus `backend/services/portal_sync.py`
- Produces: `abgleichen(conn, az_liste=None, vorschau=False) -> dict` mit den Schlüsseln `geprueft`, `abgelegt_neu`, `reaktiviert`, `angelegt`, `bezeichnung_aktualisiert`, `beispiele` (dict der ersten fünf Aktenzeichen je Übergang) und `ramicro_erreichbar` (bool).

- [ ] **Step 1: Test schreiben**

Datei `backend/tests/test_ablage_abgleich.py`:

```python
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
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `docker exec -w /app unfallakten-backend-dev python -m pytest backend/tests/test_ablage_abgleich.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'backend.services.ablage_abgleich'`

- [ ] **Step 3: Dienst schreiben**

Datei `backend/services/ablage_abgleich.py`:

```python
"""
Gleicht den Ablage-Status aus RA-MICRO nach SQLite ab.

Beidseitig: Wird eine Akte in RA-MICRO reaktiviert, kehrt sie auch bei uns
zurueck. Der Aktenstatus, den der Abgleich beim Ablegen ueberschrieben hat,
steht in status_vor_ablage und wird dabei wiederhergestellt. Ein selbst
gesetzter Abschluss hat kein status_vor_ablage und bleibt unangetastet.
"""
import logging

from ..ramicro.ablage_service import hole_ablage_status
from .portal_sync import queue_sync

logger = logging.getLogger(__name__)

MAX_BEISPIELE = 5


def _leerer_bericht():
    return {
        "geprueft": 0,
        "abgelegt_neu": 0,
        "reaktiviert": 0,
        "angelegt": 0,
        "bezeichnung_aktualisiert": 0,
        "beispiele": {"abgelegt_neu": [], "reaktiviert": [], "angelegt": []},
        "ramicro_erreichbar": True,
    }


def _merke(bericht, schluessel, az):
    bericht[schluessel] += 1
    if len(bericht["beispiele"][schluessel]) < MAX_BEISPIELE:
        bericht["beispiele"][schluessel].append(az)


def abgleichen(conn, az_liste=None, vorschau=False):
    # type: (object, list, bool) -> dict
    """
    Ohne az_liste: alle Akten in unfallakte.
    Mit az_liste: genau diese Aktenzeichen; fehlende Zeilen werden angelegt.
    """
    bericht = _leerer_bericht()

    if az_liste is None:
        az_liste = [r["az"] for r in conn.execute("SELECT az FROM unfallakte")]
        anlegen = False
    else:
        az_liste = list(az_liste)
        anlegen = True

    if not az_liste:
        return bericht

    status = hole_ablage_status(az_liste)
    if status is None:
        bericht["ramicro_erreichbar"] = False
        return bericht

    bestand = {
        r["az"]: r for r in conn.execute(
            "SELECT az, status, kurzbezeichnung, ramicro_abgelegt, status_vor_ablage "
            "FROM unfallakte"
        )
    }

    for az in az_liste:
        daten = status.get(az)
        if daten is None:
            continue
        bericht["geprueft"] += 1

        zeile = bestand.get(az)
        if zeile is None:
            if not anlegen:
                continue
            _merke(bericht, "angelegt", az)
            if not vorschau:
                conn.execute("INSERT OR IGNORE INTO unfallakte (az) VALUES (?)", (az,))
            zeile = {
                "status": "offen", "kurzbezeichnung": None,
                "ramicro_abgelegt": 0, "status_vor_ablage": None,
            }

        war_abgelegt = bool(zeile["ramicro_abgelegt"])
        ist_abgelegt = daten["abgelegt"]

        if ist_abgelegt and not war_abgelegt:
            _merke(bericht, "abgelegt_neu", az)
            if not vorschau:
                if zeile["status"] != "abgeschlossen":
                    conn.execute(
                        "UPDATE unfallakte SET status_vor_ablage = ?, status = 'abgeschlossen' "
                        "WHERE az = ?",
                        (zeile["status"], az),
                    )
                conn.execute(
                    "UPDATE unfallakte SET ramicro_abgelegt = 1, ramicro_ablage_datum = ? "
                    "WHERE az = ?",
                    (daten["ablage_datum"], az),
                )
                queue_sync(conn, az)

        elif war_abgelegt and not ist_abgelegt:
            _merke(bericht, "reaktiviert", az)
            if not vorschau:
                if zeile["status_vor_ablage"]:
                    conn.execute(
                        "UPDATE unfallakte SET status = ?, status_vor_ablage = NULL "
                        "WHERE az = ?",
                        (zeile["status_vor_ablage"], az),
                    )
                conn.execute(
                    "UPDATE unfallakte SET ramicro_abgelegt = 0, ramicro_ablage_datum = NULL "
                    "WHERE az = ?",
                    (az,),
                )
                queue_sync(conn, az)

        neue_bezeichnung = daten["kurzbezeichnung"]
        if neue_bezeichnung and neue_bezeichnung != (zeile["kurzbezeichnung"] or ""):
            bericht["bezeichnung_aktualisiert"] += 1
            if not vorschau:
                conn.execute(
                    "UPDATE unfallakte SET kurzbezeichnung = ? WHERE az = ?",
                    (neue_bezeichnung, az),
                )

    if not vorschau:
        conn.commit()

    logger.info(
        "Ablage-Abgleich%s: %d geprueft, %d neu abgelegt, %d reaktiviert, %d angelegt.",
        " (Vorschau)" if vorschau else "",
        bericht["geprueft"], bericht["abgelegt_neu"],
        bericht["reaktiviert"], bericht["angelegt"],
    )
    return bericht
```

- [ ] **Step 4: Test laufen lassen — muss bestehen**

Run: `docker exec -w /app unfallakten-backend-dev python -m pytest backend/tests/test_ablage_abgleich.py -v`
Expected: PASS, 10 Tests

- [ ] **Step 5: CLI-Befehl ergänzen**

In `backend/app.py`, direkt nach `sync_portal_cmd` (~Zeile 310):

```python
    @app.cli.command("ablage-abgleich")
    @click.option("--vorschau", is_flag=True, help="Nur berichten, nichts schreiben.")
    def ablage_abgleich_cmd(vorschau):
        """Gleicht den Ablage-Status aus RA-MICRO ab."""
        from .db.database import get_connection
        from .services.ablage_abgleich import abgleichen
        with get_connection() as conn:
            bericht = abgleichen(conn, vorschau=vorschau)
        if not bericht["ramicro_erreichbar"]:
            print("RA-MICRO nicht erreichbar - nichts geaendert.")
            return
        print("{}{} Akten geprueft".format(
            "VORSCHAU: " if vorschau else "", bericht["geprueft"]))
        print("  neu abgelegt:  {} {}".format(
            bericht["abgelegt_neu"], bericht["beispiele"]["abgelegt_neu"]))
        print("  reaktiviert:   {} {}".format(
            bericht["reaktiviert"], bericht["beispiele"]["reaktiviert"]))
        print("  neu angelegt:  {}".format(bericht["angelegt"]))
        print("  Bezeichnungen: {}".format(bericht["bezeichnung_aktualisiert"]))
```

Prüfen, ob `import click` in `backend/app.py` bereits vorhanden ist; falls nicht, oben ergänzen.

- [ ] **Step 6: Vorschaulauf gegen die Live-Datenbank**

```bash
docker exec -w /app -e FLASK_APP="backend.app:erstelle_app()" unfallakten-backend-dev flask ablage-abgleich --vorschau
```

Erwartet: rund 330 geprüfte Akten, davon etwa 40 „neu abgelegt". Am 2026-08-20 gegen RA-MICRO nachgerechnet: von 332 Akten im System sind 40 abgelegt, 286 laufend, 6 in RA-MICRO nicht auffindbar (abweichende Aktenzeichen aus dem E-Mail-Import). **Nicht schreiben** — der schreibende Lauf ist Teil von Task 10, nach Rücksprache mit RA Schatz.

- [ ] **Step 7: Commit**

```bash
git add backend/services/ablage_abgleich.py backend/tests/test_ablage_abgleich.py backend/app.py
git commit -m "feat(portal): Ablage-Abgleich mit Vorschau und Wiederherstellung bei Reaktivierung"
```

---

## Task 4: Nächtlicher Lauf

**Files:**
- Modify: `backend/app.py` (Scheduler-Block ~Zeile 285)
- Test: `backend/tests/test_ablage_abgleich_scheduler.py`

**Interfaces:**
- Consumes: `abgleichen(conn)` aus Task 3
- Produces: `_ablage_abgleich_job()` in `backend/app.py`

- [ ] **Step 1: Test schreiben**

Datei `backend/tests/test_ablage_abgleich_scheduler.py`:

```python
import os
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key-scheduler")
import inspect
from backend import app as app_modul


def test_job_ist_registriert():
    quelltext = inspect.getsource(app_modul)
    assert "_ablage_abgleich_job" in quelltext


def test_job_laeuft_um_03_30():
    quelltext = inspect.getsource(app_modul)
    stelle = quelltext.index("_ablage_abgleich_job")
    umfeld = quelltext[stelle:stelle + 600]
    assert "hour=3" in umfeld
    assert "minute=30" in umfeld
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `docker exec -w /app unfallakten-backend-dev python -m pytest backend/tests/test_ablage_abgleich_scheduler.py -v`
Expected: FAIL, `_ablage_abgleich_job` nicht gefunden

- [ ] **Step 3: Job ergänzen**

In `backend/app.py`, im Scheduler-Block direkt nach dem bestehenden Fristablauf-Job:

```python
        def _ablage_abgleich_job():
            from .db.database import get_connection
            from .services.ablage_abgleich import abgleichen
            try:
                with get_connection() as conn:
                    abgleichen(conn)
            except Exception:
                logger.exception("Ablage-Abgleich fehlgeschlagen.")

        scheduler.add_job(
            _ablage_abgleich_job,
            trigger="cron",
            hour=3,
            minute=30,
            id="ablage_abgleich",
            replace_existing=True,
        )
```

Die Protokollzeile am Ende des Blocks ergänzen: `+ "Ablage-Abgleich (taeglich 03:30)"`.

- [ ] **Step 4: Test laufen lassen — muss bestehen**

Run: `docker exec -w /app unfallakten-backend-dev python -m pytest backend/tests/test_ablage_abgleich_scheduler.py -v`
Expected: PASS, 2 Tests

- [ ] **Step 5: Backend neu starten und Protokoll prüfen**

```bash
docker restart unfallakten-backend-dev
docker logs unfallakten-backend-dev --since 2m 2>&1 | grep -i "APScheduler gestartet"
```

Erwartet: Die Zeile nennt den Ablage-Abgleich.

- [ ] **Step 6: Commit**

```bash
git add backend/app.py backend/tests/test_ablage_abgleich_scheduler.py
git commit -m "feat(portal): naechtlicher Ablage-Abgleich um 03:30"
```

---

## Task 5: Sendung an das Portal vervollständigen

Der Payload sendet die Kurzbezeichnung nicht, obwohl das Portal sie anzeigt. Der Ampel- und Statuswert muss außerdem dem Ablage-Status folgen.

**Files:**
- Modify: `backend/services/portal_sync.py` (`_build_payload` ~Zeile 92, `_berechne_ampel` ~Zeile 24)
- Modify: `stakeholder-portal/scripts/sync_connector.py` (Ampel-Ableitung ~Zeile 61)
- Test: `backend/tests/test_portal_sync_payload.py`

**Interfaces:**
- Consumes: Spalten aus Task 1
- Produces: `_build_payload(conn, akte_id)` liefert zusätzlich `akte.kurzbezeichnung`; `akte.status` ist `abgeschlossen`, sobald `ramicro_abgelegt = 1`.

- [ ] **Step 1: Test schreiben**

Datei `backend/tests/test_portal_sync_payload.py`:

```python
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
            id INTEGER PRIMARY KEY, akte_id TEXT, typ TEXT,
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
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `docker exec -w /app unfallakten-backend-dev python -m pytest backend/tests/test_portal_sync_payload.py -v`
Expected: FAIL — `kurzbezeichnung` fehlt im Payload, abgelegte Akte meldet `offen`

- [ ] **Step 3: Payload erweitern**

In `backend/services/portal_sync.py`, `_build_payload`, die Akten-Abfrage ersetzen:

```python
    akte = conn.execute("""
        SELECT az, status, unfalldatum, haftungsquote, sachbearbeiter,
               kurzbezeichnung, ramicro_abgelegt
        FROM unfallakte WHERE az = ?
    """, (akte_id,)).fetchone()
```

Und den Akten-Block im Rückgabewert:

```python
        "akte": {
            "az": akte["az"],
            "status": "abgeschlossen" if akte["ramicro_abgelegt"] else akte["status"],
            "unfalldatum": akte["unfalldatum"],
            "haftungsquote": akte["haftungsquote"],
            "sachbearbeiter": akte["sachbearbeiter"],
            "kurzbezeichnung": akte["kurzbezeichnung"],
        },
```

In `_berechne_ampel` die erste Abfrage ebenfalls um den Ablage-Status erweitern und die Auswertung darauf stützen:

```python
    akte = conn.execute(
        "SELECT status, ramicro_abgelegt FROM unfallakte WHERE az = ?", (akte_id,)
    ).fetchone()
    if not akte:
        return {"status": "akte_eroeffnet", "farbe": "grau"}

    abgeschlossen = akte["status"] == "abgeschlossen" or bool(akte["ramicro_abgelegt"])

    if akte["status"] == "klage":
        return {"status": "klage_eingereicht", "farbe": "rot"}
```

und weiter unten `if akte["status"] == "abgeschlossen" and ...` ersetzen durch `if abgeschlossen and ...`.

- [ ] **Step 4: Test laufen lassen — muss bestehen**

Run: `docker exec -w /app unfallakten-backend-dev python -m pytest backend/tests/test_portal_sync_payload.py -v`
Expected: PASS, 4 Tests

- [ ] **Step 5: Skript-Weg an dieselbe Regel angleichen**

In `stakeholder-portal/scripts/sync_connector.py`, `build_payload`, die Akten-Abfrage um `ramicro_abgelegt` erweitern und in `derive_ampel` den Aufruf entsprechend anpassen, damit der Skript-Weg nicht mit einer abweichenden Regel danebenläuft:

```python
def derive_ampel(cur: sqlite3.Cursor, az: str, akte_status: str,
                 ramicro_abgelegt: int = 0) -> tuple[str, str]:
    if akte_status == "klage":
        return "klage_eingereicht", "rot"

    if akte_status == "abgeschlossen" or ramicro_abgelegt:
        return "vollreguliert", "gruen"
```

- [ ] **Step 6: Gesamte Portal-Sync-Testdatei laufen lassen**

Run: `docker exec -w /app unfallakten-backend-dev python -m pytest backend/tests/test_portal_sync.py backend/tests/test_portal_sync_payload.py -v`
Expected: PASS, keine Regression in den bestehenden Tests

- [ ] **Step 7: Commit**

```bash
git add backend/services/portal_sync.py backend/tests/test_portal_sync_payload.py "../stakeholder-portal/scripts/sync_connector.py"
git commit -m "feat(portal): Kurzbezeichnung im Payload, Ablage-Status bestimmt Aktenstatus"
```

Liegt das Portal-Projekt außerhalb dieses Git-Baums, die Skript-Änderung dort separat committen.

---

## Task 6: Portal-Endpunkt für Zugriffe

Zuerst die Portal-Seite, damit die Kanzlei-Gegenstelle in Task 7 gegen etwas Echtes prüfen kann.

**Files:**
- Create: `stakeholder-portal/src/app/api/sync/sv-zugriffe/route.ts`
- Create: `stakeholder-portal/src/lib/sv-zugriffe.ts`
- Test: `stakeholder-portal/src/lib/__tests__/sv-zugriffe.test.ts`

**Interfaces:**
- Consumes: `verifyHmacSignature(body, signature)` aus `src/lib/sync.ts`, `getDb()` aus `src/lib/db.ts`
- Produces: `setzeSvZugriffe(payload: SvZugriffePayload, db?): { user_id: string; angelegt: number; entzogen: number; unbekannt: string[] }` mit `SvZugriffePayload = { adressnr: number; name: string; vorname?: string; email: string; akten: string[] }`

- [ ] **Step 1: Test schreiben**

Datei `stakeholder-portal/src/lib/__tests__/sv-zugriffe.test.ts` — die bestehenden Tests in `sv-data.test.ts` zeigen, wie eine Testdatenbank aufgebaut wird; dieselbe Vorgehensweise verwenden:

```typescript
import { describe, it, expect, beforeEach } from "vitest";
import Database from "better-sqlite3";
import { setzeSvZugriffe } from "@/lib/sv-zugriffe";

function testDb() {
  const db = new Database(":memory:");
  db.pragma("foreign_keys = ON");
  db.exec(`
    CREATE TABLE portal_users (
      id TEXT PRIMARY KEY,
      email TEXT NOT NULL UNIQUE,
      name TEXT,
      rolle TEXT NOT NULL
    );
    CREATE TABLE akten (
      az TEXT PRIMARY KEY,
      status TEXT NOT NULL DEFAULT 'offen'
    );
    CREATE TABLE akte_zugriff (
      user_id TEXT NOT NULL REFERENCES portal_users(id) ON DELETE CASCADE,
      az TEXT NOT NULL REFERENCES akten(az) ON DELETE CASCADE,
      PRIMARY KEY (user_id, az)
    );
  `);
  db.prepare("INSERT INTO akten (az) VALUES (?)").run("1/25");
  db.prepare("INSERT INTO akten (az) VALUES (?)").run("2/25");
  db.prepare("INSERT INTO akten (az) VALUES (?)").run("3/25");
  return db;
}

const BASIS = {
  adressnr: 25982,
  name: "Ninnivaggi",
  vorname: "KFZ-Sachverständigenbüro",
  email: "info@gn-gutachter.de",
};

describe("setzeSvZugriffe", () => {
  let db: any;
  beforeEach(() => { db = testDb(); });

  it("legt einen fehlenden Zugang an", () => {
    const ergebnis = setzeSvZugriffe({ ...BASIS, akten: ["1/25"] }, db);
    const user = db.prepare("SELECT * FROM portal_users WHERE email = ?")
      .get(BASIS.email);
    expect(user.rolle).toBe("sachverstaendiger");
    expect(ergebnis.user_id).toBe(user.id);
  });

  it("legt die Zugriffe an", () => {
    const ergebnis = setzeSvZugriffe({ ...BASIS, akten: ["1/25", "2/25"] }, db);
    const anzahl = db.prepare("SELECT COUNT(*) AS n FROM akte_zugriff").get().n;
    expect(anzahl).toBe(2);
    expect(ergebnis.angelegt).toBe(2);
  });

  it("entzieht Zugriffe, die nicht mehr in der Liste stehen", () => {
    setzeSvZugriffe({ ...BASIS, akten: ["1/25", "2/25"] }, db);
    const ergebnis = setzeSvZugriffe({ ...BASIS, akten: ["1/25"] }, db);
    const verbleibend = db.prepare("SELECT az FROM akte_zugriff").all()
      .map((r: any) => r.az);
    expect(verbleibend).toEqual(["1/25"]);
    expect(ergebnis.entzogen).toBe(1);
  });

  it("ist wiederholbar ohne Doppelanlage", () => {
    setzeSvZugriffe({ ...BASIS, akten: ["1/25"] }, db);
    const zweiter = setzeSvZugriffe({ ...BASIS, akten: ["1/25"] }, db);
    expect(zweiter.angelegt).toBe(0);
    expect(zweiter.entzogen).toBe(0);
    expect(db.prepare("SELECT COUNT(*) AS n FROM akte_zugriff").get().n).toBe(1);
  });

  it("meldet unbekannte Aktenzeichen statt abzubrechen", () => {
    const ergebnis = setzeSvZugriffe({ ...BASIS, akten: ["1/25", "999/99"] }, db);
    expect(ergebnis.unbekannt).toEqual(["999/99"]);
    expect(db.prepare("SELECT COUNT(*) AS n FROM akte_zugriff").get().n).toBe(1);
  });

  it("nimmt einem bestehenden Zugang bei leerer Liste alle Akten", () => {
    setzeSvZugriffe({ ...BASIS, akten: ["1/25", "2/25"] }, db);
    const ergebnis = setzeSvZugriffe({ ...BASIS, akten: [] }, db);
    expect(ergebnis.entzogen).toBe(2);
    expect(db.prepare("SELECT COUNT(*) AS n FROM akte_zugriff").get().n).toBe(0);
  });
});
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `cd "C:/Users/HAL9000/Documents/Projekt/Version 1.00/stakeholder-portal" && npm test -- sv-zugriffe`
Expected: FAIL, Modul `@/lib/sv-zugriffe` nicht gefunden

- [ ] **Step 3: Modul schreiben**

Datei `stakeholder-portal/src/lib/sv-zugriffe.ts`:

```typescript
import { v4 as uuid } from "uuid";
import { getDb } from "./db";

export interface SvZugriffePayload {
  adressnr: number;
  name: string;
  vorname?: string;
  email: string;
  akten: string[];
}

export interface SvZugriffeErgebnis {
  user_id: string;
  angelegt: number;
  entzogen: number;
  unbekannt: string[];
}

export function setzeSvZugriffe(
  payload: SvZugriffePayload,
  db: any = getDb(),
): SvZugriffeErgebnis {
  const email = payload.email.trim().toLowerCase();

  return db.transaction((): SvZugriffeErgebnis => {
    let user = db.prepare("SELECT id FROM portal_users WHERE LOWER(email) = ?")
      .get(email) as { id: string } | undefined;

    if (!user) {
      const id = uuid();
      const anzeigename = [payload.vorname, payload.name]
        .filter(Boolean).join(" ").trim() || payload.name;
      db.prepare(
        "INSERT INTO portal_users (id, email, name, rolle) VALUES (?, ?, ?, 'sachverstaendiger')",
      ).run(id, email, anzeigename);
      user = { id };
    }

    const bekannt = new Set(
      db.prepare("SELECT az FROM akten").all().map((r: any) => r.az),
    );
    const unbekannt = payload.akten.filter((az) => !bekannt.has(az));
    const gueltig = new Set(payload.akten.filter((az) => bekannt.has(az)));

    const vorhanden = new Set(
      db.prepare("SELECT az FROM akte_zugriff WHERE user_id = ?")
        .all(user.id).map((r: any) => r.az),
    );

    let angelegt = 0;
    for (const az of gueltig) {
      if (vorhanden.has(az)) continue;
      db.prepare("INSERT INTO akte_zugriff (user_id, az) VALUES (?, ?)")
        .run(user.id, az);
      angelegt += 1;
    }

    let entzogen = 0;
    for (const az of vorhanden) {
      if (gueltig.has(az)) continue;
      db.prepare("DELETE FROM akte_zugriff WHERE user_id = ? AND az = ?")
        .run(user.id, az);
      entzogen += 1;
    }

    return { user_id: user.id, angelegt, entzogen, unbekannt };
  })();
}
```

- [ ] **Step 4: Test laufen lassen — muss bestehen**

Run: `cd "C:/Users/HAL9000/Documents/Projekt/Version 1.00/stakeholder-portal" && npm test -- sv-zugriffe`
Expected: PASS, 6 Tests

- [ ] **Step 5: Route schreiben**

Datei `stakeholder-portal/src/app/api/sync/sv-zugriffe/route.ts`:

```typescript
import { NextRequest, NextResponse } from "next/server";
import { verifyHmacSignature } from "@/lib/sync";
import { setzeSvZugriffe, type SvZugriffePayload } from "@/lib/sv-zugriffe";

export async function POST(req: NextRequest) {
  const apiKey = req.headers.get("X-Sync-API-Key") ?? "";
  const signature = req.headers.get("X-Sync-Signature") ?? "";

  if (!process.env.SYNC_API_KEY || apiKey !== process.env.SYNC_API_KEY) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await req.text();

  if (!verifyHmacSignature(body, signature)) {
    return NextResponse.json({ error: "Invalid signature" }, { status: 401 });
  }

  let payload: unknown;
  try {
    payload = JSON.parse(body);
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const p = payload as SvZugriffePayload;

  if (!p || typeof p.email !== "string" || !p.email.includes("@")) {
    return NextResponse.json({ error: "email fehlt oder ist ungültig" }, { status: 400 });
  }
  if (!Array.isArray(p.akten) || p.akten.some((az) => typeof az !== "string")) {
    return NextResponse.json({ error: "akten muss eine Liste von Aktenzeichen sein" }, { status: 400 });
  }
  if (typeof p.name !== "string" || p.name.trim() === "") {
    return NextResponse.json({ error: "name fehlt" }, { status: 400 });
  }

  try {
    const ergebnis = setzeSvZugriffe(p);
    return NextResponse.json(ergebnis);
  } catch (err) {
    console.error("SV-Zugriffs-Abgleich fehlgeschlagen:", err);
    return NextResponse.json({ error: "Verarbeitungsfehler" }, { status: 500 });
  }
}
```

- [ ] **Step 6: Typprüfung und Gesamttests**

Run: `cd "C:/Users/HAL9000/Documents/Projekt/Version 1.00/stakeholder-portal" && npm run typecheck && npm test`
Expected: keine Typfehler, alle Tests bestehen

- [ ] **Step 7: Commit**

```bash
cd "C:/Users/HAL9000/Documents/Projekt/Version 1.00/stakeholder-portal"
git add src/lib/sv-zugriffe.ts src/lib/__tests__/sv-zugriffe.test.ts "src/app/api/sync/sv-zugriffe/route.ts"
git commit -m "feat(sync): Endpunkt fuer SV-Zugriffe (anlegen, entziehen, HMAC-geprueft)"
```

---

## Task 7: Zugriffs-Abgleich auf der Kanzlei-Seite

**Files:**
- Create: `backend/services/sv_zugriff_sync.py`
- Modify: `backend/routers/sv_portal_routes.py` (`_hole_akten_fuer_sv` herausnehmen, neue Route, Toggle auf `portal_gesperrt`, `alle`-Route entfernen, Aktenzahl)
- Modify: `backend/app.py` (CLI-Befehl)
- Test: `backend/tests/test_sv_zugriff_sync.py`

**Interfaces:**
- Consumes: `abgleichen(conn, az_liste=...)` aus Task 3; `process_queue(conn, max_batch)` aus `portal_sync.py`
- Produces:
  - `hole_akten_fuer_sv(adressnr: int) -> list[dict]` (verschoben, Rückgabe unverändert: `{"az", "ra_bezeichnung"}`)
  - `zugriffe_abgleichen(conn, adressnr: int) -> dict` mit `gesamt`, `gesperrt`, `uebertragen`, `gesendet` (bool), `antwort` (dict oder None)

- [ ] **Step 1: Test schreiben**

Datei `backend/tests/test_sv_zugriff_sync.py`:

```python
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
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `docker exec -w /app unfallakten-backend-dev python -m pytest backend/tests/test_sv_zugriff_sync.py -v`
Expected: FAIL, Modul nicht vorhanden

- [ ] **Step 3: Dienst schreiben**

Datei `backend/services/sv_zugriff_sync.py`:

```python
"""
Meldet dem Portal, welcher SV-Zugang welche Akten sehen darf.

Berechtigung und Akteninhalt sind getrennt: Diese Sendung transportiert nur
die Zuordnung. Die Akte selbst kommt ueber den Aktensync. Im Portal verweist
akte_zugriff.az per Fremdschluessel auf akten(az) - deshalb wird die
Warteschlange hier vorher geleert.
"""
import hashlib
import hmac as _hmac
import json
import logging
import os

import requests

from ..ramicro.ablage_service import hole_ablage_status  # noqa: F401  (Testbarkeit)
from ..ramicro.connector import (
    get_ramicro_connection,
    RaMicroNichtAktiv,
    RaMicroVerbindungsFehler,
)
from .ablage_abgleich import abgleichen
from .portal_sync import process_queue

logger = logging.getLogger(__name__)


def hole_akten_fuer_sv(adressnr):
    # type: (int) -> list
    """Alle Akten, in denen adressnr in RA-MICRO als SV eingetragen ist."""
    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT DISTINCT a.sAktenNummer AS az,
                       a.sAktenKurzBezeichnung AS ra_bezeichnung
                FROM tblAktenBeteiligte b
                INNER JOIN tblAkten a ON a.GUIDAkte = b.GUIDAkte
                WHERE b.iAdressnummer = %s
                  AND b.sBeteiligtenKennzeichen LIKE 'SV%%'
                  AND b.bDeaktiviert = 0
                """,
                (adressnr,),
            )
            return [{"az": r["az"], "ra_bezeichnung": r["ra_bezeichnung"] or ""}
                    for r in cur.fetchall() if r["az"]]
    except (RaMicroNichtAktiv, RaMicroVerbindungsFehler):
        return []
    except Exception as e:
        logger.warning("SV-Akten-Lookup fehlgeschlagen (adressnr=%s): %s", adressnr, e)
        return []


def _sende_zugriffe(payload):
    # type: (dict) -> dict
    url = os.environ.get("PORTAL_API_URL", "")
    api_key = os.environ.get("PORTAL_API_KEY", "")
    secret = os.environ.get("PORTAL_HMAC_SECRET", "")
    if not url or not api_key or not secret:
        logger.info("Zugriffs-Abgleich: Portal nicht konfiguriert - nicht gesendet.")
        return None

    body = json.dumps(payload, ensure_ascii=False, default=str)
    signatur = _hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    try:
        resp = requests.post(
            url + "/api/sync/sv-zugriffe",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Sync-API-Key": api_key,
                "X-Sync-Signature": signatur,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            logger.warning("Zugriffs-Abgleich: HTTP %s", resp.status_code)
            return None
        return resp.json()
    except requests.exceptions.RequestException as exc:
        logger.error("Zugriffs-Abgleich fehlgeschlagen: %s", exc)
        return None


def zugriffe_abgleichen(conn, adressnr):
    # type: (object, int) -> dict
    sv = conn.execute(
        "SELECT adressnr, name, vorname, email FROM sv_portal_accounts WHERE adressnr = ?",
        (adressnr,),
    ).fetchone()

    ra_akten = [a["az"] for a in hole_akten_fuer_sv(adressnr)]
    bericht = {"gesamt": len(ra_akten), "gesperrt": 0, "uebertragen": 0,
               "gesendet": False, "antwort": None}

    if not sv or not ra_akten:
        return bericht

    abgleichen(conn, az_liste=ra_akten)

    platzhalter = ",".join("?" * len(ra_akten))
    gesperrt = {r["az"] for r in conn.execute(
        "SELECT az FROM unfallakte WHERE portal_gesperrt = 1 "
        "AND az IN ({})".format(platzhalter),
        ra_akten,
    )}
    frei = [az for az in ra_akten if az not in gesperrt]

    for az in frei:
        conn.execute("UPDATE unfallakte SET portal_aktiv = 1 WHERE az = ?", (az,))
    for az in gesperrt:
        conn.execute("UPDATE unfallakte SET portal_aktiv = 0 WHERE az = ?", (az,))
    conn.commit()

    bericht["gesperrt"] = len(gesperrt)
    bericht["uebertragen"] = len(frei)

    antwort = _sende_zugriffe({
        "adressnr": sv["adressnr"],
        "name": sv["name"],
        "vorname": sv["vorname"],
        "email": sv["email"],
        "akten": frei,
    })
    bericht["gesendet"] = antwort is not None
    bericht["antwort"] = antwort
    return bericht
```

- [ ] **Step 4: Test laufen lassen — muss bestehen**

Run: `docker exec -w /app unfallakten-backend-dev python -m pytest backend/tests/test_sv_zugriff_sync.py -v`
Expected: PASS, 5 Tests

- [ ] **Step 5: Routen anpassen**

In `backend/routers/sv_portal_routes.py`:

1. `_hole_akten_fuer_sv` löschen und stattdessen importieren:
   `from ..services.sv_zugriff_sync import hole_akten_fuer_sv, zugriffe_abgleichen`
   Alle Aufrufe von `_hole_akten_fuer_sv(` auf `hole_akten_fuer_sv(` umstellen.

2. Die Route `akten_alle_toggle` (`PATCH /<adressnr>/akten/alle`) **ersatzlos entfernen**.

3. `toggle_portal_aktiv` auf die Sperre umstellen:

```python
@sv_portal_bp.route("/akten/<path:akte_az>/portal_gesperrt", methods=["PATCH"])
@login_erforderlich
def toggle_portal_gesperrt(akte_az: str):
    body = _body()
    gesperrt = body.get("portal_gesperrt")
    if gesperrt not in (0, 1, True, False):
        return _err("portal_gesperrt muss 0 oder 1 sein.", 400)
    wert = 1 if gesperrt else 0
    with get_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO unfallakte (az) VALUES (?)", (akte_az,))
        conn.execute(
            "UPDATE unfallakte SET portal_gesperrt = ?, portal_aktiv = ? WHERE az = ?",
            (wert, 0 if wert else 1, akte_az),
        )
        conn.commit()
    return _j({"az": akte_az, "portal_gesperrt": wert})
```

4. Neue Route für den Abgleich:

```python
@sv_portal_bp.route("/<int:adressnr>/zugriffe-abgleichen", methods=["POST"])
@login_erforderlich
def zugriffe_abgleichen_route(adressnr: int):
    with get_connection() as conn:
        if not conn.execute(
            "SELECT 1 FROM sv_portal_accounts WHERE adressnr = ?", (adressnr,)
        ).fetchone():
            return _err("SV-Account nicht gefunden.", 404)
        process_queue(conn, max_batch=1000)
        bericht = zugriffe_abgleichen(conn, adressnr)
    return _j(bericht)
```

Dazu `from ..services.portal_sync import process_queue` ergänzen.

5. In `akten()` je Zeile den Ablage-Status und die Sperre mitgeben — die SQLite-Abfrage erweitern auf
   `SELECT az, kurzbezeichnung, unfalldatum, portal_aktiv, portal_gesperrt, ramicro_abgelegt FROM unfallakte WHERE az IN (...)`
   und im Zweig „nicht im System" `"portal_gesperrt": 0, "ramicro_abgelegt": 0` ergänzen.

6. In `liste()` die Aktenzahl aus RA-MICRO ziehen statt aus `beteiligte`:

```python
@sv_portal_bp.route("", methods=["GET"])
@login_erforderlich
def liste():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT adressnr, name, vorname, email,
                   portal_aktiv, einladung_gesendet_am, angelegt_am
            FROM sv_portal_accounts
            ORDER BY name
        """).fetchall()
        ergebnis = []
        for r in rows:
            eintrag = dict(r)
            az_liste = [a["az"] for a in hole_akten_fuer_sv(r["adressnr"])]
            eintrag["akten_anzahl"] = len(az_liste)
            if az_liste:
                platzhalter = ",".join("?" * len(az_liste))
                eintrag["akten_laufend"] = conn.execute(
                    "SELECT COUNT(*) AS n FROM unfallakte "
                    "WHERE ramicro_abgelegt = 0 AND az IN ({})".format(platzhalter),
                    az_liste,
                ).fetchone()["n"]
            else:
                eintrag["akten_laufend"] = 0
            ergebnis.append(eintrag)
    return _j(ergebnis)
```

- [ ] **Step 6: CLI-Befehl ergänzen**

In `backend/app.py`, nach `ablage_abgleich_cmd`:

```python
    @app.cli.command("sync-sv-zugriffe")
    @click.argument("adressnr", type=int)
    def sync_sv_zugriffe_cmd(adressnr):
        """Gleicht die Portal-Zugriffe eines Sachverstaendigen ab."""
        from .db.database import get_connection
        from .services.portal_sync import process_queue
        from .services.sv_zugriff_sync import zugriffe_abgleichen
        with get_connection() as conn:
            print("Aktensync: {} Akte(n) uebertragen.".format(
                process_queue(conn, max_batch=1000)))
            bericht = zugriffe_abgleichen(conn, adressnr)
        print("Akten gesamt: {}, gesperrt: {}, uebertragen: {}, gesendet: {}".format(
            bericht["gesamt"], bericht["gesperrt"],
            bericht["uebertragen"], bericht["gesendet"]))
        if bericht["antwort"]:
            print("Portal-Antwort: {}".format(bericht["antwort"]))
```

- [ ] **Step 7: Bestehende SV-Portal-Tests laufen lassen**

Run: `docker exec -w /app unfallakten-backend-dev python -m pytest backend/tests/test_sv_portal.py backend/tests/test_sv_zugriff_sync.py -v`
Expected: PASS. Schlägt ein alter Test wegen der entfernten `alle`-Route fehl, den Test entfernen — die Route ist bewusst weggefallen.

- [ ] **Step 8: Commit**

```bash
git add backend/services/sv_zugriff_sync.py backend/tests/test_sv_zugriff_sync.py backend/routers/sv_portal_routes.py backend/app.py
git commit -m "feat(sv-portal): Zugriffs-Abgleich, Sperre statt Freigabe, Aktenzahl aus RA-MICRO"
```

---

## Task 8: Irreführende Zahlungsanzeige im Portal

Eine Akte ohne erfasste Beträge zeigt „bezahlt ✓" — der Sachverständige hielte offene Honorare für beglichen.

**Files:**
- Modify: `stakeholder-portal/src/components/sv/AkteCard.tsx:109-112`
- Modify: `stakeholder-portal/src/components/sv/RechnungBlock.tsx`
- Test: `stakeholder-portal/src/lib/__tests__/rechnung-anzeige.test.ts`
- Create: `stakeholder-portal/src/lib/rechnung-anzeige.ts`

**Interfaces:**
- Produces: `rechnungText(gefordert: number, reguliert: number): { text: string; offen: boolean }`

- [ ] **Step 1: Test schreiben**

Datei `stakeholder-portal/src/lib/__tests__/rechnung-anzeige.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { rechnungText } from "@/lib/rechnung-anzeige";

describe("rechnungText", () => {
  it("meldet nichts, wenn keine Forderung erfasst ist", () => {
    expect(rechnungText(0, 0)).toEqual({ text: "—", offen: false });
  });

  it("meldet den offenen Betrag", () => {
    const ergebnis = rechnungText(1000, 400);
    expect(ergebnis.offen).toBe(true);
    expect(ergebnis.text).toContain("600");
    expect(ergebnis.text).toContain("offen");
  });

  it("meldet bezahlt, wenn alles reguliert ist", () => {
    expect(rechnungText(1000, 1000)).toEqual({ text: "bezahlt ✓", offen: false });
  });

  it("meldet bezahlt bei Ueberzahlung", () => {
    expect(rechnungText(1000, 1200).text).toBe("bezahlt ✓");
  });

  it("meldet nichts, wenn ohne Forderung gezahlt wurde", () => {
    expect(rechnungText(0, 500)).toEqual({ text: "—", offen: false });
  });
});
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `cd "C:/Users/HAL9000/Documents/Projekt/Version 1.00/stakeholder-portal" && npm test -- rechnung-anzeige`
Expected: FAIL, Modul nicht gefunden

- [ ] **Step 3: Modul schreiben**

Datei `stakeholder-portal/src/lib/rechnung-anzeige.ts`:

```typescript
import { formatEur } from "./format";

export function rechnungText(
  gefordert: number,
  reguliert: number,
): { text: string; offen: boolean } {
  if (!gefordert) return { text: "—", offen: false };

  const ausstehend = Math.max(0, gefordert - reguliert);
  if (ausstehend > 0) return { text: `${formatEur(ausstehend)} offen`, offen: true };

  return { text: "bezahlt ✓", offen: false };
}
```

- [ ] **Step 4: Test laufen lassen — muss bestehen**

Run: `cd "C:/Users/HAL9000/Documents/Projekt/Version 1.00/stakeholder-portal" && npm test -- rechnung-anzeige`
Expected: PASS, 5 Tests

- [ ] **Step 5: Karte umstellen**

In `AkteCard.tsx` die Berechnung von `ausstehend` ersetzen:

```typescript
  const rechnung = rechnungText(akte.sv_kosten_gefordert, akte.sv_kosten_reguliert);
```

Den Import ergänzen (`import { rechnungText } from "@/lib/rechnung-anzeige";`), `formatEur` entfernen, falls sonst nicht mehr genutzt. `eurStyle` auf `rechnung.offen` stützen:

```typescript
  const eurStyle: CSSProperties = {
    fontSize: "0.78rem",
    fontWeight: 700,
    color: rechnung.offen ? "var(--sv-yellow)" : "var(--text-subtle)",
    whiteSpace: "nowrap",
  };
```

und die Ausgabe:

```typescript
        <div style={eurStyle}>{rechnung.text}</div>
```

- [ ] **Step 6: RechnungBlock angleichen**

`RechnungBlock.tsx` lesen und dieselbe Funktion verwenden, wo heute aus `gefordert`/`reguliert` eine Zahlungsaussage abgeleitet wird. Zeigt der Block bei fehlender Forderung ebenfalls eine Zahlungsaussage, auf `rechnungText` umstellen.

- [ ] **Step 7: Gesamttests und Typprüfung**

Run: `cd "C:/Users/HAL9000/Documents/Projekt/Version 1.00/stakeholder-portal" && npm run typecheck && npm test`
Expected: keine Typfehler, alle Tests bestehen

- [ ] **Step 8: Commit**

```bash
cd "C:/Users/HAL9000/Documents/Projekt/Version 1.00/stakeholder-portal"
git add src/lib/rechnung-anzeige.ts src/lib/__tests__/rechnung-anzeige.test.ts src/components/sv/AkteCard.tsx src/components/sv/RechnungBlock.tsx
git commit -m "fix(sv): keine Zahlungsaussage ohne erfasste Forderung"
```

---

## Task 9: Einstellungen-Oberfläche

Drei Änderungen: abgelaufene Sitzung sichtbar machen, Schalter auf die Sperre umstellen, Aktenzahl und Ablage-Status anzeigen.

**Files:**
- Modify: `frontend/src/api.js` (`apiSvPortal`)
- Modify: `frontend/src/views/EinstellungenView.jsx` (Ladefunktionen ~Zeile 111-123, SV-Liste ~Zeile 1045, Aktenliste ~Zeile 1268)
- Test: `frontend/src/views/__tests__/EinstellungenSvPortal.test.jsx` (Ablage im vorhandenen Testordner prüfen und anpassen)

**Interfaces:**
- Consumes: Routen aus Task 7
- Produces: keine für andere Tasks

- [ ] **Step 1: Test schreiben**

Ablageort der Frontend-Tests prüfen (`ls frontend/src/**/__tests__`) und die Datei dort anlegen. Inhalt:

```jsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import EinstellungenView from "../EinstellungenView";
import { apiSvPortal } from "../../api";

vi.mock("../../api", async () => {
  const echt = await vi.importActual("../../api");
  return {
    ...echt,
    apiSvPortal: {
      liste: vi.fn(),
      akten: vi.fn(),
      suche: vi.fn().mockResolvedValue([]),
    },
  };
});

describe("SV-Portal-Reiter", () => {
  beforeEach(() => vi.clearAllMocks());

  it("meldet eine abgelaufene Sitzung statt einer leeren Liste", async () => {
    const fehler = new Error("Sitzung abgelaufen. Bitte erneut anmelden.");
    fehler.status = 401;
    apiSvPortal.liste.mockRejectedValue(fehler);

    render(<EinstellungenView />);

    await waitFor(() => {
      expect(screen.getByText(/Sitzung abgelaufen/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(/Noch keine SV-Zugänge/i)).not.toBeInTheDocument();
  });

  it("zeigt laufende und gesamte Aktenzahl", async () => {
    apiSvPortal.liste.mockResolvedValue([{
      adressnr: 25982, name: "Ninnivaggi", vorname: "KFZ-SV",
      email: "info@gn-gutachter.de", portal_aktiv: 1,
      einladung_gesendet_am: null, angelegt_am: "2026-08-20",
      akten_anzahl: 578, akten_laufend: 111,
    }]);

    render(<EinstellungenView />);

    await waitFor(() => {
      expect(screen.getByText(/111 laufend/)).toBeInTheDocument();
      expect(screen.getByText(/578 gesamt/)).toBeInTheDocument();
    });
  });
});
```

Der Reiter muss dafür beim Rendern aktiv sein — im Test denselben Weg wählen wie vorhandene Reiter-Tests in dieser Datei (Reiter-Schaltfläche `🔗 SV-Portal` anklicken).

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `cd frontend && npm test -- EinstellungenSvPortal`
Expected: FAIL, keine Fehlermeldung im Baum

- [ ] **Step 3: Ladefunktionen umstellen**

In `EinstellungenView.jsx`:

```jsx
  const [svFehler, setSvFehler] = useState("");

  const ladeSvListe = async () => {
    setSvLaedt(true);
    setSvFehler("");
    try {
      setSvListe(await apiSvPortal.liste());
    } catch (e) {
      setSvListe([]);
      setSvFehler(
        e?.status === 401
          ? "Sitzung abgelaufen — bitte neu anmelden."
          : e?.message || "SV-Liste konnte nicht geladen werden."
      );
    } finally {
      setSvLaedt(false);
    }
  };
```

Dieselbe Behandlung in `ladeSvAkten` mit einem eigenen Zustand `svAktenFehler`.

Im Aufbau der linken Spalte vor der Liste ausgeben:

```jsx
                {svFehler && (
                  <p role="alert" style={{ color: "var(--rot, #b91c1c)", fontSize: 13 }}>
                    {svFehler}
                  </p>
                )}
```

Die Bedingung für die Leermeldung um `!svFehler` erweitern, damit nicht beides zugleich erscheint.

- [ ] **Step 4: Aktenzahl anzeigen**

In der SV-Listenzeile die bisherige Aktenzahl ersetzen durch:

```jsx
                        <span style={{ fontSize: 11, color: "#6b7280" }}>
                          {sv.akten_laufend ?? 0} laufend · {sv.akten_anzahl ?? 0} gesamt
                        </span>
```

- [ ] **Step 5: Schalter auf die Sperre umstellen**

In `api.js` im Objekt `apiSvPortal`:

```javascript
  togglePortalGesperrt: (akte_az, gesperrt) =>
    request(`/einstellungen/sv-portal/akten/${encodeURIComponent(akte_az)}/portal_gesperrt`, {
      method: 'PATCH',
      body: JSON.stringify({ portal_gesperrt: gesperrt ? 1 : 0 }),
    }),
  zugriffeAbgleichen: (adressnr) =>
    request(`/einstellungen/sv-portal/${adressnr}/zugriffe-abgleichen`, { method: 'POST' }),
```

`togglePortalAktiv` und `alleToggle` entfernen.

In der Aktenliste den Schalter umstellen: angezeigt wird „freigegeben", wenn `akte.portal_gesperrt` falsch ist; beim Umlegen `apiSvPortal.togglePortalGesperrt(akte.az, !akte.portal_gesperrt)` aufrufen. Den Master-Schalter „alle freigeben/sperren" entfernen. Je Zeile zusätzlich den Ablage-Status ausgeben, etwa `{akte.ramicro_abgelegt ? "abgeschlossen" : "laufend"}`.

Einen Knopf „Zugriffe abgleichen" in die rechte Spalte setzen, der `apiSvPortal.zugriffeAbgleichen(sv.adressnr)` aufruft und das Ergebnis als Toast meldet („578 Akten, 0 gesperrt, 578 übertragen").

- [ ] **Step 6: Tests laufen lassen — müssen bestehen**

Run: `cd frontend && npm test`
Expected: PASS, keine Regression

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api.js frontend/src/views/EinstellungenView.jsx frontend/src/views/__tests__/EinstellungenSvPortal.test.jsx
git commit -m "feat(einstellungen): Sperre statt Freigabe, Zugriffs-Abgleich, Sitzungsfehler sichtbar"
```

---

## Task 10: Inbetriebnahme und Abnahme

Kein neuer Code — die Kette wird verbunden und geprüft.

**Files:**
- Modify: `.env` (Zugangsdaten des Portals — nicht versioniert)
- Modify: `docs/TODO.md`, `docs/CHANGELOG.md`

- [ ] **Step 1: Zugangsdaten des Portals holen**

```bash
grep -E "SYNC_API_KEY|SYNC_HMAC_SECRET" "C:/Users/HAL9000/Documents/Projekt/Version 1.00/stakeholder-portal/.env.local"
```

Fehlen sie, im Portal setzen und dort eintragen.

- [ ] **Step 2: Backend auf das lokale Portal zeigen lassen**

**Nicht** in `docker-compose.yml` — diese Datei ist versioniert, dort eingetragene Schlüssel landeten in der Git-Historie. Der Backend-Dienst liest bereits `env_file: .env`, und `.env` ist von der Versionierung ausgenommen (`.gitignore:14`). Also dort ergänzen:

```
PORTAL_API_URL=http://host.docker.internal:3002
PORTAL_API_KEY=<SYNC_API_KEY aus .env.local des Portals>
PORTAL_HMAC_SECRET=<SYNC_HMAC_SECRET aus .env.local des Portals>
```

`docker-compose.yml` bleibt unverändert.

Danach zwingend neu erzeugen — ein Neustart übernimmt geänderte Umgebungsvariablen nicht:

```bash
docker compose up -d --force-recreate backend
docker exec unfallakten-backend-dev sh -c 'env | grep PORTAL_'
```

- [ ] **Step 3: Portal starten und erreichbar prüfen**

```bash
cd "C:/Users/HAL9000/Documents/Projekt/Version 1.00/stakeholder-portal" && npm run dev
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3002/login
```

Erwartet: `200`

- [ ] **Step 4: Vorschaulauf und Rücksprache**

```bash
docker exec -w /app -e FLASK_APP="backend.app:erstelle_app()" unfallakten-backend-dev flask ablage-abgleich --vorschau
```

Die Zahlen RA Schatz vorlegen. **Ohne seine Bestätigung nicht weiter.**

- [ ] **Step 5: Schreibenden Lauf ausführen**

```bash
docker exec unfallakten-backend-dev python -c "import sqlite3; s=sqlite3.connect('/app/data/unfallakten.db'); d=sqlite3.connect('/app/data/unfallakten.db.bak_vor_ablage_abgleich'); s.backup(d); d.close(); s.close(); print('Backup erstellt.')"
docker exec -w /app -e FLASK_APP="backend.app:erstelle_app()" unfallakten-backend-dev flask ablage-abgleich
```

- [ ] **Step 6: Akten und Zugriffe übertragen**

```bash
docker exec -w /app -e FLASK_APP="backend.app:erstelle_app()" unfallakten-backend-dev flask sync-sv-zugriffe 25982
```

Erwartet: „Akten gesamt: 578, gesperrt: 0, übertragen: 578, gesendet: True"

- [ ] **Step 7: Abnahme als Ninnivaggi**

Im Portal-Admin (`http://localhost:3002/admin/impersonate`) auf Ninnivaggi wechseln und prüfen:

- Startseite meldet „Meine Akten — 578 Fälle" (Cockpitmodus, nicht Kompaktmodus)
- `/sv/akten` zeigt beim Öffnen **111** Akten
- Chip „Abgeschlossen" klappt **467** auf
- Suche nach „Taskoparan" findet Akte 1000/25
- Keine Akte zeigt „bezahlt ✓" ohne erfasste Forderung
- Eine Akte in RA-MICRO reaktivieren, dann `flask ablage-abgleich` und `flask sync-sv-zugriffe 25982`: Sie steht wieder unter „Laufend", ihr vorheriger Aktenstatus ist wiederhergestellt
- Eine Akte in den Einstellungen sperren, `flask sync-sv-zugriffe 25982`: Sie verschwindet aus seiner Liste

- [ ] **Step 8: Vollsuiten laufen lassen**

```bash
docker exec -w /app unfallakten-backend-dev python -m pytest backend/tests/ -q
cd "C:/Users/HAL9000/Documents/Projekt/Version 1.00/stakeholder-portal" && npm test
cd "C:/Users/HAL9000/Documents/Projekt/Version 1.00/unfallakten/frontend" && npm test
```

Erwartet: keine Fehlschläge. Die Backend-Vollsuite stand zuletzt bei 1774 grün.

- [ ] **Step 9: Unterlagen nachziehen**

- `docs/CHANGELOG.md`: Eintrag mit Datum, Migration 69, den sechs Befunden und der Abnahme.
- `docs/TODO.md`: Punkt „Veröffentlichung des Portals" in den Backlog aufnehmen (Domain, SSL, Zugangslinks per E-Mail, Auftragsverarbeitung und Datenschutzerklärung für den SV-Zugang).

- [ ] **Step 10: Commit**

```bash
git add docs/CHANGELOG.md docs/TODO.md
git commit -m "docs(portal): Abnahme dokumentiert"
```

`.env` wird bewusst **nicht** committet — sie enthält Zugangsschlüssel und ist von der Versionierung ausgenommen.

---

## Selbstprüfung gegen die Spec

| Spec-Abschnitt | Task |
|---|---|
| 3.1 Freigabe wird zur Sperre | 1 (Spalte), 7 (Route/Dienst), 9 (Oberfläche) |
| 4.1 Migration 69 | 1 |
| 4.2 `ablage_service` | 2 |
| 4.3 Abgleichlauf mit Reaktivierung | 3 |
| 4.4 Zweistufige Erstanwendung | 3 (Vorschau), 10 (Rücksprache) |
| 4.5 Nächtlicher Lauf | 4 |
| 5 Beschriftung | 3 (Übernahme), 5 (Payload) |
| 6.1 Kanzlei-Seite | 7 |
| 6.2 Portal-Seite | 6 |
| 6.3 Aktenzahl | 7 (Backend), 9 (Anzeige) |
| D-1 fehlende Tabellen | 1 |
| D-2 `gutachten_nr` | 1 (Spalte nachgeholt statt Feld entfernt — die Migration 39 war ohnehin dafür gedacht) |
| D-3 Portal-Adresse | 10 |
| D-4 „bezahlt ✓" | 8 |
| D-5 stiller 401 | 9 |
| D-6 nicht löschbare Akten | 1 |
| 10 Tests | in jedem Task |
| 11 Abnahme | 10 |

**Abweichung von der Spec:** D-2 wird nicht durch Entfernen des Feldes gelöst, sondern durch Nachholen der Spalte. Grund: Bei der Planung stellte sich heraus, dass Migration 39 genau diese Spalte anlegen sollte und in Bestands-Datenbanken nur nie ausgeführt wurde. Das Nachholen ist der kleinere Eingriff und lässt den vom Portal vorgesehenen Weg offen. Das Feld bleibt inhaltlich leer, wie in der Spec beschrieben.

**Zusätzlich gegenüber der Spec:** Migration 69 holt auch `unfallakte.regulierung_status`, `unfalldetails.erstellt_am` und die Tabelle `fragebogen_erstkontakt` nach. Diese Lücken sind beim Vergleich der Live-Datenbank mit einer frisch erzeugten aufgefallen; `fragebogen_erstkontakt` verursacht im laufenden Betrieb bereits Fehler 500 auf `/email/fragebogen-erstkontakt`, `regulierung_status` legt die Regulierungs-Status-Kachel lahm. Sie im selben Zug mitzunehmen kostet nichts und behebt bestehende Störungen.
