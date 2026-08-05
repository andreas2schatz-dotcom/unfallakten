# Abschluss-/Sachstandsbericht Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Neuer Dokumenttyp `abschlussbericht` — ein mandantengerechtes DOCX-Schreiben (Abschluss ↔ Sachstand per kuratiertem Schlussfeld), gespeist aus einem kanal-unabhängigen Übersichts-Objekt, plus kanzlei-interner Vorschau-Endpoint und Kurationsdialog im Frontend.

**Architecture:** Ein Service (`services/abschluss_uebersicht.py`) baut aus `akte_daten` (geladen von `word_service._lade_akte_daten`) ein reines dict-Übersichts-Objekt — **ohne eigenen DB-Zugriff** (alle DB-Daten kommen über `akte_daten`, damit der Service hermetisch testbar bleibt). Zwei Konsumenten: `word/abschlussbericht.py` (DOCX via `styling.py`/python-docx, wie Sachstandsanfrage) und `GET /akten/<az>/abschluss-uebersicht` (JSON für die Dialog-Vorschau). Die alte Auto-Summary (`word/abschluss_summary.py`) wird ersatzlos entfernt.

**Tech Stack:** Flask-Blueprints, SQLite (Migration 67), python-docx + `backend/word/styling.py`, React (WordSection/Dialog nach `StaDialog`-Muster), pytest.

**Spec:** `docs/superpowers/specs/2026-08-05-abschlussbericht-design.md` (Stand nach Codebasis-Abgleich 2026-08-05). Mockup: `docs/superpowers/specs/2026-08-05-abschlussbericht-mockup.html`.

## Global Constraints

- **RA-MICRO ist read-only** — alle Schreibzugriffe nur in SQLite.
- **Migration-Regeln:** kein `executescript()`; `conn.commit()` explizit vor + nach jedem DDL; Migration atomar — in `schema_manager.py` die Edits so reihen, dass der `MIGRATIONS`-Dict-Eintrag für 67 als **letzter** Edit landet (Reloader-Falle: erst Funktion + Dispatch, dann Dict-Eintrag).
- **Aktive Dev-DB** ist das Docker-Volume `dev-data`, nicht `backend/data/`. Nach Migration-Edits: `docker restart unfallakten-backend-dev`.
- **Keine `sys.modules`-Stubs** für Third-Party-Deps in Tests (Guard-Test existiert).
- **Keine Kommentare** im Code außer bei nicht-offensichtlichem Verhalten.
- **Zielsprache Deutsch** in UI-Texten, Docstrings, Commit-Messages.
- **Tests:** fokussierte Suiten sind maßgeblich (`python -m pytest backend/tests/<datei> -v` vom Repo-Root; der Gesamtlauf hat bekannte, hier irrelevante Failures — `docs/STATE.md`).
- **Git:** Arbeitsbranch ist `abschlussbericht` (baut bewusst auf dem ungemergten Intake-Branch auf, Entscheidung 2026-08-05). NIE `git add -A` (Git-Root ist das Home-Verzeichnis); immer explizite Pfade adden.
- **Schluss-Typen (verbatim):** `offen` · `endgueltig` · `vorbehalt_spaetfolgen` · `restposten`. Umschalt-Regel: `modus = "sachstand"` wenn `schluss_typ IS NULL OR 'offen'`, sonst `"abschluss"`.
- **Bewusste v1-Abweichungen von der Spec** (dort als „später" gedeckt): DOCX-Bewertungszeile **ohne QR-Code** (Ziel-URL/QR ist lt. Spec §15 eine noch nicht existierende Kanzlei-Einstellung); DOCX-„Verlauf" nicht aufklappbar (gibt es in Word nicht) → eigene Zahlungsverlauf-Tabelle; Dialog-Vorschau rendert eine leichte eigene Tabelle aus dem Übersichts-Objekt statt `RegulierungsTabelle` (die konsumiert den `apiAbrechnungen`-State, nicht das Objekt); **Empfänger-Override je Position** (Spec §8 „anwaltlich überschreibbar") nicht in v1 — nur die Konvention; Override kommt bei Bedarf als eigenes Feld im Kurationsschritt (in TODO.md als offen notieren, Task 10).

---

### Task 1: Migration 67 — Tabelle `abschluss_status`

**Files:**
- Modify: `backend/db/schema_manager.py` (drei Stellen, Reihenfolge beachten: ① `_run_migration_67` neben `_run_migration_66` (~Zeile 1243), ② Dispatch-`elif` nach `elif version == 66:` (~Zeile 1745), ③ **zuletzt** `MIGRATIONS`-Dict-Eintrag neben `66:` (~Zeile 320))
- Test: `backend/tests/test_migration_67.py`

**Interfaces:**
- Produces: Tabelle `abschluss_status(akte_az TEXT PK, schluss_typ TEXT DEFAULT 'offen' CHECK(...), schluss_text TEXT, verjaehrung_datum TEXT, naechste_schritte_text TEXT, kuratiert_am TEXT, kuratiert_von TEXT)` — von Task 6 (Loader) und Task 7 (PUT-Route) genutzt.

- [ ] **Step 1: Failing Test schreiben**

```python
"""Tests für Migration 67 (abschluss_status)."""
import os
import sys
import tempfile
import unittest

_tmp_dir = tempfile.mkdtemp(prefix="mig67_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _ns(test_id: str):
    db_path = os.path.join(_tmp_dir, f"{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path

    import importlib
    import backend.db.database as db_mod
    import backend.db.schema_manager as sm_mod
    for m in (db_mod, sm_mod):
        importlib.reload(m)

    sm_mod.create_schema()
    sm_mod.run_migrations()

    class NS:
        get_connection = staticmethod(db_mod.get_connection)
    return NS()


class TestMigration67(unittest.TestCase):

    def test_tabelle_und_spalten_existieren(self):
        ns = _ns("m67_spalten")
        with ns.get_connection() as conn:
            cols = {r[1] for r in conn.execute(
                "PRAGMA table_info(abschluss_status)").fetchall()}
        self.assertEqual(cols, {
            "akte_az", "schluss_typ", "schluss_text", "verjaehrung_datum",
            "naechste_schritte_text", "kuratiert_am", "kuratiert_von"})

    def test_default_schluss_typ_offen(self):
        ns = _ns("m67_default")
        with ns.get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('67/26', '', 'offen')")
            conn.execute(
                "INSERT INTO abschluss_status (akte_az) VALUES ('67/26')")
            row = conn.execute(
                "SELECT schluss_typ FROM abschluss_status "
                "WHERE akte_az = '67/26'").fetchone()
        self.assertEqual(row[0], "offen")

    def test_check_constraint_lehnt_unbekannten_typ_ab(self):
        import sqlite3
        ns = _ns("m67_check")
        with ns.get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('68/26', '', 'offen')")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO abschluss_status (akte_az, schluss_typ) "
                    "VALUES ('68/26', 'quatsch')")

    def test_migration_67_idempotent_und_versioniert(self):
        ns = _ns("m67_idem")
        from backend.db.schema_manager import _run_migration_67
        with ns.get_connection() as conn:
            _run_migration_67(conn)
            row = conn.execute(
                "SELECT version FROM schema_version WHERE version = 67"
            ).fetchone()
        self.assertIsNotNone(row)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Test laufen lassen — muss FAILen**

Run: `python -m pytest backend/tests/test_migration_67.py -v`
Expected: FAIL (`_run_migration_67` existiert nicht / Tabelle fehlt)

- [ ] **Step 3: Migration implementieren — Edit-Reihenfolge ①→②→③**

Edit ① — Funktion nach `_run_migration_66` einfügen:

```python
def _run_migration_67(conn: sqlite3.Connection) -> None:
    """
    Migration 67 - abschluss_status (Abschluss-/Sachstandsbericht).

    Ein kuratiertes Schlussfeld je Akte; schluss_typ ist zugleich der
    Abschluss/Sachstand-Umschalter. Kein executescript, explizite Commits
    um DDL (Reloader-Falle).
    """
    conn.commit()
    conn.execute(
        "CREATE TABLE IF NOT EXISTS abschluss_status ("
        " akte_az                TEXT PRIMARY KEY REFERENCES unfallakte(az),"
        " schluss_typ            TEXT NOT NULL DEFAULT 'offen'"
        "   CHECK(schluss_typ IN ('offen','endgueltig',"
        "                         'vorbehalt_spaetfolgen','restposten')),"
        " schluss_text           TEXT,"
        " verjaehrung_datum      TEXT,"
        " naechste_schritte_text TEXT,"
        " kuratiert_am           TEXT,"
        " kuratiert_von          TEXT)"
    )
    conn.commit()
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (?, ?)",
        (67, "Migration 67 - abschluss_status (Abschluss-/Sachstandsbericht)"),
    )
    logger.info("Migration 67 abgeschlossen (abschluss_status).")
```

Edit ② — Dispatch in `run_migrations()` nach `elif version == 66:`-Block:

```python
            elif version == 67:
                _run_migration_67(conn)
```

Edit ③ — **zuletzt** im `MIGRATIONS`-Dict nach dem 66er-Eintrag:

```python
    67: "-- migration_67_abschluss_status",  # Handled by _run_migration_67
```

- [ ] **Step 4: Test laufen lassen — muss PASSen**

Run: `python -m pytest backend/tests/test_migration_67.py -v`
Expected: 4 passed

- [ ] **Step 5: Dev-Backend neu starten (Migration auf Docker-Volume ausführen) und Spalten prüfen**

Run: `docker restart unfallakten-backend-dev; docker exec unfallakten-backend-dev python -c "import sqlite3,os; c=sqlite3.connect(os.environ['DB_PATH']); print([r[1] for r in c.execute('PRAGMA table_info(abschluss_status)')])"`
Expected: Liste mit den 7 Spaltennamen (nicht leer!). Wenn leer → Reloader-Falle, `docs/STATE.md` Abschnitt 0 lesen.

- [ ] **Step 6: Commit**

```bash
git add backend/db/schema_manager.py backend/tests/test_migration_67.py
git commit -m "feat(abschlussbericht): Migration 67 - Tabelle abschluss_status"
```

---

### Task 2: Service-Grundstein — `_baue_pos_map_mit_verlauf` + RA-Gebühren-Filter

**Files:**
- Create: `backend/services/abschluss_uebersicht.py`
- Test: `backend/tests/test_abschluss_uebersicht.py`

**Interfaces:**
- Consumes: `_normalise_key` aus `backend/word/abrechnungsuebersicht_service.py`; `abrechnungen`-Listenformat aus `word_service._lade_akte_daten` (je Eintrag: `datum`, `versicherung`, `gesamt_reguliert`, `haftungsquote`, `positionen: [{position_key, betrag_gefordert, betrag_reguliert, kuerzungsart_bezeichnung, kuerzung_freitext, ...}]`).
- Produces: `_baue_pos_map_mit_verlauf(abrechnungen: list) -> tuple[dict, float]` — `(pos_map, ra_gebuehren_gezahlt)`; `pos_map`: `position_key → {"reguliert": float, "zahlungen": [{"datum","betrag","versicherung"}], "kuerzung_grund": str|None}`. Zahlungen chronologisch aufsteigend. Roh-Key `ra_gebuehren` landet NICHT in der pos_map, sondern summiert im zweiten Rückgabewert.

- [ ] **Step 1: Failing Tests schreiben**

```python
"""Tests für services/abschluss_uebersicht.py (Übersichts-Objekt)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.services.abschluss_uebersicht import _baue_pos_map_mit_verlauf


def _ab(datum, versicherung, positionen, gesamt_reguliert=None, haftungsquote=100.0):
    if gesamt_reguliert is None:
        gesamt_reguliert = sum(p.get("betrag_reguliert") or 0 for p in positionen)
    return {
        "datum": datum, "versicherung": versicherung,
        "gesamt_reguliert": gesamt_reguliert, "haftungsquote": haftungsquote,
        "positionen": positionen,
    }


class TestPosMapMitVerlauf(unittest.TestCase):

    def test_summiert_und_sammelt_zahlungen_chronologisch(self):
        abrechnungen = [
            _ab("2026-03-10", "HUK", [
                {"position_key": "sv_kosten", "betrag_gefordert": 600.0,
                 "betrag_reguliert": 450.0}]),
            _ab("2026-01-15", "HUK", [
                {"position_key": "sv_kosten", "betrag_gefordert": 600.0,
                 "betrag_reguliert": 100.0}]),
        ]
        pos_map, ra = _baue_pos_map_mit_verlauf(abrechnungen)
        self.assertEqual(pos_map["sv_kosten"]["reguliert"], 550.0)
        daten = [z["datum"] for z in pos_map["sv_kosten"]["zahlungen"]]
        self.assertEqual(daten, ["2026-01-15", "2026-03-10"])
        self.assertEqual(pos_map["sv_kosten"]["zahlungen"][0]["betrag"], 100.0)
        self.assertEqual(pos_map["sv_kosten"]["zahlungen"][0]["versicherung"], "HUK")
        self.assertEqual(ra, 0.0)

    def test_key_normalisierung_wdm(self):
        abrechnungen = [_ab("2026-02-01", "VHV", [
            {"position_key": "sonstiges_wdm_3", "betrag_gefordert": 50.0,
             "betrag_reguliert": 50.0}])]
        pos_map, _ = _baue_pos_map_mit_verlauf(abrechnungen)
        self.assertIn("extra_wdm_ss3", pos_map)

    def test_ra_gebuehren_werden_gefiltert_und_summiert(self):
        abrechnungen = [_ab("2026-02-01", "VHV", [
            {"position_key": "ra_gebuehren", "betrag_gefordert": 627.13,
             "betrag_reguliert": 627.13},
            {"position_key": "nutzungsausfall", "betrag_gefordert": 300.0,
             "betrag_reguliert": 300.0}])]
        pos_map, ra = _baue_pos_map_mit_verlauf(abrechnungen)
        self.assertNotIn("sonstiges", pos_map)
        self.assertNotIn("ra_gebuehren", pos_map)
        self.assertIn("nutzungsausfall", pos_map)
        self.assertEqual(ra, 627.13)

    def test_kuerzung_grund_bezeichnung_vor_freitext(self):
        abrechnungen = [_ab("2026-02-01", "VHV", [
            {"position_key": "mietwagenkosten", "betrag_gefordert": 500.0,
             "betrag_reguliert": 350.0,
             "kuerzungsart_bezeichnung": "Überhöhter Tagessatz",
             "kuerzung_freitext": "wird ignoriert"},
            {"position_key": "standkosten", "betrag_gefordert": 200.0,
             "betrag_reguliert": 120.0,
             "kuerzung_freitext": "nur Freitext"}])]
        pos_map, _ = _baue_pos_map_mit_verlauf(abrechnungen)
        self.assertEqual(pos_map["mietwagenkosten"]["kuerzung_grund"],
                         "Überhöhter Tagessatz")
        self.assertEqual(pos_map["standkosten"]["kuerzung_grund"], "nur Freitext")

    def test_none_reguliert_wird_uebersprungen(self):
        abrechnungen = [_ab("2026-02-01", "VHV", [
            {"position_key": "sv_kosten", "betrag_gefordert": 600.0,
             "betrag_reguliert": None}], gesamt_reguliert=0.0)]
        pos_map, _ = _baue_pos_map_mit_verlauf(abrechnungen)
        self.assertNotIn("sv_kosten", pos_map)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Test laufen lassen — muss FAILen**

Run: `python -m pytest backend/tests/test_abschluss_uebersicht.py -v`
Expected: FAIL (`ModuleNotFoundError: backend.services.abschluss_uebersicht`)

- [ ] **Step 3: Implementieren**

```python
"""
Abschluss-/Sachstandsbericht – Übersichts-Objekt (kanal-unabhängig)
====================================================================
Baut aus akte_daten (word_service._lade_akte_daten) ein reines dict,
das DOCX-Renderer und Vorschau-Endpoint speist. KEIN DB-Zugriff hier —
alle Daten kommen über akte_daten (hermetisch testbar).

Spec: docs/superpowers/specs/2026-08-05-abschlussbericht-design.md §6-§11
"""
from datetime import datetime

from ..word.abrechnungsuebersicht_service import (
    _normalise_key, _schadenpositionen_rows,
)


def _parse_datum(d):
    d = (d or "").strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(d[:10], fmt)
        except ValueError:
            continue
    return datetime.max


def _baue_pos_map_mit_verlauf(abrechnungen: list) -> tuple:
    """
    Wie _baue_pos_map (Option B: Summe der Zahlungs-Inkremente je Key),
    zusätzlich je Position: Einzelzahlungen (das "wann") + Kürzungsgrund.
    Roh-Key ra_gebuehren wird VOR der Normalisierung abgefangen (er ist
    kein Schadenersatz "für Sie") und separat summiert.

    Returns: (pos_map, ra_gebuehren_gezahlt)
      pos_map: key -> {reguliert, zahlungen: [{datum, betrag, versicherung}],
                       kuerzung_grund: str|None}
    """
    pos_map = {}
    ra_gebuehren = 0.0
    for ab in sorted(abrechnungen or [], key=lambda a: _parse_datum(a.get("datum"))):
        for p in (ab.get("positionen") or []):
            raw = p.get("position_key") or p.get("art") or "sonstiges"
            reg = p.get("betrag_reguliert")
            if reg is None:
                continue
            reg_f = round(float(reg), 2)
            if raw == "ra_gebuehren":
                ra_gebuehren = round(ra_gebuehren + reg_f, 2)
                continue
            key = _normalise_key(raw)
            eintrag = pos_map.setdefault(
                key, {"reguliert": 0.0, "zahlungen": [], "kuerzung_grund": None})
            eintrag["reguliert"] = round(eintrag["reguliert"] + reg_f, 2)
            eintrag["zahlungen"].append({
                "datum":        ab.get("datum") or "",
                "betrag":       reg_f,
                "versicherung": ab.get("versicherung") or "",
            })
            grund = (p.get("kuerzungsart_bezeichnung")
                     or p.get("kuerzung_freitext") or "").strip()
            if grund:
                eintrag["kuerzung_grund"] = grund
    return pos_map, ra_gebuehren
```

- [ ] **Step 4: Test laufen lassen — muss PASSen**

Run: `python -m pytest backend/tests/test_abschluss_uebersicht.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/services/abschluss_uebersicht.py backend/tests/test_abschluss_uebersicht.py
git commit -m "feat(abschlussbericht): pos_map mit Zahlungsverlauf + RA-Gebuehren-Filter"
```

---

### Task 3: `baue_abschluss_uebersicht` — Positionen, Empfänger-Split, Summen, Modus

**Files:**
- Modify: `backend/services/abschluss_uebersicht.py`
- Test: `backend/tests/test_abschluss_uebersicht.py` (erweitern)

**Interfaces:**
- Consumes: `_baue_pos_map_mit_verlauf` (Task 2); `_schadenpositionen_rows(schaden, pos_map, vorsteuer)` liefert `[{key, label, forderung, reguliert, ist_abzug}]` (pos_map-Werte brauchen nur `["reguliert"]`).
- Produces: `baue_abschluss_uebersicht(akte_daten: dict) -> dict` — Übersichts-Objekt lt. Spec §7. Erwartete `akte_daten`-Keys: `akte` (az/aktenzeichen, unfalldatum, unfallort, haftungsquote), `mandant`, `gegner`, `schaden`, `abrechnungen`, `wdm_roh`, `abschluss_status` (dict|None, Task 6), `gebuehren_kontext` (dict|None, Task 6). Felder je Position: `key, label, kategorie, gefordert, gezahlt, differenz, kuerzung_grund, empfaenger, status, zahlungen`. `modus`: `"sachstand"` wenn `schluss_typ` fehlt/`"offen"`, sonst `"abschluss"`.

- [ ] **Step 1: Failing Tests ergänzen** (an `test_abschluss_uebersicht.py` anhängen)

```python
from backend.services.abschluss_uebersicht import baue_abschluss_uebersicht


def _akte_daten(schaden=None, abrechnungen=None, abschluss_status=None,
                gebuehren_kontext=None, mandant_vorsteuer="N"):
    return {
        "akte": {"aktenzeichen": "42/26", "unfalldatum": "2026-01-10",
                 "unfallort": "Offenbach", "haftungsquote": 100.0},
        "mandant": {"name": "Muster", "vorname": "Max", "anrede": "1",
                    "anschrift": "Weg 1", "plz": "63065", "ort": "Offenbach",
                    "vorsteuer": mandant_vorsteuer},
        "gegner": {"versicherung": "HUK-COBURG"},
        "schaden": schaden or {},
        "abrechnungen": abrechnungen or [],
        "wdm_roh": {},
        "abschluss_status": abschluss_status,
        "gebuehren_kontext": gebuehren_kontext,
    }


class TestBaueAbschlussUebersicht(unittest.TestCase):

    def test_fiktiv_fahrzeug_an_mandant(self):
        daten = _akte_daten(
            schaden={"rep_gutachten_netto": 4000.0},
            abrechnungen=[_ab("2026-02-01", "HUK", [
                {"position_key": "rep_gutachten_netto",
                 "betrag_gefordert": 4000.0, "betrag_reguliert": 4000.0}])])
        ueb = baue_abschluss_uebersicht(daten)
        pos = next(p for p in ueb["positionen"] if p["key"] == "rep_gutachten_netto")
        self.assertEqual(pos["empfaenger"], "mandant")
        self.assertEqual(pos["kategorie"], "fahrzeug")
        self.assertEqual(pos["status"], "voll")
        self.assertEqual(ueb["summen"]["an_mandant"], 4000.0)

    def test_konkret_fahrzeug_an_dritte(self):
        daten = _akte_daten(
            schaden={"rep_rechnung_netto": 3000.0, "rep_rechnung_brutto": 3570.0},
            abrechnungen=[_ab("2026-02-01", "HUK", [
                {"position_key": "rep_rechnung_netto",
                 "betrag_gefordert": 3570.0, "betrag_reguliert": 3570.0}])])
        ueb = baue_abschluss_uebersicht(daten)
        pos = next(p for p in ueb["positionen"] if p["key"] == "rep_rechnung_netto")
        self.assertEqual(pos["empfaenger"], "dritte")
        self.assertEqual(ueb["summen"]["an_dritte"], 3570.0)

    def test_totalschaden_an_mandant_mit_abzug(self):
        daten = _akte_daten(
            schaden={"wiederbeschaffung": 10000.0, "restwert": 2000.0},
            abrechnungen=[_ab("2026-02-01", "HUK", [
                {"position_key": "wiederbeschaffung",
                 "betrag_gefordert": 8000.0, "betrag_reguliert": 8000.0}])])
        ueb = baue_abschluss_uebersicht(daten)
        wbw = next(p for p in ueb["positionen"] if p["key"] == "wiederbeschaffung")
        rst = next(p for p in ueb["positionen"] if p["key"] == "restwert")
        self.assertEqual(wbw["empfaenger"], "mandant")
        self.assertEqual(rst["status"], "abzug")

    def test_kuerzung_liefert_differenz_und_grund(self):
        daten = _akte_daten(
            schaden={"mietwagenkosten": 500.0},
            abrechnungen=[_ab("2026-02-01", "HUK", [
                {"position_key": "mietwagenkosten",
                 "betrag_gefordert": 500.0, "betrag_reguliert": 350.0,
                 "kuerzungsart_bezeichnung": "Überhöhter Tagessatz"}])])
        ueb = baue_abschluss_uebersicht(daten)
        pos = next(p for p in ueb["positionen"] if p["key"] == "mietwagenkosten")
        self.assertEqual(pos["status"], "gekuerzt")
        self.assertEqual(pos["differenz"], 150.0)
        self.assertEqual(pos["kuerzung_grund"], "Überhöhter Tagessatz")
        self.assertEqual(pos["empfaenger"], "dritte")

    def test_offene_position_ohne_zahlung(self):
        daten = _akte_daten(schaden={"nutzungsausfall": 300.0})
        ueb = baue_abschluss_uebersicht(daten)
        pos = next(p for p in ueb["positionen"] if p["key"] == "nutzungsausfall")
        self.assertEqual(pos["status"], "offen")
        self.assertIsNone(pos["gezahlt"])
        self.assertEqual(pos["empfaenger"], "mandant")

    def test_modus_aus_schluss_typ(self):
        daten = _akte_daten()
        self.assertEqual(baue_abschluss_uebersicht(daten)["modus"], "sachstand")
        daten["abschluss_status"] = {"schluss_typ": "offen"}
        self.assertEqual(baue_abschluss_uebersicht(daten)["modus"], "sachstand")
        daten["abschluss_status"] = {"schluss_typ": "endgueltig",
                                     "schluss_text": "Alles erledigt."}
        ueb = baue_abschluss_uebersicht(daten)
        self.assertEqual(ueb["modus"], "abschluss")
        self.assertEqual(ueb["schluss"]["text"], "Alles erledigt.")
```

- [ ] **Step 2: Test laufen lassen — muss FAILen**

Run: `python -m pytest backend/tests/test_abschluss_uebersicht.py -v`
Expected: neue Tests FAILen (`baue_abschluss_uebersicht` nicht importierbar)

- [ ] **Step 3: Implementieren** (an `abschluss_uebersicht.py` anhängen)

```python
EMPFAENGER_DRITTE = {"sv_kosten", "mietwagenkosten", "abschleppkosten",
                     "standkosten", "kostennb"}
_FAHRZEUG_KEYS = {"rep_gutachten_netto", "rep_rechnung_netto",
                  "wiederbeschaffung", "restwert", "reparaturkosten"}


def _empfaenger_fuer(key: str) -> str:
    if key in EMPFAENGER_DRITTE:
        return "dritte"
    if key == "rep_rechnung_netto":
        return "dritte"
    return "mandant"


def baue_abschluss_uebersicht(akte_daten: dict) -> dict:
    akte     = akte_daten.get("akte") or {}
    mandant  = akte_daten.get("mandant") or {}
    gegner   = akte_daten.get("gegner") or {}
    schaden  = akte_daten.get("schaden") or {}
    abrechnungen = akte_daten.get("abrechnungen") or []
    wdm_roh  = akte_daten.get("wdm_roh") or {}
    status   = akte_daten.get("abschluss_status") or {}

    vorsteuer = str(mandant.get("vorsteuer") or "N").strip().upper() in (
        "Y", "J", "JA", "1", "TRUE")

    pos_map, ra_gebuehren = _baue_pos_map_mit_verlauf(abrechnungen)
    rows = _schadenpositionen_rows(schaden, pos_map, vorsteuer)

    positionen = []
    s_gefordert = s_gezahlt = an_mandant = an_dritte = 0.0
    for r in rows:
        key, forderung = r["key"], r["forderung"]
        ist_abzug = r["ist_abzug"]
        info = pos_map.get(key) or {}
        gezahlt = r["reguliert"]
        vorz = -1.0 if ist_abzug else 1.0
        if ist_abzug:
            pos_status = "abzug"
        elif gezahlt is None:
            pos_status = "offen"
        elif abs(forderung) - gezahlt <= 0.005:
            pos_status = "voll"
        else:
            pos_status = "gekuerzt"
        empfaenger = _empfaenger_fuer(key)
        differenz = 0.0 if ist_abzug else round(abs(forderung) - (gezahlt or 0.0), 2)
        s_gefordert += vorz * abs(forderung)
        if gezahlt is not None:
            s_gezahlt += vorz * gezahlt
            if empfaenger == "mandant":
                an_mandant += vorz * gezahlt
            else:
                an_dritte += vorz * gezahlt
        positionen.append({
            "key":            key,
            "label":          r["label"],
            "kategorie":      "fahrzeug" if key in _FAHRZEUG_KEYS else "neben",
            "gefordert":      round(abs(forderung), 2),
            "gezahlt":        gezahlt,
            "differenz":      differenz,
            "kuerzung_grund": (info.get("kuerzung_grund")
                               if pos_status == "gekuerzt" else None),
            "empfaenger":     empfaenger,
            "status":         pos_status,
            "zahlungen":      info.get("zahlungen") or [],
        })

    schluss_typ = (status.get("schluss_typ") or "offen").strip() or "offen"
    modus = "sachstand" if schluss_typ == "offen" else "abschluss"

    def _wdm(k):
        return (wdm_roh.get(k) or "").strip()

    summen = {
        "gefordert": round(s_gefordert, 2),
        "gezahlt":   round(s_gezahlt, 2),
        "differenz": round(s_gefordert - s_gezahlt, 2),
        "an_mandant": round(an_mandant, 2),
        "an_dritte":  round(an_dritte, 2),
    }

    ueb = {
        "akte": {
            "az":         akte.get("aktenzeichen") or akte.get("az") or "",
            "unfalltag":  _wdm("varU-TAG") or akte.get("unfalldatum") or "",
            "unfallort":  _wdm("varU-ORT") or akte.get("unfallort") or "",
            "kz_mandant": _wdm("varM-KZ") or (mandant.get("kfz_kennzeichen") or ""),
            "kz_gegner":  _wdm("varG-KZ") or (gegner.get("kfz_kennzeichen") or ""),
            "gegner_versicherung": (gegner.get("versicherung")
                                    or (abrechnungen[0].get("versicherung")
                                        if abrechnungen else "") or ""),
        },
        "mandant": {
            "name":      " ".join(filter(None, [mandant.get("vorname"),
                                                mandant.get("name")])).strip()
                         or (mandant.get("firma") or ""),
            "anschrift": mandant.get("anschrift") or "",
            "plz_ort":   " ".join(filter(None, [mandant.get("plz"),
                                                mandant.get("ort")])).strip(),
            "anrede":    mandant.get("anrede") or "",
        },
        "modus":      modus,
        "positionen": positionen,
        "summen":     summen,
        "schluss": {
            "typ":                    schluss_typ,
            "text":                   status.get("schluss_text") or "",
            "verjaehrung_datum":      status.get("verjaehrung_datum") or None,
            "naechste_schritte_text": status.get("naechste_schritte_text") or "",
            "kuratiert_am":           status.get("kuratiert_am") or None,
            "kuratiert_von":          status.get("kuratiert_von") or None,
        },
    }
    ueb.update(_berechne_anwaltskosten_cta_plausi(
        akte_daten, ueb, ra_gebuehren))
    return ueb
```

Hinweis: `_berechne_anwaltskosten_cta_plausi` kommt in Task 4 — für diesen Task als Minimal-Stub anlegen, damit die Tests dieses Tasks laufen:

```python
def _berechne_anwaltskosten_cta_plausi(akte_daten, ueb, ra_gebuehren):
    return {"anwaltskosten": {}, "bewertung_cta": False, "plausi": {}}
```

- [ ] **Step 4: Tests laufen lassen — alle müssen PASSen**

Run: `python -m pytest backend/tests/test_abschluss_uebersicht.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add backend/services/abschluss_uebersicht.py backend/tests/test_abschluss_uebersicht.py
git commit -m "feat(abschlussbericht): Uebersichts-Objekt - Positionen, Empfaenger-Split, Summen, Modus"
```

---

### Task 4: Anwaltskosten, `bewertung_cta`, Plausi-Kontrolle

**Files:**
- Modify: `backend/services/abschluss_uebersicht.py` (Stub aus Task 3 ersetzen)
- Test: `backend/tests/test_abschluss_uebersicht.py` (erweitern)

**Interfaces:**
- Consumes: `berechne_rvg(streitwert: float, faktor: float = 1.3, erstellt_am: str = None) -> dict` aus `backend/word/klage_service.py` (Rückgabe-Key `"gesamt"` = Brutto-Endbetrag); `gebuehren_kontext` dict aus Task 6: `{"faktor": float|None, "streitwert": float, "erstellt_am": str|None}`.
- Produces: `_berechne_anwaltskosten_cta_plausi(akte_daten, ueb, ra_gebuehren) -> dict` mit Keys `anwaltskosten` (`{rvg_betrag, gezahlt_von_gegner, getragen_von}`), `bewertung_cta` (bool), `plausi` (`{zeilensumme, reguliert_gesamt, differenz_ok}`).

- [ ] **Step 1: Failing Tests ergänzen**

```python
class TestAnwaltskostenCtaPlausi(unittest.TestCase):

    def _voll_regulierte_daten(self, schluss_typ="endgueltig", hq=100.0):
        # Achtung: _schadenpositionen_rows setzt die Unkostenpauschale
        # per Default auf 30 € — sie muss mitbezahlt sein, sonst bleibt
        # eine "offene" Position und der CTA ist nie erreichbar.
        return _akte_daten(
            schaden={"nutzungsausfall": 300.0, "unkostenpauschale": 30.0},
            abrechnungen=[_ab("2026-02-01", "HUK", [
                {"position_key": "nutzungsausfall",
                 "betrag_gefordert": 300.0, "betrag_reguliert": 300.0},
                {"position_key": "unkostenpauschale",
                 "betrag_gefordert": 30.0, "betrag_reguliert": 30.0},
                {"position_key": "ra_gebuehren",
                 "betrag_gefordert": 200.0, "betrag_reguliert": 200.0}],
                haftungsquote=hq)],
            abschluss_status={"schluss_typ": schluss_typ},
            gebuehren_kontext={"faktor": 1.3, "streitwert": 330.0,
                               "erstellt_am": "2026-01-15"})

    def test_anwaltskosten_rvg_und_gezahlt(self):
        ueb = baue_abschluss_uebersicht(self._voll_regulierte_daten())
        self.assertGreater(ueb["anwaltskosten"]["rvg_betrag"], 0)
        self.assertEqual(ueb["anwaltskosten"]["gezahlt_von_gegner"], 200.0)
        self.assertEqual(ueb["anwaltskosten"]["getragen_von"], "gegner")

    def test_anwaltskosten_ohne_kontext_none(self):
        daten = self._voll_regulierte_daten()
        daten["gebuehren_kontext"] = None
        ueb = baue_abschluss_uebersicht(daten)
        self.assertIsNone(ueb["anwaltskosten"]["rvg_betrag"])

    def test_cta_true_bei_voller_durchsetzung(self):
        ueb = baue_abschluss_uebersicht(self._voll_regulierte_daten())
        self.assertTrue(ueb["bewertung_cta"])

    def test_cta_false_bei_kuerzung(self):
        daten = self._voll_regulierte_daten()
        daten["abrechnungen"][0]["positionen"][0]["betrag_reguliert"] = 200.0
        ueb = baue_abschluss_uebersicht(daten)
        self.assertFalse(ueb["bewertung_cta"])

    def test_cta_false_bei_teilhaftung(self):
        ueb = baue_abschluss_uebersicht(
            self._voll_regulierte_daten(hq=70.0))
        self.assertFalse(ueb["bewertung_cta"])

    def test_cta_false_bei_vorbehalt(self):
        ueb = baue_abschluss_uebersicht(
            self._voll_regulierte_daten(schluss_typ="vorbehalt_spaetfolgen"))
        self.assertFalse(ueb["bewertung_cta"])

    def test_cta_false_bei_offener_position(self):
        daten = self._voll_regulierte_daten()
        daten["schaden"]["schmerzensgeld"] = 500.0
        ueb = baue_abschluss_uebersicht(daten)
        self.assertFalse(ueb["bewertung_cta"])

    def test_plausi_ok_und_abweichung(self):
        daten = self._voll_regulierte_daten()
        ueb = baue_abschluss_uebersicht(daten)
        self.assertTrue(ueb["plausi"]["differenz_ok"])
        daten["abrechnungen"][0]["gesamt_reguliert"] = 999.99
        ueb2 = baue_abschluss_uebersicht(daten)
        self.assertFalse(ueb2["plausi"]["differenz_ok"])
```

- [ ] **Step 2: Test laufen lassen — muss FAILen**

Run: `python -m pytest backend/tests/test_abschluss_uebersicht.py -v`
Expected: neue Tests FAILen (Stub liefert leere dicts)

- [ ] **Step 3: Stub ersetzen**

```python
def _berechne_anwaltskosten_cta_plausi(akte_daten, ueb, ra_gebuehren):
    akte = akte_daten.get("akte") or {}
    abrechnungen = akte_daten.get("abrechnungen") or []
    kontext = akte_daten.get("gebuehren_kontext") or None

    rvg_betrag = None
    if kontext and float(kontext.get("streitwert") or 0) > 0:
        from ..word.klage_service import berechne_rvg
        rvg = berechne_rvg(
            float(kontext["streitwert"]),
            float(kontext.get("faktor") or 1.3),
            erstellt_am=kontext.get("erstellt_am"),
        )
        rvg_betrag = rvg["gesamt"]

    anwaltskosten = {
        "rvg_betrag":         rvg_betrag,
        "gezahlt_von_gegner": round(ra_gebuehren, 2),
        "getragen_von":       "gegner",
    }

    if abrechnungen:
        volle_haftung = all(
            float(ab.get("haftungsquote") or 100) >= 100 for ab in abrechnungen)
    else:
        volle_haftung = float(akte.get("haftungsquote") or 100) >= 100

    bewertung_cta = (
        ueb["modus"] == "abschluss"
        and ueb["schluss"]["typ"] == "endgueltig"
        and ueb["summen"]["differenz"] <= 0.01
        and volle_haftung
        and not any(p["status"] == "offen" for p in ueb["positionen"])
    )

    zeilensumme = round(ueb["summen"]["gezahlt"] + ra_gebuehren, 2)
    reguliert_gesamt = round(
        sum(float(ab.get("gesamt_reguliert") or 0) for ab in abrechnungen), 2)
    plausi = {
        "zeilensumme":      zeilensumme,
        "reguliert_gesamt": reguliert_gesamt,
        "differenz_ok":     abs(zeilensumme - reguliert_gesamt) <= 0.01,
    }
    return {"anwaltskosten": anwaltskosten,
            "bewertung_cta": bewertung_cta,
            "plausi": plausi}
```

- [ ] **Step 4: Alle Service-Tests laufen lassen — müssen PASSen**

Run: `python -m pytest backend/tests/test_abschluss_uebersicht.py -v`
Expected: 19 passed

- [ ] **Step 5: Commit**

```bash
git add backend/services/abschluss_uebersicht.py backend/tests/test_abschluss_uebersicht.py
git commit -m "feat(abschlussbericht): Anwaltskosten, Bewertungs-CTA, Plausi-Kontrolle"
```

---

### Task 5: DOCX-Generator `word/abschlussbericht.py`

**Files:**
- Create: `backend/word/abschlussbericht.py`
- Test: `backend/tests/test_abschlussbericht_docx.py`

**Interfaces:**
- Consumes: `baue_abschluss_uebersicht(akte_daten)` (Task 3/4); aus `styling.py`: `erstelle_dokument, fuege_briefkopf_ein, fuege_adressblock_ein, fuege_abschnittstitel_ein, erstelle_positions_tabelle, fuege_fusszeile_ein, setze_zellen_farbe, fmt_euro, fmt_datum, NAVY, GOLD, GRAU, _rgb_hex`.
- Produces: `generiere_abschlussbericht(akte_daten: dict) -> bytes` — von Task 6 im Dispatch verdrahtet.

- [ ] **Step 1: Failing Smoke-Tests schreiben**

```python
"""DOCX-Smoke-Tests für den Abschluss-/Sachstandsbericht."""
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from docx import Document

from backend.word.abschlussbericht import generiere_abschlussbericht


def _daten(schluss_typ="endgueltig"):
    return {
        "akte": {"aktenzeichen": "42/26", "unfalldatum": "2026-01-10",
                 "unfallort": "Offenbach", "haftungsquote": 100.0},
        "mandant": {"name": "Muster", "vorname": "Max", "anrede": "1",
                    "anschrift": "Weg 1", "plz": "63065", "ort": "Offenbach",
                    "vorsteuer": "N"},
        "gegner": {"versicherung": "HUK-COBURG"},
        "schaden": {"nutzungsausfall": 300.0, "mietwagenkosten": 500.0},
        "abrechnungen": [{
            "datum": "2026-02-01", "versicherung": "HUK-COBURG",
            "gesamt_reguliert": 650.0, "haftungsquote": 100.0,
            "positionen": [
                {"position_key": "nutzungsausfall",
                 "betrag_gefordert": 300.0, "betrag_reguliert": 300.0},
                {"position_key": "mietwagenkosten",
                 "betrag_gefordert": 500.0, "betrag_reguliert": 350.0,
                 "kuerzungsart_bezeichnung": "Überhöhter Tagessatz"}],
        }],
        "wdm_roh": {},
        "abschluss_status": {"schluss_typ": schluss_typ,
                             "schluss_text": "Damit ist die Sache erledigt.",
                             "naechste_schritte_text": "Wir warten auf die HUK."},
        "gebuehren_kontext": {"faktor": 1.3, "streitwert": 800.0,
                              "erstellt_am": "2026-01-15"},
        "kanzlei": None,
    }


def _volltext(docx_bytes):
    doc = Document(io.BytesIO(docx_bytes))
    teile = [p.text for p in doc.paragraphs]
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                teile.append(cell.text)
    return "\n".join(teile)


class TestAbschlussberichtDocx(unittest.TestCase):

    def test_abschluss_variante(self):
        b = generiere_abschlussbericht(_daten("endgueltig"))
        self.assertGreater(len(b), 5000)
        text = _volltext(b)
        self.assertIn("42/26", text)
        self.assertIn("Abschluss", text)
        self.assertIn("650,00", text)
        self.assertIn("Überhöhter Tagessatz", text)
        self.assertIn("Damit ist die Sache erledigt.", text)
        self.assertIn("Mit freundlichen Grüßen", text)
        self.assertIn("Koch, Schatz", text)

    def test_sachstand_variante(self):
        b = generiere_abschlussbericht(_daten("offen"))
        text = _volltext(b)
        self.assertIn("Sachstandsbericht", text)
        self.assertIn("Wir warten auf die HUK.", text)
        self.assertNotIn("Für Sie durchgesetzt", text)

    def test_sachstand_ohne_kuratiertes_feld(self):
        daten = _daten()
        daten["abschluss_status"] = None
        b = generiere_abschlussbericht(daten)
        self.assertIn("Sachstandsbericht", _volltext(b))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Test laufen lassen — muss FAILen**

Run: `python -m pytest backend/tests/test_abschlussbericht_docx.py -v`
Expected: FAIL (`ModuleNotFoundError: backend.word.abschlussbericht`)

- [ ] **Step 3: Generator implementieren**

```python
"""
Abschluss-/Sachstandsbericht – DOCX-Renderer
=============================================
Rendert das Übersichts-Objekt (services/abschluss_uebersicht.py) im
Kanzlei-Hausstil (styling.py, wie Sachstandsanfrage). Der Renderer ist
"dumm": keine eigene Rechenlogik.

Anatomie (Spec §9): Briefkopf/Betreff → Ergebnis bzw. Arbeitsstand →
"Was bei Ihnen ankommt" (nur Abschluss) → Gegenüberstellung + Zahlungs-
verlauf → Anwaltskosten → Schluss (+ Bewertungszeile) → Grußformel.
"""
import io
from datetime import date

from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

from ..services.abschluss_uebersicht import baue_abschluss_uebersicht
from .styling import (
    erstelle_dokument, fuege_briefkopf_ein, fuege_adressblock_ein,
    fuege_abschnittstitel_ein, erstelle_positions_tabelle,
    fuege_fusszeile_ein, setze_zellen_farbe, fmt_euro, fmt_datum,
    NAVY, GRAU,
)

_GOLD_HELL = "F7F1DF"

_STATUS_LABEL = {
    "voll":     "vollständig gezahlt",
    "gekuerzt": "gekürzt",
    "offen":    "noch offen",
    "abzug":    "Abzugsposten",
}


def dateiendung() -> str:
    return "docx"


def _anrede_zeile(mandant: dict) -> str:
    anrede = (mandant.get("anrede") or "").strip()
    name = mandant.get("name") or ""
    nachname = name.split()[-1] if name else ""
    if anrede == "1" and nachname:
        return f"Sehr geehrter Herr {nachname},"
    if anrede == "2" and nachname:
        return f"Sehr geehrte Frau {nachname},"
    return "Sehr geehrte Damen und Herren,"


def _absatz(doc, text, size=10.5, bold=False, farbe=None):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.size = Pt(size)
    run.font.bold = bold
    if farbe is not None:
        run.font.color.rgb = farbe
    return p


def _ergebnis_kachel(doc, zeilen):
    tab = doc.add_table(rows=1, cols=1)
    tab.style = "Table Grid"
    zelle = tab.rows[0].cells[0]
    setze_zellen_farbe(zelle, _GOLD_HELL)
    for i, (text, gross) in enumerate(zeilen):
        p = zelle.paragraphs[0] if i == 0 else zelle.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(text)
        run.font.bold = gross
        run.font.size = Pt(13 if gross else 10)
        run.font.color.rgb = NAVY
    doc.add_paragraph()


def generiere_abschlussbericht(akte_daten: dict) -> bytes:
    ueb = baue_abschluss_uebersicht(akte_daten)
    modus = ueb["modus"]
    az = ueb["akte"]["az"]
    summen = ueb["summen"]

    doc = erstelle_dokument()
    fuege_briefkopf_ein(doc, akte_daten.get("kanzlei"))

    mandant = ueb["mandant"]
    empfaenger = [z for z in (mandant["name"], mandant["anschrift"],
                              mandant["plz_ort"]) if z]
    betreff = (f"Abschluss Ihrer Schadenersatzangelegenheit — "
               f"Unfall vom {fmt_datum(ueb['akte']['unfalltag'])}"
               if modus == "abschluss" else
               f"Sachstandsbericht zu Ihrer Schadenersatzangelegenheit — "
               f"Unfall vom {fmt_datum(ueb['akte']['unfalltag'])}")
    fuege_adressblock_ein(
        doc, empfaenger, betreff=betreff, aktenzeichen=az,
        datum=date.today().strftime("%d.%m.%Y"))

    _absatz(doc, _anrede_zeile(mandant))
    doc.add_paragraph()

    if modus == "abschluss":
        _ergebnis_kachel(doc, [
            (f"Für Sie durchgesetzt: {fmt_euro(summen['gezahlt'])}", True),
            (f"von {fmt_euro(summen['gefordert'])} geforderten "
             f"Schadenersatzansprüchen", False),
        ])
        fuege_abschnittstitel_ein(doc, "Was davon bei Ihnen ankommt")
        _absatz(doc, f"Insgesamt reguliert wurden "
                     f"{fmt_euro(summen['gezahlt'])} — davon gingen "
                     f"{fmt_euro(summen['an_mandant'])} direkt an Sie.")
        if summen["an_dritte"] > 0.005:
            _absatz(doc, f"Die übrigen {fmt_euro(summen['an_dritte'])} wurden "
                         f"unmittelbar an Dritte gezahlt (z. B. Werkstatt, "
                         f"Sachverständiger, Mietwagenunternehmen).")
    else:
        fuege_abschnittstitel_ein(doc, "Woran wir arbeiten / worauf wir warten")
        offene = [p for p in ueb["positionen"] if p["status"] == "offen"]
        erledigte = [p for p in ueb["positionen"] if p["status"] == "voll"]
        for pos in erledigte:
            _absatz(doc, f"✓ {pos['label']} — erledigt", size=10)
        for pos in offene:
            _absatz(doc, f"○ {pos['label']} — noch offen "
                         f"({fmt_euro(pos['gefordert'])})", size=10)
        if ueb["schluss"]["naechste_schritte_text"]:
            _absatz(doc, f"Nächster Schritt: "
                         f"{ueb['schluss']['naechste_schritte_text']}", bold=True)

    fuege_abschnittstitel_ein(doc, "Gegenüberstellung Ihrer Ansprüche")
    zeilen = []
    for p in ueb["positionen"]:
        grund = p["kuerzung_grund"] or _STATUS_LABEL[p["status"]]
        zeilen.append([
            p["label"],
            fmt_euro(p["gefordert"]),
            fmt_euro(p["gezahlt"]) if p["gezahlt"] is not None else "–",
            fmt_euro(p["differenz"]) if p["differenz"] > 0.005 else "–",
            grund,
        ])
    zeilen.append(["Gesamt", fmt_euro(summen["gefordert"]),
                   fmt_euro(summen["gezahlt"]),
                   fmt_euro(summen["differenz"]) if summen["differenz"] > 0.005 else "–",
                   ""])
    erstelle_positions_tabelle(
        doc, ["Position", "gefordert", "gezahlt", "Differenz", "Anmerkung"],
        zeilen, spalten_breiten=[5.0, 2.6, 2.6, 2.6, 4.2])

    verlauf = [(z["datum"], p["label"], z["betrag"], z["versicherung"])
               for p in ueb["positionen"] for z in p["zahlungen"]]
    if verlauf:
        doc.add_paragraph()
        fuege_abschnittstitel_ein(doc, "Zahlungsverlauf")
        erstelle_positions_tabelle(
            doc, ["Datum", "Position", "Betrag", "Versicherung"],
            [[fmt_datum(d), lbl, fmt_euro(b), v]
             for d, lbl, b, v in sorted(verlauf)],
            spalten_breiten=[2.6, 6.0, 2.8, 5.6])

    doc.add_paragraph()
    fuege_abschnittstitel_ein(doc, "Ihre Anwaltskosten")
    ak = ueb["anwaltskosten"]
    if ak.get("gezahlt_von_gegner"):
        _absatz(doc, f"Unsere Gebühren in Höhe von "
                     f"{fmt_euro(ak['gezahlt_von_gegner'])} wurden von der "
                     f"Gegenseite getragen — für Sie kostenfrei.")
    elif ak.get("rvg_betrag"):
        _absatz(doc, f"Unsere Gebühren nach dem RVG in Höhe von "
                     f"{fmt_euro(ak['rvg_betrag'])} werden von der Gegenseite "
                     f"getragen — für Sie kostenfrei.")
    else:
        _absatz(doc, "Unsere Gebühren werden von der Gegenseite getragen — "
                     "für Sie kostenfrei.")

    schluss = ueb["schluss"]
    if schluss["text"]:
        doc.add_paragraph()
        fuege_abschnittstitel_ein(
            doc, "Abschluss" if modus == "abschluss" else "Ausblick")
        _absatz(doc, schluss["text"])
        if (schluss["typ"] == "vorbehalt_spaetfolgen"
                and schluss["verjaehrung_datum"]):
            _absatz(doc, f"Bitte beachten Sie: Ansprüche wegen etwaiger "
                         f"Spätfolgen verjähren am "
                         f"{fmt_datum(schluss['verjaehrung_datum'])}.",
                    bold=True)

    if ueb["bewertung_cta"]:
        _absatz(doc, "Wir würden uns freuen, wenn Sie Ihre Erfahrung mit "
                     "unserer Kanzlei in einer Google-Bewertung teilen.",
                size=9, farbe=GRAU)

    doc.add_paragraph()
    _absatz(doc, "Für Rückfragen stehen wir Ihnen gerne zur Verfügung.")
    doc.add_paragraph()
    _absatz(doc, "Mit freundlichen Grüßen")
    doc.add_paragraph()
    _absatz(doc, "Rechtsanwälte Koch, Schatz & Kollegen",
            bold=True, farbe=NAVY)

    fuege_fusszeile_ein(doc, az)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
```

- [ ] **Step 4: Test laufen lassen — muss PASSen**

Run: `python -m pytest backend/tests/test_abschlussbericht_docx.py -v`
Expected: 3 passed

- [ ] **Step 5: Sichtprüfung erzeugen (manuell öffnen, kein Testschritt)**

Run: `python -c "import sys; sys.path.insert(0,'.'); from backend.tests.test_abschlussbericht_docx import _daten; from backend.word.abschlussbericht import generiere_abschlussbericht; open('abschlussbericht_probe.docx','wb').write(generiere_abschlussbericht(_daten()))"`
Expected: `abschlussbericht_probe.docx` im Repo-Root; in Word öffnen, mit Mockup vergleichen. Datei danach löschen (nicht committen!).

- [ ] **Step 6: Commit**

```bash
git add backend/word/abschlussbericht.py backend/tests/test_abschlussbericht_docx.py
git commit -m "feat(abschlussbericht): DOCX-Renderer im Hausstil (Abschluss + Sachstand)"
```

---

### Task 6: word_service-Verdrahtung (Typ, Dispatch, Datenladung)

**Files:**
- Modify: `backend/word/word_service.py` (Zeilen 37, 55, 136-141, 274, 389, 468, Rückgabe-Dict ~490, neue Loader nach `_lade_personenschaden` ~501)
- Modify: `backend/routers/word_routes.py:38-43` (Docstring-Typenliste)
- Test: `backend/tests/test_word_gueltige_typen.py` (erweitern)

**Interfaces:**
- Consumes: `generiere_abschlussbericht` (Task 5); Tabellen `abschluss_status` (Task 1), `gebuehren_berechnung`, `forderung_positionen`, `schadenpositionen`, `unfallakte.erstellt_am`.
- Produces: `akte_daten["abschluss_status"]` (dict|None) und `akte_daten["gebuehren_kontext"]` (`{"faktor": float|None, "streitwert": float, "erstellt_am": str|None}`|None) — von Task 3/4 konsumiert; Dokumenttyp `"abschlussbericht"` generierbar über `POST /akten/<az>/dokumente/word`.

- [ ] **Step 1: Failing Test ergänzen** (in `test_word_gueltige_typen.py`)

```python
def test_abschlussbericht_ist_gueltiger_typ():
    from backend.word import word_service
    assert "abschlussbericht" in word_service.gueltige_dok_typen()
    assert "abschlussbericht" in word_service._REINE_WORD_TYPEN
```

- [ ] **Step 2: Test laufen lassen — muss FAILen**

Run: `python -m pytest backend/tests/test_word_gueltige_typen.py -v`
Expected: neuer Test FAIL

- [ ] **Step 3: word_service.py verdrahten** (sechs Edits)

Edit 1 — Import (nach Zeile 37):

```python
from .abschlussbericht import generiere_abschlussbericht
```

Edit 2 — Zeile 55:

```python
_REINE_WORD_TYPEN = {"abrechnungsuebersicht", "abschlussbericht"}
```

Edit 3 — `generator_map` (Zeile 136-141):

```python
    generator_map = {
        "forderungsschreiben":   _forderung,
        "sachstandsanfrage":     generiere_sachstandsanfrage,
        "abrechnungsuebersicht": generiere_abrechnungsuebersicht,
        "abschlussbericht":      generiere_abschlussbericht,
        "klage":                 generiere_klageschrift,
    }
```

Edit 4 — Abrechnungs-Ladebedingung (Zeile 274) und die beiden weiteren Typ-Gates:

```python
    if dok_typ in ("abrechnungsuebersicht", "abschlussbericht"):
```
(ersetzt `if dok_typ == "abrechnungsuebersicht":` an Zeile 274)

```python
    if dok_typ in ("forderungsschreiben", "abrechnungsuebersicht", "abschlussbericht"):
```
(ersetzt Zeile 389 — RA-MICRO-Nachladen Mandant/Gegner-Adresse)

```python
    if dok_typ in ("abrechnungsuebersicht", "abschlussbericht"):
```
(ersetzt Zeile 468 — WDM-Kontrollvars für Unfalldaten)

Edit 5 — Rückgabe-Dict von `_lade_akte_daten` (nach `"personenschaden"`-Zeile ~497):

```python
        "abschluss_status":  _lade_abschluss_status(az) if dok_typ == "abschlussbericht" else None,
        "gebuehren_kontext": _lade_gebuehren_kontext(az) if dok_typ == "abschlussbericht" else None,
```

Edit 6 — Loader nach `_lade_personenschaden` einfügen:

```python
def _lade_abschluss_status(az: str):
    """Kuratiertes Schlussfeld (Migration 67) — None wenn nie kuratiert."""
    try:
        from ..db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM abschluss_status WHERE akte_az = ?", (az,)
            ).fetchone()
            return dict(row) if row else None
    except Exception:
        return None


def _lade_gebuehren_kontext(az: str):
    """Faktor + Streitwert für die Anwaltskosten-Zeile (Muster gebuehren_routes)."""
    try:
        from ..db.database import get_connection
        with get_connection() as conn:
            g = conn.execute(
                "SELECT faktor_final FROM gebuehren_berechnung WHERE akte_id = ?",
                (az,)).fetchone()
            fw = conn.execute(
                "SELECT SUM(betrag_gefordert) AS s FROM forderung_positionen "
                "WHERE akte_id = ?", (az,)).fetchone()
            streitwert = float(fw["s"] or 0) if fw else 0.0
            if streitwert == 0.0:
                sp = conn.execute(
                    """SELECT COALESCE(rep_rechnung_brutto, rep_gutachten_netto, 0)
                              + COALESCE(wiederbeschaffung, 0) - COALESCE(restwert, 0)
                              + COALESCE(wertminderung, 0) + COALESCE(nutzungsausfall, 0)
                              + COALESCE(mietwagenkosten, 0) + COALESCE(sv_kosten, 0)
                              + COALESCE(schmerzensgeld, 0) + COALESCE(verdienstausfall, 0)
                              + COALESCE(unkostenpauschale, 0) AS summe
                       FROM schadenpositionen WHERE akte_id = ?""",
                    (az,)).fetchone()
                streitwert = float(sp["summe"] or 0) if sp else 0.0
            ak = conn.execute(
                "SELECT erstellt_am FROM unfallakte WHERE az = ?", (az,)
            ).fetchone()
        faktor = float(g["faktor_final"]) if g and g["faktor_final"] else None
        return {
            "faktor":      faktor,
            "streitwert":  streitwert,
            "erstellt_am": ak["erstellt_am"] if ak else None,
        }
    except Exception:
        return None
```

Edit in `word_routes.py` — Docstring Zeile 38-43 um den neuen Typ ergänzen:

```python
        "typ": "forderungsschreiben"
                | "sachstandsanfrage"
                | "abrechnungsuebersicht"
                | "abschlussbericht"
```

- [ ] **Step 4: Tests laufen lassen — müssen PASSen**

Run: `python -m pytest backend/tests/test_word_gueltige_typen.py backend/tests/test_abschluss_uebersicht.py backend/tests/test_abschlussbericht_docx.py -v`
Expected: alle passed

- [ ] **Step 5: Regressionscheck Bestands-Generatoren**

Run: `python -m pytest backend/tests/test_modul5.py -v`
Expected: gleiche Ergebnisse wie vor der Änderung (bekannte Failures aus STATE.md ausgenommen; kein NEUER Failure). Vorher/nachher vergleichen: bei Abweichung analysieren, nicht ignorieren.

- [ ] **Step 6: Commit**

```bash
git add backend/word/word_service.py backend/routers/word_routes.py backend/tests/test_word_gueltige_typen.py
git commit -m "feat(abschlussbericht): Typ-Verdrahtung word_service + Datenlader (abschluss_status, gebuehren_kontext)"
```

---

### Task 7: Routen — GET Übersicht + PUT Abschluss-Status

**Files:**
- Modify: `backend/routers/akten_routes.py` (zwei neue Routen, z. B. nach dem `aktivitaeten`-Block; Imports oben ergänzen falls nötig)
- Test: `backend/tests/test_abschluss_routes.py`

**Interfaces:**
- Consumes: `baue_abschluss_uebersicht`, `word_service._lade_akte_daten`, Tabelle `abschluss_status`; bestehende Helfer in `akten_routes.py`: `_j`, `_err`, `hole_akte_by_id`, `login_erforderlich`, `g.benutzer_id`, `logge_aktivitaet`.
- Produces: `GET /akten/<az>/abschluss-uebersicht` → Übersichts-Objekt als JSON (200) / 404; `PUT /akten/<az>/abschluss-status` mit Body `{schluss_typ, schluss_text?, verjaehrung_datum?, naechste_schritte_text?}` → `{"status": "ok", "abschluss_status": {...}}` / 422 bei ungültigem Typ. Frontend (Task 9) konsumiert beide.

- [ ] **Step 1: Failing Tests schreiben** (Muster: `test_akten_intake_pending.py` — `erstelle_app` + Test-Client + Auth-Header)

```python
"""Route-Tests: GET abschluss-uebersicht + PUT abschluss-status."""
import importlib
import os
import sys
import tempfile
import unittest

_tmp_dir = tempfile.mkdtemp(prefix="abschluss_routes_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"ar_{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    os.environ["UPLOAD_DIR"] = os.path.join(_tmp_dir, f"uploads_{test_id}")

    import backend.db.database as db_mod
    import backend.models.benutzer as ben_mod
    import backend.models.akte as akte_mod
    import backend.models.dokument as dok_mod
    import backend.auth.jwt_handler as jwt_mod
    import backend.auth.middleware as mw_mod
    import backend.auth.service as svc_mod
    import backend.routers.auth_routes as routes_mod
    import backend.app as app_mod
    for m in (db_mod, ben_mod, akte_mod, dok_mod,
              jwt_mod, mw_mod, svc_mod, routes_mod, app_mod):
        importlib.reload(m)
    app = app_mod.erstelle_app({"TESTING": True})
    return app.test_client()


def _auth_header(client):
    r = client.post("/auth/login", json={
        "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
        "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!"),
    })
    assert r.status_code == 200, f"Login failed: {r.get_json()}"
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


def _seed_akte(az="55/26"):
    from backend.db.database import get_connection
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO unfallakte (az, unfalldatum, status) "
            "VALUES (?, '2026-01-10', 'offen')", (az,))


class TestAbschlussRouten(unittest.TestCase):
    def setUp(self):
        self.client = _setup(self._testMethodName)
        self.headers = _auth_header(self.client)
        _seed_akte()

    def test_get_uebersicht_liefert_objekt(self):
        r = self.client.get("/akten/55/26/abschluss-uebersicht",
                            headers=self.headers)
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertEqual(body["modus"], "sachstand")
        self.assertIn("positionen", body)
        self.assertIn("summen", body)
        self.assertIn("plausi", body)

    def test_get_uebersicht_404_bei_unbekannter_akte(self):
        r = self.client.get("/akten/99/99/abschluss-uebersicht",
                            headers=self.headers)
        self.assertEqual(r.status_code, 404)

    def test_put_status_upsert_und_modus_wechsel(self):
        r = self.client.put("/akten/55/26/abschluss-status",
                            headers=self.headers,
                            json={"schluss_typ": "endgueltig",
                                  "schluss_text": "Erledigt."})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["abschluss_status"]["schluss_typ"],
                         "endgueltig")
        r2 = self.client.get("/akten/55/26/abschluss-uebersicht",
                             headers=self.headers)
        self.assertEqual(r2.get_json()["modus"], "abschluss")
        r3 = self.client.put("/akten/55/26/abschluss-status",
                             headers=self.headers,
                             json={"schluss_typ": "offen"})
        self.assertEqual(r3.status_code, 200)

    def test_put_status_422_bei_ungueltigem_typ(self):
        r = self.client.put("/akten/55/26/abschluss-status",
                            headers=self.headers,
                            json={"schluss_typ": "quatsch"})
        self.assertEqual(r.status_code, 422)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Test laufen lassen — muss FAILen**

Run: `python -m pytest backend/tests/test_abschluss_routes.py -v`
Expected: 404-Fehler auf beiden Routen (existieren nicht)

- [ ] **Step 3: Routen implementieren** (in `akten_routes.py`, nach dem Aktivitäten-Block)

```python
# ── Abschluss-/Sachstandsbericht ─────────────────────────────────────────────

_SCHLUSS_TYPEN = {"offen", "endgueltig", "vorbehalt_spaetfolgen", "restposten"}


@akten_bp.route("/<path:akte_id>/abschluss-uebersicht", methods=["GET"])
@login_erforderlich
def abschluss_uebersicht(akte_id: str):
    """
    GET /akten/<az>/abschluss-uebersicht
    Kanzlei-internes Übersichts-Objekt (Vorschau im Kurationsdialog).
    Read-only; Spec docs/superpowers/specs/2026-08-05-abschlussbericht-design.md §7.
    """
    akte = hole_akte_by_id(akte_id)
    if not akte:
        return _err(f"Akte {akte_id} nicht gefunden.", 404)
    from ..word.word_service import _lade_akte_daten
    from ..services.abschluss_uebersicht import baue_abschluss_uebersicht
    daten = _lade_akte_daten(akte_id, akte, dok_typ="abschlussbericht")
    return _j(baue_abschluss_uebersicht(daten))


@akten_bp.route("/<path:akte_id>/abschluss-status", methods=["PUT"])
@login_erforderlich
def abschluss_status_speichern(akte_id: str):
    """
    PUT /akten/<az>/abschluss-status
    Body: { schluss_typ, schluss_text?, verjaehrung_datum?,
            naechste_schritte_text? }
    Upsert des kuratierten Schlussfelds (Migration 67).
    """
    akte = hole_akte_by_id(akte_id)
    if not akte:
        return _err(f"Akte {akte_id} nicht gefunden.", 404)
    az = akte.az

    data = request.get_json(silent=True) or {}
    schluss_typ = (data.get("schluss_typ") or "offen").strip()
    if schluss_typ not in _SCHLUSS_TYPEN:
        return _err(
            f"Ungültiger schluss_typ '{schluss_typ}'. "
            f"Erlaubt: {', '.join(sorted(_SCHLUSS_TYPEN))}", 422)

    from ..db.database import get_connection
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO abschluss_status
                (akte_az, schluss_typ, schluss_text, verjaehrung_datum,
                 naechste_schritte_text, kuratiert_am, kuratiert_von)
            VALUES (?, ?, ?, ?, ?, datetime('now','localtime'), ?)
            ON CONFLICT(akte_az) DO UPDATE SET
                schluss_typ            = excluded.schluss_typ,
                schluss_text           = excluded.schluss_text,
                verjaehrung_datum      = excluded.verjaehrung_datum,
                naechste_schritte_text = excluded.naechste_schritte_text,
                kuratiert_am           = excluded.kuratiert_am,
                kuratiert_von          = excluded.kuratiert_von
        """, (az, schluss_typ,
              (data.get("schluss_text") or "").strip() or None,
              (data.get("verjaehrung_datum") or "").strip() or None,
              (data.get("naechste_schritte_text") or "").strip() or None,
              str(getattr(g, "benutzer_id", "") or "")))
        row = conn.execute(
            "SELECT * FROM abschluss_status WHERE akte_az = ?", (az,)
        ).fetchone()

    try:
        logge_aktivitaet(
            "abschluss_status_kuratiert",
            f"Abschluss-Status gesetzt: {schluss_typ}",
            akte_id=az, benutzer_id=getattr(g, "benutzer_id", None))
    except Exception:
        pass

    return _j({"status": "ok", "abschluss_status": dict(row)})
```

- [ ] **Step 4: Tests laufen lassen — müssen PASSen**

Run: `python -m pytest backend/tests/test_abschluss_routes.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/routers/akten_routes.py backend/tests/test_abschluss_routes.py
git commit -m "feat(abschlussbericht): GET abschluss-uebersicht + PUT abschluss-status"
```

---

### Task 8: Rückbau der alten Auto-Summary

**Files:**
- Modify: `backend/routers/akten_routes.py` (Aufruf Zeile ~409 + Funktion `_erzeuge_abschluss_summary` Zeile ~521 entfernen)
- Delete: `backend/word/abschluss_summary.py`
- Test: `backend/tests/test_abschluss_routes.py` (Guard-Test ergänzen)

**Interfaces:**
- Consumes: PUT-Update-Route `/akten/<az>` (Statuswechsel), Tabelle `dokumente`.
- Produces: Statuswechsel auf `abgeschlossen` erzeugt **kein** Dokument mehr. Portal-Sync-Flagge (`_portal_flag`) bleibt unverändert erhalten.

- [ ] **Step 1: Failing Guard-Test ergänzen** (in `TestAbschlussRouten`)

```python
    def test_status_abgeschlossen_erzeugt_kein_dokument_mehr(self):
        r = self.client.put("/akten/55/26", headers=self.headers,
                            json={"status": "abgeschlossen"})
        self.assertEqual(r.status_code, 200)
        from backend.db.database import get_connection
        with get_connection() as conn:
            n = conn.execute(
                "SELECT COUNT(*) AS n FROM dokumente WHERE akte_id = '55/26'"
            ).fetchone()["n"]
        self.assertEqual(n, 0)
```

- [ ] **Step 2: Test laufen lassen — muss FAILen**

Run: `python -m pytest backend/tests/test_abschluss_routes.py -v`
Expected: neuer Test FAIL (Auto-Summary legt ein Dokument an) — falls er unerwartet PASSt, prüfen ob die Summary-Generierung im Testkontext stillschweigend fehlschlägt (`try/except` in `_erzeuge_abschluss_summary`); dann Beweis über Log/Debugger führen, den Rückbau aber trotzdem durchführen.

- [ ] **Step 3: Rückbau durchführen**

In `akten_routes.py` den Block (Zeile ~407-409) entfernen:

```python
        # aktualisiere_akte() hat bereits committed; zweite Verbindung liest korrekte Daten.
        if felder["status"] == "abgeschlossen":
            _erzeuge_abschluss_summary(akte_id)
```

Die komplette Hilfsfunktion `_erzeuge_abschluss_summary` (Zeile ~519 bis Dateiende des Blocks, inkl. Kommentar-Header `# ── Hilfsfunktion: Abschluss-Summary ──`) entfernen. Danach Datei löschen:

```bash
git rm backend/word/abschluss_summary.py
```

Prüfen, dass keine Referenzen übrig sind (Grep über `backend/` nach `abschluss_summary`):

Run: `Get-ChildItem backend -Recurse -Include *.py | Select-String "abschluss_summary"`
Expected: keine Treffer

- [ ] **Step 4: Tests laufen lassen — müssen PASSen**

Run: `python -m pytest backend/tests/test_abschluss_routes.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/routers/akten_routes.py backend/tests/test_abschluss_routes.py
git commit -m "refactor(abschlussbericht): alte Auto-Summary entfernt (ersetzt durch kuratierten Bericht)"
```

---

### Task 9: Frontend — API-Client, Kurationsdialog, WordSection-Kachel

**Files:**
- Modify: `frontend/src/api.js` (neuer Export `abschluss` neben `word`, ~Zeile 291)
- Create: `frontend/src/components/AbschlussberichtDialog.jsx`
- Modify: `frontend/src/sections/WordSection.jsx` (neue Karte + Dialog-State, Muster Sachstandsanfrage-Karte Zeile 206-233)

**Interfaces:**
- Consumes: `GET /akten/<az>/abschluss-uebersicht`, `PUT /akten/<az>/abschluss-status` (Task 7), `apiWord.generieren(akteId, "abschlussbericht")` + `apiWord.vorschau(akteId, "abschlussbericht")` (Task 6); `request`-Helper, `T`-Theme, `fmtEuro` aus `../config/utils.js`.
- Produces: Dialog-Komponente `AbschlussberichtDialog({ az, onClose })`; `apiAbschluss = { uebersicht(az), statusSpeichern(az, body) }`.

- [ ] **Step 1: API-Client ergänzen** (in `api.js` nach dem `word`-Export)

```javascript
export const abschluss = {
  uebersicht: (az) => request(`/akten/${az}/abschluss-uebersicht`),
  statusSpeichern: (az, body) =>
    request(`/akten/${az}/abschluss-status`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),
};
```

- [ ] **Step 2: Dialog-Komponente schreiben** (Layout-/State-Muster: `StaDialog.jsx`; Theme-Objekt `T` wie dort)

```javascript
/**
 * AbschlussberichtDialog – Kuration + Vorschau + Generierung
 *
 * - Lädt das Übersichts-Objekt (GET abschluss-uebersicht)
 * - Kurationsfelder: schluss_typ (= Abschluss/Sachstand-Umschalter),
 *   schluss_text, verjaehrung_datum (nur vorbehalt_spaetfolgen),
 *   naechste_schritte_text (nur Sachstand)
 * - Leichte Vorschau aus dem Übersichts-Objekt (Summen, Positionen, Plausi)
 * - "Speichern + DOCX erzeugen" → PUT abschluss-status, dann Word-Flow
 */
import React, { useState, useEffect } from "react";
import T from "../config/theme.js";
import { abschluss as apiAbschluss, word as apiWord } from "../api.js";

const TYPEN = [
  { wert: "offen",                 label: "Noch offen (Sachstandsbericht)" },
  { wert: "endgueltig",            label: "Endgültig erledigt" },
  { wert: "vorbehalt_spaetfolgen", label: "Erledigt mit Vorbehalt Spätfolgen" },
  { wert: "restposten",            label: "Erledigt bis auf Restposten" },
];

const fmtE = (v) => v == null ? "–"
  : `${Number(v).toLocaleString("de-DE", { minimumFractionDigits: 2 })} €`;

export default function AbschlussberichtDialog({ az, onClose }) {
  const [ueb,        setUeb]        = useState(null);
  const [typ,        setTyp]        = useState("offen");
  const [text,       setText]       = useState("");
  const [verjaehrung, setVerjaehrung] = useState("");
  const [schritte,   setSchritte]   = useState("");
  const [loading,    setLoading]    = useState(true);
  const [busy,       setBusy]       = useState(false);
  const [fehler,     setFehler]     = useState(null);

  useEffect(() => {
    setLoading(true);
    apiAbschluss.uebersicht(az)
      .then(data => {
        setUeb(data);
        setTyp(data.schluss?.typ || "offen");
        setText(data.schluss?.text || "");
        setVerjaehrung(data.schluss?.verjaehrung_datum || "");
        setSchritte(data.schluss?.naechste_schritte_text || "");
      })
      .catch(e => setFehler(e?.message || "Fehler beim Laden"))
      .finally(() => setLoading(false));
  }, [az]);

  const speichernUndGenerieren = async () => {
    setBusy(true);
    setFehler(null);
    try {
      await apiAbschluss.statusSpeichern(az, {
        schluss_typ: typ,
        schluss_text: text,
        verjaehrung_datum: typ === "vorbehalt_spaetfolgen" ? verjaehrung : null,
        naechste_schritte_text: typ === "offen" ? schritte : null,
      });
      await apiWord.generieren(az, "abschlussbericht");
      await apiWord.vorschau(az, "abschlussbericht");
      onClose(true);
    } catch (e) {
      setFehler(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  const istSachstand = typ === "offen";
  const modusLabel = istSachstand ? "Sachstandsbericht" : "Abschlussbericht";

  return (
    <div style={{ position:"fixed", inset:0, background:"rgba(15,23,42,0.55)",
                  display:"flex", alignItems:"center", justifyContent:"center", zIndex:1000 }}
         onClick={() => onClose(false)}>
      <div style={{ background:T.surface, borderRadius:14, width:"min(860px, 94vw)",
                    maxHeight:"92vh", overflowY:"auto", padding:"1.6rem" }}
           onClick={e => e.stopPropagation()}>

        <div style={{ display:"flex", alignItems:"center", gap:10, marginBottom:12 }}>
          <div style={{ fontFamily:T.fontDisplay, fontSize:"1.15rem", fontWeight:700, color:T.navy, flex:1 }}>
            Abschluss-/Sachstandsbericht · Az. {az}
          </div>
          <span style={{ padding:"3px 10px", borderRadius:20, fontSize:"0.8rem", fontWeight:600,
                         background: istSachstand ? "#FEF3C7" : T.greenBg,
                         color: istSachstand ? "#B45309" : T.green }}>
            {modusLabel}
          </span>
          <button onClick={() => onClose(false)}
                  style={{ border:"none", background:"none", fontSize:"1.2rem", cursor:"pointer", color:T.textMuted }}>✕</button>
        </div>

        {loading && <div style={{ padding:"2rem", color:T.textMuted }}>Lade Übersicht …</div>}
        {fehler && (
          <div style={{ background:T.redBg, border:`1px solid ${T.red}33`, borderRadius:7,
                        padding:"8px 12px", marginBottom:10, color:T.red, fontSize:"0.875rem" }}>
            ⚠ {fehler}
          </div>
        )}

        {ueb && !loading && (
          <>
            {ueb.plausi && ueb.plausi.differenz_ok === false && (
              <div style={{ background:"#FEF3C7", border:"1px solid #F59E0B44", borderRadius:7,
                            padding:"8px 12px", marginBottom:10, color:"#B45309", fontSize:"0.875rem" }}>
                ⚠ Zeilensumme ({fmtE(ueb.plausi.zeilensumme)}) weicht vom regulierten
                Gesamtbetrag ({fmtE(ueb.plausi.reguliert_gesamt)}) ab — bitte prüfen.
              </div>
            )}

            <div style={{ display:"flex", gap:14, marginBottom:14, flexWrap:"wrap" }}>
              {[
                { l:"Gefordert",       v: fmtE(ueb.summen.gefordert) },
                { l:"Gezahlt",         v: fmtE(ueb.summen.gezahlt) },
                { l:"Davon an Mandant", v: fmtE(ueb.summen.an_mandant) },
                { l:"Differenz",       v: fmtE(ueb.summen.differenz) },
              ].map((s,i) => (
                <div key={i} style={{ flex:1, minWidth:130, background:T.navyDark, borderRadius:10,
                                       padding:"10px 14px", textAlign:"center" }}>
                  <div style={{ fontFamily:"ui-monospace,monospace", fontWeight:600, color:T.white }}>{s.v}</div>
                  <div style={{ fontSize:"0.78rem", color:"rgba(255,255,255,0.5)" }}>{s.l}</div>
                </div>
              ))}
            </div>

            <table style={{ width:"100%", borderCollapse:"collapse", fontSize:"0.875rem", marginBottom:16 }}>
              <thead>
                <tr style={{ background:T.navy, color:T.white }}>
                  {["Position","gefordert","gezahlt","Differenz","Anmerkung"].map(h => (
                    <th key={h} style={{ padding:"6px 10px", textAlign: h==="Position"||h==="Anmerkung" ? "left":"right" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ueb.positionen.map(p => (
                  <tr key={p.key} style={{ borderBottom:`1px solid ${T.border}` }}>
                    <td style={{ padding:"5px 10px" }}>{p.label}</td>
                    <td style={{ padding:"5px 10px", textAlign:"right" }}>{fmtE(p.gefordert)}</td>
                    <td style={{ padding:"5px 10px", textAlign:"right" }}>{fmtE(p.gezahlt)}</td>
                    <td style={{ padding:"5px 10px", textAlign:"right",
                                 color: p.differenz > 0.005 ? T.red : T.text }}>
                      {p.differenz > 0.005 ? fmtE(p.differenz) : "–"}
                    </td>
                    <td style={{ padding:"5px 10px", color:T.textMuted }}>
                      {p.kuerzung_grund || (p.status === "offen" ? "noch offen"
                        : p.status === "voll" ? "vollständig" : "")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <label style={{ display:"block", fontSize:"0.8rem", fontWeight:600,
                            color:T.textMuted, marginBottom:5, textTransform:"uppercase" }}>
              Schluss-Status (schaltet Abschluss ↔ Sachstand)
            </label>
            <select value={typ} onChange={e => setTyp(e.target.value)}
                    style={{ width:"100%", padding:"7px 10px", borderRadius:7,
                             border:`1.5px solid ${T.border}`, marginBottom:12 }}>
              {TYPEN.map(t => <option key={t.wert} value={t.wert}>{t.label}</option>)}
            </select>

            {typ === "vorbehalt_spaetfolgen" && (
              <>
                <label style={{ display:"block", fontSize:"0.8rem", fontWeight:600,
                                color:T.textMuted, marginBottom:5 }}>Verjährung Spätfolgen</label>
                <input type="date" value={verjaehrung}
                       onChange={e => setVerjaehrung(e.target.value)}
                       style={{ padding:"7px 10px", borderRadius:7,
                                border:`1.5px solid ${T.border}`, marginBottom:12 }} />
              </>
            )}

            {istSachstand && (
              <>
                <label style={{ display:"block", fontSize:"0.8rem", fontWeight:600,
                                color:T.textMuted, marginBottom:5 }}>
                  Woran wir arbeiten / nächster Schritt
                </label>
                <textarea value={schritte} onChange={e => setSchritte(e.target.value)}
                          rows={3}
                          style={{ width:"100%", padding:"8px 10px", borderRadius:7,
                                   border:`1.5px solid ${T.border}`, marginBottom:12,
                                   fontFamily:T.fontBody }} />
              </>
            )}

            <label style={{ display:"block", fontSize:"0.8rem", fontWeight:600,
                            color:T.textMuted, marginBottom:5 }}>
              Schlusstext (anwaltlich kuratiert, erscheint im Schreiben)
            </label>
            <textarea value={text} onChange={e => setText(e.target.value)} rows={4}
                      style={{ width:"100%", padding:"8px 10px", borderRadius:7,
                               border:`1.5px solid ${T.border}`, marginBottom:16,
                               fontFamily:T.fontBody }} />

            <div style={{ display:"flex", gap:10, justifyContent:"flex-end" }}>
              <button onClick={() => onClose(false)} disabled={busy}
                      style={{ padding:"9px 16px", borderRadius:8, border:`1px solid ${T.border}`,
                               background:T.surface, cursor:"pointer" }}>
                Abbrechen
              </button>
              <button onClick={speichernUndGenerieren} disabled={busy}
                      style={{ padding:"9px 16px", borderRadius:8, border:"none",
                               background:T.navy, color:T.white, fontWeight:600,
                               cursor: busy ? "default" : "pointer", opacity: busy ? 0.7 : 1 }}>
                {busy ? "Erzeuge …" : `Speichern + ${modusLabel} (DOCX)`}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: WordSection-Karte ergänzen** (in `WordSection.jsx`)

Import oben ergänzen:

```javascript
import AbschlussberichtDialog from "../components/AbschlussberichtDialog.jsx";
```

State neben `staOffen` (Zeile ~18):

```javascript
  const [abschlussOffen, setAbschlussOffen] = useState(false);
```

Dialog-Rendering neben dem `StaDialog`-Block (Zeile ~95):

```javascript
      {abschlussOffen && (
        <AbschlussberichtDialog
          az={akte.az || akte.id}
          onClose={(generated) => { setAbschlussOffen(false); if (generated) setT("✓ Abschluss-/Sachstandsbericht erstellt."); }}
        />
      )}
```

Neue Karte im unteren Karten-Grid (neben der Sachstandsanfrage-Karte, gleicher Stil):

```javascript
          {/* Abschluss-/Sachstandsbericht */}
          <Card style={{ padding:"1.4rem", display:"flex", flexDirection:"column", gap:14 }}>
            <div style={{ display:"flex", alignItems:"flex-start", gap:12 }}>
              <div style={{ width:44, height:44, borderRadius:10, background:T.navy, display:"flex", alignItems:"center", justifyContent:"center", fontSize:"1.3rem", flexShrink:0 }}>🏁</div>
              <div style={{ flex:1 }}>
                <div style={{ fontFamily:T.fontDisplay, fontSize:"1rem", fontWeight:700, color:T.navy }}>Abschluss-/Sachstandsbericht</div>
                <div style={{ fontFamily:T.fontBody, fontSize:"0.835rem", color:T.textFaint, marginTop:2 }}>An: {mandant?.name || "Mandant"}</div>
              </div>
            </div>
            <p style={{ fontFamily:T.fontBody, fontSize:"0.935rem", color:T.textMuted, lineHeight:1.65, margin:0 }}>
              Gegenüberstellung gefordert / gezahlt für den Mandanten. Das kuratierte
              Schlussfeld schaltet zwischen Abschluss und Sachstand um.
            </p>
            <div style={{ marginTop:"auto" }}>
              <button onClick={() => setAbschlussOffen(true)}
                style={{ width:"100%", display:"flex", alignItems:"center", justifyContent:"center", gap:7, padding:"9px 14px",
                  background:T.navy, color:T.white, border:"none", borderRadius:8,
                  fontFamily:T.fontBody, fontSize:"0.965rem", fontWeight:600, cursor:"pointer" }}>
                {Ic.word} Bericht kuratieren &amp; erstellen
              </button>
            </div>
          </Card>
```

- [ ] **Step 4: Build-/Syntax-Check im Dev-Container**

Run: `docker exec unfallakten-frontend-dev npx vite build --logLevel error`
Expected: Build ohne Fehler (Warnings ok). Falls der Container kein Build-Target hat: HMR-Konsole auf Fehler prüfen (`docker logs unfallakten-frontend-dev --tail 50`).

- [ ] **Step 5: Manueller Durchstich im Browser (Dev)**

1. Akte mit Abrechnungen öffnen → Reiter mit den Word-Kacheln.
2. „Bericht kuratieren & erstellen" → Dialog zeigt Summen + Positionen; Badge „Sachstandsbericht".
3. Typ „Endgültig erledigt" wählen → Badge wechselt auf „Abschlussbericht".
4. Schlusstext eingeben → „Speichern + Abschlussbericht (DOCX)" → Download startet, DOCX öffnet mit Ergebnis-Kachel.
5. Typ zurück auf „Noch offen" + nächster Schritt → Sachstand-DOCX ohne „Für Sie durchgesetzt".

Expected: alle 5 Punkte ok (finale Abnahme durch RA Schatz bleibt eigener Gate vor Merge).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api.js frontend/src/components/AbschlussberichtDialog.jsx frontend/src/sections/WordSection.jsx
git commit -m "feat(abschlussbericht): Kurationsdialog + WordSection-Kachel + API-Client"
```

---

### Task 10: Doku-Nachführung

**Files:**
- Modify: `docs/TODO.md` (Abschnitt „In Arbeit": neuen Eintrag Abschlussbericht mit Stand + offenen Gates: Browser-Abnahme RA Schatz, Merge-Strategie mit Intake-Branch, Portal-Payload später)
- Modify: `docs/CHANGELOG.md` (Protokoll-Eintrag 2026-08-05 ff.: Migration 67, neuer Typ, Rückbau Auto-Summary, Commits)
- Modify: `docs/DATAMODEL.md` (Tabelle `abschluss_status` dokumentieren)

- [ ] **Step 1: TODO.md-Eintrag unter „In Arbeit"**

```markdown
### Abschluss-/Sachstandsbericht — implementiert, Abnahme offen (Branch `abschlussbericht`)
Neuer Typ `abschlussbericht` (Migration 67 `abschluss_status`, Service
`abschluss_uebersicht.py`, DOCX via styling.py, GET/PUT-Routen, Kurationsdialog
in WordSection). Alte Auto-Summary (`abschluss_summary.py`) ersatzlos entfernt.
Spec: `docs/superpowers/specs/2026-08-05-abschlussbericht-design.md` · Plan:
`docs/superpowers/plans/2026-08-05-abschlussbericht.md`.
**Offen:** Browser-Abnahme RA Schatz (DOCX-Sichtprüfung beide Modi); Merge nach
Intake-Branch-Klärung (Branch stapelt auf `intake-review-sichtbarkeit`);
Portal-Auslieferung via portal_sync-Payload = Stakeholder-Portal-Teilprojekt;
Empfänger-Override je Position (Spec §8) bei Bedarf nachrüsten;
Google-Bewertungs-URL/QR als Kanzlei-Einstellung (Spec §15).
```

- [ ] **Step 2: CHANGELOG- und DATAMODEL-Einträge** analog zum bestehenden Stil der Dateien ergänzen. CHANGELOG: Datum 2026-08-05 ff., Feature-Zusammenfassung, Commit-Hashes der Tasks 1-9, Testdateien. DATAMODEL-Inhalt für `abschluss_status`:

```markdown
### abschluss_status (Migration 67)
Kuratiertes Schlussfeld je Akte — `schluss_typ` ist zugleich der
Abschluss/Sachstand-Umschalter des Abschlussberichts.

| Spalte | Typ | Bedeutung |
|---|---|---|
| `akte_az` | TEXT PK → unfallakte(az) | Akte |
| `schluss_typ` | TEXT, CHECK: `offen` · `endgueltig` · `vorbehalt_spaetfolgen` · `restposten` | Default `offen` (= Sachstand) |
| `schluss_text` | TEXT | anwaltlicher Schlusstext |
| `verjaehrung_datum` | TEXT | nur bei `vorbehalt_spaetfolgen` |
| `naechste_schritte_text` | TEXT | Sachstand-Block „Woran wir arbeiten" |
| `kuratiert_am` / `kuratiert_von` | TEXT | Audit |
```

- [ ] **Step 3: Voller fokussierter Testlauf**

Run: `python -m pytest backend/tests/test_migration_67.py backend/tests/test_abschluss_uebersicht.py backend/tests/test_abschlussbericht_docx.py backend/tests/test_abschluss_routes.py backend/tests/test_word_gueltige_typen.py -v`
Expected: alle passed

- [ ] **Step 4: Commit**

```bash
git add docs/TODO.md docs/CHANGELOG.md docs/DATAMODEL.md
git commit -m "docs(abschlussbericht): TODO/CHANGELOG/DATAMODEL nachgefuehrt"
```
