# TODO – Unfallakten-Verwaltungssystem
> Generiert: 2026-05-02 aus allen Session-Handovers (v18–v56), PRD-Dateien, backlog.md
> Quellen: session_handover_v38–v56.md, handover/backlog.md, handover/PRD-*.md

---

## ✅ Erledigt

| PRD / Feature | Beschreibung | Quelle |
|---|---|---|
| PRD-01 (Basis) | To-Do-System + Header-Widget | (aus: session_handover_v38.md, v20/v21) |
| PRD-02 | Textbaustein-Feld Kürzungsarten | (aus: session_handover_v55.md, 2e1e0fb) |
| PRD-03 K-01–K-15 | Klageschrift-Formatierung vollständig | (aus: session_handover_v38.md, v35–v36) |
| PRD-04 | Dokumentenklassen + Dispatcher + Registry | (aus: session_handover_v38.md, v23) |
| PRD-04b | Feedback-Loop: Korrektur + Trainingsdata | (aus: session_handover_v38.md, v24) |
| PRD-14 | Single Source of Truth: Abrechnungsart (Backend + Frontend) | (aus: session_handover_v55.md, 0caaa4a) |
| PRD-15 | WDM Auto-Load | (aus: session_handover_v38.md, v26) |
| PRD-16 | Tab-Reihenfolge als Workflow-Ablauf | (aus: session_handover_v55.md, d2748df) |
| PRD-18 | Phasen-Strip (UebersichtSection) | (aus: session_handover_v55.md, 3f34ed5) |
| PRD-20 | App.jsx Refactoring (26 Dateien) | (aus: session_handover_v38.md, v25) |
| PRD-21 Phase 1+2+3a | E-Akte Auto-Import vollständig | (aus: session_handover_v38.md, v28–v29) |
| PRD-22a | Gutachten im Schaden-Reiter | (aus: session_handover_v38.md, v30) |
| PRD-22b | Regulierung: Abrechnungen + Löschfunktion | (aus: session_handover_v38.md, v31) |
| PRD-22d | E-Mail-Import UI (3 Tabs + Smart-Inbox) | (aus: handover/backlog.md) |
| PRD-23a | Schadenposition-Belege + Schadenbelege-Card | (aus: session_handover_v38.md, v32) |
| PRD-23b | Rechnungs-Parser (Registry + Kandidaten + Frontend + 59 Tests) | (aus: handover/backlog.md) |
| PRD-24 | Aktivlegitimation + Klage-Wizard Sessions A–D | (aus: session_handover_v38.md, post-v38 deployed) |
| PRD-25a | Automatische Fristen | (aus: handover/backlog.md) |
| PRD-25b | Action-Dashboard (UebersichtSection) | (aus: handover/backlog.md) |
| PRD-26 | Klage-Wizard 10-Step (Umbau) | (aus: handover/backlog.md) |
| PRD-27 | ReguWizard – Stellungnahme-Wizard | (aus: session_handover_v55.md, 2e1e0fb) |
| PRD-28 | Gebührenassistent Nr. 2300 VV RVG + Kostennote DOCX | (aus: handover/backlog.md) |
| PRD-29b | E-Akte Auto-Parser: E-Brief-Filter via Schlagwort | (aus: handover/backlog.md, PRD-29_EAkte_Filter_DKz.md) |
| PRD-30 | OCR + SSE-Streaming für Bild-PDFs (pytesseract, pdf2image) | (aus: handover/backlog.md) |
| PRD-31 (KI) | KI-Parsing Gutachten: Shadow-Mode, Konflikt-Dialog, Korrektur-Endpoint | (aus: handover/backlog.md) |
| PRD-32 Phase 1 | Rechnungstypen-Subklassen (Standkosten/Abschlepprechnung) im Classifier | (aus: handover/backlog.md) |
| PRD-34 | Inbox-Pattern Dokumente-Kachel (KLASSE_TO_POS, Inline-Zuordnung) | (aus: handover/backlog.md) |
| Regulierungs-Workflow Option B | 5 Phasen, Legacy-regulierung deprecated, Delete-Bug v14c gefixt | (aus: handover/backlog.md) |
| KI-Parsing Regulierungsschreiben | Qwen Shadow-Mode, Modell-Switcher UI, Few-Shot, Datum-Fix | (aus: handover/backlog.md) |
| Action Board Global + OnboardingHub | ActionBoardView (3 Spalten), OnboardingHub (7 Kacheln) | (aus: session_handover_v56.md) |
| E-Mail-Workflow Redesign | EmailDetailView (2-spaltig), ActionBoard→Detail-Navigation, DokumenteSection E-Mail-Gruppe, Migration 42 (.eml dateityp), api.js inAkte mit erzwingen | (Session 2026-06-12) |
| PRD-22c | Mandanten-Fragebogen: E-Mail-Parser, fragebogen_parser.py, DB-Tabelle fragebogen_erstkontakt, Verarbeitungslogik, Frontend (FragebogenErstkontaktKarte.jsx). Ausstehend: Website-Formular + PRD-22d (Akte-Anlage). | (Code-Prüfung 2026-05-03) |
| PRD-35 | Klage-Wizard Bug-Fixes (5 Bugs): vorsteuer in b_dict, wizardVerzugDatum in Step 6, EinwändePanel-Preview, StepVerzug Manual-Edit-Schutz (wizardVerzugManuell), StepSchaden Gefordert-Spalte (betragOriginal). + klage_service: RVG außergerichtl. Gegenstandswert, rvg_bereits_gezahlt Abzug. | (Session 2026-05-10) |
| PRD-36 (a–d) | Code-Konsolidierung: `_pruefe_akte` → `_helpers.py`, Datum-Parsing → `utils/datum.py`, `fmtEur` → Import aus `utils.js`, Beteiligte-Serialisierer → `models/beteiligte.py`. 7 TDD-Tests. | (Session 2026-05-15) |
| B-08 | Netto/Brutto bei Vorsteuer-Mandant | (aus: session_handover_v38.md, v33) |
| B-09 | Gegenstandswert + fehlende Schadenspositionen | (aus: session_handover_v38.md, v34) |

---

## 🔄 In Arbeit

### ⭐ Intake-Refactoring (Pipeline v7 + Positionsmodell) — GROSSPROJEKT
**Maßgebliche Dokumente (immer zuerst lesen):** `freigabe.md` (verbindlich, übersteuert die Pläne) + `PIPELINE-REFACTORING-PLAN.md` + `POSITIONSMODELL-PLAN.md` (alle im Projekt-Root).
**Arbeitsbranch:** `intake-stufe1` — alle Implementierungs-Sessions arbeiten auf diesem Branch, nicht auf main.
**Reihenfolge:** verbindlich lt. freigabe.md Abschnitt 4 (S1.1–S1.5 → P1.1–P1.4 → …), inkl. Korrekturen K-P1–K-P4 / K-M1–K-M3.
**Aktueller Schritt:** **S1 komplett** (S1.1–S1.9) + **P1.1 + P1.2 + P1.3 + P1.4 + P1.5 + P1.6** ✅ (2026-07-09). Nächster Schritt: **P1.7** (Positions-Dashboard, AbleitungBadge, Dokument-Scope-Aktionsmenü, Ereignisliste je Position — UI-Arbeit). **Baseline für P1.7**: 209 failed / 670 passed / 0 errors / 18 skipped auf `intake-stufe1` (nach P1.6). Diffbasierte Regressionschecks bevorzugen (Test-Order-Rauschen bei LM-Studio-abhängigen Tests). Delta gegen P1.5-Baseline (206f/657p): +16 neue P1.6-Tests (6 Mig 52 + 7 fristablauf_service + 3 Endpoint), +3 test-order failures rein in bekannten Alt-Kategorien. Keine echte Regression, alle P1-Tests grün.

- **S1.9a** (2026-07-09) ✅: Vorbereitung + Zustellungs-Aufbewahrung. Feature-Flag `INTAKE_REVIEW_PFLICHT` (Default True) in `backend/intake/feature_flags.py` — Rollback-Anker für S1.9b-d. Migration 49: `email_import_log.ausgeblendet` (INTEGER NOT NULL DEFAULT 0). `POST /email/import/log/<id>/loeschen` setzt jetzt `ausgeblendet=1` unter dem Flag; Alt-Pfad (`status='ignoriert'` + IMAP-Move) läuft nur noch bei `INTAKE_REVIEW_PFLICHT=false`. Zielbild-Assertion-Guard `test_s19_intake_write_guard.py`: fixiert die Whitelist der aktuell noch bestehenden direkten Alt-Aufrufer (`registriere_dokument`/`setze_schadenpositionen` in import_service.py, upload_service.py, eakte_routes.py); jeder NEUE Aufruf schlägt an, in S1.9b/c/d wird die Whitelist geleert. 12 neue Tests grün (feature_flag 3 + mig49 4 + ausblenden 3 + guard 2). Suite 205f/548p/0e/18s → 205f/560p/0e/18s (keine Regression, +12 passes).
- **S1.9b** (2026-07-09) ✅: import_service.py Schritt 13 (Anhang-Auto-Registrierung, Zeile 291-322) hinter `INTAKE_REVIEW_PFLICHT` gestellt. Der IMAP-Adapter `adapter_imap.verarbeite_email()` (bereits vorher als „Doppelschreiber" aktiv) erzeugt allein die `intake_dokumente`+`zustellungen`; keine `dokumente`-Zeile mehr für E-Mail-Anhänge unter dem Flag. Hash-Dedup läuft im Adapter über `_persistenz.oder_intake_dokument_fuer_datei`. Bericht zählt Anhänge weiter (bericht["anhaenge"] += n). Alt-Pfad bleibt bei `INTAKE_REVIEW_PFLICHT=false` aktiv. Guard-Whitelist angepasst (Zeile 306 Alt-Pfad-Rest, jetzt hinter Flag; 737+767 = manuelle „In Akte importieren", S1.9d; 1041 = Fragebogen K-P1, S1.9d). 2 neue Tests grün. Suite 204f/? passes → 204f/? passes (netto keine Regression).
- **S1.9c** (2026-07-09) ✅: Upload-Route und E-Akte-Import hinter `INTAKE_REVIEW_PFLICHT` gestellt. `dokumente_routes.upload()` unter Flag → nur `adapter_upload.verarbeite_datei`, HTTP 202 `{intake_dokument_id, zustellung_id, sha256, in_review: True}`; kein `verarbeite_upload`, kein Dispatcher. `eakte_routes.importieren()` analog → nur `adapter_eakte.verarbeite_eakte_dokument`, HTTP 202. `upload_service._uebernehme_schaden()` unter Flag Skip (defensive Absicherung, primär greift der Route-Umbau). Alt-Pfad läuft bei `INTAKE_REVIEW_PFLICHT=false` unverändert. 4 neue Tests grün (2 Upload + 2 E-Akte). Suite 204f/… → 205f/… (Diff: 3 pre-existing test-order-Failures wechseln, alle isoliert grün — keine echte Regression). Guard-Whitelist gepflegt (Zeilennummern nach Kommentar-Einfügung aktualisiert).
- **S1.9d** (2026-07-09) ✅: K-P1 komplett umgesetzt. `_ergaenze_mandant`/`_ergaenze_gegner`/`_ergaenze_unfalldetails`/`_ergaenze_personenschaden` schreiben unter Flag NICHTS mehr in `beteiligte`/`unfalldetails`/`personenschaden`/`mandant`. `_speichere_fragebogen_json` (Fragebogen-Audit-Trail) unter Flag Skip. `POST /email/import/log/<id>/in-akte` liefert unter Flag HTTP 202 `{in_review, hinweis}` statt `importiere_in_akte`-Aufruf. Frontend `InAkteButton.jsx` erkennt 202+`in_review` und zeigt Hinweis auf Review-Queue statt Fehler. **End-to-End-Testkriterium erfüllt** (`test_s19d_e2e_no_intake_writes.py`, 4 Tests): Upload, E-Akte-Import, In-Akte-Klick, Fragebogen-Auto-Enrichment schreiben unter Flag KEINE dokumente/schadenpositionen/beteiligte/unfalldetails/personenschaden-Zeilen mehr. Der einzige zulässige Schreibweg in Akten-Tabellen ist der `output_adapter` (via Review-Freigabe S1.8). Guard-Whitelist bleibt als Rollback-Anker bestehen (Zeilenkommentare aktualisiert). 12 neue Tests grün. **S1.9 vollständig abgeschlossen.** Suite 204f/… → 204f/… (keine echte Regression).

**S1 komplett** (S1.1–S1.9). **P1.1 + P1.2 erledigt** (2026-07-09):

- **P1.1** ✅: `backend/registry/positionsarten.yaml` (alle POSITION_KEYS + kategorie/aggregation/checkliste), `ereignistypen.yaml` (11 Typen: eingehend/ausgehend/intern mit Wirkungen), `aktionen.yaml` (Type-Action-Matrix-Grundgerüst). Neuer Loader `backend/services/positionsmodell_registry.py` mit Fail-Loud (analog S1.5), Konsistenzchecks (POSITION_KEYS-Vollabdeckung, Checkliste-→Ereignistyp-Referenzen, aktionen-→ereignistyp-Kreuzreferenz). App-Start hängt jetzt an sauberer Positionsmodell-Registry. 7 Tests grün.
- **P1.2** ✅: Migration 51 legt `ereignisse` (Kopf, POSITIONSMODELL 4.1), `ereignis_positionen` (n:m mit K-M1 UNIQUE über `(ereignis_id, position_key, wirkung, COALESCE(kuerzungsart_id, 0))`) und `position_ereignis_cache` (Ebene 2, identisches K-M1 UNIQUE) an. `backend/services/ereignis_service.schreibe_ereignis()` ist der EINZIGE Schreibpunkt (Registry-validiert, atomarer Insert in Kopf+n:m+Cache). `rebuild_cache()` rekonstruiert Ebene 2 aus Ebene 1 (Drift-Guard-Test grün). `ersetzt_kopf_id` setzt Cache-Zeilen auf `status='ersetzt'`. AST-Guard-Test blockiert Fremd-Writes in die drei Ereignis-Tabellen aus allen Dateien außer `ereignis_service.py`+`schema_manager.py`. 16 Tests grün (6 Migration + 8 Service + 2 Guard).

**P1.3 erledigt** (2026-07-09) ✅: `backend/services/positionsstatus_service.leite_positionsstatus_ab(akte_az, mit_registry=False)` liest ausschließlich `position_ereignis_cache.status='aktuell'` (Ableitungs-Invariante: ersetzte Ereignisse fließen nie ein — 2.2c-Test bestätigt). Liefert pro `position_key`: `zustand` (offen/gefordert/anerkannt/teilanerkannt/bestritten/erledigt), `gefordert`/`anerkannt`/`gekuerzt`/`abgelehnt`, `offen` (× Quote, Default 1.0 lt. PF-03), `eskalationsstufe` (analog `sta_service._empfohlene_stufe`), `stand` (jüngstes aktuelles Datum — Pflichtfeld Wissensgrenze), `checkliste` (POSITIONSMODELL 4.6: `{erledigt, offen}` aus `positionsarten.yaml`, nur Ereignisse mit `dokument_id != NULL` zählen als erfüllt). Neuer Blueprint `backend/routers/positionen_routes.py` mit `GET /akten/<az>/positionen/status` (Ableitung + `registry_version` als Wissensgrenze) und `GET /akten/<az>/aktionen[?dokument_id=]` (Type-Action-Matrix aus `aktionen.yaml` mit Deduplikation). 16 neue Tests grün (10 Service inkl. tabellenbasierter Zustandsübergänge + 2.2c-ersetzt-Test + 6 Routes). Suite 206f → 202f (-4, reine Test-Order-Effekte).

**P1.4 erledigt** (2026-07-09) ✅: Zentraler Helper `backend/services/ausgehende_ereignisse.erzeuge()` wrapt `schreibe_ereignis` mit `quelle='dokument'` + Registry-Vorbelegung der Wirkung + Best-Effort-Fehlerbehandlung. Positionen akzeptiert als `{key: betrag}`-Dict oder Positions-Liste. Unbekannte position_keys werden weggeloggt, verbleibende Positionen laufen weiter (leere Liste → Akten-Scope-Ereignis).

Instrumentierte Generierungs-Stellen (5):
- `word_service.generiere_und_speichere()` — Mapping `forderungsschreiben → forderung_generiert`, `klage → klage_generiert`, `sachstandsanfrage → sachstandsanfrage_generiert`. Positionen aus `akte_daten["schaden"]` für Forderung+Klage; Akten-Scope für STA.
- `gebuehren_word.generiere_kostennote()` — `kostennote_generiert` mit `ra_gebuehren`-Position aus `gb_row.gesamt_brutto`/`gesamtbetrag`.
- `klage_routes.generiere_klage()` — `klage_generiert` mit Positionen aus `hole_schadenpositionen(az)`.
- `sta_routes.sta_generieren()` — `sachstandsanfrage_generiert`, Akten-Scope.
- `stellungnahme_routes.generiere()` — legt jetzt zusätzlich einen `dokumente`-Eintrag an (bisher nur Download) und erzeugt `stellungnahme_generiert`-Ereignis. Akten-Scope.

Alt-Tabellen (`forderung_positionen`, `regulierung_positionen`) bleiben parallel bestehen — kein Big-Bang. 7 neue Tests grün (4 Helper + 3 Word-Service-Aufrufweg). Suite **202 → 203 failures** (Delta = 1 test_s19c-Test wechselt zwischen Rauschen, isoliert grün). Keine echte Regression.

**P1.5 erledigt** (2026-07-09) ✅: Vier Bestätigungswege instrumentiert, alle Best-Effort und Alt-Tabellen laufen parallel weiter.

- **Vorbereitung**: neue `backend/registry/rechnungstyp_mapping.yaml` (Klasse → position_key aus positionsarten.yaml, Sondermarker `__sv_kosten_vorsteuer__`) mit Fail-Loud-Loader; `PositionsmodellRegistry` erhält Feld `rechnungstyp_mapping`. `schreibe_ereignis()` akzeptiert `ersetzt_positions_ids=[...]` (K-M2a): pro alt-Position wird per position_key eine passende neue Position gesucht, `alt.ersetzt_durch = neu_id` gesetzt und die Cache-Zeile der Alt-Position auf `status='ersetzt'` gestellt (Kopf bleibt aktuell). `pruefe_doppelerfassung(akte_az, dokument_id, ereignistyp)` prüft (akte_az, dokument_id, ereignistyp) auf aktuelle Ereignisse; NULL dokument_id → immer None (WDM). Widerspruch `ersetzt_kopf_id` + `ersetzt_positions_ids` → TypeError.
- **Neuer Helper `backend/services/eingehende_ereignisse.py`**: vier fokussierte Bestätigungsweg-Wrapper. Wirkungs-Ableitung ReguWizard: `betrag_reguliert>0 → anerkannt`; `gefordert>reguliert & kuerzungsart → gekuerzt (Differenz)` oder `abgelehnt (voller Betrag, wenn reguliert=0)`; `haftungsart='ablehnung' → alle Positionen abgelehnt`. Ohne Kuerzungsart entstehen keine gekuerzt/abgelehnt-Zeilen. Alle Helper: Best-Effort mit try/except-Wrapper.
- **P1.5a — ReguWizard-Speichern → `abrechnung_eingegangen`**: `POST /akten/<az>/abrechnungen` ruft `erzeuge_aus_regulierung` nach Alt-Insert. `PUT /akten/<az>/abrechnungen/<id>` (K-M2b): erneutes Speichern → neues Ereignis mit `ersetzt_kopf_id` des vorhandenen. Doppelerfassungs-Guard verhindert Doppel-Ereignisse. Alt-Tabelle `regulierung_positionen` läuft weiter.
- **P1.5b — Beleg-Zuordnung → `rechnung_eingegangen`**: `POST /akten/<az>/belege` ruft `erzeuge_aus_beleg` (wirkung=beleg, betrag=betrag_aus_beleg, herkunft=beleg_zuordnung). Die Alt-Konstante `_KLASSE_POSITION_MAP` in belege_routes.py bleibt bestehen (Kandidaten-Endpoint verwendet schadenpositionen-Spalten mit _netto-Suffix, die nicht in positionsarten.yaml sind — Konsolidierung inkl. Frontend-Kopie erfolgt in P1.7). Neuer Weg via Registry ist `rechnungstyp_zu_position()`.
- **P1.5c — Gutachten-Übernahme + K-M2a → `gutachten_eingegangen`**: `POST /akten/<id>/dokumente/<did>/korrektur` ruft `erzeuge_aus_gutachten` für Dokumente vom Typ `gutachten` (Positionen: reparaturkosten / wiederbeschaffung / restwert / wertminderung / sv_kosten, wirkung=gefordert, herkunft=ki_dialog). Optionales Body-Feld `ersetzt_positions_ids` steuert positionsscharfe Ersetzung durch Ergänzungsgutachten. Testkriterium (c) erfüllt: Ergänzungsgutachten ersetzt nur reparaturkosten, wertminderung bleibt aktuell.
- **P1.5d — WDM-Import → `abrechnung_eingegangen` (unbestätigt)**: `POST /akten/<az>/abrechnungen/wdm-import` ruft `erzeuge_aus_wdm` mit quelle='dokument', dokument_id=NULL, herkunft='wdm' (PF-08 — WDM ist inhaltlich Abrechnung, aber ohne Dokument). Guard läuft nicht (dokument_id=NULL); Alt-Pfad verhindert Mehrfach-Import per HTTP 409. UI-Kennzeichnung als unbestätigt erfolgt in P1.7 anhand `herkunft='wdm'`.

Tests: 34 neue Tests grün (10 Vorbereitung + 7 P1.5a + 7 P1.5b + 5 P1.5c + 5 P1.5d). Suite **203 → 206 failures** — Delta rein in bekannten Alt-Kategorien (Auth-Cluster + Schema + LM-Studio-Rauschen), keine echte Regression. Guard-Test blockiert weiterhin Fremd-Writes; kein neuer Direkt-Schreiber.

**P1.6 erledigt** (2026-07-09) ✅: System-Ereignisse via APScheduler. Migration 52 fügt `todos.fristablauf_ereignis_id` (INTEGER FK → `ereignisse(id)`, nullable) + Index `idx_todos_fristablauf_pending` als Idempotenz-Anker hinzu (Alt-Tabelle `todos` bleibt unangetastet, freigabe.md-Vorwissen).

Neuer Service `backend/services/fristablauf_service.verarbeite_faellige_todos()`: SELECT `todos WHERE quelle='system' AND erledigt=0 AND faellig_am<=date('now') AND fristablauf_ereignis_id IS NULL`; erzeugt pro Zeile genau EIN `fristablauf`-Ereignis (richtung=intern, quelle=system, herkunft='scheduler', notiz=todo.text) und setzt danach `fristablauf_ereignis_id`. Positionsregel:
- **antwort_2w_{dok_id}** (todo.dok_id gesetzt): sucht das jüngste aktuelle ausgehende Ereignis zum Dokument (`forderung_generiert` / `stellungnahme_generiert` / `sachstandsanfrage_generiert` / `fristsetzung_generiert` / `klage_generiert`, `ersetzt_durch IS NULL`) und kopiert dessen aktuelle Positionen (`ereignis_positionen` mit `ersetzt_durch IS NULL`) mit `wirkung='keine'` ins neue Fristablauf-Ereignis. Fristablauf = Eskalations-Marker, kein Betragsanspruch. Fehlt das auslösende Ereignis (Alt-Bestand vor P1.4), bleibt der Fristablauf mit dokument_id, aber ohne Positionsbezug.
- **Verjährung / PflVG** (todo.dok_id NULL): Akten-Scope, dokument_id=NULL, keine Positionen.

Scheduler-Job in `backend/app.py`: APScheduler cron-Trigger täglich 03:15 lokal (`id="fristablauf_job"`, `max_instances=1`, `coalesce=True`). Manueller Trigger-Endpoint `GET /system/fristablauf/manual` (nur Admin) für Tests/Debug. RA-MICRO strikt read-only, `INTAKE_REVIEW_PFLICHT`-Flag nicht angefasst, Alt-Tabelle `todos` bleibt bestehen (Doppel-Führung).

16 neue Tests grün: 6 Migration 52 + 7 fristablauf_service (Verjährung Akten-Scope, antwort_2w mit Position-Kopie, Idempotenz, zukünftige/erledigte/benutzer-Filter, antwort_2w ohne auslösendes Ereignis) + 3 Endpoint (401/403/200 mit Zähler). Suite **206f → 209f** — Delta +3 test-order failures rein in bekannten Alt-Kategorien (Auth-Cluster, sv_portal, prd27, dashboard, s16a_golden_e2e, migration_46), keine neuen Non-Alt-Failures. Baseline für P1.7: **209 failed / 670 passed / 0 errors / 18 skipped**.

Nächster Schritt: **P1.7** (UI): Positions-Dashboard (Toggle), `AbleitungBadge.jsx` (Wissensgrenze `stand`), Dokument-Scope-Aktionsmenü (`GET /akten/<az>/aktionen?dokument_id=`), Ereignisliste je Position (Ebene 2). K-Punkt-Zusatz aus freigabe.md Abschn. 4: `herkunft='wdm'` → `has_unbestaetigt`-Flag im Dashboard.
**Vor jedem Migrationsschritt:** Sicherungskopie der SQLite-DB. Kein executescript(), explizites conn.commit() bei ALTER TABLE. RA-MICRO read-only, Docker/CIFS tabu, Alt-Pfade unverändert (Doppelschreiben).
**Abnahmeregel (freigabe.md Abschn. 4):** Jeder Schritt lauffähig + Testkriterium erfüllt; kein Schritt beginnt, bevor der vorherige abgenommen ist. Migrations-Nummern fortlaufend nach tatsächlicher Reihenfolge.
(Stand: 2026-07-07)

### Action Board – Fristen-Spalte unvollständig
Zeigt aktuell nur RA-MICRO Wiedervorlagen (`tblAktenWiedervorlagen`), keine „harten" Rechtsmittelfristen. Falls RA-MICRO eine separate Fristen-Tabelle führt, wäre Schritt 1 aus Task 2 des Plans zu wiederholen.
(aus: session_handover_v56.md)

### Action Board – Nachrichten-Spalte
Klick auf E-Mail navigiert jetzt direkt zur E-Mail-Detail-Seite (EmailDetailView). Mandantenportal- und SV-Portal-Nachrichten sind weiterhin als Placeholder angelegt; echte Integration hängt an PRD-25c.
(aus: session_handover_v56.md, Session 2026-06-12)

### Pre-existing Testfehler (kein Blocker)
`test_prd23b.py` (7 Failures) und `test_modul8.py` (16 Errors) schlagen seit vor PRD-31 fehl — nicht durch aktuelle Sessions verursacht, noch nicht behoben.
(aus: session_handover_v55.md, session_handover_v54.md)

### 🐛 Bugfixing-Session 2026-07-08
Neben S1.6b in dieser Session gefixt (alle auf `intake-stufe1` gepusht):

- **`a6fb6f4`** — Test-Stub-Kontamination in `test_prd23b.py` entfernt. Historischer Modul-Ebenen-`sys.modules`-Stub für pdfplumber/flask/werkzeug/jwt kontaminierte die Testreihenfolge (~64 Failures + alle 26 Collection-Errors). Statischer Guard-Test `test_prd23b_kontamination.py` verhindert Rückfall. Suite 287f/26e → 223f/0e.
- **`12d78c5`** — `TestKlassifiziereEakteDok` (7 Failures seit v41/2026-04-04 latent kaputt) an neue Listen-Signatur von `_klassifiziere_eakte_dok` angepasst; SV-Domain-Tests semantisch korrigiert (Gutachten.pdf ≠ SV-Rechnung), neuer Test `test_sv_domain_match_bei_gutachten` für den 4-Kandidaten-Fall.
- **`9ffcbe6`** — `backend/tests/conftest.py` setzt `FLASK_SECRET_KEY` vor Test-Collection (verhindert Bootstrap-Crash).
- **`746f731`** — `test_modul6.py`: `TestBackupScript` entfernt (`scripts/backup.sh` existiert nicht mehr), Gitignore-Erwartungen auf Verzeichnis-Muster (`backend/data/`, `nginx/ssl/`) aktualisiert.
- **`70c77c4`** — **Migration 50** legt `unfalldetails`-Tabelle nachträglich an (Root-Cause-Fix). Der aktive Schema-Manager hatte nie ein `CREATE TABLE unfalldetails` gehabt; Migration 28 (Aktivlegit-ALTER) fand die Tabelle nicht und stempelte sich als SKIPPED. Folge: `GET/PUT /akten/<az>/unfalldetails` **und `POST /klage/generieren`** (der geschäftskritische Klageschrift-Endpunkt) crashten mit 500. FK korrekt auf `unfallakte(az)` (Legacy-DDL hatte fälschlich `aktenzeichen`). 6 neue Tests. **Live-DB von Schema 48 auf 50 migriert**, Backup: `backend/data/unfallakten.db.bak_pre_mig50`. Handover: `handover/2026-07-08-datenmodell-bugs-unfalldetails-cleanup.md`.
- **`d5916d3`** — `backend/cleanup_abrechnungen.py`: `DB_PATH`-Default auf `Path(__file__).parent / "data" / "unfallakten.db"` (Pattern aus `database.py`). Historischer Default zeigte auf die Karteileiche (`backend/db/unfallakten.db`, Schema 16); durch Docker-ENV in Praxis überdeckt, aber Falle für lokale Läufe.
- **`6572abf`** — `test_portal_sync.py` beteiligte-Fixture um `gutachten_nr` ergänzt (Migration-39-Follow-through).
- **`e7bdad9`** — P2 (Teil 1) Auth-Bootstrap: `conftest.py` setzt `JWT_SECRET_KEY` + `ADMIN_*`-Env-Vars, damit `_ensure_admin_exists()` genau den Test-Admin anlegt. `test_modul3._setup()` loggt direkt ein statt `/auth/register/erster`. Sample-Refactoring `aktenzeichen`→`az`. Rest von `test_modul3/4/7` (~150 Failures) braucht Test-für-Test-Modernisierung → eigenes Ticket.
- **`9fcdcb5`** — nginx.conf Config-Bugs: `text/html` duplicate in `gzip_types`, Multi-Line-`add_header Content-Security-Policy` mit `always` auf eigener Zeile trieb den Container in Restart-Schleife (invalid number of arguments). Plus **self-signed Zertifikat lokal generiert** (`nginx/ssl/{fullchain,privkey}.pem` — nicht committet, nur auf dieser Entwicklungsmaschine). Verifiziert per curl: HTTPS 200 auf `/health`, HTTP → 301 auf HTTPS. Prod-Deployment braucht Let's Encrypt (siehe `nginx.conf` Zeile 13-15).

**Testsuite-Bilanz:** Baseline (Anfang Session) 294f/385p/26e/3s → nach allen Fixes + S1.7 **211f/524p/0e/18s** (−83 failures, +139 passes, −26 errors; 15 Tests laufen jetzt in ihre Skip-Guards statt in Collection-Errors).

**Offene Baustellen (aus Failure-Kategorisierung 2026-07-08):**
- ~~**P3 – Portal-Sync-Spaltendrift:**~~ ✅ Commit `6572abf` — beteiligte-Fixture um `gutachten_nr` ergänzt.
- **P2 (Teil 1) – Auth-Bootstrap:** ✅ Commit `e7bdad9` — `conftest.py` setzt `JWT_SECRET_KEY` + `ADMIN_*`-Env-Vars, sodass `_ensure_admin_exists()` den Test-Admin anlegt; `test_modul3._setup()` loggt direkt ein. Access-Token-KeyError damit weg. Sample-Refactoring `aktenzeichen` → `az` in `test_modul3.py` (Migration-5-Follow-through).
- **P2 (Teil 2) – Testsuite-Modernisierung `test_modul3/4/7`:** ABGEBROCHEN — kein 1-Zeilen-Fix. Nach jedem gefixten Symptom (`access_token` → `aktenzeichen` → `regulierungen` → Sub-Struktur) kommt das nächste. Jeder Test braucht einzelnen Abgleich mit der aktuellen API. Als eigenes Ticket im Backlog.
- **Kleinere:** `test_migration_46` `intake_dokumente`-Timing (1), `test_sv_portal` 200 vs 404 (1), `test_modul1` `check_schema()` + `test_status_view` (~5). 
- **Endpunkt-Härtung:** Query-Stellen in `klage_routes.py:241/364/1232` sind nach Migration 50 heil, aber ungeschützt (kein `try/except`). Defensiver Guard sinnvoll für DB-Deployment-Reihenfolge-Ausfälle.

---

## 📋 Offen

> Absteigend nach Priorität gemäß letztem Handover (v55/v56).

### Priorität: Kritisch / Bald (nächste 1–3 Sessions)

**PRD-33 – Klage-Wizard Feintuning (klage_service.py)**
Qualitäts-Pass am generierten DOCX. Bereits gefixt (Session 2026-05-10): RVG-Tabelle zeigt jetzt außergerichtl. Gegenstandswert; `rvg_bereits_gezahlt`-Abzug mit bedingten Tabellenzeilen.
Noch offen: weitere Layout-/Inhaltsfehler im generierten DOCX (Absätze, Textbausteine, Rubrum bei mehreren Beklagten, Platzhalter-Kontrolle).
Debugging-Vorbereitung: `handover/session_handover_v52.md` → Abschnitt „Nächste Session".
(aus: handover/backlog.md, session_handover_v55.md, Session 2026-05-10)

**PRD-NEW – Onboarding-Wizard (Neue-Akte-Anlage)**
Stub `NeueAkteModal` existiert seit v54 in `AktensucheView.jsx` (AZ, Unfalldatum, Unfallort, Notizen). Echte Akte-Anlage-Logik fehlt vollständig. Hängt an PRD-22d-Konzept (neuer Mandant → Akte anlegen).
(aus: session_handover_v54.md, session_handover_v55.md)

**PRD-25c – Automatische Mandantenkommunikation**
`MandantenEmailDialog.jsx` nach Generierung von Forderungsschreiben / Regulierungsschreiben / Abrechnungsübersicht öffnen. 3 Textbausteine je Trigger, SMTP via `unfall@anwalt-offenbach.de`, neue DB-Tabelle `mandanten_emails`. 4 Sessions geplant.
PRD vorhanden: `handover/PRD-25c_Mandantenkommunikation.md`
(aus: session_handover_v55.md, session_handover_v56.md)

---

### Priorität: Mittel

**PRD-32 Phase 2 – Rechnungstypen-Parser: Beleg-Mapping**
Phase 1 (Subklassen im Classifier) ist fertig. Phase 2: erkannte Rechnungstypen automatisch der richtigen Schadenposition zuordnen (Standkosten → Standgeld-Position, Abschlepprechnung → Abschleppkosten-Position).
Plan: `handover/PRD-32_Rechnungstypen_Parser.md`
(aus: handover/backlog.md, session_handover_v55.md)

**PRD-05 – Betrag-Abgleich nach Upload**
Nach Hochladen einer Rechnung automatisch Betrag gegen Schadenposition abgleichen.
(aus: session_handover_v55.md)

**PRD-03 – Klagegenerator Abschlusstest**
Code wurde in v35–v36 implementiert und deployed. Ob ein formaler Abnahmetest je erfolgte, ist unklar. v55 listet ihn noch als offene MITTEL-Aufgabe.
(aus: session_handover_v55.md)

**PRD-29 – Schmerzensgeld-Ermittlungstool**
Modal im Klage-Wizard: KI recherchiert Vergleichsurteile (dejure.org, lexetius.com), Anwalt legt Mindestbetrag fest, KI generiert Klagetext → Übernahme in Klageschrift + Forderungsschreiben. Schema-Migration 36 + 3 neue Endpoints. Noch nicht begonnen.
Plan: `handover/PRD-29_Schmerzensgeld_Tool.md`
(aus: handover/PRD-29_Schmerzensgeld_Tool.md — fälschlicherweise als erledigt markiert, 2026-05-04 korrigiert)

---

### Priorität: Später

**PRD-01 – To-Do-System Vollausbau**
Basis (Header-Widget) vorhanden. Action Board deckt ca. 70 % des ursprünglichen Konzepts ab. Vollausbau (Aufgabenzuweisung, Fälligkeiten, Filterung) noch nicht begonnen.
(aus: session_handover_v55.md)

**PRD-06 – Parser Reparaturrechnung via LLM**
LLM-basierte Extraktion von Reparaturrechnungen, die nicht per Regex geparst werden können.
(aus: session_handover_v38.md, session_handover_v55.md)

**PRD-07 – Workflow-Regeln + automatische To-Dos**
Regelmaschine: bei bestimmten Ereignissen (z.B. Regulierungsschreiben eingegangen) automatisch To-Do anlegen.
(aus: session_handover_v55.md)

**PRD-17 – Tagesstart-Dashboard** `[refining]`
ActionBoardView (v56) erfüllt die Funktion vollständig. Wird als erledigt betrachtet; läuft in der Verfeinerungsphase (Fristen-Spalte, Nachrichten-Spalte).
(aus: session_handover_v38.md, session_handover_v55.md, session_handover_v56.md)

**~~PRD-19 – RA-Micro DMS Integration (Read-Only)~~** ✅
Vollständig implementiert in `DokumenteSection.jsx`: E-Akte-Card mit Lazy Load, Filter, Sort, Pagination, PDF-Vorschau, Einzel- und Bulk-Import.
(aus: session_handover_v55.md — als offen gelistet, Code aber fertig)

**PRD-21 Phase 3b – Batch-Klassifikation**
Mehrere E-Akte-Dokumente auf einmal klassifizieren.
(aus: session_handover_v38.md)

**PRD-21 Phase 3c – Filter nach Dokumentenklasse**
E-Akte-Ansicht nach Dokumentenklasse filtern.
(aus: session_handover_v38.md)

**PRD-04c – TF-IDF Classifier**
Statistischer Classifier als Ergänzung zum Regex-Dispatcher.
(aus: session_handover_v38.md)

**PRD-24b – Vollständiger 5-Step-Wizard**
Erweiterung des Klage-Wizards um Unfallhergang und Haftungsbegründung als eigene Wizard-Steps.
(aus: session_handover_v38.md)

**PRD-25d – Intelligente Sachstandsanfrage (STA)**
Automatisierter Versand von Sachstandsanfragen an den Versicherer nach konfigurierbaren Fristen.
PRD vorhanden: `handover/PRD-25d_Intelligente_Sachstandsanfrage.md`
(aus: session_handover_v38.md, backlog)

**Stakeholder-Portal (separates Projekt)**
Vier Phasen geplant. Kein Implementierungsstand im Unfallakten-Repo.
- PORTAL-A1: Unfallakten-Sync (`handover/PORTAL-A1_Unfallakten_Sync.md`)
- PORTAL-B1: Foundation (`handover/PORTAL-B1_Foundation.md`)
- PORTAL-B2: SV-Cockpit (`handover/PORTAL-B2_SV_Cockpit.md`)
- PORTAL-B3: Privatmandant (`handover/PORTAL-B3_Privatmandant.md`)
(aus: handover/PORTAL-*.md)

---

## 👤 UserStories (externes Review, Sprint 1)

> Quelle: Externes Review 2026-06-12. Eigenständige Sektion — nicht mischen mit internen PRDs.
> Gemeinsame Voraussetzung für US-01 + US-02: Background-Scheduler (APScheduler o.ä.) muss einmalig eingerichtet werden.

---

**~~PRD-US01 — RA-Micro Heartbeat & Verbindungs-Banner~~** ✅ *(Session 2026-06-12)*
Hintergrund-Task prüft alle 60s die RA-Micro-Verbindung; bei Abbruch erscheint ein Banner im Header.
- Backend: `verbindung_pruefen()` alle 60s in Background-Worker, Status im App-State (in-memory)
- Neuer Endpoint `GET /ramicro/status` liefert `{ ok, letzter_sync_vor_s }`
- Frontend: Header-Komponente pollt den Endpoint, zeigt Banner „RA-Micro nicht erreichbar — letzter Sync vor X Minuten"
- Automatische Wiederverbindung nach erfolgreicher Prüfung

**~~PRD-US02 — IMAP Auto-Polling~~** ✅ *(Session 2026-06-12)*
E-Mail-Import läuft automatisch für alle vier Accounts (unfall@, termin@, bussgeld@, info@) ohne manuellen Klick.
- APScheduler-Job alle 60s, importiert pro Account wenn konfiguriertes Intervall abgelaufen (Standard: 5 min)
- Per-Account Toggle + Intervall (5/10/15/30 min) im Health-Dashboard konfigurierbar
- Schema-43: `imap_polling_config`, Endpoint `GET/PATCH /system/imap-polling`, 31 Tests

**PRD-US03 — SV-Portal: Upload-Empfang (Kanzlei-Seite)** *(aus S1.3 Teil A, P0, Aufwand: L)*
Das Kanzlei-Backend nimmt Datei-Uploads vom SV-Portal-Server entgegen und verknüpft sie mit der Akte.
- Neuer Endpoint `POST /sv-portal/upload` (Auth via API-Key oder JWT)
- Empfangene PDFs landen als Dokument in der Akten-Dokumente-Liste (innerhalb 30s sichtbar)
- Audit-Trail-Tabelle: `sv_portal_uploads` (sv_id, az, dateiname, zeitstempel, hochgeladen_von)
- Action Board: Neuer Eintrag bei eingehendem Upload (eigene Notification-Gruppe)
- **Voraussetzung: PRD-US04 muss existieren** — ohne Gegenstelle gibt es niemanden, der uploadet

**PRD-US04 — SV-Portal-Server (Gegenstelle)** *(aus S1.3 Teil B, P0, Aufwand: XL — eigenes Projekt)*
Der SV-Portal-Server ist eine eigenständige Web-Applikation, auf die Sachverständige zugreifen.
- Entspricht `handover/PORTAL-B2_SV_Cockpit.md` — dort liegt die Planung
- SV authentifiziert sich, sieht seine zugewiesenen Akten, lädt PDFs hoch
- Sendet Uploads via REST an PRD-US03-Endpoint des Kanzlei-Backends
- Dieses PRD ist **nicht im Unfallakten-Repo** umsetzbar — separates Deployment nötig
- Blockiert: PRD-US03 ist ohne dieses System nicht testbar

**~~PRD-US05 — E-Akte Hover-Vorschau im Dashboard~~** ✅ *(Session 2026-06-15)*
In der Akten-Suchliste zeigt ein Hover eine kleine Dokumenten-Vorschau der E-Akte.
- Hover über Akten-Zeile in `AktensucheView` → Tooltip/Popover mit den letzten 3–5 E-Akte-Dokumenten
- Klick auf Dokument im Hover → öffnet Akten-Detail direkt im Dokumente-Tab
- Kein neuer API-Endpoint nötig (bestehender `GET /akten/<az>/eakte/liste` reicht)

**~~PRD-US06 — Health-Dashboard UI~~** ✅ *(Session 2026-06-12)*
Neuer Tab „System-Status" in den Einstellungen fasst alle Service-Indikatoren auf einer Seite zusammen.
- Tab „System-Status" in `EinstellungenView.jsx` (neben den bestehenden Tabs)
- 5 Indikatoren mit Grün/Gelb/Rot + Last-Sync-Timestamp:
  - RA-Micro (nutzt `GET /wiedervorlage/status`)
  - IMAP `unfall@`, `termin@`, `bussgeld@` (nutzt `GET /email/import/status`, aufgeteilt pro Account)
  - SV-Portal (nutzt ggf. PRD-US03-Status-Endpoint)
- Polling alle 30s im Frontend; keine neuen Backend-Endpoints nötig (Daten existieren bereits)

---

## ❓ Unklar

**PRD-29 DKz-Filter: erledigt oder offen?**
`session_handover_v56.md` nennt „PRD-29 DKz-Filter: noch nicht gestartet". `handover/PRD-29_EAkte_Filter_DKz.md` sagt `✅ Implementiert` — das DKz-Feld existiert in der DB nicht, daher Lösung via Schlagwort `E-Brief`. Ist damit das ursprüngliche Ziel als vollständig erfüllt zu betrachten?
(aus: session_handover_v56.md vs. handover/PRD-29_EAkte_Filter_DKz.md)

**PRD-03 Abschlusstest**
`session_handover_v55.md` listet „PRD-03 Klagegenerator Abschlusstest" als offene MITTEL-Aufgabe. Code wurde in v35–v36 implementiert. Ob ein Integrationstest jemals formal durchgeführt wurde, geht aus den Handovers nicht hervor.
(aus: session_handover_v55.md, session_handover_v38.md)

