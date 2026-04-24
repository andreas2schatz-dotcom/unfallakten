# Design: Übersicht-Tab Redesign
**Datum:** 2026-04-24  
**Status:** Approved  
**Scope:** `UebersichtSection.jsx` + `wiedervorlage_routes.py`

---

## Ziel

Zwei Verbesserungen am Übersicht-Tab der Aktendetailansicht:

1. **Alle Beteiligten-Kacheln ausklappbar** — nicht nur Rechtsschutz (wie bisher), sondern auch Mandant, Gegner, Behörden/Gerichte und Weitere Beteiligte. Zustand wird per Aktenzeichen im localStorage gespeichert.
2. **Wiedervorlagen in die To-Do-Kachel integriert** — zweispaltiges Layout: links offene Todos, rechts fällige Wiedervorlagen zur aktuellen Akte (max. 3, mit Verweis auf WVL-Tab für alle).

---

## Feature 1: Kollabierbare Beteiligten-Kacheln

### Komponente: `BeteiligterKachel`

Die bestehende `BeteiligterKachel`-Komponente erhält einen neuen optionalen Prop `ausklappbar` (default: `false`). Wenn gesetzt, wird der Kachel-Header zu einem Button mit Pfeil-Indikator (▲/▼). Klick togglet den Body-Inhalt.

**Props:**
- `ausklappbar?: boolean` — aktiviert das Collapse-Verhalten
- `standardOffen?: boolean` — Startzustand, wenn kein localStorage-Eintrag vorliegt (default: `true`)
- `localStorageKey?: string` — Key für Persistenz (z. B. `"akte-kachel-gegner-285/26"`)

**Verhalten:**
- Standardmäßig alle **aufgeklappt** (es sei denn, localStorage enthält `false` für den Key)
- Zustand wird sofort bei Toggle in localStorage geschrieben
- Key-Format: `uebersicht-kachel-<rolle>-<az>` (z. B. `uebersicht-kachel-gegner-285/26`)
- Wenn `ausklappbar=false` (bisheriges Verhalten): kein Toggle, kein Pfeil

### Aufrufe in `RaMicroAkteUebersicht`

Alle vier Kacheln werden mit `ausklappbar={true}` und passendem `localStorageKey` aufgerufen:

| Kachel | Rolle-Key | Standard |
|---|---|---|
| Mandant | `mandant` | aufgeklappt |
| Gegner | `gegner` | aufgeklappt |
| Behörden/Gerichte | `behoerde` | aufgeklappt |
| Weitere Beteiligte | `weitere` | aufgeklappt |

`EigeneVersicherungMini` und `RechtsschutzKlappkachel` bleiben unverändert.

---

## Feature 2: Wiedervorlagen in der To-Do-Kachel

### Backend: neuer Filter-Parameter

`GET /wiedervorlage/?az=<aktenzeichen>`

Der bestehende `liste_wiedervorlagen`-Endpunkt erhält einen optionalen Query-Parameter `az`. Wenn übergeben, wird `hole_faellige_wiedervorlagen()` nach dem Aktenzeichen gefiltert (SQL: `WHERE aktenzeichen = :az`). Ohne `az` verhält sich der Endpunkt wie bisher (alle Akten).

Die Funktion `hole_faellige_wiedervorlagen()` in `backend/ramicro/wiedervorlage_service.py` bekommt den neuen optionalen Parameter `aktenzeichen=None`. Der SQL-Filter lautet: `AND a.sAktenNummer = %(az)s` (Spalte in `tblAkten`).

### Frontend: `TodoKachelKompakt` → umgebaut

Die Komponente `TodoKachelKompakt` wird zu einer zweispaltigen Kachel:

**Layout:**
```
┌────────────────────────────────────────────────────────┐
│ 📋 To-Dos  [2 offen]          📅 Wiedervorlagen  [1] │
├──────────────────────────┬─────────────────────────────┤
│ ● Vollmacht anfordern    │ Stellungnahme Gegner?        │
│   fällig 25.04.          │ fällig 24.04.2026            │
│ ● Gutachten beauftragen  │ STA anfordern                │
│   fällig 28.04.          │                              │
│                          │ → Alle im WVL-Tab            │
└──────────────────────────┴─────────────────────────────┘
```

**Daten:**
- Todos: wie bisher via `apiTodos.liste(az)` — max. 4 offene angezeigt
- Wiedervorlagen: neuer API-Call `GET /wiedervorlage/?az=<az_roh>` — max. 3 angezeigt
- `az_roh` = Aktenzeichen im RA-Micro-Format (z. B. `285/26TB`)
- Beide Calls parallel via `Promise.all`

**Wiedervorlage-Eintrag zeigt:**
- `grund` (Betreff der WV, z. B. „Stellungnahme Gegner?")
- `datum` (Fälligkeitsdatum)
- Wenn kein Eintrag: „Keine fälligen Wiedervorlagen"
- Wenn keine RA-Micro-Verbindung: Spalte stumm ausblenden (kein Fehler anzeigen)

**Umbenennung:** Die Komponente wird intern zu `TodoUndWiedervorlageKachel` umbenannt (Export-Name `TodoKachelKompakt` bleibt für Kompatibilität).

---

## Nicht im Scope

- Das globale `WiedervorlageView.jsx` (WVL-Tab) bleibt unverändert
- STA-Generierung direkt aus der Kachel heraus — nur Anzeige, kein Button
- Wiedervorlage-Kachel an anderer Stelle (z. B. direkt unter Beteiligten) — bewusst abgelehnt
- `TodoSection` (die große To-Do-Verwaltung in AkteDetailView) bleibt unverändert

---

## Dateien mit Änderungen

| Datei | Art |
|---|---|
| `frontend/src/sections/UebersichtSection.jsx` | Hauptarbeit: `BeteiligterKachel` + `TodoKachelKompakt` |
| `backend/routers/wiedervorlage_routes.py` | Neuer `az`-Parameter in `liste_wiedervorlagen()` |
| `backend/ramicro/wiedervorlage_service.py` | `hole_faellige_wiedervorlagen()` bekommt `aktenzeichen`-Filter |
