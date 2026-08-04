# Handover-Prompt: Intake-Review-Sichtbarkeit (Feature umsetzen)

> Diesen Block in eine frische Session kopieren.

---

Wir setzen ein bereits **fertig durchdachtes und freigegebenes** Feature um. Bitte an die Superpowers-Workflows halten.

## Wo wir stehen

**Branch:** `intake-review-sichtbarkeit` (bereits ausgecheckt, Dev-Container bindet das Arbeitsverzeichnis). Er stapelt auf der SSOT-Arbeit; `main`-Basis = `40c9143e`. Aktueller HEAD `4c711265`. Relevante Commits (neu → alt):
- `4c711265` docs: **Design-Spec dieses Features** (freigegeben, wartet auf Umsetzung)
- `9d1326c9` docs: SSOT-Spec §6-Korrektur
- `4b0a99bc` **fix(dev): Intake-Worker tickt wieder** (`SCHEDULER_LEASE_DISABLED=1`, live verifiziert)
- `5452bc6c`…`3fee4cfc` + `ac6a7022`/`32859a40`/`35b94648`: die SSOT-Arbeit (Dokumentenklassen, 22 Klassen) — **fertig, reviewt, NICHT gemergt**.

## Aufgabe dieser Session

Feature aus der Spec umsetzen: **`docs/superpowers/specs/2026-08-04-intake-review-sichtbarkeit-design.md`** (bitte zuerst vollständig lesen — sie ist die Quelle der Wahrheit). Kurz: In der Dokumentenkachel einer Akte die noch-nicht-freigegebenen Intake-Dokumente zeigen (Badges „Wird verarbeitet" / „Review ausstehend" / „Fehler – prüfen") + Link, der die ReviewQueue auf genau dieses Dokument öffnet. Neuer Endpoint `GET /akten/<az>/intake-pending`; Frontend-Bereich in `DokumenteSection.jsx`; Navigation nach dem bestehenden `initial…`-Muster (`pendingReviewIntakeId`).

**Vorgehen:** Die Spec ist vom Nutzer freigegeben. Starte mit **`superpowers:writing-plans`** (Plan nach `docs/superpowers/plans/2026-08-04-intake-review-sichtbarkeit.md`), dann **`superpowers:subagent-driven-development`** (Implementer + Task-Review je Task, Whole-Branch-Review am Ende). Ledger: `.superpowers/sdd/progress.md` (enthält noch das SSOT-Protokoll — neu für dieses Feature anlegen, START_HEAD=`4c711265`).

## Wichtige Fakten aus der Vorarbeit (spart Nachforschung)

- **Datenmodell:** `intake_dokumente` hat KEINE Akte-Spalte. Akte-Zuordnung: E-Akte → `zustellungen.signale_json.$.az`; manueller Upload → `zustellungen.roh_referenz='upload/akte:<akte_id>'` (+ `ziel_akte`); E-Mail → nur `intake_dokumente.parse_json.$.akten_kandidaten` (unscharf, in Spec §4 bewusst akzeptiert). Freigabe erst schreibt `dokumente`/`freigaben`.
- `queue_status`-Werte: `neu` → `laeuft` → `bereit_zur_review` → `freigegeben`; Fehlerzweig `pipeline_fehler`; verworfene über `verworfen_am`. Endpoint-Filter: `queue_status != 'freigegeben' AND verworfen_am IS NULL`.
- ReviewQueue-Query: `backend/routers/intake_routes.py:135` (`hole_queue`), Detail-Endpoint `GET /intake/dokument/<intake_id>` (Z. 231). Upload-Gate: `backend/routers/dokumente_routes.py:141-174`. AZ-Normalisierung `_az_basis` (intake_routes.py:68 / akten_matching).
- Frontend: Dokumentenkachel = `frontend/src/sections/DokumenteSection.jsx` (liest `GET /akten/<az>/dokumente`, nur freigegebene). Nav in `frontend/src/App.jsx` (`active`-State; `navItems` hat `review-queue`; Muster `pendingEinstellungenTab`/`initialEmailId`). Farben über `theme.js`-Tokens, keine Roh-Hex.

## Umgebungs-Gotchas (WICHTIG)

- **Backend-Tests im Container:** `docker exec unfallakten-backend-dev python -m pytest <pfad> -v`. **Im Vordergrund** ausführen (kein Background/Monitor — ein Implementer hing sonst am Hintergrund-Testlauf).
- **`sqlite3`-CLI fehlt im Container** → DB per Python abfragen: `docker exec unfallakten-backend-dev python -c "import sqlite3; c=sqlite3.connect('/app/data/unfallakten.db'); ..."`.
- **Frontend nicht im Backend-Container** gemountet (nur `backend/`+`tools/`). FE-Build/-Tests auf dem **Host**: `cd frontend && npm run build` bzw. Vitest.
- **Git-Wurzel = Home** (`C:\Users\HAL9000`) → **NIE `git add -A`**, nur konkrete Pfade.
- Vollsuite hat ~232 **vorbestehende** Failures (Auth-Bootstrap-Kollision im Gesamtlauf, `docs/STATE.md §0`) — nicht durch neue Arbeit; feature-fokussierte Suiten sind maßgeblich.

## Offene Gates (nach der Umsetzung)

1. **Browser-Nachtest dieses Features:** Import in Testakte → Zeile „Review ausstehend" in der Kachel → Link öffnet Dokument in der ReviewQueue.
2. **SSOT-Browser-Abnahme** (separat, RA Schatz): Dropdown 22 Klassen + Reparaturrechnung zuordnen. Details: Memory `project_unfallakten_dokumentenklassen_ssot`.
3. **Merge-Strategie klären:** Dieser Branch enthält SSOT + Scheduler-Fix + dieses Feature. Nach den Abnahmen gemeinsam nach `main` (FF) mergen — oder vorher entscheiden, ob SSOT separat gemergt werden soll.
4. **Scheduler-Fix prod:** `SCHEDULER_LEASE_DISABLED` NICHT in Prod setzen (Gunicorn braucht den Lease). Optional dauerhaft härten: Scheduler im Reloader-Elternprozess per Code-Guard (`WERKZEUG_RUN_MAIN`) nicht starten — als Folge-Idee notiert, nicht zwingend.
