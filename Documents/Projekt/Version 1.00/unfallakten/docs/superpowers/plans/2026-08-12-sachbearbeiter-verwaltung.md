# Sachbearbeiter-Verwaltung Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sachbearbeiter-Kürzel, -Namen, -Titel, Kalenderzuordnung und Dashboard-Vorauswahl aus vier hartcodierten Listen in eine im Browser pflegbare Tabelle überführen.

**Architecture:** Neue SQLite-Tabelle `sachbearbeiter` (Migration 68) als einzige Quelle. Das bestehende Modul `backend/ramicro/sachbearbeiter.py` behält Importpfad und Funktionssignaturen, liest aber aus der Tabelle — dadurch bleiben alle fünf DOCX-Generatoren unverändert. CRUD-Endpunkte unter `/einstellungen/sachbearbeiter`, ein neuer Einstellungen-Reiter im Frontend, und die Tagesübersicht zieht ihre Filter-Chips aus derselben Quelle.

**Tech Stack:** Python 3.12 / Flask / SQLite (Backend, läuft im Container `unfallakten-backend-dev`), React 18 / Vite / Vitest + Testing Library (Frontend), pymssql read-only gegen RA-MICRO.

**Spec:** `docs/superpowers/specs/2026-08-12-sachbearbeiter-verwaltung-design.md`

## Global Constraints

- **TDD ohne Ausnahme:** Test zuerst, RED-Lauf beobachten, dann minimale Implementierung. Kein Produktionscode ohne vorher fehlgeschlagenen Test.
- **RA-MICRO ist read-only.** Nur `SELECT`. Niemals schreiben.
- **Migrationen atomar in EINEM Edit schreiben** (Reloader-Falle, `docs/STATE.md`): Der Flask-Reloader stempelt sonst mitten im Edit die Version, ohne die Tabelle anzulegen. Kein `executescript()`; um jedes DDL ein explizites `conn.commit()`.
- **Zielsprache Deutsch** für alle nutzersichtbaren Texte, Fehlermeldungen und Commit-Bodies.
- **Keine Kommentare im Code** außer bei nicht-offensichtlichem Verhalten.
- Backend-Tests: `docker exec unfallakten-backend-dev python -m pytest <pfad> -q`
- Frontend-Tests: `cd frontend && npx vitest run <pfad>`
- Kürzel-Regel systemweit: **exakt zwei Großbuchstaben** (`^[A-Z]{2}$`), deckungsgleich mit RA-MICRO.
- Nach jeder Task committen (lokal, kein Push).

---

## File Structure

| Datei | Verantwortung |
|---|---|
| `backend/db/schema_manager.py` (ändern) | Migration 68: Tabelle + Unique-Index + 11 Startzeilen |
| `backend/ramicro/sachbearbeiter.py` (ändern) | Lesezugriff auf die Tabelle; `hole_sachbearbeiter`, `alle_sachbearbeiter`, `kalender_zu_kuerzel`, Fallback-Dict |
| `backend/routers/einstellungen_routes.py` (ändern) | CRUD + RA-MICRO-Abgleich unter `/einstellungen/sachbearbeiter` |
| `backend/routers/dashboard_routes.py` (ändern) | `_KALENDER_ZU_SB` entfällt, nutzt `kalender_zu_kuerzel()` |
| `backend/tests/test_sachbearbeiter.py` (neu) | Migration, Modul, CRUD, Abgleich |
| `frontend/src/api.js` (ändern) | fünf Aufrufe in `apiEinstellungen` |
| `frontend/src/views/einstellungen/SachbearbeiterTab.jsx` (neu) | Reiter: Liste, Bearbeiten, Anlegen, Löschen, Abgleich |
| `frontend/src/views/einstellungen/SachbearbeiterTab.test.jsx` (neu) | Tests dazu |
| `frontend/src/views/EinstellungenView.jsx` (ändern) | Reiter einhängen |
| `frontend/src/views/ActionBoardView.jsx` (ändern) | Chips + Vorauswahl + Tooltips aus der API |

`SachbearbeiterTab.jsx` bekommt ein eigenes Unterverzeichnis-Muster analog `StandardtexteTab.jsx`; `EinstellungenView.jsx` ist bereits über 1.500 Zeilen lang und wird deshalb **nur** um den Tab-Eintrag und die eine Render-Zeile erweitert, nicht um Logik.

---

### Task 1: Migration 68 — Tabelle `sachbearbeiter` mit Startbefüllung

**Files:**
- Modify: `backend/db/schema_manager.py` (Migrationsliste ~Zeile 323, Dispatch ~Zeile 1781, neue Funktion neben `_run_migration_67`)
- Test: `backend/tests/test_sachbearbeiter.py` (neu)

**Interfaces:**
- Consumes: nichts
- Produces: Tabelle `sachbearbeiter(kuerzel, name, titel, anrede, rolle, aktiv, ignoriert, dashboard_vorauswahl, kalender_name, sortierung, erstellt_am, geaendert_am)`; Modulkonstante `_SACHBEARBEITER_SEED: list[tuple]`

- [ ] **Step 1: Testdatei anlegen mit dem Migrationstest**

`backend/tests/test_sachbearbeiter.py`:

```python
"""
Tests für die Sachbearbeiter-Verwaltung (Migration 68, Modul, Endpunkte).
"""

import importlib
import os
import tempfile
import unittest

_tmp_dir = tempfile.mkdtemp()


def _setup(test_id: str):
    """Frische DB + Flask-App (Muster: test_dashboard_uebersicht._setup)."""
    db_path = os.path.join(_tmp_dir, f"sb_{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    os.environ["JWT_SECRET_KEY"] = "test-secret-key-minimum-32-characters!!"
    os.environ["FLASK_SECRET_KEY"] = "test-flask-secret-key-minimum-32-characters!!"

    import backend.db.database as db_mod
    import backend.db.schema_manager as schema_mod
    import backend.ramicro.sachbearbeiter as sb_mod
    import backend.routers.einstellungen_routes as eins_mod
    import backend.app as app_mod

    for m in (db_mod, schema_mod, sb_mod, eins_mod, app_mod):
        importlib.reload(m)

    app = app_mod.erstelle_app({"TESTING": True})
    return app.test_client()


class TestMigration68(unittest.TestCase):

    def setUp(self):
        self.client = _setup(self._testMethodName)

    def test_tabelle_und_elf_startzeilen(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            rows = [dict(r) for r in conn.execute(
                "SELECT kuerzel, name, titel, rolle, aktiv, dashboard_vorauswahl, "
                "kalender_name FROM sachbearbeiter ORDER BY sortierung"
            ).fetchall()]

        self.assertEqual(len(rows), 11)
        self.assertEqual([r["kuerzel"] for r in rows][:5], ["AS", "PK", "CO", "MM", "AH"])

        nach_kuerzel = {r["kuerzel"]: r for r in rows}
        self.assertEqual(nach_kuerzel["CS"]["name"], "Carina Salvagnin")
        self.assertEqual(nach_kuerzel["JH"]["name"], "Jochen Hofmann")
        self.assertEqual(nach_kuerzel["JH"]["aktiv"], 0)
        self.assertEqual(nach_kuerzel["TB"]["rolle"], "refa")
        self.assertEqual(nach_kuerzel["AS"]["kalender_name"], "RA.Schatz")
        vorausgewaehlt = {r["kuerzel"] for r in rows if r["dashboard_vorauswahl"]}
        self.assertEqual(vorausgewaehlt, {"AS", "PK", "CO", "MM", "AH"})

    def test_zweiter_lauf_aendert_nichts(self):
        from backend.db.database import get_connection
        from backend.db.schema_manager import _run_migration_68
        with get_connection() as conn:
            conn.execute("UPDATE sachbearbeiter SET name = 'Geändert' WHERE kuerzel = 'AS'")
            conn.commit()
            _run_migration_68(conn)
            name = conn.execute(
                "SELECT name FROM sachbearbeiter WHERE kuerzel = 'AS'"
            ).fetchone()["name"]
            anzahl = conn.execute("SELECT COUNT(*) AS n FROM sachbearbeiter").fetchone()["n"]
            versionen = conn.execute(
                "SELECT COUNT(*) AS n FROM schema_version WHERE version = 68"
            ).fetchone()["n"]
        self.assertEqual(name, "Geändert")
        self.assertEqual(anzahl, 11)
        self.assertEqual(versionen, 1)

    def test_kalender_name_ist_eindeutig(self):
        import sqlite3
        from backend.db.database import get_connection
        with get_connection() as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO sachbearbeiter (kuerzel, name, kalender_name) "
                    "VALUES ('ZZ', 'Doppelkalender', 'RA.Schatz')"
                )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Test laufen lassen, RED bestätigen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_sachbearbeiter.py -q`
Expected: FAIL mit `sqlite3.OperationalError: no such table: sachbearbeiter`

- [ ] **Step 3: Migration schreiben — in EINEM Edit, sonst greift die Reloader-Falle**

Drei Änderungen in `backend/db/schema_manager.py` gemeinsam anwenden:

(a) In der Migrations-Map neben Zeile 324 ergänzen:

```python
    68: "-- migration_68_sachbearbeiter",  # Handled by _run_migration_68
```

(b) Im Dispatch von `run_migrations()` nach dem `elif version == 67:`-Zweig:

```python
            elif version == 68:
                _run_migration_68(conn)
```

(c) Neue Funktion samt Seed direkt hinter `_run_migration_67`:

```python
_SACHBEARBEITER_SEED = [
    ("AS", "Andreas Schatz",    "Rechtsanwalt",   "herr", "anwalt", 1, 1, "RA.Schatz",         10),
    ("PK", "Peter Koch",        "Rechtsanwalt",   "herr", "anwalt", 1, 1, "Peter Koch",        20),
    ("CO", "Claudia Ostarek",   "Rechtsanwältin", "frau", "anwalt", 1, 1, "C. Ostarek",        30),
    ("MM", "Monika Mieth",      "Rechtsanwältin", "frau", "anwalt", 1, 1, "Monika Mieth",      40),
    ("AH", "Alexander Herbert", "Rechtsanwalt",   "herr", "anwalt", 1, 1, "Alexander.Herbert", 50),
    ("CS", "Carina Salvagnin",  "Rechtsanwältin", "frau", "anwalt", 1, 0, None,                60),
    ("TB", "Tanja Brunner",     "Rechtsanwalts- und Notarfachangestellte",
                                                  "frau", "refa",   1, 0, None,                70),
    ("SK", "Sophie Koch",       "Rechtsanwaltsfachangestellte", "frau", "refa", 1, 0, None,     80),
    ("EI", "Elsa Ihl",          "Rechtsanwaltsfachangestellte", "frau", "refa", 1, 0, None,     90),
    ("SN", "Susanne Neumann",   "Rechtsanwaltsfachangestellte", "frau", "refa", 1, 0, None,    100),
    ("JH", "Jochen Hofmann",    "Rechtsanwalt",   "herr", "anwalt", 0, 0, None,                110),
]


def _run_migration_68(conn: sqlite3.Connection) -> None:
    """
    Migration 68 - sachbearbeiter: eine Quelle für Kürzel, Name, Titel,
    Rolle, Kalenderzuordnung und Dashboard-Vorauswahl.
    Kein executescript, explizite Commits um DDL (Reloader-Falle).
    """
    conn.commit()
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sachbearbeiter ("
        " kuerzel              TEXT PRIMARY KEY,"
        " name                 TEXT    NOT NULL,"
        " titel                TEXT    NOT NULL DEFAULT '',"
        " anrede               TEXT    NOT NULL DEFAULT '',"
        " rolle                TEXT    NOT NULL DEFAULT 'anwalt',"
        " aktiv                INTEGER NOT NULL DEFAULT 1,"
        " ignoriert            INTEGER NOT NULL DEFAULT 0,"
        " dashboard_vorauswahl INTEGER NOT NULL DEFAULT 0,"
        " kalender_name        TEXT,"
        " sortierung           INTEGER NOT NULL DEFAULT 100,"
        " erstellt_am          TEXT    NOT NULL DEFAULT (datetime('now')),"
        " geaendert_am         TEXT)"
    )
    conn.commit()
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uidx_sachbearbeiter_kalender "
        "ON sachbearbeiter(kalender_name) "
        "WHERE kalender_name IS NOT NULL AND kalender_name <> ''"
    )
    conn.commit()
    for zeile in _SACHBEARBEITER_SEED:
        conn.execute(
            "INSERT OR IGNORE INTO sachbearbeiter "
            "(kuerzel, name, titel, anrede, rolle, aktiv, dashboard_vorauswahl, "
            " kalender_name, sortierung) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            zeile,
        )
    conn.commit()
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) VALUES (?, ?)",
        (68, "Migration 68 - sachbearbeiter (Kürzel/Name/Kalender als eine Quelle)"),
    )
    logger.info("Migration 68 abgeschlossen (sachbearbeiter, %d Startzeilen).",
                len(_SACHBEARBEITER_SEED))
```

Die Tabelle wird bewusst **nicht** zusätzlich in die Basis-`CREATE`-Anweisungen aufgenommen: `run_migrations()` läuft auch auf frischen Datenbanken, genau wie bei Migration 66 und 67.

- [ ] **Step 4: Test laufen lassen, GREEN bestätigen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_sachbearbeiter.py -q`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add "Documents/Projekt/Version 1.00/unfallakten/backend/db/schema_manager.py" \
        "Documents/Projekt/Version 1.00/unfallakten/backend/tests/test_sachbearbeiter.py"
git commit -m "feat(db): Migration 68 -- Tabelle sachbearbeiter mit 11 Startzeilen"
```

---

### Task 2: Modul `sachbearbeiter.py` liest aus der Tabelle

**Files:**
- Modify: `backend/ramicro/sachbearbeiter.py` (komplett umgebaut, `HV_KENNZEICHEN` bleibt unverändert stehen)
- Test: `backend/tests/test_sachbearbeiter.py` (Klasse ergänzen)

**Interfaces:**
- Consumes: Tabelle `sachbearbeiter` aus Task 1
- Produces:
  - `hole_sachbearbeiter(kuerzel: str) -> dict` mit Schlüsseln `name`, `titel` (Signatur unverändert)
  - `alle_sachbearbeiter(nur_aktive: bool = False) -> list[dict]` mit allen Tabellenspalten
  - `kalender_zu_kuerzel() -> dict[str, str]` (Kalendername → Kürzel)

- [ ] **Step 1: Tests schreiben**

An `backend/tests/test_sachbearbeiter.py` anhängen:

```python
class TestSachbearbeiterModul(unittest.TestCase):

    def setUp(self):
        self.client = _setup(self._testMethodName)

    def test_name_kommt_aus_der_tabelle(self):
        from backend.ramicro.sachbearbeiter import hole_sachbearbeiter
        self.assertEqual(hole_sachbearbeiter("AS")["name"], "Andreas Schatz")
        self.assertEqual(hole_sachbearbeiter("as")["titel"], "Rechtsanwalt")

    def test_aenderung_wirkt_sofort(self):
        from backend.db.database import get_connection
        from backend.ramicro.sachbearbeiter import hole_sachbearbeiter
        with get_connection() as conn:
            conn.execute("UPDATE sachbearbeiter SET titel = 'Fachanwalt für Verkehrsrecht' "
                         "WHERE kuerzel = 'AS'")
            conn.commit()
        self.assertEqual(hole_sachbearbeiter("AS")["titel"], "Fachanwalt für Verkehrsrecht")

    def test_unbekanntes_kuerzel_bleibt_platzhalter(self):
        from backend.ramicro.sachbearbeiter import hole_sachbearbeiter
        self.assertEqual(hole_sachbearbeiter("XY")["name"], "[XY]")

    def test_ignoriertes_kuerzel_liefert_platzhalter(self):
        from backend.db.database import get_connection
        from backend.ramicro.sachbearbeiter import hole_sachbearbeiter
        with get_connection() as conn:
            conn.execute("INSERT INTO sachbearbeiter (kuerzel, name, aktiv, ignoriert) "
                         "VALUES ('ME', 'ME', 0, 1)")
            conn.commit()
        self.assertEqual(hole_sachbearbeiter("ME")["name"], "[ME]")

    def test_leeres_kuerzel_liefert_kanzlei(self):
        from backend.ramicro.sachbearbeiter import hole_sachbearbeiter
        self.assertIn("Koch, Schatz", hole_sachbearbeiter("")["name"])

    def test_nur_aktive_ohne_ausgeschiedene_und_ignorierte(self):
        from backend.ramicro.sachbearbeiter import alle_sachbearbeiter
        kuerzel = [e["kuerzel"] for e in alle_sachbearbeiter(nur_aktive=True)]
        self.assertIn("AS", kuerzel)
        self.assertNotIn("JH", kuerzel)
        self.assertEqual(kuerzel, sorted(kuerzel, key=lambda k: kuerzel.index(k)))

    def test_kalender_mapping_aus_der_tabelle(self):
        from backend.db.database import get_connection
        from backend.ramicro.sachbearbeiter import kalender_zu_kuerzel
        self.assertEqual(kalender_zu_kuerzel()["RA.Schatz"], "AS")
        with get_connection() as conn:
            conn.execute("UPDATE sachbearbeiter SET kalender_name = 'T. Brunner' "
                         "WHERE kuerzel = 'TB'")
            conn.commit()
        self.assertEqual(kalender_zu_kuerzel()["T. Brunner"], "TB")

    def test_fallback_wenn_tabelle_fehlt(self):
        from backend.db.database import get_connection
        from backend.ramicro.sachbearbeiter import hole_sachbearbeiter
        with get_connection() as conn:
            conn.execute("DROP TABLE sachbearbeiter")
            conn.commit()
        self.assertEqual(hole_sachbearbeiter("AS")["name"], "Andreas Schatz")
```

- [ ] **Step 2: Test laufen lassen, RED bestätigen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_sachbearbeiter.py::TestSachbearbeiterModul -q`
Expected: FAIL — `cannot import name 'alle_sachbearbeiter'`, und `test_aenderung_wirkt_sofort` schlägt fehl, weil das Dict gelesen wird

- [ ] **Step 3: Modul umbauen**

`backend/ramicro/sachbearbeiter.py` — Kopf bis einschließlich `hole_sachbearbeiter` ersetzen; `HV_KENNZEICHEN` bleibt unverändert erhalten:

```python
"""
Modul 8 – Sachbearbeiter
========================
Quelle ist die Tabelle ``sachbearbeiter`` (Migration 68), gepflegt im
Einstellungen-Reiter. Das Dict ``_FALLBACK`` greift nur, wenn die Tabelle
fehlt (Bestands-DB ohne Migration 68).

RA-Micro speichert nur Kürzel (z.B. "AS") in tblAkten.sAktenSachbearbeiter.
Eine Stammdatentabelle mit Vollnamen existiert dort nicht.
"""

import logging
import sqlite3

from ..db.database import get_connection

logger = logging.getLogger(__name__)

KANZLEI = {"name": "Kanzlei Koch, Schatz & Kollegen", "titel": "Rechtsanwälte"}

_FALLBACK: dict[str, dict] = {
    "AS": {"name": "Andreas Schatz",    "titel": "Rechtsanwalt"},
    "CO": {"name": "Claudia Ostarek",   "titel": "Rechtsanwältin"},
    "EI": {"name": "Elsa Ihl",          "titel": "Rechtsanwaltsfachangestellte"},
    "SK": {"name": "Sophie Koch",       "titel": "Rechtsanwaltsfachangestellte"},
    "SN": {"name": "Susanne Neumann",   "titel": "Rechtsanwaltsfachangestellte"},
    "TB": {"name": "Tanja Brunner",     "titel": "Rechtsanwalts- und Notarfachangestellte"},
    "PK": {"name": "Peter Koch",        "titel": "Rechtsanwalt"},
    "CS": {"name": "Carina Salvagnin",  "titel": "Rechtsanwältin"},
    "MM": {"name": "Monika Mieth",      "titel": "Rechtsanwältin"},
    "AH": {"name": "Alexander Herbert", "titel": "Rechtsanwalt"},
}

_SPALTEN = ("kuerzel, name, titel, anrede, rolle, aktiv, ignoriert, "
            "dashboard_vorauswahl, kalender_name, sortierung")


def _fallback_zeilen() -> list[dict]:
    return [
        {"kuerzel": k, "name": v["name"], "titel": v["titel"], "anrede": "",
         "rolle": "anwalt", "aktiv": 1, "ignoriert": 0, "dashboard_vorauswahl": 0,
         "kalender_name": None, "sortierung": 100}
        for k, v in _FALLBACK.items()
    ]


def _zeilen(nur_aktive: bool = False) -> list[dict]:
    sql = f"SELECT {_SPALTEN} FROM sachbearbeiter"
    if nur_aktive:
        sql += " WHERE aktiv = 1 AND ignoriert = 0"
    sql += " ORDER BY sortierung, kuerzel"
    try:
        with get_connection() as conn:
            return [dict(r) for r in conn.execute(sql).fetchall()]
    except sqlite3.OperationalError:
        logger.warning("Tabelle sachbearbeiter fehlt – Fallback auf die eingebaute Liste.")
        zeilen = _fallback_zeilen()
        return [z for z in zeilen if z["aktiv"]] if nur_aktive else zeilen


def alle_sachbearbeiter(nur_aktive: bool = False) -> list[dict]:
    """Alle Sachbearbeiter, sortiert nach Sortierung und Kürzel."""
    return _zeilen(nur_aktive)


def kalender_zu_kuerzel() -> dict[str, str]:
    """RA-MICRO-Kalendername → Kürzel (nur gepflegte Einträge)."""
    return {
        z["kalender_name"]: z["kuerzel"]
        for z in _zeilen()
        if (z.get("kalender_name") or "").strip()
    }


def hole_sachbearbeiter(kuerzel: str) -> dict:
    """
    Gibt Name und Titel für ein Sachbearbeiter-Kürzel zurück.
    Fallback: Kürzel in eckigen Klammern, Titel "Rechtsanwalt".
    """
    if not kuerzel:
        return dict(KANZLEI)
    gesucht = kuerzel.strip().upper()
    for z in _zeilen():
        if z["kuerzel"] == gesucht and not z["ignoriert"] and (z["name"] or "").strip():
            return {"name": z["name"], "titel": z["titel"]}
    return {"name": f"[{kuerzel}]", "titel": "Rechtsanwalt"}
```

Kein Zwischenspeicher: die Tabelle hat elf Zeilen, und ein Prozess-Cache würde bei vier Gunicorn-Workern zu veralteten Namen führen.

- [ ] **Step 4: Tests laufen lassen, GREEN bestätigen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_sachbearbeiter.py backend/tests/test_modul8.py -q`
Expected: alle passed (test_modul8 prüft `hole_sachbearbeiter` und muss unverändert grün bleiben)

- [ ] **Step 5: Commit**

```bash
git add "Documents/Projekt/Version 1.00/unfallakten/backend/ramicro/sachbearbeiter.py" \
        "Documents/Projekt/Version 1.00/unfallakten/backend/tests/test_sachbearbeiter.py"
git commit -m "refactor(sb): Namen/Titel/Kalender kommen aus der Tabelle statt aus dem Dict"
```

---

### Task 3: Termin-Zuordnung nutzt die Tabelle

**Files:**
- Modify: `backend/routers/dashboard_routes.py` (Konstante `_KALENDER_ZU_SB` ~Zeile 456, Nutzung ~Zeile 542)
- Test: `backend/tests/test_sachbearbeiter.py`

**Interfaces:**
- Consumes: `kalender_zu_kuerzel()` aus Task 2
- Produces: nichts Neues

- [ ] **Step 1: Test schreiben**

```python
class TestKalenderMapping(unittest.TestCase):

    def setUp(self):
        self.client = _setup(self._testMethodName)

    def test_dashboard_hat_keine_hartcodierte_kalenderliste_mehr(self):
        import backend.routers.dashboard_routes as dash
        self.assertFalse(hasattr(dash, "_KALENDER_ZU_SB"))

    def test_termine_nutzen_das_mapping_aus_der_tabelle(self):
        from backend.db.database import get_connection
        from backend.ramicro.sachbearbeiter import kalender_zu_kuerzel
        with get_connection() as conn:
            conn.execute("UPDATE sachbearbeiter SET kalender_name = 'S. Koch' "
                         "WHERE kuerzel = 'SK'")
            conn.commit()
        self.assertEqual(kalender_zu_kuerzel().get("S. Koch"), "SK")
```

- [ ] **Step 2: Test laufen lassen, RED bestätigen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_sachbearbeiter.py::TestKalenderMapping -q`
Expected: FAIL — `_KALENDER_ZU_SB` existiert noch

- [ ] **Step 3: Umstellen**

In `backend/routers/dashboard_routes.py` den Block

```python
# raKalender.dbo.Calendars → Sachbearbeiter-Kürzel
_KALENDER_ZU_SB = {
    "Peter Koch":        "PK",
    "Monika Mieth":      "MM",
    "RA.Schatz":         "AS",
    "C. Ostarek":        "CO",
    "Alexander.Herbert": "AH",
}
```

ersatzlos löschen und beim Import oben ergänzen:

```python
from ..ramicro.sachbearbeiter import kalender_zu_kuerzel
```

In der Termin-Funktion vor der Ergebnisschleife einmal laden und benutzen:

```python
            kalender_map = kalender_zu_kuerzel()
            for r in cur.fetchall():
```

```python
                sb = kalender_map.get(cal_name)
```

- [ ] **Step 4: Tests laufen lassen, GREEN bestätigen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_sachbearbeiter.py backend/tests/test_dashboard_uebersicht.py -q`
Expected: alle passed

- [ ] **Step 5: Commit**

```bash
git add "Documents/Projekt/Version 1.00/unfallakten/backend/routers/dashboard_routes.py" \
        "Documents/Projekt/Version 1.00/unfallakten/backend/tests/test_sachbearbeiter.py"
git commit -m "refactor(dashboard): Kalender-Zuordnung aus der sachbearbeiter-Tabelle"
```

---

### Task 4: CRUD-Endpunkte `/einstellungen/sachbearbeiter`

**Files:**
- Modify: `backend/routers/einstellungen_routes.py` (ans Dateiende anhängen, Kopf-Docstring ergänzen)
- Test: `backend/tests/test_sachbearbeiter.py`

**Interfaces:**
- Consumes: Tabelle aus Task 1
- Produces: `GET|POST /einstellungen/sachbearbeiter`, `PUT|DELETE /einstellungen/sachbearbeiter/<kuerzel>`; Antwortform `{"eintraege": [...]}` bzw. `{"ok": true, "eintrag": {...}}`, Fehler `{"fehler": "…"}`

- [ ] **Step 1: Tests schreiben**

```python
class TestSachbearbeiterEndpunkte(unittest.TestCase):

    def setUp(self):
        self.client = _setup(self._testMethodName)

    def _header(self):
        r = self.client.post("/auth/login", json={
            "email": "admin@test.de", "passwort": "Admin123!"})
        return {"Authorization": f"Bearer {r.get_json()['access_token']}"}

    def test_liste_liefert_alle_inklusive_inaktiver(self):
        r = self.client.get("/einstellungen/sachbearbeiter", headers=self._header())
        self.assertEqual(r.status_code, 200)
        eintraege = r.get_json()["eintraege"]
        self.assertEqual(len(eintraege), 11)
        jh = next(e for e in eintraege if e["kuerzel"] == "JH")
        self.assertFalse(jh["aktiv"])
        self.assertEqual(eintraege[0]["kuerzel"], "AS")

    def test_ohne_token_401(self):
        self.assertEqual(self.client.get("/einstellungen/sachbearbeiter").status_code, 401)

    def test_anlegen_und_wieder_lesen(self):
        r = self.client.post("/einstellungen/sachbearbeiter", headers=self._header(), json={
            "kuerzel": "XX", "name": "Neue Kollegin", "titel": "Rechtsanwältin",
            "anrede": "frau", "rolle": "anwalt", "aktiv": True,
            "dashboard_vorauswahl": True, "sortierung": 55})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json()["eintrag"]["name"], "Neue Kollegin")
        liste = self.client.get("/einstellungen/sachbearbeiter",
                                headers=self._header()).get_json()["eintraege"]
        self.assertIn("XX", [e["kuerzel"] for e in liste])

    def test_kuerzel_muss_genau_zwei_grossbuchstaben_sein(self):
        for falsch in ("A", "ABC", "a1", "12"):
            r = self.client.post("/einstellungen/sachbearbeiter", headers=self._header(),
                                 json={"kuerzel": falsch, "name": "Test"})
            self.assertEqual(r.status_code, 400, falsch)
            self.assertIn("Kürzel", r.get_json()["fehler"])

    def test_doppeltes_kuerzel_409(self):
        r = self.client.post("/einstellungen/sachbearbeiter", headers=self._header(),
                             json={"kuerzel": "AS", "name": "Doppelt"})
        self.assertEqual(r.status_code, 409)

    def test_leerer_name_400(self):
        r = self.client.post("/einstellungen/sachbearbeiter", headers=self._header(),
                             json={"kuerzel": "XX", "name": "   "})
        self.assertEqual(r.status_code, 400)

    def test_unbekannte_rolle_oder_anrede_400(self):
        r = self.client.post("/einstellungen/sachbearbeiter", headers=self._header(),
                             json={"kuerzel": "XX", "name": "Test", "rolle": "chef"})
        self.assertEqual(r.status_code, 400)
        r = self.client.post("/einstellungen/sachbearbeiter", headers=self._header(),
                             json={"kuerzel": "XY", "name": "Test", "anrede": "divers"})
        self.assertEqual(r.status_code, 400)

    def test_doppelter_kalendername_400(self):
        r = self.client.put("/einstellungen/sachbearbeiter/TB", headers=self._header(),
                            json={"kalender_name": "RA.Schatz"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Kalender", r.get_json()["fehler"])

    def test_aendern_setzt_geaendert_am(self):
        r = self.client.put("/einstellungen/sachbearbeiter/AS", headers=self._header(),
                            json={"titel": "Fachanwalt für Verkehrsrecht", "aktiv": True})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["eintrag"]["titel"], "Fachanwalt für Verkehrsrecht")
        from backend.db.database import get_connection
        with get_connection() as conn:
            row = conn.execute("SELECT geaendert_am FROM sachbearbeiter "
                               "WHERE kuerzel = 'AS'").fetchone()
        self.assertIsNotNone(row["geaendert_am"])

    def test_aendern_unbekannt_404(self):
        r = self.client.put("/einstellungen/sachbearbeiter/ZZ", headers=self._header(),
                            json={"name": "Niemand"})
        self.assertEqual(r.status_code, 404)

    def test_loeschen(self):
        self.assertEqual(
            self.client.delete("/einstellungen/sachbearbeiter/SN",
                               headers=self._header()).status_code, 200)
        liste = self.client.get("/einstellungen/sachbearbeiter",
                                headers=self._header()).get_json()["eintraege"]
        self.assertNotIn("SN", [e["kuerzel"] for e in liste])
        self.assertEqual(
            self.client.delete("/einstellungen/sachbearbeiter/SN",
                               headers=self._header()).status_code, 404)
```

- [ ] **Step 2: Tests laufen lassen, RED bestätigen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_sachbearbeiter.py::TestSachbearbeiterEndpunkte -q`
Expected: FAIL — 405/404 statt 200/201 (die Routen fehlen)

- [ ] **Step 3: Endpunkte implementieren**

Am Ende von `backend/routers/einstellungen_routes.py` anfügen (und `import re` oben ergänzen):

```python
_KUERZEL_RE = re.compile(r"^[A-Z]{2}$")
_ROLLEN     = ("anwalt", "refa")
_ANREDEN    = ("", "herr", "frau")

_SB_SPALTEN = ("kuerzel, name, titel, anrede, rolle, aktiv, ignoriert, "
               "dashboard_vorauswahl, kalender_name, sortierung, geaendert_am")


def _sb_zeile(conn, kuerzel):
    row = conn.execute(
        f"SELECT {_SB_SPALTEN} FROM sachbearbeiter WHERE kuerzel = ?", (kuerzel,)
    ).fetchone()
    return dict(row) if row else None


def _sb_liste(conn):
    return [dict(r) for r in conn.execute(
        f"SELECT {_SB_SPALTEN} FROM sachbearbeiter ORDER BY sortierung, kuerzel"
    ).fetchall()]


def _sb_pruefe_felder(conn, body, kuerzel):
    """Gibt (werte, fehler) zurück. werte enthält nur übergebene Felder."""
    werte, fehler = {}, []

    if "name" in body:
        name = str(body["name"]).strip()
        if not name:
            fehler.append("Name darf nicht leer sein.")
        werte["name"] = name
    if "titel" in body:
        werte["titel"] = str(body["titel"]).strip()
    if "anrede" in body:
        anrede = str(body["anrede"]).strip().lower()
        if anrede not in _ANREDEN:
            fehler.append("Anrede muss 'herr', 'frau' oder leer sein.")
        werte["anrede"] = anrede
    if "rolle" in body:
        rolle = str(body["rolle"]).strip().lower()
        if rolle not in _ROLLEN:
            fehler.append("Rolle muss 'anwalt' oder 'refa' sein.")
        werte["rolle"] = rolle
    for feld in ("aktiv", "ignoriert", "dashboard_vorauswahl"):
        if feld in body:
            werte[feld] = 1 if body[feld] else 0
    if "sortierung" in body:
        try:
            werte["sortierung"] = int(body["sortierung"])
        except (ValueError, TypeError):
            fehler.append("Sortierung muss eine ganze Zahl sein.")
    if "kalender_name" in body:
        kal = (str(body["kalender_name"]).strip() or None)
        if kal:
            belegt = conn.execute(
                "SELECT kuerzel FROM sachbearbeiter WHERE kalender_name = ? AND kuerzel <> ?",
                (kal, kuerzel or ""),
            ).fetchone()
            if belegt:
                fehler.append(
                    f"Kalendername '{kal}' ist bereits {belegt['kuerzel']} zugeordnet.")
        werte["kalender_name"] = kal

    return werte, fehler


@einstellungen_bp.route("/sachbearbeiter", methods=["GET"])
@login_erforderlich
def get_sachbearbeiter():
    """Alle Sachbearbeiter inklusive ausgeschiedener und ignorierter."""
    with get_connection() as conn:
        return jsonify({"eintraege": _sb_liste(conn)})


@einstellungen_bp.route("/sachbearbeiter", methods=["POST"])
@login_erforderlich
def post_sachbearbeiter():
    """Legt einen Sachbearbeiter an."""
    body   = request.get_json(silent=True) or {}
    kuerzel = str(body.get("kuerzel", "")).strip().upper()
    if not _KUERZEL_RE.match(kuerzel):
        return jsonify({"fehler": "Kürzel muss aus genau zwei Großbuchstaben bestehen."}), 400

    with get_connection() as conn:
        if _sb_zeile(conn, kuerzel):
            return jsonify({"fehler": f"Kürzel {kuerzel} ist bereits vergeben."}), 409

        werte, fehler = _sb_pruefe_felder(conn, body, kuerzel)
        if not werte.get("name"):
            fehler.append("Name darf nicht leer sein.")
        if fehler:
            return jsonify({"fehler": " ".join(fehler)}), 400

        werte["kuerzel"] = kuerzel
        spalten = ", ".join(werte)
        platz   = ", ".join("?" for _ in werte)
        conn.execute(f"INSERT INTO sachbearbeiter ({spalten}) VALUES ({platz})",
                     tuple(werte.values()))
        conn.commit()
        return jsonify({"ok": True, "eintrag": _sb_zeile(conn, kuerzel)}), 201


@einstellungen_bp.route("/sachbearbeiter/<kuerzel>", methods=["PUT"])
@login_erforderlich
def put_sachbearbeiter(kuerzel):
    """Ändert einen Sachbearbeiter; das Kürzel selbst bleibt unverändert."""
    kuerzel = kuerzel.strip().upper()
    body    = request.get_json(silent=True) or {}

    with get_connection() as conn:
        if not _sb_zeile(conn, kuerzel):
            return jsonify({"fehler": f"Sachbearbeiter {kuerzel} nicht gefunden."}), 404

        werte, fehler = _sb_pruefe_felder(conn, body, kuerzel)
        if fehler:
            return jsonify({"fehler": " ".join(fehler)}), 400
        if werte:
            werte["geaendert_am"] = datetime.now().isoformat(timespec="seconds")
            zuweisung = ", ".join(f"{k} = ?" for k in werte)
            conn.execute(f"UPDATE sachbearbeiter SET {zuweisung} WHERE kuerzel = ?",
                         (*werte.values(), kuerzel))
            conn.commit()
        return jsonify({"ok": True, "eintrag": _sb_zeile(conn, kuerzel)})


@einstellungen_bp.route("/sachbearbeiter/<kuerzel>", methods=["DELETE"])
@login_erforderlich
def delete_sachbearbeiter(kuerzel):
    """Löscht einen Sachbearbeiter. Altakten zeigen danach [XY]."""
    kuerzel = kuerzel.strip().upper()
    with get_connection() as conn:
        if not _sb_zeile(conn, kuerzel):
            return jsonify({"fehler": f"Sachbearbeiter {kuerzel} nicht gefunden."}), 404
        conn.execute("DELETE FROM sachbearbeiter WHERE kuerzel = ?", (kuerzel,))
        conn.commit()
        return jsonify({"ok": True})
```

Oben in der Datei zusätzlich ergänzen: `import re` und `from datetime import datetime`. Im Kopf-Docstring die fünf neuen Routen nachtragen.

- [ ] **Step 4: Tests laufen lassen, GREEN bestätigen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_sachbearbeiter.py -q`
Expected: alle passed

- [ ] **Step 5: Commit**

```bash
git add "Documents/Projekt/Version 1.00/unfallakten/backend/routers/einstellungen_routes.py" \
        "Documents/Projekt/Version 1.00/unfallakten/backend/tests/test_sachbearbeiter.py"
git commit -m "feat(einstellungen): CRUD-Endpunkte fuer Sachbearbeiter"
```

---

### Task 5: RA-MICRO-Abgleich (read-only, nicht blockierend)

**Files:**
- Modify: `backend/routers/einstellungen_routes.py`
- Test: `backend/tests/test_sachbearbeiter.py`

**Interfaces:**
- Consumes: `get_ramicro_connection`, `RaMicroVerbindungsFehler` aus `backend/ramicro/connector.py`
- Produces: `GET /einstellungen/sachbearbeiter/ramicro-abgleich` → `{"verfuegbar": bool, "kuerzel": {"AS": 3201, …}, "unbekannt": [{"kuerzel": "ME", "akten": 20}]}`

- [ ] **Step 1: Tests schreiben**

```python
class TestRamicroAbgleich(unittest.TestCase):

    def setUp(self):
        self.client = _setup(self._testMethodName)

    def _header(self):
        r = self.client.post("/auth/login", json={
            "email": "admin@test.de", "passwort": "Admin123!"})
        return {"Authorization": f"Bearer {r.get_json()['access_token']}"}

    def test_ohne_ramicro_verfuegbar_false(self):
        from unittest.mock import patch
        from backend.ramicro.connector import RaMicroVerbindungsFehler
        with patch("backend.ramicro.connector.get_ramicro_connection",
                   side_effect=RaMicroVerbindungsFehler("offline")):
            r = self.client.get("/einstellungen/sachbearbeiter/ramicro-abgleich",
                                headers=self._header())
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.get_json()["verfuegbar"])
        self.assertEqual(r.get_json()["unbekannt"], [])

    def test_unbekannte_kuerzel_werden_gemeldet(self):
        from contextlib import contextmanager
        from unittest.mock import patch

        class _Cursor:
            def execute(self, *a, **k): pass
            def fetchall(self):
                return [{"k": "AS", "n": 3201}, {"k": "ME", "n": 20}, {"k": "JH", "n": 2182}]

        class _Conn:
            def cursor(self): return _Cursor()

        @contextmanager
        def _fake():
            yield _Conn()

        with patch("backend.ramicro.connector.get_ramicro_connection", _fake):
            r = self.client.get("/einstellungen/sachbearbeiter/ramicro-abgleich",
                                headers=self._header())
        daten = r.get_json()
        self.assertTrue(daten["verfuegbar"])
        self.assertEqual(daten["kuerzel"]["AS"], 3201)
        self.assertEqual(daten["unbekannt"], [{"kuerzel": "ME", "akten": 20}])

    def test_ignoriertes_kuerzel_gilt_als_bekannt(self):
        from contextlib import contextmanager
        from unittest.mock import patch
        from backend.db.database import get_connection

        with get_connection() as conn:
            conn.execute("INSERT INTO sachbearbeiter (kuerzel, name, aktiv, ignoriert) "
                         "VALUES ('ME', 'ME', 0, 1)")
            conn.commit()

        class _Cursor:
            def execute(self, *a, **k): pass
            def fetchall(self): return [{"k": "ME", "n": 20}]

        class _Conn:
            def cursor(self): return _Cursor()

        @contextmanager
        def _fake():
            yield _Conn()

        with patch("backend.ramicro.connector.get_ramicro_connection", _fake):
            r = self.client.get("/einstellungen/sachbearbeiter/ramicro-abgleich",
                                headers=self._header())
        self.assertEqual(r.get_json()["unbekannt"], [])
```

- [ ] **Step 2: Tests laufen lassen, RED bestätigen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_sachbearbeiter.py::TestRamicroAbgleich -q`
Expected: FAIL — Route liefert 405

- [ ] **Step 3: Endpunkt implementieren**

An `backend/routers/einstellungen_routes.py` anfügen:

```python
@einstellungen_bp.route("/sachbearbeiter/ramicro-abgleich", methods=["GET"])
@login_erforderlich
def get_sachbearbeiter_ramicro_abgleich():
    """
    Zählt Akten je Kürzel in RA-MICRO (read-only) und meldet Kürzel,
    die dort vorkommen, hier aber weder gepflegt noch ignoriert sind.
    """
    from ..ramicro import connector

    try:
        with connector.get_ramicro_connection() as rc:
            cur = rc.cursor()
            cur.execute(
                "SELECT sAktenSachbearbeiter AS k, COUNT(*) AS n FROM tblAkten "
                "WHERE sAktenSachbearbeiter IS NOT NULL AND sAktenSachbearbeiter <> '' "
                "GROUP BY sAktenSachbearbeiter"
            )
            zaehler = {
                (r["k"] or "").strip().upper(): int(r["n"])
                for r in cur.fetchall()
                if (r["k"] or "").strip()
            }
    except Exception as e:
        logger.warning("RA-MICRO-Abgleich nicht möglich: %s", e)
        return jsonify({"verfuegbar": False, "kuerzel": {}, "unbekannt": []})

    with get_connection() as conn:
        bekannt = {r["kuerzel"] for r in conn.execute(
            "SELECT kuerzel FROM sachbearbeiter").fetchall()}

    unbekannt = sorted(
        ({"kuerzel": k, "akten": n} for k, n in zaehler.items() if k not in bekannt),
        key=lambda e: -e["akten"],
    )
    return jsonify({"verfuegbar": True, "kuerzel": zaehler, "unbekannt": unbekannt})
```

- [ ] **Step 4: Tests laufen lassen, GREEN bestätigen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_sachbearbeiter.py -q`
Expected: alle passed

- [ ] **Step 5: Commit**

```bash
git add "Documents/Projekt/Version 1.00/unfallakten/backend/routers/einstellungen_routes.py" \
        "Documents/Projekt/Version 1.00/unfallakten/backend/tests/test_sachbearbeiter.py"
git commit -m "feat(einstellungen): RA-MICRO-Abgleich fuer Sachbearbeiter-Kuerzel"
```

---

### Task 6: API-Aufrufe + Einstellungen-Reiter (Liste anzeigen und ändern)

**Files:**
- Modify: `frontend/src/api.js` (Block `apiEinstellungen`, ab Zeile 953)
- Create: `frontend/src/views/einstellungen/SachbearbeiterTab.jsx`
- Create: `frontend/src/views/einstellungen/SachbearbeiterTab.test.jsx`
- Modify: `frontend/src/views/EinstellungenView.jsx` (Tab-Leiste ~Zeile 299, Render ~Zeile 1308)

**Interfaces:**
- Consumes: Endpunkte aus Task 4/5
- Produces: `apiEinstellungen.sachbearbeiter()`, `.sachbearbeiterAnlegen(daten)`, `.sachbearbeiterSpeichern(kuerzel, daten)`, `.sachbearbeiterLoeschen(kuerzel)`, `.sachbearbeiterAbgleich()`; Default-Export `SachbearbeiterTab`

- [ ] **Step 1: Test schreiben**

`frontend/src/views/einstellungen/SachbearbeiterTab.test.jsx`:

```jsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const api = vi.hoisted(() => ({
  sachbearbeiter:          vi.fn(),
  sachbearbeiterAnlegen:   vi.fn(),
  sachbearbeiterSpeichern: vi.fn(),
  sachbearbeiterLoeschen:  vi.fn(),
  sachbearbeiterAbgleich:  vi.fn(),
}));
vi.mock("../../api.js", () => ({ apiEinstellungen: api }));

import SachbearbeiterTab from "./SachbearbeiterTab.jsx";

const EINTRAEGE = [
  { kuerzel: "AS", name: "Andreas Schatz", titel: "Rechtsanwalt", anrede: "herr",
    rolle: "anwalt", aktiv: 1, ignoriert: 0, dashboard_vorauswahl: 1,
    kalender_name: "RA.Schatz", sortierung: 10 },
  { kuerzel: "JH", name: "Jochen Hofmann", titel: "Rechtsanwalt", anrede: "herr",
    rolle: "anwalt", aktiv: 0, ignoriert: 0, dashboard_vorauswahl: 0,
    kalender_name: null, sortierung: 110 },
];

describe("SachbearbeiterTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.sachbearbeiter.mockResolvedValue({ eintraege: EINTRAEGE });
    api.sachbearbeiterAbgleich.mockResolvedValue({ verfuegbar: false, kuerzel: {}, unbekannt: [] });
  });

  it("zeigt alle Sachbearbeiter und kennzeichnet ausgeschiedene", async () => {
    render(<SachbearbeiterTab />);
    expect(await screen.findByDisplayValue("Andreas Schatz")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Jochen Hofmann")).toBeInTheDocument();
    expect(screen.getByText("ausgeschieden")).toBeInTheDocument();
  });

  it("speichert eine geänderte Zeile", async () => {
    api.sachbearbeiterSpeichern.mockResolvedValue({ ok: true });
    render(<SachbearbeiterTab />);
    const feld = await screen.findByDisplayValue("Andreas Schatz");
    fireEvent.change(feld, { target: { value: "Andreas Schatz jun." } });
    fireEvent.click(screen.getAllByRole("button", { name: "Speichern" })[0]);
    await waitFor(() => expect(api.sachbearbeiterSpeichern).toHaveBeenCalledWith(
      "AS", expect.objectContaining({ name: "Andreas Schatz jun." })));
  });

  it("zeigt die Fehlermeldung des Servers", async () => {
    api.sachbearbeiterSpeichern.mockRejectedValue(
      new Error("Kalendername 'RA.Schatz' ist bereits AS zugeordnet."));
    render(<SachbearbeiterTab />);
    const feld = await screen.findByDisplayValue("Andreas Schatz");
    fireEvent.change(feld, { target: { value: "X" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Speichern" })[0]);
    expect(await screen.findByText(/bereits AS zugeordnet/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Test laufen lassen, RED bestätigen**

Run: `cd frontend && npx vitest run src/views/einstellungen/SachbearbeiterTab.test.jsx`
Expected: FAIL — Datei `SachbearbeiterTab.jsx` existiert nicht

- [ ] **Step 3: API-Aufrufe und Komponente schreiben**

In `frontend/src/api.js` im Objekt `apiEinstellungen` ergänzen:

```js
  sachbearbeiter:          ()        => request('/einstellungen/sachbearbeiter'),
  sachbearbeiterAnlegen:   (daten)   => request('/einstellungen/sachbearbeiter', {
    method: 'POST', body: JSON.stringify(daten),
  }),
  sachbearbeiterSpeichern: (k, d)    => request(`/einstellungen/sachbearbeiter/${k}`, {
    method: 'PUT', body: JSON.stringify(d),
  }),
  sachbearbeiterLoeschen:  (k)       => request(`/einstellungen/sachbearbeiter/${k}`, {
    method: 'DELETE',
  }),
  sachbearbeiterAbgleich:  ()        => request('/einstellungen/sachbearbeiter/ramicro-abgleich'),
```

`frontend/src/views/einstellungen/SachbearbeiterTab.jsx`:

```jsx
import React, { useEffect, useState } from "react";
import T from "../../config/theme.js";
import { Card, Btn } from "../../components/common.jsx";
import { apiEinstellungen } from "../../api.js";

const ROLLEN  = [["anwalt", "Anwalt/Anwältin"], ["refa", "ReFa"]];
const ANREDEN = [["", "—"], ["herr", "Herr"], ["frau", "Frau"]];

const feldStil = {
  width: "100%", padding: "5px 7px", border: `1px solid ${T.border}`,
  borderRadius: 5, fontFamily: T.fontBody, fontSize: "0.9rem",
};

export default function SachbearbeiterTab() {
  const [eintraege, setEintraege] = useState([]);
  const [entwurf, setEntwurf]     = useState({});
  const [meldung, setMeldung]     = useState(null);
  const [fehler, setFehler]       = useState(null);

  const laden = () => apiEinstellungen.sachbearbeiter()
    .then(r => {
      setEintraege(r.eintraege || []);
      setEntwurf(Object.fromEntries((r.eintraege || []).map(e => [e.kuerzel, { ...e }])));
    })
    .catch(e => setFehler(`Laden fehlgeschlagen: ${e.message}`));

  useEffect(() => { laden(); }, []);

  const setzeFeld = (kuerzel, feld, wert) =>
    setEntwurf(prev => ({ ...prev, [kuerzel]: { ...prev[kuerzel], [feld]: wert } }));

  const speichern = async (kuerzel) => {
    const e = entwurf[kuerzel];
    setFehler(null);
    try {
      await apiEinstellungen.sachbearbeiterSpeichern(kuerzel, {
        name: e.name, titel: e.titel, anrede: e.anrede, rolle: e.rolle,
        aktiv: !!e.aktiv, dashboard_vorauswahl: !!e.dashboard_vorauswahl,
        kalender_name: e.kalender_name || "", sortierung: e.sortierung,
      });
      setMeldung(`${kuerzel} gespeichert.`);
      await laden();
    } catch (err) {
      setFehler(err.message);
    }
  };

  return (
    <Card>
      <div style={{ fontSize: "0.9rem", color: T.textMuted, marginBottom: 14 }}>
        Kürzel, Namen und Titel gelten für die Tagesübersicht <b>und</b> für die
        Unterschriftszeile in allen Schreiben. Ausgeschiedene Kolleginnen und Kollegen
        bitte auf „aktiv“ verzichten statt löschen — sonst zeigen Altakten nur noch das Kürzel.
      </div>

      {fehler  && <div role="alert" style={{ color: T.redText, marginBottom: 10 }}>{fehler}</div>}
      {meldung && <div style={{ color: T.green, marginBottom: 10 }}>{meldung}</div>}

      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
        <thead>
          <tr style={{ textAlign: "left", color: T.textMuted }}>
            <th style={{ padding: "6px 8px" }}>Kürzel</th>
            <th style={{ padding: "6px 8px" }}>Name</th>
            <th style={{ padding: "6px 8px" }}>Titel</th>
            <th style={{ padding: "6px 8px" }}>Anrede</th>
            <th style={{ padding: "6px 8px" }}>Rolle</th>
            <th style={{ padding: "6px 8px" }}>aktiv</th>
            <th style={{ padding: "6px 8px" }}>vorausgewählt</th>
            <th style={{ padding: "6px 8px" }}>RA-MICRO-Kalender</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {eintraege.map(e => {
            const d = entwurf[e.kuerzel] || e;
            return (
              <tr key={e.kuerzel} style={{ borderTop: `1px solid ${T.border}`,
                opacity: d.aktiv ? 1 : 0.55 }}>
                <td style={{ padding: "6px 8px", fontWeight: 600 }}>
                  {e.kuerzel}
                  {!d.aktiv && <div style={{ fontSize: "0.75rem", color: T.textMuted }}>
                    ausgeschieden</div>}
                </td>
                <td style={{ padding: "6px 8px" }}>
                  <input aria-label={`Name ${e.kuerzel}`} style={feldStil} value={d.name || ""}
                    onChange={ev => setzeFeld(e.kuerzel, "name", ev.target.value)} />
                </td>
                <td style={{ padding: "6px 8px" }}>
                  <input aria-label={`Titel ${e.kuerzel}`} style={feldStil} value={d.titel || ""}
                    onChange={ev => setzeFeld(e.kuerzel, "titel", ev.target.value)} />
                </td>
                <td style={{ padding: "6px 8px" }}>
                  <select aria-label={`Anrede ${e.kuerzel}`} style={feldStil} value={d.anrede || ""}
                    onChange={ev => setzeFeld(e.kuerzel, "anrede", ev.target.value)}>
                    {ANREDEN.map(([w, l]) => <option key={w} value={w}>{l}</option>)}
                  </select>
                </td>
                <td style={{ padding: "6px 8px" }}>
                  <select aria-label={`Rolle ${e.kuerzel}`} style={feldStil} value={d.rolle || "anwalt"}
                    onChange={ev => setzeFeld(e.kuerzel, "rolle", ev.target.value)}>
                    {ROLLEN.map(([w, l]) => <option key={w} value={w}>{l}</option>)}
                  </select>
                </td>
                <td style={{ padding: "6px 8px", textAlign: "center" }}>
                  <input type="checkbox" aria-label={`aktiv ${e.kuerzel}`} checked={!!d.aktiv}
                    onChange={ev => setzeFeld(e.kuerzel, "aktiv", ev.target.checked)} />
                </td>
                <td style={{ padding: "6px 8px", textAlign: "center" }}>
                  <input type="checkbox" aria-label={`vorausgewählt ${e.kuerzel}`}
                    checked={!!d.dashboard_vorauswahl}
                    onChange={ev => setzeFeld(e.kuerzel, "dashboard_vorauswahl", ev.target.checked)} />
                </td>
                <td style={{ padding: "6px 8px" }}>
                  <input aria-label={`Kalender ${e.kuerzel}`} style={feldStil}
                    value={d.kalender_name || ""}
                    onChange={ev => setzeFeld(e.kuerzel, "kalender_name", ev.target.value)} />
                </td>
                <td style={{ padding: "6px 8px", whiteSpace: "nowrap" }}>
                  <Btn size="sm" onClick={() => speichern(e.kuerzel)}>Speichern</Btn>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Card>
  );
}
```

In `frontend/src/views/EinstellungenView.jsx`: Import ergänzen

```jsx
import SachbearbeiterTab from "./einstellungen/SachbearbeiterTab.jsx";
```

in der Tab-Liste nach `["standardtexte", "📄 Standardtexte"],` einfügen

```jsx
            ["sachbearbeiter", "👤 Sachbearbeiter"],
```

die Zähler-Bedingung darunter um `&& id !== "sachbearbeiter"` erweitern, und neben `{tab === "standardtexte" && <StandardtexteTab />}` ergänzen:

```jsx
        {tab === "sachbearbeiter" && <SachbearbeiterTab />}
```

- [ ] **Step 4: Tests laufen lassen, GREEN bestätigen**

Run: `cd frontend && npx vitest run src/views/einstellungen/SachbearbeiterTab.test.jsx`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add "Documents/Projekt/Version 1.00/unfallakten/frontend/src/api.js" \
        "Documents/Projekt/Version 1.00/unfallakten/frontend/src/views/einstellungen/" \
        "Documents/Projekt/Version 1.00/unfallakten/frontend/src/views/EinstellungenView.jsx"
git commit -m "feat(einstellungen): Reiter Sachbearbeiter -- Liste anzeigen und aendern"
```

---

### Task 7: Anlegen und Löschen im Reiter

**Files:**
- Modify: `frontend/src/views/einstellungen/SachbearbeiterTab.jsx`
- Test: `frontend/src/views/einstellungen/SachbearbeiterTab.test.jsx`

**Interfaces:**
- Consumes: `apiEinstellungen.sachbearbeiterAnlegen`, `.sachbearbeiterLoeschen` aus Task 6
- Produces: nichts für spätere Tasks

- [ ] **Step 1: Tests ergänzen**

An `SachbearbeiterTab.test.jsx` anhängen:

```jsx
describe("SachbearbeiterTab – anlegen und löschen", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.sachbearbeiter.mockResolvedValue({ eintraege: EINTRAEGE });
    api.sachbearbeiterAbgleich.mockResolvedValue({ verfuegbar: false, kuerzel: {}, unbekannt: [] });
  });

  it("legt einen neuen Sachbearbeiter an", async () => {
    api.sachbearbeiterAnlegen.mockResolvedValue({ ok: true });
    render(<SachbearbeiterTab />);
    fireEvent.click(await screen.findByRole("button", { name: "+ Sachbearbeiter" }));
    fireEvent.change(screen.getByLabelText("Neues Kürzel"), { target: { value: "xx" } });
    fireEvent.change(screen.getByLabelText("Neuer Name"),   { target: { value: "Neue Kollegin" } });
    fireEvent.click(screen.getByRole("button", { name: "Anlegen" }));
    await waitFor(() => expect(api.sachbearbeiterAnlegen).toHaveBeenCalledWith(
      expect.objectContaining({ kuerzel: "XX", name: "Neue Kollegin" })));
  });

  it("weist ein Kürzel mit falscher Länge ohne Serveraufruf ab", async () => {
    render(<SachbearbeiterTab />);
    fireEvent.click(await screen.findByRole("button", { name: "+ Sachbearbeiter" }));
    fireEvent.change(screen.getByLabelText("Neues Kürzel"), { target: { value: "ABC" } });
    fireEvent.change(screen.getByLabelText("Neuer Name"),   { target: { value: "Test" } });
    fireEvent.click(screen.getByRole("button", { name: "Anlegen" }));
    expect(await screen.findByText(/genau zwei Großbuchstaben/)).toBeInTheDocument();
    expect(api.sachbearbeiterAnlegen).not.toHaveBeenCalled();
  });

  it("löscht erst nach Bestätigung", async () => {
    api.sachbearbeiterLoeschen.mockResolvedValue({ ok: true });
    const bestaetigen = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<SachbearbeiterTab />);
    fireEvent.click((await screen.findAllByRole("button", { name: "Löschen" }))[0]);
    expect(api.sachbearbeiterLoeschen).not.toHaveBeenCalled();
    bestaetigen.mockReturnValue(true);
    fireEvent.click(screen.getAllByRole("button", { name: "Löschen" })[0]);
    await waitFor(() => expect(api.sachbearbeiterLoeschen).toHaveBeenCalledWith("AS"));
    bestaetigen.mockRestore();
  });
});
```

- [ ] **Step 2: Tests laufen lassen, RED bestätigen**

Run: `cd frontend && npx vitest run src/views/einstellungen/SachbearbeiterTab.test.jsx`
Expected: FAIL — Knöpfe „+ Sachbearbeiter“ und „Löschen“ fehlen

- [ ] **Step 3: Implementieren**

In `SachbearbeiterTab.jsx` ergänzen — Konstante oben:

```jsx
const LEER_NEU = { kuerzel: "", name: "", titel: "", anrede: "", rolle: "anwalt",
                   aktiv: true, dashboard_vorauswahl: false, kalender_name: "", sortierung: 100 };
```

State und Funktionen in der Komponente:

```jsx
  const [neu, setNeu] = useState(null);

  const anlegen = async () => {
    const kuerzel = (neu.kuerzel || "").trim().toUpperCase();
    setFehler(null);
    if (!/^[A-Z]{2}$/.test(kuerzel)) {
      setFehler("Das Kürzel muss aus genau zwei Großbuchstaben bestehen.");
      return;
    }
    if (!(neu.name || "").trim()) {
      setFehler("Bitte einen Namen eintragen.");
      return;
    }
    try {
      await apiEinstellungen.sachbearbeiterAnlegen({ ...neu, kuerzel });
      setNeu(null);
      setMeldung(`${kuerzel} angelegt.`);
      await laden();
    } catch (err) {
      setFehler(err.message);
    }
  };

  const loeschen = async (kuerzel) => {
    if (!window.confirm(
      `${kuerzel} wirklich löschen? Altakten mit diesem Kürzel zeigen danach nur noch ` +
      `[${kuerzel}] statt des Namens. Sicherer ist es, den Haken bei „aktiv“ zu entfernen.`)) {
      return;
    }
    setFehler(null);
    try {
      await apiEinstellungen.sachbearbeiterLoeschen(kuerzel);
      setMeldung(`${kuerzel} gelöscht.`);
      await laden();
    } catch (err) {
      setFehler(err.message);
    }
  };
```

In der Aktionsspalte jeder Zeile hinter „Speichern“:

```jsx
                  <Btn variant="danger" size="sm" onClick={() => loeschen(e.kuerzel)}>Löschen</Btn>
```

Unter der Tabelle:

```jsx
      {neu ? (
        <div style={{ marginTop: 14, display: "flex", gap: 8, flexWrap: "wrap",
          alignItems: "center" }}>
          <input aria-label="Neues Kürzel" placeholder="XY" maxLength={2}
            style={{ ...feldStil, width: 70 }} value={neu.kuerzel}
            onChange={ev => setNeu({ ...neu, kuerzel: ev.target.value.toUpperCase() })} />
          <input aria-label="Neuer Name" placeholder="Vorname Nachname"
            style={{ ...feldStil, width: 220 }} value={neu.name}
            onChange={ev => setNeu({ ...neu, name: ev.target.value })} />
          <input aria-label="Neuer Titel" placeholder="Rechtsanwältin"
            style={{ ...feldStil, width: 220 }} value={neu.titel}
            onChange={ev => setNeu({ ...neu, titel: ev.target.value })} />
          <select aria-label="Neue Rolle" style={{ ...feldStil, width: 160 }} value={neu.rolle}
            onChange={ev => setNeu({ ...neu, rolle: ev.target.value })}>
            {ROLLEN.map(([w, l]) => <option key={w} value={w}>{l}</option>)}
          </select>
          <Btn onClick={anlegen}>Anlegen</Btn>
          <Btn variant="secondary" onClick={() => { setNeu(null); setFehler(null); }}>Abbrechen</Btn>
        </div>
      ) : (
        <div style={{ marginTop: 14 }}>
          <Btn onClick={() => { setNeu({ ...LEER_NEU }); setMeldung(null); }}>
            + Sachbearbeiter
          </Btn>
        </div>
      )}
```

`Btn` (`frontend/src/components/common.jsx:58`) kennt die Varianten `primary`, `secondary`, `gold` und `danger` sowie `size` in `sm|md|lg` — andere Werte ergeben `undefined` im Style.

- [ ] **Step 4: Tests laufen lassen, GREEN bestätigen**

Run: `cd frontend && npx vitest run src/views/einstellungen/SachbearbeiterTab.test.jsx`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add "Documents/Projekt/Version 1.00/unfallakten/frontend/src/views/einstellungen/"
git commit -m "feat(einstellungen): Sachbearbeiter anlegen und loeschen"
```

---

### Task 8: RA-MICRO-Abgleich im Reiter

**Files:**
- Modify: `frontend/src/views/einstellungen/SachbearbeiterTab.jsx`
- Test: `frontend/src/views/einstellungen/SachbearbeiterTab.test.jsx`

**Interfaces:**
- Consumes: `apiEinstellungen.sachbearbeiterAbgleich()` aus Task 6, `.sachbearbeiterAnlegen` aus Task 7
- Produces: nichts für spätere Tasks

- [ ] **Step 1: Tests ergänzen**

```jsx
describe("SachbearbeiterTab – RA-MICRO-Abgleich", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.sachbearbeiter.mockResolvedValue({ eintraege: EINTRAEGE });
    api.sachbearbeiterAbgleich.mockResolvedValue({
      verfuegbar: true,
      kuerzel: { AS: 3201, JH: 2182 },
      unbekannt: [{ kuerzel: "ME", akten: 20 }],
    });
  });

  it("zeigt die Aktenzahl je Zeile", async () => {
    render(<SachbearbeiterTab />);
    expect(await screen.findByText("RA-MICRO: 3.201 Akten")).toBeInTheDocument();
  });

  it("warnt nur bei Anwälten ohne Akten", async () => {
    api.sachbearbeiter.mockResolvedValue({ eintraege: [
      { ...EINTRAEGE[0], kuerzel: "CS", name: "Carina Salvagnin", rolle: "anwalt" },
      { ...EINTRAEGE[0], kuerzel: "TB", name: "Tanja Brunner",    rolle: "refa" },
    ] });
    render(<SachbearbeiterTab />);
    expect(await screen.findAllByText("keine Akten in RA-MICRO")).toHaveLength(1);
  });

  it("meldet unbekannte Kürzel und legt sie auf Klick als ignoriert an", async () => {
    api.sachbearbeiterAnlegen.mockResolvedValue({ ok: true });
    render(<SachbearbeiterTab />);
    expect(await screen.findByText(/ME \(20\)/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "ME ignorieren" }));
    await waitFor(() => expect(api.sachbearbeiterAnlegen).toHaveBeenCalledWith(
      expect.objectContaining({ kuerzel: "ME", aktiv: false, ignoriert: true })));
  });

  it("blendet den Abgleich aus, wenn RA-MICRO nicht erreichbar ist", async () => {
    api.sachbearbeiterAbgleich.mockResolvedValue({ verfuegbar: false, kuerzel: {}, unbekannt: [] });
    render(<SachbearbeiterTab />);
    await screen.findByDisplayValue("Andreas Schatz");
    expect(screen.queryByText(/RA-MICRO:/)).toBeNull();
    expect(screen.getByText(/RA-MICRO nicht erreichbar/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Tests laufen lassen, RED bestätigen**

Run: `cd frontend && npx vitest run src/views/einstellungen/SachbearbeiterTab.test.jsx`
Expected: FAIL — Abgleich wird nicht angezeigt

- [ ] **Step 3: Implementieren**

In `SachbearbeiterTab.jsx`:

```jsx
  const [abgleich, setAbgleich] = useState(null);

  const abgleichLaden = () => apiEinstellungen.sachbearbeiterAbgleich()
    .then(setAbgleich)
    .catch(() => setAbgleich({ verfuegbar: false, kuerzel: {}, unbekannt: [] }));

  useEffect(() => { abgleichLaden(); }, []);

  const ignorieren = async (kuerzel) => {
    setFehler(null);
    try {
      await apiEinstellungen.sachbearbeiterAnlegen({
        kuerzel, name: kuerzel, rolle: "anwalt", aktiv: false, ignoriert: true,
      });
      await Promise.all([laden(), abgleichLaden()]);
    } catch (err) {
      setFehler(err.message);
    }
  };

  const uebernehmen = (kuerzel) => {
    setNeu({ ...LEER_NEU, kuerzel });
    setMeldung(null);
  };
```

Hinweisblock über der Tabelle:

```jsx
      {abgleich && !abgleich.verfuegbar && (
        <div style={{ fontSize: "0.85rem", color: T.textMuted, marginBottom: 10 }}>
          RA-MICRO nicht erreichbar — der Kürzel-Abgleich steht gerade nicht zur Verfügung.
        </div>
      )}
      {abgleich?.verfuegbar && abgleich.unbekannt.length > 0 && (
        <div style={{ background: T.amberBg, border: `1px solid ${T.amberMid}`, borderRadius: 7,
          padding: "10px 12px", marginBottom: 12, fontSize: "0.88rem" }}>
          <b>In RA-MICRO gibt es Kürzel ohne Eintrag hier:</b>{" "}
          {abgleich.unbekannt.map(u => (
            <span key={u.kuerzel} style={{ marginRight: 12, whiteSpace: "nowrap" }}>
              {u.kuerzel} ({u.akten.toLocaleString("de-DE")})
              <button type="button" onClick={() => uebernehmen(u.kuerzel)}
                style={{ marginLeft: 4, background: "none", border: "none", color: T.accent,
                  cursor: "pointer" }}>anlegen</button>
              <button type="button" aria-label={`${u.kuerzel} ignorieren`}
                onClick={() => ignorieren(u.kuerzel)}
                style={{ marginLeft: 2, background: "none", border: "none", color: T.textMuted,
                  cursor: "pointer" }}>ignorieren</button>
            </span>
          ))}
        </div>
      )}
```

Statusangabe in der Kürzel-Spalte jeder Zeile, direkt unter dem „ausgeschieden“-Hinweis:

```jsx
                  {abgleich?.verfuegbar && (
                    abgleich.kuerzel[e.kuerzel]
                      ? <div style={{ fontSize: "0.75rem", color: T.textMuted }}>
                          RA-MICRO: {abgleich.kuerzel[e.kuerzel].toLocaleString("de-DE")} Akten
                        </div>
                      : (d.rolle === "anwalt" &&
                          <div style={{ fontSize: "0.75rem", color: T.amberText }}>
                            keine Akten in RA-MICRO
                          </div>)
                  )}
```

- [ ] **Step 4: Tests laufen lassen, GREEN bestätigen**

Run: `cd frontend && npx vitest run src/views/einstellungen/SachbearbeiterTab.test.jsx`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add "Documents/Projekt/Version 1.00/unfallakten/frontend/src/views/einstellungen/"
git commit -m "feat(einstellungen): RA-MICRO-Abgleich im Sachbearbeiter-Reiter"
```

---

### Task 9: Tagesübersicht zieht Chips, Vorauswahl und Tooltips aus der API

**Files:**
- Modify: `frontend/src/views/ActionBoardView.jsx` (Konstanten Zeile 13–27, Ladefunktion, Chip-Leiste)
- Test: `frontend/src/views/ActionBoardView.test.jsx`

**Interfaces:**
- Consumes: `apiEinstellungen.sachbearbeiter()` aus Task 6
- Produces: nichts für spätere Tasks

- [ ] **Step 1: Tests ergänzen**

In `ActionBoardView.test.jsx` den Mock erweitern und Tests anfügen:

```jsx
const einst = vi.hoisted(() => ({ sachbearbeiter: vi.fn() }));
vi.mock("../api", () => ({ apiDashboard: api, apiEinstellungen: einst }));
```

```jsx
const SB_LISTE = [
  { kuerzel: "AS", name: "Andreas Schatz", titel: "Rechtsanwalt", aktiv: 1, ignoriert: 0,
    dashboard_vorauswahl: 1, sortierung: 10 },
  { kuerzel: "TB", name: "Tanja Brunner", titel: "Rechtsanwalts- und Notarfachangestellte",
    aktiv: 1, ignoriert: 0, dashboard_vorauswahl: 0, sortierung: 70 },
  { kuerzel: "JH", name: "Jochen Hofmann", titel: "Rechtsanwalt", aktiv: 0, ignoriert: 0,
    dashboard_vorauswahl: 0, sortierung: 110 },
];
```

`mockOk()` um `einst.sachbearbeiter.mockResolvedValue({ eintraege: SB_LISTE });` ergänzen, dann:

```jsx
  it("baut die SB-Chips aus der Einstellungs-Liste, mit Klarnamen als Tooltip", async () => {
    mockOk();
    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    const as = await screen.findByRole("button", { name: "AS" });
    expect(as).toHaveAttribute("title", "Andreas Schatz · Rechtsanwalt");
    expect(as).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "TB" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.queryByRole("button", { name: "JH" })).toBeNull();
  });

  it("stellt die gespeicherte Auswahl wieder her und verwirft unbekannte Kürzel", async () => {
    localStorage.setItem("dashboard.aktiveSB", JSON.stringify(["TB", "ZZ"]));
    mockOk();
    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    expect(await screen.findByRole("button", { name: "TB" }))
      .toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "AS" })).toHaveAttribute("aria-pressed", "false");
  });

  it("filtert nicht, solange die Sachbearbeiter-Liste nicht geladen ist", async () => {
    mockOk({ fristen: [FRIST] });
    einst.sachbearbeiter.mockReturnValue(new Promise(() => {}));
    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    expect(await screen.findAllByRole("button", { name: /312\/26 AS/ })).not.toHaveLength(0);
  });
```

- [ ] **Step 2: Tests laufen lassen, RED bestätigen**

Run: `cd frontend && npx vitest run src/views/ActionBoardView.test.jsx`
Expected: FAIL — kein `title`-Attribut, JH-Chip fehlt nicht, Liste stammt aus `ALLE_SB`

- [ ] **Step 3: Implementieren**

In `ActionBoardView.jsx`: `ALLE_SB` und `DEFAULT_SB` löschen, `gespeicherteSB` ersetzen und Import ergänzen:

```jsx
import { apiDashboard, apiEinstellungen } from "../api";
```

```jsx
function gespeicherteAuswahl() {
  try {
    const arr = JSON.parse(localStorage.getItem(SB_KEY));
    return Array.isArray(arr) ? arr : null;
  } catch {
    return null;
  }
}

function initialeAuswahl(liste) {
  const gueltig    = new Set(liste.map((e) => e.kuerzel));
  const gespeichert = gespeicherteAuswahl();
  if (gespeichert) return new Set(gespeichert.filter((k) => gueltig.has(k)));
  return new Set(liste.filter((e) => e.dashboard_vorauswahl).map((e) => e.kuerzel));
}
```

State und Laden:

```jsx
  const [sbListe,  setSbListe]  = useState([]);
  const [aktiveSB, setAktiveSB] = useState(null);
```

```jsx
    const [r1, r2, r3, r4] = await Promise.allSettled([
      apiDashboard.termineHeute(),
      apiDashboard.fristen(),
      apiDashboard.wiedervorlagen(),
      apiEinstellungen.sachbearbeiter(),
    ]);
    if (r4.status === "fulfilled") {
      const aktive = (r4.value?.eintraege ?? []).filter((e) => e.aktiv && !e.ignoriert);
      setSbListe(aktive);
      setAktiveSB((prev) => prev ?? initialeAuswahl(aktive));
    }
```

Filter und Leerzustand:

```jsx
  const bekannteSB = new Set(sbListe.map((e) => e.kuerzel));
  const sbFilter = (e) => {
    if (!aktiveSB) return true;
    const sb = sbAusAz(e.az);
    return !sb || !bekannteSB.has(sb) || aktiveSB.has(sb);
  };
```

```jsx
      {sbListe.length > 0 && aktiveSB && aktiveSB.size === 0 ? (
```

Chip-Leiste:

```jsx
            {sbListe.map((sb) => {
              const aktiv = !!aktiveSB?.has(sb.kuerzel);
              return (
                <button
                  key={sb.kuerzel}
                  type="button"
                  title={sb.titel ? `${sb.name} · ${sb.titel}` : sb.name}
                  aria-pressed={aktiv}
                  onClick={() => toggleSB(sb.kuerzel)}
                  style={{
                    fontSize: "0.6875rem", fontWeight: 600, padding: "3px 9px", borderRadius: 999,
                    cursor: "pointer",
                    background: aktiv ? T.navy : "transparent",
                    color: aktiv ? "#FFFFFF" : T.textMuted,
                    border: `1px solid ${aktiv ? T.navy : T.borderSoft || T.border}`,
                  }}
                >
                  {sb.kuerzel}
                </button>
              );
            })}
```

`toggleSB` auf den möglicherweise noch leeren Zustand vorbereiten:

```jsx
  function toggleSB(kuerzel) {
    setAktiveSB((prev) => {
      const next = new Set(prev || []);
      next.has(kuerzel) ? next.delete(kuerzel) : next.add(kuerzel);
      localStorage.setItem(SB_KEY, JSON.stringify([...next]));
      return next;
    });
  }
```

- [ ] **Step 4: Tests laufen lassen, GREEN bestätigen**

Run: `cd frontend && npx vitest run src/views/ActionBoardView.test.jsx src/views/action_board`
Expected: alle passed

- [ ] **Step 5: Commit**

```bash
git add "Documents/Projekt/Version 1.00/unfallakten/frontend/src/views/ActionBoardView.jsx" \
        "Documents/Projekt/Version 1.00/unfallakten/frontend/src/views/ActionBoardView.test.jsx"
git commit -m "feat(dashboard): SB-Chips samt Klarnamen-Tooltips aus der Sachbearbeiter-Tabelle"
```

---

### Task 10: Vollsuiten, Dokumentation, Deploy-Hinweis

**Files:**
- Modify: `docs/CHANGELOG.md`, `docs/TODO.md`, `docs/STATE.md`

**Interfaces:**
- Consumes: alles Vorherige
- Produces: nichts

- [ ] **Step 1: Backend-Vollsuite laufen lassen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests -q`
Expected: 0 failed (Referenz vor diesem Vorhaben: 1733 passed, 20 skipped, ~7 min)

- [ ] **Step 2: Frontend-Vollsuite laufen lassen**

Run: `cd frontend && npx vitest run`
Expected: 0 failed (Referenz vorher: 516 passed)

- [ ] **Step 3: Dokumentation nachziehen**

- `docs/CHANGELOG.md`: neuer Eintrag ganz oben unter dem Datum des Abschlusses — Tabelle statt vier Listen, Migration 68 mit elf Startzeilen, JH als inaktiv aufgenommen, CRUD-Endpunkte, RA-MICRO-Abgleich nicht blockierend, Chips samt Tooltips, Testbilanz beider Suiten.
- `docs/TODO.md`: den Abschnitt „Sachbearbeiter-Verwaltung in den Einstellungen“ aus „In Arbeit“ nach „Erledigt“ verschieben, mit Verweis auf Spec und CHANGELOG.
- `docs/STATE.md`, Abschnitt 0: Deploy-Warnung ergänzen —

  > **Migration 68 (`sachbearbeiter`) vor App-Code anwenden.** Die Tabelle existiert nur per Migration. Startet der neue Code auf einer Bestands-DB ohne Migration 68, fällt das Lesen auf die eingebaute Liste zurück (Namen stimmen, aber CS/JH fehlen), und der Einstellungen-Reiter meldet beim Speichern einen Fehler. Bei Gunicorn wie immer einmal vorab migrieren.

- [ ] **Step 4: Sichtprüfung im Browser**

Reiter „Sachbearbeiter“ öffnen: elf Zeilen, JH grau als „ausgeschieden“, Aktenzahlen aus RA-MICRO, Hinweis auf ME/EM/EY. Danach Tagesübersicht öffnen: Chips zeigen beim Überfahren die Klarnamen, CS ist neu dabei, JH nicht.

- [ ] **Step 5: Commit**

```bash
git add "Documents/Projekt/Version 1.00/unfallakten/docs/"
git commit -m "docs: Sachbearbeiter-Verwaltung protokolliert (CHANGELOG, TODO, Deploy-Hinweis)"
```

---

## Self-Review

**Spec-Abdeckung:** Datenmodell + Startbefüllung → Task 1 · Modul und Fallback → Task 2 · `_KALENDER_ZU_SB` → Task 3 · Endpunkte und Validierung → Task 4 · Abgleich → Task 5 · Reiter (Liste/Ändern, Anlegen/Löschen, Abgleich) → Tasks 6–8 · Tagesübersicht inklusive Tooltips → Task 9 · Randfälle: fehlende Tabelle (Task 2), RA-MICRO offline (Tasks 5, 8), doppelter Kalendername (Task 4), Liste leer (Task 9) · Doku und Deploy → Task 10. Keine Lücke offen.

**Namenskonsistenz:** `hole_sachbearbeiter`, `alle_sachbearbeiter`, `kalender_zu_kuerzel` (Task 2) werden in Task 3 und Task 4 exakt so verwendet; `apiEinstellungen.sachbearbeiter*` (Task 6) exakt so in Tasks 7–9; Feldnamen `dashboard_vorauswahl`, `ignoriert`, `kalender_name` durchgängig identisch zwischen Migration, Endpunkten und Frontend.
