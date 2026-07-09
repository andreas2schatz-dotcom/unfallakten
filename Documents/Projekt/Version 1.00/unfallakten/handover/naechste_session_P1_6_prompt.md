# Prompt für nächste Session — P1.6 (System-Ereignisse via Scheduler)

Vorher: `/model` → Opus 4.7 (falls nicht schon Standard). `/effort` → high.

Danach den folgenden Block kopieren und als Prompt einfügen:

---

```
Wir setzen ein geplantes, freigegebenes Refactoring um. Branch: intake-stufe1
(bitte prüfen, dass er aktiv ist).

Lies zuerst vollständig: freigabe.md (verbindlich, übersteuert die Pläne),
POSITIONSMODELL-PLAN.md (Abschnitt P1.6 sowie 1.4 zu Fristen), 
PIPELINE-REFACTORING-PLAN.md (Überblick). Die Planung ist abgeschlossen 
und freigegeben — kein erneutes Brainstorming, keine Alternativvorschläge 
zur Architektur.

Nutze die Skills superpowers:executing-plans,
superpowers:test-driven-development und
superpowers:verification-before-completion.

Implementiere AUSSCHLIESSLICH Schritt P1.6 aus dem POSITIONSMODELL-Plan
(System-Ereignisse):

  * Täglicher APScheduler-Job liest fällige todos:
      SELECT * FROM todos
      WHERE quelle='system'
        AND erledigt = 0
        AND faellig_am <= date('now')
        AND regel_key NOT IN (SELECT regel_key FROM ...)  -- idempotent

    Für jede fällige todo -> Ereignis fristablauf (richtung=intern,
    quelle=system, dokument_id=NULL bei Verjährung/PflVG, aber
    dokument_id=<row>.dok_id bei antwort_2w_{dok_id} Fristen).

  * Idempotenz: jede todo-id darf nur EIN fristablauf-Ereignis
    erzeugen. Empfohlener Weg: neue Spalte `todos.fristablauf_ereignis_id`
    (Migration 52) oder Guard über notiz-Feld/regel_key.

  * Positionen des Fristablauf-Ereignisses:
      - Bei antwort_2w_{dok_id}: Positionen aus dem auslösenden Ereignis
        (der antwort_2w-Frist gehört zu einem stellungnahme_generiert-
        oder forderung_generiert-Ereignis; dessen Positionen werden
        ins fristablauf-Ereignis kopiert).
      - Bei Akten-Scope-Fristen (Verjährung, PflVG): Akten-Scope-Ereignis
        ohne Positionen.

  * Scheduler-Setup in app.py (analog polling_service Muster):
      APScheduler-Job wird beim App-Start registriert; einmal pro Tag
      (nachts, konfigurierbar). Ein manueller Trigger-Endpoint
      GET /system/fristablauf/manual (nur Admin) fuer Tests.

Vorwissen (bereits umgesetzt, nicht anfassen):

  * S1.1-S1.9 komplett.
  * P1.1: Registry ereignistypen.yaml enthält `fristablauf`
    (richtung=intern, zulaessige_quellen=[system]).
  * P1.2: Migration 51 + ereignis_service.schreibe_ereignis.
  * P1.3: positionsstatus_service liest aus position_ereignis_cache.
    Der fristablauf-Fall ist in _empfohlene_stufe bereits vorgesehen.
  * P1.4: ausgehende Ereignisse (word_service, klage_routes, sta_routes,
    stellungnahme_routes, gebuehren_word).
  * P1.5: eingehende Ereignisse (ReguWizard, Beleg, Gutachten, WDM).
    Neuer Helper backend/services/eingehende_ereignisse.py mit vier
    Sub-Helpern (erzeuge_aus_regulierung / _beleg / _gutachten / _wdm).
    K-M2a positionsscharfe Ersetzung im schreibe_ereignis-Service
    implementiert.

Regeln:
  * RA-MICRO strikt read-only. Docker/CIFS nicht anfassen.
  * INTAKE_REVIEW_PFLICHT-Feature-Flag NICHT anpacken.
  * Alt-Tabelle todos (fristen_service) wird NICHT ersetzt -- der
    Job liest nur und schreibt Ereignisse zusaetzlich.
  * Testgetrieben: erst Tests schreiben, RED, dann GREEN.
    - Ein Test pro Fristart (antwort_2w mit dok_id -> Positionen aus
      Alt-Ereignis; verjährung -> Akten-Scope).
    - Idempotenz-Test: Job zweimal laufen lassen -> nur 1 Ereignis.
    - Testkriterium: abgelaufene Frist erzeugt genau 1 Ereignis;
      Eskalationsableitung rueckt vor.

  * Regressionscheck am Ende: aktuelle Baseline auf intake-stufe1
    = 206 failed / 657 passed / 0 errors / 18 skipped. Diffbasiert
    pruefen (Vergleich Failure-Set vor/nach P1.6). Bekannte Alt-
    Failures (test_modul3/4/7 Auth-Cluster, test_modul1/2/5/6 Schema,
    test_sv_portal, test_prd27, test_s16a_golden_e2e, test_dashboard,
    test_migration_46) zaehlen nicht als Regression.

  * Danach: Commit, docs/TODO.md-Eintrag "Aktueller Schritt" auf P1.7
    aktualisieren, dann STOPP -- naechster Schritt (P1.7) erst nach
    meiner Abnahme.

Hinweis: P1.6 ist im POSITIONSMODELL-PLAN als S (small) markiert.
Ein einzelner Commit ist der Regelfall.
```

---

## Für weitere Sessions

Denselben Prompt kannst du für P1.7 ff. wiederverwenden — anzupassen sind:
- **Schrittnummer** (P1.7 / P1.8)
- **K-Punkt-Zusatz** aus freigabe.md Abschnitt 4
  (bei P1.7: UI-Arbeit Positions-Dashboard + AbleitungBadge +
   Dokument-Scope-Aktionsmenü; herkunft='wdm' -> has_unbestaetigt-Flag)
- **Baseline-Zahlen** (aus dem letzten Session-Commit oder dem TODO-Block)
- **Vorwissen** aktualisieren (den bereits erledigten Schritt ergänzen)
