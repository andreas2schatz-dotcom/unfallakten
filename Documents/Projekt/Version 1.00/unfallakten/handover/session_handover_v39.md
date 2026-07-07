# Session-Übergabe – Kanzlei Koch, Schatz & Kollegen
# Unfallakten-Verwaltungssystem
> Stand: Session v38 – 2. April 2026
> Erledigt diese Session: Bugfixes (WDM/KPI/Streitwert) + PRD-24b (7-Step Wizard + EinwandePanel)
> Nächste Session: PRD-23b (Rechnungs-Parser) ODER PRD-03 Abschlusstest

---

## ⚠️ ERINNERUNG: WSL-Mount vor jedem Docker-Start!

```powershell
wsl --user root
mount -t cifs //192.168.10.100/ServerSQL/ra /mnt/eakte -o username=admin,password=passwort,ro
exit
docker compose up -d
```

---

## ⛔ ABSOLUTE REGELN

1. **Kein Schreibzugriff auf raEloakte** – NUR SELECT. Alle eigenen Daten in lokaler SQLite.

2. **Vor jedem Deploy: Code-Review gegen Learnings und bekannte Fehler:**
   - Routen-URLs: api.js ↔ Flask-Blueprint (`loesche` nicht `loeschen`!)
   - `_dok_dict()`: Beide Funktionen (upload_service + akten_routes) bei neuen Spalten
   - `d.typ` Fallback: `d.dokumentenklasse === "x" || d.typ === "x"`
   - React-Hook-Imports, Kommentar-Balance, **Python 3.9** (keine Union-Types `X | Y`, kein Walrus `:=`)
   - PRAGMA foreign_keys = OFF bei dok_id-Tabellen (B-06)
   - Reducer-Actions existieren? `confirm()` vor Löschaktionen
   - **B-08:** Bei durchgereichten Dicts IMMER prüfen ob alle Felder in JEDEM Zwischenschritt weitergegeben werden
   - **B-09:** Wenn Schadentabelle und Gegenstandswert unterschiedliche Quellen → beide prüfen
   - **PRD-24:** Override-Dict vollständig durchreichen: Wizard → API → klage_service
   - **WDM Key-Mismatch:** `sonstiges_wdm_X` ≠ `extra_wdm_ssX` → immer remap prüfen bei posMap-Aufbau

3. **Stimme nicht einfach zu.** Verbesserungsvorschläge und kritische Fragen stellen.

---

## Aktueller Systemstand

| Komponente | Details |
|---|---|
| DB-Schema-Version | **28** |
| Frontend | **27 Dateien** (inkl. KlageWizard.jsx – major update) |
| Backend | Flask/Python 3.9, SQLite PK `az TEXT` |
| RA-Micro | SQL Server (read-only), WDM + E-Akte aktiv |
| E-Akte | Phase 1+2+3a live |

---

## Diese Session erledigt

### Bugfixes

| Bug | Fix | Datei |
|---|---|---|
| WDM Key-Mismatch: doppelte Sonstiger-Schaden-Zeilen | `sonstiges_wdm_X` → `extra_wdm_ssX` remap in posMap | RegulierungSection.jsx, UebersichtSection.jsx |
| Header-KPI „Reguliert" nicht aktuell | `st.abrechnungen[].gesamt_reguliert` statt `st.regulierungen` | AkteDetailView.jsx |
| Außergerichtl. Streitwert falsch | Summe aus `positionen[].betrag` (brutto) statt regulierung_positionen | KlageSection.jsx |
| Gerichtl. Streitwert falsch | Reverted auf `klagebetrag` (nur angehakte Pos.) | KlageSection.jsx |

### UI

- KlageWizard-Button als prominente Kachel rechts neben Gericht+Rubrum (2-Spalten-Layout)
- Wizard Vorschau-Textarea: `minHeight 320` + `alignItems: "stretch"` für volle Höhe

### PRD-24b: 7-Step Wizard (vollständig deployed)

| Step | Inhalt |
|---|---|
| 1 | Rubrum – read-only Parteien-Übersicht |
| 2 | Aktivlegitimation + editierbare Vorschau |
| 3 | Unfallhergang – auto Mandant→Kläger, editierbar |
| 4 | Schadenpositionen + Personenschaden |
| 5 | Rechtl. Würdigung – Haftungsquote/Begründung + **EinwandePanel** |
| 6 | Verzug & Kosten – Bestätigung + Verzug editierbar |
| 7 | Zusammenfassung + Generieren |

### EinwandePanel (in Step 5)

- Button „⚔ Kürzungen & Einwände" mit Badge (Anzahl aus Regulierungsschreiben)
- Modal zeigt alle 19 `kuerzungsarten` gruppiert nach `kategorie`
- Vorauswahl: tatsächlich gekürzte Positionen (aus `regulierung_positionen.kuerzungsart_id`)
- Jeder Eintrag zeigt `standard_gegenargument` als Vorschau-Text
- „Text übernehmen" → an `rwText` angehängt → im Textarea editierbar
- **Erweiterbar:** `KATEGORIE_ORDER` + `KATEGORIE_LABELS` in KlageWizard.jsx für neue Einwands-Kategorien

---

## Geänderte Dateien

```
frontend/src/sections/KlageWizard.jsx       ← Major Rewrite (3→7 Steps + EinwandePanel)
frontend/src/sections/KlageSection.jsx      ← Neue States + oeffneWizard + Props
frontend/src/sections/RegulierungSection.jsx ← Key-Mismatch Remap
frontend/src/sections/UebersichtSection.jsx  ← Key-Mismatch Remap + alleKeys-Filter
frontend/src/components/AkteDetailView.jsx  ← Header-KPI Reguliert
backend/routers/klage_routes.py             ← ab_positionen JOIN + kuerzungsarten in Response + Overrides
backend/word/klage_service.py               ← rw_text_override + verzug_text_override
```

---

## Backend API-Änderungen

### GET /akten/<az>/klage/daten – neue Felder in Response

```json
{
  "kuerzungsarten": [
    { "id": 1, "bezeichnung": "Stundenverrechnungssätze",
      "kategorie": "fahrzeugschaden",
      "standard_gegenargument": "..." }
  ],
  "abrechnungen": [{
    "positionen": [{
      "kuerzungsart_id": 2,
      "kuerzung_bezeichnung": "Wertminderung",
      "standard_gegenargument": "..."
    }]
  }]
}
```

### POST /akten/<az>/klage/generieren – neue Override-Keys

```json
{
  "overrides": {
    "schilderung":           "...",   // ersetzt unfallhergang-Text
    "rw_text_override":      "...",   // ersetzt gesamten RW-Block
    "verzug_text_override":  "..."    // ersetzt Verzug-Paragraph
  }
}
```

---

## Wizard-Architektur (wichtig für Erweiterungen)

```
KlageSection.jsx            ← Alle States (wizardUnfallText, wizardRwText, wizardVerzugText, ...)
  └─ KlageWizard.jsx        ← Nur Präsentation, empfängt Props
       ├─ StepRubrum         ← read-only, beklagte-Prop
       ├─ StepAktLeg         ← aktLegTyp/Freigabe/Datum, Override-Text
       ├─ StepUnfall         ← schilderungOriginal + unfalltextEdit
       ├─ StepSchaden        ← wizardPos, mitSG, sgMind
       ├─ StepRw             ← hq/hb lokal, rwText in KlageSection, EinwandePanel
       ├─ StepVerzug         ← verzug + zinsenAb (read), wizardVerzugText
       └─ StepZusammenfassung ← Generieren-Button
```

**kannWeiter-Check: step === 4** (Schadenpositionen) – nicht step === 2!

---

## Offene Punkte

### Datenfehler (manuell zu beheben)
- Akte **1/80**: `betrag_gefordert` in `regulierung_positionen` ist noch **Netto** (aus altem WDM-Import).
  → WDM-Abrechnung löschen und neu importieren → dann stimmt der Wert.

### Nächste Features

| Priorität | PRD | Beschreibung |
|---|---|---|
| Nächste | **PRD-23b** | Rechnungs-Parser + Auto-Zuordnung |
| Alternativ | **PRD-03** | Klagegenerator Abschlusstest (Formatierungen final prüfen) |
| Groß | **PRD-22c** | Mandanten-Fragebogen (5–7 Sessions) |

### Künftige Wizard-Erweiterungen
- **EinwandePanel**: neue Einwands-Kategorien (z.B. Haftungseinwände, prozessuale Einwände) → `KATEGORIE_ORDER`/`KATEGORIE_LABELS` in KlageWizard.jsx + neue `kategorie`-Werte in `kuerzungsarten`-Tabelle
- **Step 5 RW**: `§ 7 StVG / § 823 BGB / § 115 VVG` Standardformulierungen als Textbausteine
- **PRD-24b+**: Vollständiger 5-Step+ Wizard mit Unfallhergang-Details

---

## Kritische Regeln

- `unfallakte` PK = `az TEXT`
- ⛔ raEloakte: NUR SELECT
- ⛔ Python 3.9: keine Union-Types `X | Y`, kein Walrus `:=`
- ⛔ Vor Deploy: Code-Review (Routen, _dok_dict, d.typ Fallback, Hooks, Netto/Brutto, Dict-Mapping)
- ⛔ Override-Dict vollständig durchreichen (B-08 Analog)
- § 203 StGB: Keine Mandantendaten extern
- ⚠️ WSL-Mount vor jedem Docker-Start!

---

## Docker-Befehle

```powershell
# ⚠️ WSL-Mount (JEDES MAL vor Docker-Start!)
wsl --user root
mount -t cifs //192.168.10.100/ServerSQL/ra /mnt/eakte -o username=admin,password=passwort,ro
exit

docker compose up -d

# Schema prüfen (soll 28 zeigen)
docker exec unfallakten-backend-dev python3 -c "import sqlite3; c=sqlite3.connect('/app/data/unfallakten.db'); print('Schema:', c.execute('SELECT MAX(version) FROM schema_version').fetchone()[0])"

# Deploy Frontend
docker cp src/sections/KlageWizard.jsx   unfallakten-frontend-dev:/app/src/sections/KlageWizard.jsx
docker cp src/sections/KlageSection.jsx  unfallakten-frontend-dev:/app/src/sections/KlageSection.jsx
docker restart unfallakten-frontend-dev

# Deploy Backend
docker cp backend/routers/klage_routes.py unfallakten-backend-dev:/app/backend/routers/klage_routes.py
docker cp backend/word/klage_service.py   unfallakten-backend-dev:/app/backend/word/klage_service.py
docker restart unfallakten-backend-dev
```
