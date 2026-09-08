# Prompt für nächste Session: Test-Sanierung test_modul6 + test_modul7 (95 Fehlschläge)

> Diesen Text als Auftrag in die neue Session kopieren.

---

Bitte saniere die 95 vorbestehenden Test-Fehlschläge in `backend/tests/test_modul6.py` und `backend/tests/test_modul7.py` (Branch `abschlussbericht`).

## Kontext

- Entdeckt bei der Forderungsschreiben-Bugfix-Runde 2026-08-11 (Protokoll: `bugfixes.md` im Projektroot, CHANGELOG-Eintrag 2026-08-11). Die Zahl 95 war vor und nach allen damaligen Änderungen identisch — reine Test-Verrottung, keine Regression.
- Testlauf: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_modul6.py backend/tests/test_modul7.py -q` → zuletzt 95 failed, 35 passed.
- Bereits bekannte Befund-Verteilung (Stand 2026-08-11):
  - **modul7 · TestEmailParser (17):** `ImportError: cannot import name 'parser' from 'backend.email_import'` — die Tests prüfen eine API, die es nach den E-Mail-Workflow-Umbauten (PRD-22d, E-Mail-Workflow-Redesign 2026-06) nicht mehr gibt.
  - **modul7 · TestEmailRouten (15) / TestImportService (10) / TestAkteMatching (6):** vermutlich Mischung aus derselben toten API, Auth-Bootstrap und AZ-Format-Drift.
  - **modul6 · TestNginxKonfiguration (13) / TestKonfigurationsdateien (13) / TestBackupInfra (9) / TestGitignore (7) / TestMakefile (4) / TestHealthEndpunkt (1):** Datei-Existenz-Checks wie `_exists("nginx/nginx.conf")` schlagen fehl, weil diese Pfade im Backend-Container (`/app`) nicht gemountet sind — die Tests können im Container prinzipiell nicht grün werden. Klären: Pfad-Auflösung relativ zur Repo-Wurzel auf dem Host? Wurden sie früher auf dem Host ausgeführt? (Memory-Hinweis: `TestBackupInfra` war mal ein bewusster Guard-Test, siehe Memory `feedback_unfallakten_backup_konsistenz`.)

## Bekannte Fallen aus der modul5-Sanierung (gleiche Verrottungsklasse, dort schon gefixt — als Muster nutzen)

1. **AZ-Format:** `POST /akten` validiert seit Juli das Format `####/YY` bzw. `####/YYSB` (z. B. `955/25`). Alte Test-AZ wie `25-W5-001` → 422. Fix-Muster: Commit `a4cf92ca` (test_modul5).
2. **Auth-Bootstrap:** `backend/tests/conftest.py` setzt `ADMIN_EMAIL`/`ADMIN_PASSWORT`/`ADMIN_NAME` — Registrierung per `/auth/register/erster` gibt sonst 409 → Login-`KeyError: 'access_token'`.
3. **git stash-Falle:** `git stash` + `pop` auf diesem Repo macht gestagte `git rm`-Löschungen unstaged — nach jedem stash/pop den Index prüfen (Memory `project-unfallakten-forderungsschreiben-review`).

## Vorgehen (bitte in dieser Reihenfolge)

1. **Bestandsaufnahme:** Vollen Lauf machen, jede Fehlerklasse einem der drei Typen zuordnen: (a) Test verrottet, Produktverhalten ok → Test reparieren; (b) Test prüft gelöschte/umgebaute API → Test auf die heutige Produktiv-API portieren oder ersatzlos streichen (Entscheidung dokumentieren); (c) Test findet einen ECHTEN Produkt-Bug → als Befund melden, Fix nur nach TDD (Test rot sehen, dann fixen).
2. **modul6 grundsätzlich klären, bevor einzeln gefixt wird:** Sollen die Infra-Checks im Container laufen (dann Pfade/Mounts lösen oder Tests mit sauberem Skip-wenn-nicht-vorhanden versehen) oder sind sie Host-Tests? Kein stilles `skip` ohne Begründung im Test-Docstring.
3. **modul7:** Tote `email_import.parser`-API — heutige Entsprechung suchen (Klassifizierer/Dispatcher-Struktur, siehe `backend/email_import/` und Memory `project_unfallakten_email_workflow_redesign`). Tests portieren, nicht die Produktiv-API zurückbauen.
4. Nach jeder Klasse: Suite laufen lassen, Zwischenstand committen (kleine Commits je Fehlerklasse, Muster der Commits `a4cf92ca..38020716`).

## Regeln

- RA-MICRO strikt read-only; keine Schreibzugriffe.
- Kein Produktcode ändern, außer ein Test deckt einen echten Bug auf — dann TDD.
- Keine Tests „grün lügen" (keine breiten try/except, keine assertTrue(True), kein Löschen ohne dokumentierte Begründung in `bugfixes.md` oder CHANGELOG).
- Am Ende: modul5-7 + `test_forderung_modell` komplett grün (oder begründet übersprungen), Frontend-Vollsuite unangetastet grün, Protokoll in `docs/CHANGELOG.md`, Status-Update in `docs/TODO.md` (Eintrag „Forderungsschreiben-Modul — Offen: test_modul6/7").

---

## Zur Einordnung: noch offene Bugs aus dem Forderungsschreiben-Review (NICHT Teil dieser Session)

- **I-10 Haftungsquote** — wartet auf Formulierungsentscheidung RA Schatz (TODO.md).
- Minors opportunistisch (Liste in `bugfixes.md`).
