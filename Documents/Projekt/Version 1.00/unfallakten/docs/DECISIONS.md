# Architekturentscheidungen – Unfallakten

Rekonstruiert aus Code, Kommentaren und Migrationsskripten.  
Format: Entscheidung → Grund → Alternative → Konsequenz.

---

## Backend-Framework

### Flask statt FastAPI

**Entscheidung:** Flask wird als Web-Framework verwendet. Die `erstelle_app()`-Factory registriert 30 Blueprints, CORS wird per `after_request`-Hook gesetzt.

**Grund:** `requirements.txt` enthält `fastapi==0.111.0`, aber kein einziger Import davon existiert im Backend. `backend/tests/test_modul6.py` enthält einen expliziten Regressionstest `test_kein_fastapi()`: `assertNotIn("fastapi", inhalt.lower())`. Die Entscheidung wurde während der Entwicklung revidiert, FastAPI blieb versehentlich in `requirements.txt`.

**Alternative:** FastAPI mit Pydantic-Validierung, automatischem OpenAPI-Schema und async-Support.

**Konsequenz:** `fastapi==0.111.0` in `requirements.txt` ist Dead Weight und installiert pydantic, starlette, uvicorn mit. Beim nächsten Dependency-Audit entfernen.

---

### Manuelles CORS via `after_request` statt Flask-CORS

**Entscheidung:** `app.py` setzt `Access-Control-*`-Header manuell in einer `after_request`-Funktion. `flask-cors` ist nicht installiert.

**Grund:** Volle Kontrolle über den genauen `CORS_ORIGIN`-Wert aus Umgebungsvariable. Außerdem: Ein `OPTIONS`-Preflight-Handler ist explizit implementiert, der `204` zurückgibt.

**Alternative:** `flask-cors` mit `CORS(app, origins=os.environ.get("CORS_ORIGIN"))`.

**Konsequenz:** Bei Routen mit mehreren Origins oder Wildcard müsste der Handler manuell angepasst werden. Derzeit erlaubt exakt einen Origin.

---

## Datenbank

### SQLite statt PostgreSQL

**Entscheidung:** SQLite mit WAL-Modus, `timeout=30`, `check_same_thread=False`. Kein ORM.

**Grund:** `database.py` enthält im Docstring: *„Spätere Migration zu PostgreSQL: Nur diese Datei + database_pg.py austauschen. Alle Models bleiben identisch."* — bewusste Entscheidung für niedrige Deployment-Komplexität, Migrationspfad dokumentiert.

**Alternative:** PostgreSQL mit SQLAlchemy oder psycopg2 direkt.

**Konsequenz:** `check_same_thread=False` ist notwendig, weil Gunicorn (4 Worker) threaded Flask-Requests bedient. Bei SQLite kann nur ein Writer gleichzeitig aktiv sein — WAL mildert das für Lese-/Schreib-Mischlasten.

---

### `az TEXT` als Primary Key (Migration 5)

**Entscheidung:** `unfallakte.az` (z.B. `"31/21"`) ist der Primary Key, kein `INTEGER AUTOINCREMENT id`. Alle Fremdschlüssel referenzieren `az`.

**Grund:** RA-MICRO verwendet `sAktenNummer` als einmalige Kennung. Ohne AZ als PK wäre eine ID-zu-AZ-Mapping-Tabelle nötig, oder Abfragen müssten immer über JOIN gehen.

**Alternative:** Autoinkrementiertes Integer-PK + `az`-Spalte mit UNIQUE-Constraint.

**Konsequenz:** Aktenzeichen können sich theoretisch ändern — dann bricht jeder referenzierende Fremdschlüssel. In der Praxis sind RA-MICRO-AZ unveränderlich, sobald angelegt.

---

### Zwei `schema_manager.py`-Dateien

**Entscheidung:** Es existieren `backend/db/schema_manager.py` (aktiv, von `app.py` importiert) und `backend/schema_manager.py` (Root-Level, nicht importiert).

**Grund:** [UNKLAR] Der Root-Level-Manager wurde in einem früheren Refactoring zurückgelassen. Er enthält Migrations für `unfalldetails` (Migration 22) und `vertreter_name/funktion` (Migration 23), die historisch ausgeführt wurden. `backend/db/schema_manager.py` setzt in Migration 28 voraus, dass `unfalldetails` bereits existiert.

**Alternative:** Beide zu einer Datei zusammenführen, klare Nummerierungsfolge.

**Konsequenz:** Frische Instanzen ohne historische DB haben `unfalldetails` NICHT — Migration 28 würde scheitern. Der Root-Level-Manager muss daher auf frischen Instanzen manuell einmalig ausgeführt werden, oder Migration 28 muss `CREATE TABLE IF NOT EXISTS` defensiv schreiben.

---

### `PRAGMA foreign_keys = OFF` in Routen-Code

**Entscheidung:** `abrechnungsschreiben_routes.py` deaktiviert FK-Constraints beim Löschen (`DELETE FROM regulierung_positionen` → `DELETE FROM abrechnungsschreiben`) mit explizitem `PRAGMA foreign_keys = OFF`.

**Grund:** Kommentar im Code: *„Direktes sqlite3 ohne get_connection() – garantierter Commit"*. SQLite-FK-Prüfung verhindert DELETE-Reihenfolge wenn Parent-before-Child gelöscht würde; hier wird Child explizit zuerst gelöscht, aber FK=OFF verhindert Race-Conditions bei anderen aktiven Connections.

**Alternative:** Kaskadierendes `ON DELETE CASCADE` in der FK-Definition — dann übernimmt SQLite die Reihenfolge.

**Konsequenz:** Drei Stellen in `abrechnungsschreiben_routes.py` umgehen den Context-Manager und verwenden rohes `sqlite3.connect()`. Jede muss explizit `.commit()` und `.rollback()` aufrufen. Fehleranfällig wenn zukünftige Entwickler das Muster nicht kennen.

---

### `PRAGMA table_info()` vor jedem Schaden-INSERT

**Entscheidung:** `_hole_schaden_spalten(conn)` in `backend/models/schaden.py` führt `PRAGMA table_info(schadenpositionen)` durch und gibt nur Spalten zurück, die tatsächlich existieren.

**Grund:** Migrations 14 ff. haben schrittweise netto/USt-Felder zu `schadenpositionen` hinzugefügt. Code der auf einer älteren DB-Version läuft, würde ohne diese Prüfung auf nicht-existente Spalten schreiben und abstürzen.

**Alternative:** Alle Felder von Anfang an in der Basis-DDL definieren; keine dynamischen Spaltenprüfungen.

**Konsequenz:** Jeder INSERT in `schadenpositionen` trägt den Overhead einer PRAGMA-Abfrage. Bei SQLite mit In-Process-Zugriff vernachlässigbar, aber architektonisch ein Zeichen, dass das Migrations-System nicht vollständig vertraut wird.

---

### Migration 32: Defekte FK-Referenz in `todos`

**Entscheidung:** Migration 32 baut `todos` komplett neu (CREATE temp table → INSERT → DROP → RENAME), weil `todos.dok_id` auf `dokumente_alt` statt `dokumente` zeigte.

**Grund:** Kommentar in `schema_manager.py`: *„was bei PRAGMA foreign_keys = ON jeden INSERT in todos blockierte"*. Die Referenz entstand vermutlich als `dokumente` umbenannt wurde.

**Alternative:** `ALTER TABLE` mit `DROP COLUMN` + `ADD COLUMN` — aber SQLite unterstützt `DROP COLUMN` erst ab Version 3.35.0 (2021).

**Konsequenz:** Zukünftige Tabellen-Rebuilds durch den gleichen Rebuild-Pattern (OFF/CREATE/INSERT/DROP/RENAME/ON) — dieser ist in mindestens 6 weiteren Migrations etabliert.

---

## Authentifizierung

### JWT im `Authorization`-Header, Query-Parameter als SSE-Fallback

**Entscheidung:** Token-Extraktion in `auth/middleware.py` liest primär `Authorization: Bearer <token>`. Fallback: `?token=<jwt>` als Query-Parameter.

**Grund:** Kommentar im Code: *„Fallback für SSE (EventSource unterstützt keine Custom-Header)"*. Browser-`EventSource`-API kann keine `Authorization`-Header setzen.

**Alternative:** HTTP-Only-Cookie statt Header (XSS-sicherer, kein SSE-Problem).

**Konsequenz:** JWT im Query-Parameter erscheint in Webserver-Access-Logs, Browser-History und Referer-Headers. Akzeptables Risiko für Intranet-Anwendung ohne öffentlichen Zugang.

---

### PBKDF2-HMAC-SHA256 statt bcrypt

**Entscheidung:** `models/benutzer.py` nutzt `hashlib.pbkdf2_hmac("sha256", ..., iterations=260_000)` für Passwort-Hashing.

**Grund:** Kommentar im Code: *„In Produktion mit bcrypt ersetzen (sobald Paket verfügbar)."* — `bcrypt` war zur Entwicklungszeit nicht im Basis-Docker-Image verfügbar, `hashlib` ist stdlib.

**Alternative:** `bcrypt` (adaptiver, hardware-resistent) oder `argon2-cffi` (OWASP 2024 Empfehlung #1).

**Konsequenz:** 260.000 Iterationen entsprechen OWASP-Empfehlung 2024 für PBKDF2-SHA256 — funktional sicher, aber nicht Upgrade-sicher (keine konfigurierbaren Parameter im gespeicherten Hash-Format).

---

## RA-MICRO-Anbindung

### TDS-Version 7.0 erzwungen

**Entscheidung:** Alle `pymssql.connect()`-Aufrufe setzen explizit `tds_version="7.0"`.

**Grund:** Kommentar im Code: *„Dieser Server antwortet nur auf TDS 7.0"*. Der RA-MICRO SQL Server 2014 (FreeTDS-basiert) handshaked nicht korrekt mit neueren TDS-Versionen über pymssql.

**Alternative:** Neuere TDS-Version, SQL Server Native Client, ODBC.

**Konsequenz:** Bind an pymssql 2.3.1 (fest gepinnt in `requirements.txt`). Upgrade auf neuere pymssql-Versionen könnte TDS-Verhalten ändern.

---

### `TOP N` statt `OFFSET/FETCH NEXT`

**Entscheidung:** Alle paginierten Abfragen gegen den RA-MICRO SQL Server verwenden `SELECT TOP N` statt `OFFSET ? ROWS FETCH NEXT ? ROWS ONLY`.

**Grund:** Kommentar in `ramicro/wiedervorlage_service.py`: *„TOP statt OFFSET/FETCH NEXT – robuster in SQL Server 2014 mit pymssql"*.

**Alternative:** `OFFSET/FETCH` (SQL-Standard, unterstützt in SQL Server 2012+).

**Konsequenz:** `TOP N` kann keine Paginierung über die ersten N hinaus. Derzeit kein Problem, da alle Limits (50, 100 Einträge) innerhalb sinnvoller Anzeigegrenzen liegen.

---

### RAMICRO_AKTIV-Flag als Feature-Toggle

**Entscheidung:** Alle RA-MICRO-Zugriffe prüfen `os.environ.get("RAMICRO_AKTIV", "false") == "true"`. Bei `false` geben Endpunkte strukturierte Antworten mit `ramicro_aktiv: false` zurück.

**Grund:** Entwicklung ohne RA-MICRO-Zugang (z.B. remote, ohne VPN). System soll ohne SQL Server vollständig funktionieren.

**Alternative:** Immer versuchen zu verbinden, Fehler abfangen.

**Konsequenz:** Jeder Route-Handler muss `ramicro_aktiv: false` explizit behandeln. Frontend zeigt Hinweise an statt Fehlermeldungen. Reduziert "fail-fast"-Charakter.

---

## Dokument-Pipeline

### Dreistufige Klassifikations-Kaskade mit globalem Registry-Cache

**Entscheidung:** `workflow/dispatcher.py` klassifiziert Dokumente in drei Stufen: (1) registry.json-Marker-Lookup, (2) TF-IDF-Klassifier [ab Phase 4, noch nicht implementiert], (3) Eskalation zu System-Todo. Die Registry wird beim ersten Aufruf global gecacht (`_registry_cache`).

**Grund:** registry.json mit ~1.200 Einträgen soll nicht bei jedem Request gelesen werden. Globaler Cache ohne TTL, da die Registry sich während der Laufzeit nicht ändert (nur per `registry_neu_laden()` manuell invalidierbar).

**Alternative:** LRU-Cache mit TTL; Neu-Laden bei DB-Änderung per Signal.

**Konsequenz:** Änderungen an registry.json in der laufenden Instanz erfordern manuellen API-Aufruf (`registry_neu_laden()`) oder Container-Neustart.

---

### Portal-Sync als Outbox-Muster

**Entscheidung:** Akten-Updates ans Mandantenportal werden in `portal_sync_queue` (SQLite) geschrieben. Ein Sync-Worker sendet per HTTPS+HMAC-SHA256.

**Grund:** Direkte HTTP-Calls aus Route-Handlern würden bei Portal-Ausfall die Akten-Route blockieren. Outbox-Muster entkoppelt Schreiben und Senden.

**Alternative:** Message Queue (Redis/RabbitMQ); direkter HTTP-Call mit kurzer Timeout.

**Konsequenz:** Bei Portal-Ausfall wächst `portal_sync_queue` unbegrenzt. Retry-Logik und `retry_count`-Feld vorhanden, aber kein automatisches Dead-Letter-Management.

---

## Projektstruktur

### `unfallakten/`-Unterverzeichnis als historisches Artefakt

**Entscheidung:** Das Verzeichnis `unfallakten/` im Projekt-Root enthält eine vollständige ältere Kopie der Backend-Codebasis (~63 Python-Dateien, eigenes `app.py`, eigenes `schema_manager.py`).

**Grund:** [UNKLAR] Vermutlich beim Umstrukturieren von einem einfachen Python-Paket zur Docker-Compose-Struktur entstanden. Das Verzeichnis wird nicht importiert und ist nicht in Docker-Volumes gemountet.

**Alternative:** Löschen — das Verzeichnis hat keinen Laufzeit-Einfluss.

**Konsequenz:** `git grep` über das gesamte Repo findet Treffer in `unfallakten/backend/...`, die zu veralteten Code-Versionen gehören. Irreführend bei Fehlersuche und Code-Reviews.

---

### Reparaturskripte im Projekt-Root

**Entscheidung:** Dutzende Einzel-Dateien im Root: `debug_*.py`, `fix_*.py`, `patch_migration_*.py`, `cleanup_abrechnungen.py`, `seed_*.py`, `migration_24.py` etc. Alle verwenden raw `sqlite3.connect()` mit hartkodiertem Pfad `/app/data/unfallakten.db`.

**Grund:** Entstanden als Notfall-Werkzeuge für konkrete Produktionsprobleme (defekte Migrations, falsche Datensätze, fehlendes Seeding).

**Alternative:** Ins Backend als `/admin/`-Endpunkte oder als Click-CLI-Commands integrieren.

**Konsequenz:** Skripte sind nicht mehr verwendbar ohne den korrekten DB-Pfad zu setzen. Historisch wertvoll als Dokumentation vergangener Incidents. Erzeugen False-Positives bei Grep-Suchen (z.B. nach `sqlite3.connect`).

---

## Klage-Wizard

### `betragOriginal`-Snapshot in `oeffneWizard()`

**Entscheidung:** `oeffneWizard()` in `KlageSection.jsx` speichert vor der greedy-Regulierungs-Reduktion den Ursprungsbetrag als `betragOriginal` in jedem `wizardPos`-Eintrag.

**Grund:** `p.betrag` wird im gleichen Schritt um positionsgebundene Regulierungen UND um Vorschuss-Zahlungen (greedy, ungebunden) reduziert. In `StepSchaden` muss die Spalte „Gefordert" den Klageantrag zeigen: `original − gesamte Regulierung`. Mit dem reduzierten `betrag` + nur der positionsgebundenen Regulierung hätte „Gefordert" bei Vorschüssen einen zu niedrigen Wert ergeben.

**Alternative:** Gefordert im Wizard aus dem DB-Feld `schadenpositionen.betrag` neu lesen. Würde aber erneute API-Calls und Sync-Probleme mit manuellen Wizard-Änderungen erzeugen.

**Konsequenz:** Jede `wizardPos` trägt ein zusätzliches Feld `betragOriginal`. Muss beim Öffnen des Wizards immer befüllt werden — auch wenn kein Vorschuss existiert (dann identisch mit `betrag`).

---

### `wizardVerzugManuell` in Parent-State statt lokalem `useRef`

**Entscheidung:** Das Flag „Benutzer hat den Verzugstext manuell bearbeitet" (`wizardVerzugManuell`) liegt als React-State in `KlageSection.jsx`, nicht als `useRef` innerhalb von `StepVerzug`.

**Grund:** `StepVerzug` wird via `{step === 8 && <StepVerzug .../>}` konditional gerendert. Das bedeutet: bei Step-Wechsel wird die Komponente vollständig ausgehängt und beim Zurückkehren neu eingehängt. Ein lokaler `useRef` initialisiert sich dabei immer neu mit dem aktuellen Prop-Wert — der Manual-Edit-Schutz geht verloren. Parent-State überlebt das Unmounting.

**Alternative:** Step 8 permanent gemountet halten (`display: none` statt konditionales Rendering). Würde aber alle Steps parallel im DOM halten — unerwünschter Komplexitätszuwachs.

**Konsequenz:** Jeder Wizard-State der über Step-Navigation hinweg persistent sein muss, gehört in `KlageSection.jsx`, nicht in die Step-Komponenten selbst.

---

### Klage-Wizard `overrides`-Dict → `klage_cfg`-Merge-Muster

**Entscheidung:** `klage_routes.py` (POST `/klage/generieren`) enthält einen expliziten Merge-Loop der bestimmte `overrides`-Keys in `klage_cfg` schreibt:
```python
for _key in ("rvg_ausserg", "rvg_ausserg_override", "rvg_bereits_gezahlt"):
    if overrides.get(_key) is not None:
        klage_cfg[_key] = overrides[_key]
```

**Grund:** `klage_service.py` liest ausschließlich aus `klage_cfg`. Das Frontend berechnet `rvg_ausserg` im Wizard (Step 9, via `/rvg-berechnen`) und sendet es als `overrides`-Eintrag — nicht als Teil von `klage_config`, das direkt aus der DB kommt. Ohne den Merge-Loop wurden diese Felder im Service nie gesehen.

**Alternative:** `klage_service.py` bekommt `overrides` als separaten Parameter. Erzeugt aber duales Lookup-Muster im gesamten Service — schlechter wartbar.

**Konsequenz:** Neue Felder die der Wizard berechnet oder der Benutzer manuell eingibt, müssen in diesen Merge-Loop aufgenommen werden wenn sie im DOCX-Generator benötigt werden.

---

### Abrechnungsart berechnet, nicht gespeichert

**Entscheidung:** `berechne_abrechnungsart()` in `models/schaden.py` berechnet `fiktiv / konkret / totalschaden` zur Laufzeit aus vorhandenen Feldern (Gutachten-Netto, Reparaturrechnung-Brutto, WBW, Restwert). Ergebnis landet nicht in der DB — außer wenn der Benutzer `abrechnungsart` explizit setzt.

**Grund:** Die Klassifikation folgt deterministischen juristischen Regeln; Speichern würde Inkonsistenz riskieren wenn Eingabedaten nachträglich geändert werden.

**Alternative:** Gespeichertes berechnetes Feld + Trigger zur Aktualisierung.

**Konsequenz:** Jeder `_schaden_dict()`-Aufruf berechnet `gesamt_brutto` und `abrechnungsart` neu. Single Source of Truth in `berechne_abrechnungsart()` — aber `v_schadensummen`-View verwendet `reparaturkosten` (Legacy-Feld) statt `rep_gutachten_netto` (neues Feld ab Migration 10), wodurch die View veraltete Summen liefert.

---

### Admin-User-Bootstrap bei App-Start

**Entscheidung:** `_ensure_admin_exists()` in `app.py` wird bei jedem App-Start aufgerufen. Wenn `benutzer`-Tabelle leer ist, werden zwei Benutzer mit Zugangsdaten aus `.env` oder Hardcoded-Defaults angelegt (`Kanzlei2024!`).

**Grund:** Keine separate Setup-Phase nötig. Frische Instanz ist sofort einsatzbereit.

**Alternative:** Separater `init`-Befehl oder Setup-Wizard.

**Konsequenz:** Hardcoded Fallback-Passwort `Kanzlei2024!` ist in `app.py` im Klartext sichtbar. In Produktionsumgebungen ohne `.env`-Override ist das die tatsächliche Zugangsdaten.

---

## Intake-Pipeline v7 + Positionsmodell

### Review-Freigabe ist der einzige Schreibweg in Akten-Tabellen (`INTAKE_REVIEW_PFLICHT`)

**Entscheidung:** Feature-Flag `INTAKE_REVIEW_PFLICHT` (Default True). Eingehende Dokumente (E-Mail-Anhänge, Uploads, E-Akte-Import, Fragebögen) erzeugen nur noch `intake_dokumente`+`zustellungen`. Der einzige Weg, in `dokumente`/`beteiligte`/`unfalldetails`/`personenschaden`/`schadenpositionen` zu schreiben, ist die menschliche Freigabe in der Review-Queue (via `output_adapter`, S1.8). Alt-Pfade laufen nur bei `INTAKE_REVIEW_PFLICHT=false`.

**Grund:** Auto-Import hat wiederholt still falsche/unvollständige Daten in Akten geschrieben (Best-Effort-Swallow verdeckte Fehler). Ein Mensch soll jedes Dokument sehen, bevor es die Akte verändert.

**Alternative:** Auto-Import mit Konfidenzschwelle beibehalten und nur Grenzfälle in die Queue geben.

**Konsequenz:** Guard-Tests (`test_s19_intake_write_guard.py` AST + `test_s19d_e2e_no_intake_writes.py`) fixieren die Whitelist zulässiger Schreiber; jeder neue Direktschreiber schlägt an. Das Flag bleibt als Rollback-Anker bestehen. (2026-07-09, S1.9)

---

### Positionsmodell forward-only — kein Backfill aus dem Bestand (P1.8)

**Entscheidung:** Der Backfill synthetischer Ereignisse aus Altbeständen (P1.8) wird NICHT durchgeführt. Neue Vorgänge bekommen eine saubere Ereignis-Historie; Altakten zeigen den ehrlichen N-07-Hinweis („Eskalationsvorschläge erst ab [Einführungsdatum] verlässlich").

**Grund:** RA Schatz (2026-07-13) — Sorge vor „vielen unbearbeiteten Ereignissen in der Oberfläche" bei Altakten. Der Backfill hätte die Review-Queue ohnehin nicht befüllt (die liest `intake_dokumente`, Backfill schreibt nur `ereignisse`); die Alt-Historie wäre je Akte im Positions-Dashboard erschienen.

**Alternative:** Vollständiger idempotenter Backfill (`herkunft='backfill'`, filterbar) oder begrenzter Backfill nur für aktive Akten mit Dry-Run-Report.

**Konsequenz:** Der N-07-Hinweis verschwindet automatisch, falls je nachbackfillt wird. Prompt archiviert: `handover/naechste_session_P1_8_prompt.md`. (2026-07-13)

---

### Ereignis-Buchung bei Freigabe: Dropdown steuert, nur echte Beträge (P1.5e)

**Entscheidung:** (1) Die Dropdown-Auswahl im Freigabe-Dialog steuert, welches Ereignis gebucht wird; die Registry (`klasse_ereignistyp.yaml`) liefert nur die Vorbelegung je Klasse — nicht hartkodiert, nicht in den Einstellungen. (2) Es werden nur echte Beträge gebucht; fehlen sie, wird das Ereignis als reiner Fakt gebucht (erfüllt die Checkliste, erfindet keine Zahlen).

**Grund:** RA Schatz — der Mensch entscheidet bei der Freigabe, das System soll keine Beträge erfinden.

**Alternative:** Ereignistyp je Klasse fest verdrahten; fehlende Beträge schätzen.

**Konsequenz:** Serverseitiger `eingehend`-Guard verwirft bestätigte Typen, die kein eingehender Ereignistyp sind (Defence-in-depth). (2026-07-12)

---

### WDM-Import ist ein unbestätigtes Ereignis (PF-08)

**Entscheidung:** WDM-Daten aus RA-MICRO werden als `abrechnung_eingegangen` mit `dokument_id=NULL`, `herkunft='wdm'` gebucht und in der UI als unbestätigt gekennzeichnet (`has_unbestaetigt`, gestrichelter Rand + WDM-Chip).

**Grund:** WDM ist inhaltlich eine Abrechnung, aber ohne zugrundeliegendes Dokument — die Herkunft muss sichtbar bleiben, damit niemand sie mit einer belegten Abrechnung verwechselt.

**Alternative:** WDM wie eine dokumentbelegte Abrechnung behandeln.

**Konsequenz:** Der Doppelerfassungs-Guard greift bei WDM nicht (dokument_id=NULL); Mehrfach-Import verhindert der Alt-Pfad per HTTP 409. (2026-07-09)

---

### Seiten-Triage über Textabdeckung, nicht Wortzahl (N-04)

**Entscheidung:** Ob eine Seite als Bildseite gilt (und OCR/GLM übersprungen wird), entscheidet die **Textabdeckung** = Flächenanteil der Tesseract-Wort-Boxen an der Seitenfläche, nicht die reine Wortzahl.

**Grund:** Fotoseiten mit Bildunterschrift haben viele Wörter, aber nur ein schmales Textband → niedrige Abdeckung. Die Wortzahl-Heuristik hätte sie fälschlich als Textseiten behandelt (Einwand im Brainstorming).

**Alternative:** Schwellwert auf Wortzahl je Seite.

**Konsequenz:** Migrationsfrei (`SeitenText.ist_bildseite`, `parse_json.bildseiten_anzahl`). Unter `GLM_OCR_ENABLED=false` spart die Triage noch keine Aufrufe (Tesseract läuft ohnehin), nur die Markierung ist sichtbar. (2026-07-14)

---

## Klage-Wizard (PRD-33)

### Haftungsquote = zwei Fälle A/B

**Entscheidung:** Der Klage-Wizard behandelt die Haftungsquote in zwei getrennten Fällen: **Fall A** (gegnerische Quote) = reine Darstellung, keine Kürzung der Forderung; **Fall B** (eigene Quote) = die Forderung wird quotiert, und zwar **erst quotieren, dann Zahlungen abziehen** (nicht umgekehrt). Fall B erhält einen eigenen Klemmsatz („Die Beklagte …").

**Grund:** RA Schatz (2026-07-17) — juristisch korrekte Reihenfolge; die beiden Fälle bedeuten rechnerisch Verschiedenes.

**Alternative:** Eine einheitliche Quotenlogik für beide Richtungen.

**Konsequenz:** BE und FE müssen dieselbe Rundung verwenden — FE half-up vs. BE banker's wurde in Session 6 via `_round2_half_up` angeglichen. 0-€-Hauptantrag-Randfall bleibt note-only. (2026-07-17)

### Keine gerichtliche Gebührenberechnung

**Entscheidung:** Der Wizard berechnet keine gerichtlichen Gebühren. Der gerichtliche Streitwert wird ausschließlich als Gegenstandswert-Angabe geführt; RVG-Berechnung bleibt außergerichtlich (Nr. 2300 VV RVG).

**Grund:** RA Schatz (2026-07-17) — gerichtliche Gebühren setzt das Gericht fest; eine eigene Berechnung wäre fehleranfällig und überflüssig.

**Alternative:** Vollständige gerichtliche Gebührentabelle im Wizard.

**Konsequenz:** Das „RVG gerichtlich"-Duplikat samt `rvgOverride`/cfg-`rvg` wurde entfernt (KW-13/V6). Der Legacy-Generieren-Button entfällt ebenfalls — der Wizard ist der einzige Weg zur Klageschrift. (2026-07-17)

---

## Dokumentenbezeichnung: regelbasiert statt LLM (PRD-37 vs. PRD-38)

**Entscheidung:** Dokumentbezeichnungen werden regelbasiert erzeugt (`baue_bezeichnung` → `«Label» «Aussteller» vom «Datum» («Betrag»)`). Die LLM-Variante (PRD-38) wird nicht gebaut; falls im Betrieb nötig, nur eng für Klasse `sonstiges`.

**Grund:** RA Schatz (2026-07-15) — die Regel deckt klassifizierte Dokumente vorhersehbar ab; ein LLM brächte nur Kosten/Latenz/Nichtdeterminismus. Vorhersehbare Titel sind im Kanzleialltag angenehmer als stilistisch schwankende. Zudem ist KI in Stufe 1 ohnehin aus (`LLM_ENABLED=false`).

**Alternative:** LLM-generierte Titel für alle Dokumente.

**Konsequenz:** PRD-38 bleibt zurückgestellt; erst mit PRD-37 im Alltag arbeiten. (2026-07-15)

---

## Rausch-Absender: per-Dokument-Policy, kein SPF/DKIM-Gate

**Entscheidung:** Wertloses Rauschen auf `info@` wird beim Eingang automatisch verworfen — gesteuert durch eine YAML-Registry `rausch_absender.yaml` (Absender-Domain → Policy `nur_body`/`komplett`), per-Dokument angewandt (Placetel: Body verwerfen, Fax-PDF bleibt; beA: Body + Anhänge weg).

**Grund:** RA Schatz/Brainstorming (2026-07-16) — das reale Bedürfnis ist nicht ein generischer Filter, sondern konkretes bekanntes Rauschen gar nicht erst in die Queue zu lassen.

**Alternative:** Generische Filter-Chips, Betreff-Muster („Fax von … auf …"), SPF/DKIM-Gate.

**Konsequenz:** Bewusst nicht gebaut: Betreff-Muster, SPF/DKIM, Filter-Chips. Soft-Delete (`verworfen_von=NULL`=System) mit Papierkorb + Wiederherstellen. (2026-07-16)

---

## Kürzungstaxonomie vor V11 — Editor-Komponente entsteht in Phase 1

**Entscheidung:** Phase 1 der Kürzungstaxonomie (`handover/KONZEPT-Kuerzungstaxonomie-Vorgangsautomat.md`) wird vor Paket 4 „Standardtexte pflegbar" (V11) umgesetzt. Die gemeinsame Editor-Komponente (Platzhalter-Hilfe, Live-Vorschau, Registry+Override) entsteht in Phase 1; V11 erbt sie.

**Grund:** RA Schatz (2026-07-23) — die Kürzungstaxonomie ist die eigentliche Vision hinter Paket 4; wer zuerst baut, baut den Editor, der andere erbt ihn.

**Alternative:** V11 zuerst (kleiner, fertig durchgeplant) oder parallel.

**Konsequenz:** V11 wartet, Spec bleibt gültig. Kein Parallel-Editor. Phase-1-Erfolg wird an Klassifikationsgüte gemessen (Trefferquote des Typ-Vorschlags + Abdeckung durch Bausteine), nicht an „Erfassungsdisziplin" — die Daten entstehen im neuen Workflow als Abfallprodukt der Schreiben-Beantwortung. Konkrete Prozentziele nach dem Handtest (Phase 0) festlegen. (2026-07-23)

---

## Urteilscheck für Bestand-Textbausteine entfällt

**Entscheidung:** Der im Kürzungstaxonomie-Papier vorgesehene Prüfprozess `urteil-verifikation` wird für die vorhandene Bausteinsammlung NICHT gebaut. Bei der Registry-Migration wird nur das Verifikationsdatum mitgeführt („handgeprüft RA Schatz, Juli 2026").

**Grund:** RA Schatz (2026-07-23) — sämtliche zitierten Urteile der Bestandsbausteine sind bereits von Hand verifiziert.

**Alternative:** Eigenes Prüf-Werkzeug bzw. manueller Prüfablauf vor der Migration (hätte Phase 0 zum eigenen Bauvorhaben gemacht).

**Konsequenz:** Phase 0 schrumpft auf Handtest + Baustein-Zuordnung. Der 12-Monats-Re-Verifikations-Zyklus hat über `verifiziert_am` einen Anker; eine Regel für künftig NEU zitierte Urteile wird erst beim ersten Neuzugang definiert. (2026-07-23)

---

## Kommentarlose Zahlungen: Betrags-Matching → Anfrage → Not-Zuordnung (keine Verteil-Maske)

**Entscheidung:** Nicht zuordenbare Zahlungseingänge werden dreistufig behandelt: (1) automatisches Betrags-Matching gegen die offenen Kürzungsbeträge — nur bei EINDEUTIGEM Treffer (auch Summen-Kombinationen, aber nie bei Mehrdeutigkeit); (2) Regelfall sonst: generierte Anfrage an den Versicherer „worauf wurde gezahlt?" als Queue-Eintrag mit Entwurf + Frist; (3) Not-Zuordnung von Hand auf die kritischste Schadenposition, als bewusste Ausnahme protokolliert (Praxis: ~1 : 200–300 Fälle). Jede geflaggte Kürzung führt dafür ihren gekürzten Betrag als Pflichtangabe. Technische Einwände gegen den Reparaturweg werden zu einer Sammel-Kürzung gebündelt, sofern kein eigener Textbaustein existiert.

**Grund:** RA Schatz (2026-07-23) — „einfach verteilen" verfälscht die Statistik; ein bekannter offener Betrag (z. B. 33,40 € Kleinteile) identifiziert die Zahlung auch ohne Begründungsschreiben.

**Alternative:** Manuelle Verteil-Maske für alle unklaren Zahlungen; oder automatischer Abgleich mit dem RA-MICRO-Aktenkonto.

**Konsequenz:** Der Aktenkonto-Abgleich ist mit dem vorhandenen Read-only-SQL-Zugang NICHT baubar — Katalogprüfung 2026-07-23: Der RA-MICRO SQL Server (alle Datenbanken inkl. `RAMICRO_buk`) enthält keine Aktenkonto-/Buchungs-/Zahlungseingangsdaten; `tblKosten`/`tblKostenDetails` sind Kosten-/Honorarerfassung, keine Geldeingänge. Ersatz: Nach angekündigter Zahlung setzt der Workflow eine Prüf-Frist („Zahlungseingang kontrollieren"), die Bestätigung erfolgt manuell. (2026-07-23)

---

## Kürzungstaxonomie Entscheidungs-Tor: Kürzung bleibt Ereignis-Attribut (Option b), zwei getrennte Faltungen

**Entscheidung:** (1) **Ort der Kürzungsdaten = Option (b)** aus Konzept 10.3.1: Das Tripel (Position × Typ × Betrag) lebt im Ereignismodell (`ereignis_positionen` mit `wirkung='gekuerzt'`, `kuerzungsart_id`, Betrag). KEINE neue `kuerzung`-Tabelle; `regulierung_positionen` bleibt der Erfassungsweg im bestehenden Doppelschreibmuster. (2) **Verhältnis der zwei Faltungen: strikt getrennt** — die Positions-Faltung beantwortet allein „wo steht jede Schadenposition"; der Vorgangsautomat wird eine zweite, eigene Faltung über denselben Ereignisstrom für „wo steht der Prozess". Er liest den Positionszustand, schreibt aber nie hinein.

**Grund:** RA Schatz (2026-07-23), nach dem Phase-0-Handtest. Empirisch gestützt: Kürzungs-Erkennung = Differenz Forderung (Soll) vs. Zahlung (Ist) — Abrechnungsschreiben sind reine Zahlungsmitteilungen, Kürzungen dort oft unsichtbar (Stichprobe 8a: Wertminderung 1.450 € gefordert, 650 € gezahlt, kein Kürzungsausweis; Stichprobe 20c: dokumentierte Nachzahlung 25 € → +5 €). Genau diese Differenz-Mathematik existiert bereits im Ereignismodell (Konzept 12.5).

**Alternative:** (a) `regulierung_positionen` um Typ/Klassifikation erweitern; (c) neue Tabelle mit Backfill — beides schafft bzw. zementiert eine dritte Parallelwelt.

**Konsequenz:** Phase-1-Kern = Runde-1↔Runde-2-Vergleich auf dem Ereignisstrom (Nachzahlung = Differenz der `gekuerzt`-Beträge je position_key × Typ). Begründung und Zahlung liegen oft in getrennten Dokumenten (Stichprobe 25: Abrechnungsschreiben zahlt mit „Nicht zu erstatten −7.734,55 €" unbegründet, der Prüfbericht begründet) → die Abrechnungsrunde muss Abrechnungsschreiben + Prüfbericht verketten. Keyword-Matching liefert nur den TYP und nur auf Begründungsdokumenten; Zahlmitteilungen werden auf Positionen/Beträge geparst. (2026-07-23)

---

## Phase 0 Kürzungstaxonomie abgeschlossen: Zielwerte, Matching-Architektur, A–F-Zuordnung

**Entscheidung:** (1) **Phase-1-Zielwerte** (Messung nach ~4 Wochen Betrieb): Abdeckung ≥ 90 %, Trefferquote Typ-Vorschlag ≥ 75 %, Positions-/Betragszuordnung auf Zahlmitteilungen ≥ 90 %. (2) **Matching-Architektur:** regelbasierte Stichworte als Typ-Vorschlag auf Begründungsdokumenten, LLM nur als Fallback; Kürzungs-Erkennung ausschließlich über Betragsdifferenz. (3) **A–F-Zuordnung** der 17 bisher unzugeordneten Quelldateien aus `tools/textbausteine/`: ghpfabschleppgeb→E03 · ghpfjveg→E01 (Variante JVEG) · huktableau→E01 (Variante HUK-Tableau) · ghpvnkpauschal→E02 · ghpfup2→E06 (Eskalation 2. Runde) · ghpfansprort→A04 · ghpfstverort→A04 (vorbehaltlich Sichtung, altes .doc) *[Nachtrag Sichtung 2026-07-23: Datei ist LEER — 0 Wörter laut Dokument-Metadaten, leer gespeichert 04/2012; ghpfstverort entfällt ersatzlos, A04 speist sich allein aus ghpfansprort (Inhalt gesichtet: Stundenverrechnungssätze-Argumentation, passt). Achtung: ghpfansprort.doc ist altes .doc-Format → braucht .doc→.rtf-Konvertierung vor dem Import, wie ghpfup.DOC]* · ghpfreprg→B01 · repbest→A10 · ghpfzeitpunkt→**A11 neu** (Abrechnungszeitpunkt/Preissteigerung) · wertminderungsteuer→**C01b neu** · „nutzungsausfall für schadentag und sv besichtigung"→D01 · hws→F01. KEIN Kürzungstyp: ghpfandrohungsv (Eskalationsbaustein zu Nr. 11 Technische Kürzungen), heilverlauf (Mandantenkommunikation), ghpfstellung (Rahmentext Stellungnahme-Generator), vertretungsanzeige (aussortieren). Zusätzlich neu aufzunehmen ohne Quelldatei: **A07 Neu-für-alt** (reale Abzüge in Stichproben 17/18, Baustein fehlt).

**Grund:** RA Schatz (2026-07-23), 30-Stichproben-Tiefenprüfung: Abdeckung 94 % (Gesamtkorpus 11 Prüfberichte + 59 Abrechnungsschreiben, PDF-Volltexte); Trefferquote Typ auf Begründungsdokumenten 61 % roh / ~71 % nach trivialen Stichwort-Fixes.

**Alternative:** LLM-first-Klassifikation (teurer, schwerer erklärbar); Handtest auf dem Freitext-Bestand (existiert nicht — alle 44 `kuerzung_freitext` leer, `pruefberichte` 0 Zeilen).

**Konsequenz:** Phase 1 kann starten. Registry-Migration stempelt `verifiziert_am` = „handgeprüft RA Schatz, Juli 2026". Stichwort-Fixes einplanen: Wortgrenzen (Kleinteilepauschale ≠ Unkostenpauschale), „Kennzeichen" auf Schilderkosten verengen, ControlExpert-Tabellen strukturiert parsen. Positions-Synonymik je Versicherer-Template (Differenzbetrag = Fahrzeugschaden usw.). Vollprotokoll → `handover/phase0-handtest-stichproben.md`. (2026-07-23)

---

## Phase 1 Kürzungstaxonomie: Plan freigegeben + 3 Detail-Zuordnungen

**Entscheidung:** Der Phase-1-Plan (`docs/superpowers/plans/2026-07-23-kuerzungstaxonomie-phase1.md`, 12 Tasks) ist freigegeben; Umsetzung per Subagent-Verfahren. Drei bei der Freigabe bestätigte Detail-Zuordnungen: (1) Fehlerspeicher=A05a, Batteriestützbetrieb=A05b, Tankrest=A05c (Kalkulationspositionen nahe A05 Arbeitszeitwerte). (2) Varianten-Modell: mehrere Bausteine zum selben Grundtyp werden eigene Katalog-Zeilen mit Suffix-Code (A04b, B01b, E01b, E01c, E06b); Statistik aggregiert über den Code-Präfix. (3) „Technische Kürzungen" (Bestand Nr. 11) = A09 Reparaturweg; A08 bleibt frei für künftige „nicht unfallkausal"-Fälle.

**Grund:** RA Schatz (2026-07-23) — Bestätigung der Plan-Empfehlungen; Suffix-Modell, weil eine Katalog-Zeile genau einen editierbaren Textbaustein trägt.

**Alternative:** B02 für die drei technischen Positionen; Varianten-Texte in einen gemeinsamen Baustein zusammenführen; A08 für Nr. 11.

**Konsequenz:** Zieltaxonomie = 32 Typen (19 Bestand + 13 neu), Zuordnungstabelle im Plan ist verbindlich. Nachtrag zur A–F-Zuordnung vom selben Tag: ghpfstverort.DOC ist leer und entfällt ersatzlos (A04 allein aus ghpfansprort). (2026-07-23)

---

## Bewusst vertagt (kein Handlungsbedarf)

- **Prod-Rollout intake-stufe1** — Git-Teil erledigt (2026-07-15), Deployment vertagt (kein Prod-Host, Go-Live später). Runbook + Deploy-Reihenfolge in STATE.md.
- **N-05** (kooperatives Yielding + Teilergebnisse) — bewusst zurückgestellt.
- **P1.8** (Backfill) — siehe oben, forward-only.
- **PRD-38** (Dokumentenbezeichnung per LLM) — siehe oben.
