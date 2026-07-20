# Klage-Wizard Paket 2: UI-Führung — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Status-Symbole (✓/⚠/●) im Fortschrittsbalken, Einwände als eigener Wizard-Schritt (10 → 11 Schritte) und wortweiser Inline-Diff „Änderungen anzeigen" an allen editierbaren Text-Vorschauen.

**Architecture:** Reine Logik (Wort-Diff per LCS, Schritt-Status) in neuer Datei `wizardFuehrungLogik.js`; UI-Änderungen ausschließlich in `KlageWizard.jsx`/`KlageSection.jsx`/`KlageEntwurfDialog.jsx`. Das bisherige `EinwandePanel`-Modal wird zur Inline-Komponente `EinwaendeAuswahl` im neuen Schritt 8; der zuletzt übernommene Einwände-Block wandert aus einem Komponenten-Ref in gelifteten State (`wizardEinwaendeBlock`), damit er Schrittwechsel und Entwurf-Speichern überlebt. Wegen der geänderten Schritt-Nummern wird `ENTWURF_FORMAT_VERSION` auf 2 erhöht (alte Entwürfe bieten nur „Neu beginnen").

**Tech Stack:** React 18 (JSX, Inline-Styles mit Theme `T`), Vitest + @testing-library/react, kein Backend-Anteil, keine neuen Dependencies.

**Spec:** `docs/superpowers/specs/2026-07-19-klage-wizard-ui-fuehrung-design.md`

## Global Constraints

- Zielsprache aller UI-Texte, Testnamen und Commit-Messages: **Deutsch**.
- **Keine Kommentare** im Code außer bei nicht-offensichtlichem Verhalten (CLAUDE.md).
- **Keine externe Diff-Bibliothek** — einfacher LCS auf Wortebene (Spec Baustein 3).
- Status-Symbole sind **reine Anzeige, keine neuen Sperren**; Klick-/Sprungverhalten (`kannSpringen`, kumulativ) bleibt unverändert (Spec Baustein 1).
- Der Einwände-Schritt wird **nie übersprungen** — ohne Kürzungen Hinweis + Weiter (Spec, Entscheidung 3).
- **Kein Nebeneinander-Diff, keine Diff-Bearbeitung** (Annehmen/Ablehnen einzelner Wörter) (Spec „Bewusst nicht im Scope").
- Neue Schrittfolge exakt: 1 Gericht · 2 Rubrum · 3 Aktivlegitimation · 4 Unfall · 5 Schaden · 6 Anträge · 7 Würdigung · 8 Einwände · 9 Verzug · 10 Gebühren · 11 Generieren.
- `ENTWURF_FORMAT_VERSION` wird auf **2** erhöht (Paket-1-Kopplung, Spec Baustein 2). Backend bleibt unberührt (akzeptiert jede Ganzzahl ≥ 1).
- KW-24-Vertrag bleibt: `ANTRAEGE_PLACEHOLDER` bleibt dauerhaft in `wizardAntraegeText`; nur der **Wortlaut** des Platzhalters ändert sich („Schritt 9" → „Schritt 10").
- Arbeitsbranch: `klage-wizard-ui-fuehrung` (von `main`), FF-Merge erst nach Freigabe RA Schatz.
- Alle Frontend-Kommandos laufen aus `frontend/` (`npx vitest run …`, `npm run build`).

## Ausgangslage (für Implementierer ohne Kontext)

- `frontend/src/sections/KlageWizard.jsx` (~2900 Z.): `STEPS`-Array (Z. 29), `schrittBlockiert`/`kannSpringen` (Z. 306–318), `Fortschrittsbalken` (Z. 320), `DokumentCard` (Z. 391), `EinwandePanel`-Modal (Z. 1093–1294), `StepRw` (Z. 1298–1490), `TextVeraltetBadge` (Z. 1987), `ANTRAEGE_PLACEHOLDER` (Z. 1949), `komponiereAntraege` (Z. 1952), Hauptkomponente mit Step-Wiring (Z. 2543 ff.).
- `frontend/src/sections/KlageSection.jsx`: Wizard-State (Z. 229 ff.), RVG-Lade-Effekt `wizardStep !== 9` (Z. 397), `initialisiereWizardFrisch` (Z. 481), `initialisiereWizardAusEntwurf` (Z. 557), `aktuellerEntwurf` (Z. 597).
- `frontend/src/sections/klageEntwurfLogik.js`: `ENTWURF_FORMAT_VERSION = 1`, `serialisiereEntwurf`, `parseEntwurf` (lehnt fremde Versionen ab → „Neu beginnen"-Dialog existiert bereits).
- `frontend/src/sections/parteiLogik.js`: `istPersonPartei`, `parteiAnzeigeName`, `organBezeichnung`.
- DokumentCard-Nutzungen (rechte Text-Karte): Z. 725 StepAktLeg, 822 StepUnfall, 1486 StepRw, 1680 StepVerzug, 2206 StepAntraege, 2506 StepGebuehren.

---

### Task 1: Reine Diff-Funktion `wortDiff`

**Files:**
- Create: `frontend/src/sections/wizardFuehrungLogik.js`
- Test: `frontend/src/sections/wizardFuehrungLogik.test.js`

**Interfaces:**
- Consumes: nichts (reine Funktion).
- Produces: `wortDiff(autoText, aktuellerText) → Array<{typ: "gleich"|"neu"|"weg", text: string}>`. Segmente in Textreihenfolge; bei Ersetzung kommt `weg` vor `neu`; benachbarte Tokens gleichen Typs sind zu einem Segment zusammengefasst (Wörter mit `" "` verbunden, `"\n"` bleibt als Zeichen im Segmenttext erhalten). Semantik: `neu` = nur in `aktuellerText` (grün), `weg` = nur in `autoText` (rot durchgestrichen).

- [ ] **Step 1: Failing Test schreiben**

```js
import { describe, it, expect } from "vitest";
import { wortDiff } from "./wizardFuehrungLogik.js";

describe("wortDiff", () => {
  it("identische Texte ergeben ein einziges gleich-Segment", () => {
    expect(wortDiff("Der Kläger fährt", "Der Kläger fährt")).toEqual([
      { typ: "gleich", text: "Der Kläger fährt" },
    ]);
  });

  it("Ergänzung am Ende wird als neu markiert", () => {
    expect(wortDiff("Der Kläger fährt", "Der Kläger fährt schnell")).toEqual([
      { typ: "gleich", text: "Der Kläger fährt" },
      { typ: "neu", text: "schnell" },
    ]);
  });

  it("Streichung wird als weg markiert", () => {
    expect(wortDiff("Der Kläger fährt schnell", "Der Kläger fährt")).toEqual([
      { typ: "gleich", text: "Der Kläger fährt" },
      { typ: "weg", text: "schnell" },
    ]);
  });

  it("Ersetzung liefert weg vor neu", () => {
    expect(wortDiff("Der Beklagte zahlt", "Die Beklagte zahlt")).toEqual([
      { typ: "weg", text: "Der" },
      { typ: "neu", text: "Die" },
      { typ: "gleich", text: "Beklagte zahlt" },
    ]);
  });

  it("leerer Auto-Text: alles neu; beide leer: leeres Ergebnis", () => {
    expect(wortDiff("", "Neuer Text")).toEqual([{ typ: "neu", text: "Neuer Text" }]);
    expect(wortDiff("", "")).toEqual([]);
    expect(wortDiff(null, undefined)).toEqual([]);
  });

  it("Umlaute bleiben unangetastet", () => {
    expect(wortDiff("Kürzung übernommen", "Kürzung geprüft und übernommen")).toEqual([
      { typ: "gleich", text: "Kürzung" },
      { typ: "neu", text: "geprüft und" },
      { typ: "gleich", text: "übernommen" },
    ]);
  });

  it("Zeilenumbrüche bleiben im Segmenttext erhalten", () => {
    const seg = wortDiff("Absatz eins.\n\nAbsatz zwei.", "Absatz eins.\n\nAbsatz zwei.");
    expect(seg).toEqual([{ typ: "gleich", text: "Absatz eins.\n\nAbsatz zwei." }]);
  });

  it("Änderung nach Zeilenumbruch wird erkannt", () => {
    const seg = wortDiff("Satz eins.\nSatz zwei.", "Satz eins.\nSatz drei.");
    expect(seg).toEqual([
      { typ: "gleich", text: "Satz eins.\nSatz" },
      { typ: "weg", text: "zwei." },
      { typ: "neu", text: "drei." },
    ]);
  });
});
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `npx vitest run src/sections/wizardFuehrungLogik.test.js`
Expected: FAIL — `Cannot find module './wizardFuehrungLogik.js'` (o. ä.).

- [ ] **Step 3: Implementierung schreiben**

```js
// Klage-Wizard UI-Fuehrung (Paket 2): reine Logik ohne React/API.

function tokenisiere(text) {
  return String(text ?? "")
    .split(/(\n)/)
    .flatMap(teil => (teil === "\n" ? ["\n"] : teil.split(/[^\S\n]+/).filter(Boolean)));
}

function fasseZusammen(roh) {
  const segmente = [];
  roh.forEach(({ typ, token }) => {
    const letzt = segmente[segmente.length - 1];
    if (letzt && letzt.typ === typ) {
      const nahtlos = token === "\n" || letzt.text.endsWith("\n");
      letzt.text += nahtlos ? token : ` ${token}`;
    } else {
      segmente.push({ typ, text: token });
    }
  });
  return segmente;
}

export function wortDiff(autoText, aktuellerText) {
  const a = tokenisiere(autoText);
  const b = tokenisiere(aktuellerText);
  const n = a.length, m = b.length;
  const lcs = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      lcs[i][j] = a[i] === b[j]
        ? lcs[i + 1][j + 1] + 1
        : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
    }
  }
  const roh = [];
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) { roh.push({ typ: "gleich", token: a[i] }); i++; j++; }
    else if (lcs[i + 1][j] >= lcs[i][j + 1]) { roh.push({ typ: "weg", token: a[i] }); i++; }
    else { roh.push({ typ: "neu", token: b[j] }); j++; }
  }
  while (i < n) { roh.push({ typ: "weg", token: a[i] }); i++; }
  while (j < m) { roh.push({ typ: "neu", token: b[j] }); j++; }
  return fasseZusammen(roh);
}
```

- [ ] **Step 4: Test laufen lassen — muss grün sein**

Run: `npx vitest run src/sections/wizardFuehrungLogik.test.js`
Expected: PASS (8 Tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/sections/wizardFuehrungLogik.js frontend/src/sections/wizardFuehrungLogik.test.js
git commit -m "feat(klage): wortweise Diff-Funktion wortDiff (LCS) fuer Aenderungs-Ansicht"
```

---

### Task 2: Schritt-Status-Logik `schrittStatus` + `firmenOhneVertreter`

**Files:**
- Modify: `frontend/src/sections/parteiLogik.js` (Umzug `kanonischeBeklagte`)
- Modify: `frontend/src/sections/KlageWizard.jsx` (Import + Re-Export statt lokaler Definition)
- Modify: `frontend/src/sections/wizardFuehrungLogik.js`
- Test: `frontend/src/sections/wizardFuehrungLogik.test.js` (erweitern)

**Interfaces:**
- Consumes: `kanonischeBeklagte(beklagte)` — Filter `b.rolle_klage !== "klaeger" && b.checked !== false` (zieht von `KlageWizard.jsx` Z. 54–56 nach `parteiLogik.js` um; Re-Export in `KlageWizard.jsx` hält bestehende Test-Imports grün).
- Produces:
  - `firmenOhneVertreter(beklagte) → Array` (kanonische Beklagte mit `(versicherung || firma) && !vertreter_name` — identisches Kriterium wie `StepZusammenfassung` Z. 1704).
  - `schrittWarnung(nr, ctx) → string | null`
  - `schrittStatus(nr, ctx) → { zustand: "aktiv"|"warnung"|"erledigt"|"offen", warnung: string|null }` mit `ctx = { step, maxStep, gerichtBestaetigt, positionen, beklagte, antraegeVeraltet, hatPlatzhalter }`. Präzedenz: `nr === step` → aktiv; `nr > maxStep` → offen; Warnung vorhanden → warnung; sonst erledigt.

- [ ] **Step 1: Failing Tests ergänzen** (in `wizardFuehrungLogik.test.js` anhängen)

```js
import { schrittStatus, schrittWarnung, firmenOhneVertreter } from "./wizardFuehrungLogik.js";

const CTX_OK = {
  step: 3, maxStep: 6, gerichtBestaetigt: true,
  positionen: [{ checked: true }],
  beklagte: [
    { rolle_klage: "klaeger", name: "Muster" },
    { versicherung: "ADAC Autoversicherung AG", vertreter_name: "Stefan Daehne", checked: true },
  ],
  antraegeVeraltet: false, hatPlatzhalter: false,
};

describe("firmenOhneVertreter", () => {
  it("liefert kanonische Firmen-Beklagte ohne vertreter_name", () => {
    const beklagte = [
      { rolle_klage: "klaeger", firma: "Ignorier GmbH" },
      { versicherung: "HUK", vertreter_name: "", checked: true },
      { firma: "Abgewaehlt AG", checked: false },
      { name: "Privatperson", anrede: "1", checked: true },
    ];
    expect(firmenOhneVertreter(beklagte).map(b => b.versicherung || b.firma)).toEqual(["HUK"]);
  });
});

describe("schrittWarnung", () => {
  it("Schritt 1: Gericht nicht bestaetigt", () => {
    expect(schrittWarnung(1, { ...CTX_OK, gerichtBestaetigt: false }))
      .toBe("Gericht nicht bestätigt — in Schritt 1 bestätigen.");
    expect(schrittWarnung(1, CTX_OK)).toBeNull();
  });
  it("Schritt 2: Firma ohne Vertreter mit Namen", () => {
    const ctx = { ...CTX_OK, beklagte: [{ versicherung: "HUK", checked: true }] };
    expect(schrittWarnung(2, ctx)).toBe("Vertreter fehlt: HUK — Lookup in der Parteien-Karte.");
    expect(schrittWarnung(2, CTX_OK)).toBeNull();
  });
  it("Schritt 5: keine Position angehakt", () => {
    expect(schrittWarnung(5, { ...CTX_OK, positionen: [{ checked: false }] }))
      .toBe("Keine Schadenposition ausgewählt.");
    expect(schrittWarnung(5, CTX_OK)).toBeNull();
  });
  it("Schritt 6: veraltet und/oder Platzhalter", () => {
    expect(schrittWarnung(6, { ...CTX_OK, antraegeVeraltet: true }))
      .toBe("Antragstext veraltet — in Schritt 6 neu generieren.");
    expect(schrittWarnung(6, { ...CTX_OK, hatPlatzhalter: true }))
      .toBe("RVG-Platzhalter noch im Antragstext — Schritt 10 (Gebühren) aufrufen.");
    expect(schrittWarnung(6, { ...CTX_OK, antraegeVeraltet: true, hatPlatzhalter: true }))
      .toBe("Antragstext veraltet — in Schritt 6 neu generieren. RVG-Platzhalter noch im Antragstext — Schritt 10 (Gebühren) aufrufen.");
  });
  it("andere Schritte: nie Warnung", () => {
    [3, 4, 7, 8, 9, 10, 11].forEach(nr => expect(schrittWarnung(nr, CTX_OK)).toBeNull());
  });
});

describe("schrittStatus", () => {
  it("aktueller Schritt ist aktiv, auch mit Warnung", () => {
    expect(schrittStatus(3, CTX_OK).zustand).toBe("aktiv");
    const ctx = { ...CTX_OK, step: 1, gerichtBestaetigt: false };
    expect(schrittStatus(1, ctx)).toEqual({
      zustand: "aktiv", warnung: "Gericht nicht bestätigt — in Schritt 1 bestätigen.",
    });
  });
  it("nicht erreichte Schritte sind offen", () => {
    expect(schrittStatus(7, CTX_OK)).toEqual({ zustand: "offen", warnung: null });
    expect(schrittStatus(11, CTX_OK)).toEqual({ zustand: "offen", warnung: null });
  });
  it("besuchte Schritte ohne Warnung sind erledigt", () => {
    expect(schrittStatus(4, CTX_OK)).toEqual({ zustand: "erledigt", warnung: null });
  });
  it("Warnung ersetzt erledigt bei besuchten Schritten", () => {
    const ctx = { ...CTX_OK, step: 6, positionen: [{ checked: false }] };
    expect(schrittStatus(5, ctx)).toEqual({
      zustand: "warnung", warnung: "Keine Schadenposition ausgewählt.",
    });
  });
});
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `npx vitest run src/sections/wizardFuehrungLogik.test.js`
Expected: FAIL — `schrittStatus is not a function` (o. ä.); die 8 wortDiff-Tests bleiben grün.

- [ ] **Step 3: `kanonischeBeklagte` umziehen**

In `parteiLogik.js` ans Dateiende anfügen:

```js
export function kanonischeBeklagte(beklagte) {
  return (beklagte || []).filter(b => b.rolle_klage !== "klaeger" && b.checked !== false);
}
```

In `KlageWizard.jsx` die lokale Definition (Z. 54–56) **löschen** und die Import-Zeile (Z. 25) erweitern + Re-Export direkt darunter (hält Test-Imports `import { kanonischeBeklagte } from "./KlageWizard.jsx"` grün):

```js
import { istPersonPartei, parteiAnzeigeName, organBezeichnung, kanonischeBeklagte } from "./parteiLogik.js";
export { kanonischeBeklagte };
```

- [ ] **Step 4: Status-Logik implementieren** (in `wizardFuehrungLogik.js` anfügen)

```js
import { kanonischeBeklagte } from "./parteiLogik.js";

export function firmenOhneVertreter(beklagte) {
  return kanonischeBeklagte(beklagte).filter(b => (b.versicherung || b.firma) && !b.vertreter_name);
}

export function schrittWarnung(nr, ctx) {
  if (nr === 1 && !ctx.gerichtBestaetigt) {
    return "Gericht nicht bestätigt — in Schritt 1 bestätigen.";
  }
  if (nr === 2) {
    const ohne = firmenOhneVertreter(ctx.beklagte);
    if (ohne.length > 0) {
      const namen = ohne.map(b => b.versicherung || b.firma || b.name).join(", ");
      return `Vertreter fehlt: ${namen} — Lookup in der Parteien-Karte.`;
    }
  }
  if (nr === 5 && !(ctx.positionen || []).some(p => p.checked)) {
    return "Keine Schadenposition ausgewählt.";
  }
  if (nr === 6) {
    const teile = [];
    if (ctx.antraegeVeraltet) teile.push("Antragstext veraltet — in Schritt 6 neu generieren.");
    if (ctx.hatPlatzhalter) teile.push("RVG-Platzhalter noch im Antragstext — Schritt 10 (Gebühren) aufrufen.");
    if (teile.length) return teile.join(" ");
  }
  return null;
}

export function schrittStatus(nr, ctx) {
  if (nr === ctx.step) return { zustand: "aktiv", warnung: schrittWarnung(nr, ctx) };
  if (nr > ctx.maxStep) return { zustand: "offen", warnung: null };
  const warnung = schrittWarnung(nr, ctx);
  return warnung ? { zustand: "warnung", warnung } : { zustand: "erledigt", warnung: null };
}
```

- [ ] **Step 5: Tests laufen lassen**

Run: `npx vitest run src/sections/wizardFuehrungLogik.test.js src/sections/parteiLogik.test.js`
Expected: PASS. Danach Regressionscheck der Wizard-Suiten, die `kanonischeBeklagte` aus `KlageWizard.jsx` importieren:

Run: `npx vitest run src/sections/`
Expected: alle grün (Re-Export hält die Imports stabil).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/sections/wizardFuehrungLogik.js frontend/src/sections/wizardFuehrungLogik.test.js frontend/src/sections/parteiLogik.js frontend/src/sections/KlageWizard.jsx
git commit -m "feat(klage): schrittStatus/schrittWarnung als reine Fortschritts-Logik; kanonischeBeklagte nach parteiLogik"
```

---

### Task 3: `EinwaendeAuswahl` aus dem Modal extrahieren

**Files:**
- Modify: `frontend/src/sections/KlageWizard.jsx` (Z. 1093–1294: `EinwandePanel`)
- Test: `frontend/src/sections/KlageWizard.einwaende.test.jsx` (neu)

**Interfaces:**
- Consumes: bestehende Bausteine im selben File: `KATEGORIE_ORDER`, `EINLEITUNGS_VARIANTEN`, `EINLEITUNG_LETZT`, `versichererSuffix`, `fmtEuro`.
- Produces: `export function EinwaendeAuswahl({ abrechnungen, kuerzungsarten, beklagte, onUebernehmen })` — rendert die gruppierte Kürzungsarten-Auswahl (Checkboxen, Vorauswahl = in Abrechnungen erfasste `kuerzungsart_id`s), Fußzeile „N ausgewählt" und Button **„Text übernehmen"**; Klick ruft `onUebernehmen(text)` mit dem generierten Einwände-Block (bei leerer Auswahl `onUebernehmen("")`). Kein Modal, kein `onClose`. `EinwandePanel` bleibt vorerst als dünne Modal-Hülle bestehen, die `EinwaendeAuswahl` rendert (wird in Task 4 gelöscht).

- [ ] **Step 1: Failing Test schreiben**

```jsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EinwaendeAuswahl } from "./KlageWizard.jsx";

const KUERZUNGSARTEN = [
  { id: 1, bezeichnung: "Stundenverrechnungssatz", kategorie: "reparatur", varianten: [] },
  { id: 2, bezeichnung: "Verbringungskosten", kategorie: "reparatur", varianten: [] },
];
const ABRECHNUNGEN = [{
  gesamt_reguliert: "1000",
  positionen: [{ kuerzungsart_id: 1, betrag_gefordert: "500", betrag_reguliert: "300" }],
}];

describe("EinwaendeAuswahl", () => {
  it("erfasste Kuerzungsarten sind vorausgewaehlt", () => {
    render(<EinwaendeAuswahl abrechnungen={ABRECHNUNGEN} kuerzungsarten={KUERZUNGSARTEN}
      beklagte={[]} onUebernehmen={() => {}} />);
    expect(screen.getByText(/1 ausgewählt/)).toBeTruthy();
  });

  it("Text uebernehmen liefert Block mit Bezeichnung und Kuerzungsbetrag", () => {
    const onUebernehmen = vi.fn();
    render(<EinwaendeAuswahl abrechnungen={ABRECHNUNGEN} kuerzungsarten={KUERZUNGSARTEN}
      beklagte={[]} onUebernehmen={onUebernehmen} />);
    fireEvent.click(screen.getByText(/Text übernehmen/));
    const text = onUebernehmen.mock.calls[0][0];
    expect(text).toContain("Stundenverrechnungssatz");
    expect(text).toContain("200,00");
  });

  it("leere Auswahl liefert leeren String", () => {
    const onUebernehmen = vi.fn();
    render(<EinwaendeAuswahl abrechnungen={[]} kuerzungsarten={KUERZUNGSARTEN}
      beklagte={[]} onUebernehmen={onUebernehmen} />);
    fireEvent.click(screen.getByText(/Text übernehmen/));
    expect(onUebernehmen).toHaveBeenCalledWith("");
  });
});
```

Hinweis: Falls die Kürzungsarten-Zeilen im Bestand weitere Pflichtfelder erwarten (z. B. `varianten`), Fixture beim Implementieren an die tatsächliche Render-Erwartung anpassen — Verhalten, nicht Markup, ist Testgegenstand.

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `npx vitest run src/sections/KlageWizard.einwaende.test.jsx`
Expected: FAIL — `EinwaendeAuswahl` wird nicht exportiert.

- [ ] **Step 3: Extraktion durchführen**

In `KlageWizard.jsx`: den gesamten Rumpf von `EinwandePanel` (State `checked`, `aktiveIds`, `gruppen`, `uebernehmen`, Listen-Rendering, Fußzeile) in eine neue exportierte Komponente `EinwaendeAuswahl({ abrechnungen, kuerzungsarten, beklagte, onUebernehmen })` verschieben. Änderungen gegenüber dem Original:
  - Kein Modal-Wrapper (kein `position: fixed`-Backdrop), stattdessen äußerer Container `<div style={{ display: "flex", flexDirection: "column", border: \`1px solid ${T.borderSoft}\`, borderRadius: 10, background: T.white, maxHeight: 480, overflow: "hidden" }}>` mit scrollender Liste (`overflowY: "auto"` am Listen-Container).
  - Fußzeile ohne „Abbrechen"-Button; Übernehmen-Button-Label: **„Text übernehmen"** (ohne Pfeil).
  - `EinwandePanel({ abrechnungen, kuerzungsarten, beklagte, onUebernehmen, onClose })` bleibt bestehen und rendert nur noch: Backdrop + Kopfzeile + `<EinwaendeAuswahl …/>` + Schließen-Button (`onClose`); `onUebernehmen` wird durchgereicht.

- [ ] **Step 4: Tests laufen lassen**

Run: `npx vitest run src/sections/KlageWizard.einwaende.test.jsx src/sections/KlageWizard.haftungsquote.test.jsx`
Expected: PASS — neue Tests grün, StepRw-Tests unverändert grün (Modal funktioniert weiter).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/sections/KlageWizard.jsx frontend/src/sections/KlageWizard.einwaende.test.jsx
git commit -m "refactor(klage): EinwaendeAuswahl als Inline-Komponente aus EinwandePanel extrahiert"
```

---

### Task 4: Schrittfolge 10 → 11 — Einwände als eigener Schritt

**Files:**
- Modify: `frontend/src/sections/KlageWizard.jsx`
- Modify: `frontend/src/sections/KlageSection.jsx`
- Modify: `frontend/src/sections/KlageWizard.gebuehren.test.jsx` (hartkodierter Platzhalter-String Z. 16)
- Test: `frontend/src/sections/KlageWizard.einwaende.test.jsx` (erweitern)

**Interfaces:**
- Consumes: `EinwaendeAuswahl` (Task 3), `buildRwVorschau(hb, hq, gesamtReg, weiblich, hqTyp, beklagte)` (bestehend, Z. 247), `DokumentCard`.
- Produces:
  - `export function StepEinwaende({ abrechnungen, kuerzungsarten, beklagte, rwText, onRwText, einwaendeBlock, onEinwaendeBlock, grundhaftungsText })` — neuer Schritt 8.
  - `STEPS` mit 11 Einträgen; `StepRw` ohne Einwände-Button/Modal, rechte Karte read-only.
  - Neuer gelifteter State in `KlageSection`: `wizardEinwaendeBlock: string` (Ersatz für `einwaendeEingefuegtRef`), Props an `KlageWizard`: `wizardEinwaendeBlock`, `onWizardEinwaendeBlock`.
  - `ANTRAEGE_PLACEHOLDER = "[Außergerichtliche Anwaltsgebühren – wird in Schritt 10 ergänzt]"` (Wortlaut-Änderung; Task 8 der Gebühren bleibt inhaltlich gleich).

- [ ] **Step 1: Failing Tests schreiben** (in `KlageWizard.einwaende.test.jsx` anhängen)

```jsx
import { StepEinwaende } from "./KlageWizard.jsx";

describe("StepEinwaende", () => {
  it("ohne erfasste Kuerzungen: Hinweis statt Auswahlliste, Textkarte bleibt", () => {
    render(<StepEinwaende abrechnungen={[]} kuerzungsarten={KUERZUNGSARTEN} beklagte={[]}
      rwText="Grundtext" onRwText={() => {}} einwaendeBlock="" onEinwaendeBlock={() => {}}
      grundhaftungsText="Grundtext" />);
    expect(screen.getByText(/Keine Kürzungen der Versicherung erfasst/)).toBeTruthy();
    expect(screen.queryByText(/Text übernehmen/)).toBeNull();
    expect(screen.getByDisplayValue("Grundtext")).toBeTruthy();
  });

  it("Uebernehmen haengt Block an rwText an und meldet ihn als einwaendeBlock", () => {
    const onRwText = vi.fn(), onEinwaendeBlock = vi.fn();
    render(<StepEinwaende abrechnungen={ABRECHNUNGEN} kuerzungsarten={KUERZUNGSARTEN} beklagte={[]}
      rwText="Grundtext" onRwText={onRwText} einwaendeBlock="" onEinwaendeBlock={onEinwaendeBlock}
      grundhaftungsText="Grundtext" />);
    fireEvent.click(screen.getByText(/Text übernehmen/));
    const block = onEinwaendeBlock.mock.calls[0][0];
    expect(block).toContain("Stundenverrechnungssatz");
    expect(onRwText).toHaveBeenCalledWith(`Grundtext\n\n${block}`);
  });

  it("erneutes Uebernehmen ersetzt den alten Block statt anzuhaengen", () => {
    const onRwText = vi.fn();
    render(<StepEinwaende abrechnungen={ABRECHNUNGEN} kuerzungsarten={KUERZUNGSARTEN} beklagte={[]}
      rwText={"Grundtext\n\nALTER BLOCK"} onRwText={onRwText}
      einwaendeBlock="ALTER BLOCK" onEinwaendeBlock={() => {}}
      grundhaftungsText="Grundtext" />);
    fireEvent.click(screen.getByText(/Text übernehmen/));
    const neuerText = onRwText.mock.calls[0][0];
    expect(neuerText.startsWith("Grundtext\n\n")).toBe(true);
    expect(neuerText).not.toContain("ALTER BLOCK");
    expect(neuerText).toContain("Stundenverrechnungssatz");
  });
});
```

(`STEPS` selbst wird über den Header-Text der Hauptkomponente indirekt getestet; ein direkter `STEPS`-Export ist nicht nötig.)

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `npx vitest run src/sections/KlageWizard.einwaende.test.jsx`
Expected: FAIL — `StepEinwaende` existiert nicht.

- [ ] **Step 3: Umbau in `KlageWizard.jsx`**

3a. `STEPS` (Z. 29–40) ersetzen:

```js
const STEPS = [
  { nr: 1,  label: "Gericht"   },
  { nr: 2,  label: "Rubrum"    },
  { nr: 3,  label: "Aktiv."    },
  { nr: 4,  label: "Unfall"    },
  { nr: 5,  label: "Schaden"   },
  { nr: 6,  label: "Anträge"   },
  { nr: 7,  label: "Würdigung" },
  { nr: 8,  label: "Einwände"  },
  { nr: 9,  label: "Verzug"    },
  { nr: 10, label: "Gebühren"  },
  { nr: 11, label: "Generieren"},
];
```

Datei-Kopf-Docblock (Z. 6–15) auf die 11 Schritte aktualisieren (Step 7 „Rechtl. Würdigung – Quote + Begründung + Vorschau", Step 8 „Einwände – Kürzungen + finaler Würdigungstext", 9 Verzug, 10 Gebühren, 11 Zusammenfassung).

3b. `StepRw` (Z. 1298–1490) verschlanken:
  - Entfernen: `const [einwandeOffen, setEinwandeOffen] = useState(false);`, `einwaendeEingefuegtRef`, Funktion `einwandeUebernehmen`, das `{einwandeOffen && <EinwandePanel …/>}`-Fragment und den Button „⚔ Kürzungen & Einwände" (Z. 1457–1479) samt Zähler-Badge.
  - Rechte Karte read-only: `<DokumentCard text={rwText} />` statt `editText`/`onEditText`.
  - Fußnote (Z. 1481–1483) neu: `Vorschau der Grundhaftung. Einwände und Feinschliff folgen in Schritt 8 — dort ist der Text editierbar.`
  - Props `rwText, onRwText, kuerzungsarten` bleiben in der Signatur (onRwText wird weiterhin von `neuGenerieren`/`fallauswaehlen` genutzt; `kuerzungsarten` entfällt aus der Signatur, da unbenutzt — aus Aufrufstelle mit entfernen).

3c. `DokumentCard` (Z. 391 ff.): Read-only-Variante sauber machen — am `<textarea>` `readOnly={!onEditText}` ergänzen und den „(editierbar)"-Hinweis (Z. 432–434) nur rendern, wenn `onEditText` gesetzt ist.

3d. `EinwandePanel`-Modal-Hülle (Rest aus Task 3) **löschen** — einziger Nutzer war StepRw.

3e. Neue Komponente `StepEinwaende` (nach `StepRw` einfügen):

```jsx
export function StepEinwaende({ abrechnungen, kuerzungsarten, beklagte,
                                rwText, onRwText,
                                einwaendeBlock, onEinwaendeBlock,
                                grundhaftungsText }) {
  const erfasst = (abrechnungen || []).some(ab =>
    (ab.positionen || []).some(p => p.kuerzungsart_id != null));

  function uebernehmen(neuerText) {
    if (!neuerText) return;
    if (einwaendeBlock && rwText && rwText.includes(einwaendeBlock)) {
      onRwText(rwText.replace(einwaendeBlock, neuerText));
    } else {
      onRwText((rwText ? rwText + "\n\n" : "") + neuerText);
    }
    onEinwaendeBlock(neuerText);
  }

  return (
    <div style={{ display: "flex", gap: "1.5rem", alignItems: "stretch" }}>
      <div style={{ flex: "0 0 340px", display: "flex", flexDirection: "column", gap: "0.9rem" }}>
        <AbschnittLabel text="Kürzungen & Einwände" />
        {erfasst ? (
          <EinwaendeAuswahl abrechnungen={abrechnungen} kuerzungsarten={kuerzungsarten}
            beklagte={beklagte} onUebernehmen={uebernehmen} />
        ) : (
          <div style={{ background: T.surface, border: `1px solid ${T.borderSoft}`,
            borderRadius: 8, padding: "0.9rem 1rem",
            fontFamily: PLEX, fontSize: "0.85rem", color: T.textMuted, lineHeight: 1.6 }}>
            Keine Kürzungen der Versicherung erfasst. Sie können direkt mit „Weiter" fortfahren.
          </div>
        )}
        <div style={{ fontFamily: PLEX, fontSize: "0.72rem", color: T.textFaint, marginTop: "auto" }}>
          Rechts steht der vollständige Text der rechtlichen Würdigung — hier finalisieren.
        </div>
      </div>
      <DokumentCard editText={rwText} onEditText={onRwText} />
    </div>
  );
}
```

(`grundhaftungsText` bleibt vorerst unbenutzt in der Signatur — Task 8 nutzt ihn für die Diff-Basis; er wird ab jetzt von der Hauptkomponente übergeben.)

3f. Hauptkomponente:
  - Props ergänzen: `wizardEinwaendeBlock, onWizardEinwaendeBlock` (im Block „Step 7 (Rechtliche Würdigung)" der Prop-Liste).
  - Nach `const weiblich = …` (Z. 2615) ergänzen:

```js
  const gesamtReg = (abrechnungen || []).reduce((s, ab) => s + (parseFloat(ab.gesamt_reguliert) || 0), 0);
  const grundhaftungsText = buildRwVorschau(wizardHb, wizardHq, gesamtReg, weiblich, wizardHqTyp, beklagte);
```

  - Step-Rendering: `{step === 7 && <StepRw …/>}` behält alle Props außer `kuerzungsarten`; neu dazwischen:

```jsx
            {step === 8 && (
              <StepEinwaende
                abrechnungen={abrechnungen}
                kuerzungsarten={kuerzungsarten}
                beklagte={beklagte}
                rwText={wizardRwText}       onRwText={onWizardRwText}
                einwaendeBlock={wizardEinwaendeBlock}
                onEinwaendeBlock={onWizardEinwaendeBlock}
                grundhaftungsText={grundhaftungsText}
              />
            )}
```

  - Bisherige Blöcke umnummerieren: `step === 8` (StepVerzug) → `step === 9`; `step === 9` (StepGebuehren) → `step === 10`; `step === 10` (StepZusammenfassung) → `step === 11`. Props unverändert.

3g. Schritt-Nummern in Texten:
  - Z. 1949: `export const ANTRAEGE_PLACEHOLDER = "[Außergerichtliche Anwaltsgebühren – wird in Schritt 10 ergänzt]";`
  - Z. 2193: `⏳ RVG-Antrag: Platzhalter aktiv – wird in Schritt 10 ersetzt.`
  - Z. 2199: `✓ RVG-Antrag eingefügt (Schritt 10).`
  - Z. 1768–1769 (StepZusammenfassung): `Bitte Schritt 10 (Gebühren) aufrufen, damit der RVG-Antrag eingesetzt wird.`

3h. `KlageSection.jsx`:
  - State (bei den Wizard-States, nach Z. 242): `const [wizardEinwaendeBlock, setWizardEinwaendeBlock] = useState("");`
  - `initialisiereWizardFrisch` (nach `setWizardRwText(…)`, Z. 507): `setWizardEinwaendeBlock("");`
  - RVG-Lade-Effekt Z. 397: `if (!wizardOffen || wizardStep !== 10 || wizardRvgAussergData) return;`
  - Prop-Durchreichung an `<KlageWizard …>` (beim `wizardRwText`-Block): `wizardEinwaendeBlock={wizardEinwaendeBlock}` und `onWizardEinwaendeBlock={setWizardEinwaendeBlock}`.

3i. `KlageWizard.gebuehren.test.jsx` Z. 16: hartkodierten String auf `"2. [Außergerichtliche Anwaltsgebühren – wird in Schritt 10 ergänzt]"` ändern.

- [ ] **Step 4: Tests laufen lassen**

Run: `npx vitest run src/sections/`
Expected: neue StepEinwaende-Tests PASS; bestehende Suiten grün. Erwartbare, gezielt zu fixende Bruchstellen (nur Nummern/Labels, kein Verhaltens-Change): Assertions auf „Schritt 9" in `KlageWizard.gebuehren.test.jsx` / `KlageWizard.zusammenfassung.test.jsx`, Step-Wiring-Erwartungen in `KlageSection.verzugdok.test.jsx` / `KlageSection.rvgOverride.test.jsx` (falls dort `wizardStep`-Werte 8/9/10 gesetzt werden → auf 9/10/11 heben). Kein Test darf inhaltlich abgeschwächt werden.

Run: `npm run build`
Expected: Build grün.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/sections/KlageWizard.jsx frontend/src/sections/KlageSection.jsx frontend/src/sections/KlageWizard.einwaende.test.jsx frontend/src/sections/KlageWizard.gebuehren.test.jsx
git commit -m "feat(klage): Einwaende als eigener Wizard-Schritt 8 (10 -> 11 Schritte), StepRw nur noch Quote/Begruendung/Vorschau"
```

(Weitere in Step 4 angepasste Testdateien mit `git add` einzeln ergänzen.)

---

### Task 5: Entwurf-Format v2 (`format_version` 2 + `wizardEinwaendeBlock`)

**Files:**
- Modify: `frontend/src/sections/klageEntwurfLogik.js`
- Modify: `frontend/src/sections/KlageSection.jsx` (`aktuellerEntwurf`, `initialisiereWizardAusEntwurf`)
- Modify: `frontend/src/sections/KlageEntwurfDialog.jsx` (Z. 16: „von 10" → „von 11")
- Test: `frontend/src/sections/klageEntwurfLogik.test.js` (erweitern/anpassen)

**Interfaces:**
- Consumes: State `wizardEinwaendeBlock` (Task 4).
- Produces: `ENTWURF_FORMAT_VERSION = 2`; `serialisiereEntwurf` enthält zusätzlich `wizardEinwaendeBlock: string`. `parseEntwurf` lehnt v1-Zeilen ab (bestehende Logik `row.format_version !== ENTWURF_FORMAT_VERSION` — dadurch erscheint bei Alt-Entwürfen automatisch der vorhandene „mismatch"-Dialog mit „Neu beginnen").

- [ ] **Step 1: Failing Tests schreiben** (in `klageEntwurfLogik.test.js`)

```js
it("ENTWURF_FORMAT_VERSION ist 2 (Paket-2-Schrittumbau)", () => {
  expect(ENTWURF_FORMAT_VERSION).toBe(2);
});

it("serialisiereEntwurf enthaelt wizardEinwaendeBlock", () => {
  const e = serialisiereEntwurf({ wizardEinwaendeBlock: "a) Stundenverrechnungssatz …" });
  expect(e.wizardEinwaendeBlock).toBe("a) Stundenverrechnungssatz …");
  expect(serialisiereEntwurf({}).wizardEinwaendeBlock).toBe("");
});

it("parseEntwurf lehnt Alt-Entwuerfe mit format_version 1 ab", () => {
  const row = { entwurf_json: JSON.stringify({ wizardStep: 5 }), format_version: 1 };
  expect(parseEntwurf(row)).toEqual({ ok: false });
});
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `npx vitest run src/sections/klageEntwurfLogik.test.js`
Expected: FAIL (Version noch 1, Feld fehlt). Bestehende Tests, die `format_version: 1` als **gültig** fixieren, in diesem Zug auf 2 heben (nicht löschen — Verhalten „nur exakt aktuelle Version ist ok" bleibt getestet).

- [ ] **Step 3: Implementieren**

`klageEntwurfLogik.js`:
- `export const ENTWURF_FORMAT_VERSION = 2;`
- In `serialisiereEntwurf` nach `wizardRwText: s.wizardRwText,` einfügen: `wizardEinwaendeBlock: s.wizardEinwaendeBlock ?? "",`

`KlageSection.jsx`:
- `aktuellerEntwurf()` (Z. 597 ff.): `wizardEinwaendeBlock,` in das Argument-Objekt aufnehmen (beim `wizardRwText`-Eintrag).
- `initialisiereWizardAusEntwurf` (nach `setWizardRwText(…)`, Z. 568): `setWizardEinwaendeBlock(e.wizardEinwaendeBlock ?? "");`

`KlageEntwurfDialog.jsx` Z. 16: `(Schritt {step} von 11) — fortsetzen oder neu beginnen?`

- [ ] **Step 4: Tests laufen lassen**

Run: `npx vitest run src/sections/klageEntwurfLogik.test.js src/sections/KlageSection.entwurf.test.jsx src/sections/KlageWizard.entwurf.test.jsx src/sections/KlageEntwurfDialog.test.jsx`
Expected: PASS (Dialog-Test ggf. „von 10" → „von 11" anpassen).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/sections/klageEntwurfLogik.js frontend/src/sections/klageEntwurfLogik.test.js frontend/src/sections/KlageSection.jsx frontend/src/sections/KlageEntwurfDialog.jsx
git commit -m "feat(klage): Entwurf-Format v2 — wizardEinwaendeBlock serialisiert, Alt-Entwuerfe bieten Neu-beginnen"
```

(Ggf. angepasste Entwurf-Testdateien mit committen.)

---

### Task 6: Status-Symbole im Fortschrittsbalken

**Files:**
- Modify: `frontend/src/sections/KlageWizard.jsx` (`Fortschrittsbalken` Z. 320–368, Hauptkomponente)
- Test: `frontend/src/sections/KlageWizard.fortschritt.test.jsx` (neu)

**Interfaces:**
- Consumes: `schrittStatus` aus `./wizardFuehrungLogik.js` (Task 2), `komponiereAntraege`, `ANTRAEGE_PLACEHOLDER`, vorhandenes `antraegeVeraltet` (Hauptkomponente Z. 2623).
- Produces: `Fortschrittsbalken({ step, maxStep, onStepChange, springenErlaubt, statusFuer })` — `statusFuer(nr) → { zustand, warnung }` ist **optional**; ohne Prop verhält sich die Komponente wie bisher (hält `KlageWizard.springen.test.jsx` grün). Kreis-Inhalt: `warnung` → „⚠" (amber), `erledigt` → „✓" (navy), sonst Schrittnummer; `aktiv` behält Accent-Ring; `offen` bleibt ausgegraut. `title`-Attribut am Kreis = Warntext (Tooltip).

- [ ] **Step 1: Failing Test schreiben**

```jsx
import { describe, it, expect, vi } from "vitest";
import { render, fireEvent } from "@testing-library/react";
import { Fortschrittsbalken } from "./KlageWizard.jsx";

const STATUS = {
  1: { zustand: "erledigt", warnung: null },
  2: { zustand: "warnung", warnung: "Vertreter fehlt: HUK — Lookup in der Parteien-Karte." },
  3: { zustand: "aktiv", warnung: null },
};
const statusFuer = nr => STATUS[nr] || { zustand: "offen", warnung: null };

describe("Fortschrittsbalken mit Status-Symbolen", () => {
  it("zeigt Haken, Warnsymbol mit Tooltip und Nummer fuer offene Schritte", () => {
    const { getByText, getByTitle } = render(
      <Fortschrittsbalken step={3} maxStep={3} onStepChange={() => {}} statusFuer={statusFuer} />
    );
    expect(getByText("✓")).toBeTruthy();
    const warnKreis = getByTitle("Vertreter fehlt: HUK — Lookup in der Parteien-Karte.");
    expect(warnKreis.textContent).toBe("⚠");
    expect(getByText("4")).toBeTruthy();
  });

  it("Warnsymbol sperrt den Klick nicht (reine Anzeige)", () => {
    const onStepChange = vi.fn();
    const { getByTitle } = render(
      <Fortschrittsbalken step={3} maxStep={3} onStepChange={onStepChange} statusFuer={statusFuer} />
    );
    fireEvent.click(getByTitle("Vertreter fehlt: HUK — Lookup in der Parteien-Karte."));
    expect(onStepChange).toHaveBeenCalledWith(2);
  });
});
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `npx vitest run src/sections/KlageWizard.fortschritt.test.jsx`
Expected: FAIL — `statusFuer` unbekannt, „⚠" nicht gerendert.

- [ ] **Step 3: Implementieren**

`Fortschrittsbalken` umbauen (Verhalten ohne `statusFuer` unverändert):

```jsx
export function Fortschrittsbalken({ step, maxStep, onStepChange, springenErlaubt, statusFuer }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 0, marginBottom: "1.5rem" }}>
      {STEPS.map((s, i) => {
        const status    = statusFuer ? statusFuer(s.nr)
                          : { zustand: s.nr === step ? "aktiv" : s.nr < step ? "erledigt" : "offen", warnung: null };
        const aktiv     = status.zustand === "aktiv";
        const warnung   = status.zustand === "warnung";
        const erledigt  = status.zustand === "erledigt";
        const klickbar  = s.nr <= maxStep && s.nr !== step && (!springenErlaubt || springenErlaubt(s.nr));
        return (
          <React.Fragment key={s.nr}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", flex: 1, minWidth: 0 }}>
              <div
                onClick={klickbar ? () => onStepChange(s.nr) : undefined}
                title={status.warnung || undefined}
                style={{
                  width: 32, height: 32, borderRadius: "50%",
                  background: warnung ? `${T.amber}18` : erledigt ? T.navy : aktiv ? T.accent : T.surface,
                  border: `2px solid ${warnung ? T.amber : erledigt ? T.navy : aktiv ? T.accent : T.border}`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontFamily: MONO, fontSize: "0.8rem", fontWeight: 700,
                  color: warnung ? T.amberText : (erledigt || aktiv) ? "#fff" : T.textMuted,
                  transition: "all 0.25s",
                  boxShadow: aktiv ? `0 0 0 4px ${T.accent}28` : "none",
                  flexShrink: 0,
                  cursor: klickbar ? "pointer" : "default",
                }}>
                {warnung ? "⚠" : erledigt ? "✓" : s.nr}
              </div>
              <div style={{
                fontFamily: PLEX, fontSize: "0.72rem", fontWeight: aktiv ? 700 : 400,
                color: aktiv ? T.accent : warnung ? T.amberText : erledigt ? T.navy : T.textMuted,
                marginTop: 5, textAlign: "center", whiteSpace: "nowrap",
                overflow: "hidden", width: "100%",
                transition: "color 0.25s",
              }}>
                {s.label}
              </div>
            </div>
            {i < STEPS.length - 1 && (
              <div style={{
                height: 2, flex: 1, marginBottom: 16,
                background: (erledigt || warnung) ? T.navy : T.borderSoft,
                transition: "background 0.25s",
              }} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}
```

Hauptkomponente: Import `import { schrittStatus } from "./wizardFuehrungLogik.js";` ergänzen; nach `antraegeVeraltet` (Z. 2623):

```js
  const hatPlatzhalter = komponiereAntraege(wizardAntraegeText, wizardGebuehrenText)
    .includes(ANTRAEGE_PLACEHOLDER);
  const statusCtx = { step, maxStep: wizardMaxStep, gerichtBestaetigt, positionen,
    beklagte, antraegeVeraltet, hatPlatzhalter };
```

Aufruf ergänzen: `<Fortschrittsbalken … statusFuer={(nr) => schrittStatus(nr, statusCtx)} />`.

- [ ] **Step 4: Tests laufen lassen**

Run: `npx vitest run src/sections/KlageWizard.fortschritt.test.jsx src/sections/KlageWizard.springen.test.jsx`
Expected: PASS — neuer Test grün, Alt-Test (ohne `statusFuer`) unverändert grün.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/sections/KlageWizard.jsx frontend/src/sections/KlageWizard.fortschritt.test.jsx
git commit -m "feat(klage): Status-Symbole (Haken/Warnung/aktiv) mit Tooltip im Fortschrittsbalken"
```

---

### Task 7: `DiffAnsicht` + `EditorMitDiff` + Badge-Verlinkung

**Files:**
- Modify: `frontend/src/sections/KlageWizard.jsx` (neue Komponenten + `TextVeraltetBadge`-Erweiterung)
- Test: `frontend/src/sections/KlageWizard.diff.test.jsx` (neu)

**Interfaces:**
- Consumes: `wortDiff` (Task 1), `DokumentCard`.
- Produces:
  - `export function DiffAnsicht({ autoText, aktuellerText })` — read-only-Karte im DokumentCard-Papier-Stil; grüne Segmente = Ergänzungen der manuellen Fassung, rote durchgestrichene = entfallene Wörter des Automatik-Texts; `data-testid="diff-ansicht"`; Legende „grün = Ihre Fassung ergänzt · rot durchgestrichen = im Automatik-Text, bei Ihnen entfallen".
  - `export function EditorMitDiff({ autoText, text, onText, warnung })` — Umschalter „⇄ Änderungen anzeigen"/„✎ Bearbeiten" über der Karte, nur sichtbar wenn `text !== autoText`; im Diff-Modus `DiffAnsicht`, sonst `DokumentCard` (editierbar, `warnung`-Prop durchgereicht).
  - `TextVeraltetBadge({ sichtbar, onNeuGenerieren, onBehalten, autoText, aktuellerText })` — sind die zwei neuen Props gesetzt, erscheint zusätzlich Button „⇄ Änderungen anzeigen", der eine `DiffAnsicht` direkt unter der Badge ein-/ausblendet. Ohne die Props verhält sich die Badge exakt wie bisher.

- [ ] **Step 1: Failing Tests schreiben**

```jsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DiffAnsicht, EditorMitDiff, TextVeraltetBadge } from "./KlageWizard.jsx";

describe("DiffAnsicht", () => {
  it("markiert Ergaenzungen gruen und Streichungen durchgestrichen", () => {
    render(<DiffAnsicht autoText="Der Beklagte zahlt" aktuellerText="Die Beklagte zahlt sofort" />);
    const box = screen.getByTestId("diff-ansicht");
    const spans = [...box.querySelectorAll("span[data-difftyp]")];
    const typen = spans.map(s => s.dataset.difftyp);
    expect(typen).toEqual(["weg", "neu", "gleich", "neu"]);
    expect(spans[0].style.textDecoration).toContain("line-through");
  });
});

describe("EditorMitDiff", () => {
  it("ohne Abweichung: kein Umschalter, Textarea editierbar", () => {
    render(<EditorMitDiff autoText="Gleich" text="Gleich" onText={() => {}} />);
    expect(screen.queryByText(/Änderungen anzeigen/)).toBeNull();
    expect(screen.getByDisplayValue("Gleich")).toBeTruthy();
  });

  it("mit Abweichung: Umschalter wechselt zwischen Editor und Diff", () => {
    render(<EditorMitDiff autoText="Alt" text="Neu" onText={() => {}} />);
    fireEvent.click(screen.getByText(/Änderungen anzeigen/));
    expect(screen.getByTestId("diff-ansicht")).toBeTruthy();
    fireEvent.click(screen.getByText(/Bearbeiten/));
    expect(screen.getByDisplayValue("Neu")).toBeTruthy();
  });

  it("Tippen im Editor ruft onText", () => {
    const onText = vi.fn();
    render(<EditorMitDiff autoText="Alt" text="Neu" onText={onText} />);
    fireEvent.change(screen.getByDisplayValue("Neu"), { target: { value: "Neuer" } });
    expect(onText).toHaveBeenCalledWith("Neuer");
  });
});

describe("TextVeraltetBadge mit Diff-Link", () => {
  it("zeigt Aenderungen-Button nur mit autoText/aktuellerText und klappt Diff auf", () => {
    const { rerender } = render(
      <TextVeraltetBadge sichtbar onNeuGenerieren={() => {}} onBehalten={() => {}} />
    );
    expect(screen.queryByText(/Änderungen anzeigen/)).toBeNull();
    rerender(<TextVeraltetBadge sichtbar onNeuGenerieren={() => {}} onBehalten={() => {}}
      autoText="Alt" aktuellerText="Neu" />);
    fireEvent.click(screen.getByText(/Änderungen anzeigen/));
    expect(screen.getByTestId("diff-ansicht")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `npx vitest run src/sections/KlageWizard.diff.test.jsx`
Expected: FAIL — Komponenten existieren nicht.

- [ ] **Step 3: Implementieren** (in `KlageWizard.jsx`, nahe `DokumentCard`)

```jsx
export function DiffAnsicht({ autoText, aktuellerText }) {
  const segmente = wortDiff(autoText, aktuellerText);
  const stil = {
    neu:    { background: "#e2f3e2", color: "#1e6b1e", borderRadius: 3, padding: "0 2px" },
    weg:    { background: "#fbe3e3", color: "#a03030", textDecoration: "line-through", borderRadius: 3, padding: "0 2px" },
    gleich: {},
  };
  return (
    <div style={{
      flex: 1, background: "#fdfcf7", border: "1px solid #e8e4d4", borderRadius: 10,
      padding: "1.25rem", minHeight: 200, overflowY: "auto",
      fontFamily: MONO, fontSize: "0.825rem", color: "#2d2a1e", lineHeight: 1.7,
    }} data-testid="diff-ansicht">
      <div style={{ fontFamily: PLEX, fontSize: "0.68rem", color: T.textMuted, marginBottom: "0.75rem" }}>
        grün = Ihre Fassung ergänzt · rot durchgestrichen = im Automatik-Text, bei Ihnen entfallen
      </div>
      <div style={{ whiteSpace: "pre-wrap" }}>
        {segmente.map((s, i) => (
          <React.Fragment key={i}>
            {i > 0 && !s.text.startsWith("\n") && " "}
            <span data-difftyp={s.typ} style={stil[s.typ]}>{s.text}</span>
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}

export function EditorMitDiff({ autoText, text, onText, warnung }) {
  const [zeigeDiff, setZeigeDiff] = useState(false);
  const geaendert = (text ?? "") !== (autoText ?? "");
  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
      {geaendert && (
        <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 6 }}>
          <button onClick={() => setZeigeDiff(v => !v)}
            style={{ padding: "4px 10px", borderRadius: 6, cursor: "pointer",
              border: `1.5px solid ${T.border}`, background: "#fff",
              fontFamily: PLEX, fontSize: "0.76rem", fontWeight: 600, color: T.navy }}>
            {zeigeDiff ? "✎ Bearbeiten" : "⇄ Änderungen anzeigen"}
          </button>
        </div>
      )}
      {zeigeDiff && geaendert
        ? <DiffAnsicht autoText={autoText} aktuellerText={text} />
        : <DokumentCard warnung={warnung} editText={text} onEditText={onText} />}
    </div>
  );
}
```

`TextVeraltetBadge` erweitern:

```jsx
export function TextVeraltetBadge({ sichtbar, onNeuGenerieren, onBehalten, autoText, aktuellerText }) {
  const [zeigeDiff, setZeigeDiff] = useState(false);
  if (!sichtbar) return null;
  const mitDiff = autoText !== undefined && aktuellerText !== undefined;
  return (
    <div style={{ marginBottom: "0.75rem" }}>
      <div style={{ background: `${T.amber}12`, border: `1px solid ${T.amber}50`,
        borderRadius: 7, padding: "0.5rem 0.75rem",
        display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <span style={{ fontFamily: PLEX, fontSize: "0.8rem", color: T.amberText, flex: 1 }}>
          ⚠ Text veraltet – Eingaben haben sich geändert.
        </span>
        {mitDiff && (
          <button onClick={() => setZeigeDiff(v => !v)}
            style={{ padding: "5px 10px", borderRadius: 6, cursor: "pointer",
              border: `1.5px solid ${T.border}`, background: "#fff",
              fontFamily: PLEX, fontSize: "0.78rem", fontWeight: 600, color: T.navy }}>
            {zeigeDiff ? "✎ Ausblenden" : "⇄ Änderungen anzeigen"}
          </button>
        )}
        <button onClick={onNeuGenerieren}
          style={{ padding: "5px 10px", borderRadius: 6, cursor: "pointer",
            border: `1.5px solid ${T.navy}`, background: "#fff",
            fontFamily: PLEX, fontSize: "0.78rem", fontWeight: 600, color: T.navy }}>
          ↻ Neu generieren
        </button>
        <button onClick={onBehalten}
          style={{ padding: "5px 10px", borderRadius: 6, cursor: "pointer",
            border: `1.5px solid ${T.border}`, background: "#fff",
            fontFamily: PLEX, fontSize: "0.78rem", fontWeight: 600, color: T.textMuted }}>
          Behalten
        </button>
      </div>
      {mitDiff && zeigeDiff && (
        <div style={{ marginTop: 6, display: "flex" }}>
          <DiffAnsicht autoText={autoText} aktuellerText={aktuellerText} />
        </div>
      )}
    </div>
  );
}
```

Import oben ergänzen: `import { wortDiff, schrittStatus } from "./wizardFuehrungLogik.js";` (schrittStatus ggf. schon aus Task 6 vorhanden — dann nur `wortDiff` ergänzen).

- [ ] **Step 4: Tests laufen lassen**

Run: `npx vitest run src/sections/KlageWizard.diff.test.jsx src/sections/KlageWizard.antraege-dirty.test.jsx`
Expected: PASS — Badge-Alttests grün (neue Props optional; Wrapper-`<div>` um die Badge darf bestehende DOM-Assertions nicht brechen — falls doch, Assertions auf Textinhalte umstellen, nicht Verhalten ändern).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/sections/KlageWizard.jsx frontend/src/sections/KlageWizard.diff.test.jsx
git commit -m "feat(klage): DiffAnsicht + EditorMitDiff, TextVeraltetBadge verlinkt die Aenderungs-Ansicht"
```

---

### Task 8: Diff-Integration an allen sechs Textstellen

**Files:**
- Modify: `frontend/src/sections/KlageWizard.jsx` (StepAktLeg Z. 725, StepUnfall Z. 822, StepAntraege Z. 2205–2207, StepEinwaende, StepVerzug Z. 1680, StepGebuehren Z. 2506, StepZusammenfassung Z. 1733)
- Test: `frontend/src/sections/KlageWizard.diff.test.jsx` (erweitern)

**Interfaces:**
- Consumes: `EditorMitDiff`, `DiffAnsicht`, `TextVeraltetBadge` (Task 7); Auto-Text-Quellen: `buildAuto()` (StepAktLeg-intern), `ersetzeMandantDurchKlaeger(schilderungOriginal, weiblich)` (StepUnfall), `baueAntraegeText(antraegeOpts)` (Hauptkomponente), `grundhaftungsText`+`einwaendeBlock` (StepEinwaende), `buildVerzugAutoText(wizardVerzugDokDatum, wizardVerzugDatum)` (StepVerzug-intern), `baueGebuehrenAntrag()` (StepGebuehren-intern).
- Produces: neue Props `antraegeAuto` an `StepAntraege` und `StepZusammenfassung` (String, von der Hauptkomponente als `baueAntraegeText(antraegeOpts)` berechnet).

- [ ] **Step 1: Failing Test schreiben** (Beispiel StepVerzug + StepAntraege; in `KlageWizard.diff.test.jsx` anhängen)

```jsx
import { StepVerzug, StepAntraege, buildVerzugAutoText } from "./KlageWizard.jsx";

describe("Diff-Integration", () => {
  it("StepVerzug zeigt Umschalter bei manuell geaendertem Text", () => {
    const auto = buildVerzugAutoText("2026-05-01", "2026-05-15");
    render(<StepVerzug zinsenAb="verzug" weiblich={false}
      wizardVerzugDatum="2026-05-15" onWizardVerzugDatum={() => {}}
      wizardVerzugDokDatum="2026-05-01" onWizardVerzugDokDatum={() => {}}
      wizardVerzugText={auto + " Zusatz."} onWizardVerzugText={() => {}}
      manuelleBearbeitung onManuelleBearbeitung={() => {}}
      verzugDokListe={[]} verzugDokId={null} onVerzugDokId={() => {}} />);
    fireEvent.click(screen.getByText(/Änderungen anzeigen/));
    expect(screen.getByTestId("diff-ansicht").textContent).toContain("Zusatz.");
  });

  it("StepAntraege reicht antraegeAuto an Badge und Editor durch", () => {
    render(<StepAntraege positionen={[]} mitSG={false} sgMind={0} beklagte={[]} weiblich={false}
      zinsenAb="rechtshaengigkeit" verzug="" unfalldatum=""
      mitFestSg={false} onMitFestSg={() => {}} mitFestSach={false} onMitFestSach={() => {}}
      antraegeText="Manuell geaendert" onAntraegeText={() => {}} onAntraegeManuell={() => {}}
      gebuehrenText="" antraegeVeraltet antraegeAuto="Automatik Fassung"
      onNeuGenerieren={() => {}} onBehalten={() => {}} />);
    const buttons = screen.getAllByText(/Änderungen anzeigen/);
    expect(buttons.length).toBeGreaterThanOrEqual(1);
    fireEvent.click(buttons[0]);
    expect(screen.getAllByTestId("diff-ansicht")[0].textContent).toContain("Automatik Fassung");
  });
});
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `npx vitest run src/sections/KlageWizard.diff.test.jsx`
Expected: FAIL — kein Umschalter in StepVerzug/StepAntraege.

- [ ] **Step 3: Integration umsetzen** — je Stelle die rechte `DokumentCard` durch `EditorMitDiff` ersetzen:

  - **StepAktLeg** (Z. 725–729): `<EditorMitDiff autoText={buildAuto()} warnung={brauchtFreigabe && aktLegFreigabe === "ungeklaert"} text={sachverhaltText} onText={val => { onSachverhaltManuell(true); onSachverhaltText(val); }} />`
  - **StepUnfall** (Z. 822): davor `const autoText = ersetzeMandantDurchKlaeger(schilderungOriginal || "", weiblich);` — dann `<EditorMitDiff autoText={autoText} text={unfalltextEdit} onText={onUnfalltextEdit} />`
  - **StepAntraege**: Signatur um `antraegeAuto` erweitern; Badge: `<TextVeraltetBadge sichtbar={antraegeVeraltet} onNeuGenerieren={onNeuGenerieren} onBehalten={onBehalten} autoText={antraegeAuto} aktuellerText={antraegeText} />`; Karte: `<EditorMitDiff autoText={antraegeAuto} text={antraegeText} onText={val => { onAntraegeManuell(true); onAntraegeText(val); }} />`
  - **StepEinwaende**: `const autoText = einwaendeBlock ? `${grundhaftungsText}\n\n${einwaendeBlock}` : grundhaftungsText;` — Karte: `<EditorMitDiff autoText={autoText} text={rwText} onText={onRwText} />`
  - **StepVerzug** (Z. 1680): `<EditorMitDiff autoText={buildVerzugAutoText(wizardVerzugDokDatum, wizardVerzugDatum)} text={wizardVerzugText} onText={val => { onManuelleBearbeitung(true); onWizardVerzugText(val); }} />`
  - **StepGebuehren** (Z. 2506): `<EditorMitDiff autoText={rvgGesamt > 0 ? baueGebuehrenAntrag() : gebuehrenText} text={gebuehrenText} onText={val => { onGebuehrenManuell(true); onGebuehrenText(val); }} />` (bei `rvgGesamt === 0` gibt es keinen sinnvollen Automatik-Text → Umschalter bleibt aus)
  - **StepZusammenfassung** (Z. 1733): Signatur um `antraegeAuto` erweitern; `<TextVeraltetBadge sichtbar={antraegeVeraltet} onNeuGenerieren={onAntraegeNeuGenerieren} onBehalten={onAntraegeBehalten} autoText={antraegeAuto} aktuellerText={antraegeText} />`
  - **Hauptkomponente**: `const antraegeAuto = baueAntraegeText(antraegeOpts);` (neben `antraegeVeraltet`, Z. 2623) und als Prop an `StepAntraege` (`step === 6`) und `StepZusammenfassung` (`step === 11`) durchreichen.

- [ ] **Step 4: Volle Sektion + Build**

Run: `npx vitest run src/sections/`
Expected: PASS — insbesondere `KlageWizard.verzug.test.jsx`, `KlageWizard.aktleg.test.jsx`, `KlageWizard.gebuehren.test.jsx` bleiben grün (Textareas bleiben im Standardmodus unverändert erreichbar; falls ein Alt-Test an der DOM-Struktur um die Karte hängt, Assertion auf Textinhalt umstellen).

Run: `npm run build`
Expected: Build grün.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/sections/KlageWizard.jsx frontend/src/sections/KlageWizard.diff.test.jsx
git commit -m "feat(klage): Aenderungen-anzeigen-Umschalter an allen sechs editierbaren Text-Vorschauen"
```

---

### Task 9: Endabnahme — volle Suite, Build, Spec-Gegenprobe

**Files:**
- Keine neuen; nur Fixes, falls die volle Suite Bruchstellen zeigt.

- [ ] **Step 1: Volle Frontend-Suite**

Run: `npx vitest run`
Expected: alle Tests grün (Baseline vor Paket 2: 267 + neue aus Tasks 1–8). Jeden Fehlschlag einzeln fixen (nur Nummern-/Struktur-Anpassungen; Verhaltens-Assertions nicht abschwächen).

- [ ] **Step 2: Build**

Run: `npm run build`
Expected: grün, keine neuen Warnungen zu ungenutzten Exporten.

- [ ] **Step 3: Spec-Gegenprobe (manuell, Checkliste)**

- 11 Schritte in exakt der Spec-Reihenfolge; Header zeigt „Schritt N von 11".
- Schritt 8 ohne erfasste Kürzungen: Hinweis + Weiter, Schritt wird nie übersprungen, Nummerierung stabil.
- Symbole: ✓/⚠/●/ausgegraut; Tooltip-Texte; Klickverhalten unverändert (`kannSpringen` kumulativ).
- Diff an 6 Stellen + Badge-Verlinkung (Schritt 6 und Schritt 11); kein Nebeneinander-Diff, read-only.
- `ENTWURF_FORMAT_VERSION === 2`; Alt-Entwurf (v1) → „Neu beginnen"-Dialog.
- Platzhalter-Wortlaut „Schritt 10"; `komponiereAntraege`-Vertrag unangetastet.

- [ ] **Step 4: Commit (falls Fixes anfielen)**

```bash
git add -u ./frontend
git commit -m "test(klage): Suite-Anpassungen nach Schrittumbau Paket 2"
```

Danach: superpowers:requesting-code-review (Whole-Branch), DEV-Smoke im Browser durch RA Schatz, FF-Merge nach Freigabe (superpowers:finishing-a-development-branch).

---

## Self-Review (durchgeführt beim Planen)

- **Spec-Abdeckung:** Baustein 1 → Tasks 2+6; Baustein 2 → Tasks 3+4 (+5 für format_version-Kopplung); Baustein 3 → Tasks 1+7+8; Spec-Testliste → Tasks 1 (Diff-Fälle), 2 (`schrittStatus` je Warnquelle), 4 (Schrittfolge/Schnell-Durchlauf; `kannSpringen`-Indizes 1 und 5 liegen vor dem Einschub und bleiben unverändert — per Springen-Suite abgedeckt), 6–8 (Tooltips, Umschalter, Badge-Diff). ✓
- **Bewusste Design-Entscheidungen über die Spec hinaus** (dem Reviewer melden): (a) `einwaendeEingefuegtRef` → gelifteter State `wizardEinwaendeBlock` (nötig, weil Panel und Würdigungstext jetzt auf getrennten Schritten liegen; heilt nebenbei den Ref-Verlust bei Schrittwechsel), wird in Entwurf v2 mitgespeichert; (b) Ohne erfasste Kürzungen wird die Auswahlliste ausgeblendet (Spec-Wortlaut „Hinweis + Weiter-Knopf"), die Würdigungs-Textkarte bleibt; (c) Diff-Basis Würdigung = Grundhaftungstext + zuletzt übernommener Einwände-Block.
- **Typ-/Namenskonsistenz:** `wortDiff`-Segmentform `{typ, text}` einheitlich in Task 1/7; `schrittStatus`-ctx-Felder identisch in Task 2 (Definition) und Task 6 (`statusCtx`); `wizardEinwaendeBlock`-Name identisch in Tasks 4/5; `antraegeAuto` in Task 8 an beiden Stellen. ✓
- **Zeilennummern** stammen vom Stand `main` = `f710886b` und sind Orientierung; nach Task 3/4 verschieben sie sich — Implementierer suchen über die genannten Symbolnamen.
