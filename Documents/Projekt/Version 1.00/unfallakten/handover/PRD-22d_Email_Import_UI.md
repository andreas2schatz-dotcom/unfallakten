# PRD-22d – E-Mail-Import UI (Drei-Bereiche + Smart-Inbox)
> Erstellt: 2026-04-03  
> Status: Bereit zur Implementierung  
> Abhängigkeiten: PRD-22c (Fragebogen-Import) ✅, E-Mail-Import Modul 7 ✅  

---

## Ziel

Die bestehende `EmailImportView.jsx` wird zu einer **Drei-Bereiche-Ansicht** umgebaut:

1. **unfall@** – vollständiger Workflow inkl. Smart-Inbox
2. **termin@** – Stub (Modul folgt)
3. **bussgeld@** – Stub (Modul folgt)

Der unfall@-Bereich erhält eine komplett neu strukturierte Inbox:
- **Aktionspflichtig-Block** (fixiert oben): nicht zugeordnete E-Mails + Fragebogen-Erstkontakte
- **E-Mail-Stream** (gefiltert + durchsuchbar): alle Eingangspost mit Filter-Chips und Zeitgruppierung
- **Akten-Ansicht** (Stub, umschaltbar): E-Mails gruppiert nach Akte — als zukünftige Erweiterung

---

## Datei-Struktur (nach Umbau)

```
frontend/src/views/
  EmailImportView.jsx              ← Tab-Shell + Bereich-Switcher (~80 Zeilen)
  email_import/
    UnfallEmailView.jsx            ← unfall@-Hauptview (neu, aus EmailImportView extrahiert)
    TerminEmailView.jsx            ← Stub
    BussgeldEmailView.jsx          ← Stub
    components/
      AktionspflichtigBlock.jsx    ← Aktionspflichtig-Sektion (oben fixiert)
      EmailStream.jsx              ← gefilterte, durchsuchbare E-Mail-Liste
      EmailStreamZeile.jsx         ← einzelne kompakte E-Mail-Zeile (eingeklappt)
      EmailKarte.jsx               ← bestehende aufgeklappte Detailkarte (refactored)
      FragebogenErstkontaktKarte.jsx ← Karte für fragebogen_erstkontakt-Einträge
      AktenAnsicht.jsx             ← Stub: E-Mails gruppiert nach Akte
```

> Bestehende Hilfskomponenten (ImapKonfigDialog, InAkteButton, RegulierungBestaetigenButton,
> AktionBadge, AnhangZeile) bleiben unverändert — nur verschoben nach email_import/components/.

---

## Bereich-Switcher (Tab-Leiste)

Drei Tabs oben in EmailImportView.jsx:

```
[● unfall@]  [termin@]  [bussgeld@]
```

- Aktiver Tab: navy-Unterstrich, Text bold
- Inaktive Tabs: grau, voller Text (keine Icons nötig)
- Verbindungsstatus-Indikator (● grün / ● rot) nur beim aktiven Tab der konfiguriert ist
- Kein eigener Routing-Eintrag — bleibt client-seitiger State wie bisher

---

## Tab 1: unfall@

### Layout-Überblick

```
┌─────────────────────────────────────────────────────────┐
│  [● unfall@]  [termin@]  [bussgeld@]                    │
├─────────────────────────────────────────────────────────┤
│  [Import starten]  ● verbunden  [⚙ Konfiguration]       │
│  KPI-Leiste: Gesamt | Zugeordnet | Nicht zugeordnet     │
│              | Fragebogen neu | Anhänge                 │
├─────────────────────────────────────────────────────────┤
│  AKTIONSPFLICHTIG (n)                          [▼ / ▲]  │
│  ┌──────────────────────┬────────────────────────────┐  │
│  │ Nicht zugeordnet (n) │ Fragebogen-Erstkontakte (n)│  │
│  │ [Karten horizontal   │ [Karten horizontal         │  │
│  │  scrollbar]          │  scrollbar]                │  │
│  └──────────────────────┴────────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│  🔍 [Suchfeld]                  [Stream ●] [Akten ○]    │
│  [Alle] [Versicherung] [Gutachter] [Gericht] [Sonstiges]│
├─────────────────────────────────────────────────────────┤
│  ── Heute (4) ─────────────────────────────────────── │ │
│  ▸  HUK-Coburg     31/21  Regulierung: Kürzung ...  PDF │
│  ▸  GTÜ Gutachten  47/24  Ergänzungsgutachten ...   PDF │
│  ── Gestern (7) ───────────────────────────────────── │ │
│  ▸  ...                                                 │
└─────────────────────────────────────────────────────────┘
```

---

### KPI-Leiste (erweitert)

Bestehende KPIs + neuer Eintrag für Fragebogen:

| Feld | Quelle | Farbe |
|---|---|---|
| Gesamt | `statistik.gesamt` | navy |
| Zugeordnet | `statistik.zugeordnet` | grün |
| Nicht zugeordnet | `statistik.nicht_zugeordnet` | amber |
| Fragebogen neu | `fragebogenStats.neu` | gold (neu) |
| Anhänge | `statistik.anhaenge` | blau |

`fragebogenStats` kommt aus `GET /email/fragebogen-erstkontakt?stats=1`.

---

### Aktionspflichtig-Block

**Zwei Sub-Spalten** nebeneinander, beide horizontal scrollbar wenn viele Einträge:

#### Sub-Spalte links: „Nicht zugeordnet"
- Zeigt alle Log-Einträge mit `status = 'nicht_zugeordnet'` **und** `email_typ != 'fragebogen'`
- Entspricht dem bestehenden „Nicht zugeordnet"-Content der alten View
- Jede Karte: Absender, Betreff, Datum, [Akte zuordnen]-Button

#### Sub-Spalte rechts: „Fragebogen-Erstkontakte"
- Zeigt alle Einträge aus `fragebogen_erstkontakt` WHERE `status = 'neu'`
- Eigene `FragebogenErstkontaktKarte`-Komponente:
  ```
  ┌────────────────────────────────────────────┐
  │ Max Mustermann  max@example.de    ● neu    │
  │ Schadentag: 15.03.2026 · KFZ: OF-AB 123   │
  │ Empfangen: 03.04.2026 14:23                │
  │ [Als bearbeitet]  [Akte anlegen ⚠ PRD-22d]│
  └────────────────────────────────────────────┘
  ```
- „Akte anlegen"-Button: disabled, Tooltip: „Akte-Anlage folgt in Modul PRD-22d"
- „Als bearbeitet": PATCH → `status = 'bearbeitet'`, Karte verschwindet aus Block

Wenn beide Sub-Spalten leer: Block zeigt „Kein Handlungsbedarf ✓" und ist eingeklappt.

---

### E-Mail-Stream (Stream-Ansicht)

**Standardansicht** nach dem Aktionspflichtig-Block.

#### Filter-Chips

```
[Alle ●]  [Versicherung]  [Gutachter]  [Gericht]  [Sonstiges]
```

- Mappt auf `absender_kategorie` im Log
- Mehrfachauswahl möglich
- „Alle" deaktiviert die anderen Chips
- Aktiver Chip: navy-Hintergrund, weiße Schrift

#### Suchfeld

- Freitext-Suche über: Betreff, Absender, AZ (client-seitig über geladene Daten)
- Debounced (300ms)

#### Zeitgruppierung

```
── Heute (n) ────────────────────────────────────────
── Gestern (n) ──────────────────────────────────────
── Diese Woche (n) ──────────────────────────────────
── Älter (n) ────────────────────────────────────────
```

Gruppenheader klappbar. Standardmäßig alle ausgeklappt.

#### EmailStreamZeile (eingeklappt)

Eine Zeile pro E-Mail, ~40px hoch:

```
▸  [Absender-Badge]  [AZ-Badge]  Betreff-Kurztext …  [Typ-Chip]  [Datum]  [📎 n]
```

| Element | Inhalt |
|---|---|
| ▸ | Expand-Pfeil, dreht sich beim Aufklappen |
| Absender-Badge | Name oder Domain, farbig nach Kategorie (Versicherung=blau, Gutachter=lila, etc.) |
| AZ-Badge | `akte_id` wenn vorhanden, grau wenn nicht |
| Betreff | Gekürzt auf ~60 Zeichen |
| Typ-Chip | `email_typ` (Regulierung, Sachstandsanfrage, etc.) — nur wenn gesetzt |
| Datum | Heute: HH:MM, sonst: DD.MM. |
| 📎 n | Anzahl Anhänge, nur wenn > 0 |

Klick auf Zeile → klappt zur bestehenden `EmailKarte` auf (gleicher Content wie heute).

---

### Akten-Ansicht (Stub)

Umschalter oben rechts im Stream-Bereich: `[Stream ●]  [Akten ○]`

Bei Auswahl „Akten": Stub-Komponente `AktenAnsicht.jsx`:

```
┌──────────────────────────────────────────────┐
│  Akten-Ansicht                               │
│  E-Mails gruppiert nach Akte                 │
│                                              │
│  Diese Ansicht ist in Vorbereitung.          │
│  Alle E-Mails sind in der Stream-Ansicht     │
│  verfügbar.                                  │
│                                              │
│  [Zurück zur Stream-Ansicht]                 │
└──────────────────────────────────────────────┘
```

Kein API-Call, kein State. Nur Erklärungstext + Button zurück.

---

## Tab 2: termin@ (Stub)

Datei: `TerminEmailView.jsx`

```
┌──────────────────────────────────────────────┐
│  termin@anwalt-offenbach.de                  │
│                                              │
│  ⚙  Terminanfragen-Workflow                  │
│                                              │
│  Eingehende Terminanfragen werden hier       │
│  verwaltet und mit dem Kalender synchroni-   │
│  siert, sobald das Modul implementiert ist.  │
│                                              │
│  Geplante Funktionen:                        │
│  · Automatische Bestätigung / Ablehnung      │
│  · Sync mit RA-MICRO Kalender                │
│  · Erinnerungs-E-Mail an Mandant             │
└──────────────────────────────────────────────┘
```

---

## Tab 3: bussgeld@ (Stub)

Datei: `BussgeldEmailView.jsx`

```
┌──────────────────────────────────────────────┐
│  bussgeld@anwalt-offenbach.de                │
│                                              │
│  ⚙  Bußgeld-Workflow                         │
│                                              │
│  Eingehende Bußgeldbescheide und Anfragen    │
│  werden hier bearbeitet, sobald das Modul    │
│  implementiert ist.                          │
│                                              │
│  Geplante Funktionen:                        │
│  · Fristberechnung (Einspruch 2 Wochen)      │
│  · Mandant-Zuordnung                         │
│  · Vorgangs-Erstellung                       │
└──────────────────────────────────────────────┘
```

---

## Neue Backend-Endpoints

### GET `/email/fragebogen-erstkontakt`

Query-Parameter:
- `status` — `neu` | `bearbeitet` | (leer = alle)
- `stats` — `1` → gibt nur `{"neu": n, "bearbeitet": n}` zurück (für KPI)
- `limit` — Standard 50

Response (Liste):
```json
[
  {
    "id": 1,
    "empfangen_am": "2026-04-03T14:23:00",
    "absender_email": "max@example.de",
    "absender_name": "Max Mustermann",
    "mandant_name": "Mustermann",
    "mandant_email": "max@example.de",
    "kfz_kennzeichen": "OF-AB 123",
    "schadentag": "2026-03-15",
    "status": "neu"
  }
]
```

### PATCH `/email/fragebogen-erstkontakt/<id>/status`

Body: `{ "status": "bearbeitet" }`  
Response: `{ "ok": true }`

---

## Neue Frontend-API-Methoden

```javascript
emailImport.fragebogenErstkontakt(params)          // GET /email/fragebogen-erstkontakt
emailImport.fragebogenErstkontaktStatus(id, status) // PATCH /email/fragebogen-erstkontakt/<id>/status
```

---

## Session-Planung

| Session | Inhalt | Status |
|---|---|---|
| 1 | Tab-Shell + Bereich-Switcher, TerminEmailView-Stub, BussgeldEmailView-Stub | ⬜ |
| 2 | UnfallEmailView: Aktionspflichtig-Block + FragebogenErstkontaktKarte + Backend-Endpoints | ⬜ |
| 3 | UnfallEmailView: EmailStream + EmailStreamZeile + Filter-Chips + Suche + Zeitgruppierung | ⬜ |
| 4 | AktenAnsicht-Stub + Umschalter | ⬜ |
| 5 | Refactor: bestehende EmailKarte/ImapKonfigDialog in neue Ordnerstruktur verschieben | ⬜ |
| 6 | Test + Abnahme | ⬜ |

---

## Kritische Regeln

- ⛔ Bestehende EmailKarte-Logik (Regulierung bestätigen, In Akte importieren) bleibt unverändert
- ⛔ Kein neues Routing — bleibt client-seitiger State-Switch wie bisher
- ⛔ IMAP-Konfiguration bleibt nur für unfall@ sichtbar (termin@/bussgeld@ brauchen noch keine)
- ✅ Import-Button + Status nur im unfall@-Tab sichtbar
- ✅ Alle bestehenden API-Methoden weiter nutzbar (kein Breaking Change)
- ✅ Theme-Variablen aus `theme.js` verwenden, keine Hardcoded-Farben
