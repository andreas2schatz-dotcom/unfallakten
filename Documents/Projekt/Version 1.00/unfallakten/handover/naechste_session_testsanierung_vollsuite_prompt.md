# Nächste Session: Testsanierung Backend-Vollsuite — 123 vorbestehende Failures

## Prompt-Vorschlag

> Die Backend-Vollsuite hat 123 vorbestehende Failures (Stand 2026-08-11, Branch
> `abschlussbericht`, per Stash-Gegenprobe unabhängig von den STA-Fixes verifiziert).
> Bitte analog zur modul6/7-Sanierung (CHANGELOG 2026-08-11) sanieren: erst
> kategorisieren (Verrottung vs. echter Befund vs. Isolationsproblem), dann fixen.
> Lauf: `docker exec unfallakten-backend-dev python -m pytest backend/tests -q`.

## Bekannte Befunde aus der Stichprobe

- **`test_s19_intake_write_guard`:** Whitelist-Zeilennummern für
  `registriere_dokument()`-Aufrufer in `email_import/import_service.py` stimmen nicht
  mehr (gefunden: 324, 784, 814, 1182) — vermutlich Zeilen-Drift durch die
  E-Mail-Hotfixes `34342daa`/`8e9b50ea`. Prüfen, ob es wirklich nur Drift ist
  (keine NEUEN Schreibpfade!), dann Whitelist nachziehen. Grundsatzfrage: Guard auf
  zeilenunabhängige Zählung umstellen?
- **`test_modul4` (TestDokumenteRouten, ~8 Failures):** Upload-Routen-Tests.
- **`test_sv_portal` (4 Failures):** u. a. `test_sv_portal_liste_leer` mit 40x-Status.
- **`test_prd27`:** `test_vorschau_ohne_akte_gibt_404`.
- Rest (~110) nicht einzeln kategorisiert — Failure-Liste des Basislaufs liegt ggf.
  noch im Container unter `/tmp/baseline_run.txt`, sonst neu erzeugen.
- Achtung Isolations-Historie: `feedback_pytest_sys_modules_stubs` (Modul-Stubs
  kontaminieren Reihenfolge) und `_RAMICRO_VERFUEGBAR=False`-Pflicht für
  Import-Lauf-Tests (CHANGELOG 2026-08-11 modul6/7). Einige Failures treten evtl.
  nur im Gesamtlauf auf (Datei einzeln grün) — zuerst prüfen.

## Regeln

- Wie bei der modul6/7-Sanierung: möglichst **kein Produktcode ändern**; wo doch
  nötig (echter Bug), separat ausweisen. Vorher/Nachher-Bilanz ins CHANGELOG.
