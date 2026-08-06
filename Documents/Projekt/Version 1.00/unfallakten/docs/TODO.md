# TODO – Unfallakten-Verwaltungssystem

> Schlanke Arbeitsliste — nur Zukunftsgerichtetes. Zuletzt gestrafft: 2026-07-20.
> Erledigtes mit Protokoll → `docs/CHANGELOG.md` · Entscheidungen mit Begründung → `docs/DECISIONS.md` · Deploy/Betrieb → `docs/STATE.md`.

---

## 🔄 In Arbeit

### Abschluss-/Sachstandsbericht — implementiert, Abnahme offen (Branch `abschlussbericht`)
Neuer Typ `abschlussbericht` (Migration 67 `abschluss_status`, Service
`abschluss_uebersicht.py`, DOCX via styling.py, GET/PUT-Routen, Kurationsdialog
in WordSection). Alte Auto-Summary (`abschluss_summary.py`) ersatzlos entfernt.
Spec: `docs/superpowers/specs/2026-08-05-abschlussbericht-design.md` · Plan:
`docs/superpowers/plans/2026-08-05-abschlussbericht.md`.
**Offen:** Browser-Abnahme RA Schatz (DOCX-Sichtprüfung beide Modi); Merge nach
Intake-Branch-Klärung (Branch stapelt auf `intake-review-sichtbarkeit`);
Portal-Auslieferung via portal_sync-Payload = Stakeholder-Portal-Teilprojekt;
Empfänger-Override je Position (Spec §8) bei Bedarf nachrüsten;
Google-Bewertungs-URL/QR als Kanzlei-Einstellung (Spec §15).
**Folgefund Gebührenassistent: ✅ gefixt (2026-08-06, Freigabe RA Schatz).** Toter `COALESCE(rep_rechnung_brutto, rep_gutachten_netto, 0)` im Streitwert-Fallback von `gebuehren_routes.py` + `gebuehren_word.py` (Kostennote) durch `>0`-Vorrang-CASE ersetzt (analog `23ea6792`); griff nur ohne Forderungsschreiben bei fiktiver Abrechnung. 3 Regressionstests: `test_gebuehren_streitwert_fallback.py` (Route fiktiv, Rechnung-Vorrang, Kostennote-DOCX-Gegenstandswert).

### Intake-Review-Sichtbarkeit — ✅ implementiert + review-clean (SDD, 2026-08-04), Branch NICHT gemergt
Ausstehende Intake-Dokumente einer Akte werden in der Dokumentenkachel sichtbar (Badges „Wird verarbeitet"(`neu`/`laeuft`) / „Review ausstehend"(`bereit_zur_review`) / „Fehler – prüfen"(`pipeline_fehler`)) + Link „Zur Review →", der die ReviewQueue auf genau das Dokument öffnet. BE: `GET /akten/<az>/intake-pending` (`akten_routes.py`, read-only, **Union-AZ-Ableitung über alle Zustellungen**, Filter `queue_status != 'freigegeben' AND verworfen_am IS NULL`); FE: `IntakePendingListe` in `DokumenteSection`, Nav `pendingReviewIntakeId`→`initialIntakeId`→`setAktivId`. 5 Commits (`a68098ab`..`a60c7bc0`), alle Task-Reviews + Whole-Branch-Final-Review ✅ (Ready to merge). Spec/Plan: `docs/superpowers/{specs,plans}/2026-08-04-intake-review-sichtbarkeit*`. Memory `project_unfallakten_intake_review_sichtbarkeit`.
**Offen (Blocker vor Merge):**
- **Browser-Nachtest RA Schatz:** Import in Testakte → Zeile „Review ausstehend" in der Kachel → Link öffnet Dok in ReviewQueue → Zeile verschwindet nach Freigabe.
- **Merge-Strategie klären:** Branch `intake-review-sichtbarkeit` bündelt SSOT-Dokumentenklassen (22 Klassen) + Scheduler-Fix (`SCHEDULER_LEASE_DISABLED`, nur Dev) + dieses Feature. Nach beiden Browser-Abnahmen (auch SSOT-Dropdown) gemeinsam FF nach `main` — oder SSOT vorab separat. `SCHEDULER_LEASE_DISABLED` NICHT in Prod (Gunicorn braucht den Lease).

### Aktenanlage aus der ReviewQueue (PRD-NEW) — ✅ gemergt + gepusht (2026-08-03, `main`=`81e33206`), Nachlauf offen
Feature live abgenommen: Prefill Mandant, OMA-XML **strukturgleich** zum echten RA-MICRO-Export, **Dateiname muss mit `Oma_` beginnen** (Watcher-Filter, case-sensitiv), Import wird erkannt. Behoben: stale-auftraggeber-Prefill + Anrede-Normalisierung, Migration-66-Reloader-Falle, OMA-Pfad (`Z:\RA\M-Plattform`) + Dateiname + XML-Struktur (keine leere `<Gegnerliste>`, `<tvm/>`). Prod-Compose nachgezogen. Detail → Memory `project_unfallakten_aktenanlage`.
**Offen (opportunistisch, kein Blocker):**
- Echter End-to-End-Create-Test beim **nächsten echten Neu-Mandanten**: Adress-Dublette Mandant (Punkt 4), Geschwister-Szenario (Punkt 5), `dtAnlage`-Prüfung. Mit Bestands-/Altakten nicht testbar (RA-MICRO-Test-Akten nicht löschbar).
- Beteiligten-Dublettencheck (DEKRA/Versicherung) — erst am echten Import verifizieren, ob RA-MICROs eigene OMA-Dublettenprüfung reicht.
- `beispieloma.xml` als **bereinigte** Test-Fixture committen (sonst skippt der Struktur-Guard-Test in CI); NICHT die echte Kundendatei (PII).
- Prod-Rollout: `oma-share`-Volume steht in `docker-compose.prod.yml`; bei non-root Gunicorn ggf. `uid`/`gid` anpassen.

### Dashboard-Hell — ✅ gemergt (2026-08-03), Nacharbeit offen
Feinschliff separat: Sidebar-Emoji-Icons App.jsx, SB-Klarnamen-Tooltips (Kürzel-Liste von RA Schatz nötig); totes `pendingEmailId`-Gerüst + ungenutzter `nachrichtenNeu`-Endpoint entfernen; A11y (aria-pressed SB-Chips, role=alert Fehlerblock, aria-hidden Skeleton); `type=button` + Retry-Disable + Badge-Logik-Konsolidierung in `boardUi`.

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
