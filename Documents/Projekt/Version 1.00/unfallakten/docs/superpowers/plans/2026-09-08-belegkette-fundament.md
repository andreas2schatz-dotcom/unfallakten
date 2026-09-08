# Belegkette Fundament (R1 + R2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Jedes Dokument bekommt das Datum, das auf dem Schreiben steht, und die Review-Freigabe trägt ihre Belege in die Belegliste ein — damit dieselbe Arbeit nicht zweimal anfällt.

**Architecture:** Eine neue Spalte `dokumente.dokument_datum` (Migration 75) wird aus der bestehenden `bezeichnung_felder.datum`-Rolle der Klassen-Registry gefüllt und ist im Freigabe-Dialog überschreibbar. Die Ableitung liegt als reine Funktion neben `baue_bezeichnung`, die Beleg-Zuordnung wandert aus `belege_routes` in einen Service, den Freigabe und Handzuordnung gemeinsam nutzen. Alle Verbraucher (Freigabe-Ereignis, Klage-Verzugsliste) lesen danach dasselbe Datum.

**Tech Stack:** Python 3.9-kompatibel, Flask, SQLite, unittest; Frontend React (Vite), Vitest.

**Spec:** `docs/superpowers/specs/2026-09-07-belegkette-beweisantritt-design.md`

## Global Constraints

- **RA-MICRO bleibt read-only.** Geschrieben wird ausschließlich in SQLite.
- **Python 3.9-kompatibel.** Kein `X | Y` in Signaturen, `Optional[...]` verwenden.
- **Keine Kommentare im Code** außer bei nicht-offensichtlichem Verhalten.
- **Migrationen niemals mit `executescript()`.** `ALTER TABLE` braucht ein explizites `conn.commit()` davor und danach. Eine Migration wird in **einem einzigen Edit** geschrieben — der Flask-Reloader stempelt sonst einen Zwischenstand als erledigt ab (Version gesetzt, Spalte fehlt).
- **Migrations-Spalten gehören NICHT in `backend/db/schema.py`.** `init_db()` fährt auf frischen Datenbanken alle Migrationen mit; `dokumentenklasse` und `bezeichnung` stehen ebenfalls nur in `schema_manager.py`. Ein zusätzlicher Eintrag in `schema.py` bringt die Testsuite reihenweise zum Fallen.
- **Testfixtures:** temporäre SQLite-Datei je Fixture, `backend.db.database.DB_PATH` **und** `os.environ["DB_PATH"]` setzen, `init_db()` aufrufen, in `tearDown` zurücksetzen. Muster: `backend/tests/test_p15e_freigabe_ereignisse.py:13–41`.
- **Datumsformat in der DB:** ISO `YYYY-MM-DD`. Eingaben aus der Oberfläche kommen als `DD.MM.YYYY` und werden mit `backend.utils.datum.parse_datum` normalisiert.
- **Das Dokumentdatum ist optional.** Ein Dokument ohne erkennbares Datum darf freigegeben werden; die Spalte bleibt dann `NULL`. (Offener Punkt 1 der Spec, hier so entschieden — ein Pflichtfeld würde die Freigabe von Altpapier blockieren.)
- **Commit-Trailer:** Jeder Commit endet mit
  `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`
  und der Session-Zeile. In den Schritten unten steht nur die Kurzform.

---

## Nicht Gegenstand dieses Plans

R3–R5 (Anlagennummern, „b.b.", Beweismittel-Schritt im Klage-Wizard) bekommen
einen **eigenen Plan**. Sie verbrauchen, was dieser Plan herstellt: ein
Dokumentdatum und eine vollständige Belegliste. Vor deren Existenz ließen sich
ihre Schritte nur raten. Task 8 unten holt den unmittelbaren Klage-Nutzen von
R1 aber schon jetzt (Verzugsdatum), damit dieser Plan für sich genommen etwas
Sichtbares liefert.

`pruefbericht.yaml` bekommt hier **keine** `datum`-Rolle: die Klasse hat in
ihrem `schema` gar kein Datumsfeld, das man referenzieren könnte. Das braucht
erst eine Parser-Erweiterung (offener Punkt 2 der Spec).

---

## Dateiübersicht

| Datei | Verantwortung |
|---|---|
| `backend/db/schema_manager.py` | Migration 75: Spalte + Index |
| `backend/services/dokument_bezeichnung.py` | reine Ableitung des Dokumentdatums aus Registry + geparsten Feldern (liegt neben `baue_bezeichnung`, weil beide dieselbe Rollen-Tabelle lesen) |
| `backend/ramicro/output_adapter.py` | schreibt das Datum in die `dokumente`-Zeile |
| `backend/routers/intake_routes.py` | ermittelt das Datum, nimmt die Handkorrektur entgegen, reicht es an Dokument, Ereignis und Beleg weiter |
| `backend/services/beleg_zuordnung.py` | **neu** — einziger Schreibweg für `schadenposition_belege`, von Freigabe und Handzuordnung genutzt |
| `backend/routers/belege_routes.py` | nutzt den Service statt eigener SQL |
| `backend/routers/klage_routes.py` | Verzugsdokumente und Verzugsdatum lesen `dokument_datum` |
| `frontend/src/views/ReviewQueueView.jsx` | Datumsfeld im Freigabe-Dialog |
| `frontend/src/api.js` | überträgt `dokument_datum` |
| `tools/dokument_datum_nachziehen.py` | **neu** — Bestandsdokumente nachfüllen |

---

## Task 1: Migration 75 — Spalte `dokumente.dokument_datum`

**Files:**
- Modify: `backend/db/schema_manager.py` (MIGRATIONS-Dict bei Zeile 331, neue Funktion nach `_run_migration_74`, Dispatch bei Zeile 2412)
- Test: `backend/tests/test_migration_75_dokument_datum.py`

**Interfaces:**
- Consumes: nichts
- Produces: Spalte `dokumente.dokument_datum TEXT` (nullable, ISO-Datum), Index `idx_dokumente_datum` auf `(akte_id, dokument_datum)`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_migration_75_dokument_datum.py`:

```python
"""Migration 75 — dokumente.dokument_datum."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestMigration75(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="mig75_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad
        from backend.db.schema_manager import init_db
        init_db()

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt_db_path
        os.environ.pop("DB_PATH", None)
        try:
            os.unlink(self._db_pfad)
        except OSError:
            pass

    def test_spalte_existiert(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            spalten = {r[1] for r in conn.execute(
                "PRAGMA table_info(dokumente)").fetchall()}
        self.assertIn("dokument_datum", spalten)

    def test_index_existiert(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            namen = {r["name"] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'").fetchall()}
        self.assertIn("idx_dokumente_datum", namen)

    def test_datum_ist_schreibbar_und_nullable(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('44/22', '2022-04-27', 'offen')"
            )
            conn.execute(
                "INSERT INTO dokumente (akte_id, dateiname, dateipfad, "
                "dateityp, dokumentenklasse, dokument_datum) "
                "VALUES ('44/22', 'a.pdf', 'x', 'pdf', 'gutachten', '2024-03-14')"
            )
            conn.execute(
                "INSERT INTO dokumente (akte_id, dateiname, dateipfad, "
                "dateityp, dokumentenklasse) "
                "VALUES ('44/22', 'b.pdf', 'y', 'pdf', 'sonstiges')"
            )
            conn.commit()
            zeilen = conn.execute(
                "SELECT dateiname, dokument_datum FROM dokumente "
                "ORDER BY dateiname"
            ).fetchall()
        self.assertEqual(zeilen[0]["dokument_datum"], "2024-03-14")
        self.assertIsNone(zeilen[1]["dokument_datum"])

    def test_version_eingetragen(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT version FROM schema_version WHERE version=75"
            ).fetchone()
        self.assertIsNotNone(row)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_migration_75_dokument_datum.py -v`
Expected: FAIL — `AssertionError: 'dokument_datum' not found in {...}`

- [ ] **Step 3: Migration schreiben — in EINEM Edit**

Drei Änderungen in `backend/db/schema_manager.py`, alle in einer einzigen
Bearbeitung. Zuerst die Registrierung nach Zeile 331:

```python
    75: "-- migration_75_dokument_datum",  # Handled by _run_migration_75
```

Dann die Funktion direkt nach `_run_migration_74` (endet Zeile 1708):

```python
def _run_migration_75(conn: sqlite3.Connection) -> None:
    """
    Migration 75: dokumente.dokument_datum.

    Das Datum, das auf dem Schreiben steht -- nicht das Eingangs- oder
    Scan-Datum (hochgeladen_am). Wird aus der bezeichnung_felder.datum-Rolle
    der Klassen-Registry gefuellt und ist bei der Freigabe korrigierbar.
    Nullable: Dokumente ohne erkennbares Datum bleiben freigebbar.

    Bestandszeilen fuellt tools/dokument_datum_nachziehen.py nach -- eine
    Migration darf die Registry nicht importieren.
    """
    conn.commit()
    spalten = {r[1] for r in conn.execute(
        "PRAGMA table_info(dokumente)").fetchall()}
    if "dokument_datum" not in spalten:
        conn.execute("ALTER TABLE dokumente ADD COLUMN dokument_datum TEXT")
        conn.commit()
        logger.info("Migration 75: dokumente.dokument_datum angelegt.")

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_dokumente_datum "
        "ON dokumente (akte_id, dokument_datum)"
    )
    conn.commit()

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (75, 'dokumente.dokument_datum -- Datum des Schreibens')"
    )
    conn.commit()
    logger.info("Migration 75 abgeschlossen.")
```

Und der Dispatch-Zweig direkt nach `_run_migration_74(conn)` (Zeile 2412):

```python
            elif version == 75:
                _run_migration_75(conn)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_migration_75_dokument_datum.py -v`
Expected: PASS, 4 Tests

- [ ] **Step 5: Guard — die bestehende Suite darf nicht kippen**

Run: `python -m pytest backend/tests/test_dokumentenklasse_ssot.py backend/tests/test_migration_51_ereignisse.py -q`
Expected: PASS. Wenn hier etwas rot wird, wurde `schema.py` angefasst — das gehört zurückgenommen.

- [ ] **Step 6: Commit**

```bash
git add backend/db/schema_manager.py backend/tests/test_migration_75_dokument_datum.py
git commit -m "feat(dokumente): Spalte dokument_datum fuer das Datum des Schreibens"
```

---

## Task 2: Ableitung des Dokumentdatums aus der Registry

**Files:**
- Modify: `backend/services/dokument_bezeichnung.py` (neue Funktion unter `baue_bezeichnung`)
- Test: `backend/tests/test_dokument_datum_ableitung.py`

**Interfaces:**
- Consumes: `Registry.klassen[<klasse>]["bezeichnung_felder"]["datum"]` aus `backend/intake/registry_loader.py`
- Produces:
  ```python
  dokument_datum_aus_feldern(
      klasse: Optional[str],
      felder: Optional[Dict[str, Any]],
      registry,
      *, eingangsdatum: Optional[str] = None,
  ) -> Optional[str]   # ISO YYYY-MM-DD oder None
  ```

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_dokument_datum_ableitung.py`:

```python
"""Dokumentdatum aus Registry-Rolle + geparsten Feldern."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestDokumentDatumAbleitung(unittest.TestCase):
    def setUp(self):
        from backend.intake.registry_loader import lade_registry, standard_pfad
        self.reg = lade_registry(standard_pfad())

    def _ab(self, klasse, felder, **kw):
        from backend.services.dokument_bezeichnung import (
            dokument_datum_aus_feldern,
        )
        return dokument_datum_aus_feldern(klasse, felder, self.reg, **kw)

    def test_gutachten_nutzt_besichtigungsdatum(self):
        self.assertEqual(
            self._ab("gutachten", {"besichtigungsdatum": "14.03.2024"}),
            "2024-03-14",
        )

    def test_rechnung_nutzt_rechnungsdatum(self):
        self.assertEqual(
            self._ab("mietwagenrechnung", {"rechnungsdatum": "2024-05-02"}),
            "2024-05-02",
        )

    def test_abrechnungsschreiben_nutzt_schreibdatum(self):
        self.assertEqual(
            self._ab("abrechnungsschreiben", {"schreibdatum": "01.06.2024"}),
            "2024-06-01",
        )

    def test_zeitstempel_wird_auf_das_datum_gekuerzt(self):
        self.assertEqual(
            self._ab("gutachten", {"besichtigungsdatum": "2024-03-14 09:12:00"}),
            "2024-03-14",
        )

    def test_ohne_feld_kein_datum(self):
        self.assertIsNone(self._ab("gutachten", {}))

    def test_unlesbares_datum_ergibt_none(self):
        self.assertIsNone(self._ab("gutachten", {"besichtigungsdatum": "Fruehjahr"}))

    def test_pruefbericht_hat_keine_datumsrolle(self):
        self.assertIsNone(self._ab("pruefbericht", {"vorgangsnummer": "4711"}))

    def test_sonstiges_faellt_auf_eingangsdatum_zurueck(self):
        self.assertEqual(
            self._ab("sonstiges", {}, eingangsdatum="2024-07-01 08:00:00"),
            "2024-07-01",
        )

    def test_sonstiges_bevorzugt_das_eigene_feld(self):
        self.assertEqual(
            self._ab("sonstiges", {"datum": "03.02.2024"},
                     eingangsdatum="2024-07-01"),
            "2024-02-03",
        )

    def test_unbekannte_klasse_ergibt_none(self):
        self.assertIsNone(self._ab("gibtsnicht", {"datum": "01.01.2024"}))

    def test_ohne_registry_ergibt_none(self):
        from backend.services.dokument_bezeichnung import (
            dokument_datum_aus_feldern,
        )
        self.assertIsNone(
            dokument_datum_aus_feldern("gutachten",
                                        {"besichtigungsdatum": "14.03.2024"},
                                        None)
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_dokument_datum_ableitung.py -v`
Expected: FAIL — `ImportError: cannot import name 'dokument_datum_aus_feldern'`

- [ ] **Step 3: Funktion implementieren**

An `backend/services/dokument_bezeichnung.py` anhängen (die Datei importiert
`parse_datum` bereits über `from ..utils.datum import parse_datum`):

```python
def dokument_datum_aus_feldern(klasse: Optional[str],
                               felder: Optional[Dict[str, Any]],
                               registry,
                               *,
                               eingangsdatum: Optional[str] = None
                               ) -> Optional[str]:
    """Datum des Schreibens als ISO-String, oder None.

    Liest dieselbe ``bezeichnung_felder.datum``-Rolle wie baue_bezeichnung.
    Fuer 'sonstiges' gilt derselbe Rueckfall auf das Eingangsdatum.
    """
    felder = felder or {}
    spec: Dict[str, Any] = {}
    if registry is not None and klasse:
        spec = (registry.klassen.get(klasse) or {})
    rollen = spec.get("bezeichnung_felder") or {}

    datum_key = rollen.get("datum")
    roh = felder.get(datum_key) if datum_key else None
    d = None
    if roh is not None:
        s = str(roh).strip()
        d = parse_datum(s[:10]) or parse_datum(s)

    if d is None and klasse == "sonstiges" and eingangsdatum:
        s = str(eingangsdatum).strip()
        d = parse_datum(s[:10]) or parse_datum(s)

    return d.isoformat() if d else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_dokument_datum_ableitung.py -v`
Expected: PASS, 11 Tests

- [ ] **Step 5: Commit**

```bash
git add backend/services/dokument_bezeichnung.py backend/tests/test_dokument_datum_ableitung.py
git commit -m "feat(dokumente): Dokumentdatum aus der Klassen-Registry ableiten"
```

---

## Task 3: `schreibe_dokument` speichert das Datum

**Files:**
- Modify: `backend/ramicro/output_adapter.py:32–95`
- Test: `backend/tests/test_output_adapter_dokument_datum.py`

**Interfaces:**
- Consumes: Task 1 (Spalte)
- Produces:
  ```python
  schreibe_dokument(intake_dok, akte_az, freigegeben_von,
                    bezeichnung=None, dokument_datum=None) -> int
  ```
  Der neue Parameter ist optional und rein additiv — bestehende Aufrufer
  bleiben gültig.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_output_adapter_dokument_datum.py`:

```python
"""schreibe_dokument uebernimmt das Dokumentdatum."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestSchreibeDokumentDatum(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="oa_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad
        from backend.db.schema_manager import init_db
        init_db()
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('44/22', '2022-04-27', 'offen')"
            )
            conn.commit()
        self._tmpdir = tempfile.mkdtemp(prefix="oa_files_")
        self._quelle = os.path.join(self._tmpdir, "gutachten.pdf")
        with open(self._quelle, "wb") as fh:
            fh.write(b"%PDF-1.4 test")

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt_db_path
        os.environ.pop("DB_PATH", None)
        try:
            os.unlink(self._db_pfad)
        except OSError:
            pass

    def _dok(self):
        return {"klasse": "gutachten", "arbeitskopie_pfad": self._quelle,
                "parse_json": None, "konfidenz": None}

    def test_datum_wird_gespeichert(self):
        from backend.ramicro.output_adapter import schreibe_dokument
        dok_id = schreibe_dokument(self._dok(), "44/22", freigegeben_von=None,
                                    bezeichnung="Gutachten",
                                    dokument_datum="2024-03-14")
        from backend.db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT dokument_datum FROM dokumente WHERE id=?", (dok_id,)
            ).fetchone()
        self.assertEqual(row["dokument_datum"], "2024-03-14")

    def test_ohne_datum_bleibt_null(self):
        from backend.ramicro.output_adapter import schreibe_dokument
        dok_id = schreibe_dokument(self._dok(), "44/22", freigegeben_von=None,
                                    bezeichnung="Gutachten")
        from backend.db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT dokument_datum FROM dokumente WHERE id=?", (dok_id,)
            ).fetchone()
        self.assertIsNone(row["dokument_datum"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_output_adapter_dokument_datum.py -v`
Expected: FAIL — `TypeError: schreibe_dokument() got an unexpected keyword argument 'dokument_datum'`

- [ ] **Step 3: Parameter durchreichen**

In `backend/ramicro/output_adapter.py` die Signatur (Zeile 32–34) erweitern:

```python
def schreibe_dokument(intake_dok: Dict[str, Any], akte_az: str,
                      freigegeben_von: Optional[int],
                      bezeichnung: Optional[str] = None,
                      dokument_datum: Optional[str] = None) -> int:
```

Und im `felder`-Dict (Zeile 81–86) die Zeile ergänzen:

```python
    felder = {
        "bezeichnung": bezeichnung or None,
        "dokument_datum": dokument_datum or None,
        "parse_json": parse_json,
        "parse_konfidenz": intake_dok.get("konfidenz"),
        "parse_status": "erfolgreich" if parse_json else "ausstehend",
    }
```

Das bestehende `gesetzt = {k: v for k, v in felder.items() if v is not None}`
filtert `None` bereits heraus — es ist kein weiterer Code nötig.

Im Docstring (nach Zeile 43) ergänzen:

```
        dokument_datum: Datum des Schreibens als ISO-String, falls bekannt.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_output_adapter_dokument_datum.py -v`
Expected: PASS, 2 Tests

- [ ] **Step 5: Commit**

```bash
git add backend/ramicro/output_adapter.py backend/tests/test_output_adapter_dokument_datum.py
git commit -m "feat(intake): schreibe_dokument uebernimmt das Dokumentdatum"
```

---

## Task 4: Freigabe ermittelt und übernimmt das Datum

**Files:**
- Modify: `backend/routers/intake_routes.py` (Helper neben `_bezeichnung_vorschlag` bei Zeile 1020; Detail-Antwort bei Zeile 302; Freigabe-Aufruf bei Zeile 871)
- Test: `backend/tests/test_intake_dokument_datum.py`

**Interfaces:**
- Consumes: `dokument_datum_aus_feldern` (Task 2), `schreibe_dokument(..., dokument_datum=)` (Task 3)
- Produces:
  - `_dokument_datum(dok: Dict[str, Any], payload: Dict[str, Any]) -> Optional[str]` — wirft `ValueError` bei unlesbarer Handeingabe
  - Feld `dokument_datum_vorschlag` in der Detail-Antwort von `GET /intake/dokumente/<id>`
  - Payload-Feld `dokument_datum` (String `DD.MM.YYYY` oder ISO) bei `POST .../freigeben`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_intake_dokument_datum.py`:

```python
"""Freigabe ermittelt das Dokumentdatum und nimmt Handkorrekturen an."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestDokumentDatumHelper(unittest.TestCase):
    def _helper(self):
        from backend.routers.intake_routes import _dokument_datum
        return _dokument_datum

    def _dok(self, klasse="gutachten", felder=None):
        import json
        return {
            "id": None,
            "klasse": klasse,
            "parse_json": json.dumps({"felder": felder or {}}),
        }

    def test_aus_geparsten_feldern(self):
        d = self._helper()(
            self._dok(felder={"besichtigungsdatum": "14.03.2024"}), {})
        self.assertEqual(d, "2024-03-14")

    def test_handeingabe_gewinnt(self):
        d = self._helper()(
            self._dok(felder={"besichtigungsdatum": "14.03.2024"}),
            {"dokument_datum": "02.05.2024"})
        self.assertEqual(d, "2024-05-02")

    def test_handeingabe_iso(self):
        d = self._helper()(self._dok(), {"dokument_datum": "2024-05-02"})
        self.assertEqual(d, "2024-05-02")

    def test_leere_handeingabe_faellt_auf_ableitung_zurueck(self):
        d = self._helper()(
            self._dok(felder={"besichtigungsdatum": "14.03.2024"}),
            {"dokument_datum": "   "})
        self.assertEqual(d, "2024-03-14")

    def test_unlesbare_handeingabe_wirft(self):
        with self.assertRaises(ValueError):
            self._helper()(self._dok(), {"dokument_datum": "irgendwann"})

    def test_ohne_alles_none(self):
        self.assertIsNone(self._helper()(self._dok(), {}))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_intake_dokument_datum.py -v`
Expected: FAIL — `ImportError: cannot import name '_dokument_datum'`

- [ ] **Step 3: Helper implementieren**

In `backend/routers/intake_routes.py` direkt nach `_bezeichnung_effektiv`
(Zeile 1033) einfügen:

```python
def _dokument_datum(dok: Dict[str, Any],
                    payload: Dict[str, Any]) -> Optional[str]:
    """Datum des Schreibens als ISO-String. Handeingabe schlaegt Ableitung."""
    from ..utils.datum import parse_datum

    manuell = str((payload or {}).get("dokument_datum") or "").strip()
    if manuell:
        d = parse_datum(manuell)
        if d is None:
            raise ValueError(
                f"Dokumentdatum {manuell!r} ist kein gueltiges Datum "
                f"(erwartet TT.MM.JJJJ)."
            )
        return d.isoformat()

    from ..intake.registry_loader import lade_registry, standard_pfad
    from ..services.dokument_bezeichnung import dokument_datum_aus_feldern

    felder = _parse(dok.get("parse_json")).get("felder") or {}
    try:
        reg = lade_registry(standard_pfad())
    except Exception:  # pragma: no cover -- Best-Effort
        reg = None
    eingang = _eingangsdatum(dok["id"]) if dok.get("id") else None
    return dokument_datum_aus_feldern(
        dok.get("klasse"), felder, reg, eingangsdatum=eingang,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_intake_dokument_datum.py -v`
Expected: PASS, 6 Tests

- [ ] **Step 5: Vorschlag in die Detail-Antwort aufnehmen**

In `backend/routers/intake_routes.py` bei Zeile 302 neben
`"default_ereignistyp"` ergänzen:

```python
        "dokument_datum_vorschlag": _datum_vorschlag_sicher(dok),
```

Und den defensiven Wrapper direkt unter `_dokument_datum` ergänzen — die
Detailansicht darf an einem kaputten Datum nicht scheitern:

```python
def _datum_vorschlag_sicher(dok: Dict[str, Any]) -> Optional[str]:
    try:
        return _dokument_datum(dok, {})
    except Exception:  # pragma: no cover -- Best-Effort
        return None
```

- [ ] **Step 6: Datum bei der Freigabe schreiben**

In `backend/routers/intake_routes.py` den Block bei Zeile 868–871 ersetzen:

```python
    try:
        dokument_datum = _dokument_datum(dok, payload)
    except ValueError as exc:
        return _err(str(exc), 422)

    try:
        dokument_id = schreibe_dokument(dok, akte_az,
                                         freigegeben_von=benutzer_id,
                                         bezeichnung=_bezeichnung_effektiv(dok),
                                         dokument_datum=dokument_datum)
```

Der bestehende `except FileNotFoundError` / `except Exception`-Block bleibt
unverändert darunter stehen.

- [ ] **Step 7: Integrationstest für die Freigabe ergänzen**

An `backend/tests/test_intake_dokument_datum.py` anhängen — Fixture-Muster aus
`backend/tests/test_p15e_freigabe_ereignisse.py:13–41`:

```python
class TestFreigabeSchreibtDatum(unittest.TestCase):
    def setUp(self):
        import tempfile
        fd, self._db_pfad = tempfile.mkstemp(prefix="idd_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad
        from backend.db.schema_manager import init_db
        init_db()

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt_db_path
        os.environ.pop("DB_PATH", None)
        try:
            os.unlink(self._db_pfad)
        except OSError:
            pass

    def test_unlesbares_datum_liefert_422(self):
        from backend.routers.intake_routes import _dokument_datum
        with self.assertRaises(ValueError):
            _dokument_datum({"id": None, "klasse": "gutachten",
                             "parse_json": "{}"},
                            {"dokument_datum": "32.13.2024"})
```

- [ ] **Step 8: Run tests**

Run: `python -m pytest backend/tests/test_intake_dokument_datum.py backend/tests/test_intake_routes.py -q`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add backend/routers/intake_routes.py backend/tests/test_intake_dokument_datum.py
git commit -m "feat(intake): Freigabe ermittelt das Dokumentdatum und nimmt Korrekturen an"
```

---

## Task 5: Datumsfeld im Freigabe-Dialog

**Files:**
- Modify: `frontend/src/views/ReviewQueueView.jsx` (Dialog `FreigabeDialog` ab Zeile 1149; State beim Öffnen ab Zeile 990; Payload bei Zeile 1476)
- Test: `frontend/src/views/ReviewQueueView.dokumentdatum.test.jsx`

**Interfaces:**
- Consumes: `dokument_datum_vorschlag` aus der Detail-Antwort (Task 4)
- Produces: Payload-Feld `dokument_datum` (String im Format `DD.MM.JJJJ`) bei der Freigabe

- [ ] **Step 1: Write the failing test**

Create `frontend/src/views/ReviewQueueView.dokumentdatum.test.jsx`:

```jsx
import { describe, it, expect } from "vitest";
import { isoZuDe, deZuIso } from "./ReviewQueueView.jsx";

describe("Dokumentdatum-Umwandlung im Freigabe-Dialog", () => {
  it("wandelt ISO in die deutsche Anzeige", () => {
    expect(isoZuDe("2024-03-14")).toBe("14.03.2024");
  });

  it("liefert leer bei fehlendem Datum", () => {
    expect(isoZuDe(null)).toBe("");
    expect(isoZuDe("")).toBe("");
  });

  it("wandelt die deutsche Eingabe zurueck", () => {
    expect(deZuIso("14.03.2024")).toBe("2024-03-14");
  });

  it("laesst unvollstaendige Eingaben unveraendert", () => {
    expect(deZuIso("14.03.")).toBe("14.03.");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/views/ReviewQueueView.dokumentdatum.test.jsx`
Expected: FAIL — `isoZuDe is not a function`

- [ ] **Step 3: Helfer exportieren**

In `frontend/src/views/ReviewQueueView.jsx` oben bei den übrigen Hilfsfunktionen
ergänzen:

```jsx
export function isoZuDe(iso) {
  const s = String(iso || "").slice(0, 10);
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  return m ? `${m[3]}.${m[2]}.${m[1]}` : "";
}

export function deZuIso(de) {
  const s = String(de || "").trim();
  const m = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(s);
  return m ? `${m[3]}-${m[2]}-${m[1]}` : s;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/views/ReviewQueueView.dokumentdatum.test.jsx`
Expected: PASS, 4 Tests

- [ ] **Step 5: Feld in den Dialog einbauen**

State beim Öffnen des Dialogs ergänzen (neben `ereignisse:` bei Zeile 992):

```jsx
    dokumentDatum: isoZuDe(detail?.dokument_datum_vorschlag),
```

Im `FreigabeDialog` (nach dem Fragebogen-Block, vor „Ereignis-Vorschlaege")
einfügen — `dokumentDatum` und `onDokumentDatum` als Props durchreichen:

```jsx
        <div style={{ marginBottom: 16 }}>
          <label style={{ fontSize: T.textSm, fontWeight: 600,
                          display: "block", marginBottom: 6 }}>
            Datum des Schreibens
          </label>
          <input
            type="text"
            value={dokumentDatum}
            placeholder="TT.MM.JJJJ"
            onChange={e => onDokumentDatum(e.target.value)}
            style={{ padding: "6px 8px", border: `1px solid ${T.border}`,
                     borderRadius: 4, width: 140 }}
          />
          <div style={{ fontSize: T.textXs, color: T.textMuted,
                        marginTop: 4 }}>
            Steht auf dem Dokument, nicht der Tag des Einlesens. Leer lassen,
            wenn kein Datum erkennbar ist.
          </div>
        </div>
```

- [ ] **Step 6: Payload ergänzen**

Bei Zeile 1476 neben `kandidaten_ereignisse: ereignisse,`:

```jsx
        dokument_datum: deZuIso(dokumentDatum),
```

- [ ] **Step 7: Bestehende Frontend-Tests laufen lassen**

Run: `cd frontend && npx vitest run src/views/ReviewQueueView.prefill.test.jsx src/views/ReviewQueueView.initial.test.jsx src/views/ReviewQueueView.favoriten.test.jsx`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add frontend/src/views/ReviewQueueView.jsx frontend/src/views/ReviewQueueView.dokumentdatum.test.jsx
git commit -m "feat(review): Datum des Schreibens im Freigabe-Dialog erfassen"
```

---

## Task 6: Freigabe-Ereignis trägt das Dokumentdatum

**Files:**
- Modify: `backend/routers/intake_routes.py` (`_schreibe_freigabe_ereignisse` ab Zeile 1065, Aufruf bei Zeile 929)
- Test: `backend/tests/test_p15e_freigabe_ereignisse.py` (neuer Testfall)

**Interfaces:**
- Consumes: `_dokument_datum` (Task 4); `erzeuge_aus_freigabe(..., datum=)` existiert bereits (`backend/services/eingehende_ereignisse.py:586`)
- Produces: `ereignisse.datum` entspricht dem Dokumentdatum, wenn eines bekannt ist; sonst wie bisher heute

- [ ] **Step 1: Write the failing test**

An `backend/tests/test_p15e_freigabe_ereignisse.py` anhängen. Der Test greift
bewusst am Router an, nicht am Service — `erzeuge_aus_freigabe` nimmt `datum`
längst entgegen, es fehlt allein der Weg dorthin:

```python
class TestEreignisDatumAusDokument(_HelperBasis):
    def _ereignis_datum(self, ereignistyp):
        from backend.db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT datum FROM ereignisse WHERE akte_az='44/22' "
                "AND ereignistyp=? ORDER BY id DESC LIMIT 1", (ereignistyp,)
            ).fetchone()
        return row["datum"] if row else None

    def test_router_reicht_das_dokumentdatum_durch(self):
        import json
        from backend.routers.intake_routes import _schreibe_freigabe_ereignisse
        dok = {"id": None, "klasse": "gutachten",
               "parse_json": json.dumps(
                   {"felder": {"besichtigungsdatum": "14.03.2024"}})}
        _schreibe_freigabe_ereignisse(
            dok=dok, akte_az="44/22", dokument_id=self._dok_id(),
            payload={"kandidaten_ereignisse": [{"typ": "gutachten_eingegangen"}]},
            benutzer_id=None, dokument_datum="2024-03-14",
        )
        self.assertEqual(self._ereignis_datum("gutachten_eingegangen"),
                         "2024-03-14")

    def test_ohne_dokumentdatum_bleibt_es_bei_heute(self):
        import json
        from datetime import date
        from backend.routers.intake_routes import _schreibe_freigabe_ereignisse
        dok = {"id": None, "klasse": "gutachten", "parse_json": json.dumps({})}
        _schreibe_freigabe_ereignisse(
            dok=dok, akte_az="44/22", dokument_id=self._dok_id(),
            payload={"kandidaten_ereignisse": [{"typ": "gutachten_eingegangen"}]},
            benutzer_id=None, dokument_datum=None,
        )
        self.assertEqual(self._ereignis_datum("gutachten_eingegangen"),
                         date.today().isoformat())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_p15e_freigabe_ereignisse.py::TestEreignisDatumAusDokument -v`
Expected: FAIL — `TypeError: _schreibe_freigabe_ereignisse() got an unexpected keyword argument 'dokument_datum'`

- [ ] **Step 3: Datum durch den Router reichen**

Signatur von `_schreibe_freigabe_ereignisse` (Zeile 1065) erweitern:

```python
def _schreibe_freigabe_ereignisse(*, dok, akte_az, dokument_id, payload,
                                   benutzer_id, dokument_datum=None):
```

Im `erzeuge_aus_freigabe`-Aufruf (Zeile 1097–1101) ergänzen:

```python
                erzeuge_aus_freigabe(
                    akte_az=akte_az, dokument_id=dokument_id, ereignistyp=typ,
                    klasse=klasse, felder=felder, vorsteuer=vorsteuer,
                    benutzer_id=benutzer_id, datum=dokument_datum,
                )
```

Und den Aufruf bei Zeile 929:

```python
    _schreibe_freigabe_ereignisse(
        dok=dok, akte_az=akte_az, dokument_id=dokument_id,
        payload=payload, benutzer_id=benutzer_id,
        dokument_datum=dokument_datum,
    )
```

`erzeuge_aus_freigabe` ruft intern `_heute_wenn_leer(datum)` auf — ein
`None` verhält sich damit genau wie bisher.

- [ ] **Step 4: Run tests**

Run: `python -m pytest backend/tests/test_p15e_freigabe_ereignisse.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/routers/intake_routes.py backend/tests/test_p15e_freigabe_ereignisse.py
git commit -m "feat(intake): Freigabe-Ereignis traegt das Datum des Schreibens"
```

---

## Task 7: Die Freigabe schreibt den Beleg (R2)

**Files:**
- Create: `backend/services/beleg_zuordnung.py`
- Modify: `backend/routers/belege_routes.py:405–440` (nutzt den Service)
- Modify: `backend/routers/intake_routes.py` (`_schreibe_freigabe_belege`, Aufruf neben Task 6)
- Test: `backend/tests/test_beleg_zuordnung.py`

**Interfaces:**
- Consumes: `rechnungstyp_zu_position(klasse, vorsteuer=...)` und
  `_gutachten_positionen(felder, vorsteuer, akte_az=...)` aus
  `backend/services/eingehende_ereignisse.py`
- Produces:
  ```python
  ordne_beleg_zu(*, akte_az: str, position_key: str, dokument_id: int,
                 betrag: Optional[float] = None,
                 notiz: Optional[str] = None) -> None
  belege_aus_freigabe(*, akte_az: str, dokument_id: int, klasse: str,
                      felder: Dict[str, Any],
                      vorsteuer: bool = False) -> List[str]
  ```
  `belege_aus_freigabe` liefert die geschriebenen `position_key`s.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_beleg_zuordnung.py`:

```python
"""R2 — die Review-Freigabe traegt ihre Belege in die Belegliste ein."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class _Basis(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="belzu_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad
        from backend.db.schema_manager import init_db
        init_db()
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('44/22', '2022-04-27', 'offen')"
            )
            conn.execute(
                "INSERT INTO dokumente (akte_id, dateiname, dateipfad, "
                "dateityp, dokumentenklasse) "
                "VALUES ('44/22', 'r.pdf', 'x', 'pdf', 'mietwagenrechnung')"
            )
            conn.commit()

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt_db_path
        os.environ.pop("DB_PATH", None)
        try:
            os.unlink(self._db_pfad)
        except OSError:
            pass

    def _dok_id(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            return conn.execute(
                "SELECT id FROM dokumente WHERE dateiname='r.pdf'"
            ).fetchone()["id"]

    def _belege(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT position_key, dokument_id, betrag_aus_beleg "
                "FROM schadenposition_belege WHERE akte_az='44/22' "
                "ORDER BY position_key"
            ).fetchall()]


class TestOrdneBelegZu(_Basis):
    def test_legt_zuordnung_an(self):
        from backend.services.beleg_zuordnung import ordne_beleg_zu
        ordne_beleg_zu(akte_az="44/22", position_key="mietwagenkosten",
                       dokument_id=self._dok_id(), betrag=812.50)
        belege = self._belege()
        self.assertEqual(len(belege), 1)
        self.assertEqual(belege[0]["position_key"], "mietwagenkosten")
        self.assertEqual(belege[0]["betrag_aus_beleg"], 812.50)

    def test_zweiter_aufruf_aktualisiert_statt_zu_doppeln(self):
        from backend.services.beleg_zuordnung import ordne_beleg_zu
        ordne_beleg_zu(akte_az="44/22", position_key="mietwagenkosten",
                       dokument_id=self._dok_id(), betrag=812.50)
        ordne_beleg_zu(akte_az="44/22", position_key="mietwagenkosten",
                       dokument_id=self._dok_id(), betrag=900.00)
        belege = self._belege()
        self.assertEqual(len(belege), 1)
        self.assertEqual(belege[0]["betrag_aus_beleg"], 900.00)

    def test_unbekannte_position_wird_abgelehnt(self):
        from backend.services.beleg_zuordnung import ordne_beleg_zu
        with self.assertRaises(ValueError):
            ordne_beleg_zu(akte_az="44/22", position_key="fantasieposten",
                           dokument_id=self._dok_id())


class TestBelegeAusFreigabe(_Basis):
    def test_rechnung_erzeugt_einen_beleg(self):
        from backend.services.beleg_zuordnung import belege_aus_freigabe
        keys = belege_aus_freigabe(
            akte_az="44/22", dokument_id=self._dok_id(),
            klasse="mietwagenrechnung",
            felder={"bruttobetrag": "812,50"},
        )
        self.assertEqual(keys, ["mietwagenkosten"])
        self.assertEqual(self._belege()[0]["betrag_aus_beleg"], 812.50)

    def test_gutachten_belegt_mehrere_positionen(self):
        from backend.services.beleg_zuordnung import belege_aus_freigabe
        keys = belege_aus_freigabe(
            akte_az="44/22", dokument_id=self._dok_id(), klasse="gutachten",
            felder={"wiederbeschaffungswert": "12000,00",
                    "restwert_brutto": "3000,00",
                    "wertminderung": "800,00"},
        )
        self.assertGreater(len(keys), 1)
        self.assertEqual(len(self._belege()), len(keys))

    def test_klasse_ohne_positionsbezug_schreibt_nichts(self):
        from backend.services.beleg_zuordnung import belege_aus_freigabe
        keys = belege_aus_freigabe(
            akte_az="44/22", dokument_id=self._dok_id(), klasse="arztbericht",
            felder={"datum": "01.02.2024"},
        )
        self.assertEqual(keys, [])
        self.assertEqual(self._belege(), [])

    def test_auffangklasse_rechnung_schreibt_nichts(self):
        from backend.services.beleg_zuordnung import belege_aus_freigabe
        keys = belege_aus_freigabe(
            akte_az="44/22", dokument_id=self._dok_id(), klasse="rechnung",
            felder={"bruttobetrag": "100,00"},
        )
        self.assertEqual(keys, [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_beleg_zuordnung.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.services.beleg_zuordnung'`

- [ ] **Step 3: Service anlegen**

Create `backend/services/beleg_zuordnung.py`:

```python
"""Einziger Schreibweg fuer ``schadenposition_belege`` (R2).

Beleg und Ereignis sind zwei Wahrheiten: die Beleg-Tabelle sagt, WOMIT eine
Position bewiesen wird (ein Zustand), das Ereignis sagt, WANN etwas hereinkam
(ein Vorgang). Freigabe und manuelle Zuordnung schreiben beide hierher.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..db.database import get_connection
from .positionsmodell_registry import lade_positionsmodell

logger = logging.getLogger(__name__)


def ordne_beleg_zu(*, akte_az: str, position_key: str, dokument_id: int,
                   betrag: Optional[float] = None,
                   notiz: Optional[str] = None) -> None:
    """Legt die Zuordnung an oder aktualisiert sie (Upsert)."""
    reg = lade_positionsmodell()
    if position_key not in reg.positionsarten:
        raise ValueError(
            f"Unbekannter position_key {position_key!r}. Erlaubt: "
            f"{sorted(reg.positionsarten)}"
        )

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO schadenposition_belege "
            "(akte_az, position_key, dokument_id, betrag_aus_beleg, notiz) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(akte_az, position_key, dokument_id) "
            "DO UPDATE SET betrag_aus_beleg = excluded.betrag_aus_beleg, "
            "              notiz = excluded.notiz",
            (akte_az, position_key, dokument_id, betrag, notiz),
        )
        conn.commit()


def belege_aus_freigabe(*, akte_az: str, dokument_id: int, klasse: str,
                        felder: Optional[Dict[str, Any]] = None,
                        vorsteuer: bool = False) -> List[str]:
    """Traegt die Belege einer Review-Freigabe ein.

    Gutachten belegen mehrere Positionen, Rechnungen genau eine. Klassen ohne
    Positionsbezug -- und die Auffangklasse 'rechnung' ohne Mapping-Eintrag --
    schreiben nichts. Best-Effort: Fehler brechen die Freigabe nie ab.
    """
    felder = felder or {}
    geschrieben: List[str] = []

    try:
        from .eingehende_ereignisse import (
            _feld_zu_zahl, _gutachten_positionen, rechnungstyp_zu_position,
        )

        if klasse == "gutachten":
            paare = _gutachten_positionen(felder, vorsteuer, akte_az=akte_az)
            for key, betrag in paare.items():
                ordne_beleg_zu(akte_az=akte_az, position_key=key,
                               dokument_id=dokument_id,
                               betrag=round(betrag, 2))
                geschrieben.append(key)
            return sorted(geschrieben)

        pk = rechnungstyp_zu_position(klasse, vorsteuer=vorsteuer)
        if pk:
            betrag = (_feld_zu_zahl(felder.get("bruttobetrag"))
                      or _feld_zu_zahl(felder.get("nettobetrag")))
            ordne_beleg_zu(akte_az=akte_az, position_key=pk,
                           dokument_id=dokument_id,
                           betrag=round(betrag, 2) if betrag is not None
                           else None)
            geschrieben.append(pk)
    except Exception as exc:  # pragma: no cover -- Best-Effort
        logger.warning(
            "Beleg aus Freigabe fehlgeschlagen (akte %s, dok %s, klasse %s): %s",
            akte_az, dokument_id, klasse, exc,
        )

    return geschrieben
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_beleg_zuordnung.py -v`
Expected: PASS, 7 Tests

- [ ] **Step 5: `belege_routes` auf den Service umstellen**

In `backend/routers/belege_routes.py` den Upsert-Block (Zeile 415–423) durch
den Service-Aufruf ersetzen; die Dokument-Prüfung darüber bleibt:

```python
            from ..services.beleg_zuordnung import ordne_beleg_zu
            ordne_beleg_zu(akte_az=akte_id, position_key=pos_key,
                           dokument_id=int(dok_id),
                           betrag=(float(betrag) if betrag is not None
                                   else None),
                           notiz=notiz)
```

Der `conn.commit()` an dieser Stelle entfällt — der Service committet selbst.
Der darunterliegende P1.5b-Block (Ereignis `rechnung_eingegangen`) bleibt
unverändert.

- [ ] **Step 6: Freigabe schreibt die Belege mit**

In `backend/routers/intake_routes.py` neben `_schreibe_freigabe_ereignisse`
ergänzen:

```python
def _schreibe_freigabe_belege(*, dok, akte_az, dokument_id):
    from ..services.beleg_zuordnung import belege_aus_freigabe

    try:
        felder = _parse(dok.get("parse_json")).get("felder") or {}
        belege_aus_freigabe(
            akte_az=akte_az, dokument_id=dokument_id,
            klasse=dok.get("klasse") or "", felder=felder,
            vorsteuer=_mandanten_vorsteuer(akte_az),
        )
    except Exception as exc:  # pragma: no cover -- Best-Effort
        logger.warning(
            "Freigabe-Belegphase fehlgeschlagen (intake=%s, akte=%s): %s",
            dok.get("id"), akte_az, exc,
        )
```

Und direkt nach dem `_schreibe_freigabe_ereignisse`-Aufruf (Zeile 929) rufen —
mit derselben Anker-Dokument-ID, damit Re-Freigaben nicht doppeln:

```python
    _schreibe_freigabe_belege(
        dok=dok, akte_az=akte_az,
        dokument_id=_anker_dokument_id(dok.get("id"), dokument_id, akte_az),
    )
```

- [ ] **Step 7: Run tests**

Run: `python -m pytest backend/tests/test_beleg_zuordnung.py backend/tests/test_p15e_freigabe_ereignisse.py backend/tests/test_intake_routes.py -q`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add backend/services/beleg_zuordnung.py backend/routers/belege_routes.py backend/routers/intake_routes.py backend/tests/test_beleg_zuordnung.py
git commit -m "feat(belege): Review-Freigabe traegt ihre Belege in die Belegliste ein"
```

---

## Task 8: Klage liest das Verzugsdatum aus dem Dokumentdatum

**Files:**
- Modify: `backend/routers/klage_routes.py:667–698` (Verzugsdokumente) und `:1043–1049` (Verzugsdatum)
- Test: `backend/tests/test_klage_verzugsdatum.py`

**Interfaces:**
- Consumes: `dokumente.dokument_datum` (Task 1), gefüllt durch Task 4
- Produces: `verzug_dokumente[].datum` bevorzugt `dokument_datum`; Sortierung nach `dokument_datum DESC` statt `hochgeladen_am DESC`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_klage_verzugsdatum.py`:

```python
"""Verzugsdokumente tragen das Datum des Schreibens."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestVerzugsdokumente(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="klvd_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad
        from backend.db.schema_manager import init_db
        init_db()
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('44/22', '2022-04-27', 'offen')"
            )
            conn.execute(
                "INSERT INTO dokumente (akte_id, dateiname, dateipfad, "
                "dateityp, dokumentenklasse, dokument_datum) VALUES "
                "('44/22', 'alt.pdf', 'x', 'pdf', 'forderungsschreiben', "
                " '2024-02-01')"
            )
            conn.execute(
                "INSERT INTO dokumente (akte_id, dateiname, dateipfad, "
                "dateityp, dokumentenklasse, dokument_datum) VALUES "
                "('44/22', 'neu.pdf', 'y', 'pdf', 'forderungsschreiben', "
                " '2024-06-15')"
            )
            conn.commit()

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt_db_path
        os.environ.pop("DB_PATH", None)
        try:
            os.unlink(self._db_pfad)
        except OSError:
            pass

    def test_juengstes_schreiben_steht_vorn(self):
        from backend.routers.klage_routes import _verzug_dokumente
        dokumente = _verzug_dokumente("44/22")
        self.assertEqual(dokumente[0]["dateiname"], "neu.pdf")
        self.assertEqual(dokumente[0]["datum"], "2024-06-15")

    def test_dokument_ohne_datum_faellt_ans_ende(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO dokumente (akte_id, dateiname, dateipfad, "
                "dateityp, dokumentenklasse) VALUES "
                "('44/22', 'ohne.pdf', 'z', 'pdf', 'forderungsschreiben')"
            )
            conn.commit()
        from backend.routers.klage_routes import _verzug_dokumente
        dokumente = _verzug_dokumente("44/22")
        self.assertEqual(dokumente[-1]["dateiname"], "ohne.pdf")
        self.assertIsNone(dokumente[-1]["datum"])

    def test_mahnschreiben_steht_vor_forderungsschreiben(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO dokumente (akte_id, dateiname, dateipfad, "
                "dateityp, dokumentenklasse, dokument_datum) VALUES "
                "('44/22', 'mahn.pdf', 'm', 'pdf', 'mahnschreiben', "
                " '2024-03-01')"
            )
            conn.commit()
        from backend.routers.klage_routes import _verzug_dokumente
        dokumente = _verzug_dokumente("44/22")
        self.assertEqual(dokumente[0]["dokumentenklasse"], "mahnschreiben")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_klage_verzugsdatum.py -v`
Expected: FAIL — `ImportError: cannot import name '_verzug_dokumente'`

- [ ] **Step 3: Abfrage in eine testbare Funktion herausziehen**

In `backend/routers/klage_routes.py` oberhalb des Endpunkts einfügen:

```python
def _verzug_dokumente(az: str) -> list:
    """Mahn-, Verzugs- und Forderungsschreiben der Akte mit ihrem Datum.

    Massgeblich ist dokumente.dokument_datum (Datum des Schreibens); die
    Forderungshistorie dient nur noch als Rueckfall fuer Dokumente, die vor
    Migration 75 angelegt wurden.
    """
    from ..db.database import get_connection
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT d.id, d.dateiname, d.dokumentenklasse, d.hochgeladen_am,
                      COALESCE(
                          d.dokument_datum,
                          (SELECT MAX(fp.datum) FROM forderung_positionen fp
                           WHERE fp.dokument_id = d.id)
                      ) AS datum
               FROM dokumente d
               WHERE d.akte_id = ?
                 AND d.dokumentenklasse IN
                     ('mahnschreiben', 'verzugsschreiben', 'forderungsschreiben')
               ORDER BY
                 CASE d.dokumentenklasse
                   WHEN 'mahnschreiben'    THEN 1
                   WHEN 'verzugsschreiben' THEN 2
                   ELSE 3
                 END,
                 CASE WHEN datum IS NULL THEN 1 ELSE 0 END,
                 datum DESC,
                 d.hochgeladen_am DESC""",
            (az,),
        ).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 4: Aufrufstelle umstellen**

Den `try`-Block bei Zeile 680–698 ersetzen:

```python
        verzug_dokumente = []
        try:
            verzug_dokumente = _verzug_dokumente(az)
        except Exception:
            pass
```

- [ ] **Step 5: Verzugsdatum aus derselben Quelle**

Den Block bei Zeile 1043–1049 ersetzen:

```python
    verzug_datum = None
    for _vd in (verzug_dokumente or []):
        if _vd.get("datum"):
            verzug_datum = _vd["datum"]
            break
    if not verzug_datum and letztes_forderung and letztes_forderung["datum"]:
        verzug_datum = letztes_forderung["datum"]
    if not verzug_datum:
        verzug_datum = _wdm("varSCHREIBENVERZUG") or _wdm("varVERZUGAB") or None
```

- [ ] **Step 6: Run tests**

Run: `python -m pytest backend/tests/test_klage_verzugsdatum.py backend/tests/test_klage_service_docx.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/routers/klage_routes.py backend/tests/test_klage_verzugsdatum.py
git commit -m "feat(klage): Verzugsdatum aus dem Datum des Schreibens"
```

---

## Task 9: Bestandsdokumente nachziehen

**Files:**
- Create: `tools/dokument_datum_nachziehen.py`
- Test: `backend/tests/test_dokument_datum_nachziehen.py`

**Interfaces:**
- Consumes: `dokument_datum_aus_feldern` (Task 2)
- Produces: `nachziehen(trockenlauf: bool = True) -> Dict[str, int]` mit den
  Schlüsseln `geprueft`, `gesetzt`, `ohne_datum`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_dokument_datum_nachziehen.py`:

```python
"""Bestandsdokumente bekommen ihr Datum aus parse_json."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestNachziehen(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="nz_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad
        from backend.db.schema_manager import init_db
        init_db()
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('44/22', '2022-04-27', 'offen')"
            )
            conn.execute(
                "INSERT INTO dokumente (akte_id, dateiname, dateipfad, "
                "dateityp, dokumentenklasse, parse_json) VALUES "
                "('44/22', 'g.pdf', 'x', 'pdf', 'gutachten', ?)",
                (json.dumps({"felder": {"besichtigungsdatum": "14.03.2024"}}),)
            )
            conn.execute(
                "INSERT INTO dokumente (akte_id, dateiname, dateipfad, "
                "dateityp, dokumentenklasse) VALUES "
                "('44/22', 'leer.pdf', 'y', 'pdf', 'gutachten')"
            )
            conn.commit()

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt_db_path
        os.environ.pop("DB_PATH", None)
        try:
            os.unlink(self._db_pfad)
        except OSError:
            pass

    def _datum(self, dateiname):
        from backend.db.database import get_connection
        with get_connection() as conn:
            return conn.execute(
                "SELECT dokument_datum FROM dokumente WHERE dateiname=?",
                (dateiname,)
            ).fetchone()["dokument_datum"]

    def test_trockenlauf_aendert_nichts(self):
        from tools.dokument_datum_nachziehen import nachziehen
        bericht = nachziehen(trockenlauf=True)
        self.assertEqual(bericht["gesetzt"], 1)
        self.assertIsNone(self._datum("g.pdf"))

    def test_schreiblauf_setzt_das_datum(self):
        from tools.dokument_datum_nachziehen import nachziehen
        bericht = nachziehen(trockenlauf=False)
        self.assertEqual(bericht["gesetzt"], 1)
        self.assertEqual(bericht["ohne_datum"], 1)
        self.assertEqual(self._datum("g.pdf"), "2024-03-14")
        self.assertIsNone(self._datum("leer.pdf"))

    def test_zweiter_lauf_ueberschreibt_nichts(self):
        from tools.dokument_datum_nachziehen import nachziehen
        nachziehen(trockenlauf=False)
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "UPDATE dokumente SET dokument_datum='2020-01-01' "
                "WHERE dateiname='g.pdf'"
            )
            conn.commit()
        bericht = nachziehen(trockenlauf=False)
        self.assertEqual(bericht["gesetzt"], 0)
        self.assertEqual(self._datum("g.pdf"), "2020-01-01")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_dokument_datum_nachziehen.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.dokument_datum_nachziehen'`

- [ ] **Step 3: Skript anlegen**

Create `tools/dokument_datum_nachziehen.py`:

```python
"""Fuellt dokumente.dokument_datum aus dem gespeicherten Parse-Ergebnis.

Einmalig nach Migration 75 auszufuehren. Setzt nur leere Felder -- ein von
Hand korrigiertes Datum bleibt unangetastet.

    py tools/dokument_datum_nachziehen.py            # Trockenlauf
    py tools/dokument_datum_nachziehen.py --schreiben
"""
import argparse
import json
import os
import sys
from typing import Dict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def nachziehen(trockenlauf: bool = True) -> Dict[str, int]:
    from backend.db.database import get_connection
    from backend.intake.registry_loader import lade_registry, standard_pfad
    from backend.services.dokument_bezeichnung import (
        dokument_datum_aus_feldern,
    )

    reg = lade_registry(standard_pfad())
    bericht = {"geprueft": 0, "gesetzt": 0, "ohne_datum": 0}

    with get_connection() as conn:
        zeilen = conn.execute(
            "SELECT id, dokumentenklasse, parse_json, hochgeladen_am "
            "FROM dokumente WHERE dokument_datum IS NULL"
        ).fetchall()

        for zeile in zeilen:
            bericht["geprueft"] += 1
            try:
                felder = (json.loads(zeile["parse_json"] or "{}")
                          .get("felder") or {})
            except (ValueError, TypeError):
                felder = {}

            datum = dokument_datum_aus_feldern(
                zeile["dokumentenklasse"], felder, reg,
                eingangsdatum=zeile["hochgeladen_am"],
            )
            if not datum:
                bericht["ohne_datum"] += 1
                continue

            bericht["gesetzt"] += 1
            if not trockenlauf:
                conn.execute(
                    "UPDATE dokumente SET dokument_datum=? WHERE id=?",
                    (datum, zeile["id"]),
                )

        if not trockenlauf:
            conn.commit()

    return bericht


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--schreiben", action="store_true",
                   help="Aenderungen tatsaechlich speichern")
    args = p.parse_args()
    ergebnis = nachziehen(trockenlauf=not args.schreiben)
    modus = "GESCHRIEBEN" if args.schreiben else "TROCKENLAUF"
    print(f"[{modus}] geprueft: {ergebnis['geprueft']}, "
          f"Datum gesetzt: {ergebnis['gesetzt']}, "
          f"ohne Datum: {ergebnis['ohne_datum']}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_dokument_datum_nachziehen.py -v`
Expected: PASS, 3 Tests

- [ ] **Step 5: Trockenlauf gegen die Entwicklungsdatenbank**

Run: `py tools/dokument_datum_nachziehen.py`
Expected: Eine Zeile mit Zahlen. Das Ergebnis notieren — es sagt, wie viele
Bestandsdokumente ein Datum bekommen können. Der Schreiblauf erfolgt erst nach
Abnahme durch RA Schatz.

- [ ] **Step 6: Commit**

```bash
git add tools/dokument_datum_nachziehen.py backend/tests/test_dokument_datum_nachziehen.py
git commit -m "feat(tools): Dokumentdatum fuer Bestandsdokumente nachziehen"
```

---

## Task 10: Vollsuite und Dokumentation

**Files:**
- Modify: `docs/CHANGELOG.md`, `docs/DATAMODEL.md`, `docs/TODO.md`

- [ ] **Step 1: Backend-Vollsuite**

Run: `python -m pytest backend/tests -q`
Expected: PASS. Frühere Sanierungen haben die Suite grün hinterlassen — jede
neue rote Zeile gehört zu dieser Änderung und wird gefixt, nicht übergangen.

- [ ] **Step 2: Frontend-Suite**

Run: `cd frontend && npx vitest run`
Expected: PASS

- [ ] **Step 3: `docs/DATAMODEL.md` ergänzen**

Bei der Tabelle `dokumente` die neue Spalte aufnehmen:

```markdown
| `dokument_datum` | TEXT | Datum des Schreibens (ISO), nicht das Eingangs-
oder Scan-Datum. Abgeleitet aus `bezeichnung_felder.datum` der Klassen-
Registry, bei der Freigabe korrigierbar, nullable. Migration 75. |
```

- [ ] **Step 4: `docs/CHANGELOG.md` ergänzen**

Oben einfügen, Datum des Abschlusses einsetzen:

```markdown
## <Datum> — Belegkette Fundament (R1 + R2)

Migration 75 gibt `dokumente` die Spalte `dokument_datum`: das Datum, das auf
dem Schreiben steht, nicht der Tag des Einlesens. Es wird aus der
`bezeichnung_felder.datum`-Rolle der Klassen-Registry abgeleitet (22 der 23
Klassen tragen sie) und ist im Freigabe-Dialog korrigierbar. Freigabe-
Ereignisse tragen dieses Datum statt „heute"; die Verzugsliste im Klage-Wizard
sortiert danach.

Die Review-Freigabe trägt ihre Belege jetzt selbst in `schadenposition_belege`
ein — bisher tat das nur die manuelle Zuordnung, weshalb geparste Rechnungen
in der Belegliste fehlten. Einziger Schreibweg ist
`backend/services/beleg_zuordnung.py`.

Bestandsdokumente füllt `tools/dokument_datum_nachziehen.py` nach
(Trockenlauf per Vorgabe).

Regeln R1 und R2 aus
`docs/superpowers/specs/2026-09-07-belegkette-beweisantritt-design.md`.
R3–R5 (Anlagennummern, „b.b.", Beweismittel-Schritt) stehen aus.
```

- [ ] **Step 5: `docs/TODO.md` fortschreiben**

R3–R5 (Anlagennummern, „b.b.", Beweismittel-Schritt im Wizard) als nächsten
Schritt eintragen, dazu die offenen Punkte 2 (`pruefbericht`-Datumsfeld) und 6
(toter Zweig `verzugsschreiben`) aus der Spec.

- [ ] **Step 6: Commit**

```bash
git add docs/CHANGELOG.md docs/DATAMODEL.md docs/TODO.md
git commit -m "docs: Belegkette-Fundament (R1+R2) dokumentiert"
```

---

## Abnahme durch RA Schatz

Nach Task 10 im laufenden Betrieb prüfen:

1. Ein Gutachten in die Review-Queue geben, freigeben. Das Datumsfeld im
   Dialog steht vorbelegt auf dem Besichtigungsdatum.
2. In der Akte unter den Schadenpositionen erscheinen die Gutachten-Positionen
   **mit** dem Gutachten als Beleg — ohne dass etwas von Hand zugeordnet wurde.
3. Eine Mietwagenrechnung freigeben. Sie steht sofort als Beleg an der Position
   Mietwagenkosten.
4. Ein altes Forderungsschreiben einscannen und mit dem Datum von damals
   freigeben. Im Klage-Wizard steht es in der Verzugsliste an der richtigen
   Stelle, mit seinem Datum.
