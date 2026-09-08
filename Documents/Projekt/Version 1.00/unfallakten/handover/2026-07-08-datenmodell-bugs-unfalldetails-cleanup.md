# Datenmodell-Bugs: `unfalldetails` fehlt + `cleanup_abrechnungen.py` falscher DB-Default

**Stand:** 2026-07-08
**Ziel:** Zwei Bugs aus einer vorherigen Architektur-Analyse (Sicherheitsaudit-Vorbereitung) im Detail klären: Root Cause, exakte Codestellen, Impact, Fix-Optionen. **Reine Recherche — nichts gefixt, keine Migration ausgeführt.**

---

## Kontext

Live-DB: `backend/data/unfallakten.db` (Schema-Version **47**, referenziert via `.env`/Docker-ENV `DB_PATH`).
Karteileiche: `backend/db/unfallakten.db` (Schema-Version **16**, verifiziert per Introspektion, nicht aktiv genutzt).
Aktiver Migrations-Code: `backend/db/schema_manager.py`. Toter Legacy-Code: `backend/schema_manager.py` (Root-Level, wird von `app.py` nicht importiert).

Python für Introspektion: `C:\Users\HAL9000\Documents\Projekt\venv\Scripts\python.exe`

---

## Bug 1: `unfalldetails`-Tabelle existiert in der Live-DB nicht — aktiv genutztes Feature crasht

### Root Cause (korrigiert gegenüber der Vorab-Vermutung)

Die Vorab-Analyse vermutete, die Tabelle sei "ursprünglich vom toten Root-Legacy-Manager angelegt worden". Das stimmt in der Sache, aber der eigentliche Fehler liegt tiefer:

- **`backend/schema_manager.py`** (toter Root-Legacy-Manager) hat eine eigene `_run_migration_22()`, die `unfalldetails` per `CREATE TABLE IF NOT EXISTS` anlegt (Zeilen 1690–1722). Diese Datei läuft nie gegen die Live-DB (kein Import in `app.py`, hätte bei Ausführung ohnehin `ImportError` wegen fehlender relativer Imports).
- **`backend/db/schema_manager.py`** (der tatsächlich aktive Manager) hat **eine komplett andere Migration 22** — `kuerzungsarten_textbaustein` (Zeile 253) — die Versionsnummern der beiden unabhängig geführten Migrationshistorien sind kollidiert. Der aktive Manager hat **zu keinem Zeitpunkt** eine Migration, die `unfalldetails` per `CREATE TABLE` anlegt. Es gibt nur **Migration 28** (Zeile 2376–2424 in `backend/db/schema_manager.py`), die versucht, drei Aktivlegitimations-Spalten per `ALTER TABLE` nachzurüsten — und dabei über eine `PRAGMA table_info`-Prüfung feststellt, dass die Tabelle fehlt, sich daraufhin selbst mit `... - SKIPPED` in `schema_version` einträgt (Zeile 2393–2400) und nichts tut.
- Bestätigt per Introspektion gegen `backend/data/unfallakten.db`: `SELECT name FROM sqlite_master WHERE type='table' AND name='unfalldetails'` → **leeres Ergebnis**. Schema-Version 47, `unfallakte`-PK ist `az TEXT` (keine Spalte `aktenzeichen`).
- Aus `handover/session_handover_v56.md` (2. Mai 2026): dort wurde bereits an `backend/db/schema_manager.py` eine "Migration-28-Guard (unfalldetails-Tabelle)" ergänzt — das ist exakt der oben beschriebene SKIPPED-Schutz. Das Problem wurde also schon einmal berührt, aber nur das Symptom (Migration-28-Crash) behoben, nicht die eigentliche Lücke (keine Migration legt die Tabelle je an).
- Interessanter Nebenfund: `session_handover_v16.md`-Einträge (`[v16-07]` etc., in `bugs_and_fixes.md`) zeigen, dass `unfalldetails` in früheren Sessions offenbar funktioniert hat. Vermutlich lief die Tabelle einmal über eine Dev-DB, die zwischenzeitlich verworfen/neu aufgesetzt wurde (z. B. `--reset`), ohne dass dabei auffiel, dass die produktive Migrationskette die Tabelle nie selbst erzeugt.

### Ist das Feature aktiv genutzt? — Ja, durchgehend

Nicht totes Feature, sondern **aktiv im Frontend verdrahtet**:

- `frontend/src/components/AkteDetailView.jsx:234` — eigener Tab „🔍 Unfalldetails" in jeder Akte.
- `frontend/src/components/AkteDetailView.jsx:419` — rendert `<UnfalldetailsSection akteId={akte.id} />`.
- `frontend/src/sections/UnfalldetailsSection.jsx:43-74` — ruft `apiKlage.unfalldetails(akteId)` (GET) und `apiKlage.unfalldetailsSpeichern(akteId, form)` (PUT).
- `frontend/src/api.js:296-300` — `unfalldetails`, `unfalldetailsSpeichern`, `wdmLaden` (force_wdm=1) mappen auf `/akten/${az}/unfalldetails`.
- `frontend/src/sections/OnboardingHub.jsx:37` — Kachel #4 „Unfalldetails" im Onboarding-Hub jeder neuen Akte.
- `frontend/src/sections/KlageSection.jsx:456,470,472,628,633,637,647` — der Klage-Tab liest `daten.unfalldetails.{schilderung, haftungsquote, haftungsbegruendung, fahrer_gegner, unfalldatum, ...}` und reicht sie in die Klageschrift-Generierung durch.

Der `App_final.jsx` im übergeordneten `C:\Users\HAL9000\Documents\Projekt\unfallakten` (ohne "Version 1.00") ist ein **anderes, älteres Repo** und für diese Analyse irrelevant — das aktuelle Frontend liegt unter `Version 1.00\unfallakten\frontend\src`.

### Blueprint-Registrierung — aktiv erreichbar

`backend/app.py:35` importiert `unfalldetails_bp` aus `klage_routes.py`, `backend/app.py:170` registriert ihn (`app.register_blueprint(unfalldetails_bp)`) innerhalb von `erstelle_app()`. Keine Auskommentierung, kein Feature-Flag. Die Routen sind live erreichbar.

### Exakte Crash-Stellen (Datei:Zeile)

`backend/routers/klage_routes.py`, Blueprint `unfalldetails_bp = Blueprint(..., url_prefix="/akten/<path:akte_id>/unfalldetails")` (Zeile 37–38):

| Route | Zeile | Query | Guard? |
|---|---|---|---|
| `GET /akten/<az>/unfalldetails` (`hole_unfalldetails`) | 241 | `SELECT * FROM unfalldetails WHERE akte_id = ?` | **Kein try/except** → 500 `sqlite3.OperationalError: no such table: unfalldetails` |
| `PUT /akten/<az>/unfalldetails` (`speichere_unfalldetails`) | 345, 358–359, 364 | `SELECT id ...` / `INSERT INTO unfalldetails (...)` / `SELECT * ...` | **Kein try/except** → 500 crash |
| `GET /akten/<az>/klage/daten` (`hole_klage_daten` o.ä.) | 664–666 | `SELECT * FROM unfalldetails WHERE akte_id = ?` | **try/except Exception: pass** (Zeile 663/667) → degradiert still auf `ud = None`, Klage-Tab lädt trotzdem (Aktivlegitimation/Schilderung fallen auf WDM-Prefill bzw. Default zurück) |
| `POST /akten/<az>/klage/generieren` (`generiere_klage`) | 1231–1233 | `SELECT * FROM unfalldetails WHERE akte_id = ?` | **Kein try/except** → 500 crash — **das ist der eigentliche „Klage schreiben"-Endpunkt** |

Zusätzlich `backend/email_import/import_service.py:1222-1298` (`_ergaenze_unfalldetails`, aufgerufen aus dem Mandanten-Fragebogen-Import, PRD-22c, Zeile 918): komplette Funktion in `try/except Exception as e: logger.warning(...)` gekapselt (Zeile 1236 / 1297-1298) → **kein Crash, aber stiller Datenverlust**: Unfallschilderung und Ermittlungsakte-Aktenzeichen aus dem Online-Unfallbogen werden nie gespeichert, ohne dass irgendjemand das bemerkt (nur ein WARNING-Log).

### Impact-Einschätzung: akut, praktisch (nicht nur theoretisch)

- Der **Unfalldetails-Tab** in jeder Akte ist beim ersten Laden ein 500-Fehler (GET crasht ohne Guard).
- **Speichern von Unfalldetails** (Schilderung, Zeugen, Ermittlungsakte, Fahrer, Haftungsquote/-begründung, Aktivlegitimation) ist komplett unmöglich (PUT crasht).
- **Klageschrift-Generierung** (`POST /klage/generieren`) crasht hart — das ist der produktivste und geschäftskritischste Endpunkt in der ganzen Kanzleisoftware. Jeder Versuch, aus einer Akte eine Klage zu erzeugen, scheitert mit 500.
- Der Klage-**Tab selbst** (nur Anzeige/Vorbereitung) bleibt dank des try/except in `hole_klage_daten` benutzbar, zeigt aber leere/WDM-Fallback-Werte statt der tatsächlich erfassten Unfalldetails.
- Mandanten-Fragebogen-Import verliert still Unfallschilderung + Ermittlungsakte-AZ.

Das ist kein Randfall — sofern die Kanzlei aktuell Klagen über dieses System erstellt oder den Unfalldetails-Tab nutzt, tritt der Bug bei jedem Versuch auf.

### Original-DDL (aus dem toten Root-Legacy-Manager, verifiziert)

`backend/schema_manager.py:1696-1717`:

```sql
CREATE TABLE IF NOT EXISTS unfalldetails (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    akte_id                 TEXT NOT NULL UNIQUE REFERENCES unfallakte(aktenzeichen) ON DELETE CASCADE,
    schilderung             TEXT,
    zeuge_1                 TEXT,
    zeuge_1_anschrift       TEXT,
    zeuge_2                 TEXT,
    zeuge_2_anschrift       TEXT,
    zeuge_3                 TEXT,
    zeuge_3_anschrift       TEXT,
    ermittlungsakte_az      TEXT,
    ermittlungsakte_behoerde TEXT,
    ermittlungsakte_ort     TEXT,
    fahrer_mandant          TEXT,
    fahrer_gegner           TEXT,
    vorsteuerabzug          INTEGER DEFAULT 0,
    haftungsquote           REAL    DEFAULT 100,
    haftungsbegruendung     TEXT,
    erstellt_am             TEXT DEFAULT (datetime('now')),
    geaendert_am            TEXT DEFAULT (datetime('now'))
)
```

**Wichtig — das darf NICHT 1:1 übernommen werden:** `REFERENCES unfallakte(aktenzeichen)` verweist auf eine Spalte, die im aktiven Schema gar nicht existiert (PK von `unfallakte` ist seit Migration 5 `az TEXT`, siehe `handover/bugs_and_fixes.md` Checkliste: *„FKs auf `unfallakte`: Immer `TEXT REFERENCES unfallakte(az)`, niemals `INTEGER`"*). SQLite validiert das bei `CREATE TABLE` nicht sofort, aber es ist eine tickende Zeitbombe, sobald `PRAGMA foreign_keys=ON` irgendwo greift.

Die drei Aktivlegitimations-Spalten aus Migration 28 fehlen in der Original-DDL komplett (die kommen erst per `ALTER TABLE` obendrauf) — sollten in der Neu-DDL direkt mit aufgenommen werden, damit Migration 49 als vollständiger Single-Step funktioniert.

Verifiziert gegen den tatsächlichen Code: Alle vom Nutzer vermuteten Felder (`schilderung`, `zeuge_1..3` + Anschriften, `ermittlungsakte_az/behoerde/ort`, `fahrer_mandant/gegner`, `vorsteuerabzug`, `haftungsquote`, `haftungsbegruendung`) sind korrekt. `aktivlegitimation_typ/freigabe/datum` stammen **nicht** aus der ursprünglichen DDL, sondern aus Migration 28 (separate `ALTER TABLE`-Ergänzung, PRD-24).

### Fix-Optionen

**(a) Neue Migration 49 in `backend/db/schema_manager.py`, die `unfalldetails` korrekt anlegt — EMPFOHLEN.**

Begründung: Das Feature ist aktiv im Frontend verdrahtet (Tab, OnboardingHub, Klage-Tab, Fragebogen-Import) und der betroffene Endpunkt (`POST /klage/generieren`) ist geschäftskritisch. Eine defensive try/except-Lösung (Option b) würde den Crash zwar verhindern, aber das Feature bliebe funktionslos — Schilderung, Zeugen, Haftungsquote etc. blieben dauerhaft nicht speicherbar. Entfernen (Option c) ist ausgeschlossen, das Feature ist offensichtlich gewollt und in Benutzung.

Registrierungsmuster in `backend/db/schema_manager.py` (dreiteilig, exakt wie bei Migration 47/48):

1. Eintrag in der `MIGRATIONS`-Dict (nach Zeile 302, `48: "-- migration_48_queue_felder", ...`):
   ```python
   49: "-- migration_49_unfalldetails_create",  # Handled by _run_migration_49
   ```
2. Neue Funktion (Vorschlag, einzufügen z. B. direkt vor `_run_migration_28` oder ans Ende der Migrationsfunktionen, Konsistenz mit Idempotenz-Pattern aus Migration 47/48 — `PRAGMA table_info`-Guard, `INSERT OR IGNORE INTO schema_version`):

   ```python
   def _run_migration_49(conn: sqlite3.Connection) -> None:
       """
       Migration 49: unfalldetails-Tabelle anlegen (Root-Cause-Fix).

       Die Tabelle wurde nie vom aktiven Schema-Manager erzeugt — nur vom
       toten Root-Legacy-Manager (backend/schema_manager.py), der nie gegen
       die Live-DB lief. Migration 28 setzt seit v56 bereits voraus, dass
       die Tabelle existiert (ALTER TABLE fuer Aktivlegitimation), findet
       sie aber nicht und markiert sich selbst als SKIPPED.

       Diese Migration holt das CREATE TABLE nach — inkl. der drei
       Aktivlegitimations-Spalten aus Migration 28, damit ein Fresh-Setup
       nicht zusätzlich auf Migration 28 angewiesen ist.

       Idempotent: CREATE TABLE IF NOT EXISTS, zusätzlicher Spalten-Check
       falls die Tabelle aus einem älteren Dev-Stand bereits ohne die
       Aktivlegitimations-Spalten existiert.
       """
       conn.executescript("""
           CREATE TABLE IF NOT EXISTS unfalldetails (
               id                          INTEGER PRIMARY KEY AUTOINCREMENT,
               akte_id                     TEXT NOT NULL UNIQUE
                                            REFERENCES unfallakte(az) ON DELETE CASCADE,
               schilderung                 TEXT,
               zeuge_1                     TEXT,
               zeuge_1_anschrift           TEXT,
               zeuge_2                     TEXT,
               zeuge_2_anschrift           TEXT,
               zeuge_3                     TEXT,
               zeuge_3_anschrift           TEXT,
               ermittlungsakte_az          TEXT,
               ermittlungsakte_behoerde    TEXT,
               ermittlungsakte_ort         TEXT,
               fahrer_mandant              TEXT,
               fahrer_gegner               TEXT,
               vorsteuerabzug              INTEGER DEFAULT 0,
               haftungsquote               REAL    DEFAULT 100,
               haftungsbegruendung         TEXT,
               aktivlegitimation_typ       TEXT NOT NULL DEFAULT 'eigentum',
               aktivlegitimation_freigabe  TEXT NOT NULL DEFAULT 'freigabe',
               aktivlegitimation_datum     TEXT,
               erstellt_am                 TEXT DEFAULT (datetime('now','localtime')),
               geaendert_am                TEXT DEFAULT (datetime('now','localtime'))
           );
           CREATE INDEX IF NOT EXISTS idx_unfalldetails_akte
               ON unfalldetails(akte_id);
       """)

       # Falls die Tabelle aus einem alten Dev-Stand noch ohne die
       # Aktivlegitimations-Spalten existiert (CREATE TABLE IF NOT EXISTS
       # greift dann nicht) -> gleiche ALTER-Logik wie Migration 28.
       vorhandene = {r[1] for r in conn.execute(
           "PRAGMA table_info(unfalldetails)").fetchall()}
       for spalte, typ in (
           ("aktivlegitimation_typ",      "TEXT NOT NULL DEFAULT 'eigentum'"),
           ("aktivlegitimation_freigabe", "TEXT NOT NULL DEFAULT 'freigabe'"),
           ("aktivlegitimation_datum",    "TEXT"),
       ):
           if spalte not in vorhandene:
               conn.execute(f"ALTER TABLE unfalldetails ADD COLUMN {spalte} {typ}")

       conn.execute(
           "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
           "VALUES (49, 'Migration 49 - unfalldetails-Tabelle nachtraeglich angelegt (Root-Cause-Fix fuer Migration-28-SKIPPED)')"
       )
       logger.info("Migration 49: unfalldetails-Tabelle angelegt/geprueft.")
   ```
3. Dispatch-Zweig im großen `if/elif` in `run_migrations()` (nach Zeile 863, `elif version == 48: _run_migration_48(conn)`):
   ```python
   elif version == 49:
       _run_migration_49(conn)
   ```

Migration 49 wurde als nächste freie Nummer gewählt, weil `_run_migration_48` (S1.6a, Queue-Felder auf `intake_dokumente`) im Code bereits existiert, aber laut Introspektion der Live-DB **noch nicht gelaufen ist** (Live-Schema steht bei Version 47, Migration 48 ist im Code vorhanden aber "pending"). 49 ist also die nächste tatsächlich freie Nummer nach dem aktuellen Code-Stand.

**(b) Routen defensiv machen (try/except).** Nur als Zwischenlösung sinnvoll, falls (a) aus Zeitgründen nicht sofort umsetzbar ist — verhindert den 500er, lässt das Feature aber weiterhin funktionslos (Speichern liefe weiterhin ins Leere bzw. würde ebenfalls gefangen und stumm nichts tun). Nicht empfohlen als Endzustand, da es ein sichtbares Kanzlei-Feature dauerhaft kaputt beließe.

**(c) Route/Feature entfernen.** Ausgeschlossen — das Feature ist aktiv im Frontend verdrahtet und wird für die Klageschrift-Generierung gebraucht (s.o.).

**Nach dem Fix zusätzlich empfohlen:** Die Beschreibung von Migration 28 in `schema_version` bleibt für Alt-Installationen auf „... SKIPPED" stehen (INSERT OR IGNORE verhindert ein Update). Das ist harmlos (Migration 49 deckt die Spalten mit ab), aber für die nächste Person, die `schema_version` liest, potenziell verwirrend — ggf. in einem Kommentar in Migration 49 erwähnen, dass Migration 28 bewusst SKIPPED bleibt und dadurch redundant, aber unschädlich ist.

---

## Bug 2: `backend/cleanup_abrechnungen.py` — falscher DB-Pfad-Default

### Was das Skript macht

Einmal-Ad-hoc-Tool (kein generisches Cleanup-Utility) für **eine fest kodierte Akte** `AKTE_ID = "31/21"` (Zeile 17):

1. Zeigt vorhandene `abrechnungsschreiben`-Zeilen für Akte 31/21 (Zeile 26-33).
2. Falls keine vorhanden: beendet sich mit „Nichts zu löschen." (Zeile 35-38) — **kein Schaden, wenn Akte im Ziel-DB nicht existiert.**
3. Löscht **alle** `regulierung_positionen` und `abrechnungsschreiben` für Akte 31/21 (Zeile 41-47), mit `PRAGMA foreign_keys = OFF` drumherum.
4. Führt zusätzlich einen Nachzügler-Migrationsschritt aus: prüft ob Spalte `quelle` in `abrechnungsschreiben` fehlt, legt ggf. `quelle`/`gesamt_kuerzung`/`wdm_importiert` per `ALTER TABLE` an (Migration-16-Nachholung, Zeile 49-61) und entfernt einen alten `CHECK`-Constraint auf `regulierung_positionen` per Tabellen-Rebuild (Zeile 63-96).
5. Gibt am Ende Restzeilenanzahl + `schema_version`-Maximum aus (Zeile 100-111).

### Root Cause

`backend/cleanup_abrechnungen.py:15`:
```python
DB_PATH = os.environ.get("DB_PATH", "/app/backend/db/unfallakten.db")
```

Falscher Default: `/app/backend/db/unfallakten.db` entspricht (gemappt auf den Host) `backend/db/unfallakten.db` — der **Karteileiche** (Schema-Version 16, verifiziert). Das korrekte Pattern steht direkt daneben im Repo, in `backend/db/database.py:21`:
```python
DB_PATH = os.environ.get("DB_PATH", str(Path(__file__).parent.parent / "data" / "unfallakten.db"))
```
— also relativ zur Datei aufgelöst, landet konsistent auf `backend/data/unfallakten.db` (die Live-DB).

### Destruktivität, wenn tatsächlich gegen die falsche (Karteileiche-)DB gelaufen

- Wenn Akte „31/21" in der Karteileiche-DB nicht vorkommt: Skript druckt „Nichts zu löschen." und beendet sich — **wirkungslos, kein Schaden.**
- Falls doch: es würden nur `abrechnungsschreiben`/`regulierung_positionen`-Zeilen dieser einen Akte in einer laut Vorrecherche unbenutzten, nicht mehr gelesenen DB gelöscht — praktisch folgenlos, da niemand diese Daten mehr konsultiert.
- Die migrationsartigen Schritte (Schritt 4) sind idempotent/additiv (Spalten-Existenz-Checks, `CREATE TABLE IF NOT EXISTS ... _new` + Rename) und würden bei einer Schema-16-DB vermutlich größtenteils no-op sein (Migration 16 ist dort per Definition bereits gelaufen).
- **Kein Szenario gefunden, in dem ein Lauf gegen die falsche DB die Live-Daten beschädigt** — im schlimmsten Fall täuscht das Skript einen erfolgreichen Cleanup vor, während in Wahrheit die produktive Akte 31/21 unverändert bleibt (stiller Fehlschlag, nicht Datenverlust).

### Aufruf-Kontext: Risiko ist praktisch, nicht (nur) theoretisch niedrig — aber gut mitigiert

Keine Cron-/Makefile-/docker-compose-Automatisierung gefunden: `grep -rn "cleanup_abrechnungen"` über `Makefile`, `docker-compose*.yml`, `*.sh` liefert **nur** die Docstring-Referenz in der Datei selbst (Zeile 5, 8). Das Skript wird ausschließlich manuell ausgeführt.

Der im Docstring dokumentierte Aufrufweg ist:
```
docker exec -it unfallakten-backend-dev python3 /app/backend/cleanup_abrechnungen.py
```

Geprüft, ob `DB_PATH` bei diesem Aufruf bereits gesetzt ist — **ja, doppelt abgesichert:**
- `Dockerfile:46` (builder-Stage, für `unfallakten-backend-dev`) und `Dockerfile:95` (production-Stage) setzen `ENV DB_PATH=/app/data/unfallakten.db` fest im Image.
- `docker-compose.yml:38` setzt zusätzlich `DB_PATH: /app/data/unfallakten.db` als Service-Environment.

`docker exec` erbt die zur Laufzeit im Container gesetzten Environment-Variablen. Da `DB_PATH` bereits durch das Image (`ENV`) **und** durch Compose gesetzt ist, greift der falsche Default im dokumentierten Standardaufruf **nie** — `os.environ.get("DB_PATH", ...)` findet die bereits gesetzte Variable und der Fallback-String kommt gar nicht zum Zug.

Der falsche Default würde nur greifen, wenn:
- jemand das Skript **lokal ohne Docker** ausführt (im Docstring als Alternative genannt: „Oder lokal (Pfad anpassen): `python3 cleanup_abrechnungen.py`" — der Kommentar „Pfad anpassen" ist bereits ein impliziter Hinweis, dass der Default nicht stimmt) — dann existiert `/app/...` auf dem Host aber i. d. R. gar nicht → `sqlite3.connect()` scheitert sofort mit `OperationalError: unable to open database file` (lauter Fehler, kein stiller Fehlgriff), oder
- jemand den Container mit explizit geleertem Environment startet (`docker exec -e DB_PATH= ...` o. ä., unüblich).

**Fazit Risikobewertung:** praktisch gut abgesichert durch zwei unabhängige Schichten (Dockerfile-ENV + Compose-ENV), aber der Code-Default selbst ist trotzdem falsch/inkonsistent und eine Falle für jede zukünftige Änderung an Deploy-Setup oder für lokale Ad-hoc-Läufe außerhalb Docker. Kein Grund zur Panik, aber sollte behoben werden, bevor sich jemand auf den (falschen) Default verlässt.

### Fix-Empfehlung

Default konsistent zum bereits etablierten Pattern aus `backend/db/database.py` machen:

```python
# Vorher (Zeile 11-15):
import sqlite3
import os

# DB-Pfad – anpassen wenn nötig
DB_PATH = os.environ.get("DB_PATH", "/app/backend/db/unfallakten.db")

# Nachher:
import sqlite3
import os
from pathlib import Path

# DB-Pfad – gleiches Pattern wie backend/db/database.py:
# backend/cleanup_abrechnungen.py liegt in backend/, also
# Path(__file__).parent / "data" / "unfallakten.db" = backend/data/unfallakten.db
DB_PATH = os.environ.get("DB_PATH", str(Path(__file__).parent / "data" / "unfallakten.db"))
```

Damit zeigt der Default — unabhängig davon, ob `DB_PATH` gesetzt ist oder nicht, ob Docker oder lokal — konsistent auf die echte Live-DB, exakt wie in `database.py`.

---

## Zusammenfassung für die Fix-Session

| Bug | Root Cause | Impact | Empfehlung |
|---|---|---|---|
| 1 | `backend/db/schema_manager.py` hat nie ein `CREATE TABLE unfalldetails` — nur Migration 28 (ALTER) setzt die Tabelle voraus und findet sie nicht (SKIPPED seit v56) | Akut, praktisch: Unfalldetails-Tab (GET+PUT) und Klageschrift-Generierung (`POST /klage/generieren`) crashen mit 500; Fragebogen-Import verliert still Daten | Neue Migration 49 mit vollständiger DDL (inkl. Aktivlegitimations-Spalten), Entwurf oben |
| 2 | `cleanup_abrechnungen.py` hat falschen Pfad-Default (`/app/backend/db/...` statt `.../data/...`) | Theoretisch vorhanden, praktisch durch Dockerfile-ENV + Compose-ENV doppelt abgesichert — Default wird im dokumentierten Aufrufweg nie erreicht | Default auf `Path(__file__).parent / "data" / "unfallakten.db"` ändern (Pattern aus `database.py` übernehmen) |

Beide Fixes sind low-risk (additiv/idempotent bzw. reine Default-Wert-Korrektur) und sollten in der nächsten Coding-Session zusammen umgesetzt werden — Bug 1 hat Priorität, da er einen produktiv genutzten Endpunkt lahmlegt.
