# PRD-37 Dokumentenbezeichnung — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eine regelbasiert vorgeschlagene, editierbare „Dokumentenbezeichnung" im Review-Dialog, die bei Freigabe in die Akte übernommen und dort nachträglich änderbar ist.

**Architecture:** Eine reine Backend-Funktion `baue_bezeichnung` erzeugt den Vorschlag aus Klasse/Aussteller/Datum/Betrag (Registry-gesteuerte Feld-Rollen + Klassen-Labels). `hole_detail` liefert Vorschlag + gespeicherten Wert; ein PATCH-Endpoint persistiert manuelle Edits nach `intake_dokumente.bezeichnung` (NULL = lebendiger Vorschlag); die Freigabe schreibt den effektiven Wert nach `dokumente.bezeichnung` (E-Akte, nachträglich editierbar).

**Tech Stack:** Python/Flask, SQLite (Migration 59), PyYAML-Registry, React (ReviewQueueView, DokumenteSection), pytest/unittest + Vitest.

## Global Constraints

- **RA-MICRO read-only** — nur SQLite schreiben, nie in die RA-MICRO SQL Server DB.
- **Zielsprache Deutsch** — Code-Kommentare nur bei nicht-offensichtlichem Verhalten, keine überflüssigen Abstraktionen.
- **Bezeichnung nur aus inhaltlichen Dokumentdaten** — kein Eingangsdatum, kein E-Mail-Absender, außer im Sonderfall `sonstiges` (Eingangsdatum-Rückfall).
- **Migration additiv/nullable/idempotent**, explizite `conn.commit()`, **kein `executescript`** (Muster Migrationen 55–58).
- **⚠ Reloader-Migrations-Falle** (`feedback_migration_reloader_trap`): `schema_manager.py` wird über mehrere Edits geändert; der Flask-Reloader kann einen Zwischenstand als v59 stempeln, ohne dass die Spalten existieren. Mitigation in Task 4.
- **`INTAKE_REVIEW_PFLICHT` gewahrt** — neue Review-Schreibwege fassen nur `intake_dokumente` an (kein Akten-Write vor Freigabe); der einzige Akten-Schreibweg bleibt `output_adapter.schreibe_dokument` via Freigabe.
- Nächste freie Migrationsnummer: **59** (höchste bestehende = 58).

---

### Task 1: Reine Vorschlags-Funktion `baue_bezeichnung`

**Files:**
- Create: `backend/services/dokument_bezeichnung.py`
- Test: `backend/tests/test_dokument_bezeichnung.py`

**Interfaces:**
- Consumes: `backend.parsers.pdf_utils.parse_betrag`, `backend.utils.datum.parse_datum`, `backend.word.styling.fmt_euro`, `backend.intake.registry_loader.Registry`.
- Produces: `baue_bezeichnung(klasse: Optional[str], felder: dict, kontext: dict, registry) -> str`. `kontext` = `{"ist_email": bool, "eingangsdatum": Optional[str]}`. `registry` ist ein `Registry` (Attribut `.klassen: dict`) oder `None`.

- [ ] **Step 1: Write the failing test**

```python
"""PRD-37: reine Vorschlags-Funktion baue_bezeichnung."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.intake.registry_loader import Registry
from backend.services.dokument_bezeichnung import baue_bezeichnung


def _reg():
    return Registry(version="test", pfad="", klassen={
        "rechnung": {
            "klasse": "rechnung", "label": "Rechnung",
            "bezeichnung_felder": {"aussteller": "aussteller",
                                    "datum": "rechnungsdatum",
                                    "betrag": "bruttobetrag"},
        },
        "gutachten": {
            "klasse": "gutachten", "label": "Gutachten",
            "bezeichnung_felder": {"aussteller": "sv_buero",
                                    "datum": "besichtigungsdatum"},
        },
        "abrechnungsschreiben": {
            "klasse": "abrechnungsschreiben", "label": "Abrechnungsschreiben",
            "bezeichnung_felder": {"aussteller": "versicherer",
                                    "datum": "schreibdatum",
                                    "betrag": "gesamtbetrag"},
        },
        "sonstiges": {
            "klasse": "sonstiges", "label": "Sonstiges",
            "bezeichnung_felder": {"datum": "datum"},
        },
    })


class TestBaueBezeichnung(unittest.TestCase):
    def test_alle_teile(self):
        s = baue_bezeichnung("rechnung",
            {"aussteller": "Autohaus Müller", "rechnungsdatum": "12.03.2026",
             "bruttobetrag": "1.234,56"},
            {"ist_email": False, "eingangsdatum": None}, _reg())
        self.assertEqual(s, "Rechnung Autohaus Müller vom 12.03.2026 (1.234,56 €)")

    def test_fehlende_teile_fallen_weg(self):
        s = baue_bezeichnung("gutachten",
            {"besichtigungsdatum": "12.03.2026"},
            {"ist_email": False, "eingangsdatum": None}, _reg())
        self.assertEqual(s, "Gutachten vom 12.03.2026")

    def test_ohne_datum(self):
        s = baue_bezeichnung("abrechnungsschreiben",
            {"versicherer": "Allianz", "gesamtbetrag": "8.500,00"},
            {"ist_email": False, "eingangsdatum": None}, _reg())
        self.assertEqual(s, "Abrechnungsschreiben Allianz (8.500,00 €)")

    def test_betrag_als_zahl(self):
        s = baue_bezeichnung("rechnung",
            {"aussteller": "X", "bruttobetrag": 1234.5},
            {"ist_email": False, "eingangsdatum": None}, _reg())
        self.assertEqual(s, "Rechnung X (1.234,50 €)")

    def test_iso_datum_wird_deutsch(self):
        s = baue_bezeichnung("rechnung",
            {"rechnungsdatum": "2026-03-12"},
            {"ist_email": False, "eingangsdatum": None}, _reg())
        self.assertEqual(s, "Rechnung vom 12.03.2026")

    def test_unbekannte_klasse_fallback_auf_rohklasse(self):
        s = baue_bezeichnung("mahnung", {"betrag": "5,00"},
            {"ist_email": False, "eingangsdatum": None}, _reg())
        self.assertEqual(s, "mahnung")

    def test_sonstiges_email_mit_eingangsdatum(self):
        s = baue_bezeichnung("sonstiges", {},
            {"ist_email": True, "eingangsdatum": "2026-03-12 09:30:00"}, _reg())
        self.assertEqual(s, "E-Mail vom 12.03.2026")

    def test_sonstiges_schreiben_mit_schriftdatum(self):
        s = baue_bezeichnung("sonstiges", {"datum": "05.03.2026"},
            {"ist_email": False, "eingangsdatum": "2026-03-12"}, _reg())
        self.assertEqual(s, "Schreiben vom 05.03.2026")

    def test_sonstiges_schriftdatum_hat_vorrang_vor_eingang(self):
        s = baue_bezeichnung("sonstiges", {"datum": "05.03.2026"},
            {"ist_email": True, "eingangsdatum": "2026-03-12"}, _reg())
        self.assertEqual(s, "E-Mail vom 05.03.2026")

    def test_sonstiges_ohne_jedes_datum(self):
        s = baue_bezeichnung("sonstiges", {},
            {"ist_email": False, "eingangsdatum": None}, _reg())
        self.assertEqual(s, "Schreiben")

    def test_registry_none_liefert_rohklasse(self):
        s = baue_bezeichnung("rechnung", {"aussteller": "X"},
            {"ist_email": False, "eingangsdatum": None}, None)
        self.assertEqual(s, "rechnung")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_dokument_bezeichnung.py -q`
Expected: FAIL (`ModuleNotFoundError: backend.services.dokument_bezeichnung`).

- [ ] **Step 3: Write minimal implementation**

Create `backend/services/dokument_bezeichnung.py`:

```python
"""
PRD-37: Regelbasierte Dokumentenbezeichnung.

Einheitliches Schema  «Label» «Aussteller» vom «Datum» («Betrag»)  —
leere Teile fallen weg. Nur inhaltliche Dokumentdaten (kein Eingangsdatum,
kein E-Mail-Absender), Ausnahme: Klasse 'sonstiges' faellt fuers Datum auf
das Eingangsdatum zurueck und traegt ein typ-abhaengiges Label
(Schreiben/E-Mail).

Feld-Rollen (aussteller/datum/betrag) und Klassen-Label kommen aus der
Intake-Registry (klassen/*.yaml, Felder 'label' + 'bezeichnung_felder').
Reine Funktion, kein DB-/IO-Zugriff -> voll testbar.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from ..parsers.pdf_utils import parse_betrag
from ..utils.datum import parse_datum
from ..word.styling import fmt_euro


def _fmt_datum(roh: Any) -> Optional[str]:
    if roh is None:
        return None
    s = str(roh).strip()
    if not s:
        return None
    d = parse_datum(s[:10]) or parse_datum(s)
    return d.strftime("%d.%m.%Y") if d else None


def _fmt_betrag(roh: Any) -> Optional[str]:
    if roh is None:
        return None
    wert = parse_betrag(str(roh))
    if wert is None:
        return None
    return fmt_euro(wert)


def _text(roh: Any) -> Optional[str]:
    if roh is None:
        return None
    s = str(roh).strip()
    return s or None


def _zusammen(label: str, aussteller: Optional[str],
              datum: Optional[str], betrag: Optional[str]) -> str:
    teile = [label]
    if aussteller:
        teile.append(aussteller)
    if datum:
        teile.append(f"vom {datum}")
    s = " ".join(t for t in teile if t).strip()
    if betrag:
        s = f"{s} ({betrag})"
    return s.strip()


def baue_bezeichnung(klasse: Optional[str], felder: Optional[Dict[str, Any]],
                     kontext: Optional[Dict[str, Any]], registry) -> str:
    felder = felder or {}
    kontext = kontext or {}
    spec: Dict[str, Any] = {}
    if registry is not None and klasse:
        spec = (registry.klassen.get(klasse) or {})
    rollen = spec.get("bezeichnung_felder") or {}

    if klasse == "sonstiges":
        label = "E-Mail" if kontext.get("ist_email") else "Schreiben"
        datum = None
        datum_key = rollen.get("datum")
        if datum_key:
            datum = _fmt_datum(felder.get(datum_key))
        if not datum:
            datum = _fmt_datum(kontext.get("eingangsdatum"))
        return _zusammen(label, None, datum, None)

    label = spec.get("label") or klasse or "Dokument"
    aussteller = _text(felder.get(rollen["aussteller"])) if rollen.get("aussteller") else None
    datum = _fmt_datum(felder.get(rollen["datum"])) if rollen.get("datum") else None
    betrag = _fmt_betrag(felder.get(rollen["betrag"])) if rollen.get("betrag") else None
    return _zusammen(label, aussteller, datum, betrag)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_dokument_bezeichnung.py -q`
Expected: PASS (11 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/services/dokument_bezeichnung.py backend/tests/test_dokument_bezeichnung.py
git commit -m "feat(prd-37): reine Vorschlags-Funktion baue_bezeichnung"
```

---

### Task 2: Registry-Loader akzeptiert `label` + `bezeichnung_felder`

**Files:**
- Modify: `backend/intake/registry_loader.py` (`_validiere_eintrag`, ab Zeile 132)
- Test: `backend/tests/test_registry_bezeichnung.py`

**Interfaces:**
- Consumes: nichts Neues.
- Produces: geladene Klassen-Dicts dürfen optionale Schlüssel `label` (str) und `bezeichnung_felder` (dict mit optionalen Schlüsseln `aussteller`/`datum`/`betrag`, Werte str) tragen; werden fail-loud typvalidiert, wenn vorhanden. Fehlen sie, bleibt alles unverändert.

- [ ] **Step 1: Write the failing test**

```python
"""PRD-37: Registry-Loader akzeptiert optionale label/bezeichnung_felder."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.intake.registry_loader import lade_registry

_MINIMAL = """
klasse: {name}
marker: []
regex_felder: {{}}
schema: {{}}
pflichtfelder: []
kritische_felder: []
validierungsregeln: []
fristrelevanz: false
loeschfrist_jahre: 6
"""


def _schreibe(dir_, name, extra=""):
    with open(os.path.join(dir_, f"{name}.yaml"), "w", encoding="utf-8") as f:
        f.write(_MINIMAL.format(name=name) + extra)


class TestBezeichnungFelder(unittest.TestCase):
    def test_optionale_felder_werden_geladen(self):
        d = tempfile.mkdtemp(prefix="reg_bez_")
        _schreibe(d, "rechnung",
                  "label: Rechnung\n"
                  "bezeichnung_felder:\n"
                  "  aussteller: aussteller\n"
                  "  datum: rechnungsdatum\n"
                  "  betrag: bruttobetrag\n")
        reg = lade_registry(d, reload=True)
        r = reg.klassen["rechnung"]
        self.assertEqual(r["label"], "Rechnung")
        self.assertEqual(r["bezeichnung_felder"]["datum"], "rechnungsdatum")

    def test_ohne_optionale_felder_weiter_gueltig(self):
        d = tempfile.mkdtemp(prefix="reg_bez2_")
        _schreibe(d, "sonstiges")
        reg = lade_registry(d, reload=True)
        self.assertNotIn("label", reg.klassen["sonstiges"])

    def test_label_falscher_typ_faellt_auf(self):
        d = tempfile.mkdtemp(prefix="reg_bez3_")
        _schreibe(d, "rechnung", "label: [1, 2]\n")
        with self.assertRaises(RuntimeError):
            lade_registry(d, reload=True)

    def test_bezeichnung_felder_falscher_typ_faellt_auf(self):
        d = tempfile.mkdtemp(prefix="reg_bez4_")
        _schreibe(d, "rechnung", "bezeichnung_felder: nichtsdict\n")
        with self.assertRaises(RuntimeError):
            lade_registry(d, reload=True)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_registry_bezeichnung.py -q`
Expected: FAIL (`test_label_falscher_typ_faellt_auf` / `test_bezeichnung_felder_falscher_typ_faellt_auf` erwarten RuntimeError, der noch nicht geworfen wird).

- [ ] **Step 3: Write minimal implementation**

In `backend/intake/registry_loader.py`, am Ende von `_validiere_eintrag` (nach dem `loeschfrist_jahre`-Block, vor dem Funktionsende bei Zeile 195) einfügen:

```python
    if "label" in data and not isinstance(data["label"], str):
        raise RuntimeError(
            f"'label' muss ein String sein in {dateiname}"
        )
    if "bezeichnung_felder" in data:
        bf = data["bezeichnung_felder"]
        if not isinstance(bf, dict):
            raise RuntimeError(
                f"'bezeichnung_felder' muss ein Mapping sein in {dateiname}"
            )
        for rolle, feld in bf.items():
            if rolle not in ("aussteller", "datum", "betrag"):
                raise RuntimeError(
                    f"'bezeichnung_felder' Rolle {rolle!r} unbekannt in "
                    f"{dateiname} (erlaubt: aussteller, datum, betrag)"
                )
            if not isinstance(feld, str) or not feld:
                raise RuntimeError(
                    f"'bezeichnung_felder.{rolle}' muss ein nichtleerer "
                    f"String sein in {dateiname}"
                )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_registry_bezeichnung.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/intake/registry_loader.py backend/tests/test_registry_bezeichnung.py
git commit -m "feat(prd-37): Registry-Loader validiert optionale label/bezeichnung_felder"
```

---

### Task 2 verifizieren: bestehende Registry-Tests bleiben grün

- [ ] **Step 1: Run the registry + golden suite**

Run: `python -m pytest backend/tests/test_registry_golden.py backend/tests/test_s16a_golden_e2e.py -q`
Expected: PASS (unverändert grün — der Loader-Zusatz ist additiv).

---

### Task 3: Label + `bezeichnung_felder` in allen 8 Klassen-YAMLs

**Files:**
- Modify: `backend/registry/klassen/rechnung.yaml`, `sv_rechnung.yaml`, `abschlepprechnung.yaml`, `standkostenrechnung.yaml`, `abrechnungsschreiben.yaml`, `gutachten.yaml`, `pruefbericht.yaml`, `sonstiges.yaml`
- Test: `backend/tests/test_registry_bezeichnung.py` (Erweiterung um einen Vollständigkeits-Test gegen die echte Registry)

**Interfaces:**
- Consumes: Task 2 (Loader akzeptiert die Felder).
- Produces: jede Klasse trägt ein `label`; alle außer `pruefbericht` tragen mindestens eine `bezeichnung_felder`-Rolle.

- [ ] **Step 1: Write the failing test**

Am Ende von `backend/tests/test_registry_bezeichnung.py` (vor `if __name__`) eine Klasse ergänzen:

```python
class TestEchteRegistryHatLabels(unittest.TestCase):
    def test_jede_klasse_hat_label(self):
        from backend.intake.registry_loader import lade_registry, standard_pfad
        reg = lade_registry(standard_pfad(), reload=True)
        for name, spec in reg.klassen.items():
            self.assertIn("label", spec, f"{name} ohne label")
            self.assertTrue(spec["label"], f"{name} label leer")

    def test_kern_rechnungsklassen_haben_betrag_rolle(self):
        from backend.intake.registry_loader import lade_registry, standard_pfad
        reg = lade_registry(standard_pfad(), reload=True)
        for name in ("rechnung", "sv_rechnung", "abschlepprechnung",
                     "standkostenrechnung", "abrechnungsschreiben"):
            bf = reg.klassen[name].get("bezeichnung_felder") or {}
            self.assertIn("betrag", bf, f"{name} ohne Betrag-Rolle")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_registry_bezeichnung.py::TestEchteRegistryHatLabels -q`
Expected: FAIL (`... ohne label`).

- [ ] **Step 3: Anhängen der Felder an jede YAML**

Jeweils am Dateiende anhängen (zwei Leerzeilen Abstand nicht nötig, YAML ist Mapping):

`rechnung.yaml`:
```yaml
label: Rechnung
bezeichnung_felder:
  aussteller: aussteller
  datum: rechnungsdatum
  betrag: bruttobetrag
```

`sv_rechnung.yaml`:
```yaml
label: SV-Rechnung
bezeichnung_felder:
  aussteller: sv_buero
  datum: rechnungsdatum
  betrag: bruttobetrag
```

`abschlepprechnung.yaml`:
```yaml
label: Abschlepprechnung
bezeichnung_felder:
  aussteller: aussteller
  datum: rechnungsdatum
  betrag: bruttobetrag
```

`standkostenrechnung.yaml`:
```yaml
label: Standkostenrechnung
bezeichnung_felder:
  aussteller: aussteller
  datum: rechnungsdatum
  betrag: bruttobetrag
```

`abrechnungsschreiben.yaml`:
```yaml
label: Abrechnungsschreiben
bezeichnung_felder:
  aussteller: versicherer
  datum: schreibdatum
  betrag: gesamtbetrag
```

`gutachten.yaml`:
```yaml
label: Gutachten
bezeichnung_felder:
  aussteller: sv_buero
  datum: besichtigungsdatum
```

`pruefbericht.yaml`:
```yaml
label: Prüfbericht
bezeichnung_felder:
  aussteller: pruefdienstleister
```

`sonstiges.yaml`:
```yaml
label: Sonstiges
bezeichnung_felder:
  datum: datum
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_registry_bezeichnung.py -q`
Expected: PASS (6 tests). Zusätzlich Golden-Suite gegenprüfen:
Run: `python -m pytest backend/tests/test_registry_golden.py -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/registry/klassen/*.yaml backend/tests/test_registry_bezeichnung.py
git commit -m "feat(prd-37): Klassen-Labels + bezeichnung_felder in allen Registry-YAMLs"
```

---

### Task 4: Migration 59 — Spalten `intake_dokumente.bezeichnung` + `dokumente.bezeichnung`

**Files:**
- Modify: `backend/db/schema_manager.py` (MIGRATIONS-Dict ~Zeile 312, neuer Handler nach `_run_migration_58` ~Zeile 961, Dispatcher `elif version == 58` ~Zeile 1371)
- Modify: `backend/models/dokument.py` (Dataclass `Dokument`, Zeile 88–105)
- Test: `backend/tests/test_migration_59.py`

**Interfaces:**
- Consumes: nichts.
- Produces: Spalten `intake_dokumente.bezeichnung TEXT` + `dokumente.bezeichnung TEXT`; `Dokument`-Dataclass hat Feld `bezeichnung: Optional[str] = None` (damit `Dokument.from_row` sie lädt).

**⚠ Reloader-Falle:** Diese Datei wird über drei Edits geändert. Wenn der Dev-Server läuft, kann der Reloader zwischen den Edits neu laden und v59 stempeln, bevor der Handler existiert → `schema_version=59` ohne Spalten. **Vorgehen:** Dev-Server vor den Edits stoppen ODER nach Abschluss auf der aktiven Volume-DB verifizieren (`PRAGMA table_info`) und die Spalten ggf. per `ALTER TABLE` nachziehen. Der Test unten läuft ohnehin gegen eine frische Temp-DB.

- [ ] **Step 1: Write the failing test**

```python
"""PRD-37: Migration 59 legt bezeichnung-Spalten an."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestMigration59(unittest.TestCase):
    def setUp(self):
        fd, self._db = tempfile.mkstemp(prefix="mig59_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        self._alt = _db.DB_PATH
        _db.DB_PATH = self._db
        os.environ["DB_PATH"] = self._db
        from backend.db.schema_manager import init_db
        init_db()

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt
        os.environ.pop("DB_PATH", None)
        try:
            os.unlink(self._db)
        except OSError:
            pass

    def _cols(self, tabelle):
        from backend.db.database import get_connection
        with get_connection() as conn:
            return {r[1] for r in conn.execute(
                f"PRAGMA table_info({tabelle})").fetchall()}

    def test_intake_bezeichnung(self):
        self.assertIn("bezeichnung", self._cols("intake_dokumente"))

    def test_dokumente_bezeichnung(self):
        self.assertIn("bezeichnung", self._cols("dokumente"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_migration_59.py -q`
Expected: FAIL (`AssertionError: 'bezeichnung' not found`).

- [ ] **Step 3: Implementierung (drei Edits in schema_manager.py + Dataclass)**

3a. MIGRATIONS-Dict-Eintrag nach Zeile 312 (`58: ...`):
```python
    59: "-- migration_59_dokument_bezeichnung",  # Handled by _run_migration_59 (PRD-37 Dokumentenbezeichnung)
```

3b. Neuer Handler direkt nach `_run_migration_58` (nach Zeile 961):
```python
def _run_migration_59(conn: sqlite3.Connection) -> None:
    """
    Migration 59 (PRD-37) - bezeichnung-Spalten fuer Intake + Akte.

    Sprechende Dokumentenbezeichnung: intake_dokumente.bezeichnung haelt den
    im Review bestaetigten/editierten Titel (NULL = lebendiger Vorschlag);
    dokumente.bezeichnung ist der bei Freigabe uebernommene Titel in der Akte
    (dort nachtraeglich editierbar).

    Zwei additive ALTER TABLE, nullable TEXT, kein Datenverlust. Idempotent per
    PRAGMA table_info. Explizites conn.commit() (feedback_migration_executescript).
    """
    intake_spalten = {
        r[1] for r in conn.execute(
            "PRAGMA table_info(intake_dokumente)"
        ).fetchall()
    }
    if "bezeichnung" not in intake_spalten:
        conn.commit()
        conn.execute(
            "ALTER TABLE intake_dokumente ADD COLUMN bezeichnung TEXT"
        )
        conn.commit()

    dok_spalten = {
        r[1] for r in conn.execute(
            "PRAGMA table_info(dokumente)"
        ).fetchall()
    }
    if "bezeichnung" not in dok_spalten:
        conn.commit()
        conn.execute(
            "ALTER TABLE dokumente ADD COLUMN bezeichnung TEXT"
        )
        conn.commit()

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (?, ?)",
        (59, "Migration 59 - intake_dokumente.bezeichnung + dokumente.bezeichnung "
             "(PRD-37 Dokumentenbezeichnung)"),
    )
    logger.info("Migration 59 abgeschlossen (bezeichnung-Spalten).")
```

3c. Dispatcher: nach `elif version == 58: _run_migration_58(conn)` (Zeile 1370–1371) einfügen:
```python
            elif version == 59:
                _run_migration_59(conn)
```

3d. In `backend/models/dokument.py`, Dataclass `Dokument`, nach `pdf_hash: Optional[str] = None` (Zeile 105):
```python
    bezeichnung: Optional[str] = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_migration_59.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/db/schema_manager.py backend/models/dokument.py backend/tests/test_migration_59.py
git commit -m "feat(prd-37): Migration 59 - bezeichnung-Spalten intake_dokumente + dokumente"
```

---

### Task 5: `hole_detail` liefert `bezeichnung` + `bezeichnung_vorschlag`

**Files:**
- Modify: `backend/routers/intake_routes.py` (neue Helfer + `hole_detail` ~Zeile 247–280)
- Test: `backend/tests/test_intake_routes.py` (neue Testfunktion)

**Interfaces:**
- Consumes: Task 1 `baue_bezeichnung`; Task 4 Spalte `intake_dokumente.bezeichnung`.
- Produces: Modul-Helfer `_ist_email(dok) -> bool`, `_eingangsdatum(intake_id) -> Optional[str]`, `_bezeichnung_vorschlag(dok) -> str`, `_bezeichnung_effektiv(dok) -> str`. `GET /intake/dokument/<id>` enthält zusätzlich `"bezeichnung"` (gespeichert, ggf. null) und `"bezeichnung_vorschlag"` (berechnet).

- [ ] **Step 1: Write the failing test**

In `backend/tests/test_intake_routes.py` neue Funktion (Muster wie bestehende Tests — `_setup`/`_auth_header`/`_lege_intake_pdf_an` sind vorhanden):

```python
def test_detail_liefert_bezeichnung_vorschlag():
    client = _setup("bez_detail")
    h = _auth_header(client)
    parse_json = json.dumps({
        "text_gesamt": "x", "seiten": [], "klassifikation": {"kandidaten": [], "hinweise": []},
        "felder": {"aussteller": "Autohaus Müller", "rechnungsdatum": "12.03.2026",
                   "bruttobetrag": "1.234,56"},
        "akten_kandidaten": [],
    }, ensure_ascii=False)
    did = _lege_intake_pdf_an(sha_suffix="b", klasse="rechnung",
                              parse_json=parse_json)
    r = client.get(f"/intake/dokument/{did}", headers=h)
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert d["bezeichnung"] is None
    assert d["bezeichnung_vorschlag"] == "Rechnung Autohaus Müller vom 12.03.2026 (1.234,56 €)"
```

(`_lege_intake_pdf_an(...)` gibt `cur.lastrowid` (int) zurück — `did` ist direkt die Dokument-id.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_intake_routes.py::test_detail_liefert_bezeichnung_vorschlag -q`
Expected: FAIL (`KeyError: 'bezeichnung_vorschlag'`).

- [ ] **Step 3: Implementierung**

3a. In `backend/routers/intake_routes.py` oben den Import ergänzen (bei den anderen `from ..services`-Imports, ~Zeile 45):
```python
from ..services.dokument_bezeichnung import baue_bezeichnung
```

3b. Neue Helfer direkt nach `_default_ereignistyp` (nach Zeile 766) einfügen:
```python
def _ist_email(dok: Dict[str, Any]) -> bool:
    return (dok.get("payload_typ") == "text"
            or dok.get("textquelle") == "email_text")


def _eingangsdatum(intake_id: int) -> Optional[str]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT empfangen_am FROM zustellungen "
            "WHERE intake_dokument_id=? ORDER BY id ASC LIMIT 1",
            (intake_id,),
        ).fetchone()
    return row["empfangen_am"] if row else None


def _bezeichnung_vorschlag(dok: Dict[str, Any]) -> str:
    from ..intake.registry_loader import lade_registry, standard_pfad
    felder = _parse(dok.get("parse_json")).get("felder") or {}
    kontext = {
        "ist_email": _ist_email(dok),
        "eingangsdatum": _eingangsdatum(dok["id"]),
    }
    try:
        reg = lade_registry(standard_pfad())
    except Exception:  # pragma: no cover -- Best-Effort
        reg = None
    return baue_bezeichnung(dok.get("klasse"), felder, kontext, reg)


def _bezeichnung_effektiv(dok: Dict[str, Any]) -> str:
    gespeichert = (dok.get("bezeichnung") or "").strip()
    return gespeichert or _bezeichnung_vorschlag(dok)
```

3c. Im Response-Dict von `hole_detail` (nach `"klasse": dok.get("klasse"),` Zeile 255) ergänzen:
```python
        "bezeichnung": dok.get("bezeichnung"),
        "bezeichnung_vorschlag": _bezeichnung_vorschlag(dok),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_intake_routes.py::test_detail_liefert_bezeichnung_vorschlag -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/intake_routes.py backend/tests/test_intake_routes.py
git commit -m "feat(prd-37): hole_detail liefert bezeichnung + bezeichnung_vorschlag"
```

---

### Task 6: PATCH-Endpoint zum Speichern der Review-Bezeichnung + API-Client

**Files:**
- Modify: `backend/routers/intake_routes.py` (neuer Endpoint nach `patch_felder`, ~Zeile 555)
- Modify: `frontend/src/api.js` (`apiIntake`, ~Zeile 1062)
- Test: `backend/tests/test_intake_routes.py` (neue Testfunktion)

**Interfaces:**
- Consumes: Task 4 Spalte; Task 5 `_bezeichnung_vorschlag`.
- Produces: `PATCH /intake/dokument/<id>/bezeichnung` mit Body `{"bezeichnung": str}` → `{"ok": True, "bezeichnung": <gespeichert|null>}`. Leerer/whitespace-String speichert `NULL` (→ zurück zum lebendigen Vorschlag). `apiIntake.setBezeichnung(id, wert)`.

- [ ] **Step 1: Write the failing test**

```python
def test_patch_bezeichnung_speichert_und_leert():
    client = _setup("bez_patch")
    h = _auth_header(client)
    did = _lege_intake_pdf_an(sha_suffix="c", klasse="rechnung")
    # setzen
    r = client.patch(f"/intake/dokument/{did}/bezeichnung",
                     headers=h, json={"bezeichnung": "Mein Titel"})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["bezeichnung"] == "Mein Titel"
    d = client.get(f"/intake/dokument/{did}", headers=h).get_json()
    assert d["bezeichnung"] == "Mein Titel"
    # leeren -> NULL, Vorschlag lebt wieder
    r2 = client.patch(f"/intake/dokument/{did}/bezeichnung",
                      headers=h, json={"bezeichnung": "  "})
    assert r2.status_code == 200
    assert r2.get_json()["bezeichnung"] is None
    d2 = client.get(f"/intake/dokument/{did}", headers=h).get_json()
    assert d2["bezeichnung"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_intake_routes.py::test_patch_bezeichnung_speichert_und_leert -q`
Expected: FAIL (404 — Route existiert nicht).

- [ ] **Step 3: Implementierung**

3a. In `intake_routes.py` nach `patch_felder` (nach Zeile 555, vor `_upload_basis`) einfügen:
```python
@intake_bp.route("/dokument/<int:intake_id>/bezeichnung", methods=["PATCH"])
@login_erforderlich
def patch_bezeichnung(intake_id: int):
    """Manuelle Dokumentenbezeichnung speichern (PRD-37).

    Body: {"bezeichnung": str}. Leerer String -> NULL (zurueck zum
    lebendigen Vorschlag). Schreibt nur intake_dokumente -- kein Akten-Write
    (INTAKE_REVIEW_PFLICHT gewahrt).
    """
    payload = request.get_json(silent=True) or {}
    wert = (payload.get("bezeichnung") or "").strip() or None

    dok = _lade_intake(intake_id)
    if not dok:
        return _err("Intake-Dokument nicht gefunden", 404)

    with get_connection() as conn:
        conn.execute(
            "UPDATE intake_dokumente SET bezeichnung=? WHERE id=?",
            (wert, intake_id),
        )
        _log_korrektur(
            conn, intake_id, feld="bezeichnung",
            wert_alt=dok.get("bezeichnung"), wert_neu=wert,
            klasse=dok.get("klasse"),
            registry_version=dok.get("registry_version"),
            benutzer_id=getattr(g, "benutzer_id", None),
        )
    return _j({"ok": True, "bezeichnung": wert})
```

3b. In `frontend/src/api.js`, `apiIntake`, nach `setFelder` (Zeile 1062) einfügen:
```javascript
  setBezeichnung: (id, bezeichnung) => request(`/intake/dokument/${id}/bezeichnung`, {
    method: 'PATCH', body: JSON.stringify({ bezeichnung }),
  }),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_intake_routes.py::test_patch_bezeichnung_speichert_und_leert -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/intake_routes.py frontend/src/api.js backend/tests/test_intake_routes.py
git commit -m "feat(prd-37): PATCH /intake/dokument/<id>/bezeichnung + apiIntake.setBezeichnung"
```

---

### Task 7: Freigabe schreibt effektive Bezeichnung nach `dokumente.bezeichnung`

**Files:**
- Modify: `backend/ramicro/output_adapter.py` (`schreibe_dokument`, Zeile 49–97)
- Modify: `backend/routers/intake_routes.py` (`post_freigabe`, Aufruf ~Zeile 645)
- Test: `backend/tests/test_intake_routes.py` (neue Testfunktion)

**Interfaces:**
- Consumes: Task 5 `_bezeichnung_effektiv`; Task 4 Spalte `dokumente.bezeichnung`.
- Produces: `schreibe_dokument(intake_dok, akte_az, freigegeben_von, bezeichnung=None)` schreibt `bezeichnung` in die neue `dokumente`-Zeile. `post_freigabe` übergibt `_bezeichnung_effektiv(dok)`.

- [ ] **Step 1: Write the failing test**

```python
def test_freigabe_schreibt_bezeichnung_in_dokumente():
    client = _setup("bez_frei")
    h = _auth_header(client)
    _seed_akte("77/26")  # Ziel-Akte fuer die Freigabe (Helfer im Modul)
    parse_json = json.dumps({
        "text_gesamt": "x", "seiten": [], "klassifikation": {"kandidaten": [], "hinweise": []},
        "felder": {"aussteller": "Autohaus Müller", "rechnungsdatum": "12.03.2026",
                   "bruttobetrag": "1.234,56"},
        "akten_kandidaten": [],
    }, ensure_ascii=False)
    did = _lege_intake_pdf_an(sha_suffix="d", klasse="rechnung",
                              parse_json=parse_json)
    # manuelle Bezeichnung gewinnt vor Vorschlag
    client.patch(f"/intake/dokument/{did}/bezeichnung", headers=h,
                 json={"bezeichnung": "Werkstattrechnung Müller"})
    r = client.post(f"/intake/dokument/{did}/freigabe", headers=h,
                    json={"akte_az": "77/26"})
    assert r.status_code == 200, r.get_json()
    dokument_id = r.get_json()["dokument_id"]
    from backend.db.database import get_connection
    with get_connection() as conn:
        row = conn.execute("SELECT bezeichnung FROM dokumente WHERE id=?",
                           (dokument_id,)).fetchone()
    assert row["bezeichnung"] == "Werkstattrechnung Müller"


def test_freigabe_ohne_manuelle_bezeichnung_nutzt_vorschlag():
    client = _setup("bez_frei2")
    h = _auth_header(client)
    _seed_akte("78/26")
    parse_json = json.dumps({
        "text_gesamt": "x", "seiten": [], "klassifikation": {"kandidaten": [], "hinweise": []},
        "felder": {"aussteller": "Autohaus Müller", "rechnungsdatum": "12.03.2026",
                   "bruttobetrag": "1.234,56"},
        "akten_kandidaten": [],
    }, ensure_ascii=False)
    did = _lege_intake_pdf_an(sha_suffix="e", klasse="rechnung",
                              parse_json=parse_json)
    r = client.post(f"/intake/dokument/{did}/freigabe", headers=h,
                    json={"akte_az": "78/26"})
    assert r.status_code == 200, r.get_json()
    from backend.db.database import get_connection
    with get_connection() as conn:
        row = conn.execute("SELECT bezeichnung FROM dokumente WHERE id=?",
                           (r.get_json()["dokument_id"],)).fetchone()
    assert row["bezeichnung"] == "Rechnung Autohaus Müller vom 12.03.2026 (1.234,56 €)"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest "backend/tests/test_intake_routes.py::test_freigabe_schreibt_bezeichnung_in_dokumente" -q`
Expected: FAIL (`row["bezeichnung"]` ist None — noch nicht geschrieben).

- [ ] **Step 3: Implementierung**

3a. In `backend/ramicro/output_adapter.py`, Signatur + Import + Schreib-Schritt:

Signatur (Zeile 49–50) ändern zu:
```python
def schreibe_dokument(intake_dok: Dict[str, Any], akte_az: str,
                      freigegeben_von: Optional[int],
                      bezeichnung: Optional[str] = None) -> int:
```

Nach `dokument = registriere_dokument(...)` (nach Zeile 96, vor `return int(dokument.id)`) einfügen:
```python
    if bezeichnung:
        from ..db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "UPDATE dokumente SET bezeichnung=? WHERE id=?",
                (bezeichnung, dokument.id),
            )
```

3b. In `backend/routers/intake_routes.py`, `post_freigabe`, den Aufruf (Zeile 645) ersetzen:
```python
        dokument_id = schreibe_dokument(dok, akte_az,
                                        freigegeben_von=benutzer_id,
                                        bezeichnung=_bezeichnung_effektiv(dok))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest "backend/tests/test_intake_routes.py::test_freigabe_schreibt_bezeichnung_in_dokumente" "backend/tests/test_intake_routes.py::test_freigabe_ohne_manuelle_bezeichnung_nutzt_vorschlag" -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/ramicro/output_adapter.py backend/routers/intake_routes.py backend/tests/test_intake_routes.py
git commit -m "feat(prd-37): Freigabe uebernimmt effektive Bezeichnung in dokumente"
```

---

### Task 8: E-Akte — Bezeichnung ausliefern + nachträglich editieren

**Files:**
- Modify: `backend/pdf/upload_service.py` (`_dok_dict`, Zeile 363–379)
- Modify: `backend/routers/akten_routes.py` (`_dokument_dict`, Zeile 160–172)
- Modify: `backend/routers/dokumente_routes.py` (neuer Endpoint nach `klassifikation_korrigieren`, ~Zeile 475)
- Modify: `frontend/src/api.js` (`dokumente`, ~Zeile 193)
- Test: `backend/tests/test_dokumente_bezeichnung_akte.py`

**Interfaces:**
- Consumes: Task 4 Spalte `dokumente.bezeichnung` + Dataclass-Feld.
- Produces: Dokument-Serialisierer liefern `"bezeichnung"`. `PATCH /akten/<az>/dokumente/<did>/bezeichnung` mit Body `{"bezeichnung": str}` → `{"ok": True, "bezeichnung": <gespeichert|null>}`. `apiDokumente.setBezeichnung(akteId, id, wert)`.

- [ ] **Step 1: Write the failing test**

```python
"""PRD-37: E-Akte-Dokument traegt bezeichnung + ist nachtraeglich editierbar."""
import importlib
import os
import sys
import tempfile
import unittest

_tmp = tempfile.mkdtemp(prefix="dok_bez_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _client(test_id):
    db = os.path.join(_tmp, f"{test_id}.db")
    if os.path.exists(db):
        os.remove(db)
    os.environ["DB_PATH"] = db
    os.environ["UPLOAD_DIR"] = os.path.join(_tmp, f"up_{test_id}")
    import backend.db.database as db_mod
    import backend.app as app_mod
    for m in (db_mod, app_mod):
        importlib.reload(m)
    return app_mod.erstelle_app({"TESTING": True}).test_client()


def _auth(client):
    r = client.post("/auth/login", json={
        "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
        "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!")})
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


class TestDokumentBezeichnungAkte(unittest.TestCase):
    def test_patch_und_liste(self):
        client = _client("akte")
        h = _auth(client)
        from backend.models.akte import erstelle_oder_hole_akte
        from backend.models.dokument import registriere_dokument
        erstelle_oder_hole_akte("90/26", bearbeiter_id=None)
        dok = registriere_dokument(akte_id="90/26", typ="sonstiges",
                                   dateiname="scan_1.pdf", dateipfad="90_26/scan_1.pdf")
        r = client.patch(f"/akten/90/26/dokumente/{dok.id}/bezeichnung",
                         headers=h, json={"bezeichnung": "Anwaltsschreiben"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["bezeichnung"], "Anwaltsschreiben")
        liste = client.get("/akten/90/26/dokumente", headers=h).get_json()
        treffer = [d for d in liste["dokumente"] if d["id"] == dok.id]
        self.assertEqual(treffer[0]["bezeichnung"], "Anwaltsschreiben")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_dokumente_bezeichnung_akte.py -q`
Expected: FAIL (404 auf PATCH — Route fehlt).

- [ ] **Step 3: Implementierung**

3a. In `backend/pdf/upload_service.py`, `_dok_dict`, nach `"dokumentenklasse": ...` (Zeile 368) ergänzen:
```python
        "bezeichnung":      getattr(dok, "bezeichnung", None),
```

3b. In `backend/routers/akten_routes.py`, `_dokument_dict`, nach `"dokumentenklasse": ...` (Zeile 168) ergänzen:
```python
        "bezeichnung":      getattr(d, "bezeichnung", None),
```

3c. In `backend/routers/dokumente_routes.py` nach `klassifikation_korrigieren` (nach Zeile 474) neuen Endpoint einfügen:
```python
@dokumente_bp.route("/<int:dokument_id>/bezeichnung", methods=["PATCH"])
@login_erforderlich
def bezeichnung_setzen(akte_id: str, dokument_id: int):
    """PATCH /akten/<id>/dokumente/<did>/bezeichnung  (PRD-37).

    Body: {"bezeichnung": str}. Leerer String -> NULL.
    """
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)
    row = _hole_dok_row(dokument_id)
    if not row or row["akte_id"] != akte_id:
        return _err(f"Dokument {dokument_id} nicht gefunden.", 404)

    body = request.get_json(silent=True) or {}
    wert = (body.get("bezeichnung") or "").strip() or None
    from ..db.database import get_connection
    with get_connection() as conn:
        conn.execute("UPDATE dokumente SET bezeichnung=? WHERE id=?",
                     (wert, dokument_id))
    return _j({"ok": True, "bezeichnung": wert})
```

(Falls `_pruefe_akte`, `_hole_dok_row`, `_j`, `_err` nicht bereits im Modulkopf verfügbar sind — sie sind es laut Zeilen 39–48 — Import prüfen.)

3d. In `frontend/src/api.js`, `dokumente`-Objekt, nach `klassifikation` (Zeile 193) einfügen:
```javascript
  setBezeichnung: (aId, id, bezeichnung) => request(`/akten/${aId}/dokumente/${id}/bezeichnung`, {
    method: 'PATCH', body: JSON.stringify({ bezeichnung })
  }),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_dokumente_bezeichnung_akte.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/pdf/upload_service.py backend/routers/akten_routes.py backend/routers/dokumente_routes.py frontend/src/api.js backend/tests/test_dokumente_bezeichnung_akte.py
git commit -m "feat(prd-37): E-Akte-Dokument traegt bezeichnung + PATCH-Endpoint"
```

---

### Task 9: Frontend — Bezeichnungsfeld im Review-DetailPanel

**Files:**
- Modify: `frontend/src/views/ReviewQueueView.jsx` (Helfer `effektiveBezeichnung`; `naechsterFormState` Zeile 434; `DetailPanel` State + Speicher + Render)
- Test: `frontend/src/views/ReviewQueueView.bezeichnung.test.jsx`

**Interfaces:**
- Consumes: Task 5 (`detail.bezeichnung`, `detail.bezeichnung_vorschlag`), Task 6 (`apiIntake.setBezeichnung`).
- Produces: exportierte reine Funktion `effektiveBezeichnung(detail) -> string`; `naechsterFormState(detail, opts)` liefert zusätzlich `bezeichnung`.

- [ ] **Step 1: Write the failing test**

```jsx
import { describe, it, expect } from "vitest";
import { effektiveBezeichnung, naechsterFormState } from "./ReviewQueueView.jsx";

describe("effektiveBezeichnung", () => {
  it("nimmt gespeicherten Wert, wenn gesetzt", () => {
    expect(effektiveBezeichnung({ bezeichnung: "Mein Titel",
      bezeichnung_vorschlag: "Vorschlag" })).toBe("Mein Titel");
  });
  it("faellt auf Vorschlag zurueck, wenn nicht gesetzt", () => {
    expect(effektiveBezeichnung({ bezeichnung: null,
      bezeichnung_vorschlag: "Rechnung X" })).toBe("Rechnung X");
  });
  it("leerer String bei fehlenden Werten", () => {
    expect(effektiveBezeichnung({})).toBe("");
  });
});

describe("naechsterFormState liefert bezeichnung", () => {
  it("aus effektiveBezeichnung", () => {
    const f = naechsterFormState({ bezeichnung: null,
      bezeichnung_vorschlag: "Gutachten vom 01.01.2026",
      parse: { akten_kandidaten: [] } }, {});
    expect(f.bezeichnung).toBe("Gutachten vom 01.01.2026");
  });
  it("null bei skipFormReset", () => {
    expect(naechsterFormState({}, { skipFormReset: true })).toBe(null);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/views/ReviewQueueView.bezeichnung.test.jsx`
Expected: FAIL (`effektiveBezeichnung is not a function`).

- [ ] **Step 3: Implementierung**

3a. In `ReviewQueueView.jsx` nahe der anderen reinen Helfer (z. B. nach `druckZiel`, Zeile 429) exportierte Funktion einfügen:
```jsx
export function effektiveBezeichnung(detail) {
  return detail?.bezeichnung ?? detail?.bezeichnung_vorschlag ?? "";
}
```

3b. `naechsterFormState` (Zeile 434–441) um `bezeichnung` erweitern:
```jsx
export function naechsterFormState(detail, { skipFormReset = false } = {}) {
  if (skipFormReset) return null;
  return {
    gewaehlteAkte: detail?.parse?.akten_kandidaten?.[0]?.akte_az || "",
    ereignisse: initialeEreignisse(detail?.default_ereignistyp),
    bezeichnung: effektiveBezeichnung(detail),
    dirty: {},
  };
}
```

3c. In `DetailPanel` State ergänzen (nach Zeile 735):
```jsx
  const [bezeichnung, setBezeichnung] = useState("");
```

3d. Im `laden`-Callback, im `if (form)`-Block (nach Zeile 751), ergänzen:
```jsx
        setBezeichnung(form.bezeichnung);
```

3e. Speicher-Funktion neben `speichereFelder` (nach Zeile 872) einfügen:
```jsx
  const speichereBezeichnung = async () => {
    const wert = (bezeichnung || "").trim();
    if (wert === (detail.bezeichnung ?? "")) return;
    try {
      await apiIntake.setBezeichnung(id, wert);
      await laden({ skipFormReset: true });
    } catch (e) { setError(e.message); }
  };
```

3f. Render: eine neue `<section>` direkt nach dem Header-Block (nach der schließenden `</div>` der Kopfzeile, Zeile 976 — vor dem `{(meldung || pollAktiv) && ...}`-Block) einfügen:
```jsx
        <section style={{ marginBottom: 16 }}>
          <label style={{ display: "block", fontSize: T.textSm, fontWeight: 600, marginBottom: 4 }}>
            Dokumentenbezeichnung
          </label>
          <input
            type="text"
            value={bezeichnung}
            onChange={e => setBezeichnung(e.target.value)}
            onBlur={speichereBezeichnung}
            placeholder={detail.bezeichnung_vorschlag || ""}
            disabled={aktion}
            style={{
              width: "100%", padding: "6px 8px", boxSizing: "border-box",
              border: `1px solid ${T.border}`, borderRadius: 4,
              fontSize: T.textSm, background: T.white,
            }} />
          <div style={{ fontSize: T.textXs, color: T.textFaint, marginTop: 4 }}>
            Vorschlag automatisch aus Klasse/Aussteller/Datum/Betrag. Editierbar; wird bei Freigabe übernommen.
          </div>
        </section>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/views/ReviewQueueView.bezeichnung.test.jsx`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/ReviewQueueView.jsx frontend/src/views/ReviewQueueView.bezeichnung.test.jsx
git commit -m "feat(prd-37): Bezeichnungsfeld im Review-DetailPanel"
```

---

### Task 10: Frontend — Bezeichnung in der E-Akte anzeigen + inline editieren

**Files:**
- Modify: `frontend/src/sections/DokumenteSection.jsx` (Dokument-Zeile, Anzeige Zeile 950; Editier-Handler)
- Test: manuelle Verifikation via `/verify` (siehe Abschluss-Schritt); die Anzeige-Logik ist eine kleine reine Ableitung.

**Interfaces:**
- Consumes: Task 8 (`d.bezeichnung`, `apiDokumente.setBezeichnung`).
- Produces: Dokument-Zeile zeigt `d.bezeichnung || d.dateiname`; Klick darauf öffnet ein Inline-Editierfeld, das per `apiDokumente.setBezeichnung` speichert und die Liste neu lädt.

- [ ] **Step 1: Anzeige auf Bezeichnung umstellen**

In `DokumenteSection.jsx`, Zeile 950, den Anzeigetext von `{d.dateiname}` ändern zu einem editierbaren Titel. Ersetze das `<div>…{d.dateiname}</div>` durch:
```jsx
                  <div
                    onClick={() => { setBezEdit(d.id); setBezText(d.bezeichnung || ""); }}
                    title="Klicken zum Umbenennen"
                    style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.975rem", fontWeight:600, color:T.text, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap", cursor:"text" }}>
                    {d.bezeichnung || d.dateiname}
                  </div>
                  {bezEdit === d.id && (
                    <input
                      autoFocus
                      value={bezText}
                      onChange={e => setBezText(e.target.value)}
                      onBlur={() => speichereBez(d.id)}
                      onKeyDown={e => { if (e.key === "Enter") e.currentTarget.blur();
                                        if (e.key === "Escape") setBezEdit(null); }}
                      placeholder={d.dateiname}
                      style={{ width:"100%", boxSizing:"border-box", marginTop:4,
                        fontSize:"0.9rem", padding:"3px 6px",
                        border:`1px solid ${T.border}`, borderRadius:6 }} />
                  )}
```

- [ ] **Step 2: State + Speicher-Handler ergänzen**

In der `DokumenteSection`-Komponente bei den übrigen `useState`-Deklarationen ergänzen (in der Nähe von `korrekturLading`):
```jsx
  const [bezEdit, setBezEdit] = useState(null);
  const [bezText, setBezText] = useState("");
```
und einen Handler (in der Nähe von `korrigiereKlasse`):
```jsx
  const speichereBez = async (dokId) => {
    try {
      await apiDokumente.setBezeichnung(akteId, dokId, bezText.trim());
    } catch (e) {
      setToast(`Umbenennen fehlgeschlagen: ${e.message}`);
    } finally {
      setBezEdit(null);
      const res = await apiDokumente.liste(akteId);
      setDokumente(res.dokumente || []);
    }
  };
```
(Prüfe die exakten Namen `apiDokumente`, `akteId`, `setDokumente`, `setToast` im Datei-Kopf/State — sie sind laut Zeilen 4/139/184 vorhanden. Falls `setDokumente` anders heißt, den bestehenden Lade-Pfad aus Zeile 184 wiederverwenden.)

- [ ] **Step 3: Frontend-Build/Lint prüfen**

Run: `cd frontend && npx vitest run` (gesamte Frontend-Suite)
Expected: PASS — keine bestehende Datei bricht (keine Vitest-Datei deckt DokumenteSection direkt ab; dieser Task ist visuell/`/verify`).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/sections/DokumenteSection.jsx
git commit -m "feat(prd-37): Dokumentenbezeichnung in E-Akte anzeigen + inline umbenennen"
```

---

### Abschluss: Voller Testlauf + End-to-End-Verifikation

- [ ] **Step 1: Volle Backend-Suite (Regressionscheck)**

Run: `python -m pytest backend/tests -q`
Expected: Keine **neuen** Failures ggü. der Baseline (bekannte Alt-Cluster `test_modul3/4/7`, `sv_portal`, `prd27` bleiben wie zuvor). Neue PRD-37-Tests grün.

- [ ] **Step 2: Volle Frontend-Suite**

Run: `cd frontend && npx vitest run`
Expected: PASS inkl. der neuen `ReviewQueueView.bezeichnung.test.jsx`.

- [ ] **Step 3: End-to-End im DEV-App (`/verify` bzw. `/run`)**

Manuell in der laufenden Dev-App:
1. Dokument in der Review-Queue öffnen → Feld „Dokumentenbezeichnung" zeigt einen sinnvollen Vorschlag.
2. Klasse ändern → nach Reparse aktualisiert sich der Vorschlag (solange nicht manuell editiert).
3. Bezeichnung überschreiben, Feld verlassen → bleibt nach Reload erhalten.
4. Freigeben → in der Ziel-Akte (`DokumenteSection`) trägt das Dokument die Bezeichnung.
5. In der E-Akte auf die Bezeichnung klicken, umbenennen, Enter → neuer Titel bleibt nach Reload.

⚠ **Falls die Dev-Review-Queue nach dem Deploy HTTP 500 wirft** (`no such column: bezeichnung`): Reloader-Migrations-Falle (Task 4) — auf der aktiven Volume-DB (`/app/data`, nicht `backend/data/`) `schema_version` prüfen und die Spalten per `ALTER TABLE` nachziehen (Backup zuerst).
```

