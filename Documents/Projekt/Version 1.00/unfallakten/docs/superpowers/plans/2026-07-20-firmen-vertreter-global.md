# Globaler Firmen-Vertreter-Speicher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Vertreter (Organe) einer Firma zentral je Firmenname persistieren, damit RA-MICRO-/synthetische-GHPV-Beklagte (ohne SQLite-`beteiligte`-Zeile) ihren Vertreter über Reload und aktenübergreifend behalten.

**Architecture:** Neue SQLite-Tabelle `firmen_vertreter` (Key = normalisierter Firmenname). Ein SSOT-Modul `models/firmen_vertreter.py` kapselt Normalisierung + Upsert + Lookup und wird von **beiden** Seiten benutzt — Schreibweg (`firmen_routes.speichern`) und Leseweg (`klage_routes` Serializer) — damit die Normalisierung garantiert identisch ist. Beim Aufbau der Beklagten wird der globale Vertreter nachgeschlagen, wenn der Beteiligte selbst keinen `vertreter_name` trägt (direkter Wert am Beteiligten hat Vorrang → abwärtskompatibel).

**Tech Stack:** Python 3 / Flask / sqlite3 (Backend), React + Vitest (Frontend). Migrationsmechanik: `backend/db/schema_manager.py` (die **aktive** Datei; `backend/schema_manager.py` ist eine tote Altkopie, NICHT anfassen).

## Global Constraints

- **RA-MICRO ist read-only** — geschrieben wird ausschließlich in SQLite (`firmen_vertreter`, ggf. `beteiligte`).
- **Migrationen:** kein `executescript()` für die neue Migration; explizites `conn.commit()` vor **und** nach dem DDL; die komplette Migration in **einem** Edit schreiben (Flask-Reloader-Falle). Muster exakt wie `_run_migration_61` (`backend/db/schema_manager.py:1049`).
- **Aktive DB** = Docker-Volume `dev-data` unter `/app/data/unfallakten.db`, nicht `backend/data/`. Tests laufen gegen frische Temp-DBs via `DB_PATH`.
- **Normalisierung konservativ:** nur `lower()` + Whitespace-Kollaps. **Rechtsform NICHT strippen** (sonst fallen verschiedene Gesellschaften eines Konzerns zusammen). Keine Interpunktions-Entfernung.
- **KEIN Auto-Apply** von Web-Lookups — der globale Speicher wird nur beim expliziten „Übernehmen" gefüllt. Diese Änderung ändert daran nichts.
- **Lookup-Schlüssel = `firma` bzw. `name`, NUR bei Organisationen (leerer `vorname`); NIEMALS `versicherung`.** Grund: `klage_routes.py:987-988` schreibt per WDM-Anreicherung `versicherung` auf **jeden** natürlichen-Personen-Beklagten (Fahrer/Halter) — ein Lookup über `versicherung` würde jedem Fahrer den Vorstand seines Haftpflichtversicherers als eigenen Vertreter unterschieben.
- **Keine Kommentare im Code außer bei nicht-offensichtlichem Verhalten** (Projektregel).
- Kommunikation/Doku auf Deutsch.

---

## File Structure

- **Create** `backend/models/firmen_vertreter.py` — SSOT: `firma_norm()`, `upsert_firmen_vertreter()`, `hole_firmen_vertreter()`.
- **Modify** `backend/db/schema_manager.py` — Migration 62 (Tabelle `firmen_vertreter`): Registry-Eintrag + `elif`-Dispatch + Handler `_run_migration_62`.
- **Modify** `backend/routers/firmen_routes.py` — `speichern()` akzeptiert zusätzlich `firma`, Upsert global.
- **Modify** `backend/routers/klage_routes.py` — finaler Global-Lookup-Pass über `alle_bet` (nach dem synthetischen GHPV-Append, innerhalb des `with get_connection() as conn`-Blocks).
- **Modify** `frontend/src/api.js` — `vertreterSpeichern(id, name, funk, firma)`.
- **Modify** `frontend/src/sections/KlageSection.jsx` — `VertreterModal` übergibt den Firmennamen als `firma` (Shadowing des `name`-Params in `onSave` auflösen).
- **Create** Tests: `backend/tests/test_migration_62.py`, `backend/tests/test_firmen_vertreter_model.py`, `backend/tests/test_firmen_vertreter_speichern.py`, `backend/tests/test_klage_firmen_vertreter_global.py`, `frontend/src/api.vertreterSpeichern.test.js`.

---

## Task 1: Migration 62 — Tabelle `firmen_vertreter`

**Files:**
- Modify: `backend/db/schema_manager.py` (Registry `MIGRATIONS` bei `:315`, Dispatch bei `:1493`, neuer Handler nahe `:1076`)
- Test: `backend/tests/test_migration_62.py`

**Interfaces:**
- Produces: Tabelle `firmen_vertreter(firma_norm TEXT PRIMARY KEY, firma_anzeige TEXT, vertreter_name TEXT NOT NULL, vertreter_funktion TEXT, aktualisiert_am TEXT)`; Funktion `_run_migration_62(conn)`; `schema_version >= 62`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_migration_62.py`:

```python
import importlib
import os
import sys
import tempfile
import unittest

_tmp = tempfile.mkdtemp(prefix="mig62_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _fresh_db(name):
    db_path = os.path.join(_tmp, f"{name}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    import backend.db.database as db_mod
    import backend.db.schema_manager as sm
    importlib.reload(db_mod)
    importlib.reload(sm)
    sm.init_db()
    return sm, db_mod


class TestMigration62(unittest.TestCase):
    def test_tabelle_vorhanden_nach_init(self):
        sm, db_mod = _fresh_db("vorhanden")
        with db_mod.get_connection() as conn:
            spalten = {r[1] for r in conn.execute(
                "PRAGMA table_info(firmen_vertreter)").fetchall()}
            version = conn.execute(
                "SELECT MAX(version) FROM schema_version").fetchone()[0]
        self.assertEqual(
            spalten,
            {"firma_norm", "firma_anzeige", "vertreter_name",
             "vertreter_funktion", "aktualisiert_am"})
        self.assertGreaterEqual(version, 62)

    def test_firma_norm_ist_primary_key(self):
        sm, db_mod = _fresh_db("pk")
        import sqlite3
        with db_mod.get_connection() as conn:
            conn.execute(
                "INSERT INTO firmen_vertreter "
                "(firma_norm, firma_anzeige, vertreter_name) "
                "VALUES ('adac autoversicherung ag', 'ADAC Autoversicherung AG', 'X')")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO firmen_vertreter "
                    "(firma_norm, firma_anzeige, vertreter_name) "
                    "VALUES ('adac autoversicherung ag', 'ADAC', 'Y')")

    def test_migration_zieht_fehlende_tabelle_nach(self):
        sm, db_mod = _fresh_db("nachziehen")
        with db_mod.get_connection() as conn:
            conn.execute("DROP TABLE firmen_vertreter")
            conn.commit()
            sm._run_migration_62(conn)
            spalten = {r[1] for r in conn.execute(
                "PRAGMA table_info(firmen_vertreter)").fetchall()}
        self.assertIn("vertreter_name", spalten)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_migration_62.py -v`
Expected: FAIL — `firmen_vertreter` existiert nicht bzw. `_run_migration_62` undefined.

- [ ] **Step 3a: Register migration 62 in the `MIGRATIONS` dict**

In `backend/db/schema_manager.py`, direkt nach der Zeile `61: "-- migration_61_klage_entwurf", ...` (`:315`), vor der schließenden `}`:

```python
    62: "-- migration_62_firmen_vertreter",  # Handled by _run_migration_62 (globaler Firmen-Vertreter-Speicher)
```

- [ ] **Step 3b: Add the dispatch branch**

In `run_migrations()`, nach `elif version == 61: _run_migration_61(conn)` (`:1492`):

```python
            elif version == 62:
                _run_migration_62(conn)
```

- [ ] **Step 3c: Add the handler**

Direkt nach `_run_migration_61` (nach dessen `logger.info(...)`-Zeile, ~`:1076`):

```python
def _run_migration_62(conn: sqlite3.Connection) -> None:
    """
    Migration 62 - Neue Tabelle firmen_vertreter (globaler Firmen-Vertreter-Speicher).

    Vertreter (Organe) je Firmenname zentral, damit RA-MICRO-/synthetische
    Beklagte ohne beteiligte-Zeile ihren Vertreter aktenuebergreifend behalten.
    firma_norm = lower + Whitespace-Kollaps (Rechtsform NICHT gestrippt). Kein
    executescript, explizite Commits um DDL (Reloader-Falle).
    """
    conn.commit()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS firmen_vertreter (
            firma_norm         TEXT PRIMARY KEY,
            firma_anzeige      TEXT,
            vertreter_name     TEXT NOT NULL,
            vertreter_funktion TEXT,
            aktualisiert_am    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.commit()
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (?, ?)",
        (62, "Migration 62 - Tabelle firmen_vertreter (globaler Vertreter-Speicher)"),
    )
    logger.info("Migration 62 abgeschlossen (Tabelle firmen_vertreter).")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_migration_62.py -v`
Expected: PASS (3 Tests).

- [ ] **Step 5: Commit**

```bash
git add backend/db/schema_manager.py backend/tests/test_migration_62.py
git commit -m "feat(db): Migration 62 - Tabelle firmen_vertreter (globaler Vertreter-Speicher)"
```

---

## Task 2: SSOT-Modul `models/firmen_vertreter.py`

**Files:**
- Create: `backend/models/firmen_vertreter.py`
- Test: `backend/tests/test_firmen_vertreter_model.py`

**Interfaces:**
- Consumes: Tabelle `firmen_vertreter` (Task 1).
- Produces:
  - `firma_norm(firma: str) -> str` — `lower()` + Whitespace-Kollaps; leerer/None-Input → `""`.
  - `upsert_firmen_vertreter(conn, firma_anzeige: str, vertreter_name: str, vertreter_funktion: str = "") -> bool` — UPSERT auf `firma_norm(firma_anzeige)`; `False` wenn Firma oder Name leer, sonst `True`. Committet nicht selbst (Aufrufer im `with`-Block).
  - `hole_firmen_vertreter(conn, firma: str) -> dict | None` — `{"vertreter_name", "vertreter_funktion"}` oder `None`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_firmen_vertreter_model.py`:

```python
import importlib
import os
import sys
import tempfile
import unittest

_tmp = tempfile.mkdtemp(prefix="fvmodel_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _fresh_db(name):
    db_path = os.path.join(_tmp, f"{name}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    import backend.db.database as db_mod
    import backend.db.schema_manager as sm
    importlib.reload(db_mod)
    importlib.reload(sm)
    sm.init_db()
    return db_mod


class TestFirmaNorm(unittest.TestCase):
    def test_lower_und_whitespace_kollaps(self):
        from backend.models.firmen_vertreter import firma_norm
        self.assertEqual(
            firma_norm("  ADAC   Autoversicherung  AG "),
            "adac autoversicherung ag")

    def test_leer_und_none(self):
        from backend.models.firmen_vertreter import firma_norm
        self.assertEqual(firma_norm(""), "")
        self.assertEqual(firma_norm(None), "")

    def test_rechtsform_bleibt_erhalten(self):
        from backend.models.firmen_vertreter import firma_norm
        self.assertNotEqual(firma_norm("Muster GmbH"), firma_norm("Muster AG"))


class TestUpsertUndLookup(unittest.TestCase):
    def test_roundtrip(self):
        db_mod = _fresh_db("roundtrip")
        from backend.models.firmen_vertreter import (
            upsert_firmen_vertreter, hole_firmen_vertreter)
        with db_mod.get_connection() as conn:
            ok = upsert_firmen_vertreter(
                conn, "ADAC Autoversicherung AG", "Stefan Daehne", "Vorstand")
            self.assertTrue(ok)
            treffer = hole_firmen_vertreter(conn, "  adac   autoversicherung ag ")
        self.assertEqual(
            treffer,
            {"vertreter_name": "Stefan Daehne", "vertreter_funktion": "Vorstand"})

    def test_upsert_aktualisiert_bestehenden(self):
        db_mod = _fresh_db("update")
        from backend.models.firmen_vertreter import (
            upsert_firmen_vertreter, hole_firmen_vertreter)
        with db_mod.get_connection() as conn:
            upsert_firmen_vertreter(conn, "Muster AG", "Alt Name", "Vorstand")
            upsert_firmen_vertreter(conn, "Muster AG", "Neu Name", "Vorstand")
            treffer = hole_firmen_vertreter(conn, "Muster AG")
            anzahl = conn.execute(
                "SELECT COUNT(*) FROM firmen_vertreter").fetchone()[0]
        self.assertEqual(treffer["vertreter_name"], "Neu Name")
        self.assertEqual(anzahl, 1)

    def test_leerer_name_wird_abgelehnt(self):
        db_mod = _fresh_db("leername")
        from backend.models.firmen_vertreter import (
            upsert_firmen_vertreter, hole_firmen_vertreter)
        with db_mod.get_connection() as conn:
            self.assertFalse(upsert_firmen_vertreter(conn, "Muster AG", "  "))
            self.assertIsNone(hole_firmen_vertreter(conn, "Muster AG"))

    def test_lookup_ohne_treffer(self):
        db_mod = _fresh_db("kein_treffer")
        from backend.models.firmen_vertreter import hole_firmen_vertreter
        with db_mod.get_connection() as conn:
            self.assertIsNone(hole_firmen_vertreter(conn, "Unbekannt GmbH"))
            self.assertIsNone(hole_firmen_vertreter(conn, ""))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_firmen_vertreter_model.py -v`
Expected: FAIL — `ModuleNotFoundError: backend.models.firmen_vertreter`.

- [ ] **Step 3: Write minimal implementation**

Create `backend/models/firmen_vertreter.py`:

```python
"""Single Source of Truth: globaler Firmen-Vertreter-Speicher.

Normalisierung, Upsert und Lookup fuer die Tabelle firmen_vertreter. Schreib-
weg (firmen_routes) und Leseweg (klage_routes-Serializer) nutzen dieselben
Funktionen, damit der normalisierte Schluessel garantiert identisch ist.
"""
import re


def firma_norm(firma) -> str:
    return re.sub(r"\s+", " ", (firma or "").strip().lower())


def upsert_firmen_vertreter(conn, firma_anzeige, vertreter_name,
                            vertreter_funktion="") -> bool:
    key = firma_norm(firma_anzeige)
    name = (vertreter_name or "").strip()
    if not key or not name:
        return False
    conn.execute(
        """INSERT INTO firmen_vertreter
               (firma_norm, firma_anzeige, vertreter_name, vertreter_funktion,
                aktualisiert_am)
           VALUES (?, ?, ?, ?, datetime('now','localtime'))
           ON CONFLICT(firma_norm) DO UPDATE SET
               firma_anzeige      = excluded.firma_anzeige,
               vertreter_name     = excluded.vertreter_name,
               vertreter_funktion = excluded.vertreter_funktion,
               aktualisiert_am    = excluded.aktualisiert_am""",
        (key, (firma_anzeige or "").strip(), name,
         (vertreter_funktion or "").strip()),
    )
    return True


def hole_firmen_vertreter(conn, firma):
    key = firma_norm(firma)
    if not key:
        return None
    row = conn.execute(
        "SELECT vertreter_name, vertreter_funktion "
        "FROM firmen_vertreter WHERE firma_norm = ?",
        (key,),
    ).fetchone()
    if not row:
        return None
    return {
        "vertreter_name": row["vertreter_name"] or "",
        "vertreter_funktion": row["vertreter_funktion"] or "",
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_firmen_vertreter_model.py -v`
Expected: PASS (7 Tests).

- [ ] **Step 5: Commit**

```bash
git add backend/models/firmen_vertreter.py backend/tests/test_firmen_vertreter_model.py
git commit -m "feat(models): SSOT firmen_vertreter (firma_norm/upsert/hole)"
```

---

## Task 3: Endpoint `speichern` akzeptiert `firma` (globaler Upsert)

**Files:**
- Modify: `backend/routers/firmen_routes.py:379-402` (`speichern()`)
- Test: `backend/tests/test_firmen_vertreter_speichern.py`

**Interfaces:**
- Consumes: `upsert_firmen_vertreter` (Task 2).
- Produces: `POST /firmen/vertreter/speichern` akzeptiert Body `{beteiligter_id?, firma?, vertreter_name, vertreter_funktion?}`. Regeln: `vertreter_name` Pflicht; mindestens **eins** von `firma` oder echter `beteiligter_id` (int > 0) muss gesetzt sein. Bei `firma` → globaler Upsert. Bei echter `beteiligter_id` → zusätzlich `UPDATE beteiligte`. Antwort enthält `{ok, global_gespeichert: bool, beteiligter_gespeichert: bool}`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_firmen_vertreter_speichern.py`:

```python
import importlib
import os
import sys
import tempfile
import unittest

_tmp = tempfile.mkdtemp(prefix="fvspeichern_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _fresh_app(name):
    db_path = os.path.join(_tmp, f"{name}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    import backend.db.database as db_mod
    import backend.db.schema_manager as sm
    importlib.reload(db_mod)
    importlib.reload(sm)
    sm.init_db()
    from flask import Flask
    import backend.routers.firmen_routes as fr
    importlib.reload(fr)
    app = Flask(__name__)
    app.register_blueprint(fr.firmen_bp)
    return app.test_client(), db_mod


class TestSpeichernGlobal(unittest.TestCase):
    def test_firma_ohne_beteiligter_wird_global_gespeichert(self):
        client, db_mod = _fresh_app("global_only")
        r = client.post("/firmen/vertreter/speichern", json={
            "beteiligter_id": -1,
            "firma": "ADAC Autoversicherung AG",
            "vertreter_name": "Stefan Daehne",
            "vertreter_funktion": "Vorstand",
        })
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["global_gespeichert"])
        with db_mod.get_connection() as conn:
            row = conn.execute(
                "SELECT vertreter_name FROM firmen_vertreter "
                "WHERE firma_norm = 'adac autoversicherung ag'").fetchone()
        self.assertEqual(row["vertreter_name"], "Stefan Daehne")

    def test_echter_beteiligter_wird_zusaetzlich_aktualisiert(self):
        client, db_mod = _fresh_app("mit_beteiligter")
        with db_mod.get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('1/26', '2026-01-01', 'offen')")
            conn.execute(
                "INSERT INTO beteiligte (id, akte_id, rolle, name, firma) "
                "VALUES (77, '1/26', 'gegner', '', 'Muster GmbH')")
        r = client.post("/firmen/vertreter/speichern", json={
            "beteiligter_id": 77,
            "firma": "Muster GmbH",
            "vertreter_name": "Erika Muster",
            "vertreter_funktion": "Geschaeftsfuehrer",
        })
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertTrue(body["global_gespeichert"])
        self.assertTrue(body["beteiligter_gespeichert"])
        with db_mod.get_connection() as conn:
            row = conn.execute(
                "SELECT vertreter_name FROM beteiligte WHERE id = 77").fetchone()
        self.assertEqual(row["vertreter_name"], "Erika Muster")

    def test_ohne_firma_und_ohne_beteiligter_fehler(self):
        client, _ = _fresh_app("kein_ziel")
        r = client.post("/firmen/vertreter/speichern", json={
            "vertreter_name": "X",
        })
        self.assertEqual(r.status_code, 400)

    def test_leerer_vertreter_name_fehler(self):
        client, _ = _fresh_app("leer_name")
        r = client.post("/firmen/vertreter/speichern", json={
            "firma": "Muster AG", "vertreter_name": "  ",
        })
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_firmen_vertreter_speichern.py -v`
Expected: FAIL — aktueller Endpoint verlangt `beteiligter_id` und kennt `global_gespeichert` nicht.

- [ ] **Step 3: Replace the `speichern()` body**

In `backend/routers/firmen_routes.py`, ersetze die Funktion `speichern()` (`:379-402`) vollständig durch:

```python
@firmen_bp.route("/vertreter/speichern", methods=["POST"])
def speichern():
    daten = request.get_json(silent=True) or {}
    bid   = daten.get("beteiligter_id")
    firma = (daten.get("firma") or "").strip()
    vname = (daten.get("vertreter_name") or "").strip()
    vfunk = (daten.get("vertreter_funktion") or "").strip()

    try:
        bid_int = int(bid)
    except (TypeError, ValueError):
        bid_int = 0
    hat_echten_beteiligten = bid_int > 0

    if not vname:
        return _err("vertreter_name erforderlich.")
    if not firma and not hat_echten_beteiligten:
        return _err("firma oder beteiligter_id erforderlich.")

    try:
        from ..db.database import get_connection
        from ..models.firmen_vertreter import upsert_firmen_vertreter
        global_ok = False
        bet_ok = False
        with get_connection() as conn:
            if firma:
                global_ok = upsert_firmen_vertreter(conn, firma, vname, vfunk)
            if hat_echten_beteiligten:
                cur = conn.execute(
                    "UPDATE beteiligte SET vertreter_name=?, "
                    "vertreter_funktion=? WHERE id=?",
                    (vname, vfunk, bid_int),
                )
                bet_ok = cur.rowcount > 0
        return _j({"ok": True,
                   "global_gespeichert": global_ok,
                   "beteiligter_gespeichert": bet_ok,
                   "vertreter_name": vname,
                   "vertreter_funktion": vfunk})
    except Exception as e:
        logger.error("Vertreter speichern: %s", e)
        return _err("Speichern fehlgeschlagen: " + str(e), 500)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_firmen_vertreter_speichern.py -v`
Expected: PASS (4 Tests).

- [ ] **Step 5: Commit**

```bash
git add backend/routers/firmen_routes.py backend/tests/test_firmen_vertreter_speichern.py
git commit -m "feat(firmen): speichern akzeptiert firma -> globaler Vertreter-Upsert"
```

---

## Task 4: Global-Lookup-Pass im Klage-Serializer

**Files:**
- Modify: `backend/routers/klage_routes.py` — neuer Pass direkt nach dem synthetischen GHPV-Append (nach `:1025`, vor `# ── Verzugsdatum bestimmen ──` `:1027`), innerhalb des `with get_connection() as conn`-Blocks (offen ab `:608`).
- Test: `backend/tests/test_klage_firmen_vertreter_global.py`

**Interfaces:**
- Consumes: `hole_firmen_vertreter` (Task 2); `conn` aus `hole_klage_daten`; `alle_bet` (Liste Beklagten-/Kläger-Dicts, inkl. synthetischem GHPV mit `id=-1`).
- Produces: Jeder Beklagte mit leerem `vertreter_name`, leerem `vorname` (= Organisation) und nichtleerem `firma`/`name` erhält `vertreter_name`/`vertreter_funktion` aus `firmen_vertreter`. Direkt am Beteiligten gesetzter `vertreter_name` bleibt unberührt (Vorrang).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_klage_firmen_vertreter_global.py`. Der Test ruft die reine Pass-Logik als Helper `_wende_globalen_vertreter_an(conn, alle_bet)` — diese Funktion wird in Step 3 in `klage_routes.py` extrahiert, damit der Serializer-Effekt ohne kompletten RA-MICRO-Stack testbar ist:

```python
import importlib
import os
import sys
import tempfile
import unittest

_tmp = tempfile.mkdtemp(prefix="klgv_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _fresh_db(name):
    db_path = os.path.join(_tmp, f"{name}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    import backend.db.database as db_mod
    import backend.db.schema_manager as sm
    importlib.reload(db_mod)
    importlib.reload(sm)
    sm.init_db()
    return db_mod


class TestGlobalerVertreterPass(unittest.TestCase):
    def test_synthetischer_ghpv_bekommt_globalen_vertreter(self):
        db_mod = _fresh_db("ghpv")
        from backend.models.firmen_vertreter import upsert_firmen_vertreter
        from backend.routers.klage_routes import _wende_globalen_vertreter_an
        with db_mod.get_connection() as conn:
            upsert_firmen_vertreter(
                conn, "ADAC Autoversicherung AG", "Stefan Daehne", "Vorstand")
            alle_bet = [{
                "id": -1, "vorname": "", "name": "ADAC Autoversicherung AG",
                "firma": "ADAC Autoversicherung AG", "versicherung": "",
                "vertreter_name": "", "vertreter_funktion": "",
                "rolle_klage": "beklagter",
            }]
            _wende_globalen_vertreter_an(conn, alle_bet)
        self.assertEqual(alle_bet[0]["vertreter_name"], "Stefan Daehne")
        self.assertEqual(alle_bet[0]["vertreter_funktion"], "Vorstand")

    def test_direkter_vertreter_hat_vorrang(self):
        db_mod = _fresh_db("vorrang")
        from backend.models.firmen_vertreter import upsert_firmen_vertreter
        from backend.routers.klage_routes import _wende_globalen_vertreter_an
        with db_mod.get_connection() as conn:
            upsert_firmen_vertreter(conn, "Muster AG", "Global Name", "Vorstand")
            alle_bet = [{
                "id": 5, "vorname": "", "name": "Muster AG", "firma": "Muster AG",
                "versicherung": "", "vertreter_name": "Direkt Name",
                "vertreter_funktion": "Vorstand", "rolle_klage": "beklagter",
            }]
            _wende_globalen_vertreter_an(conn, alle_bet)
        self.assertEqual(alle_bet[0]["vertreter_name"], "Direkt Name")

    def test_natuerliche_person_mit_versicherung_bleibt_ohne_vertreter(self):
        db_mod = _fresh_db("person")
        from backend.models.firmen_vertreter import upsert_firmen_vertreter
        from backend.routers.klage_routes import _wende_globalen_vertreter_an
        with db_mod.get_connection() as conn:
            upsert_firmen_vertreter(conn, "HUK", "Falsch Fuellen", "Vorstand")
            alle_bet = [{
                "id": 9, "vorname": "Max", "name": "Mustermann", "firma": "",
                "versicherung": "HUK", "vertreter_name": "",
                "vertreter_funktion": "", "rolle_klage": "beklagter",
            }]
            _wende_globalen_vertreter_an(conn, alle_bet)
        self.assertEqual(alle_bet[0]["vertreter_name"], "")

    def test_ra_micro_eintrag_ohne_vertreter_key(self):
        db_mod = _fresh_db("ramicro")
        from backend.models.firmen_vertreter import upsert_firmen_vertreter
        from backend.routers.klage_routes import _wende_globalen_vertreter_an
        with db_mod.get_connection() as conn:
            upsert_firmen_vertreter(conn, "Baloise AG", "B Vorstand", "Vorstand")
            alle_bet = [{
                "id": 0, "vorname": "", "name": "Baloise AG", "firma": "Baloise AG",
                "rolle_klage": "beklagter",
            }]
            _wende_globalen_vertreter_an(conn, alle_bet)
        self.assertEqual(alle_bet[0]["vertreter_name"], "B Vorstand")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_klage_firmen_vertreter_global.py -v`
Expected: FAIL — `ImportError: cannot import name '_wende_globalen_vertreter_an'`.

- [ ] **Step 3a: Add the module-level helper**

In `backend/routers/klage_routes.py`, auf Modulebene (z.B. direkt nach `_ghpv_bereits_vorhanden`, nahe `:70` — dort wo bereits GHPV-Helfer liegen), einfügen:

```python
def _wende_globalen_vertreter_an(conn, alle_bet):
    """
    Fuellt Vertreter aus dem globalen firmen_vertreter-Speicher, wenn der
    Beklagte selbst keinen traegt. Nur fuer Organisationen (leerer vorname);
    Schluessel ist firma bzw. name -- NICHT versicherung (die traegt bei
    natuerlichen Personen den Haftpflichtversicherer, nicht die Partei selbst).
    """
    from ..models.firmen_vertreter import hole_firmen_vertreter
    for b in alle_bet:
        if b.get("rolle_klage") != "beklagter":
            continue
        if (b.get("vertreter_name") or "").strip():
            continue
        if (b.get("vorname") or "").strip():
            continue
        key = (b.get("firma") or b.get("name") or "").strip()
        if not key:
            continue
        treffer = hole_firmen_vertreter(conn, key)
        if treffer:
            b["vertreter_name"] = treffer["vertreter_name"]
            b["vertreter_funktion"] = treffer["vertreter_funktion"]
```

- [ ] **Step 3b: Call the pass in the serializer**

In `hole_klage_daten`, direkt nach dem Ende des synthetischen-GHPV-Append-Blocks (nach `:1025`, der Zeile mit `})` die den `alle_bet.append({...})` schließt), noch **innerhalb** des `with get_connection() as conn`-Blocks, einfügen:

```python
    _wende_globalen_vertreter_an(conn, alle_bet)
```

(Einrückung: dieselbe Ebene wie der `_ghpv_wdm = ...`-Block darüber — vier Leerzeichen unter der Funktion, innerhalb des `with`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_klage_firmen_vertreter_global.py -v`
Expected: PASS (4 Tests).

- [ ] **Step 5: Run the existing klage suite to confirm no regression**

Run: `cd backend && python -m pytest tests/test_klage_ghpv_dublette.py tests/test_klage_kw18_route.py -v`
Expected: PASS (unverändert).

- [ ] **Step 6: Commit**

```bash
git add backend/routers/klage_routes.py backend/tests/test_klage_firmen_vertreter_global.py
git commit -m "feat(klage): globaler Vertreter-Lookup beim Aufbau der Beklagten"
```

---

## Task 5: Frontend — `firma` an `vertreterSpeichern` durchreichen

**Files:**
- Modify: `frontend/src/api.js:818-821` (`vertreterSpeichern`)
- Modify: `frontend/src/sections/KlageSection.jsx:121-205` (`VertreterModal`)
- Test: `frontend/src/api.vertreterSpeichern.test.js`

**Interfaces:**
- Consumes: Endpoint aus Task 3 (`firma` im Body).
- Produces: `apiFirmen.vertreterSpeichern(id, name, funk, firma)` sendet Body `{beteiligter_id, vertreter_name, vertreter_funktion, firma}`. Der `VertreterModal` übergibt den Firmennamen (`vertreterModal.name`) als `firma` an beiden Speicher-Aufrufen.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/api.vertreterSpeichern.test.js`:

```javascript
import { describe, it, expect, vi, beforeEach } from "vitest";
import { apiFirmen } from "./api.js";

describe("apiFirmen.vertreterSpeichern", () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true, status: 200, json: async () => ({ ok: true }),
    });
    globalThis.localStorage = { getItem: () => null, setItem: () => {} };
  });

  it("sendet firma im Body mit", async () => {
    await apiFirmen.vertreterSpeichern(
      -1, "Stefan Daehne", "Vorstand", "ADAC Autoversicherung AG");
    const [, opts] = globalThis.fetch.mock.calls[0];
    const body = JSON.parse(opts.body);
    expect(body).toEqual({
      beteiligter_id: -1,
      vertreter_name: "Stefan Daehne",
      vertreter_funktion: "Vorstand",
      firma: "ADAC Autoversicherung AG",
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/api.vertreterSpeichern.test.js`
Expected: FAIL — `body` enthält kein `firma` (aktuell nur 3 Felder).

- [ ] **Step 3a: Extend `vertreterSpeichern` in api.js**

Ersetze `frontend/src/api.js:818-821`:

```javascript
  vertreterSpeichern:(id, name, funk, firma) => request('/firmen/vertreter/speichern', {
    method: 'POST',
    body: JSON.stringify({ beteiligter_id: id, vertreter_name: name, vertreter_funktion: funk, firma }),
  }),
```

- [ ] **Step 3b: Pass the firm name from the modal**

In `frontend/src/sections/KlageSection.jsx`:

Zeile `:123` — Firmennamen unter eigenem Bezeichner destrukturieren (der `onSave`-Callback bei `:182` hat einen Parameter `name`, der den äußeren `name` sonst verdeckt):

```javascript
  const { id, name: firmaName, daten } = vertreterModal;
```

Zeile `:133` — Überschrift auf `firmaName` umstellen:

```javascript
          Vertreter-Lookup: {firmaName}
```

Zeile `:161` — „Übernehmen"-Handler, `firmaName` als 4. Argument:

```javascript
                      await apiFirmen.vertreterSpeichern(id, v.name, v.funktion, firmaName);
```

Zeile `:187` — manuelle Eingabe, `firmaName` als 4. Argument:

```javascript
              apiFirmen.vertreterSpeichern(id, name, funk, firmaName).catch(e => {
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/api.vertreterSpeichern.test.js`
Expected: PASS.

- [ ] **Step 5: Run the full frontend suite + build**

Run: `cd frontend && npx vitest run && npm run build`
Expected: alle Tests grün (bisher 314 + neuer), Build ohne Fehler.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api.js frontend/src/sections/KlageSection.jsx frontend/src/api.vertreterSpeichern.test.js
git commit -m "feat(klage-fe): Firmennamen an vertreterSpeichern durchreichen (globaler Speicher)"
```

---

## Task 6: End-to-End-Verifikation im echten App-Flow

**Files:** keine Code-Änderung — Verifikation gemäß `verify`/`run`-Skill.

- [ ] **Step 1: Backend-Gesamtsuite**

Run: `cd backend && python -m pytest tests/test_migration_62.py tests/test_firmen_vertreter_model.py tests/test_firmen_vertreter_speichern.py tests/test_klage_firmen_vertreter_global.py -v`
Expected: alle PASS.

- [ ] **Step 2: Prod-/Dev-DB-Drift prüfen (vor App-Start)**

Sicherstellen, dass die aktive Docker-Volume-DB (`dev-data`, `/app/data/unfallakten.db`) `firmen_vertreter` besitzt (Migration zieht beim Start nach). Bei Bestands-Prod-DBs zusätzlich prüfen, ob `beteiligte.vertreter_name`/`vertreter_funktion` (Migration 23) vorhanden sind — laut Handover war hier Drift; ggf. wie im Nachtest per Migrations-Lauf/ALTER nachziehen. Backup vor Eingriff.

- [ ] **Step 3: Live-Test an Akte 828/24 (der verifizierte Reproduktionsfall)**

Klage-Wizard öffnen → Schritt 2/11 → beim synthetischen GHPV-Versicherer „Vertreter-Lookup" → Organ bestätigen/übernehmen → Wizard schließen und **neu öffnen**. Erwartung: „⚠ Firma ohne Vertreter" ist weg, „Generieren" nicht mehr `gesperrt` (`firmenOhneVertreter.length === 0`). Zweite Akte mit derselben Versicherung öffnen → Vertreter ist ohne erneuten Lookup vorbelegt (aktenübergreifend).

- [ ] **Step 4: Commit (nur falls Step 2 eine Migrations-/Doku-Anpassung nötig machte)**

```bash
git add -p
git commit -m "chore(klage): DB-Drift-Check firmen_vertreter dokumentiert"
```

---

## Self-Review

**Spec coverage (gegen `handover/naechste_session_firmen-vertreter-global.md`):**
1. Migration neue Tabelle `firmen_vertreter` → Task 1 ✅ (Schema exakt: `firma_norm` PK, `firma_anzeige`, `vertreter_name` NOT NULL, `vertreter_funktion`, `aktualisiert_am`).
2. Backend `speichern` akzeptiert `firma`, UPSERT global + optional `beteiligte` → Task 3 ✅.
3. Serializer Global-Lookup-Einweben (`b_dict`/synthetischer GHPV) → Task 4 ✅ (finaler Pass über `alle_bet`, deckt SQLite-, RA-MICRO- und synthetische Einträge ab).
4. Frontend `vertreterSpeichern(id,name,funk,firma)` + Modal übergibt `firma` → Task 5 ✅.
5. Tests: Migration/Endpoint/Serializer-E2E/Frontend → Tasks 1–5 je eigener Test ✅.
- „Optional `beteiligter_as_dict` analog" → bewusst **out of scope** (YAGNI; kein Verbraucher braucht es aktuell — Handover markiert es als optional).
- Abgrenzung „kein Auto-Apply", „RA-MICRO read-only", „Normalisierung konservativ, Rechtsform nicht strippen" → in Global Constraints + `firma_norm`-Test verankert ✅.

**Refinement gegenüber Handover:** Der Lookup-Schlüssel schließt `versicherung` bewusst aus (Handover-Wortlaut `versicherung||firma||name`). Grund: `klage_routes.py:987-988` setzt `versicherung` auf jeden natürlichen-Personen-Beklagten → `versicherung`-Key würde Fahrer/Halter den Vorstand ihres Versicherers zuordnen. Test `test_natuerliche_person_mit_versicherung_bleibt_ohne_vertreter` sichert das ab.

**Placeholder-Scan:** keine TBD/TODO/„handle edge cases" — alle Code- und Testblöcke ausformuliert.

**Typkonsistenz:** `firma_norm`/`upsert_firmen_vertreter`/`hole_firmen_vertreter` (Rückgabe-Dict `{"vertreter_name","vertreter_funktion"}`) über Tasks 2→3→4 einheitlich benannt; `_wende_globalen_vertreter_an(conn, alle_bet)` in Task 4 definiert und getestet; Frontend-Signatur `vertreterSpeichern(id, name, funk, firma)` in Task 5 durchgängig.
