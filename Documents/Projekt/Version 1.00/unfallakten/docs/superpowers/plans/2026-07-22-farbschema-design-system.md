# Farbschema-Design-System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eine einzige Quelle der Wahrheit für Design-Tokens (Farbe + Schrift) schaffen und darauf ein Farbschema-/Dark-Mode-System aufbauen: „Kanzlei Classic" (bestehend) und „Clio-Style" (neu), mit Dark Mode zunächst nur für Clio-Style, umschaltbar in Einstellungen → System-Status, persistent pro Sachbearbeiter:in im Browser.

**Architecture:** CSS Custom Properties in `tokens.css`, verschachtelt nach `[data-scheme]`×`[data-theme]`-Attributen auf `<html>`. `theme.js` (`T`-Objekt) wird von Hex-Werten zu `var(--...)`-Referenzen umgestellt — die 41+ Aufrufstellen (`T.navy` etc.) ändern sich dadurch nicht. Umschalten = zwei DOM-Attribute setzen + localStorage schreiben, kein React-Re-Render nötig.

**Tech Stack:** React 18 (Vite), CSS Custom Properties, Vitest (jsdom) für Tests, kein neues Package nötig.

## Global Constraints

- RA-MICRO bleibt unangetastet (betrifft dieses Feature ohnehin nicht, reines Frontend-Theming).
- Keine unnötigen Abstraktionen: kein React-Context/Provider, keine neuen Dependencies.
- Keine Kommentare im Code außer bei nicht-offensichtlichem Verhalten.
- Radius-/Schatten-/Spacing-Tokens des Clio-Sets werden NICHT übernommen (v1-Scope, siehe Spec).
- Dark-Variante existiert v1 nur für Clio-Style, nicht für Kanzlei Classic.
- Bestehende Nutzer:innen ohne gespeicherte Präferenz sehen exakt das heutige Aussehen (Default: `classic`/`light`).

---

## Task 1: `tokens.css` anlegen, einbinden, Inter-Font laden

**Files:**
- Create: `frontend/src/tokens.css`
- Modify: `frontend/src/main.jsx`
- Modify: `frontend/index.html`

**Interfaces:**
- Produces: CSS Custom Properties, konsumiert von Task 2 (`globals.css`) und Task 3 (`theme.js`). Vollständige Liste der Variablennamen siehe unten — diese Namen sind für alle Folgetasks bindend.

- [ ] **Step 1: `tokens.css` mit vollständigem Token-Set für beide Schemata + Clio-Dark schreiben**

```css
/* frontend/src/tokens.css */
:root,
[data-scheme="classic"][data-theme="light"] {
  --color-bg-page: #F6F4EF;
  --color-bg-card: #FFFFFF;
  --color-bg-inset: #FAFAF8;

  --color-brand-surface: #1B2A4A;
  --color-brand-surface-strong: #111d35;
  --color-brand-surface-mid: #243660;
  --color-brand-surface-hover: #2e4270;

  --color-border: #E2DDD3;
  --color-border-strong: #C9C2B4;
  --color-border-soft: rgba(226,221,211,0.6);

  --color-accent: #A06B4A;
  --color-accent-hover: #7D5038;
  --color-accent-subtle: #F3EAE2;
  --color-accent-trim: rgba(160,107,74,0.18);

  --color-text-primary: #1a1a2e;
  --color-text-secondary: #3d4060;
  --color-text-muted: #6b7094;
  --color-text-faint: #9da3be;
  --color-text-on-accent: #FFFFFF;

  --color-status-success: #10b981;
  --color-status-success-bg: #ecfdf5;
  --color-status-success-border: #86efac;
  --color-status-success-fg: #065f46;

  --color-status-warning: #f59e0b;
  --color-status-warning-bg: #fffbeb;
  --color-status-warning-bg-alt: #fef3c7;
  --color-status-warning-fg: #92400e;

  --color-status-danger: #ef4444;
  --color-status-danger-bg: #fef2f2;
  --color-status-danger-border: #fca5a5;
  --color-status-danger-fg: #991b1b;

  --color-status-info: #3b82f6;
  --color-status-info-bg: #eff6ff;
  --color-status-info-fg: #1e40af;

  --font-ui: 'Figtree', system-ui, sans-serif;
  --font-display: 'Bricolage Grotesque', system-ui, sans-serif;
  --font-mono: ui-monospace, 'Cascadia Code', 'Fira Code', monospace;
}

[data-scheme="clio"][data-theme="light"] {
  --color-bg-page: #F5F6F8;
  --color-bg-card: #FFFFFF;
  --color-bg-inset: #EEF0F3;

  --color-brand-surface: #1B4B91;
  --color-brand-surface-strong: #123561;
  --color-brand-surface-mid: #163C74;
  --color-brand-surface-hover: #2E63A8;

  --color-border: #E3E6EA;
  --color-border-strong: #CBD0D8;
  --color-border-soft: rgba(227,230,234,0.6);

  --color-accent: #1B4B91;
  --color-accent-hover: #163C74;
  --color-accent-subtle: #EAF0FA;
  --color-accent-trim: rgba(27,75,145,0.18);

  --color-text-primary: #1A1D21;
  --color-text-secondary: #5B6472;
  --color-text-muted: #8A93A1;
  --color-text-faint: #A9B0BC;
  --color-text-on-accent: #FFFFFF;

  --color-status-success: #1E7A34;
  --color-status-success-bg: #E6F4EA;
  --color-status-success-border: #A8D8B9;
  --color-status-success-fg: #1E7A34;

  --color-status-warning: #9A5B00;
  --color-status-warning-bg: #FFF4E0;
  --color-status-warning-bg-alt: #FCE8C2;
  --color-status-warning-fg: #9A5B00;

  --color-status-danger: #B23A3A;
  --color-status-danger-bg: #FBE7E7;
  --color-status-danger-border: #EFB3B3;
  --color-status-danger-fg: #B23A3A;

  --color-status-info: var(--color-accent);
  --color-status-info-bg: var(--color-accent-subtle);
  --color-status-info-fg: var(--color-accent-hover);

  --font-ui: "Inter", -apple-system, "Segoe UI", Roboto, sans-serif;
  --font-display: "Inter", -apple-system, "Segoe UI", Roboto, sans-serif;
  --font-mono: ui-monospace, "SF Mono", monospace;
}

[data-scheme="clio"][data-theme="dark"] {
  --color-bg-page: #14161A;
  --color-bg-card: #1C1F24;
  --color-bg-inset: #21242A;

  --color-brand-surface: #1B2A45;
  --color-brand-surface-strong: #10192C;
  --color-brand-surface-mid: #223655;
  --color-brand-surface-hover: #2C4570;

  --color-border: #2A2E35;
  --color-border-strong: #3A3F47;
  --color-border-soft: rgba(42,46,53,0.6);

  --color-accent: #4B8AE0;
  --color-accent-hover: #6FA3EA;
  --color-accent-subtle: #1E2A3D;
  --color-accent-trim: rgba(75,138,224,0.22);

  --color-text-primary: #E8EAED;
  --color-text-secondary: #9BA3AF;
  --color-text-muted: #7C8591;
  --color-text-faint: #5B6472;
  --color-text-on-accent: #FFFFFF;

  --color-status-success: #4ADE80;
  --color-status-success-bg: #14261C;
  --color-status-success-border: #2F6B45;
  --color-status-success-fg: #4ADE80;

  --color-status-warning: #FBBF24;
  --color-status-warning-bg: #2A2210;
  --color-status-warning-bg-alt: #3A2F16;
  --color-status-warning-fg: #FBBF24;

  --color-status-danger: #F87171;
  --color-status-danger-bg: #2A1616;
  --color-status-danger-border: #6B3232;
  --color-status-danger-fg: #F87171;

  --color-status-info: var(--color-accent);
  --color-status-info-bg: var(--color-accent-subtle);
  --color-status-info-fg: var(--color-accent-hover);

  --font-ui: "Inter", -apple-system, "Segoe UI", Roboto, sans-serif;
  --font-display: "Inter", -apple-system, "Segoe UI", Roboto, sans-serif;
  --font-mono: ui-monospace, "SF Mono", monospace;
}
```

- [ ] **Step 2: `tokens.css` vor `globals.css` in `main.jsx` importieren**

Öffne `frontend/src/main.jsx`, finde die Zeile `import './globals.css';` und füge direkt davor ein:

```js
import './tokens.css';
```

- [ ] **Step 3: Inter-Schriftart in `index.html` laden**

In `frontend/index.html`, ersetze die bestehende Google-Fonts-Zeile:

```html
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,200..800&family=Figtree:ital,wght@0,300..900;1,300..900&display=swap" rel="stylesheet" />
```

durch:

```html
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,200..800&family=Figtree:ital,wght@0,300..900;1,300..900&family=Inter:ital,wght@0,300..900;1,300..900&display=swap" rel="stylesheet" />
```

- [ ] **Step 4: Manuell prüfen, dass die App noch unverändert aussieht**

Run: `npm run dev` (im `frontend/`-Verzeichnis), Seite im Browser öffnen.
Expected: Aussehen ist identisch zu vorher (Tokens sind nur definiert, noch nicht verwendet — `globals.css`/`theme.js` nutzen sie erst nach Task 2/3).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/tokens.css frontend/src/main.jsx frontend/index.html
git commit -m "feat(theme): tokens.css mit Kanzlei-Classic/Clio-Style/Clio-Dark Tokens"
```

---

## Task 2: `globals.css` entschlacken

**Files:**
- Modify: `frontend/src/globals.css`

**Interfaces:**
- Consumes: alle `--color-*`/`--font-*`/`--text-*` Variablen aus Task 1.
- Produces: `globals.css` enthält danach keine Token-Definitionen mehr, nur noch Resets/Animationen/Fokus/Scrollbar — Task 3 verlässt sich darauf, dass keine doppelten Token-Werte mehr existieren.

- [ ] **Step 1: Token-Definitionsblock aus `:root` entfernen, Rest umschreiben**

Ersetze den kompletten Inhalt von `frontend/src/globals.css` mit:

```css
/* Globale Styles – Unfallakten-System */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html, body, #root { height: 100%; }

:root {
  --text-xs:   0.75rem;     /* 12px – Timestamps, Badges, Kleingedrucktes */
  --text-sm:   0.8125rem;   /* 13px – Sekundärlabels, Meta-Infos           */
  --text-base: 0.875rem;    /* 14px – Primärer UI-Text, Formularfelder      */
  --text-md:   1rem;        /* 16px – Lesbarer Body, Hervorhebungen         */
  --text-lg:   1.125rem;    /* 18px – Unterabschnitts-Überschriften         */
  --text-xl:   1.25rem;     /* 20px – Abschnitts-Überschriften              */
  --text-2xl:  1.5rem;      /* 24px – Seiten-/Modal-Überschriften           */

  --weight-normal:   400;
  --weight-medium:   500;
  --weight-semibold: 600;
  --weight-bold:     700;

  --leading-tight:   1.2;
  --leading-snug:    1.35;
  --leading-normal:  1.5;
  --leading-relaxed: 1.65;
}

body {
  font-family: var(--font-ui);
  font-size: var(--text-base);
  line-height: var(--leading-normal);
  background: var(--color-brand-surface);
  color: var(--color-text-primary);
  font-kerning: normal;
  font-feature-settings: "kern" 1, "liga" 1;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.tabular-nums { font-variant-numeric: tabular-nums; }

@keyframes spin      { to { transform: rotate(360deg); } }
@keyframes shimmer   { 0%{background-position:-200% 0} 100%{background-position:200% 0} }
@keyframes slideUp   { from { transform: translateY(16px); opacity: 0; } to { transform: none; opacity: 1; } }
@keyframes fadeIn    { from { opacity: 0; } to { opacity: 1; } }
@keyframes pulse     { 0%,100%{opacity:1} 50%{opacity:0.45} }
@keyframes boot-spin { to { transform: translate(-50%, -50%) rotate(360deg); } }

:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
  border-radius: 3px;
}
input:focus-visible,
textarea:focus-visible,
select:focus-visible {
  outline: none; /* Inputs signalisieren Fokus via Border-Farbe */
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}

::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--color-border-strong); border-radius: 3px; }
input[type=number]::-webkit-inner-spin-button { opacity: 0; }

#root:empty::before {
  content: '';
  display: block;
  width: 40px; height: 40px;
  border: 3px solid var(--color-accent-trim);
  border-top-color: var(--color-brand-surface);
  border-radius: 50%;
  animation: boot-spin 0.8s linear infinite;
  position: fixed;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
}
```

Hinweis: `#root:empty::before` (Ladescreen-Spinner vor React-Hydration) läuft, **bevor** das Boot-Inline-Script aus Task 5 `data-scheme`/`data-theme` gesetzt hat, falls die Script-Reihenfolge das nicht abfängt — Task 5 stellt sicher, dass das Boot-Script vor dem `<div id="root">` im `<head>` läuft, damit auch der Spinner schon die richtigen Variablen sieht.

- [ ] **Step 2: Visuell prüfen**

Run: `npm run dev`, Seite neu laden.
Expected: Identisches Aussehen wie vor der Änderung (alle Werte lösen weiterhin auf `:root`/`[data-scheme="classic"][data-theme="light"]` aus Task 1 auf, da noch kein `data-scheme`-Attribut gesetzt wird — der `:root`-Fallback in `tokens.css` greift).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/globals.css
git commit -m "refactor(theme): globals.css auf tokens.css-Variablen umgestellt, Token-Duplikate entfernt"
```

---

## Task 3: `theme.js` zu Alias-Tabelle umbauen

**Files:**
- Modify: `frontend/src/config/theme.js`

**Interfaces:**
- Consumes: CSS-Variablennamen aus Task 1.
- Produces: `T.<key>` liefert weiterhin einen String (jetzt `"var(--...)"` statt Hex) — alle 41 Aufrufstellen im Code bleiben unverändert. `T.gold*` existiert danach nicht mehr.

- [ ] **Step 1: Prüfen, dass kein Code Hex-Werte aus `T` parst (Sicherheitsnetz vor der Umstellung)**

Run: `grep -rE "T\.\w+\.(slice|split|match|replace)|parseInt\(T\.|charCodeAt" frontend/src --include=*.jsx --include=*.js`
Expected: keine Treffer (bereits während der Planung verifiziert — falls doch ein Treffer erscheint, diese Stelle vor Fortsetzung einzeln prüfen und in der PR erwähnen).

- [ ] **Step 2: `theme.js` komplett ersetzen**

```js
// frontend/src/config/theme.js
const T = {
  navy:      "var(--color-brand-surface)",
  navyDark:  "var(--color-brand-surface-strong)",
  navyMid:   "var(--color-brand-surface-mid)",
  navyLight: "var(--color-brand-surface-hover)",

  accent:      "var(--color-accent)",
  accentLight: "var(--color-accent-hover)",
  accentPale:  "var(--color-accent-subtle)",
  accentDark:  "var(--color-accent-hover)",
  accentTrim:  "var(--color-accent-trim)",

  white:      "#FFFFFF",
  offWhite:   "var(--color-bg-page)",
  surface:    "var(--color-bg-inset)",
  border:     "var(--color-border)",
  borderSoft: "var(--color-border-soft)",

  text:      "var(--color-text-primary)",
  textMid:   "var(--color-text-secondary)",
  textMuted: "var(--color-text-muted)",
  textFaint: "var(--color-text-faint)",

  green:      "var(--color-status-success)",
  greenBg:    "var(--color-status-success-bg)",
  greenLight: "var(--color-status-success-border)",
  greenText:  "var(--color-status-success-fg)",

  amber:     "var(--color-status-warning)",
  amberBg:   "var(--color-status-warning-bg)",
  amberMid:  "var(--color-status-warning-bg-alt)",
  amberText: "var(--color-status-warning-fg)",

  red:       "var(--color-status-danger)",
  redBg:     "var(--color-status-danger-bg)",
  redLight:  "var(--color-status-danger-border)",
  redText:   "var(--color-status-danger-fg)",

  blue:      "var(--color-status-info)",
  blueBg:    "var(--color-status-info-bg)",
  blueText:  "var(--color-status-info-fg)",

  fontDisplay: "var(--font-display)",
  fontBody:    "var(--font-ui)",
  fontMono:    "var(--font-mono)",

  textXs:   "0.75rem",
  textSm:   "0.8125rem",
  textBase: "0.875rem",
  textMd:   "1rem",
  textLg:   "1.125rem",
  textXl:   "1.25rem",
  text2Xl:  "1.5rem",
};

export default T;
```

`white: "#FFFFFF"` bleibt bewusst ein Literal (kein `var()`) — der Wert ist in allen drei Schema/Modus-Kombinationen identisch (`--color-text-on-accent` ist überall `#FFFFFF`), es gibt also keine Varianz abzubilden.

- [ ] **Step 3: Dev-Server durchklicken**

Run: `npm run dev`, mehrere Views öffnen (Übersicht, Klage-Wizard, Einstellungen, E-Mail-Import).
Expected: Identisches Aussehen wie vor der Änderung — nur Umbenennung der Werte-Quelle, keine visuelle Änderung, da `[data-scheme]` noch nicht gesetzt wird.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/config/theme.js
git commit -m "refactor(theme): theme.js von Hex-Werten auf CSS-Variablen-Referenzen umgestellt, gold-Tokens entfernt"
```

---

## Task 4: Schrift-Migration (Figtree/Bricolage-Literale → Token)

**Files:**
- Modify: `frontend/src/sections/OnboardingHub.jsx` (Sonderfall zuerst)
- Create (temporär, wird in Step 5 wieder gelöscht): `frontend/scripts/tmp-migrate-fonts.cjs`
- Modify: alle `.jsx`-Dateien unter `frontend/src` mit hartcodierten `Figtree`/`Bricolage Grotesque`-Strings (36 Dateien, per Skript)

**Interfaces:**
- Consumes: `T.fontBody`/`T.fontDisplay` aus Task 3.
- Produces: keine hartcodierten Font-Family-Strings mehr im Code außer in `tokens.css` selbst und der Google-Fonts-URL.

- [ ] **Step 1: Sonderfall `OnboardingHub.jsx` zuerst fixen**

Diese Datei hat ein **eigenes lokales** `const T = {...}`, das den globalen Import verschattet — ein automatischer Ersatz durch `T.fontDisplay`/`T.fontBody` würde sonst auf undefinierte Keys zeigen. Öffne `frontend/src/sections/OnboardingHub.jsx`, ändere den Kopf von:

```js
const T = {
  navy:    "#1B2A4A",
  border:  "#E2DDD3",
  amber:   "#d97706", amberBg: "#fffbeb", amberBorder: "#fde68a",
  green:   "#16a34a", greenBg: "#f0fdf4", greenBorder:  "#86efac",
  purple:  "#7c3aed", purpleBg: "#f5f3ff", purpleBorder: "#c4b5fd",
};
```

zu:

```js
const T = {
  navy:    "#1B2A4A",
  border:  "#E2DDD3",
  amber:   "#d97706", amberBg: "#fffbeb", amberBorder: "#fde68a",
  green:   "#16a34a", greenBg: "#f0fdf4", greenBorder:  "#86efac",
  purple:  "#7c3aed", purpleBg: "#f5f3ff", purpleBorder: "#c4b5fd",
  fontDisplay: "var(--font-display)",
  fontBody:    "var(--font-ui)",
};
```

Die restlichen lokalen Farbwerte (navy/amber/green/purple) bleiben unverändert — dieses Onboarding-Banner ist klein und eigenständig, seine Akzentfarben ändern sich bewusst nicht mit dem Schema-Wechsel (nur die Schrift zieht mit, damit die Typografie überall konsistent bleibt).

- [ ] **Step 2: Migrationsskript schreiben**

```js
// frontend/scripts/tmp-migrate-fonts.cjs
const fs = require("fs");
const path = require("path");

const SRC = path.join(__dirname, "..", "src");

function walk(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, out);
    else if (entry.name.endsWith(".jsx")) out.push(full);
  }
  return out;
}

const REPLACEMENTS = [
  [/fontFamily:(\s*)"'Figtree'\s*,\s*sans-serif"/g, 'fontFamily:$1T.fontBody'],
  [/fontFamily:(\s*)"Figtree"/g, 'fontFamily:$1T.fontBody'],
  [/fontFamily:(\s*)"'Bricolage Grotesque'\s*,(?:\s*system-ui\s*,)?\s*sans-serif"/g, 'fontFamily:$1T.fontDisplay'],
  [/fontFamily:(\s*)"Bricolage Grotesque"/g, 'fontFamily:$1T.fontDisplay'],
];

let changedFiles = 0;
let totalReplacements = 0;

for (const file of walk(SRC)) {
  const original = fs.readFileSync(file, "utf8");
  let content = original;
  for (const [pattern, replacement] of REPLACEMENTS) {
    content = content.replace(pattern, replacement);
  }
  if (content !== original) {
    fs.writeFileSync(file, content, "utf8");
    changedFiles++;
    console.log("geändert:", path.relative(SRC, file));
  }
}

console.log(`\n${changedFiles} Dateien geändert.`);
```

- [ ] **Step 3: Skript ausführen**

Run: `node frontend/scripts/tmp-migrate-fonts.cjs`
Expected: Konsolen-Ausgabe listet ~36 geänderte Dateien, endet mit `<N> Dateien geändert.` (N > 30).

- [ ] **Step 4: Verifizieren, dass keine hartcodierten Font-Strings mehr übrig sind**

Run: `grep -rn "Figtree\|Bricolage Grotesque" frontend/src --include=*.jsx | grep -v tokens.css`
Expected: keine Treffer (Google-Fonts-Referenz liegt in `index.html`, nicht in `.jsx`-Dateien, daher hier keine Treffer erwartet).

- [ ] **Step 5: Temporäres Skript löschen**

Run: `git rm frontend/scripts/tmp-migrate-fonts.cjs` (falls das Verzeichnis danach leer ist, wird es automatisch nicht mehr getrackt — kein weiterer Schritt nötig).

- [ ] **Step 6: Build-Check**

Run: `cd frontend && npm run build`
Expected: Build läuft ohne Fehler durch (keine Syntaxfehler durch die automatischen Ersetzungen).

- [ ] **Step 7: Visuelle Stichprobe**

Run: `npm run dev`, folgende Views öffnen: Übersicht, Klage-Wizard (`KlageSection.jsx`), Einstellungen, E-Mail-Import, Onboarding-Hinweis-Banner (bei einer Akte ohne IBAN sichtbar).
Expected: Schrift sieht exakt wie vorher aus (Figtree/Bricolage Grotesque, da Schema noch `classic`/`light` ist).

- [ ] **Step 8: Commit**

```bash
git add frontend/src
git commit -m "refactor(theme): hartcodierte Figtree/Bricolage-Fontfamily-Strings auf T.fontBody/T.fontDisplay umgestellt"
```

---

## Task 5: `themePrefs.js` + Boot-Script (Persistenz, kein FOUC)

**Files:**
- Create: `frontend/src/theme/themePrefs.js`
- Create: `frontend/src/theme/themePrefs.test.js`
- Modify: `frontend/index.html`

**Interfaces:**
- Produces:
  - `getThemePrefs(): { scheme: 'classic'|'clio', mode: 'light'|'dark' }`
  - `setThemePrefs({ scheme, mode }): void` — schreibt localStorage + setzt `document.documentElement.dataset.scheme`/`.theme`
  - `THEME_STORAGE_KEY: string` (exportierte Konstante `'unfallakten.theme'`)
- Consumes von Task 6: keine (Task 6 konsumiert dieses Modul).

- [ ] **Step 1: Test schreiben**

```js
// frontend/src/theme/themePrefs.test.js
import { describe, it, expect, beforeEach } from "vitest";
import { getThemePrefs, setThemePrefs, THEME_STORAGE_KEY } from "./themePrefs.js";

describe("themePrefs", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-scheme");
    document.documentElement.removeAttribute("data-theme");
  });

  it("liefert Default classic/light, wenn nichts gespeichert ist", () => {
    expect(getThemePrefs()).toEqual({ scheme: "classic", mode: "light" });
  });

  it("liefert Default, wenn localStorage kaputten JSON enthält", () => {
    localStorage.setItem(THEME_STORAGE_KEY, "{nicht valides json");
    expect(getThemePrefs()).toEqual({ scheme: "classic", mode: "light" });
  });

  it("speichert und liest eine gesetzte Präferenz zurück", () => {
    setThemePrefs({ scheme: "clio", mode: "dark" });
    expect(getThemePrefs()).toEqual({ scheme: "clio", mode: "dark" });
  });

  it("setzt data-scheme und data-theme auf documentElement", () => {
    setThemePrefs({ scheme: "clio", mode: "dark" });
    expect(document.documentElement.dataset.scheme).toBe("clio");
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("erzwingt mode=light, wenn scheme=classic gesetzt wird (kein Dark fuer Classic)", () => {
    setThemePrefs({ scheme: "classic", mode: "dark" });
    expect(getThemePrefs()).toEqual({ scheme: "classic", mode: "light" });
  });
});
```

- [ ] **Step 2: Test laufen lassen, sicherstellen dass er fehlschlägt**

Run: `cd frontend && npx vitest run src/theme/themePrefs.test.js`
Expected: FAIL mit „Failed to resolve import './themePrefs.js'" (Datei existiert noch nicht).

- [ ] **Step 3: `themePrefs.js` implementieren**

```js
// frontend/src/theme/themePrefs.js
export const THEME_STORAGE_KEY = "unfallakten.theme";

const DEFAULT_PREFS = { scheme: "classic", mode: "light" };

function normalize(prefs) {
  const scheme = prefs?.scheme === "clio" ? "clio" : "classic";
  const mode = scheme === "clio" && prefs?.mode === "dark" ? "dark" : "light";
  return { scheme, mode };
}

export function getThemePrefs() {
  try {
    const raw = localStorage.getItem(THEME_STORAGE_KEY);
    if (!raw) return { ...DEFAULT_PREFS };
    return normalize(JSON.parse(raw));
  } catch {
    return { ...DEFAULT_PREFS };
  }
}

export function setThemePrefs(prefs) {
  const normalized = normalize(prefs);
  localStorage.setItem(THEME_STORAGE_KEY, JSON.stringify(normalized));
  document.documentElement.dataset.scheme = normalized.scheme;
  document.documentElement.dataset.theme = normalized.mode;
  return normalized;
}
```

- [ ] **Step 4: Test laufen lassen, sicherstellen dass er passt**

Run: `cd frontend && npx vitest run src/theme/themePrefs.test.js`
Expected: 5 Tests PASS.

- [ ] **Step 5: Boot-Inline-Script in `index.html` einfügen (FOUC-Vermeidung)**

In `frontend/index.html`, füge direkt vor `<div id="root"></div>` ein:

```html
    <script>
      (function () {
        try {
          var raw = localStorage.getItem("unfallakten.theme");
          var prefs = raw ? JSON.parse(raw) : null;
          var scheme = prefs && prefs.scheme === "clio" ? "clio" : "classic";
          var mode = scheme === "clio" && prefs && prefs.mode === "dark" ? "dark" : "light";
          document.documentElement.dataset.scheme = scheme;
          document.documentElement.dataset.theme = mode;
        } catch (e) {
          document.documentElement.dataset.scheme = "classic";
          document.documentElement.dataset.theme = "light";
        }
      })();
    </script>
    <div id="root"></div>
```

Der Storage-Key (`"unfallakten.theme"`) und die Default-/Fallback-Logik sind hier bewusst dupliziert zu `themePrefs.js` — dieses Script muss synchron und ohne Modul-Ladezeit laufen, bevor der erste Frame gerendert wird. Ändert sich künftig das localStorage-Schema, müssen beide Stellen zusammen angepasst werden.

- [ ] **Step 6: Manuell prüfen**

Run: `npm run dev`, im Browser DevTools → Application → Local Storage `unfallakten.theme` auf `{"scheme":"clio","mode":"dark"}` setzen, Seite hart neu laden (Strg+Shift+R).
Expected: Kein kurzes Aufblitzen der hellen/Classic-Farben vor dem eigentlichen Rendering — `<html>` hat sofort `data-scheme="clio" data-theme="dark"`, sichtbar in den DevTools-Elementen schon vor React-Start (Seite selbst sieht optisch noch wie Classic aus, weil Task 6/UI-Komponenten das erst in Task 6 nutzen — hier geht es nur um das Attribut-Timing).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/theme/themePrefs.js frontend/src/theme/themePrefs.test.js frontend/index.html
git commit -m "feat(theme): themePrefs-Modul + Boot-Script fuer FOUC-freies Laden der Theme-Praeferenz"
```

---

## Task 6: „Darstellung"-Sektion in Einstellungen → System-Status

**Files:**
- Modify: `frontend/src/views/EinstellungenView.jsx`

**Interfaces:**
- Consumes: `getThemePrefs`, `setThemePrefs` aus Task 5 (`../theme/themePrefs.js`).

- [ ] **Step 1: Import ergänzen**

In `frontend/src/views/EinstellungenView.jsx`, Zeile 11 (nach dem `api.js`-Import-Block), ergänzen:

```js
import { getThemePrefs, setThemePrefs } from "../theme/themePrefs.js";
```

- [ ] **Step 2: State für Theme-Präferenz ergänzen**

Nach Zeile 28 (`const [speichert, setSpeichert] = useState(false);`) ergänzen:

```js
  const [themePrefs, setThemePrefsState] = useState(() => getThemePrefs());

  function handleSchemaWechsel(scheme) {
    const updated = setThemePrefs({ scheme, mode: themePrefs.mode });
    setThemePrefsState(updated);
  }

  function handleModeWechsel(mode) {
    const updated = setThemePrefs({ scheme: themePrefs.scheme, mode });
    setThemePrefsState(updated);
  }
```

- [ ] **Step 3: „Darstellung"-Sektion in den `system_status`-Tab einfügen**

In `frontend/src/views/EinstellungenView.jsx`, direkt nach der Zeile `{tab === "system_status" && (` und `<div style={{ maxWidth: 680 }}>` (aktuell Zeile 1162-1163), vor `<Card><CardHead title="System-Status" />`, folgenden neuen Block einfügen:

```jsx
            <Card style={{ marginBottom: "1.25rem" }}>
              <CardHead title="Darstellung" />
              <div style={{ padding: "1rem", display: "flex", flexDirection: "column", gap: "0.75rem" }}>

                <div style={{ color: T.textMuted, fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: "0.1em" }}>
                  Farbschema
                </div>
                <div style={{ display: "flex", gap: 10 }}>
                  {[
                    { id: "classic", label: "Kanzlei Classic", swatch1: "#1B2A4A", swatch2: "#A06B4A" },
                    { id: "clio",    label: "Clio-Style",      swatch1: "#1B4B91", swatch2: "#EAF0FA" },
                  ].map(s => (
                    <button
                      key={s.id}
                      onClick={() => handleSchemaWechsel(s.id)}
                      style={{
                        flex: 1, display: "flex", alignItems: "center", gap: 10,
                        padding: "10px 14px", borderRadius: 8, cursor: "pointer",
                        border: `2px solid ${themePrefs.scheme === s.id ? T.accent : T.border}`,
                        background: T.surface, fontFamily: T.fontBody, fontSize: "0.875rem",
                        fontWeight: 600, color: T.text,
                      }}
                    >
                      <span style={{ display: "flex", borderRadius: "50%", overflow: "hidden", width: 20, height: 20, flexShrink: 0 }}>
                        <span style={{ flex: 1, background: s.swatch1 }} />
                        <span style={{ flex: 1, background: s.swatch2 }} />
                      </span>
                      {s.label}
                    </button>
                  ))}
                </div>

                <div style={{ color: T.textMuted, fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: "0.1em", marginTop: 6 }}>
                  Dark Mode
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <div
                    onClick={() => {
                      if (themePrefs.scheme !== "clio") return;
                      handleModeWechsel(themePrefs.mode === "dark" ? "light" : "dark");
                    }}
                    title={themePrefs.scheme !== "clio" ? "Dark Mode aktuell nur fuer Clio-Style verfuegbar" : ""}
                    style={{
                      width: 42, height: 24, borderRadius: 12,
                      background: themePrefs.mode === "dark" ? T.accent : T.border,
                      position: "relative",
                      cursor: themePrefs.scheme === "clio" ? "pointer" : "not-allowed",
                      opacity: themePrefs.scheme === "clio" ? 1 : 0.45,
                      transition: "background 0.2s", flexShrink: 0,
                    }}
                  >
                    <div style={{
                      position: "absolute", top: 3,
                      left: themePrefs.mode === "dark" ? 21 : 3,
                      width: 18, height: 18, borderRadius: 9, background: "#fff",
                      transition: "left 0.2s", boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
                    }} />
                  </div>
                  <span style={{ fontFamily: T.fontBody, fontSize: "0.8rem", color: T.textMuted }}>
                    {themePrefs.scheme !== "clio"
                      ? "Dark Mode aktuell nur für Clio-Style verfügbar"
                      : themePrefs.mode === "dark" ? "An" : "Aus"}
                  </span>
                </div>

              </div>
            </Card>
```

- [ ] **Step 4: Manuell testen**

Run: `npm run dev`, Einstellungen → System-Status öffnen.
Expected:
- Beide Schema-Karten sichtbar mit Farb-Swatches, „Kanzlei Classic" initial hervorgehoben (Rahmen in Akzentfarbe).
- Klick auf „Clio-Style" färbt die **gesamte App** sofort um (Header, Buttons, Karten, Schrift wechselt auf Inter) — kein Reload nötig.
- Dark-Mode-Schalter ist bei „Kanzlei Classic" ausgegraut/deaktiviert mit Hinweistext, bei „Clio-Style" aktiv bedienbar.
- Toggle auf Dark Mode färbt die App dunkel um.
- Hard-Reload (Strg+Shift+R) behält die zuletzt gewählte Kombination bei, ohne Farbblitz.
- `localStorage.getItem("unfallakten.theme")` in DevTools zeigt den aktuellen Stand.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/EinstellungenView.jsx
git commit -m "feat(einstellungen): Darstellung-Sektion mit Farbschema- und Dark-Mode-Umschalter in System-Status"
```

---

## Task 7: Manuelle Test-Runde über die Gesamt-App

**Files:** keine Code-Änderungen — reine Verifikation.

- [ ] **Step 1: Vollständigen Durchklick-Test durchführen**

Mit `npm run dev` laufend, für jede Kombination (`classic/light`, `clio/light`, `clio/dark`) folgende Views öffnen und auf Lesbarkeit/Kontrast/Konsistenz prüfen:
- Übersicht (`UebersichtSection.jsx`)
- Eine Akte im Detail (Beteiligte, Schaden, Dokumente, Klage-Wizard)
- Einstellungen (alle Tabs, nicht nur System-Status)
- E-Mail-Import
- Onboarding-Hinweis-Banner (bei einer Akte ohne IBAN im Mandanten-Datensatz)

Expected: In allen drei Kombinationen sind Texte lesbar (kein dunkler Text auf dunklem Grund o.ä.), Buttons/Badges erkennbar, keine Layoutbrüche.

- [ ] **Step 2: Edge Cases prüfen**

- localStorage-Eintrag `unfallakten.theme` per DevTools löschen → Hard-Reload → Default (`Kanzlei Classic`/hell) wird geladen.
- localStorage-Eintrag manuell auf kaputten Wert setzen (z. B. `localStorage.setItem("unfallakten.theme","{invalid")`) → Hard-Reload → App stürzt nicht ab, fällt auf Default zurück.
- Von `clio/dark` zurück auf `classic` wechseln → Dark-Mode-Schalter wird automatisch deaktiviert, App zeigt helle Classic-Farben (kein Rest-Dark).

- [ ] **Step 3: Build-Check**

Run: `cd frontend && npm run build`
Expected: Build erfolgreich, keine Warnungen zu unbekannten CSS-Variablen.

- [ ] **Step 4: Vorhandene Test-Suite laufen lassen**

Run: `cd frontend && npx vitest run`
Expected: Alle bestehenden Tests weiterhin grün (keine Regression durch die Font-Migration oder Token-Umstellung), plus die 5 neuen `themePrefs`-Tests aus Task 5.
