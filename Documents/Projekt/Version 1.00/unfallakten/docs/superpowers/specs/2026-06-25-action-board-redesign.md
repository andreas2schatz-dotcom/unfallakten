# Action Board Redesign — Design-Spezifikation

**Datum:** 2026-06-25  
**Status:** Genehmigt  
**Ersetzt:** `ActionBoardView.jsx` (3-Spalten-Layout, v56)

---

## Ziel

Das Action Board ist die Startseite des Systems. Es soll dem Anwalt beim Tagesstart sofort zeigen, was heute zu tun ist — ohne Scrollen, ohne Suchen. Das bisherige 3-Spalten-Layout (Fristen / Handlungen / Nachrichten) wird durch ein priorisiertes 2×2-Kachel-Layout ersetzt.

---

## Layout: 2×2 Kacheln

```
┌─────────────────────┬─────────────────────┐
│  📅 Termine          │  ⏰ Fristen          │
│  (heute + morgen)   │  (überfällig+14T)   │
├─────────────────────┼─────────────────────┤
│  🔁 Wiedervorlagen  │  ✉ Posteingang      │
│  (überfällig+heute) │  (nach Postfach)    │
└─────────────────────┴─────────────────────┘
```

Alle vier Kacheln laden parallel (`Promise.allSettled`). Klick auf jeden Eintrag öffnet direkt die Akten-Detailansicht.

---

## Kachel 1 — Termine (oben links)

**Datenquelle:** `tblAktenWiedervorlagen` (RA-MICRO), gefiltert auf Grundcodes 58, 60, 9  
- Code 58 = Verhandlungstermin  
- Code 60 = Anhörungstermin  
- Code 9 = Entscheidung/Gericht  

**Zeitfenster:** Nur heute (`dtWiedervorlage = CAST(GETDATE() AS DATE)`) und morgen (`+1T`)

**Darstellung:**
- Zwischenüberschriften „Heute" und „Morgen"
- Uhrzeit rechts prominent (aus `sBemerkung`-Freitext per Regex extrahiert, z.B. „10:00 Uhr"; falls keine Uhrzeit erkennbar: nur Datum anzeigen)
- Heutige Termine: volle Helligkeit, lila Border (`#7c3aed`)
- Morgige Termine: leicht abgedimmt (`opacity: 0.85`), dunklere Border
- Lila Farbschema (Badge, Border, Titel)

**Leer-Zustand:** „Heute keine Termine" — grüne Bestätigung

**Backend-Endpoint:** `GET /dashboard/termine-heute` (neu)

---

## Kachel 2 — Fristen (oben rechts)

**Datenquelle:** `tblAktenWiedervorlagen` (RA-MICRO), gefiltert auf Grundcodes 21, 22, 46, 75  
- Code 21 = Klage  
- Code 22 = Urteil  
- Code 46 = Berufung  
- Code 75 = Fristablauf  

**Zeitfenster:** Überfällig (alle) + heute + bis +14 Tage

**Darstellung — Abschnitt „Handlungsbedarf" (Rot):**
- Überfällige Fristen: roter Hintergrund (`#3b1c0c`), rote Border (`#dc2626`), Badge `−XT`
- **Heute fällige Fristen: ebenfalls Rot** — gleiche Darstellung wie überfällig, Badge `HEUTE`
- Begründung: Eine heute fällige Frist erfordert sofortiges Handeln, nicht nur Aufmerksamkeit

**Darstellung — Abschnitt „Demnächst" (Grau):**
- +1T bis +14T: gedimmter Hintergrund, graue Border, Text `+XT`
- Kein Amber/Orange: Ampelfarben-Logik entfällt, nur Rot (jetzt) vs. Grau (später)

**Backend-Endpoint:** `GET /dashboard/fristen` (ersetzt `/dashboard/ramicro-fristen`)

---

## Kachel 3 — Wiedervorlagen (unten links)

**Datenquelle:** `tblAktenWiedervorlagen` (RA-MICRO) für alle anderen Grundcodes (nicht 9, 21, 22, 46, 58, 60, 75) + lokale SQLite (`unfallakte`)

**Was wird angezeigt — drei Abschnitte:**

1. **Überfällig** (`dtWiedervorlage < heute`): roter Badge `−XT`
2. **Heute fällig** (`dtWiedervorlage = heute`): amber Badge `HEUTE`
3. **Keine Wiedervorlage gesetzt**: Akten aus lokaler DB ohne aktive WV in RA-MICRO — indigo Border, Hinweis „⚠ keine WV"

**Nicht angezeigt:** Zukünftige Wiedervorlagen (kein `+XT`)

**Limit:** Max. 15 Einträge gesamt; „+ X weitere" Link zu voller Wiedervorlagen-Liste

**Backend-Endpoint:** `GET /dashboard/wiedervorlagen` (ersetzt `/dashboard/action-items` partiell)

---

## Kachel 4 — Posteingang (unten rechts)

**Datenquelle:** `email_import_log` (SQLite), neueste zuerst

**Darstellung:**
- Tab-Leiste: `unfall@` | `termin@` | `bussgeld@` — mit Badge-Zähler je Postfach
- Aktiver Tab hervorgehoben (grün)
- Je E-Mail: Betreff, Absender/Akte, Uhrzeit
- Max. 10 Einträge im aktiven Tab
- „→ Alle E-Mails öffnen" navigiert zur `EmailImportView`

**Klick auf E-Mail:** Öffnet `EmailDetailView` direkt (wie bisher über `onOpenEmail`)

**Backend-Endpoint:** `GET /dashboard/nachrichten-neu` (bestehend, keine Änderung nötig)

---

## Farbschema je Kachel

| Kachel | Primärfarbe | Border/Badge | Hintergrund |
|---|---|---|---|
| Termine | Lila `#7c3aed` / `#a78bfa` | `#4c1d95` | `#1e1b4b` |
| Fristen | Orange `#fb923c` | `#7c2d12` | `#1c1917` |
| Wiedervorlagen | Blau `#60a5fa` | `#1e3a5f` | `#0c1929` |
| Posteingang | Grün `#4ade80` | `#14532d` | `#0a1f1a` |

Kritisch (überfällig + heute): `#dc2626` (Rot) in allen Kacheln.

---

## Neue Backend-Endpoints

### `GET /dashboard/termine-heute`
```json
[
  {
    "az": "1213/25AS",
    "mandant": "Müller, Hans",
    "kurzbezeichnung": "Müller ./. KRAVAG",
    "termin_art": "Verhandlungstermin",
    "termin_datum": "2026-06-25",
    "uhrzeit": "10:00",   // null wenn nicht aus sBemerkung extrahierbar
    "tage_bis": 0
  }
]
```
Filter: `iWiedervorlageGrund IN (9, 58, 60)` AND `dtWiedervorlage IN (heute, morgen)`

### `GET /dashboard/fristen`
```json
[
  {
    "az": "1456/25AS",
    "mandant": "Weber, Klaus",
    "kurzbezeichnung": "Weber ./. AXA",
    "frist_art": "Klage",
    "frist_datum": "2026-06-23",
    "tage_bis": -2
  }
]
```
Filter: `iWiedervorlageGrund IN (21, 22, 46, 75)` AND `dtWiedervorlage >= heute - unbegrenzt` AND `dtWiedervorlage <= heute + 14`

### `GET /dashboard/wiedervorlagen`
```json
[
  {
    "az": "1102/25AS",
    "mandant": "Richter, Eva",
    "kurzbezeichnung": "Richter ./. Zürich",
    "grund": "Sachstandsanfrage",
    "datum": "2026-06-22",
    "tage_bis": -3,
    "hat_wv": true
  },
  {
    "az": "0345/25TB",
    "mandant": "Neumann, Frank",
    "kurzbezeichnung": "Neumann ./. Generali",
    "grund": null,
    "datum": null,
    "tage_bis": null,
    "hat_wv": false
  }
]
```
Überfällige + heutige WV aus RA-MICRO UNION lokale Akten ohne WV.

---

## Komponenten-Struktur (Frontend)

```
ActionBoardView.jsx          ← Hauptkomponente (2×2 Grid, Datenladen)
  TermineKachel.jsx          ← Kachel oben links
  FristenKachel.jsx          ← Kachel oben rechts
  WiedervorlagenKachel.jsx   ← Kachel unten links
  PosteingangKachel.jsx      ← Kachel unten rechts (Tab-Leiste)
```

Jede Kachel erhält ihre Daten als Props und ist eigenständig renderbar. Gemeinsame Hilfsfunktion `tagesBadge(tage)` für die farbigen Badges.

---

## Abgrenzung zur alten Implementierung

| Alt | Neu |
|---|---|
| 3 Spalten gleichwertig | 2×2 nach Dringlichkeit |
| Fristen = RA-MICRO WV (alle Codes) | Fristen = nur Deadline-Codes (21,22,46,75) |
| Heute fällig = Amber | Heute fällig = Rot (Handlungsbedarf) |
| WV zeigt auch Zukünftige | WV nur überfällig + heute + ohne WV |
| Onboarding-Sektion in Spalte 2 | Onboarding entfällt aus Action Board |
| Termine nicht getrennt | Termine eigene Kachel (Codes 9,58,60) |

**Onboarding-Hub** (7 Kacheln für unvollständige Akten) bleibt als separater Tab in `UebersichtSection` erhalten — wird nicht im neuen Action Board angezeigt.

---

## Nicht im Scope

- Keine Änderung an `EmailDetailView`, `EmailImportView` oder E-Mail-Routing
- Keine neue Authentifizierung oder Schema-Migration
- Keine Änderung am Onboarding-Hub
