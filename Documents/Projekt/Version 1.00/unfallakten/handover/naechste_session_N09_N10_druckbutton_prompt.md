# Prompt für die nächste Session — N-09 (WAL/busy_timeout-Härtung) + N-10 (Backup, stündlich) + ReviewQueue-Druckbutton

> Diesen Text in eine frische Session einfügen.

---

Wir machen drei kleine, klar abgegrenzte Aufgaben: zwei Infrastruktur-Härtungen **vor dem Kollegen-Rollout** (N-09, N-10) und ein kleines UI-Feature (Druckbutton). Branch: **`intake-stufe1`** (nicht pushen außer auf Ansage). Die große Bugfix-Reihe (BUG-01–30) ist abgeschlossen; **P1.8 ist zurückgestellt** (Entscheidung RA Schatz — forward-only-Betrieb mit N-07-Hinweis, kein Backfill).

**Pflichtlektüre zuerst:**
- `docs/TODO.md` (Abschnitt „Offene Bugs / Verbesserungen" + „Aktueller Schritt" — dort ist P1.8-Zurückstellung und der N-Nachtrag notiert)
- `docs/DECISIONS.md` (SQLite-Entscheidung: WAL, `timeout=30`, `check_same_thread=False`)
- **Vor DB-/Docker-Arbeit:** Memory `feedback_migration_reloader_trap` — **die aktive DB ist das Docker-Volume (`dev-data`, `/app/data`), NICHT `backend/data/unfallakten.db`** (die ist stale). Für jede Verifikation am laufenden System im Container prüfen.
- Memory `feedback_unfallakten_docker` (`.env`-Änderung → `--force-recreate`, HMR auf Windows kaputt → Restart nötig).

## Ausgangslage (bereits geprüft, Stand 2026-07-13)

- **WAL & busy_timeout sind teilweise schon da:** `backend/db/database.py` → `get_raw_connection()` (Zeilen ~40–49) setzt `sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)` + `PRAGMA journal_mode=WAL`, `foreign_keys=ON`, `synchronous=NORMAL`, `cache_size=-64000`, `temp_store=MEMORY`. **Es fehlt ein expliziter `PRAGMA busy_timeout`** (der `timeout=30`-Connect-Parameter setzt ihn implizit auf 30000 ms, aber nicht selbstdokumentierend/robust).
- **Der Prod-Backup ist AKTUELL KAPUTT:** `docker-compose.prod.yml` (Zeilen ~110–125, Service `backup`, `alpine:3.20`) mountet `./scripts/backup.sh:/backup.sh:ro` und cront `0 2 * * * sh /backup.sh`. **`scripts/backup.sh` existiert nicht mehr** (im Ordner nur `backfill_textpfad.py`; das Skript wurde in Commit `746f731` entfernt, `TestBackupScript` mit). Der Backup-Container läuft also gegen eine nicht existierende Datei → **es gibt derzeit kein funktionierendes Backup.** Außerdem: reines `alpine:3.20` enthält **kein `sqlite3`-Binary** — das muss der Entrypoint/Skript erst installieren.

---

## Aufgabe 1 — N-09: SQLite-WAL/busy_timeout härten & verifizieren

**Datei:** `backend/db/database.py` (`get_raw_connection`).

**Fix-Richtung:**
1. Expliziten `conn.execute("PRAGMA busy_timeout=30000;")` ergänzen (belt-and-suspenders neben dem Connect-`timeout`; selbstdokumentierend, greift auch für evtl. Raw-Consumer).
2. **Verifikation, dass WAL wirklich aktiv ist** — auf der **aktiven Volume-DB** (im Container, nicht `backend/data/`): `PRAGMA journal_mode;` → muss `wal` liefern, `PRAGMA busy_timeout;` → `30000`. journal_mode=WAL ist eine **persistente DB-Eigenschaft** (einmal gesetzt bleibt sie); das Setzen je Verbindung ist harmlos.
3. WAL-Checkpoint-Bloat einordnen: `PRAGMA wal_autocheckpoint` (Default 1000 Seiten) ist i.d.R. ausreichend. Entscheiden, ob ein periodischer `wal_checkpoint(TRUNCATE)` nötig ist (nur falls die `-wal`-Datei im Betrieb unbounded wächst — sonst bewusst NICHT einbauen, keine unnötige Komplexität).

**Stolpersteine:**
- `PRAGMA journal_mode=WAL` **nicht** innerhalb einer offenen Transaktion setzen (SQLite ignoriert es dann).
- Beim Testen: `get_raw_connection` nutzt `DB_PATH` aus der Env. Für den Test eine temporäre DB per `DB_PATH` setzen (Muster wie in `test_intake_routes.py::_setup`), sonst wird die echte Datei angefasst.

**TDD:** Test in `backend/tests/` (z. B. `test_db_pragma.py`): frische DB via `get_raw_connection()` → `conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"` und `conn.execute("PRAGMA busy_timeout").fetchone()[0] == 30000`. Vor dem Fix rot (busy_timeout-Default ist 0 bzw. wird nur implizit gesetzt — Wert prüfen; ggf. testet man gezielt den expliziten PRAGMA-Effekt).

---

## Aufgabe 2 — N-10: Backup reparieren + auf stündlich stellen

**Dateien:** neu `scripts/backup.sh`, Anpassung `docker-compose.prod.yml` (Service `backup`).

**Fix-Richtung:**
1. **`scripts/backup.sh` neu erstellen** — konsistenter SQLite-Backup, **kein `cp`** der Live-DB (WAL-DB + `-wal`/`-shm` → `cp` kann inkonsistent/korrupt sein). Stattdessen die Online-Backup-API bzw. `.backup`:
   ```sh
   sqlite3 /data/unfallakten.db ".backup '/backups/unfallakten_$(date +%Y%m%d_%H%M%S).db'"
   ```
   (bzw. `VACUUM INTO` — aber `.backup` ist online-sicher unter WAL und die robustere Wahl). Uploads zusätzlich als Tar sichern. Retention über `BACKUP_RETENTION_DAYS` (bei stündlich sonst 720+ Dateien — Retention-Strategie festlegen, z. B. stündlich 48 h behalten + täglich 30 Tage, oder simpel per Datei-Anzahl/Alter kappen; das mit RA Schatz-Default „30 Tage" abgleichen).
2. **`alpine:3.20` hat kein `sqlite3`** — im `entrypoint` vor `crond` `apk add --no-cache sqlite` (oder ein Image mit sqlite verwenden). Ohne das schlägt das Skript still fehl (genau der Fehlerklasse, die wir gerade gefunden haben).
3. **Cron von nächtlich auf stündlich:** `docker-compose.prod.yml` Zeile ~120 `0 2 * * *` → `0 * * * *`.
4. Datei muss ausführbar/als `sh` lauffähig sein; `ro`-Mount bleibt.

**Stolpersteine:**
- Der Backup-Service läuft nur im **Prod-Stack** (`docker-compose.prod.yml`), nicht im Dev-Compose. Dev-Verifikation ggf. durch manuellen `sh scripts/backup.sh`-Lauf gegen eine Kopie.
- Backup-Verzeichnis `./backups` (Host-Mount) — Retention-Löschung muss dorthin schreiben dürfen.
- **Regressions-Guard:** genau dieser Bug (Compose referenziert ein fehlendes Skript) sollte nicht wiederkehren — ein leichter Test, der prüft, dass jede in `docker-compose.prod.yml` gemountete `./scripts/*.sh`-Datei existiert, verhindert Rückfall (analog dem alten `TestBackupScript`, aber robuster). Prüfen, ob `backend/tests/test_modul6.py` hier der richtige Ort ist.

**TDD:** Shell-Skripte sind begrenzt unit-testbar. Sinnvoll: (a) Guard-Test „gemountete Skripte existieren"; (b) optionaler Smoke-Test, der `scripts/backup.sh` gegen eine temporäre SQLite-DB laufen lässt (falls `sqlite3`-Binary in der Testumgebung vorhanden) und prüft, dass eine nicht-leere Backup-Datei entsteht.

---

## Aufgabe 3 — ReviewQueue-Druckbutton (Wunsch RA Schatz)

**Datei:** `frontend/src/views/ReviewQueueView.jsx` (`DetailPanel`).

**Kontext:** Die Dokumentvorschau ist entweder ein PDF-`<iframe src={pdfSrc}>` (Zeile ~650) **oder** `TextVorschau text={detail.parse?.text_gesamt}` (Zeile ~647, wenn `detail.payload_typ === "text"`). `pdfSrc` ist `${API_BASE}/intake/dokument/${id}/pdf?token=…` (Zeile ~571). Der Formular-Panel-Header („Dokument #id" + `StatusBadge`) ist bei Zeile ~657–669.

**Fix-Richtung:**
- Einen **„Drucken"-Button** in den Header-Bereich (~Zeile 658, neben `StatusBadge`) oder in die Klasse/Reparse-Button-Zeile (~704) setzen.
- Verhalten:
  - **PDF:** am robustesten `window.open(pdfSrc, "_blank")` → der native PDF-Viewer des Browsers druckt zuverlässig. (`iframe.contentWindow.print()` ist fragil und je nach Browser/Token-URL unzuverlässig — nur als Option, wenn same-origin sauber trägt.)
  - **Text:** die `TextVorschau` in ein Druck-Fenster geben (z. B. `window.print()` auf einer dedizierten Druckansicht bzw. `window.open` mit dem Text).
- `disabled` nur, wenn sinnvoll (z. B. während `aktion`); der Button darf `pollAktiv` **nicht** blockieren.

**Stolpersteine:**
- `key={aktivId}`-Re-Mount + die BUG-30-Poll-Logik (`polleWorkerBisFertig`, `mountedRef`) **nicht** kaputt machen.
- Token steht in der URL (`pdfSrc`) — beim `window.open` bleibt die Auth erhalten; keine zusätzliche Header-Logik nötig.

**TDD (Vitest):** Reine Logik extrahieren und testen, z. B. `export function druckZiel(detail, pdfSrc)` → liefert `{ typ: "pdf", url }` bzw. `{ typ: "text", text }`. Das eigentliche `window.open`/`print` ist Browser-seitig und nicht sinnvoll unit-testbar. Baseline **48 Frontend-Tests** halten.

---

## Arbeitsregeln (verbindlich)

- **TDD:** erst fehlschlagender Test, ihn fehlschlagen sehen, dann minimaler Fix. Muster Backend: `test_bugfix_p4_intake_v7.py`. Muster Frontend (reine Funktion): `ReviewQueueView.poll.test.jsx`.
- **RA-MICRO bleibt read-only** — nur SQLite schreiben (betrifft hier v. a. das Backup: nur lesen/sichern, nie in die RA-MICRO-DB).
- **Baseline diffbasiert grün halten:** vorbestehende Failures in Alt-Clustern (`test_modul2/3/4/7` — u. a. `ModuleNotFoundError: backend.email_import.parser`, Login-Fixture-`KeyError`) NICHT anfassen. Maßgeblich: **null neue Failures in Pipeline-v7-/geänderten Dateien.** Verdächtige Failures per `git stash` gegenprüfen.
- **Docker/DB:** aktive DB = Volume `dev-data` (`/app/data`), nicht `backend/data/`. `docker-compose.prod.yml`-Änderungen betreffen nur den Prod-Stack (Deploy „all at once"). `.env`-Änderungen → `--force-recreate`.

## Testausführung

- Python 3.14, pytest, System-Python (kein venv). cwd = Repo-Root.
- Env-Var nötig: `export JWT_SECRET_KEY=test-secret-key-minimum-32-chars!!`
- Gezielter Lauf (Beispiel): `python -m pytest backend/tests/ -k "db or pragma or backup or modul6" --tb=short -q`
- Voller Gegencheck wie gehabt mit dem breiten `-k`-Filter der v7-Suite; Alt-Cluster-Failures ignorieren.
- Frontend: `cd frontend && npm test` (bzw. `npx vitest run`).

## Abschluss der Session

- Commits auf `intake-stufe1` (nicht pushen außer auf Ansage), Stil: `fix(infra): …` / `feat(review): …` bzw. `feat(infra): …`.
- `docs/TODO.md` fortschreiben (N-09/N-10 erledigt; Druckbutton erledigt → aus „Offene Feature-Folge-Tasks" streichen). Ggf. `docs/ARCHITECTURE.md` (Backup-Service: stündlich statt nächtlich).
- Memory aktualisieren (`project_unfallakten_pipeline_v7.md` + `MEMORY.md`-Zeile): N-09/N-10/Druckbutton erledigt, **kaputter Prod-Backup war die eigentliche Überraschung** (als Fund festhalten). Ggf. neue Feedback-Memory zur Backup-Konsistenz (`.backup` statt `cp`, alpine braucht `sqlite`).

## Danach (offen, nicht zurückgestellt)

- **N-01–N-06** (OCR-/Extraktions-Retrofits S1.6a/b) als eigene „Pipeline-Qualität"-Session.
- **Feature-Folge-Task:** Fragebogen-Feld-Übernahme bei Freigabe (aus BUG-01).
- P1.8 bleibt **zurückgestellt** (nur auf ausdrücklichen Wunsch reaktivieren; dann zuerst Dry-Run-Report, nie „alles auf einmal").
