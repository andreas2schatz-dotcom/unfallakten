# Fragebogen-Feld-Übernahme bei Freigabe — Design

Stand: 2026-07-14 · Branch `intake-stufe1` · Folge-Task aus BUG-01

## Problem

Ein Unfallbogen/Fragebogen landet seit BUG-01 verlustfrei als Text-`intake_dokument`
in der Review-Queue. Beim **Freigeben** werden die bereits geparsten Felder
(Mandant, Gegner, Unfalldetails, Personenschaden) jedoch **nicht** in die Akten-
Tabellen übernommen — der Sachbearbeiter muss sie manuell nacherfassen. Diese
Aufgabe fügt die Feld-Übernahme genau an der Freigabe an.

## Leitplanken (nicht verhandelbar)

- **Menschliche Freigabe = einzige Schreiboperation Richtung Akte.** Dieses Feature
  fügt genau dort einen Schreibweg hinzu.
- **RA-MICRO read-only** — nur SQLite schreiben.
- Alt-Pfade unter `INTAKE_REVIEW_PFLICHT=false` unangetastet lassen.
- TDD, keine unnötigen Abstraktionen, Deutsch.

## Getroffene Entscheidungen (Brainstorming 2026-07-14)

1. **UX: editierbare Vorschau im Freigabe-Dialog** (nicht vollautomatisch). Der
   Anwalt sieht die geparsten Felder, kann sie korrigieren und bestätigt dann.
2. **Bestehende Akten-Daten: nur Leerfelder füllen, nie überschreiben.** Weicht ein
   geparster Wert von einem bereits gesetzten Akten-Wert ab, wird das als Hinweis
   angezeigt (⚠ „Akte: X / Bogen: Y"), aber nicht geschrieben. Entspricht der
   heutigen `_ergaenze_*`-Semantik.
3. **Architektur A: neues Service-Modul.** Die Schreib-Logik lebt in einem eigenen,
   fokussierten Modul. Die alten `_ergaenze_*` in `import_service.py` bleiben
   eingefroren (Rollback-Anker, nur unter `INTAKE_REVIEW_PFLICHT=false` aktiv).
4. **Übernahme-Fehler brechen die Freigabe NICHT ab** — sie werden geloggt und im
   Response gemeldet; das Dokument bleibt freigegeben.
5. **Abschnitts-Checkboxen** (Mandant/Gegner/Unfall/Personenschaden) steuern, welche
   Bereiche übernommen werden.

## Architektur

### 1. Erkennung & Datenquelle

Ein Intake-Dokument ist ein Fragebogen ⇔ `payload_typ=='text'` **und**
`parse_fragebogen_anhang(structured_payload.encode())` ≠ `None`
(validiert `meta.formular=="unfallbogen"`, liefert zugleich die Abschnitte).
Das ist die **Wahrheitsquelle**; das `signale.dokument_art="fragebogen"` bleibt nur
sekundärer Hinweis und wird nicht benötigt.

`hole_detail` liefert zusätzlich `ist_fragebogen: bool`.

### 2. Neues Modul `backend/services/fragebogen_uebernahme.py`

Einzige sanktionierte Stelle, die Fragebogen-Felder in Akten-Stammdaten schreibt.
Enthält das JSON→Spalten-Mapping (aus `_ergaenze_*` übernommen).

**Feld-Mapping (Zieltabellen wie `_ergaenze_*`):**

- **Mandant** → `beteiligte` (rolle='mandant'): `name, vorname, anschrift(=strasse),
  plz, ort, email, telefon, iban, vorsteuer(=vorsteuerabzug=='ja' → 'Y')`.
- **Gegner** → `beteiligte` (rolle='gegner'): `name(=fahrer),
  kfz_kennzeichen(=fahrzeug.kennzeichen), notizen(=fahrzeug.fabrikat),
  versicherung(=versicherung.name), vers_nr(=versicherung.nummer),
  schaden_nr(=versicherung.schadennummer)`.
- **Unfall** → `unfallakte`: `unfalldatum(=datum), unfallort(=ort)`;
  → `unfalldetails`: `schilderung` (mit `[Uhrzeit: …]`-Präfix aus `zeit`),
  `ermittlungsakte_az(=polizei.aktenzeichen)`.
- **Personenschaden** → `personenschaden`: `geburtsdatum(=verletzter.geburtsdatum),
  verletzungen_text(=verletzungen), krankenhaus_name(=krankenhaus.name)
  (+krankenhaus_aufenthalt=1), krankenhaus_von/bis, krank_von/bis
  (=hauskrank.von/bis, +krankgeschrieben=1)`.

**Funktionen:**

- `baue_vorschau(akte_az, parsed) -> dict` — reine Lesefunktion. Pro Abschnitt eine
  Feldliste `{feld, label, geparst, akte_wert, ist_leer, konflikt}`.
  `ist_leer` = Akten-Feld leer/NULL (→ wird gefüllt).
  `konflikt` = Akte gefüllt **und** weicht (normalisiert) vom Bogen-Wert ab.
  Fehlt die beteiligte/unfalldetails/personenschaden-Zeile noch, gelten alle Felder
  als leer. Keine Schreibzugriffe.
- `uebernehme(akte_az, werte, aktive_abschnitte) -> dict` — schreibt **fill-empty**:
  nur Felder, deren Abschnitt in `aktive_abschnitte` steht **und** die in der Akte
  leer sind. Die Leerheit wird am Schreibzeitpunkt erneut geprüft (Sicherheitsnetz:
  auch wenn das Frontend einen Wert für ein gefülltes Feld schickt, wird nie
  überschrieben). INSERT-or-UPDATE analog `_ergaenze_*`. Rückgabe
  `{geschrieben:[…], uebersprungen:[…]}`.

### 3. Endpoints (`backend/routers/intake_routes.py`)

- `GET /intake/dokument/<id>/fragebogen-vorschau?akte_az=X`
  → parst `structured_payload`, ruft `baue_vorschau`. Parametrisiert mit `akte_az`
  (SB kann Ziel-Akte im Dropdown wechseln → Vorschau pro Akte neu). Kein Fragebogen
  → 422. Fehlt `akte_az` → 422.
- `hole_detail` → zusätzliches Feld `ist_fragebogen`.
- `post_freigabe` → akzeptiert optionalen Payload-Block
  `fragebogen_uebernahme: {abschnitte: [...], werte: {mandant:{...}, ...}}`.
  **Nach** erfolgreichem `schreibe_dokument` (und den Ereignissen) ruft die Route
  `uebernehme(...)`, gekapselt in try/except: Fehler → Log + `response.uebernahme_fehler`,
  Freigabe bleibt gültig. Erfolg → `response.uebernahme = {geschrieben, uebersprungen}`.

### 4. Frontend (`frontend/src/views/ReviewQueueView.jsx`)

Bei `ist_fragebogen`:
- Nach Akten-Auswahl `GET …/fragebogen-vorschau?akte_az=…` laden.
- Im Freigabe-Dialog: Abschnitts-Checkboxen (Mandant/Gegner/Unfall/Personenschaden),
  pro Feld:
  - leer → editierbares Input (vorbelegt mit `geparst`),
  - Konflikt → gesperrte Anzeige + ⚠-Badge „Akte: X / Bogen: Y",
  - gefüllt ohne Konflikt → ausgegraut/gesperrt.
- Akten-Wechsel im Dropdown → Vorschau neu laden.
- Beim Freigeben: bestätigte Werte + aktive Abschnitte in `fragebogen_uebernahme`
  mitsenden.

### 5. Guards & Tests

- `test_s19d_e2e_no_intake_writes.py`: „keine Schreibung" gilt weiter für den
  **Auto-Pfad** (E-Mail-Import unter Flag). Die **Freigabe-getriggerte** Übernahme ist
  ein legitimer Schreibweg → neuer, separater Test.
- AST-Guard `test_s19_intake_write_guard.py`: **unberührt** — verfolgt nur
  `registriere_dokument`/`setze_schadenpositionen`; das neue Modul schreibt (wie
  `_ergaenze_*`) direkt in `beteiligte`/`unfalldetails`/`personenschaden` und liegt in
  `backend/services/`, außerhalb der Intake-Pfade.
- Neue Tests (TDD):
  - `baue_vorschau`: leer / konflikt / gefüllt-ohne-konflikt, fehlende Zeilen.
  - `uebernehme`: fill-empty schreibt Leerfelder; überschreibt nie gefüllte;
    inaktive Abschnitte werden übersprungen.
  - Vorschau-Endpoint: 422 bei Nicht-Fragebogen / fehlendem `akte_az`; korrekte
    Sektionen.
  - Freigabe-E2E: Fragebogen freigegeben → `beteiligte` gefüllt; vorbefüllte Akte →
    unangetastet + Konflikt gemeldet; Übernahme-Fehler bricht Freigabe nicht ab.
  - Erkennung `ist_fragebogen` in `hole_detail`.
  - Frontend-Vitest: Vorschau-Render (leer/konflikt), Checkbox-Steuerung,
    Freigabe-Payload enthält `fragebogen_uebernahme`.

## Bewusst außerhalb des Scopes (YAGNI)

- `sachschaden` aus dem Bogen → **keine** Schadenpositionen/Beträge (das ist der
  Rechnungs-/Positionsmodell-Pfad). Nur die vier bestehenden Enricher-Bereiche.
- **Keine DB-Migration** — alle Zieltabellen existieren.
- Onboarding/Neu-Akte-Anlage (PRD-NEW) unberührt: Neu-Akten werden beim Freigeben
  bereits on-demand angelegt (BUG-08), dann sind alle Felder leer und werden regulär
  gefüllt.

## Andockpunkte (2026-07-14 verifiziert)

- `post_freigabe`, `hole_detail`, `_lade_intake` (liefert `SELECT *` inkl.
  `structured_payload`) — `backend/routers/intake_routes.py`.
- `_ergaenze_mandant/_gegner/_unfalldetails/_personenschaden` (Mapping-Vorlage,
  eingefroren) — `backend/email_import/import_service.py`.
- `parse_fragebogen_anhang` — `backend/email_import/fragebogen_parser.py`.
- Guard-Referenzen: `test_s19_intake_write_guard.py`,
  `test_s19d_e2e_no_intake_writes.py`.
