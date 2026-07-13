# Prompt für die nächste Session — Bugfixing Intake-Pipeline v7, **Priorität P2 (BUG-08–13)**

> Diesen Text in eine frische Session einfügen.

---

Wir setzen das Bugfixing der Dokumenten-Intake-Pipeline fort. Branch: **`intake-stufe1`**.

**Pflichtlektüre zuerst:**
- `docs/TODO.md` (Abschnitt „Offene Bugs / Verbesserungen")
- `docs/BUGFIX_INTAKE_V7.md` — die Bug-Liste mit Prioritäten P0–P4 und Fix-Richtungen. **Das ist die Quelle der Wahrheit.**

**Stand:**
- **P0 BUG-01–04 behoben** (Commit `6c858aa1`, TDD, voller v7-Rerun 237p/0f/2s).
- **P1 BUG-05–07 behoben** (Commit `b6826d91`, Doku-Hash-Nachtrag `6fc6308b`, 2026-07-13, TDD). Tests `backend/tests/test_bugfix_p1_intake_v7.py` (13). Gefilterter v7-Lauf 207p/9f — die 9 Failures sind vorbestehend in Alt-Clustern `test_modul3`/`test_modul4` (per `git stash` gegengeprüft), null neue Failures in Pipeline-v7-Dateien.

Jetzt kommt **Prio P2: BUG-08–13** (Session 3 laut Session-Aufteilung in `BUGFIX_INTAKE_V7.md` — Infrastruktur: Deadlock, Scheduler, Validierung, OCR, Migration 50).

## Aufgabe: BUG-08 bis BUG-13 fixen (TDD)

Diese sechs Bugs sind **thematisch unabhängig** (anders als P1) — wenn eine Session zu voll wird, ist ein sinnvoller Schnitt möglich (z. B. BUG-08/09/11 = testbare Route-/Service-Fixes zuerst, BUG-10/12/13 = Scheduler/OCR/Migration danach). Details je Bug in `docs/BUGFIX_INTAKE_V7.md` unter „P2". Kurzfassung + Stolpersteine:

1. **BUG-08 — Freigabe auf RA-MICRO-only-Akten → 404** (`backend/routers/intake_routes.py:535`, `post_freigabe`).
   Die Akten-Validierung prüft `akte_az` nur gegen die SQLite-Tabelle `unfallakte`. Kandidaten kommen aber auch aus RA-MICRO (`_suche_in_ramicro`, `/aktensuche` liest `tblAkten`). Vorgeschlagene RA-MICRO-only-Akte wählen → 404. **Fix-Richtung:** Alt-Pfad-Verhalten (`pruefe_akte`-Fallback) wiederherstellen oder die Akte beim Freigeben automatisch **in SQLite** anlegen. ⚠️ **RA-MICRO bleibt read-only** — Anlage NUR in SQLite. Hängt logisch mit dem BUG-06-Guard zusammen (beide in `post_freigabe`, Reihenfolge der Prüfungen beachten: erst existiert-Prüfung/Anlage, dann verworfen/freigegeben-Guard bleibt korrekt).

2. **BUG-09 — SQLite-Selbstblockade im Fristablauf-Job** (`backend/services/fristablauf_service.py:134–137`, `verarbeite_faellige_todos`).
   Äußeres `with get_connection()` hält eine unkommittierte Schreibtransaktion; `schreibe_ereignis` öffnet pro Todo eine **neue** Verbindung → wartet auf denselben Write-Lock → „database is locked" ab der 2. Frist. **Fix-Richtung:** eine Verbindung durchreichen (Parameter an `schreibe_ereignis`) **oder** pro Todo committen. Prüfen, ob `schreibe_ereignis` bereits einen optionalen `conn`-Parameter hat/bekommen kann, ohne den Guard-Test (`test_s19_intake_write_guard.py` / Ereignis-Write-Guard) zu verletzen. Testbar: 2 fällige Todos → beide bekommen ihr Ereignis.

3. **BUG-10 — Scheduler laufen unter Gunicorn 4-fach parallel** (`gunicorn.conf.py:19` + `backend/app.py`, `erstelle_app()`).
   Jeder Worker registriert eigene APScheduler (imap_polling 60 s, intake_worker 10 s, fristablauf 03:15). Nur der Intake-Tick ist per Lease geschützt. **Fix-Richtung:** Scheduler nur in genau einem Prozess starten (Env-Flag / dedizierter Prozess / DB-Lease für **alle** Jobs analog Intake-Tick). Schwer als reiner Unit-Test — die Lease-/Guard-Logik testen (nur ein Lauf trotz mehrfacher Auslösung). Mit BUG-09 verwandt (4× dupliziert die Fristablauf-Ereignisse zusätzlich).

4. **BUG-11 — Upload-Validierung umgangen** (`backend/routers/dokumente_routes.py:147`, Review-Pflicht-Pfad 144–164).
   Der Review-Pflicht-Upload umgeht `verarbeite_upload()` → keine Erweiterungs-Whitelist, kein Leere-Datei-/`MAX_DATEIGROESSE`-Check, keine PDF-Signaturprüfung. `adapter_upload.verarbeite_datei` akzeptiert beliebige Bytes (Fallback `bin`). **Fix-Richtung:** dieselben Checks (`_validiere_datei`, `validiere_pdf`, `GUELTIGE_TYPEN`) VOR `_intake_upload` ziehen → 422 statt 202. Testbar: Überlange/leere/gefälschte Datei → 422.

5. **BUG-12 — O(n²)-OCR** (`backend/intake/pipeline.py:118`, `_ocr_seite`).
   Ruft pro OCR-Seite `ocr_service.pdf_zu_bildern(pdf_bytes)` → rendert **alle** Seiten mit 300 dpi, nutzt nur eine. 30 Seiten → 900 Renderings, Lease-Ablauf, Worker-Doppelung. **Fix-Richtung:** einmal vor der Schleife konvertieren **oder** `first_page`/`last_page` von pdf2image nutzen. Testbar: Mock auf `pdf_zu_bildern` zählt Aufrufe (soll linear, nicht quadratisch sein).

6. **BUG-13 — Migration 50 verletzt `executescript()`-Verbotsregel** (`backend/db/schema_manager.py:2844`).
   Migration 50 kombiniert `conn.executescript()` mit nachfolgenden `ALTER TABLE` ohne explizites `conn.commit()` davor/danach — genau das Verbotsmuster (siehe Memory `feedback_migration_executescript`). **Fix-Richtung:** Migration 50 auf das Muster der Migrationen 52–55 umbauen (einzelne `execute`-Aufrufe, explizite Commits). ⚠️ **Wichtig:** Migration 50 ist auf Live-/Dev-DBs bereits eingespielt (schema_version ≥ 50) — ein Edit ändert nur das Verhalten bei **frischen** DBs, ein Re-Run findet NICHT statt. Also reiner Regelkonformitäts-/Fresh-Install-Fix, keine Datenmigration. Nicht versuchen, die bestehende DB neu zu migrieren.

## Arbeitsregeln (verbindlich)

- **TDD**: erst fehlschlagender Test, ihn fehlschlagen sehen, dann minimaler Fix. Kein Refactoring über den Fix hinaus. Muster: `backend/tests/test_bugfix_p1_intake_v7.py` (P1) / `test_bugfix_p0_intake_v7.py` (P0).
- **RA-MICRO bleibt read-only** — nur SQLite schreiben (besonders BUG-08).
- **Baseline grün halten**: Es gibt **~204 vorbestehende Failures in Alt-Clustern** (z. B. `test_modul3`/`test_modul4` scheitern im `setUp` an veraltetem Aktenzeichen-Format / Auth-Bootstrap; `test_modul7` an `ModuleNotFoundError`). NICHT anfassen. Maßgeblich ist der **diffbasierte Check**: null neue Failures in Pipeline-v7-Dateien. Verdächtige Failures per `git stash` gegenprüfen (fallen sie ohne den Diff genauso? → vorbestehend).
- **Guard-Test beachten**: `test_s19_intake_write_guard.py` hat eine Whitelist mit **Zeilennummern** von `registriere_dokument`-Aufrufen (u. a. `import_service.py`). Bei Edits, die diese Dateien verschieben, Whitelist mit-aktualisieren. Analog gibt es den Ereignis-Write-Guard (nur `ereignis_service.py` darf in die 3 Ereignis-Tabellen schreiben) — für BUG-09 relevant, falls `schreibe_ereignis` angefasst wird.
- **Migrationen** (BUG-13): kein `executescript()`, explizites `conn.commit()` vor/nach `ALTER TABLE`, Migration atomar in EINEM Edit. Achtung Reloader-Trap (Memory `feedback_migration_reloader_trap`).

## Testausführung

- Python 3.14, pytest 9, **kein venv** (System-Python), kein `pytest.ini`. cwd = Repo-Root.
- Env-Var nötig: `export JWT_SECRET_KEY=test-secret-key-minimum-32-chars!!`
- Tests sind `unittest.TestCase`, laufen aber unter pytest. DB-Setup-Muster (aus `test_bugfix_p1_intake_v7.py` übernehmen): temp-`DB_PATH` + `importlib.reload(...)` + `init_db()` bzw. `create_schema()/run_migrations()`. Route-Tests: `_RouteBasis` mit `erstelle_app({"TESTING": True})` + `_login()`. Flag-Toggle: `os.environ["INTAKE_REVIEW_PFLICHT"]`.
- Gezielter v7-Regressionslauf (~3 Min):
  ```
  python -m pytest backend/tests/ -k "intake or s19 or eingehende or freigabe or positionen or bugfix or fristablauf or pipeline or upload or migration_50" --tb=short -q
  ```

## Abschluss der Session

- Neue Tests in `backend/tests/test_bugfix_p2_intake_v7.py` anlegen (konsistent benennen).
- In `docs/BUGFIX_INTAKE_V7.md`: Checkbox `[x]` setzen, Fix-Notiz + **Commit-Hash** hinter den Titel schreiben, Status-Tabelle auf „behoben ✅" (Muster wie BUG-05–07). Danach Doku-Hash-Nachtrag-Commit wie `6fc6308b`.
- `docs/TODO.md` Abschnitt „Offene Bugs" fortschreiben (P2 erledigt, P3 als nächstes).
- Memory aktualisieren (`project_unfallakten_pipeline_v7.md` + `MEMORY.md`-Zeile).
- Committen (Branch `intake-stufe1`, nicht pushen außer auf Ansage). Commit-Message-Stil `fix(intake-v7): …`.

## Referenz: die bisherigen Fixes (als Muster)

- **P1 BUG-05** `_feld_zu_zahl` → `parse_betrag` (int/float-Kurzschluss bleibt, unparsbar → None). **Bekannte Grenze:** `parse_betrag` kann US-Tausender `'1,234.56'` trotz Docstring nicht (→ None) — falls in P2/später relevant, ist das ein eigener bewusster Fix an `parse_betrag` (shared parser, andere Aufrufer prüfen).
- **P1 BUG-06** Guard in `post_freigabe` (Pendant zu `post_verwerfen`): 409 bei `verworfen_am`/`queue_status='freigegeben'`. Mehrfach-Freigabe in andere Akte bewusst gesperrt — falls BUG-08 das RA-MICRO-Anlegen ergänzt, den Guard-Reihenfolge im `post_freigabe` sauber halten.
- **P1 BUG-07** `_anker_dokument_id(intake_id, dokument_id, akte_az)` mit `akte_az`-Filter.
- **Offener Folge-Task aus P0/BUG-01** (kein P2): Feld-Übernahme beim Freigeben eines Unfallbogens (Mandant/Gegner/Unfall/Personenschaden) — Freigabe-Dialog muss Fragebogen-Felder verstehen. Eigenes Feature.
