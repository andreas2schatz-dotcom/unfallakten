# Dashboard-Hell-Umbau Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die Tagesübersicht (ActionBoardView) von hart codiertem Dark-Mode auf die helle Pergament-Palette des Design-Systems umbauen — mit „Jetzt dran"-Leiste, Fristen links oben (Raster 3:2), ohne Posteingang-Kachel, mit sauberen Lade-/Fehler-/Leer-Zuständen, Tastaturbedienung und persistiertem SB-Filter.

**Architecture:** Gemeinsame UI-Bausteine (`boardUi.jsx`) ersetzen die vier per-Kachel-Stilobjekte; alle Farben kommen aus `T` (config/theme.js → tokens.css), dadurch funktioniert auch das clio-Scheme automatisch. `ActionBoardView` hält pro Datenquelle einen Status (`laedt`/`ok`/`fehler`), die Kacheln rendern die Zustände über `KachelInhalt`. Die „Jetzt dran"-Leiste ist eine reine Ableitung aus Fristen + WV (keine neue API). Posteingang-Kachel und `nachrichtenNeu`-Aufruf entfallen ersatzlos.

**Tech Stack:** React 18 (JSX, Inline-Styles wie im Bestand), Vitest + @testing-library/react (jsdom), CSS-Tokens aus `tokens.css` via `T`-Konstanten, SVG-Icons aus `config/icons.jsx`.

**Spec:** Freigegebenes Mockup → `docs/superpowers/specs/2026-07-30-dashboard-hell-mockup.html` (wird in Task 1 abgelegt). Review-Befunde: Nielsen 14/40; P0 = dunkle Farben + stille API-Fehler mit falscher Entwarnung; P1 = Tastatur + borderLeft-Streifen/Emoji; P2 = SB-Filter.

## Global Constraints

- **Git-Wurzel ist das Home-Verzeichnis** (`C:\Users\HAL9000`), nicht der Projektordner. NIEMALS `git add -A` oder `git add .` — immer nur explizite Dateipfade stagen.
- **Branch:** `dashboard-hell`, abgezweigt vom aktuellen Stand des Branches `aktenanlage` (Commit `092ea3e0` ff.). Begründung: Die Dev-Container laufen auf `aktenanlage`, dessen Abnahmetest noch aussteht — ein Wechsel auf `main` würde dem Nutzer das ungetestete Aktenanlage-Feature aus der laufenden App nehmen. Die Dashboard-Commits berühren ausschließlich Dashboard-Dateien und sind nach dem `aktenanlage`-Merge konfliktfrei nach `main` übertragbar (notfalls Cherry-pick).
- **Merge-Reihenfolge:** `dashboard-hell` wird NICHT vor `aktenanlage` in `main` gemergt.
- **Zielsprache Deutsch** (UI-Texte, Commits, Doku). Keine Code-Kommentare außer bei nicht-offensichtlichem Verhalten.
- **Verboten:** `borderLeft`/`borderRight` > 1px als Farbstreifen; Emoji als Icons; neue Hex-Farbwerte (alle Farben über `T.*`; einzige geduldete Bestandsausnahme: `T.amberMid` als Warn-Rahmen, da tokens.css keinen Warn-Border-Token hat).
- **Tests:** `cd frontend && npx vitest run <datei>`. Falls auf dem Host `node_modules` fehlen: `docker exec unfallakten-frontend-dev npx vitest run <datei>`.
- **Dev-Container:** Vite-HMR ist unter Windows kaputt — nach Abschluss `docker restart unfallakten-frontend-dev`.
- **Datenformen (Bestand, unverändert):**
  - `apiDashboard.fristen()` → `{ eintraege: [{ az, frist_art, frist_datum, tage_bis, kurzbezeichnung, mandant }] }`
  - `apiDashboard.termineHeute()` → `{ eintraege: [{ az, termin_art, termin_datum, uhrzeit, tage_bis, kurzbezeichnung, mandant }] }`
  - `apiDashboard.wiedervorlagen()` → `{ wv: [{ az, datum, tage_bis, grund, kurzbezeichnung, mandant }], ohne_wv: [{ az, kurzbezeichnung, mandant }] }`
- **Außerhalb des Scopes:** Sidebar/TopNav der App (Emoji-Nav-Icons in App.jsx), `body`-Hintergrund in globals.css, StatistikenView-Erreichbarkeit, SB-Klarnamen-Tooltips (Kürzel-Zuordnung muss RA Schatz erst liefern).

---

### Task 1: Branch + Spec sichern

**Files:**
- Create: `docs/superpowers/specs/2026-07-30-dashboard-hell-mockup.html` (Kopie aus Scratchpad)
- Create: `docs/superpowers/specs/2026-07-30-dashboard-hell-spec.md`

**Interfaces:**
- Produces: Branch `dashboard-hell`; Spec-Dateien als Referenz für alle Folge-Tasks.

- [ ] **Step 1: Branch anlegen**

```bash
cd "C:/Users/HAL9000/Documents/Projekt/Version 1.00/unfallakten"
git switch -c dashboard-hell
```

Expected: `Switched to a new branch 'dashboard-hell'`

- [ ] **Step 2: Mockup-HTML in die Specs kopieren**

```bash
cp "C:/Users/HAL9000/AppData/Local/Temp/claude/C--Users-HAL9000-Documents-Projekt-Version-1-00-unfallakten/1a418a8b-5480-48e8-b303-672d5dcef58b/scratchpad/mockup-dashboard.html" "docs/superpowers/specs/2026-07-30-dashboard-hell-mockup.html"
```

- [ ] **Step 3: Kurz-Spec schreiben**

`docs/superpowers/specs/2026-07-30-dashboard-hell-spec.md`:

```markdown
# Spec: Dashboard-Hell-Umbau (Tagesübersicht)

Freigegeben von RA Schatz am 2026-07-30 (Mockup gefiel „sehr gut").
Visuelle Referenz: `2026-07-30-dashboard-hell-mockup.html` (im Browser öffnen).

## Anforderungen

1. **Farben:** Pergament-Palette aus tokens.css (`--color-bg-page`, `--color-bg-card`,
   `--color-bg-inset`, Status-Töne). Navy nur noch Navigation (Shell), nicht im Inhalt.
   Kein `fontFamily`-Override mehr (Figtree/Bricolage erben). Keine borderLeft-Streifen,
   keine Emoji-Icons (SVG aus `config/icons.jsx`).
2. **Eine Farbachse = Dringlichkeit:** Rot ausschließlich überfällig (Zeilen-Tint
   `--color-status-danger-bg` + Voll-Badge), Gelb = heute fällig, alles andere neutral.
   Kachel-Identität nur über Titel + Terrakotta-Icon.
3. **Layout:** „Jetzt dran"-Leiste (max. 3 dringendste aus Fristen + WV) volle Breite
   oben; darunter Raster 3:2 — links Fristen + Wiedervorlagen, rechts Termine.
   Posteingang-Kachel entfällt ersatzlos (E-Mail-Arbeit: E-Mail-Import/Review-Queue).
   Keine internen Kachel-Scrollbalken/`maxHeight`-Formeln — die Seite scrollt.
4. **Zustände je Kachel:** Laden (Skeleton) / Fehler (roter Block + „Erneut laden") /
   Leer (nur bei bestätigt leerer Antwort, leiser Text + grünes Häkchen). Ein stiller
   API-Fehler darf NIE wie ein leerer (guter) Tag aussehen — Haftungsrisiko Fristen.
5. **Tastatur:** Jeder Eintrag ist ein echter `<button>`; Enter öffnet die Akte;
   `:focus-visible` aus globals.css greift.
6. **SB-Filter:** Auswahl persistiert in localStorage (`dashboard.aktiveSB`);
   leere Auswahl zeigt den Hinweis „Kein Sachbearbeiter ausgewählt" statt der
   bisherigen Invertierungslogik (leer = alle).
7. **Redundanz raus:** Überfälligkeit steht nur im Badge („−3 T"), nicht zusätzlich
   im Label-Text.

## Kontext aus dem Review (2026-07-30)

Nielsen 14/40. Detektor: 4× borderLeft-Streifen (alle Kacheln). 5 WCAG-Kontrast-Fails
(schlimmster 1,9:1). Dunkelanteil Viewport ~100 % statt Soll ~18 %.
```

- [ ] **Step 4: Commit**

```bash
git add "docs/superpowers/specs/2026-07-30-dashboard-hell-mockup.html" "docs/superpowers/specs/2026-07-30-dashboard-hell-spec.md"
git commit -m "docs(dashboard): Spec + freigegebenes Mockup Dashboard-Hell-Umbau

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Gemeinsame UI-Bausteine `boardUi.jsx`

**Files:**
- Create: `frontend/src/views/action_board/boardUi.jsx`
- Test: `frontend/src/views/action_board/boardUi.test.jsx`

**Interfaces:**
- Consumes: `T` aus `../../config/theme`, `Ic` aus `../../config/icons` (statische JSX-Elemente mit `fill="currentColor"` — Färbung über umgebenden `span` mit `color`).
- Produces (von Tasks 3–6 verwendet, Signaturen exakt so):
  - `Kachel({ icon, titel, zusammenfassung, children })` — Karten-Rahmen mit Kopfzeile
  - `KachelInhalt({ status, fehlerText, onRetry, leer, leerText, children })` — `status`: `"laedt" | "ok" | "fehler"`
  - `Zeile({ stufe, onClick, links, rechts })` — `stufe`: `"rot" | "gelb" | undefined`; rendert `<button>`
  - `ZeileText({ titel, meta, metaFarbe })`
  - `StufenBadge({ stufe, children })`
  - `AbschnittLabel({ abstandOben, children })`
  - `MehrKnopf({ onClick, children })`

- [ ] **Step 1: Failing Test schreiben**

`frontend/src/views/action_board/boardUi.test.jsx`:

```jsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Kachel, KachelInhalt, Zeile, ZeileText, StufenBadge } from "./boardUi";

describe("boardUi", () => {
  it("KachelInhalt zeigt bei laedt weder Leertext noch Kinder", () => {
    render(
      <KachelInhalt status="laedt" leerText="Nichts da" leer={true}>
        <div>Inhalt</div>
      </KachelInhalt>
    );
    expect(screen.queryByText("Nichts da")).toBeNull();
    expect(screen.queryByText("Inhalt")).toBeNull();
  });

  it("KachelInhalt zeigt bei fehler den Fehlertext und ruft onRetry", () => {
    const retry = vi.fn();
    render(
      <KachelInhalt status="fehler" fehlerText="Fristen konnten nicht geladen werden" onRetry={retry}>
        <div>Inhalt</div>
      </KachelInhalt>
    );
    expect(screen.getByText("Fristen konnten nicht geladen werden")).toBeInTheDocument();
    expect(screen.queryByText("Inhalt")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Erneut laden" }));
    expect(retry).toHaveBeenCalledTimes(1);
  });

  it("KachelInhalt zeigt bei ok+leer den Leertext, sonst die Kinder", () => {
    const { rerender } = render(
      <KachelInhalt status="ok" leer={true} leerText="Keine Fristen">
        <div>Inhalt</div>
      </KachelInhalt>
    );
    expect(screen.getByText("Keine Fristen")).toBeInTheDocument();
    rerender(
      <KachelInhalt status="ok" leer={false} leerText="Keine Fristen">
        <div>Inhalt</div>
      </KachelInhalt>
    );
    expect(screen.getByText("Inhalt")).toBeInTheDocument();
    expect(screen.queryByText("Keine Fristen")).toBeNull();
  });

  it("Zeile ist ein Button und feuert onClick", () => {
    const klick = vi.fn();
    render(
      <Zeile stufe="rot" onClick={klick} links={<ZeileText titel="312/26 AS · Müller" meta="Stellungnahme" />} rechts={<StufenBadge stufe="rot">−3 T</StufenBadge>} />
    );
    const btn = screen.getByRole("button");
    fireEvent.click(btn);
    expect(klick).toHaveBeenCalledTimes(1);
    expect(btn.style.borderLeftWidth).not.toBe("3px");
  });

  it("Kachel rendert Titel und Zusammenfassung", () => {
    render(<Kachel icon={<svg />} titel="Fristen" zusammenfassung="2 überfällig"><div /></Kachel>);
    expect(screen.getByText("Fristen")).toBeInTheDocument();
    expect(screen.getByText("2 überfällig")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `cd frontend && npx vitest run src/views/action_board/boardUi.test.jsx`
Expected: FAIL — `Cannot find module './boardUi'` (o. ä.)

- [ ] **Step 3: `boardUi.jsx` implementieren**

```jsx
import React from "react";
import { T } from "../../config/theme";
import Ic from "../../config/icons";

const STUFEN = {
  rot:  { zeileBg: T.redBg,   zeileBorder: T.redLight, meta: T.redText,   badgeBg: T.red,      badgeFg: "#FFFFFF",  badgeBorder: "transparent" },
  gelb: { zeileBg: T.amberBg, zeileBorder: T.amberMid, meta: T.amberText, badgeBg: T.amberBg,  badgeFg: T.amberText, badgeBorder: T.amberMid },
};

export function Kachel({ icon, titel, zusammenfassung, children }) {
  return (
    <section style={{ background: T.cardBg, border: `1px solid ${T.border}`, borderRadius: 10, padding: "13px 15px 14px", minWidth: 0 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 11 }}>
        <span style={{ color: T.accent, display: "flex" }}>{icon}</span>
        <span style={{ fontFamily: T.fontDisplay, fontSize: T.textSm, fontWeight: T.weightSemibold || 600, letterSpacing: "0.07em", textTransform: "uppercase", color: T.textMid }}>{titel}</span>
        {zusammenfassung && (
          <span className="tabular-nums" style={{ marginLeft: "auto", fontSize: T.textXs, color: T.textMuted }}>{zusammenfassung}</span>
        )}
      </div>
      {children}
    </section>
  );
}

export function KachelInhalt({ status, fehlerText, onRetry, leer, leerText, children }) {
  if (status === "laedt") {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 9, padding: "4px 0" }}>
        {[88, 70, 79].map((breite) => (
          <div key={breite} style={{ height: 11, width: `${breite}%`, borderRadius: 5, background: `linear-gradient(90deg, ${T.surface} 25%, ${T.border} 50%, ${T.surface} 75%)`, backgroundSize: "200% 100%", animation: "shimmer 1.4s linear infinite" }} />
        ))}
      </div>
    );
  }
  if (status === "fehler") {
    return (
      <div style={{ background: T.redBg, border: `1px solid ${T.redLight}`, borderRadius: 7, padding: "10px 12px" }}>
        <div style={{ fontSize: T.textSm, fontWeight: 600, color: T.redText }}>{fehlerText}</div>
        <button onClick={onRetry} style={{ marginTop: 8, fontSize: T.textXs, fontWeight: 600, color: T.redText, border: `1px solid ${T.redLight}`, background: T.cardBg, borderRadius: 6, padding: "4px 10px", cursor: "pointer" }}>
          Erneut laden
        </button>
      </div>
    );
  }
  if (leer) {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: T.textSm, color: T.textMuted, padding: "10px 2px" }}>
        <span style={{ color: T.green, display: "flex" }}>{Ic.check}</span>
        {leerText}
      </div>
    );
  }
  return children;
}

export function Zeile({ stufe, onClick, links, rechts }) {
  const s = STUFEN[stufe];
  return (
    <button
      onClick={onClick}
      style={{
        display: "flex", alignItems: "center", gap: 10, width: "100%", textAlign: "left",
        padding: "8px 12px", borderRadius: 7, cursor: "pointer", font: "inherit", color: "inherit",
        background: s ? s.zeileBg : T.surface,
        border: `1px solid ${s ? s.zeileBorder : T.border}`,
      }}
    >
      <span style={{ flex: 1, minWidth: 0 }}>{links}</span>
      {rechts}
      <span style={{ color: T.textFaint, display: "flex" }}>{Ic.chevR}</span>
    </button>
  );
}

export function ZeileText({ titel, meta, metaFarbe }) {
  return (
    <span style={{ display: "block", minWidth: 0 }}>
      <span style={{ display: "block", fontSize: T.textSm, fontWeight: 500, color: T.text, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{titel}</span>
      {meta && (
        <span style={{ display: "block", fontSize: T.textXs, color: metaFarbe || T.textMuted, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", marginTop: 1 }}>{meta}</span>
      )}
    </span>
  );
}

export function StufenBadge({ stufe, children }) {
  const s = STUFEN[stufe] || STUFEN.gelb;
  return (
    <span className="tabular-nums" style={{ fontSize: "0.6875rem", fontWeight: 600, padding: "2px 8px", borderRadius: 999, whiteSpace: "nowrap", background: s.badgeBg, color: s.badgeFg, border: `1px solid ${s.badgeBorder}` }}>
      {children}
    </span>
  );
}

export function AbschnittLabel({ abstandOben, children }) {
  return (
    <div style={{ fontSize: "0.65625rem", fontWeight: 600, letterSpacing: "0.07em", textTransform: "uppercase", color: T.textMuted, margin: `${abstandOben ? 12 : 0}px 2px 6px` }}>
      {children}
    </div>
  );
}

export function MehrKnopf({ onClick, children }) {
  return (
    <button onClick={onClick} style={{ display: "block", marginTop: 9, fontSize: T.textXs, color: T.textMuted, cursor: "pointer", background: "none", border: "none", padding: "4px 2px" }}>
      {children} ›
    </button>
  );
}

export function ZeilenListe({ children }) {
  return <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>{children}</div>;
}
```

Hinweis: `T.weightSemibold` existiert nicht in theme.js — im Code direkt `600` verwenden (der Ausdruck oben zeigt den Fallback; final: `fontWeight: 600`).

- [ ] **Step 4: Test laufen lassen — muss grün sein**

Run: `cd frontend && npx vitest run src/views/action_board/boardUi.test.jsx`
Expected: PASS (5 Tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/action_board/boardUi.jsx frontend/src/views/action_board/boardUi.test.jsx
git commit -m "feat(dashboard): boardUi-Bausteine (Kachel, Zustaende, Zeilen-Buttons)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: FristenKachel-Umbau

**Files:**
- Modify: `frontend/src/views/action_board/FristenKachel.jsx` (kompletter Ersatz)
- Test: `frontend/src/views/action_board/FristenKachel.test.jsx`

**Interfaces:**
- Consumes: alle boardUi-Exporte (Task 2), `fmtDatumDe` aus `../../config/utils`, `Ic.scale`.
- Produces: `FristenKachel({ status, eintraege, onOpenAkte, onRetry })` — von Task 7 verwendet.

- [ ] **Step 1: Failing Test schreiben**

`frontend/src/views/action_board/FristenKachel.test.jsx`:

```jsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import FristenKachel from "./FristenKachel";

const EINTRAEGE = [
  { az: "312/26 AS", frist_art: "Stellungnahme", frist_datum: "2026-07-27", tage_bis: -3, kurzbezeichnung: "Müller ./. HUK-Coburg" },
  { az: "218/26 PK", frist_art: "Klageerwiderung", frist_datum: "2026-07-30", tage_bis: 0, kurzbezeichnung: "Weber ./. Allianz" },
  { az: "402/26 AS", frist_art: "Nachbesserung Gutachten", frist_datum: "2026-08-01", tage_bis: 2, kurzbezeichnung: "Öztürk ./. R+V" },
];

describe("FristenKachel", () => {
  it("teilt in Handlungsbedarf und Demnächst und zeigt Badges statt Text-Redundanz", () => {
    render(<FristenKachel status="ok" eintraege={EINTRAEGE} onOpenAkte={() => {}} onRetry={() => {}} />);
    expect(screen.getByText("Handlungsbedarf")).toBeInTheDocument();
    expect(screen.getByText("Demnächst")).toBeInTheDocument();
    expect(screen.getByText("−3 T")).toBeInTheDocument();
    expect(screen.getByText("heute")).toBeInTheDocument();
    expect(screen.queryByText(/ÜBERFÄLLIG/)).toBeNull();
  });

  it("jeder Eintrag ist ein Button und öffnet die Akte", () => {
    const oeffne = vi.fn();
    render(<FristenKachel status="ok" eintraege={EINTRAEGE} onOpenAkte={oeffne} onRetry={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /312\/26 AS/ }));
    expect(oeffne).toHaveBeenCalledWith("312/26 AS");
  });

  it("zeigt Fehlerzustand statt Leertext bei status=fehler", () => {
    render(<FristenKachel status="fehler" eintraege={[]} onOpenAkte={() => {}} onRetry={() => {}} />);
    expect(screen.getByText("Fristen konnten nicht geladen werden")).toBeInTheDocument();
    expect(screen.queryByText(/Keine Fristen/)).toBeNull();
  });

  it("zeigt Leertext nur bei status=ok", () => {
    render(<FristenKachel status="ok" eintraege={[]} onOpenAkte={() => {}} onRetry={() => {}} />);
    expect(screen.getByText("Keine Fristen in den nächsten 14 Tagen")).toBeInTheDocument();
  });

  it("Kopf-Zusammenfassung nennt die Lage", () => {
    render(<FristenKachel status="ok" eintraege={EINTRAEGE} onOpenAkte={() => {}} onRetry={() => {}} />);
    expect(screen.getByText(/1 überfällig/)).toBeInTheDocument();
    expect(screen.getByText(/1 heute · 1 demnächst/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `cd frontend && npx vitest run src/views/action_board/FristenKachel.test.jsx`
Expected: FAIL (alte Komponente kennt weder `status` noch die neuen Texte)

- [ ] **Step 3: `FristenKachel.jsx` komplett ersetzen**

```jsx
import React from "react";
import { T } from "../../config/theme";
import Ic from "../../config/icons";
import { fmtDatumDe } from "../../config/utils";
import { Kachel, KachelInhalt, Zeile, ZeileText, StufenBadge, AbschnittLabel, ZeilenListe } from "./boardUi";

function badgeText(tage) {
  return tage === 0 ? "heute" : `−${Math.abs(tage)} T`;
}

export default function FristenKachel({ status, eintraege, onOpenAkte, onRetry }) {
  const dringend    = eintraege.filter((e) => e.tage_bis <= 0);
  const demnaechst  = eintraege.filter((e) => e.tage_bis > 0);
  const ueberfaellig = dringend.filter((e) => e.tage_bis < 0).length;
  const heuteFaellig = dringend.length - ueberfaellig;

  const zusammenfassung = status === "ok" && eintraege.length > 0 ? (
    <>
      {ueberfaellig > 0 && <b style={{ color: T.redText, fontWeight: 600 }}>{ueberfaellig} überfällig · </b>}
      {heuteFaellig} heute · {demnaechst.length} demnächst
    </>
  ) : null;

  return (
    <Kachel icon={Ic.scale} titel="Fristen" zusammenfassung={zusammenfassung}>
      <KachelInhalt
        status={status}
        fehlerText="Fristen konnten nicht geladen werden"
        onRetry={onRetry}
        leer={eintraege.length === 0}
        leerText="Keine Fristen in den nächsten 14 Tagen"
      >
        {dringend.length > 0 && (
          <>
            <AbschnittLabel>Handlungsbedarf</AbschnittLabel>
            <ZeilenListe>
              {dringend.map((e) => {
                const stufe = e.tage_bis < 0 ? "rot" : "gelb";
                return (
                  <Zeile
                    key={e.az + e.frist_datum}
                    stufe={stufe}
                    onClick={() => onOpenAkte(e.az)}
                    links={
                      <ZeileText
                        titel={<><b className="tabular-nums">{e.az}</b> · {e.kurzbezeichnung || e.mandant}</>}
                        meta={`${e.frist_art} · Frist ${fmtDatumDe(e.frist_datum)}`}
                        metaFarbe={stufe === "rot" ? T.redText : T.amberText}
                      />
                    }
                    rechts={<StufenBadge stufe={stufe}>{badgeText(e.tage_bis)}</StufenBadge>}
                  />
                );
              })}
            </ZeilenListe>
          </>
        )}
        {demnaechst.length > 0 && (
          <>
            <AbschnittLabel abstandOben={dringend.length > 0}>Demnächst</AbschnittLabel>
            <ZeilenListe>
              {demnaechst.map((e) => (
                <Zeile
                  key={e.az + e.frist_datum}
                  onClick={() => onOpenAkte(e.az)}
                  links={
                    <ZeileText
                      titel={<><b className="tabular-nums">{e.az}</b> · {e.kurzbezeichnung || e.mandant}</>}
                      meta={e.frist_art}
                    />
                  }
                  rechts={<span className="tabular-nums" style={{ fontSize: T.textXs, color: T.textMuted, whiteSpace: "nowrap" }}>{fmtDatumDe(e.frist_datum)}</span>}
                />
              ))}
            </ZeilenListe>
          </>
        )}
      </KachelInhalt>
    </Kachel>
  );
}
```

- [ ] **Step 4: Test laufen lassen — muss grün sein**

Run: `cd frontend && npx vitest run src/views/action_board/FristenKachel.test.jsx`
Expected: PASS (5 Tests). Falls `fmtDatumDe` ein anderes Format liefert als erwartet: Test-Assertions nutzen kein Datum — nur Implementierung prüfen.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/action_board/FristenKachel.jsx frontend/src/views/action_board/FristenKachel.test.jsx
git commit -m "feat(dashboard): FristenKachel hell, Zustaende, Tastatur, eine Farbachse

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: WiedervorlagenKachel-Umbau

**Files:**
- Modify: `frontend/src/views/action_board/WiedervorlagenKachel.jsx` (kompletter Ersatz)
- Test: `frontend/src/views/action_board/WiedervorlagenKachel.test.jsx`

**Interfaces:**
- Consumes: boardUi (Task 2), `Ic.refresh`.
- Produces: `WiedervorlagenKachel({ status, wv, ohne_wv, onOpenAkte, onRetry, onAlleOeffnen })` — von Task 7 verwendet. `onAlleOeffnen` öffnet die Wiedervorlage-Vollansicht.

- [ ] **Step 1: Failing Test schreiben**

`frontend/src/views/action_board/WiedervorlagenKachel.test.jsx`:

```jsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import WiedervorlagenKachel from "./WiedervorlagenKachel";

const WV = [
  { az: "145/26 AS", datum: "2026-07-28", tage_bis: -2, grund: "Zahlungseingang prüfen", kurzbezeichnung: "Schneider ./. DEVK" },
  { az: "287/26 AH", datum: "2026-07-30", tage_bis: 0, grund: "SV-Gutachten nachfassen", kurzbezeichnung: "Becker ./. Gothaer" },
];
const OHNE = Array.from({ length: 8 }, (_, i) => ({ az: `90${i}/26 AS`, kurzbezeichnung: `Akte ${i}` }));

describe("WiedervorlagenKachel", () => {
  it("zeigt Überfällig- und Heute-Abschnitte mit Badges", () => {
    render(<WiedervorlagenKachel status="ok" wv={WV} ohne_wv={[]} onOpenAkte={() => {}} onRetry={() => {}} onAlleOeffnen={() => {}} />);
    expect(screen.getByText("Überfällig")).toBeInTheDocument();
    expect(screen.getByText("Heute fällig")).toBeInTheDocument();
    expect(screen.getByText("−2 T")).toBeInTheDocument();
  });

  it("deckelt die Liste ohne WV auf 5 und bietet den Sprung in die Vollansicht", () => {
    const alle = vi.fn();
    render(<WiedervorlagenKachel status="ok" wv={[]} ohne_wv={OHNE} onOpenAkte={() => {}} onRetry={() => {}} onAlleOeffnen={alle} />);
    expect(screen.getByText("Keine Wiedervorlage gesetzt")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /\/26 AS/ })).toHaveLength(5);
    const mehr = screen.getByRole("button", { name: /\+ 3 weitere/ });
    fireEvent.click(mehr);
    expect(alle).toHaveBeenCalledTimes(1);
  });

  it("Fehlerzustand ersetzt den Leertext", () => {
    render(<WiedervorlagenKachel status="fehler" wv={[]} ohne_wv={[]} onOpenAkte={() => {}} onRetry={() => {}} onAlleOeffnen={() => {}} />);
    expect(screen.getByText("Wiedervorlagen konnten nicht geladen werden")).toBeInTheDocument();
    expect(screen.queryByText("Alle Wiedervorlagen erledigt")).toBeNull();
  });

  it("Leerzustand nur bei ok", () => {
    render(<WiedervorlagenKachel status="ok" wv={[]} ohne_wv={[]} onOpenAkte={() => {}} onRetry={() => {}} onAlleOeffnen={() => {}} />);
    expect(screen.getByText("Alle Wiedervorlagen erledigt")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `cd frontend && npx vitest run src/views/action_board/WiedervorlagenKachel.test.jsx`
Expected: FAIL

- [ ] **Step 3: `WiedervorlagenKachel.jsx` komplett ersetzen**

```jsx
import React from "react";
import { T } from "../../config/theme";
import Ic from "../../config/icons";
import { Kachel, KachelInhalt, Zeile, ZeileText, StufenBadge, AbschnittLabel, MehrKnopf, ZeilenListe } from "./boardUi";

const OHNE_WV_LIMIT = 5;

export default function WiedervorlagenKachel({ status, wv, ohne_wv, onOpenAkte, onRetry, onAlleOeffnen }) {
  const ueberfaellig = (wv || []).filter((e) => e.tage_bis < 0);
  const heute        = (wv || []).filter((e) => e.tage_bis === 0);
  const alleOhneWv   = ohne_wv || [];
  const ohneWvSicht  = alleOhneWv.slice(0, OHNE_WV_LIMIT);
  const ohneWvRest   = alleOhneWv.length - ohneWvSicht.length;
  const hatInhalt    = ueberfaellig.length > 0 || heute.length > 0 || alleOhneWv.length > 0;

  const zusammenfassung = status === "ok" && hatInhalt ? (
    <>
      {ueberfaellig.length > 0 && <b style={{ color: T.redText, fontWeight: 600 }}>{ueberfaellig.length} überfällig · </b>}
      {heute.length} heute
    </>
  ) : null;

  function wvZeile(e) {
    const stufe = e.tage_bis < 0 ? "rot" : "gelb";
    return (
      <Zeile
        key={e.az + e.datum}
        stufe={stufe}
        onClick={() => onOpenAkte(e.az)}
        links={
          <ZeileText
            titel={<><b className="tabular-nums">{e.az}</b> · {e.kurzbezeichnung || e.mandant || e.az}</>}
            meta={e.grund || "Wiedervorlage"}
            metaFarbe={stufe === "rot" ? T.redText : T.amberText}
          />
        }
        rechts={<StufenBadge stufe={stufe}>{e.tage_bis < 0 ? `−${Math.abs(e.tage_bis)} T` : "heute"}</StufenBadge>}
      />
    );
  }

  return (
    <Kachel icon={Ic.refresh} titel="Wiedervorlagen" zusammenfassung={zusammenfassung}>
      <KachelInhalt
        status={status}
        fehlerText="Wiedervorlagen konnten nicht geladen werden"
        onRetry={onRetry}
        leer={!hatInhalt}
        leerText="Alle Wiedervorlagen erledigt"
      >
        {ueberfaellig.length > 0 && (
          <>
            <AbschnittLabel>Überfällig</AbschnittLabel>
            <ZeilenListe>{ueberfaellig.map(wvZeile)}</ZeilenListe>
          </>
        )}
        {heute.length > 0 && (
          <>
            <AbschnittLabel abstandOben={ueberfaellig.length > 0}>Heute fällig</AbschnittLabel>
            <ZeilenListe>{heute.map(wvZeile)}</ZeilenListe>
          </>
        )}
        {alleOhneWv.length > 0 && (
          <>
            <AbschnittLabel abstandOben={ueberfaellig.length > 0 || heute.length > 0}>Keine Wiedervorlage gesetzt</AbschnittLabel>
            <ZeilenListe>
              {ohneWvSicht.map((e) => (
                <Zeile
                  key={e.az}
                  onClick={() => onOpenAkte(e.az)}
                  links={<ZeileText titel={<><b className="tabular-nums">{e.az}</b> · {e.kurzbezeichnung || e.mandant || ""}</>} meta="keine WV gesetzt" />}
                />
              ))}
            </ZeilenListe>
          </>
        )}
        {(ohneWvRest > 0 || hatInhalt) && (
          <MehrKnopf onClick={onAlleOeffnen}>
            {ohneWvRest > 0 ? `+ ${ohneWvRest} weitere · Alle Wiedervorlagen öffnen` : "Alle Wiedervorlagen öffnen"}
          </MehrKnopf>
        )}
      </KachelInhalt>
    </Kachel>
  );
}
```

- [ ] **Step 4: Test laufen lassen — muss grün sein**

Run: `cd frontend && npx vitest run src/views/action_board/WiedervorlagenKachel.test.jsx`
Expected: PASS (4 Tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/action_board/WiedervorlagenKachel.jsx frontend/src/views/action_board/WiedervorlagenKachel.test.jsx
git commit -m "feat(dashboard): WiedervorlagenKachel hell, Deckelung ohne-WV, Sprung Vollansicht

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: TermineKachel-Umbau

**Files:**
- Modify: `frontend/src/views/action_board/TermineKachel.jsx` (kompletter Ersatz)
- Test: `frontend/src/views/action_board/TermineKachel.test.jsx`

**Interfaces:**
- Consumes: boardUi (Task 2), `Ic.clock`.
- Produces: `TermineKachel({ status, eintraege, onOpenAkte, onRetry })` — von Task 7 verwendet.

- [ ] **Step 1: Failing Test schreiben**

`frontend/src/views/action_board/TermineKachel.test.jsx`:

```jsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import TermineKachel from "./TermineKachel";

const EINTRAEGE = [
  { az: "264/26 AS", termin_art: "Gerichtstermin", termin_datum: "2026-07-30", uhrzeit: "09:30", tage_bis: 0, kurzbezeichnung: "Klein ./. Provinzial" },
  { az: "198/26 CO", termin_art: "Gerichtstermin", termin_datum: "2026-07-31", uhrzeit: "10:00", tage_bis: 1, kurzbezeichnung: "Krause ./. VHV" },
];

describe("TermineKachel", () => {
  it("gruppiert nach Heute und Morgen mit Uhrzeit", () => {
    render(<TermineKachel status="ok" eintraege={EINTRAEGE} onOpenAkte={() => {}} onRetry={() => {}} />);
    expect(screen.getByText("Heute")).toBeInTheDocument();
    expect(screen.getByText("Morgen")).toBeInTheDocument();
    expect(screen.getByText("09:30")).toBeInTheDocument();
  });

  it("Eintrag ist Button und öffnet Akte", () => {
    const oeffne = vi.fn();
    render(<TermineKachel status="ok" eintraege={EINTRAEGE} onOpenAkte={oeffne} onRetry={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /264\/26 AS/ }));
    expect(oeffne).toHaveBeenCalledWith("264/26 AS");
  });

  it("Fehler- und Leerzustand sind getrennt", () => {
    const { rerender } = render(<TermineKachel status="fehler" eintraege={[]} onOpenAkte={() => {}} onRetry={() => {}} />);
    expect(screen.getByText("Termine konnten nicht geladen werden")).toBeInTheDocument();
    rerender(<TermineKachel status="ok" eintraege={[]} onOpenAkte={() => {}} onRetry={() => {}} />);
    expect(screen.getByText("Heute keine Termine")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `cd frontend && npx vitest run src/views/action_board/TermineKachel.test.jsx`
Expected: FAIL

- [ ] **Step 3: `TermineKachel.jsx` komplett ersetzen**

```jsx
import React from "react";
import { T } from "../../config/theme";
import Ic from "../../config/icons";
import { Kachel, KachelInhalt, Zeile, ZeileText, AbschnittLabel, ZeilenListe } from "./boardUi";

export default function TermineKachel({ status, eintraege, onOpenAkte, onRetry }) {
  const heute  = eintraege.filter((e) => e.tage_bis === 0);
  const morgen = eintraege.filter((e) => e.tage_bis === 1);

  const zusammenfassung = status === "ok" && eintraege.length > 0
    ? `${heute.length} heute · ${morgen.length} morgen`
    : null;

  function terminZeile(e) {
    return (
      <Zeile
        key={e.az + e.termin_datum + (e.uhrzeit || "")}
        onClick={() => onOpenAkte(e.az)}
        links={
          <ZeileText
            titel={<>{e.termin_art || "Termin"} — {e.kurzbezeichnung || e.mandant}</>}
            meta={<><b className="tabular-nums">{e.az}</b></>}
          />
        }
        rechts={<span className="tabular-nums" style={{ fontSize: T.textSm, fontWeight: 600, color: T.textMid, whiteSpace: "nowrap" }}>{e.uhrzeit || ""}</span>}
      />
    );
  }

  return (
    <Kachel icon={Ic.clock} titel="Termine" zusammenfassung={zusammenfassung}>
      <KachelInhalt
        status={status}
        fehlerText="Termine konnten nicht geladen werden"
        onRetry={onRetry}
        leer={eintraege.length === 0}
        leerText="Heute keine Termine"
      >
        {heute.length > 0 && (
          <>
            <AbschnittLabel>Heute</AbschnittLabel>
            <ZeilenListe>{heute.map(terminZeile)}</ZeilenListe>
          </>
        )}
        {morgen.length > 0 && (
          <>
            <AbschnittLabel abstandOben={heute.length > 0}>Morgen</AbschnittLabel>
            <ZeilenListe>{morgen.map(terminZeile)}</ZeilenListe>
          </>
        )}
      </KachelInhalt>
    </Kachel>
  );
}
```

- [ ] **Step 4: Test laufen lassen — muss grün sein**

Run: `cd frontend && npx vitest run src/views/action_board/TermineKachel.test.jsx`
Expected: PASS (3 Tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/action_board/TermineKachel.jsx frontend/src/views/action_board/TermineKachel.test.jsx
git commit -m "feat(dashboard): TermineKachel hell + Zustaende

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: JetztDranLeiste (neu)

**Files:**
- Create: `frontend/src/views/action_board/JetztDranLeiste.jsx`
- Test: `frontend/src/views/action_board/JetztDranLeiste.test.jsx`

**Interfaces:**
- Consumes: boardUi (Task 2).
- Produces (von Task 7 verwendet):
  - default `JetztDranLeiste({ fristenStatus, wvStatus, fristen, wv, onOpenAkte })` — rendert `null`, solange nicht beide Status `"ok"` sind.
  - named `jetztDranEintraege(fristen, wv)` → Array (max. 3) `{ az, tage, prio, titel, art }`, sortiert: am stärksten überfällig zuerst, bei Gleichstand Fristen vor WV.

- [ ] **Step 1: Failing Test schreiben**

`frontend/src/views/action_board/JetztDranLeiste.test.jsx`:

```jsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import JetztDranLeiste, { jetztDranEintraege } from "./JetztDranLeiste";

const FRISTEN = [
  { az: "312/26 AS", frist_art: "Stellungnahme", frist_datum: "2026-07-27", tage_bis: -3, kurzbezeichnung: "Müller ./. HUK" },
  { az: "218/26 PK", frist_art: "Klageerwiderung", frist_datum: "2026-07-30", tage_bis: 0, kurzbezeichnung: "Weber ./. Allianz" },
  { az: "402/26 AS", frist_art: "Nachbesserung", frist_datum: "2026-08-01", tage_bis: 2, kurzbezeichnung: "Öztürk ./. R+V" },
];
const WV = [
  { az: "145/26 AS", datum: "2026-07-28", tage_bis: -2, grund: "Zahlungseingang prüfen", kurzbezeichnung: "Schneider ./. DEVK" },
  { az: "287/26 AH", datum: "2026-07-30", tage_bis: 0, grund: "nachfassen", kurzbezeichnung: "Becker ./. Gothaer" },
];

describe("jetztDranEintraege", () => {
  it("nimmt nur Fälliges (<= 0), sortiert überfälligste zuerst, Frist vor WV, max 3", () => {
    const erg = jetztDranEintraege(FRISTEN, WV);
    expect(erg).toHaveLength(3);
    expect(erg[0].az).toBe("312/26 AS");
    expect(erg[1].az).toBe("145/26 AS");
    expect(erg[2].az).toBe("218/26 PK");
  });

  it("Frist gewinnt bei Gleichstand", () => {
    const erg = jetztDranEintraege(
      [{ az: "F", frist_art: "x", frist_datum: "d", tage_bis: 0, kurzbezeichnung: "f" }],
      [{ az: "W", datum: "d", tage_bis: 0, grund: "y", kurzbezeichnung: "w" }]
    );
    expect(erg.map((e) => e.az)).toEqual(["F", "W"]);
  });
});

describe("JetztDranLeiste", () => {
  it("rendert nichts, solange eine Quelle nicht ok ist", () => {
    const { container } = render(
      <JetztDranLeiste fristenStatus="laedt" wvStatus="ok" fristen={[]} wv={[]} onOpenAkte={() => {}} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("zeigt die dringendsten Vorgänge als klickbare Buttons", () => {
    const oeffne = vi.fn();
    render(<JetztDranLeiste fristenStatus="ok" wvStatus="ok" fristen={FRISTEN} wv={WV} onOpenAkte={oeffne} />);
    expect(screen.getByText("Jetzt dran")).toBeInTheDocument();
    expect(screen.getByText("3 Tage überfällig")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /312\/26 AS/ }));
    expect(oeffne).toHaveBeenCalledWith("312/26 AS");
  });

  it("zeigt bei leerer Lage die ruhige Entwarnung", () => {
    render(<JetztDranLeiste fristenStatus="ok" wvStatus="ok" fristen={[]} wv={[]} onOpenAkte={() => {}} />);
    expect(screen.getByText("Keine überfälligen Vorgänge")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `cd frontend && npx vitest run src/views/action_board/JetztDranLeiste.test.jsx`
Expected: FAIL — Modul existiert nicht

- [ ] **Step 3: `JetztDranLeiste.jsx` implementieren**

```jsx
import React from "react";
import { T } from "../../config/theme";
import { Kachel, KachelInhalt, Zeile, ZeileText, StufenBadge, ZeilenListe } from "./boardUi";

export function jetztDranEintraege(fristen, wv) {
  const f = (fristen || []).filter((e) => e.tage_bis <= 0).map((e) => ({
    az: e.az, tage: e.tage_bis, prio: 0,
    titel: e.kurzbezeichnung || e.mandant || e.az,
    art: e.frist_art,
  }));
  const w = (wv || []).filter((e) => e.tage_bis <= 0).map((e) => ({
    az: e.az, tage: e.tage_bis, prio: 1,
    titel: e.kurzbezeichnung || e.mandant || e.az,
    art: e.grund ? `Wiedervorlage: ${e.grund}` : "Wiedervorlage",
  }));
  return [...f, ...w].sort((a, b) => (a.tage - b.tage) || (a.prio - b.prio)).slice(0, 3);
}

function badgeText(tage) {
  if (tage === 0) return "heute fällig";
  const t = Math.abs(tage);
  return t === 1 ? "1 Tag überfällig" : `${t} Tage überfällig`;
}

export default function JetztDranLeiste({ fristenStatus, wvStatus, fristen, wv, onOpenAkte }) {
  if (fristenStatus !== "ok" || wvStatus !== "ok") return null;
  const eintraege = jetztDranEintraege(fristen, wv);

  const punkt = <span style={{ width: 8, height: 8, borderRadius: "50%", background: T.accent, display: "inline-block" }} />;
  const zusammenfassung = eintraege.length > 0
    ? (eintraege.length === 1 ? "1 Vorgang braucht Sie zuerst" : `${eintraege.length} Vorgänge brauchen Sie zuerst`)
    : null;

  return (
    <Kachel icon={punkt} titel="Jetzt dran" zusammenfassung={zusammenfassung}>
      <KachelInhalt status="ok" leer={eintraege.length === 0} leerText="Keine überfälligen Vorgänge">
        <ZeilenListe>
          {eintraege.map((e) => {
            const stufe = e.tage < 0 ? "rot" : "gelb";
            return (
              <Zeile
                key={e.prio + e.az + e.tage}
                stufe={stufe}
                onClick={() => onOpenAkte(e.az)}
                links={
                  <ZeileText
                    titel={<><b className="tabular-nums">{e.az}</b> · {e.titel}</>}
                    meta={e.art}
                    metaFarbe={stufe === "rot" ? T.redText : T.amberText}
                  />
                }
                rechts={<StufenBadge stufe={stufe}>{badgeText(e.tage)}</StufenBadge>}
              />
            );
          })}
        </ZeilenListe>
      </KachelInhalt>
    </Kachel>
  );
}
```

- [ ] **Step 4: Test laufen lassen — muss grün sein**

Run: `cd frontend && npx vitest run src/views/action_board/JetztDranLeiste.test.jsx`
Expected: PASS (5 Tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/action_board/JetztDranLeiste.jsx frontend/src/views/action_board/JetztDranLeiste.test.jsx
git commit -m "feat(dashboard): Jetzt-dran-Leiste (3 dringendste aus Fristen + WV)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: ActionBoardView-Umbau + App-Verdrahtung

**Files:**
- Modify: `frontend/src/views/ActionBoardView.jsx` (kompletter Ersatz)
- Modify: `frontend/src/App.jsx:293` (Props der ActionBoardView)
- Test: `frontend/src/views/ActionBoardView.test.jsx`

**Interfaces:**
- Consumes: Kacheln aus Tasks 3–6 (Props exakt wie dort definiert), `apiDashboard` (`termineHeute`, `fristen`, `wiedervorlagen` — `nachrichtenNeu` wird NICHT mehr aufgerufen).
- Produces: `ActionBoardView({ onOpenAkte, onOpenWiedervorlage })`. `onOpenEmail` entfällt. App.jsx liefert `onOpenWiedervorlage={() => setActive("wiedervorlage")}` (Nav-id `"wiedervorlage"`, siehe App.jsx:181).

- [ ] **Step 1: Failing Test schreiben**

`frontend/src/views/ActionBoardView.test.jsx`:

```jsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const api = vi.hoisted(() => ({
  termineHeute:   vi.fn(),
  fristen:        vi.fn(),
  wiedervorlagen: vi.fn(),
  nachrichtenNeu: vi.fn(),
}));
vi.mock("../api", () => ({ apiDashboard: api }));

import ActionBoardView from "./ActionBoardView.jsx";

const FRIST = { az: "312/26 AS", frist_art: "Stellungnahme", frist_datum: "2026-07-27", tage_bis: -3, kurzbezeichnung: "Müller ./. HUK" };

function mockOk({ fristen = [], termine = [], wv = [], ohne_wv = [] } = {}) {
  api.termineHeute.mockResolvedValue({ eintraege: termine });
  api.fristen.mockResolvedValue({ eintraege: fristen });
  api.wiedervorlagen.mockResolvedValue({ wv, ohne_wv });
}

describe("ActionBoardView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("zeigt beim Laden keinen Leertext (kein falsches 'alles erledigt')", () => {
    api.termineHeute.mockReturnValue(new Promise(() => {}));
    api.fristen.mockReturnValue(new Promise(() => {}));
    api.wiedervorlagen.mockReturnValue(new Promise(() => {}));
    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    expect(screen.queryByText(/Keine Fristen/)).toBeNull();
    expect(screen.queryByText(/Heute keine Termine/)).toBeNull();
  });

  it("zeigt bei Fristen-Fehler den Fehlerblock und lädt per Retry neu", async () => {
    mockOk();
    api.fristen.mockRejectedValue(new Error("kaputt"));
    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    await screen.findByText("Fristen konnten nicht geladen werden");
    expect(screen.queryByText(/Keine Fristen in den nächsten/)).toBeNull();
    api.fristen.mockResolvedValue({ eintraege: [] });
    fireEvent.click(screen.getByRole("button", { name: "Erneut laden" }));
    await screen.findByText("Keine Fristen in den nächsten 14 Tagen");
    expect(api.fristen).toHaveBeenCalledTimes(2);
  });

  it("ruft nachrichtenNeu nicht mehr auf und zeigt keinen Posteingang", async () => {
    mockOk();
    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    await screen.findByText("Keine Fristen in den nächsten 14 Tagen");
    expect(api.nachrichtenNeu).not.toHaveBeenCalled();
    expect(screen.queryByText(/Posteingang/i)).toBeNull();
  });

  it("öffnet Akten aus der Jetzt-dran-Leiste mit normalisiertem AZ", async () => {
    mockOk({ fristen: [FRIST] });
    const oeffne = vi.fn();
    render(<ActionBoardView onOpenAkte={oeffne} onOpenWiedervorlage={() => {}} />);
    await screen.findByText("Jetzt dran");
    fireEvent.click(screen.getAllByRole("button", { name: /312\/26 AS/ })[0]);
    expect(oeffne).toHaveBeenCalledWith({ az: "312/26", az_roh: "312/26 AS" });
  });

  it("persistiert den SB-Filter in localStorage und stellt ihn wieder her", async () => {
    mockOk();
    const { unmount } = render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    await screen.findByText("Keine Fristen in den nächsten 14 Tagen");
    fireEvent.click(screen.getByRole("button", { name: "TB" }));
    expect(JSON.parse(localStorage.getItem("dashboard.aktiveSB"))).toContain("TB");
    unmount();
    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    await waitFor(() => expect(api.fristen).toHaveBeenCalledTimes(2));
    expect(JSON.parse(localStorage.getItem("dashboard.aktiveSB"))).toContain("TB");
  });

  it("zeigt bei komplett abgewähltem SB-Filter einen Hinweis statt leerer Kacheln", async () => {
    mockOk();
    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    await screen.findByText("Keine Fristen in den nächsten 14 Tagen");
    for (const sb of ["AS", "PK", "CO", "MM", "AH"]) {
      fireEvent.click(screen.getByRole("button", { name: sb }));
    }
    expect(screen.getByText("Kein Sachbearbeiter ausgewählt")).toBeInTheDocument();
    expect(screen.queryByText(/Keine Fristen in den nächsten/)).toBeNull();
  });
});
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `cd frontend && npx vitest run src/views/ActionBoardView.test.jsx`
Expected: FAIL

- [ ] **Step 3: `ActionBoardView.jsx` komplett ersetzen**

```jsx
import React, { useCallback, useEffect, useState } from "react";
import { apiDashboard } from "../api";
import { T } from "../config/theme";
import TermineKachel        from "./action_board/TermineKachel";
import FristenKachel        from "./action_board/FristenKachel";
import WiedervorlagenKachel from "./action_board/WiedervorlagenKachel";
import JetztDranLeiste      from "./action_board/JetztDranLeiste";

function baseAz(azVoll) {
  return (azVoll || "").replace(/[A-Z]{2,3}$/i, "").trim();
}

const ALLE_SB    = ["AS", "PK", "CO", "MM", "AH", "TB", "SK", "EI"];
const DEFAULT_SB = ["AS", "PK", "CO", "MM", "AH"];
const SB_KEY     = "dashboard.aktiveSB";

function sbAusAz(az) {
  const m = (az || "").match(/([A-Z]{2,3})$/);
  return m ? m[1] : null;
}

function gespeicherteSB() {
  try {
    const arr = JSON.parse(localStorage.getItem(SB_KEY));
    if (Array.isArray(arr)) return new Set(arr.filter((sb) => ALLE_SB.includes(sb)));
  } catch { /* defekter Eintrag → Default */ }
  return new Set(DEFAULT_SB);
}

const START = {
  termine: { status: "laedt", eintraege: [] },
  fristen: { status: "laedt", eintraege: [] },
  wv:      { status: "laedt", wv: [], ohne_wv: [] },
};

export default function ActionBoardView({ onOpenAkte, onOpenWiedervorlage }) {
  const [daten,       setDaten]       = useState(START);
  const [ladeZeit,    setLadeZeit]    = useState(null);
  const [laedtGerade, setLaedtGerade] = useState(false);
  const [aktiveSB,    setAktiveSB]    = useState(gespeicherteSB);

  function toggleSB(sb) {
    setAktiveSB((prev) => {
      const next = new Set(prev);
      next.has(sb) ? next.delete(sb) : next.add(sb);
      localStorage.setItem(SB_KEY, JSON.stringify([...next]));
      return next;
    });
  }

  async function laden() {
    setLaedtGerade(true);
    const [r1, r2, r3] = await Promise.allSettled([
      apiDashboard.termineHeute(),
      apiDashboard.fristen(),
      apiDashboard.wiedervorlagen(),
    ]);
    setDaten((prev) => ({
      termine: r1.status === "fulfilled" ? { status: "ok", eintraege: r1.value?.eintraege ?? [] } : { ...prev.termine, status: "fehler" },
      fristen: r2.status === "fulfilled" ? { status: "ok", eintraege: r2.value?.eintraege ?? [] } : { ...prev.fristen, status: "fehler" },
      wv:      r3.status === "fulfilled" ? { status: "ok", wv: r3.value?.wv ?? [], ohne_wv: r3.value?.ohne_wv ?? [] } : { ...prev.wv, status: "fehler" },
    }));
    setLadeZeit(new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }));
    setLaedtGerade(false);
  }

  useEffect(() => { laden(); }, []);

  const oeffneAkte = useCallback((az) => {
    onOpenAkte({ az: baseAz(az), az_roh: az });
  }, [onOpenAkte]);

  const heute = new Date().toLocaleDateString("de-DE", {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  });

  const sbFilter = (e) => aktiveSB.has(sbAusAz(e.az));
  const sbFilterOhne = (e) => { const sb = sbAusAz(e.az); return !sb || aktiveSB.has(sb); };
  const fristen = daten.fristen.eintraege.filter(sbFilter);
  const termine = daten.termine.eintraege.filter(sbFilter);
  const wv      = daten.wv.wv.filter(sbFilter);
  const ohneWv  = daten.wv.ohne_wv.filter(sbFilterOhne);

  return (
    <div style={{ flex: 1, overflow: "auto", background: T.offWhite, padding: "20px 24px 26px" }}>
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 16, flexWrap: "wrap", marginBottom: 16 }}>
        <div>
          <div style={{ fontFamily: T.fontDisplay, fontSize: T.textXl, fontWeight: 700, color: T.text, lineHeight: 1.2 }}>Tagesübersicht</div>
          <div style={{ fontSize: T.textSm, color: T.textMuted, marginTop: 2 }}>{heute}</div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <span style={{ fontSize: "0.6875rem", fontWeight: 600, letterSpacing: "0.05em", color: T.textMuted, marginRight: 3 }}>SB</span>
            {ALLE_SB.map((sb) => {
              const aktiv = aktiveSB.has(sb);
              return (
                <button
                  key={sb}
                  onClick={() => toggleSB(sb)}
                  style={{
                    fontSize: "0.6875rem", fontWeight: 600, padding: "3px 9px", borderRadius: 999, cursor: "pointer",
                    background: aktiv ? T.navy : "transparent",
                    color: aktiv ? "#FFFFFF" : T.textMuted,
                    border: `1px solid ${aktiv ? T.navy : T.borderSoft || T.border}`,
                  }}
                >
                  {sb}
                </button>
              );
            })}
          </div>
          <button
            onClick={laden}
            disabled={laedtGerade}
            style={{ display: "flex", alignItems: "center", gap: 6, fontSize: T.textXs, color: T.textMuted, padding: "5px 10px", border: `1px solid ${T.border}`, borderRadius: 7, background: T.cardBg, cursor: "pointer", opacity: laedtGerade ? 0.5 : 1 }}
          >
            {laedtGerade ? "Lädt …" : "Aktualisieren"}
            {ladeZeit && !laedtGerade && <span className="tabular-nums">· Stand {ladeZeit}</span>}
          </button>
        </div>
      </div>

      {aktiveSB.size === 0 ? (
        <div style={{ background: T.cardBg, border: `1px solid ${T.border}`, borderRadius: 10, padding: "22px 16px", textAlign: "center", color: T.textMuted, fontSize: T.textSm }}>
          Kein Sachbearbeiter ausgewählt
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <JetztDranLeiste
            fristenStatus={daten.fristen.status}
            wvStatus={daten.wv.status}
            fristen={fristen}
            wv={wv}
            onOpenAkte={oeffneAkte}
          />
          <div style={{ display: "grid", gridTemplateColumns: "minmax(0,3fr) minmax(0,2fr)", gap: 16, alignItems: "start" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 16, minWidth: 0 }}>
              <FristenKachel status={daten.fristen.status} eintraege={fristen} onOpenAkte={oeffneAkte} onRetry={laden} />
              <WiedervorlagenKachel status={daten.wv.status} wv={wv} ohne_wv={ohneWv} onOpenAkte={oeffneAkte} onRetry={laden} onAlleOeffnen={onOpenWiedervorlage} />
            </div>
            <TermineKachel status={daten.termine.status} eintraege={termine} onOpenAkte={oeffneAkte} onRetry={laden} />
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: App.jsx-Aufruf anpassen** (Zeile ~293)

Alt:
```jsx
{active==="dashboard"        ? <ActionBoardView onOpenAkte={openAkte} onOpenEmail={openEmail} />
```
Neu:
```jsx
{active==="dashboard"        ? <ActionBoardView onOpenAkte={openAkte} onOpenWiedervorlage={() => setActive("wiedervorlage")} />
```
Prüfen: Wird `openEmail` sonst noch verwendet (EmailImportView-Kette)? Nur die ActionBoardView-Übergabe entfernen, `openEmail` selbst bleibt.

- [ ] **Step 5: Test laufen lassen — muss grün sein**

Run: `cd frontend && npx vitest run src/views/ActionBoardView.test.jsx`
Expected: PASS (6 Tests)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/ActionBoardView.jsx frontend/src/views/ActionBoardView.test.jsx frontend/src/App.jsx
git commit -m "feat(dashboard): Tagesuebersicht hell — Layout 3:2, Jetzt dran, Zustaende, SB-Persistenz, Posteingang raus

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: Aufräumen + Vollsuite

**Files:**
- Delete: `frontend/src/views/action_board/PosteingangKachel.jsx`
- Delete: `frontend/src/views/action_board/tagesBadge.js` (toter Code, nie importiert)

**Interfaces:**
- Consumes: nichts. Produces: sauberer Branch, grüne Vollsuite.

- [ ] **Step 1: Verwaiste Importe prüfen**

Run: `cd frontend && grep -rn "PosteingangKachel\|tagesBadge" src/`
Expected: keine Treffer außer den zu löschenden Dateien selbst.

- [ ] **Step 2: Dateien löschen**

```bash
git rm frontend/src/views/action_board/PosteingangKachel.jsx frontend/src/views/action_board/tagesBadge.js
```

- [ ] **Step 3: Frontend-Vollsuite**

Run: `cd frontend && npx vitest run`
Expected: alle Tests grün (Bestand 406 + neue Dashboard-Tests). Bei Fehlschlägen, die nachweislich auf `main`/`aktenanlage` schon rot waren: dokumentieren, nicht in diesem Branch fixen.

- [ ] **Step 4: Lint**

Run: `cd frontend && npm run lint`
Expected: keine neuen Fehler in den angefassten Dateien.

- [ ] **Step 5: Commit**

```bash
git commit -m "chore(dashboard): PosteingangKachel + tagesBadge entfernt

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: Doku + Browser-Verifikation

**Files:**
- Modify: `docs/TODO.md` (In-Arbeit-Eintrag Dashboard-Hell + Erledigt-Zeile)
- Modify: `docs/CHANGELOG.md` (Protokoll-Eintrag mit Commits)

**Interfaces:** keine.

- [ ] **Step 1: Frontend-Container neu starten (HMR-Windows-Bug)**

```bash
docker restart unfallakten-frontend-dev
```

- [ ] **Step 2: TODO.md ergänzen**

Unter „🔄 In Arbeit" neuen Block einfügen (vor „Kürzungstaxonomie"):

```markdown
### Dashboard-Hell-Umbau — umgesetzt (Branch `dashboard-hell`, basiert auf `aktenanlage`), Browser-Abnahme RA Schatz offen
Tagesübersicht hell (Pergament-Tokens), Jetzt-dran-Leiste, Fristen links oben (3:2),
Posteingang-Kachel entfernt, Lade/Fehler/Leer-Zustände je Kachel, Einträge als Buttons
(Tastatur), SB-Filter persistiert (`dashboard.aktiveSB`), leere SB-Auswahl = Hinweis.
Spec + Mockup: `docs/superpowers/specs/2026-07-30-dashboard-hell-*`.
**Merge-Reihenfolge: erst `aktenanlage` → `main`, dann dieser Branch.**
Offen danach (separat): Sidebar-Emoji-Icons App.jsx, SB-Klarnamen-Tooltips (Kürzel-Liste von RA Schatz nötig).
```

- [ ] **Step 3: CHANGELOG.md-Eintrag** (Muster der bestehenden Einträge folgen: Datum, Feature, Commits, Tests, Besonderheiten — u. a. Review-Ergebnis 14/40, P0 stille Fehler/Farben, Detektor 4× borderLeft).

- [ ] **Step 4: Commit**

```bash
git add docs/TODO.md docs/CHANGELOG.md
git commit -m "docs(dashboard): TODO + CHANGELOG Dashboard-Hell-Umbau

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

- [ ] **Step 5: Browser-Abnahme durch RA Schatz** — App öffnen (Dashboard-Tab), prüfen gegen Mockup: hell, Jetzt dran, 3:2, kein Posteingang, Tab-Taste erreicht Einträge, SB-Auswahl übersteht Ansichtswechsel. Danach ggf. Feinschliff-Runde.
