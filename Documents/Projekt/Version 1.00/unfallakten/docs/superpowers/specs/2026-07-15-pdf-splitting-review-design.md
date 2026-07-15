# PDF-Splitting im Review-UI — Design (Option C)

Stand: 2026-07-15 · Branch `intake-stufe1` · Zielschema **v58**

## Ziel

Ein mehrseitiges Sammel-PDF soll **im Review-Dialog** entlang von Seitengrenzen in
mehrere eigenständige Dokumente aufgetrennt werden können, **bevor** es freigegeben
wird. Jeder Teil durchläuft danach die normale Intake-Pipeline und wird einzeln
geprüft und freigegeben.

## Auslöser (reale Fälle)

1. **Sammel-PDF vom Versicherer** — ein Anlagen-PDF bündelt mehrere Einzeldokumente.
2. **Ein Dokument, mehrere Klassen** — z. B. Seiten 1–3 Gutachten, Seiten 4–5 SV-Rechnung.
3. **Scan-Stapel** — mehrere getrennte Dokumente in einem Kopierer-/E-Akte-Scan.

**Feste Randbedingung:** Die Teile liegen **immer auf sauberen Seitengrenzen**
(zusammenhängende Seitenbereiche). Der Fall „dieselbe Seite gehört zu mehreren
Vorgängen" ist **ausdrücklich nicht** Teil dieses Features.

## Gewählter Ansatz (A): „Jeder Teil ist ein neues Dokument"

Beim Aufteilen zerlegt der Server das PDF entlang der gesetzten Schnitte mit PyMuPDF
in N neue PDFs. Jeder Teil wird als **neues Intake-Dokument** angelegt und **wie ein
frisch eingegangenes Dokument** durch die bestehende Pipeline geschickt
(OCR/Text → Klassifikation → Feld-Extraktion). Danach steht jeder Teil einzeln in der
Review-Queue.

Verworfene Alternative B („vorberechnete Seitendaten wiederverwenden, OCR sparen") —
deutlich komplexer, koppelt eng an die interne `parse_json`-Struktur, optimiert ein
aktuell nicht bestehendes Problem (YAGNI).

## Bedienung (UX)

- **Einstieg:** Button **„✂ In Teile aufteilen"** im Kopf des Detail-Panels
  (`DetailPanel`), neben „🖨 Drucken".
- **Dialog `SplitDialog`:**
  - Reihe von **Seiten-Miniaturen** über **alle** Seiten des PDFs.
  - Zwischen zwei Seiten liegt eine klickbare **Lücke**; Klick setzt/entfernt einen
    **Schnitt** (aktiver Schnitt orange hervorgehoben).
  - Live-Vorschau der **resultierenden Teile** („Teil 1 · Seiten 1–3", „Teil 2 ·
    Seiten 4–5"), farbig gruppiert.
  - Aktion **„In N Teile aufteilen"** und **„Abbrechen"**.
  - Hinweistext: nach dem Aufteilen werden die Teile automatisch klassifiziert und
    erscheinen einzeln in der Queue; das Original wird als „aufgeteilt" markiert.
- **Grenzen im UI:** Bei einseitigem Dokument oder Text-Payload ohne PDF
  (`payload_typ != 'datei'`) ist der Button **ausgegraut**. „Aufteilen" ist erst
  aktiv, wenn mindestens ein Schnitt gesetzt ist (≥ 2 Teile).
- **Seitenzahl:** Miniaturen und Schnittpunkte richten sich nach der **echten
  PDF-Seitenzahl** (`doc.page_count`), **nicht** nach der auf 30 gekürzten
  `parse_json.seiten`-Liste.

## Server & Datenmodell

### Neuer Service `backend/intake/split_service.py`

Kapselt die Logik (hält die Route schlank, isoliert testbar):

1. **Vorbedingungen prüfen:** Original existiert, `payload_typ='datei'`,
   Arbeitskopie-PDF vorhanden, `queue_status` in
   `{'bereit_zur_review','pipeline_fehler','neu'}`, nicht verworfen/freigegeben,
   PDF hat ≥ 2 Seiten.
2. **Schnitte/Gruppen validieren:** Gruppen sind zusammenhängend, decken lückenlos
   alle Seiten genau einmal ab, in Reihenfolge, ≥ 2 Gruppen, alle Seitennummern im
   gültigen Bereich `[1 … page_count]`.
3. **Je Gruppe PDF bauen:** PyMuPDF (`fitz`) — neues Dokument, `insert_pdf(src,
   from_page, to_page)` → Bytes → `sha256` → Ablage über `backend/intake/archiv.py`
   (Original- und Arbeitskopie-Pfad). Bestehende Hash-Dedup-Logik gilt.
4. **Je Teil `intake_dokumente`-Zeile:** `payload_typ='datei'`, `queue_status='neu'`,
   `klasse_quelle='auto'`, `aufgeteilt_aus_id=<Original.id>`, Seitenzahl gesetzt →
   in die Worker-Queue eingereiht.
5. **Je Teil `zustellungen`-Zeile:** **erbt** die Signale des Originals (`quelle`,
   `absender`, `betreff`, `empfangen_am`, `signale_json`) — damit Akten-Matching und
   Absender-Registry weiterlaufen.
6. **Original markieren:** Soft-Delete `verworfen_grund='aufgeteilt'`,
   `verworfen_am`, `verworfen_von`; Kind-IDs ins `korrektur_log`. Verschwindet aus
   der Queue, bleibt als Nachweis, verlinkt (über den Rückbezug) auf seine Teile.

**Transaktion:** Anlegen aller Teile + Markierung des Originals läuft in **einer**
Transaktion (alles-oder-nichts). Bei Fehler Rollback. Bereits geschriebene
Archiv-PDFs sind write-once (per `sha`) und bei Wiederholung wiederverwendbar —
verwaiste Dateien sind unkritisch.

### Endpoints (`backend/routers/intake_routes.py`)

- `POST /intake/dokument/<id>/split` — Body kanonisch: `{"gruppen": [[1,2,3],[4,5]]}`
  (Liste zusammenhängender, 1-basierter Seitenlisten; das Frontend berechnet sie aus
  den Schnitten via `gruppenAusSchnitten` und schickt sie explizit). Ruft
  `split_service`, gibt die neuen Teil-IDs zurück. Fehler: 422 (ungültig / Text /
  einseitig), 409 (Original in falschem Zustand / bereits aufgeteilt).
- `GET /intake/dokument/<id>/seite/<n>/thumbnail` — rendert Seite `n` mit PyMuPDF als
  kleines PNG. Auth per `?token=` (analog bestehendem `GET …/pdf`). 404 bei
  ungültiger Seitennummer.

### Migration 58

Additiv, nullable, idempotent, **explizite Commits, kein `executescript`** (gemäß den
dokumentierten Migrations-Lehren):

- Neue Spalte `intake_dokumente.aufgeteilt_aus_id INTEGER NULL` (verweist auf das
  Original-`intake_dokumente.id`). Die Teil→Original-Verlinkung; „Original → seine
  Teile" per Rückwärts-Abfrage (`WHERE aufgeteilt_aus_id = <id>`), keine
  Doppelspeicherung.
- `'aufgeteilt'` wird als gültiger Verwerfen-Grund in die Gründe-Menge aufgenommen.

## Frontend

- Neue Komponente `SplitDialog` in `frontend/src/views/ReviewQueueView.jsx` (bzw.
  ausgelagert), aufgerufen aus `DetailPanel`.
- Reine Funktion **`gruppenAusSchnitten(seitenzahl, schnitte)`** → Liste der Teile
  (Seitenbereiche); isoliert testbar.
- Miniaturen laden je Seite vom Thumbnail-Endpoint (Token wie bei der PDF-Anzeige).
- API-Client-Spiegel in `frontend/src/api.js` (`apiIntake.split`, Thumbnail-URL).
- Nach erfolgreichem Split: Queue neu laden; Original raus, Teile erscheinen.

## Fehlerfälle & Randbedingungen

- **Nicht aufteilbar** (einseitig / Text-Payload): Button ausgegraut **und** Endpoint
  lehnt mit 422 ab (Server vertraut nicht dem UI).
- **Ungültige Schnitte** (1 Gruppe, Lücke, Überlappung, Seite außerhalb) → 422, nichts
  wird angelegt.
- **Original in falschem Zustand** (verworfen/freigegeben/läuft) → 409.
- **Doppel-Submit:** Original bereits `'aufgeteilt'` → 409 (kein doppelter Split).
- **Identischer Teil:** erzeugt ein Schnitt exakt dieselbe `sha` wie ein bestehendes
  Dokument → bestehende Zeile per Hash-Dedup wiederverwenden statt Duplikat.
- **Bildseiten/OCR:** Teile werden von der Pipeline neu triagiert (N-04) — greift
  automatisch.
- **Seitenzahl:** Dialog nutzt die echte PDF-Seitenzahl. Die 30er-Grenze bleibt eine
  reine Text-Extraktions-/Timeout-Schranke **pro Dokument** (unverändertes
  Bestandsverhalten); nach dem Split ist jeder Teil kleiner und greift meist gar
  nicht mehr.

## Sicherheit / Invarianten

- Split schreibt **ausschließlich Intake-Tabellen** (`intake_dokumente`,
  `zustellungen`) — **nie** Akten-Tabellen. `INTAKE_REVIEW_PFLICHT` bleibt gewahrt:
  jeder Teil braucht weiterhin eine **menschliche Freigabe**, bevor etwas in die Akte
  geschrieben wird.
- **RA-MICRO read-only** unberührt.
- Die Teile durchlaufen die **bestehende Pipeline unverändert** (Worker pickt
  `queue_status='neu'`) — kein neuer Parallel-Pfad.

## Tests (TDD)

**Backend:**
- `split_service` Unit: Gruppen-Validierung (gültig/ungültig), PDF-Zerlegung erzeugt
  korrekte Seitenzahlen, `sha`/Archiv-Ablage, Original-Markierung,
  Zustellungs-Vererbung, Transaktions-Rollback bei Fehler.
- Migration 58: Spalte vorhanden, additiv, idempotent.
- Route-Tests: 200 mit Teil-IDs; 422 (ungültig / Text / einseitig); 409
  (verworfen / freigegeben / bereits aufgeteilt); Teile landen mit `queue_status='neu'`.
- Thumbnail-Endpoint: rendert PNG, Auth-Token, 404 bei ungültiger Seite.
- Guard-Tests bleiben grün (Split schreibt keine Akten-Tabellen); ggf.
  `test_s19_intake_write_guard.py` erweitern.
- E2E: Sammel-PDF → split → 2 Teile in Queue → je klassifiziert/parsebar → jede
  Freigabe schreibt genau **eine** `dokumente`-Zeile.

**Frontend (Vitest):**
- Reine Funktion `gruppenAusSchnitten()` isoliert.
- Schnitt setzen/entfernen; Button-Disable (einseitig/Text); Submit ruft API mit
  korrekten Gruppen; Fehleranzeige.

## Deploy-Hinweis

Migration 58 muss aufs Volume angewandt sein, **bevor** der App-Code startet (sonst
`no such column`). Für das aktuelle Setup irrelevant, solange kein Prod-Host läuft
(Go-Live vertagt) — beim späteren Rollout in die Migrations-vorab-Reihenfolge des
Runbooks einreihen (`docs/ROLLOUT-intake-stufe1-prod.md`).

## Offen / bewusst ausgeklammert

- Nicht-zusammenhängende Seiten pro Teil (Variante C aus dem Brainstorming) — nicht
  nötig bei sauberen Seitengrenzen.
- Klasse bereits im Schneide-Dialog wählen — verworfen zugunsten „automatisch
  klassifizieren, dann Queue".
- Direkt-in-die-Akte ohne erneuten Review je Teil — verworfen (Kontrollverlust).
