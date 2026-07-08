# Prompt für nächste Session — S1.6b (Klassifikator-Kaskade + LLM-Extraktion nach YAML-Schema)

Vorher: `/model` → Opus 4.7 (falls nicht schon Standard). `/effort` → high.

Danach den folgenden Block kopieren und als Prompt einfügen:

---

```
Wir setzen ein geplantes, freigegebenes Refactoring um. Branch: intake-stufe1
(bitte prüfen, dass er aktiv ist).

Lies zuerst vollständig: freigabe.md (verbindlich, übersteuert die Pläne),
PIPELINE-REFACTORING-PLAN.md (Abschnitt S1.6), POSITIONSMODELL-PLAN.md
(alle im Projekt-Root). Die Planung ist abgeschlossen und freigegeben —
kein erneutes Brainstorming, keine Alternativvorschläge zur Architektur.

Nutze die Skills superpowers:executing-plans,
superpowers:test-driven-development und
superpowers:verification-before-completion.

Implementiere AUSSCHLIESSLICH Schritt S1.6b aus dem Pipeline-Plan
(Klassifikator-Kaskade + LLM-Extraktion). K-P3-Zusatz aus freigabe.md
sagt: S1.6 ist in a+b geteilt; S1.6a ist bereits abgeschlossen. In S1.6b
kommen NUR die Bausteine (2)–(5) aus dem Plan-Text zu S1.6:

  (2) Klassifikator Stufe 1: Regeln über VEREINIGTE Signale aller
      Zustellungen. Vererbte Signale (Absender/Domain/Kategorie aus
      email_absender_vorlagen + Zustellungs-signale_json) sind nur
      Kandidaten, nie allein "eindeutig".
  (3) Stufe 2: Qwen mit geschlossener Labelliste (Seite 1 + letzte
      Seite, je Seite auf ~3.000 Zeichen gekürzt, F-11). Unbekannte
      Klasse -> "sonstiges".
  (4) Extraktion: klassenspezifische Regex aus YAML (regex_felder) +
      Qwen-Extraktion nach YAML-schema. LLM ist Primärquelle, Regex
      ist Anker (Umkehrung des heutigen Shadow-Modes, gilt NUR im
      Neu-Pfad -- llm_service.py Regex-primär bleibt für Alt-Pfad
      unverändert).
  (5) Ergebnis am intake_dokument stempeln: klasse, klasse_quelle='auto',
      konfidenz, parse_json (jetzt mit extrahierten Feldern), textquelle
      hat S1.6a schon gestempelt.

Vorwissen aus S1.1–S1.6a (bereits umgesetzt, nicht anfassen):

  * S1.5: backend/registry/klassen/*.yaml (8 Klassen), Loader mit
    Versionsstempel unter backend/intake/registry_loader.py.
    lade_registry(standard_pfad()) im App-Start Fail-Loud.
    Endpoint GET /system/registry/status.
  * S1.6a: Migration 48 (versuch_zaehler/naechster_versuch/fehler_detail/
    worker_lease auf intake_dokumente). Queue-API backend/intake/queue.py
    (reserviere_naechsten/markiere_bereit/markiere_fehler/enqueue mit
    Backoff 1/5/30 min, MAX_VERSUCHE=3, F-10 single-instance-Lease).
    backend/intake/text_extraktion.py (seitenweise, Zeichensalat-Ratio).
    ocr_service.ocr_seite_mit_tsv (image_to_data + TSV-Persistierung).
    glm_ocr_service.py als Vision-Stub hinter Feature-Flag
    GLM_OCR_ENABLED (Default false).
    backend/intake/pipeline.py: verarbeite_dokument (Textschritt) +
    tick (APScheduler-Job intake_worker alle 10s).
    Ergebnis heute im Neu-Pfad: parse_json = {text_gesamt, seiten:[...]}
    und textquelle/registry_version/llm_stack sind gestempelt.
    klasse ist noch NULL -- S1.6b füllt sie.

Sitzungsentscheidungen (verbindlich):

  1. Klassifikator-Modul-Struktur: neue Datei backend/intake/klassifikator.py.
     - klassifiziere_stufe1(text, signale) -> (klasse_kandidaten, hinweise)
       nutzt YAML-Marker (aus registry_loader) + Zustellungs-Signale.
       Rückgabe: sortierte Liste (klasse, konfidenz, quelle), nicht ein
       einzelner Treffer -- Stufe 2 entscheidet.
     - klassifiziere_stufe2(text_seite1, text_letzte_seite,
                             kandidaten) -> (klasse, konfidenz)
       ruft LLM (llm_service, LLM_MODEL) mit closed-label-Prompt und
       Kürzung pro Seite auf ~3000 Zeichen (F-11).
  2. Extraktions-Modul: backend/intake/extraktion.py.
     - extrahiere_felder(text, klasse, registry) -> dict
       Regex-Felder aus YAML als Anker (dieselbe Logik wie
       test_registry_golden.py), dann LLM-Call mit dem YAML-schema
       als "response_format"-Beschreibung. LLM-Ergebnis überschreibt
       Regex-Werte (Regex dient nur als Fallback und
       Konsistenz-Check -> Feld llm_konflikt an parse_json wenn
       LLM ≠ Regex).
  3. Pipeline-Erweiterung: verarbeite_dokument in pipeline.py um die
     Schritte 2–5 erweitern -- NACH der Textgewinnung, VOR
     markiere_bereit. Bei Fehler: markiere_fehler wie bisher.
  4. LLM-Service: keine breite Umgestaltung. Neue Funktion
     llm_service.klassifiziere_geschlossen(labels, text) und
     llm_service.extrahiere_nach_schema(schema, text) -- klein,
     testbar, mit Timeout und Try/Except. Der bestehende Shadow-Mode
     bleibt unangetastet für den Alt-Pfad.

Regeln:
  * RA-MICRO strikt read-only. Docker/CIFS nicht anfassen.
  * Alt-Pfade (registry.json + dispatcher.py + llm_service.py Shadow-
    Mode) NICHT umbauen -- reines Doppelbetrieb-Prinzip bis S1.9.
  * Charakter des Schritts: reine Ergänzung. Neue Module + Erweiterung
    verarbeite_dokument. Keine bestehenden Aufrufer ändern.
  * Testgetrieben: erst Tests schreiben, RED, dann GREEN. Für LLM-Calls
    unittest.mock verwenden -- KEINE Netzwerkzugriffe im Test.
  * Golden-Test erweitern: der bestehende
    test_s16a_golden_e2e.py sollte nach S1.6b auch klasse=erwartete_klasse
    und Felder im parse_json prüfen -- statt einer neuen Test-Datei den
    bestehenden Test erweitern oder eine test_s16b_klassifikation_e2e.py
    daneben legen.
  * Regressionscheck am Ende: aktuelle Baseline auf intake-stufe1
    (ohne meine neuen Tests, ohne meine app.py-Änderung) = 277 failed /
    359 passed / 26 errors / 2 skipped. Bekannte Alt-Failures (Flask-
    Import-Bug in Test-Reihenfolge) zählen nicht als Regression.
  * Danach: Commit, docs/TODO.md-Eintrag "Aktueller Schritt" auf S1.7
    aktualisieren, dann STOPP -- nächster Schritt (S1.7) erst nach
    meiner Abnahme.
```

---

## Für weitere Sessions

Denselben Prompt kannst du für S1.7 ff. wiederverwenden — anzupassen sind:
- **Schrittnummer** (S1.7 / S1.8 / S1.9 …)
- **K-Punkt-Zusatz** aus freigabe.md Abschnitt 4
  (bei S1.8: K-2 + K-M2b; bei S1.9: K-P1).
- **Baseline-Zahlen** (aus dem letzten Session-Commit oder dem TODO-Block).
- **Vorwissen** aktualisieren (den bereits erledigten Schritt ergänzen).
