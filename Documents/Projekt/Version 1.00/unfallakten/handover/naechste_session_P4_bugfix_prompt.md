# Prompt für die nächste Session — Bugfixing Intake-Pipeline v7, **Priorität P4 (BUG-20–30)**

> Diesen Text in eine frische Session einfügen.

---

Wir schließen das Bugfixing der Dokumenten-Intake-Pipeline v7 ab. Branch: **`intake-stufe1`**. P4 ist die letzte Prio-Stufe des Code-Reviews — danach ist die Bugfix-Reihe komplett.

**Pflichtlektüre zuerst:**
- `docs/TODO.md` (Abschnitt „Offene Bugs / Verbesserungen")
- `docs/BUGFIX_INTAKE_V7.md` — die Bug-Liste mit Prioritäten P0–P4 und Fix-Richtungen. **Das ist die Quelle der Wahrheit.**

**Stand (alles TDD, Branch `intake-stufe1`, nicht gepusht):**
- **P0 BUG-01–04 behoben** (Commit `6c858aa1`).
- **P1 BUG-05–07 behoben** (Commit `b6826d91`, Doku-Hash `6fc6308b`).
- **P2 BUG-08–13 behoben** (Commit `7b95be7a`, Doku-Hash `16d2e534`).
- **P3 BUG-14–19 behoben** (Commit `88271a6a`, Doku-Hash `f54f6791`, 2026-07-13). Tests `backend/tests/test_bugfix_p3_intake_v7.py` (8).

Jetzt kommt **Prio P4: BUG-20–30** — reine Performance- & Code-Hygiene-Bugs. Sie sind **nicht blockierend** und **mechanisch/gut parallelisierbar**, aber wir wollen die Reihe konzentriert zu Ende bringen.

## Aufgabe: BUG-20 bis BUG-30 fixen (TDD)

Details je Bug in `docs/BUGFIX_INTAKE_V7.md` unter „P4". Kurzfassung + Stolpersteine:

1. **BUG-20 — hole_queue lädt komplettes parse_json pro Zeile** (`backend/routers/intake_routes.py:141`).
   Pro Queue-Zeile wird das ganze `parse_json` (inkl. `text_gesamt`) deserialisiert, nur um `akten_kandidaten[0]` zu ziehen — bei jedem 30-s-Poll. **Fix-Richtung:** `json_extract(parse_json,'$.akten_kandidaten[0]')` im SELECT, oder Top-Kandidat beim Pipeline-Stempeln in eine eigene Spalte schreiben. **Stolperstein:** BUG-19-Sortierung nicht kaputt machen; Frontend erwartet weiterhin `akte_kandidat_top`.

2. **BUG-21 — 4 identische korrelierte Subselects auf zustellungen** (`backend/routers/intake_routes.py:125`).
   `hole_queue` nutzt vier identische korrelierte Subselects (`ORDER BY z.id LIMIT 1`) für `zustellung_id`/`parent_id`/`absender`/`betreff`. **Fix-Richtung:** ein LEFT JOIN auf die erste Zustellung (`MIN(z.id)` je `intake_dokument_id`). **Stolperstein:** dieselbe „erste Zustellung"-Semantik wahren; mit BUG-20 zusammen in einem Query-Umbau lösbar.

3. **BUG-22 — Eigenes `_pruefe_akte` ohne AZ-Normalisierung** (`backend/routers/positionen_routes.py:45`).
   Exakter az-Vergleich statt Helper `backend/routers/_helpers.pruefe_akte` mit `_normiere_az`. **Fix-Richtung:** Helper verwenden — **Rückgabewert IMMER für die az-Extraktion nutzen** (Projekt-Regel, sonst 404 bei Schreibweise `28526`).

4. **BUG-23 — IMAP-Config dupliziert, EMAIL_FOLDER/MAX_FETCH ignoriert** (`backend/email_import/import_service.py:67`, `_imap_cfg_fuer_konto`).
   Dupliziert `polling_service._imap_config_fuer_account` mit fest `folder='INBOX'`/`max_fetch=50`. **Fix-Richtung:** gemeinsame Config-Funktion. **Stolperstein:** `import_service.py` steht in der **Guard-Whitelist** (`test_s19_intake_write_guard.py`) — Zeilennummern der Alt-Aufrufer bei Verschiebung mit-aktualisieren.

5. **BUG-24 — `_html_zu_text` ist divergierte Kopie aus email_parser** (`backend/intake/adapter_imap.py:178`).
   Kopie von `email_parser._html_zu_text`/`_extrahiere_text`, bereits divergiert (Adapter filtert unlesbaren Binär-Text NICHT). **Fix-Richtung:** Import statt Duplikat. **Stolperstein:** `dekodiere_email_payload` ist bewusst adapter-lokal (eigene Wahrheitsquelle) — prüfen, was importierbar ist, ohne Zirkelimport. Beachte [[unfallakten-pipeline-v7]] BUG-14/15-Änderungen im selben Modul.

6. **BUG-25 — Arbeitskopie-Set dupliziert `archiv._KONVERTER`-Keys** (`backend/intake/_persistenz.py:30`, `_ARBEITSKOPIE_UNTERSTUETZT`).
   Handgepflegtes Set `{pdf,docx,doc,jpg,jpeg,png}`. **Fix-Richtung:** aus `archiv._KONVERTER.keys()` ableiten.

7. **BUG-26 — KLASSEN hartcodiert statt aus Backend-Registry** (`frontend/src/views/ReviewQueueView.jsx:19`).
   Frontend-Kopie der Registry-Klassen (`backend/registry/klassen/*.yaml`). Ereignistypen werden bereits per Endpoint geladen (`apiIntake.ereignistypen`). **Fix-Richtung:** Klassen-Endpoint analog + Frontend lädt dynamisch. **Stolperstein:** Frontend-Test (Vitest) mit-anpassen; Endpoint braucht keinen Auth-Sonderfall (Registry ist statisch).

8. **BUG-27 — Toter Parameter `hat_bestritten_only`** (`backend/services/positionsstatus_service.py:77`, `_zustand`).
   Nie verwendet, einziger Aufrufer übergibt fest `False`. **Fix-Richtung:** ersatzlos streichen (Signatur + Aufrufstelle).

9. **BUG-28 — `Registry.fehler` wird nie befüllt** (`backend/intake/registry_loader.py:43`).
   Liste initialisiert, aber alle Fehlerpfade werfen `RuntimeError` → totes Feld. **Fix-Richtung:** Feld entfernen (oder Soft-Fehler tatsächlich sammeln — Feld entfernen ist einfacher/ehrlicher).

10. **BUG-29 — `date.today()`-Block 4× copy-gepastet** (`backend/services/eingehende_ereignisse.py:232` u.a.).
    In `erzeuge_aus_beleg`/`erzeuge_aus_gutachten`/`erzeuge_aus_wdm`/`erzeuge_aus_freigabe` identisch. `ausgehende_ereignisse.py` macht es bereits mit Modul-Import + Einzeiler. **Fix-Richtung:** Modul-Import + kleiner Helper. **Stolperstein:** P1.5e-Tests (`test_p15e_freigabe_ereignisse.py`) nicht brechen — reines Refactoring, Verhalten identisch.

11. **BUG-30 — `wartAufWorker` pollt nach Unmount unkündbar weiter** (`frontend/src/views/ReviewQueueView.jsx:503`).
    Unkündbare while-Schleife bis 30 s, auch nach Unmount/Dokumentwechsel (`key`-Re-Mount) → setState auf unmounteter Komponente. **Fix-Richtung:** Abbruch-Flag/AbortController beim Unmount bzw. Dokumentwechsel. **Stolperstein:** die P1.5e-Follow-up-Logik (`skipFormReset`, Commit `74400131`) im selben `wartAufWorker` nicht kaputt machen.

## Arbeitsregeln (verbindlich)

- **TDD**: erst fehlschlagender Test, ihn fehlschlagen sehen, dann minimaler Fix. Muster: `backend/tests/test_bugfix_p3_intake_v7.py` (P3) / `test_bugfix_p2_intake_v7.py` (P2). Reine Refactorings (BUG-27/28/29): Test, der Verhalten/Signatur nach dem Fix festnagelt (bei „Feld streichen" ein Test, der die Abwesenheit prüft — vorher rot, weil Feld/Param noch da).
- **RA-MICRO bleibt read-only** — nur SQLite schreiben.
- **Baseline diffbasiert grün halten**: vorbestehende Failures in Alt-Clustern (`test_modul3`/`test_modul4`/`test_modul7` — u.a. `ModuleNotFoundError: backend.email_import.parser`) NICHT anfassen. Verdächtige Failures per `git stash` gegenprüfen. Maßgeblich: **null neue Failures in Pipeline-v7-Dateien**.
- **Guard-Test beachten**: `test_s19_intake_write_guard.py` (Zeilennummern-Whitelist) bei Edits an gelisteten Dateien (v.a. **BUG-23** in `import_service.py`) mit-aktualisieren.
- **Frontend-Bugs (BUG-26, BUG-30)**: Vitest (`npm test`), 44er-Baseline halten.

## Testausführung

- Python 3.14, pytest, System-Python (kein venv). cwd = Repo-Root.
- Env-Var nötig: `export JWT_SECRET_KEY=test-secret-key-minimum-32-chars!!`
- Gezielter v7-Regressionslauf:
  ```
  python -m pytest backend/tests/ -k "intake or s19 or eingehende or freigabe or positionen or bugfix or matching or eakte or email or adapter or queue or persistenz or registry" --tb=short -q
  ```
- Frontend: `cd frontend && npm test`

## Abschluss der Session

- Neue Tests in `backend/tests/test_bugfix_p4_intake_v7.py` anlegen (+ ggf. Vitest für BUG-26/30).
- In `docs/BUGFIX_INTAKE_V7.md`: Checkbox `[x]`, Fix-Notiz + **Commit-Hash**, Status-Tabelle auf „behoben ✅". Danach Doku-Hash-Nachtrag-Commit.
- `docs/TODO.md` Abschnitt „Offene Bugs" fortschreiben (**P4 erledigt → Bugfix-Reihe komplett**).
- Memory aktualisieren (`project_unfallakten_pipeline_v7.md` + `MEMORY.md`-Zeile).
- Committen (Branch `intake-stufe1`, nicht pushen außer auf Ansage). Commit-Message-Stil `fix(intake-v7): …`.

## Danach

Bugfix-Reihe abgeschlossen. Weiter mit **P1.8** (Backfill synthetischer Ereignisse) — Prompt `handover/naechste_session_P1_8_prompt.md` — bzw. N-01–N-06 (Pipeline-Qualität). Offene Feature-Folge-Tasks: Fragebogen-Feld-Übernahme bei Freigabe (aus BUG-01) und **ReviewQueue-Druckbutton** (siehe TODO).
