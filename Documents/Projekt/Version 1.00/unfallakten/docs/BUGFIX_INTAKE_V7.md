# Bugfix-Tracking: Code-Review Intake-Pipeline v7

> **Quelle:** Multi-Agent-Code-Review vom 2026-07-12 (Branch `intake-stufe1`, Diff `main...HEAD`, 175 Dateien).
> 39 bestätigte Funde (4 Finder-Agenten, jeder Fund unabhängig verifiziert, 0 widerlegt) → nach Zusammenführung von Mehrfach-Funden derselben Stelle **30 distinkte Bugs**.
>
> **Arbeitsregeln für alle Fixes:**
> - TDD: erst fehlschlagender Test, dann Fix. Kein Refactoring über den Fix hinaus.
> - RA-MICRO bleibt **read-only** (betrifft v.a. BUG-08).
> - Baseline muss grün bleiben: Backend **204f/732p** (Failures nur in bekannten Alt-Clustern, null in Pipeline-v7-Dateien) + **44 Frontend-Tests**.
> - Beim Abhaken: `[x]` setzen und Commit-Hash hinter den Titel schreiben.

## Status-Übersicht

| ID | Prio | Datei | Kurztitel | Status |
|---|---|---|---|---|
| BUG-01 | P0 | `backend/email_import/import_service.py:251` | Fragebogen-Daten gehen komplett verloren | **behoben** ✅ |
| BUG-02 | P0 | `backend/email_import/import_service.py:442` | Anhänge verschwinden stumm bei Registrierungsfehler | **behoben** ✅ |
| BUG-03 | P0 | `backend/routers/dokumente_routes.py:151` | Upload-Ziel-Akte wird verworfen → Falschablage | **behoben** ✅ |
| BUG-04 | P0 | `backend/routers/email_routes.py:368` | Alt-E-Mails: In-Akte-Import ersatzlos gesperrt | **behoben** ✅ |
| BUG-05 | P1 | `backend/services/eingehende_ereignisse.py:466` | Beträge werden verhundertfacht (Punkt-Dezimal) | **behoben** ✅ |
| BUG-06 | P1 | `backend/routers/intake_routes.py:530` | Verworfene/bereits freigegebene Dokumente freigebbar | **behoben** ✅ |
| BUG-07 | P1 | `backend/routers/intake_routes.py:660` | Ereignis-Anker zeigt auf Dokument fremder Akte | **behoben** ✅ |
| BUG-08 | P2 | `backend/routers/intake_routes.py:535` | Freigabe auf RA-MICRO-only-Akten → 404 | offen |
| BUG-09 | P2 | `backend/services/fristablauf_service.py:134` | SQLite-Selbstblockade im Fristablauf-Job | offen |
| BUG-10 | P2 | `gunicorn.conf.py:19` | Scheduler laufen unter Gunicorn 4-fach parallel | offen |
| BUG-11 | P2 | `backend/routers/dokumente_routes.py:147` | Upload-Validierung (Größe/Typ/PDF-Signatur) umgangen | offen |
| BUG-12 | P2 | `backend/intake/pipeline.py:118` | O(n²)-OCR: ganzes PDF wird pro Seite neu gerendert | offen |
| BUG-13 | P2 | `backend/db/schema_manager.py:2844` | Migration 50 verletzt executescript()-Verbotsregel | offen |
| BUG-14 | P3 | `backend/intake/adapter_imap.py:327` + `pipeline.py:91` | Absender-Signale erreichen Anhänge nie | offen |
| BUG-15 | P3 | `backend/intake/akten_matching.py:87` | Absender-Mail-Match (Score 0.6) ist toter Code | offen |
| BUG-16 | P3 | `backend/intake/adapter_eakte.py:49` | Key-Mismatch `akte_az` vs. `az` — E-Akte-Quelle ohne Vorschlag | offen |
| BUG-17 | P3 | `backend/intake/akten_matching.py:47` | KFZ-Muster erkennt keine Umlaut-Kennzeichen (TÖL, FÜ …) | offen |
| BUG-18 | P3 | `backend/routers/email_routes.py:912` | Kurze E-Mail-Bodies (<10 Zeichen) werden unterdrückt | offen |
| BUG-19 | P3 | `backend/routers/intake_routes.py:136` | Queue-Sortierung: Konfidenz-Schlüssel ist toter Code | offen |
| BUG-20 | P4 | `backend/routers/intake_routes.py:141` | hole_queue lädt komplettes parse_json pro Zeile | offen |
| BUG-21 | P4 | `backend/routers/intake_routes.py:125` | 4 identische korrelierte Subselects auf zustellungen | offen |
| BUG-22 | P4 | `backend/routers/positionen_routes.py:45` | Eigenes `_pruefe_akte` ohne AZ-Normalisierung | offen |
| BUG-23 | P4 | `backend/email_import/import_service.py:67` | IMAP-Config dupliziert, EMAIL_FOLDER/MAX_FETCH ignoriert | offen |
| BUG-24 | P4 | `backend/intake/adapter_imap.py:178` | `_html_zu_text` ist divergierte Kopie aus email_parser | offen |
| BUG-25 | P4 | `backend/intake/_persistenz.py:30` | Arbeitskopie-Set dupliziert `archiv._KONVERTER`-Keys | offen |
| BUG-26 | P4 | `frontend/src/views/ReviewQueueView.jsx:19` | KLASSEN hartcodiert statt aus Backend-Registry | offen |
| BUG-27 | P4 | `backend/services/positionsstatus_service.py:77` | Toter Parameter `hat_bestritten_only` | offen |
| BUG-28 | P4 | `backend/intake/registry_loader.py:43` | `Registry.fehler` wird nie befüllt (totes Feld) | offen |
| BUG-29 | P4 | `backend/services/eingehende_ereignisse.py:232` | `date.today()`-Block 4× copy-gepastet | offen |
| BUG-30 | P4 | `frontend/src/views/ReviewQueueView.jsx:503` | `wartAufWorker` pollt nach Unmount unkündbar weiter | offen |

---

## P0 — Kritisch: Stiller Datenverlust / Falschablage

### - [x] BUG-01 — Fragebogen-Daten gehen komplett verloren
- **Fix (2026-07-13, Commit 6c858aa1):** Neuer Helper `_fragebogen_in_intake_queue()` legt den Unfallbogen unter `INTAKE_REVIEW_PFLICHT` verlustfrei als Text-`intake_dokument` (JSON-Payload) + `zustellung` in die Review-Queue; das Aktenzeichen wird als `az`-Signal durchgereicht (Akte im Freigabe-Dialog vorbelegt). Fehler propagieren (kein stiller Verlust → Retry). **Feld-Übernahme in die Akte beim Freigeben ist bewusst NICHT Teil dieses P0-Fixes (eigener Folge-Task).** Tests: `test_bugfix_p0_intake_v7.py::TestBug01FragebogenInQueue` (4).
- **Datei:** `backend/email_import/import_service.py:251`
- **Problem:** Unter `INTAKE_REVIEW_PFLICHT` (Default **True**) sind `_ergaenze_mandant`, `_ergaenze_gegner`, `_ergaenze_unfalldetails`, `_ergaenze_personenschaden` und `_speichere_fragebogen_json` No-ops. Der Fragebogen-Zweig returned in `_verarbeite_eine` aber **vor** dem Intake-Adapter-Aufruf (Zeile 439–443), und der IMAP-Adapter akzeptiert ohnehin keine `.json`-Anhänge (`_ERLAUBTE_ANHANG_ENDUNGEN` in `adapter_imap.py:126`). Der versprochene Ersatzpfad „Vorschläge im Review-Freigabe-Dialog" existiert nirgends (kein Fragebogen-Code in `backend/intake/`, `intake_routes.py` oder `ReviewQueueView.jsx`).
- **Auswirkung:** Mandant füllt den Unfallbogen aus, Mail mit `unfallbogen_*.json` trifft auf unfall@ ein. Import markiert sie als gelesen, Log zeigt `status='zugeordnet'` — aber kein Feld landet in der Akte, der JSON-Anhang wird nicht gespeichert, das Dokument erscheint auch nicht in der Review-Queue. Daten unsichtbar verloren (nur noch in der .eml auf Disk).
- **Fix-Richtung:** Fragebogen-Pfad muss auch unter Review-Pflicht funktionieren (Direktverarbeitung für Fragebogen-Mails beibehalten oder echten Review-Ersatzpfad bauen).

### - [x] BUG-02 — Anhänge verschwinden stumm bei Registrierungsfehler
- **Fix (2026-07-13, Commit 6c858aa1):** Scheitert der IMAP-Adapter (unter Review-Pflicht der einzige Registrierungspfad), wird jetzt `logger.error` geloggt, der Log-Eintrag auf `status='fehler'` gesetzt und die Mail **nicht** als gelesen markiert/verschoben → nächster Poll holt sie erneut. Im Alt-Pfad (Flag=false) bleibt der Adapter Best-Effort (Doppelschreiber). Tests: `test_bugfix_p0_intake_v7.py::TestBug02StillerFehler` (2).
- **Datei:** `backend/email_import/import_service.py:442`
- **Problem:** Der alte Fehlerpfad (`logger.error` + `status='fehler'` im Import-Log, Zeile 328–330) ist ersatzlos entfallen. Der jetzt einzige Registrierungspfad `_intake_imap` (Zeile 439–443) ist als Best-Effort mit `except Exception → logger.debug` verpackt; danach wird die Mail trotzdem als gelesen markiert und nach UA_Eingang verschoben. `bericht['anhaenge']` wird in Zeile 334 hochgezählt, als wäre die Registrierung gelungen.
- **Auswirkung:** SQLite kurz gelockt oder Migration fehlt → Exception verschwindet auf DEBUG, Mail gilt als `zugeordnet`. Anhänge (z. B. Regulierungsschreiben mit Fristsetzung) erscheinen weder in Review-Queue noch Akte, kein Fehlerindikator; der nächste Poll holt die Mail nicht erneut (nur ungelesene).
- **Fix-Richtung:** Fehler als `status='fehler'` loggen (mind. `logger.error`), Mail bei fehlgeschlagener Registrierung nicht als erledigt behandeln.

### - [x] BUG-03 — Upload-Ziel-Akte wird verworfen → Falschablage
- **Fix (2026-07-13, Commit 6c858aa1):** `adapter_upload.verarbeite_datei()` bekommt Parameter `ziel_akte`; die Route `POST /akten/<id>/dokumente` reicht die Ziel-Akte durch, sie landet als `signale['az']` → `akten_matching.finde_kandidaten` belegt sie als Top-Kandidat (Score 0.9–1.0) vor. Tests: `test_bugfix_p0_intake_v7.py::TestBug03UploadZielAkte` (2). Key `az` deckt sich mit BUG-16 (E-Akte) — dort denselben Mechanismus nutzen.
- **Datei:** `backend/routers/dokumente_routes.py:151`
- **Problem:** Die Invariante „Upload via `POST /akten/<id>/dokumente` landet garantiert in genau dieser Akte" ist unter Review-Pflicht entfernt: die Ziel-Akte wird nur als String in `roh_referenz` (`upload/akte:<az>`) abgelegt, den weder `akten_matching.py` noch `queue.py`/`intake_routes.py` noch `ReviewQueueView.jsx` auswerten. Die Akten-Zuordnung im Review-Dialog kommt ausschließlich aus dem Text-Matching.
- **Auswirkung:** Upload in Akte 285/26; im Brief steht nur das gegnerische Schadenaktenzeichen → Review-Queue zeigt keinen oder einen **falschen** Akten-Kandidaten vorbelegt; ein Klick auf Freigeben heftet das Dokument in die falsche Akte.
- **Fix-Richtung:** Ziel-Akte als Signal durchreichen (z. B. `signale['az']`) und im Review-Dialog als Top-Kandidat/Vorbelegung anzeigen. Zusammen mit BUG-16 lösen (gleiches Muster).

### - [x] BUG-04 — Alt-E-Mails: In-Akte-Import ersatzlos gesperrt
- **Fix (2026-07-13, Commit 6c858aa1):** Neuer Helper `_hat_intake_dokumente(log_id)` (Link `zustellungen.roh_referenz == email_import_log.eml_pfad`). Die Route liefert 202 (Review-Queue) nur noch, wenn Intake-Dokumente existieren; sonst greift der Alt-Pfad `importiere_in_akte`. Tests: `test_s19d_in_akte_flag.py` (Fallback + 202-mit-Intake) + angepasste e2e/Guard-Tests. Tests: `test_s19d_in_akte_flag.py` (5).
- **Datei:** `backend/routers/email_routes.py:368`
- **Problem:** `log_in_akte_importieren` gibt unter Review-Pflicht bedingungslos 202 „E-Mail und Anhänge liegen dort bereits vor" zurück, ohne zu prüfen, ob für den Log-Eintrag überhaupt `intake_dokumente`/`zustellungen` existieren. Für Alt-Einträge (vor dem Branch-Deployment) und für Fälle, in denen der Best-Effort-Adapter fehlschlug (BUG-02), ist der .eml-basierte Import damit gesperrt.
- **Auswirkung:** Sachbearbeiter öffnet einen älteren Log-Eintrag (`in_akte_importiert=0`), klickt „In Akte importieren" → Hinweis auf die Review-Queue, dort ist aber nichts. Anhänge dieser E-Mail sind über die UI dauerhaft nicht mehr in die Akte übernehmbar (kein Backfill-Script; `scripts/backfill_textpfad.py` behandelt nur den Text-Pfad).
- **Fix-Richtung:** Vor dem 202 prüfen, ob Intake-Dokumente zum Log-Eintrag existieren; sonst Alt-Pfad `importiere_in_akte` zulassen (oder Backfill anbieten).

---

## P1 — Kritisch: Falsche Daten in der Akte

### - [x] BUG-05 — Beträge werden verhundertfacht (Punkt-Dezimal)
- **Fix (2026-07-13, Commit `b6826d91`):** `_feld_zu_zahl` delegiert die String-Zerlegung jetzt an den format-sicheren Helper `backend/parsers/pdf_utils.parse_betrag`; die int/float-Kurzschluss-Behandlung bleibt. `'850.00' → 850.0` (statt 85000.0), `'1234.56' → 1234.56` (statt 123456.0); `'1.234,56'`/`'1011,50'`/Ganzzahlen unverändert korrekt. Unparsbare Werte → `None` (kein Betrag statt falscher Betrag — deckt sich mit dem P1.5e-Prinzip „nur echte Beträge buchen"; die Position wird dann als Fakt ohne Betrag gebucht). **Bekannte Grenze:** US-Tausendertrennung `'1,234.56'` liefert `None` (parse_betrag unterstützt sie trotz Docstring nicht) — im deutschen Rechtskontext praktisch irrelevant und sicher (kein 100×-Fehler). Tests: `test_bugfix_p1_intake_v7.py::TestBug05FeldZuZahl` (8).
- **Datei:** `backend/services/eingehende_ereignisse.py:466` (`_feld_zu_zahl`)
- **Problem:** `_feld_zu_zahl` unterstellt strikt deutsche Notation und entfernt **alle** Punkte (`replace('.','').replace(',','.')`). Die Feldwerte kommen aus `llm_service.extrahiere_nach_schema`, das das rohe LLM-JSON ohne Format-Normalisierung durchreicht (`_RESPONSE_FORMAT = None`, LM Studio kann kein response_format) — Strings mit Dezimalpunkt wie `"850.00"` sind häufig.
- **Auswirkung:** `_feld_zu_zahl('850.00') → 85000.0`; `erzeuge_aus_freigabe` bucht `rechnung_eingegangen` mit 85.000,00 € statt 850,00 €. PositionsDashboard und Regulierungs-Ableitung zeigen 100-fach falsche Forderungsbeträge, ohne dass der Reviewer eine Abweichung sieht.
- **Fix-Richtung:** Vorhandenen format-sicheren Helper `backend/parsers/pdf_utils.parse_betrag` verwenden (kann `1.234,56`, `1234.56`, `1,234.56`). *(3× unabhängig gefunden.)*

### - [x] BUG-06 — Verworfene/bereits freigegebene Dokumente freigebbar
- **Fix (2026-07-13, Commit `b6826d91`):** Guard in `post_freigabe` direkt nach dem Not-Found-Check (Pendant zum bestehenden `post_verwerfen`-Guard): `verworfen_am IS NOT NULL` → HTTP 409 „Dokument ist verworfen …"; `queue_status='freigegeben'` → HTTP 409 „Dokument ist bereits freigegeben." Damit erzeugen Doppel-Submits/Race-Freigaben keine zweite `dokumente`-/`freigaben`-Zeile und kein Doppel-Ereignis mehr. **Entscheidung zu BUG-07-Interaktion:** Mehrfach-Freigabe in eine *andere* Akte wird bewusst gesperrt (einfacher, sicherer Guard lt. Session-Prompt) — der `_anker_dokument_id`-Fix (BUG-07) bleibt als Defence-in-depth trotzdem korrekt. Tests: `test_bugfix_p1_intake_v7.py::TestBug06FreigabeGuards` (3). Keine Regression bei den P1.5e-Re-Freigabe-Tests (die prüfen nur Ereignis-Anzahl, nicht den Status-Code).
- **Datei:** `backend/routers/intake_routes.py:530–532` (`post_freigabe`)
- **Problem:** `post_freigabe` prüft weder `verworfen_am` noch `queue_status` (`_lade_intake` ist ein ungefiltertes `SELECT * FROM intake_dokumente WHERE id=?`). Die Gegenrichtung (Verwerfen nach Freigabe) ist in `post_verwerfen` explizit mit 409 gesperrt — hier fehlt das Pendant.
- **Auswirkung:** Kollege A verwirft ein Spam-Dokument, Kollege B (oder ein alter Browser-Tab / Doppel-Submit) gibt es trotzdem frei: `schreibe_dokument` legt eine `dokumente`-Zeile an, ein eingehendes Ereignis wird ins Positionsmodell gebucht, `queue_status` springt auf `freigegeben` (Verwerfen still aufgehoben). Doppel-Submits erzeugen doppelte `dokumente`-Zeilen.
- **Fix-Richtung:** Guard in `post_freigabe`: 409 bei `verworfen_am IS NOT NULL` oder `queue_status='freigegeben'` (Mehrfach-Freigabe in **andere** Akte ggf. bewusst erlauben — dann zusammen mit BUG-07 entscheiden).

### - [x] BUG-07 — Ereignis-Anker zeigt auf Dokument fremder Akte
- **Fix (2026-07-13, Commit `b6826d91`):** `_anker_dokument_id` erhält Parameter `akte_az` und filtert die erste Freigabe jetzt mit `WHERE intake_dokument_id=? AND akte_az=? ORDER BY id ASC LIMIT 1`. Der einzige Aufrufer (`_schreibe_freigabe_ereignisse`) reicht die Ziel-Akte durch. Damit ankert das Ereignis der Ziel-Akte auf deren eigene erste Freigabe (dokument_id), nicht mehr auf ein Dokument einer fremden Akte. Tests: `test_bugfix_p1_intake_v7.py::TestBug07AnkerZielakte` (2). Da BUG-06 die Route-seitige Mehrfach-Freigabe sperrt, ist der Fix v.a. Defence-in-depth + direkt unit-getestet.
- **Datei:** `backend/routers/intake_routes.py:660` (`_anker_dokument_id`)
- **Problem:** `_anker_dokument_id` nimmt immer die **erste** Freigabe (`SELECT dokument_id FROM freigaben WHERE intake_dokument_id=? ORDER BY id ASC LIMIT 1`, ohne `akte_az`-Filter) und überschreibt damit die frische dokument_id.
- **Auswirkung:** Freigabe erst in Akte 100/26 (dokument_id 5), nach Korrektur erneut in Akte 200/26 (dokument_id 9): das Ereignis für 200/26 verweist auf Dokument 5 der fremden Akte — Link in Ereignisliste/PositionsDashboard führt ins Leere bzw. in die falsche Akte, und der Doppelerfassungs-Guard keyed auf die fremde ID.
- **Fix-Richtung:** Anker auf die erste Freigabe **derselben Ziel-Akte** beziehen (`WHERE intake_dokument_id=? AND akte_az=?`).

---

## P2 — Schwer: Funktionsausfälle / Infrastruktur

### - [ ] BUG-08 — Freigabe auf RA-MICRO-only-Akten → 404
- **Datei:** `backend/routers/intake_routes.py:535`
- **Problem:** `post_freigabe` validiert `akte_az` nur gegen die SQLite-Tabelle `unfallakte`. Die Akten-Kandidaten der Pipeline (`_suche_in_ramicro` in `akten_matching.py`) und die AktenLiveSuche des Freigabe-Dialogs (`/aktensuche` liest RA-MICRO `tblAkten`) liefern aber auch Akten, die nur in RA-MICRO existieren. Der Alt-Pfad (`pruefe_akte` in `_helpers.py`) akzeptierte solche Akten via SimpleNamespace-Fallback.
- **Auswirkung:** Sachbearbeiter wählt den vorgeschlagenen Top-Kandidaten (z. B. `162/26KO`) → HTTP 404 „Akte nicht gefunden"; das Dokument lässt sich für diese Akte gar nicht ablegen, ohne Hinweis, dass die Akte erst importiert werden muss.
- **Fix-Richtung:** Verhalten des Alt-Pfads wiederherstellen (Fallback wie `pruefe_akte`) oder beim Freigeben die Akte automatisch aus RA-MICRO anlegen. **RA-MICRO bleibt read-only** — Anlage nur in SQLite.

### - [ ] BUG-09 — SQLite-Selbstblockade im Fristablauf-Job
- **Datei:** `backend/services/fristablauf_service.py:134–137` (`verarbeite_faellige_todos`)
- **Problem:** Die ganze Schleife läuft in einem äußeren `with get_connection()`; nach der ersten Todo hält `UPDATE todos` eine unkommittierte Schreibtransaktion. `schreibe_ereignis` öffnet pro Todo eine **neue** Verbindung, die auf denselben SQLite-Write-Lock wartet (timeout=30).
- **Auswirkung:** Nächtlicher 03:15-Job mit ≥2 fälligen Fristen: nur die erste bekommt ihr Ereignis, jede weitere stallt 30 s und scheitert mit „database is locked" (als Warning geschluckt). Fristablauf-Ereignisse fehlen tagelang; während der Lock-Haltezeit schlagen auch Freigaben/Uploads mit 500 fehl.
- **Fix-Richtung:** Eine Verbindung durchreichen (Parameter für `schreibe_ereignis`) oder pro Todo committen. *(2× unabhängig gefunden.)*

### - [ ] BUG-10 — Scheduler laufen unter Gunicorn 4-fach parallel
- **Datei:** `gunicorn.conf.py:19` (+ `backend/app.py`, `erstelle_app()`)
- **Problem:** Die neue Prod-Config startet bis zu 4 Worker; `erstelle_app()` registriert in **jedem** Worker einen eigenen APScheduler (imap_polling 60 s, intake_worker 10 s, fristablauf cron 03:15). Nur der Intake-Tick ist per Lease geschützt.
- **Auswirkung:** 4 Worker pollen dasselbe Postfach → Race vor der message_id-Dedup, doppelte `email_import_log`-Zeilen und doppelte Zustellungen in der Review-Queue; um 03:15 lesen 4 Prozesse dieselben fälligen Todos → bis zu 4-fach duplizierte Fristablauf-Ereignisse (verschärft BUG-09).
- **Fix-Richtung:** Scheduler nur in genau einem Prozess starten (eigener Prozess/Worker, Env-Flag, oder DB-Lease für alle Jobs analog Intake-Tick). *(2× unabhängig gefunden.)*

### - [ ] BUG-11 — Upload-Validierung (Größe/Typ/PDF-Signatur) umgangen
- **Datei:** `backend/routers/dokumente_routes.py:147` (Review-Pflicht-Pfad Zeile 144–164)
- **Problem:** Der Review-Pflicht-Upload umgeht `verarbeite_upload()` und damit `_validiere_datei` (Erweiterungs-Whitelist, Leere-Datei-Check, MAX_DATEIGROESSE), `validiere_pdf` (PDF-Signatur) und den `GUELTIGE_TYPEN`-Check. `adapter_upload.verarbeite_datei` akzeptiert beliebige Bytes mit beliebiger Endung (Fallback `bin`).
- **Auswirkung:** 300-MB-Video oder korrupte/getarnte .pdf → statt sofortigem 422 antwortet das Backend 202, die Datei landet in uploads/intake und bleibt als `pipeline_fehler` hängen; der Benutzer bekommt nie die klare Fehlermeldung des Alt-Pfads.
- **Fix-Richtung:** Validierung vor `_intake_upload` ziehen (dieselben Checks wie der Alt-Pfad).

### - [ ] BUG-12 — O(n²)-OCR: ganzes PDF wird pro Seite neu gerendert
- **Datei:** `backend/intake/pipeline.py:118` (`_ocr_seite`)
- **Problem:** `_ocr_seite` ruft für **jede** OCR-bedürftige Seite `ocr_service.pdf_zu_bildern(pdf_bytes)` auf, das alle Seiten mit 300 dpi rendert (`convert_from_bytes` ohne first_page/last_page) und dann nur `bilder[seite_nr-1]` verwendet.
- **Auswirkung:** 30-seitiger Scan → 900 statt 30 Seiten-Renderings; der Pipeline-Tick dauert zig Minuten, belegt Gigabytes RAM, das 300-s-Lease läuft ab, ein zweiter Worker beginnt dasselbe Dokument nochmal — die Single-Slot-Queue verhungert, neue Post erscheint nicht in der Review-Queue.
- **Fix-Richtung:** Einmal vor der Schleife konvertieren oder `first_page`/`last_page` von pdf2image nutzen. *(2× unabhängig gefunden.)*

### - [ ] BUG-13 — Migration 50 verletzt executescript()-Verbotsregel
- **Datei:** `backend/db/schema_manager.py:2844` (Migration 50)
- **Problem:** Migration 50 kombiniert `conn.executescript()` mit nachfolgenden `ALTER TABLE` ohne explizites `conn.commit()` davor/danach — exakt das dokumentierte Verbotsmuster (executescript committet implizit; bei Abbruch/Dev-Reloader fallen ALTER-Spalten und schema_version-Stempel auseinander). Die neuen Migrationen 52–55 halten die Regel ein.
- **Auswirkung:** Version 50 gilt als eingespielt, Spalten (`aktivlegitimation_*`) können fehlen — derselbe Fall trat bei Migration 54+55 bereits real auf.
- **Fix-Richtung:** Migration 50 auf das Muster der Migrationen 52–55 umbauen (einzelne execute-Aufrufe, explizite Commits).

---

## P3 — Mittel: Matching-/Signal-Qualität & UI-Korrektheit

### - [ ] BUG-14 — Absender-Signale erreichen Anhänge nie
- **Dateien:** `backend/intake/adapter_imap.py:327` + `backend/intake/pipeline.py:91`
- **Problem:** Anhang-Zustellungen bekommen nur `signale={'dateiname': ...}`; die Absender-Registry-Signale (`klasse_kandidat`, `versicherer_name`, `vertrauensstufe`) werden nur in die Body-Zustellung gemerged, und `pipeline._lade_zustellungs_signale` liest nur die Zustellungen des Dokuments selbst (keine Vererbung über `parent_id`).
- **Auswirkung:** Versicherer-Domain ist in `email_absender_vorlagen` registriert (z. B. `klasse_kandidat='abrechnungsschreiben'`), schickt das Abrechnungsschreiben als PDF-Anhang: die Stufe-1-Klassifikation des PDFs bekommt keinen Signal-Boost und fällt bei markerarmen Scans auf `sonstiges/0.5` zurück — genau der Hauptanwendungsfall der S1.4-Registry (Versicherungspost als PDF-Anhang) verliert die Registry komplett.
- **Fix-Richtung:** Signale an Anhang-Zustellungen vererben (beim Erzeugen im Adapter oder beim Laden via `parent_id`).

### - [ ] BUG-15 — Absender-Mail-Match (Score 0.6) ist toter Code
- **Datei:** `backend/intake/akten_matching.py:87` (`_sammle_signale_mails`)
- **Problem:** `_sammle_signale_mails` erwartet Signal-Keys `absender`/`absender_email`, die kein Adapter jemals in `signale_json` schreibt — die Absenderadresse liegt nur in der Spalte `zustellungen.absender`.
- **Auswirkung:** Der geplante 0.6-Score-Treffer `beteiligten_mail` (Mandant schreibt von der in `beteiligte.email` hinterlegten Adresse) feuert nie; ein Drittel der Score-Staffel ist wirkungslos, ohne dass ein Test es bemerkt.
- **Fix-Richtung:** Absenderadresse aus der Spalte lesen oder als Signal-Key mitschreiben (zusammen mit BUG-14 lösen).

### - [ ] BUG-16 — Key-Mismatch `akte_az` vs. `az`: E-Akte-Quelle ohne Vorschlag
- **Datei:** `backend/intake/adapter_eakte.py:49`
- **Problem:** Der E-Akte-Adapter schreibt das bekannte Aktenzeichen als Signal-Key `akte_az`, aber `akten_matching.finde_kandidaten` liest nur `az`/`aktenzeichen`/`erkannt_az` (analog zum früheren `sonstiges_wdm`/`extra_wdm`-Key-Mismatch-Bug).
- **Auswirkung:** Dokument aus der E-Akte von 285/26 importiert → Review-Queue zeigt „Keine Akten-Vorschläge", obwohl die Quelle die Akte kannte; jede E-Akte-Zustellung muss manuell zugeordnet werden.
- **Fix-Richtung:** Key vereinheitlichen (Remap oder Adapter anpassen); denselben Mechanismus für BUG-03 (Upload-Ziel-Akte) nutzen.

### - [ ] BUG-17 — KFZ-Muster erkennt keine Umlaut-Kennzeichen
- **Datei:** `backend/intake/akten_matching.py:47` (`_KFZ_MUSTER`)
- **Problem:** Zeichenklasse `[A-ZAEOU]` — A, E, O, U sind in A-Z redundant, gemeint waren offensichtlich ÄÖÜ. Deutsche Unterscheidungszeichen wie TÖL, FÜ, BÖ, GÖ matchen nie; es gibt auch keine Umlaut-Normalisierung im Umfeld.
- **Auswirkung:** Dokument nennt `TÖL-A 123` → kein KFZ-Kandidat (Score 0.7), `_suche_kfz_in_sqlite` wird nie abgefragt, Review-Dialog ohne Akten-Vorschlag trotz exakt passendem Beteiligten-Kennzeichen.
- **Fix-Richtung:** `[A-ZÄÖÜ]` (ggf. plus `\b`-Verhalten bei Umlauten prüfen — Python-Unicode-`\b` sieht Ö als Wortzeichen). *(2× unabhängig gefunden.)*

### - [ ] BUG-18 — Kurze E-Mail-Bodies (<10 Zeichen) werden unterdrückt
- **Datei:** `backend/routers/email_routes.py:912` (`log_eintrag_meta`)
- **Problem:** Neu: `body_text` wird nur zurückgegeben, wenn `len(body_stripped) >= 10`, sonst `""` — die alte Zusicherung „lesbarer Plaintext-Body wird immer angezeigt" ist für legitime Kurz-Antworten entfallen.
- **Auswirkung:** Mandant/Versicherer antwortet „OK, passt" oder „Ja" → Detailansicht zeigt leeren Body; der Sachbearbeiter hält die Mail für inhaltsleer und übersieht eine ggf. rechtlich relevante Zustimmung.
- **Fix-Richtung:** Schwellwert entfernen oder nur auf reine Whitespace-/Artefakt-Bodies anwenden.

### - [ ] BUG-19 — Queue-Sortierung: Konfidenz-Schlüssel ist toter Code
- **Datei:** `backend/routers/intake_routes.py:136` (`hole_queue`)
- **Problem:** `ORDER BY i.erstellt_am ASC, i.id ASC, COALESCE(i.konfidenz,0) DESC` — die eindeutige `id` vor dem Konfidenz-Schlüssel löst jede Bindung auf; das dokumentierte „dann Konfidenz absteigend" (Docstring + freigabe.md Stufe 1) findet nie statt.
- **Auswirkung:** Dokumente desselben Imports (gleiche erstellt_am-Sekunde) erscheinen in Insert- statt Triage-Reihenfolge; der tote Schlüssel verschleiert das.
- **Fix-Richtung:** Reihenfolge der Sortierschlüssel korrigieren (`erstellt_am ASC, konfidenz DESC, id ASC`) — oder toten Schlüssel streichen, falls die Insert-Reihenfolge gewollt ist (dann Docstring/Spec anpassen). *(2× unabhängig gefunden.)*

---

## P4 — Niedrig: Performance / Code-Hygiene

### - [ ] BUG-20 — hole_queue lädt komplettes parse_json pro Zeile
- **Datei:** `backend/routers/intake_routes.py:141`
- **Problem:** Für jede Queue-Zeile wird das komplette `parse_json` (enthält `text_gesamt` des ganzen Dokuments) geladen und deserialisiert, nur um `akten_kandidaten[0]` zu extrahieren — bei jedem 30-s-Frontend-Poll.
- **Auswirkung:** Queue mit 100 OCR-Dokumenten à ~100 KB Volltext → ~10 MB JSON-Deserialisierung pro Poll.
- **Fix-Richtung:** `json_extract(parse_json,'$.akten_kandidaten[0]')` im SELECT oder Top-Kandidat als eigene Spalte beim Pipeline-Stempeln.

### - [ ] BUG-21 — 4 identische korrelierte Subselects auf zustellungen
- **Datei:** `backend/routers/intake_routes.py:125`
- **Problem:** `hole_queue` nutzt vier identische korrelierte Subselects (je `ORDER BY z.id LIMIT 1`) für `zustellung_id`/`parent_id`/`absender`/`betreff` statt eines JOINs auf die erste Zustellung.
- **Auswirkung:** 4×N Subquery-Ausführungen pro Poll; `zustellungen` wächst unbegrenzt.
- **Fix-Richtung:** LEFT JOIN auf `MIN(z.id)` pro `intake_dokument_id`.

### - [ ] BUG-22 — Eigenes `_pruefe_akte` ohne AZ-Normalisierung
- **Datei:** `backend/routers/positionen_routes.py:45`
- **Problem:** Eigene `_pruefe_akte`-Implementierung mit exaktem az-Vergleich statt des Helpers `backend/routers/_helpers.pruefe_akte` mit `_normiere_az` (Projekt-Regel: Rückgabewert immer für az-Extraktion nutzen).
- **Auswirkung:** AZ-Schreibweise `28526` liefert auf `/akten/<az>/positionen/*` 404, während dieselbe Akte über andere Router funktioniert.
- **Fix-Richtung:** Helper verwenden.

### - [ ] BUG-23 — IMAP-Config dupliziert, EMAIL_FOLDER/MAX_FETCH ignoriert
- **Datei:** `backend/email_import/import_service.py:67` (`_imap_cfg_fuer_konto`)
- **Problem:** Dupliziert `polling_service._imap_config_fuer_account` mit stiller Abweichung: `folder` fest `INBOX`, `max_fetch` fest 50; `EMAIL_FOLDER`/`EMAIL_MAX_FETCH` werden ignoriert.
- **Auswirkung:** Bei konfiguriertem EMAIL_FOLDER liest der Auto-Poll den richtigen Ordner, manueller Import und UA-Verschiebung arbeiten auf INBOX — Mails werden nicht gefunden/verschoben.
- **Fix-Richtung:** Gemeinsame Config-Funktion verwenden.

### - [ ] BUG-24 — `_html_zu_text` ist divergierte Kopie aus email_parser
- **Datei:** `backend/intake/adapter_imap.py:178`
- **Problem:** `_html_zu_text` und die Body-Walk-Logik sind Kopien von `email_parser._html_zu_text`/`_extrahiere_text` — bereits divergiert: email_parser filtert unlesbaren Binär-Text (Lesbarkeits-Check über `decoded[:200]`), der Adapter nicht.
- **Auswirkung:** `intake_dokumente.structured_payload` kann Binärmüll enthalten; jede Korrektur muss doppelt gepflegt werden.
- **Fix-Richtung:** Import statt Duplikat (Muster ist im Modul für `dekodiere_email_payload` bereits etabliert).

### - [ ] BUG-25 — Arbeitskopie-Set dupliziert `archiv._KONVERTER`-Keys
- **Datei:** `backend/intake/_persistenz.py:30` (`_ARBEITSKOPIE_UNTERSTUETZT`)
- **Problem:** Handgepflegtes Set `{pdf,docx,doc,jpg,jpeg,png}` statt Ableitung aus dem Konverter-Mapping.
- **Auswirkung:** Neuer Konverter in `archiv.py` (z. B. heic) ohne Set-Nachzug → „Arbeitskopie fehlt", Dokument landet nach 3 Versuchen in `pipeline_fehler`, obwohl der Konverter existiert.
- **Fix-Richtung:** Set aus `archiv._KONVERTER.keys()` ableiten.

### - [ ] BUG-26 — KLASSEN hartcodiert statt aus Backend-Registry
- **Datei:** `frontend/src/views/ReviewQueueView.jsx:19`
- **Problem:** `KLASSEN` ist eine hartcodierte Frontend-Kopie der Backend-Registry-Klassen (`backend/registry/klassen/*.yaml`); der Ereignistyp-Katalog wird bereits per Endpoint geladen (`apiIntake.ereignistypen`), für Klassen fehlt das Pendant.
- **Auswirkung:** Neue Klasse als YAML → Reklassifikations-Dropdown kennt sie nicht.
- **Fix-Richtung:** Klassen-Endpoint analog Ereignistypen + Frontend lädt dynamisch.

### - [ ] BUG-27 — Toter Parameter `hat_bestritten_only`
- **Datei:** `backend/services/positionsstatus_service.py:77` (`_zustand`)
- **Problem:** Parameter wird im Funktionskörper nie verwendet, einziger Aufrufer übergibt fest `False`.
- **Auswirkung:** Suggeriert eine Steuerung, die nicht existiert.
- **Fix-Richtung:** Ersatzlos streichen.

### - [ ] BUG-28 — `Registry.fehler` wird nie befüllt
- **Datei:** `backend/intake/registry_loader.py:43`
- **Problem:** `Registry.fehler` als Liste initialisiert, aber alle Fehlerpfade werfen `RuntimeError` — dauerhaft leeres, totes Feld.
- **Auswirkung:** Konsumenten sehen immer `[]` und melden „alles ok".
- **Fix-Richtung:** Feld entfernen (oder Soft-Fehler tatsächlich sammeln).

### - [ ] BUG-29 — `date.today()`-Block 4× copy-gepastet
- **Datei:** `backend/services/eingehende_ereignisse.py:232` (u. a.)
- **Problem:** `from datetime import date as _date; if datum is None: datum=_date.today().isoformat()` ist in `erzeuge_aus_beleg`, `erzeuge_aus_gutachten`, `erzeuge_aus_wdm`, `erzeuge_aus_freigabe` identisch dupliziert; `ausgehende_ereignisse.py` macht es bereits mit Modul-Import + Einzeiler.
- **Auswirkung:** Reine Wartungslast.
- **Fix-Richtung:** Modul-Import + kleiner Helper.

### - [ ] BUG-30 — `wartAufWorker` pollt nach Unmount unkündbar weiter
- **Datei:** `frontend/src/views/ReviewQueueView.jsx:503`
- **Problem:** `wartAufWorker` pollt in einer unkündbaren while-Schleife bis 30 s weiter, auch wenn das DetailPanel unmountet (Dokumentwechsel erzwingt Re-Mount per `key`) — kein AbortController/mounted-Flag.
- **Auswirkung:** Klick auf ein anderes Dokument während eines Re-Parse → bis zu 20 weitere Detail-Requests für das verlassene Dokument + setState auf unmounteter Komponente (React-Warnungen, unnötige Backend-Last inkl. UPDATE-Statements des Detail-Endpoints).
- **Fix-Richtung:** Abbruch-Flag/AbortController beim Unmount bzw. Dokumentwechsel.

---

## Empfohlene Session-Aufteilung

1. **Session 1 (P0):** BUG-01–BUG-04 — Datenverlust-Pfade schließen (gemeinsamer Kontext: `INTAKE_REVIEW_PFLICHT`-Ersatzpfade in import_service/dokumente_routes/email_routes).
2. **Session 2 (P1):** BUG-05–BUG-07 — Freigabe-/Buchungs-Korrektheit in `intake_routes.py` + `eingehende_ereignisse.py`.
3. **Session 3 (P2):** BUG-08–BUG-13 — Infrastruktur (Deadlock, Scheduler, Validierung, OCR, Migration 50).
4. **Session 4 (P3):** BUG-14–BUG-19 — Matching-/Signal-Qualität (BUG-14+15+16 zusammen, gleiches Signal-Thema; BUG-03-Mechanismus wiederverwenden).
5. **Session 5 (P4):** BUG-20–BUG-30 — Performance & Hygiene (mechanisch, gut parallelisierbar).
