# Übersicht-Redesign A+B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Übersicht-Tab der AkteDetailView aufräumen (Mockup A: eine Wahrheit pro Information) und den OnboardingHub-Banner durch einen Fächer im PhasenStrip ersetzen (Mockup B).

**Architecture:** `AkteDetailView` lädt `/akten/<az>/positionen/status` genau einmal und wird damit zur einzigen Summen-Quelle (Header-KPI und PositionsDashboard zeigen dieselben Zahlen). `UebersichtSection` verliert FinanzBand, RegulierungsTabelle-Karte, Forderungshistorie und die doppelte posMap-Aggregation; die Forderungshistorie wandert in den Regulierung-Tab. Der OnboardingHub wird zu einer puren Check-Funktion + Fächer-Popover am PhasenStrip.

**Tech Stack:** React 18, Vite, Vitest + Testing Library (jsdom). Kein Backend-Change (Endpoint `/positionen/status` existiert, `backend/routers/positionen_routes.py:46`).

**Mockup-Referenz:** `handover/2026-08-10-uebersicht-redesign-mockups.md` (Mockup A + B, von RA Schatz freigegeben 2026-08-10). Befund-Katalog: `handover/2026-08-10-uebersicht-review-befunde.md` (offen: B3, Abschnitt B, Abschnitt C).

## Global Constraints

- Branch: **`abschlussbericht`** (Weiterarbeit, kein neuer Branch — Redesign baut auf Review-Fixes `f6fd2f3d` auf).
- Git-Wurzel ist `C:\Users\HAL9000` (Home!) — **NIE `git add -A`**, immer explizite Pfade relativ zum Projektordner.
- UI-Sprache Deutsch; keine Code-Kommentare außer bei nicht-offensichtlichem Verhalten.
- RA-MICRO bleibt read-only (hier ohnehin nur Frontend).
- Tests laufen mit `cd frontend` + `npm test` (PowerShell: kein `&&`, Befehle mit `;` oder einzeln). Einzeldatei: `npm test -- src/pfad/datei.test.jsx`.
- Vor diesem Plan grün: 476/476 Tests (Frontend 446 + Backend 43 laufen getrennt; hier ist nur das Frontend betroffen: `npm test` in `frontend/`).
- `RegulierungsTabelle` wird weiter von `KlageSection.jsx:3` importiert — Komponente und Export **bleiben**, nur die Verwendung in der Übersicht fällt weg.

---

### Task 1: Summen-Helfer + PositionsDashboard nimmt Daten als Prop

**Files:**
- Modify: `frontend/src/config/utils.js` (Export ergänzen)
- Modify: `frontend/src/components/PositionsDashboard.jsx:192-208`
- Test: `frontend/src/config/summenAusPositionsstatus.test.js` (neu)
- Test: `frontend/src/components/PositionsDashboard.daten.test.jsx` (neu)

**Interfaces:**
- Produces: `summenAusPositionsstatus(positionen) -> { gefordert, reguliert, offen } | null` (null wenn keine Positionen) aus `config/utils.js`.
- Produces: `<PositionsDashboard az daten onOeffneEreignisse />` — wenn `daten` (Response von `/positionen/status`) gesetzt ist, kein eigener Fetch.

- [ ] **Step 1: Failing Tests schreiben**

`frontend/src/config/summenAusPositionsstatus.test.js`:

```js
import { describe, it, expect } from "vitest";
import { summenAusPositionsstatus } from "./utils.js";

describe("summenAusPositionsstatus", () => {
  it("summiert gefordert/anerkannt/offen über alle Positionen", () => {
    const s = summenAusPositionsstatus({
      rep:  { gefordert: 8200, anerkannt: 6900, offen: 1300 },
      nutz: { gefordert: 1400, anerkannt: 1400, offen: 0 },
    });
    expect(s).toEqual({ gefordert: 9600, reguliert: 8300, offen: 1300 });
  });

  it("liefert null ohne Positionen", () => {
    expect(summenAusPositionsstatus({})).toBeNull();
    expect(summenAusPositionsstatus(null)).toBeNull();
  });
});
```

`frontend/src/components/PositionsDashboard.daten.test.jsx`:

```jsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("../api.js", () => ({
  API_BASE: "",
  tokenStore: { getAccess: () => "" },
}));

import PositionsDashboard from "./PositionsDashboard.jsx";

const DATEN = {
  positionen: {
    reparatur: { label: "Reparatur", gefordert: 8200, anerkannt: 6900, offen: 1300,
      zustand: "teilanerkannt", kategorie: "fahrzeugschaden", eskalationsstufe: 1,
      checkliste: { erledigt: [], offen: [] } },
  },
  registry_version: "abc12345",
};

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({}) })));
});

describe("PositionsDashboard mit daten-Prop", () => {
  it("rendert aus der Prop ohne eigenen Fetch", () => {
    render(<PositionsDashboard az="123/26" daten={DATEN} />);
    expect(screen.getByText("Reparatur")).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `cd frontend; npm test -- src/config/summenAusPositionsstatus.test.js src/components/PositionsDashboard.daten.test.jsx`
Expected: FAIL (`summenAusPositionsstatus is not a function` bzw. `fetch` wurde gerufen).

- [ ] **Step 3: Implementierung**

In `frontend/src/config/utils.js` ergänzen (ans Dateiende):

```js
export function summenAusPositionsstatus(positionen) {
  const eintraege = Object.values(positionen || {});
  if (!eintraege.length) return null;
  return eintraege.reduce((acc, p) => ({
    gefordert: acc.gefordert + Number(p.gefordert || 0),
    reguliert: acc.reguliert + Number(p.anerkannt || 0),
    offen:     acc.offen     + Number(p.offen     || 0),
  }), { gefordert: 0, reguliert: 0, offen: 0 });
}
```

In `frontend/src/components/PositionsDashboard.jsx` die Signatur + Fetch-Effekt ändern. Alt (Zeile 192-208):

```jsx
export default function PositionsDashboard({ az, onOeffneEreignisse = () => {} }) {
  const [daten, setDaten] = useState(null);
  const [fehler, setFehler] = useState(null);
  const [view, setView] = useState('getrennt');

  useEffect(() => {
    if (!az) return;
```

Neu:

```jsx
export default function PositionsDashboard({ az, daten: datenProp = null, onOeffneEreignisse = () => {} }) {
  const [geladen, setGeladen] = useState(null);
  const [fehler, setFehler] = useState(null);
  const [view, setView] = useState('getrennt');
  const daten = datenProp ?? geladen;

  useEffect(() => {
    if (!az || datenProp) return;
```

Im selben Effekt `setDaten(d)` → `setGeladen(d)` und Dependency-Array `[az]` → `[az, datenProp]`. Sonst nichts ändern (alle Lesezugriffe nutzen weiter `daten`).

- [ ] **Step 4: Tests grün**

Run: `cd frontend; npm test -- src/config/summenAusPositionsstatus.test.js src/components/PositionsDashboard.daten.test.jsx`
Expected: PASS (3 Tests).

- [ ] **Step 5: Commit**

```powershell
git add "frontend/src/config/utils.js" "frontend/src/config/summenAusPositionsstatus.test.js" "frontend/src/components/PositionsDashboard.jsx" "frontend/src/components/PositionsDashboard.daten.test.jsx"
git commit -m @'
feat(uebersicht): Summen-Helfer + PositionsDashboard mit daten-Prop (Redesign A, SSOT-Vorbereitung)
'@
```

---

### Task 2: AkteDetailView — Header-KPI aus dem Ereignismodell (B3-Fix)

**Files:**
- Modify: `frontend/src/components/AkteDetailView.jsx` (KPI-Block Z. 296-322, neuer Fetch, Props an UebersichtSection Z. 409, `akte.hq || 100` Z. 301)

**Interfaces:**
- Consumes: `summenAusPositionsstatus` aus Task 1; `request` aus `../api.js`.
- Produces: `UebersichtSection` erhält drei neue Props: `posDaten` (Response von `/positionen/status` oder null), `kpiSummen` (`{ gefordert, reguliert, offen, quelle: "ereignismodell"|"alt" }`), `mandantChecks` (das bereits geladene `raInfo`).

**Entscheidung (B3, für DECISIONS.md in Task 9):** Einzige Summen-Quelle ist das Ereignismodell. Nur wenn eine Akte dort noch **keine** Positionen hat (Bestandsakte), fällt der Header auf die Alt-Berechnung (`liveBrutto × HQ` / `Σ ab.gesamt_reguliert`) zurück — sonst zeigte er bei Bestandsakten 0 €.

- [ ] **Step 1: Implementierung (kein eigener Komponententest — AkteDetailView braucht zu viele Mocks; die Logik steckt im getesteten Helfer aus Task 1, Absicherung über Vollsuite + Browser-Abnahme)**

Import ergänzen (Zeile 4):

```jsx
import { fmtEuro, summenAusPositionsstatus } from "../config/utils.js";
```

Nach dem `raInfo`-Effekt (nach Zeile 80) neuen State + Fetch einfügen:

```jsx
  const [posDaten, setPosDaten] = useState(null);
  React.useEffect(() => {
    if (!akte.az) return;
    setPosDaten(null);
    request(`/akten/${encodeURIComponent(akte.az)}/positionen/status`)
      .then(d => setPosDaten(d))
      .catch(() => {});
  }, [akte.az]);
```

Nach dem `liveBrutto`-useMemo (nach Zeile 183) einfügen:

```jsx
  const kpiSummen = useMemo(() => {
    const s = summenAusPositionsstatus(posDaten?.positionen);
    if (s) return { ...s, quelle: "ereignismodell" };
    const gefordert = liveBrutto * ((akte.hq ?? 100) / 100);
    const reguliert = (st.abrechnungen || []).reduce((sum, ab) => sum + (parseFloat(ab.gesamt_reguliert) || 0), 0);
    return { gefordert, reguliert, offen: Math.max(0, gefordert - reguliert), quelle: "alt" };
  }, [posDaten, liveBrutto, akte.hq, st.abrechnungen]);
```

Den KPI-Block (Zeile 300-303) ersetzen. Alt:

```jsx
            {(() => {
              const gefordert = liveBrutto * ((akte.hq || 100) / 100);
              const reguliert = (st.abrechnungen||[]).reduce((s,ab) => s + (parseFloat(ab.gesamt_reguliert)||0), 0);
              const offen     = Math.max(0, gefordert - reguliert);
```

Neu:

```jsx
            {(() => {
              const { gefordert, reguliert, offen } = kpiSummen;
```

Aufruf der UebersichtSection (Zeile 409) erweitern:

```jsx
          {sec==="uebersicht" && <UebersichtSection akte={akte} st={st} dispatch={dispatch} onNavigate={setSec}
            posDaten={posDaten} kpiSummen={kpiSummen} mandantChecks={raInfo} />}
```

- [ ] **Step 2: Vollsuite grün**

Run: `cd frontend; npm test`
Expected: PASS, gleiche Testanzahl wie vorher (UebersichtSection ignoriert unbekannte Props noch).

- [ ] **Step 3: Commit**

```powershell
git add "frontend/src/components/AkteDetailView.jsx"
git commit -m @'
fix(uebersicht): Header-KPI aus Ereignismodell-Summen, Alt-Berechnung nur als Bestandsakten-Fallback (Befund B3)
'@
```

---

### Task 3: UebersichtSection aufräumen — FinanzBand, RegulierungsTabelle-Karte, Forderungshistorie und Alt-Aggregation raus

**Files:**
- Modify: `frontend/src/sections/UebersichtSection.jsx`
- Test: `frontend/src/sections/UebersichtSection.redesign.test.jsx` (neu)

**Interfaces:**
- Consumes: Props `posDaten`, `kpiSummen`, `mandantChecks` aus Task 2.
- Produces: `berechnePhase({ akte, ibanCheck, schaden, abrechnungen, summen })` (neue Signatur, `summen` = `kpiSummen`). Render-Reihenfolge neu: Leisten-Box (PhasenStrip + StatusBand) → PositionsDashboard → To-do/WV-Box → AkkordeonStrip (3 Tabs: `ramicro`, `chronik`, `notizen`) → Akkordeon-Inhalte. `ForderungshistorieKarte` bleibt in diesem Task noch definiert (Umzug in Task 4), wird aber nicht mehr gerendert.

- [ ] **Step 1: Failing Test schreiben**

`frontend/src/sections/UebersichtSection.redesign.test.jsx`:

```jsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("../api.js", () => ({
  API_BASE: "",
  ping: vi.fn(),
  ApiError: class ApiError extends Error {},
  tokenStore: { getAccess: () => "" },
  request: vi.fn(() => Promise.resolve({})),
  akten: { aktivitaeten: vi.fn(() => Promise.resolve({})), aktivitaetLoeschen: vi.fn(), aktualisieren: vi.fn(), pwaMessage: vi.fn() },
  forderungen: { nachSchreiben: vi.fn(() => Promise.resolve({ schreiben: [] })), klageFlagSetzen: vi.fn(), aktualisieren: vi.fn() },
  ramicroAkte: { laden: vi.fn(() => Promise.resolve(null)) },
  apiTodos: { liste: vi.fn(() => Promise.resolve({ todos: [] })), erstelle: vi.fn(), update: vi.fn(), loesche: vi.fn() },
  apiSta: { kontext: vi.fn(), generieren: vi.fn() },
}));

import UebersichtSection from "./UebersichtSection.jsx";

const PROPS = {
  akte: { id: "123/26", az: "123/26", az_roh: "123/26", hq: 100, status: "offen" },
  st: { schaden: { gesamt_brutto: 9600 }, abrechnungen: [], beteiligte: [], dokumente: [], aktivitaeten: [] },
  dispatch: () => {},
  onNavigate: () => {},
  posDaten: { positionen: { reparatur: { label: "Reparatur", gefordert: 8200, anerkannt: 6900, offen: 1300,
    zustand: "teilanerkannt", kategorie: "fahrzeugschaden", eskalationsstufe: 1,
    checkliste: { erledigt: [], offen: [] } } } },
  kpiSummen: { gefordert: 8200, reguliert: 6900, offen: 1300, quelle: "ereignismodell" },
  mandantChecks: { iban_vorhanden: true, vollmacht_vorhanden: true },
};

beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: false, json: () => Promise.resolve({}) })));
});

describe("Übersicht-Redesign A — eine Wahrheit pro Information", () => {
  it("zeigt weder FinanzBand noch RegulierungsTabelle noch Forderungshistorie", () => {
    render(<UebersichtSection {...PROPS} />);
    expect(screen.queryByText(/Regulierungsfortschritt/)).toBeNull();
    expect(screen.queryByText(/Forderung vs\. Regulierung/)).toBeNull();
    expect(screen.queryByText(/Forderungshistorie/)).toBeNull();
    expect(screen.getByText("Reparatur")).toBeInTheDocument();
  });

  it("bietet nur noch drei Akkordeons an", () => {
    render(<UebersichtSection {...PROPS} />);
    expect(screen.getByText(/RA-Micro Beteiligte/)).toBeInTheDocument();
    expect(screen.getByText(/Chronik/)).toBeInTheDocument();
    expect(screen.getByText(/Notizen/)).toBeInTheDocument();
    expect(screen.queryByText(/Regulierungsdetails/)).toBeNull();
  });
});
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `cd frontend; npm test -- src/sections/UebersichtSection.redesign.test.jsx`
Expected: FAIL (FinanzBand/RegulierungsTabelle/5 Akkordeons noch da).

- [ ] **Step 3: UebersichtSection umbauen**

3a — `berechnePhase` (Zeile 1635-1654) auf Summen-Objekt umstellen:

```jsx
function berechnePhase({ akte, ibanCheck, schaden, abrechnungen, summen }) {
  const hatIban       = !!ibanCheck?.iban_vorhanden;
  const hatSchaden    = parseFloat(schaden?.gesamt_brutto || 0) > 0 || summen.gefordert > 0;
  const hatAbrechnung = (abrechnungen || []).length > 0;
  const hatKuerzung   = hatAbrechnung && summen.offen > 0.005;
  const vollreguliert = summen.gefordert > 0 && summen.reguliert >= summen.gefordert * 0.99;
  const statusKlage   = akte.status === "klage";
  const istAbschluss  = vollreguliert || akte.status === "abgeschlossen" || statusKlage;

  let aktiv;
  if (istAbschluss)                      aktiv = "abschluss";
  else if (hatAbrechnung && hatKuerzung) aktiv = "stellungnahme";
  else if (hatAbrechnung)                aktiv = "regulierung";
  else if (hatIban && hatSchaden)        aktiv = "erstforderung";
  else                                   aktiv = "onboarding";

  const aktivIdx     = _PHASEN_ORDER.indexOf(aktiv);
  const phasenFertig = Object.fromEntries(_PHASEN_ORDER.map((p, i) => [p, i < aktivIdx]));
  return { aktiv, istKlage: statusKlage, phasenFertig };
}
```

3b — `STRIP_TABS` (Zeile 1477-1483) auf drei Einträge kürzen:

```jsx
const STRIP_TABS = [
  { id:"ramicro", label:"🏛 RA-Micro Beteiligte" },
  { id:"chronik", label:"🕒 Chronik" },
  { id:"notizen", label:"📝 Notizen" },
];
```

3c — Komponente `FinanzBand` (Zeile 1781-1822) komplett löschen.

3d — Hauptkomponente `UebersichtSection` (Zeile 1979 ff.):

Signatur:

```jsx
function UebersichtSection({ akte, st, dispatch, onNavigate, posDaten = null,
  kpiSummen = { gefordert: 0, reguliert: 0, offen: 0, quelle: "alt" }, mandantChecks = null }) {
```

- `ibanCheck`-State + zugehörigen `mandant-checks`-Fetch (Zeile 1983, 1990-1995) löschen; überall stattdessen `mandantChecks` verwenden (redundanter Request Nr. 2 entfällt, Review Abschnitt B).
- `stripOffene`-Default: `useState([])` statt `useState(["regulierung"])`.
- Den kompletten Aggregations-Block von `// Alle Positionen aus allen Abrechnungen aggregieren` (Zeile 2024) bis einschließlich `const gesamtKuerzung  = alleRows.reduce(...)` (Zeile 2166) löschen (posMap, SCHADEN_POS_MAP, ABZUG_FELDER, _art/_pv*/_wbw2/_rst2, _fahrzeugKeysSet, _ALLE_FAHRZEUG_KEYS, _getFahrzeugBetrag, _rawExtras, _extraCoveredKeys, _nichtFahrzeugKeys, _posMapNichtFahrzeug, alleKeys, posTableRows, extraRows, alleRows, gesamtForderung/Reguliert/Kuerzung).
- Phase neu:

```jsx
  const phase = berechnePhase({ akte, ibanCheck: mandantChecks, schaden, abrechnungen, summen: kpiSummen });
```

- Render neu (kompletter return-Block; OnboardingHub bleibt in diesem Task noch drin, fliegt in Task 7):

```jsx
  return (
    <>
      <OnboardingHub
        az={akte.az}
        akte={akte}
        beteiligte={st?.beteiligte || []}
        schaden={st?.schaden || {}}
        dokumente={st?.dokumente || []}
        onTabWechsel={onNavigate}
      />

      {toast && <Toast msg={toast} onDone={() => setToast("")} />}

      <div style={{ border:`1px solid ${T.border}`, borderRadius:10, overflow:"hidden", marginBottom:"1.25rem", boxShadow:"0 1px 4px rgba(0,0,0,.05)" }}>
        <PhasenStrip phase={phase} />
        <StatusBand ibanCheck={mandantChecks} todos={todosState} hq={akte.hq} />
      </div>

      {akte.az && (
        <PositionsDashboard
          az={akte.az}
          daten={posDaten}
          onOeffneEreignisse={(key) => setEreignislisteKey(key)}
        />
      )}
      <EreignislistePanel
        az={akte.az}
        positionKey={ereignislisteKey}
        onClose={() => setEreignislisteKey(null)}
      />

      <div style={{ border:`1px solid ${T.border}`, borderRadius:10, overflow:"hidden", marginBottom:"1.25rem", background:T.cardBg, boxShadow:"0 1px 4px rgba(0,0,0,.05)" }}>
        <TodoWvSpalten az={akte.az} azRoh={azRoh} todos={todosState} />
      </div>

      <div style={{ marginBottom:"1rem" }}>
        <AkkordeonStrip offene={stripOffene} onToggle={toggleStrip} />
      </div>

      {stripOffene.includes("ramicro") && azRoh.includes("/") && (
        <div style={{ marginBottom:"1rem" }}>
          <RaMicroAkteUebersicht azRoh={azRoh} mandantChecks={mandantChecks} />
        </div>
      )}

      {stripOffene.includes("chronik") && (
        <KlappAbschnitt titel="Akten-Chronik" lsKey={`uebersicht-chronik-${azKlappKey}`}>
          <AktenTimeline
            abrechnungen={abrechnungen}
            aktivitaeten={st.aktivitaeten || []}
            akteId={akte.id}
            onAktivitaetenChange={async () => {
              const data = await apiAkten.aktivitaeten(akte.id);
              if (data?.aktivitaeten)
                dispatch({ type:"SET_AKTIVITAETEN", akteId:akte.id, aktivitaeten:data.aktivitaeten });
            }}
          />
        </KlappAbschnitt>
      )}

      {stripOffene.includes("notizen") && (
        <Card style={{ padding:"0.6rem 1rem", display:"flex", flexDirection:"column", gap:5 }}>
          <textarea value={notizen} onChange={e => { setNotizen(e.target.value); setNC(true); }} rows={3}
            placeholder="Interne Notizen …"
            style={{ padding:"5px 8px", border:`1.5px solid ${T.border}`, borderRadius:6,
              fontSize:"0.875rem", color:T.text, background:T.surface, outline:"none", resize:"none",
              fontFamily:T.fontBody }}
            onFocus={e => e.target.style.borderColor = T.accent}
            onBlur={e => e.target.style.borderColor = T.border} />
          {nChanged && (
            <Btn variant="gold" size="sm" onClick={async () => {
              dispatch({ type:"SET_NOTIZEN", akteId:akte.id, notizen });
              setNC(false); setToast("Notizen gespeichert.");
              try { await apiAkten.aktualisieren(akte.id, { notizen }); } catch {}
            }}>{Ic.check} Speichern</Btn>
          )}
        </Card>
      )}
    </>
  );
```

(`RaMicroAkteUebersicht` bekommt die Prop `mandantChecks` schon durchgereicht — verwendet wird sie erst in Task 8; bis dahin ignoriert die Komponente sie.)

3e — Import aufräumen (Zeile 4): `positionKuerzungBetrag` aus dem `constants.js`-Import entfernen (wurde nur im gelöschten Block genutzt). `POSITION_LABELS_FE`, `HAFTUNGSART_CFG`, `TIMELINE_*` bleiben (RegulierungsTabelle/AktenTimeline).

3f — Begriffs-Vereinheitlichung (Handover Abschnitt 6): in `frontend/src/components/PositionsDashboard.jsx` den Kartentitel `Forderungen · Positions-Übersicht` ersetzen durch `Positionen` (Untertitel mit den Summen bleibt).

- [ ] **Step 4: Tests grün**

Run: `cd frontend; npm test`
Expected: PASS inkl. der 2 neuen Redesign-Tests. Die bestehenden `UebersichtSection.befunde.test.jsx` bleiben grün (sie testen nur exportierte Einzelkomponenten).

- [ ] **Step 5: Commit**

```powershell
git add "frontend/src/sections/UebersichtSection.jsx" "frontend/src/sections/UebersichtSection.redesign.test.jsx"
git commit -m @'
feat(uebersicht): Redesign A — FinanzBand/RegulierungsTabelle/Historie raus, 3 Akkordeons, Phase aus SSOT-Summen
'@
```

---

### Task 4: Forderungshistorie in den Regulierung-Tab umziehen

**Files:**
- Create: `frontend/src/components/ForderungshistorieKarte.jsx`
- Modify: `frontend/src/sections/UebersichtSection.jsx` (Funktion Z. 489-689 löschen, `apiForderungen`-Import entfernen)
- Modify: `frontend/src/sections/RegulierungSection.jsx` (Import + Render nach `<RundenVergleichKachel`)

**Interfaces:**
- Produces: `export default function ForderungshistorieKarte({ akteId })` in `components/` — Code identisch zur bisherigen Funktion (`UebersichtSection.jsx:489-689`).

- [ ] **Step 1: Komponente verschieben**

Neue Datei `frontend/src/components/ForderungshistorieKarte.jsx`: den kompletten Funktionskörper von `ForderungshistorieKarte` aus `UebersichtSection.jsx:489-689` unverändert übernehmen, mit diesem Kopf/Fuß:

```jsx
import React from "react";
import T from "../config/theme.js";
import { fmtEuro } from "../config/utils.js";
import { Card, CardHead, Toast } from "./common.jsx";
import { forderungen as apiForderungen } from "../api.js";

export default function ForderungshistorieKarte({ akteId }) {
  // … Körper 1:1 aus UebersichtSection.jsx:490-688 …
}
```

Achtung: im Original wird `React.useState`/`React.useEffect` verwendet — das funktioniert mit `import React` unverändert.

In `UebersichtSection.jsx`: Funktion `ForderungshistorieKarte` löschen und im Import (Zeile 10-17) `forderungen as apiForderungen,` entfernen.

- [ ] **Step 2: In RegulierungSection einbinden**

In `frontend/src/sections/RegulierungSection.jsx` oben ergänzen:

```jsx
import ForderungshistorieKarte from "../components/ForderungshistorieKarte.jsx";
```

Im Haupt-Render von `RegulierungSection` die Stelle `<RundenVergleichKachel` suchen und **direkt nach** deren schließendem Element einfügen:

```jsx
        <ForderungshistorieKarte akteId={akteId} />
```

- [ ] **Step 3: Vollsuite grün**

Run: `cd frontend; npm test`
Expected: PASS.

- [ ] **Step 4: Commit**

```powershell
git add "frontend/src/components/ForderungshistorieKarte.jsx" "frontend/src/sections/UebersichtSection.jsx" "frontend/src/sections/RegulierungSection.jsx"
git commit -m @'
feat(regulierung): Forderungshistorie aus der Uebersicht in den Regulierung-Tab verschoben (Redesign A)
'@
```

---

### Task 5: Mandanten-Aktionen extrahieren + Check-Pills mit Aktions-Popover

**Files:**
- Create: `frontend/src/sections/mandantAktionen.js`
- Test: `frontend/src/sections/mandantAktionen.test.js` (neu)
- Modify: `frontend/src/sections/UebersichtSection.jsx` (`BeteiligterKachel` nutzt Helfer; `StatusBand` bekommt Popover)

**Interfaces:**
- Produces aus `mandantAktionen.js`:
  - `ibanAnfrageMailto(check, mandant) -> string` (mailto-URL)
  - `vollmachtAnfrageMailto(check, mandant) -> string`
  - `vollmachtPdfLaden(akteId) -> Promise<void>` (wirft `Error` mit Meldung bei HTTP-Fehler)
- `StatusBand` neue optionale Props: `akteId`, `mandant`, `onFehler` — bei `iban_vorhanden === false` / `vollmacht_vorhanden === false` öffnet Klick auf die Pill ein Popover mit den Aktionen.

- [ ] **Step 1: Failing Tests schreiben**

`frontend/src/sections/mandantAktionen.test.js`:

```js
import { describe, it, expect, vi } from "vitest";

vi.mock("../api.js", () => ({
  tokenStore: { getAccess: () => "tok" },
}));

import { ibanAnfrageMailto, vollmachtAnfrageMailto } from "./mandantAktionen.js";

describe("mandantAktionen", () => {
  it("baut den IBAN-Anfrage-Link mit Anrede aus den Checks", () => {
    const link = ibanAnfrageMailto(
      { mandant_email: "max@example.com", mandant_name: "Max Müller" },
      { anrede: "Herr" }
    );
    expect(link).toMatch(/^mailto:max@example\.com\?subject=/);
    expect(decodeURIComponent(link)).toContain("Sehr geehrter Herr Müller,");
    expect(decodeURIComponent(link)).toContain("Bankverbindung");
  });

  it("nutzt die neutrale Anrede ohne Anredefeld", () => {
    const link = vollmachtAnfrageMailto({}, { email: "erika@example.com", name: "Erika Beispiel" });
    expect(link).toMatch(/^mailto:erika@example\.com/);
    expect(decodeURIComponent(link)).toContain("Sehr geehrte/r Erika Beispiel,");
    expect(decodeURIComponent(link)).toContain("Vollmacht");
  });
});
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `cd frontend; npm test -- src/sections/mandantAktionen.test.js`
Expected: FAIL (Modul existiert nicht).

- [ ] **Step 3: `mandantAktionen.js` implementieren**

```js
import { tokenStore } from "../api.js";

function anredeZeile(check, mandant) {
  const name = check?.mandant_name || mandant?.name || "Mandant";
  const anrede = (mandant?.anrede || "").trim();
  if (["Herr", "Herrn", "Hr."].includes(anrede)) return `Sehr geehrter Herr ${name.split(" ").pop()},`;
  if (["Frau", "Fr."].includes(anrede))          return `Sehr geehrte Frau ${name.split(" ").pop()},`;
  return `Sehr geehrte/r ${name},`;
}

function empfaenger(check, mandant) {
  return check?.mandant_email || mandant?.email || "";
}

export function ibanAnfrageMailto(check, mandant) {
  const betreff = encodeURIComponent("Bankverbindung für Ihre Akte");
  const body = encodeURIComponent(
    `${anredeZeile(check, mandant)}\n\nfür die Geltendmachung Ihrer Schadensersatzansprüche benötigen wir noch Ihre Bankverbindung (IBAN).\n\nBitte teilen Sie uns Ihre IBAN baldmöglichst mit, damit wir eingegangene Zahlungen umgehend an Sie weiterleiten können.\n\nMit freundlichen Grüßen\nRechtsanwälte Koch, Schatz & Kollegen`
  );
  return `mailto:${empfaenger(check, mandant)}?subject=${betreff}&body=${body}`;
}

export function vollmachtAnfrageMailto(check, mandant) {
  const betreff = encodeURIComponent("Vollmacht – Bitte unterzeichnen und zurücksenden");
  const body = encodeURIComponent(
    `${anredeZeile(check, mandant)}\n\nim Anhang erhalten Sie die Vollmacht für die Bearbeitung Ihrer Schadenssache.\n\nBitte unterzeichnen Sie diese und senden Sie uns die Vollmacht baldmöglichst zurück – per E-Mail, Post oder Fax.\n\nFür Rückfragen stehen wir Ihnen gerne zur Verfügung.\n\nMit freundlichen Grüßen\nRechtsanwälte Koch, Schatz & Kollegen`
  );
  return `mailto:${empfaenger(check, mandant)}?subject=${betreff}&body=${body}`;
}

export async function vollmachtPdfLaden(akteId) {
  const token = tokenStore.getAccess();
  const base = (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_URL) || "";
  const res = await fetch(`${base}/ramicro/akte/vollmacht?az=${encodeURIComponent(akteId)}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.fehler || err.typ || String(res.status));
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `Vollmacht_${(akteId || "").replace("/", "_")}.pdf`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}
```

- [ ] **Step 4: `BeteiligterKachel` auf die Helfer umstellen**

In `UebersichtSection.jsx`:
- Import ergänzen: `import { ibanAnfrageMailto, vollmachtAnfrageMailto, vollmachtPdfLaden } from "./mandantAktionen.js";`
- Die lokalen Funktionen `ibanMailtoLink` (Z. 103-117) und `vollmachtMailtoLink` (Z. 119-133) löschen; Aufrufe ersetzen durch `ibanAnfrageMailto(ibanCheck, liste[0])` bzw. `vollmachtAnfrageMailto(ibanCheck, liste[0])`.
- Den Inline-`onClick` des „Vollmacht generieren"-Buttons (Z. 280-304) ersetzen durch:

```jsx
onClick={() => vollmachtPdfLaden(akteId).catch(e => setToast(`Vollmacht-Fehler: ${e.message}`))}
```

(`tokenStore` aus dem api-Import entfernen, falls danach ungenutzt.)

- [ ] **Step 5: `StatusBand` — Pills mit Popover**

`StatusBand` (Z. 1692) erweitern:

```jsx
function StatusBand({ ibanCheck, todos, hq, akteId, mandant, onFehler }) {
```

Innerhalb von `StatusBand` neue Unterkomponente (direkt vor dem `return`):

```jsx
  const AktionsPill = ({ ok, label, aktionen }) => {
    const [offen, setOffen] = React.useState(false);
    const hatAktionen = ok === false && aktionen.length > 0;
    let bg, color, border;
    if (ok === true)       { bg = T.greenBg; color = T.greenText; border = T.greenLight; }
    else if (ok === false) { bg = T.redBg;   color = T.redText;   border = T.redLight;   }
    else                   { bg = T.surface; color = T.textFaint; border = T.border;     }
    return (
      <span style={{ position:"relative", display:"inline-flex" }}>
        <button
          onClick={() => hatAktionen && setOffen(o => !o)}
          style={{ display:"inline-flex", alignItems:"center", gap:4,
            fontSize:"0.7rem", fontWeight:600, padding:"3px 9px",
            borderRadius:20, border:`1px solid ${border}`, background:bg, color,
            whiteSpace:"nowrap", cursor: hatAktionen ? "pointer" : "default",
            fontFamily:T.fontBody }}>
          {label}{hatAktionen && " ▾"}
        </button>
        {offen && (
          <span style={{ position:"absolute", top:"calc(100% + 4px)", left:0, zIndex:60,
            background:T.cardBg, border:`1px solid ${T.border}`, borderRadius:8,
            boxShadow:"0 6px 18px rgba(0,0,0,.14)", padding:"6px 8px",
            display:"flex", gap:6, whiteSpace:"nowrap" }}>
            {aktionen}
          </span>
        )}
      </span>
    );
  };

  const aktionChip = {
    fontFamily:T.fontBody, fontSize:"0.72rem", fontWeight:600, padding:"3px 9px",
    borderRadius:6, border:`1px solid ${T.accentTrim}`, background:T.accentPale,
    color:T.accentDark, textDecoration:"none", cursor:"pointer",
  };
```

Die drei bisherigen `<Pill …/>`-Aufrufe für Vollmacht und IBAN ersetzen (RSV bleibt bei der alten `Pill`):

```jsx
        <AktionsPill ok={vollmacht}
          label={vollmacht === true ? "✓ Vollmacht" : vollmacht === false ? "✗ Vollmacht fehlt" : "○ Vollmacht"}
          aktionen={vollmacht === false ? [
            <a key="anf" href={vollmachtAnfrageMailto(ibanCheck, mandant)} style={aktionChip}>✉ anfordern</a>,
            <button key="pdf" style={aktionChip}
              onClick={() => akteId && vollmachtPdfLaden(akteId).catch(e => onFehler && onFehler(`Vollmacht-Fehler: ${e.message}`))}>
              ↓ PDF generieren
            </button>,
          ] : []} />
        <AktionsPill ok={iban}
          label={iban === true ? "✓ IBAN" : iban === false ? "✗ IBAN fehlt" : "○ IBAN"}
          aktionen={iban === false ? [
            <a key="anf" href={ibanAnfrageMailto(ibanCheck, mandant)} style={aktionChip}>✉ IBAN anfordern</a>,
          ] : []} />
```

Aufrufstelle in der Hauptkomponente ergänzen:

```jsx
        <StatusBand ibanCheck={mandantChecks} todos={todosState} hq={akte.hq}
          akteId={azRoh}
          mandant={(st.beteiligte || []).find(b => (b.rolle || "").toLowerCase() === "mandant") || null}
          onFehler={setToast} />
```

- [ ] **Step 6: Popover-Test ergänzen**

In `UebersichtSection.redesign.test.jsx` anhängen:

```jsx
import { fireEvent } from "@testing-library/react";
import { StatusBand } from "./UebersichtSection.jsx";

describe("StatusBand-Aktions-Popover", () => {
  it("zeigt bei fehlender Vollmacht die Aktionen nach Klick auf die Pill", () => {
    render(<StatusBand ibanCheck={{ vollmacht_vorhanden: false, iban_vorhanden: true }}
      todos={[]} hq={100} akteId="123/26" mandant={{ email: "m@example.com", name: "Max Müller" }} />);
    fireEvent.click(screen.getByText(/Vollmacht fehlt/));
    expect(screen.getByText(/✉ anfordern/)).toBeInTheDocument();
    expect(screen.getByText(/PDF generieren/)).toBeInTheDocument();
  });
});
```

(Die `fireEvent`/`StatusBand`-Importe in die bestehenden Import-Zeilen des Testfiles integrieren.)

- [ ] **Step 7: Tests grün**

Run: `cd frontend; npm test`
Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add "frontend/src/sections/mandantAktionen.js" "frontend/src/sections/mandantAktionen.test.js" "frontend/src/sections/UebersichtSection.jsx" "frontend/src/sections/UebersichtSection.redesign.test.jsx"
git commit -m @'
feat(uebersicht): Check-Pills mit Aktions-Popover, Mandanten-Aktionen als wiederverwendbare Helfer
'@
```

---

### Task 6: Onboarding-Checks als pure Funktion

**Files:**
- Create: `frontend/src/sections/onboardingChecks.js`
- Test: `frontend/src/sections/onboardingChecks.test.js` (neu; ersetzt fachlich `OnboardingHub.test.jsx`, der in Task 7 gelöscht wird)

**Interfaces:**
- Produces: `berechneOnboardingChecks({ akte, beteiligte, schaden, dokumente }) -> { kacheln, pflichtAnzahl, erledigt, noetig }`
  - `kacheln`: Array `{ key, label, ok, tab, optional? }` — identische Logik/Reihenfolge wie `OnboardingHub.jsx:26-34`.
  - `pflichtAnzahl`: Anzahl Pflicht-Kacheln (6), `erledigt`: davon ok, `noetig`: true solange eine Pflicht-Kachel offen ist.

- [ ] **Step 1: Failing Tests schreiben**

`frontend/src/sections/onboardingChecks.test.js`:

```js
import { describe, it, expect } from "vitest";
import { berechneOnboardingChecks } from "./onboardingChecks.js";

const voll = {
  akte: { unfalldatum: "2026-01-10", unfallort: "Offenbach" },
  beteiligte: [
    { rolle: "mandant", name: "Max Müller" },
    { rolle: "gegner", name: "Erika Beispiel" },
    { kuerzel: "GHPV", name: "HUK-COBURG" },
  ],
  schaden: { gesamt_brutto: 8200 },
  dokumente: [
    { dokumentenklasse: "vollmacht" },
    { dokumentenklasse: "forderungsschreiben" },
  ],
};

const kachel = (r, key) => r.kacheln.find(k => k.key === key);

describe("berechneOnboardingChecks", () => {
  it("meldet noetig=false, wenn alle Pflichtbereiche vollständig sind", () => {
    const r = berechneOnboardingChecks(voll);
    expect(r.noetig).toBe(false);
    expect(r.erledigt).toBe(r.pflichtAnzahl);
  });

  it("erkennt die GHPV über das großgeschriebene Kürzel", () => {
    const r = berechneOnboardingChecks({ beteiligte: [{ kuerzel: "GHPV" }] });
    expect(kachel(r, "ghpv").ok).toBe(true);
  });

  it("erkennt Schadenspositionen über gesamt_brutto", () => {
    const r = berechneOnboardingChecks({ schaden: { gesamt_brutto: 4500 } });
    expect(kachel(r, "schaden").ok).toBe(true);
  });

  it("erkennt Unfalldetails über die Akten-Felder", () => {
    const r = berechneOnboardingChecks({ akte: { unfalldatum: "2026-01-10", unfallort: "Offenbach" } });
    expect(kachel(r, "unfalldetails").ok).toBe(true);
  });

  it("erkennt Vollmacht und Erstforderung über die Dokumentenklasse", () => {
    const r = berechneOnboardingChecks({ dokumente: [
      { dokumentenklasse: "vollmacht" }, { dokumentenklasse: "forderungsschreiben" },
    ] });
    expect(kachel(r, "vollmacht").ok).toBe(true);
    expect(kachel(r, "erstforderung").ok).toBe(true);
  });

  it("zählt die Erstforderung nicht als Pflichtbereich", () => {
    const r = berechneOnboardingChecks(voll);
    expect(r.pflichtAnzahl).toBe(6);
    expect(kachel(r, "erstforderung").optional).toBe(true);
  });
});
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `cd frontend; npm test -- src/sections/onboardingChecks.test.js`
Expected: FAIL (Modul existiert nicht).

- [ ] **Step 3: Implementierung**

`frontend/src/sections/onboardingChecks.js`:

```js
export function berechneOnboardingChecks({ akte = {}, beteiligte = [], schaden = {}, dokumente = [] } = {}) {
  const rolleVon  = (b) => (b.rolle || b.kuerzel || "").toLowerCase();
  const klasseVon = (d) => (d.dokumentenklasse || d.klasse || "").toLowerCase();

  const mandant     = beteiligte.find(b => rolleVon(b) === "mandant");
  const gegner      = beteiligte.find(b => rolleVon(b) === "gegner");
  const ghpv        = beteiligte.find(b => ["ghpv", "ghv", "gbev", "versicherung", "ghpv_versicherung"].includes(rolleVon(b)));
  const hatUnfall   = !!(akte?.unfalldatum && akte?.unfallort);
  const hatSchaden  = (parseFloat(schaden?.abrechnungsberechnung?.gesamt_brutto) || parseFloat(schaden?.gesamt_brutto) || 0) > 0;
  const hatVollmacht = dokumente.some(d => klasseVon(d).includes("vollmacht"));
  const hatErstforderung = dokumente.some(d => klasseVon(d) === "forderungsschreiben");

  const kacheln = [
    { key: "mandant",       label: "Mandant",               ok: !!mandant,        tab: "beteiligte"    },
    { key: "gegner",        label: "Gegner / Schädiger",    ok: !!gegner,         tab: "beteiligte"    },
    { key: "ghpv",          label: "GHPV (Versicherung)",   ok: !!ghpv,           tab: "beteiligte"    },
    { key: "unfalldetails", label: "Unfalldetails",          ok: hatUnfall,        tab: "unfalldetails" },
    { key: "schaden",       label: "Schadenspositionen",    ok: hatSchaden,       tab: "schaden"       },
    { key: "vollmacht",     label: "Vollmacht & Dokumente", ok: hatVollmacht,     tab: "dokumente"     },
    { key: "erstforderung", label: "Erstforderung",         ok: hatErstforderung, tab: "word", optional: true },
  ];

  const pflicht = kacheln.filter(k => !k.optional);
  return {
    kacheln,
    pflichtAnzahl: pflicht.length,
    erledigt: pflicht.filter(k => k.ok).length,
    noetig: pflicht.some(k => !k.ok),
  };
}
```

- [ ] **Step 4: Tests grün**

Run: `cd frontend; npm test -- src/sections/onboardingChecks.test.js`
Expected: PASS (6 Tests).

- [ ] **Step 5: Commit**

```powershell
git add "frontend/src/sections/onboardingChecks.js" "frontend/src/sections/onboardingChecks.test.js"
git commit -m @'
feat(uebersicht): Onboarding-Checks als pure Funktion (Vorbereitung Faecher, Redesign B)
'@
```

---

### Task 7: Onboarding-Fächer im PhasenStrip, Hub-Banner weg

**Files:**
- Create: `frontend/src/sections/OnboardingFaecher.jsx`
- Modify: `frontend/src/sections/UebersichtSection.jsx` (PhasenStrip klickbar + Chip, Fächer rendern, OnboardingHub raus)
- Delete: `frontend/src/sections/OnboardingHub.jsx`, `frontend/src/sections/OnboardingHub.test.jsx`
- Test: `frontend/src/sections/UebersichtSection.redesign.test.jsx` (erweitern)

**Interfaces:**
- Consumes: `berechneOnboardingChecks` (Task 6), `vollmachtAnfrageMailto`/`vollmachtPdfLaden` (Task 5).
- Produces: `<OnboardingFaecher checks onNavigate akteId mandantChecks mandant onFehler />`; `PhasenStrip` neue optionale Props `{ onboarding, faecherOffen, onToggleFaecher }` — Chip `n/6 ▾` nur solange `phase.aktiv === "onboarding"` (verschwindet ab Erstforderung automatisch, kein localStorage).

- [ ] **Step 1: Failing Tests schreiben**

In `UebersichtSection.redesign.test.jsx` anhängen:

```jsx
describe("Redesign B — Onboarding-Fächer", () => {
  const onboardingProps = {
    ...PROPS,
    akte: { ...PROPS.akte },
    st: { ...PROPS.st, schaden: {}, beteiligte: [{ rolle: "mandant", name: "Max Müller" }] },
    posDaten: { positionen: {} },
    kpiSummen: { gefordert: 0, reguliert: 0, offen: 0, quelle: "alt" },
    mandantChecks: { iban_vorhanden: false, vollmacht_vorhanden: false },
  };

  it("zeigt keinen OnboardingHub-Banner mehr", () => {
    render(<UebersichtSection {...onboardingProps} />);
    expect(screen.queryByText(/Bereichen vollständig/)).toBeNull();
  });

  it("öffnet den Fächer per Klick auf die Onboarding-Phase", () => {
    render(<UebersichtSection {...onboardingProps} />);
    fireEvent.click(screen.getByText(/1\/6/));
    expect(screen.getByText("Gegner / Schädiger")).toBeInTheDocument();
    expect(screen.getByText("Schadenspositionen")).toBeInTheDocument();
  });

  it("zeigt in Phase Regulierung keinen Onboarding-Chip", () => {
    render(<UebersichtSection {...PROPS}
      st={{ ...PROPS.st, abrechnungen: [{ id: 1, gesamt_reguliert: 6900, positionen: [] }] }} />);
    expect(screen.queryByText(/\/6/)).toBeNull();
  });
});
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `cd frontend; npm test -- src/sections/UebersichtSection.redesign.test.jsx`
Expected: FAIL (Hub-Banner noch da, kein Chip).

- [ ] **Step 3: `OnboardingFaecher.jsx` implementieren**

```jsx
import React from "react";
import T from "../config/theme.js";
import { vollmachtAnfrageMailto, vollmachtPdfLaden } from "./mandantAktionen.js";

const chip = {
  fontFamily: T.fontBody, fontSize: "0.72rem", fontWeight: 600, padding: "2px 9px",
  borderRadius: 6, border: `1px solid ${T.accentTrim}`, background: T.accentPale,
  color: T.accentDark, textDecoration: "none", cursor: "pointer", whiteSpace: "nowrap",
};

export default function OnboardingFaecher({ checks, onNavigate, akteId, mandantChecks, mandant, onFehler }) {
  return (
    <div style={{
      background: T.cardBg, borderTop: `1px solid ${T.border}`, padding: "10px 18px",
      display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(260px,1fr))", gap: "2px 20px",
    }}>
      {checks.kacheln.map(k => (
        <div key={k.key} style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 0",
          fontFamily: T.fontBody, fontSize: "0.85rem" }}>
          <span style={{ color: k.ok ? T.green : T.amber, fontWeight: 700, width: 16, textAlign: "center" }}>
            {k.ok ? "✓" : "○"}
          </span>
          <span style={{ color: k.ok ? T.textMuted : T.text, fontWeight: k.ok ? 400 : 600 }}>
            {k.label}
            {k.optional && !k.ok && (
              <span style={{ color: T.textFaint, fontSize: "0.7rem", marginLeft: 5 }}>optional</span>
            )}
          </span>
          {!k.ok && (
            <span style={{ marginLeft: "auto", display: "flex", gap: 5 }}>
              {k.key === "vollmacht" && (mandantChecks?.mandant_email || mandant?.email) && (
                <a href={vollmachtAnfrageMailto(mandantChecks, mandant)} style={chip}>✉ anfordern</a>
              )}
              {k.key === "vollmacht" && akteId && (
                <button style={chip}
                  onClick={() => vollmachtPdfLaden(akteId).catch(e => onFehler && onFehler(`Vollmacht-Fehler: ${e.message}`))}>
                  ↓ PDF
                </button>
              )}
              {onNavigate && (
                <button style={chip} onClick={() => onNavigate(k.tab)}>→ öffnen</button>
              )}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: PhasenStrip + Hauptkomponente umbauen**

`PhasenStrip` (UebersichtSection) neue Signatur und Onboarding-Segment:

```jsx
function PhasenStrip({ phase, onboarding = null, faecherOffen = false, onToggleFaecher = null }) {
  if (!phase) return null;
  const { aktiv, istKlage, phasenFertig } = phase;
  const PHASEN = [
    { id: "onboarding",    label: "Onboarding" },
    { id: "erstforderung", label: "Erstforderung" },
    { id: "regulierung",   label: "Regulierung" },
    { id: "stellungnahme", label: "Stellungnahme" },
    { id: "abschluss",     label: istKlage ? "⚖ Klage" : "Abschluss" },
  ];
  return (
    <div style={{ display:"flex", alignItems:"stretch", borderBottom:`1px solid ${T.border}`, overflow:"hidden" }}>
      {PHASEN.map((p, i) => {
        const fertig  = phasenFertig[p.id];
        const isAktiv = aktiv === p.id;
        const last    = i === PHASEN.length - 1;
        const bg    = fertig ? T.greenBg  : isAktiv ? T.blueBg  : T.cardBg;
        const color = fertig ? T.greenText : isAktiv ? T.accent   : T.textFaint;
        const icon  = fertig ? "✓"        : isAktiv ? "▶"        : "○";
        const mitFaecher = p.id === "onboarding" && isAktiv && onboarding;
        const inhalt = (
          <>
            <span>{icon}</span><span>{p.label}</span>
            {mitFaecher && (
              <span style={{ background:T.amberMid, color:T.amberText, borderRadius:10,
                padding:"0 6px", fontWeight:700 }}>
                {onboarding.erledigt}/{onboarding.pflichtAnzahl}
              </span>
            )}
            {mitFaecher && <span>{faecherOffen ? "▴" : "▾"}</span>}
          </>
        );
        const stil = {
          flex:1, display:"flex", alignItems:"center", justifyContent:"center",
          gap:4, padding:"6px 4px",
          background:bg, color,
          borderRight: last ? "none" : `1px solid ${T.border}`,
          fontSize:"0.68rem", fontWeight:600,
          letterSpacing:"0.04em", textTransform:"uppercase", whiteSpace:"nowrap",
          fontFamily:T.fontBody,
        };
        return mitFaecher ? (
          <button key={p.id} onClick={onToggleFaecher} style={{ ...stil, border:"none", cursor:"pointer",
            borderRight: last ? "none" : `1px solid ${T.border}` }}>
            {inhalt}
          </button>
        ) : (
          <div key={p.id} style={stil}>{inhalt}</div>
        );
      })}
    </div>
  );
}
```

Hauptkomponente:
- Imports: `OnboardingHub` raus, dafür `import OnboardingFaecher from "./OnboardingFaecher.jsx";` und `import { berechneOnboardingChecks } from "./onboardingChecks.js";`
- State ergänzen: `const [faecherOffen, setFaecherOffen] = useState(false);`
- Nach der `phase`-Berechnung:

```jsx
  const onboarding = berechneOnboardingChecks({
    akte, beteiligte: st?.beteiligte || [], schaden, dokumente: st?.dokumente || [],
  });
  const mandantBeteiligter = (st.beteiligte || []).find(b => (b.rolle || "").toLowerCase() === "mandant") || null;
```

- Im Render den `<OnboardingHub …/>`-Block ersatzlos streichen und die Leisten-Box so erweitern:

```jsx
      <div style={{ border:`1px solid ${T.border}`, borderRadius:10, overflow:"hidden", marginBottom:"1.25rem", boxShadow:"0 1px 4px rgba(0,0,0,.05)" }}>
        <PhasenStrip phase={phase} onboarding={onboarding}
          faecherOffen={faecherOffen} onToggleFaecher={() => setFaecherOffen(o => !o)} />
        {faecherOffen && phase.aktiv === "onboarding" && (
          <OnboardingFaecher checks={onboarding} onNavigate={onNavigate} akteId={azRoh}
            mandantChecks={mandantChecks} mandant={mandantBeteiligter} onFehler={setToast} />
        )}
        <StatusBand ibanCheck={mandantChecks} todos={todosState} hq={akte.hq}
          akteId={azRoh} mandant={mandantBeteiligter} onFehler={setToast} />
      </div>
```

(Die in Task 5 eingeführte Inline-Mandant-Suche an der StatusBand-Aufrufstelle durch `mandantBeteiligter` ersetzen.)

- [ ] **Step 5: Alte Dateien löschen**

```powershell
Remove-Item "frontend/src/sections/OnboardingHub.jsx", "frontend/src/sections/OnboardingHub.test.jsx" -Confirm:$false
```

- [ ] **Step 6: Vollsuite grün**

Run: `cd frontend; npm test`
Expected: PASS (OnboardingHub-Tests weg, dafür onboardingChecks- + Fächer-Tests).

- [ ] **Step 7: Commit**

```powershell
git add "frontend/src/sections/OnboardingFaecher.jsx" "frontend/src/sections/UebersichtSection.jsx" "frontend/src/sections/UebersichtSection.redesign.test.jsx" "frontend/src/sections/OnboardingHub.jsx" "frontend/src/sections/OnboardingHub.test.jsx"
git commit -m @'
feat(uebersicht): Onboarding-Faecher im PhasenStrip ersetzt den Hub-Banner (Redesign B)
'@
```

---

### Task 8: RA-Micro-Akkordeon ohne Stammdaten-Doppel + mandant-checks nur noch 1 Request

**Files:**
- Modify: `frontend/src/sections/UebersichtSection.jsx` (`RaMicroAkteUebersicht` Z. 359-484, `BeteiligterKachel` Z. 73-99)

**Interfaces:**
- Consumes: Prop `mandantChecks` (wird seit Task 3 an `RaMicroAkteUebersicht` durchgereicht).
- Produces: `BeteiligterKachel` neue optionale Prop `checksProp` — wenn gesetzt, kein eigener `/ramicro/akte/mandant-checks`-Fetch (Review Abschnitt B: Request Nr. 3 entfällt).

- [ ] **Step 1: Stammdaten-Karte entfernen**

In `RaMicroAkteUebersicht` den kompletten `<Card>`-Block „Stammdaten kompakt" (Z. 403-425) löschen — der Header zeigt AZ/SB/KFZ/Kurzbezeichnung bereits. Die Beteiligten-Kacheln bleiben.

- [ ] **Step 2: Checks durchreichen**

`RaMicroAkteUebersicht({ azRoh, mandantChecks = null })` — die Mandanten-`BeteiligterKachel` (Z. 435-442) bekommt zusätzlich `checksProp={mandantChecks}`.

`BeteiligterKachel`: Signatur um `checksProp = null` erweitern; State-Deklaration ändern:

```jsx
  const [ibanCheckGeladen, setIbanCheckGeladen] = useState(null);
  const ibanCheck = checksProp ?? ibanCheckGeladen;
  React.useEffect(() => {
    if (checksProp || titel !== "Mandant" || !akteId || !akteId.includes("/")) return;
    request(`/ramicro/akte/mandant-checks?az=${encodeURIComponent(akteId)}`)
      .then(d => setIbanCheckGeladen(d))
      .catch(() => setIbanCheckGeladen({ iban_vorhanden: null }));
  }, [akteId, titel, checksProp]);
```

(Alle weiteren Lesezugriffe nutzen unverändert `ibanCheck`.)

Zusätzlich („Checks → nur noch StatusBand", Handover Abschnitt 2): in `BeteiligterKachel` die beiden Check-Blöcke `{/* IBAN-Check nur bei Mandanten */}` (Z. 207-247) und `{/* Vollmacht-Check */}` (Z. 248-316) löschen — IBAN-/Vollmacht-Status samt Aktionen liegen jetzt ausschließlich an den StatusBand-Pills (Task 5). Der Vorsteuerabzug-Block bleibt. Danach prüfen, ob `ibanCheck`/`checksProp` in der Kachel überhaupt noch gebraucht werden (nur noch für `mandant_email`-Fallback der RechtsschutzKlappkachel? — falls ungenutzt: Fetch, State und die in Task 5 eingebauten Helfer-Aufrufe aus `BeteiligterKachel` komplett entfernen und den `mandantAktionen`-Import dort streichen).

- [ ] **Step 3: Test ergänzen**

In `UebersichtSection.redesign.test.jsx`:

```jsx
import { ramicroAkte } from "../api.js";

describe("RA-Micro-Akkordeon ohne Stammdaten-Doppel", () => {
  it("zeigt im Akkordeon keine AZ/SB-Stammdatenzeile mehr", async () => {
    ramicroAkte.laden.mockResolvedValueOnce({
      stammdaten: { az: "123/26", sachbearbeiter: "AS", kurzbezeichnung: "Müller ./. HUK" },
      beteiligte: { mandant: [{ name: "Max Müller" }], gegner: [], behoerde: [],
        rechtsschutz: [], eigene_versicherung: [], weitere: [] },
    });
    render(<UebersichtSection {...PROPS} />);
    fireEvent.click(screen.getByText(/RA-Micro Beteiligte/));
    expect(await screen.findByText("Max Müller")).toBeInTheDocument();
    expect(screen.queryByText("Kurzbezeichnung")).toBeNull();
  });
});
```

- [ ] **Step 4: Vollsuite grün**

Run: `cd frontend; npm test`
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add "frontend/src/sections/UebersichtSection.jsx" "frontend/src/sections/UebersichtSection.redesign.test.jsx"
git commit -m @'
feat(uebersicht): RA-Micro-Akkordeon nur noch Beteiligte, mandant-checks nur noch 1 Request pro Akte
'@
```

---

### Task 9: Tab-Leiste beruhigen + Kosmetik-Reste

**Files:**
- Modify: `frontend/src/components/AkteDetailView.jsx` (tabs-useMemo Z. 208-240, Tab-Render Z. 370-395, Action-Button-Padding Z. 327)

**Interfaces:**
- Produces: Tab-Einträge `{ id, label, status?: "ok"|"warn", anzahl?: number, neu?: number }`; Render mit farbigem Punkt statt ✅/⚠️, grauem Zähler-Badge und rotem `n neu`-Badge (Handover Abschnitt 6).

- [ ] **Step 1: tabs-useMemo umstellen**

`sp` und die Einträge ersetzen:

```jsx
    const sp = (ok, fehlt) => ok ? { status: "ok" } : fehlt ? { status: "warn" } : {};

    return [
      { id:"uebersicht",    label:"⚡ Übersicht" },
      { id:"beteiligte",    label:"👥 Beteiligte", ...sp(beteiligteOk, !beteiligteOk && st.beteiligte !== undefined) },
      { id:"unfalldetails", label:"🔍 Unfalldetails" },
      { id:"schaden",       label:"🚗 Schaden", ...sp(schadenOk, !schadenOk && st.schaden !== undefined) },
      { id:"dokumente",     label:"📄 Dokumente", anzahl: dokumenteAnz, neu: neueDokumente },
      { id:"regulierung",   label:"💶 Regulierung", neu: neueAbrechnung ? 1 : 0, ...sp(regulierungOk, false) },
      { id:"klage",         label:"⚖ Klage", ...sp(klageStatus, false) },
      { id:"word",          label:"📝 Word" },
      { id:"gebuehren",     label:"💰 Gebühren" },
    ];
```

- [ ] **Step 2: Tab-Render umstellen**

Im Button-Body (Z. 389-393) ersetzen. Alt:

```jsx
              {t.label}
              {t.dot && t.dot !== "⬜" && (
                <span style={{ fontSize:"0.7rem", lineHeight:1 }}>{t.dot}</span>
              )}
```

Neu:

```jsx
              {t.label}
              {t.anzahl != null && (
                <span style={{ fontSize:"0.68rem", fontWeight:600, lineHeight:1,
                  background:"rgba(255,255,255,0.12)", borderRadius:9, padding:"2px 6px" }}>
                  {t.anzahl}
                </span>
              )}
              {t.neu > 0 && (
                <span style={{ fontSize:"0.66rem", fontWeight:700, lineHeight:1,
                  background:"#ef4444", color:"#fff", borderRadius:9, padding:"2px 6px" }}>
                  {t.neu} neu
                </span>
              )}
              {t.status && (
                <span style={{ width:7, height:7, borderRadius:"50%", flexShrink:0,
                  background: t.status === "ok" ? "#34d399" : "#fbbf24" }} />
              )}
```

- [ ] **Step 3: Doppelte Einrückung der Action-Buttons fixen**

Zeile 327: `padding:"6px 1.75rem 8px"` → `padding:"6px 0 8px"`.

- [ ] **Step 4: Vollsuite grün + Commit**

Run: `cd frontend; npm test`
Expected: PASS.

```powershell
git add "frontend/src/components/AkteDetailView.jsx"
git commit -m @'
feat(uebersicht): Tab-Leiste mit Farbpunkten und Badges statt Status-Emojis, Button-Einrückung gefixt
'@
```

---

### Task 10: `dringlichkeit()` deduplizieren

**Files:**
- Modify: `frontend/src/config/utils.js` (Export ergänzen)
- Modify: `frontend/src/sections/UebersichtSection.jsx` (TodoSection Z. 1148-1167, TodoWvSpalten Z. 1531-1541)
- Test: `frontend/src/config/todoDringlichkeit.test.js` (neu)

**Interfaces:**
- Produces: `todoDringlichkeit(todo, heute = new Date()) -> "rot"|"orange"|"gelb"|"grau"` aus `config/utils.js` (Logik identisch zu den beiden bisherigen Kopien; Verjährungs-Eskalation inklusive).

- [ ] **Step 1: Failing Tests schreiben**

`frontend/src/config/todoDringlichkeit.test.js`:

```js
import { describe, it, expect } from "vitest";
import { todoDringlichkeit } from "./utils.js";

const HEUTE = new Date("2026-08-10T12:00:00");

describe("todoDringlichkeit", () => {
  it("stuft nach Fälligkeit: <3 Tage rot, <7 orange, <14 gelb, sonst grau", () => {
    expect(todoDringlichkeit({ faellig_am: "2026-08-11" }, HEUTE)).toBe("rot");
    expect(todoDringlichkeit({ faellig_am: "2026-08-15" }, HEUTE)).toBe("orange");
    expect(todoDringlichkeit({ faellig_am: "2026-08-22" }, HEUTE)).toBe("gelb");
    expect(todoDringlichkeit({ faellig_am: "2026-09-30" }, HEUTE)).toBe("grau");
  });

  it("eskaliert Verjährungsfristen eine Stufe", () => {
    expect(todoDringlichkeit({ faellig_am: "2026-08-15", frist_typ: "verjaehrung" }, HEUTE)).toBe("rot");
    expect(todoDringlichkeit({ faellig_am: "2026-09-30", frist_typ: "verjaehrung" }, HEUTE)).toBe("gelb");
  });

  it("stuft ohne Fälligkeit nach Alter", () => {
    expect(todoDringlichkeit({ erstellt_am: "2026-08-09" }, HEUTE)).toBe("grau");
    expect(todoDringlichkeit({ erstellt_am: "2026-08-01" }, HEUTE)).toBe("orange");
    expect(todoDringlichkeit({ erstellt_am: "2026-07-01" }, HEUTE)).toBe("rot");
  });
});
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `cd frontend; npm test -- src/config/todoDringlichkeit.test.js`
Expected: FAIL.

- [ ] **Step 3: Implementierung + Umstellung**

In `frontend/src/config/utils.js`:

```js
export function todoDringlichkeit(todo, heute = new Date()) {
  const h = new Date(heute); h.setHours(0, 0, 0, 0);
  if (todo.faellig_am) {
    const frist = new Date(todo.faellig_am); frist.setHours(0, 0, 0, 0);
    const tage = Math.round((frist - h) / 86400000);
    const stufe = tage < 3 ? "rot" : tage < 7 ? "orange" : tage < 14 ? "gelb" : "grau";
    return todo.frist_typ === "verjaehrung"
      ? { rot: "rot", orange: "rot", gelb: "orange", grau: "gelb" }[stufe] || stufe
      : stufe;
  }
  const erstellt = new Date(todo.erstellt_am); erstellt.setHours(0, 0, 0, 0);
  const alter = Math.round((h - erstellt) / 86400000);
  if (alter >= 15) return "rot";
  if (alter >= 8)  return "orange";
  if (alter >= 4)  return "gelb";
  return "grau";
}
```

In `UebersichtSection.jsx`: `todoDringlichkeit` in den utils-Import aufnehmen; die beiden lokalen `dringlichkeit`-Funktionen (TodoSection Z. 1148-1167, TodoWvSpalten Z. 1531-1541) löschen und die Aufrufe `dringlichkeit(todo)` → `todoDringlichkeit(todo)` ersetzen.

- [ ] **Step 4: Vollsuite grün + Commit**

Run: `cd frontend; npm test`
Expected: PASS.

```powershell
git add "frontend/src/config/utils.js" "frontend/src/config/todoDringlichkeit.test.js" "frontend/src/sections/UebersichtSection.jsx"
git commit -m @'
refactor(uebersicht): dringlichkeit()-Ampel in todoDringlichkeit() dedupliziert
'@
```

---

### Task 11: Doku + Abschluss

**Files:**
- Modify: `docs/CHANGELOG.md` (neuer Eintrag oben)
- Modify: `docs/TODO.md` (Redesign-Session aus „In Arbeit/Backlog" austragen, Browser-Abnahme eintragen)
- Modify: `docs/DECISIONS.md` (B3-Entscheidung)

- [ ] **Step 1: DECISIONS.md ergänzen** (im Stil der bestehenden Einträge, Datum 2026-08-10):

Inhalt: **Summen-SSOT (Befund B3):** Einzige Geld-Wahrheit der Akte ist das Ereignismodell (`/akten/<az>/positionen/status`); Header-KPI, PositionsDashboard und Phasenberechnung lesen dieselbe Response (ein Fetch in AkteDetailView). Alt-Berechnung (`liveBrutto × HQ` / `Σ gesamt_reguliert`) existiert nur noch als Fallback für Bestandsakten ohne Ereignisse und wird mit dem Feld `quelle: "alt"` markiert. FinanzBand, RegulierungsTabelle (Übersicht) und Forderungshistorie (Übersicht) wurden dafür entfernt bzw. in den Regulierung-Tab verlagert.

- [ ] **Step 2: CHANGELOG.md-Eintrag** (Muster der bestehenden Einträge): Übersicht-Redesign A+B, Aufzählung der Tasks 1-10 mit Commit-Hashes (nach `git log --oneline -12` ermitteln), Verweis auf Mockup-Handover.

- [ ] **Step 3: TODO.md aktualisieren**: „Übersicht-Redesign (Mockups A+B)" als erledigt austragen; neu unter „Unklar/Abnahme": „Browser-Abnahme Übersicht-Redesign durch RA Schatz (Fächer, Pill-Popover, KPI-Zahlen an echter Akte, Bestandsakten-Fallback)".

- [ ] **Step 4: Vollsuite final**

Run: `cd frontend; npm test`
Expected: PASS. Anzahl notieren für CHANGELOG.

- [ ] **Step 5: Commit**

```powershell
git add "docs/CHANGELOG.md" "docs/TODO.md" "docs/DECISIONS.md"
git commit -m @'
docs: Uebersicht-Redesign A+B protokolliert (CHANGELOG/TODO/DECISIONS)
'@
```

---

## Offene Punkte nach diesem Plan (bewusst NICHT enthalten)

- **Browser-Abnahme durch RA Schatz** (Docker-Dev, echte Akte + Bestandsakte) — insbesondere: stimmen Header-KPI und PositionsDashboard jetzt überein, funktioniert der Fallback, wirkt der Fächer.
- Mockup C (Cockpit) — nur falls A+B im Alltag nicht reichen.
- Merge-Strategie `abschlussbericht` → main (Branch stapelt weiterhin auf Intake-Branch).
