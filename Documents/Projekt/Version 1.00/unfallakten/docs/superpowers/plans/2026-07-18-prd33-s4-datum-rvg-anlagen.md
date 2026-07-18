# PRD-33 Session 4 — Datum/RVG/Anlagen (KW-09, KW-10, KW-12, KW-13, KW-08) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die fünf Bugs des Datum/RVG/Anlagen-Clusters aus `docs/BUGFIX_KLAGE_WIZARD.md` beheben: KW-09 (ISO-Datum im Schriftsatz), KW-10 (Verzugsdatum-State-Split + Schreibdatum≠Verzugseintritt), KW-12 (Anlagen-Kollision K1), KW-13 („RVG gerichtlich"-Duplikat), KW-08 (Legacy-Button entfernen, inkl. KW-35-Fallback).

**Architecture:** V5-Datumsvertrag (ISO im Transport, `_fmt_datum`/`fmtDatumDe` nur im Renderer, BE+FE wortgleich), V6-RVG-Bereinigung (nur noch EINE Gebührenberechnung Nr. 2300 auf vorgerichtlichem SW; gerichtlicher SW nur als Zahl), V4-Anlagen-Zähler (fortlaufende K-Nummern in Dokumentreihenfolge, Override-Texte werden auf vorhandene K-Nummern gescannt). Legacy-`generieren()` fliegt komplett raus (Frontend), Backend bleibt für fehlende cfg-Teile tolerant, nutzt aber jetzt das korrekte RVG-Anlagedatum.

**Tech Stack:** Flask/Python (backend/word/klage_service.py, backend/routers/klage_routes.py), React (frontend/src/sections/KlageSection.jsx, KlageWizard.jsx), pytest (DOCX-Direkttest-Muster `test_klage_service_docx.py`), Vitest.

## Global Constraints

- **TDD strikt:** erst fehlschlagender Test (= Verifikation des Funds), dann Fix. Stellt sich ein Fund als falsch heraus → im Tracking-Doc `entfällt` mit Begründung.
- **RA-MICRO read-only.** Keine DB-Migration in dieser Session.
- **Baseline:** Backend voller Lauf 204f/1044p — Failures NUR in bekannten Alt-Clustern (`test_modul2/3/4/7`, `test_sv_portal`, `test_prd27`), **null neue Failures**. Frontend 143 Vitest + `npm run build` grün.
- **Tests IMMER blockierend im Vordergrund ausführen** — NIEMALS `run_in_background`, Timeout bis 600000 ms, volle Suite notfalls in zwei Hälften splitten.
- Backend-Tests: `python -m pytest backend/tests/<datei> -v` aus dem Projektroot `C:\Users\HAL9000\Documents\Projekt\Version 1.00\unfallakten`. Frontend: `npx vitest run` bzw. `npm run build` im Ordner `frontend/`.
- **Git-Wurzel ist das HOME-Verzeichnis** (`C:\Users\HAL9000`), nicht der Projektordner. NIE `git add -A`/`git add .` — immer explizite Pfade relativ zum Projektordner. Branch: `klage-wizard-fixes-s4`.
- Commit-Präfix wie in S1–S3: `fix(klage): KW-NN …` bzw. `test(klage): …`. Jeder Commit endet mit `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- **S3-Erbe nicht beschädigen:** Antrags-Subjekte kommen aus `bek_gram['verurteilt']` etc. — an der Parteibenennung nichts ändern; `gesperrt`-Logik + Warnblöcke in `StepZusammenfassung` (KW-19/23) intakt lassen (durch `KlageWizard.zusammenfassung.test.jsx` abgedeckt). Byte-Pin-Tests aus S3: falls ein Pin-Test einen Satz mit rohem Verzugsdatum fixiert, ist die Anpassung an das neue DD.MM.YYYY-Format beabsichtigt (im Commit vermerken).
- Vertagte Minors (KW-34/36, Rundungs-Helper, hq=0-Guard, AktLeg-Plural-Härtung) NICHT mitfixen.
- Zeilennummern unten: Stand 2026-07-18 auf `main` (Ist-Erhebung). Vor jedem Edit frisch verifizieren.

---

### Task 1: KW-09 Backend — Verzugsdatum an der cfg-Grenze durch `_fmt_datum`

**Files:**
- Modify: `backend/word/klage_service.py:1107` (eine Zeile)
- Test: `backend/tests/test_klage_service_docx.py` (neue Klasse)

**Interfaces:**
- Consumes: `_fmt_datum(iso)` (klage_service.py:1888–1911, ISO→`DD.MM.YYYY`, DE-Passthrough, leerer Input→`""`).
- Produces: `verzugsdatum` (lokale Variable) enthält ab jetzt IMMER das deutsche Format — alle Konsumenten (Z.1108 `zins_sachsch`, Z.1330 Antrag 1, Z.1748–1751 Verzugs-Abschnitt + BEWEIS) sind damit automatisch formatiert. Task 5 baut darauf auf.

- [ ] **Step 1: Fehlschlagenden Test schreiben** — in `test_klage_service_docx.py` ans Dateiende:

```python
class TestKW09VerzugsdatumFormat(unittest.TestCase):
    def _akte_mit_verzug(self, verzugsdatum):
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 700.0)])
        akte_daten["klage_config"]["zinsen_ab"] = "verzug"
        akte_daten["klage_config"]["verzugsdatum"] = verzugsdatum
        return akte_daten

    def test_iso_datum_erscheint_deutsch_in_antrag_und_verzugsabschnitt(self):
        xml = _document_xml(generiere_klageschrift(self._akte_mit_verzug("2026-05-04")))
        self.assertNotIn("2026-05-04", xml)
        self.assertIn("seit dem 04.05.2026 zu zahlen", xml)
        self.assertIn("am 04.05.2026 eingetreten", xml)
        self.assertIn("Schreiben vom 04.05.2026", xml)

    def test_deutsches_datum_bleibt_unveraendert(self):
        xml = _document_xml(generiere_klageschrift(self._akte_mit_verzug("04.05.2026")))
        self.assertIn("seit dem 04.05.2026 zu zahlen", xml)

    def test_ohne_verzugsdatum_bleibt_rechtshaengigkeit(self):
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 700.0)])
        akte_daten["klage_config"]["zinsen_ab"] = "verzug"
        xml = _document_xml(generiere_klageschrift(akte_daten))
        self.assertIn("seit Rechtshängigkeit zu zahlen", xml)
        self.assertIn("Verzug ist mit Rechtshängigkeit eingetreten.", xml)
```

- [ ] **Step 2: Test ausführen — muss fehlschlagen**

Run: `python -m pytest backend/tests/test_klage_service_docx.py::TestKW09VerzugsdatumFormat -v`
Expected: `test_iso_datum_…` FAIL (XML enthält `2026-05-04`), die beiden anderen PASS.

- [ ] **Step 3: Fix** — `klage_service.py:1107`:

```python
    verzugsdatum  = _fmt_datum(cfg.get("verzugsdatum") or "")
```

(vorher: `verzugsdatum  = cfg.get("verzugsdatum") or ""`)

- [ ] **Step 4: Test ausführen — PASS**

Run: `python -m pytest backend/tests/test_klage_service_docx.py -v`
Expected: alle Tests der Datei PASS (auch die 46 Bestandstests — falls ein S3-Pin-Test ein rohes ISO-Datum fixiert, Pin bewusst auf DD.MM.YYYY anpassen und im Commit begründen).

- [ ] **Step 5: Commit**

```bash
git add backend/word/klage_service.py backend/tests/test_klage_service_docx.py
git commit -m "fix(klage): KW-09 BE - Verzugsdatum an cfg-Grenze durch _fmt_datum (V5)"
```

---

### Task 2: KW-09 Frontend — `fmtDatumDe`-Helfer + alle Datums-Anzeige-/Textstellen

**Files:**
- Modify: `frontend/src/config/utils.js` (neuer Export `fmtDatumDe`)
- Modify: `frontend/src/sections/KlageWizard.jsx` (Z.1451–1455 `buildVerzugAutoText`, Z.1574 BEWEIS-Hinweis, Z.1905 `baueAntraegeText`, Z.1972 `StepAntraege`, Z.2080 `StepGebuehren`, Z.1707 `StepZusammenfassung`)
- Modify: `frontend/src/sections/KlageSection.jsx` (Z.479–484 `oeffneWizard`-Verzugstext)
- Test: `frontend/src/config/utils.fmtDatumDe.test.js` (neu), Assertions in `frontend/src/sections/KlageWizard.haftungsquote.test.jsx` NICHT anfassen

**Interfaces:**
- Consumes: Verhalten von `_fmt_datum` (klage_service.py:1888–1911) — vor Implementierung LESEN und exakt spiegeln (wortgleiche BE↔FE-Helfer, S3-Muster).
- Produces: `export function fmtDatumDe(s)` in `frontend/src/config/utils.js` — Task 5 nutzt sie ebenfalls.

- [ ] **Step 1: Fehlschlagenden Test schreiben** — `frontend/src/config/utils.fmtDatumDe.test.js`:

```js
import { describe, it, expect } from "vitest";
import { fmtDatumDe } from "./utils.js";
import { baueAntraegeText } from "../sections/KlageWizard.jsx";

describe("fmtDatumDe (KW-09, wortgleich zu _fmt_datum)", () => {
  it("wandelt ISO in DD.MM.YYYY", () => expect(fmtDatumDe("2026-05-04")).toBe("04.05.2026"));
  it("laesst deutsches Datum unveraendert", () => expect(fmtDatumDe("04.05.2026")).toBe("04.05.2026"));
  it("leer -> leer", () => expect(fmtDatumDe("")).toBe(""));
  it("unbekanntes Format unveraendert", () => expect(fmtDatumDe("unbekannt")).toBe("unbekannt"));
});

describe("baueAntraegeText nutzt fmtDatumDe (KW-09)", () => {
  it("ISO-Verzugsdatum erscheint deutsch im Zinssatz", () => {
    const text = baueAntraegeText({
      positionen: [{ key: "wertminderung", label: "Wertminderung", betrag: 700, checked: true }],
      mitSG: false, sgMind: 0,
      beklagte: [{ rolle_klage: "beklagter", versicherung: "Test AG", checked: true }],
      weiblich: false, zinsenAb: "verzug", verzug: "2026-05-04",
      unfalldatum: "01.02.2026", mitFestSg: false, mitFestSach: false,
    });
    expect(text).toContain("seit dem 04.05.2026");
    expect(text).not.toContain("2026-05-04");
  });
});
```

- [ ] **Step 2: Ausführen — FAIL** (`fmtDatumDe` existiert nicht)

Run: `npx vitest run src/config/utils.fmtDatumDe.test.js` (im Ordner `frontend/`)

- [ ] **Step 3: Implementieren**

(a) `frontend/src/config/utils.js` — nach Lesen von `_fmt_datum` exakt spiegeln; erwartete Form:

```js
// KW-09: wortgleich zu backend/word/klage_service.py::_fmt_datum
export function fmtDatumDe(s) {
  s = String(s ?? "").trim();
  if (!s) return "";
  let m = s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (m) return `${m[3]}.${m[2]}.${m[1]}`;
  m = s.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
  if (m) return `${m[1].padStart(2, "0")}.${m[2].padStart(2, "0")}.${m[3]}`;
  m = s.match(/^(\d{1,2})\.(\d{1,2})\.(\d{2})$/);
  if (m) return `${m[1].padStart(2, "0")}.${m[2].padStart(2, "0")}.20${m[3]}`;
  return s;
}
```

(b) `KlageWizard.jsx` — `fmtDatumDe` aus `../config/utils.js` importieren (neben bestehendem `fmtEuro`-Import) und einsetzen:
- Z.1905: `const zinsDat = zinsenAb === "verzug" && verzug ? \`seit dem ${fmtDatumDe(verzug)}\` : "seit Rechtshängigkeit";`
- Z.1972 (StepAntraege): identisch.
- Z.2080 (StepGebuehren): identisch.
- Z.1707 (StepZusammenfassung): `wert={wizardVerzugDatum ? \`Verzugseintritt ${fmtDatumDe(wizardVerzugDatum)}\` : "Rechtshängigkeit"}`
- Z.1451–1455 `buildVerzugAutoText`: `vDat`/`bDat` je durch `fmtDatumDe(...)` leiten (Semantik-Umbau selbst kommt erst in Task 5):

```js
function buildVerzugAutoText(dokDatum, eintrittDatum) {
  const vDat = fmtDatumDe(eintrittDatum || dokDatum);
  const bDat = fmtDatumDe(dokDatum || eintrittDatum);
  if (!vDat) return "Verzug ist mit Rechtshängigkeit eingetreten.";
  return `Der Verzug ist nach Ablauf der Zahlungsfrist bzw. dem ernsthaften und endgültigen Verweigern der Leistung am ${vDat} eingetreten.\n\nBEWEIS: Schreiben vom ${bDat}`;
}
```

- Z.1574: `→ BEWEIS: Schreiben vom {fmtDatumDe(wizardVerzugDokDatum)}`

(c) `KlageSection.jsx` Z.482–484 (`oeffneWizard`): das eingesetzte Datum durch `fmtDatumDe(verzugDatum)` leiten (Import ergänzen).

- [ ] **Step 4: Ausführen — PASS + volle Frontend-Suite**

Run: `npx vitest run` → 143 + 5 neue grün; `npm run build` grün.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/config/utils.js frontend/src/config/utils.fmtDatumDe.test.js frontend/src/sections/KlageWizard.jsx frontend/src/sections/KlageSection.jsx
git commit -m "fix(klage): KW-09 FE - fmtDatumDe-Helfer, alle Verzugs-/Zins-Datumsstellen deutsch (V5)"
```

---

### Task 3: KW-08 Frontend — Legacy-Button + `generieren()` entfernen

**Files:**
- Modify: `frontend/src/sections/KlageSection.jsx` (Z.373–397 `generieren`-Funktion; Z.991–1011 grauer Button rechte Kachel; Z.1401–1421 grauer Button untere Kachel)

**Interfaces:**
- Consumes: —
- Produces: `apiKlage.generieren` wird nur noch von `wizardGenerieren()` aufgerufen. States `rvgData`/`rvgOverride`/`verzug` bleiben in diesem Task unangetastet (Aufräumen in Task 5/6).

**ENTSCHEIDUNG (RA Schatz, 2026-07-17, Tracking-Doc):** Legacy-Button entfernen — der Wizard ist der einzige Weg.

- [ ] **Step 1: Verifikation vorab (Ersatz für fehlschlagenden Test bei reiner Entfernung):**

Run: `grep -n "veraltet" frontend/src/sections/KlageSection.jsx`
Expected: 4 Treffer (2× title, 2× Label) — dokumentiert den Ist-Zustand.

- [ ] **Step 2: Entfernen**
- `generieren`-Funktion Z.373–397 komplett löschen.
- Buttons Z.991–1011 und Z.1401–1421 komplett löschen (die 🧙-Wizard-Buttons davor Z.984–990 bzw. Z.1393–1400 bleiben; beim unteren zusätzlich `marginRight:10` im Wizard-Button-Style entfernen, damit kein Randabstand zum gelöschten Nachbarn übrigbleibt).
- Prüfen, ob `generiert_laedt` (`genLaedt`) noch von `wizardGenerieren` genutzt wird → bleibt.

- [ ] **Step 3: Verifizieren**

Run: `grep -cn "veraltet" frontend/src/sections/KlageSection.jsx` → 0 Treffer; `grep -n "const generieren" frontend/src/sections/KlageSection.jsx` → 0 Treffer.
Run: `npx vitest run` → grün; `npm run build` → grün.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/sections/KlageSection.jsx
git commit -m "fix(klage): KW-08 FE - Legacy-Generieren-Button + generieren() entfernt, Wizard ist einziger Weg"
```

---

### Task 4: KW-08/KW-35 Backend — RVG-Anlagedatum durchreichen + ValueError-Logging

**Files:**
- Modify: `backend/routers/klage_routes.py` (Z.1307–1311 `akte_daten["akte"]`, Z.1383–1384 `except ValueError`)
- Modify: `backend/word/klage_service.py:1099` (`akte_erstellt_am`)
- Test: `backend/tests/test_klage_service_docx.py` (neue Klasse), `backend/tests/test_klage_kw18_route.py` (Log-Assertion)

**Interfaces:**
- Consumes: `_rvg_anlagedatum(az, sqlite_erstellt_am)` (klage_routes.py:49–86); `berechne_rvg(streitwert, faktor=1.3, erstellt_am=None)` (klage_service.py:162–207).
- Produces: `akte_daten["akte"]["rvg_anlagedatum"]` (ISO-String) — der `berechne_rvg`-Fallback im Service nutzt ihn statt des SQLite-Importdatums. Damit ist KW-35 behoben (der Legacy-Aufrufer ist seit Task 3 weg, der Fallback selbst bleibt als Robustheit, jetzt mit korrektem Datum).

- [ ] **Step 1: Fehlschlagenden Service-Test schreiben** — `test_klage_service_docx.py`:

```python
from backend.word.klage_service import berechne_rvg

class TestKW35RvgAnlagedatumFallback(unittest.TestCase):
    def test_fallback_nutzt_rvg_anlagedatum_statt_erstellt_am(self):
        # Akte 2024 angelegt (alter RVG-Tarif), aber erst 2026 in SQLite importiert.
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 700.0)])
        akte_daten["akte"]["erstellt_am"] = "2026-01-01"
        akte_daten["akte"]["rvg_anlagedatum"] = "2024-06-01"
        # kein cfg["rvg"], kein cfg["rvg_ausserg"] -> berechne_rvg-Fallback greift
        xml = _document_xml(generiere_klageschrift(akte_daten))
        erwartet_alt  = berechne_rvg(700.0, erstellt_am="2024-06-01")["gesamt"]
        erwartet_neu  = berechne_rvg(700.0, erstellt_am="2026-01-01")["gesamt"]
        self.assertNotEqual(erwartet_alt, erwartet_neu,
                            "Testaufbau: Tarife 2021/2025 muessen sich beim gewaehlten Streitwert unterscheiden")
        alt_str = f"{erwartet_alt:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        neu_str = f"{erwartet_neu:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        self.assertIn(alt_str, xml)
        self.assertNotIn(neu_str, xml)
```

(Falls sich die beiden Tarife beim Streitwert 700 € NICHT unterscheiden, im Test einen Streitwert wählen, bei dem sie es tun — per `berechne_rvg`-Aufruf im Python-REPL prüfen.)

- [ ] **Step 2: Ausführen — FAIL** (`rvg_anlagedatum` wird ignoriert, neuer Tarif erscheint)

Run: `python -m pytest backend/tests/test_klage_service_docx.py::TestKW35RvgAnlagedatumFallback -v`

- [ ] **Step 3: Implementieren**

(a) `klage_service.py:1099`:

```python
    akte_erstellt_am = akte.get("rvg_anlagedatum") or akte.get("erstellt_am")
```

(b) `klage_routes.py` in `generiere_klage`, im `akte_daten["akte"]`-Dict (Z.1307–1311), Zeile ergänzen (dieselbe `az`-Quelle wie `aktenzeichen` im selben Dict verwenden):

```python
            "erstellt_am":  akte.erstellt_am,
            "rvg_anlagedatum": _rvg_anlagedatum(az, akte.erstellt_am),
```

(c) `klage_routes.py` Z.1383–1384, Logging ergänzen:

```python
    except ValueError as e:
        logger.warning("Klage-Generierung abgelehnt (422): %s", e)
        return _err(str(e), 422)
```

- [ ] **Step 4: Route-Log-Test ergänzen** — in `test_klage_kw18_route.py` im bestehenden 422-Test (oder als neuer Test daneben) die Log-Zeile mitprüfen:

```python
        with self.assertLogs("backend.routers.klage_routes", level="WARNING") as logs:
            resp = ...  # bestehender 422-Aufruf
        self.assertTrue(any("Klage-Generierung abgelehnt" in z for z in logs.output))
```

(An den vorhandenen Harness anpassen — Login/Client wie im Bestandstest; JSON-Fehler-Key ist `"fehler"`, nicht `"error"`.)

- [ ] **Step 5: Ausführen — PASS**

Run: `python -m pytest backend/tests/test_klage_service_docx.py backend/tests/test_klage_kw18_route.py backend/tests/test_klage_overrides_merge.py -v`

- [ ] **Step 6: Commit**

```bash
git add backend/word/klage_service.py backend/routers/klage_routes.py backend/tests/test_klage_service_docx.py backend/tests/test_klage_kw18_route.py
git commit -m "fix(klage): KW-35 RVG-Fallback nutzt _rvg_anlagedatum; KW-08 BE-Teil + 422-Logging (S3-Follow-up)"
```

---

### Task 5: KW-10 — EIN Verzugs-State, Schreibdatum ≠ Verzugseintritt (BE+FE)

**Files:**
- Modify: `backend/word/klage_service.py:1746–1751` (Verzugs-Abschnitt)
- Modify: `frontend/src/sections/KlageSection.jsx` (Z.163 `verzug`-State entfernen; Z.214–217 Init; Z.479–484 `oeffneWizard`; Z.551 `wizardGenerieren`-cfg; Z.1254–1255 Kachel-5-Felder; Wizard-Props Z.~631/649)
- Modify: `frontend/src/sections/KlageWizard.jsx` (Z.1451–1456 `buildVerzugAutoText` exportieren + Semantik; Z.2543 Step-6-Prop; Z.2592 Step-9-Prop)
- Modify: `frontend/src/config/utils.js` (neuer Export `verzugEintrittDefault`)
- Test: `backend/tests/test_klage_service_docx.py`, `frontend/src/sections/KlageWizard.verzug.test.jsx` (neu)

**Interfaces:**
- Consumes: `fmtDatumDe` aus Task 2; `wizardVerzugManuell`-Muster (PRD-35) bleibt unverändert.
- Produces: cfg-Vertrag NEU: `verzugsdatum` = **Verzugseintritt**, `verzug_schreiben_datum` = **Schreibdatum des Forderungsschreibens** (beide über `klage_config`, kein Router-Merge nötig — `klage_config` wird 1:1 durchgereicht). FE-SSOT: `wizardVerzugDatum` (Eintritt) + `wizardVerzugDokDatum` (Schreibdatum); der Alt-State `verzug` existiert nicht mehr. `export function buildVerzugAutoText(dokDatum, eintrittDatum)`; `export function verzugEintrittDefault(schreibDatum)` in utils.js.

**ENTSCHEIDUNGS-NOTIZ (dem Nutzer im Abschlussbericht vorlegen):** Der Verzugseintritt wird mit **Schreibdatum + 14 Tage** vorbelegt (Kanzlei-Standardfrist, vgl. `stellungnahme_service.py:323` „innerhalb von 14 Tagen"; editierbar in Kachel 5 und Step 8). Ohne Eintrittsdatum → „Verzug ist mit Rechtshängigkeit eingetreten." (deckt sich mit dem bestehenden Step-8-Hinweis „leer = Rechtshängigkeit").

- [ ] **Step 1: Fehlschlagenden Backend-Test schreiben** — `test_klage_service_docx.py`:

```python
class TestKW10SchreibdatumGetrennt(unittest.TestCase):
    def test_beweis_nutzt_schreibdatum_eintritt_bleibt_verzugsdatum(self):
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 700.0)])
        akte_daten["klage_config"]["zinsen_ab"] = "verzug"
        akte_daten["klage_config"]["verzugsdatum"] = "2026-05-19"
        akte_daten["klage_config"]["verzug_schreiben_datum"] = "2026-05-04"
        xml = _document_xml(generiere_klageschrift(akte_daten))
        self.assertIn("am 19.05.2026 eingetreten", xml)
        self.assertIn("Schreiben vom 04.05.2026", xml)
        self.assertNotIn("Schreiben vom 19.05.2026", xml)

    def test_ohne_schreiben_datum_faellt_beweis_auf_verzugsdatum_zurueck(self):
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 700.0)])
        akte_daten["klage_config"]["zinsen_ab"] = "verzug"
        akte_daten["klage_config"]["verzugsdatum"] = "2026-05-19"
        xml = _document_xml(generiere_klageschrift(akte_daten))
        self.assertIn("Schreiben vom 19.05.2026", xml)
```

- [ ] **Step 2: Ausführen — Test 1 FAIL, Test 2 PASS**

Run: `python -m pytest backend/tests/test_klage_service_docx.py::TestKW10SchreibdatumGetrennt -v`

- [ ] **Step 3: Backend-Fix** — `klage_service.py`: bei den Zins-Variablen (nach Z.1107) ergänzen und im Verzugs-Abschnitt nutzen:

```python
    verzug_schreiben = _fmt_datum(cfg.get("verzug_schreiben_datum") or "") or verzugsdatum
```

und Z.1751: `verzug_xml += _beweis(f"Schreiben vom {verzug_schreiben}")`

- [ ] **Step 4: Backend-Test PASS**, dann **fehlschlagenden Frontend-Test schreiben** — `frontend/src/sections/KlageWizard.verzug.test.jsx`:

```js
import { describe, it, expect } from "vitest";
import { buildVerzugAutoText } from "./KlageWizard.jsx";
import { verzugEintrittDefault } from "../config/utils.js";

describe("buildVerzugAutoText (KW-10)", () => {
  it("nutzt Eintritt fuer den Eintrittssatz und Schreibdatum fuer den BEWEIS", () => {
    const t = buildVerzugAutoText("04.05.2026", "19.05.2026");
    expect(t).toContain("am 19.05.2026 eingetreten");
    expect(t).toContain("BEWEIS: Schreiben vom 04.05.2026");
  });
  it("ohne Eintritt -> Rechtshaengigkeit (Schreibdatum behauptet KEINEN Eintritt mehr)", () => {
    expect(buildVerzugAutoText("04.05.2026", "")).toBe("Verzug ist mit Rechtshängigkeit eingetreten.");
  });
  it("mit Eintritt, ohne Schreibdatum -> kein BEWEIS-Satz", () => {
    const t = buildVerzugAutoText("", "19.05.2026");
    expect(t).toContain("am 19.05.2026 eingetreten");
    expect(t).not.toContain("BEWEIS");
  });
});

describe("verzugEintrittDefault (KW-10)", () => {
  it("Schreibdatum + 14 Tage", () => expect(verzugEintrittDefault("04.05.2026")).toBe("18.05.2026"));
  it("ISO-Input wird verarbeitet", () => expect(verzugEintrittDefault("2026-05-04")).toBe("18.05.2026"));
  it("Monatsuebergang", () => expect(verzugEintrittDefault("20.12.2026")).toBe("03.01.2027"));
  it("leer -> leer", () => expect(verzugEintrittDefault("")).toBe(""));
});
```

- [ ] **Step 5: Frontend implementieren**

(a) `utils.js`:

```js
// KW-10: Vorbelegung Verzugseintritt = Schreibdatum + 14 Tage (Kanzlei-Standardfrist)
export function verzugEintrittDefault(schreibDatum) {
  const de = fmtDatumDe(schreibDatum);
  const m = de.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
  if (!m) return "";
  const d = new Date(Date.UTC(+m[3], +m[2] - 1, +m[1] + 14));
  return `${String(d.getUTCDate()).padStart(2, "0")}.${String(d.getUTCMonth() + 1).padStart(2, "0")}.${d.getUTCFullYear()}`;
}
```

(b) `KlageWizard.jsx` — `buildVerzugAutoText` exportieren + neue Semantik (kein Eintritts-Fallback aufs Schreibdatum mehr):

```js
export function buildVerzugAutoText(dokDatum, eintrittDatum) {
  const vDat = fmtDatumDe(eintrittDatum);
  const bDat = fmtDatumDe(dokDatum);
  if (!vDat) return "Verzug ist mit Rechtshängigkeit eingetreten.";
  const basis = `Der Verzug ist nach Ablauf der Zahlungsfrist bzw. dem ernsthaften und endgültigen Verweigern der Leistung am ${vDat} eingetreten.`;
  return bDat ? `${basis}\n\nBEWEIS: Schreiben vom ${bDat}` : basis;
}
```

(c) `KlageWizard.jsx` Props: Z.2543 `verzug={wizardVerzugDatum}` (statt `wizardVerzugDatum || verzug`); Z.2592 `verzug={wizardVerzugDatum}` (statt `verzug`). Die Section-Prop `verzug` an `KlageWizard` (KlageSection Z.~649) entfällt — Prop-Signatur der `KlageWizard`-Hauptkomponente entsprechend bereinigen.

(d) `KlageSection.jsx`:
- Z.163 `const [verzug, setVerzug] = useState("");` löschen; ALLE verbleibenden `verzug`-/`setVerzug`-Referenzen bereinigen (`grep -n "\bverzug\b\|setVerzug" frontend/src/sections/KlageSection.jsx` — `verzugDokListe`/`verzugDokId`/`wizardVerzug*` bleiben!).
- Z.214–217 Init: `setVerzug(initVerzug);` löschen; stattdessen

```js
        setWizardVerzugDokDatum(initVerzug);
        setWizardVerzugDatum(verzugEintrittDefault(initVerzug));
```

- Z.1254–1255 (Kachel 5): die beiden `setVerzug(v)`-Aufrufe entfernen (`set: v => setWizardVerzugDokDatum(v)` bzw. `set: v => setWizardVerzugDatum(v)`).
- Z.479–484 (`oeffneWizard`): auf die zwei States + exportierten Builder umstellen:

```js
    const dok = wizardVerzugDokDatum || "";
    const ein = wizardVerzugDatum || "";
    setWizardVerzugText(buildVerzugAutoText(dok, ein));
    setWizardVerzugManuell(false);
```

(`buildVerzugAutoText` aus `KlageWizard.jsx` importieren; der bisherige `verzug`-Fallback und die If-Guards Z.480–481 entfallen — die Init in Z.214–217 hat beide States bereits befüllt.)
- Z.551 (`wizardGenerieren`):

```js
        verzugsdatum:           zinsenAb === "verzug" ? (wizardVerzugDatum || null) : null,
        verzug_schreiben_datum: wizardVerzugDokDatum || null,
```

- [ ] **Step 6: Ausführen — PASS**

Run: `npx vitest run` (alle, inkl. neuer Datei) + `npm run build`; `python -m pytest backend/tests/test_klage_service_docx.py -v`.

- [ ] **Step 7: Commit**

```bash
git add backend/word/klage_service.py backend/tests/test_klage_service_docx.py frontend/src/config/utils.js frontend/src/sections/KlageSection.jsx frontend/src/sections/KlageWizard.jsx frontend/src/sections/KlageWizard.verzug.test.jsx frontend/src/config/utils.fmtDatumDe.test.js
git commit -m "fix(klage): KW-10 - ein Verzugs-State (Eintritt+Schreibdatum getrennt), cfg verzug_schreiben_datum, Eintritt-Default +14 Tage"
```

---

### Task 6: KW-13 — „RVG gerichtlich"-Duplikat entfernen, `rvg_override` weg

**Files:**
- Modify: `frontend/src/sections/KlageSection.jsx` (Z.166 `rvgOverride`, Z.569 `rvgGesamt`, Z.1300–1301 SW-Hint, Z.1352–1362 Override-Feld, Z.1380 Fußzeile, `wizardGenerieren` Z.553–554, Wizard-Props)
- Modify: `frontend/src/sections/KlageWizard.jsx` (StepVerzug Z.1458–1464 + RVG-Anzeige Z.~1621; StepZusammenfassung Z.1645–1656 + Z.1713; Aufrufstellen Z.2569, Z.2603)
- Modify: `backend/word/klage_service.py:1098–1103` (`rvg_override` entfernen)
- Test: `frontend/src/sections/KlageWizard.zusammenfassung.test.jsx` (erweitern), `backend/tests/test_klage_service_docx.py`

**Interfaces:**
- Consumes: `wizardRvgAussergData`/`wizardRvgAussergOv` (Nr. 2300 auf `swAussergEffektiv`) — bleibt die EINZIGE Gebührenberechnung; `berechneKlagebetrag` liefert den gerichtlichen Streitwert-Anteil.
- Produces: cfg enthält keine Keys `rvg`/`rvg_override` mehr (Backend: `rvg_override` wird nicht mehr gelesen; `cfg.get("rvg")` bleibt als toleranter Alt-Key, greift aber nie mehr aus dem Wizard). `StepVerzug` ohne `rvgData`/`rvgOverride`-Props; `StepZusammenfassung` ohne `rvgData`/`rvgOverride`-Props, zeigt stattdessen „Gerichtlicher Streitwert"-Zeile. `rvgData`-State in KlageSection bleibt NUR für die Kachel-6-Anzeige (Nr. 2300, korrekt beschriftet).

**ENTSCHEIDUNG (RA Schatz, 2026-07-17, Tracking-Doc):** Keine gerichtliche Gebührenberechnung. Gerichtlicher Streitwert nur als Zahl/Gegenstandswert; Anzeige-Duplikat `rvgData` unter dem Label „RVG gerichtlich" entfernen; wirkungsloses `rvg_override` entfernen.

- [ ] **Step 1: Fehlschlagenden Frontend-Test schreiben** — in `KlageWizard.zusammenfassung.test.jsx` ergänzen (Render-Harness der Datei wiederverwenden):

```jsx
it("KW-13: zeigt gerichtlichen Streitwert als Zahl statt 'RVG gerichtlich'", () => {
  render(<StepZusammenfassung {...basisProps()} />);
  expect(screen.queryByText(/RVG gerichtlich/)).toBeNull();
  expect(screen.getByText(/Gerichtlicher Streitwert/)).toBeTruthy();
  expect(screen.getByText(/RVG außergerichtlich/)).toBeTruthy();
});
```

(`basisProps()` = das in der Datei etablierte Prop-Fixture; `rvgData`/`rvgOverride` daraus entfernen.)

- [ ] **Step 2: Ausführen — FAIL** (`RVG gerichtlich` wird gerendert)

Run: `npx vitest run src/sections/KlageWizard.zusammenfassung.test.jsx`

- [ ] **Step 3: Implementieren**

(a) `KlageWizard.jsx` — `StepZusammenfassung`:
- Props `rvgData, rvgOverride` aus der Signatur (Z.1646) und der Aufrufstelle (Z.2603) entfernen; Z.1654 `rvgGesamt` löschen.
- Z.1713 ersetzen:

```jsx
        <ZeileZusammenfassung icon="⚖" label="Gerichtlicher Streitwert (Gegenstandswert)"
          wert={fmtEuro(swGerichtlich)} />
        <ZeileZusammenfassung icon="💶" label={`Nr. 2300 VV RVG außergerichtlich (SW: ${fmtEuro(swAusserg || 0)})`}
          wert={rvgAussGes > 0 ? fmtEuro(rvgAussGes) : "–"} warn={rvgAussGes === 0} />
```

(Die bestehende `RVG außergerichtlich`-Zeile Z.1714–1715 geht in dieser neuen Zeile auf. `gesperrt`-Logik Z.1662–1669 und alle Warnblöcke UNVERÄNDERT lassen.)

(b) `KlageWizard.jsx` — `StepVerzug`: Props `rvgData, rvgOverride` (Z.1458) und `rvgGesamt` (Z.1464) entfernen; die RVG-Anzeigezeile in Step 8 (Umgebung Z.1621, `RVG: {fmtEuro(rvgGesamt)}`) ersatzlos streichen (Gebühren haben ihren Platz in Step 9/10); Aufrufstelle Z.2569 bereinigen.

(c) `KlageSection.jsx`:
- Z.166 `rvgOverride`-State + Override-Feld-Block Z.1352–1362 löschen; Z.569 `rvgGesamt` = `(wizardRvgAussergData?.gesamt ?? rvgData?.gesamt) || 0` (nur noch für die Fußzeile Z.1380, Label dort in „Nr. 2300 außergerichtl. {fmtEuro(rvgGesamt)} als Nebenforderung" ändern).
- `wizardGenerieren` Z.553–554: die Zeilen `rvg: rvgData,` und `rvg_override: …` ersatzlos löschen.
- Kachel-6-SW-Hint Z.1300–1301: `hint:"Basis für gerichtliche RVG-Gebühr"` → `hint:"Gegenstandswert der Klage (Gebühren folgen im Kostenfestsetzungsverfahren)"`.
- Wizard-Props: `rvgData={rvgData}`/`rvgOverride={rvgOverride}` an `<KlageWizard/>` entfernen (Signatur der Hauptkomponente mitziehen).

(d) `klage_service.py` Z.1098–1103: `rvg_override`-Zeilen entfernen:

```python
    akte_erstellt_am = akte.get("rvg_anlagedatum") or akte.get("erstellt_am")
    rvg              = cfg.get("rvg") or berechne_rvg(klagebetrag,
                                                       erstellt_am=akte_erstellt_am)
```

- [ ] **Step 4: Backend-Regressionstest ergänzen** — `test_klage_service_docx.py`:

```python
class TestKW13RvgOverrideEntfernt(unittest.TestCase):
    def test_rvg_override_wird_ignoriert_rvg_ausserg_gilt(self):
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 700.0)])
        akte_daten["klage_config"]["rvg_override"] = 9999.99
        akte_daten["klage_config"]["rvg_ausserg"] = {"gesamt": 159.94, "streitwert": 700.0,
                                                     "faktor": 1.3, "gebuehr_netto": 114.4,
                                                     "post_pauschale": 20.0, "zwischen_netto": 134.4,
                                                     "ust": 25.54}
        xml = _document_xml(generiere_klageschrift(akte_daten))
        self.assertNotIn("9.999,99", xml)
        self.assertIn("159,94", xml)
```

- [ ] **Step 5: Ausführen — alles PASS**

Run: `npx vitest run` + `npm run build`; `python -m pytest backend/tests/test_klage_service_docx.py -v`.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/sections/KlageSection.jsx frontend/src/sections/KlageWizard.jsx frontend/src/sections/KlageWizard.zusammenfassung.test.jsx backend/word/klage_service.py backend/tests/test_klage_service_docx.py
git commit -m "fix(klage): KW-13 - 'RVG gerichtlich'-Duplikat + rvg_override entfernt, gerichtl. SW nur als Zahl (V6)"
```

---

### Task 7: KW-12 — Anlagen-Zähler: fortlaufende K-Nummern (V4)

**Files:**
- Modify: `backend/word/klage_service.py` (neuer `AnlagenZaehler` + `_max_anlagen_nr`; `get_aktivlegitimation_text` Z.486/494; `_build_aktivlegitimation_xml` Z.793–825 + Aufrufe Z.1463/1469; Schaden-BEWEIS Z.1613; SG-Aufruf Z.1719–1730)
- Modify: `backend/word/sg_text_builder.py:42–54` (`baue_sg_abschnitt` Param `anlage_nr="K 2"`)
- Modify: `frontend/src/sections/KlageWizard.jsx:113/118` (Schreibweise „Anlage K 1")
- Test: `backend/tests/test_klage_service_docx.py` (neue Klasse), `backend/tests/test_klage_partei_grammatik.py` (sg_text_builder-Default-Pin)

**Interfaces:**
- Consumes: Dokumentreihenfolge = Code-Baureihenfolge in `generiere_klageschrift`: Aktivlegitimation (Z.1463/1469) → Schaden (Z.1613) → Schmerzensgeld (Z.1719–1730). VOR Implementierung an der Vorlagen-Platzhalterreihenfolge verifizieren (`{{AKTIVLEGITIMATION}}` vor `{{SCHADEN}}` vor `{{SCHMERZENSGELD}}` in `klagevorlage.docx`/document.xml).
- Produces:

```python
_ANLAGE_RE = re.compile(r"Anlage K ?(\d+)")

def _max_anlagen_nr(*texte) -> int:
    """Hoechste in Override-Texten bereits vergebene K-Nummer (0 wenn keine)."""
    nums = [int(m) for t in texte if t for m in _ANLAGE_RE.findall(t)]
    return max(nums) if nums else 0

class AnlagenZaehler:
    def __init__(self, start: int = 0):
        self._n = start
    def naechste(self) -> str:
        self._n += 1
        return f"K {self._n}"
```

`get_aktivlegitimation_text(details, kl_einf, anrede, anlage_nr="K 1")` (neuer optionaler Param, Default vereinheitlicht die Schreibweise auf „K 1" mit Leerzeichen); `_build_aktivlegitimation_xml(details, kl_einf, anrede, text_override=None, anlage_nr="K 1")`; `baue_sg_abschnitt(ps_data, kl_nom, sg_mind, verb_hat="hat", anlage_nr="K 2")` (Default → Forderungsschreiben-Pfad byte-gleich).

- [ ] **Step 1: Fehlschlagende Tests schreiben** — `test_klage_service_docx.py`:

```python
class TestKW12AnlagenNummern(unittest.TestCase):
    def _mit_aktivleg(self, akte_daten, typ="finanziert", freigabe="freigabe"):
        akte_daten["unfalldetails"]["aktivlegitimation_typ"] = typ
        akte_daten["unfalldetails"]["aktivlegitimation_freigabe"] = freigabe
        akte_daten["unfalldetails"]["aktivlegitimation_datum"] = "01.03.2026"
        return akte_daten

    def test_eigentum_gutachten_k1_sg_k2(self):
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 700.0)],
                                  mit_schmerzensgeld=True, schmerzensgeld_mindest=1000.0)
        xml = _document_xml(generiere_klageschrift(akte_daten))
        self.assertIn("Schadengutachten (Anlage K 1)", xml)
        self.assertIn("(Anlage K 2)", xml)          # Atteste
        self.assertNotIn("Anlage K 3", xml)

    def test_finanziert_freigabe_k1_gutachten_k2_sg_k3(self):
        akte_daten = self._mit_aktivleg(
            _akte_daten([_position("wertminderung", "Wertminderung", 700.0)],
                        mit_schmerzensgeld=True, schmerzensgeld_mindest=1000.0))
        xml = _document_xml(generiere_klageschrift(akte_daten))
        self.assertIn("Freigabeerklärung vom 01.03.2026, Anlage K 1", xml)
        self.assertIn("Schadengutachten (Anlage K 2)", xml)
        self.assertIn("(Anlage K 3)", xml)          # Atteste
        self.assertNotIn("Anlage K1", xml)          # alte Schreibweise weg

    def test_sachverhalt_override_mit_k1_verschiebt_gutachten_auf_k2(self):
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 700.0)])
        akte_daten["unfalldetails"]["sachverhalt_override"] = (
            "Das Fahrzeug ist finanziert.\n\nBEWEIS:\tFreigabeerklärung vom 01.03.2026, Anlage K 1\n")
        xml = _document_xml(generiere_klageschrift(akte_daten))
        self.assertIn("Schadengutachten (Anlage K 2)", xml)
```

(Die exakten `unfalldetails`-Keys für den Auto-AktLeg-Pfad und den `sachverhalt_override` VOR dem Schreiben an Z.1382–1469 verifizieren und die Fixtures entsprechend setzen.)

In `test_klage_partei_grammatik.py` (Pin für den Forderungsschreiben-Pfad):

```python
def test_kw12_sg_builder_default_anlage_bleibt_k2(self):
    absaetze, beweis, _vgl = baue_sg_abschnitt(None, "Die Klägerin", 0.0)
    self.assertTrue(beweis.endswith("(Anlage K 2)"))
```

- [ ] **Step 2: Ausführen — FAIL** (heute: AktLeg „Anlage K1" UND Gutachten „Anlage K 1" kollidieren; SG hart „K 2")

Run: `python -m pytest backend/tests/test_klage_service_docx.py::TestKW12AnlagenNummern backend/tests/test_klage_partei_grammatik.py -v`

- [ ] **Step 3: Implementieren**

(a) `klage_service.py`: `_ANLAGE_RE`/`_max_anlagen_nr`/`AnlagenZaehler` wie oben einfügen (bei den anderen Helfern).

(b) `get_aktivlegitimation_text(…, anlage_nr="K 1")`: Z.486 → `f"\n\nBEWEIS:\tFreigabeerklärung vom {datum}, Anlage {anlage_nr}\n"`; Z.494 → `f"\n\nBEWEIS:\t{bedingungstyp} in Kopie, Anlage {anlage_nr}\n"`. `_build_aktivlegitimation_xml` reicht `anlage_nr` durch (bei `text_override` wird KEINE Nummer verbraucht — der Override trägt seine eigenen).

(c) In `generiere_klageschrift`, vor dem Einleitungs-/AktLeg-Block:

```python
    anlagen = AnlagenZaehler(start=_max_anlagen_nr(
        sachverhalt_override, antraege_override,
        cfg.get("rw_text_override") or details.get("rw_text_override"),
        verzug_text_override,
    ))
```

(Die tatsächlichen lokalen Variablennamen der vier Override-Texte an Ort und Stelle verwenden.) Aufrufe Z.1463/1469: nur im Auto-Pfad und nur wenn der AktLeg-Text eine Anlage referenziert (typ ≠ eigentum, Fall C–F) `anlage_nr=anlagen.naechste()` übergeben — die Nummer darf NICHT verbraucht werden, wenn kein Anlagen-BEWEIS entsteht (typ „eigentum" erzeugt keinen). Z.1613 → `schaden_xml += _beweis(f"Schadengutachten (Anlage {anlagen.naechste()})")`. SG-Aufruf (Z.1719–1730) → `baue_sg_abschnitt(…, anlage_nr=anlagen.naechste())`, aber NUR wenn `mit_sg` (sonst keine Nummer verbrauchen — Aufruf steht bereits im `mit_sg`-Zweig, verifizieren).

(d) `sg_text_builder.py:42/54`: Signatur `def baue_sg_abschnitt(ps_data, kl_nom, sg_mind, verb_hat="hat", anlage_nr="K 2"):`, Z.54 → `beweis = f"BEWEIS: Ärztliche Atteste und Befundberichte (Anlage {anlage_nr})"`. Docstring ergänzen.

(e) `KlageWizard.jsx` Z.113/118: `Anlage K1` → `Anlage K 1` (Frontend-Vorschau = Override-Text; der Backend-Scan `_max_anlagen_nr` erkennt beide Schreibweisen, die Vorschau wird auf die kanonische vereinheitlicht).

- [ ] **Step 4: Ausführen — PASS + Gesamtdatei**

Run: `python -m pytest backend/tests/test_klage_service_docx.py backend/tests/test_klage_partei_grammatik.py -v` (alle grün; Bestandstests, die „Anlage K1" pinnen, auf „K 1" anpassen — bewusste Schreibweisen-Vereinheitlichung). `npx vitest run` + `npm run build` grün.

- [ ] **Step 5: Commit**

```bash
git add backend/word/klage_service.py backend/word/sg_text_builder.py backend/tests/test_klage_service_docx.py backend/tests/test_klage_partei_grammatik.py frontend/src/sections/KlageWizard.jsx
git commit -m "fix(klage): KW-12 - AnlagenZaehler vergibt fortlaufende K-Nummern, Override-Scan, Schreibweise 'K n' (V4)"
```

---

### Task 8: Abschluss — Baseline, Doku, Review

**Files:**
- Modify: `docs/BUGFIX_KLAGE_WIZARD.md` (KW-08/09/10/12/13/35 abhaken: `[x]` + Commit-Hashes + Umsetzungs-Notiz; Status-Tabelle; Session-Tabelle Zeile 4)
- Modify: `docs/TODO.md` (Abschnitt „AKTIV — NÄCHSTE SCHRITTE": Session 4 ✅ mit Kurzzusammenfassung, Sessions 5–6 offen)
- Create: `handover/naechste_session_PRD33_S5_prompt.md` (nach Muster S4-Prompt: KW-22/24–29, V7 Dirty-Tracking, aktualisierte Baseline + Wechselwirkungen aus S4)

- [ ] **Step 1: Volle Backend-Suite** — `python -m pytest backend/tests -q` (Vordergrund, Timeout 600000 ms, notfalls in zwei Hälften). Expected: Failures NUR in bekannten Alt-Clustern (204f-Niveau), null neue.
- [ ] **Step 2: Volle Frontend-Suite + Build** — `npx vitest run` und `npm run build` in `frontend/`. Expected: 143 + neue Tests grün, Build grün.
- [ ] **Step 3: Tracking-Doc + TODO.md + S5-Handover aktualisieren** (Commit-Hashes aus `git log --oneline main..klage-wizard-fixes-s4`).
- [ ] **Step 4: Commit Doku**

```bash
git add docs/BUGFIX_KLAGE_WIZARD.md docs/TODO.md handover/naechste_session_PRD33_S5_prompt.md
git commit -m "docs(klage): PRD-33 Session 4 abgehakt (KW-08/09/10/12/13/35), S5-Handover"
```

- [ ] **Step 5: Abschluss-Review** (Opus, Whole-Branch `main..klage-wizard-fixes-s4`) via superpowers:requesting-code-review; Findings fixen (Fix-Wave-Commits), Re-Review bis READY.
- [ ] **Step 6: STOPP — FF-Merge nach `main` NUR nach ausdrücklicher Freigabe durch RA Schatz.** Nicht pushen.
