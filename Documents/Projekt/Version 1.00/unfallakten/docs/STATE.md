# Projektstatus – Momentaufnahme

**Generiert:** 2026-05-02 · **Zuletzt aktualisiert:** 2026-05-03  
**Schema-Version:** 40  
**Test-Suite:** 544 Tests gesammelt · 269 grün · 259 rot · 16 Errors (Details: Abschnitt 3)

---

## 1. Funktioniert stabil

Vollständig implementierte Module mit Tests oder nachgewiesenem Laufzeit-Einsatz.

### Auth-System
`backend/auth/` — JWT (HS256), PBKDF2-HMAC-SHA256 (260k Iterationen), Middleware mit SSE-Fallback via `?token=`. Admin-Bootstrap beim Start. Tests in `test_modul2` (laufen wenn `FLASK_SECRET_KEY` gesetzt).

### Datenbankschema + Migrations
`backend/db/schema_manager.py` — 40 Migrations, idempotent. WAL-Modus, FK-Constraints, 64 MB Cache. Migration 5 (AZ als PK) ist der kritische Pivot; alle nachfolgenden Tabellen referenzieren `az TEXT`.

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

### E-Mail-Import (PRD-22d)
`backend/email_import/` — IMAP4_SSL (Port 993), 3 Postfächer (unfall@/termin@/bussgeld@), Smart-Inbox, Fragebogen-Erkennung. Import-Log in `email_import_log`.

### OCR + SSE-Streaming (PRD-30)
`backend/services/ocr_service.py` — Tesseract + pdf2image, 300 DPI, Deutsch (deu). SSE-Endpoint mit `?token=`-Auth-Fallback.

### Regulierungs-Workflow (PRD regulierung)
`backend/routers/schaden_routes.py` + `backend/models/abrechnungsschreiben.py` — 5 Phasen, Legacy-`regulierung`-Tabelle deprecated (v14c). `berechne_abrechnungsart()` ist Single Source of Truth für fiktiv/konkret/totalschaden.

### Gebühren-Assistent (PRD-28)
`backend/services/gebuehren_service.py` + `backend/word/gebuehren_word.py` — Nr. 2300 VV RVG, 12 VU-Sonderregeln, DOCX-Kostennote via docxtpl.

### Klage-Wizard (PRD-26)
`backend/routers/klage_routes.py` + `frontend/src/sections/KlageWizard.jsx` — 10 Schritte, gerichtlicher Streitwert aus `gesamtReguliert`, alle Gegner aus RA-MICRO.

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

**Session 2026-05-03 — Backlog-Sichtung + Commit**

- TODO.md konsolidiert: PRD-17 → `[refining]`, PRD-19 → ✅, PRD-04 Erw. gestrichen
- Uncommitted Changes committed (5f0a5ec)
- PRD-04 Erweiterte Dokumentenklassen (A/B/C) bewusst gestrichen — kein Mehrwert,
  Dokumente werden bei Bedarf (Klage/Forderungsschreiben) direkt abgerufen

**Nächste Session:** Nächste Priorität laut TODO.md: PRD-33 (Klage-Wizard Feintuning),
PRD-NEW (Onboarding-Wizard Neue-Akte-Anlage) oder PRD-25c (Mandantenkommunikation).
