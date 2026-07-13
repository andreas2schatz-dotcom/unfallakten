# Prompt für die nächste Session — Bugfixing Intake-Pipeline v7, **Priorität P3 (BUG-14–19)**

> Diesen Text in eine frische Session einfügen.

---

Wir setzen das Bugfixing der Dokumenten-Intake-Pipeline fort. Branch: **`intake-stufe1`**.

**Pflichtlektüre zuerst:**
- `docs/TODO.md` (Abschnitt „Offene Bugs / Verbesserungen")
- `docs/BUGFIX_INTAKE_V7.md` — die Bug-Liste mit Prioritäten P0–P4 und Fix-Richtungen. **Das ist die Quelle der Wahrheit.**

**Stand:**
- **P0 BUG-01–04 behoben** (Commit `6c858aa1`, TDD).
- **P1 BUG-05–07 behoben** (Commit `b6826d91`, Doku-Hash `6fc6308b`, TDD).
- **P2 BUG-08–13 behoben** (Commit `7b95be7a`, Doku-Hash `16d2e534`, 2026-07-13, TDD). Tests `backend/tests/test_bugfix_p2_intake_v7.py` (13). Null neue Failures in Pipeline-v7-Dateien; `test_modul3`/`test_modul4`-Failures vorbestehend (per `git stash` gegengeprüft).

Jetzt kommt **Prio P3: BUG-14–19** (Session 4 laut Session-Aufteilung in `BUGFIX_INTAKE_V7.md` — Matching-/Signal-Qualität & UI-Korrektheit).

## Aufgabe: BUG-14 bis BUG-19 fixen (TDD)

Details je Bug in `docs/BUGFIX_INTAKE_V7.md` unter „P3". **BUG-14 + BUG-15 + BUG-16 hängen thematisch zusammen** (Signal-/Absender-Weg) und sollten gemeinsam gelöst werden — dabei den **BUG-03-Mechanismus** (`signale['az']` → `akten_matching.finde_kandidaten`) wiederverwenden. Kurzfassung + Stolpersteine:

1. **BUG-14 — Absender-Signale erreichen Anhänge nie** (`backend/intake/adapter_imap.py:327` + `pipeline.py:91`).
   Anhang-Zustellungen bekommen nur `signale={'dateiname': …}`; Absender-Registry-Signale (`klasse_kandidat`, `versicherer_name`, `vertrauensstufe`) landen nur in der Body-Zustellung, und `pipeline._lade_zustellungs_signale` liest nur die Zustellungen des Dokuments selbst (keine Vererbung über `parent_id`). **Fix-Richtung:** Signale an Anhang-Zustellungen vererben (beim Erzeugen im Adapter **oder** beim Laden via `parent_id`).

2. **BUG-15 — Absender-Mail-Match (Score 0.6) ist toter Code** (`backend/intake/akten_matching.py:87`, `_sammle_signale_mails`).
   Erwartet Signal-Keys `absender`/`absender_email`, die kein Adapter je in `signale_json` schreibt — die Adresse liegt nur in Spalte `zustellungen.absender`. **Fix-Richtung:** Adresse aus der Spalte lesen **oder** als Signal-Key mitschreiben (zusammen mit BUG-14).

3. **BUG-16 — Key-Mismatch `akte_az` vs. `az`: E-Akte-Quelle ohne Vorschlag** (`backend/intake/adapter_eakte.py:49`).
   E-Akte-Adapter schreibt Key `akte_az`, aber `finde_kandidaten` liest nur `az`/`aktenzeichen`/`erkannt_az`. **Fix-Richtung:** Key vereinheitlichen (Remap oder Adapter anpassen) — **derselbe Mechanismus wie BUG-03**.

4. **BUG-17 — KFZ-Muster erkennt keine Umlaut-Kennzeichen** (`backend/intake/akten_matching.py:47`, `_KFZ_MUSTER`).
   Zeichenklasse `[A-ZAEOU]` — gemeint war `[A-ZÄÖÜ]` (TÖL, FÜ, BÖ, GÖ matchen nie). **Fix-Richtung:** `[A-ZÄÖÜ]`; Python-Unicode-`\b`-Verhalten bei Umlauten mitprüfen (Ö ist Wortzeichen).

5. **BUG-18 — Kurze E-Mail-Bodies (<10 Zeichen) werden unterdrückt** (`backend/routers/email_routes.py:912`, `log_eintrag_meta`).
   `body_text` wird nur bei `len(body_stripped) >= 10` zurückgegeben, sonst `""` → „OK, passt"/„Ja" verschwindet. **Fix-Richtung:** Schwellwert entfernen oder nur auf reine Whitespace-/Artefakt-Bodies anwenden.

6. **BUG-19 — Queue-Sortierung: Konfidenz-Schlüssel ist toter Code** (`backend/routers/intake_routes.py:136`, `hole_queue`).
   `ORDER BY i.erstellt_am ASC, i.id ASC, COALESCE(i.konfidenz,0) DESC` — die eindeutige `id` löst jede Bindung vor dem Konfidenz-Schlüssel auf. **Fix-Richtung:** Reihenfolge korrigieren (`erstellt_am ASC, konfidenz DESC, id ASC`) — oder toten Schlüssel streichen + Docstring/Spec anpassen.

## Arbeitsregeln (verbindlich)

- **TDD**: erst fehlschlagender Test, ihn fehlschlagen sehen, dann minimaler Fix. Muster: `backend/tests/test_bugfix_p2_intake_v7.py` (P2) / `test_bugfix_p1_intake_v7.py` (P1).
- **RA-MICRO bleibt read-only** — nur SQLite schreiben.
- **Baseline diffbasiert grün halten**: ~204 vorbestehende Failures in Alt-Clustern (`test_modul3`/`test_modul4`/`test_modul7`) NICHT anfassen. Verdächtige Failures per `git stash` gegenprüfen. Maßgeblich: null neue Failures in Pipeline-v7-Dateien.
- **Guard-Test beachten**: `test_s19_intake_write_guard.py` (Zeilennummern-Whitelist) bei Edits an gelisteten Dateien mit-aktualisieren.

## Testausführung

- Python 3.14, pytest, System-Python (kein venv). cwd = Repo-Root.
- Env-Var nötig: `export JWT_SECRET_KEY=test-secret-key-minimum-32-chars!!`
- Gezielter v7-Regressionslauf:
  ```
  python -m pytest backend/tests/ -k "intake or s19 or eingehende or freigabe or positionen or bugfix or matching or eakte or email or adapter or queue" --tb=short -q
  ```

## Abschluss der Session

- Neue Tests in `backend/tests/test_bugfix_p3_intake_v7.py` anlegen.
- In `docs/BUGFIX_INTAKE_V7.md`: Checkbox `[x]`, Fix-Notiz + **Commit-Hash**, Status-Tabelle auf „behoben ✅". Danach Doku-Hash-Nachtrag-Commit.
- `docs/TODO.md` Abschnitt „Offene Bugs" fortschreiben (P3 erledigt, P4 als nächstes).
- Memory aktualisieren (`project_unfallakten_pipeline_v7.md` + `MEMORY.md`-Zeile).
- Committen (Branch `intake-stufe1`, nicht pushen außer auf Ansage). Commit-Message-Stil `fix(intake-v7): …`.

## Alternativ statt P3

Falls stattdessen die Feature-Arbeit Vorrang hat: **P1.8** (Backfill synthetischer Ereignisse) — Prompt `handover/naechste_session_P1_8_prompt.md`. P3/P4 sind reine Aufräum-/Qualitäts-Bugs und nicht blockierend.
