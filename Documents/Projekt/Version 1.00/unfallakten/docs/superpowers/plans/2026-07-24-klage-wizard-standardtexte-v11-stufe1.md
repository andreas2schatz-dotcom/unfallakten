# V11 Standardtexte Klageschrift — Stufe 1 — Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die grammatikneutralen Standardtexte der Klageschrift (Spec-Kategorien A+B, 44 Bausteine) werden über eine YAML-Registry + DB-Override-Tabelle pflegbar; neue Einstellungen-Karte „Standardtexte Klageschrift" mit `TextbausteinEditor`; Nebenbefund-Fix („Die Beklagte" hartcodiert) inklusive.

**Architektur:** Standardtexte bleiben im Programm (`backend/registry/klage_standardtexte.yaml`, fail-loud beim App-Start wie `rausch_absender.yaml`); die DB speichert nur Abweichungen (`standardtext_override`, Migration 65). `_baue_klage_dokument` und `sg_text_builder` beziehen jeden Stufe-1-Baustein über `hole_texte_aufgeloest()` (Override vor Standard) und füllen Wert-Platzhalter per bestehendem `ersetze_platzhalter`. Das Frontend holt aufgelöste Texte über `GET /klage-standardtexte/aufgeloest` (kein dupliziertes Verzeichnis) und füllt Werte mit dem wortgleichen `ersetzePlatzhalter` aus `platzhalterLogik.js`. Golden-Snapshot-Tests pinnen Byte-Parität vor/nach dem Umbau.

**Tech Stack:** Flask + SQLite (Backend), PyYAML, React/Vite/Vitest (Frontend), unittest/pytest.

**Scope-Schnitt:** Dieser Plan ist **Stufe 1** des freigegebenen Stufenmodells (Spec 2026-07-19). **Stufe 2** (Kategorie C: Anträge, Sachverhalt-Kernsätze, Aktivlegitimation, Einwände-Rahmensätze, SG-Kernsatz — vorflektierte Platzhalter) bekommt nach Abnahme von Stufe 1 einen eigenen Plan auf derselben Infrastruktur.

## Global Constraints

- **RA-MICRO strikt read-only** — Schreibziel ist ausschließlich SQLite.
- **Git-Wurzel = Home-Verzeichnis** — NIE `git add -A`; Dateien immer einzeln adden.
- **Platzhalter-Syntax:** `<GROSSBUCHSTABEN_MIT_UNTERSTRICH>` (Handover-Vorgabe; ersetzt die `{{…}}`-Beispiele der Spec). Regex überall: `<([A-Z_]+)>`.
- **BE↔FE wortgleich:** `ersetze_platzhalter` (backend/word/stellungnahme_service.py:67) ↔ `ersetzePlatzhalter` (frontend/src/sections/platzhalterLogik.js) werden **unverändert wiederverwendet**, nicht kopiert, nicht geändert.
- **Golden-Parität:** Ohne Overrides muss der umgebaute Service byte-identische Vorschau-Texte liefern. Einzige gewollte Abweichung: der Nebenbefund-Fix (Task 2/3), dokumentiert per Golden-Neuaufnahme.
- **Test-Baseline lokal (Windows):** Backend 204 bekannte Alt-Failures / 1241 passed (ModuleNotFound-Cluster, Vergleichsbasis docs/CHANGELOG.md) · Vitest 362/362 grün. `KlageWizard.einwaende*`-Tests müssen grün bleiben.
- **Migrationen:** Dev-Container **vorher stoppen** (`docker stop unfallakten-backend-dev`), Migration atomar, kein `executescript()`, explizite `conn.commit()` um DDL (Reloader-Falle, docs/STATE.md).
- **Keine Code-Kommentare** außer bei nicht-offensichtlichem Verhalten; alle UI-/Dokumenttexte Deutsch.
- **Branch:** `standardtexte-v11`, neu von `main`.
- Frontend-Quelle ist **`frontend/src/`** — die Root-Kopien `frontend/KlageWizard.jsx` / `frontend/api.js` sind tote Duplikate, niemals anfassen.
- Testkommandos (Repo-Wurzel `unfallakten/`): Backend `python -m pytest backend/tests/<datei>.py -v` · Frontend `cd frontend` dann `npx vitest run <datei>`.

---

## Dateistruktur

| Datei | Rolle |
|---|---|
| `backend/registry/klage_standardtexte.yaml` | **Neu:** Baustein-Verzeichnis (Platzhalter-Katalog + 44 Bausteine) |
| `backend/services/standardtext_registry.py` | **Neu:** Fail-loud-Loader + `hole_texte_aufgeloest()` (Override vor Standard) |
| `backend/models/standardtext_override.py` | **Neu:** CRUD auf `standardtext_override` |
| `backend/db/schema_manager.py` | Migration 65 (`standardtext_override`) |
| `backend/routers/standardtexte_routes.py` | **Neu:** REST `/klage-standardtexte` (Liste, PUT, DELETE, Vorschau, aufgelöst) |
| `backend/app.py` | Registry-Wiring (fail-loud) + Blueprint-Registrierung |
| `backend/word/klage_service.py` | Nebenbefund-Fix; Stufe-1-Literale → `_st(key, kontext)` |
| `backend/word/sg_text_builder.py` | SG-B-Texte aus Registry (Parameter `texte`) |
| `backend/tests/test_klage_standardtexte_golden.py` | **Neu:** Golden-Paritäts-Matrix |
| `backend/tests/test_standardtext_registry.py` | **Neu:** Loader fail-loud + Inventar-Vollständigkeit |
| `backend/tests/test_standardtexte_rest.py` | **Neu:** REST-Roundtrip + Override-Wirkung im Dokument |
| `backend/tests/test_migration_65.py` | **Neu:** Migrations-Guard |
| `frontend/src/api.js` | `apiStandardtexte` |
| `frontend/vite.config.js` | Proxy-Eintrag `/klage-standardtexte` |
| `frontend/src/views/StandardtexteTab.jsx` (+ `.test.jsx`) | **Neu:** Einstellungen-Karte |
| `frontend/src/views/EinstellungenView.jsx` | Tab „standardtexte" |
| `frontend/src/sections/KlageWizard.jsx` | Nebenbefund-FE-Fix; Generatoren beziehen Texte aus `/aufgeloest` |
| `frontend/src/test/standardtexteFixture.js` | **Neu:** Text-Fixture für Vitest |

---

### Task 1: Feature-Branch + Golden-Snapshot-Fundament

Pinnt den Ist-Zustand der Auto-Texte, bevor irgendetwas umgebaut wird. Jede spätere Aufgabe muss diesen Test grün halten (bzw. bei Task 2 die Goldens bewusst neu aufnehmen).

**Files:**
- Create: `backend/tests/test_klage_standardtexte_golden.py`
- Create: `backend/tests/golden/klage_standardtexte/*.txt` (generiert)

**Interfaces:**
- Consumes: `baue_klage_vorschau(akte_daten) -> {"abschnitte": [...]}` (backend/word/klage_service.py:1860); Fixture-Helfer `_akte_daten`, `_position` aus `backend/tests/test_klage_service_docx.py` (Modulebene).
- Produces: Golden-Dateien + Test `TestKlageGolden::test_golden_paritaet`, Update-Mechanismus über Env `KLAGE_GOLDEN_UPDATE=1`.

- [ ] **Step 1: Branch anlegen**

```bash
git checkout main
git checkout -b standardtexte-v11
```

- [ ] **Step 2: Golden-Test schreiben**

`backend/tests/test_klage_standardtexte_golden.py`:

```python
"""
V11 Golden-Paritaet (Stufe 1): pinnt die Klage-Vorschautexte vor dem
Registry-Umbau. Der Umbau ohne Overrides muss byte-identische Texte liefern.
Bewusste Neuaufnahme (nur nach dokumentierter Textaenderung):
  KLAGE_GOLDEN_UPDATE=1 python -m pytest backend/tests/test_klage_standardtexte_golden.py
Abschnitt "datum" wird ausgeklammert (enthaelt das Tagesdatum).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))

from backend.word.klage_service import baue_klage_vorschau
from backend.tests.test_klage_service_docx import _akte_daten, _position

GOLDEN_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "golden", "klage_standardtexte")

VERS = {"rolle_klage": "beklagter", "versicherung": "Test-Versicherung AG",
        "anschrift": "Teststr. 2", "plz": "12345", "ort": "Teststadt"}
MANN = {"rolle_klage": "beklagter", "vorname": "Hans", "name": "Huber",
        "anrede": "1", "anschrift": "Weg 3", "plz": "63065", "ort": "Offenbach"}


def _basis_cfg(mit_sg=False, n_bek=1, akt_typ="eigentum"):
    pos = [_position("fahrzeugschaden", "Fahrzeugschaden", 3000.0)]
    akte = _akte_daten(pos, mit_schmerzensgeld=mit_sg,
                       schmerzensgeld_mindest=2000.0 if mit_sg else 0.0)
    akte["unfalldetails"]["aktivlegitimation_typ"] = akt_typ
    akte["klage_config"]["beklagte"] = [VERS] if n_bek == 1 else [VERS, MANN]
    akte["klage_config"]["verzugsdatum"] = "2026-05-04"
    return akte


def _szenarien():
    sz = {}
    for mit_sg in (False, True):
        for n_bek in (1, 2):
            for akt_typ in ("eigentum", "finanziert", "geleast"):
                sz["matrix_sg%d_bek%d_%s" % (int(mit_sg), n_bek, akt_typ)] = \
                    _basis_cfg(mit_sg, n_bek, akt_typ)
    fallb = _basis_cfg(n_bek=2)
    fallb["klage_config"]["haftungsquote"] = 70
    fallb["klage_config"]["haftungsquote_typ"] = "eigen"
    sz["fallb_eigene_quote"] = fallb
    gegnerisch = _basis_cfg(n_bek=2)
    gegnerisch["klage_config"]["haftungsquote"] = 70
    gegnerisch["klage_config"]["haftungsquote_typ"] = "gegnerisch"
    sz["quote_gegnerisch_bestritten"] = gegnerisch
    mann_solo = _basis_cfg()
    mann_solo["klage_config"]["beklagte"] = [MANN]
    sz["beklagter_maennlich"] = mann_solo
    teilreg = _basis_cfg()
    teilreg["abrechnungen"] = [{"gesamt_reguliert": 500.0}]
    sz["teilregulierung"] = teilreg
    return sz


def _snapshot(akte_daten):
    res = baue_klage_vorschau(akte_daten)
    teile = []
    for a in res["abschnitte"]:
        if a["key"] == "datum":
            continue
        teile.append("== %s ==\n%s" % (a["key"], a["text"]))
    return "\n\n".join(teile) + "\n"


class TestKlageGolden(unittest.TestCase):

    def test_golden_paritaet(self):
        os.makedirs(GOLDEN_DIR, exist_ok=True)
        update = os.environ.get("KLAGE_GOLDEN_UPDATE") == "1"
        for name, akte in _szenarien().items():
            with self.subTest(szenario=name):
                ist = _snapshot(akte)
                pfad = os.path.join(GOLDEN_DIR, name + ".txt")
                if update or not os.path.exists(pfad):
                    with open(pfad, "w", encoding="utf-8", newline="\n") as f:
                        f.write(ist)
                with open(pfad, "r", encoding="utf-8", newline="\n") as f:
                    soll = f.read()
                self.assertEqual(soll, ist)

    def test_szenarien_treffen_die_zielpfade(self):
        snaps = {n: _snapshot(a) for n, a in _szenarien().items()}
        self.assertIn("Mithaftungsquote", snaps["fallb_eigene_quote"])
        self.assertIn("Teilregulierung", snaps["teilregulierung"])
        self.assertIn("Dies wird bestritten", snaps["quote_gegnerisch_bestritten"])
        self.assertIn("keine Regulierung", snaps["matrix_sg0_bek1_eigentum"])
```

- [ ] **Step 3: Ersten Lauf ausführen (schreibt die Goldens) und Selbstprüfung**

```bash
python -m pytest backend/tests/test_klage_standardtexte_golden.py -v
```

Erwartet: PASS (2 Tests; erster Lauf legt 16 `.txt`-Dateien in `backend/tests/golden/klage_standardtexte/` an). Falls `test_szenarien_treffen_die_zielpfade` FAILt: `_baue_klage_dokument` liest `cfg["haftungsquote"]` (klage_service.py:981), `cfg["haftungsquote_typ"]` (:988), `akte_daten["abrechnungen"]` (:878) — Szenario-Verdrahtung dagegen korrigieren, bevor weitergemacht wird. Falls der Abschnitts-Key für das Tagesdatum nicht `"datum"` heißt: `print([a["key"] for a in res["abschnitte"]])` einmalig einfügen, echten Key in `_snapshot` ausklammern, wieder entfernen.

- [ ] **Step 4: Zweiten Lauf ausführen (vergleicht gegen die Goldens)**

```bash
python -m pytest backend/tests/test_klage_standardtexte_golden.py -v
```

Erwartet: PASS (deterministisch, byte-identisch).

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_klage_standardtexte_golden.py
git add backend/tests/golden/klage_standardtexte
git commit -m "test(standardtexte): Golden-Paritaets-Matrix vor V11-Umbau (16 Szenarien)"
```

---

### Task 2: Nebenbefund-Fix Backend — „Die Beklagte" über Grammatik-Helfer

Spec-Nebenbefund: Zahlungs-Vorspann (klage_service.py:1573 + :1608), Teilregulierung (:1647) und Keine-Regulierung (:1653) hartcodieren „Die Beklagte" (Sg. fem.). Fix: `_beklagten_grammatik` um `nom_gross` + `hat` erweitern und in den vier Sätzen nutzen. **Gewollte Textänderung** bei mehreren/männlichen Beklagten → Goldens werden danach bewusst neu aufgenommen.

**Files:**
- Modify: `backend/word/klage_service.py:605-628` (`_beklagten_grammatik`), `:1573`, `:1608`, `:1647-1651`, `:1653-1655`
- Test: `backend/tests/test_klage_partei_grammatik.py` (Klasse `TestBeklagtenGrammatik`)
- Regeneriert: `backend/tests/golden/klage_standardtexte/*.txt`

**Interfaces:**
- Produces: `_beklagten_grammatik(beklagte_gef) -> dict` mit **zusätzlichen** Keys `"nom_gross"` (str) und `"hat"` (str); bestehende Keys (`verurteilt`, `verpflichtet`, `kosten`, `nom_klein`, `haftet`) unverändert. Task 6 nutzt `nom_gross`/`hat` als Kontextwerte für `<BEK_NOM>`/`<BEK_HAT>`.

- [ ] **Step 1: Failing Tests schreiben** — in `backend/tests/test_klage_partei_grammatik.py`, Klasse `TestBeklagtenGrammatik`, ergänzen (Import-Stil der Datei übernehmen; `_beklagten_grammatik` ist dort bereits importiert):

```python
    def test_nom_gross_und_hat_mehrere(self):
        g = _beklagten_grammatik([{"versicherung": "X AG"}, {"anrede": "1"}])
        self.assertEqual(g["nom_gross"], "Die Beklagten")
        self.assertEqual(g["hat"], "haben")

    def test_nom_gross_und_hat_maennlich(self):
        g = _beklagten_grammatik([{"anrede": "1", "name": "Huber"}])
        self.assertEqual(g["nom_gross"], "Der Beklagte")
        self.assertEqual(g["hat"], "hat")

    def test_nom_gross_und_hat_default_feminin(self):
        g = _beklagten_grammatik([{"versicherung": "X AG"}])
        self.assertEqual(g["nom_gross"], "Die Beklagte")
        self.assertEqual(g["hat"], "hat")
```

- [ ] **Step 2: Fehlschlag verifizieren**

```bash
python -m pytest backend/tests/test_klage_partei_grammatik.py -v -k nom_gross
```

Erwartet: 3× FAIL mit `KeyError: 'nom_gross'`.

- [ ] **Step 3: `_beklagten_grammatik` erweitern** — in jeden der drei Rückgabe-Zweige (klage_service.py:607-613, :615-621, :622-628) zwei Zeilen ergänzen:

Zweig „mehrere": `"nom_gross": "Die Beklagten",` und `"hat": "haben",`
Zweig „männliche Privatperson": `"nom_gross": "Der Beklagte",` und `"hat": "hat",`
Default-Zweig: `"nom_gross": "Die Beklagte",` und `"hat": "hat",`

- [ ] **Step 4: Tests grün**

```bash
python -m pytest backend/tests/test_klage_partei_grammatik.py -v
```

Erwartet: PASS (alle, inkl. Bestand).

- [ ] **Step 5: Die vier Sätze umstellen** — exakt diese Ersetzungen in `klage_service.py`:

Zeile 1573 und Zeile 1608 (identischer Satz, beide Stellen):

```python
            schaden_xml += _p(f"{bek_gram['nom_gross']} {bek_gram['hat']} folgende Zahlungen auf den Schaden geleistet:")
```

Zeilen 1647-1651:

```python
                rw_xml += _p(
                    f"{bek_gram['nom_gross']} {bek_gram['hat']} eine Teilregulierung in Höhe von "
                    f"{_eur_str(gesamt_reguliert)} vorgenommen. Die verbleibenden Kürzungen sind "
                    f"nicht gerechtfertigt, sodass die Klage in Höhe des offenen Restbetrages erhoben wird."
                )
```

Zeilen 1653-1656:

```python
                rw_xml += _p(
                    f"{bek_gram['nom_gross']} {bek_gram['hat']} bislang keine Regulierung vorgenommen. "
                    f"Da trotz mehrfacher Fristsetzung keine Zahlung erfolgte, war die Klage notwendig."
                )
```

(`bek_gram` ist an allen vier Stellen bereits im Scope — wird vor dem Anträge-Block belegt und u. a. :1230/:1767 genutzt.)

- [ ] **Step 6: Golden-Diff bewusst aufnehmen und prüfen**

```bash
python -m pytest backend/tests/test_klage_standardtexte_golden.py -v
```

Erwartet: FAIL (gewollt) in den Szenarien mit 2 Beklagten bzw. männlichem Einzel-Beklagten. Dann:

```bash
KLAGE_GOLDEN_UPDATE=1 python -m pytest backend/tests/test_klage_standardtexte_golden.py -v
git diff backend/tests/golden/klage_standardtexte
```

Diff-Review: Es dürfen sich **ausschließlich** Zeilen ändern, die vorher „Die Beklagte hat …" (Zahlungs-Vorspann / Teilregulierung / keine Regulierung) enthielten — neu „Die Beklagten haben …" bzw. „Der Beklagte hat …". Jede andere Änderung = Fehler, abbrechen und untersuchen.

```bash
python -m pytest backend/tests/test_klage_standardtexte_golden.py backend/tests/test_klage_service_docx.py -v
```

Erwartet: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/word/klage_service.py backend/tests/test_klage_partei_grammatik.py
git add backend/tests/golden/klage_standardtexte
git commit -m "fix(klage): Nebenbefund V11 - Beklagten-Grammatik in Fall-B-/Regulierungssaetzen (nom_gross/hat)"
```

---

### Task 3: Nebenbefund-Fix Frontend — Spiegel in `beklagtenGrammatik` + `buildRwVorschau`

Hält die Wortgleichheits-Invariante pro Commit. **Sichtbare Konsequenz** (für Freigabe-Hinweis): Die Würdigungs-Vorschau schreibt bei mehreren Beklagten künftig „Die Beklagten haben …" statt „Die Beklagte zu 2) hat …" (das `versichererSuffix` entfällt in diesen zwei Sätzen — Backend kennt es dort auch nicht).

**Files:**
- Modify: `frontend/src/sections/KlageWizard.jsx:60-80` (`beklagtenGrammatik`), `:276-286` (`buildRwVorschau` Teilregulierung/keine Regulierung)
- Test: betroffene Vitest-Dateien (u. a. `KlageWizard.haftungsquote.test.jsx`, falls dort gepinnt)

**Interfaces:**
- Produces: `beklagtenGrammatik(beklagte)` liefert zusätzlich `nomGross` (string) und `hat` (string) — wortgleich zu Backend `nom_gross`/`hat`. Task 9 nutzt beide als `ersetzePlatzhalter`-Kontext.

- [ ] **Step 1: Failing Vitest schreiben** — neue Datei `frontend/src/sections/KlageWizard.beklagtengrammatik.test.jsx`:

```jsx
import { describe, it, expect } from "vitest";
import { beklagtenGrammatik, buildRwVorschau } from "./KlageWizard.jsx";

const VERS = { versicherung: "Test-Versicherung AG" };
const MANN = { anrede: "1", name: "Huber" };

describe("beklagtenGrammatik nomGross/hat (V11 Nebenbefund)", () => {
  it("mehrere Beklagte", () => {
    const g = beklagtenGrammatik([VERS, MANN]);
    expect(g.nomGross).toBe("Die Beklagten");
    expect(g.hat).toBe("haben");
  });
  it("maennlicher Einzel-Beklagter", () => {
    const g = beklagtenGrammatik([MANN]);
    expect(g.nomGross).toBe("Der Beklagte");
    expect(g.hat).toBe("hat");
  });
  it("Default feminin", () => {
    const g = beklagtenGrammatik([VERS]);
    expect(g.nomGross).toBe("Die Beklagte");
    expect(g.hat).toBe("hat");
  });
});

describe("buildRwVorschau nutzt Beklagten-Grammatik (V11 Nebenbefund)", () => {
  it("Teilregulierung bei mehreren Beklagten", () => {
    const t = buildRwVorschau("", 100, 500, false, "gegnerisch", [VERS, MANN]);
    expect(t).toContain("Die Beklagten haben eine Teilregulierung");
    expect(t).not.toContain("zu 2)");
  });
  it("keine Regulierung bei maennlichem Beklagten", () => {
    const t = buildRwVorschau("", 100, 0, false, "gegnerisch", [MANN]);
    expect(t).toContain("Der Beklagte hat bislang keine Regulierung vorgenommen.");
  });
});
```

- [ ] **Step 2: Fehlschlag verifizieren**

```bash
cd frontend
npx vitest run src/sections/KlageWizard.beklagtengrammatik.test.jsx
```

Erwartet: FAIL (`nomGross` undefined bzw. alter Wortlaut).

- [ ] **Step 3: `beklagtenGrammatik` erweitern** — in KlageWizard.jsx:60-80 je Zweig ergänzen:

Zweig `gef.length > 1`: `nomGross: "Die Beklagten", hat: "haben",`
Zweig `maennlich`: `nomGross: "Der Beklagte", hat: "hat",`
Default-Zweig: `nomGross: "Die Beklagte", hat: "hat",`

- [ ] **Step 4: `buildRwVorschau` umstellen** — Zeilen 276-286 ersetzen durch:

```jsx
  const gram = beklagtenGrammatik(beklagte);
  if (gesamtReguliert > 0) {
    lines.push(
      `${gram.nomGross} ${gram.hat} eine Teilregulierung in Höhe von ${fmtEuro(gesamtReguliert)} vorgenommen. ` +
      `Die verbleibenden Kürzungen sind nicht gerechtfertigt, sodass die Klage in Höhe des offenen Restbetrages erhoben wird.`
    );
  } else {
    lines.push(
      `${gram.nomGross} ${gram.hat} bislang keine Regulierung vorgenommen. ` +
      `Da trotz mehrfacher Fristsetzung keine Zahlung erfolgte, war die Klage notwendig.`
    );
  }
```

- [ ] **Step 5: Volle Vitest-Suite; Alt-Pins auf den früheren Wortlaut anpassen**

```bash
npx vitest run
```

Erwartet: PASS 362 + 5 neue. Falls Bestandstests „Die Beklagte zu 2) hat" oder „Die Beklagte hat eine Teilregulierung" pinnen → Pins auf neuen Wortlaut anpassen (nur Wortlaut, keine Logik). `KlageWizard.einwaende*`-Tests dürfen unberührt bleiben. Prüfen, ob `versichererSuffix` noch weitere Aufrufer hat (`grep -rn "versichererSuffix" frontend/src`) — Export bleibt bestehen.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/sections/KlageWizard.jsx frontend/src/sections/KlageWizard.beklagtengrammatik.test.jsx
git commit -m "fix(klage-wizard): FE-Spiegel Nebenbefund V11 - nomGross/hat in buildRwVorschau"
```

---

### Task 4: YAML-Registry + Fail-loud-Loader + App-Start-Wiring

**Files:**
- Create: `backend/registry/klage_standardtexte.yaml`
- Create: `backend/services/standardtext_registry.py`
- Modify: `backend/app.py` (nach dem Rausch-Block, ~:164)
- Test: `backend/tests/test_standardtext_registry.py`

**Interfaces:**
- Produces:
  - `lade_standardtexte(pfad=None, *, reload=False) -> dict[str, dict]` — Key → `{"abschnitt": str, "beschreibung": str, "text": str, "platzhalter": [{"key","beschreibung","beispiel","pflicht"}]}`; wirft `RuntimeError` bei jedem Defekt. Env-Override: `KLAGE_STANDARDTEXTE_PFAD`.
  - `ABSCHNITTE: dict[str, str]` (Gruppen-Key → deutsches Label).
  - `hole_texte_aufgeloest() -> dict[str, str]` — Override vor Standard (Overrides kommen erst mit Task 5; bis dahin liefert der `ImportError`/leere-Tabelle-Pfad die reinen Standards, siehe Code).

- [ ] **Step 1: Failing Tests schreiben** — `backend/tests/test_standardtext_registry.py`:

```python
"""Fail-loud-Guards fuer die Klage-Standardtext-Registry (Muster: test_rausch_regel.py)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))

from backend.services.standardtext_registry import lade_standardtexte, ABSCHNITTE

ERWARTETE_KEYS = {
    "antraege_versaeumnis_einleitung", "antraege_versaeumnis_titel",
    "antraege_versaeumnis_schluss",
    "sachverhalt_auslandsunfall",
    "unfallhergang_schilderung_fehlt", "unfallhergang_beweis_rekonstruktion",
    "unfallhergang_beweis_ermittlungsakte", "unfallhergang_beweis_ermittlungsakte_kurz",
    "schaden_einleitung", "schaden_beweis_gutachten", "schaden_beweis_gerichtsgutachten",
    "schaden_zahlungen_vorspann", "schaden_fallb_geklemmt", "schaden_fallb_offen",
    "schaden_fallb_voll", "schaden_differenz", "schaden_gesamtbetrag",
    "wuerdigung_grundhaftung", "wuerdigung_teilregulierung",
    "wuerdigung_keine_regulierung", "wuerdigung_alleinhaftung_bestritten",
    "sg_beweis_atteste", "sg_krankenhaus_mit_klinik", "sg_krankenhaus",
    "sg_arbeitsunfaehigkeit", "sg_dauerfolgen_mit_text", "sg_dauerfolgen",
    "sg_begruendung_mindestbetrag", "sg_begruendung_angemessen",
    "verzug_mit_datum", "verzug_beweis_schreiben", "verzug_rechtshaengigkeit",
    "gebuehren_begruendung_anspruch", "gebuehren_begruendung_kontakt",
    "gebuehren_begruendung_berechnung",
    "gebuehren_zeile_gegenstandswert", "gebuehren_zeile_geschaeftsgebuehr",
    "gebuehren_zeile_post", "gebuehren_zeile_zwischensumme", "gebuehren_zeile_ust",
    "gebuehren_zeile_gesamt", "gebuehren_zeile_gezahlt", "gebuehren_zeile_offen",
    "schluss_hinweis",
}

MINIMAL_GUELTIG = """
platzhalter:
  BETRAG: {beschreibung: "Betrag", beispiel: "1,00 €"}
bausteine:
  - key: schluss_hinweis
    abschnitt: schluss
    beschreibung: "Test"
    text: |-
      Satz mit <BETRAG>.
    platzhalter: [BETRAG]
    pflicht: [BETRAG]
"""


class TestEchteRegistry(unittest.TestCase):
    def test_vollstaendig_gegen_inventar(self):
        reg = lade_standardtexte(reload=True)
        self.assertEqual(ERWARTETE_KEYS, set(reg.keys()))

    def test_struktur_jedes_bausteins(self):
        reg = lade_standardtexte(reload=True)
        for key, e in reg.items():
            with self.subTest(key=key):
                self.assertIn(e["abschnitt"], ABSCHNITTE)
                self.assertTrue(e["beschreibung"].strip())
                self.assertTrue(e["text"].strip())
                for p in e["platzhalter"]:
                    self.assertTrue(p["beschreibung"])
                    self.assertTrue(p["beispiel"])
                    self.assertIn(p["pflicht"], (True, False))


class TestFailLoud(unittest.TestCase):
    def _lade(self, yaml_text):
        tmp = tempfile.mkdtemp(prefix="st_reg_")
        pfad = os.path.join(tmp, "klage_standardtexte.yaml")
        with open(pfad, "w", encoding="utf-8") as f:
            f.write(yaml_text)
        return lade_standardtexte(pfad, reload=True)

    def test_minimal_gueltig(self):
        reg = self._lade(MINIMAL_GUELTIG)
        self.assertEqual(list(reg), ["schluss_hinweis"])
        self.assertEqual(reg["schluss_hinweis"]["platzhalter"][0]["pflicht"], True)

    def test_datei_fehlt(self):
        with self.assertRaises(RuntimeError):
            lade_standardtexte(os.path.join(tempfile.mkdtemp(), "nix.yaml"), reload=True)

    def test_doppelter_key(self):
        kaputt = MINIMAL_GUELTIG + MINIMAL_GUELTIG.split("bausteine:")[1]
        with self.assertRaises(RuntimeError):
            self._lade(kaputt)

    def test_unbekannter_platzhalter_im_text(self):
        with self.assertRaises(RuntimeError):
            self._lade(MINIMAL_GUELTIG.replace("<BETRAG>", "<UNBEKANNT>"))

    def test_platzhalter_ohne_katalogeintrag(self):
        with self.assertRaises(RuntimeError):
            self._lade(MINIMAL_GUELTIG.replace("[BETRAG]\n    pflicht", "[BETRAG, FREMD]\n    pflicht"))

    def test_pflicht_fehlt_im_standardtext(self):
        kaputt = MINIMAL_GUELTIG.replace("Satz mit <BETRAG>.", "Satz ohne Platzhalter.")
        with self.assertRaises(RuntimeError):
            self._lade(kaputt)

    def test_unbekannter_abschnitt(self):
        with self.assertRaises(RuntimeError):
            self._lade(MINIMAL_GUELTIG.replace("abschnitt: schluss", "abschnitt: kapitel_x"))
```

- [ ] **Step 2: Fehlschlag verifizieren**

```bash
python -m pytest backend/tests/test_standardtext_registry.py -v
```

Erwartet: FAIL/ERROR (`ModuleNotFoundError: backend.services.standardtext_registry`).

- [ ] **Step 3: Loader implementieren** — `backend/services/standardtext_registry.py`:

```python
"""
V11 Standardtexte: YAML-Registry der pflegbaren Klageschrift-Bausteine.
Standardtexte bleiben im Programm (diese Registry); die DB-Tabelle
standardtext_override speichert nur Abweichungen. Fail-loud beim App-Start
(Muster: intake/rausch_regel.py).
"""
import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

_cache = {}
_PLATZHALTER_RE = re.compile(r"<([A-Z_]+)>")
_KEY_RE = re.compile(r"^[a-z0-9_]+$")

ABSCHNITTE = {
    "antraege":       "Anträge",
    "sachverhalt":    "Sachverhalt",
    "unfallhergang":  "Unfallhergang",
    "schaden":        "Unfallschaden",
    "wuerdigung":     "Rechtliche Würdigung",
    "schmerzensgeld": "Schmerzensgeld",
    "verzug":         "Verzug",
    "gebuehren":      "Vorgerichtliche Kosten",
    "schluss":        "Schluss",
}


def standard_pfad() -> str:
    env_pfad = os.environ.get("KLAGE_STANDARDTEXTE_PFAD")
    if env_pfad:
        return os.path.normpath(env_pfad)
    hier = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(
        os.path.join(hier, "..", "registry", "klage_standardtexte.yaml"))


def lade_standardtexte(pfad: Optional[str] = None, *, reload: bool = False) -> dict:
    pfad_norm = os.path.normpath(pfad or standard_pfad())
    if not reload and pfad_norm in _cache:
        return _cache[pfad_norm]

    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML nicht installiert (PyYAML>=6.0).") from exc

    if not os.path.isfile(pfad_norm):
        logger.error("Standardtext-Registry fehlt: %s", pfad_norm)
        raise RuntimeError(f"Standardtext-Registry fehlt: {pfad_norm}")

    try:
        with open(pfad_norm, "rb") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        msg = f"YAML-Syntaxfehler in {pfad_norm}: {exc}"
        logger.error(msg)
        raise RuntimeError(msg) from exc

    if not isinstance(data, dict) or "platzhalter" not in data or "bausteine" not in data:
        raise RuntimeError(
            f"{pfad_norm}: Wurzel muss ein Mapping mit 'platzhalter' und 'bausteine' sein.")

    katalog = data["platzhalter"]
    if not isinstance(katalog, dict):
        raise RuntimeError(f"{pfad_norm}: 'platzhalter' muss ein Mapping sein.")
    for pkey, pdef in katalog.items():
        if not _PLATZHALTER_RE.fullmatch(f"<{pkey}>"):
            raise RuntimeError(f"{pfad_norm}: Platzhalter-Key {pkey!r} ungueltig.")
        if not isinstance(pdef, dict) or not str(pdef.get("beschreibung") or "").strip() \
                or not str(pdef.get("beispiel") or "").strip():
            raise RuntimeError(
                f"{pfad_norm}: Platzhalter {pkey!r} braucht beschreibung + beispiel.")

    if not isinstance(data["bausteine"], list) or not data["bausteine"]:
        raise RuntimeError(f"{pfad_norm}: 'bausteine' muss eine nicht-leere Liste sein.")

    registry = {}
    for i, e in enumerate(data["bausteine"]):
        if not isinstance(e, dict):
            raise RuntimeError(f"{pfad_norm}: Baustein {i} ist kein Mapping.")
        key = e.get("key")
        if not isinstance(key, str) or not _KEY_RE.fullmatch(key):
            raise RuntimeError(f"{pfad_norm}: Baustein {i}: 'key' fehlt/ungueltig.")
        if key in registry:
            raise RuntimeError(f"{pfad_norm}: Doppelter Baustein-Key {key!r}.")
        abschnitt = e.get("abschnitt")
        if abschnitt not in ABSCHNITTE:
            raise RuntimeError(f"{pfad_norm}: {key}: unbekannter Abschnitt {abschnitt!r}.")
        beschreibung = str(e.get("beschreibung") or "").strip()
        text = e.get("text")
        if not beschreibung or not isinstance(text, str) or not text.strip():
            raise RuntimeError(f"{pfad_norm}: {key}: beschreibung/text fehlt.")
        erlaubt = e.get("platzhalter") or []
        pflicht = e.get("pflicht") or []
        if not isinstance(erlaubt, list) or not isinstance(pflicht, list):
            raise RuntimeError(f"{pfad_norm}: {key}: platzhalter/pflicht muessen Listen sein.")
        fremd = [p for p in erlaubt if p not in katalog]
        if fremd:
            raise RuntimeError(f"{pfad_norm}: {key}: Platzhalter ohne Katalogeintrag: {fremd}.")
        nicht_erlaubt = [p for p in pflicht if p not in erlaubt]
        if nicht_erlaubt:
            raise RuntimeError(f"{pfad_norm}: {key}: pflicht nicht in platzhalter: {nicht_erlaubt}.")
        benutzt = set(_PLATZHALTER_RE.findall(text))
        unbekannt = sorted(benutzt - set(erlaubt))
        if unbekannt:
            raise RuntimeError(f"{pfad_norm}: {key}: unbekannte Platzhalter im Text: {unbekannt}.")
        fehlend = sorted(set(pflicht) - benutzt)
        if fehlend:
            raise RuntimeError(
                f"{pfad_norm}: {key}: Pflicht-Platzhalter fehlen im Standardtext: {fehlend}.")
        registry[key] = {
            "abschnitt": abschnitt,
            "beschreibung": beschreibung,
            "text": text,
            "platzhalter": [
                {"key": p,
                 "beschreibung": katalog[p]["beschreibung"],
                 "beispiel": katalog[p]["beispiel"],
                 "pflicht": p in pflicht}
                for p in erlaubt
            ],
        }

    _cache[pfad_norm] = registry
    logger.info("Klage-Standardtext-Registry geladen: %d Bausteine aus %s",
                len(registry), pfad_norm)
    return registry


def hole_texte_aufgeloest() -> dict:
    registry = lade_standardtexte()
    try:
        from ..models.standardtext_override import hole_alle_overrides
        overrides = hole_alle_overrides()
    except ImportError:
        overrides = {}
    return {k: overrides.get(k, e["text"]) for k, e in registry.items()}
```

- [ ] **Step 4: YAML anlegen** — `backend/registry/klage_standardtexte.yaml`. Die Texte sind **byte-genau** aus dem Stand nach Task 2 übernommen (Task 6 ersetzt die f-Strings dagegen; der Golden-Test erzwingt Identität — bei Diff gewinnt immer der Code-Stand, nie diese Datei):

```yaml
# V11 Standardtexte Klageschrift (Stufe 1: Kategorien A+B).
# Aenderungen hier aendern die STANDARDS; Kanzlei-Anpassungen laufen ueber
# standardtext_override (Einstellungen-UI). Platzhalter-Syntax: <GROSS_MIT_UNTERSTRICH>.

platzhalter:
  GESAMTSCHADEN:       {beschreibung: "Gesamtschaden laut Schadentabelle (100 %)", beispiel: "5.000,00 €"}
  MITHAFTUNGSQUOTE:    {beschreibung: "Mithaftungsquote der Klägerseite in Prozent", beispiel: "30"}
  HAFTUNGSQUOTE:       {beschreibung: "Haftungsquote der Beklagtenseite in Prozent", beispiel: "70"}
  ERSATZFAEHIG:        {beschreibung: "Ersatzfähiger Betrag nach Quotierung", beispiel: "3.500,00 €"}
  ZAHLUNGEN:           {beschreibung: "Summe der geleisteten Zahlungen", beispiel: "1.000,00 €"}
  KLAGEBETRAG:         {beschreibung: "Betrag des Klageantrags zu 1", beispiel: "2.500,00 €"}
  BETRAG:              {beschreibung: "Betrag in Euro", beispiel: "2.000,00 €"}
  HAFTUNGSBEGRUENDUNG: {beschreibung: "Haftungsbegründung aus dem Wizard (leer → Standardformulierung sein schuldhaftes Verhalten)", beispiel: "sein schuldhaftes Verhalten"}
  ANLAGE_NR:           {beschreibung: "Laufende Anlagen-Nummer", beispiel: "K 2"}
  VERZUGSDATUM:        {beschreibung: "Datum des Verzugseintritts", beispiel: "04.05.2026"}
  SCHREIBEN_DATUM:     {beschreibung: "Datum des Fristsetzungs-Schreibens", beispiel: "20.04.2026"}
  ERMITTLUNGS_AZ:      {beschreibung: "Aktenzeichen der Ermittlungsakte", beispiel: "35 Js 123/26"}
  BEHOERDE:            {beschreibung: "Ermittelnde Behörde", beispiel: "Staatsanwaltschaft Darmstadt"}
  VON:                 {beschreibung: "Beginn-Datum", beispiel: "01.03.2026"}
  BIS:                 {beschreibung: "Ende-Datum", beispiel: "14.03.2026"}
  KLINIK:              {beschreibung: "Name des Krankenhauses", beispiel: "Klinikum Offenbach"}
  DAUERFOLGEN:         {beschreibung: "Beschreibung der Dauerfolgen", beispiel: "Bewegungseinschränkung der rechten Schulter"}
  FAKTOR:              {beschreibung: "Gebührenfaktor (Nr. 2300 VV RVG)", beispiel: "1,3"}
  ANTRAG_NR:           {beschreibung: "Nummer des Klageantrags zu den RVG-Gebühren", beispiel: "3"}
  BEK_NOM:             {beschreibung: "Beklagte, Nominativ großgeschrieben (Die Beklagte / Der Beklagte / Die Beklagten) — Beispiel-Akte: zwei Beklagte", beispiel: "Die Beklagten"}
  BEK_HAT:             {beschreibung: "Verbform hat/haben passend zur Beklagtenzahl", beispiel: "haben"}
  BEK_NOM_KLEIN:       {beschreibung: "Beklagte, Nominativ kleingeschrieben", beispiel: "die Beklagten"}
  BEK_HAFTEN:          {beschreibung: "Verbform haftet/haften passend zur Beklagtenzahl", beispiel: "haften"}

bausteine:
  - key: antraege_versaeumnis_einleitung
    abschnitt: antraege
    beschreibung: "Versäumnisurteil-Block: Einleitungssatz"
    text: |-
      Für den Fall der Anordnung des schriftlichen Vorverfahrens bitten wir, für den Fall der Nichteinlassung der Beklagten:
  - key: antraege_versaeumnis_titel
    abschnitt: antraege
    beschreibung: "Versäumnisurteil-Block: zentrierte fette Zeile"
    text: |-
      Versäumnisurteil
  - key: antraege_versaeumnis_schluss
    abschnitt: antraege
    beschreibung: "Versäumnisurteil-Block: Schlusszeile"
    text: |-
      ohne mündliche Verhandlung zu erlassen.

  - key: sachverhalt_auslandsunfall
    abschnitt: sachverhalt
    beschreibung: "Auslandsunfall: Hinweis auf EuGH C 463/06 und BGH VI ZR 200/05 (Gerichtsstand am Wohnort)"
    text: |-
      Wir machen auf die Entscheidung des EuGH vom 13.12.2007 – Az. C 463/06 –
      und die Vorlage des BGH im Verfahren vom 26.9.2006 zu VI ZR 200/05 aufmerksam. Der EuGH hat in der Entscheidung festgestellt, dass dem Geschädigten auch der Rechtsweg am Gericht seines Wohnortes eröffnet ist.

  - key: unfallhergang_schilderung_fehlt
    abschnitt: unfallhergang
    beschreibung: "Platzhalter-Absatz, wenn keine Unfallschilderung vorliegt"
    text: |-
      [Unfallschilderung – bitte aus RA-Micro WDM laden]
  - key: unfallhergang_beweis_rekonstruktion
    abschnitt: unfallhergang
    beschreibung: "Beweisantritt Unfallrekonstruktionsgutachten"
    text: |-
      Unfallrekonstruktionsgutachten
  - key: unfallhergang_beweis_ermittlungsakte
    abschnitt: unfallhergang
    beschreibung: "Beweisantritt Beiziehung der Ermittlungsakte (mit Behörde)"
    platzhalter: [ERMITTLUNGS_AZ, BEHOERDE]
    pflicht: [ERMITTLUNGS_AZ, BEHOERDE]
    text: |-
      Beiziehung der Ermittlungsakte <ERMITTLUNGS_AZ> bei der <BEHOERDE>
  - key: unfallhergang_beweis_ermittlungsakte_kurz
    abschnitt: unfallhergang
    beschreibung: "Beweisantritt Beiziehung der Ermittlungsakte (ohne Behörde)"
    platzhalter: [ERMITTLUNGS_AZ]
    pflicht: [ERMITTLUNGS_AZ]
    text: |-
      Beiziehung der Ermittlungsakte <ERMITTLUNGS_AZ>

  - key: schaden_einleitung
    abschnitt: schaden
    beschreibung: "Einleitungssatz vor der Schadentabelle"
    text: |-
      Durch den Unfall ist ein Schaden entstanden, der sich wie folgt zusammensetzt:
  - key: schaden_beweis_gutachten
    abschnitt: schaden
    beschreibung: "Beweisantritt Schadengutachten"
    platzhalter: [ANLAGE_NR]
    pflicht: [ANLAGE_NR]
    text: |-
      Schadengutachten (Anlage <ANLAGE_NR>)
  - key: schaden_beweis_gerichtsgutachten
    abschnitt: schaden
    beschreibung: "Beweisantritt gerichtliches Sachverständigengutachten (fett)"
    text: |-
      Einholung eines gerichtlichen Sachverständigengutachtens.
  - key: schaden_zahlungen_vorspann
    abschnitt: schaden
    beschreibung: "Vorspann vor der Zahlungstabelle"
    platzhalter: [BEK_NOM, BEK_HAT]
    pflicht: [BEK_NOM, BEK_HAT]
    text: |-
      <BEK_NOM> <BEK_HAT> folgende Zahlungen auf den Schaden geleistet:
  - key: schaden_fallb_geklemmt
    abschnitt: schaden
    beschreibung: "Fall B (eigene Quote): Zahlungen decken den quotierten Anspruch vollständig"
    platzhalter: [GESAMTSCHADEN, MITHAFTUNGSQUOTE, HAFTUNGSQUOTE, ERSATZFAEHIG, ZAHLUNGEN]
    pflicht: [GESAMTSCHADEN, ERSATZFAEHIG, ZAHLUNGEN]
    text: |-
      Von dem Gesamtschaden in Höhe von <GESAMTSCHADEN> sind unter Berücksichtigung der Mithaftungsquote von <MITHAFTUNGSQUOTE> % <HAFTUNGSQUOTE> %, mithin <ERSATZFAEHIG>, ersatzfähig. Hierauf wurden bereits Zahlungen in Höhe von <ZAHLUNGEN> geleistet; der ersatzfähige Betrag ist damit vollständig ausgeglichen.
  - key: schaden_fallb_offen
    abschnitt: schaden
    beschreibung: "Fall B (eigene Quote): nach Abzug der Zahlungen verbleibt der Klagebetrag"
    platzhalter: [GESAMTSCHADEN, MITHAFTUNGSQUOTE, HAFTUNGSQUOTE, ERSATZFAEHIG, ZAHLUNGEN, KLAGEBETRAG]
    pflicht: [GESAMTSCHADEN, KLAGEBETRAG]
    text: |-
      Von dem Gesamtschaden in Höhe von <GESAMTSCHADEN> sind unter Berücksichtigung der Mithaftungsquote von <MITHAFTUNGSQUOTE> % <HAFTUNGSQUOTE> %, mithin <ERSATZFAEHIG>, ersatzfähig. Abzüglich der geleisteten Zahlungen in Höhe von <ZAHLUNGEN> verbleiben <KLAGEBETRAG>, die mit dem Klageantrag zu 1 geltend gemacht werden.
  - key: schaden_fallb_voll
    abschnitt: schaden
    beschreibung: "Fall B (eigene Quote): keine Zahlungen, voller quotierter Betrag wird eingeklagt"
    platzhalter: [GESAMTSCHADEN, MITHAFTUNGSQUOTE, HAFTUNGSQUOTE, ERSATZFAEHIG]
    pflicht: [GESAMTSCHADEN, ERSATZFAEHIG]
    text: |-
      Von dem Gesamtschaden in Höhe von <GESAMTSCHADEN> sind unter Berücksichtigung der Mithaftungsquote von <MITHAFTUNGSQUOTE> % <HAFTUNGSQUOTE> %, mithin <ERSATZFAEHIG>, ersatzfähig. Dieser Betrag wird mit dem Klageantrag zu 1 geltend gemacht.
  - key: schaden_differenz
    abschnitt: schaden
    beschreibung: "Differenz-Satz: Gesamtbetrag abzüglich Zahlungen ergibt den Klagebetrag"
    platzhalter: [GESAMTSCHADEN, ZAHLUNGEN, KLAGEBETRAG]
    pflicht: [GESAMTSCHADEN, ZAHLUNGEN, KLAGEBETRAG]
    text: |-
      Die Differenz des geforderten Gesamtbetrages in Höhe von <GESAMTSCHADEN> abzgl. der oben gezeigten geleisteten Zahlungen in Höhe von <ZAHLUNGEN> beträgt <KLAGEBETRAG> und wird mit dem Klageantrag zu 1 geltend gemacht.
  - key: schaden_gesamtbetrag
    abschnitt: schaden
    beschreibung: "Ohne Zahlungen: der volle Gesamtbetrag wird eingeklagt"
    platzhalter: [GESAMTSCHADEN]
    pflicht: [GESAMTSCHADEN]
    text: |-
      Der Gesamtbetrag in Höhe von <GESAMTSCHADEN> wird mit dem Klageantrag zu 1 geltend gemacht.

  - key: wuerdigung_grundhaftung
    abschnitt: wuerdigung
    beschreibung: "Grundhaftungssatz mit Haftungsbegründung und Quote"
    platzhalter: [HAFTUNGSBEGRUENDUNG, HAFTUNGSQUOTE]
    pflicht: [HAFTUNGSQUOTE]
    text: |-
      Der bei der Beklagten versicherte Unfallgegner verursachte den Unfall durch <HAFTUNGSBEGRUENDUNG>. Die Haftungsquote beträgt <HAFTUNGSQUOTE> %.
  - key: wuerdigung_teilregulierung
    abschnitt: wuerdigung
    beschreibung: "Hinweis auf erfolgte Teilregulierung"
    platzhalter: [BEK_NOM, BEK_HAT, BETRAG]
    pflicht: [BEK_NOM, BEK_HAT, BETRAG]
    text: |-
      <BEK_NOM> <BEK_HAT> eine Teilregulierung in Höhe von <BETRAG> vorgenommen. Die verbleibenden Kürzungen sind nicht gerechtfertigt, sodass die Klage in Höhe des offenen Restbetrages erhoben wird.
  - key: wuerdigung_keine_regulierung
    abschnitt: wuerdigung
    beschreibung: "Hinweis: bislang keine Regulierung trotz Fristsetzung"
    platzhalter: [BEK_NOM, BEK_HAT]
    pflicht: [BEK_NOM, BEK_HAT]
    text: |-
      <BEK_NOM> <BEK_HAT> bislang keine Regulierung vorgenommen. Da trotz mehrfacher Fristsetzung keine Zahlung erfolgte, war die Klage notwendig.
  - key: wuerdigung_alleinhaftung_bestritten
    abschnitt: wuerdigung
    beschreibung: "Gegnerische Mithaftungsquote wird bestritten (Klage ungekürzt)"
    platzhalter: [MITHAFTUNGSQUOTE]
    pflicht: [MITHAFTUNGSQUOTE]
    text: |-
      Die Beklagtenseite geht von einer Mithaftungsquote von <MITHAFTUNGSQUOTE> % auf Klägerseite aus. Dies wird bestritten; die Beklagtenseite haftet in vollem Umfang. Die Klageforderung ist ungekürzt geltend gemacht.

  - key: sg_beweis_atteste
    abschnitt: schmerzensgeld
    beschreibung: "Beweisantritt ärztliche Atteste (auch im Forderungsschreiben verwendet)"
    platzhalter: [ANLAGE_NR]
    pflicht: [ANLAGE_NR]
    text: |-
      Ärztliche Atteste und Befundberichte (Anlage <ANLAGE_NR>)
  - key: sg_krankenhaus_mit_klinik
    abschnitt: schmerzensgeld
    beschreibung: "Stationärer Aufenthalt mit Klinikname"
    platzhalter: [VON, BIS, KLINIK]
    pflicht: [VON, BIS, KLINIK]
    text: |-
      Vom <VON> bis <BIS> war ein stationärer Aufenthalt im <KLINIK> erforderlich.
  - key: sg_krankenhaus
    abschnitt: schmerzensgeld
    beschreibung: "Stationärer Aufenthalt ohne Klinikname"
    platzhalter: [VON, BIS]
    pflicht: [VON, BIS]
    text: |-
      Vom <VON> bis <BIS> war ein stationärer Aufenthalt erforderlich.
  - key: sg_arbeitsunfaehigkeit
    abschnitt: schmerzensgeld
    beschreibung: "Zeitraum der Arbeitsunfähigkeit"
    platzhalter: [VON, BIS]
    pflicht: [VON, BIS]
    text: |-
      Eine Arbeitsunfähigkeit bestand vom <VON> bis <BIS>.
  - key: sg_dauerfolgen_mit_text
    abschnitt: schmerzensgeld
    beschreibung: "Dauerfolgen mit Beschreibung"
    platzhalter: [DAUERFOLGEN]
    pflicht: [DAUERFOLGEN]
    text: |-
      Es bestehen unfallbedingte Dauerfolgen: <DAUERFOLGEN>.
  - key: sg_dauerfolgen
    abschnitt: schmerzensgeld
    beschreibung: "Dauerfolgen ohne Beschreibung"
    text: |-
      Es bestehen unfallbedingte Dauerfolgen.
  - key: sg_begruendung_mindestbetrag
    abschnitt: schmerzensgeld
    beschreibung: "Schmerzensgeld-Begründung mit Mindestbetrag"
    platzhalter: [BETRAG]
    pflicht: [BETRAG]
    text: |-
      Die erlittenen Verletzungen und Beeinträchtigungen rechtfertigen ein Schmerzensgeld von mindestens <BETRAG>.
  - key: sg_begruendung_angemessen
    abschnitt: schmerzensgeld
    beschreibung: "Schmerzensgeld-Begründung ohne Mindestbetrag"
    text: |-
      Die erlittenen Verletzungen und Beeinträchtigungen rechtfertigen ein angemessenes Schmerzensgeld.

  - key: verzug_mit_datum
    abschnitt: verzug
    beschreibung: "Verzugseintritt mit Datum"
    platzhalter: [VERZUGSDATUM]
    pflicht: [VERZUGSDATUM]
    text: |-
      Der Verzug ist nach Ablauf der Zahlungsfrist bzw. dem ernsthaften und endgültigen Verweigern der Leistung am <VERZUGSDATUM> eingetreten.
  - key: verzug_beweis_schreiben
    abschnitt: verzug
    beschreibung: "Beweisantritt Fristsetzungs-Schreiben"
    platzhalter: [SCHREIBEN_DATUM]
    pflicht: [SCHREIBEN_DATUM]
    text: |-
      Schreiben vom <SCHREIBEN_DATUM>
  - key: verzug_rechtshaengigkeit
    abschnitt: verzug
    beschreibung: "Verzug ohne Datum (Rechtshängigkeit)"
    text: |-
      Verzug ist mit Rechtshängigkeit eingetreten.

  - key: gebuehren_begruendung_anspruch
    abschnitt: gebuehren
    beschreibung: "RVG-Begründung Absatz 1 (Anspruchsgrundlage, Waffengleichheit)"
    platzhalter: [ANTRAG_NR, BEK_NOM_KLEIN, BEK_HAFTEN]
    pflicht: [ANTRAG_NR, BEK_NOM_KLEIN, BEK_HAFTEN]
    text: |-
      Der Klageantrag zu <ANTRAG_NR>. ergibt sich aus den vorgerichtlich entstandenen Gebühren, für die <BEK_NOM_KLEIN> ebenfalls <BEK_HAFTEN>. Der Anspruch auf Zahlung vorgerichtlicher Rechtsverfolgungskosten folgt aus § 249 ff. BGB unabhängig von einem etwaigen Verzugseintritt. Der Geschädigte sieht sich im Regelfall einem in der Regulierung von Unfallschäden versierten Sachbearbeiter des Haftpflichtversicherers gegenüber. Unter dem Aspekt der Waffengleichheit wird deshalb eine Erstattungsfähigkeit der Rechtsanwaltskosten im Rahmen der Rechtsverfolgungskosten grundsätzlich bejaht (Berz/Buhrmann Straßenverkehrsrecht – Hdb/Ziegenhardt, 48. EL August 2023 5. C. Rn. 82, Beck-online).
  - key: gebuehren_begruendung_kontakt
    abschnitt: gebuehren
    beschreibung: "RVG-Begründung Absatz 2 (vorgerichtlicher Kontakt)"
    text: |-
      Der Prozessbevollmächtigte war bereits vorgerichtlich mit der Gegenseite in Kontakt getreten. Letztmalig, als man die Gegenseite unter Fristsetzung zur Zahlung aufforderte.
  - key: gebuehren_begruendung_berechnung
    abschnitt: gebuehren
    beschreibung: "RVG-Begründung Absatz 3 (Überleitung zur Tabelle)"
    text: |-
      Die hieraus vorgerichtlich entstandenen Rechtsanwaltsgebühren sind zu ersetzen. Die Gebühren berechnen sich wie folgt:
  - key: gebuehren_zeile_gegenstandswert
    abschnitt: gebuehren
    beschreibung: "RVG-Tabellenzeile: Gegenstandswert"
    text: |-
      Gegenstandswert:
  - key: gebuehren_zeile_geschaeftsgebuehr
    abschnitt: gebuehren
    beschreibung: "RVG-Tabellenzeile: Geschäftsgebühr"
    platzhalter: [FAKTOR]
    pflicht: [FAKTOR]
    text: |-
      Geschäftsgebühr §§ 13, 14, Nr. 2300 VV RVG (<FAKTOR>):
  - key: gebuehren_zeile_post
    abschnitt: gebuehren
    beschreibung: "RVG-Tabellenzeile: Post- und Telekommunikationspauschale"
    text: |-
      Post u. Telekommunikation Nr. 7002 VV RVG:
  - key: gebuehren_zeile_zwischensumme
    abschnitt: gebuehren
    beschreibung: "RVG-Tabellenzeile: Zwischensumme netto"
    text: |-
      Zwischensumme netto:
  - key: gebuehren_zeile_ust
    abschnitt: gebuehren
    beschreibung: "RVG-Tabellenzeile: Umsatzsteuer"
    text: |-
      19 % Umsatzsteuer:
  - key: gebuehren_zeile_gesamt
    abschnitt: gebuehren
    beschreibung: "RVG-Tabellenzeile: Gesamtbetrag"
    text: |-
      Gesamtbetrag:
  - key: gebuehren_zeile_gezahlt
    abschnitt: gebuehren
    beschreibung: "RVG-Tabellenzeile: bereits gezahlte Kosten"
    text: |-
      abzüglich bereits gezahlter Kosten:
  - key: gebuehren_zeile_offen
    abschnitt: gebuehren
    beschreibung: "RVG-Tabellenzeile: offener Klageanteil"
    text: |-
      Klageanteil (offen):

  - key: schluss_hinweis
    abschnitt: schluss
    beschreibung: "Schlussformel: Bitte um richterlichen Hinweis"
    text: |-
      Sollte das Gericht noch weiteren Vortrag für notwendig erachten, so wird um einen richterlichen Hinweis gebeten.
```

- [ ] **Step 5: Tests grün**

```bash
python -m pytest backend/tests/test_standardtext_registry.py -v
```

Erwartet: PASS (10 Tests).

- [ ] **Step 6: App-Start-Wiring** — in `backend/app.py` direkt nach dem Rausch-Registry-Block (~:164):

```python
    # ── Klage-Standardtext-Registry: Fail-Loud vor DB-Init ────────────────────
    from .services.standardtext_registry import lade_standardtexte as _lade_standardtexte
    _standardtexte = _lade_standardtexte(reload=True)
    logger.info("Klage-Standardtext-Registry geladen: %d Bausteine", len(_standardtexte))
```

App-Start-Guard-Test in `test_standardtext_registry.py` ergänzen (Muster test_registry_app_start.py — kaputtes YAML via Env, `erstelle_app` muss werfen):

```python
class TestAppStartGuard(unittest.TestCase):
    def test_kaputte_registry_stoppt_app_start(self):
        tmp = tempfile.mkdtemp(prefix="st_reg_broken_")
        pfad = os.path.join(tmp, "klage_standardtexte.yaml")
        with open(pfad, "w", encoding="utf-8") as f:
            f.write("bausteine: [")
        alt = os.environ.get("KLAGE_STANDARDTEXTE_PFAD")
        os.environ["KLAGE_STANDARDTEXTE_PFAD"] = pfad
        try:
            from backend.app import erstelle_app
            with self.assertRaises(RuntimeError):
                erstelle_app({"TESTING": True})
        finally:
            if alt is None:
                os.environ.pop("KLAGE_STANDARDTEXTE_PFAD", None)
            else:
                os.environ["KLAGE_STANDARDTEXTE_PFAD"] = alt
```

```bash
python -m pytest backend/tests/test_standardtext_registry.py backend/tests/test_registry_app_start.py -v
```

Erwartet: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/registry/klage_standardtexte.yaml backend/services/standardtext_registry.py backend/app.py backend/tests/test_standardtext_registry.py
git commit -m "feat(standardtexte): YAML-Registry (44 Bausteine) + Fail-loud-Loader + App-Start-Wiring"
```

---

### Task 5: Migration 65 + Override-Model

⚠️ **Reloader-Falle:** VOR den Edits an `schema_manager.py` den Dev-Container stoppen: `docker stop unfallakten-backend-dev`. Aktive Dev-DB liegt im Docker-Volume `dev-data`, nicht in `backend/data/`.

**Files:**
- Modify: `backend/db/schema_manager.py` (MIGRATIONS-Dict ~:23-Block, `_run_migration_65`, Dispatch-`elif` ~:1675)
- Create: `backend/models/standardtext_override.py`
- Test: `backend/tests/test_migration_65.py`

**Interfaces:**
- Produces: Tabelle `standardtext_override(id, baustein_key UNIQUE, text, geaendert_am)`; Model-Funktionen `hole_alle_overrides() -> dict[str,str]`, `hole_alle_overrides_mit_meta() -> dict[str,dict]` (`{"text","geaendert_am"}`), `setze_override(key, text)`, `loesche_override(key) -> bool`. `hole_alle_overrides*` liefern `{}` bei fehlender Tabelle (klage-Unit-Tests laufen ohne Migrationslauf).

- [ ] **Step 1: Failing Migrations-Test** — `backend/tests/test_migration_65.py` (setUp-Muster wortgleich aus `backend/tests/test_migration_62.py` übernehmen: temp-DB via `DB_PATH`, `importlib.reload`, `erstelle_app({"TESTING": True})`):

```python
    def test_tabelle_und_version(self):
        import sqlite3
        conn = sqlite3.connect(self._db_pfad)
        conn.row_factory = sqlite3.Row
        spalten = {r[1] for r in conn.execute(
            "PRAGMA table_info(standardtext_override)").fetchall()}
        self.assertEqual({"id", "baustein_key", "text", "geaendert_am"}, spalten)
        version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
        self.assertGreaterEqual(version, 65)
        conn.execute(
            "INSERT INTO standardtext_override (baustein_key, text) VALUES (?, ?)",
            ("schluss_hinweis", "X"))
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO standardtext_override (baustein_key, text) VALUES (?, ?)",
                ("schluss_hinweis", "Y"))
        conn.close()
```

Run: `python -m pytest backend/tests/test_migration_65.py -v` → Erwartet: FAIL (Tabelle fehlt).

- [ ] **Step 2: Migration schreiben** — Container gestoppt! Alle drei Stellen in `schema_manager.py` in **einer** Bearbeitungsrunde:

MIGRATIONS-Dict: `65: "-- migration_65_standardtext_override",  # Handled by _run_migration_65`

Funktion (neben `_run_migration_64`):

```python
def _run_migration_65(conn: sqlite3.Connection) -> None:
    """
    Migration 65 - standardtext_override (V11 Standardtexte Klageschrift).

    Speichert nur Abweichungen vom YAML-Standard (klage_standardtexte.yaml);
    Reset = DELETE der Zeile. Kein executescript, explizite Commits um DDL
    (Reloader-Falle, feedback_migration_executescript).
    """
    conn.commit()
    conn.execute(
        "CREATE TABLE IF NOT EXISTS standardtext_override ("
        " id            INTEGER PRIMARY KEY AUTOINCREMENT,"
        " baustein_key  TEXT NOT NULL UNIQUE,"
        " text          TEXT NOT NULL,"
        " geaendert_am  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')))"
    )
    conn.commit()
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) VALUES (?, ?)",
        (65, "Migration 65 - standardtext_override (V11 Standardtexte)"),
    )
    logger.info("Migration 65 abgeschlossen (standardtext_override).")
```

Dispatch-Kette: `elif version == 65: _run_migration_65(conn)`.

- [ ] **Step 3: Migrations-Test grün**

```bash
python -m pytest backend/tests/test_migration_65.py -v
```

Erwartet: PASS.

- [ ] **Step 4: Failing Model-Test** — an `test_migration_65.py` anhängen (nutzt dieselbe App/temp-DB):

```python
    def test_model_roundtrip(self):
        from backend.models import standardtext_override as m
        self.assertEqual({}, m.hole_alle_overrides())
        m.setze_override("schluss_hinweis2", "Eigener Text.")
        m.setze_override("schluss_hinweis2", "Eigener Text v2.")
        self.assertEqual({"schluss_hinweis2": "Eigener Text v2."}, m.hole_alle_overrides())
        meta = m.hole_alle_overrides_mit_meta()["schluss_hinweis2"]
        self.assertEqual("Eigener Text v2.", meta["text"])
        self.assertTrue(meta["geaendert_am"])
        self.assertTrue(m.loesche_override("schluss_hinweis2"))
        self.assertFalse(m.loesche_override("schluss_hinweis2"))
        self.assertEqual({}, m.hole_alle_overrides())
```

Run → Erwartet: FAIL (`ModuleNotFoundError`).

- [ ] **Step 5: Model implementieren** — `backend/models/standardtext_override.py` (Verbindungs-Handling exakt wie in `backend/models/kuerzungsart.py` mit `get_connection`; falls dort `with`/`close()` anders gelöst ist, dessen Stil übernehmen):

```python
"""V11 Standardtexte: DB-Overrides (nur Abweichungen vom YAML-Standard)."""
import sqlite3
import logging
from ..db.database import get_connection

logger = logging.getLogger(__name__)


def hole_alle_overrides() -> dict:
    return {k: v["text"] for k, v in hole_alle_overrides_mit_meta().items()}


def hole_alle_overrides_mit_meta() -> dict:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT baustein_key, text, geaendert_am FROM standardtext_override"
        ).fetchall()
    except sqlite3.OperationalError:
        # Tabelle existiert erst ab Migration 65 - reine Unit-Tests des
        # Klage-Services laufen ohne Migrationslauf.
        return {}
    finally:
        conn.close()
    return {r["baustein_key"]: {"text": r["text"], "geaendert_am": r["geaendert_am"]}
            for r in rows}


def setze_override(baustein_key: str, text: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO standardtext_override (baustein_key, text, geaendert_am)"
            " VALUES (?, ?, datetime('now', 'localtime'))"
            " ON CONFLICT(baustein_key) DO UPDATE SET"
            " text = excluded.text, geaendert_am = excluded.geaendert_am",
            (baustein_key, text),
        )
        conn.commit()
    finally:
        conn.close()


def loesche_override(baustein_key: str) -> bool:
    conn = get_connection()
    try:
        cur = conn.execute(
            "DELETE FROM standardtext_override WHERE baustein_key = ?",
            (baustein_key,),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
```

- [ ] **Step 6: Tests grün + Container wieder starten**

```bash
python -m pytest backend/tests/test_migration_65.py -v
docker start unfallakten-backend-dev
docker exec unfallakten-backend-dev python -c "import sqlite3; c=sqlite3.connect('/app/data/unfallakten.db'); print({r[1] for r in c.execute('PRAGMA table_info(standardtext_override)')})"
```

Erwartet: PASS; im Container werden die 4 Spalten gelistet (Migration lief beim Start). Falls der DB-Pfad im Container abweicht: `docker exec unfallakten-backend-dev printenv DB_PATH` prüfen.

- [ ] **Step 7: Commit**

```bash
git add backend/db/schema_manager.py backend/models/standardtext_override.py backend/tests/test_migration_65.py
git commit -m "feat(standardtexte): Migration 65 standardtext_override + Override-Model"
```

---

### Task 6: Service-Umbau — `klage_service` + `sg_text_builder` beziehen Texte aus der Registry

Golden-Test ist der Wächter: nach diesem Task **byte-identisch**, keine Neuaufnahme erlaubt.

**Files:**
- Modify: `backend/word/klage_service.py` (Stufe-1-Literale), `backend/word/sg_text_builder.py`
- Test: `backend/tests/test_klage_standardtexte_golden.py` (bestehend), Override-Wirkung in Task 7

**Interfaces:**
- Consumes: `hole_texte_aufgeloest()` (Task 4), `ersetze_platzhalter` (stellungnahme_service.py:67), `bek_gram["nom_gross"/"hat"]` (Task 2).
- Produces: `baue_sg_abschnitt(ps_data, kl_nom, sg_mind, verb_hat="hat", anlage_nr="K 2", texte=None)` — neue optionale Signatur; `None` lädt selbst (Forderungsschreiben-Pfad bleibt aufrufkompatibel).

- [ ] **Step 1: `_st`-Helfer einführen** — in `_baue_klage_dokument` (klage_service.py:860), direkt nach dem Block, der `cfg`/`details`/`abrechnungen` liest (~:878):

```python
    from ..services.standardtext_registry import hole_texte_aufgeloest
    from .stellungnahme_service import ersetze_platzhalter as _fuelle
    _texte = hole_texte_aufgeloest()

    def _st(key, kontext=None):
        return _fuelle(_texte[key], kontext or {})
```

(Funktions-lokale Imports wie in `kuerzungsarten_routes.py:78` — vermeidet Import-Zyklen über `forderungsschreiben_wv`.)

- [ ] **Step 2: Literale ersetzen** — jede Stelle einzeln editieren, Zeilennummern = Stand nach Task 2:

| Stelle | Neu |
|---|---|
| :1189-1190 Versäumnis-Einleitung | `_p(_st("antraege_versaeumnis_einleitung"))` |
| :1192 Versäumnis-Titel | `_p(_st("antraege_versaeumnis_titel"), fett=True, center=True)` |
| :1194 Versäumnis-Schluss | `_p(_st("antraege_versaeumnis_schluss"))` |
| :1423 Schilderung fehlt | `_p(_st("unfallhergang_schilderung_fehlt"))` |
| :1429 Rekonstruktion | `_p(_st("unfallhergang_beweis_rekonstruktion"), einzug=True)` |
| :1431 EA mit Behörde | `_p(_st("unfallhergang_beweis_ermittlungsakte", {"ERMITTLUNGS_AZ": ea_az, "BEHOERDE": ea_beh}), einzug=True)` |
| :1433 EA ohne Behörde | `_p(_st("unfallhergang_beweis_ermittlungsakte_kurz", {"ERMITTLUNGS_AZ": ea_az}), einzug=True)` |
| :1549 Schaden-Einleitung | `_p(_st("schaden_einleitung"))` |
| :1552 Beweis Gutachten | `_beweis(_st("schaden_beweis_gutachten", {"ANLAGE_NR": anlagen.naechste()}))` |
| :1554 Beweis Gerichts-SV | `_p(_st("schaden_beweis_gerichtsgutachten"), fett=True)` |
| :1573 u. :1608 Zahlungs-Vorspann | `_p(_st("schaden_zahlungen_vorspann", {"BEK_NOM": bek_gram["nom_gross"], "BEK_HAT": bek_gram["hat"]}))` |
| :1578-1584 Fall B geklemmt | `_p(_st("schaden_fallb_geklemmt", {"GESAMTSCHADEN": _eur_str(schaden_gesamt), "MITHAFTUNGSQUOTE": _pct_str(100 - hq), "HAFTUNGSQUOTE": _pct_str(hq), "ERSATZFAEHIG": _eur_str(_ersatzfaehig), "ZAHLUNGEN": _eur_str(fallb_zahlungen)}))` |
| :1586-1592 Fall B offen | `_p(_st("schaden_fallb_offen", {"GESAMTSCHADEN": _eur_str(schaden_gesamt), "MITHAFTUNGSQUOTE": _pct_str(100 - hq), "HAFTUNGSQUOTE": _pct_str(hq), "ERSATZFAEHIG": _eur_str(_ersatzfaehig), "ZAHLUNGEN": _eur_str(_zahlungen_anzeige), "KLAGEBETRAG": _eur_str(klagebetrag)}))` |
| :1594-1599 Fall B voll | `_p(_st("schaden_fallb_voll", {"GESAMTSCHADEN": _eur_str(schaden_gesamt), "MITHAFTUNGSQUOTE": _pct_str(100 - hq), "HAFTUNGSQUOTE": _pct_str(hq), "ERSATZFAEHIG": _eur_str(_ersatzfaehig)}))` |
| :1612-1616 Differenz | `_p(_st("schaden_differenz", {"GESAMTSCHADEN": _eur_str(schaden_gesamt), "ZAHLUNGEN": _eur_str(_zahlungen), "KLAGEBETRAG": _eur_str(klagebetrag)}))` |
| :1619-1622 Gesamtbetrag | `_p(_st("schaden_gesamtbetrag", {"GESAMTSCHADEN": _eur_str(schaden_gesamt)}))` |
| :1640-1642 Grundhaftung | `_p(_st("wuerdigung_grundhaftung", {"HAFTUNGSBEGRUENDUNG": haftungsbegruendung or "sein schuldhaftes Verhalten", "HAFTUNGSQUOTE": _pct_str(hq)}))` |
| :1647-1651 Teilregulierung | `_p(_st("wuerdigung_teilregulierung", {"BEK_NOM": bek_gram["nom_gross"], "BEK_HAT": bek_gram["hat"], "BETRAG": _eur_str(gesamt_reguliert)}))` |
| :1653-1656 Keine Regulierung | `_p(_st("wuerdigung_keine_regulierung", {"BEK_NOM": bek_gram["nom_gross"], "BEK_HAT": bek_gram["hat"]}))` |
| :1666-1671 Alleinhaftung bestritten | `_p(_st("wuerdigung_alleinhaftung_bestritten", {"MITHAFTUNGSQUOTE": _pct_str(100 - hq)}))` |
| :1704-1707 Verzug mit Datum | `_p(_st("verzug_mit_datum", {"VERZUGSDATUM": verzugsdatum}))` |
| :1712 Verzug-Beweis | `_beweis(_st("verzug_beweis_schreiben", {"SCHREIBEN_DATUM": verzug_schreiben}))` |
| :1714 Rechtshängigkeit | `_p(_st("verzug_rechtshaengigkeit"))` |
| :1750 Gegenstandswert | `_rvg_tbl_zeile(_st("gebuehren_zeile_gegenstandswert"), _eur_str(sw_ausserg), fett=True)` |
| :1751-1753 Geschäftsgebühr | `_rvg_tbl_zeile(_st("gebuehren_zeile_geschaeftsgebuehr", {"FAKTOR": str(rvg_fuer_tab.get('faktor', 1.3)).replace('.', ',')}), _eur_str(rvg_fuer_tab.get("gebuehr_netto", 0)))` |
| :1754-1755 Post | `_rvg_tbl_zeile(_st("gebuehren_zeile_post"), _eur_str(rvg_fuer_tab.get("post_pauschale", 0)))` |
| :1756 Zwischensumme | `_rvg_tbl_zeile(_st("gebuehren_zeile_zwischensumme"), _eur_str(rvg_fuer_tab.get("zwischen_netto", 0)), fett=True)` |
| :1757 USt | `_rvg_tbl_zeile(_st("gebuehren_zeile_ust"), _eur_str(rvg_fuer_tab.get("ust", 0)))` |
| :1758 Gesamt | `_rvg_tbl_zeile(_st("gebuehren_zeile_gesamt"), _eur_str(rvg_brutto), fett=True)` |
| :1760 gezahlt | `_rvg_tbl_zeile(_st("gebuehren_zeile_gezahlt"), f"- {_eur_str(rvg_bereits_gezahlt)}")` |
| :1761 offen | `_rvg_tbl_zeile(_st("gebuehren_zeile_offen"), _eur_str(rvg_antrag_betrag), fett=True)` |
| :1778-1788 RVG Abs. 1 | `_p(_st("gebuehren_begruendung_anspruch", {"ANTRAG_NR": str(rvg_antrag_nr), "BEK_NOM_KLEIN": bek_nom, "BEK_HAFTEN": bek_haften}))` |
| :1790-1793 RVG Abs. 2 | `_p(_st("gebuehren_begruendung_kontakt"))` |
| :1795-1798 RVG Abs. 3 | `_p(_st("gebuehren_begruendung_berechnung"))` |
| :1817-1818 Schluss-Hinweis | `_p(_st("schluss_hinweis"))` |

- [ ] **Step 3: `sg_text_builder.py` umstellen** — Signatur + betroffene Zeilen:

```python
def baue_sg_abschnitt(ps_data: dict, kl_nom: str, sg_mind: float, verb_hat: str = "hat",
                       anlage_nr: str = "K 2", texte: dict = None):
```

Direkt am Funktionsanfang:

```python
    if texte is None:
        from ..services.standardtext_registry import hole_texte_aufgeloest
        texte = hole_texte_aufgeloest()
    from .stellungnahme_service import ersetze_platzhalter as _fuelle
```

Zeile 57: `beweis = "BEWEIS: " + _fuelle(texte["sg_beweis_atteste"], {"ANLAGE_NR": anlage_nr})`
Zeilen 107-112 (Krankenhaus): mit Klinik `_fuelle(texte["sg_krankenhaus_mit_klinik"], {"VON": kh_von, "BIS": kh_bis, "KLINIK": kh_name})`, ohne Klinik `_fuelle(texte["sg_krankenhaus"], {"VON": kh_von, "BIS": kh_bis})` (die bisherige `kh_teil`-Konkatenation entfällt).
Zeilen 113-116 (AU): `_fuelle(texte["sg_arbeitsunfaehigkeit"], {"VON": au_von, "BIS": au_bis})`
Zeilen 122-126 (Dauerfolgen): mit Text `_fuelle(texte["sg_dauerfolgen_mit_text"], {"DAUERFOLGEN": dauerfolgen_txt})`, ohne `texte["sg_dauerfolgen"]`
Zeilen 128-137 (Begründung): mit Mindestbetrag `_fuelle(texte["sg_begruendung_mindestbetrag"], {"BETRAG": _eur_str(sg_mind)})`, sonst `texte["sg_begruendung_angemessen"]`

Die kl_nom-Kernsätze (Zeilen 61-67, 96-103) bleiben f-Strings (Kategorie C → Stufe 2).

Aufrufstelle klage_service.py:1676-1679: Parameter `texte=_texte` ergänzen. **Bewusste Konsequenz (Freigabe-Hinweis):** `forderungsschreiben_wv.py` ruft ohne `texte` auf und erhält damit dieselben Overrides — SG-Bausteine wirken einheitlich in Klage **und** Forderungsschreiben.

- [ ] **Step 4: Golden-Parität + Bestand verifizieren**

```bash
python -m pytest backend/tests/test_klage_standardtexte_golden.py backend/tests/test_klage_service_docx.py backend/tests/test_klage_partei_grammatik.py -v
```

Erwartet: PASS, **ohne** Golden-Update. Bei Diff: Registry-Text gegen Code-Alt-Stand abgleichen (Leerzeichen an f-String-Nahtstellen sind die üblichen Täter), YAML korrigieren — niemals die Goldens.

- [ ] **Step 5: Forderungsschreiben-Regression**

```bash
python -m pytest backend/tests/ -k "forderung" -v
```

Erwartet: PASS (bzw. exakt die bekannten Alt-Failures laut Baseline).

- [ ] **Step 6: Commit**

```bash
git add backend/word/klage_service.py backend/word/sg_text_builder.py
git commit -m "feat(standardtexte): klage_service + sg_text_builder beziehen Stufe-1-Texte aus Registry (Golden-paritaetisch)"
```

---

### Task 7: REST-Routen `/klage-standardtexte`

**Files:**
- Create: `backend/routers/standardtexte_routes.py`
- Modify: `backend/app.py` (Import ~:20-51, Registrierung ~:182-217)
- Test: `backend/tests/test_standardtexte_rest.py`

**Interfaces:**
- Produces (alle `@login_erforderlich`):
  - `GET /klage-standardtexte` → `{"bausteine": [{key, abschnitt, abschnitt_label, beschreibung, standard_text, override_text|null, geaendert_am|null, platzhalter: [{key, beschreibung, beispiel, pflicht}]}]}`
  - `PUT /klage-standardtexte/<key>` Body `{"text", "bestaetigt"?}` → 200 `{"ok": true}` · 404 unbekannter Key · 422 `{"fehler", "unbekannt": [...]}` · 409 `{"warnung", "fehlend": [...]}` (Pflicht fehlt, nicht bestätigt)
  - `DELETE /klage-standardtexte/<key>` → `{"ok": true, "geloescht": bool}`
  - `POST /klage-standardtexte/vorschau` Body `{"key", "text"}` → `{"vorschau": str}` (Beispielwerte des Bausteins; Beispiel-Akte „Klägerin + zwei Beklagte" steckt in den BEK_*-Beispielen)
  - `GET /klage-standardtexte/aufgeloest` → `{"texte": {key: text}}`

- [ ] **Step 1: Failing REST-Tests** — `backend/tests/test_standardtexte_rest.py`; setUp/Login-Muster wortgleich aus `backend/tests/test_kuerzungsarten_textbaustein_rest.py` übernehmen (temp-DB, `importlib.reload` inkl. neuem Modul `backend.routers.standardtexte_routes`, `erstelle_app`, Login → `self.h = {"Authorization": f"Bearer {token}"}`). Testmethoden:

```python
    def test_liste_liefert_alle_bausteine(self):
        r = self.client.get("/klage-standardtexte", headers=self.h)
        self.assertEqual(200, r.status_code)
        bausteine = r.get_json()["bausteine"]
        self.assertEqual(44, len(bausteine))
        b = next(x for x in bausteine if x["key"] == "schaden_differenz")
        self.assertEqual("Unfallschaden", b["abschnitt_label"])
        self.assertIsNone(b["override_text"])
        self.assertTrue(any(p["key"] == "KLAGEBETRAG" and p["pflicht"]
                            for p in b["platzhalter"]))

    def test_put_unbekannter_baustein_404(self):
        r = self.client.put("/klage-standardtexte/gibt_es_nicht",
                            json={"text": "X"}, headers=self.h)
        self.assertEqual(404, r.status_code)

    def test_put_unbekannter_platzhalter_422(self):
        r = self.client.put("/klage-standardtexte/schluss_hinweis",
                            json={"text": "Hinweis <FANTASIE>."}, headers=self.h)
        self.assertEqual(422, r.status_code)
        self.assertEqual(["FANTASIE"], r.get_json()["unbekannt"])

    def test_put_pflicht_fehlt_409_dann_bestaetigt_200(self):
        r = self.client.put("/klage-standardtexte/schaden_gesamtbetrag",
                            json={"text": "Ohne Betrag."}, headers=self.h)
        self.assertEqual(409, r.status_code)
        self.assertEqual(["GESAMTSCHADEN"], r.get_json()["fehlend"])
        r = self.client.put("/klage-standardtexte/schaden_gesamtbetrag",
                            json={"text": "Ohne Betrag.", "bestaetigt": True},
                            headers=self.h)
        self.assertEqual(200, r.status_code)

    def test_override_roundtrip_und_aufgeloest(self):
        neu = "Um richterlichen Hinweis wird gebeten."
        r = self.client.put("/klage-standardtexte/schluss_hinweis",
                            json={"text": neu}, headers=self.h)
        self.assertEqual(200, r.status_code)
        liste = self.client.get("/klage-standardtexte", headers=self.h).get_json()
        b = next(x for x in liste["bausteine"] if x["key"] == "schluss_hinweis")
        self.assertEqual(neu, b["override_text"])
        self.assertTrue(b["geaendert_am"])
        texte = self.client.get("/klage-standardtexte/aufgeloest",
                                headers=self.h).get_json()["texte"]
        self.assertEqual(neu, texte["schluss_hinweis"])
        r = self.client.delete("/klage-standardtexte/schluss_hinweis", headers=self.h)
        self.assertEqual(200, r.status_code)
        texte = self.client.get("/klage-standardtexte/aufgeloest",
                                headers=self.h).get_json()["texte"]
        self.assertIn("richterlichen Hinweis gebeten", texte["schluss_hinweis"])

    def test_vorschau_mit_beispielwerten(self):
        r = self.client.post("/klage-standardtexte/vorschau",
                             json={"key": "schaden_gesamtbetrag",
                                   "text": "Betrag: <GESAMTSCHADEN> Ende <TIPPFEHLER>"},
                             headers=self.h)
        self.assertEqual(200, r.status_code)
        v = r.get_json()["vorschau"]
        self.assertIn("5.000,00 €", v)
        self.assertIn("[FEHLT: <TIPPFEHLER>]", v)

    def test_override_wirkt_im_dokument(self):
        neu = "Um richterlichen Hinweis wird ausdruecklich gebeten."
        self.client.put("/klage-standardtexte/schluss_hinweis",
                        json={"text": neu}, headers=self.h)
        from backend.tests.test_klage_service_docx import _akte_daten, _position
        from backend.word.klage_service import baue_klage_vorschau
        res = baue_klage_vorschau(_akte_daten(
            [_position("fahrzeugschaden", "Fahrzeugschaden", 3000.0)]))
        gesamt = "\n".join(a["text"] for a in res["abschnitte"])
        self.assertIn(neu, gesamt)
```

Run: `python -m pytest backend/tests/test_standardtexte_rest.py -v` → Erwartet: FAIL/404 (Blueprint fehlt).

- [ ] **Step 2: Router implementieren** — `backend/routers/standardtexte_routes.py`:

```python
"""
V11 Standardtexte: REST-Routen fuer die pflegbaren Klageschrift-Bausteine.
Muster: kuerzungsarten_routes.py (Platzhalter-Katalog + Vorschau).
"""
import re

from flask import Blueprint, jsonify, request

from ..auth.middleware import login_erforderlich
from ..services.standardtext_registry import (
    ABSCHNITTE, hole_texte_aufgeloest, lade_standardtexte)
from ..models.standardtext_override import (
    hole_alle_overrides_mit_meta, loesche_override, setze_override)

standardtexte_bp = Blueprint(
    "standardtexte", __name__, url_prefix="/klage-standardtexte")

_PLATZHALTER_RE = re.compile(r"<([A-Z_]+)>")


def _j(d, s=200):
    return jsonify(d), s


def _body():
    return request.get_json(silent=True) or {}


@standardtexte_bp.route("", methods=["GET"])
@login_erforderlich
def liste():
    registry = lade_standardtexte()
    overrides = hole_alle_overrides_mit_meta()
    bausteine = []
    for key, e in registry.items():
        ov = overrides.get(key)
        bausteine.append({
            "key": key,
            "abschnitt": e["abschnitt"],
            "abschnitt_label": ABSCHNITTE[e["abschnitt"]],
            "beschreibung": e["beschreibung"],
            "standard_text": e["text"],
            "override_text": ov["text"] if ov else None,
            "geaendert_am": ov["geaendert_am"] if ov else None,
            "platzhalter": e["platzhalter"],
        })
    return _j({"bausteine": bausteine})


@standardtexte_bp.route("/aufgeloest", methods=["GET"])
@login_erforderlich
def aufgeloest():
    return _j({"texte": hole_texte_aufgeloest()})


@standardtexte_bp.route("/vorschau", methods=["POST"])
@login_erforderlich
def vorschau():
    from ..word.stellungnahme_service import ersetze_platzhalter
    body = _body()
    e = lade_standardtexte().get(str(body.get("key") or ""))
    if not e:
        return _j({"fehler": "Unbekannter Baustein."}, 404)
    kontext = {p["key"]: p["beispiel"] for p in e["platzhalter"]}
    return _j({"vorschau": ersetze_platzhalter(body.get("text") or "", kontext)})


@standardtexte_bp.route("/<key>", methods=["PUT"])
@login_erforderlich
def speichern(key):
    e = lade_standardtexte().get(key)
    if not e:
        return _j({"fehler": f"Unbekannter Baustein: {key}"}, 404)
    body = _body()
    text = str(body.get("text") or "").strip()
    if not text:
        return _j({"fehler": "Text darf nicht leer sein."}, 422)
    erlaubt = {p["key"] for p in e["platzhalter"]}
    benutzt = set(_PLATZHALTER_RE.findall(text))
    unbekannt = sorted(benutzt - erlaubt)
    if unbekannt:
        return _j({"fehler": "Unbekannte Platzhalter.", "unbekannt": unbekannt}, 422)
    pflicht = {p["key"] for p in e["platzhalter"] if p["pflicht"]}
    fehlend = sorted(pflicht - benutzt)
    if fehlend and not body.get("bestaetigt"):
        return _j({"warnung": "Pflicht-Platzhalter fehlen.", "fehlend": fehlend}, 409)
    setze_override(key, text)
    return _j({"ok": True})


@standardtexte_bp.route("/<key>", methods=["DELETE"])
@login_erforderlich
def zuruecksetzen(key):
    if key not in lade_standardtexte():
        return _j({"fehler": f"Unbekannter Baustein: {key}"}, 404)
    return _j({"ok": True, "geloescht": loesche_override(key)})
```

In `backend/app.py`: `from .routers.standardtexte_routes import standardtexte_bp` (Import-Block) + `app.register_blueprint(standardtexte_bp)` (Registrierungs-Block).

- [ ] **Step 3: Tests grün**

```bash
python -m pytest backend/tests/test_standardtexte_rest.py backend/tests/test_standardtext_registry.py -v
```

Erwartet: PASS (7 + 11).

- [ ] **Step 4: Commit**

```bash
git add backend/routers/standardtexte_routes.py backend/app.py backend/tests/test_standardtexte_rest.py
git commit -m "feat(standardtexte): REST /klage-standardtexte (Liste, Override, Reset, Vorschau, aufgeloest)"
```

---

### Task 8: Einstellungen-UI — Karte „Standardtexte Klageschrift"

**Files:**
- Modify: `frontend/src/api.js` (nach dem `kuerzungsarten`-Objekt, ~:624), `frontend/vite.config.js` (Proxy-Liste ~:25), `frontend/src/views/EinstellungenView.jsx` (Tab-Liste :284-294, Badge-Ausschluss :302-309, Panel, Import)
- Create: `frontend/src/views/StandardtexteTab.jsx`
- Test: `frontend/src/views/StandardtexteTab.test.jsx`

**Interfaces:**
- Consumes: REST aus Task 7; `TextbausteinEditor` (Props `wert, onChange, platzhalter, onVorschau, standardText, onReset`) + `pruefePlatzhalter(text, keys)` aus `frontend/src/components/TextbausteinEditor.jsx`.
- Produces: `apiStandardtexte = { liste(), speichern(key, text, bestaetigt), reset(key), vorschau(key, text), aufgeloest() }` in api.js (Task 9 nutzt `aufgeloest`).

- [ ] **Step 1: api.js + Proxy**

Nach dem `kuerzungsarten`-Export in `frontend/src/api.js`:

```js
export const apiStandardtexte = {
  liste:      ()                      => request('/klage-standardtexte'),
  speichern:  (key, text, bestaetigt) => request(`/klage-standardtexte/${key}`, { method: 'PUT', body: JSON.stringify({ text, bestaetigt: !!bestaetigt }) }),
  reset:      (key)                   => request(`/klage-standardtexte/${key}`, { method: 'DELETE' }),
  vorschau:   (key, text)             => request('/klage-standardtexte/vorschau', { method: 'POST', body: JSON.stringify({ key, text }) }),
  aufgeloest: ()                      => request('/klage-standardtexte/aufgeloest'),
};
```

In `frontend/vite.config.js` Proxy-Liste (unter `/kuerzungsarten`, :25):

```js
      '/klage-standardtexte':{ target: process.env.VITE_BACKEND_URL || 'http://localhost:5000', changeOrigin: true },
```

- [ ] **Step 2: Failing Vitest** — `frontend/src/views/StandardtexteTab.test.jsx`:

```jsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";

const BAUSTEIN = {
  key: "schaden_gesamtbetrag", abschnitt: "schaden", abschnitt_label: "Unfallschaden",
  beschreibung: "Ohne Zahlungen: der volle Gesamtbetrag wird eingeklagt",
  standard_text: "Der Gesamtbetrag in Höhe von <GESAMTSCHADEN> wird mit dem Klageantrag zu 1 geltend gemacht.",
  override_text: null, geaendert_am: null,
  platzhalter: [{ key: "GESAMTSCHADEN", beschreibung: "Gesamtschaden", beispiel: "5.000,00 €", pflicht: true }],
};
const GEAENDERT = { ...BAUSTEIN, key: "schluss_hinweis", abschnitt: "schluss",
  abschnitt_label: "Schluss", beschreibung: "Schlussformel", platzhalter: [],
  standard_text: "Standard.", override_text: "Eigener Text.", geaendert_am: "2026-07-24 10:00:00" };

const api = {
  liste: vi.fn().mockResolvedValue({ bausteine: [BAUSTEIN, GEAENDERT] }),
  speichern: vi.fn().mockResolvedValue({ ok: true }),
  reset: vi.fn().mockResolvedValue({ ok: true, geloescht: true }),
  vorschau: vi.fn().mockResolvedValue({ vorschau: "Vorschau." }),
  aufgeloest: vi.fn().mockResolvedValue({ texte: {} }),
};
vi.mock("../api.js", () => ({ apiStandardtexte: api }));

import StandardtexteTab from "./StandardtexteTab.jsx";

describe("StandardtexteTab", () => {
  beforeEach(() => vi.clearAllMocks());

  it("gruppiert nach Abschnitt und markiert geaenderte Bausteine", async () => {
    render(<StandardtexteTab />);
    await waitFor(() => expect(screen.getByText("Unfallschaden")).toBeInTheDocument());
    expect(screen.getByText("Schluss")).toBeInTheDocument();
    expect(screen.getAllByText("geändert").length).toBe(1);
  });

  it("Suche filtert die Liste", async () => {
    render(<StandardtexteTab />);
    await waitFor(() => screen.getByText("Schlussformel"));
    fireEvent.change(screen.getByPlaceholderText(/Suche/i), { target: { value: "Gesamtbetrag" } });
    expect(screen.queryByText("Schlussformel")).toBeNull();
    expect(screen.getByText(/Gesamtbetrag wird eingeklagt/)).toBeInTheDocument();
  });

  it("Speichern mit fehlendem Pflicht-Platzhalter fragt nach Bestaetigung", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<StandardtexteTab />);
    await waitFor(() => screen.getByText(/Gesamtbetrag wird eingeklagt/));
    fireEvent.click(screen.getByText(/Gesamtbetrag wird eingeklagt/));
    const ta = await screen.findByDisplayValue(/Der Gesamtbetrag in Höhe von/);
    fireEvent.change(ta, { target: { value: "Ohne Platzhalter." } });
    fireEvent.click(screen.getByRole("button", { name: /Speichern/ }));
    await waitFor(() => expect(api.speichern).toHaveBeenCalledWith(
      "schaden_gesamtbetrag", "Ohne Platzhalter.", true));
    expect(confirmSpy).toHaveBeenCalled();
    confirmSpy.mockRestore();
  });

  it("Reset ruft api.reset", async () => {
    render(<StandardtexteTab />);
    await waitFor(() => screen.getByText("Schlussformel"));
    fireEvent.click(screen.getByText("Schlussformel"));
    fireEvent.click(await screen.findByText(/Auf Standard zurücksetzen/));
    await waitFor(() => expect(api.reset).toHaveBeenCalledWith("schluss_hinweis"));
  });
});
```

Run: `cd frontend` → `npx vitest run src/views/StandardtexteTab.test.jsx` → Erwartet: FAIL (Komponente fehlt).

- [ ] **Step 3: Komponente implementieren** — `frontend/src/views/StandardtexteTab.jsx`:

```jsx
import { useEffect, useMemo, useState } from "react";
import TextbausteinEditor, { pruefePlatzhalter } from "../components/TextbausteinEditor.jsx";
import { apiStandardtexte } from "../api.js";

const ABSCHNITT_REIHENFOLGE = ["antraege", "sachverhalt", "unfallhergang", "schaden",
  "wuerdigung", "schmerzensgeld", "verzug", "gebuehren", "schluss"];

export default function StandardtexteTab() {
  const [bausteine, setBausteine] = useState([]);
  const [suche, setSuche] = useState("");
  const [offen, setOffen] = useState(null);
  const [entwurf, setEntwurf] = useState("");
  const [meldung, setMeldung] = useState(null);

  const laden = () => apiStandardtexte.liste()
    .then(r => setBausteine(r.bausteine || []))
    .catch(e => setMeldung(`Laden fehlgeschlagen: ${e.message}`));
  useEffect(() => { laden(); }, []);

  const gruppen = useMemo(() => {
    const q = suche.trim().toLowerCase();
    const passend = bausteine.filter(b => !q
      || b.key.includes(q)
      || b.beschreibung.toLowerCase().includes(q)
      || (b.override_text || b.standard_text).toLowerCase().includes(q));
    return ABSCHNITT_REIHENFOLGE
      .map(a => ({ abschnitt: a,
                   label: passend.find(b => b.abschnitt === a)?.abschnitt_label,
                   eintraege: passend.filter(b => b.abschnitt === a) }))
      .filter(g => g.eintraege.length > 0);
  }, [bausteine, suche]);

  const oeffnen = (b) => {
    setOffen(b.key === offen ? null : b.key);
    setEntwurf(b.override_text ?? b.standard_text);
    setMeldung(null);
  };

  const speichern = async (b) => {
    const pflicht = b.platzhalter.filter(p => p.pflicht).map(p => p.key);
    const fehlend = pflicht.filter(k => !entwurf.includes(`<${k}>`));
    let bestaetigt = false;
    if (fehlend.length > 0) {
      bestaetigt = window.confirm(
        `Pflicht-Platzhalter fehlen: ${fehlend.map(k => `<${k}>`).join(", ")}.\n` +
        `Der Wert erscheint dann nicht mehr im Dokument. Trotzdem speichern?`);
      if (!bestaetigt) return;
    }
    try {
      await apiStandardtexte.speichern(b.key, entwurf, bestaetigt);
      setMeldung("Gespeichert.");
      laden();
    } catch (e) {
      setMeldung(`Speichern fehlgeschlagen: ${e.message}`);
    }
  };

  const zuruecksetzen = async (b) => {
    await apiStandardtexte.reset(b.key);
    setEntwurf(b.standard_text);
    setMeldung("Auf Standard zurückgesetzt.");
    laden();
  };

  return (
    <div>
      <h3 style={{ margin: "0 0 4px" }}>Standardtexte Klageschrift</h3>
      <p style={{ margin: "0 0 12px", opacity: 0.75 }}>
        Feste Rahmen- und Kernsätze der Klageschrift. Geänderte Bausteine gelten
        sofort für neue Dokumente; „Auf Standard zurücksetzen" stellt den
        Programmtext wieder her.
      </p>
      <input placeholder="Suche (Beschreibung, Text, Kennung)…" value={suche}
             onChange={e => setSuche(e.target.value)}
             style={{ width: "100%", marginBottom: 12, padding: 6 }} />
      {meldung && <div style={{ marginBottom: 8 }}>{meldung}</div>}
      {gruppen.map(g => (
        <div key={g.abschnitt} style={{ marginBottom: 16 }}>
          <h4 style={{ margin: "8px 0" }}>{g.label}</h4>
          {g.eintraege.map(b => {
            const istOffen = offen === b.key;
            const pruefung = istOffen
              ? pruefePlatzhalter(entwurf, b.platzhalter.map(p => p.key))
              : { ok: true };
            return (
              <div key={b.key} style={{ border: "1px solid #8884", borderRadius: 6,
                                        padding: 8, marginBottom: 8 }}>
                <div onClick={() => oeffnen(b)} style={{ cursor: "pointer" }}>
                  <strong>{b.beschreibung}</strong>
                  {b.override_text != null &&
                    <span style={{ marginLeft: 8, fontSize: 12, padding: "1px 6px",
                                   borderRadius: 8, background: "#e6a70033" }}>geändert</span>}
                  <span style={{ float: "right", opacity: 0.5, fontSize: 12 }}>{b.key}</span>
                </div>
                {istOffen && (
                  <div style={{ marginTop: 8 }}>
                    <TextbausteinEditor
                      wert={entwurf}
                      onChange={setEntwurf}
                      platzhalter={b.platzhalter}
                      onVorschau={async (t) => (await apiStandardtexte.vorschau(b.key, t)).vorschau}
                      standardText={b.override_text != null ? b.standard_text : null}
                      onReset={b.override_text != null ? () => zuruecksetzen(b) : null}
                    />
                    <details style={{ margin: "6px 0" }}>
                      <summary>Standardtext anzeigen</summary>
                      <pre style={{ whiteSpace: "pre-wrap" }}>{b.standard_text}</pre>
                    </details>
                    <button onClick={() => speichern(b)} disabled={!pruefung.ok}>
                      Speichern
                    </button>
                    {b.geaendert_am &&
                      <span style={{ marginLeft: 8, fontSize: 12, opacity: 0.6 }}>
                        geändert am {b.geaendert_am}</span>}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
```

(Styling beim Umsetzen an `KuerzungskatalogView.jsx` / `theme.js` angleichen — Struktur und Verhalten wie oben.)

- [ ] **Step 4: Tab in EinstellungenView registrieren**

- Import: `import StandardtexteTab from "./StandardtexteTab.jsx";`
- Tab-Liste (:284-294): Eintrag `["standardtexte", "📄 Standardtexte"],` nach `["zustaendigkeit", …]` einfügen.
- Badge-Ausschluss (:302-309): `id !== "standardtexte"` zur Ausschlussliste hinzufügen.
- Panel: `{tab === "standardtexte" && <StandardtexteTab />}` neben den anderen Panels.

- [ ] **Step 5: Tests grün + Handprobe**

```bash
npx vitest run src/views/StandardtexteTab.test.jsx
npx vitest run
```

Erwartet: neue Tests PASS, Gesamtsuite grün. Kurze Browser-Handprobe (Docker-Dev): Einstellungen → Standardtexte → Baustein öffnen, Chip klicken, Vorschau erscheint, Speichern/Reset.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api.js frontend/vite.config.js frontend/src/views/StandardtexteTab.jsx frontend/src/views/StandardtexteTab.test.jsx frontend/src/views/EinstellungenView.jsx
git commit -m "feat(standardtexte): Einstellungen-Karte Standardtexte Klageschrift (TextbausteinEditor-Wiederverwendung)"
```

---

### Task 9: Klage-Wizard bezieht Stufe-1-Texte über `/aufgeloest`

Betroffen sind genau die drei FE-Generatoren mit Stufe-1-Texten: Auslandsunfall-Absatz (`buildSachverhaltText`), Verzugs-Texte (`buildVerzugAutoText`), Würdigung Grundhaftung/Teilregulierung/keine Regulierung/Alleinhaftung-bestritten (`buildRwVorschau`). Kategorie-C-Sätze (Kläger-Grammatik, hq≥100-Satz, Einleitungs-/Beklagten-Sätze) bleiben bis Stufe 2 Literale.

**Files:**
- Create: `frontend/src/test/standardtexteFixture.js`
- Modify: `frontend/src/sections/KlageWizard.jsx` (`buildSachverhaltText` :132-187, `buildRwVorschau` :249-304, `buildVerzugAutoText` :1526-1532, Wizard-Mount + Aufrufstellen), ggf. `frontend/src/sections/KlageSection.jsx` (Aufrufstellen)
- Test: bestehende Vitest-Dateien der drei Funktionen

**Interfaces:**
- Consumes: `apiStandardtexte.aufgeloest()`, `ersetzePlatzhalter` + `genusKontext` aus `platzhalterLogik.js` (bereits importiert :28), `beklagtenGrammatik().nomGross/.hat` (Task 3).
- Produces: geänderte Signaturen — `buildSachverhaltText({ …, auslandsunfallText })`, `buildRwVorschau(haftungsbegruendung, haftungsquote, gesamtReguliert, weiblich, hqTyp, beklagte, texte)`, `buildVerzugAutoText(dokDatum, eintrittDatum, texte)`.

- [ ] **Step 1: Fixture anlegen** — `frontend/src/test/standardtexteFixture.js` (Werte = Standardtexte aus der YAML, nur die FE-relevanten Keys):

```js
export const STANDARDTEXTE_FIXTURE = {
  sachverhalt_auslandsunfall:
    "Wir machen auf die Entscheidung des EuGH vom 13.12.2007 – Az. C 463/06 –\nund die Vorlage des BGH im Verfahren vom 26.9.2006 zu VI ZR 200/05 aufmerksam. Der EuGH hat in der Entscheidung festgestellt, dass dem Geschädigten auch der Rechtsweg am Gericht seines Wohnortes eröffnet ist.",
  verzug_mit_datum:
    "Der Verzug ist nach Ablauf der Zahlungsfrist bzw. dem ernsthaften und endgültigen Verweigern der Leistung am <VERZUGSDATUM> eingetreten.",
  verzug_beweis_schreiben: "Schreiben vom <SCHREIBEN_DATUM>",
  verzug_rechtshaengigkeit: "Verzug ist mit Rechtshängigkeit eingetreten.",
  wuerdigung_grundhaftung:
    "Der bei der Beklagten versicherte Unfallgegner verursachte den Unfall durch <HAFTUNGSBEGRUENDUNG>. Die Haftungsquote beträgt <HAFTUNGSQUOTE> %.",
  wuerdigung_teilregulierung:
    "<BEK_NOM> <BEK_HAT> eine Teilregulierung in Höhe von <BETRAG> vorgenommen. Die verbleibenden Kürzungen sind nicht gerechtfertigt, sodass die Klage in Höhe des offenen Restbetrages erhoben wird.",
  wuerdigung_keine_regulierung:
    "<BEK_NOM> <BEK_HAT> bislang keine Regulierung vorgenommen. Da trotz mehrfacher Fristsetzung keine Zahlung erfolgte, war die Klage notwendig.",
  wuerdigung_alleinhaftung_bestritten:
    "Die Beklagtenseite geht von einer Mithaftungsquote von <MITHAFTUNGSQUOTE> % auf Klägerseite aus. Dies wird bestritten; die Beklagtenseite haftet in vollem Umfang. Die Klageforderung ist ungekürzt geltend gemacht.",
};
```

- [ ] **Step 2: Failing Test** — an `KlageWizard.beklagtengrammatik.test.jsx` anhängen:

```jsx
import { STANDARDTEXTE_FIXTURE as TEXTE } from "../test/standardtexteFixture.js";
import { buildVerzugAutoText } from "./KlageWizard.jsx";

describe("Generatoren beziehen Standardtexte aus der Registry-Map (V11)", () => {
  it("buildVerzugAutoText nutzt Registry-Text mit Platzhaltern", () => {
    const t = buildVerzugAutoText("2026-04-20", "2026-05-04", TEXTE);
    expect(t).toContain("am 04.05.2026 eingetreten.");
    expect(t).toContain("BEWEIS: Schreiben vom 20.04.2026");
  });
  it("buildVerzugAutoText ohne Datum nutzt Rechtshaengigkeits-Baustein", () => {
    expect(buildVerzugAutoText(null, null, TEXTE))
      .toBe("Verzug ist mit Rechtshängigkeit eingetreten.");
  });
  it("buildRwVorschau nutzt Registry-Texte", () => {
    const t = buildRwVorschau("grobe Vorfahrtsverletzung", 70, 500, false,
                              "gegnerisch", [VERS, MANN], TEXTE);
    expect(t).toContain("durch grobe Vorfahrtsverletzung. Die Haftungsquote beträgt 70 %.");
    expect(t).toContain("Die Beklagten haben eine Teilregulierung in Höhe von 500,00 € vorgenommen.");
    expect(t).toContain("Mithaftungsquote von 30 % auf Klägerseite");
  });
});
```

Run: `npx vitest run src/sections/KlageWizard.beklagtengrammatik.test.jsx` → Erwartet: FAIL (Signaturen ohne `texte`).

- [ ] **Step 3: Generatoren umstellen** — in `KlageWizard.jsx`:

`buildVerzugAutoText` (:1526-1532) ersetzen durch:

```jsx
export function buildVerzugAutoText(dokDatum, eintrittDatum, texte) {
  const vDat = fmtDatumDe(eintrittDatum);
  const bDat = fmtDatumDe(dokDatum);
  if (!vDat) return texte.verzug_rechtshaengigkeit;
  const basis = ersetzePlatzhalter(texte.verzug_mit_datum, { VERZUGSDATUM: vDat });
  if (!bDat) return basis;
  return `${basis}\n\nBEWEIS: ${ersetzePlatzhalter(texte.verzug_beweis_schreiben, { SCHREIBEN_DATUM: bDat })}`;
}
```

`buildRwVorschau` (:249-304): Signatur um `texte` erweitern; die vier Textstellen ersetzen:

```jsx
export function buildRwVorschau(haftungsbegruendung, haftungsquote, gesamtReguliert,
                                weiblich, hqTyp = "gegnerisch", beklagte = [], texte) {
```

- Grundhaftung (else-Zweig :269-274): `lines.push(ersetzePlatzhalter(texte.wuerdigung_grundhaftung, { HAFTUNGSBEGRUENDUNG: (haftungsbegruendung || "").trim() || "sein schuldhaftes Verhalten", HAFTUNGSQUOTE: pctStr(hq) }));`
- Teilregulierung/keine Regulierung (Task-3-Stand): `lines.push(ersetzePlatzhalter(texte.wuerdigung_teilregulierung, { BEK_NOM: gram.nomGross, BEK_HAT: gram.hat, BETRAG: fmtEuro(gesamtReguliert) }));` bzw. `lines.push(ersetzePlatzhalter(texte.wuerdigung_keine_regulierung, { BEK_NOM: gram.nomGross, BEK_HAT: gram.hat }));`
- Alleinhaftung bestritten (hqTyp ≠ eigen, :295-299): `lines.push(ersetzePlatzhalter(texte.wuerdigung_alleinhaftung_bestritten, { MITHAFTUNGSQUOTE: pctStr(100 - hq) }));`
- hq≥100-Zweig und Mithaftung-eigen-Zweig (Kläger-Grammatik) bleiben unverändert (Stufe 2).

`buildSachverhaltText` (:132-187): Options-Objekt um `auslandsunfallText` erweitern; Auslandsunfall-Block (:182-184) ersetzen durch:

```jsx
  if (auslandsunfall && auslandsunfallText) {
    text += "\n\n" + auslandsunfallText;
  }
```

- [ ] **Step 4: Wizard-Mount + Aufrufstellen verdrahten**

Im `KlageWizard`-Komponentenrumpf:

```jsx
const [standardtexte, setStandardtexte] = useState(null);
useEffect(() => {
  apiStandardtexte.aufgeloest()
    .then(r => setStandardtexte(r.texte))
    .catch(() => setStandardtexte(null));
}, []);
```

`apiStandardtexte` in den bestehenden api.js-Import aufnehmen. Solange `standardtexte === null`, im Wizard-Kopf einen Hinweis rendern („Standardtexte werden geladen … / konnten nicht geladen werden — Seite neu laden") und die Auto-Text-Berechnungen der Steps 3/7/9 erst ausführen, wenn die Map da ist (Auto-Texte hängen als `useMemo`/Props an `standardtexte`).

Alle Aufrufstellen aktualisieren:

```bash
grep -rn "buildRwVorschau\|buildVerzugAutoText\|buildSachverhaltText" frontend/src --include="*.jsx" --include="*.js"
```

Jede Produktions-Aufrufstelle bekommt `standardtexte` (bzw. `auslandsunfallText: standardtexte?.sachverhalt_auslandsunfall`) durchgereicht; jede Test-Aufrufstelle die Fixture. Erwartete Fundorte: KlageWizard.jsx (Step-Auto-Texte), KlageSection.jsx (Re-Export/Aufrufe), Vitest-Dateien.

- [ ] **Step 5: Volle Vitest-Suite**

```bash
npx vitest run
```

Erwartet: PASS. `KlageWizard.einwaende*`-Tests unverändert grün (EinwaendeAuswahl ist nicht betroffen — Kürzungs-Bausteine laufen weiter über `platzhalterKontext`). Voll-Wizard-Tests, die `api.js` mocken, um `apiStandardtexte.aufgeloest` (Fixture) ergänzen.

- [ ] **Step 6: Browser-Handprobe (Docker-Dev)** — Wizard öffnen: Step 3 mit Auslandsunfall-Haken (Absatz erscheint), Step 7 Würdigungs-Text, Step 9 Verzugs-Text; danach in den Einstellungen `schluss_hinweis` überschreiben, neue Klage-Gesamtvorschau erzeugen → geänderter Schlusssatz erscheint (Paket-3-Kopplung: gleiche Aufbauquelle `baue_klage_vorschau`).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/sections/KlageWizard.jsx frontend/src/sections/KlageSection.jsx frontend/src/sections/KlageWizard.beklagtengrammatik.test.jsx frontend/src/test/standardtexteFixture.js
git commit -m "feat(standardtexte): Klage-Wizard bezieht Stufe-1-Texte via /klage-standardtexte/aufgeloest"
```

(Weitere angepasste Testdateien einzeln mit adden.)

---

### Task 10: Doku + Gesamtverifikation

**Files:**
- Modify: `docs/TODO.md`, `docs/CHANGELOG.md`

- [ ] **Step 1: Backend-Gesamtlauf**

```bash
python -m pytest backend/tests/ --tb=short -q
```

Erwartet: passed ≥ 1241 + neue Tests (≈ +25), failed = exakt die 204 bekannten Alt-Failures (Vergleich gegen Baseline in docs/CHANGELOG.md; jede neue Failure untersuchen).

- [ ] **Step 2: Frontend-Gesamtlauf**

```bash
cd frontend
npx vitest run
```

Erwartet: 362 Bestand + neue Tests, 0 Failures.

- [ ] **Step 3: Doku nachführen**

- `docs/TODO.md`: Punkt 4 der Klage-Wizard-Verbesserungsrunde auf „✅ Stufe 1 umgesetzt (Branch standardtexte-v11)" setzen; neuen Backlog-Punkt „V11 Stufe 2 — Kategorie C über vorflektierte Platzhalter (eigener Plan)" unter „Mittel" ergänzen; Hinweis in der Kürzungstaxonomie-Sektion („V11 kann starten") entfernen.
- `docs/CHANGELOG.md`: Protokoll-Eintrag wie bei Phase 1 (Commits, neue Tabelle/Migration 65, Registry-Datei, Golden-Mechanismus `KLAGE_GOLDEN_UPDATE=1`, Nebenbefund-Fix mit Wortlaut-Änderung, SG-Bausteine wirken auch im Forderungsschreiben).

- [ ] **Step 4: Commit**

```bash
git add docs/TODO.md docs/CHANGELOG.md
git commit -m "docs(standardtexte): V11 Stufe 1 protokolliert, TODO nachgefuehrt"
```

- [ ] **Step 5: Abschluss nach superpowers:finishing-a-development-branch** (Merge-Entscheidung liegt bei RA Schatz; kein Push ohne Freigabe).

---

## Offene Punkte für die Freigabe (bewusste Entscheidungen dieses Plans)

1. **Stufenschnitt:** Dieser Plan liefert Stufe 1 (44 Bausteine A+B). Stufe 2 (Kategorie C) folgt als eigener Plan auf derselben Infrastruktur.
2. **Nebenbefund-Wortlaut:** Bei mehreren Beklagten heißt es künftig „Die Beklagten haben …" (statt Backend „Die Beklagte hat …" bzw. Wizard-Vorschau „Die Beklagte zu 2) hat …"). Das „zu N)"-Suffix entfällt in diesen zwei Sätzen.
3. **SG-Bausteine wirken doppelt:** `sg_text_builder` wird auch vom Forderungsschreiben genutzt — Overrides der Schmerzensgeld-Bausteine ändern beide Dokumente (bewusst: einheitliche Formulierungen).
4. **Alleinhaftungssatz** („Die Beklagtenseite geht von …") ist in der Spec unter Kategorie C gezählt, faktisch aber grammatikneutral — er ist deshalb bereits in Stufe 1 pflegbar.
