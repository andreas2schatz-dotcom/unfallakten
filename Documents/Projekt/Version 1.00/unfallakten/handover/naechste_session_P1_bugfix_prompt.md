# Prompt für die nächste Session — Bugfixing Intake-Pipeline v7, **Priorität P1 (BUG-05–07)**

> Diesen Text in eine frische Session einfügen.

---

Wir setzen das Bugfixing der Dokumenten-Intake-Pipeline fort. Branch: **`intake-stufe1`**.

**Pflichtlektüre zuerst:**
- `docs/TODO.md` (Abschnitt „Offene Bugs / Verbesserungen")
- `docs/BUGFIX_INTAKE_V7.md` — die Bug-Liste mit Prioritäten P0–P4 und Fix-Richtungen. **Das ist die Quelle der Wahrheit.**

**Stand:** Die **P0-Bugs BUG-01–04 sind behoben** (Commit `6c858aa1`, TDD, voller v7-Rerun 237p/0f/2s). Jetzt kommt **Prio P1: BUG-05, BUG-06, BUG-07** (Session 2 laut der Session-Aufteilung in `BUGFIX_INTAKE_V7.md`).

## Aufgabe: BUG-05, BUG-06, BUG-07 fixen (alle in einer Session, TDD)

Details stehen in `docs/BUGFIX_INTAKE_V7.md` unter „P1 — Kritisch: Falsche Daten in der Akte". Kurzfassung:

1. **BUG-05 — Beträge werden verhundertfacht** (`backend/services/eingehende_ereignisse.py:466`, `_feld_zu_zahl`).
   `_feld_zu_zahl` entfernt strikt alle Punkte (deutsche Notation) → `"850.00"` (LLM-Output mit Dezimalpunkt) wird zu `85000.0`. **Fix-Richtung:** den vorhandenen format-sicheren Helper `backend/parsers/pdf_utils.parse_betrag` verwenden (kann `1.234,56`, `1234.56`, `1,234.56`). Vorsicht: nicht in andere Notationen zurückregressieren — Testfälle für alle drei Formate schreiben.

2. **BUG-06 — Verworfene/bereits freigegebene Dokumente freigebbar** (`backend/routers/intake_routes.py:530–532`, `post_freigabe`).
   Prüft weder `verworfen_am` noch `queue_status`. **Fix-Richtung:** Guard → HTTP 409 bei `verworfen_am IS NOT NULL` oder `queue_status='freigegeben'`. Gegenrichtung (`post_verwerfen`) hat den 409-Guard bereits — als Muster ansehen. Klären, ob Mehrfach-Freigabe in **andere** Akte bewusst erlaubt bleiben soll (dann mit BUG-07 zusammen entscheiden).

3. **BUG-07 — Ereignis-Anker zeigt auf Dokument fremder Akte** (`backend/routers/intake_routes.py:660`, `_anker_dokument_id`).
   Nimmt immer die **erste** Freigabe (`ORDER BY id ASC LIMIT 1`) ohne `akte_az`-Filter → bei Freigabe derselben Zustellung in zwei Akten zeigt der Anker in die falsche. **Fix-Richtung:** `WHERE intake_dokument_id=? AND akte_az=?`.

BUG-06 und BUG-07 hängen thematisch zusammen (beide `post_freigabe`/Anker) — sinnvoll gemeinsam bearbeiten.

## Arbeitsregeln (verbindlich)

- **TDD**: erst fehlschlagender Test, ihn fehlschlagen sehen, dann minimaler Fix. Kein Refactoring über den Fix hinaus. Muster: `backend/tests/test_bugfix_p0_intake_v7.py` (P0-Fixes dieser Serie).
- **RA-MICRO bleibt read-only** — nur SQLite schreiben.
- **Baseline grün halten**: Es gibt **~204 vorbestehende Failures in Alt-Clustern** (z. B. `test_modul7.py` scheitert im `setUp` an `ModuleNotFoundError: backend.email_import.parser` — vor langer Zeit umbenannt; NICHT anfassen, nicht meine/deine Regression). Maßgeblich ist der **diffbasierte Check**: null neue Failures in Pipeline-v7-Dateien.
- **Guard-Test beachten**: `test_s19_intake_write_guard.py` hat eine Whitelist mit **Zeilennummern** von `registriere_dokument`-Aufrufen in u. a. `import_service.py`. Wenn Edits diese Datei verschieben, die Whitelist mit-aktualisieren (reiner Status-Quo-Anker, kein neuer Schreibpfad).
- **Migrationen** (falls nötig): kein `executescript()`, explizites `conn.commit()` vor/nach `ALTER TABLE`, Migration atomar in EINEM Edit. Achtung Reloader-Trap (siehe Memory `feedback_migration_reloader_trap`).

## Testausführung

- Python 3.14, pytest 9, **kein venv** (System-Python), kein `pytest.ini`. cwd = Repo-Root.
- Env-Var nötig: `export JWT_SECRET_KEY=test-secret-key-minimum-32-chars!!`
- Tests sind `unittest.TestCase`, laufen aber unter pytest. DB-Setup-Muster: temp-`DB_PATH` + `importlib.reload(backend.db.database, schema_manager)` + `create_schema()/run_migrations()` bzw. `init_db()`. Flag-Toggle: `os.environ["INTAKE_REVIEW_PFLICHT"]` (Funktion liest live).
- Gezielter v7-Regressionslauf (dauert ~3 Min):
  ```
  python -m pytest backend/tests/ -k "intake or s19 or s16 or s17 or s18 or adapter or registry or bugfix_p0 or positionen or eingehende or freigabe" --tb=short -q
  ```
- Für BUG-05 zusätzlich die Positions-/Ereignis-Tests laufen lassen (`test_p15e_freigabe_ereignisse.py`, `test_intake_*`).

## Abschluss der Session

- Neue Tests in `backend/tests/test_bugfix_p0_intake_v7.py` ergänzen oder eine `test_bugfix_p1_intake_v7.py` anlegen (konsistent benennen).
- In `docs/BUGFIX_INTAKE_V7.md`: Checkbox `[x]` setzen, Fix-Notiz + **Commit-Hash** hinter den Titel schreiben, Status-Tabelle auf „behoben ✅".
- `docs/TODO.md` Abschnitt „Offene Bugs" fortschreiben.
- Committen (Branch `intake-stufe1`, nicht pushen außer auf Ansage). Commit-Message-Stil wie `6c858aa1` (`fix(intake-v7): …`).

## Referenz: die P0-Fixes (als Muster)

- **BUG-01** Fragebogen: `_fragebogen_in_intake_queue()` in `import_service.py` legt den Unfallbogen verlustfrei als Text-`intake_dokument` + `zustellung` (Signal `az`) in die Review-Queue. **Offener Folge-Task:** Feld-Übernahme (Mandant/Gegner/Unfall/Personenschaden) beim **Freigeben** des Unfallbogens — Freigabe-Dialog muss die Fragebogen-Felder verstehen. Eigenes Feature, nicht Teil P1.
- **BUG-03** nutzt Signal-Key **`az`** (= derselbe Mechanismus, den **BUG-16** für den E-Akte-Adapter braucht — beim späteren P3-Fix wiederverwenden).
