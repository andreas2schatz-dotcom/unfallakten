# Dokumentenklasse als SSOT — Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die im Intake vergebene Dokumentklasse überlebt die Review-Freigabe; `dokumente.typ` entfällt ersatzlos, `dokumente.dokumentenklasse` ist die alleinige Wahrheit.

**Architecture:** `registriere_dokument()` wird der einzige Schreibpunkt, der die Klasse gegen die Registry prüft. Zuerst schreiben beide Spalten konsistent (Bug behoben, System lauffähig), dann werden alle Leser umgestellt, zuletzt fällt die Spalte per Migration. Zwei Migrationen: 73 füllt nach (nicht destruktiv), 74 entfernt die Spalte — so bleibt jeder Zwischenstand lauffähig.

**Tech Stack:** Python 3.14 / Flask / SQLite 3.46 · React 18 / Vite / Vitest · pytest / unittest · Docker Compose

**Spec:** `docs/superpowers/specs/2026-09-02-dokumentenklasse-ssot-design.md`

## Global Constraints

- **Zielsprache Deutsch.** Alle Meldungen, Docstrings und Commit-Texte auf Deutsch. Umlaute in Python-Docstrings umschreiben (`ue`, `ae`, `oe`), wie im Bestand üblich.
- **Keine Kommentare im Code** außer bei nicht-offensichtlichem Verhalten.
- **Keine unnötigen Abstraktionen** — nur umsetzen, was hier steht.
- **RA-MICRO ist read-only.** Es wird ausschließlich in SQLite geschrieben.
- **Migrationen atomar in EINEM Edit schreiben.** Der Flask-Reloader greift sonst einen Zwischenstand ab, stempelt die Version und lässt die Änderung aus. Betraf bereits die Migrationen 54, 55, 58, 60, 71.
- **Niemals `executescript()`** für `ALTER TABLE`; explizites `conn.commit()` davor und danach.
- **Die aktive Entwicklungsdatenbank liegt im Docker-Volume** (`/app/data/unfallakten.db` im Container), nicht unter `backend/data/`.
- **Backend-Tests:** `python -m pytest backend/tests/ --tb=short -q`
- **Frontend-Tests:** `cd frontend && npm test` (`vitest run`)
- **Testregeln aus `backend/tests/conftest.py`:** Admin ist `admin@test.de` / `Admin123!`; jeder RA-MICRO-Zugriff muss gemockt sein (sonst `EchteRamicroVerbindungVersucht`); jede Fixture setzt ihren eigenen `DB_PATH`.
- **Ausgangslage:** `schema_version` = 72, Vollsuite 2207 grün (Stand 2026-09-02).

---

## Dateiübersicht

| Datei | Verantwortung nach dem Umbau |
|---|---|
| `backend/models/dokument.py` | Einziger Schreibpunkt für `dokumente`; prüft die Klasse gegen die Registry |
| `backend/ramicro/output_adapter.py` | Freigabe → Akte: Klasse und Parse-Ergebnis werden 1:1 übernommen |
| `backend/db/schema_manager.py` | Migration 73 (Nachfüllen + Index), Migration 74 (Spalte entfernen) |
| `backend/db/schema.py` | Tabellendefinition ohne `typ` |
| `backend/routers/intake_routes.py` | `/intake/klassen` liefert Wert **und** Label |
| `frontend/src/views/ReviewQueueView.jsx` | Zeigt Labels statt technischer Schlüssel |
| `backend/services/portal_sync.py` | Sync-Payload mit `klasse` + `klasse_label` |
| `backend/tests/test_dokumentenklasse_ssot.py` | **neu** — Verhaltenstest der Freigabe |
| `backend/tests/test_dokumente_typ_guard.py` | **neu** — statischer Guard gegen Rückfall |
| `backend/tests/test_migration_73_74.py` | **neu** — Migrationstest auf Frisch-Datenbank |

---

## Task 1: ReviewQueue zeigt Labels statt Schlüssel

Rein kosmetisch und von allem anderen unabhängig. Bewusst zuerst, weil der Task nichts blockiert und nichts blockiert wird.

**Files:**
- Modify: `backend/routers/intake_routes.py:600-611`
- Modify: `frontend/src/views/ReviewQueueView.jsx:24-33, 1665-1666, 1925-1927`
- Test: `backend/tests/test_intake_routes.py:245-260`
- Test: `frontend/src/views/ReviewQueueView.klassenlabels.test.jsx` (neu)

**Interfaces:**
- Consumes: nichts aus früheren Tasks.
- Produces: `GET /intake/klassen` → `{"klassen": [{"wert": str, "label": str}, ...]}`, aufsteigend nach `wert` sortiert. Kein späterer Task hängt daran.

- [ ] **Step 1: Bestehenden Endpoint-Test lesen und anpassen**

`backend/tests/test_intake_routes.py` Zeile 245-260 ansehen. Der Test prüft heute eine Liste von Zeichenketten. Ersetze die Zusicherung durch:

```python
    def test_klassen_liefert_wert_und_label(self):
        r = self.client.get("/intake/klassen", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        klassen = r.get_json()["klassen"]
        self.assertTrue(klassen)
        eintrag = {k["wert"]: k["label"] for k in klassen}
        self.assertEqual(eintrag["sv_rechnung"], "SV-/Gutachterrechnung")
        self.assertEqual(eintrag["fragebogen"], "Unfallfragebogen")
        self.assertEqual([k["wert"] for k in klassen],
                         sorted(k["wert"] for k in klassen))
```

Der vorhandene Test ohne Header (401-Fall) bleibt unverändert.

- [ ] **Step 2: Test laufen lassen, Fehlschlag bestätigen**

Run: `python -m pytest backend/tests/test_intake_routes.py -k klassen -v`
Expected: FAIL — `TypeError: string indices must be integers` oder `KeyError: 'wert'`

- [ ] **Step 3: Endpoint umstellen**

`backend/routers/intake_routes.py`, in `hole_klassen()` die Rückgabe ersetzen:

```python
    from ..intake.registry_loader import lade_registry, standard_pfad
    reg = lade_registry(standard_pfad())
    return _j({"klassen": [
        {"wert": k, "label": d.get("label", k)}
        for k, d in sorted(reg.klassen.items())
    ]})
```

Den Docstring anpassen — die Beispiel-Response dort zeigt noch die alte Form.

- [ ] **Step 4: Test laufen lassen, grün bestätigen**

Run: `python -m pytest backend/tests/test_intake_routes.py -k klassen -v`
Expected: PASS

- [ ] **Step 5: Frontend-Test schreiben**

Neue Datei `frontend/src/views/ReviewQueueView.klassenlabels.test.jsx`:

```jsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const api = vi.hoisted(() => ({
  apiIntake: {
    queue: vi.fn(() => Promise.resolve({ eintraege: [
      { id: 461, klasse: "sv_rechnung",
        queue_status: "bereit_zur_review", konfidenz: 0.9,
        erstellt_am: "2026-08-04 06:19:47" },
    ] })),
    detail: vi.fn(() => Promise.resolve({ id: 461, klasse: "sv_rechnung",
      queue_status: "bereit_zur_review", felder: {}, parse: {},
      akten_kandidaten: [], zustellungen: [] })),
    ereignistypen: vi.fn(() => Promise.resolve({ typen: [] })),
    klassen: vi.fn(() => Promise.resolve({ klassen: [
      { wert: "sonstiges",   label: "Sonstiges" },
      { wert: "sv_rechnung", label: "SV-/Gutachterrechnung" },
    ] })),
  },
  apiAktenanlage: { offen: vi.fn(() => Promise.resolve({ vorgaenge: [], ramicro_verfuegbar: true })) },
  tokenStore: { getAccess: vi.fn(() => "test-token") },
  API_BASE: "http://localhost:5000",
}));
vi.mock("../api", () => api);

import ReviewQueueView from "./ReviewQueueView.jsx";

describe("ReviewQueueView Klassen-Labels", () => {
  it("zeigt im Dropdown das Label, nicht den technischen Schluessel", async () => {
    render(<ReviewQueueView onOpenAkte={() => {}} initialIntakeId={461} />);
    const option = await screen.findByRole("option", { name: "SV-/Gutachterrechnung" });
    expect(option).toHaveValue("sv_rechnung");
    expect(screen.queryByRole("option", { name: "sv_rechnung" })).toBeNull();
  });

  it("zeigt die Klasse der Trefferliste als Label", async () => {
    render(<ReviewQueueView onOpenAkte={() => {}} />);
    await waitFor(() => expect(api.apiIntake.queue).toHaveBeenCalled());
    expect(await screen.findByText("SV-/Gutachterrechnung")).toBeInTheDocument();
  });
});
```

- [ ] **Step 6: Frontend-Test laufen lassen, Fehlschlag bestätigen**

Run: `cd frontend && npx vitest run src/views/ReviewQueueView.klassenlabels.test.jsx`
Expected: FAIL — die Option heißt noch `sv_rechnung`

- [ ] **Step 7: ReviewQueueView umstellen**

Drei Änderungen in `frontend/src/views/ReviewQueueView.jsx`:

**a)** `KLASSEN_FALLBACK` (Zeile 24-33) samt vorangehendem Kommentar ersatzlos löschen.

**b)** Dropdown (Zeile 1665-1666) ersetzen:

```jsx
              {(klassen || []).map(k =>
                <option key={k.wert} value={k.wert}>{k.label}</option>)}
```

**c)** Ladefehler nicht mehr stillschweigend schlucken (Zeile 1925-1927):

```jsx
    apiIntake.klassen()
      .then(d => setKlassen(d.klassen || []))
      .catch(() => setKlassenFehler(true));
```

Dazu oben bei den übrigen `useState`-Aufrufen `const [klassenFehler, setKlassenFehler] = useState(false);` ergänzen und direkt unter dem `<select>` ausgeben:

```jsx
            {klassenFehler && (
              <div style={{ color: T.danger, fontSize: T.textXs, marginTop: 4 }}>
                Klassenliste konnte nicht geladen werden — bitte Seite neu laden.
              </div>
            )}
```

- [ ] **Step 8: Anzeige der Klasse an den drei Textstellen auf Labels umstellen**

Direkt unter der `KLASSEN_FALLBACK`-Löschstelle einen Helfer einsetzen:

```jsx
function klasseLabel(klassen, wert) {
  if (!wert) return "unbekannt";
  return (klassen || []).find(k => k.wert === wert)?.label || wert;
}
```

Anwenden an Zeile 512, 1184 und 2178 — jeweils `{item.klasse || "unbekannt"}` bzw. `{dokument.klasse}` durch `{klasseLabel(klassen, item.klasse)}` ersetzen. An allen drei Stellen muss `klassen` als Prop durchgereicht werden; die Komponenten in Zeile 488ff. und 1290ff. erhalten es analog zu `ereignistypen`.

- [ ] **Step 9: Frontend-Tests laufen lassen**

Run: `cd frontend && npm test`
Expected: PASS — auch die bestehenden ReviewQueueView-Tests. Schlägt einer fehl, weil er auf den rohen Schlüssel prüft, ist er mitzuziehen.

- [ ] **Step 10: Commit**

```bash
git add backend/routers/intake_routes.py backend/tests/test_intake_routes.py \
        frontend/src/views/ReviewQueueView.jsx \
        frontend/src/views/ReviewQueueView.klassenlabels.test.jsx
git commit -m "feat(review): Klassen-Dropdown zeigt Registry-Labels statt Schluessel"
```

---

## Task 2: `registriere_dokument()` nimmt die Klasse und prüft sie

Der Kern. Nach diesem Task ist der gemeldete Fehler weg: die Klasse überlebt die Freigabe. `typ` existiert noch und wird aus der Klasse abgeleitet, damit alle Leser unverändert weiterarbeiten.

**Files:**
- Modify: `backend/models/dokument.py:79-165, 193-204`
- Modify: `backend/ramicro/output_adapter.py:12-16, 25, 28-32, 64, 83-91`
- Modify (Schreiber): `backend/email_import/import_service.py:326, 786, 816, 1193` · `backend/pdf/upload_service.py:151-155, 173` · `backend/routers/belege_routes.py:755` · `backend/routers/eakte_routes.py:256` · `backend/routers/klage_routes.py:1453` · `backend/routers/sta_routes.py:144` · `backend/routers/stellungnahme_routes.py:128` · `backend/scripts/seed_db.py:97`
- Modify: `backend/routers/dokumente_routes.py:22`
- Test: `backend/tests/test_dokumentenklasse_ssot.py` (neu)
- Test: `backend/tests/test_output_adapter.py:93-136`

**Interfaces:**
- Consumes: nichts aus Task 1.
- Produces:
  - `registriere_dokument(akte_id: str, dokumentenklasse: str, dateiname: str, dateipfad: str, bearbeiter_id: Optional[int] = None, dateityp: str = "pdf", dateigroesse: Optional[int] = None) -> Dokument` — `typ` als Parameter entfällt vollständig.
  - `pruefe_dokumentenklasse(klasse: str) -> str` in `backend/models/dokument.py` — liefert die Klasse zurück oder wirft `ValueError`.
  - `Dokument.dokumentenklasse` ist gesetzt; `Dokument.typ` existiert noch (bis Task 8).

- [ ] **Step 1: Den roten Test schreiben**

Neue Datei `backend/tests/test_dokumentenklasse_ssot.py`. Der Aufbau (temporäre Datenbank, Akte, Benutzer, Intake-Zeile) ist derselbe wie in `backend/tests/test_output_adapter.py:18-75` — von dort übernehmen.

```python
"""
Die im Intake vergebene Klasse muss die Review-Freigabe ueberleben.

Regressionstest zum Befund vom 2026-09-02: _map_klasse() im output_adapter
liess 17 der 23 Registry-Klassen auf 'sonstiges' fallen und schrieb
dokumente.dokumentenklasse ueberhaupt nicht.
"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestKlasseUeberlebtFreigabe(unittest.TestCase):
    # setUp/tearDown/_lege_intake_an wortgleich aus test_output_adapter.py

    def test_feinklasse_landet_in_dokumentenklasse(self):
        from backend.ramicro.output_adapter import schreibe_dokument
        from backend.db.database import get_connection

        for klasse in ("sv_rechnung", "pruefbericht", "mietwagenrechnung",
                       "fragebogen", "verdienstausfall_nachweis"):
            with self.subTest(klasse=klasse):
                did = self._lege_intake_an(klasse)
                with get_connection() as conn:
                    intake = dict(conn.execute(
                        "SELECT * FROM intake_dokumente WHERE id=?", (did,)
                    ).fetchone())
                dokument_id = schreibe_dokument(intake, "31/21",
                                                freigegeben_von=1)
                with get_connection() as conn:
                    row = conn.execute(
                        "SELECT dokumentenklasse FROM dokumente WHERE id=?",
                        (dokument_id,)
                    ).fetchone()
                self.assertEqual(row["dokumentenklasse"], klasse)

    def test_unbekannte_klasse_wird_abgelehnt(self):
        from backend.models.dokument import registriere_dokument

        with self.assertRaises(ValueError):
            registriere_dokument(
                akte_id="31/21", dokumentenklasse="gibt_es_nicht",
                dateiname="x.pdf", dateipfad="/tmp/x.pdf", bearbeiter_id=1,
            )


if __name__ == "__main__":
    unittest.main()
```

`_lege_intake_an` muss dabei eindeutige SHA-Werte erzeugen, weil die Schleife mehrere Intake-Zeilen anlegt — ersetze `("a" * 64, ...)` durch einen Zähler, z. B. `(klasse.ljust(64, "x")[:64], ...)`.

- [ ] **Step 2: Test laufen lassen, Fehlschlag bestätigen**

Run: `python -m pytest backend/tests/test_dokumentenklasse_ssot.py -v`
Expected: FAIL — `dokumentenklasse` ist `None`, und `registriere_dokument` kennt den Parameter noch nicht.

- [ ] **Step 3: Registry-Prüfung und neue Signatur im Model**

In `backend/models/dokument.py`: `GUELTIGE_TYPEN` (Zeile 80-83) löschen und ersetzen durch:

```python
GUELTIGE_DATEITYPEN = ("pdf", "docx", "jpg", "png", "sonstiges")
GUELTIGE_PARSE_STATUS = ("ausstehend", "erfolgreich", "fehler", "manuell_korrigiert")


def pruefe_dokumentenklasse(klasse: str) -> str:
    """Prueft eine Dokumentklasse gegen die Registry (SSOT).

    Fail-loud: eine unbekannte Klasse ist ein Programmierfehler, kein
    Anwenderfehler -- sie wuerde sonst still als nicht auffindbares
    Dokument in der Akte landen.
    """
    from ..intake.registry_loader import lade_registry, standard_pfad
    erlaubt = lade_registry(standard_pfad()).klassen
    if klasse not in erlaubt:
        raise ValueError(
            "Unbekannte Dokumentklasse %r. Erlaubt sind die Klassen aus "
            "backend/registry/klassen/: %s"
            % (klasse, ", ".join(sorted(erlaubt)))
        )
    return klasse
```

Die bestehende Zeile `GUELTIGE_DATEITYPEN = …` und `GUELTIGE_PARSE_STATUS = …` dabei nicht doppeln — sie stehen bereits darunter und bleiben unverändert.

`registriere_dokument()` umbauen (Zeile 114-165):

```python
def registriere_dokument(akte_id: int, dokumentenklasse: str, dateiname: str,
                          dateipfad: str, bearbeiter_id: Optional[int] = None,
                          dateityp: str = "pdf",
                          dateigroesse: Optional[int] = None) -> Dokument:
    """Registriert ein hochgeladenes Dokument in der Datenbank."""
    pruefe_dokumentenklasse(dokumentenklasse)
    if dateityp not in GUELTIGE_DATEITYPEN:
        raise ValueError(f"Ungültiger Dateityp: {dateityp!r}")

    typ = dokumentenklasse if dokumentenklasse in _ALT_TYP_WERTE else "sonstiges"

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO dokumente
                (akte_id, typ, dokumentenklasse, dateiname, dateipfad,
                 dateityp, dateigroesse, hochgeladen_von)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (akte_id, typ, dokumentenklasse, dateiname, dateipfad, dateityp,
             dateigroesse, bearbeiter_id)
        )
        doc_id = cursor.lastrowid
        # ... Aktivitaets-Log unveraendert, aber (typ) -> (dokumentenklasse)
        #     in der Beschreibung
```

Und den Rückgabewert um `dokumentenklasse=dokumentenklasse` ergänzen.

Über `registriere_dokument` die Übergangskonstante setzen — sie verschwindet in Task 8:

```python
# Uebergangsweise: dokumente.typ faellt in Migration 74. Bis dahin wird die
# Spalte aus der Klasse abgeleitet, damit die verbliebenen Leser weiterlaufen.
_ALT_TYP_WERTE = ("gutachten", "abrechnungsschreiben", "forderungsschreiben",
                  "sachstandsanfrage", "klage", "sonstiges")
```

- [ ] **Step 4: `output_adapter` entrümpeln**

In `backend/ramicro/output_adapter.py`:

- Modul-Docstring Zeile 12-16 ersetzen durch: `Die im Intake vergebene Klasse wird unveraendert nach dokumente.dokumentenklasse uebernommen.`
- Import Zeile 25: `from ..models.dokument import registriere_dokument`
- `_map_klasse()` (Zeile 28-32) ersatzlos löschen.
- Zeile 64 `typ = _map_klasse(...)` löschen.
- Aufruf Zeile 83-91: `typ=typ,` ersetzen durch `dokumentenklasse=intake_dok.get("klasse") or "sonstiges",`

- [ ] **Step 5: Test laufen lassen, grün bestätigen**

Run: `python -m pytest backend/tests/test_dokumentenklasse_ssot.py -v`
Expected: PASS

- [ ] **Step 6: Die übrigen elf Schreiber umstellen**

Jeweils `typ=` durch `dokumentenklasse=` ersetzen:

| Datei:Zeile | neuer Wert |
|---|---|
| `backend/email_import/import_service.py:326` | `dokumentenklasse = "sonstiges",` |
| `backend/email_import/import_service.py:786` | `dokumentenklasse = "sonstiges",` — die Bedingung `"gutachten" if "gutachten" in fn.lower() else …` entfällt ersatzlos (Spec 7.1) |
| `backend/email_import/import_service.py:816` | `dokumentenklasse = "sonstiges",` |
| `backend/email_import/import_service.py:1193` | `dokumentenklasse = "sonstiges",` |
| `backend/routers/belege_routes.py:755` | `dokumentenklasse="sonstiges",` |
| `backend/routers/eakte_routes.py:256` | `dokumentenklasse="sonstiges",` — Kommentar berichtigen: `# Dispatcher setzt danach die echte Klasse` |
| `backend/routers/klage_routes.py:1453` | `dokumentenklasse="klage",` |
| `backend/routers/sta_routes.py:144` | `dokumentenklasse="sachstandsanfrage",` |
| `backend/routers/stellungnahme_routes.py:128` | `dokumentenklasse="sonstiges",` |
| `backend/scripts/seed_db.py:97` | `dokumentenklasse="gutachten",` |

In `backend/pdf/upload_service.py`:
- Import Zeile 30-31: `GUELTIGE_TYPEN` entfernen.
- Zeile 150-155: die `GUELTIGE_TYPEN`-Prüfung ersetzen:

```python
    from ..models.dokument import pruefe_dokumentenklasse
    try:
        pruefe_dokumentenklasse(typ)
    except ValueError as e:
        raise UploadFehler(str(e))
```

- Zeile 173: `typ=typ,` → `dokumentenklasse=typ,`

In `backend/routers/dokumente_routes.py:22` den Import von `GUELTIGE_TYPEN` entfernen.

- [ ] **Step 7: `test_output_adapter.py` an das neue Sollverhalten anpassen**

`backend/tests/test_output_adapter.py`:
- Zeile 93 und 98: `typ` → `dokumentenklasse`, erwarteter Wert bleibt `"abrechnungsschreiben"`.
- Zeile 102-118: `test_unbekannte_klasse_mappt_auf_sonstiges` **ersetzen** — der Test beschreibt heute den Fehler als Sollverhalten:

```python
    def test_feinklasse_faellt_nicht_mehr_auf_sonstiges(self):
        from backend.ramicro.output_adapter import schreibe_dokument
        from backend.db.database import get_connection

        did = self._lege_intake_an("pruefbericht")
        with get_connection() as conn:
            intake = dict(conn.execute(
                "SELECT * FROM intake_dokumente WHERE id=?", (did,)
            ).fetchone())

        dokument_id = schreibe_dokument(intake, "31/21", freigegeben_von=1)

        with get_connection() as conn:
            row = conn.execute(
                "SELECT dokumentenklasse FROM dokumente WHERE id=?",
                (dokument_id,)
            ).fetchone()
        self.assertEqual(row["dokumentenklasse"], "pruefbericht")
```

- Zeile 120-136: `typ` → `dokumentenklasse`.

- [ ] **Step 8: Vollsuite laufen lassen**

Run: `python -m pytest backend/tests/ --tb=short -q`
Expected: PASS. Erwartete Ausfälle sind Tests, die `registriere_dokument(typ=…)` aufrufen — diese auf `dokumentenklasse=` umstellen. Betroffen sind laut Erhebung u. a. `test_modul1.py`, `test_p14_ausgehend_e2e.py`, `test_sta_service.py`. Tests, die per `INSERT INTO dokumente` direkt schreiben, laufen unverändert weiter und bleiben vorerst unangetastet.

- [ ] **Step 9: Commit**

```bash
git add -u backend/
git commit -m "fix(intake): Freigabe uebernimmt die Dokumentklasse in die Akte

_map_klasse() liess 17 der 23 Registry-Klassen auf 'sonstiges' fallen und
schrieb dokumente.dokumentenklasse gar nicht. registriere_dokument() nimmt
jetzt die Klasse, prueft sie gegen die Registry und leitet den alten
typ-Wert daraus ab."
```

---

## Task 3: Parse-Ergebnis mit übertragen

**Files:**
- Modify: `backend/ramicro/output_adapter.py:83-99`
- Test: `backend/tests/test_dokumentenklasse_ssot.py`

**Interfaces:**
- Consumes: `registriere_dokument(..., dokumentenklasse=…)` aus Task 2.
- Produces: nach der Freigabe sind `dokumente.parse_json`, `parse_konfidenz` und `parse_status` gefüllt, sofern das Intake-Dokument sie führt.

- [ ] **Step 1: Test ergänzen**

An `backend/tests/test_dokumentenklasse_ssot.py` anhängen. `_lege_intake_an` um zwei Parameter erweitern (`parse_json=None, konfidenz=None`) und in das `INSERT` aufnehmen — `intake_dokumente` führt die Spalten `parse_json` und `konfidenz`.

```python
    def test_parse_ergebnis_wandert_in_die_akte(self):
        from backend.ramicro.output_adapter import schreibe_dokument
        from backend.db.database import get_connection

        did = self._lege_intake_an(
            "sv_rechnung",
            parse_json='{"felder": {"bruttobetrag": 992.34}}',
            konfidenz=0.91,
        )
        with get_connection() as conn:
            intake = dict(conn.execute(
                "SELECT * FROM intake_dokumente WHERE id=?", (did,)
            ).fetchone())

        dokument_id = schreibe_dokument(intake, "31/21", freigegeben_von=1)

        with get_connection() as conn:
            row = conn.execute(
                "SELECT parse_json, parse_konfidenz, parse_status "
                "FROM dokumente WHERE id=?", (dokument_id,)
            ).fetchone()
        self.assertIn("bruttobetrag", row["parse_json"])
        self.assertAlmostEqual(row["parse_konfidenz"], 0.91)
        self.assertEqual(row["parse_status"], "erfolgreich")

    def test_ohne_parse_json_bleibt_status_ausstehend(self):
        from backend.ramicro.output_adapter import schreibe_dokument
        from backend.db.database import get_connection

        did = self._lege_intake_an("sonstiges")
        with get_connection() as conn:
            intake = dict(conn.execute(
                "SELECT * FROM intake_dokumente WHERE id=?", (did,)
            ).fetchone())

        dokument_id = schreibe_dokument(intake, "31/21", freigegeben_von=1)

        with get_connection() as conn:
            row = conn.execute(
                "SELECT parse_json, parse_status FROM dokumente WHERE id=?",
                (dokument_id,)
            ).fetchone()
        self.assertIsNone(row["parse_json"])
        self.assertEqual(row["parse_status"], "ausstehend")
```

- [ ] **Step 2: Test laufen lassen, Fehlschlag bestätigen**

Run: `python -m pytest backend/tests/test_dokumentenklasse_ssot.py -k parse -v`
Expected: FAIL — `parse_json` ist `None`

- [ ] **Step 3: Übernahme einbauen**

In `backend/ramicro/output_adapter.py` den Nachtrag-Block am Ende von `schreibe_dokument()` (Zeile 92-98, heute nur `bezeichnung`) erweitern:

```python
    parse_json = intake_dok.get("parse_json")
    felder = {
        "bezeichnung": bezeichnung or None,
        "parse_json": parse_json,
        "parse_konfidenz": intake_dok.get("konfidenz"),
        "parse_status": "erfolgreich" if parse_json else "ausstehend",
    }
    gesetzt = {k: v for k, v in felder.items() if v is not None}
    if gesetzt:
        from ..db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "UPDATE dokumente SET %s WHERE id=?"
                % ", ".join("%s=?" % k for k in gesetzt),
                (*gesetzt.values(), dokument.id),
            )
    return int(dokument.id)
```

- [ ] **Step 4: Test laufen lassen, grün bestätigen**

Run: `python -m pytest backend/tests/test_dokumentenklasse_ssot.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -u backend/
git commit -m "fix(intake): Freigabe uebernimmt parse_json und Konfidenz in die Akte"
```

---

## Task 4: Migration 73 — Altbestand nachfüllen

Nicht destruktiv. Bewusst getrennt von Migration 74, damit die Leser in Task 5/6 auf einer bereits gefüllten Spalte arbeiten.

**Files:**
- Modify: `backend/db/schema_manager.py:329` (MIGRATIONS-Dict), `:2319` (Dispatch-Kette), neue Funktion `_run_migration_73`
- Test: `backend/tests/test_migration_73_74.py` (neu)

**Interfaces:**
- Consumes: nichts.
- Produces: `dokumente.dokumentenklasse` ist für alle Zeilen gesetzt; `idx_dok_klasse` existiert; `schema_version` = 73.

- [ ] **Step 1: Migrationstest schreiben**

Neue Datei `backend/tests/test_migration_73_74.py`:

```python
"""
Migration 73 (Nachfuellen) und 74 (dokumente.typ entfernen).

Prueft auf einer Frisch-Datenbank mit kuenstlichem Altbestand, dass die
Feinklasse aus der Freigabe uebernommen wird, Altwerte ohne Registry-
Entsprechung bereinigt werden und die Spalte danach verschwindet.
"""
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestMigration73Nachfuellen(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="mig73_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        self._alt = _db.DB_PATH
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad
        from backend.db.schema_manager import init_db
        init_db()

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt
        os.environ.pop("DB_PATH", None)
        try:
            os.unlink(self._db_pfad)
        except OSError:
            pass

    def test_klasse_kommt_aus_der_freigabe(self):
        from backend.db.database import get_connection
        from backend.db.schema_manager import _run_migration_73
        with get_connection() as conn:
            conn.execute("INSERT INTO unfallakte (az, unfalldatum, status) "
                         "VALUES ('31/21','2021-04-27','offen')")
            conn.execute(
                "INSERT INTO dokumente (id, akte_id, typ, dokumentenklasse, "
                " dateiname, dateipfad) "
                "VALUES (1,'31/21','sonstiges',NULL,'a.pdf','/tmp/a.pdf')")
            conn.execute(
                "INSERT INTO intake_dokumente (id, sha256, arbeitskopie_pfad, "
                " klasse, queue_status) "
                "VALUES (7, ?, '/tmp/a.pdf','sv_rechnung','freigegeben')",
                ("a" * 64,))
            conn.execute("INSERT INTO freigaben (intake_dokument_id, akte_az, "
                         "dokument_id) VALUES (7,'31/21',1)")
            conn.commit()
            _run_migration_73(conn)
            row = conn.execute("SELECT dokumentenklasse FROM dokumente "
                               "WHERE id=1").fetchone()
        self.assertEqual(row["dokumentenklasse"], "sv_rechnung")

    def test_altwerte_ohne_registry_werden_bereinigt(self):
        from backend.db.database import get_connection
        from backend.db.schema_manager import _run_migration_73
        with get_connection() as conn:
            conn.execute("INSERT INTO unfallakte (az, unfalldatum, status) "
                         "VALUES ('31/21','2021-04-27','offen')")
            for i, k in ((1, "gutachterrechnung"), (2, "versicherung")):
                conn.execute(
                    "INSERT INTO dokumente (id, akte_id, typ, "
                    " dokumentenklasse, dateiname, dateipfad) "
                    "VALUES (?,'31/21','sonstiges',?,'a.pdf','/tmp/a.pdf')",
                    (i, k))
            conn.commit()
            _run_migration_73(conn)
            werte = [r["dokumentenklasse"] for r in conn.execute(
                "SELECT dokumentenklasse FROM dokumente ORDER BY id")]
        self.assertEqual(werte, ["sv_rechnung", "sonstiges"])

    def test_ohne_freigabe_faellt_auf_typ_zurueck(self):
        from backend.db.database import get_connection
        from backend.db.schema_manager import _run_migration_73
        with get_connection() as conn:
            conn.execute("INSERT INTO unfallakte (az, unfalldatum, status) "
                         "VALUES ('31/21','2021-04-27','offen')")
            conn.execute(
                "INSERT INTO dokumente (id, akte_id, typ, dokumentenklasse, "
                " dateiname, dateipfad) "
                "VALUES (1,'31/21','klage',NULL,'k.pdf','/tmp/k.pdf')")
            conn.commit()
            _run_migration_73(conn)
            row = conn.execute("SELECT dokumentenklasse FROM dokumente "
                               "WHERE id=1").fetchone()
        self.assertEqual(row["dokumentenklasse"], "klage")

    def test_index_auf_dokumentenklasse_existiert(self):
        from backend.db.database import get_connection
        from backend.db.schema_manager import _run_migration_73
        with get_connection() as conn:
            _run_migration_73(conn)
            namen = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND tbl_name='dokumente'")]
        self.assertIn("idx_dok_klasse", namen)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Test laufen lassen, Fehlschlag bestätigen**

Run: `python -m pytest backend/tests/test_migration_73_74.py -v`
Expected: FAIL — `ImportError: cannot import name '_run_migration_73'`

- [ ] **Step 3: Migration 73 schreiben — in EINEM Edit**

> **Achtung Reloader-Falle:** Dict-Eintrag, Dispatch-Zweig und Funktion müssen in **einem einzigen** Schreibvorgang in die Datei. Bei getrennten Edits stempelt der Reloader die Version über den generischen else-Zweig, ohne die Migration auszuführen. Betraf bereits 54, 55, 58, 60, 71.

**a)** `backend/db/schema_manager.py` Zeile 329, nach dem 72er-Eintrag:

```python
    73: "-- migration_73_dokumentenklasse_nachfuellen",  # Handled by _run_migration_73
```

**b)** Zeile 2319, nach `elif version == 72:`:

```python
            elif version == 73:
                _run_migration_73(conn)
```

**c)** Neue Funktion direkt nach `_run_migration_72`:

```python
def _run_migration_73(conn: sqlite3.Connection) -> None:
    """
    Migration 73: dokumente.dokumentenklasse fuer den Altbestand nachfuellen.

    Bis 2026-09-02 schrieb die Review-Freigabe nur dokumente.typ (sechs
    Grobwerte) und liess dokumentenklasse leer. Die Feinklasse steht in
    intake_dokumente.klasse und wird ueber die freigaben-Tabelle
    zurueckgeholt; ohne Freigabe dient der alte typ-Wert als Rueckfall.

    Der typ-Zugriff ist bewusst abgesichert: Migration 74 entfernt die
    Spalte, und auf einer Frisch-Datenbank laufen alle Migrationen der
    Reihe nach -- dort existiert typ dann nicht mehr.
    """
    conn.commit()
    spalten = {r[1] for r in conn.execute(
        "PRAGMA table_info(dokumente)").fetchall()}

    if "typ" in spalten:
        conn.execute("""
            UPDATE dokumente SET dokumentenklasse = COALESCE(
                dokumentenklasse,
                (SELECT i.klasse FROM freigaben f
                   JOIN intake_dokumente i ON i.id = f.intake_dokument_id
                  WHERE f.dokument_id = dokumente.id
                  ORDER BY f.id ASC LIMIT 1),
                typ)
            WHERE dokumentenklasse IS NULL
        """)
    else:
        conn.execute("""
            UPDATE dokumente SET dokumentenklasse = COALESCE(
                dokumentenklasse,
                (SELECT i.klasse FROM freigaben f
                   JOIN intake_dokumente i ON i.id = f.intake_dokument_id
                  WHERE f.dokument_id = dokumente.id
                  ORDER BY f.id ASC LIMIT 1),
                'sonstiges')
            WHERE dokumentenklasse IS NULL
        """)

    conn.execute("UPDATE dokumente SET dokumentenklasse='sv_rechnung' "
                 "WHERE dokumentenklasse='gutachterrechnung'")
    conn.execute("UPDATE dokumente SET dokumentenklasse='sonstiges' "
                 "WHERE dokumentenklasse='versicherung'")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_dok_klasse "
                 "ON dokumente(dokumentenklasse)")
    conn.commit()

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (73, 'dokumentenklasse fuer Altbestand nachgefuellt')"
    )
    conn.commit()
    logger.info("Migration 73 abgeschlossen.")
```

- [ ] **Step 4: Test laufen lassen, grün bestätigen**

Run: `python -m pytest backend/tests/test_migration_73_74.py -v`
Expected: PASS (4 Tests)

- [ ] **Step 5: Migration auf der Entwicklungsdatenbank ausführen und nachsehen**

```bash
docker compose restart backend
docker exec unfallakten-backend-dev python -c "
import sqlite3
c=sqlite3.connect('/app/data/unfallakten.db'); c.row_factory=sqlite3.Row
print('version:', c.execute('SELECT MAX(version) FROM schema_version').fetchone()[0])
print('ohne Klasse:', c.execute('SELECT COUNT(*) FROM dokumente WHERE dokumentenklasse IS NULL').fetchone()[0])
for r in c.execute('SELECT dokumentenklasse k, COUNT(*) n FROM dokumente GROUP BY 1 ORDER BY n DESC'):
    print(' ', r['k'], r['n'])
"
```

Erwartet: Version 73, **0** Zeilen ohne Klasse, keine Werte `gutachterrechnung` oder `versicherung` mehr.

- [ ] **Step 6: Commit**

```bash
git add backend/db/schema_manager.py backend/tests/test_migration_73_74.py
git commit -m "feat(db): Migration 73 fuellt dokumentenklasse fuer den Altbestand nach"
```

---

## Task 5: Backend-Leser auf `dokumentenklasse` umstellen

**Files:**
- Modify: `backend/services/sta_service.py:93, 113, 121`
- Modify: `backend/services/abrechnung_vorschlag.py:121-122`
- Modify: `backend/routers/dokumente_routes.py:91, 96-97, 396`
- Modify: `backend/models/dokument.py:193-198`
- Modify: `backend/routers/akten_routes.py:163`
- Modify: `backend/pdf/upload_service.py:367`
- Test: `backend/tests/test_sta_service.py`, `backend/tests/test_abrechnung_vorschlag.py`

**Interfaces:**
- Consumes: gefüllte `dokumentenklasse` aus Task 4.
- Produces: `hole_dokumente_by_akte(akte_id: str, klasse: Optional[str] = None)`. Die API liefert in `_dok_dict` und `_dokument_dict` kein `typ` mehr.

- [ ] **Step 1: Bestehende Tests auf das neue Verhalten umschreiben**

In `backend/tests/test_sta_service.py` und `backend/tests/test_abrechnung_vorschlag.py` die `INSERT INTO dokumente`-Anweisungen so ergänzen, dass `dokumentenklasse` gesetzt wird (bisher setzen sie nur `typ`). Beispiel aus `test_abrechnung_vorschlag.py:110`:

```python
            "INSERT INTO dokumente "
            "(id, akte_id, typ, dokumentenklasse, dateiname, dateipfad) "
            "VALUES (?, ?, 'abrechnungsschreiben', 'abrechnungsschreiben', ?, ?)"
```

Zusätzlich in `test_sta_service.py` einen Test ergänzen, der beweist, dass die Zählung jetzt auf der Klasse fußt. Die Funktion in `backend/services/sta_service.py:80` heißt `analysiere_regulierung(az)` und liefert das Dict mit `sta_anzahl`:

```python
    def test_zaehlt_sachstandsanfragen_ueber_die_klasse(self):
        # dokumente.typ ist entfallen; massgeblich ist dokumentenklasse
        from backend.services.sta_service import analysiere_regulierung
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO dokumente (akte_id, dokumentenklasse, dateiname, "
                " dateipfad) VALUES (?, 'sachstandsanfrage', 's.docx', '/tmp/s')",
                (self.az,))
            conn.commit()
        ergebnis = analysiere_regulierung(self.az)
        self.assertGreaterEqual(ergebnis["sta_anzahl"], 1)
```

`self.az` durch das in der Datei verwendete Aktenzeichen ersetzen.

- [ ] **Step 2: Tests laufen lassen, Fehlschlag bestätigen**

Run: `python -m pytest backend/tests/test_sta_service.py backend/tests/test_abrechnung_vorschlag.py -v`
Expected: FAIL beim neuen sta-Test

- [ ] **Step 3: `sta_service.py` umstellen**

- Zeile 93: `SELECT t.dok_id, d.typ, d.hochgeladen_am` → `d.dokumentenklasse`
- Zeile 108-113 (Rückfall-Abfrage): `SELECT id AS dok_id, typ, hochgeladen_am` → `dokumentenklasse`, und `AND typ IN (...)` → `AND dokumentenklasse IN ('forderungsschreiben', 'sachstandsanfrage')`.
  Der Wert `'stellungnahme'` entfällt: er ist keine Registry-Klasse und war schon unter `typ` nie erreichbar (der CHECK-Constraint kannte ihn nicht). Siehe Spec 7.2.
- Zeile 121: `AND typ = 'sachstandsanfrage'` → `AND dokumentenklasse = 'sachstandsanfrage'`

Falls der Rückgabewert der Abfragen weiter unten unter dem Schlüssel `typ` gelesen wird, dort ebenfalls auf `dokumentenklasse` umstellen — die Datei nach `["typ"]` durchsuchen.

- [ ] **Step 4: `abrechnung_vorschlag.py` umstellen**

Zeile 121-122: die beiden Bedingungen zu einer zusammenziehen:

```python
            "  AND d.dokumentenklasse = 'abrechnungsschreiben' "
```

- [ ] **Step 5: `dokumente_routes.py` umstellen**

- Zeile 91 (Docstring): `typ   Filter nach Dokumenttyp` → `klasse  Filter nach Dokumentklasse`
- Zeile 96-97:

```python
    klasse = request.args.get("klasse")
    dokumente = hole_dokumente_by_akte(akte_id, klasse=klasse)
```

- Zeile 396: `if (row["typ"] or "").lower() == "gutachten":` → `row["dokumentenklasse"]`

- [ ] **Step 6: Model und API-Ausgabe umstellen**

`backend/models/dokument.py:193-198`:

```python
def hole_dokumente_by_akte(akte_id: int,
                            klasse: Optional[str] = None) -> list[Dokument]:
    sql = "SELECT * FROM dokumente WHERE akte_id = ?"
    params: list = [akte_id]
    if klasse:
        sql += " AND dokumentenklasse = ?"
        params.append(klasse)
```

`backend/routers/akten_routes.py:163`: `"typ": d.typ,` ersatzlos streichen — `dokumentenklasse` steht bereits in Zeile 169.

`backend/pdf/upload_service.py:367`: `"typ": dok.typ,` ersatzlos streichen — Zeile 368 liefert bereits `dokumentenklasse`.

- [ ] **Step 7: Tests laufen lassen**

Run: `python -m pytest backend/tests/ --tb=short -q`
Expected: PASS. Tests, die auf `dokument["typ"]` in der API-Antwort prüfen, sind auf `dokumentenklasse` umzustellen.

- [ ] **Step 8: Commit**

```bash
git add -u backend/
git commit -m "refactor(dokumente): Backend-Leser fussen auf dokumentenklasse statt typ"
```

---

## Task 6: Frontend-Leser umstellen

**Files:**
- Modify: `frontend/src/config/utils.js:65`
- Modify: `frontend/src/sections/DokumenteSection.jsx:798, 1386`
- Modify: `frontend/src/sections/SchadenSection.jsx:265`
- Modify: `frontend/src/sections/RegulierungSection.jsx:303, 304, 306, 307, 1988, 1992`
- Test: `frontend/src/config/utils.dokumentAnzeige.test.js`

**Interfaces:**
- Consumes: die API liefert seit Task 5 kein `typ` mehr.
- Produces: keine Frontend-Stelle liest noch `d.typ` für Dokumente.

- [ ] **Step 1: Bestehenden Test anpassen**

`frontend/src/config/utils.dokumentAnzeige.test.js` durchsehen: Fälle, die ein Dokument nur mit `typ` konstruieren, auf `dokumentenklasse` umstellen. Einen Fall ergänzen, der beweist, dass `typ` nicht mehr ausgewertet wird.

Die Funktion heißt `dokumentAnzeige(dok)` (`frontend/src/config/utils.js:58`). Wichtig: Sie liefert zuerst `bezeichnung`, dann `dateiname` — ein Testobjekt mit Dateinamen würde die Klassenlogik nie erreichen. Daher **ohne** `dateiname` prüfen:

```js
it("wertet ein veraltetes typ-Feld nicht mehr aus", () => {
  expect(dokumentAnzeige({ typ: "gutachten", id: 5 })).toBe("Dokument Nr. 5");
});

it("nutzt weiterhin die dokumentenklasse", () => {
  expect(dokumentAnzeige({ dokumentenklasse: "gutachten", id: 5 }))
    .toBe("Gutachten (Nr. 5)");
});
```

- [ ] **Step 2: Test laufen lassen, Fehlschlag bestätigen**

Run: `cd frontend && npx vitest run src/config/utils.dokumentAnzeige.test.js`
Expected: FAIL

- [ ] **Step 3: Die neun Lesestellen umstellen**

| Datei:Zeile | vorher | nachher |
|---|---|---|
| `config/utils.js:65` | `dok.dokumentenklasse \|\| dok.typ \|\| ""` | `dok.dokumentenklasse \|\| ""` |
| `DokumenteSection.jsx:798` | `d.dokumentenklasse\|\|d.typ\|\|"sonstiges"` | `d.dokumentenklasse \|\| "sonstiges"` |
| `SchadenSection.jsx:265` | `(d.dokumentenklasse === "gutachten" \|\| d.typ === "gutachten")` | `d.dokumentenklasse === "gutachten"` |
| `RegulierungSection.jsx:303` | `d.dokumentenklasse === "abrechnungsschreiben" \|\| d.typ === "abrechnungsschreiben"` | `d.dokumentenklasse === "abrechnungsschreiben"` |
| `RegulierungSection.jsx:304` | analog `pruefbericht` | `d.dokumentenklasse === "pruefbericht"` |
| `RegulierungSection.jsx:306, 307` | die beiden negierten Bedingungen | analog verkürzen |
| `RegulierungSection.jsx:1988, 1992` | analog | analog verkürzen |

- [ ] **Step 4: Totes Upload-Dropdown entfernen**

`frontend/src/sections/DokumenteSection.jsx:1386` — die Zeile

```jsx
            <FieldSelect label="Dokumenttyp" value={uploadTyp} onChange={setTyp} options={DOK_TYPEN} />
```

ersatzlos löschen. Unter `INTAKE_REVIEW_PFLICHT` verwirft `dokumente_routes.py:143-175` den Wert ohnehin; die Klasse wird in der Review-Queue vergeben. Dazu:
- `const [uploadTyp, setTyp] = useState("gutachten");` (Zeile 23) löschen
- Zeile 685 `typ: uploadTyp,` aus dem optimistischen Eintrag entfernen
- Zeile 693 `apiDokumente.hochladen(akteId, f, uploadTyp, …)` → prüfen, ob der dritte Parameter in `api.js` noch gebraucht wird; falls nicht, dort und hier entfernen, sonst `"sonstiges"` übergeben.

`DOK_TYPEN` bleibt importiert — es wird für das Klassen-Dropdown in Zeile 802 weiter gebraucht.

- [ ] **Step 5: Frontend-Tests laufen lassen**

Run: `cd frontend && npm test`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -u frontend/
git commit -m "refactor(frontend): Dokumentanzeige fusst allein auf dokumentenklasse"
```

---

## Task 7: Portal-Sync auf Klasse und Label umstellen

**Files:**
- Modify: `backend/services/portal_sync.py:136-139, 163-166`
- Test: `backend/tests/test_portal_sync_payload.py` (existiert)

**Interfaces:**
- Consumes: gefüllte `dokumentenklasse`.
- Produces: Sync-Payload `"dokumente": [{"id", "klasse", "klasse_label", "dateiname", "erstellt_am"}]`. Das Feld `typ` entfällt. Der Vertrag ist in Spec Abschnitt 6 dokumentiert; das Portal-Repo zieht separat nach.

- [ ] **Step 1: Test schreiben**

`backend/tests/test_portal_sync_payload.py` verwendet eine pytest-Fixture `conn` mit einer eigenen In-Memory-Tabelle `dokumente` (Zeile 41-45). Diese Tabellendefinition muss zuerst angepasst werden — heute steht dort `typ TEXT`:

```python
        CREATE TABLE dokumente (
            id INTEGER PRIMARY KEY, akte_id TEXT, dokumentenklasse TEXT,
            dateiname TEXT, hochgeladen_am TEXT, portal_sichtbar INTEGER DEFAULT 0
        );
```

Bestehende `INSERT`s in dieser Datei entsprechend von `typ` auf `dokumentenklasse` umstellen. Dann den neuen Test anhängen — die Payload-Funktion heißt `_build_payload(conn, akte_id)` (`portal_sync.py:94`):

```python
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
```

Die übrigen Pflichtspalten der Fixture (`beteiligte`, `schadenpositionen` …) sind bereits angelegt; falls `_build_payload` ohne weitere Zeilen scheitert, das Muster eines bestehenden Tests derselben Datei übernehmen.

- [ ] **Step 2: Test laufen lassen, Fehlschlag bestätigen**

Run: `python -m pytest backend/tests/test_portal_sync.py -v`
Expected: FAIL — `KeyError: 'klasse'`

- [ ] **Step 3: Payload umstellen**

`backend/services/portal_sync.py`, Abfrage Zeile 136-139:

```python
    docs = conn.execute("""
        SELECT id, dokumentenklasse, dateiname, hochgeladen_am
        FROM dokumente WHERE akte_id = ? AND portal_sichtbar = 1
    """, (akte_id,)).fetchall()
```

Und der Ausgabeblock Zeile 163-166:

```python
        "dokumente": [
            {"id": d["id"], "klasse": d["dokumentenklasse"],
             "klasse_label": _klasse_label(d["dokumentenklasse"]),
             "dateiname": d["dateiname"], "erstellt_am": d["hochgeladen_am"]}
            for d in docs
        ],
```

Dazu ein Helfer oben in der Datei:

```python
def _klasse_label(klasse):
    # type: (str) -> str
    """Anzeigetext der Klasse aus der Registry. Das Portal zeigt den Wert
    Mandanten und Sachverstaendigen im Klartext -- der technische Schluessel
    waere dort unverstaendlich."""
    if not klasse:
        return "Sonstiges"
    try:
        from ..intake.registry_loader import lade_registry, standard_pfad
        eintrag = lade_registry(standard_pfad()).klassen.get(klasse) or {}
        return eintrag.get("label") or klasse
    except Exception:
        return klasse
```

- [ ] **Step 4: Test laufen lassen, grün bestätigen**

Run: `python -m pytest backend/tests/test_portal_sync.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -u backend/
git commit -m "feat(portal): Sync-Payload liefert klasse und klasse_label statt typ

Vertragsaenderung fuer das Stakeholder-Portal, dokumentiert in
docs/superpowers/specs/2026-09-02-dokumentenklasse-ssot-design.md
Abschnitt 6. Das Portal ist nicht live und wird separat nachgezogen."
```

---

## Task 8: Migration 74 — die Spalte fällt

Der destruktive Schritt, bewusst zuletzt. Ab hier ist der Rückweg nur über ein Backup.

**Files:**
- Modify: `backend/db/schema_manager.py` (MIGRATIONS-Dict, Dispatch-Kette, neue Funktion)
- Modify: `backend/db/schema.py:213-216, 235`
- Modify: `backend/models/dokument.py` (`typ` aus Dataclass und INSERT, `_ALT_TYP_WERTE`)
- Modify: `docs/DATAMODEL.md:168`
- Test: `backend/tests/test_migration_73_74.py`
- Test: `backend/tests/test_dokumente_typ_guard.py` (neu)

**Interfaces:**
- Consumes: alles aus Task 2 bis 7.
- Produces: Spalte `dokumente.typ` existiert nicht mehr; `schema_version` = 74.

- [ ] **Step 1: Sicherung der Entwicklungsdatenbank anlegen**

```bash
docker exec unfallakten-backend-dev python -c "
import sqlite3
src=sqlite3.connect('/app/data/unfallakten.db')
dst=sqlite3.connect('/app/data/bak_vor_migration_74.db')
src.backup(dst); dst.close(); src.close()
print('Sicherung angelegt')
"
```

`.backup` statt Dateikopie — bei aktivem WAL wäre eine Kopie inkonsistent.

- [ ] **Step 2: Migrationstest ergänzen**

An `backend/tests/test_migration_73_74.py` anhängen:

```python
class TestMigration74SpalteFaellt(unittest.TestCase):
    # setUp/tearDown wortgleich aus TestMigration73Nachfuellen

    def test_typ_ist_weg_und_daten_bleiben(self):
        from backend.db.database import get_connection
        from backend.db.schema_manager import _run_migration_74
        with get_connection() as conn:
            vorher = conn.execute("SELECT COUNT(*) FROM dokumente").fetchone()[0]
            _run_migration_74(conn)
            spalten = {r[1] for r in conn.execute(
                "PRAGMA table_info(dokumente)").fetchall()}
            nachher = conn.execute("SELECT COUNT(*) FROM dokumente").fetchone()[0]
            indizes = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND tbl_name='dokumente'")]
        self.assertNotIn("typ", spalten)
        self.assertIn("dokumentenklasse", spalten)
        self.assertEqual(vorher, nachher)
        self.assertNotIn("idx_dokumente_typ", indizes)

    def test_zweiter_aufruf_ist_folgenlos(self):
        from backend.db.database import get_connection
        from backend.db.schema_manager import _run_migration_74
        with get_connection() as conn:
            _run_migration_74(conn)
            _run_migration_74(conn)
            spalten = {r[1] for r in conn.execute(
                "PRAGMA table_info(dokumente)").fetchall()}
        self.assertNotIn("typ", spalten)

    def test_fremdschluessel_bleiben_heil(self):
        from backend.db.database import get_connection
        from backend.db.schema_manager import _run_migration_74
        with get_connection() as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            _run_migration_74(conn)
            verletzungen = conn.execute("PRAGMA foreign_key_check").fetchall()
        self.assertEqual(verletzungen, [])
```

- [ ] **Step 3: Test laufen lassen, Fehlschlag bestätigen**

Run: `python -m pytest backend/tests/test_migration_73_74.py -v`
Expected: FAIL — `ImportError: cannot import name '_run_migration_74'`

- [ ] **Step 4: Migration 74 schreiben — in EINEM Edit**

> Wieder: Dict-Eintrag, Dispatch-Zweig und Funktion in **einem** Schreibvorgang.

**a)** MIGRATIONS-Dict:

```python
    74: "-- migration_74_dokumente_typ_entfernen",  # Handled by _run_migration_74
```

**b)** Dispatch-Kette, nach `elif version == 73:`:

```python
            elif version == 74:
                _run_migration_74(conn)
```

**c)** Neue Funktion nach `_run_migration_73`:

```python
def _run_migration_74(conn: sqlite3.Connection) -> None:
    """
    Migration 74: dokumente.typ ersatzlos entfernen.

    Die Spalte fuehrte dieselbe Tatsache wie dokumentenklasse, aber nur in
    sechs Grobwerten -- 17 der 23 Registry-Klassen fielen darin auf
    'sonstiges'. Massgeblich ist ab jetzt allein dokumentenklasse.

    Der Index muss vor DROP COLUMN weg, sonst bricht SQLite ab mit
    "error in index idx_dokumente_typ after drop column: no such column: typ".
    Ein Tabellen-Rebuild ist nicht noetig (an SQLite 3.46.1 erprobt); der
    CHECK-Constraint verschwindet mit der Spalte.
    """
    conn.commit()
    spalten = {r[1] for r in conn.execute(
        "PRAGMA table_info(dokumente)").fetchall()}
    if "typ" in spalten:
        conn.execute("DROP INDEX IF EXISTS idx_dokumente_typ")
        conn.execute("ALTER TABLE dokumente DROP COLUMN typ")
        conn.commit()
        logger.info("Migration 74: dokumente.typ entfernt.")

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (74, 'dokumente.typ entfernt -- dokumentenklasse ist SSOT')"
    )
    conn.commit()
    logger.info("Migration 74 abgeschlossen.")
```

- [ ] **Step 5: Test laufen lassen, grün bestätigen**

Run: `python -m pytest backend/tests/test_migration_73_74.py -v`
Expected: PASS (7 Tests)

- [ ] **Step 6: Schema und Model bereinigen**

`backend/db/schema.py`:
- Zeile 213-216 (`typ TEXT NOT NULL CHECK(...)`) ersatzlos löschen
- Zeile 235 (`CREATE INDEX ... idx_dokumente_typ`) ersetzen durch:
  ```sql
  CREATE INDEX IF NOT EXISTS idx_dok_klasse ON dokumente(dokumentenklasse);
  ```

`backend/models/dokument.py`:
- `typ: str` aus der `Dokument`-Dataclass entfernen
- `_ALT_TYP_WERTE` löschen
- Im `INSERT` von `registriere_dokument` Spalte und Platzhalter für `typ` entfernen, ebenso die Ableitungszeile
- Im zurückgegebenen `Dokument(...)` das Feld `typ=typ` entfernen

- [ ] **Step 7: Statischen Guard-Test schreiben**

Neue Datei `backend/tests/test_dokumente_typ_guard.py`:

```python
"""
Guard: dokumente.typ ist entfallen (Migration 74) und darf nicht
zurueckkehren. Fachlich massgeblich ist allein dokumentenklasse.

Vorbild: test_gen_dokumentenklassen_guard.py.
"""
import os
import re

PROJEKT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Gleichnamige, aber voellig andere Felder -- diese Treffer sind erlaubt.
ERLAUBTE_NACHBARN = (
    "dateityp", "ereignistyp", "payload_typ", "rechnungstyp", "kuerzungstyp",
    "fahrzeug_typ", "frist_typ", "schluss_typ", "kfz_typ", "email_typ",
    "aktion_typ", "typ_code", "typ_quelle", "aktivlegitimation_typ",
)

VERBOTEN = (
    re.compile(r"\bd\.typ\b"),
    re.compile(r"\bdokumente\.typ\b"),
    re.compile(r"registriere_dokument\([^)]*\btyp\s*="),
    re.compile(r"GUELTIGE_TYPEN"),
)

DURCHSUCHEN = ("backend", "frontend/src", "tools")
UEBERSPRINGEN = ("node_modules", "dist", "__pycache__", ".git",
                 "test_dokumente_typ_guard.py")


def _quelldateien():
    for wurzel in DURCHSUCHEN:
        for pfad, ordner, dateien in os.walk(os.path.join(PROJEKT, wurzel)):
            ordner[:] = [o for o in ordner if o not in UEBERSPRINGEN]
            for d in dateien:
                if d in UEBERSPRINGEN:
                    continue
                if d.endswith((".py", ".js", ".jsx", ".sql")):
                    yield os.path.join(pfad, d)


def test_keine_dokumente_typ_zugriffe_mehr():
    treffer = []
    for datei in _quelldateien():
        with open(datei, "r", encoding="utf-8", errors="replace") as f:
            for nr, zeile in enumerate(f, 1):
                if any(n in zeile for n in ERLAUBTE_NACHBARN):
                    continue
                for muster in VERBOTEN:
                    if muster.search(zeile):
                        treffer.append(
                            "%s:%d: %s" % (os.path.relpath(datei, PROJEKT),
                                           nr, zeile.strip()))
    assert not treffer, (
        "dokumente.typ ist mit Migration 74 entfallen. Massgeblich ist "
        "dokumentenklasse. Gefunden:\n" + "\n".join(treffer))
```

- [ ] **Step 8: Guard laufen lassen und alle Treffer beseitigen**

Run: `python -m pytest backend/tests/test_dokumente_typ_guard.py -v`
Expected: zunächst FAIL mit einer Trefferliste. Jeden Treffer nach den Vorgaben aus Task 5/6 abarbeiten. Tests, die `INSERT INTO dokumente (… typ …)` schreiben, auf `dokumentenklasse` umstellen — betroffen sind laut Erhebung `test_abrechnungsrunden.py`, `test_belege_bezeichnung.py`, `test_fristablauf_service.py`, `test_gutachten_fahrzeugschaden_alternative.py`, `test_klage_kw28_verzugdok_datum.py`, `test_kuerzungstyp_matching.py`, `test_migration_46.py`, `test_p15a_regulierung.py`, `test_p15b_beleg.py`, `test_p15c_gutachten.py`, `test_p15e_freigabe_ereignisse.py`, `test_positionsstatus_ssot.py` und `test_abrechnung_vorschlag.py`.

Ausnahme: In `test_migration_73_74.py` sind `typ`-Spalten in den `INSERT`s **beabsichtigt** — sie bilden den Altbestand nach. Diese Datei gehört in `UEBERSPRINGEN`.

- [ ] **Step 9: Datenmodell-Dokumentation nachziehen**

`docs/DATAMODEL.md:168`: Die Zeile zu `typ` löschen. In der Zeile zu `dokumentenklasse` ergänzen: `· ab Migration 74 alleinige Klassenquelle, Wertebereich = backend/registry/klassen/*.yaml (kein CHECK, damit neue Klassen ohne Migration auskommen)`.

- [ ] **Step 10: Migration auf der Entwicklungsdatenbank fahren und prüfen**

```bash
docker compose restart backend
docker exec unfallakten-backend-dev python -c "
import sqlite3
c=sqlite3.connect('/app/data/unfallakten.db'); c.row_factory=sqlite3.Row
print('version:', c.execute('SELECT MAX(version) FROM schema_version').fetchone()[0])
print('spalten:', [r[1] for r in c.execute('PRAGMA table_info(dokumente)')])
print('indizes:', [r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='dokumente'\")])
print('zeilen:', c.execute('SELECT COUNT(*) FROM dokumente').fetchone()[0])
print('fk-verletzungen:', len(c.execute('PRAGMA foreign_key_check').fetchall()))
"
```

Erwartet: Version 74 · kein `typ` mehr · `idx_dok_klasse` vorhanden, `idx_dokumente_typ` weg · 793 Zeilen unverändert · **genau 2** FK-Verletzungen.

> Die zwei FK-Verletzungen (`klassifikation_training` → `dokumente`, `aktivitaeten` → `unfallakte`) bestehen bereits vor der Migration und sind nicht deren Folge (Spec 4.3). **Null** wäre hier verdächtig, nicht beruhigend — dann stimmt die Prüfung nicht.

- [ ] **Step 11: Vollsuite**

Run: `python -m pytest backend/tests/ --tb=short -q` und `cd frontend && npm test`
Expected: PASS. Referenzwert Backend: 2207 bestanden, 69 übersprungen (Stand vor dem Umbau, zuzüglich der hier neu geschriebenen Tests).

- [ ] **Step 12: Commit**

```bash
git add -A backend/ frontend/ docs/
git commit -m "feat(db)!: Migration 74 entfernt dokumente.typ

dokumentenklasse ist alleinige Klassenquelle. Die Spalte typ fuehrte
dieselbe Tatsache in nur sechs Grobwerten; 17 der 23 Registry-Klassen
fielen darin auf 'sonstiges'.

BREAKING: Der Portal-Sync-Payload liefert klasse/klasse_label statt typ.
Anzupassende Stellen im Portal-Repo: Spec Abschnitt 6.3."
```

---

## Task 9: Abnahme im Betrieb

**Files:** keine — reine Sichtprüfung.

**Interfaces:**
- Consumes: alles.
- Produces: nichts.

- [ ] **Step 1: Freigabe durchspielen**

Ein Dokument in der Review-Queue öffnen, Klasse auf `sv_rechnung` setzen, an eine Akte freigeben. In der DokumenteSection der Akte prüfen: steht dort **SV-/Gutachterrechnung**, nicht „Sonstiges"?

- [ ] **Step 2: Klassenliste vergleichen**

Dropdown in der Review-Queue und Dropdown in der DokumenteSection nebeneinander: dieselben 23 Einträge, dieselben Bezeichnungen.

- [ ] **Step 3: Belege-Ansicht gegenprüfen**

An einer bekannten Akte mit freigegebenen Rechnungen die Belege-Ansicht öffnen. Dort erscheinen jetzt Kandidaten und Beträge, die vorher unsichtbar waren — das ist beabsichtigt (Spec 8), verändert aber sichtbar das Bild. Zusammen mit RA Schatz an einer Akte anschauen und bestätigen, dass die Beträge stimmen.

- [ ] **Step 4: Ergebnis festhalten**

`docs/CHANGELOG.md` um einen Eintrag ergänzen; offene Punkte in `docs/TODO.md`. Der Portal-Umbau bleibt offen und gehört als eigener Punkt in `docs/TODO.md` mit Verweis auf Spec Abschnitt 6.

---

## Offen gelassen

Bewusst nicht Teil dieses Plans (Spec Abschnitt 7):

- **Nachklassifikation im E-Mail-Import** — `import_service.py:786` riet die Klasse aus dem Dateinamen. Die Heuristik entfällt ersatzlos; alle vier Import-Pfade legen jetzt `sonstiges` an. Eine echte Klassifikation dieses Pfades ist eine eigene Aufgabe.
- **Klasse `stellungnahme`** — `stellungnahme_routes.py` legt ein Dokument ohne passende Registry-Klasse ab; `sta_service` fragte einen `typ`-Wert `'stellungnahme'` ab, den der CHECK-Constraint nie zuliess. Vermerkt in `POSITIONSMODELL-PLAN.md:159-160`.
- **Zwei bestehende FK-Verletzungen** in der Entwicklungsdatenbank.
