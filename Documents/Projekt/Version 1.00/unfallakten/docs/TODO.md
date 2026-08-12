# TODO – Unfallakten-Verwaltungssystem

> Schlanke Arbeitsliste — nur Zukunftsgerichtetes. Zuletzt gestrafft: 2026-08-12 (nach dem großen Merge).
> Erledigtes mit Protokoll → `docs/CHANGELOG.md` · Entscheidungen mit Begründung → `docs/DECISIONS.md` · Deploy/Betrieb → `docs/STATE.md`.

---

## 🔄 In Arbeit

### Produktiv-Nachtests nach dem großen Merge (seit 2026-08-11, RA Schatz)
Alles ist in `main` gemergt+gepusht (`cf7dd74d`); Entscheidung RA Schatz: Abnahmen erfolgen im laufenden Betrieb („die Randfälle kriege ich nur so mit"). Beim Arbeiten gezielt sichten, Auffälligkeiten melden:
- **Abschluss-/Sachstandsbericht:** DOCX in beiden Modi generieren und gegenlesen.
- **Entfernungsprüfung:** „📍 Entfernung prüfen"-Popup an 1280/25; dabei Positions-Tabelle im Review-Detail von Dok 517 sichten.
- **Intake-Pending-Badge:** Import in Testakte → „Review ausstehend" in der Dokumentenkachel → Link öffnet Dok in der ReviewQueue → Zeile verschwindet nach Freigabe.
- **SSOT-Klassen-Dropdown** in der ReviewQueue (22 Klassen) kurz sichten.
- **Übersicht-Redesign:** Sichtkontrolle; bewusste Eigenheiten: kurzes KPI-Umspringen beim Öffnen (Alt-Zahlen → Ereignismodell), HQ=0-Semantik (Header 0 € gefordert, Backend-DOCX rechnet bei HQ=0 mit 100 % — bekannte Inkonsistenz).
Zurückgestellte Minors je Modul: `bugfixes.md` + CHANGELOG-Einträge 2026-08-07/-11 (opportunistisch bei nächster Anfassung).

### Offene Entscheidungen RA Schatz
- **I-10 Haftungsquote (Forderungsschreiben):** Brief behauptet bei erfasster Teilhaftung weiterhin Alleinschuld und fordert ungekürzt; FE-Banner quotiert daneben. Braucht juristische Formulierung für den Teilhaftungs-Baustein (+ HQ=0-Konvention, vgl. Inkonsistenz Übersicht/DOCX).
- **Fehlablage (Kürzungstaxonomie Phase 0):** Dok 41478 + 43429 aus Akten 971/25 / 980/25 löschen? (FEHLABLAGE-Vermerk gesetzt; 852/25 nur in RA-MICRO, 418/28 existiert nirgends.)

### Aktenanlage aus der ReviewQueue (PRD-NEW) — ✅ gemergt + gepusht (2026-08-03, `main`=`81e33206`), Nachlauf offen
Feature live abgenommen: Prefill Mandant, OMA-XML **strukturgleich** zum echten RA-MICRO-Export, **Dateiname muss mit `Oma_` beginnen** (Watcher-Filter, case-sensitiv), Import wird erkannt. Behoben: stale-auftraggeber-Prefill + Anrede-Normalisierung, Migration-66-Reloader-Falle, OMA-Pfad (`Z:\RA\M-Plattform`) + Dateiname + XML-Struktur (keine leere `<Gegnerliste>`, `<tvm/>`). Prod-Compose nachgezogen. Detail → Memory `project_unfallakten_aktenanlage`.
**Offen (opportunistisch, kein Blocker):**
- Echter End-to-End-Create-Test beim **nächsten echten Neu-Mandanten**: Adress-Dublette Mandant (Punkt 4), Geschwister-Szenario (Punkt 5), `dtAnlage`-Prüfung. Mit Bestands-/Altakten nicht testbar (RA-MICRO-Test-Akten nicht löschbar).
- Beteiligten-Dublettencheck (DEKRA/Versicherung) — erst am echten Import verifizieren, ob RA-MICROs eigene OMA-Dublettenprüfung reicht.
- `beispieloma.xml` als **bereinigte** Test-Fixture committen (sonst skippt der Struktur-Guard-Test in CI); NICHT die echte Kundendatei (PII).
- Prod-Rollout: `oma-share`-Volume steht in `docker-compose.prod.yml`; bei non-root Gunicorn ggf. `uid`/`gid` anpassen.

### Dashboard-Hell — ✅ gemergt (2026-08-03), Nacharbeit offen
Feinschliff separat: Sidebar-Emoji-Icons App.jsx, SB-Klarnamen-Tooltips (Kürzel-Liste von RA Schatz nötig); totes `pendingEmailId`-Gerüst + ungenutzter `nachrichtenNeu`-Endpoint entfernen; A11y (aria-pressed SB-Chips, role=alert Fehlerblock, aria-hidden Skeleton); `type=button` + Retry-Disable + Badge-Logik-Konsolidierung in `boardUi`; **NEU (Befund Playwright-Abnahme 2026-08-10):** doppelte React-Keys in `boardUi.jsx` `ZeilenListe` (Key = AZ+SB+Datum kollidiert bei mehreren Einträgen derselben Akte am selben Tag — eindeutigen Key ergänzen).

### Kürzungstaxonomie — Phase 0 ✅ · Phase 1 ✅ · in `main` (2026-07-24)
**Offen:**
- **Messung Zielwerte (~2026-08-20, nach ~4 Wochen Betrieb):** `docker exec unfallakten-backend-dev python /app/tools/kuerzungsmatching_report.py` — Zielwerte: Abdeckung ≥ 90 %, Trefferquote ≥ 75 %, Positionszuordnung ≥ 90 % (DECISIONS 2026-07-23). Baseline siehe CHANGELOG.
- **Runden-Kachel im echten Betrieb** sichten, sobald die erste Akte 2 Abrechnungsrunden hat (Test-Abdeckung vorhanden, echter Fall noch nicht).
- Fehlablage-Entscheidung → oben bei „Offene Entscheidungen RA Schatz".
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
- **PRD-25d – Intelligente Sachstandsanfrage.** Alter Plan (`handover/PRD-25d_Intelligente_Sachstandsanfrage.md`) basiert auf `aktenchronik_service.py` (Neubau) — veraltet, seit Pipeline-v7 gibt es das Ereignis-Modell (`ereignis_service.py`, Tabelle `ereignisse`/`ereignis_positionen`) als SSOT für den Aktenverlauf. Aktenchronik-Konzept wird nicht mehr verwendet. Vor Umsetzung: Plan auf Ereignis-Modell umstellen (eigenes Brainstorming). **Dazu gehören die offenen STA-Review-Kernbefunde 2026-08-11** (K-1 Eskalation ignoriert eingegangene Antworten, K-2 RA-MICRO-Vorlagen-Weg für die Stufenlogik unsichtbar, K-3 keine Rundenlogik, M-3–M-6, G-4–G-6) — Befund-Katalog + Empfehlung: `handover/2026-08-11-sachstandsanfrage-review-befunde.md` Abschnitt 6.
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
- **Betragsvalidierung Intake** (2026-08-05): größtenteils redundant — Regex↔LLM-Konsens-Check (`llm_konflikt`, > 1 €) existiert bereits in `gutachten_parser.py:685` + `abrechnungsschreiben_parser.py:599`, Temperatur 0 gesetzt. Nicht neu bauen; einziger Rest-Hebel = Beträge als String ins JSON-Schema. Detail: `PROJEKTERWEITERUNG_betragsvalidierung.md` + Memory `project_unfallakten_betragsvalidierung_redundant`.
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
- **Zwei getrennte Positions-Modelle abgleichen (aus UX-Review 2026-07-31, Baustelle 3):** Das alte Schaden-Formular (`schadenpositionen`-Tabelle, füttert Forderung/Klage) und das neuere Ereignis-Modell (`ereignisse`/`ereignis_positionen`/`position_ereignis_cache`, füttert `PositionsDashboard`) laufen parallel und gleichen sich **nicht** automatisch ab; die `position_key`-Namensräume differieren (alt hat `_netto`-Varianten, Registry `positionsarten.yaml` nicht — im Code als „bis P1.7" vertagt, `belege_routes.py:135-152`). Zu klären: konsolidieren (eine SSOT) oder bewusst getrennt lassen? Kontext: `docs/superpowers/specs/2026-07-31-belege-zu-positionen-design.md` §9.

---

## ✅ Erledigt
> Kompakter Index. Vollständige Umsetzungs-Protokolle mit Commits/Tests: **`docs/CHANGELOG.md`**.

| Datum | Feature |
|---|---|
| 2026-08-11 | **Großer Merge nach `main` + Push** (`40c9143e..cf7dd74d`, FF): kompletter Stapel `intake-review-sichtbarkeit` + `abschlussbericht` — SSOT-Dokumentenklassen (22), Intake-Review-Sichtbarkeit, Abschluss-/Sachstandsbericht, Referenzwerkstatt+Entfernungsprüfung, Übersicht-Redesign A+B, Forderungsschreiben-Fixes (C-1, I-1–I-9), STA-Sofort-Fixes, E-Mail-Hotfixes, Testsanierungen (modul6/7 + Vollsuite). Entscheidung RA Schatz: Abnahmen produktiv statt vorab |
| 2026-08-11 | **Backend-Vollsuite-Testsanierung: 123 → 0 Failures** (1735/1735 grün): modul1–4 + Nachbarn auf heutige API portiert; 3 echte Befunde gefixt (Frisch-DB-FK `unfallakte(id)`→`az` in Migration 3, `todos` ON DELETE CASCADE, „Rechnung (Auffang)" raus aus der Dokumentbezeichnung via `bezeichnung_label`); 2 Isolationsprobleme (sv_portal-Fixture ohne eigenes DB_PATH, akten_matching gegen echtes RA-MICRO). Protokoll → CHANGELOG |
| 2026-08-11 | **Sachstandsanfrage: Review + Sofort-Fixes** (M-1 AZ-Format Dialog-Einstiege, M-2 Genus/Kasus `{SchreibenDativ}`, G-1 PII-Log, G-2 Fristanzeige, G-3, G-7 Stufenlogik-Tests) — Befund-Katalog `handover/2026-08-11-sachstandsanfrage-review-befunde.md`; Kernbefunde K-1–K-3 → Backlog PRD-25d |
| 2026-08-11 | **Forderungsschreiben: Review-Fixes** C-1 (berechne_positionen = SSOT Brief+Historie, Restwert negativ) + I-1–I-9 + Aufräumen — `bugfixes.md`; offen nur I-10 (Entscheidung RA Schatz) |
| 2026-08-10 | **Übersicht-Redesign A+B** (Summen-SSOT aus Ereignismodell, 3 Akkordeons, Onboarding-Fächer, Aktions-Pills) + Playwright-Abnahme 19/19 an echten Akten |
| 2026-08-07 | **Abschluss-/Sachstandsbericht** (Migration 67, `abschluss_uebersicht.py`, DOCX, Kurationsdialog; Gebühren-Streitwert-Folgefund gefixt) — DOCX-Sichtprüfung → Produktiv-Nachtests |
| 2026-08-04 | **Intake-Review-Sichtbarkeit** (`GET /akten/<az>/intake-pending`, `IntakePendingListe`, ReviewQueue-Direktsprung) + **Dokumentenklassen-SSOT** (22 Klassen, Registry-YAML + `tools/gen_dokumentenklassen.py`) + Scheduler-Fix Dev |
| 2026-08-10 | **Übersicht-Review-Fixes** (`f6fd2f3d`, Branch `abschlussbericht`): 7 Befunde behoben — Crash RegulierungsTabelle (effRep/ist130), OnboardingHub-Phantomfelder + Auto-Ausblenden bei vollständiger Checkliste, „+ Todo"-Formular im Header, Chronik-Sortierung (ISO-sortKey), §3a-Fristtyp-Pill, RSV-Doppelanzeige, ~10,5 kB toter Code raus; TDD 11 neue Tests, Vollsuite 476/476. Befund-Katalog: `handover/2026-08-10-uebersicht-review-befunde.md` · offen: B3/Redesign → Backlog „Mittel" |
| 2026-08-07 | **Firmen-Beteiligte-Fix** (`6801be75`): RA-MICRO-Name immer aus `sNachname`, `sErsteAdresszeile` nur Anredeform — „Firma"-Geistereintrag statt „RCR GmbH" in 1280/25 behoben, 7 Fundstellen + Anrede-Code 4, 5 Tests, live verifiziert |
| 2026-08-07 | **Referenzwerkstatt-Extraktion (VHV-Blockformat) + Entfernungsprüfung ReviewQueue (Button+Popup+Persistierung) + Intake-Restbefunde a/c** (Marker-Wortgrenzen, Datums-Scheinkonflikt) + **RA-MICRO-read-only-Fallback Mandanten-Adresse** — Branch `abschlussbericht`, an Dok 516/517 + Akte 1280/25 E2E-verifiziert; Browser-Abnahme offen, siehe „In Arbeit" |
| 2026-08-06 | **E-Mail-Import Endlos-Poll-Loop gefixt** (`34342daa`: On-demand-Aktenanlage repariert + FK-Guard) und **Dubletten bereinigt** (Freigabe RA Schatz): `dokumente` 53.216→789 Zeilen, 106.266 Dateien / ~222 GB aus `/app/uploads` entfernt, VACUUM 50→4 MB. Backup: `/app/data/unfallakten.db.bak_pre_dubletten_cleanup_20260806_155109`. Außerdem `8e9b50ea`: Prüfbericht-Schema (fiktive/konkrete Erstattung) + Validierungsregeln aktiv (ReviewQueue-Warnung bei Positionssummen-Abweichung, Akte 1280/25) |
| 2026-08-03 | **Aktenanlage + Dashboard-Hell in `main` gemergt (FF) + gepusht** (`81e33206`); OMA-Live-Abnahme: Prefill-Fix (stale auftraggeber + Anrede-Normalisierung), Migration-66-Reloader-Reparatur, OMA-Pfad→`Z:\RA\M-Plattform`, Dateiname-Präfix `Oma_`, XML strukturgleich zum echten Export; Prod-Compose `oma-share` nachgezogen |
| 2026-07-24 | Klage-Wizard-Verbesserungsrunde Pakete 1–4 komplett (Entwurf speichern, UI-Führung, Gesamtvorschau, Standardtexte V11 Stufe 1) — in `main`, gepusht |
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
