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
