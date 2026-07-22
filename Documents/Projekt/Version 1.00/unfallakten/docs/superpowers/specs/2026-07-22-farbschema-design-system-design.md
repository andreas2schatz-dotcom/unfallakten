# Design: Farbschema-/Dark-Mode-System + Single Source of Truth

Datum: 2026-07-22

## Problem

Das UI-Farb-/Schrift-System ist aktuell an zwei Stellen dupliziert:

- `frontend/src/config/theme.js` — JS-Objekt `T` mit Hex-Werten, in 41 Dateien per Inline-Style verwendet (`style={{ color: T.navy }}`).
- `frontend/src/globals.css` — CSS Custom Properties mit denselben Farben in OKLCH, für globale Basis-Styles.

Beide Quellen können auseinanderlaufen (Drift-Risiko). Zusätzlich ist die Schriftart (`Figtree`/`Bricolage Grotesque`) in 608 (Figtree) + 39 (Bricolage) Stellen als Literal-String hart codiert statt über `T.fontBody`/`T.fontDisplay` (nur 6 Verwendungsstellen) — ein Schriftwechsel würde diese Stellen nicht erreichen.

Es gibt kein Dark Mode und keine Möglichkeit, ein alternatives Farbschema zu testen.

## Ziel

1. Eine einzige Quelle der Wahrheit für Design-Tokens (Farbe + Schrift).
2. Neuer Bereich „Darstellung" in Einstellungen → System-Status: Umschalter für
   - Farbschema: **Kanzlei Classic** (bestehend, Navy/Sienna) vs. **Clio-Style** (neu, an Clio/MyCase orientiert)
   - Dark Mode: nur für Clio-Style verfügbar (v1)
3. Persistente Einstellung pro Sachbearbeiter:in (localStorage, browserlokal, kein Kanzlei-weites Setting).

## Nicht-Ziele (v1)

- Radius-/Schatten-/Spacing-Tokens des Clio-Sets werden **nicht** übernommen — diese sind aktuell ebenfalls überall hart codiert (`borderRadius: 8` etc.), eine Migration wäre ein separates, größeres Projekt mit wenig zusätzlichem visuellen Effekt gegenüber Farbe+Schrift. Bleibt vorerst bei bestehenden festen Werten in beiden Schemata.
- Dark-Variante für Kanzlei Classic — kann später ergänzt werden, sobald gebraucht.
- Kanzlei-weites/serverseitiges Theme-Setting (DB) — Einstellung ist rein browserlokal (localStorage), jede SB-Person kann unabhängig wählen.
- Kein React-Context/Provider — Umfärbung läuft vollständig über CSS-Variablen + DOM-Attribute, kein Re-Render der App nötig.

## Architektur

### Token-Datei: `frontend/src/tokens.css` (neu)

Ersetzt die Token-Definitionen aus `globals.css`. Struktur: Werte verschachtelt nach `[data-scheme]` × `[data-theme]`-Attributen auf `<html>`.

```css
:root,
[data-scheme="classic"][data-theme="light"] {
  --color-bg-page: #F6F4EF;
  --color-bg-card: #FAFAF8;
  --color-border: #E2DDD3;
  --color-border-strong: #C9C2B4;
  --color-accent: #A06B4A;
  --color-accent-hover: #7D5038;
  --color-accent-subtle: #F3EAE2;
  --color-status-success-bg: #ecfdf5;
  --color-status-success-fg: #065f46;
  --color-status-warning-bg: #fffbeb;
  --color-status-warning-fg: #92400e;
  --color-status-danger-bg: #fef2f2;
  --color-status-danger-fg: #991b1b;
  --color-status-neutral-bg: #FAFAF8;
  --color-status-neutral-fg: #6b7094;
  --color-text-primary: #1a1a2e;
  --color-text-secondary: #3d4060;
  --color-text-muted: #6b7094;
  --color-text-faint: #9da3be;
  --color-text-on-accent: #FFFFFF;
  --font-ui: 'Figtree', system-ui, sans-serif;
  --font-display: 'Bricolage Grotesque', system-ui, sans-serif;
  --font-mono: ui-monospace, 'Cascadia Code', 'Fira Code', monospace;
}

[data-scheme="clio"][data-theme="light"] {
  --color-bg-page: #F5F6F8;
  --color-bg-card: #FFFFFF;
  --color-border: #E3E6EA;
  --color-border-strong: #CBD0D8;
  --color-accent: #1B4B91;
  --color-accent-hover: #163C74;
  --color-accent-subtle: #EAF0FA;
  --color-status-success-bg: #E6F4EA;
  --color-status-success-fg: #1E7A34;
  --color-status-warning-bg: #FFF4E0;
  --color-status-warning-fg: #9A5B00;
  --color-status-danger-bg: #FBE7E7;
  --color-status-danger-fg: #B23A3A;
  --color-status-neutral-bg: #EEF0F3;
  --color-status-neutral-fg: #5B6472;
  --color-text-primary: #1A1D21;
  --color-text-secondary: #5B6472;
  --color-text-muted: #8A93A1;
  --color-text-faint: #A9B0BC;
  --color-text-on-accent: #FFFFFF;
  --font-ui: "Inter", -apple-system, "Segoe UI", Roboto, sans-serif;
  --font-display: "Inter", -apple-system, "Segoe UI", Roboto, sans-serif;
  --font-mono: ui-monospace, "SF Mono", monospace;
}

[data-scheme="clio"][data-theme="dark"] {
  --color-bg-page: #14161A;
  --color-bg-card: #1C1F24;
  --color-border: #2A2E35;
  --color-border-strong: #3A3F47;
  --color-accent: #4B8AE0;
  --color-accent-hover: #6FA3EA;
  --color-accent-subtle: #1E2A3D;
  --color-status-success-bg: #14261C;
  --color-status-success-fg: #4ADE80;
  --color-status-warning-bg: #2A2210;
  --color-status-warning-fg: #FBBF24;
  --color-status-danger-bg: #2A1616;
  --color-status-danger-fg: #F87171;
  --color-status-neutral-bg: #21242A;
  --color-status-neutral-fg: #9BA3AF;
  --color-text-primary: #E8EAED;
  --color-text-secondary: #9BA3AF;
  --color-text-muted: #7C8591;
  --color-text-faint: #5B6472;
  --color-text-on-accent: #FFFFFF;
  --font-ui: "Inter", -apple-system, "Segoe UI", Roboto, sans-serif;
  --font-display: "Inter", -apple-system, "Segoe UI", Roboto, sans-serif;
  --font-mono: ui-monospace, "SF Mono", monospace;
}
```

Fehlt `data-scheme` ganz oder ist unbekannt → `:root`-Fallback (heutiges Classic/Light-Aussehen), kein Breaking Change falls das Attribut mal nicht gesetzt ist.

### `theme.js` wird Alias-Tabelle

Jeder bestehende Schlüssel bleibt erhalten (keine Aufrufstellen-Änderung nötig), zeigt aber auf `var(--...)` statt Hex. Vollständiges Mapping (bestehender Schlüssel → neuer CSS-Var-Name):

| alter Schlüssel | neuer Wert |
|---|---|
| `navy`, `navyDark`, `navyMid`, `navyLight` | `var(--color-text-primary)` (Rollen-Zusammenlegung — diese vier Abstufungen dienten nur der Navy-Optik, im Rollen-Modell reicht `text-primary`; Ausnahme: falls sich beim Durchgehen der Verwendungsstellen zeigt, dass eine Abstufung wirklich als eigenständige Rolle gebraucht wird, bekommt sie einen eigenen neuen Slot statt Zusammenlegung) |
| `accent` | `var(--color-accent)` |
| `accentLight` | `var(--color-accent-hover)` |
| `accentPale` | `var(--color-accent-subtle)` |
| `accentDark` | `var(--color-accent-hover)` |
| `accentTrim` | eigener Slot `var(--color-accent-trim)` (transparente rgba, je Schema explizit definiert) |
| `gold`, `goldLight`, `goldPale`, `goldTrim` | **entfernt** (0 Verwendungsstellen, deprecated) |
| `white` | `var(--color-bg-card)` bzw. `var(--color-text-on-accent)` je Kontext (beim Durchgehen der Stellen entscheiden) |
| `offWhite` | `var(--color-bg-page)` |
| `surface` | `var(--color-bg-card)` |
| `border` | `var(--color-border)` |
| `borderSoft` | eigener Slot `var(--color-border-soft)` |
| `text` | `var(--color-text-primary)` |
| `textMid` | `var(--color-text-secondary)` |
| `textMuted` | `var(--color-text-muted)` |
| `textFaint` | `var(--color-text-faint)` |
| `green`/`greenBg`/`greenLight`/`greenText` | `var(--color-status-success-fg)`/`-bg`/eigener Slot/`-fg` |
| `amber`/`amberBg`/`amberMid`/`amberText` | analog `--color-status-warning-*` |
| `red`/`redBg`/`redLight`/`redText` | analog `--color-status-danger-*` |
| `blue`/`blueBg`/`blueText` | analog `--color-status-neutral-*` oder eigener Info-Slot, falls Blau bei Clio mit dem Akzent kollidiert (Clio-Akzent ist selbst Blau) — beim Umsetzen prüfen und ggf. `--color-status-info-*` separat von `--color-accent` führen |
| `fontDisplay` | `var(--font-display)` |
| `fontBody` | `var(--font-ui)` |
| `fontMono` | `var(--font-mono)` |
| `textXs` … `text2Xl` | unverändert (reine rem-Werte, kein Farb-/Schema-Bezug) |

Genaue 1:1-Zuordnung wird beim Umsetzen anhand der tatsächlichen Verwendungsstellen verfeinert (z. B. wo `navyDark` speziell für Hover-States auf dunklem Grund gebraucht wird, bekommt es ggf. doch einen eigenen Slot statt Zusammenlegung auf `text-primary`).

### `globals.css` wird schlanker

Token-Definitionen wandern komplett nach `tokens.css`. `globals.css` behält nur Nicht-Token-Globales: CSS-Reset, `body`-Basisstyles (referenzieren jetzt `var(--color-bg-page)`/`var(--font-ui)` statt Hardcode), Animationen (`@keyframes`), Scrollbar-Styling, Fokus-Ring, Ladescreen-Spinner. `frontend/index.html` bindet zusätzlich `tokens.css` ein (vor `globals.css`).

### Schrift-Migration (608 + 39 Fundstellen)

Automatisiertes Suchen&Ersetzen per Skript über `frontend/src/**/*.jsx`:

- `fontFamily:"'Figtree',sans-serif"` (alle Schreibvarianten von Anführungszeichen/Leerzeichen) → `fontFamily:T.fontBody`
- `fontFamily:"'Bricolage Grotesque',sans-serif"` → `fontFamily:T.fontDisplay`
- Skript ergänzt `import T from ...theme` in Dateien, die `T` noch nicht importieren.
- Vor dem Lauf: Grep nach allen tatsächlichen Schreibvarianten (Anführungszeichen-Stile, mit/ohne Leerzeichen nach Doppelpunkt, CSS-Dateien) sammeln, damit das Skript vollständig ist.
- Nach dem Lauf: `npm run build` (Syntax-Check) + visuelle Stichprobe mehrerer Views.

### Risiko-Check: `var(...)`-Strings statt Hex

Alle bisherigen Verwendungen von `T.xxx` als String funktionieren unverändert (Template-Strings, `rgba()`-Kombinationen etc.), **außer** falls irgendwo der Hex-Wert geparst wird (z. B. Helligkeit berechnen, Farbkanäle extrahieren). Vor der Migration: Grep auf Muster wie `T\.\w+\.slice`, `parseInt.*T\.`, Farb-Interpolationsfunktionen — falls Treffer, diese Stellen einzeln behandeln.

## Settings-UI

### Ort

Neuer Abschnitt **„Darstellung"** ganz oben im `system_status`-Tab in `EinstellungenView.jsx` (vor dem RA-Micro-Block), im bestehenden visuellen Muster (Kapitälchen-Label + Karten mit `T.surface`-Hintergrund, wie bei „Externe Dienste"/„Pipeline").

### Inhalt

- **Farbschema-Auswahl**: zwei wählbare Karten mit Farb-Swatches (Hintergrund+Akzent) zur Wiedererkennung:
  - „Kanzlei Classic" (Navy/Sienna-Swatches)
  - „Clio-Style" (Blau/Grau-Swatches)
- **Dark Mode**: Toggle-Switch (gleiches Switch-Muster wie der bestehende IMAP-Aktiv-Schalter). **Deaktiviert/ausgegraut**, wenn „Kanzlei Classic" gewählt ist, mit Hinweistext „Dark Mode aktuell nur für Clio-Style verfügbar". Wechselt man zurück zu Clio, wird der zuletzt gewählte Modus wiederhergestellt.
- Auswahl wirkt **sofort** (kein „Übernehmen"-Button) — passt zum Charakter „auswählen und live testen", jederzeit reversibel.

## Persistenz & Ladeverhalten

- `localStorage['unfallakten.theme']` = `{ scheme: 'classic'|'clio', mode: 'light'|'dark' }`
- Default (kein Eintrag vorhanden): `{ scheme: 'classic', mode: 'light' }` → exakt heutiges Aussehen, keine Änderung für bestehende Nutzer bis aktiv umgeschaltet wird.
- **FOUC-Vermeidung**: Inline-`<script>` in `frontend/index.html`, **vor** dem React-Bundle, liest den localStorage-Wert synchron und setzt `data-scheme`/`data-theme` auf `<html>` vor dem ersten Paint.
- Neues Modul `frontend/src/theme/themePrefs.js`:
  - `getThemePrefs()` → liest localStorage, liefert Default falls leer/kaputt
  - `setThemePrefs({ scheme, mode })` → schreibt localStorage + setzt beide Attribute auf `document.documentElement`
  - Wird von der neuen „Darstellung"-Sektion in `EinstellungenView.jsx` verwendet.
- Bewusste kleine Duplizierung: Der Inline-Boot-Script kennt Key-Name und Default separat vom JS-Modul, weil er synchron und ohne Modul-Ladezeit laufen muss. Beide Stellen müssen bei einer künftigen Änderung des localStorage-Schemas gemeinsam angepasst werden.
- **Kein React-Context/Provider**: Die Umfärbung läuft komplett über CSS-Variablen-Kaskade durchs `data-scheme`/`data-theme`-Attribut. Nur die Settings-Komponente selbst braucht lokalen State, um die aktuelle Auswahl anzuzeigen.

## Testing

Kein Business-Logic-Kern, der Unit-Tests rechtfertigt (reine DOM-Attribut- + localStorage-Zuweisung). Manuelle Prüfliste:

1. Umschalten Classic ↔ Clio, beide Richtungen — Farben + Schrift wechseln überall (Stichproben: Übersicht, Klage-Wizard, Action-Board, Einstellungen selbst).
2. Dark Mode An/Aus bei Clio — Kontrast/Lesbarkeit in mehreren Views prüfen.
3. Dark-Mode-Switch bei Classic ist gesperrt/ausgegraut.
4. Hard-Reload nach jeder Umschaltung — kein Farb-/Schrift-Flackern beim Laden.
5. localStorage löschen → Default (Classic/Light) wird geladen.
6. `npm run build` nach Schrift-Migrationsskript — keine Syntaxfehler.

## Umsetzungsreihenfolge (grob, für Implementierungsplan)

1. `tokens.css` anlegen (beide Schemata + Clio-Dark), in `index.html` einbinden.
2. `globals.css` entschlacken (Token-Teil raus, Referenzen auf `var(...)` umstellen).
3. `theme.js` auf Alias-Tabelle umstellen (inkl. Grep-Check auf Hex-parsende Stellen vorher).
4. Schrift-Migrationsskript schreiben + laufen lassen (608+39 Stellen), Build-Check.
5. `themePrefs.js` + Boot-Inline-Script in `index.html`.
6. „Darstellung"-Sektion in `EinstellungenView.jsx` bauen.
7. Manuelle Testrunde (siehe oben).
