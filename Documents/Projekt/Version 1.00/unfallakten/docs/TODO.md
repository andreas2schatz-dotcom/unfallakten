# TODO – Unfallakten-Verwaltungssystem

> Schlanke Arbeitsliste — nur Zukunftsgerichtetes. Zuletzt gestrafft: 2026-07-20.
> Erledigtes mit Protokoll → `docs/CHANGELOG.md` · Entscheidungen mit Begründung → `docs/DECISIONS.md` · Deploy/Betrieb → `docs/STATE.md`.

---

## 🔄 In Arbeit

### Klage-Wizard-Verbesserungsrunde (4 Pakete, Designs freigegeben 2026-07-19)
Empfohlene Reihenfolge 1→2→3→4 (3+4 teilen sich den Textaufbau-Umbau/V11 — bei der Planung abstimmen). Je Paket vor Umsetzung `superpowers:writing-plans` auf die Spec.

1. **Entwurf speichern** — ✅ umgesetzt + in `main` (2026-07-19). Detail → CHANGELOG.
2. **UI-Führung** — ✅ KOMPLETT (Browser-Nachtest bestanden 2026-07-23: Status-Symbole, Schließen-Dialog, Vertreter-Lookup im Wizard). In `main`, gepusht. Detail → CHANGELOG.
3. **Gesamtvorschau** — ✅ KOMPLETT (Browser-E2E bestanden 2026-07-23: Vorschau → Sachverhalt-Edit → Übernehmen → DOCX mit geändertem Text). In `main`, gepusht. Spec: `docs/superpowers/specs/2026-07-19-klage-wizard-gesamtvorschau-design.md`.
4. **Standardtexte pflegbar (V11)** — ✅ Stufe 1 umgesetzt (Branch `standardtexte-v11`). Detail → CHANGELOG.

### Aktenanlage aus der ReviewQueue (PRD-NEW) — umgesetzt (Branch `aktenanlage`, 26 Commits, NICHT gemergt), Abnahme steht aus
12 Tasks + Final-Review-Fixwellen komplett (Migration 66, OMA-XML-Generator, RA-MICRO-Erkennung read-only, `/aktenanlage`-Blueprint, Freigabe-Hook mit Gruppen-Schließregel, `AktenanlageDialog` ersetzt `NeueAkteModal`, ReviewQueue-Banner/Chip/Leiste). 50 neue Backend-Tests grün (Vollsuite-Rot = vorbestehender Alt-Cluster, identisch auf `main` — Abgleich 2026-07-30), Frontend 406/406 grün. Dev-Container laufen auf dem Branch — die App zeigt das Feature bereits. Spec `docs/superpowers/specs/2026-07-30-aktenanlage-design.md` · Plan `docs/superpowers/plans/2026-07-30-aktenanlage.md`. Detail → CHANGELOG, Deploy-Hinweise → STATE Abschnitt 0. **Nach bestandener Abnahme: Merge in `main`.**
**Offen — manueller Abnahmetest RA Schatz am echten System (Spec Abschnitt 9):**
- Adressnummer-Referenz: Kann „Bekannt = Ja" (+ Adressnummer) in der OMA-XML eine bestehende RA-MICRO-Adresse referenzieren (keine Dublette)?
- Konkreter `OMA_EXPORT_HOST_PFAD` (überwachter Windows-Share) muss von RA Schatz benannt und in `.env` eingetragen werden, dann `docker compose up -d --force-recreate backend`.
- Options-Labels/Datumsformat: `FRAU`/`FIRMA` als Anrede-Werte + ISO-Datum kommen beim RA-MICRO-Import korrekt an, inkl. Prüfung der `dtAnlage`-Spalte beim ersten echten Import.
- Abnahme-Szenario Geschwister: Gutachten auf erkanntes AZ freigeben, dann Rechnung/Body öffnen — AZ muss vorausgewählt bleiben (kein Zurückspringen auf leer).

### Dashboard-Hell-Umbau — umgesetzt (Branch `dashboard-hell`, basiert auf `aktenanlage`), Browser-Abnahme RA Schatz offen
Tagesübersicht hell (Pergament-Tokens), Jetzt-dran-Leiste, Fristen links oben (3:2),
Posteingang-Kachel entfernt, Lade/Fehler/Leer-Zustände je Kachel, Einträge als Buttons
(Tastatur), SB-Filter persistiert (`dashboard.aktiveSB`), leere SB-Auswahl = Hinweis.
Spec + Mockup: `docs/superpowers/specs/2026-07-30-dashboard-hell-*`.
**Playwright-Browsertest 20/20 bestanden (2026-07-30, echte Dev-App):** helles Design + Hausschrift, alle Kacheln ohne Posteingang, SB-Persistenz über Reload, Fehlerblock statt falscher Entwarnung (Netzwerk-Abbruch simuliert) inkl. Erholung per „Erneut laden", Klick öffnet Akte. Skript: Session-Scratchpad `dashboard-e2e.js`.
**Merge-Reihenfolge: erst `aktenanlage` → `main`, dann dieser Branch.**
Offen danach (separat): Sidebar-Emoji-Icons App.jsx, SB-Klarnamen-Tooltips (Kürzel-Liste von RA Schatz nötig); totes pendingEmailId-Gerüst + ungenutzter nachrichtenNeu-Endpoint entfernen; A11y-Feinheiten (aria-pressed SB-Chips, role=alert Fehlerblock, aria-hidden Skeleton); type=button + Retry-Disable + Badge-Logik-Konsolidierung in boardUi.

### Kürzungstaxonomie — Phase 0 ✅ · Phase 1 ✅ · **in `main` gemergt + gepusht (2026-07-24, `febe6f06`)**
Alle 12 Tasks + Genus-Platzhalter-Nachtrag (Weg 2). Abnahme: Bausteine von RA Schatz gegengelesen ✅; Katalog-Editor, Wizard-Zitat, Genus-Formen, Speichern-Sperre per Playwright-E2E bestanden ✅ (2026-07-24). Protokoll → `docs/CHANGELOG.md`.
**Offen:**
- **Messung Zielwerte (~2026-08-20, nach ~4 Wochen Betrieb):** `docker exec unfallakten-backend-dev python /app/tools/kuerzungsmatching_report.py` — Zielwerte: Abdeckung ≥ 90 %, Trefferquote ≥ 75 %, Positionszuordnung ≥ 90 % (DECISIONS 2026-07-23). Baseline siehe CHANGELOG.
- **Fehlablage-Entscheidung RA Schatz (aus Phase 0):** Dok 41478 + 43429 aus Akten 971/25 / 980/25 löschen? (FEHLABLAGE-Vermerk gesetzt; 852/25 nur in RA-MICRO, 418/28 existiert nirgends.)
- **Runden-Kachel im echten Betrieb** sichten, sobald die erste Akte 2 Abrechnungsrunden hat (Test-Abdeckung vorhanden, echter Fall noch nicht).
Phase 2 (vorgemerkt): Trigger-Umkehr Stellungnahme (PRD-39), Zahlungs-Kaskade, Vorgangsautomat — Konzept `handover/KONZEPT-Kuerzungstaxonomie-Vorgangsautomat.md` Abschnitt 12.

---

## 📋 Backlog (nach Priorität)

### Kritisch / Bald
- **PRD-25c – Automatische Mandantenkommunikation:** `MandantenEmailDialog` nach Generierung von Forderungs-/Regulierungsschreiben; 3 Textbausteine je Trigger, neue Tabelle `mandanten_emails`. PRD: `handover/PRD-25c_Mandantenkommunikation.md`.

### Mittel
- **PRD-39 – Stellungnahme zum Abrechnungsschreiben (DOCX): bereits durch PRD-27 abgedeckt** (verifiziert 2026-07-23: 4 aktive Routen in `stellungnahme_routes.py`, voller DOCX-Generator, Tabelle `stellungnahme_texte`/Mig 40). Offen ist NUR die Trigger-Umkehr (Queue liefert fertigen Entwurf statt manuellem Wizard-Aufruf) — Teil von Phase 2 der Kürzungstaxonomie, kein eigenes Vorhaben.
- **Dokumentenklasse „Klagedrohung" mit `frist_datum` → Verzugs-Automatik im Klage-Wizard:** Fristsetzungs-Schreiben bekommen eigene Klasse + strukturiertes Fristdatum; Verzugseintritt-Vorbelegung = Tag nach Fristablauf. Zwei Befüllungswege (selbst erzeugte Schreiben stempeln die Frist exakt; importierte via Parser). `verzug_dokumente` um `frist_datum` erweitern; optional Kopplung an Fristen-System (PRD-25a). Berührt Intake + Generator — eigenes Vorhaben.
- **PRD-32 Phase 2 – Rechnungstypen Beleg-Mapping:** erkannte Typen automatisch der Schadenposition zuordnen (Standkosten→Standgeld usw.). Plan: `handover/PRD-32_Rechnungstypen_Parser.md`.
- **PRD-05 – Betrag-Abgleich nach Upload:** hochgeladene Rechnung gegen Schadenposition abgleichen.

### Später
- **PRD-01 – To-Do-System Vollausbau** (Aufgabenzuweisung, Fälligkeiten, Filterung).
- **PRD-06 – Parser Reparaturrechnung via LLM** (für nicht-Regex-parsbare Rechnungen).
- **PRD-07 – Workflow-Regeln + automatische To-Dos** (Regelmaschine bei Ereignissen).
- **PRD-21 Phase 3b/3c** – Batch-Klassifikation + Filter nach Dokumentenklasse (E-Akte).
- **PRD-04c – TF-IDF Classifier** (Ergänzung zum Regex-Dispatcher).
- **PRD-24b – Vollständiger 5-Step-Wizard** (Unfallhergang + Haftungsbegründung als eigene Steps).
- **PRD-25d – Intelligente Sachstandsanfrage.** Alter Plan (`handover/PRD-25d_Intelligente_Sachstandsanfrage.md`) basiert auf `aktenchronik_service.py` (Neubau) — veraltet, seit Pipeline-v7 gibt es das Ereignis-Modell (`ereignis_service.py`, Tabelle `ereignisse`/`ereignis_positionen`) als SSOT für den Aktenverlauf. Aktenchronik-Konzept wird nicht mehr verwendet. Vor Umsetzung: Plan auf Ereignis-Modell umstellen (eigenes Brainstorming).
- **Stakeholder-Portal (separates Projekt):** PORTAL-A1/B1/B2/B3 — je Plan in `handover/PORTAL-*.md`.

### UserStories (externes Review, offen)
- **PRD-US03 – SV-Portal Upload-Empfang (Kanzlei-Seite):** `POST /sv-portal/upload`, Audit-Tabelle `sv_portal_uploads`. **Braucht US04** (Gegenstelle).
- **PRD-US04 – SV-Portal-Server (Gegenstelle):** eigenständige Web-App, **nicht** im Unfallakten-Repo umsetzbar. Entspricht `handover/PORTAL-B2_SV_Cockpit.md`.

### Action-Board-Restposten (Verfeinerung)
- Fristen-Spalte zeigt nur RA-MICRO-Wiedervorlagen, keine „harten" Rechtsmittelfristen (falls RA-MICRO eine Fristen-Tabelle führt, Schritt 1 wiederholen).
- Nachrichten-Spalte: Mandantenportal-/SV-Portal-Nachrichten sind Placeholder; echte Integration hängt an PRD-25c.

---

## ⏸️ Zurückgestellt (bewusst, kein Handlungsbedarf)
- **Prod-Rollout intake-stufe1** (Nutzer 2026-07-15) → Runbook + Deploy-Reihenfolge in `docs/STATE.md`.
- **N-05** (Yielding/Teilergebnisse) und **P1.8** (Backfill, forward-only) → Begründung in `docs/DECISIONS.md`.
- **PRD-38** (Dokumentenbezeichnung per LLM) → Begründung in `docs/DECISIONS.md`.
- **V11 Stufe 2 — Kategorie C über vorflektierte Platzhalter** (RA Schatz, 2026-07-24): Aufwand/Ertrag passt aktuell nicht — die betroffenen ~24 Kategorie-C-Bausteine (Anträge, Aktivlegitimation, Sachverhalt-Kernsätze) sind grammatikalisch bereits korrekt hartcodiert (Genus/Numerus/Konjugation via `_get_kl_genus_vars`/`_beklagten_grammatik` in `klage_service.py`), unklar ob echter Änderungsbedarf besteht. Erst Live-Feedback aus dem Betrieb von Stufe 1 abwarten; bei konkretem Bedarf ggf. nur einzelne Bausteine gezielt freigeben statt volle Editor-Infrastruktur.
  Beim eventuellen Kickoff mitzunehmen (Abschluss-Review Stufe 1):
  - Verwaiste Overrides sichtbar machen (Startup-Warnung oder „verwaist"-Anzeige in GET /klage-standardtexte, Lösch-Option) — bei Key-Umbenennungen fällt Kanzlei-Text sonst stumm auf Standard zurück
  - Golden-Test: fehlende Golden-Datei muss FAILen statt still regenerieren (KLAGE_GOLDEN_UPDATE=1 als einziger Schreibweg)
  - Sync-Test Frontend-Fixture (standardtexteFixture.js) ↔ YAML-Registry (wortgleich, byte-genau)
  - Standardtexte-Refresh in offener KlageSection nach Override-Änderung in den Einstellungen (aktuell fetch-once pro Mount)

---

## 🚫 Verworfen (nicht durchführbar)
- **PRD-29 – Schmerzensgeld-Ermittlungstool** (RA Schatz, 2026-07-24): Als nicht durchführbar eingestuft — die Schmerzensgeld-Datenbank ist nicht per API ansprechbar. Plan lag unter `handover/PRD-29_Schmerzensgeld_Tool.md` (Recherche-Ansatz teils über Claude web_search, teils manueller Link zu schmerzensgeld.online ohne API).

---

## ❓ Unklar / zu klären
- **PRD-29 DKz-Filter — erledigt oder offen?** Handover sagt „implementiert" (via Schlagwort `E-Brief`, da DKz-Feld in DB fehlt), v56 sagt „nicht gestartet". Ist das ursprüngliche Ziel als erfüllt zu betrachten?

---

## ✅ Erledigt
> Kompakter Index. Vollständige Umsetzungs-Protokolle mit Commits/Tests: **`docs/CHANGELOG.md`**.

| Datum | Feature |
|---|---|
| 2026-07-30 | Dashboard-Hell-Umbau: Tagesübersicht hell (Pergament-Tokens), Jetzt-dran-Leiste, Fristen zuerst (3:2), Posteingang-Kachel entfernt, Zustände je Kachel, Tastatur, SB-Filter-Persistenz — Branch `dashboard-hell`, Browser-Abnahme offen, siehe „In Arbeit" |
| 2026-07-30 | Aktenanlage aus der ReviewQueue (PRD-NEW): Migration 66, OMA-XML-Generator, RA-MICRO-Erkennung read-only, `/aktenanlage`-Blueprint, Freigabe-Hook, `AktenanlageDialog` (ersetzt `NeueAkteModal`), ReviewQueue-Banner/Chip/Leiste, OMA-Export-Ordner in Compose/.env — Abnahme am echten System offen, siehe „In Arbeit" |
| 2026-07-29 | UI-Kleinkram-Runde (6 Punkte, gemeldet 2026-07-23): Systemstatus-Kachel-Bug war Caching-Problem (Nutzer bestätigt behoben); Navigationsleiste Icon-Ausrichtung + Hover-Effekt verstärkt; E-Mail-Identifier Versicherer/Gutachter zu einem Reiter mit Subreitern zusammengeführt (Muster Personenschaden/Sachschaden); Bestandsaufnahme Gutachter-Identifier (2: Ninnivaggi, Cassese); GLM-OCR-Karte im KI-Assistent-Reiter (Modellauswahl + Verbindungstest, analog Lokales-LLM-Switcher) |
| 2026-07-28 | Review-Queue: Sortier-Toggle Eingangsdatum (auf/ab, localStorage-Persistenz) — in `main`, Browser-Nachtest 11/11 bestanden |
| 2026-07-23 | Kürzungstaxonomie **Phase 1 komplett** (12 Tasks: Mig 64, YAML-Registry A–F, Matching+LLM, Verkettung, Typ-UI, Runden-Vergleich, TextbausteinEditor, ZITAT, Messanker) — Branch `kuerzungstaxonomie-phase1` |
| 2026-07-23 | Kürzungstaxonomie-Konzept verifiziert + Prozess revidiert (Papier Abschnitt 12, 3 DECISIONS-Einträge); Klage-Wizard-Fix [FEHLT]-Marker; Browser-Nachtests Paket 2+3 bestanden; main gepusht (58 Commits) |
| 2026-07-21 | Klage-Wizard Paket 3: Gesamtvorschau (Server-Text-Vorschau + Inline-Edit, Single-Source; lokal main, Browser-E2E offen) |
| 2026-07-21 | Globaler Firmen-Vertreter-Speicher (Tabelle `firmen_vertreter`, aktenübergreifende Vertreter-Zuordnung) |
| 2026-07-20 | Klage-Wizard Paket 2: UI-Führung (umgesetzt, noch nicht gemergt) |
| 2026-07-19 | Klage-Wizard Paket 1: Entwurf speichern (in main) |
| 2026-07-19 | PRD-33 Klage-Wizard Feintuning KOMPLETT (40 Bugs KW-01–40, S1–6) |
| 2026-07-16 | Rausch-Absender auto-aussortieren + Papierkorb |
| 2026-07-16 | Bugfix AZ-Normalisierung + Personenschaden-Schema-Drift (Mig 60) |
| 2026-07-15 | PRD-37 Dokumentenbezeichnung (Mig 59); PDF-Splitting Review (Mig 58); Prod-Rollout Git-Teil |
| 2026-07-14 | Fragebogen-Feld-Übernahme; N-03 Retry-Differenzierung (Mig 57); N-04 Seiten-Triage |
| 2026-07-13 | Bugfix-Reihe BUG-01–30 (Intake v7); N-01/N-02 (Mig 56)/N-06; N-09/N-10; Druckbutton |
| 2026-07-12 | P1.5e Review-Freigabe schreibt Ereignisse für alle Klassen |
| 2026-07-10 | P1.7 UI-Positionsmodell; Text-Pfad Intake (Mig 54); N-08 (Mig 55)/N-07 |
| 2026-07-09 | Intake-Refactoring S1.9 + Positionsmodell P1.1–P1.6 (Mig 49/51/52) |
| 2026-07-08 | Bugfixing-Session (Testsuite-Sanierung, Mig 50 unfalldetails) |
| bis 2026-07 | Ältere PRDs (PRD-01…PRD-36, US01/02/05/06, B-08/09 …) — Index in CHANGELOG.md |
