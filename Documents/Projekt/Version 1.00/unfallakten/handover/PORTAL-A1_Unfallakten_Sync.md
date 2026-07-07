# Portal-A1: Unfallakten-Sync-Integration – Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Erweitert das bestehende Unfallakten-Backend um Portal-Sync-Fähigkeiten: DB-Schema 38, Sync-Service (Push-Queue → Strato), Admin-API für Aktivierung & Einladungen, Frontend-Controls (Portal-Toggle, Einladen-Button), automatische Abschluss-Summary-Generierung.

**Architecture:** Neues Service-Modul `backend/services/portal_sync.py` mit Queue-basiertem Sync (Flask CLI `sync-portal` oder APScheduler 60s). Portal-Flag via `_portal_flag()` Hook in bestehenden Routes. Flask Blueprint `portal_routes.py` für Admin-Operationen. Abschluss-Summary DOCX wird bei `status → abgeschlossen` auto-generiert und als Dokument mit `portal_sichtbar=1` gespeichert.

**Tech Stack:** Python 3.9, SQLite (get_connection()), requests, python-docx, React/JSX (Frontend)

**Kontext:** Workstream A des Stakeholder-Portal-Projekts. Workstream B (neues Next.js-Portal) ist in `PORTAL-B1_Foundation.md` beschrieben.

---

## File Structure

| Datei | Aktion | Zweck |
|---|---|---|
| `backend/db/schema_manager.py` | Modify | Migration 38 + `_run_migration_38()` |
| `backend/services/portal_sync.py` | Create | Ampel-Berechnung, Payload-Builder, Queue-Verarbeitung |
| `backend/routers/portal_routes.py` | Create | Flask Blueprint: aktivieren, einladen, status |
| `backend/app.py` | Modify | Blueprint registrieren + CLI-Command |
| `backend/routers/akten_routes.py` | Modify | `_portal_flag`-Hook bei Status-Update |
| `backend/routers/abrechnungsschreiben_routes.py` | Modify | `_portal_flag`-Hook bei neuem AB |
| `backend/routers/dokumente_routes.py` | Modify | `portal_sichtbar`-Endpoint + Hook |
| `backend/word/abschluss_summary.py` | Create | Abschluss-Summary DOCX |
| `backend/tests/test_migration_38.py` | Create | Tests für Migration 38 |
| `backend/tests/test_portal_sync.py` | Create | Tests für portal_sync.py |
| `frontend/src/api.js` | Modify | Portal-API-Funktionen |
| `frontend/src/sections/BeteiligteSection.jsx` | Modify | "Portal einladen"-Button |
| `frontend/src/components/AkteDetailView.jsx` | Modify | Portal-aktiv Toggle + Sync-Zeitstempel |
| `.env.example` | Modify | PORTAL_API_URL/KEY/HMAC_SECRET |

---

## Task 1: Migration 38 – Portal-Sync-Felder

**Files:**
- Modify: `backend/db/schema_manager.py`
- Create: `backend/tests/test_migration_38.py`

- [ ] **Step 1.1: Test schreiben**

```python
# backend/tests/test_migration_38.py
import sqlite3
import pytest
from backend.db.schema_manager import _run_migration_38


@pytest.fixture
def fresh_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE schema_version (version INTEGER PRIMARY KEY, beschreibung TEXT);
        CREATE TABLE benutzer (id INTEGER PRIMARY KEY, name TEXT, email TEXT UNIQUE,
            passwort_hash TEXT, rolle TEXT DEFAULT 'sachbearbeiter',
            aktiv INTEGER DEFAULT 1, erstellt_am TEXT, zuletzt_login TEXT);
        CREATE TABLE unfallakte (az TEXT PRIMARY KEY, unfalldatum TEXT DEFAULT '',
            status TEXT DEFAULT 'offen', haftungsquote REAL DEFAULT 100.0,
            erstellt_am TEXT DEFAULT (datetime('now','localtime')));
        CREATE TABLE dokumente (id INTEGER PRIMARY KEY, akte_id TEXT, typ TEXT,
            dateiname TEXT, dateipfad TEXT, dateityp TEXT DEFAULT 'pdf');
        CREATE TABLE beteiligte (id INTEGER PRIMARY KEY, akte_id TEXT,
            rolle TEXT, name TEXT, email TEXT);
    """)
    return conn


def test_migration_38_fuegt_portal_spalten_zu_unfallakte(fresh_conn):
    _run_migration_38(fresh_conn)
    spalten = {r[1] for r in fresh_conn.execute("PRAGMA table_info(unfallakte)").fetchall()}
    assert "portal_aktiv" in spalten
    assert "portal_sync_pending" in spalten
    assert "portal_last_sync" in spalten


def test_migration_38_fuegt_portal_sichtbar_zu_dokumente(fresh_conn):
    _run_migration_38(fresh_conn)
    spalten = {r[1] for r in fresh_conn.execute("PRAGMA table_info(dokumente)").fetchall()}
    assert "portal_sichtbar" in spalten


def test_migration_38_erstellt_portal_tabellen(fresh_conn):
    _run_migration_38(fresh_conn)
    tables = {r[0] for r in fresh_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert "portal_sync_queue" in tables
    assert "portal_einladungen" in tables


def test_migration_38_ist_idempotent(fresh_conn):
    _run_migration_38(fresh_conn)
    _run_migration_38(fresh_conn)  # Darf keinen Fehler werfen


def test_migration_38_default_werte(fresh_conn):
    _run_migration_38(fresh_conn)
    fresh_conn.execute("INSERT INTO unfallakte (az) VALUES ('TEST/001')")
    row = fresh_conn.execute(
        "SELECT portal_aktiv, portal_sync_pending FROM unfallakte WHERE az = 'TEST/001'"
    ).fetchone()
    assert row["portal_aktiv"] == 0
    assert row["portal_sync_pending"] == 0
```

- [ ] **Step 1.2: Test ausführen – erwarte FAIL**

```bash
cd "C:\Users\HAL9000\Documents\Projekt\Version 1.00\unfallakten"
python -m pytest backend/tests/test_migration_38.py -v
```
Erwartetes Ergebnis: `ImportError: cannot import name '_run_migration_38'`

- [ ] **Step 1.3: Migration 38 in `schema_manager.py` eintragen**

Im `MIGRATIONS`-Dict, nach dem Eintrag für `37`:
```python
    38: "-- migration_38_portal_sync",  # Handled by _run_migration_38
```

Neue Funktion vor `create_schema()`:
```python
def _run_migration_38(conn: sqlite3.Connection) -> None:
    """Portal-Sync-Spalten + Hilfstabellen."""
    vorhanden_ua = {r[1] for r in conn.execute("PRAGMA table_info(unfallakte)").fetchall()}
    for spalte, typ in [
        ("portal_aktiv",        "INTEGER NOT NULL DEFAULT 0"),
        ("portal_sync_pending", "INTEGER NOT NULL DEFAULT 0"),
        ("portal_last_sync",    "TEXT"),
    ]:
        if spalte not in vorhanden_ua:
            conn.execute(f"ALTER TABLE unfallakte ADD COLUMN {spalte} {typ}")
            logger.info("unfallakte.%s hinzugefügt.", spalte)

    vorhanden_dok = {r[1] for r in conn.execute("PRAGMA table_info(dokumente)").fetchall()}
    if "portal_sichtbar" not in vorhanden_dok:
        conn.execute(
            "ALTER TABLE dokumente ADD COLUMN portal_sichtbar INTEGER NOT NULL DEFAULT 0"
        )
        logger.info("dokumente.portal_sichtbar hinzugefügt.")

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
            eingeladen_von INTEGER REFERENCES benutzer(id)
        )
    """)

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) VALUES (?, ?)",
        (38, "Migration 38 – portal_aktiv, portal_sync_pending, portal_sync_queue, portal_einladungen"),
    )
```

In `run_migrations()`, im elif-Block (nach dem letzten vorhandenen elif):
```python
            elif version == 38:
                _run_migration_38(conn)
```

- [ ] **Step 1.4: Tests ausführen – erwarte PASS**

```bash
python -m pytest backend/tests/test_migration_38.py -v
```
Erwartetes Ergebnis: 5 PASSED

- [ ] **Step 1.5: Commit**

```bash
git add backend/db/schema_manager.py backend/tests/test_migration_38.py
git commit -m "feat(portal): Migration 38 – portal_aktiv, portal_sync_queue, portal_einladungen"
```

---

## Task 2: `backend/services/portal_sync.py` – Ampel + Payload

**Files:**
- Create: `backend/services/portal_sync.py`
- Create: `backend/tests/test_portal_sync.py`

- [ ] **Step 2.1: Tests schreiben**

```python
# backend/tests/test_portal_sync.py
import sqlite3
import pytest
from unittest.mock import patch
from backend.services.portal_sync import (
    _berechne_ampel, _portal_flag, queue_sync, _build_payload, process_queue
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
```

- [ ] **Step 2.2: Test ausführen – erwarte FAIL**

```bash
python -m pytest backend/tests/test_portal_sync.py -v
```
Erwartetes Ergebnis: `ImportError: cannot import name '_berechne_ampel'`

- [ ] **Step 2.3: `backend/services/portal_sync.py` erstellen**

```python
"""
Portal-Sync-Service
====================
Berechnet Ampel-Status, baut JSON-Payload, verwaltet die Sync-Queue.

Aufruf:
  - flask sync-portal          (manuell / cron)
  - APScheduler alle 60s       (falls konfiguriert in app.py)
"""
import hashlib
import hmac as _hmac
import json
import logging
import os
import sqlite3
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

PORTAL_API_URL     = os.environ.get("PORTAL_API_URL", "")
PORTAL_API_KEY     = os.environ.get("PORTAL_API_KEY", "")
PORTAL_HMAC_SECRET = os.environ.get("PORTAL_HMAC_SECRET", "")


# ---------------------------------------------------------------------------
# Ampel-Berechnung (7 Stufen)
# ---------------------------------------------------------------------------

def _berechne_ampel(conn: sqlite3.Connection, akte_id: str) -> dict:
    """Gibt {'status': str, 'farbe': str} zurück."""
    akte = conn.execute(
        "SELECT status FROM unfallakte WHERE az = ?", (akte_id,)
    ).fetchone()
    if not akte:
        return {"status": "akte_eroeffnet", "farbe": "grau"}

    if akte["status"] == "klage":
        return {"status": "klage_eingereicht", "farbe": "rot"}

    sp = conn.execute("""
        SELECT COALESCE(
            reparaturkosten + wiederbeschaffung - restwert + wertminderung +
            nutzungsausfall + mietwagenkosten + sv_kosten + abschleppkosten +
            standkosten + anabmeldekosten + schmerzensgeld + sonstiges, 0.0
        ) AS gesamt
        FROM schadenpositionen WHERE akte_id = ?
    """, (akte_id,)).fetchone()
    gefordert = float(sp["gesamt"]) if sp else 0.0

    reg = conn.execute("""
        SELECT COALESCE(SUM(rp.betrag_reguliert), 0.0) AS reguliert
        FROM regulierung_positionen rp
        JOIN abrechnungsschreiben ab ON ab.id = rp.abrechnungsschreiben_id
        WHERE ab.akte_id = ?
    """, (akte_id,)).fetchone()
    reguliert = float(reg["reguliert"]) if reg else 0.0

    if akte["status"] == "abgeschlossen" and gefordert > 0 and reguliert >= gefordert * 0.95:
        return {"status": "vollreguliert", "farbe": "gruen"}

    if reguliert > 0 and gefordert > 0:
        return {"status": "teilreguliert", "farbe": "orange"}

    ab_count = conn.execute(
        "SELECT COUNT(*) AS n FROM abrechnungsschreiben WHERE akte_id = ?", (akte_id,)
    ).fetchone()["n"]
    if ab_count > 0:
        return {"status": "regulierung_laeuft", "farbe": "gelb"}

    sv = conn.execute("""
        SELECT COUNT(*) AS n FROM beteiligte
        WHERE akte_id = ? AND rolle = 'sachverstaendiger'
    """, (akte_id,)).fetchone()
    if sv["n"] > 0:
        return {"status": "gutachten_beauftragt", "farbe": "grau"}

    return {"status": "akte_eroeffnet", "farbe": "grau"}


# ---------------------------------------------------------------------------
# Queue-Verwaltung
# ---------------------------------------------------------------------------

def _portal_flag(conn: sqlite3.Connection, akte_id: str) -> None:
    """Markiert eine Akte für Portal-Sync – NUR wenn portal_aktiv = 1."""
    row = conn.execute(
        "SELECT portal_aktiv FROM unfallakte WHERE az = ?", (akte_id,)
    ).fetchone()
    if row and row["portal_aktiv"]:
        queue_sync(conn, akte_id)


def queue_sync(conn: sqlite3.Connection, akte_id: str) -> None:
    conn.execute(
        "UPDATE unfallakte SET portal_sync_pending = 1 WHERE az = ?", (akte_id,)
    )


# ---------------------------------------------------------------------------
# Payload-Builder
# ---------------------------------------------------------------------------

def _build_payload(conn: sqlite3.Connection, akte_id: str) -> dict:
    """Baut vollständigen JSON-Snapshot einer Akte. Kein IBAN, keine internen Notizen."""
    akte = conn.execute("""
        SELECT az, status, unfalldatum, haftungsquote, sachbearbeiter
        FROM unfallakte WHERE az = ?
    """, (akte_id,)).fetchone()
    if not akte:
        return {}

    last = conn.execute("""
        SELECT COALESCE(MAX(sync_version), 0) AS v
        FROM portal_sync_queue WHERE akte_id = ? AND status = 'confirmed'
    """, (akte_id,)).fetchone()
    sync_version = (last["v"] or 0) + 1

    ampel = _berechne_ampel(conn, akte_id)

    beteiligte = conn.execute("""
        SELECT id, rolle, name, vorname, firma, email
        FROM beteiligte WHERE akte_id = ?
    """, (akte_id,)).fetchall()

    sp = conn.execute("""
        SELECT reparaturkosten, wiederbeschaffung, restwert, wertminderung,
               nutzungsausfall, mietwagenkosten, sv_kosten, abschleppkosten,
               standkosten, anabmeldekosten, schmerzensgeld, sonstiges
        FROM schadenpositionen WHERE akte_id = ?
    """, (akte_id,)).fetchone()

    reg_pos = conn.execute("""
        SELECT rp.position_key,
               SUM(rp.betrag_reguliert) AS reguliert,
               MAX(ab.datum)            AS letztes_datum,
               MAX(ab.versicherung)     AS versicherung
        FROM regulierung_positionen rp
        JOIN abrechnungsschreiben ab ON ab.id = rp.abrechnungsschreiben_id
        WHERE ab.akte_id = ?
        GROUP BY rp.position_key
    """, (akte_id,)).fetchall()

    docs = conn.execute("""
        SELECT id, typ, dateiname, hochgeladen_am
        FROM dokumente WHERE akte_id = ? AND portal_sichtbar = 1
    """, (akte_id,)).fetchall()

    return {
        "sync_version": sync_version,
        "akte": {
            "az": akte["az"],
            "status": akte["status"],
            "unfalldatum": akte["unfalldatum"],
            "haftungsquote": akte["haftungsquote"],
            "sachbearbeiter": akte["sachbearbeiter"],
        },
        "beteiligte": [
            {"id": b["id"], "rolle": b["rolle"], "name": b["name"],
             "vorname": b["vorname"], "firma": b["firma"], "email": b["email"]}
            for b in beteiligte
        ],
        "schaden": dict(sp) if sp else {},
        "regulierung_positionen": [
            {"position_key": r["position_key"], "reguliert": r["reguliert"],
             "letztes_datum": r["letztes_datum"], "versicherung": r["versicherung"]}
            for r in reg_pos
        ],
        "dokumente": [
            {"id": d["id"], "typ": d["typ"], "dateiname": d["dateiname"],
             "erstellt_am": d["hochgeladen_am"]}
            for d in docs
        ],
        "ampel": ampel,
    }


# ---------------------------------------------------------------------------
# HTTP-Push
# ---------------------------------------------------------------------------

def _sign(payload_json: str) -> str:
    return _hmac.new(
        PORTAL_HMAC_SECRET.encode(), payload_json.encode(), hashlib.sha256
    ).hexdigest()


def _send_to_portal(payload: dict) -> bool:
    if not PORTAL_API_URL or not PORTAL_API_KEY:
        logger.debug("PORTAL_API_URL/KEY nicht konfiguriert – Sync übersprungen.")
        return False
    payload_json = json.dumps(payload, ensure_ascii=False, default=str)
    try:
        resp = requests.post(
            f"{PORTAL_API_URL}/api/sync/push",
            data=payload_json,
            headers={
                "Content-Type": "application/json",
                "X-Sync-API-Key": PORTAL_API_KEY,
                "X-Sync-Signature": _sign(payload_json),
            },
            timeout=30,
        )
        if resp.status_code != 200:
            logger.warning("Portal-Push %s: HTTP %s", payload.get("akte", {}).get("az"), resp.status_code)
        return resp.status_code == 200
    except Exception as exc:
        logger.error("Portal-Push fehlgeschlagen: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Queue-Verarbeitung
# ---------------------------------------------------------------------------

def process_queue(conn: sqlite3.Connection) -> int:
    """Verarbeitet bis zu 10 ausstehende Sync-Einträge. Gibt Anzahl Erfolge zurück."""
    pending = conn.execute("""
        SELECT az FROM unfallakte
        WHERE portal_sync_pending = 1 AND portal_aktiv = 1
        LIMIT 10
    """).fetchall()

    synced = 0
    for row in pending:
        akte_id = row["az"]
        payload = _build_payload(conn, akte_id)
        if not payload:
            continue

        sv = payload["sync_version"]
        conn.execute(
            "INSERT INTO portal_sync_queue (akte_id, sync_version, status) VALUES (?, ?, 'sending')",
            (akte_id, sv),
        )
        conn.commit()

        ok = _send_to_portal(payload)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if ok:
            conn.execute("""
                UPDATE portal_sync_queue SET status = 'confirmed', sent_at = ?
                WHERE akte_id = ? AND sync_version = ?
            """, (now, akte_id, sv))
            conn.execute("""
                UPDATE unfallakte SET portal_sync_pending = 0, portal_last_sync = ?
                WHERE az = ?
            """, (now, akte_id))
            synced += 1
        else:
            conn.execute("""
                UPDATE portal_sync_queue
                SET status = 'failed', retry_count = retry_count + 1, last_error = 'send_failed'
                WHERE akte_id = ? AND sync_version = ?
            """, (akte_id, sv))
        conn.commit()

    return synced
```

- [ ] **Step 2.4: Tests ausführen – erwarte PASS**

```bash
python -m pytest backend/tests/test_portal_sync.py -v
```
Erwartetes Ergebnis: 9 PASSED

- [ ] **Step 2.5: Commit**

```bash
git add backend/services/portal_sync.py backend/tests/test_portal_sync.py
git commit -m "feat(portal): portal_sync.py – Ampel, Payload-Builder, Queue-Verarbeitung"
```

---

## Task 3: `_portal_flag`-Hooks + Flask CLI-Command

**Files:**
- Modify: `backend/routers/akten_routes.py`
- Modify: `backend/routers/abrechnungsschreiben_routes.py`
- Modify: `backend/routers/dokumente_routes.py`
- Modify: `backend/app.py`

- [ ] **Step 3.1: Import in den drei Route-Dateien**

Füge jeweils nach den bestehenden Imports hinzu:
```python
from ..services.portal_sync import _portal_flag
```

- [ ] **Step 3.2: Hook in `akten_routes.py`**

Suche den PATCH-/PUT-Endpunkt, der `status` in `unfallakte` schreibt (Suche nach `UPDATE unfallakte SET` und `status`). Füge nach `conn.commit()` ein:
```python
_portal_flag(conn, az)
```
`az` ist dabei der normalisierte Aktenzeichen-String aus `_pruefe_akte()` (v14c-Pattern).

- [ ] **Step 3.3: Hook in `abrechnungsschreiben_routes.py`**

Suche den POST-Endpunkt für neue Abrechnungsschreiben (INSERT INTO abrechnungsschreiben). Füge nach `conn.commit()` ein:
```python
_portal_flag(conn, az)
```

- [ ] **Step 3.4: Hook + Endpoint in `dokumente_routes.py`**

**A) Upload-Endpunkt:** Nach `conn.commit()` beim Hochladen eines neuen Dokuments:
```python
_portal_flag(conn, az)
```

**B) Neuer Endpunkt für `portal_sichtbar` setzen** (füge am Ende des Blueprints ein):
```python
@dokumente_bp.route("/<az>/dokumente/<int:dok_id>/portal-sichtbar", methods=["PATCH"])
@jwt_required
def setze_portal_sichtbar(az: str, dok_id: int):
    akte_obj = _pruefe_akte(az)
    if not akte_obj:
        return _err("Akte nicht gefunden", 404)
    az = akte_obj.aktenzeichen if hasattr(akte_obj, "aktenzeichen") else az
    data = request.get_json(silent=True) or {}
    sichtbar = 1 if data.get("portal_sichtbar", False) else 0
    with get_connection() as conn:
        conn.execute(
            "UPDATE dokumente SET portal_sichtbar = ? WHERE id = ? AND akte_id = ?",
            (sichtbar, dok_id, az)
        )
        _portal_flag(conn, az)
    return jsonify({"status": "ok", "portal_sichtbar": bool(sichtbar)})
```

- [ ] **Step 3.5: Flask CLI-Command in `app.py`**

In `erstelle_app()`, nach der letzten Blueprint-Registrierung:
```python
from .services.portal_sync import process_queue as _portal_process_queue

@app.cli.command("sync-portal")
def sync_portal_cmd():
    """Pusht ausstehende Portal-Sync-Einträge (max 10 pro Aufruf)."""
    from .db.database import get_connection
    with get_connection() as conn:
        n = _portal_process_queue(conn)
        print(f"Portal-Sync: {n} Akte(n) synchronisiert.")
```

- [ ] **Step 3.6: Commit**

```bash
git add backend/routers/akten_routes.py backend/routers/abrechnungsschreiben_routes.py
git add backend/routers/dokumente_routes.py backend/app.py
git commit -m "feat(portal): _portal_flag Hooks in Routes + flask sync-portal CLI"
```

---

## Task 4: `backend/routers/portal_routes.py`

**Files:**
- Create: `backend/routers/portal_routes.py`
- Modify: `backend/app.py` (Blueprint registrieren)

- [ ] **Step 4.1: `portal_routes.py` erstellen**

```python
"""Portal-Admin-Routen: Akte aktivieren, Stakeholder einladen, Sync-Status."""
import logging
from flask import Blueprint, jsonify, request
from ..auth.middleware import jwt_required, admin_required
from ..db.database import get_connection
from ..services.portal_sync import queue_sync

portal_bp = Blueprint("portal", __name__, url_prefix="/portal")
logger = logging.getLogger(__name__)


def _err(msg: str, code: int = 400):
    return jsonify({"fehler": msg}), code


@portal_bp.route("/akten/<path:az>/aktivieren", methods=["POST"])
@jwt_required
@admin_required
def aktiviere_portal_fuer_akte(az: str):
    data = request.get_json(silent=True) or {}
    aktiv = 1 if data.get("aktiv", True) else 0
    with get_connection() as conn:
        row = conn.execute("SELECT az FROM unfallakte WHERE az = ?", (az,)).fetchone()
        if not row:
            return _err("Akte nicht gefunden", 404)
        conn.execute("UPDATE unfallakte SET portal_aktiv = ? WHERE az = ?", (aktiv, az))
        if aktiv:
            queue_sync(conn, az)
    return jsonify({"status": "ok", "portal_aktiv": bool(aktiv)})


@portal_bp.route("/akten/<path:az>/einladen", methods=["POST"])
@jwt_required
@admin_required
def einladen(az: str):
    data = request.get_json(silent=True) or {}
    beteiligter_id = data.get("beteiligter_id")
    email = (data.get("email") or "").strip()
    rolle = data.get("rolle", "")
    if not beteiligter_id or not email or rolle not in ("sachverstaendiger", "privatmandant"):
        return _err("beteiligter_id, email und rolle (sachverstaendiger|privatmandant) erforderlich")
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM beteiligte WHERE id = ? AND akte_id = ?", (beteiligter_id, az)
        ).fetchone()
        if not row:
            return _err("Beteiligter gehört nicht zu dieser Akte", 404)
        conn.execute("""
            INSERT INTO portal_einladungen (akte_id, beteiligter_id, email, rolle, status)
            VALUES (?, ?, ?, ?, 'ausstehend')
        """, (az, beteiligter_id, email, rolle))
    return jsonify({"status": "einladung_gespeichert"})


@portal_bp.route("/status", methods=["GET"])
@jwt_required
@admin_required
def sync_status():
    with get_connection() as conn:
        stats = conn.execute(
            "SELECT status, COUNT(*) AS n FROM portal_sync_queue GROUP BY status"
        ).fetchall()
        pending = conn.execute(
            "SELECT COUNT(*) AS n FROM unfallakte WHERE portal_sync_pending = 1"
        ).fetchone()["n"]
        aktiv = conn.execute(
            "SELECT COUNT(*) AS n FROM unfallakte WHERE portal_aktiv = 1"
        ).fetchone()["n"]
        letzte = conn.execute("""
            SELECT MAX(sent_at) AS letzte FROM portal_sync_queue WHERE status = 'confirmed'
        """).fetchone()["letzte"]
    return jsonify({
        "queue": {r["status"]: r["n"] for r in stats},
        "pending_akten": pending,
        "aktiv_akten": aktiv,
        "letzter_sync": letzte,
    })
```

- [ ] **Step 4.2: Blueprint in `app.py` registrieren**

In `erstelle_app()`, nach den anderen `register_blueprint`-Aufrufen:
```python
from .routers.portal_routes import portal_bp
app.register_blueprint(portal_bp)
```

- [ ] **Step 4.3: Manueller Test**

```bash
# Flask-Server laufen lassen, dann:
curl -X POST http://localhost:5000/portal/akten/TEST%2F001/aktivieren \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"aktiv": true}'
# Erwartetes Ergebnis: {"status": "ok", "portal_aktiv": true}

curl http://localhost:5000/portal/status \
  -H "Authorization: Bearer <token>"
# Erwartetes Ergebnis: {"queue": {}, "pending_akten": 1, "aktiv_akten": 1, "letzter_sync": null}
```

- [ ] **Step 4.4: Commit**

```bash
git add backend/routers/portal_routes.py backend/app.py
git commit -m "feat(portal): portal_routes.py – /portal/akten/:az/aktivieren, einladen, status"
```

---

## Task 5: Frontend – Portal-API + BeteiligteSection

**Files:**
- Modify: `frontend/src/api.js`
- Modify: `frontend/src/sections/BeteiligteSection.jsx`

- [ ] **Step 5.1: Portal-API-Funktionen in `api.js` hinzufügen**

Am Ende der Datei, nach den bestehenden Exporten:
```javascript
export const portalAkteAktivieren = (az, aktiv, token) =>
  authFetch(`/portal/akten/${encodeURIComponent(az)}/aktivieren`, token, {
    method: "POST",
    body: JSON.stringify({ aktiv }),
  });

export const portalEinladen = (az, data, token) =>
  authFetch(`/portal/akten/${encodeURIComponent(az)}/einladen`, token, {
    method: "POST",
    body: JSON.stringify(data),
  });

export const portalSyncStatus = (token) =>
  authFetch("/portal/status", token);

export const setzePortalSichtbar = (az, dokId, sichtbar, token) =>
  authFetch(`/akten/${encodeURIComponent(az)}/dokumente/${dokId}/portal-sichtbar`, token, {
    method: "PATCH",
    body: JSON.stringify({ portal_sichtbar: sichtbar }),
  });
```

- [ ] **Step 5.2: "Portal einladen"-Button in `BeteiligteSection.jsx`**

Import ergänzen:
```javascript
import { portalEinladen } from "../api";
```

Handler-Funktion im Komponenten-Body (vor dem return):
```javascript
const handlePortalEinladen = async (beteiligter) => {
  if (!beteiligter.email) {
    toast("Keine E-Mail-Adresse hinterlegt", "error");
    return;
  }
  try {
    await portalEinladen(az, {
      beteiligter_id: beteiligter.id,
      email: beteiligter.email,
      rolle: beteiligter.rolle,
    }, token);
    toast(`Einladung für ${beteiligter.name} gespeichert`, "success");
  } catch {
    toast("Einladung fehlgeschlagen", "error");
  }
};
```

Button-JSX in der Beteiligten-Karte/Zeile (nach Name/Rolle-Anzeige):
```jsx
{(b.rolle === "sachverstaendiger" || b.rolle === "privatmandant") && b.email && (
  <button
    className="text-xs px-2 py-1 rounded border border-blue-400 text-blue-600 hover:bg-blue-50 mt-1"
    onClick={() => handlePortalEinladen(b)}
  >
    Portal einladen
  </button>
)}
```

- [ ] **Step 5.3: Visueller Test im Browser**

Dev-Server starten, Akte mit SV-Beteiligtem und E-Mail öffnen → Button "Portal einladen" sichtbar → Klick → Toast "Einladung für ... gespeichert" erscheint.

- [ ] **Step 5.4: Commit**

```bash
git add frontend/src/api.js frontend/src/sections/BeteiligteSection.jsx
git commit -m "feat(portal): BeteiligteSection – Portal-Einladen-Button für SV + Mandant"
```

---

## Task 6: Frontend – `AkteDetailView.jsx` Portal-Toggle

**Files:**
- Modify: `frontend/src/components/AkteDetailView.jsx`

- [ ] **Step 6.1: Import ergänzen**

```javascript
import { portalAkteAktivieren } from "../api";
```

- [ ] **Step 6.2: Handler hinzufügen**

Im Komponenten-Body (neben anderen Handlern):
```javascript
const handlePortalToggle = async (aktiv) => {
  try {
    await portalAkteAktivieren(az, aktiv, token);
    dispatch({ type: "SET_AKTE", payload: { ...st.akte, portal_aktiv: aktiv ? 1 : 0 } });
    toast(aktiv ? "Portal aktiviert – Sync wird durchgeführt" : "Portal deaktiviert", "success");
  } catch {
    toast("Fehler beim Ändern des Portal-Status", "error");
  }
};
```

- [ ] **Step 6.3: Portal-Toggle-UI in den Akte-Header einfügen**

Im Akte-Header-Bereich, neben dem Status-Badge:
```jsx
{/* Portal-Sync */}
<div className="flex items-center gap-2 text-sm ml-4">
  <label className="flex items-center gap-1 cursor-pointer select-none">
    <input
      type="checkbox"
      checked={!!st.akte?.portal_aktiv}
      onChange={(e) => handlePortalToggle(e.target.checked)}
      className="w-4 h-4 accent-blue-600"
    />
    <span className="text-gray-600 text-xs">Portal</span>
  </label>
  {st.akte?.portal_last_sync && (
    <span className="text-xs text-gray-400">
      ↑ {new Date(st.akte.portal_last_sync).toLocaleString("de-DE", {
        day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit"
      })}
    </span>
  )}
</div>
```

- [ ] **Step 6.4: Visueller Test im Browser**

Portal-Toggle ein- und ausschalten → Toast erscheint → `GET /portal/status` zeigt korrekte Anzahl aktiver Akten.

- [ ] **Step 6.5: Commit**

```bash
git add frontend/src/components/AkteDetailView.jsx
git commit -m "feat(portal): AkteDetailView – Portal-aktiv Toggle + letzter Sync-Zeitstempel"
```

---

## Task 7: `backend/word/abschluss_summary.py`

**Files:**
- Create: `backend/word/abschluss_summary.py`
- Modify: `backend/routers/akten_routes.py` (Trigger)

- [ ] **Step 7.1: `abschluss_summary.py` erstellen**

```python
"""
Abschluss-Summary – "Das haben wir für Sie erreicht"
======================================================
Generiert ein DOCX bei Fallabschluss. Wird gespeichert als
dokumente.typ = 'sonstiges' mit portal_sichtbar = 1.
"""
import io
import logging
import sqlite3
from datetime import datetime, date

from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

logger = logging.getLogger(__name__)

_POSITIONEN_LABELS = {
    "reparaturkosten":   "Reparaturkosten",
    "wiederbeschaffung": "Wiederbeschaffungswert",
    "wertminderung":     "Wertminderung",
    "nutzungsausfall":   "Nutzungsausfall",
    "mietwagenkosten":   "Mietwagenkosten",
    "sv_kosten":         "Sachverständigenkosten",
    "abschleppkosten":   "Abschleppkosten",
    "standkosten":       "Standkosten",
    "schmerzensgeld":    "Schmerzensgeld",
    "sonstiges":         "Sonstige Kosten",
}


def _fmt_euro(betrag) -> str:
    if betrag is None:
        return "–"
    return f"{float(betrag):,.2f}\u00a0€".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_datum(iso_str: str) -> str:
    if not iso_str:
        return "–"
    try:
        return datetime.strptime(iso_str[:10], "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return iso_str


def generiere_abschluss_summary(conn: sqlite3.Connection, akte_id: str) -> bytes:
    """Erstellt das DOCX als Bytes. Caller speichert auf Disk und in dokumente-Tabelle."""
    akte = conn.execute(
        "SELECT az, unfalldatum, status, haftungsquote, erstellt_am FROM unfallakte WHERE az = ?",
        (akte_id,)
    ).fetchone()
    if not akte:
        raise ValueError(f"Akte {akte_id!r} nicht gefunden")

    mandant = conn.execute(
        "SELECT name, vorname FROM beteiligte WHERE akte_id = ? AND rolle = 'mandant' LIMIT 1",
        (akte_id,)
    ).fetchone()

    sp = conn.execute(
        "SELECT * FROM schadenpositionen WHERE akte_id = ?", (akte_id,)
    ).fetchone()

    reg_gesamt = conn.execute("""
        SELECT COALESCE(SUM(rp.betrag_reguliert), 0.0) AS total
        FROM regulierung_positionen rp
        JOIN abrechnungsschreiben ab ON ab.id = rp.abrechnungsschreiben_id
        WHERE ab.akte_id = ?
    """, (akte_id,)).fetchone()

    reg_per_pos = {
        r["position_key"]: float(r["reguliert"])
        for r in conn.execute("""
            SELECT rp.position_key, SUM(rp.betrag_reguliert) AS reguliert
            FROM regulierung_positionen rp
            JOIN abrechnungsschreiben ab ON ab.id = rp.abrechnungsschreiben_id
            WHERE ab.akte_id = ?
            GROUP BY rp.position_key
        """, (akte_id,)).fetchall()
    }

    # Verfahrensdauer
    heute = date.today()
    try:
        mandats_start = date.fromisoformat((akte["erstellt_am"] or "")[:10])
        dauer = (heute - mandats_start).days
    except ValueError:
        dauer = 0

    gesamt_gefordert = 0.0
    if sp:
        gesamt_gefordert = float(sum(
            sp[k] or 0.0
            for k in ("reparaturkosten", "wiederbeschaffung", "wertminderung",
                      "nutzungsausfall", "mietwagenkosten", "sv_kosten",
                      "abschleppkosten", "standkosten", "schmerzensgeld", "sonstiges")
        ) - float(sp["restwert"] or 0.0))

    gesamt_reguliert = float(reg_gesamt["total"]) if reg_gesamt else 0.0
    quote = (gesamt_reguliert / gesamt_gefordert * 100) if gesamt_gefordert > 0 else 0.0

    # DOCX aufbauen
    doc = Document()

    h = doc.add_heading("Abschluss-Summary", 0)
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_heading("Kanzlei Koch, Schatz & Kollegen", 1)

    mandant_name = "Ihr Mandant"
    if mandant:
        mandant_name = f"{(mandant['vorname'] or '').strip()} {(mandant['name'] or '').strip()}".strip()

    for label, wert in [
        ("Mandant", mandant_name),
        ("Aktenzeichen", akte["az"]),
        ("Unfalldatum", _fmt_datum(akte["unfalldatum"])),
        ("Verfahrensdauer", f"{dauer} Tage"),
    ]:
        p = doc.add_paragraph()
        p.add_run(f"{label}: ").bold = True
        p.add_run(wert)

    doc.add_heading("Das haben wir für Sie erreicht", 2)

    table = doc.add_table(rows=1, cols=3)
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    for i, txt in enumerate(("Position", "Gefordert", "Erhalten")):
        r = hdr[i].paragraphs[0].add_run(txt)
        r.bold = True

    for key, label in _POSITIONEN_LABELS.items():
        if not sp:
            continue
        gef = float(sp[key] or 0.0)
        if key == "wiederbeschaffung":
            gef = max(0.0, gef - float(sp["restwert"] or 0.0))
        if gef <= 0:
            continue
        row_cells = table.add_row().cells
        row_cells[0].text = label
        row_cells[1].text = _fmt_euro(gef)
        row_cells[2].text = _fmt_euro(reg_per_pos.get(key, 0.0))

    total_row = table.add_row().cells
    total_row[0].paragraphs[0].add_run("GESAMT").bold = True
    total_row[1].paragraphs[0].add_run(_fmt_euro(gesamt_gefordert)).bold = True
    total_row[2].paragraphs[0].add_run(_fmt_euro(gesamt_reguliert)).bold = True

    doc.add_paragraph()
    result_para = doc.add_paragraph()
    run = result_para.add_run(
        f"Wir konnten {_fmt_euro(gesamt_reguliert)} ({quote:.0f}\u00a0% Ihrer Forderung) für Sie durchsetzen."
    )
    run.bold = True
    run.font.size = Pt(13)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
```

- [ ] **Step 7.2: Trigger in `akten_routes.py` – bei status → abgeschlossen**

Suche den Endpunkt, der `status` in `unfallakte` auf `'abgeschlossen'` setzt. Füge nach dem `conn.commit()` ein:

```python
if neuer_status == "abgeschlossen":
    _erzeuge_abschluss_summary(az)
```

Neue Helper-Funktion (am Ende der Datei oder im Blueprint-Modul):
```python
def _erzeuge_abschluss_summary(az: str) -> None:
    """Generiert Abschluss-Summary und speichert sie in dokumente."""
    import hashlib
    import os
    from ..word.abschluss_summary import generiere_abschluss_summary
    from ..db.database import get_connection as _gc

    try:
        with _gc() as conn:
            docx_bytes = generiere_abschluss_summary(conn, az)
            uploads_dir = os.path.join(
                os.path.dirname(__file__), "..", "..", "uploads",
                az.replace("/", "_")
            )
            os.makedirs(uploads_dir, exist_ok=True)
            fname = f"abschluss_summary_{az.replace('/', '_')}.docx"
            fpath = os.path.join(uploads_dir, fname)
            with open(fpath, "wb") as fh:
                fh.write(docx_bytes)
            pdf_hash = hashlib.sha256(docx_bytes).hexdigest()
            existing = conn.execute(
                "SELECT id FROM dokumente WHERE akte_id = ? AND pdf_hash = ?", (az, pdf_hash)
            ).fetchone()
            if not existing:
                rel_path = os.path.join(az.replace("/", "_"), fname)
                conn.execute("""
                    INSERT INTO dokumente
                        (akte_id, typ, dateiname, dateipfad, dateityp, dateigroesse,
                         pdf_hash, portal_sichtbar)
                    VALUES (?, 'sonstiges', ?, ?, 'docx', ?, ?, 1)
                """, (az, fname, rel_path, len(docx_bytes), pdf_hash))
            from ..services.portal_sync import _portal_flag
            _portal_flag(conn, az)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error("Abschluss-Summary für %s fehlgeschlagen: %s", az, exc)
```

- [ ] **Step 7.3: Test im Browser**

Eine Testakte auf Status "abgeschlossen" setzen → in `uploads/<az_ohne_slash>/` erscheint `abschluss_summary_*.docx` → in der Dokumenten-Ansicht der Akte ist das neue Dokument (typ='sonstiges') sichtbar.

- [ ] **Step 7.4: Commit**

```bash
git add backend/word/abschluss_summary.py backend/routers/akten_routes.py
git commit -m "feat(portal): Abschluss-Summary DOCX + Auto-Trigger bei status=abgeschlossen"
```

---

## Task 8: `.env.example` + Gesamtverifikation

**Files:**
- Modify: `.env.example`

- [ ] **Step 8.1: Portal-Env-Vars dokumentieren**

```bash
# Portal-Sync (Workstream B – Stakeholder-Portal)
PORTAL_API_URL=https://portal.anwalt-offenbach.de
PORTAL_API_KEY=your-portal-api-key-here
PORTAL_HMAC_SECRET=your-hmac-secret-at-least-32-chars
```

- [ ] **Step 8.2: Alle Tests ausführen**

```bash
python -m pytest backend/tests/ -v --tb=short
```
Erwartetes Ergebnis: Alle Tests PASS, keine Regressions.

- [ ] **Step 8.3: End-to-End Smoke-Test**

1. App starten
2. Akte öffnen → Portal-Toggle sichtbar ✓
3. Toggle einschalten → Toast "Portal aktiviert" ✓
4. Beteiligten-Tab → SV mit E-Mail → "Portal einladen"-Button ✓
5. `GET /portal/status` → `{"aktiv_akten": 1, "pending_akten": 1}` ✓
6. `flask sync-portal` → "Portal-Sync: 0 Akte(n) synchronisiert." (PORTAL_API_URL leer → ok) ✓
7. Akte → Status "abgeschlossen" → DOCX in uploads/ ✓

- [ ] **Step 8.4: Final Commit**

```bash
git add .env.example
git commit -m "docs(portal): .env.example um PORTAL_API_* Variablen ergänzt"
```

---

## Verifikationscheckliste (Workstream A vollständig)

| Check | Kriterium |
|---|---|
| Migration 38 | `portal_aktiv`, `portal_sync_pending`, `portal_sync_queue`, `portal_einladungen` in DB ✓ |
| portal_sync.py | 7 Ampel-Stufen korrekt berechnet (Tests grün) ✓ |
| Hooks | Statusänderung → `portal_sync_pending = 1` (wenn portal_aktiv) ✓ |
| Admin-API | `/portal/akten/<az>/aktivieren` und `/portal/status` erreichbar ✓ |
| Frontend | Portal-Toggle und Einladen-Button sichtbar und funktional ✓ |
| Abschluss-Summary | DOCX generiert und in `dokumente` mit `portal_sichtbar=1` ✓ |
| Alle Tests | `pytest backend/tests/` komplett grün ✓ |
