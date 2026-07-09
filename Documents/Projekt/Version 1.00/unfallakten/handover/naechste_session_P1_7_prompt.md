# Prompt für nächste Session — P1.7 (UI: Positions-Dashboard + AbleitungBadge + Dokument-Scope-Aktionsmenü)

Vorher: `/model` → Opus 4.7 (falls nicht schon Standard). `/effort` → high.

Danach den folgenden Block kopieren und als Prompt einfügen:

---

```
Wir setzen ein geplantes, freigegebenes Refactoring um. Branch: intake-stufe1
(bitte prüfen, dass er aktiv ist).

Lies zuerst vollständig: freigabe.md (verbindlich, übersteuert die Pläne),
POSITIONSMODELL-PLAN.md (Abschnitte P1.7 sowie 4.3, 4.6, 5, 6 zu UI),
PIPELINE-REFACTORING-PLAN.md (Überblick, insb. S1.8 Review-UI als Muster).
Die Planung ist abgeschlossen und freigegeben — kein erneutes Brainstorming,
keine Alternativvorschläge zur Architektur.

Nutze die Skills superpowers:executing-plans,
superpowers:test-driven-development und
superpowers:verification-before-completion. UI-Änderungen laut CLAUDE.md
im Browser prüfen (dev-Server, Golden Path durchklicken).

Implementiere AUSSCHLIESSLICH Schritt P1.7 aus dem POSITIONSMODELL-Plan
(UI):

  * Neuer Block in frontend/src/components/sections/UebersichtSection.jsx
    unter dem Phasen-Strip (PRD-18): Positions-Dashboard je Akte.
    Datenquelle ausschliesslich GET /akten/<az>/positionen/status
    (P1.3-Endpoint). KEIN drittes calcBrutto im Frontend.
    Toggle aggregiert/getrennt (aggregation-Gruppe aus
    positionsarten.yaml). Zeile pro Position (getrennt):
    Zustand + gefordert/anerkannt/offen + Eskalationsvorschlag +
    Checkliste (X/Y erfüllt).

  * Neue Komponente frontend/src/components/AbleitungBadge.jsx:
    rendert jede abgeleitete Aussage NUR zusammen mit
    „nach Aktenlage, letztes Ereignis vom {stand}". Fehlt `stand`
    → Fehleranzeige (technische Erzwingung der Ehrlichkeitsregel,
    Durchgang 3d des POSITIONSMODELL-PLAN). Wird von jeder Anzeige
    abgeleiteter Zustände benutzt.

  * Dokument-Scope-Aktionsmenue in
    frontend/src/components/sections/DokumenteSection.jsx: je Zeile ein
    Aktionsmenue aus GET /akten/<az>/aktionen?dokument_id=… (P1.3-
    Endpoint, Matrix-Auswertung im Backend). Ersetzt perspektivisch
    handleInlineAnnehmen (Z.513–540); Alt-Weg zunaechst parallel
    lassen.

  * Ereignisliste je Position (Ebene-2): Klick auf Positionszeile
    oeffnet Modal/Panel mit Datum/Typ/Richtung/Dokument-Link/
    Status aktuell|ersetzt aus position_ereignis_cache. Neuer
    Endpoint GET /akten/<az>/positionen/<position_key>/ereignisse
    (falls noch nicht vorhanden — pruefen).

  * K-Punkt-Zusatz aus freigabe.md Abschn. 4: `herkunft='wdm'` in
    ereignisse -> im Dashboard eine `has_unbestaetigt`-Flag je Position
    ableiten (falls das Backend das noch nicht liefert, im
    positionsstatus_service ergaenzen). Kennzeichnet WDM-Vorschlaege
    als unbestaetigt (PF-08).

Vorwissen (bereits umgesetzt, nicht anfassen):

  * S1.1-S1.9 komplett.
  * P1.1: Registry positionsarten.yaml / ereignistypen.yaml /
    aktionen.yaml + Loader.
  * P1.2: Migration 51 + ereignis_service.schreibe_ereignis (einziger
    Schreibpunkt) + rebuild_cache + AST-Guard.
  * P1.3: positionsstatus_service.leite_positionsstatus_ab liest
    position_ereignis_cache.status='aktuell'; Blueprint positionen_bp
    mit GET /akten/<az>/positionen/status und /aktionen.
  * P1.4: ausgehende Ereignisse (word_service, klage_routes,
    sta_routes, stellungnahme_routes, gebuehren_word).
  * P1.5: eingehende Ereignisse (ReguWizard, Beleg, Gutachten, WDM);
    K-M2a positionsscharfe Ersetzung im schreibe_ereignis.
  * P1.6: APScheduler cron 03:15 (fristablauf_job) + manueller
    Endpoint GET /system/fristablauf/manual + Migration 52
    (todos.fristablauf_ereignis_id).

Regeln:
  * RA-MICRO strikt read-only. Docker/CIFS nicht anfassen.
  * INTAKE_REVIEW_PFLICHT-Feature-Flag NICHT anpacken.
  * KEIN calcBrutto-Zwilling im Frontend — Ableitung ausschliesslich
    im Backend, das Frontend rendert nur.
  * AbleitungBadge ist Pflicht fuer jede abgeleitete Aussage; ohne
    stand kein Rendering (nur Fehler).
  * Alt-Wege (handleInlineAnnehmen, direkte Betragsanzeigen) bleiben
    parallel — kein Big-Bang.
  * Testgetrieben: erst Frontend-Komponenten-Tests (vitest/jest) und
    Backend-Endpoint-Tests, RED, dann GREEN.
    - AbleitungBadge: fehlender stand -> Fehler; vorhandener stand ->
      korrekte Wortlaut-Zeile.
    - Positions-Dashboard: rendert Zeilen aus API-Antwort; Toggle
      wechselt aggregation.
    - Aktionsmenue: rendert Aktionen aus /aktionen-Endpoint.
    - has_unbestaetigt-Flag: Ereignis mit herkunft='wdm' erzeugt
      Position mit Flag=true; ohne solche Ereignisse Flag=false.
  * Manuelles Testen laut CLAUDE.md: dev-Server starten, Golden Path
    Abrechnung -> Stellungnahme -> Fristablauf im Browser durchklicken;
    Wissensgrenze ueberall sichtbar; auf Regressionen achten.

  * Regressionscheck am Ende: aktuelle Baseline auf intake-stufe1
    = 209 failed / 670 passed / 0 errors / 18 skipped (Commit d415fac).
    Diffbasiert pruefen. Bekannte Alt-Failures (test_modul3/4/7 Auth-
    Cluster, test_modul1/2/5/6 Schema, test_sv_portal, test_prd27,
    test_s16a_golden_e2e, test_dashboard, test_migration_46) zaehlen
    nicht als Regression.

  * Danach: Commit, docs/TODO.md-Eintrag "Aktueller Schritt" auf P1.8
    aktualisieren, dann STOPP -- naechster Schritt (P1.8) erst nach
    meiner Abnahme.

Hinweis: P1.7 ist im POSITIONSMODELL-PLAN als L (large) markiert.
Mehrere Commits sind normal (z. B. AbleitungBadge zuerst, dann
Positions-Dashboard, dann Aktionsmenue, dann Ereignisliste). Jeweils
lauffaehig + Regressionscheck grün, dann weiter.
```

---

## Für weitere Sessions

Denselben Prompt kannst du für P1.8 wiederverwenden — anzupassen sind:
- **Schrittnummer** (P1.8)
- **Ziel** (P1.8: Backfill synthetischer Ereignisse aus Bestand —
  siehe POSITIONSMODELL-PLAN Abschnitt 7 „Stufe P1 — Kern")
- **K-Punkt-Zusatz** aus freigabe.md Abschnitt 4
  (K-M3 Backfill-Ehrlichkeit + Dashboard-Hinweis „Eskalationsvorschläge
   erst ab [Einführungsdatum] verlässlich")
- **Baseline-Zahlen** (aus dem letzten Session-Commit oder dem TODO-Block)
- **Vorwissen** aktualisieren (P1.7 als erledigt ergänzen)
