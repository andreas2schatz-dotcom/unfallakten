# Prompt für nächste Session — P1.8 (Backfill synthetischer Ereignisse aus Bestand)

Vorher: `/model` → Opus 4.7 (falls nicht schon Standard). `/effort` → high.

Danach den folgenden Block kopieren und als Prompt einfügen:

---

```
Wir setzen ein geplantes, freigegebenes Refactoring um. Branch: intake-stufe1
(bitte prüfen, dass er aktiv ist).

Lies zuerst vollständig: freigabe.md (verbindlich, übersteuert die Pläne,
insbesondere Abschnitt 3 K-M3 Backfill-Ehrlichkeit), POSITIONSMODELL-PLAN.md
(Abschnitte 4 Datenmodell, 5 Type-Action-Matrix, 7 Stufe P1 — Kern P1.8),
PIPELINE-REFACTORING-PLAN.md (Überblick).
Die Planung ist abgeschlossen und freigegeben — kein erneutes Brainstorming,
keine Alternativvorschläge zur Architektur.

Nutze die Skills superpowers:executing-plans,
superpowers:test-driven-development und
superpowers:verification-before-completion. UI-Änderungen laut CLAUDE.md
im Browser prüfen (dev-Server, Golden Path durchklicken).

Implementiere AUSSCHLIESSLICH Schritt P1.8 aus dem POSITIONSMODELL-Plan:

Ein einmaliges Migrations-Skript scripts/backfill_ereignisse.py, das
synthetische Ereignisse aus dem Bestand ableitet. Quellen und Ziele:

  * abrechnungsschreiben + regulierung_positionen (je Zeile) ->
    ereignis abrechnung_eingegangen. Wirkung anhand betrag_reguliert /
    kuerzungsart_id analog services/eingehende_ereignisse.py Alt-Weg
    P1.5a (anerkannt / gekuerzt / abgelehnt); Datum aus
    abrechnungsschreiben.datum (falls NULL: hochgeladen_am der zugehoerigen
    dokumente-Zeile).

  * forderung_positionen (je forderungsschreiben_nr gruppiert) ->
    ereignis forderung_generiert mit wirkung=gefordert je Position.
    Datum aus der zugehoerigen dokumente-Zeile mit
    dokumente.forderungsschreiben_nr = <nr>. Ohne Position-Zeilen
    (Alt-Varianten aussserhalb "hoehe") -> K-M3 Akten-Scope-Ereignis
    ohne Positionsbezug, herkunft='backfill'.

  * dokumente.typ IN ('klage','forderungsschreiben','sachstandsanfrage',
    'stellungnahme','kostennote') und noch KEIN ausgehendes Ereignis
    dieses Typs mit dokument_id vorhanden -> synthetische
    <typ>_generiert-Ereignisse. Datum = dokumente.hochgeladen_am.
    Ohne rekonstruierbare Positionen: Akten-Scope (siehe K-M3).

  * schadenposition_belege -> rechnung_eingegangen mit wirkung=beleg auf
    die zugehoerige Position; dokument_id = schadenposition_belege.dokument_id;
    Datum = zugehoerige dokumente.hochgeladen_am oder Fallback.

Alle Ereignisse tragen herkunft='backfill' im Ereignis-Kopf. Nutzt
services.ereignis_service.schreibe_ereignis (EINZIGER Schreibpunkt) --
kein direktes INSERT in ereignisse / ereignis_positionen /
position_ereignis_cache.

Idempotenz zwingend:
  * Vor jedem Insert Query "existiert bereits ein Ereignis mit
    (akte_az, ereignistyp, dokument_id, herkunft='backfill')?" -> skip.
  * Fuer forderung_positionen zusaetzlich Anker ueber
    (akte_az, forderungsschreiben_nr).
  * Re-Lauf des Skripts erzeugt keine Duplikate; Test dazu.

K-M3 Backfill-Ehrlichkeit (freigabe.md Abschn. 3):

  * Akten-Scope-Backfill-Ereignisse (ohne Positionsbezug) sind sichtbar
    als solche im Ereignis-Kopf (dokument_id kann gesetzt sein, aber
    ereignis_positionen ist leer).
  * PositionsDashboard-Erweiterung: wenn eine Akte mindestens ein
    Backfill-Ereignis mit leerer Positionsverteilung hat -> Kachel oben
    einmalig zeigen: "Eskalationsvorschlaege fuer diese Akte erst ab
    [Einfuehrungsdatum] verlaesslich." Einfuehrungsdatum aus
    positionsstatus_service oder aus dem juengsten
    NICHT-backfill-Ereignis der Akte.
  * AbleitungBadge zeigt weiterhin den Stand -- der K-M3-Hinweis
    ergaenzt, ersetzt nicht.

Vorwissen (bereits umgesetzt, nicht anfassen):

  * S1.1-S1.9 komplett; Feature-Flag INTAKE_REVIEW_PFLICHT True aktiv.
  * P1.1-P1.7 komplett (Registry, Migrationen 51+52, ereignis_service,
    positionsstatus_service, alle Alt-Pfad-Instrumentierungen fuer
    ausgehende + eingehende Ereignisse, APScheduler fristablauf_job,
    UI mit AbleitungBadge / PositionsDashboard / EreignislistePanel /
    DokumentAktionsmenue).
  * Review-Erweiterungen (2026-07-10): Reparse-Button, manuelle Klassen-
    Sicherung, Restwert netto/brutto, Gutachten+SV-Rechnung Option A
    (Freigabe schreibt gutachten_eingegangen mit sv_kosten, Vorsteuer-
    Weiche). Namens-Fallback im akten_matching (Score 0.4).
    AktenLiveSuche.jsx im Review-UI. DetailPanel-Reset via key.
  * Backend-DB im Container ist repariert; Migration 46 hat Orphan-Guard.

Regeln:
  * RA-MICRO strikt read-only. Docker/CIFS nicht anfassen.
  * INTAKE_REVIEW_PFLICHT-Feature-Flag NICHT anpacken.
  * Skript ist idempotent, aber Backfill-Ereignisse loeschen ist
    DESTRUKTIV -- nicht implementieren. Rueckbau nur ueber DB-Neuaufbau.
  * Testgetrieben: erst Backend-Test (Backfill-Konsistenz + Idempotenz),
    dann Implementation. Frontend-K-M3-Hinweis mit Component-Test.
    - Backfill-Test: Bestand mit 5 Alt-Zeilen (abrechnungsschreiben +
      regulierung_positionen + forderungsschreiben + dokumente-typ-eintrag +
      schadenposition_beleg) -> Skript-Lauf erzeugt genau die passenden
      Ereignisse mit korrekten Wirkungen und Datumsangaben.
    - Idempotenz-Test: zweiter Skript-Lauf erzeugt keine Duplikate.
    - K-M3-Test: forderung_positionen leer, dokumente.typ='klage'
      vorhanden -> Akten-Scope-Ereignis, Dashboard-Kachel zeigt
      Backfill-Hinweis.
  * Manuelles Testen laut CLAUDE.md: Skript im Container gegen die
    reparierte Prod-Dev-DB laufen lassen (Backup vorher!). 5 Bestandsakten-
    Stichprobe: Positions-Dashboard zeigt dieselben Summen wie
    v_regulierungsstatus (+/- dokumentierte F-01-Abweichung).

  * Regressionscheck am Ende: aktuelle Baseline auf intake-stufe1
    ~ 217 failed / 682 passed / 0 errors / 18 skipped nach den Review-
    Erweiterungen (Delta gegen 212f/677p aus P1.7 = +5 neue grune Tests
    aus Option A, keine echte Regression). Diffbasiert pruefen. Bekannte
    Alt-Failures (test_modul3/4/7 Auth-Cluster, test_modul1/2/5/6 Schema,
    test_sv_portal, test_prd27, test_s16a_golden_e2e, test_dashboard,
    test_migration_46) zaehlen nicht als Regression.

  * Danach: Commit, docs/TODO.md-Eintrag "Aktueller Schritt" auf
    "P1 komplett, Beginn P2" (bzw. wenn P2-Umfang unklar, auf
    "P1 komplett, naechste Session Rueckstellung Option C PDF-Splitting")
    aktualisieren, dann STOPP -- naechster Schritt erst nach meiner
    Abnahme.

Hinweis: P1.8 ist im POSITIONSMODELL-PLAN als M (medium) markiert.
Typische Aufteilung: (1) Backfill-Skript-Skelett + Idempotenz-Anker,
(2) je Datenquelle einen Sub-Reader mit Test, (3) K-M3-Anzeige im
PositionsDashboard, (4) Manueller Trial-Lauf gegen Prod-Dev-DB mit
Backup, (5) Docs-Update. Mehrere Commits sind normal; jeweils
lauffaehig + Regressionscheck gruen, dann weiter.
```

---

## Für weitere Sessions

Nach P1.8-Abnahme ist Stufe P1 komplett. Nächste Optionen (mit RA Schatz priorisieren):
- **Option C** (zurückgestellt): manuelles PDF-Splitting im Review-UI (Randfälle wie DEKRA-PDFs mit >2 eingebetteten Dokumenten, Gutachten + Prüfbericht in einer Datei).
- **Stufe P2** aus POSITIONSMODELL-PLAN Abschnitt 7 (manuelle Ereignisse, Aktenkonto-Plausibilitätshinweis, Vergleichs-Ereignis + SV-Workflow, Eskalations-Feinschliff).
- **P1.5e**: Review-Freigabe schreibt Ereignisse auch für andere Klassen als Gutachten (heute nur Option A / Gutachten mit SV-Rechnung).
