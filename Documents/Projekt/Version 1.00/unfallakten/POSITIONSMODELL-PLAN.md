# Positionsmodell-Plan: Ereigniszentrisches Positions-/Aktionsmodell

Koch, Schatz & Kollegen · Stand: 2026-07-07 · Schema-Version 45
Setzt auf: `PIPELINE-REFACTORING-PLAN.md` (Dokument/Zustellung, Review-UI, Registry) und `extraktions-pipeline-v7.mermaid`.
Status: **Planungsdokument — keine Implementierung. Freigabe durch RA Schatz erforderlich.**

Nicht verhandelbare Design-Entscheidungen (Zielmodell):
1. **Ereignis-Tabelle als Quelle der Wahrheit** (Ebene 1). Ein Dokument ist der wichtigste Ereignis-Lieferant, aber nicht das Ereignis selbst. Ereignisse werden **nie gelöscht**, nur per `ersetzt_durch` versioniert; ersetzte Ereignisse fließen nicht in die Statusableitung.
2. **Quellen in Stufe 1 hart begrenzt**: `dokument` (eingehend via Review-Freigabe — die Pipeline schlägt vor, schreibt nie selbst; ausgehend durch jede ausgeführte Aktion) und `system` (Fristablauf). `manuell` wird im Enum **vorgesehen, aber nicht implementiert**.
3. **Aktenkonto/Zahlungseingänge sind außerhalb des Modells** (HBCI → RA-MICRO, tabu). Positionsscharfe Regulierung kommt aus dem Abrechnungsschreiben-Ereignis.
4. **Ebene 2 = materialisierter Cache** (Ereignis-/Belegliste je Position), schreibzeit-aktualisiert, jederzeit aus Ebene 1 rekonstruierbar, Rebuild-Funktion Pflicht.
5. **Status ist Ableitung, kein Label.** Positionszustand, offener Betrag, Eskalationsstufe ausschließlich aus aktuellen Ebene-1-Ereignissen. Jede Anzeige trägt ihre Wissensgrenze („nach Aktenlage, letztes Ereignis vom …").
6. **Aktionen haben Scope** (dokument/position/akte) über eine konfigurierte Type-Action-Matrix (Registry-Erweiterung). Bedingungen steuern Vorschläge und Sortierung, **nie Verbote**; die globale Aktionsleiste wird ergänzt, nicht entfernt.

---

## 1. Ist-Zustand (Durchgang 1)

Nur Fakten, keine Bewertung. Codeverweise: Datei:Funktion (Zeile).

### 1.1 Dokument↔Position-Verknüpfungen — was existiert

| Struktur | Art | Details |
|---|---|---|
| `schadenposition_belege` (Mig 27) | **echte n:m-Verknüpfung** Dokument↔Position | Spalten akte_az, position_key, dokument_id, betrag_aus_beleg, UNIQUE(akte_az, position_key, dokument_id). Schreiben/Lesen: belege_routes.py (GET Z. 350–387, POST mit INSERT OR REPLACE Z. 427–433, DELETE Z. 443–464). Frontend: DokumenteSection.jsx `handleInlineAnnehmen` (Z. 513–540). Rein assoziativ — kein Datum, keine Richtung, keine Historie. |
| `abrechnungsschreiben` → `regulierung_positionen` | 1:n je Dokument | abrechnungsschreiben.dokument_id → dokumente(id); Positionen mit betrag_gefordert/betrag_reguliert, kuerzungsart_id, `fuer_klage_vorgemerkt`, `sv_stellungnahme_ausstehend` (Auto-Setzung aus kuerzungsarten.sv_stellungnahme_erforderlich, abrechnungsschreiben.py Z. 358–366). Befüllung: manuell (ReguWizard), Parser, WDM-Import. Gespeicherte Aggregate gesamt_gefordert/gesamt_reguliert werden an zwei Schreibstellen nachgeführt (Z. 385–391, 508–524). |
| `forderung_positionen` (Mig 9) | Snapshot je ausgehendem Forderungsschreiben | dokument_id, forderungsschreiben_nr (1, 2, …), position_key, betrag_gefordert, **gespeicherter** `status` (gefordert/teilreguliert/vollreguliert/gekuerzt/abgelehnt), fuer_klage. Geschrieben von forderung.py: `erfasse_forderung()` (Z. 111–205) — nur bei Variante „hoehe". |
| `KLASSE_TO_POS`-Mapping (PRD-34) | Dokumentklasse → Positions-Key, **hartkodiert und dupliziert** | Backend `_KLASSE_POSITION_MAP` (belege_routes.py Z. 136–145) und Frontend `KLASSE_TO_POS` (constants.js Z. 514–521) — zwei unabhängige Kopien, inkl. Sonderfall `__sv_kosten_vorsteuer__`. |
| `stellungnahme_texte` (Mig 40) | Texte je Kürzungsgruppe | PK (az, gruppe_key); gruppe_key koppelt indirekt an Position+Kürzungsart, kein FK. |

**Keine chronologische Ereignis-/Historienstruktur pro Position.** `aktivitaeten` loggt nur auf Akten-Ebene (aktion/beschreibung/aenderung_json), keine Positions-Granularität. `schadenpositionen` ist **ein Datensatz pro Akte** (INSERT OR UPDATE, spaltenbasiert — eine Spalte je Positionsart): jede Änderung überschreibt, Historie geht verloren.

### 1.2 Wo werden Aktionen heute ausgelöst — Scope-Inventur

| Aktion | heutiger Scope | Auslöser im Code | Ausgehendes Dokument registriert? | Positions-Ereignis? |
|---|---|---|---|---|
| Klage | Position (fuer_klage_vorgemerkt) → Wizard | KlageSection.jsx 10-Step-Wizard → klage_routes.py:1146 `generiere_klage` | ja: dokumente, typ=`klage` (Z. 1381 f.) | **nein** — keine Rückschreibung an Positionen |
| Stellungnahme (PRD-27) | **Dokument** (abrechnungsschreiben_id, optional alle) | stellungnahme_routes.py:33 `generiere` (Body Z. 55, Kürzungsprüfung Z. 72–87) | ja, aber **typ=`sachstandsanfrage`** (Z. 140 — falsch benannt) | nein |
| Sachstandsanfrage | Akte | sta_routes.py:63; Stufen-Empfehlung sta_service.py `_empfohlene_stufe` (Z. 229–235, ad-hoc aus tage_ohne_antwort + sta_anzahl, **nichts gespeichert**) | ja: typ=`sachstandsanfrage` | nein |
| Forderungsschreiben | Akte (alle offenen Positionen) | word_service.py:76 `generiere_und_speichere` → `generiere_forderungsschreiben_wv` (Z. 126) | ja: typ=`forderungsschreiben` | **teilweise**: forderung_positionen-Snapshot (nur Variante „hoehe", Z. 186–193) |
| Kostennote (PRD-28) | Akte | gebuehren_routes.py:236 → gebuehren_word.py:63 | ja: typ=`sonstiges` | nein |
| „Für Klage vormerken" | **Position** (einzige echte Positions-Aktion) | RegulierungSection.jsx PositionenTabelle (Z. 100–108) → Flag-Update | — | Flag, kein Ereignis |

Zusätzlich: word_service.py mappt den Dok-Typ `sachstandsanfrage` beim Registrieren auf `sonstiges` (Z. 158) — **inkonsistent** zu sta_routes.py, das `sachstandsanfrage` schreibt. Ein Versanddatum/Zugangsnachweis existiert nirgends; `dokumente.hochgeladen_am` = Generierungszeitpunkt.

### 1.3 Ausgehende Dokumente — Datenhaltung

Alle Generierungs-Endpunkte registrieren das DOCX in der **eigenen** `dokumente`-Tabelle (`registriere_dokument()`), zusätzlich Download-Response. Nichts davon landet in RA-MICRO (kein Schreibweg, vgl. PIPELINE-REFACTORING-PLAN.md Gap #17). Eine Richtungs-Kennzeichnung (eingehend/ausgehend) existiert in `dokumente` nicht — ausgehende Schreiben sind nur am `typ` erkennbar, der (s. o.) inkonsistent vergeben wird.

### 1.4 Fristen-/Wiedervorlagenlogik als Kandidat für Quelle `system`

- `fristen_service.py`: `setze_verjaerungs_fristen()` (Z. 32–90, §199 BGB, regel_keys verjährung_2m/_1m/verjährung), `setze_pflvg_frist()` (Z. 93–118), `setze_antwort_frist()` (Z. 121–154, regel_key `antwort_2w_{dok_id}`, mit dok_id-Referenz!). Alle schreiben `todos` mit `quelle='system'`, idempotent über regel_key (`_todo_existiert`, Z. 159–167).
- Auslösung nur **beim Schreiben** (Akte-Anlage: akten_routes.py:293/370; Dokument-Generierung: word_service.py:199–200). **Kein Scheduler prüft Fristablauf** — APScheduler fährt heute nur health_ramicro + imap_polling (app.py Z. 181–205). Ein „Fristablauf" ist heute eine fällige todo-Zeile, kein Ereignis.
- STA-Eskalation: konfigurierbar (konfiguration-Keys sta_stufe1–3_tage, sta_service.py Z. 195–209), Stufe wird bei jedem Aufruf neu berechnet — bereits ein Beispiel gelebter Ableitung statt Speicherung.
- Wiedervorlagen: read-only aus RA-MICRO (`tblAktenWiedervorlagen`, wiedervorlage_service.py Z. 94–236) — reine Anzeige im Action Board, keine lokale Logik.

### 1.5 Status- und Betragsanzeigen heute

- `v_regulierungsstatus` (schema.py Z. 186–203): betrag_gefordert aus `v_schadensummen` (mit bekanntem Legacy-Feld-Fehler F-01/P-04), betrag_reguliert = SUM(regulierung_positionen.betrag_reguliert), differenz.
- **Gespeicherte Statuswerte:** `unfallakte.status` (manuell via PATCH, akten_routes.py Z. 318–372), `unfallakte.regulierung_status` (Mig 45, gespeicherte Spalte mit Auto-HQ-Seiteneffekt: 'abgelehnt'→HQ 0, 'offen'→HQ 100, akten_routes.py Z. 352–357), `forderung_positionen.status`, `regulierung.status` (deprecated), Flags fuer_klage_vorgemerkt / sv_stellungnahme_ausstehend, denormalisierte gesamt_gefordert/gesamt_reguliert.
- Frontend rechnet parallel: `calcBrutto()`/`ermittleAbrechnungsart()` in SchadenSection.jsx (Z. 189–200) und App.jsx spiegeln die Python-Logik aus models/schaden.py — zwei Implementierungen derselben Ableitung.
- Vollständigkeits-Checks: nur punktuell (Mandant/IBAN in dashboard_routes.py `_lade_onboarding_offen` Z. 315–335; IBAN-Check UebersichtSection.jsx Z. 101–108). **Keine Beleg-Checkliste pro Positionsart.**
- Nächster-Schritt-Vorschläge: dashboard_routes.py `_lade_akten_ohne_bewegung` (Z. 249–294) schlägt akten-weit „sachstandsanfrage"/„klage_pruefen" vor — nicht positionsscharf.

---

## 2. Befunde (Durchgänge 2–4)

### 2.1 Durchgang 2 — Fehlerarchitektur-Abgleich

| Fehlerklasse | Vom Ist-Code reproduziert? | Vom Zielmodell reproduziert? |
|---|---|---|
| **Cache-Drift** | **Ja, dreifach**: (a) gesamt_gefordert/gesamt_reguliert werden an genau 2 Schreibstellen nachgeführt — der WDM-Import und Lösch-Pfade können vorbei schreiben; (b) `v_schadensummen` driftet architektonisch (Legacy-Feld, F-01); (c) Frontend-Zwilling calcBrutto ↔ Python gesamt_brutto — zwei Implementierungen, die auseinanderlaufen können. | Nur wenn Ebene 2 mehrere Schreibpfade bekommt. Gegenmaßnahme im Entwurf: **ein einziger Event-Append-Punkt** (`ereignis_service.schreibe_ereignis()`) aktualisiert Cache in derselben Transaktion; Rebuild-Funktion + Drift-Test (Nightly-Vergleich Rebuild vs. Cache) sind Pflichtbestandteil (Abschnitt 4.4). |
| **Fehlende Versionierung ersetzender Einträge** | **Ja**: `schadenpositionen` = 1 Zeile/Akte, Ergänzungsgutachten **überschreibt** Werte (INSERT OR UPDATE); regulierung_positionen werden in place editiert; stellungnahme_texte nur geaendert_am, kein Vorher. | Nein — `ersetzt_durch` ist Kernfeld. Restrisiko: Ableitung muss ersetzte Ereignisse **wirklich** ausschließen (WHERE ersetzt_durch IS NULL); als Invariante in die Ableitungsfunktion + Test (Durchgang 3c). |
| **1:1-Zwang statt n:m** | **Teilweise**: schadenposition_belege ist n:m ✅; aber Abrechnung→Positionen hängt an genau einem Dokument, Stellungnahme referenziert genau ein Abrechnungsschreiben, KLASSE_TO_POS mappt 1 Klasse → 1 Position. | Nein — `ereignis_positionen` ist n:m by design. Achtung Sonderfall Pauschalvergleich (2.3/Durchgang 4). |
| **Hartkodiertes Actionset** | **Ja**: Aktions-Buttons fest in Sections verdrahtet; KLASSE_TO_POS doppelt (Backend+Frontend); Dok-Typ-Enum als CHECK-Constraint in dokumente. | Nein — Type-Action-Matrix als Registry-Konfiguration (Abschnitt 5). Restrisiko: Frontend muss Matrix generisch rendern, sonst entsteht die zweite Hardcoding-Schicht im JSX. |
| **Gespeicherte statt abgeleitete Aggregate** | **Ja, massiv**: unfallakte.status, unfallakte.regulierung_status (Mig 45 — erst am 2026-06-22 gebaut!), forderung_positionen.status, fuer_klage_vorgemerkt, sv_stellungnahme_ausstehend, gesamt_gefordert/gesamt_reguliert. | Nein per Definition. Konfliktpunkt: Was passiert mit den **bestehenden** gespeicherten Werten → Offene Fragen PF-01/PF-09. |
| **Doppelte Schreibpfade am Freigabeprinzip vorbei** | **Ja**: WDM-Import schreibt regulierung_positionen direkt; Fragebogen-Enrichment schreibt Beteiligte/Unfalldetails direkt; Parser-Auto-Import ≥ 0.85 (fällt mit Pipeline-S1.9). | Gefahr besteht in der Übergangszeit: solange ReguWizard/WDM parallel zur Ereignis-Schicht schreiben, gibt es zwei Wahrheiten → Übergangsregel in Abschnitt 7 (jeder Alt-Schreibpfad erzeugt ereignisseitig einen Eintrag, bis er abgelöst ist). |
| **Vollständigkeitsillusion** | **Ja**: v_regulierungsstatus zeigt „betrag_reguliert" als vollständig, kennt aber nur erfasste Abrechnungsschreiben; ein kommentarlos zahlender Versicherer ist unsichtbar. „Akten ohne Bewegung" misst nur lokale Aktivität. | **Ja, strukturell** — Stufe 1 kennt nur dokument+system: Telefonate, mündliche Zusagen, kommentarlose Zahlungen sind unsichtbar. Genau dafür ist die Wissensgrenzen-Pflicht im UI da; zusätzlich Befund 2.3 und PF-07. |

### 2.2 Durchgang 3 — Rollen-Divergenz

**a) Sachbearbeiter.** Heute sieht er: Beträge je Abrechnungsschreiben (RegulierungSection), Akten-Summen (v_regulierungsstatus), akten-weite Vorschläge (Action Board). Er sieht **nicht**: den Zustand je Position über alle Abrechnungsschreiben hinweg, den offenen Betrag je Position, den nächsten Schritt je Position (STA-Stufe existiert nur akten-weit). Das Zielmodell liefert genau das über die Ableitung auf Ebene 2 — Voraussetzung: die Ableitung läuft im **Backend** (ein Endpoint), nicht als dritter Frontend-Zwilling neben calcBrutto.

**b) Entwickler in einem Jahr.**
- *Neue Positionsart heute:* Spalte(n) in `schadenpositionen` (Migration!), POSITION_KEYS-Enum (models/abrechnungsschreiben.py), `_schaden_dict()`, `_hole_schaden_spalten`, KLASSE_TO_POS ×2, WDM-Maps, calcBrutto im Frontend, Formularfelder — **7+ Stellen, davon 1 Migration**. Ursache: spaltenbasiertes Positionsmodell.
- *Im Zielmodell:* Positionsart = Eintrag in `positionsarten`-Konfiguration (Label, Kategorie, Checkliste) — solange die Beträge weiter aus den bestehenden Tabellen kommen, bleibt deren Spaltenproblem bestehen (bewusst: Ablösung des Spaltenmodells ist Stufe P3, nicht P1). Neuer **Ereignistyp** = Konfig-Eintrag. Neue **Dokumentklasse** = Klassen-YAML (Pipeline-Plan S1.5) + Matrix-Zeilen. Ziel „nur Konfiguration" wird für Ereignistyp/Dokumentklasse voll, für Positionsart erst ab P3 erreicht → ehrlich so ausweisen.

**c) Ersetzender Beleg (Ergänzungsgutachten).** Heute: Dispatcher parst, KI-Dialog bestätigt, Werte **überschreiben** die eine schadenpositionen-Zeile — die alte Zahl ist weg (bestenfalls in aktivitaeten.aenderung_json). Im Zielmodell: neues Ereignis `gutachten_eingegangen` (n:m auf die geänderten Positionen), altes Ereignis bekommt `ersetzt_durch=<neu>`; Ableitung ignoriert es, die Ebene-2-Liste zeigt es als „ersetzt" (Nachvollziehbarkeit im Streitfall). **Kante:** Ein Ergänzungsgutachten ersetzt oft nur *einzelne* Positionen des Erstgutachtens. Da die Betragswirkung in `ereignis_positionen` (pro Position) liegt, muss `ersetzt_durch` **positionsscharf** wirken können → Entwurfsentscheidung: `ersetzt_durch` liegt auf der n:m-Zeile, nicht (nur) auf dem Ereigniskopf (Abschnitt 4.2). Sonst verschwände beim Teilersatz das ganze Erstgutachten aus der Ableitung — der klassische Doppel-/Verschwinde-Fehler.

**d) Drift-Opfer.** Codepfade, die Ebene 2 an Ebene 1 vorbei ändern könnten: (1) direkte UPDATEs aus Alt-Routen (abrechnungsschreiben_routes nutzt rohes sqlite3 mit PRAGMA foreign_keys=OFF — bekanntes Muster!), (2) WDM-Import, (3) Reparaturskripte im Root (fix_*.py-Kultur), (4) künftige Entwickler, die den Cache „mal eben" patchen. Gegenmaßnahmen im Entwurf: Cache-Tabelle wird von genau einem Modul beschrieben; Rebuild-Funktion + automatischer Drift-Check; Konvention „Cache-Tabelle taucht in keinem anderen Modul in einem UPDATE/INSERT auf" als Test (grep-basierter Guard-Test ist im Projekt etabliert, vgl. test_kein_fastapi). **Wissensgrenze:** darf nicht pro View einzeln gebaut werden, sonst fehlt sie irgendwo — der Ableitungs-Endpoint liefert `stand` (Datum des letzten aktuellen Ereignisses) als Pflichtfeld, das Frontend rendert es über eine gemeinsame Badge-Komponente (Abschnitt 6).

### 2.3 Durchgang 4 — Problem-Rahmung

Deckt „Ereignis berührt Position, Position hat abgeleiteten Zustand" die Praxis ab?

- **Dokumente ohne Positionsbezug** (Vollmacht, gerichtliche Verfügung, Terminladung, Vergleichsangebot über die Gesamtakte): Als **Akten-Scope-Ereignis** abbilden — Ereignis mit leerer Positionsmenge ist zulässig. Wichtig für die Checkliste: die Vollmacht ist checklisten-relevant (Klagebereitschaft), also braucht sie ein Ereignis, auch ohne Positionswirkung. Dokumente ganz ohne Ereignis bleiben möglich (z. B. reine Info-Post) — die Freigabe in der Review-UI schlägt dann schlicht kein Ereignis vor.
- **Haftungsquote**: Akteneigenschaft mit Wirkung auf **alle** Ableitungen (offener Betrag = gefordert × Quote − anerkannt). Heute dreifach vorhanden (unfallakte.haftungsquote, abrechnungsschreiben.haftungsquote, regulierung_status-Auto-HQ). Rahmung: Quotenänderung ist ein **Akten-Scope-Ereignis** (Quelle dokument: Abrechnungsschreiben mit haftungsart-Angabe), die Ableitung nutzt die Quote des jüngsten aktuellen Ereignisses; das Feld unfallakte.haftungsquote bleibt als Anzeige-Cache (PF-03).
- **Pauschalvergleich („8.000 € auf alles")**: schließt alle Positionsketten. Rahmung: Ereignistyp `vergleich` mit **expliziter** n:m auf alle zum Zeitpunkt offenen Positionen (Wirkungsart `erledigt`), Betragswirkung am Ereigniskopf (Gesamtbetrag, bewusst **nicht** auf Positionen verteilt — die Verteilung wäre erfunden). Implizite „gilt für alles"-Semantik wird vermieden, weil sie bei später nacherfassten Positionen falsch würde. Konsequenz: die Ableitung „offener Betrag" je Position zeigt nach Vergleich `erledigt (durch Vergleich vom …)` statt einer Zahl.
- **In Stufe 1 unsichtbare Kanzleivorgänge** (weder dokument- noch system-Ereignis):
  | Vorgang | Unsichtbar? | Akzeptabel? |
  |---|---|---|
  | Telefonat/Telefonvermerk mit Versicherer | ja | Ja — bewusste Entscheidung (manuell erst mit Diktat-Tool); Wissensgrenze macht es ehrlich. |
  | Mandantenweisung („nicht klagen") | ja | Grenzwertig: die Eskalationsableitung schlägt dann Klage vor, obwohl der Mandant sie ausschloss. In Stufe 1 akzeptabel, weil Vorschläge nie Verbote sind; als erster manueller Ereignistyp für Stufe 2 vormerken (PF-07). |
  | Kommentarlose Zahlung ohne Abrechnungsschreiben | ja | **Kritischster Fall** — Position bleibt „offen/bestritten", obwohl bezahlt. Mitigation: lesender Aktenkonto-Plausibilitätshinweis (2.4); vollständige Lösung erst mit manuellem Ereignis/Stufe 2 (PF-07). |
  | Mündliche/außergerichtliche Einigung | ja, bis das Bestätigungsschreiben eingeht | Akzeptabel — das Bestätigungsschreiben ist der übliche und dokumentierte Abschluss. |
  | Klage **eingereicht** vs. nur generiert | teilweise (Generierung ≠ Versand/Einreichung) | Ehrlichkeit über Ereignistyp-Wortlaut lösen: `klage_generiert`, nicht `klage_erhoben` (PF-04). |

### 2.4 Optionaler Prüfauftrag: lesender Plausibilitätscheck Aktenkonto

**Nur Machbarkeits-Bewertung, keine Einplanung** (Vorgabe).
- *Technisch:* Der read-only-pymssql-Zugang zur RAMICRO-DB existiert und ist erprobt (connector.py, wdm_regulierung_service.py als Muster inkl. deutschem Betragsformat-Parsing). Ein Aktenkonto-/Forderungskonto-Lesezugriff wäre derselbe Mechanismus: SELECT je Akte, Summierung der Zahlungseingänge. **Die konkrete Tabelle ist im Code nirgends referenziert** und muss erst am Live-System identifiziert werden (RA-MICRO-üblich: Forderungskonto-/Aktenkonto-Buchungstabellen) — Aufwand der Identifikation unbekannt, der Anbindung danach S–M.
- *Fachlich:* Das Aktenkonto kennt **keine Positionen** — möglich ist ausschließlich der Vergleich *Gesamteingang lt. Aktenkonto* vs. *Summe anerkannter Beträge lt. Abrechnungsschreiben-Ereignissen*. Differenz > Toleranz → Hinweis „Zahlungseingang ohne erfasstes Abrechnungsschreiben?" bzw. umgekehrt. Genau das adressiert den kritischsten Blindfleck aus 2.3 (kommentarlose Zahlung) als **Hinweis, nie als Ereignis oder Routing**.
- *Risiko:* gering (read-only, RAMICRO_AKTIV-Muster vorhanden); Fehlerquelle Fremdgeld vs. Gebühren im Konto (Buchungsarten müssen gefiltert werden).
- **Bewertung: machbar und sinnvoll als Stufe-2-Kandidat. Wird hier nicht eingeplant.** HBCI-Import und Aktenkonto-Datenhaltung bleiben unangetastet (tabu).

---

## 3. Offene Fragen

**PF-01 — regulierung_status (Mig 45): behalten oder ableiten?**
Die Kachel ist erst am 2026-06-22 gebaut worden; im Zielmodell ist der Wert ableitbar (haftungsart der jüngsten Abrechnungsschreiben-Ereignisse: ablehnung→abgelehnt, quote/mithaftung→teilhaftung).
*Empfehlung:* Spalte und Kachel in Stufe P1 unangetastet lassen; in P2 wird der Wert abgeleitet und die Spalte zum reinen Anzeige-Cache degradiert (kein manuelles Setzen mehr, Auto-HQ-Seiteneffekt entfällt — **BREAKING**, gekennzeichnet). *Begründung:* Frisch gebaute, benutzte UI nicht sofort wieder umbauen; aber zwei Wahrheiten (gespeichert vs. abgeleitet) dürfen nicht dauerhaft koexistieren.

**PF-02 — Was ist „gefordert"? schadenpositionen oder Forderungs-Ereignis?**
`schadenpositionen` enthält, was gefordert werden *könnte* (Kalkulationsgrundlage aus Gutachten/Belegen); rechtlich gefordert ist erst, was im Forderungsschreiben steht.
*Empfehlung:* Ableitung „gefordert je Position" = jüngstes aktuelles **ausgehendes** Ereignis mit Wirkungsart gefordert (Forderungsschreiben, Klage). Vor dem ersten Forderungsschreiben zeigt das Dashboard ehrlich „kalkuliert X € — noch nicht gefordert". schadenpositionen bleibt unverändert Erfassungsort der Kalkulation. *Begründung:* Deckt sich mit der bestehenden forderung_positionen-Semantik (Snapshot je Schreiben) und macht die Eskalationsableitung erst korrekt (ohne Forderung keine Verzugseskalation).

**PF-03 — Haftungsquote: Ereignis, Feld oder beides?**
*Empfehlung:* Beides — Feld `unfallakte.haftungsquote` bleibt (zig Konsumenten: Klage-Wizard, Gebühren, Frontend); jede Änderung erzeugt zusätzlich ein Akten-Scope-Ereignis `haftungsquote_geaendert` (Quelle dokument bei Abrechnungsschreiben, sonst im Rahmen der jeweiligen Aktion). Die Positions-Ableitung liest die Quote aus dem jüngsten Ereignis, fällt ohne Ereignis auf das Feld zurück. *Begründung:* Feld-Ablösung wäre ein Querschnitt-Umbau durch das halbe System — unverhältnismäßig für Stufe 1; das Ereignis sichert trotzdem die Nachvollziehbarkeit im Streitfall.

**PF-04 — Generierung ≠ Versand: Was ist das Ereignisdatum?**
Heute existiert kein Versanddatum (Befund 1.2); ein Pflicht-Klick „versandt am" wäre faktisch eine manuelle Quelle, die Stufe 1 ausschließt.
*Empfehlung:* Ereignis entsteht bei Generierung, Ereignistypen heißen ehrlich `*_generiert`; optionales nullable Feld `versand_bestaetigt_am` am Ereignis (Ein-Klick-Bestätigung, kein Zwang, keine eigene Quelle). Eskalationsableitung rechnet ab Generierungsdatum + Karenz. *Begründung:* In der Kanzleipraxis liegen Generierung und Versand fast immer am selben Tag; ein Zwangsfeld erzeugt genau das Erfassungsdisziplin-Risiko, das Stufe 1 vermeiden soll.

**PF-05 — Positions-Identität: position_key-Katalog oder Instanz-Tabelle?**
*Empfehlung:* Stufe 1 arbeitet mit den bestehenden `position_key`-Strings (POSITION_KEYS-Katalog inkl. sonstiges_wdm_1–6) als Positions-Identität je Akte; die neue `positionsarten`-Konfiguration beschreibt die Arten (Label, Kategorie, Checkliste), keine Instanzen. *Begründung:* Kompatibilität mit regulierung_positionen, forderung_positionen, schadenposition_belege ohne Umschlüsselung; eine Instanz-Tabelle (mehrere gleichartige Positionen) wird erst nötig, wenn das Spaltenmodell fällt (P3).

**PF-06 — Migrations-Nummern und Reihenfolge zur Intake-Planung**
PIPELINE-REFACTORING-PLAN.md reserviert Migrationen 46–49.
*Empfehlung:* Positionsmodell = Migrationen 50 ff.; wird das Positionsmodell **vor** der Intake-Stufe 1 umgesetzt, Nummern beim Implementieren fortlaufend neu vergeben (Nummern sind hier Platzhalter). *Begründung:* schema_manager vergibt strikt fortlaufend; ein Nummern-Konflikt zwischen zwei Plänen darf nicht in Code enden.

**PF-07 — Blindfleck „kommentarlose Zahlung" und „Mandantenweisung": bis wann akzeptabel?**
Beide sind in Stufe 1 unsichtbar (Befund 2.3).
*Empfehlung:* Akzeptieren mit zwei Leitplanken: (a) Aktenkonto-Plausibilitätshinweis (2.4) als frühes P2-Feature einplanen lassen, (b) `mandantenweisung` und `zahlung_ohne_abrechnung` als erste manuelle Ereignistypen der P2-Konzeption vormerken (Enum-Werte existieren ab Tag 1). *Begründung:* Beide Fälle betreffen die Korrektheit des vorgeschlagenen nächsten Schritts — das ist verkraftbar (Vorschlag ≠ Verbot), aber nicht dauerhaft.

**PF-08 — WDM-Regulierungsimport: welche Quelle?**
WDM-Daten sind weder Dokument noch Fristablauf; heute schreibt der Import regulierung_positionen direkt.
*Empfehlung:* WDM-Import erzeugt künftig einen **Ereignis-Vorschlag** (analog Pipeline-Vorschlägen), den der Sachbearbeiter bestätigt — Quelle bleibt `dokument` mit dokument_id=NULL und Herkunftsvermerk `wdm` im Ereignis (kein neuer Quellen-Enum-Wert). In der Übergangszeit (P1) schreibt der Import zusätzlich zum Alt-Pfad ein unbestätigtes Ereignis. *Begründung:* WDM spiegelt inhaltlich ein Abrechnungsschreiben, das in RA-MICRO erfasst wurde — es ist dieselbe Ereignisklasse, nur ein anderer Lieferweg; ein eigener Quellen-Wert würde die harte Stufe-1-Begrenzung aufweichen.

**PF-09 — fuer_klage_vorgemerkt / sv_stellungnahme_ausstehend: Flags ablösen?**
Beide sind gespeicherte Arbeitszustände, die der Klage-Wizard bzw. der SV-Workflow konsumiert.
*Empfehlung:* In Stufe P1 unangetastet lassen (Klage-Wizard funktioniert unverändert); in P2 prüfen, ob „für Klage vorgemerkt" als Vormerkungs-Ereignis und „SV-Stellungnahme ausstehend" als Ableitung (Kürzungsart mit sv_stellungnahme_erforderlich + kein SV-Stellungnahme-Eingangs-Ereignis) abgebildet wird. *Begründung:* Arbeitslisten-Flags sind kein Aktenstatus; sie zuerst zu migrieren brächte Risiko ohne Erkenntnisgewinn für das Kernmodell.

**PF-10 — Ereignis-Referenz: dokumente.id oder intake_dokumente.id?**
*Empfehlung:* `ereignisse.dokument_id` → **dokumente(id)** — also die Zeile, die die Review-Freigabe (Pipeline S1.8) über den output_adapter erzeugt. Die Zustellungshistorie bleibt über intake_dokumente/zustellungen erreichbar (dokumente-Zeile trägt künftig die intake-Referenz). *Begründung:* Ereignisse entstehen per Definition erst **bei/nach** Freigabe; vor der Freigabe gibt es nur Vorschläge. Damit ist auch der Nicht-Pipeline-Fall (Word-Generierung ausgehend) einheitlich, denn auch der registriert dokumente-Zeilen. **Kompatibilitäts-Hinweis:** Der Pipeline-Plan muss dafür an einer Stelle ergänzt werden — die Freigabe (S1.8) liefert künftig neben der dokumente-Zeile auch die **Ereignis-Vorschläge** zur Bestätigung (siehe Abschnitt 7, Kopplung K-2). Kein Widerspruch, aber eine Erweiterung des dortigen Freigabe-Schritts.

**PF-11 — Stellungnahme-Dokumenttyp-Bug beheben?**
stellungnahme_routes.py registriert mit typ='sachstandsanfrage' (Z. 140); word_service mappt 'sachstandsanfrage'→'sonstiges'. Der dokumente.typ-CHECK kennt 'stellungnahme' nicht.
*Empfehlung:* Im Zuge von P1.4 beheben (CHECK-Erweiterung per Tabellen-Rebuild-Muster oder — einfacher — Ereignistyp statt dokumente.typ als maßgebliche Semantik; dann genügt es, den Ereignistyp korrekt zu setzen und der dokumente.typ-Wildwuchs wird unschädlich). *Begründung:* Die Checkliste (Klagebereitschaft) darf nicht auf dokumente.typ aufsetzen — der ist nachweislich inkonsistent; maßgeblich ist der Ereignistyp.

---

## 4. Datenmodell-Vorschlag

Erweiterung des Schemas aus PIPELINE-REFACTORING-PLAN.md (dort Mig 46–49); hier **Migration 50 ff.** (Platzhalter, PF-06). Alles additiv, nichts Destruktives. `akte_az` referenziert wie überall `unfallakte.az` (TEXT).

### 4.1 Ebene 1 — `ereignisse` (Quelle der Wahrheit, Migration 50)

| Spalte | Typ | Bemerkung |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | |
| `akte_az` | TEXT NOT NULL FK unfallakte(az) | |
| `ereignistyp` | TEXT NOT NULL | Katalog aus Konfiguration (4.5), z. B. abrechnung_eingegangen, stellungnahme_generiert, fristablauf |
| `richtung` | TEXT NOT NULL CHECK IN ('eingehend','ausgehend','intern') | intern = system-Ereignisse (Fristablauf) |
| `quelle` | TEXT NOT NULL CHECK IN ('dokument','system','manuell') | **'manuell' ab Tag 1 im Enum, in Stufe 1 schreibt es niemand** |
| `datum` | TEXT NOT NULL | fachliches Datum (Schreibendatum/Fristablauf), ISO |
| `dokument_id` | INTEGER FK dokumente(id), nullable | Pflicht bei quelle='dokument' außer Herkunft wdm (PF-08); NULL bei system |
| `herkunft` | TEXT nullable | Feinherkunft: review_freigabe, word_service, wdm, scheduler |
| `betragswirkung_gesamt` | REAL nullable | nur für Ereignisse ohne Positionsverteilung (Pauschalvergleich) |
| `ersetzt_durch` | INTEGER FK ereignisse(id), nullable | Kopf-Ersetzung (ganzes Ereignis storniert/ersetzt); positionsscharfe Ersetzung s. 4.2 |
| `versand_bestaetigt_am` | TEXT nullable | PF-04, optionaler Ein-Klick |
| `notiz` | TEXT nullable | |
| `erfasst_von` | INTEGER FK benutzer(id), nullable | NULL bei quelle='system' |
| `erfasst_am` | TEXT NOT NULL DEFAULT datetime | |

Regeln: **kein UPDATE außer `ersetzt_durch` und `versand_bestaetigt_am`, kein DELETE** (per Konvention + Guard-Test; SQLite-Trigger als Option). Index auf (akte_az, datum), (dokument_id).

### 4.2 Ebene 1 — `ereignis_positionen` (n:m mit positionsscharfer Wirkung, Migration 50)

| Spalte | Typ | Bemerkung |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | |
| `ereignis_id` | INTEGER NOT NULL FK ereignisse(id) | |
| `position_key` | TEXT NOT NULL | bestehender POSITION_KEYS-Katalog (PF-05) |
| `wirkung` | TEXT NOT NULL CHECK IN ('gefordert','anerkannt','gekuerzt','abgelehnt','erledigt','beleg','keine') | 'beleg' = Dokument belegt Position ohne Betragsanspruch (Rechnung eingegangen) |
| `betrag` | REAL nullable | Betragswirkung dieser Position (optional lt. Zielmodell) |
| `kuerzungsart_id` | INTEGER FK kuerzungsarten(id), nullable | bei wirkung gekuerzt/abgelehnt |
| `ersetzt_durch` | INTEGER FK ereignis_positionen(id), nullable | **positionsscharfe Ersetzung** (Teilersatz durch Ergänzungsgutachten, Befund 2.2c) |

UNIQUE(ereignis_id, position_key, wirkung). Ereignis mit **null** Positionszeilen = Akten-Scope-Ereignis (2.3). Ableitungs-Invariante: nur Zeilen mit `ersetzt_durch IS NULL` **und** Ereigniskopf `ersetzt_durch IS NULL` zählen.

### 4.3 Statusableitung (kein Schema — reine Funktionen)

Modul `backend/services/positionsstatus_service.py`, einziger Ableitungsort (kein Frontend-Zwilling):
- `leite_positionsstatus_ab(akte_az) -> dict je position_key`: `zustand` (offen/anerkannt/teilanerkannt/bestritten/erledigt), `gefordert` (PF-02), `anerkannt` (Summe aktueller anerkannt-Wirkungen), `offen` (gefordert × Quote − anerkannt; Quote lt. PF-03), `eskalationsstufe` (nächster sinnvoller Schritt: nutzt die bestehende `_empfohlene_stufe`-Logik aus sta_service.py Z. 229–235, verallgemeinert auf Positionsebene: letzte ausgehende Aktion + Tage seither + Fristablauf-Ereignisse), `stand` (Datum des jüngsten aktuellen Ereignisses — **Pflichtfeld für die Wissensgrenze**), `checkliste` (4.6).
- Zustände, die sich aus dokument+system **nicht** ableiten lassen (mandantenweisung, kommentarlose Zahlung, mündliche Einigung): werden **nicht** als Felder eingeführt, sondern sind als manuelle Ereignistypen für Stufe 2 konzipiert (PF-07) — konform zur Vorgabe.

### 4.4 Ebene 2 — `position_ereignis_cache` (Migration 50)

| Spalte | Typ |
|---|---|
| `akte_az` TEXT · `position_key` TEXT · `ereignis_id` INTEGER · `ereignistyp` TEXT · `richtung` TEXT · `datum` TEXT · `dokument_id` INTEGER nullable · `wirkung` TEXT · `betrag` REAL nullable · `status` TEXT CHECK IN ('aktuell','ersetzt') | PK (akte_az, position_key, ereignis_id, wirkung) |

- Geschrieben **ausschließlich** von `ereignis_service.schreibe_ereignis()` (gleiche Transaktion wie Ebene 1) und von `rebuild_cache(akte_az=None)`.
- `rebuild_cache` ist Pflichtbestandteil (vollständige Rekonstruktion aus Ebene 1); Drift-Guard: pytest vergleicht Cache gegen Rebuild; grep-Guard-Test stellt sicher, dass kein anderes Modul in die Tabelle schreibt (Muster test_kein_fastapi).
- Aggregate (Status/Beträge/Eskalation) werden **nicht** gecacht — Ableitung (4.3) rechnet zur Laufzeit über den Cache; bei den Datenmengen einer Kanzlei-Akte (Dutzende Ereignisse) unkritisch.

### 4.5 Konfiguration (Registry-Erweiterung, keine DB)

Im Registry-Verzeichnis des Pipeline-Plans (S1.5, gleicher Loader, gleiche Versionsstempel-/Fail-Loud-Mechanik):
- `registry/positionsarten.yaml`: je position_key → label, kategorie (fahrzeugschaden/nebenkosten/personenschaden/sonstiges), checkliste (Liste benötigter Belegtypen = Ereignistypen, 4.6), aggregation (für den Dashboard-Toggle: fahrzeugschaden-Gruppe).
- `registry/ereignistypen.yaml`: je Typ → label, richtung, zulässige quellen, default-wirkung, checklisten_relevanz (welchen Belegtyp erfüllt dieses Ereignis).
- `registry/aktionen.yaml`: Type-Action-Matrix (Abschnitt 5).
Ladefehler = lauter Alarm (identisch S1.5). Registry-Version wird am Ereignis **nicht** gestempelt (Ereignisse sind Fakten, keine Parse-Ergebnisse); die Ableitung nennt ihre Registry-Version im API-Payload.

### 4.6 Checkliste / Klage-Bereitschaft

Konfiguration in `positionsarten.yaml`, z. B. reparaturkosten → benötigt: [gutachten_eingegangen, forderung_generiert, fristsetzung_generiert]. Ableitung: je benötigtem Belegtyp existiert ein **aktuelles** Ereignis dieses Typs mit Positionsbezug (oder Akten-Scope, z. B. vollmacht_eingegangen) und dokument_id ≠ NULL → „3/4 vorhanden, fehlt: Fristsetzungsnachweis". Maßgeblich ist der **Ereignistyp**, nie dokumente.typ (PF-11). Anzeige immer mit Wissensgrenze.

---

## 5. Type-Action-Matrix

### 5.1 Struktur (`registry/aktionen.yaml`)

```yaml
aktionen:
  - aktion: stellungnahme            # Schlüssel, referenziert Endpoint/Wizard
    label: "Stellungnahme zu diesem Abrechnungsschreiben"
    scope: dokument                  # dokument | position | akte
    dokumentklassen: [abrechnungsschreiben, pruefbericht]   # nur bei scope dokument
    vorschlagsbedingung: "mind. eine berührte Position mit wirkung in (gekuerzt, abgelehnt)"
    vorbelegung: positionen_des_dokuments   # was der Wizard vorbefüllt bekommt
    erzeugt_ereignis: stellungnahme_generiert   # ausgehendes Ereignis nach Ausführung
    ereignis_wirkung: keine          # Stellungnahme ändert Beträge nicht, dokumentiert Bestreiten
```

Bedingungen sind **Vorschlags-/Sortierlogik, keine Verbote** — jede Aktion bleibt manuell auslösbar (Akten-Scope-Leiste). Auswertung der Bedingungen ausschließlich im Backend (`GET /akten/<az>/aktionen?dokument_id=…&position_key=…`), damit kein zweites Frontend-Regelwerk entsteht.

### 5.2 Beispieleinträge für die 5 häufigsten Dokumentklassen

**1. abrechnungsschreiben — vollständig durchgespielt (Dokument-Scope „Stellungnahme"):**
1. *Eingang:* Review-Freigabe (Pipeline S1.8) bestätigt die vorgeschlagenen Ereignisse → `abrechnung_eingegangen` (quelle dokument, dokument_id = freigegebene dokumente-Zeile) mit n:m-Zeilen je Position aus dem Parse-Ergebnis: wirkung `anerkannt` (betrag_reguliert), `gekuerzt`/`abgelehnt` (+ kuerzungsart_id); ggf. Akten-Ereignis `haftungsquote_geaendert` (PF-03).
2. *Anzeige:* Die Dokumentansicht zeigt aus der Matrix die Dokument-Scope-Aktion **„Stellungnahme zu diesem Abrechnungsschreiben"** — Vorschlagsbedingung erfüllt, sobald eine berührte Position gekürzt ist. Vorbelegung: genau die vom Dokument berührten Positionen mit Beträgen, Kürzungsarten und Standard-Gegenargumenten (heutiger ReguWizard-Datenweg, stellungnahme_routes.py Z. 55 nimmt bereits abrechnungsschreiben_id — die Aktion existiert also fast, nur ihr Einstiegspunkt und die Ereignis-Rückschreibung fehlen).
3. *Ausführung:* Wizard → DOCX generiert → dokumente-Zeile (Typ-Bug PF-11 behoben) → ausgehendes Ereignis `stellungnahme_generiert` auf **dieselben Positionen** (wirkung keine, dokument_id = neues DOCX) → bestehende `setze_antwort_frist()` legt die 2-Wochen-Frist an.
4. *Folge:* Läuft die Frist ab, erzeugt der Scheduler (P1.6) das system-Ereignis `fristablauf` auf dieselben Positionen → die Eskalationsableitung rückt vor („nächster Schritt: Sachstandsanfrage Stufe 2 — nach Aktenlage, letztes Ereignis vom …").

**2. gutachten:** Eingangsereignis `gutachten_eingegangen`, n:m auf kalkulierte Positionen (wirkung `beleg`, Beträge aus Parse als Vorschlag für schadenpositionen). Dokument-Scope-Aktionen: „Positionen in Schaden übernehmen" (heutiger KI-Dialog-Weg), „Forderungsschreiben vorbereiten" (Vorschlagsbedingung: noch kein forderung_generiert-Ereignis). Ergänzungsgutachten: positionsscharfe Ersetzung (4.2).

**3. pruefbericht:** `pruefbericht_eingegangen`, n:m auf gekürzte Positionen (wirkung gekuerzt, kuerzungsart aus Prüfbericht-Parse). Dokument-Scope: „Stellungnahme" (wie Abrechnungsschreiben), „SV-Stellungnahme anfordern" (Vorschlagsbedingung: Kürzungsart mit sv_stellungnahme_erforderlich).

**4. rechnung (inkl. Subklassen abschlepprechnung, standkostenrechnung, mietwagenrechnung):** `rechnung_eingegangen`, n:m auf die Ziel-Position — das Mapping Klasse→position_key wandert aus den zwei hartkodierten Kopien (belege_routes.py Z. 136 + constants.js Z. 514) in `positionsarten.yaml`/Klassen-YAML (eine Quelle). Dokument-Scope: „als Beleg der Position zuordnen" (ersetzt handleInlineAnnehmen), „Betrag in Schadenposition übernehmen".

**5. sv_rechnung:** `rechnung_eingegangen` auf sv_kosten (Vorsteuer-Weiche wie heute belege_routes.py Z. 596–602, aber konfiguriert). Dokument-Scope: „Beleg zuordnen"; Vorschlagsbedingung für „Forderung ergänzen": sv_kosten noch nicht gefordert.

**Akten-Scope (immer verfügbar, ergänzt die heutige globale Leiste, entfernt nichts):**
| Aktion | Vorschlagsbedingung (nur Sortierung) | erzeugt Ereignis |
|---|---|---|
| Sachstandsanfrage Stufe 1–3 | Eskalationsableitung je Akte (verallgemeinerte sta_service-Logik) | sta_generiert |
| Forderungsschreiben | Positionen mit Kalkulation, aber ohne gefordert-Ereignis | forderung_generiert (wirkung gefordert je Position) |
| Klage (über gewählte Positionen) | Positionen bestritten + Checkliste erfüllt + Fristablauf | klage_generiert (wirkung gefordert) |
| Kostennote | Gebührenberechnung gespeichert | kostennote_generiert (Akten-Scope, keine Positionen) |

**Positions-Scope:** „Für Klage vormerken" (bleibt in P1 Flag, PF-09), „Widerspruch/Stellungnahme nur zu dieser Position" (Teilmenge der Dokument-Scope-Stellungnahme), Vorschlagsstufe aus der abgeleiteten Eskalationsstufe der Position.

---

## 6. UI-Struktur

### 6.1 Positions-Dashboard pro Akte

- **Ort:** neuer Block in `UebersichtSection.jsx` direkt unter dem Phasen-Strip (PRD-18) — die Übersicht ist heute schon das Action-Dashboard der Akte (PRD-25b); alternativ eigener Tab, Entscheidung beim UI-Feinschliff.
- **Daten:** ausschließlich neuer Endpoint `GET /akten/<az>/positionen/status` (liefert 4.3-Ableitung je Position + `stand` + `registry_version`). **Kein** drittes calcBrutto im Frontend (Befund 2.2a/2.2b).
- **Toggle aggregiert/getrennt:** aggregiert bündelt nach `aggregation`-Gruppe aus positionsarten.yaml (Fahrzeugschaden = rep/wbw/restwert/wertminderung gemäß berechne_abrechnungsart-Logik, models/schaden.py Z. 469–600 — die Ableitung ruft diese bestehende Funktion, dupliziert sie nicht); getrennt = eine Zeile je position_key mit Zustand, gefordert/anerkannt/offen, Eskalationsvorschlag, Checkliste.
- **Zeile (getrennt), Beispiel:** `Reparaturkosten · bestritten · gefordert 6.200 € · anerkannt 4.100 € · offen 2.100 € · nächster Schritt: Stellungnahme · Belege 3/4 (fehlt: Fristsetzung)` + Klick öffnet die Ebene-2-Ereignisliste der Position (Datum, Typ, Richtung, Dokument-Link, aktuell/ersetzt).

### 6.2 Bereitschaftsanzeige mit Wissensgrenze

- Gemeinsame Komponente `AbleitungBadge.jsx` (neu, frontend/src/components/): rendert jede abgeleitete Aussage nur zusammen mit `„nach Aktenlage, letztes Ereignis vom {stand}"`. Der Endpoint liefert `stand` als Pflichtfeld; fehlt es, rendert die Komponente einen Fehler statt der Aussage (technische Erzwingung der Ehrlichkeitsregel — Durchgang 3d).
- Formulierungen ausschließlich relativ: „Klage-Checkliste 4/4 erfüllt — nach Aktenlage, Stand 30.06.2026", nie „bereit zur Klage".

### 6.3 Dokument-Scope-Aktionen in der Dokumentansicht

- **DokumenteSection.jsx:** je Dokumentzeile ein Aktionsmenü aus `GET /akten/<az>/aktionen?dokument_id=…` (Matrix-Auswertung im Backend); ersetzt perspektivisch die hartkodierte Inline-Zuordnung (handleInlineAnnehmen, Z. 513–540), die als erste Matrix-Aktion „Beleg zuordnen" wiederkehrt.
- **Review-UI (Pipeline S1.8):** Der Freigabe-Dialog zeigt die vorgeschlagenen **Ereignisse** (Typ, Positionen, Beträge — aus dem Parse-Ergebnis abgeleitet) zur Bestätigung/Korrektur an; Korrekturen laufen ins korrektur_log des Pipeline-Plans. Nach Freigabe erscheinen dort die jetzt verfügbaren Dokument-Scope-Aktionen („Stellungnahme …") als direkte Anschlusshandlung — der zentrale Arbeitsfluss: *Post freigeben → sofort reagieren*.
- **Globale Aktionsleiste:** bestehende Buttons in den Sections (KlageSection, RegulierungSection, STA, Gebühren) bleiben unverändert erreichbar; die Matrix steuert nur, was das Dashboard **vorschlägt** und wie sortiert wird.

---

## 7. Umsetzungsreihenfolge (Stufen analog PIPELINE-REFACTORING-PLAN.md)

Kopplungspunkte zur Intake-Planung (Tier 1 = S1.x dort):
- **K-1:** P1.1 nutzt den Registry-Loader inkl. Fail-Loud/Version aus **S1.5**. Wird das Positionsmodell zuerst gebaut, entsteht der Loader hier und S1.5 übernimmt ihn (gleiche Mechanik, einmal gebaut).
- **K-2:** P1.5 (eingehende Ereignisse) setzt die Review-Freigabe **S1.8** voraus; bis dahin liefern die bestehenden menschlichen Bestätigungswege (ReguWizard-Erfassung, KI-Dialog-Übernahme, Beleg-Zuordnung) die Freigabe-Äquivalente. Erweiterung an S1.8: Freigabe zeigt Ereignis-Vorschläge (PF-10).
- **K-3:** P1.4 (ausgehende Ereignisse) ist **unabhängig** von der Intake-Planung — word_service/klage/sta/stellungnahme existieren heute.
- **K-4:** Migrations-Nummern nach tatsächlicher Reihenfolge vergeben (PF-06).

### Stufe P1 — Kern

| Schritt | Ziel | Dateien | Migration | Testkriterium | Rollback | Umfang |
|---|---|---|---|---|---|---|
| **P1.1** Konfiguration | positionsarten.yaml, ereignistypen.yaml, aktionen.yaml + Loader (K-1) | registry/, intake/registry_loader.py | nein | Ladefehler bricht Start laut ab; alle POSITION_KEYS abgedeckt | Dateien ungenutzt | S |
| **P1.2** Ebene 1+2 | Tabellen ereignisse, ereignis_positionen, position_ereignis_cache; ereignis_service (einziger Schreibpunkt) + rebuild_cache + Guard-Tests (kein Fremd-Write, kein DELETE) | schema_manager.py, services/ereignis_service.py, tests | **ja (50)** | Rebuild == Cache nach beliebiger Ereignisfolge; UPDATE/DELETE-Versuch schlägt fehl | Tabellen bleiben leer | M |
| **P1.3** Ableitung | positionsstatus_service (Zustand, Beträge, Eskalation, Checkliste, stand) + Endpoint /positionen/status + /aktionen (Matrix-Auswertung) | services/positionsstatus_service.py, routers/positionen_routes.py | nein | Tabellenbasierte Unit-Tests je Zustandsübergang; Ersetztes fließt nie ein (2.2c-Test); Pauschalvergleich schließt alle Ketten | Endpoints unbenutzt | M |
| **P1.4** Ausgehende Ereignisse | Jede Generierung (Klage, Stellungnahme, STA, Forderung, Kostennote) schreibt zusätzlich ihr Ereignis (Positionen aus dem jeweiligen Kontext); Typ-Bug PF-11 fix; forderung_positionen wird weiter geschrieben (Alt-Pfad bleibt) | word_service.py, klage_routes.py, stellungnahme_routes.py, sta_routes.py, gebuehren_word.py | nein | Jede Generierung erzeugt genau 1 Ereignis mit korrekten Positionen; bestehende Downloads/Fristen unverändert (Regressionstests) | Ereignis-Aufrufe auskommentieren | M |
| **P1.5** Eingehende Ereignisse | Bestätigungswege erzeugen Ereignisse: ReguWizard-Speichern → abrechnung_eingegangen; Beleg-Zuordnung → rechnung_eingegangen; Gutachten-Übernahme → gutachten_eingegangen; WDM → unbestätigter Vorschlag (PF-08). Alt-Tabellen werden **parallel** weiter befüllt (kein Big-Bang) | abrechnungsschreiben.py, belege_routes.py, dokumente_routes.py, wdm_regulierung_service.py; später intake_routes.py (K-2) | nein | Nach ReguWizard-Erfassung liefert /positionen/status dieselben Beträge wie RegulierungSection (Abgleichstest); Doppelerfassung erzeugt keine Doppel-Ereignisse | Aufrufe auskommentieren | L |
| **P1.6** System-Ereignisse | Täglicher APScheduler-Job: fällige todos (quelle=system, erledigt=0, faellig_am ≤ heute) → einmaliges Ereignis `fristablauf` (idempotent über todo-id), Positionen aus dem auslösenden Ereignis (antwort_2w_{dok_id} → Positionen des Dokuments) | app.py, services/fristen_service.py, ereignis_service.py | nein | Abgelaufene Frist erzeugt genau 1 Ereignis (auch bei mehrfachen Läufen); Eskalationsableitung rückt vor | Job deregistrieren | S |
| **P1.7** UI | Positions-Dashboard (Toggle), AbleitungBadge, Dokument-Scope-Aktionsmenü, Ereignisliste je Position (Ebene 2) | UebersichtSection.jsx, DokumenteSection.jsx, components/AbleitungBadge.jsx, api.js | nein | Manuell im Browser: Golden Path Abrechnung → Stellungnahme → Fristablauf → Eskalationsanzeige; Wissensgrenze überall sichtbar | Block ausblenden | L |
| **P1.8** Backfill | Synthetische Ereignisse aus Bestand: abrechnungsschreiben+regulierung_positionen → abrechnung_eingegangen; forderung_positionen (je forderungsschreiben_nr) → forderung_generiert; dokumente.typ klage/forderungsschreiben/sachstandsanfrage → ausgehende Ereignisse (Datum = hochgeladen_am); schadenposition_belege → beleg-Wirkungen. Kennzeichnung herkunft='backfill' | scripts/backfill_ereignisse.py | nein | Stichproben: 5 Bestandsakten zeigen im Dashboard dieselben Summen wie v_regulierungsstatus (± dokumentierte F-01-Abweichung); Backfill idempotent | Ereignisse mit herkunft='backfill' sind identifizierbar (Löschung wäre destruktiv → nur Neuaufbau der DB-Kopie) | M |

Kein Schritt bricht den heutigen Weg: alle Alt-Tabellen und -Anzeigen bleiben in P1 unverändert bestehen; das Ereignismodell läuft additiv daneben (Doppelschreiben wie im Pipeline-Plan).

### Stufe P2 — Zweite Welle (je max. 5 Sätze)

**Manuelle Ereignisse (Erfassungsweg).** Erst wenn das Diktat-Tool + LLM-Vorschlag existiert, wird quelle='manuell' aktiviert. Erste Typen: mandantenweisung, telefonvermerk, zahlung_ohne_abrechnung (PF-07). Der Erfassungsweg muss billiger sein als Nicht-Erfassen — sonst nicht einführen.

**Ablösung gespeicherter Status.** regulierung_status wird abgeleitet (PF-01, **BREAKING**: manuelles Setzen + Auto-HQ entfallen); forderung_positionen.status wird von der Ableitung ersetzt; Flags nach PF-09 geprüft. Alt-Spalten bleiben als deprecated stehen (nichts Destruktives).

**Aktenkonto-Plausibilitätshinweis.** Read-only-Vergleich Gesamteingang vs. anerkannte Summen (2.4), nur nach Freigabe von PF-Frage und Identifikation der RA-MICRO-Tabelle. Reiner Hinweis im Dashboard.

**Vergleichs-Ereignis + SV-Workflow.** Ereignistyp vergleich (2.3) mit UI-Unterstützung („alle offenen Positionen schließen"); SV-Stellungnahme-Kette (angefordert/eingegangen) als Ereignisse statt Flag.

**Eskalations-Feinschliff.** Positionsscharfe STA-Stufen-Konfiguration, Sortierung des Action Boards nach Positions-Eskalation, Metrik Sekunden-pro-Vorgang analog Pipeline-Stufe 2.

### Stufe P3 — Vertagt (Nennung + Voraussetzungen)

| Thema | Voraussetzungen |
|---|---|
| **Ablösung des Spaltenmodells** `schadenpositionen` (zeilenbasierte Positions-Instanzen, „nur Konfiguration" auch für neue Positionsarten) | P1+P2 stabil; alle Konsumenten (WDM-Maps, Klage-Wizard, Gebühren, Frontend-Formulare) auf Ableitungs-Endpoint migriert. Größter Einzelumbau des Systems — nur mit eigenem Plan. |
| **Ereignis-getriebene Workflow-Regeln** (PRD-07: Ereignis → automatischer Todo-/Aktionsvorschlag) | Ereignisbasis gefüllt, Matrix bewährt; bleibt Vorschlagslogik, nie Auto-Ausführung. |
| **Statistiken aus Ereignissen** (Durchlaufzeiten je Versicherer/Position, StatistikenView-Backend) | ≥ 6 Monate Ereignisdaten inkl. Backfill-Kennzeichnung. |

---

## Abschluss

Dieses Dokument ist reine Analyse + Plan. **Keine Implementierung erfolgt.** Nächster Schritt: Entscheidung der offenen Fragen PF-01 bis PF-11 durch RA Schatz (am wichtigsten: PF-02 „gefordert", PF-06 Reihenfolge zur Intake-Planung, PF-07 Blindflecken). Empfohlener Einstieg nach Freigabe: P1.1 + P1.2 (Konfiguration + Tabellen, rein additiv, kein Eingriff in Bestandscode).
