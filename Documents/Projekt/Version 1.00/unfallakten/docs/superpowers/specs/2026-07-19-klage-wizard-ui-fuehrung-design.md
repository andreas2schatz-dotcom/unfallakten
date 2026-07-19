# Design: Klage-Wizard — UI-Führung

> Stand: 2026-07-19 · Freigegeben von RA Schatz (Brainstorming-Session)
> Paket 2 von 4 der Klage-Wizard-Verbesserungsrunde (1: Entwurf speichern, 3: Gesamtvorschau, 4: Standardtexte pflegbar)
> Scope-Session: nur Design, keine Umsetzung in dieser Session.

## Problem

Drei Führungslücken im 10-Step-Wizard (`frontend/src/sections/KlageWizard.jsx`, 2813 Z.):

1. Der Fortschrittsbalken zeigt nur erreichbar/nicht erreichbar — Warnungen (Text veraltet, Platzhalter, fehlender Vertreter) werden erst in Schritt 6 bzw. 10 sichtbar.
2. Schritt 7 (Würdigung) ist der dichteste Block des Wizards: Haftungsquote, Einwände-Panel (~200 Z., Kürzungen je Position, Textgenerator) und Gesamt-Textarea auf einem Bildschirm.
3. Bei manuell bearbeiteten Texten sieht man nicht, **was** sich gegenüber dem Automatik-Text unterscheidet — nur die „⚠ Text veraltet"-Badge und Zurücksetzen-Knöpfe.

## Entscheidungen (RA Schatz, 2026-07-19)

1. Einwände werden ein **eigener Zwischenschritt** (Wizard wächst auf 11 Schritte) — nicht einklappbar, nicht nur Layout.
2. Diff-Darstellung als **Markierungen im Text** (grün/rot inline), nicht nebeneinander.
3. Ohne erfasste Kürzungen **bleibt der Einwände-Schritt sichtbar** (Schnell-Durchlauf, stabile Nummerierung) — kein automatisches Überspringen.

## Baustein 1: Status-Symbole im Fortschrittsbalken

Jeder Schritt zeigt einen Zustand:

- **●** aktueller Schritt
- **✓** erledigt: besucht (≤ `maxStep`) und keine Warnung
- **⚠** Warnung (ersetzt ✓): Bedingung des Schritts verletzt oder Folgeproblem
- ausgegraut: noch nicht erreichbar (wie bisher über `kannSpringen`)

Warnquellen (alles bereits heute berechnet, nur früher sichtbar gemacht):

| Schritt | Warnung |
|---|---|
| 1 | Gericht nicht bestätigt |
| 2 | Beklagte-Firma ohne Vertreter (heutige Sperre aus Schritt 10/11) |
| 5 | keine Position angehakt |
| 6 | Antragstext veraltet (`antraegeVeraltet`) oder Platzhalter noch im Text |

Tooltip am Symbol erklärt die Warnung („Antragstext veraltet — in Schritt 6 neu generieren"). Klick-/Sprungverhalten (`kannSpringen`, kumulativ) bleibt unverändert; die Symbole sind reine Anzeige, keine neuen Sperren.

## Baustein 2: Einwände als eigener Schritt (10 → 11 Schritte)

Neue Schrittfolge: 1 Gericht · 2 Rubrum · 3 Aktivlegitimation · 4 Unfall · 5 Schaden · 6 Anträge · **7 Würdigung · 8 Einwände** · 9 Verzug · 10 Gebühren · 11 Generieren.

- **Schritt 7 „Würdigung":** Haftungsquote (Radio gegnerisch/eigen), Haftungsbegründung, Vorschau des Grundhaftungs-Textes.
- **Schritt 8 „Einwände":** bisheriges `EinwandePanel` (Kürzungen je Position, Varianten, „Text übernehmen") **plus** die editierbare Gesamt-Textansicht der rechtlichen Würdigung (`wizardRwText`-DokumentCard) — erst nach den Einwänden ist dieser Text vollständig, also wird er hier finalisiert. Freigabe-Begründung: RA Schatz 2026-07-19 („Schritt 7 Quote/Begründung, Schritt 8 Einwände + fertiger Würdigungstext — passt").
- **Ohne erfasste Kürzungen:** Schritt 8 zeigt „Keine Kürzungen der Versicherung erfasst" + Weiter-Knopf. Position und Nummerierung sind in jeder Akte identisch.

Folgeänderungen: `STEPS`-Array, `schrittBlockiert`/`kannWeiter`/`kannSpringen`-Indizes, Texte „wird in Schritt 9 ergänzt" → neue Nummern prüfen, Golden-/Vitest-Anpassungen. **Paket-1-Kopplung:** `format_version` des Wizard-Entwurfs wird beim Umbau hochgezählt (gespeicherte `wizardStep`-Nummern älterer Entwürfe passen sonst nicht mehr).

## Baustein 3: Änderungs-Gegenüberstellung (Inline-Diff)

- An jeder editierbaren Text-Vorschau mit Manuell-Flag (Sachverhalt/Schritt 3, Unfall/4, Anträge/6, Würdigung/8, Verzug/9, Gebühren/10): Umschalter **„Änderungen anzeigen"**.
- Darstellung: wortweiser Vergleich manuelle Fassung vs. aktueller Automatik-Text — Ergänzungen grün, Streichungen rot durchgestrichen, im Stil eines korrigierten Schriftsatzes. Reine Anzeige (read-only); bearbeitet wird im normalen Textfeld.
- Die „⚠ Text veraltet"-Badge verlinkt dieselbe Ansicht: vor „↻ Neu generieren / Behalten" zeigt sie, was man verlieren bzw. bekommen würde.
- Umsetzung als **reine Diff-Funktion** (wortweise, testbar ohne UI); keine externe Bibliothek nötig, einfacher LCS auf Wortebene reicht bei Texten dieser Länge.

## Tests (bei Umsetzung)

- Diff-Funktion: Ergänzung/Streichung/Ersetzung/identisch/leer, Umlaute, Zeilenumbrüche.
- Status-Logik als reine Funktion `schrittStatus(nr, ctx)` → ✓/⚠/●/gesperrt je Warnquelle.
- Schrittfolge: `kannSpringen`/`kannWeiter` mit 11 Schritten, Einwände-Schnell-Durchlauf ohne Kürzungen, Manuell-Flag/`AntraegeSync`-Verhalten unverändert.
- Vitest: Tooltip-Inhalte, Umschalter, Badge-Diff-Ansicht.

## Bewusst nicht im Scope

- Keine neuen Sperren (Symbole sind Anzeige), kein Überspringen des Einwände-Schritts, kein Nebeneinander-Diff, keine Diff-Bearbeitung (Annehmen/Ablehnen einzelner Wörter).
