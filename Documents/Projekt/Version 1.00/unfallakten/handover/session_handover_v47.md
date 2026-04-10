# Session-Übergabe – Kanzlei Koch, Schatz & Kollegen
# Unfallakten-Verwaltungssystem
> Stand: Session v47 – 9. April 2026

---

## Aktueller Systemstand

| Komponente | Details |
|---|---|
| DB-Schema-Version | **35** |
| Frontend | React + Vite, aufgeteilt in Section-Dateien |
| Backend | Flask/Python 3.9, SQLite PK az TEXT |
| RA-Micro | Optional (RAMICRO_AKTIV=true) |
| E-Akte | EAKTE_BASE_PATH konfiguriert → Auto-Import aktiv |

---

## Erledigte Arbeiten v47

### PRD-28 Gebührenassistent – Post-Deployment Bug-Fixes + Verbesserungen

| Was | Datei | Details |
|---|---|---|
| Falscher Spaltenname `krankenhaus_aufenthalt` | `gebuehren_service.py` | → `krankenhaus_von`/`krankenhaus_bis`; stationär = von ≠ bis (gleicher Tag = ambulant) |
| Falscher Spaltenname `klasse` | `gebuehren_service.py` | → `typ` in `dokumente`-Tabelle |
| Spalte `gesamt_brutto` existiert nicht | `gebuehren_routes.py` | → `SUM(betrag_gefordert) FROM forderung_positionen` + COALESCE-Fallback `schadenpositionen` |
| Format-Fehler `{haftungsquote:.0f}` | `gebuehren_service.py` | Werte sind bereits Strings → Formatspezifizierer entfernt |
| Falscher Briefkopf in Kostennote | `gebuehren_word.py` | Kompletter Umbau: `forderungsschreiben_vorlage.docx` als ZIP-Template + `_render_docx` aus `forderungsschreiben_wv.py` |
| Kein Download-Link nach Word-Generierung | `GebuehrenSection.jsx` | `wordDok`-State + "Erneut herunterladen"-Button |
| Import-Fehler `apiDokumente` | `GebuehrenSection.jsx` | `import { ..., dokumente as apiDokumente }` (kein Default-Export) |
| Grußformel ohne Unterschrift | `gebuehren_word.py` | `_unterschrift_bytes()` + `_SA_DRAWING_XML` + `sachbearbeiter` aus `unfallakte` |
| Adresse an Gegner statt Mandant | `gebuehren_word.py` | Adresse + Anrede immer an Mandant |
| Falsche Anrede-Spalte `geschlecht` | `gebuehren_word.py` | → `beteiligte.anrede` + `_mandant_anrede_nominativ()` aus `forderungsschreiben_wv.py` |
| Tabellen-Formatierung | `gebuehren_word.py` | Kein oberer Rand (Gegenstandswert), Trennlinie unter Zwischensumme netto (tcBdr) |
| Begründungstexte generisch | `gebuehren_service.py` | Professionelle Texte aus `RVG_Geschaeftsgebuehr_Verkehrsunfall.docx` für alle 12 VU-Regeln |
| BGH-Toleranzsatz fehlte | `gebuehren_service.py` | Satz "Im Übrigen... BGH 08.05.2012 – VI ZR 273/11..." in VU-11/08/10/05/06/12/07/07b |

---

## Offene Bugs / Bekannte Probleme

| # | Problem | Priorität |
|---|---|---|
| B-01 | **Klage-Wizard Bug** – vom Anwalt gemeldet, noch nicht beschrieben | 🔴 |
| B-02 | Klagegenerator noch nicht vollständig getestet (13 Blöcke) | 🔴 |
| – | PRD-22c Session 4–5 (Fragebogen-Backend-Tests) ausstehend | 🟡 |
| – | PRD-25c Mandantenkommunikation nicht implementiert | 🟡 |
| – | PRD-25d STA End-to-End-Test ausstehend | 🟡 |
| – | Bußgeld-Deployment ausstehend | 🟡 |

---

## To-Do – Nächste Session

### 🔴 Priorität 1: Klage-Wizard Bug (B-01)
Anwalt hat einen Bug gemeldet, Details werden zu Beginn der nächsten Session beschrieben.
→ Bug zunächst reproduzieren, dann in `bugs_and_fixes.md` dokumentieren.

### 🔴 Priorität 2: Klagegenerator – Abschlusstest (je Block)

| Block | Was prüfen | Status |
|---|---|---|
| **Rubrum** | Kläger (Name, Anrede, Anschrift), alle Beklagten (GHPV + ggf. Halter/Fahrer), Vertreter mit Funktion, Gericht | ⬜ |
| **Einleitung** | AZ, Unfalldatum, Unfallort (SQLite > WDM), Kennzeichen Gegner, Schadennummer | ⬜ |
| **Tatbestand** | Unfallschilderung (SQLite > varSCHILD), Zeugen (varZ1-3 + Adressen), Fahrer Mandant/Gegner, KFZ-Daten aus Gutachten | ⬜ |
| **Ermittlungsakte** | AZ Ermittlungsakte (varEA-AZ), Behörde (varPOLIZEI), Ort (varEA-ADRESS) | ⬜ |
| **Schadentabelle** | Korrekte Positionen je Abrechnungsart, Beträge, Unkostenpauschale-Default 30€, WDM-Extras | ⬜ |
| **Haftungsquote** | Quoten-Block erscheint bei HQ < 100%, korrekte Berechnung | ⬜ |
| **Haftungsbegründung** | varANSP1 oder SQLite `haftungsbegruendung` | ⬜ |
| **Schmerzensgeld** | Block erscheint wenn angehakt (auch ohne Mindestbetrag), Mindestbetrag optional | ⬜ |
| **Zinsen** | Verzugsdatum (varSCHREIBENVERZUG), Zinsbeginn-Wahl, korrekter Zinssatz 5PP | ⬜ |
| **Klageanträge** | Hauptantrag korrekt je Abrechnungsart, Leerzeilen, Versäumnisurteil-Antrag | ⬜ |
| **Rechtliche Würdigung** | Platzhalter-Text vorhanden; D4: Kürzungsargumente auto aus kuerzungsarten | ⬜ |
| **RVG** | Streitwert = Summe gemerkter Positionen, §13-Tabelle korrekt, Mehrwertsteuer, Override | ⬜ |
| **Verweisbetrieb** | Textbaustein erscheint wenn verweisFlag gesetzt, Entfernungsangabe korrekt | ⬜ |

### 🟡 Priorität 3: PRD-27 ReguWizard
Geführter Wizard: Stellungnahme auf Abrechnungsschreiben. PRD: `handover/PRD-27_ReguWizard.md`.

### 🟡 Priorität 4: PRD-25c Mandantenkommunikation
### 🟡 Priorität 5: Bußgeld-Deployment

---

## Kritische Architektur-Notizen

- `unfallakte` PK = `az TEXT` (kein Integer seit Migration 5) → `WHERE az=?` überall
- `beteiligte.anrede` (nicht `geschlecht`) → `_mandant_anrede_nominativ()` aus `forderungsschreiben_wv.py`
- `personenschaden.krankenhaus_von/bis` (nicht `krankenhaus_aufenthalt`) – stationär = von ≠ bis
- `dokumente.typ` (nicht `klasse`) – für alle Typ-Abfragen
- Kostennote: OOXML-Template via `forderungsschreiben_vorlage.docx` + `_render_docx` aus `forderungsschreiben_wv.py`
- Streitwert-Fallback: `forderung_positionen` → `schadenpositionen` COALESCE-Summe
- `POSITION_KEYS` in `abrechnungsschreiben.py` UND `_POSITION_KEYS_ERWEITERT` in Route – neue Keys immer an BEIDEN Stellen
- WDM-Variablen: `varSCHREIBENVERZUG` bevorzugen vor `varVERZUGAB`
- RA-MICRO: NIEMALS schreiben. Nur SELECT.
- `pdf_hash` in `dokumente` (seit Migration 24): SHA-256, vor `registriere_dokument` auf Duplikat prüfen

---

## Geänderte Dateien v47

| Datei | Änderung |
|---|---|
| `backend/services/gebuehren_service.py` | Spaltenfix (krankenhaus_von/bis, typ), Format-Fehler behoben, professionelle Begründungstexte, BGH-Toleranzsatz in 8 Regeln |
| `backend/routers/gebuehren_routes.py` | Streitwert via forderung_positionen + COALESCE-Fallback |
| `backend/word/gebuehren_word.py` | Kompletter Umbau: OOXML-Template, _render_docx aus forderungsschreiben_wv, Unterschrift, Mandant-Adresse, Anrede, Tabellen-Formatierung |
| `frontend/src/sections/GebuehrenSection.jsx` | Download-Link nach Word-Generierung, apiDokumente-Import-Fix |
| `handover/architecture.md` | Word-Generierung-Tabelle + Kostennote-Konvention aktualisiert |
| `handover/backlog.md` | PRD-28 → Abgeschlossen, IDEA Gebührenoptimierung entfernt (= PRD-28) |

---

## Docker-Befehle

```bash
docker restart unfallakten-backend-dev
docker logs unfallakten-backend-dev --tail 50
docker exec unfallakten-backend-dev sqlite3 /app/data/unfallakten.db "SELECT schema_version FROM schema_version;"
```
