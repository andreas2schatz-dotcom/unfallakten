# Session-Übergabe – Kanzlei Koch, Schatz & Kollegen
# Unfallakten-Verwaltungssystem
> Stand: Session v17 – 27. März 2026

---

## Aktueller Systemstand

| Komponente | Details |
|---|---|
| DB-Schema-Version | **23** |
| App.jsx | ~10.865 Zeilen |
| Backend | Flask/Python, SQLite PK az TEXT |
| RA-Micro | Optional |

---

## Erledigte Features v17

| Feature | Status |
|---|---|
| Prüfbericht-Persistenz in SQLite (3 Bugs behoben) | ✅ |
| B-07: Status → `klage` nach Klageschrift-Generierung | ✅ |
| Auto-Vertreter-Lookup beim Öffnen des Klage-Tabs | ✅ |
| Vertreter-Persistenz: `Beteiligter`-Dataclass gefixed | ✅ |
| Regulierungsreiter komplett neu (Tabelle statt Formular) | ✅ |
| Gezahlt-Popup mit Datum/Versicherung/Referenz-Nr. | ✅ |
| Kürzungsarten: Checkboxen + Kategorisierung nach Position | ✅ |
| Fahrzeugschaden als eine Zeile je Abrechnungsart | ✅ |
| `RegulierungsTabelle` gemeinsame Komponente | ✅ |
| Klage-Tab: Kachel 4 Regulierungsstand | ✅ |
| Klage-Tab: RVG-Split außergerichtlich/gerichtlich | ✅ |
| abrechnungsschreiben.py: WHERE id→az, PRAGMA FK=OFF, POSITION_KEYS erweitert | ✅ |

---

## Offene Bugs / Bekannte Probleme

| # | Problem | Priorität |
|---|---|---|
| – | Klagegenerator noch nicht vollständig getestet (13 Blöcke) | 🔴 |

---

## To-Do – Nächste Session

### ✅ Erledigt v18: Stellungnahme zum Abrechnungsschreiben
`stellungnahme_service.py` + `stellungnahme_routes.py` + Button im Regulierungsreiter.
Nutzt `forderungsschreiben_vorlage.docx` als Stil-Träger, liest `standard_gegenargument` aus `kuerzungsarten`.

### ✅ Erledigt v18: Kürzungskatalog-Bug behoben
`KATEGORIE_CFG` war nie definiert → React Error Boundary fing Crash stumm ab → Dauerspinner.
Fix: Konstante definiert, `finally`-Block, 10s Timeout via `Promise.race`, echte Fehler-Toasts.

### 🔴 Priorität 1: Textbaustein-Feld in Kürzungsarten
Migration: `ALTER TABLE kuerzungsarten ADD COLUMN textbaustein TEXT`.
UI: Textarea im Kürzungskatalog-Formular.
Service: `stellungnahme_service.py` nutzt `textbaustein` statt `standard_gegenargument` (Fallback bleibt).

### 🔴 Priorität 2: Dokumente hochladen – kategorisiert
Beim Hochladen von Dokumenten Kategorisierung ermöglichen (Dokumenttyp, Beteiligter, Datum etc.).
Details noch zu klären.

### 🔴 Priorität 3: Klagegenerator – Abschlusstest (je Block)

| Block | Was prüfen | Status |
|---|---|---|
| **Rubrum** | Kläger (Name, Anrede, Anschrift), alle Beklagten (GHPV + ggf. Halter/Fahrer), Vertreter mit Funktion, Gericht | ⬜ |
| **Einleitung** | AZ, Unfalldatum, Unfallort (SQLite > WDM), Kennzeichen Gegner, Schadennummer | ⬜ |
| **Tatbestand** | Unfallschilderung (SQLite > varSCHILD), Zeugen (varZ1-3 + Adressen), Fahrer Mandant/Gegner, KFZ-Daten aus Gutachten | ⬜ |
| **Ermittlungsakte** | AZ Ermittlungsakte (varEA-AZ), Behörde (varPOLIZEI), Ort (varEA-ADRESS) | ⬜ |
| **Schadentabelle** | Korrekte Positionen je Abrechnungsart (fiktiv/konkret/Totalschaden), Beträge, Unkostenpauschale-Default 30€, WDM-Extras | ⬜ |
| **Haftungsquote** | Quoten-Block erscheint bei HQ < 100%, korrekte Berechnung | ⬜ |
| **Haftungsbegründung** | varANSP1 oder SQLite `haftungsbegruendung` | ⬜ |
| **Schmerzensgeld** | Block erscheint wenn angehakt (auch ohne Mindestbetrag), Mindestbetrag optional | ⬜ |
| **Zinsen** | Verzugsdatum (varSCHREIBENVERZUG), Zinsbeginn-Wahl, korrekter Zinssatz 5PP | ⬜ |
| **Klageanträge** | Hauptantrag korrekt je Abrechnungsart, Leerzeilen, Versäumnisurteil-Antrag | ⬜ |
| **Rechtliche Würdigung** | Platzhalter-Text vorhanden; D4: Kürzungsargumente auto aus kuerzungsarten | ⬜ |
| **RVG** | Streitwert = Summe gemerkter Positionen, §13-Tabelle korrekt, Mehrwertsteuer, Override | ⬜ |
| **Verweisbetrieb** | Textbaustein erscheint wenn verweisFlag gesetzt, Entfernungsangabe korrekt | ⬜ |

### 🟡 Priorität 3: D4 Rechtliche Würdigung
- Kürzungsargumente aus `kuerzungsarten.standard_gegenargument` automatisch in Klageschrift

### 🟡 Priorität 4: Vorlagen-Verwaltung (Einstellungen)

---

## Kritische Architektur-Notizen

- `unfallakte` PK = `az TEXT` (kein Integer seit Migration 5) → `WHERE az=?` überall
- `Beteiligter.from_row()` filtert mit `dataclasses.fields()` → neue Felder MÜSSEN in Dataclass eingetragen werden
- `POSITION_KEYS` in `abrechnungsschreiben.py` UND `_POSITION_KEYS_ERWEITERT` in Route – neue Keys immer an BEIDEN Stellen
- `PRAGMA foreign_keys = OFF` vor INSERT in `abrechnungsschreiben` (FK-Mismatch auf `dokumente`)
- `fahrzeugschaden_netto` ist Frontend-only Key → beim Speichern mappen: totalschaden→`wiederbeschaffung`, konkret→`rep_rechnung_netto`, fiktiv→`rep_gutachten_netto`
- `pruefbericht_bp` in `abrechnungsschreiben_routes.py` ist die aktive Route (nicht `pruefberichte_routes.py`)
- WDM-Variablen: `varSCHREIBENVERZUG` bevorzugen vor `varVERZUGAB`; `varQUOTEG` hat `" EUR"` Suffix → strippen
- Catch-Blöcke im Frontend NIE stumm lassen – immer echten Fehler im Toast zeigen
- `POSITION_KEYS` in `abrechnungsschreiben.py` UND `_POSITION_KEYS_ERWEITERT` in Route – neue Keys immer an BEIDEN Stellen eintragen

---

## Neue Komponente: RegulierungsTabelle

```jsx
<RegulierungsTabelle
  schaden={schaden}          // Schaden-Objekt aus Store
  abrechnungen={abrechnungen} // Array aus Store
  showCheckboxes={false}      // true = Klage-Tab-Modus mit Checkboxen
  checked={{}}                // {[key]: bool} kontrollierter State
  onToggle={(key) => {}}      // Callback bei Checkbox-Klick
  showKlageBadge={true}       // KLAGE-Badge in Übersicht zeigen
/>
```

**Verwendet in:**
- `UebersichtSection` (Zeile ~2073) – `showCheckboxes=false`, `showKlageBadge=true`
- `KlageSection` Kachel 4 (Zeile ~7967) – `showCheckboxes=false`, `showKlageBadge=false`

---

## KlageSection – Kachelstruktur (aktuell)

| Nr | Kachel | Inhalt |
|---|---|---|
| 1 | Gericht | Suche + Vorschlag |
| 2 | Parteien (Rubrum) | Beklagte + Vertreter-Lookup |
| 3 | Schadenpositionen | Checkboxen + Klagebetrag |
| **4** | **Regulierungsstand** | **Abrechnungsschreiben-Liste + RegulierungsTabelle + Textbaustein** |
| 5 | Personenschaden | Schmerzensgeld |
| 6 | Zinsen und Verzug | Datum + Zinsbeginn |
| 7 | Rechtsanwaltsgebühren | RVG-Split außergerichtl./gerichtl. |

---

## Regulierungsreiter – Neue Architektur

**Positionslogik:**
- `fahrzeugschaden_netto` ist Frontend-only Key → in `posVorlage` berechnet
- `POS_KUERZUNG_KATEGORIE` Mapping für kategorisierte Kürzungsarten
- Gezahlt-Popup: Betrag + Datum + Versicherung + Referenz-Nr.
- Teilzahlungen: aufklappbar (▶-Button), Datum/Versicherung/Quelle sichtbar
- HQ: inline editierbar in der Kopfzeile, wird in DB gespeichert

---

## Wichtige Tabellen / Felder

```sql
-- abrechnungsschreiben
quelle TEXT  -- 'pdf' | 'manuell' | 'wdm'
gesamt_kuerzung REAL
wdm_importiert INTEGER
referenz_nr TEXT

-- regulierung_positionen
position_label TEXT
-- CHECK-Constraint auf position_key entfernt

-- pruefberichte (15 PDF-Felder + Migration 4)
referenzwerkstatt_plz_ort TEXT  -- separat (nicht in Adresse geklatscht)

-- beteiligte
vertreter_name TEXT    -- MUSS in Beteiligter-Dataclass stehen!
vertreter_funktion TEXT
```

---

## Fahrzeugschaden-Logik (Backend + Frontend einheitlich)

```
eff_rep = rep_rechnung_netto > 0 ? rep_rn : rep_gutachten_netto

wenn WBW > 0:
  netto_fahrzeug = WBW − Restwert
  wenn eff_rep > 0 AND eff_rep <= netto_fahrzeug → Reparatur mit eff_rep
  sonst → Totalschaden: WBW − Restwert

wenn WBW = 0 → Reparatur mit eff_rep (oder keine Position)

Frontend-Key fahrzeugschaden_netto → Backend-Mapping beim Speichern:
  totalschaden → wiederbeschaffung
  konkret / rep_rechnung_netto > 0 → rep_rechnung_netto
  fiktiv / sonst → rep_gutachten_netto
```

---

## Geänderte Dateien v17

| Datei | Änderung |
|---|---|
| `backend/routers/abrechnungsschreiben_routes.py` | _parse_datum, _pruefe_akte, plz_ort-Fix |
| `backend/models/abrechnungsschreiben.py` | PRAGMA FK=OFF, POSITION_KEYS erweitert, WHERE az=? |
| `backend/models/schaden.py` | vertreter_name/funktion in Beteiligter-Dataclass |
| `backend/app.py` | pruefberichte_bp korrekt eingerückt |
| `frontend/src/App.jsx` | Kompletter Regulierungsreiter-Umbau, RegulierungsTabelle, Klage-Kachel 4, RVG-Split |

---

## Docker-Befehle

```powershell
# Standard-Deploy Frontend
docker cp frontend/src/App.jsx unfallakten-frontend-dev:/app/src/App.jsx

# Standard-Deploy Backend
docker cp backend/routers/<datei>.py unfallakten-backend-dev:/app/routers/<datei>.py
docker cp backend/models/<datei>.py unfallakten-backend-dev:/app/models/<datei>.py
docker restart unfallakten-backend-dev

# Logs prüfen
docker logs unfallakten-backend-dev --tail 50
```
