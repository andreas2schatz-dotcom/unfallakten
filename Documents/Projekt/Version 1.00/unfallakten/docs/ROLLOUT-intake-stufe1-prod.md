# Prod-Rollout Runbook — `intake-stufe1`

Stand: 2026-07-14 · Zielschema **v57** · Branch `intake-stufe1` (**158 Commits vor `main`**)

Dieses Runbook bringt die komplette Pipeline-v7-/Positionsmodell-Arbeit (S1, P1.x,
N-01…N-04, Fragebogen-Feld-Übernahme) auf die Produktion. **Kein Schritt wird
automatisch ausgeführt — der Rollout ist manuell und wird vom Betreiber
durchgeführt.**

## Kontext & Kernrisiko

- **Prod-DB ist derzeit klein** (~150 KB, Kollegen noch nicht ausgerollt) → geringes
  Datenrisiko, gutes Zeitfenster.
- **Kernrisiko = Schema-Migration.** Der Branch bringt Migrationen **49 → 57** plus
  neue Tabellen (`ereignisse`, `ereignis_positionen`, `position_ereignis_cache`,
  `intake_dokumente`, `zustellungen`, `freigaben`, …). Alle müssen sauber aufs
  `prod-data`-Volume.
- **Der DEV-Reloader-Trap** (v54/55/57 wurde in DEV „gestempelt ohne Spalte",
  heute für `llm_degradiert` manuell nachgezogen) **betrifft Prod NICHT** — Prod hat
  keinen Flask-Reloader, es wird all-at-once deployt.
- **ABER neuer Prod-spezifischer Fallstrick:** Prod startet Gunicorn mit **4 Workern**
  (`gunicorn … "backend.app:erstelle_app()"`), und `erstelle_app()` ruft `init_db()`.
  4 Worker → **gleichzeitige Migration** = Race auf `ALTER TABLE`. → **Migration EINMAL
  vorab** als One-Shot laufen lassen, bevor die Worker starten (Schritt 5).

## Vorentscheidung (Betreiber): Merge nach `main` vs. Branch direkt deployen

- **Empfohlen:** `intake-stufe1` → `main` mergen, dann `main` deployen (main = deployter
  Stand, sauberer für Rollback/Nachvollzug). 158 Commits → als PR oder Fast-Forward.
- **Alternativ:** `intake-stufe1` direkt deployen (schneller, aber `main` bleibt hinterher).

## Voraussetzungen-Checkliste (auf dem Prod-Host, VOR dem Deploy)

- [ ] `.env` vollständig & **echt** (nicht die Dev-Defaults!):
  `JWT_SECRET_KEY`, `FLASK_SECRET_KEY` (echte Zufallswerte), `CORS_ORIGIN`=echte Domain
  (z. B. `https://anwalt-offenbach.de`), `DB_PATH=/app/data/unfallakten.db`,
  `EMAIL_*` (Strato: unfall@/termin@/bussgeld@/info@).
- [ ] **Stufe-1-Flags** gesetzt/Default: `INTAKE_REVIEW_PFLICHT=true`,
  `LLM_ENABLED=false`, `GLM_OCR_ENABLED=false` (Badges/GLM feuern dann bewusst nicht).
- [ ] **`EREIGNISMODELL_EINGEFUEHRT_AM`** auf das **echte Cutover-Datum** setzen
  (Default `2026-07-09`) — steuert den N-07-Bestandsakten-Hinweis.
- [ ] **SSL-Zertifikat** unter `nginx/ssl/` = **Let's Encrypt** (nicht das self-signed
  Dev-Zertifikat).
- [ ] EAKTE-Mount verfügbar, falls E-Akte-Import genutzt wird.
- [ ] `./backups` existiert und ist beschreibbar (Backup-Service schreibt dorthin).
- [ ] Frontend-Prod-Build vorbereitet (`make frontend-build` bzw. Build im Compose mit
  hochgezähltem `CACHEBUST`, sonst liefert nginx alte Assets aus).

## Runbook (Schritte)

**0. Wartungsfenster ankündigen.** (Kollegen nutzen Prod noch nicht → kurzes Fenster reicht.)

**1. Code veröffentlichen.**
```bash
# lokal:
git push origin intake-stufe1
# optional (empfohlen): Merge nach main als PR oder:
git checkout main && git merge --ff-only intake-stufe1 && git push origin main
```

**2. Auf dem Prod-Host aktualisieren.**
```bash
cd <prod-repo>
git fetch --all && git checkout <main-oder-intake-stufe1> && git pull
```

**3. Prod-DB-Backup ZUERST (nicht überspringen).**
```bash
make backup   # oder manuell, WAL-sicher:
docker compose -f docker-compose.prod.yml exec backend \
  python -c "import sqlite3,os; s=sqlite3.connect(os.environ['DB_PATH']); \
d=sqlite3.connect(os.environ['DB_PATH']+'.bak_pre_rollout_v57'); \
[s.backup(d)]; s.close(); d.close(); print('backup ok')"
# Backup-Datei zusätzlich VOM Host wegkopieren (off-site).
```

**4. Images bauen (ohne zu starten).**
```bash
docker compose -f docker-compose.prod.yml build
# Frontend-Assets frisch: CACHEBUST hochzählen (z.B. export CACHEBUST=$(date +%s))
```

**5. Migrationen EINMAL vorab (Race der 4 Worker vermeiden).**
```bash
docker compose -f docker-compose.prod.yml run --rm backend \
  python -c "from backend.db.schema_manager import init_db; init_db()"
```
Ausgabe/Logs auf Fehler prüfen. `init_db()` liest `DB_PATH` aus der Env und wendet alle
ausstehenden Migrationen einmal an, dann Exit.

**6. Migration VERIFIZIEREN, bevor die App startet.**
```bash
docker compose -f docker-compose.prod.yml run --rm backend python -c "
import sqlite3,os; c=sqlite3.connect(os.environ['DB_PATH'])
print('schema_version:', c.execute('SELECT MAX(version) FROM schema_version').fetchone()[0])
cols={r[1] for r in c.execute('PRAGMA table_info(intake_dokumente)')}
for x in ('llm_degradiert','ocr_ratio_salat','ocr_quote_woerter'):
    print(' intake_dokumente.'+x+':', 'DA' if x in cols else 'FEHLT')
have={r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")}
for t in ('ereignisse','ereignis_positionen','position_ereignis_cache','intake_dokumente','zustellungen','freigaben'):
    print(' Tabelle '+t+':', 'DA' if t in have else 'FEHLT')
"
```
Erwartung: `schema_version: 57`, alle Spalten/Tabellen **DA**. Wenn eine **FEHLT** →
**nicht starten**, den DEV-Trap-Fix (manuelles `ALTER TABLE`) analog anwenden und
Ursache klären.

**6b. KW-27-Zusatzcheck (PRD-33 S5, 2026-07-18):** Die `beteiligte`-Tabelle darf
`rolle='gericht'` nicht per CHECK ablehnen — sonst schlägt die Gericht-Persistenz des
Klage-Wizards auf dieser DB fehl (sichtbar per Toast, aber ohne Speicherung):
```bash
docker compose -f docker-compose.prod.yml run --rm backend python -c "
import sqlite3,os; c=sqlite3.connect(os.environ['DB_PATH'])
sql=c.execute(\"SELECT sql FROM sqlite_master WHERE name='beteiligte'\").fetchone()[0]
print('gericht im CHECK bzw. kein rolle-CHECK:', ('gericht' in sql) or ('CHECK' not in sql.upper()) or ('rolle' not in sql))
"
```
Erwartung: `True`. Bei `False`: Rebuild-Migration der `beteiligte`-Tabelle nötig
(SQLite kann CHECK nicht per ALTER erweitern) — Entscheidung RA Schatz, siehe
`docs/BUGFIX_KLAGE_WIZARD.md` (KW-27, Bestands-DB-Einordnung).

**7. Stack starten.**
```bash
docker compose -f docker-compose.prod.yml up -d --build   # oder: make deploy
```

**8. Boot + Health abwarten, Logs prüfen.**
```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f backend | grep -iE "error|migr|traceback"
curl -fsS https://<domain>/health   # bzw. intern gegen den Container
```

**9. Prod-Smoke-Test (analog dem DEV-Test von heute).**
- Login als Admin.
- **`GET /intake/queue` → 200** (das war in DEV der 500-Kanary).
- Einen Fragebogen in der Review-Queue öffnen → Vorschau erscheint → freigeben →
  Felder landen in der Akte. **Auf einer klar markierten Wegwerf-Test-Akte, danach
  aufräumen** (siehe DEV-Vorgehen: Test-Akte `ZZ-VERIFY/99`, alle akte_id/akte_az-Zeilen
  + intake-Zeilen wieder löschen).
- Falls kein echter Fragebogen vorliegt: mindestens `ist_fragebogen` + Vorschau-Endpoint
  gegen ein Text-Dokument prüfen.

**10. Für Kollegen freigeben** (Accounts/Onboarding), dann eng beobachten.

## Rollback

- **App:** vorherige Image-Tags bzw. den vorherigen `main`-Stand redeployen
  (`git checkout <alt>` → `up -d --build`).
- **DB:** das Backup aus Schritt 3 zurückspielen:
  ```bash
  docker compose -f docker-compose.prod.yml stop backend
  # DB-Datei ersetzen + WAL/-shm entfernen, dann:
  docker compose -f docker-compose.prod.yml start backend
  ```

## Option B — Fresh-Init (nur wenn die ~150 KB Prod-Daten ENTBEHRLICH sind)

Da Prod praktisch leer ist und die Kollegen noch nicht ausgerollt sind, ist die
migrationsfreie Alternative ein **sauberer Neuaufbau**: `prod-data`-Volume leeren,
`init_db()` baut das Schema **v57 direkt** (kein Migrationskette-Risiko). **Zerstört alle
Prod-Daten** — nur wählen, wenn die aktuelle Prod-DB reine Testdaten enthält. Vorher
trotzdem ein Backup ziehen.

## Nach dem Rollout

- Stündlicher Backup-Service (N-10) läuft in Prod → verifizieren (`./backups` füllt sich,
  `integrity_check=ok`).
- Stufe-1-Flags bleiben off → `llm_degradiert`/OCR-Badges feuern nicht (erwartet, für QA
  bekannt).
- Erst nach stabilem Betrieb die zweite Welle (N-05) und ggf. LLM/GLM-Aktivierung planen.
