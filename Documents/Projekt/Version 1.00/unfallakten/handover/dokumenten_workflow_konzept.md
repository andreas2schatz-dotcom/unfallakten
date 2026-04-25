# Produktplanung & Workflow-Konzept
# Kanzlei Koch, Schatz & Kollegen – Unfallakten-Verwaltungssystem
> Version 4 – Session v54, 25. April 2026
> Grundstruktur: Onboarding → Außergerichtliche Regulierung → Klage

---

## Legende

| Präfix | Bedeutung |
|---|---|
| `PRD-##` | Product Requirement – Feature oder Modul |
| `B-##`   | Bug – Fehler in bestehendem Code |
| `IMP-##` | Implementierungsdetail aus Code-Review |
| ⬜ | Offen |
| 🔄 | In Arbeit |
| ✅ | Erledigt |
| 🔴 | Kritisch |
| 🟡 | Mittel |
| 🟢 | Niedrig |

---

## Die zwei Kernphasen des Kanzlei-Workflows

Das System bedient zwei Hauptphasen. Alle PRDs sind diesen Phasen zugeordnet.

### Phase 1: Onboarding (Mandantenaufnahme)
Von Erstkontakt bis vollständig aufgenommene Akte mit Erstforderung.

| Schritt | System-Status | Lücke |
|---|---|---|
| Erstkontakt via E-Mail (unfall@) | ✅ E-Mail-Import-View | – |
| Akte anlegen | ⚠️ Kein „+ Neue Akte"-Button im UI (Stub in v54) | Kein Onboarding-Wizard |
| Stammdaten Mandant + KFZ | ⚠️ BeteiligteSection als nacktes CRUD | Kein Geburtsdatum, kein Beruf, keine Pflichtfelder |
| RSV-Deckungsanfrage tracken | ⚠️ RSV-Pill vorhanden, aber kein Workflow | Anfrage → Deckungsbestätigung nicht nachverfolgbar |
| Vollmacht versenden | ✅ Vollmacht-Generator + Mailto-Link | – |
| Gegnerseite identifizieren | ⚠️ Gegnerkachel vorhanden | Kein KH-Versicherer-Lookup per Kennzeichen |
| WDM-Daten laden | ✅ PRD-15 implementiert (v53) | – |
| Erstanschreiben-Paket | ⚠️ WordSection generiert einzeln | Kein „Onboarding-Pack"-Button (alle Briefe auf einmal) |
| Konfliktcheck / Interessenkollision | ❌ Komplett fehlend | Kein Hinweis bei Gegenseite bereits vertreten |

### Phase 2: Außergerichtliche Regulierung
Von Erstforderung bis Vollregulierung oder Klagevorbereitung.

| Schritt | System-Status | Lücke |
|---|---|---|
| Erstforderung versenden | ✅ WordSection + Forderungshistorie | – |
| § 3a PflVG-Frist | ✅ StatusBand mit Countdown | – |
| STA versenden | ✅ STA-Dialog im Header | – |
| Abrechnungsschreiben parsen | ✅ KI-Parsing + Qwen Shadow-Mode | – |
| Kürzungsanalyse (Was wurde gekürzt?) | ✅ Kürzungsarten-Tabelle | Gut abgedeckt |
| Stellungnahme erstellen | ⚠️ apiStellungnahme vorhanden | PRD-27 (ReguWizard) fehlt; keine Textbausteine (PRD-02) |
| Mandant über Zwischenstand informieren | ⚠️ PWA-Nachricht-Modal vorhanden | Kein automatischer Stand-Bericht als PDF |
| Nachforderung / 2. Forderungsschreiben | ⚠️ Technisch möglich | Kein klarer Workflow |
| Verzugsschaden + RVG Nr. 2300 | ✅ PRD-28 Gebührenassistent | – |
| Regulierungsstand verbuchen | ✅ Option-B-Regulierungsworkflow | – |
| Entscheidungspunkt → Klage | ✅ Klage-Wizard 10 Steps (PRD-26) | – |

---

## Aktuelle Bug-Liste

### B-01 ✅ Prüfbericht-Persistenz
Prüfbericht verschwand nach Neuanmelden. Behoben v17.

### B-02 ✅ Kürzungskatalog Dauerspinner
`KATEGORIE_CFG` nicht definiert → `finally`-Block fehlte. Behoben v18.

### B-03 ⬜ Klagegenerator nicht vollständig getestet
Gehört zu PRD-03. 13 Blöcke müssen einzeln getestet werden.

### B-04 🔄 Abrechnungsart an 4 Stellen gespiegelt
**Dateien:** `AkteDetailView.jsx:172–176`, `UebersichtSection.jsx:~1789`, `RegulierungSection.jsx:~1776`
Backend liefert `abrechnungsberechnung.gesamt_brutto` (Header liest es bereits korrekt).
Frontend-Berechnungen in UebersichtSection und RegulierungSection müssen noch auf Backend-Wert umgestellt werden.
→ PRD-14 (teilweise umgesetzt, Frontend-Cleanup ausstehend)

### B-05 ✅ WDM-Daten werden nur auf Knopfdruck geladen
Behoben: PRD-15 implementiert in `AkteDetailView.jsx:106–158` (v53).

### B-06 ✅ IMP-02: RSV „anfrage"-Zustand nicht erreichbar
RSV `warn`-Prop entfernt, nur `ok/neutral`. Behoben in Commit 6f3c46e.

### B-07 ✅ IMP-04: Doppelter `apiTodos.liste()`-Fetch
Todos in `UebersichtSection` gehoisted, als Prop an StatusBand + TodoWvSpalten. Behoben in Commit 6f3c46e.

### B-08 ✅ IMP-05: `pwa_nachricht_senden` nutzt kein `logge_aktivitaet()`
`logge_aktivitaet()` verwendet. Behoben in Commit 6f3c46e.

---

## PRD-Übersicht (nach Priorität)

```
── KRITISCH (sofort) ────────────────────────────────────────────
PRD-14   Single Source of Truth: Abrechnungsart (Frontend-Cleanup)
PRD-02   Textbaustein-Feld Kürzungsarten (Voraussetzung für PRD-27)
PRD-27   ReguWizard – Stellungnahme-Wizard (größter Effizienz-Hebel)

── BALD (nächste 3 Sessions) ────────────────────────────────────
PRD-16   Tab-Reihenfolge als Workflow-Ablauf
PRD-18   Statusmodell + Phasen-Strip
PRD-NEW  Onboarding-Wizard (neu identifiziert)
PRD-17   Tagesstart-Dashboard (DashboardView existiert – nur Default setzen)

── MITTEL ───────────────────────────────────────────────────────
PRD-03   Klagegenerator Abschlusstest
PRD-33   Klage-Wizard Feintuning (Formatierung + Textbausteine)
PRD-04   Erweiterte Dokumentenklassen (Klasse A/B/C)
PRD-32   Rechnungstypen-Parser Phase 2 (Beleg-Mapping)
PRD-05   Betrag-Abgleich nach Upload
PRD-25c  Mandantenkommunikation

── SPÄTER ───────────────────────────────────────────────────────
PRD-01   To-Do-System Vollausbau (Action Board deckt 70 % ab)
PRD-06   Parser Reparaturrechnung LLM
PRD-07   Workflow-Regeln + automatische To-Dos
PRD-19   RA-Micro DMS Integration (Read-Only)

── ABGESCHLOSSEN ────────────────────────────────────────────────
PRD-15 ✅  WDM automatisch laden (AkteDetailView.jsx:106–158)
PRD-22c ✅ Mandanten-Fragebogen
PRD-22d ✅ E-Mail-Import UI (3 Tabs)
PRD-23b ✅ Rechnungs-Parser (Registry + Kandidaten + Parser)
PRD-25a ✅ Automatische Fristen
PRD-25b ✅ Action-Dashboard / Wiedervorlagen
PRD-26 ✅  Klage-Wizard (10 Steps)
PRD-28 ✅  Gebührenassistent Nr. 2300 VV RVG
PRD-29 ✅  Schmerzensgeld-Ermittlungstool
PRD-29b ✅ E-Akte Auto-Parser Schlagwort-Filter
PRD-30 ✅  OCR + SSE-Streaming (pytesseract, pdf2image, EventSource)
PRD-31 ✅  Action Board / Übersicht-Umbau (IMP-01/03/06 erledigt)
PRD-32 ✅  Phase 1: Subklassifizierung (standkostenrechnung, abschlepprechnung)
PRD-34 ✅  Inbox-Pattern Dokumente-Kachel
```

---

## PRD-Details: Offene Kritische PRDs

---

### 🔴 PRD-14 – Single Source of Truth: Abrechnungsart (Frontend-Cleanup)
**Status:** 🔄 In Arbeit (Backend ✅, Frontend-Cleanup ⬜)
**Session-Schätzung:** 0,5 Sessions
**Abhängigkeiten:** keine

#### Was bereits fertig ist
Backend liefert `abrechnungsberechnung.gesamt_brutto` in der Schaden-Response.
`AkteDetailView.jsx:172` liest es bereits korrekt mit Fallback.

#### Was noch fehlt
Lokale Berechnungen in zwei Dateien entfernen:

```javascript
// UebersichtSection.jsx – _fzg()-Funktion entfernen (~Zeile 1789)
// Stattdessen: abrechnungsberechnung aus st.schaden lesen

// RegulierungSection.jsx – lokale Betrag-Berechnung entfernen (~Zeile 1776)
// Stattdessen: st.schaden.abrechnungsberechnung verwenden
```

#### Checkliste
- [ ] `UebersichtSection.jsx`: `_fzg()` entfernen, `st.schaden.abrechnungsberechnung` lesen
- [ ] `RegulierungSection.jsx`: lokale Betrag-Berechnung auf Backend-Wert umstellen
- [ ] Regressionstest: gleiche Beträge in Übersicht, Regulierung, Header

**Abnahmekriterium:** Betrag in Übersicht, Regulierung und Header sind identisch.

---

### 🔴 PRD-02 – Textbaustein-Feld Kürzungsarten
**Status:** ⬜ Offen
**Session-Schätzung:** 0,5 Sessions
**Abhängigkeiten:** keine – Voraussetzung für PRD-27

#### DB-Migration
```sql
ALTER TABLE kuerzungsarten ADD COLUMN textbaustein TEXT;
```

#### Fallback-Kette in `stellungnahme_service.py`
```python
text = ka.textbaustein \
    or ka.standard_gegenargument \
    or "Die Kürzung ist nicht gerechtfertigt."
```

#### Checkliste
- [ ] DB-Migration + `schema_manager.py`
- [ ] Kürzungskatalog-Formular: Textarea für Textbaustein
- [ ] `stellungnahme_service.py`: Fallback-Kette
- [ ] Kürzungskatalog-Liste: Textbaustein-Preview

---

### 🔴 PRD-27 – ReguWizard: Geführte Stellungnahme
**Status:** ⬜ Offen (Planung)
**Session-Schätzung:** 1–2 Sessions
**Abhängigkeiten:** PRD-02 (Textbausteine)

#### Vision
Nach Eingang eines Abrechnungsschreibens mit 5 Kürzungen soll das System sagen:
> „Kürzung: UPE-Aufschlag 12 % → Vorschlag: BGH VI ZR 53/09 (Stundenverrechnungssätze) – Kürzung unzulässig [Einfügen]"

Exakt diese Mikrointeraktion × 5–10 Akten/Tag = mehrere Stunden Zeitersparnis pro Woche.

#### Ablauf
```
1. Abrechnung mit Kürzungen → Button „Stellungnahme erstellen"
2. Wizard öffnet: je Kürzungsposition eine Seite
3. Pro Position: Kürzungs-Art (automatisch erkannt) + vorgeschlagener Textbaustein
4. Anwalt: akzeptieren / anpassen / überspringen
5. Zusammenfassung → Word-Export
```

#### Checkliste
- [ ] Wizard-Komponente in `RegulierungSection.jsx` oder eigene Section
- [ ] Kürzungsarten → Textbaustein → Brieftext-Zusammenbau
- [ ] Word-Export über `word_routes.py`
- [ ] Stellungnahme als Dokument speichern + Aktivitäten-Log

---

### 🟡 PRD-16 – Tab-Reihenfolge als Workflow-Ablauf
**Status:** ⬜ Offen
**Session-Schätzung:** 0,5 Sessions

#### Ziel-Reihenfolge
```
1. ⚡ Übersicht   (Action Board – Default)
2. 👥 Beteiligte
3. 🔍 Unfalldetails
4. 🚗 Schaden
5. 📄 Dokumente
6. 💶 Regulierung
7. ⚖ Klage
8. 📝 Word
9. ⚖️ Gebühren
```
„To-Dos"-Tab entfernen (Inhalt liegt bereits in Übersicht).

#### Aktuelle Reihenfolge (v53)
uebersicht → beteiligte → unfalldetails → schaden → dokumente → regulierung → **gebuehren** → klage → word → **todos**

#### Checkliste
- [ ] `AkteDetailView.jsx`: `tabs`-Array umordnen (Zeile 222–233)
- [ ] „To-Dos"-Tab aus Array entfernen oder durch Redirect auf Übersicht ersetzen
- [ ] „Gebühren" nach „Word" verschieben

---

### 🟡 PRD-18 – Statusmodell + Phasen-Strip
**Status:** ⬜ Offen
**Session-Schätzung:** 1 Session
**Abhängigkeiten:** PRD-14

#### Problem
Mehrere Mitarbeiter, eine fremde Akte: Wo stehen wir? 
FinanzBand + StatusBand zeigen KPIs, aber keine **Phase**. 
Sichtbarer Phasen-Strip würde Übergaben eliminieren.

#### Phasen-Strip (automatisch abgeleitet)
```
Onboarding ▶ Erstforderung ▶ Regulierung ▶ Stellungnahme ▶ Abschluss
```
Ableitungslogik:
- Vollmacht + IBAN vorhanden → Onboarding fertig
- Erstforderung versendet (Aktivitäten-Log) → Erstforderung
- Abrechnungsschreiben eingegangen → Regulierung
- Stellungnahme versendet → Stellungnahme
- Vollregulierung oder Klage → Abschluss

#### DB-Migration
```sql
ALTER TABLE unfallakte ADD COLUMN regulierungsstatus TEXT DEFAULT 'ausstehend';
    -- 'ausstehend' | 'teilreguliert' | 'vollreguliert' | 'abgelehnt' | 'strittig'
ALTER TABLE unfallakte ADD COLUMN klagestatus TEXT DEFAULT 'kein_verfahren';
    -- 'kein_verfahren' | 'vorbereitung' | 'eingereicht' | 'anhaengig' | 'abgeschlossen'
```

#### Checkliste
- [ ] DB-Migration
- [ ] Phasen-Strip-Komponente in `UebersichtSection.jsx` (über FinanzBand)
- [ ] Phase automatisch ableiten beim Laden der Akte
- [ ] `regulierungsstatus` aus `regulierung_positionen` berechnen

---

### 🟡 PRD-NEW – Onboarding-Wizard
**Status:** ⬜ Offen (neu identifiziert 2026-04-25)
**Session-Schätzung:** 1–2 Sessions
**Abhängigkeiten:** PRD-NEW Neue-Akte-Button (Stub in v54 implementiert)

#### Problem
Kein geführter Onboarding-Ablauf. Junior-Mitarbeiter erfassen Beteiligte unvollständig
(fehlendes Geburtsdatum, Beruf, Vorsteuer). Daten fehlen dann bei Klage und Schmerzensgeld.

#### Wizard-Schritte (analog Klage-Wizard)
```
Schritt 1: Aktenzeichen + Unfalldatum + Unfallort
Schritt 2: Mandant (Anrede, Name, Adresse, Geburtsdatum, Beruf, IBAN, Vorsteuer J/N)
Schritt 3: KFZ Mandant (Kennzeichen, Typ, WBW, RSV J/N)
Schritt 4: Gegner (Halter, Fahrer, Kennzeichen, KH-Versicherung, Schadennummer)
Schritt 5: RSV-Status (RSV vorhanden? → Deckungsanfrage Vorlage erstellen)
Schritt 6: Vollmacht + Erstanschreiben (Vollmacht + Anzeige der Vertretung + optional RSV-Anfrage)
Schritt 7: Fertig → Akte öffnen
```

#### Checkliste
- [ ] `OnboardingWizard.jsx` – neue Komponente (analog `KlageWizard.jsx`)
- [ ] Schrittweise Validierung, Pflichtfelder markiert
- [ ] Integration in `AktensucheView.jsx` → Öffnet nach „+ Neue Akte" wenn kein AZ noch vergeben
- [ ] Beteiligte-Felder erweitern: `geburtsdatum`, `beruf` (DB-Migration oder Schema-Check)

---

### 🟡 PRD-17 – Tagesstart-Dashboard
**Status:** ⬜ Offen (DashboardView.jsx existiert!)
**Session-Schätzung:** 0,5 Sessions
**Abhängigkeiten:** keine

#### Was schon da ist
`DashboardView.jsx` mit Kennzahlen-Kacheln und Fristen-Übersicht existiert bereits.
Das Problem: Der Nutzer startet immer in der Aktensuche, nicht im Dashboard.

#### Fix
Dashboard als **Default-View** beim App-Start setzen (statt Aktensuche).
Aktensuche bleibt über Navigation erreichbar.
Evtl. „Guten Morgen"-Begrüßung mit heutigem Datum und offenen To-Dos.

#### Checkliste
- [ ] App.jsx / Layout.jsx: Default-Route auf Dashboard setzen
- [ ] DashboardView: Block „Heute fällig" (aus todos WHERE faellig_am < heute+3)
- [ ] DashboardView: Block „Neu eingegangen" (Dokumente heute + E-Mail-Imports)
- [ ] Sachbearbeiter-Filter: eigene Akten / alle

---

## PRD-Details: Mittelpriorität

---

### PRD-03 ⬜ Klagegenerator Abschlusstest
**Abhängigkeiten:** PRD-14 (erst nach Abrechnungsart-Bereinigung sinnvoll)

| Block | Was prüfen | Status |
|---|---|---|
| Rubrum | Kläger, Beklagte, Vertreter, Gericht | ⬜ |
| Einleitung | AZ, Unfalldatum, Unfallort, KZ, Schadennummer | ⬜ |
| Tatbestand | Unfallschilderung, Zeugen, Fahrer, KFZ | ⬜ |
| Schadentabelle | Positionen, Beträge, Pauschale | ⬜ |
| Haftungsquote | Block bei HQ < 100% | ⬜ |
| Schmerzensgeld | Block bei Anhaken | ⬜ |
| Zinsen | Verzugsdatum, 5PP | ⬜ |
| Klageanträge | Hauptantrag, Versäumnisurteil | ⬜ |
| RVG | Streitwert, §13-Tabelle, MwSt | ⬜ |

---

### PRD-33 ⬜ Klage-Wizard Feintuning
Formatierung (Absätze, Leerzeilen), Textbausteine einzelner Schritte,
Rubrum bei mehreren Beklagten, RVG-Betrags-Einbindung.
**Debugging-Vorbereitung:** `handover/session_handover_v52.md`

---

### PRD-04 ⬜ Erweiterte Dokumentenklassen (Klasse A/B/C)

**Klasse A – Immer vorhanden**
`gutachterrechnung` · `reparaturrechnung` · `abschlepprechnung` · `abrechnungsschreiben` · `pruefbericht`

**Klasse B – Personenschaden**
`arztbericht` · `krankenhausbericht` · `verdienstausfall_nachweis` · `haushalt_attest`

**Klasse C – Sonderfälle**
`mietwagenrechnung` · `kaufvertrag` · `nachbesichtigung` · `feuerwehrrechnung` · `sachschadenbeleg` · `sonstiges`

```sql
ALTER TABLE dokumente ADD COLUMN dokumentenklasse TEXT;
```

---

### PRD-32 Phase 2 ⬜ Rechnungstypen-Beleg-Mapping
Phase 1 (Subklassifizierung standkostenrechnung/abschlepprechnung) ✅.
Phase 2: automatisches Mapping auf Schadenposition bei Upload.
**Plan:** `handover/PRD-32_Rechnungstypen_Parser.md`

---

### PRD-25c ⬜ Mandantenkommunikation
Portal + PWA-Nachricht-Modal (Stub) vorhanden. Vollständiges Push-System ausstehend.

---

## Offene Entscheidungen

- [ ] Onboarding-Wizard Schritt 4 (Gegner): Kennzeichen-Lookup auf KH-Versicherer? Eigene Tabelle oder externe API?
- [ ] Soll Tagesstart-Dashboard der Default-Einstieg werden oder bleibt Aktensuche?
- [ ] PRD-NEW Neue Akte: Erlauben wir einen „Vorerfassungs-AZ" (z.B. `TMP-001/26`) der später mit RA-Micro-AZ verknüpft wird?
- [ ] PRD-18 Phasen-Strip: Automatisch ableiten oder manuell setzen? (Empfehlung: automatisch mit manuellem Override)
- [ ] Verjährungsdatum: Immer 3 Jahre automatisch aus Unfalldatum berechnen oder manuell?

---

## Architektur-Prinzipien (unveränderlich)

Diese Regeln gelten für alle PRDs und Sessions:

| # | Regel | Warum |
|---|---|---|
| 1 | **Single Source of Truth** – Backend berechnet, Frontend zeigt nur an | Vermeidet Inkonsistenz zwischen Übersicht, Regulierung und Klageschrift |
| 2 | **`az = akte.aktenzeichen`** – nach `hole_akte_by_id()` immer `az` setzen, nie `akte_id` | Verlässliches Routing; ID ist intern, AZ ist extern |
| 3 | **Kein stummer Catch** – jeder `catch`-Block zeigt echten Fehlertext im Toast | Fehler werden nicht stillschweigend verschluckt |
| 4 | **`finally` für Loading-States** – `setLoading(false)` immer in `finally` | Loading-Spinner hängen nie bei Fehler |
| 5 | **Blueprint-Routing** – fester `url_prefix` + `<path:akte_id>` | Konsistente API-Struktur |
| 6 | **Python 3.9** – kein `str | None`, kein `list[dict]` als Type-Hint | Kompatibilität |
| 7 | **`hole_beteiligte_by_akte(az)`** – immer diese Funktion | Nie roher `SELECT * FROM beteiligte` |
| 8 | **RA-MICRO Read-Only** – NIEMALS in RA-MICRO DB schreiben | Datenintegrität RA-Micro |
| 9 | **`_pruefe_akte()` Rückgabewert nutzen** – immer `az = akte_obj.aktenzeichen if hasattr(...) else akte_id` | Korrekte az-Extraktion für alle DB-Queries |
| 10 | **SHA-256 Hash-Dedup** – vor `registriere_dokument` auf Duplikat prüfen | Keine doppelten Uploads |

---

## Empfohlene Session-Reihenfolge

| Session | Was | Begründung |
|---|---|---|
| **v54** | Neue-Akte-Stub ✅ + Konzept/Architektur konsolidiert ✅ | Diese Session |
| v55 | PRD-14 Frontend-Cleanup (0,5 Std.) + PRD-02 Textbausteine | Fundament für Stellungnahme |
| v56 | PRD-27 ReguWizard Stellungnahme | Größter täglicher Effizienz-Hebel |
| v57 | PRD-16 Tab-Reihenfolge + PRD-17 Dashboard Default | Quick-Wins UX |
| v58 | PRD-18 Statusmodell + Phasen-Strip | Mehrbenutzer-Klarheit |
| v59 | PRD-NEW Onboarding-Wizard Step 1–3 | Datenqualitäts-Fundament |
| v60 | PRD-NEW Onboarding-Wizard Step 4–7 | Vollständiger Onboarding-Fluss |
| v61 | PRD-03 Klagegenerator Abschlusstest | Qualitäts-Pass Klage |
| v62 | PRD-33 Klage-Wizard Feintuning | Formatierung + Textbausteine |
| v63+ | PRD-04/05/06/07 Dokumenten-Workflow | Erweiterte Klassifizierung |
