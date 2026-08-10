# Projektstatus – Momentaufnahme

**Generiert:** 2026-05-02 · **Zuletzt aktualisiert:** 2026-08-10  
**Schema-Version:** 67 (Migrationen laufend, siehe Deploy-Warnungen)

> ⚠️ **Abschnitte 1–3 unten sind Stand 2026-06-12 (Schema 42) und veraltet** — nur als grobe Modul-Übersicht lesen. Aktuelle Arbeit: `docs/TODO.md` · Umsetzungs-Historie: `docs/CHANGELOG.md` · Entscheidungen: `docs/DECISIONS.md`.

---

## 0. Betrieb & Deploy-Warnungen (aktuell, 2026-08-10)

### ⚠️ Dev läuft auf Branch `abschlussbericht` (stapelt auf `intake-review-sichtbarkeit`), enthält kritische Hotfixes (2026-08-06)
Die Dev-Container binden dieses Arbeitsverzeichnis; aktueller Branch `abschlussbericht`. Der Branch trägt neben dem Abschlussbericht-Feature jetzt auch die **E-Mail-Import-Hotfixes** (`34342daa` Endlos-Poll-Loop/FK-Guard, `8e9b50ea` Prüfbericht-Schema + Validierungsregeln). **Diese Fixes MÜSSEN vor bzw. mit jedem Prod-/Main-Deploy des E-Mail-Imports ankommen** — ohne sie füllt der Poll-Loop bei der ersten Mail zu einer lokal fehlenden Akte erneut Platte und DB mit Dubletten (Detail: CHANGELOG 2026-08-06). Bei Klärung der Merge-Reihenfolge (TODO „Intake-Review-Sichtbarkeit") ggf. Cherry-Pick der beiden Commits nach `main` vorziehen. Branch nicht wechseln, solange die Container laufen.
**Stand 2026-08-10:** Obendrauf liegen jetzt auch die **Übersicht-Bugfixes** (`f6fd2f3d`, u. a. Crash der Regulierungsdetails-Karte bei fehlender Abrechnungsart + WBW > 0 — betrifft die standardmäßig offene Karte im Übersicht-Tab). Bei Cherry-Pick-Überlegungen Richtung `main` mitzählen; Details CHANGELOG 2026-08-10.

### Dubletten-Bereinigung 2026-08-06 — Backup-Aufbewahrung
Nach dem Poll-Loop wurden `dokumente` (53.216→789 Zeilen) und `/app/uploads` (−106.266 Dateien, ~222 GB) bereinigt (Freigabe RA Schatz). Vollständiges DB-Backup liegt auf dem `dev-data`-Volume: `/app/data/unfallakten.db.bak_pre_dubletten_cleanup_20260806_155109` (50 MB). Nach einer Kontrollfrist (Vorschlag: ~4 Wochen, sobald keine fehlenden Dokumente auffallen) kann es gelöscht werden. Registry-YAML-Änderungen brauchen einen Backend-Restart (Reloader überwacht nur .py).

### ⚠️ Aktenanlage: OMA-Export-Ordner konfigurieren (Deploy-Voraussetzung)
- `.env`: `OMA_EXPORT_HOST_PFAD` = Host-Pfad des Ordners, den RA-MICRO auf OMA-XML überwacht (Default `./oma_export`, nur für Dev-Tests ohne RA-MICRO-Import). Container-Pfad ist fest `/app/oma_export` (`OMA_EXPORT_PFAD`, gesetzt in beiden Compose-Dateien).
- Nach `.env`-Änderung wie immer: `docker compose up -d --force-recreate backend`.
- `/oma_export/` ist in der Projekt-`.gitignore` (XML enthält personenbezogene Mandantendaten — nie committen).
- Migration 66 (`aktenanlage_vorgaenge`) folgt der bestehenden Regel „Migration vor App-Code" (s. u.); läuft auf Bestands-DBs automatisch beim Start.
- Erkennung neuer Akten nutzt `tblAkten.dtAnlage` (read-only) — Existenz der Spalte wird beim ersten echten Import verifiziert; bei Fehlern degradiert die Erkennung still auf „manuell zuordnen".

### Backend-Vollsuite: vorbestehender Alt-Cluster (230 Failures, Stand 2026-07-30)
`pytest backend/tests/` zeigt 230 Failures — **identisch auf `main` und `aktenanlage`** (Gegenlauf 2026-07-30), also nicht durch neue Arbeit verursacht. Ursachen u. a. Auth-Bootstrap-Kollision bei Gesamtlauf, `test_modul6`-Config-Checks im Container, `test_intake_akten_matching` Score-Drift. Deckt sich in Teilen mit den dokumentierten P-01–P-03 (Abschnitt 3). Sanierung = eigenes Vorhaben; bis dahin gilt: fokussierte Suiten je Feature sind maßgeblich.

### ⚠️ E-Akte-Mount nach jedem Docker-/PC-Neustart erneuern (2026-07-23 diagnostiziert)
Der CIFS-Mount des E-Akte-Shares überlebt keinen Neustart und muss in der **Docker-Desktop-VM** gesetzt werden (`wsl -d docker-desktop`, NICHT die Standard-WSL-Distro — der Container bindet `/mnt/eakte` aus der VM). Exakter Befehl + Hinweise (Benutzername mit Leerzeichen → Quotes; danach `docker restart unfallakten-backend-dev`): Header von `docker-compose.yml`. Zugangsdaten: `EAKTE_SMB_USER`/`EAKTE_SMB_PASSWORD` in `.env` (unversioniert). Die früher dokumentierten Zugangsdaten `admin/passwort` waren ein Platzhalter und werden vom Server abgelehnt.

### ⚠️ Prod-Bestands-DBs: mutmaßliche Schema-Drift vor Go-Live prüfen
Auf der Dev-DB fehlten Spalten trotz korrekter `schema_version` — Prod-Bestands-DBs sind vermutlich ebenso betroffen. Vor dem Kollegen-/Prod-Rollout prüfen und ggf. per `ALTER TABLE` nachziehen (jeweils Backup zuerst):
- `beteiligte.vertreter_name` / `beteiligte.vertreter_funktion` — Drift (fehlten in aktiver Registry trotz „Migration 23") jetzt **forward-only per Migration 63 behoben** (idempotenter `ALTER`, additiv in `schema.py`-Basis-CREATE nachgezogen). Bestands-DBs bekommen die Spalten beim Migrationslauf automatisch; kein manueller `ALTER` mehr nötig.
- **NEU `firmen_vertreter` (Migration 62)** — globaler Firmen-Vertreter-Speicher, existiert **nur per Migration** (nicht in `schema.py`-Basis). Bestands-Prod-DB MUSS Migration 62+63 laufen lassen, bevor der Klage-Wizard-Code startet (sonst wirft `POST /firmen/vertreter/speichern` bzw. der Klage-Serializer `no such table`/`no such column`).
- `personenschaden.krankenhaus_aufenthalt` (Migration 60) — Dev am 2026-07-16 nachgezogen.

### ⚠️ Migrations-Reihenfolge beim Deploy
Additive Migrationen (56, 57, 59, 60 …) **müssen auf dem Prod-Volume (`/app/data`) angewandt sein, BEVOR** der neue App-Code startet — sonst wirft jedes UPDATE `no such column` und alle Dokumente landen in `pipeline_fehler`. Vor jeder Migration Volume-Backup. Bei Gunicorn (4 Worker) Migration einmal vorab laufen lassen (Worker-Race).

### ⚠️ Reloader-Migrations-Trap (nur Dev)
Der Flask-Reloader stempelt neue Migrationen mitten im inkrementellen Edit über den `else`-Kommentar-Fallback (Version gesetzt, Spalte fehlt). Aktive Dev-DB = Docker-Volume `dev-data` (`/app/data`), NICHT `backend/data/`. Migration atomar in EINEM Edit schreiben. Betroffen waren u. a. Mig 54/55/58/60.

### Prod-Rollout intake-stufe1 — bewusst vertagt
Git-Teil erledigt (2026-07-15): `intake-stufe1` → `main` per FF gemergt + gepusht, Backup-Tag `pre-rollout-main-20260715`. Deployment vertagt (kein Prod-Host, Go-Live später). Maßgebliches Runbook: `docs/ROLLOUT-intake-stufe1-prod.md` — Migration 49→61 einmal vorab, Prod-Backup zuerst, Schema-Verifikation auf v61 vor App-Start. Beim Cutover `EREIGNISMODELL_EINGEFUEHRT_AM` auf das echte Datum setzen.

### Git-Push-Stand (2026-07-30)
`main` ist lokal **25 Commits vor `origin/main`** (u. a. V11-Nachbefunde, Review-Queue-Sortier-Toggle, UI-Kleinkram-Runde 2026-07-29, Aktenanlage-Spec/Plan) — beim nächsten Anlass pushen. Der Feature-Branch `aktenanlage` existiert nur lokal (26 Commits, Merge nach Abnahme). **Achtung:** Git-Wurzel liegt im Home-Verzeichnis (`C:\Users\HAL9000`) — NIE `git add -A` aus Home; Guardrail-`.gitignore` beachten.

### Backup
`scripts/backup.sh` (SQLite `.backup`, nicht `cp`), stündlich + täglich via Cron in `docker-compose.prod.yml`. `/data`-Mount muss **read-write** sein (WAL braucht `-shm`-Schreibzugriff, sonst „unable to open database file"). Guard-Test `test_modul6.py::TestBackupInfra`.

---

## 1. Funktioniert stabil
*(Stand 2026-06-12, Schema 42 — veraltet, siehe Hinweis oben)*

Vollständig implementierte Module mit Tests oder nachgewiesenem Laufzeit-Einsatz.

### Auth-System
`backend/auth/` — JWT (HS256), PBKDF2-HMAC-SHA256 (260k Iterationen), Middleware mit SSE-Fallback via `?token=`. Admin-Bootstrap beim Start. Tests in `test_modul2` (laufen wenn `FLASK_SECRET_KEY` gesetzt).

### Datenbankschema + Migrations
`backend/db/schema_manager.py` — 42 Migrations, idempotent. WAL-Modus, FK-Constraints, 64 MB Cache. Migration 5 (AZ als PK) ist der kritische Pivot; alle nachfolgenden Tabellen referenzieren `az TEXT`. Migration 42 (2026-06-12): `.eml`-Dateien erhalten `dateityp='sonstiges'` + `dokumentenklasse='email'` statt bisheriger Workaround-`dateityp='docx'`.

### RA-MICRO-Connector
`backend/ramicro/connector.py` — pymssql 2.3.1, TDS 7.0, `RAMICRO_AKTIV`-Flag. Zwei Datenbanken: `RAMICRO` (Akten/WDM) und `raEloakte` (E-Akte-Metadaten). Read-only garantiert.

### WDM-Regulierungsimport
`backend/ramicro/wdm_regulierung_service.py` — Liest `_tbl0WDMDaten` aus RA-MICRO, mapped 20 WDM-Variablen auf interne DB-Felder. Deutsches Dezimalformat + EUR-Suffix werden geparst.

### PDF-Klassifikation (2-stufige Kaskade)
`backend/workflow/dispatcher.py` + `backend/parsers/document_classifier.py`  
- Stufe 1: registry.json (~1.200 Marker, global gecacht)  
- Stufe 1b: `classify_document()` als Konflikt-Resolver  
- Stufe 3: Eskalation → System-Todo  
Konfidenz-Schwelle: ≥ 0.85 für Auto-Import.

### Rechnungs-Parser (PRD-23b)
`backend/parsers/` — Registry-basiert (Gutachten, Versicherung, SV-Rechnung, Abschleppkosten, Standkosten). 59 Tests grün. Cache über `rechnung_parse_cache`-Tabelle.

### E-Mail-Import + E-Mail-Workflow (PRD-22d + Redesign 2026-06-12)
`backend/email_import/` — IMAP4_SSL (Port 993), 3 Postfächer (unfall@/termin@/bussgeld@), Smart-Inbox, Fragebogen-Erkennung. Import-Log in `email_import_log`.  
**Neu (2026-06-12):** `EmailDetailView.jsx` (2-spaltig: Metadaten/Anhänge links, E-Mail-Text/PDF-Vorschau rechts). Klick im Action Board öffnet direkt die Detail-Seite. E-Mail-Gruppe in `DokumenteSection.jsx` klappbar. `nachrichten-neu`-Endpoint liefert `log_id`. `emailImport.inAkte(logId, erzwingen)` in api.js.

### OCR + SSE-Streaming (PRD-30)
`backend/services/ocr_service.py` — Tesseract + pdf2image, 300 DPI, Deutsch (deu). SSE-Endpoint mit `?token=`-Auth-Fallback.

### Regulierungs-Workflow (PRD regulierung)
`backend/routers/schaden_routes.py` + `backend/models/abrechnungsschreiben.py` — 5 Phasen, Legacy-`regulierung`-Tabelle deprecated (v14c). `berechne_abrechnungsart()` ist Single Source of Truth für fiktiv/konkret/totalschaden.

### Gebühren-Assistent (PRD-28)
`backend/services/gebuehren_service.py` + `backend/word/gebuehren_word.py` — Nr. 2300 VV RVG, 12 VU-Sonderregeln, DOCX-Kostennote via docxtpl.

### Klage-Wizard (PRD-26 + PRD-35)
`backend/routers/klage_routes.py` + `frontend/src/sections/KlageWizard.jsx` — 10 Schritte, gerichtlicher Streitwert aus `gesamtReguliert`, alle Gegner aus RA-MICRO.
PRD-35 Bug-Fixes abgeschlossen (Session 2026-05-10): vorsteuer in b_dict, wizardVerzugDatum Step 6, EinwändePanel-Preview, Manual-Edit-Schutz (wizardVerzugManuell), betragOriginal für Gefordert-Spalte.
klage_service.py: RVG-Tabelle zeigt außergerichtl. Gegenstandswert (sw_ausserg); rvg_bereits_gezahlt-Abzug mit bedingten Tabellenzeilen. Weitere DOCX-Bugs folgen in nächster Session (PRD-33).

### Portal-Sync (PRD)
`backend/services/portal_sync.py` — Outbox-Muster über `portal_sync_queue`, HMAC-SHA256-Signatur, Retry-Counter.

### Action Board / Dashboard (PRD-25b + PRD-31)
`backend/routers/dashboard_routes.py` + `frontend/src/views/ActionBoardView.jsx` + `frontend/src/sections/UebersichtSection.jsx`  
3-Spalten-Layout (Fristen / Handlungen / Nachrichten). OnboardingHub mit 7 Kacheln.  
**Achtung: 2 Dateien uncommitted** (Details: Abschnitt 3).

### Aktensuche (RA-MICRO + SQLite)
`backend/routers/aktensuche_routes.py` — Suche über beide Quellen, `TOP 100` für RA-MICRO, fuzzy-tolerant.

### Distanzprüfung
`backend/routers/distanz_routes.py` — OpenRouteService Geocoding + Routing, Textbaustein-Generierung. Erfordert `ORS_APIKEY` in `.env`.

---

## 2. In Entwicklung

Teilweise implementiert oder explizit als Stub markiert.

### TF-IDF Classifier (Stufe 2)
`backend/workflow/dispatcher.py:7` — Kommentar: *„Stufe 2: TF-IDF Classifier (erst ab Phase 4, wenn Trainingsdaten vorhanden)"*. Trainingsdaten werden bereits mit `_speichere_training()` gesammelt (in SQLite), aber Classifier-Modell existiert nicht. Derzeit springt Stufe 2 direkt zu Stufe 3 (Eskalation).

### Statistiken-View
`frontend/src/views/StatistikenView.jsx` — Charts vorhanden (Recharts: BarChart, LineChart, PieChart), aber alle Daten sind hartkodierte Konstanten (`PIE_DATA`, `MONATS` aus `config/constants.js`). Kein Backend-Endpunkt für echte Daten.

### PWA Push-Notifications
`backend/routers/akten_routes.py:483` — Kommentar: *„Stub: speichert Nachricht als Aktivitätseintrag, sendet keine Push-Notification."* Der Endpunkt `POST /akten/<id>/nachrichten` schreibt nur in `aktivitaeten`.

### E-Akte Batch-Klassifikation (Phase 3b)
Tabelle `eakte_klassifikation` wurde in Migration 26 bereits angelegt. Kein Code der sie befüllt oder liest.

### Fragebogen Akte-Anlage
`backend/email_import/import_service.py:888` — `_fragebogen_neuer_mandant_stub()` speichert nur in `fragebogen_erstkontakt`. Kommentar: *„Keine Akte-Anlage – das ist PRD-22d."* PRD-22d ist als abgeschlossen markiert, aber der Stub-Kommentar wurde nicht aktualisiert. Status unklar.

---

## 3. Bekannte Probleme

### P-01: Test-Suite — 259 Failures wegen fehlendem Env-Setup
**Ursache:** `backend/app.py:114` wirft `RuntimeError` wenn `FLASK_SECRET_KEY` nicht gesetzt ist. Alle Tests die `erstelle_app()` aufrufen (`test_modul2` bis `test_modul8`, `test_dashboard_uebersicht`, `test_prd27`) scheitern mit diesem Fehler, wenn kein `.env` gesetzt ist.

**Betroffene Tests:** ~230 Tests (alle die den Flask-App-Context benötigen)  
**Keine Code-Bugs** — Produktiv-Code ist korrekt. Tests brauchen `.env.test` oder monkeypatching.

### P-02: Test-Suite — `test_modul1` Schema-Lücken
`test_modul1.py` erstellt ein In-Memory-Schema nur bis Migrations-Stand ~10. Fehlende Tabellen:
- `kuerzungsarten` (Migration 7) → `test_alle_tabellen` schlägt fehl
- `abrechnungsschreiben` (Migration 9) → `test_status_view` schlägt fehl
- `test_doppeltes_aktenzeichen` erwartet `ValueError`, bekommt `IntegrityError` (da `az` PK ist)

### P-03: Test-Suite — `test_portal_sync` Schema-Lücken
`portal_sync.py:110` fragt `gutachten_nr` Spalte in `beteiligte` ab. Das In-Memory-Setup in `test_portal_sync.py` erstellt `beteiligte` ohne diese Spalte. 3 Tests schlagen fehl.

### P-04: v_schadensummen — Veraltetes Feld
Die View `v_schadensummen` (genutzt in `v_regulierungsstatus` und der Akte-Listenabfrage) summiert `reparaturkosten` (Legacy-Feld). Seit Migration 10 ist das korrekte Feld `rep_gutachten_netto`. Die Summen in der Übersicht sind falsch sobald fiktive Abrechnung verwendet wird.

**Betroffen:** Alle Stellen die `v_schadensummen.gesamtschaden` oder `v_schadensummen.reparaturkosten` lesen.

### ~~P-05: Uncommitted Änderungen~~ ✅ behoben (Commit 5f0a5ec, 2026-05-03)
`dashboard_routes.py`, `ActionBoardView.jsx`, `pdf_utils.py`, `dispatcher.py` committed.
Zusätzlich: `normalize_text()` mit NFKC + Zero-Width-Bereinigung, Dispatcher-Refactoring
(`PARSER_MIN_KONFIDENZ`, `_kopiere_parse_ergebnis`, `_entscheide_klasse`).

### P-06: `fastapi==0.111.0` in requirements.txt
Nicht verwendet. Installiert pydantic, starlette, uvicorn mit. Erhöht Image-Größe und Abhängigkeits-Risiko unnötig.

### P-07: Hardcoded Admin-Passwort
`backend/app.py:71` — Fallback-Passwort `Kanzlei2024!` ist im Klartext wenn `ADMIN_PASSWORT` nicht in `.env` gesetzt. In Produktionsinstanzen ohne vollständige `.env` ist dieses Passwort aktiv.

### P-08: `unfallakten/`-Verzeichnis (veraltete Codekopie)
63 Python-Dateien die nicht importiert werden. Erzeugen False-Positives bei Repository-weiten Suchen. Kein Laufzeit-Impact.

---

## 4. Offene Fragen

**~~F-01: Uncommitted Dateien committen?~~** → Erledigt (Commit 5f0a5ec, 2026-05-03)

**F-02: `test_doppeltes_aktenzeichen` — Fehlertyp klären**  
Der Test erwartet `ValueError` bei doppeltem AZ, bekommt aber `sqlite3.IntegrityError` (weil `az` PK ist). Soll `erstelle_akte()` auf `IntegrityError` prüfen und `ValueError` re-raisen? Oder soll der Test angepasst werden?

**F-03: `test_portal_sync` — `gutachten_nr` in Beteiligte**  
Welche Migration fügt `gutachten_nr` zu `beteiligte` hinzu? Das Test-Setup muss aktualisiert werden. Alternativ: Spalte aus `_build_payload()` entfernen wenn sie nicht existiert.

**F-04: Statistiken-View — Roadmap**  
`StatistikenView.jsx` hat vollständige Chart-Infrastruktur mit Dummy-Daten. Wann wird ein `/statistiken/`-Endpunkt gebaut? Was soll gemessen werden (Akten/Monat, Regulierungssummen, Durchlaufzeiten)?

**F-05: Fragebogen-Stub — Ist PRD-22d wirklich fertig?**  
`_fragebogen_neuer_mandant_stub` enthält Kommentar *„Keine Akte-Anlage – das ist PRD-22d"*, aber PRD-22d gilt als abgeschlossen. Entweder ist die Akte-Anlage doch nicht implementiert, oder der Kommentar ist veraltet.

**F-06: TF-IDF Classifier — Wann Phase 4?**  
Trainingsdaten werden seit einiger Zeit gesammelt. Wann ist genug Datenvolumen vorhanden um den Classifier zu trainieren? Wie wird der Trainings-Trigger ausgelöst?

**F-07: Portal-Sync Dead-Letter**  
`portal_sync_queue` hat `retry_count`, aber kein maximales Retry-Limit und keine Dead-Letter-Logik. Bei dauerhaftem Portal-Ausfall wächst die Queue unbegrenzt. Ist das acceptable?

---

## 5. Aktueller Sprint

**Session 2026-06-12 — E-Mail-Workflow Redesign**

- `EmailDetailView.jsx` neu: 2-spaltige Detail-Seite mit PDF-Vorschau im Rechts-Panel
- `ActionBoardView.jsx` / `App.jsx`: Klick auf E-Mail öffnet Detail-Seite direkt (nicht mehr Akte-Übersicht)
- `DokumenteSection.jsx`: E-Mail-Gruppe klappbar am Ende des Dokumente-Tabs
- `EmailKarte.jsx`: „▶ öffnen"-Button im Stream
- `UnfallEmailView.jsx`: `geoeffneteEmail`-State, `initialEmailId`-Prop, `onEmailGeoffnet`-Callback
- `api.js`: `emailImport.inAkte(logId, erzwingen)` mit JSON-Body, `InAkteButton` refaktoriert
- Migration 42: `.eml` dateityp='sonstiges', dokumentenklasse='email'
- `nachrichten-neu`: liefert `log_id` Feld
- 12 Commits gepusht, 7 relevante Backend-Tests grün

**Nächste Session:** PRD-33 (Klage-Wizard DOCX-Bugs) oder PRD-25c (Mandantenkommunikation). Außerdem: noch unstaged Dateien aus vorheriger Session committen (backend/ramicro/adress_service.py, Router-Dateien, EinstellungenView.jsx).
