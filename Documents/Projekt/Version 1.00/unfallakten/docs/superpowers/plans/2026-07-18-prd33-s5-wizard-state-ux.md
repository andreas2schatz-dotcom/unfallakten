# PRD-33 Session 5 — Wizard-State/UX (KW-22, KW-24–KW-29) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die sieben Wizard-State/UX-Bugs KW-22, KW-24, KW-25, KW-26, KW-27, KW-28, KW-29 beheben — mit V7 (zentrales Dirty-Tracking/Manuell-Flags im Section-State) als gemeinsamem Muster.

**Architecture:** Frontend: Manuell-Flags und Generierungs-Basis („Dirty-Tracking") werden aus lokalen Refs/Effects in den KlageSection-State gehoben (Vorlage: `wizardVerzugManuell`); der Gebühren-Antrag wird nicht mehr per String-Ersetzung in den Anträge-Text „eingebrannt", sondern erst beim Senden komponiert (`komponiereAntraege`). Backend: die Gericht-Zeile wird VOR dem Rollen-Filter gelesen, damit der Persistenz-Rückweg funktioniert. Keine Migration, kein neues Feld an `unfallakte` (V9 entfällt — nicht nötig).

**Tech Stack:** React (JSX, Vitest + @testing-library/react), Flask + SQLite (pytest, unittest-Stil wie `test_klage_kw18_route.py`).

## Global Constraints

- **TDD strikt:** erst fehlschlagender Test (Rot-Beleg dokumentieren), dann Fix. Stellt sich ein Fund als falsch heraus → `entfällt` mit Begründung, kein Blindfix.
- **RA-MICRO read-only. KEINE DB-Migration in dieser Session.**
- **Baseline:** Backend 204f/1056p/18s (204f = bekannte Alt-Cluster `test_modul2/3/4/7`, `test_sv_portal`, `test_prd27`) — **null neue Failures**; Frontend **159 Vitest + Build grün** (Zähler wächst mit neuen Tests).
- **Tests auf dem Host:** `python -m pytest …` aus dem Projektroot (`C:\Users\HAL9000\Documents\Projekt\Version 1.00\unfallakten`); Vitest/Build aus `frontend/` (`npx vitest run …`, `npm run build`). Tests **NIEMALS run_in_background** — immer blockierend im Vordergrund, Timeout bis 600000 ms, volle Suite notfalls splitten.
- **Git-Guardrail:** Repo-Root = HOME (`C:\Users\HAL9000`) → **NIE `git add -A`**, nur explizite Pfade. Arbeitsbranch `klage-wizard-fixes-s5` (steht auf main `ec53900b`).
- **Datumsanzeigen IMMER durch `fmtDatumDe`** (`frontend/src/config/utils.js`); Transportformat bleibt ISO (V5-Vertrag).
- **Keine neuen Anlagen-Verweise** („K 1" etc.) in Auto-Texte einbauen — die bestehenden Textbausteine (`baueAntraegeText`, `baueGebuehrenAntrag`, `buildVerzugAutoText`) bleiben wortgleich; diese Session ändert nur Regenerations-/Kompositions-Logik, keine Formulierungen.
- **Code-Stil:** deutsche Bezeichner wie im Bestand; keine Kommentare außer bei nicht-offensichtlichem Verhalten.
- **cfg-Vertrag (Stand S4):** `verzugsdatum` = Verzugseintritt, `verzug_schreiben_datum` = Schreibdatum; `rvg`/`rvg_override` existieren NICHT mehr; `wizardGenerieren()` (KlageSection.jsx:494–523) ist die EINZIGE cfg-Versandstelle.
- **Vertagte Minors NICHT mitfixen** (nur nicht verschlimmern): toter Fixture-Rest `rvgData/rvgOverride` in `KlageWizard.haftungsquote.test.jsx` (~Z.205), totes try/catch in `fmtDatumDe`, AktLeg-Block/Forderungsschreiben nicht plural-gehärtet, KW-30–40.
- **Frontend-Testmuster:** nie den Default-Export `KlageWizard` rendern — reine named-export-Funktionen testen oder einzelne `Step*`-Komponenten (ggf. neu als named export) in einem lokalen State-Wrapper.

**Ist-Stand-Referenz (Erhebung 2026-07-18, Branch-Basis `ec53900b`):** KlageWizard.jsx = 2669 Zeilen, KlageSection.jsx = 1340 Zeilen, klage_routes.py = 1933 Zeilen. Zeilennummern unten stammen aus dieser Erhebung; durch die Tasks verschieben sie sich — vor jedem Edit frisch prüfen.

---

### Task 1: KW-27 — Gericht-Persistenz: Rückweg reparieren (Backend)

**Files:**
- Modify: `backend/routers/klage_routes.py` (~Z.962 Rollen-Filter, ~Z.1013–1025 Prio-1a-Loop, ~Z.1049–1050 toter Zweitfilter)
- Test: `backend/tests/test_klage_kw27_gericht_persistenz.py` (neu)

**Interfaces:**
- Konsumiert: bestehender PUT-Endpoint `speichere_gericht` (klage_routes.py:1451–1483, schreibt `beteiligte`-Zeile mit `rolle='gericht'`), bestehender Klage-Daten-GET (liefert `gericht_vorschlag` + `gericht_quelle`, Z.1132–1133). Route-Test-Harness: `backend/tests/test_klage_kw18_route.py` als Vorlage (App-Fixture, Akte anlegen, Auth).
- Produziert: `gericht_vorschlag.quelle == "akte"` nach gespeichertem Gericht — das Frontend (KlageSection.jsx:456 `setWizardGerichtBest(gericht?.quelle === "akte")`) funktioniert dann ohne Änderung.

**Befund (Ist):** Die Rollenzuweisung (Z.931–951) setzt die Gericht-Zeile auf `rolle_klage="nicht_partei"`; der Filter Z.962 (`alle_bet = [b for b in alle_bet if b.get("rolle_klage") in ("klaeger", "beklagter")]`) wirft sie raus, BEVOR der Prio-1a-Loop (Z.1013–1025) nach `b["rolle"]=='gericht'` sucht → Loop läuft immer ins Leere, Fallback 1b (RA-MICRO) bzw. 2 (Unfallort) gewinnt. Zweitfilter Z.1049–1050 ist tot.

- [ ] **Step 1: Fehlschlagenden Test schreiben**

Neue Datei `backend/tests/test_klage_kw27_gericht_persistenz.py`, Harness-Muster von `test_klage_kw18_route.py` übernehmen (gleiche Fixture-/Login-Mechanik). Kerntest:

```python
class TestGerichtPersistenz(…):
    def test_gespeichertes_gericht_kommt_als_akte_vorschlag_zurueck(self):
        # Akte anlegen (Harness), dann Gericht speichern:
        r = self.client.put(f"/api/akten/{az}/klage/gericht", json={
            "name": "Amtsgericht Testhausen", "strasse": "Gerichtsweg 1",
            "plz": "63065", "ort": "Testhausen",
        }, headers=self.auth)
        self.assertEqual(r.status_code, 200)
        # Klage-Daten laden:
        r2 = self.client.get(f"/api/akten/{az}/klage/daten", headers=self.auth)
        d = r2.get_json()
        self.assertEqual(d["gericht_quelle"], "akte")
        self.assertEqual(d["gericht_vorschlag"]["name"], "Amtsgericht Testhausen")
        self.assertEqual(d["gericht_vorschlag"]["quelle"], "akte")

    def test_gericht_zeile_erscheint_nicht_in_beteiligten(self):
        # nach dem PUT wie oben: beklagte/beteiligte-Liste der Daten-Response
        # enthält KEINEN Eintrag mit Namen "Amtsgericht Testhausen"
```

Exakte URL-Pfade/Feldnamen des PUT-Payloads vorher im Code verifizieren (Endpoint-Definition Z.1451 ff. und `apiKlage.gerichtSpeichern` im Frontend) — der Test muss den echten Vertrag treffen, nicht einen gewünschten.

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `python -m pytest backend/tests/test_klage_kw27_gericht_persistenz.py -v`
Expected: FAIL — `gericht_quelle` ist nicht `"akte"` (sondern `unfallort`/`ramicro`/None). Der zweite Test (kein Gericht in Beteiligten) darf schon grün sein (Filter existiert ja).

- [ ] **Step 3: Fix implementieren**

In der Daten-Route (Funktion um Z.946–1133):

1. **Vor** dem Rollen-Filter Z.962 die Gericht-Zeile sichern:

```python
gericht_bet = next(
    (b for b in alle_bet if (b.get("rolle") or "").lower() == "gericht"),
    None,
)
# Nur Kläger und Beklagte ins Frontend — Zeugen, SV, sonstige Beteiligte ausblenden
alle_bet = [b for b in alle_bet if b.get("rolle_klage") in ("klaeger", "beklagter")]
```

2. Den Prio-1a-Loop (Z.1013–1025) auf `gericht_bet` umstellen — die bestehende Dict-Konstruktion (Felder + `"quelle": "akte"` + `gericht_quelle = "akte"`) unverändert übernehmen, nur die Quelle der Daten ist jetzt `gericht_bet` statt des Loops:

```python
# 1a – SQLite
if gericht_bet is not None:
    gericht_vorschlag = { …bestehende Feld-Zuordnung aus gericht_bet…, "quelle": "akte" }
    gericht_quelle = "akte"
```

3. Den toten Zweitfilter Z.1049–1050 ersatzlos entfernen (nach Punkt 1 ist garantiert kein `rolle='gericht'` mehr in `alle_bet`).

- [ ] **Step 4: Tests laufen lassen — grün**

Run: `python -m pytest backend/tests/test_klage_kw27_gericht_persistenz.py backend/tests/test_klage_kw18_route.py backend/tests/test_klage_overrides_merge.py -v`
Expected: alle PASS. Danach Regressionsfläche: `python -m pytest backend/tests/ -k "klage" -v` — null neue Failures.

- [ ] **Step 5: Commit**

```bash
git add "Documents/Projekt/Version 1.00/unfallakten/backend/routers/klage_routes.py" "Documents/Projekt/Version 1.00/unfallakten/backend/tests/test_klage_kw27_gericht_persistenz.py"
git commit -m "fix(klage): KW-27 - Gericht-Persistenz-Rueckweg, Gericht-Zeile vor Rollen-Filter gelesen"
```
(Pfade relativ zum Git-Root HOME — im Projektordner entsprechend `git add backend/routers/klage_routes.py backend/tests/test_klage_kw27_gericht_persistenz.py` mit vollem Prefix. NIE `git add -A`.)

---

### Task 2: KW-26 — Fortschrittsbalken durch kannWeiter-Sperren leiten

**Files:**
- Modify: `frontend/src/sections/KlageWizard.jsx` (`Fortschrittsbalken` Z.293–341, `kannWeiter` Z.2418–2422, Render-Stelle Z.2480)
- Test: `frontend/src/sections/KlageWizard.springen.test.jsx` (neu)

**Interfaces:**
- Produziert (named exports, neu): `schrittBlockiert(nr, {gerichtBestaetigt, positionen})` → bool; `kannSpringen(ziel, step, ctx)` → bool; `Fortschrittsbalken` (bestehende Komponente, neu exportiert).
- `kannWeiter()` im Default-Export nutzt künftig `schrittBlockiert` (eine Quelle für die Sperr-Regeln).

**Befund (Ist):** `klickbar = s.nr <= maxStep && s.nr !== step` (Z.299), Klick ruft direkt `onStepChange(s.nr)` (Z.304) = `setWizardStep` — `kannWeiter()` (nur Steps 1+5: `gerichtBestaetigt`, `positionen.some(checked)`) wird umgangen.

- [ ] **Step 1: Fehlschlagende Tests schreiben**

```jsx
import { describe, it, expect, vi } from "vitest";
import { render, fireEvent } from "@testing-library/react";
import { schrittBlockiert, kannSpringen, Fortschrittsbalken } from "./KlageWizard.jsx";

describe("schrittBlockiert", () => {
  it("Step 1 blockiert ohne Gerichtsbestätigung", () => {
    expect(schrittBlockiert(1, { gerichtBestaetigt: false, positionen: [] })).toBe(true);
    expect(schrittBlockiert(1, { gerichtBestaetigt: true, positionen: [] })).toBe(false);
  });
  it("Step 5 blockiert ohne gecheckte Position", () => {
    expect(schrittBlockiert(5, { gerichtBestaetigt: true, positionen: [{ checked: false }] })).toBe(true);
    expect(schrittBlockiert(5, { gerichtBestaetigt: true, positionen: [{ checked: true }] })).toBe(false);
  });
});

describe("kannSpringen", () => {
  const ctx = { gerichtBestaetigt: true, positionen: [{ checked: false }] };
  it("rueckwaerts immer erlaubt", () => {
    expect(kannSpringen(2, 5, ctx)).toBe(true);
  });
  it("vorwaerts ueber gesperrten Step 5 hinweg verboten", () => {
    expect(kannSpringen(6, 5, ctx)).toBe(false);
    expect(kannSpringen(10, 3, ctx)).toBe(false);
  });
  it("vorwaerts erlaubt wenn alle Zwischen-Steps frei", () => {
    const frei = { gerichtBestaetigt: true, positionen: [{ checked: true }] };
    expect(kannSpringen(6, 5, frei)).toBe(true);
  });
});

describe("Fortschrittsbalken", () => {
  it("Klick auf Kreis hinter gesperrtem Step ruft onStepChange NICHT", () => {
    const onStepChange = vi.fn();
    const { getByText } = render(
      <Fortschrittsbalken step={5} maxStep={10} onStepChange={onStepChange}
        springenErlaubt={(nr) => kannSpringen(nr, 5, { gerichtBestaetigt: true, positionen: [{ checked: false }] })} />
    );
    fireEvent.click(getByText("6"));
    expect(onStepChange).not.toHaveBeenCalled();
    fireEvent.click(getByText("2"));
    expect(onStepChange).toHaveBeenCalledWith(2);
  });
});
```

(Die konkrete DOM-Struktur der Kreise vor dem Schreiben prüfen — `getByText("6")` an die echte Struktur anpassen, ggf. `getAllByText`/role.)

- [ ] **Step 2: Rot-Beleg**

Run: `cd frontend && npx vitest run src/sections/KlageWizard.springen.test.jsx`
Expected: FAIL — `schrittBlockiert`/`kannSpringen` nicht exportiert; nach deren Anlage muss mindestens der Fortschrittsbalken-Test rot sein (Klick auf „6" ruft `onStepChange` im Ist-Zustand DOCH auf).

- [ ] **Step 3: Implementieren**

```jsx
export function schrittBlockiert(nr, { gerichtBestaetigt, positionen }) {
  if (nr === 1 && !gerichtBestaetigt) return true;
  if (nr === 5 && !(positionen || []).some(p => p.checked)) return true;
  return false;
}

export function kannSpringen(ziel, step, ctx) {
  if (ziel <= step) return true;
  for (let k = step; k < ziel; k++) {
    if (schrittBlockiert(k, ctx)) return false;
  }
  return true;
}
```

`Fortschrittsbalken` exportieren und um Prop `springenErlaubt` ergänzen:

```jsx
const klickbar = s.nr <= maxStep && s.nr !== step && (!springenErlaubt || springenErlaubt(s.nr));
```

Render-Stelle (Z.2480) im Default-Export:

```jsx
<Fortschrittsbalken step={step} maxStep={wizardMaxStep} onStepChange={onStepChange}
  springenErlaubt={(nr) => kannSpringen(nr, step, { gerichtBestaetigt, positionen })} />
```

`kannWeiter` (Z.2418–2422) auf die gemeinsame Quelle umstellen:

```jsx
const kannWeiter = () => !schrittBlockiert(step, { gerichtBestaetigt, positionen });
```

Nicht-klickbare Kreise sollen weiterhin die bestehende Nicht-klickbar-Optik bekommen (kein neues Styling erfinden).

- [ ] **Step 4: Grün + Fläche**

Run: `cd frontend && npx vitest run src/sections/ && npm run build`
Expected: alle Klage-Tests grün (159 Bestand + neue), Build grün.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/sections/KlageWizard.jsx frontend/src/sections/KlageWizard.springen.test.jsx
git commit -m "fix(klage): KW-26 - Fortschrittsbalken respektiert kannWeiter-Sperren (kannSpringen kumulativ)"
```

---

### Task 3: KW-25 — Sachverhalt-Manuell-Flag in den Section-State (Step 3)

**Files:**
- Modify: `frontend/src/sections/KlageSection.jsx` (State-Block ~Z.176, `oeffneWizard`-Reset ~Z.452, Props-Durchreichung an KlageWizard)
- Modify: `frontend/src/sections/KlageWizard.jsx` (`StepAktLeg` Z.585–599 prevAutoRef, DokumentCard-Edit ~Z.683–684; StepAktLeg als named export)
- Test: `frontend/src/sections/KlageWizard.aktleg.test.jsx` (neu)

**Interfaces:**
- Konsumiert: Muster `wizardVerzugManuell` (KlageSection.jsx:183 State, :452 Reset, :599 Prop `manuelleBearbeitung`; KlageWizard.jsx:1478–1481 Guard, :1637 Edit-Setter, :1493–1496 Reset).
- Produziert: KlageSection-State `wizardSachverhaltManuell` (bool, Default false); StepAktLeg-Props `sachverhaltManuell`, `onSachverhaltManuell`; `StepAktLeg` als named export.

**Befund (Ist):** `prevAutoRef` ist lokal in `StepAktLeg` (Z.585); der Effect (587–599) überschreibt `sachverhaltText` nur, wenn er dem zuletzt generierten Auto-Text entspricht — beim Remount ist `prevAutoRef.current === null` → bedingungsloses Überschreiben, manuelle Edits weg.

- [ ] **Step 1: Fehlschlagenden Test schreiben**

Wrapper-Muster wie `KlageWizard.gebuehren.test.jsx` (lokaler `useState` im Test-Wrapper hält `sachverhaltText` + `sachverhaltManuell`, StepAktLeg wird unmounted/remounted):

```jsx
function Wrapper({ gemountet }) {
  const [text, setText] = useState("");
  const [manuell, setManuell] = useState(false);
  return gemountet ? (
    <StepAktLeg sachverhaltText={text} onSachverhaltText={setText}
      sachverhaltManuell={manuell} onSachverhaltManuell={setManuell}
      aktLegTyp="eigentum" aktLegFreigabe="freigabe" aktLegDatum=""
      beklagte={[]} … /* restliche Pflicht-Props minimal */ />
  ) : <div data-testid="leer" />;
}
```

Testfälle:
1. `manueller Edit ueberlebt Remount`: rendern → Textarea-Edit („MANUELL ERGÄNZT") → `rerender` mit `gemountet={false}` → wieder `gemountet={true}` → Textarea enthält weiterhin „MANUELL ERGÄNZT". **(Rot im Ist-Zustand: Auto-Text überschreibt.)**
2. `ohne Edit regeneriert Radio-Wechsel den Text`: kein Edit, `aktLegTyp` wechseln → Text ändert sich (Bestandsverhalten bleibt).
3. `Reset-Knopf verwirft manuellen Text`: nach Edit den Neu-generieren-Knopf klicken → Auto-Text wieder da, weitere Radio-Wechsel wirken wieder.

Für Test 1 muss der Wrapper die Props-Kette echt spiegeln (State lebt im Wrapper = Section, nicht im Step) — genau das ist der Fix.

- [ ] **Step 2: Rot-Beleg**

Run: `cd frontend && npx vitest run src/sections/KlageWizard.aktleg.test.jsx`
Expected: FAIL — `StepAktLeg` nicht exportiert; nach Export muss Testfall 1 rot sein (Remount überschreibt manuellen Text).

- [ ] **Step 3: Implementieren**

KlageSection.jsx:
```jsx
const [wizardSachverhaltManuell, setWizardSachverhaltManuell] = useState(false);
```
In `oeffneWizard` (~Z.452, neben `setWizardVerzugManuell(false)`): `setWizardSachverhaltManuell(false);`
Props an `<KlageWizard …>` → weiter an `StepAktLeg`: `sachverhaltManuell={wizardSachverhaltManuell} onSachverhaltManuell={setWizardSachverhaltManuell}`.

KlageWizard.jsx, `StepAktLeg` (jetzt `export function StepAktLeg…`):
```jsx
useEffect(() => {
  if (sachverhaltManuell) return;
  if (onSachverhaltText) onSachverhaltText(buildSachverhaltText({ …bestehende Args… }));
}, [aktLegTyp, aktLegFreigabe, aktLegDatum, mandantIstFahrer, auslandsunfall]);
```
`prevAutoRef` ersatzlos entfernen. DokumentCard-Edit (~Z.683):
```jsx
onEditText={val => { onSachverhaltManuell(true); onSachverhaltText(val); }}
```
Reset-Affordance im Muster von StepVerzug `handleReset` (Z.1493–1496): kleiner „↻ Neu generieren"-Knopf, der `onSachverhaltManuell(false)` setzt und den Auto-Text neu baut. Optik/Platzierung wie der bestehende Verzug-Reset.

- [ ] **Step 4: Grün + Fläche**

Run: `cd frontend && npx vitest run src/sections/ && npm run build`
Expected: alles grün.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/sections/KlageWizard.jsx frontend/src/sections/KlageSection.jsx frontend/src/sections/KlageWizard.aktleg.test.jsx
git commit -m "fix(klage): KW-25 - Sachverhalt-Manuell-Flag in Section-State, Remount ueberschreibt Edits nicht mehr (V7)"
```

---

### Task 4: KW-24 — Gebühren-Antrag als eigenes Segment, Komposition beim Senden

**Files:**
- Modify: `frontend/src/sections/KlageWizard.jsx` (`StepGebuehren` Z.2068–…: Effects 2144–2154 + Ersetzungs-Effect 2157–2162; `StepZusammenfassung` Z.1644–…: Guard 1665–1666; neue Funktion `komponiereAntraege`)
- Modify: `frontend/src/sections/KlageSection.jsx` (neuer State `wizardGebuehrenManuell`, `wizardGenerieren` Z.507, Props)
- Test: `frontend/src/sections/KlageWizard.gebuehren.test.jsx` (erweitern/anpassen), `KlageWizard.zusammenfassung.test.jsx` (anpassen)

**Interfaces:**
- Produziert (named export, neu): `komponiereAntraege(antraegeText, gebuehrenText)` → string. Vertrag: ersetzt `ANTRAEGE_PLACEHOLDER` durch `gebuehrenText`, wenn beides vorhanden; sonst Rückgabe unverändert.
- KlageSection-State neu: `wizardGebuehrenManuell` (bool, Default false, Reset in `oeffneWizard`).
- `StepZusammenfassung` bekommt neue Prop `gebuehrenText`; der Platzhalter-Guard prüft den **komponierten** Text.
- **Task 5 verlässt sich darauf:** `wizardAntraegeText` behält den Platzhalter dauerhaft; Regeneration in Step 6 darf ihn jederzeit neu einfügen, ohne dass Step 9 erneut besucht werden muss.

**Befund (Ist):** (a) Ersetzungs-Effect Z.2157–2162 brennt `gebuehrenText` in `antraegeText` ein — nur solange der Platzhalter vorhanden ist; danach sind Step-9-Änderungen wirkungslos. (b) Effect Z.2150–2154 (`[bereitsGez]`) überschreibt `wizardGebuehrenText` bei jedem Remount bedingungslos (Step 9 wird conditional gemountet, Z.2581). (c) `wizardGebuehrenText` wird nie gesendet (nicht in cfg/overrides, KlageSection 494–523).

- [ ] **Step 1: Fehlschlagende Tests schreiben**

In `KlageWizard.gebuehren.test.jsx` ergänzen (bestehende Tests erst NACH Implementierung an die neue Semantik anpassen — Rot-Beleg mit den neuen Tests führen):

```jsx
import { komponiereAntraege, ANTRAEGE_PLACEHOLDER } from "./KlageWizard.jsx";

describe("komponiereAntraege", () => {
  it("ersetzt den Platzhalter durch den Gebuehren-Text", () => {
    const a = `1. Antrag X\n2. ${ANTRAEGE_PLACEHOLDER}\n3. Kosten`;
    expect(komponiereAntraege(a, "GEBUEHREN-SATZ")).toBe("1. Antrag X\n2. GEBUEHREN-SATZ\n3. Kosten");
  });
  it("ohne Gebuehren-Text bleibt der Platzhalter stehen", () => {
    const a = `Antrag ${ANTRAEGE_PLACEHOLDER}`;
    expect(komponiereAntraege(a, "")).toBe(a);
    expect(komponiereAntraege(a, null)).toBe(a);
  });
  it("ohne Platzhalter bleibt der Text unveraendert", () => {
    expect(komponiereAntraege("fertiger Text", "GEB")).toBe("fertiger Text");
  });
  it("leerer Antraege-Text bleibt leer", () => {
    expect(komponiereAntraege("", "GEB")).toBe("");
  });
});
```

StepGebuehren-Verhaltenstests (Wrapper mit `useState` wie bestehend):
1. `bereitsGezahlt-Aenderung regeneriert den Gebuehren-Text` (Bestandsverhalten, bleibt).
2. `manueller Edit wird beim Remount NICHT ueberschrieben`: Edit am Gebühren-Text (DokumentCard) → unmount → remount → Text unverändert. **(Rot im Ist.)**
3. `antraegeText behaelt den Platzhalter — keine Einbrennung`: StepGebuehren mounten mit antraegeText inkl. Platzhalter → nach Generierung des Gebühren-Texts enthält `antraegeText` im Wrapper-State WEITERHIN den Platzhalter. **(Rot im Ist: Ersetzungs-Effect brennt ein.)**

StepZusammenfassung-Test (in `KlageWizard.zusammenfassung.test.jsx` ergänzen):
4. `Platzhalter + vorhandener Gebuehren-Text sperrt NICHT`: `antraegeText` mit Platzhalter, Prop `gebuehrenText="GEB"` → Generieren-Button nicht gesperrt, kein Warnbanner. **(Rot im Ist.)**
5. Bestandstest „Platzhalter sperrt" auf `gebuehrenText={null}` umstellen (bleibt gesperrt — Schutz, wenn Step 9 nie Text erzeugt hat).

- [ ] **Step 2: Rot-Beleg**

Run: `cd frontend && npx vitest run src/sections/KlageWizard.gebuehren.test.jsx src/sections/KlageWizard.zusammenfassung.test.jsx`
Expected: FAIL genau bei den neuen Tests (2, 3, 4) + `komponiereAntraege` fehlt.

- [ ] **Step 3: Implementieren**

KlageWizard.jsx:

```jsx
export function komponiereAntraege(antraegeText, gebuehrenText) {
  if (!antraegeText || !gebuehrenText) return antraegeText;
  if (!antraegeText.includes(ANTRAEGE_PLACEHOLDER)) return antraegeText;
  return antraegeText.replace(ANTRAEGE_PLACEHOLDER, gebuehrenText);
}
```

`StepGebuehren`:
- Ersetzungs-Effect Z.2157–2162 **ersatzlos entfernen**.
- Die beiden Regenerations-Effects Z.2144–2154 zusammenführen:
```jsx
useEffect(() => {
  if (gebuehrenManuell) return;
  if (rvgGesamt > 0) onGebuehrenText(baueGebuehrenAntrag());
}, [rvgGesamt, bereitsGez]);
```
- Manueller Edit am Gebühren-Text (DokumentCard in Step 9): `onEditText={val => { onGebuehrenManuell(true); onGebuehrenText(val); }}` + Reset-Affordance im Verzug-Muster (`onGebuehrenManuell(false)` + Neu-Bau).
- Zeigt Step 9 eine Anträge-Vorschau, dann dort `komponiereAntraege(antraegeText, gebuehrenText)` nur für die ANZEIGE verwenden (State bleibt mit Platzhalter).

`StepZusammenfassung` (Guard Z.1665–1666):
```jsx
const antraegeFinal = komponiereAntraege(antraegeText, gebuehrenText);
const hatPlatzhalter = !!antraegeFinal && antraegeFinal.includes(ANTRAEGE_PLACEHOLDER);
```
Neue Prop `gebuehrenText` an der Render-Stelle des Default-Exports durchreichen. Falls Step 10 den Anträge-Text anzeigt: `antraegeFinal` anzeigen.

KlageSection.jsx:
- State: `const [wizardGebuehrenManuell, setWizardGebuehrenManuell] = useState(false);` + Reset in `oeffneWizard`.
- Props an StepGebuehren: `gebuehrenManuell={wizardGebuehrenManuell} onGebuehrenManuell={setWizardGebuehrenManuell}`.
- `wizardGenerieren` Z.507:
```jsx
antraege_override: komponiereAntraege(wizardAntraegeText, wizardGebuehrenText) || null,
```
mit `import { komponiereAntraege } from "./KlageWizard.jsx";` (Import-Stil an bestehende Imports der Datei anpassen).

- [ ] **Step 4: Grün + Fläche**

Run: `cd frontend && npx vitest run src/sections/ && npm run build`
Expected: alles grün; angepasste Bestandstests nur dort, wo die Semantik sich GEWOLLT geändert hat (Einbrennung → Komposition) — jede Assertion-Änderung im Report begründen.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/sections/KlageWizard.jsx frontend/src/sections/KlageSection.jsx frontend/src/sections/KlageWizard.gebuehren.test.jsx frontend/src/sections/KlageWizard.zusammenfassung.test.jsx
git commit -m "fix(klage): KW-24 - Gebuehren-Antrag als eigenes Segment, Komposition erst beim Senden (V7)"
```

---

### Task 5: KW-22 — Dirty-Tracking für den Anträge-Text (V7-Kern)

**Files:**
- Modify: `frontend/src/sections/KlageWizard.jsx` (`StepAntraege` Z.1963–…: Effect 1981–1983, Checkbox-onChange 2011–2014, Button 2032–2037; `StepZusammenfassung`; Default-Export; neue Exports `antraegeBasis`, `AntraegeSync`, `TextVeraltetBadge`)
- Modify: `frontend/src/sections/KlageSection.jsx` (neue States `wizardAntraegeManuell`, `wizardAntraegeBasis`, Reset, Props)
- Test: `frontend/src/sections/KlageWizard.antraege-dirty.test.jsx` (neu), `KlageWizard.zusammenfassung.test.jsx` (erweitern)

**Interfaces:**
- Konsumiert aus Task 4: Platzhalter bleibt dauerhaft in `wizardAntraegeText`; `komponiereAntraege` übernimmt die Ersetzung beim Senden/Anzeigen — Regeneration darf den Platzhalter jederzeit neu setzen.
- Produziert (named exports, neu):
  - `antraegeBasis(opts)` → string (JSON-Fingerprint der textrelevanten Eingaben)
  - `AntraegeSync({ step, opts, antraegeText, manuell, basisStand, onAntraegeText, onAntraegeBasis })` → null (Sync-Komponente, immer gemountet im Wizard)
  - `TextVeraltetBadge({ sichtbar, onNeuGenerieren, onBehalten })` → Badge „⚠ Text veraltet — Eingaben haben sich geändert" mit den zwei Knöpfen
- KlageSection-States neu: `wizardAntraegeManuell` (bool), `wizardAntraegeBasis` (string|null), beide Reset in `oeffneWizard`.

**Befund (Ist):** StepAntraege generiert nur „wenn leer" (Effect Z.1981–1983, `[]`-Deps); Feststellungs-Checkboxen togglen nur die Booleans ohne `regenerieren()` (Z.2011–2014); Positions-/SG-Änderungen aus Step 5 erreichen den Text nie → stale `antraege_override` landet seit KW-01-Fix im DOCX.

**Design:**
- Ist der Text **nicht** manuell bearbeitet: bei jeder Basis-Änderung automatisch neu generieren (Text ist deterministisch — kein Datenverlust möglich). Das deckt auch die Checkboxen ab (sie sind Teil der Basis).
- Ist der Text manuell bearbeitet: nie automatisch überschreiben; stattdessen Badge „Text veraltet" mit „↻ Neu generieren" (verwirft Edits, `manuell=false`, Basis nachgezogen) / „Behalten" (Basis wird auf aktuell gesetzt, Badge verschwindet, Text bleibt). Badge erscheint in Step 6 UND Step 10; sie sperrt das Generieren NICHT (bewusste Nutzerentscheidung möglich).
- Die Sync-Logik lebt in `AntraegeSync` (im Default-Export immer gerendert), damit sie auch greift, wenn der Nutzer Step 6 nie erneut besucht (z. B. Step 5 → Balken → Step 10).

- [ ] **Step 1: Fehlschlagende Tests schreiben**

`KlageWizard.antraege-dirty.test.jsx`:

```jsx
import { antraegeBasis, AntraegeSync, TextVeraltetBadge, baueAntraegeText, ANTRAEGE_PLACEHOLDER } from "./KlageWizard.jsx";

describe("antraegeBasis", () => {
  const basisOpts = { positionen: [{ key: "a", betrag: 100, checked: true }], mitSG: false, sgMind: null,
    beklagte: [{ id: 1, checked: true, rolle_klage: "beklagter" }], weiblich: true,
    zinsenAb: "verzug", verzug: "2026-01-01", unfalldatum: "2026-01-01",
    mitFestSg: false, mitFestSach: false, hq: 100, hqTyp: "gegnerisch" };
  it("Positions-Abwahl aendert die Basis", () => {
    const b1 = antraegeBasis(basisOpts);
    const b2 = antraegeBasis({ ...basisOpts, positionen: [{ key: "a", betrag: 100, checked: false }] });
    expect(b1).not.toBe(b2);
  });
  it("Feststellungs-Checkbox aendert die Basis", () => {
    expect(antraegeBasis(basisOpts)).not.toBe(antraegeBasis({ ...basisOpts, mitFestSach: true }));
  });
  it("identische Eingaben, identische Basis", () => {
    expect(antraegeBasis(basisOpts)).toBe(antraegeBasis({ ...basisOpts }));
  });
});

describe("AntraegeSync", () => {
  // Wrapper haelt text/basis/manuell im useState (= Section-State)
  it("regeneriert bei Basis-Aenderung, wenn nicht manuell", () => { /* opts aendern -> text neu, basis nachgezogen */ });
  it("ueberschreibt manuell bearbeiteten Text NICHT", () => { /* manuell=true, opts aendern -> text unveraendert */ });
  it("generiert initial ab Step 6, nicht davor", () => { /* step=5: kein Text; step=6: Text da */ });
});

describe("TextVeraltetBadge", () => {
  it("sichtbar=false rendert nichts", () => { … });
  it("Knoepfe feuern die Callbacks", () => { … });
});
```

`KlageWizard.zusammenfassung.test.jsx` ergänzen:
- `zeigt Veraltet-Badge wenn antraegeVeraltet` (Prop-getrieben) + beide Knöpfe rufen Callbacks; Generieren bleibt möglich (nicht gesperrt).

Der zentrale Rot-Beleg für KW-22 ist der AntraegeSync-Test „regeneriert bei Basis-Aenderung": Im Ist-Zustand existiert keine Regeneration außerhalb von Step 6 (Funktion fehlt) — zusätzlich als Verhaltens-Rot dokumentieren: bestehender StepAntraege-Effect generiert nur `if (!antraegeText)`.

- [ ] **Step 2: Rot-Beleg**

Run: `cd frontend && npx vitest run src/sections/KlageWizard.antraege-dirty.test.jsx`
Expected: FAIL (Exports fehlen).

- [ ] **Step 3: Implementieren**

KlageWizard.jsx:

```jsx
export function antraegeBasis(opts) {
  const o = opts || {};
  return JSON.stringify({
    pos: (o.positionen || []).filter(p => p.checked).map(p => [p.key, p.betrag]),
    mitSG: !!o.mitSG,
    sgMind: o.mitSG ? (o.sgMind ?? null) : null,
    bek: (o.beklagte || []).map(b => [b.id, b.checked !== false, b.rolle_klage || null]),
    weiblich: o.weiblich ?? null,
    zinsenAb: o.zinsenAb ?? null,
    verzug: o.verzug ?? null,
    unfalldatum: o.unfalldatum ?? null,
    mitFestSg: !!o.mitFestSg,
    mitFestSach: !!o.mitFestSach,
    hq: o.hq ?? 100,
    hqTyp: o.hqTyp ?? "gegnerisch",
  });
}

export function AntraegeSync({ step, opts, antraegeText, manuell, basisStand, onAntraegeText, onAntraegeBasis }) {
  const basisAktuell = antraegeBasis(opts);
  useEffect(() => {
    if (step < 6) return;
    if (!antraegeText || (!manuell && basisAktuell !== basisStand)) {
      onAntraegeText(baueAntraegeText(opts));
      onAntraegeBasis(basisAktuell);
    }
  }, [step, basisAktuell]);
  return null;
}

export function TextVeraltetBadge({ sichtbar, onNeuGenerieren, onBehalten }) {
  if (!sichtbar) return null;
  return (
    <div style={{ …Amber-Optik im Stil der bestehenden Warnbloecke… }}>
      ⚠ Text veraltet — Eingaben haben sich geändert.
      <button onClick={onNeuGenerieren}>↻ Neu generieren</button>
      <button onClick={onBehalten}>Behalten</button>
    </div>
  );
}
```

Default-Export `KlageWizard`:
- `antraegeOpts` einmal aus den vorhandenen Props bauen (identisch zu dem, was `regenerieren()` in StepAntraege heute baut — Z.1973–1978 als Referenz; `weiblich` aus derselben Quelle wie dort).
- `<AntraegeSync step={step} opts={antraegeOpts} antraegeText={antraegeText} manuell={antraegeManuell} basisStand={antraegeBasisStand} onAntraegeText={onAntraegeText} onAntraegeBasis={onAntraegeBasis} />` unbedingt AUSSERHALB der step-Conditionals rendern.
- Gemeinsame Handler definieren und an Step 6 + 10 geben:
```jsx
const antraegeVeraltet = antraegeManuell && antraegeBasis(antraegeOpts) !== antraegeBasisStand;
const antraegeNeuGenerieren = () => {
  onAntraegeText(baueAntraegeText(antraegeOpts));
  onAntraegeBasis(antraegeBasis(antraegeOpts));
  onAntraegeManuell(false);
};
const antraegeBehalten = () => onAntraegeBasis(antraegeBasis(antraegeOpts));
```

`StepAntraege`:
- Mount-Effect Z.1981–1983 entfernen (Sync übernimmt). `regenerieren` durch die Prop `onNeuGenerieren` (= `antraegeNeuGenerieren`) ersetzen; „↻ Anträge neu generieren"-Button ruft sie.
- Checkbox-onChange bleibt Toggle-only — die Regeneration kommt automatisch über die Basis (kein zusätzlicher Aufruf nötig).
- Manueller Edit (DokumentCard): `onEditText={val => { onAntraegeManuell(true); onAntraegeText(val); }}`.
- `<TextVeraltetBadge sichtbar={antraegeVeraltet} … />` über der DokumentCard.

`StepZusammenfassung`: neue Props `antraegeVeraltet`, `onAntraegeNeuGenerieren`, `onAntraegeBehalten`; Badge über der Checkliste rendern; `gesperrt` NICHT erweitern.

KlageSection.jsx: States + Reset + Props:
```jsx
const [wizardAntraegeManuell, setWizardAntraegeManuell] = useState(false);
const [wizardAntraegeBasis, setWizardAntraegeBasis] = useState(null);
```
`oeffneWizard`: beide zurücksetzen (`false` / `null`).

- [ ] **Step 4: Grün + Fläche**

Run: `cd frontend && npx vitest run src/sections/ && npm run build`
Expected: alles grün. Besonders prüfen: `KlageWizard.rubrum.test.jsx` (nutzt `baueAntraegeText` pur — darf sich nicht ändern) und Task-4-Tests (Platzhalter-Lebenszyklus).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/sections/KlageWizard.jsx frontend/src/sections/KlageSection.jsx frontend/src/sections/KlageWizard.antraege-dirty.test.jsx frontend/src/sections/KlageWizard.zusammenfassung.test.jsx
git commit -m "fix(klage): KW-22 - zentrales Dirty-Tracking fuer Antraege-Text, Badge 'Text veraltet' (V7)"
```

---

### Task 6: KW-28 — Verzugsdokument-Auswahl wirkt auf die Datumsfelder

**Files:**
- Modify: `frontend/src/sections/KlageSection.jsx` (State-Nähe Z.163–164, Kachel-5-Buttons Z.1167–1188, Prop an StepVerzug)
- Modify: `frontend/src/sections/KlageWizard.jsx` (`StepVerzug`-Select Z.1526–1539 — nur falls Prop-Umbenennung nötig)
- Test: `frontend/src/sections/KlageSection.verzugdok.test.jsx` (neu)

**Interfaces:**
- Konsumiert: `verzugEintrittDefault` (utils.js:36–42, Schreibdatum+14 Tage), `buildVerzugAutoText(dokDatum, eintrittDatum)` (KlageWizard.jsx:1451, exportiert), `wizardVerzugManuell`-Flag.
- Produziert (named export aus KlageSection.jsx, neu — erste named exports der Datei): `verzugDatenAusDok(dok)` → `{ dokDatum, eintritt } | null`.

**Befund (Ist):** Auswahl setzt nur `setVerzugDokId` (Kachel 5 Z.1171, Step-8-Select Z.1528) — keinerlei Wirkung auf `wizardVerzugDokDatum`/`wizardVerzugDatum`/Text; `verzugDokId` wird nie gesendet (Placebo). Entscheidung aus dem Handover: Feld **wirksam machen** (nicht entfernen); die Doc-ID wird weiterhin NICHT gesendet (BEWEIS läuft über das Schreibdatum, S4-Vertrag).

- [ ] **Step 1: Feldnamen verifizieren**

Im Backend prüfen, welche Felder die Einträge von `verzug_dokumente` tragen (klage_routes.py, Aufbau der Daten-Response; vermutlich `id`, `dokumentenklasse`, Datum). Den echten Datums-Feldnamen im Test/Code verwenden — NICHT raten. Trägt das Dokument kein Datum, liefert `verzugDatenAusDok` `null` und die Auswahl ändert nur die ID (kein Clobber der Datumsfelder).

- [ ] **Step 2: Fehlschlagenden Test schreiben**

```jsx
import { verzugDatenAusDok } from "./KlageSection.jsx";
import { verzugEintrittDefault } from "../config/utils.js";

describe("verzugDatenAusDok", () => {
  it("liefert Schreibdatum + Eintritt-Vorschlag (+14 Tage)", () => {
    const dok = { id: 7, datum: "2026-06-01" }; // Feldname aus Step 1 einsetzen
    expect(verzugDatenAusDok(dok)).toEqual({
      dokDatum: "2026-06-01",
      eintritt: verzugEintrittDefault("2026-06-01"),
    });
  });
  it("ohne Datum null (keine Wirkung)", () => {
    expect(verzugDatenAusDok({ id: 7 })).toBeNull();
    expect(verzugDatenAusDok(null)).toBeNull();
  });
});
```

- [ ] **Step 3: Rot-Beleg**

Run: `cd frontend && npx vitest run src/sections/KlageSection.verzugdok.test.jsx`
Expected: FAIL — Export existiert nicht.

- [ ] **Step 4: Implementieren**

KlageSection.jsx:

```jsx
export function verzugDatenAusDok(dok) {
  const datum = dok?.datum || null; // echten Feldnamen aus Step 1 verwenden
  if (!datum) return null;
  return { dokDatum: datum, eintritt: verzugEintrittDefault(datum) };
}
```

Zentraler Auswahl-Handler in der Komponente:

```jsx
const waehleVerzugDok = (dokId) => {
  setVerzugDokId(dokId);
  const daten = verzugDatenAusDok(verzugDokListe.find(d => d.id === dokId));
  if (!daten) return;
  setWizardVerzugDokDatum(daten.dokDatum);
  setWizardVerzugDatum(daten.eintritt);
  if (!wizardVerzugManuell) {
    setWizardVerzugText(buildVerzugAutoText(daten.dokDatum, daten.eintritt));
  }
};
```

- Kachel-5-Buttons (Z.1171): `onClick={() => waehleVerzugDok(dok.id)}`.
- Step-8-Select: die an StepVerzug gereichte Prop `onVerzugDokId` auf `waehleVerzugDok` zeigen lassen (Signatur bleibt `(id) => …`; im Select-onChange Z.1528 nichts weiter ändern, sofern dort schon nur die ID durchgereicht wird).
- Initial-Load-Block (Z.213–221) unverändert lassen (Vorauswahl beim Laden setzt weiterhin nur die ID; die Datumsfelder kommen dort bereits aus `res.verzug_datum`).
- Import ergänzen, falls `buildVerzugAutoText` in KlageSection noch nicht importiert ist.

- [ ] **Step 5: Grün + Fläche**

Run: `cd frontend && npx vitest run src/sections/ && npm run build`
Expected: alles grün (insb. `KlageWizard.verzug.test.jsx` unverändert grün).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/sections/KlageSection.jsx frontend/src/sections/KlageWizard.jsx frontend/src/sections/KlageSection.verzugdok.test.jsx
git commit -m "fix(klage): KW-28 - Verzugsdokument-Auswahl setzt Schreibdatum + Eintritt-Vorschlag (+14 Tage)"
```

---

### Task 7: KW-29 — Vertreter-Lookup: still cachen, Modal nur auf Klick

**Files:**
- Modify: `frontend/src/sections/KlageSection.jsx` (Auto-Lookup-Effect Z.244–257, `lookupVertreter` Z.346–357, manuelle Buttons Z.782/874)
- Test: `frontend/src/sections/KlageSection.lookup.test.jsx` (neu)

**Interfaces:**
- Produziert (named export aus KlageSection.jsx): `sollAutoLookup(b, lookupCache)` → bool.
- `lookupVertreter(id, name, { oeffneModal = true } = {})`: bei `oeffneModal:false` nur Cache füllen, kein `setVModal`; bei Klick mit vorhandenem Cache-Ergebnis Modal sofort aus dem Cache öffnen (kein erneuter Fetch).

**Befund (Ist):** Auto-Effect (Deps `[beklagte]`) lookupt jede Firma ohne `vertreter_name` und **öffnet dabei das Modal** (`setVModal` in `lookupVertreter` Z.351); Guard prüft nur `vertreterLookup[b.id]?.laden` — nach abgeschlossenem Lookup (`laden:false`) verhindert nichts den nächsten Lauf; jede `setBek`-Änderung (auch die Übernahme im Modal selbst, Z.93–96) triggert erneut → Modal-Spam. **Entscheidungs-Notiz:** Das im Handover erwähnte „dismissed-Set" entfällt als eigenes Konstrukt — ohne Auto-Open gibt es nichts mehr zu dismissen; der Einmal-Guard läuft über den Lookup-Cache (`vertreterLookup[b.id]` gesetzt = nicht erneut auto-lookupen). Im Abschlussbericht erwähnen.

- [ ] **Step 1: Fehlschlagenden Test schreiben**

```jsx
import { sollAutoLookup } from "./KlageSection.jsx";

describe("sollAutoLookup", () => {
  const firma = { id: 3, versicherung: "HUK", rolle_klage: "beklagter" };
  it("Firma ohne Vertreter und ohne Cache-Eintrag: ja", () => {
    expect(sollAutoLookup(firma, {})).toBe(true);
  });
  it("abgeschlossener Lookup (laden:false, ergebnis vorhanden) verhindert Wiederholung", () => {
    expect(sollAutoLookup(firma, { 3: { laden: false, ergebnis: { name: "X" } } })).toBe(false);
  });
  it("laufender Lookup verhindert Wiederholung", () => {
    expect(sollAutoLookup(firma, { 3: { laden: true } })).toBe(false);
  });
  it("Klaeger, Privatperson, vorhandener Vertreter: nein", () => {
    expect(sollAutoLookup({ ...firma, rolle_klage: "klaeger" }, {})).toBe(false);
    expect(sollAutoLookup({ id: 4, vorname: "Max", name: "Muster", rolle: "gegner" }, {})).toBe(false);
    expect(sollAutoLookup({ ...firma, vertreter_name: "Dr. A" }, {})).toBe(false);
  });
});
```

Der Fall „abgeschlossener Lookup → false" ist der Rot-Beleg-Kern: die Ist-Logik (nur `?.laden`) würde `true` liefern. Da die Funktion neu entsteht, zusätzlich als Verhaltens-Beleg im Report festhalten: Ist-Guard Z.255 zitieren.

- [ ] **Step 2: Rot-Beleg**

Run: `cd frontend && npx vitest run src/sections/KlageSection.lookup.test.jsx`
Expected: FAIL — Export existiert nicht.

- [ ] **Step 3: Implementieren**

```jsx
export function sollAutoLookup(b, lookupCache) {
  if (b.rolle_klage === "klaeger") return false;
  if (b.vertreter_name) return false;
  const istFirma = !!(b.versicherung || b.firma || (!b.vorname && b.name && b.rolle !== "mandant"));
  if (!istFirma) return false;
  if (lookupCache[b.id]) return false;
  return true;
}
```

Auto-Effect (Z.244–257): Bedingungen durch `if (!sollAutoLookup(b, vertreterLookup)) return;` ersetzen, Aufruf still: `lookupVertreter(b.id, name, { oeffneModal: false });` (Namens-Ermittlung `const name = …` bleibt wie im Bestand).

`lookupVertreter` (Z.346–357):

```jsx
const lookupVertreter = async (id, name, { oeffneModal = true } = {}) => {
  const cached = vertreterLookup[id]?.ergebnis;
  if (cached && oeffneModal) { setVModal({ id, name, daten: cached }); return; }
  … bestehender Fetch + setVLookup …
  if (oeffneModal) setVModal({ id, name, daten: res });
};
```

Manuelle „🔍 Lookup"-Buttons (Z.782, 874) bleiben unverändert (Default `oeffneModal:true` → Klick öffnet, ggf. sofort aus dem Cache).

- [ ] **Step 4: Grün + Fläche**

Run: `cd frontend && npx vitest run src/sections/ && npm run build`
Expected: alles grün.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/sections/KlageSection.jsx frontend/src/sections/KlageSection.lookup.test.jsx
git commit -m "fix(klage): KW-29 - Vertreter-Lookup still cachen, Modal nur auf Klick"
```

---

### Task 8: Abschluss — Baselines, Doku, Whole-Branch-Review

**Files:**
- Modify: `docs/BUGFIX_KLAGE_WIZARD.md` (KW-22/24/25/26/27/28/29 → `[x]` + Commit-Hashes + Umsetzungs-Notizen, Status-Tabelle, Session-Tabelle Zeile 5)
- Modify: `docs/TODO.md` (Session-5-Eintrag im PRD-33-Block)
- Create: `handover/naechste_session_PRD33_S6_prompt.md` (KW-30–40 + V10 Golden-File-Matrix, Rundungs-Helper BE/FE, hq=0-Guard, BE/FE-BEWEIS-Fallback-Angleichung M5 aus S4)

- [ ] **Step 1: Volle Baselines fahren**

Run (Projektroot, Vordergrund, Timeout 600000): `python -m pytest backend/tests/ -q`
Expected: 204 failed (bekannte Alt-Cluster) / ≥1056 passed — **null neue Failures** (bei Abweichung: mit `git stash` gegenprüfen, ob vorbestehend).
Run: `cd frontend && npx vitest run && npm run build`
Expected: ≥159 + alle neuen Tests grün, Build grün.

- [ ] **Step 2: Doku aktualisieren + committen**

Tracking-Doc: je Bug `[x]` + Hash + kurze Umsetzungs-Notiz (Muster der S3/S4-Einträge); Status-Tabelle und Session-Tabelle pflegen. Entscheidungs-Notizen aufnehmen: (a) KW-27 ohne V9/Migration gelöst, (b) KW-28 „Feld wirksam gemacht" statt entfernt, Doc-ID wird weiter nicht gesendet, (c) KW-29 dismissed-Set entfällt (kein Auto-Open mehr), (d) KW-22-Badge sperrt das Generieren nicht. TODO.md-Block PRD-33 ergänzen, S6-Handover-Prompt schreiben (Vertagte Minors aus S4/S5 hineinziehen).

```bash
git add "docs/BUGFIX_KLAGE_WIZARD.md" "docs/TODO.md" "handover/naechste_session_PRD33_S6_prompt.md" "docs/superpowers/plans/2026-07-18-prd33-s5-wizard-state-ux.md"
git commit -m "docs(klage): PRD-33 Session 5 abgehakt (KW-22/24-29), S6-Handover"
```

- [ ] **Step 3: Finales Whole-Branch-Review (Opus, superpowers:requesting-code-review) über `ec53900b..HEAD`; Critical/Important → Fix-Wave + Re-Review**

- [ ] **Step 4: Ergebnis an RA Schatz berichten; FF-Merge nach main NUR nach ausdrücklicher Freigabe**

---

## Self-Review (durchgeführt)

- **Spec-Abdeckung:** Alle 7 Bugs aus dem S5-Handover haben je einen Task (KW-27→T1, KW-26→T2, KW-25→T3, KW-24→T4, KW-22→T5, KW-28→T6, KW-29→T7); V7 als Muster in T3/T4/T5; Abschlusspflichten in T8. ✓
- **Reihenfolge-Begründung:** T4 (Komposition) MUSS vor T5 (Dirty-Regeneration) — sonst würde Auto-Regeneration den Platzhalter neu einfügen und die alte Einbrenn-Logik bräche. T1/T2 sind unabhängig und klein (warm-up). ✓
- **Typ-/Namens-Konsistenz:** `komponiereAntraege` (T4) wird in T5-Design referenziert; `verzugEintrittDefault`/`buildVerzugAutoText` existieren (utils.js:36, KlageWizard.jsx:1451); `ANTRAEGE_PLACEHOLDER` existiert (Z.1893). ✓
- **Bekannte Restunschärfen (Implementer muss verifizieren):** exakte URL-Pfade des Klage-GET/PUT (T1), Datums-Feldname in `verzug_dokumente` (T6), DOM-Struktur der Fortschritts-Kreise (T2), genaue DokumentCard-Props in Step 6/9 (T4/T5). Jeweils als expliziter Prüf-Step im Task vermerkt. ✓
