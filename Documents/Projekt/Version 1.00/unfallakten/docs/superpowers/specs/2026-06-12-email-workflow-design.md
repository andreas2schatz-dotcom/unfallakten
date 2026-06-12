# E-Mail-Workflow Redesign

**Datum:** 2026-06-12  
**Status:** Bereit zur Implementierung  
**Projekt:** Unfallakten-Verwaltungssystem · Koch, Schatz & Kollegen

---

## Problem

Der E-Mail-Workflow ist aktuell auf vier inkonsistente Ansichten verteilt:

1. **Action Dashboard** → Klick auf E-Mail öffnet nur die Akte-Übersicht, nicht die E-Mail selbst
2. **DokumenteSection** → Importierte `.eml`-Dateien sind sichtbar, aber nicht anklickbar (kein Viewer)
3. **E-Mail-Import-Stream** → E-Mails kollabierbar, aber Anhänge öffnen neuen Browser-Tab
4. **Kein durchgehender Pfad** → Import → Zuordnen → Vorschau → Akte sind vier manuelle Sprünge

---

## Entscheidungen (bestätigt)

| Thema | Entscheidung |
|---|---|
| Navigationsmodell | **A** — Eigene E-Mail-Detail-Seite im E-Mail-Import-Bereich |
| Detail-Layout | **B** — Zweispaltig: Links Metadaten/Aktionen, Rechts Vorschau-Panel |
| Vorschau-Panel | E-Mail-Text (Standard) → PDF-Vorschau bei Klick auf Anhang |
| DokumenteSection | **B** — E-Mails klappbar direkt in der Liste, kein Seitenwechsel |
| Anhang-Import | Manuell, aber als prominenter grüner Vorschlag (kein versteckter Button) |
| Auto-Import | Nein — Fehlerkorrektur muss möglich bleiben |

---

## Design

### 1. E-Mail-Detail-Seite (`EmailDetailView.jsx`)

Neue Komponente, die im E-Mail-Import-Bereich gerendert wird wenn eine E-Mail geöffnet wird.

**Navigation:**
- `← Zurück zum Stream` — immer sichtbar, bringt zur E-Mail-Import-Stream-Ansicht
- `📁 Akte [AZ] öffnen` — nur sichtbar wenn E-Mail einer Akte zugeordnet ist; öffnet die AkteDetailView (kein Zurück-Button, sondern ein Shortcut-Link)
- Wird von zwei Stellen aus aufgerufen: Stream-Karte und Action Dashboard. DokumenteSection nutzt Inline-Expand und öffnet die Detail-Seite nicht.

**Linke Spalte (fix ~380px):**
```
┌─────────────────────────────────┐
│ Betreff (fett, groß)            │
├─────────────────────────────────┤
│ Von    rv-info@ruv.de           │
│ Akte   31/21 ✓ Zugeordnet       │
│ Datum  12.06.2026 · 14:32       │
│ Typ    Regulierungsschreiben    │
├─────────────────────────────────┤
│ ANHÄNGE                         │
│ 📎 Regulierung.pdf  [▶ Vorschau]│
│ 📎 Anlage.pdf       [▶ Vorschau]│
├─────────────────────────────────┤
│ 📥 In Akte 31/21 importieren?   │
│ 2 Anhänge + E-Mail-Text         │
│              [Jetzt importieren] │
└─────────────────────────────────┘
```

- Importvorschlag nur sichtbar wenn: Akte zugeordnet UND `in_akte_importiert = 0`
- Nach erfolgreichem Import: grünes Badge „✓ In Akte importiert · 14:35" statt Vorschlag-Box
- Wenn nicht zugeordnet: stattdessen Zuordnungs-Dropdown (wie im Stream)

**Rechte Spalte (flex, Vorschau-Panel):**
- **Standard:** E-Mail-Text (plain text, `white-space: pre-wrap`, scrollbar)
- **Nach Klick auf Anhang:** PDF-Vorschau inline (identisch zur bestehenden PDF-Vorschau in der E-Akte)
  - Header-Leiste im Panel: Dateiname + „Vollbild"-Link + „↓ Download"
  - Aktiver Anhang in der linken Liste hervorgehoben (blauer Rahmen)
  - Klick auf anderen Anhang tauscht Vorschau aus
  - Klick erneut auf aktiven Anhang → zurück zum E-Mail-Text

---

### 2. Navigation aus dem Stream

**EmailKarte.jsx** erhält einen „▶ E-Mail öffnen"-Button der `onOpenEmail(entry)` aufruft (neu).

`UnfallEmailView` verwaltet einen State `geöffneteEmail`:
- `null` → Stream-Ansicht (wie bisher)
- `entry` → EmailDetailView rendert sich statt des Streams

Zurück-Klick setzt `geöffneteEmail = null` → Stream wieder sichtbar, Position erhalten (kein Re-Fetch).

---

### 3. Navigation aus dem Action Dashboard

**ActionBoardView.jsx** — Nachrichten-Spalte:

Aktuell: Klick → `onOpenAkte(az)` → öffnet Akte-Übersicht.

Neu: Klick → navigiert zu E-Mail-Import (`active = "email-import"`) UND übergibt die Log-ID der E-Mail, damit `UnfallEmailView` direkt die Detail-Seite öffnet.

Technisch: `onOpenAkte` wird durch `onOpenEmail({ az, logId })` ergänzt. App.jsx setzt `active = "email-import"` und übergibt `initialEmailId` als Prop an `EmailImportView` → `UnfallEmailView`.

---

### 4. E-Mails in DokumenteSection (Inline-Expand)

**DokumenteSection.jsx** bekommt eine neue Gruppe „📧 E-Mails (N)" unterhalb der bestehenden Dokumentenliste.

Datenquelle: `GET /email/import/log?akte_id={az}` — gefiltert auf die aktuelle Akte.

**Aufbau pro E-Mail-Zeile:**
```
📧 R+V · Regulierung          12.06.2026 · 2 Anhänge    ▼
```
Klappt auf → zeigt inline:
```
  „Sehr geehrte Damen und Herren, wir beziehen uns…"
  📎 Regulierung.pdf  [Öffnen]
  📎 Anlage.pdf       [Öffnen]
```

- „Öffnen" bei Anhängen: öffnet PDF im Browser-Tab (wie bisher via `/anhang/<index>`)
- Kein Seitenwechsel, kein Navigieren in den E-Mail-Import-Bereich
- Gruppe nur sichtbar wenn mindestens eine E-Mail mit `akte_id = az` in `email_import_log` vorhanden

---

### 5. Backend-Änderungen

#### 5a. `dateityp`-Enum erweitern
Die `dokumente`-Tabelle hat `dateityp CHECK(... IN ('pdf','docx','jpg','png'))`. `.eml`-Dateien werden aktuell mit `dateityp='docx'` als Workaround gespeichert.

**Fix:** `.eml`-Dateien werden mit `dateityp='sonstiges'` und `dokumentenklasse='email'` gespeichert. Kein Tabellen-Rebuild nötig. `import_service.py` und `importiere_in_akte()` werden entsprechend angepasst. DokumenteSection identifiziert E-Mails über `dokumentenklasse='email'`.

#### 5b. Kein neuer Endpunkt nötig
Bestehende Endpunkte sind ausreichend:
- `GET /email/import/log?akte_id={az}` — für DokumenteSection
- `GET /email/import/log/{id}/meta` — für Detail-Seite (Anhang-Metadaten + Body-Text)
- `GET /email/import/log/{id}/anhang/{index}` — für Anhang-Vorschau/Download
- `POST /email/import/log/{id}/in-akte` — für Import-Vorschlag

#### 5c. `api.js` — fehlende Funktion ergänzen
```javascript
emailImport.inAkte = (logId, erzwingen = false) =>
  request(`/email/import/log/${logId}/in-akte`,
    { method: 'POST', body: JSON.stringify({ erzwingen }) });
```
`InAkteButton.jsx` soll diese Funktion statt direktem `request()` nutzen.

---

### 6. Nicht in Scope

- Automatischer E-Mail-Import (kein Intervall-Scheduler)
- TerminEmailView / BussgeldEmailView (bleiben Stubs)
- Regulierung-Bestätigen-Flow (bleibt unverändert)
- E-Mail-Antwort-Funktion (nicht angefragt)

---

## Betroffene Dateien

| Datei | Änderung |
|---|---|
| `frontend/src/views/email_import/EmailDetailView.jsx` | **Neu** |
| `frontend/src/views/email_import/UnfallEmailView.jsx` | State für geöffnete E-Mail, `onOpenEmail`-Handler |
| `frontend/src/views/email_import/components/EmailKarte.jsx` | „▶ E-Mail öffnen"-Button |
| `frontend/src/views/ActionBoardView.jsx` | E-Mail-Klick → `onOpenEmail` statt `onOpenAkte` |
| `frontend/src/App.jsx` | `initialEmailId`-Prop, Navigation zu `email-import` mit Ziel-E-Mail |
| `frontend/src/sections/DokumenteSection.jsx` | Neue E-Mail-Gruppe mit Inline-Expand |
| `frontend/src/api.js` | `emailImport.inAkte()` exportieren |
| `backend/db/schema_manager.py` | Migration: `dateityp`-Constraint oder `dokumentenklasse='email'` |

---

## Erfolgs-Kriterien

1. Klick auf E-Mail im Action Dashboard → E-Mail-Detail-Seite öffnet sich, nicht Akte-Übersicht
2. E-Mail-Detail-Seite zeigt Text links und PDF-Vorschau rechts bei Klick auf Anhang
3. „In Akte importieren" erscheint als prominenter grüner Vorschlag, nicht als kleiner Button
4. DokumenteSection zeigt E-Mails der Akte klappbar an; Anhänge können geöffnet werden
5. Alle Navigationspfade haben einen funktionierenden „Zurück"-Button
6. Kein Seitenwechsel beim Aufklappen einer E-Mail in der DokumenteSection
