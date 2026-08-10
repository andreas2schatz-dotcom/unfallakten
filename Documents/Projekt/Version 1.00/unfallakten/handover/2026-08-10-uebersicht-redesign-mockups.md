# Redesign-Ideen: Übersicht-Tab / AkteDetailView (2026-08-10)

Grundlage: Review vom selben Tag (`2026-08-10-uebersicht-review-befunde.md`).
Noch **nicht umgesetzt** — Diskussionsgrundlage für RA Schatz.

## 1 · Das Kernproblem: Redundanz

Beim Öffnen einer Akte mit Übersicht-Tab steht dieselbe Information mehrfach untereinander:

| Information | Stellen heute |
|---|---|
| Geldsummen (Gefordert/Reguliert/Offen) | **5×**: Header-KPI, FinanzBand, PositionsDashboard, RegulierungsTabelle (default offen), Forderungshistorie |
| Positionsliste | **2×**: PositionsDashboard (Ereignismodell, neu) + RegulierungsTabelle (Alt-Logik) — mit teils abweichenden Zahlen |
| Checks (IBAN/Vollmacht/RSV) | **3×**: StatusBand-Pills, Mandanten-Kachel (RA-Micro-Stammdaten), OnboardingHub |
| Phase „Onboarding" | **2×**: PhasenStrip + OnboardingHub-Banner |
| Stammdaten (AZ, SB, KFZ, Kurzbez.) | **2×**: Navy-Header + RA-Micro-Akkordeon |

Der OnboardingHub kommt erschwerend dazu: Er erscheint wegen der kaputten Checks (Befund B2) fast immer, ganz oben, und drückt den eigentlichen Inhalt nach unten.

## 2 · Leitidee: „Eine Wahrheit pro Information"

Jede Information hat genau **einen** Ort:

- **Summen** → nur noch Header-KPI (aus derselben Backend-Quelle wie das PositionsDashboard, damit Header und Tabelle nie widersprechen).
- **Positionen** → nur noch PositionsDashboard. Die alte RegulierungsTabelle fliegt aus der Übersicht (bleibt im Regulierung-Tab, wo sie hingehört).
- **Checks** → nur noch StatusBand. Die Aktionen „IBAN anfordern / Vollmacht anfordern / generieren" wandern als Popover an die jeweilige Pill.
- **Onboarding** → kein Banner mehr, sondern Fächer-Element im PhasenStrip (s. Mockup B).
- **Stammdaten** → Header. Das RA-Micro-Akkordeon zeigt nur noch Beteiligten-Kacheln, nicht nochmal AZ/SB/KFZ.

## 3 · Mockup A — Übersicht-Tab neu (Empfehlung)

```
┌─ NAVY-HEADER ────────────────────────────────────────────────────────────────┐
│ 123/26  Müller ./. HUK          SB: AS · M: OF-AB 123 · G: F-XY 99           │
│                                        ┌──────────────────────────────────┐  │
│ [💬 Nachricht] [📤 STA] [+Todo] [Word] │ Gefordert  Reguliert  Offen      │  │
│                                        │ 12.480 €    9.100 €   3.380 €    │  │
│                                        └──────────────────────────────────┘  │
│ Übersicht │ Beteiligte │ Unfall │ Schaden │ Dokumente │ Regulierung │ …      │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│ ┌─ PHASEN + STATUS (eine schlanke Leiste) ─────────────────────────────────┐ │
│ │ ✓ Onboarding ▸│ ✓ Erstforderung │ ▶ REGULIERUNG │ ○ Stellungn. │ ○ Absch.│ │
│ │ ✓Vollmacht ✓IBAN ○RSV · HQ 75 % · Verjährung 31.12.2029                  │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│ ┌─ POSITIONEN (einzige Geld-Tabelle, aus Ereignismodell) ──────────────────┐ │
│ │ Reparatur (fiktiv)     gefordert 8.200 €  anerkannt 6.900 €  offen 1.300 │ │
│ │ Nutzungsausfall        gefordert 1.400 €  anerkannt 1.400 €  offen     0 │ │
│ │ …                                                        [→ Regulierung] │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│ ┌─ TO-DOS ────────────────────┐  ┌─ WIEDERVORLAGEN ────────────────────────┐ │
│ │ ● Stellungnahme Kürzung 14.8│  │ 📅 Frist §3a — 20.08.                   │ │
│ │ ● IBAN nachfassen           │  │ 📅 WV Sachstand — 01.09.                │ │
│ └─────────────────────────────┘  └─────────────────────────────────────────┘ │
│                                                                              │
│ ▸ RA-Micro Beteiligte   ▸ Chronik   ▸ Notizen        (3 Akkordeons statt 5) │
└──────────────────────────────────────────────────────────────────────────────┘
```

Was verschwindet gegenüber heute: OnboardingHub-Banner, FinanzBand, RegulierungsTabelle-Karte, Forderungshistorie-Akkordeon (→ Regulierung-Tab). Was zusammenrückt: PhasenStrip + StatusBand werden **eine** Leiste.

## 4 · Mockup B — Onboarding als Fächer

Kein Banner mehr. Die Phase „Onboarding" im PhasenStrip trägt einen Fortschritts-Chip
und klappt bei Klick als Fächer/Popover auf:

```
│ ▶ ONBOARDING 3/6 ▾ │ ○ Erstforderung │ ○ Regulierung │ …
        │
        ▼  (Klick öffnet Fächer unterhalb der Leiste)
   ┌───────────────────────────────────────────────┐
   │ ✓ Mandant             ✓ Gegner                │
   │ ✓ GHPV                ○ Unfalldetails    [→]  │
   │ ○ Schadenspositionen  [→]                     │
   │ ○ Vollmacht           [✉ anfordern] [↓ PDF]   │
   └───────────────────────────────────────────────┘
```

Verhalten:
- Chip nur sichtbar, solange die Akte in Phase Onboarding ist — **verschwindet automatisch** ab Erstforderung (kein manuelles Wegklicken + kein localStorage-Vergessen mehr).
- Jede Zeile springt in den passenden Tab; Vollmacht-Zeile bekommt die Anfordern/Generieren-Aktionen aus der Mandanten-Kachel.
- Voraussetzung: die Checks aus Befund B2 müssen auf echte Datenquellen umgestellt werden (mandant-checks-Endpoint statt Phantomfelder), sonst zeigt auch der Fächer Dauer-Orange.

## 5 · Mockup C — Alternative: Zwei-Spalten-Cockpit (größerer Umbau)

Falls mehr gewollt ist als Aufräumen: Übersicht als echtes Cockpit ohne Akkordeons.

```
┌────────────────────────────────┬──────────────────────┐
│ PHASEN-LEISTE                  │  CHECKS              │
│                                │  ✓IBAN ✓VM ○RSV      │
│ POSITIONEN                     ├──────────────────────┤
│ (Ereignismodell-Tabelle,       │  TO-DOS (5)          │
│  volle Breite der Spalte)      │  WIEDERVORLAGEN (2)  │
│                                ├──────────────────────┤
│ CHRONIK (letzte 5 + „alle")    │  NOTIZEN             │
│                                │  KONTAKT MANDANT     │
│                                │  ☎ / ✉ / 💬          │
└────────────────────────────────┴──────────────────────┘
```

Vorteil: alles auf einen Blick, keine versteckten Inhalte. Nachteil: größerer Umbau, auf schmalen Fenstern (Splitscreen mit RA-MICRO) muss die rechte Spalte nach unten fallen.

## 6 · Tab-Leiste / Überschriften der Sections

- Icons vereinheitlichen: „⚖ Klage" vs. „⚖️ Gebühren" trennen (z. B. 💰 Gebühren) — oder Emojis ganz durch die vorhandenen `Ic.*`-Icons ersetzen.
- Status nicht als zweites Emoji (✅/⚠️) hinter dem Label, sondern als kleiner farbiger Punkt — ruhigeres Bild, gleiche Information.
- Zählerformat vereinheitlichen: heute „Dokumente (12) 🔴3" — besser einheitliche Badge `Dokumente 12 ●3 neu`.
- Section-interne Überschriften: „Forderung vs. Regulierung – Positionsübersicht" (Übersicht) und „Schadenpositionen" (Schaden-Tab) und PositionsDashboard konkurrieren begrifflich. Vorschlag: einheitlich **„Positionen"** mit Zusatz der Quelle, und pro Tab nur eine Positionsdarstellung.

## 7 · Empfohlene Reihenfolge

1. **Bugfix-Session** (Befunde B1–B8, v. a. Crash B1 und OnboardingHub-Checks B2) — unabhängig vom Redesign.
2. **Aufräum-Session**: toter Code raus, FinanzBand + RegulierungsTabelle aus der Übersicht, Summen-Quelle vereinheitlichen (Mockup A).
3. **Onboarding-Fächer** (Mockup B) — ersetzt den Hub.
4. Optional später: Cockpit-Layout (Mockup C), falls A/B nicht reichen.
