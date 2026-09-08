# Prompt für nächste Session — S1.5 (Dokumentklassen-Registry YAML + Loader + Golden-Files)

Vorher: `/model` → Opus 4.7 (falls nicht schon Standard). `/effort` → high.

Danach den folgenden Block kopieren und als Prompt einfügen:

---

```
Wir setzen ein geplantes, freigegebenes Refactoring um. Branch: intake-stufe1
(bitte prüfen, dass er aktiv ist).

Lies zuerst vollständig: freigabe.md (verbindlich, übersteuert die Pläne),
PIPELINE-REFACTORING-PLAN.md, POSITIONSMODELL-PLAN.md (alle im Projekt-Root).
Die Planung ist abgeschlossen und freigegeben — kein erneutes Brainstorming,
keine Alternativvorschläge zur Architektur.

Nutze die Skills superpowers:executing-plans,
superpowers:test-driven-development und
superpowers:verification-before-completion.

Implementiere AUSSCHLIESSLICH Schritt S1.5 aus dem Pipeline-Plan
(Dokumentklassen-Registry als YAML + Loader mit Versionsstempel + Golden-
Files). S1.5 hat KEINEN K-Punkt-Zusatz in freigabe.md — direkt nach Plan
umsetzen.

Sitzungsentscheidungen (aus der Vorsession, verbindlich):

  1. Golden-Files als MINIMAL-FIXTURES: synthetische, im Repo speicherbare
     Text-/PDF-Bytes je Klasse, KEINE echten Kanzlei-Dokumente (DSGVO).
     Analog zum Muster aus test_intake_archiv.py (_minimales_pdf_bytes()
     via PyMuPDF).

  2. Frontend-Kachel im Health-Dashboard ist NICHT Teil von S1.5. In
     S1.5 wird nur die Backend-Seite komplett gebaut:
       * Loader mit Fail-Loud beim App-Start (RuntimeError → app.py
         bricht ab, ERROR-Log).
       * Neuer Endpoint  GET /system/registry/status  liefert
         {ok, version, klassen: [...], fehler: [...]} — trivial testbar
         mit pytest.
     Die Kachel im Health-Dashboard folgt als eigener Mini-Schritt danach.

Vorwissen aus S1.1–S1.4 (bereits umgesetzt, nicht anfassen):
  * S1.1: Migration 46 — intake_dokumente, zustellungen, freigaben,
    korrektur_log. FK-Spalte heißt intake_dokument_id.
  * S1.2: backend/intake/archiv.py (lege_original_ab, erzeuge_arbeitskopie).
  * S1.3: backend/intake/adapter_{imap,upload,eakte}.py + _persistenz.py.
    UTF-16-BOM-Logik lebt in adapter_imap.dekodiere_email_payload.
    Doppelschreiben in import_service/dokumente_routes/eakte_routes.
  * S1.4: Migration 47 — email_absender_vorlagen um vertrauensstufe,
    klasse_kandidat, ramicro_adressnr erweitert.
    backend/scripts/konsolidiere_absender_registry.py portiert
    registry.json.marker[*].domain in die Tabelle.
    adapter_imap reichert Body-Zustellung.signale_json an.

Regeln:
  * Charakter des Schritts: reine Ergänzung (neue Verzeichnisse
    backend/registry/klassen/ + backend/intake/registry_loader.py +
    backend/tests/golden/ + neuer Route-Blueprint). registry.json bleibt
    unverändert im Alt-Pfad des Dispatchers (Doppelbetrieb).
  * Start-Klassen (je eine YAML): gutachten, abrechnungsschreiben,
    pruefbericht, rechnung, sv_rechnung, abschlepprechnung,
    standkostenrechnung, sonstiges.
  * YAML-Felder je Klasse (aus dem Plan):
      marker, regex_felder, schema, pflichtfelder, kritische_felder,
      validierungsregeln (Feld anlegen, Auswertung erst Stufe 2),
      fristrelevanz (Feld, Stufe 2), loeschfrist_jahre (F-06, Default
      6 Jahre — Auswertung erst Stufe 2).
  * Loader:
      - berechnet registry_version = kurzer Hash über alle YAMLs
        (deterministisch, reproduzierbar, ändert sich bei jeder YAML-
        Änderung).
      - Ladefehler = raise (Fail-Loud) + ERROR-Log; app.py registriert
        den Loader im Startup, damit App bei defektem YAML gar nicht
        erst hochkommt.
      - Kein stiller Fallback auf leere Registry (behebt heutigen Bug in
        registry.json-Loader).
  * Golden-Files je Klasse unter backend/tests/golden/<klasse>/:
      - Minimal-Fixtures + erwartetes JSON (Klasse + zentrale Felder).
      - pytest prüft: Loader parst YAML, Klassifikation trifft erwartete
        Klasse, extrahierte Felder ≙ Golden-JSON. Ein absichtlich
        defektes YAML in einer Test-Kopie → Loader wirft, App-Start
        schlägt fehl.
  * RA-MICRO strikt read-only. Docker/CIFS nicht anfassen.
  * Alt-Pfad muss verhaltensgleich bleiben; registry.json/dispatcher.py
    NICHT umbauen.
  * Testgetrieben arbeiten: erst Tests schreiben, RED, dann GREEN.
  * Regressionscheck am Ende: aktuelle Baseline auf intake-stufe1 ist
    346 passed / 274 failed / 23 errors / 2 skipped (Stand nach S1.4).
    Bekannte Alt-Failures zählen nicht als Regression.
  * Danach: Commit, docs/TODO.md-Eintrag „Aktueller Schritt" auf S1.6a
    aktualisieren, dann STOPP — nächster Schritt (S1.6a) erst nach
    meiner Abnahme.
```

---

## Für weitere Sessions

Denselben Prompt kannst du für S1.6a ff. wiederverwenden — anzupassen sind:
- **Schrittnummer** (S1.6a / S1.6b / S1.7 / …)
- **K-Punkt-Zusatz** aus freigabe.md Abschnitt 4
  (bei S1.6a/b: K-P3; bei S1.8: K-2 + K-M2b; bei S1.9: K-P1).
- **Baseline-Zahlen** (aus dem letzten Session-Commit oder dem TODO-Block).
