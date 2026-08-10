# Review-Befunde: ÜbersichtSection + AkteDetailView (2026-08-10)

Reiner Befund-Katalog — **nichts davon wurde gefixt**. Fix-Session separat planen.

> **Update 2026-08-10 (Fix-Session, gleicher Tag):** B1, B2, B4, B5, B6, B7, B8 ✅ gefixt
> (TDD, 11 neue Tests, Vollsuite 476/476 grün — Protokoll: `docs/CHANGELOG.md` 2026-08-10).
> **Offen für die Redesign-Session:** B3 (Summen-SSOT ist Design-Entscheidung) sowie die
> Abschnitte B (redundante Requests/Berechnungen) und C (Kosmetik).
Dateien: `frontend/src/sections/UebersichtSection.jsx` (2552 Zeilen), `frontend/src/components/AkteDetailView.jsx`, `frontend/src/sections/OnboardingHub.jsx`.

## A — Echte Bugs

### B1 · Crash-Gefahr: `effRep`/`ist130` nicht definiert (KRITISCH)
`UebersichtSection.jsx:906` (RegulierungsTabelle):
```js
if (art === "totalschaden" || (!art && wbw > 0 && (effRep === 0 || (!ist130 && effRep > nettoFzg)))) {
```
`effRep` und `ist130` existieren in dieser Funktion **nicht** (nur in `config/constants.js:383-391` und `SchadenSection.jsx:194ff` — die Zeile wurde offenbar unvollständig kopiert). Sobald keine `abrechnungsart` gesetzt ist **und** `wiederbeschaffung > 0`, wirft die Komponente einen ReferenceError → die Regulierungsdetails-Karte (standardmäßig offen!) crasht. Fix-Idee: Berechnung aus `constants.js` wiederverwenden statt kopieren.

### B2 · OnboardingHub prüft Felder, die es nicht gibt → Kacheln werden nie grün
`OnboardingHub.jsx`:
- Z. 19: `schaden?.positionen?.length` — das Schaden-Objekt hat flache Felder (`rep_gutachten_netto` …), kein `positionen`-Array → **„Schadenspositionen" nie grün**.
- Z. 18: `schaden?.unfalldatum && schaden?.unfallort` — die liegen auf `akte` bzw. in den Unfalldetails, nicht auf `schaden` → **„Unfalldetails" nie grün**.
- Z. 21: `aktivitaeten.some(a => a.typ === "forderungsschreiben")` — Aktivitäten haben das Feld `aktion` mit anderen Codes (siehe aktionLabels in AktenTimeline) → **„Erstforderung" nie grün**.
- Z. 17: Rollen `["ghpv","versicherung","ghpv_versicherung"]` kleingeschrieben — real sind es `GHPV`/`GHV`/`GBEV` (über `b.rolle || b.kuerzel`, Großschreibung) → **„GHPV" nie grün**.
- Z. 23: Sichtbarkeit `!mandant || !mandant.iban` — das lokale IBAN-Feld ist bei RA-MICRO-Akten praktisch immer leer (der echte IBAN-Check läuft über `/ramicro/akte/mandant-checks`) → **Hub erscheint quasi immer**, egal wie weit die Akte ist. Das ist der Kern von „stört mehr als es hilft".
- Kosmetik: Überschrift sagt „x von 6 Bereichen", es sind aber 7 Kacheln.

### B3 · Kennzahlen widersprechen sich auf demselben Screen
- Header-KPI (`AkteDetailView.jsx:302ff`): Gefordert = `liveBrutto × HQ`, Reguliert = `Σ ab.gesamt_reguliert`.
- FinanzBand (`UebersichtSection.jsx:1936ff` + Aggregation ab 2276): Positionssummen **ohne** HQ, Reguliert positionsweise (manuell kumulativ, PDF letzter gewinnt).
- Dazu dritte Quelle PositionsDashboard (Ereignismodell: gefordert/anerkannt/offen), vierte die RegulierungsTabelle-Fußzeile, fünfte die Forderungshistorie.
Bei Teilhaftung oder Teilzahlungen zeigen Header und FinanzBand unterschiedliche Beträge direkt übereinander.

### B4 · Header-Button „+ Todo" öffnet kein Formular
`AkteDetailView.jsx:333`: `onClick: () => setSec("uebersicht")` — navigiert nur zur Übersicht. Das zugehörige Inline-Formular existiert nur in der **toten** Komponente `AkteActionBoardHeader` (s. B5).

### B5 · Toter Code in UebersichtSection.jsx
- `AkteActionBoardHeader` (Z. 2033) — nirgends verwendet, dupliziert die Header-Buttons.
- `TodoKachelKompakt` (Z. 1446) — nirgends verwendet, Vorgänger von `TodoWvSpalten`.
- `InfoZeile` (Z. 20) — nirgends verwendet.
- In der Hauptkomponente: `InfoRow` (Z. 2424), `regGrad` (Z. 2419), `klageSumme` (Z. 2418) werden berechnet, aber nie gerendert.
- `StaDialog` wird in `AkteDetailView` über den Re-Export aus UebersichtSection importiert statt direkt aus `components/StaDialog.jsx`.

### B6 · Akten-Chronik: Sortierung kaputt
`UebersichtSection.jsx:782ff`: Aktivitäten-Datum wird erst zu `"TT.MM.JJJJ HH:MM"` formatiert, dann `split(".").reverse().join("-")` → `"JJJJ HH:MM-MM-TT"`. Lexikografischer Vergleich sortiert damit innerhalb eines Jahres nach **Uhrzeit statt Monat**; Mischung mit ISO-Datum der Abrechnungen zusätzlich inkonsistent. Fix-Idee: vor der Formatierung auf ISO-Timestamps sortieren.

### B7 · §3a-Frist-Pill kann nie erscheinen
`StatusBand` (Z. 1869) sucht `frist_typ === "gerichtlich"`, das To-Do-Formular vergibt aber `"gericht"` (Z. 1384). Wert-Mismatch → Pill zeigt sich für manuell angelegte To-Dos nie.

### B8 · Doppelte Betreff-Anzeige Rechtsschutz
`RechtsschutzKlappkachel` übergibt `zeigeBetreff` **und** `zeigeAktenzeichen` → `betreff1` wird zweimal gerendert (als Betreffzeile und als Mono-Aktenzeichen).

## B — Redundante Requests / Berechnungen

- `/ramicro/akte/mandant-checks` wird pro Aktenöffnung **3×** gerufen: AkteDetailView (`raInfo`), UebersichtSection (`ibanCheck`), BeteiligterKachel „Mandant" (eigener `ibanCheck`).
- `dringlichkeit()`-Ampellogik ist **3×** kopiert (TodoSection, TodoKachelKompakt, TodoWvSpalten).
- Die posMap-Aggregation (manuell kumulativ / PDF letzter gewinnt, wdm-Remap) existiert **2×** leicht unterschiedlich (RegulierungsTabelle Z. 930ff mit Remap `sonstiges_wdm_X → extra_wdm_ssX`, Hauptkomponente Z. 2277ff ohne Remap mit Fallback-Lookup) — Wartungsfalle.
- To-Dos werden in UebersichtSection geladen und an TodoWvSpalten gereicht — TodoSection (Klage-Tab) lädt separat nochmal. Vertretbar, aber erwähnenswert.

## C — Kosmetik / Kleinigkeiten

- `RechtsschutzKlappkachel` Z. 61: Chevron `⌄⌄` doppelt (Tippfehler).
- Tab-Leiste: „⚖ Klage" und „⚖️ Gebühren" nahezu identisches Icon; Status als Emoji (✅/⚠️) neben Emoji-Icons wirkt unruhig.
- Action-Button-Zeile im Header hat `padding: 6px 1.75rem 8px` **innerhalb** des bereits mit 1.75rem gepolsterten Containers → Buttons sind gegenüber AZ und Tabs doppelt eingerückt.
- FinanzBand Z. 1971: `{anzahlSchreiben === 1 ? "Schreiben" : "Schreiben"}` — Ternary ohne Wirkung.
- `akte.hq || 100`: HQ = 0 würde als 100 % gerechnet (Randfall).
