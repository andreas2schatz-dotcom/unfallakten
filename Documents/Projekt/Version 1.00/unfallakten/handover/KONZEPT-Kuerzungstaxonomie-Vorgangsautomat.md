# Architektur: Kürzungstaxonomie, Vorgangsautomat & ReviewQ als Actioncenter

**Status:** Brainstorming / Architekturidee — NICHT umsetzen, bevor die Intake-Pipeline (P1.x) vollständig fertig und stabil ist.
**Zweck:** Übergabedokument für eine spätere Claude-Code-Session. Enthält Prüfauftrag an die bestehende Codebasis, Datenmodell, Automaten-Design, ReviewQ-Konzept, offene Entscheidungen und Bauphasen.
**Entstanden:** Strategiegespräch Juli 2026 (optimaler Prozessflow Verkehrsrechtskanzlei).
**Ergänzt:** 2026-07-11 — Abschnitt 10 (Codebasis-Spiegelung) mit Vorab-Antworten auf den Prüfauftrag. Codebasis-Stand: Branch `intake-stufe1`, Schema 55, P1.1–P1.7 abgeschlossen.
**Ergänzt:** 2026-07-23 — Abschnitt 11 (Konsolidierung). Anlass: Brainstorming-Session zu TODO-Punkt „Standardtexte pflegbar" deckte dieses Papier als bereits vorhandenen, passenderen Rahmen auf. Codebasis-Stand: `main`, Schema 63.
**Ergänzt:** 2026-07-23 (Session 2) — Abschnitt 12 (Verifikation & Prozess-Revision): Korrektur zweier 11.4-Befunde, Migrations-Delta 56–63 geprüft, RA-MICRO-Aktenkonto negativ, Differenz-Mathematik im Ereignismodell gefunden. Entscheidungen (Reihenfolge Phase 1 vor V11, Urteilscheck entfällt, Zahlungs-Kaskade) → `docs/DECISIONS.md`.

---

## 0. Kernthese (Warum das Ganze)

Die Regulierungs-KI der Versicherer ist ökonomisch kalibriert: Sie kürzt, wo der erwartete Widerstand niedrig ist. Ihr Geschäftsmodell ist die Nichtwiderspruchsquote. Antwort der Kanzlei: **Grenzkosten pro qualifiziertem, belegtem Widerspruch gegen null** — bei gleichbleibender Begründungsqualität. Zweiter Layer (spieltheoretisch): konsequente, lückenlose Durchsetzung signalisiert den Versicherer-Modellen den Gegnertyp "teuer" und verschiebt deren Kürzungspolitik ex ante (wiederholtes Spiel, Reputationseffekt).

Nebenprodukt und eigentliches Asset: **Kürzungsverhaltens-Datenbank** pro Versicherer/Prüfdienstleister/Gericht aus den eigenen Akten.

---

## 1. Prüfauftrag an die bestehende Codebasis (erster Schritt der Session)

> **Hinweis 2026-07-11:** Der Prüfauftrag ist in Abschnitt 10 bereits zur Hälfte vorab beantwortet. Die spätere Session verifiziert die Befunde (Codebasis kann sich weiterentwickelt haben) und füllt die verbleibenden Lücken — sie beginnt NICHT bei null.

Vor jeder Implementierung die bestehende Codebasis (Flask/SQLite/React, Event-Tabelle, Document-Envelope, Review-UI der Intake-Pipeline) auf folgende Fragen prüfen:

1. **Event-Tabelle:** Trägt das bestehende Event-Schema einen zusätzlichen Scope `vorgang_id` bzw. `kuerzung_id`? Oder braucht es eine Scope-Verallgemeinerung (`scope_table`/`scope_id`)? Ziel: KEINE zweite Event-Tabelle. *(→ 10.2 Frage 1)*
2. **Review-UI:** Wie generisch ist das bestehende Review-UI der Intake-Pipeline? Kann es zu einer allgemeinen Queue erweitert werden (verschiedene Eintragstypen: Dokument-Review, Kürzungs-Review+Freigabe, Frist-Task) oder ist es fest mit Dokument-Extraktion verdrahtet? *(→ 10.2 Frage 2)*
3. **Abrechnungsschreiben-Entität:** Existiert bereits (inkl. des gefixten PRIMARY-KEY-Bugs). Welche Felder fehlen: `pruefdienstleister_id`, Verknüpfung zu Kürzungszeilen? *(→ 10.2 Frage 3)*
4. **Schadensposition:** Ist das Positionsmodell so referenzierbar, dass eine Kürzung auf eine Position zeigen kann (FK)? *(→ 10.2 Frage 4 — Achtung, Modell-Konflikt)*
5. **Freigabe-Mechanik:** Wie ist "human approval als einziger Write" aktuell implementiert? Wiederverwendbar für Freigabe von generierten Schreiben? *(→ 10.2 Frage 5)*
6. **Word-Generator:** Kann der bestehende Generator (WDM-Fallback-Pattern) parametrisierte Textbausteine aus Markdown/Registry rendern, oder braucht es einen eigenen Renderer für Stellungnahmen? *(→ 10.2 Frage 6)*
7. **Scheduler:** Gibt es bereits einen Cron-/Loop-Mechanismus im Docker-Setup, an den ein täglicher Fristen-Check angehängt werden kann? *(→ 10.2 Frage 7 — ja, P1.6)*
8. **Migrations-Stand:** Aktuelle Schema-Version, damit die neuen Tabellen als saubere Migration kommen. *(→ 10.2 Frage 8)*

Ergebnis des Prüfauftrags: Gap-Liste + Migrationsplan, DANN erst Code.

---

## 2. Kürzungstaxonomie

### 2.1 Grundsatzentscheidungen

- **Zwei orthogonale Ebenen:** Kürzung dem Grunde nach (Haftungsquote) = Attribut der Akte/Regulierung (`quote_behauptet`, `quote_akzeptiert`), KEIN Kürzungstyp. Kürzung der Höhe nach = Taxonomie.
- **Kürzung = Tripel (Schadensposition × Kürzungstyp × Betrag).** Eine Position kann von mehreren Typen gleichzeitig getroffen werden.
- **Die Taxonomie wird aus den vorhandenen Textbausteinen abgeleitet** (liegen als Word vor, Markdown-Konvertierung bereits begonnen). Die Bausteinsammlung IST die empirisch validierte Taxonomie. Die Referenzliste unten dient nur als Gegenprobe auf Lücken.
- **Typen sind append-only:** nie umdefinieren, bei Bedarf `A04b` anlegen statt `A04` umbauen. Keine Registry-Versionierung nötig (Entscheidung Andi, bestätigt).

### 2.2 Referenzliste (Gegenprobe, ~30 Typen, 6 Kategorien)

**A — Reparaturkosten fiktiv:** A01 UPE-Aufschläge · A02 Verbringungskosten · A03 Beilackierung · A04 Stundenverrechnungssatz/Verweisung · A05 Arbeitszeitwerte · A06 Kleinteile/Verschnitt · A07 Neu-für-alt/Vorschaden · A08 Positionen "nicht unfallkausal" · A09 Reparaturweg · A10 Reparaturbestätigung

**B — Reparaturkosten konkret:** B01 Rechnungskürzung trotz Reparatur (Werkstattrisiko) · B02 einzelne Rechnungspositionen · B03 130%-Grenze

**C — Fahrzeugwert:** C01 merkantile Wertminderung · C02 Restwert (Börse vs. regional) · C03 Wiederbeschaffungswert · C04 Wiederbeschaffungsdauer

**D — Ausfall/Mobilität:** D01 Nutzungsausfall Dauer · D02 NA Klasse/Tagessatz · D03 Nutzungswille/-möglichkeit · D04 Mietwagen Tarif · D05 Mietwagen Dauer · D06 Mietwagen Klasse/Eigenersparnis

**E — Nebenkosten:** E01 SV-Grundhonorar · E02 SV-Nebenkosten · E03 Abschleppkosten · E04 Standgeld · E05 An-/Abmeldung · E06 Unkostenpauschale · E07 RA-Gebühren · E08 Attest-/Befundkosten

**F — Personenschaden (nur Statistik, kein Baustein-Pfad):** F01 Schmerzensgeld · F02 Haushaltsführungsschaden · F03 Verdienstausfall · F04 Heilbehandlung. Flag `baustein_pfad: false`; Automat ist hier nur Fristenwächter, Inhalt über Skills (`haushaltsführungsschaden`) bzw. Handarbeit.

### 2.3 Zwei Pflichtfelder (oft vergessen, statistisch Gold)

1. **`pruefdienstleister_id`** pro Abrechnungsschreiben (ControlExpert, Eucon, DEKRA-Prüfdienst, …). Hypothese: Achse (Dienstleister × Typ) trennt schärfer als (Versicherer × Typ), weil derselbe Dienstleister für mehrere Versicherer identisch kürzt. → Mit eigenen Daten validieren.
2. **`begruendung_roh`** — Wortlaut des Kürzungsgrunds immer mitspeichern. (a) für konkrete Erwiderung im Schreiben, (b) Template-Wechsel-Erkennung = Frühwarnsystem für geänderte Kürzungspolitik.

### 2.4 Registry-Format (YAML, analog Dokumentklassen-Registry)

```yaml
# kuerzungstypen/A02_verbringungskosten.yaml
id: A02
kategorie: reparaturkosten_fiktiv
name: Verbringungskosten
baustein_pfad: true
erkennung:
  keywords: ["Verbringung", "Verbringungskosten", "Fremdlackierung"]
  llm_hinweis: "Kürzung der Kosten für Verbringung des Fahrzeugs zur Lackiererei bei fiktiver Abrechnung"
beweisanforderungen:
  - "SV-Gutachten weist Verbringung als regional üblich aus"
  - "ggf. Bestätigung Referenzwerkstatt ohne eigene Lackiererei"
rechtsprechung_refs: []   # NUR IDs aus Rechtsprechungstabelle; Befüllung ausschließlich via urteil-verifikation
textbaustein: tb_A02_v3   # Referenz auf Markdown-Baustein
klage:
  typischer_streitwert_anteil: "50-150 EUR"
statistik_dimensionen: [versicherer, pruefdienstleister, gericht]
```

### 2.5 Rechtsprechungstabelle

- Eigene Tabelle, Einträge NUR nach Durchlauf `urteil-verifikation` (PFLICHT-PRÜFLAYER), mit `verifiziert_am`.
- Wartungsidee (später): Refs älter als 12 Monate zur Re-Verifikation vorlegen. Grund: Ein schiefer Beleg in einem Baustein war bisher ein Fehler pro Fall — automatisiert ist er ein Fehler pro Serie.

### 2.6 Datenmodell Kürzung

```sql
CREATE TABLE kuerzung (
  id INTEGER PRIMARY KEY,
  abrechnungsschreiben_id INTEGER NOT NULL REFERENCES abrechnungsschreiben(id),
  schadensposition_id INTEGER NOT NULL REFERENCES schadensposition(id),
  kuerzungstyp_id TEXT NOT NULL,              -- 'A02'
  betrag_gefordert_ct INTEGER NOT NULL,
  betrag_gekuerzt_ct INTEGER NOT NULL,
  begruendung_roh TEXT,
  pruefdienstleister_id INTEGER,
  klassifikation TEXT NOT NULL DEFAULT 'llm_vorschlag'
    CHECK (klassifikation IN ('llm_vorschlag','bestaetigt','manuell'))
);
-- Ergebnis NICHT als Spalte. Abgeleitet aus Events auf Scope kuerzung:
-- widerspruch_versandt, zahlung_zugeordnet, ablehnung_eingegangen,
-- klage_erhoben, erledigt(ergebnis, betrag_ct)
```

> **Hinweis 2026-07-11:** Dieses DDL ist als Skizze zu lesen, nicht als beschlossenes Schema. Drei Konflikte mit der Codebasis (FK `schadensposition_id` existiert so nicht; `betrag_ct` bricht das REAL-Euro-Muster; Überlappung mit `regulierung_positionen` bzw. `ereignis_positionen`) — Details und Entscheidungsoptionen in 10.3.

### 2.7 Auswertungsschicht (Views, kommt zuletzt)

Kürzungsquote, Widerspruchserfolgsquote, Klageerfolgsquote, Mediandauer — je (Versicherer × Typ), (Prüfdienstleister × Typ), (Gericht × Typ). Fällt als Abfallprodukt der `erledigt`-Events an. Sekundärnutzen: Quoten als B2B-Marketing ("durchschnittlich X € pro gekürzter Abrechnung nachgesetzt") und als Grundlage datengestützter Klageentscheidungen.

---

## 3. Vorgangsautomat

### 3.1 Designprinzipien

1. **Automat pro Vorgang, nicht pro Akte.** Eine Akte hat n parallele Vorgänge (Sachschaden, SV-Honorar, Personenschaden, Kostenfestsetzung). Aktenstatus = Aggregation, nie gesetzt.
2. **Zustand ist gefaltet, nie gespeichert.** `zustand = fold(events, definition)`. Keine status-Spalte. Replay-fähig, debugbar. `definition_version` am Vorgang festgepinnt; laufende Vorgänge bleiben auf ihrer Version.
3. **Der Automat schreibt nie nach außen.** Aktionen erzeugen ausschließlich Entwürfe, Queue-Einträge, Fristen. Transitionen werden durch Freigabe-Events ausgelöst (human approval = einziger Write, bestehende Architekturentscheidung).
4. **LLM nie an der Transition.** Dokument → LLM-Klassifikation → Event-VORSCHLAG → Bestätigung im Review-UI → Event → Transition. Unbekanntes/Mehrdeutiges → Zustand `manuelle_pruefung` (fail-closed).

### 3.2 Timer als Events

- Aktion `frist_setzen(dauer, label)` → Eintrag in `frist`-Tabelle.
- Täglicher Scheduler emittiert `frist_abgelaufen(frist_id)` → normales Event für den Automaten UND materialisiert Queue-Eintrag (siehe 4.).
- Fristen sind sichtbar, stornierbar (Antwort-Event konsumiert Frist: `konsumiert_von_event_id`), auditierbar.
- **Abgrenzung:** Workflow-Wiedervorlagen. Notfristen/Verjährung bleiben ZUSÄTZLICH im RA-Micro-Fristenkalender. Bewusste Redundanz, kein Designfehler.

### 3.3 Scope-Entscheidung (wichtig)

**Vorgang `kuerzungswiderspruch` hat Scope = Abrechnungsschreiben, NICHT einzelne Kürzung.** Ein Widerspruchsschreiben antwortet auf alle Kürzungen einer Abrechnung. Kürzungen = Datensätze (Statistik einzeln), Vorgang = Bündel. Bei Teilzahlung: ReFa ordnet Zahlung den Kürzungen zu → `erledigt`-Events pro Kürzung, Vorgang läuft für Restpositionen in `klageentscheidung` weiter.

### 3.4 Verkettung statt Verschachtelung

Kleine Automaten, verkettet via `parent_vorgang_id`. `klage_beschlossen` spawnt Vorgang Typ `klage`. Vorgangstypen (je eigene YAML-Definition):
- `erstregulierung` (Anspruchsschreiben → Frist → Abrechnung eingegangen → spawnt ggf. `kuerzungswiderspruch`)
- `kuerzungswiderspruch` (Referenzdefinition unten)
- `klage` (Entwurf → eingereicht → Termin → Urteil/Vergleich → spawnt `kostenfestsetzung`)
- `sv_honorar`
- `kostenfestsetzung`
- `personenschaden` (nur Fristen/Queues, kein Baustein-Pfad)

### 3.5 Referenzdefinition

```yaml
# vorgangstypen/kuerzungswiderspruch.yaml
id: kuerzungswiderspruch
version: 1
scope: abrechnungsschreiben
zustaende:
  - erkannt
  - entwurf_bereit          # Eintrittsaktion: stellungnahme_generieren -> Queue
  - versandt                # Eintritt via freigabe_erteilt; Aktion: frist_setzen(21d, 'antwort_versicherer')
  - antwort_pruefen
  - klageentscheidung       # Eintrittsaktion: kostenrisiko + statistik aufbereiten -> Anwalts-Queue
  - manuelle_pruefung       # Auffangzustand (fail-closed)
  - erledigt                # terminal; Events tragen ergebnis + betrag pro kuerzung
transitionen:
  - { von: erkannt,           event: klassifikation_bestaetigt, nach: entwurf_bereit }
  - { von: entwurf_bereit,    event: freigabe_erteilt,          nach: versandt }
  - { von: versandt,          event: zahlung_zugeordnet,        nach: antwort_pruefen }
  - { von: versandt,          event: ablehnung_bestaetigt,      nach: antwort_pruefen }
  - { von: versandt,          event: frist_abgelaufen,          nach: klageentscheidung }
  - { von: antwort_pruefen,   event: vollzahlung_bestaetigt,    nach: erledigt }
  - { von: antwort_pruefen,   event: restforderung_bestaetigt,  nach: klageentscheidung }
  - { von: klageentscheidung, event: klage_beschlossen,         nach: erledigt }   # spawnt Vorgang 'klage'
  - { von: klageentscheidung, event: verzicht_beschlossen,      nach: erledigt }
  - { von: "*",               event: eskalation,                nach: manuelle_pruefung }
```

Hinweis UI: `klassifikation_bestaetigt` und `freigabe_erteilt` bleiben im Modell getrennt, werden im Ein-Pass-Modus aber durch EINE Handlung (Freigabe-Klick) gemeinsam ausgelöst.

### 3.6 Schema Vorgang/Frist

```sql
CREATE TABLE vorgang (
  id INTEGER PRIMARY KEY,
  akte_id INTEGER NOT NULL,
  typ TEXT NOT NULL,
  definition_version INTEGER NOT NULL,
  scope_table TEXT, scope_id INTEGER,
  parent_vorgang_id INTEGER,
  angelegt_am TEXT NOT NULL
);
CREATE TABLE frist (
  id INTEGER PRIMARY KEY,
  vorgang_id INTEGER NOT NULL REFERENCES vorgang(id),
  label TEXT NOT NULL,
  faellig_am TEXT NOT NULL,
  konsumiert_von_event_id INTEGER   -- NULL = offen
);
```

> **Hinweis 2026-07-11:** `akte_id INTEGER` ist falsch — Akten-PK ist `az TEXT` (seit Migration 5). Zur `frist`-Tabelle vs. bestehender `todos`-Infrastruktur siehe 10.3 Punkt 5.

Umfangsschätzung Kern: fold-Funktion + Tages-Scheduler + YAML-Loader ≈ 300–500 Zeilen Python. Der Kern ist bewusst langweilig.

---

## 4. ReviewQ als Actioncenter (zentrale Erkenntnis der Diskussion)

**Die ReviewQ ist die Oberfläche des Automaten.** Der Automat braucht kein eigenes Frontend. Alles Menschliche passiert in der Queue. Dadurch ist Erfassungsdisziplin kein Zusatzaufwand: Man kann ein Abrechnungsschreiben nicht beantworten, ohne dass die Kürzungsdaten entstehen. Statistik = Abfallprodukt des Workflows.

### 4.1 Zwei Quellen für Queue-Einträge

1. **Eingehende Dokumente** (Intake-Pipeline klassifiziert, Automat-Zustand verlangt menschliche Aktion).
2. **Ablaufende Fristen** (`frist_abgelaufen` materialisiert einen Task, z. B. Sachstandsanfrage/Mahnung/Klageentscheidungsvorlage — mit fertigem Entwurf). Fristen werden dadurch zugleich ActionItems.

Beide münden im selben Muster: **Kontext + vorgenerierter Entwurf + Freigabe.**

### 4.2 Der Bildschirm (Beispiel Abrechnungsschreiben)

- Links: Original-PDF.
- Rechts: extrahierte Daten — Kürzungszeilen (Typ, Position, Betrag, gematchter Baustein, Konfidenz), Prüfdienstleister, Zahlbetrag. Zeilen editierbar (Typ ändern, hinzufügen, streichen).
- Darunter: **spekulativ vorgenerierter Stellungnahme-Entwurf** (Generierung lokal, kostet nichts). Bei Korrektur einer Kürzungszeile → Entwurf regeneriert.
- Aktionen: bearbeiten / freigeben / eskalieren. Freigabe → Event → Transition (`versandt`, Frist läuft).

### 4.3 Persistenz-Semantik (Klarstellung)

Queue-Einträge sind **persistent** (überleben Neustarts, warten auf Bearbeitung), aber ihr **Lebenszyklus ist event-getrieben**: Sie entstehen durch Events und verschwinden durch Events — NIE durch manuelles Abhaken. Kein eigener Queue-Status ("in Bearbeitung"/"erledigt" als Flags) → sonst zweiter Zustandsspeicher neben den Events, der auseinanderläuft. Zurückstellen = Event `zurueckgestellt_bis`, kein Flag. Implementierung wahlweise als materialisierte Tabelle (deren Zeilen ausschließlich von Event-Handlern geschrieben/gelöscht werden) oder als View über gefaltete Zustände + offene Fristen — Entscheidung in der Session anhand Performance/Codebasis. *(Vorab-Befund → 10.2 Frage 2: spricht für materialisierte Tabelle.)*

### 4.4 Diff als Trainingssignal

Beim Freigabe-Event speichern: Diff zwischen generiertem Entwurf und versandter Fassung. Auswertung nach Monaten: Bausteine, die unverändert durchgehen (gut) / immer editiert werden (überarbeiten) / Typen mit häufiger Fehlklassifikation (Erkennungsregeln nachschärfen). Feedback-Loop ohne Zusatzarbeit.

### 4.5 Offene Rollenfrage

Ein-Pass-Modus (Andi macht Extraktions-Review + Freigabe in einem Durchgang) vs. Zwei-Stufen (ReFa bestätigt Daten/Zahlungszuordnung, Anwalt sieht nur freigabefertige Entwürfe). Beides mit demselben Modell abbildbar. Ein-Pass ist für den Start schneller, skaliert aber nicht (Bus-Faktor im Kleinen). UI so bauen, dass beide Modi möglich sind; Start: Ein-Pass.

---

## 5. Textbaustein-Migration

- Bausteine liegen als Word vor; **Markdown-Konvertierung bereits begonnen** (Stand Juli 2026).
- Pro Baustein: Typ-ID vergeben, Erkennungs-Keywords extrahieren (stehen implizit im Baustein), Parametrisierung (Beträge, Positionen, Versicherer, Fahrzeugdaten als Platzhalter).
- **Verifikations-Frischecheck:** Jeden zitierten Beleg einmal durch `urteil-verifikation`; `verifiziert_am` in Rechtsprechungstabelle. Veraltete Zitate VOR Automatisierung fangen.
- Migration weitgehend durch Claude Code aus den Markdown-Dateien, Andi als Reviewer.

---

## 6. Validierung vor Bau

**Handtest (ein Abend, vor jedem Code):** 30 echte Prüfberichte der letzten Monate manuell gegen die Bausteinsammlung klassifizieren. Fragen: Findet jede reale Kürzung ihren Baustein? Was fällt durch (Lücke vs. legitimer Langtail → manuelle_pruefung)? Bricht eine Konstellation das Scope-Modell (Nachbesichtigung, zweiter Prüfbericht zur selben Abrechnung, kommentarlose krumme Zahlung ohne zuordenbares Schreiben)?

**Offene Klassifikationsfrage:** Initial rein regelbasiert (Keywords gegen `begruendung_roh` — bei Prüfdienstleister-Templates vermutlich sehr treffsicher) mit LLM nur als Fallback? → In der Session anhand der 30 Testberichte entscheiden.

> **Hinweis 2026-07-11:** Der Handtest muss nicht bei null anfangen — Bestandsdaten liegen bereits geparst vor (`pruefberichte.kuerzungen_json`, `regulierung_positionen.kuerzung_freitext`). Siehe 10.4.

---

## 7. Bauphasen (Reihenfolge verbindlich)

**Phase 0 (vor Code):** Handtest 30 Prüfberichte. Baustein-Migration abschließen (läuft bereits). Verifikations-Frischecheck. **Zusätzlich (Befund 10.4): `urteil-verifikation` als Prüfprozess existiert noch nicht — muss als eigene Vorleistung von Phase 0 gebaut/definiert werden, sonst hängt die Rechtsprechungstabelle in der Luft.**

**Phase 1:** Codebasis-Prüfauftrag (Abschnitt 1, vorab beantwortet in Abschnitt 10) → Gap-Liste + Migrationsplan. Dann: Kürzungstyp-Erfassung + Typenregistry (A-Typen zuerst) + Klassifikation im bestehenden Review-UI. OHNE Automat. Liefert nach ~4 Wochen echte Daten; zeigt, ob Taxonomie trägt und Erfassung im Alltag durchgehalten wird. **Befund 10.5: Phase 1 ist voraussichtlich deutlich kleiner als hier angenommen — die Erfassungsstrecke (ReguWizard, `regulierung_positionen`, `kuerzungsarten` mit Textbausteinen) existiert; Kern ist Registry-Migration + `pruefdienstleister_id` + Typ-Achse, nicht Neubau.**

**Phase 2:** fold + `vorgang`/`frist` + Scheduler + EIN Vorgangstyp (`kuerzungswiderspruch`) + ReviewQ-Erweiterung (Entwurfs-Vorgenerierung, Freigabe, Frist-Tasks). **Befund 10.2/10.5: einzige echte strukturelle Baustelle ist die generische Action-Queue — die Intake-Queue ist dokumentgebunden.**

**Phase 3:** Weitere Vorgangstypen (erstregulierung, klage, sv_honorar, kostenfestsetzung, personenschaden). Statistik-Views. Diff-Auswertung.

**Abbruchkriterium:** Scheitert in Phase 1 die Erfassungsdisziplin, hat der Verzicht auf den Automaten nichts gekostet.

---

## 8. Ehrlichkeits-Vermerk (Epistemik der Vorschläge)

- Software-Patterns (Event Sourcing, FSM, Definition-als-Daten): etabliert, Konfidenz hoch.
- Konsistenz mit bestehender Architektur (Events primär, Status abgeleitet, human approval): folgt aus Andis eigenen Entscheidungen — Konfidenz bedingt, erbt deren Richtigkeit.
- Domänenannahmen (~30 Typen decken >95 %; Dienstleister-Achse trennt schärfer; Scope = Abrechnungsschreiben): plausible Hypothesen, KEIN Referenzprojekt bekannt. MyCase/Clio sind KEINE Vorbilder (Checklisten-Templates, keine Zustandsmaschine). Strukturell nächstes Vorbild: Versicherer-Schadensysteme (Guidewire-Muster), gespiegelt. → Validierung ausschließlich über Phase 0/1 mit eigenen Daten.

## 9. Bekannte Risiken

- **Betrieb > Bau:** System lebt von lückenloser Erfassung (jedes Schreiben, jede Zahlung, jede Erledigung). Architektur-über-Betrieb-Tendenz bewusst gegensteuern.
- **Bus-Faktor:** Dokumentation als Deliverable jeder Session; zweite Person für Deploy/Betrieb; Ein-Pass-Modus nicht als Dauerzustand.
- **Fehler-Skalierung:** Automatisierung macht aus einem schiefen Baustein-Zitat einen Serienfehler → Frischecheck + Re-Verifikations-Zyklus.
- **RVG-Ökonomie:** Automatisierung monetarisiert sich nur über Volumen; Zuführung bleibt der Engpass, nicht Bearbeitung.

---

## 10. Codebasis-Spiegelung (2026-07-11) — Vorab-Antworten auf den Prüfauftrag

> Befunde aus Abgleich mit Branch `intake-stufe1`, Schema 55, Stand nach P1.7 + N-07/N-08. Vor Baubeginn re-verifizieren — die Intake-Pipeline entwickelt sich parallel weiter (P1.5e, P1.8 ausstehend).

### 10.1 Fünf existierende Rohbauten (das Papier beschreibt teilweise Neubauten für Vorhandenes)

1. **Die Taxonomie existiert embryonal: Tabelle `kuerzungsarten`** (Migration 3, 19 Seeds; erweitert Mig 22). Felder: `kategorie` (4 Kategorien), `standard_gegenargument`, `rechtsgrundlagen` (Freitext!), `hinweis_intern`, `sv_stellungnahme_erforderlich`, `textbaustein` (briefreifer Gegenargument-Text). Seeds decken u. a. A01 (UPE), A04 (Stundenverrechnungssätze), C01 (Wertminderung) ab. Aufgabe ist **Migration 19 → ~30 Typen + Kategorien A–F + YAML-Registry**, nicht Neuerfindung. ⚠️ `kuerzungsart_id` steckt im UNIQUE-Constraint des Ereignismodells (`ereignis_positionen`, K-M1: `(ereignis_id, position_key, wirkung, COALESCE(kuerzungsart_id, 0))`) — Alt-IDs müssen stabil bleiben.
2. **Die `kuerzung`-Tabelle existiert zu ~70 %: `regulierung_positionen`.** `(abrechnungsschreiben_id, position_key, betrag_gefordert, betrag_reguliert, kuerzungsart_id, kuerzung_freitext, parser_erkannt, parser_konfidenz, fuer_klage_vorgemerkt, sv_stellungnahme_ausstehend)`. `kuerzung_freitext` **ist** `begruendung_roh`; `parser_erkannt`/`parser_konfidenz` ist die Klassifikations-Provenance. Fehlt: normalisierte `pruefdienstleister_id` (heute nur Freitext `pruefberichte.pruefdienstleister`, Mig 4) und die neue Typ-Achse.
3. **„Timer als Events" ist seit P1.6 gebaut.** APScheduler (cron täglich 03:15, `fristablauf_job`), `fristablauf_service.verarbeite_faellige_todos()` emittiert `fristablauf`-Ereignisse mit Idempotenz-Anker `todos.fristablauf_ereignis_id`, kopiert Positionsbezüge des auslösenden ausgehenden Ereignisses. Fehlt ggü. Papier: Storno-Semantik `konsumiert_von_event_id` und `vorgang_id` — **zwei Spalten auf `todos`, keine neue `frist`-Tabelle** (sonst drei Frist-Wahrheiten: RA-MICRO, todos, frist).
4. **Der fold existiert: `positionsstatus_service.leite_positionsstatus_ab()`.** Leitet pro Position Zustand (offen/gefordert/anerkannt/teilanerkannt/bestritten/erledigt) + Eskalationsstufe rein aus `position_ereignis_cache` ab; keine Status-Spalte; ersetzte Ereignisse fließen nie ein. Der Vorgangsautomat ist die Generalisierung per-Position → per-Bündel mit expliziter FSM. ⚠️ Dann existieren **zwei Faltungen aus demselben Ereignisstrom** und die Eskalationslogik doppelt (`eskalationsstufe` vs. Zustand `klageentscheidung`) — festlegen, wer führend ist.
5. **Der vorgenerierte Stellungnahme-Entwurf existiert als manueller Wizard: PRD-27 ReguWizard** + `stellungnahme_texte` (persistierte Gegenargumente je Akte/Position, Mig 40) + `stellungnahme_routes.generiere()` (schreibt seit P1.4 bereits `stellungnahme_generiert`-Ereignis + `dokumente`-Zeile). Weg zum Papier: Trigger umdrehen (Queue-Eintrag kommt mit fertigem Entwurf statt Anwalt öffnet Wizard). docxtpl-Strecke steht; nur Markdown-Baustein-Rendering wäre neu.

### 10.2 Antworten auf die 8 Prüffragen

| # | Frage | Befund (2026-07-11) |
|---|---|---|
| 1 | Event-Scope | `ereignisse` hat `akte_az` + `dokument_id` (+ `versand_bestaetigt_am`!), Positions-Scope via n:m `ereignis_positionen`. Kein generischer Scope. **Empfehlung: nullable `vorgang_id`-Spalte (additiv), NICHT `scope_table`/`scope_id`** — Polymorphie killt FK-Integrität und gefährdet den AST-Guard-Test (nur `ereignis_service.py` darf schreiben; dieser Guard ist ein Asset, unbedingt erhalten). Ziel „keine zweite Event-Tabelle" ist erreichbar. |
| 2 | Review-UI generisch? | **Nein.** `queue_status` ist Spalte auf `intake_dokumente` selbst (inkl. `worker_lease`, `versuch_zaehler`). Queue = die Dokumentzeile. Frist-Tasks ohne Dokument passen strukturell nicht hinein. → Echte Baustelle Phase 2; spricht für **materialisierte `action_queue`-Tabelle** (Zeilen ausschließlich von Event-Handlern geschrieben/gelöscht, Semantik aus 4.3) statt View-Union. Frontend (verschachtelte Queue, DetailView, Freigabe-Dialog) ist als Muster wiederverwendbar. |
| 3 | Abrechnungsschreiben | Existiert (inkl. `haftungsquote`, `haftungsart`, `quelle`, `wdm_importiert`, `gesamt_kuerzung`). Fehlt: `pruefdienstleister_id` normalisiert (Stammtabelle nötig; heute Freitext auf `pruefberichte`). Kürzungszeilen = `regulierung_positionen` (10.1.2). |
| 4 | Position referenzierbar? | **Modell-Konflikt im Papier:** Es gibt keine `schadensposition`-Zeilen mit stabiler `id` — Positionen sind `position_key`s aus `positionsarten.yaml`; `schadenpositionen` ist eine Breittabelle (1 Zeile/Akte). Kürzung muss auf `position_key` referenzieren, wie `ereignis_positionen` es tut. FK `schadensposition_id` aus 2.6 existiert so nicht. |
| 5 | Freigabe-Mechanik | S1.9: `INTAKE_REVIEW_PFLICHT`-Flag, output_adapter als einziger Schreibweg in Akten-Tabellen, E2E-Guard-Tests. P1.5e verdrahtet Freigabe → `ereignis_service.schreibe_ereignis()`. **Exakt das gesuchte Muster, wiederverwendbar.** |
| 6 | Word-Generator | docxtpl-Strecke steht (`word_service`, `gebuehren_word`, Stellungnahme-Generierung PRD-27). Parametrisiertes Rendering aus Markdown-Bausteinen wäre der neue Teil (Markdown → docxtpl-Kontext oder eigener Renderer). |
| 7 | Scheduler | **Ja**: APScheduler seit P1.6 (`fristablauf_job` täglich 03:15, `max_instances=1`, `coalesce=True`, manueller Admin-Trigger `/system/fristablauf/manual`). Neuer Job andockbar. |
| 8 | Schema-Stand | **55** (Mig 54: textquelle email_text; Mig 55: review_geoeffnet_am). ⚠️ Migration-Dev-Trap beachten (Flask-Reloader stempelt mid-Edit — Migration atomar in EINEM Edit schreiben, aktive Dev-DB ist Docker-Volume `dev-data`, nicht `backend/data/`). |

### 10.3 Zu klärende Spannungen (Entscheidungsbedarf vor Phase 1)

1. **Dritte-Parallelwelt-Gefahr (wichtigster Punkt).** Es laufen bereits zwei Repräsentationen parallel (Alt-Tabellen + Ereignismodell, bewusstes Doppelschreiben ohne Big-Bang). Eine neue `kuerzung`-Tabelle wäre die dritte. Optionen: **(a)** `regulierung_positionen` um `kuerzungstyp_id` + `klassifikation` erweitern; **(b)** Kürzung als Ereignis-Attribut modellieren — `ereignis_positionen` trägt das Tripel des Papiers bereits wortwörtlich (`position_key` × `kuerzungsart_id` × Betrag bei `wirkung='gekuerzt'`); **(c)** neue Tabelle mit Backfill. Tendenz aus dem Brainstorming: **(b)**, weil 2.6 das Ergebnis ohnehin aus Events ableiten will und die Statistik dann aus demselben Strom fällt wie alles andere. Entscheidung in Phase 1 anhand Handtest-Erkenntnissen.
2. **`betrag_ct INTEGER`** bricht das REAL-Euro-Muster der gesamten Codebasis. Konsequent bleiben oder Bruch explizit begründen — gemischt ist es eine Fehlerquelle.
3. **`kuerzungstyp_id TEXT ('A02')` vs. `kuerzungsarten.id INTEGER`:** Migrationspfad definieren. Alt-IDs stabil halten (UNIQUE-Constraint!), neue Codes als zusätzliche Spalte (`typ_code`) oder Registry-Mapping.
4. **Ereignistypen-Erweiterung:** Der Automat braucht neue Typen (`widerspruch_versandt`, `zahlung_zugeordnet`, `klage_beschlossen`, …). `ereignistypen.yaml` (11 Typen) hat Fail-Loud-Loader + Konsistenzchecks — Erweiterungsmechanismus existiert, append-only-kompatibel.
5. **Frist-Tabelle:** `frist` aus 3.6 überschneidet sich mit `todos` (quelle='system', `faellig_am`, `fristablauf_ereignis_id`). Empfehlung: `todos` um `vorgang_id` + `konsumiert_von_event_id` erweitern statt Paralleltabelle.
6. **`vorgang.akte_id INTEGER`** → muss `akte_az TEXT REFERENCES unfallakte(az)` heißen (Migration 5).

### 10.4 Ergänzungen aus dem Brainstorming 2026-07-11

- **Handtest bootstrappen:** `pruefberichte.kuerzungen_json` + `regulierung_positionen.kuerzung_freitext` liegen für den Bestand geparst vor. Der Handtest kann als „Bestandsdaten gegen Bausteinsammlung matchen" laufen — beantwortet zugleich die Regelbasiert-vs-LLM-Frage (Abschnitt 6) empirisch.
- **Template-Wechsel-Erkennung** (2.3): billig als Ähnlichkeits-Hash über `begruendung_roh` je (Prüfdienstleister × Typ) — Freitext wird bereits gespeichert.
- **`urteil-verifikation` existiert nicht** (weder als Skill noch als Prozess im Repo) — eigene Vorleistung von Phase 0, sonst hängt die Rechtsprechungstabelle in der Luft. Normalisierung der heutigen Freitext-`rechtsgrundlagen` aus `kuerzungsarten` ist Teil davon.
- **`ereignisse.versand_bestaetigt_am`** existiert bereits — der Übergang `entwurf_bereit → versandt` hat einen Schema-Anker.
- **Personenschaden (F):** konsistent mit Bestand (`personenschaden`-Tabelle + Fristen existieren); `baustein_pfad: false` passt.
- **UI-Stil-Referenz für die ReviewQ (Abschnitt 4.2):** `mockups/P1_7_positions_dashboard.html` (P1.7-Mockup, 2026-07-09; Stand 2026-07-12 untracked — ggf. committen). Die dort etablierte visuelle Sprache (Zustand-Chips, AbleitungBadge als Wissensgrenzen-Muster, Kebab-Aktionsmenü aus der Type-Action-Matrix, Farben aus `frontend/src/config/theme.js`) und die daraus gebauten Komponenten (`PositionsDashboard.jsx`, `AbleitungBadge.jsx`, `DokumentAktionsmenue.jsx`) direkt wiederverwenden statt eigene Bausteine zu erfinden.

### 10.5 Revidierte Umfangseinschätzung

- **Phase 1 ist deutlich kleiner als im Papier angenommen:** Die Erfassungsstrecke existiert (ReguWizard → `regulierung_positionen` → seit P1.5a auch `abrechnung_eingegangen`-Ereignisse). Kern: Registry-Migration `kuerzungsarten` → A–F-Taxonomie, `pruefdienstleister`-Stammtabelle + FK, Typ-Zuordnung im ReguWizard/Review-UI schärfen, `begruendung_roh` verpflichtend machen.
- **Phase 2 hat genau eine echte strukturelle Baustelle:** die generische, materialisierte Action-Queue (Intake-Queue ist dokumentgebunden). fold/Scheduler/Freigabe/Ereignis-Schreibweg existieren als Muster und werden generalisiert, nicht neu gebaut.
- **Härteste offene Designfrage:** Verhältnis der zwei Faltungen (Positionszustand vs. Vorgangszustand) und Ort der Kürzungsdaten (10.3 Punkt 1). Beides vor Phase-1-Code entscheiden.

---

## 11. Konsolidierung (2026-07-23)

> Entstanden aus einem Brainstorming zu TODO-Punkt „Standardtexte pflegbar" (V11/Paket 4 der Klage-Wizard-Runde). Kernergebnis der Session: RA Schatz' eigentliche Vision (Kürzungen aus dem Abrechnungsschreiben erfassen, Gegenargument-Textbausteine vorschlagen, Anwalt prüft/wählt in einer Maske an/ab, editiert bei Bedarf — gemeinsam für Klage UND Stellungnahme) entspricht nicht Punkt 4, sondern **Phase 1 dieses Papiers**. Punkt 4 bleibt daneben bestehen (siehe 11.4). Es wurde noch nicht weiter designt — nächste Session setzt hier an.

### 11.1 Blocker-Bedingung neu geprüft: Intake-Pipeline-Stabilität

Vorbedingung aus Kopfzeile/Abschnitt 3 der Doku ("NICHT umsetzen, bevor die Intake-Pipeline vollständig fertig und stabil ist") laut `docs/TODO.md`/`docs/STATE.md`-Stand 2026-07-23 im Wesentlichen **erfüllt**:

- P1.1–P1.7, P1.5e, BUG-01–30, N-01–N-04, PDF-Splitting/PRD-37 alle ✅ (TODO „Erledigt"-Index).
- N-05 (Yielding/Teilergebnisse) und P1.8 (Backfill) sind **bewusst zurückgestellt** (kein offener Blocker, sondern Entscheidung — Begründung in `docs/DECISIONS.md`), keine offenen Baustellen in „In Arbeit".
- Schema jetzt **v63** (Doku-Stand war v55) — vor Phase-0-Start Re-Verifikation der Abschnitt-10-Befunde gegen aktuellen Code nötig (dort bereits als Vorgehen vorgesehen), insb. Migrationen 56–63 auf neue Spalten/Tabellen prüfen, die die Prüffragen berühren könnten (u. a. Migration 62 `firmen_vertreter`, Migration 63 `beteiligte.vertreter_*`-Nachzug — beide vermutlich ohne Bezug zur Kürzungstaxonomie, aber nicht mitgeprüft).
- Prod-Rollout `intake-stufe1` selbst ist weiterhin *lokal* fertig, aber bewusst nicht deployed (kein Prod-Host) — betrifft nur Deployment, nicht die Code-/Datenmodell-Reife, die dieses Papier voraussetzt.

**Einschätzung:** Der Handtest (Abschnitt 6/7, Phase 0) kann aus Sicht der Pipeline-Reife grundsätzlich angesetzt werden, sobald die nächste Session das oben genannte Re-Verifikations-Delta (v55→v63) durchgeführt hat.

### 11.2 Matching-Befund bestätigt (nicht mehr nur Hypothese)

Abschnitt 10.1.2 vermerkt `parser_erkannt`/`parser_konfidenz` als „Klassifikations-Provenance" — heutige Recherche stellt klar, dass dahinter **keine Klassifikationslogik** steckt: `kuerzungsart_id` wird ausschließlich manuell per Dropdown gesetzt (`frontend/src/sections/RegulierungSection.jsx`, Auswahlfeld `pos.kuerzungsart_id`). Backend enthält keinerlei Keyword-/Regex-/LLM-Matching von `kuerzung_freitext`/`begruendung_roh` gegen `kuerzungsarten`. Das bestätigt exakt die in Abschnitt 6 als „offen" markierte Klassifikationsfrage als tatsächlichen Ist-Zustand **null**, nicht nur unklar — Phase 1 muss dieses Matching komplett neu bauen, es gibt keinen Teil-Automatismus, der wiederverwendet werden könnte.

### 11.3 PRD-39 in `docs/TODO.md` ist ein Karteileichen-Duplikat

`docs/TODO.md` führt „PRD-39 – Stellungnahme zum Abrechnungsschreiben (DOCX)" weiterhin als offenen Backlog-Punkt („Mittel"-Priorität, Anknüpfung PRD-27 ReguWizard). Laut Abschnitt 10.1.5 dieses Papiers existiert das Backend dafür bereits vollständig (`stellungnahme_routes.py`, `stellungnahme_service.py`, `stellungnahme_texte`-Tabelle Migration 40, produktiv seit PRD-27). Heutige Recherche bestätigt: 4 aktive Routen, voller DOCX-Generator, keine Lücke außer der im Papier ohnehin vorgesehenen Trigger-Umkehr (Queue liefert fertigen Entwurf statt Anwalt öffnet manuell). **Empfehlung für die nächste Session:** `docs/TODO.md`-Eintrag PRD-39 entweder streichen oder auf „bereits durch PRD-27 abgedeckt, nur Trigger-Umkehr über ReviewQ (Phase 2) offen" umschreiben, um keine doppelte Planung/Umsetzung anzustoßen.

### 11.4 Verhältnis zu Paket 4 „Standardtexte pflegbar" (V11)

Eigene, bereits freigegebene Design-Spec: `docs/superpowers/specs/2026-07-19-klage-wizard-standardtexte-design.md`. Deckt die **festen Klage-Rahmensätze** in `klage_service.py` ab (Kategorie A/B/C, ~56 Bausteine, u. a. „Die Beklagte"-Grammatikfix als Nebenbefund) — bewusst orthogonal zur Kürzungstaxonomie: feste Struktursätze vs. fallabhängig ausgewählte Gegenargumente. Die V11-Spec grenzt Kürzungsart-Textbausteine explizit aus („bereits pflegbar") — diese Annahme ist nach heutigem Stand **nicht korrekt** (siehe 11.2 und unten), berührt aber nicht deren eigentlichen Scope.

Zusätzlicher Befund von heute, relevant für die **Baustein-Migration (Abschnitt 5)** dieses Papiers: Das heutige `KuerzungskatalogView.jsx` dokumentiert die vom Backend beim Rendern unterstützte Platzhalter-Syntax nirgends (`<PLATZHALTER>`-Werte wie `SCHMGELD`/`GUTACHTER`, RA-Micro-Grammatik-Makros `<@xxx>`, `&&*`-Maskenzeilen, `??`→`[FEHLT]`) — wer einen Textbaustein pflegt, hat keine UI-Hilfe. Die in Migration 22 versprochene Fallback-Kette „textbaustein → standard_gegenargument → Default-Text" ist nur zu zwei Dritteln umgesetzt (kein serverseitiger Default, nur clientseitig in `KlageWizard.jsx`; bei zwei leeren Feldern entsteht stillschweigend kein Textblock). Kein einziger der 19 Seed-Einträge hat je einen `textbaustein` befüllt bekommen. **⚠️ Korrektur 2026-07-23 (Session 2): Beide Sätze sind so nicht haltbar — der Textbaustein-Befund ist falsch (aktive Dev-DB: 14/19 befüllt), die Fallback-Kritik gilt nur für den Klage-Pfad, der Stellungnahme-Pfad hat einen Server-Default. Details und Belege → Abschnitt 12.1.** Diese Punkte sollten in die Baustein-Migration (Abschnitt 5) einfließen, wenn die ~30 A–F-Typen angelegt werden — nicht als Neubau, sondern als Teil derselben Migration.

**Für die nächste Session:** Beide Vorhaben nutzen dasselbe Muster (Platzhalter-Einfügehilfe, Registry+Override, Live-Vorschau — siehe V11-Spec „Einstellungs-UI"). Empfehlung: Reihenfolge bewusst festlegen statt beide unabhängig zu designen — z. B. Editor-/Einfügehilfe-Komponente einmal (im Rahmen von Phase 1 der Kürzungstaxonomie oder im Rahmen von V11, je nachdem was zuerst drankommt) bauen und für das jeweils andere Vorhaben wiederverwenden, statt zweier Paralleleditoren. **→ Entschieden 2026-07-23: Phase 1 zuerst, V11 erbt den Editor (docs/DECISIONS.md).**

---

## 12. Verifikation & Prozess-Revision (2026-07-23, Session 2)

> Anlass: Kritik-Session zum Workflow dieses Papiers. Alle Codebasis-Aussagen dieses Abschnitts geprüft am 2026-07-23 gegen `main`, Schema 63, **aktive Docker-DB `dev-data`** (`/app/data/unfallakten.db` im Container `unfallakten-backend-dev`). Getroffene Entscheidungen → `docs/DECISIONS.md` (drei Einträge vom 2026-07-23); handelbare Punkte → `docs/TODO.md`.

### 12.1 Korrekturen an Abschnitt 11

1. **11.4-Befund „kein einziger Seed-Eintrag hat `textbaustein`" ist FALSCH.** Aktive Dev-DB: **14 von 19 befüllt** (Import via `tools/import_textbausteine.py`, April 2026). Leer sind nur 11/14/15/18/19; davon sind 11, 14, 18, 19 laut Import-Mapping *bewusst* ohne Baustein — einzig die Unkostenpauschale (15) war zugeordnet und ist trotzdem leer (klären). Mutmaßliche Fehlerquelle: Prüfung gegen die falsche DB (`backend/data/` statt Docker-Volume). **Neue Prüfregel: Jede Codebasis-Behauptung in diesem Papier nennt künftig Datum, Schema-Version und WELCHE Datenbank geprüft wurde.**
2. **Fallback-Ketten-Kritik gilt nur für den Klage-Pfad.** Stellungnahme-Pfad hat serverseitigen Default („Die Kürzung ist nicht gerechtfertigt.", `backend/word/stellungnahme_service.py:290–294`, ebenso Vorschau-Route). Im Klage-Pfad blieb bei leeren Feldern die Überschrift samt Betragsatz stehen, aber die Argumentation fehlte stillschweigend (`frontend/src/sections/KlageWizard.jsx`, `EinwaendeAuswahl.uebernehmen()`). **Behoben 2026-07-23:** sichtbarer `[FEHLT: Kein Textbaustein zur Kürzungsart „…" hinterlegt]`-Marker (folgt der `??`→`[FEHLT]`-Konvention des Klage-Pfads), abgesichert durch 3 Vitest-Tests (`KlageWizard.einwaende-fehlt.test.jsx`).
3. **Bestätigt bleiben:** kein automatisches Kürzungs-Matching im Backend (`kuerzungsart_id` nur manuell, `RegulierungSection.jsx`); keine Platzhalter-Hilfe im `KuerzungskatalogView.jsx` (Verarbeitung nur backendseitig: `stellungnahme_service.ersetze_platzhalter()`, `klage_routes._bereite_textbaustein_vor()`); PRD-39-Backend existiert vollständig (4 Routen in `stellungnahme_routes.py`, DOCX-Generator, Migration 40).

### 12.2 Migrations-Delta v55→v63: unkritisch

Migrationen 56–63 (in `backend/db/schema_manager.py`) berühren **keine** der taxonomie-relevanten Tabellen (`kuerzungsarten`, `regulierung_positionen`, `abrechnungsschreiben`, `pruefberichte`, `ereignisse`, `ereignis_positionen`, `todos`, `stellungnahme_texte`, `schadenpositionen`) — nur `intake_dokumente`-Metadaten (56–59), `dokumente.bezeichnung` (59), Schema-Drift-Fixes (60, 63) und neue Tabellen `klage_entwurf` (61) / `firmen_vertreter` (62). **Die Abschnitt-10-Befunde bleiben datenmodellseitig gültig.**

### 12.3 Bausteinsammlung: Ist-Zustand statt „Markdown-Konvertierung"

Eine Markdown-Konvertierung existiert nicht und ist nicht nötig. Real: **34 RTF/DOC-Quelldateien** in `tools/textbausteine/` (RA-MICRO-Exporte), Import-Werkzeug `tools/import_textbausteine.py` mit Datei→Kürzungsart-Mapping. **~18 Quelldateien sind noch keinem Typ zugeordnet** (u. a. Abschleppgebühren, JVEG, Reparaturbestätigung, HWS/Heilverlauf, Wertminderung-Steuer) — das ist das Rohmaterial für den Ausbau 19 → ~30 A–F-Typen. „Baustein-Migration" (Abschnitt 5) heißt also: **Zuordnung + Parametrisierung**, kein Formatprojekt. Urteilscheck für den Bestand entfällt (handverifiziert, → DECISIONS.md); bei der Registry-Migration `verifiziert_am` = „handgeprüft Juli 2026" stempeln.

### 12.4 RA-MICRO-Aktenkonto: abschließend NEGATIV geprüft

Idee aus der Session (Zahlungs-Realität aus dem Aktenkonto lesen) ist mit dem vorhandenen Zugang **nicht baubar**: Katalogabfrage 2026-07-23 über `ramicro/connector.py` (read-only) — keine der Datenbanken auf dem Server (`RAMICRO`, `RAMICRO_buk`, `RAKOLLSQL`, `RAMICRO_mus`, `RAMICRO_ttt`, `raKalender`, `raEloakte`) enthält Aktenkonto-/Buchungs-/Zahlungseingangsdaten. `tblKosten`/`tblKostenDetails` sind Kosten-/Honorarerfassung (Tätigkeits-/Honorarschlüssel, Rechnungsnummer), keine Geldeingänge. Ersatzlösung (→ DECISIONS.md): Prüf-Frist „Zahlungseingang kontrollieren" nach angekündigter Zahlung, manuelle Bestätigung. Der frühere Plan-Punkt „Aktenkonto-Plausibilitätshinweis" (POSITIONSMODELL-PLAN Abschnitt 7, Stufe P2) ist damit ebenfalls hinfällig, sofern kein anderer Datenzugang entsteht.

### 12.5 Kern-Befund: Die Differenz-Mathematik existiert bereits im Ereignismodell

Die Tabelle `abrechnungsschreiben` hat **keine** Versionierung (mehrere Schreiben pro Akte, geordnet nur `ORDER BY datum, id`; keine `ersetzt_durch`/`version`-Spalten; keine Nachzahlungs-Vergleichslogik). Die eigentliche Versionierung liegt im Ereignismodell (Migration 51): `abrechnung_eingegangen`-Ereignisse mit positionsscharfen Beträgen; `_regulierungs_wirkungen()` (`backend/services/eingehende_ereignisse.py:53–127`) berechnet **bereits heute** pro Position: reguliert>0 → `anerkannt`; Differenz mit Kürzungsart → `gekuerzt` (Differenzbetrag!); reguliert=0 mit Kürzungsart → `abgelehnt`. Ersetzung via `ersetzt_durch` auf Kopf UND Position. **Das Tripel (Position × Typ × Betrag) aus 2.6 liegt damit wortwörtlich im Ereignisstrom — starkes Argument für Option (b) aus 10.3.1** (Kürzung als Ereignis-Attribut, keine dritte Parallelwelt). Was fehlt: der Runde-1↔Runde-2-Vergleich (Nachzahlung erkennen = Differenz der `gekuerzt`-Beträge zweier Abrechnungen derselben Akte pro position_key × Typ) — nirgends implementiert, wird Kern von Phase 1/2. Geldbeträge durchgängig REAL Euro → `betrag_ct` aus 2.6 ist endgültig verworfen.

### 12.6 Revidierter Prozess (verbindlich, ersetzt Abschnitt 7 in Details)

- **Phase 0:** Handtest **maschinell** über den Bestand (`pruefberichte.kuerzungen_json` + `regulierung_positionen.kuerzung_freitext` gegen Bausteinsammlung), 30 manuelle Fälle nur als Stichproben-Tiefenprüfung. Messgrößen = dieselben wie später im Betrieb: **Trefferquote** (Typ-Vorschlag korrekt) und **Abdeckung** (Kürzung findet Baustein). Dazu: Zuordnung der ~18 restlichen Quelldateien; Unkostenpauschale-Lücke klären; `mockups/` committen.
- **Entscheidungs-Tor vor Phase 1 (NEU):** Ort der Kürzungsdaten (10.3.1, Tendenz (b) durch 12.5 gestärkt) und Verhältnis der zwei Faltungen (10.5) werden als eigene Architektur-Entscheidung in `docs/DECISIONS.md` festgehalten, BEVOR Phase-1-Code entsteht — nicht „nebenbei in der Session".
- **Phase 1 = Workflow RA Schatz:** Abrechnungsschreiben → Zahlbeträge pro Position parsen → Kürzung = Differenz (Prüfberichte beziffern Abzüge einzeln → Typ-Ebene erreichbar) → Begründung lesen, Typ flaggen (Matching muss komplett neu gebaut werden, vgl. 11.2) → Flag steuert Baustein-Vorauswahl in Stellungnahme UND Klage-Wizard. Gleicher Bildschirm für RA und ReFa. Jede Kürzung führt ihren Betrag als Pflichtangabe. Technische Reparaturweg-Einwände als Sammel-Kürzung, wenn kein eigener Baustein. Editor-Komponente entsteht hier (V11 erbt). Messlatte nach ~4 Wochen: Trefferquote/Abdeckung (Zielwerte nach Handtest festlegen) — ersetzt das alte Abbruchkriterium „Erfassungsdisziplin".
- **Zahlungs-Sonderfälle:** dreistufige Kaskade (eindeutiges Betrags-Matching → Anfrage an Versicherer mit Entwurf+Frist → protokollierte Not-Zuordnung), Details → DECISIONS.md.
- **Phase 2/3:** unverändert wie Abschnitt 7 (Automat, generische Action-Queue, weitere Vorgangstypen).
