# Design: Text-Pfad für die Intake-Pipeline

> Datum: 2026-07-10 · Branch: `intake-stufe1` · Status: freigegeben (Design), Implementierung ausstehend

## Problem

Der IMAP-Adapter legt für **jede eingehende E-Mail** zwei Arten von Intake-Dokumenten an:

- den **E-Mail-Text (Body)** als `intake_dokumente.payload_typ='text'` (Eltern-Zustellung),
- jeden **Anhang** als eigenes `payload_typ='datei'`-Dokument, per `zustellungen.parent_id` an die Body-Zustellung gehängt (Kind).

Die Verarbeitungs-Pipeline (`backend/intake/pipeline.py::verarbeite_dokument`) verlangt jedoch **immer** eine PDF-Arbeitskopie (`arbeitskopie_pfad`) und liest sie als PDF-Bytes. Text-Payloads haben per Design keine Arbeitskopie (`_persistenz.oder_intake_dokument_fuer_text`: „Kein Archiv-Original, keine Arbeitskopie"). Folge: **jeder E-Mail-Text scheitert** nach 3 Versuchen mit `pipeline_fehler` / „Arbeitskopie fehlt: None". Stand 2026-07-10: 52 solcher Fehler in der Live-DB.

**Fachliche Auswirkung:** Der E-Mail-Text — in dem oft Absender, Name und **Aktenzeichen** stehen — wird nie verarbeitet und ist in der Review-Queue nicht nutzbar. Konkreter Schmerzpunkt des Nutzers: Er erhielt eine Unfallskizze als PDF-Anhang, aber ohne die zugehörige E-Mail ließ sich Absender bzw. Akte nicht ermitteln.

## Ziele

1. Die Pipeline verarbeitet reine E-Mail-Texte **direkt** (ohne PDF): Klassifikation, Feld-Extraktion und Aktenzeichen-Erkennung laufen auf dem Body-Text.
2. E-Mail-Texte erscheinen als normale, freigebbare Einträge in der Review-Queue.
3. Beim Öffnen eines **Anhangs** ist der volle E-Mail-Kontext sichtbar (Absender, Betreff, Datum, Text, erkanntes AZ + Link zur E-Mail).
4. Die Queue zeigt **verschachtelt**: E-Mail als Kopf, ihre Anhänge eingerückt darunter.
5. Die 52 bereits aufgelaufenen Text-Fehler werden nach Deploy einmalig neu verarbeitet.

## Nicht-Ziele (bewusst, YAGNI)

- **Kein Spam-/Relevanz-Filter.** Alle E-Mail-Texte (auch Werbung) landen in der Queue; der Nutzer verwirft Werbung manuell über den bestehenden Verwerfen-Button (Migration 53). Ein Filter kann später nachgerüstet werden, falls das Volumen stört.
- **Keine umgekehrte Navigation** (E-Mail listet ihre Anhänge). Nur Anhang → E-Mail ist gefordert.
- **Kein PDF-Rendering** von E-Mail-Texten (kein Text→PDF-Umweg). Die Pipeline arbeitet ab dem Text ohnehin PDF-frei.

## Schlüssel-Erkenntnis

`verarbeite_dokument` liest zwar am Anfang ein PDF, aber **ab der Gewinnung von `text_gesamt` arbeitet der gesamte Rest nur auf Text**:

- `klassifiziere_stufe1(text, signale, registry)`
- `klassifiziere_stufe2(text_seite1, text_letzte, …)`
- `extrahiere_felder(text, klasse, registry)`
- `finde_kandidaten(text, signale)`  ← Aktenzeichen-Erkennung

Für ein Text-Payload liegt `text_gesamt` bereits als `structured_payload` vor. Der Text-Pfad ist damit im Kern nur eine Verzweigung am Anfang.

## Architektur

### A. Kernmechanik — Text-Zweig in `pipeline.verarbeite_dokument`

Verzweigung ganz oben nach `payload_typ`:

- **`payload_typ == 'text'`**: kein PDF-Read, kein OCR. `text_gesamt = structured_payload`. Ein synthetisches Ein-Seiten-Objekt (`SeitenText`) mit `textquelle='email_text'`, `braucht_ocr=False`, `text=structured_payload`. `seite1 = letzte = text_gesamt`.
- **`payload_typ == 'datei'`** (Default): heutiger Weg (Arbeitskopie-PDF → `extrahiere_seiten` → OCR) **unverändert**.

Ab der Zeile, die `text_gesamt`/`seiten` gesetzt hat, läuft **identischer** Code für beide Zweige (Klassifikation, Extraktion, Matching, `markiere_bereit`).

- `_lade_dokument` wird um `payload_typ` und `structured_payload` erweitert (SELECT-Spalten).
- Kleiner Helper `_synth_seite(text) -> SeitenText` erzeugt das Ein-Seiten-Objekt.
- `archiv.py`, `_persistenz.py`, alle Adapter: **unangetastet**.

### B. Anzeige in der Review-Queue

**B1 — E-Mail-Text lesbar statt PDF-Vorschau.** `hole_detail` liefert zusätzlich `payload_typ`. Ist es `text`, zeigt das Detail-Panel den geparsten `text_gesamt` als lesbaren Textblock (mit Klasse + AZ darüber wie bei PDFs) statt des PDF-`iframe`. Der `/pdf`-Endpoint bleibt für Text-Dokumente unaufgerufen (kein 404 im UI).

**B2 — Voller E-Mail-Kontext am Anhang.** `hole_detail` liefert für ein `datei`-Dokument mit Eltern-E-Mail einen Block `eltern_email`:

```
eltern_email: {
  intake_id, absender, betreff, empfangen_am,
  text (aus parse_json.text_gesamt der Body-Zeile),
  akte_az (Top-Kandidat aus parse_json.akten_kandidaten der Body-Zeile)
} | null
```

Ermittlung: Anhang-`zustellung.parent_id` → Body-`zustellung` → deren `intake_dokument_id` → dessen `parse_json`. Reine Lese-Erweiterung, kein Schema-Eingriff. Frontend zeigt oben im Anhang-Detail eine Box „📧 Kam mit E-Mail — Absender · Betreff · Datum · AZ" mit aufklappbarem Text und Link „Zur E-Mail →".

**B3 — Verschachtelte Queue (Variante A).** Die Queue-Liste (`ReviewQueueView` / `GET /intake/queue`) gruppiert je E-Mail: Body-Zeile als Kopf (📧), Anhänge eingerückt darunter (📎) mit Verbindungslinie. Standalone-Dokumente (ohne Eltern) erscheinen als eigene Kopfzeile. `hole_queue` liefert dafür je Eintrag `payload_typ` und `parent_zustellung_id` (bzw. eine abgeleitete Gruppen-ID), damit das Frontend gruppieren kann. Sortierung: Gruppen chronologisch, innerhalb der Gruppe Body zuerst, dann Anhänge.

### C. Backfill der 52 Altfälle

Nach Deploy des Text-Zweigs: einmaliges `enqueue` aller `intake_dokumente` mit `queue_status='pipeline_fehler' AND payload_typ='text'`. Sie durchlaufen die neue Verarbeitung und werden `bereit_zur_review`. Idempotent, kein Datenverlust. DB-Backup davor. Kein Schema-Eingriff, keine Migration.

### D. Fehlerbehandlung

- Text-Payload mit leerem/NULL `structured_payload` → definierter Fehler „Text-Payload ohne Inhalt" (statt irreführendem „Arbeitskopie fehlt"), landet regulär im Retry/`pipeline_fehler`.
- Eltern-E-Mail nicht auffindbar (Alt-Anhang ohne `parent_id`, oder Body noch nicht geparst) → `eltern_email: null`, UI zeigt Box nicht. Kein Fehler.

## Betroffene Dateien

- `backend/intake/pipeline.py` — Text-Verzweigung + `_synth_seite` + `_lade_dokument`-SELECT.
- `backend/routers/intake_routes.py` — `hole_detail`: `payload_typ` + `eltern_email`; `hole_queue`: `payload_typ` + Gruppen-Bezug.
- `frontend/src/views/ReviewQueueView.jsx` — Textblock-Anzeige (B1), Eltern-E-Mail-Box (B2), verschachtelte Liste (B3).
- `backend/tests/test_intake_*.py` + Vitest — siehe Tests.
- Backfill: Reparatur-Skript/Einmal-Lauf (kein Produktcode).

## Tests

**Backend:**
- `verarbeite_dokument` mit Text-Payload → Klasse gesetzt, `akten_kandidaten` nicht leer bei AZ im Text, `queue_status='bereit_zur_review'`, kein „Arbeitskopie fehlt".
- Regression: `payload_typ='datei'` läuft unverändert durch (bestehende Tests bleiben grün).
- Text-Payload mit leerem `structured_payload` → definierter Fehler.
- `hole_detail` Anhang mit Eltern-E-Mail → `eltern_email` mit Absender/Betreff/Text/AZ; E-Mail-Dokument → `payload_typ='text'` + Text.

**Frontend (Vitest):**
- Detail-Panel bei `payload_typ='text'` → Textblock statt iframe.
- Anhang-Detail mit `eltern_email` → Kontext-Box sichtbar.
- Queue rendert verschachtelt (E-Mail-Kopf + eingerückte Anhänge).

## Abnahmekriterien

1. Ein neu eingehender E-Mail-Text wird `bereit_zur_review` statt `pipeline_fehler`; sein Aktenzeichen wird erkannt.
2. Beim Öffnen eines E-Mail-Anhangs sind Absender, Betreff, Text und AZ der zugehörigen E-Mail sichtbar.
3. Die Queue zeigt E-Mail und Anhänge sichtbar als zusammengehörige, verschachtelte Gruppe.
4. Nach Backfill sind die 52 Alt-Text-Fehler verschwunden (verarbeitet oder vom Nutzer verworfen).
5. Bestehende `datei`-Verarbeitung unverändert (keine neue Regression in der Suite).
