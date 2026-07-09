# Prompt für nächste Session — P1.5 (Eingehende Ereignisse, K-M2a)

Vorher: `/model` → Opus 4.7 (falls nicht schon Standard). `/effort` → high.

Danach den folgenden Block kopieren und als Prompt einfügen:

---

```
Wir setzen ein geplantes, freigegebenes Refactoring um. Branch: intake-stufe1
(bitte prüfen, dass er aktiv ist).

Lies zuerst vollständig: freigabe.md (verbindlich, übersteuert die Pläne),
POSITIONSMODELL-PLAN.md (Abschnitt P1.5 sowie 4.2 zu K-M2 und 2.2c zum
Ergänzungsgutachten), PIPELINE-REFACTORING-PLAN.md (Überblick). Die
Planung ist abgeschlossen und freigegeben — kein erneutes Brainstorming,
keine Alternativvorschläge zur Architektur.

Nutze die Skills superpowers:executing-plans,
superpowers:test-driven-development und
superpowers:verification-before-completion.

Implementiere AUSSCHLIESSLICH Schritt P1.5 aus dem POSITIONSMODELL-Plan
(eingehende Ereignisse) inkl. der Freigabe-Korrektur K-M2a:

  * Bestätigungswege erzeugen Ereignisse -- Alt-Tabellen laufen
    PARALLEL weiter (kein Big-Bang):

    - ReguWizard-Speichern (Backend-Route in abrechnungsschreiben_routes.py
      / models/abrechnungsschreiben.py) -> ereignis
      `abrechnung_eingegangen` mit quelle='dokument', dokument_id des
      Abrechnungsschreiben-Dokuments, positionen aus den erfassten
      Regulierungspositionen (wirkung anerkannt / gekuerzt / abgelehnt,
      kuerzungsart_id bei Kürzung/Ablehnung).

    - Beleg-Zuordnung (belege_routes.py handleInlineAnnehmen /
      InAkte-Rechnungsflow) -> ereignis `rechnung_eingegangen` mit
      quelle='dokument', dokument_id der Rechnung, positionen: mapping
      Klasse->position_key aus positionsarten.yaml/ereignistypen.yaml
      (die zwei hartkodierten Kopien in belege_routes.py Z. 136 +
      constants.js Z. 514 wandern in die Registry -- eine Quelle).

    - Gutachten-Übernahme (dokumente_routes.py KI-Dialog / handleParseErgebnis)
      -> ereignis `gutachten_eingegangen` mit quelle='dokument', dokument_id
      des Gutachtens, positionen: Reparaturkosten / Wiederbeschaffung /
      Restwert / Wertminderung / SV-Kosten (wirkung=gefordert).

    - WDM (wdm_regulierung_service.py) -> unbestätigter Vorschlag
      (PF-08). Für P1.5 heißt das: das Ereignis wird angelegt, aber die
      Registry-Vorbelegung markiert es als
      `benutzer_bestaetigung_erforderlich` (Herkunft='wdm'). Persistenz-
      seitig gleich wie ein normales Ereignis; die Ableitung markiert es
      als "unbestätigt" (kein Sonderfeld -- erledigt sich via
      herkunft='wdm' im Cache).

  * K-M2a: Positionsscharfe Ersetzung durch Ergänzungsgutachten. Der
    ereignis_service.schreibe_ereignis() muss neben `ersetzt_kopf_id`
    auch `ersetzt_positions_ids` akzeptieren -- eine Liste von IDs aus
    ereignis_positionen des Alt-Ereignisses, die von der neuen n:m-Zeile
    positionsscharf abgelöst werden. Impl:
      - schreibe_ereignis setzt für JEDE neue Positions-Zeile das Feld
        ereignis_positionen.ersetzt_durch auf die alte Positions-ID
        (nicht umgekehrt -- Konvention: alt.ersetzt_durch = neue_id).
      - Cache-Zeilen der alten Positions-IDs bekommen status='ersetzt'.
      - Kopf-Level bleibt aktuell (Kopf ist nicht ersetzt).
    Test: Ergänzungsgutachten ersetzt nur die reparaturkosten-Zeile, aber
    NICHT die wertminderung-Zeile des Erstgutachtens. Ableitung: nur die
    neue reparaturkosten + alte wertminderung fließen ein.

  * Alt-Tabellen parallel:
      abrechnungsschreiben.py schreibt regulierung_positionen wie bisher.
      belege_routes.py schreibt schadenposition_belege wie bisher.
      dokumente_routes.py KI-Dialog schreibt schadenpositionen wie bisher.
      wdm_regulierung_service.py schreibt wdm_-Alt-Tabellen wie bisher.
    Die Ereignis-Erzeugung ist BEST-EFFORT (analog P1.4 -- Alt-Pfad darf
    durch Ereignis-Problem nie brechen).

Sitzungsentscheidungen (verbindlich):

  1. Ereignisse werden aus den BESTÄTIGUNGSWEGEN geschrieben, NICHT
     aus der Review-Freigabe (S1.8). Die Review-Freigabe erzeugt die
     dokumente-Zeile via output_adapter; erst nachdem der Sachbearbeiter
     die einzelnen Wizards/Dialoge durchläuft, entstehen die Ereignisse.
     Grund: die Bestätigungswege haben die vollen Kontext-Daten
     (Positionen mit Beträgen/Kürzungsarten/Kürzungsgrund), die
     Freigabe nur die Klasse.

  2. Positions-Klasse-Mapping (Rechnung -> position_key) wandert in die
     Registry: neue Datei backend/registry/rechnungstyp_mapping.yaml
     (oder als Feld in positionsarten.yaml). Die zwei Alt-Kopien
     (belege_routes.py Z. 136 + constants.js Z. 514) importieren dieses
     Mapping. In P1.5 nur BACKEND-Umstellung; die Frontend-Kopie
     (constants.js) bleibt bis P1.7 unangetastet.

  3. WDM-Vorschläge werden mit herkunft='wdm' geschrieben. Die Ableitung
     zählt sie normal, kennzeichnet aber das Ergebnis-Feld
     `has_unbestaetigt` je Position (aus dem Cache-Attribut). UI-seitig
     ist das Stufe 2 (P1.7).

  4. Doppelerfassung: der Ereignis-Schreiber (in jedem der 4
     Bestätigungswege) prüft zuerst, ob für die kombination
     (akte_az, dokument_id, ereignistyp) bereits ein Ereignis
     existiert. Wenn ja -> KEIN neues Ereignis, INFO-Log. Testkriterium
     verlangt das explizit.

  5. K-M2a Payload-Struktur: Der Aufruf lautet
        schreibe_ereignis(..., ersetzt_positions_ids=[id_alt1, id_alt2, ...])
     Der Service resolved die IDs zu ereignis_positionen-Zeilen und
     setzt die neuen positionsscharf. Wenn `ersetzt_positions_ids` und
     `ersetzt_kopf_id` beide gesetzt sind: TypeError (widersprüchlich).

Vorwissen (bereits umgesetzt, nicht anfassen):

  * S1.1-S1.9 komplett -- die Review-Freigabe (S1.8 POST /intake/dokument/
    <id>/freigabe) legt die dokumente-Zeile via
    backend/ramicro/output_adapter.schreibe_dokument an. Sie erzeugt
    KEIN Ereignis -- das passiert erst in den Bestätigungswegen.
  * P1.1: backend/registry/{positionsarten,ereignistypen,aktionen}.yaml
    mit Fail-Loud-Loader backend/services/positionsmodell_registry.py.
  * P1.2: Migration 51 (ereignisse + ereignis_positionen mit K-M1
    UNIQUE + position_ereignis_cache). Service
    backend/services/ereignis_service.py mit schreibe_ereignis() +
    rebuild_cache() als einzigem Schreibpunkt. Guard-Test.
  * P1.3: backend/services/positionsstatus_service.leite_positionsstatus_ab
    liest nur status='aktuell'. Blueprint positionen_bp mit
    /akten/<az>/positionen/status und /akten/<az>/aktionen.
  * P1.4: backend/services/ausgehende_ereignisse.erzeuge() als
    Best-Effort-Helper. 5 Generierungs-Stellen instrumentiert
    (word_service, gebuehren_word, klage_routes, sta_routes,
    stellungnahme_routes).

Regeln:
  * RA-MICRO strikt read-only. Docker/CIFS nicht anfassen.
  * INTAKE_REVIEW_PFLICHT-Feature-Flag NICHT anpacken. P1.5 arbeitet
    OBERHALB der Umschaltung.
  * Alt-Tabellen (regulierung_positionen, schadenposition_belege,
    schadenpositionen, wdm_-Tabellen) werden weiter geschrieben.
    Kein DELETE, keine Migrationen daran.
  * Testgetrieben: erst Tests schreiben, RED, dann GREEN. Für die
    4 Bestätigungswege je einen fokussierten Test (Mocks für Word/PDF-
    Rendering, echter DB-Insert für die Ereignis-Zeile).
  * Testkriterium (aus POSITIONSMODELL-PLAN):
    (a) Nach ReguWizard-Erfassung liefert
        GET /akten/<az>/positionen/status dieselben Beträge wie die
        RegulierungSection (Abgleichstest).
    (b) Doppelerfassung erzeugt keine Doppel-Ereignisse.
    (c) K-M2a: Ergänzungsgutachten ersetzt nur die betroffenen
        Positions-Zeilen; unveränderte Positionen bleiben aktuell.

  * Regressionscheck am Ende: aktuelle Baseline auf intake-stufe1
    = 203 failed / 570 passed / 0 errors / 18 skipped. Diffbasiert
    prüfen (Vergleich Failure-Set vor/nach P1.5). Bekannte Alt-
    Failures (test_modul3/4/7 Auth-Cluster, test_modul1 Schema,
    test_sv_portal, test_prd27) zählen nicht als Regression.

  * Danach: Commit, docs/TODO.md-Eintrag "Aktueller Schritt" auf P1.6
    aktualisieren, dann STOPP -- nächster Schritt (P1.6) erst nach
    meiner Abnahme.

Hinweis: P1.5 ist im POSITIONSMODELL-PLAN als L (large) markiert.
Wenn der Umfang zu groß wirkt, teile ihn in Teilschritte P1.5a-d
(je Bestätigungsweg einer) mit Commit + Stopp zwischen den Teilen.
```

---

## Für weitere Sessions

Denselben Prompt kannst du für P1.6 ff. wiederverwenden — anzupassen sind:
- **Schrittnummer** (P1.6 / P1.7 / …)
- **K-Punkt-Zusatz** aus freigabe.md Abschnitt 4
  (bei P1.6: keine K-Punkte, System-Ereignisse via APScheduler-Job)
- **Baseline-Zahlen** (aus dem letzten Session-Commit oder dem TODO-Block)
- **Vorwissen** aktualisieren (den bereits erledigten Schritt ergänzen)
