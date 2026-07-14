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
   UX-Mockup (vom Nutzer freigegeben):
   https://claude.ai/code/artifact/6e3de215-25d2-4ada-88eb-5f9e13353e91
2. **Bestehende Akten-Daten: Leerfelder füllen; abweichende Felder überschreibbar.**
   - Leeres Aktenfeld → wird mit dem (editierbaren) Bogen-Wert gefüllt.
   - Aktenfeld gefüllt **und** weicht vom Bogen-Wert ab → als abweichend markiert
     (⚠ „Akte: X · Bogen: Y"). **Standard bleibt der Akten-Wert** (kein stilles
     Überschreiben); der Sachbearbeiter kann per „Bogen übernehmen" oder freies
     Tippen den Wert **bewusst überschreiben**.
   - Aktenfeld gefüllt und deckungsgleich → gesperrt, nichts zu tun.
   - **Konsequenz für den Service:** die frühere „nur-Leerfelder, nie
     überschreiben"-Garantie entfällt; der Service schreibt genau die vom SB
     bestätigten Werte je aktivem Abschnitt (leer → füllen, abweichend → überschreiben).
     Die menschliche Freigabe ist der Kontrollpunkt.
3. **Architektur A: neues Service-Modul.** Die Schreib-Logik lebt in einem eigenen,
   fokussierten Modul. Die alten `_ergaenze_*` in `import_service.py` bleiben
   eingefroren (Rollback-Anker, nur unter `INTAKE_REVIEW_PFLICHT=false` aktiv).
4. **Übernahme-Fehler brechen die Freigabe NICHT ab** — sie werden geloggt und im
   Response gemeldet; das Dokument bleibt freigegeben.
5. **Abschnitts-Checkboxen** (Mandant/Gegner/Unfall/Personenschaden) steuern, welche
   Bereiche übernommen werden. Kein Master-Schalter (bei Nicht-Fragebögen erscheint der
   Block gar nicht). **Auto-Collapse-Default:** Abschnitte ohne offene Aufgabe (alle
   Felder gefüllt und deckungsgleich) starten eingeklappt; Abschnitte mit leeren oder
   abweichenden Feldern starten offen.

## Architektur

### 0. Voraussetzung: Text-Dokument-Freigabe reparieren

**Fund (2026-07-14):** `post_freigabe` ruft `output_adapter.schreibe_dokument`, das
zwingend eine Datei-**Arbeitskopie** verlangt (`FileNotFoundError`, sonst HTTP 500).
Ein Fragebogen ist aber ein **Text-Dokument** (`payload_typ='text'`, keine
Arbeitskopie) → die Freigabe bräche ab, bevor die Feld-Übernahme läuft. Betrifft
Text-Dokumente generell (auch freigegebene E-Mail-Bodies) — latenter Bug.

**Lösung (Nutzerentscheidung):** Beim Freigeben eines Text-Dokuments wird der
`structured_payload` (Fragebogen-JSON bzw. E-Mail-Text) in eine Datei
materialisiert und als Arbeitskopie an `schreibe_dokument` übergeben. Der
Fragebogen landet damit **auch als `dokumente`-Zeile** in der Akte (Audit-Trail),
und die Text-Freigabe funktioniert generisch. `output_adapter` bleibt unangetastet
(datei-basiert); die Materialisierung ist ein lokaler Helfer im Freigabe-Pfad
(`_sichere_text_arbeitskopie` in `intake_routes.py`).

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
  `konflikt` = Akte gefüllt **und** weicht (normalisiert) vom Bogen-Wert ab
  (überschreibbar, Standard = Akten-Wert).
  Fehlt die beteiligte/unfalldetails/personenschaden-Zeile noch, gelten alle Felder
  als leer. Keine Schreibzugriffe.
- `uebernehme(akte_az, werte, aktive_abschnitte) -> dict` — schreibt genau die vom SB
  bestätigten Werte je **aktivem** Abschnitt: leeres Aktenfeld → füllen; abweichendes
  Aktenfeld → überschreiben, **wenn** der bestätigte Wert vom aktuellen Akten-Wert
  abweicht (unveränderte/deckungsgleiche Felder werden nicht angefasst → kein Audit-
  Rauschen). Inaktive Abschnitte werden komplett übersprungen. INSERT-or-UPDATE analog
  `_ergaenze_*`. Rückgabe `{geschrieben:[…], uebersprungen:[…]}`.

### 3. Endpoints (`backend/routers/intake_routes.py`)

- `GET /intake/dokument/<id>/fragebogen-vorschau?akte_az=X`
  → parst `structured_payload`, ruft `baue_vorschau`. Parametrisiert mit `akte_az`
  (SB kann Ziel-Akte im Dropdown wechseln → Vorschau pro Akte neu). Kein Fragebogen
  → 422. Fehlt `akte_az` → 422.
- `hole_detail` → zusätzliches Feld `ist_fragebogen`.
- `post_freigabe` → (a) materialisiert bei `payload_typ='text'` die Arbeitskopie
  (Abschnitt 0), damit `schreibe_dokument` das Dokument anlegt; (b) akzeptiert
  optionalen Payload-Block `fragebogen_uebernahme: {abschnitte: [...], werte:
  {mandant:{...}, ...}}` und ruft **nach** erfolgreichem `schreibe_dokument` (und den
  Ereignissen) `uebernehme(...)`, gekapselt in try/except: Fehler → Log +
  `response.fragebogen_uebernahme = {fehler}`, Freigabe bleibt gültig. Erfolg →
  `response.fragebogen_uebernahme = {geschrieben, uebersprungen}`.

### 4. Frontend (`frontend/src/views/ReviewQueueView.jsx`)

Bei `ist_fragebogen`:
- Nach Akten-Auswahl `GET …/fragebogen-vorschau?akte_az=…` laden.
- Im Freigabe-Dialog: Abschnitts-Checkboxen (Mandant/Gegner/Unfall/Personenschaden),
  pro Feld:
  - leer → editierbares Input (vorbelegt mit `geparst`),
  - abweichend → editierbares Input (vorbelegt mit dem **Akten-Wert**) + ⚠-Zeile
    „Akte: X · Bogen: Y" + Button „Bogen übernehmen",
  - gefüllt und deckungsgleich → ausgegraut/gesperrt.
- Auto-Collapse: Abschnitte ohne offene Aufgabe starten eingeklappt.
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
  - `baue_vorschau`: leer / abweichend / gefüllt-deckungsgleich, fehlende Zeilen.
  - `uebernehme`: füllt Leerfelder; überschreibt ein abweichendes Feld nur mit einem
    bestätigten, tatsächlich abweichenden Wert; lässt deckungsgleiche/unveränderte
    Felder unangetastet; inaktive Abschnitte werden komplett übersprungen.
  - Vorschau-Endpoint: 422 bei Nicht-Fragebogen / fehlendem `akte_az`; korrekte
    Sektionen inkl. `konflikt`-Flag.
  - Freigabe-E2E: Fragebogen freigegeben → `beteiligte` gefüllt; abweichendes Feld
    ohne Bestätigung → Akten-Wert bleibt; abweichendes Feld mit „Bogen übernehmen" →
    überschrieben; Übernahme-Fehler bricht Freigabe nicht ab.
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
