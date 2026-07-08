# Prompt für nächste Session — S1.8 (Review-UI-Rohbau, K-2 + K-M2b)

Vorher: `/model` → Opus 4.7 (falls nicht schon Standard). `/effort` → high.

Danach den folgenden Block kopieren und als Prompt einfügen:

---

```
Wir setzen ein geplantes, freigegebenes Refactoring um. Branch: intake-stufe1
(bitte prüfen, dass er aktiv ist).

Lies zuerst vollständig: freigabe.md (verbindlich, übersteuert die Pläne),
PIPELINE-REFACTORING-PLAN.md (Abschnitt S1.8), POSITIONSMODELL-PLAN.md
(alle im Projekt-Root). Die Planung ist abgeschlossen und freigegeben —
kein erneutes Brainstorming, keine Alternativvorschläge zur Architektur.

Nutze die Skills superpowers:executing-plans,
superpowers:test-driven-development und
superpowers:verification-before-completion.

Implementiere AUSSCHLIESSLICH Schritt S1.8 aus dem Pipeline-Plan
(Review-UI-Rohbau) inkl. der Freigabe-Korrekturen K-2 und K-M2b:

  * Backend-Blueprint intake_bp mit Endpunkten:
    - GET  /intake/queue                     (Liste bereit_zur_review + pipeline_fehler,
                                              Sortierung Alter -> Konfidenz;
                                              Fristen-Prio ist S2)
    - GET  /intake/dokument/<id>             (Detail + parse_json + Kandidaten
                                              aus S1.7 + Zustellungshistorie)
    - PATCH /intake/dokument/<id>/klasse     (manuelle Reklassifikation ->
                                              re-enqueue mit korrektem
                                              Registry-Eintrag)
    - PATCH /intake/dokument/<id>/felder     (Feld-Korrektur -> korrektur_log-
                                              Eintrag: feld, alt, neu, klasse,
                                              registry_version)
    - POST  /intake/dokument/<id>/freigabe   (einzige Schreib-Op Richtung Akte:
                                              erzeugt dokumente-Zeile via neuen
                                              output_adapter + freigaben-Zeile
                                              mit intake_dokument_id, akte_az,
                                              dokument_id, freigegeben_von/_am)

  * K-2 (freigabe.md): Der Freigabe-Endpunkt liefert bereits im GET-Detail
    KANDIDATEN-EREIGNIS-VORSCHLÄGE mit -- also der Client kann sie im
    Dialog bestätigen/korrigieren. In S1.8 nur das Feld erzeugen und
    weiterreichen; die tatsächliche Ereignis-Persistierung wird von P1.5
    (Positionsmodell) übernommen. Für S1.8 also nur STRUKTUR anlegen,
    Persistenz später.

  * K-M2b (freigabe.md): Der Freigabe-Dialog + die Ereignisliste erhalten
    eine "ersetzt …"-Auswahl. Für S1.8: das Payload-Feld `ersetzt_ids`
    entgegennehmen und im korrektur_log/freigaben-Kontext festhalten;
    die tatsächliche Ersetzungslogik liegt im Positionsmodell (K-M2a/b
    dort).

  * neuen output_adapter unter backend/ramicro/output_adapter.py:
    - schreibe_dokument(intake_dok, akte_az, freigegeben_von) -> dokument_id
    - Impl fuer Stufe 1: der HEUTIGE lokale Weg (dokumente-Zeile in der
      Akte via registriere_dokument-Muster). Der echte XML-Scanner-
      Adapter kommt spaeter (F-08).
    - Interface klein halten, damit XML-Scanner spaeter einfach dazu
      kommt.

  * Frontend ReviewQueueView.jsx + Unterkomponenten:
    - Queue-Liste (drei Zustaende: bereit_zur_review / pipeline_fehler /
      leer). Sortierung: Alter absteigend, dann Konfidenz.
    - Detail-Panel: PDF im iframe (Arbeitskopie), extrahierte Felder
      editierbar, Klasse-Dropdown, Konfidenz + Hinweise, Akten-
      Kandidaten aus parse_json (Score-Chip), Zustellungshistorie,
      LLM-vs-Regex-Diskrepanzen als Hinweis.
    - Aktionen: Klasse aendern (Re-Parse), Felder speichern
      (korrektur_log), Akte zuordnen (Kandidat oder Freitextsuche),
      Freigabe -> Bestaetigungs-Dialog mit Ereignis-Vorschlaegen
      (K-2) und ersetzt-Auswahl (K-M2b).
    - Routing in App.jsx + api.js.

Vorwissen aus S1.1–S1.7 (bereits umgesetzt, nicht anfassen):

  * S1.5: backend/registry/klassen/*.yaml, Loader mit Versionsstempel.
  * S1.6a: Queue (backend/intake/queue.py), Textgewinnung
    (backend/intake/text_extraktion.py), Tesseract+TSV, GLM-OCR-Stub.
    Pipeline `verarbeite_dokument` stempelt textquelle / registry_version /
    llm_stack / parse_json{text_gesamt, seiten}.
  * S1.6b: Klassifikator (Stufe 1 Regeln + Stufe 2 LLM closed-label) und
    Extraktion (LLM primaer, Regex-Anker, llm_konflikt). Pipeline stempelt
    zusaetzlich klasse, klasse_quelle='auto', konfidenz + parse_json.klassifikation
    + parse_json.felder.
  * S1.7: backend/intake/akten_matching.py mit finde_kandidaten(text, signale).
    Score-Staffel az_exakt 1.0 / az_basis 0.9 / kfz 0.7 / mail 0.6 / name_datum 0.5.
    Pipeline schreibt Kandidatenliste in parse_json.akten_kandidaten.
    KEIN Auto-Zuordnen -- die Freigabe in S1.8 waehlt aus.

Sitzungsentscheidungen (verbindlich):

  1. Blueprint-Modul-Struktur: neue Datei backend/routers/intake_routes.py.
     - intake_bp = Blueprint("intake", __name__, url_prefix="/intake").
     - Alle Endpunkte prueflen Auth via @login_erforderlich (bestehendes
       Muster).
     - Nur JSON-Responses.

  2. Freigabe erzeugt (a) einen dokumente-Eintrag ueber den output_adapter
     UND (b) eine freigaben-Zeile mit intake_dokument_id / akte_az /
     dokument_id / freigegeben_von / freigegeben_am. Nach erfolgreicher
     Freigabe wird intake_dokumente.queue_status auf 'freigegeben' gesetzt.
     Ohne akte_az -> 422 (siehe S1.8-Testkriterium).

  3. Reklassifikation: PATCH /intake/dokument/<id>/klasse setzt
     klasse+klasse_quelle='manuell', schreibt korrektur_log-Zeile (feld=
     'klasse') und ruft enqueue() aus S1.6a auf -- der Worker parst dann
     die Felder mit dem korrekten Registry-Eintrag neu.

  4. Feld-Korrektur: PATCH /intake/dokument/<id>/felder erwartet
     { feld: {alt, neu} }, schreibt korrektur_log fuer jedes Feld, aktualisiert
     parse_json.felder. KEIN Re-Parse.

  5. Frontend-Skeleton: PDF-Anzeige im iframe genuegt (Bounding-Boxes =
     Stufe 2). Keine PDF.js-Integration in S1.8.

Regeln:
  * RA-MICRO strikt read-only. Docker/CIFS nicht anfassen.
  * Alt-Pfade (registry.json + dispatcher.py + llm_service.py Shadow-
    Mode + import_service AUTO-PFADE) NICHT umbauen -- Umschaltung ist S1.9.
  * Charakter des Schritts: NEUE Endpunkte + NEUE View, keine Aenderungen
    an bestehenden Alt-Routen. Bestehende Frontend-Views bleiben bestehen.
  * Testgetrieben: erst Tests schreiben, RED, dann GREEN. Fuer LLM- oder
    RA-Micro-Aufrufe unittest.mock verwenden -- KEINE Netzwerkzugriffe im Test.
  * Testkriterium: End-to-end am Golden-File Abrechnungsschreiben ->
    Queue enthaelt Dokument -> Klasse korrigieren -> Re-Parse sichtbar
    -> Akte zuordnen -> Freigabe -> dokumente-Zeile in der Akte +
    freigaben-Eintrag + intake_dokument.queue_status='freigegeben' +
    korrektur_log enthaelt die Feldaenderung. Freigabe ohne Akte -> 422.
  * Regressionscheck am Ende: aktuelle Baseline auf intake-stufe1
    = 211 failed / 524 passed / 0 errors / 18 skipped. Bekannte Alt-
    Failures (test_modul3/4/7 Auth-Cluster, test_modul1 Schema-Details)
    zaehlen nicht als Regression.
  * Danach: Commit, docs/TODO.md-Eintrag "Aktueller Schritt" auf S1.9
    aktualisieren, dann STOPP -- naechster Schritt (S1.9) erst nach
    meiner Abnahme.
```

---

## Für weitere Sessions

Denselben Prompt kannst du für S1.9 ff. wiederverwenden — anzupassen sind:
- **Schrittnummer** (S1.9 / P1.1 / …)
- **K-Punkt-Zusatz** aus freigabe.md Abschnitt 4
  (bei S1.9: K-P1 — Fragebogen-Flow in die Review-Queue; Auto-Pfade abschalten).
- **Baseline-Zahlen** (aus dem letzten Session-Commit oder dem TODO-Block).
- **Vorwissen** aktualisieren (den bereits erledigten Schritt ergänzen).
