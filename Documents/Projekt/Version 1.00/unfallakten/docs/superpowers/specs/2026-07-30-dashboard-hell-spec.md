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
