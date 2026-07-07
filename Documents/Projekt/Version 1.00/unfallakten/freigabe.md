# FREIGABE: PIPELINE-REFACTORING-PLAN.md + POSITIONSMODELL-PLAN.md
Stand: 2026-07-07 · Freigegeben durch RA Schatz · verbindlicher Implementierungsauftrag

Beide Planungsdokumente sind freigegeben — mit den folgenden Beschlüssen und
Korrekturen. Bei Widerspruch zwischen Plan und diesem Dokument gilt dieses
Dokument. Die Korrekturen werden NICHT als neue Planungsrunde behandelt,
sondern beim jeweiligen Schritt direkt eingearbeitet.

## 1. Entscheidungen zu den offenen Fragen

**Pipeline-Plan:** F-02, F-03, F-04, F-05, F-07, F-09, F-10, F-11 — Empfehlung
angenommen, unverändert umsetzen.
- **F-01:** GLM-OCR wird als zweiter LM-Studio-Endpoint aufgesetzt (OpenAI-
  kompatibel, VRAM ausreichend: 128 GB). Eigene Vorbereitungsaufgabe VOR S1.6
  (siehe Abschnitt 4). Bis dahin Tesseract primär hinter GLM_OCR_ENABLED=false.
- **F-06:** Löschfristen werden NICHT in der Registry hartkodiert. Registry-YAML
  enthält nur den Default (6 Jahre); maßgeblich ist eine Einstellungsseite
  (bestehendes konfiguration-Muster), auf der die Frist je Dokumentklasse
  gepflegt wird. Löschvollzug bleibt Stufe 2, manuell bestätigt.
- **F-08:** Zunächst lokaler Weg hinter output_adapter-Interface. XML-Scanner-
  Doku wird nachgereicht (in wenigen Tagen); Adapter-Implementierung dann als
  eigener Schritt, ohne den Plan zu ändern.
- **F-12:** Wird vor Implementierungsstart auf dem Host erledigt (RA Schatz).

**Positionsmodell-Plan:** PF-01, PF-03, PF-05, PF-06, PF-08, PF-09, PF-10,
PF-11 — Empfehlung angenommen, unverändert umsetzen.
- **PF-02 (geändert):** Die Ereignisse forderung_generiert (wirkung gefordert)
  werden wie geplant geschrieben und steuern die Eskalationsableitung. Die UI
  zeigt aber KEINE Unterscheidung kalkuliert/gefordert — eine Betragsspalte,
  keine zwei Labels. Die Unterscheidung existiert nur intern.
- **PF-04 (konkretisiert):** Ereignis bei Generierung, Typen heißen *_generiert.
  Eskalation rechnet ab Generierungsdatum + konfigurierbarer Karenz
  (Einstellungsseite, Default: +1 Werktag) als angenommenem Versand.
  Optionaler Ein-Klick „versandt am" in der Ereignisliste überschreibt die
  Annahme. Kein Zwangsfeld.
- **PF-07:** Blindfleck akzeptiert. Aktenkonto-Plausibilitätshinweis (2.4) als
  frühes P2-Feature vormerken; mandantenweisung/zahlung_ohne_abrechnung als
  erste manuelle Ereignistypen der P2-Konzeption.

## 2. Verbindliche Korrekturen am Pipeline-Plan

**K-P1 — Fragebogen-Flow wird in S1.9 mit umgestellt (BREAKING #6).**
Das Auto-Enrichment (fragebogen_parser → direkte Schreibvorgänge in
Beteiligten-/Unfalldetail-Tabellen) entfällt. Fragebogen-Mails laufen durch
die Review-Queue; geparste Antworten erscheinen als Vorschlag im Freigabe-
Dialog, Übernahme erst mit Freigabe. Die S1.9-Assertion („kein Schreibweg
ohne freigegeben_von") wird auf ALLE Akten-Tabellen ausgeweitet, die der
Intake befüllen kann — nicht nur dokumente/schadenpositionen.

**K-P2 — Freigabe wird eigene Relation, nicht Feld.**
intake_dokumente.akte_az/freigegeben_von/_am entfallen als Spalten; stattdessen
Tabelle `freigaben` (id, intake_dokument_id FK, akte_az FK, dokument_id FK →
dokumente(id) [die durch die Freigabe erzeugte Zeile], freigegeben_von,
freigegeben_am). Grund: dasselbe Dokument kann in mehrere Akten freigegeben
werden (zwei Mandanten, ein Unfall — Alltag); zugleich liefert dokument_id
die FK-Brücke, auf der das Positionsmodell (PF-10) aufsetzt.
S1.1-Backfill entsprechend anpassen: sha256-Duplikate über Akten hinweg
werden zu EINEM intake_dokument mit n zustellungen und n freigaben; das
Testkriterium „Backfill-Zeilenzahlen = Bestandszahlen" gilt für zustellungen
+ freigaben, nicht für intake_dokumente.

**K-P3 — S1.6 wird verbindlich geteilt** in S1.6a (Queue + Textgewinnung/OCR/
TSV) und S1.6b (Klassifikator-Kaskade + Extraktion). Zwei Schritte, zwei
Testläufe.

**K-P4 — Doppelparsing-Phase (S1.6–S1.9):** akzeptiert, keine Begrenzung auf
Teilbestand nötig.

## 3. Verbindliche Korrekturen am Positionsmodell-Plan

**K-M1 — UNIQUE-Constraint ereignis_positionen:** UNIQUE(ereignis_id,
position_key, wirkung, COALESCE(kuerzungsart_id, 0)) — mehrere Kürzungsarten
auf derselben Position im selben Ereignis sind der Normalfall (Prüfbericht).
Cache-PK (4.4) analog um kuerzungsart erweitern.

**K-M2 — Edit-/Ersetzungs-Semantik ist Teil von P1.5 und der UI:**
(a) Erneutes Speichern im ReguWizard zu einem bereits ereignis-erfassten
Abrechnungsschreiben erzeugt ein NEUES Ereignis, das das vorherige Ereignis
desselben Dokuments per ersetzt_durch (Kopf) ersetzt — nie Update, nie
Doppelereignis. (b) Der Freigabe-Dialog (S1.8) und die Ereignisliste (P1.7)
erhalten eine „ersetzt …"-Auswahl: beim Ergänzungsgutachten wählt der
Bearbeiter, welche Positionszeilen des Erstgutachtens positionsscharf ersetzt
werden. Testkriterium P1.5 wird um beide Fälle erweitert.

**K-M3 — Backfill-Ehrlichkeit:** Backfill-Ereignisse ohne rekonstruierbare
Positionszuordnung (Forderungsschreiben außerhalb Variante „hoehe") werden
als Akten-Scope-Ereignis mit herkunft='backfill' angelegt. Das Dashboard
zeigt bei Akten mit solchen Lücken einmalig: „Eskalationsvorschläge für
diese Akte erst ab [Einführungsdatum] verlässlich." (Durch PF-02-Kompromiss
entschärft — der Hinweis genügt.)

## 4. Verbindliche Reihenfolge (verschränkt)

0. Vorbereitung (RA Schatz, parallel): F-12 LM-Studio-Logging prüfen;
   GLM-Vision-Endpoint in LM Studio aufsetzen; XML-Scanner-Doku beschaffen.
1. **S1.1–S1.5** (Datenmodell inkl. K-P2, Archiv, Adapter, Absender-Registry,
   Klassen-Registry + Loader)
2. **P1.1–P1.4** (Positions-Konfiguration [Loader aus S1.5 mitbenutzen, K-1],
   Ereignis-Tabellen inkl. K-M1, Ableitung, ausgehende Ereignisse)
3. **S1.6a, S1.6b, S1.7, S1.8, S1.9** (Queue, Kaskade, Matching, Review-UI
   [Freigabe-Dialog inkl. Ereignis-Vorschlägen K-2 und „ersetzt"-Auswahl
   K-M2b], Umschaltung inkl. K-P1)
4. **P1.5–P1.8** (eingehende Ereignisse inkl. K-M2a, System-Ereignisse, UI,
   Backfill inkl. K-M3)

Migrations-Nummern fortlaufend nach tatsächlicher Reihenfolge (PF-06).
Jeder Schritt: lauffähig, Testkriterium erfüllt, dann erst weiter. Kein
Schritt beginnt, bevor der vorherige abgenommen ist.